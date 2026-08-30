"""Long-term Memory (§9.1, §9.2): escritura explícita y curada, nunca
automática. Vive en `control.db`, no en `runtime.db` ni en `domain.db`
(§21.1) — sobrevive a los runs concretos igual que sobrevive a los
reinicios del proceso.

Sin embeddings todavía (§9.3): la recuperación es top-k por coincidencia
de texto simple sobre `content`, no búsqueda semántica.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from aap.config import control_db_path
from aap.core.db import cursor


def init_memories_table(path: Path | None = None) -> None:
    path = path or control_db_path()
    with cursor(path) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                type TEXT NOT NULL,
                subject TEXT,
                content TEXT NOT NULL,
                confidence REAL,
                source_run_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                use_count INTEGER DEFAULT 0,
                expires_at TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_memories_agent ON memories(agent_id)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_memory(
    agent_id: str,
    type: str,
    content: str,
    source_run_id: str,
    subject: str | None = None,
    confidence: float | None = None,
    expires_at: str | None = None,
) -> dict:
    """Procedencia obligatoria: sin `source_run_id` no se admite (§9.2)."""
    init_memories_table()
    memory_id = str(uuid.uuid4())
    now = _now()
    with cursor(control_db_path()) as cur:
        cur.execute(
            """INSERT INTO memories(
                   id, agent_id, type, subject, content, confidence,
                   source_run_id, created_at, use_count, expires_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
            (memory_id, agent_id, type, subject, content, confidence, source_run_id, now, expires_at),
        )
    return {"id": memory_id}


def search_memories(agent_id: str, query: str, k: int = 6) -> list[dict]:
    """Top-k con filtro de frescura implícito por orden de inserción; sin
    búsqueda semántica global (§9.3)."""
    init_memories_table()
    with cursor(control_db_path()) as cur:
        rows = cur.execute(
            "SELECT * FROM memories WHERE agent_id = ? ORDER BY created_at DESC", (agent_id,)
        ).fetchall()
    query_lower = query.lower()
    matches = [dict(r) for r in rows if query_lower in (r["content"] or "").lower()]
    return matches[:k]


def list_memories(agent_id: str) -> list[dict]:
    init_memories_table()
    with cursor(control_db_path()) as cur:
        rows = cur.execute(
            "SELECT * FROM memories WHERE agent_id = ? ORDER BY created_at", (agent_id,)
        ).fetchall()
    return [dict(r) for r in rows]
