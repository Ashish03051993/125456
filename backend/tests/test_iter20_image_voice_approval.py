"""Backend tests for Iteration 20 - Image + Voice approval gates (guided pipeline).

Covers:
- Auth gating (401 without cookie) for all new endpoints
- 400 when calling approve/regenerate in wrong status
- Full E2E guided pipeline: create -> script approval -> image approval -> voice approval -> ready
- Single-scene image regeneration cache-busts image_url
- Voice regenerate with {voice:'male'} switches voice preference and re-generates audio
- Regression: script/approve, script/regenerate, script edit still work
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


def _rand_email():
    return f"TEST_iter20_{uuid.uuid4().hex[:10]}@testmail.local"


def _register(name="Iter20 Tester", credits_override=None):
    """Register a fresh user and return an authenticated requests.Session."""
    email = _rand_email()
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/register",
               json={"name": name, "identifier": email, "password": "secret123"})
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    return s, r.json()["user"], email


def _wait_for_status(s, pid, target_statuses, timeout=180, poll_every=3):
    """Poll GET /api/projects/{pid} until status in `target_statuses` or error/timeout."""
    if isinstance(target_statuses, str):
        target_statuses = {target_statuses}
    else:
        target_statuses = set(target_statuses)
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = s.get(f"{API}/projects/{pid}")
        assert r.status_code == 200, f"get project: {r.status_code} {r.text}"
        last = r.json()
        st = last.get("status")
        if st in target_statuses:
            return last
        if st == "error":
            raise AssertionError(f"Project entered error state: {last.get('error')}")
        time.sleep(poll_every)
    raise AssertionError(f"Timed out waiting for status in {target_statuses} (last={last.get('status')}, stage={last.get('stage')})")


def _create_and_start_30s(s):
    """Create a 30-sec project (min cost) and kick off /generate. Returns pid."""
    payload = {"topic": "How octopuses solve puzzles",
               "duration_sec": 30, "language": "English", "style": "Educational",
               "voice": "female", "dialogue_mode": False}
    r = s.post(f"{API}/projects", json=payload)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    g = s.post(f"{API}/projects/{pid}/generate")
    assert g.status_code == 200, g.text
    return pid


# ================================================================
# AUTH — every new endpoint must reject unauthenticated calls
# ================================================================
class TestAuthGating:
    """All new image/voice endpoints must return 401 without session cookie."""

    @pytest.mark.parametrize("method,path", [
        ("POST", "/projects/dummy/images/approve"),
        ("POST", "/projects/dummy/images/regenerate"),
        ("POST", "/projects/dummy/images/regenerate/0"),
        ("POST", "/projects/dummy/voice/approve"),
        ("POST", "/projects/dummy/voice/regenerate"),
    ])
    def test_endpoint_requires_auth(self, method, path):
        r = requests.request(method, f"{API}{path}", json={})
        assert r.status_code == 401, f"{method} {path} -> {r.status_code} {r.text}"


# ================================================================
# STATUS GATE — approving/regenerating in wrong status returns 400
# ================================================================
class TestStatusGate:
    """Regenerate/approve should refuse when the project isn't in the right state."""

    def test_images_approve_400_when_not_awaiting_image_approval(self):
        s, _u, _e = _register()
        pid = _create_and_start_30s(s)
        # Project is 'generating' shortly after /generate — approve/regen should 400
        r = s.post(f"{API}/projects/{pid}/images/approve")
        assert r.status_code == 400, r.text
        assert "status" in r.json().get("detail", "").lower()

    def test_images_regenerate_400_when_not_awaiting(self):
        s, _u, _e = _register()
        pid = _create_and_start_30s(s)
        r = s.post(f"{API}/projects/{pid}/images/regenerate")
        assert r.status_code == 400, r.text

    def test_images_regenerate_single_400_when_not_awaiting(self):
        s, _u, _e = _register()
        pid = _create_and_start_30s(s)
        r = s.post(f"{API}/projects/{pid}/images/regenerate/0")
        assert r.status_code == 400, r.text

    def test_voice_approve_400_when_not_awaiting(self):
        s, _u, _e = _register()
        pid = _create_and_start_30s(s)
        r = s.post(f"{API}/projects/{pid}/voice/approve")
        assert r.status_code == 400, r.text

    def test_voice_regenerate_400_when_not_awaiting(self):
        s, _u, _e = _register()
        pid = _create_and_start_30s(s)
        r = s.post(f"{API}/projects/{pid}/voice/regenerate", json={})
        assert r.status_code == 400, r.text

    def test_404_when_other_users_project(self):
        s1, _u1, _e1 = _register()
        pid = _create_and_start_30s(s1)
        s2, _u2, _e2 = _register()
        r = s2.post(f"{API}/projects/{pid}/images/approve")
        assert r.status_code == 404, r.text


# ================================================================
# END-TO-END GUIDED PIPELINE
# One expensive test — ~90-180 seconds, uses 3 credits.
# ================================================================
class TestGuidedPipelineE2E:
    """Full happy-path with all three approval gates."""

    def test_full_pipeline_gates_and_ready(self):
        s, u, email = _register(name="E2E Tester")
        assert u["credits"] >= 3, f"Fresh user has only {u['credits']} credits — cannot run E2E"

        pid = _create_and_start_30s(s)

        # 1) Wait for awaiting_script_approval
        p1 = _wait_for_status(s, pid, "awaiting_script_approval", timeout=180)
        assert p1["scenes"], "expected scenes drafted at script approval gate"
        # All scenes should NOT yet have image_url (image stage hasn't run)
        assert all(sc.get("image_url") in (None, "") for sc in p1["scenes"]), \
            "images should not exist yet at script approval gate"

        # 2) Approve script -> should transition through generating images
        r = s.post(f"{API}/projects/{pid}/script/approve")
        assert r.status_code == 200, r.text

        # 3) Wait for awaiting_image_approval — pipeline should STOP here (not auto-advance)
        p2 = _wait_for_status(s, pid, "awaiting_image_approval", timeout=240)
        assert p2["scenes"], "expected scenes at image approval gate"
        assert all(sc.get("image_url") for sc in p2["scenes"]), \
            "every scene should have image_url at image approval gate"

        # Wait a couple seconds; project must not auto-advance past this gate.
        time.sleep(4)
        rr = s.get(f"{API}/projects/{pid}").json()
        assert rr["status"] == "awaiting_image_approval", \
            f"pipeline auto-advanced past image gate (status={rr['status']})"

        # 4) Approve images -> should transition to voice generation
        r = s.post(f"{API}/projects/{pid}/images/approve")
        assert r.status_code == 200, r.text

        # 5) Wait for awaiting_voice_approval
        p3 = _wait_for_status(s, pid, "awaiting_voice_approval", timeout=180)
        assert p3.get("audio_url"), "expected audio_url at voice approval gate"

        # Must not auto-advance past voice gate
        time.sleep(4)
        rr = s.get(f"{API}/projects/{pid}").json()
        assert rr["status"] == "awaiting_voice_approval", \
            f"pipeline auto-advanced past voice gate (status={rr['status']})"

        # 6) Approve voice -> compose final video
        r = s.post(f"{API}/projects/{pid}/voice/approve")
        assert r.status_code == 200, r.text

        # 7) Wait for ready
        p4 = _wait_for_status(s, pid, "ready", timeout=240)
        assert p4.get("video_url"), "expected video_url at ready state"
        assert p4.get("video_urls"), "expected multi-format video_urls at ready state"


# ================================================================
# SINGLE-IMAGE REGEN — cache buster
# Also gets us to the image approval state, so we use it to test that too.
# NOTE: this is a costly test (real LLM + image + tts + ffmpeg-adjacent).
# ================================================================
class TestSingleImageRegen:
    def test_regenerate_single_scene_updates_only_that_image(self):
        s, u, _e = _register()
        pid = _create_and_start_30s(s)
        _wait_for_status(s, pid, "awaiting_script_approval", timeout=180)
        s.post(f"{API}/projects/{pid}/script/approve")
        p = _wait_for_status(s, pid, "awaiting_image_approval", timeout=240)
        before = {sc["idx"]: sc["image_url"] for sc in p["scenes"]}

        # Regenerate only scene 0
        r = s.post(f"{API}/projects/{pid}/images/regenerate/0")
        assert r.status_code == 200, r.text
        updated = r.json()
        assert updated["status"] == "awaiting_image_approval", \
            "single regen should keep project in awaiting_image_approval"
        new_by_idx = {sc["idx"]: sc["image_url"] for sc in updated["scenes"]}
        # Scene 0 URL changed (cache-buster ?v= added), others unchanged
        assert new_by_idx[0] != before[0], f"scene 0 image_url unchanged after regen (before={before[0]}, after={new_by_idx[0]})"
        assert "?v=" in new_by_idx[0] or "&v=" in new_by_idx[0], \
            f"expected cache-buster query on regen'd URL, got {new_by_idx[0]}"
        for i in [k for k in before if k != 0]:
            assert new_by_idx[i] == before[i], f"scene {i} URL should not change on single regen"


# ================================================================
# VOICE REGEN WITH PICK — updates voice preference and regenerates audio
# ================================================================
class TestVoiceRegen:
    def test_voice_regenerate_with_male_switches_preference(self):
        s, u, _e = _register()
        pid = _create_and_start_30s(s)
        _wait_for_status(s, pid, "awaiting_script_approval", timeout=180)
        s.post(f"{API}/projects/{pid}/script/approve")
        _wait_for_status(s, pid, "awaiting_image_approval", timeout=240)
        s.post(f"{API}/projects/{pid}/images/approve")
        p = _wait_for_status(s, pid, "awaiting_voice_approval", timeout=180)
        assert p["voice"] == "female"  # default from create

        r = s.post(f"{API}/projects/{pid}/voice/regenerate", json={"voice": "male"})
        assert r.status_code == 200, r.text

        # Should re-enter awaiting_voice_approval with voice='male'
        p2 = _wait_for_status(s, pid, "awaiting_voice_approval", timeout=180)
        assert p2["voice"] == "male", f"voice preference not updated (got {p2['voice']})"
        assert p2.get("audio_url"), "audio_url missing after regen"


# ================================================================
# REGRESSION — existing script endpoints still work
# ================================================================
class TestScriptRegression:
    def test_script_approve_regenerate_edit_still_work(self):
        s, u, _e = _register()
        pid = _create_and_start_30s(s)
        p = _wait_for_status(s, pid, "awaiting_script_approval", timeout=180)

        # PATCH /script edit
        first_scene = p["scenes"][0]
        edited_scenes = [
            {"narration": first_scene["narration"] + " (edited)",
             "subtitle": first_scene["subtitle"],
             "image_prompt": first_scene["image_prompt"]}
        ] + [
            {"narration": sc["narration"], "subtitle": sc["subtitle"],
             "image_prompt": sc["image_prompt"]}
            for sc in p["scenes"][1:]
        ]
        r = s.patch(f"{API}/projects/{pid}/script",
                    json={"title": "TEST_EDITED_TITLE", "scenes": edited_scenes})
        assert r.status_code == 200, r.text
        updated = r.json()
        assert updated["title"] == "TEST_EDITED_TITLE"
        assert updated["scenes"][0]["narration"].endswith("(edited)")

        # POST /script/regenerate should return to awaiting_script_approval eventually
        r = s.post(f"{API}/projects/{pid}/script/regenerate")
        assert r.status_code == 200, r.text
        p2 = _wait_for_status(s, pid, "awaiting_script_approval", timeout=180)
        assert p2.get("scenes"), "regenerated script has no scenes"

        # Finally, /script/approve still transitions the project forward
        r = s.post(f"{API}/projects/{pid}/script/approve")
        assert r.status_code == 200, r.text
