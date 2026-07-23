"""Iteration-15 tests: production-readiness polish.

Covers:
  - /api/health endpoint (public, 200 OK, correct shape, request_id matches header)
  - x-request-id middleware (echoed when supplied, generated when not)
  - Rate limiting helper _rate_limit_check (waitlist 5/hr, analytics 300/min)
    — tested at the unit level to avoid IP-collision + DB pollution over the
    Kubernetes ingress (all live traffic looks like one IP).
  - Regression sweep across existing endpoints from prior iterations.
  - Frontend HTML meta-tag regression (title / og / twitter).
"""
import os
import sys
import uuid
from pathlib import Path

import pytest
import requests
from fastapi import HTTPException

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://script-to-video-382.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_TOK = os.environ.get("ADMIN_TOK", "test_admin_1784712404860")


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


# --------------------------- Health ---------------------------
class TestHealth:
    def test_health_200_and_shape(self):
        r = requests.get(f"{API}/health", timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "ok"
        assert body["service"] == "ai-video-studio"
        assert "checks" in body
        assert body["checks"]["mongodb"] == "ok"
        assert body["checks"]["ffmpeg"] == "ok"
        assert body["checks"]["llm_key"] == "ok"
        assert "request_id" in body and body["request_id"].startswith("rq_")

    def test_health_request_id_matches_header(self):
        r = requests.get(f"{API}/health", timeout=10)
        assert r.status_code == 200
        body_rid = r.json()["request_id"]
        header_rid = r.headers.get("x-request-id")
        assert header_rid, "x-request-id header missing"
        assert body_rid == header_rid, f"body rid {body_rid} != header rid {header_rid}"

    def test_health_is_public_no_auth(self):
        # No Authorization header — must still work
        r = requests.get(f"{API}/health", timeout=10)
        assert r.status_code == 200


# --------------------------- Request-ID Middleware ---------------------------
class TestRequestIdMiddleware:
    def test_generated_when_not_supplied(self):
        # Root and formats — non-noisy paths that pass through the middleware
        r = requests.get(f"{API}/formats", timeout=10)
        assert r.status_code == 200
        rid = r.headers.get("x-request-id")
        assert rid, "x-request-id missing on response"
        assert rid.startswith("rq_"), f"generated rid should start with rq_, got {rid}"

    def test_echoed_when_supplied(self):
        custom = f"caller_test_{uuid.uuid4().hex[:8]}"
        r = requests.get(f"{API}/formats", headers={"x-request-id": custom}, timeout=10)
        assert r.status_code == 200
        assert r.headers.get("x-request-id") == custom

    def test_present_on_errors_too(self):
        # A 401 response must also carry x-request-id (middleware wraps all)
        r = requests.get(f"{API}/projects", timeout=10)
        assert r.status_code == 401
        assert r.headers.get("x-request-id"), "x-request-id missing on 401 response"


# --------------------------- Rate-limit helper (unit) ---------------------------
# Import backend module directly for unit-level tests. This avoids saturating
# the shared ingress IP with real HTTP traffic + DB writes.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _MockClient:
    def __init__(self, host):
        self.host = host


class _MockReq:
    def __init__(self, ip):
        self.client = _MockClient(ip)


class TestRateLimitHelperUnit:
    """Unit-test the sliding-window _rate_limit_check helper."""

    def setup_method(self):
        # Clean the in-memory store for isolation
        from server import _rate_limit_store
        _rate_limit_store.clear()

    def test_waitlist_5_per_hour_limit(self):
        from server import _rate_limit_check
        ip = f"10.0.0.{uuid.uuid4().int % 250}"
        req = _MockReq(ip)
        # First 5 must pass
        for i in range(5):
            _rate_limit_check(req, "waitlist", limit=5, window_seconds=3600)
        # 6th must raise 429
        with pytest.raises(HTTPException) as excinfo:
            _rate_limit_check(req, "waitlist", limit=5, window_seconds=3600)
        assert excinfo.value.status_code == 429
        assert "Rate limit" in str(excinfo.value.detail)

    def test_analytics_300_per_minute_limit(self):
        from server import _rate_limit_check
        ip = f"10.0.1.{uuid.uuid4().int % 250}"
        req = _MockReq(ip)
        for i in range(300):
            _rate_limit_check(req, "analytics", limit=300, window_seconds=60)
        with pytest.raises(HTTPException) as excinfo:
            _rate_limit_check(req, "analytics", limit=300, window_seconds=60)
        assert excinfo.value.status_code == 429

    def test_per_ip_isolation(self):
        """Two different IPs share no state."""
        from server import _rate_limit_check
        req_a = _MockReq("10.0.2.1")
        req_b = _MockReq("10.0.2.2")
        for _ in range(5):
            _rate_limit_check(req_a, "waitlist", limit=5, window_seconds=3600)
        # IP A is now capped, but IP B should still work fine
        for _ in range(5):
            _rate_limit_check(req_b, "waitlist", limit=5, window_seconds=3600)
        with pytest.raises(HTTPException):
            _rate_limit_check(req_a, "waitlist", limit=5, window_seconds=3600)

    def test_per_bucket_isolation(self):
        """Waitlist and analytics buckets are independent per IP."""
        from server import _rate_limit_check
        req = _MockReq("10.0.3.1")
        for _ in range(5):
            _rate_limit_check(req, "waitlist", limit=5, window_seconds=3600)
        # Same IP, different bucket — should still pass
        _rate_limit_check(req, "analytics", limit=300, window_seconds=60)


# --------------------------- Waitlist rate limit (live smoke, cleaned up) ---------------------------
class TestWaitlistLiveRateLimit:
    """One live pass to confirm the endpoint actually invokes the helper.
    Uses TEST_ prefix on emails and cleans up afterwards."""

    inserted_emails = []

    def test_waitlist_returns_429_after_5(self):
        # NOTE: prior tests in this test-run may have already consumed hits
        # on the shared ingress IP. To keep this deterministic we reset the
        # store via a direct import (since the test process runs in-repo).
        try:
            from server import _rate_limit_store
            # Only clear the waitlist bucket entries to not interfere with
            # a possible parallel test using analytics bucket.
            for k in list(_rate_limit_store):
                if k[1] == "waitlist":
                    del _rate_limit_store[k]
        except Exception:
            # If we can't reach the process-local store (deployed remotely),
            # skip live limit assertion — unit tests already cover it.
            pytest.skip("Cannot reset remote in-memory rate-limit store — unit tests cover logic")

        base_email = f"wl_iter15_{uuid.uuid4().hex[:6]}"
        got_429 = False
        successes = 0
        for i in range(6):
            email = f"{base_email}_{i}@example.com"
            r = requests.post(f"{API}/waitlist", json={"email": email}, timeout=10)
            if r.status_code == 200:
                successes += 1
                self.inserted_emails.append(email)
            elif r.status_code == 429:
                got_429 = True
                break
        # We should observe rate-limit trigger at or before the 6th call
        assert got_429, f"expected 429 within 6 calls, got {successes} successes"
        assert successes <= 5

    def teardown_class(cls):
        """Delete test waitlist rows created above via direct mongo access."""
        try:
            import asyncio
            from server import db
            async def _cleanup():
                if cls.inserted_emails:
                    await db.waitlist.delete_many({"email": {"$in": cls.inserted_emails}})
            asyncio.get_event_loop().run_until_complete(_cleanup())
        except Exception:
            pass


# --------------------------- Regression sweep ---------------------------
class TestRegression:
    def test_formats_public(self):
        r = requests.get(f"{API}/formats", timeout=10)
        assert r.status_code == 200
        data = r.json()
        # list_formats() returns dict or list; either shape acceptable, just non-empty
        assert data, "formats empty"

    def test_admin_stats(self):
        r = requests.get(f"{API}/admin/stats", headers=hdr(ADMIN_TOK), timeout=15)
        assert r.status_code == 200, r.text
        s = r.json()
        for k in ("total_users", "total_projects", "waitlist_total", "waitlist_24h"):
            assert k in s

    def test_admin_attribution_matrix(self):
        r = requests.get(f"{API}/admin/attribution-matrix", headers=hdr(ADMIN_TOK), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("sources", "variants", "rows", "col_totals", "grand"):
            assert k in d

    def test_admin_attribution_matrix_csv(self):
        r = requests.get(f"{API}/admin/attribution-matrix.csv", headers=hdr(ADMIN_TOK), timeout=15)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/csv")
        assert "source,variant,sessions,signups,conversion_pct" in r.text

    def test_admin_sanity(self):
        r = requests.get(f"{API}/admin/sanity", headers=hdr(ADMIN_TOK), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("orphan_signups", "unattributed_sessions", "duplicate_emails", "totals"):
            assert k in d

    def test_admin_sanity_untagged(self):
        r = requests.get(f"{API}/admin/sanity/untagged", headers=hdr(ADMIN_TOK), timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("total", "returned", "sessions", "top_referrer_hosts", "top_landing_paths"):
            assert k in d

    def test_admin_waitlist(self):
        r = requests.get(f"{API}/admin/waitlist", headers=hdr(ADMIN_TOK), timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("count", "total", "by_plan", "by_source", "by_variant", "entries"):
            assert k in d

    def test_admin_waitlist_csv(self):
        r = requests.get(f"{API}/admin/waitlist.csv", headers=hdr(ADMIN_TOK), timeout=15)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/csv")

    def test_admin_utm_links(self):
        r = requests.get(f"{API}/admin/utm-links", headers=hdr(ADMIN_TOK), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "rows" in d

    def test_short_link_404_for_unknown(self):
        r = requests.get(f"{API}/short/definitely-not-a-real-slug-abcxyz", timeout=10)
        assert r.status_code == 404

    def test_experiment_assign(self):
        cid = f"testclient_{uuid.uuid4().hex[:8]}"
        r = requests.get(f"{API}/experiments/landing_hero/{cid}", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["experiment"] == "landing_hero"
        assert "variant" in d and d["variant"]
        assert "content" in d

    def test_auth_session_invalid(self):
        r = requests.post(f"{API}/auth/session",
                          json={"session_id": "not-a-real-session"}, timeout=15)
        # Upstream returns non-200 -> our endpoint returns 401
        assert r.status_code == 401

    def test_projects_unauthed(self):
        r = requests.get(f"{API}/projects", timeout=10)
        assert r.status_code == 401


# --------------------------- Frontend HTML meta-tags ---------------------------
class TestFrontendMetaTags:
    """Verify index.html served at / carries the new title + OG/Twitter meta."""

    def _fetch_root(self):
        # The Kubernetes ingress routes '/' to frontend port 3000 (CRA dev
        # server). It serves the raw public/index.html contents.
        r = requests.get(BASE_URL + "/", timeout=15)
        assert r.status_code == 200
        return r.text

    def test_title_updated(self):
        html = self._fetch_root()
        assert "AI Video Studio" in html
        assert "One idea, four polished outputs" in html
        assert "Emergent | Fullstack App" not in html

    def test_open_graph_tags(self):
        html = self._fetch_root()
        for needle in [
            'property="og:type"',
            'property="og:site_name"',
            'property="og:title"',
            'property="og:description"',
            'property="og:image"',
        ]:
            assert needle in html, f"missing OG tag: {needle}"

    def test_twitter_tags(self):
        html = self._fetch_root()
        for needle in [
            'name="twitter:card"',
            'name="twitter:title"',
            'name="twitter:description"',
            'name="twitter:image"',
        ]:
            assert needle in html, f"missing twitter tag: {needle}"

    def test_description_meta(self):
        html = self._fetch_root()
        assert 'name="description"' in html
        assert "Turn any topic into" in html
