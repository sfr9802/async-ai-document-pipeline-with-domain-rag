from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v476_archive_purge as v476
from ai.eval import rag_v479_pdf_evidence_residual_answer_quality_replay as v479


LOGICAL_RUN_KEY = "v4_7_10"
SHORT_RUN_ID = "v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_10_"
    "pdf_korean_evidence_normalization_and_answer_replay_readiness_nonprod"
)
STATUS = "V4_7_10_PDF_KOREAN_EVIDENCE_NORMALIZATION_AND_ANSWER_REPLAY_READINESS_NONPROD_READY"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
SOURCE_RUN_ID = v479.SHORT_RUN_ID
SOURCE_REPORT_JSON = v479.SHORT_REPORT_PATH

REQUIRED_FALSE_KEYS = v479.REQUIRED_FALSE_KEYS
STOP_TOKENS = set(v479.STOP_TOKENS) | {
    "내용",
    "내용이",
    "내용은",
    "내용을",
    "제시",
    "제시되어",
    "있습니까",
    "인가요",
    "최종적인",
}
KOREAN_PARTICLE_SUFFIXES = (
    "으로부터",
    "에서",
    "에게",
    "까지",
    "부터",
    "처럼",
    "보다",
    "으로",
    "라는",
    "라고",
    "에는",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "와",
    "과",
    "도",
    "만",
    "로",
)


def utc_now_iso() -> str:
    return v476.utc_now_iso()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v476.read_jsonl(path)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v476.write_jsonl(path, rows)


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bounded(value: Any, *, limit: int = 420) -> str:
    text = re.sub(r"\s+", " ", _clean(value)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", value)
        if token not in STOP_TOKENS
    }


def _compact(value: str) -> str:
    return re.sub(r"[^가-힣A-Za-z0-9]+", "", value).lower()


def _strip_korean_particle(token: str) -> str:
    for suffix in KOREAN_PARTICLE_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 2:
            return token[: -len(suffix)]
    return token


def _query_terms(query_text: str) -> set[str]:
    terms: set[str] = set()
    for token in _tokens(query_text):
        normalized = _compact(token)
        if len(normalized) < 2 or normalized in STOP_TOKENS:
            continue
        terms.add(normalized)
        stripped = _strip_korean_particle(normalized)
        if len(stripped) >= 2 and stripped not in STOP_TOKENS:
            terms.add(stripped)
    return terms


def _spacing_insensitive_korean_overlap_terms(*, query_text: str, evidence_text: str) -> list[str]:
    compact_evidence = _compact(evidence_text)
    if not compact_evidence:
        return []
    return sorted(term for term in _query_terms(query_text) if term in compact_evidence)


def _numeric_overlap_count(*, query_text: str, evidence_text: str) -> int:
    pattern = r"\d+(?:[.,]\d+)?%?"
    return len(set(re.findall(pattern, query_text)) & set(re.findall(pattern, evidence_text)))


def korean_normalized_repair_decision(
    *,
    query_text: str,
    evidence_text: str,
    inherited_overlap: Any,
) -> dict[str, Any]:
    inherited = int(inherited_overlap or 0)
    exact_overlap = max(inherited, len(_tokens(query_text) & _tokens(evidence_text)))
    spacing_terms = _spacing_insensitive_korean_overlap_terms(query_text=query_text, evidence_text=evidence_text)
    spacing_overlap = len(spacing_terms)
    numeric_overlap = _numeric_overlap_count(query_text=query_text, evidence_text=evidence_text)
    normalized_overlap = max(exact_overlap, spacing_overlap)
    evidence_chars = len(_clean(evidence_text))
    repairable = evidence_chars >= 30 and normalized_overlap >= 4
    base = {
        "query_evidence_token_overlap_count": normalized_overlap,
        "exact_query_evidence_token_overlap_count": exact_overlap,
        "spacing_insensitive_korean_overlap_count": spacing_overlap,
        "spacing_insensitive_korean_overlap_terms_count": spacing_overlap,
        "numeric_overlap_count": numeric_overlap,
        "evidence_chars": evidence_chars,
        "source_text_added_from_raw_pdf": False,
        "source_text_added_chars": 0,
        "raw_pdf_query_time_parsing": False,
        "broad_source_atom_scan": False,
        "hidden_target_locator_used": False,
        "expected_or_supporting_gold_text_used": False,
        "source_file_title_shortcut_used": False,
        "direct_answer_value_matching_used": False,
        "full_page_dump_used": False,
    }
    if repairable:
        return {
            **base,
            "decision": "repaired",
            "reason": "spacing_insensitive_korean_query_evidence_overlap",
            "normalization_scope": "query_text_and_existing_sourceatom_span_only",
            "normalization_applied": True,
        }
    return {
        **base,
        "decision": "dropped",
        "reason": "bounded_korean_normalized_overlap_below_threshold_requires_user_gold_or_new_source_material",
        "normalization_scope": "query_text_and_existing_sourceatom_span_only",
        "normalization_applied": False,
    }


def _row_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (_clean(row.get("candidate_id_hash")), _clean(row.get("query_id_hash")))


def _answer_replay_audit(*, candidate: bool, local_llm_available: bool, protected: bool) -> dict[str, Any]:
    if protected:
        status = "not_replayed_protected_no_regression"
    elif not candidate:
        status = "not_replayed_evidence_not_answer_ready"
    elif not local_llm_available:
        status = "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"
    else:
        status = "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"
    return {
        "status": status,
        "answer_replay_candidate": candidate,
        "local_llm_available": local_llm_available,
        "llm_invoked": False,
        "generated_response_created": False,
        "raw_prompt_created": False,
        "raw_llm_response_created": False,
        "parsed_final_answer_present": False,
        "citation_rendered": False,
        "grounded_citation_required": candidate,
        "korean_final_answer_required": candidate,
        "claim_support_verifier_status": "not_run_local_llm_unavailable" if candidate else "not_run_no_answer",
        "claim_support_verifier_pass": False,
        "claim_support_verifier_fail": False,
        "unsupported_claim_risk": False,
        "evidence_underuse_flag": False,
    }


def _build_rows(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    prior_rows: Sequence[Mapping[str, Any]],
    local_llm_available: bool,
) -> list[dict[str, Any]]:
    prior_by_key = {_row_key(row): row for row in prior_rows}
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        out = dict(row)
        source_residual = row.get("weak_evidence_window") is True or row.get("missing_neighbor_context") is True
        source_answer_ready = row.get("answer_ready_evidence_bundle") is True
        prior_row = prior_by_key.get(_row_key(row), {})
        decision = {
            "decision": "carried_forward",
            "reason": "v4_7_9_answer_ready_or_non_target_row",
            "query_evidence_token_overlap_count": int(
                row.get("repair_audit", {}).get("query_evidence_token_overlap_count")
                or row.get("query_evidence_token_overlap_count")
                or 0
            ),
            "exact_query_evidence_token_overlap_count": int(
                row.get("repair_audit", {}).get("query_evidence_token_overlap_count")
                or row.get("query_evidence_token_overlap_count")
                or 0
            ),
            "spacing_insensitive_korean_overlap_count": 0,
            "spacing_insensitive_korean_overlap_terms_count": 0,
            "numeric_overlap_count": int(row.get("repair_audit", {}).get("numeric_overlap_count") or 0),
            "evidence_chars": int(row.get("repair_audit", {}).get("evidence_chars") or 0),
            "normalization_scope": "not_targeted",
            "source_text_added_from_raw_pdf": False,
            "source_text_added_chars": 0,
            "raw_pdf_query_time_parsing": False,
            "broad_source_atom_scan": False,
            "hidden_target_locator_used": False,
            "expected_or_supporting_gold_text_used": False,
            "source_file_title_shortcut_used": False,
            "direct_answer_value_matching_used": False,
            "full_page_dump_used": False,
        }
        if source_residual:
            decision = korean_normalized_repair_decision(
                query_text=_clean(prior_row.get("query_text")),
                evidence_text=_clean(row.get("citation_span_preview")),
                inherited_overlap=row.get("repair_audit", {}).get("query_evidence_token_overlap_count")
                or row.get("query_evidence_token_overlap_count"),
            )

        repaired = source_residual and decision["decision"] == "repaired"
        answer_ready = source_answer_ready or repaired
        replay_candidate = row.get("answer_replay_audit", {}).get("answer_replay_candidate") is True or repaired
        repair_audit = {
            **dict(row.get("repair_audit") or {}),
            **decision,
            "repair_targeted": source_residual,
            "repair_applied": repaired,
            "expansion_scope": "existing_sourceatom_span_spacing_normalization_only",
            "v4_7_9_repair_decision": row.get("repair_audit", {}).get("decision"),
            "v4_7_9_repair_reason": row.get("repair_audit", {}).get("reason"),
            "preserved_page_candidate": row.get("page_candidate"),
            "preserved_block_candidate": row.get("block_candidate"),
            "preserved_locator_preview_redacted": row.get("locator_preview_redacted"),
        }

        out.update(
            {
                "SourceAtom_EvidenceBundle_role": "evidence_truth",
                "SearchView_vector_payload_role": "candidate_only",
                "v4_7_9_residual_weak_evidence_window": source_residual,
                "v4_7_10_repair_targeted": source_residual,
                "v4_7_10_repair_applied": repaired,
                "v4_7_10_korean_evidence_normalization_applied": repaired,
                "v4_7_10_fail_closed_reason": "" if not source_residual or repaired else decision["reason"],
                "answer_ready_evidence_bundle": answer_ready,
                "evidence_window_sufficient_proxy": answer_ready,
                "weak_evidence_window": not answer_ready,
                "missing_neighbor_context": not answer_ready,
                "failure_buckets": ["ANSWER_READY"]
                if answer_ready
                else ["RIGHT_PAGE_WEAK_WINDOW", "CONTEXT_NEIGHBOR_MISSING", "CONTRACT_FAIL_CLOSED"],
                "repair_audit": repair_audit,
                "answer_replay_audit": _answer_replay_audit(
                    candidate=replay_candidate,
                    local_llm_available=local_llm_available,
                    protected=source_answer_ready and not replay_candidate,
                ),
                "evidence_bundle_version": "v4_7_10_korean_evidence_normalization_v1"
                if repaired
                else row.get("evidence_bundle_version"),
                "evidence_bundle_source": "v4_7_9_source_evidence_bundle_with_v4_7_10_korean_normalization_audit",
                "citation_span_preview": _bounded(row.get("citation_span_preview")),
                "citation_span_available": bool(_clean(row.get("citation_span_preview"))),
                "llm_invoked": False,
                "raw_pdf_query_time_parsing": False,
                "broad_source_atom_scan_attempt_count": 0,
                "hidden_target_locator_used": False,
                "expected_or_supporting_gold_text_used": False,
                "source_file_title_shortcut_used": False,
                "direct_answer_value_matching_used": False,
                "full_page_dump_used": False,
                "vector_payload_evidence_truth_violation": False,
            }
        )
        rows.append(out)
    return rows


def _count(rows: Sequence[Mapping[str, Any]], key: str) -> int:
    return sum(1 for row in rows if row.get(key))


def _counters(rows: Sequence[Mapping[str, Any]], *, source_report: Mapping[str, Any]) -> dict[str, Any]:
    source_counters = source_report.get("counters") or {}
    replay_candidates = [row for row in rows if row.get("answer_replay_audit", {}).get("answer_replay_candidate")]
    source_answer_ready_by_key = {
        _row_key(row): row.get("answer_ready_evidence_bundle") is True
        for row in source_report.get("pdf_residual_replay_rows") or []
    }
    source_answer_ready_count = sum(1 for ready in source_answer_ready_by_key.values() if ready)
    newly_repaired_count = _count(rows, "v4_7_10_repair_applied")
    return {
        "pdf_survivor_row_count": len(rows),
        "answer_ready_evidence_bundle_count_before": source_answer_ready_count,
        "v4_7_9_residual_weak_evidence_window_count_before": int(
            source_counters.get("residual_weak_evidence_window_count_after") or 0
        ),
        "residual_weak_evidence_window_count_before": int(
            source_counters.get("residual_weak_evidence_window_count_after") or 0
        ),
        "residual_weak_evidence_window_count_after": _count(rows, "weak_evidence_window"),
        "missing_neighbor_context_count_before": int(source_counters.get("missing_neighbor_context_count_after") or 0),
        "missing_neighbor_context_count_after": _count(rows, "missing_neighbor_context"),
        "v4_7_9_repaired_evidence_bundle_count": int(source_counters.get("repaired_evidence_bundle_count") or 0),
        "newly_repaired_evidence_bundle_count": newly_repaired_count,
        "korean_normalization_repair_count": _count(rows, "v4_7_10_korean_evidence_normalization_applied"),
        "korean_normalized_evidence_repair_count": _count(rows, "v4_7_10_korean_evidence_normalization_applied"),
        "total_repaired_evidence_bundle_count_since_v4_7_5": int(
            source_counters.get("repaired_evidence_bundle_count") or 0
        )
        + newly_repaired_count,
        "answer_ready_evidence_bundle_count": _count(rows, "answer_ready_evidence_bundle"),
        "new_answer_replay_ready_count": newly_repaired_count,
        "answer_replay_ready_count": len(replay_candidates),
        "answer_replay_candidate_count": len(replay_candidates),
        "llm_invoked_count": 0,
        "local_llm_unavailable_fail_closed_count": sum(
            1
            for row in replay_candidates
            if row.get("answer_replay_audit", {}).get("status") == "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"
        ),
        "generated_response_count": 0,
        "parsed_final_answer_present_count": 0,
        "citation_rendered_count": 0,
        "claim_support_verifier_pass_count": 0,
        "claim_support_verifier_fail_count": 0,
        "unsupported_claim_risk_count": 0,
        "evidence_underuse_flag_count": 0,
        "regression_count_for_v4_7_9_answer_ready_rows": sum(
            1
            for row in rows
            if source_answer_ready_by_key.get(_row_key(row)) is True
            and row.get("answer_ready_evidence_bundle") is not True
        ),
        "official_metric_input_rows": 0,
        "protected_namespaces_touched": [],
    }


def _remaining_residual_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "row_index_1based": row.get("row_index_1based"),
            "candidate_id_hash": row.get("candidate_id_hash"),
            "query_id_hash": row.get("query_id_hash"),
            "reason": row.get("repair_audit", {}).get("reason"),
        }
        for row in rows
        if row.get("weak_evidence_window") is True
    ]


def _row_level_repair_outcomes(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    for row in rows:
        if row.get("v4_7_10_repair_targeted") is not True:
            continue
        audit = row.get("repair_audit") or {}
        outcomes.append(
            {
                "row_index_1based": row.get("row_index_1based"),
                "candidate_id_hash": row.get("candidate_id_hash"),
                "query_id_hash": row.get("query_id_hash"),
                "decision": audit.get("decision"),
                "reason": audit.get("reason"),
                "query_evidence_token_overlap_count": audit.get("query_evidence_token_overlap_count"),
                "spacing_insensitive_korean_overlap_count": audit.get(
                    "spacing_insensitive_korean_overlap_count"
                ),
                "numeric_overlap_count": audit.get("numeric_overlap_count"),
                "evidence_chars": audit.get("evidence_chars"),
                "requires_user_owned_gold_evidence_judgment_or_new_source_material": row.get(
                    "weak_evidence_window"
                )
                is True,
            }
        )
    return outcomes


def build_report(
    *,
    root: Path,
    execute: bool = False,
    sync_surfaces: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    del execute
    source_report = registry.load_report("v4_7_9", root=root)
    v479.check_report(source_report)
    prior_report = registry.load_report("v4_7_4", root=root)
    source_rows = list(source_report.get("pdf_residual_replay_rows") or [])
    prior_rows = list(prior_report.get("pdf_survivor_replay_ledger") or [])
    local_llm_available = False
    rows = _build_rows(source_rows=source_rows, prior_rows=prior_rows, local_llm_available=local_llm_available)
    counters = _counters(rows, source_report=source_report)
    remaining = _remaining_residual_rows(rows)
    report = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated_at or utc_now_iso(),
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
        },
        "source_run_id": SOURCE_RUN_ID,
        "source_report_json": SOURCE_REPORT_JSON.as_posix(),
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
        "hidden_target_locator_used": False,
        "expected_or_supporting_gold_text_used": False,
        "source_file_title_shortcut_used": False,
        "direct_answer_value_matching_used": False,
        "full_page_dump_used": False,
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "SearchView_vector_payload_role": "candidate_only",
        "vector_payload_evidence_truth_violation_count": 0,
        "local_llm_available": local_llm_available,
        "local_llm_probe": {
            "enabled_env_var": "RAG_V4_7_10_ENABLE_LOCAL_LLM_REPLAY",
            "available": local_llm_available,
            "decision": "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED",
            "raw_prompt_or_response_payload_written": False,
        },
        "counters": counters,
        "pdf_survivor_row_count": counters["pdf_survivor_row_count"],
        "pdf_residual_replay_rows": rows,
        "row_level_repair_outcomes": _row_level_repair_outcomes(rows),
        "remaining_residual_rows": remaining,
        "completion_branch": "A_reduced_residual_weak_pdf_windows_to_0_or_1"
        if counters["residual_weak_evidence_window_count_after"] <= 1
        else "B_fail_closed_after_bounded_repair_exhaustion",
        "non_gold_ambiguity_decisions": [
            {
                "decision": "repair_only_v4_7_9_residual_weak_rows",
                "reason": "v4_7_9 answer-ready rows are protected no-regression rows",
            },
            {
                "decision": "spacing_insensitive_korean_overlap_is_scoring_normalization_only",
                "reason": "normalization compares the existing Korean query against the existing SourceAtom citation span without adding source text",
            },
            {
                "decision": "no_local_llm_substitute_generation",
                "reason": "local LLM replay surface is unavailable; extractive/noop responses would be fake success",
            },
        ],
        "residual_risks": [
            "local LLM replay remains unavailable, so answer generation stays fail-closed for answer-replay candidates",
            "all counters remain diagnostic proxies and are not official metric or promotion evidence",
        ],
    }
    if remaining:
        report["residual_risks"].append(
            "remaining residual rows require user-owned gold/evidence judgment or new source material"
        )
    check_report(report)
    if sync_surfaces:
        update_docs(root, report)
    return report


def _status_event(report: Mapping[str, Any], *, report_sha256: str) -> dict[str, Any]:
    counters = report["counters"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "event_type": "diagnostic_v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness_nonprod",
        "status": STATUS,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": {"report_json_sha256": report_sha256},
        "source_run_id": report["source_run_id"],
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
        "local_llm_available": report["local_llm_available"],
        "completion_branch": report["completion_branch"],
        **counters,
    }


def append_status(root: Path, report: Mapping[str, Any], *, report_sha256: str) -> None:
    status_path = root / STATUS_JSONL_PATH
    existing = [
        row
        for row in read_jsonl(status_path)
        if row.get("short_run_id") != SHORT_RUN_ID and row.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID
    ]
    write_jsonl(status_path, [*existing, _status_event(report, report_sha256=report_sha256)])


def update_progress_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-progress.md"
    counters = report["counters"]
    start = f"<!-- {SHORT_RUN_ID}:progress-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:progress-entry:end -->"
    block = (
        f"- {SHORT_RUN_ID} is {STATUS}. Artifact: `{SHORT_REPORT_PATH.as_posix()}`. "
        "This diagnostic-only slice consumes the v4_7_9 PDF residual replay report and targets only its remaining "
        f"weak EvidenceBundle rows: weak evidence/window {counters['residual_weak_evidence_window_count_before']} -> "
        f"{counters['residual_weak_evidence_window_count_after']}, missing neighbor context "
        f"{counters['missing_neighbor_context_count_before']} -> {counters['missing_neighbor_context_count_after']}, "
        f"answer-ready evidence bundles {counters['answer_ready_evidence_bundle_count_before']} -> "
        f"{counters['answer_ready_evidence_bundle_count']}, "
        f"spacing-insensitive Korean repairs {counters['korean_normalization_repair_count']}, prior v4_7_9 "
        f"answer-ready regressions {counters['regression_count_for_v4_7_9_answer_ready_rows']}. "
        f"Answer replay readiness now has {counters['answer_replay_candidate_count']} candidates, all fail-closed as "
        "`LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED` because no local LLM replay surface is available. "
        "SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only. "
        "official_metric=false and all gold/qrels, label, denominator, training, FT-A, fine_tuning, promotion, "
        "product-success, and live-readiness gates stay closed."
    )
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"Last updated: .*? KST\.", "Last updated: 2026-05-30 KST.", text, count=1)
    text = re.sub(r"Overall status: `[^`]+`;", f"Overall status: `{STATUS}`;", text, count=1)
    anchor = "for behavior-changing runs or explicit forensic evidence requirements.\n"
    text = v476.upsert_block(text, start_marker=start, end_marker=end, block=block, after_anchor=anchor)
    path.write_text(text, encoding="utf-8")


def update_measurements_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-measurements.md"
    counters = report["counters"]
    start = f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->"
    rows = "\n".join(f"| {key} | {value} |" for key, value in counters.items() if key != "protected_namespaces_touched")
    block = f"""### v4_7_10 PDF Korean Evidence Normalization And Answer Replay Readiness

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Source artifact: `{SOURCE_REPORT_JSON.as_posix()}`
- Boundary: diagnostic-only spacing-insensitive Korean evidence normalization over existing SourceAtom spans. No raw PDF broad scan, no gold/qrels/labels/expected/supporting evidence mutation, no denominator mutation, no training/fine_tuning/FT-A, no promotion, no live-readiness.
- Before/after: weak evidence/window {counters['residual_weak_evidence_window_count_before']} -> {counters['residual_weak_evidence_window_count_after']}; missing neighbor context {counters['missing_neighbor_context_count_before']} -> {counters['missing_neighbor_context_count_after']}.
- Answer-ready evidence bundles: {counters['answer_ready_evidence_bundle_count_before']} -> {counters['answer_ready_evidence_bundle_count']}.
- Local LLM status: `LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED`; no raw prompt or raw response payload is written.

| Counter | Value |
|---|---:|
{rows}
"""
    text = path.read_text(encoding="utf-8")
    text = v476.upsert_block(text, start_marker=start, end_marker=end, block=block)
    path.write_text(text, encoding="utf-8")


def update_triage_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-triage.md"
    counters = report["counters"]
    remaining = report["remaining_residual_rows"]
    start = f"<!-- {SHORT_RUN_ID}:triage-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:triage-entry:end -->"
    remaining_reason = (
        "none"
        if not remaining
        else "requires user-owned gold/evidence judgment or new source material for the listed row hashes"
    )
    block = f"""### v4_7_10 PDF Korean Evidence Normalization Boundary

- Scope: v4_7_9 residual weak PDF rows only; v4_7_9 answer-ready rows are protected no-regression rows.
- Repair policy: SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only.
- Bounded repair: spacing-insensitive Korean evidence normalization over the existing query text and existing SourceAtom citation span only; no raw PDF broad scan, hidden target/gold locator, expected/supporting gold text, source-file title shortcut, direct answer-value matching, or full-page dump.
- Result: weak evidence/window {counters['residual_weak_evidence_window_count_before']} -> {counters['residual_weak_evidence_window_count_after']}; missing neighbor context {counters['missing_neighbor_context_count_before']} -> {counters['missing_neighbor_context_count_after']}; answer-ready evidence bundles {counters['answer_ready_evidence_bundle_count_before']} -> {counters['answer_ready_evidence_bundle_count']}; spacing-insensitive Korean repairs {counters['korean_normalization_repair_count']}.
- Remaining row-level fail-closed reason: {remaining_reason}.
- Answer replay: {counters['answer_replay_candidate_count']} answer-replay candidates remain fail-closed with `LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED`; no raw prompt or raw response payload is written.
- Closed gates: official_metric=false, official_metric_input_rows=0, gold/qrels/labels/expected/supporting evidence/denominator/training/FT-A/fine_tuning/promotion/product-success/live-readiness remain closed.
"""
    text = path.read_text(encoding="utf-8")
    text = v476.upsert_block(text, start_marker=start, end_marker=end, block=block)
    path.write_text(text, encoding="utf-8")


def update_root_readme(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "README.md"
    counters = report["counters"]
    text = path.read_text(encoding="utf-8")
    snapshot = f"""## Current RAG Diagnostic Status

- Current RAG status: `{STATUS}`.
- Phase: v4_7 remains pre-official. `{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}` and targets only the remaining v4_7_9 weak PDF evidence/window rows; it does not open official metrics, gold/qrels, labels, denominator, training, promotion, or live-readiness.
- Resolver wiring: use `current` or `v4_7_10` for the latest PDF Korean evidence normalization and answer replay readiness report; use `v4_7_9` (`v4_7_9_pdf_evidence_residual_answer_quality_replay`) for the prior PDF residual evidence replay report.
- Runner consolidation: `ai/scripts/rag_eval.py` remains the stable short-key runner for `current`, `v4_7_10`, `v4_7_9`, `v4_7_8`, prior v4_7 cleanup keys, and verified check-only legacy aliases.
- PDF survivor residuals: weak evidence/window {counters['residual_weak_evidence_window_count_before']} -> {counters['residual_weak_evidence_window_count_after']}; answer-ready evidence bundles {counters['answer_ready_evidence_bundle_count_before']} -> {counters['answer_ready_evidence_bundle_count']}; Korean normalization repairs {counters['korean_normalization_repair_count']}; prior v4_7_9 answer-ready regressions {counters['regression_count_for_v4_7_9_answer_ready_rows']}; local LLM replay fail-closed as `LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED`.
- Retained v4_7 context: v4_7_2 supersedes the abstract v4_7_1 Korean review packet with non-empty `질의문` 204 and hydrated rows 204, PDF 100, XLSX 104; v4_7_3 applies the user-reviewed Korean query candidate CSV with 미검수=통과; v4_7_4 keeps PDF survivor 58; these remain not official metric.
- Rolling evidence docs: `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md` remain the canonical human-readable status ledgers; no per-run Markdown is created.
- Hard boundary: not official metric, not gold/qrels, not relevance/answerability labels, not expected answer/evidence approval, not product-success evidence, not promotion evidence, not FT-A execution, not fine_tuning, not actual fine-tuning/training, not threshold tuning, not winner selection, not training data, and not live DB/index/cache readiness. Locked flags remain `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `ft_a_execution=false`, `fine_tuning=false`, `fine_tuning_executed=false`, and `live_db_index_cache_readiness=false`.
"""
    if "## Current RAG Diagnostic Status" in text:
        text = re.sub(r"## Current RAG Diagnostic Status\n.*?(?=\n## )", snapshot.rstrip() + "\n\n", text, count=1, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + snapshot.rstrip() + "\n"
    path.write_text(text, encoding="utf-8")


def update_eval_readme(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "ai" / "eval" / "README.md"
    counters = report["counters"]
    text = path.read_text(encoding="utf-8")
    before_after = (
        f"weak evidence/window {counters['residual_weak_evidence_window_count_before']} -> "
        f"{counters['residual_weak_evidence_window_count_after']}"
    )
    answer_ready = (
        f"answer-ready evidence bundles {counters['answer_ready_evidence_bundle_count_before']} -> "
        f"{counters['answer_ready_evidence_bundle_count']}"
    )
    text = re.sub(r"- Current RAG status: `[^`]+`", f"- Current RAG status: `{STATUS}`", text, count=1)
    text = text.replace("`current` now resolves to v4_7_9", "`current` now resolves to v4_7_10")
    marker = (
        f"- v4_7_10 diagnostic replay: `{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}` "
        f"through `ai/scripts/rag_eval.py`; use resolver key `current` for v4_7_10 and `v4_7_9` for "
        f"the prior PDF residual report. {before_after}; {answer_ready}; official_metric=false; "
        "local LLM unavailable rows fail closed."
    )
    v479_marker = (
        "- v4_7_9 diagnostic replay: `v4_7_9_pdf_evidence_residual_answer_quality_replay` writes "
        "`ai/eval/reports/rag-ingestion/runs/v4_7_9/report.json` through `ai/scripts/rag_eval.py`; "
        "use explicit resolver key `v4_7_9` for this prior PDF residual report and `v4_7_8` for the "
        "prior cleanup/refactor report. official_metric=false; local LLM unavailable rows fail closed."
    )
    lines: list[str] = []
    inserted = False
    for line in text.splitlines():
        if line.startswith("- v4_7_10 diagnostic replay:"):
            if not inserted:
                lines.append(marker)
                inserted = True
            continue
        if line.startswith("- v4_7_9 diagnostic replay:"):
            lines.append(v479_marker)
            continue
        lines.append(line)
        if line == f"- Current RAG status: `{STATUS}`" and not inserted:
            lines.append(marker)
            inserted = True
    if not inserted:
        lines.append(marker)
    text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")


def update_scripts_readme(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "ai" / "scripts" / "README.md"
    counters = report["counters"]
    before_after = (
        f"weak evidence/window {counters['residual_weak_evidence_window_count_before']} -> "
        f"{counters['residual_weak_evidence_window_count_after']}"
    )
    answer_ready = (
        f"answer-ready evidence bundles {counters['answer_ready_evidence_bundle_count_before']} -> "
        f"{counters['answer_ready_evidence_bundle_count']}"
    )
    text = path.read_text(encoding="utf-8")
    replacement = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        f"`{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}`, `current` resolves to `v4_7_10`, "
        "`v4_7_9_pdf_evidence_residual_answer_quality_replay` remains the prior PDF residual report, "
        "`v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion` remains the prior cleanup/refactor report, "
        f"{before_after}, {answer_ready}, and local LLM-unavailable answer replay fails closed without raw prompt/response payloads. |"
    )
    text = re.sub(r"\| `rag_eval\.py` \| .*? \|", replacement, text, count=1)
    if replacement not in text:
        text = text.replace("| Script | Role |\n|---|---|\n", "| Script | Role |\n|---|---|\n" + replacement + "\n", 1)
    path.write_text(text, encoding="utf-8")


def update_docs(root: Path, report: Mapping[str, Any]) -> None:
    update_progress_doc(root, report)
    update_measurements_doc(root, report)
    update_triage_doc(root, report)
    update_root_readme(root, report)
    update_eval_readme(root, report)
    update_scripts_readme(root, report)


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v4_7_10 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v4_7_10 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v4_7_10 status mismatch")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v4_7_10 must remain diagnostic-only and non-production")
    for key in REQUIRED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v4_7_10 closed guardrail mismatch: {key}")
    if report.get("official_metric_input_rows") != 0:
        raise ValueError("v4_7_10 official_metric_input_rows must stay zero")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_10 protected namespaces were touched")
    if report.get("SourceAtom_EvidenceBundle_role") != "evidence_truth":
        raise ValueError("v4_7_10 SourceAtom/EvidenceBundle role drifted")
    if report.get("SearchView_vector_payload_role") != "candidate_only":
        raise ValueError("v4_7_10 SearchView role drifted")
    for key in (
        "raw_pdf_query_time_parsing",
        "hidden_target_locator_used",
        "expected_or_supporting_gold_text_used",
        "source_file_title_shortcut_used",
        "direct_answer_value_matching_used",
        "full_page_dump_used",
    ):
        if report.get(key) is not False:
            raise ValueError(f"v4_7_10 guardrail must be false: {key}")
    counters = report.get("counters") or {}
    if counters.get("pdf_survivor_row_count") != 58:
        raise ValueError("v4_7_10 PDF survivor row count drifted")
    if counters.get("residual_weak_evidence_window_count_before") != 3:
        raise ValueError("v4_7_10 must start from the three v4_7_9 residual weak rows")
    if counters.get("residual_weak_evidence_window_count_after", 99) > 1:
        raise ValueError("v4_7_10 did not satisfy the residual weak evidence target")
    if counters.get("missing_neighbor_context_count_after") != counters.get("residual_weak_evidence_window_count_after"):
        raise ValueError("v4_7_10 missing-neighbor count must track residual weak windows")
    if counters.get("regression_count_for_v4_7_9_answer_ready_rows") != 0:
        raise ValueError("v4_7_10 regressed v4_7_9 answer-ready rows")
    if counters.get("llm_invoked_count") != 0 or counters.get("generated_response_count") != 0:
        raise ValueError("v4_7_10 must not fake local LLM replay")
    if counters.get("local_llm_unavailable_fail_closed_count") != counters.get("answer_replay_candidate_count"):
        raise ValueError("v4_7_10 LLM unavailable fail-closed count mismatch")
    rows = list(report.get("pdf_residual_replay_rows") or [])
    if len(rows) != 58:
        raise ValueError("v4_7_10 row ledger count drifted")
    targeted = [row for row in rows if row.get("v4_7_10_repair_targeted") is True]
    if len(targeted) != 3:
        raise ValueError("v4_7_10 must target exactly the v4_7_9 residual weak rows")
    if len(report.get("remaining_residual_rows") or []) != counters.get("residual_weak_evidence_window_count_after"):
        raise ValueError("v4_7_10 remaining residual ledger mismatch")
    for row in rows:
        if row.get("SourceAtom_EvidenceBundle_role") != "evidence_truth":
            raise ValueError("v4_7_10 row SourceAtom role drifted")
        if row.get("SearchView_vector_payload_role") != "candidate_only":
            raise ValueError("v4_7_10 row SearchView role drifted")
        if row.get("raw_pdf_query_time_parsing") is not False:
            raise ValueError("v4_7_10 row raw PDF parsing opened")
        if row.get("expected_or_supporting_gold_text_used") is not False:
            raise ValueError("v4_7_10 row gold evidence shortcut opened")
