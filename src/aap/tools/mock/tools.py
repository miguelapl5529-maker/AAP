"""Las 6 tools del mundo simulado, con el mismo contrato ToolSpec que
tendría una integración real (§10.1) y los mismos modos de fallo que
pide el brief: éxito, timeout, error, resultado vacío, duplicado.

"Mock" describe la FUENTE de datos externa (search.web.mock no toca
internet real), no la persistencia: db.query/db.upsert escriben de
verdad en domain.db y memory.search/write en control.db (§9.2, §21.2),
porque un Entity Store falso no demostraría nada sobre sobrevivir a un
reinicio del proceso — que es justo lo que H6 tiene que probar.
"""

from aap.core.memory.longterm import search_memories, write_memory
from aap.core.tools.broker import ToolExecutionError, ToolTimeoutError
from aap.core.tools.registry import ToolRegistry
from aap.core.tools.spec import CostHint, ToolSpec
from aap.domain.entities import query_entities, upsert_entity
from aap.tools.mock.world import MockWorld


def _consume_fault(world: MockWorld, tool_id: str) -> str | None:
    """Si hay un fallo agendado, lo aplica (lanzando si corresponde) y
    devuelve el nombre del fallo para que la tool decida el resto
    (p.ej. "empty" no es una excepción: es una forma válida de resultado)."""
    fault = world.next_fault(tool_id)
    if fault == "timeout":
        raise ToolTimeoutError(f"{tool_id}: timeout simulado")
    if fault == "error":
        raise ToolExecutionError(f"{tool_id}: error simulado")
    return fault


def make_search_web(world: MockWorld):
    spec = ToolSpec(
        id="search.web.mock",
        title="Búsqueda web (mundo simulado)",
        description=(
            "Busca empresas del mundo simulado por palabra clave en nombre, "
            "sector o señales conocidas. No accede a internet real: es el "
            "sensor primario del Demand Hunter Demo. No sirve para nada fuera "
            "del mundo simulado."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
        output_schema={
            "type": "object",
            "properties": {"results": {"type": "array"}},
            "required": ["results"],
        },
        permissions=["network.http"],
        side_effects="read",
        network_domain="mock-search.internal.test",
        cost_hint=CostHint(money=0.0, latency_ms=50),
    )

    def fn(args: dict) -> dict:
        fault = _consume_fault(world, spec.id)
        if fault == "empty":
            return {"results": []}
        query = args["query"].lower()
        max_results = args.get("max_results", 10)
        matches = [
            {
                "id": c.id, "name": c.name, "domain": c.domain, "sector": c.sector,
                "snippet": " ".join(c.keywords),
            }
            for c in world.companies
            if query in " ".join([c.name, c.sector, *c.keywords]).lower()
        ]
        return {"results": matches[:max_results]}

    return spec, fn


def make_db_query(world: MockWorld):
    spec = ToolSpec(
        id="db.query.mock",
        title="Consulta al Entity Store",
        description="Lee filas de una tabla de domain.db, con filtro exacto por campo.",
        input_schema={
            "type": "object",
            "properties": {"table": {"type": "string"}, "filter": {"type": "object"}},
            "required": ["table"],
        },
        output_schema={
            "type": "object", "properties": {"rows": {"type": "array"}}, "required": ["rows"],
        },
        permissions=["database.read"],
        side_effects="read",
    )

    def fn(args: dict) -> dict:
        fault = _consume_fault(world, spec.id)
        if fault == "empty":
            return {"rows": []}
        entities = query_entities(args["table"], args.get("filter"))
        return {"rows": [{"id": e["id"], "natural_key": e["natural_key"], **e["values"]} for e in entities]}

    return spec, fn


def make_db_upsert(world: MockWorld, run_id: str | None = None, agent_version_id: str | None = None):
    spec = ToolSpec(
        id="db.upsert.mock",
        title="Escritura en el Entity Store",
        description=(
            "Inserta una fila en domain.db por clave natural. Si la clave ya "
            "existe, devuelve status=duplicate en vez de crear una fila nueva "
            "— la misma deduplicación que tendría el dominio real."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "table": {"type": "string"},
                "natural_key": {"type": "string"},
                "values": {"type": "object"},
            },
            "required": ["table", "natural_key", "values"],
        },
        output_schema={
            "type": "object",
            "properties": {"status": {"type": "string"}, "id": {"type": "string"}},
            "required": ["status", "id"],
        },
        permissions=["database.write", "database.read"],
        side_effects="write",
        idempotent=True,
    )

    def fn(args: dict) -> dict:
        fault = _consume_fault(world, spec.id)
        if fault == "duplicate":
            return {"status": "duplicate", "id": ""}
        return upsert_entity(
            args["table"], args["natural_key"], args["values"],
            source_run_id=run_id, agent_version_id=agent_version_id,
        )

    return spec, fn


def make_memory_search(world: MockWorld, agent_id: str = "unknown-agent"):
    spec = ToolSpec(
        id="memory.search.mock",
        title="Búsqueda en memoria de largo plazo",
        description="Recupera hasta k memorias curadas de control.db por coincidencia de texto simple, sin embeddings.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}, "k": {"type": "integer", "default": 6}},
            "required": ["query"],
        },
        output_schema={
            "type": "object", "properties": {"memories": {"type": "array"}}, "required": ["memories"],
        },
        permissions=["memory.read"],
        side_effects="read",
    )

    def fn(args: dict) -> dict:
        fault = _consume_fault(world, spec.id)
        if fault == "empty":
            return {"memories": []}
        matches = search_memories(agent_id, args["query"], k=args.get("k", 6))
        return {"memories": matches}

    return spec, fn


def make_memory_write(world: MockWorld, agent_id: str = "unknown-agent"):
    spec = ToolSpec(
        id="memory.write.mock",
        title="Escritura en memoria de largo plazo",
        description=(
            "Guarda una afirmación curada en control.db con procedencia "
            "obligatoria (source_run_id). Sujeta a política, igual que la real."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "subject": {"type": "string"},
                "content": {"type": "string"},
                "source_run_id": {"type": "string"},
            },
            "required": ["type", "content", "source_run_id"],
        },
        output_schema={
            "type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"],
        },
        permissions=["memory.write"],
        side_effects="write",
    )

    def fn(args: dict) -> dict:
        _consume_fault(world, spec.id)
        result = write_memory(
            agent_id, args["type"], args["content"], args["source_run_id"],
            subject=args.get("subject"),
        )
        return {"id": result["id"]}

    return spec, fn


def make_llm_extract(world: MockWorld):
    spec = ToolSpec(
        id="llm.extract.mock",
        title="Extracción estructurada (mundo simulado)",
        description=(
            "Extrae campos de un texto según una lista de nombres de campo. "
            "Determinista: no llama a ningún LLM real, solo detecta qué "
            "campos aparecen literalmente en el texto."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "fields": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["text", "fields"],
        },
        output_schema={
            "type": "object", "properties": {"extracted": {"type": "object"}}, "required": ["extracted"],
        },
        permissions=[],
        side_effects="read",
    )

    def fn(args: dict) -> dict:
        fault = _consume_fault(world, spec.id)
        if fault == "empty":
            return {"extracted": {}}
        text = args["text"].lower()
        extracted = {f: f for f in args["fields"] if f.lower() in text}
        return {"extracted": extracted}

    return spec, fn


def register_all(
    registry: ToolRegistry,
    world: MockWorld,
    run_id: str | None = None,
    agent_id: str = "unknown-agent",
    agent_version_id: str | None = None,
) -> None:
    for spec, fn in (
        make_search_web(world),
        make_db_query(world),
        make_db_upsert(world, run_id=run_id, agent_version_id=agent_version_id),
        make_memory_search(world, agent_id=agent_id),
        make_memory_write(world, agent_id=agent_id),
        make_llm_extract(world),
    ):
        registry.register(spec, fn)


def build_mock_registry(
    world: MockWorld,
    run_id: str | None = None,
    agent_id: str = "unknown-agent",
    agent_version_id: str | None = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    register_all(registry, world, run_id=run_id, agent_id=agent_id, agent_version_id=agent_version_id)
    return registry
