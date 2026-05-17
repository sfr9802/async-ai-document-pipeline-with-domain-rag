# RAG Ingestion Progress

Last updated: 2026-05-17 KST.

This is the compact status index for the current RAG ingestion and official
answer/citation metric work. Do not append turn transcripts or create new
per-phase `*_v1.json` / `*_v1.md` report pairs for routine status. Use this
file for human-readable status and
`ai/eval/reports/rag-ingestion/rag_current_eval_status.jsonl` for compact
current status events.

## Current Status

Overall status: `official_answer_citation_agentic_loop_measurement_partial_gpu_index_live_generation`.

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
- Next measurement run `official_answer_citation_agentic_loop_run_v1` is a
  separate actual measurement artifact family. `ai/eval/indexes/rag-data` was
  rebuilt in WSL2 with Python 3.12, CUDA PyTorch, and CUDA FAISS using
  `AIPIPELINE_WORKER_RAG_FAISS_BUILD_DEVICE=cuda`; embedding ran on `cuda:0`,
  build.json records `faiss_gpu_used=true`, and the agentic loop executed live
  generation. Result rows=29, unique_query_ids=29, scored_count=29, PASS=1,
  CITATION_UNSUPPORTED=25, PARTIAL_OR_UNSUPPORTED=3, promotion_evidence=false.
- Current focused profile is the active feedback loop:
  `python -X utf8 -m pytest ai/tests --rag-current -q`; full ai/tests is broad/nightly diagnostic only.
- Hard cleanup kept only the previous 8 source-of-truth/current files in
  `ai/eval/reports/rag-ingestion/`; the explicitly approved next measurement
  adds 3 current run artifacts under the new run id. Historical report/doc
  artifacts were moved to `D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\hard-cleanup-20260517`.

## Track Board

| Track | Current state | Current metric/evidence | Next action |
|---|---|---|---|
| `text_namu_v2_1` | Official baseline PASS=6/6; agentic measurement executed live generation | Registry-backed official rows=6; measurement rows=6, PASS=0 | Preserve baseline pass state; investigate non-production corpus coverage before any quality conclusion. |
| `xlsx_business_structured` | XLSX runtime candidate report-only PASS=19/19; agentic measurement executed live generation | Registry-backed official rows=19; candidate results JSONL retained; measurement rows=19, PASS=0 | Keep generalization/overfit guards green; no promotion or winner selection. |
| `pdf_business_ocr_mm` | PDF table/value candidate report-only repairs the three remaining failures; agentic measurement executed live generation | Registry-backed official rows=4; candidate results JSONL retained; measurement rows=4, PASS=1 | Keep PDF candidate report-only; do not promote candidate PASS=29/29. |
| Current tests | `--rag-current` profile isolates official metric, source-of-truth, candidate, and guardrail tests | Historical/optional external artifact tests are removed from the current loop | Use focused profile for PDF work; reserve full ai/tests for broad/nightly diagnostics. |

## Current Verification Command

Windows/conda:

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
conda run -n rag-eval-py311 --no-capture-output python -X utf8 -m pytest ai/tests --rag-current -q
conda run -n rag-eval-py311 --no-capture-output python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q
```

Current verification: `--rag-current` 74 passed, 0 skipped, 0 failed;
marker profile 74 passed, 2909 deselected, 0 failed.

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
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v1_results.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v1_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v1_summary.md`
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

1. If the next measurement should represent the official mixed denominator
   rather than the current fixture-all non-production corpus, build a
   source-bound non-production index for that denominator; do not repoint to
   production or candidate index paths.
2. Keep XLSX/PDF runtime candidates report-only; do not use their PASS=29/29
   observation as the immutable baseline or promotion evidence.
3. Keep full ai/tests as broad/nightly diagnostic unless the current focused
   loop explicitly expands.

## Short History

| Date | Compact entry |
|---|---|
| 2026-05-16 | Historical first-run attempt was blocked with `SCORER_BACKEND_UNAVAILABLE`; the active first-run artifacts were later regenerated and this state is superseded. |
| 2026-05-17 | Official first-run baseline scored 29/29 rows and remained partial: PASS=8, CITATION_UNSUPPORTED=11, PARTIAL_OR_UNSUPPORTED=10. |
| 2026-05-17 | XLSX runtime candidate reached PASS=26/29 and XLSX=19/19, report-only and deterministic. |
| 2026-05-17 | PDF table/value candidate reached PASS=29/29, report-only and deterministic, without baseline/gold/denominator/production mutation. |
| 2026-05-17 | Current focused test profile established; full ai/tests kept as broad/nightly diagnostic only. |
| 2026-05-17 | Hard cleanup reduced `ai/eval/reports/rag-ingestion/` to 8 current files and externalized 63 historical report/doc artifacts; use the current verification section for the latest focused-profile count. |
| 2026-05-17 | Opened `official_answer_citation_agentic_loop_run_v1` as a separate measurement artifact family; denominator validation passed, agentic loop was enabled, and the run failed closed before generation because `eval/indexes/rag-data` is unavailable. |
| 2026-05-17 | Rebuilt `ai/eval/indexes/rag-data` in WSL2 Python 3.12 with CUDA PyTorch and CUDA FAISS; reran `official_answer_citation_agentic_loop_run_v1` live generation: rows=29, scored_count=29, PASS=1, promotion_evidence=false. |
