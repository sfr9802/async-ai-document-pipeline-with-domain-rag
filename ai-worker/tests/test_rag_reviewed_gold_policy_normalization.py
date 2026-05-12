from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_reviewed_gold_policy_normalization.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_reviewed_gold_policy_normalization", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_reviewed_gold_policy_normalization_actual_pack_counts(tmp_path: Path):
    module = load_module()
    report_json = tmp_path / "report.json"
    report_md = tmp_path / "report.md"

    result = module.main(["--report-json", str(report_json), "--report-md", str(report_md)])

    assert result == 0
    report = json.loads(report_json.read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert report["guardrails"]["official_denominator_registry_changed"] is False
    assert report["guardrails"]["official_denominator_opened"] is False
    assert report["guardrails"]["diagnostic_only_row_promoted"] is False
    assert report["guardrails"]["retrieval_variants_run"] is False

    assert report["validation"]["text_namu_v2"]["actual_row_count"] == 100
    assert report["validation"]["xlsx_human_review"]["actual_row_count"] == 50
    assert report["validation"]["pdf_file_lookup_companion"]["actual_row_count"] == 28

    text = report["tracks"]["text_namu_v2"]
    assert text["proposed_official_candidate_count"] == 66
    assert text["diagnostic_only_count"] == 10
    assert text["source_verification_required_count"] == 7
    assert text["review_marker_buckets"]["needs_second_review"] == [
        "text_namu_v2_0010",
        "text_namu_v2_0078",
        "text_namu_v2_0080",
    ]
    assert text["review_marker_buckets"]["expected_answer_revision"] == [
        "text_namu_v2_0006",
        "text_namu_v2_0029",
    ]
    assert text["review_marker_buckets"]["expected_answer_and_evidence_revision"] == ["text_namu_v2_0013"]
    assert "text_namu_v2_0046" in text["diagnostic_only_query_ids"]
    assert "text_namu_v2_0046" not in text["proposed_official_candidate_query_ids"]

    xlsx = report["tracks"]["xlsx_human_review"]
    assert xlsx["proposed_official_candidate_count"] == 25
    assert xlsx["official_denominator_frozen_count"] == 0
    assert xlsx["denominator_confirmation_required_count"] == 25
    assert xlsx["source_verification_required_count"] == 10
    assert xlsx["unresolved_user_review_count"] == 35
    assert xlsx["evidence_mismatch_count"] == 7
    assert xlsx["policy_excluded_count"] == 7
    assert xlsx["diagnostic_only_count"] == 1
    assert xlsx["empty_user_gold_policy_decision_count"] == 50
    assert xlsx["empty_user_include_in_official_denominator_count"] == 50

    pdf = report["tracks"]["pdf_file_lookup_companion"]
    assert pdf["content_evidence_positive_count"] == 14
    assert pdf["file_lookup_identity_candidate_count"] == 5
    assert pdf["proposed_official_candidate_count"] is None
    assert pdf["proposed_official_candidate_query_ids"] == []
    assert pdf["official_denominator_frozen_count"] == 0
    assert pdf["expected_answer_or_evidence_revision_count"] == 9
    assert pdf["policy_excluded_count"] == 6
    assert pdf["diagnostic_only_count"] == 0
    assert "pdf_file_lookup_content_anchor_004" in pdf["expected_answer_or_evidence_revision_query_ids"]
    assert "pdf_file_lookup_content_anchor_014" not in pdf["content_evidence_positive_query_ids"]


def test_pdf_not_answerable_and_irrelevant_are_not_content_positive():
    module = load_module()
    rows = [
        {
            "query_id": "pdf_ok",
            "user_gold_decision": "KEEP_POSITIVE",
            "user_answerability_label": "ANSWERABLE",
            "user_relevance_label": "RELEVANT",
            "user_expected_evidence_policy": "KEEP_CURRENT_EVIDENCE",
            "user_denominator_policy": "INCLUDE_POSITIVE_DENOMINATOR_AFTER_USER_REVIEW",
            "risk_tags": "PDF_FILE_LOOKUP",
        },
        {
            "query_id": "pdf_bad",
            "user_gold_decision": "REVISE_EXPECTED_EVIDENCE",
            "user_answerability_label": "NOT_ANSWERABLE",
            "user_relevance_label": "IRRELEVANT",
            "user_expected_evidence_policy": "REVISE_EXPECTED_EVIDENCE",
            "user_denominator_policy": "INCLUDE_POSITIVE_DENOMINATOR_AFTER_USER_REVIEW",
            "risk_tags": "PDF_FILE_LOOKUP",
        },
    ]

    result = module.normalize_pdf(rows)

    assert result["content_evidence_positive_query_ids"] == ["pdf_ok"]
    assert result["expected_answer_or_evidence_revision_query_ids"] == ["pdf_bad"]
    assert result["policy_excluded_query_ids"] == ["pdf_bad"]
    assert result["proposed_official_candidate_count"] is None
    assert result["proposed_official_candidate_query_ids"] == []


def test_xlsx_blank_denominator_fields_are_not_frozen_official_gold():
    module = load_module()
    result = module.normalize_xlsx(
        [
            {
                "query_id": "xlsx_candidate",
                "user_answerability_label": "ANSWERABLE_CONFIRMED",
                "user_relevance_label": "EVIDENCE_RELEVANT",
                "user_gold_policy_decision": "",
                "user_include_in_official_denominator": "",
            }
        ]
    )

    assert result["proposed_official_candidate_query_ids"] == ["xlsx_candidate"]
    assert result["official_denominator_frozen_count"] == 0
    assert result["denominator_confirmation_required_query_ids"] == ["xlsx_candidate"]
    assert result["unresolved_user_review_rows"] == ["xlsx_candidate"]


def test_validate_pack_reports_schema_row_count_and_id_errors():
    module = load_module()
    result = module.validate_pack(
        rows=[
            {"query_id": "dup", "required": "x"},
            {"query_id": "dup", "required": "y"},
            {"query_id": "", "required": "z"},
        ],
        columns=["query_id", "required", "missing"],
        expected_row_count=2,
        query_id_column="query_id",
    )

    assert result["status"] == "FAIL"
    assert result["actual_row_count"] == 3
    assert result["missing_columns"] == ["missing"]
    assert result["duplicate_query_ids"] == ["dup"]
    assert result["blank_query_id_count"] == 1
