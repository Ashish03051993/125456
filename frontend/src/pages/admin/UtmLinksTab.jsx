import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Copy, Link as LinkIcon, Trash2, Plus, TrendingUp, Linkedin, Mail, MessageSquare, Megaphone, Sparkles, Globe } from "lucide-react";
import { toast } from "sonner";

const PRESETS = [
  { key: "linkedin_post",     label: "LinkedIn Post",       icon: Linkedin,       source: "linkedin",       medium: "post",     hint: "Organic LinkedIn feed post" },
  { key: "linkedin_article",  label: "LinkedIn Article",    icon: Linkedin,       source: "linkedin",       medium: "article",  hint: "Long-form LinkedIn article" },
  { key: "linkedin_dm",       label: "LinkedIn DM",         icon: MessageSquare,  source: "linkedin",       medium: "dm",       hint: "1-on-1 direct outreach" },
  { key: "linkedin_ad",       label: "LinkedIn Ad",         icon: Megaphone,      source: "linkedin",       medium: "cpc",      hint: "Sponsored LinkedIn ad" },
  { key: "email_outbound",    label: "Cold Email",          icon: Mail,           source: "email",          medium: "outbound", hint: "Personal cold email" },
  { key: "community_post",    label: "Community Post",      icon: Sparkles,       source: "community",      medium: "post",     hint: "Slack, Discord, forums" },
  { key: "custom",            label: "Custom",              icon: Globe,          source: "",               medium: "",         hint: "Fill in anything" },
];

const kebab = (s) => (s || "").trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-|-$/g, "");

export default function UtmLinksTab() {
  const [preset, setPreset] = useState(PRESETS[0].key);
  const [name, setName] = useState("");
  const [source, setSource] = useState(PRESETS[0].source);
  const [medium, setMedium] = useState(PRESETS[0].medium);
  const [campaign, setCampaign] = useState("");
  const [content, setContent] = useState("");
  const [term, setTerm] = useState("");
  const [rows, setRows] = useState(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);

  const baseUrl = window.location.origin;

  const load = async () => {
    setBusy(true);
    try {
      const { data } = await api.get("/admin/utm-links");
      setRows(data.rows);
    } catch { toast.error("Could not load campaign links"); }
    finally { setBusy(false); }
  };
  useEffect(() => { load(); }, []);

  const applyPreset = (key) => {
    const p = PRESETS.find((x) => x.key === key);
    setPreset(key);
    if (p) { setSource(p.source); setMedium(p.medium); }
  };

  const previewUrl = useMemo(() => {
    const params = new URLSearchParams();
    if (source)   params.set("utm_source", kebab(source));
    if (medium)   params.set("utm_medium", kebab(medium));
    if (campaign) params.set("utm_campaign", kebab(campaign));
    if (content)  params.set("utm_content", kebab(content));
    if (term)     params.set("utm_term", kebab(term));
    const qs = params.toString();
    return qs ? `${baseUrl}?${qs}` : baseUrl;
  }, [baseUrl, source, medium, campaign, content, term]);

  const create = async (e) => {
    e?.preventDefault?.();
    if (!name.trim()) return toast.error("Give the link a name so you can find it later.");
    if (!source.trim()) return toast.error("utm_source is required (e.g. linkedin).");
    setSaving(true);
    try {
      await api.post("/admin/utm-links", {
        name: name.trim(),
        base_url: baseUrl,
        source, medium, campaign, content, term,
      });
      toast.success("Campaign link created");
      setName(""); setCampaign(""); setContent(""); setTerm("");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to create link");
    } finally { setSaving(false); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this campaign link? Historical analytics stay intact.")) return;
    await api.delete(`/admin/utm-links/${id}`);
    toast.success("Deleted");
    load();
  };

  const copy = (text, label = "URL") => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied`);
  };

  return (
    <div className="mt-6 space-y-6" data-testid="utm-section">
      {/* Builder */}
      <div className="bg-white border border-ink-200 rounded-2xl p-6">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Campaign builder</div>
            <div className="font-heading font-bold text-xl mt-1">Generate a UTM link</div>
            <div className="text-sm text-ink-500 mt-1">
              Pick a preset, name it, hit copy — then paste into your LinkedIn post or DM.
            </div>
          </div>
        </div>

        <div className="mt-5 grid sm:grid-cols-4 md:grid-cols-7 gap-2">
          {PRESETS.map((p) => (
            <button key={p.key} onClick={() => applyPreset(p.key)}
              data-testid={`utm-preset-${p.key}`}
              className={`p-3 rounded-xl border text-left transition-colors ${
                preset === p.key ? "border-brand-600 bg-brand-50" : "border-ink-200 bg-white hover:border-brand-600"
              }`}>
              <p.icon className={`w-5 h-5 ${preset === p.key ? "text-brand-600" : "text-ink-500"}`} />
              <div className="mt-2 font-semibold text-xs sm:text-sm">{p.label}</div>
              <div className="text-[10px] text-ink-500 leading-tight mt-0.5">{p.hint}</div>
            </button>
          ))}
        </div>

        <form onSubmit={create} className="mt-6 grid md:grid-cols-2 gap-4">
          <div>
            <Label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Name (internal only)</Label>
            <Input required value={name} onChange={(e)=>setName(e.target.value)}
              placeholder="e.g. LinkedIn launch post — Dec 12"
              className="mt-2 h-11" data-testid="utm-name" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Campaign</Label>
            <Input value={campaign} onChange={(e)=>setCampaign(e.target.value)}
              placeholder="e.g. private_beta_dec"
              className="mt-2 h-11" data-testid="utm-campaign" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Source (utm_source)</Label>
            <Input required value={source} onChange={(e)=>setSource(e.target.value)}
              placeholder="linkedin"
              className="mt-2 h-11" data-testid="utm-source" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Medium (utm_medium)</Label>
            <Input value={medium} onChange={(e)=>setMedium(e.target.value)}
              placeholder="post / dm / article / cpc"
              className="mt-2 h-11" data-testid="utm-medium" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Content (optional)</Label>
            <Input value={content} onChange={(e)=>setContent(e.target.value)}
              placeholder="e.g. hero_variant_A"
              className="mt-2 h-11" data-testid="utm-content" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Term (optional)</Label>
            <Input value={term} onChange={(e)=>setTerm(e.target.value)}
              placeholder="Keyword or audience"
              className="mt-2 h-11" data-testid="utm-term" />
          </div>

          <div className="md:col-span-2">
            <Label className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Preview URL</Label>
            <div className="mt-2 flex items-stretch gap-2">
              <div className="flex-1 min-w-0 border border-ink-200 rounded-lg bg-ink-50 px-3 py-2.5 font-mono text-xs sm:text-sm text-ink-700 truncate" data-testid="utm-preview">
                {previewUrl}
              </div>
              <Button type="button" variant="outline" onClick={() => copy(previewUrl, "Preview URL")} data-testid="utm-preview-copy">
                <Copy className="w-4 h-4" />
              </Button>
            </div>
          </div>

          <div className="md:col-span-2 flex justify-end">
            <Button type="submit" disabled={saving}
              className="rounded-full bg-brand-600 hover:bg-brand-700 text-white h-11 px-6" data-testid="utm-save">
              <Plus className="w-4 h-4 mr-2" /> {saving ? "Saving…" : "Save campaign link"}
            </Button>
          </div>
        </form>
      </div>

      {/* Saved links */}
      <div className="bg-white border border-ink-200 rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-ink-100 flex items-center justify-between flex-wrap gap-2">
          <div>
            <div className="font-heading font-bold text-lg">Saved campaign links</div>
            <div className="text-xs text-ink-500 mt-0.5">Performance is measured on the last 30 days.</div>
          </div>
          <div className="inline-flex items-center gap-2 text-xs text-brand-700 font-semibold bg-brand-50 rounded-full px-2.5 py-1 border border-brand-100">
            <TrendingUp className="w-3.5 h-3.5" /> Auto-tracked via utm_* params
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[840px]">
            <thead className="bg-ink-50 text-ink-500 text-xs uppercase tracking-widest">
              <tr>
                <th className="text-left px-4 py-3 font-semibold">Name</th>
                <th className="text-left px-4 py-3 font-semibold">Source / Medium</th>
                <th className="text-left px-4 py-3 font-semibold">Campaign</th>
                <th className="text-right px-4 py-3 font-semibold">Sessions</th>
                <th className="text-right px-4 py-3 font-semibold">Demo</th>
                <th className="text-right px-4 py-3 font-semibold">Signups</th>
                <th className="text-right px-4 py-3 font-semibold">Conv.</th>
                <th className="text-right px-4 py-3 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {busy && (!rows || rows.length === 0) && (
                <tr><td colSpan={8} className="px-4 py-10 text-center text-ink-400">Loading…</td></tr>
              )}
              {rows && rows.length === 0 && !busy && (
                <tr><td colSpan={8} className="px-4 py-10 text-center text-ink-400">
                  No campaign links yet. Use the builder above to create your first.
                </td></tr>
              )}
              {rows && rows.map((r) => (
                <tr key={r.id} className="border-t border-ink-100 hover:bg-ink-50/50" data-testid={`utm-row-${r.id}`}>
                  <td className="px-4 py-3">
                    <div className="font-semibold">{r.name}</div>
                    <div className="text-[11px] text-ink-500 font-mono truncate max-w-[260px]" title={r.url}>{r.url}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <span className="text-xs font-semibold rounded-full px-2 py-1 bg-brand-50 text-brand-700 capitalize">{r.params.utm_source || "—"}</span>
                      {r.params.utm_medium && <span className="text-xs text-ink-500">· {r.params.utm_medium}</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-ink-500 font-mono text-xs">{r.params.utm_campaign || "—"}</td>
                  <td className="px-4 py-3 text-right font-mono">{r.stats.sessions}</td>
                  <td className="px-4 py-3 text-right font-mono">{r.stats.demo_clicks}</td>
                  <td className="px-4 py-3 text-right font-mono">{r.stats.signups}</td>
                  <td className="px-4 py-3 text-right font-mono font-semibold text-brand-700">{r.stats.conversion_pct}%</td>
                  <td className="px-4 py-3 text-right">
                    <div className="inline-flex items-center gap-1">
                      <Button size="sm" variant="outline" onClick={() => copy(r.url, r.name)} data-testid={`utm-copy-${r.id}`}>
                        <Copy className="w-3.5 h-3.5" />
                      </Button>
                      <a href={r.url} target="_blank" rel="noreferrer">
                        <Button size="sm" variant="outline" data-testid={`utm-open-${r.id}`}>
                          <LinkIcon className="w-3.5 h-3.5" />
                        </Button>
                      </a>
                      <Button size="sm" variant="outline" onClick={() => remove(r.id)} data-testid={`utm-delete-${r.id}`}>
                        <Trash2 className="w-3.5 h-3.5 text-red-600" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
