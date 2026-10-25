import { useEffect, useState } from "react";
import { Download, ScrollText, Search } from "lucide-react";
import { api, downloadFile } from "../api/client";
import { MockBanner } from "../components/Layout";
import type { AuditEntry } from "../types";

const ACTION_TONE: Record<string, string> = {
  LOGIN: "text-sky-300",
  LOGIN_FAILED: "text-rose-300",
  APP_CREATE: "text-indigo-300",
  DOC_UPLOAD: "text-indigo-300",
  VALIDATE_START: "text-slate-300",
  VALIDATE_COMPLETE: "text-emerald-300",
  REVIEW_DECISION: "text-amber-300",
  SEED_START: "text-fuchsia-300",
  SEED_COMPLETE: "text-fuchsia-300",
  FLAGGED: "text-slate-400",
};

export default function AuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [actions, setActions] = useState<string[]>([]);
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  useEffect(() => {
    api.get<string[]>("/audit-log/actions").then((r) => setActions(r.data));
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      api
        .get<{ total: number; entries: AuditEntry[] }>("/audit-log", {
          params: { actor, action, limit, offset },
        })
        .then((r) => {
          setTotal(r.data.total);
          setEntries(r.data.entries);
        });
    }, 200);
    return () => clearTimeout(t);
  }, [actor, action, offset]);

  return (
    <div className="space-y-4">
      <MockBanner />
      <div className="flex flex-wrap items-center gap-3">
        <div className="mr-auto">
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <ScrollText className="h-6 w-6 text-indigo-400" /> Audit Log
          </h1>
          <p className="text-sm text-slate-400">
            Append-only trail of every action: logins, uploads, validations,
            flags and human decisions. {total} entries.
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={() => downloadFile("/audit-log/export", "verigate-audit.csv")}
        >
          <Download className="h-4 w-4" /> Export CSV
        </button>
      </div>

      <div className="card">
        <div className="mb-3 flex flex-wrap gap-3">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-500" />
            <input
              className="input !w-56 !pl-8"
              placeholder="Filter by actor"
              value={actor}
              onChange={(e) => {
                setActor(e.target.value);
                setOffset(0);
              }}
            />
          </div>
          <select
            className="input !w-56"
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All actions</option>
            {actions.map((a) => (
              <option key={a}>{a}</option>
            ))}
          </select>
        </div>

        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-slate-800 text-left uppercase tracking-wide text-slate-500">
              <th className="py-2 pr-3">Timestamp (UTC)</th>
              <th className="pr-3">Actor</th>
              <th className="pr-3">Role</th>
              <th className="pr-3">Action</th>
              <th className="pr-3">Entity</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-b border-slate-800/50 align-top">
                <td className="whitespace-nowrap py-2 pr-3 font-mono text-slate-400">
                  {e.ts.replace("T", " ").slice(0, 19)}
                </td>
                <td className="pr-3">
                  <div className="font-medium text-slate-200">
                    {(e.detail as { actor_name?: string } | null)?.actor_name ??
                      e.actor}
                  </div>
                  {(
                    e.detail as { actor_name?: string } | null
                  )?.actor_name && (
                    <div className="font-mono text-[10px] text-slate-500">
                      {e.actor}
                    </div>
                  )}
                </td>
                <td className="pr-3 text-slate-400">{e.role}</td>
                <td className={`pr-3 font-semibold ${ACTION_TONE[e.action] ?? "text-slate-300"}`}>
                  {e.action}
                </td>
                <td className="pr-3 text-slate-400">
                  {e.entity_type}
                  {e.entity_id ? ` #${e.entity_id}` : ""}
                </td>
                <td className="max-w-[420px]">
                  <details>
                    <summary className="cursor-pointer text-slate-500 hover:text-slate-300">
                      {Object.keys(e.detail ?? {}).length} keys
                    </summary>
                    <pre className="mt-1 max-h-40 overflow-auto rounded bg-slate-950/70 p-2 font-mono text-[10px] text-slate-400">
                      {JSON.stringify(e.detail, null, 1)}
                    </pre>
                  </details>
                </td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500">
                  No audit entries match the filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>

        <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
          <span>
            showing {entries.length} of {total}
          </span>
          <div className="flex gap-2">
            <button
              className="btn-ghost !py-1 text-xs"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
            >
              Previous
            </button>
            <button
              className="btn-ghost !py-1 text-xs"
              disabled={offset + limit >= total}
              onClick={() => setOffset(offset + limit)}
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
