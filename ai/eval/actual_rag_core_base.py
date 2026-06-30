from __future__ import annotations

import argparse
import csv
import heapq
import hashlib
import importlib.util
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
AI_DIR = ROOT / "ai"
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from ai.eval.report_paths import (
    ACTUAL_RAG_REPORT_ROOT,
    LEGACY_RAG_INGESTION_REPORT_ROOT,
    LEGACY_RAG_INGESTION_STATUS_JSONL,
)
from ai.eval.actual_rag_dataset import (
    ANSWERABILITY_VALUES,
    DatasetSchemaError,
    EvalItem,
    ExpectedEvidence,
    _canonical_answerability,
    _expected_answer_aliases,
    _expected_evidence_rows,
    _load_dataset_rows,
    _locator_evidence_fields,
    load_eval_dataset,
)
from ai.eval.actual_rag_agentic_xlsx import (
    AGENTIC_XLSX_ANCHOR_TAXONOMY_CATEGORIES,
    AGENTIC_XLSX_AXIS_INSPECTOR_SCHEMA_VERSION,
    AGENTIC_XLSX_AXIS_REPAIR_DIAGNOSTIC_SCHEMA_VERSION,
    AGENTIC_XLSX_COORDINATOR_SCHEMA_VERSION,
    AGENTIC_XLSX_PROTECTED_ANCHOR_VERIFIER_SCHEMA_VERSION,
    AGENTIC_XLSX_QUERY_ANCHOR_TAXONOMY_SCHEMA_VERSION,
    AGENTIC_XLSX_REGATED_CANDIDATE_SIMULATOR_SCHEMA_VERSION,
    AGENTIC_XLSX_REQUIRED_AXIS_MATERIALIZER_SCHEMA_VERSION,
    AGENTIC_XLSX_REPAIR_EXPLAINER_SCHEMA_VERSION,
    AGENTIC_XLSX_REPAIR_FAILURE_FAMILIES,
    AGENTIC_XLSX_TOOL_SEQUENCE,
    AgenticXlsxAxisInspectionRecord,
    AgenticXlsxCoordinatorRecord,
    AgenticXlsxProtectedAnchorVerifierRecord,
    AgenticXlsxQueryAnchorTaxonomyRecord,
    AgenticXlsxRegatedCandidateSimulationRecord,
    AgenticXlsxRequiredAxisMaterializerRecord,
    AgenticXlsxRepairExplanationRecord,
    _agentic_xlsx_bool,
    _agentic_xlsx_clean_tuple,
    _agentic_xlsx_record_value,
    _agentic_xlsx_required_string,
    agentic_xlsx_protected_anchor_verifier_tool,
    agentic_xlsx_query_anchor_taxonomy_tool,
    validate_agentic_xlsx_protected_anchor_verifier_output,
    validate_agentic_xlsx_query_anchor_taxonomy_output,
)
from ai.eval.actual_rag_judging import (
    DEFAULT_ABSTENTION_PHRASES,
    GENERIC_ANCHOR_STOPWORDS,
    KOREAN_GENERIC_SUFFIXES,
    HeuristicJudgeAdapter,
    _anchor_in_text,
    _anchor_requirements_satisfied,
    _anchor_stopwords,
    _candidate_anchors,
    _evidence_match_anchors,
    _evidence_resolution_anchors,
    _is_generic_anchor,
    _numeric_or_date_anchors,
    _token_overlap_ratio,
    _token_set,
    abstains,
    answer_correct,
    heuristic_judge_answer,
    normalize_answer_text,
)
from ai.eval.xlsx_locator_run_store import (
    XLSX_LOCATOR_RUN_STORE_BACKEND,
    XLSX_LOCATOR_RUN_STORE_FILENAME,
    XLSX_LOCATOR_RUN_STORE_TABLES,
    XlsxLocatorEvidenceCandidateRecord,
    XlsxLocatorGateDeltaRecord,
    XlsxLocatorGuardrailRecord,
    XlsxRequiredAxisMaterializerActionRecord,
    XlsxRequiredAxisMaterializerRunRecord,
    XlsxRequiredAxisMaterializerRunStore,
    XlsxLocatorRunRecord,
    XlsxLocatorRunStore as _XlsxLocatorRunStoreBase,
    XlsxLocatorRunStoreDependencies,
    XlsxLocatorToolUseRecord,
    validate_xlsx_required_axis_materializer_run_store,
)
from app.capabilities.rag.generation import ExtractiveGenerator, RetrievedChunk
from ai.eval.weaviate_source_atom import (
    WEAVIATE_BACKEND_ALIASES,
    WEAVIATE_CANDIDATE_INPUT_POLICY,
    WeaviateSourceAtomAdapter,
    WeaviateSourceAtomConfig,
    build_default_weaviate_adapter,
    plan_weaviate_retrieval_route,
)
from scripts import rag_local_llm_expected_answer_generation_v1 as LOCAL_LLM_HELPER


DEFAULT_TOP_K_VALUES = (1, 3, 5, 10)
RUN_KIND = "actual_rag_eval_metric_generation_nonprod"
SCHEMA_VERSION = "actual_rag_eval.v1"
REGISTRY_SCHEMA_VERSION = "actual_rag_eval.run_registry.v1"
LATEST_POINTER_SCHEMA_VERSION = "actual_rag_eval.latest_pointer.v1"
STATUS_EVENT_SCHEMA_VERSION = "actual_rag_eval.run_status_event.v1"
PORTFOLIO_COMPARISON_SCHEMA_VERSION = "actual_rag_eval.portfolio_experiment_comparison.v1"
CORPUS_COVERAGE_AUDIT_SCHEMA_VERSION = "actual_rag_eval.corpus_coverage_audit.v1"
RESPONSE_QUALITY_INPUT_SUMMARY_SCHEMA_VERSION = "actual_rag_eval.response_quality_input_summary.v1"
XLSX_PDF_RESIDUAL_BREAKDOWN_SCHEMA_VERSION = "actual_rag_eval.xlsx_pdf_residual_breakdown.v1"
RESIDUAL_ANCHOR_MATRIX_SCHEMA_VERSION = "actual_rag_eval.residual_anchor_matrix.v1"
SOURCE_NATIVE_AXIS_PROVENANCE_SCHEMA_VERSION = "actual_rag_eval.source_native_axis_provenance.v1"
PDF_SOURCE_NATIVE_DECOMPOSITION_SCHEMA_VERSION = "actual_rag_eval.pdf_source_native_decomposition.v1"
HEURISTIC_RISK_LEDGER_SCHEMA_VERSION = "actual_rag_eval.heuristic_risk_ledger.v1"
METRIC_CONTINUITY_CHECKPOINT_SCHEMA_VERSION = "actual_rag_eval.metric_continuity_checkpoint.v1"
AGENTIC_PLANNER_DRY_RUN_SCHEMA_VERSION = "actual_rag_eval.agentic_planner_dry_run.v1"
AGENTIC_PLANNER_EXECUTE_ONCE_SCHEMA_VERSION = "actual_rag_eval.agentic_planner_execute_once.v1"
LLM_QUERY_ANCHOR_CLASSIFIER_PROMPT_VERSION = "llm_query_anchor_classifier_v1"
LLM_QUERY_ANCHOR_CLASSIFIER_INPUT_POLICY = "query_text_only_no_eval_fields_or_baseline"
QUERY_EVIDENCE_PLANNER_PROMPT_VERSION = "query_evidence_planner_v1"
QUERY_EVIDENCE_PLANNER_INPUT_POLICY = "query_text_only_no_eval_fields_or_baseline"
XLSX_LOCATOR_TOOL_EXECUTE_ONCE_SCHEMA_VERSION = "actual_rag_eval.xlsx_locator_tool_execute_once.v1"
XLSX_LOCATOR_QUERY_ANCHOR_TOOL_ACCEPTANCE_DIAGNOSTIC_SCHEMA_VERSION = (
    "actual_rag_eval.xlsx_locator_query_anchor_tool_acceptance_diagnostic.v1"
)
XLSX_LOCATOR_TOOL_NAME = "xlsx_locator_tool_v1"
XLSX_LOCATOR_TOOL_POLICY = "source_owned_locator_only_no_raw_xlsx_query_time_parsing"
XLSX_LOCATOR_TOOL_OUTPUT_POLICY = "selected_evidence_candidate_must_pass_unchanged_gate"
XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET = 5
XLSX_LOCATOR_SOURCE_OWNED_DIVERSIFICATION_POLICY = "source_owned_sheet_table_range_axis_budget_v1"
XLSX_LOCATOR_SIBLING_ROW_COMPOSITE_SOURCE = "source_owned_sibling_row_context"
XLSX_LOCATOR_SOURCE_ROW_CONTEXT_FAIL_CLOSED_POLICY = (
    "requires_same_doc_sheet_range_row_index_for_sibling_row_context"
)
PDF_LOCATOR_TOOL_NAME = "pdf_locator_tool_v1"
PDF_LOCATOR_TOOL_POLICY = "source_owned_pdf_locator_only_no_raw_pdf_query_time_parsing"
PDF_LOCATOR_TOOL_OUTPUT_POLICY = "selected_evidence_candidate_must_pass_unchanged_gate"
XLSX_LOCATOR_TABLE_ROW_TEXT_WINDOW_BEFORE = 180
XLSX_LOCATOR_TABLE_ROW_TEXT_WINDOW_AFTER = 760
XLSX_LOCATOR_SYNTHETIC_TABLE_ID_PREFIX = "xlsx_locator_table:"
AGENTIC_LOOP_REVIEW_SCHEMA_VERSION = "actual_rag_eval.agentic_loop_review.v1"
AGENTIC_PLANNER_MODE_CHOICES = ("off", "dry-run", "execute-once")
AGENTIC_PLANNER_EXECUTE_ONCE_PROBE_TOP_K_INCREMENT = 1
AGENTIC_PLANNER_LLM_RETRY_INPUT_POLICY = (
    "query_text_selected_evidence_gate_diagnostics_previous_bounded_answer_preview_only_no_gold_qrels_labels_ids_or_baseline"
)
AGENTIC_PLANNER_LLM_RETRY_PROMPT_VERSION = "agentic_planner_selected_evidence_llm_retry_v1"
AGENTIC_PLANNER_RUN_LOCAL_MEMORY_INPUT_POLICY = (
    "run_local_selected_evidence_memory_query_text_and_source_evidence_only_no_ids_expected_qrels_labels_or_baseline"
)
AGENTIC_PLANNER_FAILURE_CLASSES = (
    "missing_query_anchor",
    "insufficient_evidence",
    "collision",
    "corpus_absent",
    "tool_required_pdf",
    "tool_required_xlsx",
    "unsupported_generation",
    "no_safe_action",
)
AGENTIC_PLANNER_ACTIONS = (
    "query_text_only_reformulation",
    "source_owned_same_doc_residual",
    "route_selected_probe",
    "run_local_memory_reuse",
    "pdf_locator_tool",
    "xlsx_cell_or_table_tool",
    "selected_evidence_llm_rewrite",
    "deterministic_abstain",
)
AGENTIC_PLANNER_GUARDRAIL_FLAGS = (
    "gold_or_qrels_mutation",
    "expected_fields_used_for_planner_selection",
    "query_id_used_for_planner_selection",
    "row_id_used_for_planner_selection",
    "target_id_used_for_planner_selection",
    "qrels_used_for_planner_selection",
    "labels_used_for_planner_selection",
    "baseline_topk_or_legacy_outputs_used",
    "row_specific_alias_or_shortcut_used",
    "retrieval_executed",
    "tool_call_executed",
    "llm_retry_executed",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
    "evidence_gate_loosened",
    "retrieved_context_only_citation_promoted",
    "official_metric",
    "production_routing_opened",
    "protected_namespace_mutation",
)
AGENTIC_PLANNER_FORBIDDEN_DECISION_FIELDS = {
    "case_id",
    "query_id",
    "row_id",
    "target_id",
    "answerability",
    "answerability_label",
    "expected_answer",
    "expected_evidence",
    "supporting_evidence",
    "qrels",
    "qrel",
    "label",
    "labels",
    "baseline_topk",
    "legacy_outputs",
    "source_title",
    "workbook",
    "gold_locator",
    "target_locator",
    "normalized_value",
    "formula",
    "prompt",
    "response",
    "raw_prompt",
    "raw_response",
    "prompt_payload",
    "response_payload",
    "raw_prompt_payload",
    "raw_response_payload",
}
XLSX_LOCATOR_SOURCE_OWNED_FIELDS = (
    "source_atom_id",
    "evidence_bundle_id",
    "doc_id",
    "sheet",
    "cell_range",
    "cell",
    "row_index_1based",
    "row_label",
    "column_label",
    "target_column",
    "header",
    "header_path",
    "table_id",
    "synthetic_table_id",
    "display_value",
)
XLSX_LOCATOR_DIAGNOSTIC_ONLY_FORBIDDEN_SEEN_FIELDS = {
    "file_name",
    "source_file_name",
    "source_title",
    "title",
    "workbook",
    "workbook_id",
    "workbook_version_id",
}
XLSX_PDF_RESIDUAL_CLASSIFICATIONS = (
    "candidate_absent",
    "candidate_present_anchor_missing",
    "selected_evidence_absent",
    "selected_evidence_has_value_missing_axis",
    "selected_evidence_has_axis_missing_value",
    "gate_support_text_drops_source_metadata",
    "answer_generation_only_failure",
    "citation_only_failure",
)
XLSX_PDF_RESIDUAL_EXCLUDED_CLASSIFICATIONS = ("no_residual", "not_xlsx_pdf")
XLSX_RESIDUAL_AXIS_FIELDS = (
    "sheet",
    "cell",
    "cell_range",
    "column_label",
    "header",
    "header_path",
    "row_index_1based",
    "row_label",
    "table_id",
    "target_column",
)
PDF_RESIDUAL_AXIS_FIELDS = (
    "page_number",
    "bbox",
    "block_index",
    "column_label",
    "row_label",
    "section_title",
    "table_caption",
)
XLSX_PDF_RESIDUAL_FORBIDDEN_SHORTCUT_FIELDS = frozenset(
    {
        "answerability",
        "answerability_label",
        "baseline_topk",
        "case_id",
        "expected_answer",
        "expected_evidence",
        "formula",
        "gold_locator",
        "label",
        "labels",
        "legacy_outputs",
        "normalized_value",
        "qrel",
        "qrels",
        "query_id",
        "row_id",
        "target_id",
        "target_locator",
    }
)
XLSX_LOCATOR_FORBIDDEN_TEXT_MARKERS = (
    "answerability",
    "answerability_label",
    "baseline_topk",
    "case_id",
    "expected_answer",
    "expected_evidence",
    "file_name",
    "formula",
    "gold_locator",
    "label",
    "labels",
    "legacy_outputs",
    "normalized_value",
    "prompt_payload",
    "qrel",
    "qrels",
    "query_id",
    "raw_prompt",
    "raw_prompt_payload",
    "raw_response",
    "raw_response_payload",
    "raw_tool_payload",
    "row_id",
    "source_path",
    "source_title",
    "source_workbook",
    "target_id",
    "target_locator",
    "title",
    "tool_payload",
    "workbook",
    "workbook_id",
    "workbook_version_id",
)
HEURISTIC_RISK_ALLOWED_CLASSIFICATIONS = (
    "global_normalization",
    "source_derived_index_feature",
    "query_text_only_reformulation",
    "diagnostic_probe_only",
)
HEURISTIC_RISK_ALL_CLASSIFICATIONS = (
    *HEURISTIC_RISK_ALLOWED_CLASSIFICATIONS,
    "forbidden_eval_row_shortcut",
)
HEURISTIC_RISK_FORBIDDEN_ACTIVE_FLAGS = (
    "uses_query_id_or_row_id_or_target_id",
    "uses_expected_answer_or_evidence",
    "uses_qrels_or_labels",
    "per_row_alias_table",
    "composer_or_gate_loosening_for_single_residual",
)
REPORT_ROOT = ACTUAL_RAG_REPORT_ROOT
STATUS_JSONL_PATH = LEGACY_RAG_INGESTION_STATUS_JSONL
SOURCE_NATIVE_DIAGNOSTIC_INDEX_DIR = AI_DIR / "eval" / "indexes" / "rag-data-all-source-citable-nonprod-v1"
SOURCE_NATIVE_BGE_M3_INDEX_DIR = AI_DIR / "eval" / "indexes" / "rag-data-all-source-citable-nonprod-bge-m3-v1"
def _source_native_index_has_bge_m3_artifacts(index_dir: Path) -> bool:
    build_path = index_dir / "build.json"
    index_path = index_dir / "faiss.index"
    manifest_path = index_dir / "search_view_manifest.jsonl"
    if not (build_path.exists() and index_path.exists() and manifest_path.exists()):
        return False
    try:
        build = json.loads(build_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(build, Mapping):
        return False
    return "bge-m3" in str(build.get("embedding_model") or "").strip().casefold()


def select_source_native_index_dir() -> Path:
    explicit = str(os.environ.get("ACTUAL_RAG_EVAL_SOURCE_NATIVE_INDEX_DIR") or "").strip()
    if explicit:
        return Path(explicit)
    if _source_native_index_has_bge_m3_artifacts(SOURCE_NATIVE_BGE_M3_INDEX_DIR):
        return SOURCE_NATIVE_BGE_M3_INDEX_DIR
    return SOURCE_NATIVE_DIAGNOSTIC_INDEX_DIR


SOURCE_NATIVE_INDEX_DIR = select_source_native_index_dir()
SOURCE_NATIVE_SEARCH_VIEW_MANIFEST_PATH = SOURCE_NATIVE_INDEX_DIR / "search_view_manifest.jsonl"
SOURCE_NATIVE_SOURCE_REGISTRY_PATH = AI_DIR / "eval" / "source_registry" / "source_atom_registry_v1.jsonl"
SOURCE_NATIVE_MMR_DIAGNOSTIC_LAMBDA = 0.65
SOURCE_NATIVE_LEGACY_CLEANUP_RUN_ID = "actual_rag_eval_source_native_legacy_cleanup_nonprod"
SOURCE_NATIVE_LEGACY_CLEANUP_REPORT_PATH = (
    LEGACY_RAG_INGESTION_REPORT_ROOT / "runs" / SOURCE_NATIVE_LEGACY_CLEANUP_RUN_ID / "report.json"
)
REGISTRY_FILENAME = "runs.jsonl"
SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
REPORT_ARTIFACT_FILENAMES = (
    "report.json",
    "human_review_packet.csv",
    "rag_eval_items.jsonl",
    "rag_eval_summary.json",
    "rag_eval_report.md",
    "evidence_resolution_candidates.jsonl",
    "evidence_resolution_review.md",
    "evidence_mapping_review_packet.csv",
    "evidence_mapping_review_packet.jsonl",
    "evidence_mapping_review_packet.md",
    "evidence_mapping_packet_summary.json",
)
SOURCE_NATIVE_LEGACY_CLEANUP_CLASSIFICATIONS = (
    "ACTIVE_SOURCE_NATIVE_KEEP",
    "EXPLICIT_LEGACY_DEBUG_KEEP",
    "EXPLICIT_LEGACY_COMPARISON_KEEP",
    "PROTECTED_HOLD",
    "DOCS_ONLY_UPDATE",
    "SAFE_TRANSIENT_DELETE",
    "SAFE_GENERATED_DELETE",
    "DEPRECATE_FAIL_CLOSED",
    "REVIEW_MANUAL_HOLD",
)
LOWER_IS_BETTER_COMPARISON_METRICS = {
    "retrieval_empty_rate",
    "bm25_retrieval_empty_rate",
    "vector_retrieval_empty_rate",
    "hybrid_retrieval_empty_rate",
    "generation_empty_rate",
    "citation_empty_rate",
    "pipeline_error_count",
    "schema_warning_count",
    "gold_missing_count",
    "missing_expected_answer_count",
    "missing_expected_evidence_count",
    "missing_answerability_label_count",
    "expected_evidence_id_missing_count",
    "expected_evidence_id_unresolved_count",
    "source_native_retrieval_empty_rate",
    "searchunit_retrieval_empty_rate",
    "source_native_target_span_present_but_not_retrieved_count",
    "source_native_target_span_absent_count",
    "searchunit_target_span_absent_count",
    "both_surfaces_fail_count",
}
RESOLVED_EVIDENCE_COMPARISON_METRICS = {
    "resolved_evidence_available_rate",
    "citation_matches_resolved_evidence_precision_provisional",
    "citation_matches_resolved_evidence_recall_provisional",
    "e2e_rag_success_resolved_evidence_provisional",
}
EVIDENCE_MAPPING_PACKET_COMPARISON_METRICS = {
    "evidence_mapping_packet_candidate_count",
    "evidence_mapping_packet_likely_accept_count",
    "evidence_mapping_packet_possible_match_count",
    "evidence_mapping_packet_review_needed_count",
    "evidence_mapping_packet_likely_reject_count",
    "source_metadata_resolved_candidate_count",
    "source_metadata_unresolved_candidate_count",
}
BACKEND_COMPARISON_METRICS = {
    "bm25_retrieval_empty_rate",
    "vector_retrieval_empty_rate",
    "hybrid_retrieval_empty_rate",
    "bm25_candidate_count_avg",
    "vector_candidate_count_avg",
    "hybrid_candidate_count_avg",
    "bm25_vector_topk_overlap_avg",
    "vector_latency_ms_p50",
    "vector_latency_ms_p95",
    "bm25_latency_ms_p50",
    "bm25_latency_ms_p95",
    "hybrid_latency_ms_p50",
    "hybrid_latency_ms_p95",
    "embedding_build_latency_ms",
    "index_load_or_build_latency_ms",
    "gpu_used_for_embedding_count",
    "vector_index_available",
}
SURFACE_COMPARISON_METRICS = {
    "source_native_retrieval_empty_rate",
    "searchunit_retrieval_empty_rate",
    "source_native_expected_anchor_recall@k_diagnostic",
    "searchunit_expected_anchor_recall@k_diagnostic",
    "source_native_expected_evidence_text_presence_rate",
    "searchunit_expected_evidence_text_presence_rate",
    "expected_evidence_exact_present_in_source_native_count",
    "expected_evidence_normalized_present_in_source_native_count",
    "expected_anchor_present_in_source_native_count",
    "expected_anchor_present_in_searchunit_count",
    "source_native_target_span_present_but_not_retrieved_count",
    "source_native_target_span_absent_count",
    "searchunit_target_span_absent_count",
    "source_native_beats_searchunit_count",
    "searchunit_beats_source_native_count",
    "both_surfaces_fail_count",
}
SOURCE_NATIVE_LAYERED_RETRIEVAL_LAYERS = (
    "L0_query_normalization",
    "L1_lexical_anchor_search",
    "L2_semantic_vector_search",
    "L3_query_variant_search",
    "L4_structure_aware_source_native_search",
    "L5_merge_dedupe",
    "L6_source_neighbor_expansion",
    "L7_anchor_aware_reranking_diagnostics",
)
SOURCE_NATIVE_LAYERED_RETRIEVAL_BOUNDS = {
    "max_query_variants": 8,
    "max_backend_calls_per_item": 16,
    "max_candidates_per_layer": 50,
    "max_merged_candidates": 100,
    "max_neighbor_expansion_windows": 1,
}
RAG_RETRIEVAL_BACKEND_CHOICES = (
    "bm25",
    "vector",
    "hybrid",
    "auto",
    "weaviate-vector",
    "weaviate-bm25",
    "weaviate-hybrid",
    "weaviate-auto",
)
SOURCE_NATIVE_FORBIDDEN_CANDIDATE_FIELD_NAMES = frozenset(
    {
        "answerability",
        "answerability_label",
        "answerability_labels",
        "baseline_topk",
        "baseline_top_k",
        "baseline_topk_candidate_ids",
        "expected_answer",
        "expected_answer_aliases",
        "expected_answer_text",
        "expected_chunk_id",
        "expected_doc_id",
        "expected_evidence",
        "expected_evidence_text",
        "gold",
        "gold_label",
        "gold_labels",
        "gold_locator",
        "label",
        "labels",
        "previous_winning_candidate",
        "qrels",
        "qrels_positive_id",
        "qrels_positive_ids",
        "raw_prompt_payload",
        "raw_response_payload",
        "relevance",
        "relevance_label",
        "relevance_labels",
        "row_id",
        "supporting_evidence",
        "target_chunk_id",
        "target_doc_id",
        "target_id",
        "target_locator",
    }
)
SOURCE_NATIVE_FORBIDDEN_CANDIDATE_TEXT_MARKERS = (
    "expected_answer",
    "expected_evidence",
    "qrels",
    "gold_label",
    "answerability_label",
    "relevance_label",
    "baseline_topk",
    "previous_winning_candidate",
    "raw_prompt_payload",
    "raw_response_payload",
)
DIAGNOSTIC_ONLY_COMPARISON_METRICS = {
    "answer_extracted_from_retrieved_context_rate",
    "citation_points_to_retrieved_context_rate",
}

BOUNDED_EVIDENCE_ABSTENTION_ANSWER = "제공된 근거만으로는 답할 수 없습니다."
EVIDENCE_GATE_VALIDATOR_VERSION = "bounded_evidence_gate_v1"
EVIDENCE_GATE_MIN_QUERY_ANCHOR_COVERAGE = 0.67
INTERNAL_PRE_GATE_ANSWER_KEY = "_generated_answer_before_evidence_gate"
INTERNAL_XLSX_LOCATOR_SOURCE_CONTEXTS_KEY = "_xlsx_locator_source_contexts"
INTERNAL_REPORT_ROW_KEYS = frozenset({INTERNAL_PRE_GATE_ANSWER_KEY, INTERNAL_XLSX_LOCATOR_SOURCE_CONTEXTS_KEY})
PUBLIC_REPORT_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "llm_prompt",
        "llm_response",
        "prompt_payload",
        "prompt_text",
        "raw_prompt",
        "raw_prompt_payload",
        "raw_prompt_text",
        "raw_response",
        "raw_response_payload",
        "raw_response_text",
        "response_payload",
        "response_text",
        "raw_tool_payload",
        "tool_payload",
    }
)
PUBLIC_REPORT_FORBIDDEN_PAYLOAD_CANONICAL_KEYS = frozenset(
    re.sub(r"[^a-z0-9]", "", key.lower()) for key in PUBLIC_REPORT_FORBIDDEN_PAYLOAD_KEYS
)

INFORMATIONAL_LABELS = {"provisional_metric_used", "inferred_answerable_metric_used"}
CANONICAL_FAILURE_LABELS = frozenset(
    {
        "gold_missing_answerability",
        "expected_evidence_id_unresolved",
        "corpus_absent",
        "present_not_retrieved",
        "retrieved_not_validated",
        "answer_judge_fail",
        "citation_wrong",
        "should_abstain_but_answered",
        "should_answer_but_abstained",
        "metric_not_applicable",
        "schema_warning",
        "guardrail_violation",
        "evidence_package_insufficient",
        "evidence_package_conflicting",
        "evidence_package_unresolved",
        "answer_unsupported_by_evidence",
        "citation_unsupported_by_evidence",
        "citation_retrieved_context_only_diagnostic",
        "abstained_due_to_insufficient_evidence",
        "supported_answer_allowed",
        "sufficient_evidence_over_abstain",
        "gate_policy_not_applicable",
    }
)
FAILURE_LABEL_CANONICAL_ALIASES = {
    "strict_metric_not_applicable": "metric_not_applicable",
    "expected_evidence_resolution_unresolved": "expected_evidence_id_unresolved",
    "evidence_not_retrieved": "present_not_retrieved",
    "citation_missing": "citation_wrong",
    "answered_unanswerable": "should_abstain_but_answered",
    "abstention_failed": "should_abstain_but_answered",
}

EVIDENCE_GATE_QUERY_INTENT_STOPWORDS = {
    "did",
    "가리켜",
    "기록",
    "기록돼",
    "극장판",
    "극장판을",
    "how",
    "location",
    "나와",
    "나오는",
    "목록",
    "목록에",
    "말해",
    "만나려고",
    "문서",
    "문서에",
    "방영",
    "설명",
    "설명은",
    "성격",
    "성격과",
    "식으로",
    "시기",
    "시기는",
    "어디",
    "어디로",
    "어떤",
    "어떻게",
    "역할",
    "역할을",
    "올라와",
    "what",
    "when",
    "where",
    "which",
    "who",
    "의미",
    "적혀",
    "적혀있어",
    "있어",
    "향했어",
}


@dataclass(frozen=True)
class RagEvalBundle:
    output_dir: Path
    items_path: Path
    summary_path: Path
    markdown_path: Path
    summary: Mapping[str, Any]
    report_path: Path | None = None


@dataclass(frozen=True)
class EvidenceResolutionConfig:
    enabled: bool = True
    scope: str = "full-corpus"
    max_candidates: int = 5
    min_score: float = 0.35
    count_medium: bool = False


class ExpectedEvidenceResolver:
    """Diagnostic-only expected-evidence mapper.

    The resolver never mutates gold/qrels and never changes retrieval results.
    It only maps expected evidence rows onto retrieved or review-only
    source-native corpus rows after retrieval has completed, so reports can
    show whether evidence IDs are missing, exact, or resolvable.
    """

    def __init__(self, config: EvidenceResolutionConfig | None = None) -> None:
        self.config = config or EvidenceResolutionConfig()

    def resolve_item(
        self,
        item: EvalItem,
        *,
        retrieved_contexts: Sequence[Mapping[str, Any]],
        index_candidates: Sequence[Mapping[str, Any]] = (),
        limitations: Sequence[str] = (),
    ) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        selected_candidates: list[dict[str, Any]] = []
        total_candidate_count = 0
        missing_id_count = 0
        unresolved_count = 0
        exact_count = 0
        candidate_resolved_count = 0
        confidence_counts = Counter()

        for index, evidence in enumerate(item.expected_evidence):
            row = self._resolve_evidence_row(
                item,
                evidence,
                index=index,
                retrieved_contexts=retrieved_contexts,
                index_candidates=index_candidates,
                limitations=limitations,
            )
            rows.append(row)
            total_candidate_count += len(row["candidates"])
            if not evidence.doc_id or not evidence.chunk_id:
                missing_id_count += 1
            if row["id_status"] == "resolved_exact":
                exact_count += 1
            if row["id_status"] == "resolved_candidate":
                candidate_resolved_count += 1
            if row["selected_candidate"]:
                selected_candidates.append(row["selected_candidate"])
                confidence_counts[row["selected_candidate"]["confidence"]] += 1
            if not row["resolved"]:
                unresolved_count += 1

        return {
            "enabled": bool(self.config.enabled),
            "scope": self.config.scope,
            "count_medium": bool(self.config.count_medium),
            "resolved_count": exact_count + candidate_resolved_count,
            "unresolved_count": unresolved_count,
            "missing_id_count": missing_id_count,
            "candidate_count": total_candidate_count,
            "full_corpus_candidate_count": sum(
                1
                for row in rows
                for candidate in row.get("candidates", [])
                if isinstance(candidate, Mapping) and candidate.get("source") == "full_corpus_source_native"
            ),
            "full_corpus_resolved_candidate_count": sum(
                1
                for row in rows
                if row.get("resolved")
                and isinstance(row.get("selected_candidate"), Mapping)
                and row["selected_candidate"].get("source") == "full_corpus_source_native"
            ),
            "full_corpus_collision_count": sum(
                1
                for row in rows
                for candidate in row.get("candidates", [])
                if isinstance(candidate, Mapping) and _clean(candidate.get("collision_warning"))
            ),
            "selected_candidates": selected_candidates,
            "confidence_counts": dict(sorted(confidence_counts.items())),
            "rows": rows,
            "limitations": list(limitations),
        }

    def _resolve_evidence_row(
        self,
        item: EvalItem,
        evidence: ExpectedEvidence,
        *,
        index: int,
        retrieved_contexts: Sequence[Mapping[str, Any]],
        index_candidates: Sequence[Mapping[str, Any]],
        limitations: Sequence[str],
    ) -> dict[str, Any]:
        row_candidates = self._candidate_rows(retrieved_contexts, index_candidates)
        warnings: list[str] = []
        if not evidence.doc_id or not evidence.chunk_id:
            warnings.append("missing_doc_or_chunk_id")
        if limitations:
            warnings.extend(limitations)

        candidates: list[dict[str, Any]] = []
        for rank, candidate in enumerate(row_candidates, start=1):
            scored = self._score_candidate(item, evidence, candidate, rank=rank)
            if scored is not None:
                candidates.append(scored)
        candidates.sort(
            key=lambda candidate: (
                {"high": 0, "medium": 1, "low": 2}.get(candidate["confidence"], 3),
                -float(candidate.get("score") or 0.0),
                int(candidate.get("rank") or 10**9),
            )
        )
        candidates = candidates[: max(1, int(self.config.max_candidates))]
        if candidates:
            collision_candidates = [
                candidate
                for candidate in candidates
                if candidate.get("source") == "full_corpus_source_native"
                and candidate.get("confidence") in {"high", "medium"}
                and candidate.get("match_type") == candidates[0].get("match_type")
                and abs(float(candidate.get("score") or 0.0) - float(candidates[0].get("score") or 0.0)) <= 0.000001
            ]
            if len(collision_candidates) > 1:
                warning = f"collision:{len(collision_candidates)}_same_confidence_score_match_type"
                warnings.append(warning)
                collision_keys = {
                    (
                        _clean(candidate.get("doc_id")),
                        _clean(candidate.get("chunk_id")),
                        _clean(candidate.get("candidate_text_hash")),
                    )
                    for candidate in collision_candidates
                }
                for candidate in candidates:
                    key = (
                        _clean(candidate.get("doc_id")),
                        _clean(candidate.get("chunk_id")),
                        _clean(candidate.get("candidate_text_hash")),
                    )
                    if key in collision_keys:
                        candidate["collision_warning"] = warning
                        candidate["match_reasons"] = sorted({*candidate.get("match_reasons", []), "collision"})
        if not candidates:
            anchors = _evidence_resolution_anchors(item, evidence)
            if not anchors:
                warnings.append("no_non_generic_anchor_overlap")
            else:
                warnings.append("no_candidate_anchor_match")

        selected = candidates[0] if candidates else None
        resolved = bool(
            selected
            and (
                selected["confidence"] == "high"
                or (selected["confidence"] == "medium" and self.config.count_medium)
            )
        )
        if selected and not resolved and selected["confidence"] == "medium":
            warnings.append("medium_confidence_not_counted")
        if selected and selected["confidence"] == "low":
            warnings.append("low_confidence_review_only")
        if selected and "no_non_generic_anchor_overlap" in selected.get("match_reasons", []):
            warnings.append("no_non_generic_anchor_overlap")

        if evidence.doc_id and evidence.chunk_id:
            id_status = "present"
        else:
            id_status = "missing"
        if resolved and selected:
            id_status = "resolved_exact" if "exact_id_match" in selected["match_reasons"] else "resolved_candidate"
        elif (evidence.doc_id or evidence.chunk_id) and not resolved:
            id_status = "unresolved"

        return {
            "expected_evidence_index": index,
            "input_doc_id": evidence.doc_id,
            "input_chunk_id": evidence.chunk_id,
            "input_text": evidence.text,
            "id_status": id_status,
            "candidates": candidates,
            "selected_candidate": _selected_candidate(selected) if selected else None,
            "resolved": resolved,
            "resolution_warnings": sorted(set(warnings)),
        }

    def _candidate_rows(
        self,
        retrieved_contexts: Sequence[Mapping[str, Any]],
        index_candidates: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        if self.config.scope in {"retrieved-only", "both", "full-corpus"}:
            for context in retrieved_contexts:
                row = dict(context)
                row["_resolution_source"] = "retrieved_contexts"
                key = _context_key(row)
                if key not in seen:
                    rows.append(row)
                    seen.add(key)
        if self.config.scope in {"index-candidate-lookup", "both", "full-corpus", "full-corpus-review-only"}:
            for candidate in index_candidates:
                row = dict(candidate)
                row["_resolution_source"] = _clean(candidate.get("_resolution_source")) or "index_candidate_lookup"
                key = _context_key(row)
                if key not in seen:
                    rows.append(row)
                    seen.add(key)
        return rows

    def _score_candidate(
        self,
        item: EvalItem,
        evidence: ExpectedEvidence,
        row: Mapping[str, Any],
        *,
        rank: int,
    ) -> dict[str, Any] | None:
        reasons: list[str] = []
        safe_row = _runtime_safe_evidence_context(row)
        text = _clean(safe_row.get("text"))
        text_norm = normalize_answer_text(text)
        expected_text = _clean(evidence.text)
        expected_text_norm = normalize_answer_text(expected_text)
        exact_id = bool((evidence.doc_id or evidence.chunk_id) and _evidence_id_matches_row(evidence, row))
        if exact_id:
            reasons.append("exact_id_match")
        exact_text = bool(expected_text and expected_text in text)
        normalized_text_match = bool(expected_text_norm and expected_text_norm in text_norm)
        if exact_text:
            reasons.append("exact_text_match")
        elif normalized_text_match:
            reasons.append("normalized_text_match")

        anchors = _evidence_resolution_anchors(item, evidence)
        anchor_hits = sorted(anchor for anchor in anchors if _anchor_in_text([anchor], text))
        required_numeric = _numeric_or_date_anchors(
            _candidate_anchors(item.expected_answer, *item.expected_answer_aliases, evidence.text)
        )
        missing_numeric = sorted(anchor for anchor in required_numeric if not _anchor_in_text([anchor], text))
        if anchor_hits:
            reasons.append(f"anchor_hits:{len(anchor_hits)}")
        else:
            reasons.append("no_non_generic_anchor_overlap")
        if required_numeric and not missing_numeric:
            reasons.append("numeric_or_date_anchors_satisfied")
        elif required_numeric and missing_numeric:
            reasons.append("numeric_or_date_anchor_missing")

        overlap = _token_overlap_ratio(evidence.text, text)
        if overlap >= 0.45:
            reasons.append("strong_text_overlap")
        elif overlap > 0:
            reasons.append("weak_text_overlap")
        overlap_terms = sorted(_token_set(evidence.text) & _token_set(text))
        stopwords = _anchor_stopwords()
        generic_overlap_terms = [term for term in overlap_terms if _is_generic_anchor(term, stopwords)]
        non_generic_overlap_terms = [term for term in overlap_terms if not _is_generic_anchor(term, stopwords)]

        numeric_ok = not missing_numeric
        anchor_score = len(anchor_hits) / max(1, len(anchors))
        score = max(float(row.get("score") or 0.0), round((anchor_score + overlap) / 2, 6))
        match_type = "unresolved"
        confidence = "low"
        if exact_id:
            match_type = "exact_id_match"
            confidence = "high"
            score = max(score, 1.0)
        elif exact_text:
            match_type = "exact_match"
            confidence = "high" if required_numeric and numeric_ok else "medium" if numeric_ok else "low"
            score = max(score, 0.98 if confidence == "high" else 0.7 if confidence == "medium" else 0.45)
        elif normalized_text_match:
            match_type = "normalized_match"
            confidence = "high" if required_numeric and numeric_ok else "medium" if numeric_ok else "low"
            score = max(score, 0.92 if confidence == "high" else 0.68 if confidence == "medium" else 0.45)
        elif anchor_hits and numeric_ok and (len(anchor_hits) >= 2 or overlap >= 0.55):
            match_type = "anchor_only_match" if overlap < self.config.min_score else "weak_match"
            confidence = "high" if required_numeric else "medium"
        elif anchor_hits and overlap >= self.config.min_score and numeric_ok:
            match_type = "weak_match"
            confidence = "medium"

        if not exact_id and not exact_text and not normalized_text_match and not anchor_hits and overlap < self.config.min_score:
            return None
        text_hash = _sha256_text(text)
        return {
            "rank": int(row.get("rank") or rank),
            "doc_id": _clean(row.get("doc_id")),
            "chunk_id": _clean(row.get("chunk_id")),
            "candidate_doc_id": _clean(row.get("doc_id")),
            "candidate_chunk_id": _clean(row.get("chunk_id")),
            "source_atom_id": _clean(row.get("source_atom_id")),
            "evidence_bundle_id": _clean(row.get("evidence_bundle_id")),
            "candidate_source_atom_id": _clean(row.get("source_atom_id")),
            "candidate_evidence_bundle_id": _clean(row.get("evidence_bundle_id")),
            "score": round(float(score), 6),
            "confidence": confidence,
            "source": _clean(row.get("_resolution_source")) or "retrieved_contexts",
            "match_type": match_type,
            "match_reasons": sorted(set(reasons)),
            "text_preview": text[:240],
            "candidate_text_preview": text[:240],
            "candidate_full_text_hash": text_hash,
            "candidate_text_hash": text_hash,
            "full_text_hash": text_hash,
            "normalized_match_info": {
                "normalized_expected_text_sha256": _sha256_text(expected_text_norm),
                "normalized_candidate_text_sha256": _sha256_text(text_norm),
                "normalized_expected_in_candidate": normalized_text_match,
                "exact_expected_in_candidate": exact_text,
                "token_overlap": round(overlap, 6),
            },
            "anchor_hits": anchor_hits[:12],
            "missing_numeric_or_date_anchors": missing_numeric,
            "candidate_generic_overlap_terms": generic_overlap_terms[:12],
            "candidate_non_generic_anchor_overlap_terms": non_generic_overlap_terms[:12],
            "collision_warning": "",
            "text_overlap": round(overlap, 6),
        }


def _selected_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": _clean(candidate.get("doc_id")),
        "chunk_id": _clean(candidate.get("chunk_id")),
        "confidence": _clean(candidate.get("confidence")),
        "score": candidate.get("score"),
        "source": _clean(candidate.get("source")),
        "rank": candidate.get("rank"),
        "match_reasons": list(candidate.get("match_reasons") or []),
    }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_clean(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = _clean(row.get(key))
        if value:
            return value
    return ""


def _parse_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    if not (text.startswith("{") or text.startswith("[")):
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _sha256_text(value: Any) -> str:
    return hashlib.sha256(_clean(value).encode("utf-8")).hexdigest() if _clean(value) else ""


def _looks_like_local_path(value: Any) -> bool:
    text = _clean(value)
    if not text:
        return False
    if re.match(r"^[A-Za-z]:[\\/]", text):
        return True
    if text.startswith("\\\\"):
        return True
    return bool(re.search(r"[\\/](Users|Documents|Downloads|Desktop|source_registry|indexes|eval_queries)[\\/]", text))


def _redact_pathish_metadata(value: Any) -> tuple[str, bool]:
    text = _clean(value)
    if not text:
        return "", False
    if _looks_like_local_path(text):
        return f"redacted_path_sha256:{_sha256_text(text)[:16]}", True
    return text, False


_ABSOLUTE_LOCAL_PATH_RE = re.compile(r"(?<![A-Za-z0-9])(?P<path>(?:[A-Za-z]:[\\/]|\\\\)[^\s`\"']+)")


def _redact_absolute_local_paths(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""

    def replace(match: re.Match[str]) -> str:
        path_text = match.group("path").rstrip(".,;)")
        suffix = match.group("path")[len(path_text) :]
        return f"redacted_path_sha256:{_sha256_text(path_text)[:16]}{suffix}"

    return _ABSOLUTE_LOCAL_PATH_RE.sub(replace, text)


def _report_path_value(path: Path | str) -> str:
    path_obj = Path(path)
    try:
        if path_obj.is_absolute():
            resolved = path_obj.resolve()
            try:
                return resolved.relative_to(ROOT).as_posix()
            except ValueError:
                name = _clean(path_obj.name)
                suffix = f"__{name}" if name else ""
                return f"redacted_path_sha256:{_sha256_text(resolved.as_posix())[:16]}{suffix}"
    except OSError:
        return _redact_absolute_local_paths(path_obj.as_posix())
    return path_obj.as_posix()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetSchemaError(f"{path}:{line_no}: invalid JSONL row: {exc.msg}") from exc
        if not isinstance(row, dict):
            raise DatasetSchemaError(f"{path}:{line_no}: each JSONL row must be an object")
        rows.append(row)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _report_item_id(row: Mapping[str, Any], item_index: int) -> str:
    return _clean(row.get("id") or row.get("item_id") or row.get("query_id")) or str(item_index)


class XlsxLocatorRunStore(_XlsxLocatorRunStoreBase):
    """Compatibility wrapper that supplies actual-RAG callbacks to the focused RunStore."""

    def __init__(self, path: Path | str) -> None:
        super().__init__(path, dependencies=_xlsx_locator_run_store_dependencies())


def _xlsx_locator_run_store_dependencies() -> XlsxLocatorRunStoreDependencies:
    return XlsxLocatorRunStoreDependencies(
        clean=_clean,
        as_list=_as_list,
        jsonable=_jsonable,
        sha256_text=_sha256_text,
        gate_row_text=_gate_row_text,
        classify_xlsx_pdf_residual_row=_classify_xlsx_pdf_residual_row,
        query_evidence_item_projection=_query_evidence_item_projection,
        xlsx_locator_candidate_text=_xlsx_locator_candidate_text,
        xlsx_locator_source_owned_value=_xlsx_locator_source_owned_value,
        internal_xlsx_locator_source_contexts_key=INTERNAL_XLSX_LOCATOR_SOURCE_CONTEXTS_KEY,
        xlsx_locator_source_owned_fields=XLSX_LOCATOR_SOURCE_OWNED_FIELDS,
        schema_version=SCHEMA_VERSION,
        evidence_gate_validator_version=EVIDENCE_GATE_VALIDATOR_VERSION,
    )


def _is_forbidden_public_payload_key(key: Any) -> bool:
    normalized = str(key).strip().lower()
    if not normalized:
        return False
    if normalized in INTERNAL_REPORT_ROW_KEYS:
        return True
    canonical = re.sub(r"[^a-z0-9]", "", normalized)
    if (
        "sha256" in normalized
        or "sha256" in canonical
        or normalized.endswith("_hash")
        or normalized.endswith("_digest")
        or canonical.endswith("hash")
        or canonical.endswith("digest")
    ):
        return False
    if normalized in PUBLIC_REPORT_FORBIDDEN_PAYLOAD_KEYS or canonical in PUBLIC_REPORT_FORBIDDEN_PAYLOAD_CANONICAL_KEYS:
        return True
    if ("payload" in normalized or "payload" in canonical) and (
        "prompt" in normalized
        or "response" in normalized
        or "tool" in normalized
        or "prompt" in canonical
        or "response" in canonical
        or "tool" in canonical
    ):
        return True
    if (normalized.startswith("raw_") or canonical.startswith("raw")) and (
        "prompt" in normalized
        or "response" in normalized
        or "tool" in normalized
        or "prompt" in canonical
        or "response" in canonical
        or "tool" in canonical
    ):
        return True
    return False


def _sanitize_public_report_value(value: Any, *, source_native_context: bool = False) -> Any:
    if isinstance(value, Mapping):
        active_source_native_context = source_native_context or _source_native_context_requires_runtime_text_sanitization(value)
        sanitized: dict[str, Any] = {}
        for key, nested_value in value.items():
            if _is_forbidden_public_payload_key(key):
                continue
            if active_source_native_context and _source_native_runtime_forbidden_key(key):
                continue
            canonical_key = _canonical_xlsx_locator_field_name(key)
            if active_source_native_context and canonical_key in SOURCE_NATIVE_RUNTIME_TEXT_FIELDS:
                sanitized[str(key)] = _strip_source_native_runtime_forbidden_text_segments(_clean(nested_value))
                continue
            if active_source_native_context and _source_native_runtime_forbidden_scalar(nested_value):
                continue
            sanitized[str(key)] = _sanitize_public_report_value(
                nested_value,
                source_native_context=active_source_native_context,
            )
        return sanitized
    if isinstance(value, list):
        return [
            _sanitize_public_report_value(item, source_native_context=source_native_context)
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            _sanitize_public_report_value(item, source_native_context=source_native_context)
            for item in value
        ]
    if source_native_context and _source_native_runtime_forbidden_scalar(value):
        return ""
    return value


def _public_report_row(row: Mapping[str, Any]) -> dict[str, Any]:
    public: dict[str, Any] = {}
    for key, value in dict(row).items():
        if key in INTERNAL_REPORT_ROW_KEYS or _is_forbidden_public_payload_key(key):
            continue
        public[str(key)] = _sanitize_public_report_value(value)
    return public


def _source_rows_from_items(items: Sequence[EvalItem]) -> list[Mapping[str, Any]]:
    return [item.source_row for item in items if isinstance(item.source_row, Mapping)]


def _source_fields_used(rows: Sequence[Mapping[str, Any]], candidates: Sequence[str]) -> list[str]:
    used: list[str] = []
    for field in candidates:
        if any(_clean(row.get(field)) for row in rows):
            used.append(field)
    return used


def _response_quality_source_profile(dataset_path: Path | str, rows: Sequence[Mapping[str, Any]]) -> str:
    path_text = Path(dataset_path).as_posix().casefold()
    if any(_clean(row.get("quality_tier")).upper() == "SILVER" for row in rows):
        return "diagnostic_silver"
    if any("silver" in _clean(row.get("split")).casefold() for row in rows):
        return "diagnostic_silver"
    if "silver" in path_text:
        return "diagnostic_silver"
    if any(_clean(row.get("gold_status")).upper() == "APPROVED" for row in rows):
        return "user_approved_gold_snapshot"
    if any(_clean(row.get("approval_basis")) for row in rows):
        return "user_approved_gold_snapshot"
    if "official_metric_input" in path_text or "gold" in path_text:
        return "user_approved_gold_snapshot"
    return "standard_eval_dataset"


def build_response_quality_input_summary(
    *,
    dataset_path: Path | str,
    items: Sequence[EvalItem],
) -> dict[str, Any]:
    rows = _source_rows_from_items(items)
    source_profile = _response_quality_source_profile(dataset_path, rows)
    answerability_counts = Counter(item.answerability for item in items)
    strict_eligible_count = sum(
        1 for item in items if item.answerability == "answerable" and item.has_expected_answer and item.has_expected_evidence
    )
    diagnostic_silver = source_profile == "diagnostic_silver"
    strict_policy = {
        "strict_metrics_not_applicable": diagnostic_silver,
        "reason": "diagnostic_silver_answerability_unknown" if diagnostic_silver else "",
        "silver_strict_answer_citation_e2e": "N/A" if diagnostic_silver else "",
        "strict_gold_eligible_item_count": 0 if diagnostic_silver else int(strict_eligible_count),
        "answerability_inferred_for_silver": False,
    }
    return {
        "schema_version": RESPONSE_QUALITY_INPUT_SUMMARY_SCHEMA_VERSION,
        "source_profile": source_profile,
        "dataset_path": _report_path_value(dataset_path),
        "item_count": len(items),
        "answerability_distribution": {
            "answerable": int(answerability_counts.get("answerable", 0)),
            "unanswerable": int(answerability_counts.get("unanswerable", 0)),
            "unknown": int(answerability_counts.get("unknown", 0)),
        },
        "normalization": {
            "mode": "in_memory_read_only",
            "query_field_mappings": _source_fields_used(rows, ("query", "query_text", "question", "question_ko")),
            "expected_answer_field_mappings": _source_fields_used(
                rows,
                (
                    "expected_answer",
                    "expected_answer_ko",
                    "expected_answer_text",
                    "normalized_expected_answer_text",
                    "user_expected_answer_text",
                    "expected_answer_text_existing",
                ),
            ),
            "expected_evidence_field_mappings": _source_fields_used(
                rows,
                (
                    "expected_evidence",
                    "supporting_evidence",
                    "supporting_evidence_note",
                    "citation_text",
                    "expected_evidence_text_or_summary",
                    "user_expected_evidence_text_or_summary",
                    "evidence_summary",
                ),
            ),
            "source_rows_mutated": False,
            "temporary_normalized_dataset_written": False,
        },
        "strict_answer_citation_e2e_policy": strict_policy,
        "guardrails": {
            "report_only": True,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "gold_or_qrels_mutation": False,
            "label_or_denominator_mutation": False,
            "expected_field_mutation": False,
            "latest_or_current_pointer_mutation_required": False,
        },
    }


LLM_JUDGE_PROMPT_VERSION = "local_llm_semantic_rag_judge_v1"
LLM_JUDGE_PROMPT_TEMPLATE = """You are a provisional RAG evaluation judge.
Return exactly one JSON object with keys: passed (boolean), confidence (number from 0 to 1), reason (string), and evidence_basis (string).
Judge whether the generated answer is semantically correct using only the expected answer, aliases, expected evidence, notes, and retrieved context below.
Do not use outside knowledge. If gold is partial, prefer conservative support from expected evidence or retrieved context.

Payload:
{payload}
"""


class LocalLLMJudgeAdapter:
    """Optional localhost-only LLM judge adapter using the repo's existing helper."""

    def __init__(
        self,
        *,
        backend: str = "",
        base_url: str = "",
        model: str = "",
        threshold: float = 0.6,
        max_tokens: int = 360,
        timeout_seconds: int = 60,
        check_endpoint: bool = True,
    ) -> None:
        from scripts import rag_local_llm_expected_answer_generation_v1 as local_llm

        self._local_llm = local_llm
        self.backend = _clean(backend) or local_llm.DEFAULT_BACKEND
        self.base_url = local_llm.resolve_base_url(self.backend, _clean(base_url))
        self.model = _clean(model) or local_llm.DEFAULT_MODEL
        self.threshold = float(threshold)
        self.max_tokens = int(max_tokens)
        self.timeout_seconds = int(timeout_seconds)
        self.check_endpoint = bool(check_endpoint)
        self.blockers = local_llm.local_llm_entry_blockers(
            backend=self.backend,
            base_url=self.base_url,
            model=self.model,
            check_endpoint=self.check_endpoint,
            timeout_seconds=min(self.timeout_seconds, 10),
        )

    @property
    def available(self) -> bool:
        return not self.blockers

    @property
    def config(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "tier": "provisional",
            "judge_kind": "local_llm_strict_json",
            "judge_version": LLM_JUDGE_PROMPT_VERSION,
            "backend": self.backend,
            "base_url": self.base_url,
            "model": self.model,
            "threshold": self.threshold,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "check_endpoint": self.check_endpoint,
            "available": self.available,
            "blockers": list(self.blockers),
            "prompt": LLM_JUDGE_PROMPT_TEMPLATE,
            "external_api_calls": False,
        }

    def evaluate(
        self,
        *,
        item: EvalItem,
        generated_answer: str,
        retrieved_context_texts: Sequence[str],
        expected_evidence_texts: Sequence[str],
    ) -> dict[str, Any]:
        if not self.available:
            return {
                "passed": False,
                "available": False,
                "provisional": True,
                "judge_kind": "local_llm_strict_json",
                "judge_version": LLM_JUDGE_PROMPT_VERSION,
                "threshold": self.threshold,
                "reason": "local_llm_unavailable",
                "blockers": list(self.blockers),
            }
        payload = {
            "id": item.id,
            "query": item.query,
            "answerability": item.answerability,
            "generated_answer": generated_answer,
            "expected_answer": item.expected_answer,
            "expected_answer_aliases": list(item.expected_answer_aliases),
            "expected_evidence_texts": list(expected_evidence_texts)[:6],
            "retrieved_context_texts": [text[:1200] for text in retrieved_context_texts[:6]],
            "notes": item.notes,
            "threshold": self.threshold,
        }
        prompt = LLM_JUDGE_PROMPT_TEMPLATE.format(payload=json.dumps(payload, ensure_ascii=False, sort_keys=True))
        try:
            parsed, meta = self._local_llm.call_local_llm_strict_json(
                backend=self.backend,
                base_url=self.base_url,
                model=self.model,
                prompt=prompt,
                temperature=0.0,
                max_tokens=self.max_tokens,
                timeout_seconds=self.timeout_seconds,
            )
        except Exception as exc:
            return {
                "passed": False,
                "available": False,
                "provisional": True,
                "judge_kind": "local_llm_strict_json",
                "judge_version": LLM_JUDGE_PROMPT_VERSION,
                "threshold": self.threshold,
                "reason": f"local_llm_judge_error: {type(exc).__name__}: {exc}",
            }
        confidence = float(parsed.get("confidence") or 0.0)
        passed = bool(parsed.get("passed")) and confidence >= self.threshold
        return {
            "passed": passed,
            "available": True,
            "provisional": True,
            "judge_kind": "local_llm_strict_json",
            "judge_version": LLM_JUDGE_PROMPT_VERSION,
            "threshold": self.threshold,
            "confidence": round(confidence, 6),
            "reason": _clean(parsed.get("reason")) or "local_llm_judge_completed",
            "evidence_basis": _clean(parsed.get("evidence_basis")),
            "raw_response_sha256": (meta or {}).get("raw_response_sha256"),
        }


def sanitized_judge_config(config: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = dict(config)
    prompt = _clean(sanitized.pop("prompt", ""))
    if prompt:
        sanitized["prompt_sha256"] = f"sha256:{_sha256_text(prompt)}"
        sanitized["prompt_template_persisted"] = False
        sanitized.setdefault("prompt_template_id", _clean(sanitized.get("judge_version")) or "unknown")
    return sanitized


def _context_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _clean(row.get("doc_id") or row.get("docId") or row.get("document_id") or row.get("documentId")),
        _clean(row.get("chunk_id") or row.get("chunkId") or row.get("search_unit_id") or row.get("searchUnitId")),
        normalize_answer_text(_clean(row.get("text"))),
    )


def _evidence_id_matches_row(evidence: ExpectedEvidence, row: Mapping[str, Any]) -> bool:
    doc_id, chunk_id, _text_norm = _context_key(row)
    if evidence.chunk_id and chunk_id == evidence.chunk_id and (not evidence.doc_id or doc_id == evidence.doc_id):
        return True
    if evidence.doc_id and doc_id == evidence.doc_id and not evidence.chunk_id:
        return True
    return False


def _evidence_matches_row(evidence: ExpectedEvidence, row: Mapping[str, Any]) -> bool:
    if _evidence_id_matches_row(evidence, row):
        return True
    _doc_id, _chunk_id, text_norm = _context_key(row)
    expected_text = normalize_answer_text(evidence.text)
    return bool(expected_text and expected_text in text_norm)


def _weak_evidence_matches_row(
    evidence: ExpectedEvidence,
    row: Mapping[str, Any],
    *,
    anchors: Iterable[str] = (),
    threshold: float = 0.45,
) -> bool:
    if _evidence_id_matches_row(evidence, row):
        return True
    expected_text = _clean(evidence.text)
    row_text = _clean(row.get("text"))
    return bool(
        expected_text
        and row_text
        and _token_overlap_ratio(expected_text, row_text) >= threshold
        and _anchor_requirements_satisfied(anchors, row_text)
    )


def _required_evidence(item: EvalItem) -> list[ExpectedEvidence]:
    required = [evidence for evidence in item.expected_evidence if evidence.required]
    return required or list(item.expected_evidence)


def _contexts_top_k(contexts: Sequence[Mapping[str, Any]], k: int) -> list[Mapping[str, Any]]:
    return [
        row
        for row in sorted(contexts, key=lambda item: int(item.get("rank") or 10**9))
        if int(row_rank(row)) <= k
    ]


def row_rank(row: Mapping[str, Any]) -> int:
    try:
        return int(row.get("rank") or 10**9)
    except (TypeError, ValueError):
        return 10**9


def _all_required_evidence_present(
    item: EvalItem,
    rows: Sequence[Mapping[str, Any]],
) -> bool:
    required = _required_evidence(item)
    return bool(required) and all(any(_evidence_matches_row(evidence, row) for row in rows) for evidence in required)


def _all_required_weak_evidence_present(
    item: EvalItem,
    rows: Sequence[Mapping[str, Any]],
) -> bool:
    required = _required_evidence(item)
    return bool(required) and all(
        any(_weak_evidence_matches_row(evidence, row, anchors=_evidence_match_anchors(item, evidence)) for row in rows)
        for evidence in required
    )


def _count_required_evidence_matches(
    item: EvalItem,
    rows: Sequence[Mapping[str, Any]],
) -> int:
    return sum(1 for evidence in _required_evidence(item) if any(_evidence_matches_row(evidence, row) for row in rows))


def _count_required_weak_evidence_matches(
    item: EvalItem,
    rows: Sequence[Mapping[str, Any]],
) -> int:
    return sum(
        1
        for evidence in _required_evidence(item)
        if any(_weak_evidence_matches_row(evidence, row, anchors=_evidence_match_anchors(item, evidence)) for row in rows)
    )


def _count_matching_citations(
    item: EvalItem,
    citations: Sequence[Mapping[str, Any]],
) -> int:
    return sum(1 for citation in citations if any(_evidence_matches_row(evidence, citation) for evidence in item.expected_evidence))


def _resolved_evidence_candidates(resolution: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in _as_list(resolution.get("rows")):
        if not isinstance(row, Mapping) or not row.get("resolved"):
            continue
        selected = row.get("selected_candidate")
        if isinstance(selected, Mapping):
            candidate = dict(selected)
            candidate["expected_evidence_index"] = row.get("expected_evidence_index")
            candidates.append(candidate)
    return candidates


def _candidate_matches_context(candidate: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    candidate_doc = _clean(candidate.get("doc_id"))
    candidate_chunk = _clean(candidate.get("chunk_id"))
    row_doc, row_chunk, _row_text = _context_key(row)
    if candidate_chunk and row_chunk == candidate_chunk and (not candidate_doc or row_doc == candidate_doc):
        return True
    if candidate_doc and row_doc == candidate_doc and not candidate_chunk:
        return True
    return False


def _all_resolved_candidates_present(
    candidates: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
) -> bool:
    return bool(candidates) and all(any(_candidate_matches_context(candidate, row) for row in rows) for candidate in candidates)


def _count_matching_resolved_candidate_rows(
    candidates: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
) -> int:
    return sum(1 for candidate in candidates if any(_candidate_matches_context(candidate, row) for row in rows))


def _count_citations_matching_resolved_candidates(
    candidates: Sequence[Mapping[str, Any]],
    citations: Sequence[Mapping[str, Any]],
) -> int:
    return sum(1 for citation in citations if any(_candidate_matches_context(candidate, citation) for candidate in candidates))


def _metric_template(name: str, denominator_policy: str, *, tier: str = "strict") -> dict[str, Any]:
    return {
        "name": name,
        "tier": tier,
        "numerator": 0,
        "denominator": 0,
        "score": None,
        "skipped_count": 0,
        "not_applicable_count": 0,
        "diagnostic_only_count": 0,
        "exclusion_reasons": {},
        "denominator_policy": denominator_policy,
    }


def _exclude(metric: dict[str, Any], reason: str, *, diagnostic_only: bool = False) -> None:
    metric["skipped_count"] += 1
    metric["not_applicable_count"] += 1
    if diagnostic_only:
        metric["diagnostic_only_count"] += 1
    metric["exclusion_reasons"][reason] = metric["exclusion_reasons"].get(reason, 0) + 1


def _finish_metric(metric: dict[str, Any]) -> dict[str, Any]:
    denominator = metric["denominator"]
    metric["score"] = None if denominator == 0 else round(metric["numerator"] / denominator, 6)
    metric["exclusion_reasons"] = dict(sorted(metric["exclusion_reasons"].items()))
    return metric


def _canonical_failure_labels(labels: Iterable[str]) -> list[str]:
    canonical: set[str] = set()
    non_informational_seen = False
    for label in labels:
        cleaned = _clean(label)
        if not cleaned or cleaned in INFORMATIONAL_LABELS:
            continue
        non_informational_seen = True
        if cleaned in CANONICAL_FAILURE_LABELS:
            canonical.add(cleaned)
        alias = FAILURE_LABEL_CANONICAL_ALIASES.get(cleaned)
        if alias:
            canonical.add(alias)
    if not canonical and non_informational_seen:
        canonical.add("metric_not_applicable")
    return sorted(canonical)


def score_rag_eval_items(
    items: Sequence[EvalItem],
    item_outputs: Sequence[Mapping[str, Any]],
    *,
    top_k_values: Sequence[int] = DEFAULT_TOP_K_VALUES,
    abstention_phrases: Sequence[str] = DEFAULT_ABSTENTION_PHRASES,
    judge_adapter: Any | None = None,
    provisional_require_citations: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    outputs_by_id = {_clean(output.get("id")): output for output in item_outputs}
    k_values = tuple(sorted({int(k) for k in top_k_values if int(k) > 0})) or DEFAULT_TOP_K_VALUES
    primary_k = max(k_values)
    judge_adapter = judge_adapter or HeuristicJudgeAdapter()

    answer_metric = _metric_template(
        "exact_or_alias_answer_correctness",
        "answerable items with expected_answer or aliases only",
    )
    abstention_metric = _metric_template("abstention_accuracy", "unanswerable items only")
    citation_precision = _metric_template(
        "citation_precision",
        "generated citation rows for answerable items with citations and expected evidence",
    )
    citation_recall = _metric_template(
        "citation_recall",
        "required expected evidence rows for answerable items with citations and expected evidence",
    )
    e2e_metric = _metric_template(
        "e2e_rag_success_strict",
        f"answerable items with expected answer and expected evidence; evidence recall@{primary_k}; citations required",
    )
    judged_answer = _metric_template(
        "judged_answer_correctness_provisional",
        "items with generated answers plus expected answer, aliases, notes, or expected evidence signal",
        tier="provisional",
    )
    answer_context_consistency = _metric_template(
        "answer_extracted_from_retrieved_context_rate",
        "diagnostic consistency check only: generated answer overlaps retrieved context; not answer correctness",
        tier="diagnostic",
    )
    citation_points_to_context = _metric_template(
        "citation_points_to_retrieved_context_rate",
        "diagnostic consistency check only: citation points to retrieved context; strict citation metrics handle gold evidence correctness",
        tier="diagnostic",
    )
    e2e_provisional = _metric_template(
        "e2e_rag_success_provisional",
        f"items with generated answer, context, judge signal, expected evidence, judge pass, context consistency, and weak/strict evidence at top-{primary_k}",
        tier="provisional",
    )
    inferred_answer_metric = _metric_template(
        "exact_or_alias_answer_correctness_inferred_answerable",
        "unknown-answerability rows with expected answer and expected evidence; answerable inferred for this metric only",
        tier="inferred_answerable",
    )
    inferred_evidence_metrics = {
        k: _metric_template(
            f"evidence_recall@{k}_inferred_answerable",
            f"unknown-answerability rows with expected answer/evidence; answerable inferred for evidence recall@{k} only",
            tier="inferred_answerable",
        )
        for k in k_values
    }
    inferred_e2e_metric = _metric_template(
        "e2e_rag_success_inferred_answerable",
        f"unknown-answerability rows with expected answer/evidence; requires exact/alias answer and evidence recall@{primary_k}; no gold label mutation",
        tier="inferred_answerable",
    )
    evidence_metrics = {
        k: _metric_template(
            f"evidence_recall@{k}",
            f"answerable items with expected evidence; all required evidence must appear in top-{k}",
        )
        for k in k_values
    }
    weak_evidence_metrics = {
        k: _metric_template(
            f"weak_evidence_match_recall@{k}",
            f"items with expected evidence; id match or weak text overlap in top-{k}",
            tier="provisional",
        )
        for k in k_values
    }
    resolved_evidence_available = _metric_template(
        "resolved_evidence_available_rate",
        "expected evidence rows with selected high-confidence diagnostic candidate; medium counted only when configured",
        tier="provisional",
    )
    resolved_evidence_recall_metrics = {
        k: _metric_template(
            f"resolved_evidence_recall@{k}_provisional",
            f"items with at least one resolved expected evidence candidate; all selected candidates appear in top-{k}",
            tier="provisional",
        )
        for k in k_values
    }
    resolved_citation_precision = _metric_template(
        "citation_matches_resolved_evidence_precision_provisional",
        "generated citation rows for items with resolved expected evidence candidates",
        tier="provisional",
    )
    resolved_citation_recall = _metric_template(
        "citation_matches_resolved_evidence_recall_provisional",
        "resolved expected evidence candidates for items with citations",
        tier="provisional",
    )
    e2e_resolved_evidence = _metric_template(
        "e2e_rag_success_resolved_evidence_provisional",
        f"items with judge signal and resolved evidence candidates; requires judge pass and resolved evidence recall@{primary_k}",
        tier="provisional",
    )

    diagnostics = {
        "retrieval_empty_count": 0,
        "retrieval_empty_rate": 0.0,
        "generation_empty_count": 0,
        "generation_empty_rate": 0.0,
        "citation_empty_count": 0,
        "citation_empty_rate": 0.0,
        "average_context_count": 0.0,
        "average_context_chars": 0.0,
        "gold_incomplete_count": 0,
        "gold_missing_count": 0,
        "missing_expected_answer_count": 0,
        "missing_expected_evidence_count": 0,
        "missing_answerability_label_count": 0,
        "expected_evidence_id_missing_count": 0,
        "expected_evidence_id_present_count": 0,
        "expected_evidence_id_resolved_exact_count": 0,
        "expected_evidence_id_resolved_candidate_count": 0,
        "expected_evidence_id_unresolved_count": 0,
        "expected_evidence_row_count": 0,
        "expected_evidence_text_match_candidate_count": 0,
        "expected_evidence_resolution_enabled": False,
        "expected_evidence_resolution_scope": "disabled",
        "expected_evidence_resolution_candidate_count": 0,
        "expected_evidence_resolution_high_confidence_count": 0,
        "expected_evidence_resolution_medium_confidence_count": 0,
        "expected_evidence_resolution_low_confidence_count": 0,
        "expected_evidence_resolution_review_only_count": 0,
        "expected_evidence_full_corpus_candidate_count": 0,
        "expected_evidence_full_corpus_high_confidence_count": 0,
        "expected_evidence_full_corpus_medium_confidence_count": 0,
        "expected_evidence_full_corpus_low_confidence_count": 0,
        "expected_evidence_full_corpus_review_only_count": 0,
        "expected_evidence_full_corpus_resolved_candidate_count": 0,
        "expected_evidence_full_corpus_collision_count": 0,
        "expected_evidence_full_corpus_unresolved_count": 0,
        "gold_or_qrels_mutation": False,
        "human_decision_fields_filled_by_codex": False,
        "schema_warning_count": 0,
        "pipeline_error_count": 0,
        "answerable_count": 0,
        "unanswerable_count": 0,
        "unknown_answerability_count": 0,
        "not_applicable_counts_by_metric": {},
        "failure_category_counts": {},
    }

    scored_rows: list[dict[str, Any]] = []
    total_context_count = 0
    total_context_chars = 0

    for item in items:
        output = dict(outputs_by_id.get(item.id) or _pipeline_error_output(item, "missing_pipeline_output"))
        contexts = [
            _runtime_safe_evidence_context(row)
            for row in _as_list(output.get("retrieved_contexts"))
            if isinstance(row, Mapping)
        ]
        citations = [
            _runtime_safe_evidence_context(row)
            for row in _as_list(output.get("citations"))
            if isinstance(row, Mapping)
        ]
        generated_answer = _clean(output.get("generated_answer"))
        pre_gate_generated_answer = _clean(output.get(INTERNAL_PRE_GATE_ANSWER_KEY)) or generated_answer
        answerability = item.answerability
        failure_labels: set[str] = set(output.get("failure_labels") or [])
        metric_results: dict[str, Any] = {}
        evidence_id_diagnostics: list[dict[str, Any]] = []
        evidence_resolution = (
            output.get("expected_evidence_resolution")
            if isinstance(output.get("expected_evidence_resolution"), Mapping)
            else {"enabled": False, "scope": "disabled", "rows": [], "selected_candidates": []}
        )
        resolution_enabled = bool(evidence_resolution.get("enabled"))

        total_context_count += len(contexts)
        total_context_chars += sum(len(_clean(row.get("text"))) for row in contexts)

        if not contexts:
            diagnostics["retrieval_empty_count"] += 1
            failure_labels.add("retrieval_empty")
        if not generated_answer:
            diagnostics["generation_empty_count"] += 1
            failure_labels.add("generation_empty")
        if not citations:
            diagnostics["citation_empty_count"] += 1

        if answerability == "unknown":
            failure_labels.add("gold_missing_answerability")
        if not item.has_answerability_label:
            diagnostics["missing_answerability_label_count"] += 1
            failure_labels.add("gold_missing_answerability")
        if not item.has_expected_answer:
            diagnostics["missing_expected_answer_count"] += 1
            if answerability == "answerable":
                failure_labels.add("gold_missing_expected_answer")
        if not item.has_expected_evidence:
            diagnostics["missing_expected_evidence_count"] += 1
            if answerability == "answerable":
                failure_labels.add("gold_missing_expected_evidence")
        diagnostics["schema_warning_count"] += len(item.validation_warnings)
        if item.validation_warnings:
            failure_labels.add("schema_warning")

        for evidence in item.expected_evidence:
            evidence_anchors = _evidence_match_anchors(item, evidence)
            if not resolution_enabled and (not evidence.doc_id or not evidence.chunk_id):
                diagnostics["expected_evidence_id_missing_count"] += 1
            id_match = any(_evidence_id_matches_row(evidence, context) for context in contexts)
            if not resolution_enabled and (evidence.doc_id or evidence.chunk_id) and not id_match:
                diagnostics["expected_evidence_id_unresolved_count"] += 1
            text_match_candidate = bool(
                not id_match
                and evidence.text
                and any(
                    _weak_evidence_matches_row(evidence, context, anchors=evidence_anchors)
                    for context in contexts
                )
            )
            if text_match_candidate:
                diagnostics["expected_evidence_text_match_candidate_count"] += 1
            evidence_id_diagnostics.append(
                {
                    "doc_id": evidence.doc_id,
                    "chunk_id": evidence.chunk_id,
                    "doc_id_missing": not bool(evidence.doc_id),
                    "chunk_id_missing": not bool(evidence.chunk_id),
                    "id_resolved_in_retrieved_contexts": id_match,
                    "text_match_candidate": text_match_candidate,
                    "match_type": "id" if id_match else "weak_text_candidate" if text_match_candidate else "unresolved",
                    "candidate_anchor_count": len(evidence_anchors),
                }
            )

        if resolution_enabled:
            diagnostics["expected_evidence_resolution_enabled"] = True
            diagnostics["expected_evidence_resolution_scope"] = _clean(evidence_resolution.get("scope")) or "retrieved-only"
            resolution_rows = [row for row in _as_list(evidence_resolution.get("rows")) if isinstance(row, Mapping)]
            diagnostics["expected_evidence_row_count"] += len(resolution_rows)
            for resolution_row in resolution_rows:
                selected = resolution_row.get("selected_candidate") if isinstance(resolution_row.get("selected_candidate"), Mapping) else {}
                confidence = _clean(selected.get("confidence"))
                if resolution_row.get("input_doc_id") and resolution_row.get("input_chunk_id"):
                    diagnostics["expected_evidence_id_present_count"] += 1
                else:
                    diagnostics["expected_evidence_id_missing_count"] += 1
                if resolution_row.get("id_status") == "resolved_exact":
                    diagnostics["expected_evidence_id_resolved_exact_count"] += 1
                if resolution_row.get("id_status") == "resolved_candidate":
                    diagnostics["expected_evidence_id_resolved_candidate_count"] += 1
                if not resolution_row.get("resolved"):
                    diagnostics["expected_evidence_id_unresolved_count"] += 1
                diagnostics["expected_evidence_resolution_candidate_count"] += len(
                    _as_list(resolution_row.get("candidates"))
                )
                full_corpus_candidates = [
                    candidate
                    for candidate in _as_list(resolution_row.get("candidates"))
                    if isinstance(candidate, Mapping) and candidate.get("source") == "full_corpus_source_native"
                ]
                diagnostics["expected_evidence_full_corpus_candidate_count"] += len(full_corpus_candidates)
                diagnostics["expected_evidence_full_corpus_review_only_count"] += len(full_corpus_candidates)
                if (
                    resolution_row.get("resolved")
                    and isinstance(selected, Mapping)
                    and selected.get("source") == "full_corpus_source_native"
                ):
                    diagnostics["expected_evidence_full_corpus_resolved_candidate_count"] += 1
                elif _clean(evidence_resolution.get("scope")) in {"full-corpus", "full-corpus-review-only"}:
                    diagnostics["expected_evidence_full_corpus_unresolved_count"] += 1
                for full_candidate in full_corpus_candidates:
                    full_confidence = _clean(full_candidate.get("confidence"))
                    if full_confidence == "high":
                        diagnostics["expected_evidence_full_corpus_high_confidence_count"] += 1
                    elif full_confidence == "medium":
                        diagnostics["expected_evidence_full_corpus_medium_confidence_count"] += 1
                    elif full_confidence == "low":
                        diagnostics["expected_evidence_full_corpus_low_confidence_count"] += 1
                    if _clean(full_candidate.get("collision_warning")):
                        diagnostics["expected_evidence_full_corpus_collision_count"] += 1
                if confidence == "high":
                    diagnostics["expected_evidence_resolution_high_confidence_count"] += 1
                elif confidence == "medium":
                    diagnostics["expected_evidence_resolution_medium_confidence_count"] += 1
                    if not resolution_row.get("resolved"):
                        diagnostics["expected_evidence_resolution_review_only_count"] += 1
                elif confidence == "low":
                    diagnostics["expected_evidence_resolution_low_confidence_count"] += 1
                    diagnostics["expected_evidence_resolution_review_only_count"] += 1
            if any(not row.get("resolved") for row in resolution_rows):
                failure_labels.add("expected_evidence_resolution_unresolved")
            if any(row.get("resolved") for row in resolution_rows):
                failure_labels.add("provisional_metric_used")
        else:
            diagnostics["expected_evidence_row_count"] += len(item.expected_evidence)

        gold_incomplete = (
            not item.has_answerability_label
            or (answerability == "answerable" and (not item.has_expected_answer or not item.has_expected_evidence))
        )
        if gold_incomplete:
            diagnostics["gold_incomplete_count"] += 1
            diagnostics["gold_missing_count"] += 1
            failure_labels.add("metric_not_applicable")

        answer_pass = False
        if answerability == "answerable" and item.has_expected_answer:
            answer_metric["denominator"] += 1
            answer_pass = answer_correct(
                generated_answer,
                expected_answer=item.expected_answer,
                aliases=item.expected_answer_aliases,
            )
            answer_metric["numerator"] += int(answer_pass)
            if not answer_pass:
                failure_labels.add("answer_exact_mismatch")
        else:
            reason = (
                "missing_expected_answer"
                if answerability == "answerable"
                else f"answerability_{answerability}_not_in_answer_correctness_denominator"
            )
            _exclude(answer_metric, reason, diagnostic_only=gold_incomplete)
            failure_labels.add("strict_metric_not_applicable")
        metric_results["exact_or_alias_answer_correctness"] = (
            answer_pass if answerability == "answerable" and item.has_expected_answer else None
        )

        evidence_pass_by_k: dict[int, bool | None] = {}
        for k, metric in evidence_metrics.items():
            if answerability == "answerable" and item.has_expected_evidence:
                metric["denominator"] += 1
                passed = _all_required_evidence_present(item, _contexts_top_k(contexts, k))
                evidence_pass_by_k[k] = passed
                metric["numerator"] += int(passed)
                if k == primary_k and not passed:
                    failure_labels.add("evidence_not_retrieved")
            else:
                reason = (
                    "missing_expected_evidence"
                    if answerability == "answerable"
                    else f"answerability_{answerability}_not_in_evidence_recall_denominator"
                )
                _exclude(metric, reason, diagnostic_only=gold_incomplete)
                evidence_pass_by_k[k] = None
                failure_labels.add("strict_metric_not_applicable")
        metric_results.update({f"evidence_recall@{k}": value for k, value in evidence_pass_by_k.items()})

        weak_evidence_pass_by_k: dict[int, bool | None] = {}
        for k, metric in weak_evidence_metrics.items():
            if item.has_expected_evidence:
                metric["denominator"] += 1
                weak_pass = _all_required_weak_evidence_present(item, _contexts_top_k(contexts, k))
                weak_evidence_pass_by_k[k] = weak_pass
                metric["numerator"] += int(weak_pass)
                if weak_pass:
                    failure_labels.add("provisional_metric_used")
            else:
                _exclude(metric, "missing_expected_evidence", diagnostic_only=True)
                weak_evidence_pass_by_k[k] = None
        metric_results.update(
            {f"weak_evidence_match_recall@{k}": value for k, value in weak_evidence_pass_by_k.items()}
        )

        resolved_candidates = _resolved_evidence_candidates(evidence_resolution)
        resolution_rows = [row for row in _as_list(evidence_resolution.get("rows")) if isinstance(row, Mapping)]
        for resolution_row in resolution_rows:
            resolved_evidence_available["denominator"] += 1
            resolved_evidence_available["numerator"] += int(bool(resolution_row.get("resolved")))
        metric_results["resolved_evidence_available_rate"] = {
            "resolved_count": sum(1 for row in resolution_rows if row.get("resolved")),
            "expected_evidence_row_count": len(resolution_rows),
            "provisional": True,
        } if resolution_rows else None

        resolved_recall_pass_by_k: dict[int, bool | None] = {}
        for k, metric in resolved_evidence_recall_metrics.items():
            if resolved_candidates:
                metric["denominator"] += 1
                passed = _all_resolved_candidates_present(resolved_candidates, _contexts_top_k(contexts, k))
                resolved_recall_pass_by_k[k] = passed
                metric["numerator"] += int(passed)
            else:
                _exclude(metric, "missing_resolved_expected_evidence", diagnostic_only=True)
                resolved_recall_pass_by_k[k] = None
        metric_results.update(
            {f"resolved_evidence_recall@{k}_provisional": value for k, value in resolved_recall_pass_by_k.items()}
        )

        if citations and resolved_candidates:
            resolved_citation_precision["denominator"] += len(citations)
            resolved_citation_precision["numerator"] += _count_citations_matching_resolved_candidates(
                resolved_candidates,
                citations,
            )
            resolved_citation_recall["denominator"] += len(resolved_candidates)
            resolved_citation_recall["numerator"] += _count_matching_resolved_candidate_rows(
                resolved_candidates,
                citations,
            )
        else:
            _exclude(
                resolved_citation_precision,
                "missing_citations_or_resolved_expected_evidence",
                diagnostic_only=True,
            )
            _exclude(
                resolved_citation_recall,
                "missing_citations_or_resolved_expected_evidence",
                diagnostic_only=True,
            )

        if citations and item.has_expected_evidence and answerability == "answerable":
            matching_citations = _count_matching_citations(item, citations)
            citation_precision["denominator"] += len(citations)
            citation_precision["numerator"] += matching_citations
            citation_precision["eligible_item_count"] = citation_precision.get("eligible_item_count", 0) + 1
            if matching_citations != len(citations):
                failure_labels.add("citation_wrong")

            required_count = len(_required_evidence(item))
            cited_required_count = _count_required_evidence_matches(item, citations)
            citation_recall["denominator"] += required_count
            citation_recall["numerator"] += cited_required_count
            citation_recall["eligible_item_count"] = citation_recall.get("eligible_item_count", 0) + 1
            if cited_required_count != required_count:
                failure_labels.add("citation_wrong")
            citation_check_pass = matching_citations == len(citations) and cited_required_count == required_count
        else:
            if answerability != "answerable":
                reason = f"answerability_{answerability}_not_in_citation_denominator"
            else:
                reason = "missing_citations" if item.has_expected_evidence else "missing_expected_evidence"
            _exclude(citation_precision, reason, diagnostic_only=gold_incomplete)
            _exclude(citation_recall, reason, diagnostic_only=gold_incomplete)
            citation_check_pass = False
            if item.has_expected_evidence:
                failure_labels.add("citation_missing")
            failure_labels.add("strict_metric_not_applicable")
        metric_results["citation_check_pass"] = citation_check_pass if item.has_expected_evidence else None

        if citations:
            overlap_hits = 0
            for citation in citations:
                citation_text = _clean(citation.get("text"))
                context_match = any(
                    _weak_evidence_matches_row(
                        ExpectedEvidence(text=citation_text),
                        context,
                        anchors=_candidate_anchors(citation_text),
                    )
                    for context in contexts
                )
                id_context_match = any(
                    _context_key(citation)[:2] == _context_key(context)[:2]
                    and any(_context_key(citation)[:2])
                    for context in contexts
                )
                if context_match or id_context_match:
                    overlap_hits += 1
            citation_points_to_context["denominator"] += len(citations)
            citation_points_to_context["numerator"] += overlap_hits
            metric_results["citation_points_to_retrieved_context_rate"] = {
                "passed_count": overlap_hits,
                "citation_count": len(citations),
                "diagnostic_only": True,
            }
        else:
            _exclude(citation_points_to_context, "missing_citations", diagnostic_only=True)
            metric_results["citation_points_to_retrieved_context_rate"] = None

        if answerability == "unanswerable":
            abstention_metric["denominator"] += 1
            abstention_pass = abstains(generated_answer, phrases=abstention_phrases)
            abstention_metric["numerator"] += int(abstention_pass)
            if not abstention_pass:
                failure_labels.add("abstention_failed")
                if generated_answer:
                    failure_labels.add("answered_unanswerable")
        else:
            _exclude(
                abstention_metric,
                f"answerability_{answerability}_not_in_abstention_denominator",
                diagnostic_only=answerability == "unknown",
            )

        context_texts = [_clean(context.get("text")) for context in contexts if _clean(context.get("text"))]
        expected_evidence_texts = [evidence.text for evidence in item.expected_evidence if _clean(evidence.text)]
        judge_signal_available = bool(
            generated_answer
            and answerability != "unanswerable"
            and (
                item.has_expected_answer
                or expected_evidence_texts
                or _clean(item.notes)
            )
        )
        judge_result: dict[str, Any] | None = None
        judge_pass = False
        if judge_signal_available:
            judge_result = judge_adapter.evaluate(
                item=item,
                generated_answer=generated_answer,
                expected_evidence_texts=expected_evidence_texts,
                retrieved_context_texts=context_texts,
            )
            if judge_result.get("available", True) is False:
                _exclude(judged_answer, "judge_unavailable", diagnostic_only=True)
                failure_labels.add("answer_judge_unavailable")
            else:
                judged_answer["denominator"] += 1
                judge_pass = bool(judge_result["passed"])
                judged_answer["numerator"] += int(judge_pass)
                failure_labels.add("provisional_metric_used")
                if not judge_pass:
                    failure_labels.add("answer_judge_fail")
        else:
            _exclude(judged_answer, "missing_generated_answer_or_judge_signal", diagnostic_only=True)
            if generated_answer:
                failure_labels.add("answer_judge_unavailable")
        metric_results["judged_answer_correctness_provisional"] = judge_result

        support_pass = False
        if generated_answer and contexts:
            answer_context_consistency["denominator"] += 1
            best_context_overlap = max((_token_overlap_ratio(generated_answer, text) for text in context_texts), default=0.0)
            support_pass = best_context_overlap >= 0.35
            answer_context_consistency["numerator"] += int(support_pass)
            metric_results["answer_extracted_from_retrieved_context_rate"] = {
                "passed": support_pass,
                "best_context_overlap": round(best_context_overlap, 6),
                "threshold": 0.35,
                "diagnostic_only": True,
            }
            failure_labels.add("provisional_metric_used")
        else:
            _exclude(answer_context_consistency, "missing_generated_answer_or_context", diagnostic_only=True)
            metric_results["answer_extracted_from_retrieved_context_rate"] = None

        if answerability == "answerable" and item.has_expected_answer and item.has_expected_evidence:
            e2e_metric["denominator"] += 1
            evidence_pass = bool(evidence_pass_by_k.get(primary_k))
            with_citation_pass = answer_pass and evidence_pass and bool(citations) and citation_check_pass
            e2e_metric["numerator"] += int(with_citation_pass)
        else:
            reason = "missing_expected_answer_or_evidence" if answerability == "answerable" else f"answerability_{answerability}_not_in_e2e_denominator"
            _exclude(e2e_metric, reason, diagnostic_only=gold_incomplete)
            failure_labels.add("strict_metric_not_applicable")

        inferred_answerable_candidate = (
            answerability == "unknown"
            and not item.has_answerability_label
            and item.has_expected_answer
            and item.has_expected_evidence
        )
        inferred_evidence_pass_by_k: dict[int, bool | None] = {}
        if inferred_answerable_candidate:
            inferred_answer_metric["denominator"] += 1
            inferred_answer_pass = answer_correct(
                generated_answer,
                expected_answer=item.expected_answer,
                aliases=item.expected_answer_aliases,
            )
            inferred_answer_metric["numerator"] += int(inferred_answer_pass)
            for k, metric in inferred_evidence_metrics.items():
                metric["denominator"] += 1
                inferred_evidence_pass = _all_required_evidence_present(item, _contexts_top_k(contexts, k))
                inferred_evidence_pass_by_k[k] = inferred_evidence_pass
                metric["numerator"] += int(inferred_evidence_pass)
            inferred_e2e_metric["denominator"] += 1
            inferred_e2e_pass = bool(inferred_answer_pass and inferred_evidence_pass_by_k.get(primary_k))
            inferred_e2e_metric["numerator"] += int(inferred_e2e_pass)
            metric_results["answerability_inferred_for_metrics_only"] = True
            metric_results["exact_or_alias_answer_correctness_inferred_answerable"] = inferred_answer_pass
            metric_results.update(
                {f"evidence_recall@{k}_inferred_answerable": value for k, value in inferred_evidence_pass_by_k.items()}
            )
            metric_results["e2e_rag_success_inferred_answerable"] = inferred_e2e_pass
            failure_labels.add("inferred_answerable_metric_used")
        else:
            _exclude(inferred_answer_metric, "not_unknown_with_expected_answer_and_evidence", diagnostic_only=True)
            for metric in inferred_evidence_metrics.values():
                _exclude(metric, "not_unknown_with_expected_answer_and_evidence", diagnostic_only=True)
            _exclude(inferred_e2e_metric, "not_unknown_with_expected_answer_and_evidence", diagnostic_only=True)
            metric_results["answerability_inferred_for_metrics_only"] = False

        provisional_signal = bool(generated_answer and contexts and judge_signal_available and item.has_expected_evidence)
        if provisional_signal and answerability != "unanswerable":
            e2e_provisional["denominator"] += 1
            evidence_ok = bool(evidence_pass_by_k.get(primary_k)) or bool(weak_evidence_pass_by_k.get(primary_k))
            citation_ok = (not provisional_require_citations) or bool(citations and citation_check_pass)
            provisional_pass = bool(judge_pass and evidence_ok and support_pass and citation_ok)
            e2e_provisional["numerator"] += int(provisional_pass)
            metric_results["e2e_rag_success_provisional"] = provisional_pass
            failure_labels.add("provisional_metric_used")
        else:
            _exclude(e2e_provisional, "missing_generated_answer_context_judge_signal_or_expected_evidence", diagnostic_only=True)
            metric_results["e2e_rag_success_provisional"] = None

        if provisional_signal and answerability != "unanswerable" and resolved_candidates:
            e2e_resolved_evidence["denominator"] += 1
            resolved_evidence_ok = bool(resolved_recall_pass_by_k.get(primary_k))
            citation_ok = (not provisional_require_citations) or bool(
                citations
                and _count_matching_resolved_candidate_rows(resolved_candidates, citations) == len(resolved_candidates)
            )
            resolved_e2e_pass = bool(judge_pass and resolved_evidence_ok and support_pass and citation_ok)
            e2e_resolved_evidence["numerator"] += int(resolved_e2e_pass)
            metric_results["e2e_rag_success_resolved_evidence_provisional"] = resolved_e2e_pass
            failure_labels.add("provisional_metric_used")
        else:
            _exclude(
                e2e_resolved_evidence,
                "missing_generated_answer_context_judge_signal_or_resolved_expected_evidence",
                diagnostic_only=True,
            )
            metric_results["e2e_rag_success_resolved_evidence_provisional"] = None

        if output.get("diagnostics", {}).get("pipeline_error") or output.get("pipeline_error"):
            failure_labels.add("pipeline_error")
            diagnostics["pipeline_error_count"] += 1

        surface_comparison = (
            output.get("retrieval_surface_comparison")
            if isinstance(output.get("retrieval_surface_comparison"), Mapping)
            else {}
        )
        source_native_surface = (
            surface_comparison.get("source_native")
            if isinstance(surface_comparison.get("source_native"), Mapping)
            else {}
        )
        if item.has_expected_evidence and source_native_surface:
            if source_native_surface.get("expected_evidence_in_corpus_normalized") is False:
                failure_labels.add("corpus_absent")
            elif source_native_surface.get("expected_evidence_retrieved") is False:
                failure_labels.add("present_not_retrieved")
        if item.has_expected_evidence and contexts and not citation_check_pass:
            failure_labels.add("retrieved_not_validated")
        if answerability == "unanswerable" and generated_answer and not abstains(generated_answer):
            failure_labels.add("should_abstain_but_answered")
        if answerability == "answerable" and abstains(generated_answer):
            failure_labels.add("should_answer_but_abstained")

        expected_answer_match_before_gate = (
            _answer_matches_expected_deterministic(pre_gate_generated_answer, item)
            if item.has_expected_answer
            else None
        )
        expected_answer_match_after_gate = (
            _answer_matches_expected_deterministic(generated_answer, item)
            if item.has_expected_answer
            else None
        )
        expected_evidence_match_after_gate = (
            _all_required_evidence_present(item, _contexts_top_k(contexts, primary_k))
            if item.has_expected_evidence
            else None
        )
        expected_evidence_match_before_gate = expected_evidence_match_after_gate
        gate_payload = output.get("evidence_gate") if isinstance(output.get("evidence_gate"), Mapping) else {}
        gate_status = _clean(gate_payload.get("evidence_package_status"))
        real_rag_supported_before_gate = bool(gate_status == "sufficient" and not abstains(pre_gate_generated_answer))
        real_rag_supported_after_gate = bool(gate_status == "sufficient" and not abstains(generated_answer))
        if not gate_payload:
            real_rag_supported_before_gate = False
            real_rag_supported_after_gate = False
        abstention_correctness = (
            abstains(generated_answer)
            if answerability == "unanswerable"
            else (not abstains(generated_answer) if answerability == "answerable" else "diagnostic_only_unknown_answerability")
        )

        scored = dict(output)
        scored["retrieved_contexts"] = contexts
        scored["citations"] = citations
        scored["answerability"] = item.answerability
        scored["expected_answer"] = item.expected_answer
        scored["expected_answer_aliases"] = list(item.expected_answer_aliases)
        scored["expected_evidence"] = [evidence.to_dict() for evidence in item.expected_evidence]
        scored["source_track"] = _clean(item.source_row.get("track") or item.source_row.get("source_family"))
        scored["reviewed_mapping_applied"] = bool(item.source_row.get("reviewed_mapping_applied"))
        scored["reviewed_mapping_change_types"] = list(item.source_row.get("reviewed_mapping_change_types") or [])
        scored["evidence_id_diagnostics"] = evidence_id_diagnostics
        scored["expected_evidence_resolution"] = dict(evidence_resolution)
        scored["schema_warnings"] = list(item.validation_warnings)
        scored["metric_results"] = metric_results
        scored["expected_answer_match_before_gate"] = expected_answer_match_before_gate
        scored["expected_answer_match_after_gate"] = expected_answer_match_after_gate
        scored["expected_evidence_match_before_gate"] = expected_evidence_match_before_gate
        scored["expected_evidence_match_after_gate"] = expected_evidence_match_after_gate
        scored["legacy_real_answer_delta_before_gate"] = ""
        scored["legacy_real_answer_delta_after_gate"] = ""
        scored["real_rag_supported_before_gate"] = real_rag_supported_before_gate
        scored["real_rag_supported_after_gate"] = real_rag_supported_after_gate
        scored["e2e_success_after_gate_provisional"] = metric_results.get("e2e_rag_success_provisional")
        scored["abstention_correctness_diagnostic_or_strict_when_labels_available"] = abstention_correctness
        scored["failure_labels"] = sorted(failure_labels)
        scored["canonical_failure_labels"] = _canonical_failure_labels(failure_labels)
        scored_rows.append(scored)

    item_count = len(items)
    if item_count:
        diagnostics["retrieval_empty_rate"] = round(diagnostics["retrieval_empty_count"] / item_count, 6)
        diagnostics["generation_empty_rate"] = round(diagnostics["generation_empty_count"] / item_count, 6)
        diagnostics["citation_empty_rate"] = round(diagnostics["citation_empty_count"] / item_count, 6)
        diagnostics["average_context_count"] = round(total_context_count / item_count, 6)
        diagnostics["average_context_chars"] = round(total_context_chars / max(total_context_count, 1), 6)

    # Normalize dynamic answerability counts after the loop.
    answerability_counts = Counter(item.answerability for item in items)
    diagnostics["answerable_count"] = int(answerability_counts.get("answerable", 0))
    diagnostics["unanswerable_count"] = int(answerability_counts.get("unanswerable", 0))
    diagnostics["unknown_answerability_count"] = int(answerability_counts.get("unknown", 0))
    failure_counts = Counter(
        label
        for row in scored_rows
        for label in row["failure_labels"]
        if label not in INFORMATIONAL_LABELS
    )
    informational_counts = Counter(
        label
        for row in scored_rows
        for label in row["failure_labels"]
        if label in INFORMATIONAL_LABELS
    )
    diagnostics["failure_category_counts"] = dict(sorted(failure_counts.items()))
    diagnostics["informational_label_counts"] = dict(sorted(informational_counts.items()))
    canonical_failure_counts = Counter(
        label
        for row in scored_rows
        for label in row.get("canonical_failure_labels", [])
    )
    diagnostics["canonical_failure_category_counts"] = dict(sorted(canonical_failure_counts.items()))
    diagnostics["canonical_failure_labels"] = sorted(CANONICAL_FAILURE_LABELS)
    citation_gold_correct_checked_count = sum(
        1
        for row in scored_rows
        if (row.get("metric_results") if isinstance(row.get("metric_results"), Mapping) else {}).get(
            "citation_check_pass"
        )
        is not None
    )
    citation_gold_correct_pass_count = sum(
        1
        for row in scored_rows
        if (row.get("metric_results") if isinstance(row.get("metric_results"), Mapping) else {}).get(
            "citation_check_pass"
        )
        is True
    )
    diagnostics["citation_gold_correct_definition"] = (
        "citation_matches_expected_evidence_when_gold_fields_available_diagnostic_only"
    )
    diagnostics["citation_gold_correct_checked_count_diagnostic"] = int(citation_gold_correct_checked_count)
    diagnostics["citation_gold_correct_pass_count_diagnostic"] = int(citation_gold_correct_pass_count)
    diagnostics["citation_gold_correct_rate_diagnostic"] = (
        None
        if citation_gold_correct_checked_count == 0
        else round(citation_gold_correct_pass_count / citation_gold_correct_checked_count, 6)
    )

    strict_metrics = {
        "exact_or_alias_answer_correctness": _finish_metric(answer_metric),
        **{f"evidence_recall@{k}": _finish_metric(metric) for k, metric in evidence_metrics.items()},
        "citation_precision": _finish_metric(citation_precision),
        "citation_recall": _finish_metric(citation_recall),
        "abstention_accuracy": _finish_metric(abstention_metric),
        "e2e_rag_success_strict": _finish_metric(e2e_metric),
    }
    provisional_metrics = {
        "judged_answer_correctness_provisional": _finish_metric(judged_answer),
        **{f"weak_evidence_match_recall@{k}": _finish_metric(metric) for k, metric in weak_evidence_metrics.items()},
        "resolved_evidence_available_rate": _finish_metric(resolved_evidence_available),
        **{
            f"resolved_evidence_recall@{k}_provisional": _finish_metric(metric)
            for k, metric in resolved_evidence_recall_metrics.items()
        },
        "citation_matches_resolved_evidence_precision_provisional": _finish_metric(resolved_citation_precision),
        "citation_matches_resolved_evidence_recall_provisional": _finish_metric(resolved_citation_recall),
        "e2e_rag_success_provisional": _finish_metric(e2e_provisional),
        "e2e_rag_success_resolved_evidence_provisional": _finish_metric(e2e_resolved_evidence),
    }
    inferred_answerable_metrics = {
        "exact_or_alias_answer_correctness_inferred_answerable": _finish_metric(inferred_answer_metric),
        **{f"evidence_recall@{k}_inferred_answerable": _finish_metric(metric) for k, metric in inferred_evidence_metrics.items()},
        "e2e_rag_success_inferred_answerable": _finish_metric(inferred_e2e_metric),
    }
    diagnostic_metric_details = {
        "answer_extracted_from_retrieved_context_rate": _finish_metric(answer_context_consistency),
        "citation_points_to_retrieved_context_rate": _finish_metric(citation_points_to_context),
    }
    diagnostics["not_applicable_counts_by_metric"] = {
        **{name: metric["not_applicable_count"] for name, metric in strict_metrics.items()},
        **{name: metric["not_applicable_count"] for name, metric in provisional_metrics.items()},
        **{name: metric["not_applicable_count"] for name, metric in inferred_answerable_metrics.items()},
        **{name: metric["not_applicable_count"] for name, metric in diagnostic_metric_details.items()},
    }

    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_kind": RUN_KIND,
        "total_item_count": item_count,
        "answerability_distribution": {
            "answerable": diagnostics["answerable_count"],
            "unanswerable": diagnostics["unanswerable_count"],
            "unknown": diagnostics["unknown_answerability_count"],
        },
        "strict_metrics": strict_metrics,
        "provisional_metrics": provisional_metrics,
        "inferred_answerable_metrics": inferred_answerable_metrics,
        "diagnostic_metric_details": diagnostic_metric_details,
        "headline_metrics": strict_metrics,
        "diagnostic_metrics": diagnostics,
        "denominator_policy": denominator_policy_text(primary_k),
        "diagnostic_only_decisions": diagnostic_only_decisions(),
        "judge_config": sanitized_judge_config(judge_adapter.config),
        "metric_tiers": {
            "strict": list(strict_metrics),
            "provisional": list(provisional_metrics),
            "inferred_answerable": list(inferred_answerable_metrics),
            "diagnostic": [*diagnostics, *diagnostic_metric_details],
        },
        "legacy_metric_aliases": {
            "answer_supported_by_retrieved_context_provisional": "answer_extracted_from_retrieved_context_rate",
            "citation_overlap_provisional": "citation_points_to_retrieved_context_rate",
        },
        "provisional_metric_policy": {
            "e2e_requires_judge_pass": True,
            "e2e_requires_weak_or_strict_evidence_at_primary_k": True,
            "e2e_requires_answer_context_consistency_when_context_available": True,
            "answer_context_consistency_is_standalone_diagnostic": True,
            "e2e_requires_citation_pass": bool(provisional_require_citations),
            "weak_evidence_requires_non_generic_anchor_for_text_overlap": True,
            "weak_evidence_requires_all_numeric_or_date_anchors_for_text_overlap": True,
        },
    }
    return summary, scored_rows


def denominator_policy_text(primary_k: int) -> str:
    return (
        "This run reports strict, provisional, and diagnostic tiers. Strict denominators include only rows with "
        "sufficient human-owned gold for the specific metric: exact/alias answer correctness requires answerable "
        "rows with expected answers or aliases; evidence recall requires answerable rows with expected evidence; "
        "citation precision/recall require answerable rows with generated citations plus expected evidence; abstention accuracy requires "
        "unanswerable labels; strict E2E success requires answerable rows with both expected answer and expected "
        f"evidence and uses evidence recall@{primary_k}. Provisional denominators are broader and keep rows with "
        "usable partial signal, such as generated answers plus expected evidence, notes, aliases, or retrieved "
        "contexts, but provisional E2E success still requires the provisional answer judge to pass and weak-or-strict "
        f"evidence at top-{primary_k}. Inferred-answerable metrics are reported separately for unknown-answerability "
        "rows that have expected answer and expected evidence; answerability is inferred only for metric computation "
        "and no gold labels are mutated. Diagnostic metrics run across executable rows for pipeline debugging. The "
        "answer/context consistency diagnostic is also used as a conservative guard inside provisional E2E because "
        "that metric requires answer/context support when available, but the standalone consistency rate is not answer "
        "correctness. Citation/retrieved-context consistency is likewise not citation correctness. "
        "Missing gold no longer blocks the run; it is recorded as warning/failure labels and excluded only from strict "
        "metric denominators that require it."
    )


def diagnostic_only_decisions() -> list[dict[str, Any]]:
    return [
        {
            "decision": "Use a deterministic provisional answer judge before final LLM judge policy is settled.",
            "rationale": "Forward progress is prioritized for this phase; strict exact/alias scoring remains separate and the heuristic judge is versioned as heuristic_overlap_v1.",
        },
        {
            "decision": "Incomplete gold rows stay executable and contribute to provisional or diagnostic signals when possible.",
            "rationale": "Missing expected answers, evidence, aliases, or answerability labels should not block actual RAG pipeline measurement.",
        },
        {
            "decision": "Retriever ranking is not tuned by this runner.",
            "rationale": "This lane measures actual RAG behavior and only adapts retrieval outputs into the metric contract.",
        },
        {
            "decision": "Metric-semantics repair demotes tautological consistency checks and tightens weak evidence matching.",
            "rationale": "Forward progress remains the default, but provisional E2E must fail when the answer judge fails, and weak evidence text overlap must include a non-generic anchor.",
        },
    ]


def _pipeline_error_output(item: EvalItem, reason: str) -> dict[str, Any]:
    return {
        "id": item.id,
        "query": item.query,
        "answerability": item.answerability,
        "generated_answer": "",
        "retrieved_contexts": [],
        "citations": [],
        "expected_answer": item.expected_answer,
        "expected_answer_aliases": list(item.expected_answer_aliases),
        "expected_evidence": [evidence.to_dict() for evidence in item.expected_evidence],
        "metric_inputs_available": _metric_inputs_available(item, has_citations=False),
        "diagnostics": {
            "retrieval_empty": True,
            "generation_empty": True,
            "citation_empty": True,
            "gold_incomplete": True,
            "pipeline_error": reason,
        },
        "pipeline_error": reason,
    }


def _metric_inputs_available(item: EvalItem, *, has_citations: bool) -> dict[str, bool]:
    return {
        "has_expected_answer": item.has_expected_answer,
        "has_expected_evidence": item.has_expected_evidence,
        "has_answerability_label": item.has_answerability_label,
        "has_citations": bool(has_citations),
    }


def _diagnostics_for_output(
    item: EvalItem,
    *,
    generated_answer: str,
    contexts: Sequence[Mapping[str, Any]],
    citations: Sequence[Mapping[str, Any]],
) -> dict[str, bool]:
    gold_incomplete = (
        not item.has_answerability_label
        or (item.answerability == "answerable" and (not item.has_expected_answer or not item.has_expected_evidence))
    )
    return {
        "retrieval_empty": not bool(contexts),
        "generation_empty": not bool(_clean(generated_answer)),
        "citation_empty": not bool(citations),
        "gold_incomplete": gold_incomplete,
    }


def load_context_overrides(path: Path | str) -> dict[str, dict[str, Any]]:
    overrides: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(Path(path)):
        row_id = _clean(row.get("id") or row.get("query_id"))
        if not row_id:
            raise DatasetSchemaError(f"{path}: context JSONL row missing id")
        if row_id in overrides:
            raise DatasetSchemaError(f"{path}: duplicate context row id {row_id}")
        overrides[row_id] = row
    return overrides


def _normalize_context(row: Mapping[str, Any], rank: int) -> dict[str, Any]:
    score = row.get("score", 0.0)
    try:
        numeric_score = float(score)
    except (TypeError, ValueError):
        numeric_score = 0.0
    normalized = {
        "rank": int(row.get("rank") or rank),
        "doc_id": _clean(row.get("doc_id") or row.get("docId") or row.get("document_id") or row.get("documentId")),
        "chunk_id": _clean(row.get("chunk_id") or row.get("chunkId") or row.get("search_unit_id") or row.get("searchUnitId")),
        "score": numeric_score,
        "text": _clean(row.get("text") or row.get("snippet") or row.get("textPreview")),
    }
    for source_key, target_key in [
        ("source_family", "source_family"),
        ("source_kind", "source_kind"),
        ("source_title", "source_title"),
        ("source_safe_id", "source_safe_id"),
        ("source_atom_id", "source_atom_id"),
        ("evidence_bundle_id", "evidence_bundle_id"),
        ("search_unit_id", "search_unit_id"),
        ("search_view_id", "search_view_id"),
        ("provenance_hash", "provenance_hash"),
        ("source_text_sha256", "source_text_sha256"),
    ]:
        value = _clean(row.get(source_key))
        if value:
            normalized[target_key] = value
    for field in SOURCE_DERIVED_EVIDENCE_METADATA_FIELDS:
        if field in SOURCE_DERIVED_EVIDENCE_FORBIDDEN_FIELDS:
            continue
        value = row.get(field)
        if _source_value_present(value):
            normalized[field] = value
    for source_key in ("source_path", "local_path", "file_path", "raw_path", "path"):
        value = _clean(row.get(source_key))
        if not value:
            continue
        redacted, was_redacted = _redact_pathish_metadata(value)
        if redacted:
            normalized[f"{source_key}_redacted"] = redacted
        if was_redacted:
            normalized["source_path_redacted"] = True
    xlsx_locator_snapshot = _xlsx_locator_source_context_snapshot(row)
    if xlsx_locator_snapshot is not None:
        normalized[INTERNAL_XLSX_LOCATOR_SOURCE_CONTEXTS_KEY] = [xlsx_locator_snapshot]
    return normalized


def _normalize_citation(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = {
        "doc_id": _clean(row.get("doc_id") or row.get("docId") or row.get("document_id") or row.get("documentId")),
        "chunk_id": _clean(row.get("chunk_id") or row.get("chunkId") or row.get("search_unit_id") or row.get("searchUnitId")),
        "text": _clean(row.get("text") or row.get("snippet") or row.get("textPreview")),
    }
    for source_key, target_key in [
        ("source_atom_id", "source_atom_id"),
        ("evidence_bundle_id", "evidence_bundle_id"),
        ("search_unit_id", "search_unit_id"),
        ("search_view_id", "search_view_id"),
        ("source_text_sha256", "source_text_sha256"),
        ("text_sha256", "text_sha256"),
    ]:
        value = _clean(row.get(source_key))
        if value:
            normalized[target_key] = value
    for field in SOURCE_DERIVED_EVIDENCE_METADATA_FIELDS:
        if field in SOURCE_DERIVED_EVIDENCE_FORBIDDEN_FIELDS:
            continue
        value = row.get(field)
        if _source_value_present(value):
            normalized[field] = value
    return normalized


def _latency_distribution_ms(values: Sequence[float | int]) -> dict[str, float]:
    numeric = sorted(float(value) for value in values if isinstance(value, (int, float)))
    if not numeric:
        return {"p50": 0.0, "p95": 0.0}
    p50 = numeric[len(numeric) // 2] if len(numeric) % 2 else (numeric[len(numeric) // 2 - 1] + numeric[len(numeric) // 2]) / 2
    p95_index = min(len(numeric) - 1, max(0, math.ceil(len(numeric) * 0.95) - 1))
    return {"p50": round(float(p50), 6), "p95": round(float(numeric[p95_index]), 6)}


def _average(values: Sequence[float | int]) -> float:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return round(sum(numeric) / len(numeric), 6) if numeric else 0.0


def _context_backend_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _clean(row.get("doc_id")),
        _clean(row.get("chunk_id")),
        _sha256_text(_clean(row.get("text"))),
    )


def _context_preview(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rank": row.get("rank"),
        "doc_id": _clean(row.get("doc_id")),
        "chunk_id": _clean(row.get("chunk_id")),
        "score": row.get("score"),
        "retrieval_backend": _clean(row.get("retrieval_backend")),
        "text_sha256": _sha256_text(row.get("text")),
        "text_preview": _clean(row.get("text"))[:180],
    }


def fuse_hybrid_contexts(
    bm25_contexts: Sequence[Mapping[str, Any]],
    vector_contexts: Sequence[Mapping[str, Any]],
    *,
    top_k: int,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    fused: dict[tuple[str, str, str], dict[str, Any]] = {}
    for source, weight in ((bm25_contexts, 1.0), (vector_contexts, 1.0)):
        for position, row in enumerate(source, start=1):
            key = _context_backend_key(row)
            if key not in fused:
                fused[key] = dict(row)
                fused[key]["hybrid_sources"] = []
                fused[key]["fusion_score"] = 0.0
            fused[key]["fusion_score"] = float(fused[key].get("fusion_score") or 0.0) + weight / (rrf_k + position)
            fused[key]["hybrid_sources"].append(_clean(row.get("retrieval_backend")) or "unknown")
    ordered = sorted(
        fused.values(),
        key=lambda row: (
            -float(row.get("fusion_score") or 0.0),
            _clean(row.get("doc_id")),
            _clean(row.get("chunk_id")),
            _clean(row.get("text")),
        ),
    )[: max(0, int(top_k))]
    contexts: list[dict[str, Any]] = []
    for rank, row in enumerate(ordered, start=1):
        context = dict(row)
        context["rank"] = rank
        context["score"] = round(float(context.get("fusion_score") or context.get("score") or 0.0), 6)
        context["retrieval_backend"] = "hybrid"
        context["hybrid_sources"] = sorted(set(context.get("hybrid_sources") or []))
        contexts.append(context)
    return contexts


def _retrieval_backend_comparison(
    *,
    requested_backend: str,
    selected_backend: str,
    bm25_contexts: Sequence[Mapping[str, Any]],
    vector_contexts: Sequence[Mapping[str, Any]],
    hybrid_contexts: Sequence[Mapping[str, Any]],
    selected_contexts: Sequence[Mapping[str, Any]],
    bm25_latency_ms: float,
    vector_latency_ms: float,
    hybrid_latency_ms: float,
    vector_available: bool,
    vector_fallback_reason: str = "",
) -> dict[str, Any]:
    bm25_keys = {_context_backend_key(row) for row in bm25_contexts}
    vector_keys = {_context_backend_key(row) for row in vector_contexts}
    hybrid_keys = {_context_backend_key(row) for row in hybrid_contexts}
    bm25_only_keys = bm25_keys - vector_keys
    vector_only_keys = vector_keys - bm25_keys
    hybrid_sources = [
        set(str(source) for source in (row.get("hybrid_sources") or []))
        for row in hybrid_contexts
        if isinstance(row, Mapping)
    ]
    selected_layer_counts = Counter(
        str(layer)
        for row in selected_contexts
        for layer in (row.get("layer_provenance") or [])
    )
    selected_vector_contribution_count = sum(
        1
        for row in selected_contexts
        if "vector" in set(str(source) for source in (row.get("hybrid_sources") or []))
        or "L2_semantic_vector_search" in set(str(layer) for layer in (row.get("layer_provenance") or []))
    )
    selected_bm25_contribution_count = sum(
        1
        for row in selected_contexts
        if "bm25" in set(str(source) for source in (row.get("hybrid_sources") or []))
        or bool(
            {"L1_lexical_anchor_search", "L3_query_variant_search"}
            & set(str(layer) for layer in (row.get("layer_provenance") or []))
        )
    )
    return {
        "requested_backend": requested_backend,
        "selected_backend": selected_backend,
        "bm25_top_k": [_context_preview(row) for row in bm25_contexts],
        "vector_top_k": [_context_preview(row) for row in vector_contexts],
        "hybrid_top_k": [_context_preview(row) for row in hybrid_contexts],
        "selected_top_k": [_context_preview(row) for row in selected_contexts],
        "latency_ms": {
            "bm25": round(float(bm25_latency_ms), 6),
            "vector": round(float(vector_latency_ms), 6),
            "hybrid": round(float(hybrid_latency_ms), 6),
        },
        "bm25_top_k_count": len(bm25_contexts),
        "vector_top_k_count": len(vector_contexts),
        "hybrid_top_k_count": len(hybrid_contexts),
        "bm25_vector_topk_overlap_count": len(bm25_keys & vector_keys),
        "bm25_only_candidate_count": len(bm25_only_keys),
        "vector_only_candidate_count": len(vector_only_keys),
        "hybrid_contains_vector_only_candidate_count": len(hybrid_keys & vector_only_keys),
        "hybrid_contains_bm25_only_candidate_count": len(hybrid_keys & bm25_only_keys),
        "vector_contribution_to_hybrid_topk_count": sum(1 for sources in hybrid_sources if "vector" in sources),
        "bm25_contribution_to_hybrid_topk_count": sum(1 for sources in hybrid_sources if "bm25" in sources),
        "selected_topk_layer_provenance_counts": dict(sorted(selected_layer_counts.items())),
        "vector_contribution_to_selected_topk_count": selected_vector_contribution_count,
        "bm25_contribution_to_selected_topk_count": selected_bm25_contribution_count,
        "merge_policy": "rrf_v1" if hybrid_contexts else "",
        "candidate_counts": {
            "bm25": len(bm25_contexts),
            "vector": len(vector_contexts),
            "hybrid": len(hybrid_contexts),
            "selected": len(selected_contexts),
        },
        "overlap_counts": {
            "bm25_vector_topk": len(bm25_keys & vector_keys),
        },
        "vector_available": bool(vector_available),
        "vector_fallback_reason": _clean(vector_fallback_reason),
        "candidate_generation_input_policy": "query_text_only_no_gold_qrels_labels_ids_or_baseline_topk",
    }


def _unavailable_retrieval_comparison(
    *,
    requested_backend: str,
    selected_backend: str,
    selected_contexts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return _retrieval_backend_comparison(
        requested_backend=requested_backend,
        selected_backend=selected_backend,
        bm25_contexts=selected_contexts if selected_backend == "bm25" else [],
        vector_contexts=[],
        hybrid_contexts=[],
        selected_contexts=selected_contexts,
        bm25_latency_ms=0.0,
        vector_latency_ms=0.0,
        hybrid_latency_ms=0.0,
        vector_available=False,
        vector_fallback_reason="vector_backend_not_invoked_for_precomputed_contexts",
    )


def _source_native_normalized_query(query: str) -> str:
    return re.sub(r"\s+", " ", _clean(query).replace("?", " ").replace("!", " ")).strip()


def _source_native_query_terms(query: str) -> list[str]:
    normalized = _source_native_normalized_query(query)
    return re.findall(r"\d+(?:[./:-]\d+)*|[A-Za-z][A-Za-z0-9_-]*|[가-힣]{2,}", normalized)


def _source_native_query_anchor_sets(query: str) -> dict[str, list[str]]:
    terms = _source_native_query_terms(query)
    numeric_or_date = [term for term in terms if any(ch.isdigit() for ch in term)]
    entities = [
        term
        for term in terms
        if (re.search(r"[가-힣]", term) and len(term) >= 2) or (term[:1].isupper() and len(term) > 1)
    ]
    rare = [
        term
        for term in terms
        if len(term) >= 4
        and term.casefold() not in GENERIC_ANCHOR_STOPWORDS
        and term not in numeric_or_date
    ]
    korean = [term for term in terms if re.search(r"[가-힣]", term)]
    return {
        "entities": _unique_preserving_order(entities),
        "numeric_or_date": _unique_preserving_order(numeric_or_date),
        "rare": _unique_preserving_order(rare),
        "korean": _unique_preserving_order(korean),
    }


def _unique_preserving_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        cleaned = _clean(value)
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)
    return unique


def _bounded_source_native_query_variants(query: str) -> list[str]:
    anchors = _source_native_query_anchor_sets(query)
    normalized = _source_native_normalized_query(query)
    candidates = [
        normalized,
        " ".join(anchors["entities"][:6]),
        " ".join([*anchors["entities"][:4], *anchors["numeric_or_date"][:4]]),
        " ".join(anchors["rare"][:6]),
        " ".join([*anchors["numeric_or_date"][:4], *anchors["rare"][:4]]),
        " ".join(anchors["korean"][:6]),
    ]
    if anchors["entities"] and anchors["rare"]:
        candidates.append(" ".join([anchors["entities"][0], *anchors["rare"][:4]]))
    if anchors["entities"] and anchors["numeric_or_date"]:
        candidates.append(" ".join([anchors["entities"][0], *anchors["numeric_or_date"][:4], "status"]))
    variants = _unique_preserving_order(candidates)
    return variants[: int(SOURCE_NATIVE_LAYERED_RETRIEVAL_BOUNDS["max_query_variants"])]


def _layered_context_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        _clean(row.get("doc_id")),
        _clean(row.get("chunk_id")),
        _clean(row.get("source_atom_id") or row.get("evidence_bundle_id")),
        _sha256_text(row.get("text")),
    )


def _annotate_source_native_layer_context(
    row: Mapping[str, Any],
    *,
    layer: str,
    query_variant: str,
    backend: str | None = None,
) -> dict[str, Any]:
    context = dict(row)
    context["retrieval_surface"] = "source_native"
    if backend:
        context["retrieval_backend"] = backend
    provenance = list(context.get("layer_provenance") or [])
    if layer not in provenance:
        provenance.append(layer)
    context["layer_provenance"] = provenance
    variants = list(context.get("query_variant_provenance") or [])
    if query_variant and query_variant not in variants:
        variants.append(query_variant)
    context["query_variant_provenance"] = variants
    return context


def _source_native_anchor_rerank_score(
    row: Mapping[str, Any],
    *,
    query: str,
    anchors: Mapping[str, Sequence[str]],
) -> tuple[float, dict[str, Any]]:
    text = _clean(row.get("text"))
    normalized_text = normalize_answer_text(text)
    numeric_hits = [
        anchor
        for anchor in anchors.get("numeric_or_date", [])
        if normalize_answer_text(anchor) and normalize_answer_text(anchor) in normalized_text
    ]
    rare_hits = [
        anchor
        for anchor in anchors.get("rare", [])
        if normalize_answer_text(anchor) and normalize_answer_text(anchor) in normalized_text
    ]
    entity_hits = [
        anchor
        for anchor in anchors.get("entities", [])
        if normalize_answer_text(anchor) and normalize_answer_text(anchor) in normalized_text
    ]
    query_terms = set(term.casefold() for term in _source_native_query_terms(query))
    text_terms = set(term.casefold() for term in _source_native_query_terms(text))
    generic_overlap = sorted((query_terms & text_terms) & GENERIC_ANCHOR_STOPWORDS)
    base = float(row.get("fusion_score") or row.get("score") or 0.0)
    bonus = (len(numeric_hits) * 0.08) + (len(rare_hits) * 0.05) + (len(entity_hits) * 0.03)
    penalty = len(generic_overlap) * 0.01
    diagnostics = {
        "numeric_or_date_anchor_hits": numeric_hits[:8],
        "rare_anchor_hits": rare_hits[:8],
        "entity_anchor_hits": entity_hits[:8],
        "generic_overlap_penalty_terms": generic_overlap[:8],
        "source_family_mismatch": False,
    }
    return base + bonus - penalty, diagnostics


def _empty_source_native_layered_retrieval_report(
    *,
    selected_surface: str,
    selected_backend: str,
    legacy_surface_comparison: bool = False,
    fallback_reason: str = "",
) -> dict[str, Any]:
    return {
        "enabled": False,
        "planner": "bounded_deterministic_source_native_layered_retrieval_v1",
        "selected_surface": selected_surface,
        "selected_backend": selected_backend,
        "layers": list(SOURCE_NATIVE_LAYERED_RETRIEVAL_LAYERS),
        "query_variants": [],
        "query_variant_count": 0,
        "backend_call_count": 0,
        "per_layer_candidate_counts": {layer: 0 for layer in SOURCE_NATIVE_LAYERED_RETRIEVAL_LAYERS},
        "per_layer_latency_ms": {layer: 0.0 for layer in SOURCE_NATIVE_LAYERED_RETRIEVAL_LAYERS},
        "merge_policy": "rrf_v1",
        "rerank_policy": "anchor_aware_diagnostic_rerank_v1",
        "final_candidate_count": 0,
        "bounds": dict(SOURCE_NATIVE_LAYERED_RETRIEVAL_BOUNDS),
        "gold_fields_used_for_candidate_generation": False,
        "expected_fields_used_for_candidate_generation": False,
        "qrels_used_for_candidate_generation": False,
        "answerability_labels_used_for_candidate_generation": False,
        "ids_used_for_candidate_generation": False,
        "baseline_topk_used_for_candidate_generation": False,
        "searchunit_searchview_used_as_candidate_surface": False,
        "legacy_searchunit_comparison_enabled": bool(legacy_surface_comparison),
        "source_native_units_only": selected_surface == "source_native",
        "fallback_reason": fallback_reason,
    }


class JsonlContextAdapter:
    def __init__(self, path: Path | str, *, requested_backend: str = "auto") -> None:
        self.path = Path(path)
        self.requested_backend = _clean(requested_backend) or "auto"
        self.rows = load_context_overrides(self.path)
        self.generator = ExtractiveGenerator()

    @property
    def config(self) -> dict[str, Any]:
        return {
            "adapter": "jsonl_context_override",
            "context_jsonl": self.path.as_posix(),
            "retrieval_source": "deterministic_fixture_or_precomputed_pipeline_output",
            "candidate_generation_input_policy": "precomputed_fixture_rows_keyed_by_item_id_only",
        }

    @property
    def retrieval_backend_report(self) -> dict[str, Any]:
        return {
            "requested": self.requested_backend,
            "selected": "precomputed_context",
            "bm25_enabled": False,
            "vector_enabled": False,
            "hybrid_enabled": False,
            "embedding_model": "",
            "embedding_device": "unavailable",
            "gpu_used_for_embedding": False,
            "vector_index_kind": "unavailable",
            "vector_index_type": "unavailable",
            "vector_dim": 0,
            "indexed_unit_count": 0,
            "query_count": len(self.rows),
            "fallback_reason": "context_jsonl_precomputed_fixture_path",
        }

    def run_item(self, item: EvalItem, *, top_k: int) -> dict[str, Any]:
        row = self.rows.get(item.id)
        if row is None:
            contexts: list[dict[str, Any]] = []
            citations: list[dict[str, Any]] = []
            generated_answer = ""
        else:
            contexts = [
                _normalize_context(context, rank=index)
                for index, context in enumerate(_as_list(row.get("retrieved_contexts")), start=1)
                if isinstance(context, Mapping)
            ][:top_k]
            citations = [
                _normalize_citation(citation)
                for citation in _as_list(row.get("citations"))
                if isinstance(citation, Mapping)
            ]
            generated_answer = _clean(row.get("generated_answer"))
            if not generated_answer and contexts:
                generated_answer = self.generator.generate(item.query, [_context_to_chunk(context) for context in contexts])
        output = _item_output(item, generated_answer=generated_answer, contexts=contexts, citations=citations)
        output["retrieval_backend_comparison"] = _unavailable_retrieval_comparison(
            requested_backend=self.requested_backend,
            selected_backend="precomputed_context",
            selected_contexts=contexts,
        )
        output["diagnostics"]["retrieval_backend_comparison"] = output["retrieval_backend_comparison"]
        return output

    def evidence_candidates(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        return []

    def full_corpus_evidence_candidates(
        self,
        item: EvalItem,
        evidence: ExpectedEvidence,
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        return []


def _source_derived_searchview_payloads(root: Path) -> list[dict[str, Any]]:
    """Build candidate-only SearchUnit/SearchView payloads without importing FAISS."""
    from ai.eval import rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check as v62

    source_rows = v62._select_source_rows(root)  # type: ignore[attr-defined]
    payloads: list[dict[str, Any]] = []
    for ordinal, row in enumerate(source_rows, start=1):
        family = _clean(row.get("source_family") or row.get("sourceFamily")).upper()
        text = _clean(row.get("_v62_candidate_text"))
        if not text:
            text = v62._semantic_candidate_text(row)  # type: ignore[attr-defined]
        source_atom_id = _clean(row.get("source_atom_id") or row.get("sourceAtomId")) or f"source_atom_sha_{_sha256_text(text)[:24]}"
        source_safe_id = f"actual_rag_source_{_sha256_text(source_atom_id)[:24]}"
        search_unit_id = f"actual_rag_su_{family.lower()}_{ordinal:03d}_{_sha256_text(source_atom_id + text)[:12]}"
        search_view_id = f"actual_rag_sv_{family.lower()}_{ordinal:03d}_{_sha256_text(text + source_atom_id)[:12]}"
        provenance_hash = _sha256_text(json.dumps({"source_atom_id": source_atom_id, "text": text}, ensure_ascii=False, sort_keys=True))
        metadata = {
            "candidate_only_payload_role": "SearchView",
            "evidence_truth_role": "SourceAtom/EvidenceBundle",
            "materialization_bucket": _clean(row.get("materialization_bucket")) or "source_atom_ready",
            "meaningful_semantic_text": True,
            "provenance_hash": provenance_hash,
            "source_atom_id": source_atom_id,
            "source_family": family,
            "source_safe_id": source_safe_id,
            "source_text_sha256": _sha256_text(text),
            "unit_type": "source_derived_semantic_snippet",
        }
        payload = {
            "payload_id": f"actual_rag_payload_{ordinal:03d}_{_sha256_text(search_view_id)[:12]}",
            "namespace": "actual_rag_eval_nonprod_searchunit_searchview",
            "source_family": family,
            "search_unit_id": search_unit_id,
            "search_view_id": search_view_id,
            "source_atom_ids": [source_atom_id],
            "embedding_text": text,
            "bm25_text": text,
            "metadata": metadata,
            "provenance_hash": provenance_hash,
        }
        forbidden_paths = v62._forbidden_field_paths(payload)  # type: ignore[attr-defined]
        if forbidden_paths:
            raise ValueError(f"actual RAG SearchView payload contains forbidden fields: {forbidden_paths}")
        for field in ("embedding_text", "bm25_text"):
            v62._require_no_forbidden_candidate_text(_clean(payload.get(field)), context=f"actual_rag_eval {field}")  # type: ignore[attr-defined]
        payloads.append(payload)
    return payloads


class RepoCurrentBm25Adapter:
    """Use the repo's current SearchUnit/SearchView materialization with BM25 only.

    This is a compatibility adapter for actual-RAG eval execution. It reuses the
    v6.3 source-derived SearchUnit/SearchView surface and BM25 text fields, but
    does not tune or alter ranking algorithms.
    """

    def __init__(self, root: Path | str = ROOT, *, payloads: Sequence[Mapping[str, Any]] | None = None) -> None:
        self.root = Path(root)
        self.generator = ExtractiveGenerator()
        self._payloads: list[dict[str, Any]] | None = [dict(payload) for payload in payloads] if payloads is not None else None

    @property
    def config(self) -> dict[str, Any]:
        return {
            "adapter": "repo_current_v63_searchunit_bm25",
            "index": "current-searchunit-searchview-surface",
            "ranking_change": False,
            "external_api_calls": False,
        }

    def _load_payloads(self) -> list[dict[str, Any]]:
        if self._payloads is not None:
            return self._payloads
        self._payloads = [dict(payload) for payload in _source_derived_searchview_payloads(self.root)]
        return self._payloads

    def run_item(self, item: EvalItem, *, top_k: int) -> dict[str, Any]:
        payloads = self._load_payloads()
        contexts = self._bm25_contexts(item.query, payloads, top_k=top_k)
        citations = [_normalize_citation(context) for context in contexts]
        generated_answer = self.generator.generate(item.query, [_context_to_chunk(context) for context in contexts])
        return _item_output(item, generated_answer=generated_answer, contexts=contexts, citations=citations)

    def evidence_candidates(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        if not _clean(query):
            return []
        return self._bm25_contexts(query, self._load_payloads(), top_k=top_k)

    def full_corpus_evidence_candidates(
        self,
        item: EvalItem,
        evidence: ExpectedEvidence,
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        return []

    @staticmethod
    def _tokenize(value: str) -> list[str]:
        return [token for token in "".join(ch.casefold() if ch.isalnum() else " " for ch in value).split() if len(token) > 1]

    def _bm25_contexts(self, query: str, payloads: Sequence[Mapping[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
        query_terms = self._tokenize(query)
        docs = [self._tokenize(_clean(payload.get("bm25_text") or payload.get("embedding_text"))) for payload in payloads]
        doc_count = max(len(docs), 1)
        doc_freq = Counter(term for doc in docs for term in set(doc))
        avg_len = sum(len(doc) for doc in docs) / doc_count if docs else 1.0
        scored: list[tuple[float, Mapping[str, Any]]] = []
        for payload, doc_terms in zip(payloads, docs, strict=True):
            term_counts = Counter(doc_terms)
            doc_len = max(len(doc_terms), 1)
            score = 0.0
            for term in query_terms:
                if not term_counts[term]:
                    continue
                idf = math.log(1 + (doc_count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                score += idf * (term_counts[term] * 2.2) / (
                    term_counts[term] + 1.2 * (0.25 + 0.75 * doc_len / max(avg_len, 1e-9))
                )
            if score > 0:
                scored.append((score, payload))
        scored.sort(key=lambda item: (-item[0], _clean(item[1].get("search_unit_id"))))
        contexts: list[dict[str, Any]] = []
        for rank, (score, payload) in enumerate(scored[:top_k], start=1):
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
            contexts.append(
                {
                    "rank": rank,
                    "doc_id": _clean(metadata.get("source_safe_id") or payload.get("source_family")),
                    "chunk_id": _clean(payload.get("search_unit_id")),
                    "score": round(float(score), 6),
                    "text": _clean(payload.get("bm25_text") or payload.get("embedding_text")),
                    "retrieval_backend": "bm25",
                    "source_family": _clean(payload.get("source_family")),
                    "search_unit_id": _clean(payload.get("search_unit_id")),
                    "search_view_id": _clean(payload.get("search_view_id")),
                    "source_text_sha256": _clean(metadata.get("source_text_sha256")),
                    "source_atom_id": _clean(payload.get("source_atom_id") or metadata.get("source_atom_id")),
                    "evidence_bundle_id": _clean(payload.get("evidence_bundle_id") or metadata.get("evidence_bundle_id")),
                    "retrieval_surface": _clean(payload.get("retrieval_surface") or metadata.get("retrieval_surface") or "searchunit_searchview"),
                    "title": _clean(payload.get("title") or metadata.get("title")),
                    "section": _clean(payload.get("section") or metadata.get("section")),
                }
            )
        return contexts


class RepoCurrentHybridAdapter(RepoCurrentBm25Adapter):
    """Repo-current SearchUnit/SearchView BM25, vector, and hybrid retrieval.

    Candidate generation uses only the user query text and source-derived
    SearchView payload text. Gold, qrels, expected evidence, row ids, query ids,
    target ids, and baseline top-k are not inputs to this adapter.
    """

    def __init__(
        self,
        root: Path | str = ROOT,
        *,
        requested_backend: str = "auto",
        embedding_provider: Any | None = None,
        gpu_preflight: Mapping[str, Any] | None = None,
        external_vector_db: Mapping[str, Any] | None = None,
        payloads: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        super().__init__(root=root, payloads=payloads)
        self.requested_backend = _clean(requested_backend).lower() or "auto"
        if self.requested_backend not in {"auto", "bm25", "vector", "hybrid"}:
            raise DatasetSchemaError(f"unsupported retrieval backend: {requested_backend}")
        self.embedding_provider = embedding_provider
        self.gpu_preflight = dict(gpu_preflight or {})
        self.external_vector_db = dict(external_vector_db or {})
        self._vector_ready = False
        self._vector_attempted = False
        self._vector_fallback_reason = ""
        self._vector_index = None
        self._vector_id_map: list[dict[str, Any]] = []
        self._embedder: Any | None = None
        self._vector_dim = 0
        self._embedding_model = ""
        self._embedding_device = "unavailable"
        self._gpu_used_for_embedding = False
        self._embedding_build_latency_ms = 0.0
        self._index_load_or_build_latency_ms = 0.0
        self._query_count = 0

    @property
    def config(self) -> dict[str, Any]:
        return {
            "adapter": "repo_current_searchunit_vector_hybrid",
            "index": "current-searchunit-searchview-surface",
            "requested_backend": self.requested_backend,
            "selected_backend": self._selected_backend_name(),
            "ranking_change": True,
            "ranking_change_claimed_as_improvement": False,
            "external_api_calls": False,
            "candidate_generation_input_policy": "query_text_only_no_gold_qrels_labels_ids_or_baseline_topk",
        }

    @property
    def retrieval_backend_report(self) -> dict[str, Any]:
        if self.requested_backend != "bm25":
            self._ensure_vector_ready()
        selected = self._selected_backend_name()
        return {
            "requested": self.requested_backend,
            "selected": selected,
            "bm25_enabled": selected in {"bm25", "hybrid"} or self.requested_backend in {"auto", "bm25", "hybrid"},
            "vector_enabled": self._vector_ready and selected in {"vector", "hybrid"},
            "hybrid_enabled": self._vector_ready and selected == "hybrid",
            "embedding_model": self._embedding_model,
            "embedding_device": self._embedding_device,
            "gpu_used_for_embedding": self._gpu_used_for_embedding,
            "vector_index_kind": "faiss" if self._vector_ready else "unavailable",
            "vector_index_type": "IndexFlatIP" if self._vector_ready else "unavailable",
            "vector_dim": self._vector_dim,
            "indexed_unit_count": len(self._vector_id_map),
            "query_count": self._query_count,
            "fallback_reason": None if self._vector_ready else (self._vector_fallback_reason or "vector_backend_unavailable"),
        }

    @property
    def backend_diagnostics(self) -> dict[str, Any]:
        return {
            "embedding_build_latency_ms": self._embedding_build_latency_ms,
            "index_load_or_build_latency_ms": self._index_load_or_build_latency_ms,
            "vector_index_available": self._vector_ready,
            "gpu_used_for_embedding": self._gpu_used_for_embedding,
            "fallback_reason": "" if self._vector_ready else self._vector_fallback_reason,
        }

    def _selected_backend_name(self) -> str:
        if self.requested_backend == "bm25":
            return "bm25"
        if self._ensure_vector_ready():
            if self.requested_backend in {"auto", "hybrid"}:
                return "hybrid"
            if self.requested_backend == "vector":
                return "vector"
        return "bm25"

    def _ensure_vector_ready(self) -> bool:
        if self._vector_attempted:
            return self._vector_ready
        self._vector_attempted = True
        try:
            import numpy as np  # type: ignore
            import faiss  # type: ignore
        except Exception as exc:
            self._vector_fallback_reason = f"faiss_or_numpy_unavailable:{type(exc).__name__}: {exc}"
            return False

        payloads = self._load_payloads()
        texts = [_clean(payload.get("embedding_text") or payload.get("bm25_text")) for payload in payloads]
        try:
            embedder = self.embedding_provider
            if embedder is None:
                from app.capabilities.rag.embeddings import SentenceTransformerEmbedder, resolve_max_seq_length

                embedder = SentenceTransformerEmbedder(
                    model_name="BAAI/bge-m3",
                    max_seq_length=resolve_max_seq_length(
                        int(os.environ.get("ACTUAL_RAG_EVAL_BGE_M3_MAX_SEQ_LENGTH", "1024"))
                    ),
                    batch_size=int(os.environ.get("ACTUAL_RAG_EVAL_BGE_M3_BATCH_SIZE", "32")),
                    show_progress_bar=False,
                    local_files_only=True,
                )
            embed_started = time.perf_counter()
            vectors = embedder.embed_passages(texts)
            self._embedding_build_latency_ms = round((time.perf_counter() - embed_started) * 1000, 6)
            vectors = np.ascontiguousarray(vectors, dtype=np.float32)
            if vectors.ndim != 2 or vectors.shape[0] != len(payloads) or vectors.shape[1] <= 0:
                raise RuntimeError("embedding_matrix_shape_invalid")
            build_started = time.perf_counter()
            index = faiss.IndexFlatIP(int(vectors.shape[1]))
            index.add(vectors)
            self._index_load_or_build_latency_ms = round((time.perf_counter() - build_started) * 1000, 6)
            self._vector_index = index
            self._vector_id_map = [dict(payload) for payload in payloads]
            self._embedder = embedder
            self._vector_dim = int(vectors.shape[1])
            self._embedding_model = _clean(getattr(embedder, "model_name", "")) or "BAAI/bge-m3"
            model = getattr(embedder, "_model", None)
            model_device = _clean(getattr(model, "device", ""))
            cuda_available = bool(self.gpu_preflight.get("torch_cuda_available"))
            self._embedding_device = model_device or ("cuda:0" if cuda_available else "cpu")
            self._gpu_used_for_embedding = "cuda" in self._embedding_device.lower()
            self._vector_ready = True
            self._vector_fallback_reason = ""
        except Exception as exc:
            self._vector_ready = False
            self._vector_fallback_reason = f"vector_build_failed:{type(exc).__name__}: {exc}"
        return self._vector_ready

    def _vector_contexts(self, query: str, *, top_k: int) -> tuple[list[dict[str, Any]], float]:
        if not _clean(query):
            return [], 0.0
        if not self._ensure_vector_ready() or self._vector_index is None:
            return [], 0.0
        try:
            import numpy as np  # type: ignore
        except Exception:
            return [], 0.0
        started = time.perf_counter()
        try:
            if self._embedder is None:
                raise RuntimeError("vector_embedder_not_loaded")
            query_vectors = self._embedder.embed_queries([query])
            qvec = np.ascontiguousarray(query_vectors, dtype=np.float32)
            scores, ids = self._vector_index.search(qvec, min(int(top_k), len(self._vector_id_map)))
        except Exception as exc:
            self._vector_fallback_reason = f"vector_query_failed:{type(exc).__name__}: {exc}"
            return [], round((time.perf_counter() - started) * 1000, 6)
        contexts: list[dict[str, Any]] = []
        for rank, (row_id, score) in enumerate(zip(ids[0], scores[0]), start=1):
            if int(row_id) < 0:
                continue
            payload = self._vector_id_map[int(row_id)]
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
            contexts.append(
                {
                    "rank": rank,
                    "doc_id": _clean(metadata.get("source_safe_id") or payload.get("source_family")),
                    "chunk_id": _clean(payload.get("search_unit_id")),
                    "score": round(float(score), 6),
                    "text": _clean(payload.get("embedding_text") or payload.get("bm25_text")),
                    "retrieval_backend": "vector",
                    "source_family": _clean(payload.get("source_family")),
                    "search_unit_id": _clean(payload.get("search_unit_id")),
                    "search_view_id": _clean(payload.get("search_view_id")),
                    "source_text_sha256": _clean(metadata.get("source_text_sha256")),
                }
            )
        self._query_count += 1
        return contexts, round((time.perf_counter() - started) * 1000, 6)

    def run_item(self, item: EvalItem, *, top_k: int) -> dict[str, Any]:
        payloads = self._load_payloads()
        bm25_started = time.perf_counter()
        bm25_contexts = self._bm25_contexts(item.query, payloads, top_k=top_k)
        bm25_latency = round((time.perf_counter() - bm25_started) * 1000, 6)
        if self.requested_backend == "bm25":
            vector_contexts: list[dict[str, Any]] = []
            vector_latency = 0.0
            hybrid_contexts = []
            hybrid_latency = 0.0
            if not self._vector_fallback_reason:
                self._vector_fallback_reason = "vector_backend_not_requested_for_bm25_surface"
        else:
            vector_contexts, vector_latency = self._vector_contexts(item.query, top_k=top_k)
            hybrid_started = time.perf_counter()
            hybrid_contexts = fuse_hybrid_contexts(bm25_contexts, vector_contexts, top_k=top_k)
            hybrid_latency = round((time.perf_counter() - hybrid_started) * 1000, 6) + bm25_latency + vector_latency
        selected_backend = self._selected_backend_name()
        selected_contexts = {
            "bm25": bm25_contexts,
            "vector": vector_contexts,
            "hybrid": hybrid_contexts,
        }.get(selected_backend, bm25_contexts)
        citations = [_normalize_citation(context) for context in selected_contexts]
        generated_answer = self.generator.generate(item.query, [_context_to_chunk(context) for context in selected_contexts])
        output = _item_output(item, generated_answer=generated_answer, contexts=selected_contexts, citations=citations)
        output["retrieval_backend_comparison"] = _retrieval_backend_comparison(
            requested_backend=self.requested_backend,
            selected_backend=selected_backend,
            bm25_contexts=bm25_contexts,
            vector_contexts=vector_contexts,
            hybrid_contexts=hybrid_contexts,
            selected_contexts=selected_contexts,
            bm25_latency_ms=bm25_latency,
            vector_latency_ms=vector_latency,
            hybrid_latency_ms=hybrid_latency,
            vector_available=self._vector_ready,
            vector_fallback_reason=self._vector_fallback_reason,
        )
        output["diagnostics"]["retrieval_backend_comparison"] = output["retrieval_backend_comparison"]
        return output

    def evidence_candidates(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        selected_backend = self._selected_backend_name()
        bm25_contexts = self._bm25_contexts(query, self._load_payloads(), top_k=top_k)
        if selected_backend == "bm25":
            return bm25_contexts
        vector_contexts, _latency = self._vector_contexts(query, top_k=top_k)
        if selected_backend == "vector":
            return vector_contexts
        if selected_backend == "hybrid":
            return fuse_hybrid_contexts(bm25_contexts, vector_contexts, top_k=top_k)
        return bm25_contexts


class FakeVectorAdapter:
    """Deterministic test adapter that exposes BM25, vector, and hybrid rows."""

    def __init__(self, *, requested_backend: str = "auto") -> None:
        self.requested_backend = _clean(requested_backend) or "auto"
        self.generator = ExtractiveGenerator()

    @property
    def config(self) -> dict[str, Any]:
        return {
            "adapter": "deterministic_fake_vector_adapter",
            "requested_backend": self.requested_backend,
            "candidate_generation_input_policy": "query_text_only_no_reference_fields",
            "external_api_calls": False,
        }

    @property
    def retrieval_backend_report(self) -> dict[str, Any]:
        return {
            "requested": self.requested_backend,
            "selected": "hybrid",
            "bm25_enabled": True,
            "vector_enabled": True,
            "hybrid_enabled": True,
            "embedding_model": "deterministic-test-vector",
            "embedding_device": "cpu",
            "gpu_used_for_embedding": False,
            "vector_index_kind": "fake_in_memory",
            "vector_index_type": "deterministic",
            "vector_dim": 4,
            "indexed_unit_count": 2,
            "query_count": 1,
            "fallback_reason": None,
        }

    @property
    def backend_diagnostics(self) -> dict[str, Any]:
        return {
            "embedding_build_latency_ms": 1.0,
            "index_load_or_build_latency_ms": 1.0,
            "vector_index_available": True,
            "gpu_used_for_embedding": False,
            "fallback_reason": "",
        }

    def run_item(self, item: EvalItem, *, top_k: int) -> dict[str, Any]:
        bm25_contexts = [
            {
                "rank": 1,
                "doc_id": "doc-a",
                "chunk_id": "c1",
                "score": 2.0,
                "text": "Seoul is the capital.",
                "retrieval_backend": "bm25",
            }
        ][:top_k]
        vector_contexts = [
            {
                "rank": 1,
                "doc_id": "doc-a",
                "chunk_id": "c1",
                "score": 0.99,
                "text": "Seoul is the capital.",
                "retrieval_backend": "vector",
            },
            {
                "rank": 2,
                "doc_id": "doc-b",
                "chunk_id": "c2",
                "score": 0.5,
                "text": "Busan is a port city.",
                "retrieval_backend": "vector",
            },
        ][:top_k]
        hybrid_contexts = fuse_hybrid_contexts(bm25_contexts, vector_contexts, top_k=top_k)
        generated_answer = self.generator.generate(item.query, [_context_to_chunk(context) for context in hybrid_contexts])
        citations = [_normalize_citation(context) for context in hybrid_contexts]
        output = _item_output(item, generated_answer=generated_answer, contexts=hybrid_contexts, citations=citations)
        output["retrieval_backend_comparison"] = _retrieval_backend_comparison(
            requested_backend=self.requested_backend,
            selected_backend="hybrid",
            bm25_contexts=bm25_contexts,
            vector_contexts=vector_contexts,
            hybrid_contexts=hybrid_contexts,
            selected_contexts=hybrid_contexts,
            bm25_latency_ms=1.0,
            vector_latency_ms=2.0,
            hybrid_latency_ms=3.0,
            vector_available=True,
        )
        output["diagnostics"]["retrieval_backend_comparison"] = output["retrieval_backend_comparison"]
        return output

    def evidence_candidates(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        return self.run_item(EvalItem(id="lookup", query=query), top_k=top_k)["retrieved_contexts"]


def _sanitize_source_native_text(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""

    def redact_match(match: re.Match[str]) -> str:
        raw = match.group(0)
        return f"redacted_path_sha256:{_sha256_text(raw)[:16]}"

    text = re.sub(r"[A-Za-z]:[\\/][^\s|)]+", redact_match, text)
    text = re.sub(r"local-storage[\\/][^\s|)]+", redact_match, text)
    return text


def _canonical_candidate_field_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean(value).casefold())


SOURCE_NATIVE_FORBIDDEN_CANDIDATE_CANONICAL_FIELDS = frozenset(
    _canonical_candidate_field_name(field) for field in SOURCE_NATIVE_FORBIDDEN_CANDIDATE_FIELD_NAMES
)


def _source_native_forbidden_field_paths(value: Any, *, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if _canonical_candidate_field_name(key_text) in SOURCE_NATIVE_FORBIDDEN_CANDIDATE_CANONICAL_FIELDS:
                paths.append(path)
            paths.extend(_source_native_forbidden_field_paths(child, prefix=path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            paths.extend(_source_native_forbidden_field_paths(child, prefix=f"{prefix}[{index}]"))
    return paths


def _require_no_source_native_forbidden_fields(value: Mapping[str, Any], *, context: str) -> None:
    paths = _source_native_forbidden_field_paths(value)
    if paths:
        raise DatasetSchemaError(f"{context} contains forbidden source-native candidate fields: {paths}")


def _require_no_source_native_forbidden_candidate_text(value: str, *, context: str) -> None:
    lowered = _clean(value).casefold()
    found = [marker for marker in SOURCE_NATIVE_FORBIDDEN_CANDIDATE_TEXT_MARKERS if marker in lowered]
    if found:
        raise DatasetSchemaError(f"{context} contains forbidden candidate text markers: {found}")


def _diagnostic_hash_vectors(texts: Sequence[str], *, dimension: int = 128) -> Any:
    import numpy as np  # type: ignore

    rows: list[Any] = []
    for text in texts:
        vector = np.zeros((dimension,), dtype=np.float32)
        normalized = " ".join(_clean(text).casefold().split())
        tokens = normalized.split() or [normalized or "empty"]
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:4], "little") % dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = float(np.linalg.norm(vector))
        if norm > 0:
            vector /= norm
        rows.append(vector)
    return np.vstack(rows).astype(np.float32) if rows else np.zeros((0, dimension), dtype=np.float32)


class FakeDeterministicEmbeddingProvider:
    """Small deterministic embedder for source-native vector tests."""

    model_name = "deterministic-test-source-native-vector"
    python_only_vector_search = True

    def embed_passages(self, texts: Sequence[str]) -> Any:
        return _diagnostic_hash_vectors(list(texts), dimension=16)

    def embed_queries(self, texts: Sequence[str]) -> Any:
        return self.embed_passages(texts)


class SourceNativeCorpusLoader:
    """Read-only loader for source-owned SourceAtom/EvidenceBundle retrieval units."""

    def __init__(
        self,
        *,
        search_view_manifest_path: Path | str = SOURCE_NATIVE_SEARCH_VIEW_MANIFEST_PATH,
        source_atom_registry_path: Path | str = SOURCE_NATIVE_SOURCE_REGISTRY_PATH,
        synthesize_xlsx_row_value_bundles: bool = False,
    ) -> None:
        self.search_view_manifest_path = Path(search_view_manifest_path)
        self.source_atom_registry_path = Path(source_atom_registry_path)
        self.synthesize_xlsx_row_value_bundles = bool(synthesize_xlsx_row_value_bundles)
        self._source_atom_registry_structural_metadata: dict[str, dict[str, str]] | None = None

    @property
    def available(self) -> bool:
        return self.search_view_manifest_path.exists()

    def describe(self) -> dict[str, Any]:
        return {
            "preferred_surface_order": [
                "evidence_bundle",
                "source_atom",
                "source_registry_materialized_text",
                "raw_source_derived_chunks",
                "source_native_manifest_materialized_text",
            ],
            "selected_source": "source_atom" if self.available else "unavailable",
            "search_view_manifest_path_hash": f"sha256:{_sha256_text(self.search_view_manifest_path.as_posix())}",
            "source_atom_registry_path_hash": f"sha256:{_sha256_text(self.source_atom_registry_path.as_posix())}",
            "source_atom_registry_available": self.source_atom_registry_path.exists(),
            "synthesize_xlsx_row_value_bundles": self.synthesize_xlsx_row_value_bundles,
            "xlsx_row_value_bundle_policy": "source_owned_manifest_snapshot_no_gold_qrels_labels_or_normalized_fields_v1"
            if self.synthesize_xlsx_row_value_bundles
            else "",
            "read_only": True,
            "raw_local_paths_exposed": False,
        }

    def iter_units(self) -> Iterable[dict[str, Any]]:
        if not self.search_view_manifest_path.exists():
            return
        units: list[dict[str, Any]] = []
        with self.search_view_manifest_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if isinstance(row, Mapping):
                    unit = self._unit_from_row(row)
                    if unit.get("text"):
                        if self.synthesize_xlsx_row_value_bundles:
                            units.append(unit)
                        yield unit
        if self.synthesize_xlsx_row_value_bundles:
            yield from self._synthesize_xlsx_row_value_bundle_units(units)

    def load_units(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        units: list[dict[str, Any]] = []
        for unit in self.iter_units():
            units.append(unit)
            if limit is not None and len(units) >= limit:
                break
        return units

    def _unit_from_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        _require_no_source_native_forbidden_fields(row, context="SourceNativeCorpusLoader row")
        source_atom_id = _clean(row.get("source_atom_id") or row.get("sourceAtomId"))
        evidence_bundle_id = _clean(row.get("evidence_bundle_id") or row.get("evidenceBundleId"))
        search_view_id = _clean(row.get("search_view_id") or row.get("searchViewId"))
        source_identity = _clean(row.get("source_identity") or row.get("sourceIdentity"))
        text = _sanitize_source_native_text(
            row.get("bm25_text") or row.get("display_text") or row.get("embedding_text")
        )
        _require_no_source_native_forbidden_candidate_text(text, context="SourceNativeCorpusLoader text")
        family = _clean(row.get("source_family") or row.get("sourceFamily") or "unknown").upper() or "unknown"
        if family not in {"TEXT", "PDF", "XLSX"}:
            family = "unknown"
        title = _clean(row.get("workbook_id") or row.get("document_version_id") or row.get("document_id") or family)
        unit_id = source_atom_id or evidence_bundle_id or search_view_id or f"source_native_{_sha256_text(text)[:24]}"
        surface = "evidence_bundle" if evidence_bundle_id else "source_atom"
        metadata = {
            "source_identity_hash": f"sha256:{_sha256_text(source_identity)}" if source_identity else "",
            "source_registry_version": _clean(row.get("source_registry_version") or row.get("sourceRegistryVersion")),
            "materialization_bucket": _clean(row.get("materialization_bucket")),
            "canonical_payload_source": _clean(row.get("canonical_payload_source") or row.get("canonicalPayloadSource")),
            "faiss_row_id": int(row.get("faiss_row_id")) if str(row.get("faiss_row_id", "")).isdigit() else None,
            "raw_local_paths_exposed": False,
        }
        structural_source = {**self._registry_structural_metadata_for_source_atom(source_atom_id), **dict(row)}
        structural_metadata = self._structural_metadata_from_row(structural_source)
        metadata.update(structural_metadata)
        return {
            "unit_id": unit_id,
            "source_atom_id": source_atom_id,
            "evidence_bundle_id": evidence_bundle_id,
            "doc_id": _clean(
                row.get("document_version_id")
                or row.get("document_id")
                or row.get("workbook_version_id")
                or structural_metadata.get("workbook_version_id")
            )
            or f"source_native_doc_{_sha256_text(source_identity or unit_id)[:16]}",
            "chunk_id": source_atom_id or evidence_bundle_id or search_view_id or unit_id,
            "source_family": family,
            "title": title,
            "section": _clean(row.get("section") or row.get("search_view_kind") or row.get("searchViewKind")),
            "text": text,
            "metadata": metadata,
            "surface": surface,
            "text_sha256": _sha256_text(text),
            "faiss_row_id": metadata["faiss_row_id"],
        }

    def _registry_structural_metadata_for_source_atom(self, source_atom_id: str) -> dict[str, str]:
        if self._source_atom_registry_structural_metadata is None:
            self._source_atom_registry_structural_metadata = self._load_source_atom_registry_structural_metadata()
        return dict(self._source_atom_registry_structural_metadata.get(_clean(source_atom_id)) or {})

    def _load_source_atom_registry_structural_metadata(self) -> dict[str, dict[str, str]]:
        if not self.source_atom_registry_path.exists():
            return {}
        records: dict[str, dict[str, str]] = {}
        with self.source_atom_registry_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, Mapping):
                    continue
                source_atom_id = _clean(row.get("source_atom_id") or row.get("sourceAtomId"))
                if not source_atom_id:
                    continue
                structural = self._source_owned_structural_metadata_from_registry_row(row)
                if structural:
                    records[source_atom_id] = structural
        return records

    def _source_owned_structural_metadata_from_registry_row(self, row: Mapping[str, Any]) -> dict[str, str]:
        raw_locator = row.get("raw_locator") if isinstance(row.get("raw_locator"), Mapping) else {}
        citation = (
            row.get("canonical_citation_payload")
            if isinstance(row.get("canonical_citation_payload"), Mapping)
            else {}
        )
        track_locator = (
            citation.get("track_locator_payload")
            if isinstance(citation.get("track_locator_payload"), Mapping)
            else {}
        )

        def first(*values: Any) -> str:
            for value in values:
                if isinstance(value, (list, tuple)):
                    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                else:
                    text = _clean(value)
                if text:
                    return text
            return ""

        structural = {
            "workbook_id": first(row.get("workbook_id"), raw_locator.get("workbook"), citation.get("workbook")),
            "workbook_version_id": first(
                row.get("workbook_version_id"),
                raw_locator.get("document_version_id"),
                citation.get("document_version_id"),
            ),
            "sheet": first(raw_locator.get("sheet"), citation.get("sheet"), track_locator.get("sheet")),
            "cell_range": first(raw_locator.get("range"), citation.get("range"), track_locator.get("range")),
            "cell": first(raw_locator.get("cell"), citation.get("cell"), track_locator.get("cell")),
            "row_index_1based": first(
                raw_locator.get("row_index_1based"),
                raw_locator.get("row_number"),
                raw_locator.get("row"),
                citation.get("row_index_1based"),
                citation.get("row_number"),
                track_locator.get("row_index_1based"),
            ),
            "row_label": first(raw_locator.get("row_label"), citation.get("row_label"), track_locator.get("row_label")),
            "column_label": first(
                raw_locator.get("column_label"),
                citation.get("column_label"),
                track_locator.get("column_label"),
            ),
            "target_column": first(
                raw_locator.get("target_column"),
                citation.get("target_column"),
                track_locator.get("target_column"),
            ),
            "header": first(raw_locator.get("header"), citation.get("header"), track_locator.get("header")),
            "header_path": first(
                raw_locator.get("header_path"),
                raw_locator.get("column_header_path"),
                citation.get("header_path"),
                citation.get("column_header_path"),
                track_locator.get("header_path"),
            ),
            "table_id": first(raw_locator.get("table_id"), citation.get("table_id"), track_locator.get("table_id")),
            "page_number": first(raw_locator.get("page"), citation.get("page"), track_locator.get("page")),
            "physical_page_index": first(
                raw_locator.get("physical_page_index"),
                citation.get("physical_page_index"),
                track_locator.get("physical_page_index"),
            ),
            "block_index": first(raw_locator.get("block_index"), citation.get("block_index"), track_locator.get("block_index")),
            "bbox": first(raw_locator.get("bbox"), citation.get("bbox"), track_locator.get("bbox")),
            "region_type": first(raw_locator.get("region_type"), citation.get("region_type"), track_locator.get("region_type")),
            "section_title": first(
                raw_locator.get("section_title"),
                citation.get("section_title"),
                track_locator.get("section_title"),
            ),
            "table_caption": first(
                raw_locator.get("table_caption"),
                citation.get("table_caption"),
                track_locator.get("table_caption"),
            ),
            "locator_fingerprint": first(
                raw_locator.get("stable_locator_fingerprint"),
                raw_locator.get("locator_fingerprint"),
                citation.get("locator_fingerprint"),
                citation.get("locatorFingerprint"),
                row.get("locator_fingerprint"),
            ),
            "parent_source_unit_id": first(
                row.get("parent_source_unit_id"),
                row.get("parent_pointers", {}).get("source_unit_id") if isinstance(row.get("parent_pointers"), Mapping) else "",
            ),
        }
        return {key: value for key, value in structural.items() if value}

    def _source_owned_display_value_from_text(self, row: Mapping[str, Any], target_column: str) -> str:
        target = _clean(target_column)
        if not target:
            return ""
        forbidden_display_value_axes = {
            *XLSX_PDF_RESIDUAL_FORBIDDEN_SHORTCUT_FIELDS,
            *SOURCE_DERIVED_EVIDENCE_FORBIDDEN_FIELDS,
            "raw_prompt",
            "raw_response",
            "prompt_payload",
            "response_payload",
            "raw_prompt_payload",
            "raw_response_payload",
            "raw_tool_payload",
            "tool_payload",
        }

        def forbidden_axis_name(value: str) -> bool:
            text = _clean(value)
            canonical = _canonical_candidate_field_name(text) or _canonical_xlsx_locator_field_name(text)
            names = {text.casefold(), canonical.casefold() if canonical else ""}
            return bool(
                names & {field.casefold() for field in forbidden_display_value_axes}
                or _xlsx_locator_forbidden_text_fields(f"{text}=x")
            )

        if forbidden_axis_name(target):
            return ""
        display_text = _clean(row.get("display_text") or row.get("bm25_text") or row.get("embedding_text"))
        if not display_text:
            return ""

        def same_key(left: str, right: str) -> bool:
            left_text = " ".join(_clean(left).casefold().split())
            right_text = " ".join(_clean(right).casefold().split())
            if left_text and left_text == right_text:
                return True
            left_canonical = _canonical_candidate_field_name(left)
            right_canonical = _canonical_candidate_field_name(right)
            return bool(left_canonical and right_canonical and left_canonical == right_canonical)

        for segment in re.split(r"\s+\|\s+|\r?\n+", display_text):
            key, separator, value = _clean(segment).partition("=")
            if not separator or not same_key(key, target):
                continue
            if forbidden_axis_name(key):
                continue
            candidate = _clean(value).strip("|;,")
            lowered = candidate.casefold()
            if not candidate:
                continue
            if any(marker in lowered for marker in ("normalized_value", "formula", "source_path", "workbook=")):
                continue
            return candidate
        return ""

    def _structural_metadata_from_row(self, row: Mapping[str, Any]) -> dict[str, str]:
        source_identity = _clean(row.get("source_identity") or row.get("sourceIdentity"))
        display_text = _clean(row.get("display_text") or row.get("bm25_text") or row.get("embedding_text"))

        def first(*values: Any) -> str:
            for value in values:
                if isinstance(value, (list, tuple)):
                    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                else:
                    text = _clean(value)
                if text:
                    return text
            return ""

        def regex(pattern: str, text: str) -> str:
            match = re.search(pattern, text)
            return _clean(match.group(1)) if match else ""

        page_number = first(
            row.get("page"),
            row.get("page_number"),
            row.get("pageNumber"),
            row.get("page_candidate"),
            regex(r"\bpage[=:\s]+(\d+)\b", display_text),
            regex(r":(\d+):\[[^\]]+\]$", source_identity),
        )
        bbox = first(
            row.get("bbox"),
            row.get("bounding_box"),
            regex(r"\bbbox=([^|)]+)", display_text),
            regex(r":(\[[^\]]+\])$", source_identity),
        )
        row_index_1based = first(
            row.get("row_index_1based"),
            row.get("row_number"),
            row.get("row"),
            regex(r"\bcell=[A-Z]{1,3}(\d+)\b", display_text),
            regex(r":[A-Z]{1,3}(\d+)$", source_identity),
        )
        target_column = first(row.get("target_column"), regex(r"\btarget_column=([^|]+)", display_text))
        display_value = first(
            row.get("display_value"),
            row.get("displayValue"),
            self._source_owned_display_value_from_text(row, target_column),
        )
        structural = {
            "workbook_id": first(row.get("workbook_id"), row.get("workbookId")),
            "workbook_version_id": first(row.get("workbook_version_id"), row.get("workbookVersionId")),
            "sheet": first(row.get("sheet"), row.get("sheet_name"), regex(r"\bsheet=([^|]+)", display_text)),
            "cell_range": first(row.get("cell_range"), row.get("range"), regex(r"\brange=([^|]+)", display_text)),
            "cell": first(row.get("cell"), regex(r"\bcell=([A-Z]{1,3}\d+)\b", display_text)),
            "row_index_1based": row_index_1based,
            "row_label": first(row.get("row_label"), regex(r"\brow_label=([^|]+)", display_text)),
            "column_label": first(row.get("column_label"), regex(r"\bcolumn_label=([^|]+)", display_text)),
            "target_column": target_column,
            "display_value": display_value,
            "header": first(row.get("header"), regex(r"\bheader=([^|]+)", display_text)),
            "header_path": first(row.get("header_path"), regex(r"\bheader_path=([^|]+)", display_text)),
            "table_id": first(row.get("table_id"), regex(r"\btable_id=([^|]+)", display_text)),
            "page_number": page_number,
            "physical_page_index": first(row.get("physical_page_index"), regex(r"\bphysical_page_index=([^|]+)", display_text)),
            "block_index": first(row.get("block_index"), regex(r"\bblock_index=([^|]+)", display_text)),
            "bbox": bbox,
            "region_type": first(row.get("region_type"), regex(r"\bregion_type=([^|]+)", display_text)),
            "section_title": first(row.get("section_title"), regex(r"\bsection_title=([^|]+)", display_text)),
            "table_caption": first(row.get("table_caption"), regex(r"\btable_caption=([^|]+)", display_text)),
            "locator_fingerprint": first(row.get("locator_fingerprint")),
            "parent_source_unit_id": first(row.get("parent_source_unit_id"), row.get("parent_search_unit_id")),
        }
        return {key: value for key, value in structural.items() if value}

    def _synthesize_xlsx_row_value_bundle_units(self, units: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        bundles: list[dict[str, Any]] = []
        seen: set[str] = set()
        same_row_date_aliases: dict[tuple[str, ...], list[str]] = {}
        same_row_date_alias_source_ids: dict[tuple[str, ...], list[str]] = {}

        def same_row_key(unit: Mapping[str, Any], metadata: Mapping[str, Any]) -> tuple[str, ...]:
            return (
                _clean(unit.get("doc_id")),
                _clean(metadata.get("sheet")),
                _clean(metadata.get("cell_range")),
                _clean(metadata.get("row_index_1based")),
                _clean(metadata.get("row_label")),
            )

        def add_alias(row_key: tuple[str, ...], alias: str, source_atom_id: str) -> None:
            clean_alias = _clean(alias)
            if not clean_alias or not all(row_key[:3]) or not (row_key[3] or row_key[4]):
                return
            aliases = same_row_date_aliases.setdefault(row_key, [])
            if clean_alias not in aliases:
                aliases.append(clean_alias)
            source_ids = same_row_date_alias_source_ids.setdefault(row_key, [])
            if source_atom_id and source_atom_id not in source_ids:
                source_ids.append(source_atom_id)

        for unit in units:
            if _clean(unit.get("source_family")).upper() != "XLSX":
                continue
            metadata = unit.get("metadata") if isinstance(unit.get("metadata"), Mapping) else {}
            row_key = same_row_key(unit, metadata)
            source_atom_id = _clean(unit.get("source_atom_id"))
            source_text = _strip_xlsx_locator_forbidden_text_segments(
                _clean(unit.get("text") or unit.get("bm25_text") or unit.get("embedding_text"))
            )
            for alias in _xlsx_locator_date_aliases(source_text):
                add_alias(row_key, alias, source_atom_id)
        for unit in units:
            if _clean(unit.get("source_family")).upper() != "XLSX":
                continue
            metadata = dict(unit.get("metadata") if isinstance(unit.get("metadata"), Mapping) else {})
            target_column = _clean(metadata.get("target_column"))
            display_value = _clean(metadata.get("display_value"))
            row_label = _clean(metadata.get("row_label"))
            row_index = _clean(metadata.get("row_index_1based"))
            sheet = _clean(metadata.get("sheet"))
            cell_range = _clean(metadata.get("cell_range"))
            doc_id = _clean(unit.get("doc_id"))
            source_atom_id = _clean(unit.get("source_atom_id"))
            if not (doc_id and source_atom_id and target_column and display_value and (row_label or row_index)):
                continue
            basis = json.dumps(
                {
                    "doc_id": doc_id,
                    "sheet": sheet,
                    "cell_range": cell_range,
                    "row_index_1based": row_index,
                    "row_label": row_label,
                    "target_column": target_column,
                    "display_value": display_value,
                    "source_atom_id": source_atom_id,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            digest = _sha256_text(basis)[:24]
            if digest in seen:
                continue
            seen.add(digest)
            bundle_id = f"srcatom_xlsx_row_value_bundle_{digest}"
            row_key = same_row_key(unit, metadata)
            source_date_aliases = list(
                dict.fromkeys(
                    [
                        *_xlsx_locator_date_aliases(
                            _strip_xlsx_locator_forbidden_text_segments(
                                _clean(unit.get("text") or unit.get("bm25_text") or unit.get("embedding_text"))
                            )
                        ),
                        *same_row_date_aliases.get(row_key, []),
                    ]
                )
            )
            text_parts = [
                f"{key}={value}"
                for key, value in (
                    ("sheet", sheet),
                    ("range", cell_range),
                    ("row_index_1based", row_index),
                    ("row_label", row_label),
                    ("column_label", _clean(metadata.get("column_label"))),
                    ("target_column", target_column),
                    ("display_value", display_value),
                    ("header_path", _clean(metadata.get("header_path"))),
                    ("table_id", _clean(metadata.get("table_id"))),
                )
                if value
            ]
            text_parts.extend(f"source_date_alias={alias}" for alias in source_date_aliases)
            bundle_metadata = {
                key: value
                for key, value in metadata.items()
                if key
                in {
                    "sheet",
                    "cell_range",
                    "cell",
                    "row_index_1based",
                    "row_label",
                    "column_label",
                    "target_column",
                    "header",
                    "header_path",
                    "table_id",
                    "display_value",
                    "source_text_sha256",
                }
            }
            if source_date_aliases:
                bundle_metadata["source_date_aliases"] = source_date_aliases
            bundle_metadata.update(
                {
                    "candidate_surface_materialization": "xlsx_row_value_bundle_v1",
                    "candidate_surface_materialization_policy": (
                        "source_owned_manifest_snapshot_no_gold_qrels_labels_or_normalized_fields_v1"
                    ),
                    "source_atom_ids": list(
                        dict.fromkeys([source_atom_id, *same_row_date_alias_source_ids.get(row_key, [])])
                    ),
                    "source_registry_mutated": False,
                    "raw_local_paths_exposed": False,
                }
            )
            text = " | ".join(text_parts)
            bundles.append(
                {
                    "unit_id": bundle_id,
                    "source_atom_id": bundle_id,
                    "evidence_bundle_id": f"bundle_{bundle_id}",
                    "doc_id": doc_id,
                    "chunk_id": bundle_id,
                    "source_family": "XLSX",
                    "granularity": "table_row",
                    "retrieval_route": "xlsx_table",
                    "title": "",
                    "section": "xlsx_row_value_bundle",
                    "text": text,
                    "metadata": bundle_metadata,
                    "surface": "source_atom",
                    "text_sha256": _sha256_text(text),
                    "faiss_row_id": None,
                }
            )
        return bundles


def _unit_to_payload(unit: Mapping[str, Any]) -> dict[str, Any]:
    _require_no_source_native_forbidden_fields(unit, context="source-native retrieval unit")
    _require_no_source_native_forbidden_candidate_text(_clean(unit.get("text")), context="source-native retrieval unit text")
    metadata = dict(unit.get("metadata") if isinstance(unit.get("metadata"), Mapping) else {})
    metadata.update(
        {
            "source_safe_id": _clean(unit.get("doc_id")),
            "source_text_sha256": _clean(unit.get("text_sha256")),
            "source_atom_id": _clean(unit.get("source_atom_id")),
            "evidence_bundle_id": _clean(unit.get("evidence_bundle_id")),
            "retrieval_surface": _clean(unit.get("surface")) or "source_native",
            "title": _clean(unit.get("title")),
            "section": _clean(unit.get("section")),
        }
    )
    return {
        "payload_id": _clean(unit.get("unit_id")),
        "search_unit_id": _clean(unit.get("chunk_id") or unit.get("unit_id")),
        "search_view_id": _clean(unit.get("unit_id")),
        "source_family": _clean(unit.get("source_family")),
        "embedding_text": _clean(unit.get("text")),
        "bm25_text": _clean(unit.get("text")),
        "metadata": metadata,
        "source_atom_id": _clean(unit.get("source_atom_id")),
        "evidence_bundle_id": _clean(unit.get("evidence_bundle_id")),
        "retrieval_surface": _clean(unit.get("surface")) or "source_native",
        "title": _clean(unit.get("title")),
        "section": _clean(unit.get("section")),
        "faiss_row_id": unit.get("faiss_row_id"),
    }


def build_source_native_bge_m3_index_artifact(
    *,
    index_dir: Path | str = SOURCE_NATIVE_BGE_M3_INDEX_DIR,
    loader: SourceNativeCorpusLoader | None = None,
    embedding_provider: Any | None = None,
    force: bool = False,
    gpu_preflight: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a persisted non-production source-native BGE-M3 FAISS index."""

    target = Path(index_dir)
    build_path = target / "build.json"
    index_path = target / "faiss.index"
    manifest_path = target / "search_view_manifest.jsonl"
    if not force and _source_native_index_has_bge_m3_artifacts(target):
        existing = json.loads(build_path.read_text(encoding="utf-8"))
        if isinstance(existing, Mapping):
            return dict(existing)
    source_loader = loader or SourceNativeCorpusLoader(
        search_view_manifest_path=SOURCE_NATIVE_DIAGNOSTIC_INDEX_DIR / "search_view_manifest.jsonl",
        source_atom_registry_path=SOURCE_NATIVE_SOURCE_REGISTRY_PATH,
    )
    units = source_loader.load_units()
    if not units:
        raise DatasetSchemaError("source-native BGE-M3 index build requires at least one source-native unit")
    payloads = [_unit_to_payload(unit) for unit in units]
    texts = [_clean(payload.get("embedding_text") or payload.get("bm25_text")) for payload in payloads]
    text_hashes = [_sha256_text(text) for text in texts]
    try:
        import numpy as np  # type: ignore
        import faiss  # type: ignore
    except Exception as exc:
        raise DatasetSchemaError(f"source-native BGE-M3 index build requires numpy/faiss: {type(exc).__name__}: {exc}") from exc
    embedder = embedding_provider
    if embedder is None:
        from app.capabilities.rag.embeddings import SentenceTransformerEmbedder, resolve_max_seq_length

        embedder = SentenceTransformerEmbedder(
            model_name="BAAI/bge-m3",
            max_seq_length=resolve_max_seq_length(
                int(os.environ.get("ACTUAL_RAG_EVAL_BGE_M3_MAX_SEQ_LENGTH", "1024"))
            ),
            batch_size=int(os.environ.get("ACTUAL_RAG_EVAL_BGE_M3_BATCH_SIZE", "32")),
            show_progress_bar=True,
            local_files_only=True,
        )
    started = time.perf_counter()
    vectors = embedder.embed_passages(texts)
    embedding_build_latency_ms = round((time.perf_counter() - started) * 1000, 6)
    vectors = np.ascontiguousarray(vectors, dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[0] != len(payloads) or vectors.shape[1] <= 0:
        raise DatasetSchemaError("source-native BGE-M3 embedding matrix shape is invalid")
    build_started = time.perf_counter()
    index = faiss.IndexFlatIP(int(vectors.shape[1]))
    index.add(vectors)
    index_build_latency_ms = round((time.perf_counter() - build_started) * 1000, 6)
    target.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_path))
    source_manifest = source_loader.search_view_manifest_path
    if not source_manifest.exists():
        raise DatasetSchemaError(f"source-native manifest does not exist: {source_manifest}")
    if source_manifest.resolve() != manifest_path.resolve():
        manifest_path.write_bytes(source_manifest.read_bytes())
    model = getattr(embedder, "_model", None)
    model_device = _clean(getattr(model, "device", ""))
    preflight = dict(gpu_preflight or {})
    embedding_device = model_device or ("cuda:0" if bool(preflight.get("torch_cuda_available")) else "cpu")
    gpu_used = "cuda" in embedding_device.casefold()
    build = {
        "schema_version": "actual_rag_eval.source_native_bge_m3_index_build.v1",
        "index_version": "actual-rag-source-native-bge-m3-nonprod-v1",
        "embedding_model": _clean(getattr(embedder, "model_name", "")) or "BAAI/bge-m3",
        "embedding_model_revision": _clean(getattr(embedder, "model_revision", "")) or "unavailable",
        "dimension": int(vectors.shape[1]),
        "chunk_count": int(vectors.shape[0]),
        "source_native_unit_count": len(payloads),
        "text_hash_count": len(text_hashes),
        "corpus_fingerprint_sha256": f"sha256:{_sha256_text(json.dumps(text_hashes, sort_keys=True))}",
        "faiss_index_ntotal": int(index.ntotal),
        "faiss_index_type": "IndexFlatIP",
        "embedding_device": embedding_device,
        "gpu_used_for_embedding": gpu_used,
        "embedding_build_latency_ms": embedding_build_latency_ms,
        "index_build_latency_ms": index_build_latency_ms,
        "source_manifest_path_sha256": f"sha256:{_sha256_text(source_manifest.as_posix())}",
        "source_manifest_copy_sha256": f"sha256:{_sha256_text(manifest_path.as_posix())}",
        "faiss_row_id_mismatch_count": sum(
            1
            for expected, payload in enumerate(payloads)
            if payload.get("faiss_row_id") is not None and int(payload.get("faiss_row_id")) != expected
        ),
        "diagnostic_only": True,
        "semantic_quality_claim_allowed": False,
        "gold_fields_used_for_index_build": False,
        "expected_fields_used_for_index_build": False,
        "qrels_used_for_index_build": False,
        "labels_used_for_index_build": False,
        "raw_local_paths_exposed": False,
    }
    write_json(build_path, build)
    return build


class SourceNativeHybridAdapter(RepoCurrentHybridAdapter):
    """SourceAtom/EvidenceBundle-backed BM25, vector, and hybrid retrieval."""

    def __init__(
        self,
        root: Path | str = ROOT,
        *,
        requested_backend: str = "auto",
        loader: SourceNativeCorpusLoader | None = None,
        units: Sequence[Mapping[str, Any]] | None = None,
        embedding_provider: Any | None = None,
        gpu_preflight: Mapping[str, Any] | None = None,
        external_vector_db: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            root=root,
            requested_backend=requested_backend,
            embedding_provider=embedding_provider,
            gpu_preflight=gpu_preflight,
            external_vector_db=external_vector_db,
        )
        self.loader = loader or SourceNativeCorpusLoader()
        self._provided_units = [dict(unit) for unit in units] if units is not None else None
        self._bm25_cache: tuple[list[list[str]], Counter[str], float] | None = None
        self._existing_vector_index = None
        self._existing_vector_mode = False
        self._persisted_bge_m3_vector_mode = False
        self._python_vector_mode = False
        self._python_vector_matrix = None

    @property
    def config(self) -> dict[str, Any]:
        return {
            "adapter": "source_native_sourceatom_hybrid",
            "surface": "source_native",
            "source_native_loader": self.loader.describe(),
            "requested_backend": self.requested_backend,
            "selected_backend": self._selected_backend_name(),
            "candidate_generation_input_policy": "query_text_only_over_source_owned_corpus",
            "searchunit_searchview_role": "legacy_comparison_debug_only",
            "external_api_calls": False,
        }

    def _load_payloads(self) -> list[dict[str, Any]]:
        if self._payloads is not None:
            return self._payloads
        units = self._provided_units if self._provided_units is not None else self.loader.load_units()
        self._payloads = [_unit_to_payload(unit) for unit in units]
        return self._payloads

    @property
    def retrieval_backend_report(self) -> dict[str, Any]:
        report = super().retrieval_backend_report
        if self._vector_ready and not self._gpu_used_for_embedding and self._vector_fallback_reason:
            report["fallback_reason"] = self._vector_fallback_reason
        if self._python_vector_mode:
            report["vector_index_kind"] = "python_deterministic_test"
            report["vector_index_type"] = "in_memory_dot_product"
        if self._persisted_bge_m3_vector_mode:
            report["vector_index_kind"] = "faiss"
            report["vector_index_type"] = "IndexFlatIP"
        report.update(
            {
                "retrieval_surface": "source_native",
                "source_native_corpus_available": bool(self._load_payloads()),
                "source_native_loader": self.loader.describe(),
                "gpu_fallback_reason": self._vector_fallback_reason if not self._gpu_used_for_embedding else "",
            }
        )
        return report

    @property
    def backend_diagnostics(self) -> dict[str, Any]:
        diagnostics = dict(super().backend_diagnostics)
        if self._vector_ready and not self._gpu_used_for_embedding and self._vector_fallback_reason:
            diagnostics["fallback_reason"] = self._vector_fallback_reason
        return diagnostics

    @property
    def vector_index_audit_report(self) -> dict[str, Any]:
        if self.requested_backend != "bm25":
            self._ensure_vector_ready()
        payloads = self._load_payloads()
        id_map = list(self._vector_id_map)
        id_keys = [_clean(payload.get("search_unit_id")) for payload in id_map]
        duplicate_vector_id_count = len(id_keys) - len(set(key for key in id_keys if key))
        texts = [_clean(payload.get("bm25_text") or payload.get("embedding_text")) for payload in payloads]
        text_hashes = [_sha256_text(text) for text in texts]
        metadata_rows = [
            payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
            for payload in payloads
        ]
        index_path = self.loader.search_view_manifest_path.parent / "faiss.index"
        vector_index_kind = (
            "python_deterministic_test"
            if self._python_vector_mode
            else "faiss"
            if self._vector_ready
            else "unavailable"
        )
        build_path = self.loader.search_view_manifest_path.parent / "build.json"
        build: dict[str, Any] = {}
        provided_units_mode = self._provided_units is not None
        if build_path.exists() and not provided_units_mode:
            try:
                loaded_build = json.loads(build_path.read_text(encoding="utf-8"))
                if isinstance(loaded_build, Mapping):
                    build = dict(loaded_build)
            except Exception:
                build = {}
        faiss_index_ntotal = 0
        if self._python_vector_mode and self._python_vector_matrix is not None:
            faiss_index_ntotal = int(getattr(self._python_vector_matrix, "shape", [0])[0])
        elif self._existing_vector_index is not None:
            faiss_index_ntotal = int(getattr(self._existing_vector_index, "ntotal", 0) or 0)
        elif self._vector_index is not None:
            faiss_index_ntotal = int(getattr(self._vector_index, "ntotal", 0) or 0)
        row_ids: list[int] = []
        for payload in id_map:
            value = payload.get("faiss_row_id")
            if isinstance(value, int):
                row_ids.append(value)
            elif str(value).isdigit():
                row_ids.append(int(str(value)))
        faiss_row_id_available_count = len(row_ids)
        faiss_row_id_sequential_match_count = sum(1 for expected, actual in enumerate(row_ids) if expected == actual)
        faiss_row_id_mismatch_count = (
            faiss_row_id_available_count - faiss_row_id_sequential_match_count
            if faiss_row_id_available_count
            else 0
        )
        faiss_ntotal_matches_id_map = bool(self._vector_ready and faiss_index_ntotal == len(id_map))
        build_chunk_count = int(build.get("chunk_count") or 0)
        build_dim = int(build.get("dimension") or 0)
        build_count_matches = bool(not build_chunk_count or build_chunk_count == len(payloads))
        build_dim_matches = bool(not build_dim or build_dim == int(self._vector_dim))
        index_integrity_passed = (
            bool(self._vector_ready)
            and len(id_map) == len(payloads)
            and duplicate_vector_id_count == 0
            and all(bool(_clean(payload.get("search_unit_id"))) for payload in id_map)
            and faiss_ntotal_matches_id_map
            and build_count_matches
            and build_dim_matches
            and faiss_row_id_mismatch_count == 0
        )
        bge_m3_selected = "bge-m3" in _clean(self._embedding_model).casefold()
        status = (
            "not_connected"
            if not self._vector_ready
            else "connected_bge_m3_candidate"
            if bge_m3_selected and self._gpu_used_for_embedding
            else "connected_semantic_quality_unproven"
        )
        family_distribution = Counter(_clean(payload.get("source_family")) or "unknown" for payload in payloads)
        kind_distribution = Counter(
            _clean(metadata.get("retrieval_surface") or payload.get("retrieval_surface") or "source_native")
            for payload, metadata in zip(payloads, metadata_rows, strict=True)
        )
        return {
            "enabled": True,
            "status": status,
            "vector_surface": "source_native",
            "vector_backend": vector_index_kind,
            "vector_index_available": bool(self._vector_ready),
            "vector_index_kind": vector_index_kind,
            "vector_index_type": "in_memory_dot_product"
            if self._python_vector_mode
            else "IndexFlatIP"
            if self._vector_ready
            else "unavailable",
            "vector_index_path_sha256": f"sha256:{_sha256_text(index_path.as_posix())}" if index_path.exists() and not provided_units_mode else "",
            "vector_index_path_present": index_path.exists() if not self._python_vector_mode and not provided_units_mode else False,
            "build_json_path_sha256": f"sha256:{_sha256_text(build_path.as_posix())}" if build_path.exists() and not provided_units_mode else "",
            "build_json_present": build_path.exists() and not provided_units_mode,
            "build_index_version": _clean(build.get("index_version")),
            "build_schema_version": _clean(build.get("schema_version")),
            "build_chunk_count": build_chunk_count,
            "build_dimension": build_dim,
            "build_embedding_model": _clean(build.get("embedding_model")),
            "build_embedding_model_revision": _clean(build.get("embedding_model_revision")),
            "build_corpus_fingerprint_sha256": _clean(build.get("corpus_fingerprint_sha256")),
            "build_text_hash_count": int(build.get("text_hash_count") or 0),
            "embedding_model_revision": _clean(build.get("embedding_model_revision"))
            or _clean(getattr(self._embedder, "model_revision", ""))
            or "unavailable",
            "corpus_fingerprint_sha256": _clean(build.get("corpus_fingerprint_sha256"))
            or f"sha256:{_sha256_text(json.dumps(text_hashes, sort_keys=True))}",
            "text_hash_count": int(build.get("text_hash_count") or 0) or len(text_hashes),
            "faiss_index_ntotal": faiss_index_ntotal,
            "faiss_ntotal_matches_id_map": faiss_ntotal_matches_id_map,
            "embedding_model": _clean(self._embedding_model),
            "embedding_dim": int(self._vector_dim),
            "embedding_device": _clean(self._embedding_device),
            "gpu_used_for_embedding": bool(self._gpu_used_for_embedding),
            "bge_m3_replacement_needed": not (bge_m3_selected and self._gpu_used_for_embedding),
            "indexed_unit_count": len(id_map),
            "id_map_count": len(id_map),
            "source_native_unit_count": len(payloads),
            "id_map_matches_source_native_units": len(id_map) == len(payloads) if self._vector_ready else False,
            "missing_id_map_count": max(len(payloads) - len(id_map), 0) if self._vector_ready else len(payloads),
            "duplicate_vector_id_count": duplicate_vector_id_count,
            "faiss_row_id_available_count": faiss_row_id_available_count,
            "faiss_row_id_sequential_match_count": faiss_row_id_sequential_match_count,
            "faiss_row_id_mismatch_count": faiss_row_id_mismatch_count,
            "empty_text_unit_count": sum(1 for text in texts if not text),
            "too_short_text_unit_count": sum(1 for text in texts if 0 < len(text) < 12),
            "too_long_text_unit_count": sum(1 for text in texts if len(text) > 8000),
            "text_hash_available_count": sum(1 for metadata in metadata_rows if _clean(metadata.get("source_text_sha256"))),
            "doc_id_available_count": sum(1 for metadata, payload in zip(metadata_rows, payloads, strict=True) if _clean(metadata.get("source_safe_id") or payload.get("source_family"))),
            "chunk_id_available_count": sum(1 for payload in payloads if _clean(payload.get("search_unit_id"))),
            "source_anchor_available_count": sum(
                1
                for metadata, payload in zip(metadata_rows, payloads, strict=True)
                if _clean(payload.get("source_atom_id") or metadata.get("source_atom_id") or payload.get("evidence_bundle_id") or metadata.get("evidence_bundle_id"))
            ),
            "source_family_distribution": dict(sorted(family_distribution.items())),
            "source_kind_distribution": dict(sorted(kind_distribution.items())),
            "raw_local_paths_exposed": False,
            "index_integrity_passed": index_integrity_passed,
            "semantic_quality_claim_allowed": False,
            "limitations": [
                "diagnostic hash vectors do not prove semantic retrieval quality"
                if not bge_m3_selected
                else "BGE-M3 semantic quality still requires evaluation before official claims",
                "external VectorDB parity is not configured",
                "expected fields are diagnostics-only after retrieval",
            ],
        }

    def _source_native_vector_invocation_diagnostics(
        self,
        *,
        vector_contexts: Sequence[Mapping[str, Any]],
        vector_latency_ms: float,
    ) -> dict[str, Any]:
        vector_invoked = self.requested_backend != "bm25"
        hydrated = [
            row
            for row in vector_contexts
            if _clean(row.get("doc_id"))
            and _clean(row.get("chunk_id"))
            and _clean(row.get("retrieval_surface")) == "source_native"
        ]
        return {
            "vector_backend_invoked": bool(vector_invoked),
            "query_embedding_created_or_loaded": bool(vector_invoked and self._vector_ready),
            "query_embedding_model": _clean(self._embedding_model),
            "query_embedding_dim": int(self._vector_dim),
            "vector_top_k_count": len(vector_contexts),
            "vector_latency_ms": round(float(vector_latency_ms), 6),
            "vector_candidate_doc_ids": [_clean(row.get("doc_id")) for row in vector_contexts],
            "vector_candidate_chunk_ids": [_clean(row.get("chunk_id")) for row in vector_contexts],
            "vector_candidate_scores": [round(float(row.get("score") or 0.0), 6) for row in vector_contexts],
            "vector_candidate_text_hashes": [_sha256_text(row.get("text")) for row in vector_contexts],
            "vector_candidate_text_previews": [_redact_absolute_local_paths(_clean(row.get("text"))[:240]) for row in vector_contexts],
            "vector_hydration_success_count": len(hydrated),
            "vector_hydration_failure_count": max(len(vector_contexts) - len(hydrated), 0),
            "vector_candidate_generation_input_policy": "query_text_only_no_gold_qrels_labels_ids_or_baseline_topk",
        }

    def _ensure_vector_ready(self) -> bool:
        if self._vector_attempted:
            return self._vector_ready
        self._vector_attempted = True
        payloads = self._load_payloads()
        if not payloads:
            self._vector_fallback_reason = "source_native_corpus_unavailable"
            return False
        try:
            import numpy as np  # type: ignore
            import faiss  # type: ignore
        except Exception as exc:
            self._vector_fallback_reason = f"faiss_or_numpy_unavailable:{type(exc).__name__}: {exc}"
            return False

        index_dir = self.loader.search_view_manifest_path.parent
        build_path = index_dir / "build.json"
        index_path = index_dir / "faiss.index"
        if self._provided_units is None and build_path.exists() and index_path.exists():
            try:
                build = json.loads(build_path.read_text(encoding="utf-8"))
                build_model = _clean(build.get("embedding_model"))
                if "bge-m3" in build_model.casefold():
                    started = time.perf_counter()
                    self._existing_vector_index = faiss.read_index(str(index_path))
                    self._index_load_or_build_latency_ms = round((time.perf_counter() - started) * 1000, 6)
                    embedder = self.embedding_provider
                    if embedder is None:
                        from app.capabilities.rag.embeddings import SentenceTransformerEmbedder, resolve_max_seq_length

                        embedder = SentenceTransformerEmbedder(
                            model_name=build_model or "BAAI/bge-m3",
                            max_seq_length=resolve_max_seq_length(
                                int(os.environ.get("ACTUAL_RAG_EVAL_BGE_M3_MAX_SEQ_LENGTH", "1024"))
                            ),
                            batch_size=int(os.environ.get("ACTUAL_RAG_EVAL_BGE_M3_BATCH_SIZE", "32")),
                            show_progress_bar=False,
                            local_files_only=True,
                        )
                    self._vector_id_map = payloads
                    self._embedder = embedder
                    self._vector_dim = int(build.get("dimension") or getattr(embedder, "dimension", 1024) or 1024)
                    self._embedding_model = build_model or _clean(getattr(embedder, "model_name", "")) or "BAAI/bge-m3"
                    self._embedding_device = _clean(build.get("embedding_device")) or (
                        "cuda:0" if bool(self.gpu_preflight.get("torch_cuda_available")) else "cpu"
                    )
                    self._gpu_used_for_embedding = bool(build.get("gpu_used_for_embedding")) or "cuda" in self._embedding_device.casefold()
                    self._persisted_bge_m3_vector_mode = True
                    self._existing_vector_mode = False
                    self._vector_ready = True
                    self._vector_fallback_reason = ""
                    return True
                if build_model == "codex-diagnostic-hashing-vector-v1":
                    started = time.perf_counter()
                    self._existing_vector_index = faiss.read_index(str(index_path))
                    self._index_load_or_build_latency_ms = round((time.perf_counter() - started) * 1000, 6)
                    self._vector_id_map = payloads
                    self._vector_dim = int(build.get("dimension") or 128)
                    self._embedding_model = "codex-diagnostic-hashing-vector-v1"
                    self._embedding_device = "cpu_existing_nonprod_index"
                    self._gpu_used_for_embedding = False
                    self._existing_vector_mode = True
                    self._vector_ready = True
                    self._vector_fallback_reason = "existing_source_native_index_uses_diagnostic_hash_vectors_not_gpu_bge_m3"
                    return True
            except Exception as exc:
                self._vector_fallback_reason = f"existing_source_native_index_load_failed:{type(exc).__name__}: {exc}"

        try:
            embedder = self.embedding_provider
            if embedder is None:
                from app.capabilities.rag.embeddings import SentenceTransformerEmbedder, resolve_max_seq_length

                embedder = SentenceTransformerEmbedder(
                    model_name="BAAI/bge-m3",
                    max_seq_length=resolve_max_seq_length(
                        int(os.environ.get("ACTUAL_RAG_EVAL_BGE_M3_MAX_SEQ_LENGTH", "1024"))
                    ),
                    batch_size=int(os.environ.get("ACTUAL_RAG_EVAL_BGE_M3_BATCH_SIZE", "32")),
                    show_progress_bar=False,
                    local_files_only=True,
                )
            texts = [_clean(payload.get("embedding_text") or payload.get("bm25_text")) for payload in payloads]
            embed_started = time.perf_counter()
            vectors = embedder.embed_passages(texts)
            self._embedding_build_latency_ms = round((time.perf_counter() - embed_started) * 1000, 6)
            vectors = np.ascontiguousarray(vectors, dtype=np.float32)
            if getattr(embedder, "python_only_vector_search", False):
                self._index_load_or_build_latency_ms = 0.0
                self._python_vector_mode = True
                self._python_vector_matrix = vectors
                self._vector_id_map = payloads
                self._embedder = embedder
                self._vector_dim = int(vectors.shape[1])
                self._embedding_model = _clean(getattr(embedder, "model_name", "")) or "python-only-vector-test-adapter"
                self._embedding_device = "cpu_python_test_adapter"
                self._gpu_used_for_embedding = False
                self._vector_ready = True
                self._vector_fallback_reason = "python_only_deterministic_test_vector_adapter"
                return True
            build_started = time.perf_counter()
            index = faiss.IndexFlatIP(int(vectors.shape[1]))
            index.add(vectors)
            self._index_load_or_build_latency_ms = round((time.perf_counter() - build_started) * 1000, 6)
            self._vector_index = index
            self._vector_id_map = payloads
            self._embedder = embedder
            self._vector_dim = int(vectors.shape[1])
            self._embedding_model = _clean(getattr(embedder, "model_name", "")) or "BAAI/bge-m3"
            model = getattr(embedder, "_model", None)
            model_device = _clean(getattr(model, "device", ""))
            cuda_available = bool(self.gpu_preflight.get("torch_cuda_available"))
            self._embedding_device = model_device or ("cuda:0" if cuda_available else "cpu")
            self._gpu_used_for_embedding = "cuda" in self._embedding_device.lower()
            self._vector_ready = True
            self._vector_fallback_reason = "" if self._gpu_used_for_embedding else "gpu_not_used_for_source_native_embedding"
        except Exception as exc:
            self._vector_ready = False
            self._vector_fallback_reason = f"source_native_vector_build_failed:{type(exc).__name__}: {exc}"
        return self._vector_ready

    def _vector_contexts(self, query: str, *, top_k: int) -> tuple[list[dict[str, Any]], float]:
        if not _clean(query) or not self._ensure_vector_ready():
            return [], 0.0
        try:
            import numpy as np  # type: ignore
        except Exception:
            return [], 0.0
        started = time.perf_counter()
        try:
            if self._python_vector_mode and self._python_vector_matrix is not None:
                if self._embedder is None:
                    raise RuntimeError("source_native_python_vector_embedder_not_loaded")
                query_vectors = self._embedder.embed_queries([query])
                qvec = np.ascontiguousarray(query_vectors, dtype=np.float32)
                if qvec.ndim != 2 or qvec.shape[1] != self._vector_dim:
                    raise RuntimeError("source_native_python_vector_query_dim_mismatch")
                scores_matrix = self._python_vector_matrix @ qvec[0]
                order = np.argsort(-scores_matrix)[: min(int(top_k), len(self._vector_id_map))]
                row_ids = [int(row_id) for row_id in order]
                score_values = [float(scores_matrix[row_id]) for row_id in row_ids]
            elif self._persisted_bge_m3_vector_mode and self._existing_vector_index is not None:
                if self._embedder is None:
                    raise RuntimeError("source_native_bge_m3_query_embedder_not_loaded")
                query_vectors = self._embedder.embed_queries([query])
                qvec = np.ascontiguousarray(query_vectors, dtype=np.float32)
                scores, ids = self._existing_vector_index.search(qvec, min(int(top_k), len(self._vector_id_map)))
                row_ids = [int(row_id) for row_id in ids[0]]
                score_values = [float(score) for score in scores[0]]
            elif self._existing_vector_mode and self._existing_vector_index is not None:
                qvec = _diagnostic_hash_vectors([query], dimension=max(self._vector_dim, 1))
                scores, ids = self._existing_vector_index.search(qvec, min(int(top_k), len(self._vector_id_map)))
                row_ids = [int(row_id) for row_id in ids[0]]
                score_values = [float(score) for score in scores[0]]
            else:
                if self._embedder is None or self._vector_index is None:
                    raise RuntimeError("source_native_vector_index_not_loaded")
                query_vectors = self._embedder.embed_queries([query])
                qvec = np.ascontiguousarray(query_vectors, dtype=np.float32)
                scores, ids = self._vector_index.search(qvec, min(int(top_k), len(self._vector_id_map)))
                row_ids = [int(row_id) for row_id in ids[0]]
                score_values = [float(score) for score in scores[0]]
        except Exception as exc:
            self._vector_fallback_reason = f"source_native_vector_query_failed:{type(exc).__name__}: {exc}"
            return [], round((time.perf_counter() - started) * 1000, 6)
        contexts = [
            self._context_from_payload(self._vector_id_map[row_id], rank, score, "vector")
            for rank, (row_id, score) in enumerate(zip(row_ids, score_values), start=1)
            if row_id >= 0
        ]
        self._query_count += 1
        return contexts, round((time.perf_counter() - started) * 1000, 6)

    def _bm25_contexts(self, query: str, payloads: Sequence[Mapping[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
        query_terms = self._tokenize(query)
        if not query_terms:
            return []
        docs, doc_freq, avg_len = self._bm25_stats(payloads)
        doc_count = max(len(docs), 1)
        scored: list[tuple[float, int, Mapping[str, Any]]] = []
        for index, (payload, doc_terms) in enumerate(zip(payloads, docs, strict=True)):
            term_counts = Counter(doc_terms)
            doc_len = max(len(doc_terms), 1)
            score = 0.0
            for term in query_terms:
                if not term_counts[term]:
                    continue
                idf = math.log(1 + (doc_count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                score += idf * (term_counts[term] * 2.2) / (
                    term_counts[term] + 1.2 * (0.25 + 0.75 * doc_len / max(avg_len, 1e-9))
                )
            if score > 0:
                scored.append((score, index, payload))
        scored.sort(key=lambda item: (-item[0], _clean(item[2].get("search_unit_id"))))
        return [self._context_from_payload(payload, rank, score, "bm25") for rank, (score, _index, payload) in enumerate(scored[:top_k], start=1)]

    def _bm25_stats(self, payloads: Sequence[Mapping[str, Any]]) -> tuple[list[list[str]], Counter[str], float]:
        if self._bm25_cache is not None:
            return self._bm25_cache
        docs = [self._tokenize(_clean(payload.get("bm25_text") or payload.get("embedding_text"))) for payload in payloads]
        doc_count = max(len(docs), 1)
        doc_freq = Counter(term for doc in docs for term in set(doc))
        avg_len = sum(len(doc) for doc in docs) / doc_count if docs else 1.0
        self._bm25_cache = (docs, doc_freq, avg_len)
        return self._bm25_cache

    def _context_from_payload(self, payload: Mapping[str, Any], rank: int, score: float, backend: str) -> dict[str, Any]:
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
        return {
            "rank": rank,
            "doc_id": _clean(metadata.get("source_safe_id") or payload.get("source_family")),
            "chunk_id": _clean(payload.get("search_unit_id")),
            "score": round(float(score), 6),
            "text": _clean(payload.get("bm25_text") or payload.get("embedding_text")),
            "retrieval_backend": backend,
            "retrieval_surface": "source_native",
            "source_family": _clean(payload.get("source_family")),
            "source_atom_id": _clean(payload.get("source_atom_id") or metadata.get("source_atom_id")),
            "evidence_bundle_id": _clean(payload.get("evidence_bundle_id") or metadata.get("evidence_bundle_id")),
            "title": _clean(payload.get("title") or metadata.get("title")),
            "section": _clean(payload.get("section") or metadata.get("section")),
            "source_text_sha256": _clean(metadata.get("source_text_sha256")),
        }

    def full_corpus_evidence_candidates(
        self,
        item: EvalItem,
        evidence: ExpectedEvidence,
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        evidence_text = _clean(evidence.text)
        normalized_evidence = normalize_answer_text(evidence_text)
        anchors = _evidence_resolution_anchors(item, evidence)
        required_numeric = _numeric_or_date_anchors(
            _candidate_anchors(item.expected_answer, *item.expected_answer_aliases, evidence.text)
        )
        rows: list[dict[str, Any]] = []
        for payload in self._load_payloads():
            context = self._context_from_payload(payload, 0, 0.0, "full_corpus_diagnostic")
            text = _clean(context.get("text"))
            normalized_text = normalize_answer_text(text)
            exact_text = bool(evidence_text and evidence_text in text)
            normalized_match = bool(normalized_evidence and normalized_evidence in normalized_text)
            anchor_hits = sorted(anchor for anchor in anchors if _anchor_in_text([anchor], text))
            missing_numeric = sorted(anchor for anchor in required_numeric if not _anchor_in_text([anchor], text))
            overlap = _token_overlap_ratio(evidence_text, text)
            if not exact_text and not normalized_match and not anchor_hits and overlap < 0.2:
                continue
            if exact_text:
                score = 0.98
            elif normalized_match:
                score = 0.92
            elif anchor_hits and not missing_numeric:
                score = 0.65 + min(len(anchor_hits), 4) * 0.03
            else:
                score = max(0.25, overlap)
            context.update(
                {
                    "rank": 0,
                    "score": round(float(score), 6),
                    "retrieval_backend": "full_corpus_diagnostic",
                    "_resolution_source": "full_corpus_source_native",
                    "full_corpus_review_only": True,
                    "expected_evidence_used_for_candidate_generation": False,
                    "expected_evidence_used_for_review_only_resolution": True,
                    "gold_or_qrels_mutation": False,
                }
            )
            rows.append(context)
        rows.sort(
            key=lambda row: (
                -float(row.get("score") or 0.0),
                _clean(row.get("doc_id")),
                _clean(row.get("chunk_id")),
                _sha256_text(row.get("text")),
            )
        )
        bounded = rows[: max(1, int(top_k))]
        for rank, row in enumerate(bounded, start=1):
            row["rank"] = rank
        return bounded

    def run_item(self, item: EvalItem, *, top_k: int) -> dict[str, Any]:
        payloads = self._load_payloads()
        bm25_started = time.perf_counter()
        bm25_contexts = self._bm25_contexts(item.query, payloads, top_k=top_k)
        bm25_latency = round((time.perf_counter() - bm25_started) * 1000, 6)
        if self.requested_backend == "bm25":
            vector_contexts: list[dict[str, Any]] = []
            vector_latency = 0.0
            hybrid_contexts: list[dict[str, Any]] = []
            hybrid_latency = 0.0
            if not self._vector_fallback_reason:
                self._vector_fallback_reason = "vector_backend_not_requested_for_bm25_surface"
        else:
            vector_contexts, vector_latency = self._vector_contexts(item.query, top_k=top_k)
            hybrid_started = time.perf_counter()
            hybrid_contexts = fuse_hybrid_contexts(bm25_contexts, vector_contexts, top_k=top_k)
            hybrid_latency = round((time.perf_counter() - hybrid_started) * 1000, 6) + bm25_latency + vector_latency
        selected_backend = self._selected_backend_name()
        fallback_selected_contexts = {
            "bm25": bm25_contexts,
            "vector": vector_contexts,
            "hybrid": hybrid_contexts,
        }.get(selected_backend, bm25_contexts)
        layered_contexts, layered_report = self._source_native_layered_contexts(
            item.query,
            top_k=top_k,
            selected_backend=selected_backend,
            payloads=payloads,
            bm25_contexts=bm25_contexts,
            vector_contexts=vector_contexts,
            bm25_latency_ms=bm25_latency,
            vector_latency_ms=vector_latency,
        )
        selected_contexts = layered_contexts or fallback_selected_contexts
        citations = [_normalize_citation(context) for context in selected_contexts]
        generated_answer = self.generator.generate(item.query, [_context_to_chunk(context) for context in selected_contexts])
        output = _item_output(item, generated_answer=generated_answer, contexts=selected_contexts, citations=citations)
        output["retrieval_backend_comparison"] = _retrieval_backend_comparison(
            requested_backend=self.requested_backend,
            selected_backend=selected_backend,
            bm25_contexts=bm25_contexts,
            vector_contexts=vector_contexts,
            hybrid_contexts=hybrid_contexts,
            selected_contexts=selected_contexts,
            bm25_latency_ms=bm25_latency,
            vector_latency_ms=vector_latency,
            hybrid_latency_ms=hybrid_latency,
            vector_available=self._vector_ready,
            vector_fallback_reason=self._vector_fallback_reason,
        )
        output["retrieval_backend_comparison"]["source_native_vector_invocation"] = self._source_native_vector_invocation_diagnostics(
            vector_contexts=vector_contexts,
            vector_latency_ms=vector_latency,
        )
        output["retrieval_backend_comparison"]["post_retrieval_target_diagnostics"] = {
            "expected_fields_used_for_post_retrieval_diagnostics": item.has_expected_answer or item.has_expected_evidence,
            "expected_fields_used_for_candidate_generation": False,
            "gold_fields_used_for_candidate_generation": False,
            "qrels_used_for_candidate_generation": False,
            "ids_used_for_candidate_generation": False,
            "baseline_topk_used_for_candidate_generation": False,
            "bm25_expected_anchor_retrieved": _contexts_match_expected(item, bm25_contexts),
            "vector_expected_anchor_retrieved": _contexts_match_expected(item, vector_contexts),
            "hybrid_expected_anchor_retrieved": _contexts_match_expected(item, hybrid_contexts),
        }
        output["source_native_layered_retrieval"] = layered_report
        output["diagnostic_retrieval_metrics"] = _source_native_diagnostic_retrieval_metrics_for_item(
            item,
            bm25_contexts=bm25_contexts,
            vector_contexts=vector_contexts,
            hybrid_contexts=hybrid_contexts,
            selected_contexts=selected_contexts,
            top_k=top_k,
        )
        output["diagnostics"]["retrieval_backend_comparison"] = output["retrieval_backend_comparison"]
        output["diagnostics"]["source_native_layered_retrieval"] = layered_report
        output["diagnostics"]["diagnostic_retrieval_metrics"] = output["diagnostic_retrieval_metrics"]
        return output

    def _source_native_layered_contexts(
        self,
        query: str,
        *,
        top_k: int,
        selected_backend: str,
        payloads: Sequence[Mapping[str, Any]],
        bm25_contexts: Sequence[Mapping[str, Any]],
        vector_contexts: Sequence[Mapping[str, Any]],
        bm25_latency_ms: float,
        vector_latency_ms: float,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        bounds = dict(SOURCE_NATIVE_LAYERED_RETRIEVAL_BOUNDS)
        layer_limit = min(int(bounds["max_candidates_per_layer"]), max(int(top_k) * 5, int(top_k), 1))
        max_backend_calls = int(bounds["max_backend_calls_per_item"])
        variants = _bounded_source_native_query_variants(query)
        anchors = _source_native_query_anchor_sets(query)
        per_layer_candidate_counts = {layer: 0 for layer in SOURCE_NATIVE_LAYERED_RETRIEVAL_LAYERS}
        per_layer_latency_ms = {layer: 0.0 for layer in SOURCE_NATIVE_LAYERED_RETRIEVAL_LAYERS}
        layer_candidates: dict[str, list[dict[str, Any]]] = {
            layer: [] for layer in SOURCE_NATIVE_LAYERED_RETRIEVAL_LAYERS
        }
        backend_call_count = 0

        l0_started = time.perf_counter()
        normalized_query = _source_native_normalized_query(query)
        per_layer_latency_ms["L0_query_normalization"] = round((time.perf_counter() - l0_started) * 1000, 6)
        if not normalized_query:
            report = _empty_source_native_layered_retrieval_report(
                selected_surface="source_native",
                selected_backend=selected_backend,
                fallback_reason="empty_query",
            )
            return [], report

        def record(layer: str, contexts: Sequence[Mapping[str, Any]], *, query_variant: str, backend: str) -> None:
            rows = [
                _annotate_source_native_layer_context(row, layer=layer, query_variant=query_variant, backend=backend)
                for row in contexts[:layer_limit]
            ]
            layer_candidates[layer].extend(rows)
            per_layer_candidate_counts[layer] = min(
                int(bounds["max_candidates_per_layer"]),
                len({_layered_context_key(row) for row in layer_candidates[layer]}),
            )

        lexical_variants = variants[: min(3, len(variants))]
        for variant in lexical_variants:
            if backend_call_count >= max_backend_calls:
                break
            if variant == normalized_query:
                contexts = list(bm25_contexts)[:layer_limit]
                latency = bm25_latency_ms
            else:
                started = time.perf_counter()
                contexts = self._bm25_contexts(variant, payloads, top_k=layer_limit)
                latency = round((time.perf_counter() - started) * 1000, 6)
            backend_call_count += 1
            per_layer_latency_ms["L1_lexical_anchor_search"] += latency
            record("L1_lexical_anchor_search", contexts, query_variant=variant, backend="bm25")

        if self.requested_backend != "bm25" and backend_call_count < max_backend_calls:
            backend_call_count += 1
            per_layer_latency_ms["L2_semantic_vector_search"] += vector_latency_ms
            record(
                "L2_semantic_vector_search",
                list(vector_contexts)[:layer_limit],
                query_variant=normalized_query,
                backend="vector",
            )

        variant_layer_inputs = [variant for variant in variants if variant not in lexical_variants]
        for variant in variant_layer_inputs:
            if backend_call_count >= max_backend_calls:
                break
            started = time.perf_counter()
            contexts = self._bm25_contexts(variant, payloads, top_k=layer_limit)
            per_layer_latency_ms["L3_query_variant_search"] += round((time.perf_counter() - started) * 1000, 6)
            backend_call_count += 1
            record("L3_query_variant_search", contexts, query_variant=variant, backend="bm25")

        l4_started = time.perf_counter()
        anchor_values = [*anchors.get("entities", []), *anchors.get("rare", []), *anchors.get("numeric_or_date", [])]
        seen_l4: set[tuple[str, str, str, str]] = set()
        structure_rows: list[dict[str, Any]] = []
        for source_layer in (
            "L1_lexical_anchor_search",
            "L2_semantic_vector_search",
            "L3_query_variant_search",
        ):
            for row in layer_candidates[source_layer]:
                title_section = " ".join([_clean(row.get("title")), _clean(row.get("section"))])
                normalized_title_section = normalize_answer_text(title_section)
                if not title_section and not row.get("source_atom_id") and not row.get("evidence_bundle_id"):
                    continue
                if anchor_values and normalized_title_section:
                    if not any(normalize_answer_text(anchor) in normalized_title_section for anchor in anchor_values):
                        continue
                key = _layered_context_key(row)
                if key in seen_l4:
                    continue
                seen_l4.add(key)
                structure_rows.append(
                    _annotate_source_native_layer_context(
                        row,
                        layer="L4_structure_aware_source_native_search",
                        query_variant="structure_metadata_filter",
                        backend=_clean(row.get("retrieval_backend")) or selected_backend,
                    )
                )
                if len(structure_rows) >= layer_limit:
                    break
            if len(structure_rows) >= layer_limit:
                break
        layer_candidates["L4_structure_aware_source_native_search"] = structure_rows
        per_layer_candidate_counts["L4_structure_aware_source_native_search"] = len(structure_rows)
        per_layer_latency_ms["L4_structure_aware_source_native_search"] = round((time.perf_counter() - l4_started) * 1000, 6)

        l5_started = time.perf_counter()
        layer_weights = {
            "L1_lexical_anchor_search": 1.0,
            "L2_semantic_vector_search": 1.0,
            "L3_query_variant_search": 0.8,
            "L4_structure_aware_source_native_search": 0.6,
        }
        fused: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for layer, weight in layer_weights.items():
            for position, row in enumerate(layer_candidates[layer], start=1):
                key = _layered_context_key(row)
                if key not in fused:
                    fused[key] = dict(row)
                    fused[key]["fusion_score"] = 0.0
                    fused[key]["layer_provenance"] = []
                    fused[key]["query_variant_provenance"] = []
                fused[key]["fusion_score"] = float(fused[key].get("fusion_score") or 0.0) + weight / (60 + position)
                for provenance in row.get("layer_provenance") or []:
                    if provenance not in fused[key]["layer_provenance"]:
                        fused[key]["layer_provenance"].append(provenance)
                for variant in row.get("query_variant_provenance") or []:
                    if variant not in fused[key]["query_variant_provenance"]:
                        fused[key]["query_variant_provenance"].append(variant)
        merged = sorted(
            fused.values(),
            key=lambda row: (
                -float(row.get("fusion_score") or 0.0),
                _clean(row.get("doc_id")),
                _clean(row.get("chunk_id")),
                _clean(row.get("text")),
            ),
        )[: int(bounds["max_merged_candidates"])]
        for row in merged:
            if "L5_merge_dedupe" not in row["layer_provenance"]:
                row["layer_provenance"].append("L5_merge_dedupe")
            row["retrieval_surface"] = "source_native"
        layer_candidates["L5_merge_dedupe"] = [dict(row) for row in merged]
        per_layer_candidate_counts["L5_merge_dedupe"] = len(merged)
        per_layer_latency_ms["L5_merge_dedupe"] = round((time.perf_counter() - l5_started) * 1000, 6)

        l6_started = time.perf_counter()
        chunk_to_index = {_clean(payload.get("search_unit_id")): index for index, payload in enumerate(payloads)}
        expanded: list[dict[str, Any]] = []
        existing_keys = {_layered_context_key(row) for row in merged}
        window = int(bounds["max_neighbor_expansion_windows"])
        for row in merged[: max(int(top_k), 1)]:
            index = chunk_to_index.get(_clean(row.get("chunk_id")))
            if index is None:
                continue
            for offset in range(-window, window + 1):
                if offset == 0:
                    continue
                neighbor_index = index + offset
                if neighbor_index < 0 or neighbor_index >= len(payloads):
                    continue
                neighbor_payload = payloads[neighbor_index]
                neighbor = self._context_from_payload(neighbor_payload, 0, 0.0, "neighbor")
                same_doc = _clean(neighbor.get("doc_id")) == _clean(row.get("doc_id"))
                same_section = _clean(neighbor.get("section")) and _clean(neighbor.get("section")) == _clean(row.get("section"))
                same_title = _clean(neighbor.get("title")) and _clean(neighbor.get("title")) == _clean(row.get("title"))
                if not same_doc or not (same_section or same_title):
                    continue
                key = _layered_context_key(neighbor)
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                neighbor = _annotate_source_native_layer_context(
                    neighbor,
                    layer="L6_source_neighbor_expansion",
                    query_variant="same_doc_section_neighbor",
                    backend="neighbor",
                )
                neighbor["neighbor_expansion_source_chunk_id"] = _clean(row.get("chunk_id"))
                expanded.append(neighbor)
                if len(expanded) >= layer_limit:
                    break
            if len(expanded) >= layer_limit:
                break
        layer_candidates["L6_source_neighbor_expansion"] = expanded
        per_layer_candidate_counts["L6_source_neighbor_expansion"] = len(expanded)
        per_layer_latency_ms["L6_source_neighbor_expansion"] = round((time.perf_counter() - l6_started) * 1000, 6)

        l7_started = time.perf_counter()
        rerank_pool: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for row in [*merged, *expanded]:
            key = _layered_context_key(row)
            if key not in rerank_pool:
                rerank_pool[key] = dict(row)
            else:
                for provenance in row.get("layer_provenance") or []:
                    if provenance not in rerank_pool[key].setdefault("layer_provenance", []):
                        rerank_pool[key]["layer_provenance"].append(provenance)
        reranked: list[dict[str, Any]] = []
        for row in rerank_pool.values():
            score, diagnostics = _source_native_anchor_rerank_score(row, query=query, anchors=anchors)
            context = dict(row)
            context["anchor_aware_rerank_score"] = round(float(score), 6)
            context["anchor_aware_diagnostics"] = diagnostics
            context["score"] = round(float(score), 6)
            context["retrieval_backend"] = selected_backend
            context["retrieval_surface"] = "source_native"
            if "L7_anchor_aware_reranking_diagnostics" not in context.setdefault("layer_provenance", []):
                context["layer_provenance"].append("L7_anchor_aware_reranking_diagnostics")
            reranked.append(context)
        reranked.sort(
            key=lambda row: (
                -float(row.get("anchor_aware_rerank_score") or 0.0),
                _clean(row.get("doc_id")),
                _clean(row.get("chunk_id")),
                _clean(row.get("text")),
            )
        )
        final_contexts: list[dict[str, Any]] = []
        for rank, row in enumerate(reranked[: max(int(top_k), 0)], start=1):
            context = dict(row)
            context["rank"] = rank
            context["layer_provenance"] = sorted(set(context.get("layer_provenance") or []))
            context["query_variant_provenance"] = sorted(set(context.get("query_variant_provenance") or []))
            final_contexts.append(context)
        layer_candidates["L7_anchor_aware_reranking_diagnostics"] = final_contexts
        per_layer_candidate_counts["L7_anchor_aware_reranking_diagnostics"] = len(final_contexts)
        per_layer_latency_ms["L7_anchor_aware_reranking_diagnostics"] = round((time.perf_counter() - l7_started) * 1000, 6)

        report = {
            "enabled": True,
            "planner": "bounded_deterministic_source_native_layered_retrieval_v1",
            "selected_surface": "source_native",
            "selected_backend": selected_backend,
            "layers": list(SOURCE_NATIVE_LAYERED_RETRIEVAL_LAYERS),
            "query_variants": variants,
            "query_variant_count": len(variants),
            "backend_call_count": backend_call_count,
            "per_layer_candidate_counts": per_layer_candidate_counts,
            "per_layer_latency_ms": {key: round(float(value), 6) for key, value in per_layer_latency_ms.items()},
            "merge_policy": "rrf_v1",
            "rerank_policy": "anchor_aware_diagnostic_rerank_v1",
            "final_candidate_count": len(final_contexts),
            "bounds": bounds,
            "anchor_diagnostics": {
                "entity_anchor_count": len(anchors.get("entities", [])),
                "numeric_or_date_anchor_count": len(anchors.get("numeric_or_date", [])),
                "rare_anchor_count": len(anchors.get("rare", [])),
                "required_numeric_date_anchor_coverage": bool(
                    not anchors.get("numeric_or_date")
                    or any(
                        set(anchors.get("numeric_or_date", []))
                        & set((row.get("anchor_aware_diagnostics") or {}).get("numeric_or_date_anchor_hits") or [])
                        for row in final_contexts
                    )
                ),
            },
            "gold_fields_used_for_candidate_generation": False,
            "expected_fields_used_for_candidate_generation": False,
            "qrels_used_for_candidate_generation": False,
            "answerability_labels_used_for_candidate_generation": False,
            "ids_used_for_candidate_generation": False,
            "baseline_topk_used_for_candidate_generation": False,
            "searchunit_searchview_used_as_candidate_surface": False,
            "legacy_searchunit_comparison_enabled": False,
            "source_native_units_only": True,
            "fallback_reason": _clean(self._vector_fallback_reason) if selected_backend in {"vector", "hybrid"} else "",
        }
        return final_contexts, report

    def presence_probe(self, item: EvalItem) -> dict[str, Any]:
        evidence_texts = [_clean(evidence.text) for evidence in item.expected_evidence if _clean(evidence.text)]
        anchors = sorted(_candidate_anchors(item.expected_answer, *item.expected_answer_aliases, *evidence_texts))
        exact_present = False
        normalized_present = False
        anchor_present = False
        normalized_evidence = [normalize_answer_text(text) for text in evidence_texts if normalize_answer_text(text)]
        for payload in self._load_payloads():
            text = _clean(payload.get("bm25_text") or payload.get("embedding_text"))
            normalized = normalize_answer_text(text)
            if evidence_texts and any(text_value in text for text_value in evidence_texts):
                exact_present = True
            if normalized_evidence and any(text_value and text_value in normalized for text_value in normalized_evidence):
                normalized_present = True
            if anchors and _anchor_in_text(anchors, text):
                anchor_present = True
            if (not evidence_texts or exact_present or normalized_present) and (not anchors or anchor_present):
                break
        return {
            "expected_evidence_exact_present": exact_present,
            "expected_evidence_normalized_present": normalized_present,
            "expected_anchor_present": anchor_present,
            "anchor_count": len(anchors),
        }


def _contexts_match_expected(item: EvalItem, contexts: Sequence[Mapping[str, Any]]) -> bool:
    evidence_texts = [_clean(evidence.text) for evidence in item.expected_evidence if _clean(evidence.text)]
    normalized_evidence = [normalize_answer_text(text) for text in evidence_texts if normalize_answer_text(text)]
    anchors = sorted(_candidate_anchors(item.expected_answer, *item.expected_answer_aliases, *evidence_texts))
    for context in contexts:
        text = _clean(context.get("text"))
        normalized = normalize_answer_text(text)
        if normalized_evidence and any(value and value in normalized for value in normalized_evidence):
            return True
        if anchors and _anchor_requirements_satisfied(anchors, text):
            return True
    return False


def _context_matches_evidence_indices(item: EvalItem, context: Mapping[str, Any]) -> set[int]:
    matched: set[int] = set()
    for index, evidence in enumerate(_required_evidence(item)):
        anchors = _evidence_match_anchors(item, evidence)
        if _evidence_matches_row(evidence, context) or _weak_evidence_matches_row(
            evidence,
            context,
            anchors=anchors,
        ):
            matched.add(index)
    return matched


def _diagnostic_ndcg_at_k(relevances: Sequence[int], *, k: int, ideal_relevant_count: int) -> float | None:
    if ideal_relevant_count <= 0:
        return None
    cutoff = max(0, int(k))
    if cutoff == 0:
        return 0.0
    dcg = 0.0
    for rank, rel in enumerate(list(relevances)[:cutoff], start=1):
        if rel:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(int(ideal_relevant_count), cutoff)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    if idcg <= 0.0:
        return 0.0
    return round(dcg / idcg, 6)


def _dedupe_contexts_for_diagnostics(contexts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for context in contexts:
        if not isinstance(context, Mapping):
            continue
        key = (
            _clean(context.get("doc_id")),
            _clean(context.get("chunk_id")),
            _sha256_text(context.get("text")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(context))
    return deduped


@dataclass(frozen=True)
class _MmrDiagnosticCandidate:
    row: Mapping[str, Any]
    doc_id: str
    title: str
    score: float
    rerank_score: float | None = None


def _mmr_select_contexts(
    contexts: Sequence[Mapping[str, Any]],
    *,
    top_k: int,
    lambda_val: float = SOURCE_NATIVE_MMR_DIAGNOSTIC_LAMBDA,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates = [
        _MmrDiagnosticCandidate(
            row=dict(context),
            doc_id=_clean(context.get("doc_id")),
            title=_clean(context.get("title") or context.get("section")),
            score=float(context.get("fusion_score") or context.get("score") or 0.0),
            rerank_score=float(context.get("rerank_score")) if context.get("rerank_score") is not None else None,
        )
        for context in _dedupe_contexts_for_diagnostics(contexts)
    ]
    if not candidates:
        return [], {
            "mmr_enabled": True,
            "mmr_lambda": float(lambda_val),
            "candidate_pool_k": 0,
            "selected_k": 0,
            "selection_strategy": "mmr_score_fallback_doc_title_diversity",
            "fallback_reason": "empty_candidate_pool",
        }
    try:
        from ai.eval.harness.wide_retrieval_helpers import mmr_select_score_fallback

        selected = mmr_select_score_fallback(
            candidates,
            top_k=top_k,
            lambda_val=lambda_val,
            title_provider=lambda candidate: candidate.title,
        )
        rows = [dict(candidate.row) for candidate in selected]
        fallback_reason = ""
    except Exception as exc:
        rows = [dict(candidate.row) for candidate in candidates[: max(int(top_k), 0)]]
        fallback_reason = f"mmr_selector_unavailable:{type(exc).__name__}: {exc}"
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
        row["retrieval_backend"] = "mmr_selected"
        row["mmr_diagnostic_selected"] = True
    before_doc_ratio = _duplicate_ratio([candidate.doc_id for candidate in candidates[: max(int(top_k), 1)]])
    after_doc_ratio = _duplicate_ratio([_clean(row.get("doc_id")) for row in rows])
    return rows, {
        "mmr_enabled": True,
        "mmr_lambda": float(lambda_val),
        "candidate_pool_k": len(candidates),
        "selected_k": len(rows),
        "selection_strategy": "mmr_score_fallback_doc_title_diversity",
        "doc_id_penalty_applied": True,
        "title_penalty_applied": True,
        "pre_mmr_duplicate_doc_ratio@k": before_doc_ratio,
        "post_mmr_duplicate_doc_ratio@k": after_doc_ratio,
        "unique_doc_count_delta@k": len({_clean(row.get("doc_id")) for row in rows if _clean(row.get("doc_id"))})
        - len({candidate.doc_id for candidate in candidates[: max(int(top_k), 1)] if candidate.doc_id}),
        "fallback_reason": fallback_reason,
    }


def _duplicate_ratio(values: Sequence[str]) -> float:
    normalized = [_clean(value).casefold() for value in values if _clean(value)]
    if not normalized:
        return 0.0
    return round(1.0 - (len(set(normalized)) / len(normalized)), 6)


def _ranking_diagnostic_metrics(
    item: EvalItem,
    contexts: Sequence[Mapping[str, Any]],
    *,
    top_k_values: Sequence[int],
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    required = _required_evidence(item)
    metrics: dict[str, Any] = {
        "eligible": bool(required),
        "denominator_reason": "rows_with_expected_evidence_for_post_retrieval_diagnostics_only"
        if required
        else "missing_expected_evidence",
        "candidate_count": len([context for context in contexts if isinstance(context, Mapping)]),
        "selected_chunk_ids": [_clean(context.get("chunk_id")) for context in contexts if isinstance(context, Mapping)],
        "first_relevant_rank": None,
        "relevant_expected_evidence_count": 0,
        "diagnostic_only": True,
        "official_metric": False,
    }
    if extra:
        metrics.update(dict(extra))
    for k in top_k_values:
        metrics[f"hit@{k}"] = None
        metrics[f"ndcg@{k}"] = None
    if not required:
        return metrics
    seen_evidence: set[int] = set()
    relevances: list[int] = []
    for rank, context in enumerate(contexts, start=1):
        if not isinstance(context, Mapping):
            relevances.append(0)
            continue
        matched = _context_matches_evidence_indices(item, context)
        if matched and metrics["first_relevant_rank"] is None:
            metrics["first_relevant_rank"] = rank
        new_matches = matched - seen_evidence
        relevances.append(1 if new_matches else 0)
        seen_evidence.update(matched)
    metrics["relevant_expected_evidence_count"] = len(seen_evidence)
    for k in top_k_values:
        cutoff = max(int(k), 0)
        hit = 1.0 if any(relevances[:cutoff]) else 0.0
        metrics[f"hit@{k}"] = hit
        metrics[f"ndcg@{k}"] = _diagnostic_ndcg_at_k(
            relevances,
            k=k,
            ideal_relevant_count=len(required),
        )
    return metrics


def _source_native_diagnostic_retrieval_metrics_for_item(
    item: EvalItem,
    *,
    bm25_contexts: Sequence[Mapping[str, Any]],
    vector_contexts: Sequence[Mapping[str, Any]],
    hybrid_contexts: Sequence[Mapping[str, Any]],
    selected_contexts: Sequence[Mapping[str, Any]],
    top_k: int,
) -> dict[str, Any]:
    top_k_values = top_k_values_for(top_k)
    mmr_pool = _dedupe_contexts_for_diagnostics(
        [
            *list(hybrid_contexts),
            *list(selected_contexts),
            *list(vector_contexts),
            *list(bm25_contexts),
        ]
    )
    mmr_contexts, mmr_report = _mmr_select_contexts(
        mmr_pool,
        top_k=top_k,
        lambda_val=SOURCE_NATIVE_MMR_DIAGNOSTIC_LAMBDA,
    )
    rankings = {
        "bm25": _ranking_diagnostic_metrics(item, bm25_contexts, top_k_values=top_k_values),
        "vector": _ranking_diagnostic_metrics(item, vector_contexts, top_k_values=top_k_values),
        "hybrid": _ranking_diagnostic_metrics(item, hybrid_contexts, top_k_values=top_k_values),
        "selected": _ranking_diagnostic_metrics(item, selected_contexts, top_k_values=top_k_values),
        "mmr_selected": _ranking_diagnostic_metrics(
            item,
            mmr_contexts,
            top_k_values=top_k_values,
            extra=mmr_report,
        ),
    }
    return {
        **rankings,
        "enabled": True,
        "diagnostic_only": True,
        "official_metric": False,
        "metric_policy": "diagnostic_only_not_official",
        "denominator_policy": "rows_with_expected_evidence_for_post_retrieval_diagnostics_only",
        "candidate_generation_input_policy": "query_text_only_no_gold_qrels_labels_ids_or_baseline_topk",
        "gold_fields_used_for_candidate_generation": False,
        "expected_fields_used_for_candidate_generation": False,
        "qrels_used_for_candidate_generation": False,
        "ids_used_for_candidate_generation": False,
        "baseline_topk_used_for_candidate_generation": False,
        "post_retrieval_expected_evidence_diagnostics": bool(item.has_expected_evidence),
    }


def build_diagnostic_retrieval_metrics_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    top_k: int,
) -> dict[str, Any]:
    top_k_values = top_k_values_for(top_k)
    ranking_names = ("bm25", "vector", "hybrid", "selected", "mmr_selected")
    rankings: dict[str, dict[str, Any]] = {}
    for name in ranking_names:
        denominators = 0
        sums: dict[str, float] = {f"hit@{k}": 0.0 for k in top_k_values}
        sums.update({f"ndcg@{k}": 0.0 for k in top_k_values})
        candidate_counts: list[int] = []
        mmr_template: dict[str, Any] = {}
        for row in rows:
            item_metrics = row.get("diagnostic_retrieval_metrics") if isinstance(row, Mapping) else {}
            metric = item_metrics.get(name) if isinstance(item_metrics, Mapping) else {}
            if not isinstance(metric, Mapping) or not metric.get("eligible"):
                continue
            denominators += 1
            candidate_counts.append(int(metric.get("candidate_count") or 0))
            if name == "mmr_selected":
                mmr_template = {
                    "mmr_enabled": bool(metric.get("mmr_enabled")),
                    "mmr_lambda": metric.get("mmr_lambda"),
                    "selection_strategy": metric.get("selection_strategy"),
                    "candidate_pool_k_max": max(
                        int(mmr_template.get("candidate_pool_k_max") or 0),
                        int(metric.get("candidate_pool_k") or 0),
                    ),
                    "selected_k_max": max(
                        int(mmr_template.get("selected_k_max") or 0),
                        int(metric.get("selected_k") or 0),
                    ),
                }
            for key in sums:
                value = metric.get(key)
                if value is not None:
                    sums[key] += float(value)
        aggregate = {
            "eligible_item_count": denominators,
            "denominator": denominators,
            "candidate_count_avg": None
            if not candidate_counts
            else round(sum(candidate_counts) / len(candidate_counts), 6),
            "diagnostic_only": True,
            "official_metric": False,
        }
        for key, value in sums.items():
            aggregate[key] = None if denominators == 0 else round(value / denominators, 6)
        aggregate.update(mmr_template)
        rankings[name] = aggregate
    return {
        "enabled": True,
        "metric_policy": "diagnostic_only_not_official",
        "denominator_policy": "rows_with_expected_evidence_for_post_retrieval_diagnostics_only",
        "candidate_generation_input_policy": "query_text_only_no_gold_qrels_labels_ids_or_baseline_topk",
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "semantic_quality_claim_allowed": False,
        "gold_fields_used_for_candidate_generation": False,
        "expected_fields_used_for_candidate_generation": False,
        "qrels_used_for_candidate_generation": False,
        "ids_used_for_candidate_generation": False,
        "baseline_topk_used_for_candidate_generation": False,
        "mrr_or_reciprocal_rank_reported": False,
        "mmr_is_selection_strategy_not_reciprocal_rank": True,
        "rankings": rankings,
    }


def build_semantic_quality_samples_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    max_samples: int = 8,
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for row in rows:
        if len(samples) >= max_samples:
            break
        if not isinstance(row, Mapping):
            continue
        contexts = [context for context in _as_list(row.get("retrieved_contexts")) if isinstance(context, Mapping)]
        sample = {
            "id": _clean(row.get("id")),
            "query": _clean(row.get("query")),
            "answerability": _clean(row.get("answerability")),
            "generated_answer_excerpt": _redact_absolute_local_paths(_clean(row.get("generated_answer"))[:600]),
            "failure_labels": list(row.get("failure_labels") or [])[:12],
            "judge_result": row.get("metric_results", {}).get("judged_answer_correctness_provisional")
            if isinstance(row.get("metric_results"), Mapping)
            else None,
            "diagnostic_retrieval_metrics": row.get("diagnostic_retrieval_metrics")
            if isinstance(row.get("diagnostic_retrieval_metrics"), Mapping)
            else {},
            "retrieved_contexts": [
                {
                    "rank": context.get("rank"),
                    "doc_id": _clean(context.get("doc_id")),
                    "chunk_id": _clean(context.get("chunk_id")),
                    "source_family": _clean(context.get("source_family")),
                    "retrieval_backend": _clean(context.get("retrieval_backend")),
                    "score": context.get("score"),
                    "text_sha256": _clean(context.get("source_text_sha256")) or _sha256_text(context.get("text")),
                    "text_preview": _redact_absolute_local_paths(_clean(context.get("text"))[:240]),
                }
                for context in contexts[:3]
            ],
        }
        samples.append(sample)
    return {
        "enabled": True,
        "sample_policy": "bounded_query_response_context_examples_no_raw_prompt_or_full_raw_response",
        "semantic_quality_claim_allowed": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "sample_count": len(samples),
        "samples": samples,
    }


def _surface_output_summary(item: EvalItem, output: Mapping[str, Any], presence: Mapping[str, Any], surface: str) -> dict[str, Any]:
    contexts = [
        _runtime_safe_evidence_context(context)
        for context in _as_list(output.get("retrieved_contexts"))
        if isinstance(context, Mapping)
    ]
    families = Counter(_clean(context.get("source_family")) or "unknown" for context in contexts)
    return {
        "surface": surface,
        "backend": (output.get("retrieval_backend_comparison") or {}).get("selected_backend")
        if isinstance(output.get("retrieval_backend_comparison"), Mapping)
        else "",
        "candidate_count": len(contexts),
        "retrieval_empty": not contexts,
        "latency_ms": (output.get("retrieval_backend_comparison") or {}).get("latency_ms")
        if isinstance(output.get("retrieval_backend_comparison"), Mapping)
        else {},
        "source_family_distribution": dict(sorted(families.items())),
        "top_k_previews": [
            {
                "rank": context.get("rank"),
                "doc_id": _clean(context.get("doc_id")),
                "chunk_id": _clean(context.get("chunk_id")),
                "source_atom_id": _clean(context.get("source_atom_id")),
                "source_family": _clean(context.get("source_family")),
                "score": context.get("score"),
                "text_preview": _clean(context.get("text"))[:240],
            }
            for context in contexts[:10]
        ],
        "expected_evidence_in_corpus_exact": bool(presence.get("expected_evidence_exact_present")),
        "expected_evidence_in_corpus_normalized": bool(presence.get("expected_evidence_normalized_present")),
        "expected_anchor_in_corpus": bool(presence.get("expected_anchor_present")),
        "expected_evidence_retrieved": _contexts_match_expected(item, contexts),
    }


def _disabled_surface_output_summary(surface: str, reason: str) -> dict[str, Any]:
    return {
        "surface": surface,
        "comparison_enabled": False,
        "candidate_count": None,
        "retrieval_empty": None,
        "latency_ms": {},
        "source_family_distribution": {},
        "top_k_previews": [],
        "expected_evidence_in_corpus_exact": None,
        "expected_evidence_in_corpus_normalized": None,
        "expected_anchor_in_corpus": None,
        "expected_evidence_retrieved": None,
        "fallback_reason": reason,
    }


class SurfaceComparingRagAdapter:
    """Runs source-native retrieval beside the legacy SearchUnit/SearchView baseline."""

    def __init__(
        self,
        *,
        requested_surface: str = "auto",
        requested_backend: str = "auto",
        source_adapter: SourceNativeHybridAdapter,
        searchunit_adapter: RepoCurrentHybridAdapter,
        legacy_surface_comparison: bool = False,
    ) -> None:
        self.requested_surface = _clean(requested_surface).replace("_", "-").lower() or "auto"
        if self.requested_surface not in {"auto", "source-native", "source-atom", "evidence-bundle", "searchunit-searchview"}:
            raise DatasetSchemaError(f"unsupported retrieval surface: {requested_surface}")
        if self.requested_surface == "searchunit-searchview" and not legacy_surface_comparison:
            raise DatasetSchemaError(
                "retrieval_surface=searchunit-searchview is legacy/debug only; pass legacy_surface_comparison=True"
            )
        self.requested_backend = requested_backend
        self.source_adapter = source_adapter
        self.searchunit_adapter = searchunit_adapter
        self.legacy_surface_comparison = bool(legacy_surface_comparison)
        self._last_surface_comparisons: list[dict[str, Any]] = []

    @property
    def selected_surface(self) -> str:
        if self.requested_surface == "searchunit-searchview":
            return "searchunit_searchview"
        if self.source_available:
            return "source_native"
        return "unavailable"

    @property
    def source_available(self) -> bool:
        try:
            return bool(self.source_adapter._load_payloads())
        except DatasetSchemaError:
            raise
        except Exception:
            return False

    @property
    def config(self) -> dict[str, Any]:
        return {
            "adapter": "surface_comparing_actual_rag_adapter",
            "requested_surface": self.requested_surface,
            "selected_surface": self.selected_surface,
            "requested_backend": self.requested_backend,
            "source_native": self.source_adapter.config,
            "searchunit_searchview": {
                **self.searchunit_adapter.config,
                "role": "legacy_comparison_debug_only",
                "candidate_surface_enabled": self.selected_surface == "searchunit_searchview",
                "legacy_comparison_enabled": self.legacy_surface_comparison,
            },
            "candidate_generation_input_policy": "query_text_only; expected fields diagnostics_only_after_retrieval",
        }

    @property
    def retrieval_backend_report(self) -> dict[str, Any]:
        if self.selected_surface == "source_native":
            return dict(self.source_adapter.retrieval_backend_report)
        if self.selected_surface == "searchunit_searchview":
            return dict(self.searchunit_adapter.retrieval_backend_report)
        return {
            "requested": self.requested_backend,
            "selected": "unavailable",
            "bm25_enabled": False,
            "vector_enabled": False,
            "hybrid_enabled": False,
            "embedding_model": "",
            "embedding_device": "unavailable",
            "gpu_used_for_embedding": False,
            "vector_index_kind": "unavailable",
            "vector_index_type": "unavailable",
            "vector_dim": 0,
            "indexed_unit_count": 0,
            "query_count": 0,
            "fallback_reason": "source_native_unavailable_auto_fallback_to_searchunit_disabled",
        }

    @property
    def retrieval_surface_report(self) -> dict[str, Any]:
        fallback = ""
        if self.selected_surface != "source_native":
            fallback = "source_native_unavailable" if not self.source_available else "searchunit_surface_requested"
        return {
            "requested": self.requested_surface.replace("-", "_"),
            "selected": self.selected_surface,
            "source_native_available": self.source_available,
            "source_native_unit_count": len(self.source_adapter._load_payloads()) if self.source_available else 0,
            "source_native_selected": self.selected_surface == "source_native",
            "searchunit_searchview_role": "legacy_comparison_debug_only",
            "searchunit_searchview_candidate_surface_enabled": self.selected_surface == "searchunit_searchview",
            "legacy_surface_comparison_enabled": self.legacy_surface_comparison,
            "auto_fallback_to_searchunit_searchview": False,
            "fallback_reason": fallback,
        }

    @property
    def backend_diagnostics(self) -> dict[str, Any]:
        if self.selected_surface == "source_native":
            return dict(self.source_adapter.backend_diagnostics)
        if self.selected_surface == "searchunit_searchview":
            return dict(self.searchunit_adapter.backend_diagnostics)
        return {
            "embedding_build_latency_ms": 0.0,
            "index_load_or_build_latency_ms": 0.0,
            "vector_index_available": False,
            "gpu_used_for_embedding": False,
            "fallback_reason": "source_native_unavailable_auto_fallback_to_searchunit_disabled",
        }

    @property
    def vector_index_audit_report(self) -> dict[str, Any]:
        if self.selected_surface == "source_native":
            return dict(self.source_adapter.vector_index_audit_report)
        return {
            "enabled": False,
            "status": "not_source_native_vector_surface",
            "vector_surface": self.selected_surface,
            "semantic_quality_claim_allowed": False,
            "index_integrity_passed": False,
            "query_invocation_passed": False,
            "hydration_passed": False,
            "hybrid_comparison_available": False,
        }

    @property
    def retrieval_surface_decision(self) -> dict[str, Any]:
        source_wins = sum(1 for row in self._last_surface_comparisons if row.get("source_native_beats_searchunit"))
        searchunit_wins = sum(1 for row in self._last_surface_comparisons if row.get("searchunit_beats_source_native"))
        demoted = self.source_available and self.selected_surface == "source_native" and searchunit_wins == 0
        if not self.source_available:
            recommendation = "repair_source_native_corpus_loading_before_ranking_work"
            reason = "source_native_unavailable"
        elif source_wins > searchunit_wins:
            recommendation = "keep_source_native_as_default_and_repair_source_native_retrieval_misses"
            reason = "source_native_has_better_post_retrieval_expected_evidence_diagnostics"
        elif demoted:
            recommendation = "keep_source_native_as_default; searchunit_searchview_has_no_observed_advantage"
            reason = "source_native_available_and_searchunit_has_no_diagnostic_advantage"
        else:
            recommendation = "inspect_surface_diagnostics_before_default_change"
            reason = "surface_advantage_inconclusive"
        return {
            "selected_default_surface": self.selected_surface,
            "searchunit_searchview_demoted": demoted,
            "demotion_reason": reason if demoted else "",
            "source_native_available": self.source_available,
            "source_native_selected": self.selected_surface == "source_native",
            "fallback_reason": "" if self.source_available else "source_native_unavailable_auto_fallback_to_searchunit_disabled",
            "recommendation": recommendation,
        }

    def run_item(self, item: EvalItem, *, top_k: int) -> dict[str, Any]:
        source_output = self.source_adapter.run_item(item, top_k=top_k) if self.source_available else _pipeline_error_output(item, "source_native_unavailable_auto_fallback_to_searchunit_disabled")
        searchunit_output: dict[str, Any] | None = None
        if self.selected_surface == "searchunit_searchview" or self.legacy_surface_comparison:
            searchunit_output = self.searchunit_adapter.run_item(item, top_k=top_k)
        selected_output = source_output if self.selected_surface == "source_native" else searchunit_output
        if selected_output is None:
            selected_output = _pipeline_error_output(item, "source_native_unavailable_auto_fallback_to_searchunit_disabled")
        output = dict(selected_output)
        output["retrieved_contexts"] = [
            _runtime_safe_evidence_context(context)
            for context in _as_list(selected_output.get("retrieved_contexts"))
            if isinstance(context, Mapping)
        ]
        output["citations"] = [
            _runtime_safe_evidence_context(citation)
            for citation in _as_list(selected_output.get("citations"))
            if isinstance(citation, Mapping)
        ]
        output["retrieval_backend_comparison"] = selected_output.get("retrieval_backend_comparison")
        source_presence = self.source_adapter.presence_probe(item) if self.source_available else {}
        source_summary = _surface_output_summary(item, source_output, source_presence, "source_native")
        if searchunit_output is not None:
            searchunit_presence = self._searchunit_presence_probe(item)
            searchunit_summary = _surface_output_summary(item, searchunit_output, searchunit_presence, "searchunit_searchview")
            searchunit_summary["comparison_enabled"] = True
        else:
            searchunit_summary = _disabled_surface_output_summary(
                "searchunit_searchview",
                "legacy_surface_comparison_not_requested",
            )
        comparison = {
            "searchunit_searchview": searchunit_summary,
            "source_native": source_summary,
            "selected": {
                "surface": self.selected_surface,
                "backend": (selected_output.get("retrieval_backend_comparison") or {}).get("selected_backend")
                if isinstance(selected_output.get("retrieval_backend_comparison"), Mapping)
                else "",
                "candidate_count": len(output["retrieved_contexts"]),
                "fallback_reason": self.retrieval_surface_report.get("fallback_reason"),
            },
            "source_native_beats_searchunit": bool(
                searchunit_summary.get("comparison_enabled")
                and source_summary["expected_evidence_retrieved"]
                and not searchunit_summary["expected_evidence_retrieved"]
            ),
            "searchunit_beats_source_native": bool(
                searchunit_summary.get("comparison_enabled")
                and searchunit_summary["expected_evidence_retrieved"]
                and not source_summary["expected_evidence_retrieved"]
            ),
            "both_surfaces_fail": bool(
                searchunit_summary.get("comparison_enabled")
                and not source_summary["expected_evidence_retrieved"]
                and not searchunit_summary["expected_evidence_retrieved"]
            ),
        }
        self._last_surface_comparisons.append(comparison)
        output["retrieval_surface_comparison"] = comparison
        output.setdefault("diagnostics", {})["retrieval_surface_comparison"] = comparison
        return output

    def evidence_candidates(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        if self.selected_surface == "source_native":
            return self.source_adapter.evidence_candidates(query, top_k=top_k)
        if self.selected_surface == "searchunit_searchview" and self.legacy_surface_comparison:
            return self.searchunit_adapter.evidence_candidates(query, top_k=top_k)
        return []

    def full_corpus_evidence_candidates(
        self,
        item: EvalItem,
        evidence: ExpectedEvidence,
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        if self.selected_surface == "source_native" and self.source_available:
            method = getattr(self.source_adapter, "full_corpus_evidence_candidates", None)
            if callable(method):
                return [
                    dict(candidate)
                    for candidate in method(item, evidence, top_k=top_k)
                    if isinstance(candidate, Mapping)
                ]
        return []

    def _searchunit_presence_probe(self, item: EvalItem) -> dict[str, Any]:
        evidence_texts = [_clean(evidence.text) for evidence in item.expected_evidence if _clean(evidence.text)]
        anchors = sorted(_candidate_anchors(item.expected_answer, *item.expected_answer_aliases, *evidence_texts))
        exact_present = False
        normalized_present = False
        anchor_present = False
        normalized_evidence = [normalize_answer_text(text) for text in evidence_texts if normalize_answer_text(text)]
        for payload in self.searchunit_adapter._load_payloads():
            text = _clean(payload.get("bm25_text") or payload.get("embedding_text"))
            normalized = normalize_answer_text(text)
            if evidence_texts and any(text_value in text for text_value in evidence_texts):
                exact_present = True
            if normalized_evidence and any(text_value and text_value in normalized for text_value in normalized_evidence):
                normalized_present = True
            if anchors and _anchor_in_text(anchors, text):
                anchor_present = True
            if (not evidence_texts or exact_present or normalized_present) and (not anchors or anchor_present):
                break
        return {
            "expected_evidence_exact_present": exact_present,
            "expected_evidence_normalized_present": normalized_present,
            "expected_anchor_present": anchor_present,
            "anchor_count": len(anchors),
        }


def _context_to_chunk(context: Mapping[str, Any]) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=_clean(context.get("chunk_id")) or f"rank-{row_rank(context)}",
        doc_id=_clean(context.get("doc_id")) or "unknown-doc",
        section=_clean(context.get("section")) or _clean(context.get("chunk_id")) or "context",
        text=_clean(context.get("text")),
        score=float(context.get("score") or 0.0),
    )


def _item_output(
    item: EvalItem,
    *,
    generated_answer: str,
    contexts: Sequence[Mapping[str, Any]],
    citations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    context_rows = [_runtime_safe_evidence_context(context) for context in contexts]
    citation_rows = [_runtime_safe_evidence_context(citation) for citation in citations]
    return {
        "id": item.id,
        "query": item.query,
        "answerability": item.answerability,
        "generated_answer": generated_answer,
        "retrieved_contexts": context_rows,
        "citations": citation_rows,
        "expected_answer": item.expected_answer,
        "expected_answer_aliases": list(item.expected_answer_aliases),
        "expected_evidence": [evidence.to_dict() for evidence in item.expected_evidence],
        "metric_inputs_available": _metric_inputs_available(item, has_citations=bool(citation_rows)),
        "diagnostics": _diagnostics_for_output(
            item,
            generated_answer=generated_answer,
            contexts=context_rows,
            citations=citation_rows,
        ),
    }


def top_k_values_for(top_k: int) -> tuple[int, ...]:
    values = [value for value in DEFAULT_TOP_K_VALUES if value <= top_k]
    values.append(top_k)
    return tuple(sorted(set(value for value in values if value > 0)))


def build_judge_adapter(
    *,
    judge_mode: str = "heuristic",
    judge_backend: str = "",
    judge_base_url: str = "",
    judge_model: str = "",
    judge_threshold: float = 0.5,
    judge_timeout_seconds: int = 60,
    judge_max_tokens: int = 360,
    skip_judge_endpoint_check: bool = False,
) -> Any:
    mode = _clean(judge_mode).lower() or "heuristic"
    if mode == "heuristic":
        return HeuristicJudgeAdapter(threshold=judge_threshold)
    if mode in {"local-llm", "local_llm", "llm"}:
        return LocalLLMJudgeAdapter(
            backend=judge_backend,
            base_url=judge_base_url,
            model=judge_model,
            threshold=judge_threshold,
            timeout_seconds=judge_timeout_seconds,
            max_tokens=judge_max_tokens,
            check_endpoint=not skip_judge_endpoint_check,
        )
    raise DatasetSchemaError(f"unsupported judge mode: {judge_mode}")


def dataset_slug_for_path(path: Path | str) -> str:
    stem = Path(path).stem.casefold()
    if "text" in stem and "gold" in stem:
        return "text_gold"
    if "fixture" in stem or "smoke" in stem or "tiny" in stem:
        return "fixture"
    slug = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    return (slug[:48].strip("_") or "dataset")


def _summary_dataset_slug(summary: Mapping[str, Any]) -> str:
    return _clean(summary.get("dataset_slug")) or dataset_slug_for_path(_clean(summary.get("dataset_path")))


def _run_id_timestamp(generated_at: str | None = None) -> str:
    value = _clean(generated_at)
    if value:
        match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z", value)
        if match:
            year, month, day, hour, minute, second = match.groups()
            return f"{year}{month}{day}_{hour}{minute}{second}"
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _output_dir_has_artifacts(path: Path) -> bool:
    return any((path / filename).exists() for filename in REPORT_ARTIFACT_FILENAMES)


def _output_dir_is_occupied(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def make_actual_rag_run_id(
    dataset_path: Path | str,
    *,
    explicit_run_id: str = "",
    generated_at: str | None = None,
    report_root: Path | str = REPORT_ROOT,
) -> str:
    explicit = _clean(explicit_run_id)
    if explicit:
        if not SAFE_RUN_ID_RE.fullmatch(explicit) or "/" in explicit or "\\" in explicit or ".." in explicit:
            raise DatasetSchemaError(f"run_id must be filesystem-safe: {explicit_run_id!r}")
        return explicit

    root = Path(report_root)
    base = f"actual_rag_eval_{dataset_slug_for_path(dataset_path)}_{_run_id_timestamp(generated_at)}"
    candidate = base
    suffix = 2
    while _output_dir_is_occupied(root / candidate):
        candidate = f"{base}_{suffix:02d}"
        suffix += 1
    return candidate


def validate_actual_rag_guardrails(summary: Mapping[str, Any]) -> None:
    run_id = _clean(summary.get("run_id")) or "<unknown-run>"
    expected_top_level = {
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }
    for key, expected in expected_top_level.items():
        if key not in summary:
            raise DatasetSchemaError(f"{run_id}: missing closed guardrail field {key}")
        if summary.get(key) != expected:
            raise DatasetSchemaError(f"{run_id}: {key} must be {expected!r}, got {summary.get(key)!r}")
    optional_false_top_level = (
        "gold_fields_used_for_candidate_generation",
        "expected_fields_used_for_candidate_generation",
        "qrels_used_for_candidate_generation",
        "answerability_labels_used_for_candidate_generation",
        "ids_used_for_candidate_generation",
        "query_id_used_for_candidate_generation",
        "row_id_used_for_candidate_generation",
        "target_id_used_for_candidate_generation",
        "baseline_topk_used_for_candidate_generation",
        "retriever_oracle_shortcut_used",
        "gate_uses_expected_fields",
        "gate_uses_gold_fields",
        "gate_uses_legacy_fields",
        "evidence_gate_retrieval_loop_triggered",
        "official_metric",
    )
    for key in optional_false_top_level:
        if key in summary and summary.get(key) is not False:
            raise DatasetSchemaError(f"{run_id}: {key} must be False, got {summary.get(key)!r}")

    guardrails = summary.get("guardrails")
    if not isinstance(guardrails, Mapping):
        raise DatasetSchemaError(f"{run_id}: guardrails must be present")
    expected_guardrails = {
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "answerability_label_mutation": False,
        "expected_answer_mutation": False,
        "expected_evidence_mutation": False,
        "denominator_mutation": False,
        "retriever_ranking_improvement": False,
        "official_metric": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_readiness_claim": False,
    }
    for key, expected in expected_guardrails.items():
        if key not in guardrails:
            raise DatasetSchemaError(f"{run_id}: missing guardrails.{key}")
        if guardrails.get(key) != expected:
            raise DatasetSchemaError(f"{run_id}: guardrails.{key} must be {expected!r}, got {guardrails.get(key)!r}")
    for key in optional_false_top_level:
        if key in guardrails and guardrails.get(key) is not False:
            raise DatasetSchemaError(f"{run_id}: guardrails.{key} must be False, got {guardrails.get(key)!r}")
    layered = summary.get("source_native_layered_retrieval")
    if isinstance(layered, Mapping) and layered.get("enabled"):
        for key in (
            "gold_fields_used_for_candidate_generation",
            "expected_fields_used_for_candidate_generation",
            "qrels_used_for_candidate_generation",
            "answerability_labels_used_for_candidate_generation",
            "ids_used_for_candidate_generation",
            "baseline_topk_used_for_candidate_generation",
            "searchunit_searchview_used_as_candidate_surface",
        ):
            if layered.get(key) is not False:
                raise DatasetSchemaError(f"{run_id}: source_native_layered_retrieval.{key} must be False")
        if layered.get("source_native_units_only") is not True:
            raise DatasetSchemaError(f"{run_id}: source_native_layered_retrieval.source_native_units_only must be True")
    vector_audit = summary.get("vector_index_audit")
    if isinstance(vector_audit, Mapping) and vector_audit.get("enabled"):
        if vector_audit.get("semantic_quality_claim_allowed") is not False:
            raise DatasetSchemaError(f"{run_id}: vector_index_audit.semantic_quality_claim_allowed must be False")
        target_presence = vector_audit.get("target_presence_diagnostics")
        if isinstance(target_presence, Mapping):
            for key in (
                "gold_fields_used_for_candidate_generation",
                "expected_fields_used_for_candidate_generation",
                "qrels_used_for_candidate_generation",
                "ids_used_for_candidate_generation",
                "baseline_topk_used_for_candidate_generation",
            ):
                if target_presence.get(key) is not False:
                    raise DatasetSchemaError(f"{run_id}: vector_index_audit.target_presence_diagnostics.{key} must be False")
    retrieval_metrics = summary.get("diagnostic_retrieval_metrics")
    if isinstance(retrieval_metrics, Mapping) and retrieval_metrics.get("enabled"):
        if retrieval_metrics.get("official_metric") is not False:
            raise DatasetSchemaError(f"{run_id}: diagnostic_retrieval_metrics.official_metric must be False")
        if retrieval_metrics.get("semantic_quality_claim_allowed") is not False:
            raise DatasetSchemaError(
                f"{run_id}: diagnostic_retrieval_metrics.semantic_quality_claim_allowed must be False"
            )
        for key in (
            "gold_fields_used_for_candidate_generation",
            "expected_fields_used_for_candidate_generation",
            "qrels_used_for_candidate_generation",
            "ids_used_for_candidate_generation",
            "baseline_topk_used_for_candidate_generation",
        ):
            if retrieval_metrics.get(key) is not False:
                raise DatasetSchemaError(f"{run_id}: diagnostic_retrieval_metrics.{key} must be False")
        if retrieval_metrics.get("mrr_or_reciprocal_rank_reported") is not False:
            raise DatasetSchemaError(f"{run_id}: diagnostic_retrieval_metrics must not report MRR")
    semantic_samples = summary.get("semantic_quality_samples")
    if isinstance(semantic_samples, Mapping) and semantic_samples.get("enabled"):
        if semantic_samples.get("semantic_quality_claim_allowed") is not False:
            raise DatasetSchemaError(f"{run_id}: semantic_quality_samples.semantic_quality_claim_allowed must be False")
        if semantic_samples.get("raw_prompt_payload_written") is not False:
            raise DatasetSchemaError(f"{run_id}: semantic_quality_samples.raw_prompt_payload_written must be False")
        if semantic_samples.get("raw_response_payload_written") is not False:
            raise DatasetSchemaError(f"{run_id}: semantic_quality_samples.raw_response_payload_written must be False")
    evidence_gate = summary.get("evidence_gate")
    if isinstance(evidence_gate, Mapping):
        gate_guardrails = evidence_gate.get("guardrail_status")
        if not isinstance(gate_guardrails, Mapping):
            raise DatasetSchemaError(f"{run_id}: evidence_gate.guardrail_status must be present")
        for key in ("gate_uses_expected_fields", "gate_uses_gold_fields", "gate_uses_legacy_fields", "retrieval_loop_triggered"):
            if gate_guardrails.get(key) is not False:
                raise DatasetSchemaError(f"{run_id}: evidence_gate.guardrail_status.{key} must be False")
        if isinstance(semantic_samples, Mapping) and semantic_samples.get("raw_response_payload_written") is not False:
            raise DatasetSchemaError(f"{run_id}: semantic_quality_samples.raw_response_payload_written must be False")
    agentic_planner = summary.get("agentic_planner_dry_run")
    if isinstance(agentic_planner, Mapping):
        validate_agentic_planner_dry_run(run_id, agentic_planner)
    agentic_execute_once = summary.get("agentic_planner_execute_once")
    if isinstance(agentic_execute_once, Mapping):
        validate_agentic_planner_execute_once(run_id, agentic_execute_once)
    xlsx_locator_execute_once = summary.get("xlsx_locator_tool_execute_once")
    if isinstance(xlsx_locator_execute_once, Mapping):
        validate_xlsx_locator_tool_execute_once(run_id, xlsx_locator_execute_once)
    pdf_decomposition = summary.get("pdf_source_native_decomposition")
    if isinstance(pdf_decomposition, Mapping):
        validate_pdf_source_native_decomposition(run_id, pdf_decomposition)
    heuristic_risk_ledger = summary.get("heuristic_risk_ledger")
    if isinstance(heuristic_risk_ledger, Mapping):
        validate_heuristic_risk_ledger(run_id, heuristic_risk_ledger)
    metric_continuity = summary.get("metric_continuity_checkpoint")
    if isinstance(metric_continuity, Mapping):
        if metric_continuity.get("official_metric") is not False:
            raise DatasetSchemaError(f"{run_id}: metric_continuity_checkpoint.official_metric must be False")
        if int(metric_continuity.get("official_metric_input_rows") or 0) != 0:
            raise DatasetSchemaError(f"{run_id}: metric_continuity_checkpoint.official_metric_input_rows must be 0")
        flags = metric_continuity.get("guardrail_mutation_flags")
        if not isinstance(flags, Mapping):
            raise DatasetSchemaError(f"{run_id}: metric_continuity_checkpoint.guardrail_mutation_flags must be present")
        for key, value in flags.items():
            if value is not False:
                raise DatasetSchemaError(f"{run_id}: metric_continuity_checkpoint.guardrail_mutation_flags.{key} must be False")
    agentic_loop_review = summary.get("agentic_loop_review")
    if isinstance(agentic_loop_review, Mapping):
        validate_agentic_loop_review(run_id, agentic_loop_review)


def validate_heuristic_risk_ledger(run_id: str, ledger: Mapping[str, Any]) -> None:
    if ledger.get("official_metric") is not False:
        raise DatasetSchemaError(f"{run_id}: heuristic_risk_ledger.official_metric must be False")
    if int(ledger.get("official_metric_input_rows") or 0) != 0:
        raise DatasetSchemaError(f"{run_id}: heuristic_risk_ledger.official_metric_input_rows must be 0")
    if ledger.get("forbidden_eval_row_shortcut_active") is not False:
        raise DatasetSchemaError(f"{run_id}: heuristic_risk_ledger.forbidden_eval_row_shortcut_active must be False")
    entries = [entry for entry in _as_list(ledger.get("entries")) if isinstance(entry, Mapping)]
    if not entries:
        raise DatasetSchemaError(f"{run_id}: heuristic_risk_ledger.entries must be non-empty")
    for entry in entries:
        rule_id = _clean(entry.get("rule_id")) or "<unnamed>"
        classification = _clean(entry.get("classification"))
        status = _clean(entry.get("status")) or "active"
        if classification not in HEURISTIC_RISK_ALL_CLASSIFICATIONS:
            raise DatasetSchemaError(
                f"{run_id}: heuristic_risk_ledger.{rule_id}.classification unsupported: {classification}"
            )
        if status != "active":
            continue
        if classification == "forbidden_eval_row_shortcut":
            raise DatasetSchemaError(
                f"{run_id}: heuristic_risk_ledger.{rule_id}.forbidden_eval_row_shortcut cannot be active"
            )
        if classification not in HEURISTIC_RISK_ALLOWED_CLASSIFICATIONS:
            raise DatasetSchemaError(
                f"{run_id}: heuristic_risk_ledger.{rule_id}.classification must be allowed for active rules"
            )
        for flag in HEURISTIC_RISK_FORBIDDEN_ACTIVE_FLAGS:
            if entry.get(flag) is not False:
                raise DatasetSchemaError(f"{run_id}: heuristic_risk_ledger.{rule_id}.{flag} must be False")


def _compact_metric(metric: Any) -> dict[str, Any]:
    if not isinstance(metric, Mapping):
        return {"available": False}
    return {
        "tier": metric.get("tier"),
        "numerator": metric.get("numerator"),
        "denominator": metric.get("denominator"),
        "score": metric.get("score"),
        "skipped_count": metric.get("skipped_count"),
        "not_applicable_count": metric.get("not_applicable_count"),
        "diagnostic_only_count": metric.get("diagnostic_only_count"),
    }


def _metrics_subset(metrics: Mapping[str, Any], names: Sequence[str] | None = None) -> dict[str, Any]:
    selected = names or list(metrics)
    return {name: _compact_metric(metrics.get(name)) for name in selected if name in metrics}


def _lookup_metric(summary: Mapping[str, Any], name: str) -> dict[str, Any]:
    for section_name in ("strict_metrics", "provisional_metrics", "inferred_answerable_metrics", "diagnostic_metric_details"):
        section = summary.get(section_name)
        if isinstance(section, Mapping) and isinstance(section.get(name), Mapping):
            metric = dict(section[name])  # type: ignore[index]
            return {
                "available": metric.get("score") is not None,
                "kind": "metric",
                "tier": metric.get("tier") or section_name.replace("_metrics", ""),
                "numerator": metric.get("numerator"),
                "denominator": metric.get("denominator"),
                "score": metric.get("score"),
            }
    diagnostics = summary.get("diagnostic_metrics")
    if isinstance(diagnostics, Mapping) and name in diagnostics:
        value = diagnostics.get(name)
        return {
            "available": isinstance(value, (int, float)),
            "kind": "value",
            "tier": "diagnostic",
            "value": value,
        }
    return {"available": False, "kind": "missing", "tier": _comparison_tier_for_name(name)}


def _comparison_tier_for_name(name: str) -> str:
    if (
        name in {"judged_answer_correctness_provisional", "e2e_rag_success_provisional"}
        or name in RESOLVED_EVIDENCE_COMPARISON_METRICS
        or name.startswith("resolved_evidence_recall@")
    ):
        return "provisional"
    if name.startswith("weak_evidence_match_recall@"):
        return "provisional"
    if (
        name in DIAGNOSTIC_ONLY_COMPARISON_METRICS
        or name in LOWER_IS_BETTER_COMPARISON_METRICS
        or name in EVIDENCE_MAPPING_PACKET_COMPARISON_METRICS
        or name in BACKEND_COMPARISON_METRICS
        or name in SURFACE_COMPARISON_METRICS
    ):
        return "diagnostic"
    return "strict"


def _comparison_numeric_value(record: Mapping[str, Any]) -> float | None:
    if not record.get("available"):
        return None
    if record.get("kind") == "metric":
        value = record.get("score")
    else:
        value = record.get("value")
    return float(value) if isinstance(value, (int, float)) else None


def _format_comparison_value(record: Mapping[str, Any]) -> str:
    if not record.get("available"):
        if record.get("kind") == "metric" and record.get("denominator") == 0:
            return f"{record.get('numerator', 0)}/0 (unavailable)"
        return "unavailable"
    if record.get("kind") == "metric":
        score = record.get("score")
        rendered_score = "" if score is None else f"{float(score):.6f}"
        return f"{record.get('numerator')}/{record.get('denominator')} ({rendered_score})"
    value = record.get("value")
    return f"{float(value):.6f}" if isinstance(value, float) else str(value)


def _comparison_metric_names(current: Mapping[str, Any], previous: Mapping[str, Any]) -> list[str]:
    primary_k = int(current.get("top_k") or previous.get("top_k") or DEFAULT_TOP_K_VALUES[-1])
    names = [
        "judged_answer_correctness_provisional",
        f"weak_evidence_match_recall@{primary_k}",
        "e2e_rag_success_provisional",
        "exact_or_alias_answer_correctness",
        f"evidence_recall@{primary_k}",
        "citation_precision",
        "citation_recall",
        "retrieval_empty_rate",
        "generation_empty_rate",
        "citation_empty_rate",
        "pipeline_error_count",
        "schema_warning_count",
        "gold_missing_count",
        "expected_evidence_id_missing_count",
        "expected_evidence_id_unresolved_count",
        "expected_evidence_id_resolved_candidate_count",
        "expected_evidence_resolution_candidate_count",
        "evidence_mapping_packet_candidate_count",
        "evidence_mapping_packet_likely_accept_count",
        "evidence_mapping_packet_possible_match_count",
        "evidence_mapping_packet_review_needed_count",
        "evidence_mapping_packet_likely_reject_count",
        "source_metadata_resolved_candidate_count",
        "source_metadata_unresolved_candidate_count",
        "resolved_evidence_available_rate",
        f"resolved_evidence_recall@{primary_k}_provisional",
        "citation_matches_resolved_evidence_precision_provisional",
        "citation_matches_resolved_evidence_recall_provisional",
        "e2e_rag_success_resolved_evidence_provisional",
        *sorted(BACKEND_COMPARISON_METRICS),
        *sorted(SURFACE_COMPARISON_METRICS),
        *sorted(DIAGNOSTIC_ONLY_COMPARISON_METRICS),
    ]
    for summary in (current, previous):
        details = summary.get("diagnostic_metric_details")
        if isinstance(details, Mapping):
            for key in details:
                if key not in names:
                    names.append(str(key))
    return names


def _interpret_comparison(name: str, previous: Mapping[str, Any], current: Mapping[str, Any]) -> str:
    if not previous.get("available") and current.get("available"):
        return "new metric" if _comparison_tier_for_name(name) == "provisional" else "unavailable"
    if not previous.get("available") or not current.get("available"):
        return "unavailable"
    if (
        previous.get("kind") == "metric"
        and current.get("kind") == "metric"
        and previous.get("denominator") != current.get("denominator")
    ):
        return "denominator changed"
    if (
        name in DIAGNOSTIC_ONLY_COMPARISON_METRICS
        or name in EVIDENCE_MAPPING_PACKET_COMPARISON_METRICS
        or name in BACKEND_COMPARISON_METRICS
    ):
        return "diagnostic only"
    if name in RESOLVED_EVIDENCE_COMPARISON_METRICS or name.startswith("resolved_evidence_recall@"):
        return "provisional only"
    previous_value = _comparison_numeric_value(previous)
    current_value = _comparison_numeric_value(current)
    if previous_value is None or current_value is None:
        return "unavailable"
    if current_value == previous_value:
        return "unchanged"
    if name in LOWER_IS_BETTER_COMPARISON_METRICS:
        return "improved" if current_value < previous_value else "regressed"
    return "improved" if current_value > previous_value else "regressed"


def build_run_comparison(
    previous_summary: Mapping[str, Any],
    current_summary: Mapping[str, Any],
    *,
    target_label: str = "",
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for name in _comparison_metric_names(current_summary, previous_summary):
        previous = _lookup_metric(previous_summary, name)
        current = _lookup_metric(current_summary, name)
        previous_value = _comparison_numeric_value(previous)
        current_value = _comparison_numeric_value(current)
        delta = None if previous_value is None or current_value is None else round(current_value - previous_value, 6)
        rows.append(
            {
                "metric": name,
                "tier": current.get("tier") or previous.get("tier") or _comparison_tier_for_name(name),
                "previous": _format_comparison_value(previous),
                "current": _format_comparison_value(current),
                "delta": delta,
                "interpretation": _interpret_comparison(name, previous, current),
            }
        )
    return {
        "schema_version": "actual_rag_eval.run_comparison.v1",
        "target": target_label or _clean(previous_summary.get("run_id")) or "previous",
        "target_run_id": previous_summary.get("run_id"),
        "current_run_id": current_summary.get("run_id"),
        "target_generated_at": previous_summary.get("generated_at"),
        "current_generated_at": current_summary.get("generated_at"),
        "interpretation_policy": "nonprod_diagnostic_comparison_only",
        "guardrails": {
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
        "rows": rows,
    }


def _portfolio_comparison_ref(value: str) -> tuple[str, Path]:
    raw = _clean(value)
    if not raw:
        raise DatasetSchemaError("portfolio comparison report reference cannot be empty")
    if "=" in raw:
        label, path_text = raw.split("=", 1)
        label = _clean(label)
        path_text = _clean(path_text)
        if not label:
            raise DatasetSchemaError(f"portfolio comparison report label is empty: {value!r}")
    else:
        path_text = raw
        label = _clean(Path(path_text).parent.name or Path(path_text).stem)
    if not path_text:
        raise DatasetSchemaError(f"portfolio comparison report path is empty: {value!r}")
    return label, Path(path_text)


def _load_portfolio_comparison_reports(report_refs: Sequence[str] | None) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    seen_labels: set[str] = set()
    for ref in report_refs or []:
        label, path = _portfolio_comparison_ref(ref)
        if label in seen_labels:
            raise DatasetSchemaError(f"duplicate portfolio comparison report label: {label}")
        seen_labels.add(label)
        summary = _load_summary_from_pointer_or_path(path)
        validate_actual_rag_guardrails(summary)
        loaded.append(
            {
                "label": label,
                "path": _report_path_value(path),
                "summary": summary,
            }
        )
    return loaded


def _portfolio_report_items(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _query_id(row): dict(row)
        for row in _as_list(summary.get("items"))
        if isinstance(row, Mapping) and _query_id(row)
    }


def _portfolio_answer_preview(row: Mapping[str, Any]) -> dict[str, Any]:
    answer = _clean(row.get("generated_answer"))
    before_gate = _clean(row.get(INTERNAL_PRE_GATE_ANSWER_KEY))
    return {
        "answer_sha256": f"sha256:{_sha256_text(answer)}" if answer else "",
        "answer_preview": _bounded_text_preview(answer, 220),
        "pre_gate_answer_sha256": f"sha256:{_sha256_text(before_gate)}" if before_gate else "",
        "pre_gate_answer_preview": _bounded_text_preview(before_gate, 220),
        "abstained": abstains(answer),
    }


def _portfolio_citation_identity(citation: Mapping[str, Any]) -> str:
    bundle_id = _clean(citation.get("evidence_bundle_id"))
    atom_id = _clean(citation.get("source_atom_id"))
    doc_id = _clean(citation.get("doc_id"))
    chunk_id = _clean(citation.get("chunk_id"))
    text_hash = _clean(citation.get("source_text_sha256") or citation.get("text_sha256")) or _sha256_text(
        citation.get("text")
    )
    if bundle_id:
        return f"evidence_bundle_id:{bundle_id}"
    if atom_id:
        return f"source_atom_id:{atom_id}"
    if doc_id or chunk_id:
        return f"doc_chunk:{doc_id}#{chunk_id}"
    return f"text_sha256:{text_hash}" if text_hash else ""


def _portfolio_citation_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    citations = [dict(citation) for citation in _as_list(row.get("citations")) if isinstance(citation, Mapping)]
    identities = sorted({identity for citation in citations if (identity := _portfolio_citation_identity(citation))})
    composer = row.get("answer_composer") if isinstance(row.get("answer_composer"), Mapping) else {}
    formatted = [str(value) for value in _as_list(composer.get("formatted_citations"))]
    gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
    return {
        "citation_count": len(citations),
        "citation_identity_count": len(identities),
        "citation_identities": identities[:12],
        "citation_identities_truncated": len(identities) > 12,
        "citation_identity_hash": f"sha256:{_sha256_text(json.dumps(identities, ensure_ascii=False, sort_keys=True))}",
        "formatted_citation_count": len(formatted),
        "formatted_citation_preview": [_bounded_text_preview(value, 160) for value in formatted[:4]],
        "formatted_citation_hash": f"sha256:{_sha256_text(json.dumps(formatted, ensure_ascii=False, sort_keys=True))}"
        if formatted
        else "",
        "citation_supported_count": int(gate.get("citation_supported_count") or 0),
        "citation_retrieved_context_only_diagnostic_count": int(
            gate.get("citation_retrieved_context_only_diagnostic_count") or 0
        ),
        "citation_wrong_target_count": int(gate.get("citation_wrong_target_count") or 0),
        "citation_missing_target_count": int(gate.get("citation_missing_target_count") or 0),
        "citation_unsupported_text_count": int(gate.get("citation_unsupported_text_count") or 0),
    }


def _portfolio_gate_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    gate = summary.get("evidence_gate") if isinstance(summary.get("evidence_gate"), Mapping) else {}
    return {
        "evidence_gate_mode": _clean(gate.get("evidence_gate_mode") or summary.get("evidence_gate_mode")),
        "unsupported_answer_rate_before_gate": gate.get("unsupported_answer_rate_before_gate"),
        "unsupported_answer_rate_after_gate": gate.get("unsupported_answer_rate_after_gate"),
        "allowed_answer_count": int(gate.get("allowed_answer_count") or 0),
        "abstained_count": int(gate.get("abstained_count") or 0),
        "unsupported_answer_blocked_count": int(gate.get("unsupported_answer_blocked_count") or 0),
        "would_abstain_count": int(gate.get("would_abstain_count") or 0),
        "would_block_unsupported_answer_count": int(gate.get("would_block_unsupported_answer_count") or 0),
        "sufficient_evidence_package_count": int(gate.get("sufficient_evidence_package_count") or 0),
        "insufficient_evidence_package_count": int(gate.get("insufficient_evidence_package_count") or 0),
        "citation_supported_count": int(gate.get("citation_supported_count") or 0),
        "citation_retrieved_context_only_diagnostic_count": int(
            gate.get("citation_retrieved_context_only_diagnostic_count") or 0
        ),
        "citation_wrong_target_count": int(gate.get("citation_wrong_target_count") or 0),
        "citation_missing_target_count": int(gate.get("citation_missing_target_count") or 0),
        "citation_unsupported_text_count": int(gate.get("citation_unsupported_text_count") or 0),
    }


def _portfolio_selected_evidence_citation_precision(gate: Mapping[str, Any]) -> float | None:
    supported = int(gate.get("citation_supported_count") or 0)
    total = sum(
        int(gate.get(key) or 0)
        for key in (
            "citation_supported_count",
            "citation_retrieved_context_only_diagnostic_count",
            "citation_wrong_target_count",
            "citation_missing_target_count",
            "citation_unsupported_text_count",
        )
    )
    return round(float(supported) / float(total), 6) if total else None


def _portfolio_residual_taxonomy(summary: Mapping[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in _as_list(summary.get("items")):
        if not isinstance(row, Mapping):
            continue
        gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
        decision = _clean(row.get("answer_gate_decision"))
        if decision == "allow_answer":
            counts["allowed"] += 1
            continue
        reason = _clean(gate.get("abstention_reason")) or _clean(gate.get("evidence_package_status")) or decision
        counts[reason or "unknown"] += 1
    return dict(sorted(counts.items()))


def _agentic_planner_closed_guardrail_flags() -> dict[str, bool]:
    return {key: False for key in AGENTIC_PLANNER_GUARDRAIL_FLAGS}


def _agentic_planner_execution_closed() -> dict[str, Any]:
    return {
        "retrieval_executed": False,
        "tool_call_executed": False,
        "llm_retry_executed": False,
        "extra_query_count_executed": 0,
        "tool_call_count_executed": 0,
        "llm_retry_count_executed": 0,
    }


def _agentic_planner_failure_class(row: Mapping[str, Any]) -> str:
    gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
    gate_reason = _clean(gate.get("abstention_reason"))
    gate_status = _clean(gate.get("evidence_package_status"))
    gate_reasons = {
        _clean(reason)
        for key in ("validation_reasons", "abstention_reasons", "unsupported_answer_reasons")
        for reason in _as_list(gate.get(key))
        if _clean(reason)
    }
    source_families = {
        _clean(context.get("source_family")).upper()
        for context in _as_list(row.get("retrieved_contexts"))
        if isinstance(context, Mapping) and _clean(context.get("source_family"))
    }
    source_families.update(
        {
            _clean(citation.get("source_family")).upper()
            for citation in _as_list(row.get("citations"))
            if isinstance(citation, Mapping) and _clean(citation.get("source_family"))
        }
    )
    combined = " ".join(sorted(gate_reasons | {gate_reason, gate_status})).casefold()
    if "collision" in combined or "conflicting_evidence" in combined:
        return "collision"
    if "corpus_absent" in combined or "corpus absent" in combined:
        return "corpus_absent"
    if "PDF" in source_families and gate_status == "insufficient":
        return "tool_required_pdf"
    if source_families.intersection({"XLSX", "XLS", "SPREADSHEET"}) and gate_status == "insufficient":
        return "tool_required_xlsx"
    if "missing_query_anchor" in combined or "missing query anchor" in combined:
        return "missing_query_anchor"
    if gate_status == "insufficient":
        return "insufficient_evidence"
    if bool(gate.get("unsupported_answer_blocked")) or "citation_unsupported" in combined:
        return "unsupported_generation"
    return "no_safe_action"


def _agentic_planner_action_for_failure(failure_class: str) -> str:
    if failure_class == "missing_query_anchor":
        return "query_text_only_reformulation"
    if failure_class == "insufficient_evidence":
        return "source_owned_same_doc_residual"
    if failure_class == "collision":
        return "route_selected_probe"
    if failure_class == "tool_required_pdf":
        return "pdf_locator_tool"
    if failure_class == "tool_required_xlsx":
        return "xlsx_cell_or_table_tool"
    if failure_class == "unsupported_generation":
        return "selected_evidence_llm_rewrite"
    return "deterministic_abstain"


def _agentic_planner_expected_extra_query_count(action: str) -> int:
    return 1 if action in {"query_text_only_reformulation", "source_owned_same_doc_residual", "route_selected_probe"} else 0


def _agentic_planner_expected_tool_call_count(action: str) -> int:
    return 1 if action in {"pdf_locator_tool", "xlsx_cell_or_table_tool"} else 0


def _agentic_planner_expected_llm_retry_count(action: str) -> int:
    return 1 if action == "selected_evidence_llm_rewrite" else 0


def _agentic_planner_expected_memory_lookup_count(action: str) -> int:
    return 1 if action == "run_local_memory_reuse" else 0


def _agentic_planner_forbidden_shortcut_count(decisions: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for decision in decisions:
        if any(key in decision for key in AGENTIC_PLANNER_FORBIDDEN_DECISION_FIELDS):
            count += 1
        if decision.get("uses_query_id_or_row_id_or_target_id") is True:
            count += 1
        if decision.get("uses_expected_answer_or_evidence") is True:
            count += 1
        if decision.get("uses_qrels_or_labels") is True:
            count += 1
    return count


def build_agentic_planner_dry_run_report(summary: Mapping[str, Any], *, mode: str = "off") -> dict[str, Any]:
    normalized_mode = _clean(mode).lower() or "off"
    if normalized_mode not in AGENTIC_PLANNER_MODE_CHOICES:
        raise DatasetSchemaError(f"unsupported agentic planner mode: {mode}")
    gate_snapshot = _portfolio_gate_summary(summary)
    config = summary.get("generator_config") if isinstance(summary.get("generator_config"), Mapping) else {}
    gate = summary.get("evidence_gate") if isinstance(summary.get("evidence_gate"), Mapping) else {}
    base: dict[str, Any] = {
        "schema_version": AGENTIC_PLANNER_DRY_RUN_SCHEMA_VERSION,
        "planner_enabled": normalized_mode == "dry-run",
        "planner_mode": normalized_mode,
        "planner_version": AGENTIC_PLANNER_DRY_RUN_SCHEMA_VERSION,
        "ran_after_selected_evidence_composer": bool(config.get("selected_evidence_composer_invoked")),
        "ran_after_evidence_gate": _clean(gate.get("evidence_gate_mode")) not in {"", "off"},
        "planner_decision_count": 0,
        "planner_action_counts": {},
        "planner_failure_class_counts": {},
        "planner_no_safe_action_count": 0,
        "planner_forbidden_shortcut_detected_count": 0,
        "planner_expected_extra_query_count": 0,
        "planner_expected_tool_call_count": 0,
        "planner_expected_llm_retry_count": 0,
        "planner_expected_memory_lookup_count": 0,
        "planner_heuristic_risk_class": "diagnostic_probe_only",
        "candidate_generation_input_policy": (
            "query_text_and_public_gate_diagnostics_only_no_ids_expected_qrels_labels_baseline_or_legacy_outputs"
        ),
        "retrieved_context_only_citation_policy": "diagnostic_only_never_promoted",
        "report_only_diagnostic": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "planner_execution": _agentic_planner_execution_closed(),
        "guardrail_flags": _agentic_planner_closed_guardrail_flags(),
        "gate_before": gate_snapshot,
        "gate_after_unchanged_because_dry_run": dict(gate_snapshot),
        "decisions": [],
        "execute_once_readiness": {
            "ready": False,
            "assessment": (
                "dry_run_only_not_ready_for_execute_once_until explicit user approval, execution budget, "
                "and unchanged evidence-gate validation are reviewed"
            ),
            "quality_improvement_measured": False,
            "reason": "dry_run_records proposed actions only and cannot demonstrate a quality delta",
        },
        "planner_scope": "failed_rows_after_selected_evidence_composer_and_evidence_gate",
    }
    if normalized_mode == "off":
        return base

    memory_bank = _agentic_planner_run_local_memory_bank(_as_list(summary.get("items")))
    decisions: list[dict[str, Any]] = []
    for item_index, row in enumerate(_as_list(summary.get("items"))):
        if not isinstance(row, Mapping):
            continue
        if _clean(row.get("answer_gate_decision")) == "allow_answer":
            continue
        failure_class = _agentic_planner_failure_class(row)
        action = _agentic_planner_action_for_failure(failure_class)
        if failure_class in {"insufficient_evidence", "missing_query_anchor"} and _agentic_planner_run_local_memory_match(
            row,
            memory_bank,
        ):
            action = "run_local_memory_reuse"
        extra_query_count = _agentic_planner_expected_extra_query_count(action)
        tool_call_count = _agentic_planner_expected_tool_call_count(action)
        llm_retry_count = _agentic_planner_expected_llm_retry_count(action)
        memory_lookup_count = _agentic_planner_expected_memory_lookup_count(action)
        query = _clean(row.get("query"))
        decisions.append(
            {
                "item_index": item_index,
                "query_sha256": f"sha256:{_sha256_text(query)}" if query else "",
                "query_preview": _bounded_text_preview(query, 160),
                "failure_class": failure_class,
                "proposed_action": action,
                "expected_extra_query_count": extra_query_count,
                "expected_tool_call_count": tool_call_count,
                "expected_llm_retry_count": llm_retry_count,
                "expected_memory_lookup_count": memory_lookup_count,
                "executed": False,
                "dry_run_only": True,
                "input_policy": (
                    "query_text_and_public_gate_diagnostics_only_no_ids_expected_qrels_labels_baseline_or_legacy_outputs"
                ),
            }
        )
    action_counts = Counter(_clean(decision.get("proposed_action")) for decision in decisions)
    failure_counts = Counter(_clean(decision.get("failure_class")) for decision in decisions)
    base.update(
        {
            "planner_decision_count": len(decisions),
            "planner_action_counts": dict(sorted(action_counts.items())),
            "planner_failure_class_counts": dict(sorted(failure_counts.items())),
            "planner_no_safe_action_count": int(failure_counts.get("no_safe_action", 0)),
            "planner_forbidden_shortcut_detected_count": _agentic_planner_forbidden_shortcut_count(decisions),
            "planner_expected_extra_query_count": sum(
                int(decision.get("expected_extra_query_count") or 0) for decision in decisions
            ),
            "planner_expected_tool_call_count": sum(
                int(decision.get("expected_tool_call_count") or 0) for decision in decisions
            ),
            "planner_expected_llm_retry_count": sum(
                int(decision.get("expected_llm_retry_count") or 0) for decision in decisions
            ),
            "planner_expected_memory_lookup_count": sum(
                int(decision.get("expected_memory_lookup_count") or 0) for decision in decisions
            ),
            "decisions": decisions,
        }
    )
    if decisions and base["planner_forbidden_shortcut_detected_count"] == 0 and base["planner_no_safe_action_count"] == 0:
        base["execute_once_readiness"] = {
            "ready": False,
            "assessment": (
                "candidate_plan_safe_for_human_review_but_not_ready_for_execute_once_without explicit user approval "
                "and a separate bounded execution checkpoint"
            ),
            "quality_improvement_measured": False,
            "reason": "dry_run preserves the gate and only estimates query/tool/retry budgets",
        }
    return base


def _agentic_planner_execute_once_guardrail_flags() -> dict[str, bool]:
    return {
        "gold_or_qrels_mutation": False,
        "expected_fields_used_for_planner_selection": False,
        "query_id_used_for_planner_selection": False,
        "row_id_used_for_planner_selection": False,
        "target_id_used_for_planner_selection": False,
        "qrels_used_for_planner_selection": False,
        "labels_used_for_planner_selection": False,
        "baseline_topk_or_legacy_outputs_used": False,
        "row_specific_alias_or_shortcut_used": False,
        "unbudgeted_retrieval_executed": False,
        "tool_call_executed": False,
        "llm_retry_executed": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "gate_loosened": False,
        "retrieved_context_only_citation_promoted": False,
        "official_metric": False,
        "production_routing_opened": False,
        "protected_namespace_mutation": False,
    }


def _agentic_planner_execute_once_execution(
    *,
    extra_query_count: int,
    tool_call_count: int = 0,
    llm_retry_count: int = 0,
) -> dict[str, Any]:
    return {
        "retrieval_executed": extra_query_count > 0,
        "tool_call_executed": tool_call_count > 0,
        "llm_retry_executed": llm_retry_count > 0,
        "extra_query_count_executed": max(0, int(extra_query_count)),
        "tool_call_count_executed": max(0, int(tool_call_count)),
        "llm_retry_count_executed": max(0, int(llm_retry_count)),
    }


def _agentic_planner_gate_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, int]:
    keys = (
        "allowed_answer_count",
        "abstained_count",
        "unsupported_answer_blocked_count",
        "sufficient_evidence_package_count",
        "insufficient_evidence_package_count",
        "citation_supported_count",
        "citation_retrieved_context_only_diagnostic_count",
    )
    return {f"{key}_delta": int(after.get(key) or 0) - int(before.get(key) or 0) for key in keys}


def _agentic_planner_sanitized_item_for_retrieval(row: Mapping[str, Any]) -> EvalItem:
    return EvalItem(
        id="",
        query=_clean(row.get("query")),
        answerability="unknown",
        expected_answer="",
        expected_answer_aliases=(),
        expected_evidence=(),
        tags=(),
        notes="",
        has_answerability_label=False,
        validation_warnings=(),
        source_row={},
    )
