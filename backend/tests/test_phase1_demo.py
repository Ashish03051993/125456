"""Phase 1 additions — demo video, Book-a-Demo, richer analytics.

Verifies:
- Static media at /api/media/videos/demo.mp4 and /demo_poster.jpg
- POST /api/analytics/track accepts new event names + properties.source
- GET /api/admin/stats exposes demo_views, demo_impressions, book_demo_clicks, waitlist_clicks
- GET /api/admin/analytics returns conversion_by_source array
"""
import os
import uuid
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://script-to-video-382.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_TOK = os.environ.get("ADMIN_TOK", "test_admin_1784712404860")


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="session")
def http():
    s = requests.Session()
    return s


# --------------------------- Static media at /api/media ---------------------------
class TestStaticMedia:
    def test_demo_mp4_full_body(self, http):
        r = http.get(f"{API}/media/videos/demo.mp4", stream=True)
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("video/mp4"), r.headers
        # Full file should be ~7.4MB
        body = r.content
        assert len(body) >= 7_000_000, f"body too small: {len(body)}"

    def test_demo_poster_jpg(self, http):
        r = http.get(f"{API}/media/videos/demo_poster.jpg")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/jpeg"), r.headers
        assert len(r.content) > 10_000

    def test_missing_media_404(self, http):
        r = http.get(f"{API}/media/videos/does_not_exist.mp4")
        assert r.status_code == 404


# --------------------------- Track new events + attribution ---------------------------
NEW_EVENTS = [
    "waitlist_button_click",
    "demo_video_view",
    "demo_video_impression",
    "demo_video_completed",
    "book_demo_click",
    "book_demo_submit",
    "book_demo_success",
    "page_view",
]


class TestPhase1Events:
    session_id = f"TEST_phase1demo_{uuid.uuid4().hex[:8]}"
    src = f"TEST_src_{uuid.uuid4().hex[:6]}"

    @pytest.mark.parametrize("ev", NEW_EVENTS)
    def test_track_new_event(self, http, ev):
        r = http.post(f"{API}/analytics/track", json={
            "event": ev,
            "properties": {"source": TestPhase1Events.src, "medium": "social"},
            "session_id": TestPhase1Events.session_id,
            "path": "/",
        })
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True

    def test_conversion_by_source_reflects_events(self, http):
        # Fire a page_view + waitlist_signup with our test source
        http.post(f"{API}/analytics/track", json={
            "event": "page_view",
            "properties": {"source": TestPhase1Events.src, "medium": "social"},
            "session_id": TestPhase1Events.session_id,
            "path": "/",
        })
        # Waitlist signup with same source
        email = f"TEST_phase1demo_{uuid.uuid4().hex[:8]}@example.com"
        wr = http.post(f"{API}/waitlist", json={
            "email": email, "plan_interest": "enterprise",
            "use_case": f"DEMO_REQUEST · src={TestPhase1Events.src}",
        })
        assert wr.status_code == 200
        # Also track a waitlist_signup event with source attribution (mirrors what analytics.js would send)
        http.post(f"{API}/analytics/track", json={
            "event": "waitlist_signup",
            "properties": {"source": TestPhase1Events.src},
            "session_id": TestPhase1Events.session_id,
        })
        time.sleep(0.5)
        r = http.get(f"{API}/admin/analytics", headers=hdr(ADMIN_TOK))
        assert r.status_code == 200
        a = r.json()
        assert "conversion_by_source" in a, list(a.keys())
        rows = a["conversion_by_source"]
        assert isinstance(rows, list)
        # Row schema
        for row in rows:
            for k in ("source", "sessions", "signups", "conversion_pct"):
                assert k in row, f"missing key {k} in {row}"
            # demo_views optional key (present only when there is at least one demo_view row)
        # Our test source should exist with at least 1 signup
        our = [r for r in rows if r["source"] == TestPhase1Events.src]
        assert len(our) == 1, f"expected 1 row for {TestPhase1Events.src}, got {our}"
        assert our[0]["signups"] >= 1


# --------------------------- Admin stats – extra counters ---------------------------
class TestAdminStatsPhase1:
    def test_extra_phase1_counters(self, http):
        r = http.get(f"{API}/admin/stats", headers=hdr(ADMIN_TOK))
        assert r.status_code == 200
        s = r.json()
        for k in ("demo_views", "demo_impressions", "book_demo_clicks", "waitlist_clicks"):
            assert k in s, f"missing key {k}"
            assert isinstance(s[k], int), f"{k} should be int, got {type(s[k])}"
