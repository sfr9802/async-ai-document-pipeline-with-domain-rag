# Tuning Readiness Report

## Status

- Status: `READY_FOR_DOCUMENTED_SILVER_ONLY_TUNING_STEP`.
- Expensive tuning run: `false`.
- Standard command found: `true`.
- Active tuning sweep allowed: `false`.
- Recommended next step: review the generated silver manifest, then create an explicit silver-only tuning config before running `python scripts\phase7_human_gold_tune.py`; evaluate only on frozen cleaned gold candidates after that.

## Inputs

- `text_review_csv`: `ai-worker/eval/review/text_namu_v2_gold_review/text_namu_v2_gold_review_pack - text_namu_v2_gold_review_pack.csv` (`sha256=5a2407089a5c5c22cf8f0101b76bba23a8c991fe7d2fa3f7fb89e395b56e4d0a`, `bytes=218141`).
- `pdf_file_lookup_review_csv`: `ai-worker/eval/review/pdf_supplemental_gold_review/pdf_gold_review_pack_manual_v1_file_lookup_companion - pdf_gold_review_pack_manual_v1_file_lookup_companion.csv` (`sha256=c77f8b431c2cef5dffac5a968606c309eb653ec506efeb7ad37190c45f8b2b9a`, `bytes=29850`).
- `official_denominator_registry`: `ai-worker/eval/eval_queries/official_denominator_registry.json` (`sha256=8f5e6bde33ff7cd68cfcc3d43bca976ca59799b78e490fab440ec2651c52fc22`, `bytes=8455`).

## Output Files

- `text_gold_main_positive_clean.csv`: `ai-worker/eval/review/gold_silver_tuning/text_gold_main_positive_clean.csv`
- `text_gold_abstain_diagnostic_clean.csv`: `ai-worker/eval/review/gold_silver_tuning/text_gold_abstain_diagnostic_clean.csv`
- `text_gold_deferred_or_excluded_clean.csv`: `ai-worker/eval/review/gold_silver_tuning/text_gold_deferred_or_excluded_clean.csv`
- `pdf_file_lookup_gold_positive_clean.csv`: `ai-worker/eval/review/gold_silver_tuning/pdf_file_lookup_gold_positive_clean.csv`
- `pdf_file_lookup_diagnostic_clean.csv`: `ai-worker/eval/review/gold_silver_tuning/pdf_file_lookup_diagnostic_clean.csv`
- `pdf_file_lookup_deferred_or_excluded_clean.csv`: `ai-worker/eval/review/gold_silver_tuning/pdf_file_lookup_deferred_or_excluded_clean.csv`
- `silver_text_positive_train.csv`: `ai-worker/eval/review/gold_silver_tuning/silver_text_positive_train.csv`
- `silver_text_hard_negative_train.csv`: `ai-worker/eval/review/gold_silver_tuning/silver_text_hard_negative_train.csv`
- `silver_text_abstain_diagnostic.csv`: `ai-worker/eval/review/gold_silver_tuning/silver_text_abstain_diagnostic.csv`
- `silver_pdf_file_lookup_positive_train.csv`: `ai-worker/eval/review/gold_silver_tuning/silver_pdf_file_lookup_positive_train.csv`
- `silver_pdf_file_lookup_hard_negative_train.csv`: `ai-worker/eval/review/gold_silver_tuning/silver_pdf_file_lookup_hard_negative_train.csv`
- `silver_manifest.csv`: `ai-worker/eval/review/gold_silver_tuning/silver_manifest.csv`

## Denominator Policies

- Official denominator registry was not updated.
- Cleaned TEXT/PDF outputs are candidate or diagnostic artifacts, not automatic official gold.
- Silver rows are tuning-only and `official_gold=false`.
- PDF FILE lookup remains separate from PDF content retrieval.

## Next Tuning Entry Point

A standard tuning command exists, but the active config blocks tuning sweeps by default.

```powershell
python scripts\phase7_human_gold_tune.py --help
```

## 2026-05-08 Silver-Only First Pass

- Status: `PASS`.
- Config: `ai-worker/eval/configs/silver_only_tuning_config.yaml`.
- Baseline: `ai-worker/eval/reports/rag-ingestion/silver_tuning_baseline_report.md`, `ai-worker/eval/reports/rag-ingestion/silver_tuning_baseline_report.json`.
- Silver tuning: `ai-worker/eval/reports/rag-ingestion/silver_tuning_run_report.md`, `ai-worker/eval/reports/rag-ingestion/silver_tuning_run_report.json`.
- Frozen gold eval: `ai-worker/eval/reports/rag-ingestion/gold_eval_after_silver_tuning_report.md`, `ai-worker/eval/reports/rag-ingestion/gold_eval_after_silver_tuning_report.json`.
- Delta: `ai-worker/eval/reports/rag-ingestion/before_after_metric_delta.md`.
- Selection data: silver only; frozen gold training rows `0`.
- Selected TEXT profile: `tuned_text_section_boost_bm25`.
- Selected PDF FILE lookup profile: `baseline_pdf_file_identity_tokens`.
- Gold leakage guard: `PASS`; exact query, query_id, source_query_id, and expected-id overlaps remain `0`.
- Official denominator registry changed: `false`.
- Standard Phase 7 report-only refresh: `python -m scripts.run_phase7_silver_500_full_eval --reports-root eval/reports --report-only` passed without broad indexing.
- Note: this pass is a diagnostic profile-selection bridge for the cleaned/silver artifacts, not a production config promotion.
