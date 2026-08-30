"""Model Router (§6.6, §17.1–17.3): tabla + cadena de degradación. Nada más.

Traduce una capacidad (`cheap`/`standard`/`heavy`/`coding`/`embedding`) en
un provider físico concreto, según `config/models.yaml` —que NUNCA es
parte de ninguna Agent Definition—, recorriendo la cadena declarada hasta
encontrar uno sano. No aprende, no optimiza, no es ML: es un diccionario
y una regla, tal como pide la arquitectura para V1.
"""

import os
import re
from pathlib import Path

import yaml

from aap.core.llm.errors import NoProviderAvailableError, ProviderUnavailableError
from aap.core.llm.interface import Capability, CompletionRequest, CompletionResult, LLMProvider
from aap.core.llm.providers.mock import MockProvider
from aap.core.llm.providers.openai_compatible import OpenAICompatibleProvider

_ENV_VAR_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _interpolate(value):
    if isinstance(value, str):
        return _ENV_VAR_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value


def load_config(path: Path) -> dict:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return _interpolate(raw)


def build_provider(name: str, provider_cfg: dict) -> LLMProvider:
    kind = provider_cfg.get("kind")
    if kind == "mock":
        return MockProvider()
    if kind == "openai_compatible":
        cost = provider_cfg.get("cost_per_1k", {})
        return OpenAICompatibleProvider(
            base_url=provider_cfg.get("base_url", ""),
            model=provider_cfg.get("model", ""),
            api_key=provider_cfg.get("api_key") or None,
            cost_per_1k_in=float(cost.get("in", 0.0)),
            cost_per_1k_out=float(cost.get("out", 0.0)),
        )
    raise ProviderUnavailableError(f"provider kind desconocido: {kind!r} ({name})")


class ModelRouter:
    def __init__(self, config: dict, providers: dict[str, LLMProvider] | None = None):
        self._providers_cfg: dict[str, dict] = config.get("providers", {})
        self._routing: dict[str, list[str]] = config.get("routing", {})
        self._on_unavailable = config.get("policies", {}).get("on_unavailable", "next_in_chain")
        self._provider_instances: dict[str, LLMProvider] = dict(providers or {})

    @classmethod
    def from_file(cls, path: Path) -> "ModelRouter":
        return cls(load_config(path))

    def _get_provider(self, name: str) -> LLMProvider:
        if name not in self._provider_instances:
            cfg = self._providers_cfg.get(name)
            if cfg is None:
                raise ProviderUnavailableError(f"provider no declarado en config/models.yaml: {name}")
            self._provider_instances[name] = build_provider(name, cfg)
        return self._provider_instances[name]

    def complete(self, capability: Capability, req: CompletionRequest) -> CompletionResult:
        chain = self._routing.get(capability, [])
        if not chain:
            raise NoProviderAvailableError(f"sin cadena de routing para capability={capability!r}")

        last_error: Exception | None = None
        for provider_name in chain:
            try:
                provider = self._get_provider(provider_name)
                return provider.complete(req)
            except ProviderUnavailableError as exc:
                last_error = exc
                if self._on_unavailable != "next_in_chain":
                    raise
                continue

        raise NoProviderAvailableError(
            f"se agotó la cadena de degradación para capability={capability!r}: {last_error}"
        )
