"""API tests for aidev.server using FastAPI's TestClient."""

import pytest
from fastapi.testclient import TestClient

import aidev.server as server_module
from aidev.server import API_PORT, DEV_ORIGINS, app
from aidev.storage import TraceSQLite


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient with an isolated temp database.

    The lifespan handler (re)initializes module storage on portal entry,
    so the temp store is injected *after* entering the client context.
    """
    store = TraceSQLite(str(tmp_path / "api.db"))
    with TestClient(app) as c:
        monkeypatch.setattr(server_module, "storage", store)
        yield c
    store.close()


def test_list_spans_empty(client):
    resp = client.get("/api/spans")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_and_get_span(client):
    created = client.post("/api/spans", json={"name": "agent"}).json()
    assert created["name"] == "agent"
    assert created["status"] == "ok"
    assert created["parent_id"] is None

    fetched = client.get(f"/api/spans/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_create_child_span_uses_parent_id(client):
    parent = client.post("/api/spans", json={"name": "parent"}).json()
    child = client.post("/api/spans", json={"name": "child", "parent_id": parent["id"]}).json()
    assert child["parent_id"] == parent["id"]

    spans = {s["id"]: s for s in client.get("/api/spans").json()}
    assert set(spans) == {parent["id"], child["id"]}


def test_get_span_404(client):
    resp = client.get("/api/spans/missing")
    assert resp.status_code == 404


def test_storage_uninitialized_returns_500(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as c:
        monkeypatch.setattr(server_module, "storage", None)
        resp = c.get("/api/spans")
    assert resp.status_code == 500


def test_cors_allows_dev_origin_but_not_arbitrary(client):
    allowed = client.options(
        "/api/spans",
        headers={
            "Origin": DEV_ORIGINS[0],
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == DEV_ORIGINS[0]

    denied = client.options(
        "/api/spans",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in denied.headers


def test_canonical_api_port():
    assert API_PORT == 18003
