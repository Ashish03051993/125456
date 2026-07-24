import { useEffect, useState, useMemo } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import axios from "axios";
import { Video, Sparkles, Loader2, Eye, Play, PlayCircle, Gift } from "lucide-react";
import { Button } from "@/components/ui/button";
import { track } from "@/lib/analytics";

const API = process.env.REACT_APP_BACKEND_URL;
const PENDING_REF_KEY = "avs_pending_referral";

export default function PublicVideo() {
  const { slug } = useParams();
  const [search] = useSearchParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await axios.get(`${API}/api/public/videos/${slug}`);
        if (alive) { setData(data); track("public_video_view", { slug }); }
      } catch (e) {
        if (alive) setErr(e?.response?.status === 404 ? "This video is no longer available." : "Something went wrong.");
      }
    })();
    return () => { alive = false; };
  }, [slug]);

  // Pick the effective referral code: URL `?ref=` beats the creator's own
  // fallback code. Whichever wins, we persist it so it survives navigation
  // through login → signup pages (the signup page reads it for the bonus).
  const refCode = useMemo(() => {
    const urlRef = (search.get("ref") || "").trim().toUpperCase();
    const fallback = (data?.creator_ref_code || "").trim().toUpperCase();
    return urlRef || fallback || null;
  }, [search, data]);

  useEffect(() => {
    if (!refCode) return;
    try { localStorage.setItem(PENDING_REF_KEY, refCode); } catch {}
  }, [refCode]);

  const signupHref = refCode ? `/signup?ref=${encodeURIComponent(refCode)}` : "/signup";

  const videoSrc = useMemo(() => {
    if (!data?.video_url) return null;
    return `${API}${data.video_url}`;
  }, [data]);

  if (err) {
    return (
      <div className="min-h-screen bg-ink-900 text-white flex flex-col items-center justify-center px-4" data-testid="public-video-error">
        <div className="w-14 h-14 rounded-2xl bg-ink-700 flex items-center justify-center mb-4">
          <Video className="w-7 h-7 text-ink-400" />
        </div>
        <h1 className="font-heading text-3xl font-black tracking-tight text-center">{err}</h1>
        <p className="text-ink-400 mt-2 text-center max-w-md">The creator may have made this private, or the link has expired.</p>
        <Link to="/" className="mt-6">
          <Button className="rounded-full bg-brand-600 hover:bg-brand-700 text-white px-6 h-11" data-testid="err-cta">
            <Sparkles className="w-4 h-4 mr-2" /> Make your own with AI Video Studio
          </Button>
        </Link>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-ink-900 text-white flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-ink-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-ink-900 text-white" data-testid="public-video-page">
      {/* Sticky top bar */}
      <header className="sticky top-0 z-40 backdrop-blur-md bg-ink-900/70 border-b border-white/5">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 group" data-testid="brand-link">
            <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center shadow-lg shadow-brand-600/40 group-hover:rotate-6 transition-transform">
              <Video className="w-5 h-5 text-white" />
            </div>
            <div className="font-heading font-extrabold text-lg tracking-tight">AI Video<span className="text-brand-500">Studio</span></div>
          </Link>
          <Link to={signupHref} data-testid="topbar-signup">
            <Button className="rounded-full bg-brand-600 hover:bg-brand-700 text-white px-4 sm:px-5 h-9 text-sm font-semibold">
              <Sparkles className="w-3.5 h-3.5 mr-1.5" /> Make yours free
            </Button>
          </Link>
        </div>
      </header>

      {/* Video hero */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
        <div className="flex flex-wrap items-center gap-3 text-xs text-ink-400 uppercase tracking-widest font-semibold">
          <span>{data.style}</span>
          <span className="w-1 h-1 rounded-full bg-ink-600" />
          <span>{data.duration_sec}s</span>
          <span className="w-1 h-1 rounded-full bg-ink-600" />
          <span>{data.language}</span>
          {data.has_animated_scenes && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gradient-to-r from-purple-600 to-brand-600 text-white normal-case tracking-normal font-semibold text-[10px] shadow-lg shadow-purple-900/40"
                  data-testid="sora-animated-badge">
              ✨ AI-Animated · Sora 2
            </span>
          )}
          <span className="ml-auto inline-flex items-center gap-1.5 text-ink-500">
            <Eye className="w-3.5 h-3.5" /> <span className="normal-case tracking-normal" data-testid="view-count">{data.view_count.toLocaleString()} views</span>
          </span>
        </div>

        <h1 className="mt-3 font-heading text-3xl sm:text-5xl font-black tracking-tighter" data-testid="video-title">
          {data.title}
        </h1>
        {data.hook && <p className="mt-3 text-ink-200 text-base sm:text-lg max-w-2xl italic">{data.hook}</p>}

        <div className="mt-6 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center font-bold text-sm shadow-lg">
            {(data.creator_name || "K").charAt(0).toUpperCase()}
          </div>
          <div>
            <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Made by</div>
            <div className="font-heading font-bold" data-testid="creator-name">{data.creator_name}</div>
          </div>
        </div>

        {/* Player */}
        <div className="mt-8 relative rounded-2xl overflow-hidden bg-black ring-1 ring-white/10 shadow-2xl shadow-black/50 aspect-video">
          {videoSrc ? (
            <video src={videoSrc} poster={data.thumbnail_url ? `${API}${data.thumbnail_url}` : undefined} controls className="w-full h-full object-contain" data-testid="public-video-player" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-ink-500">
              <PlayCircle className="w-14 h-14" />
            </div>
          )}
        </div>

        {/* Made-with-AI-Video-Studio CTA ribbon */}
        <div className="mt-10 rounded-2xl bg-gradient-to-r from-brand-600 to-indigo-600 p-6 sm:p-8 shadow-lg shadow-brand-900/30" data-testid="hero-cta-ribbon">
          {refCode && (
            <div className="mb-3 inline-flex items-center gap-1.5 rounded-full bg-white/15 backdrop-blur px-3 py-1 text-[11px] font-bold text-white uppercase tracking-widest border border-white/20"
                 data-testid="invite-chip">
              <Gift className="w-3.5 h-3.5" /> You&apos;ve been invited by {data.creator_name} — claim 3 free credits
            </div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="text-xs uppercase tracking-widest text-white/70 font-bold">Made with</div>
              <div className="mt-1 font-heading text-2xl sm:text-3xl font-black tracking-tighter">AI Video Studio</div>
              <p className="text-white/80 text-sm mt-2 max-w-lg">
                {refCode
                  ? "Turn any topic into a polished video — script, visuals, voice — all approved by you. Sign up with this invite and start with 3 bonus credits on the house."
                  : "Turn any topic into a polished video — approve the script, the visuals and the voice, then download in seconds. Your first 30-second video is on us, every month."}
              </p>
            </div>
            <Link to={signupHref} data-testid="hero-cta-signup">
              <Button className="rounded-full bg-white text-brand-700 hover:bg-white/90 h-12 px-6 font-bold shadow-lg">
                <Sparkles className="w-4 h-4 mr-2" /> {refCode ? "Claim my 3 credits" : "Create yours free"}
              </Button>
            </Link>
          </div>
        </div>

        {/* Storyboard preview */}
        {data.scenes?.length > 0 && (
          <div className="mt-12">
            <div className="text-xs uppercase tracking-widest text-brand-500 font-bold">Storyboard</div>
            <h2 className="mt-1 font-heading text-2xl sm:text-3xl font-black tracking-tight">Behind the scenes</h2>
            <div className="mt-6 grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {data.scenes.map((sc) => (
                <div key={sc.idx} className="rounded-xl overflow-hidden bg-ink-900 ring-1 ring-white/5" data-testid={`public-scene-${sc.idx}`}>
                  <div className="aspect-video bg-black relative">
                    {sc.image_url && (
                      <img src={`${API}${sc.image_url}`} alt={sc.heading}
                           className="w-full h-full object-cover opacity-90" />
                    )}
                    <div className="absolute bottom-2 left-2 bg-black/70 text-white text-[10px] px-2 py-0.5 rounded font-mono">
                      #{sc.idx + 1}
                    </div>
                  </div>
                  <div className="p-3">
                    <div className="text-xs text-brand-500 font-mono">&ldquo;{sc.subtitle}&rdquo;</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      <footer className="mt-16 border-t border-white/5 py-8 text-center text-xs text-ink-500">
        <Link to="/" className="hover:text-white transition-colors">© AI Video Studio · Made with love</Link>
      </footer>
    </div>
  );
}
