import json

import httpx
import pytest

from aap.core.llm.errors import ProviderTimeoutError, ProviderUnavailableError
from aap.core.llm.interface import CompletionRequest, Message
from aap.core.llm.providers.openai_compatible import OpenAICompatibleProvider


def _provider(handler) -> OpenAICompatibleProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="http://fake-llm.test", transport=transport)
    return OpenAICompatibleProvider(
        base_url="http://fake-llm.test",
        model="test-model",
        cost_per_1k_in=1.0,
        cost_per_1k_out=2.0,
        client=client,
    )


def test_missing_base_url_or_model_is_unavailable():
    with pytest.raises(ProviderUnavailableError):
        OpenAICompatibleProvider(base_url="", model="x")
    with pytest.raises(ProviderUnavailableError):
        OpenAICompatibleProvider(base_url="http://x", model="")


def test_successful_completion_computes_cost_and_usage():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [{"message": {"content": "hola"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    provider = _provider(handler)
    result = provider.complete(
        CompletionRequest(messages=[Message(role="user", content="hola")], capability="standard")
    )
    assert result.text == "hola"
    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 5
    assert result.usage.cost_usd == pytest.approx(10 / 1000 * 1.0 + 5 / 1000 * 2.0)
    assert result.finish_reason == "stop"


def test_tool_calls_are_parsed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "function": {
                                        "name": "search.web.mock",
                                        "arguments": json.dumps({"query": "logística"}),
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    provider = _provider(handler)
    result = provider.complete(
        CompletionRequest(messages=[Message(role="user", content="busca")], capability="standard")
    )
    assert result.finish_reason == "tool_calls"
    assert result.tool_calls[0].tool_id == "search.web.mock"
    assert result.tool_calls[0].arguments == {"query": "logística"}


def test_server_error_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    provider = _provider(handler)
    with pytest.raises(ProviderUnavailableError):
        provider.complete(
            CompletionRequest(messages=[Message(role="user", content="hola")], capability="standard")
        )


def test_network_timeout_raises_provider_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    provider = _provider(handler)
    with pytest.raises(ProviderTimeoutError):
        provider.complete(
            CompletionRequest(messages=[Message(role="user", content="hola")], capability="standard")
        )
