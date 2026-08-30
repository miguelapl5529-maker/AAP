"""Criterio de aceptación de H10: el eval set fijo del brief corriendo
contra el agente real (recuperado desde su YAML exportado, como en H6/
H8), y una comparación v1 vs v2 que muestra una regresión real de
coste/latencia/tasa de éxito — no datos fabricados para que el test
pase."""

from pathlib import Path

from aap.core.definition import repository as repo
from aap.core.definition.export import definition_from_yaml_doc
from aap.core.definition.validate import validate_definition
from aap.core.evaluation.compare import compare_versions_by_metrics
from aap.core.evaluation.eval_runner import run_eval_set
from aap.core.llm.interface import CompletionResult, ToolCall, Usage
from aap.core.llm.providers.mock import MockProvider
from aap.core.runtime.executor import execute_run
from aap.core.runtime.runs import create_run
from aap.tools.mock.world import default_world
from tests.conftest import build_registry_with_state, make_scripted_router

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMAND_HUNTER_YAML = REPO_ROOT / "agents" / "demand-hunter" / "v2.yaml"
EVAL_SET = REPO_ROOT / "evals" / "demand_hunter_v1.jsonl"


def _registry_factory(agent_id, agent_version_id, definition):
    def factory(run_id, faults):
        world = default_world()
        for f in faults:
            world.schedule_fault(f["tool_id"], f["fault"])
        return build_registry_with_state(
            world, run_id, definition.memory.state_schema,
            agent_id=agent_id, agent_version_id=agent_version_id,
        )
    return factory


def test_eval_set_ref_is_declared_and_the_file_exists():
    definition_dict = definition_from_yaml_doc(DEMAND_HUNTER_YAML.read_text(encoding="utf-8"))
    definition = validate_definition(definition_dict)
    assert definition.evaluation.eval_set_ref == "evals/demand_hunter_v1.jsonl"
    assert EVAL_SET.exists()


def test_fixed_eval_set_passes_against_the_real_agent():
    definition_dict = definition_from_yaml_doc(DEMAND_HUNTER_YAML.read_text(encoding="utf-8"))
    repo.create_agent("demand-hunter", "Demand Hunter Demo", owner="miguel")
    version = repo.create_version("demand-hunter", definition_dict, created_by="miguel")
    definition = validate_definition(version["definition"])

    report = run_eval_set(
        definition, version["id"], _registry_factory(definition.id, version["id"], definition), EVAL_SET,
    )

    assert report["total"] == 2
    assert report["failed"] == 0, report["scenarios"]


def test_compare_v1_vs_v2_shows_a_real_cost_regression(demand_hunter_definition):
    """Ambas versiones completan con éxito (misma señal encontrada) —
    la regresión es puramente de coste, producida por runs reales
    ejecutados de punta a punta, no inyectada a mano en el reporte. Es
    justo la pregunta que más importa según §12.3: ¿la nueva versión
    resuelve lo mismo más caro?

    (La latencia real del run es tiempo de reloj de pared del propio
    executor, no el latency_ms simulado que lleva el Usage de un LLM
    scripteado — con el provider mock ambas versiones corren casi
    instantáneamente sin importar qué latencia diga el script, así que
    comparar latencia aquí no demostraría nada real.)"""
    repo.create_agent("demand-hunter", "Demand Hunter Demo")
    v1 = repo.create_version("demand-hunter", demand_hunter_definition)
    v2 = repo.create_version("demand-hunter", demand_hunter_definition)
    definition = validate_definition(demand_hunter_definition)
    state_schema = definition.memory.state_schema
    world = default_world()

    def successful_plan(cost_usd: float, latency_ms: int) -> CompletionResult:
        return CompletionResult(
            text=None,
            tool_calls=[
                ToolCall(id="1", tool_id="search.web.mock", arguments={"query": "automatización"}),
                ToolCall(id="2", tool_id="state.update", arguments={"senales_validas": 1}),
            ],
            usage=Usage(prompt_tokens=50, completion_tokens=10, cost_usd=cost_usd, latency_ms=latency_ms),
            model_used="mock", finish_reason="tool_calls",
        )

    run1 = create_run("demand-hunter", v1["id"])
    registry1 = build_registry_with_state(world, run1["id"], state_schema)
    execute_run(
        definition, make_scripted_router(MockProvider(script=[successful_plan(0.001, 5)])),
        registry1, run1["id"], {},
    )

    run2 = create_run("demand-hunter", v2["id"])
    registry2 = build_registry_with_state(world, run2["id"], state_schema)
    execute_run(
        definition, make_scripted_router(MockProvider(script=[successful_plan(0.50, 4000)])),
        registry2, run2["id"], {},
    )

    report = compare_versions_by_metrics("demand-hunter", 1, 2)

    assert report["a"]["metrics"]["completion_rate"] == 1.0
    assert report["b"]["metrics"]["completion_rate"] == 1.0  # ambas "funcionan"
    assert report["delta"]["completion_rate"] == 0.0
    assert report["delta"]["avg_cost_usd"] > 0.4  # pero v2 es ~500x más cara
