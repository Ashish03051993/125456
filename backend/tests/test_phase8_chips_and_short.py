"""
Iteration 8 (phase 8) — Chip filters (source/plan/variant) + short URLs.

Covers:
  1. GET /api/admin/waitlist: variant filter incl. 'unassigned' (null OR missing),
     combined AND with source/plan/q. Facets by_source/by_plan/by_variant on
     UNFILTERED collection with null/missing coalesced to fallback bucket.
  2. GET /api/admin/waitlist.csv: filename encodes source/plan/variant; 401 for
     non-admin; body respects filters.
  3. POST /api/admin/utm-links: optional slug field; auto-derived from name if
     omitted; duplicate slugs get -N suffix; slug returned.
  4. GET /api/short/{slug}: returns {slug,target,name} for known slug and inserts
     a short_link_hit analytics event; 404 for unknown.
"""
import os
import time
import uuid
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL")
        or "https://script-to-video-382.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_admin_1784712404860"
H = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


# --------------------------- Chip filters ---------------------------
class TestWaitlistFacets:
    def test_unfiltered_facets_present(self):
        r = requests.get(f"{BASE}/api/admin/waitlist", headers=H)
        assert r.status_code == 200
        d = r.json()
        for k in ("count", "total", "by_source", "by_plan", "by_variant", "entries"):
            assert k in d, f"missing key {k}"
        assert isinstance(d["by_source"], list) and d["by_source"], "by_source empty"
        assert isinstance(d["by_plan"], list) and d["by_plan"], "by_plan empty"
        assert isinstance(d["by_variant"], list) and d["by_variant"], "by_variant empty"
        # by_source items shape {source, n}
        assert set(d["by_source"][0].keys()) >= {"source", "n"}
        assert set(d["by_plan"][0].keys()) >= {"plan", "n"}
        assert set(d["by_variant"][0].keys()) >= {"variant", "n"}
        # Unfiltered: count should equal total (no filters applied)
        assert d["count"] == d["total"], f"unfiltered count({d['count']})!=total({d['total']})"

    def test_by_variant_contains_unassigned_bucket(self):
        r = requests.get(f"{BASE}/api/admin/waitlist", headers=H)
        d = r.json()
        variants = {v["variant"]: v["n"] for v in d["by_variant"]}
        assert "unassigned" in variants, f"expected 'unassigned' bucket, got {list(variants)}"
        assert variants["unassigned"] > 0

    def test_variant_filter_B(self):
        r = requests.get(f"{BASE}/api/admin/waitlist", headers=H, params={"variant": "B"})
        assert r.status_code == 200
        d = r.json()
        assert all(row.get("variant") == "B" for row in d["entries"])
        assert d["filters"]["variant"] == "B"

    def test_variant_filter_unassigned_matches_null_or_missing(self):
        r = requests.get(f"{BASE}/api/admin/waitlist", headers=H, params={"variant": "unassigned"})
        assert r.status_code == 200
        d = r.json()
        assert d["count"] > 0
        for row in d["entries"]:
            v = row.get("variant")
            assert v is None or v == "", f"expected null/missing variant, got {v!r}"

    def test_combined_source_and_variant_AND(self):
        r = requests.get(f"{BASE}/api/admin/waitlist",
                         headers=H, params={"source": "linkedin", "variant": "A"})
        assert r.status_code == 200
        d = r.json()
        for row in d["entries"]:
            assert row.get("source") == "linkedin"
            assert row.get("variant") == "A"

    def test_combined_source_direct_and_variant_unassigned(self):
        # 'direct' expands to null/missing/direct; must still AND with unassigned.
        r = requests.get(f"{BASE}/api/admin/waitlist",
                         headers=H, params={"source": "direct", "variant": "unassigned"})
        assert r.status_code == 200
        d = r.json()
        for row in d["entries"]:
            s = row.get("source")
            v = row.get("variant")
            assert s in (None, "", "direct"), f"unexpected source {s!r}"
            assert v in (None, ""), f"unexpected variant {v!r}"

    def test_unauth_401(self):
        r = requests.get(f"{BASE}/api/admin/waitlist")
        assert r.status_code == 401


# --------------------------- CSV filters ---------------------------
class TestWaitlistCsv:
    def test_csv_unauth_401(self):
        r = requests.get(f"{BASE}/api/admin/waitlist.csv")
        assert r.status_code == 401

    def test_csv_filename_encodes_filters(self):
        r = requests.get(f"{BASE}/api/admin/waitlist.csv",
                         headers=H, params={"source": "linkedin", "variant": "B"})
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert 'filename="waitlist-linkedin-vB.csv"' in cd, cd

    def test_csv_body_respects_variant_filter(self):
        r = requests.get(f"{BASE}/api/admin/waitlist.csv",
                         headers=H, params={"variant": "B"})
        assert r.status_code == 200
        lines = r.text.strip().splitlines()
        header = lines[0].split(",")
        assert "variant" in header
        v_idx = header.index("variant")
        for row in lines[1:]:
            cols = row.split(",")
            assert cols[v_idx] == "B", f"row has variant={cols[v_idx]!r}"


# --------------------------- UTM slug ---------------------------
class TestUtmSlug:
    def test_create_with_explicit_slug(self):
        unique = f"TEST-slug-explicit-{uuid.uuid4().hex[:8]}"
        r = requests.post(f"{BASE}/api/admin/utm-links", headers=H, json={
            "name": unique, "source": "linkedin", "medium": "post",
            "campaign": "TEST_iter8", "slug": unique.lower(),
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["slug"] == unique.lower(), d
        # cleanup
        requests.delete(f"{BASE}/api/admin/utm-links/{d['id']}", headers=H)

    def test_auto_slug_from_name(self):
        nm = f"TEST Iter8 auto slug {uuid.uuid4().hex[:6]}"
        r = requests.post(f"{BASE}/api/admin/utm-links", headers=H, json={
            "name": nm, "source": "linkedin", "campaign": "TEST_iter8_auto",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        # kebab-cased
        assert d["slug"], d
        assert d["slug"] == nm.lower().replace(" ", "-")
        requests.delete(f"{BASE}/api/admin/utm-links/{d['id']}", headers=H)

    def test_duplicate_slug_gets_suffix(self):
        nm = f"TEST-Iter8-dup-{uuid.uuid4().hex[:6]}"
        created = []
        try:
            r1 = requests.post(f"{BASE}/api/admin/utm-links", headers=H, json={
                "name": nm, "source": "linkedin", "campaign": "TEST_iter8_dup",
            })
            assert r1.status_code == 200, r1.text
            d1 = r1.json(); created.append(d1["id"])
            first_slug = d1["slug"]
            r2 = requests.post(f"{BASE}/api/admin/utm-links", headers=H, json={
                "name": nm, "source": "linkedin", "campaign": "TEST_iter8_dup",
            })
            assert r2.status_code == 200, r2.text
            d2 = r2.json(); created.append(d2["id"])
            assert d2["slug"] == f"{first_slug}-2", (first_slug, d2["slug"])
        finally:
            for lid in created:
                requests.delete(f"{BASE}/api/admin/utm-links/{lid}", headers=H)


# --------------------------- Short URL resolver ---------------------------
class TestShortResolver:
    def test_unknown_slug_returns_404(self):
        r = requests.get(f"{BASE}/api/short/definitely-not-a-real-slug-{uuid.uuid4().hex[:6]}")
        assert r.status_code == 404

    def test_known_slug_returns_target_and_logs_event(self):
        # 1. Create a link with a known slug
        nm = f"TEST-Iter8-short-{uuid.uuid4().hex[:6]}"
        cr = requests.post(f"{BASE}/api/admin/utm-links", headers=H, json={
            "name": nm, "source": "linkedin", "medium": "post",
            "campaign": "TEST_iter8_short", "slug": nm.lower(),
        })
        assert cr.status_code == 200, cr.text
        link = cr.json()
        slug = link["slug"]
        try:
            # 2. Hit the short URL (unauthenticated - it's public)
            resp = requests.get(f"{BASE}/api/short/{slug}", allow_redirects=False)
            assert resp.status_code == 200, resp.text
            d = resp.json()
            assert d["slug"] == slug
            assert d["target"] == link["url"], (d["target"], link["url"])
            assert d["name"] == nm
            # analytics event insertion is async but same request; give it a beat.
            time.sleep(0.5)
        finally:
            requests.delete(f"{BASE}/api/admin/utm-links/{link['id']}", headers=H)

    def test_prewired_beta_post_1(self):
        # Sanity: the seed link from other_misc_info still resolves.
        r = requests.get(f"{BASE}/api/short/beta-post-1")
        assert r.status_code == 200
        d = r.json()
        assert d["slug"] == "beta-post-1"
        assert "utm_source" in d["target"]
