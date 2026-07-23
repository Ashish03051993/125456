import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Cookie, X } from "lucide-react";
import { Button } from "@/components/ui/button";

const STORAGE_KEY = "avs_cookie_consent_v1";

export function getCookieConsent() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
  } catch { return null; }
}

export function hasAnalyticsConsent() {
  const c = getCookieConsent();
  return c?.analytics === true;
}

export default function CookieConsent() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Show only if no choice yet
    if (!getCookieConsent()) {
      // Delay slightly so the page renders first, avoiding CLS
      const t = setTimeout(() => setVisible(true), 700);
      return () => clearTimeout(t);
    }
  }, []);

  const save = (choice) => {
    const payload = {
      necessary: true,
      analytics: choice === "all",
      at: new Date().toISOString(),
      v: 1,
    };
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(payload)); } catch {}
    setVisible(false);
    // Broadcast so analytics/tracking layers can start (or stay silent)
    try { window.dispatchEvent(new CustomEvent("cookie-consent:updated", { detail: payload })); } catch {}
  };

  if (!visible) return null;

  return (
    <div
      role="dialog"
      aria-labelledby="cookie-title"
      aria-describedby="cookie-desc"
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[90] w-[min(680px,calc(100vw-2rem))]"
      data-testid="cookie-consent"
    >
      <div className="rounded-2xl bg-white border border-ink-200 shadow-2xl p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex items-start sm:items-center gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-brand-50 border border-brand-100 flex items-center justify-center shrink-0">
            <Cookie className="w-5 h-5 text-brand-600" />
          </div>
          <div className="min-w-0">
            <div id="cookie-title" className="font-heading font-bold text-sm text-ink-900">We use a few cookies</div>
            <p id="cookie-desc" className="text-xs text-ink-500 mt-0.5">
              Login sessions are strictly necessary. Anonymous product analytics help us improve the app.{" "}
              <Link to="/privacy" className="underline hover:text-brand-600 font-semibold" data-testid="cookie-privacy-link">Details</Link>.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0" data-testid="cookie-actions">
          <Button variant="outline" size="sm" onClick={() => save("necessary")}
            className="rounded-full text-xs h-9 whitespace-nowrap"
            data-testid="cookie-necessary-btn">
            Only necessary
          </Button>
          <Button size="sm" onClick={() => save("all")}
            className="rounded-full text-xs h-9 whitespace-nowrap bg-brand-600 hover:bg-brand-700 text-white font-semibold"
            data-testid="cookie-accept-all-btn">
            Accept all
          </Button>
          <button onClick={() => save("necessary")}
            className="text-ink-400 hover:text-ink-700 ml-1"
            aria-label="Dismiss"
            data-testid="cookie-close-btn">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
