import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sparkles, CheckCircle2, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { track, getAttribution } from "@/lib/analytics";
import { toast } from "sonner";

export default function WaitlistForm({ compact = false, source = "landing_hero" }) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [useCase, setUseCase] = useState("");
  const [plan, setPlan] = useState("pro");
  const [busy, setBusy] = useState(false);
  const [joined, setJoined] = useState(null);

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!email.trim() || !email.includes("@")) return toast.error("Enter a valid email");
    setBusy(true);
    track("waitlist_button_click", { source });
    track("waitlist_submit", { source, plan_interest: plan });
    try {
      const attr = getAttribution();
      let variant = null;
      try {
        const cached = JSON.parse(localStorage.getItem("avs_exp_landing_hero") || "null");
        variant = cached?.variant || null;
      } catch { /* ignore */ }
      const { data } = await api.post("/waitlist", {
        email, name: name || undefined, use_case: useCase || undefined,
        plan_interest: plan, referrer: document.referrer || undefined,
        source: attr?.source, medium: attr?.medium, campaign: attr?.campaign,
        variant,
      });
      setJoined(data);
      track("waitlist_success", { source, position: data.position, already: !!data.already_joined });
      toast.success(data.already_joined ? "You're already on the list!" : "You're on the list 🎉");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Something went wrong");
    } finally { setBusy(false); }
  };

  if (joined) {
    return (
      <div className="rounded-2xl border-2 border-brand-600/30 bg-white p-6 sm:p-8 max-w-xl" data-testid="waitlist-success">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-full bg-brand-600 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="font-heading font-extrabold text-xl sm:text-2xl tracking-tight">You&apos;re in.</div>
            <div className="text-ink-500 text-sm mt-0.5">
              {joined.already_joined ? "Already on the list — " : "Position "}
              <span className="text-brand-700 font-bold">#{joined.position}</span>
            </div>
          </div>
        </div>
        <p className="mt-5 text-ink-700 text-sm sm:text-base leading-relaxed">
          We&apos;ll email <span className="font-semibold">{email}</span> the moment early access opens.
          In the meantime, share the studio with a friend who ships content.
        </p>
      </div>
    );
  }

  if (compact) {
    return (
      <form onSubmit={submit} className="flex flex-col sm:flex-row gap-2 max-w-lg" data-testid="waitlist-form-compact">
        <Input type="email" placeholder="you@company.com" value={email} onChange={(e)=>setEmail(e.target.value)}
          data-testid="waitlist-email-compact" className="h-12 flex-1" required />
        <Button type="submit" disabled={busy}
          className="h-12 rounded-full bg-brand-600 hover:bg-brand-700 text-white px-6 whitespace-nowrap"
          data-testid="waitlist-submit-compact">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Sparkles className="w-4 h-4 mr-2" /> Join waitlist</>}
        </Button>
      </form>
    );
  }

  return (
    <form onSubmit={submit} className="rounded-2xl border border-ink-200 bg-white p-6 sm:p-8 max-w-xl space-y-4 shadow-sm" data-testid="waitlist-form">
      <div>
        <label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Work email</label>
        <Input type="email" required placeholder="you@company.com" value={email}
          onChange={(e)=>setEmail(e.target.value)} className="mt-2 h-11" data-testid="waitlist-email" />
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <div>
          <label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Your name</label>
          <Input placeholder="Optional" value={name} onChange={(e)=>setName(e.target.value)}
            className="mt-2 h-11" data-testid="waitlist-name" />
        </div>
        <div>
          <label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Interested plan</label>
          <select value={plan} onChange={(e)=>setPlan(e.target.value)}
            className="mt-2 h-11 w-full rounded-md border border-ink-200 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            data-testid="waitlist-plan">
            <option value="free">Free — try it out</option>
            <option value="pro">Pro (₹999/mo)</option>
            <option value="business">Business (₹4,999/mo)</option>
            <option value="enterprise">Enterprise</option>
          </select>
        </div>
      </div>
      <div>
        <label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">What will you make?</label>
        <Input placeholder="e.g. Product explainers, YouTube shorts, training clips"
          value={useCase} onChange={(e)=>setUseCase(e.target.value)}
          className="mt-2 h-11" data-testid="waitlist-usecase" />
      </div>
      <Button type="submit" disabled={busy}
        className="w-full h-12 rounded-full bg-brand-600 hover:bg-brand-700 text-white text-base"
        data-testid="waitlist-submit">
        {busy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Adding you…</> :
                <><Sparkles className="w-4 h-4 mr-2" /> Reserve my spot</>}
      </Button>
      <p className="text-xs text-ink-500 text-center">No spam. One email when access opens. Unsubscribe anytime.</p>
    </form>
  );
}
