"""Enrich existing dataset manifests with license and usage-gate metadata.

This diagnostic/report-only gate scans already-collected manifests, normalizes
their rows, and emits companion manifests for noncommercial internal OCR/MM and
RAG experiments. It does not write production vectors, create namespaces,
promote rows to gold, create labels, or change official denominator files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    import yaml
except ImportError:  # pragma: no cover - only for stripped runtimes.
    yaml = None  # type: ignore[assignment]


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent

DEFAULT_CONFIG = AI_WORKER_ROOT / "eval" / "configs" / "existing_manifest_license_usage_gate.yaml"

PROJECT_USAGE_PROFILE = "NONCOMMERCIAL_INTERNAL_RESEARCH_AND_DEVELOPMENT"

LICENSE_STATUSES = {
    "VERIFIED_KOGL_TYPE_1",
    "VERIFIED_KOGL_TYPE_2_NONCOMMERCIAL",
    "VERIFIED_KOGL_TYPE_3_NO_DERIVATIVES",
    "VERIFIED_KOGL_TYPE_4_NONCOMMERCIAL_NO_DERIVATIVES",
    "VERIFIED_OPEN_PUBLIC_DATA",
    "VERIFIED_OPEN_LICENSE",
    "VERIFIED_ATTRIBUTION_REQUIRED",
    "VERIFIED_RESEARCH_ONLY",
    "VERIFIED_INTERNAL_EVAL_ONLY",
    "VERIFIED_NONCOMMERCIAL_ONLY",
    "VERIFIED_RESTRICTED",
    "SOURCE_TERMS_FOUND_BUT_AMBIGUOUS",
    "SOURCE_LICENSE_NOT_FOUND",
    "DOWNLOAD_URL_ONLY_NO_TERMS",
    "LICENSE_INFERRED_FROM_CATALOG_BUT_UNVERIFIED",
    "LICENSE_CONFLICT",
    "UNKNOWN_NEEDS_REVIEW",
}

VERIFIED_STATUSES = {status for status in LICENSE_STATUSES if status.startswith("VERIFIED_")}
LICENSE_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "BLOCKER", "UNKNOWN"}

USAGE_CLASSIFICATIONS = {
    "READY_INTERNAL_NONCOMMERCIAL_RAG_EXPERIMENT",
    "READY_INTERNAL_NONCOMMERCIAL_OCR_MM_EXPERIMENT",
    "READY_INTERNAL_NONCOMMERCIAL_VECTOR_STAGING",
    "READY_INTERNAL_NONCOMMERCIAL_PARSER_SMOKE",
    "READY_INTERNAL_NONCOMMERCIAL_DISTRACTOR_ONLY",
    "READY_PDF_FILE_IDENTITY_ONLY",
    "READY_PUBLIC_RELEASE_ALLOWED",
    "HOLD_LICENSE_UNKNOWN",
    "HOLD_LICENSE_AMBIGUOUS",
    "HOLD_RESEARCH_ONLY_NO_VECTOR_STAGING",
    "HOLD_NO_DERIVATIVES_OCR_MM_UNCLEAR",
    "HOLD_THIRD_PARTY_TRANSFER_PROHIBITED",
    "HOLD_FONT_NO_USER_FACING_ARTIFACT",
    "HOLD_GEODATA_SCOPE_CREEP",
    "HOLD_MOJIBAKE_IDENTITY_RISK",
    "HOLD_DUPLICATE_SHA_GROUP_ONLY",
    "BLOCK_LICENSE_RESTRICTED",
    "UNKNOWN_NEEDS_INVESTIGATION",
}

IDENTITY_FIELDS = [
    "manifest_source_path",
    "row_id",
    "canonical_row_id",
    "lane",
    "subtype",
    "role",
    "title",
    "relative_path",
    "sha256",
    "source_page",
    "download_url",
    "parent_archive_path",
    "parent_archive_sha256",
    "zip_entry_name",
    "normalized_path",
    "source_domain",
    "source_family_id",
]

PROJECT_USAGE_FIELDS = [
    "project_usage_profile",
    "intended_experiment_use",
    "support_eligible_default",
    "promotion_evidence",
]

LICENSE_FIELDS = [
    "license_status",
    "license_name",
    "license_type_code",
    "license_url",
    "source_terms_url",
    "source_license_evidence_url",
    "source_license_evidence_field",
    "license_evidence_text_preview",
    "license_verified_at",
    "license_verification_method",
    "attribution_required",
    "commercial_use_allowed",
    "noncommercial_use_allowed",
    "redistribution_allowed",
    "derivative_allowed",
    "no_derivatives",
    "third_party_transfer_prohibited",
    "internal_eval_allowed",
    "embedding_allowed",
    "vector_db_internal_allowed",
    "ocr_processing_allowed",
    "vlm_processing_allowed",
    "benchmark_eval_allowed",
    "public_report_allowed",
    "public_release_allowed",
    "license_risk_level",
    "license_notes",
    "requires_user_license_review",
]

OCR_MM_FIELDS = [
    "raw_image_allowed_internal",
    "annotation_allowed_internal",
    "annotation_answer_embedding_allowed",
    "support_eligible",
    "duplicate_image_group_id",
    "split_group_key",
]

RAG_POLICY_FIELDS = [
    "citation_capable_candidate",
    "parser_smoke_required",
    "gold_candidate_allowed",
    "pdf_file_identity_only",
    "pdf_file_content_mixing_support_allowed",
]

DUPLICATE_FIELDS = [
    "duplicate_sha_group_id",
    "duplicate_sha_group_size",
    "duplicate_sha_representative",
    "duplicate_relative_path_group_id",
    "duplicate_relative_path_group_size",
    "mojibake_identity_risk",
    "font_user_facing_artifact_allowed",
]

OUTPUT_FIELDS = (
    IDENTITY_FIELDS
    + PROJECT_USAGE_FIELDS
    + LICENSE_FIELDS
    + OCR_MM_FIELDS
    + RAG_POLICY_FIELDS
    + DUPLICATE_FIELDS
)

RAG_CORE_LANES = {"TEXT_NAMU", "XLSX", "PDF_CONTENT", "PDF_FILE_IDENTITY"}
OCR_MM_LANES = {
    "OCR_IMAGE",
    "OCR_ANNOTATION",
    "OCR_SHADOW",
    "IDP_SHADOW",
    "MULTIMODAL_IMAGE",
    "MULTIMODAL_ANNOTATION",
    "IMAGE_ARCHIVE",
}
ANNOTATION_LANES = {"OCR_ANNOTATION", "MULTIMODAL_ANNOTATION"}
FONT_LANES = {"FONT"}
GEODATA_LANES = {"GEODATA", "GEODATA_ARCHIVE"}
PDF_FILE_LANES = {"PDF_FILE_IDENTITY", "PDF_FILE_LOOKUP"}

LICENSE_FIELD_HINTS = (
    "license",
    "licence",
    "rights",
    "terms",
    "copyright",
    "kogl",
    "public_data",
    "usage",
    "use_policy",
)
SOURCE_FIELD_NAMES = (
    "source_page",
    "source_url",
    "url",
    "homepage",
    "dataset_url",
    "download_page",
)
DOWNLOAD_FIELD_NAMES = ("download_url", "download", "file_url", "url")
PATH_FIELD_NAMES = (
    "relative_path",
    "file_path",
    "path",
    "fileName",
    "filename",
    "sourceFileName",
    "querySetPath",
)
TITLE_FIELD_NAMES = (
    "title",
    "name",
    "sample_id",
    "logicalSourceId",
    "dataset_id",
    "query_id",
    "case_id",
)
SHA_FIELD_NAMES = ("sha256", "sha", "file_sha256", "digest")
ROW_ID_FIELD_NAMES = ("row_id", "id", "sample_id", "logicalSourceId", "query_id", "case_id")
PARENT_ARCHIVE_RE = re.compile(r"(?:extracted_from|parent_archive)\s*=\s*([^;]+)")
ZIP_ENTRY_RE = re.compile(r"(?:zip_entry|entry|zip_entry_name)\s*=\s*([^;]+)")
MOJIBAKE_RE = re.compile(r"(?:�|Ã.|Â.|ì|í|ë|ê|ð|¤)")
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


@dataclass(frozen=True)
class ManifestFile:
    path: Path
    rows: list[dict[str, Any]]
    schema_fields: list[str]
    load_warning: str = ""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = resolve_path(args.config)
    config = load_config(config_path)
    payload = run_gate(config=config, config_path=config_path)
    write_outputs(config, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "manifests_scanned": payload["counts"]["manifest_count"],
                "total_rows": payload["counts"]["total_rows"],
                "canonical_rows": payload["counts"]["canonical_row_count"],
                "internal_eval_allowed": payload["counts"]["internal_eval_allowed_count"],
                "embedding_allowed": payload["counts"]["embedding_allowed_count"],
                "vector_db_internal_allowed": payload["counts"]["vector_db_internal_allowed_count"],
                "ocr_mm_ready": payload["counts"]["ocr_mm_internal_ready_count"],
                "rag_ready": payload["counts"]["rag_internal_ready_count"],
                "review_required_rows": payload["counts"]["review_required_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if payload["guardrail_status"]["all_guardrails_preserved"] else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    return parser.parse_args(argv)


def load_config(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("pyyaml is required to load existing manifest license gate config")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"config must be a mapping: {path}")
    return raw


def run_gate(*, config: Mapping[str, Any], config_path: Path) -> dict[str, Any]:
    manifest_files = load_manifest_files(config)
    manifest_inventory = [inventory_for_manifest(manifest) for manifest in manifest_files]
    raw_rows = normalize_manifest_rows(manifest_files)
    source_cache = build_source_evidence_cache(raw_rows, config)
    enriched_rows = enrich_rows(raw_rows, config, source_cache)
    apply_duplicate_groups(enriched_rows)
    for row in enriched_rows:
        finalize_usage_classification(row)

    official_diff = official_denominator_registry_diff()
    guardrails = build_guardrail_status(enriched_rows, official_diff)
    counts = build_counts(enriched_rows, manifest_inventory)
    readiness = build_readiness(enriched_rows, config)
    by_source = build_source_summary(enriched_rows)
    status = "PASS_WITH_GAPS" if guardrails["all_guardrails_preserved"] else "BLOCKED"
    if readiness["overall_threshold_status"] == "PASS" and guardrails["all_guardrails_preserved"]:
        status = "PASS"

    outputs = output_paths(config)
    return {
        "schema_version": "existing_manifest_license_usage_gate_report_v1",
        "task": "rag_existing_dataset_license_usage_gate_v1",
        "generated_at": utc_timestamp(),
        "config_path": repo_relative(config_path),
        "status": status,
        "scope": {
            "diagnostic_report_only": True,
            "project_usage_profile": PROJECT_USAGE_PROFILE,
            "production_index_mutation": False,
            "production_vector_write": False,
            "namespace_created": False,
            "official_denominator_registry_changed": official_diff["changed"],
            "gold_promotion": False,
            "label_creation": False,
            "support_evidence_creation": False,
        },
        "outputs": {name: repo_relative(path) for name, path in outputs.items()},
        "counts": counts,
        "manifest_inventory": manifest_inventory,
        "license_status_counts": counter_dict(row["license_status"] for row in enriched_rows),
        "license_risk_level_counts": counter_dict(row["license_risk_level"] for row in enriched_rows),
        "usage_classification_counts": counter_dict(row["intended_experiment_use"] for row in enriched_rows),
        "lane_counts": counter_dict(row["lane"] for row in enriched_rows),
        "source_domain_counts": counter_dict(row["source_domain"] for row in enriched_rows),
        "source_family_counts": counter_dict(row["source_family_id"] for row in enriched_rows),
        "duplicate_sha_groups": duplicate_group_summary(enriched_rows, "duplicate_sha_group_id", "sha256"),
        "duplicate_relative_path_groups": duplicate_group_summary(
            enriched_rows,
            "duplicate_relative_path_group_id",
            "normalized_path",
        ),
        "readiness": readiness,
        "source_summary": by_source,
        "guardrail_status": guardrails,
        "enriched_rows": enriched_rows,
        "review_required_rows": review_required_rows(enriched_rows),
    }


def load_manifest_files(config: Mapping[str, Any]) -> list[ManifestFile]:
    paths = discover_manifest_paths(config)
    manifests: list[ManifestFile] = []
    for path in paths:
        try:
            manifests.append(load_manifest_file(path))
        except (OSError, ValueError, json.JSONDecodeError, csv.Error) as exc:
            manifests.append(ManifestFile(path=path, rows=[], schema_fields=[], load_warning=str(exc)))
    return manifests


def discover_manifest_paths(config: Mapping[str, Any]) -> list[Path]:
    inputs = config.get("inputs", {}) if isinstance(config.get("inputs"), Mapping) else {}
    candidates: list[Path] = []
    for raw in inputs.get("manifest_paths", []) or []:
        path = resolve_path(str(raw))
        if path.exists() and path.is_file():
            candidates.append(path)

    if bool(inputs.get("discover_repo_manifests", True)):
        for pattern in inputs.get("repo_manifest_globs", []) or []:
            for path in REPO_ROOT.glob(str(pattern)):
                if path.is_file():
                    candidates.append(path.resolve())

    exclude_patterns = [str(pattern).replace("\\", "/") for pattern in inputs.get("exclude_path_contains", []) or []]
    output_names = {path.name for path in output_paths(config).values()}
    seen: set[str] = set()
    result: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        normalized = str(resolved).replace("\\", "/")
        if any(pattern in normalized for pattern in exclude_patterns):
            continue
        if resolved.name in output_names:
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(resolved)
    return sorted(result, key=lambda p: str(p).lower())


def load_manifest_file(path: Path) -> ManifestFile:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = [dict(row) for row in reader]
            fields = list(reader.fieldnames or [])
        return ManifestFile(path=path, rows=rows, schema_fields=fields)
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = rows_from_json_payload(payload)
        fields = sorted({key for row in rows for key in row.keys()})
        return ManifestFile(path=path, rows=rows, schema_fields=fields)
    raise ValueError(f"unsupported manifest suffix: {path}")


def rows_from_json_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [coerce_row(row) for row in payload]
    if not isinstance(payload, dict):
        return [{"value": payload}]

    for key in (
        "rows",
        "manifest_rows",
        "samples",
        "sources",
        "files",
        "items",
        "records",
        "queries",
        "cases",
        "datasets",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            return [coerce_row(row) for row in value]

    # Report manifests are still inventory evidence, but have no per-file rows.
    return [coerce_row(payload)]


def coerce_row(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): val for key, val in value.items()}
    return {"value": value}


def inventory_for_manifest(manifest: ManifestFile) -> dict[str, Any]:
    normalized_rows = [base_identity_fields(manifest, row, idx) for idx, row in enumerate(manifest.rows)]
    source_page_count = sum(bool(row["source_page"]) for row in normalized_rows)
    download_url_count = sum(bool(row["download_url"]) for row in normalized_rows)
    sha_counts = Counter(row["sha256"] for row in normalized_rows if row["sha256"])
    path_counts = Counter(row["normalized_path"] for row in normalized_rows if row["normalized_path"])
    collected_issues = sum(collected_at_issue(row) for row in manifest.rows)
    mojibake_count = sum(
        has_mojibake(identity_text(row, fields=("title", "relative_path", "normalized_path")))
        for row in normalized_rows
    )
    fields = sorted(set(manifest.schema_fields))
    license_fields_present = [field for field in fields if field_has_license_hint(field)]
    return {
        "manifest_path": repo_relative(manifest.path),
        "row_count": len(manifest.rows),
        "schema_fields": fields,
        "load_warning": manifest.load_warning,
        "source_page_coverage": coverage(source_page_count, len(manifest.rows)),
        "download_url_coverage": coverage(download_url_count, len(manifest.rows)),
        "duplicate_sha256_count": sum(count for count in sha_counts.values() if count > 1),
        "duplicate_relative_path_count": sum(count for count in path_counts.values() if count > 1),
        "lane_distribution": counter_dict(row["lane"] for row in normalized_rows),
        "subtype_distribution": counter_dict(row["subtype"] for row in normalized_rows if row["subtype"]),
        "role_distribution": counter_dict(row["role"] for row in normalized_rows if row["role"]),
        "collected_at_format_issue_count": collected_issues,
        "mojibake_filename_or_title_count": mojibake_count,
        "license_metadata_fields_present": license_fields_present,
        "license_metadata_fields_absent": [hint for hint in LICENSE_FIELD_HINTS if not any(hint in f.lower() for f in fields)],
    }


def normalize_manifest_rows(manifest_files: Sequence[ManifestFile]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for manifest in manifest_files:
        for index, row in enumerate(manifest.rows):
            base = base_identity_fields(manifest, row, index)
            base["_source_row"] = row
            base["_source_row_index"] = index
            normalized.append(base)
    return normalized


def base_identity_fields(manifest: ManifestFile, row: Mapping[str, Any], index: int) -> dict[str, Any]:
    source_page = first_value(row, SOURCE_FIELD_NAMES)
    download_url = first_value(row, DOWNLOAD_FIELD_NAMES)
    relative_path = first_value(row, PATH_FIELD_NAMES)
    title = first_value(row, TITLE_FIELD_NAMES) or relative_path
    sha256 = first_value(row, SHA_FIELD_NAMES).lower()
    lane = normalize_lane(first_value(row, ("lane", "bucket", "file_type", "type")), row, manifest.path, relative_path)
    notes = stringify(row.get("notes"))
    parent_archive_path = first_value(row, ("parent_archive_path", "parent_archive", "archive_path"))
    zip_entry_name = first_value(row, ("zip_entry_name", "zip_entry", "entry_name"))
    if not parent_archive_path:
        parent_archive_path = regex_value(PARENT_ARCHIVE_RE, notes)
    if not zip_entry_name:
        zip_entry_name = regex_value(ZIP_ENTRY_RE, notes)
    normalized_path = normalize_path(relative_path or zip_entry_name or title)
    row_id = first_value(row, ROW_ID_FIELD_NAMES) or f"{repo_relative(manifest.path)}#{index + 1:05d}"
    source_domain = domain_from_url(source_page or download_url)
    source_family_id = source_family(source_domain, source_page, download_url, row, lane)
    canonical_seed = "|".join(
        [
            sha256,
            normalized_path.lower(),
            source_page.lower(),
            download_url.lower(),
            title.lower(),
        ]
    )
    return {
        "manifest_source_path": repo_relative(manifest.path),
        "row_id": stringify(row_id),
        "canonical_row_id": "row_" + stable_hash(canonical_seed, length=20),
        "lane": lane,
        "subtype": stringify(row.get("subtype")),
        "role": stringify(row.get("role")),
        "title": stringify(title),
        "relative_path": stringify(relative_path),
        "sha256": sha256,
        "source_page": source_page,
        "download_url": download_url,
        "parent_archive_path": normalize_path(parent_archive_path),
        "parent_archive_sha256": stringify(row.get("parent_archive_sha256")).lower(),
        "zip_entry_name": stringify(zip_entry_name),
        "normalized_path": normalized_path,
        "source_domain": source_domain,
        "source_family_id": source_family_id,
    }


def enrich_rows(
    rows: Sequence[dict[str, Any]],
    config: Mapping[str, Any],
    source_cache: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched = []
    for row in rows:
        source_row = row.get("_source_row", {})
        license_fields = classify_license(row, source_row, config, source_cache)
        usage_fields = {
            "project_usage_profile": PROJECT_USAGE_PROFILE,
            "intended_experiment_use": "UNKNOWN_NEEDS_INVESTIGATION",
            "support_eligible_default": False,
            "promotion_evidence": False,
        }
        policy_fields = build_policy_fields(row, license_fields, source_row)
        output = {field: "" for field in OUTPUT_FIELDS}
        output.update({key: row.get(key, "") for key in IDENTITY_FIELDS})
        output.update(usage_fields)
        output.update(license_fields)
        output.update(policy_fields)
        output["mojibake_identity_risk"] = has_mojibake(identity_text(output))
        output["font_user_facing_artifact_allowed"] = False if output["lane"] in FONT_LANES else True
        assert_license_field_contract(output)
        enriched.append(output)
    return enriched


def classify_license(
    row: Mapping[str, Any],
    source_row: Mapping[str, Any],
    config: Mapping[str, Any],
    source_cache: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    evidence = collect_row_license_evidence(source_row)
    source_policy = configured_source_policy(row, config)
    network_evidence = source_cache.get(str(row.get("source_page") or ""), {})

    if evidence:
        decision = decision_from_evidence(evidence, evidence_url=str(row.get("source_page") or row.get("download_url") or ""))
    elif source_policy:
        decision = decision_from_source_policy(row, source_policy)
    elif network_evidence.get("license_evidence_text"):
        decision = decision_from_evidence(
            {
                "field": "source_page_html",
                "text": network_evidence["license_evidence_text"],
                "url": network_evidence.get("url", ""),
            },
            evidence_url=network_evidence.get("url", ""),
        )
    else:
        decision = default_unknown_decision(row)

    decision = apply_source_specific_conservatism(row, source_row, decision)
    ensure_verified_has_evidence(decision)
    return normalize_license_decision(decision)


def collect_row_license_evidence(row: Mapping[str, Any]) -> dict[str, str]:
    for key, value in row.items():
        key_text = str(key).lower()
        text = stringify(value)
        if not text:
            continue
        if field_has_license_hint(key_text) or "license=" in text.lower() or "공공누리" in text:
            return {
                "field": str(key),
                "text": text,
                "url": url_from_text(text),
            }
    return {}


def decision_from_evidence(evidence: Mapping[str, str], evidence_url: str = "") -> dict[str, Any]:
    text = evidence.get("text", "")
    lowered = text.lower()
    kogl_type = detect_kogl_type(text)
    if kogl_type:
        return kogl_decision(kogl_type, evidence, evidence_url)
    if "cc by-nc-nd" in lowered or ("noncommercial" in lowered and "no deriv" in lowered):
        return {
            **base_decision("VERIFIED_KOGL_TYPE_4_NONCOMMERCIAL_NO_DERIVATIVES", "HIGH"),
            "license_name": "Noncommercial no-derivatives license evidence",
            "license_type_code": "NONCOMMERCIAL_NO_DERIVATIVES",
            "source_license_evidence_field": evidence.get("field", ""),
            "source_license_evidence_url": evidence.get("url") or evidence_url,
            "license_evidence_text_preview": preview(text),
            "license_verification_method": "manifest_license_metadata",
            "attribution_required": True,
            "commercial_use_allowed": False,
            "noncommercial_use_allowed": True,
            "redistribution_allowed": False,
            "derivative_allowed": False,
            "no_derivatives": True,
            "internal_eval_allowed": True,
            "ocr_processing_allowed": False,
            "vlm_processing_allowed": False,
            "public_release_allowed": False,
            "requires_user_license_review": True,
        }
    if "cc by-nc" in lowered or "non-commercial" in lowered or "noncommercial" in lowered:
        return {
            **base_decision("VERIFIED_NONCOMMERCIAL_ONLY", "MEDIUM"),
            "license_name": license_name_from_text(text, default="Noncommercial license evidence"),
            "license_type_code": "NONCOMMERCIAL_ONLY",
            "source_license_evidence_field": evidence.get("field", ""),
            "source_license_evidence_url": evidence.get("url") or evidence_url,
            "license_evidence_text_preview": preview(text),
            "license_verification_method": "manifest_license_metadata",
            "attribution_required": "cc by" in lowered or "attribution" in lowered,
            "commercial_use_allowed": False,
            "noncommercial_use_allowed": True,
            "redistribution_allowed": "no redistrib" not in lowered,
            "derivative_allowed": "nd" not in lowered and "no deriv" not in lowered,
            "no_derivatives": "nd" in lowered or "no deriv" in lowered,
            "internal_eval_allowed": True,
            "embedding_allowed": True,
            "vector_db_internal_allowed": True,
            "ocr_processing_allowed": True,
            "vlm_processing_allowed": True,
            "benchmark_eval_allowed": True,
            "public_report_allowed": True,
            "public_release_allowed": False,
        }
    if "이용허락범위 제한 없음" in text or "public domain" in lowered or "공공데이터" in text and "제한 없음" in text:
        return {
            **base_decision("VERIFIED_OPEN_PUBLIC_DATA", "LOW"),
            "license_name": "Open public data / unrestricted use evidence",
            "license_type_code": "OPEN_PUBLIC_DATA_UNRESTRICTED",
            "source_license_evidence_field": evidence.get("field", ""),
            "source_license_evidence_url": evidence.get("url") or evidence_url,
            "license_evidence_text_preview": preview(text),
            "license_verification_method": "manifest_or_catalog_license_metadata",
            "attribution_required": "public domain" not in lowered,
            "commercial_use_allowed": True,
            "noncommercial_use_allowed": True,
            "redistribution_allowed": True,
            "derivative_allowed": True,
            "internal_eval_allowed": True,
            "embedding_allowed": True,
            "vector_db_internal_allowed": True,
            "ocr_processing_allowed": True,
            "vlm_processing_allowed": True,
            "benchmark_eval_allowed": True,
            "public_report_allowed": True,
            "public_release_allowed": True,
        }
    if "research" in lowered and ("only" in lowered or "solely" in lowered):
        return {
            **base_decision("VERIFIED_RESEARCH_ONLY", "MEDIUM"),
            "license_name": "Research-only terms",
            "license_type_code": "RESEARCH_ONLY",
            "source_license_evidence_field": evidence.get("field", ""),
            "source_license_evidence_url": evidence.get("url") or evidence_url,
            "license_evidence_text_preview": preview(text),
            "license_verification_method": "manifest_license_metadata",
            "commercial_use_allowed": False,
            "noncommercial_use_allowed": True,
            "redistribution_allowed": not ("third party" in lowered or "redistribution" in lowered or "redistribute" in lowered),
            "third_party_transfer_prohibited": "third party" in lowered or "제3자" in text,
            "internal_eval_allowed": True,
            "ocr_processing_allowed": True,
            "vlm_processing_allowed": True,
            "benchmark_eval_allowed": True,
            "public_report_allowed": False,
            "requires_user_license_review": True,
        }
    if any(token in lowered for token in ("cc by", "cc-by", "cc0", "apache", "mit license", "gpl-3.0", "gpl 3")):
        license_name = license_name_from_text(text, default="Open license evidence")
        attribution = "cc by" in lowered or "apache" in lowered or "gpl" in lowered
        return {
            **base_decision("VERIFIED_OPEN_LICENSE", "LOW"),
            "license_name": license_name,
            "license_type_code": license_type_from_name(license_name),
            "license_url": evidence.get("url", ""),
            "source_license_evidence_field": evidence.get("field", ""),
            "source_license_evidence_url": evidence.get("url") or evidence_url,
            "license_evidence_text_preview": preview(text),
            "license_verification_method": "manifest_license_metadata",
            "attribution_required": attribution,
            "commercial_use_allowed": True,
            "noncommercial_use_allowed": True,
            "redistribution_allowed": True,
            "derivative_allowed": True,
            "internal_eval_allowed": True,
            "embedding_allowed": True,
            "vector_db_internal_allowed": True,
            "ocr_processing_allowed": True,
            "vlm_processing_allowed": True,
            "benchmark_eval_allowed": True,
            "public_report_allowed": True,
            "public_release_allowed": True,
        }
    if any(token in lowered for token in ("restricted", "prohibit", "금지", "third party", "제3자")):
        return {
            **base_decision("VERIFIED_RESTRICTED", "BLOCKER"),
            "license_name": "Restricted terms evidence",
            "license_type_code": "RESTRICTED",
            "source_license_evidence_field": evidence.get("field", ""),
            "source_license_evidence_url": evidence.get("url") or evidence_url,
            "license_evidence_text_preview": preview(text),
            "license_verification_method": "manifest_license_metadata",
            "third_party_transfer_prohibited": "third party" in lowered or "제3자" in text,
            "requires_user_license_review": True,
        }
    return {
        **base_decision("SOURCE_TERMS_FOUND_BUT_AMBIGUOUS", "MEDIUM"),
        "source_license_evidence_field": evidence.get("field", ""),
        "source_license_evidence_url": evidence.get("url") or evidence_url,
        "license_evidence_text_preview": preview(text),
        "license_verification_method": "manifest_license_metadata_ambiguous",
        "internal_eval_allowed": True,
        "public_report_allowed": True,
        "requires_user_license_review": True,
    }


def decision_from_source_policy(row: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    status = str(policy.get("license_status", "SOURCE_TERMS_FOUND_BUT_AMBIGUOUS"))
    risk = str(policy.get("license_risk_level", "MEDIUM"))
    decision = base_decision(status, risk)
    decision.update(
        {
            "license_name": stringify(policy.get("license_name")),
            "license_type_code": stringify(policy.get("license_type_code")),
            "license_url": stringify(policy.get("license_url")),
            "source_terms_url": stringify(policy.get("source_terms_url")),
            "source_license_evidence_url": stringify(policy.get("source_license_evidence_url") or policy.get("source_terms_url")),
            "source_license_evidence_field": "configured_source_family_rule",
            "license_evidence_text_preview": preview(stringify(policy.get("evidence_text"))),
            "license_verified_at": utc_timestamp() if status in VERIFIED_STATUSES else "",
            "license_verification_method": stringify(policy.get("verification_method") or "configured_source_family_rule"),
            "license_notes": stringify(policy.get("license_notes")),
        }
    )
    for field in boolean_license_fields():
        if field in policy:
            decision[field] = bool(policy[field])
    if "requires_user_license_review" in policy:
        decision["requires_user_license_review"] = bool(policy["requires_user_license_review"])
    if status not in VERIFIED_STATUSES:
        decision["license_verified_at"] = ""
    if row.get("source_family_id") == "KOSIS" and kosis_restricted_scope(row):
        decision.update(
            {
                "license_status": "SOURCE_TERMS_FOUND_BUT_AMBIGUOUS",
                "license_risk_level": "HIGH",
                "embedding_allowed": False,
                "vector_db_internal_allowed": False,
                "public_release_allowed": False,
                "requires_user_license_review": True,
                "license_notes": append_note(
                    decision.get("license_notes", ""),
                    "KOSIS row may involve international or third-party statistics; row-specific review required.",
                ),
            }
        )
    return decision


def default_unknown_decision(row: Mapping[str, Any]) -> dict[str, Any]:
    if row.get("download_url") and not row.get("source_page"):
        return {
            **base_decision("DOWNLOAD_URL_ONLY_NO_TERMS", "UNKNOWN"),
            "license_verification_method": "download_url_only_no_terms",
            "license_notes": "Download URL exists but no source page or terms metadata was found.",
            "requires_user_license_review": True,
        }
    if row.get("source_page"):
        return {
            **base_decision("SOURCE_LICENSE_NOT_FOUND", "UNKNOWN"),
            "source_license_evidence_url": stringify(row.get("source_page")),
            "license_verification_method": "source_page_present_no_license_metadata",
            "license_notes": "Source page exists, but no row-specific license metadata was present in the manifest.",
            "requires_user_license_review": True,
        }
    return {
        **base_decision("UNKNOWN_NEEDS_REVIEW", "UNKNOWN"),
        "license_verification_method": "no_license_or_source_metadata",
        "license_notes": "No license, terms, source page, or catalog metadata was found in the manifest row.",
        "requires_user_license_review": True,
    }


def apply_source_specific_conservatism(
    row: Mapping[str, Any],
    source_row: Mapping[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    lane = str(row.get("lane", ""))
    source_family_id = str(row.get("source_family_id", ""))
    notes: list[str] = []

    if lane in FONT_LANES:
        decision.update(
            {
                "embedding_allowed": False,
                "vector_db_internal_allowed": False,
                "ocr_processing_allowed": False,
                "vlm_processing_allowed": False,
                "benchmark_eval_allowed": False,
                "public_report_allowed": False,
                "public_release_allowed": False,
                "redistribution_allowed": False,
                "license_risk_level": "HIGH" if decision.get("license_risk_level") != "BLOCKER" else "BLOCKER",
                "requires_user_license_review": True,
            }
        )
        notes.append("Font files are blocked from user-facing artifacts, public release, generated downloads, and benchmark artifacts.")

    if lane in GEODATA_LANES:
        decision.update({"embedding_allowed": False, "vector_db_internal_allowed": False, "public_release_allowed": False})
        notes.append("Geodata is held out of vector staging until scope is explicitly approved.")

    if source_family_id == "AI_HUB":
        decision["third_party_transfer_prohibited"] = bool(decision.get("third_party_transfer_prohibited", True))
        decision.update({"redistribution_allowed": False, "public_release_allowed": False, "requires_user_license_review": True})
        notes.append("AI Hub-like terms require explicit dataset-specific review and block redistribution by default.")

    if source_family_id == "PRISM" and decision.get("license_status") == "SOURCE_LICENSE_NOT_FOUND":
        decision.update({"internal_eval_allowed": False, "embedding_allowed": False, "vector_db_internal_allowed": False})
        notes.append("PRISM attachments require per-task KOGL/source-page evidence; no PRISM-wide license was assumed.")

    if source_family_id == "DART" and decision.get("license_status") in {"SOURCE_TERMS_FOUND_BUT_AMBIGUOUS", "SOURCE_LICENSE_NOT_FOUND"}:
        decision.update({"embedding_allowed": False, "vector_db_internal_allowed": False, "public_release_allowed": False})
        notes.append("DART/OpenDART terms do not automatically prove PDF redistribution or vector staging permission.")

    if lane in PDF_FILE_LANES:
        notes.append("PDF FILE lane remains file-identity only; no content/page/bbox/table/row/column/value support is allowed.")

    if lane in ANNOTATION_LANES:
        notes.append("Annotation labels are diagnostic metadata only and are never used as embedding/search text.")

    if decision.get("no_derivatives") and lane in OCR_MM_LANES:
        decision.update({"ocr_processing_allowed": False, "vlm_processing_allowed": False, "embedding_allowed": False, "vector_db_internal_allowed": False})
        notes.append("No-derivatives evidence blocks automatic OCR/VLM transformation and vector staging.")

    if has_mojibake(identity_text(row)):
        decision.update({"embedding_allowed": False, "vector_db_internal_allowed": False, "public_release_allowed": False})
        notes.append("Mojibake filename/title blocks identity evidence use until normalized.")

    if notes:
        decision["license_notes"] = append_note(stringify(decision.get("license_notes")), " ".join(notes))
    return decision


def normalize_license_decision(decision: Mapping[str, Any]) -> dict[str, Any]:
    normalized = base_decision(
        str(decision.get("license_status", "UNKNOWN_NEEDS_REVIEW")),
        str(decision.get("license_risk_level", "UNKNOWN")),
    )
    normalized.update({key: decision.get(key, normalized.get(key, "")) for key in LICENSE_FIELDS})
    if normalized["license_status"] not in LICENSE_STATUSES:
        normalized["license_status"] = "UNKNOWN_NEEDS_REVIEW"
    if normalized["license_risk_level"] not in LICENSE_RISK_LEVELS:
        normalized["license_risk_level"] = "UNKNOWN"
    for field in boolean_license_fields():
        normalized[field] = bool(normalized.get(field, False))
    normalized["license_verified_at"] = stringify(normalized.get("license_verified_at"))
    if normalized["license_status"] not in VERIFIED_STATUSES:
        normalized["license_verified_at"] = ""
    return normalized


def base_decision(status: str, risk: str) -> dict[str, Any]:
    return {
        "license_status": status,
        "license_name": "",
        "license_type_code": "",
        "license_url": "",
        "source_terms_url": "",
        "source_license_evidence_url": "",
        "source_license_evidence_field": "",
        "license_evidence_text_preview": "",
        "license_verified_at": utc_timestamp() if status in VERIFIED_STATUSES else "",
        "license_verification_method": "",
        "attribution_required": False,
        "commercial_use_allowed": False,
        "noncommercial_use_allowed": False,
        "redistribution_allowed": False,
        "derivative_allowed": False,
        "no_derivatives": False,
        "third_party_transfer_prohibited": False,
        "internal_eval_allowed": False,
        "embedding_allowed": False,
        "vector_db_internal_allowed": False,
        "ocr_processing_allowed": False,
        "vlm_processing_allowed": False,
        "benchmark_eval_allowed": False,
        "public_report_allowed": False,
        "public_release_allowed": False,
        "license_risk_level": risk,
        "license_notes": "",
        "requires_user_license_review": status not in VERIFIED_STATUSES,
    }


def kogl_decision(kogl_type: int, evidence: Mapping[str, str], evidence_url: str) -> dict[str, Any]:
    status_by_type = {
        1: "VERIFIED_KOGL_TYPE_1",
        2: "VERIFIED_KOGL_TYPE_2_NONCOMMERCIAL",
        3: "VERIFIED_KOGL_TYPE_3_NO_DERIVATIVES",
        4: "VERIFIED_KOGL_TYPE_4_NONCOMMERCIAL_NO_DERIVATIVES",
    }
    commercial = kogl_type in {1, 3}
    derivative = kogl_type in {1, 2}
    risk = "LOW" if kogl_type == 1 else "MEDIUM"
    if not derivative:
        risk = "HIGH"
    return {
        **base_decision(status_by_type[kogl_type], risk),
        "license_name": f"KOGL Type {kogl_type}",
        "license_type_code": f"KOGL-{kogl_type}",
        "license_url": "https://www.mcst.go.kr/kor/s_open/kogl/koglType.jsp?pTab=02",
        "source_license_evidence_field": evidence.get("field", ""),
        "source_license_evidence_url": evidence.get("url") or evidence_url,
        "license_evidence_text_preview": preview(evidence.get("text", "")),
        "license_verification_method": "manifest_license_metadata",
        "attribution_required": True,
        "commercial_use_allowed": commercial,
        "noncommercial_use_allowed": True,
        "redistribution_allowed": True,
        "derivative_allowed": derivative,
        "no_derivatives": not derivative,
        "internal_eval_allowed": True,
        "embedding_allowed": derivative,
        "vector_db_internal_allowed": derivative,
        "ocr_processing_allowed": derivative,
        "vlm_processing_allowed": derivative,
        "benchmark_eval_allowed": derivative,
        "public_report_allowed": True,
        "public_release_allowed": kogl_type == 1,
        "requires_user_license_review": kogl_type != 1,
    }


def detect_kogl_type(text: str) -> int | None:
    compact = re.sub(r"\s+", "", text.lower())
    patterns = {
        1: ("kogltype1", "kogl-1", "제1유형", "1유형"),
        2: ("kogltype2", "kogl-2", "제2유형", "2유형"),
        3: ("kogltype3", "kogl-3", "제3유형", "3유형"),
        4: ("kogltype4", "kogl-4", "제4유형", "4유형"),
    }
    for kogl_type, tokens in patterns.items():
        if any(token in compact for token in tokens):
            return kogl_type
    if "공공누리" in text and "상업적이용금지" in compact and "변경금지" in compact:
        return 4
    if "공공누리" in text and "상업적이용금지" in compact:
        return 2
    if "공공누리" in text and "변경금지" in compact:
        return 3
    if "공공누리" in text and "출처" in text:
        return 1
    return None


def configured_source_policy(row: Mapping[str, Any], config: Mapping[str, Any]) -> Mapping[str, Any]:
    policies = config.get("source_family_policies", []) or []
    source_page = stringify(row.get("source_page")).lower()
    domain = stringify(row.get("source_domain")).lower()
    source_family_id = stringify(row.get("source_family_id"))
    for policy in policies:
        if not isinstance(policy, Mapping):
            continue
        families = {str(item) for item in policy.get("source_family_ids", []) or []}
        domains = {str(item).lower() for item in policy.get("domains", []) or []}
        contains = [str(item).lower() for item in policy.get("source_page_contains", []) or []]
        if families and source_family_id not in families:
            continue
        if domains and domain not in domains:
            continue
        if contains and not any(token in source_page for token in contains):
            continue
        return policy
    return {}


def build_source_evidence_cache(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    network_cfg = config.get("network_verification", {}) if isinstance(config.get("network_verification"), Mapping) else {}
    if not bool(network_cfg.get("enabled", False)):
        return {}
    max_checks = int(network_cfg.get("max_source_page_checks", 25))
    timeout = float(network_cfg.get("timeout_seconds", 4))
    urls = []
    for row in rows:
        url = stringify(row.get("source_page"))
        if url and url.startswith(("http://", "https://")) and url not in urls:
            urls.append(url)
    cache: dict[str, dict[str, Any]] = {}
    for url in urls[:max_checks]:
        cache[url] = fetch_license_evidence(url, timeout=timeout)
    return cache


def fetch_license_evidence(url: str, *, timeout: float) -> dict[str, Any]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "codex-license-usage-gate/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - explicit user-approved source check.
            content_type = response.headers.get("content-type", "")
            raw = response.read(250_000)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"url": url, "fetch_error": str(exc), "license_evidence_text": ""}
    if "text" not in content_type and "html" not in content_type and not raw.startswith(b"<"):
        return {"url": url, "content_type": content_type, "license_evidence_text": ""}
    text = raw.decode("utf-8", errors="ignore")
    evidence = extract_license_snippet(text)
    return {"url": url, "content_type": content_type, "license_evidence_text": evidence}


def extract_license_snippet(text: str) -> str:
    normalized = re.sub(r"<[^>]+>", " ", text)
    normalized = re.sub(r"\s+", " ", normalized)
    lowered = normalized.lower()
    markers = ("공공누리", "kogl", "license", "copyright", "cc by", "apache", "research only")
    positions = [lowered.find(marker.lower()) for marker in markers if lowered.find(marker.lower()) >= 0]
    if not positions:
        return ""
    pos = min(positions)
    return normalized[max(0, pos - 120) : pos + 800]


def build_policy_fields(
    row: Mapping[str, Any],
    license_fields: Mapping[str, Any],
    source_row: Mapping[str, Any],
) -> dict[str, Any]:
    lane = str(row.get("lane", ""))
    internal = bool(license_fields.get("internal_eval_allowed"))
    can_process_visual = bool(license_fields.get("ocr_processing_allowed") or license_fields.get("vlm_processing_allowed"))
    duplicate_image_group_id = ""
    split_group_key = ""
    if lane in OCR_MM_LANES:
        group_seed = stringify(row.get("sha256")) or stringify(row.get("relative_path")) or stringify(row.get("title"))
        duplicate_image_group_id = "imggrp_" + stable_hash(group_seed, length=16)
        split_group_key = "split_" + stable_hash(
            "|".join(
                [
                    stringify(row.get("source_family_id")),
                    stringify(row.get("source_page")),
                    stringify(source_row.get("paired_image")),
                    stringify(row.get("title")),
                ]
            ),
            length=16,
        )
    citation_capable = lane in {"XLSX", "PDF_CONTENT"} and all(
        truthy(source_row.get(field)) for field in ("parser_version", "location_json", "citation_text")
    )
    parser_smoke_required = lane in {"XLSX", "PDF_CONTENT", "OCR_SHADOW", "OFFICE", "ARCHIVE", "CSV", "JSON", "XML"}
    return {
        "raw_image_allowed_internal": lane in OCR_MM_LANES and internal,
        "annotation_allowed_internal": lane in ANNOTATION_LANES and internal,
        "annotation_answer_embedding_allowed": False,
        "support_eligible": False,
        "duplicate_image_group_id": duplicate_image_group_id,
        "split_group_key": split_group_key,
        "citation_capable_candidate": citation_capable,
        "parser_smoke_required": parser_smoke_required,
        "gold_candidate_allowed": False,
        "pdf_file_identity_only": lane in PDF_FILE_LANES,
        "pdf_file_content_mixing_support_allowed": False,
    }


def apply_duplicate_groups(rows: list[dict[str, Any]]) -> None:
    sha_groups = group_by(rows, "sha256")
    path_groups = group_by(rows, "normalized_path")
    for group_index, (_, group_rows) in enumerate(sorted(sha_groups.items()), start=1):
        if len(group_rows) <= 1:
            continue
        group_id = f"sha_group_{group_index:04d}"
        representative_id = min(row["canonical_row_id"] for row in group_rows)
        for row in group_rows:
            row["duplicate_sha_group_id"] = group_id
            row["duplicate_sha_group_size"] = len(group_rows)
            row["duplicate_sha_representative"] = row["canonical_row_id"] == representative_id
    for group_index, (_, group_rows) in enumerate(sorted(path_groups.items()), start=1):
        if len(group_rows) <= 1:
            continue
        group_id = f"path_group_{group_index:04d}"
        for row in group_rows:
            row["duplicate_relative_path_group_id"] = group_id
            row["duplicate_relative_path_group_size"] = len(group_rows)
    for row in rows:
        row.setdefault("duplicate_sha_group_id", "")
        row.setdefault("duplicate_sha_group_size", 0)
        row.setdefault("duplicate_sha_representative", True)
        row.setdefault("duplicate_relative_path_group_id", "")
        row.setdefault("duplicate_relative_path_group_size", 0)


def finalize_usage_classification(row: dict[str, Any]) -> None:
    if row["mojibake_identity_risk"]:
        row["intended_experiment_use"] = "HOLD_MOJIBAKE_IDENTITY_RISK"
        row["embedding_allowed"] = False
        row["vector_db_internal_allowed"] = False
        return
    if row["lane"] in FONT_LANES:
        row["intended_experiment_use"] = "HOLD_FONT_NO_USER_FACING_ARTIFACT"
        return
    if row["lane"] in GEODATA_LANES:
        row["intended_experiment_use"] = "HOLD_GEODATA_SCOPE_CREEP"
        return
    if row["duplicate_sha_group_id"] and not row["duplicate_sha_representative"]:
        row["intended_experiment_use"] = "HOLD_DUPLICATE_SHA_GROUP_ONLY"
        row["vector_db_internal_allowed"] = False
        return
    if row["license_status"] == "VERIFIED_RESTRICTED" or row["license_risk_level"] == "BLOCKER":
        row["intended_experiment_use"] = "BLOCK_LICENSE_RESTRICTED"
        return
    if row["third_party_transfer_prohibited"]:
        row["intended_experiment_use"] = "HOLD_THIRD_PARTY_TRANSFER_PROHIBITED"
        return
    if row["license_status"] in {"UNKNOWN_NEEDS_REVIEW", "SOURCE_LICENSE_NOT_FOUND", "DOWNLOAD_URL_ONLY_NO_TERMS"}:
        row["intended_experiment_use"] = "HOLD_LICENSE_UNKNOWN"
        row["embedding_allowed"] = False
        row["vector_db_internal_allowed"] = False
        return
    if row["license_status"] in {"SOURCE_TERMS_FOUND_BUT_AMBIGUOUS", "LICENSE_INFERRED_FROM_CATALOG_BUT_UNVERIFIED", "LICENSE_CONFLICT"}:
        row["intended_experiment_use"] = "HOLD_LICENSE_AMBIGUOUS"
        row["vector_db_internal_allowed"] = False
        return
    if row["license_status"] == "VERIFIED_RESEARCH_ONLY" and row["lane"] not in OCR_MM_LANES:
        row["intended_experiment_use"] = "HOLD_RESEARCH_ONLY_NO_VECTOR_STAGING"
        row["embedding_allowed"] = False
        row["vector_db_internal_allowed"] = False
        return
    if row["no_derivatives"] and row["lane"] in OCR_MM_LANES:
        row["intended_experiment_use"] = "HOLD_NO_DERIVATIVES_OCR_MM_UNCLEAR"
        return
    if row["lane"] in PDF_FILE_LANES and row["internal_eval_allowed"]:
        row["intended_experiment_use"] = "READY_PDF_FILE_IDENTITY_ONLY"
        row["citation_capable_candidate"] = False
        row["parser_smoke_required"] = False
        return
    if row["vector_db_internal_allowed"] and row["embedding_allowed"]:
        row["intended_experiment_use"] = "READY_INTERNAL_NONCOMMERCIAL_VECTOR_STAGING"
        return
    if row["lane"] in OCR_MM_LANES and row["internal_eval_allowed"] and (row["ocr_processing_allowed"] or row["vlm_processing_allowed"]):
        row["intended_experiment_use"] = "READY_INTERNAL_NONCOMMERCIAL_OCR_MM_EXPERIMENT"
        return
    if row["lane"] in RAG_CORE_LANES and row["internal_eval_allowed"]:
        row["intended_experiment_use"] = "READY_INTERNAL_NONCOMMERCIAL_RAG_EXPERIMENT"
        return
    if row["parser_smoke_required"] and row["internal_eval_allowed"]:
        row["intended_experiment_use"] = "READY_INTERNAL_NONCOMMERCIAL_PARSER_SMOKE"
        return
    if row["public_release_allowed"]:
        row["intended_experiment_use"] = "READY_PUBLIC_RELEASE_ALLOWED"
        return
    row["intended_experiment_use"] = "UNKNOWN_NEEDS_INVESTIGATION"


def build_counts(rows: Sequence[Mapping[str, Any]], manifest_inventory: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "manifest_count": len(manifest_inventory),
        "total_rows": len(rows),
        "canonical_row_count": len({row["canonical_row_id"] for row in rows}),
        "rows_by_lane": counter_dict(row["lane"] for row in rows),
        "rows_by_source_domain": counter_dict(row["source_domain"] for row in rows),
        "license_verified_count": sum(str(row["license_status"]).startswith("VERIFIED_") for row in rows),
        "license_unknown_count": sum(
            row["license_status"] in {"UNKNOWN_NEEDS_REVIEW", "SOURCE_LICENSE_NOT_FOUND", "DOWNLOAD_URL_ONLY_NO_TERMS"}
            for row in rows
        ),
        "license_blocker_count": sum(
            row["license_risk_level"] == "BLOCKER" or row["license_status"] == "VERIFIED_RESTRICTED" for row in rows
        ),
        "source_terms_ambiguous_count": sum(
            row["license_status"] in {"SOURCE_TERMS_FOUND_BUT_AMBIGUOUS", "LICENSE_INFERRED_FROM_CATALOG_BUT_UNVERIFIED"}
            for row in rows
        ),
        "internal_eval_allowed_count": sum(bool(row["internal_eval_allowed"]) for row in rows),
        "embedding_allowed_count": sum(bool(row["embedding_allowed"]) for row in rows),
        "vector_db_internal_allowed_count": sum(bool(row["vector_db_internal_allowed"]) for row in rows),
        "public_release_allowed_count": sum(bool(row["public_release_allowed"]) for row in rows),
        "public_release_blocked_count": sum(not bool(row["public_release_allowed"]) for row in rows),
        "ocr_mm_internal_ready_count": sum(row["intended_experiment_use"] == "READY_INTERNAL_NONCOMMERCIAL_OCR_MM_EXPERIMENT" for row in rows),
        "rag_internal_ready_count": sum(
            row["intended_experiment_use"]
            in {
                "READY_INTERNAL_NONCOMMERCIAL_RAG_EXPERIMENT",
                "READY_INTERNAL_NONCOMMERCIAL_VECTOR_STAGING",
                "READY_PDF_FILE_IDENTITY_ONLY",
            }
            and row["lane"] in RAG_CORE_LANES
            for row in rows
        ),
        "vector_staging_ready_count": sum(row["intended_experiment_use"] == "READY_INTERNAL_NONCOMMERCIAL_VECTOR_STAGING" for row in rows),
        "review_required_count": sum(bool(row["requires_user_license_review"]) for row in rows),
        "duplicate_sha_group_count": len({row["duplicate_sha_group_id"] for row in rows if row["duplicate_sha_group_id"]}),
        "duplicate_sha_row_count": sum(bool(row["duplicate_sha_group_id"]) for row in rows),
        "mojibake_identity_risk_count": sum(bool(row["mojibake_identity_risk"]) for row in rows),
        "font_user_facing_blocked_count": sum(row["lane"] in FONT_LANES and not row["font_user_facing_artifact_allowed"] for row in rows),
        "third_party_transfer_restricted_count": sum(bool(row["third_party_transfer_prohibited"]) for row in rows),
        "support_eligible_ocr_mm_count": sum(row["lane"] in OCR_MM_LANES and bool(row["support_eligible"]) for row in rows),
        "annotation_answer_embedding_count": sum(bool(row["annotation_answer_embedding_allowed"]) for row in rows),
        "pdf_file_content_mixing_support_count": sum(bool(row["pdf_file_content_mixing_support_allowed"]) for row in rows),
        "promotion_evidence_count": sum(bool(row["promotion_evidence"]) for row in rows),
        "hidden_xlsx_exposed": False,
    }


def build_readiness(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> dict[str, Any]:
    thresholds = config.get("readiness_thresholds", {}) if isinstance(config.get("readiness_thresholds"), Mapping) else {}
    retrieval_rows = [row for row in rows if row["lane"] in RAG_CORE_LANES]
    retrieval_core_rows = [row for row in retrieval_rows if row["lane"] != "PDF_FILE_IDENTITY"]
    visual_rows = [row for row in rows if row["lane"] in OCR_MM_LANES]
    annotation_rows = [row for row in visual_rows if row["lane"] in ANNOTATION_LANES]
    xlsx_pdf_content_rows = [row for row in rows if row["lane"] in {"XLSX", "PDF_CONTENT"}]
    metrics = {
        "retrieval_core_internal_eval_allowed_rate": rate(
            sum(bool(row["internal_eval_allowed"]) for row in retrieval_core_rows),
            len(retrieval_core_rows),
        ),
        "retrieval_core_embedding_allowed_rate": rate(
            sum(bool(row["embedding_allowed"]) for row in retrieval_core_rows),
            len(retrieval_core_rows),
        ),
        "retrieval_core_vector_db_internal_allowed_rate": rate(
            sum(bool(row["vector_db_internal_allowed"]) for row in retrieval_core_rows),
            len(retrieval_core_rows),
        ),
        "xlsx_pdf_content_parser_smoke_candidate_count": sum(
            bool(row["parser_smoke_required"]) and bool(row["internal_eval_allowed"]) for row in xlsx_pdf_content_rows
        ),
        "pdf_file_identity_identity_only_count": sum(
            row["lane"] == "PDF_FILE_IDENTITY" and bool(row["pdf_file_identity_only"]) for row in rows
        ),
        "visual_shadow_internal_eval_allowed_rate": rate(
            sum(bool(row["internal_eval_allowed"]) for row in visual_rows),
            len(visual_rows),
        ),
        "visual_shadow_ocr_or_vlm_processing_allowed_rate": rate(
            sum(bool(row["ocr_processing_allowed"] or row["vlm_processing_allowed"]) for row in visual_rows),
            len(visual_rows),
        ),
        "visual_shadow_vector_db_internal_allowed_rate": rate(
            sum(bool(row["vector_db_internal_allowed"]) for row in visual_rows),
            len(visual_rows),
        ),
        "annotation_answer_embedding_count": sum(bool(row["annotation_answer_embedding_allowed"]) for row in rows),
        "support_eligible_ocr_mm_count": sum(row["lane"] in OCR_MM_LANES and bool(row["support_eligible"]) for row in rows),
        "annotation_split_group_available_count": sum(bool(row["split_group_key"]) for row in annotation_rows),
        "annotation_backed_row_count": len(annotation_rows),
    }
    checks = {
        "retrieval_core_internal_eval_allowed_rate": metrics["retrieval_core_internal_eval_allowed_rate"]
        >= float(thresholds.get("retrieval_core_internal_eval_allowed_rate", 0.80)),
        "retrieval_core_embedding_allowed_rate": metrics["retrieval_core_embedding_allowed_rate"]
        >= float(thresholds.get("retrieval_core_embedding_allowed_rate", 0.70)),
        "retrieval_core_vector_db_internal_allowed_rate": metrics["retrieval_core_vector_db_internal_allowed_rate"]
        >= float(thresholds.get("retrieval_core_vector_db_internal_allowed_rate", 0.70)),
        "xlsx_pdf_content_parser_smoke_candidate_count": metrics["xlsx_pdf_content_parser_smoke_candidate_count"]
        >= int(thresholds.get("xlsx_pdf_content_parser_smoke_candidate_count", 1)),
        "pdf_file_identity_rows_separated": metrics["pdf_file_identity_identity_only_count"]
        == sum(row["lane"] == "PDF_FILE_IDENTITY" for row in rows),
        "visual_shadow_internal_eval_allowed_rate": metrics["visual_shadow_internal_eval_allowed_rate"]
        >= float(thresholds.get("visual_shadow_internal_eval_allowed_rate", 0.80)),
        "visual_shadow_ocr_or_vlm_processing_allowed_rate": metrics["visual_shadow_ocr_or_vlm_processing_allowed_rate"]
        >= float(thresholds.get("visual_shadow_ocr_or_vlm_processing_allowed_rate", 0.70)),
        "visual_shadow_vector_db_internal_allowed_rate": metrics["visual_shadow_vector_db_internal_allowed_rate"]
        >= float(thresholds.get("visual_shadow_vector_db_internal_allowed_rate", 0.60)),
        "annotation_answer_embedding_count_zero": metrics["annotation_answer_embedding_count"] == 0,
        "support_eligible_ocr_mm_count_zero": metrics["support_eligible_ocr_mm_count"] == 0,
        "duplicate_image_group_split_keys_available": metrics["annotation_split_group_available_count"]
        == metrics["annotation_backed_row_count"],
        "official_denominator_unchanged": True,
    }
    retrieval_pass = all(
        checks[key]
        for key in (
            "retrieval_core_internal_eval_allowed_rate",
            "retrieval_core_embedding_allowed_rate",
            "retrieval_core_vector_db_internal_allowed_rate",
            "xlsx_pdf_content_parser_smoke_candidate_count",
            "pdf_file_identity_rows_separated",
        )
    )
    visual_pass = all(
        checks[key]
        for key in (
            "visual_shadow_internal_eval_allowed_rate",
            "visual_shadow_ocr_or_vlm_processing_allowed_rate",
            "visual_shadow_vector_db_internal_allowed_rate",
            "annotation_answer_embedding_count_zero",
            "support_eligible_ocr_mm_count_zero",
            "duplicate_image_group_split_keys_available",
        )
    )
    return {
        "thresholds": dict(thresholds),
        "metrics": metrics,
        "checks": checks,
        "rag_experiment_readiness": "PASS" if retrieval_pass else "NEEDS_MORE_LICENSED_DATA_OR_REVIEW",
        "ocr_mm_experiment_readiness": "PASS" if visual_pass else "NEEDS_MORE_LICENSED_DATA_OR_REVIEW",
        "overall_threshold_status": "PASS" if retrieval_pass and visual_pass else "NEEDS_MORE_LICENSED_DATA_OR_REVIEW",
        "production_readiness_claimed": False,
    }


def build_source_summary(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["source_domain"]), str(row["source_family_id"]))].append(row)
    summary = []
    for (domain, family), group_rows in sorted(grouped.items()):
        summary.append(
            {
                "source_domain": domain,
                "source_family_id": family,
                "row_count": len(group_rows),
                "lane_counts": counter_dict(row["lane"] for row in group_rows),
                "license_status_counts": counter_dict(row["license_status"] for row in group_rows),
                "license_risk_level_counts": counter_dict(row["license_risk_level"] for row in group_rows),
                "internal_eval_allowed_count": sum(bool(row["internal_eval_allowed"]) for row in group_rows),
                "embedding_allowed_count": sum(bool(row["embedding_allowed"]) for row in group_rows),
                "vector_db_internal_allowed_count": sum(bool(row["vector_db_internal_allowed"]) for row in group_rows),
                "public_release_allowed_count": sum(bool(row["public_release_allowed"]) for row in group_rows),
                "review_required_count": sum(bool(row["requires_user_license_review"]) for row in group_rows),
                "kogl_status_counts": counter_dict(
                    row["license_status"] for row in group_rows if "KOGL" in str(row["license_status"])
                ),
            }
        )
    return summary


def build_guardrail_status(rows: Sequence[Mapping[str, Any]], official_diff: Mapping[str, Any]) -> dict[str, Any]:
    status = {
        "official_denominator_registry_changed": bool(official_diff["changed"]),
        "official_denominator_registry_diff_proof": official_diff,
        "production_index_mutation": False,
        "production_vector_write": False,
        "namespace_created": False,
        "support_eligible_ocr_mm_count": sum(row["lane"] in OCR_MM_LANES and bool(row["support_eligible"]) for row in rows),
        "annotation_answer_embedding_count": sum(bool(row["annotation_answer_embedding_allowed"]) for row in rows),
        "pdf_file_content_mixing_support_count": sum(bool(row["pdf_file_content_mixing_support_allowed"]) for row in rows),
        "hidden_xlsx_exposed": False,
        "promotion_evidence": any(bool(row["promotion_evidence"]) for row in rows),
        "expected_answers_created": False,
        "relevance_labels_created": False,
        "answerability_labels_created": False,
        "annotation_labels_used_as_embedding_text": False,
        "font_files_redistributed_or_user_facing": False,
    }
    status["all_guardrails_preserved"] = (
        not status["official_denominator_registry_changed"]
        and not status["production_index_mutation"]
        and not status["production_vector_write"]
        and not status["namespace_created"]
        and status["support_eligible_ocr_mm_count"] == 0
        and status["annotation_answer_embedding_count"] == 0
        and status["pdf_file_content_mixing_support_count"] == 0
        and not status["hidden_xlsx_exposed"]
        and not status["promotion_evidence"]
        and not status["expected_answers_created"]
        and not status["relevance_labels_created"]
        and not status["answerability_labels_created"]
        and not status["annotation_labels_used_as_embedding_text"]
        and not status["font_files_redistributed_or_user_facing"]
    )
    return status


def review_required_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    review_statuses = {
        "SOURCE_TERMS_FOUND_BUT_AMBIGUOUS",
        "SOURCE_LICENSE_NOT_FOUND",
        "DOWNLOAD_URL_ONLY_NO_TERMS",
        "LICENSE_INFERRED_FROM_CATALOG_BUT_UNVERIFIED",
        "LICENSE_CONFLICT",
        "UNKNOWN_NEEDS_REVIEW",
        "VERIFIED_RESTRICTED",
        "VERIFIED_RESEARCH_ONLY",
    }
    return [
        dict(row)
        for row in rows
        if row["license_status"] in review_statuses
        or bool(row["requires_user_license_review"])
        or row["intended_experiment_use"].startswith(("HOLD_", "BLOCK_", "UNKNOWN_"))
    ]


def write_outputs(config: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    paths = output_paths(config)
    rows = list(payload["enriched_rows"])
    write_json(paths["enriched_json"], rows)
    write_csv(paths["enriched_csv"], rows, OUTPUT_FIELDS)
    write_json(paths["gate_json"], report_without_rows(payload))
    write_text(paths["gate_md"], render_gate_markdown(payload))
    write_json(paths["summary_by_source_json"], payload["source_summary"])
    write_text(paths["summary_by_source_md"], render_source_summary_markdown(payload))
    write_json(paths["readiness_json"], payload["readiness"])
    write_text(paths["readiness_md"], render_readiness_markdown(payload))
    write_csv(paths["review_required_csv"], payload["review_required_rows"], OUTPUT_FIELDS)


def report_without_rows(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in {"enriched_rows", "review_required_rows"}}


def render_gate_markdown(payload: Mapping[str, Any]) -> str:
    counts = payload["counts"]
    guardrails = payload["guardrail_status"]
    lines = [
        "# Existing Manifest License Usage Gate",
        "",
        f"- Task: `{payload['task']}`",
        f"- Generated: `{payload['generated_at']}`",
        f"- Status: `{payload['status']}`",
        f"- Project usage profile: `{PROJECT_USAGE_PROFILE}`",
        f"- Manifests scanned: `{counts['manifest_count']}`",
        f"- Total rows: `{counts['total_rows']}`; canonical rows: `{counts['canonical_row_count']}`",
        "",
        "## License Summary",
        "",
    ]
    lines.extend(markdown_counter("License status", payload["license_status_counts"]))
    lines.extend(markdown_counter("License risk", payload["license_risk_level_counts"]))
    lines.extend(
        [
            "",
            "## Usage Readiness",
            "",
            f"- Internal eval allowed: `{counts['internal_eval_allowed_count']}`",
            f"- Embedding allowed: `{counts['embedding_allowed_count']}`",
            f"- Diagnostic vector staging ready: `{counts['vector_staging_ready_count']}`",
            f"- RAG internal ready: `{counts['rag_internal_ready_count']}`",
            f"- OCR/MM internal ready: `{counts['ocr_mm_internal_ready_count']}`",
            f"- Public release allowed: `{counts['public_release_allowed_count']}`",
            f"- Public release blocked: `{counts['public_release_blocked_count']}`",
            f"- Review required: `{counts['review_required_count']}`",
            "",
            "## Risk Signals",
            "",
            f"- Duplicate SHA groups: `{counts['duplicate_sha_group_count']}`; duplicate SHA rows: `{counts['duplicate_sha_row_count']}`",
            f"- Mojibake identity-risk rows: `{counts['mojibake_identity_risk_count']}`",
            f"- Font rows blocked from user-facing artifacts: `{counts['font_user_facing_blocked_count']}`",
            f"- Third-party transfer restricted rows: `{counts['third_party_transfer_restricted_count']}`",
            "",
            "## Guardrails",
            "",
            f"- official_denominator_registry_changed: `{str(guardrails['official_denominator_registry_changed']).lower()}`",
            f"- production_index_mutation: `{str(guardrails['production_index_mutation']).lower()}`",
            f"- production_vector_write: `{str(guardrails['production_vector_write']).lower()}`",
            f"- namespace_created: `{str(guardrails['namespace_created']).lower()}`",
            f"- support_eligible_ocr_mm_count: `{guardrails['support_eligible_ocr_mm_count']}`",
            f"- annotation_answer_embedding_count: `{guardrails['annotation_answer_embedding_count']}`",
            f"- pdf_file_content_mixing_support_count: `{guardrails['pdf_file_content_mixing_support_count']}`",
            f"- hidden_xlsx_exposed: `{str(guardrails['hidden_xlsx_exposed']).lower()}`",
            f"- promotion_evidence: `{str(guardrails['promotion_evidence']).lower()}`",
        ]
    )
    return "\n".join(lines) + "\n"


def render_source_summary_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Existing Manifest License Summary By Source",
        "",
        "| source_domain | source_family_id | rows | top license status | internal | vector | review |",
        "|---|---:|---:|---|---:|---:|---:|",
    ]
    for row in payload["source_summary"]:
        top_status = top_counter_label(row["license_status_counts"])
        lines.append(
            f"| {row['source_domain'] or 'UNKNOWN'} | {row['source_family_id']} | {row['row_count']} | "
            f"{top_status} | {row['internal_eval_allowed_count']} | {row['vector_db_internal_allowed_count']} | "
            f"{row['review_required_count']} |"
        )
    lines.extend(
        [
            "",
            "## PRISM KOGL Status",
            "",
        ]
    )
    prism_rows = [row for row in payload["source_summary"] if row["source_family_id"] == "PRISM"]
    if prism_rows:
        for row in prism_rows:
            lines.extend(markdown_counter(f"{row['source_domain']} KOGL/license status", row["license_status_counts"]))
    else:
        lines.append("- No PRISM rows found.")
    lines.extend(["", "## Public Data Portal Status", ""])
    portal_rows = [row for row in payload["source_summary"] if row["source_family_id"] in {"PUBLIC_DATA_PORTAL", "SEOUL_OPEN_DATA"}]
    if portal_rows:
        for row in portal_rows:
            lines.extend(markdown_counter(f"{row['source_domain']} license status", row["license_status_counts"]))
    else:
        lines.append("- No public data portal rows found.")
    return "\n".join(lines) + "\n"


def render_readiness_markdown(payload: Mapping[str, Any]) -> str:
    readiness = payload["readiness"]
    metrics = readiness["metrics"]
    checks = readiness["checks"]
    lines = [
        "# Existing Manifest Experiment Readiness",
        "",
        f"- RAG experiment readiness: `{readiness['rag_experiment_readiness']}`",
        f"- OCR/MM experiment readiness: `{readiness['ocr_mm_experiment_readiness']}`",
        f"- Overall threshold status: `{readiness['overall_threshold_status']}`",
        f"- Production readiness claimed: `{str(readiness['production_readiness_claimed']).lower()}`",
        "",
        "## Metrics",
        "",
    ]
    for key, value in metrics.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Checks", ""])
    for key, value in checks.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    return "\n".join(lines) + "\n"


def output_paths(config: Mapping[str, Any]) -> dict[str, Path]:
    outputs = config.get("outputs", {}) if isinstance(config.get("outputs"), Mapping) else {}
    defaults = {
        "enriched_json": AI_WORKER_ROOT / "eval" / "review" / "retrieval_dataset_supplementation" / "existing_manifest_license_enriched.json",
        "enriched_csv": AI_WORKER_ROOT / "eval" / "review" / "retrieval_dataset_supplementation" / "existing_manifest_license_enriched.csv",
        "gate_md": AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "existing_manifest_license_usage_gate.md",
        "gate_json": AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "existing_manifest_license_usage_gate.json",
        "summary_by_source_md": AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "existing_manifest_license_summary_by_source.md",
        "summary_by_source_json": AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "existing_manifest_license_summary_by_source.json",
        "readiness_md": AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "existing_manifest_experiment_readiness.md",
        "readiness_json": AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "existing_manifest_experiment_readiness.json",
        "review_required_csv": AI_WORKER_ROOT / "eval" / "review" / "retrieval_dataset_supplementation" / "license_review_required_rows.csv",
    }
    return {key: resolve_path(str(outputs.get(key) or value)) for key, value in defaults.items()}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def official_denominator_registry_diff() -> dict[str, Any]:
    registry = "ai/eval/eval_queries/official_denominator_registry.json"
    if not (REPO_ROOT / registry).exists():
        return {"path": registry, "exists": False, "changed": False, "git_diff_returncode": 0}
    result = subprocess.run(
        ["git", "diff", "--quiet", "--", registry],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    return {
        "path": registry,
        "exists": True,
        "changed": result.returncode != 0,
        "git_diff_returncode": result.returncode,
        "stderr": result.stderr.strip(),
    }


def assert_license_field_contract(row: Mapping[str, Any]) -> None:
    missing = [field for field in OUTPUT_FIELDS if field not in row]
    if missing:
        raise ValueError(f"enriched row missing required fields: {missing}")
    if row["license_status"] not in LICENSE_STATUSES:
        raise ValueError(f"invalid license_status: {row['license_status']}")
    if row["license_risk_level"] not in LICENSE_RISK_LEVELS:
        raise ValueError(f"invalid license_risk_level: {row['license_risk_level']}")


def ensure_verified_has_evidence(decision: Mapping[str, Any]) -> None:
    if decision.get("license_status") not in VERIFIED_STATUSES:
        return
    has_evidence = any(
        stringify(decision.get(field))
        for field in (
            "source_license_evidence_url",
            "source_terms_url",
            "license_url",
            "license_evidence_text_preview",
        )
    )
    if not has_evidence:
        raise ValueError(f"verified license lacks explicit evidence: {decision.get('license_status')}")


def normalize_lane(raw_lane: str, row: Mapping[str, Any], manifest_path: Path, relative_path: str) -> str:
    value = stringify(raw_lane).upper().replace("-", "_").replace(" ", "_")
    if value in {"PDF_FILE_LOOKUP", "PDF_FILE_IDENTITY"}:
        return "PDF_FILE_IDENTITY"
    if value in {
        "TEXT_NAMU",
        "XLSX",
        "PDF_CONTENT",
        "OCR_IMAGE",
        "OCR_ANNOTATION",
        "OCR_SHADOW",
        "MULTIMODAL_IMAGE",
        "MULTIMODAL_ANNOTATION",
        "FONT",
        "GEODATA",
        "GEODATA_ARCHIVE",
        "IMAGE_ARCHIVE",
        "CSV",
        "JSON",
        "XML",
        "TXT",
        "HTML",
        "OFFICE",
        "ARCHIVE",
        "REFERENCE",
    }:
        return value
    path_text = " ".join([str(manifest_path), relative_path, stringify(row.get("file_type")), stringify(row.get("type"))]).lower()
    if "namu" in path_text:
        return "TEXT_NAMU"
    if ".xlsx" in path_text or "xlsx" in path_text:
        return "XLSX"
    if ".pdf" in path_text or "pdf" in path_text:
        return "PDF_CONTENT"
    if any(ext in path_text for ext in (".jpg", ".jpeg", ".png", ".tif", ".tiff")):
        return "OCR_IMAGE"
    if ".ttf" in path_text or ".otf" in path_text or "font" in path_text:
        return "FONT"
    if value:
        return value
    return "UNKNOWN"


def source_family(
    domain: str,
    source_page: str,
    download_url: str,
    row: Mapping[str, Any],
    lane: str,
) -> str:
    text = " ".join([domain, source_page, download_url, stringify(row.get("title")), stringify(row.get("notes"))]).lower()
    if "aihub.or.kr" in text or "ai hub" in text or "ai허브" in text:
        return "AI_HUB"
    if "data.go.kr" in domain:
        return "PUBLIC_DATA_PORTAL"
    if "data.seoul.go.kr" in domain:
        return "SEOUL_OPEN_DATA"
    if "kosis.kr" in domain:
        return "KOSIS"
    if "prism.go.kr" in domain:
        return "PRISM"
    if "dart.fss.or.kr" in domain or "opendart" in domain:
        return "DART"
    if "namu.wiki" in domain:
        return "NAMU"
    if "commons.wikimedia.org" in domain:
        return "WIKIMEDIA_COMMONS"
    if "huggingface.co" in domain:
        return "HUGGING_FACE"
    if "guillaumejaume.github.io" in domain or "funsd" in text:
        return "FUNSD"
    if "github.com" in domain and "paddleocr" in text:
        return "PADDLEOCR_GITHUB"
    if any(public_domain in domain for public_domain in ("acrc.go.kr", "kepco.co.kr", "lh.or.kr", "alio.go.kr", "smartcity.go.kr", "ggc.go.kr", "naju.go.kr")):
        return "PUBLIC_INSTITUTION"
    if lane in FONT_LANES:
        return "FONT_ARCHIVE"
    if not domain:
        return "UNKNOWN_SOURCE"
    return "OTHER_SOURCE"


def kosis_restricted_scope(row: Mapping[str, Any]) -> bool:
    text = identity_text(row).lower()
    return any(token in text for token in ("oecd", "imf", "worldbank", "world bank", "국제", "international"))


def group_by(rows: Sequence[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = stringify(row.get(field))
        if value:
            grouped[value].append(row)
    return grouped


def duplicate_group_summary(rows: Sequence[Mapping[str, Any]], group_field: str, value_field: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        group_id = stringify(row.get(group_field))
        if group_id:
            grouped[group_id].append(row)
    return [
        {
            "group_id": group_id,
            "row_count": len(group_rows),
            "value": stringify(group_rows[0].get(value_field)),
            "lanes": counter_dict(row["lane"] for row in group_rows),
            "manifest_sources": sorted({str(row["manifest_source_path"]) for row in group_rows}),
        }
        for group_id, group_rows in sorted(grouped.items())
    ]


def resolve_path(raw: str | Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def repo_relative(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(resolved).replace("\\", "/")


def first_value(row: Mapping[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        if key in row and stringify(row.get(key)):
            return stringify(row.get(key))
    lower_map = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lower_map.get(key.lower())
        if stringify(value):
            return stringify(value)
    return ""


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return stringify(value)


def truthy(value: Any) -> bool:
    text = stringify(value).lower()
    return bool(text and text not in {"0", "false", "none", "null", "[]", "{}"})


def normalize_path(path: str) -> str:
    text = stringify(path).replace("/", "\\")
    while "\\\\" in text:
        text = text.replace("\\\\", "\\")
    return text.strip("\\")


def domain_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return ""
    return (parsed.netloc or "").lower()


def url_from_text(text: str) -> str:
    match = re.search(r"https?://[^\s,;)]+", text)
    return match.group(0) if match else ""


def regex_value(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def stable_hash(text: str, *, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:length]


def identity_text(row: Mapping[str, Any], fields: Sequence[str] = ("title", "relative_path", "normalized_path", "source_page")) -> str:
    return " ".join(stringify(row.get(field)) for field in fields if stringify(row.get(field)))


def has_mojibake(text: str) -> bool:
    return bool(MOJIBAKE_RE.search(text or ""))


def field_has_license_hint(field: str) -> bool:
    lowered = field.lower()
    return any(hint in lowered for hint in LICENSE_FIELD_HINTS)


def collected_at_issue(row: Mapping[str, Any]) -> bool:
    value = stringify(row.get("collected_at"))
    if not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return True
    return False


def coverage(count: int, total: int) -> dict[str, Any]:
    return {"count": count, "total": total, "rate": rate(count, total)}


def rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 6)


def counter_dict(values: Iterable[Any]) -> dict[str, int]:
    counter = Counter(stringify(value) or "UNKNOWN" for value in values)
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def top_counter_label(counter: Mapping[str, int]) -> str:
    if not counter:
        return "UNKNOWN"
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]


def markdown_counter(title: str, counter: Mapping[str, int]) -> list[str]:
    lines = [f"### {title}", ""]
    if not counter:
        return lines + ["- None"]
    for key, value in counter.items():
        lines.append(f"- `{key}`: `{value}`")
    return lines


def preview(text: str, max_chars: int = 240) -> str:
    return re.sub(r"\s+", " ", stringify(text))[:max_chars]


def append_note(existing: str, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing} {note}"


def license_name_from_text(text: str, *, default: str) -> str:
    lowered = text.lower()
    if "cc by-nc-sa" in lowered:
        return "CC BY-NC-SA"
    if "cc by-nc-nd" in lowered:
        return "CC BY-NC-ND"
    if "cc by-sa" in lowered:
        return "CC BY-SA"
    if "cc by" in lowered:
        return "CC BY"
    if "cc0" in lowered:
        return "CC0"
    if "apache" in lowered:
        return "Apache-2.0"
    if "gpl-3.0" in lowered or "gpl 3" in lowered:
        return "GPL-3.0"
    if "mit license" in lowered:
        return "MIT"
    return default


def license_type_from_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9.+-]+", "_", name).strip("_").upper()


def boolean_license_fields() -> set[str]:
    return {
        "attribution_required",
        "commercial_use_allowed",
        "noncommercial_use_allowed",
        "redistribution_allowed",
        "derivative_allowed",
        "no_derivatives",
        "third_party_transfer_prohibited",
        "internal_eval_allowed",
        "embedding_allowed",
        "vector_db_internal_allowed",
        "ocr_processing_allowed",
        "vlm_processing_allowed",
        "benchmark_eval_allowed",
        "public_report_allowed",
        "public_release_allowed",
        "requires_user_license_review",
    }


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
