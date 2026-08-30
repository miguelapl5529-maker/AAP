import os
from pathlib import Path

import pytest

from aap.core.definition.models import BudgetPolicy, Policies
from aap.core.llm.router import ModelRouter
from aap.core.policy.context import PolicyContext
from aap.core.runtime.budget import BudgetManager
from aap.core.tools.registry import ToolRegistry
from aap.tools.builtin.state import make_state_update_tool
from aap.tools.mock.tools import build_mock_registry


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Cada test corre contra su propio directorio de datos: nunca toca ./data real."""
    monkeypatch.setenv("AAP_DATA_DIR", str(tmp_path / "data"))
    yield tmp_path


def make_budget_policy(**overrides) -> BudgetPolicy:
    defaults = dict(
        max_steps=25, max_tool_calls=60, max_tokens=400_000,
        max_money_usd=2.0, max_wallclock_s=900,
    )
    defaults.update(overrides)
    return BudgetPolicy(**defaults)


def make_policy_context(
    budget_overrides: dict | None = None,
    dry_run: bool = False,
    clock=None,
    **policy_overrides,
) -> PolicyContext:
    """Construye un PolicyContext de pruebas con defaults permisivos
    razonables, sobreescribibles pieza a pieza."""
    policy_overrides.setdefault(
        "network", {"mode": "allowlist", "domains": ["*.internal.test"]}
    )
    policy_overrides.setdefault(
        "database", {"domain_db": "read_write", "tables": ["companies", "signals"]}
    )
    policies = Policies(
        budget=make_budget_policy(**(budget_overrides or {})),
        **policy_overrides,
    )
    budget = BudgetManager(policies.budget, clock=clock) if clock else BudgetManager(policies.budget)
    return PolicyContext(policies=policies, budget=budget, dry_run=dry_run)


@pytest.fixture
def policy_context_factory():
    return make_policy_context


def make_scripted_router(provider, capabilities=("cheap", "standard", "heavy", "coding", "embedding")):
    """Router de pruebas: toda capacidad va directa al provider scripteado
    dado (normalmente un MockProvider(script=[...])), sin degradación."""
    config = {
        "providers": {},
        "routing": {cap: ["scripted"] for cap in capabilities},
        "policies": {"on_unavailable": "fail"},
    }
    return ModelRouter(config, providers={"scripted": provider})


def build_registry_with_state(
    world, run_id: str, state_schema: dict, agent_id: str = "unknown-agent",
    agent_version_id: str | None = None,
) -> ToolRegistry:
    """Las 6 tools del mundo simulado + la única tool que todo agente tiene
    siempre disponible: escribir en su propio run_state (§9.2)."""
    registry = build_mock_registry(world, run_id=run_id, agent_id=agent_id, agent_version_id=agent_version_id)
    spec, fn = make_state_update_tool(run_id, state_schema)
    registry.register(spec, fn)
    return registry


@pytest.fixture
def scripted_router_factory():
    return make_scripted_router


@pytest.fixture
def full_registry_factory():
    return build_registry_with_state


@pytest.fixture
def demand_hunter_definition() -> dict:
    """Definición mínima válida, usada por H1 en adelante como fixture compartida."""
    return {
        "schema_version": 1,
        "id": "demand-hunter",
        "identity": {
            "name": "Demand Hunter",
            "description": "Detecta empresas con señales de necesidad de automatización",
            "owner": "miguel",
            "tags": ["ventas", "prospección"],
        },
        "goal": {
            "statement": (
                "Encontrar empresas del sector logístico en España con señales de "
                "necesidad de automatización y registrarlas como oportunidades."
            ),
            # La expr se evalúa contra las claves de memory.state_schema (§14.3):
            # tiene que citar "senales_validas", no un nombre inventado.
            "success_criteria": [{"type": "metric", "expr": "senales_validas >= 1"}],
        },
        "runtime": {"autonomy_level": 2, "max_iterations": 10, "resumable": True},
        "brain": {
            "primary": {"capability": "standard", "temperature": 0.2},
            "cheap": {"capability": "cheap", "use_for": ["extract"]},
        },
        "tools": [
            {"id": "search.web.mock", "config": {"max_results": 10}},
            {"id": "llm.extract.mock"},
            {"id": "db.upsert.mock", "config": {"tables": ["companies", "signals"]}},
            {"id": "memory.write.mock"},
        ],
        "memory": {
            "state_schema": {
                "fase": {"type": "string", "enum": ["buscar", "registrar"]},
                "senales_validas": {"type": "integer", "default": 0},
            }
        },
        "policies": {
            # Debe cubrir el network_domain real de search.web.mock (ver
            # tools/mock/tools.py) o toda búsqueda queda denegada en silencio.
            "network": {"mode": "allowlist", "domains": ["*.internal.test"]},
            "database": {"domain_db": "read_write", "tables": ["companies", "signals"]},
            "budget": {
                "max_steps": 25,
                "max_tool_calls": 60,
                "max_tokens": 400000,
                "max_money_usd": 2.0,
                "max_wallclock_s": 900,
            },
        },
        "triggers": [{"type": "manual"}],
    }
