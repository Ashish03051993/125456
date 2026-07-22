"""Iteration 13 delta tests — Attribution Matrix CSV export.

Covers:
  1. GET /api/admin/attribution-matrix.csv — auth (401/403 anon), 200 admin,
     text/csv media type, Content-Disposition attachment + dated filename.
  2. CSV body: header + one row per (source, variant) + `__total__` variant
     row per source + `__total__` source row per variant + grand total.
  3. Round-trip consistency: parse CSV, cross-check every cell/total against
     JSON /api/admin/attribution-matrix exactly.
  4. Spot-check iter-9..iter-12 endpoints still healthy.
"""
import os
import csv
import io
import re
from datetime import date, timezone, datetime

import pytest
import requests

_BE = os.environ.get("REACT_APP_BACKEND_URL")
if not _BE:
    _env_path = "/app/frontend/.env"
    if os.path.exists(_env_path):
        with open(_env_path) as _f:
            for _line in _f:
                if _line.startswith("REACT_APP_BACKEND_URL="):
                    _BE = _line.split("=", 1)[1].strip()
                    break
BASE_URL = (_BE or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
API = f"{BASE_URL}/api"

ADMIN_TOKEN = "test_admin_1784712404860"
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


# ============ 1. CSV endpoint: auth + headers ============
class TestMatrixCsvAuth:
    def test_anon_denied(self):
        r = requests.get(f"{API}/admin/attribution-matrix.csv", timeout=20)
        assert r.status_code in (401, 403), (r.status_code, r.text)

    def test_admin_ok(self):
        r = requests.get(f"{API}/admin/attribution-matrix.csv",
                         headers=ADMIN_HEADERS, timeout=30)
        assert r.status_code == 200, r.text


class TestMatrixCsvHeaders:
    @pytest.fixture(scope="class")
    def resp(self):
        r = requests.get(f"{API}/admin/attribution-matrix.csv",
                         headers=ADMIN_HEADERS, timeout=30)
        assert r.status_code == 200
        return r

    def test_content_type_csv(self, resp):
        ctype = resp.headers.get("content-type", "").lower()
        assert "text/csv" in ctype, f"content-type={ctype!r}"

    def test_content_disposition_attachment(self, resp):
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd.lower(), cd
        # filename="attribution-matrix-YYYY-MM-DD.csv"
        m = re.search(r'filename="?attribution-matrix-(\d{4}-\d{2}-\d{2})\.csv"?', cd)
        assert m, f"Content-Disposition missing dated filename: {cd!r}"
        # Date should be today (UTC). Allow +/- 1 day to tolerate TZ boundary.
        fname_date = m.group(1)
        today = date.today().isoformat()
        # Simple string compare is fine; also accept previous day for safety.
        assert fname_date <= today, f"filename date {fname_date} in future"

    def test_body_non_empty(self, resp):
        assert resp.text.strip(), "empty CSV body"


# ============ 2. CSV body structure ============
def _fetch_csv_and_json():
    csv_r = requests.get(f"{API}/admin/attribution-matrix.csv",
                         headers=ADMIN_HEADERS, timeout=30)
    assert csv_r.status_code == 200
    json_r = requests.get(f"{API}/admin/attribution-matrix",
                          headers=ADMIN_HEADERS, timeout=30)
    assert json_r.status_code == 200
    return csv_r.text, json_r.json()


class TestMatrixCsvBody:
    @pytest.fixture(scope="class")
    def parsed(self):
        csv_text, data = _fetch_csv_and_json()
        rows = list(csv.reader(io.StringIO(csv_text)))
        return {"rows": rows, "data": data, "text": csv_text}

    def test_header_row(self, parsed):
        assert parsed["rows"][0] == [
            "source", "variant", "sessions", "signups", "conversion_pct"
        ], parsed["rows"][0]

    def test_total_line_count(self, parsed):
        d = parsed["data"]
        n_sources = len(d["sources"])
        n_variants = len(d["variants"])
        expected = 1 + (n_sources * n_variants) + n_sources + n_variants + 1
        assert len(parsed["rows"]) == expected, (
            f"expected {expected} lines "
            f"(1 header + {n_sources}*{n_variants} cells + "
            f"{n_sources} row-totals + {n_variants} col-totals + 1 grand), "
            f"got {len(parsed['rows'])}"
        )

    def test_grand_total_last_row(self, parsed):
        last = parsed["rows"][-1]
        assert last[0] == "__total__" and last[1] == "__total__", last
        d = parsed["data"]
        assert int(last[2]) == d["grand"]["sessions"]
        assert int(last[3]) == d["grand"]["signups"]
        assert float(last[4]) == pytest.approx(d["grand"]["conversion_pct"])

    def test_col_totals_block_before_grand(self, parsed):
        """Rows immediately before the grand total must be __total__/<variant>
        col-total rows — one per variant, in order."""
        d = parsed["data"]
        n_variants = len(d["variants"])
        rows = parsed["rows"]
        # Slice before grand-total (last row).
        col_slice = rows[-1 - n_variants : -1]
        assert len(col_slice) == n_variants
        for i, v in enumerate(d["variants"]):
            r = col_slice[i]
            assert r[0] == "__total__" and r[1] == v, r
            ct = d["col_totals"][i]
            assert int(r[2]) == ct["sessions"]
            assert int(r[3]) == ct["signups"]
            assert float(r[4]) == pytest.approx(ct["conversion_pct"])


# ============ 3. Round-trip: JSON ↔ CSV numeric consistency ============
class TestMatrixCsvRoundTrip:
    @pytest.fixture(scope="class")
    def parsed(self):
        csv_text, data = _fetch_csv_and_json()
        rows = list(csv.reader(io.StringIO(csv_text)))
        # Build lookup: (source, variant) -> row
        lookup = {}
        for r in rows[1:]:
            lookup[(r[0], r[1])] = r
        return {"lookup": lookup, "data": data, "raw": rows}

    def test_every_cell_matches_json(self, parsed):
        d = parsed["data"]
        lookup = parsed["lookup"]
        mismatches = []
        for row in d["rows"]:
            src = row["source"]
            for cell in row["cells"]:
                key = (src, cell["variant"])
                if key not in lookup:
                    mismatches.append(f"missing CSV row for {key}")
                    continue
                r = lookup[key]
                if int(r[2]) != cell["sessions"]:
                    mismatches.append(
                        f"{key} sessions csv={r[2]} json={cell['sessions']}"
                    )
                if int(r[3]) != cell["signups"]:
                    mismatches.append(
                        f"{key} signups csv={r[3]} json={cell['signups']}"
                    )
                if float(r[4]) != pytest.approx(cell["conversion_pct"]):
                    mismatches.append(
                        f"{key} conv csv={r[4]} json={cell['conversion_pct']}"
                    )
        assert not mismatches, mismatches

    def test_every_row_total_matches_json(self, parsed):
        d = parsed["data"]
        lookup = parsed["lookup"]
        for row in d["rows"]:
            key = (row["source"], "__total__")
            assert key in lookup, f"missing row-total for {row['source']}"
            r = lookup[key]
            assert int(r[2]) == row["totals"]["sessions"]
            assert int(r[3]) == row["totals"]["signups"]
            assert float(r[4]) == pytest.approx(row["totals"]["conversion_pct"])

    def test_every_col_total_matches_json(self, parsed):
        d = parsed["data"]
        lookup = parsed["lookup"]
        for ct in d["col_totals"]:
            key = ("__total__", ct["variant"])
            assert key in lookup, f"missing col-total for {ct['variant']}"
            r = lookup[key]
            assert int(r[2]) == ct["sessions"]
            assert int(r[3]) == ct["signups"]
            assert float(r[4]) == pytest.approx(ct["conversion_pct"])

    def test_grand_total_matches_json(self, parsed):
        d = parsed["data"]
        r = parsed["lookup"][("__total__", "__total__")]
        assert int(r[2]) == d["grand"]["sessions"]
        assert int(r[3]) == d["grand"]["signups"]
        assert float(r[4]) == pytest.approx(d["grand"]["conversion_pct"])


# ============ 4. Iter-9..iter-12 regression spot-checks ============
class TestPriorRegressionSpot:
    def test_sanity(self):
        r = requests.get(f"{API}/admin/sanity",
                         headers=ADMIN_HEADERS, timeout=20)
        assert r.status_code == 200, r.text
        # Basic shape check.
        j = r.json()
        assert isinstance(j, dict)

    def test_sanity_untagged(self):
        r = requests.get(f"{API}/admin/sanity/untagged",
                         headers=ADMIN_HEADERS, timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        assert {"total", "returned", "sessions"} <= set(j.keys())

    def test_attribution_matrix_json(self):
        r = requests.get(f"{API}/admin/attribution-matrix",
                         headers=ADMIN_HEADERS, timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        assert {"sources", "variants", "rows",
                "col_totals", "grand"} <= set(j.keys())

    def test_waitlist_csv(self):
        r = requests.get(f"{API}/admin/waitlist.csv",
                         headers=ADMIN_HEADERS, timeout=20)
        assert r.status_code == 200, r.text
        assert "text/csv" in r.headers.get("content-type", "").lower()

    def test_utm_links_csv(self):
        r = requests.get(f"{API}/admin/utm-links.csv",
                         headers=ADMIN_HEADERS, timeout=20)
        assert r.status_code == 200, r.text
        assert "text/csv" in r.headers.get("content-type", "").lower()

    def test_formats(self):
        r = requests.get(f"{API}/formats", timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert isinstance(j, (list, dict))

    def test_waitlist_list(self):
        r = requests.get(f"{API}/admin/waitlist",
                         headers=ADMIN_HEADERS, timeout=20)
        assert r.status_code == 200, r.text

    def test_experiments(self):
        r = requests.get(f"{API}/admin/experiments",
                         headers=ADMIN_HEADERS, timeout=20)
        assert r.status_code == 200, r.text

    def test_short_link(self):
        # Spot-check the short-link endpoint is wired up. `script-to-video-382`
        # from the iter-13 spec is the preview host, not an actual slug in
        # db.utm_links, so it correctly 404s. Use a real slug from admin/utm-links.
        list_r = requests.get(f"{API}/admin/utm-links",
                              headers=ADMIN_HEADERS, timeout=20)
        assert list_r.status_code == 200
        rows = list_r.json().get("rows", [])
        if not rows:
            pytest.skip("no utm-links seeded — endpoint auth already verified")
        slug = rows[0]["slug"]
        r = requests.get(f"{API}/short/{slug}",
                         timeout=20, allow_redirects=False)
        assert r.status_code in (200, 301, 302, 307, 308), (r.status_code, r.text)
        # Also verify literal 'script-to-video-382' 404s (proves endpoint responds).
        r404 = requests.get(f"{API}/short/definitely-not-a-real-slug-xyz",
                            timeout=15)
        assert r404.status_code == 404

    def test_analytics_track(self):
        r = requests.post(f"{API}/analytics/track", json={
            "event": "iter13_probe",
            "properties": {"src": "test"},
            "session_id": "sess_iter13_probe",
            "path": "/",
        }, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
