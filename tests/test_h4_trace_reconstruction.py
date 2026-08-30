"""Criterio de aceptación de H4: reconstruir la traza completa de un run
desde `events`. Todavía no existe el executor (eso es H5): aquí se
ensambla el mismo camino a mano —run, estado, tool call, evento de
política— para probar que las piezas de H3+H4 encajan.
"""

from aap.core.events.log import emit, list_events
from aap.core.policy.engine import PolicyEngine
from aap.core.runtime.runs import create_run, finish_run, get_run, record_step, record_tool_call_metric
from aap.core.runtime.state import compute_diff, get_state, init_state, update_state
from aap.core.runtime.tool_calls import list_tool_calls, record_tool_call
from aap.core.tools.broker import ToolBroker
from aap.tools.mock.tools import build_mock_registry
from aap.tools.mock.world import default_world
from tests.conftest import make_policy_context


def test_full_trace_is_reconstructible_from_events():
    world = default_world()
    registry = build_mock_registry(world)
    broker = ToolBroker(registry, PolicyEngine())
    ctx = make_policy_context(
        database={"domain_db": "read_write", "tables": ["companies", "signals"]},
    )

    run = create_run("demand-hunter", "version-1", trigger="manual", input_data={"sector": "logistica"})
    run_id = run["id"]
    emit(run_id, "run.started", "AUDIT", payload={"trigger": "manual"})

    init_state(run_id, {"fase": "buscar", "senales_validas": 0})
    record_step(run_id)
    emit(run_id, "step.started", "INFO", step=1)

    emit(run_id, "tool.called", "INFO", step=1, payload={"tool_id": "search.web.mock"})
    tool_result = broker.invoke(ctx, "search.web.mock", {"query": "automatización"})
    record_tool_call(run_id, step=1, tool_id="search.web.mock",
                      arguments={"query": "automatización"}, result=tool_result)
    record_tool_call_metric(run_id)
    emit(run_id, "tool.result", "INFO", step=1, payload={"status": tool_result.status})

    old_state = get_state(run_id)
    new_values = {"fase": "registrar", "senales_validas": 1}
    diff = compute_diff(old_state["state"], new_values)
    update_state(run_id, new_values, expected_version=old_state["version"])
    emit(run_id, "state.updated", "INFO", step=1, payload=diff)

    # Un intento de tool prohibida por la política, para demostrar el DENY end-to-end.
    denied = broker.invoke(ctx, "db.upsert.mock", {"table": "unknown_table", "natural_key": "x", "values": {}})
    emit(run_id, "policy.evaluated", "AUDIT", step=1, payload={"decision": denied.policy_decision, "reason": denied.error})
    record_tool_call(run_id, step=1, tool_id="db.upsert.mock",
                      arguments={"table": "unknown_table"}, result=denied)

    finish_run(run_id, status="completed", termination_reason="success", output_data={"qualified": 1})
    emit(run_id, "run.finished", "AUDIT", payload={"termination_reason": "success"})

    # --- reconstrucción, como haría el Run Inspector ---
    final_run = get_run(run_id)
    events = list_events(run_id)
    tool_calls = list_tool_calls(run_id)

    assert final_run["status"] == "completed"
    assert final_run["steps"] == 1
    assert final_run["tool_calls"] == 1  # el denegado no cuenta: nunca se ejecutó

    assert [e["type"] for e in events] == [
        "run.started", "step.started", "tool.called", "tool.result",
        "state.updated", "policy.evaluated", "run.finished",
    ]
    assert events[-1]["payload"]["termination_reason"] == "success"

    assert len(tool_calls) == 2
    assert tool_calls[0]["status"] == "ok"
    assert tool_calls[1]["status"] == "denied"
    assert tool_calls[1]["policy_decision"] == "DENY"

    final_state = get_state(run_id)
    assert final_state["state"] == {"fase": "registrar", "senales_validas": 1}
    assert final_state["version"] == 2
