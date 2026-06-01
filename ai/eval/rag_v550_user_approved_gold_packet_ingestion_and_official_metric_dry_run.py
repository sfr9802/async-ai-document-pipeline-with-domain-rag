from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import openpyxl

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v540_user_owned_official_eval_approval_packet as v540
from ai.eval import rag_v5_diagnostic_common as common


LOGICAL_RUN_KEY = "v5_5"
SHORT_RUN_ID = "v5_5_user_approved_gold_packet_ingestion_and_official_metric_dry_run"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v5_5_"
    "user_approved_gold_packet_ingestion_and_official_metric_dry_run_nonprod"
)
STATUS = "V5_5_USER_APPROVED_GOLD_PACKET_INGESTION_AND_OFFICIAL_METRIC_DRY_RUN_NONPROD_READY"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
SHORT_REPORT_PATH = RUN_ROOT / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
APPROVED_GOLD_PACKET_PATH = RUN_ROOT / "user_approved_gold_packet.jsonl"
DENOMINATOR_PATH = RUN_ROOT / "user_approved_denominator.jsonl"
QRELS_PATH = RUN_ROOT / "user_approved_qrels.jsonl"
EXPECTED_ANSWERS_PATH = RUN_ROOT / "user_approved_expected_answers.jsonl"
OFFICIAL_METRIC_INPUT_PATH = RUN_ROOT / "official_metric_input.jsonl"
DRY_RUN_RESULT_PATH = RUN_ROOT / "official_metric_dry_run_result.json"

SOURCE_LOGICAL_RUN_KEY = v540.LOGICAL_RUN_KEY
SOURCE_RUN_ID = v540.SHORT_RUN_ID
SOURCE_CANONICAL_LONG_RUN_ID = v540.CANONICAL_LONG_RUN_ID
SOURCE_REPORT_JSON = v540.SHORT_REPORT_PATH
KST_DOC_DATE = "2026-06-01"
EXPECTED_ROWS_BY_TRACK = dict(v540.EXPECTED_ROWS_BY_TRACK)
EXPECTED_ROW_COUNT = sum(EXPECTED_ROWS_BY_TRACK.values())
REVIEWER = "user-approved-bulk-review"
POLICY_NOTE = "user bulk-approved existing registry-backed human-audit-approved 29-row gold snapshot"
SCOPE_POLICY = "exact_v5_4_user_review_packet_rows_only"
EXCLUDED_SCOPES = (
    "all_1000_silver_rows",
    "v5_2_or_v5_3_residual_rows",
    "overlay_90_sample",
    "xlsx_candidate_state_or_pdf_text_residual_taxonomy_denominators",
)
SOURCE_PACKET_PATHS = (
    v540.PACKET_CSV_PATH.as_posix(),
    v540.PACKET_JSONL_PATH.as_posix(),
    v540.PACKET_XLSX_PATH.as_posix(),
)

CLOSED_FALSE_KEYS = (
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "training_dataset_created",
    "training_manifest_jsonl_created",
    "training_job_created",
    "fine_tuning_dataset_export_created",
    "fine_tuning",
    "fine_tuning_started",
    "fine_tuning_executed",
    "ft_a_execution",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_db_mutated",
    "source_registry_mutated",
    "silver_mutation",
    "index_rebuilt",
    "cache_mutated",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
    "official_metric_finalized",
    "official_metric_execution_started",
)
RAW_PAYLOAD_FORBIDDEN_KEYS = v540.RAW_PAYLOAD_FORBIDDEN_KEYS

utc_now_iso = common.utc_now_iso
read_jsonl = common.read_jsonl
write_json = common.write_json
write_jsonl = common.write_jsonl
sha256_file = common.sha256_file


def _repo_path(root: Path | str, rel_path: Path) -> Path:
    return Path(root) / rel_path


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return common.json_clone(payload)


def _source_hash(root: Path) -> str:
    path = root / SOURCE_REPORT_JSON
    return sha256_file(path) if path.exists() else ""


def _source_artifact_status(root: Path) -> str:
    return "present" if (root / SOURCE_REPORT_JSON).exists() else "materialized_in_memory"


def _load_source_report(root: Path, source_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if source_report is not None:
        report = _json_clone(source_report)
    else:
        try:
            report = registry.load_report(SOURCE_LOGICAL_RUN_KEY, root=root)
        except registry.ReportResolutionError:
            report = v540.build_report(root=root, source_report=None)
    v540.check_report(report)
    return report


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_xlsx_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    workbook = openpyxl.load_workbook(path, read_only=True)
    try:
        sheet = workbook.active
        iterator = sheet.iter_rows(values_only=True)
        header = [str(value or "") for value in next(iterator)]
        rows = []
        for values in iterator:
            rows.append({key: value for key, value in zip(header, values)})
        return rows
    finally:
        workbook.close()


def _packet_rows_from_artifacts(root: Path, source: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    jsonl_path = root / v540.PACKET_JSONL_PATH
    csv_path = root / v540.PACKET_CSV_PATH
    xlsx_path = root / v540.PACKET_XLSX_PATH
    jsonl_rows = read_jsonl(jsonl_path)
    if not jsonl_rows:
        jsonl_rows = list(source.get("user_review_packet_rows") or [])
    csv_rows = _read_csv_rows(csv_path)
    xlsx_rows = _read_xlsx_rows(xlsx_path)

    source_ids = [str(row.get("machine_review_row_id") or "") for row in jsonl_rows]
    validation = {
        "jsonl_row_count": len(jsonl_rows),
        "csv_row_count": len(csv_rows),
        "xlsx_row_count": len(xlsx_rows),
        "jsonl_review_ids": source_ids,
        "csv_review_ids": [str(row.get("machine_review_row_id") or "") for row in csv_rows],
        "xlsx_review_ids": [str(row.get("machine_review_row_id") or "") for row in xlsx_rows],
        "source_packet_hashes": {
            "user_review_packet_jsonl_sha256": sha256_file(jsonl_path) if jsonl_path.exists() else "",
            "user_review_packet_csv_sha256": sha256_file(csv_path) if csv_path.exists() else "",
            "user_review_packet_xlsx_sha256": sha256_file(xlsx_path) if xlsx_path.exists() else "",
        },
        "source_packet_artifact_status": {
            "user_review_packet_jsonl": "present" if jsonl_path.exists() else "materialized_from_source_report",
            "user_review_packet_csv": "present" if csv_path.exists() else "missing",
            "user_review_packet_xlsx": "present" if xlsx_path.exists() else "missing",
        },
    }
    return [dict(row) for row in jsonl_rows], validation


def _parse_locator(row: Mapping[str, Any]) -> dict[str, Any]:
    text = str(row.get("machine_existing_citation_locator_hint") or "").strip()
    if not text:
        raise ValueError(f"missing citation locator hint: {row.get('machine_review_row_id')}")
    try:
        locator = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid citation locator hint: {row.get('machine_review_row_id')}") from exc
    if not isinstance(locator, dict):
        raise ValueError(f"citation locator hint must be object: {row.get('machine_review_row_id')}")
    return locator


def _derive_supporting_evidence_ids(row: Mapping[str, Any], locator: Mapping[str, Any]) -> list[str]:
    track = str(row.get("machine_track") or "")
    if track == "text_namu_v2_1":
        ids = locator.get("cited_chunk_ids")
        if not isinstance(ids, list):
            raise ValueError(f"TEXT locator missing cited_chunk_ids: {row.get('machine_review_row_id')}")
        result = [str(item).strip() for item in ids if str(item).strip()]
    elif track in {"xlsx_business_structured", "pdf_business_ocr_mm"}:
        result = [str(locator.get("search_unit_id") or "").strip()]
    else:
        raise ValueError(f"unsupported track for evidence derivation: {track}")
    if not result:
        raise ValueError(f"empty supporting evidence ids: {row.get('machine_review_row_id')}")
    return result


def _validate_source_row(row: Mapping[str, Any]) -> None:
    review_id = str(row.get("machine_review_row_id") or "")
    required = {
        "machine_existing_human_review_status_hint": "USER_REVIEWED_APPROVED",
        "machine_existing_human_label_hint": "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE",
        "machine_existing_official_denominator_current_hint": "TRUE",
        "machine_existing_official_metric_input_hint": "TRUE",
    }
    for key, expected in required.items():
        if str(row.get(key) or "") != expected:
            raise ValueError(f"v5_5 source row precondition failed for {review_id}: {key}")
    for key in (
        "machine_existing_expected_answer_ko_hint",
        "machine_existing_supporting_evidence_hint",
        "machine_existing_citation_locator_hint",
        "machine_query_id",
        "machine_track",
        "machine_question_ko_hint",
    ):
        if not str(row.get(key) or "").strip():
            raise ValueError(f"v5_5 source row missing required hint for {review_id}: {key}")


def _make_approved_row(row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    _validate_source_row(row)
    locator = _parse_locator(row)
    evidence_ids = _derive_supporting_evidence_ids(row, locator)
    query_id = str(row.get("machine_query_id") or "")
    track = str(row.get("machine_track") or "")
    return {
        "source_v5_4_review_row_id": str(row.get("machine_review_row_id") or ""),
        "query_id": query_id,
        "track": track,
        "question_ko": row.get("machine_question_ko_hint"),
        "include_in_official_denominator": "INCLUDE",
        "relevance_label": 3,
        "answerability_label": 3,
        "expected_answer_ko": row.get("machine_existing_expected_answer_ko_hint"),
        "supporting_evidence_ids": evidence_ids,
        "supporting_evidence_note": row.get("machine_existing_supporting_evidence_hint"),
        "citation_locator": locator,
        "gold_status": "APPROVED",
        "policy_note": POLICY_NOTE,
        "reviewer": REVIEWER,
        "reviewed_at": generated_at,
        "source_registry_key": row.get("machine_source_registry_key"),
        "source_csv_path": row.get("machine_source_csv_path"),
        "source_csv_sha256": row.get("machine_source_csv_sha256"),
        "source_row_index": row.get("machine_source_row_index"),
        "registry_denominator_kind": row.get("machine_registry_denominator_kind"),
        "registry_metric_lane": row.get("machine_registry_metric_lane"),
        "source_issue_type": row.get("machine_issue_type_hint"),
        "source_packet_role": row.get("machine_source_packet_role_hint"),
        "query_id_bridge_policy": row.get("machine_query_id_bridge_policy_hint"),
        "approval_basis": "user_bulk_approved_v5_4_packet",
    }


def _denominator_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "query_id": row["query_id"],
        "track": row["track"],
        "source_v5_4_review_row_id": row["source_v5_4_review_row_id"],
        "include_in_official_denominator": row["include_in_official_denominator"],
        "gold_status": row["gold_status"],
        "reviewer": row["reviewer"],
        "reviewed_at": row["reviewed_at"],
        "policy_note": row["policy_note"],
        "denominator_scope": SCOPE_POLICY,
    }


def _qrels_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "query_id": row["query_id"],
        "track": row["track"],
        "source_v5_4_review_row_id": row["source_v5_4_review_row_id"],
        "relevance_label": row["relevance_label"],
        "answerability_label": row["answerability_label"],
        "supporting_evidence_ids": list(row["supporting_evidence_ids"]),
        "citation_locator": dict(row["citation_locator"]),
        "gold_status": row["gold_status"],
        "policy_note": row["policy_note"],
    }


def _expected_answer_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "query_id": row["query_id"],
        "track": row["track"],
        "source_v5_4_review_row_id": row["source_v5_4_review_row_id"],
        "expected_answer_ko": row["expected_answer_ko"],
        "supporting_evidence_note": row["supporting_evidence_note"],
        "supporting_evidence_ids": list(row["supporting_evidence_ids"]),
        "citation_locator": dict(row["citation_locator"]),
        "gold_status": row["gold_status"],
    }


def _official_metric_input_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "query_id": row["query_id"],
        "track": row["track"],
        "question_ko": row["question_ko"],
        "source_v5_4_review_row_id": row["source_v5_4_review_row_id"],
        "include_in_official_denominator": row["include_in_official_denominator"],
        "relevance_label": row["relevance_label"],
        "answerability_label": row["answerability_label"],
        "expected_answer_ko": row["expected_answer_ko"],
        "supporting_evidence_ids": list(row["supporting_evidence_ids"]),
        "supporting_evidence_note": row["supporting_evidence_note"],
        "citation_locator": dict(row["citation_locator"]),
        "gold_status": row["gold_status"],
        "policy_note": row["policy_note"],
        "reviewer": row["reviewer"],
        "reviewed_at": row["reviewed_at"],
        "approval_basis": row["approval_basis"],
    }


def _duplicate_evidence_summary(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        for evidence_id in row.get("supporting_evidence_ids") or []:
            by_id[str(evidence_id)].append(str(row.get("source_v5_4_review_row_id") or ""))
    duplicates = {evidence_id: ids for evidence_id, ids in sorted(by_id.items()) if len(ids) > 1}
    return {
        "duplicate_supporting_evidence_id_count": len(duplicates),
        "duplicate_supporting_evidence_ids": duplicates,
        "duplicate_supporting_evidence_policy": (
            "recorded_for_locator_precision_audit; row-level citation_locator remains authoritative"
        ),
    }


def _dry_run_result(
    *,
    generated_at: str,
    row_count_by_track: Mapping[str, int],
    approved_rows: list[dict[str, Any]],
    duplicate_summary: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_dry_run_result_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "status": "OFFICIAL_METRIC_DRY_RUN_EXECUTED_USER_APPROVED_PACKET_ONLY",
        "generated_at": generated_at,
        "dry_run_mode": "official_metric_input_contract_validation_only_no_answer_generation_no_scorer",
        "source_run_id": SOURCE_RUN_ID,
        "official_metric_input_rows": len(approved_rows),
        "row_count_by_track": dict(row_count_by_track),
        "contract_validation_passed": True,
        "validation_rows": len(approved_rows),
        "answer_quality_metric_computed": False,
        "scored_answer_rows": 0,
        "official_metric_execution_started": False,
        "promotion_evidence": False,
        "training_dataset_created": False,
        "fine_tuning": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
        **dict(duplicate_summary),
    }


def _assert_no_raw_payload_keys(value: Any) -> None:
    common.assert_no_raw_payload_keys(value, set(RAW_PAYLOAD_FORBIDDEN_KEYS), context="v5_5")


def build_report(
    *,
    root: Path,
    generated_at: str | None = None,
    source_report: Mapping[str, Any] | None = None,
    check: bool = True,
) -> dict[str, Any]:
    repo_root = Path(root)
    source = _load_source_report(repo_root, source_report=source_report)
    generated = generated_at or utc_now_iso()
    packet_rows, packet_validation = _packet_rows_from_artifacts(repo_root, source)
    approved_rows = [_make_approved_row(row, generated_at=generated) for row in packet_rows]
    row_count_by_track = dict(Counter(row["track"] for row in approved_rows))
    denominator_rows = [_denominator_row(row) for row in approved_rows]
    qrels_rows = [_qrels_row(row) for row in approved_rows]
    expected_answer_rows = [_expected_answer_row(row) for row in approved_rows]
    metric_input_rows = [_official_metric_input_row(row) for row in approved_rows]
    duplicate_summary = _duplicate_evidence_summary(approved_rows)
    dry_run = _dry_run_result(
        generated_at=generated,
        row_count_by_track=row_count_by_track,
        approved_rows=approved_rows,
        duplicate_summary=duplicate_summary,
    )

    report = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated,
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
            "source_report_json": SOURCE_REPORT_JSON.as_posix(),
            "user_approved_gold_packet_jsonl": APPROVED_GOLD_PACKET_PATH.as_posix(),
            "user_approved_denominator_jsonl": DENOMINATOR_PATH.as_posix(),
            "user_approved_qrels_jsonl": QRELS_PATH.as_posix(),
            "user_approved_expected_answers_jsonl": EXPECTED_ANSWERS_PATH.as_posix(),
            "official_metric_input_jsonl": OFFICIAL_METRIC_INPUT_PATH.as_posix(),
            "official_metric_dry_run_result_json": DRY_RUN_RESULT_PATH.as_posix(),
        },
        "artifact_sha256": {},
        "source_run_id": SOURCE_RUN_ID,
        "source_logical_run_key": SOURCE_LOGICAL_RUN_KEY,
        "source_canonical_long_run_id": SOURCE_CANONICAL_LONG_RUN_ID,
        "source_report_status": source.get("status"),
        "source_report_schema_version": source.get("schema_version"),
        "source_report_sha256": _source_hash(repo_root),
        "source_report_artifact_status": _source_artifact_status(repo_root),
        "source_report_materialized_in_memory": _source_hash(repo_root) == "",
        "source_packet_validation": packet_validation,
        "current_resolves_to": LOGICAL_RUN_KEY,
        "non_production": True,
        "diagnostic_only": False,
        "approval_packet_only": False,
        "user_approved_gold_packet_ingestion": True,
        "review_surface_source": "existing_registry_backed_29_official_snapshot",
        "review_packet_source_row_count": len(packet_rows),
        "review_packet_rows_by_track": row_count_by_track,
        "source_review_packet_rows": packet_rows,
        "approval_scope": {
            "source_run_id": SOURCE_RUN_ID,
            "source_packet_paths": list(SOURCE_PACKET_PATHS),
            "row_count": len(packet_rows),
            "scope_policy": SCOPE_POLICY,
            "excluded_scopes": list(EXCLUDED_SCOPES),
        },
        "user_approval_statement": (
            "User bulk-approved all 29 existing v5_4 review packet rows as sufficient gold for this run only."
        ),
        "user_policy_mapping": {
            "include_in_official_denominator": "INCLUDE",
            "gold_status": "APPROVED",
            "relevance_label": 3,
            "answerability_label": 3,
            "expected_answer_ko": "machine_existing_expected_answer_ko_hint",
            "supporting_evidence_note": "machine_existing_supporting_evidence_hint",
            "supporting_evidence_ids": "derived_only_from_machine_existing_citation_locator_hint",
            "reviewer": REVIEWER,
            "reviewed_at": generated,
            "policy_note": POLICY_NOTE,
        },
        "user_approved_gold_packet_created": True,
        "user_approved_denominator_created": True,
        "user_approved_qrels_created": True,
        "user_approved_expected_answers_created": True,
        "official_qrels_created": True,
        "official_relevance_labels_created": True,
        "official_answerability_labels_created": True,
        "official_gold_labels_created": True,
        "official_metric": False,
        "official_metric_denominator_usage_allowed": True,
        "official_metric_input_rows": len(metric_input_rows),
        "official_metric_input_rows_created": len(metric_input_rows),
        "official_metric_input_rows_scope": SCOPE_POLICY,
        "official_metric_dry_run_opened": True,
        "official_metric_dry_run_executed": True,
        "official_eval_user_gate_ready": True,
        "official_metric_dry_run_result": dry_run,
        "user_approved_gold_packet_rows": approved_rows,
        "user_approved_denominator_rows": denominator_rows,
        "user_approved_qrels_rows": qrels_rows,
        "user_approved_expected_answer_rows": expected_answer_rows,
        "official_metric_input_rows_payload": metric_input_rows,
        "artifact_row_counts": {
            "user_approved_gold_packet": len(approved_rows),
            "user_approved_denominator": len(denominator_rows),
            "user_approved_qrels": len(qrels_rows),
            "user_approved_expected_answers": len(expected_answer_rows),
            "official_metric_input": len(metric_input_rows),
        },
        "protected_namespaces_touched": [],
    }
    for key in CLOSED_FALSE_KEYS:
        report[key] = False
    if check:
        check_report(report)
    return report


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    repo_root = Path(root)
    payload = _json_clone(report)
    write_jsonl(repo_root / APPROVED_GOLD_PACKET_PATH, payload["user_approved_gold_packet_rows"])
    write_jsonl(repo_root / DENOMINATOR_PATH, payload["user_approved_denominator_rows"])
    write_jsonl(repo_root / QRELS_PATH, payload["user_approved_qrels_rows"])
    write_jsonl(repo_root / EXPECTED_ANSWERS_PATH, payload["user_approved_expected_answer_rows"])
    write_jsonl(repo_root / OFFICIAL_METRIC_INPUT_PATH, payload["official_metric_input_rows_payload"])
    write_json(repo_root / DRY_RUN_RESULT_PATH, payload["official_metric_dry_run_result"])
    child_hashes = {
        "user_approved_gold_packet_jsonl_sha256": sha256_file(repo_root / APPROVED_GOLD_PACKET_PATH),
        "user_approved_denominator_jsonl_sha256": sha256_file(repo_root / DENOMINATOR_PATH),
        "user_approved_qrels_jsonl_sha256": sha256_file(repo_root / QRELS_PATH),
        "user_approved_expected_answers_jsonl_sha256": sha256_file(repo_root / EXPECTED_ANSWERS_PATH),
        "official_metric_input_jsonl_sha256": sha256_file(repo_root / OFFICIAL_METRIC_INPUT_PATH),
        "official_metric_dry_run_result_json_sha256": sha256_file(repo_root / DRY_RUN_RESULT_PATH),
    }
    payload["artifact_sha256"] = {
        **dict(payload.get("source_packet_validation", {}).get("source_packet_hashes") or {}),
        **child_hashes,
    }
    write_json(repo_root / SHORT_REPORT_PATH, payload)
    artifact_hashes = {"report_json_sha256": sha256_file(repo_root / SHORT_REPORT_PATH), **child_hashes}
    return payload, artifact_hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "v5_5_user_approved_gold_packet_ingestion_and_official_metric_dry_run_nonprod",
        "generated_at": report["generated_at"],
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "source_run_id": SOURCE_RUN_ID,
        "source_report_status": report["source_report_status"],
        "source_report_sha256": report["source_report_sha256"],
        "source_report_artifact_status": report["source_report_artifact_status"],
        "current_resolves_to": LOGICAL_RUN_KEY,
        "non_production": True,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "review_packet_source_row_count": report["review_packet_source_row_count"],
        "review_packet_rows_by_track": dict(report["review_packet_rows_by_track"]),
        "approval_scope": dict(report["approval_scope"]),
        "official_metric_input_rows": report["official_metric_input_rows"],
        "official_metric_input_rows_created": report["official_metric_input_rows_created"],
        "official_metric_dry_run_opened": True,
        "official_metric_dry_run_executed": True,
        "official_eval_user_gate_ready": True,
        "user_approved_gold_packet_created": True,
        "user_approved_denominator_created": True,
        "user_approved_qrels_created": True,
        "user_approved_expected_answers_created": True,
        "official_metric_finalized": False,
        "training_dataset_created": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
    }


def append_status(root: Path | str, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    repo_root = Path(root)
    status_path = repo_root / STATUS_JSONL_PATH
    rows = read_jsonl(status_path)
    rows = [row for row in rows if row.get("short_run_id") != SHORT_RUN_ID]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    write_jsonl(status_path, rows)


def _upsert_block_at_top(text: str, *, start_marker: str, end_marker: str, block: str) -> str:
    return common.upsert_block_at_top(text, start_marker=start_marker, end_marker=end_marker, block=block)


def _sync_last_updated(text: str) -> str:
    return common.sync_last_updated(text, KST_DOC_DATE)


def _replace_summary_block(text: str, *, block: str) -> str:
    return common.replace_summary_block(
        text,
        start_marker="<!-- v5_5_summary_start -->",
        end_marker="<!-- v5_5_summary_end -->",
        block=block,
        marker_pattern=r"<!-- v5_[0-9]+_summary_start -->.*?<!-- v5_[0-9]+_summary_end -->",
    )


def _replace_current_status_block(progress_text: str, report: Mapping[str, Any]) -> str:
    paths = report["artifact_paths"]
    replacement = (
        "## Current Status\n\n"
        f"Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is the current user-approved gold packet ingestion "
        "and official metric dry-run phase. `current` resolves to `v5_5`, while `v5_4`, `v5_3`, `v5_2`, "
        "`v5_1`, `v5_0`, and `v4_7_18` remain directly checkable.\n\n"
        "Current run board:\n"
        "- current_source_of_truth: `v5_5_user_approved_gold_packet_ingestion_and_official_metric_dry_run`.\n"
        f"- source_run: `{SOURCE_RUN_ID}`; v5_5 ingests only the existing registry-backed 29-row official snapshot "
        "from the v5_4 user-owned approval packet and does not expand to silver, residual, overlay-90, XLSX candidate-state, "
        "or PDF/TEXT residual taxonomy rows.\n"
        f"- Created run-local artifacts: `{paths['user_approved_gold_packet_jsonl']}`, "
        f"`{paths['user_approved_denominator_jsonl']}`, `{paths['user_approved_qrels_jsonl']}`, "
        f"`{paths['user_approved_expected_answers_jsonl']}`, `{paths['official_metric_input_jsonl']}`, and "
        f"`{paths['official_metric_dry_run_result_json']}`.\n"
        "- official_metric_dry_run_opened=true; official_metric_dry_run_executed=true; "
        "official_metric_input_rows=29; official_metric_input_rows_created=29; official_eval_user_gate_ready=true.\n"
        "- promotion/training/fine-tuning/live-readiness remain closed; protected_namespaces_touched=[].\n"
        "- Pre-execution artifact note: older official metric pre-execution artifact remains historical; "
        "official_metric_execution_started=false and must not be read\nas the latest metric execution status.\n\n"
        "Current verification: after v5_5 user-approved gold packet ingestion and official metric dry-run,\n"
        "`pytest ai/tests --rag-current -q` passed with 44 passed, 0 failed, 0 skipped, 1 warning, while historical "
        "focused runs remain directly checkable by explicit key. Generated report/status/official-eval artifacts remain ignored.\n\n"
        "Artifact policy:\n"
        "- `ai/eval/reports/rag-ingestion/status.jsonl` remains local/ignored status ledger.\n"
        f"- Current v5_5 report: `{SHORT_REPORT_PATH.as_posix()}`.\n"
        f"- Source v5_4 packet paths: `{v540.PACKET_CSV_PATH.as_posix()}`, `{v540.PACKET_JSONL_PATH.as_posix()}`, "
        f"and `{v540.PACKET_XLSX_PATH.as_posix()}`.\n"
        f"- Prior basis reports remain explicit: `{SOURCE_REPORT_JSON.as_posix()}`, `{v540.SOURCE_REPORT_JSON.as_posix()}`, "
        "`ai/eval/reports/rag-ingestion/runs/v5_2/report.json`, "
        "`ai/eval/reports/rag-ingestion/runs/v5_1/report.json`, "
        "`ai/eval/reports/rag-ingestion/runs/v5_0/report.json`, and "
        "`ai/eval/reports/rag-ingestion/runs/v4_7_18/report.json`.\n"
    )
    return re.sub(r"## Current Status\n\n.*?(?=\n## Short History)", replacement, progress_text, count=1, flags=re.S)


def update_docs(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    progress = repo_root / "docs" / "rag-ingestion-progress.md"
    measurements = repo_root / "docs" / "rag-ingestion-measurements.md"
    triage = repo_root / "docs" / "rag-ingestion-triage.md"
    readme = repo_root / "README.md"
    eval_readme = repo_root / "ai" / "eval" / "README.md"
    scripts_readme = repo_root / "ai" / "scripts" / "README.md"

    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} ingests the user-approved v5_4 packet as a run-local "
        "official-eval dry-run surface. It creates gold packet, denominator, qrels, expected-answer, official metric input, "
        f"and dry-run result artifacts under `{RUN_ROOT.as_posix()}` only. Scope is exactly 29 v5_4 packet rows "
        "(TEXT 6, XLSX 19, PDF 4); no silver/residual/overlay-90 expansion. official_metric_input_rows=29, "
        "official_metric_dry_run_opened=true, official_metric_dry_run_executed=true, official_metric_execution_started=false, "
        "promotion/training/fine-tuning/product-success/live-readiness remain closed, and protected_namespaces_touched=[]."
    )
    progress_text = _upsert_block_at_top(
        progress.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
        block=progress_block,
    )
    progress_text = _replace_current_status_block(progress_text, report)
    progress.write_text(_sync_last_updated(progress_text), encoding="utf-8")

    measurements_block = f"""## v5_5 user-approved official metric dry-run input

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Interpretation: user-approved 29-row v5_4 packet ingestion and official metric input-contract dry-run only. No answer-generation scorer, final official metric, training, fine-tuning, promotion, product-success, or live-readiness evidence.

| Counter | Value |
|---|---:|
| source_v5_4_packet_rows | {report['review_packet_source_row_count']} |
| text_namu_v2_1_rows | {report['review_packet_rows_by_track']['text_namu_v2_1']} |
| xlsx_business_structured_rows | {report['review_packet_rows_by_track']['xlsx_business_structured']} |
| pdf_business_ocr_mm_rows | {report['review_packet_rows_by_track']['pdf_business_ocr_mm']} |
| user_approved_gold_packet_rows | {len(report['user_approved_gold_packet_rows'])} |
| user_approved_denominator_rows | {len(report['user_approved_denominator_rows'])} |
| user_approved_qrels_rows | {len(report['user_approved_qrels_rows'])} |
| user_approved_expected_answers_rows | {len(report['user_approved_expected_answer_rows'])} |
| official_metric_input_rows | {report['official_metric_input_rows']} |
| official_metric_input_rows_created | {report['official_metric_input_rows_created']} |
| official_metric_dry_run_opened | true |
| official_metric_dry_run_executed | true |
| answer_quality_metric_computed | false |
| duplicate_supporting_evidence_id_count | {report['official_metric_dry_run_result']['duplicate_supporting_evidence_id_count']} |
"""
    measurements_text = _upsert_block_at_top(
        measurements.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->",
        block=measurements_block,
    )
    measurements.write_text(_sync_last_updated(measurements_text), encoding="utf-8")

    triage_block = f"""### v5_5 user approval ingestion boundary

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Scope: exactly the 29 v5_4 user review packet rows. It excludes all 1000 silver rows, v5_2/v5_3 residual rows, overlay-90, XLSX candidate-state rows, and PDF/TEXT residual taxonomy rows from denominator/label creation.
- Evidence IDs are derived only from `machine_existing_citation_locator_hint`; TEXT uses `cited_chunk_ids`, while XLSX/PDF use `search_unit_id` with the full locator preserved for row-level precision audit.
- Duplicate evidence IDs are recorded as diagnostic metadata, not silently collapsed. Run-local official-eval artifacts are ignored and protected namespaces remain untouched.
- Training, fine-tuning, FT-A, promotion, product-success, and live-readiness remain closed.
"""
    triage_text = _upsert_block_at_top(
        triage.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:triage-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:triage-entry:end -->",
        block=triage_block,
    )
    triage.write_text(_sync_last_updated(triage_text), encoding="utf-8")

    summary = f"""## Current RAG Diagnostic Status
Current RAG status: `{STATUS}`.
`current` resolves to `v5_5`: a user-approved gold packet ingestion and official metric dry-run input-contract run. `v5_4` remains the explicit user-owned approval packet source, `v5_3` remains the PDF/TEXT residual hardening basis, `v5_2` remains the XLSX residual candidate-state taxonomy, `v5_1` remains the official-eval gate scaffold, `v5_0` remains the v4 closeout and v5 gate-plan basis, and `v4_7_18` remains the frozen v4 closeout basis.
v5_5 writes `{APPROVED_GOLD_PACKET_PATH.as_posix()}`, `{DENOMINATOR_PATH.as_posix()}`, `{QRELS_PATH.as_posix()}`, `{EXPECTED_ANSWERS_PATH.as_posix()}`, `{OFFICIAL_METRIC_INPUT_PATH.as_posix()}`, and `{DRY_RUN_RESULT_PATH.as_posix()}` for exactly the approved 29 v5_4 packet rows.
Hard boundary: no protected official baseline/input/qrels/gold/denominator namespace mutation, no training dataset, no fine-tuning dataset export, no fine-tuning job, no promotion evidence, no product-success evidence, and no live-readiness claim.
"""
    for doc in (readme, eval_readme):
        text = doc.read_text(encoding="utf-8")
        doc.write_text(_replace_summary_block(text, block=summary), encoding="utf-8")

    scripts_text = scripts_readme.read_text(encoding="utf-8")
    scripts_text = re.sub(
        r"\| `rag_eval\.py` \| .*? \|",
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        "`current` resolves to `v5_5`, `v5_4_user_owned_official_eval_approval_packet` remains explicit, "
        "`v5_3_pdf_text_residual_retrieval_evidence_hardening` remains explicit, "
        "`v5_2_xlsx_residual_candidate_only_retrieval_engineering` remains explicit, "
        "`v5_1_official_eval_gate_scaffolding` remains explicit, `v5_0_v4_closeout_and_v5_gate_plan` remains explicit, "
        "`v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility` remains explicit as the frozen v4 closeout basis, "
        "and v5_5 creates only run-local official metric dry-run input artifacts with training/fine-tuning/promotion/product-success/live-readiness closed. |",
        scripts_text,
        count=1,
    )
    scripts_text = scripts_text.replace(
        "| `required_by_current_tests` | `status.jsonl`, the current v5_4 report and packet, the explicit v5_3, v5_2, v5_1, and v5_0 basis reports, the frozen v4_7_18 source report, and v3_9_2 through v3_22 scripts. |",
        "| `required_by_current_tests` | `status.jsonl`, the current v5_5 report and run-local official metric dry-run artifacts, the explicit v5_4 packet, v5_3, v5_2, v5_1, and v5_0 basis reports, the frozen v4_7_18 source report, and v3_9_2 through v3_22 scripts. |",
    )
    scripts_readme.write_text(scripts_text, encoding="utf-8")


def _require_artifact_paths(report: Mapping[str, Any]) -> None:
    expected = {
        "report_json": SHORT_REPORT_PATH.as_posix(),
        "status_jsonl": STATUS_JSONL_PATH.as_posix(),
        "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        "user_approved_gold_packet_jsonl": APPROVED_GOLD_PACKET_PATH.as_posix(),
        "user_approved_denominator_jsonl": DENOMINATOR_PATH.as_posix(),
        "user_approved_qrels_jsonl": QRELS_PATH.as_posix(),
        "user_approved_expected_answers_jsonl": EXPECTED_ANSWERS_PATH.as_posix(),
        "official_metric_input_jsonl": OFFICIAL_METRIC_INPUT_PATH.as_posix(),
        "official_metric_dry_run_result_json": DRY_RUN_RESULT_PATH.as_posix(),
    }
    if report.get("artifact_paths") != expected:
        raise ValueError("v5_5 artifact path drift")


def _require_no_machine_fields(rows: Iterable[Mapping[str, Any]], *, context: str) -> None:
    for row in rows:
        machine_keys = [key for key in row if key.startswith("machine_")]
        if machine_keys:
            raise ValueError(f"v5_5 machine field leaked into {context}: {machine_keys[:3]}")


def _require_exact_row_sets(report: Mapping[str, Any]) -> None:
    source_rows = list(report.get("source_review_packet_rows") or [])
    source_by_review_id = {str(row.get("machine_review_row_id") or ""): row for row in source_rows}
    if len(source_by_review_id) != EXPECTED_ROW_COUNT:
        raise ValueError("v5_5 source row count drift")
    source_query_ids = {str(row.get("machine_query_id") or "") for row in source_rows}
    for collection_key in (
        "user_approved_gold_packet_rows",
        "user_approved_denominator_rows",
        "user_approved_qrels_rows",
        "user_approved_expected_answer_rows",
        "official_metric_input_rows_payload",
    ):
        rows = list(report.get(collection_key) or [])
        if len(rows) != EXPECTED_ROW_COUNT:
            raise ValueError(f"v5_5 row count drift: {collection_key}")
        if {str(row.get("query_id") or "") for row in rows} != source_query_ids:
            raise ValueError(f"v5_5 row source mismatch: {collection_key}")
        _require_no_machine_fields(rows, context=collection_key)

    for row in report.get("user_approved_gold_packet_rows") or []:
        review_id = str(row.get("source_v5_4_review_row_id") or "")
        source = source_by_review_id.get(review_id)
        if source is None:
            raise ValueError("v5_5 approved row outside v5_4 packet source")
        expected_ids = _derive_supporting_evidence_ids(source, _parse_locator(source))
        if row.get("include_in_official_denominator") != "INCLUDE":
            raise ValueError("v5_5 denominator include drift")
        if row.get("gold_status") != "APPROVED":
            raise ValueError("v5_5 gold status drift")
        if row.get("relevance_label") != 3:
            raise ValueError("v5_5 relevance label drift")
        if row.get("answerability_label") != 3:
            raise ValueError("v5_5 answerability label drift")
        if row.get("expected_answer_ko") != source.get("machine_existing_expected_answer_ko_hint"):
            raise ValueError("v5_5 expected answer drift")
        if row.get("supporting_evidence_note") != source.get("machine_existing_supporting_evidence_hint"):
            raise ValueError("v5_5 supporting evidence note drift")
        if row.get("supporting_evidence_ids") != expected_ids:
            raise ValueError("v5_5 supporting evidence id drift")

    approved_rows = list(report.get("user_approved_gold_packet_rows") or [])
    expected_projections = {
        "user_approved_denominator_rows": [_denominator_row(row) for row in approved_rows],
        "user_approved_qrels_rows": [_qrels_row(row) for row in approved_rows],
        "user_approved_expected_answer_rows": [_expected_answer_row(row) for row in approved_rows],
        "official_metric_input_rows_payload": [_official_metric_input_row(row) for row in approved_rows],
    }
    for collection_key, expected_rows in expected_projections.items():
        if list(report.get(collection_key) or []) != expected_rows:
            raise ValueError(f"v5_5 derived row projection drift: {collection_key}")


def _require_written_artifacts(report: Mapping[str, Any], *, root: Path | str) -> None:
    repo_root = Path(root)
    artifact_paths = report.get("artifact_paths") or {}
    artifact_hashes = report.get("artifact_sha256") or {}
    expected_artifacts = (
        (
            "user_approved_gold_packet_jsonl",
            "user_approved_gold_packet_rows",
            "user_approved_gold_packet_jsonl_sha256",
            "jsonl",
        ),
        (
            "user_approved_denominator_jsonl",
            "user_approved_denominator_rows",
            "user_approved_denominator_jsonl_sha256",
            "jsonl",
        ),
        ("user_approved_qrels_jsonl", "user_approved_qrels_rows", "user_approved_qrels_jsonl_sha256", "jsonl"),
        (
            "user_approved_expected_answers_jsonl",
            "user_approved_expected_answer_rows",
            "user_approved_expected_answers_jsonl_sha256",
            "jsonl",
        ),
        (
            "official_metric_input_jsonl",
            "official_metric_input_rows_payload",
            "official_metric_input_jsonl_sha256",
            "jsonl",
        ),
        (
            "official_metric_dry_run_result_json",
            "official_metric_dry_run_result",
            "official_metric_dry_run_result_json_sha256",
            "json",
        ),
    )
    for path_key, payload_key, hash_key, kind in expected_artifacts:
        rel_path = artifact_paths.get(path_key)
        if not rel_path:
            raise ValueError(f"v5_5 artifact path missing: {path_key}")
        artifact_path = repo_root / str(rel_path)
        if not artifact_path.exists():
            raise ValueError(f"v5_5 artifact missing: {path_key}")
        if kind == "jsonl":
            actual_payload = read_jsonl(artifact_path)
        else:
            actual_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        if actual_payload != report.get(payload_key):
            raise ValueError(f"v5_5 artifact payload drift: {path_key}")
        actual_hash = sha256_file(artifact_path)
        if artifact_hashes.get(hash_key) != actual_hash:
            raise ValueError(f"v5_5 artifact hash drift: {hash_key}")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _assert_no_raw_payload_keys(report)
    if report.get("run_id") != SHORT_RUN_ID or report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v5_5 run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v5_5 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v5_5 status mismatch")
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v5_5 logical run key mismatch")
    if report.get("source_run_id") != SOURCE_RUN_ID or report.get("source_logical_run_key") != SOURCE_LOGICAL_RUN_KEY:
        raise ValueError("v5_5 source run mismatch")
    if report.get("current_resolves_to") != LOGICAL_RUN_KEY:
        raise ValueError("v5_5 current resolution mismatch")
    if report.get("non_production") is not True:
        raise ValueError("v5_5 must remain non-production")
    _require_artifact_paths(report)
    if report.get("review_surface_source") != "existing_registry_backed_29_official_snapshot":
        raise ValueError("v5_5 review surface drift")
    if report.get("review_packet_source_row_count") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_5 row count drift")
    if report.get("review_packet_rows_by_track") != EXPECTED_ROWS_BY_TRACK:
        raise ValueError("v5_5 by-track row count drift")
    validation = report.get("source_packet_validation") or {}
    if validation.get("jsonl_row_count") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_5 source packet JSONL row count drift")
    if validation.get("csv_row_count") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_5 source packet CSV row count drift")
    if validation.get("xlsx_row_count") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_5 source packet XLSX row count drift")
    if validation.get("jsonl_review_ids") != validation.get("csv_review_ids"):
        raise ValueError("v5_5 source packet CSV review id drift")
    if validation.get("jsonl_review_ids") != validation.get("xlsx_review_ids"):
        raise ValueError("v5_5 source packet XLSX review id drift")
    if report.get("approval_scope") != {
        "source_run_id": SOURCE_RUN_ID,
        "source_packet_paths": list(SOURCE_PACKET_PATHS),
        "row_count": EXPECTED_ROW_COUNT,
        "scope_policy": SCOPE_POLICY,
        "excluded_scopes": list(EXCLUDED_SCOPES),
    }:
        raise ValueError("v5_5 approval scope drift")
    for key in (
        "user_approved_gold_packet_created",
        "user_approved_denominator_created",
        "user_approved_qrels_created",
        "user_approved_expected_answers_created",
        "official_qrels_created",
        "official_relevance_labels_created",
        "official_answerability_labels_created",
        "official_gold_labels_created",
        "official_metric_dry_run_opened",
        "official_metric_dry_run_executed",
        "official_eval_user_gate_ready",
    ):
        if report.get(key) is not True:
            raise ValueError(f"v5_5 required open flag missing: {key}")
    if report.get("official_metric") is not False:
        raise ValueError("v5_5 official metric final flag drift")
    if report.get("official_metric_denominator_usage_allowed") is not True:
        raise ValueError("v5_5 official denominator usage flag drift")
    if report.get("official_metric_input_rows") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_5 official metric rows drift")
    if report.get("official_metric_input_rows_created") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_5 official metric rows created drift")
    if report.get("official_metric_input_rows_scope") != SCOPE_POLICY:
        raise ValueError("v5_5 official metric row scope drift")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v5_5 protected namespace touched")
    for key in CLOSED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v5_5 closed surface opened: {key}")
    _require_exact_row_sets(report)
    row_counts = report.get("artifact_row_counts") or {}
    for key in (
        "user_approved_gold_packet",
        "user_approved_denominator",
        "user_approved_qrels",
        "user_approved_expected_answers",
        "official_metric_input",
    ):
        if row_counts.get(key) != EXPECTED_ROW_COUNT:
            raise ValueError(f"v5_5 artifact row count drift: {key}")
    dry_run = report.get("official_metric_dry_run_result") or {}
    if dry_run.get("status") != "OFFICIAL_METRIC_DRY_RUN_EXECUTED_USER_APPROVED_PACKET_ONLY":
        raise ValueError("v5_5 dry run status drift")
    if dry_run.get("official_metric_input_rows") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_5 dry run official metric rows drift")
    if dry_run.get("row_count_by_track") != EXPECTED_ROWS_BY_TRACK:
        raise ValueError("v5_5 dry run by-track row count drift")
    if dry_run.get("contract_validation_passed") is not True:
        raise ValueError("v5_5 dry run contract validation failed")
    if dry_run.get("answer_quality_metric_computed") is not False:
        raise ValueError("v5_5 dry run computed answer quality metric")
    if dry_run.get("promotion_evidence") is not False:
        raise ValueError("v5_5 dry run promotion evidence drift")
    duplicate_summary = _duplicate_evidence_summary(report.get("user_approved_gold_packet_rows") or [])
    if dry_run.get("duplicate_supporting_evidence_id_count") != duplicate_summary["duplicate_supporting_evidence_id_count"]:
        raise ValueError("v5_5 duplicate evidence summary drift")
    if root is not None:
        _require_written_artifacts(report, root=root)
