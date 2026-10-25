import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Inbox, ArrowRight, MapPin } from "lucide-react";
import { api } from "../api/client";
import { MockBanner } from "../components/Layout";
import StatusBadge, { SeverityBadge } from "../components/StatusBadge";
import type { ReviewQueueItem } from "../types";

export default function ReviewQueue() {
  const [queue, setQueue] = useState<ReviewQueueItem[]>([]);

  useEffect(() => {
    api.get<ReviewQueueItem[]>("/reviews/queue").then((r) => setQueue(r.data));
  }, []);

  return (
    <div className="space-y-4">
      <MockBanner />
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <Inbox className="h-6 w-6 text-amber-400" /> Manual Review Queue
        </h1>
        <p className="text-sm text-slate-400">
          Applications the Evidence Gate abstained on, ranked by risk. Officers
          and reviewers decide - every action is written to the audit log.
        </p>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        {queue.map(({ application: a, open_flags, decided_flags }) => (
          <div key={a.id} className="card">
            <div className="flex items-start gap-3">
              <div className="mr-auto">
                <Link
                  to={`/applications/${a.id}`}
                  className="font-semibold text-indigo-300 hover:underline"
                >
                  {a.institution_name}
                </Link>
                <div className="text-xs text-slate-500">
                  <span className="font-mono">{a.ref_no}</span> · {a.category} · issuer{" "}
                  {a.issuer_status || "n/a"}
                </div>
              </div>
              <StatusBadge status={a.status} />
            </div>

            <div className="mt-3 flex items-center gap-3 text-xs">
              <span className="text-slate-400">
                risk <b className="text-slate-200">{a.risk_score.toFixed(2)}</b>
              </span>
              <span className="text-slate-400">
                gate conf <b className="text-slate-200">{a.gate_confidence.toFixed(2)}</b>
              </span>
              <span className="text-slate-400">
                decided flags <b className="text-slate-200">{decided_flags}</b>
              </span>
            </div>

            {a.gate_reasons?.length > 0 && (
              <ul className="mt-2 space-y-1">
                {a.gate_reasons.slice(0, 2).map((r, i) => (
                  <li key={i} className="text-xs text-slate-400">
                    <span className="rounded bg-slate-800 px-1 font-mono text-[10px] text-indigo-300">
                      {r.rule_id}
                    </span>{" "}
                    {r.message.slice(0, 130)}
                    {r.message.length > 130 ? "…" : ""}
                  </li>
                ))}
              </ul>
            )}

            <div className="mt-3 space-y-1">
              {open_flags.map((f) => (
                <div
                  key={f.id}
                  className="flex items-center gap-2 rounded border border-slate-800 bg-slate-950/40 px-2 py-1.5 text-xs"
                >
                  <SeverityBadge severity={f.severity} />
                  <span className="min-w-0 flex-1 truncate text-slate-300">{f.title}</span>
                  <span className="font-mono text-[10px] text-slate-500">{f.rule_id}</span>
                  {f.has_location && (
                    <span className="flex items-center gap-1 text-[10px] text-sky-300">
                      <MapPin className="h-3 w-3" /> located
                    </span>
                  )}
                </div>
              ))}
              {open_flags.length === 0 && (
                <p className="text-xs text-slate-500">
                  No open flags left - awaiting final disposition.
                </p>
              )}
            </div>

            <Link to={`/applications/${a.id}`} className="btn-primary mt-3 !py-1.5 text-xs">
              Review application <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        ))}
        {queue.length === 0 && (
          <div className="card col-span-full py-10 text-center text-slate-500">
            The review queue is empty - the gate vouched for everything, or all
            flags have been decided.
          </div>
        )}
      </div>
    </div>
  );
}
