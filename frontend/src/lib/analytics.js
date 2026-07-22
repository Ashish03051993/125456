import { api } from "@/lib/api";

const KEY = "avs_session_id";
function getSessionId() {
  let s = localStorage.getItem(KEY);
  if (!s) {
    s = "s_" + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
    localStorage.setItem(KEY, s);
  }
  return s;
}

export async function track(event, properties = {}) {
  try {
    await api.post("/analytics/track", {
      event,
      properties,
      session_id: getSessionId(),
      path: window.location.pathname + window.location.hash,
    });
  } catch { /* swallow */ }
}
