"""
Iter-16 backend tests: credit-based pricing pivot.

Covers:
- GET /api/durations shape & tier correctness
- POST /api/projects (duration_sec, duration_min legacy, snapping, 402)
- POST /api/projects/{id}/generate credit deduction
- Free-tier auto-refill on /api/auth/me (idempotent within month, paid users skipped)
- Regression: /api/health, /api/formats, /api/waitlist (rate-limited), /api/admin/*
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://script-to-video-382.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "test_admin_1784712404860")

# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


def _seed_user(mongo, credits=3, plan="free", last_refill_at=None, email=None, role="user"):
    uid = f"TEST_iter16_{uuid.uuid4().hex[:8]}"
    tok = f"TEST_iter16_tok_{uuid.uuid4().hex[:8]}"
    email = email or f"{uid}@example.com"
    doc = {
        "user_id": uid,
        "email": email,
        "name": "Iter16 Test",
        "picture": "",
        "role": role,
        "credits": credits,
        "plan": plan,
        "created_at": datetime.now(timezone.utc),
    }
    if last_refill_at is not None:
        doc["last_refill_at"] = last_refill_at
    mongo.users.insert_one(doc)
    mongo.user_sessions.insert_one({
        "user_id": uid,
        "session_token": tok,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        "created_at": datetime.now(timezone.utc),
    })
    return uid, tok, email


@pytest.fixture
def seeded_user(mongo):
    uid, tok, email = _seed_user(mongo, credits=50, plan="free",
                                 last_refill_at=datetime.now(timezone.utc).isoformat())
    yield {"uid": uid, "token": tok, "email": email}
    # cleanup
    mongo.projects.delete_many({"user_id": uid})
    mongo.users.delete_one({"user_id": uid})
    mongo.user_sessions.delete_one({"user_id": uid})


def auth_headers(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------- Public durations endpoint ----------
class TestDurations:
    EXPECTED = [
        (30, 3, 3, "30 sec"), (45, 4, 4, "45 sec"), (60, 5, 5, "60 sec"),
        (90, 7, 7, "90 sec"), (120, 10, 9, "2 min"), (180, 15, 12, "3 min"),
        (300, 25, 16, "5 min"), (600, 50, 22, "10 min"),
    ]

    def test_durations_public_no_auth(self):
        r = requests.get(f"{API}/durations", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 8

    def test_durations_exact_tiers(self):
        r = requests.get(f"{API}/durations", timeout=15)
        rows = r.json()
        for expected, actual in zip(self.EXPECTED, rows):
            sec, cr, sc, lbl = expected
            assert actual["sec"] == sec
            assert actual["credits"] == cr
            assert actual["scenes"] == sc
            assert actual["label"] == lbl


# ---------- Project creation with credits ----------
class TestProjectCreation:
    def test_create_project_duration_sec_30(self, seeded_user, mongo):
        r = requests.post(f"{API}/projects",
                          json={"topic": "TEST_iter16 coffee", "duration_sec": 30},
                          headers=auth_headers(seeded_user["token"]), timeout=15)
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["duration_sec"] == 30
        assert p["credit_cost"] == 3
        assert p["duration_min"] == 1
        assert p["topic"] == "TEST_iter16 coffee"
        # Verify DB persistence
        db_doc = mongo.projects.find_one({"id": p["id"]}, {"_id": 0})
        assert db_doc and db_doc["credit_cost"] == 3 and db_doc["duration_sec"] == 30

    def test_create_project_duration_sec_90(self, seeded_user):
        r = requests.post(f"{API}/projects",
                          json={"topic": "TEST_iter16 90s", "duration_sec": 90},
                          headers=auth_headers(seeded_user["token"]), timeout=15)
        assert r.status_code == 200
        p = r.json()
        assert p["duration_sec"] == 90
        assert p["credit_cost"] == 7

    def test_create_project_legacy_duration_min(self, seeded_user):
        r = requests.post(f"{API}/projects",
                          json={"topic": "TEST_iter16 legacy", "duration_min": 3},
                          headers=auth_headers(seeded_user["token"]), timeout=15)
        assert r.status_code == 200
        p = r.json()
        assert p["duration_sec"] == 180
        assert p["credit_cost"] == 15

    def test_create_project_snap_unsupported_duration(self, seeded_user):
        # 200 should snap to nearest tier (180 or 300 depending on tie-break)
        r = requests.post(f"{API}/projects",
                          json={"topic": "TEST_iter16 snap", "duration_sec": 200},
                          headers=auth_headers(seeded_user["token"]), timeout=15)
        assert r.status_code == 200
        p = r.json()
        assert p["duration_sec"] in (180, 300)
        assert p["credit_cost"] in (15, 25)

    def test_insufficient_credits_returns_402(self, mongo):
        # New user with only 3 credits — requests 600s (50 credits)
        uid, tok, _ = _seed_user(mongo, credits=3, plan="free",
                                 last_refill_at=datetime.now(timezone.utc).isoformat())
        try:
            r = requests.post(f"{API}/projects",
                              json={"topic": "TEST_iter16 big", "duration_sec": 600},
                              headers=auth_headers(tok), timeout=15)
            assert r.status_code == 402, r.text
            body = r.json()
            detail = body.get("detail", "")
            assert "50 credits" in detail
            assert "600" in detail
            assert "3" in detail
        finally:
            mongo.users.delete_one({"user_id": uid})
            mongo.user_sessions.delete_one({"user_id": uid})
            mongo.projects.delete_many({"user_id": uid})


# ---------- Generation deducts credit_cost ----------
class TestGenerateDeductsCredits:
    def test_generate_decrements_by_credit_cost(self, mongo):
        # Seed with enough credits, create a 90-sec project (cost=7), start generate → decrement by 7
        uid, tok, _ = _seed_user(mongo, credits=20, plan="free",
                                 last_refill_at=datetime.now(timezone.utc).isoformat())
        try:
            r = requests.post(f"{API}/projects",
                              json={"topic": "TEST_iter16 deduct", "duration_sec": 90},
                              headers=auth_headers(tok), timeout=15)
            assert r.status_code == 200
            pid = r.json()["id"]
            # start_generate
            g = requests.post(f"{API}/projects/{pid}/generate",
                              headers=auth_headers(tok), timeout=15)
            assert g.status_code == 200
            # Give the deduction a moment to persist (BackgroundTask kicks off after response is queued)
            time.sleep(0.5)
            u = mongo.users.find_one({"user_id": uid}, {"_id": 0})
            assert u["credits"] == 20 - 7, f"expected 13 got {u['credits']}"
        finally:
            mongo.users.delete_one({"user_id": uid})
            mongo.user_sessions.delete_one({"user_id": uid})
            mongo.projects.delete_many({"user_id": uid})


# ---------- Free-tier refill ----------
class TestFreeRefill:
    def test_refill_new_free_user_no_last_refill(self, mongo):
        uid, tok, _ = _seed_user(mongo, credits=0, plan="free", last_refill_at=None)
        try:
            r = requests.get(f"{API}/auth/me", headers=auth_headers(tok), timeout=15)
            assert r.status_code == 200
            user = r.json()
            assert user["credits"] == 3
            assert user.get("last_refill_at") is not None
        finally:
            mongo.users.delete_one({"user_id": uid})
            mongo.user_sessions.delete_one({"user_id": uid})

    def test_refill_idempotent_same_month(self, mongo):
        # Already refilled this month → credits should NOT top-up above current
        # Set credits low (1) and last_refill = today → no refill fires
        now = datetime.now(timezone.utc).isoformat()
        uid, tok, _ = _seed_user(mongo, credits=1, plan="free", last_refill_at=now)
        try:
            r = requests.get(f"{API}/auth/me", headers=auth_headers(tok), timeout=15)
            assert r.status_code == 200
            assert r.json()["credits"] == 1, "must not refill twice within same month"
        finally:
            mongo.users.delete_one({"user_id": uid})
            mongo.user_sessions.delete_one({"user_id": uid})

    def test_refill_previous_month_triggers(self, mongo):
        # last_refill_at ~40 days ago → refill fires
        prev = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
        uid, tok, _ = _seed_user(mongo, credits=0, plan="free", last_refill_at=prev)
        try:
            r = requests.get(f"{API}/auth/me", headers=auth_headers(tok), timeout=15)
            assert r.status_code == 200
            assert r.json()["credits"] == 3
        finally:
            mongo.users.delete_one({"user_id": uid})
            mongo.user_sessions.delete_one({"user_id": uid})

    def test_paid_user_not_refilled(self, mongo):
        # Paid user with 0 credits → should stay 0 (no refill)
        uid, tok, _ = _seed_user(mongo, credits=0, plan="starter", last_refill_at=None)
        try:
            r = requests.get(f"{API}/auth/me", headers=auth_headers(tok), timeout=15)
            assert r.status_code == 200
            assert r.json()["credits"] == 0, "paid plan should NOT auto-refill"
        finally:
            mongo.users.delete_one({"user_id": uid})
            mongo.user_sessions.delete_one({"user_id": uid})

    def test_refill_does_not_reduce_existing_credits(self, mongo):
        # Existing user with 10 credits, prev-month refill → should top up to max(10, 3) = 10
        prev = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
        uid, tok, _ = _seed_user(mongo, credits=10, plan="free", last_refill_at=prev)
        try:
            r = requests.get(f"{API}/auth/me", headers=auth_headers(tok), timeout=15)
            assert r.status_code == 200
            assert r.json()["credits"] == 10
        finally:
            mongo.users.delete_one({"user_id": uid})
            mongo.user_sessions.delete_one({"user_id": uid})


# ---------- Regression: core public endpoints ----------
class TestRegression:
    def test_health(self):
        r = requests.get(f"{API}/health", timeout=15)
        assert r.status_code in (200, 503)
        body = r.json()
        assert "status" in body

    def test_formats(self):
        r = requests.get(f"{API}/formats", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_waitlist_still_accepts(self, mongo):
        email = f"TEST_iter16_wl_{uuid.uuid4().hex[:6]}@ex.com"
        try:
            r = requests.post(f"{API}/waitlist", json={"email": email}, timeout=15)
            # Either 200 (accepted) or 429 (rate limited from earlier tests).
            assert r.status_code in (200, 429), r.text
        finally:
            mongo.waitlist.delete_many({"email": email})

    def test_admin_stats(self):
        r = requests.get(f"{API}/admin/stats",
                         headers=auth_headers(ADMIN_TOKEN), timeout=15)
        # 200 with data, or 401/403 if seeded token no longer valid
        assert r.status_code in (200, 401, 403), r.text

    def test_admin_attribution_matrix(self):
        r = requests.get(f"{API}/admin/attribution-matrix",
                         headers=auth_headers(ADMIN_TOKEN), timeout=15)
        assert r.status_code in (200, 401, 403), r.text

    def test_admin_sanity(self):
        r = requests.get(f"{API}/admin/sanity",
                         headers=auth_headers(ADMIN_TOKEN), timeout=15)
        assert r.status_code in (200, 401, 403), r.text

    def test_short_referral(self):
        # /api/short/{slug} — endpoint reachable; 404 when slug missing is valid regression signal
        r = requests.get(f"{API}/short/script-to-video-382",
                         allow_redirects=False, timeout=15)
        # Endpoint should route: 200 (found) or 404 (unknown slug) both prove route is wired.
        assert r.status_code in (200, 302, 307, 404), r.text

    def test_analytics_track(self):
        r = requests.post(f"{API}/analytics/track",
                          json={"event": "TEST_iter16_ping", "properties": {"src": "pytest"}},
                          timeout=15)
        assert r.status_code in (200, 429), r.text
