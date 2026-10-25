import { useEffect, useState } from "react";
import { Globe, Loader2, Server, ServerOff, ShieldAlert } from "lucide-react";
import { api } from "../api/client";
import { MockBanner } from "../components/Layout";
import type { IssuerStatusView } from "../types";

const STATUS_TONE: Record<string, string> = {
  VERIFIED: "bg-emerald-500",
  MANUAL_REVIEW: "bg-amber-500",
  SOURCE_UNAVAILABLE: "bg-sky-500",
  EXPIRED: "bg-orange-500",
  NOT_FOUND: "bg-rose-500",
  INVALID: "bg-rose-600",
};

export default function IssuerStatus() {
  const [data, setData] = useState<IssuerStatusView | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<IssuerStatusView>("/issuer/status")
      .then((r) => setData(r.data))
      .catch(() => setError("Could not load issuer portal status"));
  }, []);

  if (error) return <div className="text-sm text-rose-300">{error}</div>;

  if (!data)
    return (
      <div className="flex items-center gap-2 text-slate-400">
        <Loader2 className="h-5 w-5 animate-spin" /> Querying issuer portals…
      </div>
    );

  const { summary } = data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold">
            <Globe className="h-5 w-5 text-indigo-400" /> Issuer portal status
          </h1>
          <p className="text-xs text-slate-400">
            Live health of every authority portal VeriGate cross-checks documents
            against, plus the outcome of each check. Updated {data.updated_at}.
          </p>
        </div>
        <span className="rounded-full bg-gradient-to-r from-indigo-500/25 to-sky-500/20 px-3 py-1 text-xs font-semibold text-sky-200 ring-1 ring-sky-500/30">
          {summary.verified}/{summary.total_checks} checks verified ·{" "}
          {Math.round(summary.verified_rate * 100)}%
        </span>
      </div>

      <MockBanner />

      {/* What the statuses mean - the scenario D story in one line */}
      <div className="rounded-lg border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs leading-relaxed text-sky-200">
        <b className="text-sky-100">SOURCE_UNAVAILABLE = the portal did not
        answer</b> - unknown, not fake. The Evidence Gate abstains and routes the
        file to a human instead of approving or rejecting it (demo scenario D).
      </div>

      {/* Summary tiles */}
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          {
            label: "Portals online",
            value: `${summary.portals - summary.down}/${summary.portals}`,
            tone: "text-emerald-300",
          },
          {
            label: "Checks performed",
            value: summary.total_checks,
            tone: "text-slate-100",
            sub: "one per document with an issuing portal",
          },
          {
            label: "Verification rate",
            value: `${Math.round(summary.verified_rate * 100)}%`,
            tone: "text-emerald-300",
          },
        ].map((s) => (
          <div className="card" key={s.label}>
            <div className="text-[10px] uppercase tracking-widest text-slate-500">
              {s.label}
            </div>
            <div className={`mt-1 text-2xl font-bold ${s.tone}`}>{s.value}</div>
            {s.sub && <div className="mt-0.5 text-[11px] text-slate-500">{s.sub}</div>}
          </div>
        ))}
      </div>

      {/* Portal cards */}
      <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
        {data.portals.map((p) => {
          const down = p.status === "DOWN";
          const total = Math.max(1, p.checks_total);
          return (
            <div
              key={p.id}
              className={`card ${
                down
                  ? "border-rose-500/50"
                  : p.degraded
                  ? "border-amber-500/40"
                  : ""
              }`}
              data-testid={`portal-${p.id}`}
            >
              <div className="flex items-start gap-2">
                {down ? (
                  <ServerOff className="mt-0.5 h-5 w-5 shrink-0 text-rose-400" />
                ) : (
                  <Server
                    className={`mt-0.5 h-5 w-5 shrink-0 ${
                      p.degraded ? "text-amber-400" : "text-emerald-400"
                    }`}
                  />
                )}
                <div className="min-w-0">
                  <div className="font-semibold leading-tight">{p.name}</div>
                  <div className="font-mono text-[10px] text-slate-500">{p.id}</div>
                </div>
                <span
                  className={`ml-auto rounded-full px-2 py-0.5 text-[10px] font-bold ${
                    down
                      ? "bg-rose-500/15 text-rose-300"
                      : p.degraded
                      ? "bg-amber-500/15 text-amber-300"
                      : "bg-emerald-500/15 text-emerald-300"
                  }`}
                >
                  {down ? "DOWN" : p.degraded ? "DEGRADED" : "UP"}
                </span>
              </div>

              {/* verification outcome bar */}
              <div className="mt-3">
                <div className="mb-1 flex items-center justify-between text-[11px]">
                  <span className="text-slate-400">
                    {p.checks_total} document checks
                  </span>
                  <span className="text-slate-300">
                    {p.verified_rate === null
                      ? "no checks yet"
                      : `${Math.round(p.verified_rate * 100)}% verified`}
                  </span>
                </div>
                <div className="flex h-2.5 w-full overflow-hidden rounded bg-slate-800">
                  {Object.entries(p.checks).map(([status, n]) => (
                    <div
                      key={status}
                      className={STATUS_TONE[status] ?? "bg-slate-500"}
                      style={{ width: `${(n / total) * 100}%` }}
                      title={`${status}: ${n}`}
                    />
                  ))}
                </div>
              </div>

              {/* breakdown */}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {Object.entries(p.checks).map(([status, n]) => (
                  <span
                    key={status}
                    className="rounded bg-slate-800/80 px-1.5 py-0.5 text-[10px] text-slate-300"
                  >
                    {status.replace(/_/g, " ")} <b>{n}</b>
                  </span>
                ))}
                {p.checks_total === 0 && (
                  <span className="text-[11px] text-slate-500">
                    No documents reference this portal yet.
                  </span>
                )}
              </div>

              {/* affected applications */}
              {Object.keys(p.examples).length > 0 && (
                <div className="mt-3 rounded border border-slate-800 bg-slate-950/40 p-2 text-[11px]">
                  {Object.entries(p.examples).map(([status, refs]) => (
                    <div key={status} className="flex gap-2">
                      <span className="shrink-0 text-slate-500">
                        {status.replace(/_/g, " ")}:
                      </span>
                      <span className="font-mono text-slate-300">
                        {refs.join(", ")}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-800 pt-2 text-[10px] text-slate-500">
                <span>{p.records} records on file</span>
                {p.records_down > 0 && (
                  <span className="flex items-center gap-1 text-amber-300">
                    <ShieldAlert className="h-3 w-3" />
                    {p.records_down} record(s) reporting outage
                  </span>
                )}
                {p.last_checked && <span className="ml-auto">last check {p.last_checked}</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
