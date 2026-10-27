from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_register():
    response = client.post(
        "/register", json={"email": "test@email.com", "password": "test1234"}
    )
    assert response.status_code in [201, 409]


def test_login():
    response = client.post(
        "/login", data={"username": "test@email.com", "password": "test1234"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_protected_rout_no_token():
    response = client.get("/get_upload_data")
    assert response.status_code == 401


def test_protected_route_with_token():
    login_response = client.post(
        "/login", data={"username": "test@email.com", "password": "test1234"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/get_upload_data", headers=headers)
    assert response.status_code == 200
