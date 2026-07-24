"""
Iteration 29 backend regression tests.

Focus:
- /api/health shape (mongodb/ffmpeg/llm_key checks)
- /api/admin/repair/ffmpeg auth semantics (200 admin idempotent, 403 non-admin, 401 anon)
- /api/admin/stats.referral block shape (users_with_code, total_referred,
  referred_24h, conversion_pct, top_referrers)
- /api/referrals/me share_url uses PUBLIC host (X-Forwarded-Host aware), not
  the internal cluster hostname.

NOTE: We do NOT actually uninstall ffmpeg — the goal is to verify auth &
response shape, not to destabilise the shared container.
"""

import os
import time
import requests
import pytest


def _load_base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if v:
        return v.rstrip("/")
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


def _fresh_email(prefix="iter29"):
    return f"{prefix}_{int(time.time()*1000)}@example.com"


def _register(session, email, password="secret123", name="Iter29 Tester"):
    return session.post(
        f"{API}/auth/register",
        json={"name": name, "identifier": email, "password": password},
    )


def _login(session, email, password):
    return session.post(f"{API}/auth/login", json={"identifier": email, "password": password})


@pytest.fixture
def admin_session():
    s = requests.Session()
    r = _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture
def user_session():
    s = requests.Session()
    email = _fresh_email("regular_user")
    r = _register(s, email)
    assert r.status_code == 200, f"User register failed: {r.status_code} {r.text}"
    return s


# ------------ /api/health shape ------------
class TestHealthShape:
    def test_health_endpoint_returns_ok_with_all_checks(self):
        r = requests.get(f"{API}/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        checks = data.get("checks") or {}
        # Required checks
        assert checks.get("mongodb") == "ok", f"mongodb check failed: {checks}"
        assert checks.get("ffmpeg") == "ok", f"ffmpeg check failed: {checks}"
        assert checks.get("llm_key") == "ok", f"llm_key check failed: {checks}"


# ------------ FFmpeg repair endpoint auth ------------
class TestFFmpegRepairAuth:
    def test_repair_ffmpeg_admin_returns_200_idempotent(self, admin_session):
        r = admin_session.post(f"{API}/admin/repair/ffmpeg")
        assert r.status_code == 200, r.text
        data = r.json()
        # Idempotent: since ffmpeg is currently installed, we expect already_installed
        assert data.get("status") in ("already_installed", "installed"), (
            f"Unexpected status: {data}"
        )
        # Must include a path
        assert isinstance(data.get("path"), str) and len(data["path"]) > 0

    def test_repair_ffmpeg_user_returns_403(self, user_session):
        r = user_session.post(f"{API}/admin/repair/ffmpeg")
        assert r.status_code == 403, f"Expected 403, got {r.status_code} {r.text}"

    def test_repair_ffmpeg_anon_returns_401(self):
        r = requests.post(f"{API}/admin/repair/ffmpeg")
        assert r.status_code == 401, f"Expected 401, got {r.status_code} {r.text}"


# ------------ /api/admin/stats.referral rollup shape ------------
class TestAdminStatsReferralRollup:
    def test_admin_stats_contains_referral_block(self, admin_session):
        r = admin_session.get(f"{API}/admin/stats")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "referral" in data, f"Missing referral block: {list(data.keys())}"
        ref = data["referral"]
        for k in ("users_with_code", "total_referred", "referred_24h", "conversion_pct", "top_referrers"):
            assert k in ref, f"Missing {k} in referral block: {ref}"
        # Types
        assert isinstance(ref["users_with_code"], int)
        assert isinstance(ref["total_referred"], int)
        assert isinstance(ref["referred_24h"], int)
        assert isinstance(ref["conversion_pct"], (int, float))
        assert isinstance(ref["top_referrers"], list)
        # Top referrers rows shape
        for row in ref["top_referrers"]:
            for kk in ("user_id", "name", "code", "invited_count"):
                assert kk in row, f"Missing {kk} in top_referrer row: {row}"
            assert isinstance(row["invited_count"], int)

    def test_admin_stats_requires_admin(self, user_session):
        r = user_session.get(f"{API}/admin/stats")
        assert r.status_code == 403, f"Expected 403 for regular user, got {r.status_code}"

    def test_admin_stats_requires_auth(self):
        r = requests.get(f"{API}/admin/stats")
        assert r.status_code == 401, f"Expected 401 for anon, got {r.status_code}"


# ------------ /api/referrals/me share_url uses public host ------------
class TestReferralShareUrlPublicHost:
    def test_share_url_uses_public_preview_host(self, admin_session):
        r = admin_session.get(f"{API}/referrals/me")
        assert r.status_code == 200, r.text
        data = r.json()
        share_url = data["share_url"]
        # Must NOT contain the internal cluster hostname
        assert "cluster" not in share_url, (
            f"share_url still contains internal cluster hostname: {share_url}"
        )
        # Must be the preview external host
        assert (
            "preview.emergentagent.com" in share_url
            or "preview.emergentcf.cloud" in share_url
            or "emergent.host" in share_url
        ), f"share_url is not a public preview URL: {share_url}"
        # Must contain the signup path with code
        assert "/signup?ref=" in share_url

    def test_referral_endpoint_shape(self, admin_session):
        r = admin_session.get(f"{API}/referrals/me")
        assert r.status_code == 200
        data = r.json()
        for k in ("code", "share_url", "invited_count", "credits_earned", "bonus_per_referral"):
            assert k in data
        assert data["bonus_per_referral"] == 3


# ------------ Projects endpoint sanity (Dashboard poll) ------------
class TestProjectsListSmoke:
    def test_projects_endpoint_returns_200_for_authed_user(self, admin_session):
        r = admin_session.get(f"{API}/projects")
        assert r.status_code == 200, r.text
        data = r.json()
        # Accept either bare list or wrapped payload
        assert isinstance(data, (list, dict))
