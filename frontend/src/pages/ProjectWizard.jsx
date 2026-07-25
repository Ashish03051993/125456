import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { TopBar, Sidebar } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sparkles, Loader2, Briefcase, Film, GraduationCap, Camera, BookOpen, Upload, Wand2, User, X, Lock } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";

const STYLES = [
  { id: "Business", icon: Briefcase, desc: "Corporate, polished, confident" },
  { id: "Documentary", icon: Film, desc: "Neutral, informative, factual" },
  { id: "Educational", icon: GraduationCap, desc: "Clear, friendly, structured" },
  { id: "Cinematic", icon: Camera, desc: "Dramatic, evocative, slow" },
  { id: "Storytelling", icon: BookOpen, desc: "Warm, character-driven" },
];
const LANGS = ["English", "Hindi", "Spanish", "French", "German", "Portuguese", "Japanese"];

// Fallback used if /api/durations is momentarily unreachable
const FALLBACK_DURATIONS = [
  { sec: 30,  credits: 5,   label: "30 sec" },
  { sec: 45,  credits: 8,   label: "45 sec" },
  { sec: 60,  credits: 10,  label: "60 sec" },
  { sec: 90,  credits: 15,  label: "90 sec" },
  { sec: 120, credits: 20,  label: "2 min" },
  { sec: 180, credits: 30,  label: "3 min" },
  { sec: 300, credits: 50,  label: "5 min" },
  { sec: 600, credits: 100, label: "10 min" },
];

// Local draft-save so users don't lose their in-progress wizard state on reload / accidental nav
const DRAFT_KEY = "avs_wizard_draft_v1";
const loadDraft = () => {
  try { return JSON.parse(localStorage.getItem(DRAFT_KEY) || "null"); } catch { return null; }
};
const saveDraft = (d) => {
  try { localStorage.setItem(DRAFT_KEY, JSON.stringify({ ...d, at: Date.now() })); } catch {}
};
const clearDraft = () => { try { localStorage.removeItem(DRAFT_KEY); } catch {} };

export default function ProjectWizard() {
  const nav = useNavigate();
  const { refresh, user } = useAuth();
  const [topic, setTopic] = useState("");
  const [durations, setDurations] = useState(FALLBACK_DURATIONS);
  const [durationSec, setDurationSec] = useState(30);
  const [style, setStyle] = useState("Educational");
  const [language, setLanguage] = useState("English");
  const [voice, setVoice] = useState("female");
  const [dialogueMode, setDialogueMode] = useState(false);
  const [autoAnimate, setAutoAnimate] = useState(false);
  const [talkingHead, setTalkingHead] = useState(false);
  const [charSource, setCharSource] = useState(null);         // "upload" | "ai_generated"
  const [charImageUrl, setCharImageUrl] = useState(null);
  const [charBusy, setCharBusy] = useState(false);
  const [charDesc, setCharDesc] = useState("");
  const [showUpsell, setShowUpsell] = useState(false);
  const [feature, setFeature] = useState({ enabled: true, live_render: false, paid_plans: ["pro", "business", "enterprise"] });
  const fileInputRef = useRef(null);
  const draftIdRef = useRef(null);                           // holds a placeholder project id for pre-create character uploads
  const [busy, setBusy] = useState(false);
  const [enhanceBusy, setEnhanceBusy] = useState(false);
  const [suggestions, setSuggestions] = useState([]); // alt rewrites shown as chips

  const isPaidUser = user && feature.paid_plans.includes(user.plan);

  // Rewrite the raw topic into a richer prompt via GPT. Free of credits.
  // Keeps a snapshot so we can offer "undo" via a toast action.
  const enhanceTopic = async () => {
    const original = topic.trim();
    if (original.length < 3) return;
    setEnhanceBusy(true);
    try {
      const { data } = await api.post("/wizard/enhance-topic", {
        topic: original, style, language,
      });
      if (data?.enhanced && data.enhanced !== original) {
        setTopic(data.enhanced);
        setSuggestions(Array.isArray(data.alternatives) ? data.alternatives : []);
        toast.success("Topic enhanced", {
          description: "Tweak anything — or undo to restore your original.",
          action: { label: "Undo", onClick: () => { setTopic(original); setSuggestions([]); } },
        });
      } else {
        toast.info("Your topic already looks great.");
      }
    } catch (e) {
      const msg = e?.response?.data?.detail || "Couldn't enhance right now — try again in a moment.";
      toast.error(msg);
    } finally {
      setEnhanceBusy(false);
    }
  };

  const applySuggestion = (text) => {
    setTopic(text);
    setSuggestions((prev) => prev.filter((s) => s !== text));
    toast.success("Topic swapped");
  };

  // Open the global upgrade modal (same one the axios 402 interceptor uses)
  const openPaywall = () => {
    window.dispatchEvent(new CustomEvent("paywall:open", {
      detail: { code: "paid_feature_required", feature: "talking_head",
                message: "Talking-head is available on Pro plan and above.",
                upgrade_url: "/pricing" },
    }));
  };

  useEffect(() => {
    api.get("/durations").then(({ data }) => { if (Array.isArray(data) && data.length) setDurations(data); }).catch(() => {});
    api.get("/features/talking_head").then(({ data }) => setFeature(data)).catch(() => {});
    // Restore any saved wizard draft from a previous session
    const d = loadDraft();
    if (d && (d.topic || d.dialogueMode)) {
      if (d.topic) setTopic(d.topic);
      if (typeof d.durationSec === "number") setDurationSec(d.durationSec);
      if (d.style) setStyle(d.style);
      if (d.language) setLanguage(d.language);
      if (d.voice) setVoice(d.voice);
      if (typeof d.dialogueMode === "boolean") setDialogueMode(d.dialogueMode);
      if (d.topic?.trim()) {
        if (d.fromTemplate) {
          toast.success("Template loaded", { description: "Tweak the topic or style, then generate." });
        } else {
          toast.info("Draft restored", { description: "Picked up where you left off — clear the topic to start fresh." });
        }
      }
    }
  }, []);

  // Persist wizard state whenever the user tweaks anything (debounced via effect batching)
  useEffect(() => {
    // Only save if the user actually put a topic in — avoids resurrecting a blank wizard
    if (!topic.trim()) { clearDraft(); return; }
    saveDraft({ topic, durationSec, style, language, voice, dialogueMode });
  }, [topic, durationSec, style, language, voice, dialogueMode]);

  const activeCredits = durations.find((d) => d.sec === durationSec)?.credits ?? 3;
  const currentCredits = user?.credits ?? 0;
  const canAfford = currentCredits >= activeCredits;

  // --- Character (talking-head) handlers ---
  // Strategy: create the project first (topic required anyway), then upload/generate the character
  // against that project id, THEN kick off /generate. This avoids a temp-draft table.
  const ensureDraftProject = async () => {
    if (draftIdRef.current) return draftIdRef.current;
    if (!topic.trim()) { toast.error("Please enter a topic first — we'll attach the character to this project."); return null; }
    if (!isPaidUser) { openPaywall(); return null; }
    try {
      const { data } = await api.post("/projects", {
        topic, duration_sec: durationSec, style, language, voice,
        dialogue_mode: dialogueMode, talking_head: false,   // set to true only at final submit
      });
      draftIdRef.current = data.id;
      return data.id;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Couldn't prepare project");
      return null;
    }
  };

  const onUploadCharacter = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!isPaidUser) { openPaywall(); e.target.value = ""; return; }
    const pid = await ensureDraftProject();
    if (!pid) { e.target.value = ""; return; }
    setCharBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const { data } = await api.post(`/projects/${pid}/character/upload`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setCharImageUrl(data.character_image_url);
      setCharSource("upload");
      toast.success("Photo uploaded");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Upload failed");
    } finally { setCharBusy(false); e.target.value = ""; }
  };

  const onGenerateCharacter = async () => {
    if (!isPaidUser) { openPaywall(); return; }
    if (charDesc.trim().length < 8) { toast.error("Describe the character in a few words (e.g. 'confident Indian entrepreneur, 30s')."); return; }
    const pid = await ensureDraftProject();
    if (!pid) return;
    setCharBusy(true);
    try {
      const { data } = await api.post(`/projects/${pid}/character/generate`, { description: charDesc });
      setCharImageUrl(data.character_image_url);
      setCharSource("ai_generated");
      toast.success("Portrait generated");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Generation failed");
    } finally { setCharBusy(false); }
  };

  const onClearCharacter = async () => {
    if (draftIdRef.current) {
      try { await api.delete(`/projects/${draftIdRef.current}/character`); } catch { /* ignore */ }
    }
    setCharImageUrl(null); setCharSource(null); setCharDesc("");
  };

  const create = async () => {
    if (!topic.trim()) return toast.error("Please enter a topic.");
    if (!canAfford) return toast.error(`Need ${activeCredits} credits, you have ${currentCredits}. Top up to continue.`);
    if (talkingHead && !isPaidUser) { setShowUpsell(true); return; }
    if (talkingHead && !charImageUrl) return toast.error("Please add a character photo or generate one before enabling Talking Head.");
    setBusy(true);
    try {
      let pid = draftIdRef.current;
      if (pid) {
        // Update the draft with final settings (topic/duration/etc may have changed after draft creation)
        await api.patch(`/projects/${pid}`, {
          topic, duration_sec: durationSec, style, language, voice,
          dialogue_mode: dialogueMode, talking_head: talkingHead,
          auto_animate: autoAnimate,
        }).catch(() => {}); // PATCH may not exist yet — soft-fail so we still generate
      } else {
        const { data } = await api.post("/projects", {
          topic, duration_sec: durationSec, style, language, voice,
          dialogue_mode: dialogueMode, talking_head: talkingHead,
          auto_animate: autoAnimate,
          character_image_url: charImageUrl || undefined,
        });
        pid = data.id;
      }
      await api.post(`/projects/${pid}/generate`);
      await refresh();
      clearDraft(); // draft is now a real project — no need to keep the local copy
      toast.success("Generation started");
      nav(`/project/${pid}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to start");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-ink-50">
      <TopBar />
      <div className="max-w-7xl mx-auto flex">
        <Sidebar />
        <main className="flex-1 p-8">
          <div className="max-w-3xl">
            <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">New video</div>
            <h1 className="mt-1 font-heading text-4xl font-extrabold tracking-tighter">Describe your video.</h1>
            <p className="mt-2 text-ink-500">We&apos;ll draft the script, then walk you through visuals and voice — you approve every step before the video is rendered.</p>

            <div className="mt-8 bg-white border border-ink-200 rounded-2xl p-6 space-y-6">
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <Label className="text-sm font-semibold" htmlFor="topic">Topic or prompt</Label>
                  <button
                    type="button"
                    onClick={enhanceTopic}
                    disabled={enhanceBusy || topic.trim().length < 3}
                    className="inline-flex items-center gap-1.5 rounded-full border border-brand-200 bg-brand-50 hover:bg-brand-100 disabled:opacity-50 disabled:cursor-not-allowed text-brand-700 text-xs font-semibold px-3 py-1 transition-colors"
                    data-testid="enhance-topic-btn"
                  >
                    {enhanceBusy ? (
                      <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Enhancing…</>
                    ) : (
                      <><Wand2 className="w-3.5 h-3.5" /> Enhance with AI</>
                    )}
                  </button>
                </div>
                <Textarea id="topic" data-testid="topic-input" rows={3} value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g. How coffee is grown in Ethiopia — for high school students"
                  className="" />
                <div className="mt-1 text-[11px] text-ink-400">
                  Tip: 15+ words gives the AI enough context to write a rich script.
                </div>
                {suggestions.length > 0 && (
                  <div className="mt-3 rounded-xl border border-brand-100 bg-brand-50/40 p-3" data-testid="topic-suggestions">
                    <div className="text-[10px] uppercase tracking-widest text-brand-600 font-bold mb-2">
                      Or try another angle
                    </div>
                    <div className="space-y-2">
                      {suggestions.map((s, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => applySuggestion(s)}
                          className="w-full text-left rounded-lg border border-ink-200 bg-white hover:border-brand-300 hover:shadow-sm transition-all p-2.5 text-xs text-ink-700 line-clamp-3"
                          data-testid={`topic-suggestion-${i}`}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div>
                <Label className="text-sm font-semibold">Duration</Label>
                <div className="mt-3 grid grid-cols-4 sm:grid-cols-4 gap-2.5" data-testid="duration-grid">
                  {durations.map((d) => {
                    const active = durationSec === d.sec;
                    const affordable = currentCredits >= d.credits;
                    return (
                      <button key={d.sec} data-testid={`duration-${d.sec}`}
                        type="button"
                        onClick={() => setDurationSec(d.sec)}
                        className={[
                          "relative rounded-xl border p-3 text-left transition-all",
                          active
                            ? "bg-brand-600 border-brand-600 text-white shadow-lg shadow-brand-600/20"
                            : affordable
                              ? "bg-white border-ink-200 hover:border-brand-600 hover:shadow-sm text-ink-900"
                              : "bg-ink-50 border-ink-200 text-ink-400 opacity-70 cursor-not-allowed",
                        ].join(" ")}
                        disabled={!affordable}>
                        <div className={`font-heading font-bold text-base leading-none ${active ? "text-white" : "text-ink-900"}`}>{d.label}</div>
                        <div className="mt-2 flex items-baseline justify-between">
                          <span className={`text-[10px] uppercase tracking-widest font-semibold ${active ? "text-white/70" : "text-ink-400"}`}>Credits</span>
                          <span className={`font-heading font-black text-lg leading-none ${active ? "text-white" : affordable ? "text-brand-600" : "text-ink-400"}`}>
                            {d.credits}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <Label className="text-sm font-semibold">Style</Label>
                <div className="mt-2 grid md:grid-cols-5 grid-cols-2 gap-2">
                  {STYLES.map((s) => (
                    <button key={s.id} data-testid={`style-${s.id}`}
                      onClick={() => setStyle(s.id)}
                      className={`p-3 rounded-lg border text-left transition-colors ${
                        style === s.id ? "border-brand-600 bg-brand-50" : "border-ink-200 hover:border-brand-600 bg-white"
                      }`}>
                      <s.icon className={`w-5 h-5 ${style === s.id ? "text-brand-600" : "text-ink-500"}`} />
                      <div className="mt-2 font-semibold text-sm">{s.id}</div>
                      <div className="text-[11px] text-ink-500 leading-tight mt-0.5">{s.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label className="text-sm font-semibold">Language</Label>
                  <Select value={language} onValueChange={setLanguage}>
                    <SelectTrigger className="mt-2" data-testid="language-select"><SelectValue /></SelectTrigger>
                    <SelectContent>{LANGS.map(l => <SelectItem key={l} value={l}>{l}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-sm font-semibold">Voice</Label>
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    {[{id:"female", label:"Female (Nova)"},{id:"male", label:"Male (Onyx)"}].map(v => (
                      <button key={v.id} data-testid={`voice-${v.id}`} onClick={() => setVoice(v.id)}
                        className={`h-11 rounded-lg border font-medium text-sm transition-colors ${
                          voice === v.id ? "bg-brand-600 text-white border-brand-600" : "bg-white border-ink-200 hover:border-brand-600"
                        }`}>{v.label}</button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Character Dialogue toggle */}
              <div className="rounded-xl border-2 border-dashed border-brand-200 bg-brand-50/40 p-4" data-testid="dialogue-toggle-block">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <Label className="text-sm font-semibold text-ink-900">Multi-voice dialogue (audio only)</Label>
                      <span className="text-[10px] uppercase tracking-widest font-bold text-brand-700 bg-brand-100 rounded-full px-2 py-0.5">Beta</span>
                    </div>
                    <p className="mt-1 text-xs text-ink-500">
                      Instead of one narrator, the script is written with named speakers (e.g. <span className="font-mono">Sarah:</span> and <span className="font-mono">Narrator:</span>) and different voices are used per speaker. <strong className="text-ink-700">This changes audio only</strong> — for characters that visually speak on screen, also turn on <em>Animated scenes</em> below.
                    </p>
                  </div>
                  <button type="button"
                    onClick={() => setDialogueMode(v => !v)}
                    role="switch"
                    aria-checked={dialogueMode}
                    className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors ${dialogueMode ? "bg-brand-600" : "bg-ink-200"}`}
                    data-testid="dialogue-toggle">
                    <span className={`inline-block h-5 w-5 rounded-full bg-white shadow transform transition-transform ${dialogueMode ? "translate-x-6" : "translate-x-1"}`} />
                  </button>
                </div>
              </div>

              {/* Auto-animate with Sora 2 toggle */}
              <div className={`rounded-xl border-2 p-4 ${autoAnimate ? "border-purple-500 bg-gradient-to-br from-purple-50 via-white to-brand-50" : "border-dashed border-purple-200 bg-purple-50/30"}`} data-testid="auto-animate-block">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Label className="text-sm font-semibold text-ink-900">✨ Animated scenes (Sora 2)</Label>
                      <span className="text-[10px] uppercase tracking-widest font-bold text-white bg-gradient-to-r from-purple-600 to-brand-600 rounded-full px-2 py-0.5">Cinematic</span>
                    </div>
                    <p className="mt-1 text-xs text-ink-500">
                      Every scene becomes a real animated 4-second cinematic clip via OpenAI's Sora 2 (not a still image with pan). <strong className="text-purple-700">Costs 5 extra credits per scene</strong> (usually 5–7 scenes per video). You can still turn this off on individual scenes during approval if you want to save credits.
                    </p>
                  </div>
                  <button type="button"
                    onClick={() => setAutoAnimate(v => !v)}
                    role="switch"
                    aria-checked={autoAnimate}
                    className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors ${autoAnimate ? "bg-purple-600" : "bg-ink-200"}`}
                    data-testid="auto-animate-toggle">
                    <span className={`inline-block h-5 w-5 rounded-full bg-white shadow transform transition-transform ${autoAnimate ? "translate-x-6" : "translate-x-1"}`} />
                  </button>
                </div>
              </div>

              {/* Talking Head (Realistic Speaker) — Paid Only */}
              <div className={`rounded-xl border-2 p-4 ${talkingHead ? "border-brand-600 bg-brand-50/60" : "border-dashed border-amber-300 bg-amber-50/40"}`} data-testid="talking-head-block">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Label className="text-sm font-semibold text-ink-900">Realistic Talking Head</Label>
                      <span className="text-[10px] uppercase tracking-widest font-bold text-white bg-gradient-to-r from-amber-500 to-orange-600 rounded-full px-2 py-0.5">Pro</span>
                      {!feature.live_render && talkingHead && (
                        <span className="text-[10px] uppercase tracking-widest font-bold text-amber-800 bg-amber-100 rounded-full px-2 py-0.5">Preview mode</span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-ink-500">
                      Add a real human speaker to your video. Upload your own photo or let AI generate a photorealistic portrait — your character will lip-sync to the narration.
                    </p>
                    {!feature.live_render && (
                      <p className="mt-2 text-[11px] text-amber-700 italic">
                        Lip-sync render is currently in preview — your character will appear in the storyboard, and full lip-sync activates when the studio finalises the render provider.
                      </p>
                    )}
                  </div>
                  <button type="button"
                    onClick={() => {
                      if (!isPaidUser) { openPaywall(); return; }
                      setTalkingHead(v => !v);
                    }}
                    role="switch"
                    aria-checked={talkingHead}
                    className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors ${talkingHead ? "bg-brand-600" : "bg-ink-200"} ${!isPaidUser ? "opacity-70" : ""}`}
                    data-testid="talking-head-toggle">
                    {!isPaidUser && <Lock className="w-3 h-3 text-white absolute left-1.5" />}
                    <span className={`inline-block h-5 w-5 rounded-full bg-white shadow transform transition-transform ${talkingHead ? "translate-x-6" : "translate-x-1"}`} />
                  </button>
                </div>

                {talkingHead && (
                  <div className="mt-4 pt-4 border-t border-brand-200/60" data-testid="character-picker">
                    {charImageUrl ? (
                      <div className="flex items-start gap-4">
                        <div className="relative w-24 h-24 rounded-xl overflow-hidden border-2 border-brand-600 shrink-0 bg-ink-100">
                          <img src={`${process.env.REACT_APP_BACKEND_URL}${charImageUrl}`}
                               alt="Character" className="w-full h-full object-cover"
                               data-testid="character-preview" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">
                            {charSource === "upload" ? "Your uploaded photo" : "AI-generated portrait"}
                          </div>
                          <div className="mt-1 font-heading font-bold text-ink-900">Character ready</div>
                          <p className="text-xs text-ink-500 mt-1">
                            This face will appear in every scene where a character speaks. You can replace it before generating.
                          </p>
                          <Button variant="outline" size="sm" onClick={onClearCharacter}
                            className="mt-2 rounded-full text-xs" data-testid="character-clear-btn">
                            <X className="w-3.5 h-3.5 mr-1" /> Replace character
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="grid md:grid-cols-2 gap-3">
                        {/* Upload path */}
                        <div className="rounded-xl border border-ink-200 bg-white p-4">
                          <div className="flex items-center gap-2">
                            <Upload className="w-4 h-4 text-brand-600" />
                            <div className="font-semibold text-sm">Upload your photo</div>
                          </div>
                          <p className="text-[11px] text-ink-500 mt-1">Any front-facing headshot works best. JPG, PNG or WEBP, max 5 MB.</p>
                          <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp"
                            onChange={onUploadCharacter} className="hidden"
                            data-testid="character-file-input" />
                          <Button size="sm" variant="outline" onClick={() => fileInputRef.current?.click()}
                            disabled={charBusy || !topic.trim()}
                            className="mt-3 rounded-full w-full" data-testid="character-upload-btn">
                            {charBusy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Uploading…</>
                                      : <><Upload className="w-4 h-4 mr-2" /> Choose photo</>}
                          </Button>
                          {!topic.trim() && <p className="text-[10px] text-amber-600 mt-1.5">Enter your topic first ↑</p>}
                        </div>
                        {/* AI-generate path */}
                        <div className="rounded-xl border border-ink-200 bg-white p-4">
                          <div className="flex items-center gap-2">
                            <Wand2 className="w-4 h-4 text-brand-600" />
                            <div className="font-semibold text-sm">Generate with AI</div>
                          </div>
                          <p className="text-[11px] text-ink-500 mt-1">Describe your ideal speaker — we&apos;ll generate a photorealistic portrait.</p>
                          <Input value={charDesc} onChange={(e) => setCharDesc(e.target.value)}
                            placeholder="e.g. Confident Indian woman, 30s, business attire"
                            className="mt-2 text-xs"
                            data-testid="character-desc-input" />
                          <Button size="sm" onClick={onGenerateCharacter}
                            disabled={charBusy || !topic.trim() || charDesc.trim().length < 8}
                            className="mt-2 rounded-full w-full bg-brand-600 hover:bg-brand-700 text-white"
                            data-testid="character-generate-btn">
                            {charBusy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Generating…</>
                                      : <><Wand2 className="w-4 h-4 mr-2" /> Generate portrait</>}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Upsell modal for Free users clicking Talking Head */}
              {showUpsell && (
                <div className="fixed inset-0 z-50 bg-ink-900/60 backdrop-blur-sm flex items-center justify-center p-4"
                     onClick={() => setShowUpsell(false)} data-testid="talking-head-upsell">
                  <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-start justify-between">
                      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-amber-400 to-orange-600 flex items-center justify-center">
                        <Sparkles className="w-6 h-6 text-white" />
                      </div>
                      <button onClick={() => setShowUpsell(false)} className="text-ink-400 hover:text-ink-700" data-testid="upsell-close">
                        <X className="w-5 h-5" />
                      </button>
                    </div>
                    <h3 className="mt-4 font-heading text-2xl font-black tracking-tight">Unlock Realistic Talking Head</h3>
                    <p className="text-sm text-ink-500 mt-2">
                      Bring your videos to life with a real human character that speaks on-screen. Upload your own photo or generate a photorealistic portrait — your character will lip-sync to every scene.
                    </p>
                    <ul className="mt-4 space-y-2 text-sm text-ink-700">
                      <li className="flex items-start gap-2"><span className="text-brand-600 mt-0.5">✓</span> Photorealistic characters, not cartoons</li>
                      <li className="flex items-start gap-2"><span className="text-brand-600 mt-0.5">✓</span> Upload your own face or generate with AI</li>
                      <li className="flex items-start gap-2"><span className="text-brand-600 mt-0.5">✓</span> Same character across every scene</li>
                    </ul>
                    <div className="mt-6 flex gap-2">
                      <Button onClick={() => { setShowUpsell(false); nav("/pricing"); }}
                        className="flex-1 rounded-full bg-brand-600 hover:bg-brand-700 text-white h-11"
                        data-testid="upsell-upgrade-btn">
                        <Sparkles className="w-4 h-4 mr-2" /> See Pro plans
                      </Button>
                      <Button variant="outline" onClick={() => setShowUpsell(false)}
                        className="rounded-full h-11" data-testid="upsell-dismiss-btn">
                        Maybe later
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between pt-2 flex-wrap gap-3">
                <div className="text-xs text-ink-500" data-testid="cost-summary">
                  Uses <span className="font-bold text-brand-700">{activeCredits} credits</span> · You have <span className="font-bold text-ink-900">{currentCredits}</span>
                  {!canAfford && <span className="ml-2 text-amber-700 font-semibold">(insufficient)</span>}
                </div>
                <Button onClick={create} disabled={busy || !topic.trim() || !canAfford || (talkingHead && !charImageUrl)}
                  className="h-11 rounded-full bg-brand-600 hover:bg-brand-700 text-white px-7"
                  data-testid="generate-btn">
                  {busy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Starting…</> : <><Sparkles className="w-4 h-4 mr-2" /> Generate video</>}
                </Button>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
