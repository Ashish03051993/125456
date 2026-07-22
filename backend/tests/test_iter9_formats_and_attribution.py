"""Iteration 9 tests — Dual-format video pipeline + Signup Attribution Matrix.

Covers:
  - GET /api/formats (public) — landscape + vertical with correct dims/aspect/default
  - Synthetic ready-project persistence — video_url + video_urls dict
  - GET /api/admin/attribution-matrix — auth, shape, cell↔variant order, totals math
  - Regression checks for endpoints touched by prior iterations
"""
import os
import uuid
import pathlib
import subprocess
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get(
    "REACT_APP_BACKEND_URL") else "https://script-to-video-382.preview.emergentagent.com"
API = f"{BASE_URL}/api"

ADMIN_TOKEN = "test_admin_1784712404860"
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

# ---- Mongo helpers ------------------------------------------------
mc = MongoClient("mongodb://localhost:27017")
mdb = mc["test_database"]


# ================== /api/formats (public) ==================
class TestFormats:
    def test_formats_shape(self):
        r = requests.get(f"{API}/formats", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        ids = {f["id"] for f in data}
        assert {"landscape", "vertical"}.issubset(ids)

    def test_formats_landscape_spec(self):
        data = requests.get(f"{API}/formats", timeout=15).json()
        ls = next(f for f in data if f["id"] == "landscape")
        assert ls["aspect"] == "16:9"
        assert ls["width"] == 1920
        assert ls["height"] == 1080
        assert ls["default"] is True
        assert ls["label"]
        assert "YouTube" in ls["platforms"]
        assert isinstance(ls["subtitle_font"], int)

    def test_formats_vertical_spec(self):
        data = requests.get(f"{API}/formats", timeout=15).json()
        v = next(f for f in data if f["id"] == "vertical")
        assert v["aspect"] == "9:16"
        assert v["width"] == 1080
        assert v["height"] == 1920
        assert v.get("default") is False
        assert "LinkedIn" in v["platforms"]
        # pad_blur is the correct fit strategy for vertical from a 16:9 source
        assert v["fit"] == "pad_blur"


# ================== Synthetic ready-project (dual-format contract) ==================
class TestProjectVideoUrls:
    """Insert a synthetic ready project with tiny mp4 fixtures and confirm the
    /api/projects/{id} contract returns both video_url and video_urls."""

    PROJ_ID = f"proj_TESTITER9{uuid.uuid4().hex[:6]}"
    USER_ID = None
    SESS = None

    @classmethod
    def setup_class(cls):
        # Create a throwaway test user + session
        cls.USER_ID = f"user_TESTITER9{uuid.uuid4().hex[:6]}"
        cls.SESS = f"sess_TESTITER9_{uuid.uuid4().hex[:8]}"
        mdb.users.insert_one({
            "user_id": cls.USER_ID,
            "email": f"TEST_iter9_{cls.USER_ID}@example.com",
            "name": "Iter9 Test",
            "role": "user",
            "credits": 5,
            "plan": "free",
        })
        mdb.user_sessions.insert_one({
            "user_id": cls.USER_ID,
            "session_token": cls.SESS,
            "expires_at": "2099-01-01T00:00:00+00:00",
        })

        # Create tiny mp4 fixtures. ffmpeg is not installed in this preview env
        # so we write minimal valid-container bytes. Static-file serving keys
        # off the .mp4 extension for content-type, so real encoding isn't
        # required to verify the URL contract.
        storage = pathlib.Path("/app/backend/storage/videos")
        storage.mkdir(parents=True, exist_ok=True)
        cls.landscape_path = storage / f"{cls.PROJ_ID}_landscape.mp4"
        cls.vertical_path = storage / f"{cls.PROJ_ID}_vertical.mp4"
        # Minimal MP4 ftyp box header — enough for a non-zero response body.
        mp4_stub = (
            b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
            + b"\x00" * 1024
        )
        cls.landscape_path.write_bytes(mp4_stub)
        cls.vertical_path.write_bytes(mp4_stub)

        # Insert synthetic ready project
        mdb.projects.insert_one({
            "id": cls.PROJ_ID,
            "user_id": cls.USER_ID,
            "topic": "Iter9 dual-format smoke test",
            "duration_min": 1,
            "language": "English",
            "style": "Educational",
            "voice": "female",
            "status": "ready",
            "progress": 100,
            "stage": "done",
            "video_url": f"/api/media/videos/{cls.PROJ_ID}_landscape.mp4",
            "video_urls": {
                "landscape": f"/api/media/videos/{cls.PROJ_ID}_landscape.mp4",
                "vertical":  f"/api/media/videos/{cls.PROJ_ID}_vertical.mp4",
            },
            "created_at": "2026-01-01T00:00:00+00:00",
        })

    @classmethod
    def teardown_class(cls):
        mdb.projects.delete_many({"id": cls.PROJ_ID})
        mdb.users.delete_many({"user_id": cls.USER_ID})
        mdb.user_sessions.delete_many({"session_token": cls.SESS})
        cls.landscape_path.unlink(missing_ok=True)
        cls.vertical_path.unlink(missing_ok=True)

    def test_project_returns_both_urls(self):
        h = {"Authorization": f"Bearer {self.SESS}"}
        r = requests.get(f"{API}/projects/{self.PROJ_ID}", headers=h, timeout=15)
        assert r.status_code == 200
        p = r.json()
        assert p["status"] == "ready"
        assert p["video_url"].endswith(f"{self.PROJ_ID}_landscape.mp4")
        vu = p["video_urls"]
        assert set(vu.keys()) == {"landscape", "vertical"}
        assert vu["landscape"].endswith(f"{self.PROJ_ID}_landscape.mp4")
        assert vu["vertical"].endswith(f"{self.PROJ_ID}_vertical.mp4")
        # Path shape /api/media/videos/... required for static mount
        for u in vu.values():
            assert u.startswith("/api/media/videos/")

    def test_static_serving_landscape(self):
        url = f"{BASE_URL}/api/media/videos/{self.PROJ_ID}_landscape.mp4"
        r = requests.get(url, timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("video/mp4") or \
               r.headers.get("content-type", "") == "video/mp4"
        assert len(r.content) > 500

    def test_static_serving_vertical(self):
        url = f"{BASE_URL}/api/media/videos/{self.PROJ_ID}_vertical.mp4"
        r = requests.get(url, timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("video/mp4")
        assert len(r.content) > 500

    def test_ffprobe_resolutions(self):
        """Skipped in preview env — ffmpeg/ffprobe not installed. Backend
        pipeline itself would ALSO fail here, so full generation is an
        ENV-blocker (main-agent should verify locally or in prod)."""
        pytest.skip("ffprobe not installed in preview container — ENV blocker")


# ================== /api/admin/attribution-matrix ==================
class TestAttributionMatrix:
    SEEDED_IDS = []

    @classmethod
    def setup_class(cls):
        # Seed a few distinct waitlist rows via public POST
        payloads = [
            {"email": f"TEST_iter9_li_a_{uuid.uuid4().hex[:6]}@example.com",
             "source": "linkedin", "medium": "post", "campaign": "iter9",
             "variant": "A", "plan_interest": "pro"},
            {"email": f"TEST_iter9_li_b_{uuid.uuid4().hex[:6]}@example.com",
             "source": "linkedin", "medium": "post", "campaign": "iter9",
             "variant": "B", "plan_interest": "pro"},
            {"email": f"TEST_iter9_dir_u_{uuid.uuid4().hex[:6]}@example.com",
             "source": "direct", "plan_interest": "free"},  # variant unassigned
        ]
        for p in payloads:
            r = requests.post(f"{API}/waitlist", json=p, timeout=15)
            assert r.status_code == 200, r.text
            cls.SEEDED_IDS.append(p["email"])

    @classmethod
    def teardown_class(cls):
        mdb.waitlist.delete_many({"email": {"$in": cls.SEEDED_IDS}})

    def test_requires_admin_no_cookie(self):
        r = requests.get(f"{API}/admin/attribution-matrix", timeout=15)
        assert r.status_code in (401, 403)

    def test_requires_admin_non_admin(self):
        # Create a plain-user session on the fly
        uid = f"user_TESTITER9NA_{uuid.uuid4().hex[:6]}"
        tok = f"sess_TESTITER9NA_{uuid.uuid4().hex[:6]}"
        mdb.users.insert_one({"user_id": uid, "email": f"{uid}@example.com",
                              "role": "user", "credits": 0})
        mdb.user_sessions.insert_one({"user_id": uid, "session_token": tok,
                                      "expires_at": "2099-01-01T00:00:00+00:00"})
        try:
            r = requests.get(f"{API}/admin/attribution-matrix",
                             headers={"Authorization": f"Bearer {tok}"}, timeout=15)
            assert r.status_code == 403
        finally:
            mdb.users.delete_one({"user_id": uid})
            mdb.user_sessions.delete_one({"session_token": tok})

    def test_matrix_shape(self):
        r = requests.get(f"{API}/admin/attribution-matrix",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        m = r.json()
        for key in ("sources", "variants", "rows", "col_totals", "grand"):
            assert key in m, f"missing {key}"
        assert isinstance(m["sources"], list) and len(m["sources"]) >= 1
        assert isinstance(m["variants"], list) and len(m["variants"]) >= 1
        assert isinstance(m["rows"], list) and len(m["rows"]) == len(m["sources"])

    def test_cell_order_matches_variants(self):
        m = requests.get(f"{API}/admin/attribution-matrix",
                         headers=ADMIN_HEADERS, timeout=15).json()
        for row in m["rows"]:
            assert len(row["cells"]) == len(m["variants"])
            for i, cell in enumerate(row["cells"]):
                assert cell["variant"] == m["variants"][i]

    def test_row_totals_equal_sum_of_cells(self):
        m = requests.get(f"{API}/admin/attribution-matrix",
                         headers=ADMIN_HEADERS, timeout=15).json()
        for row in m["rows"]:
            sig = sum(c["signups"] for c in row["cells"])
            sess = sum(c["sessions"] for c in row["cells"])
            assert row["totals"]["signups"] == sig
            assert row["totals"]["sessions"] == sess

    def test_col_totals_sum_equals_grand(self):
        m = requests.get(f"{API}/admin/attribution-matrix",
                         headers=ADMIN_HEADERS, timeout=15).json()
        col_sig = sum(c["signups"] for c in m["col_totals"])
        col_sess = sum(c["sessions"] for c in m["col_totals"])
        assert col_sig == m["grand"]["signups"]
        assert col_sess == m["grand"]["sessions"]

    def test_conversion_pct_math(self):
        m = requests.get(f"{API}/admin/attribution-matrix",
                         headers=ADMIN_HEADERS, timeout=15).json()
        for row in m["rows"]:
            for c in row["cells"]:
                if c["sessions"] == 0:
                    assert c["conversion_pct"] == 0.0
                else:
                    expected = round(c["signups"] / c["sessions"] * 100, 2)
                    assert c["conversion_pct"] == expected

    def test_seed_visible(self):
        """After seeding linkedin+A/B and direct+unassigned, matrix should
        contain these sources & variants."""
        m = requests.get(f"{API}/admin/attribution-matrix",
                         headers=ADMIN_HEADERS, timeout=15).json()
        assert "linkedin" in m["sources"]
        assert "direct" in m["sources"]
        assert "A" in m["variants"]
        assert "B" in m["variants"]
        assert "unassigned" in m["variants"]


# ================== Regression on previously green endpoints ==================
class TestRegression:
    def test_waitlist_admin_get(self):
        r = requests.get(f"{API}/admin/waitlist",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "entries" in d and "total" in d
        assert "filters" in d and "variant" in d["filters"]

    def test_admin_experiments(self):
        r = requests.get(f"{API}/admin/experiments",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "rows" in d and "experiment" in d

    def test_analytics_track(self):
        r = requests.post(f"{API}/analytics/track",
                          json={"event": "iter9_smoke",
                                "properties": {"src": "test"},
                                "session_id": f"iter9_{uuid.uuid4().hex[:8]}"},
                          timeout=15)
        assert r.status_code == 200 and r.json().get("ok") is True

    def test_short_link_prewired(self):
        r = requests.get(f"{API}/short/script-to-video-382",
                         timeout=15, allow_redirects=False)
        # /api/short/... resolves to JSON (per server.py); previously seeded slug
        # is expected to be present.
        assert r.status_code in (200, 404)  # 404 if slug not seeded in this env
        if r.status_code == 200:
            body = r.json()
            assert "target" in body

    def test_admin_utm_links(self):
        r = requests.get(f"{API}/admin/utm-links",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        assert "rows" in r.json()

    def test_admin_stats(self):
        r = requests.get(f"{API}/admin/stats",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        s = r.json()
        for k in ("total_users", "waitlist_total", "events_24h"):
            assert k in s

    def test_admin_analytics(self):
        r = requests.get(f"{API}/admin/analytics",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("by_event", "by_day", "unique_sessions"):
            assert k in d

    def test_admin_digest_list(self):
        r = requests.get(f"{API}/admin/digest",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
