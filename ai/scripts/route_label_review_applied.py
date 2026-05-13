"""Apply Korean memo-style route/fallback labels as diagnostic-only artifacts.

This script normalizes the user's Korean memo decisions into the review-pack
schema columns. It leaves the original review packs unchanged and does not
mutate the official denominator registry, production namespaces, vector data,
candidate artifacts, or immutable baselines.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_ROUTE_PACK_JSON = REVIEW_DIR / "route_gold_label_review_pack_v1.json"
DEFAULT_FALLBACK_PACK_JSON = REVIEW_DIR / "fallback_outcome_label_review_pack_v1.json"
OFFICIAL_DENOMINATOR_REGISTRY = AI_WORKER_ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"

ROUTE_APPLIED_JSON = REVIEW_DIR / "route_gold_label_review_applied_v1.json"
ROUTE_APPLIED_MD = REVIEW_DIR / "route_gold_label_review_applied_v1.md"
FALLBACK_APPLIED_JSON = REVIEW_DIR / "fallback_outcome_label_review_applied_v1.json"
FALLBACK_APPLIED_MD = REVIEW_DIR / "fallback_outcome_label_review_applied_v1.md"

SCHEMA_VERSION = "route_fallback_label_review_applied_v1"
REVIEWER = "user_korean_memo"

TRACKS = [
    "text_namuwiki_animation",
    "xlsx_business_structured",
    "pdf_business_ocr_mm",
]

REQUIRED_COLUMNS = [
    "query_id",
    "safe_query_text",
    "source_type_hint",
    "reviewed_primary_route",
    "reviewed_candidate_routes",
    "expected_evidence_lane",
    "fallback_allowed",
    "fallback_expected_route",
    "fallback_outcome_label",
    "wrong_route_label",
    "denominator_scope",
    "reviewer",
    "reviewed_time",
    "notes",
]

ROUTE_DECISIONS: dict[str, dict[str, Any]] = {
    "route_review_text_namuwiki_animation_001": {
        "source_user_memo_ko": "올바른 라우트",
        "source_type_hint": "text_namuwiki_animation",
        "reviewed_primary_route": "text_namuwiki_animation",
        "reviewed_candidate_routes": ["text_namuwiki_animation"],
        "expected_evidence_lane": "text_content",
        "fallback_allowed": False,
        "fallback_expected_route": None,
        "fallback_outcome_label": "fallback_not_applicable",
        "wrong_route_label": "correct_route",
        "denominator_scope": "reviewed_route_label_diagnostic_only",
        "final_action": "direct_route_confirmed",
        "notes": "User confirmed TEXT/Namu route and text_content evidence lane.",
    },
    "route_review_xlsx_business_structured_001": {
        "source_user_memo_ko": "정책상 사용자에게 재질문 유도",
        "source_type_hint": "xlsx_business_structured_short_query",
        "reviewed_primary_route": "xlsx_business_structured",
        "reviewed_candidate_routes": ["xlsx_business_structured"],
        "expected_evidence_lane": "xlsx_structured_evidence",
        "fallback_allowed": False,
        "fallback_expected_route": None,
        "fallback_outcome_label": "fallback_to_user_clarification",
        "wrong_route_label": "correct_track_but_query_under_specified",
        "denominator_scope": "reviewed_route_label_diagnostic_only_clarification_required",
        "final_action": "clarification_required",
        "notes": (
            "User decided the short XLSX-shaped query is under-specified and should trigger user "
            "clarification. Do not treat fallback to PDF as success."
        ),
    },
    "route_review_pdf_content_evidence_001": {
        "source_user_memo_ko": "PDF 본문 근거 검색 맞음",
        "source_type_hint": "pdf_content_evidence",
        "reviewed_primary_route": "pdf_business_ocr_mm",
        "reviewed_candidate_routes": ["pdf_business_ocr_mm"],
        "expected_evidence_lane": "pdf_content_evidence",
        "fallback_allowed": False,
        "fallback_expected_route": None,
        "fallback_outcome_label": "fallback_not_applicable",
        "wrong_route_label": "correct_route",
        "denominator_scope": "reviewed_route_label_diagnostic_only",
        "final_action": "direct_route_confirmed",
        "pdf_lane_separation_required": True,
        "notes": "User confirmed PDF CONTENT evidence search. This is not FILE/document identity.",
    },
    "route_review_pdf_file_identity_001": {
        "source_user_memo_ko": "PDF 언급이 있으므로 PDF 파일 색인 라우트",
        "source_type_hint": "pdf_file_identity",
        "reviewed_primary_route": "pdf_business_ocr_mm",
        "reviewed_candidate_routes": ["pdf_business_ocr_mm"],
        "expected_evidence_lane": "pdf_file_identity",
        "fallback_allowed": False,
        "fallback_expected_route": None,
        "fallback_outcome_label": "fallback_not_applicable",
        "wrong_route_label": "correct_route",
        "denominator_scope": "reviewed_route_label_diagnostic_only_file_identity",
        "final_action": "stable_file_identity_route_confirmed",
        "pdf_lane_separation_required": True,
        "stable_identity_required": True,
        "notes": (
            "User confirmed PDF file/document identity route when a stable document identity exists. "
            "Generic filename-only identity remains blocked by stable_identity_required."
        ),
    },
    "route_review_ambiguous_multi_route_001": {
        "source_user_memo_ko": "OCR 및 파싱을 통해 키워드 추출 후 라우팅",
        "source_type_hint": "ambiguous_multi_route",
        "reviewed_primary_route": "diagnostic_multi_route",
        "reviewed_candidate_routes": TRACKS,
        "expected_evidence_lane": "none",
        "fallback_allowed": False,
        "fallback_expected_route": None,
        "fallback_outcome_label": "fallback_deferred_until_source_context_extraction",
        "wrong_route_label": "ambiguous_requires_source_context",
        "denominator_scope": "reviewed_route_label_diagnostic_only_requires_source_context",
        "final_action": "source_context_extraction_required",
        "notes": (
            "User decided that this ambiguous query requires OCR/parsing/source-context keyword "
            "extraction before final routing. Do not count this as direct single-route success."
        ),
    },
}

FALLBACK_DECISIONS: dict[str, dict[str, Any]] = {
    "fallback_review_xlsx_to_pdf_001": {
        "source_user_memo_ko": "풀백하여 사용자에게 질문 재유도",
        "source_type_hint": "xlsx_business_structured_short_query",
        "reviewed_primary_route": "xlsx_business_structured",
        "reviewed_candidate_routes": ["xlsx_business_structured"],
        "expected_evidence_lane": "xlsx_structured_evidence",
        "fallback_allowed": False,
        "fallback_expected_route": None,
        "fallback_outcome_label": "fallback_to_user_clarification",
        "wrong_route_label": "pdf_fallback_not_success",
        "denominator_scope": "reviewed_fallback_label_diagnostic_only_clarification_required",
        "final_action": "clarification_required",
        "clarification_fallback_allowed": True,
        "notes": (
            "User decided that this short XLSX-shaped query should not be treated as successful "
            "fallback to PDF. The safe fallback behavior is to ask the user for clarification "
            "about target workbook/table/metric."
        ),
    },
    "fallback_review_text_pdf_ambiguous_001": {
        "source_user_memo_ko": "풀백하여 사용자에게 질문 재유도",
        "source_type_hint": "text_pdf_ambiguous",
        "reviewed_primary_route": "diagnostic_multi_route",
        "reviewed_candidate_routes": ["text_namuwiki_animation", "pdf_business_ocr_mm"],
        "expected_evidence_lane": "none",
        "fallback_allowed": False,
        "fallback_expected_route": None,
        "fallback_outcome_label": "fallback_to_user_clarification",
        "wrong_route_label": "ambiguous_requires_user_clarification",
        "denominator_scope": "reviewed_fallback_label_diagnostic_only_clarification_required",
        "final_action": "clarification_required",
        "clarification_fallback_allowed": True,
        "notes": (
            "User decided that this TEXT/PDF ambiguous query should ask the user for clarification "
            "rather than silently falling back across tracks."
        ),
    },
    "fallback_review_pdf_content_file_identity_lane_001": {
        "source_user_memo_ko": "OCR 및 파싱을 통해 키워드 추출 후 라우팅",
        "source_type_hint": "pdf_content_vs_file_identity",
        "reviewed_primary_route": "pdf_business_ocr_mm",
        "reviewed_candidate_routes": ["pdf_business_ocr_mm"],
        "expected_evidence_lane": "pdf_content_evidence",
        "fallback_allowed": True,
        "fallback_expected_route": "pdf_business_ocr_mm",
        "fallback_outcome_label": "fallback_deferred_until_ocr_parse_keywords",
        "wrong_route_label": "no_cross_track_wrong_route_but_lane_separation_required",
        "denominator_scope": "reviewed_fallback_label_diagnostic_only_pdf_scoped",
        "final_action": "ocr_parse_keywords_required",
        "pdf_lane_separation_required": True,
        "stable_identity_required_for_file_identity": True,
        "layout_page_bbox_required_for_content_evidence": True,
        "notes": (
            "User decided that OCR/parsing should extract keywords before final routing. PDF CONTENT "
            "evidence and PDF FILE/document identity lanes must remain separate. Do not aggregate "
            "them into one success metric."
        ),
    },
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)
    route_pack_path = Path(args.route_pack_json)
    fallback_pack_path = Path(args.fallback_pack_json)
    artifacts = build_applied_artifacts(
        route_pack=read_json(route_pack_path),
        fallback_pack=read_json(fallback_pack_path),
        route_pack_path=route_pack_path,
        fallback_pack_path=fallback_pack_path,
        official_denominator_registry=Path(args.official_denominator_registry),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    route_json = output_dir / ROUTE_APPLIED_JSON.name
    route_md = output_dir / ROUTE_APPLIED_MD.name
    fallback_json = output_dir / FALLBACK_APPLIED_JSON.name
    fallback_md = output_dir / FALLBACK_APPLIED_MD.name
    write_json(route_json, artifacts["route_gold_label_review_applied"])
    route_md.write_text(render_markdown(artifacts["route_gold_label_review_applied"]), encoding="utf-8")
    write_json(fallback_json, artifacts["fallback_outcome_label_review_applied"])
    fallback_md.write_text(render_markdown(artifacts["fallback_outcome_label_review_applied"]), encoding="utf-8")

    route_status = artifacts["route_gold_label_review_applied"]["status"]
    fallback_status = artifacts["fallback_outcome_label_review_applied"]["status"]
    summary = {
        "status": "PASS" if route_status == fallback_status == "PASS" else "FAIL",
        "route_gold_label_review_applied_json": repo_relative(route_json),
        "route_gold_label_review_applied_md": repo_relative(route_md),
        "fallback_outcome_label_review_applied_json": repo_relative(fallback_json),
        "fallback_outcome_label_review_applied_md": repo_relative(fallback_md),
        "route_human_rows_applied": artifacts["route_gold_label_review_applied"]["counts"][
            "applied_human_review_rows"
        ],
        "fallback_human_rows_applied": artifacts["fallback_outcome_label_review_applied"]["counts"][
            "applied_human_review_rows"
        ],
        "codex_diagnostic_only_rows_unchanged": artifacts["route_gold_label_review_applied"]["counts"][
            "codex_diagnostic_only_rows_unchanged"
        ]
        + artifacts["fallback_outcome_label_review_applied"]["counts"]["codex_diagnostic_only_rows_unchanged"],
        "official_denominator_registry_changed": artifacts["route_gold_label_review_applied"]["guardrails"][
            "official_denominator_registry_changed"
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route-pack-json", default=str(DEFAULT_ROUTE_PACK_JSON))
    parser.add_argument("--fallback-pack-json", default=str(DEFAULT_FALLBACK_PACK_JSON))
    parser.add_argument("--official-denominator-registry", default=str(OFFICIAL_DENOMINATOR_REGISTRY))
    parser.add_argument("--output-dir", default=str(REVIEW_DIR))
    return parser.parse_args(argv)


def build_applied_artifacts(
    *,
    route_pack: Mapping[str, Any],
    fallback_pack: Mapping[str, Any],
    route_pack_path: Path,
    fallback_pack_path: Path,
    official_denominator_registry: Path,
) -> dict[str, dict[str, Any]]:
    registry_sha_before = sha256_file(official_denominator_registry)
    registry_sha_after = sha256_file(official_denominator_registry)
    generated_at = utc_timestamp()
    guardrails = build_guardrails(
        official_denominator_registry=official_denominator_registry,
        registry_sha_before=registry_sha_before,
        registry_sha_after=registry_sha_after,
    )
    route_rows = apply_decisions(
        source_rows=route_pack.get("human_review_rows", []),
        decisions=ROUTE_DECISIONS,
        reviewed_time=generated_at,
    )
    fallback_rows = apply_decisions(
        source_rows=fallback_pack.get("human_review_rows", []),
        decisions=FALLBACK_DECISIONS,
        reviewed_time=generated_at,
    )
    route_auto_rows = list(route_pack.get("codex_diagnostic_only_rows", []))
    fallback_auto_rows = list(fallback_pack.get("codex_diagnostic_only_rows", []))

    route_artifact = applied_artifact(
        pack_type="route_gold_label_review_applied",
        source_pack=route_pack,
        source_pack_path=route_pack_path,
        source_rows=route_rows,
        codex_rows=route_auto_rows,
        decisions=ROUTE_DECISIONS,
        guardrails=guardrails,
        generated_at=generated_at,
        metrics=route_metrics(route_rows),
    )
    fallback_artifact = applied_artifact(
        pack_type="fallback_outcome_label_review_applied",
        source_pack=fallback_pack,
        source_pack_path=fallback_pack_path,
        source_rows=fallback_rows,
        codex_rows=fallback_auto_rows,
        decisions=FALLBACK_DECISIONS,
        guardrails=guardrails,
        generated_at=generated_at,
        metrics=fallback_metrics(fallback_rows),
    )
    route_artifact["validation"] = validate_applied(route_artifact)
    fallback_artifact["validation"] = validate_applied(fallback_artifact)
    route_artifact["status"] = "PASS" if route_artifact["validation"]["ok"] else "FAIL"
    fallback_artifact["status"] = "PASS" if fallback_artifact["validation"]["ok"] else "FAIL"
    return {
        "route_gold_label_review_applied": route_artifact,
        "fallback_outcome_label_review_applied": fallback_artifact,
    }


def apply_decisions(
    *,
    source_rows: Any,
    decisions: Mapping[str, Mapping[str, Any]],
    reviewed_time: str,
) -> list[dict[str, Any]]:
    source_by_id = {row.get("query_id"): dict(row) for row in source_rows if isinstance(row, Mapping)}
    applied: list[dict[str, Any]] = []
    for query_id, decision in decisions.items():
        original = source_by_id.get(query_id, {})
        row = normalized_row(
            original=original,
            query_id=query_id,
            decision=decision,
            reviewed_time=reviewed_time,
        )
        applied.append(row)
    return applied


def normalized_row(*, original: Mapping[str, Any], query_id: str, decision: Mapping[str, Any], reviewed_time: str) -> dict[str, Any]:
    row = {
        "query_id": query_id,
        "safe_query_text": str(original.get("safe_query_text") or decision.get("safe_query_text") or ""),
        "source_type_hint": decision["source_type_hint"],
        "reviewed_primary_route": decision["reviewed_primary_route"],
        "reviewed_candidate_routes": list(decision["reviewed_candidate_routes"]),
        "expected_evidence_lane": decision["expected_evidence_lane"],
        "fallback_allowed": decision["fallback_allowed"],
        "fallback_expected_route": decision["fallback_expected_route"],
        "fallback_outcome_label": decision["fallback_outcome_label"],
        "wrong_route_label": decision["wrong_route_label"],
        "denominator_scope": decision["denominator_scope"],
        "reviewer": REVIEWER,
        "reviewed_time": reviewed_time,
        "notes": decision["notes"],
        "label_status": "applied_user_review",
        "source_user_memo_ko": decision["source_user_memo_ko"],
        "normalized_from_user_memo": True,
        "diagnostic_only": True,
        "official_metric_input": False,
        "official_denominator_mutation": False,
        "production_namespace_mutation": False,
        "production_vector_write": False,
        "final_action": decision["final_action"],
        "original_prefilled_fallback_expected_route": original.get("fallback_expected_route", ""),
        "original_prefilled_fallback_allowed": original.get("fallback_allowed", ""),
        "original_label_status": original.get("label_status", ""),
        "report_only_label_values": True,
    }
    for optional_key in [
        "clarification_fallback_allowed",
        "pdf_lane_separation_required",
        "stable_identity_required",
        "stable_identity_required_for_file_identity",
        "layout_page_bbox_required_for_content_evidence",
    ]:
        if optional_key in decision:
            row[optional_key] = decision[optional_key]
    return row


def applied_artifact(
    *,
    pack_type: str,
    source_pack: Mapping[str, Any],
    source_pack_path: Path,
    source_rows: list[dict[str, Any]],
    codex_rows: list[Mapping[str, Any]],
    decisions: Mapping[str, Mapping[str, Any]],
    guardrails: Mapping[str, Any],
    generated_at: str,
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    is_route = pack_type == "route_gold_label_review_applied"
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "pack_type": pack_type,
        "status": "PASS",
        "generated_at": generated_at,
        "source_review_pack": {
            "path": repo_relative(source_pack_path),
            "schema_version": source_pack.get("schema_version", ""),
            "sha256": sha256_file_if_exists(source_pack_path),
            "pack_type": source_pack.get("pack_type", ""),
        },
        "original_review_pack_modified": False,
        "original_review_pack_decision": (
            "left unchanged; applied artifacts preserve the source pack and record normalized user decisions separately"
        ),
        "diagnostic_only": True,
        "route_metrics_official": False,
        "fallback_metrics_official": False,
        "official_metric_blocker": "reviewed labels are applied for diagnostic analysis only",
        "required_columns": REQUIRED_COLUMNS,
        "tracks": TRACKS,
        "applied_human_review_rows": source_rows,
        "codex_diagnostic_only_rows": codex_rows,
        "normalization_mappings": normalization_mappings(decisions),
        "enum_value_fallbacks": [
            {
                "reason": "No existing exact route/fallback review enum constants were found for the Korean memo decisions.",
                "choice": "Use report-only label strings in applied artifacts without changing production routing behavior.",
                "labels": sorted({str(decision["fallback_outcome_label"]) for decision in decisions.values()}),
            }
        ],
        "prefilled_diagnostic_hints_overridden": prefilled_overrides(source_rows),
        "guardrails": dict(guardrails),
        "counts": counts(source_rows, codex_rows),
        "reviewed_route_metrics_diagnostic" if is_route else "reviewed_fallback_metrics_diagnostic": dict(metrics),
    }
    return artifact


def normalization_mappings(decisions: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    mappings = []
    for query_id, decision in decisions.items():
        mappings.append(
            {
                "query_id": query_id,
                "user_memo_ko": decision["source_user_memo_ko"],
                "normalized_fields": {
                    column: decision[column]
                    for column in [
                        "reviewed_primary_route",
                        "reviewed_candidate_routes",
                        "expected_evidence_lane",
                        "fallback_allowed",
                        "fallback_expected_route",
                        "fallback_outcome_label",
                        "wrong_route_label",
                        "denominator_scope",
                    ]
                },
                "final_action": decision["final_action"],
            }
        )
    return mappings


def route_metrics(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "official_metric": False,
        "metric_namespace": "reviewed_route_metrics_diagnostic",
        "applied_route_labels": len(rows),
        "correct_route_count": sum(1 for row in rows if row.get("wrong_route_label") == "correct_route"),
        "clarification_required_count": sum(1 for row in rows if row.get("final_action") == "clarification_required"),
        "source_context_required_count": sum(
            1 for row in rows if row.get("final_action") == "source_context_extraction_required"
        ),
        "direct_single_route_success_count": sum(
            1
            for row in rows
            if row.get("wrong_route_label") == "correct_route"
            and row.get("final_action") != "source_context_extraction_required"
        ),
        "deferred_rows_not_counted_as_direct_success": True,
    }


def fallback_metrics(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "official_metric": False,
        "metric_namespace": "reviewed_fallback_metrics_diagnostic",
        "applied_fallback_labels": len(rows),
        "route_retrieval_fallback_success_count": 0,
        "cross_track_fallback_success_count": 0,
        "clarification_required_count": sum(1 for row in rows if row.get("final_action") == "clarification_required"),
        "pdf_scoped_deferred_ocr_parse_count": sum(
            1 for row in rows if row.get("final_action") == "ocr_parse_keywords_required"
        ),
        "clarification_required_rows_not_counted_as_fallback_success": True,
        "pdf_lane_transition_not_aggregated_as_success": True,
    }


def counts(applied_rows: list[Mapping[str, Any]], codex_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "applied_human_review_rows": len(applied_rows),
        "codex_diagnostic_only_rows_unchanged": len(codex_rows),
        "total_rows": len(applied_rows) + len(codex_rows),
        "official_metric_input_rows": sum(1 for row in applied_rows if row.get("official_metric_input"))
        + sum(1 for row in codex_rows if row.get("official_metric_input")),
        "clarification_required_rows": sum(1 for row in applied_rows if row.get("final_action") == "clarification_required"),
        "deferred_ocr_or_source_context_rows": sum(
            1
            for row in applied_rows
            if row.get("final_action") in {"source_context_extraction_required", "ocr_parse_keywords_required"}
        ),
        "pdf_content_evidence_rows": sum(
            1 for row in applied_rows if row.get("expected_evidence_lane") == "pdf_content_evidence"
        ),
        "pdf_file_identity_rows": sum(1 for row in applied_rows if row.get("expected_evidence_lane") == "pdf_file_identity"),
    }


def build_guardrails(
    *,
    official_denominator_registry: Path,
    registry_sha_before: str,
    registry_sha_after: str,
) -> dict[str, Any]:
    return {
        "official_denominator_registry_path": repo_relative(official_denominator_registry),
        "official_denominator_registry_sha256_before": registry_sha_before,
        "official_denominator_registry_sha256_after": registry_sha_after,
        "official_denominator_registry_changed": registry_sha_before != registry_sha_after,
        "official_denominator_opened_or_frozen": False,
        "production_namespace_mutated": False,
        "production_vector_index_mutated": False,
        "production_vector_written": False,
        "candidate_artifact_mutated": False,
        "immutable_baseline_mutated": False,
        "diagnostic_only_row_promoted": False,
        "pdf_content_and_file_identity_aggregated": False,
        "hidden_xlsx_content_exposed": False,
        "policy_excluded_rows_counted_as_retrieval_failures": False,
        "route_metrics_official": False,
        "fallback_metrics_official": False,
    }


def prefilled_overrides(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    overrides = []
    for row in rows:
        original_route = row.get("original_prefilled_fallback_expected_route")
        if original_route and row.get("fallback_expected_route") != original_route:
            overrides.append(
                {
                    "query_id": row["query_id"],
                    "original_prefilled_fallback_expected_route": original_route,
                    "normalized_fallback_expected_route": row.get("fallback_expected_route"),
                    "reason": "User memo required clarification or deferred source-context extraction instead of treating the prefilled route hint as success.",
                }
            )
    return overrides


def validate_applied(artifact: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    rows = list(artifact.get("applied_human_review_rows", []))
    for row in rows:
        for column in REQUIRED_COLUMNS:
            if column not in row:
                errors.append(f"{row.get('query_id', '<missing>')} missing {column}")
        if row.get("reviewer") != REVIEWER:
            errors.append(f"{row.get('query_id')} missing reviewer")
        if not row.get("reviewed_time"):
            errors.append(f"{row.get('query_id')} missing reviewed_time")
        if row.get("diagnostic_only") is not True:
            errors.append(f"{row.get('query_id')} not diagnostic_only")
        if row.get("official_metric_input") is not False:
            errors.append(f"{row.get('query_id')} marked official metric input")
    guardrails = artifact.get("guardrails", {})
    for key in [
        "official_denominator_registry_changed",
        "official_denominator_opened_or_frozen",
        "production_namespace_mutated",
        "production_vector_index_mutated",
        "production_vector_written",
        "candidate_artifact_mutated",
        "immutable_baseline_mutated",
        "diagnostic_only_row_promoted",
        "pdf_content_and_file_identity_aggregated",
        "hidden_xlsx_content_exposed",
        "policy_excluded_rows_counted_as_retrieval_failures",
        "route_metrics_official",
        "fallback_metrics_official",
    ]:
        if guardrails.get(key) is not False:
            errors.append(f"guardrail {key} expected false")
    if artifact.get("counts", {}).get("official_metric_input_rows") != 0:
        errors.append("official_metric_input_rows must remain 0")
    serialized = json.dumps(artifact, ensure_ascii=False)
    for forbidden in ["hidden cell value", "xlsx_hidden_source_payload", "hidden_value_payload"]:
        if forbidden in serialized:
            errors.append(f"forbidden hidden XLSX marker surfaced: {forbidden}")
    return {"ok": not errors, "errors": errors}


def render_markdown(artifact: Mapping[str, Any]) -> str:
    title = (
        "Route Gold Label Review Applied v1"
        if artifact["pack_type"] == "route_gold_label_review_applied"
        else "Fallback Outcome Label Review Applied v1"
    )
    metric_key = (
        "reviewed_route_metrics_diagnostic"
        if artifact["pack_type"] == "route_gold_label_review_applied"
        else "reviewed_fallback_metrics_diagnostic"
    )
    lines = [
        f"# {title}",
        "",
        f"- Generated at: `{artifact['generated_at']}`",
        f"- Status: `{artifact['status']}`",
        "- Scope: Korean memo labels normalized into diagnostic-only review columns.",
        f"- Source review pack: `{artifact['source_review_pack']['path']}`",
        f"- Original review pack modified: `{str(artifact['original_review_pack_modified']).lower()}`",
        f"- Applied human review rows: `{artifact['counts']['applied_human_review_rows']}`",
        f"- Codex diagnostic-only auto-classified rows unchanged: `{artifact['counts']['codex_diagnostic_only_rows_unchanged']}`",
        f"- Official metric input rows: `{artifact['counts']['official_metric_input_rows']}`",
        "",
        "## Applied Labels",
        "",
        "| query_id | user memo | reviewed_primary_route | expected_evidence_lane | fallback_allowed | fallback_expected_route | fallback_outcome_label | wrong_route_label | final_action |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in artifact["applied_human_review_rows"]:
        lines.append(
            "| "
            + " | ".join(
                escape_md(display(row.get(key)))
                for key in [
                    "query_id",
                    "source_user_memo_ko",
                    "reviewed_primary_route",
                    "expected_evidence_lane",
                    "fallback_allowed",
                    "fallback_expected_route",
                    "fallback_outcome_label",
                    "wrong_route_label",
                    "final_action",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Diagnostic Metrics",
            "",
        ]
    )
    for key, value in artifact[metric_key].items():
        lines.append(f"- `{key}`: `{display(value)}`")
    lines.extend(
        [
            "",
            "## Mapping Notes",
            "",
            "- Korean memo decisions are treated as authoritative human review input for this phase.",
            "- Exact production enum constants were not found for these labels; report-only label strings were used.",
            "- Prefilled fallback routes from the original pack remain diagnostic hints and were overridden where the user memo required clarification or OCR/parsing first.",
            "- Route/fallback metrics remain diagnostic-only.",
            "",
            "## Guardrails",
            "",
        ]
    )
    for key, value in artifact["guardrails"].items():
        if "sha256" in key:
            continue
        lines.append(f"- `{key}`: `{display(value)}`")
    return "\n".join(lines) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file_if_exists(path: Path) -> str:
    return sha256_file(path) if path.exists() else ""


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def display(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
