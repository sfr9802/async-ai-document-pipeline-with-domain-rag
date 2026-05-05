"""Produce the Track C C8.3 diagnostic case-level review report.

C8.3 consumes the already-frozen C8/C8.1/C8.2 diagnostic artifacts and turns
the 7 reviewed non-table failures into case-level decisions. It does not run
promotion, mutate gold v0, tune retrieval, reindex, regenerate PDF artifacts,
or query the vector index.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from rag_pdf_policy_common import (  # noqa: E402
    EVIDENCE_ROLE,
    PDF_ARTIFACT_DIR,
    PDF_CANDIDATE_NAMESPACE,
    clean,
    dedupe,
    file_sha256,
    print_json,
    read_csv_rows,
    read_json,
    report_ref,
    utc_run_id,
    utc_timestamp,
    write_json,
)


DEFAULT_RANK_PROBE = Path("reports/rag_pdf_c8_rank_probe_report.json")
DEFAULT_CASE_INVESTIGATION = Path("reports/rag_pdf_c8_case_investigation_report.json")
DEFAULT_CASE_PACK = Path("reports/rag_pdf_retrieval_tuning_case_pack.json")
DEFAULT_REVIEWED_DIAGNOSTIC = Path("reports/rag_retrieval_eval_pdf_v1_reviewed_vector_diagnostic_report.json")
DEFAULT_REVIEWED_MANIFEST = Path("eval/gold_queries_pdf_v1_reviewed.csv")
DEFAULT_OUTPUT = Path("reports/rag_pdf_c8_case_level_review_report.json")

EXPECTED_CASE_COUNT = 7
EXPECTED_NEXT_ACTION_COUNTS = {
    "FILE_DISAMBIGUATION_REVIEW": 1,
    "LEXICAL_EXACT_PHRASE_PROBE_REVIEW": 1,
    "QUERY_SURFACE_REVIEW": 5,
}

ALLOWED_CASE_DECISIONS = {
    "KEEP_AS_STRESS_CASE",
    "REWRITE_QUERY_SURFACE",
    "REQUIRE_GOLD_BINDING_REVIEW",
    "REQUIRE_EXPECTED_PAGE_REVIEW",
    "REQUIRE_EMBEDDING_SURFACE_REVIEW",
    "REQUIRE_FILE_DISAMBIGUATION_POLICY",
    "DEFER_NO_TUNING",
}

QUERY_SURFACE_REWRITES = {
    "gq_pdf_page_lookup_003": "목차 위치를 찾아줘",
    "gq_auto_009": "주요 국가 국내총생산 규모 표의 기간 항목을 찾아줘",
    "gq_auto_014": "달러 기준 1인당 국내총생산 표를 찾아줘",
    "gq_auto_019": "1인당 국내총생산 표의 기간 항목을 찾아줘",
    "gq_auto_025": "목차에서 부문별 동향 위치를 찾아줘",
}

CASE_REVIEW_OVERRIDES = {
    "gq_pdf_page_lookup_003": {
        "case_decision": "REWRITE_QUERY_SURFACE",
        "review_requirements": {
            "query_surface_rewrite": True,
            "gold_binding_review": False,
            "expected_page_review": False,
            "embedding_surface_review": False,
            "file_disambiguation_policy": False,
            "stress_case_option": True,
        },
    },
    "gq_pdf_section_question_002": {
        "case_decision": "REQUIRE_FILE_DISAMBIGUATION_POLICY",
        "review_requirements": {
            "query_surface_rewrite": False,
            "gold_binding_review": False,
            "expected_page_review": False,
            "embedding_surface_review": False,
            "file_disambiguation_policy": True,
            "stress_case_option": False,
        },
    },
    "gq_pdf_section_question_003": {
        "case_decision": "REQUIRE_EMBEDDING_SURFACE_REVIEW",
        "review_requirements": {
            "query_surface_rewrite": False,
            "gold_binding_review": False,
            "expected_page_review": True,
            "embedding_surface_review": True,
            "file_disambiguation_policy": False,
            "stress_case_option": False,
        },
    },
    "gq_auto_009": {
        "case_decision": "REWRITE_QUERY_SURFACE",
        "review_requirements": {
            "query_surface_rewrite": True,
            "gold_binding_review": False,
            "expected_page_review": False,
            "embedding_surface_review": False,
            "file_disambiguation_policy": False,
            "stress_case_option": True,
        },
    },
    "gq_auto_014": {
        "case_decision": "REWRITE_QUERY_SURFACE",
        "review_requirements": {
            "query_surface_rewrite": True,
            "gold_binding_review": False,
            "expected_page_review": False,
            "embedding_surface_review": False,
            "file_disambiguation_policy": False,
            "stress_case_option": True,
        },
    },
    "gq_auto_019": {
        "case_decision": "REWRITE_QUERY_SURFACE",
        "review_requirements": {
            "query_surface_rewrite": True,
            "gold_binding_review": False,
            "expected_page_review": False,
            "embedding_surface_review": False,
            "file_disambiguation_policy": False,
            "stress_case_option": True,
        },
    },
    "gq_auto_025": {
        "case_decision": "REWRITE_QUERY_SURFACE",
        "review_requirements": {
            "query_surface_rewrite": True,
            "gold_binding_review": False,
            "expected_page_review": False,
            "embedding_surface_review": False,
            "file_disambiguation_policy": False,
            "stress_case_option": True,
        },
    },
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rank_probe_path = Path(args.rank_probe)
    case_investigation_path = Path(args.case_investigation)
    case_pack_path = Path(args.case_pack)
    reviewed_diagnostic_path = Path(args.reviewed_diagnostic)
    reviewed_manifest_path = Path(args.reviewed_manifest)

    payload = build_case_level_review_report(
        rank_probe=read_json(rank_probe_path),
        case_investigation=read_json(case_investigation_path),
        case_pack=read_json(case_pack_path),
        reviewed_diagnostic=read_json(reviewed_diagnostic_path),
        reviewed_manifest_rows=read_csv_rows(reviewed_manifest_path),
        rank_probe_path=rank_probe_path,
        case_investigation_path=case_investigation_path,
        case_pack_path=case_pack_path,
        reviewed_diagnostic_path=reviewed_diagnostic_path,
        reviewed_manifest_path=reviewed_manifest_path,
    )
    write_json(Path(args.output), payload)
    print_json(payload)
    return 0 if payload.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rank-probe", default=str(DEFAULT_RANK_PROBE))
    parser.add_argument("--case-investigation", default=str(DEFAULT_CASE_INVESTIGATION))
    parser.add_argument("--case-pack", default=str(DEFAULT_CASE_PACK))
    parser.add_argument("--reviewed-diagnostic", default=str(DEFAULT_REVIEWED_DIAGNOSTIC))
    parser.add_argument("--reviewed-manifest", default=str(DEFAULT_REVIEWED_MANIFEST))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


def build_case_level_review_report(
    *,
    rank_probe: Mapping[str, Any],
    case_investigation: Mapping[str, Any],
    case_pack: Mapping[str, Any],
    reviewed_diagnostic: Mapping[str, Any],
    reviewed_manifest_rows: list[Mapping[str, Any]],
    rank_probe_path: Path,
    case_investigation_path: Path,
    case_pack_path: Path,
    reviewed_diagnostic_path: Path,
    reviewed_manifest_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = [
        "C8.3 remains diagnostic-only and requires case-level label/query/page/file follow-up before any tuning.",
    ]
    validate_inputs(
        rank_probe=rank_probe,
        case_investigation=case_investigation,
        case_pack=case_pack,
        reviewed_diagnostic=reviewed_diagnostic,
        reviewed_manifest_rows=reviewed_manifest_rows,
        blockers=blockers,
    )

    rank_rows = by_query_id(rank_probe.get("rows") or [])
    investigation_rows = by_query_id(case_investigation.get("rows") or [])
    case_pack_rows = by_query_id(case_pack.get("cases") or [])
    reviewed_diagnostic_rows = by_query_id(reviewed_diagnostic.get("rows") or [])
    manifest_rows = by_query_id(reviewed_manifest_rows)

    rows: list[dict[str, Any]] = []
    for query_id in rank_rows:
        rows.append(
            review_case(
                rank_row=rank_rows[query_id],
                investigation_row=investigation_rows.get(query_id, {}),
                case_pack_row=case_pack_rows.get(query_id, {}),
                reviewed_diagnostic_row=reviewed_diagnostic_rows.get(query_id, {}),
                manifest_row=manifest_rows.get(query_id, {}),
                blockers=blockers,
            )
        )

    if len(rows) != EXPECTED_CASE_COUNT:
        blockers.append(f"C8.3 must review exactly {EXPECTED_CASE_COUNT} C8 failures; got {len(rows)}")

    source_next_action_counts = count(rows, "source_next_action")
    if source_next_action_counts != EXPECTED_NEXT_ACTION_COUNTS:
        blockers.append(
            "C8.3 source_next_action counts must be "
            f"{EXPECTED_NEXT_ACTION_COUNTS}; got {source_next_action_counts}"
        )

    decision_counts = count(rows, "case_decision")
    next_action_counts = source_next_action_counts
    proposed_query_rewrite_count = sum(1 for row in rows if row.get("proposed_query_surface"))
    review_requirement_counts = count_review_requirements(rows)
    query_surface_audit_counts = count_query_surface_audits(rows)

    if any(decision not in ALLOWED_CASE_DECISIONS for decision in decision_counts):
        blockers.append(f"C8.3 case_decision must be one of {sorted(ALLOWED_CASE_DECISIONS)}")
    if proposed_query_rewrite_count != EXPECTED_NEXT_ACTION_COUNTS["QUERY_SURFACE_REVIEW"]:
        blockers.append("C8.3 must propose rewrites for exactly the 5 QUERY_SURFACE_REVIEW cases")
    if query_surface_audit_counts["filename_leak_count"]:
        blockers.append("C8.3 proposed query surfaces must not leak expected file names")
    if query_surface_audit_counts["latin_letter_count"]:
        blockers.append("C8.3 proposed query surfaces should avoid Latin letters")

    status = "BLOCKED_WITH_REASON" if blockers else "PASS_WITH_WARNINGS"
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C8.3",
        "report_role": "pdf_c8_case_level_review",
        "promotion_evidence": False,
        "evidence_role": EVIDENCE_ROLE,
        "pdf_candidate_namespace": PDF_CANDIDATE_NAMESPACE,
        "pdf_artifact_dir": PDF_ARTIFACT_DIR,
        "retrieval_tuning_executed": False,
        "retrieval_execution": "not_run_by_this_script",
        "indexing_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "baseline_execution": "not_run_by_this_script",
        "gold_mutation_execution": "not_run_by_this_script",
        "immutable_baseline_changed": False,
        "xlsx_candidate_artifact_changed": False,
        "table_specific_retrieval_proven": False,
        "broad_tuning_recommended": False,
        "input_reports": {
            "rank_probe": report_ref(rank_probe, rank_probe_path),
            "case_investigation": report_ref(case_investigation, case_investigation_path),
            "case_pack": report_ref(case_pack, case_pack_path),
            "reviewed_diagnostic": report_ref(reviewed_diagnostic, reviewed_diagnostic_path),
            "reviewed_manifest": {
                "path": str(reviewed_manifest_path),
                "exists": reviewed_manifest_path.exists(),
                "sha256": file_sha256(reviewed_manifest_path)
                if reviewed_manifest_path.exists() and reviewed_manifest_path.is_file()
                else None,
            },
        },
        "case_count": len(rows),
        "decision_counts": decision_counts,
        "next_action_counts": next_action_counts,
        "review_requirement_counts": review_requirement_counts,
        "query_surface_audit_counts": query_surface_audit_counts,
        "proposed_query_rewrite_count": proposed_query_rewrite_count,
        "gold_binding_review_required_count": review_requirement_counts["gold_binding_review"],
        "expected_page_review_required_count": review_requirement_counts["expected_page_review"],
        "file_disambiguation_policy_required_count": review_requirement_counts["file_disambiguation_policy"],
        "embedding_surface_review_required_count": review_requirement_counts["embedding_surface_review"],
        "rows": rows,
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "next_action": (
            "Apply C8.3 case decisions to labels/query surfaces/page or file policy before any narrow retrieval experiment."
            if not blockers
            else "Resolve C8.3 blockers before using this report."
        ),
        "notes": [
            "Promotion was not run.",
            "C8.3 does not modify eval/gold_queries_v0.csv or reviewed manifests.",
            "C8.3 does not run broad retrieval tuning, hybrid search, reranking, parser expansion, reindexing, or artifact regeneration.",
            "Page aggregation and lexical findings are inherited diagnostics and do not prove table-specific retrieval.",
        ],
    }


def review_case(
    *,
    rank_row: Mapping[str, Any],
    investigation_row: Mapping[str, Any],
    case_pack_row: Mapping[str, Any],
    reviewed_diagnostic_row: Mapping[str, Any],
    manifest_row: Mapping[str, Any],
    blockers: list[str],
) -> dict[str, Any]:
    query_id = clean(rank_row.get("query_id"))
    if not investigation_row:
        blockers.append(f"{query_id} is missing from C8.1 case investigation rows")
    if not case_pack_row:
        blockers.append(f"{query_id} is missing from C8 case pack rows")
    if not manifest_row:
        blockers.append(f"{query_id} is missing from reviewed PDF manifest rows")
    override = CASE_REVIEW_OVERRIDES.get(query_id)
    if not override:
        blockers.append(f"C8.3 has no manual review override for {query_id}")
        override = {
            "case_decision": "DEFER_NO_TUNING",
            "review_requirements": default_review_requirements(),
        }

    source_next_action = clean(rank_row.get("rank_probe_next_action"))
    vector_probe = rank_row.get("vector_probe") if isinstance(rank_row.get("vector_probe"), Mapping) else {}
    page_aggregation = (
        rank_row.get("page_aggregation_probe")
        if isinstance(rank_row.get("page_aggregation_probe"), Mapping)
        else {}
    )
    lexical_probe = rank_row.get("lexical_probe") if isinstance(rank_row.get("lexical_probe"), Mapping) else {}
    case_decision = clean(override.get("case_decision"))
    review_requirements = dict(override.get("review_requirements") or default_review_requirements())
    proposed_query_surface = QUERY_SURFACE_REWRITES.get(query_id) if case_decision == "REWRITE_QUERY_SURFACE" else None
    query_surface_audit = audit_query_surface(
        original_query=rank_row.get("query"),
        proposed_query=proposed_query_surface,
        expected_file_name=first_nonempty(
            rank_row.get("expected_file_name"),
            manifest_row.get("expected_file_name"),
            reviewed_diagnostic_row.get("expected_file_name"),
        ),
        expected_document_version_id=first_nonempty(
            rank_row.get("expected_document_version_id"),
            investigation_row.get("expected_document_version_id"),
            manifest_row.get("expected_document_version_id"),
        ),
    )

    row = {
        "query_id": query_id,
        "query": first_nonempty(rank_row.get("query"), investigation_row.get("query"), manifest_row.get("query")),
        "bucket": first_nonempty(rank_row.get("bucket"), investigation_row.get("bucket"), manifest_row.get("bucket")),
        "source_next_action": source_next_action,
        "source_root_cause": first_nonempty(rank_row.get("source_root_cause"), investigation_row.get("root_cause")),
        "source_case_pack_next_action": case_pack_row.get("next_action"),
        "expected_document_version_id": first_nonempty(
            rank_row.get("expected_document_version_id"),
            investigation_row.get("expected_document_version_id"),
            manifest_row.get("expected_document_version_id"),
        ),
        "expected_file_name": first_nonempty(
            rank_row.get("expected_file_name"),
            manifest_row.get("expected_file_name"),
            reviewed_diagnostic_row.get("expected_file_name"),
        ),
        "expected_page_no": first_nonempty(
            rank_row.get("expected_page_no"),
            investigation_row.get("expected_page_no"),
            manifest_row.get("expected_page_no"),
        ),
        "expected_physical_page_index": first_nonempty(
            rank_row.get("expected_physical_page_index"),
            investigation_row.get("expected_physical_page_index"),
            manifest_row.get("expected_physical_page_index"),
        ),
        "expected_bbox": first_nonempty(
            rank_row.get("expected_bbox"),
            investigation_row.get("expected_bbox"),
            manifest_row.get("expected_bbox"),
        ),
        "expected_file_first_rank": vector_probe.get("expected_file_first_rank"),
        "expected_docv_first_rank": vector_probe.get("expected_docv_first_rank"),
        "expected_page_first_rank": vector_probe.get("expected_page_first_rank"),
        "expected_exact_bbox_first_rank": vector_probe.get("expected_exact_bbox_first_rank"),
        "page_group_rank": page_aggregation.get("expected_page_group_rank"),
        "corpus_exact_phrase_unit_count": lexical_probe.get("corpus_exact_phrase_unit_count"),
        "competing_exact_phrase_page_count": lexical_probe.get("competing_exact_phrase_page_count"),
        "case_decision": case_decision,
        "secondary_case_decisions": secondary_decisions(source_next_action, review_requirements),
        "proposed_query_surface": proposed_query_surface,
        "query_surface_audit": query_surface_audit,
        "review_requirements": review_requirements,
        "source_policy_fields": {
            "label_status": manifest_row.get("label_status"),
            "pdf_review_label": manifest_row.get("pdf_review_label"),
            "pdf_match_policy": manifest_row.get("pdf_match_policy"),
            "pdf_table_policy": manifest_row.get("pdf_table_policy"),
            "pdf_bbox_policy": manifest_row.get("pdf_bbox_policy"),
            "review_decision": manifest_row.get("review_decision"),
            "positive_metric_eligible": manifest_row.get("positive_metric_eligible"),
        },
        "evidence_summary": evidence_summary(
            rank_row=rank_row,
            investigation_row=investigation_row,
            case_pack_row=case_pack_row,
        ),
        "why_not_broad_tuning": why_not_broad_tuning(
            source_next_action=source_next_action,
            vector_probe=vector_probe,
            lexical_probe=lexical_probe,
            page_aggregation=page_aggregation,
        ),
        "recommended_next_step": recommended_next_step(source_next_action),
    }

    if case_decision not in ALLOWED_CASE_DECISIONS:
        blockers.append(f"{query_id} has unsupported case_decision={case_decision}")
    if source_next_action == "QUERY_SURFACE_REVIEW" and not proposed_query_surface:
        blockers.append(f"{query_id} is QUERY_SURFACE_REVIEW but has no proposed query surface")
    if query_surface_audit["leaks_expected_file_name"]:
        blockers.append(f"{query_id} proposed query surface leaks the expected file name")
    if query_surface_audit["contains_latin_letters"]:
        blockers.append(f"{query_id} proposed query surface contains Latin letters")
    return row


def validate_inputs(
    *,
    rank_probe: Mapping[str, Any],
    case_investigation: Mapping[str, Any],
    case_pack: Mapping[str, Any],
    reviewed_diagnostic: Mapping[str, Any],
    reviewed_manifest_rows: list[Mapping[str, Any]],
    blockers: list[str],
) -> None:
    validate_report(
        rank_probe,
        name="C8.2 rank probe",
        require_namespace=True,
        require_artifact_dir=True,
        blockers=blockers,
    )
    validate_report(
        case_investigation,
        name="C8.1 case investigation",
        require_namespace=True,
        require_artifact_dir=True,
        blockers=blockers,
    )
    validate_report(
        case_pack,
        name="C8 case pack",
        require_namespace=True,
        require_artifact_dir=True,
        blockers=blockers,
    )
    validate_report(
        reviewed_diagnostic,
        name="C5.1 reviewed diagnostic",
        require_namespace=False,
        require_artifact_dir=False,
        blockers=blockers,
    )
    if rank_probe.get("case_count") != EXPECTED_CASE_COUNT:
        blockers.append(f"C8.2 rank probe must have case_count={EXPECTED_CASE_COUNT}")
    if rank_probe.get("refined_next_action_counts") != EXPECTED_NEXT_ACTION_COUNTS:
        blockers.append(
            "C8.2 refined_next_action_counts must be "
            f"{EXPECTED_NEXT_ACTION_COUNTS}; got {rank_probe.get('refined_next_action_counts')}"
        )
    if case_investigation.get("case_count") != EXPECTED_CASE_COUNT:
        blockers.append(f"C8.1 case investigation must have case_count={EXPECTED_CASE_COUNT}")
    if case_pack.get("case_count") != EXPECTED_CASE_COUNT:
        blockers.append(f"C8 case pack must have case_count={EXPECTED_CASE_COUNT}")
    if not reviewed_manifest_rows:
        blockers.append("reviewed PDF manifest must be readable and non-empty")
    if "broad_tuning_recommended" in case_pack and case_pack.get("broad_tuning_recommended") is not False:
        blockers.append("C8 case pack must keep broad_tuning_recommended=false")
    if "broad_tuning_recommended" in rank_probe and rank_probe.get("broad_tuning_recommended") is not False:
        blockers.append("C8.2 rank probe must keep broad_tuning_recommended=false")


def validate_report(
    report: Mapping[str, Any],
    *,
    name: str,
    require_namespace: bool,
    require_artifact_dir: bool,
    blockers: list[str],
) -> None:
    if report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"{name} must be PASS or PASS_WITH_WARNINGS; got {report.get('status')}")
    if report.get("promotion_evidence") is not False:
        blockers.append(f"{name} must keep promotion_evidence=false")
    if report.get("evidence_role") != EVIDENCE_ROLE:
        blockers.append(f"{name} must keep evidence_role=diagnostic")
    if "retrieval_tuning_executed" in report and report.get("retrieval_tuning_executed") is not False:
        blockers.append(f"{name} must keep retrieval_tuning_executed=false")
    if report.get("table_specific_retrieval_proven") is not False and "table_specific_retrieval_proven" in report:
        blockers.append(f"{name} must not claim table-specific retrieval is proven")
    if report.get("immutable_baseline_changed") is not False and "immutable_baseline_changed" in report:
        blockers.append(f"{name} must keep immutable_baseline_changed=false")
    if report.get("xlsx_candidate_artifact_changed") is not False and "xlsx_candidate_artifact_changed" in report:
        blockers.append(f"{name} must keep xlsx_candidate_artifact_changed=false")
    if require_namespace and report.get("pdf_candidate_namespace") != PDF_CANDIDATE_NAMESPACE:
        blockers.append(f"{name} namespace must match {PDF_CANDIDATE_NAMESPACE}")
    if require_artifact_dir and clean(report.get("pdf_artifact_dir")) != PDF_ARTIFACT_DIR:
        blockers.append(f"{name} artifact dir must match {PDF_ARTIFACT_DIR}")


def evidence_summary(
    *,
    rank_row: Mapping[str, Any],
    investigation_row: Mapping[str, Any],
    case_pack_row: Mapping[str, Any],
) -> str:
    vector_probe = rank_row.get("vector_probe") if isinstance(rank_row.get("vector_probe"), Mapping) else {}
    page_aggregation = (
        rank_row.get("page_aggregation_probe")
        if isinstance(rank_row.get("page_aggregation_probe"), Mapping)
        else {}
    )
    lexical_probe = rank_row.get("lexical_probe") if isinstance(rank_row.get("lexical_probe"), Mapping) else {}
    same_file = case_pack_row.get("same_file_hit_ranks") or investigation_row.get("same_file_hit_ranks") or []
    same_page = case_pack_row.get("same_page_hit_ranks") or investigation_row.get("same_page_hit_ranks") or []
    parts = [
        f"C8.2 action={rank_row.get('rank_probe_next_action')}",
        f"root_cause={rank_row.get('source_root_cause') or investigation_row.get('root_cause')}",
        "ranks(file/docv/page/exact_bbox)="
        f"{vector_probe.get('expected_file_first_rank')}/"
        f"{vector_probe.get('expected_docv_first_rank')}/"
        f"{vector_probe.get('expected_page_first_rank')}/"
        f"{vector_probe.get('expected_exact_bbox_first_rank')}",
        f"page_group_rank={page_aggregation.get('expected_page_group_rank')}",
        "lexical(exact_units/competing_pages)="
        f"{lexical_probe.get('corpus_exact_phrase_unit_count')}/"
        f"{lexical_probe.get('competing_exact_phrase_page_count')}",
        f"same_file_top10_ranks={same_file}",
        f"same_page_top10_ranks={same_page}",
    ]
    if investigation_row.get("evidence_summary"):
        parts.append(f"C8.1={investigation_row.get('evidence_summary')}")
    return "; ".join(parts) + "."


def why_not_broad_tuning(
    *,
    source_next_action: str,
    vector_probe: Mapping[str, Any],
    lexical_probe: Mapping[str, Any],
    page_aggregation: Mapping[str, Any],
) -> str:
    file_rank = vector_probe.get("expected_file_first_rank")
    docv_rank = vector_probe.get("expected_docv_first_rank")
    page_rank = vector_probe.get("expected_page_first_rank")
    exact_rank = vector_probe.get("expected_exact_bbox_first_rank")
    page_group_rank = page_aggregation.get("expected_page_group_rank")
    exact_units = lexical_probe.get("corpus_exact_phrase_unit_count")
    competing_pages = lexical_probe.get("competing_exact_phrase_page_count")
    if source_next_action == "QUERY_SURFACE_REVIEW":
        return (
            "The row has a short/generic query surface and repeated lexical evidence "
            f"(exact_units={exact_units}, competing_pages={competing_pages}); the expected file/docv is already "
            f"retrievable at ranks {file_rank}/{docv_rank}, but the expected page remains below top-10 "
            f"(page_rank={page_rank}, page_group_rank={page_group_rank}). That points to query/label surface "
            "review before any global retrieval change."
        )
    if source_next_action == "FILE_DISAMBIGUATION_REVIEW":
        return (
            "The query text is a repeated table label across PDFs: exact lexical evidence appears broadly "
            f"(exact_units={exact_units}, competing_pages={competing_pages}), while the expected file/docv/page "
            f"first appears at {file_rank}/{docv_rank}/{page_rank} and exact bbox at {exact_rank}. This needs "
            "file-context policy rather than broad tuning."
        )
    if source_next_action == "LEXICAL_EXACT_PHRASE_PROBE_REVIEW":
        return (
            "The expected file/docv is already rank 1 and the exact phrase exists on the expected page, but the "
            "strict expected page is absent from top-100. This is a page or embedding-surface anomaly to inspect "
            "case-by-case, not a broad recall/tuning failure."
        )
    return "The case has no broad-tuning signal until its diagnostic bucket is reviewed."


def recommended_next_step(source_next_action: str) -> str:
    if source_next_action == "QUERY_SURFACE_REVIEW":
        return (
            "Review and rewrite the query surface; if the original generic phrase is intentionally kept, label it "
            "as a stress case instead of using it as a tuning target."
        )
    if source_next_action == "FILE_DISAMBIGUATION_REVIEW":
        return (
            "Define the file/date disambiguation policy for repeated table labels, then decide whether the gold "
            "binding needs explicit user context."
        )
    if source_next_action == "LEXICAL_EXACT_PHRASE_PROBE_REVIEW":
        return (
            "Inspect the expected page binding and SearchUnit embedding/exact-phrase surface before proposing any "
            "retrieval experiment."
        )
    return "Defer retrieval changes until the row has a case-level label decision."


def secondary_decisions(source_next_action: str, review_requirements: Mapping[str, Any]) -> list[str]:
    decisions: list[str] = []
    if source_next_action == "QUERY_SURFACE_REVIEW" and review_requirements.get("stress_case_option"):
        decisions.append("KEEP_AS_STRESS_CASE")
    if review_requirements.get("expected_page_review"):
        decisions.append("REQUIRE_EXPECTED_PAGE_REVIEW")
    if review_requirements.get("gold_binding_review"):
        decisions.append("REQUIRE_GOLD_BINDING_REVIEW")
    return decisions


def count_review_requirements(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    keys = [
        "query_surface_rewrite",
        "gold_binding_review",
        "expected_page_review",
        "embedding_surface_review",
        "file_disambiguation_policy",
        "stress_case_option",
    ]
    counts = {key: 0 for key in keys}
    for row in rows:
        requirements = row.get("review_requirements") if isinstance(row.get("review_requirements"), Mapping) else {}
        for key in keys:
            if requirements.get(key):
                counts[key] += 1
    return counts


def count_query_surface_audits(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = {
        "rewrite_count": 0,
        "changed_from_original_count": 0,
        "filename_leak_count": 0,
        "document_version_leak_count": 0,
        "pdf_extension_leak_count": 0,
        "latin_letter_count": 0,
        "korean_surface_count": 0,
    }
    for row in rows:
        audit = row.get("query_surface_audit") if isinstance(row.get("query_surface_audit"), Mapping) else {}
        if audit.get("has_proposed_query_surface"):
            counts["rewrite_count"] += 1
        if audit.get("changed_from_original"):
            counts["changed_from_original_count"] += 1
        if audit.get("leaks_expected_file_name"):
            counts["filename_leak_count"] += 1
        if audit.get("leaks_expected_document_version_id"):
            counts["document_version_leak_count"] += 1
        if audit.get("contains_pdf_extension"):
            counts["pdf_extension_leak_count"] += 1
        if audit.get("contains_latin_letters"):
            counts["latin_letter_count"] += 1
        if audit.get("contains_korean"):
            counts["korean_surface_count"] += 1
    return counts


def audit_query_surface(
    *,
    original_query: Any,
    proposed_query: Any,
    expected_file_name: Any,
    expected_document_version_id: Any,
) -> dict[str, Any]:
    proposed = clean(proposed_query)
    original = clean(original_query)
    return {
        "has_proposed_query_surface": bool(proposed),
        "changed_from_original": bool(proposed) and proposed != original,
        "length_chars": len(proposed),
        "token_count": len([token for token in re.split(r"\s+", proposed) if token]),
        "contains_korean": bool(re.search(r"[가-힣]", proposed)),
        "contains_latin_letters": bool(re.search(r"[A-Za-z]", proposed)),
        "contains_pdf_extension": ".pdf" in proposed.lower(),
        "leaks_expected_file_name": leaks_file_name(proposed, expected_file_name),
        "leaks_expected_document_version_id": bool(
            proposed and clean(expected_document_version_id) and clean(expected_document_version_id) in proposed
        ),
        "short_user_like_surface": bool(proposed) and len(proposed) <= 40 and bool(re.search(r"[가-힣]", proposed)),
    }


def default_review_requirements() -> dict[str, bool]:
    return {
        "query_surface_rewrite": False,
        "gold_binding_review": False,
        "expected_page_review": False,
        "embedding_surface_review": False,
        "file_disambiguation_policy": False,
        "stress_case_option": False,
    }


def by_query_id(rows: Iterable[Any]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        query_id = clean(row.get("query_id"))
        if query_id:
            out[query_id] = row
    return out


def count(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean(row.get(key)) or "UNKNOWN"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def first_nonempty(*values: Any) -> Any:
    for value in values:
        if value is not None and clean(value):
            return value
    return None


def leaks_file_name(query: str, expected_file_name: Any) -> bool:
    file_name = clean(expected_file_name)
    if not file_name:
        return False
    stem = Path(file_name).stem
    lowered = query.lower()
    return file_name.lower() in lowered or stem.lower() in lowered


if __name__ == "__main__":
    raise SystemExit(main())
