import { CheckCircle2, CircleDashed, Loader2, XCircle } from "lucide-react";
import type { Progress } from "../types";
import { stepLabels } from "../api/client";

export default function ProgressSteps({ progress }: { progress: Progress }) {
  if (!progress?.steps?.length) return null;
  return (
    <div className="space-y-1.5">
      {progress.steps.map((s) => (
        <div
          key={s.name}
          className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-sm transition ${
            s.status === "RUNNING"
              ? "border-indigo-500/50 bg-indigo-500/10"
              : s.status === "ERROR"
              ? "border-rose-500/50 bg-rose-500/10"
              : "border-slate-800 bg-slate-900/60"
          }`}
        >
          {s.status === "DONE" && <CheckCircle2 className="h-4 w-4 text-emerald-400" />}
          {s.status === "RUNNING" && (
            <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
          )}
          {s.status === "PENDING" && (
            <CircleDashed className="h-4 w-4 text-slate-600" />
          )}
          {s.status === "ERROR" && <XCircle className="h-4 w-4 text-rose-400" />}
          <span
            className={
              s.status === "PENDING" ? "text-slate-500" : "font-medium text-slate-200"
            }
          >
            {stepLabels[s.name] ?? s.name}
          </span>
          <span className="ml-auto text-xs text-slate-500">
            {s.status === "DONE" && s.ms !== undefined ? `${s.ms} ms` : s.status}
          </span>
        </div>
      ))}
      {progress.error && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
          {progress.error}
        </div>
      )}
    </div>
  );
}
