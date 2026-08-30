"""Criterio de aceptación de H6: el Demand Hunter Demo —el agente real
del repositorio, no un fixture de prueba— escribe una señal real en
domain.db y termina COMPLETED, y esa señal sobrevive a un "reinicio del
proceso" (una conexión SQLite completamente nueva, sin nada cacheado en
RAM).
"""

from pathlib import Path

import pytest

from aap.config import domain_db_path
from aap.core.definition import repository as repo
from aap.core.definition.export import definition_from_yaml_doc
from aap.core.definition.validate import validate_definition
from aap.core.db import cursor
from aap.core.events.log import list_events
from aap.core.llm.interface import CompletionResult, ToolCall, Usage
from aap.core.llm.providers.mock import MockProvider
from aap.core.memory.longterm import list_memories
from aap.core.runtime.executor import execute_run
from aap.core.runtime.runs import create_run
from aap.domain.entities import query_entities
from aap.tools.mock.world import default_world
from tests.conftest import build_registry_with_state, make_scripted_router

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMAND_HUNTER_YAML = REPO_ROOT / "agents" / "demand-hunter" / "v1.yaml"


@pytest.fixture
def demand_hunter_from_repo() -> dict:
    """La definición real, tal como la recuperaría `aap import` en una
    máquina nueva (§14.1) — no un fixture de test reescrito a mano."""
    yaml_text = DEMAND_HUNTER_YAML.read_text(encoding="utf-8")
    return definition_from_yaml_doc(yaml_text)


def test_exported_yaml_file_exists_and_is_valid():
    assert DEMAND_HUNTER_YAML.exists(), "agents/demand-hunter/v1.yaml debe existir en el repo (§20.1)"


def test_demand_hunter_demo_writes_a_real_signal_and_completes(demand_hunter_from_repo):
    repo.create_agent("demand-hunter", "Demand Hunter Demo", owner="miguel")
    version = repo.create_version("demand-hunter", demand_hunter_from_repo, created_by="miguel")
    definition = validate_definition(version["definition"])

    world = default_world()
    run = create_run(definition.id, version["id"], trigger="manual", input_data={"sector": "logistica"})
    run_id = run["id"]
    registry = build_registry_with_state(
        world, run_id, definition.memory.state_schema,
        agent_id=definition.id, agent_version_id=version["id"],
    )

    plan = CompletionResult(
        text=None,
        tool_calls=[
            ToolCall(id="1", tool_id="search.web.mock", arguments={"query": "automatización"}),
            ToolCall(id="2", tool_id="llm.extract.mock", arguments={
                "text": "Rutas del Sur SL — sector logistica, señal: automatización de flota",
                "fields": ["sector"],
            }),
            ToolCall(id="3", tool_id="db.upsert.mock", arguments={
                "table": "signals", "natural_key": "rutasdelsur.mock:automatizacion-flota",
                "values": {"company_id": "c1", "type": "automatización de flota", "score": 0.8},
            }),
            ToolCall(id="4", tool_id="memory.write.mock", arguments={
                "type": "patron_senal",
                "content": "logística + automatización de flota es un patrón fuerte",
                "source_run_id": run_id,
            }),
            ToolCall(id="5", tool_id="state.update", arguments={"fase": "registrar", "senales_validas": 1}),
        ],
        usage=Usage(prompt_tokens=150, completion_tokens=45, cost_usd=0.004, latency_ms=20),
        model_used="mock-plan",
        finish_reason="tool_calls",
    )
    router = make_scripted_router(MockProvider(script=[plan]))

    result = execute_run(definition, router, registry, run_id, {"sector": "logistica"})

    assert result["status"] == "completed"
    assert result["termination_reason"] == "completed"

    # --- "reinicio del proceso": conexión SQLite nueva, nada de Python en común ---
    with cursor(domain_db_path()) as cur:
        rows = cur.execute(
            "SELECT natural_key, values_json FROM entities WHERE table_name = 'signals'"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["natural_key"] == "rutasdelsur.mock:automatizacion-flota"
    assert "automatización de flota" in rows[0]["values_json"]

    # y también por la vía normal del repositorio
    signals = query_entities("signals")
    assert signals[0]["source_run_id"] == run_id
    assert signals[0]["agent_version_id"] == version["id"]

    memories = list_memories("demand-hunter")
    assert len(memories) == 1
    assert memories[0]["type"] == "patron_senal"

    events = list_events(run_id)
    assert events[0]["type"] == "run.started"
    assert events[-1]["type"] == "run.finished"
    assert any(e["type"] == "state.updated" for e in events)


def test_demand_hunter_demo_can_demonstrate_a_policy_deny(demand_hunter_from_repo):
    """El brief pide poder demostrar un DENY explícito con el agente real:
    intentar escribir en una tabla fuera de la política declarada."""
    repo.create_agent("demand-hunter", "Demand Hunter Demo")
    version = repo.create_version("demand-hunter", demand_hunter_from_repo)
    definition = validate_definition(version["definition"])

    world = default_world()
    run = create_run(definition.id, version["id"])
    registry = build_registry_with_state(world, run["id"], definition.memory.state_schema)

    forbidden_write = CompletionResult(
        text=None,
        tool_calls=[ToolCall(id="1", tool_id="db.upsert.mock", arguments={
            "table": "outreach_messages",  # fuera de policies.database.tables
            "natural_key": "x", "values": {},
        })],
        usage=Usage(prompt_tokens=10, completion_tokens=5, cost_usd=0.0001, latency_ms=1),
        model_used="mock-plan",
        finish_reason="tool_calls",
    )
    router = make_scripted_router(MockProvider(script=[forbidden_write]))

    execute_run(definition, router, registry, run["id"], {})

    events = list_events(run["id"])
    policy_events = [e for e in events if e["type"] == "policy.evaluated"]
    assert len(policy_events) == 1
    assert policy_events[0]["payload"]["decision"] == "DENY"
    assert "tabla no permitida" in policy_events[0]["payload"]["reason"]
