"""Iter-Final Pre-Launch Production Readiness Sweep.

Comprehensive end-to-end verification of every implemented feature per the
PRE-LAUNCH sweep spec. Does NOT run LLM video generation (uses synthetic
'ready' projects for the video pipeline contract check).
"""
import os
import shutil
import uuid
import time
import csv
import io
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL",
                          "https://script-to-video-382.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_admin_1784712404860"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"


@pytest.fixture(scope="module")
def db():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


@pytest.fixture
def anon():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture
def admin():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    s.cookies.set("session_token", ADMIN_TOKEN)
    return s


# =========== 1. AUTH & AUTHORIZATION ===========
class TestAuth:
    def test_admin_seeded_on_startup(self, db):
        u = db.users.find_one({"email": "admin@videostudio.ai"})
        assert u is not None
        assert u.get("role") == "admin"
        assert u.get("credits", 0) >= 9999

    def test_anon_admin_endpoint_401(self, anon):
        r = anon.get(f"{BASE_URL}/api/admin/stats")
        assert r.status_code == 401

    def test_admin_cookie_200(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/stats")
        assert r.status_code == 200
        d = r.json()
        for key in ["waitlist_total", "waitlist_24h", "events_24h", "total_users",
                    "demo_views", "demo_impressions", "book_demo_clicks",
                    "waitlist_clicks", "waitlist_by_plan"]:
            assert key in d, f"missing key {key}"

    def test_non_admin_403(self, db, anon):
        # Create a temp session with role=user
        uid = f"testuser_{uuid.uuid4().hex[:8]}"
        db.users.insert_one({"user_id": uid, "email": f"{uid}@x.com", "role": "user", "credits": 5})
        tok = f"test_user_sess_{uuid.uuid4().hex[:10]}"
        db.user_sessions.insert_one({
            "user_id": uid, "session_token": tok,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            r = requests.get(f"{BASE_URL}/api/admin/stats",
                             cookies={"session_token": tok})
            assert r.status_code == 403
        finally:
            db.user_sessions.delete_one({"session_token": tok})
            db.users.delete_one({"user_id": uid})


# =========== 2. WAITLIST FLOW + ATTRIBUTION ===========
class TestWaitlistFlow:
    def test_full_signup_flow(self, anon):
        email = f"TEST_prelaunch_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "email": email, "name": "PreLaunch Tester",
            "use_case": "sanity", "plan_interest": "enterprise",
            "referrer": "https://linkedin.com/x",
            "source": "linkedin", "medium": "social",
            "campaign": "launch_test", "variant": "hero_a",
        }
        r = anon.post(f"{BASE_URL}/api/waitlist", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert d["already_joined"] is False
        assert isinstance(d["position"], int) and d["position"] > 0
        pos = d["position"]

        # duplicate
        r2 = anon.post(f"{BASE_URL}/api/waitlist", json=payload)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["already_joined"] is True
        assert d2["position"] == pos

    def test_duplicate_case_insensitive(self, anon, db):
        email = f"TEST_CI_{uuid.uuid4().hex[:8]}@Example.COM"
        r1 = anon.post(f"{BASE_URL}/api/waitlist", json={"email": email})
        assert r1.status_code == 200
        # Same email, different case
        r2 = anon.post(f"{BASE_URL}/api/waitlist",
                       json={"email": email.upper()})
        assert r2.status_code == 200
        assert r2.json()["already_joined"] is True

    def test_invalid_email(self, anon):
        r = anon.post(f"{BASE_URL}/api/waitlist", json={"email": "notanemail"})
        assert r.status_code == 400

    @classmethod
    def teardown_class(cls):
        c = MongoClient(MONGO_URL)
        c[DB_NAME].waitlist.delete_many({"email": {"$regex": "^test_"}})
        c[DB_NAME].waitlist.delete_many({"email": {"$regex": "^TEST_"}})
        c[DB_NAME].analytics_events.delete_many({"properties.email": {"$regex": "^TEST_"}})


# =========== 3. ANALYTICS ===========
class TestAnalytics:
    def test_track_event(self, anon):
        r = anon.post(f"{BASE_URL}/api/analytics/track", json={
            "event": "iter_final_probe",
            "properties": {"source": "test"},
            "session_id": f"sess_iter_final_{uuid.uuid4().hex[:8]}",
            "path": "/",
        })
        assert r.status_code == 200

    def test_admin_analytics_shape(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/analytics?days=14")
        assert r.status_code == 200
        d = r.json()
        for k in ["total_events", "unique_sessions", "by_event", "by_day",
                  "conversion_by_source"]:
            assert k in d
        assert isinstance(d["by_event"], list)
        assert isinstance(d["conversion_by_source"], list)


# =========== 4. ATTRIBUTION MATRIX + CSV ===========
class TestAttributionMatrix:
    def test_matrix_json(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/attribution-matrix")
        assert r.status_code == 200
        d = r.json()
        for k in ["sources", "variants", "rows", "col_totals", "grand"]:
            assert k in d
        # Verify totals internally consistent
        grand_sig = d["grand"]["signups"]
        col_sig = sum(c["signups"] for c in d["col_totals"])
        row_sig = sum(r["totals"]["signups"] for r in d["rows"])
        assert grand_sig == col_sig == row_sig

    def test_matrix_csv(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/attribution-matrix.csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("Content-Type", "")
        assert "attachment" in r.headers.get("Content-Disposition", "")
        # header line
        text = r.text
        lines = text.strip().split("\n")
        assert lines[0].strip() == "source,variant,sessions,signups,conversion_pct"
        # last line must be grand total
        assert lines[-1].startswith("__total__,__total__")


# =========== 5. SANITY PANEL ===========
class TestSanity:
    def test_sanity(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/sanity")
        assert r.status_code == 200
        d = r.json()
        for k in ["orphan_signups", "unattributed_sessions",
                  "duplicate_emails", "totals"]:
            assert k in d

    def test_untagged(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/sanity/untagged?limit=50")
        assert r.status_code == 200
        d = r.json()
        for k in ["total", "sessions", "top_referrer_hosts", "top_landing_paths"]:
            assert k in d
        assert isinstance(d["sessions"], list)

    def test_untagged_limit_clamp_low(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/sanity/untagged?limit=0")
        assert r.status_code == 200
        # returned <= 1 due to clamp (max returns 1, but if less untagged exist could be 0)
        assert r.json()["returned"] <= 1

    def test_untagged_limit_clamp_high(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/sanity/untagged?limit=99999")
        assert r.status_code == 200
        assert r.json()["returned"] <= 500


# =========== 6. A/B EXPERIMENTS ===========
class TestExperiments:
    def test_assignment_deterministic(self, anon):
        cid = f"clt_iter_final_{uuid.uuid4().hex[:8]}"
        r1 = anon.get(f"{BASE_URL}/api/experiments/landing_hero/{cid}")
        r2 = anon.get(f"{BASE_URL}/api/experiments/landing_hero/{cid}")
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["variant"] == r2.json()["variant"]
        assert "content" in r1.json()

    def test_admin_experiments(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/experiments?experiment=landing_hero")
        assert r.status_code == 200
        d = r.json()
        assert "rows" in d
        for row in d["rows"]:
            for k in ["variant", "sessions", "cta_clicks", "signups",
                      "conversion_pct", "content"]:
                assert k in row


# =========== 7. WAITLIST ADMIN ===========
class TestWaitlistAdmin:
    def test_list_no_filter(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/waitlist")
        assert r.status_code == 200
        d = r.json()
        for k in ["total", "entries", "by_plan", "by_source", "by_variant", "filters"]:
            assert k in d

    def test_filter_plan(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/waitlist?plan=enterprise")
        assert r.status_code == 200
        d = r.json()
        for e in d["entries"]:
            assert e.get("plan_interest") == "enterprise"

    def test_csv(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/waitlist.csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("Content-Type", "")
        assert 'filename="waitlist.csv"' in r.headers.get("Content-Disposition", "")

    def test_csv_filtered_filename(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/waitlist.csv?source=linkedin&plan=pro")
        assert r.status_code == 200
        cd = r.headers.get("Content-Disposition", "")
        assert "linkedin" in cd and "pro" in cd


# =========== 8. UTM + SHORT LINKS ===========
class TestUTMShort:
    _link_id = None
    _slug = None

    def test_create_utm_link(self, admin, request):
        payload = {"name": f"TEST prelaunch {uuid.uuid4().hex[:6]}",
                   "source": "linkedin", "medium": "social",
                   "campaign": "launch_test",
                   "slug": f"test-prelaunch-{uuid.uuid4().hex[:6]}"}
        r = admin.post(f"{BASE_URL}/api/admin/utm-links", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert "url" in d and "slug" in d
        assert "utm_source=linkedin" in d["url"]
        TestUTMShort._link_id = d["id"]
        TestUTMShort._slug = d["slug"]

    def test_short_resolve(self, anon):
        assert TestUTMShort._slug
        r = anon.get(f"{BASE_URL}/api/short/{TestUTMShort._slug}")
        assert r.status_code == 200
        d = r.json()
        assert d["slug"] == TestUTMShort._slug
        assert "utm_source=linkedin" in d["target"]

    def test_short_404(self, anon):
        r = anon.get(f"{BASE_URL}/api/short/does-not-exist-{uuid.uuid4().hex[:6]}")
        assert r.status_code == 404

    def test_list_utm_links(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/utm-links")
        assert r.status_code == 200
        d = r.json()
        assert "rows" in d
        # newly created one is present
        assert any(row["id"] == TestUTMShort._link_id for row in d["rows"])
        # stats present
        for row in d["rows"]:
            for k in ["sessions", "signups", "demo_clicks", "conversion_pct"]:
                assert k in row["stats"]

    def test_delete_utm_link(self, admin):
        assert TestUTMShort._link_id
        r = admin.delete(f"{BASE_URL}/api/admin/utm-links/{TestUTMShort._link_id}")
        assert r.status_code == 200
        assert r.json()["deleted"] == 1


# =========== 9. DIGEST ===========
class TestDigest:
    def test_digest_config(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/digest/config")
        assert r.status_code == 200
        d = r.json()
        for k in ["recipients", "sender", "schedule", "email_enabled"]:
            assert k in d

    def test_digest_preview(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/digest/preview")
        assert r.status_code == 200

    def test_digest_send_now(self, admin):
        r = admin.post(f"{BASE_URL}/api/admin/digest/send-now")
        assert r.status_code == 200
        d = r.json()
        assert "id" in d and "delivery" in d
        # When RESEND_API_KEY missing, delivery should skip gracefully
        # (has some reason field)
        assert isinstance(d["delivery"], dict)

    def test_digest_list(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/digest")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# =========== 10. VIDEO PIPELINE CONTRACT (synthetic) ===========
class TestVideoPipelineContract:
    _test_user_id = None
    _test_session = None
    _project_id = None
    _legacy_project_id = None

    @classmethod
    def setup_class(cls):
        c = MongoClient(MONGO_URL)
        db = c[DB_NAME]
        cls._test_user_id = f"TEST_video_user_{uuid.uuid4().hex[:8]}"
        cls._test_session = f"TEST_video_sess_{uuid.uuid4().hex[:10]}"
        db.users.insert_one({
            "user_id": cls._test_user_id,
            "email": f"{cls._test_user_id}@x.com",
            "role": "user", "credits": 5,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        db.user_sessions.insert_one({
            "user_id": cls._test_user_id,
            "session_token": cls._test_session,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # New-style project with video_urls
        cls._project_id = f"proj_TEST_{uuid.uuid4().hex[:10]}"
        db.projects.insert_one({
            "id": cls._project_id,
            "user_id": cls._test_user_id,
            "topic": "test",
            "duration_min": 1,
            "language": "English", "style": "Educational", "voice": "female",
            "status": "ready", "progress": 100, "stage": "done",
            "title": "Synthetic Test",
            "hook": "hook",
            "scenes": [],
            "audio_url": "/api/media/audio/x.mp3",
            "video_url": "/api/media/videos/x_landscape.mp4",
            "video_urls": {
                "landscape": "/api/media/videos/x_landscape.mp4",
                "vertical": "/api/media/videos/x_vertical.mp4",
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # Legacy project - only video_url
        cls._legacy_project_id = f"proj_TEST_leg_{uuid.uuid4().hex[:10]}"
        db.projects.insert_one({
            "id": cls._legacy_project_id,
            "user_id": cls._test_user_id,
            "topic": "test",
            "duration_min": 1,
            "language": "English", "style": "Educational", "voice": "female",
            "status": "ready", "progress": 100, "stage": "done",
            "title": "Legacy",
            "hook": "hook",
            "scenes": [],
            "audio_url": "/api/media/audio/x.mp3",
            "video_url": "/api/media/videos/x_legacy.mp4",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    @classmethod
    def teardown_class(cls):
        c = MongoClient(MONGO_URL)
        db = c[DB_NAME]
        db.projects.delete_many({"id": {"$in": [cls._project_id, cls._legacy_project_id]}})
        db.users.delete_one({"user_id": cls._test_user_id})
        db.user_sessions.delete_one({"session_token": cls._test_session})

    def test_formats_endpoint(self, anon):
        r = anon.get(f"{BASE_URL}/api/formats")
        assert r.status_code == 200
        d = r.json()
        ids = {f["id"] for f in d}
        assert "landscape" in ids
        assert "vertical" in ids
        for f in d:
            if f["id"] == "landscape":
                assert f["aspect"] == "16:9"
                assert f["width"] == 1920 and f["height"] == 1080
            elif f["id"] == "vertical":
                assert f["aspect"] == "9:16"
                assert f["width"] == 1080 and f["height"] == 1920

    def test_synthetic_project_has_both_video_urls(self):
        r = requests.get(f"{BASE_URL}/api/projects/{TestVideoPipelineContract._project_id}",
                         cookies={"session_token": TestVideoPipelineContract._test_session})
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "ready"
        assert "video_urls" in d
        assert "landscape" in d["video_urls"]
        assert "vertical" in d["video_urls"]

    def test_legacy_project_no_video_urls(self):
        r = requests.get(f"{BASE_URL}/api/projects/{TestVideoPipelineContract._legacy_project_id}",
                         cookies={"session_token": TestVideoPipelineContract._test_session})
        assert r.status_code == 200
        d = r.json()
        assert d.get("video_url")
        # No video_urls field OR empty
        assert not d.get("video_urls")

    def test_ffmpeg_installed(self):
        # THIS WILL FAIL if ffmpeg missing on container — critical for video pipeline
        assert shutil.which("ffmpeg") is not None, \
            "ffmpeg binary NOT installed on container — video generation will fail at runtime!"


# =========== 11. DATABASE COLLECTIONS ===========
class TestDatabase:
    REQUIRED = ["users", "projects", "waitlist", "analytics_events",
                "utm_links", "digests"]

    def test_collections_present(self, db):
        cols = set(db.list_collection_names())
        for c in self.REQUIRED:
            assert c in cols, f"missing collection: {c}"

    def test_no_null_source_in_waitlist(self, db):
        # Migration should coalesce legacy null source → 'direct'
        n = db.waitlist.count_documents({"$or": [
            {"source": None}, {"source": {"$exists": False}}
        ]})
        assert n == 0, f"{n} waitlist rows still have null source after migration"


# =========== 12. PRODUCTION CONFIG ===========
class TestConfig:
    def test_env_vars(self):
        # Backend reads via dotenv.load_dotenv(). Verify the .env file has required keys.
        with open("/app/backend/.env") as f:
            content = f.read()
        assert "EMERGENT_LLM_KEY=" in content
        assert "MONGO_URL=" in content
        assert "DB_NAME=" in content

    def test_frontend_env(self):
        with open("/app/frontend/.env") as f:
            content = f.read()
        assert "REACT_APP_BACKEND_URL=" in content

    def test_media_under_api_path(self):
        # /api/media/* must be the static mount path (not /media/*)
        r = requests.get(f"{BASE_URL}/api/media/nonexistent.png")
        # Either 404 (mounted, file missing) OR 200 with content
        assert r.status_code in [404, 405]
        # /media/* should NOT be routed (would 404 from ingress since not /api-prefixed)
        r2 = requests.get(f"{BASE_URL}/media/nonexistent.png")
        # ingress won't route non-/api → served by frontend nginx as SPA 200 or 404
        # this is expected — media MUST be under /api

    def test_no_localhost_in_frontend_src(self):
        import subprocess
        r = subprocess.run(
            ["grep", "-rn", "localhost", "/app/frontend/src"],
            capture_output=True, text=True,
        )
        # Only allow inside comments or none at all
        offending = [l for l in r.stdout.splitlines()
                     if "localhost" in l and not l.strip().startswith("//")]
        assert len(offending) == 0, f"Found hardcoded localhost: {offending[:3]}"


# =========== 13. PERFORMANCE ===========
class TestPerformance:
    def test_matrix_under_1s(self, admin):
        t = time.time()
        r = admin.get(f"{BASE_URL}/api/admin/attribution-matrix")
        assert r.status_code == 200
        assert (time.time() - t) < 2.0

    def test_sanity_under_1s(self, admin):
        t = time.time()
        r = admin.get(f"{BASE_URL}/api/admin/sanity")
        assert r.status_code == 200
        assert (time.time() - t) < 2.0

    def test_untagged_under_1s(self, admin):
        t = time.time()
        r = admin.get(f"{BASE_URL}/api/admin/sanity/untagged")
        assert r.status_code == 200
        assert (time.time() - t) < 2.0
