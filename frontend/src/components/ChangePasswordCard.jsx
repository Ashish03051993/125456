import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { KeyRound, Eye, EyeOff, Loader2, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

// Change-password card. Requires the current password unless the user is a
// Google-only account that has never set one (in which case the backend accepts
// no current password and simply attaches one). Always invalidates all other
// sessions after a successful change.
export default function ChangePasswordCard() {
  const { user, setUser } = useAuth();
  const isPasswordless = !(user?.auth_methods || []).includes("password");

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [ok, setOk] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setOk(false);
    if (next.length < 8)     { toast.error("New password must be at least 8 characters"); return; }
    if (next !== confirm)    { toast.error("Passwords don't match"); return; }
    if (!isPasswordless && !current) { toast.error("Current password required"); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/auth/change-password", {
        current_password: current,
        new_password: next,
      });
      if (data.user) setUser(data.user);
      toast.success("Password updated", { description: "All other devices have been signed out." });
      setOk(true); setCurrent(""); setNext(""); setConfirm("");
    } catch (e2) {
      toast.error(e2?.response?.data?.detail || "Couldn't update password");
    } finally { setBusy(false); }
  };

  return (
    <div className="bg-white border border-ink-200 rounded-2xl p-6" data-testid="change-password-card">
      <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-ink-500 font-semibold">
        <KeyRound className="w-3.5 h-3.5 text-brand-600" /> Password
      </div>
      <div className="mt-2 font-heading font-bold text-lg">
        {isPasswordless ? "Set a password" : "Change password"}
      </div>
      <p className="text-sm text-ink-500 mt-1">
        {isPasswordless
          ? "You signed in with Google. Set a password to also log in with your email."
          : "You'll be signed out of every other browser and device after the change."}
      </p>

      <form onSubmit={submit} className="mt-5 space-y-3">
        {!isPasswordless && (
          <div>
            <label className="text-xs font-semibold text-ink-700">Current password</label>
            <Input type="password" value={current} onChange={(e) => setCurrent(e.target.value)}
                   autoComplete="current-password"
                   className="mt-1" data-testid="cpw-current-input" required={!isPasswordless} />
          </div>
        )}
        <div>
          <label className="text-xs font-semibold text-ink-700">New password</label>
          <div className="relative">
            <Input type={showNew ? "text" : "password"} value={next} onChange={(e) => setNext(e.target.value)}
                   autoComplete="new-password" minLength={8}
                   className="mt-1 pr-9" data-testid="cpw-new-input" />
            <button type="button" onClick={() => setShowNew(!showNew)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-700"
                    aria-label={showNew ? "Hide password" : "Show password"}
                    data-testid="cpw-show-toggle">
              {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <div className="mt-1 text-[11px] text-ink-500">Minimum 8 characters.</div>
        </div>
        <div>
          <label className="text-xs font-semibold text-ink-700">Confirm new password</label>
          <Input type={showNew ? "text" : "password"} value={confirm} onChange={(e) => setConfirm(e.target.value)}
                 autoComplete="new-password" minLength={8}
                 className="mt-1" data-testid="cpw-confirm-input" />
        </div>
        <div className="flex items-center gap-3 pt-2">
          <Button type="submit" disabled={busy}
                  className="rounded-full bg-brand-600 hover:bg-brand-700 text-white"
                  data-testid="cpw-submit-btn">
            {busy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Updating…</>
                  : isPasswordless ? "Set password" : "Update password"}
          </Button>
          {ok && (
            <span className="inline-flex items-center gap-1.5 text-emerald-700 text-sm" data-testid="cpw-success">
              <CheckCircle2 className="w-4 h-4" /> Updated
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
