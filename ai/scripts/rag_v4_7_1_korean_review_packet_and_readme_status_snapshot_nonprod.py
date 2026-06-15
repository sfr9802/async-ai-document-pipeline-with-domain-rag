from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod as v47


ROOT = v47.ROOT
REPORT_DIR = v47.REPORT_DIR
STATUS_JSONL = v47.STATUS_JSONL
PROGRESS_DOC = v47.PROGRESS_DOC
MEASUREMENTS_DOC = v47.MEASUREMENTS_DOC
TRIAGE_DOC = v47.TRIAGE_DOC
README = v47.README
EVAL_README = v47.EVAL_README
SCRIPTS_README = ROOT / "ai" / "scripts" / "README.md"

V4_NAME = v47.V4_NAME
V4_RUN_FAMILY = v47.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod"
EVENT_TYPE = "diagnostic_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod"
STATUS = "DIAGNOSTIC_V4_7_1_KOREAN_REVIEW_PACKET_AND_README_STATUS_SNAPSHOT_NONPROD_READY"
REPORT_SCHEMA_VERSION = "rag_v4_7_1_korean_review_packet_and_readme_status_snapshot_report_v1"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"
REVIEW_PACKET_XLSX = OUTPUT_DIR / "review_packet_ko.xlsx"
REVIEW_PACKET_CSV = OUTPUT_DIR / "review_packet_ko.csv"
REVIEW_PACKET_JSONL = OUTPUT_DIR / "review_packet_ko.jsonl"
ACTUAL_QUERY_RESPONSE_EXAMPLES_CSV = OUTPUT_DIR / "actual_query_llm_response_examples_ko.csv"
REVIEW_GUIDELINES = OUTPUT_DIR / "review_guidelines_ko.md"
REVIEW_SUMMARY_JSON = OUTPUT_DIR / "review_summary_ko.json"

V4_7_SOURCE_RUN_ID = v47.RUN_ID
V3_22_RUN_ID = "official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod"
V3_22_REPORT_JSON = REPORT_DIR / "quality" / V3_22_RUN_ID / "report.json"
V4_1_RUN_ID = "official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod"
V4_1_REPORT_JSON = REPORT_DIR / "quality" / V4_1_RUN_ID / "report.json"
V4_2_RUN_ID = "official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod"
V4_2_REPORT_JSON = REPORT_DIR / "quality" / V4_2_RUN_ID / "report.json"
V4_3_RUN_ID = "official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod"
V4_3_REPORT_JSON = REPORT_DIR / "quality" / V4_3_RUN_ID / "report.json"

EXPECTED_V4_7_MANIFEST_SHA256 = "15b2f5f61a03bf588bf49d74a95a11259e2a6a83c0a32a727625344cae7af58c"
SOURCE_COLLECTION_MANIFEST_CSV = Path(
    r"D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\source_collection_20260510\manifest.csv"
)
NOT_SUPPLIED = "__not_supplied_by_v4_7_registration_manifest__"
SOURCE_MANIFEST_MISSING = "__source_collection_manifest_match_missing__"

KOREAN_REVIEW_COLUMNS = [
    "검수상태",
    "소스계열",
    "후보ID",
    "질의ID",
    "질의문",
    "질의자연성",
    "질의승인",
    "질의보존성",
    "관련성라벨",
    "답변가능성라벨",
    "기대답변_한국어",
    "근거판단_한국어",
    "근거위치_확인",
    "공식분모포함판단",
    "제외사유",
    "정책메모",
    "검수자",
    "검수일시",
    "재검수필요",
]

MACHINE_CONTEXT_COLUMNS = [
    "source_family",
    "candidate_id_hash",
    "query_id_hash",
    "document_or_workbook_identity_hash",
    "source_identity_kind",
    "source_disjointness_gate",
    "query_fidelity_included",
    "leakage_bucket",
    "prior_identity_collision",
    "manifest_sha256",
    "source_manifest_match_status",
    "source_manifest_sha256",
    "source_manifest_lane",
    "source_manifest_subtype",
    "source_manifest_role",
    "source_manifest_title",
    "source_manifest_relative_path",
    "source_manifest_bytes",
    "source_manifest_source_page",
    "source_manifest_download_url",
    "source_manifest_notes",
    "source_manifest_collected_at",
    "source_preview_redacted",
    "evidence_preview_redacted",
    "locator_preview_redacted",
    "page_or_sheet_locator_redacted",
    "machine_notes",
    "source_report_run_id",
]

REVIEW_COLUMNS = KOREAN_REVIEW_COLUMNS + MACHINE_CONTEXT_COLUMNS

EXCLUSION_REASONS = [
    "질의의도불명확",
    "근거부족",
    "관련성부족",
    "답변불가",
    "중복질의",
    "문서정체성불명확",
    "워크북정체성불명확",
    "누출위험",
    "경로노출위험",
    "소스불일치",
    "범위과대",
    "정책판단필요",
    "기타",
]

SHEET_NAMES = ["검수_대상_전체", "PDF_검수", "XLSX_검수", "라벨_가이드", "제외_사유_가이드", "요약"]
ALLOWED_ARTIFACT_NAMES = {
    "actual_query_llm_response_examples_ko.csv",
    "report.json",
    "review_packet_ko.xlsx",
    "review_packet_ko.csv",
    "review_packet_ko.jsonl",
    "review_guidelines_ko.md",
    "review_summary_ko.json",
}


def clean(value: Any) -> str:
    return v47.clean(value)


def utc_now() -> str:
    return v47.utc_now()


def repo_relative(path: Path) -> str:
    return v47.repo_relative(path)


def sha256_file(path: Path) -> str:
    return v47.sha256_file(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v47.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v47.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v47.write_jsonl(path, rows)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _artifact_paths(output_dir: Path) -> dict[str, str]:
    paths = {
        "report_json": output_dir / "report.json",
        "review_packet_ko_xlsx": output_dir / "review_packet_ko.xlsx",
        "review_packet_ko_csv": output_dir / "review_packet_ko.csv",
        "review_packet_ko_jsonl": output_dir / "review_packet_ko.jsonl",
        "actual_query_llm_response_examples_ko_csv": output_dir / "actual_query_llm_response_examples_ko.csv",
        "review_guidelines_ko_md": output_dir / "review_guidelines_ko.md",
        "review_summary_ko_json": output_dir / "review_summary_ko.json",
    }
    if output_dir == OUTPUT_DIR:
        return {key: repo_relative(path) for key, path in paths.items()}
    return {key: path.as_posix() for key, path in paths.items()}


def _source_identity(row: Mapping[str, Any], family: str) -> tuple[str, str]:
    if family == "PDF":
        return "PDF_source_document", clean(row.get("source_document_id") or row.get("document_id"))
    if family == "XLSX":
        return "XLSX_workbook", clean(row.get("workbook_id"))
    return "unsupported", ""


def _identity_manifest_sha256(identity: str) -> str:
    match = re.search(r"([0-9a-f]{64})$", clean(identity))
    if not match:
        return ""
    return match.group(1)


def _bounded(value: Any, *, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", clean(value)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def read_source_collection_manifest(path: Path | None = SOURCE_COLLECTION_MANIFEST_CSV) -> dict[str, dict[str, str]]:
    if path is None or not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        clean(row.get("sha256")): {key: clean(value) for key, value in row.items()}
        for row in rows
        if clean(row.get("sha256"))
    }


def _manifest_field(metadata: Mapping[str, str], key: str) -> str:
    return clean(metadata.get(key))


def _source_manifest_context(identity: str, source_manifest_rows: Mapping[str, Mapping[str, str]]) -> dict[str, str]:
    manifest_sha256 = _identity_manifest_sha256(identity)
    metadata = source_manifest_rows.get(manifest_sha256, {})
    if not metadata:
        return {
            "source_manifest_match_status": "missing",
            "source_manifest_sha256": manifest_sha256,
            "source_manifest_lane": "",
            "source_manifest_subtype": "",
            "source_manifest_role": "",
            "source_manifest_title": "",
            "source_manifest_relative_path": "",
            "source_manifest_bytes": "",
            "source_manifest_source_page": "",
            "source_manifest_download_url": "",
            "source_manifest_notes": "",
            "source_manifest_collected_at": "",
            "source_preview_redacted": SOURCE_MANIFEST_MISSING,
            "evidence_preview_redacted": SOURCE_MANIFEST_MISSING,
            "locator_preview_redacted": SOURCE_MANIFEST_MISSING,
            "page_or_sheet_locator_redacted": SOURCE_MANIFEST_MISSING,
        }
    title = _manifest_field(metadata, "title")
    lane = _manifest_field(metadata, "lane")
    subtype = _manifest_field(metadata, "subtype")
    role = _manifest_field(metadata, "role")
    notes = _manifest_field(metadata, "notes")
    source_page = _manifest_field(metadata, "source_page")
    download_url = _manifest_field(metadata, "download_url")
    relative_path = _manifest_field(metadata, "relative_path")
    return {
        "source_manifest_match_status": "matched",
        "source_manifest_sha256": manifest_sha256,
        "source_manifest_lane": lane,
        "source_manifest_subtype": subtype,
        "source_manifest_role": role,
        "source_manifest_title": title,
        "source_manifest_relative_path": relative_path,
        "source_manifest_bytes": _manifest_field(metadata, "bytes"),
        "source_manifest_source_page": source_page,
        "source_manifest_download_url": download_url,
        "source_manifest_notes": notes,
        "source_manifest_collected_at": _manifest_field(metadata, "collected_at"),
        "source_preview_redacted": _bounded(f"title={title}; lane={lane}; subtype={subtype}; role={role}"),
        "evidence_preview_redacted": _bounded(f"manifest_notes={notes}") if notes else "manifest_notes=",
        "locator_preview_redacted": _bounded(f"source_page={source_page}; download_url={download_url}"),
        "page_or_sheet_locator_redacted": _bounded(f"source_collection_relative_path={relative_path}"),
    }


def _review_row(
    row: Mapping[str, Any],
    *,
    source_manifest_rows: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, str]:
    family = clean(row.get("source_family")).upper()
    candidate_id = clean(row.get("candidate_id"))
    query_id = clean(row.get("query_id"))
    identity_kind, identity = _source_identity(row, family)
    manifest_context = _source_manifest_context(identity, source_manifest_rows or {})
    korean = {
        "검수상태": "미검수",
        "소스계열": family,
        "후보ID": candidate_id,
        "질의ID": query_id,
        "질의문": "",
        "질의자연성": "판단불가",
        "질의승인": "보류",
        "질의보존성": "의도불명확",
        "관련성라벨": "보류",
        "답변가능성라벨": "보류",
        "기대답변_한국어": "",
        "근거판단_한국어": "",
        "근거위치_확인": "보류",
        "공식분모포함판단": "보류",
        "제외사유": "",
        "정책메모": "",
        "검수자": "",
        "검수일시": "",
        "재검수필요": "보류",
    }
    machine = {
        "source_family": family,
        "candidate_id_hash": _sha256_text(candidate_id),
        "query_id_hash": _sha256_text(query_id),
        "document_or_workbook_identity_hash": _sha256_text(f"{family}:{identity}"),
        "source_identity_kind": identity_kind,
        "source_disjointness_gate": "pass" if row.get("disjoint_from_prior") is True else "review",
        "query_fidelity_included": "true" if row.get("query_fidelity_included") is True else "false",
        "leakage_bucket": "none",
        "prior_identity_collision": "false",
        "manifest_sha256": EXPECTED_V4_7_MANIFEST_SHA256,
        **manifest_context,
        "machine_notes": (
            "source_collection manifest.csv의 sha256 매칭으로 실제 source metadata를 채웠습니다. "
            "v4_7 등록 manifest/registration report에는 실제 질의문이나 LLM 답변 artifact가 없으므로 "
            "질의문, 기대답변_한국어, 근거판단_한국어는 생성하지 않고 사람 검수 보류로 남깁니다."
        ),
        "source_report_run_id": V4_7_SOURCE_RUN_ID,
    }
    return {column: str({**korean, **machine}.get(column, "")) for column in REVIEW_COLUMNS}


def build_review_rows(
    candidate_manifest_path: Path,
    *,
    source_collection_manifest_path: Path | None = SOURCE_COLLECTION_MANIFEST_CSV,
) -> list[dict[str, str]]:
    rows = read_jsonl(candidate_manifest_path)
    source_manifest_rows = read_source_collection_manifest(source_collection_manifest_path)
    review_rows = [
        _review_row(row, source_manifest_rows=source_manifest_rows)
        for row in rows
        if clean(row.get("source_family")).upper() in {"PDF", "XLSX"}
    ]
    return sorted(review_rows, key=lambda row: (row["소스계열"], row["후보ID"], row["질의ID"]))


def _source_report(path: Path) -> dict[str, Any]:
    exists = path.exists()
    return {
        "path": repo_relative(path),
        "exists": exists,
        "sha256": sha256_file(path) if exists else "",
        "report": read_json(path) if exists else {},
    }


def _metric(source: Mapping[str, Any], key: str, default: Any = 0) -> Any:
    metrics = source.get("metrics") if isinstance(source.get("metrics"), Mapping) else {}
    if key in source:
        return source.get(key)
    return metrics.get(key, default)


def extract_actual_llm_response_examples(limit: int = 10) -> list[dict[str, str]]:
    report = read_json(V3_22_REPORT_JSON)
    examples: list[dict[str, str]] = []
    for index, row in enumerate(report.get("per_query", [])):
        if row.get("llm_invoked") is not True:
            continue
        if row.get("answer_allowed_by_policy") is not True:
            continue
        if clean(row.get("response_policy_bucket")) != "ANSWER_ALLOWED":
            continue
        if clean(row.get("evidence_truth_source")) != "source_atom_evidence_bundle":
            continue
        parsed = clean(row.get("parsed_final_answer"))
        raw_hash = clean(row.get("raw_llm_response_sha256"))
        prompt_hash = clean(row.get("prompt_sha256"))
        query = clean(row.get("actual_input_query"))
        if not (parsed and query and (raw_hash or prompt_hash)):
            continue
        examples.append(
            {
                "source_run": V3_22_RUN_ID,
                "source_family": clean(row.get("source_family")) or "XLSX",
                "query_id": clean(row.get("query_id")),
                "actual_user_query": query,
                "response_policy_bucket": "ANSWER_ALLOWED",
                "evidence_truth_source": "source_atom_evidence_bundle",
                "parsed_final_answer_or_sanitized_excerpt": re.sub(r"\s+", " ", parsed).strip(),
                "raw_response_hash": raw_hash,
                "prompt_hash": prompt_hash,
                "evidence_source": f"{repo_relative(V3_22_REPORT_JSON)} $.per_query[{index}]",
                "diagnostic_boundary": "diagnostic_only_non_official_not_v4_7_output",
            }
        )
        if len(examples) >= limit:
            break
    return examples


def _count_by_family(rows: Sequence[Mapping[str, str]]) -> dict[str, int]:
    counts = Counter(row["소스계열"] for row in rows)
    return {"PDF": counts.get("PDF", 0), "XLSX": counts.get("XLSX", 0), "TEXT": counts.get("TEXT", 0)}


def _source_manifest_summary(
    review_rows: Sequence[Mapping[str, str]],
    *,
    source_collection_manifest_path: Path | None,
) -> dict[str, Any]:
    matched_rows = [row for row in review_rows if row.get("source_manifest_match_status") == "matched"]
    missing_rows = [row for row in review_rows if row.get("source_manifest_match_status") != "matched"]
    path_exists = source_collection_manifest_path is not None and source_collection_manifest_path.exists()
    return {
        "source_collection_manifest_available": bool(path_exists),
        "source_collection_manifest_path_redacted": True,
        "source_collection_manifest_sha256": sha256_file(source_collection_manifest_path) if path_exists else "",
        "source_manifest_metadata_rows_matched": len(matched_rows),
        "source_manifest_metadata_rows_missing": len(missing_rows),
        "source_manifest_unique_sources_matched": len({row.get("source_manifest_sha256") for row in matched_rows}),
        "source_manifest_unique_sources_missing": len({row.get("source_manifest_sha256") for row in missing_rows}),
        "review_packet_source_rows_have_source_manifest_metadata": len(matched_rows) > 0,
    }


def _review_summary(
    review_rows: Sequence[Mapping[str, str]],
    *,
    source_collection_manifest_path: Path | None = SOURCE_COLLECTION_MANIFEST_CSV,
) -> dict[str, Any]:
    counts = _count_by_family(review_rows)
    source_summary = _source_manifest_summary(
        review_rows,
        source_collection_manifest_path=source_collection_manifest_path,
    )
    return {
        "schema_version": f"{RUN_ID}_review_summary_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "human_review_only": True,
        "diagnostic_only": True,
        "review_packet_row_count": len(review_rows),
        "review_packet_counts_by_family": counts,
        "user_decision_columns_defaulted": True,
        "user_decision_defaults": {
            "검수상태": "미검수",
            "질의승인": "보류",
            "관련성라벨": "보류",
            "답변가능성라벨": "보류",
            "공식분모포함판단": "보류",
            "기대답변_한국어": "",
            "근거판단_한국어": "",
        },
        "review_packet_source_rows_have_actual_query_text": False,
        "review_packet_source_rows_have_evidence_context": False,
        "review_packet_source_rows_have_source_manifest_metadata": source_summary[
            "review_packet_source_rows_have_source_manifest_metadata"
        ],
        "source_manifest_metadata_rows_matched": source_summary["source_manifest_metadata_rows_matched"],
        "source_manifest_metadata_rows_missing": source_summary["source_manifest_metadata_rows_missing"],
        "query_text_source": "not_supplied_by_v4_7_registration_manifest",
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "live_db_index_cache_readiness": False,
    }


def _diagnostic_snapshot() -> dict[str, Any]:
    v3_22 = _source_report(V3_22_REPORT_JSON)
    v4_1 = _source_report(V4_1_REPORT_JSON)
    v4_2 = _source_report(V4_2_REPORT_JSON)
    v4_3 = _source_report(V4_3_REPORT_JSON)
    v3_22_report = v3_22["report"]
    v4_1_report = v4_1["report"]
    v4_2_report = v4_2["report"]
    v4_3_report = v4_3["report"]
    return {
        "v3_22": {
            "run_id": V3_22_RUN_ID,
            "report_json": v3_22["path"],
            "report_sha256": v3_22["sha256"],
            "report_row_count": int(_metric(v3_22_report, "report_row_count", 0) or 0),
            "xlsx_answer_allowed_count": int(_metric(v3_22_report, "xlsx_answer_allowed_count", 0) or 0),
            "llm_invoked_count": int(_metric(v3_22_report, "llm_invoked_count", 0) or 0),
            "display_value_used_count": int(_metric(v3_22_report, "display_value_used_count", 0) or 0),
            "raw_value_fallback_count": int(_metric(v3_22_report, "raw_value_fallback_count", 0) or 0),
            "runtime_contract_violation_count": int(_metric(v3_22_report, "runtime_contract_violation_count", 0) or 0),
            "vector_payload_evidence_truth_violation_count": int(
                _metric(v3_22_report, "vector_payload_evidence_truth_violation_count", 0) or 0
            ),
            "official_metric_input_rows": int(_metric(v3_22_report, "official_metric_input_rows", 0) or 0),
        },
        "v4_1": {
            "run_id": V4_1_RUN_ID,
            "report_json": v4_1["path"],
            "report_sha256": v4_1["sha256"],
            "persisted_xlsx_sourceatom_display_metadata_rows": int(
                _metric(v4_1_report, "persisted_xlsx_sourceatom_display_metadata_rows", 0) or 0
            ),
            "persisted_display_value_available_count": int(
                _metric(v4_1_report, "persisted_display_value_available_count", 0) or 0
            ),
            "persisted_raw_value_fallback_count": int(
                _metric(v4_1_report, "persisted_raw_value_fallback_count", 0) or 0
            ),
            "runtime_contract_violation_count": int(_metric(v4_1_report, "runtime_contract_violation_count", 0) or 0),
            "vector_payload_evidence_truth_violation_count": int(
                _metric(v4_1_report, "vector_payload_evidence_truth_violation_count", 0) or 0
            ),
            "official_metric_input_rows": int(_metric(v4_1_report, "official_metric_input_rows", 0) or 0),
        },
        "v4_2": {
            "run_id": V4_2_RUN_ID,
            "report_json": v4_2["path"],
            "report_sha256": v4_2["sha256"],
            "seen_reference_rows": int((_metric(v4_2_report, "per_query_rows", {}) or {}).get("row_count") or 0),
            "official_metric_input_rows": int(_metric(v4_2_report, "official_metric_input_rows", 0) or 0),
        },
        "v4_3": {
            "run_id": V4_3_RUN_ID,
            "report_json": v4_3["path"],
            "report_sha256": v4_3["sha256"],
            "pdf_file_identity_rows": int(_metric(v4_3_report, "pdf_file_identity_rows", 0) or 0),
            "seen_reference_rows": int((_metric(v4_3_report, "per_query_rows", {}) or {}).get("row_count") or 0),
            "official_metric_input_rows": int(_metric(v4_3_report, "official_metric_input_rows", 0) or 0),
        },
    }


def build_artifacts(
    *,
    candidate_manifest_path: Path,
    output_dir: Path = OUTPUT_DIR,
    source_collection_manifest_path: Path | None = SOURCE_COLLECTION_MANIFEST_CSV,
) -> dict[str, Any]:
    v4_7_artifacts = v47.build_artifacts(candidate_manifest_path=candidate_manifest_path)
    v47.check_report(v4_7_artifacts["report"])
    review_rows = build_review_rows(
        candidate_manifest_path,
        source_collection_manifest_path=source_collection_manifest_path,
    )
    counts = _count_by_family(review_rows)
    source_manifest_summary = _source_manifest_summary(
        review_rows,
        source_collection_manifest_path=source_collection_manifest_path,
    )
    summary = _review_summary(
        review_rows,
        source_collection_manifest_path=source_collection_manifest_path,
    )
    examples = extract_actual_llm_response_examples(limit=10)
    diagnostic_snapshot = _diagnostic_snapshot()
    registration = v4_7_artifacts["report"]["preofficial_external_holdout_candidate_manifest_registration"]
    artifact_paths = _artifact_paths(output_dir)
    manifest_sha256_actual = sha256_file(candidate_manifest_path)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "non_production": True,
        "human_review_only": True,
        "generation_source": False,
        "not_silver_source": True,
        "not_gold_mutation": True,
        "not_official_metric_input": True,
        "not_training_dataset": True,
        "not_promotion_evidence": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "v4_7_official_metric_gate_opened": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "live_db_index_cache_readiness": False,
        "candidate_manifest_available": True,
        "candidate_manifest_sha256": EXPECTED_V4_7_MANIFEST_SHA256,
        "candidate_manifest_sha256_verified_against_expected": manifest_sha256_actual == EXPECTED_V4_7_MANIFEST_SHA256,
        "candidate_manifest_actual_sha256": manifest_sha256_actual,
        "candidate_manifest_path_redacted": True,
        "source_report_run_id": V4_7_SOURCE_RUN_ID,
        "source_report_status": clean(v4_7_artifacts["report"]["status"]),
        "source_report_registration_gate_passed": bool(v4_7_artifacts["report"]["registration_gate_passed"]),
        "source_report_artifact": repo_relative(v47.REPORT_JSON),
        "source_report_artifact_sha256": sha256_file(v47.REPORT_JSON) if v47.REPORT_JSON.exists() else "",
        "v4_7_registration_snapshot": {
            "status": clean(v4_7_artifacts["report"]["status"]),
            "candidate_rows_registered": int(registration.get("candidate_rows_registered") or 0),
            "candidate_counts_by_family": dict(registration.get("candidate_counts_by_family") or {}),
            "accepted_candidate_counts_by_family": dict(registration.get("accepted_candidate_counts_by_family") or {}),
            "accepted_pdf_holdout_candidates": int(registration.get("accepted_pdf_holdout_candidates") or 0),
            "accepted_xlsx_holdout_candidates": int(registration.get("accepted_xlsx_holdout_candidates") or 0),
            "rejected_candidate_count": int(registration.get("rejected_candidate_count") or 0),
            "source_identity_collision_count": int(registration.get("source_identity_collision_count") or 0),
            "real_query_fidelity_included_counts": dict(registration.get("real_query_fidelity_included_counts") or {}),
            "preofficial_candidate_thresholds_met": bool(registration.get("preofficial_candidate_thresholds_met")),
            "real_holdout_sufficient": False,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "v4_7_official_metric_gate_opened": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_db_index_cache_readiness": False,
        },
        "review_packet_row_count": len(review_rows),
        "review_packet_counts_by_family": counts,
        "review_packet_source_rows_have_actual_query_text": False,
        "review_packet_source_rows_have_evidence_context": False,
        "review_packet_source_rows_have_source_manifest_metadata": source_manifest_summary[
            "review_packet_source_rows_have_source_manifest_metadata"
        ],
        "source_collection_manifest_metadata": source_manifest_summary,
        "source_manifest_metadata_rows_matched": source_manifest_summary["source_manifest_metadata_rows_matched"],
        "source_manifest_metadata_rows_missing": source_manifest_summary["source_manifest_metadata_rows_missing"],
        "source_manifest_unique_sources_matched": source_manifest_summary["source_manifest_unique_sources_matched"],
        "source_manifest_unique_sources_missing": source_manifest_summary["source_manifest_unique_sources_missing"],
        "query_text_source": "not_supplied_by_v4_7_registration_manifest",
        "review_packet_artifacts_created": {
            "report_json": True,
            "review_packet_ko_xlsx": True,
            "review_packet_ko_csv": True,
            "review_packet_ko_jsonl": True,
            "actual_query_llm_response_examples_ko_csv": True,
            "review_guidelines_ko_md": True,
            "review_summary_ko_json": True,
        },
        "user_decision_columns": list(KOREAN_REVIEW_COLUMNS),
        "machine_context_columns": list(MACHINE_CONTEXT_COLUMNS),
        "user_decision_columns_defaulted": True,
        "user_decision_column_policy": {
            "검수상태": ["미검수", "승인", "수정필요", "제외", "보류"],
            "관련성라벨": ["정확근거", "보조근거", "주제관련", "무관", "보류"],
            "답변가능성라벨": ["완전답변가능", "부분답변가능", "관련있지만답변불가", "무관", "보류"],
            "공식분모포함판단": ["포함", "제외", "보류"],
            "제외사유": list(EXCLUSION_REASONS),
        },
        "actual_llm_response_example_source_run_id": V3_22_RUN_ID,
        "actual_llm_response_examples": examples,
        "diagnostic_snapshot": diagnostic_snapshot,
        "artifact_paths": artifact_paths,
        "candidate_manifest_jsonl_created": False,
        "qrels_jsonl_created": False,
        "gold_jsonl_created": False,
        "labels_jsonl_created": False,
        "expected_answers_jsonl_created": False,
        "supporting_evidence_jsonl_created": False,
        "training_manifest_jsonl_created": False,
        "prompt_manifest_jsonl_created": False,
        "raw_response_payload_jsonl_created": False,
        "review_summary": summary,
        "guardrails": {
            "raw_local_paths_absent": True,
            "raw_source_identities_absent": True,
            "source_manifest_metadata_projected_from_sha256_match": True,
            "protected_oracle_fields_absent": True,
            "gold_qrels_expected_supporting_labels_mutated": False,
            "official_metric_input_rows_created": 0,
            "ft_a_execution": False,
            "fine_tuning": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_db_index_cache_readiness": False,
        },
        "remaining_user_owned_actions": [
            "actual Korean query text and answer/evidence context must be supplied or adjudicated by the user before labels can be final",
            "gold/qrels, expected answers, supporting evidence, relevance, answerability, denominator inclusion, and promotion policy remain user-owned",
        ],
        "readiness_decision": "korean_human_review_packet_prepared_official_metric_closed",
    }
    return {
        "report": report,
        "review_rows": review_rows,
        "review_summary": summary,
        "actual_llm_response_examples": examples,
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_actual_examples_csv(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    columns = [
        "source_run",
        "source_family",
        "query_id",
        "실제질의문",
        "실제답변",
        "response_policy_bucket",
        "evidence_truth_source",
        "raw_response_hash",
        "prompt_hash",
        "evidence_source",
        "diagnostic_boundary",
    ]
    projected_rows = [
        {
            "source_run": row["source_run"],
            "source_family": row["source_family"],
            "query_id": row["query_id"],
            "실제질의문": row["actual_user_query"],
            "실제답변": row["parsed_final_answer_or_sanitized_excerpt"],
            "response_policy_bucket": row["response_policy_bucket"],
            "evidence_truth_source": row["evidence_truth_source"],
            "raw_response_hash": row["raw_response_hash"],
            "prompt_hash": row["prompt_hash"],
            "evidence_source": row["evidence_source"],
            "diagnostic_boundary": row["diagnostic_boundary"],
        }
        for row in rows
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(projected_rows)


def _cell_ref(row_index: int, col_index: int) -> str:
    letters = ""
    col = col_index
    while col:
        col, rem = divmod(col - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row_index}"


def _worksheet_xml(rows: Sequence[Sequence[Any]]) -> str:
    sheet_rows: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        cells: list[str] = []
        for col_index, value in enumerate(row, start=1):
            text = "" if value is None else str(value)
            ref = _cell_ref(row_index, col_index)
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index}">' + "".join(cells) + "</row>")
    max_col = max((len(row) for row in rows), default=1)
    max_row = max(len(rows), 1)
    ref = f"A1:{_cell_ref(max_row, max_col)}"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        "<sheetData>"
        + "".join(sheet_rows)
        + f'</sheetData><autoFilter ref="{ref}"/></worksheet>'
    )


def _workbook_xml() -> str:
    sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(SHEET_NAMES, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets}</sheets></workbook>"
    )


def _content_types_xml() -> str:
    worksheets = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(SHEET_NAMES) + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{worksheets}</Types>"
    )


def _root_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )


def _workbook_rels_xml() -> str:
    rels = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(SHEET_NAMES) + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>'
    )


def _xlsx_rows(review_rows: Sequence[Mapping[str, str]], summary: Mapping[str, Any]) -> dict[str, list[list[Any]]]:
    labels = [
        ["구분", "라벨", "설명"],
        ["관련성라벨", "정확근거", "질의에 대한 답을 직접 산출할 수 있는 근거다."],
        ["관련성라벨", "보조근거", "답을 직접 산출하기에는 부족하지만, 답변 맥락을 보조한다."],
        ["관련성라벨", "주제관련", "같은 주제이지만 질의의 답을 판단하기에는 부족하다."],
        ["관련성라벨", "무관", "질의와 실질적으로 관련이 없다."],
        ["관련성라벨", "보류", "사람이 추가 확인해야 한다."],
        ["답변가능성라벨", "완전답변가능", "제공된 근거만으로 기대답변을 확정할 수 있다."],
        ["답변가능성라벨", "부분답변가능", "일부 답변은 가능하지만 누락이나 불확실성이 있다."],
        ["답변가능성라벨", "관련있지만답변불가", "관련 문맥은 있으나 질문에 답하기에는 근거가 부족하다."],
        ["답변가능성라벨", "무관", "관련 근거가 아니다."],
        ["답변가능성라벨", "보류", "사람이 추가 확인해야 한다."],
        ["공식분모포함판단", "포함", "공식 평가 denominator 후보로 사용할 수 있다."],
        ["공식분모포함판단", "제외", "공식 평가 denominator에서 제외해야 한다."],
        ["공식분모포함판단", "보류", "추가 정책 판단 필요."],
    ]
    summary_rows = [
        ["항목", "값"],
        ["status", summary["status"]],
        ["human_review_only", "true"],
        ["review_packet_row_count", summary["review_packet_row_count"]],
        ["PDF rows", summary["review_packet_counts_by_family"]["PDF"]],
        ["XLSX rows", summary["review_packet_counts_by_family"]["XLSX"]],
        ["TEXT rows", summary["review_packet_counts_by_family"]["TEXT"]],
        ["source_manifest_metadata_rows_matched", summary["source_manifest_metadata_rows_matched"]],
        ["source_manifest_metadata_rows_missing", summary["source_manifest_metadata_rows_missing"]],
        ["official_metric_input_rows", 0],
        ["promotion_evidence", "false"],
        ["ft_a_execution", "false"],
        ["fine_tuning", "false"],
        ["live_db_index_cache_readiness", "false"],
    ]
    all_rows = [REVIEW_COLUMNS] + [[row[column] for column in REVIEW_COLUMNS] for row in review_rows]
    pdf_rows = [REVIEW_COLUMNS] + [[row[column] for column in REVIEW_COLUMNS] for row in review_rows if row["소스계열"] == "PDF"]
    xlsx_rows = [REVIEW_COLUMNS] + [[row[column] for column in REVIEW_COLUMNS] for row in review_rows if row["소스계열"] == "XLSX"]
    exclusions = [["제외사유", "사용 기준"]] + [[reason, "제외로 판단한 경우에만 선택"] for reason in EXCLUSION_REASONS]
    return {
        "검수_대상_전체": all_rows,
        "PDF_검수": pdf_rows,
        "XLSX_검수": xlsx_rows,
        "라벨_가이드": labels,
        "제외_사유_가이드": exclusions,
        "요약": summary_rows,
    }


def _write_xlsx(path: Path, review_rows: Sequence[Mapping[str, str]], summary: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_payloads = _xlsx_rows(review_rows, summary)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _root_rels_xml())
        archive.writestr("xl/workbook.xml", _workbook_xml())
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml())
        for index, sheet_name in enumerate(SHEET_NAMES, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _worksheet_xml(sheet_payloads[sheet_name]))


def _guidelines_markdown(summary: Mapping[str, Any]) -> str:
    return f"""# v4_7_1 한국어 후보 검수 가이드

이 packet은 v4_7 pre-official external holdout candidate registration 결과를 사람이 검수하기 위한 자료입니다.
모든 결정은 human-review-only이며, Codex는 gold, qrels, expected answer, supporting evidence, 관련성, 답변가능성, 공식 denominator 포함 여부를 채우지 않았습니다.

## 검수 방법

1. `review_packet_ko.xlsx`의 `검수_대상_전체`, `PDF_검수`, `XLSX_검수` sheet에서 후보를 확인합니다.
2. `검수상태`, `질의승인`, `관련성라벨`, `답변가능성라벨`, `공식분모포함판단`, `제외사유`, `정책메모`, `검수자`, `검수일시`, `재검수필요`를 사람이 채웁니다.
3. `기대답변_한국어`와 `근거판단_한국어`는 user-owned gold/evidence 판단이므로 비워 둔 상태에서 시작합니다.
4. `source_manifest_*`와 redacted preview/locator columns는 `source_collection` manifest.csv의 SHA-256 매칭으로 채운 실제 소스 메타데이터입니다.
5. v4_7 등록 manifest에는 실제 질의문과 LLM 답변 artifact가 포함되지 않았으므로, 이 packet의 빈 `질의문`, `기대답변_한국어`, `근거판단_한국어`는 자동 생성하지 않습니다.

## 관련성라벨

- 정확근거: 질의에 대한 답을 직접 산출할 수 있는 근거다.
- 보조근거: 답을 직접 산출하기에는 부족하지만, 답변 맥락을 보조한다.
- 주제관련: 같은 주제이지만 질의의 답을 판단하기에는 부족하다.
- 무관: 질의와 실질적으로 관련이 없다.
- 보류: 사람이 추가 확인해야 한다.

## 답변가능성라벨

- 완전답변가능: 제공된 근거만으로 기대답변을 확정할 수 있다.
- 부분답변가능: 일부 답변은 가능하지만 누락이나 불확실성이 있다.
- 관련있지만답변불가: 관련 문맥은 있으나 질문에 답하기에는 근거가 부족하다.
- 무관: 관련 근거가 아니다.
- 보류: 사람이 추가 확인해야 한다.

## 공식분모포함판단

- 포함: 공식 평가 denominator 후보로 사용할 수 있다.
- 제외: 공식 평가 denominator에서 제외해야 한다.
- 보류: 추가 정책 판단 필요.

## 제외사유 allowed values

{chr(10).join(f"- {reason}" for reason in EXCLUSION_REASONS)}

## 경계

- human_review_only=true
- not_gold_mutation=true
- not_official_metric_input=true
- not_training_dataset=true
- not_promotion_evidence=true
- official_metric=false
- official_metric_input_rows=0
- FT-A execution=false
- fine_tuning=false
- live_db_index_cache_readiness=false

요약: PDF {summary["review_packet_counts_by_family"]["PDF"]} rows, XLSX {summary["review_packet_counts_by_family"]["XLSX"]} rows, TEXT {summary["review_packet_counts_by_family"]["TEXT"]} rows.
"""


def write_artifacts(artifacts: Mapping[str, Any], *, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    unexpected = {path.name for path in output_dir.iterdir() if path.is_file()} - ALLOWED_ARTIFACT_NAMES
    if unexpected:
        raise RuntimeError(f"unexpected v4_7_1 artifacts present: {sorted(unexpected)}")
    review_rows = list(artifacts["review_rows"])
    summary = dict(artifacts["review_summary"])
    report = dict(artifacts["report"])
    report["artifact_paths"] = _artifact_paths(output_dir)
    write_json(output_dir / "report.json", report)
    _write_csv(output_dir / "review_packet_ko.csv", review_rows)
    _write_actual_examples_csv(output_dir / "actual_query_llm_response_examples_ko.csv", artifacts["actual_llm_response_examples"])
    write_jsonl(output_dir / "review_packet_ko.jsonl", review_rows)
    write_json(output_dir / "review_summary_ko.json", summary)
    (output_dir / "review_guidelines_ko.md").write_text(_guidelines_markdown(summary), encoding="utf-8")
    _write_xlsx(output_dir / "review_packet_ko.xlsx", review_rows, summary)
    return report


def _contains_forbidden_text(payload: str) -> bool:
    forbidden = [
        r"\bD:/",
        r"\bD:\\",
        r"source_identity_key",
        r"v47_pdf_doc_sha_",
        r"v47_xlsx_workbook_sha_",
        r'"raw_llm_response"\s*:',
        r"prompt_payload",
        r"official_metric_input\.jsonl",
        r"training_dataset\.jsonl",
        r"training_dataset_path",
        r"checkpoint",
    ]
    return any(re.search(pattern, payload) for pattern in forbidden)


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise AssertionError("unexpected v4_7_1 report schema")
    if report.get("status") != STATUS:
        raise AssertionError("unexpected v4_7_1 status")
    for field in (
        "diagnostic_only",
        "human_review_only",
        "not_silver_source",
        "not_gold_mutation",
        "not_official_metric_input",
        "not_training_dataset",
        "not_promotion_evidence",
    ):
        if report.get(field) is not True:
            raise AssertionError(f"{field} must remain true")
    for field in (
        "generation_source",
        "official_metric",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "ft_a_execution",
        "fine_tuning",
        "live_db_index_cache_readiness",
        "candidate_manifest_jsonl_created",
        "qrels_jsonl_created",
        "gold_jsonl_created",
        "labels_jsonl_created",
        "expected_answers_jsonl_created",
        "supporting_evidence_jsonl_created",
        "training_manifest_jsonl_created",
        "prompt_manifest_jsonl_created",
        "raw_response_payload_jsonl_created",
    ):
        if report.get(field) is not False:
            raise AssertionError(f"{field} must remain false")
    if int(report.get("official_metric_input_rows") or 0) != 0:
        raise AssertionError("official_metric_input_rows must remain 0")
    if report.get("review_packet_row_count") != 204:
        raise AssertionError("review packet must cover 204 accepted candidates")
    if report.get("review_packet_counts_by_family") != {"PDF": 100, "XLSX": 104, "TEXT": 0}:
        raise AssertionError("review packet family counts drifted")
    matched = int(report.get("source_manifest_metadata_rows_matched") or 0)
    missing = int(report.get("source_manifest_metadata_rows_missing") or 0)
    if matched + missing != int(report.get("review_packet_row_count") or 0):
        raise AssertionError("source manifest metadata match accounting drifted")
    if report.get("query_text_source") != "not_supplied_by_v4_7_registration_manifest":
        raise AssertionError("query text source must remain explicit")
    examples = report.get("actual_llm_response_examples")
    if not isinstance(examples, list) or len(examples) != 10:
        raise AssertionError("expected 10 artifact-backed v3_22 examples")
    if any(example.get("source_run") != V3_22_RUN_ID for example in examples):
        raise AssertionError("actual response examples must come from v3_22")
    if any(example.get("diagnostic_boundary") != "diagnostic_only_non_official_not_v4_7_output" for example in examples):
        raise AssertionError("actual response examples must not be represented as v4_7 output")
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True)
    if _contains_forbidden_text(payload):
        raise AssertionError("forbidden raw path, source identity, prompt/response, training, or checkpoint text leaked")


def check_written_artifacts(output_dir: Path = OUTPUT_DIR) -> None:
    files = {path.name for path in output_dir.iterdir() if path.is_file()}
    if files != ALLOWED_ARTIFACT_NAMES:
        raise AssertionError(f"unexpected v4_7_1 artifact set: {sorted(files)}")
    report = read_json(output_dir / "report.json")
    check_report(report)
    rows = read_jsonl(output_dir / "review_packet_ko.jsonl")
    if len(rows) != 204:
        raise AssertionError("review_packet_ko.jsonl row count drifted")
    if any(set(row) != set(REVIEW_COLUMNS) for row in rows):
        raise AssertionError("review packet columns drifted")
    if any(row["검수상태"] != "미검수" for row in rows):
        raise AssertionError("검수상태 must default to 미검수")
    if any(row["질의문"] for row in rows):
        raise AssertionError("질의문 must remain blank because v4_7 did not supply actual query text")
    if any(row["source_manifest_match_status"] not in {"matched", "missing"} for row in rows):
        raise AssertionError("source manifest match status drifted")
    if any(not row["source_preview_redacted"] for row in rows):
        raise AssertionError("source preview column must be populated with manifest context or a closed marker")
    with (output_dir / "actual_query_llm_response_examples_ko.csv").open(encoding="utf-8-sig", newline="") as handle:
        actual_rows = list(csv.DictReader(handle))
    if len(actual_rows) != 10:
        raise AssertionError("actual query/response CSV must contain 10 artifact-backed examples")
    if any(not row.get("실제질의문") or not row.get("실제답변") for row in actual_rows):
        raise AssertionError("actual query/response CSV must include actual query and answer text")
    if any(row.get("source_run") != V3_22_RUN_ID for row in actual_rows):
        raise AssertionError("actual query/response CSV must be sourced from v3_22")
    if any(row.get("diagnostic_boundary") != "diagnostic_only_non_official_not_v4_7_output" for row in actual_rows):
        raise AssertionError("actual query/response CSV must not be represented as v4_7 output")
    text_payload = "\n".join(
        [
            (output_dir / "review_packet_ko.csv").read_text(encoding="utf-8-sig"),
            (output_dir / "actual_query_llm_response_examples_ko.csv").read_text(encoding="utf-8-sig"),
            (output_dir / "review_guidelines_ko.md").read_text(encoding="utf-8"),
            json.dumps(rows[:5], ensure_ascii=False, sort_keys=True),
        ]
    )
    if _contains_forbidden_text(text_payload):
        raise AssertionError("forbidden text leaked into review packet artifacts")
    with zipfile.ZipFile(output_dir / "review_packet_ko.xlsx") as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        for sheet in SHEET_NAMES:
            if sheet not in workbook:
                raise AssertionError(f"missing sheet {sheet}")


def update_status(report: Mapping[str, Any]) -> None:
    artifact_hashes = {
        "report_json_sha256": sha256_file(REPORT_JSON),
        "review_packet_ko_xlsx_sha256": sha256_file(REVIEW_PACKET_XLSX),
        "review_packet_ko_csv_sha256": sha256_file(REVIEW_PACKET_CSV),
        "review_packet_ko_jsonl_sha256": sha256_file(REVIEW_PACKET_JSONL),
        "actual_query_llm_response_examples_ko_csv_sha256": sha256_file(ACTUAL_QUERY_RESPONSE_EXAMPLES_CSV),
        "review_guidelines_ko_md_sha256": sha256_file(REVIEW_GUIDELINES),
        "review_summary_ko_json_sha256": sha256_file(REVIEW_SUMMARY_JSON),
    }
    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": artifact_hashes,
        "diagnostic_only": True,
        "human_review_only": True,
        "review_packet_row_count": report["review_packet_row_count"],
        "review_packet_counts_by_family": dict(report["review_packet_counts_by_family"]),
        "review_packet_source_rows_have_actual_query_text": False,
        "review_packet_source_rows_have_evidence_context": False,
        "review_packet_source_rows_have_source_manifest_metadata": report[
            "review_packet_source_rows_have_source_manifest_metadata"
        ],
        "source_manifest_metadata_rows_matched": report["source_manifest_metadata_rows_matched"],
        "source_manifest_metadata_rows_missing": report["source_manifest_metadata_rows_missing"],
        "official_metric": False,
        "official_metric_input_rows": 0,
        "v4_7_official_metric_gate_opened": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "live_db_index_cache_readiness": False,
        "source_report_run_id": V4_7_SOURCE_RUN_ID,
        "actual_llm_response_example_source_run_id": V3_22_RUN_ID,
    }
    rows = [
        row
        for row in read_jsonl(STATUS_JSONL)
        if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)
    ]
    rows.append(event)
    write_jsonl(STATUS_JSONL, rows)


def _root_readme_snapshot(report: Mapping[str, Any]) -> str:
    snap = report["diagnostic_snapshot"]
    v3 = snap["v3_22"]
    v41 = snap["v4_1"]
    v42 = snap["v4_2"]
    v43 = snap["v4_3"]
    reg = report["v4_7_registration_snapshot"]
    query_counts = reg["real_query_fidelity_included_counts"]
    source_manifest_matched = report["source_manifest_metadata_rows_matched"]
    source_manifest_missing = report["source_manifest_metadata_rows_missing"]
    return f"""## Current RAG Diagnostic Status

- Current RAG status: `{STATUS}`.
- Phase: Phase 1 closed after v3_22 as a diagnostic source-first RAG contract closure. v4 is source-grounded runtime, locator, external holdout, and fine-tuning-readiness work; v4_7 is open only as pre-official external holdout candidate registration, and v4_7_1 only prepares the Korean human review packet plus README snapshot.
- v4_7 pre-official candidate registration: 204 rows total, PDF 100 rows from 20 source documents, XLSX 104 rows from 8 workbooks, TEXT 0 rows. Accepted PDF 20/20 source documents, accepted XLSX 8/8 workbooks, rejected 0, prior identity collisions 0, query fidelity PDF {query_counts.get("PDF", 0)}/100 and XLSX {query_counts.get("XLSX", 0)}/100. v4_7_1 source manifest metadata is matched for {source_manifest_matched}/204 packet rows with {source_manifest_missing} missing rows. External manifest SHA-256: `{EXPECTED_V4_7_MANIFEST_SHA256}`.
- v3_22 diagnostic answer/rendering snapshot: {v3["report_row_count"]} rows, {v3["xlsx_answer_allowed_count"]} answer-allowed, {v3["llm_invoked_count"]} LLM invoked, display-value used {v3["display_value_used_count"]}, raw-value fallback {v3["raw_value_fallback_count"]}, runtime contract violations {v3["runtime_contract_violation_count"]}, vector-payload evidence-truth violations {v3["vector_payload_evidence_truth_violation_count"]}, `official_metric_input_rows=0`.
- v4 reference-only diagnostics: v4_1 persisted XLSX display metadata has {v41["persisted_xlsx_sourceatom_display_metadata_rows"]} rows, {v41["persisted_display_value_available_count"]} persisted display values, {v41["persisted_raw_value_fallback_count"]} raw-value fallback, and zero runtime/vector evidence-truth violations. v4_2 carries {v42["seen_reference_rows"]} XLSX locator seen-reference rows, and v4_3 carries {v43["pdf_file_identity_rows"]} PDF file-identity seen-reference rows; these are not official/product/promotion metrics.
- Hard boundary: not production routing, not product-success evidence, not promotion evidence, not official metric lift, not live DB/index/cache readiness, not FT-A execution, not fine-tuning, and no headline product score. Locked flags remain `production_routing=false`, `official_metric=false`, `official_metric_input_rows=0`, `official_metric_lift=false`, `product_success_evidence_allowed=false`, `promotion_evidence=false`, `fine_tuning_readiness_only=true`, `fine_tuning_started=false`, `fine_tuning_executed=false`, and `live_db_index_cache_readiness=false`. Review packet decisions remain pending user adjudication; official metric remains closed pending user-owned gold/qrels, expected evidence, denominator, and promotion decisions.
"""


def update_root_readme(report: Mapping[str, Any]) -> None:
    text = README.read_text(encoding="utf-8")
    snapshot = _root_readme_snapshot(report)
    if "## Current RAG Diagnostic Status" in text:
        text = re.sub(
            r"## Current RAG Diagnostic Status\n.*?(?=\n## (?:Recent Focus:|전체 구조|구성 요소|폴더 구조))",
            snapshot.rstrip() + "\n",
            text,
            count=1,
            flags=re.S,
        )
    elif "## Recent Focus:" in text:
        text = re.sub(
            r"\nCurrent RAG status: `[^`]+`\..*?(?=\n\n## Recent Focus:)",
            "\n\n" + snapshot.rstrip(),
            text,
            count=1,
            flags=re.S,
        )
    elif "\n## 전체 구조" in text:
        text = text.replace("\n## 전체 구조", "\n" + snapshot.rstrip() + "\n\n## 전체 구조", 1)
    else:
        text = text.rstrip() + "\n\n" + snapshot.rstrip() + "\n"

    if "## How To Verify Locally" in text and "## Repo Map" in text:
        verify_start = text.index("## How To Verify Locally")
        verify_end = text.index("## Repo Map")
        verify_section = text[verify_start:verify_end]
        compile_cmd = (
            "python -X utf8 -m py_compile "
            "ai\\scripts\\rag_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod.py"
        )
        check_cmd = (
            "python -X utf8 ai\\scripts\\rag_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod.py --check"
        )
        if compile_cmd not in verify_section:
            verify_section = verify_section.replace(
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod.py\n",
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod.py\n"
                f"{compile_cmd}\n",
                1,
            )
        if check_cmd not in verify_section:
            verify_section = verify_section.replace(
                "python -X utf8 ai\\scripts\\rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod.py --check\n",
                "python -X utf8 ai\\scripts\\rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod.py --check\n"
                f"{check_cmd}\n",
                1,
            )
        text = text[:verify_start] + verify_section + text[verify_end:]
    elif "## 로컬 실행 메모" in text and "## 라이선스와 외부 데이터" in text:
        local_start = text.index("## 로컬 실행 메모")
        local_end = text.index("## 라이선스와 외부 데이터")
        local_section = text[local_start:local_end]
        verify_note = (
            "\n진단 산출물 재검증은 원본 외부 manifest 경로를 README에 노출하지 않고 다음 명령으로 수행합니다.\n\n"
            "```powershell\n"
            "python -X utf8 ai\\scripts\\rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod.py --check --candidate-manifest <external-candidate-manifest-jsonl>\n"
            "python -X utf8 ai\\scripts\\rag_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod.py --check\n"
            "```\n"
        )
        if "rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod.py" not in local_section:
            local_section = local_section.rstrip() + "\n" + verify_note + "\n"
        text = text[:local_start] + local_section + text[local_end:]
    README.write_text(text, encoding="utf-8")


def _markdown_table(rows: Sequence[Mapping[str, str]]) -> str:
    columns = [
        "Source run",
        "Source family",
        "Query ID",
        "Actual user query",
        "Response policy bucket",
        "Evidence truth source",
        "Parsed final answer or sanitized LLM response excerpt",
        "Raw response hash",
        "Prompt hash",
        "Diagnostic boundary",
    ]
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        values = [
            row["source_run"],
            row["source_family"],
            row["query_id"],
            row["actual_user_query"],
            row["response_policy_bucket"],
            row["evidence_truth_source"],
            row["parsed_final_answer_or_sanitized_excerpt"],
            row["raw_response_hash"],
            row["prompt_hash"],
            row["diagnostic_boundary"],
        ]
        safe = [value.replace("|", "\\|") for value in values]
        lines.append("| " + " | ".join(safe) + " |")
    return "\n".join(lines)


def update_eval_readme(report: Mapping[str, Any]) -> None:
    text = EVAL_README.read_text(encoding="utf-8")
    text = re.sub(r"- Current RAG status: `[^`]+`", f"- Current RAG status: `{STATUS}`", text, count=1)
    packet_section = f"""## Korean human review packet

The v4_7_1 Korean human review packet is generated under `reports/rag_eval/rag-ingestion/quality/{RUN_ID}/` with `report.json`, `review_packet_ko.xlsx`, `review_packet_ko.csv`, `review_packet_ko.jsonl`, `actual_query_llm_response_examples_ko.csv`, `review_guidelines_ko.md`, and `review_summary_ko.json`.

The user decision columns are Korean and all start as `미검수`, `보류`, or blank. Codex did not fill gold/qrels, expected answers, supporting evidence, relevance labels, answerability labels, official denominator inclusion, or promotion policy. The completed packet should be returned as a user-owned review artifact; the next gate is user-owned adjudication of query/evidence text, gold/qrels, expected evidence, denominator policy, and promotion policy. v4_7 registration did not execute an LLM and did not provide actual query/answer artifacts, so the review packet keeps `질의문`, `기대답변_한국어`, and `근거판단_한국어` blank rather than inventing text. The `source_manifest_*` columns and redacted preview/locator columns are filled from SHA-256 matches against the `source_collection` manifest. Actual artifact-backed query/answer examples are exported separately in `actual_query_llm_response_examples_ko.csv`.

## Actual query and LLM response examples

This table is artifact-backed diagnostic evidence from v3_22 answer-allowed XLSX rows. It is not v4_7 output; v4_7 registration did not invoke an LLM. Full raw prompts and full raw LLM responses are intentionally not embedded here.

{_markdown_table(report["actual_llm_response_examples"])}
"""
    if "## Korean human review packet" in text:
        text = re.sub(
            r"## Korean human review packet\n.*?(?=\n## (?:Evaluation Boundary|평가 경계))",
            packet_section.rstrip() + "\n",
            text,
            count=1,
            flags=re.S,
        )
    elif "\n## 평가 경계" in text:
        text = text.replace("\n## 평가 경계", "\n" + packet_section.rstrip() + "\n\n## 평가 경계", 1)
    else:
        text = text.replace("\n## Evaluation Boundary", "\n" + packet_section.rstrip() + "\n\n## Evaluation Boundary", 1)
    EVAL_README.write_text(text, encoding="utf-8")


def update_scripts_readme() -> None:
    text = SCRIPTS_README.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod.py` | "
        "Creates the human-review-only Korean review packet for the registered v4_7 pre-official PDF/XLSX candidates, "
        "updates README/status snapshot surfaces, and keeps official metrics, FT-A execution, fine-tuning, promotion, "
        "product-success evidence, and live readiness closed. |"
    )
    pattern = r"\n?\| `rag_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod\.py` \| .*?\|"
    text = re.sub(pattern, "", text)
    text = text.replace(
        "\n\nv4 scripts remain diagnostic/non-production",
        f"\n{row}\n\nv4 scripts remain diagnostic/non-production",
        1,
    )
    SCRIPTS_README.write_text(text, encoding="utf-8")


def update_progress_doc(report: Mapping[str, Any]) -> None:
    entry = (
        f"- v4_7_1 Korean human review packet and README diagnostic snapshot (`{RUN_ID}`) is {STATUS}. "
        "It creates human-review-only Korean packet artifacts for the accepted v4_7 pre-official PDF/XLSX candidates "
        "and updates README/status surfaces with artifact-backed diagnostic snapshots. The packet starts all user "
        "decision columns as `미검수`, `보류`, or blank; source manifest metadata is filled from SHA-256 matches, "
        "while actual query/answer text was not supplied by the v4_7 registration artifacts and is not invented. "
        "It keeps `official_metric=false`, `official_metric_input_rows=0`, "
        "`promotion_evidence=false`, `product_success_evidence_allowed=false`, `ft_a_execution=false`, "
        "`fine_tuning=false`, and `live_db_index_cache_readiness=false`."
    )
    v47.v4610.v469.v467.replace_marked_entry(PROGRESS_DOC, RUN_ID, entry)
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    text = re.sub(r"Overall status: `[^`]+`;", f"Overall status: `{STATUS}`;", text, count=1)
    text = text.replace(
        "v4_7 remains closed because candidate_manifest_present=false, real_holdout_sufficient=false, "
        "accepted_pdf_holdout_candidates=0/20, accepted_xlsx_holdout_candidates=0/8, "
        "real_query_fidelity_included_rows_per_family=0/100 PDF and 0/100 XLSX,",
        "At v4_6 closeout time, before the v4_7 pre-official registration run, the registration lane was still closed because candidate_manifest_present=false, real_holdout_sufficient=false, accepted_pdf_holdout_candidates=0/20, accepted_xlsx_holdout_candidates=0/8, real_query_fidelity_included_rows_per_family=0/100 PDF and 0/100 XLSX,",
    )
    PROGRESS_DOC.write_text(text, encoding="utf-8")


def update_measurements_doc(report: Mapping[str, Any]) -> None:
    entry = f"""### v4_7_1 Korean Review Packet And README Diagnostic Snapshot

- Run: `{RUN_ID}`
- Primary artifacts: `report.json`, `review_packet_ko.xlsx`, `review_packet_ko.csv`, `review_packet_ko.jsonl`, `actual_query_llm_response_examples_ko.csv`, `review_guidelines_ko.md`, `review_summary_ko.json` under `{repo_relative(OUTPUT_DIR)}`.
- Source evidence: v4_7 pre-official registration report plus external manifest SHA-256 `{EXPECTED_V4_7_MANIFEST_SHA256}`; source metadata fields are filled from SHA-256 matches against the `source_collection` manifest; actual LLM response examples are from v3_22 answer-allowed rows only.
- Interpretation: Korean packet artifacts are user-owned review surfaces. They are not gold/qrels, expected answer, supporting evidence, official metric input, training data, FT-A execution, promotion evidence, product-success evidence, or live readiness evidence.

| Counter | Value |
|---|---:|
| human_review_only | true |
| review_packet_row_count | {report["review_packet_row_count"]} |
| review_packet_pdf_rows | {report["review_packet_counts_by_family"]["PDF"]} |
| review_packet_xlsx_rows | {report["review_packet_counts_by_family"]["XLSX"]} |
| review_packet_text_rows | {report["review_packet_counts_by_family"]["TEXT"]} |
| review_packet_source_rows_have_actual_query_text | false |
| review_packet_source_rows_have_evidence_context | false |
| review_packet_source_rows_have_source_manifest_metadata | {str(report["review_packet_source_rows_have_source_manifest_metadata"]).lower()} |
| source_manifest_metadata_rows_matched | {report["source_manifest_metadata_rows_matched"]} |
| source_manifest_metadata_rows_missing | {report["source_manifest_metadata_rows_missing"]} |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| ft_a_execution | false |
| fine_tuning | false |
| live_db_index_cache_readiness | false |

`preofficial_candidate_thresholds_met=true` in v4_7 means intake thresholds only; `real_holdout_sufficient=false` remains because official denominator, gold/qrels, expected evidence, and promotion gates are still closed and user-owned.
"""
    v47.v4610.v469.v467.replace_marked_entry(MEASUREMENTS_DOC, RUN_ID, entry)


def update_triage_doc(report: Mapping[str, Any]) -> None:
    entry = f"""### v4_7_1 Korean Review Packet And README Diagnostic Snapshot Triage

- Run: `{RUN_ID}`
- The packet covers PDF {report["review_packet_counts_by_family"]["PDF"]} rows and XLSX {report["review_packet_counts_by_family"]["XLSX"]} rows from the accepted v4_7 pre-official candidate manifest registration.
- It is human-review-only. Codex did not fill expected answers, supporting evidence, relevance labels, answerability labels, denominator inclusion, qrels, gold, or promotion decisions.
- The `source_manifest_*` columns and redacted preview/locator columns are filled from SHA-256 matches against the `source_collection` manifest.
- The v4_7 registration artifacts did not contain actual query/answer text, so `질의문`, `기대답변_한국어`, and `근거판단_한국어` remain blank.
- Actual artifact-backed query/answer examples are exported separately in `actual_query_llm_response_examples_ko.csv` from v3_22 answer-allowed LLM rows, not from v4_7.
- It is not official metric, not product-success evidence, not promotion evidence, not FT-A execution, not fine-tuning, and not live DB/index/cache readiness.
- Remaining user-owned actions: provide or adjudicate actual query/evidence context, then decide gold/qrels, expected evidence, relevance, answerability, official denominator inclusion, and promotion policy.
"""
    v47.v4610.v469.v467.replace_marked_entry(TRIAGE_DOC, RUN_ID, entry)
    text = TRIAGE_DOC.read_text(encoding="utf-8")
    text = text.replace(
        "- v4_7 remains closed because candidate_manifest_present=false, real_holdout_sufficient=false, accepted PDF holdout candidates are 0/20, accepted XLSX holdout candidates are 0/8, real query-fidelity included rows are 0/100 for PDF and 0/100 for XLSX, v4_5 readiness gate=false, v4_5_1 intake gate=false, v4_5_2 source identity audit gate=false, user-owned gold/qrels policy gate=false, official denominator gate=false, and promotion policy gate=false.",
        "- At v4_6 closeout time, before v4_7 pre-official registration, the registration lane was closed because candidate_manifest_present=false, real_holdout_sufficient=false, accepted PDF holdout candidates were 0/20, accepted XLSX holdout candidates were 0/8, and real query-fidelity included rows were 0/100 for PDF and 0/100 for XLSX. Current v4_7 registration resolves only the candidate-manifest/source-disjointness blocker; user-owned gold/qrels, expected evidence, official denominator, and promotion policy gates remain closed.",
    )
    text = text.replace(
        "- Do not open v4_7; do not create candidate manifests, validation sidecars, dry-run input manifests, prompt payloads, datasets, jobs, checkpoints, official metric rows, product-success evidence, promotion evidence, or live readiness claims.",
        "- Do not open v4_7 official metric, FT-A, promotion, product-success, or live-readiness gates from this marker; do not create official metric rows, training datasets, jobs, checkpoints, promotion evidence, or live readiness claims.",
    )
    TRIAGE_DOC.write_text(text, encoding="utf-8")


def update_human_docs(report: Mapping[str, Any]) -> None:
    update_root_readme(report)
    update_eval_readme(report)
    update_scripts_readme()
    update_progress_doc(report)
    update_measurements_doc(report)
    update_triage_doc(report)


def run_write(
    *,
    candidate_manifest_path: Path,
    output_dir: Path = OUTPUT_DIR,
    update_docs: bool = True,
    source_collection_manifest_path: Path | None = SOURCE_COLLECTION_MANIFEST_CSV,
) -> dict[str, Any]:
    artifacts = build_artifacts(
        candidate_manifest_path=candidate_manifest_path,
        output_dir=output_dir,
        source_collection_manifest_path=source_collection_manifest_path,
    )
    check_report(artifacts["report"])
    report = write_artifacts(artifacts, output_dir=output_dir)
    check_written_artifacts(output_dir)
    if update_docs and output_dir == OUTPUT_DIR:
        update_status(report)
        update_human_docs(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--candidate-manifest", type=Path, default=None)
    parser.add_argument("--source-collection-manifest", type=Path, default=SOURCE_COLLECTION_MANIFEST_CSV)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    output_dir = args.output_dir
    if args.check:
        if args.candidate_manifest is not None:
            artifacts = build_artifacts(
                candidate_manifest_path=args.candidate_manifest,
                output_dir=output_dir,
                source_collection_manifest_path=args.source_collection_manifest,
            )
            check_report(artifacts["report"])
            report = artifacts["report"]
        else:
            check_written_artifacts(output_dir)
            report = read_json(output_dir / "report.json")
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": report["status"],
                    "human_review_only": True,
                    "review_packet_row_count": report["review_packet_row_count"],
                    "review_packet_counts_by_family": report["review_packet_counts_by_family"],
                    "source_manifest_metadata_rows_matched": report.get("source_manifest_metadata_rows_matched", 0),
                    "source_manifest_metadata_rows_missing": report.get("source_manifest_metadata_rows_missing", 0),
                    "official_metric_input_rows": 0,
                    "promotion_evidence": False,
                    "ft_a_execution": False,
                    "fine_tuning": False,
                    "live_db_index_cache_readiness": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if args.candidate_manifest is None:
        raise SystemExit("--candidate-manifest is required when writing the Korean review packet")
    report = run_write(
        candidate_manifest_path=args.candidate_manifest,
        output_dir=output_dir,
        update_docs=True,
        source_collection_manifest_path=args.source_collection_manifest,
    )
    print(json.dumps({"run_id": RUN_ID, "status": report["status"], "report": report["artifact_paths"]["report_json"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
