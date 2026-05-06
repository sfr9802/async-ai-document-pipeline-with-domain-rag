from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_file_content_lane_readiness.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


readiness = load_module(SCRIPT_PATH, "rag_file_content_lane_readiness_for_tests")


def test_r9_lane_readiness_separates_smoke_content_file_and_policy_pending_pdf(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    report = readiness.run_lane_readiness(**paths)
    csv_rows = read_csv(paths["csv_path"])

    assert report["status"] == "PASS_WITH_WARNINGS"
    assert report["promotion_evidence"] is False
    assert report["evidence_role"] == "diagnostic"
    assert report["r1_status"] == "NEEDS_REVIEW"
    assert report["r1_status_preserved"] is True
    assert report["forced_lane_coverage"] is False
    assert report["must_group_by"] == "retrieval_lane"
    assert report["app_text_smoke_separate"] is True
    assert report["pdf_policy_pending"] is True
    assert report["file_lane_official_denominator_ready"] is False
    assert report["promotion_run"] is False
    assert report["indexing_run"] is False
    assert len(csv_rows) == len(readiness.LANES)

    lanes = {row["retrieval_lane"]: row for row in report["lane_readiness_table"]}
    assert lanes["APP_TEXT_SMOKE"]["observed_row_count"] == 2
    assert lanes["APP_TEXT_SMOKE"]["eligible_positive_denominator_count"] == 0
    assert lanes["APP_TEXT_SMOKE"]["readiness_status"] == "SMOKE_ONLY"
    assert lanes["B_NAMU_TEXT_CONTENT"]["observed_row_count"] == 5
    assert lanes["B_NAMU_TEXT_CONTENT"]["eligible_positive_denominator_count"] == 4
    assert lanes["B_NAMU_TEXT_CONTENT"]["excluded_count"] == 1
    assert lanes["B_NAMU_TEXT_CONTENT"]["citation_support_denominator_count"] == 3
    assert lanes["XLSX_CONTENT"]["observed_row_count"] == 2
    assert lanes["XLSX_CONTENT"]["eligible_positive_denominator_count"] == 2
    assert lanes["XLSX_CONTENT"]["readiness_status"] == "DIAGNOSTIC_READY_PROMOTION_BASELINE_BLOCKED"
    assert lanes["PDF_CONTENT"]["observed_row_count"] == 2
    assert lanes["PDF_CONTENT"]["eligible_positive_denominator_count"] == 0
    assert lanes["PDF_CONTENT"]["excluded_count"] == 2
    assert lanes["PDF_CONTENT"]["readiness_status"] == "POLICY_PENDING_DIAGNOSTIC_ONLY"
    assert lanes["TEXT_FILE_LOOKUP"]["readiness_status"] == "NOT_OBSERVED"
    assert lanes["XLSX_FILE"]["readiness_status"] == "NOT_OBSERVED"
    assert lanes["PDF_FILE"]["readiness_status"] == "NOT_OBSERVED"
    assert lanes["UNKNOWN"]["readiness_status"] == "NOT_OBSERVED"
    assert lanes["MIXED_FILE_CONTENT"]["readiness_status"] == "NOT_OBSERVED"


def test_r9_records_observed_file_lanes_as_needing_fixture_or_gold_design(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path, include_file_lane=True)

    report = readiness.run_lane_readiness(**paths)

    lanes = {row["retrieval_lane"]: row for row in report["lane_readiness_table"]}
    assert lanes["XLSX_FILE"]["observed_row_count"] == 1
    assert lanes["XLSX_FILE"]["eligible_positive_denominator_count"] == 0
    assert lanes["XLSX_FILE"]["readiness_status"] == "NEEDS_FIXTURE_OR_GOLD_DESIGN"
    assert report["file_lane_official_denominator_ready"] is False


def test_r9_counts_mixed_file_content_by_retrieval_lane(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path, include_mixed_lane=True)

    report = readiness.run_lane_readiness(**paths)

    lanes = {row["retrieval_lane"]: row for row in report["lane_readiness_table"]}
    assert lanes["MIXED_FILE_CONTENT"]["observed_row_count"] == 1
    assert lanes["MIXED_FILE_CONTENT"]["eligible_positive_denominator_count"] == 0
    assert lanes["MIXED_FILE_CONTENT"]["readiness_status"] == "NEEDS_SPLIT_OR_CLARIFICATION"


def test_r9_fails_closed_before_overwriting_r1_paths(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    original_csv = paths["r1_csv"].read_text(encoding="utf-8")
    original_report = paths["r1_report"].read_text(encoding="utf-8")

    report = readiness.run_lane_readiness(
        **{
            **paths,
            "report_path": paths["r1_report"],
            "csv_path": paths["r1_csv"],
        }
    )

    assert report["status"] == "NEEDS_REVIEW"
    assert any("must not overwrite R1 input path" in blocker for blocker in report["blockers"])
    assert paths["r1_csv"].read_text(encoding="utf-8") == original_csv
    assert paths["r1_report"].read_text(encoding="utf-8") == original_report
    assert report["done_criteria"]["r1_report_not_overwritten"] is True
    assert report["done_criteria"]["r1_csv_not_overwritten"] is True
    assert report["done_criteria"]["r9_report_json_written"] is False
    assert report["done_criteria"]["r9_csv_written"] is False


def test_r9_needs_review_when_r1_report_is_missing(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    paths["r1_report"].unlink()

    report = readiness.run_lane_readiness(**paths)

    assert report["status"] == "NEEDS_REVIEW"
    assert any("missing R1 report" in blocker for blocker in report["blockers"])
    assert report["promotion_evidence"] is False


def write_fixture_bundle(
    tmp_path: Path, *, include_file_lane: bool = False, include_mixed_lane: bool = False
) -> dict[str, Path]:
    r1_csv = tmp_path / "query_intent_routing_matrix_v0.csv"
    r1_report = tmp_path / "rag_query_intent_routing_matrix_report.json"
    namu_gold = tmp_path / "gold_queries_text_namu_v4_v0.csv"
    xlsx_gold = tmp_path / "gold_queries_xlsx_v3_positive_reviewed.csv"
    pdf_gold = tmp_path / "gold_queries_pdf_v0.csv"
    report_path = tmp_path / "rag_file_content_lane_readiness_report.json"
    csv_path = tmp_path / "rag_file_content_lane_readiness.csv"

    write_r1_csv(r1_csv, include_file_lane=include_file_lane, include_mixed_lane=include_mixed_lane)
    write_json(
        r1_report,
        {
            "status": "NEEDS_REVIEW",
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "row_count": 5 + int(include_file_lane) + int(include_mixed_lane),
            "lane_counts": {
                "APP_TEXT_SMOKE": 2,
                "XLSX_CONTENT": 2,
                "PDF_CONTENT": 1,
                "XLSX_FILE": int(include_file_lane),
                "MIXED_FILE_CONTENT": int(include_mixed_lane),
            },
        },
    )
    write_namu_gold(namu_gold)
    write_xlsx_gold(xlsx_gold)
    write_pdf_gold(pdf_gold)
    patch_artifact_paths(tmp_path)
    return {
        "r1_csv": r1_csv,
        "r1_report": r1_report,
        "namu_gold": namu_gold,
        "xlsx_gold": xlsx_gold,
        "pdf_gold": pdf_gold,
        "report_path": report_path,
        "csv_path": csv_path,
    }


def patch_artifact_paths(tmp_path: Path) -> None:
    namu = tmp_path / "namu"
    xlsx = tmp_path / "xlsx"
    pdf = tmp_path / "pdf"
    baseline = tmp_path / "baseline"
    readiness.NAMU_ARTIFACTS = {
        "gold_validate": write_artifact(namu / "gold_validate.json", "PASSED"),
        "retrieval_diagnostic": write_artifact(
            namu / "retrieval.json",
            "PASS_WITH_WARNINGS",
            positive_denominator_count=4,
            needs_review_excluded_count=1,
        ),
        "context_assembly": write_artifact(namu / "context.json", "PASS_WITH_WARNINGS"),
        "answer_eval": write_artifact(
            namu / "answer.json",
            "PASS_WITH_WARNINGS",
            answerable_from_context_count=3,
        ),
        "citation_support": write_artifact(
            namu / "citation.json",
            "PASS_WITH_WARNINGS",
            citation_support_denominator_count=3,
            retrieval_context_miss_excluded_count=1,
            promotion_ready=False,
        ),
    }
    readiness.XLSX_ARTIFACTS = {
        "retrieval_diagnostic": write_artifact(xlsx / "retrieval.json", "COMPLETED"),
        "performance_summary": write_artifact(xlsx / "summary.json", "COMPLETED"),
        "promotion_readiness": write_artifact(
            xlsx / "promotion.json",
            "BLOCKED",
            readiness_summary={"baseline_dataset_compatible_with_cleaned_xlsx_v1": False},
        ),
    }
    readiness.PDF_ARTIFACTS = {
        "gold_policy_review": write_artifact(
            pdf / "policy.json",
            "NEEDS_POLICY_DECISION",
            human_decision_required_count=2,
        ),
        "c7_decision_pack": write_artifact(
            pdf / "c7.json",
            "NEEDS_USER_DECISION",
            human_decision_required_count=2,
            official_denominator_change=False,
            retrieval_tuning_ready=False,
        ),
        "vector_diagnostic": write_artifact(pdf / "vector.json", "PASS_WITH_WARNINGS"),
    }
    readiness.BASELINE_ARTIFACTS = {
        "baseline": write_artifact(
            baseline / "baseline.json",
            "PASS",
            baseline_type="INITIAL_BASELINE_BOOTSTRAP",
            baseline_index_version="baseline",
        )
    }


def write_artifact(path: Path, status: str, **extra) -> Path:
    payload = {
        "status": status,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        **extra,
    }
    write_json(path, payload)
    return path


def write_r1_csv(path: Path, *, include_file_lane: bool, include_mixed_lane: bool) -> None:
    rows = [
        r1_row("app-1", "APP_TEXT_SMOKE", "SMOKE_ONLY", "TEXT", "CONTENT"),
        r1_row("app-2", "APP_TEXT_SMOKE", "SMOKE_ONLY", "TEXT", "CONTENT"),
        r1_row("xlsx-1", "XLSX_CONTENT", "DIAGNOSTIC_READY", "XLSX", "CONTENT"),
        r1_row("xlsx-2", "XLSX_CONTENT", "DIAGNOSTIC_READY", "XLSX", "CONTENT"),
        r1_row("pdf-1", "PDF_CONTENT", "BLOCKED", "PDF", "CONTENT"),
    ]
    if include_file_lane:
        rows.append(r1_row("xlsx-file-1", "XLSX_FILE", "NOT_READY", "XLSX", "FILE"))
    if include_mixed_lane:
        rows.append(r1_row("mixed-1", "MIXED_FILE_CONTENT", "NOT_READY", "PDF", "CONTENT"))
    write_csv(path, readiness_row_fieldnames(), rows)


def r1_row(query_id: str, lane: str, status: str, resource: str, target: str) -> dict[str, str]:
    return {
        "query_id": query_id,
        "source_manifest": "fixture",
        "query": f"{query_id} query",
        "resource_type": resource,
        "target_type": target,
        "answer_mode": "CONTENT_ANSWER" if target == "CONTENT" else "FILE_LIST",
        "retrieval_lane": lane,
        "readiness": status,
        "classification_rule": "fixture",
        "confidence": "high",
        "requires_clarification": "false",
        "notes": "",
    }


def write_namu_gold(path: Path) -> None:
    rows = []
    for index in range(1, 6):
        rows.append(
            {
                "query_id": f"namu-{index}",
                "bucket": "text_fact_lookup",
                "query": f"namu query {index}",
                "expected_page_ids": f"page-{index}",
                "expected_section_ids": f"section-{index}",
                "expected_chunk_ids": f"chunk-{index}",
                "expected_answer_summary": f"answer {index}",
                "must_contain_terms": "",
                "must_not_contain_terms": "",
                "allowed_abstain": "false",
                "answer_type": "short_fact",
                "label_status": "needs_review" if index == 5 else "bound",
                "source_dataset": "fixture",
                "notes": "",
            }
        )
    write_csv(path, list(rows[0]), rows)


def write_xlsx_gold(path: Path) -> None:
    rows = []
    for index in range(1, 3):
        rows.append(
            {
                "query_id": f"xlsx-{index}",
                "query": f"xlsx query {index}",
                "expected_location_type": "xlsx",
                "expected_sheet_name": "Sheet1",
                "expected_cell_range": f"A{index}:B{index}",
                "expected_answer_text": f"answer {index}",
                "label_status": "bound",
                "policy_label": "positive",
                "review_status": "ready_positive",
                "review_decision": "KEEP_AS_POSITIVE",
                "promotion_eval_eligible": "true",
            }
        )
    write_csv(path, list(rows[0]), rows)


def write_pdf_gold(path: Path) -> None:
    rows = []
    for index in range(1, 3):
        rows.append(
            {
                "query_id": f"pdf-{index}",
                "query": f"pdf query {index}",
                "expected_location_type": "pdf",
                "expected_page_no": str(index),
                "expected_answer_text": f"answer {index}",
                "label_status": "bound",
            }
        )
    write_csv(path, list(rows[0]), rows)


def readiness_row_fieldnames() -> list[str]:
    return [
        "query_id",
        "source_manifest",
        "query",
        "resource_type",
        "target_type",
        "answer_mode",
        "retrieval_lane",
        "readiness",
        "classification_rule",
        "confidence",
        "requires_clarification",
        "notes",
    ]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
