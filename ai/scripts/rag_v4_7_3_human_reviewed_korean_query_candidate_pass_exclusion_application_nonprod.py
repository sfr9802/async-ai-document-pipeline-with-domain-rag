from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

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
RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod"
EVENT_TYPE = "diagnostic_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod"
STATUS = "V4_7_3_HUMAN_REVIEWED_KOREAN_QUERY_CANDIDATE_PASS_EXCLUSION_APPLICATION_NONPROD_READY"
REPORT_SCHEMA_VERSION = "rag_v4_7_3_human_reviewed_korean_query_candidate_decision_report_v1"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"

SOURCE_RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod"
SOURCE_REGISTRATION_RUN_ID = v47.RUN_ID
SOURCE_PACKET_CSV = REPORT_DIR / "quality" / SOURCE_RUN_ID / "review_packet_ko_hydrated.csv"
SOURCE_REPORT_JSON = REPORT_DIR / "quality" / SOURCE_RUN_ID / "report.json"
SOURCE_REGISTRATION_REPORT_JSON = REPORT_DIR / "quality" / SOURCE_REGISTRATION_RUN_ID / "report.json"
DEFAULT_REVIEWED_CSV = Path(r"D:\다운\review_packet_ko_hydrated - review_packet_ko_hydrated.csv.csv")

ALLOWED_ARTIFACT_NAMES = {"report.json"}
IDENTITY_COLUMNS = ("후보ID", "질의ID", "candidate_id_hash", "query_id_hash", "source_family")
REQUIRED_COLUMNS = (
    "검수상태",
    "소스계열",
    "후보ID",
    "질의ID",
    "질의문",
    "관련성라벨",
    "답변가능성라벨",
    "기대답변_한국어",
    "근거판단_한국어",
    "공식분모포함판단",
    "제외사유",
    "source_family",
    "candidate_id_hash",
    "query_id_hash",
)
FORBIDDEN_DECISION_TEXT_PATTERNS = (
    r"\bD:[\\/]",
    r"v4_7_external_pdf_document_sha256_",
    r"v4_7_external_xlsx_workbook_sha256_",
    r"source_identity_key",
    r"target_locator",
    r"gold_locator",
    r"expected_answer_used_as_source",
    r"supporting_evidence_used_as_source",
    r"official_metric_input_rows\.jsonl",
    r"prompt_payload",
    r"raw_llm_response",
    r"checkpoint artifact written",
    r"formula_text",
)

DECISION_POLICY = [
    "user_clarified_migeomsu_means_pass",
    "non_empty_exclusion_reason_means_user_excluded",
    "empty_exclusion_reason_means_user_passed_query_candidate",
    "query_candidate_pass_does_not_open_gold_qrels_labels_expected_evidence_or_official_denominator",
]
RESIDUAL_RISKS = [
    "all passed query candidates are PDF",
    "all XLSX candidates are user-excluded in this review",
    "expected answers/evidence and relevance/answerability labels remain unresolved",
    "official metric and FT-A remain closed",
]


def clean(value: Any) -> str:
    return v47.clean(value)


def utc_now() -> str:
    return v47.utc_now()


def sha256_file(path: Path) -> str:
    return v47.sha256_file(path)


def repo_relative(path: Path) -> str:
    return v47.repo_relative(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v47.write_json(path, payload)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v47.read_jsonl(path)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v47.write_jsonl(path, rows)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise AssertionError(f"CSV has no rows: {path}")
    return rows


def stable_payload_sha256(payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def family_of(row: Mapping[str, str]) -> str:
    return clean(row.get("source_family") or row.get("소스계열")).upper()


def row_key(row: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(clean(row.get(column)) for column in IDENTITY_COLUMNS)


def counts_by_family(rows: Iterable[Mapping[str, str]]) -> dict[str, int]:
    counts = Counter(family_of(row) for row in rows)
    return {family: counts.get(family, 0) for family in ("PDF", "XLSX", "TEXT")}


def contains_forbidden_text(payload: Any) -> bool:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True) if not isinstance(payload, str) else payload
    return any(re.search(pattern, text) for pattern in FORBIDDEN_DECISION_TEXT_PATTERNS)


def validate_input_rows(
    *,
    reviewed_rows: Sequence[Mapping[str, str]],
    source_rows: Sequence[Mapping[str, str]],
) -> None:
    if len(reviewed_rows) != 204:
        raise AssertionError("reviewed CSV row count must be 204")
    if len(source_rows) != 204:
        raise AssertionError("source v4_7_2 packet row count must be 204")
    missing = [column for column in REQUIRED_COLUMNS if column not in reviewed_rows[0]]
    if missing:
        raise AssertionError(f"reviewed CSV missing required columns: {missing}")
    missing_source = [column for column in IDENTITY_COLUMNS if column not in source_rows[0]]
    if missing_source:
        raise AssertionError(f"source v4_7_2 packet missing identity columns: {missing_source}")

    if counts_by_family(reviewed_rows) != {"PDF": 100, "XLSX": 104, "TEXT": 0}:
        raise AssertionError("reviewed CSV family counts drifted")
    if counts_by_family(source_rows) != {"PDF": 100, "XLSX": 104, "TEXT": 0}:
        raise AssertionError("source v4_7_2 packet family counts drifted")

    reviewed_keys = [row_key(row) for row in reviewed_rows]
    source_keys = [row_key(row) for row in source_rows]
    if len(set(reviewed_keys)) != len(reviewed_keys):
        raise AssertionError("reviewed CSV contains duplicate candidate/query identities")
    if reviewed_keys != source_keys:
        raise AssertionError("reviewed CSV identities do not match v4_7_2 source packet order")

    if any(clean(row.get("검수상태")) != "미검수" for row in reviewed_rows):
        raise AssertionError("this v4_7_3 pass applies only the user-clarified 미검수 review status")
    if any(clean(row.get("관련성라벨")) != "보류" for row in reviewed_rows):
        raise AssertionError("relevance labels must remain 보류")
    if any(clean(row.get("답변가능성라벨")) != "보류" for row in reviewed_rows):
        raise AssertionError("answerability labels must remain 보류")
    if any(clean(row.get("공식분모포함판단")) != "보류" for row in reviewed_rows):
        raise AssertionError("official denominator decisions must remain 보류")
    if any(clean(row.get("기대답변_한국어")) for row in reviewed_rows):
        raise AssertionError("expected answers must remain user-owned blank fields")
    if any(clean(row.get("근거판단_한국어")) for row in reviewed_rows):
        raise AssertionError("supporting evidence judgments must remain user-owned blank fields")
    if any(not clean(row.get("질의문")) for row in reviewed_rows):
        raise AssertionError("reviewed CSV must keep concrete Korean query text")

    decision_inputs = [
        {
            "검수상태": clean(row.get("검수상태")),
            "제외사유": clean(row.get("제외사유")),
            "후보ID": clean(row.get("후보ID")),
            "질의ID": clean(row.get("질의ID")),
            "candidate_id_hash": clean(row.get("candidate_id_hash")),
            "query_id_hash": clean(row.get("query_id_hash")),
            "source_family": family_of(row),
        }
        for row in reviewed_rows
    ]
    if contains_forbidden_text(decision_inputs):
        raise AssertionError("decision input columns contain forbidden local/source/oracle text")


def build_decision_ledger(reviewed_rows: Sequence[Mapping[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ledger: list[dict[str, Any]] = []
    passed: list[dict[str, Any]] = []
    for index, row in enumerate(reviewed_rows, start=1):
        exclusion_reason = clean(row.get("제외사유"))
        source_family = family_of(row)
        query_text = clean(row.get("질의문"))
        common = {
            "row_index_1based": index,
            "source_family": source_family,
            "candidate_id": clean(row.get("후보ID")),
            "query_id": clean(row.get("질의ID")),
            "candidate_id_hash": clean(row.get("candidate_id_hash")),
            "query_id_hash": clean(row.get("query_id_hash")),
            "review_status_original": clean(row.get("검수상태")),
            "review_status_interpretation": "user_clarified_migeomsu_means_pass_override",
            "csv_migeomsu_interpreted_as_pass": True,
            "query_text": query_text,
            "query_text_sha256": hash_text(query_text),
            "exclusion_reason_user_text": exclusion_reason,
            "official_denominator_eligible": False,
            "gold_status": "not_gold",
            "qrels_status": "not_qrels",
            "label_status": "not_labeled",
            "expected_answer_status": "unresolved_user_owned_blank",
            "supporting_evidence_status": "unresolved_user_owned_blank",
            "relevance_label_original": clean(row.get("관련성라벨")),
            "answerability_label_original": clean(row.get("답변가능성라벨")),
            "official_denominator_decision_original": clean(row.get("공식분모포함판단")),
            "source_row_identity_verified_against_v4_7_2": True,
        }
        if exclusion_reason:
            decision = {
                **common,
                "decision_status": "user_excluded",
                "query_candidate_passed": False,
                "acceptance_basis": "",
            }
        else:
            decision = {
                **common,
                "decision_status": "user_passed_query_candidate",
                "query_candidate_passed": True,
                "acceptance_basis": "user_clarified_csv_migeomsu_means_pass_and_blank_exclusion_reason",
            }
            passed.append(
                {
                    "source_family": source_family,
                    "candidate_id": common["candidate_id"],
                    "query_id": common["query_id"],
                    "candidate_id_hash": common["candidate_id_hash"],
                    "query_id_hash": common["query_id_hash"],
                    "query_text": query_text,
                    "decision_status": "user_passed_query_candidate",
                    "query_candidate_passed": True,
                    "acceptance_basis": decision["acceptance_basis"],
                    "official_denominator_eligible": False,
                    "gold_status": "not_gold",
                    "qrels_status": "not_qrels",
                    "label_status": "not_labeled",
                }
            )
        ledger.append(decision)
    return ledger, passed


def build_report(
    *,
    reviewed_csv_path: Path = DEFAULT_REVIEWED_CSV,
    source_packet_csv_path: Path = SOURCE_PACKET_CSV,
    generated_at: str | None = None,
) -> dict[str, Any]:
    reviewed_rows = read_csv_rows(reviewed_csv_path)
    source_rows = read_csv_rows(source_packet_csv_path)
    validate_input_rows(reviewed_rows=reviewed_rows, source_rows=source_rows)
    ledger, passed = build_decision_ledger(reviewed_rows)
    excluded = [row for row in ledger if row["decision_status"] == "user_excluded"]
    passed_by_family = counts_by_family(passed)
    excluded_by_family = counts_by_family(excluded)

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "source_run_id": SOURCE_RUN_ID,
        "source_registration_run_id": SOURCE_REGISTRATION_RUN_ID,
        "status": STATUS,
        "generated_at": generated_at or utc_now(),
        "diagnostic_only": True,
        "human_review_applied": True,
        "user_clarification_applied": True,
        "csv_migeomsu_interpreted_as_pass": True,
        "reviewed_csv_path_redacted": True,
        "source_packet_path": repo_relative(source_packet_csv_path),
        "source_report_path": repo_relative(SOURCE_REPORT_JSON),
        "source_registration_report_path": repo_relative(SOURCE_REGISTRATION_REPORT_JSON),
        "reviewed_csv_sha256": sha256_file(reviewed_csv_path),
        "source_packet_csv_sha256": sha256_file(source_packet_csv_path),
        "artifact_paths": {"report_json": repo_relative(REPORT_JSON)},
        "decision_input_columns_used": [
            "후보ID",
            "질의ID",
            "candidate_id_hash",
            "query_id_hash",
            "source_family",
            "소스계열",
            "검수상태",
            "제외사유",
        ],
        "decision_policy": DECISION_POLICY,
        "residual_risks": RESIDUAL_RISKS,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "v4_7_official_metric_gate_opened": False,
        "query_candidate_pass_mutation": True,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "gold_jsonl_created": False,
        "qrels_jsonl_created": False,
        "labels_jsonl_created": False,
        "expected_answer_artifact_created": False,
        "supporting_evidence_artifact_created": False,
        "training_manifest_jsonl_created": False,
        "prompt_manifest_jsonl_created": False,
        "raw_response_payload_jsonl_created": False,
        "checkpoint_artifact_created": False,
        "production_db_index_cache_artifact_created": False,
        "protected_namespaces_touched": [],
        "reviewed_csv_row_count": len(reviewed_rows),
        "reviewed_csv_pdf_rows": counts_by_family(reviewed_rows)["PDF"],
        "reviewed_csv_xlsx_rows": counts_by_family(reviewed_rows)["XLSX"],
        "reviewed_csv_text_rows": counts_by_family(reviewed_rows)["TEXT"],
        "user_passed_query_candidate_row_count": len(passed),
        "user_excluded_row_count": len(excluded),
        "passed_counts_by_family": passed_by_family,
        "excluded_counts_by_family": excluded_by_family,
        "review_status_values": dict(Counter(clean(row.get("검수상태")) for row in reviewed_rows)),
        "review_status_override": {
            "original_value": "미검수",
            "interpreted_as": "user_passed_query_candidate_when_exclusion_reason_blank",
            "basis": "user_clarified_csv_migeomsu_means_pass",
        },
        "unresolved_user_owned_fields": {
            "관련성라벨": "보류",
            "답변가능성라벨": "보류",
            "공식분모포함판단": "보류",
            "기대답변_한국어": "blank",
            "근거판단_한국어": "blank",
        },
        "sidecar_artifacts_created": [],
        "review_decision_ledger": ledger,
        "passed_query_candidates": passed,
        "decision_ledger_sha256": stable_payload_sha256(ledger),
        "passed_query_candidates_sha256": stable_payload_sha256(passed),
    }
    check_report(report)
    return report


def check_report(report: Mapping[str, Any]) -> None:
    expected_false_flags = (
        "official_metric",
        "v4_7_official_metric_gate_opened",
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "denominator_mutation",
        "training_dataset_created",
        "ft_a_execution",
        "fine_tuning",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "live_db_index_cache_readiness",
        "gold_jsonl_created",
        "qrels_jsonl_created",
        "labels_jsonl_created",
        "expected_answer_artifact_created",
        "supporting_evidence_artifact_created",
        "training_manifest_jsonl_created",
        "prompt_manifest_jsonl_created",
        "raw_response_payload_jsonl_created",
        "checkpoint_artifact_created",
        "production_db_index_cache_artifact_created",
    )
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise AssertionError("unexpected v4_7_3 report schema")
    if report.get("run_id") != RUN_ID or report.get("status") != STATUS:
        raise AssertionError("unexpected v4_7_3 report identity/status")
    if report.get("source_run_id") != SOURCE_RUN_ID:
        raise AssertionError("source v4_7_2 run id drifted")
    if report.get("source_registration_run_id") != SOURCE_REGISTRATION_RUN_ID:
        raise AssertionError("source registration run id drifted")
    if report.get("diagnostic_only") is not True:
        raise AssertionError("v4_7_3 must remain diagnostic-only")
    if report.get("human_review_applied") is not True:
        raise AssertionError("human review application flag must be true")
    if report.get("user_clarification_applied") is not True:
        raise AssertionError("user clarification flag must be true")
    if report.get("csv_migeomsu_interpreted_as_pass") is not True:
        raise AssertionError("미검수 must be interpreted as pass for this CSV")
    if report.get("official_metric_input_rows") != 0:
        raise AssertionError("official metric input rows must remain 0")
    for flag in expected_false_flags:
        if report.get(flag) is not False:
            raise AssertionError(f"{flag} must remain false")
    if report.get("query_candidate_pass_mutation") is not True:
        raise AssertionError("query candidate pass mutation flag must be true")
    if report.get("protected_namespaces_touched") != []:
        raise AssertionError("protected namespaces must remain untouched")
    if report.get("decision_policy") != DECISION_POLICY:
        raise AssertionError("decision policy drifted")
    if report.get("residual_risks") != RESIDUAL_RISKS:
        raise AssertionError("residual risks drifted")
    if report.get("reviewed_csv_row_count") != 204:
        raise AssertionError("reviewed CSV row count must be 204")
    if report.get("reviewed_csv_pdf_rows") != 100 or report.get("reviewed_csv_xlsx_rows") != 104:
        raise AssertionError("reviewed CSV family row counts drifted")
    if report.get("user_passed_query_candidate_row_count") != 58:
        raise AssertionError("passed query candidate count must be 58")
    if report.get("user_excluded_row_count") != 146:
        raise AssertionError("user excluded row count must be 146")
    if report.get("passed_counts_by_family") != {"PDF": 58, "XLSX": 0, "TEXT": 0}:
        raise AssertionError("passed family counts drifted")
    if report.get("excluded_counts_by_family") != {"PDF": 42, "XLSX": 104, "TEXT": 0}:
        raise AssertionError("excluded family counts drifted")
    ledger = list(report.get("review_decision_ledger") or [])
    passed = list(report.get("passed_query_candidates") or [])
    if len(ledger) != 204 or len(passed) != 58:
        raise AssertionError("embedded ledger counts drifted")
    if stable_payload_sha256(ledger) != report.get("decision_ledger_sha256"):
        raise AssertionError("decision ledger hash drifted")
    if stable_payload_sha256(passed) != report.get("passed_query_candidates_sha256"):
        raise AssertionError("passed candidate hash drifted")
    if contains_forbidden_text(report):
        raise AssertionError("forbidden local/source/oracle text leaked into v4_7_3 report")


def write_artifacts(report: Mapping[str, Any], *, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    unexpected = {path.name for path in output_dir.iterdir() if path.name not in ALLOWED_ARTIFACT_NAMES}
    if unexpected:
        raise RuntimeError(f"unexpected v4_7_3 artifacts present: {sorted(unexpected)}")
    write_json(output_dir / "report.json", report)
    return dict(report)


def check_written_artifacts(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    files = {path.name for path in output_dir.iterdir()} if output_dir.exists() else set()
    if files != ALLOWED_ARTIFACT_NAMES:
        raise AssertionError(f"unexpected v4_7_3 artifact set: {sorted(files)}")
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    check_report(report)
    return report


def status_event(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": {"report_json_sha256": sha256_file(REPORT_JSON)},
        "diagnostic_only": True,
        "human_review_applied": True,
        "user_clarification_applied": True,
        "csv_migeomsu_interpreted_as_pass": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "v4_7_official_metric_gate_opened": False,
        "query_candidate_pass_mutation": True,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "reviewed_csv_row_count": report["reviewed_csv_row_count"],
        "reviewed_csv_pdf_rows": report["reviewed_csv_pdf_rows"],
        "reviewed_csv_xlsx_rows": report["reviewed_csv_xlsx_rows"],
        "user_passed_query_candidate_row_count": report["user_passed_query_candidate_row_count"],
        "user_excluded_row_count": report["user_excluded_row_count"],
        "passed_counts_by_family": dict(report["passed_counts_by_family"]),
        "excluded_counts_by_family": dict(report["excluded_counts_by_family"]),
        "source_run_id": SOURCE_RUN_ID,
        "source_registration_run_id": SOURCE_REGISTRATION_RUN_ID,
        "decision_ledger_sha256": report["decision_ledger_sha256"],
        "passed_query_candidates_sha256": report["passed_query_candidates_sha256"],
    }


def update_status(report: Mapping[str, Any]) -> None:
    event = status_event(report)
    rows = [
        row
        for row in read_jsonl(STATUS_JSONL)
        if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)
    ]
    rows.append(event)
    write_jsonl(STATUS_JSONL, rows)


def update_root_readme(report: Mapping[str, Any]) -> None:
    text = README.read_text(encoding="utf-8")
    snapshot = f"""## Current RAG Diagnostic Status

- Current RAG status: `{STATUS}`.
- Phase: v4_7 remains pre-official. v4_7_3 applies the user-reviewed Korean query candidate CSV over the v4_7_2 hydrated packet and freezes pass/exclusion decisions only.
- v4_7_2 supersedes the abstract v4_7_1 Korean review packet with source-grounded Korean query candidates; hydrated rows 204, PDF 100, XLSX 104, and non-empty `질의문` 204 before this decision application.
- v4_7_3 counters: reviewed rows {report["reviewed_csv_row_count"]}, PDF {report["reviewed_csv_pdf_rows"]}, XLSX {report["reviewed_csv_xlsx_rows"]}; user-passed query candidates {report["user_passed_query_candidate_row_count"]}; user-excluded rows {report["user_excluded_row_count"]}. `미검수=통과` is applied per user clarification when `제외사유` is blank.
- Rolling evidence docs: `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md` remain the canonical human-readable status ledgers; this packet decision application is not production promotion evidence.
- Hard boundary: not official metric, not gold/qrels, not relevance/answerability labels, not expected answer/evidence approval, not product-success evidence, not promotion evidence, not FT-A execution, not fine-tuning, not training data, and not live DB/index/cache readiness. Locked flags remain `official_metric=false`, `official_metric_input_rows=0`, `v4_7_official_metric_gate_opened=false`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `ft_a_execution=false`, `fine_tuning=false`, `fine_tuning_executed=false`, and `live_db_index_cache_readiness=false`.
"""
    if "## Current RAG Diagnostic Status" in text:
        text = re.sub(
            r"## Current RAG Diagnostic Status\n.*?(?=\n## (?:Recent Focus:|전체 구조|구성 요소|폴더 구조))",
            snapshot.rstrip() + "\n",
            text,
            count=1,
            flags=re.S,
        )
    elif "\n## 전체 구조" in text:
        text = text.replace("\n## 전체 구조", "\n" + snapshot.rstrip() + "\n\n## 전체 구조", 1)
    else:
        text = text.rstrip() + "\n\n" + snapshot.rstrip() + "\n"

    script_name = "rag_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod.py"
    if "## How To Verify Locally" in text and "## Repo Map" in text:
        start = text.index("## How To Verify Locally")
        end = text.index("## Repo Map")
        section = text[start:end]
        compile_cmd = f"python -X utf8 -m py_compile ai\\scripts\\{script_name}"
        check_cmd = f"python -X utf8 ai\\scripts\\{script_name} --check"
        if compile_cmd not in section:
            section = section.rstrip() + f"\n{compile_cmd}\n"
        if check_cmd not in section:
            section = section.rstrip() + f"\n{check_cmd}\n"
        text = text[:start] + section + "\n" + text[end:]
    elif "## 로컬 실행 메모" in text and "## 라이선스와 외부 데이터" in text:
        start = text.index("## 로컬 실행 메모")
        end = text.index("## 라이선스와 외부 데이터")
        section = text[start:end]
        compile_cmd = f"python -X utf8 -m py_compile ai\\scripts\\{script_name}"
        check_cmd = f"python -X utf8 ai\\scripts\\{script_name} --check"
        if compile_cmd not in section:
            section = section.replace(
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod.py\n",
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod.py\n"
                f"{compile_cmd}\n",
                1,
            )
        if check_cmd not in section:
            section = section.replace(
                "python -X utf8 ai\\scripts\\rag_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod.py --check\n",
                "python -X utf8 ai\\scripts\\rag_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod.py --check\n"
                f"{check_cmd}\n",
                1,
            )
        text = text[:start] + section + text[end:]
    README.write_text(text, encoding="utf-8")


def update_eval_readme(report: Mapping[str, Any]) -> None:
    text = EVAL_README.read_text(encoding="utf-8")
    text = re.sub(r"- Current RAG status: `[^`]+`", f"- Current RAG status: `{STATUS}`", text, count=1)
    section = f"""## Korean human review packet

The previous v4_7_1 Korean review packet was abstract because v4_7 registration contained source-disjoint candidate identities but not query text. v4_7_2 superseded it with `ai/eval/reports/rag-ingestion/quality/{SOURCE_RUN_ID}/review_packet_ko_hydrated.xlsx`, plus CSV/JSONL equivalents, containing actual Korean query candidates, bounded evidence previews, and locator previews. User-owned fields remain blank/default for expected answers, evidence judgment, relevance labels, answerability labels, official denominator inclusion, exclusion reasons, policy memo, reviewer, and review timestamp.

v4_7_3 applies the user-reviewed CSV decisions over that hydrated packet. Per user clarification, `검수상태=미검수` means pass for rows with blank `제외사유`; rows with non-empty `제외사유` are user-excluded. The result freezes {report["user_passed_query_candidate_row_count"]} passed query candidates and {report["user_excluded_row_count"]} excluded candidates for later human-owned labeling steps.

This is human-review decision application only. It is not official metric, not gold/qrels, not relevance or answerability labels, not expected answer/evidence approval, not training data, not product-success evidence, not promotion evidence, not FT-A execution, not fine-tuning, and not live DB/index/cache readiness. Locked flags include `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `fine_tuning=false`, `fine_tuning_executed=false`, and `live_db_index_cache_readiness=false`.
"""
    if "## Korean human review packet" in text:
        text = re.sub(
            r"## Korean human review packet\n.*?(?=\n## (?:Evaluation Boundary|평가 경계))",
            section.rstrip() + "\n",
            text,
            count=1,
            flags=re.S,
        )
    elif "\n## 평가 경계" in text:
        text = text.replace("\n## 평가 경계", "\n" + section.rstrip() + "\n\n## 평가 경계", 1)
    else:
        text = text.rstrip() + "\n\n" + section.rstrip() + "\n"
    EVAL_README.write_text(text, encoding="utf-8")


def update_scripts_readme() -> None:
    text = SCRIPTS_README.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod.py` | "
        "Applies the user-reviewed v4_7_2 Korean query candidate CSV as a pass/exclusion decision ledger, "
        "interpreting `미검수` as pass per user clarification when `제외사유` is blank, while keeping official metrics, "
        "gold/qrels, labels, FT-A execution, fine-tuning, training data, promotion evidence, and live readiness closed. |"
    )
    pattern = r"\n?\| `rag_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod\.py` \| .*?\|"
    text = re.sub(pattern, "", text)
    text = text.replace(
        "\n\nv4 scripts remain diagnostic/non-production",
        f"\n{row}\n\nv4 scripts remain diagnostic/non-production",
        1,
    )
    SCRIPTS_README.write_text(text, encoding="utf-8")


def update_progress_doc(report: Mapping[str, Any]) -> None:
    entry = (
        f"- v4_7_3 human-reviewed Korean query candidate pass/exclusion application (`{RUN_ID}`) is {STATUS}. "
        "It applies the user-reviewed CSV over the v4_7_2 hydrated Korean review packet, treating `미검수=통과` "
        "per user clarification when `제외사유` is blank. It freezes query candidate decisions only: "
        f"user-passed {report['user_passed_query_candidate_row_count']} rows and user-excluded {report['user_excluded_row_count']} rows. "
        "It does not create official metric rows, gold/qrels, relevance or answerability labels, expected-answer/evidence approvals, "
        "training data, product-success evidence, promotion evidence, FT-A execution, fine-tuning, or live readiness."
    )
    v47.v4610.v469.v467.replace_marked_entry(PROGRESS_DOC, RUN_ID, entry)
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    text = re.sub(r"Overall status: `[^`]+`;", f"Overall status: `{STATUS}`;", text, count=1)
    PROGRESS_DOC.write_text(text, encoding="utf-8")


def update_measurements_doc(report: Mapping[str, Any]) -> None:
    entry = f"""### v4_7_3 Human-Reviewed Korean Query Candidate Pass/Exclusion Application

- Run: `{RUN_ID}`
- Primary artifact: `{repo_relative(REPORT_JSON)}`; sidecar ledgers are embedded in `report.json` instead of written as JSONL.
- Interpretation: `검수상태=미검수` is user-clarified as pass only when `제외사유` is blank. Non-empty `제외사유` means user-excluded. Query candidate pass remains separate from gold/qrels, labels, expected answers/evidence, and official denominator decisions.

| Counter | Value |
|---|---:|
| reviewed_csv_row_count | {report["reviewed_csv_row_count"]} |
| reviewed_csv_pdf_rows | {report["reviewed_csv_pdf_rows"]} |
| reviewed_csv_xlsx_rows | {report["reviewed_csv_xlsx_rows"]} |
| user_passed_query_candidate_row_count | {report["user_passed_query_candidate_row_count"]} |
| user_excluded_row_count | {report["user_excluded_row_count"]} |
| passed_counts_by_family | PDF {report["passed_counts_by_family"]["PDF"]}, XLSX {report["passed_counts_by_family"]["XLSX"]}, TEXT {report["passed_counts_by_family"]["TEXT"]} |
| excluded_counts_by_family | PDF {report["excluded_counts_by_family"]["PDF"]}, XLSX {report["excluded_counts_by_family"]["XLSX"]}, TEXT {report["excluded_counts_by_family"]["TEXT"]} |
| official_metric_input_rows | 0 |
| gold_jsonl_created | false |
| qrels_jsonl_created | false |
| labels_jsonl_created | false |
| training_dataset_created | false |
| ft_a_execution | false |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |
"""
    v47.v4610.v469.v467.replace_marked_entry(MEASUREMENTS_DOC, RUN_ID, entry)


def update_triage_doc(report: Mapping[str, Any]) -> None:
    entry = f"""### v4_7_3 Human-Reviewed Korean Query Candidate Decision Boundary

- Run: `{RUN_ID}`
- Boundary: this step applies user review decisions to v4_7_2 query candidates only. It does not approve relevance, answerability, expected answers, supporting evidence, qrels, gold records, official denominator rows, or official metric input.
- User clarification: CSV `검수상태=미검수` is not pending for this file; it is interpreted as pass 표기로 override when `제외사유` is blank. Non-empty `제외사유` remains user exclusion text and is preserved in the embedded ledger.
- Applied counters: reviewed rows {report["reviewed_csv_row_count"]}; passed query candidates {report["user_passed_query_candidate_row_count"]}; excluded rows {report["user_excluded_row_count"]}; passed PDF {report["passed_counts_by_family"]["PDF"]}; passed XLSX {report["passed_counts_by_family"]["XLSX"]}.
- Residual risks: all passed query candidates are PDF; all XLSX candidates are user-excluded in this review; expected answers/evidence and relevance/answerability labels remain unresolved; official metric and FT-A remain closed.
- It is not official metric, not product-success evidence, not promotion evidence, not FT-A execution, not fine-tuning, not training data, and not live DB/index/cache readiness.
"""
    v47.v4610.v469.v467.replace_marked_entry(TRIAGE_DOC, RUN_ID, entry)


def update_human_docs(report: Mapping[str, Any]) -> None:
    update_root_readme(report)
    update_eval_readme(report)
    update_scripts_readme()
    update_progress_doc(report)
    update_measurements_doc(report)
    update_triage_doc(report)


def run_write(
    *,
    reviewed_csv_path: Path = DEFAULT_REVIEWED_CSV,
    source_packet_csv_path: Path = SOURCE_PACKET_CSV,
    output_dir: Path = OUTPUT_DIR,
    update_docs: bool = True,
) -> dict[str, Any]:
    report = build_report(reviewed_csv_path=reviewed_csv_path, source_packet_csv_path=source_packet_csv_path)
    written = write_artifacts(report, output_dir=output_dir)
    check_written_artifacts(output_dir)
    if update_docs and output_dir == OUTPUT_DIR:
        update_status(written)
        update_human_docs(written)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--reviewed-csv", type=Path, default=DEFAULT_REVIEWED_CSV)
    parser.add_argument("--source-packet-csv", type=Path, default=SOURCE_PACKET_CSV)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--no-docs", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        report = check_written_artifacts(args.output_dir)
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": report["status"],
                    "reviewed_csv_row_count": report["reviewed_csv_row_count"],
                    "user_passed_query_candidate_row_count": report["user_passed_query_candidate_row_count"],
                    "user_excluded_row_count": report["user_excluded_row_count"],
                    "passed_counts_by_family": report["passed_counts_by_family"],
                    "excluded_counts_by_family": report["excluded_counts_by_family"],
                    "official_metric_input_rows": 0,
                    "v4_7_official_metric_gate_opened": False,
                    "gold_mutation": False,
                    "qrels_mutation": False,
                    "label_mutation": False,
                    "training_dataset_created": False,
                    "ft_a_execution": False,
                    "fine_tuning": False,
                    "promotion_evidence": False,
                    "product_success_evidence_allowed": False,
                    "live_db_index_cache_readiness": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    report = run_write(
        reviewed_csv_path=args.reviewed_csv,
        source_packet_csv_path=args.source_packet_csv,
        output_dir=args.output_dir,
        update_docs=not args.no_docs,
    )
    print(json.dumps({"run_id": RUN_ID, "status": report["status"], "report": report["artifact_paths"]["report_json"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
