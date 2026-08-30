def _register(api_client, definition: dict) -> None:
    api_client.post("/agents", json={"id": definition["id"], "name": definition["identity"]["name"]})
    resp = api_client.post("/agents/" + definition["id"] + "/versions", json={"definition": definition})
    assert resp.status_code == 201


def test_duplicate_endpoint(api_client, demand_hunter_definition):
    _register(api_client, demand_hunter_definition)

    resp = api_client.post(
        "/agents/demand-hunter/duplicate",
        json={"new_id": "lead-discovery", "new_name": "Lead Discovery",
              "overrides": {"goal": {"statement": "otro objetivo"}}},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "draft"
    assert body["definition"]["goal"]["statement"] == "otro objetivo"


def test_duplicate_of_unknown_agent_is_404(api_client):
    resp = api_client.post("/agents/no-existe/duplicate", json={"new_id": "x", "new_name": "X"})
    assert resp.status_code == 404


def test_promote_and_archive_endpoints(api_client, demand_hunter_definition):
    _register(api_client, demand_hunter_definition)
    edited = dict(demand_hunter_definition)
    edited["policies"]["budget"]["max_steps"] = 40
    api_client.post("/agents/demand-hunter/versions", json={"definition": edited, "activate": False})

    resp = api_client.post("/agents/demand-hunter/versions/2/promote")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"
    assert api_client.get("/agents/demand-hunter/versions/1").json()["status"] == "archived"

    resp = api_client.post("/agents/demand-hunter/versions/2/archive")
    assert resp.status_code == 200
    assert api_client.get("/agents/demand-hunter").json()["active_version_id"] is None


def test_diff_endpoint(api_client, demand_hunter_definition):
    _register(api_client, demand_hunter_definition)
    edited = dict(demand_hunter_definition)
    edited["policies"]["budget"]["max_steps"] = 40
    api_client.post("/agents/demand-hunter/versions", json={"definition": edited})

    resp = api_client.get("/agents/demand-hunter/versions/1/diff/2")
    assert resp.status_code == 200
    assert resp.json()["diff"]["changed"]["policies.budget.max_steps"] == {"from": 25, "to": 40}
