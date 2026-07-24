import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import usePageTitle from "@/lib/usePageTitle";
import { Check, Sparkles, Zap, Rocket, Building2, Calculator } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TopBar } from "@/components/Layout";
import { track } from "@/lib/analytics";

const PLANS = [
  {
    id: "free",
    icon: Sparkles,
    name: "Free",
    price: "$0",
    tagline: "One 30-second video every month, forever",
    credits: "3 credits / month",
    creditsNum: 3,
    refill: "= 1 × 30-second video every month",
    cta: "Get started free",
    features: [
      "1 × 30-second video every month",
      "Guided script → visuals → voice",
      "16:9 + 9:16 formats included",
      "Standard queue",
      "MP4 download",
    ],
    highlight: false,
    color: "border-ink-200",
  },
  {
    id: "starter",
    icon: Zap,
    name: "Starter Pack",
    price: "$10",
    tagline: "One-time top-up. Credits never expire.",
    credits: "60 credits",
    creditsNum: 60,
    cta: "Buy 60 credits",
    features: [
      "Everything in Free",
      "Any duration 30 sec → 10 min",
      "Priority queue",
      "Email support",
      "Credits never expire",
    ],
    highlight: false,
    color: "border-ink-200",
  },
  {
    id: "creator",
    icon: Rocket,
    name: "Creator Pack",
    price: "$25",
    tagline: "Most popular · +10% bonus credits",
    credits: "175 credits",
    creditsNum: 175,
    cta: "Buy 175 credits",
    features: [
      "Everything in Starter",
      "10% bonus credits",
      "HD downloads",
      "Brand watermark toggle",
      "Priority support",
    ],
    highlight: true,
    color: "border-brand-600 ring-2 ring-brand-600/20",
  },
  {
    id: "pro",
    icon: Building2,
    name: "Pro Pack",
    price: "$50",
    tagline: "Best value · +20% bonus credits",
    credits: "400 credits",
    creditsNum: 400,
    cta: "Buy 400 credits",
    features: [
      "Everything in Creator",
      "20% bonus credits",
      "Faster generation",
      "1-hour support SLA",
      "Volume-discount pricing",
    ],
    highlight: false,
    color: "border-ink-200",
  },
];

// Single source of truth for duration → credit mapping (matches backend DURATION_TIERS)
const DURATIONS = [
  { sec: 30,  label: "30 sec",  credits: 3,  bestFor: "Instagram Stories, TikTok teasers", usd: "$0.60" },
  { sec: 45,  label: "45 sec",  credits: 4,  bestFor: "LinkedIn feed videos",              usd: "$0.80" },
  { sec: 60,  label: "60 sec",  credits: 5,  bestFor: "Instagram Reels, YouTube Shorts",   usd: "$1.00" },
  { sec: 90,  label: "90 sec",  credits: 7,  bestFor: "X/Twitter video posts",             usd: "$1.40" },
  { sec: 120, label: "2 min",   credits: 10, bestFor: "Product demos",                     usd: "$2.00" },
  { sec: 180, label: "3 min",   credits: 15, bestFor: "Deep explainers",                   usd: "$3.00" },
  { sec: 300, label: "5 min",   credits: 25, bestFor: "Tutorials, walkthroughs",           usd: "$5.00" },
  { sec: 600, label: "10 min",  credits: 50, bestFor: "Long-form YouTube",                 usd: "$10.00" },
];

const AGENCY = {
  name: "Agency Pack",
  price: "$200",
  credits: "2000 credits + team seats",
  bonus: "+25% bonus credits",
  features: [
    "Team collaboration",
    "White-label export",
    "API access",
    "Dedicated Slack channel",
    "Custom onboarding",
  ],
};

export default function Pricing() {
  usePageTitle("Pricing");
  const navigate = useNavigate();
  const [pickedSec, setPickedSec] = useState(30);
  useEffect(() => { track("page_view", { page: "pricing" }); }, []);

  const pickedDuration = DURATIONS.find((d) => d.sec === pickedSec) || DURATIONS[0];

  const onPlan = (plan) => {
    track("pricing_click", { plan });
    // All CTAs currently route to signup — checkout hooks come with Stripe later
    navigate("/signup");
  };

  return (
    <div className="min-h-screen bg-white text-ink-900">
      <TopBar />

      {/* HERO */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 pt-14 sm:pt-20 pb-6">
        <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Pricing</div>
        <h1 className="mt-2 font-heading font-black text-4xl sm:text-6xl tracking-tighter max-w-4xl">
          Credits, not subscriptions.
        </h1>
        <p className="mt-4 text-ink-500 text-base sm:text-lg max-w-2xl">
          Start free with one 30-second video every month. Top up when you need more — credits never expire and you only pay for what you actually generate.
        </p>
      </section>

      {/* PLAN GRID */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-5">
          {PLANS.map((p) => (
            <div key={p.id}
              className={`relative rounded-3xl bg-white border ${p.color} p-6 flex flex-col`}
              data-testid={`plan-${p.id}`}>
              {p.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand-600 text-white text-[10px] uppercase tracking-widest font-bold px-3 py-1">
                  Most popular
                </div>
              )}
              <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-700 flex items-center justify-center">
                <p.icon className="w-5 h-5" />
              </div>
              <div className="mt-4 font-heading font-bold text-lg">{p.name}</div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="font-heading font-black text-4xl tracking-tighter">{p.price}</span>
                {p.id === "free" && <span className="text-xs text-ink-500">/ month</span>}
                {p.id !== "free" && <span className="text-xs text-ink-500">one-time</span>}
              </div>
              <div className="mt-1 text-xs text-ink-500">{p.tagline}</div>
              <div className="mt-4 rounded-xl bg-brand-50 border border-brand-100 px-3 py-2">
                <div className="text-xs uppercase tracking-widest text-brand-700 font-semibold">{p.credits}</div>
                {p.id === "free" ? (
                  <div className="text-xs text-ink-500 mt-0.5">{p.refill}</div>
                ) : (
                  <a href="#calculator"
                     onClick={() => track("pricing_scroll_calc", { plan: p.id })}
                     className="text-xs text-brand-600 hover:text-brand-700 font-semibold mt-0.5 inline-block"
                     data-testid={`plan-calc-link-${p.id}`}>
                    See exactly what you get ↓
                  </a>
                )}
              </div>
              <ul className="mt-5 space-y-2 text-sm text-ink-700 flex-1">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2">
                    <Check className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" /> {f}
                  </li>
                ))}
              </ul>
              <Button
                onClick={() => onPlan(p.id)}
                className={`mt-6 w-full rounded-full h-11 font-semibold ${p.highlight ? "bg-brand-600 hover:bg-brand-700 text-white" : "bg-ink-900 hover:bg-ink-800 text-white"}`}
                data-testid={`plan-cta-${p.id}`}>
                {p.cta}
              </Button>
            </div>
          ))}
        </div>
      </section>

      {/* AGENCY BANNER */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <div className="rounded-3xl bg-gradient-to-br from-ink-900 via-brand-700 to-violet-600 text-white p-8 sm:p-10" data-testid="agency-banner">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-xl">
              <div className="text-xs uppercase tracking-widest opacity-80 font-semibold">{AGENCY.name}</div>
              <div className="mt-1 font-heading font-black text-3xl sm:text-4xl tracking-tighter">
                {AGENCY.price} <span className="text-lg opacity-80">one-time</span>
              </div>
              <div className="mt-1 text-white/80 text-sm">{AGENCY.credits} · {AGENCY.bonus}</div>
              <ul className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
                {AGENCY.features.map((f) => (
                  <li key={f} className="flex items-center gap-2">
                    <Check className="w-4 h-4 shrink-0" /> {f}
                  </li>
                ))}
              </ul>
            </div>
            <Button onClick={() => onPlan("agency")}
              className="rounded-full bg-white text-ink-900 hover:bg-white/90 h-11 px-6 font-semibold"
              data-testid="plan-cta-agency">
              Talk to sales
            </Button>
          </div>
        </div>
      </section>

      {/* INTERACTIVE CREDIT CALCULATOR */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-12" id="calculator">
        <div className="flex items-center gap-2 text-brand-600">
          <Calculator className="w-4 h-4" />
          <div className="text-xs uppercase tracking-widest font-semibold">Credit calculator</div>
        </div>
        <h2 className="mt-2 font-heading font-extrabold text-2xl sm:text-3xl tracking-tighter">
          Pick a duration — see exactly what each pack gets you.
        </h2>
        <p className="mt-2 text-ink-500 text-sm max-w-2xl">
          No math required. Tap a duration below and every plan card updates with the exact number of videos you can generate.
        </p>

        {/* Duration chip picker */}
        <div className="mt-6 flex flex-wrap gap-2" data-testid="calc-duration-picker">
          {DURATIONS.map((d) => {
            const active = pickedSec === d.sec;
            return (
              <button key={d.sec}
                type="button"
                onClick={() => { setPickedSec(d.sec); track("calc_duration_pick", { sec: d.sec }); }}
                data-testid={`calc-duration-${d.sec}`}
                className={[
                  "rounded-xl border px-4 py-2.5 text-left transition-all",
                  active
                    ? "bg-brand-600 border-brand-600 text-white shadow-lg shadow-brand-600/20"
                    : "bg-white border-ink-200 hover:border-brand-600 hover:shadow-sm text-ink-900",
                ].join(" ")}>
                <div className={`font-heading font-bold text-sm leading-none ${active ? "text-white" : "text-ink-900"}`}>{d.label}</div>
                <div className={`mt-1 text-[10px] uppercase tracking-widest font-semibold ${active ? "text-white/70" : "text-ink-400"}`}>
                  {d.credits} credits
                </div>
              </button>
            );
          })}
        </div>

        {/* Selected duration summary */}
        <div className="mt-5 rounded-2xl bg-brand-50 border border-brand-100 p-4 flex flex-wrap items-center gap-3 text-sm" data-testid="calc-selected-summary">
          <div className="font-semibold text-brand-900">Selected:</div>
          <div className="font-heading font-bold text-ink-900">{pickedDuration.label}</div>
          <span className="text-ink-400">·</span>
          <div className="font-mono font-bold text-brand-700">{pickedDuration.credits} credits / video</div>
          <span className="text-ink-400">·</span>
          <div className="text-ink-500">Best for: {pickedDuration.bestFor}</div>
        </div>

        {/* Pack payoff cards */}
        <div className="mt-6 grid md:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="calc-pack-payoff">
          {PLANS.map((p) => {
            const videos = Math.floor(p.creditsNum / pickedDuration.credits);
            const remainder = p.creditsNum % pickedDuration.credits;
            return (
              <div key={p.id}
                className={`rounded-2xl border p-5 ${p.highlight ? "border-brand-600 bg-brand-50/40" : "border-ink-200 bg-white"}`}
                data-testid={`calc-payoff-${p.id}`}>
                <div className="flex items-center gap-2">
                  <p.icon className="w-4 h-4 text-brand-600" />
                  <div className="text-xs uppercase tracking-widest text-brand-700 font-semibold">{p.name}</div>
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="font-heading font-black text-4xl tracking-tighter text-ink-900" data-testid={`calc-count-${p.id}`}>{videos}</span>
                  <span className="text-sm text-ink-500">{videos === 1 ? "video" : "videos"}</span>
                </div>
                <div className="mt-1 text-xs text-ink-500">
                  at {pickedDuration.label} each
                  {remainder > 0 && <> · <span className="text-ink-400">({remainder} credits left over)</span></>}
                </div>
                <div className="mt-3 pt-3 border-t border-ink-100 text-xs text-ink-500">
                  <span className="font-semibold text-ink-700">{p.credits}</span> · <span className="font-mono">{p.price}</span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* FULL MATRIX — every pack × every duration */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Full transparency</div>
        <h2 className="mt-2 font-heading font-extrabold text-2xl sm:text-3xl tracking-tighter">
          Every pack × every duration
        </h2>
        <p className="mt-2 text-ink-500 text-sm max-w-2xl">
          The complete lookup — number of videos you can generate from each pack at every supported duration. Credit cost + approx. USD cost per video shown for clarity.
        </p>
        <div className="mt-6 rounded-2xl border border-ink-200 overflow-x-auto" data-testid="duration-cost-table">
          <table className="w-full text-sm">
            <thead className="bg-ink-50 text-ink-500 uppercase tracking-widest text-xs">
              <tr>
                <th className="text-left px-4 py-3 font-semibold sticky left-0 bg-ink-50">Duration</th>
                <th className="text-right px-4 py-3 font-semibold">Credits</th>
                <th className="text-right px-4 py-3 font-semibold">Cost / video</th>
                {PLANS.map((p) => (
                  <th key={p.id} className="text-right px-4 py-3 font-semibold whitespace-nowrap">
                    {p.name}
                    <div className="text-[10px] text-ink-400 font-normal normal-case tracking-normal mt-0.5">{p.credits}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {DURATIONS.map((d) => (
                <tr key={d.sec} className="border-t border-ink-100 hover:bg-brand-50/30 transition-colors" data-testid={`dur-row-${d.label.replace(" ","-")}`}>
                  <td className="px-4 py-3 font-semibold sticky left-0 bg-white">
                    {d.label}
                    <div className="text-[11px] text-ink-400 font-normal mt-0.5">{d.bestFor}</div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-brand-700 font-bold">{d.credits}</td>
                  <td className="px-4 py-3 text-right text-ink-500 font-mono">{d.usd}</td>
                  {PLANS.map((p) => {
                    const videos = Math.floor(p.creditsNum / d.credits);
                    return (
                      <td key={p.id} className="px-4 py-3 text-right font-mono"
                          data-testid={`matrix-${p.id}-${d.sec}`}>
                        {p.id === "free" && d.sec !== 30 ? (
                          <span className="text-ink-300">—</span>
                        ) : (
                          <>
                            <span className={`font-bold ${videos > 0 ? "text-ink-900" : "text-ink-400"}`}>{videos}</span>
                            <span className="text-ink-400 text-[11px] ml-1">×</span>
                          </>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-xs text-ink-500">
          All prices in USD. Every generation includes both 16:9 (YouTube/Web) and 9:16 (LinkedIn/Reels) exports at no extra credits. Free plan is limited to 30-sec videos only — upgrade to any pack for full duration access.
        </p>
      </section>

      {/* FAQ */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 py-16 sm:py-20">
        <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">FAQ</div>
        <h2 className="mt-2 font-heading font-extrabold text-2xl sm:text-3xl tracking-tighter">Frequently asked</h2>
        <div className="mt-8 space-y-4">
          {[
            {q: "Do free credits really refill every month?",
             a: "Yes. On the first day of each calendar month, every free account is topped up to at least 3 credits — enough for exactly one 30-second video. No card required, ever."},
            {q: "Do purchased credits expire?",
             a: "No. Any credits you buy stay in your account until you use them. If you pause for a few months, they wait patiently."},
            {q: "Can I edit the script or regenerate images?",
             a: "Absolutely. Each project moves through 3 approval steps: script, visuals, voice. You can edit or regenerate at any step before the final video is rendered."},
            {q: "What formats do I get?",
             a: "Every render produces both 16:9 (1920×1080, for YouTube and web) and 9:16 (1080×1920, for LinkedIn, Instagram Reels, YouTube Shorts and TikTok). No extra credits."},
            {q: "How do I pay?",
             a: "Credit packs are one-time purchases via secure checkout. Refunds available within 14 days if you haven't used the credits."},
          ].map((f) => (
            <div key={f.q} className="rounded-2xl border border-ink-200 bg-white p-5" data-testid="faq-item">
              <div className="font-heading font-bold">{f.q}</div>
              <div className="mt-1 text-sm text-ink-500">{f.a}</div>
            </div>
          ))}
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-ink-100 py-8">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-wrap items-center justify-between gap-3 text-sm text-ink-500">
          <div>© {new Date().getFullYear()} AI Video Studio</div>
          <div className="flex items-center gap-5">
            <Link to="/" className="hover:text-brand-600">Home</Link>
            <a href="mailto:hello@videostudio.ai" className="hover:text-brand-600">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
