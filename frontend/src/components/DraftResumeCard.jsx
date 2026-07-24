import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FileText, ArrowRight, X, Clock } from "lucide-react";

// Reads the wizard draft written by ProjectWizard.jsx (avs_wizard_draft_v1)
// and prompts the user to resume if they started a wizard but never finished.
// Silent if there's no draft or the draft has no topic yet.
const DRAFT_KEY = "avs_wizard_draft_v1";

function timeAgo(ts) {
  if (!ts) return "";
  const seconds = Math.max(1, Math.floor((Date.now() - ts) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function DraftResumeCard() {
  const [draft, setDraft] = useState(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (!raw) return;
      const d = JSON.parse(raw);
      if (d && typeof d.topic === "string" && d.topic.trim().length >= 3) {
        setDraft(d);
      }
    } catch { /* ignore corrupt draft */ }
  }, []);

  const clear = (e) => {
    e.preventDefault();
    e.stopPropagation();
    try { localStorage.removeItem(DRAFT_KEY); } catch {}
    setDraft(null);
  };

  if (!draft) return null;

  const preview = draft.topic.length > 110 ? draft.topic.slice(0, 107) + "…" : draft.topic;

  return (
    <div className="mt-6 relative rounded-2xl border border-brand-200 bg-white p-4 sm:p-5 flex items-start gap-4 shadow-sm"
         data-testid="draft-resume-card">
      <div className="w-10 h-10 shrink-0 rounded-xl bg-brand-50 border border-brand-100 flex items-center justify-center">
        <FileText className="w-5 h-5 text-brand-600" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="text-[10px] uppercase tracking-widest text-brand-600 font-bold">Resume where you left off</div>
          {draft.at && (
            <span className="inline-flex items-center gap-1 text-[10px] text-ink-400 font-semibold">
              <Clock className="w-3 h-3" /> {timeAgo(draft.at)}
            </span>
          )}
        </div>
        <div className="mt-1 font-semibold text-ink-900 text-sm line-clamp-2">
          &ldquo;{preview}&rdquo;
        </div>
        <div className="mt-3 flex items-center gap-3">
          <Link to="/new"
                className="inline-flex items-center gap-1.5 rounded-full bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold px-4 py-1.5 transition-colors"
                data-testid="draft-resume-btn">
            Resume draft <ArrowRight className="w-3.5 h-3.5" />
          </Link>
          <button onClick={clear}
                  className="text-xs font-semibold text-ink-500 hover:text-ink-800 transition-colors"
                  data-testid="draft-discard-btn">
            Discard
          </button>
        </div>
      </div>
      <button onClick={clear}
              className="absolute top-3 right-3 text-ink-400 hover:text-ink-700"
              aria-label="Dismiss"
              data-testid="draft-dismiss">
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
