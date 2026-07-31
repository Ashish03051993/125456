import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import usePageTitle from "@/lib/usePageTitle";
import { Check, Sparkles, Zap, Rocket, Building2, Calculator, ShieldCheck, Star, CreditCard, Award, Package, Video, Image as ImageIcon, FileText, Mic, Film } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TopBar } from "@/components/Layout";
import { track } from "@/lib/analytics";
import { api } from "@/lib/api";
import { purchaseCreditPack } from "@/lib/razorpayCheckout";
import { toast } from "sonner";

// ContentOS AI · Two-part pricing model. Fallbacks mirror /api/pricing/config
// exactly so the page still renders during API downtime.
const FALLBACK_PLANS = [
  { id: "free",   name: "Free Preview", price_inr: 0,     credits: 50,   tagline: "Try one 30-sec slideshow video · no card" },
  { id: "basic",  name: "Basic Access", price_inr: 999,   credits: 50,   tagline: "1 Brand Kit · Standard voices · 50 credits bundled" },
  { id: "pro",    name: "Pro Studio",   price_inr: 3999,  credits: 250,  tagline: "5 Brand Kits · Premium voices · Sora unlocked · 250 credits bundled", popular: true },
  { id: "agency", name: "Agency OS",    price_inr: 14999, credits: 1000, tagline: "Unlimited Brand Kits · Multi-workspace · Priority support · 1,000 credits bundled" },
];
const FALLBACK_PACKS = [
  { id: "micro",  name: "Micro Pack",  price_inr:  999, credits:  100, tagline: "Top-up for ~1 minute of slideshow video" },
  { id: "growth", name: "Growth Pack", price_inr: 3999, credits:  500, tagline: "Best value for regular content", popular: true },
  { id: "power",  name: "Power Pack",  price_inr: 9999, credits: 1500, tagline: "Bulk savings for agencies + video-heavy months" },
];
const FALLBACK_USAGE = [
  { action: "Text-only post (LinkedIn / Blog)", credits: 10,  unit: "post" },
  { action: "AI image generation",              credits: 20,  unit: "image" },
  { action: "Slideshow video (Ken Burns)",      credits: 100, unit: "minute" },
  { action: "Cinematic AI video (Sora 2)",      credits: 20,  unit: "second" },
  { action: "Talking-head avatar (Phase 2)",    credits: 30,  unit: "second" },
];

const PLAN_ICONS = { free: Sparkles, basic: Zap, pro: Rocket, agency: Building2 };
const USAGE_ICONS = { post: FileText, image: ImageIcon, minute: Film, second: Video, avatar: Mic };

// Access-only feature matrix (what you get JUST by having the subscription —
// separate from usage credits). Kept intentionally short so the promise is clear.
const ACCESS_FEATURES = [
  { key: "brand_kits",   label: "Brand Kits (logo, colors, fonts)",
    free: "—", basic: "1", pro: "5", agency: "Unlimited" },
  { key: "voices",       label: "Voice library",
    free: "Standard", basic: "Standard", pro: "Premium", agency: "Premium + custom" },
  { key: "sora_access",  label: "Cinematic Sora 2 video",
    free: "Preview only", basic: "—", pro: "Yes", agency: "Yes" },
  { key: "workspaces",   label: "Team workspaces + roles",
    free: "—", basic: "—", pro: "—", agency: "Unlimited" },
  { key: "watermark",    label: "No watermark on video",
    free: "—", basic: "Yes", pro: "Yes", agency: "Yes" },
  { key: "support",      label: "Support SLA",
    free: "Community", basic: "Email · 48 hr", pro: "Email · 24 hr", agency: "Priority · 1 hr" },
];

const inr = (n) => (n || 0).toLocaleString("en-IN");

export default function Pricing() {
  usePageTitle("ContentOS AI · Pricing");
  const navigate = useNavigate();
  const [plans, setPlans] = useState(FALLBACK_PLANS);
  const [packs, setPacks] = useState(FALLBACK_PACKS);
  const [usage, setUsage] = useState(FALLBACK_USAGE);
  const [rzpEnabled, setRzpEnabled] = useState(false);
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    track("page_view", { page: "pricing" });
    api.get("/pricing/config").then(({ data }) => {
      if (Array.isArray(data.plans) && data.plans.length) setPlans(data.plans);
      if (Array.isArray(data.credit_packs) && data.credit_packs.length) setPacks(data.credit_packs);
      if (Array.isArray(data.usage_costs) && data.usage_costs.length) setUsage(data.usage_costs);
    }).catch(() => {/* fall back to defaults */});
    api.get("/payments/razorpay/config").then(({ data }) => {
      setRzpEnabled(!!data.enabled);
    }).catch(() => {});
  }, []);

  // --- Content Cost Estimator ---
  // User picks a mix of assets they want to produce → we sum the credits.
  const [est, setEst] = useState({ text: 0, image: 0, slideshowMin: 0, soraSec: 0 });
  const findCost = (unit) => usage.find((u) => u.unit === unit)?.credits || 0;
  const estimate = useMemo(() => {
    return (
      est.text          * findCost("post")   +
      est.image         * findCost("image")  +
      est.slideshowMin  * findCost("minute") +
      est.soraSec       * findCost("second")
    );
  }, [est, usage]);
  const perCreditInr = (p) => (p.credits > 0 && p.price_inr > 0 ? (p.price_inr / p.credits).toFixed(2) : "0");
  const cheapestPack = useMemo(() => {
    if (!estimate) return null;
    return [...packs].sort((a, b) => a.credits - b.credits).find((p) => p.credits >= estimate) || packs[packs.length - 1];
  }, [estimate, packs]);

  const goCheckout = async (id, kind) => {
    track("pricing_cta_click", { id, kind, rzp_enabled: rzpEnabled });
    // Payments still dormant → friendly toast, no redirect to a broken checkout page.
    if (!rzpEnabled) {
      toast.info("Payments launching soon", {
        description: "We're activating the payment gateway. Sign up free — we'll email you the moment checkout is live.",
      });
      navigate("/signup");
      return;
    }
    // Credit-pack path → Razorpay Checkout.js modal opens right here.
    if (kind === "pack") {
      setBusyId(id);
      try {
        await purchaseCreditPack({ packId: id });
      } catch (e) {
        // Errors already toasted inside purchaseCreditPack (network/user cancel).
      } finally { setBusyId(null); }
      return;
    }
    // Subscription path → dedicated checkout page (subscriptions use Razorpay
    // Plans, requires a separate Recurring flow — deferred until Phase 2).
    navigate(`/checkout?plan=${id}&kind=${kind}`);
  };

  return (
    <div className="min-h-screen bg-white">
      <TopBar />
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-14">

        {/* Header */}
        <div className="text-center max-w-2xl mx-auto">
          <div className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 text-brand-700 border border-brand-200 px-3 py-1 text-[11px] font-bold uppercase tracking-widest" data-testid="pricing-badge">
            <ShieldCheck className="w-3.5 h-3.5" /> Fairness First · Credits Never Expire
          </div>
          <h1 className="mt-4 font-heading text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter text-ink-900">
            Pay for Access. Fuel with Credits.
          </h1>
          <p className="mt-4 text-lg text-ink-600 leading-relaxed">
            <strong>Subscribe once</strong> for platform access, brand kits, and premium features. <strong>Buy credits</strong> as you need them — every credit works across text, images, slideshows, and cinematic Sora 2 videos. <em>Your credits never expire.</em>
          </p>
        </div>

        {/* --- Part A: Platform Access (Subscriptions) --- */}
        <div className="mt-14">
          <div className="text-center">
            <div className="inline-flex items-center gap-1 text-[11px] uppercase tracking-widest text-brand-700 font-bold">
              <Package className="w-3.5 h-3.5" /> Part A · Platform Access
            </div>
            <h2 className="mt-2 font-heading text-3xl sm:text-4xl font-black tracking-tighter text-ink-900">Monthly Subscriptions</h2>
            <p className="mt-2 text-sm text-ink-500">Unlock features + get bundled credits every month. Cancel anytime.</p>
          </div>

          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="plans-grid">
            {plans.map((p) => {
              const Icon = PLAN_ICONS[p.id] || Sparkles;
              return (
                <div key={p.id}
                  className={`relative rounded-2xl border-2 p-5 flex flex-col ${p.popular ? "border-brand-600 bg-gradient-to-br from-brand-50 via-white to-white shadow-xl" : "border-ink-200 bg-white"}`}
                  data-testid={`plan-card-${p.id}`}>
                  {p.popular && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-brand-600 text-white text-[10px] font-bold uppercase tracking-widest px-3 py-1 rounded-full shadow">Most Popular</div>
                  )}
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${p.popular ? "bg-brand-600 text-white" : "bg-ink-100 text-ink-700"}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="mt-3 font-heading text-2xl font-black tracking-tighter">{p.name}</div>
                  <div className="mt-1 text-xs text-ink-500 min-h-[36px]">{p.tagline}</div>
                  <div className="mt-4 flex items-baseline gap-1">
                    <span className="text-3xl font-black tracking-tighter">₹{inr(p.price_inr)}</span>
                    {p.price_inr > 0 && <span className="text-xs text-ink-500">/mo</span>}
                  </div>
                  <div className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-mono font-semibold text-brand-700 bg-brand-50 border border-brand-200 rounded-full px-2 py-0.5 self-start">
                    + {inr(p.credits)} credits bundled
                  </div>
                  <Button onClick={() => goCheckout(p.id, "subscription")}
                    className={`mt-5 rounded-full font-bold ${p.popular ? "bg-brand-600 hover:bg-brand-700 text-white" : "bg-white border-2 border-ink-900 text-ink-900 hover:bg-ink-900 hover:text-white"}`}
                    data-testid={`plan-cta-${p.id}`}>
                    {p.price_inr === 0 ? "Start free" : "Subscribe"}
                  </Button>
                </div>
              );
            })}
          </div>
        </div>

        {/* --- Part B: Credit Packs --- */}
        <div className="mt-16">
          <div className="text-center">
            <div className="inline-flex items-center gap-1 text-[11px] uppercase tracking-widest text-emerald-700 font-bold">
              <CreditCard className="w-3.5 h-3.5" /> Part B · Content Credits
            </div>
            <h2 className="mt-2 font-heading text-3xl sm:text-4xl font-black tracking-tighter text-ink-900">Top-Up Packs (Never Expire)</h2>
            <p className="mt-2 text-sm text-ink-500">Buy once, use forever. Credits work across every AI action.</p>
          </div>

          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4" data-testid="packs-grid">
            {packs.map((p) => (
              <div key={p.id}
                className={`relative rounded-2xl border-2 p-5 flex flex-col ${p.popular ? "border-emerald-600 bg-gradient-to-br from-emerald-50 via-white to-white shadow-xl" : "border-ink-200 bg-white"}`}
                data-testid={`pack-card-${p.id}`}>
                {p.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-emerald-600 text-white text-[10px] font-bold uppercase tracking-widest px-3 py-1 rounded-full shadow">Best Value</div>
                )}
                <div className="font-heading text-2xl font-black tracking-tighter">{p.name}</div>
                <div className="mt-1 text-xs text-ink-500 min-h-[32px]">{p.tagline}</div>
                <div className="mt-4 flex items-baseline gap-2">
                  <span className="text-3xl font-black tracking-tighter">₹{inr(p.price_inr)}</span>
                  <span className="text-xs text-ink-500">= {inr(p.credits)} credits</span>
                </div>
                <div className="mt-1 text-[11px] font-mono text-emerald-700">₹{perCreditInr(p)} / credit</div>
                <Button onClick={() => goCheckout(p.id, "pack")}
                  disabled={busyId === p.id}
                  className={`mt-5 rounded-full font-bold ${p.popular ? "bg-emerald-600 hover:bg-emerald-700 text-white" : "bg-white border-2 border-ink-900 text-ink-900 hover:bg-ink-900 hover:text-white"}`}
                  data-testid={`pack-cta-${p.id}`}>
                  {busyId === p.id ? "Opening checkout…" : rzpEnabled ? "Buy pack" : "Notify me when live"}
                </Button>
              </div>
            ))}
          </div>
        </div>

        {/* --- Content Cost Estimator --- */}
        <div className="mt-16 rounded-3xl border-2 border-ink-200 bg-gradient-to-br from-ink-50 via-white to-brand-50/30 p-6 sm:p-8" data-testid="cost-estimator">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-widest text-ink-700 font-bold">
            <Calculator className="w-4 h-4" /> Content Cost Estimator
          </div>
          <h3 className="mt-2 font-heading text-3xl font-black tracking-tighter">See what your month will cost</h3>
          <p className="mt-2 text-sm text-ink-600">Enter what you plan to produce. We&apos;ll show total credits + which pack covers it.</p>

          <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <EstimatorRow icon={FileText}  label="Text posts (LinkedIn / Blog)" unitLabel="posts"  cost={findCost("post")}
              value={est.text}         onChange={(v) => setEst({ ...est, text: v })}          testid="est-text" />
            <EstimatorRow icon={ImageIcon} label="AI images"                   unitLabel="images" cost={findCost("image")}
              value={est.image}        onChange={(v) => setEst({ ...est, image: v })}         testid="est-image" />
            <EstimatorRow icon={Film}      label="Slideshow video"             unitLabel="minutes" cost={findCost("minute")}
              value={est.slideshowMin} onChange={(v) => setEst({ ...est, slideshowMin: v })}  testid="est-slide" />
            <EstimatorRow icon={Video}     label="Cinematic Sora 2 video"      unitLabel="seconds" cost={findCost("second")}
              value={est.soraSec}      onChange={(v) => setEst({ ...est, soraSec: v })}       testid="est-sora" />
          </div>

          <div className="mt-6 rounded-2xl bg-white border border-ink-200 p-5 flex flex-wrap items-center gap-4">
            <div className="min-w-[180px]">
              <div className="text-[11px] uppercase tracking-widest text-ink-500 font-bold">Estimated total</div>
              <div className="mt-1 text-4xl font-black tracking-tighter text-ink-900" data-testid="est-total">
                {inr(estimate)} <span className="text-base font-bold text-ink-500">credits</span>
              </div>
            </div>
            {cheapestPack && estimate > 0 && (
              <div className="flex-1 min-w-[240px] p-4 rounded-xl bg-emerald-50 border border-emerald-200">
                <div className="text-[11px] uppercase tracking-widest text-emerald-700 font-bold flex items-center gap-1">
                  <Award className="w-3.5 h-3.5" /> Recommended pack
                </div>
                <div className="mt-1 text-sm font-bold text-ink-900">
                  {cheapestPack.name} · ₹{inr(cheapestPack.price_inr)} = {inr(cheapestPack.credits)} credits
                </div>
                <div className="text-[11px] text-ink-500">Covers your month with {inr(cheapestPack.credits - estimate)} credits left over.</div>
                <Button onClick={() => goCheckout(cheapestPack.id, "pack")}
                  size="sm" className="mt-2 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold"
                  data-testid="est-cta-pack">
                  Buy this pack
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* --- Access-only feature matrix --- */}
        <div className="mt-16">
          <h3 className="font-heading text-2xl font-black tracking-tighter">What each subscription unlocks</h3>
          <p className="mt-1 text-sm text-ink-500">Compare access features — credits sold separately.</p>
          <div className="mt-6 overflow-x-auto rounded-2xl border border-ink-200 bg-white">
            <table className="w-full text-sm" data-testid="feature-matrix">
              <thead className="bg-ink-50">
                <tr>
                  <th className="text-left px-4 py-3 font-bold text-ink-700 text-xs uppercase tracking-widest">Feature</th>
                  {plans.map((p) => (
                    <th key={p.id} className="text-left px-4 py-3 font-bold text-ink-700 text-xs uppercase tracking-widest whitespace-nowrap">{p.name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ACCESS_FEATURES.map((f) => (
                  <tr key={f.key} className="border-t border-ink-100">
                    <td className="px-4 py-3 text-ink-800 font-medium">{f.label}</td>
                    <td className="px-4 py-3 text-ink-600">{f.free}</td>
                    <td className="px-4 py-3 text-ink-600">{f.basic}</td>
                    <td className="px-4 py-3 text-ink-800 font-semibold">{f.pro}</td>
                    <td className="px-4 py-3 text-ink-800 font-semibold">{f.agency}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* --- Transparent unit costs --- */}
        <div className="mt-16">
          <h3 className="font-heading text-2xl font-black tracking-tighter">Exactly what each credit pays for</h3>
          <p className="mt-1 text-sm text-ink-500">No hidden math. Every AI action has a fixed credit cost.</p>
          <div className="mt-6 grid gap-2" data-testid="usage-costs-list">
            {usage.map((u, i) => {
              const Icon = USAGE_ICONS[u.unit] || Sparkles;
              return (
                <div key={i} className="flex items-center gap-3 bg-white border border-ink-200 rounded-xl px-4 py-3">
                  <div className="w-8 h-8 rounded-lg bg-ink-100 flex items-center justify-center text-ink-700">
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="flex-1 text-sm text-ink-800 font-medium">{u.action}</div>
                  <div className="text-sm font-mono font-bold text-brand-700">{u.credits} credits / {u.unit}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* --- Fairness pledge --- */}
        <div className="mt-16 rounded-2xl bg-ink-900 text-white p-6 sm:p-10 flex flex-wrap items-start gap-6">
          <ShieldCheck className="w-8 h-8 text-emerald-400 shrink-0" />
          <div className="flex-1 min-w-[240px]">
            <div className="font-heading text-2xl font-black tracking-tighter">Our fairness pledge</div>
            <ul className="mt-3 space-y-2 text-sm text-white/85">
              <li className="flex items-start gap-2"><Check className="w-4 h-4 text-emerald-400 mt-0.5" /> Credits <strong>never expire</strong> — buy in bulk, use over months.</li>
              <li className="flex items-start gap-2"><Check className="w-4 h-4 text-emerald-400 mt-0.5" /> Every AI action shows its <strong>exact credit cost</strong> before you spend.</li>
              <li className="flex items-start gap-2"><Check className="w-4 h-4 text-emerald-400 mt-0.5" /> Auto-pause if balance runs low — <strong>no surprise overages</strong>.</li>
              <li className="flex items-start gap-2"><Check className="w-4 h-4 text-emerald-400 mt-0.5" /> Cancel your subscription anytime — your <strong>credits stay with you</strong>.</li>
            </ul>
          </div>
        </div>

        {/* --- CTA --- */}
        <div className="mt-14 text-center">
          <Link to="/signup" className="inline-flex items-center gap-2 text-brand-700 font-bold hover:underline" data-testid="pricing-signup-link">
            <Sparkles className="w-4 h-4" /> Start free · No card required
          </Link>
        </div>

      </div>
    </div>
  );
}

// Small numeric input for the estimator; keeps main render clean.
function EstimatorRow({ icon: Icon, label, unitLabel, cost, value, onChange, testid }) {
  return (
    <div className="rounded-xl bg-white border border-ink-200 p-4">
      <div className="flex items-center gap-2 text-xs text-ink-700 font-bold">
        <Icon className="w-3.5 h-3.5" /> {label}
      </div>
      <div className="mt-1 text-[11px] text-ink-500">{cost} credits / {unitLabel.replace(/s$/, "")}</div>
      <input type="number" min="0" step="1"
        value={value} onChange={(e) => onChange(Math.max(0, parseInt(e.target.value || "0", 10)))}
        placeholder="0"
        className="mt-3 w-full rounded-lg border-2 border-ink-200 focus:border-brand-600 outline-none px-3 py-2 text-lg font-mono font-bold text-ink-900"
        data-testid={testid} />
      <div className="mt-1 text-[11px] text-ink-500">{unitLabel}</div>
    </div>
  );
}
