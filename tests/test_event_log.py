from aap.core.events.log import emit, list_events


def test_seq_autoincrements_per_run():
    emit("run-a", "run.started", "AUDIT")
    emit("run-a", "step.started", "INFO", step=1)
    emit("run-a", "tool.called", "INFO", step=1, payload={"tool_id": "search.web.mock"})

    events = list_events("run-a")
    assert [e["seq"] for e in events] == [1, 2, 3]
    assert [e["type"] for e in events] == ["run.started", "step.started", "tool.called"]
    assert events[2]["payload"] == {"tool_id": "search.web.mock"}


def test_seq_is_independent_per_run():
    emit("run-a", "run.started")
    emit("run-b", "run.started")
    emit("run-a", "run.finished")

    assert [e["seq"] for e in list_events("run-a")] == [1, 2]
    assert [e["seq"] for e in list_events("run-b")] == [1]


def test_missing_payload_defaults_to_empty_dict():
    emit("run-a", "run.started", "AUDIT")
    assert list_events("run-a")[0]["payload"] == {}


def test_unknown_run_id_returns_empty_list():
    assert list_events("run-nonexistent") == []
