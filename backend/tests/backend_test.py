"""AI Video Studio - backend integration tests.

Covers: health, auth, projects CRUD, credit gating, admin endpoints, media static, and
end-to-end pipeline polling (long-running ~60-180s, guarded by RUN_PIPELINE env).
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://script-to-video-382.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

# Test tokens seeded via mongosh (documented in test report)
ADMIN_TOK = os.environ.get("ADMIN_TOK", "test_admin_1784715294652")
USER_TOK = os.environ.get("USER_TOK", "test_user_1784715294657")
ZERO_TOK = os.environ.get("ZERO_TOK", "test_zero_1784715294661")

RUN_PIPELINE = os.environ.get("RUN_PIPELINE", "1") == "1"  # long-running


# --------------------------- session/fixtures ---------------------------
@pytest.fixture(scope="session")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


# --------------------------- Health ---------------------------
class TestHealth:
    def test_root_api(self, http):
        r = http.get(f"{API}/")
        assert r.status_code == 200
        body = r.json()
        assert body.get("service") == "AI Video Studio"
        assert body.get("status") == "ok"


# --------------------------- Auth ---------------------------
class TestAuth:
    def test_me_unauthenticated(self, http):
        r = http.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_with_bearer(self, http):
        r = http.get(f"{API}/auth/me", headers=hdr(USER_TOK))
        assert r.status_code == 200, r.text
        u = r.json()
        assert u["email"] == "TEST_pytestuser@example.com"
        assert u["role"] == "user"
        assert "_id" not in u

    def test_me_bad_token(self, http):
        r = http.get(f"{API}/auth/me", headers=hdr("nonexistent_token"))
        assert r.status_code == 401


# --------------------------- Projects CRUD ---------------------------
class TestProjectsCRUD:
    created_ids = []

    def test_create_project(self, http):
        r = http.post(f"{API}/projects", headers=hdr(USER_TOK), json={
            "topic": "TEST_A short intro to photosynthesis",
            "duration_min": 1,
            "style": "Educational",
            "language": "English",
            "voice": "female",
        })
        assert r.status_code == 200, r.text
        p = r.json()
        assert "_id" not in p, "MongoDB _id should be excluded from response"
        assert p["topic"].startswith("TEST_")
        assert p["status"] == "draft"
        assert p["id"].startswith("proj_")
        TestProjectsCRUD.created_ids.append(p["id"])

    def test_get_project(self, http):
        pid = TestProjectsCRUD.created_ids[0]
        r = http.get(f"{API}/projects/{pid}", headers=hdr(USER_TOK))
        assert r.status_code == 200
        p = r.json()
        assert p["id"] == pid
        assert "_id" not in p

    def test_list_projects_scoped_to_user(self, http):
        r = http.get(f"{API}/projects", headers=hdr(USER_TOK))
        assert r.status_code == 200
        projects = r.json()
        assert isinstance(projects, list)
        # Every project belongs to same user_id and no _id leaks
        for p in projects:
            assert "_id" not in p
            assert p.get("user_id")
            assert p["id"].startswith("proj_")

    def test_list_projects_unauthed(self, http):
        r = http.get(f"{API}/projects")
        assert r.status_code == 401

    def test_get_other_users_project_404(self, http):
        # Try to fetch first project as admin - it belongs to USER, so admin should also 404 (scoped)
        pid = TestProjectsCRUD.created_ids[0]
        r = http.get(f"{API}/projects/{pid}", headers=hdr(ADMIN_TOK))
        assert r.status_code == 404

    def test_delete_project(self, http):
        # Create a throwaway project and delete it
        r = http.post(f"{API}/projects", headers=hdr(USER_TOK), json={
            "topic": "TEST_delete me", "duration_min": 1,
        })
        assert r.status_code == 200
        pid = r.json()["id"]
        d = http.delete(f"{API}/projects/{pid}", headers=hdr(USER_TOK))
        assert d.status_code == 200
        assert d.json()["deleted"] == 1
        g = http.get(f"{API}/projects/{pid}", headers=hdr(USER_TOK))
        assert g.status_code == 404


# --------------------------- Credit gating ---------------------------
class TestCredits:
    def test_create_project_zero_credits_returns_402(self, http):
        r = http.post(f"{API}/projects", headers=hdr(ZERO_TOK), json={
            "topic": "TEST_should not create",
            "duration_min": 1,
        })
        assert r.status_code == 402, r.text


# --------------------------- Admin ---------------------------
class TestAdmin:
    def test_users_requires_admin(self, http):
        r = http.get(f"{API}/admin/users", headers=hdr(USER_TOK))
        assert r.status_code == 403

    def test_stats_requires_admin(self, http):
        r = http.get(f"{API}/admin/stats", headers=hdr(USER_TOK))
        assert r.status_code == 403

    def test_admin_users_list(self, http):
        r = http.get(f"{API}/admin/users", headers=hdr(ADMIN_TOK))
        assert r.status_code == 200
        users = r.json()
        assert isinstance(users, list) and len(users) >= 1
        for u in users:
            assert "_id" not in u
        assert any(u.get("email") == "admin@videostudio.ai" for u in users)

    def test_admin_stats(self, http):
        r = http.get(f"{API}/admin/stats", headers=hdr(ADMIN_TOK))
        assert r.status_code == 200
        s = r.json()
        for k in ("total_users", "total_projects", "videos_ready", "plans", "monthly_revenue_inr"):
            assert k in s

    def test_admin_set_credits(self, http):
        # Read current credits for zero user
        users = http.get(f"{API}/admin/users", headers=hdr(ADMIN_TOK)).json()
        zero = next(u for u in users if u["email"] == "TEST_zerocredits@example.com")
        uid = zero["user_id"]
        r = http.post(f"{API}/admin/users/{uid}/credits?credits=7", headers=hdr(ADMIN_TOK))
        assert r.status_code == 200
        # Verify change via listing
        users2 = http.get(f"{API}/admin/users", headers=hdr(ADMIN_TOK)).json()
        z2 = next(u for u in users2 if u["user_id"] == uid)
        assert z2["credits"] == 7
        # Reset to 0 so credit-gating test remains reliable
        http.post(f"{API}/admin/users/{uid}/credits?credits=0", headers=hdr(ADMIN_TOK))


# --------------------------- End-to-end pipeline ---------------------------
@pytest.mark.skipif(not RUN_PIPELINE, reason="Set RUN_PIPELINE=1 to run long pipeline test (~60-180s)")
class TestPipeline:
    def test_generate_end_to_end(self, http):
        # Ensure user has credit
        # (admin resets)
        users = http.get(f"{API}/admin/users", headers=hdr(ADMIN_TOK)).json()
        me = next(u for u in users if u["email"] == "TEST_pytestuser@example.com")
        http.post(f"{API}/admin/users/{me['user_id']}/credits?credits=3", headers=hdr(ADMIN_TOK))

        r = http.post(f"{API}/projects", headers=hdr(USER_TOK), json={
            "topic": "TEST_A 30-second explainer on how bees make honey",
            "duration_min": 1,
            "style": "Educational",
            "language": "English",
            "voice": "female",
        })
        assert r.status_code == 200
        pid = r.json()["id"]

        g = http.post(f"{API}/projects/{pid}/generate", headers=hdr(USER_TOK))
        assert g.status_code == 200
        assert g.json().get("ok") is True

        stages_seen = set()
        start = time.time()
        final = None
        while time.time() - start < 240:
            time.sleep(5)
            pr = http.get(f"{API}/projects/{pid}", headers=hdr(USER_TOK))
            assert pr.status_code == 200
            body = pr.json()
            stages_seen.add(body.get("stage"))
            if body.get("status") in ("ready", "error"):
                final = body
                break
        assert final is not None, f"pipeline did not finish in 240s; stages seen: {stages_seen}"
        assert final["status"] == "ready", f"pipeline errored: {final.get('error')}; stages seen: {stages_seen}"
        assert final["video_url"], "video_url missing"
        assert final["audio_url"]
        assert final["title"]
        assert final["script"]
        assert isinstance(final["scenes"], list) and len(final["scenes"]) >= 1
        for sc in final["scenes"]:
            assert sc["image_url"].startswith("/media/images/")
        # Verify static media served
        vid = http.get(f"{BASE_URL}{final['video_url']}", stream=True)
        assert vid.status_code == 200, f"video not served: {vid.status_code}"
        img = http.get(f"{BASE_URL}{final['scenes'][0]['image_url']}", stream=True)
        assert img.status_code == 200
        aud = http.get(f"{BASE_URL}{final['audio_url']}", stream=True)
        assert aud.status_code == 200
