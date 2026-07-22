import { Link, NavLink, useNavigate } from "react-router-dom";
import { Video, LayoutDashboard, Settings, Shield, LogOut, Sparkles, Coins } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { login } from "@/pages/AuthCallback";

export function TopBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <header className="glass-nav sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 group" data-testid="brand-link">
          <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center shadow-sm group-hover:rotate-6 transition-transform">
            <Video className="w-5 h-5 text-white" />
          </div>
          <div className="font-heading font-extrabold text-lg tracking-tight">AI Video<span className="text-brand-600">Studio</span></div>
        </Link>
        <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-ink-700">
          <Link to="/pricing" className="hover:text-brand-600 transition-colors" data-testid="nav-pricing">Pricing</Link>
          {user && <Link to="/dashboard" className="hover:text-brand-600 transition-colors" data-testid="nav-dashboard">Dashboard</Link>}
          {user?.role === "admin" && <Link to="/admin" className="hover:text-brand-600 transition-colors" data-testid="nav-admin">Admin</Link>}
        </nav>
        <div className="flex items-center gap-3">
          {user ? (
            <>
              <div className="hidden sm:flex items-center gap-1.5 text-xs bg-brand-50 text-brand-700 px-2.5 py-1 rounded-full font-semibold" data-testid="credits-badge">
                <Coins className="w-3.5 h-3.5" /> {user.credits} credits
              </div>
              <Link to="/settings" className="text-ink-500 hover:text-ink-900" data-testid="nav-settings"><Settings className="w-5 h-5" /></Link>
              <button onClick={logout} className="text-ink-500 hover:text-ink-900" data-testid="logout-btn"><LogOut className="w-5 h-5" /></button>
            </>
          ) : (
            <Button onClick={login} className="rounded-full bg-brand-600 hover:bg-brand-700 text-white px-5" data-testid="signin-btn">
              <Sparkles className="w-4 h-4 mr-2" /> Sign in
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}

export function Sidebar() {
  const { user } = useAuth();
  const items = [
    { to: "/dashboard", label: "Projects", icon: LayoutDashboard, testId: "side-projects" },
    { to: "/new", label: "New Video", icon: Sparkles, testId: "side-new" },
    { to: "/settings", label: "Settings", icon: Settings, testId: "side-settings" },
  ];
  if (user?.role === "admin") items.push({ to: "/admin", label: "Admin", icon: Shield, testId: "side-admin" });
  return (
    <aside className="w-[240px] shrink-0 border-r border-ink-200 bg-white/60 backdrop-blur-sm min-h-[calc(100vh-64px)] p-4">
      <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold mb-3 px-2">Workspace</div>
      <nav className="flex flex-col gap-1">
        {items.map((it) => (
          <NavLink key={it.to} to={it.to} data-testid={it.testId}
            className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
              isActive ? "bg-brand-600 text-white" : "text-ink-700 hover:bg-ink-100"
            }`}>
            <it.icon className="w-4 h-4" /> {it.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
