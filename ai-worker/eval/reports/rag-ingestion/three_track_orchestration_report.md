# 3-track RAG Orchestration Report

Generated: 2026-05-11 KST

## Status

`implemented_diagnostic_contracts`

This change defines the query-time orchestration contract for three separated
RAG tracks:

| Track | Scope |
|---|---|
| `text_namuwiki_animation` | Namuwiki animation-domain TEXT RAG, not general business text RAG |
| `xlsx_business_structured` | Business spreadsheet structured RAG with sheet/table/row/column context |
| `pdf_business_ocr_mm` | Business OCR/MM document RAG with page/bbox/region context |

The system must not interpret these as one integrated vector quality pool.
Namespace/index scope, retrieval contracts, and eval denominators remain
track-specific.

## Changed files

- `.gitignore`
- `ai-worker/app/capabilities/rag_orchestrator/graph.py`
- `ai-worker/app/capabilities/rag_orchestrator/state.py`
- `ai-worker/app/capabilities/rag_orchestrator/capability.py`
- `ai-worker/app/capabilities/rag_orchestrator/tools.py`
- `ai-worker/app/capabilities/rag_orchestrator/vector_tools.py`
- `ai-worker/app/capabilities/rag_orchestrator/xlsx_tools.py`
- `ai-worker/app/capabilities/rag_orchestrator/pdf_tools.py`
- `ai-worker/eval/harness/rag_ingestion_retrieval_eval.py`
- `ai-worker/scripts/rag_query_intent_routing_matrix.py`
- `ai-worker/scripts/rag_xlsx_retrieval_performance_diagnostic.py`
- `ai-worker/tests/test_rag_query_orchestrator_graph.py`
- `ai-worker/tests/test_rag_query_orchestrator_capability.py`
- `ai-worker/tests/test_rag_query_orchestrator_vector_tools.py`
- `ai-worker/tests/test_retrieval_eval_harness.py`
- `ai-worker/tests/test_rag_query_intent_routing_matrix.py`
- `docs/eval/denominator_policy.md`
- `docs/rag-ingestion-progress.md`
- `docs/rag-ingestion/xlsx-retrieval/README.md`
- `docs/track_b_text_retrieval_e2e/README.md`
- `docs/track-c-pdf-embedding-preparation/README.md`
- `ai-worker/eval/reports/rag-ingestion/README.md`
- `ai-worker/eval/reports/rag-ingestion/three_track_orchestration_report.md`

## Route schema

The route decision payload is now carried in orchestrator state, capability
output, and trace:

- `route`
- `routes`
- `route_confidence`
- `reason`
- `required_evidence_type`
- `allow_fallback`
- `fallback_routes`
- `multi_route`
- `deterministic_hints`
- `metadata_guards`
- `llm_decision_used`
- `post_retrieval_validation`

Route selection uses deterministic query hints plus policy/source metadata
guards. Optional LLM suggestions can only narrow inside the guarded route set;
they cannot relax source type, parser, or namespace constraints. XLSX/PDF
questions are blocked from silently falling into `text_namuwiki_animation` when
policy metadata indicates spreadsheet or PDF input.

## Namespace and index scope policy

- `text_namuwiki_animation`: TEXT source type, namu-v4 domain rows, separate
  denominator from legacy B-app smoke.
- `xlsx_business_structured`: SPREADSHEET source type, XLSX parser/version
  scope, hidden-safe spreadsheet evidence contract.
- `pdf_business_ocr_mm`: PDF source type, PDF parser/version scope, page and
  layout metadata contract.

The fake graph and vector wrappers still use post-filtering in the POC path.
Production readiness still requires a safe retrieval API that enforces tenant,
ACL, source type, parser version, index version, and embedding status before or
inside vector ranking.

## XLSX evidence contract

XLSX candidate retrieval and context assembly are separated. The assembled
context includes:

- `file`
- `sheet`
- `table_id`
- `table_range`
- `matched_cells`
- `header_rows`
- `target_rows`
- `target_columns`
- `row_values`
- `column_headers`
- `nearby_rows`
- `merged_cell_context`
- `table_title_candidate`
- `score`

Context assembly policy: same row, header row, target column header, nearby
rows, merged parent cells, sheet name, and table title candidate. Flatten-only
evidence is diagnostic fallback and receives
`xlsx_context_diagnostic_only_missing_structure`.

## PDF evidence contract

PDF candidate retrieval and context assembly are separated. The assembled
context includes:

- `file`
- `page`
- `region_type`
- `bbox`
- `matched_text`
- `section_heading`
- `table_caption_footnote`
- `nearby_paragraphs`
- `OCR_confidence`
- `score`

Context assembly policy: matched block, page number, bbox, section heading,
table/caption/footnote, nearby paragraph, and OCR confidence if available.
Missing OCR/MM layout metadata is diagnostic-only and receives
`pdf_context_diagnostic_only_missing_layout`.

## Eval denominator policy

The retrieval eval harness reports route/xlsx/pdf metric families separately.
Cross-track averages must not be interpreted as quality:

- route: `routing_accuracy`, `wrong_route_rate`, `fallback_success_rate`,
  `multi_route_success_rate`, `low_confidence_route_count`
- xlsx: `target_cell_hit`, `target_row_hit`, `header_included`,
  `target_column_included`, `surrounding_context_included`,
  `sheet_resolution_accuracy`
- pdf: `page_hit`, `region_hit`, `bbox_available`,
  `table_or_caption_included`, `nearby_paragraph_included`,
  `OCR_confidence_available`

Route metrics remain diagnostic-only until route gold labels and fallback
outcomes are human-reviewed. Gold evidence creation, evidence judgment,
answerability labels, and final gold policy remain user-owned.

## Verification

```text
python -m py_compile app/capabilities/rag_orchestrator/state.py app/capabilities/rag_orchestrator/graph.py app/capabilities/rag_orchestrator/xlsx_tools.py app/capabilities/rag_orchestrator/pdf_tools.py app/capabilities/rag_orchestrator/tools.py app/capabilities/rag_orchestrator/vector_tools.py app/capabilities/rag_orchestrator/capability.py eval/harness/rag_ingestion_retrieval_eval.py scripts/rag_query_intent_routing_matrix.py scripts/rag_xlsx_retrieval_performance_diagnostic.py
```

Result: passed.

```text
python -m pytest -q -p no:cacheprovider tests/test_rag_query_orchestrator_graph.py tests/test_rag_query_orchestrator_capability.py tests/test_rag_query_orchestrator_vector_tools.py tests/test_retrieval_eval_harness.py tests/test_rag_query_intent_routing_matrix.py
```

Result: `59 passed, 8 warnings`.

## Remaining risks

- Production vector retrieval still uses bounded overfetch plus post-filtering in
  this POC wrapper; pre-ranking fail-closed filters are still required.
- Route metrics are diagnostic-only until route gold labels exist.
- XLSX/PDF answer-generation denominators remain `0` until human-reviewed
  expected answer/evidence and answerability labels exist.
- PDF layout/OCR confidence coverage depends on parser metadata availability;
  missing layout stays diagnostic-only.
