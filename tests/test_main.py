from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import app


def _test_sqlite_path(monkeypatch) -> Path:
    directory = Path(".test-data")
    directory.mkdir(exist_ok=True)
    db_path = directory / f"api-{uuid4()}.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    return db_path


def test_health_returns_ok():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_returns_partial_profile_for_valid_query():
    client = TestClient(app)

    response = client.post("/analyze", json={"query": "East Austin"})

    assert response.status_code == 200
    body = response.json()
    assert body["place"]["label"] == "East Austin"
    assert body["confidence"]["level"] in {"low", "medium", "high", "none"}
    assert len(body["source_statuses"]) >= 4


def test_profile_endpoints_save_list_read_and_delete(monkeypatch):
    _test_sqlite_path(monkeypatch)
    client = TestClient(app)
    analyze_response = client.post("/analyze", json={"query": "East Austin"})
    assert analyze_response.status_code == 200

    save_response = client.post("/profiles", json=analyze_response.json())
    assert save_response.status_code == 200
    saved = save_response.json()
    profile_id = saved["id"]
    assert saved["place_label"] == "East Austin"
    assert saved["response"]["place"]["label"] == "East Austin"

    list_response = client.get("/profiles")
    assert list_response.status_code == 200
    summaries = list_response.json()
    assert summaries[0]["id"] == profile_id
    assert "response" not in summaries[0]

    get_response = client.get(f"/profiles/{profile_id}")
    assert get_response.status_code == 200
    assert get_response.json()["response"]["place"]["label"] == "East Austin"

    delete_response = client.delete(f"/profiles/{profile_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}

    missing_response = client.get(f"/profiles/{profile_id}")
    assert missing_response.status_code == 404


def test_delete_missing_profile_returns_404(monkeypatch):
    _test_sqlite_path(monkeypatch)
    client = TestClient(app)

    response = client.delete("/profiles/missing-id")

    assert response.status_code == 404


def test_cors_allows_local_vite_origin():
    client = TestClient(app)

    response = client.options(
        "/analyze",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
