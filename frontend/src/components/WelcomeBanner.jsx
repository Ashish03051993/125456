import { useState } from "react";
import { Link } from "react-router-dom";
import { Sparkles, X, ArrowRight, MessageSquare, CheckCircle2, Film } from "lucide-react";

const DISMISS_KEY = "avs_welcome_dismissed_v1";

// Shows once for a first-time user on their Dashboard — a friendly 3-step
// primer so they know exactly what to do next. Auto-hides for anyone who has
// (a) previously dismissed it, or (b) already created at least one project.
export default function WelcomeBanner({ hasProjects }) {
  const [dismissed, setDismissed] = useState(() => {
    try { return localStorage.getItem(DISMISS_KEY) === "1"; } catch { return false; }
  });

  if (dismissed) return null;
  if (hasProjects) return null; // Silent auto-hide once they've made their first video

  const dismiss = () => {
    try { localStorage.setItem(DISMISS_KEY, "1"); } catch {}
    setDismissed(true);
  };

  return (
    <div className="mt-6 relative rounded-2xl border border-brand-200 bg-gradient-to-br from-brand-50 via-white to-white p-5 sm:p-6 overflow-hidden"
         data-testid="welcome-banner">
      <div className="absolute -top-10 -right-10 w-48 h-48 bg-brand-100 rounded-full opacity-40 blur-3xl pointer-events-none" />
      <button onClick={dismiss}
              className="absolute top-3 right-3 text-ink-400 hover:text-ink-700 z-10"
              aria-label="Dismiss"
              data-testid="welcome-dismiss">
        <X className="w-4 h-4" />
      </button>
      <div className="relative">
        <div className="text-[10px] uppercase tracking-widest text-brand-600 font-bold flex items-center gap-1.5">
          <Sparkles className="w-3 h-3" /> Welcome aboard
        </div>
        <h2 className="mt-1 font-heading text-2xl sm:text-3xl font-black tracking-tight text-ink-900">
          Let&apos;s make your first video.
        </h2>
        <p className="mt-1 text-ink-500 text-sm">
          Your free credits are ready. From topic to polished MP4 in three easy steps.
        </p>

        <div className="mt-5 grid sm:grid-cols-3 gap-3">
          {[
            { n: 1, Icon: MessageSquare, title: "Type a topic",     desc: "Any idea — the AI writes the script." },
            { n: 2, Icon: CheckCircle2,  title: "Approve each step", desc: "Tweak script, images and voice." },
            { n: 3, Icon: Film,          title: "Download or share", desc: "In 16:9, 9:16 and 1:1." },
          ].map((s) => (
            <div key={s.n} className="flex gap-3 rounded-xl bg-white border border-ink-100 px-4 py-3" data-testid={`welcome-step-${s.n}`}>
              <div className="w-8 h-8 shrink-0 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center">
                <s.Icon className="w-4 h-4 text-brand-600" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-bold text-ink-500">STEP {s.n}</div>
                <div className="font-semibold text-ink-900 text-sm">{s.title}</div>
                <div className="text-xs text-ink-500 leading-snug">{s.desc}</div>
              </div>
            </div>
          ))}
        </div>

        <Link to="/new"
              onClick={dismiss}
              className="mt-5 inline-flex items-center gap-1.5 rounded-full bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold px-5 py-2.5 shadow-sm transition-colors"
              data-testid="welcome-cta-btn">
          Start my first video <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}
