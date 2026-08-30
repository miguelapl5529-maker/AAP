from aap.core.definition import repository as repo
from aap.factory.diff import deep_diff, diff_versions


def test_deep_diff_reports_added_changed_and_removed():
    old = {"a": 1, "b": {"c": 2, "d": 3}}
    new = {"a": 1, "b": {"c": 5}, "e": 9}

    diff = deep_diff(old, new)
    assert diff["changed"] == {"b.c": {"from": 2, "to": 5}}
    assert diff["removed"] == {"b.d": 3}
    assert diff["added"] == {"e": 9}


def test_diff_versions_between_two_saved_versions(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    repo.create_version("demand-hunter", demand_hunter_definition)

    edited = dict(demand_hunter_definition)
    edited["policies"] = dict(edited["policies"])
    edited["policies"]["budget"] = {**edited["policies"]["budget"], "max_steps": 40}
    repo.create_version("demand-hunter", edited)

    result = diff_versions("demand-hunter", 1, 2)
    assert result["diff"]["changed"]["policies.budget.max_steps"] == {"from": 25, "to": 40}


def test_diff_of_identical_versions_is_empty(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    repo.create_version("demand-hunter", demand_hunter_definition)
    repo.create_version("demand-hunter", demand_hunter_definition)

    result = diff_versions("demand-hunter", 1, 2)
    assert result["diff"] == {"added": {}, "changed": {}, "removed": {}}
