"""
Iteration 28 backend regression tests.

Focus: referral program (backend endpoints), CORS hardening,
health endpoint, and register/auth-me flow with referral_by tracking.
"""

import os
import time
import requests
import pytest


def _load_base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if v:
        return v.rstrip("/")
    # Fallback: read from /app/frontend/.env
    try:
        with open("/app/frontend/.env", "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE_URL = _load_base_url()
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@videostudio.ai"
ADMIN_PASSWORD = "Admin@2026"


# ------------ helpers ------------
def _fresh_email(prefix="referral_test"):
    return f"{prefix}_{int(time.time()*1000)}@example.com"


def _register(session, email, password="secret123", name="Ref Tester", referral_code=None):
    body = {"name": name, "identifier": email, "password": password}
    if referral_code is not None:
        body["referral_code"] = referral_code
    return session.post(f"{API}/auth/register", json=body)


def _login(session, email, password):
    return session.post(f"{API}/auth/login", json={"identifier": email, "password": password})


# ------------ fixtures ------------
@pytest.fixture
def admin_session():
    s = requests.Session()
    r = _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


# ------------ health ------------
class TestHealth:
    def test_health_returns_ok_with_checks(self):
        r = requests.get(f"{API}/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        checks = data.get("checks") or {}
        assert checks.get("mongodb") == "ok"
        assert checks.get("ffmpeg") == "ok"
        assert checks.get("llm_key") == "ok"


# ------------ CORS ------------
class TestCORS:
    def test_options_preflight_ok(self):
        r = requests.options(
            f"{API}/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        # Should be 200 or 204; not 5xx
        assert r.status_code in (200, 204), f"Preflight failed: {r.status_code}"

    def test_service_reachable_after_cors_init(self):
        # If backend crashed on wildcard, /api/health would fail
        r = requests.get(f"{API}/health")
        assert r.status_code == 200


# ------------ referrals ------------
class TestReferralsAdmin:
    def test_admin_referral_endpoint_shape(self, admin_session):
        r = admin_session.get(f"{API}/referrals/me")
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("code", "share_url", "invited_count", "credits_earned", "bonus_per_referral"):
            assert k in data, f"Missing {k} in {data}"
        assert isinstance(data["code"], str) and len(data["code"]) >= 6
        assert "/signup?ref=" in data["share_url"]
        assert data["bonus_per_referral"] == 3
        assert isinstance(data["invited_count"], int)
        assert isinstance(data["credits_earned"], int)

    def test_referrals_requires_auth(self):
        r = requests.get(f"{API}/referrals/me")
        assert r.status_code in (401, 403)


class TestReferralSignupFlow:
    def test_signup_without_referral_gives_3_credits(self):
        s = requests.Session()
        email = _fresh_email("no_ref")
        r = _register(s, email)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("created") is True
        assert data.get("referred_by") is False
        # auth/me
        me = s.get(f"{API}/auth/me")
        assert me.status_code == 200
        me_data = me.json()
        # unwrap possible shape
        user = me_data.get("user", me_data)
        assert user.get("credits") == 3, f"Expected 3 credits, got {user.get('credits')}"

    def test_signup_with_bad_referral_still_succeeds(self):
        s = requests.Session()
        email = _fresh_email("bad_ref")
        r = _register(s, email, referral_code="NOPE99")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("created") is True
        assert data.get("referred_by") is False
        me = s.get(f"{API}/auth/me")
        assert me.status_code == 200
        user = me.json().get("user", me.json())
        assert user.get("credits") == 3

    def test_full_referral_flow_credits_both_sides(self, admin_session):
        # snapshot admin state
        r = admin_session.get(f"{API}/referrals/me")
        assert r.status_code == 200
        before = r.json()
        code = before["code"]
        prev_invited = before["invited_count"]
        prev_earned = before["credits_earned"]

        # snapshot admin credits
        me_r = admin_session.get(f"{API}/auth/me")
        assert me_r.status_code == 200
        admin_user_before = me_r.json().get("user", me_r.json())
        prev_admin_credits = int(admin_user_before.get("credits", 0))

        # register new user with admin's referral code
        s2 = requests.Session()
        email = _fresh_email("with_ref")
        rr = _register(s2, email, referral_code=code)
        assert rr.status_code == 200, rr.text
        data = rr.json()
        assert data.get("created") is True
        assert data.get("referred_by") is True

        # new user should have 6 credits (3 base + 3 bonus)
        me2 = s2.get(f"{API}/auth/me")
        assert me2.status_code == 200
        u2 = me2.json().get("user", me2.json())
        assert u2.get("credits") == 6, f"Expected 6 credits, got {u2.get('credits')}"

        # admin referral stats should bump by +1 (invited_count always) and by +3
        # (credits_earned) unless the daily anti-farming cap (REFERRAL_DAILY_CAP=10)
        # has been hit by prior test runs on the same day.
        r2 = admin_session.get(f"{API}/referrals/me")
        after = r2.json()
        assert after["invited_count"] == prev_invited + 1, \
            f"invited_count did not increment: before={prev_invited} after={after['invited_count']}"
        # Under cap → credits_earned bumps by 3. At cap → credits_earned unchanged (referee still credited).
        assert after["credits_earned"] in (prev_earned + 3, prev_earned), \
            f"credits_earned unexpected: before={prev_earned} after={after['credits_earned']}"
        earned_bumped = after["credits_earned"] == prev_earned + 3

        # admin credits should bump by +3 only if the cap wasn't hit
        me_r2 = admin_session.get(f"{API}/auth/me")
        admin_user_after = me_r2.json().get("user", me_r2.json())
        expected_admin_after = prev_admin_credits + (3 if earned_bumped else 0)
        assert int(admin_user_after.get("credits", 0)) == expected_admin_after, \
            f"admin credits mismatch: before={prev_admin_credits} after={admin_user_after.get('credits')} expected={expected_admin_after}"

    def test_new_user_gets_own_referral_code(self):
        s = requests.Session()
        email = _fresh_email("own_code")
        r = _register(s, email)
        assert r.status_code == 200
        rr = s.get(f"{API}/referrals/me")
        assert rr.status_code == 200
        data = rr.json()
        assert isinstance(data["code"], str) and len(data["code"]) >= 6
        assert data["invited_count"] == 0
        assert data["credits_earned"] == 0


# ------------ smoke: login / me ------------
class TestAdminLoginSmoke:
    def test_admin_login_and_me(self, admin_session):
        me = admin_session.get(f"{API}/auth/me")
        assert me.status_code == 200
        user = me.json().get("user", me.json())
        assert user.get("role") == "admin"
        assert user.get("email") == ADMIN_EMAIL
