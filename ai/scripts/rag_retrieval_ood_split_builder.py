"""Build diagnostic OOD split manifests for retrieval generalization checks.

The builder is report-only. It does not tune, index, write vectors, mutate the
official denominator registry, or expose hidden XLSX content. Raw query/content
previews are not emitted; the manifest carries query ids and redacted hashes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent

DEFAULT_CONFIG = AI_WORKER_ROOT / "eval" / "configs" / "retrieval_ood_interference_diagnostic.yaml"
DEFAULT_MANIFEST = AI_WORKER_ROOT / "eval" / "review" / "retrieval_ood" / "retrieval_ood_split_manifest.csv"
DEFAULT_REPORT_JSON = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "retrieval_ood_split_report.json"
DEFAULT_REPORT_MD = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "retrieval_ood_split_report.md"

SPLIT_RANDOM = "random_row_split"
SPLIT_DOC_FAMILY = "leave_document_family_out"
SPLIT_TEMPLATE = "leave_template_or_table_shape_out"
SPLIT_PARSER = "leave_parser_version_out"
SPLIT_SOURCE = "leave_source_artifact_out"
SPLIT_FILE_ID = "file_identity_confusion_split"
SPLIT_LANE_CROSS = "lane_cross_eval"
ALL_SPLITS = [
    SPLIT_RANDOM,
    SPLIT_DOC_FAMILY,
    SPLIT_TEMPLATE,
    SPLIT_PARSER,
    SPLIT_SOURCE,
    SPLIT_FILE_ID,
    SPLIT_LANE_CROSS,
]

MANIFEST_FIELDS = [
    "split_id",
    "split_type",
    "lane",
    "query_id",
    "query_hash",
    "split_role",
    "group_hash",
    "group_kind",
    "main_metric_eligible",
    "random_baseline_only",
    "document_family_hash",
    "template_or_table_shape_hash",
    "parser_version",
    "source_artifact_hash",
    "file_identity_hash",
    "lane_cross_eval_target",
    "hidden_xlsx_redacted",
    "pdf_file_identity_only",
    "content_preview_emitted",
]

TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(resolve_path(args.config))
    rows, report = build_splits(config)
    manifest_path = resolve_path(args.output_csv or config["outputs"].get("split_manifest_csv") or DEFAULT_MANIFEST)
    report_json = resolve_path(args.output_json or config["outputs"].get("split_report_json") or DEFAULT_REPORT_JSON)
    report_md = resolve_path(args.output_md or config["outputs"].get("split_report_md") or DEFAULT_REPORT_MD)
    write_manifest(manifest_path, rows)
    report["outputs"] = {
        "split_manifest_csv": repo_relative(manifest_path),
        "split_report_json": repo_relative(report_json),
        "split_report_md": repo_relative(report_md),
    }
    write_json(report_json, report)
    write_text(report_md, render_markdown(report))
    print(json.dumps({
        "status": report["status"],
        "manifest_rows": report["manifest_row_count"],
        "split_manifest_csv": repo_relative(manifest_path),
        "split_report_json": repo_relative(report_json),
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"PASS", "PASS_WITH_SKIPS"} else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-csv", default=None)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-md", default=None)
    return parser.parse_args(argv)


def load_config(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("pyyaml is required")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"config must be a mapping: {path}")
    return raw


def build_splits(config: Mapping[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    prerequisites = prerequisite_status(config.get("prerequisites", {}))
    if not all(item["present"] for item in prerequisites.values()):
        status = "FAIL_CLOSED_PREREQUISITE_MISSING"
    else:
        status = "PASS"

    split_cfg = config.get("splits", {}) if isinstance(config.get("splits"), Mapping) else {}
    max_groups = int(split_cfg.get("max_groups_per_type", 8))
    main_types = set(split_cfg.get("main_metric_split_types") or [])
    lane_cfg_by_name = {lane_name(lane): lane for lane in config.get("lanes", [])}
    rows_by_lane = {lane: load_lane_rows(lane_cfg) for lane, lane_cfg in lane_cfg_by_name.items()}

    manifest: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for lane_cfg in config.get("lanes", []):
        lane = lane_name(lane_cfg)
        lane_rows = rows_by_lane[lane]
        random_rows = build_random_rows(lane, lane_rows, split_cfg)
        manifest.extend(random_rows)
        for split_type in [SPLIT_DOC_FAMILY, SPLIT_TEMPLATE, SPLIT_PARSER, SPLIT_SOURCE]:
            split_rows, skip = build_group_split_rows(
                lane=lane,
                lane_cfg=lane_cfg,
                lane_rows=lane_rows,
                split_type=split_type,
                max_groups=max_groups,
                main_metric_eligible=split_type in main_types,
            )
            manifest.extend(split_rows)
            if skip:
                skipped.append(skip)
        if bool(lane_cfg.get("identity_only")):
            split_rows, skip = build_group_split_rows(
                lane=lane,
                lane_cfg=lane_cfg,
                lane_rows=lane_rows,
                split_type=SPLIT_FILE_ID,
                max_groups=max_groups,
                main_metric_eligible=SPLIT_FILE_ID in main_types,
            )
            manifest.extend(split_rows)
            if skip:
                skipped.append(skip)

    if SPLIT_LANE_CROSS in main_types:
        for target_lane, lane_rows in rows_by_lane.items():
            lane_cfg = lane_cfg_by_name[target_lane]
            for row in lane_rows:
                manifest.append(manifest_row(
                    split_id=f"{SPLIT_LANE_CROSS}__{stable_slug(target_lane)}",
                    split_type=SPLIT_LANE_CROSS,
                    lane=target_lane,
                    row=row,
                    group_kind="lane",
                    group_value=target_lane,
                    main_metric_eligible=True,
                    lane_cross_eval_target=target_lane,
                    hidden_xlsx_redacted=bool(lane_cfg.get("hidden_xlsx_redaction")),
                    pdf_file_identity_only=bool(lane_cfg.get("identity_only")),
                ))

    lane_counts: dict[str, Any] = {
        lane: {
            "input_rows": len(lane_rows),
            "manifest_rows": sum(1 for row in manifest if row["lane"] == lane),
        }
        for lane, lane_rows in sorted(rows_by_lane.items())
    }
    split_counts = Counter(row["split_type"] for row in manifest)
    lane_split_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in manifest:
        lane_split_counts[row["lane"]][row["split_type"]] += 1
    if skipped and status == "PASS":
        status = "PASS_WITH_SKIPS"
    report = {
        "schema_version": "retrieval_ood_split_report_v1",
        "task": "rag_retrieval_ood_split_and_vector_interference_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        "scope": "diagnostic_report_only",
        "prerequisites": prerequisites,
        "production_index_mutation": False,
        "vector_write_attempted": False,
        "official_denominator_registry_changed": False,
        "hidden_xlsx_exposed": False,
        "pdf_file_lookup_policy": "file_identity_only_no_content_page_bbox_table_row_column_value_support",
        "random_row_split_used_as_main_metric": any(
            row["split_type"] == SPLIT_RANDOM and row["main_metric_eligible"] == "true"
            for row in manifest
        ),
        "main_metric_split_types": sorted(t for t in main_types if t != SPLIT_RANDOM),
        "diagnostic_baseline_split_types": [SPLIT_RANDOM],
        "manifest_row_count": len(manifest),
        "split_counts": dict(sorted(split_counts.items())),
        "lane_counts": lane_counts,
        "lane_split_counts": {lane: dict(sorted(counts.items())) for lane, counts in sorted(lane_split_counts.items())},
        "skipped_splits": skipped,
        "content_preview_emitted": False,
        "hidden_xlsx_redacted": True,
    }
    if report["random_row_split_used_as_main_metric"]:
        report["status"] = "FAIL_RANDOM_SPLIT_MARKED_MAIN"
    return manifest, report


def prerequisite_status(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, Mapping):
        return {}
    status: dict[str, dict[str, Any]] = {}
    for name, value in raw.items():
        path = resolve_path(str(value))
        item: dict[str, Any] = {"path": repo_relative(path), "present": path.exists()}
        if path.exists() and path.suffix.lower() == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                item["status"] = payload.get("status")
                item["schema_version"] = payload.get("schema_version")
            except json.JSONDecodeError:
                item["status"] = "UNREADABLE_JSON"
        status[str(name)] = item
    return status


def load_lane_rows(lane_cfg: Mapping[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source in lane_cfg.get("query_sources", []) or []:
        if not isinstance(source, Mapping):
            raise ValueError("query source must be a mapping")
        path = resolve_path(required_str(source, "path"))
        role = str(source.get("role") or "")
        if not path.exists():
            raise FileNotFoundError(path)
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                clean = {str(k): clean_text(v) for k, v in row.items() if k is not None}
                clean["_source_role"] = role
                rows.append(clean)
    return rows


def build_random_rows(lane: str, rows: Sequence[Mapping[str, str]], split_cfg: Mapping[str, Any]) -> list[dict[str, str]]:
    modulo = max(2, int(split_cfg.get("random_holdout_modulo", 5)))
    seed = str(split_cfg.get("random_seed", 9802))
    out = []
    for row in rows:
        bucket = int(hashlib.sha256((seed + query_id(row)).encode("utf-8")).hexdigest()[:8], 16) % modulo
        role = "heldout_eval" if bucket == 0 else "train_reference"
        out.append(manifest_row(
            split_id=f"{SPLIT_RANDOM}__mod{modulo}_bucket{bucket}",
            split_type=SPLIT_RANDOM,
            lane=lane,
            row=row,
            group_kind="random_bucket",
            group_value=str(bucket),
            split_role=role,
            main_metric_eligible=False,
            random_baseline_only=True,
        ))
    return out


def build_group_split_rows(
    *,
    lane: str,
    lane_cfg: Mapping[str, Any],
    lane_rows: Sequence[Mapping[str, str]],
    split_type: str,
    max_groups: int,
    main_metric_eligible: bool,
) -> tuple[list[dict[str, str]], dict[str, str] | None]:
    groups: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in lane_rows:
        group_value = group_for_split(split_type, row, lane_cfg)
        if group_value:
            groups[group_value].append(row)
    groups = {
        key: value
        for key, value in groups.items()
        if key and key not in {"UNKNOWN", "NOT_AVAILABLE", "NOT_APPLICABLE"}
    }
    if not groups:
        return [], {"lane": lane, "split_type": split_type, "reason": "metadata_unavailable"}
    selected = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))[:max_groups]
    out: list[dict[str, str]] = []
    for group_value, rows in selected:
        split_id = f"{split_type}__{stable_slug(lane)}__{short_hash(group_value)}"
        for row in rows:
            out.append(manifest_row(
                split_id=split_id,
                split_type=split_type,
                lane=lane,
                row=row,
                group_kind=split_type,
                group_value=group_value,
                main_metric_eligible=main_metric_eligible,
                pdf_file_identity_only=bool(lane_cfg.get("identity_only")),
                hidden_xlsx_redacted=bool(lane_cfg.get("hidden_xlsx_redaction")),
            ))
    return out, None


def group_for_split(split_type: str, row: Mapping[str, str], lane_cfg: Mapping[str, Any]) -> str:
    if split_type == SPLIT_DOC_FAMILY:
        return document_family(row)
    if split_type == SPLIT_TEMPLATE:
        return template_shape(row, lane_name(lane_cfg))
    if split_type == SPLIT_PARSER:
        return parser_version(row)
    if split_type == SPLIT_SOURCE:
        return source_artifact(row)
    if split_type == SPLIT_FILE_ID:
        return file_identity_family(row)
    return ""


def manifest_row(
    *,
    split_id: str,
    split_type: str,
    lane: str,
    row: Mapping[str, str],
    group_kind: str,
    group_value: str,
    split_role: str = "heldout_eval",
    main_metric_eligible: bool,
    random_baseline_only: bool = False,
    lane_cross_eval_target: str = "",
    hidden_xlsx_redacted: bool = False,
    pdf_file_identity_only: bool = False,
) -> dict[str, str]:
    return {
        "split_id": split_id,
        "split_type": split_type,
        "lane": lane,
        "query_id": query_id(row),
        "query_hash": short_hash(clean_text(row.get("query"))),
        "split_role": split_role,
        "group_hash": short_hash(group_value),
        "group_kind": group_kind,
        "main_metric_eligible": bool_text(main_metric_eligible),
        "random_baseline_only": bool_text(random_baseline_only),
        "document_family_hash": short_hash(document_family(row)),
        "template_or_table_shape_hash": short_hash(template_shape(row, lane)),
        "parser_version": parser_version(row),
        "source_artifact_hash": short_hash(source_artifact(row)),
        "file_identity_hash": short_hash(file_identity(row)),
        "lane_cross_eval_target": lane_cross_eval_target,
        "hidden_xlsx_redacted": bool_text(hidden_xlsx_redacted),
        "pdf_file_identity_only": bool_text(pdf_file_identity_only),
        "content_preview_emitted": "false",
    }


def write_manifest(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in MANIFEST_FIELDS})


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Retrieval OOD Split Report",
        "",
        f"Status: `{report['status']}`",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "Scope: diagnostic/report-only. The manifest contains query ids and redacted hashes, not raw content previews.",
        "",
        "## Split Counts",
        "",
        "| Split type | Rows |",
        "|---|---:|",
    ]
    for split_type, count in report["split_counts"].items():
        lines.append(f"| `{split_type}` | {count} |")
    lines.extend([
        "",
        "Main metric split types:",
    ])
    for split_type in report["main_metric_split_types"]:
        lines.append(f"- `{split_type}`")
    lines.extend([
        "",
        f"Random row split used as main metric: `{str(report['random_row_split_used_as_main_metric']).lower()}`",
        "",
        "## Lane Counts",
        "",
        "| Lane | Input rows | Manifest rows |",
        "|---|---:|---:|",
    ])
    for lane, counts in report["lane_counts"].items():
        lines.append(f"| `{lane}` | {counts['input_rows']} | {counts['manifest_rows']} |")
    if report["skipped_splits"]:
        lines.extend(["", "## Skipped Splits", ""])
        for skip in report["skipped_splits"]:
            lines.append(f"- `{skip['lane']}` `{skip['split_type']}`: {skip['reason']}")
    lines.extend([
        "",
        "## Guardrails",
        "",
        f"- `production_index_mutation`: `{str(report['production_index_mutation']).lower()}`",
        f"- `vector_write_attempted`: `{str(report['vector_write_attempted']).lower()}`",
        f"- `official_denominator_registry_changed`: `{str(report['official_denominator_registry_changed']).lower()}`",
        f"- `hidden_xlsx_exposed`: `{str(report['hidden_xlsx_exposed']).lower()}`",
        f"- PDF FILE lookup policy: `{report['pdf_file_lookup_policy']}`",
        "",
    ])
    return "\n".join(lines)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def required_str(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"missing required value: {key}")
    return str(value)


def lane_name(lane_cfg: Mapping[str, Any]) -> str:
    return required_str(lane_cfg, "name")


def query_id(row: Mapping[str, str]) -> str:
    return clean_text(row.get("query_id")) or clean_text(row.get("source_query_id")) or short_hash(clean_text(row.get("query")))


def document_family(row: Mapping[str, str]) -> str:
    for field in ("expected_file_name", "source_file_name", "expected_page_title", "expected_document_ids", "expected_page_ids"):
        value = first_multi(row.get(field))
        if value:
            return family_key(value)
    return "UNKNOWN"


def template_shape(row: Mapping[str, str], lane: str) -> str:
    if lane == "XLSX":
        parts = [
            "xlsx",
            clean_text(row.get("expected_chunk_type")),
            clean_text(row.get("expected_location_type")),
            clean_text(row.get("expected_sheet_name")) and "sheet_present",
            range_shape(clean_text(row.get("expected_cell_range"))),
            clean_text(row.get("expected_table_id")) and "table_present",
            bool_text(bool(clean_text(row.get("requires_formula_value")))),
            bool_text(bool(clean_text(row.get("requires_aggregation")))),
        ]
        return "|".join(part for part in parts if part)
    if lane == "PDF_CONTENT":
        parts = [
            "pdf",
            clean_text(row.get("expected_chunk_type")),
            clean_text(row.get("expected_location_type")),
            clean_text(row.get("expected_page_no")) and "page_present",
            clean_text(row.get("expected_bbox")) and "bbox_present",
            clean_text(row.get("expected_table_id")) and "table_present",
        ]
        return "|".join(part for part in parts if part)
    if lane == "PDF_FILE_IDENTITY":
        return file_identity_family(row)
    return "|".join(part for part in [
        "text",
        clean_text(row.get("bucket")),
        clean_text(row.get("answer_type")),
        clean_text(row.get("source_dataset")),
    ] if part) or "TEXT_GENERIC"


def parser_version(row: Mapping[str, str]) -> str:
    return clean_text(row.get("parser_version")) or clean_text(row.get("parserVersion")) or "UNKNOWN"


def source_artifact(row: Mapping[str, str]) -> str:
    for field in (
        "source_sample_id",
        "expected_document_version_id",
        "expected_file_name",
        "source_file_name",
        "expected_document_ids",
        "expected_page_ids",
    ):
        value = first_multi(row.get(field))
        if value:
            return value
    return "UNKNOWN"


def file_identity(row: Mapping[str, str]) -> str:
    return clean_text(row.get("expected_file_name")) or clean_text(row.get("source_file_name"))


def file_identity_family(row: Mapping[str, str]) -> str:
    return family_key(file_identity(row))


def first_multi(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    return re.split(r"[\s,;|]+", text)[0].strip()


def range_shape(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"\d+", "N", value.upper())


def family_key(value: str) -> str:
    text = clean_text(value).lower()
    if not text:
        return ""
    text = Path(text).stem
    text = re.sub(r"(?:19|20)\d{2}", "YEAR", text)
    text = re.sub(r"(?<!\d)(?:0?[1-9]|1[0-2])(?!\d)", "MONTH", text)
    text = re.sub(r"\d+", "NUM", text)
    text = re.sub(r"[_\-\s]+", " ", text)
    return text.strip() or clean_text(value)


def stable_slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    return text.strip("_").lower() or "group"


def short_hash(value: str) -> str:
    return hashlib.sha256(clean_text(value).encode("utf-8")).hexdigest()[:12]


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
