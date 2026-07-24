import { useEffect, useState, useRef, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, resolveMediaUrl } from "@/lib/api";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

// Format catalogue for the download dropdown — id maps to keys in `video_urls`.
const DOWNLOAD_FORMATS = [
  { id: "landscape", label: "YouTube (16:9)", aspect: "16:9" },
  { id: "portrait",  label: "Reels · TikTok · Shorts (9:16)", aspect: "9:16" },
  { id: "square",    label: "Instagram feed (1:1)", aspect: "1:1" },
];
import { TopBar, Sidebar } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Video, Loader2, AlertCircle, CheckCircle2, Trash2, Pencil, Copy as CopyIcon, Check, X, Search, SlidersHorizontal, Sparkles, Download, ImageDown, PlayCircle } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import LowCreditNudge from "@/components/LowCreditNudge";
import { useAuth } from "@/lib/auth";

const STATUS_STYLES = {
  draft: "bg-ink-100 text-ink-700",
  generating: "bg-brand-50 text-brand-700",
  ready: "bg-emerald-50 text-emerald-700",
  error: "bg-red-50 text-red-700",
};

const STATUS_FILTERS = [
  { id: "all",         label: "All",         match: () => true },
  { id: "draft",       label: "Drafts",      match: (p) => p.status === "draft" || p.status?.startsWith("awaiting_") },
  { id: "generating",  label: "Generating",  match: (p) => p.status === "generating" },
  { id: "ready",       label: "Ready",       match: (p) => p.status === "ready" },
  { id: "error",       label: "Failed",      match: (p) => p.status === "error" },
];

export default function Dashboard() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);       // project id currently in rename mode
  const [draftTitle, setDraftTitle] = useState("");
  const [renameBusy, setRenameBusy] = useState(false);
  const [dupBusy, setDupBusy] = useState({});
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const editInputRef = useRef(null);
  const prevStatusRef = useRef(new Map()); // { projectId → previous status } for transition detection
  const navigate = useNavigate();
  const { user, setUser } = useAuth();
  const [previewProject, setPreviewProject] = useState(null);   // opens the quick-preview modal

  // Celebrate a monthly free-credit refill exactly once (backend sets a transient
  // refill_delta on the /auth/me response the first time the new month is seen).
  useEffect(() => {
    const delta = user?.refill_delta;
    if (!delta || delta <= 0) return;
    toast.success(`${delta} free credits refilled — enjoy!`, {
      description: "Your monthly free grant just landed. One more video is on us.",
      icon: <Sparkles className="w-4 h-4 text-brand-600" />,
      duration: 6000,
    });
    // Clear the transient flag so the toast fires exactly once per session
    setUser({ ...user, refill_delta: 0 });
  }, [user?.refill_delta]); // eslint-disable-line react-hooks/exhaustive-deps


  const load = async () => {
    try {
      const { data } = await api.get("/projects");
      // Detect projects that transitioned generating → ready or → error since the
      // last poll, and fire a celebration/error toast so users never miss a completion.
      const prev = prevStatusRef.current;
      if (prev.size > 0) {
        for (const p of data) {
          const was = prev.get(p.id);
          if (!was) continue;
          const wasBusy = was === "generating" || was?.startsWith?.("awaiting_");
          if (wasBusy && p.status === "ready") {
            toast.success("Video ready 🎬", {
              description: p.title || p.topic || "Your generation just finished.",
              icon: <CheckCircle2 className="w-4 h-4 text-emerald-600" />,
              duration: 8000,
              action: {
                label: "Open",
                onClick: () => navigate(`/project/${p.id}`),
              },
            });
          } else if (wasBusy && p.status === "error") {
            toast.error("Generation failed", {
              description: `${p.title || p.topic || "This project"} couldn't complete. Credits were refunded.`,
              icon: <AlertCircle className="w-4 h-4 text-rose-600" />,
              duration: 8000,
              action: {
                label: "Review",
                onClick: () => navigate(`/project/${p.id}`),
              },
            });
          }
        }
      }
      prevStatusRef.current = new Map(data.map((p) => [p.id, p.status]));
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

  const startRename = (p) => {
    setEditingId(p.id);
    setDraftTitle(p.title || p.topic || "");
    // Focus + select once React renders the input
    setTimeout(() => editInputRef.current?.select(), 30);
  };

  const cancelRename = () => { setEditingId(null); setDraftTitle(""); };

  const saveRename = async (id) => {
    const title = draftTitle.trim();
    if (!title) { toast.error("Title cannot be empty"); return; }
    setRenameBusy(true);
    try {
      const { data } = await api.patch(`/projects/${id}/title`, { title });
      setProjects((ps) => ps.map((p) => (p.id === id ? data : p)));
      toast.success("Renamed");
      cancelRename();
    } catch (e) { toast.error(e?.response?.data?.detail || "Rename failed"); }
    finally { setRenameBusy(false); }
  };

  const duplicate = async (id) => {
    setDupBusy((b) => ({ ...b, [id]: true }));
    try {
      const { data } = await api.post(`/projects/${id}/duplicate`);
      toast.success("Duplicated — opening editor");
      navigate(`/project/${data.id}`);
    } catch (e) {
      // 402 already handled globally by paywall modal; other errors -> toast
      const detail = e?.response?.data?.detail;
      if (typeof detail !== "object") toast.error(detail || "Duplicate failed");
    } finally { setDupBusy((b) => ({ ...b, [id]: false })); }
  };

  // Filter counts + result list — memoised so hover-repaint doesn't re-filter
  const statusCounts = useMemo(() => {
    const c = {};
    for (const f of STATUS_FILTERS) c[f.id] = projects.filter(f.match).length;
    return c;
  }, [projects]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filter = STATUS_FILTERS.find((f) => f.id === statusFilter) || STATUS_FILTERS[0];
    return projects.filter((p) => {
      if (!filter.match(p)) return false;
      if (!q) return true;
      const hay = `${p.title || ""} ${p.topic || ""} ${p.style || ""} ${p.language || ""}`.toLowerCase();
      return hay.includes(q);
    });
  }, [projects, query, statusFilter]);

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

          <LowCreditNudge />

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
            <>
              {/* Search + status filter row */}
              <div className="mt-6 flex flex-wrap items-center gap-3" data-testid="dashboard-filter-row">
                <div className="relative flex-1 min-w-[220px] max-w-md">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-400 pointer-events-none" />
                  <Input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={`Search ${projects.length} project${projects.length === 1 ? "" : "s"}…`}
                    className="pl-9 pr-9 h-10 rounded-full border-ink-200 bg-white"
                    data-testid="dashboard-search-input"
                  />
                  {query && (
                    <button onClick={() => setQuery("")}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-700"
                      title="Clear"
                      data-testid="dashboard-search-clear">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
                <div className="flex items-center gap-1.5 flex-wrap" data-testid="dashboard-status-filter">
                  {STATUS_FILTERS.map((f) => {
                    const active = statusFilter === f.id;
                    const count = statusCounts[f.id];
                    return (
                      <button key={f.id}
                        onClick={() => setStatusFilter(f.id)}
                        disabled={count === 0 && f.id !== "all"}
                        className={[
                          "inline-flex items-center gap-1.5 text-xs font-semibold rounded-full px-3 py-1.5 border transition-colors",
                          active
                            ? "bg-ink-900 text-white border-ink-900"
                            : count === 0 && f.id !== "all"
                              ? "bg-white text-ink-400 border-ink-100 cursor-not-allowed"
                              : "bg-white text-ink-700 border-ink-200 hover:border-brand-600 hover:text-brand-600",
                        ].join(" ")}
                        data-testid={`filter-${f.id}`}>
                        {f.label}
                        <span className={`text-[10px] font-mono ${active ? "text-white/70" : "text-ink-400"}`}>{count}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Result summary line */}
              <div className="mt-4 text-xs text-ink-500 flex items-center gap-2">
                <SlidersHorizontal className="w-3.5 h-3.5" />
                <span data-testid="filter-summary">
                  Showing <span className="font-semibold text-ink-900">{filtered.length}</span> of {projects.length}
                  {query && <> matching &ldquo;<span className="font-semibold text-ink-900">{query}</span>&rdquo;</>}
                  {statusFilter !== "all" && <> · status: {STATUS_FILTERS.find((f) => f.id === statusFilter)?.label}</>}
                </span>
              </div>

              {filtered.length === 0 ? (
                <div className="mt-8 rounded-2xl border border-dashed border-ink-200 bg-white p-12 text-center" data-testid="no-matches">
                  <Search className="w-8 h-8 mx-auto text-ink-400" />
                  <div className="mt-3 font-heading font-bold">No projects match your filters</div>
                  <p className="mt-1 text-sm text-ink-500">Try a broader keyword or clear the status filter.</p>
                  <Button variant="outline" onClick={() => { setQuery(""); setStatusFilter("all"); }}
                    className="mt-4 rounded-full" data-testid="reset-filters-btn">
                    Reset filters
                  </Button>
                </div>
              ) : (
                <div className="mt-6 grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {filtered.map((p) => (
                <div key={p.id} className="rounded-2xl bg-white border border-ink-200 overflow-hidden hover:-translate-y-1 hover:shadow-lg transition-all" data-testid={`project-card-${p.id}`}>
                  <div className="aspect-video bg-ink-100 relative">
                    {p.scenes?.[0]?.image_url ? (
                      <img src={resolveMediaUrl(p.scenes[0].image_url)} alt="cover" className="w-full h-full object-cover" />
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
                    {editingId === p.id ? (
                      <div className="flex items-center gap-1" data-testid={`rename-row-${p.id}`}>
                        <input
                          ref={editInputRef}
                          value={draftTitle}
                          onChange={(e) => setDraftTitle(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") saveRename(p.id);
                            if (e.key === "Escape") cancelRename();
                          }}
                          disabled={renameBusy}
                          maxLength={200}
                          className="flex-1 min-w-0 font-heading font-bold text-lg bg-brand-50 border border-brand-300 rounded-md px-2 py-1 outline-none focus:border-brand-600"
                          data-testid={`rename-input-${p.id}`}
                        />
                        <button onClick={() => saveRename(p.id)} disabled={renameBusy}
                          className="p-1.5 rounded-md text-emerald-600 hover:bg-emerald-50"
                          data-testid={`rename-save-${p.id}`}>
                          {renameBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                        </button>
                        <button onClick={cancelRename} disabled={renameBusy}
                          className="p-1.5 rounded-md text-ink-400 hover:text-ink-700 hover:bg-ink-50"
                          data-testid={`rename-cancel-${p.id}`}>
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ) : (
                      <div className="group flex items-center gap-1.5">
                        <div className="font-heading font-bold text-lg truncate flex-1 min-w-0" data-testid={`project-title-${p.id}`}>
                          {p.title || p.topic}
                        </div>
                        <button onClick={() => startRename(p)}
                          className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded text-ink-400 hover:text-brand-600 hover:bg-brand-50 shrink-0"
                          title="Rename"
                          data-testid={`rename-btn-${p.id}`}>
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
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
                      <div className="flex items-center gap-1">
                        {p.status === "ready" && (
                          <button onClick={() => setPreviewProject(p)}
                                  className="p-1.5 rounded-md text-ink-400 hover:text-brand-600 hover:bg-brand-50"
                                  title="Quick preview"
                                  data-testid={`preview-${p.id}`}>
                            <PlayCircle className="w-4 h-4" />
                          </button>
                        )}
                        {p.status === "ready" && (() => {
                          // Assemble the set of available formats. New projects populate `video_urls`
                          // (one URL per aspect). Legacy projects only have a single `video_url`.
                          const available = DOWNLOAD_FORMATS
                            .filter((f) => p.video_urls?.[f.id])
                            .map((f) => ({ ...f, url: p.video_urls[f.id] }));
                          if (available.length === 0 && p.video_url) {
                            available.push({ id: "video", label: "Video", aspect: "", url: p.video_url });
                          }
                          const thumbUrl = p.scenes?.[0]?.image_url;
                          const safe = (p.title || p.topic || p.id).replace(/[^a-z0-9\-_]+/gi, "_").slice(0, 60);
                          return (
                            <>
                              {available.length === 1 && (
                                <a href={resolveMediaUrl(available[0].url)}
                                   download={`${safe}.mp4`}
                                   className="p-1.5 rounded-md text-ink-400 hover:text-brand-600 hover:bg-brand-50"
                                   title={`Download video${available[0].aspect ? ` (${available[0].aspect})` : ""}`}
                                   data-testid={`download-video-${p.id}`}>
                                  <Download className="w-4 h-4" />
                                </a>
                              )}
                              {available.length > 1 && (
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild>
                                    <button className="p-1.5 rounded-md text-ink-400 hover:text-brand-600 hover:bg-brand-50"
                                            title="Download video"
                                            data-testid={`download-video-${p.id}`}>
                                      <Download className="w-4 h-4" />
                                    </button>
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end" className="w-56">
                                    <DropdownMenuLabel className="text-[10px] uppercase tracking-widest text-ink-500">
                                      Download format
                                    </DropdownMenuLabel>
                                    <DropdownMenuSeparator />
                                    {available.map((fmt) => (
                                      <DropdownMenuItem asChild key={fmt.id}>
                                        <a href={resolveMediaUrl(fmt.url)}
                                           download={`${safe}_${fmt.id}.mp4`}
                                           className="cursor-pointer"
                                           data-testid={`download-video-${p.id}-${fmt.id}`}>
                                          <Download className="w-3.5 h-3.5 mr-2" /> {fmt.label}
                                        </a>
                                      </DropdownMenuItem>
                                    ))}
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              )}
                              {thumbUrl && (
                                <a href={resolveMediaUrl(thumbUrl)}
                                   download={`${safe}_thumbnail.png`}
                                   className="p-1.5 rounded-md text-ink-400 hover:text-brand-600 hover:bg-brand-50"
                                   title="Download thumbnail (PNG)"
                                   data-testid={`download-thumb-${p.id}`}>
                                  <ImageDown className="w-4 h-4" />
                                </a>
                              )}
                            </>
                          );
                        })()}
                        <button onClick={() => duplicate(p.id)} disabled={dupBusy[p.id]}
                          className="p-1.5 rounded-md text-ink-400 hover:text-brand-600 hover:bg-brand-50 disabled:opacity-50"
                          title="Duplicate as new draft"
                          data-testid={`duplicate-${p.id}`}>
                          {dupBusy[p.id] ? <Loader2 className="w-4 h-4 animate-spin" /> : <CopyIcon className="w-4 h-4" />}
                        </button>
                        <button onClick={() => del(p.id)}
                          className="p-1.5 rounded-md text-ink-400 hover:text-red-600 hover:bg-red-50"
                          title="Delete"
                          data-testid={`delete-${p.id}`}>
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
              )}
            </>
          )}
        </main>
      </div>

      {/* Quick preview modal — plays the video without navigating away from Dashboard */}
      <Dialog open={!!previewProject} onOpenChange={(open) => !open && setPreviewProject(null)}>
        <DialogContent className="max-w-3xl p-0 overflow-hidden" data-testid="preview-modal">
          {previewProject && (() => {
            const videoUrl = previewProject.video_urls?.landscape
              || previewProject.video_urls?.portrait
              || previewProject.video_urls?.square
              || previewProject.video_url;
            const src = videoUrl ? resolveMediaUrl(videoUrl) : null;
            return (
              <>
                <DialogHeader className="p-6 pb-3">
                  <DialogTitle className="font-heading text-2xl font-black tracking-tight truncate">
                    {previewProject.title || previewProject.topic}
                  </DialogTitle>
                  <DialogDescription>
                    {previewProject.style} · {previewProject.duration_min} min · {previewProject.voice}
                  </DialogDescription>
                </DialogHeader>
                <div className="bg-black">
                  {src ? (
                    <video src={src} controls autoPlay className="w-full max-h-[65vh] bg-black"
                           data-testid="preview-video" />
                  ) : (
                    <div className="text-white/70 text-sm py-16 text-center">Video source not available.</div>
                  )}
                </div>
                <div className="flex items-center justify-between gap-3 p-4 border-t border-ink-100">
                  <Link to={`/project/${previewProject.id}`}
                        onClick={() => setPreviewProject(null)}
                        className="text-sm font-semibold text-brand-600 hover:underline"
                        data-testid="preview-open-full">
                    Open full project →
                  </Link>
                  {src && (
                    <a href={src}
                       download={`${(previewProject.title || previewProject.topic || previewProject.id).replace(/[^a-z0-9\-_]+/gi,"_").slice(0,60)}.mp4`}
                       className="inline-flex items-center gap-1.5 rounded-full bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold px-4 py-2"
                       data-testid="preview-download-btn">
                      <Download className="w-4 h-4" /> Download
                    </a>
                  )}
                </div>
              </>
            );
          })()}
        </DialogContent>
      </Dialog>
    </div>
  );
}
