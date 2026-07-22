"""
Retest for HIGH-severity bug from iteration 6:
duplicate 'direct' bucket in /api/admin/waitlist by_source aggregation.

Verifies:
1. DB state — no null/missing-source rows remain after startup migration.
2. by_source returns EXACTLY ONE 'direct' entry.
3. Sum of by_source.n == total.
4. count(?source=direct) == by_source[direct].n.
5. CSV export ?source=direct has (count + 1) rows and every source column is 'direct'.
"""
import os
import csv
import io
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
           "https://script-to-video-382.preview.emergentagent.com"
ADMIN_TOKEN = "test_admin_1784712404860"


@pytest.fixture
def admin_client():
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Cookie": f"session_token={ADMIN_TOKEN}",
    })
    return s


class TestDuplicateDirectBucketFix:
    def test_by_source_has_single_direct_entry(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/waitlist")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "by_source" in data
        direct_entries = [b for b in data["by_source"] if b["source"] == "direct"]
        assert len(direct_entries) == 1, (
            f"Expected exactly ONE 'direct' bucket, got {len(direct_entries)}: "
            f"{data['by_source']}"
        )
        # Also ensure no bucket has null/None/empty source key
        for b in data["by_source"]:
            assert b["source"], f"Found bucket with falsy source: {b}"

    def test_by_source_sum_equals_total(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/waitlist")
        assert r.status_code == 200
        data = r.json()
        summed = sum(b["n"] for b in data["by_source"])
        assert summed == data["total"], (
            f"by_source sum {summed} != total {data['total']} — "
            f"means some rows are unclassified. by_source={data['by_source']}"
        )

    def test_filter_direct_matches_bucket_size(self, admin_client):
        r_all = admin_client.get(f"{BASE_URL}/api/admin/waitlist")
        assert r_all.status_code == 200
        by_source = r_all.json()["by_source"]
        direct_bucket = next((b for b in by_source if b["source"] == "direct"), None)
        assert direct_bucket, "No 'direct' bucket present"

        r_filter = admin_client.get(f"{BASE_URL}/api/admin/waitlist?source=direct")
        assert r_filter.status_code == 200
        data = r_filter.json()
        assert data["count"] == direct_bucket["n"], (
            f"count(?source=direct)={data['count']} != by_source[direct].n="
            f"{direct_bucket['n']} — chip claim mismatches filtered rows"
        )
        # Total remains the collection-wide total (constant across filters)
        assert data["total"] == r_all.json()["total"]

    def test_csv_direct_exports_match_filter_count_and_source_column_is_direct(self, admin_client):
        # Filter JSON to know the expected row count
        r_json = admin_client.get(f"{BASE_URL}/api/admin/waitlist?source=direct")
        assert r_json.status_code == 200
        expected_count = r_json.json()["count"]

        r_csv = admin_client.get(f"{BASE_URL}/api/admin/waitlist.csv?source=direct")
        assert r_csv.status_code == 200
        assert r_csv.headers.get("content-type", "").startswith("text/csv")
        assert 'filename="waitlist-direct.csv"' in r_csv.headers.get(
            "content-disposition", ""
        )

        reader = csv.reader(io.StringIO(r_csv.text))
        rows = list(reader)
        assert len(rows) >= 1, "CSV has no header"
        header = rows[0]
        data_rows = rows[1:]
        assert len(data_rows) == expected_count, (
            f"CSV data rows={len(data_rows)} != JSON count={expected_count}"
        )
        # Every source cell must equal 'direct' (never blank)
        src_idx = header.index("source")
        for i, row in enumerate(data_rows):
            assert row[src_idx] == "direct", (
                f"Row {i}: source column={row[src_idx]!r}, expected 'direct'. "
                f"Row: {row}"
            )
