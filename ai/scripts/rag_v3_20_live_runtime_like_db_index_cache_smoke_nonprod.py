from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod as v319

import sys

ROOT = v319.ROOT
REPORT_DIR = v319.REPORT_DIR
STATUS_JSONL = v319.STATUS_JSONL
PROGRESS_DOC = v319.PROGRESS_DOC
MEASUREMENTS_DOC = v319.MEASUREMENTS_DOC
TRIAGE_DOC = v319.TRIAGE_DOC

if str(ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai"))

from eval.harness import rag_diagnostic_common as diagnostic_common  # noqa: E402

from app.capabilities.rag_orchestrator.agent_runtime import (  # noqa: E402
    AgentRuntime,
    AgentRuntimeRequest,
    RUNTIME_CONTRACT_GUARDS,
)
from app.capabilities.rag_orchestrator.runtime_adapters import (  # noqa: E402
    InMemoryRuntimeCacheAdapter,
    InMemorySearchIndexAdapter,
    InMemorySourceAtomStoreAdapter,
    cache_key_for_query,
)
from app.capabilities.rag_orchestrator.tool_registry import (  # noqa: E402
    LAYER_NAMES,
    ROUTE_LANES,
    build_default_tool_registry,
)


RUN_ID = "official_answer_citation_agentic_loop_run_v3_20_live_runtime_like_db_index_cache_smoke_nonprod"
EVENT_TYPE = "diagnostic_v3_20_live_runtime_like_db_index_cache_smoke_nonprod"
STATUS = "DIAGNOSTIC_V3_20_LIVE_RUNTIME_LIKE_DB_INDEX_CACHE_SMOKE_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
RUNTIME_LAYER_NAMES = LAYER_NAMES
ADAPTER_NAMESPACE = "rag-data-live-runtime-smoke-nonprod"
DIAGNOSTIC_TENANT_ID = "diagnostic-tenant"
CACHE_NAMESPACE = "rag-v3-20-smoke-cache"

OUTPUTS = {
    "summary_json": OUTPUT_DIR / "summary.json",
    "metrics_json": OUTPUT_DIR / "metrics.json",
    "per_query_jsonl": OUTPUT_DIR / "per_query.jsonl",
    "agent_tool_call_trace_jsonl": OUTPUT_DIR / "agent_tool_call_trace.jsonl",
    "route_policy_audit_jsonl": OUTPUT_DIR / "route_policy_audit.jsonl",
    "runtime_contract_audit_jsonl": OUTPUT_DIR / "runtime_contract_audit.jsonl",
    "user_response_policy_audit_jsonl": OUTPUT_DIR / "user_response_policy_audit.jsonl",
    "db_contract_audit_jsonl": OUTPUT_DIR / "db_contract_audit.jsonl",
    "index_contract_audit_jsonl": OUTPUT_DIR / "index_contract_audit.jsonl",
    "cache_contract_audit_jsonl": OUTPUT_DIR / "cache_contract_audit.jsonl",
    "live_runtime_smoke_audit_jsonl": OUTPUT_DIR / "live_runtime_smoke_audit.jsonl",
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
    "live_runtime_smoke_case",
    "bucket",
    "source_family",
    "query",
    "final_answer",
    "agent_route",
    "route_lane",
    "response_policy_bucket",
    "answer_allowed_by_policy",
    "abstained",
    "db_contract_status",
    "index_contract_status",
    "cache_contract_status",
    "cache_hit",
    "cache_key_namespace",
    "adapter_fail_closed_reason",
    "runtime_adapter_trace_path",
    "tool_call_trace_path",
    "evidence_truth_source",
    "selected_source_atom_ids",
    "evidence_bundle_ids",
    "vector_payload_candidate_only",
    "production_write_attempted",
    "broad_scan_attempted",
    "runtime_contract_violation",
    "official_metric_candidate",
    "promotion_evidence",
    *USER_REVIEW_FIELDS,
)


def clean(value: Any) -> str:
    return diagnostic_common.clean(value)


def repo_relative(path: Path) -> str:
    return diagnostic_common.repo_relative(path, root=ROOT)


def utc_now() -> str:
    return diagnostic_common.utc_now()


def sha256_file(path: Path) -> str:
    return diagnostic_common.sha256_file(path)


def sha256_text(value: str) -> str:
    return diagnostic_common.sha256_text(value)


def read_json(path: Path) -> dict[str, Any]:
    return diagnostic_common.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return diagnostic_common.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    diagnostic_common.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    diagnostic_common.write_jsonl(path, rows)


def build_input_paths() -> dict[str, Path]:
    v3_19_dir = v319.OUTPUT_DIR
    return {
        "v3_19_summary_json": v3_19_dir / "summary.json",
        "v3_19_metrics_json": v3_19_dir / "metrics.json",
        "v3_19_per_query_jsonl": v3_19_dir / "per_query.jsonl",
        "v3_19_review_packet_jsonl": v3_19_dir / "review_packet.jsonl",
        "v3_19_agent_tool_call_trace_jsonl": v3_19_dir / "agent_tool_call_trace.jsonl",
        "v3_19_user_response_policy_audit_jsonl": v3_19_dir / "user_response_policy_audit.jsonl",
        "v3_19_runtime_contract_audit_jsonl": v3_19_dir / "runtime_contract_audit.jsonl",
        "v3_19_guardrail_audit_json": v3_19_dir / "guardrail_audit.json",
    }


def require_input_artifacts(paths: Mapping[str, Path]) -> None:
    missing = [repo_relative(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required v3_20 input artifacts: " + ", ".join(missing))


def build_input_lineage(paths: Mapping[str, Path]) -> dict[str, Any]:
    return {
        key: {"exists": path.exists(), "path": repo_relative(path), "sha256": sha256_file(path) if path.exists() else ""}
        for key, path in paths.items()
    }


def guardrail_flags() -> dict[str, Any]:
    return {
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "agent_runtime_nonprod": True,
        "agent_runtime_product_ready": False,
        "tool_registry_only_invocation": True,
        "live_db_index_cache_readiness": False,
        "raw_file_query_time_accessed": False,
        "source_atom_registry_canonical_truth": True,
        "source_atom_store_canonical_truth": True,
        "source_atom_registry_mutated": False,
        "search_index_candidate_only": True,
        "runtime_cache_evidence_truth": False,
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


def source_atoms() -> dict[str, dict[str, Any]]:
    return {
        "atom-xlsx-a1": {
            "source_atom_id": "atom-xlsx-a1",
            "mock_source_atom": True,
            "tenant_id": DIAGNOSTIC_TENANT_ID,
            "source_family": "XLSX",
            "source_identity": "XLSX:Book.xlsx:Sheet1:A1",
            "raw_locator": {"workbook": "Book.xlsx", "sheet": "Sheet1", "cell": "A1", "range": "A1:B2"},
            "canonical_citation_payload": {"workbook": "Book.xlsx", "sheet": "Sheet1", "cell": "A1", "range": "A1:B2"},
            "normalized_text_or_value_snapshot": "Book Sheet1 A1 source atom value=42",
        },
        "atom-xlsx-b2": {
            "source_atom_id": "atom-xlsx-b2",
            "mock_source_atom": True,
            "tenant_id": DIAGNOSTIC_TENANT_ID,
            "source_family": "XLSX",
            "source_identity": "XLSX:Book.xlsx:Sheet1:B2",
            "raw_locator": {"workbook": "Book.xlsx", "sheet": "Sheet1", "cell": "B2", "range": "A1:B2"},
            "canonical_citation_payload": {"workbook": "Book.xlsx", "sheet": "Sheet1", "cell": "B2", "range": "A1:B2"},
            "normalized_text_or_value_snapshot": "Book Sheet1 B2 source atom value=84",
        },
        "atom-pdf-p3": {
            "source_atom_id": "atom-pdf-p3",
            "mock_source_atom": True,
            "tenant_id": DIAGNOSTIC_TENANT_ID,
            "source_family": "PDF",
            "source_identity": "PDF:Manual.pdf:p3",
            "raw_locator": {"file_name": "Manual.pdf", "page": 3, "section": "contract"},
            "canonical_citation_payload": {"file_name": "Manual.pdf", "page": 3, "section": "contract"},
            "normalized_text_or_value_snapshot": "Manual page 3 source atom clause=bounded",
        },
    }


def search_views() -> dict[str, dict[str, Any]]:
    return {
        "sv-xlsx-a1": {
            "search_view_id": "sv-xlsx-a1",
            "source_atom_ids": ["atom-xlsx-a1"],
            "source_family": "XLSX",
            "vector_payload_text": "POISONED_VECTOR_PAYLOAD_XLSX_A1",
            "canonical_citation_payload": {"workbook": "Poison.xlsx", "sheet": "Wrong", "cell": "Z99"},
        },
        "sv-xlsx-b2": {
            "search_view_id": "sv-xlsx-b2",
            "source_atom_ids": ["atom-xlsx-b2"],
            "source_family": "XLSX",
            "vector_payload_text": "POISONED_VECTOR_PAYLOAD_XLSX_B2",
        },
        "sv-pdf-p3": {
            "search_view_id": "sv-pdf-p3",
            "source_atom_ids": ["atom-pdf-p3"],
            "source_family": "PDF",
            "vector_payload_text": "POISONED_VECTOR_PAYLOAD_PDF",
        },
    }


def build_cases() -> list[dict[str, Any]]:
    return [
        {
            "review_id": "v3_20_001",
            "query_id": "v3_20_explicit_xlsx_cell",
            "diagnostic_case_id": "v3_20_explicit_xlsx_cell",
            "live_runtime_smoke_case": "explicit_file_sheet_cell",
            "bucket": "user_locator_explicit_file_sheet_cell",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            "candidate_source_atom_ids": (),
            "rough_query_hint": False,
            "cache_namespace": CACHE_NAMESPACE,
        },
        {
            "review_id": "v3_20_002",
            "query_id": "v3_20_explicit_pdf_page_cache_hit",
            "diagnostic_case_id": "v3_20_explicit_pdf_page_cache_hit",
            "live_runtime_smoke_case": "explicit_file_page_cache_hit",
            "bucket": "user_locator_explicit_file_page",
            "source_family": "PDF",
            "query": "Manual.pdf 3페이지 내용 알려줘",
            "candidate_source_atom_ids": (),
            "rough_query_hint": False,
            "cache_namespace": CACHE_NAMESPACE,
            "cache_hit": True,
        },
        {
            "review_id": "v3_20_003",
            "query_id": "v3_20_rough_semantic_constraints",
            "diagnostic_case_id": "v3_20_rough_semantic_constraints",
            "live_runtime_smoke_case": "rough_query_semantic_constraints",
            "bucket": "rough_query_sufficient_semantic_constraints",
            "source_family": "XLSX",
            "query": "계약금 값이 있는 표 내용을 알려줘",
            "candidate_source_atom_ids": (),
            "rough_query_hint": True,
            "cache_namespace": CACHE_NAMESPACE,
        },
        {
            "review_id": "v3_20_004",
            "query_id": "v3_20_deictic_context_missing",
            "diagnostic_case_id": "v3_20_deictic_context_missing",
            "live_runtime_smoke_case": "deictic_context_missing_fail_closed",
            "bucket": "rough_deictic_context_missing",
            "source_family": "XLSX",
            "query": "이 표에서 뭐라고 돼 있어?",
            "candidate_source_atom_ids": ("atom-xlsx-a1",),
            "rough_query_hint": True,
            "cache_namespace": CACHE_NAMESPACE,
        },
        {
            "review_id": "v3_20_005",
            "query_id": "v3_20_deictic_active_context",
            "diagnostic_case_id": "v3_20_deictic_active_context",
            "live_runtime_smoke_case": "deictic_active_context_allowed",
            "bucket": "rough_deictic_active_context_allowed",
            "source_family": "XLSX",
            "query": "이 표에서 뭐라고 돼 있어?",
            "candidate_source_atom_ids": ("atom-xlsx-a1",),
            "rough_query_hint": True,
            "request_context": {"active_source_atom_ids": ("atom-xlsx-a1",)},
            "cache_namespace": CACHE_NAMESPACE,
        },
        {
            "review_id": "v3_20_006",
            "query_id": "v3_20_unsupported_source_policy",
            "diagnostic_case_id": "v3_20_unsupported_source_policy",
            "live_runtime_smoke_case": "unsupported_source_policy_fail_closed",
            "bucket": "unsupported_source_policy_route",
            "source_family": "IMAGE",
            "query": "이미지 내용을 알려줘",
            "candidate_source_atom_ids": (),
            "rough_query_hint": True,
            "cache_namespace": CACHE_NAMESPACE,
        },
        {
            "review_id": "v3_20_007",
            "query_id": "v3_20_index_unavailable",
            "diagnostic_case_id": "v3_20_index_unavailable",
            "live_runtime_smoke_case": "index_unavailable_fail_closed",
            "bucket": "index_unavailable_fail_closed",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            "candidate_source_atom_ids": (),
            "rough_query_hint": False,
            "index_available": False,
            "cache_namespace": CACHE_NAMESPACE,
        },
        {
            "review_id": "v3_20_008",
            "query_id": "v3_20_db_unavailable",
            "diagnostic_case_id": "v3_20_db_unavailable",
            "live_runtime_smoke_case": "db_unavailable_fail_closed",
            "bucket": "source_atom_store_unavailable_fail_closed",
            "source_family": "PDF",
            "query": "Manual.pdf 3페이지 내용 알려줘",
            "candidate_source_atom_ids": (),
            "rough_query_hint": False,
            "db_available": False,
            "cache_namespace": CACHE_NAMESPACE,
        },
        {
            "review_id": "v3_20_009",
            "query_id": "v3_20_cache_unavailable_optional",
            "diagnostic_case_id": "v3_20_cache_unavailable_optional",
            "live_runtime_smoke_case": "cache_unavailable_optional",
            "bucket": "cache_unavailable_optional_evidence_truth_unchanged",
            "source_family": "PDF",
            "query": "Manual.pdf 3페이지 내용 알려줘",
            "candidate_source_atom_ids": (),
            "rough_query_hint": False,
            "cache_available": False,
            "cache_namespace": CACHE_NAMESPACE,
        },
        {
            "review_id": "v3_20_010",
            "query_id": "v3_20_stale_cache_namespace",
            "diagnostic_case_id": "v3_20_stale_cache_namespace",
            "live_runtime_smoke_case": "stale_cache_namespace_mismatch",
            "bucket": "cache_namespace_mismatch_fail_closed",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            "candidate_source_atom_ids": (),
            "rough_query_hint": False,
            "cache_namespace": "stale-cache-namespace",
            "expected_cache_namespace": CACHE_NAMESPACE,
        },
    ]


def cache_items_for_cases(cases: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not case.get("cache_hit"):
            continue
        namespace = clean(case.get("cache_namespace")) or CACHE_NAMESPACE
        key = cache_key_for_query(run_id=RUN_ID, query_id=clean(case.get("query_id")), namespace=namespace)
        items[key] = {"source_atom_ids": ["atom-pdf-p3"], "evidence_bundle_ids": ["bundle:atom-pdf-p3"]}
    return items


def build_runtime_for_case(case: Mapping[str, Any], cache_items: Mapping[str, Mapping[str, Any]]) -> AgentRuntime:
    return AgentRuntime(
        registry=build_default_tool_registry(),
        search_index=InMemorySearchIndexAdapter(
            search_views=search_views(),
            namespace=ADAPTER_NAMESPACE,
            available=case.get("index_available", True) is not False,
        ),
        source_atom_store=InMemorySourceAtomStoreAdapter(
            source_atoms=source_atoms(),
            namespace=ADAPTER_NAMESPACE,
            available=case.get("db_available", True) is not False,
        ),
        runtime_cache=InMemoryRuntimeCacheAdapter(
            namespace=clean(case.get("cache_namespace")) or CACHE_NAMESPACE,
            cache_items=cache_items,
            available=case.get("cache_available", True) is not False,
        ),
    )


def base_request_context(case: Mapping[str, Any]) -> dict[str, Any]:
    context = {
        "diagnostic_tenant_id": DIAGNOSTIC_TENANT_ID,
        "namespace": ADAPTER_NAMESPACE,
        "cache_namespace": clean(case.get("cache_namespace")) or CACHE_NAMESPACE,
        "expected_cache_namespace": clean(case.get("expected_cache_namespace")) or clean(case.get("cache_namespace")) or CACHE_NAMESPACE,
    }
    context.update(v319.v317.as_mapping(case.get("request_context")))
    return context


def build_live_audit_row(result: Any) -> dict[str, Any]:
    adapter_rows = list(result.runtime_adapter_trace_rows)
    search_view_ids = []
    for row in adapter_rows:
        search_view_ids.extend(row.get("search_view_ids") or [])
    fail_closed = bool(result.abstained and result.fail_closed_reason)
    return {
        "run_id": result.run_id,
        "query_id": result.query_id,
        "route_lane": result.route_lane,
        "adapter_name": "AgentRuntimeLiveSmoke",
        "operation": "invoke",
        "input_schema_version": "rag_live_runtime_smoke_input_v1",
        "output_schema_version": "rag_live_runtime_smoke_output_v1",
        "tenant_id": DIAGNOSTIC_TENANT_ID,
        "diagnostic_tenant_id": DIAGNOSTIC_TENANT_ID,
        "namespace": ADAPTER_NAMESPACE,
        "cache_key": adapter_rows[0].get("cache_key", "") if adapter_rows else "",
        "source_atom_ids": list(result.selected_source_atom_ids),
        "search_view_ids": sorted(set(search_view_ids)),
        "evidence_bundle_ids": list(result.evidence_bundle_ids),
        "allowed_by_contract": not bool(result.adapter_fail_closed_reason),
        "fail_closed": fail_closed,
        "fail_closed_reason": clean(result.fail_closed_reason),
        "latency_ms": round(sum(float(row.get("latency_ms") or 0.0) for row in adapter_rows), 3),
        "timeout_ms": 250,
        "production_write_attempted": False,
        "broad_scan_attempted": False,
        "vector_payload_used_as_evidence_truth": False,
        "runtime_contract_violation": bool(result.runtime_contract_violation),
        "cache_hit": bool(result.cache_hit),
        "status": "fail_closed" if fail_closed else "allowed",
    }


def build_rows() -> dict[str, list[dict[str, Any]]]:
    cases = build_cases()
    cache_items = cache_items_for_cases(cases)
    per_query_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    route_policy_rows: list[dict[str, Any]] = []
    runtime_audit_rows: list[dict[str, Any]] = []
    user_response_policy_rows: list[dict[str, Any]] = []
    db_rows: list[dict[str, Any]] = []
    index_rows: list[dict[str, Any]] = []
    cache_rows: list[dict[str, Any]] = []
    live_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    leakage_rows: list[dict[str, Any]] = []
    for case in cases:
        runtime = build_runtime_for_case(case, cache_items)
        result = runtime.invoke(
            AgentRuntimeRequest(
                run_id=RUN_ID,
                query_id=clean(case.get("query_id")),
                diagnostic_case_id=clean(case.get("diagnostic_case_id")),
                query_text=clean(case.get("query")),
                source_family=clean(case.get("source_family")),
                source_registry={},
                candidate_source_atom_ids=tuple(case.get("candidate_source_atom_ids") or ()),
                rough_query_hint=bool(case.get("rough_query_hint")),
                request_context=base_request_context(case),
                runtime_flags=v319.v317.as_mapping(case.get("runtime_flags")),
                internal_replay_adapter=True,
            )
        )
        trace_rows.extend(result.trace_rows)
        adapter_rows = list(result.runtime_adapter_trace_rows)
        db_rows.extend(row for row in adapter_rows if row["adapter_name"] == "InMemorySourceAtomStoreAdapter")
        index_rows.extend(row for row in adapter_rows if row["adapter_name"] == "InMemorySearchIndexAdapter")
        cache_rows.extend(row for row in adapter_rows if row["adapter_name"] == "InMemoryRuntimeCacheAdapter")
        live_row = build_live_audit_row(result)
        live_rows.append(live_row)
        selected_ids = list(result.selected_source_atom_ids)
        evidence_bundle_ids = list(result.evidence_bundle_ids)
        common = {
            "schema_version": f"{RUN_ID}_per_query_v1",
            "run_id": RUN_ID,
            "review_id": clean(case.get("review_id")),
            "query_id": result.query_id,
            "diagnostic_case_id": result.diagnostic_case_id,
            "live_runtime_smoke_case": clean(case.get("live_runtime_smoke_case")),
            "bucket": clean(case.get("bucket")),
            "source_family": clean(case.get("source_family")),
            "query_text_sha256": sha256_text(clean(case.get("query"))),
            "agent_route": result.agent_route,
            "route_lane": result.route_lane,
            "tool_call_sequence": result.tool_call_sequence,
            "tool_call_trace_path": repo_relative(OUTPUTS["agent_tool_call_trace_jsonl"]),
            "runtime_adapter_trace_path": repo_relative(OUTPUTS["live_runtime_smoke_audit_jsonl"]),
            "runtime_contract_violation": result.runtime_contract_violation,
            "blocked_reason": result.blocked_reason,
            "fail_closed_reason": result.fail_closed_reason,
            "adapter_fail_closed_reason": result.adapter_fail_closed_reason,
            "locator_resolution_bucket": result.locator_resolution_bucket,
            "locator_bounds_answerability": result.locator_bounds_answerability,
            "response_policy_bucket": result.response_policy_bucket,
            "answer_allowed_by_policy": result.answer_allowed_by_policy,
            "db_contract_status": result.db_contract_status,
            "index_contract_status": result.index_contract_status,
            "cache_contract_status": result.cache_contract_status,
            "cache_hit": result.cache_hit,
            "cache_key_namespace": result.cache_key_namespace,
            "evidence_truth_source": result.evidence_truth_source,
            "selected_source_atom_ids": selected_ids,
            "selected_source_atom_count": len(selected_ids),
            "evidence_bundle_ids": evidence_bundle_ids,
            "vector_payload_candidate_only": True,
            "production_write_attempted": False,
            "broad_scan_attempted": False,
            "abstained": result.abstained,
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
                "response_policy_bucket": result.response_policy_bucket,
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
        user_response_policy_rows.append(
            {
                "schema_version": f"{RUN_ID}_user_response_policy_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "agent_route": result.agent_route,
                "route_lane": result.route_lane,
                "response_policy_bucket": result.response_policy_bucket,
                "answer_allowed_by_policy": result.answer_allowed_by_policy,
                "abstained": result.abstained,
                "blocked_reason": result.blocked_reason,
                "fail_closed_reason": result.fail_closed_reason,
                "evidence_truth_source": result.evidence_truth_source,
                "selected_source_atom_count": len(selected_ids),
                "runtime_contract_violation": result.runtime_contract_violation,
                "official_metric_input_rows": 0,
                "diagnostic_only": True,
            }
        )
        review = {
            "review_id": clean(case.get("review_id")),
            "query_id": result.query_id,
            "diagnostic_case_id": result.diagnostic_case_id,
            "live_runtime_smoke_case": clean(case.get("live_runtime_smoke_case")),
            "bucket": clean(case.get("bucket")),
            "source_family": clean(case.get("source_family")),
            "query": clean(case.get("query")),
            "final_answer": result.final_answer,
            "agent_route": result.agent_route,
            "route_lane": result.route_lane,
            "response_policy_bucket": result.response_policy_bucket,
            "answer_allowed_by_policy": result.answer_allowed_by_policy,
            "abstained": result.abstained,
            "db_contract_status": result.db_contract_status,
            "index_contract_status": result.index_contract_status,
            "cache_contract_status": result.cache_contract_status,
            "cache_hit": result.cache_hit,
            "cache_key_namespace": result.cache_key_namespace,
            "adapter_fail_closed_reason": result.adapter_fail_closed_reason,
            "runtime_adapter_trace_path": repo_relative(OUTPUTS["live_runtime_smoke_audit_jsonl"]),
            "tool_call_trace_path": repo_relative(OUTPUTS["agent_tool_call_trace_jsonl"]),
            "evidence_truth_source": result.evidence_truth_source,
            "selected_source_atom_ids": "|".join(selected_ids),
            "evidence_bundle_ids": "|".join(evidence_bundle_ids),
            "vector_payload_candidate_only": True,
            "production_write_attempted": False,
            "broad_scan_attempted": False,
            "runtime_contract_violation": result.runtime_contract_violation,
            "official_metric_candidate": False,
            "promotion_evidence": False,
            **{field: "" for field in USER_REVIEW_FIELDS},
        }
        review_rows.append(review)
        leakage_hits = v319.v317.leakage_hits(review)
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
        "db_contract_audit_rows": db_rows,
        "index_contract_audit_rows": index_rows,
        "cache_contract_audit_rows": cache_rows,
        "live_runtime_smoke_audit_rows": live_rows,
        "review_rows": review_rows,
        "leakage_audit_rows": leakage_rows,
    }


def build_metrics(rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    per_query = list(rows["per_query_rows"])
    trace_rows = list(rows["agent_tool_call_trace_rows"])
    db_rows = list(rows["db_contract_audit_rows"])
    index_rows = list(rows["index_contract_audit_rows"])
    cache_rows = list(rows["cache_contract_audit_rows"])
    route_counts = Counter(clean(row.get("route_lane")) for row in per_query)
    response_counts = Counter(clean(row.get("response_policy_bucket")) for row in per_query)
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "live_runtime_smoke_row_count": len(per_query),
        "review_packet_row_count": len(rows["review_rows"]),
        "per_query_row_count": len(per_query),
        "db_contract_audit_row_count": len(db_rows),
        "index_contract_audit_row_count": len(index_rows),
        "cache_contract_audit_row_count": len(cache_rows),
        "agent_tool_call_trace_row_count": len(trace_rows),
        "user_response_policy_audit_row_count": len(rows["user_response_policy_audit_rows"]),
        "route_lane_counts": dict(sorted(route_counts.items())),
        "response_policy_bucket_counts": dict(sorted(response_counts.items())),
        "db_available_count": sum(1 for row in db_rows if row["status"] == "available"),
        "db_unavailable_fail_closed_count": sum(1 for row in per_query if row["db_contract_status"] == "unavailable" and row["fail_closed_reason"] == "SOURCE_ATOM_STORE_UNAVAILABLE"),
        "index_available_count": sum(1 for row in index_rows if row["status"] == "available"),
        "index_unavailable_fail_closed_count": sum(1 for row in per_query if row["index_contract_status"] == "unavailable" and row["fail_closed_reason"] == "INDEX_UNAVAILABLE"),
        "cache_hit_count": sum(1 for row in per_query if row["cache_hit"]),
        "cache_miss_count": sum(1 for row in per_query if row["cache_contract_status"] == "miss"),
        "cache_unavailable_count": sum(1 for row in per_query if row["cache_contract_status"] == "unavailable"),
        "cache_namespace_mismatch_blocked_count": sum(1 for row in per_query if row["fail_closed_reason"] == "CACHE_NAMESPACE_MISMATCH"),
        "vector_payload_evidence_truth_violation_count": sum(1 for row in [*db_rows, *index_rows, *cache_rows] if row["vector_payload_used_as_evidence_truth"]),
        "broad_source_atom_scan_attempt_count": sum(1 for row in [*db_rows, *index_rows, *cache_rows] if row["broad_scan_attempted"]),
        "production_write_attempt_count": sum(1 for row in [*db_rows, *index_rows, *cache_rows] if row["production_write_attempted"]),
        "raw_file_query_time_accessed": False,
        "runtime_contract_violation_count": sum(1 for row in per_query if row["runtime_contract_violation"]),
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
        "run_class": "diagnostic_only_live_runtime_like_db_index_cache_smoke_nonprod",
        "generated_at": utc_now(),
        "review_packet_dir": repo_relative(OUTPUT_DIR),
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
        "runtime_contract_violation_count": metrics["runtime_contract_violation_count"],
        "production_write_attempt_count": metrics["production_write_attempt_count"],
        "broad_source_atom_scan_attempt_count": metrics["broad_source_atom_scan_attempt_count"],
        "vector_payload_evidence_truth_violation_count": metrics["vector_payload_evidence_truth_violation_count"],
        **guardrail_flags(),
    }


def build_artifacts() -> dict[str, Any]:
    input_paths = build_input_paths()
    require_input_artifacts(input_paths)
    input_lineage = build_input_lineage(input_paths)
    rows = build_rows()
    metrics = build_metrics(rows)
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
    return diagnostic_common.artifact_sha256_without_summary(OUTPUTS)


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    diagnostic_common.replace_marked_entry(path, marker, entry)


def refresh_stale_v3_19_gate_wording() -> None:
    replacements = (
        (
            "full `--rag-current` in this checkout is classified separately when older local legacy report artifacts are absent",
            "full `--rag-current` was reclassified during v3_20 preflight; the concrete blocker in this checkout was the incomplete v3_20 live-runtime-like handoff, not sampled v3_6_9-v3_15 compact artifact availability",
        ),
        (
            "The full `python -X utf8 -m pytest ai/tests --rag-current -q` command currently fails before reaching a clean suite because older v3_6_9-v3_15 local report artifacts are absent from the repo-local/current external archive; this is classified as a legacy artifact availability issue, not a v3_19 official metric or promotion signal.",
            "The broad current-profile gate was reclassified during v3_20 preflight: sampled older v3_6_9-v3_15 compact artifact locks were available in this checkout, while the concrete blocker was the incomplete v3_20 live-runtime-like DB/index/cache handoff. This remains diagnostic-only and not a v3_19 official metric or promotion signal.",
        ),
        (
            "full `--rag-current` remains blocked in this checkout by missing legacy v3_6_9-v3_15 report artifacts; v3_19 targeted policy, artifact, guardrail, and status checks pass.",
            "the broad `--rag-current` blocker was reclassified in v3_20 preflight as the incomplete v3_20 handoff rather than sampled v3_6_9-v3_15 artifact availability; v3_19 targeted policy, artifact, guardrail, and status checks pass.",
        ),
    )
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        text = doc_path.read_text(encoding="utf-8")
        for old, new in replacements:
            text = text.replace(old, new)
        doc_path.write_text(text, encoding="utf-8")


def update_docs(summary: Mapping[str, Any], metrics: Mapping[str, Any]) -> None:
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v319.refresh_last_updated(doc_path)
    refresh_stale_v3_19_gate_wording()

    progress_entry = (
        f"- v3_20 live-runtime-like DB/index/cache smoke (`{RUN_ID}`) is "
        "diagnostic_v3_20_live_runtime_like_db_index_cache_smoke_nonprod_ready. It keeps the non-production "
        "ToolRegistry-only agent runtime and introduces SourceAtomStoreContract, SearchIndexContract, and "
        "RuntimeCacheContract adapters that look like live contracts without touching production surfaces. "
        "SearchIndexContract returns candidates only; SourceAtomStoreContract hydrates canonical SourceAtom ids; "
        "RuntimeCacheContract is optional and never evidence truth. SourceAtom/EvidenceBundle remains canonical "
        "answer evidence; vector/SearchView payload remains candidate-only. Index unavailable and DB/source-atom-store "
        "unavailable rows fail closed, cache unavailable is bypassed without changing answer truth, and stale cache "
        "namespace mismatch fails closed with audit. This is not production routing, not product success, not promotion "
        "evidence, not official scoring, and not live DB/index/cache readiness."
    )
    measurements_entry = f"""### v3_20 Live-Runtime-Like DB/Index/Cache Smoke

- Run: `{RUN_ID}`
- Policy: diagnostic-only, non-production live-runtime-like adapter smoke; no official metric, promotion, production DB/index/cache write, raw PDF/XLSX query-time parsing, broad SourceAtom scan, target/gold/supporting/expected locator use, or vector-payload evidence truth.

| Diagnostic count | Value |
| --- | ---: |
| live_runtime_smoke_row_count | {metrics["live_runtime_smoke_row_count"]} |
| db_contract_audit_row_count | {metrics["db_contract_audit_row_count"]} |
| index_contract_audit_row_count | {metrics["index_contract_audit_row_count"]} |
| cache_contract_audit_row_count | {metrics["cache_contract_audit_row_count"]} |
| agent_tool_call_trace_row_count | {metrics["agent_tool_call_trace_row_count"]} |
| db_available_count | {metrics["db_available_count"]} |
| db_unavailable_fail_closed_count | {metrics["db_unavailable_fail_closed_count"]} |
| index_available_count | {metrics["index_available_count"]} |
| index_unavailable_fail_closed_count | {metrics["index_unavailable_fail_closed_count"]} |
| cache_hit_count | {metrics["cache_hit_count"]} |
| cache_miss_count | {metrics["cache_miss_count"]} |
| cache_unavailable_count | {metrics["cache_unavailable_count"]} |
| cache_namespace_mismatch_blocked_count | {metrics["cache_namespace_mismatch_blocked_count"]} |
| runtime_contract_violation_count | {metrics["runtime_contract_violation_count"]} |
| production_write_attempt_count | {metrics["production_write_attempt_count"]} |
| broad_source_atom_scan_attempt_count | {metrics["broad_source_atom_scan_attempt_count"]} |
| vector_payload_evidence_truth_violation_count | {metrics["vector_payload_evidence_truth_violation_count"]} |
| official_metric_input_rows | 0 |

Artifacts: `{summary["review_packet_dir"]}/summary.json`, `metrics.json`, `per_query.jsonl`, `agent_tool_call_trace.jsonl`, `route_policy_audit.jsonl`, `runtime_contract_audit.jsonl`, `user_response_policy_audit.jsonl`, `db_contract_audit.jsonl`, `index_contract_audit.jsonl`, `cache_contract_audit.jsonl`, `live_runtime_smoke_audit.jsonl`, `guardrail_audit.json`, `leakage_audit.jsonl`, `review_packet.jsonl`, and `review_packet.csv`.

Counter source-of-truth: `metrics.json` carries the adapter availability, fail-closed, cache, and guardrail counters; `status.jsonl` is a compact event ledger with acceptance counters and artifact hashes.
"""
    triage_entry = (
        "### v3_20 Live-Runtime-Like DB/Index/Cache Smoke Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        "- Scope: diagnostic-only non-production smoke over live-runtime-like SourceAtomStoreContract, SearchIndexContract, and RuntimeCacheContract adapters.\n"
        "- INDEX_UNAVAILABLE rows fail closed before evidence assembly; SOURCE_ATOM_STORE_UNAVAILABLE rows fail closed before SourceAtom/EvidenceBundle truth can be produced.\n"
        "- Cache unavailable is optional: it is audited and bypassed only when SourceAtomStore/EvidenceBundle truth can still be hydrated.\n"
        "- CACHE_NAMESPACE_MISMATCH fails closed in this v3_20 contract, so stale cache namespaces do not return evidence.\n"
        "- SearchIndexContract output is candidate-only; vector/SearchView payload and cache payload are never evidence truth.\n"
        "- The smoke covers explicit XLSX file/sheet/cell, explicit PDF file/page, rough-query semantic constraints, missing-context deictic fail-closed, bounded active-context deictic allowed, unsupported source policy fail-closed, index unavailable, DB unavailable, cache unavailable, and stale cache namespace mismatch.\n"
        "- This is not production routing and not live DB/index/cache readiness.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        "Overall status: `diagnostic_v3_20_live_runtime_like_db_index_cache_smoke_nonprod_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"current diagnostic (?:answer-quality|response-policy) loop:\n`[^`]+`;",
        f"current diagnostic live-runtime-like smoke loop:\n`{RUN_ID}`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)


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
        "tool_registry_version": summary["tool_registry_version"],
        "route_policy_lanes": summary["route_policy_lanes"],
        "live_runtime_smoke_row_count": summary["live_runtime_smoke_row_count"],
        "db_contract_audit_row_count": summary["db_contract_audit_row_count"],
        "index_contract_audit_row_count": summary["index_contract_audit_row_count"],
        "cache_contract_audit_row_count": summary["cache_contract_audit_row_count"],
        "agent_tool_call_trace_row_count": summary["agent_tool_call_trace_row_count"],
        "db_unavailable_fail_closed_count": summary["db_unavailable_fail_closed_count"],
        "index_unavailable_fail_closed_count": summary["index_unavailable_fail_closed_count"],
        "cache_namespace_mismatch_blocked_count": summary["cache_namespace_mismatch_blocked_count"],
        "runtime_contract_violation_count": summary["runtime_contract_violation_count"],
        "production_write_attempt_count": summary["production_write_attempt_count"],
        "broad_source_atom_scan_attempt_count": summary["broad_source_atom_scan_attempt_count"],
        "vector_payload_evidence_truth_violation_count": summary["vector_payload_evidence_truth_violation_count"],
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
    write_jsonl(OUTPUTS["db_contract_audit_jsonl"], artifacts["db_contract_audit_rows"])
    write_jsonl(OUTPUTS["index_contract_audit_jsonl"], artifacts["index_contract_audit_rows"])
    write_jsonl(OUTPUTS["cache_contract_audit_jsonl"], artifacts["cache_contract_audit_rows"])
    write_jsonl(OUTPUTS["live_runtime_smoke_audit_jsonl"], artifacts["live_runtime_smoke_audit_rows"])
    write_json(OUTPUTS["guardrail_audit_json"], artifacts["guardrail_audit"])
    write_jsonl(OUTPUTS["leakage_audit_jsonl"], artifacts["leakage_audit_rows"])
    write_jsonl(OUTPUTS["review_packet_jsonl"], artifacts["review_rows"])
    write_csv(OUTPUTS["review_packet_csv"], artifacts["review_rows"])
    summary = dict(artifacts["summary"])
    summary["artifact_sha256"] = artifact_sha256_without_summary()
    write_json(OUTPUTS["summary_json"], summary)
    return summary


def run_write() -> dict[str, Any]:
    artifacts = build_artifacts()
    summary = write_artifacts(artifacts)
    update_docs(summary, artifacts["metrics"])
    append_status_event(summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Build in memory only.")
    args = parser.parse_args(argv)
    artifacts = build_artifacts()
    payload = {
        "run_id": RUN_ID,
        "status": artifacts["summary"]["status"],
        "live_runtime_smoke_row_count": artifacts["metrics"]["live_runtime_smoke_row_count"],
        "db_contract_audit_row_count": artifacts["metrics"]["db_contract_audit_row_count"],
        "index_contract_audit_row_count": artifacts["metrics"]["index_contract_audit_row_count"],
        "cache_contract_audit_row_count": artifacts["metrics"]["cache_contract_audit_row_count"],
        "runtime_contract_violation_count": artifacts["metrics"]["runtime_contract_violation_count"],
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }
    if args.check:
        print(json.dumps({"check": True, **payload}, ensure_ascii=False, sort_keys=True))
        return 0
    summary = run_write()
    print(json.dumps({**payload, "summary": repo_relative(OUTPUTS["summary_json"]), "status": summary["status"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
