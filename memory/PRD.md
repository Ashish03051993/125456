# AI Video Studio — PRD

## Original problem statement
Build a SaaS web application called "AI Video Studio". Users enter a topic/text
prompt and the system automatically generates a complete video (title, hook,
script, scene-by-scene storyboard, images, voiceover, subtitles, final MP4).
Dashboard, credit system, projects, download, admin panel, pricing.

## Chosen architecture
- Frontend: React 19 + React Router + TailwindCSS + shadcn/ui + sonner
- Backend: FastAPI + Motor (async MongoDB)
- Auth: Emergent-managed Google Auth (session_token httpOnly cookie)
- AI: OpenAI GPT-5.4 (script), Gemini `gemini-3.1-flash-image-preview` (Nano Banana) images, OpenAI TTS `tts-1` (nova/onyx) — all via emergentintegrations + EMERGENT_LLM_KEY
- Video compose: ffmpeg (zoompan Ken Burns + drawtext subtitles + concat + AAC mux)
- Storage: local `/app/backend/storage/{images,audio,videos}` served at `/media/*`

## User personas
- **Creator**: solo content creator turning ideas into publishable videos in minutes.
- **Marketer**: needs styled explainers (Business / Educational) with brand-safe voice.
- **Admin**: manages users, credits, revenue snapshot.

## Core requirements (static)
- Wizard: topic, duration (1/3/5/10 min), language, style (Business/Documentary/Educational/Cinematic/Storytelling), voice (male/female)
- Script → storyboard → per-scene image_prompt/video_prompt/subtitle → images → voiceover → MP4
- Credit system with per-generate deduction and refund on failure
- Landing, Pricing, Dashboard, Wizard, Project View, Settings, Admin Panel
- Blue & white professional theme (Canva/InVideo inspired)

## Implemented (2026-02)
- ✅ Emergent Google Auth (cookie + Authorization Bearer support)
- ✅ Full generation pipeline (script + images + TTS + ffmpeg MP4) — validated E2E in ~90s for 1-min video
- ✅ Projects CRUD, background pipeline, live polling status/progress/stage
- ✅ Landing (hero, how-it-works, bento features, CTA, footer)
- ✅ Pricing (Free / Pro ₹999 / Business ₹4,999 / Enterprise)
- ✅ Dashboard grid with per-project status, progress and delete
- ✅ Project View (progress + storyboard + player + Download MP4 + mocked YouTube/Instagram export)
- ✅ Settings page (profile, plan, credits)
- ✅ Admin Panel (stats: users/projects/videos ready/MRR, user table, edit credits)
- ✅ Auto-seeded admin user `admin@videostudio.ai` (role=admin, credits=9999)

## Deferred / backlog
- P1: Drag-and-drop video editor timeline (scene reorder, per-scene edit)
- P1: Actual YouTube and Instagram publish integration (OAuth + upload)
- P1: Real video generation clips (Runway / Luma / fal.ai) instead of Ken-Burns slideshows
- P1: Stripe / Razorpay checkout for paid plans
- P2: Per-scene image regenerate button, scene reorder in view
- P2: Draft save (create wizard but don't generate yet)
- P2: Team seats (Business plan)
- P2: Analytics for admin (charts using recharts)

## Notes
- ffmpeg is installed at container level. If the container is ever rebuilt from scratch, ensure `apt-get install -y ffmpeg fonts-dejavu`.
- All routes are prefixed `/api`. Static media at `/media`.
- Frontend uses `REACT_APP_BACKEND_URL` for all requests.
