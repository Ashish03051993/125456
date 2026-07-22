import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { TopBar, Sidebar } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sparkles, Loader2, Briefcase, Film, GraduationCap, Camera, BookOpen } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";

const STYLES = [
  { id: "Business", icon: Briefcase, desc: "Corporate, polished, confident" },
  { id: "Documentary", icon: Film, desc: "Neutral, informative, factual" },
  { id: "Educational", icon: GraduationCap, desc: "Clear, friendly, structured" },
  { id: "Cinematic", icon: Camera, desc: "Dramatic, evocative, slow" },
  { id: "Storytelling", icon: BookOpen, desc: "Warm, character-driven" },
];
const DURATIONS = [1, 3, 5, 10];
const LANGS = ["English", "Hindi", "Spanish", "French", "German", "Portuguese", "Japanese"];

export default function ProjectWizard() {
  const nav = useNavigate();
  const { refresh, user } = useAuth();
  const [topic, setTopic] = useState("");
  const [duration, setDuration] = useState(1);
  const [style, setStyle] = useState("Educational");
  const [language, setLanguage] = useState("English");
  const [voice, setVoice] = useState("female");
  const [busy, setBusy] = useState(false);

  const create = async () => {
    if (!topic.trim()) return toast.error("Please enter a topic.");
    setBusy(true);
    try {
      const { data } = await api.post("/projects", {
        topic, duration_min: duration, style, language, voice,
      });
      await api.post(`/projects/${data.id}/generate`);
      await refresh();
      toast.success("Generation started");
      nav(`/project/${data.id}`);
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
            <p className="mt-2 text-ink-500">We&apos;ll draft the script and storyboard, then generate images, voice and MP4.</p>

            <div className="mt-8 bg-white border border-ink-200 rounded-2xl p-6 space-y-6">
              <div>
                <Label className="text-sm font-semibold" htmlFor="topic">Topic or prompt</Label>
                <Textarea id="topic" data-testid="topic-input" rows={3} value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g. How coffee is grown in Ethiopia — for high school students"
                  className="mt-2" />
              </div>

              <div>
                <Label className="text-sm font-semibold">Duration</Label>
                <div className="mt-2 grid grid-cols-4 gap-2">
                  {DURATIONS.map((d) => (
                    <button key={d} data-testid={`duration-${d}`}
                      onClick={() => setDuration(d)}
                      className={`h-11 rounded-lg border font-medium text-sm transition-colors ${
                        duration === d ? "bg-brand-600 text-white border-brand-600" : "bg-white border-ink-200 hover:border-brand-600"
                      }`}>{d} min</button>
                  ))}
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

              <div className="flex items-center justify-between pt-2">
                <div className="text-xs text-ink-500">Uses 1 credit · {user?.credits} remaining</div>
                <Button onClick={create} disabled={busy || !topic.trim()}
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
