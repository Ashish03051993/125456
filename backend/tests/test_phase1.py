"""Phase 1 pivot backend tests: waitlist, analytics, admin waitlist/analytics, billing stub."""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://script-to-video-382.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

# Use admin token requested by main agent for Phase 2 tests
ADMIN_TOK = os.environ.get("ADMIN_TOK", "test_admin_1784712404860")
USER_TOK = os.environ.get("USER_TOK", "test_user_1784715294657")


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="session")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --------------------------- Waitlist ---------------------------
class TestWaitlist:
    unique_email = f"TEST_phase1_{uuid.uuid4().hex[:8]}@example.com"

    def test_join_valid_email(self, http):
        r = http.post(f"{API}/waitlist", json={
            "email": TestWaitlist.unique_email,
            "name": "TEST User",
            "use_case": "product explainers",
            "plan_interest": "pro",
        })
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["ok"] is True
        assert b["already_joined"] is False
        assert isinstance(b["position"], int) and b["position"] > 0
        TestWaitlist.first_position = b["position"]

    def test_duplicate_returns_already_joined(self, http):
        r = http.post(f"{API}/waitlist", json={
            "email": TestWaitlist.unique_email,
            "plan_interest": "business",
        })
        assert r.status_code == 200
        b = r.json()
        assert b["already_joined"] is True
        assert b["position"] == TestWaitlist.first_position

    def test_invalid_email_returns_400(self, http):
        r = http.post(f"{API}/waitlist", json={"email": "not-an-email"})
        assert r.status_code == 400

    def test_email_case_insensitive_and_trimmed(self, http):
        r = http.post(f"{API}/waitlist",
                      json={"email": "  " + TestWaitlist.unique_email.upper() + "  "})
        assert r.status_code == 200
        assert r.json()["already_joined"] is True


# --------------------------- Analytics ---------------------------
class TestAnalytics:
    session_id = f"TEST_sess_{uuid.uuid4().hex[:8]}"
    event_name = f"TEST_evt_{uuid.uuid4().hex[:6]}"

    def test_track_valid_event(self, http):
        r = http.post(f"{API}/analytics/track", json={
            "event": TestAnalytics.event_name,
            "properties": {"foo": "bar", "n": 3},
            "session_id": TestAnalytics.session_id,
            "path": "/",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_track_invalid_event_empty(self, http):
        r = http.post(f"{API}/analytics/track", json={"event": ""})
        assert r.status_code == 400

    def test_track_invalid_event_too_long(self, http):
        r = http.post(f"{API}/analytics/track", json={"event": "x" * 61})
        assert r.status_code == 400

    def test_event_visible_in_admin_analytics(self, http):
        # Ensure previous track has flushed
        time.sleep(0.5)
        r = http.get(f"{API}/admin/analytics", headers=hdr(ADMIN_TOK))
        assert r.status_code == 200, r.text
        a = r.json()
        events = {e["event"] for e in a["by_event"]}
        assert TestAnalytics.event_name in events, f"Test event not persisted; events: {events}"


# --------------------------- Admin waitlist ---------------------------
class TestAdminWaitlist:
    def test_requires_admin(self, http):
        r = http.get(f"{API}/admin/waitlist", headers=hdr(USER_TOK))
        assert r.status_code == 403

    def test_unauthenticated(self, http):
        r = http.get(f"{API}/admin/waitlist")
        assert r.status_code == 401

    def test_admin_ok(self, http):
        r = http.get(f"{API}/admin/waitlist", headers=hdr(ADMIN_TOK))
        assert r.status_code == 200, r.text
        b = r.json()
        assert "count" in b and "entries" in b and "by_plan_interest" in b
        assert b["count"] == len(b["entries"])
        # No mongo _id leak
        for row in b["entries"]:
            assert "_id" not in row
            assert "email" in row and "position" in row
        # Seeded rows present
        emails = {r["email"] for r in b["entries"]}
        assert "early.user@example.com" in emails


# --------------------------- Admin analytics ---------------------------
class TestAdminAnalytics:
    def test_requires_admin(self, http):
        r = http.get(f"{API}/admin/analytics", headers=hdr(USER_TOK))
        assert r.status_code == 403

    def test_unauthenticated(self, http):
        r = http.get(f"{API}/admin/analytics")
        assert r.status_code == 401

    def test_admin_ok(self, http):
        r = http.get(f"{API}/admin/analytics", headers=hdr(ADMIN_TOK))
        assert r.status_code == 200, r.text
        a = r.json()
        for k in ("days", "total_events", "unique_sessions", "waitlist_total", "by_event", "by_day"):
            assert k in a, f"missing key {k}"
        assert isinstance(a["by_event"], list)
        assert isinstance(a["by_day"], list)


# --------------------------- Admin stats (extended) ---------------------------
class TestAdminStatsExtended:
    def test_new_phase1_fields(self, http):
        r = http.get(f"{API}/admin/stats", headers=hdr(ADMIN_TOK))
        assert r.status_code == 200
        s = r.json()
        for k in ("waitlist_total", "waitlist_24h", "events_24h", "waitlist_by_plan"):
            assert k in s, f"missing key {k}"
        assert isinstance(s["waitlist_by_plan"], dict)


# --------------------------- Billing stub ---------------------------
class TestBillingStub:
    def test_status_disabled(self, http):
        r = http.get(f"{API}/billing/status")
        assert r.status_code == 200
        b = r.json()
        assert b == {"enabled": False, "phase": "waitlist"}

    def test_checkout_501(self, http):
        r = http.post(f"{API}/billing/checkout")
        assert r.status_code == 501

    def test_webhook_501(self, http):
        r = http.post(f"{API}/billing/webhook")
        assert r.status_code == 501
