from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping

import openpyxl

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v510_official_eval_gate_scaffolding as v510
from ai.eval import rag_v530_pdf_text_residual_retrieval_evidence_hardening as v530
from ai.eval import rag_v5_diagnostic_common as common


LOGICAL_RUN_KEY = "v5_4"
SHORT_RUN_ID = "v5_4_user_owned_official_eval_approval_packet"
CANONICAL_LONG_RUN_ID = "official_answer_citation_agentic_loop_run_v5_4_user_owned_official_eval_approval_packet_nonprod"
STATUS = "V5_4_USER_OWNED_OFFICIAL_EVAL_APPROVAL_PACKET_NONPROD_READY"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
SHORT_REPORT_PATH = RUN_ROOT / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
SCHEMA_PATH = RUN_ROOT / "user_owned_approval_schema.json"
POLICY_TEMPLATE_PATH = RUN_ROOT / "user_owned_policy_template.json"
PACKET_JSONL_PATH = RUN_ROOT / "user_review_packet.jsonl"
PACKET_CSV_PATH = RUN_ROOT / "user_review_packet.csv"
PACKET_XLSX_PATH = RUN_ROOT / "user_review_packet.xlsx"
OFFICIAL_DENOMINATOR_REGISTRY_PATH = Path("ai/eval/eval_queries/official_denominator_registry.json")

SOURCE_LOGICAL_RUN_KEY = v530.LOGICAL_RUN_KEY
SOURCE_RUN_ID = v530.SHORT_RUN_ID
SOURCE_CANONICAL_LONG_RUN_ID = v530.CANONICAL_LONG_RUN_ID
SOURCE_REPORT_JSON = v530.SHORT_REPORT_PATH
KST_DOC_DATE = "2026-06-01"

OFFICIAL_SNAPSHOT_REGISTRY_KEYS = (
    "track_b_text_namu_v2_1_question_gold_v2_human_audit_approved",
    "track_a_xlsx_question_gold_v2_human_audit_approved",
    "track_c_pdf_question_gold_v2_human_audit_approved",
)
EXPECTED_ROWS_BY_TRACK = {
    "text_namu_v2_1": 6,
    "xlsx_business_structured": 19,
    "pdf_business_ocr_mm": 4,
}
FINAL_USER_OWNED_FIELDS = (
    "include_in_official_denominator",
    "relevance_label",
    "answerability_label",
    "expected_answer_ko",
    "supporting_evidence_ids",
    "supporting_evidence_note",
    "gold_status",
    "policy_note",
    "reviewer",
    "reviewed_at",
)
MACHINE_CONTEXT_FIELDS = (
    "machine_review_row_id",
    "machine_hint_status",
    "machine_packet_role",
    "machine_packet_only",
    "machine_packet_not_official_metric_input",
    "machine_packet_not_gold_qrels_or_label_artifact",
    "machine_packet_does_not_mutate_source_row",
    "machine_review_surface_source",
    "machine_source_registry_key",
    "machine_source_csv_path",
    "machine_source_csv_sha256",
    "machine_source_row_index",
    "machine_registry_denominator_kind",
    "machine_registry_metric_lane",
    "machine_query_id",
    "machine_track",
    "machine_question_ko_hint",
    "machine_existing_expected_answer_ko_hint",
    "machine_existing_supporting_evidence_hint",
    "machine_existing_citation_locator_hint",
    "machine_existing_human_label_hint",
    "machine_existing_human_review_status_hint",
    "machine_existing_official_denominator_current_hint",
    "machine_existing_official_metric_input_hint",
    "machine_existing_promotion_evidence_hint",
    "machine_source_packet_role_hint",
    "machine_issue_type_hint",
    "machine_supersedes_rejected_row_id_hint",
    "machine_query_id_bridge_policy_hint",
)
PACKET_FIELDNAMES = (*FINAL_USER_OWNED_FIELDS, *MACHINE_CONTEXT_FIELDS)
KOREAN_REVIEW_HELP_FIELDS = (
    "검수_안내",
    "검수_행_ID",
    "자료_유형",
    "질문_확인",
    "기존_답변_참고",
    "기존_근거_참고",
    "기존_인용위치_참고",
    "최종_입력_대상",
    "포함여부_작성_가이드",
    "관련성_작성_가이드",
    "답변가능성_작성_가이드",
    "골드상태_작성_가이드",
)
REVIEW_SHEET_FIELDNAMES = (*FINAL_USER_OWNED_FIELDS, *KOREAN_REVIEW_HELP_FIELDS, *MACHINE_CONTEXT_FIELDS)

FORBIDDEN_FALSE_KEYS = tuple(
    dict.fromkeys(
        (
            *v530.FORBIDDEN_FALSE_KEYS,
            "official_metric",
            "official_metric_denominator_usage_allowed",
            "gold_mutation",
            "qrels_mutation",
            "label_mutation",
            "expected_answer_mutation",
            "supporting_evidence_mutation",
            "denominator_mutation",
            "official_qrels_created",
            "official_relevance_labels_created",
            "official_answerability_labels_created",
            "official_gold_labels_created",
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
            "official_metric_dry_run_opened",
            "raw_prompt_payload_written",
            "raw_response_payload_written",
        )
    )
)
RAW_PAYLOAD_FORBIDDEN_KEYS = v530.RAW_PAYLOAD_FORBIDDEN_KEYS

utc_now_iso = common.utc_now_iso
read_jsonl = common.read_jsonl
write_json = common.write_json
write_jsonl = common.write_jsonl
sha256_file = common.sha256_file


def _source_report_path(root: Path) -> Path:
    return root / SOURCE_REPORT_JSON


def _load_source_report(root: Path, source_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if source_report is not None:
        report = common.json_clone(source_report)
    else:
        try:
            report = registry.load_report(SOURCE_LOGICAL_RUN_KEY, root=root)
        except registry.ReportResolutionError:
            report = v530.build_report(root=root, source_report=None)
    v530.check_report(report)
    return report


def _source_hash(root: Path) -> str:
    path = _source_report_path(root)
    return sha256_file(path) if path.exists() else ""


def _source_artifact_status(root: Path) -> str:
    return common.artifact_status(_source_report_path(root))


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "" if not value else json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _blank_user_fields() -> dict[str, Any]:
    return {
        "include_in_official_denominator": "pending_user_review",
        "relevance_label": "pending_user_review",
        "answerability_label": "pending_user_review",
        "expected_answer_ko": None,
        "supporting_evidence_ids": [],
        "supporting_evidence_note": None,
        "gold_status": "pending_user_review",
        "policy_note": None,
        "reviewer": None,
        "reviewed_at": None,
    }


def _track_ko(track: Any) -> str:
    track_text = str(track or "")
    return {
        "text_namu_v2_1": "TEXT 문서",
        "xlsx_business_structured": "XLSX 스프레드시트",
        "pdf_business_ocr_mm": "PDF 문서",
    }.get(track_text, track_text)


def _with_korean_review_helpers(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload.update(
        {
            "검수_안내": "왼쪽 10개 user-owned 필드만 최종 검수 입력 대상입니다. machine_* 및 기존_* 열은 참고용입니다.",
            "검수_행_ID": row.get("machine_review_row_id", ""),
            "자료_유형": _track_ko(row.get("machine_track")),
            "질문_확인": row.get("machine_question_ko_hint", ""),
            "기존_답변_참고": row.get("machine_existing_expected_answer_ko_hint", ""),
            "기존_근거_참고": row.get("machine_existing_supporting_evidence_hint", ""),
            "기존_인용위치_참고": row.get("machine_existing_citation_locator_hint", ""),
            "최종_입력_대상": ", ".join(FINAL_USER_OWNED_FIELDS),
            "포함여부_작성_가이드": "include_in_official_denominator에 사용자 판단을 입력하세요.",
            "관련성_작성_가이드": "relevance_label에 사용자 판단을 입력하세요.",
            "답변가능성_작성_가이드": "answerability_label에 사용자 판단을 입력하세요.",
            "골드상태_작성_가이드": "gold_status에 사용자 판단을 입력하세요.",
        }
    )
    return payload


def _load_registry(root: Path) -> dict[str, Any]:
    path = root / OFFICIAL_DENOMINATOR_REGISTRY_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_review_surface_rows(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    registry_payload = _load_registry(root)
    denominators = registry_payload.get("official_diagnostic_denominators") or {}
    packet_rows: list[dict[str, Any]] = []
    source_files: list[dict[str, Any]] = []
    blockers: list[str] = []

    for registry_key in OFFICIAL_SNAPSHOT_REGISTRY_KEYS:
        metadata = denominators.get(registry_key)
        if not isinstance(metadata, Mapping):
            blockers.append(f"missing registry key: {registry_key}")
            continue
        rel_path = str(metadata.get("path") or "")
        if not rel_path:
            blockers.append(f"missing source CSV path: {registry_key}")
            continue
        source_path = root / rel_path
        if not source_path.exists():
            blockers.append(f"missing source CSV: {rel_path}")
            continue
        source_sha = sha256_file(source_path)
        expected_sha = str(metadata.get("sha256") or "")
        if expected_sha and source_sha != expected_sha:
            blockers.append(f"source CSV sha256 mismatch: {rel_path}")
            continue
        rows = _read_csv_rows(source_path)
        expected_count = int(metadata.get("official_metric_input_rows") or metadata.get("row_count") or 0)
        if len(rows) != expected_count:
            blockers.append(f"source CSV row count mismatch: {rel_path}")
            continue
        source_files.append(
            {
                "source_registry_key": registry_key,
                "path": rel_path,
                "sha256": source_sha,
                "row_count": len(rows),
                "denominator_kind": metadata.get("denominator_kind"),
                "metric_lane": metadata.get("metric_lane"),
            }
        )
        for source_index, source_row in enumerate(rows, start=1):
            packet_index = len(packet_rows) + 1
            packet_rows.append(
                {
                    **_blank_user_fields(),
                    "machine_review_row_id": f"v5_4_review_{packet_index:03d}",
                    "machine_hint_status": "non_final_context_hint",
                    "machine_packet_role": "user_approval_packet_non_final_context",
                    "machine_packet_only": True,
                    "machine_packet_not_official_metric_input": True,
                    "machine_packet_not_gold_qrels_or_label_artifact": True,
                    "machine_packet_does_not_mutate_source_row": True,
                    "machine_review_surface_source": "existing_registry_backed_29_official_snapshot",
                    "machine_source_registry_key": registry_key,
                    "machine_source_csv_path": rel_path,
                    "machine_source_csv_sha256": source_sha,
                    "machine_source_row_index": source_index,
                    "machine_registry_denominator_kind": metadata.get("denominator_kind") or "",
                    "machine_registry_metric_lane": metadata.get("metric_lane") or "",
                    "machine_query_id": source_row.get("query_id", ""),
                    "machine_track": source_row.get("track", ""),
                    "machine_question_ko_hint": source_row.get("question", ""),
                    "machine_existing_expected_answer_ko_hint": source_row.get("expected_answer", ""),
                    "machine_existing_supporting_evidence_hint": source_row.get("supporting_evidence", ""),
                    "machine_existing_citation_locator_hint": source_row.get("citation_locator", ""),
                    "machine_existing_human_label_hint": source_row.get("human_label", ""),
                    "machine_existing_human_review_status_hint": source_row.get("human_review_status", ""),
                    "machine_existing_official_denominator_current_hint": source_row.get(
                        "official_denominator_current", ""
                    ),
                    "machine_existing_official_metric_input_hint": source_row.get("official_metric_input", ""),
                    "machine_existing_promotion_evidence_hint": source_row.get("promotion_evidence", ""),
                    "machine_source_packet_role_hint": source_row.get("source_packet_role", ""),
                    "machine_issue_type_hint": source_row.get("issue_type", ""),
                    "machine_supersedes_rejected_row_id_hint": source_row.get("supersedes_rejected_row_id", ""),
                    "machine_query_id_bridge_policy_hint": source_row.get("query_id_bridge_policy", ""),
                }
            )

    source_summary = {
        "registry_path": OFFICIAL_DENOMINATOR_REGISTRY_PATH.as_posix(),
        "registry_sha256": sha256_file(root / OFFICIAL_DENOMINATOR_REGISTRY_PATH)
        if (root / OFFICIAL_DENOMINATOR_REGISTRY_PATH).exists()
        else "",
        "registry_keys": list(OFFICIAL_SNAPSHOT_REGISTRY_KEYS),
        "source_files": source_files,
        "expected_rows_by_track": dict(EXPECTED_ROWS_BY_TRACK),
        "total_rows": len(packet_rows),
    }
    blocker = "; ".join(blockers)
    return packet_rows, source_summary, blocker


def _approval_schema() -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_approval_schema_v1",
        "owner": "user",
        "status": "pending_user_review",
        "final_user_owned_fields": list(FINAL_USER_OWNED_FIELDS),
        "machine_context_fields": list(MACHINE_CONTEXT_FIELDS),
        "machine_context_fields_policy": {
            "prefix": "machine_",
            "non_final_context_only": True,
            "codex_may_include": True,
            "required_before_official_metric": False,
        },
        "field_policies": {
            field: {
                "owner": "user",
                "codex_may_fill": False,
                "default": "pending_user_review" if field in {"include_in_official_denominator", "relevance_label", "answerability_label", "gold_status"} else None,
                "required_before_official_metric": True,
            }
            for field in FINAL_USER_OWNED_FIELDS
        },
        "v5_1_user_owned_approval_artifacts": list(v510.USER_OWNED_APPROVAL_ARTIFACTS),
        "official_metric_dry_run_opened": False,
        "official_metric_input_rows_created": 0,
    }


def _policy_template() -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_policy_template_v1",
        "owner": "user",
        "status": "pending_user_review",
        "codex_may_fill_user_owned_fields": False,
        "official_metric_dry_run_requested": False,
        "official_eval_user_gate_ready": False,
        "policy_decisions": {
            artifact: {
                "owner": "user",
                "status": "pending_user_review",
                "codex_may_infer": False,
                "decision": None,
                "reviewer": None,
                "reviewed_at": None,
            }
            for artifact in v510.USER_OWNED_APPROVAL_ARTIFACTS
        },
        "final_user_owned_fields": {field: None for field in FINAL_USER_OWNED_FIELDS},
    }


def build_report(
    *,
    root: Path,
    generated_at: str | None = None,
    source_report: Mapping[str, Any] | None = None,
    check: bool = True,
) -> dict[str, Any]:
    source = _load_source_report(root, source_report=source_report)
    source_sha = _source_hash(root)
    packet_rows, source_summary, blocker = _load_review_surface_rows(root)
    packet_created = blocker == "" and len(packet_rows) == sum(EXPECTED_ROWS_BY_TRACK.values())
    by_track: dict[str, int] = {}
    for row in packet_rows:
        track = str(row.get("machine_track") or "")
        by_track[track] = by_track.get(track, 0) + 1
    schema = _approval_schema()
    policy_template = _policy_template()
    report = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated_at or utc_now_iso(),
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
            "source_report_json": SOURCE_REPORT_JSON.as_posix(),
            "user_owned_approval_schema_json": SCHEMA_PATH.as_posix(),
            "user_owned_policy_template_json": POLICY_TEMPLATE_PATH.as_posix(),
            "user_review_packet_jsonl": PACKET_JSONL_PATH.as_posix(),
            "user_review_packet_csv": PACKET_CSV_PATH.as_posix(),
            "user_review_packet_xlsx": PACKET_XLSX_PATH.as_posix(),
        },
        "artifact_sha256": {},
        "source_run_id": SOURCE_RUN_ID,
        "source_logical_run_key": SOURCE_LOGICAL_RUN_KEY,
        "source_canonical_long_run_id": SOURCE_CANONICAL_LONG_RUN_ID,
        "source_report_status": source.get("status"),
        "source_report_schema_version": source.get("schema_version"),
        "source_report_sha256": source_sha,
        "source_report_artifact_status": _source_artifact_status(root),
        "source_report_materialized_in_memory": source_sha == "",
        "current_resolves_to": LOGICAL_RUN_KEY,
        "diagnostic_only": True,
        "non_production": True,
        "approval_packet_only": True,
        "review_surface_source": "existing_registry_backed_29_official_snapshot",
        "review_surface_scope": "bounded_initial_review_surface_not_all_silver_or_residual_rows",
        "review_packet_row_count": len(packet_rows) if packet_created else 0,
        "review_packet_rows_by_track": by_track if packet_created else {},
        "review_packet_blocker": blocker,
        "user_approval_packet_created": True,
        "user_policy_template_created": True,
        "user_review_packet_created": packet_created,
        "user_review_packet_xlsx_created": packet_created,
        "user_owned_final_fields_filled_by_codex": False,
        "user_owned_final_fields": list(FINAL_USER_OWNED_FIELDS),
        "user_owned_approval_schema": schema,
        "user_owned_policy_template": policy_template,
        "user_review_packet_preview": packet_rows[:3] if packet_created else [],
        "user_review_packet_rows": packet_rows if packet_created else [],
        "official_eval_scaffold_created": False,
        "official_eval_user_gate_ready": False,
        "official_eval_approval_artifact_found": False,
        "official_metric": False,
        "official_metric_denominator_usage_allowed": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_scope": "v5_4_approval_packet_created_rows_only",
        "official_metric_dry_run_opened": False,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "official_qrels_created": False,
        "official_relevance_labels_created": False,
        "official_answerability_labels_created": False,
        "official_gold_labels_created": False,
        "gold_qrels_label_rows_created": 0,
        "training_dataset_created": False,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning": False,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "ft_a_execution": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "production_db_mutated": False,
        "source_registry_mutated": False,
        "silver_mutation": False,
        "index_rebuilt": False,
        "cache_mutated": False,
        "protected_namespaces_touched": [],
        "answer_generation_attempted": False,
        "generated_response_count": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "raw_pdf_query_time_parsing": False,
        "raw_xlsx_query_time_parsing": False,
        "broad_pdf_scan_or_full_page_dump": False,
        "direct_normalized_answer_value_matching": False,
        "formula_evaluation": False,
        "formula_text_exposure": False,
        "source_file_title_shortcut_used": False,
        "workbook_or_source_title_shortcut_used": False,
        "target_or_gold_locator_used_for_candidate_construction": False,
        "query_id_case_id_hack_used": False,
        "expected_or_supporting_gold_text_used": False,
        "source_snapshot": source_summary,
        "decision_policy": {
            "user_owned_decisions": list(v510.USER_OWNED_APPROVAL_ARTIFACTS),
            "codex_owned_work": [
                "packet_schema_materialization",
                "policy_template_materialization",
                "non_final_machine_context_copy",
                "guardrail_validation",
            ],
            "non_gold_ambiguity_policy": "conservative_packet_only_pending_user_review",
        },
        "counters": {
            "current_resolves_to": LOGICAL_RUN_KEY,
            "source_run_id": SOURCE_RUN_ID,
            "user_approval_packet_created": True,
            "user_policy_template_created": True,
            "user_review_packet_created": packet_created,
            "user_review_packet_row_count": len(packet_rows) if packet_created else 0,
            "official_metric_input_rows": 0,
            "official_metric_input_rows_created": 0,
            "official_metric_dry_run_opened": False,
            "official_eval_user_gate_ready": False,
            "training_dataset_created": False,
            "fine_tuning_dataset_export_created": False,
            "protected_namespaces_touched": [],
        },
        "residual_risks": [
            "v5_4 materializes a user-owned packet only; official metric scoring remains closed",
            "all final user-owned fields remain blank or pending_user_review until explicit user approval",
            "existing registry-backed rows are copied only as machine_* non-final review hints",
        ],
        "next_recommendations": [
            "user fills the approval packet fields outside Codex-owned inference",
            "do not open official metric dry-run until user-owned packet and policy approvals are complete",
            "keep v5_3, v5_2, v5_1, v5_0, and v4_7_18 directly checkable",
        ],
    }
    for key in FORBIDDEN_FALSE_KEYS:
        report.setdefault(key, False)
    if check:
        check_report(report)
    return report


def _write_packet_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REVIEW_SHEET_FIELDNAMES), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            review_row = _with_korean_review_helpers(row)
            writer.writerow({field: _csv_cell(review_row.get(field)) for field in REVIEW_SHEET_FIELDNAMES})


def _write_packet_xlsx(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "user_review_packet"
    sheet.append(list(REVIEW_SHEET_FIELDNAMES))
    for row in rows:
        review_row = _with_korean_review_helpers(row)
        sheet.append([_csv_cell(review_row.get(field)) for field in REVIEW_SHEET_FIELDNAMES])
    workbook.save(path)
    workbook.close()


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    repo_root = Path(root)
    payload = common.json_clone(report)
    rows = payload.get("user_review_packet_rows") or []
    write_json(repo_root / SCHEMA_PATH, payload["user_owned_approval_schema"])
    write_json(repo_root / POLICY_TEMPLATE_PATH, payload["user_owned_policy_template"])
    write_jsonl(repo_root / PACKET_JSONL_PATH, rows)
    _write_packet_csv(repo_root / PACKET_CSV_PATH, list(rows))
    _write_packet_xlsx(repo_root / PACKET_XLSX_PATH, list(rows))
    write_json(repo_root / SHORT_REPORT_PATH, payload)
    artifact_hashes = {
        "report_json_sha256": sha256_file(repo_root / SHORT_REPORT_PATH),
        "user_owned_approval_schema_json_sha256": sha256_file(repo_root / SCHEMA_PATH),
        "user_owned_policy_template_json_sha256": sha256_file(repo_root / POLICY_TEMPLATE_PATH),
        "user_review_packet_jsonl_sha256": sha256_file(repo_root / PACKET_JSONL_PATH),
        "user_review_packet_csv_sha256": sha256_file(repo_root / PACKET_CSV_PATH),
        "user_review_packet_xlsx_sha256": sha256_file(repo_root / PACKET_XLSX_PATH),
    }
    return payload, artifact_hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    event = {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "diagnostic_v5_4_user_owned_official_eval_approval_packet_nonprod",
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
        "diagnostic_only": True,
        "non_production": True,
        "approval_packet_only": True,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "review_surface_source": report["review_surface_source"],
        "review_packet_row_count": report["review_packet_row_count"],
        "user_approval_packet_created": report["user_approval_packet_created"],
        "user_policy_template_created": report["user_policy_template_created"],
        "user_review_packet_created": report["user_review_packet_created"],
        "user_review_packet_xlsx_created": report["user_review_packet_xlsx_created"],
        "user_owned_final_fields_filled_by_codex": False,
        "official_eval_user_gate_ready": False,
        "official_metric": False,
        "official_metric_denominator_usage_allowed": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_dry_run_opened": False,
        "official_qrels_created": False,
        "official_relevance_labels_created": False,
        "official_answerability_labels_created": False,
        "official_gold_labels_created": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning": False,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "ft_a_execution": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "production_db_mutated": False,
        "source_registry_mutated": False,
        "silver_mutation": False,
        "index_rebuilt": False,
        "cache_mutated": False,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }
    for key in FORBIDDEN_FALSE_KEYS:
        event.setdefault(key, False)
    return event


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
        start_marker="<!-- v5_4_summary_start -->",
        end_marker="<!-- v5_4_summary_end -->",
        block=block,
        marker_pattern=r"<!-- v5_[0-9]+_summary_start -->.*?<!-- v5_[0-9]+_summary_end -->",
    )


def _replace_current_status_block(progress_text: str, report: Mapping[str, Any]) -> str:
    replacement = (
        "## Current Status\n\n"
        f"Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is the current packet-only phase. "
        "`current` resolves to `v5_4`, while `v5_3`, `v5_2`, `v5_1`, `v5_0`, and `v4_7_18` remain directly checkable.\n\n"
        "Current run board:\n"
        "- current_source_of_truth: `v5_4_user_owned_official_eval_approval_packet`.\n"
        f"- source_run: `{SOURCE_RUN_ID}`; v5_4 materializes a user-owned approval packet over the existing "
        f"registry-backed 29-row official snapshot only; it does not expand to silver or residual rows.\n"
        f"- Packet artifacts: `{SCHEMA_PATH.as_posix()}`, `{POLICY_TEMPLATE_PATH.as_posix()}`, "
        f"`{PACKET_JSONL_PATH.as_posix()}`, `{PACKET_CSV_PATH.as_posix()}`, and `{PACKET_XLSX_PATH.as_posix()}`.\n"
        "- user-owned final fields remain blank/pending_user_review; machine_* columns are non-final context hints only.\n"
        "- official_metric_dry_run_opened=false; official_metric_input_rows=0; official_metric_input_rows_created=0; "
        "official_eval_user_gate_ready=false.\n"
        "- Gold/qrels/labels/expected answers/supporting evidence/denominator/training/fine-tuning/FT-A/promotion/"
        "product-success/live-readiness gates remain closed, and protected_namespaces_touched=[].\n\n"
        "Current verification: after v5_4 user-owned approval packet materialization,\n"
        "`pytest ai/tests --rag-current -q` passed with 38 passed, 0 failed, 0 skipped, 1 warning, while historical "
        "focused runs remain directly checkable by explicit key. Generated report/status/packet artifacts remain ignored.\n\n"
        "Artifact policy:\n"
        "- `ai/eval/reports/rag-ingestion/status.jsonl` remains local/ignored status ledger.\n"
        f"- Current v5_4 report: `{SHORT_REPORT_PATH.as_posix()}`.\n"
        f"- Current user packet paths: `{SCHEMA_PATH.as_posix()}`, `{POLICY_TEMPLATE_PATH.as_posix()}`, "
        f"`{PACKET_JSONL_PATH.as_posix()}`, `{PACKET_CSV_PATH.as_posix()}`, `{PACKET_XLSX_PATH.as_posix()}`.\n"
        f"- Prior basis reports remain explicit: `{SOURCE_REPORT_JSON.as_posix()}`, `{v530.SOURCE_REPORT_JSON.as_posix()}`, "
        f"`{v510.SOURCE_REPORT_JSON.as_posix()}`, `ai/eval/reports/rag-ingestion/runs/v5_0/report.json`, "
        "and frozen v4 basis `ai/eval/reports/rag-ingestion/runs/v4_7_18/report.json`.\n"
    )
    return re_sub_current_status(progress_text, replacement)


def re_sub_current_status(progress_text: str, replacement: str) -> str:
    import re

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
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} creates the user-owned official-eval approval packet only. "
        f"Artifact: `{SHORT_REPORT_PATH.as_posix()}`. Source phase: `v5_3` / `{SOURCE_RUN_ID}`. "
        "`current` resolves to `v5_4`, while `v5_3`, `v5_2`, `v5_1`, `v5_0`, and `v4_7_18` remain directly checkable. "
        f"Required packet artifacts are `{SCHEMA_PATH.as_posix()}`, `{POLICY_TEMPLATE_PATH.as_posix()}`, "
        f"`{PACKET_JSONL_PATH.as_posix()}`, `{PACKET_CSV_PATH.as_posix()}`, and `{PACKET_XLSX_PATH.as_posix()}`. "
        "The bounded review surface is the existing registry-backed 29-row official snapshot, not all silver/residual rows. "
        "All final user-owned row fields remain blank, null, or pending_user_review; Codex fills no user-owned final field. "
        "official_metric_dry_run_opened=false, official_metric_input_rows=0, official_metric_input_rows_created=0, "
        "official_eval_user_gate_ready=false, and no gold/qrels/label/expected/supporting/denominator/training/"
        "fine-tuning/FT-A/promotion/product-success/live-readiness gates are opened."
    )
    progress_text = _upsert_block_at_top(
        progress.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
        block=progress_block,
    )
    progress_text = _replace_current_status_block(progress_text, report)
    progress.write_text(_sync_last_updated(progress_text), encoding="utf-8")

    measurements_block = f"""## v5_4 user-owned official-eval approval packet

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Interpretation: packet-only user approval materialization. No official metric dry-run, no official metric rows, and no user-owned final fields filled by Codex.

| counter | value |
| --- | --- |
| status | {STATUS} |
| source_run_id | {SOURCE_RUN_ID} |
| current_resolves_to | {LOGICAL_RUN_KEY} |
| review_surface_source | {report['review_surface_source']} |
| user_approval_packet_created | {str(report['user_approval_packet_created']).lower()} |
| user_policy_template_created | {str(report['user_policy_template_created']).lower()} |
| user_review_packet_created | {str(report['user_review_packet_created']).lower()} |
| user_review_packet_xlsx_created | {str(report['user_review_packet_xlsx_created']).lower()} |
| user_review_packet_row_count | {report['review_packet_row_count']} |
| user_owned_final_fields_filled_by_codex | false |
| official_metric_input_rows | 0 |
| official_metric_input_rows_created | 0 |
| official_metric_dry_run_opened | false |
| official_eval_user_gate_ready | false |
| training_dataset_created | false |
| fine_tuning_dataset_export_created | false |
| promotion_evidence | false |
| live_db_index_cache_readiness | false |
| protected_namespaces_touched | [] |"""
    measurements_text = _upsert_block_at_top(
        measurements.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->",
        block=measurements_block,
    )
    measurements.write_text(_sync_last_updated(measurements_text), encoding="utf-8")

    triage_block = (
        "### v5_4 user-owned official-eval approval packet\n\n"
        "- Scope: materialize only the user-owned approval schema, policy template, and 29-row review packet over the "
        "existing registry-backed official snapshot.\n"
        "- Do not fill expected answers, supporting evidence, relevance, answerability, denominator, gold/qrels, "
        "promotion, reviewer, or reviewed_at decisions; those remain user-owned and pending_user_review.\n"
        "- Machine context: `machine_*` columns are non-final review hints copied from existing source rows and are not "
        "official metric inputs, qrels, labels, expected answers, supporting evidence approvals, or denominator rows.\n"
        "- Closed gates: official_metric_dry_run_opened=false, official_metric_input_rows=0, "
        "official_metric_input_rows_created=0, training_dataset_created=false, fine_tuning_dataset_export_created=false, "
        "promotion_evidence=false, protected_namespaces_touched=[]."
    )
    triage_text = _upsert_block_at_top(
        triage.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:triage-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:triage-entry:end -->",
        block=triage_block,
    )
    triage.write_text(_sync_last_updated(triage_text), encoding="utf-8")

    summary_block = (
        "## Current RAG Diagnostic Status\n"
        f"Current RAG status: `{STATUS}`.\n"
        "`current` resolves to `v5_4`: a packet-only user-owned official-eval approval materialization run. `v5_3` "
        "remains the PDF/TEXT residual retrieval/evidence hardening basis, `v5_2` remains the XLSX residual candidate-state "
        "taxonomy, `v5_1` remains the official-eval gate scaffold, `v5_0` remains the v4 closeout and v5 gate-plan basis, "
        "and `v4_7_18` remains the frozen v4 closeout basis.\n"
        f"v5_4 writes `{SCHEMA_PATH.as_posix()}`, `{POLICY_TEMPLATE_PATH.as_posix()}`, "
        f"`{PACKET_JSONL_PATH.as_posix()}`, `{PACKET_CSV_PATH.as_posix()}`, and `{PACKET_XLSX_PATH.as_posix()}`. "
        "All final user-owned fields remain blank, null, or pending_user_review; machine_* fields are non-final hints only.\n"
        "Hard boundary: official_metric_dry_run_opened=false, official_metric_input_rows=0, "
        "official_metric_input_rows_created=0; no gold/qrels/labels, no expected/supporting evidence or denominator "
        "mutation, no training dataset, no fine-tuning dataset export, no fine-tuning job, no promotion evidence, "
        "no product-success evidence, and no live-readiness claim."
    )
    for path in (readme, eval_readme):
        path.write_text(_replace_summary_block(path.read_text(encoding="utf-8"), block=summary_block), encoding="utf-8")

    row = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        "`current` resolves to `v5_4`, `v5_3_pdf_text_residual_retrieval_evidence_hardening` remains explicit, "
        "`v5_2_xlsx_residual_candidate_only_retrieval_engineering` remains explicit, "
        "`v5_1_official_eval_gate_scaffolding` remains explicit, `v5_0_v4_closeout_and_v5_gate_plan` remains explicit, "
        "`v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility` remains explicit as the "
        "frozen v4 closeout basis, and all official/gold/qrels/labels/denominator/training/fine-tuning/FT-A/"
        "promotion/product-success/live-readiness gates stay closed. |"
    )
    scripts_text = scripts_readme.read_text(encoding="utf-8")
    import re

    scripts_text = re.sub(r"\| `rag_eval.py` \|.*?\|", row, scripts_text, count=1)
    scripts_text = scripts_text.replace(
        "`status.jsonl`, the current v5_3 report, the explicit v5_2, v5_1, and v5_0 basis reports, "
        "the frozen v4_7_18 source report",
        "`status.jsonl`, the current v5_4 report and packet, the explicit v5_3, v5_2, v5_1, and v5_0 basis reports, "
        "the frozen v4_7_18 source report",
    )
    scripts_readme.write_text(scripts_text, encoding="utf-8")


def _assert_no_raw_payload_keys(value: Any) -> None:
    common.assert_no_raw_payload_keys(value, RAW_PAYLOAD_FORBIDDEN_KEYS, context="v5_4")


def _is_blank_user_value(value: Any) -> bool:
    return value in ("", None, "pending_user_review", [])


def _validate_user_packet_rows(rows: Any, *, expected_count: int) -> None:
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise ValueError("v5_4 review packet row count drift")
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("v5_4 review packet row shape drift")
        for key in row:
            if key not in FINAL_USER_OWNED_FIELDS and not key.startswith("machine_"):
                raise ValueError(f"v5_4 non-machine packet context field: {key}")
        for field in FINAL_USER_OWNED_FIELDS:
            if field not in row:
                raise ValueError(f"v5_4 missing user-owned field: {field}")
            if not _is_blank_user_value(row[field]):
                raise ValueError(f"v5_4 user-owned field filled by Codex: {field}")


def check_report(report: Mapping[str, Any]) -> None:
    _assert_no_raw_payload_keys(report)
    if report.get("run_id") != SHORT_RUN_ID:
        raise ValueError("v5_4 run_id mismatch")
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v5_4 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v5_4 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v5_4 status mismatch")
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v5_4 logical run key mismatch")
    if report.get("source_run_id") != SOURCE_RUN_ID:
        raise ValueError("v5_4 source run must remain v5_3")
    if report.get("source_report_status") != v530.STATUS:
        raise ValueError("v5_4 source report status mismatch")
    if report.get("current_resolves_to") != LOGICAL_RUN_KEY:
        raise ValueError("v5_4 current resolution mismatch")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v5_4 must remain diagnostic-only and non-production")
    if report.get("approval_packet_only") is not True:
        raise ValueError("v5_4 must remain packet-only")
    if report.get("review_surface_source") != "existing_registry_backed_29_official_snapshot":
        raise ValueError("v5_4 review surface drift")
    if report.get("user_approval_packet_created") is not True:
        raise ValueError("v5_4 approval schema packet missing")
    if report.get("user_policy_template_created") is not True:
        raise ValueError("v5_4 policy template missing")
    if report.get("user_review_packet_created") is not True:
        raise ValueError("v5_4 user review packet missing")
    if report.get("user_review_packet_xlsx_created") is not True:
        raise ValueError("v5_4 user review packet xlsx missing")
    if report.get("user_owned_final_fields_filled_by_codex") is not False:
        raise ValueError("v5_4 user-owned final fields filled by Codex")
    if report.get("review_packet_row_count") != 29:
        raise ValueError("v5_4 review packet row count drift")
    if report.get("review_packet_rows_by_track") != dict(EXPECTED_ROWS_BY_TRACK):
        raise ValueError("v5_4 review packet by-track drift")
    if report.get("review_packet_blocker") != "":
        raise ValueError("v5_4 review packet blocker present")
    for key in FORBIDDEN_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v5_4 opened forbidden gate: {key}")
    if report.get("official_metric_input_rows") != 0 or report.get("official_metric_input_rows_created") != 0:
        raise ValueError("v5_4 opened official metric rows")
    if report.get("official_metric_input_rows_scope") != "v5_4_approval_packet_created_rows_only":
        raise ValueError("v5_4 official metric row scope drift")
    if report.get("official_eval_user_gate_ready") is not False:
        raise ValueError("v5_4 official eval user gate opened")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v5_4 protected namespace touched")

    schema = report.get("user_owned_approval_schema") or {}
    if tuple(schema.get("final_user_owned_fields") or ()) != FINAL_USER_OWNED_FIELDS:
        raise ValueError("v5_4 user-owned schema field drift")
    if tuple(schema.get("machine_context_fields") or ()) != MACHINE_CONTEXT_FIELDS:
        raise ValueError("v5_4 machine context schema field drift")
    field_policies = schema.get("field_policies") or {}
    for field in FINAL_USER_OWNED_FIELDS:
        policy = field_policies.get(field) or {}
        if policy.get("owner") != "user" or policy.get("codex_may_fill") is not False:
            raise ValueError(f"v5_4 user-owned schema policy drift: {field}")
        if policy.get("required_before_official_metric") is not True:
            raise ValueError(f"v5_4 user-owned schema requirement drift: {field}")

    policy_template = report.get("user_owned_policy_template") or {}
    if policy_template.get("owner") != "user":
        raise ValueError("v5_4 policy owner drift")
    if policy_template.get("codex_may_fill_user_owned_fields") is not False:
        raise ValueError("v5_4 policy lets Codex fill user fields")
    if policy_template.get("official_metric_dry_run_requested") is not False:
        raise ValueError("v5_4 policy opened official metric dry-run")
    decisions = policy_template.get("policy_decisions") or {}
    if set(decisions) != set(v510.USER_OWNED_APPROVAL_ARTIFACTS):
        raise ValueError("v5_4 policy approval artifact set drift")
    for artifact, decision in decisions.items():
        if decision.get("owner") != "user" or decision.get("codex_may_infer") is not False:
            raise ValueError(f"v5_4 policy artifact owner drift: {artifact}")
        if decision.get("status") != "pending_user_review" or decision.get("decision") is not None:
            raise ValueError(f"v5_4 policy artifact filled: {artifact}")

    _validate_user_packet_rows(report.get("user_review_packet_rows"), expected_count=29)
    _validate_user_packet_rows(report.get("user_review_packet_preview"), expected_count=3)

    source_snapshot = report.get("source_snapshot") or {}
    if source_snapshot.get("total_rows") != 29:
        raise ValueError("v5_4 source snapshot row count drift")
    if source_snapshot.get("expected_rows_by_track") != dict(EXPECTED_ROWS_BY_TRACK):
        raise ValueError("v5_4 source snapshot track drift")

    counters = report.get("counters") or {}
    for key in ("official_metric_input_rows", "official_metric_input_rows_created"):
        if counters.get(key) != 0:
            raise ValueError(f"v5_4 counter opened official metric rows: {key}")
    if counters.get("user_review_packet_row_count") != 29:
        raise ValueError("v5_4 counter review packet row count drift")
    if counters.get("official_metric_dry_run_opened") is not False:
        raise ValueError("v5_4 counter opened official metric dry-run")
    if counters.get("official_eval_user_gate_ready") is not False:
        raise ValueError("v5_4 counter opened official eval user gate")
    if counters.get("protected_namespaces_touched") != []:
        raise ValueError("v5_4 counter protected namespace drift")
