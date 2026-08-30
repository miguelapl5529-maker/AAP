"""Event Log append-only (§9.4, P3): a la vez traza, log y auditoría. Una
sola tabla, tipada, consultable por `run_id`. Nadie "espera" a un evento
en V1 (§9.4): esto es puro registro, no un bus.

Quien llama a `emit()` es responsable de no incluir secretos en
`payload` — el log no sabe qué es un secreto (§11.5); esa decisión vive
en `ToolSpec.redact` y se aplica antes de llegar aquí.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from aap.config import runtime_db_path
from aap.core.db import cursor
from aap.core.events.types import EventLevel, EventType


def init_events_table(path: Path | None = None) -> None:
    path = path or runtime_db_path()
    with cursor(path) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                ts TEXT NOT NULL,
                type TEXT NOT NULL,
                level TEXT NOT NULL,
                step INTEGER,
                payload_json TEXT,
                UNIQUE(run_id, seq)
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id, seq)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(
    run_id: str,
    type: EventType,
    level: EventLevel = "INFO",
    step: int | None = None,
    payload: dict | None = None,
) -> dict:
    init_events_table()
    with cursor(runtime_db_path()) as cur:
        row = cur.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM events WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        seq = row["next_seq"]
        ts = _now()
        cur.execute(
            "INSERT INTO events(run_id, seq, ts, type, level, step, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, seq, ts, type, level, step, json.dumps(payload or {}, ensure_ascii=False)),
        )
    return {
        "run_id": run_id, "seq": seq, "ts": ts, "type": type,
        "level": level, "step": step, "payload": payload or {},
    }


def list_events(run_id: str) -> list[dict]:
    init_events_table()
    with cursor(runtime_db_path()) as cur:
        rows = cur.execute(
            "SELECT * FROM events WHERE run_id = ? ORDER BY seq", (run_id,)
        ).fetchall()
        return [_row_to_event(r) for r in rows]


def _row_to_event(row) -> dict:
    d = dict(row)
    d["payload"] = json.loads(d.pop("payload_json") or "{}")
    return d
