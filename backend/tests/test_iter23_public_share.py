"""Iteration 23 — Public Share Links backend tests."""
import os
import string
import asyncio
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
if not MONGO_URL:
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("MONGO_URL="):
                MONGO_URL = line.split("=", 1)[1].strip()
            elif line.startswith("DB_NAME="):
                DB_NAME = line.split("=", 1)[1].strip()

# Alphabet used by _generate_share_slug — must have NO 0, O, 1, I, l
SHARE_ALPHABET_SET = set("abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789")

READY_PID = "proj_8930939f0b84"   # newuser@test.com's ready project
DRAFT_PID = "proj_141b7c94c5d7"   # newuser@test.com's draft project


@pytest.fixture(scope="session")
def auth_session():
    """Login as newuser@test.com and return authenticated requests.Session."""
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"identifier": "newuser@test.com", "password": "secret123"})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session", autouse=True)
def _preflight_reset_share(auth_session):
    """Ensure ready project has NO share_slug/share_enabled to start clean, then re-enable at end
    so downstream fixtures/tests still have data. This also purges any stray 'demo123x' slug."""
    async def _reset():
        cli = AsyncIOMotorClient(MONGO_URL); db = cli[DB_NAME]
        # Save original slug/state, then unset to force fresh flow tests
        proj = await db.projects.find_one({"id": READY_PID}, {"_id": 0, "share_slug": 1, "share_enabled": 1, "share_view_count": 1})
        original = {
            "slug": (proj or {}).get("share_slug"),
            "enabled": (proj or {}).get("share_enabled"),
            "views": (proj or {}).get("share_view_count"),
        }
        await db.projects.update_one(
            {"id": READY_PID},
            {"$unset": {"share_slug": "", "share_enabled": "", "share_view_count": "", "share_last_viewed_at": ""}},
        )
        cli.close()
        return original
    original = asyncio.get_event_loop().run_until_complete(_reset())
    yield original
    # No teardown needed — the test suite ends with an enabled share which is fine.


# ---------------------------------------------------------------------------
# TEST 1: draft project → 400
# ---------------------------------------------------------------------------
class TestShareEnable:
    def test_share_draft_returns_400(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/projects/{DRAFT_PID}/share")
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        detail = (r.json().get("detail") or "").lower()
        assert "only completed videos can be shared" in detail, f"Unexpected detail: {detail!r}"

    def test_share_ready_returns_slug(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/projects/{READY_PID}/share")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("share_enabled") is True
        slug = body.get("share_slug")
        assert isinstance(slug, str) and len(slug) == 10, f"Slug not 10 chars: {slug!r}"
        # Verify each char is in the safe alphabet (no 0/O/1/I/l)
        bad = [c for c in slug if c not in SHARE_ALPHABET_SET]
        assert not bad, f"Slug contains forbidden chars: {bad} in {slug!r}"

    def test_share_is_idempotent(self, auth_session):
        r1 = auth_session.post(f"{BASE_URL}/api/projects/{READY_PID}/share")
        r2 = auth_session.post(f"{BASE_URL}/api/projects/{READY_PID}/share")
        assert r1.status_code == r2.status_code == 200
        s1 = r1.json()["share_slug"]; s2 = r2.json()["share_slug"]
        assert s1 == s2, f"Slug changed between calls: {s1} vs {s2}"

    def test_disable_keeps_slug_reserved(self, auth_session):
        """DELETE /share sets share_enabled=false. Re-enabling returns SAME slug."""
        r = auth_session.post(f"{BASE_URL}/api/projects/{READY_PID}/share")
        original_slug = r.json()["share_slug"]

        d = auth_session.delete(f"{BASE_URL}/api/projects/{READY_PID}/share")
        assert d.status_code == 200

        # Verify DB state (share_slug still present, share_enabled=false)
        async def _check():
            cli = AsyncIOMotorClient(MONGO_URL); db = cli[DB_NAME]
            p = await db.projects.find_one({"id": READY_PID}, {"_id": 0})
            cli.close()
            return p
        rec = asyncio.get_event_loop().run_until_complete(_check())
        assert rec.get("share_slug") == original_slug, "slug was cleared on revoke"
        assert rec.get("share_enabled") is False, "share_enabled not set to false"

        # Re-enable returns SAME slug
        r2 = auth_session.post(f"{BASE_URL}/api/projects/{READY_PID}/share")
        assert r2.status_code == 200
        assert r2.json()["share_slug"] == original_slug, "Re-enable minted a new slug!"


# ---------------------------------------------------------------------------
# TEST 2: /api/public/videos/{slug}
# ---------------------------------------------------------------------------
class TestPublicVideo:
    def _slug(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/projects/{READY_PID}/share")
        return r.json()["share_slug"]

    def test_public_endpoint_no_auth_required(self, auth_session):
        slug = self._slug(auth_session)
        # Fresh session — NO cookies
        fresh = requests.Session()
        r = fresh.get(f"{BASE_URL}/api/public/videos/{slug}")
        assert r.status_code == 200, f"Public GET failed: {r.status_code} {r.text}"
        data = r.json()
        for key in ("slug", "title", "hook", "duration_sec", "language", "style",
                    "video_url", "video_urls", "scenes", "creator_name", "view_count"):
            assert key in data, f"Missing key {key!r} in public response"
        # Data type sanity
        assert isinstance(data["scenes"], list)
        assert isinstance(data["view_count"], int)
        assert data["slug"] == slug

    def test_public_projection_no_private_leak(self, auth_session):
        # Ensure share is enabled (parallel workers may have disabled it)
        auth_session.post(f"{BASE_URL}/api/projects/{READY_PID}/share")
        slug = self._slug(auth_session)
        r = requests.get(f"{BASE_URL}/api/public/videos/{slug}")
        assert r.status_code == 200
        data = r.json()
        # Top-level must NOT contain private fields
        for forbidden in ("user_id", "email", "password_hash", "credits",
                          "plan", "role", "_id", "reset_token"):
            assert forbidden not in data, f"Leaked field {forbidden!r} in public response"
        # scenes projection must only have idx/heading/subtitle/image_url
        allowed_scene_keys = {"idx", "heading", "subtitle", "image_url"}
        for sc in data["scenes"]:
            extra = set(sc.keys()) - allowed_scene_keys
            assert not extra, f"Scene leaks fields: {extra} — scene keys: {list(sc.keys())}"
            for banned in ("image_prompt", "video_prompt", "narration",
                           "voice_url", "duration_sec"):
                assert banned not in sc, f"Scene leaked {banned!r}"

    def test_view_count_increments(self, auth_session):
        slug = self._slug(auth_session)
        r1 = requests.get(f"{BASE_URL}/api/public/videos/{slug}")
        r2 = requests.get(f"{BASE_URL}/api/public/videos/{slug}")
        r3 = requests.get(f"{BASE_URL}/api/public/videos/{slug}")
        assert r1.status_code == r2.status_code == r3.status_code == 200
        v1, v2, v3 = r1.json()["view_count"], r2.json()["view_count"], r3.json()["view_count"]
        assert v2 > v1 and v3 > v2, f"view_count not monotonic: {v1}, {v2}, {v3}"
        # And share_last_viewed_at is set
        async def _fetch():
            cli = AsyncIOMotorClient(MONGO_URL); db = cli[DB_NAME]
            p = await db.projects.find_one({"share_slug": slug}, {"_id": 0, "share_last_viewed_at": 1, "share_view_count": 1})
            cli.close()
            return p
        rec = asyncio.get_event_loop().run_until_complete(_fetch())
        assert rec.get("share_last_viewed_at"), "share_last_viewed_at not updated"
        assert isinstance(rec.get("share_view_count"), int) and rec["share_view_count"] >= 3

    def test_unknown_slug_returns_404(self):
        r = requests.get(f"{BASE_URL}/api/public/videos/nonexistentslug99")
        assert r.status_code == 404
        assert "no longer available" in (r.json().get("detail") or "").lower()

    def test_disabled_share_returns_404(self, auth_session):
        slug = self._slug(auth_session)
        auth_session.delete(f"{BASE_URL}/api/projects/{READY_PID}/share")
        r = requests.get(f"{BASE_URL}/api/public/videos/{slug}")
        assert r.status_code == 404
        assert "no longer available" in (r.json().get("detail") or "").lower()
        # Re-enable for downstream tests
        auth_session.post(f"{BASE_URL}/api/projects/{READY_PID}/share")


# ---------------------------------------------------------------------------
# TEST 3: MongoDB index
# ---------------------------------------------------------------------------
class TestShareIndex:
    def test_share_slug_index_unique_sparse(self):
        async def _check():
            cli = AsyncIOMotorClient(MONGO_URL); db = cli[DB_NAME]
            idx = await db.projects.index_information()
            cli.close()
            return idx
        idx = asyncio.get_event_loop().run_until_complete(_check())
        # Find any index on share_slug
        share_idx = None
        for name, spec in idx.items():
            keys = dict(spec.get("key") or {})
            if list(keys.keys()) == ["share_slug"]:
                share_idx = spec
                break
        assert share_idx is not None, f"No share_slug index found. Indexes: {list(idx.keys())}"
        assert share_idx.get("unique") is True, "share_slug index not unique"
        assert share_idx.get("sparse") is True, "share_slug index not sparse"


# ---------------------------------------------------------------------------
# TEST 4: Rate limit 120 req/min per IP  (kept LAST — most disruptive)
# ---------------------------------------------------------------------------
class TestRateLimit:
    def test_rate_limit_public_video_120_per_min(self, auth_session):
        # Get a valid slug
        r = auth_session.post(f"{BASE_URL}/api/projects/{READY_PID}/share")
        slug = r.json()["share_slug"]
        # Fire 130 requests as fast as we can from a fresh session (same IP)
        s = requests.Session()
        codes = []
        got_429 = False
        for i in range(140):
            r = s.get(f"{BASE_URL}/api/public/videos/{slug}", timeout=10)
            codes.append(r.status_code)
            if r.status_code == 429:
                got_429 = True
                break
        assert got_429, f"Never received 429 in 140 requests. Codes: {set(codes)}"
        # Confirm we got at least ~100 200-OKs before the 429
        assert codes.count(200) >= 100, f"Expected >=100 200s before 429 but got {codes.count(200)}"
