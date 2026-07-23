"""AI Video Studio - FastAPI backend.

Endpoints (all under /api):
  /auth/session, /auth/me, /auth/logout
  /projects (list, create, get, delete)
  /projects/{id}/generate  (kicks off pipeline)
  /projects/{id}/status
  /admin/users, /admin/stats
  /media/{kind}/{file}     (serves generated files)
"""
import asyncio
import base64
import json
import logging
import os
import re
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import httpx
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAITextToSpeech
from fastapi import (APIRouter, BackgroundTasks, Cookie, Depends, FastAPI,
                     Header, HTTPException, Request)
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", ROOT_DIR / "storage"))
for sub in ("images", "audio", "videos"):
    (STORAGE_DIR / sub).mkdir(parents=True, exist_ok=True)

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("videostudio")

app = FastAPI(title="AI Video Studio")
api = APIRouter(prefix="/api")


# --------------------------- Request ID + Structured Logs Middleware ---------------------------
@app.middleware("http")
async def request_context(request, call_next):
    """Attach a request_id to every request for log correlation + emit structured access log."""
    rid = request.headers.get("x-request-id") or f"rq_{uuid.uuid4().hex[:12]}"
    request.state.request_id = rid
    start = datetime.now(timezone.utc)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled_exception request_id=%s path=%s", rid, request.url.path)
        raise
    dur_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    response.headers["x-request-id"] = rid
    # Skip noisy paths in access log
    if not request.url.path.startswith("/api/media") and request.url.path != "/api/health":
        logger.info('access request_id=%s method=%s path=%s status=%d duration_ms=%d',
                    rid, request.method, request.url.path, response.status_code, dur_ms)
    return response


# --------------------------- Rate Limiting (in-memory, per-IP) ---------------------------
_rate_limit_store: dict = {}   # {(ip, bucket): [(timestamp, ...)]}

def _client_ip(request) -> str:
    """Extract real client IP even when behind a reverse proxy (K8s ingress, CloudFront, Cloudflare).

    Trusts the FIRST entry in X-Forwarded-For when the direct peer is inside a
    known-proxy CIDR. Falls back to X-Real-IP, then request.client.host, then 'unknown'.
    Safe against spoofing because we only trust the header when the L4 peer is one
    of our own ingress pods.
    """
    import ipaddress
    peer = request.client.host if request.client else None
    trusted_cidrs = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8"]
    peer_trusted = False
    if peer:
        try:
            ip_obj = ipaddress.ip_address(peer)
            peer_trusted = any(ip_obj in ipaddress.ip_network(c) for c in trusted_cidrs)
        except ValueError:
            peer_trusted = False
    if peer_trusted:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
        xreal = request.headers.get("x-real-ip", "").strip()
        if xreal:
            return xreal
    return peer or "unknown"


def _rate_limit_check(request, bucket: str, limit: int, window_seconds: int):
    """Sliding-window per-IP rate limit. Raises 429 if exceeded.

    In-memory only — resets on backend restart. Fine for public endpoints
    at current traffic scale; graduate to Redis if we need distributed limits.
    """
    ip = _client_ip(request)
    key = (ip, bucket)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window_seconds)
    hits = [t for t in _rate_limit_store.get(key, []) if t > cutoff]
    if len(hits) >= limit:
        raise HTTPException(429, f"Rate limit exceeded. Try again in {window_seconds}s.")
    hits.append(now)
    _rate_limit_store[key] = hits
    # Periodic garbage collection: if the store grows past 5k keys, prune stale ones
    if len(_rate_limit_store) > 5000:
        for k in list(_rate_limit_store):
            _rate_limit_store[k] = [t for t in _rate_limit_store[k] if t > cutoff]
            if not _rate_limit_store[k]:
                del _rate_limit_store[k]


# --------------------------- Health Check ---------------------------
@api.get("/health")
async def health(request: Request):
    """Liveness + readiness probe. Returns 200 if all critical deps are reachable, 503 otherwise.

    Public endpoint — no auth. Safe to expose to load balancers and uptime monitors.
    """
    import shutil
    status = {"status": "ok", "service": "ai-video-studio",
              "version": "phase-1", "checks": {}}
    # DB check
    try:
        await client.admin.command("ping")
        status["checks"]["mongodb"] = "ok"
    except Exception as e:
        status["status"] = "degraded"
        status["checks"]["mongodb"] = f"error: {str(e)[:80]}"
    # FFmpeg check (needed for video pipeline)
    status["checks"]["ffmpeg"] = "ok" if shutil.which("ffmpeg") else "missing"
    if status["checks"]["ffmpeg"] == "missing":
        status["status"] = "degraded"
    # LLM key configured?
    status["checks"]["llm_key"] = "ok" if os.environ.get("EMERGENT_LLM_KEY") else "missing"
    if status["checks"]["llm_key"] == "missing":
        status["status"] = "degraded"
    status["request_id"] = request.state.request_id
    code = 200 if status["status"] == "ok" else 503
    return JSONResponse(content=status, status_code=code)


# --------------------------- Models ---------------------------
class Scene(BaseModel):
    idx: int
    heading: str
    narration: str
    subtitle: str
    image_prompt: str
    video_prompt: str
    image_url: Optional[str] = None
    duration: float = 5.0


class Project(BaseModel):
    id: str = Field(default_factory=lambda: f"proj_{uuid.uuid4().hex[:12]}")
    user_id: str
    topic: str
    duration_sec: int = 30                # New: precise duration in seconds
    duration_min: int = 1                 # Legacy: kept for backwards compat
    language: str = "English"
    style: str = "Educational"
    voice: str = "female"
    dialogue_mode: bool = False           # If True, script uses named characters + multi-voice
    status: str = "draft"  # draft | generating | ready | error
    progress: int = 0
    stage: str = "queued"
    title: Optional[str] = None
    hook: Optional[str] = None
    script: Optional[str] = None
    scenes: List[Scene] = []
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    credit_cost: int = 3                  # Credits charged when generation started
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreateProjectIn(BaseModel):
    topic: str
    duration_sec: Optional[int] = None    # Preferred; if None, falls back to duration_min
    duration_min: Optional[int] = None    # Legacy fallback
    language: str = "English"
    style: str = "Educational"
    voice: str = "female"
    dialogue_mode: bool = False           # NEW: character dialogue toggle


# --------------------------- Auth helpers ---------------------------
async def current_user(request: Request,
                       session_token: Optional[str] = Cookie(default=None),
                       authorization: Optional[str] = Header(default=None)):
    token = session_token
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(401, "Not authenticated")
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        raise HTTPException(401, "Invalid session")
    exp = sess.get("expires_at")
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp and exp < datetime.now(timezone.utc):
        raise HTTPException(401, "Session expired")
    user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user


async def require_admin(user=Depends(current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    return user


# --------------------------- Auth routes ---------------------------
class SessionIn(BaseModel):
    session_id: str


@api.post("/auth/session")
async def auth_session(payload: SessionIn, response: Response):
    async with httpx.AsyncClient(timeout=15) as hc:
        r = await hc.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": payload.session_id})
    if r.status_code != 200:
        raise HTTPException(401, "Invalid session_id")
    data = r.json()
    email = data["email"]
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one({"user_id": user_id},
                                  {"$set": {"name": data.get("name"),
                                            "picture": data.get("picture")}})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        # First admin bootstrap
        role = "admin" if email == "admin@videostudio.ai" else "user"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": data.get("name"),
            "picture": data.get("picture"),
            "role": role,
            "plan": "free",
            "credits": 3,   # Free plan: 1 × 30-sec video / month (as designed)
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_refill_at": datetime.now(timezone.utc).isoformat(),
        })
    session_token = data["session_token"]
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    response.set_cookie("session_token", session_token, max_age=7 * 24 * 3600,
                        httponly=True, secure=True, samesite="none", path="/")
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return {"user": user}


@api.get("/auth/me")
async def auth_me(user=Depends(current_user)):
    return await apply_free_refill(user)


@api.post("/auth/logout")
async def auth_logout(response: Response, session_token: Optional[str] = Cookie(default=None)):
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


# --------------------------- Project CRUD ---------------------------
@api.get("/projects")
async def list_projects(user=Depends(current_user)):
    cur = db.projects.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1)
    return await cur.to_list(200)


# --------------------------- Duration Registry (single source of truth) ---------------------------
DURATION_TIERS: list = [
    # (duration_sec, credit_cost, num_scenes, label)
    (30,   3,  3,  "30 sec"),
    (45,   4,  4,  "45 sec"),
    (60,   5,  5,  "60 sec"),
    (90,   7,  7,  "90 sec"),
    (120, 10,  9,  "2 min"),
    (180, 15, 12,  "3 min"),
    (300, 25, 16,  "5 min"),
    (600, 50, 22,  "10 min"),
]
DURATION_BY_SEC = {t[0]: t for t in DURATION_TIERS}
DEFAULT_DURATION_SEC = 30

def resolve_duration_sec(payload: "CreateProjectIn") -> int:
    """Coerce input into a supported duration tier. Prefers duration_sec; falls
    back to legacy duration_min. Snaps to the nearest supported tier."""
    if payload.duration_sec and payload.duration_sec in DURATION_BY_SEC:
        return payload.duration_sec
    if payload.duration_min:
        return {1: 30, 3: 180, 5: 300, 10: 600}.get(payload.duration_min, DEFAULT_DURATION_SEC)
    if payload.duration_sec:
        supported = [t[0] for t in DURATION_TIERS]
        return min(supported, key=lambda s: abs(s - payload.duration_sec))
    return DEFAULT_DURATION_SEC

def credit_cost_for_sec(sec: int) -> int:
    return DURATION_BY_SEC.get(sec, DURATION_BY_SEC[DEFAULT_DURATION_SEC])[1]

def scenes_for_sec(sec: int) -> int:
    return DURATION_BY_SEC.get(sec, DURATION_BY_SEC[DEFAULT_DURATION_SEC])[2]


# --------------------------- Free-tier credit refill ---------------------------
FREE_MONTHLY_CREDITS = 3   # Enough for exactly one 30-sec video

async def apply_free_refill(user: dict) -> dict:
    """If the user's `last_refill_at` is in a previous calendar month (or missing),
    top them up to at least FREE_MONTHLY_CREDITS. Idempotent: only fires once per
    calendar month per user. Returns the (possibly refilled) user doc.
    """
    if user.get("plan") and user["plan"] != "free":
        return user  # Paid users don't auto-refill; they buy credit packs.
    now = datetime.now(timezone.utc)
    last = user.get("last_refill_at")
    if isinstance(last, str):
        try: last = datetime.fromisoformat(last)
        except Exception: last = None
    if last and last.tzinfo is None: last = last.replace(tzinfo=timezone.utc)
    same_month = last and last.year == now.year and last.month == now.month
    if same_month:
        return user
    # New month → top up to at least the free grant
    current = int(user.get("credits", 0) or 0)
    new_credits = max(current, FREE_MONTHLY_CREDITS)
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"credits": new_credits, "last_refill_at": now.isoformat(),
                  "plan": user.get("plan") or "free"}},
    )
    user["credits"] = new_credits
    user["last_refill_at"] = now.isoformat()
    return user


@api.post("/projects")
async def create_project(payload: CreateProjectIn, user=Depends(current_user)):
    user = await apply_free_refill(user)
    sec = resolve_duration_sec(payload)
    cost = credit_cost_for_sec(sec)
    if int(user.get("credits", 0) or 0) < cost:
        raise HTTPException(402, f"Need {cost} credits for a {sec}-sec video, "
                                 f"you have {user.get('credits', 0)}. Top up to continue.")
    project = Project(
        user_id=user["user_id"],
        topic=payload.topic,
        duration_sec=sec,
        duration_min=max(1, sec // 60),      # legacy field, best-effort mapping
        language=payload.language,
        style=payload.style,
        voice=payload.voice,
        dialogue_mode=payload.dialogue_mode,
        credit_cost=cost,
    )
    doc = project.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.projects.insert_one(doc)
    return await db.projects.find_one({"id": project.id}, {"_id": 0})


@api.get("/projects/{pid}")
async def get_project(pid: str, user=Depends(current_user)):
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Not found")
    return p


@api.delete("/projects/{pid}")
async def delete_project(pid: str, user=Depends(current_user)):
    r = await db.projects.delete_one({"id": pid, "user_id": user["user_id"]})
    return {"deleted": r.deleted_count}


@api.post("/projects/{pid}/generate")
async def start_generate(pid: str, bg: BackgroundTasks, user=Depends(current_user)):
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Not found")
    if p["status"] == "generating":
        return {"ok": True, "message": "Already running"}
    await db.projects.update_one({"id": pid},
                                 {"$set": {"status": "generating", "progress": 5,
                                           "stage": "writing script", "error": None}})
    # Decrement credits based on project's stored cost (set at creation time)
    cost = int(p.get("credit_cost", 1) or 1)
    await db.users.update_one({"user_id": user["user_id"]}, {"$inc": {"credits": -cost}})
    bg.add_task(run_pipeline, pid)
    return {"ok": True}


# --------------------------- Admin ---------------------------
@api.get("/admin/users")
async def admin_users(_admin=Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0}).to_list(500)
    return users


@api.post("/admin/users/{user_id}/credits")
async def admin_set_credits(user_id: str, credits: int,
                            _admin=Depends(require_admin)):
    r = await db.users.update_one({"user_id": user_id}, {"$set": {"credits": credits}})
    return {"updated": r.modified_count}


# --------------------------- Waitlist ---------------------------
class WaitlistIn(BaseModel):
    email: str
    name: Optional[str] = None
    use_case: Optional[str] = None
    plan_interest: Optional[str] = None  # free | pro | business | enterprise
    referrer: Optional[str] = None
    # Attribution (populated from client's captureAttribution() cache)
    source: Optional[str] = None
    medium: Optional[str] = None
    campaign: Optional[str] = None
    variant: Optional[str] = None  # A/B variant at time of signup


@api.post("/waitlist")
async def waitlist_join(payload: WaitlistIn, request: Request):
    # Rate limit: 5 signups per IP per hour (protects against spam bots)
    _rate_limit_check(request, "waitlist", limit=5, window_seconds=3600)
    email = payload.email.strip().lower()
    if "@" not in email or "." not in email:
        raise HTTPException(400, "Invalid email")
    existing = await db.waitlist.find_one({"email": email})
    if existing:
        return {"ok": True, "already_joined": True, "position": existing.get("position")}
    count = await db.waitlist.count_documents({})
    doc = {
        "id": f"wl_{uuid.uuid4().hex[:12]}",
        "email": email,
        "name": payload.name,
        "use_case": payload.use_case,
        "plan_interest": payload.plan_interest or "free",
        "referrer": payload.referrer,
        "source": payload.source or "direct",
        "medium": payload.medium,
        "campaign": payload.campaign,
        "variant": payload.variant,
        "position": count + 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent", "")[:200],
    }
    await db.waitlist.insert_one(doc)
    await db.analytics_events.insert_one({
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "event": "waitlist_signup",
        "properties": {
            "email": email,
            "plan_interest": doc["plan_interest"],
            "use_case": payload.use_case,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True, "already_joined": False, "position": doc["position"]}


@api.get("/admin/waitlist")
async def admin_waitlist(_admin=Depends(require_admin),
                         source: Optional[str] = None,
                         plan: Optional[str] = None,
                         variant: Optional[str] = None,
                         q: Optional[str] = None):
    match: dict = {}
    if source == "direct":
        match["$or"] = [{"source": "direct"}, {"source": None}, {"source": {"$exists": False}}]
    elif source:
        match["source"] = source
    if plan:
        match["plan_interest"] = plan
    if variant == "unassigned":
        v_clause = [{"variant": None}, {"variant": {"$exists": False}}]
        if "$or" in match:
            match = {"$and": [{"$or": match.pop("$or")}, {"$or": v_clause}]}
        else:
            match["$or"] = v_clause
    elif variant:
        match["variant"] = variant
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        q_or = [{"email": rx}, {"name": rx}, {"use_case": rx}]
        if "$or" in match:
            match = {"$and": [{"$or": match.pop("$or")}, {"$or": q_or}], **match}
        elif "$and" in match:
            match["$and"].append({"$or": q_or})
        else:
            match["$or"] = q_or
    rows = await db.waitlist.find(match, {"_id": 0}).sort("position", 1).to_list(2000)

    # Unfiltered facets — coalesce null/missing into a fallback bucket
    by_plan_cur = db.waitlist.aggregate([
        {"$group": {"_id": {"$ifNull": ["$plan_interest", "unspecified"]}, "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
    ])
    by_plan = [{"plan": d["_id"], "n": d["n"]} async for d in by_plan_cur]
    by_source_cur = db.waitlist.aggregate([
        {"$group": {"_id": {"$ifNull": ["$source", "direct"]}, "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
    ])
    by_source = [{"source": d["_id"], "n": d["n"]} async for d in by_source_cur]
    by_variant_cur = db.waitlist.aggregate([
        {"$group": {"_id": {"$ifNull": ["$variant", "unassigned"]}, "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
    ])
    by_variant = [{"variant": d["_id"], "n": d["n"]} async for d in by_variant_cur]
    total = await db.waitlist.count_documents({})
    return {
        "count": len(rows),
        "total": total,
        "by_plan_interest": {r["plan"]: r["n"] for r in by_plan},
        "by_plan": by_plan,
        "by_source": by_source,
        "by_variant": by_variant,
        "filters": {"source": source, "plan": plan, "variant": variant, "q": q},
        "entries": rows,
    }


@api.get("/admin/waitlist.csv")
async def admin_waitlist_csv(_admin=Depends(require_admin),
                             source: Optional[str] = None,
                             plan: Optional[str] = None,
                             variant: Optional[str] = None,
                             q: Optional[str] = None):
    match: dict = {}
    if source == "direct":
        match["$or"] = [{"source": "direct"}, {"source": None}, {"source": {"$exists": False}}]
    elif source:
        match["source"] = source
    if plan: match["plan_interest"] = plan
    if variant == "unassigned":
        v_clause = [{"variant": None}, {"variant": {"$exists": False}}]
        if "$or" in match:
            match = {"$and": [{"$or": match.pop("$or")}, {"$or": v_clause}]}
        else:
            match["$or"] = v_clause
    elif variant:
        match["variant"] = variant
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        q_or = [{"email": rx}, {"name": rx}, {"use_case": rx}]
        if "$or" in match:
            match = {"$and": [{"$or": match.pop("$or")}, {"$or": q_or}], **match}
        elif "$and" in match:
            match["$and"].append({"$or": q_or})
        else:
            match["$or"] = q_or
    rows = await db.waitlist.find(match, {"_id": 0}).sort("position", 1).to_list(5000)
    import csv, io
    buf = io.StringIO()
    cols = ["position", "email", "name", "plan_interest", "source", "medium",
            "campaign", "variant", "use_case", "referrer", "created_at"]
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        line = []
        for c in cols:
            v = r.get(c)
            if c == "source" and not v:
                v = "direct"
            line.append(v if v is not None else "")
        w.writerow(line)
    fname = "waitlist"
    if source: fname += f"-{source}"
    if plan: fname += f"-{plan}"
    if variant: fname += f"-v{variant}"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}.csv"'},
    )


@api.get("/durations")
async def list_durations():
    """Public list of supported video durations + credit costs (source of truth for FE picker)."""
    return [
        {"sec": s, "credits": c, "scenes": n, "label": lbl}
        for (s, c, n, lbl) in DURATION_TIERS
    ]


@api.get("/formats")
async def formats_list():
    """Public list of available video output formats."""
    from formats import list_formats
    return list_formats()


@api.get("/admin/sanity")
async def admin_sanity(_admin=Depends(require_admin)):
    """Analytics sanity check — flags data-quality issues before scaling acquisition.

    Returns:
      - orphan_signups: waitlist rows with no matching page_view session_id in analytics_events
      - unattributed_sessions: unique page_view session_ids where properties.source is missing/null
      - duplicate_emails: waitlist emails appearing more than once (case-insensitive)
      - totals: {waitlist, sessions} for context
    """
    # 1) Duplicate emails (case-insensitive)
    dup_cur = db.waitlist.aggregate([
        {"$group": {"_id": {"$toLower": "$email"}, "n": {"$sum": 1},
                    "positions": {"$push": "$position"}}},
        {"$match": {"n": {"$gt": 1}}},
        {"$sort": {"n": -1}},
        {"$limit": 50},
    ])
    duplicate_emails = [
        {"email": d["_id"], "count": d["n"], "positions": sorted(d.get("positions", []))[:10]}
        async for d in dup_cur
    ]

    # 2) Unique page_view session_ids (all + unattributed)
    all_sess_cur = db.analytics_events.aggregate([
        {"$match": {"event": "page_view"}},
        {"$group": {"_id": "$session_id"}},
    ])
    all_sids = {d["_id"] async for d in all_sess_cur if d["_id"]}

    unattr_cur = db.analytics_events.aggregate([
        {"$match": {"event": "page_view",
                    "$or": [{"properties.source": {"$in": [None, ""]}},
                            {"properties.source": {"$exists": False}}]}},
        {"$group": {"_id": "$session_id"}},
    ])
    unattr_sids = {d["_id"] async for d in unattr_cur if d["_id"]}

    # 3) Orphan signups — waitlist emails whose session_id (if captured) has no page_view,
    #    OR waitlist rows with no session_id linkage at all.
    # We look up analytics_events matching properties.email == waitlist.email (waitlist_submit event).
    submit_cur = db.analytics_events.aggregate([
        {"$match": {"event": {"$in": ["waitlist_submit", "waitlist_success"]}}},
        {"$group": {"_id": {"$toLower": {"$ifNull": ["$properties.email", ""]}},
                    "sids": {"$addToSet": "$session_id"}}},
    ])
    submit_sids_by_email: dict = {}
    async for d in submit_cur:
        submit_sids_by_email[d["_id"]] = set(s for s in d.get("sids", []) if s)

    wl_cur = db.waitlist.find({}, {"_id": 0, "id": 1, "email": 1, "position": 1,
                                    "created_at": 1, "source": 1})
    orphans = []
    total_wl = 0
    async for w in wl_cur:
        total_wl += 1
        em = (w.get("email") or "").lower()
        sids = submit_sids_by_email.get(em, set())
        has_pv = bool(sids & all_sids)
        if not has_pv:
            orphans.append({
                "email": w.get("email"),
                "position": w.get("position"),
                "source": w.get("source") or "direct",
                "created_at": w.get("created_at"),
                "reason": "no matching page_view session" if sids else "no analytics session captured",
            })

    # Cap the returned list; frontend shows count + first N
    orphans_sorted = sorted(orphans, key=lambda o: o.get("position") or 10**9)

    return {
        "orphan_signups": {
            "count": len(orphans_sorted),
            "sample": orphans_sorted[:25],
        },
        "unattributed_sessions": {
            "count": len(unattr_sids),
            "total_sessions": len(all_sids),
            "pct": round((len(unattr_sids) / len(all_sids)) * 100, 2) if all_sids else 0.0,
        },
        "duplicate_emails": {
            "count": len(duplicate_emails),
            "sample": duplicate_emails,
        },
        "totals": {
            "waitlist": total_wl,
            "sessions": len(all_sids),
        },
    }


@api.get("/admin/sanity/untagged")
async def admin_sanity_untagged(_admin=Depends(require_admin), limit: int = 100):
    """Drilldown for untagged sessions — sessions with no utm_source but with captured
    referrer/landing-path/user-agent. Helps diagnose where dark traffic is coming from.

    Returns:
      - sessions: list of {session_id, first_seen, last_seen, page_views, referrer, referrer_host, landing_path, user_agent}
      - top_referrer_hosts: rollup [{host, n}] sorted desc
      - top_landing_paths: rollup [{path, n}] sorted desc
      - total: total unique untagged sessions
    """
    from urllib.parse import urlparse
    limit = max(1, min(limit, 500))

    # Fetch all page_view events with no source, group by session_id
    cur = db.analytics_events.aggregate([
        {"$match": {
            "event": "page_view",
            "$or": [
                {"properties.source": {"$in": [None, ""]}},
                {"properties.source": {"$exists": False}},
            ],
        }},
        {"$sort": {"created_at": 1}},
        {"$group": {
            "_id": "$session_id",
            "first_seen": {"$first": "$created_at"},
            "last_seen": {"$last": "$created_at"},
            "page_views": {"$sum": 1},
            "referrer": {"$first": "$referrer"},
            "path": {"$first": "$path"},
            "user_agent": {"$first": "$user_agent"},
        }},
        {"$sort": {"last_seen": -1}},
    ])
    all_sessions = [d async for d in cur if d.get("_id")]
    total = len(all_sessions)

    def _host(url: str) -> str:
        if not url:
            return "(direct/none)"
        try:
            h = urlparse(url).netloc or url
            return h.lower() or "(direct/none)"
        except Exception:
            return "(unknown)"

    # Rollups over ALL untagged (not just the paginated slice)
    host_counts: dict = {}
    path_counts: dict = {}
    for s in all_sessions:
        h = _host(s.get("referrer") or "")
        host_counts[h] = host_counts.get(h, 0) + 1
        p = s.get("path") or "(unknown)"
        path_counts[p] = path_counts.get(p, 0) + 1

    top_hosts = sorted(({"host": k, "n": v} for k, v in host_counts.items()),
                        key=lambda x: -x["n"])[:15]
    top_paths = sorted(({"path": k, "n": v} for k, v in path_counts.items()),
                        key=lambda x: -x["n"])[:15]

    sessions_out = []
    for s in all_sessions[:limit]:
        ua = (s.get("user_agent") or "")[:120]
        sessions_out.append({
            "session_id": s["_id"],
            "first_seen": s.get("first_seen"),
            "last_seen": s.get("last_seen"),
            "page_views": s.get("page_views", 0),
            "referrer": s.get("referrer") or "",
            "referrer_host": _host(s.get("referrer") or ""),
            "landing_path": s.get("path") or "",
            "user_agent": ua,
        })

    return {
        "total": total,
        "returned": len(sessions_out),
        "sessions": sessions_out,
        "top_referrer_hosts": top_hosts,
        "top_landing_paths": top_paths,
    }


@api.get("/admin/attribution-matrix")
async def admin_attribution_matrix(_admin=Depends(require_admin)):
    """Signup Attribution Matrix: sources × variants → signups & conversion.

    Rows: unique source values from waitlist.
    Cols: unique variant values (plus 'unassigned' for null/missing).
    Cell: {signups, sessions, conversion_pct}. Also sends `totals` per row/col.
    """
    # Load facets first so the matrix has stable row/col order
    src_cur = db.waitlist.aggregate([
        {"$group": {"_id": {"$ifNull": ["$source", "direct"]}, "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
    ])
    sources = [d["_id"] async for d in src_cur]

    var_cur = db.waitlist.aggregate([
        {"$group": {"_id": {"$ifNull": ["$variant", "unassigned"]}, "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
    ])
    variants = [d["_id"] async for d in var_cur]

    # Signup counts per (source, variant)
    sig_cur = db.waitlist.aggregate([
        {"$group": {
            "_id": {
                "s": {"$ifNull": ["$source", "direct"]},
                "v": {"$ifNull": ["$variant", "unassigned"]},
            },
            "n": {"$sum": 1},
        }}
    ])
    signups: dict = {}
    async for d in sig_cur:
        signups[(d["_id"]["s"], d["_id"]["v"])] = d["n"]

    # Session (page_view) counts per (source, variant) — unique session_id
    sess_cur = db.analytics_events.aggregate([
        {"$match": {"event": "page_view"}},
        {"$group": {"_id": {
            "s": {"$ifNull": ["$properties.source", "direct"]},
            "v": {"$ifNull": ["$properties.variant", "unassigned"]},
            "sid": "$session_id",
        }}},
        {"$group": {"_id": {"s": "$_id.s", "v": "$_id.v"}, "n": {"$sum": 1}}},
    ])
    sessions: dict = {}
    async for d in sess_cur:
        sessions[(d["_id"]["s"], d["_id"]["v"])] = d["n"]

    rows_out = []
    col_totals = {v: {"sessions": 0, "signups": 0} for v in variants}
    grand = {"sessions": 0, "signups": 0}
    for s in sources:
        cells = []
        row_sess = 0
        row_sig = 0
        for v in variants:
            sess_n = sessions.get((s, v), 0)
            sig_n = signups.get((s, v), 0)
            cells.append({
                "variant": v,
                "sessions": sess_n,
                "signups": sig_n,
                "conversion_pct": round((sig_n / sess_n) * 100, 2) if sess_n else 0.0,
            })
            row_sess += sess_n
            row_sig += sig_n
            col_totals[v]["sessions"] += sess_n
            col_totals[v]["signups"] += sig_n
        rows_out.append({
            "source": s,
            "cells": cells,
            "totals": {
                "sessions": row_sess,
                "signups": row_sig,
                "conversion_pct": round((row_sig / row_sess) * 100, 2) if row_sess else 0.0,
            },
        })
        grand["sessions"] += row_sess
        grand["signups"] += row_sig

    return {
        "sources": sources,
        "variants": variants,
        "rows": rows_out,
        "col_totals": [
            {"variant": v,
             "sessions": col_totals[v]["sessions"],
             "signups": col_totals[v]["signups"],
             "conversion_pct": round((col_totals[v]["signups"] / col_totals[v]["sessions"]) * 100, 2)
                                 if col_totals[v]["sessions"] else 0.0}
            for v in variants
        ],
        "grand": {
            **grand,
            "conversion_pct": round((grand["signups"] / grand["sessions"]) * 100, 2)
                              if grand["sessions"] else 0.0,
        },
    }


@api.get("/admin/attribution-matrix.csv")
async def admin_attribution_matrix_csv(_admin=Depends(require_admin)):
    """CSV export of the Source × Variant attribution matrix.

    Columns: source, variant, sessions, signups, conversion_pct.
    Includes one row per (source, variant) cell + a `__total__` variant per
    source (row totals) + a `__total__` source per variant (col totals) +
    a final grand total row. Ready to open in Sheets/Excel.
    """
    data = await admin_attribution_matrix(_admin=_admin)
    import csv, io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["source", "variant", "sessions", "signups", "conversion_pct"])
    for r in data["rows"]:
        for c in r["cells"]:
            w.writerow([r["source"], c["variant"], c["sessions"],
                        c["signups"], c["conversion_pct"]])
        w.writerow([r["source"], "__total__", r["totals"]["sessions"],
                    r["totals"]["signups"], r["totals"]["conversion_pct"]])
    for c in data["col_totals"]:
        w.writerow(["__total__", c["variant"], c["sessions"],
                    c["signups"], c["conversion_pct"]])
    w.writerow(["__total__", "__total__", data["grand"]["sessions"],
                data["grand"]["signups"], data["grand"]["conversion_pct"]])

    from datetime import date
    fname = f"attribution-matrix-{date.today().isoformat()}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# --------------------------- Analytics ---------------------------
class AnalyticsEvent(BaseModel):
    event: str
    properties: Optional[dict] = None
    session_id: Optional[str] = None
    path: Optional[str] = None


@api.post("/analytics/track")
async def track(payload: AnalyticsEvent, request: Request):
    # Rate limit: 300 events per IP per minute (generous — a normal session fires ~5-20 events)
    _rate_limit_check(request, "analytics", limit=300, window_seconds=60)
    if not payload.event or len(payload.event) > 60:
        raise HTTPException(400, "Invalid event")
    doc = {
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "event": payload.event,
        "properties": payload.properties or {},
        "session_id": payload.session_id,
        "path": payload.path,
        "referrer": request.headers.get("referer", ""),
        "user_agent": request.headers.get("user-agent", "")[:200],
        "ip": request.client.host if request.client else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.analytics_events.insert_one(doc)
    return {"ok": True}


@api.get("/admin/analytics")
async def admin_analytics(_admin=Depends(require_admin), days: int = 14):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    total = await db.analytics_events.count_documents({"created_at": {"$gte": since}})
    by_event_cur = db.analytics_events.aggregate([
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {"_id": "$event", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
    ])
    by_event = [{"event": d["_id"], "count": d["n"]} async for d in by_event_cur]

    by_day_cur = db.analytics_events.aggregate([
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {
            "_id": {"day": {"$substr": ["$created_at", 0, 10]}, "event": "$event"},
            "n": {"$sum": 1}
        }},
        {"$sort": {"_id.day": 1}},
    ])
    by_day = [{"day": d["_id"]["day"], "event": d["_id"]["event"], "count": d["n"]}
              async for d in by_day_cur]

    # Unique sessions
    sess = await db.analytics_events.distinct("session_id",
                                              {"created_at": {"$gte": since}})
    unique_sessions = len([s for s in sess if s])
    waitlist_total = await db.waitlist.count_documents({})

    # Conversion by source: sessions per source vs waitlist_signups per source
    src_page_cur = db.analytics_events.aggregate([
        {"$match": {"created_at": {"$gte": since}, "event": "page_view"}},
        {"$group": {"_id": {"src": "$properties.source", "sid": "$session_id"}}},
        {"$group": {"_id": "$_id.src", "sessions": {"$sum": 1}}},
    ])
    per_source = {}
    async for d in src_page_cur:
        per_source[d["_id"] or "direct"] = {"sessions": d["sessions"], "signups": 0, "demo_views": 0}

    src_signup_cur = db.analytics_events.aggregate([
        {"$match": {"created_at": {"$gte": since},
                    "event": {"$in": ["waitlist_signup", "waitlist_success"]}}},
        {"$group": {"_id": "$properties.source", "n": {"$sum": 1}}},
    ])
    async for d in src_signup_cur:
        key = d["_id"] or "direct"
        per_source.setdefault(key, {"sessions": 0, "signups": 0, "demo_views": 0})
        per_source[key]["signups"] += d["n"]

    src_demo_cur = db.analytics_events.aggregate([
        {"$match": {"created_at": {"$gte": since}, "event": "demo_video_view"}},
        {"$group": {"_id": "$properties.source", "n": {"$sum": 1}}},
    ])
    async for d in src_demo_cur:
        key = d["_id"] or "direct"
        per_source.setdefault(key, {"sessions": 0, "signups": 0, "demo_views": 0})
        per_source[key]["demo_views"] = d["n"]

    conv_by_source = []
    for src, v in per_source.items():
        sess_n = v.get("sessions", 0) or 0
        sign_n = v.get("signups", 0) or 0
        demo_n = v.get("demo_views", 0) or 0
        conv_by_source.append({
            "source": src,
            "sessions": sess_n,
            "signups": sign_n,
            "demo_views": demo_n,
            "conversion_pct": round((sign_n / sess_n) * 100, 2) if sess_n else 0.0,
        })
    conv_by_source.sort(key=lambda r: r["sessions"], reverse=True)

    return {
        "days": days,
        "total_events": total,
        "unique_sessions": unique_sessions,
        "waitlist_total": waitlist_total,
        "by_event": by_event,
        "by_day": by_day,
        "conversion_by_source": conv_by_source,
    }


@api.get("/admin/stats")
async def admin_stats(_admin=Depends(require_admin)):
    total_users = await db.users.count_documents({})
    total_projects = await db.projects.count_documents({})
    ready = await db.projects.count_documents({"status": "ready"})
    waitlist_total = await db.waitlist.count_documents({})
    since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    signups_24h = await db.waitlist.count_documents({"created_at": {"$gte": since_24h}})
    events_24h = await db.analytics_events.count_documents({"created_at": {"$gte": since_24h}})
    demo_views = await db.analytics_events.count_documents({"event": "demo_video_view"})
    demo_impressions = await db.analytics_events.count_documents({"event": "demo_video_impression"})
    book_demo_clicks = await db.analytics_events.count_documents({"event": "book_demo_click"})
    waitlist_clicks = await db.analytics_events.count_documents({"event": "waitlist_button_click"})
    plans_cur = db.waitlist.aggregate([{"$group": {"_id": "$plan_interest", "n": {"$sum": 1}}}])
    plans = {d["_id"] or "unspecified": d["n"] async for d in plans_cur}
    return {
        "total_users": total_users,
        "total_projects": total_projects,
        "videos_ready": ready,
        "waitlist_total": waitlist_total,
        "waitlist_24h": signups_24h,
        "events_24h": events_24h,
        "demo_views": demo_views,
        "demo_impressions": demo_impressions,
        "book_demo_clicks": book_demo_clicks,
        "waitlist_clicks": waitlist_clicks,
        "waitlist_by_plan": plans,
    }


# --------------------------- Media static ---------------------------
# Mount under /api so Kubernetes ingress routes it to the backend
app.mount("/api/media", StaticFiles(directory=str(STORAGE_DIR)), name="media")


# --------------------------- Pipeline ---------------------------
STYLE_GUIDE = {
    "Business": "Corporate, polished, confident and analytical.",
    "Documentary": "Neutral, informative, David Attenborough style.",
    "Educational": "Clear, friendly, structured, ELI5 tone.",
    "Cinematic": "Dramatic, evocative, poetic imagery, slow pacing.",
    "Storytelling": "Warm narrative, character-driven, engaging arc.",
}
VOICE_MAP = {"male": "onyx", "female": "nova"}


def scenes_for_duration(minutes: int) -> int:
    return {1: 5, 3: 10, 5: 14, 10: 20}.get(minutes, 6)


async def _generate_script(project: dict) -> dict:
    # Prefer new duration_sec, fall back to legacy duration_min-based count
    sec = project.get("duration_sec")
    n_scenes = scenes_for_sec(sec) if sec else scenes_for_duration(project.get("duration_min", 1))
    sys = ("You write concise scripts for AI-generated short videos. "
           "Return ONLY valid JSON matching the schema, no prose, no code fences.")
    schema = ("{\"title\": str, \"hook\": str, \"scenes\": ["
              "{\"heading\": str, \"narration\": str, \"subtitle\": str, "
              "\"image_prompt\": str, \"video_prompt\": str}]}")
    dialogue_rules = (
        "\n- IMPORTANT: This video is in CHARACTER DIALOGUE MODE. Each `narration` field "
        "should be a spoken line prefixed with the speaker name and a colon, e.g. "
        "`Sarah: Hello, welcome.` or `Narrator: In a small town...`. Use at most 3 named "
        "characters plus 1 optional `Narrator`. Keep names consistent across scenes."
        if project.get("dialogue_mode") else ""
    )
    prompt = (
        f"Topic: {project['topic']}\n"
        f"Language: {project['language']}\n"
        f"Style: {project['style']} ({STYLE_GUIDE.get(project['style'], '')})\n"
        f"Target length: {project['duration_min']} minute(s) with {n_scenes} scenes.\n"
        f"Rules:\n"
        f"- Each `narration` is 1-3 sentences, spoken in {project['language']}.\n"
        f"- Each `subtitle` <= 8 words.\n"
        f"- Each `image_prompt` is a vivid, cinematic English prompt suitable for AI image generation.\n"
        f"- Return exactly {n_scenes} scenes."
        f"{dialogue_rules}\n"
        f"Schema: {schema}"
    )
    chat = LlmChat(api_key=EMERGENT_LLM_KEY,
                   session_id=f"script-{project['id']}",
                   system_message=sys).with_model("openai", "gpt-5.4")
    resp = await chat.send_message(UserMessage(text=prompt))
    text = resp.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


async def _generate_image(prompt: str, out_path: Path):
    chat = LlmChat(api_key=EMERGENT_LLM_KEY,
                   session_id=f"img-{uuid.uuid4().hex[:8]}",
                   system_message="Image generator")
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(
        modalities=["image", "text"])
    _, images = await chat.send_message_multimodal_response(
        UserMessage(text=f"Cinematic, high quality, 16:9. {prompt}"))
    if not images:
        raise RuntimeError("No image returned")
    out_path.write_bytes(base64.b64decode(images[0]["data"]))


async def _generate_tts(text: str, voice: str, out_path: Path):
    tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
    audio_bytes = await tts.generate_speech(text=text, model="tts-1",
                                            voice=voice, response_format="mp3")
    out_path.write_bytes(audio_bytes)


def _ffprobe_duration(path: Path) -> float:
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path)
        ], stderr=subprocess.STDOUT).decode().strip()
        return float(out)
    except Exception:
        return 5.0


def _wrap_text(s: str, width: int = 34) -> str:
    words = s.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return "\n".join(lines[:2])


def _ffmpeg_compose_format(project_id: str, fmt_id: str, spec: dict,
                           scenes: list, images: list,
                           audio_path: Path, out_path: Path,
                           total_duration: float):
    """Compose a single output MP4 for one aspect-ratio format spec."""
    per = total_duration / max(len(images), 1)
    tmp_dir = STORAGE_DIR / "videos" / f"tmp_{project_id}_{fmt_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    clips = []
    from formats import build_scene_vf
    for i, (img, sc) in enumerate(zip(images, scenes)):
        clip = tmp_dir / f"c{i}.mp4"
        sub = _wrap_text(sc.get("subtitle", ""), width=spec.get("subtitle_wrap_chars", 34))
        sub_esc = sub.replace(":", "\\:").replace("'", "\u2019")
        vf = build_scene_vf(spec, per, sub_esc)
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(img), "-t", f"{per:.2f}",
            "-vf", vf, "-r", "30", "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", str(clip)
        ], check=True, capture_output=True)
        clips.append(clip)

    concat_txt = tmp_dir / "list.txt"
    concat_txt.write_text("\n".join(f"file '{c}'" for c in clips))
    silent_video = tmp_dir / "video.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
        "-c", "copy", str(silent_video)
    ], check=True, capture_output=True)
    subprocess.run([
        "ffmpeg", "-y", "-i", str(silent_video), "-i", str(audio_path),
        "-c:v", "copy", "-c:a", "aac", "-shortest", str(out_path)
    ], check=True, capture_output=True)
    for c in clips:
        c.unlink(missing_ok=True)
    silent_video.unlink(missing_ok=True)
    concat_txt.unlink(missing_ok=True)
    try:
        tmp_dir.rmdir()
    except OSError:
        pass


def _ffmpeg_compose_all(project_id: str, scenes: list, images: list,
                        audio_path: Path, total_duration: float) -> dict:
    """Compose every registered format. Returns {format_id: relative_url}."""
    import shutil
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg not installed on server. Install with `apt-get install -y ffmpeg`.")
    from formats import FORMATS
    urls: dict = {}
    for fid, spec in FORMATS.items():
        out = STORAGE_DIR / "videos" / f"{project_id}_{fid}.mp4"
        _ffmpeg_compose_format(project_id, fid, spec, scenes, images, audio_path,
                               out, total_duration)
        urls[fid] = f"/api/media/videos/{project_id}_{fid}.mp4"
    return urls


async def run_pipeline(project_id: str):
    """Step 1 (Batch 2): Generate the script, then STOP and wait for user approval.
    Subsequent steps (images/voice/final compose) are triggered by
    POST /api/projects/{id}/script/approve which calls `run_after_script_approval`.
    """
    async def upd(**fields):
        await db.projects.update_one({"id": project_id}, {"$set": fields})
    try:
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
        await upd(stage="writing script", progress=10, status="generating")
        script = await _generate_script(proj)
        scenes = script["scenes"]
        # Save script scenes with placeholder image_url (no images generated yet)
        draft_scenes = [{
            "idx": i,
            "heading": sc.get("heading", f"Scene {i+1}"),
            "narration": sc["narration"],
            "subtitle": sc["subtitle"],
            "image_prompt": sc["image_prompt"],
            "video_prompt": sc.get("video_prompt", sc["image_prompt"]),
            "image_url": None,
            "duration": None,
        } for i, sc in enumerate(scenes)]
        full_narration = " ".join(s["narration"] for s in scenes)
        await upd(
            stage="awaiting script approval",
            progress=20,
            status="awaiting_script_approval",
            title=script.get("title"),
            hook=script.get("hook"),
            script=full_narration,
            scenes=draft_scenes,
        )
        logger.info("Project %s script drafted, awaiting user approval", project_id)
    except Exception as e:
        logger.exception("Script generation failed for %s", project_id)
        await db.projects.update_one({"id": project_id},
                                     {"$set": {"status": "error", "error": str(e),
                                               "stage": "failed"}})
        # Refund credit
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
        if proj:
            cost = int(proj.get("credit_cost", 1) or 1)
            await db.users.update_one({"user_id": proj["user_id"]},
                                      {"$inc": {"credits": cost}})


async def run_after_script_approval(project_id: str):
    """Continues the pipeline once the user has approved the script.
    Batch 2 keeps the remaining stages (images → voice → compose) sequential;
    Batches 3+4 will further split these into individual approval gates.
    """
    async def upd(**fields):
        await db.projects.update_one({"id": project_id}, {"$set": fields})
    try:
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
        scenes = proj.get("scenes") or []
        if not scenes:
            raise RuntimeError("Cannot continue: no scenes on the project.")
        # 2) Images (sequential)
        await upd(stage="generating images", progress=25, status="generating")
        image_paths: List[Path] = []
        img_dir = STORAGE_DIR / "images" / project_id
        img_dir.mkdir(parents=True, exist_ok=True)
        for i, sc in enumerate(scenes):
            p = img_dir / f"s{i}.png"
            image_paths.append(p)
            await _generate_image(sc["image_prompt"], p)
            await upd(progress=25 + int(35 * (i + 1) / max(len(scenes), 1)))
        # 3) TTS
        await upd(stage="generating voiceover", progress=65)
        full_narration = " ".join(s["narration"] for s in scenes)
        audio_path = STORAGE_DIR / "audio" / f"{project_id}.mp3"
        voice = VOICE_MAP.get(proj["voice"], "nova")
        await _generate_tts(full_narration[:4000], voice, audio_path)
        # 4) Compose MP4
        await upd(stage="composing video", progress=80)
        total_dur = _ffprobe_duration(audio_path)
        loop = asyncio.get_event_loop()
        video_urls = await loop.run_in_executor(
            None, _ffmpeg_compose_all, project_id, scenes, image_paths,
            audio_path, total_dur,
        )
        from formats import default_format
        primary = default_format()
        per = total_dur / max(len(scenes), 1)
        final_scenes = [{
            **sc, "image_url": f"/api/media/images/{project_id}/s{i}.png",
            "duration": per,
        } for i, sc in enumerate(scenes)]
        await upd(
            stage="done", progress=100, status="ready",
            scenes=final_scenes,
            audio_url=f"/api/media/audio/{project_id}.mp3",
            video_url=video_urls[primary],
            video_urls=video_urls,
        )
        logger.info("Project %s ready", project_id)
    except Exception as e:
        logger.exception("Post-script pipeline failed for %s", project_id)
        await db.projects.update_one({"id": project_id},
                                     {"$set": {"status": "error", "error": str(e),
                                               "stage": "failed"}})
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
        if proj:
            cost = int(proj.get("credit_cost", 1) or 1)
            await db.users.update_one({"user_id": proj["user_id"]},
                                      {"$inc": {"credits": cost}})


# --------------------------- Experiments (A/B testing) ---------------------------
from experiments import (assign_variant as _assign_variant,
                         variant_content as _variant_content,
                         all_variants as _all_variants)


@api.get("/experiments/{experiment}/{client_id}")
async def experiment_assign(experiment: str, client_id: str, request: Request):
    variant = _assign_variant(experiment, client_id)
    # Fire an exposure event server-side so it's counted even if the client
    # skips analytics (adblock, etc.).
    await db.analytics_events.insert_one({
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "event": "experiment_exposure",
        "properties": {"experiment": experiment, "variant": variant,
                       "client_id": client_id},
        "session_id": client_id,
        "path": "/",
        "user_agent": request.headers.get("user-agent", "")[:200],
        "ip": request.client.host if request.client else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {
        "experiment": experiment,
        "variant": variant,
        "content": _variant_content(experiment, variant),
    }


@api.get("/admin/experiments")
async def admin_experiments(_admin=Depends(require_admin), experiment: str = "landing_hero"):
    since = _iso_ago_days(30)
    variants = _all_variants(experiment)
    expose_cur = db.analytics_events.aggregate([
        {"$match": {"event": "experiment_exposure",
                    "properties.experiment": experiment,
                    "created_at": {"$gte": since}}},
        {"$group": {"_id": {"v": "$properties.variant", "sid": "$session_id"}}},
        {"$group": {"_id": "$_id.v", "sessions": {"$sum": 1}}},
    ])
    expose = {d["_id"]: d["sessions"] async for d in expose_cur}

    sig_cur = db.analytics_events.aggregate([
        {"$match": {"event": {"$in": ["waitlist_submit", "waitlist_success"]},
                    "properties.variant": {"$ne": None},
                    "created_at": {"$gte": since}}},
        {"$group": {"_id": "$properties.variant", "n": {"$sum": 1}}},
    ])
    signups = {d["_id"]: d["n"] async for d in sig_cur}

    cta_cur = db.analytics_events.aggregate([
        {"$match": {"event": "waitlist_button_click",
                    "properties.variant": {"$ne": None},
                    "created_at": {"$gte": since}}},
        {"$group": {"_id": "$properties.variant", "n": {"$sum": 1}}},
    ])
    cta_clicks = {d["_id"]: d["n"] async for d in cta_cur}

    rows = []
    for v in variants:
        sess_n = expose.get(v, 0)
        sig_n = signups.get(v, 0)
        cta_n = cta_clicks.get(v, 0)
        rows.append({
            "variant": v,
            "sessions": sess_n,
            "cta_clicks": cta_n,
            "signups": sig_n,
            "conversion_pct": round((sig_n / sess_n) * 100, 2) if sess_n else 0.0,
            "cta_ctr_pct": round((cta_n / sess_n) * 100, 2) if sess_n else 0.0,
            "content": _variant_content(experiment, v),
        })
    # Sort by conversion desc for a natural winner-first table
    winner = max(rows, key=lambda r: r["conversion_pct"]) if rows else None
    return {
        "experiment": experiment,
        "rows": rows,
        "winner": winner["variant"] if winner and winner["sessions"] > 0 else None,
    }


def _iso_ago_days(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()


# --------------------------- Short URLs ---------------------------
@api.get("/short/{slug}")
async def short_resolve(slug: str, request: Request):
    slug = _clean_slug(slug) or ""
    link = await db.utm_links.find_one({"slug": slug}, {"_id": 0})
    if not link:
        raise HTTPException(404, "Not found")
    # Fire an analytics event so short-link clicks show up in dashboards
    await db.analytics_events.insert_one({
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "event": "short_link_hit",
        "properties": {
            "slug": slug,
            "utm_source": link["params"].get("utm_source"),
            "utm_campaign": link["params"].get("utm_campaign"),
        },
        "path": f"/l/{slug}",
        "referrer": request.headers.get("referer", ""),
        "user_agent": request.headers.get("user-agent", "")[:200],
        "ip": request.client.host if request.client else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"slug": slug, "target": link["url"], "name": link.get("name")}


# --------------------------- UTM Campaign Links (existing) ---------------------------
class UtmLinkIn(BaseModel):
    name: str
    base_url: Optional[str] = None
    source: str
    medium: Optional[str] = None
    campaign: Optional[str] = None
    content: Optional[str] = None
    term: Optional[str] = None
    slug: Optional[str] = None  # Optional short-URL slug for /l/<slug>


def _clean_slug(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9_\-]+", "-", s)
    return s.strip("-") or None


def _compose_url(base: str, params: dict) -> str:
    from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl
    parts = urlparse(base)
    q = dict(parse_qsl(parts.query))
    for k, v in params.items():
        if v:
            q[k] = v
    return urlunparse(parts._replace(query=urlencode(q)))


@api.post("/admin/utm-links")
async def utm_create(payload: UtmLinkIn, request: Request, _admin=Depends(require_admin)):
    if not payload.source.strip():
        raise HTTPException(400, "source is required")
    base = payload.base_url or (str(request.base_url).rstrip("/").replace(
        "http://", "https://").replace(":8001", ""))
    # Strip our own /api path if it accidentally came in
    if base.endswith("/api"):
        base = base[:-4]
    params = {
        "utm_source": _clean_slug(payload.source),
        "utm_medium": _clean_slug(payload.medium),
        "utm_campaign": _clean_slug(payload.campaign),
        "utm_content": _clean_slug(payload.content),
        "utm_term": _clean_slug(payload.term),
    }
    # Short-URL slug: user-supplied or derived from name; ensure uniqueness.
    desired_slug = _clean_slug(payload.slug) or _clean_slug(payload.name) or None
    slug = None
    if desired_slug:
        slug = desired_slug
        suffix = 1
        while await db.utm_links.find_one({"slug": slug}):
            suffix += 1
            slug = f"{desired_slug}-{suffix}"
    doc = {
        "id": f"utm_{uuid.uuid4().hex[:12]}",
        "name": payload.name.strip(),
        "base_url": base,
        "params": params,
        "url": _compose_url(base, params),
        "slug": slug,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.utm_links.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def _link_stats(link: dict, since: str) -> dict:
    p = link["params"]
    match = {"created_at": {"$gte": since}}
    # Match on utm_source at minimum; add utm_campaign/medium if present for precision
    if p.get("utm_source"):
        match["properties.source"] = p["utm_source"]
    if p.get("utm_medium"):
        match["properties.medium"] = p["utm_medium"]
    if p.get("utm_campaign"):
        match["properties.campaign"] = p["utm_campaign"]

    sessions = await db.analytics_events.distinct(
        "session_id", {**match, "event": "page_view"}
    )
    sess_n = len([s for s in sessions if s])
    signups = await db.analytics_events.count_documents(
        {**match, "event": {"$in": ["waitlist_submit", "waitlist_success"]}}
    )
    demo_clicks = await db.analytics_events.count_documents(
        {**match, "event": "book_demo_click"}
    )
    conv_pct = round((signups / sess_n) * 100, 2) if sess_n else 0.0
    return {
        "sessions": sess_n,
        "signups": signups,
        "demo_clicks": demo_clicks,
        "conversion_pct": conv_pct,
    }


@api.get("/admin/utm-links")
async def utm_list(_admin=Depends(require_admin), days: int = 30):
    since = _iso_ago_days(days)
    rows = await db.utm_links.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    for r in rows:
        r["stats"] = await _link_stats(r, since)
    return {"days": days, "rows": rows}


@api.delete("/admin/utm-links/{link_id}")
async def utm_delete(link_id: str, _admin=Depends(require_admin)):
    r = await db.utm_links.delete_one({"id": link_id})
    return {"deleted": r.deleted_count}


@api.get("/admin/utm-links.csv")
async def utm_export_csv(_admin=Depends(require_admin), days: int = 30):
    since = _iso_ago_days(days)
    rows = await db.utm_links.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    import csv, io
    buf = io.StringIO()
    cols = ["name", "url", "utm_source", "utm_medium", "utm_campaign",
            "utm_content", "utm_term", "sessions", "demo_clicks", "signups",
            "conversion_pct", "created_at"]
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        st = await _link_stats(r, since)
        p = r.get("params", {})
        w.writerow([
            r.get("name", ""), r.get("url", ""),
            p.get("utm_source") or "", p.get("utm_medium") or "",
            p.get("utm_campaign") or "", p.get("utm_content") or "",
            p.get("utm_term") or "",
            st["sessions"], st["demo_clicks"], st["signups"], st["conversion_pct"],
            r.get("created_at", ""),
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="utm-campaigns.csv"'},
    )


# --------------------------- Digest ---------------------------
from digest import (build_digest as _build_digest,
                    render_html as _render_digest_html,
                    generate_and_deliver as _generate_digest,
                    DIGEST_HOUR_IST, IST)


@api.get("/admin/digest/preview")
async def digest_preview(_admin=Depends(require_admin)):
    return await _build_digest(db)


@api.get("/admin/digest/preview.html")
async def digest_preview_html(_admin=Depends(require_admin)):
    data = await _build_digest(db)
    return Response(content=_render_digest_html(data), media_type="text/html")


@api.get("/admin/digest/config")
async def digest_config(_admin=Depends(require_admin)):
    return {
        "recipients": [r.strip() for r in os.environ.get(
            "DIGEST_TO", "ashish.jha93@gmail.com").split(",") if r.strip()],
        "sender": os.environ.get("DIGEST_FROM", "AI Video Studio <onboarding@resend.dev>"),
        "schedule": f"Daily at {DIGEST_HOUR_IST:02d}:00 IST",
        "email_enabled": bool(os.environ.get("RESEND_API_KEY")),
        "provider": "Resend",
    }


@api.get("/admin/digest")
async def digest_list(_admin=Depends(require_admin), limit: int = 20):
    cur = db.digests.find({}, {"_id": 0, "html": 0}).sort("generated_at", -1).limit(limit)
    return await cur.to_list(limit)


@api.post("/admin/digest/send-now")
async def digest_send_now(_admin=Depends(require_admin)):
    doc = await _generate_digest(db)
    return {"id": doc["id"], "delivery": doc["delivery"], "subject": doc["subject"]}


@api.get("/admin/digest/{digest_id}")
async def digest_get(digest_id: str, _admin=Depends(require_admin)):
    doc = await db.digests.find_one({"id": digest_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    return doc


# --------------------------- Startup ---------------------------
@app.on_event("startup")
async def startup():
    # Seed admin (empty shell) if not exists so we can promote by email login
    admin = await db.users.find_one({"email": "admin@videostudio.ai"})
    if not admin:
        await db.users.insert_one({
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": "admin@videostudio.ai",
            "name": "Admin",
            "picture": None,
            "role": "admin",
            "plan": "business",
            "credits": 9999,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    # One-time migration: legacy waitlist rows had no `source` — treat them as 'direct'.
    await db.waitlist.update_many(
        {"$or": [{"source": None}, {"source": {"$exists": False}}]},
        {"$set": {"source": "direct"}},
    )
    # Kick off the daily digest scheduler (08:00 IST)
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone=IST)

    async def _digest_job():
        try:
            await _generate_digest(db)
        except Exception:
            logger.exception("Daily digest job failed")

    _scheduler.add_job(_digest_job, CronTrigger(hour=DIGEST_HOUR_IST, minute=0),
                       id="daily_digest", replace_existing=True)
    _scheduler.start()
    logger.info("Digest scheduler started — 08:00 IST daily")


_scheduler = None


@app.on_event("shutdown")
async def _stop_scheduler():
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)


@api.get("/")
async def root():
    return {"service": "AI Video Studio", "status": "ok"}


app.include_router(api)
# Phase 1 stub: architecture only, no live payments. See /app/backend/billing.py
from billing import router as billing_router  # noqa: E402
app.include_router(billing_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    client.close()
