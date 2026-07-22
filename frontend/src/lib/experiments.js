import { api } from "@/lib/api";

const CLIENT_KEY = "avs_client_id";

function getClientId() {
  let c = localStorage.getItem(CLIENT_KEY);
  if (!c) {
    c = "c_" + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
    localStorage.setItem(CLIENT_KEY, c);
  }
  return c;
}

/**
 * Fetch (or cache) the assigned variant + content for an experiment.
 * Cached per-experiment in localStorage so the visitor sees a stable UI.
 */
export async function fetchVariant(experiment) {
  const cacheKey = `avs_exp_${experiment}`;
  const cached = localStorage.getItem(cacheKey);
  if (cached) {
    try { return JSON.parse(cached); } catch { /* re-fetch */ }
  }
  const client_id = getClientId();
  const { data } = await api.get(`/experiments/${experiment}/${client_id}`);
  localStorage.setItem(cacheKey, JSON.stringify(data));
  return data;
}

/** Read the cached variant name for tagging analytics events. */
export function currentVariant(experiment) {
  try {
    const cached = JSON.parse(localStorage.getItem(`avs_exp_${experiment}`) || "null");
    return cached?.variant || null;
  } catch { return null; }
}
