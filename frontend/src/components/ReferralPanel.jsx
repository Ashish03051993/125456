import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Gift, Copy, Check, Users, Coins, Share2, Loader2, Twitter, Linkedin, MessageCircle, Trophy } from "lucide-react";
import { toast } from "sonner";

// Milestone tiers — purely UX gamification on top of the existing per-invite
// credit reward. Reaching a tier unlocks a badge; every invite still pays
// out +bonus credits via the backend regardless of tier.
const TIERS = [
  { at: 1,  name: "First Invite",  medal: "🎉", color: "text-ink-600" },
  { at: 3,  name: "Ambassador",    medal: "🥉", color: "text-amber-700" },
  { at: 10, name: "Advocate",      medal: "🥈", color: "text-slate-500" },
  { at: 25, name: "Champion",      medal: "🥇", color: "text-yellow-600" },
];

function ReferralMilestones({ invitedCount, bonus }) {
  const max = TIERS[TIERS.length - 1].at;
  const clamped = Math.min(invitedCount, max);
  const pct = Math.round((clamped / max) * 100);
  const nextTier = TIERS.find((t) => t.at > invitedCount);
  const earnedTiers = TIERS.filter((t) => invitedCount >= t.at);
  const topTier = earnedTiers[earnedTiers.length - 1];

  return (
    <div className="mt-5 pt-4 border-t border-brand-100/70" data-testid="referral-milestones">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Trophy className="w-4 h-4 text-brand-600" />
          <span className="text-[10px] uppercase tracking-widest text-ink-500 font-semibold">
            Milestones
          </span>
          {topTier && (
            <span
              className={`ml-1 inline-flex items-center gap-1 rounded-full bg-white border border-ink-200 px-2 py-0.5 text-[11px] font-semibold ${topTier.color}`}
              data-testid="referral-current-tier"
            >
              <span>{topTier.medal}</span> {topTier.name}
            </span>
          )}
        </div>
        <div className="text-xs text-ink-500">
          {nextTier ? (
            <>
              <span className="font-semibold text-ink-700">
                {nextTier.at - invitedCount}
              </span>{" "}
              more to unlock{" "}
              <span className="font-semibold">
                {nextTier.medal} {nextTier.name}
              </span>{" "}
              <span className="text-ink-400">
                (+{(nextTier.at - invitedCount) * bonus} credits along the way)
              </span>
            </>
          ) : (
            <span className="font-semibold text-brand-600">
              Legend unlocked — top-tier referrer 
            </span>
          )}
        </div>
      </div>

      <div className="mt-3 relative h-2 rounded-full bg-white border border-ink-100 overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 bg-gradient-to-r from-brand-500 to-brand-700 transition-all duration-500"
          style={{ width: `${pct}%` }}
          data-testid="referral-progress-bar"
        />
      </div>

      <div className="mt-2 flex items-center justify-between">
        {TIERS.map((t) => {
          const done = invitedCount >= t.at;
          return (
            <div
              key={t.at}
              className={`flex flex-col items-center text-center ${done ? "opacity-100" : "opacity-45"}`}
              data-testid={`referral-tier-${t.at}`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs border ${
                  done ? "bg-brand-600 border-brand-600 text-white" : "bg-white border-ink-200 text-ink-400"
                }`}
              >
                {done ? <Check className="w-3.5 h-3.5" /> : t.at}
              </div>
              <div className="text-[10px] font-semibold text-ink-600 mt-1">
                {t.medal} {t.name}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

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
      text: "I've been making videos with ContentOS AI — you get 3 bonus credits with my link:",
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

        <ReferralMilestones invitedCount={data.invited_count} bonus={data.bonus_per_referral} />

        {/* One-click social shares — pre-written copy tuned per platform */}
        {data.share_url && (() => {
          const url = encodeURIComponent(data.share_url);
          const tweet = encodeURIComponent(
            `I've been making videos with ContentOS AI — you get 3 bonus credits with my link:`
          );
          const linkedin = encodeURIComponent(
            `I've been making videos with ContentOS AI — turn any topic into a polished 30s–10min video (16:9 for YouTube + 9:16 for LinkedIn/Reels) in minutes. Grab 3 bonus credits with my invite link:`
          );
          const whatsapp = encodeURIComponent(
            `Hey! I've been using ContentOS AI to turn ideas into polished videos — you'll get 3 bonus credits if you sign up with my link 👉 ${data.share_url}`
          );
          const socials = [
            { id: "twitter",  label: "X / Twitter", Icon: Twitter,       href: `https://twitter.com/intent/tweet?text=${tweet}&url=${url}`,  bg: "hover:bg-ink-900 hover:text-white hover:border-ink-900" },
            { id: "linkedin", label: "LinkedIn",    Icon: Linkedin,      href: `https://www.linkedin.com/sharing/share-offsite/?url=${url}&summary=${linkedin}`, bg: "hover:bg-[#0A66C2] hover:text-white hover:border-[#0A66C2]" },
            { id: "whatsapp", label: "WhatsApp",    Icon: MessageCircle, href: `https://wa.me/?text=${whatsapp}`,                            bg: "hover:bg-[#25D366] hover:text-white hover:border-[#25D366]" },
          ];
          return (
            <div className="mt-4 pt-4 border-t border-brand-100/70">
              <div className="text-[10px] uppercase tracking-widest text-ink-500 font-semibold mb-2">Or share directly to</div>
              <div className="flex flex-wrap gap-2" data-testid="referral-social-share">
                {socials.map((s) => (
                  <a key={s.id} href={s.href} target="_blank" rel="noopener noreferrer"
                     onClick={() => toast.success(`Opening ${s.label}…`)}
                     className={`inline-flex items-center gap-1.5 rounded-full border border-ink-200 bg-white px-3 py-1.5 text-xs font-semibold text-ink-700 transition-colors ${s.bg}`}
                     data-testid={`referral-social-${s.id}`}>
                    <s.Icon className="w-3.5 h-3.5" /> {s.label}
                  </a>
                ))}
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
