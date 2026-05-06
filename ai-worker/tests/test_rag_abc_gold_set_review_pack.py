from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_abc_gold_set_review_pack.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pack = load_module(SCRIPT_PATH, "rag_abc_gold_set_review_pack_for_tests")


def test_labeling_csv_schema_is_minimal_and_has_required_user_columns():
    assert pack.DECISION_COLUMNS == [
        "user_gold_decision",
        "user_answerability_label",
        "user_relevance_label",
        "user_expected_evidence_policy",
        "user_denominator_policy",
        "user_issue_tags",
        "user_notes",
    ]
    for removed_column in [
        "source_gold_file",
        "source_record_origin",
        "current_eval_status",
        "current_failure_or_warning_type",
        "current_denominator_policy",
        "notes_for_reviewer",
        "user_decision_options",
    ]:
        assert removed_column not in pack.REVIEW_FIELDNAMES
    assert pack.REVIEW_FIELDNAMES[-7:] == pack.DECISION_COLUMNS


def test_active_legacy_gold_paths_are_not_default_inputs():
    for removed_name in [
        "gold_queries_v0.csv",
        "gold_queries_xlsx_v1.csv",
        "gold_queries_xlsx_v2.csv",
        "gold_queries_xlsx_v3_naturalized.csv",
        "gold_queries_xlsx_v3_positive.csv",
    ]:
        removed_active_path = pack.EVAL_QUERY_DIR / removed_name
        assert removed_active_path not in pack.DEFAULT_INPUTS.values()

    assert {
        path.name for path in pack.REMOVED_ACTIVE_LEGACY_DATASET_PATHS
    } == {
        "gold_queries_v0.csv",
        "gold_queries_xlsx_v1.csv",
        "gold_queries_xlsx_v2.csv",
        "gold_queries_xlsx_v3_naturalized.csv",
        "gold_queries_xlsx_v3_positive.csv",
    }


def test_suggestions_encode_xlsx_text_pdf_guardrails():
    xlsx_hidden = pack.default_suggestions(
        track="XLSX",
        review_group="hidden_negative_policy_review",
        review_group_tags="hidden_negative_policy_review",
        current_gold_status="archived_or_review_overlay_unresolved_candidate",
    )
    assert xlsx_hidden["suggested_gold_decision"] == "RELABEL_NEGATIVE"
    assert xlsx_hidden["suggested_denominator_policy"] == "EXCLUDE_POSITIVE_DENOMINATOR"
    assert xlsx_hidden["suggested_issue_tags"] == "HIDDEN_NEGATIVE_POLICY"

    text_miss = pack.default_suggestions(
        track="TEXT",
        review_group="retrieval_context_miss_18",
        review_group_tags="retrieval_context_miss_18|expected_answer_or_evidence_review",
        current_gold_status="positive_bound_retrieval_context_miss",
    )
    assert text_miss["suggested_gold_decision"] == "KEEP_POSITIVE"
    assert (
        text_miss["suggested_denominator_policy"]
        == "INCLUDE_POSITIVE_EXCLUDE_CITATION_DENOMINATOR"
    )
    assert "CITATION_DENOMINATOR_EXCLUDED" in text_miss["suggested_issue_tags"]

    pdf_failed = pack.default_suggestions(
        track="PDF",
        review_group="table_gold_policy_review_required",
        review_group_tags="table_gold_policy_review_required|c7_human_decision_required_15",
        current_gold_status="c7_policy_pending_human_decision_required",
    )
    assert pdf_failed["suggested_denominator_policy"] == "BLOCKED_GOLD_POLICY"
    assert pdf_failed["suggested_expected_evidence_policy"] == "REQUIRE_TABLE_LIKE_EVIDENCE"
    assert "PDF_C7_POLICY_PENDING" in pdf_failed["suggested_issue_tags"]


def test_base_record_leaves_user_columns_blank_and_suggestions_enum_bound():
    record = pack.base_record(
        track="TEXT",
        query_id="q1",
        source_gold_file=Path("gold.csv"),
        source_record_origin="fixture",
        bucket="text_fact_lookup",
        query="질문",
        label_status="bound",
        current_gold_status="positive_bound_answerable_from_context",
        review_group="positive_answerable_from_context_29",
        review_group_tags="positive_answerable_from_context_29|must_contain_terms_strictness_review",
    )

    for column in pack.DECISION_COLUMNS:
        assert record[column] == ""
    assert record["suggested_gold_decision"] in pack.USER_GOLD_DECISION_OPTIONS
    assert record["suggested_answerability_label"] in pack.USER_ANSWERABILITY_OPTIONS
    assert record["suggested_relevance_label"] in pack.USER_RELEVANCE_OPTIONS
    assert record["suggested_expected_evidence_policy"] in pack.USER_EXPECTED_EVIDENCE_POLICY_OPTIONS
    assert record["suggested_denominator_policy"] in pack.USER_DENOMINATOR_POLICY_OPTIONS
    for tag in record["suggested_issue_tags"].split(";"):
        if tag:
            assert tag in pack.USER_ISSUE_TAG_OPTIONS
