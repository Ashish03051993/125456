"""Iteration 10 delta tests — additive changes verification.

Covers:
  1. Infra: ffmpeg/ffprobe binaries present on PATH (fixes iter-9 ENV blocker).
  2. Backend defense: _ffmpeg_compose_all raises clean RuntimeError with the
     expected message when shutil.which('ffmpeg') returns None (monkeypatched;
     the real ffmpeg is NOT uninstalled).
  3. Regression: /api/formats still returns landscape + vertical.
  4. Regression: /api/admin/attribution-matrix — 200 for admin, 401/403 for anon.
"""
import os
import sys
import shutil
import subprocess
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get(
    "REACT_APP_BACKEND_URL") else "https://script-to-video-382.preview.emergentagent.com"
API = f"{BASE_URL}/api"

ADMIN_TOKEN = "test_admin_1784712404860"
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

# Make backend importable for direct unit call of _ffmpeg_compose_all
sys.path.insert(0, "/app/backend")


# ============ 1. Infra ============
class TestFFmpegInstalled:
    def test_ffmpeg_on_path(self):
        p = shutil.which("ffmpeg")
        assert p is not None, "ffmpeg binary must be present on PATH"
        assert os.path.isfile(p)

    def test_ffprobe_on_path(self):
        p = shutil.which("ffprobe")
        assert p is not None, "ffprobe binary must be present on PATH"
        assert os.path.isfile(p)

    def test_ffmpeg_version_runs(self):
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10)
        assert r.returncode == 0
        assert "ffmpeg version" in r.stdout.lower()

    def test_ffprobe_version_runs(self):
        r = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True, timeout=10)
        assert r.returncode == 0
        assert "ffprobe version" in r.stdout.lower()

    def test_dejavu_font_present(self):
        # fonts-dejavu install requirement — used by ffmpeg drawtext filter
        result = subprocess.run(["fc-list"], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        assert "dejavu" in result.stdout.lower(), "DejaVu font family must be installed"


# ============ 2. Backend defense: RuntimeError when ffmpeg missing ============
class TestFFmpegGuard:
    """Verify _ffmpeg_compose_all raises RuntimeError with expected message
    when shutil.which('ffmpeg') returns None (guard added in iter-10)."""

    def test_raises_runtime_error_when_ffmpeg_missing(self, monkeypatch):
        # Import here so pytest can still run other tests if server import fails
        from server import _ffmpeg_compose_all
        import server as server_mod

        # Force shutil.which to return None *for the server module's shutil* —
        # server.py does `import shutil` inside the function, so patching the
        # top-level `shutil.which` covers it.
        monkeypatch.setattr(shutil, "which", lambda name: None)

        with pytest.raises(RuntimeError) as exc_info:
            _ffmpeg_compose_all(
                project_id="pytest_stub",
                scenes=[{"heading": "h", "narration": "n", "subtitle": "s",
                         "image_prompt": "ip"}],
                images=[],
                audio_path=None,
                total_duration=1.0,
            )
        msg = str(exc_info.value)
        assert "FFmpeg not installed" in msg, f"Unexpected message: {msg!r}"
        assert "apt-get install" in msg, f"Should suggest install cmd: {msg!r}"

    def test_guard_does_not_fire_when_ffmpeg_present(self):
        """Sanity check: without the monkeypatch, shutil.which('ffmpeg') is truthy
        so the guard is bypassed. We don't run the full compose here (expensive),
        we just re-assert the guard predicate is False in the current env."""
        assert shutil.which("ffmpeg") is not None


# ============ 3. Regression: /api/formats ============
class TestFormatsRegression:
    def test_formats_still_returns_landscape_and_vertical(self):
        r = requests.get(f"{API}/formats", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        ids = {f["id"] for f in data}
        assert "landscape" in ids
        assert "vertical" in ids

    def test_landscape_is_default(self):
        data = requests.get(f"{API}/formats", timeout=15).json()
        ls = next(f for f in data if f["id"] == "landscape")
        assert ls["default"] is True
        assert ls["aspect"] == "16:9"

    def test_vertical_spec_intact(self):
        data = requests.get(f"{API}/formats", timeout=15).json()
        v = next(f for f in data if f["id"] == "vertical")
        assert v["aspect"] == "9:16"
        assert v["width"] == 1080
        assert v["height"] == 1920


# ============ 4. Regression: /api/admin/attribution-matrix ============
class TestAttributionMatrixRegression:
    def test_anon_denied(self):
        r = requests.get(f"{API}/admin/attribution-matrix", timeout=15)
        assert r.status_code in (401, 403)

    def test_admin_gets_matrix(self):
        r = requests.get(f"{API}/admin/attribution-matrix",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # matrix shape sanity — expect the same schema as iter-9
        # Common shapes: {"rows": [...], "cols": [...], "cells": {...}, "grand": {...}}
        # or {"matrix": [...], "totals": {...}}. Assert non-empty JSON object.
        assert isinstance(data, dict) and len(data) > 0

    def test_admin_matrix_has_expected_keys(self):
        r = requests.get(f"{API}/admin/attribution-matrix",
                         headers=ADMIN_HEADERS, timeout=15)
        data = r.json()
        # Iter-9 baseline: grand totals present
        # (be permissive — accept either 'grand' key or 'totals' key)
        keys = set(data.keys())
        assert keys & {"grand", "totals", "matrix", "rows", "cells", "sources"}, \
            f"Unexpected matrix shape: {sorted(keys)}"
