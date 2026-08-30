from aap.core.definition import repository as repo
from aap.core.llm.providers.mock import MockProvider
from aap.core.runtime.runs import create_run, get_run
from aap.domain.entities import query_entities
from aap.worker.main import process_one_queued_run
from tests.conftest import make_scripted_router


def test_process_one_queued_run_returns_false_when_nothing_to_do():
    router = make_scripted_router(MockProvider())
    assert process_one_queued_run(router) is False


def test_process_one_queued_run_executes_l0_agent_end_to_end(l0_agent_definition):
    repo.create_agent("l0-demo", "L0 Demo")
    version = repo.create_version("l0-demo", l0_agent_definition)
    run = create_run("l0-demo", version["id"], input_data={"sector": "logistica"})
    assert run["status"] == "queued"

    router = make_scripted_router(MockProvider())  # nunca se llama: L0 no usa LLM
    did_work = process_one_queued_run(router)

    assert did_work is True
    finished = get_run(run["id"])
    assert finished["status"] == "completed"
    assert query_entities("signals")[0]["natural_key"] == "rutasdelsur.mock:l0-demo"


def test_process_one_queued_run_only_claims_one_at_a_time(l0_agent_definition):
    repo.create_agent("l0-demo", "L0 Demo")
    version = repo.create_version("l0-demo", l0_agent_definition)
    run_a = create_run("l0-demo", version["id"])
    run_b = create_run("l0-demo", version["id"])

    router = make_scripted_router(MockProvider())
    process_one_queued_run(router)

    a, b = get_run(run_a["id"]), get_run(run_b["id"])
    statuses = {a["status"], b["status"]}
    assert statuses == {"completed", "queued"}


def test_a_crashing_run_does_not_stop_the_worker(demand_hunter_definition):
    d = dict(demand_hunter_definition)
    d["runtime"] = {"autonomy_level": 4}  # no soportado -> crashed
    repo.create_agent("demand-hunter", "Demand Hunter")
    version = repo.create_version("demand-hunter", d)
    run = create_run("demand-hunter", version["id"])

    router = make_scripted_router(MockProvider())
    did_work = process_one_queued_run(router)  # no debe propagar la excepción

    assert did_work is True
    assert get_run(run["id"])["status"] == "crashed"
