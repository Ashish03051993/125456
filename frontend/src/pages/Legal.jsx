import { Link } from "react-router-dom";
import usePageTitle from "@/lib/usePageTitle";
import { Video, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

// Simple legal-page shell — swap in real content when your legal team is ready.
// Everything here is production-safe defaults for a SaaS video generation tool.
export function LegalShell({ title, updated, children }) {
  return (
    <div className="min-h-screen bg-ink-50" data-testid={`legal-${title.toLowerCase().replace(/\s+/g,'-')}`}>
      <header className="border-b border-ink-100 bg-white">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 group" data-testid="brand-link">
            <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center shadow-sm group-hover:rotate-6 transition-transform">
              <Video className="w-5 h-5 text-white" />
            </div>
            <div className="font-heading font-extrabold text-lg tracking-tight">AI Video<span className="text-brand-600">Studio</span></div>
          </Link>
          <Link to="/" className="text-sm text-ink-500 hover:text-ink-900 inline-flex items-center gap-1" data-testid="back-home">
            <ArrowLeft className="w-3.5 h-3.5" /> Back home
          </Link>
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-10 sm:py-14">
        <div className="text-xs uppercase tracking-widest text-brand-600 font-semibold">Legal</div>
        <h1 className="mt-2 font-heading text-3xl sm:text-4xl font-black tracking-tighter text-ink-900">{title}</h1>
        <p className="text-ink-500 text-sm mt-1">Last updated: {updated}</p>
        <div className="mt-8 space-y-6
                        [&_h2]:font-heading [&_h2]:font-black [&_h2]:tracking-tight [&_h2]:text-lg [&_h2]:sm:text-xl [&_h2]:text-ink-900 [&_h2]:mt-8 [&_h2]:mb-2 [&_h2]:pb-1 [&_h2]:border-b [&_h2]:border-ink-100
                        [&_p]:text-ink-700 [&_p]:leading-relaxed [&_p]:text-sm
                        [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1.5 [&_ul]:text-sm [&_li]:text-ink-700 [&_li]:leading-relaxed
                        [&_code]:bg-ink-100 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_code]:font-mono
                        [&_a]:text-brand-600 [&_a]:font-semibold hover:[&_a]:underline
                        [&_strong]:text-ink-900 [&_strong]:font-semibold">
          {children}
        </div>
        <div className="mt-12 border-t border-ink-100 pt-6 flex flex-wrap items-center justify-between gap-3 text-xs text-ink-500">
          <div>Questions? Reply to any invoice or transactional email — a human reads every one.</div>
          <div className="flex gap-4">
            <Link to="/terms" className="hover:text-brand-600" data-testid="footer-terms">Terms</Link>
            <Link to="/privacy" className="hover:text-brand-600" data-testid="footer-privacy">Privacy</Link>
            <Link to="/" className="hover:text-brand-600">Home</Link>
          </div>
        </div>
      </main>
    </div>
  );
}

export function Terms() {
  usePageTitle("Terms of Service");
  return (
    <LegalShell title="Terms of Service" updated="July 23, 2026">
      <h2>1. Who we are</h2>
      <p>ContentOS AI (the &ldquo;Service&rdquo;) is an AI-powered video generation platform that turns text prompts into polished short-form and long-form video content. By using the Service you agree to these Terms.</p>

      <h2>2. Your account</h2>
      <ul>
        <li>You must be at least 16 years old to use the Service.</li>
        <li>You are responsible for keeping your login credentials safe. Notify us immediately if you suspect unauthorised access.</li>
        <li>You must provide accurate account information. We may suspend accounts that impersonate others or falsify identity.</li>
      </ul>

      <h2>3. Free and paid usage</h2>
      <ul>
        <li>The Free plan grants 3 credits per calendar month, refilled automatically. Free credits do not accumulate month-over-month.</li>
        <li>Purchased credit packs (Starter, Creator, Pro, Agency) are one-time top-ups. Purchased credits do not expire.</li>
        <li>We reserve the right to change pricing with 30 days&apos; notice. Existing credit balances remain valid at their original terms.</li>
      </ul>

      <h2>4. What you can and cannot generate</h2>
      <p>You are responsible for the topics, prompts, character images and any user-uploaded assets. You may not use the Service to generate content that:</p>
      <ul>
        <li>Violates any applicable law in your jurisdiction or ours.</li>
        <li>Depicts real, identifiable individuals without their explicit consent (this includes uploading someone else&apos;s photo as a &ldquo;Talking Head&rdquo; character).</li>
        <li>Contains child sexual abuse material, incites violence, promotes self-harm, or constitutes targeted harassment.</li>
        <li>Infringes on any copyright, trademark, or other intellectual property right you do not own or have licence to use.</li>
        <li>Impersonates public figures, brands or officials for the purpose of misleading viewers.</li>
      </ul>
      <p>We use automated safety filters and reserve the right to refuse or remove generations that violate these rules. Serious or repeated violations may result in account termination without refund.</p>

      <h2>5. Your ownership of generated content</h2>
      <p>Subject to your compliance with these Terms and applicable law, you own the videos, audio, images and text that you generate using the Service and may use them for any purpose — personal or commercial. We claim no ownership over your creations. However:</p>
      <ul>
        <li>You grant us a limited, non-exclusive licence to store, process and deliver your content solely for the purpose of operating the Service.</li>
        <li>You grant us the right to display your <strong>publicly shared</strong> videos (those you explicitly enable a share link for) on any &ldquo;Made with ContentOS AI&rdquo; showcase surface. You can revoke the share link at any time to remove them.</li>
      </ul>

      <h2>6. AI limitations and no warranty</h2>
      <p>AI-generated content may contain errors, hallucinations or artifacts. You are solely responsible for reviewing every generation before publishing or distributing it. The Service is provided <strong>&ldquo;as is&rdquo;</strong> without warranty of any kind.</p>

      <h2>7. Refunds and cancellations</h2>
      <ul>
        <li>Unused credit packs are refundable within 14 days of purchase, provided fewer than 20% of the pack&apos;s credits have been used.</li>
        <li>Contact us via the address in your purchase receipt for refund requests.</li>
      </ul>

      <h2>8. Termination</h2>
      <p>You may delete your account at any time by contacting us. We may suspend or terminate accounts for material breach of these Terms; you will not be charged for unused credits at that point, and refunds are at our discretion.</p>

      <h2>9. Changes to these Terms</h2>
      <p>We may update these Terms from time to time. Material changes will be notified by email at least 14 days before they take effect.</p>

      <h2>10. Contact</h2>
      <p>For legal notices or dispute resolution, reply to any transactional email from our service — a human reads every one and will route to the right person within 3 business days.</p>
    </LegalShell>
  );
}

export function Privacy() {
  usePageTitle("Privacy Policy");
  return (
    <LegalShell title="Privacy Policy" updated="July 23, 2026">
      <h2>1. Data we collect</h2>
      <p>We collect only what we need to run the Service:</p>
      <ul>
        <li><strong>Account data</strong>: name, email or mobile number, hashed password (bcrypt), Google profile info if you sign in with Google.</li>
        <li><strong>Project data</strong>: topics you enter, generated scripts, images, audio and video files, and any character portraits you upload.</li>
        <li><strong>Usage analytics</strong>: pages viewed, feature clicks, and coarse device type. We use PostHog and internal analytics; we do not sell this data.</li>
        <li><strong>Share-link analytics</strong>: when someone views a public <code>/v/:slug</code> link, we record the referring website host (e.g. <code>twitter.com</code>) and device bucket (mobile / desktop / bot preview) — never the visitor&apos;s IP, precise location or fingerprint.</li>
      </ul>

      <h2>2. What we do NOT collect</h2>
      <ul>
        <li>We do not store viewer IP addresses for share-link analytics.</li>
        <li>We do not fingerprint your visitors or your paid customers.</li>
        <li>We do not use your generated content to train third-party models.</li>
      </ul>

      <h2>3. Third parties that process data on our behalf</h2>
      <ul>
        <li><strong>OpenAI, Anthropic, Google (Gemini)</strong> — LLM inference for scripts, subtitles and images. Your topics + prompts are transmitted to these providers under their standard data-processing terms.</li>
        <li><strong>fal.ai</strong> (only when Talking-Head lip-sync is enabled) — for character portrait + audio → talking-head video rendering.</li>
        <li><strong>Google (via Emergent Auth)</strong> — for Sign in with Google.</li>
        <li><strong>MongoDB Atlas</strong> — encrypted-at-rest primary database.</li>
        <li><strong>PostHog</strong> — anonymous product analytics.</li>
      </ul>

      <h2>4. How we secure your data</h2>
      <ul>
        <li>All traffic is TLS-encrypted end-to-end.</li>
        <li>Passwords are hashed with bcrypt (never stored in plaintext).</li>
        <li>Sessions use HttpOnly, Secure, SameSite=None cookies with 7-day expiry.</li>
        <li>Password reset tokens are single-use and expire in 1 hour.</li>
        <li>We enforce rate-limits on login (20/10min per IP) and forgot-password (5/10min) to defeat credential-stuffing.</li>
      </ul>

      <h2>5. Your rights</h2>
      <p>You have the right to:</p>
      <ul>
        <li>Export your account data — reply to any transactional email and we will send you a JSON dump within 30 days.</li>
        <li>Delete your account and all associated projects, character portraits, and analytics events.</li>
        <li>Withdraw consent for optional analytics by contacting us.</li>
      </ul>

      <h2>6. Data retention</h2>
      <ul>
        <li>Abandoned draft projects with no generated content are auto-deleted after 24 hours.</li>
        <li>Password reset tokens are auto-purged 1 hour after expiry (or 7 days after use).</li>
        <li>Orphan character portrait files are auto-purged 24 hours after their parent project is deleted.</li>
        <li>Deleted accounts have all associated data purged within 30 days, except where we are required by law to retain it (e.g. tax records for paid transactions).</li>
      </ul>

      <h2>7. International transfers</h2>
      <p>The Service may process data outside your country of residence. Where applicable, we rely on Standard Contractual Clauses (SCCs) for EU-to-US transfers.</p>

      <h2>8. Children</h2>
      <p>The Service is not directed at anyone under 16. We do not knowingly collect data from children. If you become aware that a minor has provided us data without parental consent, contact us and we will delete the information.</p>

      <h2>9. Changes</h2>
      <p>We&apos;ll notify you of material changes to this Policy by email at least 14 days before they take effect.</p>
    </LegalShell>
  );
}
