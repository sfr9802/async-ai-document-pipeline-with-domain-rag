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

## Cleanup Rules

1. Keep current reports here when a script default, progress document, or
   generated manifest references this path.
2. Move local process logs under `runtime-logs/<run-name>/`; logs are ignored by
   git and should not be mixed with report JSON.
3. Archive retired generated reports under `archive/results/<date>-<topic>/`
   only after proving they are no longer active evidence. Add archive manifest
   rows when doing that.
4. If a report is ambiguous, keep it in place and mark the cleanup decision as
  `needs_review` rather than moving it aggressively.
