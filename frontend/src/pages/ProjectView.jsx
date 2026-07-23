import { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { TopBar, Sidebar } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Loader2, Download, Youtube, Instagram, AlertCircle, ArrowLeft, PlayCircle, Monitor, Smartphone, Pencil, Copy as CopyIcon, RefreshCw, Check, X, Image as ImageIcon, Mic, Play, Pause, Volume2 } from "lucide-react";
import { toast } from "sonner";

const STAGES = ["writing script","generating images","generating voiceover","composing video","done"];

const FORMAT_ICON = { landscape: Monitor, vertical: Smartphone };

export default function ProjectView() {
  const { id } = useParams();
  const [p, setP] = useState(null);
  const [formats, setFormats] = useState([]);
  const [selected, setSelected] = useState(null);
  const [videoMissing, setVideoMissing] = useState(false);
  const [editingScript, setEditingScript] = useState(false);
  const [draftScenes, setDraftScenes] = useState([]);
  const [draftTitle, setDraftTitle] = useState("");
  const [scriptBusy, setScriptBusy] = useState(false);
  // Image + Voice approval state
  const [imgBusy, setImgBusy] = useState({});           // { [sceneIdx]: true } for per-scene regen
  const [imgAllBusy, setImgAllBusy] = useState(false);  // approving/regenerating all
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [pickedVoice, setPickedVoice] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const { data } = await api.get(`/projects/${id}`);
        if (alive) setP(data);
      } catch { /* ignore */ }
    };
    load();
    const iv = setInterval(() => {
      if (p?.status === "generating") load();
    }, 3000);
    return () => { alive = false; clearInterval(iv); };
  }, [id, p?.status]);

  useEffect(() => {
    api.get("/formats").then((r) => setFormats(r.data)).catch(() => setFormats([]));
  }, []);

  const availableFormats = useMemo(() => {
    if (!p?.video_urls) {
      return p?.video_url ? [{ id: "landscape", label: "Video", url: p.video_url, aspect: "16:9" }] : [];
    }
    return formats
      .filter((f) => p.video_urls?.[f.id])
      .map((f) => ({ id: f.id, label: f.label, url: p.video_urls[f.id], aspect: f.aspect,
                     width: f.width, height: f.height, platforms: f.platforms }));
  }, [p, formats]);

  const active = selected
    ? availableFormats.find((f) => f.id === selected) || availableFormats[0]
    : availableFormats[0];

  // Reset the "video file missing" warning whenever the active format changes.
  // MUST be declared before any conditional/early returns to respect the
  // Rules of Hooks.
  useEffect(() => { setVideoMissing(false); }, [active?.id]);

  // Sync local edit state with backend scenes when awaiting approval
  useEffect(() => {
    if (p?.status === "awaiting_script_approval" && !editingScript) {
      setDraftScenes(p.scenes || []);
      setDraftTitle(p.title || "");
    }
  }, [p?.status, p?.scenes, p?.title, editingScript]);

  const regenerateScript = async () => {
    setScriptBusy(true);
    try {
      await api.post(`/projects/${id}/script/regenerate`);
      toast.success("Rewriting your script…");
      const { data } = await api.get(`/projects/${id}`);
      setP(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Regeneration failed"); }
    finally { setScriptBusy(false); }
  };

  const saveScriptEdits = async () => {
    setScriptBusy(true);
    try {
      const { data } = await api.patch(`/projects/${id}/script`, {
        title: draftTitle,
        scenes: draftScenes.map((s) => ({
          narration: s.narration, subtitle: s.subtitle, image_prompt: s.image_prompt,
        })),
      });
      setP(data);
      setEditingScript(false);
      toast.success("Script updated");
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
    finally { setScriptBusy(false); }
  };

  const approveScript = async () => {
    setScriptBusy(true);
    try {
      await api.post(`/projects/${id}/script/approve`);
      toast.success("Script approved — generating visuals now");
      const { data } = await api.get(`/projects/${id}`);
      setP(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Approve failed"); }
    finally { setScriptBusy(false); }
  };

  // --- Image approval handlers ---
  const regenerateOneImage = async (idx) => {
    setImgBusy((b) => ({ ...b, [idx]: true }));
    try {
      const { data } = await api.post(`/projects/${id}/images/regenerate/${idx}`);
      setP(data);
      toast.success(`Scene ${idx + 1} refreshed`);
    } catch (e) { toast.error(e?.response?.data?.detail || "Regen failed"); }
    finally { setImgBusy((b) => ({ ...b, [idx]: false })); }
  };

  const regenerateAllImages = async () => {
    setImgAllBusy(true);
    try {
      await api.post(`/projects/${id}/images/regenerate`);
      toast.success("Regenerating all visuals…");
      const { data } = await api.get(`/projects/${id}`);
      setP(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Regen failed"); }
    finally { setImgAllBusy(false); }
  };

  const approveImages = async () => {
    setImgAllBusy(true);
    try {
      await api.post(`/projects/${id}/images/approve`);
      toast.success("Visuals approved — generating voiceover");
      const { data } = await api.get(`/projects/${id}`);
      setP(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Approve failed"); }
    finally { setImgAllBusy(false); }
  };

  // --- Voice approval handlers ---
  const regenerateVoice = async (newVoice) => {
    setVoiceBusy(true);
    try {
      await api.post(`/projects/${id}/voice/regenerate`, newVoice ? { voice: newVoice } : {});
      toast.success("Regenerating voiceover…");
      const { data } = await api.get(`/projects/${id}`);
      setP(data);
      setPickedVoice(null);
    } catch (e) { toast.error(e?.response?.data?.detail || "Regen failed"); }
    finally { setVoiceBusy(false); }
  };

  const approveVoice = async () => {
    setVoiceBusy(true);
    try {
      await api.post(`/projects/${id}/voice/approve`);
      toast.success("Voice approved — composing your final video");
      const { data } = await api.get(`/projects/${id}`);
      setP(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Approve failed"); }
    finally { setVoiceBusy(false); }
  };

  if (!p) return (
    <div className="min-h-screen bg-ink-50">
      <TopBar />
      <div className="flex items-center justify-center py-24 text-ink-500"><Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading…</div>
    </div>
  );

  const videoSrc = active ? `${process.env.REACT_APP_BACKEND_URL}${active.url}` : null;

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
            {p.status === "ready" && active && (
              <div className="flex items-center gap-2 flex-wrap">
                <a href={videoSrc} download={`${p.id}_${active.id}.mp4`}>
                  <Button className="rounded-full bg-brand-600 hover:bg-brand-700 text-white" data-testid="download-btn">
                    <Download className="w-4 h-4 mr-2" /> Download {active.aspect}
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

          {/* Status (during actual generation) */}
          {p.status === "generating" && (
            <div className="mt-6 bg-white border border-ink-200 rounded-2xl p-6" data-testid="generating-panel">
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

          {/* Script Approval Gate — user reviews & approves the script before visuals are generated */}
          {p.status === "awaiting_script_approval" && (
            <div className="mt-6 space-y-4" data-testid="script-approval-panel">
              <div className="bg-brand-600 text-white rounded-2xl p-5 flex items-center justify-between flex-wrap gap-3">
                <div>
                  <div className="text-xs uppercase tracking-widest font-bold opacity-80">Step 1 of 3 · Your approval needed</div>
                  <div className="mt-1 font-heading font-extrabold text-2xl tracking-tighter">Review your script</div>
                  <p className="text-sm opacity-90 mt-1 max-w-lg">Edit the narration, tweak subtitles, or regenerate. Nothing else runs until you approve.</p>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <Button variant="outline" onClick={regenerateScript} disabled={scriptBusy}
                    className="rounded-full bg-transparent border-white/50 text-white hover:bg-white/10"
                    data-testid="script-regen-btn">
                    <RefreshCw className="w-4 h-4 mr-2" /> Regenerate
                  </Button>
                  {editingScript ? (
                    <>
                      <Button variant="outline" onClick={() => { setEditingScript(false); setDraftScenes(p.scenes || []); setDraftTitle(p.title || ""); }} disabled={scriptBusy}
                        className="rounded-full bg-transparent border-white/50 text-white hover:bg-white/10"
                        data-testid="script-cancel-btn">
                        <X className="w-4 h-4 mr-2" /> Cancel
                      </Button>
                      <Button onClick={saveScriptEdits} disabled={scriptBusy}
                        className="rounded-full bg-white text-brand-700 hover:bg-white/90"
                        data-testid="script-save-btn">
                        <Check className="w-4 h-4 mr-2" /> Save edits
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button variant="outline" onClick={() => setEditingScript(true)}
                        className="rounded-full bg-transparent border-white/50 text-white hover:bg-white/10"
                        data-testid="script-edit-btn">
                        <Pencil className="w-4 h-4 mr-2" /> Edit
                      </Button>
                      <Button onClick={approveScript} disabled={scriptBusy}
                        className="rounded-full bg-white text-brand-700 hover:bg-white/90 font-semibold"
                        data-testid="script-approve-btn">
                        <Check className="w-4 h-4 mr-2" /> Approve & generate visuals
                      </Button>
                    </>
                  )}
                </div>
              </div>

              {editingScript && (
                <div className="bg-white border border-ink-200 rounded-2xl p-5">
                  <label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Title</label>
                  <input type="text" value={draftTitle} onChange={(e) => setDraftTitle(e.target.value)}
                    data-testid="script-edit-title"
                    className="mt-1 w-full rounded-lg border border-ink-200 px-3 py-2 font-heading font-bold text-lg" />
                </div>
              )}

              <div className="grid md:grid-cols-2 gap-4">
                {(editingScript ? draftScenes : (p.scenes || [])).map((sc, i) => (
                  <div key={sc.idx} className="bg-white border border-ink-200 rounded-2xl p-5" data-testid={`draft-scene-${sc.idx}`}>
                    <div className="flex items-center justify-between">
                      <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Scene {sc.idx + 1}</div>
                      {sc.heading && <div className="text-[11px] text-ink-500 truncate max-w-[60%]">{sc.heading}</div>}
                    </div>
                    {editingScript ? (
                      <>
                        <label className="mt-3 text-[11px] uppercase tracking-widest text-ink-500 font-semibold">Narration</label>
                        <textarea rows={3} value={sc.narration || ""}
                          data-testid={`edit-narration-${sc.idx}`}
                          onChange={(e) => {
                            const upd = [...draftScenes]; upd[i] = { ...upd[i], narration: e.target.value }; setDraftScenes(upd);
                          }}
                          className="mt-1 w-full rounded-lg border border-ink-200 px-3 py-2 text-sm text-ink-900" />
                        <label className="mt-3 text-[11px] uppercase tracking-widest text-ink-500 font-semibold">On-screen subtitle</label>
                        <input type="text" value={sc.subtitle || ""}
                          data-testid={`edit-subtitle-${sc.idx}`}
                          onChange={(e) => {
                            const upd = [...draftScenes]; upd[i] = { ...upd[i], subtitle: e.target.value }; setDraftScenes(upd);
                          }}
                          className="mt-1 w-full rounded-lg border border-ink-200 px-3 py-2 text-sm text-ink-900" />
                        <label className="mt-3 text-[11px] uppercase tracking-widest text-ink-500 font-semibold">Image prompt (used to generate the visual)</label>
                        <textarea rows={2} value={sc.image_prompt || ""}
                          data-testid={`edit-image-prompt-${sc.idx}`}
                          onChange={(e) => {
                            const upd = [...draftScenes]; upd[i] = { ...upd[i], image_prompt: e.target.value }; setDraftScenes(upd);
                          }}
                          className="mt-1 w-full rounded-lg border border-ink-200 px-3 py-2 text-xs font-mono text-ink-700" />
                      </>
                    ) : (
                      <>
                        <p className="mt-3 text-sm text-ink-800 leading-relaxed">{sc.narration}</p>
                        <div className="mt-3 rounded-lg bg-brand-50 text-brand-700 text-xs font-mono px-3 py-1.5 inline-block">
                          &ldquo;{sc.subtitle}&rdquo;
                        </div>
                        <div className="mt-2 text-[11px] text-ink-400 line-clamp-2">
                          <span className="font-semibold">Visual:</span> {sc.image_prompt}
                        </div>
                      </>
                    )}
                  </div>
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

          {/* Image Approval Gate — Step 2 of 3 */}
          {p.status === "awaiting_image_approval" && (
            <div className="mt-6 space-y-4" data-testid="image-approval-panel">
              <div className="bg-brand-600 text-white rounded-2xl p-5 flex items-center justify-between flex-wrap gap-3">
                <div>
                  <div className="text-xs uppercase tracking-widest font-bold opacity-80">Step 2 of 3 · Your approval needed</div>
                  <div className="mt-1 font-heading font-extrabold text-2xl tracking-tighter">Review your visuals</div>
                  <p className="text-sm opacity-90 mt-1 max-w-lg">Regenerate any scene you don't love. When you're happy, approve to unlock the voiceover.</p>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <Button variant="outline" onClick={regenerateAllImages} disabled={imgAllBusy}
                    className="rounded-full bg-transparent border-white/50 text-white hover:bg-white/10"
                    data-testid="images-regen-all-btn">
                    <RefreshCw className="w-4 h-4 mr-2" /> Regenerate all
                  </Button>
                  <Button onClick={approveImages} disabled={imgAllBusy}
                    className="rounded-full bg-white text-brand-700 hover:bg-white/90 font-semibold"
                    data-testid="images-approve-btn">
                    <Check className="w-4 h-4 mr-2" /> Approve & generate voice
                  </Button>
                </div>
              </div>

              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {(p.scenes || []).map((sc) => (
                  <div key={sc.idx} className="bg-white border border-ink-200 rounded-2xl overflow-hidden" data-testid={`img-scene-${sc.idx}`}>
                    <div className="aspect-video bg-ink-100 relative">
                      {sc.image_url ? (
                        <img src={`${process.env.REACT_APP_BACKEND_URL}${sc.image_url}`} alt={sc.heading}
                             className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-ink-400"><ImageIcon className="w-8 h-8" /></div>
                      )}
                      <div className="absolute bottom-2 left-2 bg-black/70 text-white text-[11px] px-2 py-1 rounded font-mono">Scene {sc.idx + 1}</div>
                      {imgBusy[sc.idx] && (
                        <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                          <Loader2 className="w-6 h-6 text-white animate-spin" />
                        </div>
                      )}
                    </div>
                    <div className="p-3 flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-xs font-semibold text-ink-700 truncate">{sc.heading}</div>
                        <div className="text-[11px] text-ink-400 mt-0.5 line-clamp-2">{sc.image_prompt}</div>
                      </div>
                      <Button size="sm" variant="outline"
                        onClick={() => regenerateOneImage(sc.idx)} disabled={imgBusy[sc.idx] || imgAllBusy}
                        className="rounded-full text-xs shrink-0"
                        data-testid={`img-regen-${sc.idx}`}>
                        <RefreshCw className="w-3.5 h-3.5 mr-1" /> Regen
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Voice Approval Gate — Step 3 of 3 */}
          {p.status === "awaiting_voice_approval" && (
            <div className="mt-6 space-y-4" data-testid="voice-approval-panel">
              <div className="bg-brand-600 text-white rounded-2xl p-5 flex items-center justify-between flex-wrap gap-3">
                <div>
                  <div className="text-xs uppercase tracking-widest font-bold opacity-80">Step 3 of 3 · Your approval needed</div>
                  <div className="mt-1 font-heading font-extrabold text-2xl tracking-tighter">Preview your voiceover</div>
                  <p className="text-sm opacity-90 mt-1 max-w-lg">Listen back, switch voice, or regenerate. When it sounds right, we'll compose the final video.</p>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <Button onClick={approveVoice} disabled={voiceBusy}
                    className="rounded-full bg-white text-brand-700 hover:bg-white/90 font-semibold"
                    data-testid="voice-approve-btn">
                    <Check className="w-4 h-4 mr-2" /> Approve & compose video
                  </Button>
                </div>
              </div>

              <div className="bg-white border border-ink-200 rounded-2xl p-6">
                <div className="flex items-center gap-3">
                  <div className="w-11 h-11 rounded-full bg-brand-50 border border-brand-200 flex items-center justify-center">
                    <Volume2 className="w-5 h-5 text-brand-700" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-heading font-bold text-lg">Full voiceover</div>
                    <div className="text-xs text-ink-500">Voice: <span className="font-semibold text-ink-700 uppercase">{p.voice}</span> · Language: {p.language}</div>
                  </div>
                </div>
                {p.audio_url && (
                  <audio controls className="w-full mt-4"
                         src={`${process.env.REACT_APP_BACKEND_URL}${p.audio_url}`}
                         data-testid="voice-audio-player" />
                )}

                <div className="mt-6 flex flex-wrap items-center gap-3">
                  <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Switch voice:</div>
                  {["female", "male"].map((v) => {
                    const isCurrent = p.voice === v && !pickedVoice;
                    const isPicked = pickedVoice === v;
                    return (
                      <button key={v} onClick={() => setPickedVoice(v)}
                        disabled={voiceBusy}
                        className={`inline-flex items-center gap-1.5 text-xs font-semibold rounded-full px-3 py-1.5 border transition-colors ${
                          isPicked ? "bg-brand-600 text-white border-brand-600"
                          : isCurrent ? "bg-brand-50 text-brand-700 border-brand-200"
                          : "bg-white text-ink-700 border-ink-200 hover:border-brand-600"
                        }`}
                        data-testid={`voice-pick-${v}`}>
                        <Mic className="w-3.5 h-3.5" /> {v.charAt(0).toUpperCase() + v.slice(1)}
                        {isCurrent && <span className="text-[10px] opacity-70">· current</span>}
                      </button>
                    );
                  })}
                  <Button variant="outline" onClick={() => regenerateVoice(pickedVoice)} disabled={voiceBusy}
                    className="rounded-full ml-auto" data-testid="voice-regen-btn">
                    {voiceBusy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Regenerating…</>
                              : <><RefreshCw className="w-4 h-4 mr-2" /> Regenerate {pickedVoice && pickedVoice !== p.voice ? `with ${pickedVoice}` : ""}</>}
                  </Button>
                </div>
              </div>

              {/* Read-along storyboard for context while previewing voice */}
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {(p.scenes || []).map((sc) => (
                  <div key={sc.idx} className="bg-white border border-ink-200 rounded-2xl overflow-hidden">
                    <div className="aspect-video bg-ink-100 relative">
                      {sc.image_url && (
                        <img src={`${process.env.REACT_APP_BACKEND_URL}${sc.image_url}`} alt={sc.heading}
                             className="w-full h-full object-cover" />
                      )}
                      <div className="absolute bottom-2 left-2 bg-black/70 text-white text-[11px] px-2 py-1 rounded font-mono">Scene {sc.idx + 1}</div>
                    </div>
                    <div className="p-3">
                      <div className="text-[11px] text-brand-700 font-mono">&ldquo;{sc.subtitle}&rdquo;</div>
                      <div className="text-xs text-ink-500 mt-1 line-clamp-2">{sc.narration}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}


          {/* Video Player + Format Switcher */}
          {p.status === "ready" && active && (
            <div className="mt-6" data-testid="format-switcher-wrap">
              {availableFormats.length > 1 && (
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <span className="text-xs uppercase tracking-widest text-ink-500 font-semibold mr-1">Format:</span>
                  {availableFormats.map((f) => {
                    const Icon = FORMAT_ICON[f.id] || Monitor;
                    const isActive = active.id === f.id;
                    return (
                      <button key={f.id} onClick={() => setSelected(f.id)}
                        data-testid={`format-${f.id}`}
                        className={`inline-flex items-center gap-2 text-xs font-semibold rounded-full px-3 py-1.5 border transition-colors ${
                          isActive ? "bg-brand-600 text-white border-brand-600" : "bg-white text-ink-700 border-ink-200 hover:border-brand-600"
                        }`}>
                        <Icon className="w-3.5 h-3.5" /> {f.label} <span className="opacity-70">· {f.aspect}</span>
                      </button>
                    );
                  })}
                </div>
              )}
              <div className={`bg-black rounded-2xl overflow-hidden border border-ink-200 mx-auto ${
                active.aspect === "9:16" ? "max-w-[400px] aspect-[9/16]" : "aspect-video"
              }`}>
                <video src={videoSrc} controls key={active.id}
                       onError={() => setVideoMissing(true)}
                       className="w-full h-full object-contain" data-testid="video-player" />
              </div>
              {videoMissing && (
                <div className="mt-3 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800" data-testid="video-missing-warning">
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                  <div>
                    <div className="font-semibold">Video failed to load</div>
                    <div className="text-xs mt-0.5">The {active.aspect} file couldn&apos;t be played — this may be a network, decoding or storage issue. Please regenerate from the dashboard.</div>
                  </div>
                </div>
              )}
              {active.platforms?.length > 0 && (
                <div className="mt-3 text-center text-xs text-ink-500">
                  Ready for: {active.platforms.map(pl => (
                    <span key={pl} className="inline-block mx-1 px-2 py-0.5 rounded-full bg-ink-100 text-ink-700 font-medium">{pl}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Scenes storyboard (only shown after all approvals) */}
          {!["awaiting_script_approval", "awaiting_image_approval", "awaiting_voice_approval"].includes(p.status) && p.scenes?.length > 0 && (
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

          {/* Script (only shown after all approvals) */}
          {!["awaiting_script_approval", "awaiting_image_approval", "awaiting_voice_approval"].includes(p.status) && p.script && (
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
