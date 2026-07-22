"""Iteration 12 delta tests — Untagged Session Drilldown + iter-11 regressions.

Covers:
  1. GET /api/admin/sanity/untagged — auth, shape, limit clamp, referrer_host
     derivation, sorted+capped rollups, only-page_view+missing-source counted.
  2. Regressions: /api/admin/sanity, /api/admin/attribution-matrix,
     /api/formats, /api/admin/waitlist, /api/admin/experiments,
     /api/admin/utm-links, /api/short/script-to-video-382, /api/analytics/track.
"""
import os
import time
import uuid
import subprocess
import pytest
import requests

_BE = os.environ.get("REACT_APP_BACKEND_URL")
if not _BE:
    # Load from frontend/.env
    _env_path = "/app/frontend/.env"
    if os.path.exists(_env_path):
        with open(_env_path) as _f:
            for _line in _f:
                if _line.startswith("REACT_APP_BACKEND_URL="):
                    _BE = _line.split("=", 1)[1].strip()
                    break
BASE_URL = (_BE or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
API = f"{BASE_URL}/api"

ADMIN_TOKEN = "test_admin_1784712404860"
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


# ============ 1. Untagged drilldown endpoint ============
class TestUntaggedAuth:
    def test_anon_denied(self):
        r = requests.get(f"{API}/admin/sanity/untagged", timeout=15)
        assert r.status_code in (401, 403), (r.status_code, r.text)

    def test_admin_ok(self):
        r = requests.get(f"{API}/admin/sanity/untagged",
                         headers=ADMIN_HEADERS, timeout=20)
        assert r.status_code == 200, r.text


class TestUntaggedShape:
    @pytest.fixture(scope="class")
    def data(self):
        r = requests.get(f"{API}/admin/sanity/untagged",
                         headers=ADMIN_HEADERS, timeout=20)
        assert r.status_code == 200
        return r.json()

    def test_top_level_keys(self, data):
        assert set(data.keys()) >= {
            "total", "returned", "sessions",
            "top_referrer_hosts", "top_landing_paths",
        }

    def test_types(self, data):
        assert isinstance(data["total"], int)
        assert isinstance(data["returned"], int)
        assert isinstance(data["sessions"], list)
        assert isinstance(data["top_referrer_hosts"], list)
        assert isinstance(data["top_landing_paths"], list)

    def test_session_row_shape(self, data):
        if not data["sessions"]:
            pytest.skip("no untagged sessions in DB")
        s = data["sessions"][0]
        expected = {
            "session_id", "first_seen", "last_seen", "page_views",
            "referrer", "referrer_host", "landing_path", "user_agent",
        }
        assert expected <= set(s.keys()), (expected - set(s.keys()))

    def test_top_arrays_capped_at_15(self, data):
        assert len(data["top_referrer_hosts"]) <= 15
        assert len(data["top_landing_paths"]) <= 15

    def test_top_arrays_sorted_desc(self, data):
        for arr in (data["top_referrer_hosts"], data["top_landing_paths"]):
            ns = [x["n"] for x in arr]
            assert ns == sorted(ns, reverse=True), ns

    def test_returned_le_limit(self, data):
        # default limit is 100
        assert data["returned"] <= 100
        assert data["returned"] <= data["total"]


class TestUntaggedLimitClamp:
    def test_limit_zero_clamps_to_1(self):
        r = requests.get(f"{API}/admin/sanity/untagged",
                         headers=ADMIN_HEADERS,
                         params={"limit": 0}, timeout=20)
        assert r.status_code == 200
        # Server should clamp to min=1
        assert r.json()["returned"] <= 1

    def test_limit_negative_clamps_to_1(self):
        r = requests.get(f"{API}/admin/sanity/untagged",
                         headers=ADMIN_HEADERS,
                         params={"limit": -50}, timeout=20)
        assert r.status_code == 200
        assert r.json()["returned"] <= 1

    def test_limit_huge_clamps_to_500(self):
        r = requests.get(f"{API}/admin/sanity/untagged",
                         headers=ADMIN_HEADERS,
                         params={"limit": 9999}, timeout=20)
        assert r.status_code == 200
        assert r.json()["returned"] <= 500


class TestUntaggedSeededHosts:
    """Seed 3 fake page_view events with distinct referrers and no source,
    then confirm the hosts + direct fallback appear in top_referrer_hosts.
    """

    unique = uuid.uuid4().hex[:8]
    ids = [
        f"s_iter12_{unique}_A",
        f"s_iter12_{unique}_B",
        f"s_iter12_{unique}_C",
    ]

    @classmethod
    def setup_class(cls):
        # Insert 3 page_view events with different referrers, no properties.source
        script = f"""
        use('test_database');
        db.analytics_events.insertMany([
          {{
            id: 'evt_iter12_{cls.unique}_A',
            event: 'page_view',
            session_id: '{cls.ids[0]}',
            path: '/iter12A',
            referrer: 'https://linkedin.com/feed/post/xyz',
            user_agent: 'iter12-test-ua',
            properties: {{}},
            created_at: new Date().toISOString(),
          }},
          {{
            id: 'evt_iter12_{cls.unique}_B',
            event: 'page_view',
            session_id: '{cls.ids[1]}',
            path: '/iter12B',
            referrer: 'https://twitter.com/x/status/1',
            user_agent: 'iter12-test-ua',
            properties: {{}},
            created_at: new Date().toISOString(),
          }},
          {{
            id: 'evt_iter12_{cls.unique}_C',
            event: 'page_view',
            session_id: '{cls.ids[2]}',
            path: '/iter12C',
            referrer: '',
            user_agent: 'iter12-test-ua',
            properties: {{}},
            created_at: new Date().toISOString(),
          }}
        ]);
        """
        subprocess.run(["mongosh", "--quiet", "--eval", script],
                       check=True, capture_output=True)

    @classmethod
    def teardown_class(cls):
        script = f"""
        use('test_database');
        db.analytics_events.deleteMany({{ session_id: {{ $in: {list(cls.ids)!r} }} }});
        """
        subprocess.run(["mongosh", "--quiet", "--eval", script],
                       check=True, capture_output=True)

    def test_seeded_hosts_appear(self):
        r = requests.get(f"{API}/admin/sanity/untagged",
                         headers=ADMIN_HEADERS,
                         params={"limit": 500}, timeout=20)
        assert r.status_code == 200
        data = r.json()
        hosts = {h["host"] for h in data["top_referrer_hosts"]}
        # Note: with 15-cap on top_referrer_hosts, our seeded hosts may not appear
        # if there are 15+ higher-count hosts already. Instead assert via sessions.
        seeded_found = [s for s in data["sessions"]
                        if s["session_id"] in self.ids]
        assert len(seeded_found) == 3, f"expected 3 seeded, got {len(seeded_found)}"

        hosts_seen = {s["referrer_host"] for s in seeded_found}
        assert "linkedin.com" in hosts_seen
        assert "twitter.com" in hosts_seen
        assert "(direct/none)" in hosts_seen

    def test_only_page_view_missing_source_counted(self):
        """Insert a page_view WITH source — it should NOT appear."""
        tagged_sid = f"s_iter12_{self.unique}_TAGGED"
        script = f"""
        use('test_database');
        db.analytics_events.insertOne({{
          id: 'evt_iter12_{self.unique}_TAGGED',
          event: 'page_view',
          session_id: '{tagged_sid}',
          path: '/iter12TAGGED',
          referrer: 'https://google.com',
          user_agent: 'iter12-test-ua',
          properties: {{ source: 'google' }},
          created_at: new Date().toISOString(),
        }});
        """
        subprocess.run(["mongosh", "--quiet", "--eval", script],
                       check=True, capture_output=True)
        try:
            r = requests.get(f"{API}/admin/sanity/untagged",
                             headers=ADMIN_HEADERS,
                             params={"limit": 500}, timeout=20)
            assert r.status_code == 200
            sids = {s["session_id"] for s in r.json()["sessions"]}
            assert tagged_sid not in sids, "tagged session leaked into untagged"
        finally:
            subprocess.run(["mongosh", "--quiet", "--eval",
                            f"use('test_database'); db.analytics_events.deleteOne({{id: 'evt_iter12_{self.unique}_TAGGED'}});"],
                           check=True, capture_output=True)


# ============ 2. Regressions ============
class TestSanityRegression:
    def test_admin_ok_shape(self):
        r = requests.get(f"{API}/admin/sanity",
                         headers=ADMIN_HEADERS, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert {"orphan_signups", "unattributed_sessions",
                "duplicate_emails", "totals"} <= set(d.keys())


class TestAttributionMatrixRegression:
    def test_admin_ok(self):
        r = requests.get(f"{API}/admin/attribution-matrix",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert {"sources", "variants", "rows", "col_totals", "grand"} <= set(d.keys())


class TestFormatsRegression:
    def test_landscape_and_vertical(self):
        r = requests.get(f"{API}/formats", timeout=15)
        assert r.status_code == 200
        ids = {f["id"] for f in r.json()}
        assert {"landscape", "vertical"} <= ids


class TestWaitlistRegression:
    def test_admin_ok(self):
        r = requests.get(f"{API}/admin/waitlist",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert {"count", "total", "entries", "by_source"} <= set(d.keys())


class TestExperimentsRegression:
    def test_admin_ok(self):
        r = requests.get(f"{API}/admin/experiments",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        assert r.json().get("experiment") == "landing_hero"


class TestUtmLinksRegression:
    def test_admin_ok(self):
        r = requests.get(f"{API}/admin/utm-links",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        assert "rows" in r.json()


class TestShortLinkRegression:
    def test_short_slug(self):
        r = requests.get(f"{API}/short/script-to-video-382",
                         timeout=15, allow_redirects=False)
        assert r.status_code in (200, 404), r.text


class TestAnalyticsTrackRegression:
    def test_track_ok(self):
        payload = {
            "event": "TEST_iter12_ping",
            "properties": {"source": "pytest", "iter": 12},
            "session_id": f"pytest_iter12_{uuid.uuid4().hex[:10]}",
            "path": "/test",
        }
        r = requests.post(f"{API}/analytics/track", json=payload, timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True


# ============ 3. Referral-URL end-to-end attribution (waitlist) ============
class TestWaitlistReferralAttribution:
    """Simulate second-hop signup via referral URL: POST /api/waitlist with
    source=referral, campaign=waitlist — verify it lands with that attribution.
    """
    email = f"wl_iter12_{uuid.uuid4().hex[:8]}@x.com"

    @classmethod
    def teardown_class(cls):
        subprocess.run(["mongosh", "--quiet", "--eval",
                        f"use('test_database'); db.waitlist.deleteOne({{email: '{cls.email}'}});"],
                       check=True, capture_output=True)

    def test_referral_signup_recorded(self):
        payload = {
            "email": self.email,
            "plan_interest": "free",
            "source": "referral",
            "medium": "share",
            "campaign": "waitlist",
            "referrer": "https://example.com/?ref=100",
        }
        r = requests.post(f"{API}/waitlist", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        # Now fetch admin waitlist with source=referral filter to see it
        r2 = requests.get(f"{API}/admin/waitlist",
                          headers=ADMIN_HEADERS,
                          params={"source": "referral"}, timeout=15)
        assert r2.status_code == 200
        entries = r2.json().get("entries", [])
        emails = {e.get("email") for e in entries}
        assert self.email in emails, f"referral signup {self.email} not found in source=referral filter"
        row = next(e for e in entries if e.get("email") == self.email)
        assert row.get("source") == "referral"
        assert row.get("campaign") == "waitlist"
