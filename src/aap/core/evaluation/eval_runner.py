"""Evaluación por rúbrica, Capa 2 (§12.2) — SOLO comprobaciones
programáticas en V1. Nada de juez-LLM todavía: "el juez-LLM es ruidoso y
sesgado hacia respuestas largas... jamás para diferencias de menos de un
10 %" describe un coste que esta fase no tiene por qué pagar (la
brief pide explícitamente no usarlo salvo que sea estrictamente
necesario).

Cada escenario del eval set declara un plan fijo de tool_calls (lo que
un LLM real habría decidido) para que el resultado sea 100 % reproducible
— la variable que se está probando es el AGENTE (sus políticas, su
schema de estado, sus criterios), no el modelo.
"""

import json
from pathlib import Path
from typing import Callable

from aap.core.definition.models import AgentDefinition
from aap.core.llm.interface import CompletionResult, ToolCall, Usage
from aap.core.llm.providers.mock import MockProvider
from aap.core.llm.router import ModelRouter
from aap.core.runtime.executor import execute_run
from aap.core.runtime.runs import create_run, get_run
from aap.core.runtime.state import StateNotFoundError, get_state
from aap.core.runtime.tool_calls import list_tool_calls
from aap.core.tools.registry import ToolRegistry

RegistryFactory = Callable[[str, list[dict]], ToolRegistry]


def load_eval_set(path: Path) -> list[dict]:
    scenarios = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            scenarios.append(json.loads(line))
    return scenarios


def _plan_to_completion_result(plan: list[dict]) -> CompletionResult:
    tool_calls = [
        ToolCall(id=str(i), tool_id=step["tool_id"], arguments=step.get("arguments", {}))
        for i, step in enumerate(plan, start=1)
    ]
    return CompletionResult(
        text=None, tool_calls=tool_calls,
        usage=Usage(prompt_tokens=0, completion_tokens=0, cost_usd=0.0, latency_ms=1),
        model_used="eval-scripted", finish_reason="tool_calls",
    )


def _scripted_router(plan: list[dict]) -> ModelRouter:
    provider = MockProvider(script=[_plan_to_completion_result(plan)])
    config = {
        "providers": {},
        "routing": {cap: ["scripted"] for cap in ("cheap", "standard", "heavy", "coding", "embedding")},
        "policies": {"on_unavailable": "fail"},
    }
    return ModelRouter(config, providers={"scripted": provider})


def _check_expectations(run: dict, state: dict, tool_calls: list[dict], expect: dict) -> list[str]:
    failures = []
    if "status" in expect and run["status"] != expect["status"]:
        failures.append(f"status esperado {expect['status']!r}, obtenido {run['status']!r}")
    if "termination_reason" in expect and run["termination_reason"] != expect["termination_reason"]:
        failures.append(
            f"termination_reason esperado {expect['termination_reason']!r}, "
            f"obtenido {run['termination_reason']!r}"
        )
    if "min_tool_calls" in expect and run["tool_calls"] < expect["min_tool_calls"]:
        failures.append(f"se esperaban >= {expect['min_tool_calls']} tool calls, hubo {run['tool_calls']}")
    for key, expected_value in expect.get("state", {}).items():
        actual = state.get(key)
        if actual != expected_value:
            failures.append(f"state.{key} esperado {expected_value!r}, obtenido {actual!r}")
    for expected_call in expect.get("tool_call_statuses", []):
        matches = [tc for tc in tool_calls if tc["tool_id"] == expected_call["tool_id"]]
        if not any(tc["status"] == expected_call["status"] for tc in matches):
            failures.append(
                f"se esperaba algún tool call de {expected_call['tool_id']} con "
                f"status={expected_call['status']!r}, no se encontró"
            )
    return failures


def run_eval_set(
    definition: AgentDefinition,
    agent_version_id: str,
    registry_factory: RegistryFactory,
    eval_set_path: Path,
) -> dict:
    """`registry_factory(run_id, faults)` deja que quien llama decida qué
    mundo de tools usar — el eval runner no conoce el mundo mock ni
    ningún otro concreto (mismo principio que el executor, §6.13)."""
    scenarios = load_eval_set(eval_set_path)
    results = []
    for scenario in scenarios:
        run = create_run(
            definition.id, agent_version_id, trigger="eval", input_data=scenario.get("input", {}),
        )
        registry = registry_factory(run["id"], scenario.get("faults", []))
        router = _scripted_router(scenario["plan"])
        execute_run(definition, router, registry, run["id"], scenario.get("input", {}))

        final_run = get_run(run["id"])
        try:
            state = get_state(run["id"])["state"]
        except StateNotFoundError:
            state = {}
        tool_calls = list_tool_calls(run["id"])
        failures = _check_expectations(final_run, state, tool_calls, scenario.get("expect", {}))

        results.append({
            "scenario_id": scenario["id"],
            "description": scenario.get("description", ""),
            "run_id": run["id"],
            "passed": not failures,
            "failures": failures,
            "run_status": final_run["status"],
            "cost_usd": final_run["cost_usd"],
        })

    passed = sum(1 for r in results if r["passed"])
    return {"total": len(results), "passed": passed, "failed": len(results) - passed, "scenarios": results}
