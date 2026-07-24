import { TopBar, Sidebar } from "@/components/Layout";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Coins, User as UserIcon } from "lucide-react";
import { Link } from "react-router-dom";
import ReferralPanel from "@/components/ReferralPanel";
import ChangePasswordCard from "@/components/ChangePasswordCard";
import usePageTitle from "@/lib/usePageTitle";

export default function Settings() {
  usePageTitle("Settings");
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-ink-50">
      <TopBar />
      <div className="max-w-7xl mx-auto flex">
        <Sidebar />
        <main className="flex-1 p-8" data-testid="settings-main">
          <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Account</div>
          <h1 className="mt-1 font-heading text-4xl font-extrabold tracking-tighter">Settings</h1>

          <div className="mt-8 grid md:grid-cols-2 gap-4">
            <div className="bg-white border border-ink-200 rounded-2xl p-6">
              <div className="flex items-center gap-3">
                {user?.picture ? <img src={user.picture} alt="" className="w-14 h-14 rounded-full" /> :
                  <div className="w-14 h-14 rounded-full bg-brand-100 flex items-center justify-center"><UserIcon className="w-6 h-6 text-brand-600" /></div>}
                <div>
                  <div className="font-heading font-bold text-lg">{user?.name}</div>
                  <div className="text-sm text-ink-500">{user?.email}</div>
                </div>
              </div>
              <div className="mt-6 text-xs uppercase tracking-widest text-ink-500 font-semibold">Role</div>
              <div className="mt-1 capitalize font-semibold">{user?.role}</div>
              <Button variant="outline" onClick={logout} className="mt-6 rounded-full" data-testid="settings-logout">Sign out</Button>
            </div>

            <div className="bg-white border border-ink-200 rounded-2xl p-6">
              <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">Billing</div>
              <div className="mt-2 flex items-baseline gap-2">
                <div className="font-heading text-4xl font-extrabold tracking-tighter capitalize">{user?.plan}</div>
                <div className="text-sm text-ink-500">plan</div>
              </div>
              <div className="mt-6 flex items-center gap-2 text-brand-700 font-semibold">
                <Coins className="w-4 h-4" /> {user?.credits} credits remaining
              </div>
              <Link to="/pricing"><Button className="mt-6 rounded-full bg-brand-600 hover:bg-brand-700 text-white" data-testid="upgrade-btn">Upgrade plan</Button></Link>
            </div>

            <ChangePasswordCard />
            <ReferralPanel />
          </div>
        </main>
      </div>
    </div>
  );
}
