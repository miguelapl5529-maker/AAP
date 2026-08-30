import pytest

from aap.core.llm.errors import NoProviderAvailableError, ProviderUnavailableError
from aap.core.llm.interface import CompletionRequest, LLMProvider, Message
from aap.core.llm.providers.mock import MockProvider
from aap.core.llm.router import ModelRouter, load_config


def _req() -> CompletionRequest:
    return CompletionRequest(messages=[Message(role="user", content="hola")], capability="standard")


def test_router_degrades_to_mock_when_primary_unconfigured():
    config = {
        "providers": {
            "api_fast": {"kind": "openai_compatible", "base_url": "", "model": ""},
            "mock": {"kind": "mock"},
        },
        "routing": {"standard": ["api_fast", "mock"]},
        "policies": {"on_unavailable": "next_in_chain"},
    }
    router = ModelRouter(config)
    result = router.complete("standard", _req())
    assert result.model_used == "mock-echo"


class _AlwaysFails(LLMProvider):
    def complete(self, req):
        raise ProviderUnavailableError("siempre falla")


def test_router_raises_when_whole_chain_is_unavailable():
    config = {"providers": {}, "routing": {"standard": ["ghost"]}, "policies": {}}
    router = ModelRouter(config, providers={"ghost": _AlwaysFails()})
    with pytest.raises(NoProviderAvailableError):
        router.complete("standard", _req())


def test_router_raises_immediately_when_on_unavailable_is_fail():
    config = {
        "providers": {},
        "routing": {"standard": ["ghost", "mock"]},
        "policies": {"on_unavailable": "fail"},
    }
    router = ModelRouter(
        config, providers={"ghost": _AlwaysFails(), "mock": MockProvider()}
    )
    with pytest.raises(ProviderUnavailableError):
        router.complete("standard", _req())


def test_missing_capability_raises_no_provider_available():
    router = ModelRouter({"providers": {}, "routing": {}, "policies": {}})
    with pytest.raises(NoProviderAvailableError):
        router.complete("heavy", _req())


def test_load_config_interpolates_env_vars(tmp_path, monkeypatch):
    monkeypatch.setenv("AAP_OPENAI_BASE_URL", "https://api.example.test")
    config_file = tmp_path / "models.yaml"
    config_file.write_text(
        "providers:\n  api_fast:\n    base_url: \"${AAP_OPENAI_BASE_URL}\"\n", encoding="utf-8"
    )
    config = load_config(config_file)
    assert config["providers"]["api_fast"]["base_url"] == "https://api.example.test"


def test_load_config_leaves_unset_env_vars_empty(tmp_path):
    config_file = tmp_path / "models.yaml"
    config_file.write_text(
        "providers:\n  api_fast:\n    base_url: \"${AAP_TOTALLY_UNSET_VAR}\"\n", encoding="utf-8"
    )
    config = load_config(config_file)
    assert config["providers"]["api_fast"]["base_url"] == ""


def test_default_repo_config_loads_and_degrades_to_mock(monkeypatch):
    """El config/models.yaml real del repo debe funcionar sin ninguna API configurada."""
    from pathlib import Path

    for var in ("AAP_OPENAI_BASE_URL", "AAP_OPENAI_API_KEY", "AAP_OPENAI_MODEL"):
        monkeypatch.delenv(var, raising=False)

    repo_root = Path(__file__).resolve().parents[1]
    router = ModelRouter.from_file(repo_root / "config" / "models.yaml")
    result = router.complete("standard", _req())
    assert result.model_used == "mock-echo"
