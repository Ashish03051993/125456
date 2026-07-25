import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Local storage key for the Bearer session token. We prefer Bearer auth over
// cookies because the preview proxy rewrites `Access-Control-Allow-Origin` to
// `*`, which combined with `credentials: true` causes browsers to silently
// drop the session cookie on cross-origin (.static.emergentagent.com) hosts.
const TOKEN_KEY = "avs_auth_token";
export const getAuthToken = () => {
  try { return localStorage.getItem(TOKEN_KEY) || null; } catch { return null; }
};
export const setAuthToken = (tok) => {
  try {
    if (tok) localStorage.setItem(TOKEN_KEY, tok);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {}
};

export const api = axios.create({
  baseURL: API,
  withCredentials: true,   // still send cookie when same-origin — belt & braces
});

// Attach Authorization: Bearer <token> on every outgoing request so auth
// survives cross-origin previews where the cookie gets stripped.
api.interceptors.request.use((cfg) => {
  const t = getAuthToken();
  if (t) {
    cfg.headers = cfg.headers || {};
    cfg.headers.Authorization = `Bearer ${t}`;
  }
  return cfg;
});

// If any endpoint returns a fresh `token`, capture it so subsequent requests
// use it automatically. Login/register/session/password-reset all do this.
api.interceptors.response.use((res) => {
  const tok = res?.data?.token;
  if (typeof tok === "string" && tok.length > 10) setAuthToken(tok);
  return res;
}, (err) => {
  const status = err?.response?.status;
  const detail = err?.response?.data?.detail;
  // Structured 402: detail is a dict with {message, code, ...}
  if (status === 402 && detail && typeof detail === "object" && detail.code) {
    try {
      window.dispatchEvent(new CustomEvent("paywall:open", { detail }));
    } catch {}
  }
  return Promise.reject(err);
});

// Resolves any media path returned by the backend to a fully-qualified URL.
// The backend serves generated files at `/api/media/...` but a chunk of
// pre-existing DB rows store the legacy `/media/...` form (without the `/api`
// prefix). Handles both without touching absolute URLs.
export const resolveMediaUrl = (path) => {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;             // already absolute
  const withApi = path.startsWith("/api/") ? path : `/api${path.startsWith("/") ? "" : "/"}${path}`;
  return `${process.env.REACT_APP_BACKEND_URL}${withApi}`;
};
