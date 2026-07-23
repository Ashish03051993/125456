import { useEffect, useRef, useState } from "react";
import { Sparkles, Video as VideoIcon, Linkedin, FileText, Mail, Youtube, Instagram, Facebook } from "lucide-react";
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
  const sectionRef = useRef(null);
  const [viewed, setViewed] = useState(false);

  // Fire view event when the section is scrolled into view
  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting && !viewed) {
          setViewed(true);
          track("demo_section_impression");
        }
      });
    }, { threshold: 0.4 });
    io.observe(el);
    return () => io.disconnect();
  }, [viewed]);

  return (
    <section id="demo" className="max-w-7xl mx-auto px-5 sm:px-6 py-16 sm:py-24 scroll-mt-20" ref={sectionRef}>
      <div className="max-w-3xl">
        <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">See what you get</div>
        <h2 className="mt-3 font-heading text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight">
          One idea. Every platform.
        </h2>
        <p className="mt-4 text-ink-500 text-base sm:text-lg max-w-2xl">
          Feed AI Video Studio a topic and it hands you cinematic video for <span className="font-semibold text-ink-900">YouTube, Instagram, Reels, Facebook and LinkedIn</span> — every format included from a single prompt.
        </p>
      </div>

      <div className="mt-8 sm:mt-10 grid lg:grid-cols-5 gap-6 lg:gap-10 items-stretch">
        {/* Storyboard preview panel */}
        <div className="lg:col-span-3">
          <div className="relative rounded-2xl overflow-hidden border border-ink-200 shadow-2xl bg-ink-900 aspect-video" data-testid="demo-storyboard">
            <div className="absolute inset-0 bg-[radial-gradient(60%_60%_at_50%_50%,rgba(79,70,229,0.35),transparent)]" />
            <div className="relative h-full grid grid-cols-3 grid-rows-2 gap-2 p-4">
              {[
                { label: "Scene 1", sub: "Hook",      grad: "from-brand-600 to-indigo-700" },
                { label: "Scene 2", sub: "Setup",     grad: "from-fuchsia-600 to-brand-700" },
                { label: "Scene 3", sub: "Insight",   grad: "from-emerald-600 to-teal-700" },
                { label: "Scene 4", sub: "Reveal",    grad: "from-amber-500 to-orange-700" },
                { label: "Scene 5", sub: "Call to action", grad: "from-rose-500 to-pink-700" },
                { label: "Export",  sub: "16:9 + 9:16", grad: "from-ink-500 to-ink-700" },
              ].map((s) => (
                <div key={s.label} className={`rounded-lg bg-gradient-to-br ${s.grad} p-3 flex flex-col justify-end ring-1 ring-white/10 overflow-hidden`}>
                  <div className="text-[9px] uppercase tracking-widest text-white/70 font-bold">{s.label}</div>
                  <div className="text-sm font-heading font-black text-white leading-tight">{s.sub}</div>
                </div>
              ))}
            </div>
            <div className="absolute top-3 left-3 bg-white/95 backdrop-blur text-ink-900 text-[10px] tracking-widest uppercase font-bold px-2.5 py-1 rounded-full flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-brand-600" /> Sample storyboard
            </div>
          </div>
          <p className="mt-3 text-xs text-ink-500 text-center">
            Every video is 5–8 approved scenes stitched into a polished MP4.
          </p>
        </div>

        {/* Outputs grid */}
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
