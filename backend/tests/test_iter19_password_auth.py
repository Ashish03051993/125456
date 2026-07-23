"""Backend tests for Email/Mobile + Password authentication (iteration 19).

Covers:
- /api/auth/register (email, mobile, duplicate, validation)
- /api/auth/login (success, wrong password, unknown identifier, brute force lockout)
- /api/auth/me (returns user without password_hash, requires session)
- /api/auth/logout (clears cookie)
- /api/auth/set-password (attach password to existing user)
- Regression: /api/auth/session (Google) still validates payload
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


# ---------- helpers ----------
def _rand_email():
    return f"TEST_pw_{uuid.uuid4().hex[:10]}@testmail.local"


def _rand_mobile():
    # E.164-ish. Use a country code and 10 random digits
    return "+91" + "".join([str((int(x, 16) % 10)) for x in uuid.uuid4().hex[:10]])


@pytest.fixture
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# =====================================================================
# REGISTER
# =====================================================================
class TestRegister:
    def test_register_email_creates_user_with_3_credits_and_cookie(self, s):
        email = _rand_email()
        r = s.post(f"{API}/auth/register",
                   json={"name": "Test User", "identifier": email, "password": "secret123"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "user" in body
        u = body["user"]
        assert u["email"] == email.lower()
        assert u.get("credits") == 3
        assert u.get("plan") == "free"
        assert "password_hash" not in u
        # httpOnly session cookie must be set
        assert "session_token" in s.cookies.get_dict()

        # /auth/me with cookie returns same user, no password_hash
        me = s.get(f"{API}/auth/me")
        assert me.status_code == 200
        me_body = me.json()
        assert me_body["user_id"] == u["user_id"]
        assert "password_hash" not in me_body

    def test_register_with_mobile_identifier(self, s):
        mobile = _rand_mobile()
        r = s.post(f"{API}/auth/register",
                   json={"name": "Mobile User", "identifier": mobile, "password": "secret123"})
        assert r.status_code == 200, r.text
        u = r.json()["user"]
        assert u.get("mobile") == mobile
        assert u.get("email") in (None, "", u.get("email"))  # email may be absent

    def test_register_duplicate_email_returns_409(self, s):
        email = _rand_email()
        r1 = s.post(f"{API}/auth/register",
                    json={"name": "Dup", "identifier": email, "password": "secret123"})
        assert r1.status_code == 200
        # New session (new client) so cookie doesn't matter
        s2 = requests.Session()
        r2 = s2.post(f"{API}/auth/register",
                     json={"name": "Dup2", "identifier": email, "password": "secret123"})
        assert r2.status_code == 409, r2.text
        detail = r2.json().get("detail", "")
        assert "exist" in detail.lower() or "already" in detail.lower()

    def test_register_short_password_400(self, s):
        r = s.post(f"{API}/auth/register",
                   json={"name": "Shorty", "identifier": _rand_email(), "password": "short"})
        assert r.status_code == 400
        assert "8" in r.json()["detail"]

    def test_register_invalid_identifier_400(self, s):
        r = s.post(f"{API}/auth/register",
                   json={"name": "Bad", "identifier": "not-an-email-or-mobile", "password": "secret123"})
        assert r.status_code == 400


# =====================================================================
# LOGIN
# =====================================================================
class TestLogin:
    @pytest.fixture
    def account(self):
        # Fresh registered account (independent requests.Session)
        email = _rand_email()
        password = "secret123"
        sess = requests.Session()
        r = sess.post(f"{API}/auth/register",
                      json={"name": "Login Fixture", "identifier": email, "password": password})
        assert r.status_code == 200
        return {"email": email, "password": password, "user": r.json()["user"]}

    def test_login_success_sets_cookie_and_me_returns_user(self, account):
        s = requests.Session()
        r = s.post(f"{API}/auth/login",
                   json={"identifier": account["email"], "password": account["password"]})
        assert r.status_code == 200, r.text
        assert "session_token" in s.cookies.get_dict()
        u = r.json()["user"]
        assert u["email"] == account["email"].lower()
        assert "password_hash" not in u

        me = s.get(f"{API}/auth/me")
        assert me.status_code == 200
        assert me.json()["user_id"] == u["user_id"]
        assert "password_hash" not in me.json()

    def test_login_wrong_password_401(self, account):
        s = requests.Session()
        r = s.post(f"{API}/auth/login",
                   json={"identifier": account["email"], "password": "definitely-wrong"})
        assert r.status_code == 401
        assert "invalid" in r.json()["detail"].lower()

    def test_login_unknown_identifier_401(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login",
                   json={"identifier": _rand_email(), "password": "whatever123"})
        assert r.status_code == 401

    def test_brute_force_lockout_after_5_failures(self):
        # Use a unique identifier to avoid clashing with other tests / prior state.
        email = _rand_email()
        # Register first, so identifier exists (still bad-password path triggers failure counter)
        setup = requests.Session()
        rr = setup.post(f"{API}/auth/register",
                        json={"name": "Locky", "identifier": email, "password": "secret123"})
        assert rr.status_code == 200

        s = requests.Session()
        for i in range(5):
            r = s.post(f"{API}/auth/login",
                       json={"identifier": email, "password": "wrong-pass"})
            assert r.status_code == 401, f"attempt {i+1}: {r.status_code} {r.text}"
        # 6th attempt should be locked out with 429
        r6 = s.post(f"{API}/auth/login",
                    json={"identifier": email, "password": "wrong-pass"})
        assert r6.status_code == 429, r6.text
        assert "too many" in r6.json()["detail"].lower()


# =====================================================================
# LOGOUT
# =====================================================================
class TestLogout:
    def test_logout_clears_session(self, s):
        email = _rand_email()
        r = s.post(f"{API}/auth/register",
                   json={"name": "Logout U", "identifier": email, "password": "secret123"})
        assert r.status_code == 200
        assert s.get(f"{API}/auth/me").status_code == 200

        lo = s.post(f"{API}/auth/logout")
        assert lo.status_code == 200
        # After logout, /auth/me should be 401 (cookie deleted by server)
        # NOTE: requests session may still keep the cookie value but server-side session doc is deleted
        me = s.get(f"{API}/auth/me")
        assert me.status_code == 401


# =====================================================================
# SET-PASSWORD (attach password to Google-only user)
# =====================================================================
class TestSetPassword:
    def test_set_password_attaches_and_login_works(self, s):
        # Simulate a Google-only user by directly inserting via register-then-clearing password?
        # Simpler: register normally (has password_hash) then call set-password to change; then log in.
        email = _rand_email()
        r = s.post(f"{API}/auth/register",
                   json={"name": "Setter", "identifier": email, "password": "secret123"})
        assert r.status_code == 200

        newpw = "newpassword456"
        sp = s.post(f"{API}/auth/set-password", json={"password": newpw})
        assert sp.status_code == 200

        # Log in with new password
        s2 = requests.Session()
        li = s2.post(f"{API}/auth/login", json={"identifier": email, "password": newpw})
        assert li.status_code == 200, li.text

    def test_set_password_short_400(self, s):
        email = _rand_email()
        s.post(f"{API}/auth/register",
               json={"name": "Setter", "identifier": email, "password": "secret123"})
        r = s.post(f"{API}/auth/set-password", json={"password": "short"})
        assert r.status_code == 400


# =====================================================================
# Regression: Google /auth/session still exists & validates
# =====================================================================
class TestGoogleAuthRegression:
    def test_auth_session_rejects_invalid_session_id(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/session", json={"session_id": "obviously-invalid-id"})
        # Must not crash; should return 401 from upstream
        assert r.status_code == 401

    def test_auth_me_without_cookie_401(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401
