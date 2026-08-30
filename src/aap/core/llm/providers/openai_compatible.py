"""Provider para cualquier endpoint compatible con la API de chat de OpenAI.

Sirve igual para una API externa de pago que para un futuro servidor vLLM
local (§18.3): ambos hablan el mismo protocolo. Cambiar de uno a otro es
editar `config/models.yaml`, no tocar código — ese es el valor real de
tener esta interfaz.
"""

import json
import time

import httpx

from aap.core.llm.errors import ProviderTimeoutError, ProviderUnavailableError
from aap.core.llm.interface import (
    CompletionRequest,
    CompletionResult,
    LLMProvider,
    ToolCall,
    Usage,
)


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        cost_per_1k_in: float = 0.0,
        cost_per_1k_out: float = 0.0,
        client: httpx.Client | None = None,
    ):
        if not base_url or not model:
            raise ProviderUnavailableError("openai_compatible: base_url/model no configurados")
        self._model = model
        self._cost_in = cost_per_1k_in
        self._cost_out = cost_per_1k_out
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx.Client(base_url=base_url, headers=headers)

    def complete(self, req: CompletionRequest) -> CompletionResult:
        payload = {
            "model": self._model,
            "messages": [m.model_dump(exclude_none=True) for m in req.messages],
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
        }
        if req.stop:
            payload["stop"] = req.stop
        if req.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.id,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in req.tools
            ]
        if req.response_schema:
            payload["response_format"] = {"type": "json_schema", "json_schema": req.response_schema}

        started = time.monotonic()
        try:
            resp = self._client.post(
                "/chat/completions", json=payload, timeout=req.timeout_s
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(str(exc)) from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        if resp.status_code >= 500:
            raise ProviderUnavailableError(f"openai_compatible: {resp.status_code} {resp.text}")
        if resp.status_code >= 400:
            raise ProviderUnavailableError(f"openai_compatible: {resp.status_code} {resp.text}")

        data = resp.json()
        choice = data["choices"][0]
        message = choice["message"]
        usage_raw = data.get("usage", {})
        prompt_tokens = usage_raw.get("prompt_tokens", 0)
        completion_tokens = usage_raw.get("completion_tokens", 0)
        cost = (prompt_tokens / 1000) * self._cost_in + (completion_tokens / 1000) * self._cost_out

        tool_calls = [
            ToolCall(
                id=tc["id"],
                tool_id=tc["function"]["name"],
                arguments=json.loads(tc["function"]["arguments"] or "{}"),
            )
            for tc in message.get("tool_calls", []) or []
        ]

        finish_reason = choice.get("finish_reason", "stop")
        normalized_finish = finish_reason if finish_reason in (
            "stop", "tool_calls", "length"
        ) else "stop"

        return CompletionResult(
            text=message.get("content"),
            tool_calls=tool_calls,
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost,
                latency_ms=latency_ms,
            ),
            model_used=data.get("model", self._model),
            finish_reason="tool_calls" if tool_calls else normalized_finish,
        )
