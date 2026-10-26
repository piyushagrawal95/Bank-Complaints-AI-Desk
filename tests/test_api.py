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
    assert "8 characters" in res.json()["detail"]


def test_signup_password_complexity(client):
    # Missing uppercase
    r1 = client.post("/auth/signup", json={"email": "u1@bank.com", "password": "password1@"})
    assert r1.status_code == 422
    assert "uppercase" in r1.json()["detail"].lower()

    # Missing lowercase
    r2 = client.post("/auth/signup", json={"email": "u2@bank.com", "password": "PASSWORD1@"})
    assert r2.status_code == 422
    assert "lowercase" in r2.json()["detail"].lower()

    # Missing digit
    r3 = client.post("/auth/signup", json={"email": "u3@bank.com", "password": "Password@@"})
    assert r3.status_code == 422
    assert "number" in r3.json()["detail"].lower() or "digit" in r3.json()["detail"].lower()

    # Missing special character
    r4 = client.post("/auth/signup", json={"email": "u4@bank.com", "password": "Password123"})
    assert r4.status_code == 422
    assert "special character" in r4.json()["detail"].lower()


def test_captcha_challenge_and_verification(client):
    # 1. Fetch challenge
    res = client.get("/auth/captcha")
    assert res.status_code == 200
    data = res.json()
    assert "question" in data
    assert "captcha_token" in data

    # 2. Reject missing captcha/turnstile on login
    r_missing = client.post("/auth/login", json={"email": "nobody@bank.com", "password": "Password123@"})
    assert r_missing.status_code == 400
    assert "Security verification" in r_missing.json()["detail"]

    # 3. Reject invalid captcha answer
    r_invalid = client.post("/auth/login", json={
        "email": "nobody@bank.com",
        "password": "Password123@",
        "captcha_token": data["captcha_token"],
        "captcha_answer": "wrong_ans_999",
    })
    assert r_invalid.status_code == 400
    assert "Incorrect CAPTCHA answer" in r_invalid.json()["detail"]

    # 4. Turnstile token verification
    r_turnstile = client.post("/auth/login", json={
        "email": "nonexistent@bank.com",
        "password": "WrongPassword123",
        "turnstile_token": "TEST_CAPTCHA_BYPASS",
    })
    assert r_turnstile.status_code == 401


def test_login_invalid_credentials(client):
    res = client.post("/auth/login", json={
        "email": "nonexistent@bank.com",
        "password": "WrongPassword123",
        "captcha_token": "TEST_CAPTCHA_BYPASS",
        "captcha_answer": "bypass",
    })
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



def get_admin_user():
    from app.core.config import settings
    from app.db import pool
    super_admin = (settings.super_admin_email or "piyushagrawal300504@gmail.com").strip().lower()
    with pool.connection() as conn:
        u = conn.execute("SELECT id, email, role FROM users WHERE email = %s", [super_admin]).fetchone()
        if not u:
            u = conn.execute("SELECT id, email, role FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        if not u:
            u = conn.execute("INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, 'dummy_hash', 'admin', true) RETURNING id, email, role", [super_admin]).fetchone()
        return u

def get_agent_user():
    from app.db import pool
    with pool.connection() as conn:
        u = conn.execute("SELECT id, email, role FROM users WHERE role = 'agent' LIMIT 1").fetchone()
        if not u:
            u = conn.execute("INSERT INTO users (email, password_hash, role, is_active) VALUES ('test_agent@bank.com', 'dummy_hash', 'agent', true) RETURNING id, email, role").fetchone()
        return u

def test_permanent_admin_protection(client):
    from app.security import create_access_token
    admin = get_admin_user()
    admin_token = create_access_token(user_id=admin["id"], role="admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Attempt to demote root super admin
    res = client.put(
        "/auth/users/role",
        headers=headers,
        json={"user_id": admin["id"], "role": "agent"},
    )
    assert res.status_code == 403
    assert "cannot be modified or demoted" in res.json()["detail"]


def test_complaints_list_authenticated(client):
    from app.security import create_access_token
    admin = get_admin_user()
    token = create_access_token(user_id=admin["id"], role="admin")
    res = client.get("/complaints?page=1&page_size=5", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) == 5
    assert "total" in data


def test_trends_spikes_rbac(client):
    from app.security import create_access_token
    admin = get_admin_user()
    agent = get_agent_user()
    agent_token = create_access_token(user_id=agent["id"], role="agent")
    res_agent = client.get("/trends/spikes", headers={"Authorization": f"Bearer {agent_token}"})
    assert res_agent.status_code == 403

    admin_token = create_access_token(user_id=admin["id"], role="admin")
    res_admin = client.get("/trends/spikes", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    assert "items" in res_admin.json()


def test_similar_complaints_search(client):
    from app.security import create_access_token
    from app.db import pool
    with pool.connection() as conn:
        row = conn.execute("SELECT complaint_id FROM complaint_embeddings LIMIT 1").fetchone()
        cid = row["complaint_id"] if row else 1743702
    admin = get_admin_user()
    token = create_access_token(user_id=admin["id"], role="admin")
    res = client.get(f"/complaints/{cid}/similar?top_k=3", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "similar" in data
    assert len(data["similar"]) > 0
    assert "similarity" in data["similar"][0]



