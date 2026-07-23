import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Gift, X, ArrowRight } from "lucide-react";

const DISMISS_KEY = "avs_low_credit_nudge_dismissed_v1";

// Low-Credit Referral Nudge — appears on Dashboard when the user can't afford
// the cheapest video (30s = 3 credits) and is on the free plan. Turns dead-end
// moments into growth by pointing them at the referral program instead of just
// the pricing page.
export default function LowCreditNudge() {
  const { user } = useAuth();
  const [dismissed, setDismissed] = useState(() => {
    try { return sessionStorage.getItem(DISMISS_KEY) === "1"; } catch { return false; }
  });

  if (!user) return null;
  if (dismissed) return null;
  // Show only when user is genuinely low: below the cheapest video cost AND on free plan
  if ((user.credits ?? 0) >= 3) return null;
  if (user.plan && user.plan !== "free") return null;

  const dismiss = () => {
    try { sessionStorage.setItem(DISMISS_KEY, "1"); } catch {}
    setDismissed(true);
  };

  return (
    <div className="mt-6 relative rounded-2xl border border-amber-200 bg-gradient-to-r from-amber-50 via-white to-brand-50 p-5 sm:p-6 overflow-hidden"
         data-testid="low-credit-nudge">
      <div className="absolute -top-8 -right-6 w-32 h-32 bg-brand-100 rounded-full opacity-40 blur-2xl pointer-events-none" />
      <button onClick={dismiss}
              className="absolute top-3 right-3 text-ink-400 hover:text-ink-700 z-10"
              aria-label="Dismiss"
              data-testid="low-credit-nudge-dismiss">
        <X className="w-4 h-4" />
      </button>
      <div className="relative flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-white border-2 border-amber-200 flex items-center justify-center shrink-0">
          <Gift className="w-6 h-6 text-brand-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] uppercase tracking-widest font-bold text-amber-700">
            Running low on credits
          </div>
          <div className="mt-1 font-heading text-lg sm:text-xl font-black tracking-tight text-ink-900">
            Invite a friend, both of you get <span className="text-brand-600">3 credits</span>.
          </div>
          <p className="mt-1 text-sm text-ink-500">
            One referral = one free 30-second video for you. No wait, no card required.
          </p>
        </div>
        <Link to="/settings"
              className="shrink-0 inline-flex items-center gap-1.5 rounded-full bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold px-5 py-2.5 shadow-sm transition-colors"
              data-testid="low-credit-nudge-cta">
          Get my invite link <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}
