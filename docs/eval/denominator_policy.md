# Eval Denominator Policy

## Official denominator

Only rows with:

```text
gold_status=gold
```

enter official retrieval metrics and official E2E pass-rate denominators.

The machine-readable source of truth is:

```text
ai-worker/eval/eval_queries/official_denominator_registry.json
```

Rows with:

```text
gold_status=candidate
gold_status=diagnostic_only
```

are excluded from official denominators.

## What still gets logged

`candidate` and `diagnostic_only` rows are still written to:

- `retrieval_results.jsonl`
- `e2e_llm_io.jsonl`
- `e2e_judgements.jsonl`
- `summary.json` failure and verdict breakdowns

This keeps raw I/O and failure analysis available without inflating official
metrics.

## Human-owned policy boundaries

Humans own these decisions:

- gold-set creation
- gold-set review
- expected answer judgement
- expected evidence judgement
- relevance and answerability labels
- final gold policy changes

Codex must not promote a row to `gold` when expected answer, expected evidence,
or answerability is not already sufficiently established by the repo artifacts.

## Conservative defaults used in the current snapshot

- Track A reviewed XLSX positives are treated as `gold` for denominator
  purposes because the reviewed CSV has bound expected evidence and positive
  review decisions. The evidence role still remains diagnostic, not promotion.
- Track B bound namu-v4 rows are treated as `gold`; `needs_review` rows are
  `diagnostic_only`.
- Track C PDF rows use C7 conservative policy classification:
  - C7 current-policy positive controls are `gold`.
  - C7 gold-policy change candidates are `candidate`.
  - Remaining C7 review rows are `diagnostic_only`.
  - Only the `gold` controls enter the official Track C denominator.

## 3-track denominator split

Current orchestration uses three named tracks and each track owns its own
namespace, index scope, retrieval contract, and eval denominator.

| Track | Domain | Denominator rule |
|---|---|---|
| `text_namuwiki_animation` | Namuwiki animation-domain TEXT RAG, not general business text RAG | Use only namu-v4 bound TEXT rows. Legacy B-app TEXT smoke remains diagnostic-only and cannot be averaged into this track. |
| `xlsx_business_structured` | Business spreadsheet structured RAG | Use XLSX retrieval/evidence rows with sheet/range/table/row/column evidence. XLSX answer-generation denominator remains separately governed and currently `0`. |
| `pdf_business_ocr_mm` | Business OCR/MM document RAG | Use PDF rows only when page/layout evidence is policy-bound. Rows without enough page/bbox/region/table/caption evidence stay `diagnostic_only`. |

Reports must not interpret a single overall mean across TEXT/XLSX/PDF as
system quality. If a report includes an overall field for convenience, it must
also include track-level denominators and state that cross-track averaging is
diagnostic only.

Route-decision metrics are a separate denominator family:

- `routing_accuracy`
- `wrong_route_rate`
- `fallback_success_rate`
- `multi_route_success_rate`
- `low_confidence_route_count`

These require route gold labels and fallback outcome labels. Until those human
labels exist, route metrics are reported as `diagnostic_only`.

## Archived legacy CSVs

Intermediate and mixed CSVs were removed from the active eval-query directory.
Archive copies are retained only for provenance:

```text
archive/results/2026-05-05-eval-query-lineage-cleanup/csv/
```

Archived files are provenance only. They must not be selected by default for
promotion or baseline comparison.

## Ambiguous non-gold rows

Do not ask for an interactive decision during baseline capture. If a row is
ambiguous and not clearly gold, mark it:

```text
gold_status=diagnostic_only
```

Then record the reason in the report and progress entry.

## Dry-run E2E denominator

When live LLM execution is not performed, official E2E pass rate is reported as
`n/a`, not as zero. The official gold denominator is still recorded so a later
live run can compare against the same case set.
