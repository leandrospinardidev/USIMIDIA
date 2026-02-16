from fastapi.testclient import TestClient

from main import app


def test_admin_check_requires_role_header() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/cadastro/admin-check")

    assert response.status_code == 401
    assert response.json()["error"] == "http_error"


def test_admin_check_allows_admin_role() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/cadastro/admin-check", headers={"X-User-Role": "admin"})

    assert response.status_code == 200
    assert response.json() == {"access": "granted"}
