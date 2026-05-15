"""Validate anti-shortcut guardrails for the report-only canonical pack."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_XLSX_PACKET = REPORT_DIR / "rag_xlsx_answer_citation_policy_review_packet_v1.json"
DEFAULT_XLSX_LEAKAGE = REPORT_DIR / "xlsx_answer_citation_hidden_excluded_leakage_reprobe.json"
DEFAULT_XLSX_REVIEW_INPUT = REPORT_DIR / "xlsx_answer_citation_diagnostic_review_input.jsonl"
DEFAULT_PDF_REPAIR = REPORT_DIR / "pdf_evidence_readiness_repair_report.json"
DEFAULT_PDF_ANSWER_PACKET = REPORT_DIR / "rag_pdf_answer_citation_policy_review_packet_v1.json"
DEFAULT_PDF_REVIEW_INPUT = REPORT_DIR / "pdf_answer_citation_diagnostic_review_input.jsonl"
DEFAULT_HUMAN_AUDIT = REVIEW_DIR / "rag_human_audit_packet_v1.json"
DEFAULT_DRY_RUN_PLAN = REPORT_DIR / "report_only_tuning_dry_run_plan_v1.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "anti_shortcut_guardrail_audit_v1.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "anti_shortcut_guardrail_audit_v1.md"

FORMERLY_BLOCKED_PDF_ROWS = {"gq_auto_010", "gq_auto_015", "gq_auto_030"}
SOURCE_BOUND_BBOX_SOURCES = {
    "local_db.search_unit.location_json.bbox",
    "source_bound_search_unit.location_json.bbox",
    "local_db.search_unit.location_json",
}
FORBIDDEN_BBOX_SOURCES = {
    "",
    "synthetic",
    "generated",
    "inferred",
    "page_anchor_only",
    "full_page_fallback",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    audit = run_audit(
        xlsx_packet_path=Path(args.xlsx_packet),
        xlsx_leakage_reprobe_path=Path(args.xlsx_leakage_reprobe),
        xlsx_review_input_path=Path(args.xlsx_review_input),
        pdf_repair_report_path=Path(args.pdf_repair_report),
        pdf_answer_packet_path=Path(args.pdf_answer_packet),
        pdf_review_input_path=Path(args.pdf_review_input),
        human_audit_packet_path=Path(args.human_audit_packet),
        dry_run_plan_path=Path(args.dry_run_plan),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": audit["status"],
                "report": audit["artifact_paths"]["report_json"],
                "shortcut_errors": len(audit["validation"]["errors"]),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if audit["validation"]["ok"] else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx-packet", default=str(DEFAULT_XLSX_PACKET))
    parser.add_argument("--xlsx-leakage-reprobe", default=str(DEFAULT_XLSX_LEAKAGE))
    parser.add_argument("--xlsx-review-input", default=str(DEFAULT_XLSX_REVIEW_INPUT))
    parser.add_argument("--pdf-repair-report", default=str(DEFAULT_PDF_REPAIR))
    parser.add_argument("--pdf-answer-packet", default=str(DEFAULT_PDF_ANSWER_PACKET))
    parser.add_argument("--pdf-review-input", default=str(DEFAULT_PDF_REVIEW_INPUT))
    parser.add_argument("--human-audit-packet", default=str(DEFAULT_HUMAN_AUDIT))
    parser.add_argument("--dry-run-plan", default=str(DEFAULT_DRY_RUN_PLAN))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_audit(
    *,
    xlsx_packet_path: Path,
    xlsx_leakage_reprobe_path: Path,
    xlsx_review_input_path: Path,
    pdf_repair_report_path: Path,
    pdf_answer_packet_path: Path,
    pdf_review_input_path: Path,
    human_audit_packet_path: Path,
    dry_run_plan_path: Path,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    xlsx_packet = read_json(xlsx_packet_path)
    xlsx_leakage = read_json(xlsx_leakage_reprobe_path)
    xlsx_review_rows = read_jsonl(xlsx_review_input_path)
    pdf_repair = read_json(pdf_repair_report_path)
    pdf_answer = read_json(pdf_answer_packet_path)
    pdf_review_rows = read_jsonl(pdf_review_input_path)
    human_audit = read_json(human_audit_packet_path)
    dry_run_plan = read_json(dry_run_plan_path)

    checks = {
        "xlsx_public_private_surface_separation": check_xlsx_public_private(
            xlsx_packet=xlsx_packet,
            xlsx_leakage=xlsx_leakage,
            xlsx_review_rows=xlsx_review_rows,
        ),
        "pdf_bbox_source_bound_proof": check_pdf_bbox_source_bound(pdf_repair),
        "pdf_answer_citation_packet": check_pdf_answer_packet(pdf_answer=pdf_answer, pdf_review_rows=pdf_review_rows),
        "human_audit_packet": check_human_audit_packet(human_audit),
        "dry_run_plan": check_dry_run_plan(dry_run_plan),
    }
    errors: list[str] = []
    for check in checks.values():
        errors.extend(check["errors"])
    audit = {
        "schema_version": "anti_shortcut_guardrail_audit_v1",
        "generated_at": utc_timestamp(),
        "status": "ANTI_SHORTCUT_GUARDRAIL_AUDIT_PASS" if not errors else "ANTI_SHORTCUT_GUARDRAIL_AUDIT_FAIL_CLOSED",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "checks": checks,
        "validation": {"ok": not errors, "errors": sorted(dict.fromkeys(errors))},
        "artifact_paths": {"report_json": repo_relative(output_report), "report_md": repo_relative(output_md)},
    }
    write_json(output_report, audit)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(audit), encoding="utf-8")
    return audit


def check_xlsx_public_private(
    *,
    xlsx_packet: Mapping[str, Any],
    xlsx_leakage: Mapping[str, Any],
    xlsx_review_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    surface_leakage_count = max(
        int_value(nested_mapping(xlsx_leakage, "metrics").get("surface_leakage_count")),
        int_value(nested_mapping(xlsx_leakage, "counts").get("surface_leakage_count")),
        sum(1 for row in nested_sequence(xlsx_leakage, "query_results") if int_value(row.get("surface_violation_count")) > 0),
    )
    annotation_only_promoted = nested_mapping(xlsx_leakage, "allowlist_policy").get(
        "annotation_only_allowlist_promoted_to_pass"
    ) is True or nested_mapping(xlsx_packet, "guardrails").get("annotation_only_allowlist_promoted_to_pass") is True
    private_formatter_rows = sum(1 for row in xlsx_review_rows if isinstance(row.get("formatter_input"), Mapping))
    if clean(xlsx_leakage.get("status")) != "PASS":
        errors.append("XLSX leakage reprobe must be PASS")
    if surface_leakage_count != 0:
        errors.append("XLSX hidden/excluded row appeared on public surface")
    if annotation_only_promoted:
        errors.append("annotation-only allowlist cannot create PASS")
    if xlsx_packet.get("official_metric") is True or int_value(xlsx_packet.get("official_metric_input_rows")) != 0:
        errors.append("XLSX official rows must remain closed")
    if xlsx_packet.get("promotion_evidence") is True:
        errors.append("XLSX packet must not be promotion evidence")
    return {
        "ok": not errors,
        "public_surface_policy": "generated_answer, answer_claims, citation_items only",
        "private_formatter_input_rows": private_formatter_rows,
        "private_formatter_input_treated_as_public": False,
        "public_surface_leakage_count": surface_leakage_count,
        "annotation_only_allowlist_promoted_to_pass": annotation_only_promoted,
        "errors": errors,
    }


def check_pdf_bbox_source_bound(pdf_repair: Mapping[str, Any]) -> dict[str, Any]:
    rows = [row for row in nested_sequence(pdf_repair, "repair_rows") if row.get("strict_ready") is True]
    errors: list[str] = []
    forbidden_rows: list[str] = []
    formerly_blocked_checked: list[str] = []
    for row in rows:
        qid = clean(row.get("query_id"))
        for field in (
            "search_unit_id",
            "page",
            "bbox",
            "region_type",
            "bbox_source",
            "layout_resolution_method",
            "citation_locator",
        ):
            if not row.get(field):
                errors.append(f"PDF strict-ready row {qid} missing {field}")
        if not (row.get("source_file_id") or row.get("stable_source_identity")):
            errors.append(f"PDF strict-ready row {qid} missing source_file_id or stable identity")
        if not (row.get("parser_version") or nested_mapping(row, "source_metadata").get("parser_version") or row.get("source_metadata")):
            errors.append(f"PDF strict-ready row {qid} missing parser/source metadata")
        bbox_source = clean(row.get("bbox_source"))
        method = clean(row.get("layout_resolution_method"))
        if bbox_source_forbidden(bbox_source):
            errors.append(f"PDF bbox source must be source-bound for {qid}")
            forbidden_rows.append(qid)
        if full_page_or_anchor_fallback(bbox_source, method):
            errors.append(f"full-page/page-anchor fallback cannot make strict-ready row {qid}")
        if qid in FORMERLY_BLOCKED_PDF_ROWS:
            formerly_blocked_checked.append(qid)
            if bbox_source not in SOURCE_BOUND_BBOX_SOURCES:
                errors.append(f"formerly blocked PDF row {qid} must use source-bound bbox")
    missing_former = sorted(FORMERLY_BLOCKED_PDF_ROWS - set(formerly_blocked_checked))
    errors.extend(f"formerly blocked PDF row {qid} missing from strict-ready proof" for qid in missing_former)
    if int_value(pdf_repair.get("strict_ready_rows")) != len(rows):
        errors.append("PDF strict_ready_rows must match strict-ready proof rows")
    return {
        "ok": not errors,
        "strict_ready_rows_checked": len(rows),
        "formerly_blocked_rows_checked": sorted(formerly_blocked_checked),
        "forbidden_bbox_source_rows": forbidden_rows,
        "errors": errors,
    }


def check_pdf_answer_packet(*, pdf_answer: Mapping[str, Any], pdf_review_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    clean_pass_rows = int_value(pdf_answer.get("clean_pass_rows"))
    cleanup_rows = int_value(pdf_answer.get("cleanup_rows"))
    unresolved_rows = int_value(pdf_answer.get("unresolved_rows"))
    lane_policy_blocked_rows = int_value(pdf_answer.get("lane_policy_blocked_rows"))
    answer_support_pass_count = int_value(pdf_answer.get("answer_support_pass_count"))
    citation_locator_valid_count = int_value(pdf_answer.get("citation_locator_valid_count"))
    if clean(pdf_answer.get("status")) != "DIAGNOSTIC_POLICY_PACKET_READY":
        errors.append("PDF answer/citation packet must be DIAGNOSTIC_POLICY_PACKET_READY")
    if int_value(pdf_answer.get("input_rows")) != 7 or int_value(pdf_answer.get("strict_ready_rows")) != 7:
        errors.append("PDF answer/citation packet must use exactly 7 strict-ready rows")
    if clean_pass_rows != 7:
        errors.append("PDF answer/citation packet must have 7 clean pass rows")
    if cleanup_rows != 0 or unresolved_rows != 0 or lane_policy_blocked_rows != 0:
        errors.append("PDF answer/citation packet must have 0 cleanup/unresolved/lane-policy rows")
    if answer_support_pass_count != 7 or citation_locator_valid_count != 7:
        errors.append("PDF answer/citation packet must have 7 support and citation-valid rows")
    if int_value(pdf_answer.get("diagnostic_fallback_rows_used")) != 0 or nested_mapping(pdf_answer, "guardrails").get(
        "diagnostic_fallback_rows_used"
    ) is True:
        errors.append("PDF answer/citation packet must exclude diagnostic fallback rows")
    if pdf_answer.get("content_file_identity_lane_merge") is True or nested_mapping(pdf_answer, "guardrails").get(
        "content_file_identity_lane_merge"
    ) is True:
        errors.append("PDF answer/citation packet must not merge CONTENT and FILE lanes")
    if pdf_answer.get("filename_only_identity_accepted") is True or nested_mapping(pdf_answer, "guardrails").get(
        "filename_only_identity_accepted"
    ) is True:
        errors.append("PDF answer/citation packet must not accept filename-only identity")
    if int_value(pdf_answer.get("official_metric_input_rows")) != 0:
        errors.append("PDF answer/citation official_metric_input_rows must remain 0")
    if pdf_answer.get("promotion_evidence") is True:
        errors.append("PDF answer/citation packet must not be promotion evidence")
    if pdf_answer.get("pdf_answer_generation_denominator_opened") is True:
        errors.append("PDF answer denominator must remain closed")
    if len(pdf_review_rows) != 7:
        errors.append("PDF review input must contain exactly 7 strict-ready rows")
    if any(row.get("no_file_identity_lane_used_as_content_evidence") is not True for row in pdf_review_rows):
        errors.append("PDF FILE identity lane used as CONTENT evidence")
    if any(row.get("no_filename_only_identity_acceptance") is not True for row in pdf_review_rows):
        errors.append("PDF filename-only identity accepted")
    if any(row.get("official_metric_input") is not False for row in pdf_review_rows):
        errors.append("PDF review rows must keep official_metric_input=false")
    if any(row.get("promotion_evidence") is True for row in pdf_review_rows):
        errors.append("PDF review rows must keep promotion_evidence=false")
    return {
        "ok": not errors,
        "input_rows": int_value(pdf_answer.get("input_rows")),
        "strict_ready_rows": int_value(pdf_answer.get("strict_ready_rows")),
        "clean_pass_rows": clean_pass_rows,
        "cleanup_rows": cleanup_rows,
        "unresolved_rows": unresolved_rows,
        "lane_policy_blocked_rows": lane_policy_blocked_rows,
        "answer_support_pass_count": answer_support_pass_count,
        "citation_locator_valid_count": citation_locator_valid_count,
        "review_input_rows": len(pdf_review_rows),
        "official_metric_input_rows": int_value(pdf_answer.get("official_metric_input_rows")),
        "promotion_evidence": pdf_answer.get("promotion_evidence") is True,
        "errors": errors,
    }


def check_human_audit_packet(human: Mapping[str, Any]) -> dict[str, Any]:
    answer_recovery = nested_mapping(human, "sections", "answer_recovery")
    xlsx = nested_mapping(human, "sections", "xlsx_business_structured")
    pdf = nested_mapping(human, "sections", "pdf_business_ocr_mm")
    errors: list[str] = []
    if clean(human.get("status")) != "HUMAN_AUDIT_PACKET_READY":
        errors.append("human audit packet must be ready")
    if int_value(human.get("official_metric_input_rows")) != 0 or human.get("official_metric") is True:
        errors.append("human audit packet official rows must remain 0")
    if human.get("promotion_evidence") is True:
        errors.append("human audit packet must not be promotion evidence")
    if int_value(xlsx.get("hidden_excluded_rows_candidate_count")) != 0:
        errors.append("human audit must not include hidden/excluded XLSX rows as candidates")
    if pdf.get("filename_only_identity_accepted") is True:
        errors.append("human audit must not auto-accept PDF filename-only identity")
    if answer_recovery.get("gold_policy_required_count_matches_report") is not True:
        errors.append("human audit answer recovery GOLD_POLICY_REQUIRED count mismatch")
    if answer_recovery.get("gold_policy_required_ids_match_report") is not True:
        errors.append("human audit answer recovery GOLD_POLICY_REQUIRED id mismatch")
    if int_value(answer_recovery.get("gold_policy_required_rows")) <= 0:
        errors.append("human audit must include answer recovery GOLD_POLICY_REQUIRED rows")
    return {
        "ok": not errors,
        "total_user_action_rows": nested_mapping(human, "summary").get("total_user_action_rows"),
        "gold_policy_required_rows": int_value(answer_recovery.get("gold_policy_required_rows")),
        "gold_policy_required_count_matches_report": answer_recovery.get("gold_policy_required_count_matches_report") is True,
        "gold_policy_required_ids_match_report": answer_recovery.get("gold_policy_required_ids_match_report") is True,
        "errors": errors,
    }


def check_dry_run_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if plan.get("tuning_run_started") is not False:
        errors.append("dry-run plan must not start tuning")
    if (
        plan.get("cross_track_average_optimization_allowed") is True
        or plan.get("cross_track_averages_computed") is True
        or nested_mapping(plan, "split_policy").get("cross_track_average_computed") is True
    ):
        errors.append("dry-run plan must not compute or optimize cross-track averages")
    if int_value(plan.get("official_metric_input_rows")) != 0:
        errors.append("dry-run plan official_metric_input_rows must remain 0")
    by_track = plan.get("official_metric_input_rows_by_track") if isinstance(plan.get("official_metric_input_rows_by_track"), Mapping) else {}
    if any(int_value(value) != 0 for value in by_track.values()):
        errors.append("dry-run plan track official_metric_input_rows must remain 0")
    if nested_mapping(plan, "split_policy").get("parameter_winner_selected") is True:
        errors.append("dry-run plan must not pick production winners")
    if not {"text_namu_v2_1", "xlsx_business_structured", "pdf_business_ocr_mm"}.issubset(
        set(nested_mapping(plan, "track_dev_set_policy"))
    ):
        errors.append("dry-run plan must keep track-specific dev policies")
    return {
        "ok": not errors,
        "tuning_run_started": plan.get("tuning_run_started") is True,
        "cross_track_average_optimization_allowed": plan.get("cross_track_average_optimization_allowed") is True,
        "official_metric_input_rows": int_value(plan.get("official_metric_input_rows")),
        "errors": errors,
    }


def bbox_source_forbidden(value: str) -> bool:
    lowered = value.lower()
    return (
        not value
        or any(token and token in lowered for token in FORBIDDEN_BBOX_SOURCES)
        or value not in SOURCE_BOUND_BBOX_SOURCES
    )


def full_page_or_anchor_fallback(bbox_source: str, method: str) -> bool:
    joined = f"{bbox_source} {method}".lower()
    return any(token in joined for token in ("page_anchor_only", "full_page_fallback", "full_page"))


def render_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        "# Anti-Shortcut Guardrail Audit v1",
        "",
        f"- Status: `{audit['status']}`",
        f"- Errors: `{len(audit['validation']['errors'])}`",
        "",
    ]
    for name, check in audit["checks"].items():
        lines.append(f"- `{name}`: `{'PASS' if check['ok'] else 'FAIL'}`")
    return "\n".join(lines) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                payload = json.loads(line)
                if isinstance(payload, dict):
                    rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def nested_mapping(payload: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return current if isinstance(current, Mapping) else {}


def nested_sequence(payload: Mapping[str, Any], *keys: str) -> list[Mapping[str, Any]]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return []
        current = current.get(key)
    return [row for row in current if isinstance(row, Mapping)] if isinstance(current, list) else []


def int_value(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def clean(value: Any) -> str:
    return str(value or "").strip()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
