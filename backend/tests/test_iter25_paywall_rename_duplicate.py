"""Iteration 25 backend tests:
- Structured 402 responses (paid_feature_required + insufficient_credits)
- PATCH /projects/{pid}/title (rename)
- POST /projects/{pid}/duplicate
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://script-to-video-382.preview.emergentagent.com").rstrip("/")
# Read from frontend/.env directly to avoid relying on shell env for the testing agent
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL"):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"

# Mongo direct access for plan flips
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

PRO_EMAIL = "newuser@test.com"
PRO_PASSWORD = "secret123"


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="session")
def pro_session():
    """Login as PRO user; guarantee plan=pro credits=100 first."""
    dbc = MongoClient(MONGO_URL)[DB_NAME]
    dbc.users.update_one({"email": PRO_EMAIL}, {"$set": {"plan": "pro", "credits": 100}})
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"identifier": PRO_EMAIL, "password": PRO_PASSWORD})
    assert r.status_code == 200, f"pro login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def free_session():
    """Create a fresh free-plan user for paywall tests."""
    s = requests.Session()
    rand = uuid.uuid4().hex[:8]
    ident = f"TEST_free_{rand}@example.com"
    r = s.post(f"{API}/auth/register", json={
        "name": "Free Test",
        "identifier": ident,
        "password": "secret123",
    })
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    return s


# ---------- Structured 402 tests ----------
class TestStructured402:
    def test_free_user_talking_head_returns_structured_402(self, free_session):
        r = free_session.post(f"{API}/projects", json={
            "topic": "TEST paywall talking head",
            "duration_sec": 30,
            "talking_head": True,
        })
        assert r.status_code == 402, f"Expected 402, got {r.status_code}: {r.text}"
        body = r.json()
        assert isinstance(body.get("detail"), dict), f"detail must be dict, got: {body}"
        d = body["detail"]
        assert d["code"] == "paid_feature_required"
        assert d["feature"] == "talking_head"
        assert d["upgrade_url"] == "/pricing"
        assert "message" in d and isinstance(d["message"], str)

    def test_free_user_insufficient_credits_structured_402(self, free_session):
        # Free user has 3 credits. Request 10-min video (needs 50)
        r = free_session.post(f"{API}/projects", json={
            "topic": "TEST paywall insufficient credits",
            "duration_sec": 600,
        })
        assert r.status_code == 402, f"Expected 402, got {r.status_code}: {r.text}"
        d = r.json()["detail"]
        assert isinstance(d, dict)
        assert d["code"] == "insufficient_credits"
        assert d["needed"] == 50
        assert d["have"] == 3
        assert d["duration_sec"] == 600
        assert d["upgrade_url"] == "/pricing"


# ---------- Rename tests ----------
class TestRename:
    def test_rename_project_in_draft(self, pro_session, db):
        # Create a draft project
        r = pro_session.post(f"{API}/projects", json={"topic": "TEST rename draft", "duration_sec": 30})
        assert r.status_code == 200
        pid = r.json()["id"]
        # Rename
        r = pro_session.patch(f"{API}/projects/{pid}/title", json={"title": "Renamed title A"})
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "Renamed title A"
        # Verify persistence via GET
        r = pro_session.get(f"{API}/projects/{pid}")
        assert r.status_code == 200
        assert r.json()["title"] == "Renamed title A"
        # Cleanup
        pro_session.delete(f"{API}/projects/{pid}")

    def test_rename_project_any_status(self, pro_session, db):
        # Create draft then flip status to "ready" via DB
        r = pro_session.post(f"{API}/projects", json={"topic": "TEST rename ready", "duration_sec": 30})
        assert r.status_code == 200
        pid = r.json()["id"]
        db.projects.update_one({"id": pid}, {"$set": {"status": "ready"}})
        r = pro_session.patch(f"{API}/projects/{pid}/title", json={"title": "Renamed even when ready"})
        assert r.status_code == 200, f"Rename should work in any status, got {r.status_code}: {r.text}"
        assert r.json()["title"] == "Renamed even when ready"
        pro_session.delete(f"{API}/projects/{pid}")

    def test_rename_empty_title_400(self, pro_session):
        r = pro_session.post(f"{API}/projects", json={"topic": "TEST rename empty", "duration_sec": 30})
        pid = r.json()["id"]
        r = pro_session.patch(f"{API}/projects/{pid}/title", json={"title": "   "})
        assert r.status_code == 400
        pro_session.delete(f"{API}/projects/{pid}")

    def test_rename_too_long_400(self, pro_session):
        r = pro_session.post(f"{API}/projects", json={"topic": "TEST rename long", "duration_sec": 30})
        pid = r.json()["id"]
        r = pro_session.patch(f"{API}/projects/{pid}/title", json={"title": "x" * 201})
        assert r.status_code == 400
        pro_session.delete(f"{API}/projects/{pid}")

    def test_rename_unknown_project_404(self, pro_session):
        r = pro_session.patch(f"{API}/projects/proj_nonexistent999/title", json={"title": "hi"})
        assert r.status_code == 404

    def test_rename_wrong_user_404(self, pro_session, free_session):
        # Create with pro user
        r = pro_session.post(f"{API}/projects", json={"topic": "TEST rename owner", "duration_sec": 30})
        pid = r.json()["id"]
        # Try to rename with free user (different user_id)
        r2 = free_session.patch(f"{API}/projects/{pid}/title", json={"title": "hack"})
        assert r2.status_code == 404
        pro_session.delete(f"{API}/projects/{pid}")


# ---------- Duplicate tests ----------
class TestDuplicate:
    def test_duplicate_project_copies_fields(self, pro_session):
        # Create original
        r = pro_session.post(f"{API}/projects", json={
            "topic": "TEST original for duplicate",
            "duration_sec": 60,
            "style": "Cinematic",
            "language": "English",
            "voice": "male",
            "dialogue_mode": True,
        })
        assert r.status_code == 200
        orig = r.json()
        pid = orig["id"]
        # Rename original for suffix check
        pro_session.patch(f"{API}/projects/{pid}/title", json={"title": "Original Doc"})
        # Duplicate
        r = pro_session.post(f"{API}/projects/{pid}/duplicate")
        assert r.status_code == 200, r.text
        dup = r.json()
        assert dup["id"] != pid
        assert dup["topic"] == orig["topic"]
        assert dup["duration_sec"] == 60
        assert dup["style"] == "Cinematic"
        assert dup["language"] == "English"
        assert dup["voice"] == "male"
        assert dup["dialogue_mode"] is True
        assert dup["credit_cost"] == 5
        assert dup["status"] == "draft"
        assert dup["progress"] == 0
        assert dup.get("video_url") in (None, "",), f"video_url should be absent, got: {dup.get('video_url')}"
        assert dup["scenes"] == []
        assert dup["title"] == "Original Doc (copy)"
        # Cleanup
        pro_session.delete(f"{API}/projects/{pid}")
        pro_session.delete(f"{API}/projects/{dup['id']}")

    def test_duplicate_talking_head_by_free_user_returns_402(self, pro_session, db):
        """Create talking-head project as pro, flip user to free, then duplicate."""
        r = pro_session.post(f"{API}/projects", json={
            "topic": "TEST th duplicate", "duration_sec": 30, "talking_head": True,
        })
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        # Flip to free
        db.users.update_one({"email": PRO_EMAIL}, {"$set": {"plan": "free", "credits": 2}})
        try:
            r = pro_session.post(f"{API}/projects/{pid}/duplicate")
            assert r.status_code == 402, f"Expected 402, got {r.status_code}: {r.text}"
            d = r.json()["detail"]
            assert d["code"] == "paid_feature_required"
            assert d["feature"] == "talking_head"
        finally:
            # RESTORE
            db.users.update_one({"email": PRO_EMAIL}, {"$set": {"plan": "pro", "credits": 100}})
            pro_session.delete(f"{API}/projects/{pid}")

    def test_duplicate_insufficient_credits_returns_402(self, pro_session, db):
        # Create expensive project (600 sec = 50 credits)
        r = pro_session.post(f"{API}/projects", json={"topic": "TEST big duplicate", "duration_sec": 600})
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        db.users.update_one({"email": PRO_EMAIL}, {"$set": {"credits": 5}})
        try:
            r = pro_session.post(f"{API}/projects/{pid}/duplicate")
            assert r.status_code == 402
            d = r.json()["detail"]
            assert d["code"] == "insufficient_credits"
            assert d["needed"] == 50
            assert d["have"] == 5
            assert d["duration_sec"] == 600
        finally:
            db.users.update_one({"email": PRO_EMAIL}, {"$set": {"plan": "pro", "credits": 100}})
            pro_session.delete(f"{API}/projects/{pid}")

    def test_duplicate_unknown_project_404(self, pro_session):
        r = pro_session.post(f"{API}/projects/proj_doesnotexist99/duplicate")
        assert r.status_code == 404


# ---------- Cleanup + Restore ----------
def test_zzz_restore_pro_user():
    dbc = MongoClient(MONGO_URL)[DB_NAME]
    dbc.users.update_one({"email": PRO_EMAIL}, {"$set": {"plan": "pro", "credits": 100}})
    u = dbc.users.find_one({"email": PRO_EMAIL})
    assert u["plan"] == "pro"
    assert u["credits"] == 100
    # Clean up test-created data
    dbc.projects.delete_many({"topic": {"$regex": "^TEST "}})
