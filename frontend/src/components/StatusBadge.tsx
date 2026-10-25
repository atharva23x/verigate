import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Eye,
  ThumbsUp,
  ThumbsDown,
  Upload,
} from "lucide-react";
import type { AppStatus } from "../types";

const STYLES: Record<AppStatus, { cls: string; icon: typeof Clock; label: string }> = {
  VERIFIED: {
    cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    icon: CheckCircle2,
    label: "Verified",
  },
  INSUFFICIENT_EVIDENCE: {
    cls: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    icon: AlertTriangle,
    label: "Insufficient evidence",
  },
  IN_REVIEW: {
    cls: "bg-sky-500/15 text-sky-300 border-sky-500/30",
    icon: Eye,
    label: "In review",
  },
  APPROVED: {
    cls: "bg-emerald-600/20 text-emerald-200 border-emerald-600/40",
    icon: ThumbsUp,
    label: "Approved (human)",
  },
  REJECTED: {
    cls: "bg-rose-600/20 text-rose-200 border-rose-600/40",
    icon: ThumbsDown,
    label: "Rejected (human)",
  },
  PROCESSING: {
    cls: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
    icon: Clock,
    label: "Processing",
  },
  UPLOADED: {
    cls: "bg-slate-500/15 text-slate-300 border-slate-500/30",
    icon: Upload,
    label: "Awaiting validation",
  },
};

export default function StatusBadge({ status }: { status: AppStatus }) {
  const s = STYLES[status] ?? STYLES.UPLOADED;
  const Icon = s.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${s.cls}`}
    >
      <Icon className="h-3.5 w-3.5" />
      {s.label}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, string> = {
    CRITICAL: "bg-rose-500/15 text-rose-300 border-rose-500/40",
    WARN: "bg-amber-500/15 text-amber-300 border-amber-500/40",
    INFO: "bg-slate-500/15 text-slate-300 border-slate-500/40",
  };
  return (
    <span
      className={`rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
        map[severity] ?? map.INFO
      }`}
    >
      {severity}
    </span>
  );
}

export function IssuerBadge({ status }: { status: string }) {
  if (!status || status === "NOT_REQUIRED")
    return <span className="text-xs text-slate-500">n/a</span>;
  const map: Record<string, string> = {
    VERIFIED: "bg-emerald-500/15 text-emerald-300",
    EXPIRED: "bg-orange-500/15 text-orange-300",
    INVALID: "bg-rose-500/15 text-rose-300",
    NOT_FOUND: "bg-rose-500/15 text-rose-300",
    SOURCE_UNAVAILABLE: "bg-sky-500/15 text-sky-300",
    MANUAL_REVIEW: "bg-amber-500/15 text-amber-300",
  };
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
        map[status] ?? "bg-slate-600/20 text-slate-300"
      }`}
      title={status}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
