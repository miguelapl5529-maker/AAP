from aap.config import runtime_db_path
from aap.core.db import cursor
from aap.core.evaluation.metrics import compute_metrics, metrics_for_version
from aap.core.runtime.runs import create_run, finish_run, get_run
from aap.core.runtime.tool_calls import list_tool_calls, record_tool_call
from aap.core.tools.broker import ToolResult


def _run(status, cost=0.01, latency_ms=100, steps=2, tool_calls=1):
    r = create_run("agent-a", "v1")
    finish_run(r["id"], status=status, termination_reason=status, output_data={})
    # finish_run no toca steps/tool_calls/cost: los seteamos a mano para el test
    with cursor(runtime_db_path()) as cur:
        cur.execute(
            "UPDATE runs SET cost_usd=?, latency_ms=?, steps=?, tool_calls=? WHERE id=?",
            (cost, latency_ms, steps, tool_calls, r["id"]),
        )
    return get_run(r["id"])


def test_compute_metrics_on_empty_runs():
    metrics = compute_metrics([], [])
    assert metrics["total_runs"] == 0
    assert metrics["completion_rate"] is None


def test_compute_metrics_rates_and_averages():
    runs = [
        _run("completed", cost=0.01, latency_ms=100),
        _run("completed", cost=0.03, latency_ms=200),
        _run("failed", cost=0.02, latency_ms=50),
        _run("exhausted", cost=0.0, latency_ms=10),
    ]
    metrics = compute_metrics(runs, [])
    assert metrics["total_runs"] == 4
    assert metrics["completion_rate"] == 0.5
    assert metrics["failure_rate"] == 0.25
    assert metrics["exhausted_rate"] == 0.25
    assert metrics["cost_usd"]["total"] == 0.06
    assert metrics["cost_per_completed_run"] == (0.01 + 0.03) / 2


def test_tool_error_and_denial_rates():
    ok = ToolResult(tool_id="x", status="ok", result={}, policy_decision="ALLOW", latency_ms=1)
    err = ToolResult(tool_id="x", status="error", error="boom", policy_decision="ALLOW", latency_ms=1)
    denied = ToolResult(tool_id="x", status="denied", error="no", policy_decision="DENY", latency_ms=0)

    run = _run("completed")
    record_tool_call(run["id"], 1, "x", {}, ok)
    record_tool_call(run["id"], 1, "x", {}, err)
    record_tool_call(run["id"], 1, "x", {}, denied)

    metrics = compute_metrics([run], list_tool_calls(run["id"]))
    assert metrics["tool_error_rate"] == 1 / 3
    assert metrics["policy_denial_rate"] == 1 / 3


def test_metrics_for_version_filters_by_exact_version(demand_hunter_definition):
    from aap.core.definition import repository as repo

    repo.create_agent("demand-hunter", "Demand Hunter")
    v1 = repo.create_version("demand-hunter", demand_hunter_definition)
    edited = dict(demand_hunter_definition)
    edited["policies"]["budget"]["max_steps"] = 40
    v2 = repo.create_version("demand-hunter", edited)

    r1 = create_run("demand-hunter", v1["id"])
    finish_run(r1["id"], status="completed", termination_reason="completed")
    r2 = create_run("demand-hunter", v2["id"])
    finish_run(r2["id"], status="failed", termination_reason="failed")

    m1 = metrics_for_version(v1["id"])
    m2 = metrics_for_version(v2["id"])
    assert m1["total_runs"] == 1 and m1["completion_rate"] == 1.0
    assert m2["total_runs"] == 1 and m2["failure_rate"] == 1.0
