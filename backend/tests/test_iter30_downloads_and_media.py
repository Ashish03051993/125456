"""
Iteration 30 regression tests — guards for:
1. Media static-file mount at /api/media (video + image content-types)
2. Multi-format video_urls schema on projects
3. resolveMediaUrl helper contract (via the backend paths it depends on)
4. FFmpeg availability (boot self-heal + admin repair)

Run with: `pytest tests/test_iter30_downloads_and_media.py -v`
"""
import os
import time
import pytest
import httpx

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
ADMIN_EMAIL = "admin@videostudio.ai"
ADMIN_PASSWORD = "Admin@2026"


@pytest.fixture(scope="module")
def http_client():
    with httpx.Client(base_url=API_URL, timeout=15, follow_redirects=False) as c:
        yield c


@pytest.fixture(scope="module")
def admin_cookies(http_client):
    r = http_client.post(
        "/api/auth/login",
        json={"identifier": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.cookies


class TestMediaMount:
    """The download & cover-image UX depends on /api/media/* returning the right content-type."""

    def test_media_root_returns_404_not_html(self, http_client):
        """A missing file should 404, NOT return React's index.html (which was the pre-fix bug)."""
        r = http_client.get("/api/media/does-not-exist.mp4")
        assert r.status_code == 404
        # Belt-and-braces: even the 404 body should not look like an HTML app shell
        assert "<!doctype html" not in r.text.lower()

    def test_media_video_content_type(self, http_client, admin_cookies):
        """Any existing video should be served as video/mp4, not text/html."""
        # Find any existing project video via the projects endpoint
        r = http_client.get("/api/projects", cookies=admin_cookies)
        assert r.status_code == 200
        projects = r.json()
        video_url = None
        for p in projects:
            if p.get("status") == "ready":
                # Handle both legacy /media/... and new /api/media/... paths
                u = p.get("video_urls", {}).get("landscape") or p.get("video_url")
                if u:
                    video_url = u if u.startswith("/api/") else "/api" + u
                    break
        if not video_url:
            pytest.skip("No ready video in DB to probe content-type")
        r2 = http_client.head(video_url)
        assert r2.status_code == 200, f"HEAD {video_url} → {r2.status_code}"
        assert r2.headers.get("content-type", "").startswith("video/"), \
            f"Expected video/*, got {r2.headers.get('content-type')}"

    def test_media_image_content_type(self, http_client, admin_cookies):
        """Scene thumbnails must be served as image/*, not text/html."""
        r = http_client.get("/api/projects", cookies=admin_cookies)
        assert r.status_code == 200
        thumb_url = None
        for p in r.json():
            scenes = p.get("scenes") or []
            if scenes and scenes[0].get("image_url"):
                u = scenes[0]["image_url"]
                thumb_url = u if u.startswith("/api/") else "/api" + u
                break
        if not thumb_url:
            pytest.skip("No project with scene image to probe")
        r2 = http_client.head(thumb_url)
        assert r2.status_code == 200
        assert r2.headers.get("content-type", "").startswith("image/"), \
            f"Expected image/*, got {r2.headers.get('content-type')}"


class TestProjectSchemaFields:
    """Multi-format download dropdown depends on these fields existing on the project payload."""

    def test_ready_project_exposes_download_fields(self, http_client, admin_cookies):
        r = http_client.get("/api/projects", cookies=admin_cookies)
        assert r.status_code == 200
        for p in r.json():
            if p.get("status") == "ready":
                # Either legacy video_url OR video_urls map must be present
                assert p.get("video_url") or p.get("video_urls"), \
                    f"Ready project {p['id']} has neither video_url nor video_urls"
                return
        pytest.skip("No ready project to check")

    def test_projects_endpoint_stable_shape(self, http_client, admin_cookies):
        """Any polling client on the Dashboard breaks if `status`/`id` disappears."""
        r = http_client.get("/api/projects", cookies=admin_cookies)
        assert r.status_code == 200
        for p in r.json():
            assert "id" in p and "status" in p, f"Missing id/status on project: {p}"


class TestFfmpegAvailability:
    """FFmpeg dropping from the container is the #1 recurring ops issue — regression guard."""

    def test_health_ffmpeg_ok(self, http_client):
        r = http_client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["checks"]["ffmpeg"] == "ok", \
            "ffmpeg not detected — boot self-heal should have caught this"

    def test_admin_repair_idempotent_when_installed(self, http_client, admin_cookies):
        """Repair endpoint returns already_installed when ffmpeg is present (no-op)."""
        r = http_client.post("/api/admin/repair/ffmpeg", cookies=admin_cookies)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in {"already_installed", "installed"}
        assert "ffmpeg" in body.get("path", "")

    def test_admin_repair_requires_admin(self):
        """Fresh client with no session cookies — should get 401."""
        with httpx.Client(base_url=API_URL, timeout=15) as fresh:
            r = fresh.post("/api/admin/repair/ffmpeg")
        assert r.status_code == 401, f"Expected 401 for unauth call, got {r.status_code}"
