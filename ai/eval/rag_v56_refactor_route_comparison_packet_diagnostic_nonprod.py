from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ai.eval import rag_v560_official_metric_scored_execution_and_failure_attribution_nonprod as v560
from ai.eval import rag_v5_diagnostic_common as common


AI_DIR = Path(__file__).resolve().parents[1]
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from app.capabilities.rag_orchestrator.graph import (  # noqa: E402
    TRACK_INSUFFICIENT_METADATA,
    TRACK_MULTI_ROUTE,
    TRACK_PDF_BUSINESS_OCR_MM,
    TRACK_POLICY_BLOCKED,
    TRACK_TEXT_NAMUWIKI_ANIMATION,
    TRACK_XLSX_BUSINESS_STRUCTURED,
    build_route_decision,
)


LOGICAL_RUN_KEY = "v5_6_refactor_comparison"
SHORT_RUN_ID = "v5_6_refactor_route_comparison_packet_diagnostic_nonprod"
CANONICAL_LONG_RUN_ID = SHORT_RUN_ID
STATUS = "V5_6_REFACTOR_ROUTE_COMPARISON_PACKET_DIAGNOSTIC_NONPROD_READY"
CURRENT_RESOLVES_TO = v560.LOGICAL_RUN_KEY
KST_DOC_DATE = "2026-06-05"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
SHORT_REPORT_PATH = RUN_ROOT / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
PROGRESS_DOC = Path("docs/rag-ingestion-progress.md")

TOP_K = 3
FAMILIES = ("TEXT", "XLSX", "PDF")
SCOPE_TYPES = ("metadata_scoped", "query_only")

LEGACY_KEYWORD_POLICY = (
    "diagnostic_replay_of_prior_query_keyword_route_only_no_runtime_or_metric_authority"
)
COMPARISON_INPUT_POLICY = "fixture_only_no_official_denominator_rows_consumed"

_TEXT_KEYWORDS = (
    "namu",
    "나무위키",
    "애니",
    "애니메이션",
    "작품",
    "캐릭터",
    "등장인물",
    "성우",
    "줄거리",
)
_XLSX_KEYWORDS = (
    "xlsx",
    "xls",
    "excel",
    "엑셀",
    "spreadsheet",
    "sheet",
    "시트",
    "셀",
    "행",
    "열",
    "표",
    "합계",
    "평균",
    "승차",
    "승객수",
)
_PDF_KEYWORDS = (
    "pdf",
    ".pdf",
    "페이지",
    "쪽",
    "bbox",
    "ocr",
    "문단",
    "캡션",
    "footnote",
    "각주",
)

CLOSED_FALSE_KEYS = (
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "training_dataset_created",
    "training_manifest_jsonl_created",
    "training_job_created",
    "fine_tuning_dataset_export_created",
    "fine_tuning",
    "fine_tuning_started",
    "fine_tuning_executed",
    "ft_a_execution",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_db_mutated",
    "source_registry_mutated",
    "silver_mutation",
    "index_rebuilt",
    "cache_mutated",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
)
FORBIDDEN_PAYLOAD_KEYS = set(v560.RAW_PAYLOAD_FORBIDDEN_KEYS) | {
    "raw_prompt_payload",
    "raw_response_payload",
    "raw_llm_response",
    "expected_answer",
    "expected_answer_ko",
    "supporting_evidence_ids",
    "supporting_evidence_note",
    "citation_locator",
    "official_metric_input_rows_payload",
    "gold_status",
    "target_locator",
}


class _FixtureRouteAdjudicator:
    def __init__(self, route: str) -> None:
        self.route = route
        self.calls: list[dict[str, Any]] = []

    def adjudicate(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self.calls.append(dict(payload))
        evidence_lane = {
            TRACK_TEXT_NAMUWIKI_ANIMATION: "text_content",
            TRACK_XLSX_BUSINESS_STRUCTURED: "xlsx_structured_evidence",
            TRACK_PDF_BUSINESS_OCR_MM: "pdf_content_evidence",
        }.get(self.route, "none")
        intent = {
            TRACK_TEXT_NAMUWIKI_ANIMATION: "text_content",
            TRACK_XLSX_BUSINESS_STRUCTURED: "xlsx_lookup",
            TRACK_PDF_BUSINESS_OCR_MM: "pdf_content_evidence",
        }.get(self.route, "unknown")
        return {
            "primary_route": self.route,
            "candidate_routes": [self.route] if self.route in {
                TRACK_TEXT_NAMUWIKI_ANIMATION,
                TRACK_XLSX_BUSINESS_STRUCTURED,
                TRACK_PDF_BUSINESS_OCR_MM,
            } else [],
            "route_confidence": 0.92,
            "intent": intent,
            "evidence_lane": evidence_lane,
            "requires_multi_route": False,
            "fallback_plan": [],
            "policy_flags": [],
            "blocked_flags": [],
            "diagnostic_only": True,
            "reason": "Fixture adjudicator selected the bounded diagnostic source family.",
        }


FIXTURE_PACKET: tuple[dict[str, Any], ...] = (
    {
        "query_id": "cmp_xlsx_metadata_valid",
        "family": "XLSX",
        "scope_type": "metadata_scoped",
        "query": "엑셀 신논현요양원 행 찾아줘.",
        "source_metadata": {
            "source_file_type": "SPREADSHEET",
            "parser_version": "xlsx-extract-v2-hidden-safe",
            "location_json": {"sheetName": "일반현황", "cellRange": "A1052:J1101"},
            "citation_text": "fixture.xlsx!일반현황!A1052:J1101",
            "query_id": "cmp_xlsx_metadata_valid",
        },
        "target_candidate_id": "su-xlsx-target",
        "existing_qrels_or_locator_valid": True,
        "before_candidates": ["su-xlsx-target", "su-xlsx-neighbor"],
        "after_candidates": ["su-xlsx-target", "su-xlsx-neighbor"],
        "before_answer": {"execution_status": "executed", "answer_present": True, "citation_present": True, "citation_verified": True},
        "after_answer": {"execution_status": "executed", "answer_present": True, "citation_present": True, "citation_verified": True},
    },
    {
        "query_id": "cmp_text_metadata_keyword_conflict",
        "family": "TEXT",
        "scope_type": "metadata_scoped",
        "query": "xlsx 표 합계를 알려줘.",
        "source_metadata": {
            "source_file_type": "TEXT",
            "parser_version": "text-namu-v2",
            "location_json": {"documentId": "doc-text"},
            "citation_text": "bounded text citation",
            "query_id": "cmp_text_metadata_keyword_conflict",
        },
        "target_candidate_id": "su-text-target",
        "existing_qrels_or_locator_valid": True,
        "before_candidates": ["su-xlsx-wrong", "su-xlsx-neighbor"],
        "after_candidates": ["su-text-target", "su-text-neighbor"],
        "before_answer": {"execution_status": "execution_unavailable", "abstain_reason": "legacy_route_retrieval_context_missing"},
        "after_answer": {"execution_status": "executed", "answer_present": True, "citation_present": True, "citation_verified": True},
    },
    {
        "query_id": "cmp_pdf_metadata_keyword_conflict",
        "family": "PDF",
        "scope_type": "metadata_scoped",
        "query": "xlsx 표를 pdf 근거로 설명해줘.",
        "source_metadata": {
            "source_file_type": "PDF",
            "parser_version": "pdf-extract-v2",
            "location_json": {"page_no": 3, "bbox": [0, 0, 10, 10]},
            "citation_text": "fixture.pdf p. 3",
            "query_id": "cmp_pdf_metadata_keyword_conflict",
        },
        "target_candidate_id": "su-pdf-target",
        "existing_qrels_or_locator_valid": True,
        "before_candidates": ["su-xlsx-wrong", "su-pdf-target"],
        "after_candidates": ["su-pdf-target", "su-pdf-neighbor"],
        "before_answer": {"execution_status": "execution_unavailable", "abstain_reason": "legacy_multi_route_not_synthesized"},
        "after_answer": {"execution_status": "executed", "answer_present": True, "citation_present": True, "citation_verified": True},
    },
    {
        "query_id": "pdf_file_lookup_content_anchor_004",
        "family": "PDF",
        "scope_type": "metadata_scoped",
        "query": "pdf 내용 근거 찾아줘.",
        "source_metadata": {
            "source_file_type": "PDF",
            "parser_version": "pdf-extract-v2",
            "query_id": "pdf_file_lookup_content_anchor_004",
        },
        "target_candidate_id": "",
        "existing_qrels_or_locator_valid": False,
        "before_candidates": ["su-pdf-policy-excluded"],
        "after_candidates": [],
        "before_answer": {"execution_status": "execution_unavailable", "abstain_reason": "policy_excluded_row"},
        "after_answer": {"execution_status": "execution_unavailable", "abstain_reason": "policy_blocked"},
    },
    {
        "query_id": "cmp_query_only_election_llm",
        "family": "XLSX",
        "scope_type": "query_only",
        "query": "구시군의 장선거에서 정당별로 이긴 지역구 수를 알려줘.",
        "after_llm_route": TRACK_XLSX_BUSINESS_STRUCTURED,
        "target_candidate_id": "",
        "existing_qrels_or_locator_valid": False,
        "before_candidates": [],
        "after_candidates": ["su-election-xlsx-preview"],
        "before_answer": {"execution_status": "execution_unavailable", "abstain_reason": "legacy_keyword_route_unresolved"},
        "after_answer": {"execution_status": "execution_unavailable", "abstain_reason": "answer_generation_not_run_in_comparator"},
    },
    {
        "query_id": "cmp_query_only_pdf_keyword",
        "family": "PDF",
        "scope_type": "query_only",
        "query": "pdf 페이지 요약해줘.",
        "target_candidate_id": "",
        "existing_qrels_or_locator_valid": False,
        "before_candidates": ["su-pdf-keyword-preview"],
        "after_candidates": [],
        "before_answer": {"execution_status": "execution_unavailable", "abstain_reason": "query_only_not_synthesized"},
        "after_answer": {"execution_status": "execution_unavailable", "abstain_reason": "llm_route_adjudicator_required"},
    },
    {
        "query_id": "cmp_query_only_text_keyword",
        "family": "TEXT",
        "scope_type": "query_only",
        "query": "나무위키 애니 줄거리 알려줘.",
        "target_candidate_id": "",
        "existing_qrels_or_locator_valid": False,
        "before_candidates": ["su-text-keyword-preview"],
        "after_candidates": [],
        "before_answer": {"execution_status": "execution_unavailable", "abstain_reason": "query_only_not_synthesized"},
        "after_answer": {"execution_status": "execution_unavailable", "abstain_reason": "llm_route_adjudicator_required"},
    },
)


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return common.json_clone(payload)


def _keyword_hit(query: str, keywords: Iterable[str]) -> bool:
    text = query.lower()
    return any(keyword.lower() in text for keyword in keywords)


def legacy_keyword_route(query: str) -> str:
    """Reproduce the old query-keyword route as an eval-only comparator."""

    routes: list[str] = []
    if _keyword_hit(query, _TEXT_KEYWORDS):
        routes.append(TRACK_TEXT_NAMUWIKI_ANIMATION)
    if _keyword_hit(query, _XLSX_KEYWORDS):
        routes.append(TRACK_XLSX_BUSINESS_STRUCTURED)
    if _keyword_hit(query, _PDF_KEYWORDS):
        routes.append(TRACK_PDF_BUSINESS_OCR_MM)
    deduped = list(dict.fromkeys(routes))
    if not deduped:
        return TRACK_INSUFFICIENT_METADATA
    if len(deduped) > 1:
        return TRACK_MULTI_ROUTE
    return deduped[0]


def _after_decision(row: Mapping[str, Any]):
    adjudicator = None
    if _clean(row.get("after_llm_route")):
        adjudicator = _FixtureRouteAdjudicator(_clean(row["after_llm_route"]))
    metadata = row.get("source_metadata")
    return build_route_decision(
        query=_clean(row.get("query")),
        source_metadata=dict(metadata) if isinstance(metadata, Mapping) else None,
        route_adjudicator=adjudicator,
    )


def _route_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        before_route = legacy_keyword_route(_clean(row.get("query")))
        decision = _after_decision(row)
        blocked_reason = ";".join(decision.blocked_flags)
        llm_required = (
            decision.llm_adjudicator_called
            or decision.llm_validation_status == "required"
            or "llm_route_adjudicator_required" in decision.blocked_flags
        )
        metadata_scoped = row.get("scope_type") == "metadata_scoped"
        output.append(
            {
                "query_id": _clean(row.get("query_id")),
                "family": _clean(row.get("family")),
                "scope_type": _clean(row.get("scope_type")),
                "metadata_scoped": metadata_scoped,
                "before_route": before_route,
                "after_route": decision.route,
                "route_changed": before_route != decision.route,
                "after_blocked_reason": blocked_reason,
                "llm_required": bool(llm_required),
                "after_llm_adjudicator_called": decision.llm_adjudicator_called,
                "after_llm_validation_status": decision.llm_validation_status,
                "after_metadata_guards": list(decision.metadata_guards),
                "after_policy_guards": list(decision.policy_guards),
                "after_blocked_flags": list(decision.blocked_flags),
            }
        )
    return output


def _retrieval_side(candidates: Sequence[Any], target: str, *, valid: bool) -> dict[str, Any]:
    candidate_ids = [_clean(item) for item in candidates if _clean(item)]
    if not valid:
        return {
            "hit_at_1": False,
            "hit_at_k": False,
            "target_in_candidates": False,
            "candidate_count": len(candidate_ids),
            "evidence_sufficiency_status": "not_computed_invalid_qrels_or_locator",
        }
    target_in_candidates = target in candidate_ids
    return {
        "hit_at_1": bool(candidate_ids[:1] and candidate_ids[0] == target),
        "hit_at_k": target in candidate_ids[:TOP_K],
        "target_in_candidates": target_in_candidates,
        "candidate_count": len(candidate_ids),
        "evidence_sufficiency_status": "target_found" if target_in_candidates else "target_missing",
    }


def _retrieval_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> str:
    before_score = (1 if before["hit_at_1"] else 0, 1 if before["hit_at_k"] else 0)
    after_score = (1 if after["hit_at_1"] else 0, 1 if after["hit_at_k"] else 0)
    if after_score > before_score:
        return "improved_on_fixture_subset"
    if after_score < before_score:
        return "regressed_on_fixture_subset"
    return "unchanged_on_fixture_subset"


def _retrieval_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        valid = row.get("existing_qrels_or_locator_valid") is True and bool(_clean(row.get("target_candidate_id")))
        before = _retrieval_side(row.get("before_candidates") or [], _clean(row.get("target_candidate_id")), valid=valid)
        after = _retrieval_side(row.get("after_candidates") or [], _clean(row.get("target_candidate_id")), valid=valid)
        output.append(
            {
                "query_id": _clean(row.get("query_id")),
                "family": _clean(row.get("family")),
                "scope_type": _clean(row.get("scope_type")),
                "existing_qrels_or_locator_valid": valid,
                "retrieval_quality_delta_computed": valid,
                "retrieval_blocked_reason": "" if valid else "missing_valid_qrels_or_locator",
                "before_retrieval": before,
                "after_retrieval": after,
                "retrieval_quality_delta": _retrieval_delta(before, after) if valid else "not_computed",
            }
        )
    return output


def _answer_side(value: Mapping[str, Any]) -> dict[str, Any]:
    status = _clean(value.get("execution_status")) or "execution_unavailable"
    executed = status == "executed"
    return {
        "execution_status": status,
        "answer_present": bool(value.get("answer_present")) if executed else False,
        "citation_present": bool(value.get("citation_present")) if executed else False,
        "citation_verified": bool(value.get("citation_verified")) if executed else False,
        "unsupported_claim_flag": bool(value.get("unsupported_claim_flag")) if executed else False,
        "abstain_reason": _clean(value.get("abstain_reason")),
    }


def _answer_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> str:
    before_score = (
        1 if before["answer_present"] else 0,
        1 if before["citation_present"] else 0,
        1 if before["citation_verified"] else 0,
        0 if before["unsupported_claim_flag"] else 1,
    )
    after_score = (
        1 if after["answer_present"] else 0,
        1 if after["citation_present"] else 0,
        1 if after["citation_verified"] else 0,
        0 if after["unsupported_claim_flag"] else 1,
    )
    if after_score > before_score:
        return "improved_on_executed_fixture_subset"
    if after_score < before_score:
        return "regressed_on_executed_fixture_subset"
    return "unchanged_on_executed_fixture_subset"


def _answer_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        before = _answer_side(row.get("before_answer") or {})
        after = _answer_side(row.get("after_answer") or {})
        computed = before["execution_status"] == "executed" and after["execution_status"] == "executed"
        unavailable = before["execution_status"] == "execution_unavailable" or after["execution_status"] == "execution_unavailable"
        output.append(
            {
                "query_id": _clean(row.get("query_id")),
                "family": _clean(row.get("family")),
                "scope_type": _clean(row.get("scope_type")),
                "answer_quality_delta_computed": computed,
                "answer_execution_status": "executed" if computed else "execution_unavailable" if unavailable else "not_computed",
                "answer_quality_blocked_reason": "" if computed else "execution_unavailable",
                "before_answer": before,
                "after_answer": after,
                "answer_quality_delta": _answer_delta(before, after) if computed else "not_computed",
            }
        )
    return output


def _scope_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_family = Counter(_clean(row.get("family")) for row in rows)
    by_scope = Counter(_clean(row.get("scope_type")) for row in rows)
    return {
        "input_policy": COMPARISON_INPUT_POLICY,
        "fixture_row_count": len(rows),
        "families": [family for family in FAMILIES if by_family[family]],
        "family_counts": {family: by_family[family] for family in FAMILIES},
        "scope_counts": {scope: by_scope[scope] for scope in SCOPE_TYPES},
        "metadata_scoped_cases_separated": True,
        "query_only_cases_separated": True,
        "official_29_row_denominator_consumed": False,
    }


def _route_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "row_count": len(rows),
        "route_changed_count": sum(1 for row in rows if row["route_changed"]),
        "llm_required_count": sum(1 for row in rows if row["llm_required"]),
        "after_policy_blocked_count": sum(1 for row in rows if row["after_route"] == TRACK_POLICY_BLOCKED),
        "by_scope_type": {},
        "by_family": {},
    }
    for key_name, keys in (("by_scope_type", SCOPE_TYPES), ("by_family", FAMILIES)):
        source_key = "scope_type" if key_name == "by_scope_type" else "family"
        for key in keys:
            scoped = [row for row in rows if row[source_key] == key]
            summary[key_name][key] = {
                "row_count": len(scoped),
                "route_changed_count": sum(1 for row in scoped if row["route_changed"]),
                "llm_required_count": sum(1 for row in scoped if row["llm_required"]),
            }
    return summary


def _retrieval_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    computed = [row for row in rows if row["retrieval_quality_delta_computed"]]
    blocked = [row for row in rows if not row["retrieval_quality_delta_computed"]]
    by_family: dict[str, Any] = {}
    for family in FAMILIES:
        scoped = [row for row in computed if row["family"] == family]
        by_family[family] = {
            "computed_row_count": len(scoped),
            "before_hit_at_1_count": sum(1 for row in scoped if row["before_retrieval"]["hit_at_1"]),
            "after_hit_at_1_count": sum(1 for row in scoped if row["after_retrieval"]["hit_at_1"]),
            "before_hit_at_k_count": sum(1 for row in scoped if row["before_retrieval"]["hit_at_k"]),
            "after_hit_at_k_count": sum(1 for row in scoped if row["after_retrieval"]["hit_at_k"]),
        }
    return {
        "metric_policy": "computed_only_where_existing_qrels_or_locator_valid",
        "global_delta_claim_supported": False,
        "computed_row_count": len(computed),
        "blocked_row_count": len(blocked),
        "blocked_reason_counts": dict(Counter(row["retrieval_blocked_reason"] for row in blocked)),
        "by_family": by_family,
    }


def _answer_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    computed = [row for row in rows if row["answer_quality_delta_computed"]]
    unavailable = [row for row in rows if row["answer_execution_status"] == "execution_unavailable"]
    by_family: dict[str, Any] = {}
    for family in FAMILIES:
        scoped = [row for row in computed if row["family"] == family]
        by_family[family] = {
            "computed_row_count": len(scoped),
            "answer_present_after_count": sum(1 for row in scoped if row["after_answer"]["answer_present"]),
            "citation_verified_after_count": sum(1 for row in scoped if row["after_answer"]["citation_verified"]),
            "unsupported_claim_after_count": sum(1 for row in scoped if row["after_answer"]["unsupported_claim_flag"]),
        }
    return {
        "metric_policy": "computed_only_when_before_and_after_answer_generation_or_synthesis_executed",
        "global_delta_claim_supported": False,
        "computed_row_count": len(computed),
        "execution_unavailable_row_count": len(unavailable),
        "blocked_reason_counts": dict(Counter(row["answer_quality_blocked_reason"] for row in unavailable)),
        "by_family": by_family,
    }


def build_report(
    *,
    root: Path | str,
    generated_at: str | None = None,
    check: bool = True,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated = generated_at or common.utc_now_iso()
    rows = list(FIXTURE_PACKET)
    route_rows = _route_rows(rows)
    retrieval_rows = _retrieval_rows(rows)
    answer_rows = _answer_rows(rows)
    report = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated,
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
        },
        "artifact_sha256": {},
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "baseline_official_metric_lane_key": v560.LOGICAL_RUN_KEY,
        "baseline_official_metric_report_json": v560.SHORT_REPORT_PATH.as_posix(),
        "baseline_official_metric_artifact_status": common.artifact_status(repo_root / v560.SHORT_REPORT_PATH),
        "non_production": True,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_consumed": 0,
        "official_metric_input_rows_created": 0,
        "official_denominator_rows_touched": 0,
        "official_29_row_denominator_preserved": True,
        "comparison_input_policy": COMPARISON_INPUT_POLICY,
        "legacy_keyword_route_policy": LEGACY_KEYWORD_POLICY,
        "quality_delta_claim_supported": False,
        "quality_delta_claim_blocked_reason": "fixture_subset_diagnostic_only_not_official_metric_denominator",
        "retrieval_quality_delta_computed": False,
        "retrieval_quality_delta_blocked_reason": "global_delta_not_computed_subset_rows_only",
        "answer_quality_delta_computed": False,
        "answer_quality_delta_blocked_reason": "global_delta_not_computed_answer_execution_subset_only",
        "comparator_scope": _scope_summary(rows),
        "route_comparison_rows": route_rows,
        "route_change_summary": _route_summary(route_rows),
        "retrieval_quality_rows": retrieval_rows,
        "retrieval_quality_subset": _retrieval_summary(retrieval_rows),
        "answer_quality_rows": answer_rows,
        "answer_quality_subset": _answer_summary(answer_rows),
        "protected_namespaces_touched": [],
    }
    for key in CLOSED_FALSE_KEYS:
        report[key] = False
    if check:
        check_report(report)
    return report


def _assert_no_forbidden_payload_keys(report: Mapping[str, Any]) -> None:
    common.assert_no_raw_payload_keys(report, FORBIDDEN_PAYLOAD_KEYS, context="v5_6_refactor_comparison")


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("run_id") != SHORT_RUN_ID or report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v5_6 refactor comparison run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v5_6 refactor comparison canonical_long_run_id mismatch")
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v5_6 refactor comparison logical key mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v5_6 refactor comparison status mismatch")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v5_6 refactor comparison current alias drift")


def _require_closed_gates(report: Mapping[str, Any]) -> None:
    if report.get("diagnostic_only") is not True:
        raise ValueError("v5_6 refactor comparison diagnostic_only drift")
    if report.get("official_metric") is not False:
        raise ValueError("v5_6 refactor comparison official metric drift")
    for key in ("official_metric_input_rows", "official_metric_input_rows_consumed", "official_metric_input_rows_created", "official_denominator_rows_touched"):
        if report.get(key) != 0:
            raise ValueError("v5_6 refactor comparison official metric input drift")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v5_6 refactor comparison protected namespace drift")
    for key in CLOSED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v5_6 refactor comparison closed gate drift: {key}")
    quality_delta_messages = {
        "quality_delta_claim_supported": "quality delta claim drift",
        "retrieval_quality_delta_computed": "retrieval quality delta drift",
        "answer_quality_delta_computed": "answer quality delta drift",
    }
    for key, message in quality_delta_messages.items():
        if report.get(key) is not False:
            raise ValueError(f"v5_6 refactor comparison fake {message}: {key}")


def _require_artifact_paths(report: Mapping[str, Any]) -> None:
    expected = {
        "report_json": SHORT_REPORT_PATH.as_posix(),
        "status_jsonl": STATUS_JSONL_PATH.as_posix(),
    }
    if report.get("artifact_paths") != expected:
        raise ValueError("v5_6 refactor comparison artifact path drift")


def _require_route_rows(report: Mapping[str, Any]) -> None:
    rows = list(report.get("route_comparison_rows") or [])
    scope = report.get("comparator_scope") or {}
    if scope.get("fixture_row_count") != len(FIXTURE_PACKET) or len(rows) != len(FIXTURE_PACKET):
        raise ValueError("v5_6 refactor comparison route row count drift")
    required = {
        "query_id",
        "family",
        "scope_type",
        "before_route",
        "after_route",
        "route_changed",
        "after_blocked_reason",
        "llm_required",
        "metadata_scoped",
    }
    for row in rows:
        if not required <= set(row):
            raise ValueError("v5_6 refactor comparison route row schema drift")
        if not _clean(row.get("before_route")) or not _clean(row.get("after_route")):
            raise ValueError("v5_6 refactor comparison route row route drift")
        if row.get("family") not in FAMILIES or row.get("scope_type") not in SCOPE_TYPES:
            raise ValueError("v5_6 refactor comparison route row family or scope drift")
    summary = report.get("route_change_summary") or {}
    if summary.get("route_changed_count") != sum(1 for row in rows if row.get("route_changed") is True):
        raise ValueError("v5_6 refactor comparison route change summary drift")


def _require_retrieval_rows(report: Mapping[str, Any]) -> None:
    rows = list(report.get("retrieval_quality_rows") or [])
    if len(rows) != len(FIXTURE_PACKET):
        raise ValueError("v5_6 refactor comparison retrieval row count drift")
    computed_count = 0
    for row in rows:
        computed = row.get("retrieval_quality_delta_computed") is True
        valid = row.get("existing_qrels_or_locator_valid") is True
        if computed:
            computed_count += 1
            if not valid:
                raise ValueError("v5_6 refactor comparison retrieval subset validity drift")
            for side_key in ("before_retrieval", "after_retrieval"):
                side = row.get(side_key) or {}
                if not {"hit_at_1", "hit_at_k", "target_in_candidates", "candidate_count", "evidence_sufficiency_status"} <= set(side):
                    raise ValueError("v5_6 refactor comparison retrieval metric schema drift")
        elif not _clean(row.get("retrieval_blocked_reason")):
            raise ValueError("v5_6 refactor comparison retrieval blocked reason drift")
    subset = report.get("retrieval_quality_subset") or {}
    if subset.get("global_delta_claim_supported") is not False:
        raise ValueError("v5_6 refactor comparison retrieval quality claim drift")
    if subset.get("computed_row_count") != computed_count:
        raise ValueError("v5_6 refactor comparison retrieval subset count drift")


def _require_answer_rows(report: Mapping[str, Any]) -> None:
    rows = list(report.get("answer_quality_rows") or [])
    if len(rows) != len(FIXTURE_PACKET):
        raise ValueError("v5_6 refactor comparison answer row count drift")
    computed_count = 0
    unavailable_count = 0
    for row in rows:
        computed = row.get("answer_quality_delta_computed") is True
        before = row.get("before_answer") or {}
        after = row.get("after_answer") or {}
        if computed:
            computed_count += 1
            if before.get("execution_status") != "executed" or after.get("execution_status") != "executed":
                raise ValueError("v5_6 refactor comparison answer subset execution drift")
        else:
            if not _clean(row.get("answer_quality_blocked_reason")):
                raise ValueError("v5_6 refactor comparison answer blocked reason drift")
        if row.get("answer_execution_status") == "execution_unavailable":
            unavailable_count += 1
    subset = report.get("answer_quality_subset") or {}
    if subset.get("global_delta_claim_supported") is not False:
        raise ValueError("v5_6 refactor comparison answer quality claim drift")
    if subset.get("computed_row_count") != computed_count:
        raise ValueError("v5_6 refactor comparison answer subset count drift")
    if subset.get("execution_unavailable_row_count") != unavailable_count:
        raise ValueError("v5_6 refactor comparison answer unavailable count drift")


def _require_written_artifact(report: Mapping[str, Any], *, root: Path | str) -> None:
    repo_root = Path(root)
    paths = report.get("artifact_paths") or {}
    report_path = repo_root / str(paths.get("report_json") or "")
    if not report_path.exists():
        raise ValueError("v5_6 refactor comparison report artifact missing")
    hashes = report.get("artifact_sha256") or {}
    expected_report_hash = hashes.get("report_json_sha256")
    if expected_report_hash and expected_report_hash != common.sha256_file(report_path):
        raise ValueError("v5_6 refactor comparison report artifact hash drift")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _assert_no_forbidden_payload_keys(report)
    _require_identity(report)
    _require_closed_gates(report)
    _require_artifact_paths(report)
    _require_route_rows(report)
    _require_retrieval_rows(report)
    _require_answer_rows(report)
    if report.get("comparison_input_policy") != COMPARISON_INPUT_POLICY:
        raise ValueError("v5_6 refactor comparison input policy drift")
    if report.get("legacy_keyword_route_policy") != LEGACY_KEYWORD_POLICY:
        raise ValueError("v5_6 refactor comparison legacy keyword policy drift")
    if root is not None:
        _require_written_artifact(report, root=root)


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    payload = _json_clone(report)
    report_path = Path(root) / SHORT_REPORT_PATH
    common.write_json(report_path, payload)
    artifact_hashes = {"report_json_sha256": common.sha256_file(report_path)}
    check_report(payload, root=root)
    return payload, artifact_hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "v5_6_refactor_route_comparison_packet_diagnostic_nonprod",
        "generated_at": report["generated_at"],
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": report["status"],
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_consumed": 0,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "fixture_row_count": report["comparator_scope"]["fixture_row_count"],
        "route_changed_count": report["route_change_summary"]["route_changed_count"],
        "metadata_scoped_row_count": report["comparator_scope"]["scope_counts"]["metadata_scoped"],
        "query_only_row_count": report["comparator_scope"]["scope_counts"]["query_only"],
        "quality_delta_claim_supported": False,
        "retrieval_quality_delta_computed": False,
        "retrieval_quality_subset_computed_row_count": report["retrieval_quality_subset"]["computed_row_count"],
        "answer_quality_delta_computed": False,
        "answer_quality_subset_computed_row_count": report["answer_quality_subset"]["computed_row_count"],
        "answer_execution_unavailable_row_count": report["answer_quality_subset"]["execution_unavailable_row_count"],
        "protected_namespaces_touched": [],
        "training_dataset_created": False,
        "fine_tuning": False,
        "ft_a_execution": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
    }


def append_status(root: Path | str, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    status_path = Path(root) / STATUS_JSONL_PATH
    rows = common.read_jsonl(status_path)
    rows = [row for row in rows if row.get("short_run_id") != SHORT_RUN_ID]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    common.write_jsonl(status_path, rows)


def update_docs(root: Path | str, report: Mapping[str, Any]) -> None:
    progress_path = Path(root) / PROGRESS_DOC
    if not progress_path.exists():
        return
    block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} writes a single diagnostic-only comparison report at "
        f"`{SHORT_REPORT_PATH.as_posix()}`. It replays the prior query-keyword route heuristic against current "
        "policy/provider/LLM adjudication routing over a minimal fixture packet separated by source-metadata scope "
        f"and query-only scope (rows={report['comparator_scope']['fixture_row_count']}; "
        f"metadata_scoped={report['comparator_scope']['scope_counts']['metadata_scoped']}; "
        f"query_only={report['comparator_scope']['scope_counts']['query_only']}; families=TEXT/XLSX/PDF). "
        f"`current` remains `{CURRENT_RESOLVES_TO}` and the v5_6 official metric lane stays fail-closed. "
        "official_metric_input_rows=0, official_metric_input_rows_consumed=0, quality_delta_claim_supported=false, "
        "retrieval_quality_delta_computed=false globally, and answer_quality_delta_computed=false globally; only "
        f"subset tables are populated (retrieval valid rows={report['retrieval_quality_subset']['computed_row_count']}; "
        f"answer executed rows={report['answer_quality_subset']['computed_row_count']}). No gold/qrels/labels/"
        "expected/supporting/denominator/training/fine-tuning/FT-A/promotion/product-success/live-readiness gate is opened."
    )
    text = progress_path.read_text(encoding="utf-8")
    text = common.upsert_block_at_top(
        text,
        start_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
        block=block,
    )
    text = common.sync_last_updated(text, KST_DOC_DATE)
    progress_path.write_text(text, encoding="utf-8")
