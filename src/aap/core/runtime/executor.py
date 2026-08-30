"""El intérprete (§1.1, §8.2): cinco funciones que comparten toda la
infraestructura (contexto, policy, tools, eventos, presupuesto) y
difieren solo en la forma del bucle. L4 queda fuera de V1.

`execute_run` es el único punto de entrada. No conoce ningún agente
concreto — recibe una `AgentDefinition` ya validada, un `ModelRouter`, y
un `ToolRegistry` ya ensamblado por quien orquesta el run (H7+); el
executor no decide qué tools existen, solo las invoca a través del
`ToolBroker`.
"""

import json

from aap.core.definition.models import AgentDefinition
from aap.core.events.log import emit
from aap.core.llm.interface import CompletionRequest, CompletionResult, Message
from aap.core.llm.router import ModelRouter
from aap.core.policy.context import PolicyContext
from aap.core.policy.engine import PolicyEngine
from aap.core.runtime.budget import BudgetManager
from aap.core.runtime.context import build_system_message, build_tool_specs
from aap.core.runtime.criteria import InvalidCriterionError, evaluate_all
from aap.core.runtime.runs import (
    finish_run,
    get_run,
    record_llm_usage,
    record_step,
    record_tool_call_metric,
)
from aap.core.runtime.state import compute_diff, default_state, get_state, init_state
from aap.core.runtime.constants import STATE_UPDATE_TOOL_ID
from aap.core.tools.broker import ToolBroker, ToolResult
from aap.core.runtime.tool_calls import record_tool_call
from aap.core.tools.registry import ToolRegistry

class UnsupportedAutonomyLevelError(ValueError):
    pass


def execute_run(
    definition: AgentDefinition,
    router: ModelRouter,
    registry: ToolRegistry,
    run_id: str,
    input_data: dict | None = None,
) -> dict:
    input_data = input_data or {}
    budget = BudgetManager(definition.policies.budget)
    ctx = PolicyContext(policies=definition.policies, budget=budget, dry_run=False)
    broker = ToolBroker(registry, PolicyEngine())

    init_state(run_id, default_state(definition.memory.state_schema))
    emit(run_id, "run.started", "AUDIT", payload={
        "autonomy_level": definition.runtime.autonomy_level, "input": input_data,
    })

    level = definition.runtime.autonomy_level
    try:
        if level == 0:
            status, reason, output = _run_l0(definition, ctx, broker, run_id)
        elif level == 1:
            status, reason, output = _run_single_shot(
                definition, ctx, router, broker, registry, run_id, input_data, phase="react"
            )
        elif level == 2:
            status, reason, output = _run_single_shot(
                definition, ctx, router, broker, registry, run_id, input_data, phase="plan"
            )
        elif level == 3:
            status, reason, output = _run_l3(definition, ctx, router, broker, registry, run_id, input_data)
        else:
            raise UnsupportedAutonomyLevelError(
                f"autonomy_level={level} no soportado en V1 (L4 requiere evaluación madura, §24.2)"
            )
    except Exception as exc:  # CRASHED (§8.4): un bug, no un fallo esperado del agente
        emit(run_id, "error.raised", "ERROR", payload={"error": str(exc)})
        finish_run(run_id, status="crashed", termination_reason="unhandled_exception", error=str(exc))
        emit(run_id, "run.finished", "AUDIT", payload={"status": "crashed"})
        raise

    finish_run(run_id, status=status, termination_reason=reason, output_data=output)
    emit(run_id, "run.finished", "AUDIT", payload={"status": status, "termination_reason": reason})
    return get_run(run_id)


# ───────────────────────── L0 — determinista ─────────────────────────

def _run_l0(definition: AgentDefinition, ctx: PolicyContext, broker: ToolBroker, run_id: str):
    state = get_state(run_id)["state"]
    for i, fixed in enumerate(definition.runtime.fixed_steps, start=1):
        exhausted = ctx.budget.exhausted_dimension()
        if exhausted:
            return "exhausted", exhausted, {"final_state": state}
        record_step(run_id)
        emit(run_id, "step.started", "INFO", step=i)
        _invoke_tool(broker, ctx, run_id, i, fixed.tool_id, fixed.arguments)
        state = get_state(run_id)["state"]

    outcome = _evaluate_termination(definition, state)
    return (outcome or "completed"), (outcome or "sequence_completed"), {"final_state": state}


# ─────────────────── L1 (react) y L2 (plan): un solo tiro ───────────────────

def _run_single_shot(
    definition: AgentDefinition, ctx: PolicyContext, router: ModelRouter,
    broker: ToolBroker, registry: ToolRegistry, run_id: str, input_data: dict, phase: str,
):
    exhausted = ctx.budget.exhausted_dimension()
    if exhausted:
        return "exhausted", exhausted, {}

    record_step(run_id)
    emit(run_id, "step.started", "INFO", step=1)
    messages = [
        build_system_message(definition, phase=phase),
        Message(role="user", content=json.dumps(input_data, ensure_ascii=False)),
    ]
    tool_specs = build_tool_specs(definition, registry)
    result = _call_llm(router, definition.brain.primary.capability, messages, tool_specs, ctx, run_id, phase)
    emit(run_id, "decision.made", "INFO", step=1, payload={
        "phase": phase, "tool_calls": [tc.tool_id for tc in result.tool_calls], "text": result.text,
    })

    for tc in result.tool_calls:
        exhausted = ctx.budget.exhausted_dimension()
        if exhausted:
            state = get_state(run_id)["state"]
            return "exhausted", exhausted, {"final_state": state}
        _invoke_tool(broker, ctx, run_id, 1, tc.tool_id, tc.arguments)

    state = get_state(run_id)["state"]
    outcome = _evaluate_termination(definition, state)
    default_reason = "plan_executed" if phase == "plan" else "reacted"
    return (outcome or "completed"), (outcome or default_reason), {"text": result.text, "final_state": state}


# ───────────────────── L3 — iterativo, con replanificación ─────────────────────

def _run_l3(
    definition: AgentDefinition, ctx: PolicyContext, router: ModelRouter,
    broker: ToolBroker, registry: ToolRegistry, run_id: str, input_data: dict,
):
    messages = [
        build_system_message(definition, phase="react"),
        Message(role="user", content=json.dumps(input_data, ensure_ascii=False)),
    ]
    tool_specs = build_tool_specs(definition, registry)

    for iteration in range(1, definition.runtime.max_iterations + 1):
        exhausted = ctx.budget.exhausted_dimension()
        if exhausted:
            state = get_state(run_id)["state"]
            return "exhausted", exhausted, {"final_state": state}

        record_step(run_id)
        emit(run_id, "step.started", "INFO", step=iteration)
        result = _call_llm(router, definition.brain.primary.capability, messages, tool_specs, ctx, run_id, "react")
        emit(run_id, "decision.made", "INFO", step=iteration, payload={
            "tool_calls": [tc.tool_id for tc in result.tool_calls], "text": result.text,
        })

        if not result.tool_calls:
            state = get_state(run_id)["state"]
            outcome = _evaluate_termination(definition, state)
            return (outcome or "completed"), (outcome or "model_finished"), {
                "text": result.text, "final_state": state,
            }

        messages.append(Message(role="assistant", content=result.text or ""))
        for tc in result.tool_calls:
            exhausted = ctx.budget.exhausted_dimension()
            if exhausted:
                state = get_state(run_id)["state"]
                return "exhausted", exhausted, {"final_state": state}
            tool_result = _invoke_tool(broker, ctx, run_id, iteration, tc.tool_id, tc.arguments)
            messages.append(Message(
                role="tool", tool_call_id=tc.id, name=tc.tool_id,
                content=json.dumps(tool_result.result if tool_result.result is not None
                                    else {"error": tool_result.error}, ensure_ascii=False),
            ))

        state = get_state(run_id)["state"]
        outcome = _evaluate_termination(definition, state)
        if outcome:
            return outcome, outcome, {"final_state": state}

    state = get_state(run_id)["state"]
    return "exhausted", "max_iterations", {"final_state": state}


# ───────────────────────────── helpers compartidos ─────────────────────────────

def _call_llm(
    router: ModelRouter, capability, messages: list[Message], tool_specs, ctx: PolicyContext,
    run_id: str, phase: str,
) -> CompletionResult:
    req = CompletionRequest(messages=messages, tools=tool_specs or None, capability=capability)
    result = router.complete(capability, req)
    ctx.budget.consume_llm_usage(result.usage)
    record_llm_usage(run_id, result.usage.prompt_tokens, result.usage.completion_tokens, result.usage.cost_usd)
    emit(run_id, "llm.called", "INFO", payload={
        "phase": phase, "model_used": result.model_used,
        "prompt_tokens": result.usage.prompt_tokens, "completion_tokens": result.usage.completion_tokens,
        "cost_usd": result.usage.cost_usd, "latency_ms": result.usage.latency_ms,
        "finish_reason": result.finish_reason,
    })
    return result


def _invoke_tool(
    broker: ToolBroker, ctx: PolicyContext, run_id: str, step: int, tool_id: str, arguments: dict,
) -> ToolResult:
    old_state = get_state(run_id)["state"] if tool_id == STATE_UPDATE_TOOL_ID else None

    emit(run_id, "tool.called", "INFO", step=step, payload={"tool_id": tool_id, "arguments": arguments})
    result = broker.invoke(ctx, tool_id, arguments)

    if result.policy_decision != "ALLOW":
        emit(run_id, "policy.evaluated", "AUDIT", step=step, payload={
            "tool_id": tool_id, "decision": result.policy_decision, "reason": result.error,
        })

    record_tool_call(run_id, step, tool_id, arguments, result)
    if result.policy_decision == "ALLOW":
        record_tool_call_metric(run_id)

    emit(run_id, "tool.result", "INFO" if result.status == "ok" else "WARN", step=step, payload={
        "tool_id": tool_id, "status": result.status, "error": result.error,
    })

    if tool_id == STATE_UPDATE_TOOL_ID and result.status == "ok":
        diff = compute_diff(old_state, result.result["state"])
        emit(run_id, "state.updated", "INFO", step=step, payload=diff)

    return result


def _evaluate_termination(definition: AgentDefinition, state: dict) -> str | None:
    """None significa "no se puede decidir todavía", no "fallo silencioso":
    un criterio mal formado o que cita una variable que aún no existe en el
    estado no debe tumbar el run (§14.3)."""
    try:
        if definition.goal.failure_criteria and evaluate_all(definition.goal.failure_criteria, state):
            return "failed"
        if definition.goal.success_criteria and evaluate_all(definition.goal.success_criteria, state):
            return "completed"
    except InvalidCriterionError:
        return None
    return None
