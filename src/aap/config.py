"""Configuración del entorno. NUNCA una Agent Definition: eso vive en core/definition.

Deliberadamente perezoso (funciones, no constantes de módulo): así
`AAP_DATA_DIR` se puede cambiar entre tests o entre llamadas sin recargar
el intérprete.
"""

import os
from pathlib import Path

WORKER_HEARTBEAT_STALE_S = 30


def data_dir() -> Path:
    raw = os.environ.get("AAP_DATA_DIR", "data")
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def control_db_path() -> Path:
    return data_dir() / "control.db"


def runtime_db_path() -> Path:
    return data_dir() / "runtime.db"


def domain_db_path() -> Path:
    return data_dir() / "domain.db"
