import { useEffect, useRef, useState } from "react";
import { Sparkles, Video as VideoIcon, Linkedin, FileText, Mail, Youtube, Instagram, Facebook, Zap, Eye, Lightbulb, Target, Rocket, Film } from "lucide-react";
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
          Feed ContentOS AI a topic and it hands you cinematic video for <span className="font-semibold text-ink-900">YouTube, Instagram, Reels, Facebook and LinkedIn</span> — every format included from a single prompt.
        </p>
      </div>

      <div className="mt-8 sm:mt-10 grid lg:grid-cols-5 gap-6 lg:gap-10 items-stretch">
        {/* Storyboard preview panel */}
        <div className="lg:col-span-3">
          <div className="relative rounded-2xl overflow-hidden border border-ink-200 shadow-2xl bg-ink-900 aspect-video" data-testid="demo-storyboard">
            <div className="absolute inset-0 bg-[radial-gradient(60%_60%_at_50%_50%,rgba(79,70,229,0.35),transparent)]" />
            {/* Subtle animated grain for depth */}
            <div className="absolute inset-0 opacity-[0.15] mix-blend-overlay pointer-events-none"
                 style={{ backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><filter id='n'><feTurbulence baseFrequency='0.9' numOctaves='2'/></filter><rect width='120' height='120' filter='url(%23n)'/></svg>\")" }} />
            <div className="relative h-full grid grid-cols-3 grid-rows-2 gap-2 p-4">
              {[
                { icon: Zap,       label: "Scene 1", sub: "Hook",       grad: "from-brand-600 via-indigo-600 to-indigo-800",  delay: "0ms"   },
                { icon: Lightbulb, label: "Scene 2", sub: "Setup",      grad: "from-fuchsia-500 via-purple-600 to-brand-700", delay: "80ms"  },
                { icon: Eye,       label: "Scene 3", sub: "Insight",    grad: "from-emerald-500 via-teal-600 to-cyan-700",    delay: "160ms" },
                { icon: Target,    label: "Scene 4", sub: "Reveal",     grad: "from-amber-400 via-orange-500 to-red-600",     delay: "240ms" },
                { icon: Rocket,    label: "Scene 5", sub: "Call to action", grad: "from-rose-500 via-pink-600 to-fuchsia-700", delay: "320ms" },
                { icon: Film,      label: "Export",  sub: "16:9 + 9:16", grad: "from-ink-600 via-ink-700 to-ink-900",         delay: "400ms" },
              ].map((s) => (
                <div key={s.label}
                     className={`relative rounded-lg bg-gradient-to-br ${s.grad} p-3 flex flex-col justify-between ring-1 ring-white/15 shadow-inner overflow-hidden group animate-[fadein_600ms_ease-out_both]`}
                     style={{ animationDelay: s.delay }}>
                  {/* Shine sweep on hover */}
                  <div className="absolute -inset-x-full inset-y-0 bg-gradient-to-r from-transparent via-white/20 to-transparent group-hover:translate-x-[300%] transition-transform duration-1000" />
                  <div className="relative flex items-start justify-between">
                    <div className="w-7 h-7 rounded-md bg-white/15 backdrop-blur-sm border border-white/25 flex items-center justify-center">
                      <s.icon className="w-3.5 h-3.5 text-white" strokeWidth={2.4} />
                    </div>
                    <div className="text-[8px] uppercase tracking-widest text-white/70 font-bold flex items-center gap-0.5 bg-black/25 backdrop-blur-sm px-1.5 py-0.5 rounded-full">
                      <Sparkles className="w-2 h-2" /> Sora
                    </div>
                  </div>
                  <div className="relative">
                    <div className="text-[9px] uppercase tracking-widest text-white/60 font-bold">{s.label}</div>
                    <div className="text-sm font-heading font-black text-white leading-tight drop-shadow-md">{s.sub}</div>
                  </div>
                </div>
              ))}
            </div>
            <div className="absolute top-3 left-3 bg-white/95 backdrop-blur text-ink-900 text-[10px] tracking-widest uppercase font-bold px-2.5 py-1 rounded-full flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-brand-600" /> Sample storyboard
            </div>
            <div className="absolute top-3 right-3 bg-gradient-to-r from-purple-600 to-brand-600 text-white text-[10px] tracking-widest uppercase font-bold px-2.5 py-1 rounded-full flex items-center gap-1 shadow-lg shadow-purple-900/50">
              <Sparkles className="w-3 h-3" /> Sora 2 · Cinematic
            </div>
          </div>
          <p className="mt-3 text-xs text-ink-500 text-center">
            Every video is 5–8 approved scenes — now with optional Sora 2 cinematic animation on every scene.
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
