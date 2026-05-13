"""Generate PDF strict retrieval/evidence diagnostic silver artifacts.

This script is report-only for the PDF retrieval/evidence sector. It never
opens PDF answer generation, never promotes route/fallback labels to official
metrics, and keeps the full manifest outside the repository unless a canonical
repo path is explicitly introduced later.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
EVAL_QUERY_DIR = AI_WORKER_ROOT / "eval" / "eval_queries"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_PDF_GOLD_CSV = EVAL_QUERY_DIR / "gold_queries_pdf_v0.csv"
DEFAULT_PDF_REVIEW_PACK_CSV = (
    REVIEW_DIR
    / "_archive"
    / "2026-05-11-review-cleanup"
    / "pdf_gold_v1"
    / "pdf_gold_v1_review_draft_pack.csv"
)
DEFAULT_POLICY_DECISIONS = REVIEW_DIR / "rag_gold_policy_applied_decisions_v1.json"
DEFAULT_ROUTE_LABEL_REVIEW_APPLIED = REVIEW_DIR / "route_gold_label_review_applied_v1.json"
DEFAULT_FALLBACK_OUTCOME_LABEL_REVIEW_APPLIED = REVIEW_DIR / "fallback_outcome_label_review_applied_v1.json"
DEFAULT_THREE_TRACK_REPORT = REPORT_DIR / "three_track_orchestration_report.json"
DEFAULT_REGISTRY = EVAL_QUERY_DIR / "official_denominator_registry.json"
DEFAULT_JSON_OUTPUT = REPORT_DIR / "pdf_strict_silver_generation_report.json"
DEFAULT_MD_OUTPUT = REPORT_DIR / "pdf_strict_silver_generation_report.md"
DEFAULT_EXTERNAL_SILVER_OUTPUT = (
    REPO_ROOT.parent
    / "_external_runtime_artifacts"
    / "async-ocr-rag-multimodal-pipeline"
    / "rag-ingestion"
    / "pdf_strict_silver_generation"
    / "pdf_strict_silver_retrieval_evidence_manifest.jsonl"
)

SCHEMA_VERSION = "pdf_strict_silver_generation_report_v1"
SILVER_SCHEMA_VERSION = "pdf_strict_retrieval_evidence_silver_v1"
TRACK = "pdf_business_ocr_mm"
PDF_CONTENT_EVIDENCE_LANE = "pdf_content_evidence"
PDF_FILE_IDENTITY_LANE = "pdf_file_identity"
PDF_CONTEXT_DIAGNOSTIC_ONLY_MISSING_LAYOUT = "pdf_context_diagnostic_only_missing_layout"
STABLE_IDENTITY_REQUIRED = "stable_identity_required"
FLATTENED_ONLY = "flattened_only"

REQUIRED_PDF_EVIDENCE_METADATA_FIELDS = (
    "file",
    "document_version_id",
    "page",
    "physical_page_index",
    "region_type",
    "bbox",
    "matched_text",
    "section_heading",
    "table_caption_footnote",
    "nearby_paragraphs",
    "OCR_confidence",
    "source_searchunit_id",
    "source_searchunit_rank",
    "parser_source_metadata",
    "citation_locator",
    "score",
)

STRICT_REQUIRED_NONEMPTY_FIELDS = (
    "file",
    "document_version_id",
    "page",
    "region_type",
    "bbox",
    "matched_text",
    "nearby_paragraphs",
    "OCR_confidence",
    "source_searchunit_id",
    "source_searchunit_rank",
    "parser_source_metadata",
    "citation_locator",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report, silver_rows = build_generation(
        pdf_gold_csv=Path(args.pdf_gold_csv),
        pdf_review_pack_csv=Path(args.pdf_review_pack_csv),
        policy_decisions=Path(args.policy_decisions),
        route_label_review_applied=Path(args.route_label_review_applied),
        fallback_outcome_label_review_applied=Path(args.fallback_outcome_label_review_applied),
        three_track_report=Path(args.three_track_report),
        official_denominator_registry=Path(args.official_denominator_registry),
        silver_output=Path(args.silver_output),
    )
    silver_output = Path(args.silver_output)
    if report["status"] == "COMPLETED_DIAGNOSTIC_ONLY":
        write_jsonl(silver_output, silver_rows)
        report["silver_artifact_policy"]["external_silver_artifact"] = file_identity(silver_output)
        report["silver_artifact_policy"]["external_silver_artifact_written"] = True
    else:
        report["silver_artifact_policy"]["external_silver_artifact"] = file_identity(silver_output)
        report["silver_artifact_policy"]["external_silver_artifact_written"] = False

    json_output = Path(args.json_output)
    md_output = Path(args.md_output)
    write_json(json_output, report)
    md_output.parent.mkdir(parents=True, exist_ok=True)
    md_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "json_output": repo_relative(json_output),
                "md_output": repo_relative(md_output),
                "external_silver_output": str(silver_output.resolve()),
                "input_denominator_row_count": report["counts"]["input_denominator_row_count"],
                "generated_silver_row_count": report["counts"]["generated_silver_row_count"],
                "diagnostic_only_fallback_row_count": report["counts"]["diagnostic_only_fallback_row_count"],
                "official_denominator_registry_changed": report["guardrails"][
                    "official_denominator_registry_changed"
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "COMPLETED_DIAGNOSTIC_ONLY" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-gold-csv", default=str(DEFAULT_PDF_GOLD_CSV))
    parser.add_argument("--pdf-review-pack-csv", default=str(DEFAULT_PDF_REVIEW_PACK_CSV))
    parser.add_argument("--policy-decisions", default=str(DEFAULT_POLICY_DECISIONS))
    parser.add_argument("--route-label-review-applied", default=str(DEFAULT_ROUTE_LABEL_REVIEW_APPLIED))
    parser.add_argument("--fallback-outcome-label-review-applied", default=str(DEFAULT_FALLBACK_OUTCOME_LABEL_REVIEW_APPLIED))
    parser.add_argument("--three-track-report", default=str(DEFAULT_THREE_TRACK_REPORT))
    parser.add_argument("--official-denominator-registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--silver-output", default=str(DEFAULT_EXTERNAL_SILVER_OUTPUT))
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--md-output", default=str(DEFAULT_MD_OUTPUT))
    return parser.parse_args(argv)


def build_report(**kwargs: Any) -> dict[str, Any]:
    report, _silver_rows = build_generation(**kwargs)
    return report


def build_generation(
    *,
    pdf_gold_csv: Path = DEFAULT_PDF_GOLD_CSV,
    pdf_review_pack_csv: Path = DEFAULT_PDF_REVIEW_PACK_CSV,
    policy_decisions: Path = DEFAULT_POLICY_DECISIONS,
    route_label_review_applied: Path = DEFAULT_ROUTE_LABEL_REVIEW_APPLIED,
    fallback_outcome_label_review_applied: Path = DEFAULT_FALLBACK_OUTCOME_LABEL_REVIEW_APPLIED,
    three_track_report: Path = DEFAULT_THREE_TRACK_REPORT,
    official_denominator_registry: Path = DEFAULT_REGISTRY,
    silver_output: Path = DEFAULT_EXTERNAL_SILVER_OUTPUT,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    assert_external_pdf_silver_output_path(silver_output)
    assert_canonical_strict_inputs(
        pdf_gold_csv=pdf_gold_csv,
        pdf_review_pack_csv=pdf_review_pack_csv,
        official_denominator_registry=official_denominator_registry,
    )
    registry_sha_before = sha256_file(official_denominator_registry)

    gold_rows = read_csv_rows(pdf_gold_csv)
    review_rows = read_csv_rows(pdf_review_pack_csv)
    registry_payload = load_json(official_denominator_registry)
    policy_payload = load_json(policy_decisions)
    route_payload = load_json(route_label_review_applied)
    fallback_payload = load_json(fallback_outcome_label_review_applied)
    three_track_payload = load_json(three_track_report)
    registry_sha_after = sha256_file(official_denominator_registry)

    denominator = pdf_registry_denominator(registry_payload)
    gold_by_id = {clean(row.get("query_id")): row for row in gold_rows if clean(row.get("query_id"))}
    review_by_id = {clean(row.get("query_id")): row for row in review_rows if clean(row.get("query_id"))}
    input_ids = [
        query_id
        for query_id, row in review_by_id.items()
        if clean(row.get("c7_decision_group")) == "matched_positive_control"
    ]
    input_ids = [query_id for query_id in input_ids if query_id in gold_by_id]
    diagnostic_candidates = [
        silver_row_from_sources(
            query_id=query_id,
            gold_row=gold_by_id[query_id],
            review_row=review_by_id.get(query_id, {}),
            retrieval_hit={},
            evidence_lane=PDF_CONTENT_EVIDENCE_LANE,
        )
        for query_id in input_ids
    ]
    silver_rows = [row for row in diagnostic_candidates if not row.get("diagnostic_only")]

    applied_decisions = policy_payload.get("applied_decisions") if isinstance(policy_payload.get("applied_decisions"), Mapping) else {}
    policy_excluded_ids = sorted(
        clean(query_id)
        for query_id in list_from_mapping(
            applied_decisions.get("pdf_excluded_from_gold_v0_1", {}),
            "query_ids",
        )
    )
    stable_identity_required_ids = sorted(
        clean(query_id)
        for query_id in list_from_mapping(
            applied_decisions.get("pdf_stable_identity_required_excluded", {}),
            "query_ids",
        )
    )
    deferred_rows = deferred_ocr_or_source_context_rows(route_payload, fallback_payload)
    diagnostic_fallback_rows = [
        {
            "query_id": row["query_id"],
            "reason": row["diagnostic_only_reason"],
            "missing_context_fields": row["missing_context_fields"],
            "evidence_lane": row["evidence_lane"],
        }
        for row in diagnostic_candidates
        if row.get("diagnostic_only")
    ]

    guardrail_payloads = (three_track_payload, policy_payload, route_payload, fallback_payload)
    guardrails = {
        "official_denominator_registry_changed": registry_sha_before != registry_sha_after,
        "official_denominator_opened_or_frozen": nested_guardrail_flag(
            *guardrail_payloads,
            keys=(
                "official_denominator_opened_or_frozen",
                "official_denominator_opened",
                "official_denominator_frozen",
                "official_denominator_open_or_freeze",
            ),
        ),
        "promotion_evidence_created": nested_guardrail_flag(
            *guardrail_payloads,
            keys=(
                "promotion_evidence_created",
                "promotion_evidence",
                "production_promotion_evidence_created",
            ),
        ),
        "pdf_answer_generation_denominator_opened": pdf_answer_generation_denominator(three_track_payload) != 0,
        "production_namespace_mutated": nested_guardrail_flag(
            *guardrail_payloads,
            keys=("production_namespace_mutated", "production_namespace_mutation"),
        ),
        "production_vector_index_mutated": nested_guardrail_flag(
            *guardrail_payloads,
            keys=("production_vector_index_mutated",),
        ),
        "production_vector_written": nested_guardrail_flag(
            *guardrail_payloads,
            keys=("production_vector_written", "production_vector_write"),
        ),
        "repo_local_pdf_silver_manifest_written": silver_output.resolve().is_relative_to(REPO_ROOT.resolve()),
        "candidate_artifact_mutated": nested_guardrail_flag(
            *guardrail_payloads,
            keys=("candidate_artifact_mutated",),
        ),
        "immutable_baseline_mutated": nested_guardrail_flag(
            *guardrail_payloads,
            keys=("immutable_baseline_mutated",),
        ),
        "diagnostic_only_row_promoted": nested_guardrail_flag(
            *guardrail_payloads,
            keys=("diagnostic_only_row_promoted",),
        )
        or any(row.get("diagnostic_only") for row in silver_rows),
        "policy_excluded_rows_counted_as_retrieval_failures": nested_guardrail_flag(
            *guardrail_payloads,
            keys=("policy_excluded_rows_counted_as_retrieval_failures",),
        ),
        "route_fallback_labels_promoted_to_official_metrics": nested_guardrail_flag(
            *guardrail_payloads,
            keys=(
                "route_fallback_labels_official_metric",
                "route_metrics_official",
                "fallback_metrics_official",
                "official_routing_accuracy_computed",
                "official_wrong_route_rate_computed",
                "official_fallback_success_computed",
                "official_multi_route_success_computed",
                "official_metric_input_rows",
            ),
        ),
        "pdf_content_file_lanes_aggregated": nested_guardrail_flag(
            *guardrail_payloads,
            keys=(
                "pdf_content_and_file_identity_aggregated",
                "pdf_content_file_lanes_aggregated",
                "pdf_lanes_aggregated",
            ),
        ),
        "answer_generation_run": False,
        "answer_citation_surfaces_opened": False,
        "diagnostic_only_row_promoted_from_flattened_evidence": any(
            row.get("diagnostic_only") is False and row.get("diagnostic_only_reason") == FLATTENED_ONLY
            for row in silver_rows
        ),
    }
    validation_errors = validate_generation(
        denominator=denominator,
        input_ids=input_ids,
        silver_rows=silver_rows,
        diagnostic_candidates=diagnostic_candidates,
        policy_excluded_ids=policy_excluded_ids,
        stable_identity_required_ids=stable_identity_required_ids,
        guardrails=guardrails,
    )
    status = "COMPLETED_DIAGNOSTIC_ONLY" if not validation_errors else "FAILED_GUARDRAIL"

    metadata_completeness = citation_metadata_completeness(diagnostic_candidates, silver_rows)
    retrieval_metrics = pdf_retrieval_evidence_metrics(diagnostic_candidates)
    strict_metrics = strict_silver_evidence_metrics(silver_rows)
    lane_counts = lane_count(silver_rows)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "pdf_strict_retrieval_evidence_silver_generation_diagnostic",
        "track": TRACK,
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric": False,
        "answer_generation_run": False,
        "surface_status": {
            "query": "DIAGNOSTIC_ONLY",
            "candidate": "DIAGNOSTIC_ONLY",
            "debug_public": "DIAGNOSTIC_ONLY",
            "official_denominator": "NOT_OPENED",
            "answer": "NOT_OPENED",
            "citation": "NOT_OPENED",
        },
        "source_artifacts": {
            "pdf_gold_csv": file_identity(pdf_gold_csv),
            "pdf_review_pack_csv": file_identity(pdf_review_pack_csv),
            "policy_decisions": file_identity(policy_decisions),
            "route_label_review_applied": file_identity(route_label_review_applied),
            "fallback_outcome_label_review_applied": file_identity(fallback_outcome_label_review_applied),
            "three_track_report": file_identity(three_track_report),
            "official_denominator_registry": file_identity(official_denominator_registry),
        },
        "counts": {
            "registry_pdf_row_count": int_or_none(denominator.get("row_count")) or 0,
            "input_denominator_row_count": len(input_ids),
            "generated_silver_row_count": len(silver_rows),
            "strict_structured_row_count": len(silver_rows),
            "diagnostic_only_fallback_row_count": len(diagnostic_fallback_rows),
            "candidate_row_count": int_or_none(denominator.get("candidate_count")) or 0,
            "registry_diagnostic_only_row_count": int_or_none(denominator.get("diagnostic_only_count")) or 0,
            "policy_excluded_row_count": len(policy_excluded_ids),
            "stable_identity_required_row_count": len(stable_identity_required_ids),
            "pending_deferred_ocr_or_parsing_row_count": len(deferred_rows),
            "pdf_answer_generation_denominator": pdf_answer_generation_denominator(three_track_payload),
        },
        "input_denominator_query_ids": input_ids,
        "included_query_ids": [row["query_id"] for row in silver_rows],
        "excluded_query_ids": {
            "policy_excluded": policy_excluded_ids,
            "stable_identity_required": stable_identity_required_ids,
            "pending_deferred_ocr_or_parsing": [row["query_id"] for row in deferred_rows],
            "diagnostic_only_fallback": [row["query_id"] for row in diagnostic_fallback_rows],
        },
        "deferred_rows": deferred_rows,
        "diagnostic_only_fallback_rows": diagnostic_fallback_rows,
        "retrieval_failure_accounting": {
            "policy_excluded_retrieval_failure_count": 0,
            "stable_identity_required_retrieval_failure_count": 0,
            "diagnostic_only_fallback_retrieval_failure_count": 0,
            "policy_excluded_rows_counted_as_retrieval_failures": False,
        },
        "lane_separation": {
            "status": "PASS" if not guardrails["pdf_content_file_lanes_aggregated"] else "FAILED",
            "content_evidence_lane": PDF_CONTENT_EVIDENCE_LANE,
            "file_identity_lane": PDF_FILE_IDENTITY_LANE,
            "content_and_file_identity_aggregated": guardrails["pdf_content_file_lanes_aggregated"],
            "strict_silver_lanes": lane_counts,
            "content_to_file_transition_counted_as_success": False,
            "file_to_content_transition_counted_as_success": False,
        },
        "retrieval_evidence_metrics": retrieval_metrics,
        "strict_silver_evidence_metrics": strict_metrics,
        "citation_metadata_completeness": metadata_completeness,
        "silver_manifest_preview": silver_manifest_preview(silver_rows),
        "silver_artifact_policy": {
            "canonical_repo_silver_artifact_defined": False,
            "repo_silver_artifact_written": False,
            "repo_local_full_manifest_allowed": False,
            "full_manifest_location_guard": "assert_external_pdf_silver_output_path",
            "decision": (
                "No canonical PDF strict silver manifest path exists in the repository. "
                "The compact report is repo-local; the full manifest is external-only."
            ),
            "external_runtime_convention": "../_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/",
            "external_silver_artifact": file_identity(silver_output),
            "external_silver_artifact_written": False,
        },
        "guardrails": guardrails,
        "validation": {
            "ok": not validation_errors,
            "errors": validation_errors,
        },
        "notes": [
            "The active C7 PDF positive controls identify retrieval/evidence candidates only.",
            "Current active PDF artifacts do not expose source search unit rank, parser metadata, OCR confidence, or nearby paragraph context for strict promotion.",
            "All seven input denominator rows remain diagnostic-only until layout/source metadata is present.",
            "PDF CONTENT evidence and PDF FILE/document identity lanes remain separate.",
            "Answer and citation generation surfaces remain NOT_OPENED.",
        ],
    }
    return report, silver_rows


def silver_row_from_sources(
    *,
    query_id: str,
    gold_row: Mapping[str, Any],
    review_row: Mapping[str, Any],
    retrieval_hit: Mapping[str, Any],
    evidence_lane: str = PDF_CONTENT_EVIDENCE_LANE,
    stable_identity_required: bool = False,
) -> dict[str, Any]:
    bbox = parse_bbox(first_present(retrieval_hit, "bbox", "bounding_box") or gold_row.get("expected_bbox"))
    page = int_or_none(first_present(retrieval_hit, "page", "page_no") or gold_row.get("expected_page_no"))
    physical_page_index = int_or_none(
        first_present(retrieval_hit, "physical_page_index", "page_index")
        or gold_row.get("expected_physical_page_index")
    )
    nearby_paragraphs = parse_list(first_present(retrieval_hit, "nearby_paragraphs", "nearby_text"))
    parser_source_metadata = parser_metadata(retrieval_hit)
    source_searchunit_id = clean(
        first_present(retrieval_hit, "source_searchunit_id", "source_search_unit_id", "search_unit_id")
    )
    source_searchunit_rank = int_or_none(
        first_present(retrieval_hit, "source_searchunit_rank", "source_search_unit_rank", "rank")
    )
    ocr_confidence = float_or_none(first_present(retrieval_hit, "OCR_confidence", "ocr_confidence"))
    metadata = {
        "file": clean(first_present(retrieval_hit, "file", "source_file") or gold_row.get("expected_file_name")),
        "document_version_id": clean(
            first_present(retrieval_hit, "document_version_id", "docv")
            or gold_row.get("expected_document_version_id")
        ),
        "page": page,
        "physical_page_index": physical_page_index,
        "region_type": clean(first_present(retrieval_hit, "region_type") or gold_row.get("expected_chunk_type")),
        "bbox": bbox,
        "matched_text": clean(
            first_present(retrieval_hit, "matched_text", "text")
            or gold_row.get("expected_answer_text")
            or gold_row.get("must_contain_terms")
        ),
        "section_heading": clean(first_present(retrieval_hit, "section_heading") or review_row.get("section_heading")),
        "table_caption_footnote": clean(
            first_present(retrieval_hit, "table_caption_footnote", "table_caption")
            or review_row.get("table_caption_footnote")
            or review_row.get("expected_table_id")
            or gold_row.get("expected_table_id")
        ),
        "nearby_paragraphs": nearby_paragraphs,
        "OCR_confidence": ocr_confidence,
        "source_searchunit_id": source_searchunit_id,
        "source_searchunit_rank": source_searchunit_rank,
        "parser_source_metadata": parser_source_metadata,
        "citation_locator": {
            "file": clean(first_present(retrieval_hit, "file", "source_file") or gold_row.get("expected_file_name")),
            "document_version_id": clean(
                first_present(retrieval_hit, "document_version_id", "docv")
                or gold_row.get("expected_document_version_id")
            ),
            "page": page,
            "physical_page_index": physical_page_index,
            "bbox": bbox,
            "region_type": clean(first_present(retrieval_hit, "region_type") or gold_row.get("expected_chunk_type")),
            "search_unit_id": source_searchunit_id,
        },
        "score": float_or_none(first_present(retrieval_hit, "score", "retrieval_score")),
    }
    missing = [field for field in STRICT_REQUIRED_NONEMPTY_FIELDS if not nonempty(metadata.get(field))]
    flattened_only = parse_bool(retrieval_hit.get("flattened_only") or retrieval_hit.get("flattened_only_evidence"))
    filename_only_identity = parse_bool(retrieval_hit.get("filename_only_identity"))
    stable_identity_blocked = (
        evidence_lane == PDF_FILE_IDENTITY_LANE
        and stable_identity_required
        and (filename_only_identity or not nonempty(metadata.get("document_version_id")))
    )
    if stable_identity_blocked:
        diagnostic_reason = STABLE_IDENTITY_REQUIRED
    elif flattened_only:
        diagnostic_reason = FLATTENED_ONLY
    elif missing:
        diagnostic_reason = PDF_CONTEXT_DIAGNOSTIC_ONLY_MISSING_LAYOUT
    else:
        diagnostic_reason = ""
    diagnostic_only = bool(diagnostic_reason)
    return {
        "schema_version": SILVER_SCHEMA_VERSION,
        "query_id": query_id,
        "track": TRACK,
        "evidence_lane": evidence_lane,
        "retrieval_denominator_included": evidence_lane == PDF_CONTENT_EVIDENCE_LANE and not stable_identity_blocked,
        "answer_generation_denominator_included": False,
        "official_metric_input": False,
        "promotion_evidence": False,
        "diagnostic_only": diagnostic_only,
        "diagnostic_only_reason": diagnostic_reason,
        "missing_context_fields": missing,
        "citation_metadata": metadata,
        "citation_locator": metadata["citation_locator"],
        "contract_checks": {
            "flattened_only_evidence": flattened_only,
            "stable_identity_required": stable_identity_required,
            "filename_only_identity": filename_only_identity,
            "layout_page_bbox_required_for_content_evidence": evidence_lane == PDF_CONTENT_EVIDENCE_LANE,
            "source_searchunit_required": True,
            "answer_generation_denominator_opened": False,
        },
    }


def assert_external_pdf_silver_output_path(silver_output: Path) -> None:
    resolved = silver_output.resolve()
    repo_root = REPO_ROOT.resolve()
    if resolved == repo_root or resolved.is_relative_to(repo_root):
        raise ValueError(
            "PDF strict silver manifest must be written outside the repository; "
            "compact report files are the only repo-local strict silver outputs."
        )


def assert_canonical_strict_inputs(**paths: Path) -> None:
    expected_paths = {
        "pdf_gold_csv": DEFAULT_PDF_GOLD_CSV,
        "pdf_review_pack_csv": DEFAULT_PDF_REVIEW_PACK_CSV,
        "official_denominator_registry": DEFAULT_REGISTRY,
    }
    for name, actual in paths.items():
        expected = expected_paths[name]
        if actual.resolve() != expected.resolve():
            raise ValueError(
                f"canonical PDF strict input required for {name}: "
                f"expected {repo_relative(expected)!r}, got {repo_relative(actual)!r}"
            )


def validate_generation(
    *,
    denominator: Mapping[str, Any],
    input_ids: Sequence[str],
    silver_rows: Sequence[Mapping[str, Any]],
    diagnostic_candidates: Sequence[Mapping[str, Any]],
    policy_excluded_ids: Sequence[str],
    stable_identity_required_ids: Sequence[str],
    guardrails: Mapping[str, bool],
) -> list[str]:
    errors: list[str] = []
    expected_denominator = int_or_none(denominator.get("official_positive_denominator"))
    if expected_denominator is not None and len(input_ids) != expected_denominator:
        errors.append(
            "input denominator row count mismatch: "
            f"expected {expected_denominator}, got {len(input_ids)}"
        )
    if set(input_ids).intersection(policy_excluded_ids):
        errors.append("policy-excluded PDF rows appeared in the input denominator")
    if set(input_ids).intersection(stable_identity_required_ids):
        errors.append("stable-identity-required PDF rows appeared in the input denominator")
    for row in silver_rows:
        if row.get("diagnostic_only"):
            errors.append(f"diagnostic-only row promoted: {row.get('query_id')}")
        missing = [
            field
            for field in STRICT_REQUIRED_NONEMPTY_FIELDS
            if not nonempty(metadata_value(row, field))
        ]
        if missing:
            errors.append(f"strict PDF row missing required evidence metadata: {row.get('query_id')} {missing}")
        if row.get("evidence_lane") not in {PDF_CONTENT_EVIDENCE_LANE, PDF_FILE_IDENTITY_LANE}:
            errors.append(f"invalid PDF evidence lane: {row.get('query_id')} {row.get('evidence_lane')}")
    if any(row.get("diagnostic_only_reason") == FLATTENED_ONLY and not row.get("diagnostic_only") for row in diagnostic_candidates):
        errors.append("flattened-only PDF evidence was promoted")
    for key, value in guardrails.items():
        if value:
            errors.append(f"guardrail violation: {key}=true")
    return errors


def pdf_retrieval_evidence_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    row_count = len(rows)
    return {
        "metric_source": "generated_pdf_strict_pre_silver_gate_input_completeness",
        "retrieval_run_current_slice": False,
        "page_hit": None,
        "region_hit": None,
        "bbox_available": ratio(sum(1 for row in rows if nonempty(metadata_value(row, "bbox"))), row_count),
        "table_or_caption_included": ratio(
            sum(1 for row in rows if nonempty(metadata_value(row, "table_caption_footnote"))),
            row_count,
        ),
        "nearby_paragraph_included": ratio(
            sum(1 for row in rows if nonempty(metadata_value(row, "nearby_paragraphs"))),
            row_count,
        ),
        "OCR_confidence_available": ratio(
            sum(1 for row in rows if nonempty(metadata_value(row, "OCR_confidence"))),
            row_count,
        ),
        "citation_locator_completeness": ratio(sum(1 for row in rows if locator_complete_for_row(row)), row_count),
        "metadata_key_presence_completeness": metadata_key_presence_ratio(rows),
        "metadata_nonempty_value_completeness": metadata_nonempty_ratio(rows),
    }


def strict_silver_evidence_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    row_count = len(rows)
    return {
        "metric_source": "external_pdf_strict_silver_manifest_completeness",
        "page_hit": None,
        "region_hit": None,
        "bbox_available": ratio(sum(1 for row in rows if nonempty(metadata_value(row, "bbox"))), row_count),
        "table_or_caption_included": ratio(
            sum(1 for row in rows if nonempty(metadata_value(row, "table_caption_footnote"))),
            row_count,
        ),
        "nearby_paragraph_included": ratio(
            sum(1 for row in rows if nonempty(metadata_value(row, "nearby_paragraphs"))),
            row_count,
        ),
        "OCR_confidence_available": ratio(
            sum(1 for row in rows if nonempty(metadata_value(row, "OCR_confidence"))),
            row_count,
        ),
        "citation_locator_completeness": ratio(sum(1 for row in rows if locator_complete_for_row(row)), row_count),
        "metadata_key_presence_completeness": metadata_key_presence_ratio(rows),
        "metadata_nonempty_value_completeness": metadata_nonempty_ratio(rows),
    }


def citation_metadata_completeness(
    diagnostic_candidates: Sequence[Mapping[str, Any]],
    silver_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    field_presence = {field: 0 for field in REQUIRED_PDF_EVIDENCE_METADATA_FIELDS}
    field_nonempty = {field: 0 for field in REQUIRED_PDF_EVIDENCE_METADATA_FIELDS}
    for row in diagnostic_candidates:
        metadata = row.get("citation_metadata") if isinstance(row.get("citation_metadata"), Mapping) else {}
        for field in REQUIRED_PDF_EVIDENCE_METADATA_FIELDS:
            if field in metadata:
                field_presence[field] += 1
            if nonempty(metadata.get(field)):
                field_nonempty[field] += 1
    row_count = len(diagnostic_candidates)
    return {
        "required_fields": list(REQUIRED_PDF_EVIDENCE_METADATA_FIELDS),
        "input_candidate_row_count": row_count,
        "strict_silver_row_count": len(silver_rows),
        "diagnostic_only_fallback_row_count": row_count - len(silver_rows),
        "field_presence_counts": field_presence,
        "field_nonempty_counts": field_nonempty,
        "field_presence_ratio": {field: ratio(count, row_count) for field, count in field_presence.items()},
        "field_nonempty_ratio": {field: ratio(count, row_count) for field, count in field_nonempty.items()},
        "metadata_key_presence_completeness": metadata_key_presence_ratio(diagnostic_candidates),
        "metadata_nonempty_value_completeness": metadata_nonempty_ratio(diagnostic_candidates),
        "locator_complete_row_count": sum(1 for row in diagnostic_candidates if locator_complete_for_row(row)),
        "locator_completeness": ratio(sum(1 for row in diagnostic_candidates if locator_complete_for_row(row)), row_count),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    counts = report["counts"]
    metrics = report["retrieval_evidence_metrics"]
    guardrails = report["guardrails"]
    lines = [
        "# PDF Strict Silver Generation Report",
        "",
        f"Status: `{report['status']}`",
        "",
        "Scope: PDF retrieval/evidence diagnostic silver only. Answer generation, route/fallback official metrics, and production promotion remain closed.",
        "",
        "## Counts",
        "",
        "| Item | Count |",
        "|---|---:|",
        f"| Input denominator rows | `{counts['input_denominator_row_count']}` |",
        f"| Generated strict silver rows | `{counts['generated_silver_row_count']}` |",
        f"| Policy-excluded rows | `{counts['policy_excluded_row_count']}` |",
        f"| Stable-identity-required rows excluded | `{counts['stable_identity_required_row_count']}` |",
        f"| Pending/deferred OCR or parsing rows | `{counts['pending_deferred_ocr_or_parsing_row_count']}` |",
        f"| Diagnostic-only fallback rows | `{counts['diagnostic_only_fallback_row_count']}` |",
        f"| PDF answer-generation denominator | `{counts['pdf_answer_generation_denominator']}` |",
        "",
        "## Retrieval/Evidence Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| page_hit | `{metrics['page_hit']}` |",
        f"| region_hit | `{metrics['region_hit']}` |",
        f"| bbox_available | `{metrics['bbox_available']}` |",
        f"| table_or_caption_included | `{metrics['table_or_caption_included']}` |",
        f"| nearby_paragraph_included | `{metrics['nearby_paragraph_included']}` |",
        f"| OCR_confidence_available | `{metrics['OCR_confidence_available']}` |",
        f"| citation_locator_completeness | `{metrics['citation_locator_completeness']}` |",
        f"| metadata_key_presence_completeness | `{metrics['metadata_key_presence_completeness']}` |",
        f"| metadata_nonempty_value_completeness | `{metrics['metadata_nonempty_value_completeness']}` |",
        "",
        "## Lane Separation",
        "",
        f"- Status: `{report['lane_separation']['status']}`",
        f"- Content evidence lane: `{report['lane_separation']['content_evidence_lane']}`",
        f"- File identity lane: `{report['lane_separation']['file_identity_lane']}`",
        f"- Aggregated: `{str(report['lane_separation']['content_and_file_identity_aggregated']).lower()}`",
        "",
        "## Artifact Decision",
        "",
        f"- Repo full manifest written: `{str(report['silver_artifact_policy']['repo_silver_artifact_written']).lower()}`",
        f"- External manifest: `{report['silver_artifact_policy']['external_silver_artifact']['path']}`",
        "- Decision: no canonical PDF strict silver manifest path exists in the repo, so the full manifest is external-only and this report stays compact.",
        "",
        "## Guardrails",
        "",
        "| Guardrail | Value |",
        "|---|---:|",
    ]
    for key in [
        "official_denominator_registry_changed",
        "official_denominator_opened_or_frozen",
        "promotion_evidence_created",
        "pdf_answer_generation_denominator_opened",
        "production_namespace_mutated",
        "production_vector_index_mutated",
        "production_vector_written",
        "repo_local_pdf_silver_manifest_written",
        "candidate_artifact_mutated",
        "immutable_baseline_mutated",
        "diagnostic_only_row_promoted",
        "policy_excluded_rows_counted_as_retrieval_failures",
        "route_fallback_labels_promoted_to_official_metrics",
        "pdf_content_file_lanes_aggregated",
    ]:
        lines.append(f"| {key} | `{str(guardrails[key]).lower()}` |")
    lines.extend(
        [
            "",
            "## Validation",
            "",
            f"- OK: `{str(report['validation']['ok']).lower()}`",
            f"- Errors: `{len(report['validation']['errors'])}`",
            "",
            "Answer/citation generation surfaces remain `NOT_OPENED`.",
            "",
        ]
    )
    return "\n".join(lines)


def pdf_registry_denominator(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    denominators = payload.get("official_diagnostic_denominators")
    if not isinstance(denominators, Mapping):
        return {}
    denominator = denominators.get("track_c_pdf_c7_conservative")
    return denominator if isinstance(denominator, Mapping) else {}


def pdf_answer_generation_denominator(payload: Mapping[str, Any]) -> int:
    tracks = payload.get("tracks") if isinstance(payload.get("tracks"), Mapping) else {}
    pdf_track = tracks.get(TRACK) if isinstance(tracks.get(TRACK), Mapping) else {}
    for key in (
        "answer_generation_denominator",
        "pdf_answer_generation_denominator",
        "official_pdf_answer_generation_denominator",
    ):
        value = int_or_none(pdf_track.get(key))
        if value is not None:
            return value
    return 0


def deferred_ocr_or_source_context_rows(*payloads: Mapping[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for payload in payloads:
        applied_rows = payload.get("applied_human_review_rows")
        if not isinstance(applied_rows, list):
            continue
        for row in applied_rows:
            if not isinstance(row, Mapping):
                continue
            candidate_routes = row.get("reviewed_candidate_routes")
            candidate_routes = candidate_routes if isinstance(candidate_routes, list) else []
            route_scope = {clean(item) for item in candidate_routes}
            route_scope.add(clean(row.get("reviewed_primary_route")))
            text = " ".join(
                clean(row.get(key))
                for key in ("final_action", "fallback_outcome_label", "wrong_route_label", "notes")
            ).lower()
            if TRACK not in route_scope:
                continue
            if any(token in text for token in ("ocr", "parse", "parsing", "source_context", "source-context")):
                rows.append(
                    {
                        "query_id": clean(row.get("query_id")),
                        "reason": clean(row.get("fallback_outcome_label") or row.get("final_action")),
                        "evidence_lane": clean(row.get("expected_evidence_lane")),
                    }
                )
    return rows


def lane_count(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        PDF_CONTENT_EVIDENCE_LANE: sum(1 for row in rows if row.get("evidence_lane") == PDF_CONTENT_EVIDENCE_LANE),
        PDF_FILE_IDENTITY_LANE: sum(1 for row in rows if row.get("evidence_lane") == PDF_FILE_IDENTITY_LANE),
    }


def silver_manifest_preview(rows: Sequence[Mapping[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    return [
        {
            "query_id": row.get("query_id"),
            "evidence_lane": row.get("evidence_lane"),
            "file": metadata_value(row, "file"),
            "page": metadata_value(row, "page"),
            "source_searchunit_id": metadata_value(row, "source_searchunit_id"),
        }
        for row in rows[:limit]
    ]


def locator_complete_for_row(row: Mapping[str, Any]) -> bool:
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    return all(
        nonempty(locator.get(field))
        for field in ("file", "document_version_id", "page", "bbox", "region_type", "search_unit_id")
    )


def metadata_key_presence_ratio(rows: Sequence[Mapping[str, Any]]) -> float | None:
    if not rows:
        return None
    total = len(rows) * len(REQUIRED_PDF_EVIDENCE_METADATA_FIELDS)
    count = 0
    for row in rows:
        metadata = row.get("citation_metadata") if isinstance(row.get("citation_metadata"), Mapping) else {}
        count += sum(1 for field in REQUIRED_PDF_EVIDENCE_METADATA_FIELDS if field in metadata)
    return ratio(count, total)


def metadata_nonempty_ratio(rows: Sequence[Mapping[str, Any]]) -> float | None:
    if not rows:
        return None
    total = len(rows) * len(REQUIRED_PDF_EVIDENCE_METADATA_FIELDS)
    count = 0
    for row in rows:
        metadata = row.get("citation_metadata") if isinstance(row.get("citation_metadata"), Mapping) else {}
        count += sum(1 for field in REQUIRED_PDF_EVIDENCE_METADATA_FIELDS if nonempty(metadata.get(field)))
    return ratio(count, total)


def metadata_value(row: Mapping[str, Any], field: str) -> Any:
    metadata = row.get("citation_metadata") if isinstance(row.get("citation_metadata"), Mapping) else {}
    return metadata.get(field)


def parser_metadata(retrieval_hit: Mapping[str, Any]) -> dict[str, Any]:
    raw = retrieval_hit.get("parser_source_metadata")
    if isinstance(raw, Mapping):
        return dict(raw)
    metadata: dict[str, Any] = {}
    for key in ("parser", "source", "source_parser", "index_version", "namespace"):
        value = clean(retrieval_hit.get(key))
        if value:
            metadata[key] = value
    return metadata


def first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if nonempty(value):
            return value
    return None


def parse_bbox(value: Any) -> list[float]:
    if isinstance(value, list):
        parsed = [float_or_none(item) for item in value]
        return [item for item in parsed if item is not None]
    text = clean(value)
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    parsed = [float_or_none(item) for item in payload]
    return [item for item in parsed if item is not None]


def parse_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return [item for item in value if nonempty(item)]
    text = clean(value)
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [part.strip() for part in text.split("\n") if part.strip()]
    if isinstance(payload, list):
        return [item for item in payload if nonempty(item)]
    return []


def list_from_mapping(mapping: Any, key: str) -> list[Any]:
    if not isinstance(mapping, Mapping):
        return []
    value = mapping.get(key)
    return value if isinstance(value, list) else []


def nested_guardrail_flag(*payloads: Any, keys: Iterable[str]) -> bool:
    key_set = set(keys)
    return any(nested_guardrail_value(payload, key_set) for payload in payloads)


def nested_guardrail_value(value: Any, keys: set[str]) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in keys and guardrail_value_is_true(item):
                return True
            if isinstance(item, (Mapping, list, tuple)) and nested_guardrail_value(item, keys):
                return True
    elif isinstance(value, (list, tuple)):
        return any(nested_guardrail_value(item, keys) for item in value)
    return False


def guardrail_value_is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def file_identity(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path) if path.resolve().is_relative_to(REPO_ROOT.resolve()) else str(path.resolve()),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ratio(count: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(count / total, 3)


def int_or_none(value: Any) -> int | None:
    try:
        return int(clean(value))
    except (TypeError, ValueError):
        return None


def float_or_none(value: Any) -> float | None:
    try:
        return float(clean(value))
    except (TypeError, ValueError):
        return None


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return clean(value).lower() in {"1", "true", "yes", "y", "on"}


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    if isinstance(value, (int, float)):
        return True
    return bool(value)


if __name__ == "__main__":
    raise SystemExit(main())
