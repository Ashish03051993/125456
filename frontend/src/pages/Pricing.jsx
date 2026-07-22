import { Link } from "react-router-dom";
import { Check, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TopBar } from "@/components/Layout";
import { login } from "@/pages/AuthCallback";
import { useAuth } from "@/lib/auth";

const TIERS = [
  { id: "free", name: "Free", price: "₹0", period: "forever", credits: "1 video / month", features: ["720p export", "5 scene max", "Watermark"], cta: "Start free", primary: false },
  { id: "pro", name: "Pro", price: "₹999", period: "/month", credits: "40 videos / month", features: ["1080p export", "Unlimited scenes", "No watermark", "Priority queue"], cta: "Upgrade to Pro", primary: true },
  { id: "business", name: "Business", price: "₹4,999", period: "/month", credits: "300 videos / month", features: ["4K export", "Team seats (5)", "Brand kit", "API access"], cta: "Start Business", primary: false },
  { id: "enterprise", name: "Enterprise", price: "Custom", period: "", credits: "Unlimited", features: ["SSO / SAML", "SLA", "Dedicated support", "Custom models"], cta: "Talk to sales", primary: false },
];

export default function Pricing() {
  const { user } = useAuth();
  return (
    <div className="min-h-screen bg-ink-50">
      <TopBar />
      <section className="max-w-7xl mx-auto px-6 py-20">
        <div className="text-center max-w-2xl mx-auto">
          <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Pricing</div>
          <h1 className="mt-3 font-heading text-5xl sm:text-6xl font-extrabold tracking-tighter">Simple, credit-based pricing.</h1>
          <p className="mt-5 text-ink-500 text-lg">Every video costs one credit — regardless of length. Upgrade or cancel anytime.</p>
        </div>
        <div className="mt-14 grid md:grid-cols-4 gap-4">
          {TIERS.map((t) => (
            <div key={t.id} data-testid={`plan-${t.id}`} className={`rounded-2xl border p-7 flex flex-col ${
              t.primary ? "border-brand-600 bg-white shadow-xl ring-2 ring-brand-600/20 md:-translate-y-3" : "border-ink-200 bg-white"
            }`}>
              {t.primary && (
                <div className="inline-flex self-start items-center gap-1 bg-brand-600 text-white text-xs font-bold uppercase tracking-widest rounded-full px-2 py-1 mb-3">
                  <Sparkles className="w-3 h-3" /> Popular
                </div>
              )}
              <div className="font-heading font-bold text-2xl">{t.name}</div>
              <div className="mt-2 flex items-baseline gap-1">
                <div className="font-heading text-4xl font-extrabold tracking-tighter">{t.price}</div>
                <div className="text-ink-500 text-sm">{t.period}</div>
              </div>
              <div className="mt-1 text-sm text-brand-700 font-semibold">{t.credits}</div>
              <ul className="mt-6 space-y-2.5 flex-1">
                {t.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-ink-700"><Check className="w-4 h-4 text-brand-600 mt-0.5 shrink-0" /> {f}</li>
                ))}
              </ul>
              <Button data-testid={`plan-cta-${t.id}`}
                className={`mt-6 h-11 rounded-full ${t.primary ? "bg-brand-600 hover:bg-brand-700 text-white" : "bg-ink-900 hover:bg-ink-700 text-white"}`}
                onClick={() => { if (t.id === "enterprise") window.open("mailto:sales@videostudio.ai"); }}
              >
                {user && t.id === "free" ? "Current plan" : t.cta}
              </Button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
