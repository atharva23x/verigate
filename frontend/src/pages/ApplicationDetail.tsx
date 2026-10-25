import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  AlertTriangle,
  CheckCircle2,
  FileWarning,
  FileDown,
  Flame,
  Eye,
  Scan,
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
  Send,
  Loader2,
  Hash,
  Trash2,
  CopyCheck,
} from "lucide-react";
import { api, downloadFile, fetchImageURL, docTypeLabels } from "../api/client";
import BBoxOverlay, { OverlayBox } from "../components/BBoxOverlay";
import ProgressSteps from "../components/ProgressSteps";
import ScoreBar from "../components/ScoreBar";
import StatusBadge, { IssuerBadge, SeverityBadge } from "../components/StatusBadge";
import { useAuth } from "../auth/AuthContext";
import type {
  AppConfig,
  ApplicationDetail as AppDetail,
  ConsistencyView,
  DuplicatesView,
  FlagOut,
} from "../types";

const KIND_ICONS: Record<string, typeof Flame> = {
  TAMPER: Flame,
  DUPLICATE: FileWarning,
  RULE: AlertTriangle,
  ISSUER: Scan,
  OCR: Eye,
  EXTRACTION: Hash,
  CONSISTENCY: AlertTriangle,
};

const FEATURE_LABELS: Record<string, string> = {
  name_sim: "institution name",
  aicte_id_match: "AICTE ID",
  category_match: "category",
  address_sim: "address",
  intake_match: "approved intake",
  issue_plausible: "issue date validity",
  expiry_aligned: "expiry alignment",
  issuer_ok_ratio: "issuer checks",
  ocr_conf: "OCR confidence",
  tamper_ok: "tamper clean",
  not_duplicate: "not a duplicate",
};

export default function ApplicationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { canReview, canUpload } = useAuth();
  const [app, setApp] = useState<AppDetail | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [activeDocId, setActiveDocId] = useState<number | null>(null);
  const [activeFlagId, setActiveFlagId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [pageUrl, setPageUrl] = useState<string | null>(null);
  const [elaUrl, setElaUrl] = useState<string | null>(null);
  const [showEla, setShowEla] = useState(false);
  const [showFields, setShowFields] = useState(true);
  const [comments, setComments] = useState<Record<number, string>>({});
  const [busyFlag, setBusyFlag] = useState<number | null>(null);
  const [consistency, setConsistency] = useState<ConsistencyView | null>(null);
  const [duplicates, setDuplicates] = useState<DuplicatesView | null>(null);
  const [dupImages, setDupImages] = useState<Record<string, string>>({});
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState("");
  const viewerRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    const { data } = await api.get<AppDetail>(`/applications/${id}`);
    setApp(data);
    return data;
  }, [id]);

  useEffect(() => {
    load();
    api.get<AppConfig>("/config").then((r) => setConfig(r.data)).catch(() => {});
  }, [load]);

  // Live progress while the pipeline runs
  useEffect(() => {
    if (app?.status !== "PROCESSING") return;
    const t = setInterval(() => load(), 1000);
    return () => clearInterval(t);
  }, [app?.status, load]);

  // Consistency + duplicate insights (re-fetched whenever a run finishes)
  useEffect(() => {
    if (!app || app.status === "PROCESSING") return;
    let cancelled = false;
    api
      .get<ConsistencyView>(`/applications/${app.id}/consistency`)
      .then((r) => !cancelled && setConsistency(r.data))
      .catch(() => !cancelled && setConsistency(null));
    api
      .get<DuplicatesView>(`/applications/${app.id}/duplicates`)
      .then((r) => !cancelled && setDuplicates(r.data))
      .catch(() => !cancelled && setDuplicates(null));
    return () => {
      cancelled = true;
    };
  }, [app?.id, app?.status]);

  // Fetch the page-1 images of both copies of each duplicate pair (authed)
  useEffect(() => {
    if (!duplicates?.pairs.length) {
      setDupImages({});
      return;
    }
    let cancelled = false;
    const urls: Record<string, string> = {};
    const tasks = duplicates.pairs.flatMap((p, i) => [
      fetchImageURL(
        `/applications/${p.document.application_id}/documents/${p.document.id}/pages/${p.page}.png`
      )
        .then((u) => (urls[`doc-${i}`] = u))
        .catch(() => {}),
      fetchImageURL(
        `/applications/${p.donor.application_id}/documents/${p.donor.id}/pages/${p.page}.png`
      )
        .then((u) => (urls[`donor-${i}`] = u))
        .catch(() => {}),
    ]);
    Promise.all(tasks).then(() => {
      if (!cancelled) setDupImages(urls);
    });
    return () => {
      cancelled = true;
    };
  }, [duplicates]);

  const activeDoc = useMemo(
    () =>
      app?.documents.find((d) => d.id === activeDocId) ??
      app?.documents[0] ??
      null,
    [app, activeDocId]
  );

  // Rendered page image (fetched with auth header -> object URL)
  useEffect(() => {
    if (!activeDoc) return;
    let cancelled = false;
    setPageUrl(null);
    fetchImageURL(`/applications/${id}/documents/${activeDoc.id}/pages/${page}.png`)
      .then((url) => !cancelled && setPageUrl(url))
      .catch(() => !cancelled && setPageUrl(null));
    return () => {
      cancelled = true;
    };
  }, [id, activeDoc, page]);

  // ELA heatmap for the active document
  useEffect(() => {
    let cancelled = false;
    if (!showEla || !activeDoc) {
      setElaUrl(null);
      return;
    }
    fetchImageURL(`/applications/${id}/documents/${activeDoc.id}/ela.png`)
      .then((url) => !cancelled && setElaUrl(url))
      .catch(() => !cancelled && setElaUrl(null));
    return () => {
      cancelled = true;
    };
  }, [showEla, activeDoc, id]);

  /** Click a flag -> jump to its document/page and pulse the box. */
  function focusFlag(flag: FlagOut) {
    setActiveFlagId(flag.id);
    if (flag.document_id) setActiveDocId(flag.document_id);
    setPage(flag.page_no ?? 1);
    viewerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const overlayBoxes: OverlayBox[] = useMemo(() => {
    const boxes: OverlayBox[] = [];
    if (!activeDoc) return boxes;
    // Flags with a located region on the visible page
    for (const f of app?.flags ?? []) {
      if (f.document_id !== activeDoc.id || !f.bbox || (f.page_no ?? 1) !== page)
        continue;
      boxes.push({
        id: `flag-${f.id}`,
        bbox: f.bbox,
        tone: f.severity === "CRITICAL" ? "red" : "orange",
        label: f.rule_id,
        active: f.id === activeFlagId,
      });
    }
    // Extracted-field highlights (neutral blue)
    if (showFields) {
      for (const [name, field] of Object.entries(activeDoc.extracted_json ?? {})) {
        if (!field.bbox || (field.page_no ?? 1) !== page) continue;
        boxes.push({
          id: `field-${name}`,
          bbox: field.bbox as [number, number, number, number],
          tone: "blue",
          label: name.replace(/_/g, " "),
        });
      }
    }
    return boxes;
  }, [app, activeDoc, activeFlagId, page, showFields]);

  async function decide(flagId: number, decision: "APPROVE" | "REJECT" | "REQUEST_INFO") {
    setBusyFlag(flagId);
    try {
      await api.post(`/reviews/${flagId}/decision`, {
        decision,
        comment: comments[flagId] ?? "",
      });
      await load();
    } finally {
      setBusyFlag(null);
    }
  }

  async function downloadReport() {
    if (!app) return;
    setReportBusy(true);
    setReportError("");
    try {
      await downloadFile(
        `/applications/${app.id}/report`,
        `VeriGate_${app.ref_no.replace(/\//g, "-")}_report.pdf`
      );
    } catch {
      setReportError("Report download failed - try again.");
    } finally {
      setReportBusy(false);
    }
  }

  async function deleteApp() {
    if (!app) return;
    setDeleting(true);
    setDeleteError("");
    try {
      await api.delete(`/applications/${app.id}`);
      navigate("/", {
        state: {
          notice: {
            tone: "ok",
            text: `${app.ref_no} (${app.institution_name}) deleted`,
          },
        },
      });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Delete failed";
      setDeleteError(msg);
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  if (!app)
    return (
      <div className="flex items-center gap-2 text-slate-400">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading application…
      </div>
    );

  const verified = app.status === "VERIFIED";
  const processing = app.status === "PROCESSING";

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/" className="btn-ghost !px-2.5">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="mr-auto">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold">{app.institution_name}</h1>
            {app.scenario && (
              <span className="rounded bg-fuchsia-600/30 px-1.5 py-0.5 text-[10px] font-bold text-fuchsia-300">
                DEMO SCENARIO {app.scenario}
              </span>
            )}
          </div>
          <div className="text-xs text-slate-400">
            <span className="font-mono">{app.ref_no}</span> · {app.category} · AICTE ID{" "}
            <span className="font-mono">{app.aicte_id || "—"}</span> · intake{" "}
            {app.approved_intake} · created by {app.created_by}
          </div>
        </div>
        <StatusBadge status={app.status} />
        <IssuerBadge status={app.issuer_status} />
        <button
          className="btn-ghost !px-2.5 !py-1.5 !text-xs"
          title="Download the verification report as a PDF (verdict, signals, flags, checklist, sign-off)"
          disabled={reportBusy || processing}
          onClick={downloadReport}
          aria-label="Download verification report"
        >
          {reportBusy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <FileDown className="h-4 w-4" />
          )}
          Report
        </button>
        {canUpload &&
          (confirmDelete ? (
            <span className="flex items-center gap-2">
              <button
                className="btn-danger !px-2.5 !py-1.5 !text-xs"
                disabled={deleting}
                onClick={deleteApp}
              >
                {deleting ? "Deleting…" : "Yes, delete"}
              </button>
              <button
                className="btn-ghost !px-2.5 !py-1.5 !text-xs"
                disabled={deleting}
                onClick={() => {
                  setConfirmDelete(false);
                  setDeleteError("");
                }}
              >
                Keep
              </button>
            </span>
          ) : (
            <button
              className="btn-ghost !px-2.5 !py-1.5 !text-xs hover:!border-rose-500/60 hover:!text-rose-300"
              title="Delete this application (officer only)"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 className="h-4 w-4" /> Delete
            </button>
          ))}
      </div>

      {deleteError && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          {deleteError}
        </div>
      )}

      {reportError && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          {reportError}
        </div>
      )}

      {/* Plain-English orientation for first-time viewers */}
      <div className="rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2 text-xs leading-relaxed text-slate-400">
        <b className="text-slate-300">What you're looking at:</b>{" "}
        <span className="text-slate-300">Left</span> — the uploaded document with
        highlights (<span className="text-rose-300">red = critical problem</span>,{" "}
        <span className="text-amber-300">orange = warning</span>,{" "}
        <span className="text-sky-300">blue = a field the machine read</span>).{" "}
        <span className="text-slate-300">Right</span> — the Evidence Gate verdict
        and <i>why</i>, the confidence scores, the APH checklist, and the list of
        explainable flags. Click{" "}
        <i className="text-indigo-300">show on document</i> on any flag to jump to
        the highlighted spot. Nothing here is a final decision — officers decide.
      </div>

      {processing && app.progress_json?.steps?.length > 0 && (
        <div className="card">
          <h2 className="mb-2 font-semibold">Pipeline running…</h2>
          <ProgressSteps progress={app.progress_json} />
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_460px]">
        {/* ------------------------------------------------ document viewer */}
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="label !mb-0 mr-2">Document viewer</span>
            {app.documents.map((d) => (
              <button
                key={d.id}
                onClick={() => {
                  setActiveDocId(d.id);
                  setPage(1);
                  setActiveFlagId(null);
                }}
                className={`rounded-lg border px-2.5 py-1 text-xs font-medium transition ${
                  activeDoc?.id === d.id
                    ? "border-indigo-500 bg-indigo-600/20 text-indigo-200"
                    : "border-slate-700 text-slate-400 hover:bg-slate-800"
                }`}
                title={d.filename}
              >
                {docTypeLabels[d.doc_type] ?? d.doc_type}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs">
            <label className="flex cursor-pointer items-center gap-1.5 text-slate-300">
              <input
                type="checkbox"
                checked={showFields}
                onChange={(e) => setShowFields(e.target.checked)}
                className="accent-sky-500"
              />
              Extracted fields
            </label>
            <label className="flex cursor-pointer items-center gap-1.5 text-slate-300">
              <input
                type="checkbox"
                checked={showEla}
                onChange={(e) => setShowEla(e.target.checked)}
                className="accent-rose-500"
              />
              ELA heatmap
            </label>
            <span className="text-slate-500">
              page {page}/{activeDoc?.page_count ?? 1}
              {activeDoc && ` · OCR ${(activeDoc.ocr_confidence ?? 0).toFixed(2)} (${activeDoc.ocr_engine})`}
            </span>
            <div className="ml-auto flex items-center gap-2">
              <span className="h-3 w-3 rounded-sm border-2 border-rose-500 bg-rose-500/20" />
              <span className="text-slate-500">critical</span>
              <span className="h-3 w-3 rounded-sm border-2 border-amber-400 bg-amber-400/20" />
              <span className="text-slate-500">warning</span>
              <span className="h-3 w-3 rounded-sm border-2 border-sky-400 bg-sky-400/20" />
              <span className="text-slate-500">field</span>
            </div>
          </div>

          <div ref={viewerRef} className="card !p-3">
            <div className="relative mx-auto max-w-[760px]">
              {pageUrl ? (
                <>
                  <img src={pageUrl} alt="document page" className="w-full rounded" />
                  <BBoxOverlay boxes={overlayBoxes} />
                  {showEla && elaUrl && (
                    <img
                      src={elaUrl}
                      alt="ELA heatmap"
                      className="absolute inset-0 w-full rounded opacity-70 mix-blend-screen"
                    />
                  )}
                  {!pageUrl && null}
                </>
              ) : (
                <div className="flex h-64 items-center justify-center text-slate-500">
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Rendering page…
                </div>
              )}
            </div>
            {(activeDoc?.page_count ?? 1) > 1 && (
              <div className="mt-2 flex justify-center gap-1">
                {Array.from({ length: activeDoc!.page_count }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={`rounded px-2 py-1 text-xs ${
                      p === page ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* OCR text + extracted fields */}
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="card max-h-72 overflow-auto">
              <div className="label">OCR text ({activeDoc?.ocr_engine ?? "–"})</div>
              <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-slate-300">
                {activeDoc?.ocr_text || "—"}
              </pre>
            </div>
            <div className="card max-h-72 overflow-auto">
              <div className="label">Extracted fields (click to highlight)</div>
              <table className="w-full text-xs">
                <tbody>
                  {Object.entries(activeDoc?.extracted_json ?? {}).map(([name, f]) => (
                    <tr
                      key={name}
                      className="cursor-pointer border-b border-slate-800/60 hover:bg-slate-800/40"
                      onClick={() => {
                        if (f.page_no) setPage(f.page_no);
                      }}
                    >
                      <td className="py-1.5 pr-2 font-medium text-slate-400">
                        {name.replace(/_/g, " ")}
                      </td>
                      <td className="py-1.5 pr-2 font-mono text-slate-200">{f.value || "—"}</td>
                      <td className="w-20 py-1.5">
                        <div className="h-1.5 rounded bg-slate-800">
                          <div
                            className={`h-full rounded ${
                              f.confidence > 0.9 ? "bg-emerald-500" : "bg-amber-500"
                            }`}
                            style={{ width: `${f.confidence * 100}%` }}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                  {Object.keys(activeDoc?.extracted_json ?? {}).length === 0 && (
                    <tr>
                      <td className="py-2 text-slate-500">No fields extracted.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* ----------------------------------------------------- right rail */}
        <div className="space-y-3">
          {/* Gate verdict */}
          <div
            className={`card border-2 ${
              verified
                ? "border-emerald-500/50 bg-gradient-to-b from-emerald-500/10 to-emerald-500/5 shadow-[0_10px_34px_-16px_var(--glow-success)]"
                : "border-amber-500/50 bg-gradient-to-b from-amber-500/10 to-amber-500/5 shadow-[0_10px_34px_-16px_var(--glow-warn)]"
            }`}
          >
            <div className="flex items-center gap-2">
              {verified ? (
                <CheckCircle2 className="h-6 w-6 text-emerald-400 drop-shadow-[0_0_8px_var(--glow-success)]" />
              ) : (
                <AlertTriangle className="h-6 w-6 text-amber-400 drop-shadow-[0_0_8px_var(--glow-warn)]" />
              )}
              <div>
                <div
                  className={`font-bold ${
                    verified ? "text-emerald-200" : "text-amber-200"
                  }`}
                >
                  {verified ? "EVIDENCE GATE: VERIFIED" : "EVIDENCE GATE: INSUFFICIENT EVIDENCE"}
                </div>
                <div className="text-xs text-slate-400">
                  gate confidence {app.gate_confidence.toFixed(2)} · risk{" "}
                  {app.risk_score.toFixed(2)}
                  {app.validated_at && ` · validated ${app.validated_at.replace("T", " ").slice(0, 16)} UTC`}
                </div>
              </div>
            </div>
            {app.gate_reasons?.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {app.gate_reasons.map((r, i) => (
                  <li key={i} className="flex gap-2 text-xs text-slate-300">
                    <span className="mt-0.5 rounded bg-slate-800 px-1 font-mono text-[10px] text-indigo-300">
                      {r.rule_id}
                    </span>
                    <span>{r.message}</span>
                  </li>
                ))}
              </ul>
            )}
            {verified && (
              <p className="mt-2 text-xs text-emerald-300/80">
                All evidence checks passed: OCR confidence above threshold,
                issuer portals confirmed, no tamper/duplicate/consistency issues.
              </p>
            )}
            <p className="mt-2 text-[11px] italic text-slate-500">
              Machine recommendation only - a human officer makes the final call.
            </p>
          </div>

          {/* Scores */}
          <div className="card space-y-3">
            <h3 className="font-semibold">Signals</h3>
            <ScoreBar
              label="OCR confidence"
              value={app.ocr_confidence}
              threshold={config?.ocr_confidence_threshold ?? 0.9}
              hint="Gate requires OCR > 0.90"
            />
            <ScoreBar
              label="Cross-record consistency (XGBoost)"
              value={app.consistency_score}
              threshold={config?.consistency_threshold ?? 0.7}
            />
            <ScoreBar
              label="Tamper score (ELA)"
              value={app.tamper_score}
              threshold={config?.tamper_score_threshold ?? 0.3}
              invert
              hint="Lower is better"
            />
          </div>

          {/* Consistency: submitted vs AICTE master record */}
          {consistency && (
            <div className="card" data-testid="consistency-card">
              <h3 className="mb-1 font-semibold">Submitted vs AICTE master record</h3>
              <p className="mb-2 text-[11px] text-slate-500">
                XGBoost consistency{" "}
                <b className="text-slate-300">{consistency.score.toFixed(2)}</b> vs
                threshold {consistency.threshold.toFixed(2)} · model{" "}
                {String(
                  (consistency.model as { engine?: string })?.engine ?? "heuristic"
                )}{" "}
                {consistency.below_threshold
                  ? "· below threshold → gate abstains"
                  : "· within threshold"}
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-[10px] uppercase tracking-wide text-slate-500">
                      <th className="py-1 pr-2">Field</th>
                      <th className="py-1 pr-2">Submitted</th>
                      <th className="py-1 pr-2">AICTE master</th>
                      <th className="py-1 text-right">Match</th>
                    </tr>
                  </thead>
                  <tbody>
                    {consistency.rows.map((row) => {
                      const bad = row.status === "MISMATCH";
                      const partial = row.status === "PARTIAL";
                      return (
                        <tr
                          key={row.field}
                          className="border-t border-slate-800/70 align-top"
                        >
                          <td className="py-1.5 pr-2 text-slate-400">{row.field}</td>
                          <td className="py-1.5 pr-2 font-mono text-slate-200">
                            {row.submitted || "—"}
                          </td>
                          <td
                            className={`py-1.5 pr-2 font-mono ${
                              bad
                                ? "bg-rose-500/10 text-rose-300"
                                : partial
                                ? "text-amber-300"
                                : "text-slate-300"
                            }`}
                          >
                            {row.master || "—"}
                          </td>
                          <td className="py-1.5 text-right">
                            <span
                              className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                                row.status === "MATCH"
                                  ? "bg-emerald-500/15 text-emerald-300"
                                  : partial
                                  ? "bg-amber-500/15 text-amber-300"
                                  : bad
                                  ? "bg-rose-500/15 text-rose-300"
                                  : "bg-slate-700/50 text-slate-400"
                              }`}
                            >
                              {row.status.replace("_", " ")}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {consistency.below_threshold && (
                <p className="mt-2 rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-[11px] leading-relaxed text-amber-200">
                  Score dragged down mostly by{" "}
                  <b>
                    {consistency.weakest_features
                      .slice(0, 3)
                      .map(
                        (f) =>
                          `${FEATURE_LABELS[f.feature] ?? f.feature} ${f.value.toFixed(
                            2
                          )}`
                      )
                      .join(" · ")}
                  </b>
                  .
                </p>
              )}
              <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
                {consistency.master_record
                  ? `Master record ${consistency.master_record.aicte_id} · valid up to ${consistency.master_record.valid_upto}.`
                  : "No AICTE master record matched this AICTE ID - the model scores the remaining signals only."}{" "}
                Submitted vs master values are compared field by field; the model also
                weighs issuer, OCR, tamper and duplicate signals.
              </p>
            </div>
          )}

          {/* Duplicate pair viewer */}
          {duplicates && duplicates.count > 0 && (
            <div className="card" data-testid="duplicates-card">
              <h3 className="mb-2 flex items-center gap-2 font-semibold">
                <CopyCheck className="h-4 w-4 text-rose-400" />
                Duplicate documents (pHash)
                <span className="ml-auto rounded-full bg-rose-500/15 px-2 text-xs text-rose-300">
                  {duplicates.count}
                </span>
              </h3>
              <div className="space-y-3">
                {duplicates.pairs.map((p, i) => (
                  <div
                    key={p.document.id}
                    className="rounded-lg border border-rose-500/30 bg-slate-950/40 p-2.5"
                  >
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px]">
                      <span className="font-mono text-rose-300">{p.rule_id}</span>
                      <span className="text-slate-400">
                        hamming distance{" "}
                        <b className="text-slate-200">{p.distance ?? "–"}</b> (limit{" "}
                        {p.threshold}) · OCR text similarity{" "}
                        <b className="text-slate-200">{p.text_sim.toFixed(2)}</b>
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <figure className="rounded border border-amber-500/30 bg-amber-500/5 p-1">
                        <figcaption className="mb-1 truncate text-[10px] font-bold text-amber-300">
                          Submitted · {p.document.ref_no}
                        </figcaption>
                        {dupImages[`doc-${i}`] ? (
                          <img
                            src={dupImages[`doc-${i}`]}
                            alt={`submitted ${p.document.filename}`}
                            className="w-full rounded"
                          />
                        ) : (
                          <div className="flex h-24 items-center justify-center text-slate-500">
                            <Loader2 className="h-4 w-4 animate-spin" />
                          </div>
                        )}
                        <div className="mt-1 truncate text-[10px] text-slate-500">
                          {p.document.filename}
                        </div>
                      </figure>
                      <figure className="rounded border border-sky-500/30 bg-sky-500/5 p-1">
                        <figcaption className="mb-1 truncate text-[10px] font-bold text-sky-300">
                          Original · {p.donor.ref_no}
                        </figcaption>
                        {dupImages[`donor-${i}`] ? (
                          <img
                            src={dupImages[`donor-${i}`]}
                            alt={`original ${p.donor.filename}`}
                            className="w-full rounded"
                          />
                        ) : (
                          <div className="flex h-24 items-center justify-center text-slate-500">
                            <Loader2 className="h-4 w-4 animate-spin" />
                          </div>
                        )}
                        <div className="mt-1 truncate text-[10px] text-slate-500">
                          {p.donor.institution_name}
                        </div>
                      </figure>
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
                The same file appears in more than one application - both copies are
                shown so a human can confirm before any decision.
              </p>
            </div>
          )}

          {/* Checklist */}
          <div className="card">
            <h3 className="mb-2 font-semibold">APH 2024-27 auto-checklist</h3>
            <div className="space-y-2">
              {(app.checklist_json ?? []).map((item) => (
                <div
                  key={item.rule_id}
                  className="rounded-lg border border-slate-800 bg-slate-950/40 p-2.5 text-xs"
                >
                  <div className="flex items-center gap-2">
                    {item.status === "OK" && (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                    )}
                    {item.status === "MISSING" && (
                      <XIcon className="h-4 w-4 shrink-0 text-rose-400" />
                    )}
                    {item.status === "EXPIRED" && (
                      <AlertTriangle className="h-4 w-4 shrink-0 text-orange-400" />
                    )}
                    {item.status === "WARN" && (
                      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
                    )}
                    <span className="font-medium text-slate-200">{item.name}</span>
                    <span className="ml-auto font-mono text-[10px] text-slate-500">
                      {item.rule_id}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                    <span>{item.present ? `doc #${item.document_id}` : "not uploaded"}</span>
                    {item.issuer_status && <IssuerBadge status={item.issuer_status} />}
                    {item.missing_fields?.length ? (
                      <span className="text-amber-300">
                        missing: {item.missing_fields.join(", ")}
                      </span>
                    ) : null}
                    {item.expiry_date && (
                      <span className="text-orange-300">expired {item.expiry_date}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Flags */}
          <div className="card">
            <h3 className="mb-2 flex items-center gap-2 font-semibold">
              Explainable flags
              <span className="rounded-full bg-rose-500/15 px-2 text-xs text-rose-300">
                {app.flags.filter((f) => f.status === "OPEN").length} open / {app.flags.length}
              </span>
            </h3>
            <div className="space-y-2">
              {app.flags.map((f) => {
                const Icon = KIND_ICONS[f.kind] ?? AlertTriangle;
                return (
                  <div
                    key={f.id}
                    className={`rounded-lg border p-2.5 text-xs transition ${
                      f.id === activeFlagId
                        ? "border-indigo-500 bg-indigo-500/10"
                        : "border-slate-800 bg-slate-950/40"
                    } ${f.status === "RESOLVED" ? "opacity-60" : ""}`}
                  >
                    <div className="flex items-center gap-2">
                      <Icon
                        className={`h-4 w-4 shrink-0 ${
                          f.severity === "CRITICAL" ? "text-rose-400" : "text-amber-400"
                        }`}
                      />
                      <span className="font-semibold text-slate-200">{f.title}</span>
                      <SeverityBadge severity={f.severity} />
                      <span className="ml-auto font-mono text-[10px] text-slate-500">
                        {f.rule_id}
                      </span>
                    </div>
                    <p className="mt-1.5 leading-relaxed text-slate-400">{f.reason}</p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
                      <span>kind: {f.kind}</span>
                      {f.document_id && <span>document #{f.document_id}</span>}
                      {f.page_no && <span>page {f.page_no}</span>}
                      {f.bbox && (
                        <span className="font-mono">
                          bbox [{f.bbox.map((v) => v.toFixed(2)).join(", ")}]
                        </span>
                      )}
                      <span className={f.status === "OPEN" ? "text-amber-300" : "text-emerald-300"}>
                        {f.status}
                      </span>
                      {f.bbox && (
                        <button className="btn-ghost !px-2 !py-0.5 !text-[10px]" onClick={() => focusFlag(f)}>
                          <Eye className="h-3 w-3" /> show on document
                        </button>
                      )}
                    </div>

                    {f.status === "OPEN" && canReview && (
                      <div className="mt-2 space-y-2">
                        <input
                          className="input !py-1.5 text-xs"
                          placeholder="Comment for the audit trail…"
                          value={comments[f.id] ?? ""}
                          onChange={(e) =>
                            setComments({ ...comments, [f.id]: e.target.value })
                          }
                        />
                        <div className="flex gap-2">
                          <button
                            className="btn-primary !px-2.5 !py-1 !text-xs"
                            disabled={busyFlag === f.id}
                            onClick={() => decide(f.id, "APPROVE")}
                          >
                            <ThumbsUp className="h-3 w-3" /> Approve
                          </button>
                          <button
                            className="btn !px-2.5 !py-1 !text-xs bg-rose-600 text-white hover:bg-rose-500"
                            disabled={busyFlag === f.id}
                            onClick={() => decide(f.id, "REJECT")}
                          >
                            <ThumbsDown className="h-3 w-3" /> Reject
                          </button>
                          <button
                            className="btn-ghost !px-2.5 !py-1 !text-xs"
                            disabled={busyFlag === f.id}
                            onClick={() => decide(f.id, "REQUEST_INFO")}
                          >
                            <Send className="h-3 w-3" /> Request info
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
              {app.flags.length === 0 && (
                <p className="text-xs text-slate-500">
                  No flags - the machine found nothing worth reporting.
                </p>
              )}
            </div>
          </div>

          {/* Review history */}
          {app.reviews.length > 0 && (
            <div className="card">
              <h3 className="mb-2 flex items-center gap-2 font-semibold">
                <MessageSquare className="h-4 w-4 text-slate-400" /> Human decisions
              </h3>
              <div className="space-y-1.5">
                {app.reviews.map((r) => (
                  <div key={r.id} className="rounded-lg border border-slate-800 p-2 text-xs">
                    <div className="flex items-center gap-2">
                      <span
                        className={`font-bold ${
                          r.decision === "APPROVE"
                            ? "text-emerald-300"
                            : r.decision === "REJECT"
                            ? "text-rose-300"
                            : "text-sky-300"
                        }`}
                      >
                        {r.decision.replace("_", " ")}
                      </span>
                      <span className="text-slate-400">by {r.reviewer_name}</span>
                      <span className="ml-auto text-slate-600">
                        {r.created_at.replace("T", " ").slice(0, 16)}
                      </span>
                    </div>
                    {r.comment && <p className="mt-1 text-slate-300">{r.comment}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="9" />
      <path d="m9 9 6 6M15 9l-6 6" />
    </svg>
  );
}
