import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import usePageTitle from "@/lib/usePageTitle";
import { Check, Sparkles, Zap, Rocket, Building2, Calculator, ShieldCheck, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TopBar } from "@/components/Layout";
import { track } from "@/lib/analytics";
import { api } from "@/lib/api";

// Pricing tiles + duration calculator. All numbers are pulled from
// /api/pricing/config so backend + frontend can never drift.
const FALLBACK_PLANS = [
  { id: "free",     name: "Free",     price_inr: 0,     credits: 5,    tagline: "1 × 30-sec video every month" },
  { id: "starter",  name: "Starter",  price_inr: 499,   credits: 10,   tagline: "2 × 30-sec videos or 1 × 60-sec video every month" },
  { id: "creator",  name: "Creator",  price_inr: 1999,  credits: 50,   tagline: "10 × 30-sec videos or ~5 mins of slideshow" },
  { id: "business", name: "Business", price_inr: 6999,  credits: 200,  tagline: "Unlocks premium AI video + higher volume", popular: true },
  { id: "agency",   name: "Agency",   price_inr: 24999, credits: 800,  tagline: "Multi-workspace + priority support" },
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
const inr = (n) => n.toLocaleString("en-IN");

export default function Pricing() {
  usePageTitle("Pricing");
  const navigate = useNavigate();
  const [plans, setPlans] = useState(FALLBACK_PLANS);
  const [durations, setDurations] = useState(FALLBACK_DURATIONS);
  const [topup, setTopup] = useState({ price_inr: 1999, credits: 500, label: "Credit Top-Up Pack" });
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

  return (
    <div className="min-h-screen bg-white">
      <TopBar />
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-14">
        {/* Header */}
        <div className="text-center max-w-2xl mx-auto">
          <div className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 text-brand-700 border border-brand-200 px-3 py-1 text-[11px] font-bold uppercase tracking-widest">
            <ShieldCheck className="w-3.5 h-3.5" /> Early-Access Pricing
          </div>
          <h1 className="mt-4 font-heading text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter text-ink-900">
            Pay only for what you generate.
          </h1>
          <p className="mt-4 text-base sm:text-lg text-ink-500">
            One credit-based economy for every video. Your credits never expire, and you always know exactly what a video will cost before you hit generate.
          </p>
        </div>

        {/* Plan tiles */}
        <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4" data-testid="pricing-plans-grid">
          {plans.map((p) => {
            const Icon = PLAN_ICONS[p.id] || Sparkles;
            const isPopular = !!p.popular;
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
                <p className="mt-2 text-xs text-ink-500 leading-relaxed">{p.tagline}</p>
                <ul className="mt-4 space-y-1.5 text-xs text-ink-600 flex-1">
                  <li className="flex items-start gap-1.5"><Check className="w-3.5 h-3.5 text-emerald-500 mt-0.5" /> Guided script → visuals → voice</li>
                  <li className="flex items-start gap-1.5"><Check className="w-3.5 h-3.5 text-emerald-500 mt-0.5" /> All aspect ratios (16:9, 9:16, 1:1)</li>
                  <li className="flex items-start gap-1.5"><Check className="w-3.5 h-3.5 text-emerald-500 mt-0.5" /> MP4 + thumbnail downloads</li>
                  {p.id !== "free" && <li className="flex items-start gap-1.5"><Check className="w-3.5 h-3.5 text-emerald-500 mt-0.5" /> Priority queue</li>}
                  {p.id === "business" && <li className="flex items-start gap-1.5"><Check className="w-3.5 h-3.5 text-emerald-500 mt-0.5" /> Premium AI video (Sora) unlock</li>}
                  {p.id === "agency" && <li className="flex items-start gap-1.5"><Check className="w-3.5 h-3.5 text-emerald-500 mt-0.5" /> Multi-workspace + team seats</li>}
                  {p.id === "agency" && <li className="flex items-start gap-1.5"><Check className="w-3.5 h-3.5 text-emerald-500 mt-0.5" /> Dedicated support channel</li>}
                </ul>
                <Button
                  onClick={() => { track("pricing_cta", { plan: p.id }); navigate(p.price_inr === 0 ? "/signup" : "/credits"); }}
                  className={`mt-5 rounded-full ${isPopular ? "bg-brand-600 hover:bg-brand-700 text-white" : "bg-ink-900 hover:bg-ink-800 text-white"}`}
                  data-testid={`plan-${p.id}-cta`}
                >
                  {p.price_inr === 0 ? "Get started free" : "Choose " + p.name}
                </Button>
              </div>
            );
          })}
        </div>

        {/* Top-up + Sora tooltip */}
        <div className="mt-6 rounded-2xl border border-ink-200 bg-ink-50/40 p-5 flex flex-wrap items-center justify-between gap-4" data-testid="topup-strip">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-brand-600 font-bold">Top-up any time</div>
            <div className="mt-1 text-lg font-semibold text-ink-900">
              {topup.label} — <span className="font-mono">{inr(topup.credits)}</span> credits for <span className="font-mono">₹{inr(topup.price_inr)}</span>
            </div>
            <div className="text-xs text-ink-500 mt-1">Credits never expire · works with every plan · buy as many packs as you need.</div>
          </div>
          <Link to="/credits">
            <Button className="rounded-full bg-brand-600 hover:bg-brand-700 text-white">Buy credits</Button>
          </Link>
        </div>

        {/* Duration calculator */}
        <div className="mt-12">
          <div className="flex items-center gap-2">
            <Calculator className="w-4 h-4 text-brand-600" />
            <div className="text-[11px] uppercase tracking-widest text-brand-600 font-bold">Credit Calculator</div>
          </div>
          <h2 className="mt-1 font-heading text-2xl font-black tracking-tighter">See what any video costs</h2>
          <p className="mt-1 text-sm text-ink-500 max-w-2xl">Pick a duration below to see the credit cost. Slideshow video is priced at ~100 credits/minute.</p>

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

          <div className="mt-5 rounded-2xl border border-ink-200 bg-white p-6 flex items-center justify-between flex-wrap gap-4">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-ink-500 font-bold">You picked</div>
              <div className="mt-1 font-heading text-3xl font-black tracking-tighter text-ink-900">{picked.label}</div>
              <div className="text-xs text-ink-500 mt-1">Best for {picked.bestFor}</div>
            </div>
            <div className="text-right">
              <div className="text-[10px] uppercase tracking-widest text-ink-500 font-bold">Cost</div>
              <div className="mt-1 font-heading text-3xl font-black tracking-tighter text-brand-700" data-testid="picked-credit-cost">
                {inr(picked.credits)} credits
              </div>
              <div className="text-xs text-ink-500 mt-1">≈ ₹{inr(Math.round(picked.credits * 4))} on the Creator plan</div>
            </div>
          </div>

          <div className="mt-4 rounded-xl bg-amber-50 border border-amber-200 p-4 flex items-start gap-3" data-testid="sora-tooltip">
            <Sparkles className="w-4 h-4 text-amber-700 mt-0.5" />
            <div className="text-xs text-amber-800">
              <span className="font-bold">Premium AI Video (Sora)</span> is a high-compute feature and consumes <span className="font-bold">200 credits per second</span> of footage. Unlocked on the Business plan and above.
            </div>
          </div>
        </div>

        {/* Waitlist CTA at the bottom — primary conversion for early access */}
        <div className="mt-14 rounded-2xl bg-gradient-to-br from-brand-600 to-indigo-700 text-white p-8 sm:p-10 text-center">
          <div className="text-[11px] uppercase tracking-widest text-white/80 font-bold">Early access</div>
          <h2 className="mt-2 font-heading text-3xl sm:text-4xl font-black tracking-tighter">Get in early — save 40% for life.</h2>
          <p className="mt-2 text-white/85 max-w-lg mx-auto">Join the waitlist to lock in early-access pricing and be first to try the new premium AI video generation.</p>
          <Link to="/signup" data-testid="pricing-waitlist-cta">
            <Button className="mt-5 rounded-full bg-white text-brand-700 hover:bg-white/90 font-bold px-6 h-11">
              Join waitlist <Zap className="w-4 h-4 ml-1.5" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
