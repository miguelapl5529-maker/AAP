import pytest

from aap.core.llm.interface import CompletionRequest, CompletionResult, Message, Usage
from aap.core.llm.providers.mock import (
    ExhaustedScriptError,
    MockProvider,
    error_step,
    timeout_step,
)


def _req(text: str = "hola") -> CompletionRequest:
    return CompletionRequest(messages=[Message(role="user", content=text)], capability="cheap")


def test_echo_is_deterministic():
    provider = MockProvider()
    a = provider.complete(_req("busca empresas de logística"))
    b = provider.complete(_req("busca empresas de logística"))
    assert a.text == b.text == "echo:busca empresas de logística"
    assert a.usage.cost_usd == 0.0
    assert a.finish_reason == "stop"


def test_echo_reflects_prompt_length_in_usage():
    short = MockProvider().complete(_req("hola"))
    long = MockProvider().complete(_req("hola " * 50))
    assert long.usage.prompt_tokens > short.usage.prompt_tokens


def test_scripted_responses_are_returned_in_order():
    scripted = CompletionResult(
        text="ok",
        usage=Usage(prompt_tokens=1, completion_tokens=1, cost_usd=0.0, latency_ms=1),
        model_used="mock-scripted",
        finish_reason="stop",
    )
    provider = MockProvider(script=[scripted])
    result = provider.complete(_req())
    assert result.model_used == "mock-scripted"
    assert provider.calls_made == 1


def test_scripted_timeout_and_error_are_raised():
    provider = MockProvider(script=[timeout_step(), error_step("boom")])
    with pytest.raises(Exception, match="timeout simulado"):
        provider.complete(_req())
    with pytest.raises(Exception, match="boom"):
        provider.complete(_req())


def test_exhausted_script_raises():
    provider = MockProvider(script=[])
    with pytest.raises(ExhaustedScriptError):
        provider.complete(_req())
