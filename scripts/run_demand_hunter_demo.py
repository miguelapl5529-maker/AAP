"""Demo manual: ejecuta el Demand Hunter Demo registrado contra los datos
reales del proyecto (./data), con el provider mock. Uso:

    AAP_DATA_DIR=./data python scripts/run_demand_hunter_demo.py

Requiere que el agente ya exista (aap create-agent / create-version, o
haber corrido esto una vez). No es parte de la suite de tests: es la
forma de ver el sistema funcionar de verdad, tal como pide §0.5.
"""

from aap.core.definition import repository as repo
from aap.core.definition.validate import validate_definition
from aap.core.llm.interface import CompletionResult, ToolCall, Usage
from aap.core.llm.providers.mock import MockProvider
from aap.core.llm.router import ModelRouter
from aap.core.runtime.executor import execute_run
from aap.core.runtime.runs import create_run
from aap.tools.builtin.state import make_state_update_tool
from aap.tools.mock.tools import build_mock_registry
from aap.tools.mock.world import default_world


def main() -> None:
    version = repo.get_active_version("demand-hunter")
    definition = validate_definition(version["definition"])
    print(f"Ejecutando {definition.identity.name} v{version['version']}")

    world = default_world()
    run = create_run(definition.id, version["id"], trigger="manual", input_data={"sector": "logistica"})
    print(f"run_id = {run['id']}")

    registry = build_mock_registry(
        world, run_id=run["id"], agent_id=definition.id, agent_version_id=version["id"],
    )
    spec, fn = make_state_update_tool(run["id"], definition.memory.state_schema)
    registry.register(spec, fn)

    plan = CompletionResult(
        text=None,
        tool_calls=[
            ToolCall(id="1", tool_id="search.web.mock", arguments={"query": "automatización"}),
            ToolCall(id="2", tool_id="db.upsert.mock", arguments={
                "table": "signals",
                "natural_key": "rutasdelsur.mock:automatizacion-flota",
                "values": {"company_id": "c1", "type": "automatización de flota", "score": 0.8},
            }),
            ToolCall(id="3", tool_id="memory.write.mock", arguments={
                "type": "patron_senal",
                "content": "logística + automatización de flota es un patrón fuerte",
                "source_run_id": run["id"],
            }),
            ToolCall(id="4", tool_id="state.update", arguments={"fase": "registrar", "senales_validas": 1}),
        ],
        usage=Usage(prompt_tokens=150, completion_tokens=45, cost_usd=0.004, latency_ms=20),
        model_used="mock-plan",
        finish_reason="tool_calls",
    )
    router = ModelRouter(
        {"providers": {}, "routing": {"standard": ["scripted"]}, "policies": {"on_unavailable": "fail"}},
        providers={"scripted": MockProvider(script=[plan])},
    )

    result = execute_run(definition, router, registry, run["id"], {"sector": "logistica"})
    print(f"status = {result['status']}  termination_reason = {result['termination_reason']}")
    print(f"tool_calls = {result['tool_calls']}  cost_usd = {result['cost_usd']}")


if __name__ == "__main__":
    main()
