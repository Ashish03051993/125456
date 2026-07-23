import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Video, LogIn, Loader2 } from "lucide-react";
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

export default function Login() {
  const { user, loading, setUser } = useAuth();
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (loading) return;
    if (user) navigate("/dashboard", { replace: true });
  }, [user, loading, navigate]);

  useEffect(() => { track("page_view", { page: "login" }); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const { data } = await api.post("/auth/login", { identifier: identifier.trim(), password });
      setUser(data.user);
      track("login_success", { method: "password" });
      navigate("/dashboard", { replace: true });
    } catch (e2) {
      setErr(formatApiError(e2.response?.data?.detail) || e2.message);
      track("login_failed", { method: "password" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-ink-50 flex flex-col" data-testid="login-page">
      <div className="max-w-md w-full mx-auto px-4 pt-10 pb-6">
        <Link to="/" className="flex items-center gap-2 mb-8" data-testid="brand-link">
          <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center shadow-sm">
            <Video className="w-5 h-5 text-white" />
          </div>
          <div className="font-heading font-extrabold text-lg tracking-tight">AI Video<span className="text-brand-600">Studio</span></div>
        </Link>

        <div className="bg-white rounded-2xl shadow-sm border border-ink-200 p-6 sm:p-8">
          <h1 className="font-heading text-3xl font-black tracking-tight text-ink-900" data-testid="login-title">Welcome back</h1>
          <p className="text-ink-500 mt-1 text-sm">Log in to continue creating videos.</p>

          <form onSubmit={submit} className="mt-6 space-y-4" data-testid="login-form">
            <div>
              <Label htmlFor="identifier" className="text-ink-700">Email or mobile</Label>
              <Input id="identifier" data-testid="login-identifier-input"
                value={identifier} onChange={(e) => setIdentifier(e.target.value)}
                placeholder="you@example.com or +91xxxxxxxxxx"
                autoComplete="username" required className="mt-1.5" />
            </div>
            <div>
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-ink-700">Password</Label>
                <Link to="/forgot-password" className="text-xs text-brand-600 hover:underline font-semibold" data-testid="link-forgot-password">Forgot password?</Link>
              </div>
              <Input id="password" type="password" data-testid="login-password-input"
                value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="Your password" autoComplete="current-password" required
                minLength={8} className="mt-1.5" />
            </div>

            {err && <div className="text-sm text-rose-600 bg-rose-50 border border-rose-200 px-3 py-2 rounded-md" data-testid="login-error">{err}</div>}

            <Button type="submit" disabled={busy}
              className="w-full h-11 rounded-full bg-brand-600 hover:bg-brand-700 text-white font-semibold"
              data-testid="login-submit-btn">
              {busy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Logging in…</> : <><LogIn className="w-4 h-4 mr-2" /> Log in</>}
            </Button>
          </form>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-ink-200" /></div>
            <div className="relative flex justify-center text-xs uppercase tracking-widest">
              <span className="bg-white px-3 text-ink-500 font-semibold">or</span>
            </div>
          </div>

          <Button type="button" variant="outline"
            onClick={() => { track("signin_click", { method: "google", source: "login_page" }); googleLogin(); }}
            className="w-full h-11 rounded-full border-ink-300 hover:bg-ink-50 font-semibold"
            data-testid="login-google-btn">
            <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09A6.98 6.98 0 0 1 5.5 12c0-.72.13-1.43.34-2.09V7.07H2.18A11 11 0 0 0 1 12c0 1.77.42 3.45 1.18 4.93l3.66-2.84z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"/></svg>
            Continue with Google
          </Button>

          <p className="text-sm text-ink-500 text-center mt-6">
            Don't have an account?{" "}
            <Link to="/signup" className="text-brand-600 font-semibold hover:underline" data-testid="link-to-signup">Sign up free</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
