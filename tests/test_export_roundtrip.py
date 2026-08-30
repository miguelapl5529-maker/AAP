from aap.core.definition import repository as repo
from aap.core.definition.export import definition_from_yaml_doc, export_yaml, roundtrip_hash_matches


def test_export_import_is_idempotent(demand_hunter_definition):
    """Criterio de aceptación de M1: exportar→importar produce el mismo hash."""
    repo.create_agent("demand-hunter", "Demand Hunter")
    version = repo.create_version("demand-hunter", demand_hunter_definition)

    assert roundtrip_hash_matches(version)


def test_yaml_contains_human_readable_metadata(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    version = repo.create_version("demand-hunter", demand_hunter_definition)

    yaml_text = export_yaml(version)
    assert "version: 1" in yaml_text
    assert "status: active" in yaml_text
    assert "demand-hunter" in yaml_text

    recovered = definition_from_yaml_doc(yaml_text)
    assert "version" not in recovered
    assert "status" not in recovered
    assert recovered["id"] == "demand-hunter"
