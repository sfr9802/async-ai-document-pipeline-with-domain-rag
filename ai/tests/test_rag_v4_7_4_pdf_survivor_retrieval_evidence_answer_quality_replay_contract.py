from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "ai" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import rag_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod as v474


RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod"
STATUS = "V4_7_4_PDF_SURVIVOR_RETRIEVAL_EVIDENCE_ANSWER_QUALITY_REPLAY_NONPROD_READY"
EVENT_TYPE = "diagnostic_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod"
SOURCE_RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod"
SOURCE_HYDRATION_RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod"

REPORT_DIR = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / RUN_ID
REPORT_JSON = REPORT_DIR / "report.json"
V4_7_3_REPORT_JSON = (
    ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / SOURCE_RUN_ID / "report.json"
)
V4_7_2_PACKET_CSV = (
    ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / SOURCE_HYDRATION_RUN_ID / "review_packet_ko_hydrated.csv"
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


def test_v4_7_4_selects_only_pdf_survivors_and_reports_replay_metrics() -> None:
    assert REPORT_JSON.exists()
    assert V4_7_3_REPORT_JSON.exists()
    assert V4_7_2_PACKET_CSV.exists()

    source_report = json.loads(V4_7_3_REPORT_JSON.read_text(encoding="utf-8"))
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    hydrated_rows = _read_csv(V4_7_2_PACKET_CSV)
    hydrated_by_hash = {
        (row["candidate_id_hash"], row["query_id_hash"]): row
        for row in hydrated_rows
    }
    passed_pdf_keys = {
        (row["candidate_id_hash"], row["query_id_hash"])
        for row in source_report["passed_query_candidates"]
        if row["source_family"] == "PDF" and row["query_candidate_passed"] is True
    }
    replay_keys = {
        (row["candidate_id_hash"], row["query_id_hash"])
        for row in report["pdf_survivor_replay_ledger"]
    }

    assert len(passed_pdf_keys) == 58
    assert replay_keys == passed_pdf_keys
    assert all(key in hydrated_by_hash for key in replay_keys)

    assert report["schema_version"] == "rag_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_report_v1"
    assert report["run_id"] == RUN_ID
    assert report["source_run_id"] == SOURCE_RUN_ID
    assert report["source_hydration_run_id"] == SOURCE_HYDRATION_RUN_ID
    assert report["status"] == STATUS
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["pdf_survivor_row_count"] == 58
    assert report["xlsx_rows_in_scope"] == 0
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["protected_namespaces_touched"] == []
    assert report["raw_pdf_query_time_parsing"] is False
    assert report["broad_source_atom_scan_attempt_count"] == 0
    assert report["vector_payload_evidence_truth_violation_count"] == 0
    assert report["hidden_target_locator_used"] is False
    assert report["expected_or_supporting_gold_text_used"] is False
    assert report["source_file_title_shortcut_used"] is False

    metrics = report["metrics"]
    assert set(metrics) == {
        "file_identity",
        "locator",
        "evidence_bundle",
        "llm_answer_quality",
        "failure_taxonomy",
    }
    file_identity = metrics["file_identity"]
    locator = metrics["locator"]
    evidence = metrics["evidence_bundle"]
    answer_quality = metrics["llm_answer_quality"]
    taxonomy = metrics["failure_taxonomy"]

    assert file_identity["pdf_survivor_row_count"] == 58
    assert len(file_identity["document_candidate_count_by_row"]) == 58
    assert all(count >= 1 for count in file_identity["document_candidate_count_by_row"])
    assert 0 <= file_identity["file_identity_hit_proxy_at1"] <= 58
    assert file_identity["file_identity_hit_proxy_at1"] <= file_identity["file_identity_hit_proxy_at3"] <= 58
    assert file_identity["hidden_target_or_gold_locator_used"] is False
    assert 0 <= file_identity["query_visible_locator_signal_present_count"] <= 58

    assert locator["page_locator_signal_present_count"] == 58
    assert 0 <= locator["page_candidate_hit_proxy_at1"] <= 58
    assert locator["page_candidate_hit_proxy_at1"] <= locator["page_candidate_hit_proxy_at3"] <= 58
    assert locator["block_candidate_available_count"] == 58
    assert locator["bbox_metric_computed"] is False

    assert evidence["evidence_bundle_created_count"] == 58
    assert evidence["source_atom_hydration_success_count"] == 58
    assert evidence["evidence_window_sufficient_proxy_count"] == 35
    assert evidence["weak_evidence_window_count"] == 23
    assert evidence["duplicate_or_redundant_evidence_count"] == 0
    assert evidence["citation_candidate_count"] == 58
    assert 0 <= evidence["citation_support_proxy_count"] <= 58
    assert evidence["vector_payload_evidence_truth_violation_count"] == 0

    assert answer_quality["answer_ready_evidence_bundle_count"] == 35
    assert answer_quality["fail_closed_before_llm_count"] == 23
    assert answer_quality["L8_generation_executed"] is (answer_quality["local_llm_available"] and answer_quality["generated_response_count"] > 0)
    assert 0 <= answer_quality["generated_response_count"] <= 35
    assert 0 <= answer_quality["parsed_final_answer_present_count"] <= answer_quality["generated_response_count"]
    assert 0 <= answer_quality["citation_rendered_count"] <= answer_quality["generated_response_count"]
    assert 0 <= answer_quality["abstain_count"] <= 35
    assert answer_quality["answer_plan_created_count"] <= 35
    assert (
        answer_quality["claim_support_verifier_pass_count"]
        + answer_quality["claim_support_verifier_fail_count"]
        <= answer_quality["generated_response_count"]
    )

    for bucket in (
        "FILE_IDENTITY_MISS",
        "FILE_IDENTITY_AMBIGUOUS",
        "RIGHT_FILE_WRONG_PAGE",
        "RIGHT_PAGE_WEAK_WINDOW",
        "TABLE_OR_FIGURE_STRUCTURE_LOST",
        "CONTEXT_NEIGHBOR_MISSING",
        "EVIDENCE_UNDERUSE",
        "OVER_ABSTAIN",
        "UNSUPPORTED_CLAIM_RISK",
        "ANSWER_READY",
        "CONTRACT_FAIL_CLOSED",
    ):
        assert bucket in taxonomy
        assert taxonomy[bucket] >= 0
    assert taxonomy["ANSWER_READY"] == 35
    assert taxonomy["RIGHT_PAGE_WEAK_WINDOW"] == 23

    ledger = report["pdf_survivor_replay_ledger"]
    assert len(ledger) == 58
    assert all(row["source_family"] == "PDF" for row in ledger)
    assert all(row["decision_status"] == "user_passed_query_candidate" for row in ledger)
    assert all(row["query_candidate_passed"] is True for row in ledger)
    assert all(row["evidence_bundle_source"] == "v4_7_2_hydrated_packet_bounded_preview" for row in ledger)
    assert all(row["SearchView_vector_payload_role"] == "candidate_only" for row in ledger)
    assert all(row["SourceAtom_EvidenceBundle_role"] == "evidence_truth" for row in ledger)
    assert all(row["raw_pdf_query_time_parsing"] is False for row in ledger)
    assert all(row["hidden_target_locator_used"] is False for row in ledger)
    assert all(row["expected_or_supporting_gold_text_used"] is False for row in ledger)
    assert all(not row["llm_invoked"] for row in ledger if row["answer_ready_evidence_bundle"] is False)
    if answer_quality["local_llm_available"]:
        generated = [row for row in ledger if row["llm_invoked"]]
        assert generated
        assert all(row["answer_quality_diagnostics"]["raw_response_sha256"] for row in generated)
        assert all("raw_response_payload" not in row["answer_quality_diagnostics"] for row in generated)
    else:
        assert answer_quality["generated_response_count"] == 0
        assert all(not row["llm_invoked"] for row in ledger)


def test_v4_7_4_docs_status_guardrails_and_idempotence() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    rebuilt = v474.build_report(
        source_report_path=V4_7_3_REPORT_JSON,
        hydration_packet_csv_path=V4_7_2_PACKET_CSV,
        generated_at=report["generated_at"],
        execute_llm=False,
    )
    report_no_llm = {key: value for key, value in report.items() if key != "metrics"}

    assert rebuilt["pdf_survivor_selection_sha256"] == report["pdf_survivor_selection_sha256"]
    assert rebuilt["deterministic_replay_input_sha256"] == report["deterministic_replay_input_sha256"]
    assert rebuilt["pdf_survivor_row_count"] == report["pdf_survivor_row_count"] == 58
    assert rebuilt["metrics"]["file_identity"] == report["metrics"]["file_identity"]
    assert rebuilt["metrics"]["locator"] == report["metrics"]["locator"]
    assert rebuilt["metrics"]["evidence_bundle"] == report["metrics"]["evidence_bundle"]
    assert report_no_llm["artifact_paths"] == {"report_json": REPORT_JSON.relative_to(ROOT).as_posix()}
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
    ):
        assert report[key] is False, key

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
    assert event["pdf_survivor_row_count"] == 58
    assert event["xlsx_rows_in_scope"] == 0
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
        "### v4_7_4 PDF Survivor Retrieval/Evidence/Answer Quality Replay",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_7_4 PDF Survivor Failure Taxonomy And Decision Boundary",
        1,
    )[1].split("\n### ", 1)[0]

    assert f"Overall status: `{STATUS}`;" in progress_current
    assert RUN_ID in progress_section
    assert "PDF survivor 58" in progress_section
    assert "not official metric" in progress_section
    assert "| pdf_survivor_row_count | 58 |" in measurements_section
    assert "| xlsx_rows_in_scope | 0 |" in measurements_section
    assert "| evidence_window_sufficient_proxy_count | 35 |" in measurements_section
    assert "| weak_evidence_window_count | 23 |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "| training_dataset_created | false |" in measurements_section
    assert RUN_ID in triage_section
    assert "RIGHT_PAGE_WEAK_WINDOW" in triage_section
    assert "ANSWER_READY" in triage_section
    assert "XLSX remains parked" in triage_section

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
        r"(?<!hidden_)target_locator",
        r"(?<!hidden_target_or_)gold_locator",
        r"expected_answer_used_as_source",
        r"supporting_evidence_used_as_source",
        r"official_metric_input_rows\.jsonl",
        r"training dataset artifact",
        r"prompt_payload",
        r"raw_llm_response",
        r"raw_response_payload",
        r"checkpoint artifact written",
        r"formula_text",
    )
    for pattern in forbidden_patterns:
        assert not re.search(pattern, generated_text), pattern
