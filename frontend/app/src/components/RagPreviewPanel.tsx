import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, queryRagPreview } from "@/lib/api";
import type { RagPreviewCitation, RagPreviewEvidenceCard, RagPreviewResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { CircleAlert, FileText, Loader2, Search, ShieldCheck, Table2 } from "lucide-react";

export function RagPreviewPanel() {
  const [query, setQuery] = useState("");
  const [contextOpen, setContextOpen] = useState(false);
  const [fileId, setFileId] = useState("");
  const [sheet, setSheet] = useState("");
  const [locatorText, setLocatorText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<RagPreviewResponse | null>(null);

  const canSubmit = query.trim().length > 0 && !loading;
  const failClosed = result && result.status !== "answered";

  async function handleSubmit() {
    if (!query.trim()) {
      setError("질문을 입력하세요.");
      setResult(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await queryRagPreview({
        query,
        locale: "ko-KR",
        active_context: {
          file_id: fileId,
          sheet,
          locator_text: locatorText,
        },
      });
      setResult(response);
    } catch (e) {
      if (e instanceof ApiError) {
        setError(typeof e.body === "object" && e.body ? `${e.body.code}: ${e.body.message}` : e.message);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && canSubmit) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <section className="overflow-hidden rounded-[22px] border border-hairline-2 bg-glass shadow-glass backdrop-blur-[18px] backdrop-saturate-150">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline px-6 py-4">
        <div className="flex items-center gap-2.5">
          <div className="grid h-9 w-9 place-items-center rounded-lg border border-hairline-2 bg-glass-strong">
            <Search className="h-4 w-4 text-cap-rag" />
          </div>
          <div>
            <h2 className="text-[15px] font-semibold tracking-snug">RAG 미리보기</h2>
            <div className="t-eyebrow">non-prod · source-first · default-off</div>
          </div>
        </div>
        <Badge variant="outline" className="gap-1.5 border-success/35 bg-success/10 text-success">
          <ShieldCheck className="h-3 w-3" />
          redacted
        </Badge>
      </header>

      <div className="space-y-4 px-6 py-5">
        <div>
          <div className="flex items-baseline justify-between">
            <Label htmlFor="rag-preview-query" className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
              질문
            </Label>
            <span className="font-mono text-[10.5px] text-muted-foreground">{query.length}자</span>
          </div>
          <Textarea
            id="rag-preview-query"
            aria-label="RAG preview query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="문서, 표, PDF 근거에 대해 질문하세요."
            className="mt-2 min-h-[96px] resize-y rounded-lg border-hairline-2 bg-glass-3 font-mono text-[12.5px] leading-relaxed shadow-none focus-visible:bg-glass-strong focus-visible:ring-2 focus-visible:ring-ring/30"
          />
        </div>

        <div className="rounded-lg border border-hairline-2 bg-glass-2">
          <button
            type="button"
            onClick={() => setContextOpen((open) => !open)}
            aria-label="활성 컨텍스트"
            className="flex w-full items-center justify-between px-3 py-2.5 text-left text-[12px] font-semibold uppercase tracking-[0.12em] text-muted-foreground"
          >
            활성 컨텍스트
            <span className="font-mono text-[10px]">{contextOpen ? "open" : "closed"}</span>
          </button>
          {contextOpen && (
            <div className="grid gap-3 border-t border-hairline px-3 py-3 md:grid-cols-3">
              <ContextInput id="rag-preview-file" label="파일 ID" value={fileId} onChange={setFileId} />
              <ContextInput id="rag-preview-sheet" label="시트" value={sheet} onChange={setSheet} />
              <ContextInput id="rag-preview-locator" label="위치" value={locatorText} onChange={setLocatorText} />
            </div>
          )}
        </div>

        {error && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2.5 text-[12.5px] text-destructive">
            {error}
          </div>
        )}

        <div className="flex justify-end">
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={loading}
            className="h-9 gap-1.5 px-4 shadow-glass-button transition-all hover:-translate-y-px hover:bg-primary/90"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
            {loading ? "실행 중..." : "미리보기 실행"}
          </Button>
        </div>
      </div>

      {result && (
        <div className="border-t border-hairline bg-glass-2 px-6 py-5">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={result.status} />
            {result.non_production_preview && (
              <span className="t-mono-tag rounded-full border border-hairline-2 bg-glass-3 px-2 py-1">
                non-prod preview
              </span>
            )}
          </div>

          <div className="mt-4">
            {failClosed ? (
              <FailClosedResult result={result} />
            ) : (
              <AnsweredResult result={result} />
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function ContextInput({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </Label>
      <Input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 border-hairline-2 bg-glass-3 font-mono text-xs focus-visible:bg-glass-strong"
      />
    </div>
  );
}

function StatusPill({ status }: { status: RagPreviewResponse["status"] }) {
  const good = status === "answered";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-[0.12em]",
        good ? "border-success/40 bg-success/10 text-success" : "border-warning/40 bg-warning/10 text-warning",
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", good ? "bg-success" : "bg-warning")} />
      {status}
    </span>
  );
}

function AnsweredResult({ result }: { result: RagPreviewResponse }) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-hairline-2 bg-glass-strong p-4">
        <div className="t-eyebrow mb-2">answer</div>
        <p className="text-[14px] leading-relaxed">{safePreviewText(result.answer)}</p>
      </div>

      {result.citations.length > 0 && (
        <section aria-label="RAG preview citations">
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            인용
          </h3>
          <ul className="grid gap-2 md:grid-cols-3">
            {result.citations.map((citation, index) => (
              <CitationRow citation={citation} key={citationRenderKey(citation, index)} />
            ))}
          </ul>
        </section>
      )}

      {result.evidence_cards.length > 0 && (
        <section>
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            근거 카드
          </h3>
          <ul className="grid gap-2 md:grid-cols-3">
            {result.evidence_cards.map((card, index) => (
              <EvidenceCard card={card} key={evidenceCardRenderKey(card, index)} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function FailClosedResult({ result }: { result: RagPreviewResponse }) {
  return (
    <div className="rounded-lg border border-warning/35 bg-warning/10 p-4 text-warning">
      <div className="flex items-start gap-2">
        <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="space-y-1">
          <p className="text-[13px] font-semibold">답변 가능한 근거가 부족하거나 백엔드가 준비되지 않았습니다.</p>
          {safePreviewText(result.diagnostics?.fail_closed_reason) && (
            <p className="font-mono text-[11.5px]">{safePreviewText(result.diagnostics?.fail_closed_reason)}</p>
          )}
        </div>
      </div>
    </div>
  );
}

function CitationRow({ citation }: { citation: RagPreviewCitation }) {
  const detail = citationDetail(citation);
  const primary = safePreviewText(detail.primary);
  const secondary = safePreviewText(detail.secondary);
  return (
    <li className="rounded-lg border border-hairline-2 bg-glass-3 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-cap-rag">
          {citation.source_family}
        </span>
        <FileText className="h-3.5 w-3.5 text-muted-foreground" />
      </div>
      <div className="text-[12.5px] font-medium">{primary}</div>
      {secondary && (
        <div className="mt-1 font-mono text-[10.5px] text-muted-foreground">{secondary}</div>
      )}
    </li>
  );
}

function EvidenceCard({ card }: { card: RagPreviewEvidenceCard }) {
  const primary = safePreviewText(card.display_value || card.matched_text || "근거 표시값 없음");
  const meta = safePreviewText(evidenceMeta(card));
  return (
    <li className="rounded-lg border border-hairline-2 bg-glass-3 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          {card.kind}
        </span>
        <Table2 className="h-3.5 w-3.5 text-muted-foreground" />
      </div>
      <div className="text-[12.5px] font-medium leading-relaxed">{primary}</div>
      {meta && <div className="mt-1 font-mono text-[10.5px] text-muted-foreground">{meta}</div>}
    </li>
  );
}

function citationRenderKey(citation: RagPreviewCitation, index: number): string {
  if (citation.citation_key) return citation.citation_key;
  return [
    "citation",
    citation.source_family,
    citation.source_atom_id,
    citation.source_identity_hash,
    citation.page,
    jsonKeyPart(citation.bbox),
    citation.sheet,
    citation.table_or_range,
    citation.title,
    citation.section,
    index,
  ]
    .filter((part) => part !== undefined && part !== null && part !== "")
    .join(":");
}

function evidenceCardRenderKey(card: RagPreviewEvidenceCard, index: number): string {
  return [
    "evidence",
    card.kind,
    card.source_family,
    card.source_atom_id,
    card.sheet,
    card.table_or_range,
    jsonKeyPart(card.matched_cells),
    card.page,
    jsonKeyPart(card.bbox),
    jsonKeyPart(card.section),
    card.text_span,
    card.display_value,
    card.matched_text,
    index,
  ]
    .filter((part) => part !== undefined && part !== null && part !== "")
    .join(":");
}

function jsonKeyPart(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function citationDetail(citation: RagPreviewCitation): { primary: string; secondary: string } {
  if (citation.source_family === "XLSX") {
    return { primary: citation.sheet || "XLSX", secondary: citation.table_or_range || citation.source_identity_hash || "" };
  }
  if (citation.source_family === "PDF") {
    return { primary: citation.page != null ? `page ${citation.page}` : "PDF", secondary: citation.source_identity_hash || "" };
  }
  return { primary: citation.title || citation.section || "TEXT", secondary: citation.section || citation.source_identity_hash || "" };
}

function evidenceMeta(card: RagPreviewEvidenceCard): string {
  if (card.kind === "xlsx") {
    return [card.sheet, card.table_or_range, ...(card.matched_cells ?? [])].filter(Boolean).join(" · ");
  }
  if (card.kind === "pdf") {
    return card.page != null ? `page ${card.page}` : "";
  }
  if (card.kind === "text") {
    return (card.section ?? []).join(" · ") || card.text_span || "";
  }
  return "";
}

const FORBIDDEN_PREVIEW_TEXT = /\b(prompt|raw_prompt|raw_response|raw_llm_response|expected_answer|expected_answer_ko|gold_label|gold_labels|gold_locator|gold_qrels|gold_status|hidden_locator|include_in_official_denominator|official_metric_input_rows_payload|citation_locator|query_id|case_id|source_identity|source_path|source_pdf_path|source_title|supporting_evidence_id|supporting_evidence_ids|supporting_evidence_note|target_locator|workbook|file_name)\b/gi;
const LOCAL_PATH_TEXT = /(?:[A-Za-z]:[\\/][^\s"'<>]+|\/(?:data|home|mnt|private|tmp|Users)\/[^\s"'<>]+)/g;

function safePreviewText(value: unknown): string {
  const text = typeof value === "string" ? value : "";
  return text.replace(LOCAL_PATH_TEXT, "[redacted]").replace(FORBIDDEN_PREVIEW_TEXT, "[redacted]");
}
