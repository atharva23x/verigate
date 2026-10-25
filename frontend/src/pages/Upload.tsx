import { Fragment, FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  UploadCloud,
  FileUp,
  Plus,
  Trash2,
  Rocket,
  ArrowRight,
  ShieldOff,
  ScanText,
  ListChecks,
  Globe,
  Fingerprint,
  ShieldCheck,
  UserCheck,
  Sparkles,
  FileText,
  ChevronRight,
  CircleCheck,
  Loader2,
} from "lucide-react";
import { api, docTypeLabels, stepLabels } from "../api/client";
import ProgressSteps from "../components/ProgressSteps";
import { MockBanner } from "../components/Layout";
import { useAuth } from "../auth/AuthContext";
import type { AppConfig, Progress } from "../types";

const DOC_TYPES = Object.keys(docTypeLabels);
const CATEGORIES = ["Engineering", "Management", "Pharmacy"] as const;

const HINTS: [string, string][] = [
  ["fire", "FIRE_SAFETY_NOC"],
  ["stability", "BUILDING_STABILITY_CERT"],
  ["premises", "PREMISES_NOC"],
  ["pharmacy|pci", "PHARMACY_REG_CERT"],
  ["lease", "LEASE_DEED"],
  ["land", "LAND_OWNERSHIP_DEED"],
  ["affidavit", "AFFIDAVIT_UNDERTAKING"],
  ["previous|approval", "PREV_EOA_LETTER"],
  ["eoa|form", "EOA_FORM"],
];

/** The 6 stages the aside promises — keep in sync with the real pipeline. */
const PIPELINE: { icon: typeof ScanText; title: string; desc: string; tone: string }[] = [
  {
    icon: ScanText,
    title: "1 · OCR the documents",
    desc: "Reads every field with its position and confidence.",
    tone: "bg-indigo-500/15 text-indigo-300 ring-1 ring-indigo-500/30",
  },
  {
    icon: ListChecks,
    title: "2 · APH 2024-27 checklist",
    desc: "Missing, expired or invalid documents get flagged.",
    tone: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
  },
  {
    icon: Globe,
    title: "3 · Ask the issuer portal",
    desc: "Cross-checks each doc number with the issuing authority.",
    tone: "bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30",
  },
  {
    icon: Fingerprint,
    title: "4 · Tamper + duplicate + ML",
    desc: "ELA heatmap, pHash copy check, XGBoost consistency.",
    tone: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30",
  },
  {
    icon: ShieldCheck,
    title: "5 · Evidence Gate",
    desc: "VERIFIED only when every check passes — otherwise it abstains.",
    tone: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  },
  {
    icon: UserCheck,
    title: "6 · Officer decides",
    desc: "AI advises; a human approves, rejects or requests info.",
    tone: "bg-violet-500/15 text-violet-300 ring-1 ring-violet-500/30",
  },
];

const RIBBON = [
  "OCR",
  "APH 2024-27 rules",
  "Issuer portals",
  "Tamper + duplicates",
  "Evidence Gate",
];

interface PickedFile {
  file: File;
  docType: string;
}

function SectionTitle({
  n,
  title,
  hint,
}: {
  n: string;
  title: string;
  hint?: string;
}) {
  return (
    <div className="mb-4 flex items-center gap-2.5 border-b border-slate-800/80 pb-2.5">
      <span className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-indigo-500/40 to-sky-500/25 text-[11px] font-bold text-indigo-200 ring-1 ring-indigo-500/30">
        {n}
      </span>
      <h2 className="text-sm font-semibold tracking-wide">{title}</h2>
      {hint && <span className="ml-auto text-[11px] text-slate-500">{hint}</span>}
    </div>
  );
}

export default function Upload() {
  const { user, canUpload } = useAuth();
  const [form, setForm] = useState({
    institution_name: "",
    category: "Engineering",
    aicte_id: "",
    address: "",
    approved_intake: 60,
  });
  const [files, setFiles] = useState<PickedFile[]>([]);
  const [phase, setPhase] = useState<"form" | "running" | "done">("form");
  const [appId, setAppId] = useState<number | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);

  useEffect(() => {
    api
      .get<AppConfig>("/config")
      .then((r) => setConfig(r.data))
      .catch(() => {});
  }, []);

  function onPick(list: FileList | null) {
    if (!list) return;
    const next: PickedFile[] = Array.from(list).map((file) => ({
      file,
      docType: autoDocType(file.name),
    }));
    setFiles((prev) => [...prev, ...next]);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.institution_name.trim()) return setError("Institution name is required");
    if (files.length === 0) return setError("Upload at least one document");
    setError("");
    setPhase("running");
    try {
      // 1. create the application
      const { data: app } = await api.post<{ id: number }>("/applications", form);
      setAppId(app.id);

      // 2. upload documents (multipart)
      const fd = new FormData();
      files.forEach((f) => fd.append("files", f.file));
      fd.append("doc_types", JSON.stringify(files.map((f) => f.docType)));
      await api.post(`/applications/${app.id}/documents`, fd);

      // 3. kick off validation, then poll live progress
      await api.post(`/applications/${app.id}/validate`);
      const poll = setInterval(async () => {
        try {
          const { data } = await api.get(`/applications/${app.id}`);
          setProgress(data.progress_json);
          if (data.progress_json?.status === "DONE" || data.status !== "PROCESSING") {
            clearInterval(poll);
            setPhase("done");
          }
        } catch {
          clearInterval(poll);
        }
      }, 700);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Upload failed";
      setError(msg);
      setPhase("form");
    }
  }

  function resetForAnother() {
    setPhase("form");
    setFiles([]);
    setAppId(null);
    setProgress(null);
    setError("");
  }

  if (phase === "done" && appId) {
    return (
      <div className="mx-auto max-w-2xl space-y-5 text-center">
        <div className="flex justify-center">
          <span className="relative">
            <span className="absolute -inset-3 rounded-full bg-gradient-to-br from-emerald-500/40 to-sky-500/25 blur-xl" />
            <CircleCheck className="relative h-16 w-16 text-emerald-400 drop-shadow-[0_0_16px_var(--glow-success)]" />
          </span>
        </div>
        <div>
          <h1 className="gradient-text text-3xl font-bold tracking-tight">
            Validation complete
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            The Evidence Gate has made its call (or abstained). Every signal below is
            explainable — open the file to see the evidence.
          </p>
        </div>
        <div className="card text-left">
          <ProgressSteps progress={progress!} />
        </div>
        <div className="flex justify-center gap-3">
          <Link to={`/applications/${appId}`} className="btn-primary">
            Open application <ArrowRight className="h-4 w-4" />
          </Link>
          <button className="btn-ghost" onClick={resetForAnother}>
            <UploadCloud className="h-4 w-4" /> Upload another
          </button>
        </div>
      </div>
    );
  }

  if (!canUpload) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <h1 className="text-2xl font-bold">Upload</h1>
        <div className="card flex items-start gap-3 border-amber-500/30 bg-amber-500/5">
          <ShieldOff className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
          <div>
            <div className="font-semibold text-amber-300">Read-only role</div>
            <p className="mt-1 text-sm leading-relaxed text-slate-400">
              Signed in as <b className="text-slate-300">{user?.full_name}</b> (
              {user?.role}). Only <b className="text-slate-300">officers</b> can create
              and upload applications. You can still browse every application, its
              evidence, flags and the audit log.
            </p>
          </div>
        </div>
        <Link to="/" className="btn-ghost">
          <ArrowRight className="h-4 w-4" /> Back to dashboard
        </Link>
      </div>
    );
  }

  if (phase === "running") {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <div className="card border-indigo-500/40 bg-gradient-to-b from-indigo-500/10 to-indigo-500/5">
          <div className="mb-4 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-sky-500 shadow-md shadow-indigo-950">
              <Loader2 className="h-5 w-5 animate-spin text-white" />
            </span>
            <div>
              <h1 className="text-lg font-bold">
                Running the pipeline
                {appId ? ` for application #${appId}` : ""}…
              </h1>
              <p className="text-xs text-slate-400">
                OCR → APH rules → issuer portals → tamper &amp; duplicates → Evidence Gate
              </p>
            </div>
          </div>
          <ProgressSteps
            progress={
              progress ?? { status: "RUNNING", current_step: null, steps: [], error: null }
            }
          />
          {!progress?.steps?.length && (
            <div className="space-y-1.5">
              {Object.values(stepLabels).map((label, i) => (
                <div
                  key={label}
                  className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-sm ${
                    i === 0
                      ? "border-indigo-500/50 bg-indigo-500/10"
                      : "border-slate-800 bg-slate-900/60"
                  }`}
                >
                  <Loader2
                    className={`h-4 w-4 ${i === 0 ? "animate-spin text-indigo-400" : "text-slate-600"}`}
                  />
                  <span className={i === 0 ? "font-medium text-slate-200" : "text-slate-500"}>
                    {label}
                  </span>
                  <span className="ml-auto text-xs text-slate-600">
                    {i === 0 ? "starting…" : "queued"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      {/* ---------------------------------------------------------- header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="relative">
            <span className="absolute -inset-1.5 rounded-2xl bg-gradient-to-br from-indigo-500/40 to-sky-500/30 blur-md" />
            <span className="relative flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-sky-500 shadow-lg shadow-indigo-950">
              <UploadCloud className="h-6 w-6 text-white" />
            </span>
          </span>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">New EoA application</h1>
            <p className="text-sm text-slate-400">
              Drop in the institution's documents — VeriGate reads, checks and gates them
              end to end.
            </p>
          </div>
        </div>
        <MockBanner />
      </div>

      {/* pipeline ribbon */}
      <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
        {RIBBON.map((step, i) => (
          <Fragment key={step}>
            {i > 0 && <ChevronRight className="h-3 w-3 text-slate-600" />}
            <span className="rounded-full border border-slate-700/70 bg-slate-900/70 px-2.5 py-1 text-slate-300">
              {step}
            </span>
          </Fragment>
        ))}
        <ChevronRight className="h-3 w-3 text-slate-600" />
        <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 font-semibold text-emerald-300">
          human decides
        </span>
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_310px]">
        {/* --------------------------------------------------------- form */}
        <form onSubmit={onSubmit} className="card space-y-6">
          <section>
            <SectionTitle n="1" title="Institution details" hint="as declared on the EoA form" />
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="label">Institution name *</label>
                <input
                  className="input"
                  placeholder="e.g. Sri Vidya Institute of Technology"
                  value={form.institution_name}
                  onChange={(e) => setForm({ ...form, institution_name: e.target.value })}
                />
              </div>

              <div className="sm:col-span-2">
                <label className="label">Category</label>
                <div className="flex flex-wrap gap-2">
                  {CATEGORIES.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setForm({ ...form, category: c })}
                      className={`rounded-full px-4 py-1.5 text-xs font-semibold transition ${
                        form.category === c
                          ? "bg-gradient-to-r from-indigo-500 to-sky-500 text-white shadow-md shadow-indigo-950 ring-1 ring-indigo-400/50"
                          : "border border-slate-700 text-slate-300 hover:border-slate-600 hover:bg-slate-800/70"
                      }`}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="label">AICTE ID (if known)</label>
                <input
                  className="input font-mono"
                  placeholder="AICTE-DL2025-01234"
                  value={form.aicte_id}
                  onChange={(e) => setForm({ ...form, aicte_id: e.target.value })}
                />
                <p className="mt-1 text-[11px] leading-snug text-slate-500">
                  Printed on the approval letter — enables the master-record cross-check.
                </p>
              </div>

              <div>
                <label className="label">Approved intake</label>
                <input
                  className="input"
                  type="number"
                  min={0}
                  value={form.approved_intake}
                  onChange={(e) =>
                    setForm({ ...form, approved_intake: Number(e.target.value) })
                  }
                />
                <p className="mt-1 text-[11px] leading-snug text-slate-500">
                  Seats AICTE allows per year (e.g. 60 or 120) — compared with the master
                  record.
                </p>
              </div>

              <div className="sm:col-span-2">
                <label className="label">Address</label>
                <input
                  className="input"
                  placeholder="Locality, city - PIN"
                  value={form.address}
                  onChange={(e) => setForm({ ...form, address: e.target.value })}
                />
              </div>
            </div>
          </section>

          <section>
            <SectionTitle
              n="2"
              title="Documents *"
              hint="doc type auto-detected from the filename"
            />
            <div
              className="group flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-700 bg-slate-950/40 px-6 py-9 text-center transition hover:border-indigo-500/60 hover:bg-indigo-500/5"
              onClick={() => fileInput.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                onPick(e.dataTransfer.files);
              }}
            >
              <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500/30 to-sky-500/20 ring-1 ring-indigo-500/30 transition group-hover:scale-110">
                <FileUp className="h-6 w-6 text-indigo-300" />
              </span>
              <span className="text-sm font-medium text-slate-200">
                Drag &amp; drop the institution's files here
              </span>
              <span className="mt-1 text-xs text-slate-500">
                or click to browse — you can edit each doc type below
              </span>
              <span className="mt-3 flex gap-1.5 text-[10px]">
                {[".pdf", ".png", ".jpg"].map((t) => (
                  <span
                    key={t}
                    className="rounded border border-slate-700/70 bg-slate-900/70 px-1.5 py-0.5 text-slate-400"
                  >
                    {t}
                  </span>
                ))}
              </span>
              <input
                ref={fileInput}
                type="file"
                multiple
                accept=".pdf,.png,.jpg,.jpeg"
                className="hidden"
                onChange={(e) => onPick(e.target.files)}
              />
            </div>

            {files.length > 0 && (
              <div className="mt-3 space-y-2">
                {files.map((f, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-sm transition hover:border-slate-700"
                  >
                    <FileText className="h-4 w-4 shrink-0 text-slate-500" />
                    <span className="min-w-0 flex-1 truncate">{f.file.name}</span>
                    <span className="text-xs text-slate-500">
                      {(f.file.size / 1024).toFixed(0)} KB
                    </span>
                    <select
                      className="input !w-60 !py-1 text-xs"
                      value={f.docType}
                      onChange={(e) => {
                        const next = [...files];
                        next[i] = { ...f, docType: e.target.value };
                        setFiles(next);
                      }}
                    >
                      {DOC_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {docTypeLabels[t]}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="text-slate-500 hover:text-rose-400"
                      onClick={() => setFiles(files.filter((_, j) => j !== i))}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>

          {error && (
            <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
              {error}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3 border-t border-slate-800/80 pt-4">
            <button className="btn-primary">
              <Rocket className="h-4 w-4" />
              Upload &amp; validate
            </button>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => fileInput.current?.click()}
            >
              <Plus className="h-4 w-4" /> Add files
            </button>
            <span className="ml-auto text-[11px] text-slate-500">
              Runs the full pipeline in a few seconds
            </span>
          </div>
        </form>

        {/* --------------------------------------------------------- aside */}
        <aside className="hidden space-y-4 lg:block">
          <div className="card">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <Sparkles className="h-4 w-4 text-indigo-400" /> What happens when you
              validate
            </h3>
            <ol className="space-y-3">
              {PIPELINE.map((s) => (
                <li key={s.title} className="flex gap-2.5">
                  <span
                    className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${s.tone}`}
                  >
                    <s.icon className="h-3.5 w-3.5" />
                  </span>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-slate-200">{s.title}</div>
                    <div className="text-[11px] leading-snug text-slate-500">
                      {s.desc}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
            <div className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-2 text-[11px] leading-relaxed text-emerald-200">
              <b>The Gate only passes on strong evidence</b> — anything weaker abstains
              and lands in the review queue. It never guesses.
            </div>
          </div>

          <div className="card space-y-2 text-[11px] text-slate-400">
            <div className="flex items-center justify-between">
              <span>Mode</span>
              <span className="font-semibold text-slate-300">
                {config?.mock_mode ? "Synthetic demo data" : "Live"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>Gate threshold</span>
              <span className="font-semibold text-slate-300">
                OCR &gt; {config?.ocr_confidence_threshold ?? "–"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>Ruleset</span>
              <span className="font-semibold text-slate-300">APH 2024-27</span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function autoDocType(filename: string): string {
  const low = filename.toLowerCase();
  for (const [pattern, docType] of HINTS) {
    if (new RegExp(pattern).test(low)) return docType;
  }
  return "EOA_FORM";
}
