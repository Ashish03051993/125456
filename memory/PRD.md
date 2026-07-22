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

## Phase 9 (2026-02) — Analytics Trust + Waitlist Empty-State
- ✅ **Analytics Sanity Panel** on Admin → Overview — new `GET /api/admin/sanity` endpoint returning: orphan_signups (waitlist rows with no matching page_view session), unattributed_sessions (page_views with no utm_source, with pct), duplicate_emails (case-insensitive `$toLower` grouping). Panel renders 3 sub-cards + verdict badge (✓ Analytics healthy / ⚠ Review recommended) with thresholds (orphans+dups==0 AND untagged<25%).
- ✅ **Attribution Matrix UX** — every cell now has a plain-English `title` tooltip explaining the numbers. Overflow cells (signups > sessions) render in amber with a ⚠ suffix. New 3-row footnote with a color legend (green ≥ 20%, amber ⚠ explainer).
- ✅ **Video warning copy softened** — "Video failed to load" + "network, decoding or storage issue" (was: "Video file not found" / "missing on disk"). Matches the actual set of failure modes covered by `<video onError>`.
- ✅ **Waitlist empty-state** — when 0 signups, Admin → Waitlist shows a friendly gradient card with 3 CTAs: Share on LinkedIn (opens native LinkedIn share with pre-filled launch URL + summary), Copy launch link (clipboard + toast), Build tracked UTM link (tab jump). Plus a 3-step playbook (Announce / DM 10 / Watch).
- ✅ Testing iter-11: 19/19 backend + 100% frontend. Zero regressions.

## Phase 8 (2026-02) — Dual-Format Video Export + Signup Attribution Matrix
- ✅ **Dual-format ffmpeg pipeline** — `/app/backend/formats.py` registers `landscape` (16:9, 1920x1080, cover-crop) and `vertical` (9:16, 1080x1920, pad-blur). `_ffmpeg_compose_all` iterates FORMATS and produces `{project_id}_{fid}.mp4` for each. Adding a new aspect ratio is one declarative entry.
- ✅ Project response persists both `video_url` (backwards-compat, points to default landscape) and `video_urls: {landscape, vertical}` dict.
- ✅ **Format Switcher** in `ProjectView.jsx` — chips render only when >1 format available. Clicking swaps `<video>` src (via key remount), toggles container aspect class (`aspect-video` vs `aspect-[9/16]`), updates Download button label, and lists target platforms.
- ✅ **Video-missing warning** — amber banner (data-testid=`video-missing-warning`) fires on `<video onError>` when file 404s.
- ✅ **Signup Attribution Matrix** — `GET /api/admin/attribution-matrix` returns Source × Variant → {signups, sessions, conversion_pct} with row/col/grand totals. Admin panel (Experiments tab) renders a matrix table with per-cell testids.
- ✅ Public `GET /api/formats` endpoint exposing the format registry to the frontend.
- ✅ **Infra**: `apt-get install -y ffmpeg fonts-dejavu` (5.1.9) installed on preview container. Defensive `shutil.which("ffmpeg")` guard in `_ffmpeg_compose_all` raises a friendly `RuntimeError` if binary missing.
- ✅ Testing pass iter-9 (100% — 22/22 backend + 100% frontend) + iter-10 delta (100% — 13/13 backend + 100% frontend, after a critical Rules-of-Hooks regression in ProjectView.jsx was caught and fixed by testing agent).

## Phase 7 (2026-02) — Multi-Chip Filters + Short URLs
- ✅ **Tri-chip filters** on Admin Waitlist tab: Source / Plan / Variant chip rows combine via AND. Header renders active-filter chips + "Clear filters" button. `variant='unassigned'` bucket matches null/missing rows.
- ✅ Backend `/api/admin/waitlist` now returns three facets (`by_source`, `by_plan`, `by_variant`) with counts, accepts `?variant=` filter combinable with `source` and `plan`.
- ✅ Waitlist table gained a `Variant` column (violet chip when set).
- ✅ **Short URLs** — UTM builder now has an optional `slug` field with a live hostname/l/ prefix; auto-derives kebab slug from name if blank; duplicate slugs get `-2` suffix. Saved links table shows the short URL below the name with copy button.
- ✅ Frontend `/l/:slug` route resolves to `/api/short/{slug}` → `window.location.replace(target)` so LinkedIn users see a clean short URL while the destination still receives full utm_* attribution.
- ✅ Each `/l/:slug` hit records a `short_link_hit` analytics event with utm_source + campaign.
- ✅ Testing pass 8/8 — 16/16 new + 42/42 combined regression, 100% green (backend + frontend Playwright).

## Phase 6 (2026-02) — CSV Export + Segment Compare
- ✅ **Waitlist CSV export** — `/api/admin/waitlist.csv` streams CSV with position/email/name/plan/source/medium/campaign/variant/use_case/referrer/created_at; filename encodes the active filter (e.g. `waitlist-linkedin.csv`)
- ✅ **UTM Links CSV export** — `/api/admin/utm-links.csv` with per-link stats (sessions, demo_clicks, signups, conversion_pct) rolled up over 30 days
- ✅ **Attribution capture on waitlist** — POST `/api/waitlist` now accepts `source/medium/campaign/variant` in the payload; frontend WaitlistForm and BookDemoDialog send `getAttribution()` on submit so every signup is linked back to its LinkedIn/campaign
- ✅ **Segment Compare** — Admin Waitlist tab renders segment chips (`All + one per source`) with live counts. Clicking a chip filters the table via `?source=linkedin` and updates the header to "N from linkedin of TOTAL total"
- ✅ Added Source + Campaign columns to the Waitlist table
- ✅ Idempotent startup migration coalesces legacy `source=null` rows to `'direct'`, plus `$ifNull` + `$or` defense-in-depth
- ✅ Testing pass 6+7: 68/68 across full non-generation suite; iter-6 HIGH-severity duplicate-'direct' bucket bug is closed (retested)

## Phase 5 (2026-02) — UTM Campaign Links
- ✅ **UTM Builder** in Admin (new tab `UTM Links`) — 7 quick presets: LinkedIn Post / Article / DM / Ad, Cold Email, Community Post, Custom
- ✅ Form with live-updating kebab-cased preview URL, copy-to-clipboard (with fallback), and save-to-DB
- ✅ Saved-links table with per-link stats (sessions / demo clicks / signups / conversion %) rolled up from `analytics_events` by matching `properties.source/medium/campaign`
- ✅ Backend endpoints: `POST /api/admin/utm-links`, `GET /api/admin/utm-links`, `DELETE /api/admin/utm-links/{id}` — admin-only
- ✅ Testing pass 5/5: 10/10 new tests + 56/56 across the non-generation suite — 100% green


## Phase 1 Additions #2 (2026-02, this iteration) — A/B Testing + Daily Digest

- ✅ **A/B Testing** on landing hero (`landing_hero` experiment) — two variants (A/B) with distinct **eyebrow / headline / subtitle / primary CTA / secondary CTA**. Deterministic per-client assignment via SHA-256 (client_id persisted in `localStorage.avs_client_id`). Every subsequent analytics event carries `properties.variant`.
- ✅ Backend endpoints: `GET /api/experiments/{exp}/{client_id}` (returns content + writes an exposure event), `GET /api/admin/experiments` (rows with sessions / CTA clicks / signups / conversion% / CTR% + winner). Non-admin gets 403.
- ✅ **Daily Digest** (7-day rolling window, WoW deltas): visitors, waitlist signups, conversion rate, traffic sources, A/B performance, demo requests, device split (UA-parsed), top countries (best-effort via ip-api.com).
- ✅ Scheduler: **APScheduler AsyncIOScheduler + CronTrigger(hour=8, tz=IST)** — fires daily at 08:00 IST → recipient `ashish.jha93@gmail.com` (via `DIGEST_TO`). Every digest is stored in `digests` Mongo collection.
- ✅ Email delivery: **Resend** integration — activates automatically when `RESEND_API_KEY` is set in `/app/backend/.env`. Until then, digests are generated + stored + previewable, and Admin shows a yellow warning banner.
- ✅ Admin new tabs: **A/B Tests** (side-by-side variant cards with content preview + stats + winner banner) and **Daily Digest** (schedule card, Preview email HTML, Generate now button, KPI cards, WoW/Devices/Top-countries panels, digest archive table).
- ✅ Testing pass 4/4: 15/15 new tests pass + 62/63 across full suite (only failure is unrelated EMERGENT_LLM_KEY budget on the video pipeline test).

## Phase 1 Additions (2026-02) — Demo Video + Book-a-Demo + Rich Analytics
- ✅ Landing **Demo Video Section**: 30-second demo MP4 with poster, IntersectionObserver-based impression tracking, play-click view tracking, 4 output cards (Cinematic Video / LinkedIn Post / Blog Article / Email Newsletter) demonstrating multi-format repurposing from one prompt
- ✅ **Book-a-Demo** dialog for agencies/enterprise — surfaced from hero link, Waitlist section CTA, Pricing footer CTA and the Enterprise plan CTA. Submissions land in `waitlist` collection with `plan_interest=enterprise` and `use_case="DEMO_REQUEST · seats=… · notes=…"`
- ✅ **Attribution capture** (`captureAttribution()`): reads `?utm_source/?utm_medium/?utm_campaign/?ref` and classifies referrer host (organic_search / social / referral / direct); attribution is persisted in localStorage and injected into every subsequent `track()` event
- ✅ Backend endpoint `GET /api/admin/analytics` now returns `conversion_by_source[]` with {sessions, demo_views, signups, conversion_pct} per source; `GET /api/admin/stats` exposes `demo_views`, `demo_impressions`, `book_demo_clicks`, `waitlist_clicks`
- ✅ Admin **Overview** shows 4 additional stat cards (Waitlist clicks / Demo views / Demo impressions / Book demo clicks); **Analytics** tab adds a `Conversion by traffic source` table
- ✅ Static media path moved to `/api/media/...` (previous `/media/...` was routed to the frontend by ingress and returned HTML)
- ✅ Testing pass 3/3: 31/31 backend tests + Landing/Pricing/Admin/Mobile Playwright flows PASS

## Phase 2 — Market validation (2026-02)
- ✅ Waitlist collection: `POST /api/waitlist` with position tracking, duplicate detection, plan interest and use-case capture
- ✅ Analytics tracking: `POST /api/analytics/track` with per-session `session_id` (localStorage-persisted) — `page_view`, `cta_click`, `pricing_cta_click`, `waitlist_submit`, `waitlist_success` events
- ✅ Landing pivot: waitlist-first hero, "Reserve my spot" CTA, dedicated waitlist section, footer marked "Private beta"
- ✅ Pricing page: CTAs now funnel to the waitlist (no live checkout)
- ✅ Admin dashboard tabs: **Overview** (waitlist + signups 24h + events 24h + users), **Waitlist** (searchable table, Copy emails, Export CSV), **Analytics** (recharts BarChart of events + LineChart of daily activity)
- ✅ Stripe stub `/app/backend/billing.py` mounted at `/api/billing` — status endpoint returns `{enabled:false, phase:"waitlist"}`, checkout/webhook return 501 (architecture only, no payments)
- ✅ Mobile responsiveness: landing, pricing, admin all verified at 390px viewport
- ✅ Testing pass 2/2: 34/34 backend tests + 4/4 Playwright frontend flows PASS

## Deferred (unchanged from Phase 1)
- Wire real Stripe checkout when payments are ready
- Timeline editor / scene regeneration / YouTube & Instagram publish

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
