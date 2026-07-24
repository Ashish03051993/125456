import { Check, Sparkles, Image as ImageIcon, Mic, Film } from "lucide-react";

// Shared 4-step visualisation used in every approval gate (script → images →
// voice → composing). Highlights the current step so users always know where
// they are in the pipeline instead of getting a raw stage string.
const STEPS = [
  { id: "script",   label: "Script",   Icon: Sparkles },
  { id: "images",   label: "Visuals",  Icon: ImageIcon },
  { id: "voice",    label: "Voice",    Icon: Mic },
  { id: "compose",  label: "Final",    Icon: Film },
];

// Map a project's `status` to the current step index. Anything post-compose
// counts as fully done (index === STEPS.length).
export function currentStepIndex(status) {
  switch (status) {
    case "awaiting_script_approval": return 0;
    case "awaiting_image_approval":  return 1;
    case "awaiting_voice_approval":  return 2;
    case "generating":               return 3;
    case "ready":                    return STEPS.length;
    default:                         return 0;
  }
}

export default function ApprovalStepIndicator({ status }) {
  const active = currentStepIndex(status);
  return (
    <div className="flex items-center gap-1.5 sm:gap-2 overflow-x-auto pb-1" data-testid="approval-step-indicator">
      {STEPS.map((s, i) => {
        const done = i < active;
        const current = i === active;
        return (
          <div key={s.id} className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            <div className={`flex items-center gap-1.5 rounded-full pl-1.5 pr-2.5 py-1 border transition-all
                            ${current ? "bg-white text-brand-700 border-white shadow-sm" :
                              done    ? "bg-white/20 text-white border-white/30" :
                                        "bg-transparent text-white/60 border-white/25"}`}
                 data-testid={`step-chip-${s.id}${current ? "-current" : done ? "-done" : "-pending"}`}>
              <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold
                              ${current ? "bg-brand-600 text-white" :
                                done    ? "bg-emerald-500 text-white" :
                                          "bg-white/25 text-white"}`}>
                {done ? <Check className="w-3 h-3" /> : <s.Icon className="w-3 h-3" />}
              </div>
              <span className="text-[11px] font-bold uppercase tracking-widest">{s.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`h-px w-3 sm:w-6 ${done ? "bg-white/40" : "bg-white/20"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
