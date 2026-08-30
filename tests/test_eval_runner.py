import json

from aap.core.definition.validate import validate_definition
from aap.core.evaluation.eval_runner import load_eval_set, run_eval_set
from aap.tools.builtin.state import make_state_update_tool
from aap.tools.mock.tools import build_mock_registry
from aap.tools.mock.world import default_world


def _registry_factory(agent_id, agent_version_id, definition):
    def factory(run_id, faults):
        world = default_world()
        for f in faults:
            world.schedule_fault(f["tool_id"], f["fault"])
        registry = build_mock_registry(world, run_id=run_id, agent_id=agent_id, agent_version_id=agent_version_id)
        spec, fn = make_state_update_tool(run_id, definition.memory.state_schema)
        registry.register(spec, fn)
        return registry
    return factory


def test_load_eval_set_parses_jsonl(tmp_path):
    path = tmp_path / "evals.jsonl"
    path.write_text(
        '{"id": "a", "plan": []}\n\n{"id": "b", "plan": []}\n', encoding="utf-8",
    )
    scenarios = load_eval_set(path)
    assert [s["id"] for s in scenarios] == ["a", "b"]


def test_run_eval_set_all_pass(tmp_path, demand_hunter_definition):
    definition = validate_definition(demand_hunter_definition)
    eval_path = tmp_path / "evals.jsonl"
    eval_path.write_text(json.dumps({
        "id": "encuentra-senal",
        "plan": [
            {"tool_id": "search.web.mock", "arguments": {"query": "automatización"}},
            {"tool_id": "state.update", "arguments": {"senales_validas": 1}},
        ],
        "expect": {"status": "completed", "termination_reason": "completed", "state": {"senales_validas": 1}},
    }) + "\n", encoding="utf-8")

    report = run_eval_set(
        definition, "v1", _registry_factory(definition.id, "v1", definition), eval_path,
    )
    assert report["total"] == 1
    assert report["passed"] == 1
    assert report["failed"] == 0
    assert report["scenarios"][0]["passed"] is True


def test_run_eval_set_detects_a_real_mismatch(tmp_path, demand_hunter_definition):
    """Si esto no fallara, el comprobador no estaría comprobando nada."""
    definition = validate_definition(demand_hunter_definition)
    eval_path = tmp_path / "evals.jsonl"
    eval_path.write_text(json.dumps({
        "id": "criterio-imposible",
        "plan": [{"tool_id": "search.web.mock", "arguments": {"query": "automatización"}}],
        "expect": {"min_tool_calls": 99, "state": {"senales_validas": 1}},
    }) + "\n", encoding="utf-8")

    report = run_eval_set(
        definition, "v1", _registry_factory(definition.id, "v1", definition), eval_path,
    )
    assert report["passed"] == 0
    assert report["failed"] == 1
    failures = report["scenarios"][0]["failures"]
    assert any("99 tool calls" in f for f in failures)
    assert any("senales_validas" in f for f in failures)


def test_run_eval_set_applies_faults(tmp_path, demand_hunter_definition):
    definition = validate_definition(demand_hunter_definition)
    eval_path = tmp_path / "evals.jsonl"
    eval_path.write_text(json.dumps({
        "id": "busqueda-vacia",
        "plan": [{"tool_id": "search.web.mock", "arguments": {"query": "automatización"}}],
        "faults": [{"tool_id": "search.web.mock", "fault": "empty"}],
        "expect": {"tool_call_statuses": [{"tool_id": "search.web.mock", "status": "ok"}]},
    }) + "\n", encoding="utf-8")

    report = run_eval_set(
        definition, "v1", _registry_factory(definition.id, "v1", definition), eval_path,
    )
    assert report["passed"] == 1  # "ok" sigue siendo ok aunque el resultado esté vacío


def test_run_eval_set_records_run_ids_for_full_traceability(tmp_path, demand_hunter_definition):
    from aap.core.events.log import list_events

    definition = validate_definition(demand_hunter_definition)
    eval_path = tmp_path / "evals.jsonl"
    eval_path.write_text(json.dumps({
        "id": "trazable", "plan": [{"tool_id": "search.web.mock", "arguments": {"query": "x"}}], "expect": {},
    }) + "\n", encoding="utf-8")

    report = run_eval_set(
        definition, "v1", _registry_factory(definition.id, "v1", definition), eval_path,
    )
    run_id = report["scenarios"][0]["run_id"]
    events = list_events(run_id)
    assert events[0]["type"] == "run.started"
    assert events[-1]["type"] == "run.finished"
