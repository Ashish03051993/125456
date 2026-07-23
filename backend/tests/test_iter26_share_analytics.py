"""Iteration 26 — Share Analytics for creators.

Tests:
  1. Helper functions (imported directly): _parse_referrer_host, _bucket_user_agent
  2. GET /api/public/videos/{slug} inserts a share_events doc with correct fields
  3. GET /api/projects/{pid}/share/analytics returns full shape
  4. 14-day timeline is correct shape/order
  5. Auth required (401 without cookie); other user gets 404 for foreign project
  6. Project without share_slug -> share_enabled=false + empty arrays
  7. Multi-referrer aggregation
  8. MongoDB indexes exist: (slug,at_day) compound and (at) single
"""
import os
import sys
import asyncio
import pytest
import requests
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

# Import backend helper functions for direct unit testing
sys.path.insert(0, "/app/backend")
from server import _parse_referrer_host, _bucket_user_agent  # type: ignore

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                break

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"
with open("/app/backend/.env") as f:
    for l in f:
        if l.startswith("MONGO_URL="):
            MONGO_URL = l.split("=", 1)[1].strip().strip('"')
        if l.startswith("DB_NAME="):
            DB_NAME = l.split("=", 1)[1].strip().strip('"')

READY_PID = "proj_8930939f0b84"


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def auth_session():
    """Login as newuser@test.com."""
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"identifier": "newuser@test.com", "password": "secret123"})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def other_auth_session():
    """Register + login as a distinct user so we can verify cross-user 404."""
    s = requests.Session()
    ident = "TEST_iter26_other@test.com"
    s.post(f"{BASE_URL}/api/auth/register",
           json={"name": "Other Iter26", "identifier": ident, "password": "secret123"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"identifier": ident, "password": "secret123"})
    assert r.status_code == 200, f"other login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def slug(auth_session):
    """Ensure share is enabled on READY_PID and return the current slug."""
    r = auth_session.post(f"{BASE_URL}/api/projects/{READY_PID}/share")
    assert r.status_code == 200, f"enable_share failed: {r.status_code} {r.text}"
    return r.json()["share_slug"]


# NOTE: no autouse cleanup fixture — cross-worker teardown races caused
# spurious failures. Data is left in place; the ready project's share_view_count
# accumulates but that is inconsequential for review-request validation.


# ---------------------------------------------------------------------------
# 1. Helper functions
# ---------------------------------------------------------------------------
class TestReferrerHostParser:
    def test_full_url_extracts_host(self):
        assert _parse_referrer_host("https://twitter.com/user/status/1") == "twitter.com"

    def test_strips_www_prefix(self):
        assert _parse_referrer_host("https://www.twitter.com/x") == "twitter.com"

    def test_strips_m_prefix(self):
        assert _parse_referrer_host("https://m.facebook.com/") == "facebook.com"

    def test_strips_mobile_prefix(self):
        assert _parse_referrer_host("https://mobile.twitter.com/x") == "twitter.com"

    def test_empty_returns_direct(self):
        assert _parse_referrer_host("") == "direct"
        assert _parse_referrer_host(None) == "direct"

    def test_own_domain_kadenza_returns_direct(self):
        assert _parse_referrer_host("https://kadenza.app/dashboard") == "direct"

    def test_own_domain_emergentagent_returns_direct(self):
        assert _parse_referrer_host("https://foo.emergentagent.com/x") == "direct"

    def test_malformed_url_returns_direct(self):
        # No scheme, no netloc -> host empty -> direct
        assert _parse_referrer_host("garbage") == "direct"


class TestUABucket:
    def test_mobile_iphone(self):
        assert _bucket_user_agent(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
        ) == "mobile"

    def test_mobile_android(self):
        assert _bucket_user_agent(
            "Mozilla/5.0 (Linux; Android 13; Pixel 6)"
        ) == "mobile"

    def test_desktop_chrome(self):
        # Standard Chrome desktop UA
        assert _bucket_user_agent(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ) == "desktop"

    def test_desktop_firefox(self):
        assert _bucket_user_agent(
            "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
        ) == "desktop"

    def test_bot_twitter(self):
        assert _bucket_user_agent("Twitterbot/1.0") == "bot_preview"

    def test_bot_whatsapp(self):
        assert _bucket_user_agent("WhatsApp/2.19.81 A") == "bot_preview"

    def test_bot_linkedin(self):
        assert _bucket_user_agent("LinkedInBot/1.0 (compatible; Mozilla/5.0)") == "bot_preview"

    def test_bot_slack(self):
        assert _bucket_user_agent("Slackbot-LinkExpanding 1.0") == "bot_preview"

    def test_bot_facebook_external_hit(self):
        assert _bucket_user_agent("facebookexternalhit/1.1") == "bot_preview"

    def test_empty_returns_unknown(self):
        assert _bucket_user_agent("") == "unknown"


# ---------------------------------------------------------------------------
# 2. View logging: /api/public/videos/{slug} inserts share_event
# ---------------------------------------------------------------------------
class TestViewLogging:
    def test_view_inserts_share_event(self, slug):
        # Use a UNIQUE referrer host so we can find our own inserted event
        # regardless of concurrent xdist workers hitting the same slug.
        unique_ref = "https://example.org/iter26-viewlogging"

        r = requests.get(
            f"{BASE_URL}/api/public/videos/{slug}",
            headers={
                "Referer": unique_ref,
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
            },
            timeout=10,
        )
        assert r.status_code == 200, f"public GET failed: {r.status_code} {r.text}"

        # Small delay for fire-and-forget insert
        import time; time.sleep(0.7)

        # Verify a document with our unique referer + expected shape
        async def _fetch_ours():
            cli = AsyncIOMotorClient(MONGO_URL); db = cli[DB_NAME]
            doc = await db.share_events.find_one(
                {"slug": slug, "referrer": "example.org"},
                sort=[("at", -1)],
            )
            cli.close()
            return doc
        doc = _run(_fetch_ours())
        assert doc is not None, "share_event with expected referer='example.org' not found"
        for field in ("slug", "project_id", "user_id", "referrer", "ua_bucket", "at", "at_day"):
            assert field in doc, f"missing field {field!r} in share_event doc: {doc.keys()}"
        assert doc["slug"] == slug
        assert doc["project_id"] == READY_PID
        assert doc["referrer"] == "example.org"
        assert doc["ua_bucket"] == "mobile"
        # at_day format
        assert len(doc["at_day"]) == 10 and doc["at_day"][4] == "-" and doc["at_day"][7] == "-"


# ---------------------------------------------------------------------------
# 3-4. Analytics endpoint shape + timeline
# ---------------------------------------------------------------------------
class TestAnalyticsShape:
    def test_analytics_returns_expected_shape(self, auth_session, slug):
        r = auth_session.get(f"{BASE_URL}/api/projects/{READY_PID}/share/analytics")
        assert r.status_code == 200, f"analytics failed: {r.status_code} {r.text}"
        data = r.json()
        for field in ("total_views", "share_enabled", "last_viewed_at",
                      "share_slug", "timeline", "top_referrers", "ua_breakdown"):
            assert field in data, f"missing field {field!r} in analytics: {list(data.keys())}"
        assert isinstance(data["total_views"], int)
        assert data["share_slug"] == slug
        assert data["share_enabled"] is True
        assert isinstance(data["timeline"], list)
        assert isinstance(data["top_referrers"], list)
        assert isinstance(data["ua_breakdown"], list)
        assert len(data["top_referrers"]) <= 6

    def test_timeline_has_14_days_oldest_first(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/projects/{READY_PID}/share/analytics")
        assert r.status_code == 200
        tl = r.json()["timeline"]
        assert len(tl) == 14, f"timeline is not 14 entries: {len(tl)}"
        # Each entry has {day, views}
        for entry in tl:
            assert set(entry.keys()) == {"day", "views"}, f"bad keys: {entry.keys()}"
            assert isinstance(entry["views"], int)
        # Days are ordered oldest -> newest
        days = [e["day"] for e in tl]
        assert days == sorted(days), f"timeline not oldest-first: {days}"
        # Today is last
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert tl[-1]["day"] == today_str, f"last day is not today: {tl[-1]['day']} vs {today_str}"
        # Oldest is 13 days ago
        expected_oldest = (datetime.now(timezone.utc) - timedelta(days=13)).strftime("%Y-%m-%d")
        assert tl[0]["day"] == expected_oldest, f"oldest day off: {tl[0]['day']} vs {expected_oldest}"


# ---------------------------------------------------------------------------
# 5. Auth / cross-user
# ---------------------------------------------------------------------------
class TestAnalyticsAuth:
    def test_no_auth_returns_401_or_403(self):
        # Fresh session, no cookies
        r = requests.get(f"{BASE_URL}/api/projects/{READY_PID}/share/analytics")
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}: {r.text}"

    def test_other_user_gets_404(self, other_auth_session):
        r = other_auth_session.get(f"{BASE_URL}/api/projects/{READY_PID}/share/analytics")
        assert r.status_code == 404, f"expected 404 for foreign project, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# 6. No share_slug -> empty
# ---------------------------------------------------------------------------
class TestAnalyticsNoShare:
    def test_project_without_share_returns_empty(self, auth_session):
        """Create a fresh draft project (no share_slug) and verify empty analytics."""
        # Use the existing DRAFT_PID from prior iterations if it exists; otherwise create a new draft
        r = auth_session.post(
            f"{BASE_URL}/api/projects",
            json={"topic": "TEST_iter26 no-share", "duration_sec": 30,
                  "style": "cinematic", "language": "en", "voice": "female"},
        )
        assert r.status_code == 200, f"create project failed: {r.status_code} {r.text}"
        new_pid = r.json()["id"]

        try:
            ra = auth_session.get(f"{BASE_URL}/api/projects/{new_pid}/share/analytics")
            assert ra.status_code == 200, f"analytics failed: {ra.status_code} {ra.text}"
            body = ra.json()
            assert body["share_enabled"] is False
            assert body["total_views"] == 0
            assert body["timeline"] == []
            assert body["top_referrers"] == []
            assert body["ua_breakdown"] == []
        finally:
            # Cleanup
            auth_session.delete(f"{BASE_URL}/api/projects/{new_pid}")


# ---------------------------------------------------------------------------
# 7. Multi-referrer aggregation
# ---------------------------------------------------------------------------
class TestMultiReferrer:
    def test_top_referrers_aggregates_correctly(self, auth_session, slug):
        # Simulate 5 hits with different referrers, some repeated
        hits = [
            ("https://linkedin.com/feed", "Mozilla/5.0 (X11; Linux) Chrome/120"),
            ("https://linkedin.com/feed", "Mozilla/5.0 (X11; Linux) Chrome/120"),
            ("https://linkedin.com/feed", "Mozilla/5.0 (X11; Linux) Chrome/120"),
            ("https://reddit.com/r/x", "Mozilla/5.0 (X11; Linux) Chrome/120"),
            ("https://reddit.com/r/x", "Mozilla/5.0 (X11; Linux) Chrome/120"),
            ("https://youtube.com/watch", "Mozilla/5.0 (iPhone) AppleWebKit"),
        ]
        for ref, ua in hits:
            r = requests.get(
                f"{BASE_URL}/api/public/videos/{slug}",
                headers={"Referer": ref, "User-Agent": ua},
                timeout=10,
            )
            assert r.status_code == 200, f"hit failed for ref={ref}: {r.status_code} {r.text[:200]}"
            import time; time.sleep(0.05)

        import time; time.sleep(0.7)

        r = auth_session.get(f"{BASE_URL}/api/projects/{READY_PID}/share/analytics")
        assert r.status_code == 200
        top = r.json()["top_referrers"]
        by_host = {t["host"]: t["count"] for t in top}
        # linkedin should have >=3, reddit >=2, youtube >=1
        assert by_host.get("linkedin.com", 0) >= 3, f"linkedin count wrong: {by_host}"
        assert by_host.get("reddit.com", 0) >= 2, f"reddit count wrong: {by_host}"
        assert by_host.get("youtube.com", 0) >= 1, f"youtube count wrong: {by_host}"
        # Sorted desc by count
        counts = [t["count"] for t in top]
        assert counts == sorted(counts, reverse=True), f"top_referrers not desc-sorted: {counts}"


# ---------------------------------------------------------------------------
# 8. Mongo indexes
# ---------------------------------------------------------------------------
class TestShareEventsIndexes:
    def test_compound_and_single_indexes_exist(self):
        async def _idx():
            cli = AsyncIOMotorClient(MONGO_URL); db = cli[DB_NAME]
            info = await db.share_events.index_information()
            cli.close()
            return info
        info = _run(_idx())
        compound_found = False
        at_only_found = False
        for name, spec in info.items():
            keys = list(dict(spec.get("key") or {}).keys())
            if keys == ["slug", "at_day"]:
                compound_found = True
            if keys == ["at"]:
                at_only_found = True
        assert compound_found, f"missing compound index (slug,at_day). Indexes: {list(info.keys())}"
        assert at_only_found, f"missing single-field index (at). Indexes: {list(info.keys())}"
