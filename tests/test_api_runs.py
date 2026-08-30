def _register_agent(api_client, definition: dict) -> None:
    api_client.post("/agents", json={"id": definition["id"], "name": definition["identity"]["name"]})
    resp = api_client.post("/agents/" + definition["id"] + "/versions", json={"definition": definition})
    assert resp.status_code == 201


def test_trigger_run_returns_202_and_queued_status(api_client, l0_agent_definition):
    _register_agent(api_client, l0_agent_definition)

    resp = api_client.post("/agents/l0-demo/runs", json={"input": {"sector": "logistica"}})
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"

    run = api_client.get(f"/runs/{body['run_id']}").json()
    assert run["status"] == "queued"
    assert run["input"] == {"sector": "logistica"}
    assert run["agent_id"] == "l0-demo"


def test_trigger_run_for_unknown_agent_is_404(api_client):
    resp = api_client.post("/agents/no-existe/runs", json={})
    assert resp.status_code == 404


def test_get_unknown_run_is_404(api_client):
    assert api_client.get("/runs/no-existe").status_code == 404
    assert api_client.get("/runs/no-existe/events").status_code == 404
    assert api_client.get("/runs/no-existe/tool_calls").status_code == 404


def test_run_state_before_execution_is_empty(api_client, l0_agent_definition):
    _register_agent(api_client, l0_agent_definition)
    run_id = api_client.post("/agents/l0-demo/runs", json={}).json()["run_id"]

    state = api_client.get(f"/runs/{run_id}/state").json()
    assert state["state"] == {}


def test_list_runs_filters_by_agent_and_status(api_client, l0_agent_definition):
    _register_agent(api_client, l0_agent_definition)
    r1 = api_client.post("/agents/l0-demo/runs", json={}).json()["run_id"]
    r2 = api_client.post("/agents/l0-demo/runs", json={}).json()["run_id"]

    runs = api_client.get("/runs", params={"agent_id": "l0-demo"}).json()
    assert {r["id"] for r in runs} == {r1, r2}

    runs = api_client.get("/runs", params={"agent_id": "l0-demo", "status": "queued"}).json()
    assert {r["id"] for r in runs} == {r1, r2}

    runs = api_client.get("/runs", params={"agent_id": "l0-demo", "status": "completed"}).json()
    assert runs == []


def test_trigger_run_defaults_to_active_version(api_client, demand_hunter_definition):
    _register_agent(api_client, demand_hunter_definition)
    resp = api_client.post("/agents/demand-hunter/runs", json={})
    assert resp.status_code == 202

    run = api_client.get(f"/runs/{resp.json()['run_id']}").json()
    agent = api_client.get("/agents/demand-hunter").json()
    assert run["agent_version_id"] == agent["active_version_id"]
