import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { TopBar, Sidebar } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Users, Video, Mail, TrendingUp, BarChart3, Copy, Search, FlaskConical, Send, Trophy, AlertTriangle, Link as LinkIcon, Download, ExternalLink } from "lucide-react";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, LineChart, Line } from "recharts";
import UtmLinksTab from "@/pages/admin/UtmLinksTab";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import HealthTile from "@/components/admin/HealthTile";

const TABS = [
  { id: "overview",   label: "Overview",    icon: BarChart3 },
  { id: "waitlist",   label: "Waitlist",    icon: Mail },
  { id: "analytics",  label: "Analytics",   icon: TrendingUp },
  { id: "experiments",label: "A/B Tests",   icon: FlaskConical },
  { id: "utm",        label: "UTM Links",   icon: LinkIcon },
  { id: "digest",     label: "Daily Digest",icon: Send },
];

function StatCard({ label, value, icon: Icon, testid }) {
  return (
    <div className="bg-white border border-ink-200 rounded-2xl p-5" data-testid={testid}>
      <div className="flex items-center justify-between">
        <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">{label}</div>
        <Icon className="w-4 h-4 text-brand-600" />
      </div>
      <div className="mt-2 font-heading text-3xl font-extrabold tracking-tighter">{value}</div>
    </div>
  );
}

function ChipRow({ label, items, active, onSelect, testidPrefix, testid }) {
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid={testid}>
      <span className="text-[10px] text-ink-500 font-semibold uppercase tracking-widest mr-1 w-16 shrink-0">{label}</span>
      {items.map((it, i) => {
        const key = it.key || "";
        const isActive = active === key;
        const testId = key ? `${testidPrefix}-${key}` : `${testidPrefix}-all`;
        return (
          <button key={`${testidPrefix}-${key || "all"}-${i}`}
            onClick={() => onSelect(key)}
            data-testid={testId}
            className={`text-xs font-semibold rounded-full px-3 py-1.5 border transition-colors capitalize ${
              isActive ? "bg-brand-600 text-white border-brand-600" : "bg-white text-ink-700 border-ink-200 hover:border-brand-600"
            }`}>
            {key || "All"} <span className="opacity-70 ml-1">({it.n})</span>
          </button>
        );
      })}
    </div>
  );
}

export default function AdminPanel() {
  const [params, setParams] = useSearchParams();
  const activeTab = params.get("tab") || "overview";
  const [stats, setStats] = useState(null);
  const [waitlist, setWaitlist] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [experiments, setExperiments] = useState(null);
  const [attribution, setAttribution] = useState(null);
  const [sanity, setSanity] = useState(null);
  const [untaggedOpen, setUntaggedOpen] = useState(false);
  const [untagged, setUntagged] = useState(null);
  const [untaggedBusy, setUntaggedBusy] = useState(false);
  const [digestList, setDigestList] = useState(null);
  const [digestConfig, setDigestConfig] = useState(null);
  const [digestPreview, setDigestPreview] = useState(null);
  const [sendingDigest, setSendingDigest] = useState(false);
  const [sourceFilter, setSourceFilter] = useState("");
  const [planFilter, setPlanFilter] = useState("");
  const [variantFilter, setVariantFilter] = useState("");
  const [q, setQ] = useState("");

  const load = async () => {
    try {
      const wParams = {};
      if (sourceFilter)  wParams.source = sourceFilter;
      if (planFilter)    wParams.plan = planFilter;
      if (variantFilter) wParams.variant = variantFilter;
      const [s, w, a, e, matrix, san, d, dc, dp] = await Promise.all([
        api.get("/admin/stats"),
        api.get("/admin/waitlist", { params: wParams }),
        api.get("/admin/analytics"),
        api.get("/admin/experiments"),
        api.get("/admin/attribution-matrix"),
        api.get("/admin/sanity"),
        api.get("/admin/digest"),
        api.get("/admin/digest/config"),
        api.get("/admin/digest/preview"),
      ]);
      setStats(s.data); setWaitlist(w.data); setAnalytics(a.data);
      setExperiments(e.data); setAttribution(matrix.data);
      setSanity(san.data);
      setDigestList(d.data);
      setDigestConfig(dc.data); setDigestPreview(dp.data);
    } catch { toast.error("Could not load admin data"); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [sourceFilter, planFilter, variantFilter]);

  const activeFilters = [
    ...(sourceFilter  ? [{ label: `Source: ${sourceFilter}`,    clear: () => setSourceFilter("") }]  : []),
    ...(planFilter    ? [{ label: `Plan: ${planFilter}`,        clear: () => setPlanFilter("") }]    : []),
    ...(variantFilter ? [{ label: `Variant: ${variantFilter}`,  clear: () => setVariantFilter("") }] : []),
  ];
  const clearAllFilters = () => { setSourceFilter(""); setPlanFilter(""); setVariantFilter(""); };

  const openUntaggedDrilldown = async () => {
    setUntaggedOpen(true);
    if (untagged) return; // cached
    setUntaggedBusy(true);
    try {
      const { data } = await api.get("/admin/sanity/untagged", { params: { limit: 100 } });
      setUntagged(data);
    } catch { toast.error("Failed to load untagged sessions"); }
    finally { setUntaggedBusy(false); }
  };

  const sendDigestNow = async () => {
    setSendingDigest(true);
    try {
      const { data } = await api.post("/admin/digest/send-now");
      if (data.delivery?.sent) toast.success("Digest sent!");
      else toast.info(`Digest generated. Email skipped: ${data.delivery?.reason}`);
      // Refresh the whole tab so KPIs, preview and archive stay in sync
      const [d, dp] = await Promise.all([
        api.get("/admin/digest"),
        api.get("/admin/digest/preview"),
      ]);
      setDigestList(d.data);
      setDigestPreview(dp.data);
    } catch { toast.error("Failed to generate digest"); }
    finally { setSendingDigest(false); }
  };

  const filteredWaitlist = useMemo(() => {
    if (!waitlist) return [];
    const s = q.toLowerCase().trim();
    if (!s) return waitlist.entries;
    return waitlist.entries.filter(
      (r) => r.email.toLowerCase().includes(s) ||
             (r.name || "").toLowerCase().includes(s) ||
             (r.use_case || "").toLowerCase().includes(s)
    );
  }, [waitlist, q]);

  const exportCsv = () => {
    const url = new URL(`${process.env.REACT_APP_BACKEND_URL}/api/admin/waitlist.csv`);
    if (sourceFilter)  url.searchParams.set("source", sourceFilter);
    if (planFilter)    url.searchParams.set("plan", planFilter);
    if (variantFilter) url.searchParams.set("variant", variantFilter);
    const a = document.createElement("a");
    a.href = url.toString();
    a.download = "";
    document.body.appendChild(a); a.click(); a.remove();
  };

  const copyEmails = async () => {
    if (!waitlist?.entries?.length) return;
    const emails = waitlist.entries.map(r => r.email).join(", ");
    try {
      await navigator.clipboard.writeText(emails);
      toast.success(`Copied ${waitlist.entries.length} emails`);
    } catch { toast.error("Copy failed — check browser permissions"); }
  };

  return (
    <div className="min-h-screen bg-ink-50">
      <TopBar />
      <div className="max-w-7xl mx-auto flex">
        <Sidebar />
        <main className="flex-1 p-5 sm:p-8 min-w-0" data-testid="admin-main">
          <div className="flex items-start sm:items-center justify-between gap-3 flex-wrap">
            <div>
              <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Admin · Phase 1</div>
              <h1 className="mt-1 font-heading text-3xl sm:text-4xl font-extrabold tracking-tighter">Market validation</h1>
            </div>
          </div>

          {/* Tabs */}
          <div className="mt-6 border-b border-ink-200 flex items-center gap-1 overflow-x-auto">
            {TABS.map((t) => (
              <button key={t.id} data-testid={`tab-${t.id}`}
                onClick={() => setParams(t.id === "overview" ? {} : { tab: t.id })}
                className={`inline-flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 transition-colors whitespace-nowrap ${
                  activeTab === t.id ? "border-brand-600 text-brand-700" : "border-transparent text-ink-500 hover:text-ink-900"
                }`}>
                <t.icon className="w-4 h-4" /> {t.label}
              </button>
            ))}
          </div>

          {/* Overview */}
          {activeTab === "overview" && stats && (
            <div className="mt-6 space-y-6">
              <HealthTile />
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard label="Waitlist" value={stats.waitlist_total} icon={Mail} testid="stat-waitlist" />
                <StatCard label="Signups · 24h" value={stats.waitlist_24h} icon={TrendingUp} testid="stat-signups-24h" />
                <StatCard label="Events · 24h" value={stats.events_24h} icon={BarChart3} testid="stat-events-24h" />
                <StatCard label="Users" value={stats.total_users} icon={Users} testid="stat-users" />
              </div>
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard label="Waitlist clicks" value={stats.waitlist_clicks || 0} icon={TrendingUp} testid="stat-waitlist-clicks" />
                <StatCard label="Demo views" value={stats.demo_views || 0} icon={BarChart3} testid="stat-demo-views" />
                <StatCard label="Demo impressions" value={stats.demo_impressions || 0} icon={BarChart3} testid="stat-demo-impressions" />
                <StatCard label="Book demo clicks" value={stats.book_demo_clicks || 0} icon={Mail} testid="stat-book-demo-clicks" />
              </div>
              <div className="bg-white border border-ink-200 rounded-2xl p-6">
                <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Waitlist interest by plan</div>
                <div className="mt-4 grid sm:grid-cols-4 gap-3">
                  {["free","pro","business","enterprise","unspecified"].map((p) => {
                    const n = stats.waitlist_by_plan?.[p] || 0;
                    if (!n && p !== "pro") return null;
                    return (
                      <div key={p} className="rounded-xl bg-brand-50 border border-brand-100 p-4" data-testid={`plan-count-${p}`}>
                        <div className="text-xs uppercase tracking-widest text-brand-700 font-semibold capitalize">{p}</div>
                        <div className="mt-1 font-heading text-2xl font-extrabold text-brand-900">{n}</div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Analytics Sanity Panel */}
              {sanity && (
                <div className="bg-white border border-ink-200 rounded-2xl p-6" data-testid="sanity-panel">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div>
                      <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Analytics sanity</div>
                      <div className="font-heading font-bold text-xl mt-1">Data-quality check</div>
                      <div className="text-sm text-ink-500 mt-1 max-w-xl">
                        Quick health signals so you can trust the numbers before scaling acquisition. Zero warnings = analytics is clean.
                      </div>
                    </div>
                    <div className={`text-xs font-semibold rounded-full px-3 py-1.5 ${
                      (sanity.orphan_signups.count + sanity.duplicate_emails.count === 0 && sanity.unattributed_sessions.pct < 25)
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : "bg-amber-50 text-amber-700 border border-amber-200"
                    }`} data-testid="sanity-verdict">
                      {(sanity.orphan_signups.count + sanity.duplicate_emails.count === 0 && sanity.unattributed_sessions.pct < 25)
                        ? "✓ Analytics healthy"
                        : "⚠ Review recommended"}
                    </div>
                  </div>

                  <div className="mt-5 grid sm:grid-cols-3 gap-3">
                    {/* Orphan signups */}
                    <div className="rounded-xl border border-ink-200 p-4" data-testid="sanity-orphans">
                      <div className="flex items-center justify-between">
                        <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Orphan signups</div>
                        <AlertTriangle className={`w-4 h-4 ${sanity.orphan_signups.count > 0 ? "text-amber-600" : "text-ink-300"}`} />
                      </div>
                      <div className="mt-2 font-heading text-3xl font-extrabold tracking-tighter">{sanity.orphan_signups.count}</div>
                      <div className="text-xs text-ink-500 mt-1">
                        of {sanity.totals.waitlist} signups have no matching page_view session — visitor arrived before analytics loaded or was untagged.
                      </div>
                    </div>

                    {/* Unattributed sessions */}
                    <button type="button"
                      onClick={openUntaggedDrilldown}
                      className="text-left rounded-xl border border-ink-200 p-4 hover:border-brand-600 hover:shadow-sm transition-all cursor-pointer group"
                      data-testid="sanity-unattributed">
                      <div className="flex items-center justify-between">
                        <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Untagged sessions</div>
                        <div className="flex items-center gap-1">
                          <ExternalLink className="w-3.5 h-3.5 text-ink-400 group-hover:text-brand-600" />
                          <AlertTriangle className={`w-4 h-4 ${sanity.unattributed_sessions.pct >= 25 ? "text-amber-600" : "text-ink-300"}`} />
                        </div>
                      </div>
                      <div className="mt-2 font-heading text-3xl font-extrabold tracking-tighter">
                        {sanity.unattributed_sessions.count}
                        <span className="text-base text-ink-500 font-mono ml-2">{sanity.unattributed_sessions.pct}%</span>
                      </div>
                      <div className="text-xs text-ink-500 mt-1">
                        of {sanity.unattributed_sessions.total_sessions} sessions have no <span className="font-mono">utm_source</span>. <span className="text-brand-600 font-semibold group-hover:underline">Investigate →</span>
                      </div>
                    </button>

                    {/* Duplicate emails */}
                    <div className="rounded-xl border border-ink-200 p-4" data-testid="sanity-duplicates">
                      <div className="flex items-center justify-between">
                        <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Duplicate emails</div>
                        <AlertTriangle className={`w-4 h-4 ${sanity.duplicate_emails.count > 0 ? "text-amber-600" : "text-ink-300"}`} />
                      </div>
                      <div className="mt-2 font-heading text-3xl font-extrabold tracking-tighter">{sanity.duplicate_emails.count}</div>
                      <div className="text-xs text-ink-500 mt-1">
                        {sanity.duplicate_emails.count === 0
                          ? "No duplicate signups — unique-email guard is working."
                          : "email(s) appear more than once. Investigate before running a paid campaign."}
                      </div>
                    </div>
                  </div>

                  {sanity.duplicate_emails.count > 0 && (
                    <div className="mt-4 rounded-xl bg-amber-50 border border-amber-200 p-3 text-xs" data-testid="sanity-dup-list">
                      <div className="font-semibold text-amber-800 mb-1">Duplicated:</div>
                      <div className="flex flex-wrap gap-1.5">
                        {sanity.duplicate_emails.sample.slice(0, 10).map((d) => (
                          <span key={d.email} className="rounded-full bg-white border border-amber-200 px-2 py-0.5 font-mono text-amber-800">
                            {d.email} <span className="text-amber-600">×{d.count}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Waitlist — empty state */}
          {activeTab === "waitlist" && waitlist && waitlist.total === 0 && (
            <div className="mt-8" data-testid="waitlist-empty">
              <div className="bg-gradient-to-br from-brand-50 via-white to-violet-50 border border-brand-100 rounded-3xl p-8 sm:p-12 text-center">
                <div className="mx-auto w-16 h-16 rounded-2xl bg-brand-600/10 flex items-center justify-center">
                  <Mail className="w-8 h-8 text-brand-600" />
                </div>
                <h2 className="mt-5 font-heading text-2xl sm:text-3xl font-extrabold tracking-tighter">No signups yet — let&apos;s change that</h2>
                <p className="mt-2 text-ink-500 max-w-lg mx-auto text-sm sm:text-base">
                  Your waitlist is ready. Share your beta once on LinkedIn to seed the first cohort — most founders see their first 5-10 signups from the announcement post alone.
                </p>
                <div className="mt-6 flex flex-wrap justify-center gap-3">
                  <Button
                    className="rounded-full bg-brand-600 hover:bg-brand-700 text-white"
                    data-testid="empty-share-linkedin-btn"
                    onClick={() => {
                      const url = `${window.location.origin}/?utm_source=linkedin&utm_medium=organic&utm_campaign=launch`;
                      const text = "I'm building AI Video Studio — turn any topic into a ready-to-post video (16:9 for YouTube + 9:16 for LinkedIn/Reels) in minutes. Reserve your spot 👇";
                      window.open(`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}&summary=${encodeURIComponent(text)}`, "_blank", "noopener,noreferrer");
                    }}>
                    <LinkIcon className="w-4 h-4 mr-2" /> Share beta on LinkedIn
                  </Button>
                  <Button
                    variant="outline"
                    className="rounded-full"
                    data-testid="empty-copy-link-btn"
                    onClick={async () => {
                      const url = `${window.location.origin}/?utm_source=linkedin&utm_medium=organic&utm_campaign=launch`;
                      try { await navigator.clipboard.writeText(url); toast.success("Launch link copied"); }
                      catch { toast.error("Copy failed — please copy manually"); }
                    }}>
                    <Copy className="w-4 h-4 mr-2" /> Copy launch link
                  </Button>
                  <Button
                    variant="outline"
                    className="rounded-full"
                    data-testid="empty-utm-tab-btn"
                    onClick={() => setParams({ tab: "utm" })}>
                    <LinkIcon className="w-4 h-4 mr-2" /> Build tracked UTM link
                  </Button>
                </div>
                <div className="mt-8 grid sm:grid-cols-3 gap-3 max-w-xl mx-auto text-left">
                  <div className="rounded-xl bg-white border border-ink-200 p-3 text-xs">
                    <div className="font-semibold text-ink-900">1. Announce</div>
                    <div className="text-ink-500 mt-0.5">Post on LinkedIn with the tracked link above.</div>
                  </div>
                  <div className="rounded-xl bg-white border border-ink-200 p-3 text-xs">
                    <div className="font-semibold text-ink-900">2. DM 10 people</div>
                    <div className="text-ink-500 mt-0.5">Personal invites convert 5-10× higher than posts.</div>
                  </div>
                  <div className="rounded-xl bg-white border border-ink-200 p-3 text-xs">
                    <div className="font-semibold text-ink-900">3. Watch this tab</div>
                    <div className="text-ink-500 mt-0.5">Signups show up here in real time.</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Waitlist */}
          {activeTab === "waitlist" && waitlist && waitlist.total > 0 && (
            <div className="mt-6" data-testid="waitlist-section">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="text-ink-500 text-sm">
                  <span className="font-heading font-bold text-ink-900 text-xl" data-testid="segment-count">{waitlist.count}</span>
                  {activeFilters.length > 0
                    ? <> of {waitlist.total} <span className="text-brand-700">·</span> filtered by <span className="font-semibold">{activeFilters.map(f => f.label).join(", ")}</span></>
                    : <> people on the waitlist</>}
                </div>
                <div className="flex items-center gap-2">
                  {activeFilters.length > 0 && (
                    <Button variant="outline" onClick={clearAllFilters} data-testid="clear-filters-btn">Clear filters</Button>
                  )}
                  <Button variant="outline" onClick={copyEmails} data-testid="copy-emails-btn"><Copy className="w-4 h-4 mr-2" /> Copy emails</Button>
                  <Button onClick={exportCsv} className="bg-brand-600 hover:bg-brand-700 text-white" data-testid="export-csv-btn">
                    <Download className="w-4 h-4 mr-2" /> Export CSV
                  </Button>
                </div>
              </div>

              {/* Filter chip rows */}
              <div className="mt-4 space-y-2" data-testid="filter-chips">
                <ChipRow label="Source" testid="segment-chips"
                  items={[{ key: "", n: waitlist.total }, ...(waitlist.by_source || []).map(s => ({ key: s.source, n: s.n }))]}
                  active={sourceFilter} onSelect={setSourceFilter} testidPrefix="segment" />
                <ChipRow label="Plan" testid="plan-chips"
                  items={[{ key: "", n: waitlist.total }, ...(waitlist.by_plan || []).map(p => ({ key: p.plan, n: p.n }))]}
                  active={planFilter} onSelect={setPlanFilter} testidPrefix="plan" />
                <ChipRow label="Variant" testid="variant-chips"
                  items={[{ key: "", n: waitlist.total }, ...(waitlist.by_variant || []).map(v => ({ key: v.variant, n: v.n }))]}
                  active={variantFilter} onSelect={setVariantFilter} testidPrefix="variant" />
              </div>

              <div className="mt-4 relative max-w-sm">
                <Search className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <Input placeholder="Search email, name or use case" value={q} onChange={(e)=>setQ(e.target.value)}
                  className="pl-9" data-testid="waitlist-search" />
              </div>
              <div className="mt-4 bg-white border border-ink-200 rounded-2xl overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm min-w-[840px]">
                    <thead className="bg-ink-50 text-ink-500 text-xs uppercase tracking-widest">
                      <tr>
                        <th className="text-left px-3 py-3 font-semibold">#</th>
                        <th className="text-left px-3 py-3 font-semibold">Email</th>
                        <th className="text-left px-3 py-3 font-semibold">Source</th>
                        <th className="text-left px-3 py-3 font-semibold">Campaign</th>
                        <th className="text-left px-3 py-3 font-semibold">Plan</th>
                        <th className="text-left px-3 py-3 font-semibold">Variant</th>
                        <th className="text-left px-3 py-3 font-semibold">Use case</th>
                        <th className="text-left px-3 py-3 font-semibold">When</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredWaitlist.map((r) => (
                        <tr key={r.id} className="border-t border-ink-100 hover:bg-ink-50/50" data-testid={`waitlist-row-${r.id}`}>
                          <td className="px-3 py-2.5 font-mono text-ink-500">{r.position}</td>
                          <td className="px-3 py-2.5">
                            <div className="font-semibold">{r.email}</div>
                            {r.name && <div className="text-[11px] text-ink-500">{r.name}</div>}
                          </td>
                          <td className="px-3 py-2.5">
                            <span className="text-xs font-semibold rounded-full px-2 py-1 bg-ink-100 text-ink-700 capitalize">{r.source || "direct"}</span>
                            {r.medium && <span className="text-[11px] text-ink-500 ml-1">· {r.medium}</span>}
                          </td>
                          <td className="px-3 py-2.5 font-mono text-xs text-ink-500">{r.campaign || "—"}</td>
                          <td className="px-3 py-2.5"><span className="text-xs font-semibold rounded-full px-2 py-1 bg-brand-50 text-brand-700 capitalize">{r.plan_interest}</span></td>
                          <td className="px-3 py-2.5">
                            {r.variant
                              ? <span className="text-xs font-mono font-bold rounded-full px-2 py-1 bg-violet-50 text-violet-700">{r.variant}</span>
                              : <span className="text-[11px] text-ink-400">—</span>}
                          </td>
                          <td className="px-3 py-2.5 text-ink-500 max-w-[220px] truncate" title={r.use_case}>{r.use_case || "—"}</td>
                          <td className="px-3 py-2.5 text-ink-500 whitespace-nowrap">{new Date(r.created_at).toLocaleString()}</td>
                        </tr>
                      ))}
                      {filteredWaitlist.length === 0 && (
                        <tr><td colSpan={8} className="px-3 py-10 text-center text-ink-400">No entries match this filter.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Analytics */}
          {activeTab === "analytics" && analytics && (
            <div className="mt-6 space-y-6" data-testid="analytics-section">
              <div className="grid sm:grid-cols-3 gap-4">
                <StatCard label={`Events · ${analytics.days}d`} value={analytics.total_events} icon={BarChart3} testid="stat-events-total" />
                <StatCard label="Unique sessions" value={analytics.unique_sessions} icon={Users} testid="stat-unique-sessions" />
                <StatCard label="Waitlist total" value={analytics.waitlist_total} icon={Mail} testid="stat-waitlist-total" />
              </div>
              <div className="bg-white border border-ink-200 rounded-2xl p-4 sm:p-6">
                <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Events by type</div>
                <div className="mt-4 h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={analytics.by_event}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                      <XAxis dataKey="event" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#4F46E5" radius={[6,6,0,0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
              <div className="bg-white border border-ink-200 rounded-2xl p-4 sm:p-6">
                <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Daily activity</div>
                <div className="mt-4 h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={groupByDay(analytics.by_day)}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                      <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Line type="monotone" dataKey="count" stroke="#4F46E5" strokeWidth={2} dot={{ r: 3 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
              <div className="bg-white border border-ink-200 rounded-2xl overflow-hidden" data-testid="conversion-source-table">
                <div className="p-4 sm:p-6 border-b border-ink-100">
                  <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Conversion by traffic source</div>
                  <div className="mt-1 text-sm text-ink-500">Sessions → waitlist signups, split by where visitors came from.</div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm min-w-[560px]">
                    <thead className="bg-ink-50 text-ink-500 text-xs uppercase tracking-widest">
                      <tr>
                        <th className="text-left px-4 py-3 font-semibold">Source</th>
                        <th className="text-right px-4 py-3 font-semibold">Sessions</th>
                        <th className="text-right px-4 py-3 font-semibold">Demo views</th>
                        <th className="text-right px-4 py-3 font-semibold">Signups</th>
                        <th className="text-right px-4 py-3 font-semibold">Conv.</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(analytics.conversion_by_source || []).map((r) => (
                        <tr key={r.source} className="border-t border-ink-100" data-testid={`conv-row-${r.source}`}>
                          <td className="px-4 py-3">
                            <span className="text-xs font-semibold rounded-full px-2 py-1 bg-brand-50 text-brand-700 capitalize">{r.source}</span>
                          </td>
                          <td className="px-4 py-3 text-right font-mono">{r.sessions}</td>
                          <td className="px-4 py-3 text-right font-mono">{r.demo_views}</td>
                          <td className="px-4 py-3 text-right font-mono">{r.signups}</td>
                          <td className="px-4 py-3 text-right font-mono font-semibold text-brand-700">{r.conversion_pct}%</td>
                        </tr>
                      ))}
                      {(!analytics.conversion_by_source || analytics.conversion_by_source.length === 0) && (
                        <tr><td colSpan={5} className="px-4 py-8 text-center text-ink-400">No traffic yet.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* A/B Experiments */}
          {activeTab === "experiments" && experiments && (
            <div className="mt-6 space-y-6" data-testid="experiments-section">
              <div className="bg-white border border-ink-200 rounded-2xl p-6">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div>
                    <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Experiment</div>
                    <div className="font-heading font-bold text-xl mt-1">landing_hero — headline &amp; CTA</div>
                    <div className="text-sm text-ink-500 mt-1">Each visitor is deterministically assigned once. Winner is the variant with the highest waitlist conversion.</div>
                  </div>
                  {experiments.winner && (
                    <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 text-emerald-700 px-3 py-1.5 text-sm font-semibold border border-emerald-200" data-testid="experiment-winner">
                      <Trophy className="w-4 h-4" /> Winner: Variant {experiments.winner}
                    </div>
                  )}
                </div>
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                {experiments.rows.map((r) => (
                  <div key={r.variant} data-testid={`experiment-variant-${r.variant}`}
                    className={`bg-white border-2 rounded-2xl p-6 ${experiments.winner === r.variant ? "border-emerald-500 shadow-lg" : "border-ink-200"}`}>
                    <div className="flex items-center justify-between">
                      <div className="font-heading font-extrabold text-2xl tracking-tight">Variant {r.variant}</div>
                      <div className="text-sm font-mono text-ink-500">{r.sessions} sessions</div>
                    </div>
                    <div className="mt-4 space-y-2 text-sm">
                      <div className="text-ink-500 text-xs uppercase tracking-widest">Headline</div>
                      <div className="font-heading font-bold text-lg">
                        {r.content.headline_pre} <span className="text-brand-600">{r.content.headline_highlight}</span> {r.content.headline_mid} {r.content.headline_after}.
                      </div>
                      <div className="text-ink-500 text-xs uppercase tracking-widest pt-2">Primary CTA</div>
                      <div className="inline-block bg-brand-600 text-white text-sm font-semibold rounded-full px-3 py-1">{r.content.cta_primary}</div>
                    </div>
                    <div className="mt-5 grid grid-cols-3 gap-2">
                      <div className="rounded-lg bg-ink-50 p-3">
                        <div className="text-[10px] uppercase tracking-widest text-ink-500 font-semibold">CTA clicks</div>
                        <div className="mt-1 font-heading font-extrabold text-xl">{r.cta_clicks}</div>
                        <div className="text-[11px] text-ink-500">{r.cta_ctr_pct}% CTR</div>
                      </div>
                      <div className="rounded-lg bg-ink-50 p-3">
                        <div className="text-[10px] uppercase tracking-widest text-ink-500 font-semibold">Signups</div>
                        <div className="mt-1 font-heading font-extrabold text-xl">{r.signups}</div>
                      </div>
                      <div className="rounded-lg bg-brand-50 border border-brand-100 p-3">
                        <div className="text-[10px] uppercase tracking-widest text-brand-700 font-semibold">Conv.</div>
                        <div className="mt-1 font-heading font-extrabold text-xl text-brand-800">{r.conversion_pct}%</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="text-xs text-ink-500 bg-ink-50 border border-ink-200 rounded-xl p-4">
                Statistical note: results below ~200 sessions per variant are directional only.
                Wait until each variant has enough traffic before declaring a definitive winner.
              </div>

              {/* Signup Attribution Matrix */}
              {attribution && (
                <div className="bg-white border border-ink-200 rounded-2xl overflow-hidden" data-testid="attribution-matrix">
                  <div className="p-5 border-b border-ink-100 flex items-start justify-between gap-3 flex-wrap">
                    <div>
                      <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Signup Attribution</div>
                      <div className="font-heading font-bold text-xl mt-1">Source × Variant matrix</div>
                      <div className="text-sm text-ink-500 mt-1">
                        Cells show <span className="font-mono">signups</span> and conversion % (signups ÷ sessions).
                        Use this to see which channel + message combo converts best.
                      </div>
                    </div>
                    <Button variant="outline" size="sm" className="rounded-full text-ink-900 shrink-0"
                      data-testid="matrix-export-csv-btn"
                      onClick={() => {
                        const url = new URL(`${process.env.REACT_APP_BACKEND_URL}/api/admin/attribution-matrix.csv`);
                        const a = document.createElement("a");
                        a.href = url.toString();
                        a.download = "";
                        document.body.appendChild(a); a.click(); a.remove();
                        toast.success("Matrix CSV downloading");
                      }}>
                      <Download className="w-4 h-4 mr-2" /> Export CSV
                    </Button>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm min-w-[640px]">
                      <thead className="bg-ink-50 text-ink-500 text-xs uppercase tracking-widest">
                        <tr>
                          <th className="text-left px-4 py-3 font-semibold">Source ↓ / Variant →</th>
                          {attribution.variants.map((v) => (
                            <th key={v} className="text-right px-4 py-3 font-semibold" data-testid={`matrix-col-${v}`}>
                              {v}
                            </th>
                          ))}
                          <th className="text-right px-4 py-3 font-semibold bg-brand-50 text-brand-700">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {attribution.rows.map((r) => (
                          <tr key={r.source} className="border-t border-ink-100 hover:bg-ink-50/50" data-testid={`matrix-row-${r.source}`}>
                            <td className="px-4 py-3">
                              <span className="text-xs font-semibold rounded-full px-2 py-1 bg-ink-100 text-ink-700 capitalize">{r.source}</span>
                            </td>
                            {r.cells.map((c) => {
                              const overflow = c.signups > c.sessions && c.sessions > 0;
                              const tt = c.sessions
                                ? (overflow
                                    ? `${c.signups} signups from ${c.sessions} sessions — conversion >100% means some visitors signed up before analytics loaded (e.g. direct POST to /api/waitlist) or arrived from a channel we didn't tag.`
                                    : `${c.signups} signups from ${c.sessions} sessions · ${c.conversion_pct}% conversion`)
                                : (c.signups > 0
                                    ? `${c.signups} signups but no page_view sessions captured — visitor arrived before analytics started tracking.`
                                    : "No sessions, no signups.");
                              return (
                                <td key={c.variant} className="px-4 py-3 text-right" data-testid={`matrix-cell-${r.source}-${c.variant}`} title={tt}>
                                  <div className="font-heading font-bold text-base">{c.signups}</div>
                                  <div className={`text-[11px] font-mono cursor-help ${
                                    overflow ? "text-amber-700 font-semibold" :
                                    c.conversion_pct >= 20 ? "text-emerald-700 font-semibold" : "text-ink-400"
                                  }`}>
                                    {c.sessions ? `${c.conversion_pct}%` : "—"}
                                    {overflow && <span className="ml-1" aria-hidden="true">⚠</span>}
                                  </div>
                                </td>
                              );
                            })}
                            <td className="px-4 py-3 text-right bg-brand-50/40">
                              <div className="font-heading font-bold text-base text-brand-800">{r.totals.signups}</div>
                              <div className="text-[11px] text-brand-700 font-mono">{r.totals.sessions ? `${r.totals.conversion_pct}%` : "—"}</div>
                            </td>
                          </tr>
                        ))}
                        <tr className="border-t border-ink-200 bg-brand-50/40 font-semibold">
                          <td className="px-4 py-3 text-brand-800">Total</td>
                          {attribution.col_totals.map((c) => (
                            <td key={c.variant} className="px-4 py-3 text-right" data-testid={`matrix-coltotal-${c.variant}`}>
                              <div className="font-heading font-bold text-brand-800">{c.signups}</div>
                              <div className="text-[11px] font-mono text-brand-700">{c.sessions ? `${c.conversion_pct}%` : "—"}</div>
                            </td>
                          ))}
                          <td className="px-4 py-3 text-right" data-testid="matrix-grand">
                            <div className="font-heading font-bold text-brand-900">{attribution.grand.signups}</div>
                            <div className="text-[11px] font-mono text-brand-700">{attribution.grand.sessions ? `${attribution.grand.conversion_pct}%` : "—"}</div>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div className="p-4 border-t border-ink-100 text-xs text-ink-500 space-y-1">
                    <div><span className="font-semibold text-ink-700">Reading this table:</span> each cell shows <span className="font-mono">signups</span> on top and <span className="font-mono">conversion %</span> below (signups ÷ sessions). Hover any % for a plain-English breakdown.</div>
                    <div><span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1.5 align-middle" /> Green ≥ 20% conversion — a strong performing combo, worth doubling down.</div>
                    <div><span className="inline-block w-2 h-2 rounded-full bg-amber-500 mr-1.5 align-middle" /> Amber (with ⚠) means signups exceeded tracked sessions — usually a visitor who signed up before analytics loaded, or via a channel we didn&apos;t tag. Signup counts remain accurate; conversion % is directional.</div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* UTM Links */}
          {activeTab === "utm" && <UtmLinksTab />}

          {/* Daily Digest */}
          {activeTab === "digest" && digestConfig && digestPreview && (
            <div className="mt-6 space-y-6" data-testid="digest-section">
              {!digestConfig.email_enabled && (
                <div className="rounded-2xl border-2 border-amber-300 bg-amber-50 p-5 flex items-start gap-3" data-testid="digest-email-disabled">
                  <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                  <div className="text-sm">
                    <div className="font-heading font-bold text-amber-900">Email delivery is off.</div>
                    <div className="text-amber-800 mt-1">
                      Digests are being generated and stored, but no email is sent yet.
                      Set <code className="bg-amber-100 px-1.5 py-0.5 rounded font-mono text-xs">RESEND_API_KEY</code> in <code className="bg-amber-100 px-1.5 py-0.5 rounded font-mono text-xs">/app/backend/.env</code> to turn on delivery to
                      <strong> {digestConfig.recipients.join(", ")}</strong>.
                    </div>
                  </div>
                </div>
              )}

              <div className="bg-white border border-ink-200 rounded-2xl p-6">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div>
                    <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Schedule</div>
                    <div className="font-heading font-bold text-lg mt-1">{digestConfig.schedule}</div>
                    <div className="text-sm text-ink-500 mt-1">Recipients: {digestConfig.recipients.join(", ") || "—"}</div>
                  </div>
                  <div className="flex gap-2">
                    <a href={`${process.env.REACT_APP_BACKEND_URL}/api/admin/digest/preview.html`} target="_blank" rel="noreferrer">
                      <Button variant="outline" data-testid="preview-html-btn">Preview email</Button>
                    </a>
                    <Button onClick={sendDigestNow} disabled={sendingDigest}
                      className="bg-brand-600 hover:bg-brand-700 text-white" data-testid="send-digest-btn">
                      {sendingDigest ? "Sending…" : (digestConfig.email_enabled ? "Send now" : "Generate now")}
                    </Button>
                  </div>
                </div>
              </div>

              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard label="Visitors · 7d" value={`${digestPreview.visitors}`} icon={Users} testid="digest-visitors" />
                <StatCard label="Signups · 7d" value={`${digestPreview.signups}`} icon={Mail} testid="digest-signups" />
                <StatCard label="Conversion" value={`${digestPreview.conversion_pct}%`} icon={TrendingUp} testid="digest-conversion" />
                <StatCard label="Demo requests" value={`${digestPreview.demo_requests.book_demo_submitted}`} icon={FlaskConical} testid="digest-demos" />
              </div>

              <div className="grid md:grid-cols-3 gap-4">
                <div className="bg-white border border-ink-200 rounded-2xl p-4">
                  <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">WoW growth</div>
                  <div className="mt-3 space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-ink-500">Visitors</span><span className="font-mono font-semibold">{digestPreview.visitors_wow}</span></div>
                    <div className="flex justify-between"><span className="text-ink-500">Signups</span><span className="font-mono font-semibold">{digestPreview.signups_wow}</span></div>
                    <div className="flex justify-between"><span className="text-ink-500">Conversion</span><span className="font-mono font-semibold">{digestPreview.conversion_wow}</span></div>
                  </div>
                </div>
                <div className="bg-white border border-ink-200 rounded-2xl p-4">
                  <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Devices</div>
                  <div className="mt-3 space-y-2 text-sm">
                    {Object.entries(digestPreview.devices).filter(([, v]) => v).map(([k, v]) => (
                      <div key={k} className="flex justify-between"><span className="text-ink-500 capitalize">{k}</span><span className="font-mono font-semibold">{v}</span></div>
                    ))}
                  </div>
                </div>
                <div className="bg-white border border-ink-200 rounded-2xl p-4">
                  <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Top countries</div>
                  <div className="mt-3 space-y-2 text-sm">
                    {digestPreview.top_countries.length === 0 && <div className="text-ink-400 text-xs">No geo data yet</div>}
                    {digestPreview.top_countries.map((c) => (
                      <div key={c.country} className="flex justify-between"><span className="text-ink-500">{c.country}</span><span className="font-mono font-semibold">{c.n}</span></div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="bg-white border border-ink-200 rounded-2xl overflow-hidden">
                <div className="p-4 border-b border-ink-100 font-heading font-bold text-lg">Digest archive</div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm min-w-[560px]">
                    <thead className="bg-ink-50 text-ink-500 text-xs uppercase tracking-widest">
                      <tr>
                        <th className="text-left px-4 py-3 font-semibold">Generated</th>
                        <th className="text-right px-4 py-3 font-semibold">Visitors</th>
                        <th className="text-right px-4 py-3 font-semibold">Signups</th>
                        <th className="text-right px-4 py-3 font-semibold">Conv.</th>
                        <th className="text-left px-4 py-3 font-semibold">Delivery</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(digestList || []).map((d) => (
                        <tr key={d.id} className="border-t border-ink-100" data-testid={`digest-row-${d.id}`}>
                          <td className="px-4 py-3 text-ink-700">{new Date(d.generated_at).toLocaleString()}</td>
                          <td className="px-4 py-3 text-right font-mono">{d.visitors}</td>
                          <td className="px-4 py-3 text-right font-mono">{d.signups}</td>
                          <td className="px-4 py-3 text-right font-mono">{d.conversion_pct}%</td>
                          <td className="px-4 py-3">
                            {d.delivery?.sent
                              ? <span className="text-xs font-semibold bg-emerald-50 text-emerald-700 rounded-full px-2 py-1">sent</span>
                              : <span className="text-xs font-semibold bg-ink-100 text-ink-500 rounded-full px-2 py-1" title={d.delivery?.reason || ""}>not sent</span>}
                          </td>
                        </tr>
                      ))}
                      {(!digestList || digestList.length === 0) && (
                        <tr><td colSpan={5} className="px-4 py-8 text-center text-ink-400">
                          No digests generated yet. Click <b>Generate now</b> to create the first one.
                        </td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Untagged Sessions Drilldown Dialog */}
          <Dialog open={untaggedOpen} onOpenChange={setUntaggedOpen}>
            <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto" data-testid="untagged-drilldown">
              <DialogHeader>
                <DialogTitle className="font-heading text-2xl tracking-tighter">Untagged sessions — drilldown</DialogTitle>
                <DialogDescription>
                  Sessions with no <span className="font-mono">utm_source</span>. Use this to find dark traffic and add tracked UTM links to those channels.
                </DialogDescription>
              </DialogHeader>

              {untaggedBusy && (
                <div className="py-12 text-center text-ink-500">Loading untagged sessions…</div>
              )}

              {untagged && !untaggedBusy && (
                <div className="space-y-6">
                  <div className="text-sm text-ink-500">
                    Showing <span className="font-semibold text-ink-900">{untagged.returned}</span> of{" "}
                    <span className="font-semibold text-ink-900">{untagged.total}</span> untagged sessions, sorted by most recent.
                  </div>

                  {/* Rollups */}
                  <div className="grid md:grid-cols-2 gap-4">
                    <div className="rounded-xl border border-ink-200 p-4" data-testid="untagged-top-hosts">
                      <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold mb-3">Top referrer hosts</div>
                      {untagged.top_referrer_hosts.length === 0 && <div className="text-sm text-ink-400">No data.</div>}
                      <div className="space-y-1.5">
                        {untagged.top_referrer_hosts.map((h) => (
                          <div key={h.host} className="flex items-center justify-between text-sm">
                            <span className="font-mono text-ink-700 truncate mr-2">{h.host}</span>
                            <span className="rounded-full bg-brand-50 text-brand-700 font-semibold text-xs px-2 py-0.5">{h.n}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-xl border border-ink-200 p-4" data-testid="untagged-top-paths">
                      <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold mb-3">Top landing paths</div>
                      {untagged.top_landing_paths.length === 0 && <div className="text-sm text-ink-400">No data.</div>}
                      <div className="space-y-1.5">
                        {untagged.top_landing_paths.map((p) => (
                          <div key={p.path} className="flex items-center justify-between text-sm">
                            <span className="font-mono text-ink-700 truncate mr-2">{p.path || "(unknown)"}</span>
                            <span className="rounded-full bg-brand-50 text-brand-700 font-semibold text-xs px-2 py-0.5">{p.n}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Recommended fix banner */}
                  {untagged.top_referrer_hosts.length > 0 && (
                    <div className="rounded-xl bg-brand-50 border border-brand-100 p-4 text-sm">
                      <div className="font-semibold text-brand-800">Recommended:</div>
                      <div className="text-brand-700 mt-1">
                        Next time you share from <span className="font-mono">{untagged.top_referrer_hosts[0].host}</span>, use a{" "}
                        <button onClick={() => { setUntaggedOpen(false); setParams({ tab: "utm" }); }}
                                className="text-brand-700 underline font-semibold">tracked UTM link</button>{" "}
                        instead of a raw URL — that alone will attribute {untagged.top_referrer_hosts[0].n} of these sessions.
                      </div>
                    </div>
                  )}

                  {/* Session table */}
                  <div className="rounded-xl border border-ink-200 overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs min-w-[720px]" data-testid="untagged-session-table">
                        <thead className="bg-ink-50 text-ink-500 uppercase tracking-widest">
                          <tr>
                            <th className="text-left px-3 py-2 font-semibold">Session</th>
                            <th className="text-left px-3 py-2 font-semibold">Referrer host</th>
                            <th className="text-left px-3 py-2 font-semibold">Landing path</th>
                            <th className="text-right px-3 py-2 font-semibold">Page views</th>
                            <th className="text-left px-3 py-2 font-semibold">Last seen</th>
                          </tr>
                        </thead>
                        <tbody>
                          {untagged.sessions.map((s) => (
                            <tr key={s.session_id} className="border-t border-ink-100 hover:bg-ink-50/50"
                                data-testid={`untagged-row-${s.session_id}`}>
                              <td className="px-3 py-2 font-mono text-ink-500 truncate max-w-[140px]" title={s.session_id}>{s.session_id.slice(0,14)}…</td>
                              <td className="px-3 py-2 font-mono text-ink-700 truncate max-w-[220px]" title={s.referrer}>{s.referrer_host}</td>
                              <td className="px-3 py-2 font-mono text-ink-700 truncate max-w-[180px]" title={s.landing_path}>{s.landing_path || "(unknown)"}</td>
                              <td className="px-3 py-2 text-right font-semibold">{s.page_views}</td>
                              <td className="px-3 py-2 text-ink-500 whitespace-nowrap">{s.last_seen ? new Date(s.last_seen).toLocaleString() : "—"}</td>
                            </tr>
                          ))}
                          {untagged.sessions.length === 0 && (
                            <tr><td colSpan={5} className="px-3 py-10 text-center text-ink-400">No untagged sessions 🎉</td></tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
            </DialogContent>
          </Dialog>
        </main>
      </div>
    </div>
  );
}

function groupByDay(rows) {
  const map = {};
  rows.forEach(r => { map[r.day] = (map[r.day] || 0) + r.count; });
  return Object.keys(map).sort().map(d => ({ day: d.slice(5), count: map[d] }));
}
