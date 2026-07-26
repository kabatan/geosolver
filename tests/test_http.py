from fastapi.testclient import TestClient

from geotarget.api import app


def test_catalog_and_preview_share_v15_contract(problem: dict) -> None:
    with TestClient(app) as client:
        catalog = client.get("/api/v1/dsl/catalog")
        assert catalog.status_code == 200
        assert any(tool["id"] == "PointOnCircle" for tool in catalog.json()["tools"])
        assert client.post("/api/v1/preview", json=problem).status_code == 403
        assert client.get("/api/v1/session").status_code == 200
        preview = client.post("/api/v1/preview", json=problem)
        assert preview.status_code == 200
        assert preview.json()["validation"]["valid"] is True
