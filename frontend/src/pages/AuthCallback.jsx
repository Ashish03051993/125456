// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, setAuthToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function login() {
  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  const redirectUrl = window.location.origin + "/auth/callback";
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
}

// Module-level guard that survives React 18 StrictMode's double-mount and any
// component remount. Emergent OAuth session_ids are single-use — a second POST
// with the same id returns 401 and breaks sign-in silently.
const _consumedSessionIds = new Set();

export default function AuthCallback() {
  const location = useLocation();
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [msg, setMsg] = useState("Signing you in…");

  useEffect(() => {
    const hash = location.hash || window.location.hash;
    const m = hash.match(/session_id=([^&]+)/);
    if (!m) { navigate("/", { replace: true }); return; }
    const sid = m[1];
    if (_consumedSessionIds.has(sid)) return;   // StrictMode double-fire guard
    _consumedSessionIds.add(sid);
    (async () => {
      try {
        const { data } = await api.post("/auth/session", { session_id: sid });
        // Bearer token is also auto-captured by the axios response interceptor,
        // but set it explicitly here as a safety net.
        if (data.token) setAuthToken(data.token);
        setUser(data.user);
        navigate("/dashboard", { replace: true, state: { user: data.user } });
      } catch (e) {
        setMsg("Sign-in failed. Redirecting…");
        setTimeout(() => navigate("/", { replace: true }), 1500);
      }
    })();
  }, [location, navigate, setUser]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-ink-50">
      <div className="text-ink-700 font-heading text-xl">{msg}</div>
    </div>
  );
}
