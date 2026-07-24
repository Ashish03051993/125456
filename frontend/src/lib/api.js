import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
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

// Global 402 interceptor — surfaces structured payment-required errors
// as a `paywall:open` DOM event so <UpgradeModal> can render an in-context
// upgrade experience instead of a raw toast. Callers should still `.catch(...)`
// their own promise chain; the interceptor rethrows so nothing breaks.
api.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err?.response?.status;
    const detail = err?.response?.data?.detail;
    // Structured 402: detail is a dict with {message, code, ...}
    if (status === 402 && detail && typeof detail === "object" && detail.code) {
      try {
        window.dispatchEvent(new CustomEvent("paywall:open", { detail }));
      } catch {
        // no-op: SSR / non-browser environment
      }
    }
    return Promise.reject(err);
  },
);
