from datetime import datetime, timezone

from fastapi import APIRouter

from aap.config import WORKER_HEARTBEAT_STALE_S, control_db_path
from aap.core.db import read_heartbeat

router = APIRouter()


def _worker_alive() -> bool:
    ts = read_heartbeat(control_db_path(), "worker")
    if ts is None:
        return False
    age_s = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
    return age_s < WORKER_HEARTBEAT_STALE_S


def _db_reachable() -> bool:
    try:
        control_db_path().parent.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "api": True,
        "worker": _worker_alive(),
        "db": _db_reachable(),
        "providers": {},
    }
