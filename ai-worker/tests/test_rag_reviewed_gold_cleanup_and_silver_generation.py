from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_reviewed_gold_cleanup_and_silver_generation.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_reviewed_gold_cleanup_and_silver_generation", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_reviewed_gold_cleanup_generates_candidate_freeze_and_silver_sets(tmp_path: Path):
    module = load_module()
    output_dir = tmp_path / "review"
    report_dir = tmp_path / "reports"

    result = module.main(
        [
            "--output-dir",
            str(output_dir),
            "--report-dir",
            str(report_dir),
            "--no-update-progress",
        ]
    )

    assert result == 0
    manifest = json.loads((report_dir / "denominator_manifest.json").read_text(encoding="utf-8"))

    assert manifest["gold_frozen"]["official_denominator_registry_changed"] is False
    assert manifest["gold_frozen"]["promotion_evidence"] is False
    assert manifest["gold_frozen"]["denominator_candidates"] == {
        "pdf_file_lookup_candidate_count": 15,
        "pdf_file_lookup_deferred_or_excluded_count": 9,
        "pdf_file_lookup_diagnostic_count": 4,
        "text_abstain_diagnostic_count": 10,
        "text_deferred_or_excluded_count": 21,
        "text_main_positive_candidate_count": 69,
    }
    assert manifest["text_cleanup"]["conflict_rows"]
    assert manifest["text_cleanup"]["missing_override_rows"] == [
        "text_namu_v2_0006",
        "text_namu_v2_0013",
        "text_namu_v2_0029",
    ]
    assert manifest["pdf_cleanup"]["generic_filename_rows"]

    silver = manifest["silver"]
    assert silver["leakage"]["status"] == "PASS"
    assert silver["leakage"]["query_id_overlap_count"] == 0
    assert silver["leakage"]["query_text_overlap_count"] == 0
    assert silver["leakage"]["source_query_id_overlap_count"] == 0
    assert silver["leakage"]["expected_id_overlap_count"] == 0
    assert silver["row_counts"]["silver_text_positive_train"] > 0
    assert silver["row_counts"]["silver_text_hard_negative_train"] > 0
    assert silver["row_counts"]["silver_pdf_file_lookup_positive_train"] > 0
    assert silver["row_counts"]["silver_pdf_file_lookup_hard_negative_train"] > 0


def test_pdf_file_lookup_outputs_claim_file_identity_only(tmp_path: Path):
    module = load_module()
    output_dir = tmp_path / "review"
    report_dir = tmp_path / "reports"
    module.main(["--output-dir", str(output_dir), "--report-dir", str(report_dir), "--no-update-progress"])

    positive_rows = read_csv(output_dir / "pdf_file_lookup_gold_positive_clean.csv")
    assert positive_rows
    for row in positive_rows:
        assert "expected_page_no" not in row
        assert "expected_page_label" not in row
        assert "expected_bbox" not in row
        assert "expected_evidence_excerpt" not in row
        assert row["diagnostic_page_no"]
        assert row["diagnostic_evidence_excerpt"]
        assert row["denominator_role"] == "PDF_FILE_LOOKUP_GOLD_CANDIDATE"
        assert row["retrieval_lane_clean"] == "pdf_file_lookup"
        assert row["user_answerability_label_clean"] == "ANSWERABLE_AS_FILE_LOOKUP"
        assert row["user_expected_evidence_policy_clean"] == "EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY"
        assert row["official_gold"] == "false"

    report = (report_dir / "silver_generation_report.md").read_text(encoding="utf-8")
    assert "No page, bbox, table, row, column, or value semantics are used or claimed." in report


def test_silver_leakage_check_catches_source_ids_and_carryover_expected_ids():
    module = load_module()
    frozen = {
        "query_ids": {"gold_qid"},
        "queries": {"gold query"},
        "source_query_ids": {"gold_source_qid"},
        "expected_ids": {"gold_doc", "gold_file.pdf"},
    }

    report = module.run_silver_leakage_checks(
        [
            {
                "query_id": "silver_001",
                "source_query_id": "gold_source_qid",
                "query": "fresh query",
                "positive_expected_document_ids": "gold_doc",
                "expected_document_ids": "other_doc",
            },
            {
                "query_id": "silver_002",
                "source_query_id": "fresh_source",
                "query": "another fresh query",
                "positive_expected_file_name": "gold_file.pdf",
                "expected_file_name": "other_file.pdf",
            },
        ],
        frozen,
    )

    assert report["status"] == "FAIL"
    assert report["source_query_id_overlap_count"] == 1
    assert report["expected_id_overlap_count"] == 2


def test_conflicted_abstain_text_row_is_deferred_not_diagnostic():
    module = load_module()
    row = {column: "" for column in module.clean_text_fieldnames()}
    row.update(
        {
            "query_id": "text_conflict_abstain",
            "bucket": "abstain_not_answerable_diagnostic",
            "query": "확인 어려운 질문",
            "expected_answer_text": "답",
            "source_evidence_quote": "근거 문장",
            "expected_document_ids": "doc1",
            "expected_page_ids": "doc1",
            "expected_section_ids": "sec1",
            "expected_chunk_ids": "chunk1",
            "source_locator": "source_namespace=TEXT_NAMU_V4; page_id=doc1; chunk_id=chunk1",
            "candidate_default_policy": "DIAGNOSTIC_ONLY_DEFAULT",
            "source_query_id": "src1",
            "source_label_status": "bound",
            "user_final_gold_policy": "KEEP_POSITIVE",
            "user_answerability_label": "ANSWERABLE, INVALID_QUERY",
            "user_relevance_label": "RELEVANT",
        }
    )

    result = module.clean_text_gold(
        [row],
        module.required_text_columns(),
        {"chunk1": {"chunk_text": "앞부분 근거 문장 뒷부분"}},
    )

    assert len(result["abstain_diagnostic"]) == 0
    assert len(result["deferred_or_excluded"]) == 1
    assert result["deferred_or_excluded"][0]["cleanup_status"] == "DEFERRED_LABEL_CONFLICT"
    assert result["deferred_or_excluded"][0]["denominator_role"] == "DEFERRED"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
