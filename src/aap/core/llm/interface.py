"""El contrato único de inferencia (§17.1). Todo provider lo implementa;
nadie fuera de core/llm sabe qué modelo físico responde.

`budget_ctx` está declarado tal como lo exige el contrato de la
arquitectura pero todavía no se usa: el BudgetManager real llega en H3
(Policy Engine). Traerlo aquí ya evita tener que romper esta forma más
adelante.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

Capability = Literal["cheap", "standard", "heavy", "coding", "embedding"]
Role = Literal["system", "user", "assistant", "tool"]


class Message(BaseModel):
    role: Role
    content: str
    name: str | None = None
    tool_call_id: str | None = None


class ToolSpec(BaseModel):
    """Forma mínima que el LLM necesita ver de una tool. El registro real
    de tools (con permisos, timeouts, etc.) llega en H3 y construye esto
    a partir de su propio ToolSpec — no al revés."""

    id: str
    description: str
    parameters: dict = Field(default_factory=dict)


class ToolCall(BaseModel):
    id: str
    tool_id: str
    arguments: dict = Field(default_factory=dict)


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int


class CompletionRequest(BaseModel):
    messages: list[Message]
    tools: list[ToolSpec] | None = None
    response_schema: dict | None = None
    capability: Capability
    max_tokens: int = 1024
    temperature: float = 0.2
    timeout_s: float = 30.0
    stop: list[str] | None = None
    budget_ctx: Any | None = None


class CompletionResult(BaseModel):
    text: str | None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage
    model_used: str
    finish_reason: Literal["stop", "tool_calls", "length", "error"]


class LLMProvider:
    """Interfaz que implementa cada provider concreto."""

    def complete(self, req: CompletionRequest) -> CompletionResult:
        raise NotImplementedError
