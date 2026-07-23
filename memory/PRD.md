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

## Phase 12 (2026-02) — Sign-in Access + Analytics Correctness Fix
- ✅ **Sign-in nav button** — landing page top nav now shows a visible `Sign in` link (data-testid=`nav-signin-btn`) alongside `Join waitlist` for waitlist members who receive invite emails. Visible on ≥640px; hidden on mobile to preserve pill button prominence. Fires `signin_click` analytics event tagged with `source: 'top_nav'` then redirects to Emergent Auth.
- ✅ **/login route** — direct-link route (data-testid=`login-page`) that auto-triggers Google OAuth for anon users and redirects logged-in users to `/dashboard`. Ideal for invite email links.
- ✅ **Analytics correctness bug fix** — pre-existing bug in `/app/frontend/src/lib/analytics.js` where caller-supplied `properties.source` (e.g. `'top_nav'`, `'landing_hero'`) was silently overwritten by the visitor's attribution source. Swapped spread order so caller wins while attribution still fills in as fallback. Affected every event using `source:` (signin_click, waitlist_button_click, etc). Confirmed by testing agent 5/5 green.

## Phase 11 (2026-02) — Attribution Matrix CSV Export
- ✅ **CSV export** — new `GET /api/admin/attribution-matrix.csv` (admin-only) delegates to the JSON endpoint for numeric consistency and streams a CSV: header row + one line per cell + `__total__` variant lines for row totals + `__total__` source lines for col totals + a final grand total. Filename encodes today's date.
- ✅ **Frontend Export CSV button** on the Attribution Matrix panel header (data-testid=`matrix-export-csv-btn`). Uses `<a download>` synthesis so the server-supplied Content-Disposition filename is honored. Toast confirmation. Mobile-safe at 390px (flex-wrap + shrink-0).
- ✅ Testing iter-13: 23/23 backend + full frontend green, including a strict JSON↔CSV round-trip test that verifies every cell + row-total + col-total + grand-total is numerically identical between the two endpoints.

## Phase 10 (2026-02) — Untagged Drilldown + Waitlist Referral Loop
- ✅ **Untagged Session Drilldown** — new `GET /api/admin/sanity/untagged` endpoint returns {total, sessions[], top_referrer_hosts[], top_landing_paths[]}. Rollups computed over ALL untagged sessions (not just paginated slice), capped at 15 entries each. Sanity Panel's "Untagged sessions" card is now a clickable button that opens a shadcn Dialog with rollup panels + a session table + a "Recommended: use tracked UTM link" banner that jumps to /admin?tab=utm.
- ✅ **Waitlist Position Badge + Referral Share Loop** — success screen now shows a large gradient position badge (`#N`) plus 3 share CTAs (LinkedIn native share dialog, X/Twitter intent, Copy referral link). Referral URL carries `utm_source=referral&utm_medium=share&utm_campaign=waitlist&ref={position}` so downstream signups auto-attribute back to the referrer channel in the attribution matrix. Every share click fires a `waitlist_share_click` analytics event tagged with channel + position.
- ✅ Testing iter-12: 22/22 backend + full frontend green. One design regression caught + fixed (outline share buttons invisible inside `bg-ink-900 text-white` landing section — added `text-ink-900`).

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

## Phase 3 — Freemium Guided Pipeline + Custom Auth (2026-07)
- ✅ **Custom Email/Mobile + Password Auth** alongside Emergent Google Auth (2026-07-23)
  - `POST /api/auth/register` — accepts email OR mobile (E.164) + password + name
  - `POST /api/auth/login` — password auth; issues same `session_token` httpOnly cookie used by Google Auth (unified sessions)
  - `POST /api/auth/set-password` — lets Google-signed users add a password later
  - `bcrypt` hashing (rounds=12), 8-char minimum, brute-force lockout after 5 fails (15-min cool-down)
  - Rate limits: 10 registers / 20 logins per IP per 10 min
  - Unique + sparse indexes on `users.email` and `users.mobile`
  - `/api/auth/me` now strips `password_hash` before returning
- ✅ **Login vs Sign-up split** — previously the same page. Now:
  - `/login` — Email/Mobile + Password + Continue with Google
  - `/signup` — Name + Email/Mobile + Password + Confirm + Continue with Google
  - Top-nav "Log in" and "Sign up free" buttons wired to correct pages
  - Landing hero and Pricing CTAs → `/signup`
- ✅ Free tier: 3 credits/month auto-refill (`FREE_MONTHLY_CREDITS=3`, refill on `/auth/me`)
- ✅ Duration picker: 8 tiers (30s / 45s / 60s / 90s / 2m / 3m / 5m / 10m) with credit cost per tier
- ✅ **Full step-gated pipeline** — script → images → voice → compose (2026-07-23)
  - Script gate: `/api/projects/{id}/script/{approve|regenerate}` + PATCH edit
  - **Image gate**: `/api/projects/{id}/images/{approve|regenerate}` + `/images/regenerate/{idx}` for per-scene refresh
  - **Voice gate**: `/api/projects/{id}/voice/{approve|regenerate}` — regenerate accepts optional `{voice}` to switch preference (returns 400 on unknown voice)
  - Credit refund on failure now covers all pipeline stages (script, image, voice, compose)
  - Frontend: `image-approval-panel` (per-scene regen buttons + Approve/Regen All) and `voice-approval-panel` (audio preview + voice switch + regenerate/approve) in ProjectView
- ✅ Character dialogue mode (`dialogue_mode` toggle in wizard, multi-voice TTS parsing)
- ✅ Hindi subtitles rendered via Noto CJK/Devanagari fonts (OS-level `apt install fonts-noto-cjk fonts-noto-devanagari`)
- ✅ Testing: iteration 19 (auth, 100% frontend / 86% backend rate-limit-noise) + iteration 20 (image/voice gates, 100% both) + iteration 21 (talking-head feature, 100% both)
- ✅ **Realistic Talking Head — Pro feature** (2026-07-23)
  - `POST /api/projects/{id}/character/upload` — user uploads own portrait (JPG/PNG/WEBP, max 5MB)
  - `POST /api/projects/{id}/character/generate` — AI-generates photorealistic portrait via Nano Banana from user description
  - `DELETE /api/projects/{id}/character` — clears character
  - `GET /api/features/talking_head` — feature flag exposure (enabled + provider + live_render + paid_plans + max_upload_mb)
  - `PATCH /api/projects/{id}` — draft-only project updates (topic/duration/style/voice/dialogue_mode/talking_head) with plan gate + credit recompute
  - Backend Project model extended: `talking_head`, `character_image_url`, `character_source` fields
  - Free plan gets **402 Payment Required** on any talking-head or character operation — Pro/Business/Enterprise unlocked
  - Frontend wizard: new "Realistic Talking Head [PRO]" section, upsell modal for Free users, upload OR AI-generate character with live preview, character-source badge (upload vs AI-generated), replace-character button
  - Actual lip-sync render is **stubbed behind env `TALKING_HEAD_PROVIDER=stub`** — UI shows "Preview mode" badge and honest disclosure. When user provides fal.ai API key, flip env to `fal_sonic` to activate real lip-sync render (~$0.02/sec of output)

## Backlog after Phase 3
- P0: Password reset flow (`/api/auth/forgot-password` + email link via Resend) — needs Resend API key from user
- P0: Sentry error tracking (FE + BE) — needs Sentry DSN from user
- P1: CORS lockdown to final production domain (currently `CORS_ORIGINS=*`)
- P1: Landing OG meta tags + `sitemap.xml` for SEO
- P1: Rate limiting on more public APIs
- P1: Inline rename, duplicate as new version, public share link on projects
- P2: `server.py` modular split (routes/, services/, models/) — currently ~2140 lines
- P2: Real Resend email delivery for daily digests
- P2: Real Stripe checkout for paid credit packs
- P2: Per-project image regen cooldown (throttle abuse of `/images/regenerate/{idx}`)
