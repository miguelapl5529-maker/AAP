import pytest

from aap.core.definition import repository as repo


def test_create_agent_and_first_version_becomes_active(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter", owner="miguel")
    version = repo.create_version("demand-hunter", demand_hunter_definition, created_by="miguel")

    assert version["version"] == 1
    assert version["status"] == "active"
    assert version["definition"]["id"] == "demand-hunter"

    agent = repo.get_agent("demand-hunter")
    active = repo.get_active_version("demand-hunter")
    assert agent["active_version_id"] == active["id"]
    assert active["version"] == 1


def test_duplicate_agent_id_rejected(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    with pytest.raises(repo.DuplicateAgentError):
        repo.create_agent("demand-hunter", "Otro nombre")


def test_creating_agent_version_requires_existing_agent(demand_hunter_definition):
    with pytest.raises(repo.AgentNotFoundError):
        repo.create_version("no-existe", demand_hunter_definition)


def test_second_version_archives_the_first(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    v1 = repo.create_version("demand-hunter", demand_hunter_definition)

    demand_hunter_definition["policies"]["budget"]["max_steps"] = 40
    v2 = repo.create_version("demand-hunter", demand_hunter_definition)

    assert v2["version"] == 2
    assert v2["status"] == "active"

    versions = repo.list_versions("demand-hunter")
    assert [v["version"] for v in versions] == [1, 2]
    assert next(v for v in versions if v["version"] == 1)["status"] == "archived"

    active = repo.get_active_version("demand-hunter")
    assert active["id"] == v2["id"]


def test_versions_are_immutable_content(demand_hunter_definition):
    """No existe ninguna operación de UPDATE sobre definition_json/content_hash."""
    repo.create_agent("demand-hunter", "Demand Hunter")
    v1 = repo.create_version("demand-hunter", demand_hunter_definition)
    reread = repo.get_version("demand-hunter", 1)
    assert reread["content_hash"] == v1["content_hash"]
    assert reread["definition"] == v1["definition"]
