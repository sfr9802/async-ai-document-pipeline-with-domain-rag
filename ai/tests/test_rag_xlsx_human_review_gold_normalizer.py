from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_WORKER_ROOT = ROOT / "ai"
MODULE_PATH = AI_WORKER_ROOT / "scripts" / "rag_xlsx_human_review_gold_normalizer.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_xlsx_human_review_gold_normalizer", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


normalizer = load_module()


def test_normalizer_derives_strict_official_subset_without_overwriting_user_labels(tmp_path: Path):
    review_pack = tmp_path / "review.csv"
    rows = [
        row(
            query_id="q_valid",
            evidence_summary="Alpha row has value 123.",
            evidence_headers='["Name","Value"]',
            user_answerability_label="ANSWERABLE_CONFIRMED",
            user_relevance_label="EVIDENCE_RELEVANT",
            user_gold_answer_shape="CELL_VALUE",
            expected_answer_text_existing="Alpha Value",
            must_contain_terms_existing='["Alpha","Value"]',
            sheet="Sheet1",
            cell_range="A1:B2",
            citation_locator='{"sheet":"Sheet1","range":"A1:B2","file":"book.xlsx"}',
            user_gold_policy_decision="",
            user_include_in_official_denominator="",
        ),
        row(
            query_id="q_empty_locator",
            evidence_summary="Alpha row has value 123.",
            user_answerability_label="ANSWERABLE_CONFIRMED",
            user_relevance_label="EVIDENCE_RELEVANT",
            user_gold_answer_shape="CELL_VALUE",
            citation_locator="{}",
            sheet="",
            cell_range="",
        ),
        row(
            query_id="q_mismatch",
            user_answerability_label="ANSWERABLE_NEEDS_SOURCE_VERIFICATION",
            user_relevance_label="EVIDENCE_MISMATCH",
            user_gold_answer_shape="ROW_SUMMARY",
            citation_locator='{"sheet":"Sheet1","range":"A1:B2"}',
            sheet="Sheet1",
            cell_range="A1:B2",
        ),
        row(
            query_id="q_pending",
            evidence_summary="Needs source check.",
            user_answerability_label="ANSWERABLE_NEEDS_SOURCE_VERIFICATION",
            user_relevance_label="EVIDENCE_PARTIAL",
            user_gold_answer_shape="ROW_SUMMARY",
            citation_locator='{"sheet":"Sheet1","range":"A1:B2"}',
            sheet="Sheet1",
            cell_range="A1:B2",
        ),
    ]
    write_csv(review_pack, rows)

    report = normalizer.run_normalization(
        review_pack=review_pack,
        output=tmp_path / "normalized.csv",
        official_output=tmp_path / "official.csv",
        jsonl_output=tmp_path / "normalized.jsonl",
        report_path=tmp_path / "report.json",
        artifact_root=tmp_path / "runs",
        dataset_root=tmp_path / "datasets",
        registry_path=tmp_path / "registry.json",
        expected_row_count=4,
        run_id="test",
    )

    assert report["status"] == "PASS"
    assert report["official_positive_count"] == 1
    assert report["official_positive_retrieval_count"] == 1
    assert report["official_xlsx_answer_generation_denominator"] == 0
    assert report["diagnostic_only_count"] == 1
    assert report["pending_source_verification_count"] == 1
    assert report["excluded_count"] == 1

    normalized_rows = read_csv(tmp_path / "normalized.csv")
    by_id = {item["query_id"]: item for item in normalized_rows}
    assert by_id["q_valid"]["user_gold_policy_decision"] == ""
    assert by_id["q_valid"]["user_include_in_official_denominator"] == ""
    assert by_id["q_valid"]["derived_denominator_policy"] == normalizer.OFFICIAL_POLICY
    assert by_id["q_empty_locator"]["derived_denominator_policy"] == normalizer.DIAGNOSTIC_POLICY
    assert "invalid_or_empty_citation_locator" in by_id["q_empty_locator"]["derived_policy_reasons"]
    assert by_id["q_mismatch"]["derived_denominator_policy"] == normalizer.EXCLUDED_POLICY
    assert by_id["q_pending"]["derived_denominator_policy"] == normalizer.PENDING_POLICY

    official_rows = read_csv(tmp_path / "official.csv")
    assert [item["query_id"] for item in official_rows] == ["q_valid"]
    assert official_rows[0]["citation_locator"] != "{}"
    assert official_rows[0]["sheet"] == "Sheet1"
    assert official_rows[0]["range"] == "A1:B2"
    assert official_rows[0]["normalized_expected_answer_text"] == "Alpha Value"
    assert json.loads(official_rows[0]["normalized_must_contain_terms_json"]) == ["Alpha", "Value"]
    assert official_rows[0]["llm_answer_used_for_source_validation"] == "FALSE"
    assert official_rows[0]["denominator_kind"] == "xlsx_retrieval_evidence_diagnostic"
    assert official_rows[0]["not_answer_generation_denominator"] == "TRUE"

    retrieval_rows = read_csv(tmp_path / "official_retrieval.csv")
    assert [item["query_id"] for item in retrieval_rows] == ["q_valid"]
    assert set(normalizer.RETRIEVAL_REQUIRED_COLUMNS).issubset(retrieval_rows[0])
    assert retrieval_rows[0]["expected_location_type"] == "xlsx"
    assert retrieval_rows[0]["expected_sheet_name"] == "Sheet1"
    assert retrieval_rows[0]["expected_cell_range"] == "A1:B2"
    assert retrieval_rows[0]["range_match_policy"] == "exact_match"
    assert retrieval_rows[0]["notes"].endswith("llm_answer_used_for_source_validation=false")
    assert normalizer.validate_retrieval_gold_rows(retrieval_rows, require_live_bound=False).ok


def test_llm_answer_text_cannot_make_row_official_without_bound_source_evidence(tmp_path: Path):
    review_pack = tmp_path / "llm_only.csv"
    write_csv(
        review_pack,
        [
            row(
                query_id="q_llm_only",
                evidence_summary="",
                evidence_headers="",
                evidence_row_values="",
                evidence_cell_values="",
                llm_answer="Alpha Value",
                citation_locator='{"sheet":"Sheet1","range":"A1:B2","file":"book.xlsx"}',
                sheet="Sheet1",
                cell_range="A1:B2",
            )
        ],
    )

    report = normalizer.run_normalization(
        review_pack=review_pack,
        output=tmp_path / "normalized.csv",
        official_output=tmp_path / "official.csv",
        jsonl_output=tmp_path / "normalized.jsonl",
        report_path=tmp_path / "report.json",
        artifact_root=tmp_path / "runs",
        dataset_root=tmp_path / "datasets",
        registry_path=tmp_path / "registry.json",
        expected_row_count=1,
        run_id="llm_only",
    )

    assert report["status"] == "PASS"
    assert report["official_positive_count"] == 0
    assert report["official_positive_retrieval_count"] == 0
    assert report["diagnostic_only_count"] == 1
    normalized = read_csv(tmp_path / "normalized.csv")[0]
    assert normalized["source_validation_status"] == "FAIL"
    assert normalized["source_validation_basis"] == ""
    assert normalized["llm_answer_used_for_source_validation"] == "FALSE"
    assert normalized["derived_denominator_policy"] == normalizer.DIAGNOSTIC_POLICY
    assert "must_contain_terms_not_in_bound_evidence" in normalized["derived_policy_reasons"]


def test_update_registry_preserves_existing_denominators_and_writes_projection_metadata(tmp_path: Path):
    review_pack = tmp_path / "review.csv"
    write_csv(
        review_pack,
        [
            row(
                query_id="q_valid",
                evidence_summary="Alpha row has value 123.",
                evidence_headers='["Name","Value"]',
                expected_answer_text_existing="Alpha Value",
                must_contain_terms_existing='["Alpha","Value"]',
                citation_locator='{"sheet":"Sheet1","range":"A1:B2","file":"book.xlsx"}',
                sheet="Sheet1",
                cell_range="A1:B2",
            )
        ],
    )
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": "official_denominator_registry_v1",
                "official_diagnostic_denominators": {
                    "track_a_xlsx_reviewed_positive": {
                        "path": "ai/eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv",
                        "row_count": 35,
                    }
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    report = normalizer.run_normalization(
        review_pack=review_pack,
        output=tmp_path / "normalized.csv",
        official_output=tmp_path / "official.csv",
        jsonl_output=tmp_path / "normalized.jsonl",
        report_path=tmp_path / "report.json",
        artifact_root=tmp_path / "runs",
        dataset_root=tmp_path / "datasets",
        registry_path=registry,
        expected_row_count=1,
        run_id="registry",
        update_registry=True,
    )

    assert report["status"] == "PASS"
    assert report["registry_updated"] is True
    payload = json.loads(registry.read_text(encoding="utf-8"))
    denominators = payload["official_diagnostic_denominators"]
    assert denominators["track_a_xlsx_reviewed_positive"]["row_count"] == 35
    assert denominators["track_a_xlsx_reviewed_positive"]["current_default"] is False
    assert denominators["track_a_xlsx_reviewed_positive"]["superseded_by"] == "track_a_xlsx_human_review_normalized_v0"
    assert payload["current_defaults"]["track_a_xlsx"]["denominator_key"] == "track_a_xlsx_human_review_normalized_v0"
    entry = denominators["track_a_xlsx_human_review_normalized_v0"]
    assert entry["row_count"] == 1
    assert entry["official_positive_denominator"] == 1
    assert entry["official_positive_retrieval_subset_path"].endswith("_retrieval.csv")
    assert entry["official_positive_retrieval_subset_sha256"]
    assert entry["official_xlsx_answer_generation_denominator"] == 0
    assert entry["not_answer_generation_denominator"] is True
    assert entry["current_default"] is True
    assert entry["xlsx_retrieval_wrapper_default"] is True
    assert entry["replaces_legacy_track_a_xlsx_reviewed_positive_default_for_wrapper"] is True
    assert entry["legacy_track_a_xlsx_reviewed_positive_artifact_preserved"] is True


def test_normalizer_does_not_update_registry_when_validation_fails(tmp_path: Path):
    review_pack = tmp_path / "invalid.csv"
    write_csv(
        review_pack,
        [
            row(
                query_id="q_bad",
                user_answerability_label="ANSWERABLE",
                citation_locator="{not-json",
            )
        ],
    )
    registry = tmp_path / "registry.json"
    original = {
        "schema_version": "official_denominator_registry_v1",
        "official_diagnostic_denominators": {
            "track_a_xlsx_reviewed_positive": {"row_count": 35}
        },
    }
    registry.write_text(json.dumps(original, ensure_ascii=False) + "\n", encoding="utf-8")
    output = tmp_path / "normalized.csv"
    official_output = tmp_path / "official.csv"
    jsonl_output = tmp_path / "normalized.jsonl"
    output.write_text("sentinel-normalized\n", encoding="utf-8")
    official_output.write_text("sentinel-official\n", encoding="utf-8")
    jsonl_output.write_text("sentinel-jsonl\n", encoding="utf-8")

    report = normalizer.run_normalization(
        review_pack=review_pack,
        output=output,
        official_output=official_output,
        jsonl_output=jsonl_output,
        report_path=tmp_path / "report.json",
        artifact_root=tmp_path / "runs",
        dataset_root=tmp_path / "datasets",
        registry_path=registry,
        expected_row_count=1,
        run_id="invalid_registry",
        update_registry=True,
    )

    assert report["status"] == "FAIL"
    assert report["registry_updated"] is False
    assert report["outputs_written"] is False
    assert report["write_skipped_reason"] == "validation_errors"
    assert json.loads(registry.read_text(encoding="utf-8")) == original
    assert output.read_text(encoding="utf-8") == "sentinel-normalized\n"
    assert official_output.read_text(encoding="utf-8") == "sentinel-official\n"
    assert jsonl_output.read_text(encoding="utf-8") == "sentinel-jsonl\n"


def test_special_rows_follow_requested_conservative_policy(tmp_path: Path):
    review_pack = tmp_path / "special.csv"
    rows = [
        row(
            query_id="gq_xlsx_lookup_005",
            query="경인선 월별 승차 찾아줘.",
            evidence_summary="Row has value 경인선 and header 승차총승객수.",
            evidence_headers='["노선명","승차총승객수"]',
            user_answerability_label="ANSWERABLE_CONFIRMED",
            user_relevance_label="EVIDENCE_RELEVANT",
            user_gold_answer_shape="RANGE_LOCATION_SUMMARY",
            expected_answer_text_existing="경인선 월별 승차",
            must_contain_terms_existing='["경인선","승차총승객수"]',
            deterministic_compiled_answer="",
            deterministic_compiled_status="CONTENT_MISSING_ABSTAIN",
            sheet="철도",
            cell_range="A102:D151",
            citation_locator='{"sheet":"철도","range":"A102:D151","file":"서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx"}',
            user_required_citation_policy="SHEET_RANGE_WITH_EXAMPLES",
        ),
        row(
            query_id="gq_xlsx_lookup_006",
            query="수인선 월별 승차 찾아줘.",
            evidence_summary="Row has value 수인선 and header 승차총승객수.",
            evidence_headers='["노선명","승차총승객수"]',
            user_answerability_label="ANSWERABLE_CONFIRMED",
            user_relevance_label="EVIDENCE_RELEVANT",
            user_gold_answer_shape="RANGE_LOCATION_SUMMARY",
            expected_answer_text_existing="수인선 월별 승차",
            must_contain_terms_existing='["수인선","승차총승객수"]',
            deterministic_compiled_answer="",
            deterministic_compiled_status="CONTENT_MISSING_ABSTAIN",
            sheet="철도",
            cell_range="A302:D351",
            citation_locator='{"sheet":"철도","range":"A302:D351","file":"서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx"}',
            user_required_citation_policy="SHEET_RANGE_WITH_EXAMPLES",
        ),
        row(
            query_id="gq_xlsx_date_number_format_003",
            query="163,443,126 승객수 찾아줘.",
            evidence_summary="Row has value 9호선 and 8,048,476.",
            evidence_headers='["노선명","승차총승객수"]',
            user_answerability_label="ANSWERABLE_CONFIRMED",
            user_relevance_label="EVIDENCE_RELEVANT",
            user_gold_answer_shape="FORMULA_VALUE",
            expected_answer_text_existing="버스 201711 승차총승객수",
            must_contain_terms_existing='["163","443","126"]',
            sheet="철도",
            cell_range="A452:D501",
            citation_locator='{"sheet":"철도","range":"A452:D501","file":"서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx"}',
            user_required_citation_policy="EXACT_CELL",
        ),
        row(
            query_id="gq_xlsx_aggregation_001",
            query="버스 승차 쪽 찾아줘.",
            evidence_summary="Workbook-level locator only.",
            user_answerability_label="ANSWERABLE_CONFIRMED",
            user_relevance_label="EVIDENCE_RELEVANT",
            user_gold_answer_shape="RANGE_LOCATION_SUMMARY",
            expected_answer_text_existing="aggregation needs bus table range",
            must_contain_terms_existing='["버스","승차총승객수"]',
            sheet="",
            cell_range="",
            citation_locator="{}",
            user_required_citation_policy="SHEET_RANGE_WITH_EXAMPLES",
        ),
    ]
    write_csv(review_pack, rows)

    report = normalizer.run_normalization(
        review_pack=review_pack,
        output=tmp_path / "normalized.csv",
        official_output=tmp_path / "official.csv",
        jsonl_output=tmp_path / "normalized.jsonl",
        report_path=tmp_path / "report.json",
        artifact_root=tmp_path / "runs",
        dataset_root=tmp_path / "datasets",
        registry_path=tmp_path / "registry.json",
        expected_row_count=4,
        run_id="special",
    )

    assert report["status"] == "PASS"
    assert report["official_positive_count"] == 2
    special = report["special_rows"]
    assert special["gq_xlsx_lookup_005"]["derived_denominator_policy"] == normalizer.OFFICIAL_POLICY
    assert special["gq_xlsx_lookup_005"]["normalized_expected_answer_text"] == "경인선 승차총승객수"
    assert special["gq_xlsx_lookup_006"]["derived_denominator_policy"] == normalizer.OFFICIAL_POLICY
    assert special["gq_xlsx_lookup_006"]["normalized_expected_answer_text"] == "수인선 승차총승객수"
    assert special["gq_xlsx_date_number_format_003"]["derived_denominator_policy"] == normalizer.DIAGNOSTIC_POLICY
    assert "must_contain_terms_not_in_bound_evidence" in special["gq_xlsx_date_number_format_003"]["derived_policy_reasons"]
    assert special["gq_xlsx_aggregation_001"]["derived_denominator_policy"] == normalizer.DIAGNOSTIC_POLICY
    assert "invalid_or_empty_citation_locator" in special["gq_xlsx_aggregation_001"]["derived_policy_reasons"]


def test_invalid_vocab_and_malformed_locator_fail_validation(tmp_path: Path):
    review_pack = tmp_path / "invalid.csv"
    write_csv(
        review_pack,
        [
            row(
                query_id="q_bad",
                user_answerability_label="ANSWERABLE",
                user_relevance_label="RELEVANT",
                user_gold_answer_shape="CELL_VALUE",
                user_required_citation_policy="EXACT_CELL",
                citation_locator="{not-json",
            )
        ],
    )

    report = normalizer.run_normalization(
        review_pack=review_pack,
        output=tmp_path / "normalized.csv",
        official_output=tmp_path / "official.csv",
        jsonl_output=tmp_path / "normalized.jsonl",
        report_path=tmp_path / "report.json",
        artifact_root=tmp_path / "runs",
        dataset_root=tmp_path / "datasets",
        registry_path=tmp_path / "registry.json",
        expected_row_count=1,
        run_id="invalid",
    )

    assert report["status"] == "FAIL"
    assert any("invalid user_answerability_label" in error for error in report["validation_errors"])
    assert any("invalid user_relevance_label" in error for error in report["validation_errors"])
    assert any("invalid_citation_locator_json" in error for error in report["validation_errors"])


def row(**overrides: str) -> dict[str, str]:
    base = {
        "query_id": "q",
        "query": "query",
        "track": "XLSX",
        "sheet": "Sheet1",
        "range": "A1:B2",
        "citation_locator": '{"sheet":"Sheet1","range":"A1:B2"}',
        "evidence_summary": "",
        "evidence_headers": "",
        "evidence_row_values": "",
        "evidence_cell_values": "",
        "deterministic_compiled_answer": "",
        "deterministic_compiled_status": "CONTENT_MISSING_ABSTAIN",
        "expected_answer_text_existing": "Alpha Value",
        "must_contain_terms_existing": '["Alpha","Value"]',
        "user_answerability_label": "ANSWERABLE_CONFIRMED",
        "user_relevance_label": "EVIDENCE_RELEVANT",
        "user_gold_answer_shape": "CELL_VALUE",
        "user_expected_answer_text": "",
        "user_required_citation_policy": "EXACT_CELL",
        "user_gold_policy_decision": "",
        "user_include_in_official_denominator": "",
        "llm_answer": "",
    }
    if "cell_range" in overrides:
        overrides["range"] = overrides.pop("cell_range")
    base.update(overrides)
    return base


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))
