"""Persistencia de la entidad Run (§21.2, §3.2, regla 2: un run apunta
siempre a una versión, nunca a un agente — sin eso la evaluación es
imposible)."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from aap.config import runtime_db_path
from aap.core.db import cursor

TERMINAL_STATUSES = {"completed", "failed", "exhausted", "cancelled", "crashed"}


class RunNotFoundError(KeyError):
    pass


def init_runs_table(path: Path | None = None) -> None:
    path = path or runtime_db_path()
    with cursor(path) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                agent_version_id TEXT NOT NULL,
                trigger TEXT,
                parent_run_id TEXT,
                status TEXT NOT NULL,
                input_json TEXT, output_json TEXT,
                started_at TEXT, finished_at TEXT,
                steps INTEGER DEFAULT 0, tool_calls INTEGER DEFAULT 0,
                tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0, latency_ms INTEGER,
                termination_reason TEXT, error TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_agent_time ON runs(agent_id, started_at DESC)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_run(
    agent_id: str,
    agent_version_id: str,
    trigger: str = "manual",
    input_data: dict | None = None,
    parent_run_id: str | None = None,
    status: str = "queued",
) -> dict:
    """`status="queued"` por defecto: los runs son asíncronos siempre
    (§22.3). `started_at` se refresca cuando el worker reclama el run
    (`claim_next_queued_run`), así que hasta entonces también hace de
    "en cola desde" para el orden FIFO."""
    init_runs_table()
    run_id = str(uuid.uuid4())
    now = _now()
    with cursor(runtime_db_path()) as cur:
        cur.execute(
            """INSERT INTO runs(
                   id, agent_id, agent_version_id, trigger, parent_run_id, status,
                   input_json, started_at, steps, tool_calls, tokens_in, tokens_out, cost_usd
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0)""",
            (
                run_id, agent_id, agent_version_id, trigger, parent_run_id, status,
                json.dumps(input_data or {}, ensure_ascii=False), now,
            ),
        )
    return get_run(run_id)


def claim_next_queued_run() -> dict | None:
    """El worker reclama UN run en cola de forma atómica: el `WHERE
    status='queued'` en el UPDATE hace que dos workers reclamando a la
    vez nunca se pisen (aunque V1 solo tenga uno, §21.1: un único
    proceso escritor por fichero)."""
    init_runs_table()
    now = _now()
    with cursor(runtime_db_path()) as cur:
        row = cur.execute(
            "SELECT id FROM runs WHERE status = 'queued' ORDER BY started_at ASC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        run_id = row["id"]
        cur.execute(
            "UPDATE runs SET status = 'running', started_at = ? WHERE id = ? AND status = 'queued'",
            (now, run_id),
        )
        if cur.rowcount == 0:
            return None
    return get_run(run_id)


def get_run(run_id: str) -> dict:
    init_runs_table()
    with cursor(runtime_db_path()) as cur:
        row = cur.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise RunNotFoundError(run_id)
        return _row_to_run(row)


def list_runs(agent_id: str | None = None) -> list[dict]:
    init_runs_table()
    with cursor(runtime_db_path()) as cur:
        if agent_id:
            rows = cur.execute(
                "SELECT * FROM runs WHERE agent_id = ? ORDER BY started_at DESC", (agent_id,)
            ).fetchall()
        else:
            rows = cur.execute("SELECT * FROM runs ORDER BY started_at DESC").fetchall()
        return [_row_to_run(r) for r in rows]


def list_runs_by_version(agent_version_id: str) -> list[dict]:
    """Para comparar v1 vs v2 (§12.4) hace falta filtrar por versión
    exacta, no solo por agente — `list_runs(agent_id)` mezcla todas."""
    init_runs_table()
    with cursor(runtime_db_path()) as cur:
        rows = cur.execute(
            "SELECT * FROM runs WHERE agent_version_id = ? ORDER BY started_at DESC",
            (agent_version_id,),
        ).fetchall()
        return [_row_to_run(r) for r in rows]


def record_step(run_id: str) -> None:
    with cursor(runtime_db_path()) as cur:
        cur.execute("UPDATE runs SET steps = steps + 1 WHERE id = ?", (run_id,))


def record_tool_call_metric(run_id: str) -> None:
    with cursor(runtime_db_path()) as cur:
        cur.execute("UPDATE runs SET tool_calls = tool_calls + 1 WHERE id = ?", (run_id,))


def record_llm_usage(run_id: str, prompt_tokens: int, completion_tokens: int, cost_usd: float) -> None:
    with cursor(runtime_db_path()) as cur:
        cur.execute(
            "UPDATE runs SET tokens_in = tokens_in + ?, tokens_out = tokens_out + ?, "
            "cost_usd = cost_usd + ? WHERE id = ?",
            (prompt_tokens, completion_tokens, cost_usd, run_id),
        )


def finish_run(
    run_id: str,
    status: str,
    termination_reason: str | None = None,
    output_data: dict | None = None,
    error: str | None = None,
) -> dict:
    if status not in TERMINAL_STATUSES:
        raise ValueError(f"status de terminación inválido: {status!r} (§8.4)")
    run = get_run(run_id)
    started = datetime.fromisoformat(run["started_at"])
    now = datetime.now(timezone.utc)
    latency_ms = int((now - started).total_seconds() * 1000)
    with cursor(runtime_db_path()) as cur:
        cur.execute(
            """UPDATE runs SET status = ?, finished_at = ?, termination_reason = ?,
               output_json = ?, error = ?, latency_ms = ? WHERE id = ?""",
            (
                status, now.isoformat(), termination_reason,
                json.dumps(output_data or {}, ensure_ascii=False), error, latency_ms, run_id,
            ),
        )
    return get_run(run_id)


def _row_to_run(row) -> dict:
    d = dict(row)
    d["input"] = json.loads(d.pop("input_json") or "{}")
    output_json = d.pop("output_json")
    d["output"] = json.loads(output_json) if output_json else {}
    return d
