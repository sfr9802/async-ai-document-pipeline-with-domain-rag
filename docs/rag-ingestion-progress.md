# RAG Ingestion Progress

Last updated: 2026-05-17 KST.

This is the compact status index for the current RAG ingestion and official
answer/citation metric work. Do not append turn transcripts or create new
per-phase `*_v1.json` / `*_v1.md` report pairs for routine status. Use this
file for human-readable status and
`ai/eval/reports/rag-ingestion/rag_current_eval_status.jsonl` for compact
current status events.

## Current Status

Overall status: `official_answer_citation_pdf_table_value_candidate_report_only_pass`.

- Official first-run baseline is `SCORED_BASELINE_PARTIAL` with
  `official_metric_execution_started=true`, `official_scoring_attempt_count=29`,
  `scored_count=29`, PASS=8, CITATION_UNSUPPORTED=11,
  PARTIAL_OR_UNSUPPORTED=10.
- XLSX runtime candidate is report-only and deterministic: PASS=26/29,
  XLSX=19/19, local LLM/GPU used=false.
- PDF candidate now has official-compatible source-bound locators for
  `gq_auto_010`, `gq_auto_030`, and `gq_pdf_section_question_001`; report-only,
  no promotion, PASS=29/29, and it does not overwrite the official first-run
  baseline or XLSX runtime candidate results.
- Current focused profile is the active feedback loop:
  `python -X utf8 -m pytest ai/tests --rag-current -q`; full ai/tests is broad/nightly diagnostic only.
- Hard cleanup keeps only the 8 source-of-truth/current files in
  `ai/eval/reports/rag-ingestion/`. Historical report/doc artifacts were moved
  to `D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\hard-cleanup-20260517`.

## Track Board

| Track | Current state | Current metric/evidence | Next action |
|---|---|---|---|
| `text_namu_v2_1` | Official baseline PASS=6/6; `text_namu_v2_0017` remains diagnostic-only warning | Registry-backed official rows=6 | Preserve pass state and warning; no tuning. |
| `xlsx_business_structured` | XLSX runtime candidate report-only PASS=19/19; all-track carry-forward PASS=26/29 | Registry-backed official rows=19; candidate results JSONL retained | Keep generalization/overfit guards green; no promotion. |
| `pdf_business_ocr_mm` | PDF table/value candidate report-only repairs the three remaining failures; all-track observation PASS=29/29 | Registry-backed official rows=4; candidate results JSONL retained | Review PDF candidate as a narrow repair surface before any next official run. |
| Current tests | `--rag-current` profile isolates official metric, source-of-truth, candidate, and guardrail tests | Historical/optional external artifact tests are removed from the current loop | Use focused profile for PDF work; reserve full ai/tests for broad/nightly diagnostics. |

## Current Verification Command

Windows/conda:

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
conda run -n rag-eval-py311 --no-capture-output python -X utf8 -m pytest ai/tests --rag-current -q
conda run -n rag-eval-py311 --no-capture-output python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q
```

Current verification: `--rag-current` 68 passed, 0 skipped, 0 failed;
marker profile 68 passed, 2909 deselected, 0 failed.

## Current Source-Of-Truth Artifacts

Canonical official artifacts:

- `ai/eval/reports/rag-ingestion/official_answer_citation_metric_first_run_v1.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_metric_first_run_v1.md`
- `ai/eval/reports/rag-ingestion/official_answer_citation_scorer_results_v1.jsonl`
- `ai/eval/reports/rag-ingestion/official_metric_input_config_v1.json`
- `ai/eval/reports/rag-ingestion/official_metric_pre_execution_smoke_report_v1.json`

Current compact candidate/status artifacts:

- `ai/eval/reports/rag-ingestion/xlsx_answer_citation_runtime_precision_candidate_results_v1.jsonl`
- `ai/eval/reports/rag-ingestion/pdf_answer_citation_table_value_candidate_results_v1.jsonl`
- `ai/eval/reports/rag-ingestion/rag_current_eval_status.jsonl`

The pre-execution smoke report is a pre-execution artifact, so
`official_metric_execution_started=false` there is expected and must not be read
as the latest metric execution status.

## Guardrails

- `tuning_run_started=false`
- `promotion_evidence=false`
- `threshold_tuning=false`
- `winner_selection=false`
- `production_mutation=false`
- `denominator_mutation=false`
- `gold_mutation=false`
- Expected answer and supporting evidence are not used for generation.
- Gold CSVs, official denominator registry, human labels, production namespace,
  vector indexes, and immutable first-run baseline artifacts remain protected.

## Next Recommended Steps

1. Continue PDF 3-row candidate review with the current focused profile only.
2. Keep XLSX runtime generalization guards in the focused profile.
3. Open a next official metric run only after explicit approval; report-only
   candidates are not promotion evidence.

## Short History

| Date | Compact entry |
|---|---|
| 2026-05-16 | Historical first-run attempt was blocked with `SCORER_BACKEND_UNAVAILABLE`; the active first-run artifacts were later regenerated and this state is superseded. |
| 2026-05-17 | Official first-run baseline scored 29/29 rows and remained partial: PASS=8, CITATION_UNSUPPORTED=11, PARTIAL_OR_UNSUPPORTED=10. |
| 2026-05-17 | XLSX runtime candidate reached PASS=26/29 and XLSX=19/19, report-only and deterministic. |
| 2026-05-17 | PDF table/value candidate reached PASS=29/29, report-only and deterministic, without baseline/gold/denominator/production mutation. |
| 2026-05-17 | Current focused test profile established; full ai/tests kept as broad/nightly diagnostic only. |
| 2026-05-17 | Hard cleanup reduced `ai/eval/reports/rag-ingestion/` to 8 current files and externalized 63 historical report/doc artifacts; use the current verification section for the latest focused-profile count. |
