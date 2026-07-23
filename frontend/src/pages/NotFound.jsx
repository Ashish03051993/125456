import { Link } from "react-router-dom";
import { Video, Home, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

export default function NotFound() {
  const { user } = useAuth();
  return (
    <div className="min-h-screen bg-ink-50 flex flex-col items-center justify-center px-4" data-testid="not-found-page">
      <div className="max-w-md w-full text-center">
        <div className="inline-flex items-center gap-2 mb-6">
          <div className="w-11 h-11 rounded-lg bg-brand-600 flex items-center justify-center shadow-sm">
            <Video className="w-6 h-6 text-white" />
          </div>
          <div className="font-heading font-extrabold text-xl tracking-tight">AI Video<span className="text-brand-600">Studio</span></div>
        </div>

        <div className="font-heading font-black tracking-tighter text-brand-600 text-[92px] leading-none" data-testid="not-found-code">404</div>
        <h1 className="mt-3 font-heading text-2xl sm:text-3xl font-black tracking-tighter text-ink-900" data-testid="not-found-title">This page slipped out of frame</h1>
        <p className="mt-3 text-ink-500 text-sm">The URL you followed doesn&apos;t exist — the video may have been unshared, or the link is a typo. Head back home and pick up where you left off.</p>

        <div className="mt-8 flex flex-wrap gap-2 justify-center">
          <Link to={user ? "/dashboard" : "/"}>
            <Button className="rounded-full bg-brand-600 hover:bg-brand-700 text-white h-11 px-6 font-semibold" data-testid="not-found-home-btn">
              <Home className="w-4 h-4 mr-2" /> {user ? "Go to dashboard" : "Back to home"}
            </Button>
          </Link>
          {!user && (
            <Link to="/signup">
              <Button variant="outline" className="rounded-full h-11 px-6 font-semibold" data-testid="not-found-signup-btn">
                <Sparkles className="w-4 h-4 mr-2" /> Start free
              </Button>
            </Link>
          )}
        </div>
        <div className="mt-6 flex justify-center gap-4 text-xs text-ink-500">
          <Link to="/pricing" className="hover:text-brand-600">Pricing</Link>
          <Link to="/terms" className="hover:text-brand-600">Terms</Link>
          <Link to="/privacy" className="hover:text-brand-600">Privacy</Link>
        </div>
      </div>
    </div>
  );
}
