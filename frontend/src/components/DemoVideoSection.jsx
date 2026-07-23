import { useCallback, useEffect, useRef, useState } from "react";
import { Play, Sparkles, Video as VideoIcon, Linkedin, FileText, Mail, Youtube, Instagram, Facebook } from "lucide-react";
import { track } from "@/lib/analytics";

const OUTPUTS = [
  { icon: VideoIcon, label: "Cinematic Video",   sub: "MP4 · 16:9 + 9:16" },
  { icon: Youtube,   label: "YouTube Ready",     sub: "16:9 landscape master" },
  { icon: Instagram, label: "Instagram / Reels", sub: "9:16 vertical cut" },
  { icon: Facebook,  label: "Facebook Feed",     sub: "Square + caption ready" },
  { icon: Linkedin,  label: "LinkedIn Post",     sub: "Hook + thread ready" },
  { icon: FileText,  label: "Blog Article",      sub: "SEO-friendly long form" },
  { icon: Mail,      label: "Email Newsletter",  sub: "Personalized send-ready" },
];

export default function DemoVideoSection({ videoSrc, posterSrc }) {
  const videoRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [viewed, setViewed] = useState(false);

  // Fire view event when video is scrolled into view
  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting && !viewed) {
          setViewed(true);
          track("demo_video_impression");
        }
      });
    }, { threshold: 0.5 });
    io.observe(el);
    return () => io.disconnect();
  }, [viewed]);

  const play = useCallback(async () => {
    const el = videoRef.current;
    if (!el) return;
    try {
      await el.play();
      setPlaying(true);
      track("demo_video_view", { at: "manual_click" });
    } catch { /* autoplay blocked */ }
  }, []);

  const onPlay = () => { setPlaying(true); track("demo_video_view", { at: "native_play" }); };
  const onEnded = () => track("demo_video_completed");

  return (
    <section id="demo" className="max-w-7xl mx-auto px-5 sm:px-6 py-16 sm:py-24 scroll-mt-20">
      <div className="max-w-3xl">
        <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">See it in action</div>
        <h2 className="mt-3 font-heading text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight">
          One idea. Every platform.
        </h2>
        <p className="mt-4 text-ink-500 text-base sm:text-lg max-w-2xl">
          Feed AI Video Studio a topic and it hands you cinematic video for <span className="font-semibold text-ink-900">YouTube, Instagram, Reels, Facebook and LinkedIn</span> — plus a LinkedIn post, blog article and email newsletter. All from a single prompt, in your voice.
        </p>
      </div>

      <div className="mt-8 sm:mt-10 grid lg:grid-cols-5 gap-6 lg:gap-10 items-center">
        <div className="lg:col-span-3">
          <div ref={videoRef} className="relative rounded-2xl overflow-hidden border border-ink-200 shadow-2xl bg-black aspect-video" data-testid="demo-video-wrap">
            <video
              className="w-full h-full object-cover"
              src={videoSrc}
              poster={posterSrc}
              controls={playing}
              playsInline
              preload="metadata"
              onPlay={onPlay}
              onEnded={onEnded}
              data-testid="demo-video"
            />
            {!playing && (
              <button
                onClick={play}
                aria-label="Play demo"
                className="absolute inset-0 flex items-center justify-center group"
                data-testid="demo-play-btn">
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/10 to-transparent" />
                <div className="relative flex flex-col items-center gap-3">
                  <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-white/95 backdrop-blur border border-ink-200 flex items-center justify-center shadow-2xl group-hover:scale-110 transition-transform">
                    <Play className="w-7 sm:w-8 h-7 sm:h-8 text-brand-600 fill-brand-600 ml-1" />
                  </div>
                  <div className="text-white font-heading font-bold text-sm sm:text-base tracking-wide">
                    Watch the 30-second demo
                  </div>
                </div>
                <div className="absolute top-3 left-3 bg-white/90 backdrop-blur text-ink-900 text-[10px] tracking-widest uppercase font-bold px-2.5 py-1 rounded-full flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-brand-600" /> Live demo
                </div>
              </button>
            )}
          </div>
        </div>

        <div className="lg:col-span-2">
          <div className="grid grid-cols-2 lg:grid-cols-2 gap-3 sm:gap-4" data-testid="outputs-grid">
            {OUTPUTS.map((o, i) => (
              <div key={o.label} data-testid={`output-${i}`}
                className="rounded-2xl bg-white border border-ink-200 p-4 sm:p-5 hover:-translate-y-1 hover:shadow-lg transition-all">
                <div className="w-10 h-10 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center">
                  <o.icon className="w-5 h-5 text-brand-600" />
                </div>
                <div className="mt-3 font-heading font-bold text-sm sm:text-base">{o.label}</div>
                <div className="mt-1 text-[11px] sm:text-xs text-ink-500">{o.sub}</div>
              </div>
            ))}
          </div>
          <div className="mt-5 flex items-center gap-2 text-xs text-ink-500">
            <div className="h-px flex-1 bg-ink-200" />
            <span className="font-mono">from one prompt</span>
            <div className="h-px flex-1 bg-ink-200" />
          </div>
        </div>
      </div>
    </section>
  );
}
