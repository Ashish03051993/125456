"""Phase 6 tests — Segment Compare (?source filter) + CSV exports.

Covers:
  * POST /api/waitlist accepts source/medium/campaign/variant and persists them.
    Missing source falls back to 'direct'.
  * GET /api/admin/waitlist returns {count,total,by_plan_interest,by_source,filters,entries}.
    - total stays constant across filters, count reflects filtered rows.
    - source/plan/q query params filter results.
    - Non-admin gets 401 (per current server behavior: 401 unauthed).
  * GET /api/admin/waitlist.csv returns text/csv with Content-Disposition attachment
    filename encoding the filter (waitlist-linkedin.csv).
  * GET /api/admin/utm-links.csv returns utm-campaigns.csv with expected columns.
"""
import os
import io
import csv
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://script-to-video-382.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_TOK = os.environ.get("ADMIN_TOK", "test_admin_1784712404860")
USER_TOK = os.environ.get("USER_TOK", "test_user_1784715294657")


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="session")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --------------------- Waitlist POST with attribution ---------------------
class TestWaitlistAttribution:
    def test_signup_with_attribution_persists_all_fields(self, http):
        email = f"TEST_seg6_{int(time.time())}@example.com"
        r = http.post(f"{API}/waitlist", json={
            "email": email,
            "name": "Seg6 User",
            "plan_interest": "pro",
            "use_case": "TEST_phase6_attr",
            "source": "linkedin",
            "medium": "post",
            "campaign": "beta_dec",
            "variant": "hero_a",
        })
        assert r.status_code == 200, r.text
        pos = r.json()["position"]
        assert isinstance(pos, int)

        # Verify via admin listing (backend lowercases emails)
        adm = http.get(f"{API}/admin/waitlist", headers=hdr(ADMIN_TOK),
                       params={"q": email})
        assert adm.status_code == 200
        entries = adm.json()["entries"]
        row = next((e for e in entries if e["email"] == email.lower()), None)
        assert row is not None, "signup row not visible in admin listing"
        assert row["source"] == "linkedin"
        assert row["medium"] == "post"
        assert row["campaign"] == "beta_dec"
        assert row["variant"] == "hero_a"

    def test_signup_without_source_defaults_to_direct(self, http):
        email = f"TEST_seg6_direct_{int(time.time())}@example.com"
        r = http.post(f"{API}/waitlist", json={"email": email})
        assert r.status_code == 200

        adm = http.get(f"{API}/admin/waitlist", headers=hdr(ADMIN_TOK),
                       params={"q": email})
        row = next((e for e in adm.json()["entries"] if e["email"] == email.lower()), None)
        assert row is not None
        assert row.get("source") == "direct"


# --------------------- Admin waitlist listing shape ---------------------
class TestAdminWaitlistListing:
    def test_shape_contains_all_keys(self, http):
        r = http.get(f"{API}/admin/waitlist", headers=hdr(ADMIN_TOK))
        assert r.status_code == 200
        b = r.json()
        for k in ("count", "total", "by_plan_interest", "by_source", "filters", "entries"):
            assert k in b, f"missing key: {k}"
        assert isinstance(b["by_source"], list)
        for row in b["by_source"]:
            assert "source" in row and "n" in row
        assert b["filters"] == {"source": None, "plan": None, "q": None}
        assert b["count"] == b["total"]  # unfiltered

    def test_source_filter_returns_only_matching(self, http):
        # Ensure at least one linkedin row exists (from prior tests / seed)
        http.post(f"{API}/waitlist", json={
            "email": f"TEST_seg6_lk_{int(time.time())}@example.com",
            "source": "linkedin", "medium": "post", "campaign": "beta_dec",
        })
        unfiltered = http.get(f"{API}/admin/waitlist", headers=hdr(ADMIN_TOK)).json()
        total = unfiltered["total"]

        r = http.get(f"{API}/admin/waitlist", headers=hdr(ADMIN_TOK),
                     params={"source": "linkedin"})
        assert r.status_code == 200
        b = r.json()
        assert b["filters"]["source"] == "linkedin"
        assert b["total"] == total, "total must stay constant across filters"
        assert b["count"] == len(b["entries"])
        assert b["count"] <= total
        assert b["count"] >= 1
        for e in b["entries"]:
            assert e["source"] == "linkedin"

    def test_plan_and_q_filters(self, http):
        # Seed a matching row
        email = f"TEST_seg6_qfilter_{int(time.time())}@example.com"
        http.post(f"{API}/waitlist", json={
            "email": email, "plan_interest": "business",
            "source": "twitter", "use_case": "unique_marker_phase6",
        })
        # plan filter
        r = http.get(f"{API}/admin/waitlist", headers=hdr(ADMIN_TOK),
                     params={"plan": "business"})
        assert r.status_code == 200
        assert all(e["plan_interest"] == "business" for e in r.json()["entries"])
        # q filter
        r = http.get(f"{API}/admin/waitlist", headers=hdr(ADMIN_TOK),
                     params={"q": "unique_marker_phase6"})
        assert r.status_code == 200
        assert len(r.json()["entries"]) >= 1

    def test_non_admin_returns_401_or_403(self, http):
        # Unauthenticated
        r = http.get(f"{API}/admin/waitlist")
        assert r.status_code == 401
        # User (non-admin) → 403 per require_admin
        r = http.get(f"{API}/admin/waitlist", headers=hdr(USER_TOK))
        assert r.status_code in (401, 403)


# --------------------- Waitlist CSV export ---------------------
class TestWaitlistCsvExport:
    def _parse_csv(self, text):
        rows = list(csv.reader(io.StringIO(text)))
        return rows[0], rows[1:]

    def test_csv_default_headers_and_filename(self, http):
        r = http.get(f"{API}/admin/waitlist.csv", headers=hdr(ADMIN_TOK))
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/csv")
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert 'filename="waitlist.csv"' in cd
        header, rows = self._parse_csv(r.text)
        assert header == ["position", "email", "name", "plan_interest",
                          "source", "medium", "campaign", "variant",
                          "use_case", "referrer", "created_at"]
        assert len(rows) >= 1

    def test_csv_source_filter_filename_and_rows(self, http):
        # ensure linkedin row exists
        http.post(f"{API}/waitlist", json={
            "email": f"TEST_seg6_csv_{int(time.time())}@example.com",
            "source": "linkedin",
        })
        r = http.get(f"{API}/admin/waitlist.csv", headers=hdr(ADMIN_TOK),
                     params={"source": "linkedin"})
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert 'filename="waitlist-linkedin.csv"' in cd
        header, rows = self._parse_csv(r.text)
        src_idx = header.index("source")
        assert all(row[src_idx] == "linkedin" for row in rows)
        assert len(rows) >= 1

    def test_csv_non_admin_401(self, http):
        r = http.get(f"{API}/admin/waitlist.csv")
        assert r.status_code == 401


# --------------------- UTM Links CSV export ---------------------
class TestUtmLinksCsvExport:
    def test_csv_headers_and_filename(self, http):
        r = http.get(f"{API}/admin/utm-links.csv", headers=hdr(ADMIN_TOK))
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/csv")
        assert 'filename="utm-campaigns.csv"' in r.headers.get("content-disposition", "")
        rows = list(csv.reader(io.StringIO(r.text)))
        header = rows[0]
        assert header == ["name", "url", "utm_source", "utm_medium",
                          "utm_campaign", "utm_content", "utm_term",
                          "sessions", "demo_clicks", "signups",
                          "conversion_pct", "created_at"]

    def test_csv_rows_match_json_endpoint(self, http):
        j = http.get(f"{API}/admin/utm-links", headers=hdr(ADMIN_TOK)).json()
        c = http.get(f"{API}/admin/utm-links.csv", headers=hdr(ADMIN_TOK))
        rows = list(csv.reader(io.StringIO(c.text)))[1:]
        assert len(rows) == len(j["rows"]), (
            f"csv rows ({len(rows)}) must equal json rows ({len(j['rows'])})"
        )

    def test_csv_non_admin_401(self, http):
        r = http.get(f"{API}/admin/utm-links.csv")
        assert r.status_code == 401
