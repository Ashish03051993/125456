"""Digest generator + scheduler + Resend delivery.

Runs every day at 08:00 Asia/Kolkata (IST). Aggregates the last 7 days from
Mongo, renders an HTML email, stores the digest doc in `digests` collection,
and (if RESEND_API_KEY is set) sends via Resend to DIGEST_TO addresses.
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("videostudio.digest")

IST = timezone(timedelta(hours=5, minutes=30))
DIGEST_HOUR_IST = 8

MOBILE_RE = re.compile(r"(mobile|android|iphone|ipad|ipod)", re.I)
TABLET_RE = re.compile(r"(ipad|tablet)", re.I)


def _iso_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _device_of(ua: str) -> str:
    if not ua:
        return "unknown"
    if TABLET_RE.search(ua):
        return "tablet"
    if MOBILE_RE.search(ua):
        return "mobile"
    return "desktop"


async def _lookup_country(ip: str) -> Optional[str]:
    if not ip or ip.startswith(("127.", "10.", "192.168.")):
        return None
    try:
        async with httpx.AsyncClient(timeout=3) as hc:
            r = await hc.get(f"http://ip-api.com/json/{ip}?fields=country")
            if r.status_code == 200:
                data = r.json()
                return data.get("country") or None
    except Exception:  # noqa: BLE001
        return None
    return None


async def build_digest(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """Return a dict with all metrics for the past 7 days + WoW deltas."""
    now = datetime.now(timezone.utc)
    since_7 = _iso_ago(7)
    since_14 = _iso_ago(14)

    # === Visitors (unique sessions in last 7 days on page_view) ===
    sess_7 = await db.analytics_events.distinct(
        "session_id",
        {"event": "page_view", "created_at": {"$gte": since_7}},
    )
    sess_14 = await db.analytics_events.distinct(
        "session_id",
        {"event": "page_view", "created_at": {"$gte": since_14, "$lt": since_7}},
    )
    visitors = len([s for s in sess_7 if s])
    visitors_prev = len([s for s in sess_14 if s])

    # === Waitlist signups ===
    signups = await db.waitlist.count_documents({"created_at": {"$gte": since_7}})
    signups_prev = await db.waitlist.count_documents(
        {"created_at": {"$gte": since_14, "$lt": since_7}}
    )
    conv_pct = round((signups / visitors) * 100, 2) if visitors else 0.0
    conv_prev = round((signups_prev / visitors_prev) * 100, 2) if visitors_prev else 0.0

    # === Traffic sources ===
    src_cur = db.analytics_events.aggregate([
        {"$match": {"event": "page_view", "created_at": {"$gte": since_7}}},
        {"$group": {"_id": {"src": "$properties.source", "sid": "$session_id"}}},
        {"$group": {"_id": "$_id.src", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
    ])
    traffic_sources = [
        {"source": d["_id"] or "direct", "sessions": d["n"]} async for d in src_cur
    ]

    # === Demo requests ===
    demo_clicks = await db.analytics_events.count_documents(
        {"event": "book_demo_click", "created_at": {"$gte": since_7}}
    )
    demo_submits = await db.analytics_events.count_documents(
        {"event": "book_demo_success", "created_at": {"$gte": since_7}}
    )
    demo_video_views = await db.analytics_events.count_documents(
        {"event": "demo_video_view", "created_at": {"$gte": since_7}}
    )

    # === A/B test performance (landing_hero) ===
    ab_expose_cur = db.analytics_events.aggregate([
        {"$match": {"event": "experiment_exposure",
                    "properties.experiment": "landing_hero",
                    "created_at": {"$gte": since_7}}},
        {"$group": {"_id": {"v": "$properties.variant", "sid": "$session_id"}}},
        {"$group": {"_id": "$_id.v", "sessions": {"$sum": 1}}},
    ])
    ab_expose = {d["_id"]: d["sessions"] async for d in ab_expose_cur}

    ab_signup_cur = db.analytics_events.aggregate([
        {"$match": {"event": {"$in": ["waitlist_submit", "waitlist_success"]},
                    "properties.variant": {"$ne": None},
                    "created_at": {"$gte": since_7}}},
        {"$group": {"_id": "$properties.variant", "n": {"$sum": 1}}},
    ])
    ab_signups = {d["_id"]: d["n"] async for d in ab_signup_cur}

    ab_rows = []
    for variant in sorted({*ab_expose.keys(), *ab_signups.keys()} | {"A", "B"}):
        sess_n = ab_expose.get(variant, 0)
        sig_n = ab_signups.get(variant, 0)
        ab_rows.append({
            "variant": variant,
            "sessions": sess_n,
            "signups": sig_n,
            "conversion_pct": round((sig_n / sess_n) * 100, 2) if sess_n else 0.0,
        })

    # === Device split (from user_agent on page_view) ===
    device_counts: Dict[str, int] = {"desktop": 0, "mobile": 0, "tablet": 0, "unknown": 0}
    seen_sessions: set[str] = set()
    async for doc in db.analytics_events.find(
        {"event": "page_view", "created_at": {"$gte": since_7}},
        {"_id": 0, "session_id": 1, "user_agent": 1},
    ):
        sid = doc.get("session_id")
        if not sid or sid in seen_sessions:
            continue
        seen_sessions.add(sid)
        device_counts[_device_of(doc.get("user_agent") or "")] += 1

    # === Geo insights (best-effort, capped to 20 unique IPs to stay under rate limit) ===
    ips: List[str] = []
    async for doc in db.analytics_events.find(
        {"event": "page_view", "created_at": {"$gte": since_7}},
        {"_id": 0, "ip": 1},
    ).limit(500):
        ip = doc.get("ip")
        if ip and ip not in ips:
            ips.append(ip)
        if len(ips) >= 20:
            break
    country_counts: Dict[str, int] = {}
    for ip in ips:
        country = await _lookup_country(ip)
        if country:
            country_counts[country] = country_counts.get(country, 0) + 1
    top_countries = sorted(
        [{"country": k, "n": v} for k, v in country_counts.items()],
        key=lambda x: x["n"], reverse=True,
    )[:5]

    def _delta(cur: float, prev: float) -> str:
        if prev == 0:
            return "+∞%" if cur > 0 else "0%"
        d = ((cur - prev) / prev) * 100
        sign = "+" if d >= 0 else ""
        return f"{sign}{d:.1f}%"

    return {
        "id": f"digest_{uuid.uuid4().hex[:12]}",
        "generated_at": now.isoformat(),
        "period_days": 7,
        "visitors": visitors,
        "visitors_prev": visitors_prev,
        "visitors_wow": _delta(visitors, visitors_prev),
        "signups": signups,
        "signups_prev": signups_prev,
        "signups_wow": _delta(signups, signups_prev),
        "conversion_pct": conv_pct,
        "conversion_prev_pct": conv_prev,
        "conversion_wow": _delta(conv_pct, conv_prev),
        "traffic_sources": traffic_sources,
        "demo_requests": {
            "book_demo_clicks": demo_clicks,
            "book_demo_submitted": demo_submits,
            "demo_video_views": demo_video_views,
        },
        "ab_test": {
            "experiment": "landing_hero",
            "rows": ab_rows,
        },
        "devices": device_counts,
        "top_countries": top_countries,
        "geo_lookups": len(ips),
    }


def render_html(d: Dict[str, Any]) -> str:
    def _rows(rows: List[Dict[str, Any]], cols: List[tuple]) -> str:
        empty_row = '<tr><td colspan="100" style="padding:16px;color:#94A3B8;text-align:center">No data</td></tr>'
        out = []
        for r in rows:
            tds = "".join(f"<td style='padding:8px 12px;border-top:1px solid #E2E8F0'>{r.get(k, '')}</td>" for _, k in cols)
            out.append(f"<tr>{tds}</tr>")
        body = "".join(out) or empty_row
        head = "".join(f"<th style='text-align:left;padding:8px 12px;background:#F1F5F9;color:#64748B;font-size:11px;text-transform:uppercase;letter-spacing:0.08em'>{lbl}</th>" for lbl, _ in cols)
        return f"<table style='width:100%;border-collapse:collapse;border:1px solid #E2E8F0;border-radius:12px;overflow:hidden'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    generated = datetime.fromisoformat(d["generated_at"]).astimezone(IST).strftime("%a, %d %b %Y · %H:%M IST")
    devices_line = " · ".join(f"{k.title()}: <b>{v}</b>" for k, v in d["devices"].items() if v)
    countries_line = " · ".join(f"{c['country']}: <b>{c['n']}</b>" for c in d["top_countries"]) or "No geo data yet"

    return f"""
<!doctype html><html><body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;background:#F8FAFC;color:#0F172A;margin:0;padding:24px">
<div style="max-width:640px;margin:0 auto;background:#FFF;border:1px solid #E2E8F0;border-radius:16px;overflow:hidden">
  <div style="background:#4F46E5;padding:24px 28px;color:#FFF">
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.14em;opacity:0.8">AI Video Studio · Daily Digest</div>
    <div style="font-size:22px;font-weight:800;margin-top:4px">Yesterday, in one glance.</div>
    <div style="font-size:12px;opacity:0.8;margin-top:4px">Generated {generated} · 7-day window</div>
  </div>
  <div style="padding:24px 28px">
    <div style="display:flex;flex-wrap:wrap;gap:10px">
      {_stat("Visitors", d["visitors"], d["visitors_wow"])}
      {_stat("Waitlist signups", d["signups"], d["signups_wow"])}
      {_stat("Conversion", f"{d['conversion_pct']}%", d["conversion_wow"])}
      {_stat("Demo requests", d["demo_requests"]["book_demo_submitted"], f"+{d['demo_requests']['book_demo_clicks']} clicks")}
    </div>

    <h3 style="margin:26px 0 10px;font-size:13px;text-transform:uppercase;letter-spacing:0.12em;color:#64748B">Traffic sources</h3>
    {_rows(d["traffic_sources"], [("Source","source"),("Sessions","sessions")])}

    <h3 style="margin:26px 0 10px;font-size:13px;text-transform:uppercase;letter-spacing:0.12em;color:#64748B">A/B test — {d['ab_test']['experiment']}</h3>
    {_rows(d['ab_test']['rows'], [("Variant","variant"),("Sessions","sessions"),("Signups","signups"),("Conv.","conversion_pct")])}

    <h3 style="margin:26px 0 10px;font-size:13px;text-transform:uppercase;letter-spacing:0.12em;color:#64748B">Device & geo</h3>
    <div style="padding:12px 14px;border:1px solid #E2E8F0;border-radius:12px;background:#F8FAFC;font-size:13px">
      {devices_line or "No device data yet"}<br/>
      <span style="color:#64748B">Top countries: {countries_line}</span>
    </div>

    <p style="margin-top:26px;color:#94A3B8;font-size:12px">
      This is an automated digest for AI Video Studio. To stop these, ping the admin.
    </p>
  </div>
</div></body></html>
""".strip()


def _stat(label: str, value: Any, wow: str) -> str:
    up = wow.startswith("+") and wow != "+0.0%"
    color = "#059669" if up else ("#DC2626" if wow.startswith("-") else "#64748B")
    return f"""
<div style="flex:1 1 45%;min-width:220px;padding:14px 16px;border:1px solid #E2E8F0;border-radius:12px;background:#FFF">
  <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.12em;color:#64748B">{label}</div>
  <div style="font-size:26px;font-weight:800;margin-top:4px;letter-spacing:-0.02em">{value}</div>
  <div style="font-size:12px;color:{color};margin-top:2px">{wow} <span style="color:#94A3B8">vs prior week</span></div>
</div>
""".strip()


async def send_via_resend(subject: str, html: str, to_list: List[str]) -> Dict[str, Any]:
    """Attempt Resend delivery. Returns {'sent': bool, 'reason': str}."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return {"sent": False, "reason": "RESEND_API_KEY not configured"}
    sender = os.environ.get("DIGEST_FROM", "AI Video Studio <onboarding@resend.dev>")
    try:
        async with httpx.AsyncClient(timeout=15) as hc:
            r = await hc.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"from": sender, "to": to_list, "subject": subject, "html": html},
            )
        if r.status_code < 300:
            return {"sent": True, "reason": r.json().get("id", "ok")}
        return {"sent": False, "reason": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:  # noqa: BLE001
        return {"sent": False, "reason": str(e)[:200]}


async def generate_and_deliver(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    data = await build_digest(db)
    html = render_html(data)
    subject = (
        f"AI Video Studio · {data['signups']} signups · "
        f"{data['visitors']} visitors · {data['conversion_pct']}% conv"
    )
    recipients = [r.strip() for r in os.environ.get(
        "DIGEST_TO", "ashish.jha93@gmail.com"
    ).split(",") if r.strip()]
    delivery = await send_via_resend(subject, html, recipients)
    doc = {
        **data,
        "subject": subject,
        "recipients": recipients,
        "html": html,
        "delivery": delivery,
    }
    await db.digests.insert_one(doc)
    logger.info("Digest generated id=%s sent=%s reason=%s",
                data["id"], delivery["sent"], delivery["reason"])
    return doc
