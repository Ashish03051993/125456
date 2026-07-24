import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { Sparkles, X, ArrowRight, CheckCircle2, Circle, Trophy, Share2, Loader2, Copy, Check } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

const DISMISS_KEY = "avs_onboarding_dismissed_v1";
const CELEBRATED_KEY = "avs_onboarding_celebrated_v1";

// Onboarding checklist — auto-tracks progress from the user's projects.
// - Step 1: Create first video (any project exists)
// - Step 2: Watch a video render fully (any project.status === "ready")
// - Step 3: Share with the world (any project.share_enabled === true)
// Hides once all 3 done, or if user dismissed. Fires a one-time "🎉 pro!"
// toast on first completion.
export default function OnboardingChecklist({ projects }) {
  const [dismissed, setDismissed] = useState(() => {
    try { return localStorage.getItem(DISMISS_KEY) === "1"; } catch { return false; }
  });

  const steps = useMemo(() => {
    const list = projects || [];
    const created = list.length > 0;
    const rendered = list.some((p) => p.status === "ready");
    const shared = list.some((p) => p.share_enabled === true);
    const firstReady = list.find((p) => p.status === "ready");
    return [
      { id: "create",  title: "Create your first video", desc: "Type a topic and kick off the wizard.", done: created,  cta: { to: "/new", label: "Start creating" } },
      { id: "render",  title: "Watch it come to life",     desc: "Approve the script, images and voice.", done: rendered, cta: created ? null : { to: "/new", label: "Start creating" } },
      { id: "share",   title: "Share with the world",     desc: "One click — we'll create a public link you can send to anyone.", done: shared,  firstReadyId: firstReady?.id || null },
    ];
  }, [projects]);

  const [sharing, setSharing] = useState(false);

  const shareFirstReady = async (pid) => {
    if (!pid) return;
    setSharing(true);
    try {
      const { data } = await api.post(`/projects/${pid}/share`);
      const url = `${window.location.origin}/v/${data.share_slug}`;
      toast.success("Public link ready!", {
        description: url,
        duration: 8000,
        action: {
          label: "Copy link",
          onClick: () => {
            try { navigator.clipboard.writeText(url); toast.success("Copied to clipboard"); } catch {}
          },
        },
      });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Couldn't create share link — try again.");
    } finally { setSharing(false); }
  };

  const doneCount = steps.filter((s) => s.done).length;
  const allDone = doneCount === steps.length;

  // Fire a one-time celebration when the user finishes all 3.
  if (allDone) {
    try {
      if (localStorage.getItem(CELEBRATED_KEY) !== "1") {
        localStorage.setItem(CELEBRATED_KEY, "1");
        setTimeout(() => toast.success("You're a pro now! 🎉", {
          description: "Every core step done. Keep making great videos.",
        }), 200);
      }
    } catch {}
  }

  if (dismissed) return null;
  // Nothing to show for first-time users — the WelcomeBanner handles that state.
  if (!projects || projects.length === 0) return null;
  if (allDone) return null; // silent hide once fully completed

  const dismiss = () => {
    try { localStorage.setItem(DISMISS_KEY, "1"); } catch {}
    setDismissed(true);
  };

  const nextStep = steps.find((s) => !s.done);
  const pct = Math.round((doneCount / steps.length) * 100);

  return (
    <div className="mt-6 relative rounded-2xl border border-brand-200 bg-white p-5 sm:p-6 shadow-sm overflow-hidden"
         data-testid="onboarding-checklist">
      <button onClick={dismiss}
              className="absolute top-3 right-3 text-ink-400 hover:text-ink-700 z-10"
              aria-label="Dismiss checklist"
              data-testid="onboarding-dismiss">
        <X className="w-4 h-4" />
      </button>

      <div className="flex items-center gap-2">
        <Trophy className="w-4 h-4 text-brand-600" />
        <div className="text-[10px] uppercase tracking-widest text-brand-600 font-bold">Your quick-start</div>
        <div className="ml-auto text-xs text-ink-500 font-semibold" data-testid="onboarding-progress-text">
          {doneCount} of {steps.length} done
        </div>
      </div>

      <h2 className="mt-1 font-heading text-2xl sm:text-2xl font-black tracking-tight text-ink-900">
        {nextStep ? `Next up: ${nextStep.title.toLowerCase()}` : "You're all set!"}
      </h2>

      <div className="mt-3 relative h-1.5 rounded-full bg-ink-100 overflow-hidden">
        <div className="absolute inset-y-0 left-0 bg-gradient-to-r from-brand-500 to-brand-700 transition-all duration-500"
             style={{ width: `${pct}%` }}
             data-testid="onboarding-progress-bar" />
      </div>

      <ol className="mt-4 space-y-2.5">
        {steps.map((s, i) => (
          <li key={s.id}
              className={`flex items-start gap-3 rounded-xl px-3 py-2.5 border ${s.done ? "border-emerald-100 bg-emerald-50/40" : "border-ink-100 bg-white"}`}
              data-testid={`onboarding-step-${s.id}`}>
            {s.done ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" data-testid={`onboarding-step-${s.id}-done`} />
            ) : (
              <Circle className="w-5 h-5 text-ink-300 shrink-0 mt-0.5" />
            )}
            <div className="min-w-0 flex-1">
              <div className={`text-sm font-semibold ${s.done ? "text-emerald-700" : "text-ink-900"}`}>
                {i + 1}. {s.title}
              </div>
              <div className={`text-xs ${s.done ? "text-emerald-700/70" : "text-ink-500"}`}>{s.desc}</div>
            </div>
            {!s.done && s.cta && (
              <Link to={s.cta.to}
                    className="inline-flex items-center gap-1 rounded-full bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold px-3 py-1.5 transition-colors shrink-0"
                    data-testid={`onboarding-step-${s.id}-cta`}>
                {s.cta.label} <ArrowRight className="w-3 h-3" />
              </Link>
            )}
            {!s.done && s.id === "share" && s.firstReadyId && (
              <button
                onClick={() => shareFirstReady(s.firstReadyId)}
                disabled={sharing}
                className="inline-flex items-center gap-1 rounded-full bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white text-xs font-semibold px-3 py-1.5 transition-colors shrink-0"
                data-testid="onboarding-step-share-quickbtn"
              >
                {sharing ? <><Loader2 className="w-3 h-3 animate-spin" /> Publishing…</> : <><Share2 className="w-3 h-3" /> Publish share link</>}
              </button>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
