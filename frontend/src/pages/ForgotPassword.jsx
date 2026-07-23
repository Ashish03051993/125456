import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Video, Loader2, ArrowLeft, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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

export default function ForgotPassword() {
  const [identifier, setIdentifier] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [devHint, setDevHint] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => { track("page_view", { page: "forgot_password" }); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      const { data } = await api.post("/auth/forgot-password", { identifier: identifier.trim() });
      setSent(true);
      // In dev/staging when RESEND is not configured, backend returns delivery:"logged"
      if (data.delivery === "logged") {
        setDevHint("Delivery: dev mode — the reset link was written to the backend logs (email will be enabled once Resend is configured).");
      }
      track("forgot_password_submitted");
    } catch (e2) {
      setErr(formatApiError(e2.response?.data?.detail) || e2.message);
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-ink-50 flex flex-col" data-testid="forgot-page">
      <div className="max-w-md w-full mx-auto px-4 pt-10 pb-6">
        <Link to="/" className="flex items-center gap-2 mb-8" data-testid="brand-link">
          <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center shadow-sm">
            <Video className="w-5 h-5 text-white" />
          </div>
          <div className="font-heading font-extrabold text-lg tracking-tight">AI Video<span className="text-brand-600">Studio</span></div>
        </Link>

        <div className="bg-white rounded-2xl shadow-sm border border-ink-200 p-6 sm:p-8">
          <Link to="/login" className="inline-flex items-center gap-1 text-xs text-ink-500 hover:text-ink-900 mb-4" data-testid="back-to-login">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to login
          </Link>
          <h1 className="font-heading text-3xl font-black tracking-tight text-ink-900" data-testid="forgot-title">Forgot password?</h1>
          <p className="text-ink-500 mt-1 text-sm">Enter your email and we&apos;ll send you a reset link. Link expires in 1 hour.</p>

          {!sent ? (
            <form onSubmit={submit} className="mt-6 space-y-4" data-testid="forgot-form">
              <div>
                <Label htmlFor="identifier" className="text-ink-700">Email address</Label>
                <Input id="identifier" type="email" data-testid="forgot-identifier-input"
                  value={identifier} onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="you@example.com"
                  autoComplete="username" required className="mt-1.5" />
                <p className="text-xs text-ink-400 mt-1">SMS-based reset for mobile-only accounts is coming soon.</p>
              </div>
              {err && <div className="text-sm text-rose-600 bg-rose-50 border border-rose-200 px-3 py-2 rounded-md" data-testid="forgot-error">{err}</div>}
              <Button type="submit" disabled={busy}
                className="w-full h-11 rounded-full bg-brand-600 hover:bg-brand-700 text-white font-semibold"
                data-testid="forgot-submit-btn">
                {busy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Sending…</> : <><Mail className="w-4 h-4 mr-2" /> Send reset link</>}
              </Button>
            </form>
          ) : (
            <div className="mt-6 space-y-4" data-testid="forgot-sent">
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-full bg-emerald-600 flex items-center justify-center shrink-0">
                    <Mail className="w-4 h-4 text-white" />
                  </div>
                  <div className="min-w-0">
                    <div className="font-heading font-bold text-emerald-900">Check your inbox</div>
                    <p className="text-sm text-emerald-800 mt-1">
                      If an account matches <span className="font-semibold">{identifier}</span>, a reset link is on the way. Check spam if it doesn&apos;t arrive in a couple of minutes.
                    </p>
                  </div>
                </div>
              </div>
              {devHint && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-900" data-testid="forgot-dev-hint">
                  <span className="font-semibold">Heads up:</span> {devHint}
                </div>
              )}
              <Link to="/login">
                <Button variant="outline" className="w-full rounded-full h-11" data-testid="forgot-back-btn">
                  Back to login
                </Button>
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
