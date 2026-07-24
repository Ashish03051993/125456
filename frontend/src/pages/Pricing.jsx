import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import usePageTitle from "@/lib/usePageTitle";
import { Check, X, Sparkles, Zap, Rocket, Building2, Calculator, ShieldCheck, Star, Info, CreditCard, RefreshCcw, Award, FileCheck, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TopBar } from "@/components/Layout";
import { track } from "@/lib/analytics";
import { api } from "@/lib/api";

// Pricing page — designed for full transparency. Every number, feature, and
// policy is exposed to the user. Backend `/api/pricing/config` is the single
// source of truth for plans + duration costs; fallbacks below mirror it so
// the page still renders during API downtime.
const FALLBACK_PLANS = [
  { id: "free",     name: "Free",     price_inr: 0,     credits: 5,    tagline: "Try the full flow — one video on us." },
  { id: "starter",  name: "Starter",  price_inr: 499,   credits: 10,   tagline: "Occasional creators. Warm-up plan." },
  { id: "creator",  name: "Creator",  price_inr: 1999,  credits: 50,   tagline: "Regular short-form content." },
  { id: "business", name: "Business", price_inr: 6999,  credits: 200,  tagline: "Unlocks premium AI video (Sora).", popular: true },
  { id: "agency",   name: "Agency",   price_inr: 24999, credits: 800,  tagline: "Teams, workspaces, priority support." },
];
const FALLBACK_DURATIONS = [
  { sec: 30,  credits: 5,   label: "30 sec",  bestFor: "Instagram Stories, TikTok teasers" },
  { sec: 45,  credits: 8,   label: "45 sec",  bestFor: "LinkedIn feed videos" },
  { sec: 60,  credits: 10,  label: "60 sec",  bestFor: "Instagram Reels, YouTube Shorts" },
  { sec: 90,  credits: 15,  label: "90 sec",  bestFor: "X/Twitter video posts" },
  { sec: 120, credits: 20,  label: "2 min",   bestFor: "Product demos" },
  { sec: 180, credits: 30,  label: "3 min",   bestFor: "Deep explainers" },
  { sec: 300, credits: 50,  label: "5 min",   bestFor: "Tutorials, walkthroughs" },
  { sec: 600, credits: 100, label: "10 min",  bestFor: "Long-form YouTube" },
];
const PLAN_ICONS = { free: Sparkles, starter: Zap, creator: Rocket, business: Star, agency: Building2 };

// Feature capability matrix — kept explicit so nothing is "surprise-locked".
const FEATURES = [
  { key: "wizard",       label: "Guided script → visuals → voice wizard",  all: true },
  { key: "aspects",      label: "All aspect ratios (16:9, 9:16, 1:1)",     all: true },
  { key: "download_mp4", label: "MP4 downloads + auto-thumbnail",           all: true },
  { key: "share",        label: "Public share link (/v/…)",                all: true },
  { key: "captions",     label: "Multi-language captions (10+ scripts)",   all: true },
  { key: "credit_expiry",label: "Credits never expire",                    all: true },
  { key: "no_watermark", label: "No watermark on video",                   plans: ["starter", "creator", "business", "agency"] },
  { key: "priority",     label: "Priority render queue",                   plans: ["creator", "business", "agency"] },
  { key: "talking_head", label: "Talking-head avatars",                    plans: ["creator", "business", "agency"] },
  { key: "sora",         label: "Premium AI video (Sora, 200 credits/sec)", plans: ["business", "agency"] },
  { key: "workspaces",   label: "Team workspaces + roles",                 plans: ["agency"] },
  { key: "support_sla",  label: "1-hour support SLA",                      plans: ["agency"] },
];

// What one credit actually pays for — no math hidden anywhere.
const WHAT_CREDITS_PAY_FOR = [
  { action: "Slideshow video generation",         cost: "~1 credit per 6 seconds (5 credits = 30-sec video)" },
  { action: "AI script writing (unlimited edits)", cost: "Free — included in every video generation" },
  { action: "AI image generation for scenes",     cost: "Free — included in every video generation" },
  { action: "AI voiceover (TTS, multi-voice)",    cost: "Free — included in every video generation" },
  { action: "Enhance-topic AI helper",            cost: "Free — no credits deducted" },
  { action: "Talking-head avatar (paid plans)",   cost: "Included in the video's credit cost" },
  { action: "Premium AI video (Sora)",            cost: "200 credits per second of footage" },
];

const inr = (n) => n.toLocaleString("en-IN");

export default function Pricing() {
  usePageTitle("Pricing");
  const navigate = useNavigate();
  const [plans, setPlans] = useState(FALLBACK_PLANS);
  const [durations, setDurations] = useState(FALLBACK_DURATIONS);
  const [topup, setTopup] = useState({ price_inr: 1999, credits: 50, label: "Credit Top-Up Pack" });
  const [pickedSec, setPickedSec] = useState(30);

  useEffect(() => {
    track("page_view", { page: "pricing" });
    api.get("/pricing/config").then(({ data }) => {
      if (Array.isArray(data.plans) && data.plans.length) setPlans(data.plans);
      if (Array.isArray(data.durations) && data.durations.length) setDurations(data.durations);
      if (data.topup) setTopup(data.topup);
    }).catch(() => {/* fall back to defaults */});
  }, []);

  const picked = durations.find((d) => d.sec === pickedSec) || durations[0];
  const planHas = (planId, featKey) => {
    const f = FEATURES.find((x) => x.key === featKey);
    if (!f) return false;
    if (f.all) return true;
    return (f.plans || []).includes(planId);
  };
  const perCreditInr = (p) => (p.credits > 0 && p.price_inr > 0 ? (p.price_inr / p.credits) : 0);

  return (
    <div className="min-h-screen bg-white">
      <TopBar />
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-14">

        {/* Header */}
        <div className="text-center max-w-2xl mx-auto">
          <div className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 text-brand-700 border border-brand-200 px-3 py-1 text-[11px] font-bold uppercase tracking-widest">
            <ShieldCheck className="w-3.5 h-3.5" /> Transparent Pricing · No Hidden Fees
          </div>
          <h1 className="mt-4 font-heading text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter text-ink-900">
            Simple, honest pricing.
          </h1>
          <p className="mt-4 text-base sm:text-lg text-ink-500">
            Every plan is credit-based, credits never expire, and every feature that requires a paid plan is clearly labelled below. Cancel any time — you keep every credit you've bought.
          </p>
        </div>

        {/* Trust badges strip */}
        <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="trust-badges">
          {[
            { Icon: ShieldCheck, title: "No hidden fees",        body: "One monthly price + optional top-ups. Nothing else." },
            { Icon: RefreshCcw,  title: "Cancel any time",       body: "Downgrade, pause, or cancel from Settings. Zero questions." },
            { Icon: Award,       title: "Credits never expire",  body: "Anything you've paid for stays yours forever." },
            { Icon: FileCheck,   title: "You own your videos",   body: "Full commercial rights. Yours to publish, sell, remix." },
          ].map((b) => (
            <div key={b.title} className="rounded-xl border border-ink-200 bg-white p-4">
              <b.Icon className="w-4 h-4 text-brand-600" />
              <div className="mt-2 text-sm font-bold text-ink-900">{b.title}</div>
              <div className="text-xs text-ink-500 mt-0.5 leading-snug">{b.body}</div>
            </div>
          ))}
        </div>

        {/* Plan tiles */}
        <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4" data-testid="pricing-plans-grid">
          {plans.map((p) => {
            const Icon = PLAN_ICONS[p.id] || Sparkles;
            const isPopular = !!p.popular;
            const per = perCreditInr(p);
            return (
              <div key={p.id}
                   className={`relative rounded-2xl border p-6 bg-white flex flex-col ${isPopular ? "border-brand-600 ring-2 ring-brand-600/20 shadow-lg shadow-brand-600/10" : "border-ink-200"}`}
                   data-testid={`plan-${p.id}`}>
                {isPopular && (
                  <div className="absolute -top-3 left-6 inline-flex items-center gap-1 rounded-full bg-brand-600 text-white text-[10px] font-bold px-3 py-1 uppercase tracking-widest">
                    Most popular
                  </div>
                )}
                <Icon className="w-6 h-6 text-brand-600" />
                <div className="mt-4 font-heading font-black text-xl text-ink-900">{p.name}</div>
                <div className="mt-2 flex items-end gap-1">
                  {p.price_inr === 0 ? (
                    <span className="font-heading text-4xl font-black tracking-tighter">Free</span>
                  ) : (
                    <>
                      <span className="text-lg font-bold text-ink-500">₹</span>
                      <span className="font-heading text-4xl font-black tracking-tighter">{inr(p.price_inr)}</span>
                      <span className="text-sm text-ink-500 mb-1">/mo</span>
                    </>
                  )}
                </div>
                <div className="mt-1 text-sm font-semibold text-brand-700">
                  {inr(p.credits)} credits{p.price_inr === 0 ? " / month" : " included"}
                </div>
                {per > 0 && (
                  <div className="text-[11px] text-ink-500 mt-0.5" data-testid={`plan-${p.id}-per-credit`}>
                    ₹{per.toFixed(2)} per credit
                  </div>
                )}
                <p className="mt-2 text-xs text-ink-500 leading-relaxed">{p.tagline}</p>
                <ul className="mt-4 space-y-1.5 text-xs text-ink-700 flex-1">
                  {FEATURES.map((f) => {
                    const has = planHas(p.id, f.key);
                    return (
                      <li key={f.key} className={`flex items-start gap-1.5 ${has ? "" : "opacity-45"}`}>
                        {has
                          ? <Check className="w-3.5 h-3.5 text-emerald-500 mt-0.5 shrink-0" />
                          : <X     className="w-3.5 h-3.5 text-ink-400 mt-0.5 shrink-0" />}
                        <span className={has ? "" : "line-through"}>{f.label}</span>
                      </li>
                    );
                  })}
                </ul>
                <Button
                  onClick={() => { track("pricing_cta", { plan: p.id }); navigate(p.price_inr === 0 ? "/signup" : "/credits"); }}
                  className={`mt-5 rounded-full ${isPopular ? "bg-brand-600 hover:bg-brand-700 text-white" : "bg-ink-900 hover:bg-ink-800 text-white"}`}
                  data-testid={`plan-${p.id}-cta`}
                >
                  {p.price_inr === 0 ? "Start free" : "Choose " + p.name}
                </Button>
              </div>
            );
          })}
        </div>

        {/* Top-up strip */}
        <div className="mt-6 rounded-2xl border border-ink-200 bg-ink-50/40 p-5 flex flex-wrap items-center justify-between gap-4" data-testid="topup-strip">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-brand-600 font-bold">Top-up any time</div>
            <div className="mt-1 text-lg font-semibold text-ink-900">
              {topup.label} — <span className="font-mono">{inr(topup.credits)}</span> credits for <span className="font-mono">₹{inr(topup.price_inr)}</span>
              <span className="text-sm text-ink-500 ml-2">(₹{(topup.price_inr / topup.credits).toFixed(2)} per credit)</span>
            </div>
            <div className="text-xs text-ink-500 mt-1">Credits never expire · works on every plan · buy as many packs as you need.</div>
          </div>
          <Link to="/credits">
            <Button className="rounded-full bg-brand-600 hover:bg-brand-700 text-white">Buy credits</Button>
          </Link>
        </div>

        {/* What credits actually pay for */}
        <div className="mt-14">
          <div className="text-[11px] uppercase tracking-widest text-brand-600 font-bold">Full credit transparency</div>
          <h2 className="mt-1 font-heading text-2xl sm:text-3xl font-black tracking-tighter">What one credit pays for</h2>
          <p className="mt-1 text-sm text-ink-500 max-w-2xl">Everything you see below is included in your credit cost. We don't charge for AI writing, image generation, or voice separately.</p>
          <div className="mt-4 rounded-2xl border border-ink-200 bg-white overflow-hidden" data-testid="credit-usage-table">
            <table className="w-full text-sm">
              <thead className="bg-ink-50/60 text-left">
                <tr>
                  <th className="px-4 py-3 text-xs uppercase tracking-widest text-ink-500 font-bold">Action</th>
                  <th className="px-4 py-3 text-xs uppercase tracking-widest text-ink-500 font-bold">Credit cost</th>
                </tr>
              </thead>
              <tbody>
                {WHAT_CREDITS_PAY_FOR.map((row) => (
                  <tr key={row.action} className="border-t border-ink-100">
                    <td className="px-4 py-3 text-ink-900">{row.action}</td>
                    <td className="px-4 py-3 text-ink-600 font-mono text-xs">{row.cost}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Duration calculator */}
        <div className="mt-14">
          <div className="flex items-center gap-2">
            <Calculator className="w-4 h-4 text-brand-600" />
            <div className="text-[11px] uppercase tracking-widest text-brand-600 font-bold">Credit Calculator</div>
          </div>
          <h2 className="mt-1 font-heading text-2xl sm:text-3xl font-black tracking-tighter">See what any video costs</h2>
          <p className="mt-1 text-sm text-ink-500 max-w-2xl">Pick a duration to see the exact credit cost + the ₹ equivalent on each paid plan. No surprises when you hit generate.</p>

          <div className="mt-4 flex flex-wrap gap-2" data-testid="duration-picker">
            {durations.map((d) => (
              <button key={d.sec}
                      onClick={() => setPickedSec(d.sec)}
                      className={`rounded-full px-4 py-2 text-sm font-semibold border transition-all
                                  ${pickedSec === d.sec ? "bg-brand-600 border-brand-600 text-white" : "bg-white border-ink-200 text-ink-700 hover:border-brand-300"}`}
                      data-testid={`duration-${d.sec}`}>
                {d.label}
              </button>
            ))}
          </div>

          <div className="mt-5 rounded-2xl border border-ink-200 bg-white p-6" data-testid="calc-result">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <div className="text-[10px] uppercase tracking-widest text-ink-500 font-bold">You picked</div>
                <div className="mt-1 font-heading text-3xl font-black tracking-tighter text-ink-900">{picked.label}</div>
                <div className="text-xs text-ink-500 mt-1">Best for {picked.bestFor}</div>
              </div>
              <div className="text-right">
                <div className="text-[10px] uppercase tracking-widest text-ink-500 font-bold">Credits used</div>
                <div className="mt-1 font-heading text-3xl font-black tracking-tighter text-brand-700" data-testid="picked-credit-cost">
                  {inr(picked.credits)} credits
                </div>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-ink-100 grid grid-cols-2 md:grid-cols-4 gap-3">
              {plans.filter((p) => p.price_inr > 0).map((p) => (
                <div key={p.id} className="text-center rounded-lg bg-ink-50/60 p-3">
                  <div className="text-[10px] uppercase tracking-widest text-ink-500 font-semibold">On {p.name}</div>
                  <div className="mt-1 font-heading font-black text-lg text-ink-900">
                    ₹{(perCreditInr(p) * picked.credits).toFixed(0)}
                  </div>
                  <div className="text-[10px] text-ink-500">per video</div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 rounded-xl bg-amber-50 border border-amber-200 p-4 flex items-start gap-3" data-testid="sora-tooltip">
            <Sparkles className="w-4 h-4 text-amber-700 mt-0.5" />
            <div className="text-xs text-amber-800">
              <span className="font-bold">Premium AI Video (Sora)</span> is priced separately at <span className="font-bold">200 credits per second</span> — a 10-second Sora clip = 2,000 credits. Only available on Business plan and above. Regular slideshow videos above already include everything (script + images + voice + captions) for the credit cost shown.
            </div>
          </div>
        </div>

        {/* Ethical / policy strip */}
        <div className="mt-14" data-testid="policy-strip">
          <div className="text-[11px] uppercase tracking-widest text-brand-600 font-bold">Our fair-use commitment</div>
          <h2 className="mt-1 font-heading text-2xl sm:text-3xl font-black tracking-tighter">The fine print, unhidden.</h2>
          <div className="mt-6 grid md:grid-cols-2 gap-4">
            {[
              { Icon: CreditCard, title: "How billing works", body: "You're billed monthly on the day you subscribe. Credits arrive instantly. If your card fails, we retry over 3 days and email you before pausing your plan — never a silent charge." },
              { Icon: RefreshCcw, title: "Cancel or downgrade", body: "Do it any time from Settings — takes effect at the end of your current billing cycle. Credits you've already earned stay in your account and remain usable forever." },
              { Icon: Award,      title: "Refund policy", body: "Since credits never expire and are consumable, we don't offer prorated cash refunds. If you're unhappy with a specific generation, contact support — we'll re-credit failed jobs within 24 hours." },
              { Icon: Lock,       title: "Your data & privacy", body: "Your prompts and generated videos are yours. We never train models on your prompts and never resell your data. Delete your account at any time to wipe everything." },
              { Icon: FileCheck,  title: "Commercial rights", body: "You own the full commercial rights to every video generated on paid plans. Free-tier videos are also yours to use, with a small unobtrusive credit line." },
              { Icon: Info,       title: "Fair-use rate limits", body: "Every plan has generous limits and a soft priority queue. Agency plan gets its own priority lane. Abuse (bots, scraped prompts, illegal content) leads to a warning + refund + closure." },
            ].map((p) => (
              <div key={p.title} className="rounded-2xl border border-ink-200 bg-white p-5">
                <p.Icon className="w-5 h-5 text-brand-600" />
                <div className="mt-3 font-heading font-bold text-ink-900">{p.title}</div>
                <p className="mt-1 text-sm text-ink-600 leading-relaxed">{p.body}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom CTA */}
        <div className="mt-14 rounded-2xl bg-gradient-to-br from-brand-600 to-indigo-700 text-white p-8 sm:p-10 text-center">
          <div className="text-[11px] uppercase tracking-widest text-white/80 font-bold">Early access</div>
          <h2 className="mt-2 font-heading text-3xl sm:text-4xl font-black tracking-tighter">Start with 5 free credits. No card.</h2>
          <p className="mt-2 text-white/85 max-w-lg mx-auto">Generate your first 30-second video in under 3 minutes — script, visuals, voice, all approved by you.</p>
          <Link to="/signup" data-testid="pricing-waitlist-cta">
            <Button className="mt-5 rounded-full bg-white text-brand-700 hover:bg-white/90 font-bold px-6 h-11">
              Get started free <Zap className="w-4 h-4 ml-1.5" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
