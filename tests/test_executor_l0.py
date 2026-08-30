from aap.core.definition.validate import validate_definition
from aap.core.events.log import list_events
from aap.core.runtime.executor import execute_run
from aap.core.runtime.runs import create_run
from tests.conftest import build_registry_with_state

from aap.tools.mock.world import default_world


class _ExplodingRouter:
    """Si L0 llegara a llamar al LLM, algo está mal: L0 no tiene LLM."""

    def complete(self, capability, req):
        raise AssertionError("L0 no debe llamar al LLM jamás (§8.2)")


def _l0_definition(base: dict) -> dict:
    d = dict(base)
    d["runtime"] = {
        "autonomy_level": 0,
        "fixed_steps": [
            {"tool_id": "search.web.mock", "arguments": {"query": "automatización"}},
            {"tool_id": "db.upsert.mock", "arguments": {
                "table": "companies", "natural_key": "manual-1", "values": {"name": "X"},
            }},
        ],
    }
    return d


def test_l0_runs_fixed_sequence_without_any_llm_call(demand_hunter_definition):
    definition = validate_definition(_l0_definition(demand_hunter_definition))
    world = default_world()
    run = create_run(definition.id, "v1")
    registry = build_registry_with_state(world, run["id"], definition.memory.state_schema)

    result = execute_run(definition, _ExplodingRouter(), registry, run["id"], {})

    assert result["status"] == "completed"
    assert result["termination_reason"] == "sequence_completed"
    assert result["steps"] == 2
    assert result["tool_calls"] == 2

    events = list_events(run["id"])
    assert [e["type"] for e in events][:3] == ["run.started", "step.started", "tool.called"]
    assert events[-1]["type"] == "run.finished"


def test_l0_stops_charging_budget_once_tool_calls_are_exhausted(demand_hunter_definition):
    d = _l0_definition(demand_hunter_definition)
    d["policies"]["budget"]["max_tool_calls"] = 1
    definition = validate_definition(d)
    world = default_world()
    run = create_run(definition.id, "v1")
    registry = build_registry_with_state(world, run["id"], definition.memory.state_schema)

    result = execute_run(definition, _ExplodingRouter(), registry, run["id"], {})

    assert result["status"] == "exhausted"
    assert result["termination_reason"] == "max_tool_calls"
    assert result["tool_calls"] == 1
