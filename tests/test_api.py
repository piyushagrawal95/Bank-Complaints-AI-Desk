"""Automated integration tests for Bank Complaint AI API."""
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_complaints_unauthorized(client):
    res = client.get("/complaints")
    assert res.status_code == 401


def test_signup_validation(client):
    res = client.post("/auth/signup", json={"email": "test_invalid@bank.com", "password": "123"})
    assert res.status_code == 422


def test_login_invalid_credentials(client):
    res = client.post("/auth/login", json={"email": "nonexistent@bank.com", "password": "WrongPassword123"})
    assert res.status_code == 401


def test_forgot_password_flow(client):
    res = client.post("/auth/forgot-password", json={"email": "nobody@bank.com"})
    assert res.status_code == 200
    assert "link has been issued" in res.json()["message"]


def test_google_login_invalid(client):
    res = client.post("/auth/google", json={"credential": "invalid_jwt_token"})
    assert res.status_code == 401
    assert "Google authentication failed" in res.json()["detail"]


def test_google_login_mock_token(client):
    import time
    import jwt
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": "https://accounts.google.com",
            "aud": "639319834126-b1ouen3no25o2elim13idbab182m3tjd.apps.googleusercontent.com",
            "email": "test_google_runner@bank.com",
            "name": "Test Google Runner",
            "iat": now,
            "exp": now + 3600,
        },
        "mock_secret_key_that_is_at_least_32_bytes_long",
        algorithm="HS256",
    )
    res = client.post("/auth/google", json={"credential": token})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test_google_runner@bank.com"


def test_permanent_admin_protection(client):
    from app.security import create_access_token
    # Admin token
    admin_token = create_access_token(user_id=26, role="admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Attempt to demote user 11 (piyushagrawal300504@gmail.com)
    res = client.put(
        "/auth/users/role",
        headers=headers,
        json={"user_id": 26, "role": "agent"},
    )
    assert res.status_code == 403
    assert "cannot be modified or demoted" in res.json()["detail"]


def test_complaints_list_authenticated(client):
    from app.security import create_access_token
    token = create_access_token(user_id=26, role="admin")
    res = client.get("/complaints?page=1&page_size=5", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) == 5
    assert "total" in data


def test_trends_spikes_rbac(client):
    from app.security import create_access_token
    agent_token = create_access_token(user_id=12, role="agent")
    res_agent = client.get("/trends/spikes", headers={"Authorization": f"Bearer {agent_token}"})
    assert res_agent.status_code == 403

    admin_token = create_access_token(user_id=26, role="admin")
    res_admin = client.get("/trends/spikes", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    assert "items" in res_admin.json()


def test_similar_complaints_search(client):
    from app.security import create_access_token
    token = create_access_token(user_id=26, role="admin")
    res = client.get("/complaints/2026100000/similar?top_k=3", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "similar" in data
    assert len(data["similar"]) > 0
    assert "similarity" in data["similar"][0]



