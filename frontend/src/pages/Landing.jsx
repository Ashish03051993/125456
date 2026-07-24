import { useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import usePageTitle from "@/lib/usePageTitle";
import { Sparkles, Palette, CheckCircle2, ArrowRight, Wand2, Image as ImageIcon, Mic, Film, HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TopBar } from "@/components/Layout";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { track, captureAttribution } from "@/lib/analytics";
import DemoVideoSection from "@/components/DemoVideoSection";

// Landing page FAQ — pre-signup objections handled in one place.
// Every answer is factual against the current build; keep this list honest.
const FAQ_ITEMS = [
  {
    q: "How much does one video actually cost me?",
    a: "Every plan is credit-based. Slideshow video costs about 100 credits per minute, so a 30-second video is 50 credits and a 5-minute video is 500 credits. The Creator plan (₹1,999/mo) includes 500 credits and Business (₹6,999/mo) includes 2,000 credits with premium AI video unlocked. Credits never expire.",
  },
  {
    q: "Do I need to record my own voice or upload footage?",
    a: "No — you just type a topic. Our pipeline writes the script, generates the visuals, picks a voice, and stitches the final video. You approve each step before it moves to the next, so you're always in control.",
  },
  {
    q: "What formats do I get?",
    a: "Every video is exported in 16:9 (YouTube), 9:16 (Reels, TikTok, Shorts), and 1:1 (Instagram feed). One prompt, three ready-to-post files — plus a downloadable thumbnail image for your post banner.",
  },
  {
    q: "Can I edit the script or images before rendering?",
    a: "Yes. The wizard pauses at three approval gates — Script, Images, Voice — so you can tweak wording, swap a scene image, or pick a different narrator before we render the final MP4. Regenerations don't cost extra credits.",
  },
  {
    q: "Who owns the videos I create?",
    a: "You do. Everything you generate is yours to post commercially, on any platform. We only display your work if you flip on a public share link (and you can revoke it any time from the project page).",
  },
  {
    q: "How long does one video take?",
    a: "A 30-second video typically completes in about 2–3 minutes end-to-end. Longer videos scale roughly linearly. We ping you on the dashboard the moment a render is ready.",
  },
  {
    q: "Do you have an API or team plan?",
    a: "Team workspaces, brand kits and API access are on the roadmap. Drop into the waitlist at the top and we'll email you the moment they're live.",
  },
];

const DURATION_CHIPS = [
  { label: "30s",  credits: 3,  hint: "Reels · Shorts" },
  { label: "45s",  credits: 4,  hint: "LinkedIn" },
  { label: "60s",  credits: 5,  hint: "Instagram" },
  { label: "90s",  credits: 7,  hint: "X / Twitter" },
  { label: "2 min", credits: 10, hint: "Demos" },
  { label: "3 min", credits: 15, hint: "Explainers" },
  { label: "5 min", credits: 25, hint: "Tutorials" },
  { label: "10 min",credits: 50, hint: "Long-form" },
];

const STEPS = [
  { icon: Wand2,     title: "1. Share your idea",   body: "Type a topic. Pick a duration between 30 seconds and 10 minutes." },
  { icon: Sparkles,  title: "2. Approve the script", body: "Our AI writes the story. You edit or approve — nothing moves until you say yes." },
  { icon: ImageIcon, title: "3. Approve the visuals",body: "Every scene rendered as an image. Regenerate any frame you don't love." },
  { icon: Mic,       title: "4. Approve the voice",  body: "Pick a voice, listen, refine. You&apos;re always in the driver&apos;s seat." },
  { icon: Film,      title: "5. Video ready",        body: "16:9 for YouTube. 9:16 for LinkedIn & Reels. Download in minutes." },
];

const FEATURES = [
  { icon: Sparkles,  title: "Guided step-by-step",   body: "Approve script, visuals and voice before your video is rendered — never a surprise output.", span: "md:col-span-2" },
  { icon: Palette,   title: "5 cinematic styles",    body: "Business, Documentary, Educational, Cinematic, Storytelling.", span: "md:col-span-1" },
  { icon: Film,      title: "Every platform, one render", body: "16:9 for YouTube. 9:16 for Instagram Reels, LinkedIn, TikTok, Facebook & Shorts. Every output included, no extra credits.", span: "md:col-span-1" },
  { icon: CheckCircle2, title: "One free 30-sec video every month", body: "New users get 50 credits every month, forever. No credit card needed to start.", span: "md:col-span-2" },
];

export default function Landing() {
  usePageTitle(null); // Landing keeps the default full title
  const fired = useRef(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (fired.current) return;
    fired.current = true;
    captureAttribution();
    track("page_view", { page: "landing" });
  }, []);

  const startFree = (surface) => {
    track("signup_click", { source: surface });
    navigate("/signup");
  };

  const scrollToDemo = () => {
    track("cta_click", { target: "demo_section" });
    document.getElementById("demo")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="min-h-screen bg-white text-ink-900 selection:bg-brand-600 selection:text-white">
      <TopBar />

      {/* HERO */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(60%_50%_at_50%_0%,rgba(79,70,229,0.10),transparent)]" />
        <div className="max-w-6xl mx-auto px-4 sm:px-6 pt-14 sm:pt-24 pb-12 sm:pb-20">
          <div className="inline-flex items-center gap-2 rounded-full border border-brand-100 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700" data-testid="hero-eyebrow">
            <Sparkles className="w-3.5 h-3.5" /> Your first 30-second video is on us — every month
          </div>
          <h1 className="mt-5 font-heading font-black tracking-tighter text-4xl sm:text-6xl lg:text-7xl max-w-4xl" data-testid="hero-headline">
            Turn any idea into a video — <span className="text-brand-600">from 30 seconds to 10 minutes.</span>
          </h1>
          <p className="mt-5 text-ink-500 text-base sm:text-lg max-w-2xl" data-testid="hero-subtitle">
            Type your idea. Approve the script. Approve the visuals. Approve the voice. Get a polished video in minutes — with you in control at every step.
          </p>

          {/* Duration chips — click to sign up */}
          <div className="mt-7 flex flex-wrap gap-2" data-testid="hero-duration-chips">
            {DURATION_CHIPS.map((d) => (
              <button key={d.label}
                type="button"
                onClick={() => { track("hero_chip_click", { duration: d.label }); startFree(`hero_chip_${d.label}`); }}
                className="group rounded-xl border border-ink-200 bg-white pl-3 pr-3 py-2 flex items-center gap-3 hover:border-brand-600 hover:shadow-sm transition-all cursor-pointer text-left"
                data-testid={`duration-chip-${d.label.replace(/\s|min/gi, "").replace("s","sec")}`}>
                <div className="flex flex-col leading-tight">
                  <span className="font-heading font-bold text-sm text-ink-900">{d.label}</span>
                  <span className="text-[10px] text-ink-400 uppercase tracking-wider font-semibold">{d.hint}</span>
                </div>
                <div className="pl-3 border-l border-ink-100 flex flex-col items-end leading-tight">
                  <span className="text-[10px] text-ink-400 uppercase tracking-widest font-semibold">Credits</span>
                  <span className="font-heading font-black text-brand-600 text-base">{d.credits}</span>
                </div>
              </button>
            ))}
          </div>

          {/* CTAs */}
          <div className="mt-8 flex flex-wrap gap-3">
            <Button onClick={() => startFree("hero_primary")} className="rounded-full bg-brand-600 hover:bg-brand-700 text-white h-12 px-6 text-base font-semibold" data-testid="hero-signup-btn">
              <Sparkles className="w-4 h-4 mr-2" /> Start free — 1 video / month
            </Button>
            <Button variant="outline" onClick={scrollToDemo} className="rounded-full h-12 px-6 text-base font-semibold border-ink-200 text-ink-900" data-testid="hero-demo-btn">
              See what you get
            </Button>
          </div>
          <div className="mt-3 text-xs text-ink-500 flex flex-wrap items-center gap-x-4 gap-y-1">
            <span className="flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> No credit card</span>
            <span className="flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Sign up with Google</span>
            <span className="flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Free credits auto-refill</span>
          </div>
        </div>
      </section>

      {/* Demo section — no props needed, storyboard is self-contained */}
      <DemoVideoSection />

      {/* HOW IT WORKS */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-24" data-testid="how-it-works">
        <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">How it works</div>
        <h2 className="mt-2 font-heading font-extrabold text-3xl sm:text-5xl tracking-tighter max-w-3xl">
          Five steps. You approve every one.
        </h2>
        <div className="mt-10 grid md:grid-cols-2 lg:grid-cols-5 gap-4">
          {STEPS.map((s, i) => (
            <div key={s.title} className="rounded-2xl border border-ink-200 bg-white p-5" data-testid={`step-${i+1}`}>
              <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-700 flex items-center justify-center">
                <s.icon className="w-5 h-5" />
              </div>
              <div className="mt-4 font-heading font-bold text-base">{s.title}</div>
              <div className="mt-1 text-sm text-ink-500" dangerouslySetInnerHTML={{ __html: s.body }} />
            </div>
          ))}
        </div>
      </section>

      {/* FEATURES */}
      <section className="bg-ink-50 border-y border-ink-100">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-24">
          <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">What&apos;s inside</div>
          <h2 className="mt-2 font-heading font-extrabold text-3xl sm:text-5xl tracking-tighter max-w-3xl">
            Everything you need to ship a video. Nothing you don&apos;t.
          </h2>
          <div className="mt-10 grid md:grid-cols-3 gap-4">
            {FEATURES.map((f) => (
              <div key={f.title} className={`rounded-2xl border border-ink-200 bg-white p-6 ${f.span}`} data-testid={`feature-${f.title.toLowerCase().split(" ")[0]}`}>
                <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-700 flex items-center justify-center">
                  <f.icon className="w-5 h-5" />
                </div>
                <div className="mt-4 font-heading font-bold text-lg">{f.title}</div>
                <div className="mt-1 text-sm text-ink-500">{f.body}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 py-16 sm:py-24" id="faq" data-testid="landing-faq">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-8">
          <div>
            <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold flex items-center gap-1.5">
              <HelpCircle className="w-3.5 h-3.5" /> Questions creators actually ask
            </div>
            <h2 className="mt-2 font-heading font-black text-3xl sm:text-5xl tracking-tighter text-ink-900">
              You&apos;re curious. That&apos;s fair.
            </h2>
          </div>
        </div>
        <Accordion type="single" collapsible className="rounded-2xl border border-ink-200 bg-white divide-y divide-ink-100 overflow-hidden">
          {FAQ_ITEMS.map((item, i) => (
            <AccordionItem key={i} value={`faq-${i}`} className="px-5 border-0" data-testid={`faq-item-${i}`}>
              <AccordionTrigger className="text-left font-semibold text-ink-900 hover:no-underline py-5">
                {item.q}
              </AccordionTrigger>
              <AccordionContent className="text-ink-600 pb-5 pr-6 leading-relaxed">
                {item.a}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
        <p className="mt-6 text-center text-sm text-ink-500">
          Still on the fence? <Link to="/signup" className="text-brand-600 font-semibold hover:underline" data-testid="faq-signup-link">Grab your free credits</Link> and see what shows up.
        </p>
      </section>

      {/* FINAL CTA */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-24">
        <div className="rounded-3xl bg-gradient-to-br from-ink-900 via-brand-700 to-violet-600 text-white p-8 sm:p-12 relative overflow-hidden" data-testid="final-cta">
          <div className="absolute -right-24 -top-24 w-80 h-80 rounded-full bg-white/10 blur-3xl" />
          <div className="relative">
            <h2 className="font-heading font-black text-3xl sm:text-5xl tracking-tighter max-w-3xl">
              Your first video is on us. Every single month.
            </h2>
            <p className="mt-3 text-white/80 max-w-2xl">
              Free plan gives you 50 credits every month — enough for one polished 30-second video. Need more? Top up any time, credits never expire.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button onClick={() => startFree("final_cta")} className="rounded-full bg-white text-ink-900 hover:bg-white/90 h-12 px-6 font-semibold" data-testid="final-signup-btn">
                <Sparkles className="w-4 h-4 mr-2" /> Get started free
              </Button>
              <Link to="/pricing" data-testid="final-pricing-link">
                <Button variant="outline" className="rounded-full h-12 px-6 font-semibold border-white/40 bg-transparent text-white hover:bg-white/10">
                  See pricing <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-ink-100 py-8">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-wrap items-center justify-between gap-3 text-sm text-ink-500">
          <div>© {new Date().getFullYear()} AI Video Studio</div>
          <div className="flex items-center gap-x-5 gap-y-2 flex-wrap justify-end">
            <a href="#faq" className="hover:text-brand-600" data-testid="footer-faq">FAQ</a>
            <Link to="/pricing" className="hover:text-brand-600" data-testid="footer-pricing">Pricing</Link>
            <Link to="/login" className="hover:text-brand-600" data-testid="footer-login">Log in</Link>
            <Link to="/signup" className="hover:text-brand-600" data-testid="footer-signup">Sign up</Link>
            <Link to="/terms" className="hover:text-brand-600" data-testid="footer-terms">Terms</Link>
            <Link to="/privacy" className="hover:text-brand-600" data-testid="footer-privacy">Privacy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
