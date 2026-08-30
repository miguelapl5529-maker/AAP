"""El único camino hacia una tool (§10, §11.1).

`authorize()` es lo primero que ocurre, siempre. El executor del runtime
(H5) no tendrá ninguna referencia a las funciones de las tools: solo al
broker, y el broker no expone ningún atajo para saltarse la política.
"""

import time
from typing import Literal

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as jsonschema_validate
from pydantic import BaseModel

from aap.core.policy.context import PolicyContext
from aap.core.policy.engine import PolicyEngine
from aap.core.tools.registry import ToolRegistry

ToolStatus = Literal["ok", "error", "timeout", "denied", "pending_approval"]


class ToolTimeoutError(Exception):
    """Una tool la lanza para simular o reportar un timeout real."""


class ToolExecutionError(Exception):
    """Una tool la lanza para reportar un fallo de ejecución."""


class ToolResult(BaseModel):
    tool_id: str
    status: ToolStatus
    result: dict | None = None
    error: str | None = None
    policy_decision: Literal["ALLOW", "DENY", "REQUIRE_APPROVAL"]
    latency_ms: int


class ToolBroker:
    def __init__(self, registry: ToolRegistry, policy_engine: PolicyEngine):
        self._registry = registry
        self._policy = policy_engine

    def invoke(self, ctx: PolicyContext, tool_id: str, arguments: dict) -> ToolResult:
        registered = self._registry.get(tool_id)  # ToolNotFoundError: deliberado, no se traga
        spec = registered.spec

        decision = self._policy.authorize(ctx, tool_id, arguments, spec)
        if decision.action == "DENY":
            return ToolResult(
                tool_id=tool_id, status="denied", error=decision.reason,
                policy_decision="DENY", latency_ms=0,
            )
        if decision.action == "REQUIRE_APPROVAL":
            return ToolResult(
                tool_id=tool_id, status="pending_approval", error=decision.reason,
                policy_decision="REQUIRE_APPROVAL", latency_ms=0,
            )

        try:
            jsonschema_validate(arguments, spec.input_schema)
        except JsonSchemaValidationError as exc:
            return ToolResult(
                tool_id=tool_id, status="error", error=f"input inválido: {exc.message}",
                policy_decision="ALLOW", latency_ms=0,
            )

        started = time.monotonic()
        try:
            raw_result = registered.fn(arguments)
        except ToolTimeoutError as exc:
            ctx.budget.consume_tool_call()
            return self._fail(tool_id, "timeout", str(exc), started)
        except ToolExecutionError as exc:
            ctx.budget.consume_tool_call()
            return self._fail(tool_id, "error", str(exc), started)

        latency_ms = self._elapsed_ms(started)
        try:
            jsonschema_validate(raw_result, spec.output_schema)
        except JsonSchemaValidationError as exc:
            ctx.budget.consume_tool_call()
            return ToolResult(
                tool_id=tool_id, status="error",
                error=f"la tool devolvió una forma inválida (bug de la tool, no del agente): {exc.message}",
                policy_decision="ALLOW", latency_ms=latency_ms,
            )

        ctx.budget.consume_tool_call()
        return ToolResult(
            tool_id=tool_id, status="ok", result=raw_result,
            policy_decision="ALLOW", latency_ms=latency_ms,
        )

    def _fail(self, tool_id: str, status: ToolStatus, error: str, started: float) -> ToolResult:
        return ToolResult(
            tool_id=tool_id, status=status, error=error,
            policy_decision="ALLOW", latency_ms=self._elapsed_ms(started),
        )

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.monotonic() - started) * 1000)
