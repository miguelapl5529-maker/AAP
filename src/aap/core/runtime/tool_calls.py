"""Log desnormalizado de tool calls (§21.2): se consulta muchísimo más de
lo que se escribe, así que vive en su propia tabla en vez de
reconstruirse a partir de `events` cada vez que el Run Inspector la pida.

Redacta con `ToolSpec.redact` ANTES de tocar disco (§11.5) — lo que se
guarda aquí es justo lo que un Run Inspector puede mostrar sin miedo.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from aap.config import runtime_db_path
from aap.core.db import cursor
from aap.core.tools.broker import ToolResult
from aap.core.tools.redact import redact


def init_tool_calls_table(path: Path | None = None) -> None:
    path = path or runtime_db_path()
    with cursor(path) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tool_calls (
                id TEXT PRIMARY KEY, run_id TEXT NOT NULL, step INTEGER,
                tool_id TEXT NOT NULL, args_json TEXT, result_json TEXT,
                status TEXT, policy_decision TEXT, error TEXT,
                latency_ms INTEGER, started_at TEXT
            )
            """
        )


def record_tool_call(
    run_id: str,
    step: int,
    tool_id: str,
    arguments: dict,
    result: ToolResult,
    redact_paths: list[str] | None = None,
) -> dict:
    init_tool_calls_table()
    safe_args = redact(arguments, redact_paths or [])
    safe_result = redact(result.result or {}, redact_paths or [])
    call_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with cursor(runtime_db_path()) as cur:
        cur.execute(
            """INSERT INTO tool_calls(
                   id, run_id, step, tool_id, args_json, result_json,
                   status, policy_decision, error, latency_ms, started_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                call_id, run_id, step, tool_id,
                json.dumps(safe_args, ensure_ascii=False),
                json.dumps(safe_result, ensure_ascii=False),
                result.status, result.policy_decision, result.error,
                result.latency_ms, now,
            ),
        )
    return {
        "id": call_id, "run_id": run_id, "step": step, "tool_id": tool_id,
        "args": safe_args, "result": safe_result, "status": result.status,
        "policy_decision": result.policy_decision, "error": result.error,
        "latency_ms": result.latency_ms, "started_at": now,
    }


def list_tool_calls(run_id: str) -> list[dict]:
    init_tool_calls_table()
    with cursor(runtime_db_path()) as cur:
        rows = cur.execute(
            "SELECT * FROM tool_calls WHERE run_id = ? ORDER BY started_at", (run_id,)
        ).fetchall()
        return [_row_to_call(r) for r in rows]


def _row_to_call(row) -> dict:
    d = dict(row)
    d["args"] = json.loads(d.pop("args_json") or "{}")
    d["result"] = json.loads(d.pop("result_json") or "{}")
    return d
