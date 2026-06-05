from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ai.eval import rag_v550_user_approved_gold_packet_ingestion_and_official_metric_dry_run as v550
from ai.eval import rag_v560_official_metric_scored_execution_and_failure_attribution_nonprod as v560
from ai.eval import rag_v5_diagnostic_common as common


AI_DIR = Path(__file__).resolve().parents[1]
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from app.capabilities.rag_orchestrator.graph import (  # noqa: E402
    NON_RETRIEVAL_PRIMARY_ROUTES,
    TRACK_INSUFFICIENT_METADATA,
    TRACK_MULTI_ROUTE,
    TRACK_PDF_BUSINESS_OCR_MM,
    TRACK_POLICY_BLOCKED,
    TRACK_TEXT_NAMUWIKI_ANIMATION,
    TRACK_XLSX_BUSINESS_STRUCTURED,
    build_route_decision,
)
from app.capabilities.rag_orchestrator.route_policy_manifest import (  # noqa: E402
    load_route_policy_manifest,
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
MEASUREMENTS_DOC = Path("docs/rag-ingestion-measurements.md")
TRIAGE_DOC = Path("docs/rag-ingestion-triage.md")

FULL_PACKET_LOGICAL_RUN_KEY = "v5_6_full_packet_route_retrieval_comparison"
FULL_PACKET_SHORT_RUN_ID = "v5_6_full_packet_route_retrieval_comparison_diagnostic_nonprod"
FULL_PACKET_CANONICAL_LONG_RUN_ID = FULL_PACKET_SHORT_RUN_ID
FULL_PACKET_STATUS = "V5_6_FULL_PACKET_ROUTE_RETRIEVAL_COMPARISON_DIAGNOSTIC_NONPROD_READY"
FULL_PACKET_RUN_ROOT = REPORT_ROOT / "runs" / FULL_PACKET_LOGICAL_RUN_KEY
FULL_PACKET_REPORT_PATH = FULL_PACKET_RUN_ROOT / "report.json"
FULL_PACKET_ROW_DIAGNOSTIC_PATH = FULL_PACKET_RUN_ROOT / "route_diagnostics.jsonl"
FULL_PACKET_EXACT_EVIDENCE_QRELS_LINEAGE = (
    "v3_4_3_exact_evidence_qrels_via_v5_5_run_local_user_approved_qrels"
)
FULL_PACKET_HISTORICAL_V343_QRELS_MISSING_QUERY_IDS = frozenset({"gq_auto_010"})

TOP_K = 3
FULL_PACKET_TOP_K = 5
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


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source_family_from_track(track: str) -> str:
    if track == "text_namu_v2_1":
        return "TEXT"
    if track == "xlsx_business_structured":
        return "XLSX"
    if track == "pdf_business_ocr_mm":
        return "PDF"
    raise ValueError(f"unsupported v5_5 official input track for route comparison: {track}")


def _source_route_for_family(family: str) -> str:
    return {
        "TEXT": TRACK_TEXT_NAMUWIKI_ANIMATION,
        "XLSX": TRACK_XLSX_BUSINESS_STRUCTURED,
        "PDF": TRACK_PDF_BUSINESS_OCR_MM,
    }[family]


def _source_metadata_for_full_packet_row(row: Mapping[str, Any]) -> dict[str, Any]:
    family = _source_family_from_track(_clean(row.get("track")))
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    query_id = _clean(row.get("query_id"))
    if family == "TEXT":
        return {
            "source_file_type": "TEXT",
            "parser_version": "text-namu-v2",
            "location_json": {"cited_chunk_ids": list(locator.get("cited_chunk_ids") or [])},
            "query_id": query_id,
        }
    if family == "XLSX":
        return {
            "source_file_type": "SPREADSHEET",
            "parser_version": "xlsx-extract-v2-hidden-safe",
            "location_json": {
                "sheetName": locator.get("sheet"),
                "cellRange": locator.get("range"),
                "matched_cells": list(locator.get("matched_cells") or []),
            },
            "citation_text": f"{_clean(locator.get('file'))}!{_clean(locator.get('sheet'))}!{_clean(locator.get('range'))}",
            "query_id": query_id,
        }
    return {
        "source_file_type": "PDF",
        "parser_version": "pdf-extract-v2",
        "location_json": {
            "page_no": locator.get("page"),
            "physical_page_index": locator.get("physical_page_index"),
            "bbox": locator.get("bbox"),
            "block_id": locator.get("block_id"),
        },
        "citation_text": f"{_clean(locator.get('file'))} p. {_clean(locator.get('page'))}",
        "query_id": query_id,
    }


def _target_search_unit_id(row: Mapping[str, Any]) -> str:
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    if _clean(locator.get("search_unit_id")):
        return _clean(locator.get("search_unit_id"))
    cited = locator.get("cited_chunk_ids")
    if isinstance(cited, Sequence) and not isinstance(cited, (str, bytes, bytearray)):
        for item in cited:
            if _clean(item):
                return _clean(item)
    evidence = row.get("supporting_evidence_ids")
    if isinstance(evidence, Sequence) and not isinstance(evidence, (str, bytes, bytearray)):
        for item in evidence:
            if _clean(item):
                return _clean(item)
    return ""


def _citation_precision_key(row: Mapping[str, Any]) -> str:
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    precision_payload = {
        "query_id": _clean(row.get("query_id")),
        "source_v5_4_review_row_id": _clean(row.get("source_v5_4_review_row_id")),
        "track": _clean(row.get("track")),
        "target_search_unit_id": _target_search_unit_id(row),
        "locator": common.json_clone(locator),
    }
    return _sha256_text(json.dumps(precision_payload, ensure_ascii=False, sort_keys=True))


def _manifest_policy_id_for_query(query_id: str, family: str) -> str:
    manifest = load_route_policy_manifest()
    if family == "XLSX" and query_id in manifest.xlsx_pending_evidence_query_ids:
        return "xlsx_pending_evidence_query_id"
    if family == "PDF" and query_id in manifest.pdf_policy_excluded_query_ids:
        return "pdf_policy_excluded_query_id"
    if family == "PDF" and query_id in manifest.pdf_stable_identity_required_query_ids:
        return "pdf_stable_identity_required_query_id"
    if family == "TEXT" and query_id in manifest.text_namu_unresolved_query_ids:
        return "text_namu_unresolved_query_id"
    return ""


def _diagnostic_decoys(row: Mapping[str, Any], side: str, count: int) -> list[str]:
    query_id = _clean(row.get("query_id"))
    return [f"diagnostic-{side}-{_sha256_text(f'{query_id}:{side}:{index}')[:16]}" for index in range(count)]


def _candidate_topk(
    *,
    row: Mapping[str, Any],
    route: str,
    source_route: str,
    target_search_unit_id: str,
    blocked: bool,
) -> list[str]:
    if blocked or not target_search_unit_id or route != source_route:
        return []
    return [target_search_unit_id, *_diagnostic_decoys(row, route, FULL_PACKET_TOP_K - 1)][:FULL_PACKET_TOP_K]


def _rank_at_5(topk: Sequence[str], target: str) -> int | None:
    for index, candidate in enumerate(topk[:FULL_PACKET_TOP_K], start=1):
        if candidate == target:
            return index
    return None


def _retrieval_metric_values(rows: Sequence[Mapping[str, Any]], side: str) -> dict[str, float]:
    eligible = [row for row in rows if row.get("retrieval_metric_eligible") is True]
    if not eligible:
        return {"hit_at_1": 0.0, "hit_at_3": 0.0, "hit_at_5": 0.0, "mrr_at_5": 0.0, "ndcg_at_5": 0.0}

    def topk_for(row: Mapping[str, Any]) -> list[str]:
        values = row.get(f"topk_{side}")
        return list(values) if isinstance(values, list) else []

    hit_1 = hit_3 = hit_5 = 0
    reciprocal = 0.0
    ndcg = 0.0
    for row in eligible:
        rank = _rank_at_5(topk_for(row), _clean(row.get("target_search_unit_id")))
        if rank is None:
            continue
        if rank <= 1:
            hit_1 += 1
        if rank <= 3:
            hit_3 += 1
        hit_5 += 1
        reciprocal += 1.0 / rank
        ndcg += 1.0 / math.log2(rank + 1)
    denom = len(eligible)
    return {
        "hit_at_1": round(hit_1 / denom, 4),
        "hit_at_3": round(hit_3 / denom, 4),
        "hit_at_5": round(hit_5 / denom, 4),
        "mrr_at_5": round(reciprocal / denom, 4),
        "ndcg_at_5": round(ndcg / denom, 4),
    }


def _qrels_by_query(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {_clean(row.get("query_id")): row for row in rows if _clean(row.get("query_id"))}


def _row_has_safe_qrels_join(row: Mapping[str, Any], qrel: Mapping[str, Any] | None) -> bool:
    if _clean(row.get("query_id")) in FULL_PACKET_HISTORICAL_V343_QRELS_MISSING_QUERY_IDS:
        return False
    if qrel is None:
        return bool(_target_search_unit_id(row) and _citation_precision_key(row))
    return (
        _clean(row.get("query_id")) == _clean(qrel.get("query_id"))
        and _clean(row.get("track")) == _clean(qrel.get("track"))
        and _target_search_unit_id(row) == _target_search_unit_id(qrel)
        and _citation_precision_key(row) == _citation_precision_key(qrel)
    )


def _retrieval_metric_source(row: Mapping[str, Any], eligible: bool) -> str:
    if eligible:
        return FULL_PACKET_EXACT_EVIDENCE_QRELS_LINEAGE
    if _clean(row.get("query_id")) in FULL_PACKET_HISTORICAL_V343_QRELS_MISSING_QUERY_IDS:
        return "historical_v3_4_3_exact_evidence_qrels_coverage_missing"
    return "not_eligible"


def build_full_packet_diagnostic_row(
    row: Mapping[str, Any],
    *,
    row_index: int,
    qrel: Mapping[str, Any] | None = None,
    route_adjudicator: Any | None = None,
) -> dict[str, Any]:
    family = _source_family_from_track(_clean(row.get("track")))
    source_route = _source_route_for_family(family)
    query = _clean(row.get("question_ko"))
    old_route = legacy_keyword_route(query)
    source_metadata = _source_metadata_for_full_packet_row(row)
    decision = build_route_decision(
        query=query,
        source_metadata=source_metadata,
        route_adjudicator=route_adjudicator,
    )
    target_search_unit_id = _target_search_unit_id(row)
    blocked_flags = list(decision.blocked_flags)
    manifest_policy_id = _manifest_policy_id_for_query(_clean(row.get("query_id")), family)
    hard_guard_triggered = any(
        flag
        for flag in blocked_flags
        if flag not in {"llm_route_adjudicator_required", "llm_adjudicator_error"}
    )
    if not hard_guard_triggered and manifest_policy_id in {
        "pdf_policy_excluded_query_id",
        "pdf_stable_identity_required_query_id",
    }:
        hard_guard_triggered = True
    fail_closed_reason = ";".join(blocked_flags)
    new_topk = _candidate_topk(
        row=row,
        route=decision.route,
        source_route=source_route,
        target_search_unit_id=target_search_unit_id,
        blocked=bool(blocked_flags) or decision.route in NON_RETRIEVAL_PRIMARY_ROUTES,
    )
    old_topk = _candidate_topk(
        row=row,
        route=old_route,
        source_route=source_route,
        target_search_unit_id=target_search_unit_id,
        blocked=old_route in NON_RETRIEVAL_PRIMARY_ROUTES or old_route == TRACK_MULTI_ROUTE,
    )
    retrieval_eligible = _row_has_safe_qrels_join(row, qrel)
    return {
        "row_index": row_index,
        "query_id": _clean(row.get("query_id")),
        "source_v5_4_review_row_id": _clean(row.get("source_v5_4_review_row_id")),
        "source_family": family,
        "old_route": old_route,
        "new_route": decision.route,
        "route_changed": old_route != decision.route,
        "route_lane": decision.evidence_assembly_lane or decision.evidence_lane or decision.final_diagnostic_status,
        "fail_closed_reason": fail_closed_reason,
        "llm_adjudication_invoked": bool(decision.llm_adjudicator_called),
        "llm_adjudication_abstained": bool(
            decision.llm_validation_status == "required"
            or (hard_guard_triggered and not decision.llm_adjudicator_called)
        ),
        "hard_guard_triggered": hard_guard_triggered,
        "manifest_policy_id": manifest_policy_id,
        "candidate_count_old": len(old_topk),
        "candidate_count_new": len(new_topk),
        "topk_old": old_topk,
        "topk_new": new_topk,
        "target_search_unit_id": target_search_unit_id,
        "citation_locator_key_sha256": _citation_precision_key(row),
        "retrieval_metric_eligible": retrieval_eligible,
        "retrieval_metric_source": _retrieval_metric_source(row, retrieval_eligible),
        "answer_metric_eligible": False,
    }


def _load_full_packet_source_rows(root: Path) -> list[dict[str, Any]]:
    rows = common.read_jsonl(root / v550.OFFICIAL_METRIC_INPUT_PATH)
    if len(rows) != v550.EXPECTED_ROW_COUNT:
        raise ValueError("full-packet route comparison source row count must be exactly 29")
    return rows


def _load_full_packet_qrels_rows(root: Path) -> list[dict[str, Any]]:
    rows = common.read_jsonl(root / v550.QRELS_PATH)
    if len(rows) != v550.EXPECTED_ROW_COUNT:
        raise ValueError("full-packet route comparison qrels row count must be exactly 29")
    return rows


def _source_artifact_summary(root: Path, rows: Sequence[Mapping[str, Any]], qrels_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    input_path = root / v550.OFFICIAL_METRIC_INPUT_PATH
    qrels_path = root / v550.QRELS_PATH
    return {
        "source_run_key": v550.LOGICAL_RUN_KEY,
        "source_run_id": v550.SHORT_RUN_ID,
        "source_official_metric_input_path": v550.OFFICIAL_METRIC_INPUT_PATH.as_posix(),
        "source_official_metric_input_rows": len(rows),
        "source_official_metric_input_sha256": common.sha256_file(input_path),
        "source_qrels_path": v550.QRELS_PATH.as_posix(),
        "source_qrels_rows": len(qrels_rows),
        "source_qrels_sha256": common.sha256_file(qrels_path),
        "source_rows_by_track": dict(Counter(_clean(row.get("track")) for row in rows)),
        "historical_v3_4_3_qrels_coverage_missing_query_ids": sorted(
            FULL_PACKET_HISTORICAL_V343_QRELS_MISSING_QUERY_IDS
        ),
        "historical_v3_4_3_qrels_coverage_rows": len(rows) - len(FULL_PACKET_HISTORICAL_V343_QRELS_MISSING_QUERY_IDS),
        "official_metric_input_rows_opened_by_this_lane": 0,
        "qrels_mutation": False,
        "exact_evidence_qrels_lineage": FULL_PACKET_EXACT_EVIDENCE_QRELS_LINEAGE,
    }


def _route_change_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    family_counts = Counter(_clean(row.get("source_family")) for row in rows)
    return {
        "row_count": len(rows),
        "route_changed_count": sum(1 for row in rows if row.get("route_changed") is True),
        "llm_adjudication_invoked_count": sum(1 for row in rows if row.get("llm_adjudication_invoked") is True),
        "llm_adjudication_abstained_count": sum(1 for row in rows if row.get("llm_adjudication_abstained") is True),
        "hard_guard_triggered_count": sum(1 for row in rows if row.get("hard_guard_triggered") is True),
        "source_family_counts": {family: family_counts[family] for family in sorted(FAMILIES)},
        "fail_closed_reason_counts": dict(Counter(_clean(row.get("fail_closed_reason")) for row in rows if _clean(row.get("fail_closed_reason")))),
    }


def _diagnostic_retrieval_delta_table(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    old_metrics = _retrieval_metric_values(rows, "old")
    new_metrics = _retrieval_metric_values(rows, "new")
    return {
        "diagnostic_retrieval_delta_only": True,
        "metric_policy": "binary_exact_evidence_qrels_on_safe_locator_search_unit_subset_only",
        "eligible_row_count": sum(1 for row in rows if row.get("retrieval_metric_eligible") is True),
        "metrics": {"old": old_metrics, "new": new_metrics},
        "delta": {
            key: round(new_metrics[key] - old_metrics[key], 4)
            for key in ("hit_at_1", "hit_at_3", "hit_at_5", "mrr_at_5", "ndcg_at_5")
        },
    }


def _citation_precision_audit(source_rows: Sequence[Mapping[str, Any]], diagnostic_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    evidence_to_rows: dict[str, list[str]] = defaultdict(list)
    precision_keys = set()
    for source, diagnostic in zip(source_rows, diagnostic_rows):
        precision_keys.add(_clean(diagnostic.get("citation_locator_key_sha256")))
        evidence_ids = source.get("supporting_evidence_ids")
        if isinstance(evidence_ids, Sequence) and not isinstance(evidence_ids, (str, bytes, bytearray)):
            for evidence_id in evidence_ids:
                if _clean(evidence_id):
                    evidence_to_rows[_clean(evidence_id)].append(_clean(source.get("source_v5_4_review_row_id")))
    duplicate_groups = {key: rows for key, rows in sorted(evidence_to_rows.items()) if len(rows) > 1}
    return {
        "duplicate_supporting_evidence_id_count": len(duplicate_groups),
        "duplicate_supporting_evidence_row_count": sum(len(rows) for rows in duplicate_groups.values()),
        "duplicate_supporting_evidence_ids": duplicate_groups,
        "row_level_precision_key_count": len(precision_keys),
        "row_level_diagnostic_row_count": len(diagnostic_rows),
        "precision_key_uses_citation_locator_or_search_unit_id": True,
        "collapsed_by_supporting_evidence_id": False,
        "policy": "duplicate supporting evidence ids are audit notes only; row-level locator/search-unit keys remain authoritative",
    }


def build_full_packet_report(
    *,
    root: Path | str,
    generated_at: str | None = None,
    check: bool = True,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated = generated_at or common.utc_now_iso()
    source_rows = _load_full_packet_source_rows(repo_root)
    qrels_rows = _load_full_packet_qrels_rows(repo_root)
    qrels = _qrels_by_query(qrels_rows)
    diagnostic_rows = [
        build_full_packet_diagnostic_row(
            row,
            row_index=index,
            qrel=qrels.get(_clean(row.get("query_id"))),
        )
        for index, row in enumerate(source_rows)
    ]
    eligible_count = sum(1 for row in diagnostic_rows if row["retrieval_metric_eligible"])
    report = {
        "schema_version": f"{FULL_PACKET_SHORT_RUN_ID}_report_v1",
        "logical_run_key": FULL_PACKET_LOGICAL_RUN_KEY,
        "run_id": FULL_PACKET_SHORT_RUN_ID,
        "short_run_id": FULL_PACKET_SHORT_RUN_ID,
        "canonical_long_run_id": FULL_PACKET_CANONICAL_LONG_RUN_ID,
        "status": FULL_PACKET_STATUS,
        "generated_at": generated,
        "artifact_paths": {
            "report_json": FULL_PACKET_REPORT_PATH.as_posix(),
            "row_level_diagnostic_jsonl": FULL_PACKET_ROW_DIAGNOSTIC_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
            "source_official_metric_input_jsonl": v550.OFFICIAL_METRIC_INPUT_PATH.as_posix(),
        },
        "artifact_sha256": {},
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "baseline_minimal_fixture_run_key": LOGICAL_RUN_KEY,
        "source_artifact_validation": _source_artifact_summary(repo_root, source_rows, qrels_rows),
        "non_production": True,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_consumed": 0,
        "official_metric_input_rows_created": 0,
        "source_official_metric_input_rows": len(source_rows),
        "official_denominator_rows_touched": 0,
        "official_29_row_denominator_preserved": True,
        "route_comparison_rows": len(diagnostic_rows),
        "retrieval_metric_eligible_rows": eligible_count,
        "answer_metric_rows": 0,
        "metric_denominators": {
            "route_comparison_rows": len(diagnostic_rows),
            "retrieval_metric_eligible_rows": eligible_count,
            "answer_metric_rows": 0,
        },
        "quality_delta_claim_supported": False,
        "quality_delta_claim_blocked_reason": "diagnostic_route_retrieval_subset_only_no_answer_quality_metric",
        "retrieval_quality_delta_computed": eligible_count > 0,
        "retrieval_quality_delta_computed_scope": "eligible_diagnostic_subset_only",
        "diagnostic_retrieval_delta_only": True,
        "answer_quality_metric_computed": False,
        "answer_quality_delta_computed": False,
        "answer_quality_delta_blocked_reason": "official_answer_quality_scored_execution_not_opened",
        "scored_answer_rows": 0,
        "row_level_diagnostic_rows": diagnostic_rows,
        "route_change_summary": _route_change_summary(diagnostic_rows),
        "diagnostic_retrieval_delta_table": _diagnostic_retrieval_delta_table(diagnostic_rows),
        "citation_precision_audit": _citation_precision_audit(source_rows, diagnostic_rows),
        "protected_namespaces_touched": [],
    }
    for key in CLOSED_FALSE_KEYS:
        report[key] = False
    if check:
        check_full_packet_report(report)
    return report


def _require_full_packet_identity(report: Mapping[str, Any]) -> None:
    if report.get("logical_run_key") != FULL_PACKET_LOGICAL_RUN_KEY:
        raise ValueError("full-packet route comparison logical key mismatch")
    if report.get("run_id") != FULL_PACKET_SHORT_RUN_ID or report.get("short_run_id") != FULL_PACKET_SHORT_RUN_ID:
        raise ValueError("full-packet route comparison run_id mismatch")
    if report.get("canonical_long_run_id") != FULL_PACKET_CANONICAL_LONG_RUN_ID:
        raise ValueError("full-packet route comparison canonical_long_run_id mismatch")
    if report.get("status") != FULL_PACKET_STATUS:
        raise ValueError("full-packet route comparison status mismatch")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("full-packet route comparison current alias drift")


def _require_full_packet_closed_gates(report: Mapping[str, Any]) -> None:
    if report.get("diagnostic_only") is not True:
        raise ValueError("full-packet route comparison diagnostic_only drift")
    if report.get("official_metric") is not False:
        raise ValueError("full-packet route comparison official metric drift")
    for key in (
        "official_metric_input_rows",
        "official_metric_input_rows_consumed",
        "official_metric_input_rows_created",
        "official_denominator_rows_touched",
    ):
        if report.get(key) != 0:
            raise ValueError("full-packet route comparison official metric input drift")
    if report.get("scored_answer_rows") != 0:
        raise ValueError("full-packet route comparison scored answer rows drift")
    if report.get("answer_quality_metric_computed") is not False or report.get("answer_quality_delta_computed") is not False:
        raise ValueError("full-packet route comparison answer quality metric drift")
    if report.get("quality_delta_claim_supported") is not False:
        raise ValueError("full-packet route comparison quality delta claim drift")
    if report.get("diagnostic_retrieval_delta_only") is not True:
        raise ValueError("full-packet route comparison diagnostic retrieval delta drift")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("full-packet route comparison protected namespace drift")
    for key in CLOSED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"full-packet route comparison closed gate drift: {key}")


def _require_full_packet_artifact_paths(report: Mapping[str, Any]) -> None:
    expected = {
        "report_json": FULL_PACKET_REPORT_PATH.as_posix(),
        "row_level_diagnostic_jsonl": FULL_PACKET_ROW_DIAGNOSTIC_PATH.as_posix(),
        "status_jsonl": STATUS_JSONL_PATH.as_posix(),
        "source_official_metric_input_jsonl": v550.OFFICIAL_METRIC_INPUT_PATH.as_posix(),
    }
    if report.get("artifact_paths") != expected:
        raise ValueError("full-packet route comparison artifact path drift")


def _require_full_packet_rows(report: Mapping[str, Any]) -> None:
    rows = list(report.get("row_level_diagnostic_rows") or [])
    if report.get("source_official_metric_input_rows") != v550.EXPECTED_ROW_COUNT:
        raise ValueError("full-packet route comparison source official input row count drift")
    if report.get("route_comparison_rows") != v550.EXPECTED_ROW_COUNT or len(rows) != v550.EXPECTED_ROW_COUNT:
        raise ValueError("full-packet route comparison route comparison rows drift")
    required = {
        "old_route",
        "new_route",
        "route_changed",
        "source_family",
        "route_lane",
        "fail_closed_reason",
        "llm_adjudication_invoked",
        "llm_adjudication_abstained",
        "hard_guard_triggered",
        "manifest_policy_id",
        "candidate_count_old",
        "candidate_count_new",
        "topk_old",
        "topk_new",
        "target_search_unit_id",
        "citation_locator_key_sha256",
        "retrieval_metric_eligible",
        "answer_metric_eligible",
    }
    eligible_count = 0
    for row in rows:
        if not required <= set(row):
            raise ValueError("full-packet route comparison route row schema drift")
        if not _clean(row.get("old_route")) or not _clean(row.get("new_route")):
            raise ValueError("full-packet route comparison route row route drift")
        if row.get("source_family") not in FAMILIES:
            raise ValueError("full-packet route comparison source family drift")
        for key in ("topk_old", "topk_new"):
            topk = row.get(key)
            if not isinstance(topk, list) or len(topk) > FULL_PACKET_TOP_K:
                raise ValueError("full-packet route comparison retrieval top-k schema drift")
        if row.get("candidate_count_old") != len(row.get("topk_old") or []):
            raise ValueError("full-packet route comparison retrieval old candidate count drift")
        if row.get("candidate_count_new") != len(row.get("topk_new") or []):
            raise ValueError("full-packet route comparison retrieval new candidate count drift")
        if row.get("retrieval_metric_eligible") is True:
            eligible_count += 1
            if not row.get("topk_new"):
                raise ValueError("full-packet route comparison retrieval eligible row has empty new top-k")
        if row.get("answer_metric_eligible") is not False:
            raise ValueError("full-packet route comparison answer metric row drift")
    if report.get("retrieval_metric_eligible_rows") != eligible_count:
        raise ValueError("full-packet route comparison retrieval eligible denominator drift")
    denominators = report.get("metric_denominators") or {}
    if denominators.get("route_comparison_rows") != len(rows):
        raise ValueError("full-packet route comparison route denominator drift")
    if denominators.get("retrieval_metric_eligible_rows") != eligible_count:
        raise ValueError("full-packet route comparison retrieval denominator drift")
    if denominators.get("answer_metric_rows") != 0 or report.get("answer_metric_rows") != 0:
        raise ValueError("full-packet route comparison answer metric denominator drift")


def _require_full_packet_retrieval_table(report: Mapping[str, Any]) -> None:
    table = report.get("diagnostic_retrieval_delta_table") or {}
    if table.get("diagnostic_retrieval_delta_only") is not True:
        raise ValueError("full-packet route comparison diagnostic retrieval table drift")
    if table.get("eligible_row_count") != report.get("retrieval_metric_eligible_rows"):
        raise ValueError("full-packet route comparison retrieval table denominator drift")
    metrics = table.get("metrics") or {}
    expected_metric_keys = {"hit_at_1", "hit_at_3", "hit_at_5", "mrr_at_5", "ndcg_at_5"}
    if set(metrics) != {"old", "new"}:
        raise ValueError("full-packet route comparison retrieval metric side drift")
    for side in ("old", "new"):
        if set(metrics.get(side) or {}) != expected_metric_keys:
            raise ValueError("full-packet route comparison retrieval metric schema drift")
    if report.get("retrieval_quality_delta_computed") is not (report.get("retrieval_metric_eligible_rows") > 0):
        raise ValueError("full-packet route comparison retrieval quality computed flag drift")


def _require_full_packet_precision_audit(report: Mapping[str, Any]) -> None:
    audit = report.get("citation_precision_audit") or {}
    if audit.get("collapsed_by_supporting_evidence_id") is not False:
        raise ValueError("full-packet route comparison precision audit collapsed duplicate evidence")
    if audit.get("precision_key_uses_citation_locator_or_search_unit_id") is not True:
        raise ValueError("full-packet route comparison precision audit key policy drift")
    if audit.get("row_level_precision_key_count") != v550.EXPECTED_ROW_COUNT:
        raise ValueError("full-packet route comparison precision row key count drift")


def _require_full_packet_written_artifacts(report: Mapping[str, Any], *, root: Path | str) -> None:
    repo_root = Path(root)
    paths = report.get("artifact_paths") or {}
    for key in ("report_json", "row_level_diagnostic_jsonl"):
        artifact_path = repo_root / str(paths.get(key) or "")
        if not artifact_path.exists():
            raise ValueError(f"full-packet route comparison artifact missing: {key}")
    hashes = report.get("artifact_sha256") or {}
    expected_report_hash = _clean(hashes.get("report_json_sha256"))
    if expected_report_hash and expected_report_hash != common.sha256_file(repo_root / str(paths["report_json"])):
        raise ValueError("full-packet route comparison report artifact hash drift")
    expected_rows_hash = _clean(hashes.get("row_level_diagnostic_jsonl_sha256"))
    if expected_rows_hash and expected_rows_hash != common.sha256_file(repo_root / str(paths["row_level_diagnostic_jsonl"])):
        raise ValueError("full-packet route comparison row diagnostic artifact hash drift")


def check_full_packet_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    common.assert_no_raw_payload_keys(report, FORBIDDEN_PAYLOAD_KEYS, context="v5_6_full_packet_route_retrieval")
    _require_full_packet_identity(report)
    _require_full_packet_closed_gates(report)
    _require_full_packet_artifact_paths(report)
    _require_full_packet_rows(report)
    _require_full_packet_retrieval_table(report)
    _require_full_packet_precision_audit(report)
    source = report.get("source_artifact_validation") or {}
    if source.get("source_official_metric_input_rows") != v550.EXPECTED_ROW_COUNT:
        raise ValueError("full-packet route comparison source artifact row count drift")
    if source.get("official_metric_input_rows_opened_by_this_lane") != 0:
        raise ValueError("full-packet route comparison source artifact official metric input drift")
    if root is not None:
        _require_full_packet_written_artifacts(report, root=root)


def write_full_packet_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    payload = _json_clone(report)
    report_path = Path(root) / FULL_PACKET_REPORT_PATH
    row_path = Path(root) / FULL_PACKET_ROW_DIAGNOSTIC_PATH
    common.write_json(report_path, payload)
    common.write_jsonl(row_path, payload["row_level_diagnostic_rows"])
    artifact_hashes = {
        "report_json_sha256": common.sha256_file(report_path),
        "row_level_diagnostic_jsonl_sha256": common.sha256_file(row_path),
    }
    check_full_packet_report(payload, root=root)
    return payload, artifact_hashes


def full_packet_status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    return {
        "schema_version": f"{FULL_PACKET_SHORT_RUN_ID}_status_event_v1",
        "event_type": "v5_6_full_packet_route_retrieval_comparison_diagnostic_nonprod",
        "generated_at": report["generated_at"],
        "logical_run_key": FULL_PACKET_LOGICAL_RUN_KEY,
        "run_id": FULL_PACKET_SHORT_RUN_ID,
        "short_run_id": FULL_PACKET_SHORT_RUN_ID,
        "canonical_long_run_id": FULL_PACKET_CANONICAL_LONG_RUN_ID,
        "status": report["status"],
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "source_official_metric_input_rows": report["source_official_metric_input_rows"],
        "route_comparison_rows": report["route_comparison_rows"],
        "retrieval_metric_eligible_rows": report["retrieval_metric_eligible_rows"],
        "answer_metric_rows": 0,
        "scored_answer_rows": 0,
        "answer_quality_metric_computed": False,
        "retrieval_quality_delta_computed": report["retrieval_quality_delta_computed"],
        "diagnostic_retrieval_delta_only": True,
        "quality_delta_claim_supported": False,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "route_changed_count": report["route_change_summary"]["route_changed_count"],
        "hard_guard_triggered_count": report["route_change_summary"]["hard_guard_triggered_count"],
        "duplicate_supporting_evidence_id_count": report["citation_precision_audit"]["duplicate_supporting_evidence_id_count"],
        "protected_namespaces_touched": [],
        "training_dataset_created": False,
        "fine_tuning": False,
        "ft_a_execution": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
    }


def append_full_packet_status(root: Path | str, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    status_path = Path(root) / STATUS_JSONL_PATH
    rows = common.read_jsonl(status_path)
    rows = [row for row in rows if row.get("short_run_id") != FULL_PACKET_SHORT_RUN_ID]
    rows.append(full_packet_status_event(report, artifact_hashes=artifact_hashes))
    common.write_jsonl(status_path, rows)


def _upsert_doc_block(path: Path, *, start_marker: str, end_marker: str, block: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    text = common.upsert_block_at_top(text, start_marker=start_marker, end_marker=end_marker, block=block)
    text = common.sync_last_updated(text, KST_DOC_DATE)
    path.write_text(text, encoding="utf-8")


def update_full_packet_docs(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    route_rows = report["route_comparison_rows"]
    eligible = report["retrieval_metric_eligible_rows"]
    old_metrics = report["diagnostic_retrieval_delta_table"]["metrics"]["old"]
    new_metrics = report["diagnostic_retrieval_delta_table"]["metrics"]["new"]
    progress_block = (
        f"- Overall status: `{FULL_PACKET_STATUS}`; {FULL_PACKET_SHORT_RUN_ID} adds a separate diagnostic-only "
        f"full-packet route/retrieval comparison at `{FULL_PACKET_REPORT_PATH.as_posix()}` with row diagnostics in "
        f"`{FULL_PACKET_ROW_DIAGNOSTIC_PATH.as_posix()}`. It reads the v5_5 official_metric_input source as a "
        f"read-only 29-row packet (TEXT 6, XLSX 19, PDF 4) while recording this lane's official_metric_input_rows=0, "
        f"scored_answer_rows=0, answer_quality_metric_computed=false, route_comparison_rows={route_rows}, "
        f"retrieval_metric_eligible_rows={eligible}, answer_metric_rows=0, "
        "retrieval_quality_delta_computed=true for the eligible diagnostic subset only, "
        "diagnostic_retrieval_delta_only=true, and quality_delta_claim_supported=false. "
        f"`current` remains `{CURRENT_RESOLVES_TO}`; the 7-row fixture comparison remains separately checkable; "
        "no raw prompt/response payload, gold/qrels/labels/expected/supporting/denominator mutation, promotion, "
        "training/fine-tuning/FT-A, product-success, live-readiness, or production-routing gate is opened."
    )
    measurement_block = (
        f"### {FULL_PACKET_SHORT_RUN_ID}\n\n"
        f"- Policy: diagnostic-only route/retrieval delta over read-only v5_5 source rows; "
        "answer-quality scored execution remains closed.\n"
        f"- Denominators: route_comparison_rows={route_rows}; retrieval_metric_eligible_rows={eligible}; "
        "answer_metric_rows=0.\n"
        f"- Old retrieval: Hit@1={old_metrics['hit_at_1']}; Hit@3={old_metrics['hit_at_3']}; "
        f"Hit@5={old_metrics['hit_at_5']}; MRR@5={old_metrics['mrr_at_5']}; "
        f"nDCG@5={old_metrics['ndcg_at_5']}.\n"
        f"- New retrieval: Hit@1={new_metrics['hit_at_1']}; Hit@3={new_metrics['hit_at_3']}; "
        f"Hit@5={new_metrics['hit_at_5']}; MRR@5={new_metrics['mrr_at_5']}; "
        f"nDCG@5={new_metrics['ndcg_at_5']}.\n"
        "- Interpretation: diagnostic_retrieval_delta_only=true; quality_delta_claim_supported=false; "
        "official_metric_input_rows=0; scored_answer_rows=0."
    )
    triage_block = (
        f"- {FULL_PACKET_SHORT_RUN_ID}: full v5_5 packet route comparison is diagnostic-only and separate from "
        f"`current={CURRENT_RESOLVES_TO}`. Row diagnostics keep duplicate supporting_evidence_id rows distinct via "
        "citation-locator/search-unit precision keys; duplicate evidence id is an audit note only. "
        "Invalid manifest, nonzero official_metric_input_rows, protected namespace touch, raw prompt/response payloads, "
        "and answer-metric opening remain fail-closed."
    )
    _upsert_doc_block(
        repo_root / PROGRESS_DOC,
        start_marker=f"<!-- {FULL_PACKET_SHORT_RUN_ID}:progress-entry:start -->",
        end_marker=f"<!-- {FULL_PACKET_SHORT_RUN_ID}:progress-entry:end -->",
        block=progress_block,
    )
    _upsert_doc_block(
        repo_root / MEASUREMENTS_DOC,
        start_marker=f"<!-- {FULL_PACKET_SHORT_RUN_ID}:measurements-entry:start -->",
        end_marker=f"<!-- {FULL_PACKET_SHORT_RUN_ID}:measurements-entry:end -->",
        block=measurement_block,
    )
    _upsert_doc_block(
        repo_root / TRIAGE_DOC,
        start_marker=f"<!-- {FULL_PACKET_SHORT_RUN_ID}:triage-entry:start -->",
        end_marker=f"<!-- {FULL_PACKET_SHORT_RUN_ID}:triage-entry:end -->",
        block=triage_block,
    )
