import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Search,
  ShieldCheck,
  AlertTriangle,
  Eye,
  Activity,
  Workflow,
  Lightbulb,
  ArrowRight,
  Trash2,
} from "lucide-react";
import { api } from "../api/client";
import { MockBanner } from "../components/Layout";
import StatusBadge, { IssuerBadge } from "../components/StatusBadge";
import { useAuth } from "../auth/AuthContext";
import type { ApplicationSummary, DashboardStats } from "../types";

/** Plain-English guide for the 5 built-in demo scenarios (clickable). */
const SCENARIO_GUIDE: Record<
  string,
  { title: string; look: string }
> = {
  A: { title: "Clean application", look: "Green VERIFIED verdict, zero flags" },
  B: { title: "Missing document", look: "Red rule flag APH-MGT-003, checklist shows 'not uploaded'" },
  C: { title: "Tampered date", look: "Red box over the altered date + ELA heatmap toggle" },
  D: { title: "Issuer portal down", look: "SOURCE UNAVAILABLE → routed to review, never auto-rejected" },
  E: { title: "Low OCR confidence", look: "OCR 0.87 < 0.90 → gate abstains → review queue" },
};

const FLOW_STEPS = [
  { t: "1 · Upload", d: "An officer uploads the application's PDFs and picks the category." },
  { t: "2 · Read", d: "OCR extracts every field with its location and confidence." },
  { t: "3 · Check rules", d: "APH 2024-27 checklist: missing or expired documents get flagged." },
  { t: "4 · Verify", d: "Issuer portals, ELA tamper check, duplicate (pHash) and XGBoost consistency." },
  { t: "5 · Evidence Gate", d: "Strong evidence → VERIFIED. Anything weaker → it abstains." },
  { t: "6 · Human decides", d: "Flags go to the review queue: approve, reject or request info. All audited." },
];

export default function Dashboard() {
  const { canUpload } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [apps, setApps] = useState<ApplicationSummary[]>([]);
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  // officer-only delete: confirmId = row waiting for the 2nd confirming click
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  // seeded from navigation state so a delete on the detail page can report back
  const location = useLocation();
  const [notice, setNotice] = useState<{ tone: "ok" | "bad"; text: string } | null>(
    () =>
      (location.state as { notice?: { tone: "ok" | "bad"; text: string } } | null)
        ?.notice ?? null
  );

  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(null), 5000);
    return () => clearTimeout(t);
  }, [notice]);

  async function deleteApp(a: ApplicationSummary) {
    setBusyId(a.id);
    try {
      await api.delete(`/applications/${a.id}`);
      setApps((prev) => prev.filter((x) => x.id !== a.id));
      const { data } = await api.get<DashboardStats>("/dashboard/stats");
      setStats(data);
      setNotice({ tone: "ok", text: `${a.ref_no} (${a.institution_name}) deleted` });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Delete failed";
      setNotice({ tone: "bad", text: msg });
    } finally {
      setBusyId(null);
      setConfirmId(null);
    }
  }

  useEffect(() => {
    api.get<DashboardStats>("/dashboard/stats").then((r) => setStats(r.data));
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      api
        .get<ApplicationSummary[]>("/applications", {
          params: { status, category, q },
        })
        .then((r) => setApps(r.data));
    }, 200);
    return () => clearTimeout(t);
  }, [status, category, q]);

  const gateChart = useMemo(() => {
    if (!stats) return null;
    const decided = stats.verified + stats.insufficient_evidence;
    const awaiting = Math.max(stats.total - decided, 0);
    const passPct = decided ? (stats.verified / decided) * 100 : 0;
    return { passPct, failPct: 100 - passPct, decided, awaiting };
  }, [stats]);

  return (
    <div className="space-y-5">
      <MockBanner />
      {notice && (
        <div
          className={`rounded-lg border px-3 py-2 text-sm ${
            notice.tone === "ok"
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
              : "border-rose-500/40 bg-rose-500/10 text-rose-200"
          }`}
        >
          {notice.text}
        </div>
      )}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-xs text-slate-400">
            Risk-ranked EoA applications — the Evidence Gate advises, officers decide.
          </p>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          icon={<ShieldCheck className="h-5 w-5 text-emerald-300" />}
          label="Verified by Evidence Gate"
          value={stats?.verified ?? "–"}
          tone="text-emerald-300"
          glow="from-emerald-500/25 to-emerald-500/5 ring-emerald-500/25"
        />
        <StatCard
          icon={<AlertTriangle className="h-5 w-5 text-amber-300" />}
          label="Insufficient evidence"
          value={stats?.insufficient_evidence ?? "–"}
          tone="text-amber-300"
          glow="from-amber-500/25 to-amber-500/5 ring-amber-500/25"
        />
        <StatCard
          icon={<Eye className="h-5 w-5 text-sky-300" />}
          label="In manual review"
          value={stats?.in_review ?? "–"}
          tone="text-sky-300"
          glow="from-sky-500/25 to-sky-500/5 ring-sky-500/25"
        />
        <StatCard
          icon={<Activity className="h-5 w-5 text-indigo-300" />}
          label="Total applications"
          value={stats?.total ?? "–"}
          tone="text-indigo-300"
          glow="from-indigo-500/25 to-indigo-500/5 ring-indigo-500/25"
        />
      </div>

      {/* ------------------------------------------------------ how it works */}
      <div className="card">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h2 className="flex items-center gap-2 font-semibold">
            <Workflow className="h-4 w-4 text-indigo-400" /> How VeriGate works
          </h2>
          <span className="text-xs text-slate-500">AI advises — humans decide</span>
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-6">
          {FLOW_STEPS.map((s) => (
            <div
              key={s.t}
              className="rounded-lg border border-slate-800 bg-slate-950/40 p-3"
            >
              <div className="mb-1 text-xs font-bold text-indigo-300">{s.t}</div>
              <p className="text-[11px] leading-snug text-slate-400">{s.d}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs leading-relaxed text-slate-400">
          The <b className="text-indigo-300">Evidence Gate</b> is the safety
          feature: it marks a file <b className="text-emerald-300">VERIFIED</b> only
          when <i>every</i> check passes — OCR &gt; 0.90, XGBoost consistency ≥ 0.70,
          every issuer portal confirms the documents, no tamper or duplicate hit and no
          critical rule flag. Anything weaker → it says{" "}
          <b className="text-amber-300">INSUFFICIENT_EVIDENCE</b> and sends the
          file to the Manual Review Queue.{" "}
          <span className="text-slate-300">It never guesses.</span>
        </p>
      </div>

      {/* --------------------------------------------------- demo scenarios */}
      <div className="card">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h2 className="flex items-center gap-2 font-semibold">
            <Lightbulb className="h-4 w-4 text-amber-400" /> 5 demo scenarios —
            click any card to open it
          </h2>
          <span className="text-xs text-slate-500">pre-validated, ready to present</span>
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {(["A", "B", "C", "D", "E"] as const).map((tag) => {
            const app = apps.find((a) => a.scenario === tag);
            const info = SCENARIO_GUIDE[tag];
            if (!app) return null;
            return (
              <Link
                key={tag}
                to={`/applications/${app.id}`}
                className="group rounded-lg border border-slate-800 bg-slate-950/40 p-3 transition hover:border-indigo-500/60 hover:bg-slate-800/50"
              >
                <div className="mb-1 flex items-center justify-between">
                  <span className="rounded bg-fuchsia-600/30 px-1.5 py-0.5 text-[10px] font-bold text-fuchsia-300">
                    {tag}
                  </span>
                  <ArrowRight className="h-3.5 w-3.5 text-slate-600 transition group-hover:text-indigo-300" />
                </div>
                <div className="text-xs font-semibold text-slate-200">
                  {info.title}
                </div>
                <div className="mt-0.5 font-mono text-[10px] text-slate-500">
                  app #{app.id} · {app.ref_no}
                </div>
                <div className="mt-1.5">
                  <StatusBadge status={app.status} />
                </div>
                <p className="mt-1.5 text-[10px] leading-snug text-slate-500">
                  {info.look}
                </p>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Evidence Gate chart */}
      {gateChart && (
        <div className="card">
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="font-semibold">Evidence Gate outcomes</h2>
            <span className="text-xs text-slate-400">
              pass rate {((stats?.gate_pass_rate ?? 0) * 100).toFixed(1)}% over{" "}
              {gateChart.decided} machine-decided applications
              {gateChart.awaiting > 0 ? ` · ${gateChart.awaiting} await a human` : ""}
            </span>
          </div>
          <div className="flex h-8 overflow-hidden rounded-lg bg-slate-800">
            <div
              className="flex items-center justify-center bg-emerald-600 text-xs font-bold text-white transition-all"
              style={{ width: `${gateChart.passPct}%` }}
              title={`VERIFIED: ${stats?.verified}`}
            >
              {gateChart.passPct > 12 ? `VERIFIED ${stats?.verified}` : ""}
            </div>
            <div
              className="flex items-center justify-center bg-amber-500 text-xs font-bold text-amber-950 transition-all"
              style={{ width: `${gateChart.failPct}%` }}
              title={`INSUFFICIENT_EVIDENCE: ${stats?.insufficient_evidence}`}
            >
              {gateChart.failPct > 12
                ? `INSUFFICIENT EVIDENCE ${stats?.insufficient_evidence}`
                : ""}
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-400">
            {Object.entries(stats?.by_category ?? {}).map(([cat, n]) => (
              <span key={cat}>
                {cat}: <b className="text-slate-200">{n}</b>
              </span>
            ))}
            {(stats?.approved ?? 0) + (stats?.rejected ?? 0) > 0 ? (
              <span>
                Human decisions: approved <b className="text-emerald-300">{stats?.approved}</b> ·
                rejected <b className="text-rose-300">{stats?.rejected}</b> ·
                in review <b className="text-sky-300">{stats?.in_review}</b>
              </span>
            ) : (
              <span>
                No human decisions yet — <b className="text-sky-300">{stats?.insufficient_evidence}</b>{" "}
                files wait in the review queue
              </span>
            )}
          </div>
        </div>
      )}

      {/* Risk-ranked list */}
      <div className="card">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <h2 className="mr-auto font-semibold">Applications (risk-ranked)</h2>
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-500" />
            <input
              className="input !w-56 !pl-8"
              placeholder="Search name / ref / AICTE ID"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <select className="input !w-44" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="VERIFIED">Verified</option>
            <option value="INSUFFICIENT_EVIDENCE">Insufficient evidence</option>
            <option value="IN_REVIEW">In review</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
            <option value="UPLOADED">Awaiting validation</option>
          </select>
          <select className="input !w-40" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All categories</option>
            <option>Engineering</option>
            <option>Management</option>
            <option>Pharmacy</option>
          </select>
        </div>

        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="py-2">Ref</th>
              <th>Institution</th>
              <th>Category</th>
              <th>Status</th>
              <th>Risk</th>
              <th>Gate confidence</th>
              <th>Issuer</th>
              <th className="text-right">Flags</th>
              {canUpload && <th className="text-right">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {apps.map((a) => (
              <tr
                key={a.id}
                className="border-b border-slate-800/60 transition hover:bg-slate-800/40"
              >
                <td className="py-2.5">
                  <Link
                    to={`/applications/${a.id}`}
                    className="font-mono text-indigo-300 hover:underline"
                  >
                    {a.ref_no}
                  </Link>
                  {a.scenario && (
                    <span className="ml-1 rounded bg-fuchsia-600/30 px-1 text-[10px] font-bold text-fuchsia-300">
                      {a.scenario}
                    </span>
                  )}
                </td>
                <td className="max-w-[260px] truncate">{a.institution_name}</td>
                <td className="text-slate-400">{a.category}</td>
                <td>
                  <StatusBadge status={a.status} />
                </td>
                <td>
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-16 overflow-hidden rounded-full bg-slate-800">
                      <div
                        className={`h-full rounded-full ${
                          a.risk_score >= 0.7
                            ? "bg-rose-500"
                            : a.risk_score >= 0.4
                            ? "bg-amber-500"
                            : "bg-emerald-500"
                        }`}
                        style={{ width: `${a.risk_score * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-slate-400">{a.risk_score.toFixed(2)}</span>
                  </div>
                </td>
                <td className="text-slate-300">{a.gate_confidence.toFixed(2)}</td>
                <td>
                  <IssuerBadge status={a.issuer_status} />
                </td>
                <td className="text-right">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-bold ${
                      a.open_flags > 0
                        ? "bg-rose-500/15 text-rose-300"
                        : "bg-slate-700/40 text-slate-500"
                    }`}
                  >
                    {a.open_flags}
                  </span>
                </td>
                {canUpload && (
                  <td className="whitespace-nowrap text-right">
                    {confirmId === a.id ? (
                      <span className="inline-flex items-center gap-1">
                        {a.scenario && (
                          <span
                            className="text-[10px] font-bold uppercase text-fuchsia-300"
                            title="This is one of the 5 built-in demo scenarios - deleting it removes it from the demo"
                          >
                            demo {a.scenario}
                          </span>
                        )}
                        <button
                          className="btn-danger !px-2 !py-1 !text-xs"
                          disabled={busyId === a.id}
                          onClick={() => deleteApp(a)}
                        >
                          {busyId === a.id ? "Deleting…" : "Yes, delete"}
                        </button>
                        <button
                          className="btn-ghost !px-2 !py-1 !text-xs"
                          onClick={() => setConfirmId(null)}
                        >
                          Keep
                        </button>
                      </span>
                    ) : (
                      <button
                        className="rounded-lg border border-slate-700 p-1.5 text-slate-500 transition hover:border-rose-500/60 hover:bg-rose-500/10 hover:text-rose-300"
                        title={`Delete ${a.ref_no} (officer only)`}
                        aria-label={`Delete ${a.ref_no}`}
                        onClick={() => setConfirmId(a.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
            {apps.length === 0 && (
              <tr>
                <td
                  colSpan={canUpload ? 9 : 8}
                  className="py-8 text-center text-slate-500"
                >
                  No applications match the filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  tone,
  glow,
}: {
  icon: JSX.Element;
  label: string;
  value: number | string;
  tone: string;
  glow?: string;
}) {
  return (
    <div className="card flex items-center gap-4">
      <div
        className={`rounded-xl bg-gradient-to-br p-3 ring-1 ${
          glow ?? "from-slate-700/60 to-slate-800/40 ring-slate-700/60"
        }`}
      >
        {icon}
      </div>
      <div>
        <div className={`text-3xl font-bold tabular-nums ${tone}`}>{value}</div>
        <div className="text-xs text-slate-400">{label}</div>
      </div>
    </div>
  );
}
