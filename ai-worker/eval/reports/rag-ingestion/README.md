# RAG Ingestion Reports

This directory is the active working-evidence location for RAG ingestion
diagnostics. Many scripts and progress logs intentionally write to this flat
directory, so do not move current reports into topic folders unless the script
defaults and documentation references are updated in the same change.

## Report Families

| Family | Typical files | Use |
|---|---|---|
| Baseline and indexing | `initial_*`, `a5_*`, `rag_candidate_*`, `rag_ingestion_a5_*`, `rag_retrieval_eval_full72_*` | Immutable baseline, candidate indexing, and full72 diagnostics. |
| Track A XLSX | `xlsx_candidate_*`, `rag_xlsx_*`, `rag_retrieval_eval_xlsx_*` | Spreadsheet candidate, hidden-content, query-surface, and retrieval diagnostics. |
| Track B text | `rag_text_*`, `rag_query_intent_routing_matrix_report.json` | Namu/text corpus, query-intent, answerability, citation-support, and prompt diagnostics. |
| Track C PDF | `pdf_*`, `rag_pdf_*`, `rag_retrieval_eval_pdf_*` | PDF candidate, metadata, vector-quality, policy-review, and decision-pack diagnostics. |
| Cross-track readiness | `rag_file_content_lane_*`, `rag_pdf_xlsx_*`, `rag_text_r8_*` | ABC lane readiness, denominator, and shape/echo-risk comparison outputs. |
| Runtime logs | `runtime-logs/` | Ignored local process logs. Keep logs out of the report root. |

## 3-track report policy

Current orchestration reports must name the active tracks explicitly:

| Track | Report meaning |
|---|---|
| `text_namuwiki_animation` | Namuwiki animation-domain TEXT RAG. Do not describe this as general business text RAG. |
| `xlsx_business_structured` | Business spreadsheet structured RAG with sheet/table/row/column context, not flatten-only keyword search. |
| `pdf_business_ocr_mm` | Business OCR/MM document RAG with page/bbox/region context, not OCR-text-only search. |

Reports should include track-level denominator fields for TEXT, XLSX, and PDF.
An overall average may be printed for quick diagnostics, but it must not be used
as a promotion or quality interpretation unless each track denominator is
shown separately.

Route-decision sections should record wrong-route, low-confidence, fallback, and
multi-route cases when route labels exist. If route labels do not exist, record
those fields as diagnostic-only instead of silently treating them as zero.

## Cleanup Rules

1. Keep current reports here when a script default, progress document, or
   generated manifest references this path.
2. Move local process logs under `runtime-logs/<run-name>/`; logs are ignored by
   git and should not be mixed with report JSON.
3. Do not create new repo-internal archive folders for retired generated
   reports. Large historical payloads should move to an external archive with a
   manifest and per-file checksums, preserving the repo-relative path. Existing
   `archive/results/...` entries are provenance-only and are not a dumping
   ground for new run output.
4. If a report is ambiguous, keep it in place and mark the cleanup decision as
  `needs_review` rather than moving it aggressively.

Recent external archive:

- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260511-eval-report-cleanup\archive_summary.json`
- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260511-eval-report-cleanup\archive_manifest.csv`

The 2026-05-11 cleanup moved ignored/generated reports and eval artifacts only.
Tracked/canonical reports, current 3-track report output, denominator registry
inputs, and active corpus/eval-query inputs were preserved in the workspace.

## Runtime Output Policy

Generated raw artifacts should default outside the repository when a workflow is
not producing a small current summary, denominator registry, baseline descriptor,
or human-review/gold artifact. Preferred roots are:

| Env var | Intended payload |
|---|---|
| `RAG_ARTIFACT_ROOT` | Raw `eval_runs/` bundles and diagnostic payloads. |
| `RAG_REPORT_ROOT` | Re-runnable report output that is not current evidence. |
| `RAG_VECTOR_ARTIFACT_ROOT` | FAISS/vector cache directories not protected by an active baseline or candidate descriptor. |
| `RAG_DATASET_CACHE_ROOT` | Generated dataset caches and temporary parsed exports. |
| `RAG_PAGEINDEX_ARTIFACT_ROOT` | PageIndex manifests, trees, and local canary bundles. |
| `RAG_LLM_IO_ARTIFACT_ROOT` | Prompt/input/raw-answer JSONL from local LLM diagnostics. |

Default external runtime root: `../_external_runtime_artifacts/<repo-name>/`.
If a script has not yet been migrated to these env vars, pass an explicit
`--report`, `--report-dir`, `--output`, or run-artifact path instead of letting
large diagnostics accumulate here.
