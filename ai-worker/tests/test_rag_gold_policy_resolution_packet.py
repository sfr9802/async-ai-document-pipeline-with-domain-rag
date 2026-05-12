from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_gold_policy_resolution_packet.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_gold_policy_resolution_packet", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_resolution_packet_scope_guardrails_and_decision_counts(tmp_path: Path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path, module)

    packet = module.build_packet(
        normalization_report_path=paths["normalization_report"],
        xlsx_review_csv=paths["xlsx_csv"],
        pdf_review_csv=paths["pdf_csv"],
        xlsx_strict_report=paths["xlsx_strict_report"],
        official_denominator_registry=paths["registry"],
    )

    assert packet["schema_version"] == module.SCHEMA_VERSION
    assert packet["status"] == "PASS"
    assert packet["rows_processed_by_track"] == {
        "pdf_file_lookup_companion": 9,
        "text_namu_v2": 0,
        "xlsx_human_review": 25,
    }
    assert [row["query_id"] for row in packet["xlsx_decision_packets"]] == module.XLSX_TARGET_IDS
    assert [row["query_id"] for row in packet["pdf_decision_packets"]] == module.PDF_TARGET_IDS
    assert packet["unchanged_text_unresolved_summary"]["unresolved_user_review_count"] == 23
    assert packet["unchanged_text_unresolved_summary"]["resolution_attempted"] is False

    assert packet["counts_by_proposed_decision"]["xlsx_human_review"] == {
        module.XLSX_CONFIRM: 23,
        module.XLSX_PENDING_EVIDENCE: 2,
    }
    assert packet["counts_by_proposed_decision"]["pdf_file_lookup_companion"] == {
        module.PDF_EXCLUDE: 6,
        module.PDF_PENDING: 3,
    }
    assert packet["guardrail_status"]["official_denominator_registry_changed"] is False
    assert packet["guardrail_status"]["retrieval_variants_run"] is False
    assert packet["guardrail_status"]["production_namespace_mutated"] is False
    assert packet["guardrail_status"]["diagnostic_only_row_promoted"] is False
    assert packet["guardrail_status"]["pdf_content_and_file_identity_aggregated"] is False
    assert packet["validation"]["pdf_lane_counts"]["aggregate_official_denominator_count"] is None
    assert packet["validation"]["text_unresolved_carried_forward_only"] is True


def test_not_answerable_or_irrelevant_pdf_rows_are_not_content_positive(tmp_path: Path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path, module)
    packet = module.build_packet(
        normalization_report_path=paths["normalization_report"],
        xlsx_review_csv=paths["xlsx_csv"],
        pdf_review_csv=paths["pdf_csv"],
        xlsx_strict_report=paths["xlsx_strict_report"],
        official_denominator_registry=paths["registry"],
    )

    conflicted = [
        row
        for row in packet["pdf_decision_packets"]
        if {"NOT_ANSWERABLE", "IRRELEVANT"} & set(row["current_conflict_tags"])
    ]
    assert conflicted
    assert {row["proposed_expected_evidence_policy"] for row in conflicted} == {module.PDF_EXCLUDE}
    assert packet["guardrail_status"]["not_answerable_or_irrelevant_emitted_as_content_positive"] is False


def test_main_writes_packet_outputs_without_registry_mutation(tmp_path: Path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path, module)
    output_json = tmp_path / "packet.json"
    output_md = tmp_path / "packet.md"
    before = paths["registry"].read_text(encoding="utf-8")

    result = module.main(
        [
            "--normalization-report",
            str(paths["normalization_report"]),
            "--xlsx-review-csv",
            str(paths["xlsx_csv"]),
            "--pdf-review-csv",
            str(paths["pdf_csv"]),
            "--xlsx-strict-report",
            str(paths["xlsx_strict_report"]),
            "--official-denominator-registry",
            str(paths["registry"]),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
    )

    assert result == 0
    assert output_json.exists()
    assert output_md.exists()
    assert paths["registry"].read_text(encoding="utf-8") == before


def write_fixture_inputs(tmp_path: Path, module) -> dict[str, Path]:
    registry = tmp_path / "official_denominator_registry.json"
    registry.write_text(json.dumps({"schema_version": "official_denominator_registry_v1"}) + "\n", encoding="utf-8")

    normalization_report = tmp_path / "normalization.json"
    normalization_report.write_text(
        json.dumps(
            {
                "status": "PASS",
                "cross_track_validation_errors": [],
                "tracks": {
                    "text_namu_v2": {
                        "unresolved_user_review_count": 23,
                        "unresolved_user_review_rows": ["text_unresolved_001"],
                    },
                    "xlsx_human_review": {
                        "denominator_confirmation_required_query_ids": module.XLSX_TARGET_IDS,
                        "rows": [
                            {
                                "query_id": query_id,
                                "normalized_policy_bucket": "PROPOSED_OFFICIAL_CANDIDATE",
                                "issue_tags": ["ANSWERABLE_CONFIRMED", "EVIDENCE_RELEVANT"],
                            }
                            for query_id in module.XLSX_TARGET_IDS
                        ],
                    },
                    "pdf_file_lookup_companion": {
                        "expected_answer_or_evidence_revision_query_ids": module.PDF_TARGET_IDS,
                        "rows": [
                            {
                                "query_id": query_id,
                                "normalized_policy_bucket": "EXPECTED_EVIDENCE_REVISION",
                                "issue_tags": ["REVISE_EXPECTED_EVIDENCE"],
                            }
                            for query_id in module.PDF_TARGET_IDS
                        ],
                    },
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    xlsx_csv = tmp_path / "xlsx.csv"
    write_csv(
        xlsx_csv,
        [
            {
                "query_id": query_id,
                "query": f"question {query_id}",
                "user_answerability_label": "ANSWERABLE_CONFIRMED",
                "user_relevance_label": "EVIDENCE_RELEVANT",
                "user_gold_answer_shape": "ROW_SUMMARY",
                "user_required_citation_policy": "EXACT_ROW",
                "expected_answer_text_existing": f"answer {query_id}",
                "deterministic_compiled_answer": f"compiled {query_id}",
                "deterministic_compiled_status": "COMPILED",
                "user_expected_evidence_text_or_summary": "",
                "evidence_summary": f"evidence {query_id}",
                "evidence_headers": "[\"h1\"]",
                "citation_locator": json.dumps({"sheet": "Sheet1", "range": "A1:B2", "file": "book.xlsx"}),
                "sheet": "Sheet1",
                "range": "A1:B2",
            }
            for query_id in module.XLSX_TARGET_IDS
        ],
    )

    xlsx_strict_report = tmp_path / "xlsx_strict.json"
    xlsx_strict_report.write_text(
        json.dumps(
            {
                "rows_excluded_despite_human_relevant_labels": [
                    {"query_id": "gq_xlsx_date_number_format_003", "derived_denominator_policy": "DIAGNOSTIC_ONLY"},
                    {"query_id": "gq_xlsx_aggregation_001", "derived_denominator_policy": "DIAGNOSTIC_ONLY"},
                ]
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    pdf_csv = tmp_path / "pdf.csv"
    excluded_ids = set(module.PDF_TARGET_IDS[:6])
    write_csv(
        pdf_csv,
        [
            pdf_row(query_id=query_id, excluded=query_id in excluded_ids)
            for query_id in module.PDF_TARGET_IDS
        ],
    )

    return {
        "registry": registry,
        "normalization_report": normalization_report,
        "xlsx_csv": xlsx_csv,
        "xlsx_strict_report": xlsx_strict_report,
        "pdf_csv": pdf_csv,
    }


def pdf_row(*, query_id: str, excluded: bool) -> dict[str, str]:
    if excluded:
        answerability = "NOT_ANSWERABLE"
        relevance = "IRRELEVANT"
        denominator_policy = "INCLUDE_POSITIVE_DENOMINATOR_AFTER_USER_REVIEW"
    else:
        answerability = "ANSWERABLE_AS_FILE_LOOKUP"
        relevance = "PARTIAL"
        denominator_policy = "INCLUDE_FILE_LOOKUP_DENOMINATOR_CANDIDATE"
    return {
        "query_id": query_id,
        "user_gold_decision": "REVISE_EXPECTED_EVIDENCE",
        "user_answerability_label": answerability,
        "user_relevance_label": relevance,
        "user_expected_evidence_policy": "EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY",
        "user_denominator_policy": denominator_policy,
        "risk_tags": "PDF_FILE_LOOKUP;GENERIC_FILENAME",
        "expected_evidence_excerpt": f"evidence {query_id}",
        "evidence_object_summary": "",
        "deterministic_draft": "",
        "source_file_name": "file (1).pdf",
        "expected_file_name": "file (1).pdf",
        "expected_document_version_id": "",
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    columns = sorted({column for row in rows for column in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
