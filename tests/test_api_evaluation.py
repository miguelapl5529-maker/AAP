def _register(api_client, definition: dict) -> None:
    api_client.post("/agents", json={"id": definition["id"], "name": definition["identity"]["name"]})
    resp = api_client.post("/agents/" + definition["id"] + "/versions", json={"definition": definition})
    assert resp.status_code == 201


def test_metrics_endpoint_on_active_version_with_no_runs(api_client, demand_hunter_definition):
    _register(api_client, demand_hunter_definition)
    resp = api_client.get("/agents/demand-hunter/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 1
    assert body["metrics"]["total_runs"] == 0
    assert body["evaluations"] == []


def test_metrics_endpoint_reflects_real_runs(api_client, demand_hunter_definition):
    _register(api_client, demand_hunter_definition)
    api_client.post("/agents/demand-hunter/runs", json={})
    resp = api_client.get("/agents/demand-hunter/metrics")
    assert resp.json()["metrics"]["total_runs"] == 1


def test_metrics_endpoint_for_a_specific_version(api_client, demand_hunter_definition):
    _register(api_client, demand_hunter_definition)
    edited = dict(demand_hunter_definition)
    edited["policies"]["budget"]["max_steps"] = 40
    api_client.post("/agents/demand-hunter/versions", json={"definition": edited, "activate": False})

    resp = api_client.get("/agents/demand-hunter/metrics", params={"version": 2})
    assert resp.status_code == 200
    assert resp.json()["version"] == 2


def test_metrics_of_unknown_agent_is_404(api_client):
    assert api_client.get("/agents/no-existe/metrics").status_code == 404


def test_compare_endpoint(api_client, demand_hunter_definition):
    _register(api_client, demand_hunter_definition)
    api_client.post("/agents/demand-hunter/versions", json={"definition": demand_hunter_definition})

    resp = api_client.get("/agents/demand-hunter/compare", params={"a": 1, "b": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["a"]["version"] == 1
    assert body["b"]["version"] == 2
