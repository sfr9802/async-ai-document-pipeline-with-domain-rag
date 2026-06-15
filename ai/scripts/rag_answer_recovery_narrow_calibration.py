"""Run narrow report-only answer recovery calibration over diagnostic cases.

This is not broad tuning. It evaluates deterministic policy variants against
the expanded answer recovery diagnostic report and rejects any variant that
weakens PDF FILE identity exactness, hidden XLSX blocking, diagnostic-only
evidence blocking, or denominator/index guardrails.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import rag_answer_recovery_report_artifacts as report_artifacts  # noqa: E402

DEFAULT_CONFIG = AI_WORKER_ROOT / "eval" / "configs" / "answer_recovery_narrow_silver_calibration.yaml"
DEFAULT_REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
PDF_FILE_LOOKUP = "PDF_FILE_LOOKUP"
XLSX = "XLSX"
SHADOW_LANES = {"OCR_SHADOW", "IDP_SHADOW", "MULTIMODAL_SHADOW"}
SUPPORTED = "SUPPORTED"
UNSUPPORTED = "UNSUPPORTED"
NEEDS_RECOVERY = "NEEDS_RECOVERY"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = resolve_path(args.config)
    config = report_artifacts.with_reporting_overrides(
        load_config(config_path),
        report_artifacts.reporting_overrides_from_args(args),
    )
    report_dir = resolve_path(args.reports_dir or DEFAULT_REPORT_DIR)
    report_dir.mkdir(parents=True, exist_ok=True)
    report = run_calibration(config=config, config_path=config_path, report_dir=report_dir)
    write_outputs(config, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "selected_variant": report["selected_policy"]["variant_name"],
                "wrongly_supported_count": report["selected_policy"]["counts"]["wrongly_supported_count"],
                "tuning_ready": report["decision"]["tuning_ready"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORT_DIR))
    report_artifacts.add_reporting_args(parser)
    return parser.parse_args(argv)


def run_calibration(*, config: Mapping[str, Any], config_path: Path, report_dir: Path) -> dict[str, Any]:
    expanded_report_path = resolve_path(config["silver_only_diagnostic_inputs"]["answer_recovery_expanded_input"][0])
    expanded = read_json(expanded_report_path)
    case_results = expanded["case_results"]
    baseline = variant_metrics(
        case_results,
        {
            "name": "calibrated_identity_exact_v1",
            "support_score_threshold": 0.0,
            "citation_coverage_threshold": 1.0,
            "pdf_file_identity_exactness_rule": "exact_or_canonical_identity_required",
        },
        baseline_counts=None,
    )
    variants = []
    for variant in config["variants"]:
        metrics = variant_metrics(case_results, variant, baseline_counts=baseline)
        metrics["rejection_reasons"] = rejection_reasons(metrics, variant, baseline)
        metrics["accepted"] = not metrics["rejection_reasons"]
        variants.append(metrics)
    selected = select_variant(variants, baseline)
    before = read_json(report_dir / "pdf_file_lookup_wrongly_supported_root_cause.json")
    before_wrongly_supported = int(before.get("counts", {}).get("case_count", 0))
    guardrails = build_guardrail_status(config)
    registry_changed = official_registry_changed()
    guardrails["official_denominator_registry_changed"] = registry_changed
    if registry_changed:
        selected["rejection_reasons"] = [*selected["rejection_reasons"], "official_denominator_registry_changed"]
        selected["accepted"] = False
    decision = {
        "tuning_ready": (
            "true_for_narrow_silver_only_calibration"
            if selected["accepted"] and selected["counts"]["wrongly_supported_count"] == 0 and not registry_changed
            else "false"
        ),
        "production_promotion_ready": False,
        "official_answer_denominator_ready": False,
        "reason": "Selected diagnostic-only policy preserves all guardrails with zero wrongly-supported cases."
        if selected["accepted"]
        else "No acceptable diagnostic calibration variant was selected.",
    }
    return {
        "schema_version": "answer_recovery_narrow_calibration_report_v1",
        "status": "PASS" if decision["tuning_ready"] == "true_for_narrow_silver_only_calibration" else "BLOCKED",
        "config_path": repo_relative(config_path),
        "selection_inputs": {
            "expanded_report": repo_relative(expanded_report_path),
            "frozen_gold_used_for_selection": False,
            "frozen_gold_used_for_training": False,
            "excluded_frozen_gold_id_count": len(config["excluded_frozen_gold_ids"]["ids"]),
            "silver_only_diagnostic_inputs": config["silver_only_diagnostic_inputs"],
        },
        "before_after_counts": {
            "before_calibration_wrongly_supported_count": before_wrongly_supported,
            "after_calibration_wrongly_supported_count": selected["counts"]["wrongly_supported_count"],
            "after_hidden_xlsx_surface_attempt_count": selected["counts"]["hidden_xlsx_surface_attempt_count"],
            "after_pdf_file_lookup_content_mixing_attempt_count": selected["counts"]["pdf_file_lookup_content_mixing_attempt_count"],
            "after_diagnostic_only_evidence_blocked_count": selected["counts"]["diagnostic_only_evidence_blocked_count"],
        },
        "decision": decision,
        "selected_policy": build_selected_policy(selected, config, guardrails),
        "variants": variants,
        "rejected_variants": [
            {"variant_name": row["variant_name"], "rejection_reasons": row["rejection_reasons"]}
            for row in variants
            if row["variant_name"] != selected["variant_name"]
        ],
        "guardrail_status": guardrails,
        "official_denominator_registry_changed": registry_changed,
    }


def write_outputs(config: Mapping[str, Any], report: Mapping[str, Any]) -> None:
    options = report_artifacts.reporting_options(config)
    paths = config["report_paths"]
    if options["emit_stage_reports"]:
        write_json(resolve_path(paths["calibration_report_json"]), report)
        write_text(resolve_path(paths["calibration_report_md"]), render_report_md(report))
        write_json(resolve_path(paths["selected_policy_json"]), report["selected_policy"])
    if options["emit_csv"]:
        write_csv(resolve_path(paths["variants_csv"]), report["variants"])


def variant_metrics(
    case_results: Sequence[Mapping[str, Any]],
    variant: Mapping[str, Any],
    baseline_counts: Mapping[str, Any] | None,
) -> dict[str, Any]:
    lane_breakdown: dict[str, dict[str, int]] = {}
    before_coverages: list[float] = []
    after_coverages: list[float] = []
    loop_iterations: list[int] = []
    counts = Counter()
    for row in case_results:
        before = transform_decision(row, row["before_decision"], variant)
        after = transform_decision(row, row["after_decision"], variant)
        lane = row["lane"]
        expected_support = bool(row.get("expected_official_support_allowed"))
        item = lane_breakdown.setdefault(
            lane,
            {
                "total": 0,
                "initially_supported": 0,
                "supported_after_recovery": 0,
                "wrongly_supported": 0,
                "unsupported_correctly_blocked": 0,
            },
        )
        item["total"] += 1
        if before["sufficiency_status"] == SUPPORTED:
            item["initially_supported"] += 1
            counts["initially_supported"] += 1
        if after["sufficiency_status"] == SUPPORTED:
            item["supported_after_recovery"] += 1
        if after["sufficiency_status"] == SUPPORTED and not expected_support:
            item["wrongly_supported"] += 1
            counts["wrongly_supported_count"] += 1
        if after["sufficiency_status"] != SUPPORTED and not expected_support:
            item["unsupported_correctly_blocked"] += 1
            counts["unsupported_correctly_blocked_count"] += 1
        if row["route"]["action"] == "ASK_CLARIFICATION" or after["sufficiency_status"] == "NEEDS_CLARIFICATION":
            counts["clarification_needed_count"] += 1
        if row.get("loop_result") and after["sufficiency_status"] == SUPPORTED:
            counts["recovered_after_loop"] += 1
        if row.get("loop_result"):
            loop_iterations.append(int(row["loop_result"]["loop_iterations"]))
        before_coverages.append(float(before.get("citation_coverage", 0.0)))
        after_coverages.append(float(after.get("citation_coverage", 0.0)))
        if is_hidden_xlsx_case(row) and after["sufficiency_status"] != SUPPORTED:
            counts["hidden_xlsx_surface_attempt_count"] += 1
        if is_pdf_file_content_mixing_case(row) and after["sufficiency_status"] != SUPPORTED:
            counts["pdf_file_lookup_content_mixing_attempt_count"] += 1
        counts["diagnostic_only_evidence_blocked_count"] += diagnostic_only_block_increment(row, before, after)
    return {
        "variant_name": variant["name"],
        "support_score_threshold": variant.get("support_score_threshold", 0.0),
        "citation_coverage_threshold": variant.get("citation_coverage_threshold", 1.0),
        "needs_recovery_vs_unsupported_boundary": variant.get("needs_recovery_vs_unsupported_boundary", "keep_current_fail_closed"),
        "needs_clarification_routing_threshold": variant.get(
            "needs_clarification_routing_threshold", "current_ambiguous_or_missing_identity"
        ),
        "pdf_file_identity_exactness_rule": variant.get("pdf_file_identity_exactness_rule", "exact_or_canonical_identity_required"),
        "hidden_xlsx_blocking": variant.get("hidden_xlsx_blocking", "enabled"),
        "diagnostic_only_support": variant.get("diagnostic_only_support", "disabled"),
        "total_evaluated": len(case_results),
        "counts": {
            "total_evaluated": len(case_results),
            "initially_supported": counts["initially_supported"],
            "recovered_after_loop": counts["recovered_after_loop"],
            "wrongly_supported_count": counts["wrongly_supported_count"],
            "unsupported_correctly_blocked_count": counts["unsupported_correctly_blocked_count"],
            "clarification_needed_count": counts["clarification_needed_count"],
            "hidden_xlsx_surface_attempt_count": counts["hidden_xlsx_surface_attempt_count"],
            "pdf_file_lookup_content_mixing_attempt_count": counts["pdf_file_lookup_content_mixing_attempt_count"],
            "diagnostic_only_evidence_blocked_count": counts["diagnostic_only_evidence_blocked_count"],
            "citation_coverage_before": average(before_coverages),
            "citation_coverage_after": average(after_coverages),
            "average_loop_iterations": average(loop_iterations),
        },
        "lane_breakdown": dict(sorted(lane_breakdown.items())),
        "accepted": False,
        "rejection_reasons": [],
    }


def transform_decision(
    row: Mapping[str, Any],
    decision: Mapping[str, Any],
    variant: Mapping[str, Any],
) -> dict[str, Any]:
    transformed = deepcopy(dict(decision))
    blocked = set(transformed.get("blocked_lanes", []))
    if variant.get("pdf_file_identity_exactness_rule") == "filename_token_overlap_allowed" and row["lane"] == PDF_FILE_LOOKUP:
        if blocked.intersection({"PDF_FILE_HARD_NEGATIVE_IDENTITY", "PDF_FILE_IDENTITY_MISMATCH"}):
            transformed["sufficiency_status"] = SUPPORTED
            transformed["failure_type"] = ""
            transformed["blocked_lanes"] = []
    if variant.get("hidden_xlsx_blocking") == "disabled" and "XLSX_HIDDEN_CONTENT" in blocked:
        transformed["sufficiency_status"] = SUPPORTED
        transformed["failure_type"] = ""
        transformed["blocked_lanes"] = []
    if variant.get("diagnostic_only_support") == "enabled" and (
        row["lane"] in SHADOW_LANES or blocked.intersection(SHADOW_LANES)
    ):
        transformed["sufficiency_status"] = SUPPORTED
        transformed["failure_type"] = ""
        transformed["blocked_lanes"] = []
    if (
        variant.get("needs_recovery_vs_unsupported_boundary") == "retry_uncited_diagnostic_only"
        and transformed["sufficiency_status"] == UNSUPPORTED
        and transformed.get("failure_type") == "INSUFFICIENT_EVIDENCE"
        and transformed.get("citation_coverage", 0.0) == 0.0
    ):
        transformed["sufficiency_status"] = NEEDS_RECOVERY
    if transformed["sufficiency_status"] == SUPPORTED:
        if float(transformed.get("support_score", 0.0)) < float(variant.get("support_score_threshold", 0.0)):
            transformed["sufficiency_status"] = UNSUPPORTED
            transformed["failure_type"] = "INSUFFICIENT_EVIDENCE"
            transformed["blocked_lanes"] = [*transformed.get("blocked_lanes", []), "SUPPORT_SCORE_BELOW_THRESHOLD"]
        elif float(transformed.get("citation_coverage", 0.0)) < float(variant.get("citation_coverage_threshold", 0.0)):
            transformed["sufficiency_status"] = UNSUPPORTED
            transformed["failure_type"] = "INSUFFICIENT_EVIDENCE"
            transformed["blocked_lanes"] = [*transformed.get("blocked_lanes", []), "CITATION_COVERAGE_BELOW_THRESHOLD"]
    return transformed


def rejection_reasons(metrics: Mapping[str, Any], variant: Mapping[str, Any], baseline: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    counts = metrics["counts"]
    baseline_counts = baseline["counts"]
    if counts["wrongly_supported_count"] > 0:
        reasons.append("wrongly_supported_count > 0")
    if counts["hidden_xlsx_surface_attempt_count"] < baseline_counts["hidden_xlsx_surface_attempt_count"]:
        reasons.append("weakens hidden XLSX blocking")
    if counts["pdf_file_lookup_content_mixing_attempt_count"] < baseline_counts["pdf_file_lookup_content_mixing_attempt_count"]:
        reasons.append("weakens PDF FILE content-mixing blocking")
    if counts["diagnostic_only_evidence_blocked_count"] < baseline_counts["diagnostic_only_evidence_blocked_count"]:
        reasons.append("weakens diagnostic-only evidence blocking")
    if variant.get("pdf_file_identity_exactness_rule", "exact_or_canonical_identity_required") != "exact_or_canonical_identity_required":
        reasons.append("weakens PDF FILE identity exactness")
    if variant["name"] != "calibrated_identity_exact_v1" and not reasons:
        if (
            counts["recovered_after_loop"] <= baseline_counts["recovered_after_loop"]
            and counts["citation_coverage_after"] <= baseline_counts["citation_coverage_after"]
        ):
            reasons.append("no recovery or citation-coverage improvement")
    return reasons


def select_variant(variants: Sequence[Mapping[str, Any]], baseline: Mapping[str, Any]) -> dict[str, Any]:
    accepted = [dict(row) for row in variants if row["accepted"]]
    if not accepted:
        return dict(baseline)
    accepted.sort(
        key=lambda row: (
            row["counts"]["wrongly_supported_count"] == 0,
            row["counts"]["recovered_after_loop"],
            row["counts"]["citation_coverage_after"],
            row["variant_name"] == "calibrated_identity_exact_v1",
        ),
        reverse=True,
    )
    return accepted[0]


def build_selected_policy(
    selected: Mapping[str, Any],
    config: Mapping[str, Any],
    guardrails: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "answer_recovery_narrow_calibration_selected_policy_v1",
        "variant_name": selected["variant_name"],
        "diagnostic_only": True,
        "production_promotion_ready": False,
        "official_answer_denominator_ready": False,
        "policy": {
            "support_score_threshold": selected["support_score_threshold"],
            "citation_coverage_threshold": selected["citation_coverage_threshold"],
            "needs_recovery_vs_unsupported_boundary": selected["needs_recovery_vs_unsupported_boundary"],
            "needs_clarification_routing_threshold": selected["needs_clarification_routing_threshold"],
            "pdf_file_identity_exactness_rule": selected["pdf_file_identity_exactness_rule"],
            "max_loop_iterations": config["allowed_calibration_knobs"]["max_loop_iterations"],
            "max_query_rewrites": config["allowed_calibration_knobs"]["max_query_rewrites"],
        },
        "counts": selected["counts"],
        "lane_breakdown": selected["lane_breakdown"],
        "guardrails": dict(guardrails),
    }


def build_guardrail_status(config: Mapping[str, Any]) -> dict[str, Any]:
    assertions = dict(config["guardrail_assertions"])
    assertions["production_index_mutation"] = False
    assertions["broad_indexing"] = False
    assertions["official_answer_denominator_opened"] = False
    assertions["production_promotion_ready"] = False
    assertions["official_answer_denominator_ready"] = False
    return assertions


def is_hidden_xlsx_case(row: Mapping[str, Any]) -> bool:
    blocked = set(row["before_decision"].get("blocked_lanes", [])) | set(row["after_decision"].get("blocked_lanes", []))
    return row["lane"] == XLSX and "XLSX_HIDDEN_CONTENT" in blocked


def is_pdf_file_content_mixing_case(row: Mapping[str, Any]) -> bool:
    return row["lane"] == PDF_FILE_LOOKUP and row.get("case_type") == "pdf_file_lookup_content_mixing"


def diagnostic_only_block_increment(
    row: Mapping[str, Any],
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> int:
    if after["sufficiency_status"] == SUPPORTED:
        return 0
    blocked = set(before.get("blocked_lanes", [])) | set(after.get("blocked_lanes", []))
    count = 0
    if row["lane"] in SHADOW_LANES:
        count += 1
    if blocked.intersection(SHADOW_LANES):
        count += 1
    return count


def official_registry_changed() -> bool:
    registry = AI_WORKER_ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"
    result = subprocess.run(
        ["git", "diff", "--quiet", "--", str(registry.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    return result.returncode != 0


def render_report_md(payload: Mapping[str, Any]) -> str:
    selected = payload["selected_policy"]
    lines = [
        "# Answer Recovery Narrow Calibration Report",
        "",
        f"- Status: `{payload['status']}`.",
        f"- Selected policy: `{selected['variant_name']}`.",
        f"- Tuning ready: `{payload['decision']['tuning_ready']}`.",
        "- Production promotion ready: `false`.",
        "- Official answer denominator ready: `false`.",
        "- Frozen gold used for selection: `false`.",
        "- Official denominator registry changed: `false`.",
        "",
        "## Before/After Counts",
        "",
    ]
    for key, value in payload["before_after_counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Selected Counts", ""])
    for key, value in selected["counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Rejected Variants", ""])
    for item in payload["rejected_variants"]:
        reasons = ", ".join(item["rejection_reasons"]) or "not selected"
        lines.append(f"- {item['variant_name']}: {reasons}")
    lines.extend(["", "## Guardrails", ""])
    for key, value in payload["guardrail_status"].items():
        if isinstance(value, Mapping):
            compact = ", ".join(f"{subkey}={subvalue}" for subkey, subvalue in value.items())
            lines.append(f"- {key}: `{compact}`")
        else:
            lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "variant_name",
        "accepted",
        "rejection_reasons",
        "total_evaluated",
        "initially_supported",
        "recovered_after_loop",
        "wrongly_supported_count",
        "unsupported_correctly_blocked_count",
        "clarification_needed_count",
        "hidden_xlsx_surface_attempt_count",
        "pdf_file_lookup_content_mixing_attempt_count",
        "diagnostic_only_evidence_blocked_count",
        "citation_coverage_before",
        "citation_coverage_after",
        "average_loop_iterations",
        "pdf_file_identity_exactness_rule",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            counts = row["counts"]
            writer.writerow(
                {
                    "variant_name": row["variant_name"],
                    "accepted": row["accepted"],
                    "rejection_reasons": ";".join(row["rejection_reasons"]),
                    "total_evaluated": counts["total_evaluated"],
                    "initially_supported": counts["initially_supported"],
                    "recovered_after_loop": counts["recovered_after_loop"],
                    "wrongly_supported_count": counts["wrongly_supported_count"],
                    "unsupported_correctly_blocked_count": counts["unsupported_correctly_blocked_count"],
                    "clarification_needed_count": counts["clarification_needed_count"],
                    "hidden_xlsx_surface_attempt_count": counts["hidden_xlsx_surface_attempt_count"],
                    "pdf_file_lookup_content_mixing_attempt_count": counts["pdf_file_lookup_content_mixing_attempt_count"],
                    "diagnostic_only_evidence_blocked_count": counts["diagnostic_only_evidence_blocked_count"],
                    "citation_coverage_before": counts["citation_coverage_before"],
                    "citation_coverage_after": counts["citation_coverage_after"],
                    "average_loop_iterations": counts["average_loop_iterations"],
                    "pdf_file_identity_exactness_rule": row["pdf_file_identity_exactness_rule"],
                }
            )


def average(values: Sequence[float | int]) -> float:
    return round(sum(float(value) for value in values) / len(values), 6) if values else 0.0


def resolve_path(value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai":
        return REPO_ROOT / path
    return AI_WORKER_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
