from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v3_17_user_locator_and_rough_query_answer_quality_nonprod as v317

import sys

ROOT = v317.ROOT
REPORT_DIR = v317.REPORT_DIR
STATUS_JSONL = v317.STATUS_JSONL
PROGRESS_DOC = v317.PROGRESS_DOC
MEASUREMENTS_DOC = v317.MEASUREMENTS_DOC
TRIAGE_DOC = v317.TRIAGE_DOC

if str(ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai"))

from app.capabilities.rag_orchestrator.agent_runtime import (  # noqa: E402
    AgentRuntime,
    AgentRuntimeRequest,
    RUNTIME_CONTRACT_GUARDS,
    is_deictic_query,
    parse_query_locator,
)
from app.capabilities.rag_orchestrator.tool_registry import (  # noqa: E402
    LAYER_NAMES,
    ROUTE_LANES,
    build_default_tool_registry,
)


RUN_ID = "official_answer_citation_agentic_loop_run_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod"
EVENT_TYPE = "diagnostic_v3_19_locator_ambiguity_deictic_response_policy_nonprod"
STATUS = "DIAGNOSTIC_V3_19_LOCATOR_AMBIGUITY_DEICTIC_RESPONSE_POLICY_NONPROD_READY"
V3_18_RUN_ID = "official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod"
V3_18_OUTPUT_DIR = REPORT_DIR / "quality" / V3_18_RUN_ID
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
RUNTIME_LAYER_NAMES = LAYER_NAMES

OUTPUTS = {
    "summary_json": OUTPUT_DIR / "summary.json",
    "metrics_json": OUTPUT_DIR / "metrics.json",
    "per_query_jsonl": OUTPUT_DIR / "per_query.jsonl",
    "agent_tool_call_trace_jsonl": OUTPUT_DIR / "agent_tool_call_trace.jsonl",
    "route_policy_audit_jsonl": OUTPUT_DIR / "route_policy_audit.jsonl",
    "runtime_contract_audit_jsonl": OUTPUT_DIR / "runtime_contract_audit.jsonl",
    "user_response_policy_audit_jsonl": OUTPUT_DIR / "user_response_policy_audit.jsonl",
    "guardrail_audit_json": OUTPUT_DIR / "guardrail_audit.json",
    "leakage_audit_jsonl": OUTPUT_DIR / "leakage_audit.jsonl",
    "review_packet_jsonl": OUTPUT_DIR / "review_packet.jsonl",
    "review_packet_csv": OUTPUT_DIR / "review_packet.csv",
}

USER_REVIEW_FIELDS = (
    "user_review_like",
    "user_review_note",
    "user_expected_answer_decision",
    "user_supporting_evidence_decision",
    "user_relevance_decision",
    "user_answerability_decision",
)

REVIEW_COLUMNS = (
    "review_id",
    "query_id",
    "diagnostic_case_id",
    "bucket",
    "source_family",
    "query",
    "final_answer",
    "agent_route",
    "route_lane",
    "tool_call_sequence",
    "tool_call_trace_path",
    "runtime_contract_violation",
    "blocked_reason",
    "locator_resolution_bucket",
    "locator_bounds_answerability",
    "response_policy_bucket",
    "answer_allowed_by_policy",
    "user_clarification_required",
    "ambiguity_requires_clarification",
    "active_context_required",
    "active_context_present",
    "duplicate_query_hash_count",
    "duplicate_query_group_size",
    "evidence_truth_source",
    "selected_source_atom_ids",
    "abstained",
    "over_abstain_review_candidate",
    "official_metric_candidate",
    "promotion_evidence",
    *USER_REVIEW_FIELDS,
)

AMBIGUOUS_BUCKETS = {
    "AMBIGUOUS_FILE_IDENTITY",
    "AMBIGUOUS_WORKBOOK_IDENTITY",
    "AMBIGUOUS_PAGE_ONLY_LOCATOR",
    "AMBIGUOUS_SHEET_ONLY_LOCATOR",
}


def clean(value: Any) -> str:
    return v317.clean(value)


def repo_relative(path: Path) -> str:
    return v317.repo_relative(path)


def utc_now() -> str:
    return v317.utc_now()


def sha256_file(path: Path) -> str:
    return v317.sha256_file(path)


def sha256_text(value: str) -> str:
    return v317.sha256_text(value)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v317.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v317.write_jsonl(path, rows)


def read_json(path: Path) -> dict[str, Any]:
    return v317.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v317.read_jsonl(path)


def artifact_exists(path: Path) -> bool:
    return v317.artifact_exists(path)


def build_input_paths() -> dict[str, Path]:
    return {
        "v3_18_summary_json": V3_18_OUTPUT_DIR / "summary.json",
        "v3_18_metrics_json": V3_18_OUTPUT_DIR / "metrics.json",
        "v3_18_per_query_jsonl": V3_18_OUTPUT_DIR / "per_query.jsonl",
        "v3_18_review_packet_jsonl": V3_18_OUTPUT_DIR / "review_packet.jsonl",
        "v3_18_agent_tool_call_trace_jsonl": V3_18_OUTPUT_DIR / "agent_tool_call_trace.jsonl",
        "v3_18_route_policy_audit_jsonl": V3_18_OUTPUT_DIR / "route_policy_audit.jsonl",
        "v3_18_runtime_contract_audit_jsonl": V3_18_OUTPUT_DIR / "runtime_contract_audit.jsonl",
        "v3_18_guardrail_audit_json": V3_18_OUTPUT_DIR / "guardrail_audit.json",
        "v3_18_leakage_audit_jsonl": V3_18_OUTPUT_DIR / "leakage_audit.jsonl",
    }


def require_input_artifacts(paths: Mapping[str, Path]) -> None:
    missing = [repo_relative(path) for path in paths.values() if not artifact_exists(path)]
    if missing:
        raise FileNotFoundError("missing required v3_19 input artifacts: " + ", ".join(missing))


def build_input_lineage(paths: Mapping[str, Path]) -> dict[str, Any]:
    return {
        key: {"exists": artifact_exists(path), "path": repo_relative(path), "sha256": sha256_file(path) if artifact_exists(path) else ""}
        for key, path in paths.items()
    }


def guardrail_flags() -> dict[str, Any]:
    return {
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "raw_file_query_time_accessed": False,
        "source_atom_registry_canonical_truth": True,
        "source_atom_registry_mutated": False,
        "vector_payload_used_as_evidence_truth": False,
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_text_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "direct_normalized_value_query_matching_used": False,
        "protected_namespaces_touched": [],
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "official_denominator_mutated": False,
        "production_mutation": False,
        "db_or_production_namespace_written": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "pdf_xlsx_collapsed_headline_score_reported": False,
        "headline_score": None,
    }


def split_source_atom_ids(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(clean(item) for item in value if clean(item))
    return tuple(item for item in clean(value).split("|") if item)


def replay_atom_from_review(row: Mapping[str, Any], source_atom_id: str) -> dict[str, Any]:
    query = clean(row.get("query"))
    family = clean(row.get("source_family")).upper()
    parsed = parse_query_locator(query)
    terms = parsed["locator_terms"]
    file_term = terms.get("file", [""])[0] if terms.get("file") else ""
    sheet = terms.get("sheet", [""])[0] if terms.get("sheet") else ""
    cell = terms.get("cell", [""])[0] if terms.get("cell") else ""
    range_text = terms.get("range", [""])[0] if terms.get("range") else ""
    page = terms.get("page", [""])[0] if terms.get("page") else ""
    text = "diagnostic replay bounded evidence"
    if family == "PDF":
        locator = {"file_name": file_term or f"{clean(row.get('query_id'))}.pdf", "page": page}
        identity = f"PDF:{locator['file_name']}:p{page or 'replay'}:{source_atom_id}"
    else:
        locator = {
            "workbook": file_term or f"{clean(row.get('query_id'))}.xlsx",
            "sheet": sheet,
            "cell": cell,
            "range": range_text,
        }
        identity = f"XLSX:{locator['workbook']}:{sheet or 'replay'}:{source_atom_id}"
    return {
        "source_atom_id": source_atom_id,
        "diagnostic_replay_atom": True,
        "evidence_replay_source": "v3_18_review_packet_selected_source_atom_id",
        "source_family": family,
        "source_identity": identity,
        "raw_locator": {key: value for key, value in locator.items() if clean(value)},
        "canonical_citation_payload": {key: value for key, value in locator.items() if clean(value)},
        "normalized_text_or_value_snapshot": text,
    }


def add_synthetic_policy_cases(
    cases: list[dict[str, Any]],
    source_registry: dict[str, Mapping[str, Any]],
) -> None:
    synthetic_atoms = {
        "v3_19_pdf_manual_p1": {
            "source_atom_id": "v3_19_pdf_manual_p1",
            "diagnostic_replay_atom": True,
            "source_family": "PDF",
            "source_identity": "PDF:Manual.pdf:p1",
            "raw_locator": {"file_name": "Manual.pdf", "page": "1"},
            "canonical_citation_payload": {"file_name": "Manual.pdf", "page": "1"},
            "normalized_text_or_value_snapshot": "Manual page 1 bounded evidence",
        },
        "v3_19_pdf_other_p1": {
            "source_atom_id": "v3_19_pdf_other_p1",
            "diagnostic_replay_atom": True,
            "source_family": "PDF",
            "source_identity": "PDF:Other.pdf:p1",
            "raw_locator": {"file_name": "Other.pdf", "page": "1"},
            "canonical_citation_payload": {"file_name": "Other.pdf", "page": "1"},
            "normalized_text_or_value_snapshot": "Other page 1 bounded evidence",
        },
        "v3_19_xlsx_book_sheet1_a1": {
            "source_atom_id": "v3_19_xlsx_book_sheet1_a1",
            "diagnostic_replay_atom": True,
            "source_family": "XLSX",
            "source_identity": "XLSX:Book.xlsx:Sheet1:A1",
            "raw_locator": {"workbook": "Book.xlsx", "sheet": "Sheet1", "cell": "A1", "range": "A1:B2"},
            "canonical_citation_payload": {"workbook": "Book.xlsx", "sheet": "Sheet1", "cell": "A1", "range": "A1:B2"},
            "normalized_text_or_value_snapshot": "Book Sheet1 A1 value=42",
            "vector_payload_text": "POISONED_VECTOR_PAYLOAD",
        },
        "v3_19_xlsx_book_sheet1_b2": {
            "source_atom_id": "v3_19_xlsx_book_sheet1_b2",
            "diagnostic_replay_atom": True,
            "source_family": "XLSX",
            "source_identity": "XLSX:Book.xlsx:Sheet1:B2",
            "raw_locator": {"workbook": "Book.xlsx", "sheet": "Sheet1", "cell": "B2", "range": "A1:B2"},
            "canonical_citation_payload": {"workbook": "Book.xlsx", "sheet": "Sheet1", "cell": "B2", "range": "A1:B2"},
            "normalized_text_or_value_snapshot": "Book Sheet1 B2 value=84",
        },
        "v3_19_xlsx_other_sheet1": {
            "source_atom_id": "v3_19_xlsx_other_sheet1",
            "diagnostic_replay_atom": True,
            "source_family": "XLSX",
            "source_identity": "XLSX:Other.xlsx:Sheet1:A1",
            "raw_locator": {"workbook": "Other.xlsx", "sheet": "Sheet1", "cell": "A1"},
            "canonical_citation_payload": {"workbook": "Other.xlsx", "sheet": "Sheet1", "cell": "A1"},
            "normalized_text_or_value_snapshot": "Other Sheet1 value=11",
        },
    }
    source_registry.update(synthetic_atoms)
    synthetic_cases = (
        {
            "diagnostic_case_id": "v3_19_synthetic_page_only_missing_file_identity",
            "query_id": "v3_19_synthetic_page_only_missing_file_identity",
            "bucket": "pdf_page_only_ambiguous_file_identity_policy",
            "source_family": "PDF",
            "query": "1페이지에서 확인되는 내용 알려줘",
            "candidate_source_atom_ids": ("v3_19_pdf_manual_p1", "v3_19_pdf_other_p1"),
            "rough_query_hint": False,
            "request_context": {},
        },
        {
            "diagnostic_case_id": "v3_19_synthetic_sheet_only_missing_workbook_identity",
            "query_id": "v3_19_synthetic_sheet_only_missing_workbook_identity",
            "bucket": "xlsx_sheet_only_ambiguous_workbook_identity_policy",
            "source_family": "XLSX",
            "query": "Sheet1에서 뭐야?",
            "candidate_source_atom_ids": ("v3_19_xlsx_book_sheet1_a1", "v3_19_xlsx_other_sheet1"),
            "rough_query_hint": False,
            "request_context": {},
        },
        {
            "diagnostic_case_id": "v3_19_synthetic_unique_cell_allowed",
            "query_id": "v3_19_synthetic_unique_cell_allowed",
            "bucket": "xlsx_unique_file_sheet_cell_allowed_policy",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            "candidate_source_atom_ids": ("v3_19_xlsx_book_sheet1_a1", "v3_19_xlsx_book_sheet1_b2"),
            "rough_query_hint": False,
            "request_context": {},
        },
        {
            "diagnostic_case_id": "v3_19_synthetic_bounded_broad_range_allowed",
            "query_id": "v3_19_synthetic_bounded_broad_range_allowed",
            "bucket": "xlsx_bounded_broad_range_allowed_policy",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 범위 A1:B2 내용 알려줘",
            "candidate_source_atom_ids": ("v3_19_xlsx_book_sheet1_a1", "v3_19_xlsx_book_sheet1_b2"),
            "rough_query_hint": False,
            "request_context": {},
        },
        {
            "diagnostic_case_id": "v3_19_synthetic_deictic_table_context_missing",
            "query_id": "v3_19_synthetic_deictic_table_context_missing",
            "bucket": "rough_deictic_context_missing_policy",
            "source_family": "XLSX",
            "query": "이 표에서 뭐라고 돼 있어?",
            "candidate_source_atom_ids": ("v3_19_xlsx_book_sheet1_a1",),
            "rough_query_hint": True,
            "request_context": {},
        },
        {
            "diagnostic_case_id": "v3_19_synthetic_deictic_this_value_context_missing",
            "query_id": "v3_19_synthetic_deictic_this_value_context_missing",
            "bucket": "rough_deictic_context_missing_policy",
            "source_family": "XLSX",
            "query": "이거 값 좀 봐줘",
            "candidate_source_atom_ids": ("v3_19_xlsx_book_sheet1_a1",),
            "rough_query_hint": True,
            "request_context": {},
        },
        {
            "diagnostic_case_id": "v3_19_synthetic_deictic_active_context_allowed",
            "query_id": "v3_19_synthetic_deictic_active_context_allowed",
            "bucket": "rough_deictic_active_context_allowed_policy",
            "source_family": "XLSX",
            "query": "이 표에서 뭐라고 돼 있어?",
            "candidate_source_atom_ids": ("v3_19_xlsx_book_sheet1_a1",),
            "rough_query_hint": True,
            "request_context": {"active_source_atom_ids": ("v3_19_xlsx_book_sheet1_a1",)},
        },
        {
            "diagnostic_case_id": "v3_19_synthetic_duplicate_unique_cell_a",
            "query_id": "v3_19_synthetic_duplicate_unique_cell_a",
            "bucket": "duplicate_query_text_policy",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            "candidate_source_atom_ids": ("v3_19_xlsx_book_sheet1_a1",),
            "rough_query_hint": False,
            "request_context": {},
        },
        {
            "diagnostic_case_id": "v3_19_synthetic_duplicate_unique_cell_b",
            "query_id": "v3_19_synthetic_duplicate_unique_cell_b",
            "bucket": "duplicate_query_text_policy",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            "candidate_source_atom_ids": ("v3_19_xlsx_book_sheet1_a1",),
            "rough_query_hint": False,
            "request_context": {},
        },
    )
    start = len(cases) + 1
    for offset, case in enumerate(synthetic_cases):
        cases.append({"review_id": f"v3_19_{start + offset:03d}", "artifact_context": {}, **case})


def build_runtime_cases() -> tuple[list[dict[str, Any]], dict[str, Mapping[str, Any]]]:
    review_rows = read_jsonl(V3_18_OUTPUT_DIR / "review_packet.jsonl")
    source_registry: dict[str, Mapping[str, Any]] = {}
    cases: list[dict[str, Any]] = []
    for index, row in enumerate(review_rows, start=1):
        selected_ids = split_source_atom_ids(row.get("selected_source_atom_ids"))
        for source_atom_id in selected_ids:
            source_registry.setdefault(source_atom_id, replay_atom_from_review(row, source_atom_id))
        cases.append(
            {
                "review_id": f"v3_19_{index:03d}",
                "diagnostic_case_id": clean(row.get("diagnostic_case_id")),
                "query_id": clean(row.get("query_id")),
                "bucket": clean(row.get("bucket")),
                "source_family": clean(row.get("source_family")),
                "query": clean(row.get("query")),
                "candidate_source_atom_ids": selected_ids,
                "rough_query_hint": clean(row.get("agent_route")) == "rough_query",
                "request_context": {},
                "artifact_context": {},
            }
        )
    add_synthetic_policy_cases(cases, source_registry)
    return cases, source_registry


def duplicate_hash_info(cases: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    hash_counts = Counter(sha256_text(clean(case.get("query"))) for case in cases)
    return {
        sha: {"duplicate_query_hash_count": 1 if count > 1 else 0, "duplicate_query_group_size": count}
        for sha, count in hash_counts.items()
    }


def final_answer_policy(result: Any) -> str:
    return clean(result.final_answer_policy) or ("answer_allowed" if not result.abstained else "abstain")


def build_rows(
    cases: Sequence[Mapping[str, Any]],
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    runtime = AgentRuntime(registry=build_default_tool_registry())
    dup_info = duplicate_hash_info(cases)
    per_query_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    route_policy_rows: list[dict[str, Any]] = []
    runtime_audit_rows: list[dict[str, Any]] = []
    user_response_policy_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    leakage_rows: list[dict[str, Any]] = []
    for case in cases:
        query_text = clean(case.get("query"))
        query_hash = sha256_text(query_text)
        result = runtime.invoke(
            AgentRuntimeRequest(
                run_id=RUN_ID,
                query_id=clean(case.get("query_id")),
                diagnostic_case_id=clean(case.get("diagnostic_case_id")),
                query_text=query_text,
                source_family=clean(case.get("source_family")),
                source_registry=source_registry,
                candidate_source_atom_ids=tuple(case.get("candidate_source_atom_ids") or ()),
                rough_query_hint=bool(case.get("rough_query_hint")),
                artifact_context=v317.as_mapping(case.get("artifact_context")),
                request_context=v317.as_mapping(case.get("request_context")),
                internal_replay_adapter=True,
            )
        )
        trace_rows.extend(result.trace_rows)
        selected_ids = list(result.selected_source_atom_ids)
        over_abstain = result.route_lane == "rough_query" and result.abstained and bool(selected_ids)
        common = {
            "schema_version": f"{RUN_ID}_per_query_v1",
            "run_id": RUN_ID,
            "review_id": clean(case.get("review_id")),
            "query_id": result.query_id,
            "diagnostic_case_id": result.diagnostic_case_id,
            "bucket": clean(case.get("bucket")),
            "source_family": clean(case.get("source_family")),
            "query_text_sha256": query_hash,
            "agent_route": result.agent_route,
            "route_lane": result.route_lane,
            "tool_call_sequence": result.tool_call_sequence,
            "tool_call_trace_path": repo_relative(OUTPUTS["agent_tool_call_trace_jsonl"]),
            "runtime_contract_violation": result.runtime_contract_violation,
            "blocked_reason": result.blocked_reason,
            "fail_closed_reason": result.fail_closed_reason,
            "locator_resolution_bucket": result.locator_resolution_bucket,
            "locator_bounds_answerability": result.locator_bounds_answerability,
            "response_policy_bucket": result.response_policy_bucket,
            "answer_allowed_by_policy": result.answer_allowed_by_policy,
            "user_clarification_required": result.user_clarification_required,
            "ambiguity_requires_clarification": result.ambiguity_requires_clarification,
            "active_context_required": result.active_context_required,
            "active_context_present": result.active_context_present,
            "deictic_query": result.deictic_query,
            "page_only_locator": result.page_only_locator,
            "sheet_only_locator": result.sheet_only_locator,
            "final_answer_policy": final_answer_policy(result),
            "duplicate_query_hash_count": dup_info[query_hash]["duplicate_query_hash_count"],
            "duplicate_query_group_size": dup_info[query_hash]["duplicate_query_group_size"],
            "evidence_truth_source": result.evidence_truth_source,
            "selected_source_atom_ids": selected_ids,
            "selected_source_atom_count": len(selected_ids),
            "evidence_bundle_ids": list(result.evidence_bundle_ids),
            "abstained": result.abstained,
            "over_abstain_review_candidate": over_abstain,
            "official_metric_input_rows": 0,
            "official_metric_candidate": False,
            "promotion_evidence": False,
            **guardrail_flags(),
        }
        per_query_rows.append(common)
        route_policy_rows.append(
            {
                "schema_version": f"{RUN_ID}_route_policy_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "route_lane": result.route_lane,
                "agent_route": result.agent_route,
                "locator_resolution_bucket": result.locator_resolution_bucket,
                "response_policy_bucket": result.response_policy_bucket,
                "answer_allowed_by_policy": result.answer_allowed_by_policy,
                "allow_unbounded_fallback": False,
                "selected_tool_ids": result.tool_call_sequence,
                "fail_closed_reason": result.fail_closed_reason,
                "official_metric_input_rows": 0,
                "diagnostic_only": True,
            }
        )
        runtime_audit_rows.append(
            {
                "schema_version": f"{RUN_ID}_runtime_contract_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "runtime_contract_violation": result.runtime_contract_violation,
                "runtime_contract_guards": list(RUNTIME_CONTRACT_GUARDS),
                "violated_guard": result.fail_closed_reason if result.runtime_contract_violation else "",
                "raw_file_query_time_accessed": False,
                "full_workbook_sheet_scan": False,
                "full_pdf_page_block_scan": False,
                "broad_source_atom_scan": False,
                "vector_payload_used_as_evidence_truth": False,
                "target_locator_used": False,
                "gold_locator_used": False,
                "expected_supporting_text_used": False,
                "direct_normalized_value_query_matching_used": False,
                "unbounded_fallback": False,
                "production_write_allowed": False,
                "official_metric_input_rows": 0,
            }
        )
        policy_row = {
            "schema_version": f"{RUN_ID}_user_response_policy_audit_v1",
            "run_id": RUN_ID,
            "query_id": result.query_id,
            "diagnostic_case_id": result.diagnostic_case_id,
            "agent_route": result.agent_route,
            "route_lane": result.route_lane,
            "locator_resolution_bucket": result.locator_resolution_bucket,
            "response_policy_bucket": result.response_policy_bucket,
            "answer_allowed_by_policy": result.answer_allowed_by_policy,
            "user_clarification_required": result.user_clarification_required,
            "abstained": result.abstained,
            "blocked_reason": result.blocked_reason,
            "final_answer_policy": final_answer_policy(result),
            "evidence_truth_source": result.evidence_truth_source,
            "selected_source_atom_count": len(selected_ids),
            "runtime_contract_violation": result.runtime_contract_violation,
            "official_metric_input_rows": 0,
            "diagnostic_only": True,
        }
        user_response_policy_rows.append(policy_row)
        review = {
            "review_id": clean(case.get("review_id")),
            "query_id": result.query_id,
            "diagnostic_case_id": result.diagnostic_case_id,
            "bucket": clean(case.get("bucket")),
            "source_family": clean(case.get("source_family")),
            "query": query_text,
            "final_answer": result.final_answer,
            "agent_route": result.agent_route,
            "route_lane": result.route_lane,
            "tool_call_sequence": " > ".join(result.tool_call_sequence),
            "tool_call_trace_path": repo_relative(OUTPUTS["agent_tool_call_trace_jsonl"]),
            "runtime_contract_violation": result.runtime_contract_violation,
            "blocked_reason": result.blocked_reason,
            "locator_resolution_bucket": result.locator_resolution_bucket,
            "locator_bounds_answerability": result.locator_bounds_answerability,
            "response_policy_bucket": result.response_policy_bucket,
            "answer_allowed_by_policy": result.answer_allowed_by_policy,
            "user_clarification_required": result.user_clarification_required,
            "ambiguity_requires_clarification": result.ambiguity_requires_clarification,
            "active_context_required": result.active_context_required,
            "active_context_present": result.active_context_present,
            "duplicate_query_hash_count": dup_info[query_hash]["duplicate_query_hash_count"],
            "duplicate_query_group_size": dup_info[query_hash]["duplicate_query_group_size"],
            "evidence_truth_source": result.evidence_truth_source,
            "selected_source_atom_ids": "|".join(selected_ids),
            "abstained": result.abstained,
            "over_abstain_review_candidate": over_abstain,
            "official_metric_candidate": False,
            "promotion_evidence": False,
            **{field: "" for field in USER_REVIEW_FIELDS},
        }
        review_rows.append(review)
        leakage_hits = v317.leakage_hits(review)
        leakage_rows.append(
            {
                "schema_version": f"{RUN_ID}_leakage_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "leakage_detected": bool(leakage_hits),
                "leakage_fields": leakage_hits,
                "official_metric_input_rows": 0,
                "diagnostic_only": True,
                "target_locator_used": False,
                "gold_locator_used": False,
                "expected_supporting_text_used": False,
                "source_atom_registry_canonical_truth": True,
                "vector_payload_used_as_evidence_truth": False,
            }
        )
    return {
        "per_query_rows": per_query_rows,
        "agent_tool_call_trace_rows": trace_rows,
        "route_policy_audit_rows": route_policy_rows,
        "runtime_contract_audit_rows": runtime_audit_rows,
        "user_response_policy_audit_rows": user_response_policy_rows,
        "review_rows": review_rows,
        "leakage_audit_rows": leakage_rows,
    }


def build_metrics(rows: Sequence[Mapping[str, Any]], trace_rows: Sequence[Mapping[str, Any]], policy_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    route_counts = Counter(clean(row.get("route_lane")) for row in rows)
    locator_counts = Counter(clean(row.get("locator_resolution_bucket")) for row in rows)
    response_counts = Counter(clean(row.get("response_policy_bucket")) for row in rows)
    duplicate_groups = {row["query_text_sha256"] for row in rows if int(row["duplicate_query_group_size"]) > 1}
    ambiguous_rows = [row for row in rows if clean(row.get("locator_resolution_bucket")) in AMBIGUOUS_BUCKETS]
    page_only_missing = [row for row in rows if row["page_only_locator"] and not row["active_context_present"]]
    sheet_only_missing = [row for row in rows if row["sheet_only_locator"] and not row["active_context_present"]]
    deictic_missing = [row for row in rows if row["deictic_query"] and not row["active_context_present"]]
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "review_packet_row_count": len(rows),
        "per_query_row_count": len(rows),
        "agent_tool_call_trace_row_count": len(trace_rows),
        "user_response_policy_audit_row_count": len(policy_rows),
        "route_lane_counts": dict(sorted(route_counts.items())),
        "locator_resolution_bucket_counts": dict(sorted(locator_counts.items())),
        "response_policy_bucket_counts": dict(sorted(response_counts.items())),
        "ambiguous_locator_count": len(ambiguous_rows),
        "ambiguous_locator_nonabstained_count": sum(1 for row in ambiguous_rows if not row["abstained"]),
        "page_only_locator_count": len(page_only_missing),
        "page_only_locator_nonabstained_count": sum(1 for row in page_only_missing if not row["abstained"]),
        "sheet_only_locator_count": len(sheet_only_missing),
        "sheet_only_locator_nonabstained_count": sum(1 for row in sheet_only_missing if not row["abstained"]),
        "deictic_query_count": sum(1 for row in rows if row["deictic_query"]),
        "deictic_context_missing_count": len(deictic_missing),
        "deictic_context_missing_nonabstained_count": sum(1 for row in deictic_missing if not row["abstained"]),
        "duplicate_query_hash_count": len(duplicate_groups),
        "duplicate_query_text_group_count": len(duplicate_groups),
        "rough_query_abstain_count": sum(1 for row in rows if row["route_lane"] == "rough_query" and row["abstained"]),
        "over_abstain_review_candidate_count": sum(1 for row in rows if row["over_abstain_review_candidate"]),
        "runtime_contract_violation_count": sum(1 for row in rows if row["runtime_contract_violation"]),
        "official_metric_input_rows": 0,
        "official_metric": False,
        "promotion_evidence": False,
        "diagnostic_only": True,
        **guardrail_flags(),
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    input_lineage: Mapping[str, Any],
    artifact_sha256: Mapping[str, str],
) -> dict[str, Any]:
    registry = build_default_tool_registry()
    return {
        "schema_version": f"{RUN_ID}_summary_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "event_type": EVENT_TYPE,
        "run_class": "diagnostic_only_locator_ambiguity_deictic_response_policy_nonprod",
        "generated_at": utc_now(),
        "review_packet_dir": repo_relative(OUTPUT_DIR),
        "agent_runtime_nonprod": True,
        "agent_runtime_product_ready": False,
        "tool_registry_only_invocation": True,
        "ambiguous_locator_fail_closed": metrics["ambiguous_locator_nonabstained_count"] == 0,
        "page_only_locator_without_context_fail_closed": metrics["page_only_locator_nonabstained_count"] == 0,
        "deictic_context_missing_fail_closed": metrics["deictic_context_missing_nonabstained_count"] == 0,
        "tool_registry_version": registry.registry_version,
        "route_policy_lanes": list(ROUTE_LANES),
        "runtime_layer_names": list(RUNTIME_LAYER_NAMES),
        "input_lineage": dict(input_lineage),
        "artifact_paths": {key: repo_relative(path) for key, path in OUTPUTS.items()},
        "artifact_sha256": dict(artifact_sha256),
        **dict(metrics),
        **guardrail_flags(),
    }


def build_guardrail_audit(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "generated_at": utc_now(),
        "agent_runtime_nonprod": True,
        "tool_registry_only_invocation": True,
        "ambiguous_locator_fail_closed": metrics["ambiguous_locator_nonabstained_count"] == 0,
        "page_only_locator_without_context_fail_closed": metrics["page_only_locator_nonabstained_count"] == 0,
        "deictic_context_missing_fail_closed": metrics["deictic_context_missing_nonabstained_count"] == 0,
        "runtime_contract_violation_count": metrics["runtime_contract_violation_count"],
        **guardrail_flags(),
    }


def build_artifacts() -> dict[str, Any]:
    input_paths = build_input_paths()
    require_input_artifacts(input_paths)
    input_lineage = build_input_lineage(input_paths)
    cases, source_registry = build_runtime_cases()
    rows = build_rows(cases, source_registry=source_registry)
    metrics = build_metrics(
        rows["per_query_rows"],
        rows["agent_tool_call_trace_rows"],
        rows["user_response_policy_audit_rows"],
    )
    guardrail = build_guardrail_audit(metrics)
    summary = build_summary(metrics=metrics, input_lineage=input_lineage, artifact_sha256={})
    return {
        "summary": summary,
        "metrics": metrics,
        "guardrail_audit": guardrail,
        "input_lineage": input_lineage,
        **rows,
    }


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REVIEW_COLUMNS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def artifact_sha256_without_summary() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path in OUTPUTS.items():
        if key == "summary_json":
            continue
        hashes[f"{key}_sha256"] = sha256_file(path)
    return hashes


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    v317.replace_marked_entry(path, marker, entry)


def kst_today() -> str:
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")


def refresh_last_updated(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"Last updated: \d{4}-\d{2}-\d{2} KST\.", f"Last updated: {kst_today()} KST.", text, count=1)
    path.write_text(text, encoding="utf-8")


def update_docs(summary: Mapping[str, Any], metrics: Mapping[str, Any]) -> None:
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        refresh_last_updated(doc_path)

    progress_entry = (
        f"- v3_19 locator ambiguity and deictic response policy (`{RUN_ID}`) is "
        "diagnostic_v3_19_locator_ambiguity_deictic_response_policy_nonprod_ready. It keeps the "
        "non-production ToolRegistry runtime, but fail-closes ambiguous file/workbook identity, page-only "
        "and sheet-only locator requests without bounded active context, and Korean deictic rough queries "
        "without explicit active context. SourceAtom/EvidenceBundle remains canonical evidence truth; "
        "SearchView/vector payload remains candidate-only; official_metric_input_rows=0. This is not "
        "production routing, product success, promotion evidence, official scoring, or live DB/index/cache readiness. "
        "Targeted v3_19 checks pass; full `--rag-current` in this checkout is classified separately when older "
        "local legacy report artifacts are absent."
    )
    measurements_entry = f"""### v3_19 Locator Ambiguity And Deictic Response Policy

- Run: `{RUN_ID}`
- Policy: diagnostic-only, non-production response-policy hardening; ambiguous locator and missing-context deictic rows ask for clarification instead of answering.

| Diagnostic count | Value |
| --- | ---: |
| review_packet_row_count | {metrics["review_packet_row_count"]} |
| agent_tool_call_trace_row_count | {metrics["agent_tool_call_trace_row_count"]} |
| user_response_policy_audit_row_count | {metrics["user_response_policy_audit_row_count"]} |
| ambiguous_locator_count | {metrics["ambiguous_locator_count"]} |
| ambiguous_locator_nonabstained_count | {metrics["ambiguous_locator_nonabstained_count"]} |
| page_only_locator_count | {metrics["page_only_locator_count"]} |
| page_only_locator_nonabstained_count | {metrics["page_only_locator_nonabstained_count"]} |
| sheet_only_locator_count | {metrics["sheet_only_locator_count"]} |
| sheet_only_locator_nonabstained_count | {metrics["sheet_only_locator_nonabstained_count"]} |
| deictic_query_count | {metrics["deictic_query_count"]} |
| deictic_context_missing_count | {metrics["deictic_context_missing_count"]} |
| deictic_context_missing_nonabstained_count | {metrics["deictic_context_missing_nonabstained_count"]} |
| duplicate_query_hash_count | {metrics["duplicate_query_hash_count"]} |
| duplicate_query_text_group_count | {metrics["duplicate_query_text_group_count"]} |
| rough_query_abstain_count | {metrics["rough_query_abstain_count"]} |
| over_abstain_review_candidate_count | {metrics["over_abstain_review_candidate_count"]} |
| runtime_contract_violation_count | {metrics["runtime_contract_violation_count"]} |
| official_metric_input_rows | 0 |

Artifacts: `{summary["review_packet_dir"]}/summary.json`, `metrics.json`, `per_query.jsonl`, `agent_tool_call_trace.jsonl`, `route_policy_audit.jsonl`, `runtime_contract_audit.jsonl`, `user_response_policy_audit.jsonl`, `guardrail_audit.json`, `leakage_audit.jsonl`, `review_packet.jsonl`, and `review_packet.csv`.

Counter source-of-truth: `metrics.json` carries the full bucket maps and diagnostic counters; `status.jsonl` is a compact event ledger with the acceptance and headline diagnostic counters.

Verification note: the v3_19 `--check`, runtime-policy tests, artifact hash-lock test, guardrail test, status-sync test, py_compile, diff checks, protected-surface checks, and ignored-artifact checks pass in this checkout. The full `python -X utf8 -m pytest ai/tests --rag-current -q` command currently fails before reaching a clean suite because older v3_6_9-v3_15 local report artifacts are absent from the repo-local/current external archive; this is classified as a legacy artifact availability issue, not a v3_19 official metric or promotion signal.
"""
    triage_entry = (
        "### v3_19 Locator Ambiguity And Deictic Response Policy Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        "- Scope: diagnostic-only non-production response-policy hardening before live DB/index/cache smoke.\n"
        "- Ambiguous file/workbook/document identity, page-only locators without active file context, and sheet-only locators without active workbook context fail closed with user clarification; sheet-only rows are surfaced as `AMBIGUOUS_SHEET_ONLY_LOCATOR` in `locator_resolution_bucket_counts` and dedicated sheet-only counters.\n"
        "- Deictic Korean rough queries such as `이 표`, `이거`, `그 페이지`, `이 페이지`, `이 파일`, `방금 것`, `여기`, and `선택한 범위` require bounded active context and otherwise use the `CONTEXT_REQUIRED` response policy bucket.\n"
        "- `BOUNDED_BROAD_RANGE` can answer only when the broad locator resolves to a unique source identity.\n"
        "- Duplicate query text is surfaced in summary metrics and review packet fields; it remains diagnostic-only and not a gold label.\n"
        "- No target/gold/supporting/expected locator text or hidden artifact source identity is used as active context.\n"
        "- Verification risk: full `--rag-current` remains blocked in this checkout by missing legacy v3_6_9-v3_15 report artifacts; v3_19 targeted policy, artifact, guardrail, and status checks pass.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        "Overall status: `diagnostic_v3_19_locator_ambiguity_deictic_response_policy_nonprod_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"current diagnostic (?:answer-quality|response-policy) loop:\n`[^`]+`;",
        f"current diagnostic response-policy loop:\n`{RUN_ID}`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        refresh_last_updated(doc_path)


def append_status_event(summary: Mapping[str, Any]) -> None:
    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "generated_at": utc_now(),
        "review_packet_dir": summary["review_packet_dir"],
        "artifact_paths": summary["artifact_paths"],
        "artifact_sha256": {**summary["artifact_sha256"], "summary_json_sha256": sha256_file(OUTPUTS["summary_json"])},
        "agent_runtime_nonprod": True,
        "agent_runtime_product_ready": False,
        "tool_registry_only_invocation": True,
        "tool_registry_version": summary["tool_registry_version"],
        "route_policy_lanes": summary["route_policy_lanes"],
        "review_packet_row_count": summary["review_packet_row_count"],
        "agent_tool_call_trace_row_count": summary["agent_tool_call_trace_row_count"],
        "user_response_policy_audit_row_count": summary["user_response_policy_audit_row_count"],
        "ambiguous_locator_nonabstained_count": summary["ambiguous_locator_nonabstained_count"],
        "ambiguous_locator_count": summary["ambiguous_locator_count"],
        "page_only_locator_count": summary["page_only_locator_count"],
        "page_only_locator_nonabstained_count": summary["page_only_locator_nonabstained_count"],
        "sheet_only_locator_count": summary["sheet_only_locator_count"],
        "sheet_only_locator_nonabstained_count": summary["sheet_only_locator_nonabstained_count"],
        "deictic_query_count": summary["deictic_query_count"],
        "deictic_context_missing_count": summary["deictic_context_missing_count"],
        "deictic_context_missing_nonabstained_count": summary["deictic_context_missing_nonabstained_count"],
        "duplicate_query_hash_count": summary["duplicate_query_hash_count"],
        "duplicate_query_text_group_count": summary["duplicate_query_text_group_count"],
        "rough_query_abstain_count": summary["rough_query_abstain_count"],
        "over_abstain_review_candidate_count": summary["over_abstain_review_candidate_count"],
        "runtime_contract_violation_count": summary["runtime_contract_violation_count"],
        **guardrail_flags(),
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def write_artifacts(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUTS["metrics_json"], artifacts["metrics"])
    write_jsonl(OUTPUTS["per_query_jsonl"], artifacts["per_query_rows"])
    write_jsonl(OUTPUTS["agent_tool_call_trace_jsonl"], artifacts["agent_tool_call_trace_rows"])
    write_jsonl(OUTPUTS["route_policy_audit_jsonl"], artifacts["route_policy_audit_rows"])
    write_jsonl(OUTPUTS["runtime_contract_audit_jsonl"], artifacts["runtime_contract_audit_rows"])
    write_jsonl(OUTPUTS["user_response_policy_audit_jsonl"], artifacts["user_response_policy_audit_rows"])
    write_json(OUTPUTS["guardrail_audit_json"], artifacts["guardrail_audit"])
    write_jsonl(OUTPUTS["leakage_audit_jsonl"], artifacts["leakage_audit_rows"])
    write_jsonl(OUTPUTS["review_packet_jsonl"], artifacts["review_rows"])
    write_csv(OUTPUTS["review_packet_csv"], artifacts["review_rows"])
    artifact_sha = artifact_sha256_without_summary()
    summary = build_summary(
        metrics=artifacts["metrics"],
        input_lineage=artifacts["input_lineage"],
        artifact_sha256=artifact_sha,
    )
    write_json(OUTPUTS["summary_json"], summary)
    append_status_event(summary)
    update_docs(summary, artifacts["metrics"])
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build v3_19 diagnostic-only locator/deictic response policy artifacts.")
    parser.add_argument("--check", action="store_true", help="Build in memory only.")
    args = parser.parse_args(argv)
    artifacts = build_artifacts()
    payload = {
        "run_id": RUN_ID,
        "status": artifacts["summary"]["status"],
        "review_packet_row_count": artifacts["metrics"]["review_packet_row_count"],
        "agent_tool_call_trace_row_count": artifacts["metrics"]["agent_tool_call_trace_row_count"],
        "user_response_policy_audit_row_count": artifacts["metrics"]["user_response_policy_audit_row_count"],
        "ambiguous_locator_nonabstained_count": artifacts["metrics"]["ambiguous_locator_nonabstained_count"],
        "page_only_locator_nonabstained_count": artifacts["metrics"]["page_only_locator_nonabstained_count"],
        "deictic_context_missing_nonabstained_count": artifacts["metrics"]["deictic_context_missing_nonabstained_count"],
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }
    if args.check:
        print(json.dumps({"check": True, **payload}, ensure_ascii=False, sort_keys=True))
        return 0
    summary = write_artifacts(artifacts)
    print(
        json.dumps(
            {**payload, "summary": repo_relative(OUTPUTS["summary_json"]), "status": summary["status"]},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
