import { useEffect, useRef, useState } from "react";
import { Activity, CheckCircle2, XCircle, AlertTriangle, Loader2, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

// Live system health tile — polls /api/health every 15s and shows overall status
// + individual dependency checks + response time. Uses raw fetch (not the axios
// wrapper) so we can measure real end-to-end latency including ingress hops.
const POLL_MS = 15000;
const HEALTH_URL = `${process.env.REACT_APP_BACKEND_URL}/api/health`;

function Dot({ status }) {
  const color =
    status === "ok" ? "bg-emerald-500"
    : status === "degraded" ? "bg-amber-500"
    : status === "missing" ? "bg-rose-500"
    : status === "error" || status?.startsWith?.("error") ? "bg-rose-500"
    : "bg-ink-300";
  return <span className={`inline-block w-2 h-2 rounded-full ${color}`} />;
}

export default function HealthTile() {
  const [state, setState] = useState({ loading: true });
  const [repairing, setRepairing] = useState(false);
  const timerRef = useRef(null);

  const poll = async () => {
    const t0 = performance.now();
    try {
      const res = await fetch(HEALTH_URL, { credentials: "include", cache: "no-store" });
      const data = await res.json();
      setState({
        loading: false,
        ok: res.ok,
        status: data.status || (res.ok ? "ok" : "degraded"),
        checks: data.checks || {},
        latency_ms: Math.round(performance.now() - t0),
        at: new Date(),
        error: null,
      });
    } catch (e) {
      setState({
        loading: false,
        ok: false,
        status: "unreachable",
        checks: {},
        latency_ms: Math.round(performance.now() - t0),
        at: new Date(),
        error: e.message,
      });
    }
  };

  useEffect(() => {
    poll();
    timerRef.current = setInterval(poll, POLL_MS);
    return () => clearInterval(timerRef.current);
  }, []);

  const repairFfmpeg = async () => {
    setRepairing(true);
    try {
      const { data } = await api.post("/admin/repair/ffmpeg");
      toast.success("ffmpeg repaired", { description: `Status: ${data.status} · path: ${data.path}` });
      poll(); // refresh the tile immediately
    } catch (e) {
      toast.error("Repair failed", { description: e?.response?.data?.detail || e.message });
    } finally {
      setRepairing(false);
    }
  };

  const ffmpegBroken = !state.loading && state.checks?.ffmpeg && state.checks.ffmpeg !== "ok";

  const badgeStyles =
    state.status === "ok"
      ? "bg-emerald-50 border-emerald-200 text-emerald-800"
      : state.status === "degraded"
      ? "bg-amber-50 border-amber-200 text-amber-800"
      : "bg-rose-50 border-rose-200 text-rose-800";

  const StatusIcon =
    state.status === "ok" ? CheckCircle2
    : state.status === "degraded" ? AlertTriangle
    : XCircle;

  const label =
    state.status === "ok" ? "All systems operational"
    : state.status === "degraded" ? "Degraded"
    : state.status === "unreachable" ? "Unreachable"
    : "Unknown";

  return (
    <div className="bg-white border border-ink-200 rounded-2xl p-5" data-testid="admin-health-tile">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 min-w-0">
          <Activity className="w-4 h-4 text-brand-600" />
          <div className="text-xs uppercase tracking-widest text-ink-500 font-semibold">System health</div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {state.loading ? (
            <span className="inline-flex items-center gap-1 text-xs text-ink-500">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Checking…
            </span>
          ) : (
            <>
              <span className={`inline-flex items-center gap-1.5 text-[10px] uppercase tracking-widest font-bold rounded-full border px-2.5 py-1 ${badgeStyles}`}
                    data-testid="admin-health-status">
                <StatusIcon className="w-3 h-3" /> {label}
              </span>
              <span className="text-[10px] text-ink-500 font-mono" data-testid="admin-health-latency">
                {state.latency_ms}ms
              </span>
            </>
          )}
        </div>
      </div>

      {!state.loading && (
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-2" data-testid="admin-health-checks">
          {["mongodb", "ffmpeg", "llm_key"].map((key) => {
            const val = state.checks[key] || (state.status === "unreachable" ? "unreachable" : "unknown");
            return (
              <div key={key} className="flex items-center gap-2 rounded-lg bg-ink-50 border border-ink-100 px-3 py-2"
                   data-testid={`admin-health-check-${key}`}>
                <Dot status={val === "ok" ? "ok" : val === "missing" ? "missing" : val?.startsWith?.("error") ? "error" : "degraded"} />
                <span className="text-xs font-semibold capitalize text-ink-700">{key.replace("_", " ")}</span>
                <span className={`ml-auto text-[10px] font-mono ${val === "ok" ? "text-emerald-700" : "text-rose-700"}`}>
                  {val === "ok" ? "OK" : val}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {state.at && (
        <div className="mt-3 flex items-center justify-between gap-3 flex-wrap">
          <div className="text-[10px] text-ink-400 font-mono">
            Last checked {state.at.toLocaleTimeString()} · polls every {POLL_MS / 1000}s
          </div>
          {ffmpegBroken && (
            <button
              onClick={repairFfmpeg}
              disabled={repairing}
              className="inline-flex items-center gap-1.5 text-xs font-semibold rounded-full border border-brand-600 text-brand-700 bg-white hover:bg-brand-50 px-3 py-1.5 disabled:opacity-50"
              data-testid="admin-health-repair-ffmpeg">
              {repairing ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Repairing…</>
                         : <><Wrench className="w-3.5 h-3.5" /> Repair ffmpeg</>}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
