"""Entrypoint del proceso WORKER.

En H0 el worker no ejecuta runs todavía (eso llega en H5/H7): su único
trabajo es demostrar que API y WORKER son procesos separados desde el
primer día (§19.2 de docs/ARCHITECTURE.md), y anunciar que está vivo
mediante un heartbeat en control.db que /health puede leer.
"""

import time
from datetime import datetime, timezone

from aap.config import control_db_path
from aap.core.db import write_heartbeat

HEARTBEAT_INTERVAL_S = 10


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_forever() -> None:
    print("[worker] arrancando — heartbeat cada", HEARTBEAT_INTERVAL_S, "s")
    while True:
        write_heartbeat(control_db_path(), "worker", now_iso())
        time.sleep(HEARTBEAT_INTERVAL_S)


if __name__ == "__main__":
    run_forever()
