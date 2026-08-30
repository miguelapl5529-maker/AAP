"""Criterio de aceptación de H7: la API encola, el worker ejecuta en un
proceso separado (aquí, una llamada directa a su función de trabajo —
no hay hilo de petición HTTP de por medio), y la API vuelve a servir el
resultado. Nada de esto pasa por el hilo de la petición HTTP (§6.12,
§19.2, §22.3)."""

from aap.core.llm.providers.mock import MockProvider
from aap.worker.main import process_one_queued_run
from tests.conftest import make_scripted_router


def test_full_async_pipeline_via_api_and_worker(api_client, l0_agent_definition):
    # 1. La API registra el agente y lo versiona.
    api_client.post("/agents", json={"id": "l0-demo", "name": "L0 Demo"})
    resp = api_client.post("/agents/l0-demo/versions", json={"definition": l0_agent_definition})
    assert resp.status_code == 201

    # 2. La API encola un run — 202 inmediato, nada se ejecutó todavía.
    resp = api_client.post("/agents/l0-demo/runs", json={"input": {"sector": "logistica"}})
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]
    assert api_client.get(f"/runs/{run_id}").json()["status"] == "queued"

    # 3. El worker —proceso separado en producción— reclama y ejecuta.
    router = make_scripted_router(MockProvider())
    assert process_one_queued_run(router) is True

    # 4. La API vuelve a servir el resultado, la traza y el estado final.
    run = api_client.get(f"/runs/{run_id}").json()
    assert run["status"] == "completed"
    assert run["termination_reason"] == "completed"  # el criterio de éxito se cumplió

    events = api_client.get(f"/runs/{run_id}/events").json()
    assert events[0]["type"] == "run.started"
    assert events[-1]["type"] == "run.finished"

    tool_calls = api_client.get(f"/runs/{run_id}/tool_calls").json()
    assert len(tool_calls) == 3
    assert {tc["tool_id"] for tc in tool_calls} == {"search.web.mock", "db.upsert.mock", "state.update"}

    state = api_client.get(f"/runs/{run_id}/state").json()
    assert state["state"]["senales_validas"] == 1
