from fastapi.testclient import TestClient

from aap.api.main import app
from aap.config import control_db_path
from aap.core.db import write_heartbeat


def test_health_reports_api_up_and_worker_down_without_heartbeat():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["api"] is True
    assert body["worker"] is False
    assert body["db"] is True


def test_health_reports_worker_up_after_fresh_heartbeat():
    from datetime import datetime, timezone

    write_heartbeat(control_db_path(), "worker", datetime.now(timezone.utc).isoformat())

    client = TestClient(app)
    body = client.get("/health").json()
    assert body["worker"] is True
