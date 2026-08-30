"""La UI es estática (HTML/CSS/JS sin build, §15.1): esto solo confirma
que la API la sirve donde toca. El comportamiento real —formularios,
polling, el Run Inspector— se verificó a mano en un navegador real
(no es razonable simularlo con pytest)."""

from fastapi.testclient import TestClient

from aap.api.main import app


def test_root_redirects_to_ui():
    client = TestClient(app, follow_redirects=False)
    resp = client.get("/")
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/ui/"


def test_ui_index_is_served():
    client = TestClient(app)
    resp = client.get("/ui/")
    assert resp.status_code == 200
    assert "AAP" in resp.text
    assert "<script src=\"app.js\">" in resp.text


def test_ui_static_assets_are_served():
    client = TestClient(app)
    assert client.get("/ui/style.css").status_code == 200
    assert client.get("/ui/app.js").status_code == 200
    assert client.get("/ui/create.html").status_code == 200
    assert client.get("/ui/agent.html").status_code == 200
    assert client.get("/ui/run.html").status_code == 200
