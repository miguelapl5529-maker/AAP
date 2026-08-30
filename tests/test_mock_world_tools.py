from aap.tools.mock.tools import build_mock_registry
from aap.tools.mock.world import default_world


def test_search_web_matches_by_sector_keyword():
    registry = build_mock_registry(default_world())
    fn = registry.get("search.web.mock").fn
    result = fn({"query": "automatización"})
    names = {r["name"] for r in result["results"]}
    assert "Rutas del Sur SL" in names
    assert "TransCarga Ibérica" in names
    assert "Panadería Artesana Luna" not in names


def test_search_web_respects_max_results():
    registry = build_mock_registry(default_world())
    fn = registry.get("search.web.mock").fn
    result = fn({"query": "logistica", "max_results": 1})
    assert len(result["results"]) == 1


def test_db_query_filters_by_field():
    world = default_world()
    world.table("signals").extend(
        [{"id": "s1", "company_id": "c1", "type": "hiring"}, {"id": "s2", "company_id": "c2", "type": "funding"}]
    )
    fn = build_mock_registry(world).get("db.query.mock").fn
    result = fn({"table": "signals", "filter": {"company_id": "c1"}})
    assert [r["id"] for r in result["rows"]] == ["s1"]


def test_memory_write_then_search_roundtrip():
    world = default_world()
    registry = build_mock_registry(world)
    write = registry.get("memory.write.mock").fn
    search = registry.get("memory.search.mock").fn

    write({"type": "empresa_descartada", "content": "no interesa: sector retail", "source_run_id": "run-1"})
    found = search({"query": "retail"})
    assert len(found["memories"]) == 1
    assert found["memories"][0]["source_run_id"] == "run-1"


def test_llm_extract_finds_literal_fields():
    fn = build_mock_registry(default_world()).get("llm.extract.mock").fn
    result = fn({"text": "Empresa: Rutas del Sur. Sector: logistica.", "fields": ["sector", "presupuesto"]})
    assert result["extracted"] == {"sector": "sector"}
