from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "ai" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import rag_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod as v473


RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod"
STATUS = "V4_7_3_HUMAN_REVIEWED_KOREAN_QUERY_CANDIDATE_PASS_EXCLUSION_APPLICATION_NONPROD_READY"
EVENT_TYPE = "diagnostic_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod"
SOURCE_RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod"
SOURCE_REGISTRATION_RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod"

REPORT_DIR = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / RUN_ID
REPORT_JSON = REPORT_DIR / "report.json"
SOURCE_PACKET_CSV = (
    ROOT
    / "ai"
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "quality"
    / SOURCE_RUN_ID
    / "review_packet_ko_hydrated.csv"
)
STATUS_JSONL = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "status.jsonl"
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"
MEASUREMENTS_DOC = ROOT / "docs" / "rag-ingestion-measurements.md"
TRIAGE_DOC = ROOT / "docs" / "rag-ingestion-triage.md"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _family_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = Counter((row.get("source_family") or row.get("소스계열") or "").strip() for row in rows)
    return {family: counts.get(family, 0) for family in ("PDF", "XLSX", "TEXT")}


def test_v4_7_3_reviewed_csv_decision_application_contract() -> None:
    assert REPORT_JSON.exists()
    assert SOURCE_PACKET_CSV.exists()
    assert v473.DEFAULT_REVIEWED_CSV.exists()

    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    source_rows = _read_csv(SOURCE_PACKET_CSV)
    reviewed_rows = _read_csv(v473.DEFAULT_REVIEWED_CSV)
    ledger = report["review_decision_ledger"]
    passed = report["passed_query_candidates"]

    assert len(reviewed_rows) == 204
    assert _family_counts(reviewed_rows) == {"PDF": 100, "XLSX": 104, "TEXT": 0}
    assert len(ledger) == 204
    assert len(passed) == 58

    key_columns = ("후보ID", "질의ID", "candidate_id_hash", "query_id_hash", "source_family")
    source_keys = [tuple((row.get(column) or "").strip() for column in key_columns) for row in source_rows]
    reviewed_keys = [tuple((row.get(column) or "").strip() for column in key_columns) for row in reviewed_rows]
    assert reviewed_keys == source_keys
    assert len(set(reviewed_keys)) == 204

    assert report["schema_version"] == "rag_v4_7_3_human_reviewed_korean_query_candidate_decision_report_v1"
    assert report["run_id"] == RUN_ID
    assert report["source_run_id"] == SOURCE_RUN_ID
    assert report["source_registration_run_id"] == SOURCE_REGISTRATION_RUN_ID
    assert report["status"] == STATUS
    assert report["diagnostic_only"] is True
    assert report["human_review_applied"] is True
    assert report["user_clarification_applied"] is True
    assert report["csv_migeomsu_interpreted_as_pass"] is True
    assert report["query_candidate_pass_mutation"] is True
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["reviewed_csv_row_count"] == 204
    assert report["reviewed_csv_pdf_rows"] == 100
    assert report["reviewed_csv_xlsx_rows"] == 104
    assert report["user_passed_query_candidate_row_count"] == 58
    assert report["user_excluded_row_count"] == 146
    assert report["passed_counts_by_family"] == {"PDF": 58, "XLSX": 0, "TEXT": 0}
    assert report["excluded_counts_by_family"] == {"PDF": 42, "XLSX": 104, "TEXT": 0}

    assert all(row["review_status_original"] == "미검수" for row in ledger)
    assert all(row["csv_migeomsu_interpreted_as_pass"] is True for row in ledger)
    assert all(row["official_denominator_eligible"] is False for row in ledger)
    assert all(row["gold_status"] == "not_gold" for row in ledger)
    assert all(row["qrels_status"] == "not_qrels" for row in ledger)
    assert all(row["label_status"] == "not_labeled" for row in ledger)
    assert all(row["expected_answer_status"] == "unresolved_user_owned_blank" for row in ledger)
    assert all(row["supporting_evidence_status"] == "unresolved_user_owned_blank" for row in ledger)
    assert all(row["official_denominator_decision_original"] == "보류" for row in ledger)

    passed_rows = [row for row in ledger if row["decision_status"] == "user_passed_query_candidate"]
    excluded_rows = [row for row in ledger if row["decision_status"] == "user_excluded"]
    assert len(passed_rows) == 58
    assert len(excluded_rows) == 146
    assert Counter(row["source_family"] for row in passed_rows) == {"PDF": 58}
    assert Counter(row["source_family"] for row in excluded_rows) == {"PDF": 42, "XLSX": 104}
    assert all(row["query_candidate_passed"] is True for row in passed_rows)
    assert all(row["exclusion_reason_user_text"] == "" for row in passed_rows)
    assert all(
        row["acceptance_basis"] == "user_clarified_csv_migeomsu_means_pass_and_blank_exclusion_reason"
        for row in passed_rows
    )
    assert all(row["query_candidate_passed"] is False for row in excluded_rows)
    assert all(row["exclusion_reason_user_text"].strip() for row in excluded_rows)

    assert {row["candidate_id_hash"] for row in passed} == {row["candidate_id_hash"] for row in passed_rows}
    assert {row["query_id_hash"] for row in passed} == {row["query_id_hash"] for row in passed_rows}
    assert all(row["source_family"] == "PDF" for row in passed)


def test_v4_7_3_guardrails_docs_status_and_idempotence() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    rebuilt = v473.build_report(
        reviewed_csv_path=v473.DEFAULT_REVIEWED_CSV,
        source_packet_csv_path=SOURCE_PACKET_CSV,
        generated_at=report["generated_at"],
    )

    assert rebuilt["decision_ledger_sha256"] == report["decision_ledger_sha256"]
    assert rebuilt["passed_query_candidates_sha256"] == report["passed_query_candidates_sha256"]
    assert rebuilt["reviewed_csv_sha256"] == report["reviewed_csv_sha256"]
    assert report["artifact_paths"] == {"report_json": REPORT_JSON.relative_to(ROOT).as_posix()}
    assert sorted(path.name for path in REPORT_DIR.iterdir()) == ["report.json"]

    for key in (
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
    ):
        assert report[key] is False, key
    assert report["protected_namespaces_touched"] == []

    events = _read_jsonl(STATUS_JSONL)
    matches = [
        event
        for event in events
        if event.get("run_id") == RUN_ID and event.get("event_type") == EVENT_TYPE
    ]
    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == STATUS
    assert event["artifact_paths"] == report["artifact_paths"]
    assert event["artifact_sha256"]["report_json_sha256"] == _sha256_file(REPORT_JSON)
    assert event["csv_migeomsu_interpreted_as_pass"] is True
    assert event["user_passed_query_candidate_row_count"] == 58
    assert event["user_excluded_row_count"] == 146
    assert event["official_metric_input_rows"] == 0
    assert event["gold_mutation"] is False
    assert event["qrels_mutation"] is False
    assert event["label_mutation"] is False
    assert event["training_dataset_created"] is False

    progress_current = PROGRESS_DOC.read_text(encoding="utf-8").split("## Short History", 1)[0]
    progress_section = progress_current.split(f"<!-- {RUN_ID}:progress-entry:start -->", 1)[1].split(
        f"<!-- {RUN_ID}:progress-entry:end -->",
        1,
    )[0]
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_7_3 Human-Reviewed Korean Query Candidate Pass/Exclusion Application",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_7_3 Human-Reviewed Korean Query Candidate Decision Boundary",
        1,
    )[1].split("\n### ", 1)[0]

    assert RUN_ID in progress_current
    assert "미검수=통과" in progress_current
    assert "official metric rows" in progress_current
    assert "| reviewed_csv_row_count | 204 |" in measurements_section
    assert "| user_passed_query_candidate_row_count | 58 |" in measurements_section
    assert "| user_excluded_row_count | 146 |" in measurements_section
    assert "| passed_counts_by_family | PDF 58, XLSX 0, TEXT 0 |" in measurements_section
    assert "| excluded_counts_by_family | PDF 42, XLSX 104, TEXT 0 |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "| training_dataset_created | false |" in measurements_section
    assert RUN_ID in triage_section
    assert "미검수" in triage_section
    assert "pass 표기로 override" in triage_section
    assert "all XLSX candidates are user-excluded" in triage_section

    generated_text = "\n".join(
        [
                REPORT_JSON.read_text(encoding="utf-8"),
                progress_section,
                measurements_section,
                triage_section,
            ]
        )
    forbidden_patterns = (
        r"\bD:[\\/]",
        r"v4_7_external_pdf_document_sha256_",
        r"v4_7_external_xlsx_workbook_sha256_",
        r"source_identity_key",
        r"target_locator",
        r"gold_locator",
        r"expected_answer_used_as_source",
        r"supporting_evidence_used_as_source",
        r"official_metric_input_rows\.jsonl",
        r"training dataset artifact",
        r"prompt_payload",
        r"raw_llm_response",
        r"checkpoint artifact written",
        r"formula_text",
    )
    for pattern in forbidden_patterns:
        assert not re.search(pattern, generated_text), pattern
