"""Persistencia de evaluaciones (§21.2: tabla `evaluations` en
runtime.db). Nunca se sobreescribe — cada evaluación es un registro
nuevo, historial de cómo fue mejorando (o no) una versión.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from aap.config import runtime_db_path
from aap.core.db import cursor


def init_evaluations_table(path: Path | None = None) -> None:
    path = path or runtime_db_path()
    with cursor(path) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluations (
                id TEXT PRIMARY KEY,
                agent_version_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                eval_set TEXT,
                run_id TEXT,
                metrics_json TEXT NOT NULL,
                score REAL,
                created_at TEXT NOT NULL
            )
            """
        )


def record_evaluation(
    agent_version_id: str,
    kind: str,
    metrics: dict,
    eval_set: str | None = None,
    run_id: str | None = None,
    score: float | None = None,
) -> dict:
    init_evaluations_table()
    eval_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with cursor(runtime_db_path()) as cur:
        cur.execute(
            """INSERT INTO evaluations(
                   id, agent_version_id, kind, eval_set, run_id, metrics_json, score, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (eval_id, agent_version_id, kind, eval_set, run_id,
             json.dumps(metrics, ensure_ascii=False), score, now),
        )
    return {
        "id": eval_id, "agent_version_id": agent_version_id, "kind": kind,
        "eval_set": eval_set, "run_id": run_id, "metrics": metrics,
        "score": score, "created_at": now,
    }


def list_evaluations(agent_version_id: str) -> list[dict]:
    init_evaluations_table()
    with cursor(runtime_db_path()) as cur:
        # rowid como desempate: en Windows dos INSERT consecutivos pueden
        # caer en el mismo microsegundo y created_at por sí solo deja el
        # orden sin definir.
        rows = cur.execute(
            "SELECT * FROM evaluations WHERE agent_version_id = ? ORDER BY created_at DESC, rowid DESC",
            (agent_version_id,),
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["metrics"] = json.loads(d.pop("metrics_json"))
        result.append(d)
    return result
