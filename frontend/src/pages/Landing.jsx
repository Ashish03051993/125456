import { Link } from "react-router-dom";
import { Sparkles, Zap, MousePointerClick, Palette, Layers, Video, ArrowRight, Check, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TopBar } from "@/components/Layout";
import { useAuth } from "@/lib/auth";
import { login } from "@/pages/AuthCallback";

const FEATURES = [
  { icon: Sparkles, title: "Prompt to Video", body: "Type a topic. We write the script, storyboard, and generate every scene." , span: "md:col-span-2" },
  { icon: Palette,  title: "5 Cinematic Styles", body: "Business, Documentary, Educational, Cinematic, Storytelling.", span: "md:col-span-1" },
  { icon: Zap,      title: "60 sec generation", body: "Parallel image + voice + compose. First cut in under a minute.", span: "md:col-span-1" },
  { icon: Layers,   title: "Scene-by-Scene Control", body: "Every scene: image prompt, video prompt, subtitle, narration.", span: "md:col-span-2" },
];

export default function Landing() {
  const { user } = useAuth();
  return (
    <div className="min-h-screen bg-ink-50 text-ink-900">
      <TopBar />

      {/* HERO */}
      <section className="relative overflow-hidden">
        <div className="blue-orb bg-brand-500" style={{ width: 480, height: 480, top: -160, right: -120 }} />
        <div className="blue-orb bg-cyan-400" style={{ width: 380, height: 380, bottom: -140, left: -100 }} />
        <div className="dot-grid absolute inset-0 opacity-40" />
        <div className="relative max-w-7xl mx-auto px-6 pt-24 pb-32 grid md:grid-cols-12 gap-12 items-center">
          <div className="md:col-span-7 stagger">
            <div className="inline-flex items-center gap-2 bg-white border border-ink-200 rounded-full px-3 py-1 text-xs font-semibold text-brand-700 shadow-sm">
              <Sparkles className="w-3.5 h-3.5" /> Powered by GPT-5.4 · Nano Banana · OpenAI TTS
            </div>
            <h1 className="mt-6 font-heading font-extrabold text-5xl sm:text-6xl lg:text-7xl tracking-tighter leading-[0.95]">
              Turn a <span className="text-brand-600">topic</span> into a<br />
              cinematic video<span className="text-brand-600">.</span>
            </h1>
            <p className="mt-6 text-lg text-ink-500 max-w-xl">
              AI Video Studio writes the script, storyboards every scene, generates the imagery,
              records the voiceover and renders a finished MP4 — automatically.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              {user ? (
                <Link to="/new"><Button className="rounded-full h-12 px-7 bg-brand-600 hover:bg-brand-700 text-white text-base" data-testid="hero-cta-new">
                  Create your first video <ArrowRight className="w-4 h-4 ml-2" />
                </Button></Link>
              ) : (
                <Button onClick={login} className="rounded-full h-12 px-7 bg-brand-600 hover:bg-brand-700 text-white text-base" data-testid="hero-cta-signin">
                  Get started free <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              )}
              <Link to="/pricing"><Button variant="outline" className="rounded-full h-12 px-7 border-ink-300 text-base" data-testid="hero-cta-pricing">See pricing</Button></Link>
            </div>
            <div className="mt-8 flex items-center gap-6 text-sm text-ink-500">
              <div className="flex items-center gap-2"><Check className="w-4 h-4 text-brand-600" /> 5 free credits on signup</div>
              <div className="flex items-center gap-2"><Check className="w-4 h-4 text-brand-600" /> Download MP4</div>
            </div>
          </div>
          <div className="md:col-span-5 relative animate-fade-up">
            <div className="relative rounded-2xl overflow-hidden shadow-2xl border border-ink-200 bg-white animate-float-slow">
              <img alt="Editor preview" src="https://images.unsplash.com/photo-1574717024653-61fd2cf4d44d?crop=entropy&cs=srgb&fm=jpg&w=940&q=85" className="w-full h-auto" />
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-16 h-16 rounded-full bg-white/90 backdrop-blur border border-ink-200 flex items-center justify-center shadow-lg">
                  <Play className="w-6 h-6 text-brand-600 fill-brand-600 ml-1" />
                </div>
              </div>
            </div>
            <div className="absolute -bottom-6 -left-6 rounded-xl bg-white border border-ink-200 shadow-lg p-4 w-56">
              <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Scene 3 / 12</div>
              <div className="mt-1 font-heading font-bold text-ink-900">Rainforest at dawn</div>
              <div className="mt-2 h-1.5 bg-ink-100 rounded-full overflow-hidden">
                <div className="h-full w-2/3 bg-brand-600" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="max-w-7xl mx-auto px-6 py-24">
        <div className="max-w-2xl">
          <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">How it works</div>
          <h2 className="mt-3 font-heading text-4xl sm:text-5xl font-bold tracking-tight">From idea to MP4 in one flow.</h2>
        </div>
        <div className="mt-14 grid md:grid-cols-3 gap-6">
          {[
            { n: "01", title: "Describe the video", body: "Topic, duration, language, style, voice — that's it." },
            { n: "02", title: "AI builds the story", body: "Title, hook, full script, and a scene-by-scene storyboard." },
            { n: "03", title: "Render & download", body: "Images, voiceover and subtitles composed into a shareable MP4." },
          ].map((s) => (
            <div key={s.n} className="rounded-2xl bg-white border border-ink-200 p-8 hover:-translate-y-1 hover:shadow-lg transition-all">
              <div className="text-6xl font-heading font-extrabold text-brand-100">{s.n}</div>
              <div className="mt-4 font-heading font-bold text-2xl">{s.title}</div>
              <p className="mt-2 text-ink-500">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* BENTO FEATURES */}
      <section className="max-w-7xl mx-auto px-6 pb-24">
        <div className="grid md:grid-cols-3 gap-4 auto-rows-[220px]">
          {FEATURES.map((f) => (
            <div key={f.title} className={`${f.span} rounded-2xl bg-white border border-ink-200 p-8 hover:-translate-y-1 hover:shadow-lg transition-all relative overflow-hidden`}>
              <f.icon className="w-8 h-8 text-brand-600" />
              <div className="mt-4 font-heading font-bold text-xl">{f.title}</div>
              <p className="mt-2 text-ink-500 text-sm max-w-md">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-6xl mx-auto px-6 pb-24">
        <div className="rounded-3xl bg-ink-900 text-white p-14 relative overflow-hidden">
          <div className="blue-orb bg-brand-500" style={{ width: 340, height: 340, top: -80, right: -40, opacity: 0.4 }} />
          <div className="relative">
            <h3 className="font-heading text-4xl sm:text-5xl font-extrabold tracking-tighter max-w-2xl">
              Make your first video in the next 5 minutes.
            </h3>
            <p className="mt-4 text-ink-400 max-w-xl">No credit card. Five credits on the house. Ship your first cut before lunch.</p>
            <div className="mt-8">
              {user ? (
                <Link to="/new"><Button className="rounded-full h-12 px-7 bg-white text-ink-900 hover:bg-ink-100 text-base" data-testid="cta-final-new">
                  Open the studio <ArrowRight className="w-4 h-4 ml-2" />
                </Button></Link>
              ) : (
                <Button onClick={login} className="rounded-full h-12 px-7 bg-white text-ink-900 hover:bg-ink-100 text-base" data-testid="cta-final-signin">
                  Sign in with Google <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              )}
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-ink-200 py-8">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between text-sm text-ink-500">
          <div className="flex items-center gap-2"><Video className="w-4 h-4 text-brand-600" /> AI Video Studio</div>
          <div>© 2026</div>
        </div>
      </footer>
    </div>
  );
}
