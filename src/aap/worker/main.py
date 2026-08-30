"""Entrypoint del proceso WORKER (§19.2, §6.12).

Dos responsabilidades: anunciar que está vivo (heartbeat, H0) y ser el
único proceso que realmente ejecuta runs — el servidor HTTP solo los
encola (§22.3). Sin colas distribuidas: una tabla `runs` con estado
`queued` y un poll cada pocos segundos resuelve lo mismo con muchas
menos piezas que Kafka/RabbitMQ (§24.2).
"""

import time
from datetime import datetime, timezone
from pathlib import Path

from aap.config import control_db_path
from aap.core.db import write_heartbeat
from aap.core.definition.repository import get_version_by_id
from aap.core.definition.validate import validate_definition
from aap.core.llm.router import ModelRouter
from aap.core.runtime.executor import execute_run
from aap.core.runtime.runs import claim_next_queued_run
from aap.tools.builtin.state import make_state_update_tool
from aap.tools.mock.tools import build_mock_registry
from aap.tools.mock.world import default_world

HEARTBEAT_INTERVAL_S = 10
POLL_INTERVAL_S = 2
MODELS_CONFIG_PATH = Path("config/models.yaml")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_registry(run_id: str, agent_id: str, agent_version_id: str, state_schema: dict):
    """V1 solo tiene el Mundo Mock — no hay integraciones reales todavía
    (§24.2, §24.1). Cuando exista una segunda familia de tools, este es
    el punto donde el worker decide cuál usar según la Definición, no el
    executor."""
    world = default_world()
    registry = build_mock_registry(
        world, run_id=run_id, agent_id=agent_id, agent_version_id=agent_version_id,
    )
    spec, fn = make_state_update_tool(run_id, state_schema)
    registry.register(spec, fn)
    return registry


def process_one_queued_run(router: ModelRouter) -> bool:
    """Reclama y ejecuta UN run en cola. Devuelve False si no había nada
    que hacer, para que quien orquesta el loop sepa si debe esperar."""
    run = claim_next_queued_run()
    if run is None:
        return False

    try:
        version = get_version_by_id(run["agent_version_id"])
        definition = validate_definition(version["definition"])
        registry = _build_registry(
            run["id"], run["agent_id"], run["agent_version_id"], definition.memory.state_schema,
        )
        execute_run(definition, router, registry, run["id"], run["input"])
    except Exception as exc:
        # execute_run ya marcó el run como crashed y volvió a lanzar la
        # excepción (§8.4): esto es solo para que UN run malo no tumbe
        # el proceso worker entero.
        print(f"[worker] run {run['id']} terminó con excepción no controlada: {exc}")
    return True


def run_forever() -> None:
    print(
        "[worker] arrancando — heartbeat cada", HEARTBEAT_INTERVAL_S,
        "s, poll cada", POLL_INTERVAL_S, "s",
    )
    router = ModelRouter.from_file(MODELS_CONFIG_PATH)
    last_heartbeat = 0.0
    while True:
        now = time.monotonic()
        if now - last_heartbeat >= HEARTBEAT_INTERVAL_S:
            write_heartbeat(control_db_path(), "worker", now_iso())
            last_heartbeat = now

        if not process_one_queued_run(router):
            time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    run_forever()
