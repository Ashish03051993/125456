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

import bcrypt
import httpx
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAITextToSpeech
from fastapi import (APIRouter, BackgroundTasks, Cookie, Depends, FastAPI,
                     File, Form, Header, HTTPException, Request, UploadFile)
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", ROOT_DIR / "storage"))
for sub in ("images", "audio", "videos", "characters"):
    (STORAGE_DIR / sub).mkdir(parents=True, exist_ok=True)

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]

# Talking-head provider — "stub" (default, no external calls) or "fal_sonic" (needs FAL_KEY env)
TALKING_HEAD_PROVIDER = os.environ.get("TALKING_HEAD_PROVIDER", "stub")
# Paid-only feature — Free-plan users cannot enable talking_head
PAID_PLANS = {"pro", "business", "enterprise"}

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
    talking_head: bool = False            # If True, character speaks on-screen (paid plans only)
    character_image_url: Optional[str] = None   # /api/media/characters/{project_id}.png
    character_source: Optional[str] = None      # "upload" | "ai_generated"
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
    share_slug: Optional[str] = None      # Public share URL slug (nanoid-ish)
    share_enabled: bool = False           # Whether the public link is active
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreateProjectIn(BaseModel):
    topic: str
    duration_sec: Optional[int] = None    # Preferred; if None, falls back to duration_min
    duration_min: Optional[int] = None    # Legacy fallback
    language: str = "English"
    style: str = "Educational"
    voice: str = "female"
    dialogue_mode: bool = False           # Character dialogue toggle
    talking_head: bool = False            # Realistic on-screen speaker (paid plans only)
    character_image_url: Optional[str] = None  # Pre-uploaded/generated character portrait


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
    user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0, "password_hash": 0})
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


# --------------------------- Structured Payment-Required errors ---------------------------
class PaymentRequiredError(HTTPException):
    """HTTPException(402) whose `detail` is a machine-readable dict.
    Response body: {"detail": {"message": "...", "code": "...", ...extras}}
    Client interceptor keys off `code` to render the right upgrade modal."""

    def __init__(self, message: str, code: str, **extras):
        super().__init__(status_code=402, detail={"message": message, "code": code, **extras})


def _paid_feature_required(feature: str, message: Optional[str] = None):
    return PaymentRequiredError(
        message or "This feature is available on Pro plan and above.",
        code="paid_feature_required",
        feature=feature,
        upgrade_url="/pricing",
    )


def _insufficient_credits(need: int, have: int, duration_sec: int):
    return PaymentRequiredError(
        f"Need {need} credits for a {duration_sec}-sec video, you have {have}. Top up to continue.",
        code="insufficient_credits",
        needed=need,
        have=have,
        duration_sec=duration_sec,
        upgrade_url="/pricing",
    )


# --------------------------- Email / Mobile + Password Auth ---------------------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# E.164-ish: optional +, 8–15 digits. Also accept plain 10-digit local numbers.
MOBILE_RE = re.compile(r"^\+?[0-9]{8,15}$")


def _hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _normalize_identifier(raw: str) -> tuple[str, str]:
    """Return (kind, normalized_value). kind = 'email' | 'mobile'. Raises 400 if invalid."""
    v = (raw or "").strip()
    if not v:
        raise HTTPException(400, "Email or mobile is required")
    if EMAIL_RE.match(v):
        return "email", v.lower()
    digits = v.replace(" ", "").replace("-", "")
    if MOBILE_RE.match(digits):
        return "mobile", digits
    raise HTTPException(400, "Enter a valid email address or mobile number")


async def _issue_session(user_id: str, response: Response) -> str:
    token = f"sess_{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    response.set_cookie("session_token", token, max_age=7 * 24 * 3600,
                        httponly=True, secure=True, samesite="none", path="/")
    return token


class RegisterIn(BaseModel):
    name: str
    identifier: str          # email or mobile
    password: str
    mobile: Optional[str] = None  # optional secondary mobile if identifier is email


class LoginIn(BaseModel):
    identifier: str          # email or mobile
    password: str


async def _brute_force_guard(request: Request, ident: str):
    ip = _client_ip(request)
    key = f"{ip}:{ident}"
    now = datetime.now(timezone.utc)
    rec = await db.login_attempts.find_one({"key": key})
    if rec:
        locked_until = rec.get("locked_until")
        if isinstance(locked_until, str):
            try: locked_until = datetime.fromisoformat(locked_until)
            except Exception: locked_until = None
        if locked_until and locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until and locked_until > now:
            wait = int((locked_until - now).total_seconds())
            raise HTTPException(429, f"Too many failed attempts. Try again in {wait}s.")


async def _record_login_failure(request: Request, ident: str):
    ip = _client_ip(request)
    key = f"{ip}:{ident}"
    now = datetime.now(timezone.utc)
    rec = await db.login_attempts.find_one({"key": key}) or {}
    attempts = int(rec.get("attempts", 0)) + 1
    update = {"attempts": attempts, "last_attempt_at": now.isoformat()}
    if attempts >= 5:
        update["locked_until"] = (now + timedelta(minutes=15)).isoformat()
        update["attempts"] = 0  # reset counter after lockout
    await db.login_attempts.update_one({"key": key}, {"$set": update, "$setOnInsert": {"key": key}}, upsert=True)


async def _clear_login_failures(request: Request, ident: str):
    ip = _client_ip(request)
    await db.login_attempts.delete_one({"key": f"{ip}:{ident}"})


@api.post("/auth/register")
async def auth_register(payload: RegisterIn, request: Request, response: Response):
    _rate_limit_check(request, "auth_register", limit=10, window_seconds=600)
    name = (payload.name or "").strip()
    if len(name) < 2:
        raise HTTPException(400, "Name must be at least 2 characters")
    if len(payload.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    kind, ident = _normalize_identifier(payload.identifier)

    # Optional secondary mobile
    mobile_val = None
    if payload.mobile:
        mkind, mval = _normalize_identifier(payload.mobile)
        if mkind != "mobile":
            raise HTTPException(400, "Secondary mobile must be a valid phone number")
        mobile_val = mval

    query = {"email": ident} if kind == "email" else {"mobile": ident}
    existing = await db.users.find_one(query, {"_id": 0})
    if existing:
        # If they already have a password → conflict. If Google-only (no password_hash) → attach one.
        if existing.get("password_hash"):
            raise HTTPException(409, f"An account with this {kind} already exists. Please log in.")
        await db.users.update_one(
            {"user_id": existing["user_id"]},
            {"$set": {
                "password_hash": _hash_password(payload.password),
                "name": existing.get("name") or name,
                **({"mobile": mobile_val} if mobile_val and not existing.get("mobile") else {}),
            }},
        )
        await _issue_session(existing["user_id"], response)
        user = await db.users.find_one({"user_id": existing["user_id"]}, {"_id": 0, "password_hash": 0})
        user = await apply_free_refill(user)
        return {"user": user, "linked": True}

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    doc = {
        "user_id": user_id,
        "name": name,
        "role": "user",
        "plan": "free",
        "credits": 3,
        "password_hash": _hash_password(payload.password),
        "created_at": now_iso,
        "last_refill_at": now_iso,
        "auth_methods": ["password"],
    }
    if kind == "email":
        doc["email"] = ident
        if mobile_val:
            doc["mobile"] = mobile_val
    else:
        doc["mobile"] = ident
    await db.users.insert_one(doc)
    await _issue_session(user_id, response)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"user": user, "created": True}


@api.post("/auth/login")
async def auth_login(payload: LoginIn, request: Request, response: Response):
    _rate_limit_check(request, "auth_login", limit=20, window_seconds=600)
    kind, ident = _normalize_identifier(payload.identifier)
    await _brute_force_guard(request, ident)
    query = {"email": ident} if kind == "email" else {"mobile": ident}
    user = await db.users.find_one(query)
    if not user or not user.get("password_hash"):
        await _record_login_failure(request, ident)
        raise HTTPException(401, "Invalid credentials. If you signed up with Google, use 'Continue with Google'.")
    if not _verify_password(payload.password, user["password_hash"]):
        await _record_login_failure(request, ident)
        raise HTTPException(401, "Invalid credentials")
    await _clear_login_failures(request, ident)
    await _issue_session(user["user_id"], response)
    user_public = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    user_public = await apply_free_refill(user_public)
    return {"user": user_public}


class SetPasswordIn(BaseModel):
    password: str


@api.post("/auth/set-password")
async def auth_set_password(payload: SetPasswordIn, user=Depends(current_user)):
    """Allow an existing (e.g. Google) user to add a password to their account."""
    if len(payload.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"password_hash": _hash_password(payload.password)},
         "$addToSet": {"auth_methods": "password"}},
    )
    return {"ok": True}


# --------------------------- Password Reset ---------------------------
import secrets as _secrets

FRONTEND_URL_ENV = os.environ.get("FRONTEND_URL", "")


async def _send_reset_email(email: str, name: str, reset_url: str) -> str:
    """Deliver the password-reset link. Uses Resend if RESEND_API_KEY is set,
    otherwise logs the link to the backend console (dev/staging fallback).
    Returns 'sent' | 'logged' so callers can surface an accurate hint."""
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        # Dev/staging: log link so devs can copy it out of the backend logs.
        logger.info("password_reset_link email=%s url=%s", email, reset_url)
        return "logged"
    # Real Resend delivery
    try:
        async with httpx.AsyncClient(timeout=15) as hc:
            r = await hc.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {resend_key}",
                         "Content-Type": "application/json"},
                json={
                    "from": os.environ.get("RESEND_FROM", "noreply@kadenza.app"),
                    "to": [email],
                    "subject": "Reset your AI Video Studio password",
                    "html": f"""<div style="font-family:sans-serif;max-width:520px;margin:0 auto">
                      <h2>Hi {name or 'there'},</h2>
                      <p>Click the link below to reset your password. This link expires in 1 hour.</p>
                      <p><a href="{reset_url}" style="display:inline-block;background:#4F46E5;color:#fff;padding:12px 20px;border-radius:24px;text-decoration:none;font-weight:600">Reset password</a></p>
                      <p style="color:#666;font-size:12px">If you didn't request this, ignore this email — your password is safe.</p>
                    </div>""",
                },
            )
        if r.status_code >= 300:
            logger.warning("resend_delivery_failed status=%d body=%s", r.status_code, r.text[:200])
            return "logged"
        return "sent"
    except Exception:
        logger.exception("resend_delivery_exception")
        return "logged"


class ForgotIn(BaseModel):
    identifier: str   # email or mobile


@api.post("/auth/forgot-password")
async def auth_forgot(payload: ForgotIn, request: Request):
    """Generate a 1-hour reset token and email it. Always returns 200 with a
    generic message — never reveals whether the account exists (email-enum guard)."""
    _rate_limit_check(request, "auth_forgot", limit=5, window_seconds=600)
    try:
        kind, ident = _normalize_identifier(payload.identifier)
    except HTTPException:
        # Return generic OK so an attacker can't probe formatting either
        return {"ok": True, "delivery": "logged",
                "message": "If an account matches, a reset link has been sent."}
    query = {"email": ident} if kind == "email" else {"mobile": ident}
    user = await db.users.find_one(query)
    delivery = "logged"
    if user and kind == "email":
        # Invalidate previous unused tokens for this user
        await db.password_reset_tokens.delete_many(
            {"user_id": user["user_id"], "used": {"$ne": True}}
        )
        token = _secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.password_reset_tokens.insert_one({
            "token": token,
            "user_id": user["user_id"],
            "email": user.get("email"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat(),
            "used": False,
        })
        frontend = FRONTEND_URL_ENV or request.headers.get("origin") or ""
        reset_url = f"{frontend}/reset-password?token={token}"
        delivery = await _send_reset_email(user.get("email", ident),
                                           user.get("name", ""), reset_url)
    # Mobile-only accounts: we don't SMS yet — return generic message
    return {"ok": True, "delivery": delivery,
            "message": "If an account matches, a reset link has been sent."}


class ResetPasswordIn(BaseModel):
    token: str
    password: str


@api.post("/auth/reset-password")
async def auth_reset_password(payload: ResetPasswordIn, request: Request, response: Response):
    _rate_limit_check(request, "auth_reset", limit=10, window_seconds=600)
    if len(payload.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    rec = await db.password_reset_tokens.find_one({"token": payload.token})
    if not rec:
        raise HTTPException(400, "Invalid or expired reset link.")
    if rec.get("used"):
        raise HTTPException(400, "This reset link has already been used.")
    exp = rec.get("expires_at")
    if isinstance(exp, str):
        try: exp = datetime.fromisoformat(exp)
        except Exception: exp = None
    if exp and exp.tzinfo is None: exp = exp.replace(tzinfo=timezone.utc)
    if not exp or exp < datetime.now(timezone.utc):
        raise HTTPException(400, "This reset link has expired. Please request a new one.")
    # Update the user's password
    await db.users.update_one(
        {"user_id": rec["user_id"]},
        {"$set": {"password_hash": _hash_password(payload.password)},
         "$addToSet": {"auth_methods": "password"}},
    )
    # Invalidate ALL existing sessions for this user (security: any prior stolen
    # session_token is now unusable). A fresh one is issued below.
    await db.user_sessions.delete_many({"user_id": rec["user_id"]})
    # Mark token used
    await db.password_reset_tokens.update_one(
        {"token": payload.token},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc).isoformat()}},
    )
    # Auto-log-in the user for a smooth UX
    await _issue_session(rec["user_id"], response)
    user_public = await db.users.find_one({"user_id": rec["user_id"]},
                                          {"_id": 0, "password_hash": 0})
    return {"user": user_public, "message": "Password reset successful."}


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
    # Talking-head is a paid-plan-only feature
    if payload.talking_head and user.get("plan", "free") not in PAID_PLANS:
        raise _paid_feature_required("talking_head",
            "Talking-head is available on Pro plan and above. "
            "Upgrade to enable a realistic on-screen speaker.")
    if int(user.get("credits", 0) or 0) < cost:
        raise _insufficient_credits(cost, int(user.get("credits", 0) or 0), sec)
    project = Project(
        user_id=user["user_id"],
        topic=payload.topic,
        duration_sec=sec,
        duration_min=max(1, sec // 60),      # legacy field, best-effort mapping
        language=payload.language,
        style=payload.style,
        voice=payload.voice,
        dialogue_mode=payload.dialogue_mode,
        talking_head=payload.talking_head,
        character_image_url=payload.character_image_url,
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


class RenameProjectIn(BaseModel):
    title: str


@api.patch("/projects/{pid}/title")
async def rename_project(pid: str, payload: RenameProjectIn, user=Depends(current_user)):
    """Rename any project (works in ANY status — safe metadata-only edit)."""
    title = (payload.title or "").strip()
    if len(title) < 1: raise HTTPException(400, "Title cannot be empty")
    if len(title) > 200: raise HTTPException(400, "Title too long (max 200 chars)")
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    await db.projects.update_one({"id": pid}, {"$set": {"title": title}})
    return await db.projects.find_one({"id": pid}, {"_id": 0})


@api.post("/projects/{pid}/duplicate")
async def duplicate_project(pid: str, user=Depends(current_user)):
    """Create a fresh draft with the same settings (topic/duration/style/voice/
    dialogue_mode/talking_head + character reference). Does NOT copy generated
    content (script, scenes, audio, video) — user reruns generation from scratch."""
    src = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not src: raise HTTPException(404, "Not found")
    user_fresh = await apply_free_refill(await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0}))
    cost = int(src.get("credit_cost", credit_cost_for_sec(src.get("duration_sec", 30))))
    # Duplicating a talking-head project on a downgraded account? Fail fast.
    if src.get("talking_head") and user_fresh.get("plan", "free") not in PAID_PLANS:
        raise _paid_feature_required("talking_head",
            "This project uses Talking Head — Pro plan required to duplicate.")
    if int(user_fresh.get("credits", 0) or 0) < cost:
        raise _insufficient_credits(cost, int(user_fresh.get("credits", 0) or 0),
                                    src.get("duration_sec", 30))
    new_id = f"proj_{uuid.uuid4().hex[:12]}"

    # Copy the character portrait file to a new path keyed by new_id so
    # deleting the source project won't break the duplicate.
    new_char_url = None
    src_char_url = src.get("character_image_url")
    if src_char_url:
        for ext in (".png", ".jpg", ".webp"):
            src_file = STORAGE_DIR / "characters" / f"{src['id']}{ext}"
            if src_file.exists():
                dst_file = STORAGE_DIR / "characters" / f"{new_id}{ext}"
                try:
                    dst_file.write_bytes(src_file.read_bytes())
                    new_char_url = f"/api/media/characters/{new_id}{ext}?v={int(datetime.now(timezone.utc).timestamp())}"
                except Exception:
                    logger.exception("Failed to copy character file on duplicate")
                break

    now_iso = datetime.now(timezone.utc).isoformat()
    original_title = src.get("title") or src.get("topic") or "Untitled"
    doc = {
        "id": new_id,
        "user_id": user_fresh["user_id"],
        "topic": src.get("topic"),
        "title": f"{original_title[:180]} (copy)",
        "duration_sec": src.get("duration_sec", 30),
        "duration_min": src.get("duration_min", 1),
        "language": src.get("language", "English"),
        "style": src.get("style", "Educational"),
        "voice": src.get("voice", "female"),
        "dialogue_mode": src.get("dialogue_mode", False),
        "talking_head": src.get("talking_head", False),
        "character_image_url": new_char_url,
        "character_source": src.get("character_source") if new_char_url else None,
        "credit_cost": cost,
        "status": "draft",
        "progress": 0,
        "stage": "queued",
        "scenes": [],
        "created_at": now_iso,
    }
    await db.projects.insert_one(doc)
    return await db.projects.find_one({"id": new_id}, {"_id": 0})


class ProjectPatchIn(BaseModel):
    topic: Optional[str] = None
    duration_sec: Optional[int] = None
    style: Optional[str] = None
    language: Optional[str] = None
    voice: Optional[str] = None
    dialogue_mode: Optional[bool] = None
    talking_head: Optional[bool] = None


@api.patch("/projects/{pid}")
async def patch_project(pid: str, payload: ProjectPatchIn, user=Depends(current_user)):
    """Update project settings while it is still a draft. Once generation has
    started, only /script/edit is allowed."""
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    if p["status"] != "draft":
        raise HTTPException(400, f"Project is no longer editable (status: {p['status']}).")
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    # Recompute cost if duration changed
    if "duration_sec" in updates:
        updates["credit_cost"] = credit_cost_for_sec(updates["duration_sec"])
        updates["duration_min"] = max(1, updates["duration_sec"] // 60)
    if updates.get("talking_head"):
        user_fresh = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
        if (user_fresh or {}).get("plan", "free") not in PAID_PLANS:
            raise _paid_feature_required("talking_head")
    if updates:
        await db.projects.update_one({"id": pid}, {"$set": updates})
    return await db.projects.find_one({"id": pid}, {"_id": 0})


# --------------------------- Character Portrait (Talking-Head) ---------------------------
CHAR_MAX_BYTES = 5 * 1024 * 1024   # 5 MB
CHAR_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


def _require_paid_plan(user: dict):
    if user.get("plan", "free") not in PAID_PLANS:
        raise _paid_feature_required("talking_head")


@api.post("/projects/{pid}/character/upload")
async def upload_character(pid: str, file: UploadFile = File(...),
                           user=Depends(current_user)):
    """User uploads their own portrait. Saves under /storage/characters/{pid}.png."""
    _require_paid_plan(user)
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    if file.content_type not in CHAR_ALLOWED_MIME:
        raise HTTPException(400, "Only JPG, PNG or WEBP allowed.")
    contents = await file.read()
    if len(contents) > CHAR_MAX_BYTES:
        raise HTTPException(400, f"File too large. Max {CHAR_MAX_BYTES // 1024 // 1024} MB.")
    if len(contents) < 1024:
        raise HTTPException(400, "File too small.")
    ext = ".png" if file.content_type == "image/png" else (".webp" if file.content_type == "image/webp" else ".jpg")
    out_path = STORAGE_DIR / "characters" / f"{pid}{ext}"
    # Remove any prior character file for this project
    for existing_ext in (".png", ".jpg", ".webp"):
        old = STORAGE_DIR / "characters" / f"{pid}{existing_ext}"
        if old.exists() and old != out_path:
            try: old.unlink()
            except Exception: pass
    out_path.write_bytes(contents)
    # Cache buster
    url = f"/api/media/characters/{pid}{ext}?v={int(datetime.now(timezone.utc).timestamp())}"
    await db.projects.update_one(
        {"id": pid},
        {"$set": {"character_image_url": url, "character_source": "upload"}},
    )
    return {"character_image_url": url}


class CharGenIn(BaseModel):
    description: str   # "A confident 30-year-old Indian entrepreneur in a blazer"


@api.post("/projects/{pid}/character/generate")
async def generate_character(pid: str, payload: CharGenIn, user=Depends(current_user)):
    """AI-generate a realistic portrait via Nano Banana (Emergent LLM Key)."""
    _require_paid_plan(user)
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    desc = (payload.description or "").strip()
    if len(desc) < 8:
        raise HTTPException(400, "Please describe the character in at least a few words.")
    # Build a photorealistic-portrait prompt so the output looks like a real human.
    prompt = ("Photorealistic close-up portrait, professional studio lighting, sharp focus, "
              "cinematic 85mm depth of field, natural skin texture, direct eye contact. "
              f"Subject: {desc[:280]}. Ultra-realistic, no cartoon, no illustration.")
    out_path = STORAGE_DIR / "characters" / f"{pid}.png"
    # Clean up any prior character file
    for existing_ext in (".jpg", ".webp"):
        old = STORAGE_DIR / "characters" / f"{pid}{existing_ext}"
        if old.exists():
            try: old.unlink()
            except Exception: pass
    try:
        await _generate_image(prompt, out_path)
    except Exception as e:
        logger.exception("Character generation failed for %s", pid)
        raise HTTPException(502, f"Character generation failed: {str(e)[:120]}")
    url = f"/api/media/characters/{pid}.png?v={int(datetime.now(timezone.utc).timestamp())}"
    await db.projects.update_one(
        {"id": pid},
        {"$set": {"character_image_url": url, "character_source": "ai_generated"}},
    )
    return {"character_image_url": url}


@api.delete("/projects/{pid}/character")
async def delete_character(pid: str, user=Depends(current_user)):
    """Remove the character portrait from a project."""
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    for ext in (".png", ".jpg", ".webp"):
        f = STORAGE_DIR / "characters" / f"{pid}{ext}"
        if f.exists():
            try: f.unlink()
            except Exception: pass
    await db.projects.update_one(
        {"id": pid},
        {"$set": {"character_image_url": None, "character_source": None}},
    )
    return {"ok": True}


@api.get("/features/talking_head")
async def talking_head_feature():
    """Expose feature status so the frontend knows whether to show the toggle."""
    return {
        "enabled": True,
        "provider": TALKING_HEAD_PROVIDER,
        "live_render": TALKING_HEAD_PROVIDER != "stub" and bool(os.environ.get("FAL_KEY")),
        "paid_plans": sorted(list(PAID_PLANS)),
        "max_upload_mb": CHAR_MAX_BYTES // 1024 // 1024,
    }


# --------------------------- Public Share Links ---------------------------
_SHARE_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/l


def _generate_share_slug(length: int = 10) -> str:
    return "".join(_secrets.choice(_SHARE_ALPHABET) for _ in range(length))


@api.post("/projects/{pid}/share")
async def enable_share(pid: str, user=Depends(current_user)):
    """Create (or return existing) public share slug for a completed video."""
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    if p.get("status") != "ready":
        raise HTTPException(400, "Only completed videos can be shared. "
                                 "Approve all steps to finish rendering first.")
    slug = p.get("share_slug")
    if not slug:
        # Retry-until-unique (astronomically unlikely to collide, but be safe)
        for _ in range(5):
            candidate = _generate_share_slug()
            if not await db.projects.find_one({"share_slug": candidate}, {"_id": 1}):
                slug = candidate; break
        if not slug:
            raise HTTPException(500, "Couldn't allocate a share link, try again.")
    await db.projects.update_one(
        {"id": pid},
        {"$set": {"share_slug": slug, "share_enabled": True,
                  "shared_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"share_slug": slug, "share_enabled": True}


@api.delete("/projects/{pid}/share")
async def disable_share(pid: str, user=Depends(current_user)):
    """Revoke the public share link (slug stays reserved but link is disabled)."""
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    await db.projects.update_one({"id": pid}, {"$set": {"share_enabled": False}})
    return {"ok": True}


@api.get("/public/videos/{slug}")
async def public_video(slug: str, request: Request):
    """Public endpoint — no auth. Returns a slim, safe projection for the /v/:slug page."""
    _rate_limit_check(request, "public_video", limit=120, window_seconds=60)
    p = await db.projects.find_one({"share_slug": slug, "share_enabled": True}, {"_id": 0})
    if not p:
        raise HTTPException(404, "This video is no longer available.")
    if p.get("status") != "ready":
        raise HTTPException(404, "This video is no longer available.")
    # Look up creator display name (may be null if user was deleted)
    creator = await db.users.find_one(
        {"user_id": p["user_id"]}, {"_id": 0, "name": 1, "picture": 1},
    ) or {}
    # Fire-and-forget view counter
    try:
        await db.projects.update_one(
            {"share_slug": slug},
            {"$inc": {"share_view_count": 1},
             "$set": {"share_last_viewed_at": datetime.now(timezone.utc).isoformat()}},
        )
    except Exception: pass
    return {
        "slug": slug,
        "title": p.get("title") or p.get("topic"),
        "hook": p.get("hook"),
        "duration_sec": p.get("duration_sec"),
        "language": p.get("language"),
        "style": p.get("style"),
        "video_url": p.get("video_url"),
        "video_urls": p.get("video_urls") or {},
        "scenes": [{"idx": s.get("idx"), "heading": s.get("heading"),
                    "subtitle": s.get("subtitle"), "image_url": s.get("image_url")}
                   for s in (p.get("scenes") or [])],
        "creator_name": creator.get("name") or "A Kadenza creator",
        "view_count": (p.get("share_view_count") or 0) + 1,
    }


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


# --------------------------- Guided Approval Endpoints (Batch 2) ---------------------------
@api.post("/projects/{pid}/script/regenerate")
async def regenerate_script(pid: str, bg: BackgroundTasks, user=Depends(current_user)):
    """Discard current draft and generate a fresh script. No extra credit charged
    — the initial credit deduction covers all script regenerations up to approval."""
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    if p["status"] not in ("awaiting_script_approval", "error"):
        raise HTTPException(400, f"Cannot regenerate script from status '{p['status']}'.")
    await db.projects.update_one(
        {"id": pid},
        {"$set": {"status": "generating", "stage": "rewriting script",
                  "progress": 10, "error": None}},
    )
    bg.add_task(run_pipeline, pid)   # same entrypoint — will end at awaiting_script_approval
    return {"ok": True}


class ScriptEditIn(BaseModel):
    title: Optional[str] = None
    hook: Optional[str] = None
    scenes: Optional[List[dict]] = None   # user-edited scenes list


@api.patch("/projects/{pid}/script")
async def edit_script(pid: str, payload: ScriptEditIn, user=Depends(current_user)):
    """User-driven inline edit of the draft script. Only allowed while awaiting
    script approval. Scenes must keep the same length; users can tweak narration,
    subtitle or image_prompt but cannot add/remove scenes here."""
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    if p["status"] != "awaiting_script_approval":
        raise HTTPException(400, f"Script is not editable in status '{p['status']}'.")
    updates: dict = {}
    if payload.title is not None: updates["title"] = payload.title[:120]
    if payload.hook is not None: updates["hook"] = payload.hook[:280]
    if payload.scenes is not None:
        existing = p.get("scenes") or []
        if len(payload.scenes) != len(existing):
            raise HTTPException(400, "Scene count cannot change during edit.")
        merged = []
        for i, sc in enumerate(payload.scenes):
            base = existing[i]
            merged.append({
                **base,
                "narration": (sc.get("narration") or base.get("narration") or "")[:600],
                "subtitle": (sc.get("subtitle") or base.get("subtitle") or "")[:120],
                "image_prompt": (sc.get("image_prompt") or base.get("image_prompt") or "")[:400],
            })
        updates["scenes"] = merged
        updates["script"] = " ".join(s.get("narration", "") for s in merged)
    if updates:
        await db.projects.update_one({"id": pid}, {"$set": updates})
    return await db.projects.find_one({"id": pid}, {"_id": 0})


@api.post("/projects/{pid}/script/approve")
async def approve_script(pid: str, bg: BackgroundTasks, user=Depends(current_user)):
    """User approved the current script — kick off images/voice/compose."""
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    if p["status"] != "awaiting_script_approval":
        raise HTTPException(400, f"Cannot approve from status '{p['status']}'.")
    await db.projects.update_one(
        {"id": pid},
        {"$set": {"status": "generating", "stage": "generating images",
                  "progress": 25, "error": None}},
    )
    bg.add_task(run_after_script_approval, pid)
    return {"ok": True}


# --------------------------- Guided Approval Endpoints (Batch 3: Images) ---------------------------
@api.post("/projects/{pid}/images/regenerate/{idx}")
async def regenerate_single_image(pid: str, idx: int, user=Depends(current_user)):
    """Regenerate one scene's image. Runs synchronously (await) so the caller
    gets back the updated project with a fresh image_url + cache-buster."""
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    if p["status"] != "awaiting_image_approval":
        raise HTTPException(400, f"Images not editable in status '{p['status']}'.")
    await regen_single_image(pid, idx)
    return await db.projects.find_one({"id": pid}, {"_id": 0})


@api.post("/projects/{pid}/images/regenerate")
async def regenerate_all_images(pid: str, bg: BackgroundTasks, user=Depends(current_user)):
    """Regenerate every scene's image (rare — user hated all of them)."""
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    if p["status"] != "awaiting_image_approval":
        raise HTTPException(400, f"Cannot regenerate from status '{p['status']}'.")
    await db.projects.update_one(
        {"id": pid},
        {"$set": {"status": "generating", "stage": "regenerating images",
                  "progress": 30, "error": None}},
    )
    bg.add_task(run_after_script_approval, pid)   # regenerates all images, stops at awaiting_image_approval
    return {"ok": True}


@api.post("/projects/{pid}/images/approve")
async def approve_images(pid: str, bg: BackgroundTasks, user=Depends(current_user)):
    """User approved all visuals — kick off voice generation."""
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    if p["status"] != "awaiting_image_approval":
        raise HTTPException(400, f"Cannot approve from status '{p['status']}'.")
    await db.projects.update_one(
        {"id": pid},
        {"$set": {"status": "generating", "stage": "generating voiceover",
                  "progress": 65, "error": None}},
    )
    bg.add_task(run_after_image_approval, pid)
    return {"ok": True}


# --------------------------- Guided Approval Endpoints (Batch 4: Voice) ---------------------------
class VoiceRegenIn(BaseModel):
    voice: Optional[str] = None   # optional new voice preset ("female", "male", etc.)


@api.post("/projects/{pid}/voice/regenerate")
async def regenerate_voice(pid: str, payload: VoiceRegenIn, bg: BackgroundTasks,
                           user=Depends(current_user)):
    """Regenerate the voiceover (optionally with a different voice)."""
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    if p["status"] != "awaiting_voice_approval":
        raise HTTPException(400, f"Cannot regenerate voice from status '{p['status']}'.")
    updates = {"status": "generating", "stage": "regenerating voiceover",
               "progress": 70, "error": None}
    if payload.voice is not None:
        if payload.voice not in VOICE_MAP:
            raise HTTPException(400, f"Unknown voice '{payload.voice}'. Allowed: {list(VOICE_MAP)}")
        updates["voice"] = payload.voice
    await db.projects.update_one({"id": pid}, {"$set": updates})
    bg.add_task(run_after_image_approval, pid)   # regenerates voice, stops at awaiting_voice_approval
    return {"ok": True}


@api.post("/projects/{pid}/voice/approve")
async def approve_voice(pid: str, bg: BackgroundTasks, user=Depends(current_user)):
    """User approved the voiceover — final compose (ffmpeg) starts now."""
    p = await db.projects.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
    if not p: raise HTTPException(404, "Not found")
    if p["status"] != "awaiting_voice_approval":
        raise HTTPException(400, f"Cannot approve from status '{p['status']}'.")
    await db.projects.update_one(
        {"id": pid},
        {"$set": {"status": "generating", "stage": "composing video",
                  "progress": 85, "error": None}},
    )
    bg.add_task(run_after_voice_approval, pid)
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
                           total_duration: float, language: str = "English"):
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
        vf = build_scene_vf(spec, per, sub_esc, language=language)
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
                        audio_path: Path, total_duration: float,
                        language: str = "English") -> dict:
    """Compose every registered format. Returns {format_id: relative_url}."""
    import shutil
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg not installed on server. Install with `apt-get install -y ffmpeg`.")
    from formats import FORMATS
    urls: dict = {}
    for fid, spec in FORMATS.items():
        out = STORAGE_DIR / "videos" / f"{project_id}_{fid}.mp4"
        _ffmpeg_compose_format(project_id, fid, spec, scenes, images, audio_path,
                               out, total_duration, language=language)
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
    """Stage 2: Generate images, then STOP at status='awaiting_image_approval'."""
    async def upd(**fields):
        await db.projects.update_one({"id": project_id}, {"$set": fields})
    try:
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
        scenes = proj.get("scenes") or []
        if not scenes:
            raise RuntimeError("Cannot continue: no scenes on the project.")
        await upd(stage="generating images", progress=30, status="generating")
        img_dir = STORAGE_DIR / "images" / project_id
        img_dir.mkdir(parents=True, exist_ok=True)
        for i, sc in enumerate(scenes):
            p = img_dir / f"s{i}.png"
            await _generate_image(sc["image_prompt"], p)
            scenes[i] = {**sc, "image_url": f"/api/media/images/{project_id}/s{i}.png"}
            await upd(scenes=scenes,
                      progress=30 + int(30 * (i + 1) / max(len(scenes), 1)))
        await upd(stage="awaiting image approval", progress=60,
                  status="awaiting_image_approval", scenes=scenes)
        logger.info("Project %s images drafted, awaiting image approval", project_id)
    except Exception as e:
        logger.exception("Image stage failed for %s", project_id)
        await db.projects.update_one({"id": project_id},
                                     {"$set": {"status": "error", "error": str(e),
                                               "stage": "failed"}})
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
        if proj:
            cost = int(proj.get("credit_cost", 1) or 1)
            await db.users.update_one({"user_id": proj["user_id"]},
                                      {"$inc": {"credits": cost}})


async def regen_single_image(project_id: str, scene_idx: int):
    """Regenerate one specific scene image without re-running the whole stage."""
    async def upd(**fields):
        await db.projects.update_one({"id": project_id}, {"$set": fields})
    try:
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
        scenes = proj.get("scenes") or []
        if scene_idx < 0 or scene_idx >= len(scenes):
            raise RuntimeError(f"Scene idx {scene_idx} out of range.")
        sc = scenes[scene_idx]
        img_dir = STORAGE_DIR / "images" / project_id
        img_dir.mkdir(parents=True, exist_ok=True)
        p = img_dir / f"s{scene_idx}.png"
        await _generate_image(sc["image_prompt"], p)
        # bust browser cache with cache-buster query param on URL
        import time as _t
        scenes[scene_idx] = {**sc, "image_url": f"/api/media/images/{project_id}/s{scene_idx}.png?v={int(_t.time())}"}
        await upd(scenes=scenes, status="awaiting_image_approval",
                  stage="awaiting image approval")
    except Exception as e:
        logger.exception("Single image regen failed for %s scene %d", project_id, scene_idx)


async def run_after_image_approval(project_id: str):
    """Stage 3: Generate voiceover, then STOP at status='awaiting_voice_approval'."""
    async def upd(**fields):
        await db.projects.update_one({"id": project_id}, {"$set": fields})
    try:
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
        scenes = proj.get("scenes") or []
        await upd(stage="generating voiceover", progress=65, status="generating")
        full_narration = " ".join(s["narration"] for s in scenes)
        audio_path = STORAGE_DIR / "audio" / f"{project_id}.mp3"
        voice = VOICE_MAP.get(proj.get("voice", "female"), "nova")
        await _generate_tts(full_narration[:4000], voice, audio_path)
        await upd(stage="awaiting voice approval", progress=75,
                  status="awaiting_voice_approval",
                  audio_url=f"/api/media/audio/{project_id}.mp3")
        logger.info("Project %s voice drafted, awaiting voice approval", project_id)
    except Exception as e:
        logger.exception("Voice stage failed for %s", project_id)
        await db.projects.update_one({"id": project_id},
                                     {"$set": {"status": "error", "error": str(e),
                                               "stage": "failed"}})
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
        if proj:
            cost = int(proj.get("credit_cost", 1) or 1)
            await db.users.update_one({"user_id": proj["user_id"]},
                                      {"$inc": {"credits": cost}})


async def run_after_voice_approval(project_id: str):
    """Stage 4 (final): Compose the MP4 in every format."""
    async def upd(**fields):
        await db.projects.update_one({"id": project_id}, {"$set": fields})
    try:
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
        scenes = proj.get("scenes") or []
        await upd(stage="composing video", progress=85, status="generating")
        audio_path = STORAGE_DIR / "audio" / f"{project_id}.mp3"
        image_paths = [STORAGE_DIR / "images" / project_id / f"s{i}.png"
                       for i in range(len(scenes))]
        total_dur = _ffprobe_duration(audio_path)
        loop = asyncio.get_event_loop()
        video_urls = await loop.run_in_executor(
            None, _ffmpeg_compose_all, project_id, scenes, image_paths,
            audio_path, total_dur, proj.get("language", "English"),
        )
        from formats import default_format
        primary = default_format()
        per = total_dur / max(len(scenes), 1)
        final_scenes = [{**sc, "duration": per} for sc in scenes]
        await upd(
            stage="done", progress=100, status="ready",
            scenes=final_scenes,
            video_url=video_urls[primary],
            video_urls=video_urls,
        )
        logger.info("Project %s ready", project_id)
    except Exception as e:
        logger.exception("Compose stage failed for %s", project_id)
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
    # Ensure indexes for auth
    try:
        # If pre-existing indexes are non-unique, drop them and recreate as unique+sparse.
        existing = await db.users.index_information()
        for name, spec in list(existing.items()):
            keys = dict(spec.get("key") or {})
            if keys in ({"email": 1}, {"mobile": 1}) and not spec.get("unique"):
                try: await db.users.drop_index(name)
                except Exception: pass
        await db.users.create_index("email", unique=True, sparse=True)
        await db.users.create_index("mobile", unique=True, sparse=True)
        await db.users.create_index("user_id", unique=True)
        await db.user_sessions.create_index("session_token", unique=True)
        await db.login_attempts.create_index("key", unique=True)
        await db.password_reset_tokens.create_index("token", unique=True)
        await db.projects.create_index("share_slug", unique=True, sparse=True)
        # NOTE: TTL on ISO-string dates doesn't work — we manually prune expired tokens in scheduler
    except Exception as e:
        logger.warning("index_creation_warning: %s", e)
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

    async def _cleanup_job():
        """Nightly: purge abandoned drafts (>24h old, status='draft', no scenes)
        and expired password reset tokens (>1h past expires_at)."""
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            r1 = await db.projects.delete_many({
                "status": "draft",
                "created_at": {"$lt": cutoff},
                "$or": [{"scenes": {"$size": 0}}, {"scenes": {"$exists": False}}],
            })
            # Expired reset tokens
            now_iso = datetime.now(timezone.utc).isoformat()
            r2 = await db.password_reset_tokens.delete_many({
                "$or": [{"expires_at": {"$lt": now_iso}},
                        {"used": True,
                         "used_at": {"$lt": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()}}],
            })
            # Orphaned character files (>24h old, no matching draft in DB)
            char_dir = STORAGE_DIR / "characters"
            purged_files = 0
            if char_dir.exists():
                cutoff_ts = (datetime.now(timezone.utc) - timedelta(hours=24)).timestamp()
                for f in char_dir.iterdir():
                    if not f.is_file(): continue
                    if f.stat().st_mtime > cutoff_ts: continue
                    pid = f.stem   # proj_xxxxx
                    if not await db.projects.find_one({"id": pid}, {"_id": 1}):
                        try: f.unlink(); purged_files += 1
                        except Exception: pass
            logger.info("cleanup_job drafts=%d tokens=%d orphan_char_files=%d",
                        r1.deleted_count, r2.deleted_count, purged_files)
        except Exception:
            logger.exception("Cleanup job failed")

    _scheduler.add_job(_digest_job, CronTrigger(hour=DIGEST_HOUR_IST, minute=0),
                       id="daily_digest", replace_existing=True)
    _scheduler.add_job(_cleanup_job, CronTrigger(hour=3, minute=0),
                       id="nightly_cleanup", replace_existing=True)
    _scheduler.start()
    logger.info("Schedulers started — digest 08:00 IST + cleanup 03:00 IST daily")


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
