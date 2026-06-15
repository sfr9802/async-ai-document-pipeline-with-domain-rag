"""Estimate Phase 2 review unlocks before collecting more RAG/OCR data.

This report-only script reads the Phase 1 license/readiness outputs and emits
companion artifacts for Phase 2A-2. It does not touch source manifests,
official denominators, production indexes, namespaces, or vector stores.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent

DEFAULT_ENRICHED_CSV = (
    AI_WORKER_ROOT
    / "eval"
    / "review"
    / "retrieval_dataset_supplementation"
    / "existing_manifest_license_enriched.csv"
)
DEFAULT_REVIEW_REQUIRED_CSV = (
    AI_WORKER_ROOT
    / "eval"
    / "review"
    / "retrieval_dataset_supplementation"
    / "license_review_required_rows.csv"
)
DEFAULT_REPORTS_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
DEFAULT_DOCS_DIR = REPO_ROOT / "docs"
DEFAULT_OUTPUT_DIR = REPO_ROOT / ".tmp" / "phase2-review-unlock"
OFFICIAL_DENOMINATOR_REGISTRY = AI_WORKER_ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"

RETRIEVAL_CORE_LANES = {"TEXT_NAMU", "XLSX", "PDF_CONTENT"}
VISUAL_SHADOW_LANES = {
    "OCR_IMAGE",
    "OCR_ANNOTATION",
    "MULTIMODAL_IMAGE",
    "MULTIMODAL_ANNOTATION",
    "OCR_SHADOW",
    "IMAGE_ARCHIVE",
}

TARGET_READINESS = 0.80

UNSAFE_LICENSE_STATUSES = {
    "UNKNOWN_NEEDS_REVIEW",
    "SOURCE_TERMS_FOUND_BUT_AMBIGUOUS",
    "SOURCE_LICENSE_NOT_FOUND",
    "DOWNLOAD_URL_ONLY_NO_TERMS",
    "LICENSE_INFERRED_FROM_CATALOG_BUT_UNVERIFIED",
    "LICENSE_CONFLICT",
}

OPEN_LICENSE_STATUSES = {
    "VERIFIED_KOGL_TYPE_1",
    "VERIFIED_OPEN_PUBLIC_DATA",
    "VERIFIED_OPEN_LICENSE",
    "VERIFIED_ATTRIBUTION_REQUIRED",
}

NONCOMMERCIAL_STATUSES = {
    "VERIFIED_NONCOMMERCIAL_ONLY",
    "VERIFIED_KOGL_TYPE_2_NONCOMMERCIAL",
    "VERIFIED_KOGL_TYPE_4_NONCOMMERCIAL_NO_DERIVATIVES",
}

REPORT_OUTPUTS = {
    "estimate_md": "phase2_review_unlock_estimate.md",
    "estimate_json": "phase2_review_unlock_estimate.json",
    "review_priority_csv": "phase2_review_priority_matrix.csv",
    "collection_priority_csv": "phase2_collection_priority_matrix.csv",
    "denominator_risk_md": "phase2_denominator_risk_report.md",
    "retrieval_breakdown_csv": "phase2_rag_retrieval_core_breakdown.csv",
    "visual_breakdown_csv": "phase2_visual_shadow_breakdown.csv",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enriched-csv", type=Path, default=DEFAULT_ENRICHED_CSV)
    parser.add_argument("--review-required-csv", type=Path, default=DEFAULT_REVIEW_REQUIRED_CSV)
    parser.add_argument(
        "--readiness-md",
        type=Path,
        default=DEFAULT_REPORTS_DIR / "existing_manifest_experiment_readiness.md",
    )
    parser.add_argument(
        "--summary-by-source-md",
        type=Path,
        default=DEFAULT_REPORTS_DIR / "existing_manifest_license_summary_by_source.md",
    )
    parser.add_argument(
        "--usage-gate-md",
        type=Path,
        default=DEFAULT_REPORTS_DIR / "existing_manifest_license_usage_gate.md",
    )
    parser.add_argument("--phase1-dir", type=Path, default=DEFAULT_DOCS_DIR)
    parser.add_argument("--out-dir", "--output-dir", dest="output_dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--target-readiness", type=float, default=TARGET_READINESS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_estimator(
        enriched_csv=args.enriched_csv,
        review_required_csv=args.review_required_csv,
        readiness_md=args.readiness_md,
        summary_by_source_md=args.summary_by_source_md,
        usage_gate_md=args.usage_gate_md,
        phase1_dir=args.phase1_dir,
        output_dir=args.output_dir,
        target_readiness=args.target_readiness,
    )
    write_outputs(args.output_dir, payload)


def run_estimator(
    *,
    enriched_csv: Path = DEFAULT_ENRICHED_CSV,
    review_required_csv: Path = DEFAULT_REVIEW_REQUIRED_CSV,
    readiness_md: Path = DEFAULT_REPORTS_DIR / "existing_manifest_experiment_readiness.md",
    summary_by_source_md: Path = DEFAULT_REPORTS_DIR / "existing_manifest_license_summary_by_source.md",
    usage_gate_md: Path = DEFAULT_REPORTS_DIR / "existing_manifest_license_usage_gate.md",
    phase1_dir: Path = DEFAULT_DOCS_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    target_readiness: float = TARGET_READINESS,
) -> dict[str, Any]:
    enriched_csv = enriched_csv.resolve()
    review_required_csv = review_required_csv.resolve()
    readiness_md = readiness_md.resolve()
    summary_by_source_md = summary_by_source_md.resolve()
    usage_gate_md = usage_gate_md.resolve()
    phase1_dir = phase1_dir.resolve()
    output_dir = output_dir.resolve()

    rows = read_csv_rows(enriched_csv)
    review_rows = read_csv_rows(review_required_csv)
    required_markdown = {
        "existing_manifest_experiment_readiness.md": read_text(readiness_md),
        "existing_manifest_license_summary_by_source.md": read_text(summary_by_source_md),
        "existing_manifest_license_usage_gate.md": read_text(usage_gate_md),
    }
    phase1_inputs = read_phase1_inputs(phase1_dir)

    review_row_ids = {row.get("row_id", "") for row in review_rows if row.get("row_id")}

    retrieval_scope = build_scope(
        "rag_retrieval_core",
        rows,
        lanes=RETRIEVAL_CORE_LANES,
        target_readiness=target_readiness,
        review_row_ids=review_row_ids,
    )
    visual_scope = build_scope(
        "visual_shadow",
        rows,
        lanes=VISUAL_SHADOW_LANES,
        target_readiness=target_readiness,
        review_row_ids=review_row_ids,
    )

    family_summaries = build_source_family_summaries(
        rows,
        retrieval_scope=retrieval_scope,
        visual_scope=visual_scope,
        target_readiness=target_readiness,
    )

    guardrails = build_guardrail_status(rows)
    denominator_risks = build_denominator_risks(retrieval_scope, visual_scope, family_summaries)
    readiness_delta = build_readiness_delta(retrieval_scope, visual_scope, family_summaries)
    new_collection = build_new_collection_summary(retrieval_scope, visual_scope, family_summaries)
    derived_views = build_derived_readiness_views(
        retrieval_scope=retrieval_scope,
        visual_scope=visual_scope,
        target_readiness=target_readiness,
    )

    output_paths = {key: display_path(output_dir / name) for key, name in REPORT_OUTPUTS.items()}

    return {
        "schema_version": "rag_phase2_review_unlock_estimate_v1",
        "task": "phase2a_2_review_unlock_estimate_and_license_first_collection_prioritization",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "mode": "diagnostic_report_only",
        "target_readiness": target_readiness,
        "files_read": build_file_inventory(
            [
                enriched_csv,
                review_required_csv,
                readiness_md,
                summary_by_source_md,
                usage_gate_md,
                *phase1_inputs.values(),
            ]
        ),
        "required_markdown_inputs": {
            name: {"chars": len(text), "present": bool(text)} for name, text in required_markdown.items()
        },
        "phase1_inputs": {name: display_path(path) for name, path in phase1_inputs.items()},
        "outputs": output_paths,
        "scope_definitions": {
            "rag_retrieval_core": {
                "lanes": sorted(RETRIEVAL_CORE_LANES),
                "lane_mapping_status": retrieval_scope["lane_mapping_status"],
            },
            "visual_shadow": {
                "lanes": sorted(VISUAL_SHADOW_LANES),
                "lane_mapping_status": visual_scope["lane_mapping_status"],
            },
        },
        "denominators": {
            "rag_retrieval_core": retrieval_scope["denominators"],
            "visual_shadow": visual_scope["denominators"],
        },
        "breakdowns": {
            "rag_retrieval_core": retrieval_scope["breakdown"],
            "visual_shadow": visual_scope["breakdown"],
        },
        "source_family_priorities": family_summaries,
        "review_unlock_summary": readiness_delta,
        "new_collection_summary": new_collection,
        "derived_readiness_views": derived_views,
        "denominator_risks": denominator_risks,
        "guardrail_status": guardrails,
    }


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def read_phase1_inputs(phase1_dir: Path) -> dict[str, Path]:
    required = [
        "phase1_visual_shadow_source_summary.csv",
        "phase1_review_license_status_summary.csv",
        "phase1_retrieval_core_source_summary.csv",
        "phase1_lane_readiness_summary.csv",
        "phase1_source_family_readiness_summary.csv",
        "phase1_csv_reanalysis.md",
    ]
    found: dict[str, Path] = {}
    for filename in required:
        path = phase1_dir / filename
        if not path.exists():
            raise FileNotFoundError(path)
        if path.suffix == ".csv":
            read_csv_rows(path)
        else:
            read_text(path)
        found[filename] = path.resolve()
    return found


def build_file_inventory(paths: Sequence[Path]) -> list[dict[str, Any]]:
    inventory = []
    for path in paths:
        inventory.append(
            {
                "path": str(path.relative_to(REPO_ROOT)) if is_relative_to(path, REPO_ROOT) else str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return inventory


def display_path(path: Path) -> str:
    path = path.resolve()
    return str(path.relative_to(REPO_ROOT)) if is_relative_to(path, REPO_ROOT) else str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def canonical_key(row: Mapping[str, str]) -> str:
    return (
        row.get("canonical_row_id")
        or row.get("sha256")
        or row.get("row_id")
        or row.get("relative_path")
        or json.dumps(dict(row), sort_keys=True)
    )


def source_family(row: Mapping[str, str]) -> str:
    return (row.get("source_family_id") or "UNKNOWN_SOURCE").strip() or "UNKNOWN_SOURCE"


def lane(row: Mapping[str, str]) -> str:
    return (row.get("lane") or "UNKNOWN").strip() or "UNKNOWN"


def build_scope(
    name: str,
    rows: Sequence[dict[str, str]],
    *,
    lanes: set[str],
    target_readiness: float,
    review_row_ids: set[str],
) -> dict[str, Any]:
    scoped_rows = [row for row in rows if lane(row) in lanes]
    grouped = group_by_canonical(scoped_rows)
    metric_fields = {
        "internal_eval_allowed": "internal_eval_allowed",
        "embedding_allowed": "embedding_allowed",
        "vector_db_internal_allowed": "vector_db_internal_allowed",
        "ocr_or_vlm_allowed": "ocr_or_vlm_allowed",
        "parser_smoke_required": "parser_smoke_required",
        "public_release_allowed": "public_release_allowed",
        "support_eligible": "support_eligible",
        "gold_candidate_allowed": "gold_candidate_allowed",
    }

    row_level = build_level_counts(scoped_rows, grouped, metric_fields, target_readiness, "row")
    canonical_level = build_level_counts(scoped_rows, grouped, metric_fields, target_readiness, "canonical")
    row_level["review_required"] = sum(is_review_required(row, review_row_ids) for row in scoped_rows)
    canonical_level["review_required"] = sum(
        any(is_review_required(row, review_row_ids) for row in group) for group in grouped.values()
    )

    breakdown = build_scope_breakdown(scoped_rows, lanes, target_readiness, review_row_ids)
    observed_lanes = sorted({lane(row) for row in scoped_rows})

    return {
        "name": name,
        "lanes": sorted(lanes),
        "rows": scoped_rows,
        "canonical_groups": grouped,
        "lane_mapping_status": "detected" if set(observed_lanes) == lanes else "detected_with_missing_or_extra_lanes",
        "observed_lanes": observed_lanes,
        "denominators": {
            "row_level": row_level,
            "canonical_level": canonical_level,
        },
        "breakdown": breakdown,
    }


def group_by_canonical(rows: Sequence[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[canonical_key(row)].append(row)
    return dict(grouped)


def build_level_counts(
    scoped_rows: Sequence[dict[str, str]],
    grouped: Mapping[str, Sequence[dict[str, str]]],
    metric_fields: Mapping[str, str],
    target_readiness: float,
    level: str,
) -> dict[str, Any]:
    if level == "row":
        denominator = len(scoped_rows)
        metric_counts = {name: count_rows(scoped_rows, name) for name in metric_fields}
    else:
        denominator = len(grouped)
        metric_counts = {
            name: sum(any(metric_value(row, name) for row in group) for group in grouped.values())
            for name in metric_fields
        }

    vector_count = metric_counts["vector_db_internal_allowed"]
    return {
        "basis": "raw_row" if level == "row" else "canonical_row_id",
        "denominator": denominator,
        "metrics": {
            name: {
                "numerator": count,
                "rate": safe_rate(count, denominator),
                "target": target_readiness if name == "vector_db_internal_allowed" else None,
            }
            for name, count in metric_counts.items()
        },
        "vector_readiness": build_target_estimate(vector_count, denominator, target_readiness),
    }


def metric_value(row: Mapping[str, str], metric: str) -> bool:
    if metric == "ocr_or_vlm_allowed":
        return raw_metric_value(row, metric)
    if metric == "vector_db_internal_allowed":
        return raw_metric_value(row, metric) and not unsafe_license(row)
    if metric in {"public_release_allowed", "support_eligible", "gold_candidate_allowed"}:
        return raw_metric_value(row, metric) and promotion_safe(row)
    return raw_metric_value(row, metric)


def raw_metric_value(row: Mapping[str, str], metric: str) -> bool:
    if metric == "ocr_or_vlm_allowed":
        return as_bool(row.get("ocr_processing_allowed")) or as_bool(row.get("vlm_processing_allowed"))
    return as_bool(row.get(metric))


def count_rows(rows: Iterable[Mapping[str, str]], metric: str) -> int:
    return sum(metric_value(row, metric) for row in rows)


def raw_count_rows(rows: Iterable[Mapping[str, str]], metric: str) -> int:
    return sum(raw_metric_value(row, metric) for row in rows)


def safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def nullable_rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return safe_rate(numerator, denominator)


def build_target_estimate(numerator: int, denominator: int, target_readiness: float) -> dict[str, Any]:
    existing_needed = max(0, math.ceil((target_readiness * denominator) - numerator - 1e-12))
    if target_readiness >= 1:
        all_qualified_new_needed = None
    else:
        all_qualified_new_needed = max(
            0,
            math.ceil(((target_readiness * denominator) - numerator) / (1 - target_readiness) - 1e-12),
        )
    return {
        "current_numerator": numerator,
        "current_denominator": denominator,
        "current_rate": safe_rate(numerator, denominator),
        "target": target_readiness,
        "existing_units_to_promote_for_target": existing_needed,
        "new_all_qualified_units_needed_if_denominator_grows": all_qualified_new_needed,
        "adding_unqualified_units_worsens_rate": denominator > 0 and numerator > 0,
    }


def build_scope_breakdown(
    scoped_rows: Sequence[dict[str, str]],
    lanes: set[str],
    target_readiness: float,
    review_row_ids: set[str],
) -> list[dict[str, Any]]:
    by_family: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in scoped_rows:
        by_family[source_family(row)].append(row)

    breakdown = []
    for family, family_rows in sorted(by_family.items()):
        grouped = group_by_canonical(family_rows)
        classification = classify_source_family(family, family_rows)
        review_unlock_rows = count_conditional_review_unlock(family_rows, classification, review_row_ids, "row")
        review_unlock_canonical = count_conditional_review_unlock(
            family_rows, classification, review_row_ids, "canonical"
        )
        breakdown.append(
            {
                "source_family_id": family,
                "classification": classification.kind,
                "policy_posture": classification.policy_posture,
                "lanes": "|".join(sorted({lane(row) for row in family_rows})),
                "rows": len(family_rows),
                "canonical_rows": len(grouped),
                "review_required_rows": sum(is_review_required(row, review_row_ids) for row in family_rows),
                "review_required_canonical_rows": sum(
                    any(is_review_required(row, review_row_ids) for row in group) for group in grouped.values()
                ),
                "internal_eval_allowed_rows": count_rows(family_rows, "internal_eval_allowed"),
                "internal_eval_allowed_canonical_rows": count_canonical(grouped, "internal_eval_allowed"),
                "embedding_allowed_rows": count_rows(family_rows, "embedding_allowed"),
                "embedding_allowed_canonical_rows": count_canonical(grouped, "embedding_allowed"),
                "vector_db_internal_allowed_rows": count_rows(family_rows, "vector_db_internal_allowed"),
                "vector_db_internal_allowed_canonical_rows": count_canonical(grouped, "vector_db_internal_allowed"),
                "ocr_or_vlm_allowed_rows": count_rows(family_rows, "ocr_or_vlm_allowed"),
                "ocr_or_vlm_allowed_canonical_rows": count_canonical(grouped, "ocr_or_vlm_allowed"),
                "parser_smoke_required_rows": count_rows(family_rows, "parser_smoke_required"),
                "parser_smoke_required_canonical_rows": count_canonical(grouped, "parser_smoke_required"),
                "public_release_allowed_rows": count_rows(family_rows, "public_release_allowed"),
                "support_eligible_rows": count_rows(family_rows, "support_eligible"),
                "gold_candidate_allowed_rows": count_rows(family_rows, "gold_candidate_allowed"),
                "conditional_review_unlock_vector_rows": review_unlock_rows,
                "conditional_review_unlock_vector_canonical_rows": review_unlock_canonical,
                "target": target_readiness,
                "risk_flags": "|".join(classification.risk_flags),
                "required_evidence": classification.required_evidence,
                "recommendation": classification.recommendation,
            }
        )
    return breakdown


def count_canonical(grouped: Mapping[str, Sequence[dict[str, str]]], metric: str) -> int:
    return sum(any(metric_value(row, metric) for row in group) for group in grouped.values())


def is_review_required(row: Mapping[str, str], review_row_ids: set[str]) -> bool:
    return as_bool(row.get("requires_user_license_review")) or row.get("row_id") in review_row_ids


@dataclass(frozen=True)
class Classification:
    kind: str
    policy_posture: str
    risk_flags: tuple[str, ...]
    required_evidence: str
    recommendation: str
    review_unlock_candidate: bool
    collection_order: int


def classify_source_family(family: str, rows: Sequence[Mapping[str, str]]) -> Classification:
    family_upper = family.upper()
    statuses = {row.get("license_status", "") for row in rows}
    domains = {row.get("source_domain", "") for row in rows}
    license_text = " ".join(
        " ".join(
            [
                row.get("license_notes", ""),
                row.get("license_name", ""),
                row.get("license_type_code", ""),
                row.get("source_page", ""),
                row.get("relative_path", ""),
            ]
        )
        for row in rows
    ).lower()
    has_review = any(as_bool(row.get("requires_user_license_review")) for row in rows)
    has_item_level_evidence = any(item_level_evidence_captured(row) for row in rows)
    has_open_verified = any(row.get("license_status") in OPEN_LICENSE_STATUSES for row in rows)
    all_open_unreviewed = all(row.get("license_status") in OPEN_LICENSE_STATUSES for row in rows) and not has_review

    if family_upper in {"PUBLIC_DATA_PORTAL", "SEOUL_OPEN_DATA"} or domains & {
        "www.data.go.kr",
        "data.seoul.go.kr",
    }:
        if has_item_level_evidence and all_open_unreviewed:
            return Classification(
                "COLLECT_NOW",
                "ITEM_LEVEL_PUBLIC_DATA_LICENSE_CAPTURED",
                (),
                "Keep item-level 이용허락범위, KOGL, or equivalent catalog license evidence attached per row.",
                "Collect narrowly from public-data rows whose item-level license evidence is captured.",
                False,
                20,
            )
        return Classification(
            "REVIEW_FIRST",
            "ITEM_LEVEL_PUBLIC_DATA_LICENSE_REQUIRED",
            ("catalog_license_inferred_not_row_level", "new_unreviewed_collection_worsens_denominator"),
            "Capture item-level 이용허락범위, KOGL, or equivalent catalog license evidence per row.",
            "Review existing data.go.kr/Seoul rows before collecting more; collect only rows with captured item-level license fields.",
            True,
            10,
        )

    if family_upper == "KOSIS":
        if not (all_open_unreviewed and has_item_level_evidence):
            return Classification(
                "REVIEW_FIRST",
                "KOSIS_PUBLIC_DATA_EVIDENCE_INCOMPLETE",
                ("item_level_or_open_status_required",),
                "Verify KOSIS row status, excluded third-party constraints, and item-level or equivalent public-data evidence.",
                "Review KOSIS rows until they are open, unreviewed, and evidence-backed.",
                True,
                35,
            )
        return Classification(
            "COLLECT_NOW",
            "EXPLICIT_PUBLIC_DATA_TERMS_CAPTURED_COLLECTION_CONDITIONAL",
            (),
            "Keep KOSIS/public-data use-guide or row-level excluded-third-party checks attached to each new row.",
            "Collect narrowly from KOSIS or similarly explicit public-data sources while preserving item-level evidence.",
            False,
            20,
        )

    if family_upper == "FUNSD":
        return Classification(
            "DIAGNOSTIC_ONLY",
            "OCR_MM_DIAGNOSTIC_ONLY",
            ("research_only", "does_not_improve_vector_readiness"),
            "No vector/public/support promotion; keep research-only OCR/MM diagnostics internal.",
            "Use only for OCR/MM parser and diagnostic checks.",
            False,
            70,
        )

    if family_upper == "AI_HUB":
        return Classification(
            "DIAGNOSTIC_ONLY",
            "DATASET_SPECIFIC_TERMS_REQUIRED",
            ("dataset_terms_required",),
            "Capture dataset-specific terms that permit the intended use before any non-diagnostic use.",
            "Keep AI Hub rows diagnostic-only unless dataset-specific terms explicitly allow broader use.",
            False,
            75,
        )

    if family_upper == "NAMU":
        return Classification(
            "DIAGNOSTIC_ONLY",
            "NONCOMMERCIAL_LIMITED",
            ("noncommercial_overdependence", "not_public_support_or_gold_by_default"),
            "Source-family noncommercial terms are insufficient for public/support/gold promotion.",
            "Keep NAMU noncommercial-limited and prevent it from dominating gold or support denominators.",
            False,
            80,
        )

    if family_upper == "HUGGING_FACE":
        flags = ["dataset_specific_license_required"]
        if "gpl" in license_text or "chartqa" in license_text or any("GPL" in status for status in statuses):
            flags.append("chartqa_gpl_isolate_from_public_support")
        return Classification(
            "REVIEW_FIRST",
            "DATASET_SPECIFIC_LICENSE_REQUIRED",
            tuple(flags),
            "Capture dataset card license per dataset and isolate GPL/review-required rows from public/support outputs.",
            "Review dataset-specific license before expanding; do not mix GPL ChartQA rows into public/support outputs.",
            True,
            30,
        )

    if family_upper in {"PRISM", "PUBLIC_INSTITUTION"}:
        if has_item_level_evidence:
            kind = "REVIEW_FIRST"
            posture = "ITEM_LEVEL_KOGL_REVIEW_REQUIRED"
            unlock = True
            order = 40
            recommendation = "Review item-level KOGL/equivalent evidence before promotion."
        else:
            kind = "DIAGNOSTIC_ONLY"
            posture = "PARSER_SMOKE_ONLY_WITHOUT_ITEM_LICENSE"
            unlock = False
            order = 85
            recommendation = "Keep parser-smoke or diagnostic-only until item-level KOGL/equivalent evidence exists."
        return Classification(
            kind,
            posture,
            ("parser_smoke_only_without_item_level_license",),
            "Document item-level KOGL/equivalent license evidence for each promoted item.",
            recommendation,
            unlock,
            order,
        )

    if family_upper == "DART":
        return Classification(
            "REVIEW_FIRST",
            "DOCUMENT_LEVEL_RIGHTS_REQUIRED",
            ("ambiguous_document_rights",),
            "Capture document-level rights evidence for each disclosure attachment.",
            "Review DART document rights before vector/public/support use.",
            True,
            50,
        )

    if statuses & UNSAFE_LICENSE_STATUSES:
        if has_review:
            return Classification(
                "REVIEW_FIRST",
                "AMBIGUOUS_OR_MISSING_LICENSE",
                ("unsafe_license_status",),
                "Replace inferred/missing/ambiguous evidence with item-level license evidence.",
                "Review before any promotion; do not count new rows until all-qualified.",
                True,
                60,
            )
        return Classification(
            "BLOCKED_OR_DO_NOT_PROMOTE",
            "UNSAFE_LICENSE_STATUS",
            ("unsafe_license_status",),
            "Explicit item-level license evidence required.",
            "Do not promote.",
            False,
            90,
        )

    if has_open_verified and not has_review:
        return Classification(
            "COLLECT_NOW",
            "EXPLICIT_OPEN_LICENSE_CAPTURED",
            (),
            "Preserve item-level or repository license evidence and attribution metadata.",
            "Collect now for internal diagnostic/vector staging where license evidence remains attached.",
            False,
            25,
        )

    if statuses & NONCOMMERCIAL_STATUSES:
        return Classification(
            "DIAGNOSTIC_ONLY",
            "NONCOMMERCIAL_LIMITED",
            ("noncommercial_limited",),
            "Do not use for public/support/gold by default.",
            "Keep diagnostic/noncommercial-limited.",
            False,
            80,
        )

    return Classification(
        "BLOCKED_OR_DO_NOT_PROMOTE",
        "UNCLASSIFIED_LICENSE_RISK",
        ("unclassified_source_family",),
        "Explicit license evidence required.",
        "Do not promote until reviewed.",
        False,
        95,
    )


def item_level_evidence_captured(row: Mapping[str, str]) -> bool:
    method = (row.get("license_verification_method") or "").lower()
    evidence_field = (row.get("source_license_evidence_field") or "").strip()
    status = row.get("license_status", "")
    if status in UNSAFE_LICENSE_STATUSES:
        return False
    source_family_fields = {
        "configured_source_family_rule",
        "configured_source_family_terms_page",
        "configured_portal_policy_not_row_specific",
    }
    if evidence_field and evidence_field not in source_family_fields:
        return True
    return any(token in method for token in ("row", "item", "catalog_json", "dataset_card"))


def unsafe_license(row: Mapping[str, str]) -> bool:
    return row.get("license_status") in UNSAFE_LICENSE_STATUSES


def promotion_safe(row: Mapping[str, str]) -> bool:
    if unsafe_license(row):
        return False
    if source_family(row).upper() in {"NAMU", "FUNSD", "AI_HUB"}:
        return False
    return item_level_evidence_captured(row) and not as_bool(row.get("requires_user_license_review"))


def count_conditional_review_unlock(
    rows: Sequence[dict[str, str]],
    classification: Classification,
    review_row_ids: set[str],
    level: str,
) -> int:
    if not classification.review_unlock_candidate:
        return 0
    candidates = [
        row
        for row in rows
        if is_review_required(row, review_row_ids)
        and not metric_value(row, "vector_db_internal_allowed")
        and not is_diagnostic_only_family(source_family(row))
    ]
    if level == "row":
        return len(candidates)
    return len(group_by_canonical(candidates))


def is_diagnostic_only_family(family: str) -> bool:
    return family.upper() in {"FUNSD", "NAMU", "AI_HUB"}


def build_source_family_summaries(
    rows: Sequence[dict[str, str]],
    *,
    retrieval_scope: Mapping[str, Any],
    visual_scope: Mapping[str, Any],
    target_readiness: float,
) -> list[dict[str, Any]]:
    by_family: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_family[source_family(row)].append(row)

    retrieval_by_family = {entry["source_family_id"]: entry for entry in retrieval_scope["breakdown"]}
    visual_by_family = {entry["source_family_id"]: entry for entry in visual_scope["breakdown"]}

    summaries = []
    for family, family_rows in sorted(by_family.items()):
        grouped = group_by_canonical(family_rows)
        classification = classify_source_family(family, family_rows)
        retrieval = retrieval_by_family.get(family, {})
        visual = visual_by_family.get(family, {})
        summaries.append(
            {
                "source_family_id": family,
                "classification": classification.kind,
                "collection_order": classification.collection_order,
                "policy_posture": classification.policy_posture,
                "rows": len(family_rows),
                "canonical_rows": len(grouped),
                "lanes": "|".join(sorted({lane(row) for row in family_rows})),
                "license_statuses": "|".join(sorted({row.get("license_status", "") for row in family_rows})),
                "review_required_rows": sum(as_bool(row.get("requires_user_license_review")) for row in family_rows),
                "vector_db_internal_allowed_rows": count_rows(family_rows, "vector_db_internal_allowed"),
                "public_release_allowed_rows": count_rows(family_rows, "public_release_allowed"),
                "support_eligible_rows": count_rows(family_rows, "support_eligible"),
                "gold_candidate_allowed_rows": count_rows(family_rows, "gold_candidate_allowed"),
                "retrieval_core_rows": retrieval.get("rows", 0),
                "retrieval_core_canonical_rows": retrieval.get("canonical_rows", 0),
                "retrieval_core_conditional_review_unlock_rows": retrieval.get(
                    "conditional_review_unlock_vector_rows", 0
                ),
                "retrieval_core_conditional_review_unlock_canonical_rows": retrieval.get(
                    "conditional_review_unlock_vector_canonical_rows", 0
                ),
                "visual_shadow_rows": visual.get("rows", 0),
                "visual_shadow_canonical_rows": visual.get("canonical_rows", 0),
                "visual_shadow_conditional_review_unlock_rows": visual.get(
                    "conditional_review_unlock_vector_rows", 0
                ),
                "visual_shadow_conditional_review_unlock_canonical_rows": visual.get(
                    "conditional_review_unlock_vector_canonical_rows", 0
                ),
                "target": target_readiness,
                "risk_flags": "|".join(classification.risk_flags),
                "required_evidence": classification.required_evidence,
                "phase2b_recommendation": classification.recommendation,
            }
        )
    return sorted(summaries, key=lambda item: (item["collection_order"], item["source_family_id"]))


def build_readiness_delta(
    retrieval_scope: Mapping[str, Any],
    visual_scope: Mapping[str, Any],
    family_summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    retrieval_row_unlock = sum(int(item["retrieval_core_conditional_review_unlock_rows"]) for item in family_summaries)
    retrieval_canon_unlock = sum(
        int(item["retrieval_core_conditional_review_unlock_canonical_rows"]) for item in family_summaries
    )
    visual_row_unlock = sum(int(item["visual_shadow_conditional_review_unlock_rows"]) for item in family_summaries)
    visual_canon_unlock = sum(
        int(item["visual_shadow_conditional_review_unlock_canonical_rows"]) for item in family_summaries
    )

    return {
        "rag_retrieval_core": attach_unlock_to_scope(retrieval_scope, retrieval_row_unlock, retrieval_canon_unlock),
        "visual_shadow": attach_unlock_to_scope(visual_scope, visual_row_unlock, visual_canon_unlock),
        "interpretation": (
            "Existing-review unlock keeps denominators fixed. New all-qualified collection grows both numerator "
            "and denominator, so it needs many more units when the current rate is far below 0.80."
        ),
    }


def attach_unlock_to_scope(scope: Mapping[str, Any], row_unlock: int, canonical_unlock: int) -> dict[str, Any]:
    row_level = scope["denominators"]["row_level"]
    canonical_level = scope["denominators"]["canonical_level"]
    row_current = row_level["metrics"]["vector_db_internal_allowed"]["numerator"]
    row_denominator = row_level["denominator"]
    canon_current = canonical_level["metrics"]["vector_db_internal_allowed"]["numerator"]
    canon_denominator = canonical_level["denominator"]
    row_needed = row_level["vector_readiness"]["existing_units_to_promote_for_target"]
    canon_needed = canonical_level["vector_readiness"]["existing_units_to_promote_for_target"]
    return {
        "row_level": {
            "current": f"{row_current}/{row_denominator}",
            "current_rate": safe_rate(row_current, row_denominator),
            "existing_units_to_promote_for_target": row_needed,
            "conditional_existing_review_unlock_potential": row_unlock,
            "rate_after_conditional_review_unlock": safe_rate(row_current + row_unlock, row_denominator),
            "target_reachable_by_existing_review": row_unlock >= row_needed,
            "new_all_qualified_units_needed_if_denominator_grows": row_level["vector_readiness"][
                "new_all_qualified_units_needed_if_denominator_grows"
            ],
        },
        "canonical_level": {
            "current": f"{canon_current}/{canon_denominator}",
            "current_rate": safe_rate(canon_current, canon_denominator),
            "existing_units_to_promote_for_target": canon_needed,
            "conditional_existing_review_unlock_potential": canonical_unlock,
            "rate_after_conditional_review_unlock": safe_rate(canon_current + canonical_unlock, canon_denominator),
            "target_reachable_by_existing_review": canonical_unlock >= canon_needed,
            "new_all_qualified_units_needed_if_denominator_grows": canonical_level["vector_readiness"][
                "new_all_qualified_units_needed_if_denominator_grows"
            ],
        },
    }


def build_new_collection_summary(
    retrieval_scope: Mapping[str, Any],
    visual_scope: Mapping[str, Any],
    family_summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    collect_now = [item["source_family_id"] for item in family_summaries if item["classification"] == "COLLECT_NOW"]
    review_first = [item["source_family_id"] for item in family_summaries if item["classification"] == "REVIEW_FIRST"]
    diagnostic_only = [
        item["source_family_id"] for item in family_summaries if item["classification"] == "DIAGNOSTIC_ONLY"
    ]
    blocked = [
        item["source_family_id"] for item in family_summaries if item["classification"] == "BLOCKED_OR_DO_NOT_PROMOTE"
    ]
    return {
        "collect_now_sources": collect_now,
        "review_first_sources": review_first,
        "diagnostic_only_sources": diagnostic_only,
        "blocked_or_do_not_promote_sources": blocked,
        "rag_retrieval_core_new_all_qualified_needed": {
            "row_level": retrieval_scope["denominators"]["row_level"]["vector_readiness"][
                "new_all_qualified_units_needed_if_denominator_grows"
            ],
            "canonical_level": retrieval_scope["denominators"]["canonical_level"]["vector_readiness"][
                "new_all_qualified_units_needed_if_denominator_grows"
            ],
        },
        "visual_shadow_new_all_qualified_needed": {
            "row_level": visual_scope["denominators"]["row_level"]["vector_readiness"][
                "new_all_qualified_units_needed_if_denominator_grows"
            ],
            "canonical_level": visual_scope["denominators"]["canonical_level"]["vector_readiness"][
                "new_all_qualified_units_needed_if_denominator_grows"
            ],
        },
        "recommendation": (
            "Phase 2B should review high-yield existing public-data rows first, then collect only all-qualified "
            "rows with captured item-level license evidence. Unreviewed collection should stay out of denominators."
        ),
    }


def build_derived_readiness_views(
    *,
    retrieval_scope: Mapping[str, Any],
    visual_scope: Mapping[str, Any],
    target_readiness: float,
) -> dict[str, Any]:
    scopes = {
        "rag_retrieval_core": retrieval_scope,
        "visual_shadow": visual_scope,
    }
    official: dict[str, Any] = {}
    promotion: dict[str, Any] = {}
    diagnostic_drag: dict[str, list[dict[str, Any]]] = {}
    noncommercial_drag: dict[str, list[dict[str, Any]]] = {}
    parser_drag: dict[str, list[dict[str, Any]]] = {}
    warnings: list[dict[str, Any]] = []

    for scope_name, scope in scopes.items():
        official[scope_name] = build_official_view(scope, target_readiness)
        promotion[scope_name] = build_promotion_scope_view(scope, target_readiness)
        diagnostic_drag[scope_name] = build_drag_breakdown(scope, "diagnostic_or_policy_excluded")
        noncommercial_drag[scope_name] = build_drag_breakdown(scope, "noncommercial_limited")
        parser_drag[scope_name] = build_drag_breakdown(scope, "parser_smoke_only_without_item_level_evidence")
        warnings.extend(build_vector_promotion_warnings(scope, scope_name))

    return {
        "official_denominator_readiness": official,
        "promotion_scope_readiness": promotion,
        "diagnostic_drag_breakdown": diagnostic_drag,
        "noncommercial_limited_drag_breakdown": noncommercial_drag,
        "parser_smoke_only_drag_breakdown": parser_drag,
        "kosis_state": build_kosis_state([*retrieval_scope["rows"], *visual_scope["rows"]]),
        "vector_readiness_promotion_block_warnings": warnings,
        "policy_assumptions": [
            "Derived views are diagnostic/report-only and do not change official denominators.",
            "Official denominator readiness preserves the Phase 2A lane denominator basis.",
            "Promotion-scope readiness excludes diagnostic-only, noncommercial-limited, parser-smoke-only without item-level/equivalent evidence, research-only, unsafe, ambiguous, inferred-only, and missing-license rows.",
            "Conservative review unlock assumes review-first rows become all-qualified only after item-level or equivalent evidence is captured.",
        ],
    }


def build_official_view(scope: Mapping[str, Any], target_readiness: float) -> dict[str, Any]:
    row_unlock = sum(int(item["conditional_review_unlock_vector_rows"]) for item in scope["breakdown"])
    canonical_unlock = sum(int(item["conditional_review_unlock_vector_canonical_rows"]) for item in scope["breakdown"])
    return {
        "row_level": build_official_basis_view(
            scope["denominators"]["row_level"],
            row_unlock,
            target_readiness,
        ),
        "canonical_level": build_official_basis_view(
            scope["denominators"]["canonical_level"],
            canonical_unlock,
            target_readiness,
        ),
        "source_family_drag": build_source_family_drag(scope),
    }


def build_official_basis_view(
    level_counts: Mapping[str, Any],
    unlock_units: int,
    target_readiness: float,
) -> dict[str, Any]:
    numerator = int(level_counts["metrics"]["vector_db_internal_allowed"]["numerator"])
    denominator = int(level_counts["denominator"])
    after_numerator = numerator + unlock_units
    after_denominator = denominator
    return build_readiness_projection(
        numerator=numerator,
        denominator=denominator,
        unlock_units=unlock_units,
        after_numerator=after_numerator,
        after_denominator=after_denominator,
        target_readiness=target_readiness,
        denominator_policy="official_denominator_fixed",
    )


def build_promotion_scope_view(scope: Mapping[str, Any], target_readiness: float) -> dict[str, Any]:
    by_family = group_scope_rows_by_family(scope["rows"])
    family_classifications = {
        family: classify_source_family(family, family_rows) for family, family_rows in by_family.items()
    }
    row_current_denominator = count_promotion_current(scope["rows"], family_classifications, "row")
    row_current_numerator = count_promotion_current_vector(scope["rows"], family_classifications, "row")
    row_unlock = count_promotion_unlock(scope["rows"], family_classifications, "row")

    canonical_groups = scope["canonical_groups"]
    canonical_current_denominator = count_promotion_current(canonical_groups, family_classifications, "canonical")
    canonical_current_numerator = count_promotion_current_vector(canonical_groups, family_classifications, "canonical")
    canonical_unlock = count_promotion_unlock(canonical_groups, family_classifications, "canonical")

    return {
        "row_level": build_promotion_basis_view(
            row_current_numerator,
            row_current_denominator,
            row_unlock,
            target_readiness,
        ),
        "canonical_level": build_promotion_basis_view(
            canonical_current_numerator,
            canonical_current_denominator,
            canonical_unlock,
            target_readiness,
        ),
        "source_family_drag": build_source_family_drag(scope),
    }


def build_promotion_basis_view(
    numerator: int,
    denominator: int,
    unlock_units: int,
    target_readiness: float,
) -> dict[str, Any]:
    after_numerator = numerator + unlock_units
    after_denominator = denominator + unlock_units
    return build_readiness_projection(
        numerator=numerator,
        denominator=denominator,
        unlock_units=unlock_units,
        after_numerator=after_numerator,
        after_denominator=after_denominator,
        target_readiness=target_readiness,
        denominator_policy="promotion_scope_denominator_excludes_currently_blocked_rows",
    )


def build_readiness_projection(
    *,
    numerator: int,
    denominator: int,
    unlock_units: int,
    after_numerator: int,
    after_denominator: int,
    target_readiness: float,
    denominator_policy: str,
) -> dict[str, Any]:
    fixed_denominator_gap = max(0, math.ceil((target_readiness * after_denominator) - after_numerator - 1e-12))
    if target_readiness >= 1:
        new_need = None
    else:
        new_need = max(
            0,
            math.ceil(((target_readiness * after_denominator) - after_numerator) / (1 - target_readiness) - 1e-12),
        )
    current_rate_status = ""
    after_rate_status = ""
    if denominator <= 0 and denominator_policy.startswith("promotion_scope"):
        current_rate_status = "no_currently_eligible_promotion_scope_units"
    if after_denominator <= 0 and denominator_policy.startswith("promotion_scope"):
        after_rate_status = "no_eligible_promotion_scope_units_after_conservative_unlock"
    return {
        "denominator_policy": denominator_policy,
        "current_numerator": numerator,
        "current_denominator": denominator,
        "current_rate": nullable_rate(numerator, denominator),
        "current_rate_status": current_rate_status,
        "conservative_review_unlock_units": unlock_units,
        "after_conservative_unlock_numerator": after_numerator,
        "after_conservative_unlock_denominator": after_denominator,
        "after_conservative_unlock_rate": nullable_rate(after_numerator, after_denominator),
        "after_conservative_unlock_rate_status": after_rate_status,
        "fixed_denominator_remaining_gap_to_0_80_after_unlock": fixed_denominator_gap,
        "new_all_qualified_units_needed_after_conservative_unlock": new_need,
    }


def group_scope_rows_by_family(rows: Sequence[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    by_family: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_family[source_family(row)].append(row)
    return dict(by_family)


def count_promotion_current(
    units: Sequence[dict[str, str]] | Mapping[str, Sequence[dict[str, str]]],
    family_classifications: Mapping[str, Classification],
    level: str,
) -> int:
    if level == "row":
        return sum(promotion_scope_current_candidate(row, family_classifications[source_family(row)]) for row in units)  # type: ignore[arg-type]
    return sum(
        any(promotion_scope_current_candidate(row, family_classifications[source_family(row)]) for row in group)
        for group in units.values()  # type: ignore[union-attr]
    )


def count_promotion_current_vector(
    units: Sequence[dict[str, str]] | Mapping[str, Sequence[dict[str, str]]],
    family_classifications: Mapping[str, Classification],
    level: str,
) -> int:
    if level == "row":
        return sum(
            promotion_scope_current_candidate(row, family_classifications[source_family(row)])
            and metric_value(row, "vector_db_internal_allowed")
            for row in units  # type: ignore[union-attr]
        )
    return sum(
        any(
            promotion_scope_current_candidate(row, family_classifications[source_family(row)])
            and metric_value(row, "vector_db_internal_allowed")
            for row in group
        )
        for group in units.values()  # type: ignore[union-attr]
    )


def count_promotion_unlock(
    units: Sequence[dict[str, str]] | Mapping[str, Sequence[dict[str, str]]],
    family_classifications: Mapping[str, Classification],
    level: str,
) -> int:
    if level == "row":
        return sum(
            promotion_scope_review_unlock_candidate(row, family_classifications[source_family(row)])
            for row in units  # type: ignore[union-attr]
        )
    return sum(
        any(
            promotion_scope_review_unlock_candidate(row, family_classifications[source_family(row)])
            for row in group
        )
        for group in units.values()  # type: ignore[union-attr]
    )


def promotion_scope_current_candidate(row: Mapping[str, str], classification: Classification) -> bool:
    return promotion_exclusion_reason(row, classification) == ""


def promotion_scope_review_unlock_candidate(row: Mapping[str, str], classification: Classification) -> bool:
    if promotion_scope_current_candidate(row, classification):
        return False
    if not classification.review_unlock_candidate:
        return False
    if metric_value(row, "vector_db_internal_allowed"):
        return False
    if is_diagnostic_only_family(source_family(row)):
        return False
    if classification.policy_posture in {"PARSER_SMOKE_ONLY_WITHOUT_ITEM_LICENSE", "NONCOMMERCIAL_LIMITED"}:
        return False
    return True


def promotion_exclusion_reason(row: Mapping[str, str], classification: Classification) -> str:
    if classification.kind == "DIAGNOSTIC_ONLY":
        return "diagnostic_only"
    if classification.policy_posture == "NONCOMMERCIAL_LIMITED" or row.get("license_status") in NONCOMMERCIAL_STATUSES:
        return "noncommercial_limited"
    if row.get("license_status") == "VERIFIED_RESEARCH_ONLY":
        return "research_only"
    if unsafe_license(row):
        return "unsafe_or_ambiguous_or_inferred_only_license"
    if as_bool(row.get("requires_user_license_review")):
        return "review_required_until_item_level_or_equivalent_evidence"
    if raw_metric_value(row, "parser_smoke_required") and not item_level_evidence_captured(row):
        return "parser_smoke_only_without_item_level_evidence"
    return ""


def build_source_family_drag(scope: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_family = group_scope_rows_by_family(scope["rows"])
    rows: list[dict[str, Any]] = []
    for family, family_rows in sorted(by_family.items()):
        classification = classify_source_family(family, family_rows)
        grouped = group_by_canonical(family_rows)
        rows.append(
            {
                "source_family_id": family,
                "classification": classification.kind,
                "policy_posture": classification.policy_posture,
                "row_denominator_contribution": len(family_rows),
                "row_numerator_contribution": count_rows(family_rows, "vector_db_internal_allowed"),
                "row_promotion_scope_denominator": count_promotion_current(
                    family_rows, {family: classification}, "row"
                ),
                "row_promotion_scope_numerator": count_promotion_current_vector(
                    family_rows, {family: classification}, "row"
                ),
                "row_denominator_drag": len(family_rows)
                - count_promotion_current(family_rows, {family: classification}, "row"),
                "row_numerator_drag": count_rows(family_rows, "vector_db_internal_allowed")
                - count_promotion_current_vector(family_rows, {family: classification}, "row"),
                "canonical_denominator_contribution": len(grouped),
                "canonical_numerator_contribution": count_canonical(grouped, "vector_db_internal_allowed"),
                "canonical_promotion_scope_denominator": count_promotion_current(
                    grouped, {family: classification}, "canonical"
                ),
                "canonical_promotion_scope_numerator": count_promotion_current_vector(
                    grouped, {family: classification}, "canonical"
                ),
                "canonical_denominator_drag": len(grouped)
                - count_promotion_current(grouped, {family: classification}, "canonical"),
                "canonical_numerator_drag": count_canonical(grouped, "vector_db_internal_allowed")
                - count_promotion_current_vector(grouped, {family: classification}, "canonical"),
                "primary_exclusion_reason": first_exclusion_reason(family_rows, classification),
                "risk_flags": "|".join(classification.risk_flags),
            }
        )
    return rows


def build_drag_breakdown(scope: Mapping[str, Any], reason_group: str) -> list[dict[str, Any]]:
    rows = []
    for item in build_source_family_drag(scope):
        reason = str(item["primary_exclusion_reason"])
        if reason_group == "diagnostic_or_policy_excluded":
            include = item["row_denominator_drag"] > 0
        else:
            include = reason == reason_group
        if include:
            rows.append(item)
    return rows


def first_exclusion_reason(rows: Sequence[Mapping[str, str]], classification: Classification) -> str:
    reasons = [promotion_exclusion_reason(row, classification) for row in rows]
    reasons = [reason for reason in reasons if reason]
    return reasons[0] if reasons else ""


def build_vector_promotion_warnings(scope: Mapping[str, Any], scope_name: str) -> list[dict[str, Any]]:
    warnings = []
    for item in build_source_family_drag(scope):
        if item["row_numerator_contribution"] <= 0:
            continue
        if item["row_numerator_drag"] <= 0:
            continue
        warnings.append(
            {
                "scope": scope_name,
                "source_family_id": item["source_family_id"],
                "warning": "counted_in_vector_readiness_but_blocked_from_public_support_gold_promotion",
                "row_vector_numerator_drag": item["row_numerator_drag"],
                "canonical_vector_numerator_drag": item["canonical_numerator_drag"],
                "reason": item["primary_exclusion_reason"],
                "policy_posture": item["policy_posture"],
            }
        )
    return warnings


def build_kosis_state(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    kosis_rows = [row for row in rows if source_family(row).upper() == "KOSIS"]
    grouped = group_by_canonical([dict(row) for row in kosis_rows])
    evidence_levels = sorted({license_evidence_level(row) for row in kosis_rows})
    review_reasons = sorted({kosis_review_required_reason(row) for row in kosis_rows})
    return {
        "rows": len(kosis_rows),
        "canonical_rows": len(grouped),
        "vector_stage_eligible": {
            "rows": count_rows(kosis_rows, "vector_db_internal_allowed"),
            "canonical_rows": count_canonical(grouped, "vector_db_internal_allowed"),
        },
        "support_eligible": {
            "rows": count_rows(kosis_rows, "support_eligible"),
            "canonical_rows": count_canonical(grouped, "support_eligible"),
        },
        "gold_candidate_allowed": {
            "rows": count_rows(kosis_rows, "gold_candidate_allowed"),
            "canonical_rows": count_canonical(grouped, "gold_candidate_allowed"),
        },
        "license_evidence_level": "|".join(evidence_levels) if evidence_levels else "not_observed",
        "review_required_reason": "|".join(review_reasons) if review_reasons else "not_observed",
    }


def license_evidence_level(row: Mapping[str, str]) -> str:
    if item_level_evidence_captured(row):
        return "item_level_or_equivalent"
    evidence_field = (row.get("source_license_evidence_field") or "").strip()
    method = (row.get("license_verification_method") or "").strip()
    if evidence_field == "configured_source_family_rule" or method.startswith("configured_"):
        return "source_family_or_terms_page_only"
    if unsafe_license(row):
        return "unsafe_or_ambiguous_or_missing"
    return "missing_or_unclassified"


def kosis_review_required_reason(row: Mapping[str, str]) -> str:
    if source_family(row).upper() != "KOSIS":
        return "not_kosis"
    if unsafe_license(row):
        return "unsafe_or_missing_license_status"
    if license_evidence_level(row) != "item_level_or_equivalent":
        return "source_family_terms_only_requires_item_level_or_equivalent_evidence"
    if raw_metric_value(row, "parser_smoke_required") and not item_level_evidence_captured(row):
        return "parser_smoke_requires_item_level_or_equivalent_evidence"
    if as_bool(row.get("requires_user_license_review")):
        return "requires_user_license_review_true"
    return "ready_for_vector_stage_only_support_gold_still_false"


def build_denominator_risks(
    retrieval_scope: Mapping[str, Any],
    visual_scope: Mapping[str, Any],
    family_summaries: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = [
        {
            "risk": "mixed_row_and_canonical_denominator_conventions",
            "severity": "HIGH",
            "evidence": (
                "RAG retrieval core row denominator is "
                f"{retrieval_scope['denominators']['row_level']['denominator']} while canonical denominator is "
                f"{retrieval_scope['denominators']['canonical_level']['denominator']}; visual shadow row denominator is "
                f"{visual_scope['denominators']['row_level']['denominator']} while canonical denominator is "
                f"{visual_scope['denominators']['canonical_level']['denominator']}."
            ),
            "recommendation": "Report both row-level and canonical-level readiness for every Phase 2B decision.",
        },
        {
            "risk": "new_unqualified_collection_worsens_denominator_rates",
            "severity": "HIGH",
            "evidence": "Any new row added to a denominator without vector eligibility increases the denominator only.",
            "recommendation": "Do not add unreviewed rows to readiness denominators; keep them diagnostic-only.",
        },
    ]
    for item in family_summaries:
        flags = str(item.get("risk_flags", "")).split("|") if item.get("risk_flags") else []
        if "noncommercial_overdependence" in flags:
            risks.append(
                {
                    "risk": "namu_noncommercial_overdependence",
                    "severity": "HIGH",
                    "evidence": f"NAMU contributes {item['retrieval_core_rows']} retrieval-core rows.",
                    "recommendation": "Keep NAMU noncommercial-limited and out of public/support/gold denominators.",
                }
            )
        if "does_not_improve_vector_readiness" in flags:
            risks.append(
                {
                    "risk": "funsd_ocr_diagnostic_not_vector_readiness",
                    "severity": "MEDIUM",
                    "evidence": f"FUNSD contributes {item['visual_shadow_rows']} visual-shadow rows but no vector-ready rows.",
                    "recommendation": "Use FUNSD for OCR/MM diagnostics only.",
                }
            )
        if "parser_smoke_only_without_item_level_license" in flags:
            risks.append(
                {
                    "risk": f"{item['source_family_id'].lower()}_parser_smoke_only",
                    "severity": "HIGH",
                    "evidence": "Rows lack item-level KOGL/equivalent evidence.",
                    "recommendation": "Do not promote without item-level license evidence.",
                }
            )
        if "ambiguous_document_rights" in flags:
            risks.append(
                {
                    "risk": "dart_document_rights_ambiguous",
                    "severity": "HIGH",
                    "evidence": "DART rows have ambiguous source terms and no document-level rights proof.",
                    "recommendation": "Keep DART review-required until document-level rights evidence is captured.",
                }
            )
    return risks


def build_guardrail_status(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    visual_rows = [row for row in rows if lane(row) in VISUAL_SHADOW_LANES]
    unsafe_rows = [row for row in rows if row.get("license_status") in UNSAFE_LICENSE_STATUSES]
    noncommercial_rows = [row for row in rows if source_family(row).upper() == "NAMU"]
    font_rows = [row for row in rows if lane(row) == "FONT"]
    return {
        "official_denominator_registry_changed": official_denominator_changed(),
        "production_index_mutation": False,
        "production_vector_write": False,
        "namespace_created": False,
        "support_eligible_ocr_mm_count": count_rows(visual_rows, "support_eligible"),
        "annotation_answer_embedding_count": count_rows(rows, "annotation_answer_embedding_allowed"),
        "pdf_file_content_mixing_support_count": count_rows(rows, "pdf_file_content_mixing_support_allowed"),
        "hidden_xlsx_exposed": False,
        "promotion_evidence": any(as_bool(row.get("promotion_evidence")) for row in rows),
        "font_user_facing_artifact_allowed_count": raw_count_rows(font_rows, "font_user_facing_artifact_allowed"),
        "unsafe_license_effective_vector_eligible_count": count_rows(unsafe_rows, "vector_db_internal_allowed"),
        "unsafe_license_effective_public_release_count": count_rows(unsafe_rows, "public_release_allowed"),
        "unsafe_license_effective_support_eligible_count": count_rows(unsafe_rows, "support_eligible"),
        "unsafe_license_effective_gold_candidate_count": count_rows(unsafe_rows, "gold_candidate_allowed"),
        "raw_unsafe_license_vector_flag_count": raw_count_rows(unsafe_rows, "vector_db_internal_allowed"),
        "raw_unsafe_license_public_flag_count": raw_count_rows(unsafe_rows, "public_release_allowed"),
        "raw_unsafe_license_support_flag_count": raw_count_rows(unsafe_rows, "support_eligible"),
        "raw_unsafe_license_gold_flag_count": raw_count_rows(unsafe_rows, "gold_candidate_allowed"),
        "namu_public_release_allowed_count": count_rows(noncommercial_rows, "public_release_allowed"),
        "namu_support_eligible_count": count_rows(noncommercial_rows, "support_eligible"),
        "namu_gold_candidate_allowed_count": count_rows(noncommercial_rows, "gold_candidate_allowed"),
    }


def official_denominator_changed() -> bool:
    if not OFFICIAL_DENOMINATOR_REGISTRY.exists():
        return False
    result = subprocess.run(
        ["git", "diff", "--quiet", "--", str(OFFICIAL_DENOMINATOR_REGISTRY.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.returncode != 0


def write_outputs(output_dir: Path, payload: Mapping[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / REPORT_OUTPUTS["estimate_json"]).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / REPORT_OUTPUTS["estimate_md"]).write_text(render_estimate_md(payload), encoding="utf-8")
    write_csv(output_dir / REPORT_OUTPUTS["review_priority_csv"], review_priority_rows(payload))
    write_csv(output_dir / REPORT_OUTPUTS["collection_priority_csv"], collection_priority_rows(payload))
    (output_dir / REPORT_OUTPUTS["denominator_risk_md"]).write_text(
        render_denominator_risk_md(payload), encoding="utf-8"
    )
    write_csv(output_dir / REPORT_OUTPUTS["retrieval_breakdown_csv"], payload["breakdowns"]["rag_retrieval_core"])
    write_csv(output_dir / REPORT_OUTPUTS["visual_breakdown_csv"], payload["breakdowns"]["visual_shadow"])


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def review_priority_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in payload["source_family_priorities"]:
        rows.append(
            {
                "source_family_id": item["source_family_id"],
                "classification": item["classification"],
                "policy_posture": item["policy_posture"],
                "license_statuses": item["license_statuses"],
                "collection_order": item["collection_order"],
                "rows": item["rows"],
                "canonical_rows": item["canonical_rows"],
                "review_required_rows": item["review_required_rows"],
                "retrieval_core_conditional_review_unlock_rows": item[
                    "retrieval_core_conditional_review_unlock_rows"
                ],
                "retrieval_core_conditional_review_unlock_canonical_rows": item[
                    "retrieval_core_conditional_review_unlock_canonical_rows"
                ],
                "visual_shadow_conditional_review_unlock_rows": item[
                    "visual_shadow_conditional_review_unlock_rows"
                ],
                "visual_shadow_conditional_review_unlock_canonical_rows": item[
                    "visual_shadow_conditional_review_unlock_canonical_rows"
                ],
                "risk_flags": item["risk_flags"],
                "required_evidence": item["required_evidence"],
                "phase2b_recommendation": item["phase2b_recommendation"],
            }
        )
    return rows


def collection_priority_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in payload["source_family_priorities"]:
        rows.append(
            {
                "source_family_id": item["source_family_id"],
                "phase2b_collection_classification": item["classification"],
                "policy_posture": item["policy_posture"],
                "license_statuses": item["license_statuses"],
                "recommended_action": item["phase2b_recommendation"],
                "required_evidence_before_denominator": item["required_evidence"],
                "new_unreviewed_data_denominator_effect": (
                    "worsens_or_does_not_help"
                    if item["classification"] != "COLLECT_NOW"
                    else "helps_only_when_all_qualified_and_evidence_captured"
                ),
                "public_release_allowed_rows_current": item["public_release_allowed_rows"],
                "support_eligible_rows_current": item["support_eligible_rows"],
                "gold_candidate_allowed_rows_current": item["gold_candidate_allowed_rows"],
                "risk_flags": item["risk_flags"],
            }
        )
    return rows


def render_estimate_md(payload: Mapping[str, Any]) -> str:
    retrieval = payload["review_unlock_summary"]["rag_retrieval_core"]
    visual = payload["review_unlock_summary"]["visual_shadow"]
    collection = payload["new_collection_summary"]
    derived = payload.get("derived_readiness_views", {})
    lines = [
        "# Phase 2A-2 Review-Unlock Estimate",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Target readiness: `{payload['target_readiness']:.2f}`",
        "- Mode: `diagnostic_report_only`; no production index/vector/namespace mutation.",
        "",
        "## Denominator Interpretation",
        "",
        "| scope | row vector readiness | canonical vector readiness | row promote need | canonical promote need | row new all-qualified need | canonical new all-qualified need |",
        "|---|---:|---:|---:|---:|---:|---:|",
        denominator_table_row("RAG retrieval core", retrieval),
        denominator_table_row("Visual shadow", visual),
        "",
        "Both row-level and canonical-level denominators must be reported. The current Phase 1 rates mix row and canonical conventions, and new data can make a rate worse whenever it enters a denominator before it is all-qualified.",
        "",
        "## Review-Unlock Estimate",
        "",
        f"- RAG retrieval core can conditionally unlock `{retrieval['row_level']['conditional_existing_review_unlock_potential']}` existing rows / `{retrieval['canonical_level']['conditional_existing_review_unlock_potential']}` canonical rows if review produces item-level evidence.",
        f"- Visual shadow can conditionally unlock `{visual['row_level']['conditional_existing_review_unlock_potential']}` existing rows / `{visual['canonical_level']['conditional_existing_review_unlock_potential']}` canonical rows under the same conservative rule.",
        "- These are conditional estimates, not promotion decisions. Ambiguous, inferred, missing, or source-family-only evidence is not promotion evidence and stays out of public/support/gold outputs.",
        "",
        "## New-Collection Estimate",
        "",
        f"- RAG retrieval core needs `{collection['rag_retrieval_core_new_all_qualified_needed']['row_level']}` new all-qualified rows or `{collection['rag_retrieval_core_new_all_qualified_needed']['canonical_level']}` new all-qualified canonical rows if the denominator grows.",
        f"- Visual shadow needs `{collection['visual_shadow_new_all_qualified_needed']['row_level']}` new all-qualified rows or `{collection['visual_shadow_new_all_qualified_needed']['canonical_level']}` new all-qualified canonical rows if the denominator grows.",
        "- Phase 2B should therefore review high-yield existing rows first, then collect only rows whose item-level license evidence is captured before they enter readiness denominators.",
        "",
        "## Phase 2B Derived Readiness Views",
        "",
        "These views are diagnostic/report-only. Official denominator values remain unchanged; promotion-scope readiness separates rows blocked by diagnostic-only, noncommercial-limited, parser-smoke-only, research-only, unsafe, ambiguous, inferred-only, or missing-license policy.",
        "",
        "| scope | basis | official current | official after review unlock | promotion-scope current | promotion-scope after review unlock | fixed-denominator gap after unlock | new all-qualified need after unlock |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
        *derived_view_table_rows(derived),
        *promotion_scope_status_lines(derived),
        "",
        "### KOSIS State",
        "",
        *kosis_state_lines(derived),
        "",
        "### Vector Readiness Promotion-Block Warnings",
        "",
        *promotion_warning_lines(derived),
        "",
        "## Source-Family Priority",
        "",
        "| source_family_id | class | license_statuses | rows | canonical | review rows | retrieval unlock | visual unlock | notes |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in payload["source_family_priorities"]:
        lines.append(
            "| {source_family_id} | {classification} | {license_statuses} | {rows} | {canonical_rows} | {review_required_rows} | {retrieval_core_conditional_review_unlock_rows}/{retrieval_core_conditional_review_unlock_canonical_rows} | {visual_shadow_conditional_review_unlock_rows}/{visual_shadow_conditional_review_unlock_canonical_rows} | {policy_posture} |".format(
                **{**item, "license_statuses": md_table_cell(item["license_statuses"])}
            )
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
        ]
    )
    for key, value in payload["guardrail_status"].items():
        lines.append(f"- {key}: `{str(value).lower() if isinstance(value, bool) else value}`")
    return "\n".join(lines) + "\n"


def derived_view_table_rows(derived: Mapping[str, Any]) -> list[str]:
    if not derived:
        return []
    rows = []
    official = derived["official_denominator_readiness"]
    promotion = derived["promotion_scope_readiness"]
    for scope_name in ["rag_retrieval_core", "visual_shadow"]:
        for basis in ["row_level", "canonical_level"]:
            official_basis = official[scope_name][basis]
            promotion_basis = promotion[scope_name][basis]
            rows.append(
                "| {scope} | {basis} | `{official_current}` | `{official_after}` | `{promotion_current}` | `{promotion_after}` | `{gap}` | `{new_need}` |".format(
                    scope=scope_name,
                    basis=basis,
                    official_current=format_projection_cell(official_basis, "current"),
                    official_after=format_projection_cell(official_basis, "after_conservative_unlock"),
                    promotion_current=format_projection_cell(promotion_basis, "current"),
                    promotion_after=format_projection_cell(promotion_basis, "after_conservative_unlock"),
                    gap=promotion_basis["fixed_denominator_remaining_gap_to_0_80_after_unlock"],
                    new_need=promotion_basis["new_all_qualified_units_needed_after_conservative_unlock"],
                )
            )
    return rows


def md_table_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def format_projection_cell(projection: Mapping[str, Any], prefix: str) -> str:
    numerator = projection[f"{prefix}_numerator"]
    denominator = projection[f"{prefix}_denominator"]
    rate = projection[f"{prefix}_rate"]
    if rate is None:
        return f"{numerator}/{denominator} = N/A"
    return f"{numerator}/{denominator} = {rate}"


def promotion_scope_status_lines(derived: Mapping[str, Any]) -> list[str]:
    if not derived:
        return []
    lines: list[str] = []
    promotion = derived["promotion_scope_readiness"]
    for scope_name in ["rag_retrieval_core", "visual_shadow"]:
        for basis in ["row_level", "canonical_level"]:
            projection = promotion[scope_name][basis]
            status = projection.get("current_rate_status")
            if status:
                lines.append(f"- {scope_name} {basis} promotion-scope current rate: `{status}`.")
    return lines


def kosis_state_lines(derived: Mapping[str, Any]) -> list[str]:
    state = derived.get("kosis_state") if derived else None
    if not state:
        return ["- KOSIS state: `not_observed`"]
    return [
        f"- rows/canonical: `{state['rows']}/{state['canonical_rows']}`",
        f"- vector_stage_eligible rows/canonical: `{state['vector_stage_eligible']['rows']}/{state['vector_stage_eligible']['canonical_rows']}`",
        f"- support_eligible rows/canonical: `{state['support_eligible']['rows']}/{state['support_eligible']['canonical_rows']}`",
        f"- gold_candidate_allowed rows/canonical: `{state['gold_candidate_allowed']['rows']}/{state['gold_candidate_allowed']['canonical_rows']}`",
        f"- license_evidence_level: `{state['license_evidence_level']}`",
        f"- review_required_reason: `{state['review_required_reason']}`",
    ]


def promotion_warning_lines(derived: Mapping[str, Any]) -> list[str]:
    warnings = derived.get("vector_readiness_promotion_block_warnings", []) if derived else []
    if not warnings:
        return ["- none"]
    return [
        "- `{source_family_id}` in `{scope}`: `{warning}`; row/canonical vector numerator drag `{row_vector_numerator_drag}/{canonical_vector_numerator_drag}`; reason `{reason}`.".format(
            **warning
        )
        for warning in warnings
    ]


def denominator_table_row(label: str, summary: Mapping[str, Any]) -> str:
    row = summary["row_level"]
    canon = summary["canonical_level"]
    return (
        f"| {label} | `{row['current']}` = `{row['current_rate']}` | "
        f"`{canon['current']}` = `{canon['current_rate']}` | "
        f"`{row['existing_units_to_promote_for_target']}` | "
        f"`{canon['existing_units_to_promote_for_target']}` | "
        f"`{row['new_all_qualified_units_needed_if_denominator_grows']}` | "
        f"`{canon['new_all_qualified_units_needed_if_denominator_grows']}` |"
    )


def render_denominator_risk_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 2A-2 Denominator Risk Report",
        "",
        f"- Generated: `{payload['generated_at']}`",
        "- Recommendation: report row-level and canonical-level denominators together.",
        "",
        "| risk | severity | evidence | recommendation |",
        "|---|---|---|---|",
    ]
    for risk in payload["denominator_risks"]:
        lines.append(
            f"| {risk['risk']} | {risk['severity']} | {risk['evidence']} | {risk['recommendation']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
