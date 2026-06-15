"""Generate diagnostic-only route and fallback label review packs.

The generated packs prepare human review for routing metrics. They do not
create route gold labels, compute official route metrics, mutate the official
denominator registry, run retrieval, write vectors, or promote rows.
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
DEFAULT_REPORT_JSON = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "three_track_orchestration_report.json"
OFFICIAL_DENOMINATOR_REGISTRY = AI_WORKER_ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"

ROUTE_JSON_OUTPUT = REVIEW_DIR / "route_gold_label_review_pack_v1.json"
ROUTE_MD_OUTPUT = REVIEW_DIR / "route_gold_label_review_pack_v1.md"
FALLBACK_JSON_OUTPUT = REVIEW_DIR / "fallback_outcome_label_review_pack_v1.json"
FALLBACK_MD_OUTPUT = REVIEW_DIR / "fallback_outcome_label_review_pack_v1.md"

SCHEMA_VERSION = "route_fallback_label_review_pack_v1"

TRACKS = [
    "text_namuwiki_animation",
    "xlsx_business_structured",
    "pdf_business_ocr_mm",
]

DENOMINATOR_SCOPES = {
    "text_namuwiki_animation": "text_namuwiki_bound_diagnostic_denominator_47_answer_citation_denominator_not_open",
    "xlsx_business_structured": "xlsx_retrieval_evidence_diagnostic_denominator_23_answer_generation_denominator_0",
    "pdf_business_ocr_mm": "pdf_conservative_content_and_file_identity_denominators_separate_answer_denominator_0",
}

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

HUMAN_LABEL_FIELDS = [
    "reviewed_primary_route",
    "reviewed_candidate_routes",
    "expected_evidence_lane",
    "fallback_allowed",
    "fallback_expected_route",
    "fallback_outcome_label",
    "wrong_route_label",
    "reviewer",
    "reviewed_time",
    "notes",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)
    report_path = Path(args.report_json)
    registry_path = Path(args.official_denominator_registry)
    packs = build_review_packs(report_path=report_path, official_denominator_registry=registry_path)

    route_json = output_dir / ROUTE_JSON_OUTPUT.name
    route_md = output_dir / ROUTE_MD_OUTPUT.name
    fallback_json = output_dir / FALLBACK_JSON_OUTPUT.name
    fallback_md = output_dir / FALLBACK_MD_OUTPUT.name
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(route_json, packs["route_gold_label_review_pack"])
    route_md.write_text(render_markdown(packs["route_gold_label_review_pack"]), encoding="utf-8")
    write_json(fallback_json, packs["fallback_outcome_label_review_pack"])
    fallback_md.write_text(render_markdown(packs["fallback_outcome_label_review_pack"]), encoding="utf-8")

    summary = {
        "status": packs["route_gold_label_review_pack"]["status"]
        if packs["route_gold_label_review_pack"]["status"] == packs["fallback_outcome_label_review_pack"]["status"]
        else "FAIL",
        "route_gold_label_review_pack_json": repo_relative(route_json),
        "route_gold_label_review_pack_md": repo_relative(route_md),
        "fallback_outcome_label_review_pack_json": repo_relative(fallback_json),
        "fallback_outcome_label_review_pack_md": repo_relative(fallback_md),
        "human_review_rows": packs["route_gold_label_review_pack"]["counts"]["human_review_rows"]
        + packs["fallback_outcome_label_review_pack"]["counts"]["human_review_rows"],
        "codex_diagnostic_only_rows": packs["route_gold_label_review_pack"]["counts"]["codex_diagnostic_only_rows"]
        + packs["fallback_outcome_label_review_pack"]["counts"]["codex_diagnostic_only_rows"],
        "official_denominator_registry_changed": packs["route_gold_label_review_pack"]["guardrails"][
            "official_denominator_registry_changed"
        ],
        "production_vector_index_mutated": packs["route_gold_label_review_pack"]["guardrails"][
            "production_vector_index_mutated"
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", default=str(DEFAULT_REPORT_JSON))
    parser.add_argument("--official-denominator-registry", default=str(OFFICIAL_DENOMINATOR_REGISTRY))
    parser.add_argument("--output-dir", default=str(REVIEW_DIR))
    return parser.parse_args(argv)


def build_review_packs(*, report_path: Path, official_denominator_registry: Path) -> dict[str, dict[str, Any]]:
    registry_sha_before = sha256_file(official_denominator_registry)
    report = read_json(report_path)
    registry_sha_after = sha256_file(official_denominator_registry)
    registry_changed = registry_sha_before != registry_sha_after
    generated_at = utc_timestamp()
    sample_diagnostics = {
        row.get("query_id"): row
        for row in report.get("route_diagnostic_contract", {}).get("sample_diagnostics", [])
        if isinstance(row, Mapping)
    }
    guardrails = build_guardrails(
        report=report,
        official_denominator_registry=official_denominator_registry,
        registry_sha_before=registry_sha_before,
        registry_sha_after=registry_sha_after,
        registry_changed=registry_changed,
    )
    route_human_rows = route_human_review_rows()
    route_auto_rows = route_codex_diagnostic_rows(sample_diagnostics)
    fallback_human_rows = fallback_human_review_rows(sample_diagnostics)
    fallback_auto_rows = fallback_codex_diagnostic_rows(sample_diagnostics)

    route_pack = {
        "schema_version": SCHEMA_VERSION,
        "pack_type": "route_gold_label_review",
        "status": "PASS",
        "generated_at": generated_at,
        "source_report": {
            "path": repo_relative(report_path),
            "schema_version": report.get("schema_version", ""),
            "sha256": sha256_file(report_path),
        },
        "diagnostic_only": True,
        "route_metrics_official": False,
        "official_metric_blocker": "route gold labels and fallback outcome labels are absent",
        "required_columns": REQUIRED_COLUMNS,
        "human_label_fields": HUMAN_LABEL_FIELDS,
        "tracks": TRACKS,
        "denominator_scopes": DENOMINATOR_SCOPES,
        "human_review_rows": route_human_rows,
        "codex_diagnostic_only_rows": route_auto_rows,
        "counts": counts(route_human_rows, route_auto_rows),
        "guardrails": guardrails,
        "label_policy": label_policy(),
        "validation": {},
    }
    fallback_pack = {
        "schema_version": SCHEMA_VERSION,
        "pack_type": "fallback_outcome_label_review",
        "status": "PASS",
        "generated_at": generated_at,
        "source_report": route_pack["source_report"],
        "diagnostic_only": True,
        "fallback_metrics_official": False,
        "official_metric_blocker": "fallback outcome labels are absent",
        "required_columns": REQUIRED_COLUMNS,
        "human_label_fields": HUMAN_LABEL_FIELDS,
        "tracks": TRACKS,
        "denominator_scopes": DENOMINATOR_SCOPES,
        "bounded_fallback_policy": {
            "maximum_fallback_attempts": int(
                report.get("bounded_fallback_loop", {}).get("maximum_fallback_attempts", 1)
            ),
            "allow_unscoped": bool(report.get("bounded_fallback_loop", {}).get("allow_unscoped", False)),
            "production_mutation": bool(report.get("bounded_fallback_loop", {}).get("production_mutation", False)),
            "broad_retrieval_expansion": bool(
                report.get("bounded_fallback_loop", {}).get("broad_retrieval_expansion", False)
            ),
        },
        "human_review_rows": fallback_human_rows,
        "codex_diagnostic_only_rows": fallback_auto_rows,
        "counts": counts(fallback_human_rows, fallback_auto_rows),
        "guardrails": guardrails,
        "label_policy": label_policy(),
        "validation": {},
    }
    route_pack["validation"] = validate_pack(route_pack)
    fallback_pack["validation"] = validate_pack(fallback_pack)
    if route_pack["validation"]["errors"]:
        route_pack["status"] = "FAIL"
    if fallback_pack["validation"]["errors"]:
        fallback_pack["status"] = "FAIL"
    return {
        "route_gold_label_review_pack": route_pack,
        "fallback_outcome_label_review_pack": fallback_pack,
    }


def route_human_review_rows() -> list[dict[str, Any]]:
    return [
        review_row(
            query_id="route_review_text_namuwiki_animation_001",
            safe_query_text="애니 작품 내용과 등장인물 설명을 찾아줘",
            source_type_hint="text_namuwiki_animation",
            expected_evidence_lane="text_content",
            denominator_scope=DENOMINATOR_SCOPES["text_namuwiki_animation"],
            human_judgment_required=True,
            codex_classification="pending_user_route_label",
            notes="Human must confirm primary route and expected TEXT/Namu evidence lane before route metrics.",
            observed_primary_route="text_namuwiki_animation",
            observed_candidate_routes=["text_namuwiki_animation"],
        ),
        review_row(
            query_id="route_review_xlsx_business_structured_001",
            safe_query_text="합계?",
            source_type_hint="xlsx_business_structured_short_query",
            expected_evidence_lane="xlsx_structured_evidence",
            denominator_scope=DENOMINATOR_SCOPES["xlsx_business_structured"],
            human_judgment_required=True,
            codex_classification="pending_user_route_label",
            notes="Short XLSX-shaped query needs human route label before routing accuracy can be computed.",
            observed_primary_route="xlsx_business_structured",
            observed_candidate_routes=["xlsx_business_structured", "pdf_business_ocr_mm"],
        ),
        review_row(
            query_id="route_review_pdf_content_evidence_001",
            safe_query_text="PDF 본문 근거를 찾아줘",
            source_type_hint="pdf_content_evidence",
            expected_evidence_lane="pdf_content_evidence",
            denominator_scope=DENOMINATOR_SCOPES["pdf_business_ocr_mm"],
            human_judgment_required=True,
            codex_classification="pending_user_route_label",
            notes="Human must confirm this belongs to PDF CONTENT evidence, not FILE/document identity.",
            observed_primary_route="pdf_business_ocr_mm",
            observed_candidate_routes=["pdf_business_ocr_mm"],
        ),
        review_row(
            query_id="route_review_pdf_file_identity_001",
            safe_query_text="안정적인 문서 식별자가 있는 PDF 파일을 찾아줘",
            source_type_hint="pdf_file_identity",
            expected_evidence_lane="pdf_file_identity",
            denominator_scope=DENOMINATOR_SCOPES["pdf_business_ocr_mm"],
            human_judgment_required=True,
            codex_classification="pending_user_file_identity_route_label",
            notes="Human must confirm stable document identity policy; generic filename-only identity is not allowed.",
            observed_primary_route="pdf_business_ocr_mm",
            observed_candidate_routes=["pdf_business_ocr_mm"],
        ),
        review_row(
            query_id="route_review_ambiguous_multi_route_001",
            safe_query_text="이 자료에서 확인해줘",
            source_type_hint="ambiguous_multi_route",
            expected_evidence_lane="none",
            denominator_scope=DENOMINATOR_SCOPES["text_namuwiki_animation"],
            human_judgment_required=True,
            codex_classification="pending_user_multi_route_label",
            notes="Ambiguous query needs reviewed route and evidence-lane label before multi-route metrics.",
            observed_primary_route="diagnostic_multi_route",
            observed_candidate_routes=TRACKS,
        ),
    ]


def route_codex_diagnostic_rows(sample_diagnostics: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    generic_pdf = sample_diagnostics.get("generic-pdf-file-identity", {})
    return [
        review_row(
            query_id="route_auto_pdf_generic_filename_identity_blocked_001",
            safe_query_text=safe_text(generic_pdf.get("safe_query_text"), "계약서 PDF 파일 찾아줘"),
            source_type_hint="pdf_file_identity_guard",
            reviewed_primary_route="policy_blocked",
            reviewed_candidate_routes=["pdf_business_ocr_mm"],
            expected_evidence_lane="pdf_file_identity",
            fallback_allowed=False,
            fallback_expected_route="",
            fallback_outcome_label="fallback_blocked_by_policy",
            wrong_route_label="not_official_metric_input",
            denominator_scope=DENOMINATOR_SCOPES["pdf_business_ocr_mm"],
            human_judgment_required=False,
            codex_classification="generic_filename_only_identity_blocked",
            blocked_flags=["stable_identity_required"],
            notes="Codex diagnostic-only classification: generic PDF filename-only identity cannot become stable document identity.",
        ),
        review_row(
            query_id="route_auto_xlsx_hidden_excluded_guard_001",
            safe_query_text="[redacted xlsx excluded-row guard probe]",
            source_type_hint="xlsx_hidden_or_excluded_guard",
            reviewed_primary_route="policy_blocked",
            reviewed_candidate_routes=["xlsx_business_structured"],
            expected_evidence_lane="xlsx_structured_evidence",
            fallback_allowed=False,
            fallback_expected_route="",
            fallback_outcome_label="fallback_blocked_by_policy",
            wrong_route_label="not_official_metric_input",
            denominator_scope=DENOMINATOR_SCOPES["xlsx_business_structured"],
            human_judgment_required=False,
            codex_classification="xlsx_hidden_or_excluded_row_blocked",
            blocked_flags=["hidden_negative_or_excluded_row_guard"],
            notes="Codex diagnostic-only classification: XLSX hidden/excluded content is not surfaced.",
        ),
        review_row(
            query_id="route_auto_text_unresolved_carry_forward_guard_001",
            safe_query_text="TEXT/Namu unresolved carry-forward guard",
            source_type_hint="text_namuwiki_unresolved_guard",
            reviewed_primary_route="policy_blocked",
            reviewed_candidate_routes=["text_namuwiki_animation"],
            expected_evidence_lane="text_content",
            fallback_allowed=False,
            fallback_expected_route="",
            fallback_outcome_label="fallback_blocked_by_policy",
            wrong_route_label="not_official_metric_input",
            denominator_scope=DENOMINATOR_SCOPES["text_namuwiki_animation"],
            human_judgment_required=False,
            codex_classification="text_namu_unresolved_rows_excluded",
            blocked_flags=["text_namu_unresolved_carry_forward_excluded"],
            notes="Codex diagnostic-only classification: unresolved TEXT/Namu rows remain excluded from gold_v0.1.",
        ),
        review_row(
            query_id="route_auto_invalid_llm_json_fail_closed_001",
            safe_query_text="invalid LLM adjudicator output guard",
            source_type_hint="llm_adjudicator_validation_guard",
            reviewed_primary_route="insufficient_metadata",
            reviewed_candidate_routes=[],
            expected_evidence_lane="none",
            fallback_allowed=False,
            fallback_expected_route="",
            fallback_outcome_label="fallback_blocked_invalid_adjudicator",
            wrong_route_label="not_official_metric_input",
            denominator_scope=DENOMINATOR_SCOPES["text_namuwiki_animation"],
            human_judgment_required=False,
            codex_classification="invalid_llm_json_fails_closed",
            blocked_flags=["invalid_llm_json"],
            notes="Codex diagnostic-only classification: invalid adjudicator JSON fails closed and is not official success.",
        ),
    ]


def fallback_human_review_rows(sample_diagnostics: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    xlsx_sample = sample_diagnostics.get("req-graph-1", {})
    return [
        review_row(
            query_id="fallback_review_xlsx_to_pdf_001",
            safe_query_text=safe_text(xlsx_sample.get("safe_query_text"), "합계?"),
            source_type_hint="xlsx_business_structured_short_query",
            expected_evidence_lane="xlsx_structured_evidence",
            fallback_allowed=True,
            fallback_expected_route="pdf_business_ocr_mm",
            denominator_scope=DENOMINATOR_SCOPES["xlsx_business_structured"],
            human_judgment_required=True,
            codex_classification="pending_user_fallback_outcome_label",
            observed_primary_route="xlsx_business_structured",
            observed_candidate_routes=["xlsx_business_structured", "pdf_business_ocr_mm"],
            observed_fallback_attempts=xlsx_sample.get("fallback_attempts", [{"attempt": 1, "route": "pdf_business_ocr_mm"}]),
            notes="Human must label whether this bounded fallback was allowed and whether outcome is success, blocked, or wrong route.",
        ),
        review_row(
            query_id="fallback_review_text_pdf_ambiguous_001",
            safe_query_text="본문 내용을 찾아줘",
            source_type_hint="text_pdf_ambiguous",
            expected_evidence_lane="none",
            fallback_allowed=True,
            fallback_expected_route="",
            denominator_scope=DENOMINATOR_SCOPES["text_namuwiki_animation"],
            human_judgment_required=True,
            codex_classification="pending_user_fallback_outcome_label",
            observed_primary_route="diagnostic_multi_route",
            observed_candidate_routes=["text_namuwiki_animation", "pdf_business_ocr_mm"],
            notes="Human must decide the route label and whether fallback should be allowed for TEXT/PDF ambiguity.",
        ),
        review_row(
            query_id="fallback_review_pdf_content_file_identity_lane_001",
            safe_query_text="PDF에서 이 문서와 본문 근거를 확인해줘",
            source_type_hint="pdf_content_vs_file_identity",
            expected_evidence_lane="pdf_content_evidence",
            fallback_allowed=True,
            fallback_expected_route="pdf_business_ocr_mm",
            denominator_scope=DENOMINATOR_SCOPES["pdf_business_ocr_mm"],
            human_judgment_required=True,
            codex_classification="pending_user_pdf_lane_fallback_label",
            observed_primary_route="pdf_business_ocr_mm",
            observed_candidate_routes=["pdf_business_ocr_mm"],
            notes="Human must decide whether fallback across PDF CONTENT and FILE identity lanes is allowed; lanes stay separate.",
        ),
    ]


def fallback_codex_diagnostic_rows(sample_diagnostics: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    generic_pdf = sample_diagnostics.get("generic-pdf-file-identity", {})
    return [
        review_row(
            query_id="fallback_auto_pdf_generic_filename_identity_blocked_001",
            safe_query_text=safe_text(generic_pdf.get("safe_query_text"), "계약서 PDF 파일 찾아줘"),
            source_type_hint="pdf_file_identity_guard",
            reviewed_primary_route="policy_blocked",
            reviewed_candidate_routes=["pdf_business_ocr_mm"],
            expected_evidence_lane="pdf_file_identity",
            fallback_allowed=False,
            fallback_expected_route="",
            fallback_outcome_label="fallback_blocked_by_policy",
            wrong_route_label="not_official_metric_input",
            denominator_scope=DENOMINATOR_SCOPES["pdf_business_ocr_mm"],
            human_judgment_required=False,
            codex_classification="stable_identity_required_blocks_fallback",
            blocked_flags=["stable_identity_required"],
            notes="Codex diagnostic-only classification: no fallback can turn generic filename identity into stable document identity.",
        ),
        review_row(
            query_id="fallback_auto_max_attempts_guard_001",
            safe_query_text="second fallback attempt guard",
            source_type_hint="bounded_fallback_guard",
            reviewed_primary_route="policy_blocked",
            reviewed_candidate_routes=[],
            expected_evidence_lane="none",
            fallback_allowed=False,
            fallback_expected_route="",
            fallback_outcome_label="fallback_blocked_max_attempts",
            wrong_route_label="not_official_metric_input",
            denominator_scope=DENOMINATOR_SCOPES["text_namuwiki_animation"],
            human_judgment_required=False,
            codex_classification="maximum_one_fallback_attempt_enforced",
            blocked_flags=["maximum_fallback_attempts_exceeded"],
            notes="Codex diagnostic-only classification: fallback loop is bounded to at most one scoped fallback attempt.",
        ),
        review_row(
            query_id="fallback_auto_unscoped_retrieval_blocked_001",
            safe_query_text="unscoped fallback guard",
            source_type_hint="allow_unscoped_false_guard",
            reviewed_primary_route="policy_blocked",
            reviewed_candidate_routes=[],
            expected_evidence_lane="none",
            fallback_allowed=False,
            fallback_expected_route="",
            fallback_outcome_label="fallback_blocked_unscoped",
            wrong_route_label="not_official_metric_input",
            denominator_scope=DENOMINATOR_SCOPES["text_namuwiki_animation"],
            human_judgment_required=False,
            codex_classification="unscoped_fallback_blocked",
            blocked_flags=["allow_unscoped_false"],
            notes="Codex diagnostic-only classification: broad or unscoped fallback retrieval is blocked.",
        ),
        review_row(
            query_id="fallback_auto_xlsx_hidden_excluded_blocked_001",
            safe_query_text="[redacted xlsx excluded-row fallback guard]",
            source_type_hint="xlsx_hidden_or_excluded_guard",
            reviewed_primary_route="policy_blocked",
            reviewed_candidate_routes=["xlsx_business_structured"],
            expected_evidence_lane="xlsx_structured_evidence",
            fallback_allowed=False,
            fallback_expected_route="",
            fallback_outcome_label="fallback_blocked_by_policy",
            wrong_route_label="not_official_metric_input",
            denominator_scope=DENOMINATOR_SCOPES["xlsx_business_structured"],
            human_judgment_required=False,
            codex_classification="hidden_or_excluded_xlsx_fallback_blocked",
            blocked_flags=["hidden_negative_or_excluded_row_guard"],
            notes="Codex diagnostic-only classification: fallback cannot surface XLSX hidden/excluded content.",
        ),
    ]


def review_row(
    *,
    query_id: str,
    safe_query_text: str,
    source_type_hint: str,
    denominator_scope: str,
    reviewed_primary_route: str = "",
    reviewed_candidate_routes: list[str] | None = None,
    expected_evidence_lane: str = "",
    fallback_allowed: bool | str = "",
    fallback_expected_route: str = "",
    fallback_outcome_label: str = "",
    wrong_route_label: str = "",
    reviewer: str = "",
    reviewed_time: str = "",
    notes: str = "",
    human_judgment_required: bool,
    codex_classification: str,
    observed_primary_route: str = "",
    observed_candidate_routes: list[str] | None = None,
    observed_fallback_attempts: list[Mapping[str, Any]] | None = None,
    blocked_flags: list[str] | None = None,
) -> dict[str, Any]:
    row = {
        "query_id": query_id,
        "safe_query_text": safe_query_text,
        "source_type_hint": source_type_hint,
        "reviewed_primary_route": reviewed_primary_route,
        "reviewed_candidate_routes": reviewed_candidate_routes or [],
        "expected_evidence_lane": expected_evidence_lane,
        "fallback_allowed": fallback_allowed,
        "fallback_expected_route": fallback_expected_route,
        "fallback_outcome_label": fallback_outcome_label,
        "wrong_route_label": wrong_route_label,
        "denominator_scope": denominator_scope,
        "reviewer": reviewer,
        "reviewed_time": reviewed_time,
        "notes": notes,
        "label_status": "pending_user_review" if human_judgment_required else "codex_diagnostic_only_auto_classified",
        "human_judgment_required": human_judgment_required,
        "codex_auto_classified": not human_judgment_required,
        "codex_classification": codex_classification,
        "diagnostic_only": True,
        "official_metric_input": False,
        "official_denominator_mutation": False,
        "production_namespace_mutation": False,
        "production_vector_write": False,
        "observed_primary_route": observed_primary_route,
        "observed_candidate_routes": observed_candidate_routes or [],
        "observed_fallback_attempts": list(observed_fallback_attempts or []),
        "blocked_flags": blocked_flags or [],
    }
    return row


def build_guardrails(
    *,
    report: Mapping[str, Any],
    official_denominator_registry: Path,
    registry_sha_before: str,
    registry_sha_after: str,
    registry_changed: bool,
) -> dict[str, Any]:
    return {
        "official_denominator_registry_path": repo_relative(official_denominator_registry),
        "official_denominator_registry_sha256_before": registry_sha_before,
        "official_denominator_registry_sha256_after": registry_sha_after,
        "official_denominator_registry_changed": registry_changed,
        "official_denominator_opened_or_frozen": bool(report.get("official_denominator_opened_or_frozen", False)),
        "production_namespace_mutated": bool(report.get("production_namespace_mutated", False)),
        "production_vector_index_mutated": bool(report.get("production_vector_index_mutated", False)),
        "production_vector_written": bool(report.get("production_vector_written", False)),
        "candidate_artifact_mutated": False,
        "immutable_baseline_mutated": False,
        "diagnostic_only_row_promoted": bool(report.get("diagnostic_only_row_promoted", False)),
        "pdf_content_and_file_identity_aggregated": False,
        "hidden_xlsx_content_exposed": False,
        "policy_excluded_rows_counted_as_retrieval_failures": False,
        "route_metrics_official": False,
        "allow_unscoped": bool(report.get("architecture", {}).get("allow_unscoped_retrieval", False)),
    }


def counts(human_rows: list[Mapping[str, Any]], auto_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = human_rows + auto_rows
    return {
        "human_review_rows": len(human_rows),
        "codex_diagnostic_only_rows": len(auto_rows),
        "total_rows": len(rows),
        "official_metric_input_rows": sum(1 for row in rows if row.get("official_metric_input")),
        "tracks_present": TRACKS,
        "pdf_content_evidence_rows": sum(1 for row in rows if row.get("expected_evidence_lane") == "pdf_content_evidence"),
        "pdf_file_identity_rows": sum(1 for row in rows if row.get("expected_evidence_lane") == "pdf_file_identity"),
    }


def label_policy() -> dict[str, Any]:
    return {
        "human_owned_fields": HUMAN_LABEL_FIELDS,
        "codex_may_auto_classify": [
            "invalid_or_missing_llm_json",
            "route_not_allowed_by_hard_policy",
            "unsafe_denominator_or_promotion_mutation_claim",
            "hidden_or_excluded_xlsx_guard",
            "generic_pdf_filename_only_identity_guard",
            "fallback_attempt_exceeds_one",
            "unscoped_fallback_blocked",
        ],
        "do_not_compute": [
            "official_routing_accuracy",
            "official_wrong_route_rate",
            "official_fallback_success",
            "official_multi_route_success",
        ],
        "prefilled_fields_are_diagnostic_hints_not_gold_labels": True,
    }


def validate_pack(pack: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    rows = list(pack.get("human_review_rows", [])) + list(pack.get("codex_diagnostic_only_rows", []))
    for row in rows:
        for column in REQUIRED_COLUMNS:
            if column not in row:
                errors.append(f"{row.get('query_id', '<missing>')} missing required column {column}")
        if row.get("diagnostic_only") is not True:
            errors.append(f"{row.get('query_id')} is not diagnostic_only")
        if row.get("official_metric_input") is not False:
            errors.append(f"{row.get('query_id')} is official metric input")
    guardrails = pack.get("guardrails", {})
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
        "allow_unscoped",
    ]:
        if guardrails.get(key) is not False:
            errors.append(f"guardrail {key} expected false")
    if pack.get("counts", {}).get("official_metric_input_rows") != 0:
        errors.append("official metric input rows must remain 0")
    serialized = json.dumps(pack, ensure_ascii=False)
    for forbidden in ["hidden cell value", "xlsx_hidden_source_payload", "hidden_value_payload"]:
        if forbidden in serialized:
            errors.append(f"forbidden hidden XLSX marker surfaced: {forbidden}")
    return {"errors": errors, "ok": not errors}


def render_markdown(pack: Mapping[str, Any]) -> str:
    title = (
        "Route Gold Label Review Pack v1"
        if pack["pack_type"] == "route_gold_label_review"
        else "Fallback Outcome Label Review Pack v1"
    )
    lines = [
        f"# {title}",
        "",
        f"- Generated at: `{pack['generated_at']}`",
        f"- Status: `{pack['status']}`",
        "- Scope: diagnostic-only label preparation; this is not official route metric evidence.",
        f"- Source report: `{pack['source_report']['path']}`",
        f"- Human review rows: `{pack['counts']['human_review_rows']}`",
        f"- Codex diagnostic-only auto-classified rows: `{pack['counts']['codex_diagnostic_only_rows']}`",
        "- Guardrails: official denominator registry unchanged, production namespace/vector unchanged, "
        "PDF CONTENT and FILE identity lanes separated, XLSX hidden/excluded content not surfaced.",
        "",
        "## Required Columns",
        "",
        ", ".join(f"`{column}`" for column in REQUIRED_COLUMNS),
        "",
        "## Human Review Rows",
        "",
        "| query_id | safe_query_text | source_type_hint | expected_evidence_lane | fallback_expected_route | notes |",
        "|---|---|---|---|---|---|",
    ]
    for row in pack["human_review_rows"]:
        lines.append(markdown_row(row))
    lines.extend(
        [
            "",
            "## Codex Diagnostic-Only Auto-Classified Rows",
            "",
            "| query_id | safe_query_text | source_type_hint | expected_evidence_lane | fallback_outcome_label | codex_classification |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in pack["codex_diagnostic_only_rows"]:
        lines.append(
            "| "
            + " | ".join(
                escape_md(str(row.get(key, "")))
                for key in [
                    "query_id",
                    "safe_query_text",
                    "source_type_hint",
                    "expected_evidence_lane",
                    "fallback_outcome_label",
                    "codex_classification",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Metric Policy",
            "",
            "- `official_metric_input_rows`: `0`.",
            "- Route/fallback metrics remain diagnostic-only until this pack is reviewed.",
            "- Prefilled lanes and routes are diagnostic hints, not gold labels.",
            "",
            "## Guardrails",
            "",
        ]
    )
    for key, value in pack["guardrails"].items():
        if key.endswith("sha256_before") or key.endswith("sha256_after"):
            continue
        lines.append(f"- `{key}`: `{json.dumps(value, ensure_ascii=False)}`")
    return "\n".join(lines) + "\n"


def markdown_row(row: Mapping[str, Any]) -> str:
    return (
        "| "
        + " | ".join(
            escape_md(str(row.get(key, "")))
            for key in [
                "query_id",
                "safe_query_text",
                "source_type_hint",
                "expected_evidence_lane",
                "fallback_expected_route",
                "notes",
            ]
        )
        + " |"
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def safe_text(value: Any, fallback: str) -> str:
    return str(value) if isinstance(value, str) and value.strip() else fallback


def escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
