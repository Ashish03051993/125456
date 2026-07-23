import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Gift, Copy, Check, Users, Coins, Share2, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function ReferralPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let alive = true;
    api.get("/referrals/me").then(({ data }) => { if (alive) setData(data); })
      .catch(() => { if (alive) setData({ error: true }); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  const copy = async (text, label = "Copied") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success(label);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      toast.error("Copy failed — long-press to copy manually");
    }
  };

  const share = async () => {
    if (!data?.share_url) return;
    const shareData = {
      title: "Make videos with AI",
      text: "I've been making videos with AI Video Studio — you get 3 bonus credits with my link:",
      url: data.share_url,
    };
    if (navigator.share) {
      try { await navigator.share(shareData); } catch { /* user cancelled */ }
    } else {
      copy(data.share_url, "Link copied — paste to share");
    }
  };

  if (loading) {
    return (
      <div className="bg-white border border-ink-200 rounded-2xl p-6 flex items-center gap-3 text-ink-500" data-testid="referral-panel-loading">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading your invite code…
      </div>
    );
  }

  if (!data || data.error) {
    return (
      <div className="bg-white border border-ink-200 rounded-2xl p-6 text-sm text-ink-500" data-testid="referral-panel-error">
        Couldn&apos;t load referral info. Refresh to try again.
      </div>
    );
  }

  return (
    <div className="md:col-span-2 bg-gradient-to-br from-brand-50 via-white to-white border border-brand-100 rounded-2xl p-6 relative overflow-hidden"
         data-testid="referral-panel">
      <div className="absolute -top-8 -right-8 w-40 h-40 bg-brand-100 rounded-full opacity-40 blur-2xl pointer-events-none" />
      <div className="relative">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold flex items-center gap-1.5">
              <Gift className="w-3.5 h-3.5" /> Invite friends
            </div>
            <h2 className="mt-1 font-heading text-2xl font-black tracking-tight text-ink-900">
              Give <span className="text-brand-600">{data.bonus_per_referral}</span>, get <span className="text-brand-600">{data.bonus_per_referral}</span>
            </h2>
            <p className="text-sm text-ink-500 mt-1">
              Share your link — every friend who signs up gets {data.bonus_per_referral} bonus credits, and you get {data.bonus_per_referral} too.
            </p>
          </div>
          <div className="flex items-center gap-4 shrink-0">
            <div className="text-center">
              <div className="text-2xl font-heading font-black text-ink-900" data-testid="referral-invited-count">{data.invited_count}</div>
              <div className="text-[10px] uppercase tracking-widest text-ink-500 font-semibold flex items-center gap-1"><Users className="w-3 h-3" /> Invited</div>
            </div>
            <div className="w-px h-8 bg-ink-200" />
            <div className="text-center">
              <div className="text-2xl font-heading font-black text-brand-600" data-testid="referral-credits-earned">{data.credits_earned}</div>
              <div className="text-[10px] uppercase tracking-widest text-ink-500 font-semibold flex items-center gap-1"><Coins className="w-3 h-3" /> Earned</div>
            </div>
          </div>
        </div>

        <div className="mt-5 grid sm:grid-cols-[auto,1fr,auto] gap-2 items-center">
          <div className="rounded-xl bg-white border-2 border-brand-200 px-4 py-2.5 font-mono font-bold text-lg tracking-widest text-brand-700 text-center"
               data-testid="referral-code">
            {data.code}
          </div>
          <Input readOnly value={data.share_url}
                 className="font-mono text-xs bg-white"
                 data-testid="referral-share-url"
                 onFocus={(e) => e.target.select()} />
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => copy(data.share_url, "Link copied to clipboard")}
                    className="rounded-full h-10" data-testid="referral-copy-btn">
              {copied ? <><Check className="w-4 h-4 mr-1.5" /> Copied</> : <><Copy className="w-4 h-4 mr-1.5" /> Copy</>}
            </Button>
            <Button size="sm" onClick={share}
                    className="rounded-full h-10 bg-brand-600 hover:bg-brand-700 text-white"
                    data-testid="referral-share-btn">
              <Share2 className="w-4 h-4 mr-1.5" /> Share
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
