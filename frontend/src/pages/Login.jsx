import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { useNavigate } from "react-router-dom";
import { login } from "@/pages/AuthCallback";

export default function Login() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (loading) return;
    if (user) { navigate("/dashboard", { replace: true }); return; }
    // Kick off Google OAuth immediately
    login();
  }, [user, loading, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-ink-50" data-testid="login-page">
      <div className="text-ink-700 font-heading text-xl">Redirecting to sign in…</div>
    </div>
  );
}
