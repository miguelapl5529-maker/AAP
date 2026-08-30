"""Ejecución (§22.2, §22.3): los runs son asíncronos siempre. `POST
/agents/{id}/runs` devuelve 202 de inmediato — el servidor HTTP no
ejecuta el bucle del agente en el hilo de la petición (§6.12, §19.2).
El worker (proceso separado) es quien realmente los corre; esta API
solo encola y consulta.
"""

from fastapi import APIRouter, Body

from aap.core.definition import repository as repo
from aap.core.events.log import list_events
from aap.core.runtime.runs import create_run, get_run, list_runs
from aap.core.runtime.state import StateNotFoundError, get_state
from aap.core.runtime.tool_calls import list_tool_calls

router = APIRouter()


@router.post("/agents/{agent_id}/runs", status_code=202)
def trigger_run(agent_id: str, body: dict = Body(default={})) -> dict:
    version_number = body.get("version")
    version = (
        repo.get_version(agent_id, version_number)
        if version_number is not None
        else repo.get_active_version(agent_id)
    )
    run = create_run(
        agent_id, version["id"],
        trigger=body.get("trigger", "api"),
        input_data=body.get("input", {}),
    )
    return {"run_id": run["id"], "status": run["status"]}


@router.get("/runs")
def list_all_runs(agent_id: str | None = None, status: str | None = None) -> list[dict]:
    runs = list_runs(agent_id)
    if status:
        runs = [r for r in runs if r["status"] == status]
    return runs


@router.get("/runs/{run_id}")
def get_one_run(run_id: str) -> dict:
    return get_run(run_id)


@router.get("/runs/{run_id}/events")
def get_run_events(run_id: str) -> list[dict]:
    get_run(run_id)  # 404 limpio si el run no existe
    return list_events(run_id)


@router.get("/runs/{run_id}/tool_calls")
def get_run_tool_calls(run_id: str) -> list[dict]:
    get_run(run_id)
    return list_tool_calls(run_id)


@router.get("/runs/{run_id}/state")
def get_run_state(run_id: str) -> dict:
    get_run(run_id)
    try:
        return get_state(run_id)
    except StateNotFoundError:
        return {"run_id": run_id, "state": {}, "version": 0}
