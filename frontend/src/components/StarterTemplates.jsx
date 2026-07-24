import { useNavigate } from "react-router-dom";
import { Sparkles, GraduationCap, Briefcase, Film, BookOpen, Quote } from "lucide-react";
import { HoverCard, HoverCardTrigger, HoverCardContent } from "@/components/ui/hover-card";

// Curated one-click starters for brand-new users who don't know what to type.
// Each card writes to the wizard draft key and navigates to /new — the wizard
// then restores the topic + style on mount (see ProjectWizard.jsx).
const DRAFT_KEY = "avs_wizard_draft_v1";

const TEMPLATES = [
  {
    id: "explain-topic",
    Icon: GraduationCap,
    tag: "Educational",
    title: "Explain a topic simply",
    example: "Explain quantum computing to a 10-year-old",
    style: "Educational",
    topic: "Explain quantum computing to a 10-year-old — use everyday analogies and end with why it matters",
    preview: [
      "Ever heard of a coin that's heads AND tails at the same time?",
      "That's the wild world of quantum computing — where tiny particles play by different rules.",
      "And it might unlock cures, cracks the internet's toughest locks, and change everything.",
    ],
  },
  {
    id: "product-explainer",
    Icon: Briefcase,
    tag: "Business",
    title: "Product explainer",
    example: "Introduce our new AI note-taking app",
    style: "Business",
    topic: "Introduce a new AI note-taking app that turns meetings into action items — hook, 3 key benefits, and a clear call-to-action",
    preview: [
      "Meetings are where great ideas go to die — because nobody remembers what was said.",
      "Meet Notely: AI that listens, summarises, and turns every call into clear action items.",
      "Try it free — the meeting you had this morning is one click away from being useful.",
    ],
  },
  {
    id: "story-hook",
    Icon: BookOpen,
    tag: "Storytelling",
    title: "Tell a story",
    example: "The rise and fall of Blockbuster",
    style: "Storytelling",
    topic: "Tell the story of the rise and fall of Blockbuster — set the scene, the pivotal mistake, and the lesson for founders today",
    preview: [
      "In 2000, Blockbuster had 9,000 stores and turned down buying Netflix for $50 million.",
      "Ten years later, Netflix was worth $13 billion — and Blockbuster was gone.",
      "The lesson? Being the biggest isn't the same as being the future.",
    ],
  },
  {
    id: "cinematic-list",
    Icon: Film,
    tag: "Cinematic",
    title: "Top 5 list",
    example: "5 places on Earth that look alien",
    style: "Cinematic",
    topic: "5 places on Earth that look alien — one scene per place with vivid, atmospheric visuals",
    preview: [
      "Some places on Earth don't feel like Earth at all.",
      "From salt flats that mirror the sky — to lakes that boil, and forests that whisper.",
      "Here are five places on our planet that will make you question where you really are.",
    ],
  },
];

export default function StarterTemplates() {
  const nav = useNavigate();

  const pick = (t) => {
    try {
      localStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({
          topic: t.topic,
          style: t.style,
          fromTemplate: true,
          templateId: t.id,
          at: Date.now(),
        })
      );
    } catch {}
    nav("/new");
  };

  return (
    <div className="mt-8" data-testid="starter-templates">
      <div className="flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-brand-600" />
        <div className="text-[11px] uppercase tracking-widest text-ink-500 font-bold">
          Not sure where to start?
        </div>
      </div>
      <h3 className="mt-1 font-heading text-xl font-bold text-ink-900">
        Try a starter template
      </h3>
      <p className="text-sm text-ink-500">
        Hover any card to preview a sample script — click to load it into the wizard.
      </p>

      <div className="mt-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {TEMPLATES.map((t) => (
          <HoverCard key={t.id} openDelay={150} closeDelay={100}>
            <HoverCardTrigger asChild>
              <button
                onClick={() => pick(t)}
                className="text-left group rounded-xl border border-ink-200 bg-white hover:border-brand-300 hover:shadow-sm transition-all p-4 focus:outline-none focus:ring-2 focus:ring-brand-300 w-full"
                data-testid={`starter-template-${t.id}`}
              >
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center group-hover:bg-brand-100 transition-colors">
                    <t.Icon className="w-4 h-4 text-brand-600" />
                  </div>
                  <span className="text-[10px] uppercase tracking-widest font-bold text-ink-400">
                    {t.tag}
                  </span>
                </div>
                <div className="mt-3 font-semibold text-ink-900 text-sm">{t.title}</div>
                <div className="mt-1 text-xs text-ink-500 leading-snug line-clamp-2">
                  &ldquo;{t.example}&rdquo;
                </div>
              </button>
            </HoverCardTrigger>
            <HoverCardContent
              side="top"
              align="start"
              className="w-80 border-brand-100 shadow-lg"
              data-testid={`starter-template-${t.id}-preview`}
            >
              <div className="flex items-center gap-2 mb-2">
                <Quote className="w-3.5 h-3.5 text-brand-500" />
                <div className="text-[10px] uppercase tracking-widest text-ink-400 font-bold">
                  Sample script
                </div>
              </div>
              <div className="space-y-2">
                {t.preview.map((line, i) => (
                  <div key={i} className="text-xs text-ink-700 leading-relaxed">
                    <span className="font-mono text-brand-400 mr-1.5">·</span>
                    {line}
                  </div>
                ))}
              </div>
              <div className="mt-3 pt-3 border-t border-ink-100 text-[11px] text-ink-500">
                Click the card to load this topic into the wizard.
              </div>
            </HoverCardContent>
          </HoverCard>
        ))}
      </div>
    </div>
  );
}
