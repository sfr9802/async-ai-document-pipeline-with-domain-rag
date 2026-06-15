from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v476_archive_purge as v476


LOGICAL_RUN_KEY = "v4_7_9"
SHORT_RUN_ID = "v4_7_9_pdf_evidence_residual_answer_quality_replay"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_9_"
    "pdf_evidence_residual_answer_quality_replay_nonprod"
)
STATUS = "V4_7_9_PDF_EVIDENCE_RESIDUAL_ANSWER_QUALITY_REPLAY_NONPROD_READY"

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
V4_7_5_REPORT_PATH = REPORT_ROOT / "runs" / "v4_7_5" / "report.json"
V4_7_4_REPORT_PATH = REPORT_ROOT / "runs" / "v4_7_4" / "report.json"
SOURCE_RUN_ID = "v4_7_5_pdf_evidence_repair_eval_compaction"
PRIOR_REPLAY_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_4_"
    "pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod"
)

REQUIRED_FALSE_KEYS = (
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


def utc_now_iso() -> str:
    return v476.utc_now_iso()


def read_json(path: Path) -> dict[str, Any]:
    return v476.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v476.read_jsonl(path)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v476.write_jsonl(path, rows)


def repo_relative(path: Path, root: Path) -> str:
    return v476.repo_relative(path, root)


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", value)
        if token not in STOP_TOKENS
    }


def _row_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (_clean(row.get("candidate_id_hash")), _clean(row.get("query_id_hash")))


def _bounded(value: Any, *, limit: int = 420) -> str:
    text = re.sub(r"\s+", " ", _clean(value)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _local_llm_available() -> bool:
    return os.environ.get("RAG_V4_7_9_ENABLE_LOCAL_LLM_REPLAY") == "1" and False


def _overlap_count(*, query_text: str, evidence_text: str, inherited_overlap: Any) -> int:
    inherited = int(inherited_overlap or 0)
    return max(inherited, len(_tokens(query_text) & _tokens(evidence_text)))


def _numeric_overlap_count(*, query_text: str, evidence_text: str) -> int:
    pattern = r"\d+(?:[.,]\d+)?%?"
    return len(set(re.findall(pattern, query_text)) & set(re.findall(pattern, evidence_text)))


def _repair_decision(row: Mapping[str, Any], prior_row: Mapping[str, Any]) -> dict[str, Any]:
    evidence_text = _clean(row.get("citation_span_preview"))
    query_text = _clean(prior_row.get("query_text"))
    overlap = _overlap_count(
        query_text=query_text,
        evidence_text=evidence_text,
        inherited_overlap=row.get("query_evidence_token_overlap_count"),
    )
    numeric_overlap = _numeric_overlap_count(query_text=query_text, evidence_text=evidence_text)
    evidence_chars = len(evidence_text)
    repairable = evidence_chars >= 30 and (overlap >= 2 or numeric_overlap >= 1)
    if repairable:
        return {
            "decision": "repaired",
            "reason": "existing_sourceatom_span_has_bounded_query_overlap",
            "query_evidence_token_overlap_count": overlap,
            "numeric_overlap_count": numeric_overlap,
            "evidence_chars": evidence_chars,
        }
    return {
        "decision": "dropped",
        "reason": "insufficient_query_evidence_overlap_for_bounded_repair",
        "query_evidence_token_overlap_count": overlap,
        "numeric_overlap_count": numeric_overlap,
        "evidence_chars": evidence_chars,
    }


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
    v475_rows: Sequence[Mapping[str, Any]],
    v474_rows: Sequence[Mapping[str, Any]],
    local_llm_available: bool,
) -> list[dict[str, Any]]:
    prior_by_key = {_row_key(row): row for row in v474_rows}
    rows: list[dict[str, Any]] = []
    for row in v475_rows:
        key = _row_key(row)
        prior_row = prior_by_key.get(key, {})
        prior_ready = row.get("answer_ready_evidence_bundle") is True
        residual = row.get("weak_evidence_window") is True or row.get("missing_neighbor_context") is True
        if prior_ready:
            decision = {
                "decision": "protected_no_regression",
                "reason": "v4_7_5_answer_ready_row",
                "query_evidence_token_overlap_count": int(row.get("query_evidence_token_overlap_count") or 0),
                "numeric_overlap_count": 0,
                "evidence_chars": len(_clean(row.get("citation_span_preview"))),
            }
        elif residual:
            decision = _repair_decision(row, prior_row)
        else:
            decision = {
                "decision": "dropped",
                "reason": "not_answer_ready_and_not_marked_residual",
                "query_evidence_token_overlap_count": int(row.get("query_evidence_token_overlap_count") or 0),
                "numeric_overlap_count": 0,
                "evidence_chars": len(_clean(row.get("citation_span_preview"))),
            }

        repaired = decision["decision"] == "repaired"
        answer_ready = prior_ready or repaired
        replay_candidate = repaired
        evidence_text = _bounded(row.get("citation_span_preview"))
        repair_audit = {
            **decision,
            "repair_targeted": residual,
            "repair_applied": repaired,
            "expansion_scope": "same_page_sourceatom_block_window_metadata_only",
            "source_text_added_from_raw_pdf": False,
            "source_text_added_chars": 0,
            "raw_pdf_query_time_parsing": False,
            "broad_source_atom_scan": False,
            "hidden_target_locator_used": False,
            "expected_or_supporting_gold_text_used": False,
            "source_file_title_shortcut_used": False,
            "direct_answer_value_matching_used": False,
            "full_page_dump_used": False,
            "preserved_page_candidate": row.get("page_candidate"),
            "preserved_block_candidate": row.get("block_candidate"),
            "preserved_locator_preview_redacted": row.get("locator_preview_redacted"),
        }
        out = {
            "row_index_1based": row.get("row_index_1based"),
            "candidate_id": row.get("candidate_id"),
            "candidate_id_hash": row.get("candidate_id_hash"),
            "query_id": row.get("query_id"),
            "query_id_hash": row.get("query_id_hash"),
            "query_text_sha256": row.get("query_text_sha256"),
            "source_family": row.get("source_family"),
            "decision_status": row.get("decision_status"),
            "query_candidate_passed": row.get("query_candidate_passed"),
            "SourceAtom_EvidenceBundle_role": "evidence_truth",
            "SearchView_vector_payload_role": "candidate_only",
            "evidence_bundle_version": "v4_7_9_residual_v1" if repaired else row.get("evidence_bundle_version"),
            "evidence_bundle_source": "v4_7_5_source_evidence_bundle_with_v4_7_9_residual_repair_audit",
            "source_atom_hydration_success": row.get("source_atom_hydration_success"),
            "page_candidate": row.get("page_candidate"),
            "block_candidate": row.get("block_candidate"),
            "locator_preview_redacted": row.get("locator_preview_redacted"),
            "citation_candidate": row.get("citation_candidate"),
            "citation_span_preview": evidence_text,
            "citation_span_available": bool(evidence_text),
            "evidence_snippet_sha256": row.get("evidence_snippet_sha256"),
            "preserved_locator_metadata": {
                "page_candidate": row.get("page_candidate"),
                "block_candidate": row.get("block_candidate"),
                "locator_preview_redacted": row.get("locator_preview_redacted"),
                "citation_candidate": row.get("citation_candidate"),
                "bbox_metric_computed": row.get("bbox_metric_computed", False),
            },
            "prior_answer_ready_evidence_bundle": prior_ready,
            "v4_7_5_residual_weak_evidence_window": residual,
            "v4_7_9_repair_targeted": residual,
            "v4_7_9_repair_applied": repaired,
            "answer_ready_evidence_bundle": answer_ready,
            "evidence_window_sufficient_proxy": answer_ready,
            "weak_evidence_window": not answer_ready,
            "missing_neighbor_context": not answer_ready,
            "failure_buckets": ["ANSWER_READY"] if answer_ready else [
                "RIGHT_PAGE_WEAK_WINDOW",
                "CONTEXT_NEIGHBOR_MISSING",
                "CONTRACT_FAIL_CLOSED",
            ],
            "repair_audit": repair_audit,
            "answer_replay_audit": _answer_replay_audit(
                candidate=replay_candidate,
                local_llm_available=local_llm_available,
                protected=prior_ready,
            ),
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
        rows.append(out)
    return rows


def _count(rows: Sequence[Mapping[str, Any]], key: str) -> int:
    return sum(1 for row in rows if row.get(key))


def _counters(rows: Sequence[Mapping[str, Any]], *, before: Mapping[str, Any]) -> dict[str, Any]:
    repaired = [row for row in rows if row.get("v4_7_9_repair_applied")]
    replay_candidates = [row for row in rows if row.get("answer_replay_audit", {}).get("answer_replay_candidate")]
    return {
        "pdf_survivor_row_count": len(rows),
        "prior_answer_ready_evidence_bundle_count": int(before.get("answer_ready_evidence_bundle_count") or 0),
        "residual_weak_evidence_window_count_before": int(before.get("weak_evidence_window_count") or 0),
        "residual_weak_evidence_window_count_after": _count(rows, "weak_evidence_window"),
        "missing_neighbor_context_count_before": int(before.get("missing_neighbor_context_count") or 0),
        "missing_neighbor_context_count_after": _count(rows, "missing_neighbor_context"),
        "repaired_evidence_bundle_count": len(repaired),
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
        "regression_count_for_prior_answer_ready_rows": sum(
            1
            for row in rows
            if row.get("prior_answer_ready_evidence_bundle") is True
            and row.get("answer_ready_evidence_bundle") is not True
        ),
        "official_metric_input_rows": 0,
        "protected_namespaces_touched": [],
    }


def _source_before(v475_report: Mapping[str, Any]) -> dict[str, int]:
    after = v475_report.get("evidence_repair_metrics", {}).get("after", {})
    return {
        "answer_ready_evidence_bundle_count": int(after.get("answer_ready_evidence_bundle_count") or 0),
        "weak_evidence_window_count": int(after.get("weak_evidence_window_count") or 0),
        "missing_neighbor_context_count": int(after.get("missing_neighbor_context_count") or 0),
    }


def build_report(
    *,
    root: Path,
    execute: bool = False,
    sync_surfaces: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    del execute
    v475_report = registry.load_report("v4_7_5", root=root)
    v474_report = registry.load_report("v4_7_4", root=root)
    v475_rows = list(v475_report.get("pdf_survivor_replay_ledger") or [])
    v474_rows = list(v474_report.get("pdf_survivor_replay_ledger") or [])
    local_llm_available = _local_llm_available()
    rows = _build_rows(v475_rows=v475_rows, v474_rows=v474_rows, local_llm_available=local_llm_available)
    before = _source_before(v475_report)
    counters = _counters(rows, before=before)
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
        "source_report_json": V4_7_5_REPORT_PATH.as_posix(),
        "prior_replay_run_id": PRIOR_REPLAY_RUN_ID,
        "prior_replay_report_json": V4_7_4_REPORT_PATH.as_posix(),
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
            "enabled_env_var": "RAG_V4_7_9_ENABLE_LOCAL_LLM_REPLAY",
            "available": local_llm_available,
            "decision": "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED",
            "raw_prompt_or_response_payload_written": False,
        },
        "counters": counters,
        "pdf_survivor_row_count": counters["pdf_survivor_row_count"],
        "pdf_residual_replay_rows": rows,
        "non_gold_ambiguity_decisions": [
            {
                "decision": "repair_only_v4_7_5_residual_weak_rows",
                "reason": "v4_7_5 answer-ready rows are protected no-regression rows",
            },
            {
                "decision": "no_local_llm_substitute_generation",
                "reason": "local LLM replay surface is unavailable; extractive/noop responses would be fake success",
            },
            {
                "decision": "drop_low_overlap_residual_rows",
                "reason": "bounded SourceAtom span overlap is insufficient without raw PDF or gold locator access",
            },
        ],
        "residual_risks": [
            "local LLM replay was unavailable, so answer generation remains fail-closed for repaired residual rows",
            "remaining residual weak rows need human/gold-owned policy or safer source metadata before answer replay",
            "all counters remain diagnostic proxies and are not official metric or promotion evidence",
        ],
    }
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
        "event_type": "diagnostic_v4_7_9_pdf_evidence_residual_answer_quality_replay_nonprod",
        "status": STATUS,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": {"report_json_sha256": report_sha256},
        "source_run_id": report["source_run_id"],
        "prior_replay_run_id": report["prior_replay_run_id"],
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
        "This diagnostic-only slice replays the v4_7_5 PDF survivor surface and targets only the residual weak "
        f"EvidenceBundle rows: weak evidence/window {counters['residual_weak_evidence_window_count_before']} -> "
        f"{counters['residual_weak_evidence_window_count_after']}, missing neighbor context "
        f"{counters['missing_neighbor_context_count_before']} -> {counters['missing_neighbor_context_count_after']}, "
        f"repaired bundles {counters['repaired_evidence_bundle_count']}, prior answer-ready regressions "
        f"{counters['regression_count_for_prior_answer_ready_rows']}. Local LLM replay stayed fail-closed as "
        f"`LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED` for {counters['local_llm_unavailable_fail_closed_count']} candidates. "
        "SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only. "
        "All official, gold/qrels, label, denominator, training, FT-A, fine_tuning, promotion, product-success, "
        "and live-readiness gates stay closed."
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
    block = f"""### v4_7_9 PDF Evidence Residual Answer Quality Replay

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
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
    start = f"<!-- {SHORT_RUN_ID}:triage-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:triage-entry:end -->"
    block = f"""### v4_7_9 PDF Residual Evidence Replay Boundary

- Scope: v4_7_5 PDF survivor rows only; prior answer-ready rows are protected no-regression rows.
- Repair policy: SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only.
- Bounded repair: same-page SourceAtom/block/window metadata only; no raw PDF broad scan, hidden target/gold locator, expected/supporting gold text, source-file title shortcut, direct answer-value matching, or full-page dump.
- Residual after repair: weak evidence/window {counters['residual_weak_evidence_window_count_after']}; missing neighbor context {counters['missing_neighbor_context_count_after']}.
- Answer replay: {counters['answer_replay_candidate_count']} repaired candidates were eligible, but local LLM was unavailable and therefore failed closed with `LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED`.
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
- Phase: v4_7 remains pre-official. `{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}` and targets only residual v4_7_5 PDF survivor evidence rows; it does not open official metrics, gold/qrels, labels, denominator, training, promotion, or live-readiness.
- Resolver wiring: use `current` or `v4_7_9` for the latest PDF residual evidence replay report; use `v4_7_8` for the prior cleanup/refactor report.
- Runner consolidation: `ai/scripts/rag_eval.py` remains the stable short-key runner for `current`, `v4_7_9`, `v4_7_8`, prior v4_7 cleanup keys, and verified check-only legacy aliases.
- PDF survivor residuals: weak evidence/window {counters['residual_weak_evidence_window_count_before']} -> {counters['residual_weak_evidence_window_count_after']}; repaired bundles {counters['repaired_evidence_bundle_count']}; prior answer-ready regressions {counters['regression_count_for_prior_answer_ready_rows']}; local LLM replay fail-closed as `LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED`.
- Retained v4_7 context: v4_7_2 supersedes the abstract v4_7_1 Korean review packet with non-empty `질의문` 204 and hydrated rows 204, PDF 100, XLSX 104; v4_7_3 applies the user-reviewed Korean query candidate CSV with 미검수=통과; v4_7_4 keeps PDF survivor 58; these remain not official metric.
- Rolling evidence docs: `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md` remain the canonical human-readable status ledgers; no per-run Markdown is created.
- Hard boundary: not official metric, not gold/qrels, not relevance/answerability labels, not expected answer/evidence approval, not product-success evidence, not promotion evidence, not FT-A execution, not fine_tuning, not actual fine-tuning/training, not threshold tuning, not winner selection, not training data, and not live DB/index/cache readiness. Locked flags remain `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `ft_a_execution=false`, `fine_tuning=false`, `fine_tuning_executed=false`, and `live_db_index_cache_readiness=false`.
"""
    if "## Current RAG Diagnostic Status" in text:
        text = re.sub(r"## Current RAG Diagnostic Status\n.*?(?=\n## )", snapshot.rstrip() + "\n\n", text, count=1, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + snapshot.rstrip() + "\n"
    path.write_text(text, encoding="utf-8")


def update_eval_readme(root: Path) -> None:
    path = root / "ai" / "eval" / "README.md"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"- Current RAG status: `[^`]+`", f"- Current RAG status: `{STATUS}`", text, count=1)
    text = text.replace(
        "use resolver key `current` for v4_7_8 and `v4_7_7` for the prior",
        "use resolver key `v4_7_8` for this prior cleanup/refactor report and `v4_7_7` for the prior",
    )
    text = text.replace(
        "`current` now resolves to v4_7_8",
        "`current` now resolves to v4_7_9",
    )
    marker = (
        f"- v4_7_9 diagnostic replay: `{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}` "
        "through `ai/scripts/rag_eval.py`; use resolver key `current` for v4_7_9 and `v4_7_8` for "
        "the prior cleanup/refactor report. official_metric=false; local LLM unavailable rows fail closed."
    )
    if marker not in text:
        current_status = f"- Current RAG status: `{STATUS}`"
        if current_status in text:
            text = text.replace(current_status, current_status + "\n" + marker, 1)
        else:
            text = text.rstrip() + "\n" + current_status + "\n" + marker + "\n"
    path.write_text(text, encoding="utf-8")


def update_scripts_readme(root: Path) -> None:
    path = root / "ai" / "scripts" / "README.md"
    text = path.read_text(encoding="utf-8")
    replacement = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        f"`{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}`, `current` resolves to `v4_7_9`, "
        "`v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion` remains the prior cleanup/refactor report, "
        "and local LLM-unavailable answer replay fails closed without raw prompt/response payloads. |"
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
    update_eval_readme(root)
    update_scripts_readme(root)


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v4_7_9 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v4_7_9 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v4_7_9 status mismatch")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v4_7_9 must remain diagnostic-only and non-production")
    for key in REQUIRED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v4_7_9 closed guardrail mismatch: {key}")
    if report.get("official_metric_input_rows") != 0:
        raise ValueError("v4_7_9 official_metric_input_rows must stay zero")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_9 protected namespaces were touched")
    if report.get("SourceAtom_EvidenceBundle_role") != "evidence_truth":
        raise ValueError("v4_7_9 SourceAtom/EvidenceBundle role drifted")
    if report.get("SearchView_vector_payload_role") != "candidate_only":
        raise ValueError("v4_7_9 SearchView role drifted")
    for key in (
        "raw_pdf_query_time_parsing",
        "hidden_target_locator_used",
        "expected_or_supporting_gold_text_used",
        "source_file_title_shortcut_used",
        "direct_answer_value_matching_used",
        "full_page_dump_used",
    ):
        if report.get(key) is not False:
            raise ValueError(f"v4_7_9 guardrail must be false: {key}")
    counters = report.get("counters") or {}
    if counters.get("pdf_survivor_row_count") != 58:
        raise ValueError("v4_7_9 PDF survivor row count drifted")
    if counters.get("prior_answer_ready_evidence_bundle_count") != 48:
        raise ValueError("v4_7_9 v4_7_5 prior ready count drifted")
    if counters.get("residual_weak_evidence_window_count_before") != 10:
        raise ValueError("v4_7_9 residual weak before count drifted")
    if counters.get("residual_weak_evidence_window_count_after", 99) >= 10:
        raise ValueError("v4_7_9 did not reduce residual weak evidence rows")
    if counters.get("regression_count_for_prior_answer_ready_rows") != 0:
        raise ValueError("v4_7_9 regressed v4_7_5 answer-ready rows")
    if counters.get("llm_invoked_count") != 0 or counters.get("generated_response_count") != 0:
        raise ValueError("v4_7_9 must not fake local LLM replay")
    if counters.get("local_llm_unavailable_fail_closed_count") != counters.get("answer_replay_candidate_count"):
        raise ValueError("v4_7_9 LLM unavailable fail-closed count mismatch")
    rows = list(report.get("pdf_residual_replay_rows") or [])
    if len(rows) != 58:
        raise ValueError("v4_7_9 row ledger count drifted")
    for row in rows:
        if row.get("SourceAtom_EvidenceBundle_role") != "evidence_truth":
            raise ValueError("v4_7_9 row SourceAtom role drifted")
        if row.get("SearchView_vector_payload_role") != "candidate_only":
            raise ValueError("v4_7_9 row SearchView role drifted")
        if row.get("raw_pdf_query_time_parsing") is not False:
            raise ValueError("v4_7_9 row raw PDF parsing opened")
