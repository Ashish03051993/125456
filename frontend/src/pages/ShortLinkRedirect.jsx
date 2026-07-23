import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Video, AlertCircle } from "lucide-react";

/**
 * Short-URL redirector. Route: /l/:slug
 * Fetches the mapped target from /api/short/:slug and does a full navigation
 * so that the browser keeps the utm_* params intact and captureAttribution
 * runs on the destination page.
 */
export default function ShortLinkRedirect() {
  const { slug } = useParams();
  const [error, setError] = useState(null);
  const fired = useRef(false);

  useEffect(() => {
    if (fired.current) return;
    fired.current = true;
    (async () => {
      try {
        const { data } = await api.get(`/short/${slug}`);
        if (data?.target) {
          window.location.replace(data.target);
          return;
        }
        setError("Link not found");
      } catch (e) {
        setError(e?.response?.status === 404 ? "Link not found" : "Something went wrong");
      }
    })();
  }, [slug]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-ink-50 px-6">
      <div className="max-w-md text-center" data-testid="short-link-page">
        {error ? (
          <>
            <div className="w-14 h-14 mx-auto rounded-full bg-red-50 border border-red-200 flex items-center justify-center">
              <AlertCircle className="w-6 h-6 text-red-600" />
            </div>
            <div className="mt-4 font-heading font-bold text-2xl tracking-tight" data-testid="short-link-error">{error}</div>
            <p className="mt-2 text-ink-500">The short URL <span className="font-mono">/l/{slug}</span> doesn&apos;t exist or was removed.</p>
            <a href="/" className="mt-6 inline-block text-brand-700 font-semibold hover:underline">Go to homepage →</a>
          </>
        ) : (
          <>
            <div className="w-14 h-14 mx-auto rounded-lg bg-brand-600 flex items-center justify-center animate-pulse">
              <Video className="w-7 h-7 text-white" />
            </div>
            <div className="mt-4 font-heading font-bold text-xl tracking-tight">Taking you there…</div>
            <p className="mt-1 text-ink-500 text-sm">Redirecting to Kadenza.</p>
          </>
        )}
      </div>
    </div>
  );
}
