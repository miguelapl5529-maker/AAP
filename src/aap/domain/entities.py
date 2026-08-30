"""Entity Store mínimo para V1 (§9.2, §21.2): "los datos de valor
económico no viven dentro del agente. Viven en un almacén de dominio que
sobrevive a todos los agentes, a todas sus versiones y a todos sus
fallos."

Simplificación deliberada respecto a §21.2: en vez de tablas rígidas
`companies`/`signals`/`opportunities` con columnas propias, V1 usa una
única tabla genérica `entities` (`table_name` + `natural_key` +
`values_json`). Es exactamente lo que necesita el Demand Hunter Demo
(H6) para que sus escrituras sobrevivan a un reinicio del proceso, sin
construir un modelo relacional que ningún agente real ha pedido
todavía (P8). El día que un segundo agente vertical necesite
relaciones reales (FKs, tipos fuertes por tabla), es el momento de
partir esto en tablas propias — no antes.

`domain/` no importa de `core/runtime` (regla 2, §20.2): el almacén de
dominio existe con independencia de los agentes que lo llenan. Solo usa
`core/db.py`, que es infraestructura SQLite genérica.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from aap.config import domain_db_path
from aap.core.db import cursor


def init_domain_db(path: Path | None = None) -> None:
    path = path or domain_db_path()
    with cursor(path) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                table_name TEXT NOT NULL,
                natural_key TEXT NOT NULL,
                values_json TEXT NOT NULL,
                source_run_id TEXT,
                agent_version_id TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(table_name, natural_key)
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_entities_table ON entities(table_name)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_entity(
    table_name: str,
    natural_key: str,
    values: dict,
    source_run_id: str | None = None,
    agent_version_id: str | None = None,
) -> dict:
    """Igual que `db.upsert.mock` siempre prometió: si la clave natural ya
    existe, `status=duplicate` en vez de una fila nueva (§10.2)."""
    init_domain_db()
    with cursor(domain_db_path()) as cur:
        existing = cur.execute(
            "SELECT id FROM entities WHERE table_name = ? AND natural_key = ?",
            (table_name, natural_key),
        ).fetchone()
        if existing:
            return {"status": "duplicate", "id": existing["id"]}
        entity_id = str(uuid.uuid4())
        cur.execute(
            """INSERT INTO entities(
                   id, table_name, natural_key, values_json,
                   source_run_id, agent_version_id, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                entity_id, table_name, natural_key,
                json.dumps(values, ensure_ascii=False),
                source_run_id, agent_version_id, _now(),
            ),
        )
    return {"status": "created", "id": entity_id}


def query_entities(table_name: str, filter: dict | None = None) -> list[dict]:
    init_domain_db()
    with cursor(domain_db_path()) as cur:
        rows = cur.execute(
            "SELECT * FROM entities WHERE table_name = ?", (table_name,)
        ).fetchall()
    results = [_row_to_entity(r) for r in rows]
    if filter:
        results = [r for r in results if all(r["values"].get(k) == v for k, v in filter.items())]
    return results


def get_entity(table_name: str, natural_key: str) -> dict | None:
    init_domain_db()
    with cursor(domain_db_path()) as cur:
        row = cur.execute(
            "SELECT * FROM entities WHERE table_name = ? AND natural_key = ?",
            (table_name, natural_key),
        ).fetchone()
    return _row_to_entity(row) if row else None


def list_table_names() -> list[str]:
    init_domain_db()
    with cursor(domain_db_path()) as cur:
        rows = cur.execute("SELECT DISTINCT table_name FROM entities").fetchall()
    return [r["table_name"] for r in rows]


def _row_to_entity(row) -> dict:
    d = dict(row)
    d["values"] = json.loads(d.pop("values_json"))
    return d
