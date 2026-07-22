import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { CalendarClock, Loader2, Sparkles, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import { track, getAttribution } from "@/lib/analytics";
import { toast } from "sonner";

export default function BookDemoDialog({ open, onOpenChange, source = "unknown" }) {
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [seats, setSeats] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!email.includes("@")) return toast.error("Enter a work email");
    setBusy(true);
    track("book_demo_submit", { source, company, seats });
    try {
      const attr = getAttribution();
      // We piggy-back on /waitlist with plan_interest=enterprise + use_case="Demo request"
      await api.post("/waitlist", {
        email,
        name: company || undefined,
        plan_interest: "enterprise",
        use_case: `DEMO_REQUEST · seats=${seats || "?"} · notes=${notes || "-"}`,
        referrer: document.referrer || undefined,
        source: attr?.source, medium: attr?.medium, campaign: attr?.campaign,
      });
      track("book_demo_success", { source });
      setDone(true);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Something went wrong");
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { onOpenChange(v); if (!v) setDone(false); }}>
      <DialogContent className="sm:max-w-lg" data-testid="book-demo-dialog">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-brand-600 flex items-center justify-center">
              <CalendarClock className="w-5 h-5 text-white" />
            </div>
            <div>
              <DialogTitle className="font-heading tracking-tight text-2xl">Book a demo</DialogTitle>
              <DialogDescription className="text-sm text-ink-500">
                A 20-minute walkthrough for agencies &amp; enterprise teams.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {done ? (
          <div className="p-2" data-testid="book-demo-success">
            <div className="flex items-start gap-3 rounded-xl bg-brand-50 border border-brand-100 p-4">
              <CheckCircle2 className="w-6 h-6 text-brand-600 shrink-0" />
              <div>
                <div className="font-heading font-bold text-brand-900">Request received.</div>
                <p className="mt-1 text-sm text-ink-700">
                  We&apos;ll reach out at <span className="font-semibold">{email}</span> within
                  one business day with a calendar link.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Work email</label>
              <Input required type="email" value={email} onChange={(e)=>setEmail(e.target.value)}
                placeholder="you@company.com" className="mt-1.5 h-11" data-testid="demo-email" />
            </div>
            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Company</label>
                <Input value={company} onChange={(e)=>setCompany(e.target.value)}
                  placeholder="Acme Media" className="mt-1.5 h-11" data-testid="demo-company" />
              </div>
              <div>
                <label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Team seats</label>
                <Input value={seats} onChange={(e)=>setSeats(e.target.value)}
                  placeholder="5+" className="mt-1.5 h-11" data-testid="demo-seats" />
              </div>
            </div>
            <div>
              <label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">What&apos;s your use case?</label>
              <Textarea rows={3} value={notes} onChange={(e)=>setNotes(e.target.value)}
                placeholder="e.g. Weekly product explainers for our sales team"
                className="mt-1.5" data-testid="demo-notes" />
            </div>
            <Button type="submit" disabled={busy}
              className="w-full h-12 rounded-full bg-brand-600 hover:bg-brand-700 text-white text-base"
              data-testid="demo-submit">
              {busy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Sending…</> :
                      <><Sparkles className="w-4 h-4 mr-2" /> Request a demo</>}
            </Button>
            <p className="text-[11px] text-ink-500 text-center">
              This is a placeholder — we&apos;ll confirm a real slot by email during private beta.
            </p>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
