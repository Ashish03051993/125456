import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Check, Sparkles, Zap, Rocket, Building2 } from "lucide-react";
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
    refill: "Auto-refills on the 1st",
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
    refill: "≈ 20 × 30-sec or 4 × 3-min videos",
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
    refill: "≈ 58 × 30-sec or 7 × 5-min videos",
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
    refill: "≈ 133 × 30-sec or 8 × 10-min videos",
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
  const navigate = useNavigate();
  useEffect(() => { track("page_view", { page: "pricing" }); }, []);

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
                <div className="text-xs text-ink-500 mt-0.5">{p.refill}</div>
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

      {/* PER-DURATION COST TABLE */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-12">
        <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Per-video cost</div>
        <h2 className="mt-2 font-heading font-extrabold text-2xl sm:text-3xl tracking-tighter">
          Credits by duration
        </h2>
        <div className="mt-6 rounded-2xl border border-ink-200 overflow-hidden" data-testid="duration-cost-table">
          <table className="w-full text-sm">
            <thead className="bg-ink-50 text-ink-500 uppercase tracking-widest text-xs">
              <tr>
                <th className="text-left px-4 py-3 font-semibold">Duration</th>
                <th className="text-right px-4 py-3 font-semibold">Credits</th>
                <th className="text-right px-4 py-3 font-semibold">Approx. cost</th>
                <th className="text-left px-4 py-3 font-semibold pl-6">Best for</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["30 sec",  3,  "$0.60", "Instagram Stories, TikTok teasers"],
                ["45 sec",  4,  "$0.80", "LinkedIn feed videos"],
                ["60 sec",  5,  "$1.00", "Instagram Reels, YouTube Shorts"],
                ["90 sec",  7,  "$1.40", "X/Twitter video posts"],
                ["2 min",  10,  "$2.00", "Product demos"],
                ["3 min",  15,  "$3.00", "Deep explainers"],
                ["5 min",  25,  "$5.00", "Tutorials, walkthroughs"],
                ["10 min", 50,  "$10.00", "Long-form YouTube"],
              ].map(([dur, cr, usd, best]) => (
                <tr key={dur} className="border-t border-ink-100" data-testid={`dur-row-${dur.replace(" ","-")}`}>
                  <td className="px-4 py-3 font-semibold">{dur}</td>
                  <td className="px-4 py-3 text-right font-mono text-brand-700 font-bold">{cr}</td>
                  <td className="px-4 py-3 text-right text-ink-500 font-mono">{usd}</td>
                  <td className="px-4 py-3 pl-6 text-ink-500">{best}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-xs text-ink-500">
          All prices in USD. Every generation includes both 16:9 (YouTube/Web) and 9:16 (LinkedIn/Reels) exports at no extra credits.
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
