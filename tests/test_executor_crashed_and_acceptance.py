"""Camino CRASHED (§8.4) y el criterio de aceptación de M5: un agente
completo, corriendo de punta a punta con el provider mock, sin GPU y sin
ningún céntimo de inferencia real."""

import pytest

from aap.core.definition.validate import validate_definition
from aap.core.events.log import list_events
from aap.core.llm.interface import CompletionResult, ToolCall, Usage
from aap.core.llm.providers.mock import MockProvider
from aap.core.memory.longterm import list_memories
from aap.core.runtime.executor import UnsupportedAutonomyLevelError, execute_run
from aap.core.runtime.runs import create_run, get_run
from aap.domain.entities import query_entities
from aap.tools.mock.world import default_world
from tests.conftest import build_registry_with_state, make_scripted_router


def test_l4_is_unsupported_and_run_is_marked_crashed(demand_hunter_definition):
    d = dict(demand_hunter_definition)
    d["runtime"] = {"autonomy_level": 4}
    definition = validate_definition(d)
    world = default_world()
    run = create_run(definition.id, "v1")
    registry = build_registry_with_state(world, run["id"], definition.memory.state_schema)

    with pytest.raises(UnsupportedAutonomyLevelError):
        execute_run(definition, make_scripted_router(MockProvider()), registry, run["id"], {})

    persisted = get_run(run["id"])
    assert persisted["status"] == "crashed"
    assert persisted["termination_reason"] == "unhandled_exception"

    events = list_events(run["id"])
    assert events[-2]["type"] == "error.raised"
    assert events[-1]["type"] == "run.finished"


def test_m5_acceptance_full_agent_runs_end_to_end_with_mock_provider(demand_hunter_definition):
    """Reproduce el flujo del brief: recibir objetivo -> buscar -> decidir
    -> usar tool -> registrar señal -> actualizar estado -> evaluar ->
    terminar. Cero llamadas a un LLM real, cero servicios externos."""
    definition = validate_definition(demand_hunter_definition)  # autonomy_level=2 en el fixture
    world = default_world()
    run = create_run(definition.id, "v1", trigger="manual", input_data={"sector": "logistica"})
    run_id = run["id"]
    registry = build_registry_with_state(
        world, run_id, definition.memory.state_schema,
        agent_id=definition.id, agent_version_id="v1",
    )

    plan = CompletionResult(
        text=None,
        tool_calls=[
            ToolCall(id="1", tool_id="search.web.mock", arguments={"query": "automatización"}),
            ToolCall(id="2", tool_id="db.upsert.mock", arguments={
                "table": "signals", "natural_key": "rutasdelsur.mock:automatizacion",
                "values": {"company_id": "c1", "type": "automatización"},
            }),
            ToolCall(id="3", tool_id="memory.write.mock", arguments={
                "type": "patron_senal", "content": "logística + automatización es un patrón fuerte",
                "source_run_id": run_id,
            }),
            ToolCall(id="4", tool_id="state.update", arguments={"fase": "registrar", "senales_validas": 1}),
        ],
        usage=Usage(prompt_tokens=120, completion_tokens=40, cost_usd=0.003, latency_ms=15),
        model_used="mock-plan",
        finish_reason="tool_calls",
    )
    router = make_scripted_router(MockProvider(script=[plan]))

    result = execute_run(definition, router, registry, run_id, {"sector": "logistica"})

    assert result["status"] == "completed"
    assert result["termination_reason"] == "completed"
    assert result["tool_calls"] == 4
    assert result["cost_usd"] == pytest.approx(0.003)
    assert result["tokens_in"] == 120
    assert result["tokens_out"] == 40

    events = list_events(run_id)
    assert [e["type"] for e in events] == [
        "run.started", "step.started", "llm.called", "decision.made",
        "tool.called", "tool.result",
        "tool.called", "tool.result",
        "tool.called", "tool.result",
        "tool.called", "tool.result", "state.updated",
        "run.finished",
    ]

    # La señal y la memoria viven en domain.db/control.db, no en el mundo
    # simulado en RAM: eso es justo lo que H6 tenía que demostrar (§9.2, P4).
    signals = query_entities("signals")
    assert len(signals) == 1
    assert signals[0]["source_run_id"] == run_id
    assert signals[0]["agent_version_id"] == "v1"

    memories = list_memories(definition.id)
    assert len(memories) == 1
    assert memories[0]["source_run_id"] == run_id
