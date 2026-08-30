from aap.core.definition import repository as repo
from aap.core.evaluation.compare import compare_versions_by_metrics
from aap.core.runtime.runs import create_run, finish_run


def test_compare_versions_shows_a_real_regression(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    v1 = repo.create_version("demand-hunter", demand_hunter_definition)
    v2 = repo.create_version("demand-hunter", demand_hunter_definition)  # misma config, otra versión

    for _ in range(3):
        r = create_run("demand-hunter", v1["id"])
        finish_run(r["id"], status="completed", termination_reason="completed")

    for _ in range(3):
        r = create_run("demand-hunter", v2["id"])
        finish_run(r["id"], status="failed", termination_reason="failed")

    report = compare_versions_by_metrics("demand-hunter", 1, 2)
    assert report["a"]["metrics"]["completion_rate"] == 1.0
    assert report["b"]["metrics"]["completion_rate"] == 0.0
    assert report["delta"]["completion_rate"] == -1.0
    assert report["delta"]["failure_rate"] == 1.0


def test_compare_versions_with_no_runs_yet_has_no_delta(demand_hunter_definition):
    repo.create_agent("demand-hunter", "Demand Hunter")
    repo.create_version("demand-hunter", demand_hunter_definition)
    repo.create_version("demand-hunter", demand_hunter_definition)

    report = compare_versions_by_metrics("demand-hunter", 1, 2)
    assert report["a"]["metrics"]["total_runs"] == 0
    assert report["delta"] == {}
