"""Iteration 21 – Talking-Head (Character Portrait) feature tests.

Covers:
- GET /api/features/talking_head
- POST /api/projects with talking_head gating (Free 402 / Pro 200)
- PATCH /api/projects/{id} — draft-only edits, plan gate, duration cost recompute
- POST /api/projects/{id}/character/upload — plan gate, mime + size validation
- POST /api/projects/{id}/character/generate — plan gate, min description length, real Nano Banana render
- DELETE /api/projects/{id}/character
- Media file served at /api/media/characters/{pid}.png
- Free user regression: normal wizard flow still works
"""
import io
import os
import time
import uuid
import struct
import zlib

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if False else "https://script-to-video-382.preview.emergentagent.com"
# use frontend/.env value directly since backend tests run outside the container’s env
# but keep dotenv-style read as fallback if env var is set
_env_url = os.environ.get("REACT_APP_BACKEND_URL")
if _env_url:
    BASE_URL = _env_url.rstrip("/")

API = f"{BASE_URL}/api"

PRO_EMAIL = "newuser@test.com"
PRO_PASSWORD = "secret123"


# -------------- Helpers --------------
def _make_png_bytes(width: int = 128, height: int = 128) -> bytes:
    """Create a valid PNG (>1KB) with real pixel data so backend size check passes."""
    # Random-ish RGB stripes
    raw = b""
    for y in range(height):
        raw += b"\x00"  # filter type
        for x in range(width):
            raw += bytes([(x * 2) & 0xFF, (y * 2) & 0xFF, ((x + y) * 3) & 0xFF])

    def _chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw)
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _register_free_user() -> requests.Session:
    """Fresh free-plan user for gate tests."""
    s = requests.Session()
    email = f"TEST_iter21_{uuid.uuid4().hex[:8]}@testmail.local"
    r = s.post(f"{API}/auth/register", json={
        "name": "Iter21 Free", "identifier": email, "password": "secret123"})
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    return s, email


def _login_pro_user() -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"identifier": PRO_EMAIL, "password": PRO_PASSWORD})
    assert r.status_code == 200, f"pro login failed: {r.status_code} {r.text}"
    return s


# =====================================================================
class TestFeatureFlag:
    def test_talking_head_feature_shape(self):
        r = requests.get(f"{API}/features/talking_head")
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is True
        assert d["provider"] == "stub"
        assert d["live_render"] is False
        assert set(d["paid_plans"]) == {"pro", "business", "enterprise"}
        assert d["max_upload_mb"] == 5


# =====================================================================
class TestProjectCreateGating:
    def test_free_user_talking_head_true_returns_402(self):
        s, _ = _register_free_user()
        r = s.post(f"{API}/projects", json={
            "topic": "Free plan talking head attempt",
            "duration_sec": 30, "talking_head": True,
        })
        assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text}"

    def test_free_user_regular_project_works(self):
        s, _ = _register_free_user()
        r = s.post(f"{API}/projects", json={
            "topic": "How coffee is grown", "duration_sec": 30,
            "style": "Educational", "voice": "female",
        })
        assert r.status_code in (200, 201), r.text
        p = r.json()
        assert p["talking_head"] is False
        assert p["status"] == "draft"
        assert p["credit_cost"] == 3
        # Clean up
        s.delete(f"{API}/projects/{p['id']}")

    def test_pro_user_talking_head_true_succeeds(self):
        s = _login_pro_user()
        r = s.post(f"{API}/projects", json={
            "topic": "Pro user with talking head",
            "duration_sec": 30, "talking_head": True,
        })
        assert r.status_code in (200, 201), r.text
        p = r.json()
        assert p["talking_head"] is True
        assert p["status"] == "draft"
        s.delete(f"{API}/projects/{p['id']}")


# =====================================================================
class TestProjectPatch:
    def test_patch_updates_draft_and_recomputes_cost(self):
        s = _login_pro_user()
        r = s.post(f"{API}/projects", json={"topic": "Patch test", "duration_sec": 30})
        pid = r.json()["id"]
        try:
            r = s.patch(f"{API}/projects/{pid}", json={"duration_sec": 60, "style": "Cinematic"})
            assert r.status_code == 200, r.text
            p = r.json()
            assert p["duration_sec"] == 60
            assert p["style"] == "Cinematic"
            assert p["credit_cost"] == 5  # 60s costs 5 per pricing table
        finally:
            s.delete(f"{API}/projects/{pid}")

    def test_patch_free_user_talking_head_true_returns_402(self):
        s, _ = _register_free_user()
        r = s.post(f"{API}/projects", json={"topic": "Free patch th", "duration_sec": 30})
        pid = r.json()["id"]
        try:
            r = s.patch(f"{API}/projects/{pid}", json={"talking_head": True})
            assert r.status_code == 402, f"expected 402 got {r.status_code}: {r.text}"
        finally:
            s.delete(f"{API}/projects/{pid}")

    def test_patch_non_draft_returns_400(self):
        s = _login_pro_user()
        r = s.post(f"{API}/projects", json={"topic": "Immutable test", "duration_sec": 30})
        pid = r.json()["id"]
        try:
            # Kick off generation to leave draft status
            g = s.post(f"{API}/projects/{pid}/generate")
            assert g.status_code == 200
            # Give backend a moment to flip status
            time.sleep(1.5)
            r = s.patch(f"{API}/projects/{pid}", json={"topic": "Should not update"})
            assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"
        finally:
            s.delete(f"{API}/projects/{pid}")


# =====================================================================
class TestCharacterUpload:
    def test_upload_free_user_returns_402(self):
        s, _ = _register_free_user()
        r = s.post(f"{API}/projects", json={"topic": "Upload gate", "duration_sec": 30})
        pid = r.json()["id"]
        try:
            png = _make_png_bytes()
            files = {"file": ("me.png", png, "image/png")}
            r = s.post(f"{API}/projects/{pid}/character/upload", files=files)
            assert r.status_code == 402
        finally:
            s.delete(f"{API}/projects/{pid}")

    def test_upload_pro_valid_png(self):
        s = _login_pro_user()
        r = s.post(f"{API}/projects", json={"topic": "Upload png", "duration_sec": 30})
        pid = r.json()["id"]
        try:
            png = _make_png_bytes(200, 200)
            assert len(png) > 1024
            files = {"file": ("me.png", png, "image/png")}
            r = s.post(f"{API}/projects/{pid}/character/upload", files=files)
            assert r.status_code == 200, r.text
            url = r.json()["character_image_url"]
            assert url.startswith("/api/media/characters/") and pid in url
            # Fetch the file via media endpoint
            clean_url = url.split("?")[0]
            m = requests.get(f"{BASE_URL}{clean_url}")
            assert m.status_code == 200
            assert m.headers["content-type"].startswith("image/")
            # Verify project doc updated
            pg = s.get(f"{API}/projects/{pid}").json()
            assert pg["character_image_url"] == url
            assert pg["character_source"] == "upload"
        finally:
            s.delete(f"{API}/projects/{pid}")

    def test_upload_bad_mime_returns_400(self):
        s = _login_pro_user()
        r = s.post(f"{API}/projects", json={"topic": "Bad mime", "duration_sec": 30})
        pid = r.json()["id"]
        try:
            files = {"file": ("me.gif", b"GIF89a" + b"\x00" * 2000, "image/gif")}
            r = s.post(f"{API}/projects/{pid}/character/upload", files=files)
            assert r.status_code == 400, r.text
        finally:
            s.delete(f"{API}/projects/{pid}")

    def test_upload_too_large_returns_400(self):
        s = _login_pro_user()
        r = s.post(f"{API}/projects", json={"topic": "Too large", "duration_sec": 30})
        pid = r.json()["id"]
        try:
            # 6 MB fake PNG header + zeros. Backend reads full body then rejects on size.
            fake = b"\x89PNG\r\n\x1a\n" + b"\x00" * (6 * 1024 * 1024)
            files = {"file": ("big.png", fake, "image/png")}
            r = s.post(f"{API}/projects/{pid}/character/upload", files=files)
            assert r.status_code == 400, r.text
        finally:
            s.delete(f"{API}/projects/{pid}")


# =====================================================================
class TestCharacterGenerate:
    def test_generate_free_returns_402(self):
        s, _ = _register_free_user()
        r = s.post(f"{API}/projects", json={"topic": "Gen gate", "duration_sec": 30})
        pid = r.json()["id"]
        try:
            r = s.post(f"{API}/projects/{pid}/character/generate",
                       json={"description": "confident 30s Indian entrepreneur"})
            assert r.status_code == 402
        finally:
            s.delete(f"{API}/projects/{pid}")

    def test_generate_short_desc_returns_400(self):
        s = _login_pro_user()
        r = s.post(f"{API}/projects", json={"topic": "Short desc", "duration_sec": 30})
        pid = r.json()["id"]
        try:
            r = s.post(f"{API}/projects/{pid}/character/generate", json={"description": "hi"})
            assert r.status_code == 400, r.text
        finally:
            s.delete(f"{API}/projects/{pid}")

    def test_generate_real_portrait_nano_banana(self):
        s = _login_pro_user()
        r = s.post(f"{API}/projects", json={"topic": "Real gen", "duration_sec": 30})
        pid = r.json()["id"]
        try:
            r = s.post(f"{API}/projects/{pid}/character/generate", json={
                "description": "Confident Indian entrepreneur, 30s, business attire"},
                       timeout=90)
            assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
            url = r.json()["character_image_url"]
            assert url.startswith("/api/media/characters/")
            # Fetch and verify real image (>100KB per requirement)
            clean = url.split("?")[0]
            m = requests.get(f"{BASE_URL}{clean}", timeout=30)
            assert m.status_code == 200
            assert m.headers["content-type"].startswith("image/")
            content_len = len(m.content)
            assert content_len > 100_000, f"portrait suspiciously small: {content_len} bytes"
            # Verify project doc
            pg = s.get(f"{API}/projects/{pid}").json()
            assert pg["character_source"] == "ai_generated"
        finally:
            s.delete(f"{API}/projects/{pid}")


# =====================================================================
class TestCharacterDelete:
    def test_delete_clears_project_field(self):
        s = _login_pro_user()
        r = s.post(f"{API}/projects", json={"topic": "Del", "duration_sec": 30})
        pid = r.json()["id"]
        try:
            png = _make_png_bytes()
            files = {"file": ("me.png", png, "image/png")}
            up = s.post(f"{API}/projects/{pid}/character/upload", files=files)
            assert up.status_code == 200
            # Delete
            d = s.delete(f"{API}/projects/{pid}/character")
            assert d.status_code == 200 and d.json().get("ok") is True
            pg = s.get(f"{API}/projects/{pid}").json()
            assert pg.get("character_image_url") in (None, "")
            assert pg.get("character_source") in (None, "")
        finally:
            s.delete(f"{API}/projects/{pid}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
