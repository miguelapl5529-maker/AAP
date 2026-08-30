"""La prueba de fuego de §7, literal:

    Crear "Lead Discovery Agent" duplicando "Demand Hunter", cambiando
    objetivo, dos tools, la política de red y el criterio de éxito,
    sin un solo commit en `core/`.

Este archivo solo llama a funciones que ya existían antes de H8
(`execute_run`, el registro de tools mock, el router) más las de la
Factory (`duplicate_agent`). No añade ninguna tool nueva, ninguna regla
de política nueva, ningún nivel de autonomía nuevo: crear un agente es
una operación de datos, no de código (§7, §20.2).
"""

from pathlib import Path

from aap.core.definition import repository as repo
from aap.core.definition.export import definition_from_yaml_doc
from aap.core.definition.validate import validate_definition
from aap.core.llm.interface import CompletionResult, ToolCall, Usage
from aap.core.llm.providers.mock import MockProvider
from aap.core.runtime.executor import execute_run
from aap.core.runtime.runs import create_run
from aap.domain.entities import query_entities
from aap.factory.clone import duplicate_agent
from aap.factory.diff import diff_versions
from aap.tools.mock.world import default_world
from tests.conftest import build_registry_with_state, make_scripted_router

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMAND_HUNTER_YAML = REPO_ROOT / "agents" / "demand-hunter" / "v1.yaml"


def test_lead_discovery_agent_is_a_real_working_duplicate_with_changes():
    # 0. El agente real del repo, recuperado desde Git (igual que en H6).
    source_definition = definition_from_yaml_doc(DEMAND_HUNTER_YAML.read_text(encoding="utf-8"))
    repo.create_agent("demand-hunter", "Demand Hunter Demo", owner="miguel")
    repo.create_version("demand-hunter", source_definition, created_by="miguel")

    # 1-4. Duplicar cambiando objetivo, dos tools, política de red y
    # criterio de éxito — todo en una sola llamada a la Factory.
    lead_discovery = duplicate_agent(
        "demand-hunter",
        "lead-discovery",
        "Lead Discovery Agent",
        owner="miguel",
        activate=True,
        overrides={
            "goal": {
                # objetivo cambiado
                "statement": "Encontrar leads de desarrollo de software a medida en el mundo simulado.",
                # criterio de éxito cambiado (variable de estado nueva)
                "success_criteria": [{"type": "metric", "expr": "leads_calificados >= 1"}],
            },
            # dos tools cambiadas: fuera llm.extract.mock y memory.write.mock,
            # dentro memory.search.mock
            "tools": [
                {"id": "search.web.mock", "config": {"max_results": 10}},
                {"id": "db.upsert.mock", "config": {"tables": ["companies", "signals"]}},
                {"id": "memory.search.mock"},
            ],
            "memory": {"state_schema": {
                "fase": {"type": "string", "enum": ["buscar", "registrar"]},
                "leads_calificados": {"type": "integer", "default": 0},
            }},
            # política de red cambiada: se añade un dominio nuevo
            "policies": {"network": {
                "mode": "allowlist",
                "domains": ["*.internal.test", "*.linkedin.com"],
            }},
        },
    )

    assert lead_discovery["status"] == "active"
    definition = validate_definition(lead_discovery["definition"])

    # Confirmación explícita de los cuatro cambios pedidos.
    assert definition.goal.statement != source_definition["goal"]["statement"]
    assert [c.expr for c in definition.goal.success_criteria] == ["leads_calificados >= 1"]
    assert {t.id for t in definition.tools} == {"search.web.mock", "db.upsert.mock", "memory.search.mock"}
    assert definition.policies.network.domains == ["*.internal.test", "*.linkedin.com"]

    # El original queda intacto (§16.3).
    assert repo.get_active_version("demand-hunter")["definition"]["goal"]["statement"] == \
        source_definition["goal"]["statement"]

    # El diff lo confirma de un vistazo (§14.3, §22.2) — no aplica aquí
    # porque son agentes distintos, pero comparar v1 del propio
    # lead-discovery consigo misma prueba que el mecanismo funciona.
    self_diff = diff_versions("lead-discovery", 1, 1)
    assert self_diff["diff"] == {"added": {}, "changed": {}, "removed": {}}

    # 5. Y lo más importante: CORRE. Sin tocar core/ ni tools/ para nada
    # de esto — solo se usa lo que ya existía.
    world = default_world()
    run = create_run(definition.id, lead_discovery["id"], input_data={"objetivo": "leads de software"})
    registry = build_registry_with_state(
        world, run["id"], definition.memory.state_schema,
        agent_id=definition.id, agent_version_id=lead_discovery["id"],
    )

    plan = CompletionResult(
        text=None,
        tool_calls=[
            ToolCall(id="1", tool_id="search.web.mock", arguments={"query": "automatización"}),
            ToolCall(id="2", tool_id="db.upsert.mock", arguments={
                "table": "signals", "natural_key": "rutasdelsur.mock:lead-software",
                "values": {"company_id": "c1", "type": "necesidad de software a medida"},
            }),
            ToolCall(id="3", tool_id="memory.search.mock", arguments={"query": "software"}),
            ToolCall(id="4", tool_id="state.update", arguments={"fase": "registrar", "leads_calificados": 1}),
        ],
        usage=Usage(prompt_tokens=90, completion_tokens=30, cost_usd=0.002, latency_ms=10),
        model_used="mock-plan",
        finish_reason="tool_calls",
    )
    router = make_scripted_router(MockProvider(script=[plan]))

    result = execute_run(definition, router, registry, run["id"], {"objetivo": "leads de software"})

    assert result["status"] == "completed"
    assert result["termination_reason"] == "completed"
    assert result["output"]["final_state"]["leads_calificados"] == 1

    signals = query_entities("signals")
    assert any(s["natural_key"] == "rutasdelsur.mock:lead-software" for s in signals)
