import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def auth_token():
    response = client.post('/login', data={"username": "test@email.com", "password": "test1234"})
    return response.json()["access_token"]


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


def test_protected_route_with_token(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/get_upload_data", headers=headers)
    assert response.status_code == 200


def test_upload_file(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post(
        "/files",
        headers=headers,
        files={"file": ("test.pdf", b"fake content", "application/pdf")}
    )
    assert response.status_code in [200, 201]


def test_user_isolation():
    client.post(
        "/register",
        json={"email": "edyas1hgj@mozmail.com", "password": "suman123"}
    )
    userA = client.post('/login', data={"username": "edyas1hgj@mozmail.com", "password": "suman123"})
    assert userA.status_code == 200
    token_a = userA.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    dummy_file = {"file": ("invoice.pdf", b"fake pdf content", "application/pdf")}
    upload_response = client.post("/files", headers=headers_a, files=dummy_file)
    assert upload_response.status_code in [200, 201]

    # Extract the uploaded file ID
    file_id = upload_response.json()["id"]

    # 2. Login as User B and attempt to access User A's file
    userB = client.post('/login', data={"username": "test@email.com", "password": "test1234"})
    assert userB.status_code == 200
    token_b = userB.json()["access_token"]
    userB_headers = {"Authorization": f"Bearer {token_b}"}

    # 3. Assert forbidden
    response = client.get(f"/files/{file_id}", headers=userB_headers)
    assert response.status_code == 403


def test_excel_export(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/invoices/export", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
