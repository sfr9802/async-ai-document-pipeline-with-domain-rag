# Actual RAG Metric Contract

## Metric Tiers

Strict metrics require human-owned labels and complete gold fields. Unknown-answerability rows are excluded from strict answer, strict evidence, strict citation, and strict end-to-end denominators.

Provisional metrics are iteration signals only. They are not official metrics and cannot be promoted without the required human-owned denominator.

Inferred-answerable metrics may score unknown-answerability rows that contain expected answer and expected evidence, but inference is metric-local only. It does not mutate answerability labels.

Diagnostic metrics are pipeline-health signals only. Examples include schema warnings, empty retrieval, expected-evidence resolution counts, answer/context consistency, citation/context consistency, source-native Hit@K/nDCG, MMR selection diagnostics, vector fallback diagnostics, and failure taxonomy counts.

## Denominator Policy

- Strict answer metrics require human-owned answerability labels and expected answers.
- Strict evidence metrics require human-owned answerability labels and expected evidence.
- Strict citation metrics require human-owned answerability labels, citations, and expected evidence.
- Unknown-answerability rows are excluded from strict answer/evidence/citation denominators.
- Provisional denominators are reported separately from strict denominators.
- Diagnostic denominators must state their scope, such as rows with expected evidence for post-retrieval diagnostics.
- Denominator changes must be visible in `report.json` and the rolling progress log.
- Official metric inputs remain zero unless a separate explicit official-metric gate is opened.

## Candidate Generation

Routine source-native candidate generation may use query text, source-native unit text, source metadata, backend scores, FAISS/id-map hydration, and layer provenance.

It must not use expected answers, expected evidence, qrels, answerability labels, relevance labels, row IDs, query IDs, target IDs, baseline top-k, previous winners, or human decisions.

Expected evidence may be used only after retrieval or in explicit full-corpus diagnostic evidence-resolution mode.

## Evidence Resolution

Full-corpus expected-evidence resolution is review-only. It can report candidate doc IDs, chunk IDs or source atom IDs, evidence bundle IDs, previews, hashes, normalized match info, confidence, score, match reasons, anchor hits, missing numeric/date anchors, and collision warnings.

Resolved candidates are machine recommendations. They do not mutate gold/qrels and do not become official evidence IDs without human review.

## Human Review Packets

Human review CSV output is created only when `--write-human-review-packet` is passed. Human decision fields must remain blank. Machine recommendations are not gold.

Routine runs without that flag keep single-artifact output: `report.json` only.

## Reviewed Mapping Ingest

Reviewed mapping ingest uses a separate explicit input file via `--reviewed-evidence-mapping-csv`. The input file is not the original eval dataset and must contain human-owned decision fields such as `human_accept`, `human_mapping_decision`, or `human_answerability_label`.

The ingest path creates a run-local derived overlay and a patch proposal artifact. It must not overwrite gold, qrels, expected answers, expected evidence, answerability labels, relevance labels, source registries, or production namespaces.

Machine recommendation fields are rejected as human decisions. Blank human decision rows are rejected for ingest. Any strict denominator change caused by accepted human answerability or evidence mapping must be reported in `denominator_changes`, in `diagnostic_metrics`, and in the progress log.

## Vector Contract

BAAI/bge-m3 is the real semantic embedding path when available. `codex-diagnostic-hashing-vector-v1` is a diagnostic fallback and must be reported as such.

Reports must prove whether BGE-M3 was used, whether FAISS was available, whether CPU or GPU was used for embedding/search, and why any fallback happened.
