"""Iter-15 HIGH bug fix retest: `_client_ip(request)` helper + rate-limit spoofing protection.

Covers 4 unit scenarios for the new `_client_ip` helper:
  (1) peer in trusted CIDR + XFF present   → returns first XFF hop
  (2) peer in trusted CIDR + only X-Real-IP → returns X-Real-IP
  (3) peer NOT in trusted CIDR + forged XFF → IGNORES XFF (spoofing protection)
  (4) no peer, no headers                    → returns 'unknown'

Plus:
  - Rate-limit key derived from _client_ip (not peer) — same trusted-peer with
    different XFF values is treated as DIFFERENT users; same untrusted peer
    with rotating XFF values is treated as the SAME user (cannot bypass).
  - Live smoke: 5 successive /api/waitlist calls succeed and 6th returns 429
    from a single external caller (rate-limit end-to-end).
  - Spoofing protection over the wire: forged X-Forwarded-For from an external
    caller is ignored — the ingress overwrites/appends it, so the FIRST value
    in the header at backend receipt is our own untrusted external IP anyway,
    which the backend correctly does not honor because the peer is the ingress
    (trusted), it re-reads XFF that was set/appended by the ingress and uses
    the first hop = real caller IP (this is standard nginx-ingress behavior).
    We just assert that repeated calls from same external IP with rotating
    forged XFF header still get rate-limited.
"""
import os
import sys
import uuid
from pathlib import Path

import pytest
import requests
from fastapi import HTTPException

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://script-to-video-382.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

# Make backend importable for unit tests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# Unit tests for _client_ip helper
# ---------------------------------------------------------------------------
class _Client:
    def __init__(self, host):
        self.host = host


class _Req:
    """Minimal Request-like double for unit-testing _client_ip."""

    def __init__(self, peer_ip, headers=None):
        self.client = _Client(peer_ip) if peer_ip is not None else None
        self.headers = headers or {}


class TestClientIpHelper:
    """4 required scenarios for the _client_ip helper."""

    def test_scenario_1_trusted_peer_with_xff(self):
        """Peer in trusted CIDR + XFF='203.0.113.7, 10.231.142.130' → '203.0.113.7'."""
        from server import _client_ip

        req = _Req(
            peer_ip="10.231.142.130",  # inside 10.0.0.0/8 (trusted)
            headers={"x-forwarded-for": "203.0.113.7, 10.231.142.130"},
        )
        assert _client_ip(req) == "203.0.113.7"

    def test_scenario_2_trusted_peer_with_only_x_real_ip(self):
        """Peer in trusted CIDR + only X-Real-IP='203.0.113.42' → '203.0.113.42'."""
        from server import _client_ip

        req = _Req(
            peer_ip="10.231.142.130",
            headers={"x-real-ip": "203.0.113.42"},
        )
        assert _client_ip(req) == "203.0.113.42"

    def test_scenario_3_untrusted_peer_ignores_forged_xff(self):
        """Peer NOT in trusted CIDR + forged XFF header → IGNORES XFF (returns real peer).

        This is the critical spoofing-protection test: an attacker connecting
        directly (peer is a public IP) cannot inject a fake XFF header to
        rotate rate-limit buckets and bypass the limits.
        """
        from server import _client_ip

        req = _Req(
            peer_ip="203.0.113.10",  # public IP, NOT in any trusted CIDR
            headers={"x-forwarded-for": "1.2.3.4", "x-real-ip": "5.6.7.8"},
        )
        # Must return the real L4 peer, not the forged XFF/X-Real-IP values.
        assert _client_ip(req) == "203.0.113.10"

    def test_scenario_4_no_peer_no_headers(self):
        """No peer, no headers → 'unknown'."""
        from server import _client_ip

        req = _Req(peer_ip=None, headers={})
        assert _client_ip(req) == "unknown"

    # --------- Extra safety scenarios (regression) ---------
    def test_trusted_peer_no_headers_returns_peer(self):
        from server import _client_ip

        req = _Req(peer_ip="10.231.142.130", headers={})
        assert _client_ip(req) == "10.231.142.130"

    def test_trusted_cidr_172_variants(self):
        """172.16.0.0/12 is trusted; 172.15/172.32 are NOT."""
        from server import _client_ip

        # 172.16.x.x → trusted → honor XFF
        req_in = _Req(peer_ip="172.16.5.5", headers={"x-forwarded-for": "9.9.9.9"})
        assert _client_ip(req_in) == "9.9.9.9"
        # 172.15.x.x → NOT trusted → ignore XFF
        req_out = _Req(peer_ip="172.15.5.5", headers={"x-forwarded-for": "9.9.9.9"})
        assert _client_ip(req_out) == "172.15.5.5"

    def test_localhost_peer_is_trusted(self):
        from server import _client_ip

        req = _Req(peer_ip="127.0.0.1", headers={"x-forwarded-for": "8.8.8.8"})
        assert _client_ip(req) == "8.8.8.8"

    def test_xff_whitespace_stripped(self):
        from server import _client_ip

        req = _Req(peer_ip="10.0.0.1",
                   headers={"x-forwarded-for": "   203.0.113.99   ,10.0.0.1"})
        assert _client_ip(req) == "203.0.113.99"

    def test_invalid_peer_ip_treated_as_untrusted(self):
        from server import _client_ip

        req = _Req(peer_ip="not-an-ip", headers={"x-forwarded-for": "1.2.3.4"})
        assert _client_ip(req) == "not-an-ip"


# ---------------------------------------------------------------------------
# Rate-limit key derivation now uses _client_ip (not raw peer)
# ---------------------------------------------------------------------------
class TestRateLimitUsesClientIp:
    def setup_method(self):
        from server import _rate_limit_store
        _rate_limit_store.clear()

    def test_trusted_peer_different_xff_are_isolated(self):
        """Two calls from same ingress peer but DIFFERENT XFF (=different real users)
        must have independent buckets."""
        from server import _rate_limit_check
        # Real end-user A behind ingress
        req_a = _Req(peer_ip="10.231.142.130",
                     headers={"x-forwarded-for": "203.0.113.1"})
        # Real end-user B behind ingress
        req_b = _Req(peer_ip="10.231.142.130",
                     headers={"x-forwarded-for": "203.0.113.2"})
        for _ in range(5):
            _rate_limit_check(req_a, "waitlist", limit=5, window_seconds=3600)
        # A is capped
        with pytest.raises(HTTPException):
            _rate_limit_check(req_a, "waitlist", limit=5, window_seconds=3600)
        # B still fine — proves independent buckets keyed on real IP
        for _ in range(5):
            _rate_limit_check(req_b, "waitlist", limit=5, window_seconds=3600)

    def test_untrusted_peer_cannot_rotate_xff_to_bypass(self):
        """Attacker connects directly (untrusted peer) and rotates XFF header
        each request — should still be treated as SAME bucket (peer IP)."""
        from server import _rate_limit_check
        attacker_ip = "203.0.113.66"
        # Fire 5 requests with rotating forged XFF values
        for i in range(5):
            req = _Req(peer_ip=attacker_ip,
                       headers={"x-forwarded-for": f"9.9.9.{i}"})
            _rate_limit_check(req, "waitlist", limit=5, window_seconds=3600)
        # 6th, still with a new forged XFF, MUST be rate-limited
        req6 = _Req(peer_ip=attacker_ip,
                    headers={"x-forwarded-for": "9.9.9.99"})
        with pytest.raises(HTTPException) as excinfo:
            _rate_limit_check(req6, "waitlist", limit=5, window_seconds=3600)
        assert excinfo.value.status_code == 429


# ---------------------------------------------------------------------------
# Live end-to-end smoke tests
# ---------------------------------------------------------------------------
class TestWaitlistLiveRateLimitFix:
    """Confirm the rate-limit fires on the live endpoint from the same external
    caller. Cleans up rows on teardown."""

    inserted_emails = []

    def test_five_pass_then_429(self):
        # Reset local store (this works because the test process runs in the
        # same container as the backend for pytest.)
        try:
            from server import _rate_limit_store
            for k in list(_rate_limit_store):
                if k[1] == "waitlist":
                    del _rate_limit_store[k]
        except Exception:
            pytest.skip("Cannot reach in-memory store — running remotely")

        base = f"ratefix_{uuid.uuid4().hex[:6]}"
        successes = 0
        got_429 = False
        for i in range(7):
            email = f"{base}_{i}@example.com"
            r = requests.post(f"{API}/waitlist", json={"email": email}, timeout=10)
            if r.status_code == 200:
                successes += 1
                type(self).inserted_emails.append(email)
            elif r.status_code == 429:
                got_429 = True
                # keep going to confirm >=2 429s
        assert successes == 5, (
            f"expected exactly 5 successes then 429s, got successes={successes}")
        assert got_429, "expected 429 after 5 successful signups"

    def test_forged_xff_does_not_bypass(self):
        """Send /waitlist with a forged X-Forwarded-For — cluster ingress will
        overwrite/append it, so backend derives the real IP from the trusted
        peer and the forged value is functionally ignored. In particular,
        rotating the forged value across requests must NOT reset the bucket.
        """
        # Reset store first
        try:
            from server import _rate_limit_store
            for k in list(_rate_limit_store):
                if k[1] == "waitlist":
                    del _rate_limit_store[k]
        except Exception:
            pytest.skip("Cannot reach in-memory store — running remotely")

        base = f"spoof_{uuid.uuid4().hex[:6]}"
        successes = 0
        got_429 = False
        for i in range(7):
            email = f"{base}_{i}@example.com"
            r = requests.post(
                f"{API}/waitlist",
                json={"email": email},
                headers={"X-Forwarded-For": f"1.2.3.{i}"},  # rotating forgery
                timeout=10,
            )
            if r.status_code == 200:
                successes += 1
                type(self).inserted_emails.append(email)
            elif r.status_code == 429:
                got_429 = True
        # Even with rotating forged XFF, we must still hit the limit
        assert successes <= 5, (
            f"forged XFF appears to bypass rate limit! successes={successes}")
        assert got_429, "forged XFF rotation appears to bypass rate limit"

    def teardown_class(cls):
        try:
            import asyncio
            from server import db
            emails = cls.inserted_emails
            if emails:
                async def _cleanup():
                    await db.waitlist.delete_many({"email": {"$in": emails}})
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        raise RuntimeError()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                loop.run_until_complete(_cleanup())
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Regression: /api/health still works, x-request-id still echoed
# ---------------------------------------------------------------------------
class TestHealthRegression:
    def test_health_shape(self):
        r = requests.get(f"{API}/health", timeout=10)
        assert r.status_code == 200
        b = r.json()
        assert b["status"] == "ok"
        for k in ("mongodb", "ffmpeg", "llm_key"):
            assert k in b["checks"]
        assert "request_id" in b
        assert r.headers.get("x-request-id") == b["request_id"]

    def test_request_id_echoed(self):
        custom = f"caller_{uuid.uuid4().hex[:8]}"
        r = requests.get(f"{API}/formats",
                         headers={"x-request-id": custom}, timeout=10)
        assert r.status_code == 200
        assert r.headers.get("x-request-id") == custom
