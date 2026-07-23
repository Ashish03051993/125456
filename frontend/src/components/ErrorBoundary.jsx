import { Component } from "react";

/**
 * Wraps the entire app so a React render crash shows a friendly retry
 * screen instead of a white page. Also logs the error to the backend
 * so we can spot regressions in production without user reports.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message || "Unknown error" };
  }

  componentDidCatch(error, info) {
    // Fire-and-forget log to backend
    try {
      fetch(`${process.env.REACT_APP_BACKEND_URL}/api/analytics/track`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          event: "frontend_error",
          properties: {
            message: (error?.message || "").slice(0, 200),
            stack: (error?.stack || "").slice(0, 500),
            component_stack: (info?.componentStack || "").slice(0, 500),
            url: window.location.pathname,
          },
          session_id: localStorage.getItem("avs_session_id") || null,
          path: window.location.pathname,
        }),
      }).catch(() => { /* logging is best-effort */ });
    } catch { /* ignore */ }
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="min-h-screen flex items-center justify-center bg-ink-50 px-4" data-testid="error-boundary">
        <div className="max-w-md w-full bg-white border border-ink-200 rounded-2xl p-8 text-center shadow-sm">
          <div className="mx-auto w-14 h-14 rounded-full bg-red-50 flex items-center justify-center">
            <svg className="w-7 h-7 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M4.93 19h14.14a2 2 0 001.732-3l-7.07-12.24a2 2 0 00-3.464 0L3.196 16a2 2 0 001.732 3z" />
            </svg>
          </div>
          <h1 className="mt-5 font-heading font-extrabold text-2xl tracking-tight">Something went wrong</h1>
          <p className="mt-2 text-sm text-ink-500">
            The page ran into an unexpected error. We&apos;ve been notified — try reloading, and if it keeps happening please reach out.
          </p>
          <div className="mt-5 flex justify-center gap-2">
            <button onClick={() => window.location.reload()}
              className="rounded-full bg-brand-600 hover:bg-brand-700 text-white px-5 h-10 text-sm font-semibold"
              data-testid="error-reload-btn">
              Reload page
            </button>
            <button onClick={() => { window.location.href = "/"; }}
              className="rounded-full border border-ink-200 hover:border-brand-600 text-ink-900 px-5 h-10 text-sm font-semibold"
              data-testid="error-home-btn">
              Go home
            </button>
          </div>
          {this.state.message && (
            <details className="mt-4 text-left text-xs text-ink-400">
              <summary className="cursor-pointer">Technical details</summary>
              <div className="mt-2 font-mono bg-ink-50 rounded-lg p-2 break-words">{this.state.message}</div>
            </details>
          )}
        </div>
      </div>
    );
  }
}
