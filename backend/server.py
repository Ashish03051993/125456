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
                     Header, HTTPException, Request, Response)
from fastapi.responses import FileResponse, JSONResponse
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
    duration_min: int = 1
    language: str = "English"
    style: str = "Educational"
    voice: str = "female"
    status: str = "draft"  # draft | generating | ready | error
    progress: int = 0
    stage: str = "queued"
    title: Optional[str] = None
    hook: Optional[str] = None
    script: Optional[str] = None
    scenes: List[Scene] = []
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreateProjectIn(BaseModel):
    topic: str
    duration_min: int = 1
    language: str = "English"
    style: str = "Educational"
    voice: str = "female"


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
            "credits": 5,
            "created_at": datetime.now(timezone.utc).isoformat(),
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
    return user


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


@api.post("/projects")
async def create_project(payload: CreateProjectIn, user=Depends(current_user)):
    if user.get("credits", 0) <= 0:
        raise HTTPException(402, "No credits remaining. Upgrade your plan.")
    p = Project(user_id=user["user_id"], **payload.model_dump())
    doc = p.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.projects.insert_one(doc)
    return await db.projects.find_one({"id": p.id}, {"_id": 0})


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
    # Decrement one credit up-front
    await db.users.update_one({"user_id": user["user_id"]}, {"$inc": {"credits": -1}})
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


@api.get("/admin/stats")
async def admin_stats(_admin=Depends(require_admin)):
    total_users = await db.users.count_documents({})
    total_projects = await db.projects.count_documents({})
    ready = await db.projects.count_documents({"status": "ready"})
    plans_cur = db.users.aggregate([{"$group": {"_id": "$plan", "n": {"$sum": 1}}}])
    plans = {d["_id"] or "free": d["n"] async for d in plans_cur}
    # Fake revenue calc
    price = {"free": 0, "pro": 999, "business": 4999}
    revenue = sum(price.get(k, 0) * v for k, v in plans.items())
    return {
        "total_users": total_users,
        "total_projects": total_projects,
        "videos_ready": ready,
        "plans": plans,
        "monthly_revenue_inr": revenue,
    }


# --------------------------- Media static ---------------------------
app.mount("/media", StaticFiles(directory=str(STORAGE_DIR)), name="media")


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
    n_scenes = scenes_for_duration(project["duration_min"])
    sys = ("You write concise scripts for AI-generated short videos. "
           "Return ONLY valid JSON matching the schema, no prose, no code fences.")
    schema = ("{\"title\": str, \"hook\": str, \"scenes\": ["
              "{\"heading\": str, \"narration\": str, \"subtitle\": str, "
              "\"image_prompt\": str, \"video_prompt\": str}]}")
    prompt = (
        f"Topic: {project['topic']}\n"
        f"Language: {project['language']}\n"
        f"Style: {project['style']} ({STYLE_GUIDE.get(project['style'], '')})\n"
        f"Target length: {project['duration_min']} minute(s) with {n_scenes} scenes.\n"
        f"Rules:\n"
        f"- Each `narration` is 1-3 sentences, spoken in {project['language']}.\n"
        f"- Each `subtitle` <= 8 words.\n"
        f"- Each `image_prompt` is a vivid, cinematic English prompt suitable for AI image generation.\n"
        f"- Return exactly {n_scenes} scenes.\n"
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


def _ffmpeg_compose(project_id: str, scenes: List[dict], images: List[Path],
                    audio_path: Path, out_path: Path, total_duration: float):
    """Build MP4: image slideshow with Ken Burns pan + audio + burned subtitles."""
    per = total_duration / max(len(images), 1)
    tmp_dir = STORAGE_DIR / "videos" / f"tmp_{project_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    clips = []
    # Build a per-scene short mp4 with subtitle drawn
    for i, (img, sc) in enumerate(zip(images, scenes)):
        clip = tmp_dir / f"c{i}.mp4"
        sub = _wrap_text(sc.get("subtitle", ""))
        # escape single quotes for drawtext
        sub_esc = sub.replace(":", "\\:").replace("'", "\u2019")
        vf = (
            f"scale=1920:1080:force_original_aspect_ratio=increase,"
            f"crop=1920:1080,"
            f"zoompan=z='min(zoom+0.0008,1.12)':d={int(per*30)}:s=1920x1080:fps=30,"
            f"drawbox=y=ih-160:color=black@0.55:width=iw:height=160:t=fill,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{sub_esc}':fontcolor=white:fontsize=44:x=(w-text_w)/2:y=h-130"
        )
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(img), "-t", f"{per:.2f}",
            "-vf", vf, "-r", "30", "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", str(clip)
        ], check=True, capture_output=True)
        clips.append(clip)

    # concat list
    concat_txt = tmp_dir / "list.txt"
    concat_txt.write_text("\n".join(f"file '{c}'" for c in clips))
    silent_video = tmp_dir / "video.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
        "-c", "copy", str(silent_video)
    ], check=True, capture_output=True)
    # Mux audio
    subprocess.run([
        "ffmpeg", "-y", "-i", str(silent_video), "-i", str(audio_path),
        "-c:v", "copy", "-c:a", "aac", "-shortest", str(out_path)
    ], check=True, capture_output=True)
    # Cleanup tmp
    for c in clips:
        c.unlink(missing_ok=True)
    silent_video.unlink(missing_ok=True)
    concat_txt.unlink(missing_ok=True)
    try:
        tmp_dir.rmdir()
    except OSError:
        pass


async def run_pipeline(project_id: str):
    async def upd(**fields):
        await db.projects.update_one({"id": project_id}, {"$set": fields})
    try:
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
        # 1) Script
        await upd(stage="writing script", progress=10)
        script = await _generate_script(proj)
        scenes = script["scenes"]
        # 2) Images (parallel)
        await upd(stage="generating images", progress=25,
                  title=script.get("title"), hook=script.get("hook"))
        image_paths: List[Path] = []
        img_dir = STORAGE_DIR / "images" / project_id
        img_dir.mkdir(parents=True, exist_ok=True)
        tasks = []
        for i, sc in enumerate(scenes):
            p = img_dir / f"s{i}.png"
            image_paths.append(p)
            tasks.append(_generate_image(sc["image_prompt"], p))
        # Run sequentially to avoid concurrent_request_limit on shared key
        for i, t in enumerate(tasks):
            await t
            await upd(progress=25 + int(35 * (i + 1) / max(len(tasks), 1)))
        # 3) TTS full narration
        await upd(stage="generating voiceover", progress=65)
        full_narration = " ".join(s["narration"] for s in scenes)
        audio_path = STORAGE_DIR / "audio" / f"{project_id}.mp3"
        voice = VOICE_MAP.get(proj["voice"], "nova")
        await _generate_tts(full_narration[:4000], voice, audio_path)
        # 4) Compose MP4
        await upd(stage="composing video", progress=80)
        total_dur = _ffprobe_duration(audio_path)
        out_video = STORAGE_DIR / "videos" / f"{project_id}.mp4"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _ffmpeg_compose, project_id, scenes,
                                   image_paths, audio_path, out_video, total_dur)
        # Build final scene list w/ image urls
        final_scenes = []
        per = total_dur / max(len(scenes), 1)
        for i, sc in enumerate(scenes):
            final_scenes.append({
                "idx": i,
                "heading": sc.get("heading", f"Scene {i+1}"),
                "narration": sc["narration"],
                "subtitle": sc["subtitle"],
                "image_prompt": sc["image_prompt"],
                "video_prompt": sc.get("video_prompt", sc["image_prompt"]),
                "image_url": f"/media/images/{project_id}/s{i}.png",
                "duration": per,
            })
        await upd(
            stage="done", progress=100, status="ready",
            title=script.get("title"), hook=script.get("hook"),
            script=full_narration, scenes=final_scenes,
            audio_url=f"/media/audio/{project_id}.mp3",
            video_url=f"/media/videos/{project_id}.mp4",
        )
        logger.info("Project %s ready", project_id)
    except Exception as e:
        logger.exception("Pipeline failed for %s", project_id)
        await db.projects.update_one({"id": project_id},
                                     {"$set": {"status": "error", "error": str(e),
                                               "stage": "failed"}})
        # Refund credit
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
        if proj:
            await db.users.update_one({"user_id": proj["user_id"]},
                                      {"$inc": {"credits": 1}})


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


@api.get("/")
async def root():
    return {"service": "AI Video Studio", "status": "ok"}


app.include_router(api)
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
