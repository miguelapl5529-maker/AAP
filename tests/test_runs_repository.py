import pytest

from aap.core.runtime.runs import (
    RunNotFoundError,
    claim_next_queued_run,
    create_run,
    finish_run,
    get_run,
    list_runs,
    record_llm_usage,
    record_step,
    record_tool_call_metric,
)


def test_create_run_defaults():
    run = create_run("demand-hunter", "version-1", trigger="manual", input_data={"sector": "logistica"})
    assert run["status"] == "queued"
    assert run["steps"] == 0
    assert run["tool_calls"] == 0
    assert run["input"] == {"sector": "logistica"}
    assert run["finished_at"] is None


def test_get_unknown_run_raises():
    with pytest.raises(RunNotFoundError):
        get_run("no-existe")


def test_list_runs_filters_by_agent():
    r1 = create_run("agent-a", "v1")
    create_run("agent-b", "v1")
    r2 = create_run("agent-a", "v1")

    runs_a = list_runs("agent-a")
    assert {r["id"] for r in runs_a} == {r1["id"], r2["id"]}
    assert all(r["agent_id"] == "agent-a" for r in runs_a)

    assert len(list_runs()) == 3


def test_metrics_accumulate():
    run = create_run("demand-hunter", "v1")
    record_step(run["id"])
    record_step(run["id"])
    record_tool_call_metric(run["id"])
    record_llm_usage(run["id"], prompt_tokens=100, completion_tokens=20, cost_usd=0.01)
    record_llm_usage(run["id"], prompt_tokens=50, completion_tokens=10, cost_usd=0.005)

    updated = get_run(run["id"])
    assert updated["steps"] == 2
    assert updated["tool_calls"] == 1
    assert updated["tokens_in"] == 150
    assert updated["tokens_out"] == 30
    assert updated["cost_usd"] == pytest.approx(0.015)


def test_finish_run_sets_terminal_fields():
    run = create_run("demand-hunter", "v1")
    finished = finish_run(
        run["id"], status="completed", termination_reason="success",
        output_data={"qualified": 3},
    )
    assert finished["status"] == "completed"
    assert finished["termination_reason"] == "success"
    assert finished["output"] == {"qualified": 3}
    assert finished["finished_at"] is not None
    assert finished["latency_ms"] >= 0


def test_finish_run_rejects_non_terminal_status():
    run = create_run("demand-hunter", "v1")
    with pytest.raises(ValueError):
        finish_run(run["id"], status="running")


def test_claim_next_queued_run_picks_oldest_and_marks_running():
    first = create_run("agent-a", "v1")
    create_run("agent-a", "v1")

    claimed = claim_next_queued_run()
    assert claimed["id"] == first["id"]
    assert claimed["status"] == "running"


def test_claim_next_queued_run_returns_none_when_nothing_queued():
    run = create_run("agent-a", "v1")
    claim_next_queued_run()  # se lleva el único run en cola
    assert claim_next_queued_run() is None
    assert get_run(run["id"])["status"] == "running"


def test_claim_next_queued_run_does_not_reclaim_an_already_running_run():
    run = create_run("agent-a", "v1")
    finish_run(run["id"], status="completed", termination_reason="ok")
    assert claim_next_queued_run() is None
