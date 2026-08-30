from aap.core.definition import repository as repo
from aap.factory.clone import duplicate_agent


def test_duplicate_copies_the_active_definition_as_a_draft(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    repo.create_version("demand-hunter", demand_hunter_definition)

    dup = duplicate_agent("demand-hunter", "lead-discovery", "Lead Discovery")

    assert dup["version"] == 1
    assert dup["status"] == "draft"  # §16.3: por defecto, un borrador
    assert dup["definition"]["id"] == "lead-discovery"
    assert dup["definition"]["goal"]["statement"] == demand_hunter_definition["goal"]["statement"]

    new_agent = repo.get_agent("lead-discovery")
    assert new_agent["active_version_id"] is None  # el draft no está activo


def test_duplicate_applies_overrides_on_top_of_the_copy(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    repo.create_version("demand-hunter", demand_hunter_definition)

    dup = duplicate_agent(
        "demand-hunter", "lead-discovery", "Lead Discovery",
        overrides={
            "goal": {"statement": "Encontrar leads de software a medida"},
            "policies": {"network": {"domains": ["*.otro-dominio.test"]}},
        },
        activate=True,
    )

    assert dup["status"] == "active"
    assert dup["definition"]["goal"]["statement"] == "Encontrar leads de software a medida"
    assert dup["definition"]["policies"]["network"]["domains"] == ["*.otro-dominio.test"]
    # lo que no se sobreescribió sigue igual que el original
    assert dup["definition"]["policies"]["database"] == demand_hunter_definition["policies"]["database"]


def test_duplicate_never_touches_the_source_agent(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    original = repo.create_version("demand-hunter", demand_hunter_definition)

    duplicate_agent("demand-hunter", "lead-discovery", "Lead Discovery", overrides={"goal": {"statement": "otro"}})

    assert repo.get_active_version("demand-hunter")["id"] == original["id"]
    assert repo.get_active_version("demand-hunter")["definition"]["goal"]["statement"] != "otro"


def test_duplicate_does_not_copy_runs_events_or_state(demand_hunter_definition):
    """§16.3: nunca se copian runs, eventos, memorias ni estado."""
    from aap.core.runtime.runs import create_run, list_runs

    repo.create_agent("demand-hunter", "Demand Hunter")
    version = repo.create_version("demand-hunter", demand_hunter_definition)
    create_run("demand-hunter", version["id"])

    duplicate_agent("demand-hunter", "lead-discovery", "Lead Discovery", activate=True)

    assert list_runs("lead-discovery") == []
