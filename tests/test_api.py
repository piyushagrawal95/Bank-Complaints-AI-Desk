import os
os.environ["TESTING"] = "1"
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

    # 3. Reject math captcha fallback (enforces Cloudflare Turnstile)
    r_invalid = client.post("/auth/login", json={
        "email": "nobody@bank.com",
        "password": "Password123@",
        "captcha_token": data["captcha_token"],
        "captcha_answer": "wrong_ans_999",
    })
    assert r_invalid.status_code == 400
    assert "Cloudflare Turnstile" in r_invalid.json()["detail"] or "no longer supported" in r_invalid.json()["detail"]

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
    from unittest.mock import patch
    with patch("google.oauth2.id_token.verify_oauth2_token", return_value={"email": "test_google_runner@bank.com", "name": "Test Google Runner", "email_verified": True}):
        res = client.post("/auth/google", json={"credential": "mock_valid_google_token"})
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





def test_complaint_creation_and_approval_workflow(client):
    import uuid
    from app.security import create_access_token
    agent = get_agent_user()
    admin = get_admin_user()
    agent_token = create_access_token(user_id=agent["id"], role="agent")
    admin_token = create_access_token(user_id=admin["id"], role="admin")
    test_email = f"consumer.test.{uuid.uuid4().hex[:8]}@example.com"

    # 1. Agent creates complaint
    res_create = client.post(
        "/complaints/create",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={
            "product": "Credit card or prepaid card",
            "issue": "Dispute on unauthorized fee",
            "company": "JPMorgan Chase & Co.",
            "consumer_email": test_email,
            "narrative": "Unauthorized monthly maintenance fee was deducted from my account without disclosure.",
        },
    )
    assert res_create.status_code == 200
    complaint_data = res_create.json()["complaint"]
    cid = complaint_data["complaint_id"]
    assert complaint_data["consumer_email"] == test_email

    # 2. Agent submits draft for approval
    res_req = client.post(
        f"/complaints/{cid}/request-approval",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={"response_text": "We have credited your account back $25 as a courtesy."},
    )
    assert res_req.status_code == 200
    assert res_req.json()["status"] == "pending_approval"

    # 3. Agent is forbidden from self-approving
    res_agent_app = client.post(
        f"/complaints/{cid}/approve",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={"response_text": "Illegal self-approval attempt."},
    )
    assert res_agent_app.status_code == 403

    # 4. Admin successfully approves
    res_admin_app = client.post(
        f"/complaints/{cid}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"response_text": "We have investigated your dispute and issued a full fee refund."},
    )
    assert res_admin_app.status_code == 200
    assert res_admin_app.json()["status"] == "approved"
    assert "email_dispatched" in res_admin_app.json()


def test_complaint_file_extraction(client):
    from app.security import create_access_token
    agent = get_agent_user()
    token = create_access_token(user_id=agent["id"], role="agent")
    sample_text = (
        b"DISPUTE SUBMISSION\n"
        b"Consumer: Alice Smith\n"
        b"Email: alice.smith@finance.org\n"
        b"Bank: Citibank, N.A.\n"
        b"State: TX\n"
        b"Issue: Fraudulent ATM withdrawal\n"
        b"Narrative: An unknown withdrawal of $200 took place at an ATM in Houston while I had my physical card."
    )
    res = client.post(
        "/complaints/extract-file",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("complaint_dispute.txt", sample_text, "text/plain")},
    )
    assert res.status_code == 200
    extracted = res.json()["extracted"]
    assert extracted["consumer_email"] == "alice.smith@finance.org"
    assert extracted["state"] == "TX"
    assert "Checking or savings account" in extracted["product"] or "Credit card" in extracted["product"]
# -------------------------------------------------------------
# STRIPE BILLING & SUBSCRIPTION INTEGRATION TESTS
# -------------------------------------------------------------

def test_billing_unauthorized(client):
    r1 = client.get("/billing/status")
    assert r1.status_code == 401
    r2 = client.post("/billing/checkout")
    assert r2.status_code == 401
    r3 = client.post("/billing/portal")
    assert r3.status_code == 401
    r4 = client.post("/billing/sync")
    assert r4.status_code == 401


def test_billing_config(client):
    from app.security import create_access_token
    agent = get_agent_user()
    token = create_access_token(user_id=agent["id"], role="agent")
    res = client.get("/billing/config", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "configured" in data
    assert data["plan_name"] == "AI Pro Plan"
    assert data["amount"] == 500
    assert data["currency"].upper() == "INR"


def test_billing_status_authorized(client):
    from app.security import create_access_token
    agent = get_agent_user()
    token = create_access_token(user_id=agent["id"], role="agent")
    res = client.get("/billing/status", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "plan" in data
    assert data["plan"] in ("free", "pro")


def test_billing_webhook_security(client):
    # Missing or invalid stripe-signature should be immediately rejected
    res = client.post(
        "/billing/webhook",
        headers={"stripe-signature": "t=123,v1=invalid_fake_sig"},
        content=b'{"id": "evt_test", "type": "checkout.session.completed"}',
    )
    assert res.status_code in (400, 503)


def get_isolated_test_user():
    from app.db import pool
    with pool.connection() as conn:
        u = conn.execute("SELECT id, email, role FROM users WHERE email = 'test_isolated_billing@bank.com'").fetchone()
        if not u:
            u = conn.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES ('test_isolated_billing@bank.com', 'dummy_hash', 'agent', true) RETURNING id, email, role"
            ).fetchone()
        return u


def test_billing_checkout_and_portal_mocked(client):
    from unittest.mock import patch, MagicMock
    from app.security import create_access_token
    from app.core.config import settings
    from app.db import pool

    user = get_isolated_test_user()
    token = create_access_token(user_id=user["id"], role="agent")

    mock_cust = MagicMock(id="cus_test_mock_isolated")
    mock_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test_mock")
    mock_portal = MagicMock(url="https://billing.stripe.com/p/session/test_mock")

    # Clean previous test subscription data
    with pool.connection() as conn:
        conn.execute("DELETE FROM subscriptions WHERE user_id = %s", [user["id"]])

    with patch.object(settings, "stripe_secret_key", "sk_test_mock_for_ci"),          patch.object(settings, "stripe_price_id", "price_mock_for_ci"),          patch("stripe.Customer.create", return_value=mock_cust),          patch("stripe.checkout.Session.create", return_value=mock_session),          patch("stripe.billing_portal.Session.create", return_value=mock_portal):

        # 1. Checkout session test
        r_checkout = client.post(
            "/billing/checkout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r_checkout.status_code == 200
        assert r_checkout.json()["url"] == "https://checkout.stripe.com/pay/cs_test_mock"

        # 2. Portal session test
        r_portal = client.post(
            "/billing/portal",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r_portal.status_code == 200
        assert r_portal.json()["url"] == "https://billing.stripe.com/p/session/test_mock"

    # Cleanup isolated test data so real database is never polluted
    with pool.connection() as conn:
        conn.execute("DELETE FROM subscriptions WHERE user_id = %s", [user["id"]])


def test_pro_gating_enforcement(client):
    from app.security import create_access_token
    from app.db import pool

    # Free agent without Pro subscription
    user = get_isolated_test_user()
    with pool.connection() as conn:
        conn.execute("DELETE FROM subscriptions WHERE user_id = %s", [user["id"]])

    token = create_access_token(user_id=user["id"], role="agent")

    # 1. Draft reply should be rejected with 402 Payment Required
    r_draft = client.post(
        "/complaints/1/draft-reply",
        headers={"Authorization": f"Bearer {token}"},
        json={"custom_instructions": "Test instructions"},
    )
    assert r_draft.status_code == 402
    assert "Pro Plan subscription" in r_draft.json()["detail"]

    # 2. Ask Regulations should be rejected with 402 Payment Required
    r_ask = client.post(
        "/regulations/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "What is the timeline for error resolution?"},
    )
    assert r_ask.status_code == 402
    assert "Pro Plan subscription" in r_ask.json()["detail"]

    # 3. AI Analysis should be rejected with 402 Payment Required
    r_analysis = client.post(
        "/complaints/1/analysis",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_analysis.status_code == 402
    assert "Pro Plan subscription" in r_analysis.json()["detail"]
