import { api } from "@/lib/api";

const KEY_SESSION = "avs_session_id";
const KEY_SOURCE = "avs_attribution";

function getSessionId() {
  let s = localStorage.getItem(KEY_SESSION);
  if (!s) {
    s = "s_" + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
    localStorage.setItem(KEY_SESSION, s);
  }
  return s;
}

/** Persist UTM / referrer attribution once per session so every event gets it. */
export function captureAttribution() {
  try {
    const existing = JSON.parse(localStorage.getItem(KEY_SOURCE) || "null");
    if (existing) return existing;
    const params = new URLSearchParams(window.location.search);
    const utm = {
      source: params.get("utm_source") || params.get("ref") || null,
      medium: params.get("utm_medium") || null,
      campaign: params.get("utm_campaign") || null,
    };
    let referrer_host = null;
    try {
      if (document.referrer) referrer_host = new URL(document.referrer).hostname;
    } catch { /* ignore */ }
    // Classify traffic source
    let source = utm.source;
    if (!source) {
      if (!referrer_host || referrer_host.includes(window.location.hostname)) source = "direct";
      else if (/(google|bing|duckduckgo|yahoo)/i.test(referrer_host)) source = "organic_search";
      else if (/(twitter|x\.com|t\.co|linkedin|facebook|instagram|reddit|producthunt)/i.test(referrer_host)) source = "social";
      else source = "referral";
    }
    const attribution = { source, medium: utm.medium, campaign: utm.campaign, referrer_host };
    localStorage.setItem(KEY_SOURCE, JSON.stringify(attribution));
    return attribution;
  } catch { return { source: "direct" }; }
}

export function getAttribution() {
  try { return JSON.parse(localStorage.getItem(KEY_SOURCE) || "null") || { source: "direct" }; }
  catch { return { source: "direct" }; }
}

export async function track(event, properties = {}) {
  try {
    const attr = getAttribution();
    let variant = null;
    try {
      const cached = JSON.parse(localStorage.getItem("avs_exp_landing_hero") || "null");
      variant = cached?.variant || null;
    } catch { /* ignore */ }
    await api.post("/analytics/track", {
      event,
      properties: { ...attr, ...properties, variant },
      session_id: getSessionId(),
      path: window.location.pathname + window.location.hash,
    });
  } catch { /* swallow */ }
}
