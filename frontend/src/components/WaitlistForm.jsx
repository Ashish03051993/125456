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
    const referralUrl = `${window.location.origin}/?utm_source=referral&utm_medium=share&utm_campaign=waitlist&ref=${joined.position}`;
    const shareText = `I just joined the Kadenza private beta at position #${joined.position} — turn any topic into a ready-to-post video (16:9 + 9:16) in minutes. Reserve your spot 👇`;
    const openLinkedIn = () => {
      window.open(
        `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(referralUrl)}&summary=${encodeURIComponent(shareText)}`,
        "_blank", "noopener,noreferrer",
      );
      track("waitlist_share_click", { channel: "linkedin", position: joined.position });
    };
    const openTwitter = () => {
      window.open(
        `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(referralUrl)}`,
        "_blank", "noopener,noreferrer",
      );
      track("waitlist_share_click", { channel: "twitter", position: joined.position });
    };
    const copyReferral = async () => {
      try {
        await navigator.clipboard.writeText(referralUrl);
        toast.success("Your referral link is copied");
        track("waitlist_share_click", { channel: "copy", position: joined.position });
      } catch { toast.error("Copy failed — please copy manually"); }
    };

    return (
      <div className="rounded-2xl border-2 border-brand-600/30 bg-white p-6 sm:p-8 max-w-xl" data-testid="waitlist-success">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-full bg-brand-600 flex items-center justify-center shrink-0 shadow-lg shadow-brand-600/30">
            <CheckCircle2 className="w-7 h-7 text-white" />
          </div>
          <div className="flex-1">
            <div className="font-heading font-extrabold text-xl sm:text-2xl tracking-tight">You&apos;re in.</div>
            <div className="text-ink-500 text-sm mt-0.5">
              {joined.already_joined ? "Already on the list " : "Reserved seat "}
              for <span className="font-semibold text-ink-900">{email}</span>
            </div>
          </div>
        </div>

        {/* Position badge */}
        <div className="mt-5 rounded-xl bg-gradient-to-br from-brand-600 to-violet-600 text-white p-5 flex items-center justify-between" data-testid="waitlist-position-badge">
          <div>
            <div className="text-[10px] uppercase tracking-widest opacity-80 font-semibold">Your position</div>
            <div className="font-heading font-extrabold text-4xl sm:text-5xl tracking-tighter mt-0.5">
              #{joined.position}
            </div>
          </div>
          <div className="text-right text-xs opacity-90 max-w-[180px]">
            We&apos;ll email you the moment early access opens for your slot.
          </div>
        </div>

        {/* Share-back CTA */}
        <div className="mt-5">
          <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Move up the queue</div>
          <p className="text-sm text-ink-700 mt-1">
            Share with a founder or creator who ships content — every signup from your link bumps you higher.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" onClick={openLinkedIn}
              className="rounded-full bg-brand-600 hover:bg-brand-700 text-white"
              data-testid="waitlist-share-linkedin">
              <Sparkles className="w-4 h-4 mr-2" /> Share on LinkedIn
            </Button>
            <Button type="button" variant="outline" onClick={openTwitter}
              className="rounded-full text-ink-900"
              data-testid="waitlist-share-twitter">
              Share on X
            </Button>
            <Button type="button" variant="outline" onClick={copyReferral}
              className="rounded-full text-ink-900"
              data-testid="waitlist-copy-referral">
              Copy referral link
            </Button>
          </div>
          <div className="mt-3 rounded-lg bg-ink-50 border border-ink-200 px-3 py-2 text-xs font-mono text-ink-500 break-all" data-testid="waitlist-referral-url">
            {referralUrl}
          </div>
        </div>
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
