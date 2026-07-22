import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { TopBar, Sidebar } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Users, Video, IndianRupee, TrendingUp, Coins } from "lucide-react";
import { toast } from "sonner";

export default function AdminPanel() {
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState(null);

  const load = async () => {
    try {
      const [u, s] = await Promise.all([api.get("/admin/users"), api.get("/admin/stats")]);
      setUsers(u.data);
      setStats(s.data);
    } catch (e) { toast.error("Failed to load admin data"); }
  };
  useEffect(() => { load(); }, []);

  const setCredits = async (u) => {
    const v = window.prompt(`Set credits for ${u.email}`, u.credits);
    if (v == null) return;
    const n = parseInt(v, 10);
    if (Number.isNaN(n)) return;
    await api.post(`/admin/users/${u.user_id}/credits`, null, { params: { credits: n } });
    toast.success("Credits updated");
    load();
  };

  const cards = stats && [
    { label: "Users", value: stats.total_users, icon: Users, color: "brand" },
    { label: "Projects", value: stats.total_projects, icon: Video, color: "cyan" },
    { label: "Videos ready", value: stats.videos_ready, icon: TrendingUp, color: "emerald" },
    { label: "MRR (₹)", value: stats.monthly_revenue_inr.toLocaleString("en-IN"), icon: IndianRupee, color: "violet" },
  ];

  return (
    <div className="min-h-screen bg-ink-50">
      <TopBar />
      <div className="max-w-7xl mx-auto flex">
        <Sidebar />
        <main className="flex-1 p-8" data-testid="admin-main">
          <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Admin</div>
          <h1 className="mt-1 font-heading text-4xl font-extrabold tracking-tighter">Control panel</h1>

          {cards && (
            <div className="mt-8 grid md:grid-cols-4 gap-4">
              {cards.map((c) => (
                <div key={c.label} className="bg-white border border-ink-200 rounded-2xl p-5" data-testid={`stat-${c.label.toLowerCase()}`}>
                  <div className="flex items-center justify-between">
                    <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">{c.label}</div>
                    <c.icon className="w-4 h-4 text-brand-600" />
                  </div>
                  <div className="mt-2 font-heading text-3xl font-extrabold tracking-tighter">{c.value}</div>
                </div>
              ))}
            </div>
          )}

          <div className="mt-10 bg-white border border-ink-200 rounded-2xl overflow-hidden">
            <div className="p-4 border-b border-ink-200 font-heading font-bold text-lg">Users</div>
            <table className="w-full text-sm">
              <thead className="bg-ink-50 text-ink-500 text-xs uppercase tracking-widest">
                <tr>
                  <th className="text-left px-4 py-3 font-semibold">User</th>
                  <th className="text-left px-4 py-3 font-semibold">Role</th>
                  <th className="text-left px-4 py-3 font-semibold">Plan</th>
                  <th className="text-left px-4 py-3 font-semibold">Credits</th>
                  <th className="text-right px-4 py-3 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.user_id} className="border-t border-ink-100 hover:bg-ink-50/50" data-testid={`user-row-${u.user_id}`}>
                    <td className="px-4 py-3">
                      <div className="font-semibold">{u.name || u.email}</div>
                      <div className="text-xs text-ink-500">{u.email}</div>
                    </td>
                    <td className="px-4 py-3"><span className={`text-xs font-semibold rounded-full px-2 py-1 ${u.role === "admin" ? "bg-violet-50 text-violet-700" : "bg-ink-100 text-ink-700"}`}>{u.role}</span></td>
                    <td className="px-4 py-3 capitalize">{u.plan}</td>
                    <td className="px-4 py-3"><div className="flex items-center gap-1 font-semibold text-brand-700"><Coins className="w-3.5 h-3.5" /> {u.credits}</div></td>
                    <td className="px-4 py-3 text-right">
                      <Button size="sm" variant="outline" onClick={() => setCredits(u)} data-testid={`edit-credits-${u.user_id}`}>Edit credits</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </main>
      </div>
    </div>
  );
}
