def test_create_and_get_agent(api_client):
    resp = api_client.post("/agents", json={"id": "demo", "name": "Demo", "owner": "miguel"})
    assert resp.status_code == 201
    assert resp.json()["id"] == "demo"

    resp = api_client.get("/agents/demo")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Demo"


def test_get_unknown_agent_is_404(api_client):
    resp = api_client.get("/agents/no-existe")
    assert resp.status_code == 404


def test_duplicate_agent_is_409(api_client):
    api_client.post("/agents", json={"id": "demo", "name": "Demo"})
    resp = api_client.post("/agents", json={"id": "demo", "name": "Otro"})
    assert resp.status_code == 409


def test_list_agents(api_client):
    api_client.post("/agents", json={"id": "a", "name": "A"})
    api_client.post("/agents", json={"id": "b", "name": "B"})
    resp = api_client.get("/agents")
    assert resp.status_code == 200
    assert {a["id"] for a in resp.json()} == {"a", "b"}


def test_create_version_validates_and_activates(api_client, demand_hunter_definition):
    api_client.post("/agents", json={"id": "demand-hunter", "name": "Demand Hunter"})
    resp = api_client.post(
        "/agents/demand-hunter/versions",
        json={"definition": demand_hunter_definition, "created_by": "miguel"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["version"] == 1
    assert body["status"] == "active"

    agent = api_client.get("/agents/demand-hunter").json()
    assert agent["active_version_id"] == body["id"]


def test_create_version_with_invalid_definition_is_422(api_client, demand_hunter_definition):
    api_client.post("/agents", json={"id": "demand-hunter", "name": "Demand Hunter"})
    del demand_hunter_definition["policies"]["budget"]
    resp = api_client.post("/agents/demand-hunter/versions", json={"definition": demand_hunter_definition})
    assert resp.status_code == 422
    assert "errors" in resp.json()


def test_list_and_get_version(api_client, demand_hunter_definition):
    api_client.post("/agents", json={"id": "demand-hunter", "name": "Demand Hunter"})
    api_client.post("/agents/demand-hunter/versions", json={"definition": demand_hunter_definition})

    resp = api_client.get("/agents/demand-hunter/versions")
    assert len(resp.json()) == 1

    resp = api_client.get("/agents/demand-hunter/versions/1")
    assert resp.status_code == 200
    assert resp.json()["version"] == 1


def test_versions_of_unknown_agent_is_404(api_client):
    resp = api_client.get("/agents/no-existe/versions")
    assert resp.status_code == 404


def test_validate_endpoint_does_not_persist_anything(api_client, demand_hunter_definition):
    resp = api_client.post("/definitions/validate", json=demand_hunter_definition)
    assert resp.status_code == 200
    assert resp.json()["valid"] is True

    # nada se guardó: el agente no existe
    assert api_client.get("/agents/demand-hunter").status_code == 404


def test_validate_endpoint_rejects_invalid_definition(api_client, demand_hunter_definition):
    demand_hunter_definition["runtime"]["autonomy_level"] = 9
    resp = api_client.post("/definitions/validate", json=demand_hunter_definition)
    assert resp.status_code == 422


def test_schema_endpoint_returns_json_schema(api_client):
    resp = api_client.get("/schema/agent-definition")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["title"] == "AgentDefinition"
    assert "properties" in schema
