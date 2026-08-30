"""Provider `mock` — determinista y gratis (§0.5, §17.1: `kind: mock`).

Permite ejecutar el runtime de punta a punta sin gastar un céntimo de
inferencia. Dos modos:

- **Por defecto (echo)**: responde de forma determinista a partir del
  último mensaje de usuario. Sirve para probar el contrato sin más.
- **Scripted**: se le da una lista de `CompletionResult` (o fábricas de
  error) y los va devolviendo en orden. Es lo que el runtime (H5+) usará
  para conducir a un agente completo a través de un plan fijo sin
  depender de que un LLM real "decida" nada — el mundo mock necesita un
  cerebro igual de mock.
"""

from collections.abc import Callable

from aap.core.llm.errors import ProviderTimeoutError, ProviderUnavailableError
from aap.core.llm.interface import CompletionRequest, CompletionResult, LLMProvider, Usage
from aap.core.llm.tokens import estimate_tokens

ScriptStep = CompletionResult | Exception | Callable[[CompletionRequest], CompletionResult]


class ExhaustedScriptError(RuntimeError):
    """El test pidió más respuestas de las que el script del mock tenía preparadas."""


class MockProvider(LLMProvider):
    def __init__(self, script: list[ScriptStep] | None = None):
        self._script = list(script) if script is not None else None
        self._calls = 0

    @property
    def calls_made(self) -> int:
        return self._calls

    def complete(self, req: CompletionRequest) -> CompletionResult:
        self._calls += 1
        if self._script is not None:
            return self._next_scripted(req)
        return self._echo(req)

    def _next_scripted(self, req: CompletionRequest) -> CompletionResult:
        if not self._script:
            raise ExhaustedScriptError(f"sin más pasos scriptados (llamada #{self._calls})")
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        if isinstance(step, CompletionResult):
            return step
        return step(req)

    def _echo(self, req: CompletionRequest) -> CompletionResult:
        last_user = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
        text = f"echo:{last_user}"
        prompt_tokens = sum(estimate_tokens(m.content) for m in req.messages)
        completion_tokens = estimate_tokens(text)
        return CompletionResult(
            text=text,
            tool_calls=[],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=0.0,
                latency_ms=1,
            ),
            model_used="mock-echo",
            finish_reason="stop",
        )


def timeout_step() -> ProviderTimeoutError:
    return ProviderTimeoutError("mock: timeout simulado")


def error_step(message: str = "mock: error simulado") -> ProviderUnavailableError:
    return ProviderUnavailableError(message)
