import { useState, useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import usePageTitle from "@/lib/usePageTitle";
import { Video, Loader2, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { track } from "@/lib/analytics";

function formatApiError(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default function ResetPassword() {
  usePageTitle("Set a new password");
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const { setUser } = useAuth();
  const nav = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => { track("page_view", { page: "reset_password", has_token: !!token }); }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    if (password.length < 8) return setErr("Password must be at least 8 characters.");
    if (password !== confirm) return setErr("Passwords do not match.");
    setBusy(true);
    try {
      const { data } = await api.post("/auth/reset-password", { token, password });
      setUser(data.user);
      track("password_reset_success");
      nav("/dashboard", { replace: true });
    } catch (e2) {
      setErr(formatApiError(e2.response?.data?.detail) || e2.message);
      track("password_reset_failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-ink-50 flex flex-col" data-testid="reset-page">
      <div className="max-w-md w-full mx-auto px-4 pt-10 pb-6">
        <Link to="/" className="flex items-center gap-2 mb-8" data-testid="brand-link">
          <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center shadow-sm">
            <Video className="w-5 h-5 text-white" />
          </div>
          <div className="font-heading font-extrabold text-lg tracking-tight">AI Video<span className="text-brand-600">Studio</span></div>
        </Link>

        <div className="bg-white rounded-2xl shadow-sm border border-ink-200 p-6 sm:p-8">
          <h1 className="font-heading text-3xl font-black tracking-tight text-ink-900" data-testid="reset-title">Set a new password</h1>
          <p className="text-ink-500 mt-1 text-sm">Pick something strong — at least 8 characters.</p>

          {!token ? (
            <div className="mt-6 bg-rose-50 border border-rose-200 rounded-xl p-4 text-sm text-rose-800" data-testid="reset-missing-token">
              This link is missing a reset token. Please{" "}
              <Link to="/forgot-password" className="underline font-semibold">request a new reset link</Link>.
            </div>
          ) : (
            <form onSubmit={submit} className="mt-6 space-y-4" data-testid="reset-form">
              <div>
                <Label htmlFor="password" className="text-ink-700">New password</Label>
                <Input id="password" type="password" data-testid="reset-password-input"
                  value={password} onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters" autoComplete="new-password" required
                  minLength={8} className="mt-1.5" />
              </div>
              <div>
                <Label htmlFor="confirm" className="text-ink-700">Confirm password</Label>
                <Input id="confirm" type="password" data-testid="reset-confirm-input"
                  value={confirm} onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Re-enter password" autoComplete="new-password" required
                  minLength={8} className="mt-1.5" />
              </div>

              {err && <div className="text-sm text-rose-600 bg-rose-50 border border-rose-200 px-3 py-2 rounded-md" data-testid="reset-error">{err}</div>}

              <Button type="submit" disabled={busy}
                className="w-full h-11 rounded-full bg-brand-600 hover:bg-brand-700 text-white font-semibold"
                data-testid="reset-submit-btn">
                {busy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving…</> : <><KeyRound className="w-4 h-4 mr-2" /> Reset password & log in</>}
              </Button>
            </form>
          )}

          <p className="text-sm text-ink-500 text-center mt-6">
            Remembered it?{" "}
            <Link to="/login" className="text-brand-600 font-semibold hover:underline" data-testid="reset-back-to-login">Log in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
