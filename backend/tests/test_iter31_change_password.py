"""
Iteration 31 — regression guards for the change-password endpoint.
Runs any time to verify auth invariants hold.
"""
import os, uuid, requests, pytest

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001") + "/api"


def _fresh_email(tag="cpw"):
    return f"iter31_{tag}_{uuid.uuid4().hex[:8]}@example.com"


def _register(session, email, password="StartPass1!"):
    return session.post(f"{API}/auth/register", json={
        "name": "Iter31 Test", "identifier": email, "password": password,
    })


class TestChangePassword:
    def test_unauthenticated_returns_401(self):
        r = requests.post(f"{API}/auth/change-password",
                          json={"current_password": "x", "new_password": "y"})
        assert r.status_code == 401

    def test_wrong_current_password_rejected(self):
        s = requests.Session()
        email = _fresh_email("wrong")
        assert _register(s, email).status_code == 200
        r = s.post(f"{API}/auth/change-password", json={
            "current_password": "NotMyPassword!", "new_password": "NewGoodPass1!",
        })
        assert r.status_code == 400
        assert "incorrect" in r.text.lower()

    def test_short_new_password_rejected(self):
        s = requests.Session()
        email = _fresh_email("short")
        assert _register(s, email).status_code == 200
        r = s.post(f"{API}/auth/change-password", json={
            "current_password": "StartPass1!", "new_password": "short",
        })
        assert r.status_code == 400
        assert "8 characters" in r.text

    def test_happy_path_invalidates_old_sessions(self):
        """After a successful change, the OLD cookie should NOT work but a NEW one issued during the change should."""
        old = requests.Session()
        email = _fresh_email("happy")
        assert _register(old, email).status_code == 200
        # Snapshot the old cookie for later verification
        old_cookie_jar = requests.utils.dict_from_cookiejar(old.cookies)
        # Change password — response gets a NEW session_token cookie
        r = old.post(f"{API}/auth/change-password", json={
            "current_password": "StartPass1!", "new_password": "BrandNew1!",
        })
        assert r.status_code == 200
        # A separate session using the OLD cookie only must now be denied
        stale = requests.Session()
        for k, v in old_cookie_jar.items():
            stale.cookies.set(k, v)
        me_stale = stale.get(f"{API}/auth/me")
        assert me_stale.status_code == 401, "Old session should have been invalidated after password change"
        # The `old` session (which followed the Set-Cookie in the response) should still work
        me_new = old.get(f"{API}/auth/me")
        assert me_new.status_code == 200

    def test_new_password_actually_becomes_current(self):
        s = requests.Session()
        email = _fresh_email("login")
        assert _register(s, email).status_code == 200
        r = s.post(f"{API}/auth/change-password", json={
            "current_password": "StartPass1!", "new_password": "MyNewPass1!",
        })
        assert r.status_code == 200
        # Login with OLD password → should fail
        r_old = requests.post(f"{API}/auth/login", json={"identifier": email, "password": "StartPass1!"})
        assert r_old.status_code == 401
        # Login with NEW password → should succeed
        r_new = requests.post(f"{API}/auth/login", json={"identifier": email, "password": "MyNewPass1!"})
        assert r_new.status_code == 200
