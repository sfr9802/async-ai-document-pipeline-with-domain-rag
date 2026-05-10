"""Build a report-only fresh diagnostic answer-recovery candidate pack."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent
DEFAULT_CONFIG = AI_WORKER_ROOT / "eval" / "configs" / "answer_recovery_fresh_diagnostic_candidate_discovery.yaml"

REVIEW_READY_STATUSES = {"REVIEW_READY_NON_FROZEN_DIAGNOSTIC", "REVIEW_READY_FILE_IDENTITY_ONLY"}
SHADOW_LANES = {"OCR_SHADOW", "IDP_SHADOW", "MULTIMODAL_SHADOW"}
STATUS_ORDER = [
    "REVIEW_READY_NON_FROZEN_DIAGNOSTIC",
    "REVIEW_READY_FILE_IDENTITY_ONLY",
    "SKIP_FROZEN_GOLD_DERIVED",
    "SKIP_OFFICIAL_DENOMINATOR_MEMBER",
    "SKIP_HIDDEN_XLSX",
    "SKIP_EXPECTED_ANSWER_OR_LABEL_SURFACE",
    "SKIP_PDF_FILE_CONTENT_MIXING_RISK",
    "SKIP_DIAGNOSTIC_ONLY_SHADOW",
    "SKIP_POLICY_BLOCKED",
    "SKIP_SOURCE_CONTENT_UNAVAILABLE",
    "SKIP_UNSCOPED_OR_BROAD_INDEXING_REQUIRED",
    "REVIEW_GOLD_POLICY_REQUIRED",
    "UNKNOWN_NEEDS_INVESTIGATION",
]

REVIEW_PACK_COLUMNS = [
    "candidate_id",
    "lane",
    "source_artifact_path",
    "source_row_id",
    "source_document_id",
    "document_version_id",
    "query_text",
    "query_seed",
    "retrieved_or_candidate_chunk_id",
    "citation_text_preview",
    "citation_location_json",
    "parser_version",
    "diagnostic_reason",
    "required_user_decision",
    "codex_recommended_handling",
    "exclusion_from_official_denominator",
    "promotion_evidence",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = resolve_path(args.config)
    config = load_config(config_path)
    payload = run_discovery(config=config, config_path=config_path)
    write_outputs(config, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "total_inspected": payload["counts"]["total_inspected"],
                "review_ready_count": payload["counts"]["review_ready_count"],
                "promotion_evidence": payload["guardrail_status"]["promotion_evidence"],
                "official_denominator_registry_changed": payload["guardrail_status"][
                    "official_denominator_registry_changed"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    return parser.parse_args(argv)


def run_discovery(*, config: Mapping[str, Any], config_path: Path) -> dict[str, Any]:
    validation_errors = validate_config(config)
    if validation_errors:
        raise ValueError("Unsafe fresh diagnostic candidate discovery config: " + "; ".join(validation_errors))

    artifacts = load_artifacts(config)
    triage_rows = list(artifacts["missed_row_triage"]["payload"]["rows"])
    trace_by_case = artifacts["answer_recovery_expanded_trace"]["trace_by_case"]
    expanded_by_case = {
        row["case_id"]: row
        for row in artifacts["answer_sufficiency_expanded_report"]["payload"].get("case_results", [])
        if row.get("case_id")
    }
    source_cache: dict[str, list[dict[str, str]]] = {}
    frozen_sources = {normal_path(path) for path in config["excluded_frozen_gold_ids"]["source_files"]}
    official_sources = official_denominator_paths(artifacts["official_denominator_registry"]["payload"])
    silver_manifest = {
        row.get("file_name", ""): row for row in artifacts.get("silver_manifest", {}).get("rows", [])
    }

    rows = []
    for triage in triage_rows:
        expanded = expanded_by_case.get(triage["row_id"], {})
        trace = trace_by_case.get(triage["row_id"], {})
        source_record = find_source_record(triage, expanded, source_cache)
        rows.append(
            build_candidate_row(
                triage=triage,
                expanded=expanded,
                trace=trace,
                source_record=source_record,
                frozen_sources=frozen_sources,
                official_sources=official_sources,
                silver_manifest=silver_manifest,
            )
        )

    status_counts = counts_with_zeros((row["status"] for row in rows), STATUS_ORDER)
    lane_breakdown = {
        lane: dict(Counter(row["status"] for row in rows if row["lane"] == lane))
        for lane in sorted({row["lane"] for row in rows})
    }
    official_diff = official_registry_diff_proof()
    review_rows = [row for row in rows if row["status"] in REVIEW_READY_STATUSES]
    guardrails = build_guardrail_status(config, rows, official_diff)
    status = "PASS" if guardrails["all_guardrails_preserved"] else "diagnostic_failed_guardrail_uncertain"

    return {
        "schema_version": "answer_recovery_fresh_diagnostic_candidate_discovery_report_v1",
        "status": status,
        "mode": config["mode"],
        "config_path": repo_relative(config_path),
        "input_artifacts": artifact_summaries(artifacts),
        "counts": {
            "total_inspected": len(rows),
            "review_ready_count": len(review_rows),
            "review_ready_non_frozen_diagnostic_count": status_counts["REVIEW_READY_NON_FROZEN_DIAGNOSTIC"],
            "review_ready_file_identity_only_count": status_counts["REVIEW_READY_FILE_IDENTITY_ONLY"],
            "reviewed_positive_candidate_count": 0,
            "status_counts": status_counts,
            "lane_breakdown": lane_breakdown,
        },
        "guardrail_status": guardrails,
        "official_denominator_registry_diff_proof": official_diff,
        "review_pack_path": config["report_paths"]["review_pack_csv"],
        "candidate_rows": rows,
        "review_pack_rows": [review_pack_row(row) for row in review_rows],
        "decision": {
            "creates_official_gold": False,
            "production_promotion_ready": False,
            "official_answer_denominator_ready": False,
            "promotion_evidence": False,
            "reason": "Rows are candidates for human review only; no expected answer, evidence, label, or gold policy was decided.",
        },
    }


def validate_config(config: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if config["excluded_frozen_gold_ids"].get("use_for_selection") is not False:
        errors.append("frozen gold use_for_selection must remain false")
    if config["excluded_frozen_gold_ids"].get("use_for_training") is not False:
        errors.append("frozen gold use_for_training must remain false")
    policy = config["source_content_policy"]
    for key in (
        "allow_expected_answer_as_surface",
        "allow_label_as_surface",
        "allow_hidden_xlsx",
        "allow_pdf_file_content_support",
        "allow_diagnostic_only_support",
    ):
        if policy.get(key) is not False:
            errors.append(f"{key} must remain false")
    guardrails = config["guardrail_assertions"]
    if guardrails.get("promotion_evidence") is not False:
        errors.append("promotion_evidence must remain false")
    return errors


def load_artifacts(config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
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
        elif path.suffix == ".jsonl":
            rows = read_jsonl(path)
            entry["line_count"] = len(rows)
            entry["trace_by_case"] = {row.get("case_id"): row for row in rows if row.get("case_id")}
        elif path.suffix == ".csv":
            entry["rows"] = read_csv(path)
            entry["row_count"] = len(entry["rows"])
        artifacts[name] = entry
    missing = [
        name
        for name in ("missed_row_triage", "answer_recovery_expanded_trace", "answer_sufficiency_expanded_report")
        if not artifacts.get(name, {}).get("exists")
    ]
    if missing:
        raise FileNotFoundError(f"Missing required candidate discovery inputs: {', '.join(missing)}")
    return artifacts


def build_candidate_row(
    *,
    triage: Mapping[str, Any],
    expanded: Mapping[str, Any],
    trace: Mapping[str, Any],
    source_record: Mapping[str, str],
    frozen_sources: set[str],
    official_sources: set[str],
    silver_manifest: Mapping[str, Mapping[str, str]],
) -> dict[str, Any]:
    source_artifact = str(triage.get("source_artifact") or expanded.get("source_artifact") or "")
    source_norm = normal_path(source_artifact)
    lane = str(triage.get("lane") or expanded.get("lane") or "")
    hidden = bool(triage.get("hidden_xlsx_involved"))
    diagnostic_only = lane in SHADOW_LANES or bool(triage.get("evidence_is_diagnostic_only"))
    pdf_mixing = bool(triage.get("pdf_file_identity_content_mixing_risk"))
    category = str(triage.get("category") or "")
    source_available = bool(source_record)
    candidate_id = f"fresh_diag_{triage['row_id']}"
    chunk_id = first_nonempty(
        source_record.get("expected_chunk_ids"),
        first_retrieved_chunk_id(trace),
    )
    silver_entry = silver_manifest.get(Path(source_artifact).name, {})
    official_gold = str(silver_entry.get("official_gold", "")).lower() == "true"
    denominator_role = silver_entry.get("denominator_role", "")

    status = classify_status(
        lane=lane,
        category=category,
        hidden=hidden,
        diagnostic_only=diagnostic_only,
        pdf_mixing=pdf_mixing,
        source_available=source_available,
        source_norm=source_norm,
        frozen_sources=frozen_sources,
        official_sources=official_sources,
        official_gold=official_gold,
        denominator_role=denominator_role,
    )
    review_ready = status in REVIEW_READY_STATUSES
    query = str(expanded.get("query") or source_record.get("query") or "")
    citation_preview = safe_citation_preview(source_record, hidden=hidden, diagnostic_only=diagnostic_only)

    return {
        "candidate_id": candidate_id,
        "status": status,
        "lane": lane,
        "source_artifact_path": source_artifact,
        "source_row_id": first_nonempty(source_record.get("query_id"), source_record.get("source_query_id"), triage["row_id"]),
        "source_document_id": first_nonempty(
            source_record.get("expected_document_ids"),
            source_record.get("source_document_id"),
            source_record.get("document_id"),
        ),
        "document_version_id": first_nonempty(source_record.get("document_version_id"), source_record.get("expected_page_ids")),
        "query_text": query if review_ready and not hidden else "",
        "query_seed": query if review_ready and not hidden else "",
        "retrieved_or_candidate_chunk_id": chunk_id,
        "citation_text_preview": citation_preview if review_ready else "",
        "citation_location_json": citation_location_json(source_record) if review_ready else "",
        "parser_version": first_nonempty(source_record.get("parser_version"), expanded.get("case_type")),
        "diagnostic_reason": first_nonempty(
            triage.get("recovery_or_block_reason"),
            triage.get("recommended_next_action"),
            expanded.get("route", {}).get("diagnostic_reason") if isinstance(expanded.get("route"), Mapping) else "",
        ),
        "required_user_decision": required_user_decision(status),
        "codex_recommended_handling": recommended_handling(status, lane),
        "exclusion_from_official_denominator": True,
        "promotion_evidence": False,
        "hidden_xlsx": hidden,
        "diagnostic_only": diagnostic_only,
        "pdf_file_content_mixing_risk": pdf_mixing,
        "source_content_available": source_available,
        "official_denominator_member": source_norm in official_sources or official_gold,
        "frozen_gold_derived": source_norm in frozen_sources,
        "denominator_role": denominator_role,
        "codex_decided_expected_answer": False,
        "codex_decided_expected_evidence": False,
        "codex_decided_answerability": False,
        "codex_decided_relevance": False,
        "codex_decided_gold_policy": False,
    }


def classify_status(
    *,
    lane: str,
    category: str,
    hidden: bool,
    diagnostic_only: bool,
    pdf_mixing: bool,
    source_available: bool,
    source_norm: str,
    frozen_sources: set[str],
    official_sources: set[str],
    official_gold: bool,
    denominator_role: str,
) -> str:
    if hidden:
        return "SKIP_HIDDEN_XLSX"
    if pdf_mixing:
        return "SKIP_PDF_FILE_CONTENT_MIXING_RISK"
    if diagnostic_only:
        return "SKIP_DIAGNOSTIC_ONLY_SHADOW"
    if source_norm in frozen_sources:
        return "SKIP_FROZEN_GOLD_DERIVED"
    if source_norm in official_sources or official_gold:
        return "SKIP_OFFICIAL_DENOMINATOR_MEMBER"
    if not source_available:
        return "SKIP_SOURCE_CONTENT_UNAVAILABLE"
    if category == "INDEX_SCOPE_MISSING":
        return "SKIP_UNSCOPED_OR_BROAD_INDEXING_REQUIRED"
    if category == "GOLD_POLICY_REQUIRED":
        if lane == "PDF_FILE_LOOKUP" and denominator_role == "TUNING_ONLY":
            return "REVIEW_READY_FILE_IDENTITY_ONLY"
        return "REVIEW_GOLD_POLICY_REQUIRED"
    if category == "SAFE_RECOVERABLE_WITH_EXISTING_EVIDENCE":
        if lane == "PDF_FILE_LOOKUP":
            return "REVIEW_READY_FILE_IDENTITY_ONLY"
        return "REVIEW_READY_NON_FROZEN_DIAGNOSTIC"
    if category == "SAFE_RECOVERABLE_WITH_CANONICAL_LINKING":
        return "REVIEW_GOLD_POLICY_REQUIRED"
    if category == "POLICY_BLOCKED_CORRECTLY":
        return "SKIP_POLICY_BLOCKED"
    return "UNKNOWN_NEEDS_INVESTIGATION"


def find_source_record(
    triage: Mapping[str, Any],
    expanded: Mapping[str, Any],
    source_cache: dict[str, list[dict[str, str]]],
) -> dict[str, str]:
    source_artifact = str(triage.get("source_artifact") or expanded.get("source_artifact") or "")
    if not source_artifact or not source_artifact.endswith(".csv"):
        return {}
    path = resolve_path(source_artifact)
    if not path.exists():
        return {}
    rows = source_cache.setdefault(source_artifact, read_csv(path))
    query = str(expanded.get("query") or "")
    stable_id = str(triage.get("stable_query_id") or triage.get("row_id") or "")
    for row in rows:
        if query and row.get("query") == query:
            return row
    for row in rows:
        if stable_id and stable_id in {row.get("query_id", ""), row.get("source_query_id", "")}:
            return row
    return {}


def safe_citation_preview(source_record: Mapping[str, str], *, hidden: bool, diagnostic_only: bool) -> str:
    if hidden or diagnostic_only:
        return ""
    text = first_nonempty(
        source_record.get("source_evidence_quote"),
        source_record.get("evidence_summary"),
        source_record.get("citation_text_preview"),
    )
    return text[:240]


def citation_location_json(source_record: Mapping[str, str]) -> str:
    locator = {
        key: source_record.get(key, "")
        for key in (
            "expected_document_ids",
            "expected_page_ids",
            "expected_section_path",
            "expected_chunk_ids",
            "document_version_id",
        )
        if source_record.get(key)
    }
    return json.dumps(locator, ensure_ascii=False, sort_keys=True) if locator else ""


def required_user_decision(status: str) -> str:
    if status in REVIEW_READY_STATUSES or status == "REVIEW_GOLD_POLICY_REQUIRED":
        return (
            "gold candidate inclusion; expected answer; expected evidence; relevance label; "
            "answerability label; gold policy decision"
        )
    return "none"


def recommended_handling(status: str, lane: str) -> str:
    if status == "REVIEW_READY_FILE_IDENTITY_ONLY":
        return "Review as PDF FILE identity only; do not treat as content/page/bbox/table/row/column/value support."
    if status == "REVIEW_READY_NON_FROZEN_DIAGNOSTIC":
        return "Review as non-frozen diagnostic candidate; keep out of official denominator until human decisions exist."
    if status == "REVIEW_GOLD_POLICY_REQUIRED":
        return "Defer to human gold and policy review before any use."
    if lane in SHADOW_LANES:
        return "Keep diagnostic-only shadow lane non-support-eligible."
    return "Do not include in review pack under current guardrails."


def review_pack_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {column: row.get(column, "") for column in REVIEW_PACK_COLUMNS}


def build_guardrail_status(
    config: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    official_diff: Mapping[str, Any],
) -> dict[str, Any]:
    assertions = dict(config["guardrail_assertions"])
    review_rows = [row for row in rows if row["status"] in REVIEW_READY_STATUSES]
    assertions.update(
        {
            "official_denominator_registry_changed": bool(official_diff["changed"]),
            "official_answer_denominator_opened": False,
            "production_index_mutation": False,
            "broad_indexing": False,
            "vector_write_attempted": False,
            "namespace_created": False,
            "hidden_xlsx_support_eligible_count": sum(1 for row in review_rows if row["hidden_xlsx"]),
            "pdf_file_content_mixing_support_eligible_count": sum(
                1 for row in review_rows if row["pdf_file_content_mixing_risk"]
            ),
            "diagnostic_only_support_eligible_count": sum(1 for row in review_rows if row["diagnostic_only"]),
            "promotion_evidence": False,
            "production_promotion_ready": False,
            "official_answer_denominator_ready": False,
            "hidden_xlsx_content_surfaced": False,
        }
    )
    assertions["all_guardrails_preserved"] = (
        not assertions["official_denominator_registry_changed"]
        and assertions["hidden_xlsx_support_eligible_count"] == 0
        and assertions["pdf_file_content_mixing_support_eligible_count"] == 0
        and assertions["diagnostic_only_support_eligible_count"] == 0
        and assertions["expected_answer_or_label_embedding_count"] == 0
        and assertions["frozen_gold_training_rows"] == 0
        and assertions["promotion_evidence"] is False
        and assertions["per_trial_llm_steering"] is False
        and assertions["llm_as_objective"] is False
        and assertions["mid_round_search_space_mutation"] is False
        and assertions["raw_data_exposed_to_llm_analyst"] is False
    )
    return assertions


def official_denominator_paths(registry: Mapping[str, Any]) -> set[str]:
    paths: set[str] = set()
    for entry in (registry.get("official_diagnostic_denominators") or {}).values():
        for key in ("path", "official_positive_subset_path", "official_positive_retrieval_subset_path"):
            if entry.get(key):
                paths.add(normal_path(entry[key]))
    return paths


def counts_with_zeros(values: Any, order: list[str]) -> dict[str, int]:
    counts = Counter(values)
    return {key: int(counts.get(key, 0)) for key in order}


def write_outputs(config: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    paths = config["report_paths"]
    write_json(resolve_path(paths["discovery_json"]), payload)
    write_text(resolve_path(paths["discovery_md"]), render_md(payload))
    write_csv(resolve_path(paths["review_pack_csv"]), payload["review_pack_rows"], REVIEW_PACK_COLUMNS)


def render_md(payload: Mapping[str, Any]) -> str:
    counts = payload["counts"]
    lines = [
        "# Answer Recovery Fresh Diagnostic Candidate Discovery",
        "",
        f"- Status: `{payload['status']}`.",
        "- Scope: report-only candidate discovery; no official gold creation, no denominator opening, no index mutation.",
        f"- Total inspected: `{counts['total_inspected']}`.",
        f"- Review-ready: `{counts['review_ready_count']}`.",
        f"- Reviewed positive candidates: `{counts['reviewed_positive_candidate_count']}`.",
        f"- Review pack: `{payload['review_pack_path']}`.",
        "",
        "## Status Counts",
        "",
    ]
    for key, value in counts["status_counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Guardrails", ""])
    for key, value in payload["guardrail_status"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## User Review Boundary", ""])
    lines.append(
        "- User review is limited to gold candidate inclusion, expected answer, expected evidence, relevance, answerability, and policy decisions."
    )
    return "\n".join(lines) + "\n"


def artifact_summaries(artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    summary = {}
    for name, entry in artifacts.items():
        summary[name] = {key: value for key, value in entry.items() if key not in {"payload", "rows", "trace_by_case"}}
    return summary


def official_registry_diff_proof() -> dict[str, Any]:
    rel = "ai-worker/eval/eval_queries/official_denominator_registry.json"
    unstaged = subprocess.run(["git", "diff", "--quiet", "--", rel], cwd=REPO_ROOT, text=True, capture_output=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", rel],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    changed = unstaged.returncode != 0 or staged.returncode != 0
    return {
        "path": rel,
        "command": f"git diff --quiet -- {rel}; git diff --cached --quiet -- {rel}",
        "changed": changed,
        "unstaged_diff_empty": unstaged.returncode == 0,
        "staged_diff_empty": staged.returncode == 0,
        "diff_empty": not changed,
        "diff_stdout_bytes": len(unstaged.stdout or "") + len(staged.stdout or ""),
    }


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: list[Mapping[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: serialize_csv_value(row.get(column, "")) for column in columns})


def serialize_csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return str(value).lower()
    return value


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


def normal_path(value: str) -> str:
    return value.replace("\\", "/").strip()


def first_nonempty(*values: Any) -> str:
    for value in values:
        if value:
            return str(value)
    return ""


def first_retrieved_chunk_id(trace: Mapping[str, Any]) -> str:
    loop = trace.get("loop_result") if isinstance(trace, Mapping) else {}
    for item in (loop or {}).get("trace", []) if isinstance(loop, Mapping) else []:
        chunks = item.get("retrieved_chunk_ids") or []
        if chunks:
            return str(chunks[0])
    return ""


if __name__ == "__main__":
    sys.exit(main())
