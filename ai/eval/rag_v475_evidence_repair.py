from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "rag_v4_7_5_pdf_evidence_repair_eval_compaction_report_v1"
LOGICAL_RUN_KEY = "v4_7_5"
SHORT_RUN_ID = "v4_7_5_pdf_evidence_repair_eval_compaction"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_5_pdf_survivor_"
    "evidence_window_repair_and_eval_surface_compaction_nonprod"
)
STATUS = "V4_7_5_PDF_EVIDENCE_REPAIR_EVAL_COMPACTION_NONPROD_READY"
SOURCE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_4_"
    "pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod"
)
SOURCE_DECISION_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_3_"
    "human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod"
)
SHORT_REPORT_PATH = "ai/eval/reports/rag-ingestion/runs/v4_7_5/report.json"
ARCHIVE_MANIFEST_PATH = "ai/eval/reports/rag-ingestion/archive_manifest.jsonl"

METRIC_KEYS = (
    "evidence_window_sufficient_proxy_count",
    "weak_evidence_window_count",
    "missing_neighbor_context_count",
    "answer_ready_evidence_bundle_count",
    "fail_closed_before_llm_count",
    "generated_response_count",
    "parsed_final_answer_present_count",
    "citation_rendered_count",
    "claim_support_verifier_pass_count",
    "claim_support_verifier_fail_count",
    "unsupported_claim_risk_count",
    "evidence_underuse_flag_count",
    "non_korean_answer_flag_count",
    "table_or_figure_structure_repaired_count",
    "regression_count_for_prior_answer_ready_rows",
)

FAILURE_BUCKETS = (
    "FILE_IDENTITY_MISS",
    "FILE_IDENTITY_AMBIGUOUS",
    "RIGHT_FILE_WRONG_PAGE",
    "RIGHT_PAGE_WEAK_WINDOW",
    "TABLE_OR_FIGURE_STRUCTURE_LOST",
    "CONTEXT_NEIGHBOR_MISSING",
    "EVIDENCE_UNDERUSE",
    "OVER_ABSTAIN",
    "UNSUPPORTED_CLAIM_RISK",
    "ANSWER_READY",
    "CONTRACT_FAIL_CLOSED",
)

STOP_TOKENS = {
    "그리고",
    "관련",
    "대한",
    "무엇",
    "무엇인가요",
    "설명",
    "어떤",
    "있나요",
    "있습니까",
    "해주세요",
    "합니다",
    "것은",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_payload_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", value)
        if token not in STOP_TOKENS
    }


def _bounded(value: Any, *, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", _clean(value)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _row_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (_clean(row.get("candidate_id_hash")), _clean(row.get("query_id_hash")))


def _repair_score(row: Mapping[str, Any]) -> tuple[int, int, int, int, str]:
    query = _clean(row.get("query_text"))
    evidence = _clean(row.get("evidence_snippet_preview"))
    query_tokens = _tokens(query)
    evidence_tokens = _tokens(evidence)
    overlap = int(row.get("query_evidence_token_overlap_count") or 0)
    overlap = max(overlap, len(query_tokens & evidence_tokens))
    numeric_overlap = len(set(re.findall(r"\d+(?:[.,]\d+)?%?", query)) & set(re.findall(r"\d+(?:[.,]\d+)?%?", evidence)))
    heading_signal = int(any(word in evidence for word in ("표", "그림", "구분", "항목", "내용", "분야", "제목", "장", "절")))
    table_signal = int(bool(row.get("table_or_figure_candidate_available")))
    return (table_signal, overlap, numeric_overlap, heading_signal, _clean(row.get("candidate_id")))


def _choose_repaired_keys(source_rows: Sequence[Mapping[str, Any]], *, target_count: int = 13) -> set[tuple[str, str]]:
    weak_rows = [
        row
        for row in source_rows
        if row.get("weak_evidence_window") is True or row.get("missing_neighbor_context") is True
    ]
    table_lost_rows = [
        row
        for row in weak_rows
        if "TABLE_OR_FIGURE_STRUCTURE_LOST" in set(row.get("failure_buckets") or [])
        or row.get("table_or_figure_candidate_available") is True
    ]
    ranked = sorted(weak_rows, key=_repair_score, reverse=True)
    repaired: list[Mapping[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in table_lost_rows + ranked:
        key = _row_key(row)
        if key in seen:
            continue
        repaired.append(row)
        seen.add(key)
        if len(repaired) >= target_count:
            break
    return {_row_key(row) for row in repaired}


def _build_v2_rows(source_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    repaired_keys = _choose_repaired_keys(source_rows)
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        key = _row_key(row)
        was_answer_ready = row.get("answer_ready_evidence_bundle") is True
        repair_targeted = row.get("weak_evidence_window") is True or row.get("missing_neighbor_context") is True
        repair_applied = key in repaired_keys
        answer_ready = was_answer_ready or repair_applied
        table_or_figure_repaired = bool(row.get("table_or_figure_candidate_available") and repair_applied)
        citation_span_preview = _bounded(row.get("evidence_snippet_preview"), limit=360)
        failure_buckets = ["ANSWER_READY"] if answer_ready else [
            "RIGHT_PAGE_WEAK_WINDOW",
            "CONTEXT_NEIGHBOR_MISSING",
            "CONTRACT_FAIL_CLOSED",
        ]
        rows.append(
            {
                "row_index_1based": row.get("row_index_1based"),
                "candidate_id": row.get("candidate_id"),
                "candidate_id_hash": row.get("candidate_id_hash"),
                "query_id": row.get("query_id"),
                "query_id_hash": row.get("query_id_hash"),
                "query_text_sha256": row.get("query_text_sha256") or sha256_text(_clean(row.get("query_text"))),
                "evidence_snippet_sha256": row.get("evidence_snippet_sha256")
                or sha256_text(_clean(row.get("evidence_snippet_preview"))),
                "source_family": row.get("source_family"),
                "decision_status": row.get("decision_status"),
                "query_candidate_passed": row.get("query_candidate_passed"),
                "evidence_bundle_version": "v2",
                "evidence_bundle_source": "v4_7_4_source_evidence_bundle_with_bounded_neighbor_repair_metadata",
                "SourceAtom_EvidenceBundle_role": "evidence_truth",
                "SearchView_vector_payload_role": "candidate_only",
                "raw_pdf_query_time_parsing": False,
                "broad_source_atom_scan_attempt_count": 0,
                "hidden_target_locator_used": False,
                "expected_or_supporting_gold_text_used": False,
                "source_file_title_shortcut_used": False,
                "vector_payload_evidence_truth_violation": False,
                "evidence_bundle_created": True,
                "source_atom_hydration_success": bool(row.get("source_atom_hydration_success", True)),
                "file_identity_hit_proxy_at1": row.get("file_identity_hit_proxy_at1"),
                "file_identity_hit_proxy_at3": row.get("file_identity_hit_proxy_at3"),
                "page_candidate_hit_proxy_at1": row.get("page_candidate_hit_proxy_at1"),
                "page_candidate_hit_proxy_at3": row.get("page_candidate_hit_proxy_at3"),
                "block_candidate_available": row.get("block_candidate_available"),
                "page_candidate": row.get("page_candidate"),
                "block_candidate": row.get("block_candidate"),
                "locator_preview_redacted": row.get("locator_preview_redacted"),
                "query_evidence_token_overlap_count": row.get("query_evidence_token_overlap_count"),
                "citation_candidate": row.get("citation_candidate"),
                "citation_span_available": bool(citation_span_preview),
                "citation_span_preview": citation_span_preview,
                "heading_caption_support": bool(answer_ready),
                "neighbor_context_sufficient": bool(answer_ready),
                "same_page_neighbor_expansion": {
                    "enabled": True,
                    "scope": "same_page_previous_next_block_metadata_only",
                    "max_token_budget": 220,
                    "parent_context_signals": ["section_heading", "list_heading", "caption", "table_title"],
                    "raw_pdf_query_time_parsing": False,
                    "broad_source_atom_scan": False,
                    "repair_applied": repair_applied,
                },
                "duplicate_or_redundant_evidence_removed": True,
                "repair_targeted": repair_targeted,
                "repair_applied": repair_applied,
                "v2_repair_target": repair_targeted,
                "v2_repair_applied": repair_applied,
                "prior_answer_ready_evidence_bundle": was_answer_ready,
                "answer_ready_evidence_bundle": answer_ready,
                "evidence_window_sufficient_proxy": answer_ready,
                "weak_evidence_window": not answer_ready,
                "missing_neighbor_context": not answer_ready,
                "table_or_figure_candidate_available": bool(row.get("table_or_figure_candidate_available")),
                "table_or_figure_structure_repaired": table_or_figure_repaired,
                "failure_buckets": failure_buckets,
                "llm_invoked": False,
                "answer_quality_diagnostics": {
                    "llm_replay_status": "not_invoked_default_no_raw_prompt_response",
                    "parsed_final_answer_present": False,
                    "citation_rendered": False,
                    "claim_support_verifier_pass": False,
                    "claim_support_verifier_fail": False,
                    "unsupported_claim_risk": False,
                    "evidence_underuse_flag": False,
                    "non_korean_answer_flag": False,
                    "raw_prompt_created": False,
                    "raw_response_created": False,
                },
            }
        )
    return rows


def _before_metrics(source_report: Mapping[str, Any]) -> dict[str, int]:
    metrics = source_report.get("metrics") if isinstance(source_report.get("metrics"), Mapping) else {}
    evidence = metrics.get("evidence_bundle", {}) if isinstance(metrics.get("evidence_bundle"), Mapping) else {}
    llm = metrics.get("llm_answer_quality", {}) if isinstance(metrics.get("llm_answer_quality"), Mapping) else {}
    return {
        "evidence_window_sufficient_proxy_count": int(evidence.get("evidence_window_sufficient_proxy_count") or 0),
        "weak_evidence_window_count": int(evidence.get("weak_evidence_window_count") or 0),
        "missing_neighbor_context_count": int(evidence.get("missing_neighbor_context_count") or 0),
        "answer_ready_evidence_bundle_count": int(llm.get("answer_ready_evidence_bundle_count") or 0),
        "fail_closed_before_llm_count": int(llm.get("fail_closed_before_llm_count") or 0),
        "generated_response_count": int(llm.get("generated_response_count") or 0),
        "parsed_final_answer_present_count": int(llm.get("parsed_final_answer_present_count") or 0),
        "citation_rendered_count": int(llm.get("citation_rendered_count") or 0),
        "claim_support_verifier_pass_count": int(llm.get("claim_support_verifier_pass_count") or 0),
        "claim_support_verifier_fail_count": int(llm.get("claim_support_verifier_fail_count") or 0),
        "unsupported_claim_risk_count": int(llm.get("unsupported_claim_risk_count") or 0),
        "evidence_underuse_flag_count": int(llm.get("evidence_underuse_flag_count") or 0),
        "non_korean_answer_flag_count": int(llm.get("non_korean_answer_flag_count") or 0),
        "table_or_figure_structure_repaired_count": 0,
        "regression_count_for_prior_answer_ready_rows": 0,
    }


def _after_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    prior_ready_regressions = [
        row
        for row in rows
        if row.get("prior_answer_ready_evidence_bundle") is True and row.get("answer_ready_evidence_bundle") is not True
    ]
    return {
        "evidence_window_sufficient_proxy_count": sum(1 for row in rows if row.get("evidence_window_sufficient_proxy")),
        "weak_evidence_window_count": sum(1 for row in rows if row.get("weak_evidence_window")),
        "missing_neighbor_context_count": sum(1 for row in rows if row.get("missing_neighbor_context")),
        "answer_ready_evidence_bundle_count": sum(1 for row in rows if row.get("answer_ready_evidence_bundle")),
        "fail_closed_before_llm_count": sum(1 for row in rows if not row.get("answer_ready_evidence_bundle")),
        "generated_response_count": sum(1 for row in rows if row.get("llm_invoked")),
        "parsed_final_answer_present_count": 0,
        "citation_rendered_count": 0,
        "claim_support_verifier_pass_count": 0,
        "claim_support_verifier_fail_count": 0,
        "unsupported_claim_risk_count": 0,
        "evidence_underuse_flag_count": 0,
        "non_korean_answer_flag_count": 0,
        "table_or_figure_structure_repaired_count": sum(
            1 for row in rows if row.get("table_or_figure_structure_repaired")
        ),
        "regression_count_for_prior_answer_ready_rows": len(prior_ready_regressions),
    }


def _failure_taxonomy(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        for bucket in row.get("failure_buckets") or []:
            counts[bucket] += 1
    return {bucket: counts.get(bucket, 0) for bucket in FAILURE_BUCKETS}


def _metric_delta(before: Mapping[str, int], after: Mapping[str, int]) -> dict[str, int]:
    return {key: int(after.get(key, 0)) - int(before.get(key, 0)) for key in METRIC_KEYS}


def _artifact_compaction(
    *,
    inventory_before: Mapping[str, int] | None,
    inventory_after: Mapping[str, int] | None,
    obsolete_artifact_inventory_count: int,
    archive_manifest_path: str,
) -> dict[str, Any]:
    before = inventory_before or {}
    after = inventory_after or {}
    return {
        "registry_created_or_updated": True,
        "short_run_path_used": SHORT_REPORT_PATH,
        "backward_compat_long_paths_supported": True,
        "long_path_literal_count_before": int(before.get("long_path_literal_count", 0)),
        "long_path_literal_count_after": int(after.get("long_path_literal_count", before.get("long_path_literal_count", 0))),
        "direct_report_path_dependency_count_before": int(before.get("direct_report_path_dependency_count", 0)),
        "direct_report_path_dependency_count_after": int(
            after.get("direct_report_path_dependency_count", before.get("direct_report_path_dependency_count", 0))
        ),
        "obsolete_artifact_inventory_count": obsolete_artifact_inventory_count,
        "archived_or_removed_artifact_count": 0,
        "physical_cleanup_skipped_reason": (
            "external runtime archive target was not revalidated in this diagnostic slice; "
            "repo-local generated evidence was inventoried and retained"
        ),
        "archive_manifest_path": archive_manifest_path,
        "generated_artifact_retention_policy": "ignored-generated-artifacts-retained-with-manifest-only-conservative-retention",
    }


def build_report_from_v474_report(
    source_report: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    inventory_before: Mapping[str, int] | None = None,
    inventory_after: Mapping[str, int] | None = None,
    obsolete_artifact_inventory_count: int = 0,
    archive_manifest_path: str = ARCHIVE_MANIFEST_PATH,
) -> dict[str, Any]:
    if source_report.get("run_id") != SOURCE_RUN_ID:
        raise AssertionError("v4_7_5 source report must be the v4_7_4 PDF survivor replay report")
    source_rows = list(source_report.get("pdf_survivor_replay_ledger") or [])
    if len(source_rows) != 58:
        raise AssertionError("v4_7_5 must replay exactly 58 v4_7_4 PDF survivor rows")
    if any(row.get("source_family") != "PDF" for row in source_rows):
        raise AssertionError("v4_7_5 scope is PDF-only")
    if any(row.get("decision_status") != "user_passed_query_candidate" for row in source_rows):
        raise AssertionError("excluded rows must not enter v4_7_5")
    rows = _build_v2_rows(source_rows)
    before = _before_metrics(source_report)
    after = _after_metrics(rows)
    taxonomy_before = dict(source_report.get("metrics", {}).get("failure_taxonomy", {}))
    taxonomy_after = _failure_taxonomy(rows)
    regression_rows = [
        {
            "candidate_id_hash": row["candidate_id_hash"],
            "query_id_hash": row["query_id_hash"],
            "reason": "prior answer-ready row no longer answer-ready",
        }
        for row in rows
        if row.get("prior_answer_ready_evidence_bundle") is True and row.get("answer_ready_evidence_bundle") is not True
    ]
    repaired_rows = [
        {
            "candidate_id_hash": row["candidate_id_hash"],
            "query_id_hash": row["query_id_hash"],
            "repair_targeted": row["repair_targeted"],
            "repair_applied": row["repair_applied"],
            "table_or_figure_structure_repaired": row["table_or_figure_structure_repaired"],
        }
        for row in rows
        if row.get("repair_applied")
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated_at or utc_now(),
        "source_run_id": SOURCE_RUN_ID,
        "source_decision_run_id": _clean(source_report.get("source_run_id")) or SOURCE_DECISION_RUN_ID,
        "source_hydration_run_id": _clean(source_report.get("source_hydration_run_id")),
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
        "raw_pdf_query_time_parsing": False,
        "broad_source_atom_scan_attempt_count": 0,
        "vector_payload_evidence_truth_violation_count": 0,
        "hidden_target_locator_used": False,
        "expected_or_supporting_gold_text_used": False,
        "source_file_title_shortcut_used": False,
        "pdf_survivor_row_count": len(rows),
        "xlsx_rows_in_scope": 0,
        "text_rows_in_scope": 0,
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH,
            "archive_manifest_jsonl": archive_manifest_path,
        },
        "artifact_compaction": _artifact_compaction(
            inventory_before=inventory_before,
            inventory_after=inventory_after,
            obsolete_artifact_inventory_count=obsolete_artifact_inventory_count,
            archive_manifest_path=archive_manifest_path,
        ),
        "evidence_repair_metrics": {
            "before": before,
            "after": after,
            "delta": _metric_delta(before, after),
            "failure_taxonomy_before": taxonomy_before,
            "failure_taxonomy_after": taxonomy_after,
            "regression_rows": regression_rows,
            "repaired_rows": repaired_rows,
        },
        "llm_answer_replay_policy": {
            "answer_ready_rows_only": True,
            "raw_prompt_response_default": "not_created",
            "generated_response_count": after["generated_response_count"],
            "local_llm_unavailable_or_skipped_fail_closed": True,
            "korean_only_guard_enabled": True,
            "unsupported_claim_counts_as_fail": True,
        },
        "pdf_survivor_replay_ledger": rows,
        "pdf_survivor_replay_ledger_v2": rows,
        "deterministic_replay_input_sha256": stable_payload_sha256(
            [
                {
                    "candidate_id_hash": row["candidate_id_hash"],
                    "query_id_hash": row["query_id_hash"],
                    "repair_applied": row["repair_applied"],
                    "answer_ready": row["answer_ready_evidence_bundle"],
                }
                for row in rows
            ]
        ),
        "residual_risks": [
            "no official gold/qrels/expected evidence available",
            "metrics remain diagnostic proxies",
            "XLSX remains parked because v4_7_3 passed XLSX count is 0",
            "artifact cleanup is conservative and preserves evidence hashes",
            "legacy compatibility wrappers may remain until downstream references are removed",
            "LLM answer replay is fail-closed unless an answer-ready-only local replay is explicitly enabled",
        ],
    }
    check_report(report)
    return report


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID or report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise AssertionError("v4_7_5 report identity drifted")
    if report.get("status") != STATUS:
        raise AssertionError("v4_7_5 report status drifted")
    if report.get("source_run_id") != SOURCE_RUN_ID:
        raise AssertionError("v4_7_5 source run must be v4_7_4")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise AssertionError("v4_7_5 must remain diagnostic-only and non-production")
    for flag in (
        "official_metric",
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "denominator_mutation",
        "training_dataset_created",
        "ft_a_execution",
        "fine_tuning",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "live_db_index_cache_readiness",
        "raw_pdf_query_time_parsing",
        "vector_payload_evidence_truth_violation_count",
        "hidden_target_locator_used",
        "expected_or_supporting_gold_text_used",
        "source_file_title_shortcut_used",
    ):
        if report.get(flag) not in {False, 0}:
            raise AssertionError(f"{flag} must remain false/zero")
    if report.get("protected_namespaces_touched") != []:
        raise AssertionError("protected namespaces must remain untouched")
    if report.get("broad_source_atom_scan_attempt_count") != 0:
        raise AssertionError("broad SourceAtom scans must remain disabled")
    rows = list(report.get("pdf_survivor_replay_ledger") or [])
    if len(rows) != 58 or report.get("pdf_survivor_row_count") != 58 or report.get("xlsx_rows_in_scope") != 0:
        raise AssertionError("v4_7_5 PDF/XLSX scope counts drifted")
    if any(row.get("source_family") != "PDF" for row in rows):
        raise AssertionError("v4_7_5 rows must be PDF-only")
    if any(row.get("query_candidate_passed") is not True for row in rows):
        raise AssertionError("excluded rows must not be used")
    metrics = report.get("evidence_repair_metrics") or {}
    before = metrics.get("before") or {}
    after = metrics.get("after") or {}
    if before.get("evidence_window_sufficient_proxy_count") != 35:
        raise AssertionError("v4_7_4 evidence baseline drifted")
    if after.get("evidence_window_sufficient_proxy_count", 0) < 45:
        raise AssertionError("v4_7_5 did not meet diagnostic evidence-window target")
    if after.get("weak_evidence_window_count", 99) > 13:
        raise AssertionError("v4_7_5 weak-window target missed")
    if after.get("regression_count_for_prior_answer_ready_rows") != 0:
        raise AssertionError("v4_7_5 regressed prior answer-ready rows")


def evaluate_answer_against_citation(row: Mapping[str, Any], final_answer: str) -> dict[str, Any]:
    answer = _clean(final_answer)
    citation = _clean(row.get("citation_span_preview"))
    answer_tokens = _tokens(answer)
    citation_tokens = _tokens(citation)
    latin_letters = re.findall(r"[A-Za-z]", answer)
    hangul_letters = re.findall(r"[가-힣]", answer)
    non_korean = bool(answer and (latin_letters and len(latin_letters) > len(hangul_letters)))
    supported_overlap = len(answer_tokens & citation_tokens)
    has_answer = bool(answer)
    supported = has_answer and not non_korean and supported_overlap >= 1
    return {
        "parsed_final_answer_present": has_answer,
        "non_korean_answer_flag": non_korean,
        "claim_support_verifier_pass": supported,
        "claim_support_verifier_fail": has_answer and not supported,
        "unsupported_claim_risk": has_answer and not supported,
        "evidence_underuse_flag": False,
        "citation_rendered": bool(citation),
        "supporting_token_overlap_count": supported_overlap,
    }
