import { useEffect, useState } from "react";
import {
  BarChart3,
  Loader2,
  TrendingUp,
  AlertTriangle,
  FileWarning,
  Clock,
} from "lucide-react";
import { api } from "../api/client";
import { MockBanner } from "../components/Layout";
import type { AnalyticsView } from "../types";

const STATUS_TONE: Record<string, string> = {
  VERIFIED: "bg-emerald-500",
  APPROVED: "bg-emerald-600",
  INSUFFICIENT_EVIDENCE: "bg-amber-500",
  IN_REVIEW: "bg-sky-500",
  PROCESSING: "bg-indigo-500",
  UPLOADED: "bg-slate-500",
  REJECTED: "bg-rose-500",
};

function Bar({
  label,
  value,
  max,
  color = "bg-indigo-500",
  hint,
}: {
  label: string;
  value: number;
  max: number;
  color?: string;
  hint?: string;
}) {
  const pct = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-44 shrink-0 truncate text-slate-400" title={label}>
        {label}
      </span>
      <div className="h-3 flex-1 rounded bg-slate-800">
        <div className={`h-full rounded ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-7 text-right font-mono text-slate-200">{value}</span>
      {hint && (
        <span className="w-16 text-right text-[10px] text-slate-500">{hint}</span>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  tone = "text-slate-100",
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: string;
}) {
  return (
    <div className="card">
      <div className="text-[10px] uppercase tracking-widest text-slate-500">
        {label}
      </div>
      <div className={`mt-1 text-2xl font-bold ${tone}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-slate-500">{sub}</div>}
    </div>
  );
}

export default function Analytics() {
  const [data, setData] = useState<AnalyticsView | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<AnalyticsView>("/dashboard/analytics")
      .then((r) => setData(r.data))
      .catch(() => setError("Could not load analytics"));
  }, []);

  if (error)
    return <div className="text-sm text-rose-300">{error}</div>;

  if (!data)
    return (
      <div className="flex items-center gap-2 text-slate-400">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading analytics…
      </div>
    );

  const { totals, averages, by_category } = data;
  const maxCat = Math.max(1, ...by_category.map((c) => c.total));
  const maxRule = Math.max(1, ...data.flags_by_rule.map((r) => r.count));
  const maxGap = Math.max(1, ...data.document_gaps.map((g) => g.count));
  const maxOutcome = Math.max(1, ...data.gate_outcomes.map((o) => o.count));
  const maxAbstain = Math.max(1, ...data.abstain_reasons.map((a) => a.count));
  const maxIssuer = Math.max(1, ...data.issuer_outcomes.map((o) => o.count));
  const maxRisk = Math.max(1, ...data.risk_buckets.map((b) => b.count));
  const maxAging = Math.max(1, ...data.queue_aging.map((b) => b.count));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold">
            <BarChart3 className="h-5 w-5 text-indigo-400" /> Analytics &amp; trends
          </h1>
          <p className="text-xs text-slate-400">
            Portfolio view of every validation run - what the Evidence Gate certified,
            what it refused to certify, and why. Generated {data.generated_at}.
          </p>
        </div>
        <span className="rounded-full bg-indigo-500/15 px-3 py-1 text-xs text-indigo-300">
          {totals.applications} applications · {totals.documents} documents ·{" "}
          {totals.flags} flags
        </span>
      </div>

      <MockBanner />

      {/* KPI row */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Stat
          label="Gate pass rate"
          value={`${Math.round(totals.gate_pass_rate * 100)}%`}
          sub={`${totals.verified} verified · ${totals.insufficient_evidence} abstained`}
          tone="text-emerald-300"
        />
        <Stat
          label="Flags raised"
          value={totals.flags}
          sub={`${totals.open_flags} still open`}
          tone="text-amber-300"
        />
        <Stat
          label="Avg OCR confidence"
          value={averages.ocr_confidence.toFixed(2)}
          sub="gate needs > 0.90"
        />
        <Stat
          label="Avg consistency"
          value={averages.consistency.toFixed(2)}
          sub="gate needs > 0.70"
        />
        <Stat
          label="Avg risk score"
          value={averages.risk.toFixed(2)}
          sub="1 - weakest evidence link"
          tone="text-rose-300"
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {/* Gate outcomes */}
        <div className="card">
          <h3 className="mb-3 font-semibold">Evidence Gate outcomes</h3>
          <div className="space-y-2">
            {data.gate_outcomes.map((o) => (
              <Bar
                key={o.status}
                label={o.status.replace(/_/g, " ")}
                value={o.count}
                max={maxOutcome}
                color={STATUS_TONE[o.status] ?? "bg-slate-500"}
                hint={`${Math.round((o.count / Math.max(1, totals.applications)) * 100)}%`}
              />
            ))}
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
            The gate never rejects: amber files were <i>abstained</i> and routed to the
            manual review queue for a human decision.
          </p>
        </div>

        {/* By category */}
        <div className="card">
          <h3 className="mb-3 font-semibold">Applications by category</h3>
          <div className="space-y-3">
            {by_category.map((c) => (
              <div key={c.category} className="text-xs">
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-slate-300">{c.category}</span>
                  <span className="text-slate-500">
                    {c.total} files · {c.verified} verified · avg confidence{" "}
                    {c.avg_confidence.toFixed(2)}
                  </span>
                </div>
                <div className="flex h-3 w-full overflow-hidden rounded bg-slate-800">
                  <div
                    className="h-full bg-emerald-500"
                    style={{
                      width: `${(c.verified / Math.max(1, c.total)) * 100}%`,
                    }}
                    title={`${c.verified} verified`}
                  />
                  <div
                    className="h-full bg-amber-500"
                    style={{
                      width: `${(c.insufficient / Math.max(1, c.total)) * 100}%`,
                    }}
                    title={`${c.insufficient} abstained`}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 flex gap-4 text-[10px] text-slate-500">
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-sm bg-emerald-500" /> verified
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-sm bg-amber-500" /> abstained →
              manual review
            </span>
          </div>
        </div>

        {/* Top rules */}
        <div className="card">
          <h3 className="mb-3 flex items-center gap-2 font-semibold">
            <AlertTriangle className="h-4 w-4 text-amber-400" /> Which rules fire
            most
          </h3>
          <div className="space-y-2">
            {data.flags_by_rule.map((r) => (
              <Bar
                key={r.rule_id}
                label={`${r.rule_id} · ${r.title}`}
                value={r.count}
                max={maxRule}
                color={
                  r.severity === "CRITICAL" ? "bg-rose-500" : "bg-amber-500"
                }
                hint={r.severity === "CRITICAL" ? "critical" : "warn"}
              />
            ))}
          </div>
        </div>

        {/* Abstain reasons */}
        <div className="card">
          <h3 className="mb-3 flex items-center gap-2 font-semibold">
            <TrendingUp className="h-4 w-4 text-indigo-400" /> Why the gate abstains
          </h3>
          <div className="space-y-2">
            {data.abstain_reasons.map((a) => (
              <Bar
                key={a.rule_id}
                label={a.rule_id}
                value={a.count}
                max={maxAbstain}
                color="bg-amber-500"
              />
            ))}
            {data.abstain_reasons.length === 0 && (
              <p className="text-xs text-slate-500">No abstentions recorded.</p>
            )}
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
            Each bar is a distinct Evidence Gate condition that failed at least once
            (OCR, issuer, rules, tamper, consistency).
          </p>
        </div>

        {/* Document gaps */}
        <div className="card">
          <h3 className="mb-3 flex items-center gap-2 font-semibold">
            <FileWarning className="h-4 w-4 text-rose-400" /> Missing &amp; expired
            documents
          </h3>
          <div className="space-y-2">
            {data.document_gaps.map((g) => (
              <Bar
                key={`${g.status}-${g.name}`}
                label={`${g.name} (${g.status})`}
                value={g.count}
                max={maxGap}
                color={g.status === "MISSING" ? "bg-rose-500" : "bg-orange-500"}
                hint={g.rule_id}
              />
            ))}
            {data.document_gaps.length === 0 && (
              <p className="text-xs text-emerald-300">
                Every required document was present and valid.
              </p>
            )}
          </div>
        </div>

        {/* Issuer + risk + aging stacked in one column each */}
        <div className="space-y-4">
          <div className="card">
            <h3 className="mb-3 font-semibold">Issuer portal outcomes</h3>
            <div className="space-y-2">
              {data.issuer_outcomes.map((o) => (
                <Bar
                  key={o.status}
                  label={o.status.replace(/_/g, " ")}
                  value={o.count}
                  max={maxIssuer}
                  color={
                    o.status === "VERIFIED"
                      ? "bg-emerald-500"
                      : o.status === "SOURCE_UNAVAILABLE"
                      ? "bg-sky-500"
                      : "bg-rose-500"
                  }
                  hint={`${Math.round(
                    (o.count / Math.max(1, totals.applications)) * 100
                  )}%`}
                />
              ))}
            </div>
          </div>

          <div className="card">
            <h3 className="mb-3 font-semibold">Risk distribution</h3>
            <div className="space-y-2">
              {data.risk_buckets.map((b) => (
                <Bar
                  key={b.bucket}
                  label={b.bucket}
                  value={b.count}
                  max={maxRisk}
                  color="bg-rose-500/80"
                />
              ))}
            </div>
            <p className="mt-3 text-[11px] text-slate-500">
              Risk = 1 - gate confidence (plus a penalty for critical flags).
            </p>
          </div>
        </div>

        {/* Queue aging */}
        <div className="space-y-4">
          <div className="card">
            <h3 className="mb-3 flex items-center gap-2 font-semibold">
              <Clock className="h-4 w-4 text-sky-400" /> Manual review queue aging
            </h3>
            <div className="space-y-2">
              {data.queue_aging.map((b) => (
                <Bar
                  key={b.bucket}
                  label={b.bucket}
                  value={b.count}
                  max={maxAging}
                  color="bg-sky-500"
                />
              ))}
            </div>
            <p className="mt-3 text-[11px] text-slate-500">
              Files awaiting a human decision, grouped by time in the queue.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
