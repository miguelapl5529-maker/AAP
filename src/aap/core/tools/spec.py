"""Contrato de una Tool (§10.1). Genérico: no sabe qué tools existen,
solo la forma que cualquier tool —mock o real— debe tener.
"""

from typing import Literal

from pydantic import BaseModel, Field

SideEffects = Literal["read", "write", "destructive"]


class RetryPolicy(BaseModel):
    max: int = 0
    backoff: Literal["none", "exponential"] = "none"
    on: list[str] = Field(default_factory=list)


class CostHint(BaseModel):
    money: float = 0.0
    latency_ms: int = 0


class ToolSpec(BaseModel):
    id: str
    version: int = 1
    title: str
    description: str
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    permissions: list[str] = Field(default_factory=list)
    side_effects: SideEffects = "read"
    idempotent: bool = True
    timeout_s: float = 30.0
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    cost_hint: CostHint = Field(default_factory=CostHint)
    redact: list[str] = Field(default_factory=list)
    network_domain: str | None = None
    """Dominio fijo que esta tool contacta, si `network.http` está entre sus
    permisos. Lo declara quien escribe la tool, no quien la llama — así el
    Policy Engine puede evaluar el allowlist sin depender de que cada
    llamada incluya una URL en sus argumentos."""
