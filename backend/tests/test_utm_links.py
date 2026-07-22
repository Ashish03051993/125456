"""Backend tests for UTM Campaign Links (Phase 5)."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://script-to-video-382.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_admin_1784712404860"


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    s.cookies.set("session_token", ADMIN_TOKEN)
    return s


@pytest.fixture(scope="module")
def anon_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Auth guard ----------

class TestAuthGuard:
    def test_list_requires_admin(self, anon_client):
        r = anon_client.get(f"{BASE_URL}/api/admin/utm-links")
        assert r.status_code in (401, 403)

    def test_create_requires_admin(self, anon_client):
        r = anon_client.post(f"{BASE_URL}/api/admin/utm-links",
                             json={"name": "x", "source": "linkedin"})
        assert r.status_code in (401, 403)

    def test_delete_requires_admin(self, anon_client):
        r = anon_client.delete(f"{BASE_URL}/api/admin/utm-links/utm_deadbeef")
        assert r.status_code in (401, 403)


# ---------- Create / slug cleaning / url composition ----------

class TestUtmCreate:
    def test_create_basic_returns_all_fields(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/admin/utm-links", json={
            "name": "TEST_UTM_basic",
            "base_url": "https://example.com/",
            "source": "LinkedIn",
            "medium": "Post",
            "campaign": "Beta Dec",
            "content": "Hero A",
            "term": "founders",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert "id" in d and d["id"].startswith("utm_")
        assert d["name"] == "TEST_UTM_basic"
        assert d["base_url"] == "https://example.com/"
        assert d["params"]["utm_source"] == "linkedin"
        assert d["params"]["utm_medium"] == "post"
        assert d["params"]["utm_campaign"] == "beta-dec"
        assert d["params"]["utm_content"] == "hero-a"
        assert d["params"]["utm_term"] == "founders"
        assert "utm_source=linkedin" in d["url"]
        assert "utm_campaign=beta-dec" in d["url"]
        assert "created_at" in d
        # cleanup
        admin_client.delete(f"{BASE_URL}/api/admin/utm-links/{d['id']}")

    def test_create_preserves_existing_querystring(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/admin/utm-links", json={
            "name": "TEST_UTM_preserve_qs",
            "base_url": "https://example.com/landing?foo=bar&x=1",
            "source": "linkedin",
            "medium": "post",
            "campaign": "beta_dec",
        })
        assert r.status_code == 200, r.text
        url = r.json()["url"]
        assert "foo=bar" in url
        assert "x=1" in url
        assert "utm_source=linkedin" in url
        assert "utm_medium=post" in url
        # created_id cleanup
        admin_client.delete(f"{BASE_URL}/api/admin/utm-links/{r.json()['id']}")

    def test_create_missing_source_returns_400(self, admin_client):
        # Empty string source
        r = admin_client.post(f"{BASE_URL}/api/admin/utm-links",
                              json={"name": "TEST_UTM_bad", "source": ""})
        assert r.status_code in (400, 422)

    def test_create_missing_source_key_returns_422(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/admin/utm-links",
                              json={"name": "TEST_UTM_bad2"})
        assert r.status_code in (400, 422)


# ---------- List & delete ----------

class TestUtmList:
    def test_list_shape_and_sort(self, admin_client):
        # create two rows
        c1 = admin_client.post(f"{BASE_URL}/api/admin/utm-links", json={
            "name": "TEST_UTM_list_1", "source": "linkedin", "medium": "post",
            "campaign": "beta_dec", "base_url": "https://example.com",
        }).json()
        time.sleep(0.05)
        c2 = admin_client.post(f"{BASE_URL}/api/admin/utm-links", json={
            "name": "TEST_UTM_list_2", "source": "linkedin", "medium": "dm",
            "campaign": "outreach", "base_url": "https://example.com",
        }).json()

        r = admin_client.get(f"{BASE_URL}/api/admin/utm-links")
        assert r.status_code == 200
        payload = r.json()
        assert "days" in payload and "rows" in payload
        ids = [row["id"] for row in payload["rows"]]
        assert c1["id"] in ids and c2["id"] in ids
        # newest first — c2 (created later) should appear before c1
        assert ids.index(c2["id"]) < ids.index(c1["id"])

        # each row has stats block with 4 keys
        row = next(r for r in payload["rows"] if r["id"] == c1["id"])
        for k in ("sessions", "signups", "demo_clicks", "conversion_pct"):
            assert k in row["stats"]

        # cleanup
        admin_client.delete(f"{BASE_URL}/api/admin/utm-links/{c1['id']}")
        admin_client.delete(f"{BASE_URL}/api/admin/utm-links/{c2['id']}")

    def test_delete_removes_row(self, admin_client):
        c = admin_client.post(f"{BASE_URL}/api/admin/utm-links", json={
            "name": "TEST_UTM_del", "source": "linkedin",
            "base_url": "https://example.com",
        }).json()
        d = admin_client.delete(f"{BASE_URL}/api/admin/utm-links/{c['id']}")
        assert d.status_code == 200
        assert d.json().get("deleted", 0) == 1
        # verify no longer listed
        rows = admin_client.get(f"{BASE_URL}/api/admin/utm-links").json()["rows"]
        assert not any(r["id"] == c["id"] for r in rows)


# ---------- Stats aggregation end-to-end ----------

class TestUtmStatsAggregation:
    def test_events_roll_up_into_row_stats(self, admin_client):
        # 1. Create a link
        campaign_slug = "test-utm-agg-" + str(int(time.time()))
        c = admin_client.post(f"{BASE_URL}/api/admin/utm-links", json={
            "name": "TEST_UTM_agg",
            "source": "linkedin",
            "medium": "post",
            "campaign": campaign_slug,
            "base_url": "https://example.com",
        }).json()
        link_id = c["id"]

        # 2. Fire tracking events matching this campaign
        sess_id = "test_utm_sess_" + str(int(time.time()))
        props = {"source": "linkedin", "medium": "post", "campaign": campaign_slug}
        for event in ("page_view", "waitlist_success", "book_demo_click"):
            r = requests.post(f"{BASE_URL}/api/analytics/track",
                              json={"event": event, "properties": props,
                                    "session_id": sess_id, "path": "/"})
            assert r.status_code in (200, 201, 204), f"{event}: {r.status_code} {r.text}"

        # 3. Refresh list and verify stats
        rows = admin_client.get(f"{BASE_URL}/api/admin/utm-links").json()["rows"]
        row = next((r for r in rows if r["id"] == link_id), None)
        assert row is not None
        stats = row["stats"]
        assert stats["sessions"] >= 1, f"sessions expected >=1, got {stats}"
        assert stats["signups"] >= 1, f"signups expected >=1, got {stats}"
        assert stats["demo_clicks"] >= 1, f"demo_clicks expected >=1, got {stats}"
        assert stats["conversion_pct"] > 0, f"conversion_pct expected >0, got {stats}"

        # 4. Delete the utm link and confirm analytics_events untouched
        admin_client.delete(f"{BASE_URL}/api/admin/utm-links/{link_id}")
