"""Run State (§9.2): explícito y tipado, no un cajón desastre. El agente
solo puede escribir en las claves que declara `state_schema` de su
Definición — eso se valida en el runtime (H5), no aquí; esto es solo la
persistencia con control optimista que hace posible reanudar un run sin
pisar una escritura perdida.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from aap.config import runtime_db_path
from aap.core.db import cursor


class StateConflictError(RuntimeError):
    """La versión esperada no coincide con la versión actual persistida."""


class StateNotFoundError(KeyError):
    pass


def init_run_state_table(path: Path | None = None) -> None:
    path = path or runtime_db_path()
    with cursor(path) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS run_state (
                run_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                version INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_state(run_id: str, initial: dict) -> int:
    init_run_state_table()
    with cursor(runtime_db_path()) as cur:
        cur.execute(
            "INSERT INTO run_state(run_id, state_json, version, updated_at) VALUES (?, ?, 1, ?)",
            (run_id, json.dumps(initial, ensure_ascii=False), _now()),
        )
    return 1


def get_state(run_id: str) -> dict:
    init_run_state_table()
    with cursor(runtime_db_path()) as cur:
        row = cur.execute("SELECT * FROM run_state WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise StateNotFoundError(run_id)
        return {"run_id": run_id, "state": json.loads(row["state_json"]), "version": row["version"]}


def update_state(run_id: str, new_state: dict, expected_version: int) -> int:
    init_run_state_table()
    with cursor(runtime_db_path()) as cur:
        cur.execute("BEGIN IMMEDIATE")
        try:
            row = cur.execute(
                "SELECT version FROM run_state WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise StateNotFoundError(run_id)
            if row["version"] != expected_version:
                raise StateConflictError(
                    f"{run_id}: versión esperada v{expected_version}, actual v{row['version']}"
                )
            next_version = expected_version + 1
            cur.execute(
                "UPDATE run_state SET state_json = ?, version = ?, updated_at = ? WHERE run_id = ?",
                (json.dumps(new_state, ensure_ascii=False), next_version, _now(), run_id),
            )
        except Exception:
            cur.execute("ROLLBACK")
            raise
        cur.execute("COMMIT")
    return next_version


def compute_diff(old: dict, new: dict) -> dict:
    """Diff a nivel de clave, suficiente para el evento `state.updated`."""
    added = {k: v for k, v in new.items() if k not in old}
    removed = [k for k in old if k not in new]
    changed = {k: {"from": old[k], "to": new[k]} for k in new if k in old and old[k] != new[k]}
    return {"added": added, "changed": changed, "removed": removed}
