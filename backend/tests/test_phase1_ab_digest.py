"""Phase 1 additions #2 — Landing Page A/B testing + Daily Digest.

Covers:
- /api/experiments/landing_hero/{client_id} — variant assignment (deterministic)
- /api/admin/experiments — variant aggregation & winner
- /api/admin/digest/config, /preview, /preview.html, /send-now, /
- Scheduler registration (log check)
- Analytics track now honours properties.variant
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://script-to-video-382.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_admin_1784712404860"


@pytest.fixture(scope="module")
def anon_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ADMIN_TOKEN}",
    })
    s.cookies.set("session_token", ADMIN_TOKEN)
    return s


# ---------------- A/B experiments ----------------

class TestExperiments:
    def test_landing_hero_returns_variant_and_content(self, anon_client):
        cid = f"TEST_client_{uuid.uuid4().hex[:8]}"
        r = anon_client.get(f"{BASE_URL}/api/experiments/landing_hero/{cid}")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["experiment"] == "landing_hero"
        assert data["variant"] in ("A", "B")
        c = data["content"]
        for k in ("headline_pre", "headline_highlight", "headline_mid",
                  "headline_after", "subtitle", "eyebrow",
                  "cta_primary", "cta_secondary"):
            assert k in c and isinstance(c[k], str) and c[k], f"missing/empty {k}"

    def test_deterministic_same_client_id_same_variant(self, anon_client):
        cid = f"TEST_client_det_{uuid.uuid4().hex[:8]}"
        v1 = anon_client.get(f"{BASE_URL}/api/experiments/landing_hero/{cid}").json()["variant"]
        for _ in range(3):
            v = anon_client.get(f"{BASE_URL}/api/experiments/landing_hero/{cid}").json()["variant"]
            assert v == v1, f"variant flipped between calls: {v1} -> {v}"

    def test_both_variants_reachable(self, anon_client):
        seen = set()
        # Try several client ids to observe both variants
        for i in range(20):
            cid = f"TEST_client_dist_{i}_{uuid.uuid4().hex[:6]}"
            v = anon_client.get(f"{BASE_URL}/api/experiments/landing_hero/{cid}").json()["variant"]
            seen.add(v)
            if len(seen) >= 2:
                break
        assert seen == {"A", "B"}, f"only saw variants: {seen}"

    def test_known_client_ids_assignments(self, anon_client):
        # sanity — check specific ids referenced in review request
        for cid in ("test_client_a", "test_client_z"):
            r = anon_client.get(f"{BASE_URL}/api/experiments/landing_hero/{cid}")
            assert r.status_code == 200
            assert r.json()["variant"] in ("A", "B")

    def test_exposure_event_written(self, anon_client, admin_client):
        cid = f"TEST_expose_{uuid.uuid4().hex[:8]}"
        r = anon_client.get(f"{BASE_URL}/api/experiments/landing_hero/{cid}")
        assert r.status_code == 200
        assigned_variant = r.json()["variant"]
        # The exposure event should show up in admin/experiments aggregate ≥ 1 session
        # after we hit the endpoint. Give it a small settle time.
        time.sleep(0.5)
        r2 = admin_client.get(f"{BASE_URL}/api/admin/experiments")
        assert r2.status_code == 200, r2.text
        data = r2.json()
        # find variant row
        row = next((x for x in data["rows"] if x["variant"] == assigned_variant), None)
        assert row is not None
        assert row["sessions"] >= 1

    def test_admin_experiments_shape(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/experiments")
        assert r.status_code == 200
        data = r.json()
        assert data["experiment"] == "landing_hero"
        variants = {row["variant"] for row in data["rows"]}
        assert variants == {"A", "B"}, f"expected both variants, got {variants}"
        for row in data["rows"]:
            for k in ("sessions", "cta_clicks", "signups", "conversion_pct", "cta_ctr_pct"):
                assert k in row, f"row missing {k}"
                assert isinstance(row[k], (int, float))
        # winner may be None or 'A'/'B'
        assert data["winner"] in (None, "A", "B")

    def test_admin_experiments_requires_admin(self, anon_client):
        r = anon_client.get(f"{BASE_URL}/api/admin/experiments")
        assert r.status_code in (401, 403), f"non-admin should be blocked, got {r.status_code}"


# ---------------- Analytics variant plumbing ----------------

class TestAnalyticsVariant:
    def test_track_accepts_variant_property(self, anon_client, admin_client):
        # Fire a track with variant='A' and confirm it lands
        r = anon_client.post(f"{BASE_URL}/api/analytics/track", json={
            "event": "waitlist_button_click",
            "properties": {"variant": "A", "source": "TEST_variant_pytest"},
            "session_id": f"TEST_variant_sess_{uuid.uuid4().hex[:6]}",
            "path": "/",
        })
        assert r.status_code in (200, 201, 204), r.text


# ---------------- Digest ----------------

class TestDigest:
    def test_config(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/digest/config")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data.get("recipients"), list) and len(data["recipients"]) >= 1
        assert data["email_enabled"] is False, "RESEND_API_KEY should be unset"
        assert "IST" in data["schedule"]
        assert data["provider"] == "Resend"
        assert "sender" in data

    def test_config_requires_admin(self, anon_client):
        r = anon_client.get(f"{BASE_URL}/api/admin/digest/config")
        assert r.status_code in (401, 403)

    def test_preview_returns_model(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/digest/preview")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("visitors", "signups", "conversion_pct", "visitors_wow",
                  "signups_wow", "traffic_sources", "ab_test",
                  "demo_requests", "devices", "top_countries"):
            assert k in d, f"missing {k}"
        assert "rows" in d["ab_test"]
        assert isinstance(d["ab_test"]["rows"], list)
        assert isinstance(d["traffic_sources"], list)
        assert set(d["devices"].keys()) >= {"desktop", "mobile", "tablet", "unknown"}

    def test_preview_html(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/digest/preview.html")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")
        body = r.text
        assert "AI Video Studio · Daily Digest" in body
        assert "Visitors" in body
        assert "Waitlist signups" in body

    def test_send_now_returns_document(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/admin/digest/send-now")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"].startswith("digest_")
        assert d["delivery"]["sent"] is False
        assert "RESEND_API_KEY" in d["delivery"]["reason"]
        assert "AI Video Studio" in d["subject"]
        # Now verify listing contains it and html body is stripped
        lst = admin_client.get(f"{BASE_URL}/api/admin/digest").json()
        assert isinstance(lst, list) and len(lst) >= 1
        first = lst[0]
        assert "html" not in first
        # first should be our just-created id (most recent first)
        assert any(row["id"] == d["id"] for row in lst)

    def test_list_requires_admin(self, anon_client):
        r = anon_client.get(f"{BASE_URL}/api/admin/digest")
        assert r.status_code in (401, 403)


# ---------------- Scheduler ----------------

class TestScheduler:
    def test_startup_log_present(self):
        found = False
        for path in ("/var/log/supervisor/backend.err.log",
                     "/var/log/supervisor/backend.out.log"):
            if not os.path.exists(path):
                continue
            with open(path, "r", errors="ignore") as fh:
                if "Digest scheduler started" in fh.read():
                    found = True
                    break
        assert found, "Expected 'Digest scheduler started' log line to be present"
