from fastapi.testclient import TestClient

from geosolver.application.http import app


def test_http_session_catalog_and_preview_use_geosolver_contract() -> None:
    client = TestClient(app)
    assert client.get("/api/v1/session").status_code == 200
    catalog = client.get("/api/v1/dsl/catalog").json()
    assert catalog["schema_version"] == 1
    assert all(not tool["id"].startswith("Assume") for tool in catalog["tools"])

    response = client.post(
        "/api/v1/preview",
        json={
            "id": "api",
            "variables": ["x"],
            "constructions": [],
            "conditions": [{"left": "x", "operator": "=", "right": 1}],
            "target": "x",
        },
    )
    assert response.status_code == 200
    assert response.json()["validation"]["valid"] is True


def test_capabilities_do_not_silently_alias_reference() -> None:
    payload = TestClient(app).get("/api/v1/capabilities").json()
    assert payload["default_engine"] == "standard"
    assert set(payload["engines"]) == {"standard", "reference"}
