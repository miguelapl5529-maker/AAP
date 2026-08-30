"""Evaluación (§22.2, §12): métricas mecánicas y comparación entre
versiones. Ambos endpoints son de solo lectura sobre runs ya
ejecutados — nunca disparan una ejecución nueva, así que no chocan con
la regla de que la API no ejecuta nada en el hilo de la petición
(§6.12, §19.2). Correr el eval set sí ejecuta runs (aunque scripteados
e instantáneos): por eso vive en el CLI (`aap evaluate`), no aquí.
"""

from fastapi import APIRouter

from aap.core.definition import repository as repo
from aap.core.evaluation.compare import compare_versions_by_metrics
from aap.core.evaluation.metrics import metrics_for_version
from aap.core.evaluation.store import list_evaluations

router = APIRouter()


@router.get("/agents/{agent_id}/metrics")
def agent_metrics(agent_id: str, version: int | None = None) -> dict:
    target = repo.get_version(agent_id, version) if version is not None else repo.get_active_version(agent_id)
    return {
        "agent_id": agent_id,
        "version": target["version"],
        "agent_version_id": target["id"],
        "metrics": metrics_for_version(target["id"]),
        "evaluations": list_evaluations(target["id"]),
    }


@router.get("/agents/{agent_id}/compare")
def compare(agent_id: str, a: int, b: int) -> dict:
    return compare_versions_by_metrics(agent_id, a, b)
