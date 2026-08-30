"""Control plane de agentes y versiones (§22.2, recortado para V1).

La API es un cliente más de `core/definition/repository.py` — no
reimplementa validación ni hash: los reutiliza (P6: UI y API iguales
ante el sistema, y aquí ni siquiera hay dos codebases que puedan divergir).
"""

from fastapi import APIRouter, Body

from aap.core.definition import repository as repo
from aap.core.definition.canonical import content_hash
from aap.core.definition.schema import get_schema
from aap.core.definition.validate import validate_definition
from aap.factory.clone import duplicate_agent
from aap.factory.diff import diff_versions

router = APIRouter()


@router.post("/definitions/validate")
def validate(body: dict = Body(...)) -> dict:
    """Valida sin guardar — la UI (H10) la usa en vivo, mientras el
    operador rellena el formulario (§22.2)."""
    validated = validate_definition(body)
    return {"valid": True, "content_hash": content_hash(validated.model_dump(mode="json"))}


@router.get("/agents")
def list_agents() -> list[dict]:
    return repo.list_agents()


@router.post("/agents", status_code=201)
def create_agent(body: dict = Body(...)) -> dict:
    return repo.create_agent(body["id"], body["name"], owner=body.get("owner"))


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str) -> dict:
    return repo.get_agent(agent_id)


@router.get("/agents/{agent_id}/versions")
def list_versions(agent_id: str) -> list[dict]:
    repo.get_agent(agent_id)  # 404 limpio si el agente no existe
    return repo.list_versions(agent_id)


@router.post("/agents/{agent_id}/versions", status_code=201)
def create_version(agent_id: str, body: dict = Body(...)) -> dict:
    definition = body.get("definition", body)
    return repo.create_version(
        agent_id, definition, created_by=body.get("created_by"), notes=body.get("notes"),
        activate=body.get("activate", True),
    )


@router.get("/agents/{agent_id}/versions/{version}")
def get_version(agent_id: str, version: int) -> dict:
    return repo.get_version(agent_id, version)


@router.post("/agents/{agent_id}/versions/{version}/promote")
def promote_version(agent_id: str, version: int) -> dict:
    return repo.promote_version(agent_id, version)


@router.post("/agents/{agent_id}/versions/{version}/archive")
def archive_version(agent_id: str, version: int) -> dict:
    return repo.archive_version(agent_id, version)


@router.get("/agents/{agent_id}/versions/{version_a}/diff/{version_b}")
def diff(agent_id: str, version_a: int, version_b: int) -> dict:
    return diff_versions(agent_id, version_a, version_b)


@router.post("/agents/{agent_id}/duplicate", status_code=201)
def duplicate(agent_id: str, body: dict = Body(...)) -> dict:
    return duplicate_agent(
        agent_id, body["new_id"], body["new_name"],
        overrides=body.get("overrides"), owner=body.get("owner"),
        activate=body.get("activate", False),
    )


@router.get("/schema/agent-definition")
def agent_definition_schema() -> dict:
    return get_schema()
