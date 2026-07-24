import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { TopBar, Sidebar } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Coins, Sparkles, Loader2, Check, ArrowRight } from "lucide-react";
import { purchaseCreditPack } from "@/lib/razorpayCheckout";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";

// Buy-credits page. Feature-flagged: if the backend reports
// `enabled: false`, we show a "coming soon" state with an invite-your-friend
// fallback (they can still earn credits via referrals right now).
export default function BuyCredits() {
  const { user, refresh } = useAuth();
  const [config, setConfig] = useState(null);
  const [busyPack, setBusyPack] = useState(null);

  useEffect(() => {
    let alive = true;
    api.get("/payments/razorpay/config")
      .then(({ data }) => { if (alive) setConfig(data); })
      .catch(() => { if (alive) setConfig({ enabled: false, packs: [] }); });
    return () => { alive = false; };
  }, []);

  const buy = async (pack) => {
    setBusyPack(pack.id);
    try {
      await purchaseCreditPack({ packId: pack.id });
      await refresh();  // pick up the new credit balance
    } catch (e) {
      // Errors already surfaced via toast inside purchaseCreditPack
      if (e?.message !== "user_dismissed") {
        // no extra toast — helper already fired one
      }
    } finally {
      setBusyPack(null);
    }
  };

  return (
    <div className="min-h-screen bg-ink-50" data-testid="buy-credits-page">
      <TopBar />
      <div className="flex">
        <Sidebar />
        <main className="flex-1 p-6 sm:p-8">
          <div className="max-w-5xl">
            <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Top up</div>
            <h1 className="mt-1 font-heading text-4xl font-extrabold tracking-tighter">
              Buy credits
            </h1>
            <p className="mt-2 text-ink-500 max-w-2xl">
              One credit = one 10-second slice of finished video.
              {user && (
                <> You currently have <span className="font-bold text-ink-900">{user.credits ?? 0}</span> credits.</>
              )}
            </p>

            {!config && (
              <div className="mt-10 flex items-center gap-2 text-ink-500">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading packs…
              </div>
            )}

            {config && !config.enabled && (
              <div className="mt-8 rounded-2xl border border-amber-200 bg-amber-50 p-6 max-w-2xl" data-testid="payments-disabled-banner">
                <div className="flex items-start gap-3">
                  <Sparkles className="w-5 h-5 text-amber-600 mt-0.5" />
                  <div>
                    <div className="font-heading font-bold text-lg text-ink-900">Card payments arrive soon.</div>
                    <p className="text-sm text-ink-700 mt-1">
                      We&apos;re finishing final compliance checks. In the meantime you can earn free credits any time
                      by inviting friends — you both get 3 credits per successful signup.
                    </p>
                    <Link to="/settings">
                      <Button className="mt-4 rounded-full bg-brand-600 hover:bg-brand-700 text-white" data-testid="fallback-referral-btn">
                        Get free credits with referrals <ArrowRight className="w-4 h-4 ml-1.5" />
                      </Button>
                    </Link>
                  </div>
                </div>
              </div>
            )}

            {config && config.enabled && (
              <>
                {!config.live_mode && (
                  <div className="mt-6 inline-flex items-center gap-1.5 rounded-full bg-amber-100 border border-amber-300 px-3 py-1 text-[11px] font-semibold text-amber-800 uppercase tracking-widest"
                       data-testid="test-mode-banner">
                    Test mode — no real money will be charged
                  </div>
                )}
                <div className="mt-8 grid sm:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="credit-packs-grid">
                  {config.packs.map((p) => {
                    const perCredit = (p.price_inr / p.credits).toFixed(2);
                    const busy = busyPack === p.id;
                    return (
                      <div key={p.id}
                           className={`relative rounded-2xl border p-6 bg-white flex flex-col ${p.popular ? "border-brand-600 shadow-lg shadow-brand-600/10" : "border-ink-200"}`}
                           data-testid={`credit-pack-${p.id}`}>
                        {p.popular && (
                          <div className="absolute -top-3 left-6 inline-flex items-center gap-1 rounded-full bg-brand-600 text-white text-[10px] font-bold px-3 py-1 uppercase tracking-widest">
                            Most popular
                          </div>
                        )}
                        <div className="flex items-center gap-2">
                          <Coins className="w-4 h-4 text-brand-600" />
                          <div className="text-[10px] uppercase tracking-widest text-ink-500 font-bold">{p.label}</div>
                        </div>
                        <div className="mt-3 font-heading font-black text-4xl tracking-tighter text-ink-900">
                          {p.credits}
                          <span className="text-base font-semibold text-ink-500 ml-2">credits</span>
                        </div>
                        <div className="mt-1 text-2xl font-heading font-bold text-brand-700">
                          ₹{p.price_inr.toLocaleString("en-IN")}
                        </div>
                        <div className="mt-1 text-xs text-ink-500">
                          ≈ ₹{perCredit} per credit
                        </div>
                        <ul className="mt-4 space-y-1.5 text-xs text-ink-600 flex-1">
                          <li className="flex items-center gap-1.5"><Check className="w-3.5 h-3.5 text-emerald-500" /> Instant delivery</li>
                          <li className="flex items-center gap-1.5"><Check className="w-3.5 h-3.5 text-emerald-500" /> Never expires</li>
                          <li className="flex items-center gap-1.5"><Check className="w-3.5 h-3.5 text-emerald-500" /> All video formats included</li>
                        </ul>
                        <Button
                          onClick={() => buy(p)}
                          disabled={busy}
                          className={`mt-5 rounded-full w-full ${p.popular ? "bg-brand-600 hover:bg-brand-700 text-white" : "bg-ink-900 hover:bg-ink-800 text-white"}`}
                          data-testid={`credit-pack-buy-${p.id}`}
                        >
                          {busy ? (
                            <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Opening…</>
                          ) : (
                            <>Buy for ₹{p.price_inr.toLocaleString("en-IN")}</>
                          )}
                        </Button>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-6 text-xs text-ink-500">
                  Payments powered by Razorpay. All prices in INR. Credits are non-refundable but never expire.
                </div>
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
