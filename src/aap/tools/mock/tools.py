"""Las 6 tools del mundo simulado, con el mismo contrato ToolSpec que
tendría una integración real (§10.1) y los mismos modos de fallo que
pide el brief: éxito, timeout, error, resultado vacío, duplicado.

Esto es lo que permite probar el runtime entero sin GPU y sin servicios
externos (§0.5).
"""

import uuid

from aap.core.tools.broker import ToolExecutionError, ToolTimeoutError
from aap.core.tools.registry import ToolRegistry
from aap.core.tools.spec import CostHint, ToolSpec
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
        title="Consulta al Entity Store (mundo simulado)",
        description="Lee filas de una tabla del dominio simulado, con filtro exacto por campo.",
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
        rows = world.table(args["table"])
        filt = args.get("filter") or {}
        matched = [r for r in rows if all(r.get(k) == v for k, v in filt.items())]
        return {"rows": matched}

    return spec, fn


def make_db_upsert(world: MockWorld):
    spec = ToolSpec(
        id="db.upsert.mock",
        title="Escritura en el Entity Store (mundo simulado)",
        description=(
            "Inserta una fila por clave natural. Si la clave ya existe, "
            "devuelve status=duplicate en vez de crear una fila nueva — "
            "igual que la deduplicación real del dominio."
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
        rows = world.table(args["table"])
        natural_key = args["natural_key"]
        existing = next((r for r in rows if r.get("natural_key") == natural_key), None)
        if fault == "duplicate" or existing:
            return {"status": "duplicate", "id": existing["id"] if existing else ""}
        row_id = str(uuid.uuid4())
        rows.append({"id": row_id, "natural_key": natural_key, **args["values"]})
        return {"status": "created", "id": row_id}

    return spec, fn


def make_memory_search(world: MockWorld):
    spec = ToolSpec(
        id="memory.search.mock",
        title="Búsqueda en memoria de largo plazo (mundo simulado)",
        description="Recupera hasta k memorias curadas por coincidencia de texto simple, sin embeddings.",
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
        query = args["query"].lower()
        k = args.get("k", 6)
        matches = [m for m in world.memories if query in m.get("content", "").lower()]
        return {"memories": matches[:k]}

    return spec, fn


def make_memory_write(world: MockWorld):
    spec = ToolSpec(
        id="memory.write.mock",
        title="Escritura en memoria de largo plazo (mundo simulado)",
        description=(
            "Guarda una afirmación curada con procedencia obligatoria "
            "(source_run_id). Sujeta a política, igual que la real."
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
        mem_id = str(uuid.uuid4())
        world.memories.append({"id": mem_id, **args})
        return {"id": mem_id}

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


_FACTORIES = (
    make_search_web,
    make_db_query,
    make_db_upsert,
    make_memory_search,
    make_memory_write,
    make_llm_extract,
)


def register_all(registry: ToolRegistry, world: MockWorld) -> None:
    for factory in _FACTORIES:
        spec, fn = factory(world)
        registry.register(spec, fn)


def build_mock_registry(world: MockWorld) -> ToolRegistry:
    registry = ToolRegistry()
    register_all(registry, world)
    return registry
