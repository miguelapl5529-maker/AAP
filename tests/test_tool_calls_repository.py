from aap.core.tools.broker import ToolResult
from aap.core.runtime.tool_calls import list_tool_calls, record_tool_call


def test_record_and_list_roundtrip():
    result = ToolResult(
        tool_id="search.web.mock", status="ok", result={"results": [{"name": "Rutas del Sur"}]},
        policy_decision="ALLOW", latency_ms=12,
    )
    record_tool_call("run-1", step=1, tool_id="search.web.mock", arguments={"query": "logistica"}, result=result)

    calls = list_tool_calls("run-1")
    assert len(calls) == 1
    assert calls[0]["tool_id"] == "search.web.mock"
    assert calls[0]["status"] == "ok"
    assert calls[0]["args"] == {"query": "logistica"}
    assert calls[0]["result"] == {"results": [{"name": "Rutas del Sur"}]}


def test_redact_paths_are_applied_to_args_and_result_before_persisting():
    result = ToolResult(
        tool_id="http.get.mock", status="ok",
        result={"headers": {"authorization": "Bearer secreto-real"}, "body": "ok"},
        policy_decision="ALLOW", latency_ms=5,
    )
    record_tool_call(
        "run-1", step=1, tool_id="http.get.mock",
        arguments={"headers": {"authorization": "Bearer secreto-real"}, "url": "https://x"},
        result=result,
        redact_paths=["headers.authorization"],
    )

    stored = list_tool_calls("run-1")[0]
    assert stored["args"]["headers"]["authorization"] == "***REDACTED***"
    assert stored["result"]["headers"]["authorization"] == "***REDACTED***"
    assert stored["args"]["url"] == "https://x"  # el resto no se toca


def test_denied_calls_have_no_result_but_still_get_logged():
    result = ToolResult(
        tool_id="db.upsert.mock", status="denied", error="database: tabla no permitida (signals)",
        policy_decision="DENY", latency_ms=0,
    )
    record_tool_call("run-1", step=2, tool_id="db.upsert.mock", arguments={"table": "signals"}, result=result)

    stored = list_tool_calls("run-1")[0]
    assert stored["status"] == "denied"
    assert stored["policy_decision"] == "DENY"
    assert stored["result"] == {}
