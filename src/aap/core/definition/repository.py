"""Registro autoritativo para EJECUTAR (§16.4): tablas `agents` y
`agent_versions` en control.db. Git (export.py) es el registro autoritativo
para REVISAR; este módulo no sabe nada de Git.

Las versiones son inmutables: una vez insertada una fila en
`agent_versions`, `definition_json` y `content_hash` no vuelven a
escribirse jamás. "Editar" siempre crea una fila nueva.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from aap.config import control_db_path
from aap.core.db import cursor
from aap.core.definition.canonical import canonical_json, content_hash
from aap.core.definition.validate import validate_definition


class DuplicateAgentError(ValueError):
    pass


class AgentNotFoundError(ValueError):
    pass


class VersionNotFoundError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_control_db(path: Path | None = None) -> None:
    path = path or control_db_path()
    with cursor(path) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner TEXT,
                active_version_id TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_versions (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL REFERENCES agents(id),
                version INTEGER NOT NULL,
                definition_json TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_by TEXT,
                created_at TEXT NOT NULL,
                notes TEXT,
                UNIQUE(agent_id, version)
            )
            """
        )


def _row_to_agent(row) -> dict:
    return dict(row)


def _row_to_version(row) -> dict:
    d = dict(row)
    d["definition"] = json.loads(d.pop("definition_json"))
    return d


def create_agent(agent_id: str, name: str, owner: str | None = None) -> dict:
    init_control_db()
    with cursor(control_db_path()) as cur:
        existing = cur.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if existing:
            raise DuplicateAgentError(agent_id)
        now = _now()
        cur.execute(
            """INSERT INTO agents(id, name, owner, active_version_id, status, created_at, updated_at)
               VALUES (?, ?, ?, NULL, 'active', ?, ?)""",
            (agent_id, name, owner, now, now),
        )
    return get_agent(agent_id)


def get_agent(agent_id: str) -> dict:
    init_control_db()
    with cursor(control_db_path()) as cur:
        row = cur.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if row is None:
            raise AgentNotFoundError(agent_id)
        return _row_to_agent(row)


def list_agents() -> list[dict]:
    init_control_db()
    with cursor(control_db_path()) as cur:
        rows = cur.execute("SELECT * FROM agents ORDER BY created_at").fetchall()
        return [_row_to_agent(r) for r in rows]


def create_version(
    agent_id: str,
    definition: dict,
    created_by: str | None = None,
    notes: str | None = None,
    activate: bool = True,
) -> dict:
    """Valida, hashea e inserta una versión inmutable nueva.

    `activate=True` (por defecto en H1: aún no hay Factory ni drafts en la
    UI) la promociona de inmediato: archiva la versión activa anterior y
    actualiza `agents.active_version_id`. §16.4 exige que exista siempre
    exactamente una versión activa por agente.
    """
    get_agent(agent_id)  # lanza AgentNotFoundError si no existe
    validated = validate_definition(definition)
    canonical = validated.model_dump(mode="json")
    digest = content_hash(canonical)

    with cursor(control_db_path()) as cur:
        row = cur.execute(
            "SELECT COALESCE(MAX(version), 0) AS m FROM agent_versions WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        next_version = row["m"] + 1
        version_id = str(uuid.uuid4())
        status = "active" if activate else "draft"
        now = _now()
        cur.execute(
            """INSERT INTO agent_versions(
                   id, agent_id, version, definition_json, content_hash,
                   schema_version, status, created_by, created_at, notes
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                version_id,
                agent_id,
                next_version,
                canonical_json(canonical),
                digest,
                validated.schema_version,
                status,
                created_by,
                now,
                notes,
            ),
        )
        if activate:
            cur.execute(
                "UPDATE agent_versions SET status = 'archived' "
                "WHERE agent_id = ? AND id <> ? AND status = 'active'",
                (agent_id, version_id),
            )
            cur.execute(
                "UPDATE agents SET active_version_id = ?, updated_at = ? WHERE id = ?",
                (version_id, now, agent_id),
            )

    return get_version(agent_id, next_version)


def get_version(agent_id: str, version: int) -> dict:
    init_control_db()
    with cursor(control_db_path()) as cur:
        row = cur.execute(
            "SELECT * FROM agent_versions WHERE agent_id = ? AND version = ?",
            (agent_id, version),
        ).fetchone()
        if row is None:
            raise VersionNotFoundError(f"{agent_id} v{version}")
        return _row_to_version(row)


def get_version_by_id(version_id: str) -> dict:
    """El worker (H7) solo conoce el UUID que `runs.agent_version_id`
    guarda, no el número de versión — esta es la vía de resolución."""
    init_control_db()
    with cursor(control_db_path()) as cur:
        row = cur.execute("SELECT * FROM agent_versions WHERE id = ?", (version_id,)).fetchone()
        if row is None:
            raise VersionNotFoundError(version_id)
        return _row_to_version(row)


def list_versions(agent_id: str) -> list[dict]:
    init_control_db()
    with cursor(control_db_path()) as cur:
        rows = cur.execute(
            "SELECT * FROM agent_versions WHERE agent_id = ? ORDER BY version",
            (agent_id,),
        ).fetchall()
        return [_row_to_version(r) for r in rows]


def get_active_version(agent_id: str) -> dict:
    agent = get_agent(agent_id)
    if agent["active_version_id"] is None:
        raise VersionNotFoundError(f"{agent_id} no tiene versión activa")
    with cursor(control_db_path()) as cur:
        row = cur.execute(
            "SELECT * FROM agent_versions WHERE id = ?", (agent["active_version_id"],)
        ).fetchone()
        return _row_to_version(row)
