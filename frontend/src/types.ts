// Mirrors of the FastAPI response schemas (backend/app/schemas.py)

export interface TokenResponse {
  access_token: string;
  token_type: string;
  username: string;
  role: "officer" | "reviewer" | "auditor";
  full_name: string;
}

export type AppStatus =
  | "UPLOADED"
  | "PROCESSING"
  | "VERIFIED"
  | "INSUFFICIENT_EVIDENCE"
  | "IN_REVIEW"
  | "APPROVED"
  | "REJECTED";

export interface ApplicationSummary {
  id: number;
  ref_no: string;
  institution_name: string;
  category: string;
  aicte_id: string;
  status: AppStatus;
  gate_status: string;
  gate_confidence: number;
  risk_score: number;
  consistency_score: number;
  ocr_confidence: number;
  tamper_score: number;
  issuer_status: string;
  open_flags: number;
  doc_count: number;
  scenario: string;
  created_at: string;
  validated_at: string | null;
}

export interface ExtractedField {
  value?: string;
  confidence: number;
  page_no?: number;
  bbox?: [number, number, number, number]; // normalized x, y, w, h
}

export interface DocumentOut {
  id: number;
  doc_type: string;
  filename: string;
  mime: string;
  page_count: number;
  ocr_confidence: number;
  ocr_engine: string;
  ocr_text: string;
  extracted_json: Record<string, ExtractedField>;
  tamper_score: number;
  ela_bbox?: [number, number, number, number] | null;
  phash: string;
  duplicate_of: number | null;
  uploaded_at: string;
}

export type FlagKind =
  | "RULE"
  | "OCR"
  | "EXTRACTION"
  | "CONSISTENCY"
  | "TAMPER"
  | "DUPLICATE"
  | "ISSUER"
  | "EVIDENCE";

export interface FlagOut {
  id: number;
  application_id: number;
  document_id: number | null;
  kind: FlagKind;
  rule_id: string;
  title: string;
  reason: string;
  severity: "INFO" | "WARN" | "CRITICAL";
  page_no: number | null;
  bbox: [number, number, number, number] | null;
  status: string;
  created_at: string;
}

export interface ChecklistItem {
  rule_id: string;
  doc_type: string;
  name: string;
  required: boolean;
  issuer_portal: string | null;
  validity_required: boolean;
  present: boolean;
  document_id: number | null;
  status: "OK" | "MISSING" | "EXPIRED" | "WARN";
  issuer_status?: string;
  missing_fields?: string[];
  expiry_date?: string;
  fields: Record<
    string,
    {
      ok: boolean;
      value: string;
      confidence: number;
      page_no?: number;
      bbox?: number[];
    }
  >;
}

export interface ReviewOut {
  id: number;
  flag_id: number;
  reviewer_name: string;
  decision: "APPROVE" | "REJECT" | "REQUEST_INFO";
  comment: string;
  created_at: string;
}

export interface ProgressStep {
  name: string;
  detail: string;
  status: "PENDING" | "RUNNING" | "DONE" | "ERROR";
  ms?: number;
}

export interface Progress {
  status: string;
  current_step: string | null;
  steps: ProgressStep[];
  error: string | null;
  updated_at?: string;
}

export interface ApplicationDetail extends ApplicationSummary {
  address: string;
  approved_intake: number;
  scenario: string;
  gate_reasons: { rule_id: string; message: string }[];
  checklist_json: ChecklistItem[];
  progress_json: Progress;
  created_by: string;
  documents: DocumentOut[];
  flags: FlagOut[];
  reviews: ReviewOut[];
}

export interface DashboardStats {
  total: number;
  verified: number;
  insufficient_evidence: number;
  in_review: number;
  approved: number;
  rejected: number;
  processing: number;
  gate_pass_rate: number;
  by_category: Record<string, number>;
  mock_mode: boolean;
}

export interface AuditEntry {
  id: number;
  ts: string;
  actor: string;
  role: string;
  action: string;
  entity_type: string;
  entity_id: number | null;
  detail: Record<string, unknown>;
}

export interface ReviewQueueItem {
  application: {
    id: number;
    ref_no: string;
    institution_name: string;
    category: string;
    status: AppStatus;
    risk_score: number;
    gate_confidence: number;
    issuer_status: string;
    gate_reasons: { rule_id: string; message: string }[];
  };
  open_flags: {
    id: number;
    title: string;
    rule_id: string;
    severity: string;
    kind: string;
    has_location: boolean;
  }[];
  decided_flags: number;
}

export interface AppConfig {
  mock_mode: boolean;
  ocr_confidence_threshold: number;
  tamper_score_threshold: number;
  consistency_threshold: number;
  categories: string[];
}

// ------------------------------------------------------- insights (new views)

export type ConsistencyStatus =
  | "MATCH"
  | "PARTIAL"
  | "MISMATCH"
  | "NO_RECORD"
  | "NOT_EXTRACTED";

export interface ConsistencyRow {
  field: string;
  submitted: string;
  master: string;
  feature: string;
  value: number;
  status: ConsistencyStatus;
}

export interface MasterRecord {
  aicte_id: string;
  institution_name: string;
  category: string;
  address: string;
  approved_intake: number;
  status: string;
  valid_upto: string;
}

export interface ConsistencyView {
  score: number;
  stored_score: number;
  threshold: number;
  below_threshold: boolean;
  model: { engine?: string; trained?: boolean; [k: string]: unknown };
  weakest_features: { feature: string; value: number; weight: number }[];
  master_record: MasterRecord | null;
  rows: ConsistencyRow[];
  features: Record<string, number>;
}

export interface DocRef {
  id: number;
  filename: string;
  doc_type: string;
  page_count: number;
  application_id: number;
  ref_no: string;
  institution_name: string;
}

export interface DuplicatePair {
  rule_id: string;
  document: DocRef;
  donor: DocRef;
  distance: number | null;
  threshold: number;
  text_sim: number;
  page: number;
}

export interface DuplicatesView {
  pairs: DuplicatePair[];
  count: number;
}

export interface IssuerPortal {
  id: string;
  name: string;
  status: "UP" | "DOWN";
  degraded: boolean;
  records: number;
  records_down: number;
  checks_total: number;
  checks: Record<string, number>;
  verified: number;
  verified_rate: number | null;
  failures: Record<string, number>;
  examples: Record<string, string[]>;
  last_checked: string;
}

export interface IssuerStatusView {
  portals: IssuerPortal[];
  outage_portals: string[];
  pinned_outages: {
    portal: string;
    portal_name: string;
    doc_number: string;
    holder_name: string;
  }[];
  summary: {
    portals: number;
    down: number;
    degraded: number;
    total_checks: number;
    verified: number;
    verified_rate: number;
    by_status: Record<string, number>;
  };
  updated_at: string;
}

export interface AnalyticsView {
  generated_at: string;
  totals: {
    applications: number;
    verified: number;
    insufficient_evidence: number;
    in_review: number;
    approved: number;
    rejected: number;
    pending: number;
    gate_pass_rate: number;
    flags: number;
    open_flags: number;
    documents: number;
  };
  averages: {
    ocr_confidence: number;
    consistency: number;
    tamper: number;
    gate_confidence: number;
    risk: number;
  };
  gate_outcomes: { status: string; count: number }[];
  by_category: {
    category: string;
    total: number;
    verified: number;
    insufficient: number;
    avg_confidence: number;
    avg_risk: number;
  }[];
  flags_by_kind: { kind: string; count: number; critical: number }[];
  flags_by_rule: {
    rule_id: string;
    title: string;
    severity: string;
    count: number;
  }[];
  document_gaps: {
    name: string;
    status: "MISSING" | "EXPIRED";
    rule_id: string;
    count: number;
  }[];
  issuer_outcomes: { status: string; count: number }[];
  abstain_reasons: { rule_id: string; count: number }[];
  risk_buckets: { bucket: string; count: number }[];
  queue_aging: { bucket: string; count: number }[];
  decisions: { APPROVE: number; REJECT: number; REQUEST_INFO: number };
  scenarios: Record<string, { ref_no: string; status: string }>;
}
