# Actual RAG Failure Taxonomy

Canonical failure labels are report-level categories for triage. Legacy labels may still appear for backward compatibility, but new reports also normalize them into `canonical_failure_labels`.

## Canonical Labels

- `gold_missing_answerability`: Human-owned answerability is absent, so strict answer/evidence denominators are unavailable.
- `expected_evidence_id_unresolved`: Expected evidence lacks a resolved human-approved ID or only has review-only candidates.
- `corpus_absent`: Expected evidence text is not present in the source-native corpus diagnostic probe.
- `present_not_retrieved`: Expected evidence is present in the source-native corpus but was not retrieved in the selected top-k.
- `retrieved_not_validated`: Context was retrieved but answer/evidence/citation validation did not pass.
- `answer_judge_fail`: Provisional answer judge failed or returned a non-passing judgment.
- `citation_wrong`: Citation is missing, points to the wrong evidence, or does not cover required evidence.
- `should_abstain_but_answered`: An unanswerable row produced a non-abstention answer.
- `should_answer_but_abstained`: An answerable row abstained.
- `metric_not_applicable`: The metric denominator is closed for this row.
- `schema_warning`: The row is executable but has schema warnings that affect interpretation.
- `guardrail_violation`: A protected boundary was violated or the report failed a guardrail check.

Reviewed mapping ingest errors use existing canonical categories: malformed or blank human decision input is a `schema_warning`-class problem before scoring, while machine recommendations treated as human decisions or any gold/qrels/label mutation would be a `guardrail_violation`.

## Report Rules

Every failed item should carry actionable labels. If a legacy label is more specific, keep it and also normalize to the canonical category.

Diagnostic-only limitations must stay diagnostic-only. They cannot be used as product-readiness, live-readiness, promotion, or official-metric evidence.

## Common Mappings

- `strict_metric_not_applicable` maps to `metric_not_applicable`.
- `expected_evidence_resolution_unresolved` maps to `expected_evidence_id_unresolved`.
- `evidence_not_retrieved` maps to `present_not_retrieved`.
- `citation_missing` maps to `citation_wrong`.
- `answered_unanswerable` and `abstention_failed` map to `should_abstain_but_answered`.
