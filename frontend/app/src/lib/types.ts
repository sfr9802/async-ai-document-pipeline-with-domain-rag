export type Capability = "MOCK" | "OCR" | "RAG" | "MULTIMODAL";

export const CAPABILITIES: Capability[] = ["MOCK", "OCR", "RAG", "MULTIMODAL"];

export interface ArtifactView {
  id: string;
  role: "INPUT" | "OUTPUT" | string;
  type: string;
  contentType: string | null;
  sizeBytes: number | null;
  checksumSha256: string | null;
  accessUrl: string;
}

export interface JobCreated {
  jobId: string;
  status: string;
  capability: Capability;
  inputs: ArtifactView[];
}

export interface JobView {
  jobId: string;
  capability: Capability;
  status: string;
  attemptNo: number;
  errorCode: string | null;
  errorMessage: string | null;
  createdAt: string;
  claimedAt: string | null;
  updatedAt: string;
}

export interface JobEvent {
  status: string;
  at: string;
  source: "server" | "client";
}

export interface JobResult {
  jobId: string;
  status: string;
  inputs: ArtifactView[];
  outputs: ArtifactView[];
  errorCode: string | null;
  errorMessage: string | null;
}

export interface ErrorBody {
  code: string;
  message: string;
}

export type RagPreviewStatus =
  | "answered"
  | "insufficient_context"
  | "backend_unavailable"
  | "unsupported"
  | "validation_error";

export interface RagPreviewRequest {
  query: string;
  locale?: string;
  language?: string;
  session_id?: string;
  active_context?: {
    source_family?: "TEXT" | "PDF" | "XLSX";
    file_id?: string;
    sheet?: string;
    page?: number;
    locator_text?: string;
  };
}

export interface RagPreviewCitation {
  source_family: "TEXT" | "PDF" | "XLSX" | string;
  citation_key?: string;
  source_atom_id?: string;
  title?: string;
  section?: string;
  sheet?: string;
  table_or_range?: string;
  page?: number;
  bbox?: unknown;
  source_identity_hash?: string;
}

export interface RagPreviewEvidenceCard {
  source_family: "TEXT" | "PDF" | "XLSX" | string;
  kind: "text" | "pdf" | "xlsx" | string;
  source_atom_id?: string;
  matched_text?: string;
  display_value?: string;
  sheet?: string;
  table_or_range?: string;
  matched_cells?: string[];
  page?: number;
  bbox?: unknown;
  section?: string[];
  text_span?: string;
}

export interface RagPreviewResponse {
  answer: string;
  status: RagPreviewStatus;
  citations: RagPreviewCitation[];
  evidence_cards: RagPreviewEvidenceCard[];
  diagnostics?: {
    redacted?: boolean;
    llm_invoked?: boolean;
    response_policy_bucket?: string;
    fail_closed_reason?: string;
  };
  non_production_preview?: boolean;
  production_routing?: boolean;
  official_metric?: boolean;
  promotion_evidence?: boolean;
  product_success_evidence_allowed?: boolean;
  live_db_index_cache_readiness?: boolean;
}

export const TERMINAL_STATUSES = new Set(["SUCCEEDED", "FAILED", "CANCELED", "CANCELLED"]);

export function isTerminal(status: string | undefined | null): boolean {
  if (!status) return false;
  return TERMINAL_STATUSES.has(status.toUpperCase());
}
