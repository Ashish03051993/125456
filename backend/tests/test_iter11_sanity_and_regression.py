"""Iteration 11 delta tests — Sanity Panel + regressions.

Covers:
  1. GET /api/admin/sanity — auth required, JSON shape, sample caps, pct math,
     case-insensitive duplicate detection.
  2. Regressions: /api/formats, /api/admin/attribution-matrix,
     /api/admin/waitlist (with filters), /api/admin/experiments,
     /api/admin/utm-links, /api/short/{slug}, /api/analytics/track.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://script-to-video-382.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_TOKEN = "test_admin_1784712404860"
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


# ============ 1. Sanity endpoint ============
class TestSanityAuth:
    def test_anon_denied(self):
        r = requests.get(f"{API}/admin/sanity", timeout=15)
        assert r.status_code in (401, 403), (r.status_code, r.text)

    def test_admin_ok(self):
        r = requests.get(f"{API}/admin/sanity", headers=ADMIN_HEADERS, timeout=20)
        assert r.status_code == 200, r.text


class TestSanityShape:
    @pytest.fixture(scope="class")
    def data(self):
        r = requests.get(f"{API}/admin/sanity", headers=ADMIN_HEADERS, timeout=20)
        assert r.status_code == 200
        return r.json()

    def test_top_level_keys(self, data):
        assert set(data.keys()) >= {
            "orphan_signups", "unattributed_sessions",
            "duplicate_emails", "totals",
        }

    def test_orphan_shape(self, data):
        o = data["orphan_signups"]
        assert set(o.keys()) >= {"count", "sample"}
        assert isinstance(o["count"], int)
        assert isinstance(o["sample"], list)
        # Cap at 25
        assert len(o["sample"]) <= 25
        # Sample entries have expected fields when present
        if o["sample"]:
            e = o["sample"][0]
            assert set(e.keys()) >= {"email", "position", "source",
                                     "created_at", "reason"}

    def test_unattributed_shape_and_pct_math(self, data):
        u = data["unattributed_sessions"]
        assert set(u.keys()) >= {"count", "total_sessions", "pct"}
        assert isinstance(u["count"], int)
        assert isinstance(u["total_sessions"], int)
        assert isinstance(u["pct"], (int, float))
        if u["total_sessions"]:
            expected = round((u["count"] / u["total_sessions"]) * 100, 2)
            assert u["pct"] == expected, (u["pct"], expected)
        else:
            assert u["pct"] == 0.0

    def test_duplicates_shape(self, data):
        d = data["duplicate_emails"]
        assert set(d.keys()) >= {"count", "sample"}
        assert isinstance(d["count"], int)
        assert isinstance(d["sample"], list)
        assert len(d["sample"]) <= 50

    def test_totals_shape(self, data):
        t = data["totals"]
        assert set(t.keys()) >= {"waitlist", "sessions"}
        assert isinstance(t["waitlist"], int)
        assert isinstance(t["sessions"], int)


class TestDuplicateDetectionCaseInsensitive:
    """Seed two waitlist rows with mixed-case emails and verify the sanity
    endpoint groups them together (case-insensitive)."""

    unique = uuid.uuid4().hex[:8]
    e_upper = f"CaseTest_{unique}@x.com"
    e_lower = f"casetest_{unique}@x.com"  # server lowercases on insert
    inserted_ids = []

    @classmethod
    def setup_class(cls):
        # Both go through POST /api/waitlist; server lowercases so the second
        # one hits the "already_joined" branch and does NOT create a dup.
        # So instead we insert directly to Mongo to force the duplicate.
        import subprocess
        # We use mongosh to bypass the API's lowercase+unique guard.
        script = f"""
        use('test_database');
        db.waitlist.insertOne({{
          id: 'wl_test_dupA_{cls.unique}',
          email: '{cls.e_upper}',
          plan_interest: 'free',
          source: 'test',
          position: 9990001,
          created_at: new Date().toISOString(),
        }});
        db.waitlist.insertOne({{
          id: 'wl_test_dupB_{cls.unique}',
          email: '{cls.e_lower}',
          plan_interest: 'free',
          source: 'test',
          position: 9990002,
          created_at: new Date().toISOString(),
        }});
        """
        subprocess.run(["mongosh", "--quiet", "--eval", script],
                       check=True, capture_output=True)

    @classmethod
    def teardown_class(cls):
        import subprocess
        subprocess.run(["mongosh", "--quiet", "--eval",
                        f"use('test_database'); db.waitlist.deleteMany({{id: {{$in: ['wl_test_dupA_{cls.unique}','wl_test_dupB_{cls.unique}']}}}});"],
                       check=True, capture_output=True)

    def test_duplicate_appears_case_insensitively(self):
        r = requests.get(f"{API}/admin/sanity", headers=ADMIN_HEADERS, timeout=20)
        assert r.status_code == 200
        data = r.json()
        emails = [d["email"] for d in data["duplicate_emails"]["sample"]]
        # emails are lowercased by $toLower
        assert self.e_lower.lower() in emails, (
            f"expected {self.e_lower.lower()} in duplicate sample, got {emails}"
        )
        # find the row for our test email
        row = next(d for d in data["duplicate_emails"]["sample"]
                   if d["email"] == self.e_lower.lower())
        assert row["count"] >= 2


# ============ 2. Regressions (iter-9/10 baseline) ============
class TestFormatsRegression:
    def test_landscape_and_vertical(self):
        r = requests.get(f"{API}/formats", timeout=15)
        assert r.status_code == 200
        ids = {f["id"] for f in r.json()}
        assert {"landscape", "vertical"} <= ids


class TestAttributionMatrixRegression:
    def test_anon_denied(self):
        r = requests.get(f"{API}/admin/attribution-matrix", timeout=15)
        assert r.status_code in (401, 403)

    def test_admin_ok_with_expected_shape(self):
        r = requests.get(f"{API}/admin/attribution-matrix",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert {"sources", "variants", "rows", "col_totals", "grand"} <= set(d.keys())


class TestWaitlistFiltersRegression:
    def test_anon_denied(self):
        r = requests.get(f"{API}/admin/waitlist", timeout=15)
        assert r.status_code in (401, 403)

    def test_admin_no_filter(self):
        r = requests.get(f"{API}/admin/waitlist", headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert {"count", "total", "entries", "by_source", "by_plan",
                "by_variant", "filters"} <= set(d.keys())

    def test_source_filter(self):
        r = requests.get(f"{API}/admin/waitlist",
                         headers=ADMIN_HEADERS,
                         params={"source": "direct"}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        # Every entry returned should be direct (or None coalesced to direct)
        for e in d["entries"]:
            assert (e.get("source") or "direct") == "direct"


class TestExperimentsRegression:
    def test_admin_ok(self):
        r = requests.get(f"{API}/admin/experiments",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get("experiment") == "landing_hero"
        assert isinstance(d.get("rows"), list)


class TestUtmLinksRegression:
    def test_admin_ok(self):
        r = requests.get(f"{API}/admin/utm-links",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "rows" in d and isinstance(d["rows"], list)


class TestShortLinkRegression:
    def test_short_slug_resolves_or_404(self):
        # The iter-11 spec mentions /api/short/script-to-video-382 — this may
        # not exist in every DB. Accept either 200 (resolves) or 404.
        r = requests.get(f"{API}/short/script-to-video-382", timeout=15,
                         allow_redirects=False)
        assert r.status_code in (200, 404), r.text


class TestAnalyticsTrackRegression:
    def test_track_ok(self):
        payload = {
            "event": "TEST_iter11_ping",
            "properties": {"source": "pytest", "iter": 11},
            "session_id": f"pytest_{uuid.uuid4().hex[:10]}",
            "path": "/test",
        }
        r = requests.post(f"{API}/analytics/track", json=payload, timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_track_invalid_event_rejected(self):
        r = requests.post(f"{API}/analytics/track", json={"event": ""}, timeout=15)
        assert r.status_code == 400
