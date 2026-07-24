import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import usePageTitle from "@/lib/usePageTitle";
import { Video, Sparkles, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { login as googleLogin } from "@/pages/AuthCallback";
import { track } from "@/lib/analytics";

function formatApiError(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default function Signup() {
  usePageTitle("Sign up free");
  const { user, loading, setUser } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [identifier, setIdentifier] = useState("");   // email OR mobile (required)
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [refCode, setRefCode] = useState("");

  useEffect(() => {
    if (loading) return;
    if (user) navigate("/dashboard", { replace: true });
  }, [user, loading, navigate]);

  // Pick up referral code — precedence: URL `?ref=` > localStorage (persisted
  // by the public share page when the viewer opened /v/:slug). Cleared once
  // signup succeeds so it doesn't leak into a future session.
  useEffect(() => {
    try {
      const q = new URLSearchParams(window.location.search);
      const urlRef = (q.get("ref") || "").trim().toUpperCase();
      const stashed = (localStorage.getItem("avs_pending_referral") || "").trim().toUpperCase();
      const r = urlRef || stashed;
      if (/^[A-Z0-9]{4,10}$/.test(r)) {
        setRefCode(r);
        track("referral_landing", { code: r, source: urlRef ? "url" : "storage" });
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { track("page_view", { page: "signup" }); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    if (password !== confirm) { setErr("Passwords do not match."); return; }
    if (password.length < 8) { setErr("Password must be at least 8 characters."); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/auth/register", {
        name: name.trim(),
        identifier: identifier.trim(),
        password,
        ...(refCode ? { referral_code: refCode } : {}),
      });
      setUser(data.user);
      try { localStorage.removeItem("avs_pending_referral"); } catch {}
      track("signup_success", { method: "password", linked: !!data.linked, referred: !!data.referred_by });
      navigate("/dashboard", { replace: true });
    } catch (e2) {
      setErr(formatApiError(e2.response?.data?.detail) || e2.message);
      track("signup_failed", { method: "password" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-ink-50 flex flex-col" data-testid="signup-page">
      <div className="max-w-md w-full mx-auto px-4 pt-10 pb-6">
        <Link to="/" className="flex items-center gap-2 mb-8" data-testid="brand-link">
          <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center shadow-sm">
            <Video className="w-5 h-5 text-white" />
          </div>
          <div className="font-heading font-extrabold text-lg tracking-tight">AI Video<span className="text-brand-600">Studio</span></div>
        </Link>

        <div className="bg-white rounded-2xl shadow-sm border border-ink-200 p-6 sm:p-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-brand-100 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700 mb-3">
            <Sparkles className="w-3.5 h-3.5" /> 3 free credits every month
          </div>
          <h1 className="font-heading text-3xl font-black tracking-tight text-ink-900" data-testid="signup-title">Create your account</h1>
          <p className="text-ink-500 mt-1 text-sm">Your first 30-second video is on us.</p>

          {refCode && (
            <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2.5 flex items-start gap-2.5" data-testid="referral-banner">
              <Sparkles className="w-4 h-4 text-emerald-700 mt-0.5 shrink-0" />
              <div className="text-sm text-emerald-900">
                <span className="font-semibold">You&apos;re invited!</span> You&apos;ll get <span className="font-bold">3 bonus credits</span> when you sign up
                <span className="font-mono text-emerald-800 ml-1">({refCode})</span>.
              </div>
            </div>
          )}

          <form onSubmit={submit} className="mt-6 space-y-4" data-testid="signup-form">
            <div>
              <Label htmlFor="name" className="text-ink-700">Full name</Label>
              <Input id="name" data-testid="signup-name-input"
                value={name} onChange={(e) => setName(e.target.value)}
                placeholder="Jane Doe" autoComplete="name" required minLength={2} className="mt-1.5" />
            </div>
            <div>
              <Label htmlFor="identifier" className="text-ink-700">Email or mobile</Label>
              <Input id="identifier" data-testid="signup-identifier-input"
                value={identifier} onChange={(e) => setIdentifier(e.target.value)}
                placeholder="you@example.com or +91xxxxxxxxxx"
                autoComplete="username" required className="mt-1.5" />
              <p className="text-xs text-ink-500 mt-1">Use either an email address or a mobile number as your login ID.</p>
            </div>
            <div>
              <Label htmlFor="password" className="text-ink-700">Password</Label>
              <Input id="password" type="password" data-testid="signup-password-input"
                value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters" autoComplete="new-password" required
                minLength={8} className="mt-1.5" />
            </div>
            <div>
              <Label htmlFor="confirm" className="text-ink-700">Confirm password</Label>
              <Input id="confirm" type="password" data-testid="signup-confirm-input"
                value={confirm} onChange={(e) => setConfirm(e.target.value)}
                placeholder="Re-enter password" autoComplete="new-password" required
                minLength={8} className="mt-1.5" />
            </div>

            {err && <div className="text-sm text-rose-600 bg-rose-50 border border-rose-200 px-3 py-2 rounded-md" data-testid="signup-error">{err}</div>}

            <Button type="submit" disabled={busy}
              className="w-full h-11 rounded-full bg-brand-600 hover:bg-brand-700 text-white font-semibold"
              data-testid="signup-submit-btn">
              {busy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Creating account…</> : <><Sparkles className="w-4 h-4 mr-2" /> Create account</>}
            </Button>
          </form>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-ink-200" /></div>
            <div className="relative flex justify-center text-xs uppercase tracking-widest">
              <span className="bg-white px-3 text-ink-500 font-semibold">or</span>
            </div>
          </div>

          <Button type="button" variant="outline"
            onClick={() => { track("signup_click", { method: "google", source: "signup_page" }); googleLogin(); }}
            className="w-full h-11 rounded-full border-ink-300 hover:bg-ink-50 font-semibold"
            data-testid="signup-google-btn">
            <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09A6.98 6.98 0 0 1 5.5 12c0-.72.13-1.43.34-2.09V7.07H2.18A11 11 0 0 0 1 12c0 1.77.42 3.45 1.18 4.93l3.66-2.84z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"/></svg>
            Continue with Google
          </Button>

          <p className="text-sm text-ink-500 text-center mt-6">
            Already have an account?{" "}
            <Link to="/login" className="text-brand-600 font-semibold hover:underline" data-testid="link-to-login">Log in</Link>
          </p>
          <p className="text-xs text-ink-400 text-center mt-3">
            By creating an account, you agree to our{" "}
            <Link to="/terms" className="underline hover:text-brand-600" data-testid="signup-terms-link">Terms</Link>{" "}
            and{" "}
            <Link to="/privacy" className="underline hover:text-brand-600" data-testid="signup-privacy-link">Privacy Policy</Link>.
            You&apos;ll get 3 free credits every month.
          </p>
        </div>
      </div>
    </div>
  );
}
