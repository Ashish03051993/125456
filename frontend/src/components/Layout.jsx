import { Link, NavLink, useNavigate } from "react-router-dom";
import { Video, LayoutDashboard, Shield, LogOut, Sparkles, Users, BarChart3, FlaskConical, Send, Link as LinkIcon, LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { track } from "@/lib/analytics";
import { login } from "@/pages/AuthCallback";

export function TopBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <header className="glass-nav sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
        <Link to="/" className="flex items-center gap-2 group shrink-0" data-testid="brand-link">
          <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center shadow-sm group-hover:rotate-6 transition-transform">
            <Video className="w-5 h-5 text-white" />
          </div>
          <div className="font-heading font-extrabold text-lg tracking-tight">AI Video<span className="text-brand-600">Studio</span></div>
        </Link>
        <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-ink-700">
          <Link to="/pricing" className="hover:text-brand-600 transition-colors" data-testid="nav-pricing">Pricing</Link>
          {user?.role === "admin" && <Link to="/admin" className="hover:text-brand-600 transition-colors" data-testid="nav-admin">Admin</Link>}
        </nav>
        <div className="flex items-center gap-2 sm:gap-3">
          {user ? (
            <>
              {user.role === "admin" && (
                <div className="hidden sm:flex items-center gap-1.5 text-xs bg-violet-50 text-violet-700 px-2.5 py-1 rounded-full font-semibold">
                  <Shield className="w-3.5 h-3.5" /> admin
                </div>
              )}
              <button onClick={logout} className="text-ink-500 hover:text-ink-900" data-testid="logout-btn"><LogOut className="w-5 h-5" /></button>
            </>
          ) : (
            <>
              <button
                onClick={() => { track("signin_click", { source: "top_nav" }); login(); }}
                className="hidden sm:inline-flex items-center gap-1.5 text-sm font-semibold text-ink-700 hover:text-brand-600 transition-colors px-2"
                data-testid="nav-signin-btn">
                <LogIn className="w-4 h-4" /> Log in
              </button>
              <Button onClick={() => { track("signup_click", { source: "top_nav" }); login(); }}
                className="rounded-full bg-brand-600 hover:bg-brand-700 text-white px-4 sm:px-5 h-10"
                data-testid="nav-signup-btn">
                <Sparkles className="w-4 h-4 mr-1.5" /> Sign up free
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export function Sidebar() {
  const { user } = useAuth();
  if (user?.role !== "admin") return null;
  const items = [
    { to: "/admin", label: "Overview", icon: LayoutDashboard, testId: "side-overview" },
    { to: "/admin?tab=waitlist", label: "Waitlist", icon: Users, testId: "side-waitlist" },
    { to: "/admin?tab=analytics", label: "Analytics", icon: BarChart3, testId: "side-analytics" },
    { to: "/admin?tab=experiments", label: "A/B Tests", icon: FlaskConical, testId: "side-experiments" },
    { to: "/admin?tab=utm", label: "UTM Links", icon: LinkIcon, testId: "side-utm" },
    { to: "/admin?tab=digest", label: "Daily Digest", icon: Send, testId: "side-digest" },
  ];
  return (
    <aside className="hidden md:block w-[240px] shrink-0 border-r border-ink-200 bg-white/60 backdrop-blur-sm min-h-[calc(100vh-64px)] p-4">
      <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold mb-3 px-2">Admin</div>
      <nav className="flex flex-col gap-1">
        {items.map((it) => (
          <NavLink key={it.to} to={it.to} data-testid={it.testId} end
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
