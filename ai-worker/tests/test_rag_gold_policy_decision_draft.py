from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_gold_policy_decision_draft.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_gold_policy_decision_draft", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_decision_draft_schema_counts_and_guardrails(tmp_path: Path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path, module)

    draft = module.build_draft(
        packet_json=paths["packet_json"],
        packet_md=paths["packet_md"],
        normalization_report=paths["normalization_report"],
        official_denominator_registry=paths["registry"],
    )

    assert draft["schema_version"] == module.SCHEMA_VERSION
    assert draft["status"] == "PASS"
    assert draft["rows_processed_by_track"] == {
        "pdf_file_lookup_companion": 9,
        "text_namu_v2": 0,
        "xlsx_human_review": 25,
    }
    assert draft["text_unresolved_carry_forward_summary"]["unresolved_user_review_count"] == 23
    assert draft["text_unresolved_carry_forward_summary"]["resolution_attempted"] is False
    assert draft["counts_by_proposed_user_decision"]["xlsx_human_review"] == {
        module.XLSX_INCLUDE_DECISION: 23,
        module.XLSX_PENDING_EVIDENCE_DECISION: 2,
    }
    assert draft["counts_by_proposed_user_decision"]["pdf_file_lookup_companion"] == {
        module.PDF_EXCLUDE_DECISION: 6,
        module.PDF_PENDING_FILE_IDENTITY_DECISION: 3,
    }
    assert draft["guardrail_status"]["official_denominator_registry_changed"] is False
    assert draft["guardrail_status"]["retrieval_variants_run"] is False
    assert draft["guardrail_status"]["production_namespace_mutated"] is False
    assert draft["guardrail_status"]["diagnostic_only_row_promoted"] is False
    assert draft["guardrail_status"]["pdf_content_and_file_identity_aggregated"] is False
    assert draft["validation"]["pdf_content_file_identity_aggregation_count"] is None


def test_expected_rows_stay_unresolved_or_excluded_without_content_conversion(tmp_path: Path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path, module)

    draft = module.build_draft(
        packet_json=paths["packet_json"],
        packet_md=paths["packet_md"],
        normalization_report=paths["normalization_report"],
        official_denominator_registry=paths["registry"],
    )

    pending_xlsx = [
        row["query_id"]
        for row in draft["xlsx_draft_decisions"]
        if row["proposed_user_decision"] == module.XLSX_PENDING_EVIDENCE_DECISION
    ]
    assert sorted(pending_xlsx) == sorted(module.EXPECTED_XLSX_PENDING_EVIDENCE_IDS)
    for row in draft["xlsx_draft_decisions"]:
        assert row["registry_mutation"] is False
        assert row["official_denominator_frozen"] is False

    excluded_pdf = [
        row
        for row in draft["pdf_draft_decisions"]
        if row["proposed_user_decision"] == module.PDF_EXCLUDE_DECISION
    ]
    assert sorted(row["query_id"] for row in excluded_pdf) == sorted(module.EXPECTED_PDF_EXCLUDE_IDS)
    for row in excluded_pdf:
        assert {"NOT_ANSWERABLE", "IRRELEVANT"} & set(row["current_conflict_tags"])
        assert row["converted_to_content_evidence_positive"] is False
        assert row["content_evidence_lane_counted"] is False

    pending_pdf = [
        row
        for row in draft["pdf_draft_decisions"]
        if row["proposed_user_decision"] == module.PDF_PENDING_FILE_IDENTITY_DECISION
    ]
    assert sorted(row["query_id"] for row in pending_pdf) == sorted(module.EXPECTED_PDF_PENDING_IDS)
    for row in pending_pdf:
        assert row["final_denominator_status"] == "UNRESOLVED"
        assert row["stable_document_identity"]["available"] is False
        assert row["official_denominator_frozen"] is False


def test_main_writes_outputs_without_registry_mutation(tmp_path: Path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path, module)
    output_json = tmp_path / "draft.json"
    output_md = tmp_path / "draft.md"
    registry_before = paths["registry"].read_text(encoding="utf-8")

    result = module.main(
        [
            "--packet-json",
            str(paths["packet_json"]),
            "--packet-md",
            str(paths["packet_md"]),
            "--normalization-report",
            str(paths["normalization_report"]),
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
    assert paths["registry"].read_text(encoding="utf-8") == registry_before


def write_fixture_inputs(tmp_path: Path, module) -> dict[str, Path]:
    registry = tmp_path / "official_denominator_registry.json"
    registry.write_text(json.dumps({"schema_version": "official_denominator_registry_v1"}) + "\n", encoding="utf-8")

    text_ids = [f"text_namu_v2_{index:04d}" for index in range(1, 24)]
    xlsx_ids = [
        "gq_xlsx_lookup_001",
        "gq_xlsx_lookup_004",
        "gq_xlsx_lookup_005",
        "gq_xlsx_lookup_006",
        "gq_xlsx_lookup_007",
        "gq_xlsx_lookup_008",
        "gq_xlsx_date_number_format_001",
        "gq_xlsx_date_number_format_003",
        "gq_xlsx_aggregation_001",
        "gq_xlsx_aggregation_002",
        "gq_auto_012",
        "gq_auto_017",
        "gq_auto_018",
        "gq_auto_022",
        "gq_auto_023",
        "gq_auto_028",
        "gq_auto_031",
        "gq_auto_034",
        "gq_auto_035",
        "gq_auto_036",
        "gq_auto_037",
        "gq_auto_038",
        "gq_auto_040",
        "gq_auto_043",
        "gq_auto_044",
    ]
    pdf_ids = module.EXPECTED_PDF_EXCLUDE_IDS + module.EXPECTED_PDF_PENDING_IDS

    packet_json = tmp_path / "packet.json"
    packet_json.write_text(
        json.dumps(
            {
                "schema_version": "rag_gold_policy_resolution_packet_v1",
                "status": "PASS",
                "guardrail_status": {
                    "retrieval_variants_run": False,
                    "production_namespace_mutated": False,
                    "official_denominator_opened": False,
                    "official_denominator_registry_changed": False,
                    "diagnostic_only_row_promoted": False,
                    "pdf_content_and_file_identity_aggregated": False,
                    "not_answerable_or_irrelevant_emitted_as_content_positive": False,
                },
                "rows_processed_by_track": {
                    "xlsx_human_review": 25,
                    "pdf_file_lookup_companion": 9,
                    "text_namu_v2": 0,
                },
                "xlsx_decision_packets": [xlsx_packet(module, query_id) for query_id in xlsx_ids],
                "pdf_decision_packets": [
                    pdf_packet(module, query_id, exclude=query_id in module.EXPECTED_PDF_EXCLUDE_IDS)
                    for query_id in pdf_ids
                ],
                "unchanged_text_unresolved_summary": {
                    "track": "text_namuwiki_animation",
                    "resolution_attempted": False,
                    "unresolved_user_review_count": 23,
                    "unresolved_user_review_rows": text_ids,
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    packet_md = tmp_path / "packet.md"
    packet_md.write_text("# packet\n", encoding="utf-8")

    normalization_report = tmp_path / "normalization.json"
    normalization_report.write_text(
        json.dumps(
            {
                "status": "PASS",
                "tracks": {
                    "text_namu_v2": {
                        "review_marker_buckets": {
                            "expected_answer_revision": text_ids[:2],
                            "expected_answer_and_evidence_revision": text_ids[2:3],
                            "needs_second_review": text_ids[3:6],
                            "ambiguous_query": text_ids[6:9],
                            "invalid_query": text_ids[9:12],
                            "evidence_too_broad": text_ids[12:13],
                            "source_binding_review_required": text_ids[13:20],
                        }
                    }
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "registry": registry,
        "packet_json": packet_json,
        "packet_md": packet_md,
        "normalization_report": normalization_report,
    }


def xlsx_packet(module, query_id: str) -> dict:
    recommendation = (
        module.XLSX_PENDING_EVIDENCE_RECOMMENDATION
        if query_id in module.EXPECTED_XLSX_PENDING_EVIDENCE_IDS
        else module.XLSX_CONFIRM_RECOMMENDATION
    )
    return {
        "query_id": query_id,
        "question_input": f"question {query_id}",
        "codex_recommendation": recommendation,
        "current_normalized_bucket": "PROPOSED_OFFICIAL_CANDIDATE",
        "user_answerability_label": "ANSWERABLE_CONFIRMED",
        "user_relevance_label": "EVIDENCE_RELEVANT",
        "user_gold_answer_shape": "ROW_SUMMARY",
        "user_required_citation_policy": "EXACT_ROW",
        "candidate_expected_answer": {"text": f"answer {query_id}", "source_field": "expected_answer_text_existing"},
        "candidate_expected_evidence": {"summary": f"evidence {query_id}", "source_field": "evidence_summary"},
        "source_citation_target": {"sheet": "Sheet1", "range": "A1:B2"},
        "official_denominator_frozen": False,
    }


def pdf_packet(module, query_id: str, *, exclude: bool) -> dict:
    conflict_tags = ["REVISE_EXPECTED_EVIDENCE", "NOT_ANSWERABLE", "IRRELEVANT"] if exclude else [
        "REVISE_EXPECTED_EVIDENCE",
        "ANSWERABLE_AS_FILE_LOOKUP",
        "PARTIAL",
        "GENERIC_FILENAME",
    ]
    return {
        "query_id": query_id,
        "proposed_expected_evidence_policy": (
            module.PDF_EXCLUDE_RECOMMENDATION if exclude else module.PDF_PENDING_RECOMMENDATION
        ),
        "current_issue_tags": conflict_tags,
        "current_conflict_tags": conflict_tags,
        "current_normalized_bucket": "EXPECTED_EVIDENCE_REVISION",
        "appears_to_be": "policy_excluded_not_answerable" if exclude else "file_document_identity_lookup_candidate",
        "generic_filename_identity_risk": not exclude,
        "stable_document_identity": {"available": False, "basis": "none", "value": ""},
        "proposed_expected_evidence_text_or_summary": {"text": "", "source_field": "USER_REQUIRED"},
        "official_denominator_frozen": False,
    }
