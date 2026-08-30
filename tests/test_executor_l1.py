from aap.core.definition.validate import validate_definition
from aap.core.llm.interface import CompletionResult, ToolCall, Usage
from aap.core.llm.providers.mock import MockProvider
from aap.core.runtime.executor import execute_run
from aap.core.runtime.runs import create_run
from aap.tools.mock.world import default_world
from tests.conftest import build_registry_with_state, make_scripted_router


def _l1_definition(base: dict) -> dict:
    d = dict(base)
    d["runtime"] = {"autonomy_level": 1, "max_iterations": 5}
    return d


def _usage(**overrides) -> Usage:
    defaults = dict(prompt_tokens=50, completion_tokens=10, cost_usd=0.001, latency_ms=5)
    defaults.update(overrides)
    return Usage(**defaults)


def test_l1_executes_a_single_llm_decision_and_its_tool_calls(demand_hunter_definition):
    definition = validate_definition(_l1_definition(demand_hunter_definition))
    world = default_world()
    run = create_run(definition.id, "v1")
    registry = build_registry_with_state(world, run["id"], definition.memory.state_schema)

    scripted = CompletionResult(
        text=None,
        tool_calls=[ToolCall(id="1", tool_id="search.web.mock", arguments={"query": "automatización"})],
        usage=_usage(),
        model_used="mock-scripted",
        finish_reason="tool_calls",
    )
    router = make_scripted_router(MockProvider(script=[scripted]))

    result = execute_run(definition, router, registry, run["id"], {"sector": "logistica"})

    assert result["steps"] == 1
    assert result["tool_calls"] == 1
    assert result["tokens_in"] == 50
    assert result["tokens_out"] == 10
    # sin state.update, senales_validas se queda en su default (0): el
    # criterio de éxito no se cumple, pero L1 no reintenta — termina igual.
    assert result["status"] == "completed"
    assert result["termination_reason"] == "reacted"


def test_l1_never_calls_the_llm_a_second_time_even_with_tool_calls_pending(demand_hunter_definition):
    """Es lo que distingue L1 de L3: una sola decisión, nunca replanifica."""
    definition = validate_definition(_l1_definition(demand_hunter_definition))
    world = default_world()
    run = create_run(definition.id, "v1")
    registry = build_registry_with_state(world, run["id"], definition.memory.state_schema)

    scripted = CompletionResult(
        text=None,
        tool_calls=[
            ToolCall(id="1", tool_id="search.web.mock", arguments={"query": "automatización"}),
            ToolCall(id="2", tool_id="memory.write.mock", arguments={
                "type": "empresa_descartada", "content": "nota", "source_run_id": run["id"],
            }),
        ],
        usage=_usage(),
        model_used="mock-scripted",
        finish_reason="tool_calls",
    )
    provider = MockProvider(script=[scripted])
    router = make_scripted_router(provider)

    execute_run(definition, router, registry, run["id"], {})

    assert provider.calls_made == 1


def test_l1_stops_cleanly_when_budget_runs_out_mid_tool_execution(demand_hunter_definition):
    d = _l1_definition(demand_hunter_definition)
    d["policies"]["budget"]["max_tool_calls"] = 1
    definition = validate_definition(d)
    world = default_world()
    run = create_run(definition.id, "v1")
    registry = build_registry_with_state(world, run["id"], definition.memory.state_schema)

    scripted = CompletionResult(
        text=None,
        tool_calls=[
            ToolCall(id="1", tool_id="search.web.mock", arguments={"query": "automatización"}),
            ToolCall(id="2", tool_id="db.query.mock", arguments={"table": "companies"}),
        ],
        usage=_usage(),
        model_used="mock-scripted",
        finish_reason="tool_calls",
    )
    router = make_scripted_router(MockProvider(script=[scripted]))

    result = execute_run(definition, router, registry, run["id"], {})

    assert result["status"] == "exhausted"
    assert result["termination_reason"] == "max_tool_calls"
    assert result["tool_calls"] == 1
