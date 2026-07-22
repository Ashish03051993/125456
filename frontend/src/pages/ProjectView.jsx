import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { TopBar, Sidebar } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Loader2, Download, Youtube, Instagram, AlertCircle, ArrowLeft, PlayCircle } from "lucide-react";
import { toast } from "sonner";

const STAGES = ["writing script","generating images","generating voiceover","composing video","done"];

export default function ProjectView() {
  const { id } = useParams();
  const [p, setP] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const { data } = await api.get(`/projects/${id}`);
        if (alive) setP(data);
      } catch { /* ignore */ }
    };
    load();
    const iv = setInterval(() => { if (p?.status !== "ready" && p?.status !== "error") load(); }, 3000);
    return () => { alive = false; clearInterval(iv); };
  }, [id, p?.status]);

  if (!p) return (
    <div className="min-h-screen bg-ink-50">
      <TopBar />
      <div className="flex items-center justify-center py-24 text-ink-500"><Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading…</div>
    </div>
  );

  const videoUrl = p.video_url ? `${process.env.REACT_APP_BACKEND_URL}${p.video_url}` : null;

  return (
    <div className="min-h-screen bg-ink-50">
      <TopBar />
      <div className="max-w-7xl mx-auto flex">
        <Sidebar />
        <main className="flex-1 p-8" data-testid="project-view">
          <Link to="/dashboard" className="inline-flex items-center gap-1 text-ink-500 hover:text-ink-900 text-sm mb-4"><ArrowLeft className="w-4 h-4" /> Back to projects</Link>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">{p.style} · {p.duration_min} min · {p.language}</div>
              <h1 className="mt-1 font-heading text-4xl font-extrabold tracking-tighter" data-testid="project-title">{p.title || p.topic}</h1>
              {p.hook && <p className="mt-2 text-ink-500 max-w-2xl italic">{p.hook}</p>}
            </div>
            {p.status === "ready" && (
              <div className="flex items-center gap-2 flex-wrap">
                <a href={videoUrl} download={`${p.id}.mp4`}>
                  <Button className="rounded-full bg-brand-600 hover:bg-brand-700 text-white" data-testid="download-btn">
                    <Download className="w-4 h-4 mr-2" /> Download MP4
                  </Button>
                </a>
                <Button variant="outline" className="rounded-full" onClick={() => toast.info("YouTube export: connect account in Settings (coming soon)")} data-testid="youtube-btn">
                  <Youtube className="w-4 h-4 mr-2" /> YouTube
                </Button>
                <Button variant="outline" className="rounded-full" onClick={() => toast.info("Instagram export coming soon")} data-testid="instagram-btn">
                  <Instagram className="w-4 h-4 mr-2" /> Instagram
                </Button>
              </div>
            )}
          </div>

          {/* Status */}
          {p.status !== "ready" && p.status !== "error" && (
            <div className="mt-6 bg-white border border-ink-200 rounded-2xl p-6">
              <div className="flex items-center gap-3">
                <Loader2 className="w-5 h-5 animate-spin text-brand-600" />
                <div className="font-heading font-bold text-lg capitalize">{p.stage}</div>
              </div>
              <div className="mt-4 h-2 bg-ink-100 rounded-full overflow-hidden">
                <div className="h-full bg-brand-600 transition-all" style={{ width: `${p.progress}%` }} data-testid="progress-bar" />
              </div>
              <div className="mt-4 flex gap-3 flex-wrap">
                {STAGES.map((s) => (
                  <div key={s} className={`text-xs px-2.5 py-1 rounded-full font-semibold capitalize ${
                    p.stage === s ? "bg-brand-600 text-white" : "bg-ink-100 text-ink-500"
                  }`}>{s}</div>
                ))}
              </div>
            </div>
          )}

          {p.status === "error" && (
            <div className="mt-6 bg-red-50 border border-red-200 rounded-2xl p-6 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
              <div>
                <div className="font-heading font-bold text-red-700">Generation failed</div>
                <div className="text-sm text-red-600 mt-1">{p.error}</div>
                <div className="text-xs text-ink-500 mt-2">Your credit was refunded. Try again from the dashboard.</div>
              </div>
            </div>
          )}

          {/* Video Player */}
          {p.status === "ready" && (
            <div className="mt-6 bg-black rounded-2xl overflow-hidden border border-ink-200">
              <video src={videoUrl} controls className="w-full aspect-video" data-testid="video-player" />
            </div>
          )}

          {/* Scenes storyboard */}
          {p.scenes?.length > 0 && (
            <div className="mt-10">
              <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Storyboard</div>
              <h2 className="mt-1 font-heading text-3xl font-bold tracking-tight">Scenes ({p.scenes.length})</h2>
              <div className="mt-6 grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {p.scenes.map((sc) => (
                  <div key={sc.idx} className="bg-white border border-ink-200 rounded-2xl overflow-hidden" data-testid={`scene-${sc.idx}`}>
                    <div className="aspect-video bg-ink-100 relative">
                      {sc.image_url ? (
                        <img src={`${process.env.REACT_APP_BACKEND_URL}${sc.image_url}`} className="w-full h-full object-cover" alt={sc.heading} />
                      ) : <div className="w-full h-full flex items-center justify-center text-ink-400"><PlayCircle className="w-8 h-8" /></div>}
                      <div className="absolute bottom-2 left-2 bg-black/70 text-white text-[11px] px-2 py-1 rounded font-mono">#{sc.idx + 1}</div>
                    </div>
                    <div className="p-4">
                      <div className="font-heading font-bold">{sc.heading}</div>
                      <div className="text-xs text-brand-700 mt-1 font-mono">&ldquo;{sc.subtitle}&rdquo;</div>
                      <p className="text-sm text-ink-500 mt-2 line-clamp-3">{sc.narration}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Script */}
          {p.script && (
            <div className="mt-10">
              <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Script</div>
              <div className="mt-2 bg-white border border-ink-200 rounded-2xl p-6 text-ink-700 leading-relaxed whitespace-pre-line" data-testid="script-text">{p.script}</div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
