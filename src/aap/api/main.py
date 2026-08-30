"""Entrypoint del proceso API (control plane + backend de UI, §22.1).

No ejecuta runs en el hilo de la petición HTTP (§6.12, §19.2): eso es
responsabilidad exclusiva del WORKER. Esta app solo lee y escribe las
tres SQLite a través de los mismos módulos que usa el CLI (P6: UI y API
son clientes iguales del mismo control plane).
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from aap.api.routers import agents, health, runs
from aap.core.definition.repository import (
    AgentNotFoundError,
    DuplicateAgentError,
    VersionNotFoundError,
)
from aap.core.definition.validate import DefinitionValidationError
from aap.core.runtime.runs import RunNotFoundError
from aap.core.runtime.state import StateNotFoundError

app = FastAPI(title="AAP — Autonomous Agent Platform", version="0.1.0")
app.include_router(health.router)
app.include_router(agents.router)
app.include_router(runs.router)


def _not_found(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


app.add_exception_handler(AgentNotFoundError, _not_found)
app.add_exception_handler(VersionNotFoundError, _not_found)
app.add_exception_handler(RunNotFoundError, _not_found)
app.add_exception_handler(StateNotFoundError, _not_found)


@app.exception_handler(DuplicateAgentError)
def _duplicate(_: Request, exc: DuplicateAgentError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": f"el agente ya existe: {exc}"})


@app.exception_handler(DefinitionValidationError)
def _invalid_definition(_: Request, exc: DefinitionValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc), "errors": exc.errors})
