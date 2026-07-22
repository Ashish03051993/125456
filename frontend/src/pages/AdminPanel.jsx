import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { TopBar, Sidebar } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Users, Video, Mail, TrendingUp, BarChart3, Copy, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, LineChart, Line } from "recharts";

const TABS = [
  { id: "overview",  label: "Overview",  icon: BarChart3 },
  { id: "waitlist",  label: "Waitlist",  icon: Mail },
  { id: "analytics", label: "Analytics", icon: TrendingUp },
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

export default function AdminPanel() {
  const [params, setParams] = useSearchParams();
  const activeTab = params.get("tab") || "overview";
  const [stats, setStats] = useState(null);
  const [waitlist, setWaitlist] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [q, setQ] = useState("");

  const load = async () => {
    try {
      const [s, w, a] = await Promise.all([
        api.get("/admin/stats"),
        api.get("/admin/waitlist"),
        api.get("/admin/analytics"),
      ]);
      setStats(s.data);
      setWaitlist(w.data);
      setAnalytics(a.data);
    } catch { toast.error("Could not load admin data"); }
  };
  useEffect(() => { load(); }, []);

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
    if (!waitlist?.entries?.length) return;
    const header = ["position","email","name","plan_interest","use_case","referrer","created_at"];
    const rows = waitlist.entries.map(r => header.map(h => JSON.stringify(r[h] ?? "")).join(","));
    const csv = header.join(",") + "\n" + rows.join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "waitlist.csv"; a.click();
    URL.revokeObjectURL(url);
  };

  const copyEmails = () => {
    if (!waitlist?.entries?.length) return;
    const emails = waitlist.entries.map(r => r.email).join(", ");
    navigator.clipboard.writeText(emails);
    toast.success(`Copied ${waitlist.entries.length} emails`);
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
            </div>
          )}

          {/* Waitlist */}
          {activeTab === "waitlist" && waitlist && (
            <div className="mt-6" data-testid="waitlist-section">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="text-ink-500 text-sm">
                  <span className="font-heading font-bold text-ink-900 text-xl">{waitlist.count}</span> people on the waitlist
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" onClick={copyEmails} data-testid="copy-emails-btn"><Copy className="w-4 h-4 mr-2" /> Copy emails</Button>
                  <Button onClick={exportCsv} className="bg-brand-600 hover:bg-brand-700 text-white" data-testid="export-csv-btn">Export CSV</Button>
                </div>
              </div>
              <div className="mt-4 relative max-w-sm">
                <Search className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <Input placeholder="Search email, name or use case" value={q} onChange={(e)=>setQ(e.target.value)}
                  className="pl-9" data-testid="waitlist-search" />
              </div>
              <div className="mt-4 bg-white border border-ink-200 rounded-2xl overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm min-w-[720px]">
                    <thead className="bg-ink-50 text-ink-500 text-xs uppercase tracking-widest">
                      <tr>
                        <th className="text-left px-3 py-3 font-semibold">#</th>
                        <th className="text-left px-3 py-3 font-semibold">Email</th>
                        <th className="text-left px-3 py-3 font-semibold">Name</th>
                        <th className="text-left px-3 py-3 font-semibold">Plan</th>
                        <th className="text-left px-3 py-3 font-semibold">Use case</th>
                        <th className="text-left px-3 py-3 font-semibold">When</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredWaitlist.map((r) => (
                        <tr key={r.id} className="border-t border-ink-100 hover:bg-ink-50/50" data-testid={`waitlist-row-${r.id}`}>
                          <td className="px-3 py-2.5 font-mono text-ink-500">{r.position}</td>
                          <td className="px-3 py-2.5 font-semibold">{r.email}</td>
                          <td className="px-3 py-2.5">{r.name || "—"}</td>
                          <td className="px-3 py-2.5"><span className="text-xs font-semibold rounded-full px-2 py-1 bg-brand-50 text-brand-700 capitalize">{r.plan_interest}</span></td>
                          <td className="px-3 py-2.5 text-ink-500 max-w-[220px] truncate" title={r.use_case}>{r.use_case || "—"}</td>
                          <td className="px-3 py-2.5 text-ink-500 whitespace-nowrap">{new Date(r.created_at).toLocaleString()}</td>
                        </tr>
                      ))}
                      {filteredWaitlist.length === 0 && (
                        <tr><td colSpan={6} className="px-3 py-10 text-center text-ink-400">No entries match your search.</td></tr>
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
