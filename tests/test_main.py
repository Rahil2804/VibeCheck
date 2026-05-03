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


def test_preference_profile_endpoints_crud_and_default(monkeypatch):
    _test_sqlite_path(monkeypatch)
    client = TestClient(app)

    first_response = client.post(
        "/preference-profiles",
        json={
            "name": "Rahil",
            "car_reliance": "no_car",
            "top_priority": "transit_access",
            "must_haves": ["transit"],
        },
    )
    assert first_response.status_code == 200
    first = first_response.json()
    assert first["name"] == "Rahil"
    assert first["is_default"] is True

    second_response = client.post(
        "/preference-profiles",
        json={"name": "Budget-first", "budget_sensitivity": "very_budget_conscious"},
    )
    assert second_response.status_code == 200
    second = second_response.json()
    assert second["is_default"] is False

    list_response = client.get("/preference-profiles")
    assert list_response.status_code == 200
    assert [profile["id"] for profile in list_response.json()] == [first["id"], second["id"]]

    update_response = client.put(
        f"/preference-profiles/{second['id']}",
        json={"name": "Budget and transit", "must_haves": ["transit", "lower_rent_pressure"]},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Budget and transit"
    assert updated["must_haves"] == ["transit", "lower_rent_pressure"]

    default_response = client.post(f"/preference-profiles/{second['id']}/default")
    assert default_response.status_code == 200
    assert default_response.json()["is_default"] is True

    get_response = client.get(f"/preference-profiles/{second['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["is_default"] is True

    delete_response = client.delete(f"/preference-profiles/{first['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}

    missing_response = client.get(f"/preference-profiles/{first['id']}")
    assert missing_response.status_code == 404


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


def test_cors_allows_preference_profile_update_from_local_vite():
    client = TestClient(app)

    response = client.options(
        "/preference-profiles/example",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PUT",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_analyze_uses_selected_preference_profile(monkeypatch):
    _test_sqlite_path(monkeypatch)
    client = TestClient(app)
    profile_response = client.post(
        "/preference-profiles",
        json={
            "name": "Transit profile",
            "car_reliance": "no_car",
            "top_priority": "transit_access",
            "generic_mode": False,
        },
    )
    assert profile_response.status_code == 200
    profile_id = profile_response.json()["id"]

    generic_response = client.post(
        "/analyze",
        json={"query": "East Austin", "preference_profile_id": profile_id, "generic_mode": True},
    )

    assert generic_response.status_code == 200
    body = generic_response.json()
    assert body["fit"] is not None


def test_analyze_returns_404_for_missing_preference_profile(monkeypatch):
    _test_sqlite_path(monkeypatch)
    client = TestClient(app)

    response = client.post(
        "/analyze",
        json={"query": "East Austin", "preference_profile_id": "missing-profile"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Preference profile not found."
