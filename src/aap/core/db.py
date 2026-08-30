"""Infraestructura SQLite compartida por las tres bases (control/runtime/domain).

Genérico a propósito: no sabe qué tablas existen. Eso lo declara cada módulo
que posee su base (ver §21 de docs/ARCHITECTURE.md). Un único proceso
escritor por fichero, modo WAL, sin excepciones.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def cursor(path: Path):
    conn = connect(path)
    try:
        cur = conn.cursor()
        yield cur
    finally:
        conn.close()


def ensure_heartbeat_table(path: Path) -> None:
    with cursor(path) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS system_heartbeat (
                component TEXT PRIMARY KEY,
                ts TEXT NOT NULL
            )
            """
        )


def write_heartbeat(path: Path, component: str, ts_iso: str) -> None:
    ensure_heartbeat_table(path)
    with cursor(path) as cur:
        cur.execute(
            """
            INSERT INTO system_heartbeat(component, ts) VALUES (?, ?)
            ON CONFLICT(component) DO UPDATE SET ts=excluded.ts
            """,
            (component, ts_iso),
        )


def read_heartbeat(path: Path, component: str) -> str | None:
    if not path.exists():
        return None
    ensure_heartbeat_table(path)
    with cursor(path) as cur:
        row = cur.execute(
            "SELECT ts FROM system_heartbeat WHERE component = ?", (component,)
        ).fetchone()
        return row["ts"] if row else None
