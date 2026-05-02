from fastapi.testclient import TestClient

from backend.main import app


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
