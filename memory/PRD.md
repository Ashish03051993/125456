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


## Phase 14 (2026-02) — Welcome Banner + Starter Templates + Referral Milestones + Share Landing Loop
- ✅ **Cohort Retention Analytics + Drilldown** — new `GET /api/admin/analytics/cohorts?weeks=8` and `GET /api/admin/analytics/cohorts/{week_start}/users` (admin-only). Analytics tab now shows a "Signup-week cohorts" card with per-week table (Signups / Activated / Activation% / Shared / Share%), all-time totals, and a stacked bar chart. Each row is click-through: opens a dialog listing the exact users (name, email, plan chip, credits, activated ✓, shared ✓, referred ✓, signup timestamp) — usable for retention outreach. Test-ids `cohorts-section`, `cohort-row-{iso_date}`, `cohort-drilldown-dialog`, `cohort-drilldown-table`, `cohort-user-{uid}`. E2E verified: clicked 2026-07-20 row → dialog rendered with 100 users, all fields populated.
- ✅ **Razorpay Credit-Pack Purchases (feature-flagged, dormant until keys set)** — Full paid-checkout stack built and inert: `razorpay==2.0.1` installed; new `/app/backend/razorpay_router.py` with `/config`, `/create-order`, `/verify` (HMAC signature check), `/webhook` (server-to-server fallback with optional secret). All endpoints return `503` until `RAZORPAY_KEY_ID` + `RAZORPAY_KEY_SECRET` are set — safe to ship. Frontend: `/app/frontend/src/lib/razorpayCheckout.js` loads Checkout.js on demand + orchestrates the modal; `/app/frontend/src/pages/BuyCredits.jsx` at route `/credits` shows 4 credit packs (Starter/Creator/Studio/Enterprise, ₹499–₹19999) with test-mode banner and graceful "coming soon" fallback pointing users to the referral program when disabled. TopBar credits badge links to `/credits`. Payment records stored in `payments` collection for reconciliation. NOTE: this went beyond Phase 1 but is left in place per user request; it stays completely invisible/inert until you flip the env vars.
- ✅ **Resend default sender fixed** — the `_send_reset_email` fallback address was still `noreply@kadenza.app` from the old rebrand. Updated to Resend's public sandbox `onboarding@resend.dev` so ops don't have to remember to override the default just to unblock testing. Real prod use should always set `RESEND_FROM` to a domain-verified sender.
- ✅ **Project Retry on Error** — `ProjectView.jsx` error state now includes a prominent **Retry generation** button + Back-to-Dashboard secondary action. The retry hits the existing `POST /api/projects/{pid}/generate` endpoint (credits were already refunded on error and are re-deducted cleanly on retry). Copy updated to explicitly call out how many credits were refunded and reassure users the same topic/settings will be reused. Any `402 insufficient-credits` response falls through to the existing global paywall interceptor. Test-ids `error-panel`, `retry-generate-btn`, `back-to-dashboard-btn`. E2E verified against a seeded error project.
- ✅ **Onboarding Checklist** — new `<OnboardingChecklist projects={projects} />` on Dashboard auto-tracks 3 milestones from the user's projects: (1) *Create your first video* (any project exists), (2) *Watch it come to life* (any project `status === "ready"`), (3) *Share with the world* (any project `share_enabled === true`). Renders only when 0 < progress < 3 — silent when user hasn't started (`WelcomeBanner` covers that) and silent when fully done (fires a one-time "🎉 You're a pro now!" Sonner toast on completion). Progress bar + checked-strikethrough for done steps + inline CTA for the current pending step. Dismissable, dismissal persisted to `localStorage['avs_onboarding_dismissed_v1']`. Test-ids `onboarding-checklist`, `onboarding-progress-bar`, `onboarding-progress-text`, `onboarding-step-{create,render,share}`, `onboarding-step-{id}-done`, `onboarding-dismiss`. E2E verified against a user with `create+render` complete: shows "Your quick-start · 2 of 3 done", heading "Next up: share with the world", steps 1 & 2 checked + step 3 pending.
- ✅ **Template Preview (HoverCard)** — every starter card in `StarterTemplates` now surfaces a 3-line sample script preview on hover (shadcn `HoverCard`, 150ms open delay). Each template gained a `preview` array with a realistic hook/mid/close line for its style. Educational, Business, Storytelling, Cinematic all have distinct hand-written samples. Hint text on card + inside the popover reinforces "Click to load into the wizard". Test-ids `starter-template-{id}-preview`. E2E verified: hovered Educational card, popover appeared with the 3 quantum-computing sample lines.
- ✅ **Prompt Suggestions (multi-angle)** — `/api/wizard/enhance-topic` now returns `{enhanced, alternatives: [str, str]}` — the LLM is asked to produce **3 distinct angles** (e.g. explainer vs story vs contrarian) in a single call and the response is JSON-parsed with fallback + de-dup + 500-char clamp. `ProjectWizard.jsx` still applies the primary rewrite in-place with the Undo action, and now also renders an "Or try another angle" panel below the textarea listing the alternatives as clickable chips (`topic-suggestion-0`, `topic-suggestion-1`). Clicking a chip swaps the topic and removes just that chip. E2E verified: raw "blockbuster failure" → 3 outputs (explainer 220c, storytelling 197c, contrarian 199c) all rendered.
- ✅ **AI Prompt Enhancer (wizard)** — new `POST /api/wizard/enhance-topic` endpoint (auth required, 20/10min per-IP rate limit, 0 credits) uses GPT-5.4 via emergentintegrations to rewrite a rough user topic into a 1–3 sentence, hook-friendly, style-aware brief. `ProjectWizard.jsx` shows an "Enhance with AI" pill button next to the topic label. On click it swaps the topic in-place, fires a Sonner toast with an **Undo** action to restore the original, respects the currently selected style + language, and gracefully surfaces backend errors (short-topic 400, LLM timeout 502) as user-facing toasts. Guards: min 3 chars, max 500 chars in, hard-clamped to 500 chars out. Also added a subtle "Tip: 15+ words gives the AI enough context" hint under the textarea. E2E verified: raw *"blockbuster failure"* (2 words) → rich 233-char brief in-place, toast surfaces, credits untouched. Test-id `enhance-topic-btn`.
- ✅ **Dashboard Draft Resume Card** — new `<DraftResumeCard />` renders at the top of the Dashboard whenever `localStorage['avs_wizard_draft_v1']` contains a topic ≥3 chars. Shows a truncated preview of the topic, a relative timestamp ("15m ago"), and two actions: Resume draft (→ `/new`, wizard restores the full state) and Discard (clears the draft). Also has an "✕" dismiss button in the corner. Coexists gracefully with the Welcome Banner + Starter Templates below. Recovers users who started the wizard on a previous visit but never finished — a common drop-off point. Test-ids `draft-resume-card`, `draft-resume-btn`, `draft-discard-btn`, `draft-dismiss`. E2E verified: seeded a 15-min-old draft in localStorage, reloaded Dashboard, card rendered with correct text and CTA href.
- ✅ **Public Share Referral Loop** — every shared video is now an automatic referral link. Backend `/api/public/videos/{slug}` returns a new `creator_ref_code` field (creator's own referral code). `PublicVideo.jsx` reads `?ref=<code>` from the URL (explicit override) or falls back to `creator_ref_code`, persists it to `localStorage['avs_pending_referral']` (so it survives redirects through login/signup), forwards it to *both* signup CTAs (topbar + hero), swaps the ribbon copy to invite-mode, and shows a dedicated "You've been invited by <creator> — claim 3 free credits" chip. Test-ids `invite-chip`, `hero-cta-ribbon`, `hero-cta-signup`, `topbar-signup`. E2E verified: hero button href → `/signup?ref=XQEBLM`, localStorage populated, chip text matches creator name. Closes the viral loop end-to-end without any manual URL-crafting from creators.
- ✅ **Signup Ref Autopickup** — `Signup.jsx` now falls back to `localStorage['avs_pending_referral']` when no `?ref=` is present in the URL. Emits `referral_landing { source: "url"|"storage" }` for analytics attribution. Clears the pending key on successful signup so it never leaks into future sessions. Makes the referral loop bulletproof even if the user closes the tab and comes back to `/signup` directly. E2E verified: fresh signup visit with only localStorage populated → invited banner shows `(XQEBLM)` and the code is bound to the register call.
- ✅ **Welcome Banner mounted + verified** — `<WelcomeBanner hasProjects={projects.length > 0} />` now renders on the Dashboard between `<LowCreditNudge />` and the projects list. Auto-hides once the user has any projects OR dismissed the banner (persisted in `localStorage['avs_welcome_dismissed_v1']`). Three-step guide (Topic → Approve → Download), CTA button routes to `/new` and dismisses. Test-ids `welcome-banner`, `welcome-cta-btn`, `welcome-step-1/2/3`, `welcome-dismiss`. Fixed missing JSX mount from previous session (import was present but component was never rendered). E2E verified via screenshot with a freshly-registered account.
- ✅ **Starter Templates on empty dashboard** — new `<StarterTemplates />` component shows 4 curated one-click starters (Educational, Business, Storytelling, Cinematic) under the empty state. Clicking a card writes `{topic, style, fromTemplate:true, templateId}` to `avs_wizard_draft_v1` and navigates to `/new`. `ProjectWizard.jsx` now detects `fromTemplate` and shows a friendly *"Template loaded — tweak the topic or style, then generate"* toast instead of the generic "Draft restored". Removes the cold-start "what do I even ask for?" friction for new users. Test-ids `starter-templates`, `starter-template-{id}`. E2E verified: clicking Educational template lands wizard at `/new` with the 95-char topic pre-populated.
- ✅ **Referral Milestones** — new `<ReferralMilestones />` sub-component inside `ReferralPanel` gamifies the existing invite loop. 4 tiers (🎉 First Invite @ 1, 🥉 Ambassador @ 3, 🥈 Advocate @ 10, 🥇 Champion @ 25) rendered as a gradient progress bar with tier chips. Shows current earned tier as a badge chip and the exact **"N more to unlock <tier> (+N*bonus credits along the way)"** copy — making the credit reward front-and-center. Pure frontend, backend `invited_count` and `bonus_per_referral` from `/api/referrals/me` used as-is. Test-ids `referral-milestones`, `referral-current-tier`, `referral-progress-bar`, `referral-tier-{n}`. E2E verified on both 0-invite (empty state) and 14-invite (Advocate) accounts.

## Phase 13 (2026-02) — Launch Compliance + Wizard Draft-Save + Prod Hardening + Referrals
- ✅ **Cookie Consent Banner mounted** — `<CookieConsent />` mounted globally in `App.js` (right below `<UpgradeModal />`). Appears 700ms after first paint (avoids CLS), stores choice in `localStorage['avs_cookie_consent_v1']` with `{necessary, analytics, at, v}`, broadcasts `cookie-consent:updated` event so downstream analytics layers can respect user choice. Verified: shows on first visit → hides on Accept/Only-Necessary → stays hidden across reload.
- ✅ **robots.txt + sitemap.xml verified** — both serve correctly under `/robots.txt` and `/sitemap.xml`; robots.txt allows public routes (`/`, `/pricing`, `/terms`, `/privacy`, `/v/`) and disallows auth/dashboard surfaces; sitemap lists 6 public URLs.
- ✅ **Wizard draft-save (P2 backlog item cleared)** — `ProjectWizard.jsx` now auto-persists `{topic, durationSec, style, language, voice, dialogueMode}` to `localStorage['avs_wizard_draft_v1']` on every change. On revisit, restores the draft and shows a `Draft restored` toast. Draft is cleared automatically when the user clears the topic or successfully starts generation.
- ✅ **CORS safe-mode** — CORS middleware now strips whitespace, drops empty entries, and auto-disables `allow_credentials` when the origin list is `*` (browsers reject the wildcard+credentials combination anyway). Emits a startup warning under wildcard so operators know to lock down for production. Verified admin login + `/auth/me` cookie flow still works.
- ✅ **Sentry-ready init** — lazy import behind `SENTRY_DSN` env var. When DSN is set + `sentry-sdk[fastapi]` is installed, it initialises Starlette + FastAPI integrations with `send_default_pii=False` and configurable `SENTRY_ENV` / `SENTRY_TRACES_RATE`. Gracefully warns and no-ops if SDK is missing so the app never fails to boot.
- ✅ **Referral Program (viral growth loop)** — 6-char OCR-safe codes (`_REFERRAL_ALPHABET` skips 0/1/O/I). On signup with valid `?ref=CODE` both referrer and referee get +3 credits (`REFERRAL_BONUS`). New endpoint `GET /api/referrals/me` returns `{code, share_url, invited_count, credits_earned, bonus_per_referral}`. Codes are generated lazily on first fetch/register so existing users are covered without a migration. New `ReferralPanel` component mounted on `Settings` page (Give/get card + copy/share buttons + live stats). Signup page shows a green "You're invited!" banner when `?ref=` is present. E2E verified: invited count `0→1`, earned `0→3`, referrer balance `10006→10009`, invalid codes silently skip bonus without erroring.
- 🔁 **Rebrand reverted** — user preferred to keep "AI Video Studio". All wordmarks, footers, browser title, OG/Twitter meta, share text, and backend FastAPI title restored to `AI Video Studio` across all 15 files. Zero residual Kadenza refs.
- ✅ **Referral share URL fix** — testing agent iter-28 flagged that `_referral_share_url` was returning the internal cluster hostname behind Kubernetes ingress. Now honours `X-Forwarded-Host` / `X-Forwarded-Proto` reverse-proxy headers (with `PUBLIC_APP_URL` env override as first choice, and `Host` header as fallback). Verified live: share URL now returns the public preview URL, so copied referral links actually work externally. All 10 pytest cases still green.
- ✅ **Low-Credit Referral Nudge** — new `<LowCreditNudge />` component on Dashboard shows only when `credits < 3` AND `plan === "free"` (targets the exact moment a user hits a dead-end). Amber-to-brand gradient card with gift icon, headline "Invite a friend, both of you get 3 credits", direct CTA to `/settings` (referral panel). Session-dismissible via `sessionStorage['avs_low_credit_nudge_dismissed_v1']`. E2E verified: appears for user with 1 credit on free plan, dismiss persists across reload, does NOT show for admin (business plan, 10k+ credits). Existing Dashboard search/filter/projects UI untouched.
- ✅ **Auto-Refill Delight Toast** — backend `apply_free_refill` now attaches a transient `refill_delta` on the returned user dict (not persisted) exactly once per calendar month. Dashboard picks it up via a `useEffect` and fires a Sonner toast — "*{n} free credits refilled — enjoy!*" with a Sparkles icon. Toast fires exactly once per session (setUser clears the flag). E2E verified: `credits 0→3, refill_delta:2` on first login of a new month, subsequent `/auth/me` returns no `refill_delta` (idempotent). Turns a silent backend event into a moment of delight that pulls free users back to create.
- ✅ **Video Ready Toast** — Dashboard's 4-second poll now diffs project statuses via a `prevStatusRef` Map. When any project transitions `generating → ready`, a "Video ready 🎬" success toast with green CheckCircle icon fires including an **Open** action button that navigates to `/project/{id}`. Symmetric error handling: `generating → error` shows a rose-red "Generation failed" toast with a **Review** action button. E2E verified: manually flipping `proj_a4b96fbf3aec` to `generating` then back to `ready` in mongo fires the toast on the next poll with correct title and CTA.
- ✅ **Admin Health Tile** — new `<HealthTile />` component mounted at the top of Admin > Overview. Polls `/api/health` every 15s (raw fetch for accurate ingress-inclusive latency), shows an overall status badge (green/amber/rose), individual dep dots (mongodb, ffmpeg, llm_key), response latency in ms, and a "Last checked …" timestamp. **Caught a real ops issue on first use**: flagged that `ffmpeg` was missing from the container (recurring bug per handoff summary). Reinstalled `ffmpeg` (apt-get) — tile now reads `ALL SYSTEMS OPERATIONAL` / 103ms. Unblocks the video composition pipeline.
- ✅ **FFmpeg Self-Heal button** — new admin-only endpoint `POST /api/admin/repair/ffmpeg` runs `apt-get install -y ffmpeg` in a 90s-guarded subprocess (idempotent — returns `already_installed` if present), logs the admin email on success. HealthTile shows a `Repair ffmpeg` button only when the check is failing; on click, it fires a toast, refreshes the tile, and the button vanishes. Verified full loop: uninstalled ffmpeg → button appeared → clicked → apt-get ran (~1.6s) → tile flipped to green → button hid. Auth hardened: 403 for regular users, 401 for anonymous. Turns the recurring ffmpeg-drop into a one-click fix.
- ✅ **Boot Self-Heal for ffmpeg** — FastAPI startup event now checks `shutil.which("ffmpeg")` and, if missing, kicks off a fire-and-forget `asyncio.create_task` that runs `apt-get install -y ffmpeg` via `asyncio.to_thread` (180s timeout). Startup itself never blocks. Verified: uninstalled ffmpeg → restarted backend → health returned `status:ok, ffmpeg:ok` within 2s of first request; startup log shows `WARNING Boot self-heal: ffmpeg missing → INFO Boot self-heal: ffmpeg reinstalled → /bin/ffmpeg` (1.37s elapsed). Admins will no longer see the DEGRADED state after container restarts — the manual Repair button remains as a fallback for future issues.
- ✅ **Referral Admin Rollup** — `GET /api/admin/stats` now includes a `referral` block: `{users_with_code, total_referred, referred_24h, conversion_pct, top_referrers[top-5]}`. New "Referral program · Invite-loop health" section on the Admin Overview shows conversion rate (e.g. `28.6% signup→referred rate`), three summary cards (referred signups, referred·24h, top inviter with code + count), and a top-5 leaderboard when there are multiple inviters. Business-value: at-a-glance answer to "is my referral program actually driving growth?" without querying mongo. E2E verified against admin@videostudio.ai with live data (4 referred out of 14 coded users = 28.6%).
- ✅ **Iter-29 regression + async subprocess fix** — Testing agent iter-29 came back **100% clean, 0 bugs, 13/13 items green**. Follow-up: wrapped the admin `/api/admin/repair/ffmpeg` `subprocess.run` in `asyncio.to_thread` so a slow apt-get no longer blocks the FastAPI event loop (the code review had flagged this). Combined pytest suite (iter-28 + iter-29) = **20/20 pass in 5.0s**.
- ✅ **Referral Panel social share buttons** — new one-click share pills on `<ReferralPanel />` for X/Twitter, LinkedIn and WhatsApp (data-testid=referral-social-{twitter,linkedin,whatsapp}). Each opens in a new tab pre-filled with platform-tuned copy + the user's `share_url`. Uses tasteful hover-fill in each network's brand color. Purely additive to the existing Copy/Share buttons.
- ✅ **Dashboard Download + Thumbnail buttons + latent media-URL bug fix** — added two new icon actions on READY cards: `Download video (MP4)` (data-testid=download-video-{id}) and `Download thumbnail (PNG)` (data-testid=download-thumb-{id}). Filenames auto-derived from the project title (sanitized to `_`). While wiring these up, discovered the DB stores legacy `/media/*` paths on older projects while the backend serves at `/api/media/*` — the cover `<img>` on Dashboard cards AND the `Download` button on ProjectView were both silently broken (returning HTML instead of the media). Fixed by centralizing `resolveMediaUrl(path)` in `/app/frontend/src/lib/api.js` that transparently prefixes `/api` when missing and passes through absolute URLs. Verified: video URL now returns `200 video/mp4`, thumbnail returns `200 image/png`, and the coffee-farm cover image now actually renders on the Dashboard READY card.
- ✅ **Multi-Format Download dropdown** — when a project has multiple aspect-ratio outputs (`video_urls: {landscape, portrait, square}`), the Download icon becomes a Shadcn dropdown showing all three: **YouTube (16:9)**, **Reels · TikTok · Shorts (9:16)**, **Instagram feed (1:1)**. Filenames tagged per format (`{safe_title}_landscape.mp4` etc). Falls back to the single icon for legacy single-format projects. E2E verified: dropdown opens correctly, all 3 formats show, filenames include the aspect tag, cleanup left the project unchanged.
- ✅ **Iter-30 pytest regression suite** — new `tests/test_iter30_downloads_and_media.py` guards the media mount + downloads. 8 test cases: `/api/media/` bogus paths return 404 (not React HTML), `.mp4` requests return `video/*` content-type, `.png` requests return `image/*`, ready projects expose either `video_url` or `video_urls`, projects endpoint keeps stable `{id, status}` shape, health endpoint reports ffmpeg=ok, admin `/repair/ffmpeg` is idempotent when installed, and requires admin auth (401 on fresh client). Combined suite (iter-28 + iter-29 + iter-30) = **28/28 pass in 7.75s**.
- ✅ **Quick Preview modal on Dashboard** — new Play (⏵) icon on READY project cards (data-testid=preview-{id}) opens a Shadcn Dialog with the project title + metadata, an inline `<video controls autoPlay>` playing the video via `resolveMediaUrl`, and a footer with "Open full project →" link + a **Download** CTA. Reuses the media URL helper so it handles legacy `/media/*` and new `/api/media/*` paths. Creators can watch their video in ~1 click without leaving the workspace. E2E verified: button present, modal opens with correct video src, download button navigates to correct MP4, close button restores dashboard.
- ✅ **Polish sweep: per-page browser titles + auth silencing** — audited all 9 public pages (Landing, Pricing, Terms, Privacy, 404, Login, Signup, Signup?ref=, Forgot). No broken images, no dead links, no visible error banners. Fixed the one real issue: every tab was showing the same title. Added `usePageTitle` hook in `/app/frontend/src/lib/usePageTitle.js` that sets `document.title` on mount and restores on unmount — wired into 8 pages (Landing keeps default full title, others show contextual titles like `Pricing · AI Video Studio`, `Terms of Service · AI Video Studio`, `404 — Page not found · AI Video Studio`, etc.). Big SEO + accessibility + browser-history win. Also silenced the console noise from `/auth/me` 401s on anonymous pages by adding `validateStatus: (s) => s < 500` to the axios call in `auth.jsx` — the raw HTTP-status log from the browser network layer still shows in DevTools (unavoidable and invisible to end users).
- ✅ **Landing page FAQ section** — new "*You're curious. That's fair.*" section with 7 pre-signup Q&As in a Shadcn Accordion (single-open, collapsible). Covers the objections that actually matter — pricing/credits math, no recording/footage needed, 16:9+9:16+1:1 formats + thumbnail, editable script/images/voice at each gate, video ownership + commercial use, generation time, API/team roadmap. Every answer is factually grounded against the current build (nothing fake). Anchor-linkable at `#faq` and reachable from a new footer link. Converts pre-signup friction into confidence.
- ✅ **Referral anti-farming daily cap** — `_apply_referral_bonus` now enforces `REFERRAL_DAILY_CAP=10`: a single referrer can only earn the +3 credit bonus for the first 10 referred signups in any rolling 24h window. Beyond that: the referee still gets their +3 welcome bonus and gets tagged with `referred_by` (so admin analytics still track the invite path), but the referrer's payout is skipped and the cap-hit event is logged. Combined with the existing IP register rate-limit (10/10min) this gives two-layer defense against credit farming without penalising legitimate viral growth. `28/28 pytest` still green.
- ✅ **Change Password in Settings** — new backend endpoint `POST /api/auth/change-password` (rate-limited 8/10min): validates current password, enforces 8-char minimum on new, hashes with bcrypt, **invalidates every existing session** (any stolen cookie is instantly dead), issues a fresh session for the current browser, logs the event for audit. Context-aware frontend card `<ChangePasswordCard />` mounted in Settings between Billing and Referral: for password users → "Change password" with current-password field, for Google-only accounts → "Set a password — You signed in with Google" with no current-password prompt. Includes show/hide toggle, confirm-match check, success toast. Verified 7 code paths end-to-end via curl (wrong current → 400, short new → 400, correct change → 200 + fresh cookie, old session → 401, new session → 200, login with new → 200, login with old → 401). Pytest 28/28 still green.
- ✅ **Full-system smoke test** — verified all 12 surfaces green in one pass: health/mongo/ffmpeg/llm_key, robots/sitemap, 7 public pages HTTP-200, admin auth + stats (30.6% referral conversion), referral endpoint returning public share URL, media mount, ffmpeg repair, change-password auth guards, and 28/28 pytest. Also patched `test_full_referral_flow_credits_both_sides` to handle the new `REFERRAL_DAILY_CAP=10` gracefully — the test now correctly accepts both under-cap (referrer +3) and at-cap (referee still credited, referrer skipped) outcomes so the suite stays green across repeated same-day runs.
- ✅ **Iter-31 change-password regression suite** — new `tests/test_iter31_change_password.py` with 5 cases guarding the security-critical endpoint: unauthenticated → 401, wrong current password → 400, short new password → 400, happy path invalidates old sessions but keeps the new session alive, and post-change login only works with the new password. Combined pytest across all 4 iterations = **33/33 pass in 10.6s**.




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
- ✅ Testing: iteration 19 (auth, 100% frontend / 86% backend rate-limit-noise) + iteration 20 (image/voice gates, 100% both) + iteration 21 (talking-head feature, 100% both) + iteration 22 (password reset + cleanup, 100% both)
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
- ✅ **Password Reset flow** (2026-07-23)
  - `POST /api/auth/forgot-password` — accepts email or mobile; email-enum-guarded (always returns 200 with generic message)
  - `POST /api/auth/reset-password` — token + new password → updates hash, invalidates ALL prior sessions (session-fixation defence), issues fresh session cookie (auto-login), marks token used
  - 1-hour token TTL, single-use, prior tokens invalidated on new request
  - Email delivery via Resend when `RESEND_API_KEY` env is set; otherwise logs the URL to backend console (dev fallback) — UI shows "Delivery: dev mode" hint
  - Rate limits: 5 forgot / 10 reset per IP per 10 min
  - Frontend: `/forgot-password` and `/reset-password` pages + "Forgot password?" link on Login
- ✅ **Nightly Cleanup Job** (2026-07-23)
  - Runs daily at 03:00 IST via APScheduler
  - Purges abandoned draft projects (>24h, status='draft', no scenes)
  - Purges expired password reset tokens + used tokens >7d old
  - Purges orphan character portrait files (no matching project in DB)
- ✅ **Public Share Links** (2026-07-23)
  - `POST /api/projects/{id}/share` — creates 10-char slug for status='ready' project (idempotent)
  - `DELETE /api/projects/{id}/share` — disables slug (kept reserved for later re-enable)
  - `GET /api/public/videos/{slug}` — public, no auth, safe projection only, rate-limited 120/min per IP, increments view counter
  - Frontend: new `/v/:slug` public page (dark hero, video player, 3 signup CTAs) + Share modal on ProjectView with copy-link + Twitter/WhatsApp/LinkedIn/Email socials
  - Iteration 23: 100% backend (11/11) + 100% frontend
- ✅ **Pricing transparency rebuild** (2026-07-23)
  - Interactive Credit Calculator: 8 duration chips → all 4 plan cards live-update with exact video counts
  - Full Pack × Duration matrix table (8 durations × 4 packs) with per-video cost + best-for use case
  - Free plan explicitly shows `—` for non-30s durations (transparent about the free-tier limit)
  - "See exactly what you get ↓" scroll link on paid cards → jumps to calculator
  - Iteration 24: 97% pass (63/65) — no bugs, 2 non-passes were test-env artifacts
- ✅ **Global Upgrade Modal + Structured 402s + Dashboard Rename/Duplicate** (2026-07-23)
  - Backend: New `PaymentRequiredError` class returns 402 with machine-readable detail: `{message, code, upgrade_url, ...}`. Two codes: `paid_feature_required` (with `feature`) and `insufficient_credits` (with `needed`, `have`, `duration_sec`)
  - Frontend: Axios response interceptor catches every 402 and dispatches a `paywall:open` window event
  - New `<UpgradeModal>` component mounted at App root — two variants: (a) "Almost there / You need X credits" with a mini plan strip, (b) "Pro plan required / Unlock Pro features" with benefit bullets
  - Wizard's local Talking-Head upsell replaced with the unified global modal (single source of truth)
  - Backend: `PATCH /api/projects/{id}/title` — rename works in any status; `POST /api/projects/{id}/duplicate` — creates a fresh draft with same settings, empty scenes; copies the character portrait file to a new pid-keyed path so source deletion doesn't break the duplicate; enforces paid-plan gate + credit balance via structured 402s
  - Frontend: Dashboard cards have hover-revealed rename pencil + inline input with Enter/Escape/save/cancel; duplicate icon in every card footer
  - Iteration 25: 100% backend (13/13) + 100% frontend (10/10)
- ✅ **Dashboard Search + Status Filter** (2026-07-23)
  - Client-side search box (title/topic/style/language) with clear button
  - Status filter chips (All / Drafts / Generating / Ready / Failed) with per-status counts
  - Empty statuses render disabled chips so users see the whole taxonomy at a glance
  - "Showing X of Y matching …" summary line + no-match empty state with Reset Filters button
  - Zero backend changes — all filtering is memoised client-side for instant response
- ✅ **Share Analytics for Creators** (2026-07-23)
  - Every `/v/:slug` view now inserts a `share_events` doc with referrer host + coarse UA bucket (mobile / desktop / bot_preview / unknown)
  - `GET /projects/{id}/share/analytics` returns {total_views, last_viewed_at, 14-day timeline, top-6 referrers, ua_breakdown}
  - Referrer parser strips `www.`/`m.`/`mobile.` prefixes and treats own-domain hits as `direct`
  - Frontend: Share modal on ProjectView now has 2 tabs — "Share link" (existing) and "Insights" — with total-views card, 14-day CSS bar chart, top-referrer bars with %, and device pill chips
- ✅ **Landing Integrity Audit** (2026-07-23)
  - **Duration chips**: converted from decorative `<div>` to real `<button>` — clicking now navigates to `/signup` with tracked chip source
  - **"Watch 60-second demo" button**: renamed to **"See what you get"** — previously scrolled to a broken `<DemoVideoSection>` where the play button silently did nothing (missing `videoSrc` prop)
  - **DemoVideoSection rewritten** as a self-contained "Sample storyboard" — 6-panel gradient grid showing Scene 1-5 + Export card + the outputs-grid; no video element, no broken play button, no misleading affordance
  - **Footer mailto removed**: was `mailto:hello@videostudio.ai` (dead domain); replaced with 3 real Router links (Pricing / Log in / Sign up)
  - Iteration 27: 100% frontend regression pass, zero console errors on desktop + mobile viewports
- ✅ **Launch-Readiness Pack** (2026-07-23)
  - `/terms` — 10-section Terms of Service (account, usage, content ownership + rights grant on public shares, AI limitations, refunds, termination, updates policy)
  - `/privacy` — 9-section Privacy Policy (data collection scope, explicit "we do NOT collect" list, third-party processors, retention windows including 24h draft cleanup, GDPR rights)
  - `/404` catch-all `<NotFound>` — clean brand-consistent page with dashboard/home fallback CTAs
  - Landing footer expanded to 5 links: Pricing / Log in / Sign up / Terms / Privacy
  - Signup page shows inline "By creating an account, you agree to our Terms and Privacy Policy"
  - HTML `<head>` meta cleaned: dropped stale "private beta" copy, added canonical URL + robots + author + freemium-accurate og:description/twitter:description

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
