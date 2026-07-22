import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { TopBar, Sidebar } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Plus, Video, Loader2, AlertCircle, CheckCircle2, Trash2 } from "lucide-react";
import { toast } from "sonner";

const STATUS_STYLES = {
  draft: "bg-ink-100 text-ink-700",
  generating: "bg-brand-50 text-brand-700",
  ready: "bg-emerald-50 text-emerald-700",
  error: "bg-red-50 text-red-700",
};

export default function Dashboard() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const { data } = await api.get("/projects");
      setProjects(data);
    } catch (e) {
      toast.error("Could not load projects");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); const iv = setInterval(load, 4000); return () => clearInterval(iv); }, []);

  const del = async (id) => {
    if (!window.confirm("Delete this project?")) return;
    await api.delete(`/projects/${id}`);
    toast.success("Project deleted");
    load();
  };

  return (
    <div className="min-h-screen bg-ink-50">
      <TopBar />
      <div className="max-w-7xl mx-auto flex">
        <Sidebar />
        <main className="flex-1 p-8" data-testid="dashboard-main">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Workspace</div>
              <h1 className="mt-1 font-heading text-4xl font-extrabold tracking-tighter">Your projects</h1>
            </div>
            <Link to="/new"><Button className="rounded-full bg-brand-600 hover:bg-brand-700 text-white h-11 px-6" data-testid="new-project-btn">
              <Plus className="w-4 h-4 mr-2" /> New video
            </Button></Link>
          </div>

          {loading ? (
            <div className="mt-16 flex justify-center text-ink-500"><Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading…</div>
          ) : projects.length === 0 ? (
            <div className="mt-16 rounded-2xl border border-dashed border-ink-200 bg-white p-16 text-center">
              <Video className="w-10 h-10 mx-auto text-ink-400" />
              <div className="mt-4 font-heading font-bold text-xl">No videos yet</div>
              <p className="mt-2 text-ink-500">Kick off your first generation — you have free credits waiting.</p>
              <Link to="/new"><Button className="mt-6 rounded-full bg-brand-600 hover:bg-brand-700 text-white" data-testid="empty-new-btn">
                <Plus className="w-4 h-4 mr-2" /> Create first video
              </Button></Link>
            </div>
          ) : (
            <div className="mt-8 grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((p) => (
                <div key={p.id} className="rounded-2xl bg-white border border-ink-200 overflow-hidden hover:-translate-y-1 hover:shadow-lg transition-all" data-testid={`project-card-${p.id}`}>
                  <div className="aspect-video bg-ink-100 relative">
                    {p.scenes?.[0]?.image_url ? (
                      <img src={`${process.env.REACT_APP_BACKEND_URL}${p.scenes[0].image_url}`} alt="cover" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-ink-400">
                        <Video className="w-8 h-8" />
                      </div>
                    )}
                    <span className={`absolute top-3 right-3 text-[10px] tracking-widest uppercase font-semibold rounded-full px-2 py-1 ${STATUS_STYLES[p.status]}`} data-testid={`status-${p.id}`}>
                      {p.status === "generating" && <Loader2 className="w-3 h-3 inline mr-1 animate-spin" />}
                      {p.status === "ready" && <CheckCircle2 className="w-3 h-3 inline mr-1" />}
                      {p.status === "error" && <AlertCircle className="w-3 h-3 inline mr-1" />}
                      {p.status}
                    </span>
                  </div>
                  <div className="p-4">
                    <div className="font-heading font-bold text-lg truncate">{p.title || p.topic}</div>
                    <div className="text-xs text-ink-500 mt-0.5">{p.style} · {p.duration_min} min · {p.voice}</div>
                    {p.status === "generating" && (
                      <div className="mt-3">
                        <div className="text-xs text-ink-500">{p.stage} · {p.progress}%</div>
                        <div className="mt-1 h-1.5 bg-ink-100 rounded-full overflow-hidden">
                          <div className="h-full bg-brand-600 transition-all" style={{ width: `${p.progress}%` }} />
                        </div>
                      </div>
                    )}
                    <div className="mt-4 flex items-center justify-between">
                      <Link to={`/project/${p.id}`} className="text-brand-600 font-semibold text-sm hover:underline" data-testid={`open-${p.id}`}>Open →</Link>
                      <button onClick={() => del(p.id)} className="text-ink-400 hover:text-red-600" data-testid={`delete-${p.id}`}><Trash2 className="w-4 h-4" /></button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
