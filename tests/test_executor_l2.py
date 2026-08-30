from aap.core.definition.validate import validate_definition
from aap.core.events.log import list_events
from aap.core.llm.interface import CompletionResult, ToolCall, Usage
from aap.core.llm.providers.mock import MockProvider
from aap.core.runtime.executor import execute_run
from aap.core.runtime.runs import create_run
from aap.tools.mock.world import default_world
from tests.conftest import build_registry_with_state, make_scripted_router


def _l2_definition(base: dict) -> dict:
    d = dict(base)
    d["runtime"] = {"autonomy_level": 2, "max_iterations": 5}
    return d


def _usage() -> Usage:
    return Usage(prompt_tokens=80, completion_tokens=30, cost_usd=0.002, latency_ms=8)


def test_l2_executes_the_whole_plan_from_a_single_llm_call(demand_hunter_definition):
    definition = validate_definition(_l2_definition(demand_hunter_definition))
    world = default_world()
    run = create_run(definition.id, "v1")
    registry = build_registry_with_state(world, run["id"], definition.memory.state_schema)

    plan = CompletionResult(
        text=None,
        tool_calls=[
            ToolCall(id="1", tool_id="search.web.mock", arguments={"query": "automatización"}),
            ToolCall(id="2", tool_id="state.update", arguments={"senales_validas": 1}),
        ],
        usage=_usage(),
        model_used="mock-scripted",
        finish_reason="tool_calls",
    )
    provider = MockProvider(script=[plan])
    router = make_scripted_router(provider)

    result = execute_run(definition, router, registry, run["id"], {"sector": "logistica"})

    assert provider.calls_made == 1  # el plan no se reconsulta
    assert result["steps"] == 1
    assert result["tool_calls"] == 2
    assert result["status"] == "completed"  # el criterio se cumplió tras el plan
    assert result["termination_reason"] == "completed"
    assert result["output"]["final_state"]["senales_validas"] == 1

    events = list_events(run["id"])
    plan_events = [e for e in events if e["type"] == "llm.called"]
    assert plan_events[0]["payload"]["phase"] == "plan"
    assert any(e["type"] == "state.updated" for e in events)


def test_l2_without_meeting_criteria_still_finishes_after_the_plan(demand_hunter_definition):
    definition = validate_definition(_l2_definition(demand_hunter_definition))
    world = default_world()
    run = create_run(definition.id, "v1")
    registry = build_registry_with_state(world, run["id"], definition.memory.state_schema)

    plan = CompletionResult(
        text=None,
        tool_calls=[ToolCall(id="1", tool_id="search.web.mock", arguments={"query": "automatización"})],
        usage=_usage(),
        model_used="mock-scripted",
        finish_reason="tool_calls",
    )
    router = make_scripted_router(MockProvider(script=[plan]))

    result = execute_run(definition, router, registry, run["id"], {})

    assert result["status"] == "completed"
    assert result["termination_reason"] == "plan_executed"
