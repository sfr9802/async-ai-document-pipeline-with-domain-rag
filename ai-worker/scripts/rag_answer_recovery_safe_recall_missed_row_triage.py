"""Report-only missed-row triage for answer recovery safe recall.

This diagnostic step analyzes the rows behind recovered loop cases, remaining
citation gaps, and correctly blocked unsupported cases. It never promotes a
policy, opens official answer denominators, mutates indexes, trains on frozen
gold, or turns diagnostic-only evidence into support.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import rag_answer_recovery_safe_recall_tuning as safe_recall  # noqa: E402
import rag_answer_recovery_report_artifacts as report_artifacts  # noqa: E402

AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent
DEFAULT_CONFIG = AI_WORKER_ROOT / "eval" / "configs" / "answer_recovery_safe_recall_missed_row_triage.yaml"

SUPPORTED = "SUPPORTED"
PDF_FILE_LOOKUP = "PDF_FILE_LOOKUP"
PDF_CONTENT = "PDF_CONTENT"
TEXT = "TEXT"
XLSX = "XLSX"
OCR_SHADOW = "OCR_SHADOW"
IDP_SHADOW = "IDP_SHADOW"
MULTIMODAL_SHADOW = "MULTIMODAL_SHADOW"
SHADOW_LANES = {OCR_SHADOW, IDP_SHADOW, MULTIMODAL_SHADOW}

CATEGORY_ORDER = [
    "SAFE_RECOVERABLE_WITH_EXISTING_EVIDENCE",
    "SAFE_RECOVERABLE_WITH_CANONICAL_LINKING",
    "INDEX_SCOPE_MISSING",
    "POLICY_BLOCKED_CORRECTLY",
    "GOLD_POLICY_REQUIRED",
    "DIAGNOSTIC_ONLY_DO_NOT_PROMOTE",
    "UNKNOWN_NEEDS_MANUAL_REVIEW",
]

HARD_IDENTITY_BLOCKS = {
    "PDF_FILE_HARD_NEGATIVE_IDENTITY",
    "PDF_FILE_IDENTITY_MISMATCH",
    "PDF_FILE_DOCUMENT_VERSION_ID_MISMATCH",
    "PDF_FILE_SOURCE_FILE_ID_MISMATCH",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = resolve_path(args.config)
    config = report_artifacts.with_reporting_overrides(
        load_config(config_path),
        report_artifacts.reporting_overrides_from_args(args),
    )
    payload = run_triage(config=config, config_path=config_path)
    write_outputs(config, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "triage_row_count": payload["counts"]["triage_row_count"],
                "safe_recovery_category_count": payload["counts"]["safe_recovery_category_count"],
                "production_promotion_ready": payload["decision"]["production_promotion_ready"],
                "official_answer_denominator_ready": payload["decision"]["official_answer_denominator_ready"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    report_artifacts.add_reporting_args(parser)
    return parser.parse_args(argv)


def run_triage(*, config: Mapping[str, Any], config_path: Path) -> dict[str, Any]:
    return run_triage_with_artifacts(config=config, config_path=config_path)


def run_triage_with_artifacts(
    *,
    config: Mapping[str, Any],
    config_path: Path,
    artifact_overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    validation_errors = validate_config(config)
    if validation_errors:
        raise ValueError("Unsafe missed-row triage config: " + "; ".join(validation_errors))

    artifacts = load_input_artifacts(config, artifact_overrides=artifact_overrides)
    expanded = artifacts["answer_sufficiency_expanded_report"]["payload"]
    case_results = expanded["case_results"]
    trace_by_case = artifacts["answer_recovery_expanded_trace"]["trace_by_case"]
    missed_by_case = {
        row["case_id"]: row
        for row in artifacts["missed_safe_recovery_analysis"].get("payload", {}).get("rows", [])
    }
    selected_variant = artifacts["safe_recall_selected_policy"].get("payload", {}).get("variant_name", "")
    excluded_sources = set(config["excluded_frozen_gold_ids"]["source_files"])
    selection_rows, excluded_frozen_rows = split_selection_rows(case_results, excluded_sources)

    triage_rows = build_triage_rows(
        case_results=case_results,
        trace_by_case=trace_by_case,
        missed_by_case=missed_by_case,
        selected_variant=selected_variant,
        excluded_sources=excluded_sources,
    )
    category_counts = category_counts_with_zeros(triage_rows)
    focus_counts = focus_group_counts(triage_rows)
    official_diff = official_registry_diff_proof()
    guardrails = build_guardrail_status(config, triage_rows, official_diff)
    status = "PASS" if guardrails["all_guardrails_preserved"] else "BLOCKED"
    safe_count = (
        category_counts["SAFE_RECOVERABLE_WITH_EXISTING_EVIDENCE"]
        + category_counts["SAFE_RECOVERABLE_WITH_CANONICAL_LINKING"]
    )

    return {
        "schema_version": "answer_recovery_safe_recall_missed_row_triage_report_v1",
        "status": status,
        "mode": config["mode"],
        "config_path": repo_relative(config_path),
        "input_artifacts": artifact_summaries(artifacts),
        "selection_policy": {
            "selected_variant": selected_variant,
            "frozen_gold_used_for_selection": False,
            "frozen_gold_used_for_training": False,
            "selection_row_count": len(selection_rows),
            "excluded_frozen_gold_row_count": len(excluded_frozen_rows),
            "excluded_frozen_gold_rows": excluded_frozen_rows,
        },
        "counts": {
            "expanded_total": len(case_results),
            "triage_row_count": len(triage_rows),
            "safe_recovery_category_count": safe_count,
            "recovered_after_loop_focus_count": focus_counts["RECOVERED_AFTER_LOOP"],
            "citation_uncovered_focus_count": focus_counts["CITATION_UNCOVERED"],
            "unsupported_correctly_blocked_focus_count": focus_counts["UNSUPPORTED_CORRECTLY_BLOCKED"],
            "category_counts": category_counts,
        },
        "guardrail_status": guardrails,
        "official_denominator_registry_diff_proof": official_diff,
        "local_db_provenance_inspection": {
            "used": False,
            "reason": config["local_db_provenance_inspection"]["reason"],
        },
        "local_llm_usage": {
            "used": False,
            "reason": "No local LLM was needed; classification is deterministic from existing artifacts.",
            "may_decide_answer_correctness": False,
            "may_decide_evidence_support": False,
            "may_decide_gold_labels": False,
        },
        "optuna_usage": {
            "used": False,
            "reason": config["optuna"]["reason"],
        },
        "decision": {
            "production_promotion_ready": False,
            "official_answer_denominator_ready": False,
            "policy_promoted": False,
            "reason": "Report-only triage found no basis to promote; safe categories remain diagnostic evidence only.",
        },
        "rows": triage_rows,
    }


def validate_config(config: Mapping[str, Any]) -> list[str]:
    errors: list[str] = report_artifacts.validate_reporting_config(config)
    if config["excluded_frozen_gold_ids"].get("use_for_selection") is not False:
        errors.append("frozen gold use_for_selection must remain false")
    if config["excluded_frozen_gold_ids"].get("use_for_training") is not False:
        errors.append("frozen gold use_for_training must remain false")
    guardrails = config["guardrail_assertions"]
    if guardrails.get("production_promotion_ready") is not False:
        errors.append("production promotion must remain false")
    if guardrails.get("official_answer_denominator_ready") is not False:
        errors.append("official answer denominator readiness must remain false")
    if guardrails.get("pdf_file_lookup_semantics") != "file_identity_only":
        errors.append("PDF FILE lookup must remain file identity only")
    for category in CATEGORY_ORDER:
        if category not in config["categories"]:
            errors.append(f"missing category {category}")
    return errors


def load_input_artifacts(
    config: Mapping[str, Any],
    artifact_overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    for name, raw_path in config["inputs"].items():
        path = resolve_path(raw_path)
        entry: dict[str, Any] = {"path": repo_relative(path), "exists": path.exists(), "bytes": 0}
        if not path.exists():
            artifacts[name] = entry
            continue
        entry["bytes"] = path.stat().st_size
        if path.suffix == ".json":
            entry["payload"] = read_json(path)
        elif path.suffix == ".csv":
            entry["rows"] = read_csv(path)
        elif path.suffix == ".jsonl":
            trace_rows = read_jsonl(path)
            entry["line_count"] = len(trace_rows)
            entry["trace_by_case"] = {row.get("case_id"): row for row in trace_rows if row.get("case_id")}
        elif path.suffix == ".md":
            entry["line_count"] = len(path.read_text(encoding="utf-8").splitlines())
        artifacts[name] = entry
    for name, override in (artifact_overrides or {}).items():
        raw_path = config.get("inputs", {}).get(name, name)
        path = resolve_path(raw_path)
        entry = {"path": repo_relative(path), "exists": True, "bytes": 0}
        entry.update(dict(override))
        artifacts[name] = entry

    required = ("answer_sufficiency_expanded_report", "answer_recovery_expanded_trace")
    missing_required = [name for name in required if not artifacts.get(name, {}).get("exists")]
    if missing_required:
        raise FileNotFoundError(f"Missing required triage inputs: {', '.join(missing_required)}")
    return artifacts


def build_triage_rows(
    *,
    case_results: Sequence[Mapping[str, Any]],
    trace_by_case: Mapping[str, Mapping[str, Any]],
    missed_by_case: Mapping[str, Mapping[str, Any]],
    selected_variant: str,
    excluded_sources: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in case_results:
        groups = row_focus_groups(row)
        if not groups:
            continue
        rows.append(
            classify_row(
                row,
                focus_groups=groups,
                trace_row=trace_by_case.get(row["case_id"], {}),
                missed_row=missed_by_case.get(row["case_id"], {}),
                selected_variant=selected_variant,
                excluded_sources=excluded_sources,
            )
        )
    return sorted(rows, key=lambda item: (item["lane"], item["row_id"]))


def row_focus_groups(row: Mapping[str, Any]) -> list[str]:
    groups: list[str] = []
    after = row["after_decision"]
    if row.get("loop_result") and after["sufficiency_status"] == SUPPORTED:
        groups.append("RECOVERED_AFTER_LOOP")
    if float(after.get("citation_coverage", 0.0)) < 1.0:
        groups.append("CITATION_UNCOVERED")
    if after["sufficiency_status"] != SUPPORTED and not bool(row.get("expected_official_support_allowed")):
        groups.append("UNSUPPORTED_CORRECTLY_BLOCKED")
    return groups


def classify_row(
    row: Mapping[str, Any],
    *,
    focus_groups: Sequence[str],
    trace_row: Mapping[str, Any],
    missed_row: Mapping[str, Any],
    selected_variant: str,
    excluded_sources: set[str],
) -> dict[str, Any]:
    before = row["before_decision"]
    after = row["after_decision"]
    blocked = set(before.get("blocked_lanes", [])) | set(after.get("blocked_lanes", []))
    lane = row["lane"]
    source_artifact = str(row.get("source_artifact", ""))
    hidden_xlsx = lane == XLSX and "XLSX_HIDDEN_CONTENT" in blocked
    pdf_file_mixing = is_pdf_file_identity_content_mixing(row, blocked)
    diagnostic_only = is_diagnostic_only(row, blocked)
    native_pdf_available = lane == PDF_CONTENT and after.get("best_trust_tier") == "NATIVE_TEXT_HIGH"
    ocr_fallback = lane == OCR_SHADOW or after.get("best_trust_tier") == "OCR_MEDIUM" or "OCR_SHADOW" in blocked
    selection_role = "excluded_frozen_gold" if source_artifact in excluded_sources else "selection_candidate"
    category = choose_category(
        row,
        focus_groups=focus_groups,
        blocked=blocked,
        hidden_xlsx=hidden_xlsx,
        pdf_file_mixing=pdf_file_mixing,
        diagnostic_only=diagnostic_only,
    )
    human_gold_required = category in {"GOLD_POLICY_REQUIRED", "UNKNOWN_NEEDS_MANUAL_REVIEW"}
    evidence_production_safe = evidence_is_production_safe(row, category, diagnostic_only, hidden_xlsx, pdf_file_mixing)
    reason = recovery_or_block_reason(row, category, blocked, missed_row)

    return {
        "row_id": row["case_id"],
        "stable_query_id": row["case_id"],
        "focus_groups": list(focus_groups),
        "lane": lane,
        "case_type": row.get("case_type", ""),
        "source_artifact": source_artifact,
        "selection_role": selection_role,
        "before_status": before.get("sufficiency_status", ""),
        "after_status": after.get("sufficiency_status", ""),
        "before_citation_coverage": before.get("citation_coverage", 0.0),
        "after_citation_coverage": after.get("citation_coverage", 0.0),
        "selected_variant": selected_variant,
        "category": category,
        "recovery_or_block_reason": reason,
        "evidence_source_type": evidence_source_type(row, after),
        "evidence_is_production_safe": evidence_production_safe,
        "evidence_is_diagnostic_only": diagnostic_only,
        "hidden_xlsx_involved": hidden_xlsx,
        "pdf_file_identity_content_mixing_risk": pdf_file_mixing,
        "native_pdf_text_available": native_pdf_available,
        "ocr_fallback_involved": ocr_fallback,
        "human_gold_decision_required": human_gold_required,
        "recommended_next_action": recommended_next_action(category, row, reason),
        "blocked_lanes": sorted(blocked),
        "failure_type": after.get("failure_type", ""),
        "loop_iterations": (row.get("loop_result") or {}).get("loop_iterations"),
        "query_rewrite_count": (row.get("loop_result") or {}).get("query_rewrite_count"),
        "trace_available": bool(trace_row),
        "diagnostic_policy": row.get("diagnostic_policy", {}),
    }


def choose_category(
    row: Mapping[str, Any],
    *,
    focus_groups: Sequence[str],
    blocked: set[str],
    hidden_xlsx: bool,
    pdf_file_mixing: bool,
    diagnostic_only: bool,
) -> str:
    lane = row["lane"]
    after = row["after_decision"]
    if diagnostic_only:
        return "DIAGNOSTIC_ONLY_DO_NOT_PROMOTE"
    if hidden_xlsx or pdf_file_mixing or blocked.intersection(HARD_IDENTITY_BLOCKS):
        return "POLICY_BLOCKED_CORRECTLY"
    if "RECOVERED_AFTER_LOOP" in focus_groups and recovered_with_existing_evidence(row):
        return "SAFE_RECOVERABLE_WITH_EXISTING_EVIDENCE"
    if lane == PDF_FILE_LOOKUP and after["sufficiency_status"] == SUPPORTED:
        return "SAFE_RECOVERABLE_WITH_CANONICAL_LINKING"
    if after.get("failure_type") in {"NEEDS_USER_CONSTRAINT", "AMBIGUOUS_QUERY"}:
        return "GOLD_POLICY_REQUIRED"
    if row.get("loop_result") and after["sufficiency_status"] != SUPPORTED:
        return "INDEX_SCOPE_MISSING"
    if after["sufficiency_status"] != SUPPORTED and not bool(row.get("expected_official_support_allowed")):
        return "POLICY_BLOCKED_CORRECTLY"
    return "UNKNOWN_NEEDS_MANUAL_REVIEW"


def recovered_with_existing_evidence(row: Mapping[str, Any]) -> bool:
    after = row["after_decision"]
    return (
        after.get("sufficiency_status") == SUPPORTED
        and int(after.get("cited_evidence_count", 0)) > 0
        and float(after.get("citation_coverage", 0.0)) >= 1.0
        and not row.get("diagnostic_policy", {}).get("promotion_evidence", False)
    )


def is_diagnostic_only(row: Mapping[str, Any], blocked: set[str]) -> bool:
    lane = row["lane"]
    return lane in SHADOW_LANES or bool(blocked.intersection(SHADOW_LANES))


def is_pdf_file_identity_content_mixing(row: Mapping[str, Any], blocked: set[str]) -> bool:
    if row["lane"] != PDF_FILE_LOOKUP:
        return False
    if row.get("case_type") == "pdf_file_lookup_content_mixing":
        return True
    return "PDF_FILE_LOOKUP" in blocked or row["after_decision"].get("failure_type") == "LANE_MISMATCH"


def evidence_source_type(row: Mapping[str, Any], after: Mapping[str, Any]) -> str:
    lane = row["lane"]
    trust = after.get("best_trust_tier", "")
    if lane == TEXT:
        return "TEXT_NATIVE"
    if lane == XLSX:
        return "XLSX_STRICT_WRAPPER" if "XLSX_HIDDEN_CONTENT" not in after.get("blocked_lanes", []) else "XLSX_HIDDEN_BLOCKED"
    if lane == PDF_CONTENT:
        return "PDF_NATIVE_TEXT" if trust == "NATIVE_TEXT_HIGH" else "PDF_CONTENT"
    if lane == PDF_FILE_LOOKUP:
        return "PDF_FILE_IDENTITY"
    if lane == OCR_SHADOW:
        return "OCR_FALLBACK_DIAGNOSTIC"
    if lane == IDP_SHADOW:
        return "IDP_DIAGNOSTIC"
    if lane == MULTIMODAL_SHADOW:
        return "MULTIMODAL_DIAGNOSTIC"
    return "UNKNOWN"


def evidence_is_production_safe(
    row: Mapping[str, Any],
    category: str,
    diagnostic_only: bool,
    hidden_xlsx: bool,
    pdf_file_mixing: bool,
) -> bool:
    after = row["after_decision"]
    return (
        category in {"SAFE_RECOVERABLE_WITH_EXISTING_EVIDENCE", "SAFE_RECOVERABLE_WITH_CANONICAL_LINKING"}
        and after.get("official_support") is True
        and not diagnostic_only
        and not hidden_xlsx
        and not pdf_file_mixing
    )


def recovery_or_block_reason(
    row: Mapping[str, Any],
    category: str,
    blocked: set[str],
    missed_row: Mapping[str, Any],
) -> str:
    if missed_row.get("do_not_recover_reason"):
        return str(missed_row["do_not_recover_reason"])
    if category == "SAFE_RECOVERABLE_WITH_EXISTING_EVIDENCE":
        return "Recovered by the existing capped loop with cited non-diagnostic evidence; remains report-only."
    if category == "SAFE_RECOVERABLE_WITH_CANONICAL_LINKING":
        return "Would require exact/canonical identity linkage evidence; no promotion is made here."
    if category == "INDEX_SCOPE_MISSING":
        return "The capped loop stopped without support; inspect retrieval/index scope only after gold policy says answerable."
    if category == "POLICY_BLOCKED_CORRECTLY":
        return "Current fail-closed policy blocks this row: " + (", ".join(sorted(blocked)) or row["after_decision"].get("failure_type", ""))
    if category == "GOLD_POLICY_REQUIRED":
        return "The row needs a human/gold policy decision or user constraint before recovery can be considered."
    if category == "DIAGNOSTIC_ONLY_DO_NOT_PROMOTE":
        return "Evidence is OCR/IDP/multimodal diagnostic-only and cannot support official answers."
    return "Insufficient deterministic signal; surface for manual review instead of promoting."


def recommended_next_action(category: str, row: Mapping[str, Any], reason: str) -> str:
    del reason
    if category == "SAFE_RECOVERABLE_WITH_EXISTING_EVIDENCE":
        return "Keep as diagnostic evidence; collect fresh non-frozen positives before any policy discussion."
    if category == "SAFE_RECOVERABLE_WITH_CANONICAL_LINKING":
        return "Verify exact/canonical identity linkage in a future report-only pass."
    if category == "INDEX_SCOPE_MISSING":
        return "Inspect scoped provenance/index availability only; do not create support from DB content."
    if category == "POLICY_BLOCKED_CORRECTLY":
        if row["lane"] == PDF_FILE_LOOKUP:
            return "Keep PDF FILE lookup file-identity-only and separate from PDF CONTENT."
        return "Keep blocked under the current guardrail."
    if category == "GOLD_POLICY_REQUIRED":
        return "Defer to user/human gold decision; do not infer labels automatically."
    if category == "DIAGNOSTIC_ONLY_DO_NOT_PROMOTE":
        return "Keep OCR/IDP/multimodal rows diagnostic-only."
    return "Manual review required; do not promote or recover automatically."


def split_selection_rows(
    case_results: Sequence[Mapping[str, Any]],
    excluded_sources: set[str],
) -> tuple[list[Mapping[str, Any]], list[dict[str, str]]]:
    selection_rows: list[Mapping[str, Any]] = []
    excluded_rows: list[dict[str, str]] = []
    for row in case_results:
        source = str(row.get("source_artifact", ""))
        if source in excluded_sources:
            excluded_rows.append(
                {
                    "case_id": str(row.get("case_id", "")),
                    "lane": str(row.get("lane", "")),
                    "case_type": str(row.get("case_type", "")),
                    "source_artifact": source,
                }
            )
        else:
            selection_rows.append(row)
    return selection_rows, excluded_rows


def build_guardrail_status(
    config: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    official_diff: Mapping[str, Any],
) -> dict[str, Any]:
    hidden_supported = sum(1 for row in rows if row["hidden_xlsx_involved"] and row["after_status"] == SUPPORTED)
    pdf_mixing_supported = sum(
        1 for row in rows if row["pdf_file_identity_content_mixing_risk"] and row["after_status"] == SUPPORTED
    )
    diagnostic_supported = sum(
        1 for row in rows if row["evidence_is_diagnostic_only"] and row["after_status"] == SUPPORTED
    )
    assertions = dict(config["guardrail_assertions"])
    status = {
        **assertions,
        "wrongly_supported_count": 0,
        "hidden_xlsx_support_count": hidden_supported,
        "pdf_file_content_mixing_support_count": pdf_mixing_supported,
        "diagnostic_only_evidence_support_count": diagnostic_supported,
        "official_denominator_registry_changed": bool(official_diff["changed"]),
        "production_promotion_ready": False,
        "official_answer_denominator_ready": False,
    }
    status["all_guardrails_preserved"] = (
        hidden_supported == 0
        and pdf_mixing_supported == 0
        and diagnostic_supported == 0
        and not official_diff["changed"]
    )
    return status


def focus_group_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for row in rows:
        counts.update(row["focus_groups"])
    return {key: counts[key] for key in ("RECOVERED_AFTER_LOOP", "CITATION_UNCOVERED", "UNSUPPORTED_CORRECTLY_BLOCKED")}


def category_counts_with_zeros(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(row["category"] for row in rows)
    return {category: counts[category] for category in CATEGORY_ORDER}


def artifact_summaries(artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for name, artifact in artifacts.items():
        summary = {key: artifact.get(key) for key in ("path", "exists", "bytes", "line_count")}
        if "payload" in artifact and isinstance(artifact["payload"], Mapping):
            summary["schema_version"] = artifact["payload"].get("schema_version")
        if "rows" in artifact:
            summary["row_count"] = len(artifact["rows"])
        if "trace_by_case" in artifact:
            summary["case_count"] = len(artifact["trace_by_case"])
        summaries[name] = {key: value for key, value in summary.items() if value is not None}
    return summaries


def write_outputs(config: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    options = report_artifacts.reporting_options(config)
    paths = config["report_paths"]
    if options["emit_stage_reports"]:
        write_json(resolve_path(paths["triage_json"]), payload)
        write_text(resolve_path(paths["triage_md"]), render_md(payload))
    if options["emit_csv"]:
        write_rows_csv(resolve_path(paths["triage_csv"]), payload["rows"])


def render_md(payload: Mapping[str, Any]) -> str:
    counts = payload["counts"]
    lines = [
        "# Answer Recovery Safe Recall Missed Row Triage",
        "",
        f"- Status: `{payload['status']}`.",
        f"- Triage rows: `{counts['triage_row_count']}`.",
        f"- Recovered-after-loop focus rows: `{counts['recovered_after_loop_focus_count']}`.",
        f"- Citation-uncovered focus rows: `{counts['citation_uncovered_focus_count']}`.",
        f"- Unsupported-correctly-blocked focus rows: `{counts['unsupported_correctly_blocked_focus_count']}`.",
        f"- Safe recovery categories found: `{counts['safe_recovery_category_count']}`.",
        "- Production promotion ready: `false`.",
        "- Official answer denominator ready: `false`.",
        "",
        "## Category Counts",
        "",
    ]
    for category, value in counts["category_counts"].items():
        lines.append(f"- {category}: `{value}`")
    lines.extend(["", "## Guardrails", ""])
    for key, value in payload["guardrail_status"].items():
        if isinstance(value, Mapping):
            compact = ", ".join(f"{subkey}={subvalue}" for subkey, subvalue in value.items())
            lines.append(f"- {key}: `{compact}`")
        else:
            lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Rows", ""])
    for row in payload["rows"]:
        groups = ",".join(row["focus_groups"])
        lines.append(
            f"- `{row['row_id']}` {row['lane']} {groups} category=`{row['category']}` "
            f"action=`{row['recommended_next_action']}`"
        )
    lines.append("")
    return "\n".join(lines)


def write_rows_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "row_id",
        "stable_query_id",
        "focus_groups",
        "lane",
        "before_status",
        "after_status",
        "selected_variant",
        "category",
        "recovery_or_block_reason",
        "evidence_source_type",
        "evidence_is_production_safe",
        "evidence_is_diagnostic_only",
        "hidden_xlsx_involved",
        "pdf_file_identity_content_mixing_risk",
        "native_pdf_text_available",
        "ocr_fallback_involved",
        "human_gold_decision_required",
        "recommended_next_action",
        "selection_role",
        "source_artifact",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: serialize_csv_value(row.get(key)) for key in fieldnames})


def serialize_csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def official_registry_diff_proof() -> dict[str, Any]:
    return safe_recall.official_registry_diff_proof()


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


def resolve_path(value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai-worker":
        return REPO_ROOT / path
    return AI_WORKER_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
