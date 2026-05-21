# Evaluation harness samples

`ai/eval` keeps RAG/OCR evaluation work separate from production code. This page
is the portfolio-facing sample surface; detailed status and metric history live
in `../../docs/rag-ingestion-progress.md`,
`../../docs/rag-ingestion-measurements.md`, and
`../../docs/rag-ingestion-triage.md`.

Current freeze status: `portfolio_ready_freeze_v1_completed`.

## Current Status

| Item | Reading |
|---|---|
| Primary status | `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed` |
| Portfolio freeze | README/progress/status hygiene only; no new performance experiment |
| Contract path | SearchView -> SourceAtom -> EvidenceBundle -> Citation render |
| Source families | TEXT, PDF, XLSX |
| Comparable live diagnostic | PASS `27/29`; PDF `4/4`, XLSX `19/19`, TEXT `4/6` |
| Retrieval smoke | `v3_4_3` exact-evidence smoke is a 28-query small-sample regression guard only |
| Promotion | No production promotion has been performed |

## Sample Evidence Shapes

These rows show the citation shape without republishing raw third-party corpus
content. They are diagnostic samples, not promotion evidence, official qrels, or
representative product-performance claims.

| Family | Example query id | Response source | Citation truth shape | Public sample policy |
|---|---|---|---|---|
| TEXT | `text_namu_v2_0005` | local LLM synthesis | document/version + text locator hydrated through SourceAtom | Raw source text and long generated answer are omitted from this public-facing sample. |
| PDF | `gq_auto_030` | retained structured adapter output | PDF file identity + page/physical page + bbox/region + matched text locator | Numeric answer details stay in local diagnostic artifacts. |
| XLSX | `gq_auto_012` | retained structured adapter output | workbook + sheet + range/cell + row label + target column/value | Cell values stay in local diagnostic artifacts. |

## Demo / Verification Path

Use the current RAG pytest profile as the lightweight portfolio demo path. It
does not require production DB writes, production index mutation, or new
gold/qrels/labels.

```powershell
python -X utf8 -m pytest ai/tests --rag-current -q
python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q
```

Local generated evidence is stored under `reports/rag-ingestion/`, including
`status.jsonl`, `v3_7_2` top-k rows, `v3_8*` summary artifacts, and the
SourceAtom registry. Those JSON/JSONL artifacts are compact machine evidence and
may be ignored/local in a clean clone; the tracked rolling docs above are the
portable portfolio explanation.

## Boundaries

- Do not read vector metadata as canonical citation truth.
- Do not collapse TEXT/PDF/XLSX or Lane A/B/C into one official score.
- Do not treat `v3_4_3` as representative product performance.
- Do not mutate gold CSVs, qrels, labels, expected answers, supporting evidence,
  denominator registries, production namespace, or immutable baseline artifacts
  during a portfolio freeze.
