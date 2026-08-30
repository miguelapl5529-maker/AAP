"""Entrypoint del proceso API (control plane + backend de UI, §22.1).

No ejecuta runs en el hilo de la petición HTTP (§6.12, §19.2): eso es
responsabilidad exclusiva del WORKER.
"""

from fastapi import FastAPI

from aap.api.routers import health

app = FastAPI(title="AAP — Autonomous Agent Platform", version="0.1.0")
app.include_router(health.router)
