# Third-Party Data License Notice

This repository's root `LICENSE` applies to original source code, configuration,
tests, documentation, and project-authored scripts in this repository.

It does not grant rights to third-party datasets, public documents, PDFs, XLSX
files, images, OCR annotations, fonts, or benchmark/source artifacts collected
from external providers. Those materials remain governed by their original
source terms.

The current project usage profile for collected external data is:

`NONCOMMERCIAL_INTERNAL_RESEARCH_AND_DEVELOPMENT`

## Operating Rules

- Original manifests are not rewritten to change upstream rights.
- Companion license manifests record source evidence, review status, and usage
  gates for internal diagnostics.
- Public release, redistribution, support evidence, and gold promotion require
  explicit item-level evidence and a separate project decision.
- Unknown, ambiguous, inferred, missing, source-family-only, or restricted
  licenses remain review-required and diagnostic-only by default.
- OCR/MM annotation answers are not embedding/search text.
- OCR/MM rows are not support-eligible by default.
- Hidden XLSX content is not exposed as a user-facing artifact.
- Font files are blocked from user-facing artifacts, generated downloads, and
  public benchmark artifacts unless a separate font license review allows it.

## Current Source-Family Summary

| Source family | Current license posture | Default project use |
|---|---|---|
| `PUBLIC_DATA_PORTAL` / data.go.kr | Item-level catalog JSON evidence is recorded where available. Observed values include unrestricted use, KOGL Type 1, KOGL Type 2 noncommercial, and KOGL Type 4 noncommercial/no-derivatives. Rows without item-level evidence remain review-required. | Internal diagnostics; vector staging only where the row-level license allows it. Public/support/gold still needs separate approval. |
| `SEOUL_OPEN_DATA` | Some dataset pages expose item-level KOGL evidence. Seoul `OA-1176` is recorded as KOGL Type 1. Generic statbook-list rows remain unverified at item level. | Review-first unless item-level KOGL/equivalent evidence is captured. |
| `KOSIS` | Public-use terms are recorded at source-family/terms-page level. International or third-party statistics require extra review. | Internal diagnostics; item-level or equivalent evidence needed before broader promotion. |
| `FUNSD` | Source terms restrict use to noncommercial research/education. | OCR/MM diagnostic-only. No public release, redistribution, support evidence, or gold promotion by default. |
| `NAMU` | Noncommercial-limited source-family terms are recorded. | Metadata hard-negative/internal diagnostic use only. Must not dominate gold/support denominators; no public release by default. |
| `HUGGING_FACE` | Dataset-specific license is required. ChartQA is recorded with GPL-3.0 evidence. DocVQA/CORD mirrors currently have no license in the revisited Hugging Face dataset API and remain review-required. | Dataset-specific review-first; isolate from public/support outputs unless explicitly allowed. |
| `PADDLEOCR_GITHUB` | Apache-2.0 repository license evidence is recorded for repository sample images. | Internal OCR diagnostics and vector staging are allowed by the recorded license posture; public benchmark release still needs separate packaging review. |
| `WIKIMEDIA_COMMONS` | Row metadata may include CC BY-SA or public-domain evidence. Public-domain rows are recorded separately from attribution/share-alike rows. | Internal diagnostics; public release depends on each file's recorded license and attribution/share-alike obligations. |
| `PRISM` | Sample task pages checked during the license refresh did not expose KOGL/equivalent item-level evidence in the captured page text. | Parser smoke or diagnostic-only until item-level rights evidence is captured. |
| `DART` / OpenDART | OpenDART terms are recorded as ambiguous for document/PDF redistribution and vector staging. | Review-required; no document-level promotion without rights evidence. |
| Public institutions such as KEPCO, LH, ALIO, ACRC, Smartcity, local government boards | Public-facing attachment availability is not treated as a license grant. | Review-first or parser-smoke-only unless item-level KOGL/equivalent evidence is captured. |
| AI Hub or similar restricted datasets | Dataset-specific terms are required; third-party transfer restrictions block redistribution by default. | Diagnostic-only unless dataset-specific terms allow more. |
| Fonts | Font files retain their upstream font licenses. | Exclusion/archive/parser stress only unless explicit font-license review allows user-facing artifacts. |

## Generated Evidence Artifacts

The current companion license gate artifacts are generated locally and may be
ignored by git depending on artifact policy:

- `ai-worker/eval/review/retrieval_dataset_supplementation/existing_manifest_license_enriched.json`
- `ai-worker/eval/review/retrieval_dataset_supplementation/existing_manifest_license_enriched.csv`
- `ai-worker/eval/review/retrieval_dataset_supplementation/license_review_required_rows.csv`
- `ai-worker/eval/reports/rag-ingestion/existing_manifest_license_usage_gate.json`
- `ai-worker/eval/reports/rag-ingestion/existing_manifest_license_usage_gate.md`
- `ai-worker/eval/reports/rag-ingestion/existing_manifest_license_summary_by_source.json`
- `ai-worker/eval/reports/rag-ingestion/existing_manifest_license_summary_by_source.md`
- `ai-worker/eval/reports/rag-ingestion/existing_manifest_experiment_readiness.json`
- `ai-worker/eval/reports/rag-ingestion/existing_manifest_experiment_readiness.md`

These files are diagnostic/review companions. They do not change upstream
licenses and do not promote any row to gold/support/public release.
