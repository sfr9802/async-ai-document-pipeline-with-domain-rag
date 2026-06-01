from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v4713_live_retrieval_answerability_and_full_pdf_replay as v4713
from ai.eval import rag_v476_archive_purge as v476


LOGICAL_RUN_KEY = "v4_7_14"
SHORT_RUN_ID = "v4_7_14_diagnostic_precondition_hardening"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_14_"
    "diagnostic_precondition_hardening_nonprod"
)
STATUS = "V4_7_14_DIAGNOSTIC_PRECONDITION_HARDENING_NONPROD_READY"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
SOURCE_RUN_ID = v4713.SHORT_RUN_ID
SOURCE_REPORT_JSON = v4713.SHORT_REPORT_PATH

FAMILIES = ("TEXT", "PDF", "XLSX")
ZERO_BY_FAMILY = {family: 0 for family in FAMILIES}
KST_DOC_DATE = "2026-05-31"
FORBIDDEN_QUALITY_FAILURE_COUNTERS = (
    "live_retrieval_quality_failure_count",
    "claim_support_fail_count",
    "parser_failure_count",
    "citation_failure_count",
    "unsupported_answer_count",
    "generated_response_count",
    "noop_or_extractive_fallback_answer_count",
)


def utc_now_iso() -> str:
    return v476.utc_now_iso()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v476.write_json(path, payload)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v476.read_jsonl(path)


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    v476.write_jsonl(path, rows)


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _load_source_report(root: Path, source_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    report = dict(source_report or registry.load_report("v4_7_13", root=root))
    v4713.check_report(report)
    return report


def live_retrieval_preflight(source_report: Mapping[str, Any]) -> dict[str, Any]:
    live = source_report.get("live_silver_retrieval_replay") or {}
    blocked_reason = str(live.get("blocked_reason") or "")
    row_count = _as_int(live.get("row_count"))
    unavailable = live.get("status") != "LIVE_SILVER_RETRIEVAL_REPLAY_COMPLETED_DIAGNOSTIC_ONLY"
    source_candidate_count = 1000
    return {
        "status": "LIVE_RETRIEVAL_PRECONDITION_UNAVAILABLE_FAIL_CLOSED"
        if unavailable
        else "LIVE_RETRIEVAL_PRECONDITION_AVAILABLE_DIAGNOSTIC_ONLY",
        "source_v4_7_13_status": live.get("status"),
        "read_only_search_index_contract_available": not unavailable,
        "blocked_reason": blocked_reason,
        "source_candidate_row_count": source_candidate_count,
        "attempted_row_count": 0 if unavailable else row_count,
        "quality_evaluated_row_count": 0 if unavailable else row_count,
        "not_evaluated_count_by_reason": {
            "read_only_live_SearchIndexContract_unavailable": source_candidate_count if unavailable else 0,
        },
        "blocked_source_denominator_by_family": {"TEXT": 350, "PDF": 325, "XLSX": 325}
        if source_candidate_count == 1000
        else dict(ZERO_BY_FAMILY),
        "row_count": 0 if unavailable else row_count,
        "precondition_unavailable_count": 1 if unavailable else 0,
        "retrieval_quality_failure_count": 0,
        "retrieval_quality_failure_count_by_family": dict(ZERO_BY_FAMILY),
        "read_only": True,
        "production_db_mutated": live.get("production_db_mutated") is True,
        "cache_mutated": live.get("cache_mutated") is True,
        "source_registry_mutated": live.get("source_registry_mutated") is True,
        "silver_mutated": live.get("silver_mutated") is True,
        "index_rebuilt": live.get("index_rebuilt") is True,
        "protected_namespaces_touched": list(live.get("protected_namespaces_touched") or []),
        "comparison_source": "v4_7_12_persisted_topk_only",
        "retrieval_quality_failure_policy": (
            "not_evaluated_when_read_only_live_SearchIndexContract_is_unavailable"
            if unavailable
            else "reserved_for_completed_live_retrieval_rows_only"
        ),
    }


def local_llm_preflight(source_report: Mapping[str, Any]) -> dict[str, Any]:
    counters = source_report.get("counters") or {}
    replay = source_report.get("full_pdf_llm_replay") or {}
    eligible_count = _as_int(counters.get("pdf_full_replay_eligible_count") or replay.get("eligible_count"))
    generated_count = _as_int(replay.get("generated_response_count"))
    unavailable = generated_count == 0 or replay.get("status") != "FULL_PDF_LLM_REPLAY_COMPLETED_DIAGNOSTIC_ONLY"
    return {
        "status": "LOCAL_LLM_UNAVAILABLE_GENERATION_NOT_ATTEMPTED_FAIL_CLOSED"
        if unavailable
        else "LOCAL_LLM_GENERATION_COMPLETED_DIAGNOSTIC_ONLY",
        "source_v4_7_13_status": replay.get("status"),
        "local_llm_available": bool((source_report.get("local_llm_probe") or {}).get("available")),
        "source_candidate_row_count": eligible_count,
        "attempted_row_count": 0 if unavailable else eligible_count,
        "quality_evaluated_row_count": 0 if unavailable else eligible_count,
        "not_evaluated_count_by_reason": {
            "local_LLM_unavailable_or_generation_not_attempted": eligible_count if unavailable else 0,
        },
        "eligible_count": eligible_count,
        "llm_unavailable_skip_count": eligible_count if unavailable else 0,
        "generation_attempted": not unavailable,
        "llm_invoked_count": 0 if unavailable else _as_int(replay.get("llm_invoked_count")),
        "generated_response_count": 0 if unavailable else generated_count,
        "parser_not_evaluated_count": eligible_count if unavailable else 0,
        "parser_failure_count": 0,
        "citation_not_evaluated_count": eligible_count if unavailable else 0,
        "claim_support_fail_count": 0,
        "citation_failure_count": 0,
        "unsupported_answer_count": 0,
        "claim_support_not_evaluated_due_to_no_generation_count": eligible_count if unavailable else 0,
        "noop_or_extractive_fallback_answer_count": 0,
        "fake_answer_emitted_count": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "parser_policy": "invoke_only_after_generation",
        "claim_verifier_policy": "invoke_only_after_generation_and_parse",
    }


def silver_answerability_root_cause_queues(source_report: Mapping[str, Any]) -> dict[str, Any]:
    overlay = source_report.get("silver_answerability_overlay") or {}
    category_counts = overlay.get("category_counts_by_family") or {}

    def family_count(category: str, family: str) -> int:
        return _as_int((category_counts.get(category) or {}).get(family))

    queues_by_family = {
        "TEXT": {
            "primary_queue_order": ["target_not_in_topk", "evidence_mismatch_after_family_route"],
            "root_cause_counts": {
                "target_not_in_topk": _as_int((overlay.get("target_not_in_topk_count_by_family") or {}).get("TEXT")),
                "evidence_mismatch_after_family_route": family_count(
                    "source_family_route_ok_but_evidence_mismatch", "TEXT"
                ),
            },
        },
        "XLSX": {
            "primary_queue_order": ["target_not_in_topk", "repeated_prefix_cluster"],
            "root_cause_counts": {
                "target_not_in_topk": _as_int((overlay.get("target_not_in_topk_count_by_family") or {}).get("XLSX")),
                "repeated_prefix_cluster": family_count("repeated_prefix_cluster_member", "XLSX"),
            },
        },
        "PDF": {
            "primary_queue_order": [
                "evidence_window_insufficient",
                "source_family_route_ok_but_evidence_mismatch",
                "query_too_broad",
            ],
            "root_cause_counts": {
                "evidence_window_insufficient": family_count("evidence_window_insufficient", "PDF"),
                "source_family_route_ok_but_evidence_mismatch": family_count(
                    "source_family_route_ok_but_evidence_mismatch", "PDF"
                ),
                "query_too_broad": family_count("query_too_broad", "PDF"),
            },
        },
    }
    return {
        "schema_version": f"{SHORT_RUN_ID}_silver_answerability_root_cause_queues_v1",
        "status": "SILVER_ANSWERABILITY_ROOT_CAUSE_QUEUES_READY_DIAGNOSTIC_ONLY",
        "source_overlay_status": overlay.get("status"),
        "row_count": _as_int(overlay.get("row_count")),
        "prior_smoke_counts_by_family": dict(overlay.get("prior_smoke_counts_by_family") or ZERO_BY_FAMILY),
        "queues_by_family": queues_by_family,
        "diagnostic_silver_only": True,
        "silver_mutation": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "silver_promoted_to_gold_count": 0,
        "official_metric_input_rows": 0,
        "mutation_policy": [
            "do_not_modify_silver_rows",
            "do_not_modify_gold_qrels_labels_expected_or_supporting_evidence",
            "do_not_modify_denominator_rows",
        ],
    }


def _build_counters(
    *,
    live_preflight: Mapping[str, Any],
    llm_preflight: Mapping[str, Any],
    queues: Mapping[str, Any],
) -> dict[str, Any]:
    queue_families = queues.get("queues_by_family") or {}
    text_counts = (queue_families.get("TEXT") or {}).get("root_cause_counts") or {}
    xlsx_counts = (queue_families.get("XLSX") or {}).get("root_cause_counts") or {}
    pdf_counts = (queue_families.get("PDF") or {}).get("root_cause_counts") or {}
    return {
        "diagnostic_only": True,
        "non_production": True,
        "current_resolves_to": LOGICAL_RUN_KEY,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "protected_namespaces_touched": [],
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
        "SearchView_vector_payload_role": "candidate_only",
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "live_retrieval_precondition_unavailable_count": _as_int(live_preflight.get("precondition_unavailable_count")),
        "live_retrieval_source_candidate_row_count": _as_int(live_preflight.get("source_candidate_row_count")),
        "live_retrieval_attempted_row_count": _as_int(live_preflight.get("attempted_row_count")),
        "live_retrieval_quality_evaluated_row_count": _as_int(live_preflight.get("quality_evaluated_row_count")),
        "live_retrieval_row_count": _as_int(live_preflight.get("row_count")),
        "live_retrieval_quality_failure_count": _as_int(live_preflight.get("retrieval_quality_failure_count")),
        "live_retrieval_quality_failure_count_by_family": dict(
            live_preflight.get("retrieval_quality_failure_count_by_family") or ZERO_BY_FAMILY
        ),
        "llm_source_candidate_row_count": _as_int(llm_preflight.get("source_candidate_row_count")),
        "llm_attempted_row_count": _as_int(llm_preflight.get("attempted_row_count")),
        "llm_quality_evaluated_row_count": _as_int(llm_preflight.get("quality_evaluated_row_count")),
        "llm_unavailable_skip_count": _as_int(llm_preflight.get("llm_unavailable_skip_count")),
        "claim_support_not_evaluated_due_to_no_generation_count": _as_int(
            llm_preflight.get("claim_support_not_evaluated_due_to_no_generation_count")
        ),
        "parser_not_evaluated_count": _as_int(llm_preflight.get("parser_not_evaluated_count")),
        "citation_not_evaluated_count": _as_int(llm_preflight.get("citation_not_evaluated_count")),
        "generated_response_count": _as_int(llm_preflight.get("generated_response_count")),
        "parser_failure_count": _as_int(llm_preflight.get("parser_failure_count")),
        "claim_support_fail_count": _as_int(llm_preflight.get("claim_support_fail_count")),
        "citation_failure_count": _as_int(llm_preflight.get("citation_failure_count")),
        "unsupported_answer_count": _as_int(llm_preflight.get("unsupported_answer_count")),
        "noop_or_extractive_fallback_answer_count": _as_int(
            llm_preflight.get("noop_or_extractive_fallback_answer_count")
        ),
        "fake_answer_emitted_count": _as_int(llm_preflight.get("fake_answer_emitted_count")),
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "silver_answerability_overlay_row_count": _as_int(queues.get("row_count")),
        "silver_text_target_not_in_topk_count": _as_int(text_counts.get("target_not_in_topk")),
        "silver_text_evidence_mismatch_count": _as_int(text_counts.get("evidence_mismatch_after_family_route")),
        "silver_xlsx_target_not_in_topk_count": _as_int(xlsx_counts.get("target_not_in_topk")),
        "silver_xlsx_repeated_prefix_cluster_count": _as_int(xlsx_counts.get("repeated_prefix_cluster")),
        "silver_pdf_evidence_window_insufficient_count": _as_int(pdf_counts.get("evidence_window_insufficient")),
        "silver_pdf_source_family_route_ok_but_evidence_mismatch_count": _as_int(
            pdf_counts.get("source_family_route_ok_but_evidence_mismatch")
        ),
        "silver_pdf_query_too_broad_count": _as_int(pdf_counts.get("query_too_broad")),
    }


def build_report(
    *,
    root: Path,
    generated_at: str | None = None,
    source_report: Mapping[str, Any] | None = None,
    check: bool = True,
) -> dict[str, Any]:
    v4713_report = _load_source_report(root, source_report=source_report)
    live_preflight = live_retrieval_preflight(v4713_report)
    llm_preflight = local_llm_preflight(v4713_report)
    queues = silver_answerability_root_cause_queues(v4713_report)
    counters = _build_counters(live_preflight=live_preflight, llm_preflight=llm_preflight, queues=queues)
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
        "artifact_sha256": {},
        "source_run_id": SOURCE_RUN_ID,
        "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
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
        "SearchView_vector_payload_role": "candidate_only",
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "live_retrieval_preflight": live_preflight,
        "local_llm_preflight": llm_preflight,
        "full_pdf_generation_rows": [],
        "silver_answerability_root_cause_queues": queues,
        "counters": counters,
        "completion_branch": "artifact_ready_fail_closed_diagnostic_ready",
        "non_gold_ambiguity_decisions": [
            {
                "decision": "v4_7_13_unavailable_live_retrieval_is_precondition_outcome",
                "reason": "row_count=0 because no read-only live SearchIndexContract was configured; no retrieval rows were evaluated",
            },
            {
                "decision": "v4_7_13_unavailable_local_llm_is_generation_not_attempted",
                "reason": "generated_response_count=0 means parser, citation, and claim-support checks did not run",
            },
        ],
        "residual_risks": [
            "live retrieval quality remains unevaluated until a read-only SearchIndexContract is configured",
            "full PDF answer quality remains unevaluated until the local LLM endpoint is available",
        ],
    }
    if check:
        check_report(report)
    return report


def write_report_bundle(root: Path, report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    report = json.loads(json.dumps(report, ensure_ascii=False))
    write_json(root / SHORT_REPORT_PATH, report)
    hashes = {"report_json_sha256": sha256_file(root / SHORT_REPORT_PATH)}
    return report, hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    counters = report["counters"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "diagnostic_v4_7_14_precondition_hardening_nonprod",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "source_run_id": SOURCE_RUN_ID,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "protected_namespaces_touched": [],
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
        "live_retrieval_precondition_unavailable_count": counters["live_retrieval_precondition_unavailable_count"],
        "live_retrieval_quality_failure_count": counters["live_retrieval_quality_failure_count"],
        "llm_unavailable_skip_count": counters["llm_unavailable_skip_count"],
        "generated_response_count": counters["generated_response_count"],
        "claim_support_not_evaluated_due_to_no_generation_count": counters[
            "claim_support_not_evaluated_due_to_no_generation_count"
        ],
        "claim_support_fail_count": counters["claim_support_fail_count"],
        "parser_failure_count": counters["parser_failure_count"],
        "citation_failure_count": counters["citation_failure_count"],
        "unsupported_answer_count": counters["unsupported_answer_count"],
        "noop_or_extractive_fallback_answer_count": counters["noop_or_extractive_fallback_answer_count"],
        "silver_answerability_overlay_row_count": counters["silver_answerability_overlay_row_count"],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def append_status(root: Path, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    path = root / STATUS_JSONL_PATH
    rows = read_jsonl(path) if path.exists() else []
    rows = [
        row
        for row in rows
        if row.get("run_id") not in {SHORT_RUN_ID, CANONICAL_LONG_RUN_ID}
        and row.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID
        and row.get("event_type") != "diagnostic_v4_7_14_precondition_hardening_nonprod"
    ]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    write_jsonl(path, rows)


def _upsert_block(text: str, *, start_marker: str, end_marker: str, block: str, after_anchor: str | None = None) -> str:
    wrapped = f"{start_marker}\n{block.rstrip()}\n{end_marker}"
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.S)
    if pattern.search(text):
        return pattern.sub(wrapped, text, count=1)
    if after_anchor and after_anchor in text:
        return text.replace(after_anchor, after_anchor + "\n\n" + wrapped, 1)
    return wrapped + "\n" + text


def _sync_last_updated(text: str) -> str:
    return re.sub(r"Last updated: .*? KST\.", f"Last updated: {KST_DOC_DATE} KST.", text, count=1)


def _replace_summary_block(text: str, *, block: str) -> str:
    start = "<!-- v4_7_14_summary_start -->"
    end = "<!-- v4_7_14_summary_end -->"
    old_pattern = re.compile(r"<!-- v4_7_13_summary_start -->.*?<!-- v4_7_13_summary_end -->", re.S)
    wrapped = f"{start}\n{block.rstrip()}\n{end}"
    if old_pattern.search(text):
        return old_pattern.sub(wrapped, text, count=1)
    return _upsert_block(text, start_marker=start, end_marker=end, block=block)


def update_docs(root: Path, report: Mapping[str, Any]) -> None:
    counters = report["counters"]
    queues = report["silver_answerability_root_cause_queues"]["queues_by_family"]
    progress = root / "docs/rag-ingestion-progress.md"
    measurements = root / "docs/rag-ingestion-measurements.md"
    triage = root / "docs/rag-ingestion-triage.md"
    readme = root / "README.md"
    eval_readme = root / "ai/eval/README.md"
    scripts_readme = root / "ai/scripts/README.md"

    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} is artifact-ready / fail-closed diagnostic-ready. "
        f"Artifact: `{SHORT_REPORT_PATH.as_posix()}`. Live retrieval precondition unavailable "
        f"{counters['live_retrieval_precondition_unavailable_count']} and retrieval-quality failures "
        f"{counters['live_retrieval_quality_failure_count']}; local LLM unavailable skips "
        f"{counters['llm_unavailable_skip_count']} and claim-support failures {counters['claim_support_fail_count']}. "
        "No fake/noop/extractive fallback answer is emitted. Silver overlay queues remain diagnostic-only over 90 rows. "
        "official_metric_input_rows=0, silver_official_metric_input_rows=0, silver_promoted_to_gold_count=0, "
        "promotion_evidence=false, product_success_evidence_allowed=false, live_db_index_cache_readiness=false."
    )
    progress.write_text(
        _sync_last_updated(
            _upsert_block(
                progress.read_text(encoding="utf-8"),
                start_marker="<!-- v4_7_14_diagnostic_precondition_hardening:progress-entry:start -->",
                end_marker="<!-- v4_7_14_diagnostic_precondition_hardening:progress-entry:end -->",
                block=progress_block,
                after_anchor="# RAG Ingestion Progress",
            )
        ),
        encoding="utf-8",
    )

    measurements_block = f"""## v4_7_14 diagnostic precondition hardening

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`

| counter | value |
| --- | --- |
| status | {STATUS} |
| live_retrieval_preflight_status | {report['live_retrieval_preflight']['status']} |
| live_retrieval_precondition_unavailable_count | {counters['live_retrieval_precondition_unavailable_count']} |
| live_retrieval_quality_failure_count | {counters['live_retrieval_quality_failure_count']} |
| local_llm_preflight_status | {report['local_llm_preflight']['status']} |
| llm_unavailable_skip_count | {counters['llm_unavailable_skip_count']} |
| generated_response_count | {counters['generated_response_count']} |
| parser_failure_count | {counters['parser_failure_count']} |
| claim_support_fail_count | {counters['claim_support_fail_count']} |
| citation_failure_count | {counters['citation_failure_count']} |
| unsupported_answer_count | {counters['unsupported_answer_count']} |
| claim_support_not_evaluated_due_to_no_generation_count | {counters['claim_support_not_evaluated_due_to_no_generation_count']} |
| silver_answerability_overlay_row_count | {counters['silver_answerability_overlay_row_count']} |
| official_metric_input_rows | 0 |
"""
    measurements.write_text(
        _sync_last_updated(
            _upsert_block(
                measurements.read_text(encoding="utf-8"),
                start_marker="<!-- v4_7_14_measurements_start -->",
                end_marker="<!-- v4_7_14_measurements_end -->",
                block=measurements_block,
                after_anchor="# RAG Ingestion Measurements",
            )
        ),
        encoding="utf-8",
    )

    text_counts = queues["TEXT"]["root_cause_counts"]
    xlsx_counts = queues["XLSX"]["root_cause_counts"]
    pdf_counts = queues["PDF"]["root_cause_counts"]
    triage_block = (
        f"- {SHORT_RUN_ID} diagnostic-only root-cause queues: "
        f"TEXT target_not_in_topk {text_counts['target_not_in_topk']} and evidence_mismatch_after_family_route "
        f"{text_counts['evidence_mismatch_after_family_route']}; "
        f"XLSX target_not_in_topk {xlsx_counts['target_not_in_topk']} and repeated_prefix_cluster "
        f"{xlsx_counts['repeated_prefix_cluster']}; "
        f"PDF evidence_window_insufficient {pdf_counts['evidence_window_insufficient']}, "
        f"source_family_route_ok_but_evidence_mismatch {pdf_counts['source_family_route_ok_but_evidence_mismatch']}, "
        f"and query_too_broad {pdf_counts['query_too_broad']}. "
        "These are diagnostic-only queues; silver, gold, qrels, labels, expected/supporting evidence, denominator rows, "
        "source registry, cache, production DB, and indexes are not mutated. SearchView/vector payload remains "
        "candidate-only; SourceAtom/EvidenceBundle remains evidence truth."
    )
    triage.write_text(
        _sync_last_updated(
            _upsert_block(
                triage.read_text(encoding="utf-8"),
                start_marker="<!-- v4_7_14_triage_start -->",
                end_marker="<!-- v4_7_14_triage_end -->",
                block=triage_block,
                after_anchor="# RAG Ingestion Triage",
            )
        ),
        encoding="utf-8",
    )

    summary_block = (
        "## Current RAG Diagnostic Status\n"
        f"Current RAG status: `{STATUS}`.\n"
        "`current` resolves to `v4_7_14`: non-production diagnostic precondition hardening over v4_7_13. "
        f"Live retrieval unavailable is represented as precondition unavailable, retrieval-quality failures "
        f"{counters['live_retrieval_quality_failure_count']}; local LLM unavailable skips "
        f"{counters['llm_unavailable_skip_count']} with generated responses {counters['generated_response_count']} "
        f"and claim-support failures {counters['claim_support_fail_count']}. "
        "No raw prompt or raw response payload is written. Canonical progress/details: "
        "`docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and "
        "`docs/rag-ingestion-triage.md`. prior v4_7 cleanup keys remain explicit for historical checks.\n"
        "Lineage breadcrumbs: v4_7 remains pre-official; it supersedes the abstract v4_7_1 Korean review packet; "
        "the hydrated packet has hydrated rows 204, PDF 100, XLSX 104 and non-empty `질의문` 204; "
        "v4_7_3 applies the user-reviewed Korean query candidate CSV and v4_7_3 applies the user-reviewed CSV "
        "decisions with 미검수=통과; PDF survivor 58 and v4_7_4 replays only the 58 user-passed PDF survivor "
        "candidates. official_metric_input_rows=0. "
        "## Korean human review packet. The previous v4_7_1 Korean review packet was abstract; "
        "review_packet_ko_hydrated.xlsx carries actual Korean query candidates. "
        "User-owned fields remain blank/default; not official metric. fine_tuning_executed=false.\n"
        "Hard boundary: diagnostic-only, non-production, not official metric, not gold/qrels/labels, "
        "not denominator/training/fine-tuning/FT-A, not promotion evidence, and not live readiness."
    )
    for path in (readme, eval_readme):
        path.write_text(_replace_summary_block(path.read_text(encoding="utf-8"), block=summary_block), encoding="utf-8")

    row = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        "`current` resolves to `v4_7_14`, `v4_7_13_live_retrieval_answerability_and_full_pdf_replay` remains explicit, "
        "`v4_7_12_layered_retrieval_generalization_and_overfit_audit` records layered retrieval audit rows 1057, "
        "`v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness`, "
        "`v4_7_9_pdf_evidence_residual_answer_quality_replay`, and prior v4_7 cleanup keys remain checkable "
        "without opening official metrics. |"
    )
    scripts_text = scripts_readme.read_text(encoding="utf-8")
    scripts_text = re.sub(r"\| `rag_eval.py` \|.*?\|", row, scripts_text, count=1)
    scripts_readme.write_text(scripts_text, encoding="utf-8")


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v4_7_14 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v4_7_14 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v4_7_14 status mismatch")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v4_7_14 must remain diagnostic-only and non-production")
    for key in (
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
    ):
        if report.get(key) is not False:
            raise ValueError(f"v4_7_14 opened forbidden gate: {key}")
    if report.get("official_metric_input_rows") != 0:
        raise ValueError("v4_7_14 official_metric_input_rows must stay 0")
    if report.get("silver_official_metric_input_rows") != 0 or report.get("silver_promoted_to_gold_count") != 0:
        raise ValueError("v4_7_14 opened silver official or promotion surface")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_14 touched protected namespaces")
    if report.get("SearchView_vector_payload_role") != "candidate_only":
        raise ValueError("v4_7_14 SearchView/vector payload role changed")
    if report.get("SourceAtom_EvidenceBundle_role") != "evidence_truth":
        raise ValueError("v4_7_14 SourceAtom/EvidenceBundle role changed")

    live = report.get("live_retrieval_preflight") or {}
    if live.get("status") == "LIVE_RETRIEVAL_PRECONDITION_UNAVAILABLE_FAIL_CLOSED":
        source_candidate_count = _as_int(live.get("source_candidate_row_count"))
        live_not_evaluated = live.get("not_evaluated_count_by_reason") or {}
        if _as_int(live.get("row_count")) != 0:
            raise ValueError("live precondition unavailable row_count must stay 0")
        if _as_int(live.get("attempted_row_count")) != 0 or _as_int(live.get("quality_evaluated_row_count")) != 0:
            raise ValueError("live precondition attempted/evaluated counts must stay 0")
        if (
            _as_int(live_not_evaluated.get("read_only_live_SearchIndexContract_unavailable"))
            != source_candidate_count
        ):
            raise ValueError("live precondition not-evaluated count must match source candidate rows")
        if _as_int(live.get("retrieval_quality_failure_count")) != 0:
            raise ValueError("precondition unavailable states must not be counted as quality failures")
        for key in ("production_db_mutated", "cache_mutated", "source_registry_mutated", "silver_mutated", "index_rebuilt"):
            if live.get(key) is not False:
                raise ValueError(f"v4_7_14 live preflight mutated forbidden surface: {key}")

    llm = report.get("local_llm_preflight") or {}
    if llm.get("status") == "LOCAL_LLM_UNAVAILABLE_GENERATION_NOT_ATTEMPTED_FAIL_CLOSED":
        eligible_count = _as_int(llm.get("eligible_count"))
        llm_not_evaluated = llm.get("not_evaluated_count_by_reason") or {}
        if _as_int(llm.get("attempted_row_count")) != 0 or _as_int(llm.get("quality_evaluated_row_count")) != 0:
            raise ValueError("local LLM unavailable attempted/evaluated counts must stay 0")
        if _as_int(llm_not_evaluated.get("local_LLM_unavailable_or_generation_not_attempted")) != eligible_count:
            raise ValueError("local LLM unavailable not-evaluated count must match eligible rows")
        if llm.get("raw_prompt_payload_written") is not False or llm.get("raw_response_payload_written") is not False:
            raise ValueError("v4_7_14 raw prompt/response payload must not be written")
        for key in (
            "generated_response_count",
            "parser_failure_count",
            "claim_support_fail_count",
            "citation_failure_count",
            "unsupported_answer_count",
            "noop_or_extractive_fallback_answer_count",
        ):
            if _as_int(llm.get(key)) != 0:
                raise ValueError("precondition unavailable states must not be counted as quality failures")
        for key in (
            "parser_not_evaluated_count",
            "citation_not_evaluated_count",
            "claim_support_not_evaluated_due_to_no_generation_count",
            "llm_unavailable_skip_count",
        ):
            if _as_int(llm.get(key)) != eligible_count:
                raise ValueError("v4_7_14 not-evaluated count must match eligible rows")
        if report.get("full_pdf_generation_rows") != []:
            raise ValueError("v4_7_14 unavailable local LLM emitted generation rows")

    counters = report.get("counters") or {}
    required = (
        "current_resolves_to",
        "official_metric_input_rows",
        "silver_official_metric_input_rows",
        "silver_promoted_to_gold_count",
        "live_retrieval_precondition_unavailable_count",
        "live_retrieval_quality_failure_count",
        "live_retrieval_quality_failure_count_by_family",
        "llm_unavailable_skip_count",
        "claim_support_not_evaluated_due_to_no_generation_count",
        "generated_response_count",
        "parser_failure_count",
        "claim_support_fail_count",
        "citation_failure_count",
        "unsupported_answer_count",
        "noop_or_extractive_fallback_answer_count",
        "silver_answerability_overlay_row_count",
    )
    missing = [key for key in required if key not in counters]
    if missing:
        raise ValueError(f"v4_7_14 missing counters: {missing}")
    if counters["current_resolves_to"] != LOGICAL_RUN_KEY:
        raise ValueError("current must resolve to v4_7_14")
    if counters["official_metric_input_rows"] != 0 or counters["silver_official_metric_input_rows"] != 0:
        raise ValueError("v4_7_14 opened official metric rows")
    if counters["silver_promoted_to_gold_count"] != 0:
        raise ValueError("v4_7_14 promoted silver")
    if (
        counters.get("raw_prompt_payload_written") is not False
        or counters.get("raw_response_payload_written") is not False
    ):
        raise ValueError("v4_7_14 raw prompt/response payload must not be written")
    for key in FORBIDDEN_QUALITY_FAILURE_COUNTERS:
        if _as_int(counters.get(key)) != 0:
            raise ValueError("precondition unavailable states must not be counted as quality failures")
    if counters.get("live_retrieval_quality_failure_count_by_family") != dict(ZERO_BY_FAMILY):
        raise ValueError("precondition unavailable states must not be counted as quality failures")
    if _as_int(counters.get("live_retrieval_attempted_row_count")) != 0 or _as_int(
        counters.get("live_retrieval_quality_evaluated_row_count")
    ) != 0:
        raise ValueError("live precondition attempted/evaluated counts must stay 0")
    if _as_int(counters.get("llm_attempted_row_count")) != 0 or _as_int(
        counters.get("llm_quality_evaluated_row_count")
    ) != 0:
        raise ValueError("local LLM unavailable attempted/evaluated counts must stay 0")
    if _as_int(counters.get("llm_unavailable_skip_count")) != _as_int(llm.get("eligible_count")):
        raise ValueError("v4_7_14 local LLM skip count must match eligible rows")
    if _as_int(counters.get("claim_support_not_evaluated_due_to_no_generation_count")) != _as_int(
        llm.get("eligible_count")
    ):
        raise ValueError("v4_7_14 claim support not-evaluated count must match eligible rows")
    for key in ("parser_not_evaluated_count", "citation_not_evaluated_count"):
        if _as_int(counters.get(key)) != _as_int(llm.get("eligible_count")):
            raise ValueError("v4_7_14 not-evaluated count must match eligible rows")

    queues = report.get("silver_answerability_root_cause_queues") or {}
    if queues.get("diagnostic_silver_only") is not True:
        raise ValueError("v4_7_14 queues must stay diagnostic silver only")
    for key in (
        "silver_mutation",
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "denominator_mutation",
    ):
        if queues.get(key) is not False:
            raise ValueError(f"v4_7_14 queue opened forbidden surface: {key}")
    if _as_int(queues.get("silver_promoted_to_gold_count")) != 0 or _as_int(queues.get("official_metric_input_rows")) != 0:
        raise ValueError("v4_7_14 queue opened official or promotion surface")
