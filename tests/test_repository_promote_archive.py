from aap.core.definition import repository as repo


def test_promote_activates_a_draft_and_archives_the_previous_active(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    v1 = repo.create_version("demand-hunter", demand_hunter_definition)  # activa

    edited = dict(demand_hunter_definition)
    edited["policies"]["budget"]["max_steps"] = 40
    v2 = repo.create_version("demand-hunter", edited, activate=False)  # draft

    assert repo.get_version("demand-hunter", 2)["status"] == "draft"

    promoted = repo.promote_version("demand-hunter", 2)
    assert promoted["status"] == "active"
    assert repo.get_version("demand-hunter", 1)["status"] == "archived"
    assert repo.get_agent("demand-hunter")["active_version_id"] == v2["id"]


def test_promoting_the_already_active_version_is_idempotent(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    repo.create_version("demand-hunter", demand_hunter_definition)

    promoted = repo.promote_version("demand-hunter", 1)
    assert promoted["status"] == "active"
    assert repo.get_agent("demand-hunter")["active_version_id"] == promoted["id"]


def test_rollback_is_just_promoting_an_older_version(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    v1 = repo.create_version("demand-hunter", demand_hunter_definition)
    edited = dict(demand_hunter_definition)
    edited["policies"]["budget"]["max_steps"] = 40
    repo.create_version("demand-hunter", edited)  # v2, activa

    repo.promote_version("demand-hunter", 1)  # rollback

    assert repo.get_agent("demand-hunter")["active_version_id"] == v1["id"]
    assert repo.get_version("demand-hunter", 2)["status"] == "archived"


def test_archive_active_version_leaves_agent_without_active_version(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    repo.create_version("demand-hunter", demand_hunter_definition)

    repo.archive_version("demand-hunter", 1)

    assert repo.get_version("demand-hunter", 1)["status"] == "archived"
    assert repo.get_agent("demand-hunter")["active_version_id"] is None


def test_archive_a_draft_does_not_touch_the_active_version(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    v1 = repo.create_version("demand-hunter", demand_hunter_definition)
    repo.create_version("demand-hunter", demand_hunter_definition, activate=False)  # v2 draft

    repo.archive_version("demand-hunter", 2)

    assert repo.get_agent("demand-hunter")["active_version_id"] == v1["id"]
    assert repo.get_version("demand-hunter", 1)["status"] == "active"
