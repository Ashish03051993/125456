import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, X, Coins, Lock, ArrowRight, Zap, Rocket } from "lucide-react";
import { Button } from "@/components/ui/button";
import { track } from "@/lib/analytics";

// Config: maps 402 `code` → visual + copy.
const PAYWALL_CONTENT = {
  insufficient_credits: {
    Icon: Coins,
    accent: "from-amber-400 to-orange-600",
    title: (d) => `You need ${d.needed} credits`,
    kicker: "Almost there",
    body: (d) => `A ${d.duration_sec}-second video costs ${d.needed} credits — you currently have ${d.have}. Top up any pack (credits never expire) and continue where you left off.`,
    bullets: [
      "Credits never expire — buy once, use whenever",
      "Bigger packs unlock better cost per video",
      "Every render includes 16:9 AND 9:16 formats",
    ],
    ctaLabel: "See top-up packs",
    trackEvent: "paywall_credits",
  },
  paid_feature_required: {
    Icon: Lock,
    accent: "from-brand-500 to-indigo-600",
    title: () => "Unlock this feature",
    kicker: "Creator plan or above required",
    body: (d) => d.feature === "talking_head"
      ? "Talking-head uses a specialised external AI service on top of your regular credits, so it's a paid-plan feature. Your existing credits still pay for the video generation itself — the plan upgrade only unlocks feature access. Available on Creator plan (₹1,999/mo) and above."
      : "This capability requires a paid plan. Your credits stay on your account and cover the video generation itself — the plan upgrade unlocks feature access. Available on Creator plan (₹1,999/mo) and above.",
    bullets: [
      "Photorealistic talking-head characters",
      "Priority render queue",
      "HD downloads & brand watermark toggle",
      "1-hour support response SLA",
    ],
    ctaLabel: "See paid plans",
    trackEvent: "paywall_paid_feature",
  },
};

export default function UpgradeModal() {
  const nav = useNavigate();
  const [payload, setPayload] = useState(null);

  const close = useCallback(() => {
    if (payload) track(`${(PAYWALL_CONTENT[payload.code] || {}).trackEvent || "paywall"}_dismiss`);
    setPayload(null);
  }, [payload]);

  useEffect(() => {
    const onOpen = (e) => {
      setPayload(e.detail);
      const cfg = PAYWALL_CONTENT[e.detail.code];
      if (cfg?.trackEvent) track(`${cfg.trackEvent}_open`, { code: e.detail.code, ...e.detail });
    };
    window.addEventListener("paywall:open", onOpen);
    return () => window.removeEventListener("paywall:open", onOpen);
  }, []);

  // Close on Escape
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape" && payload) close(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [payload, close]);

  if (!payload) return null;
  const cfg = PAYWALL_CONTENT[payload.code] || PAYWALL_CONTENT.paid_feature_required;
  const { Icon, accent, kicker } = cfg;
  const title = cfg.title(payload);
  const body = cfg.body(payload);
  const bullets = cfg.bullets;

  const goPricing = () => {
    track(`${cfg.trackEvent}_convert`, { code: payload.code, ...payload });
    setPayload(null);
    nav(payload.upgrade_url || "/pricing");
  };

  return (
    <div className="fixed inset-0 z-[100] bg-ink-900/70 backdrop-blur-sm flex items-center justify-center p-4"
         onClick={close}
         data-testid="upgrade-modal"
         data-code={payload.code}>
      <div className="relative bg-white rounded-2xl max-w-md w-full shadow-2xl overflow-hidden"
           onClick={(e) => e.stopPropagation()}
           data-testid="upgrade-modal-inner">
        {/* Colorful accent header */}
        <div className={`bg-gradient-to-br ${accent} px-6 pt-6 pb-16 relative`}>
          <button onClick={close} data-testid="upgrade-modal-close"
                  className="absolute top-3 right-3 text-white/70 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-white/25 backdrop-blur-sm px-2.5 py-1 text-[10px] uppercase tracking-widest font-bold text-white">
            <Sparkles className="w-3 h-3" /> {kicker}
          </div>
        </div>

        {/* Floating icon */}
        <div className="absolute top-14 left-6 w-16 h-16 rounded-2xl bg-white shadow-lg flex items-center justify-center ring-4 ring-white">
          <Icon className="w-7 h-7 text-brand-600" />
        </div>

        <div className="px-6 pt-12 pb-6">
          <h3 className="font-heading text-2xl font-black tracking-tight text-ink-900" data-testid="upgrade-modal-title">
            {title}
          </h3>
          <p className="text-sm text-ink-500 mt-2" data-testid="upgrade-modal-body">{body}</p>

          <ul className="mt-5 space-y-2.5 text-sm text-ink-700" data-testid="upgrade-modal-bullets">
            {bullets.map((b) => (
              <li key={b} className="flex items-start gap-2">
                <div className="w-4 h-4 rounded-full bg-brand-100 flex items-center justify-center mt-0.5 shrink-0">
                  <div className="w-1.5 h-1.5 rounded-full bg-brand-600" />
                </div>
                <span>{b}</span>
              </li>
            ))}
          </ul>

          {/* Compact plan preview strip */}
          {payload.code === "insufficient_credits" && (
            <div className="mt-5 grid grid-cols-3 gap-2 text-center" data-testid="upgrade-plan-strip">
              {[
                { name: "Starter", credits: "60", price: "$10", Icon: Zap },
                { name: "Creator", credits: "175", price: "$25", Icon: Rocket, best: true },
                { name: "Pro", credits: "400", price: "$50", Icon: Sparkles },
              ].map((p) => (
                <div key={p.name}
                     className={`rounded-xl border p-2 ${p.best ? "border-brand-600 bg-brand-50" : "border-ink-200"}`}>
                  <p.Icon className={`w-3.5 h-3.5 mx-auto ${p.best ? "text-brand-600" : "text-ink-500"}`} />
                  <div className="mt-1 text-[10px] uppercase tracking-widest text-ink-500 font-semibold">{p.name}</div>
                  <div className="font-heading font-bold text-sm text-ink-900">{p.credits}</div>
                  <div className="text-[10px] text-ink-400">{p.price}</div>
                </div>
              ))}
            </div>
          )}

          <div className="mt-6 flex gap-2">
            <Button onClick={goPricing}
                    data-testid="upgrade-modal-cta"
                    className="flex-1 rounded-full bg-brand-600 hover:bg-brand-700 text-white h-11 font-semibold">
              {cfg.ctaLabel} <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
            <Button variant="outline" onClick={close}
                    data-testid="upgrade-modal-dismiss"
                    className="rounded-full h-11 px-4">
              Maybe later
            </Button>
          </div>
          <p className="text-[10px] text-ink-400 text-center mt-3">
            Credits never expire · 14-day refund if unused · Secure checkout
          </p>
        </div>
      </div>
    </div>
  );
}
