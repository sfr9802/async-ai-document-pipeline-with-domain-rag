from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_gold_policy_user_approved_resolutions.py"


XLSX_PENDING_IDS = ["gq_xlsx_date_number_format_003", "gq_xlsx_aggregation_001"]
PDF_PENDING_IDS = [
    "pdf_file_lookup_content_anchor_017",
    "pdf_file_lookup_content_anchor_018",
    "pdf_file_lookup_content_anchor_020",
]


def load_module():
    spec = importlib.util.spec_from_file_location("rag_gold_policy_user_approved_resolutions", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_user_approved_resolutions_counts_manifest_and_guardrails(tmp_path: Path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path, module)

    resolutions = module.build_resolutions(
        draft_json=paths["draft"],
        review_sheet_md=paths["sheet"],
        official_denominator_registry=paths["registry"],
    )

    assert resolutions["schema_version"] == module.SCHEMA_VERSION
    assert resolutions["status"] == "PASS"
    assert resolutions["counts"]["xlsx"] == {
        module.XLSX_APPROVED_DECISION: 23,
        module.XLSX_PENDING_EVIDENCE_DECISION: 2,
    }
    assert resolutions["counts"]["pdf"] == {
        module.PDF_EXCLUDE_DECISION: 6,
        module.PDF_EXCLUDE_REQUIRE_STABLE_IDENTITY_DECISION: 3,
    }
    assert resolutions["text_namu_v2"]["unresolved_count"] == 23
    assert resolutions["text_namu_v2"]["include_in_gold_v0_1"] is False
    assert resolutions["draft_gold_v0_1_candidate_manifest"]["status"] == "DRAFT_ONLY_NOT_FROZEN"
    assert resolutions["draft_gold_v0_1_candidate_manifest"]["included_track_count"] == {"xlsx_human_review": 23}
    assert not set(XLSX_PENDING_IDS) & set(
        resolutions["draft_gold_v0_1_candidate_manifest"]["included_query_ids_by_track"]["xlsx_human_review"]
    )
    assert resolutions["guardrails"]["official_denominator_registry_changed"] is False
    assert resolutions["guardrails"]["retrieval_variants_run"] is False
    assert resolutions["guardrails"]["production_namespace_mutated"] is False
    assert resolutions["guardrails"]["diagnostic_only_row_promoted"] is False


def test_pdf_generic_filename_rows_are_excluded_and_diagnostic_only(tmp_path: Path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path, module)

    resolutions = module.build_resolutions(
        draft_json=paths["draft"],
        review_sheet_md=paths["sheet"],
        official_denominator_registry=paths["registry"],
    )

    generic_rows = [
        row
        for row in resolutions["pdf_file_lookup_companion"]["resolutions"]
        if row["user_gold_policy_decision"] == module.PDF_EXCLUDE_REQUIRE_STABLE_IDENTITY_DECISION
    ]
    assert sorted(row["query_id"] for row in generic_rows) == sorted(PDF_PENDING_IDS)
    for row in generic_rows:
        assert row["generic_filename_identity_accepted"] is False
        assert row["stable_document_identity_required"] is True
        assert row["gold_v0_1_status"] == "EXCLUDED_APPROVED"
        assert row["diagnostic_only_file_identity_candidate"] is True
        assert row["count_as_retrieval_failure"] is False
        assert row["content_evidence_positive"] is False


def test_main_writes_artifacts_without_registry_mutation(tmp_path: Path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path, module)
    output_json = tmp_path / "resolutions.json"
    output_md = tmp_path / "resolutions.md"
    registry_before = paths["registry"].read_text(encoding="utf-8")

    result = module.main(
        [
            "--draft-json",
            str(paths["draft"]),
            "--review-sheet-md",
            str(paths["sheet"]),
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
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps(fixture_draft(module), ensure_ascii=False) + "\n", encoding="utf-8")
    sheet = tmp_path / "sheet.md"
    sheet.write_text("# review sheet\n", encoding="utf-8")
    return {"registry": registry, "draft": draft, "sheet": sheet}


def fixture_draft(module) -> dict:
    xlsx_include_ids = [f"gq_include_{index:03d}" for index in range(23)]
    pdf_exclude_ids = [f"pdf_exclude_{index:03d}" for index in range(6)]
    text_ids = [f"text_namu_v2_{index:04d}" for index in range(1, 24)]
    return {
        "status": "PASS",
        "xlsx_draft_decisions": [
            xlsx_row(query_id, module.XLSX_PENDING_EVIDENCE_DRAFT) for query_id in XLSX_PENDING_IDS
        ]
        + [xlsx_row(query_id, module.XLSX_INCLUDE_DRAFT) for query_id in xlsx_include_ids],
        "pdf_draft_decisions": [
            pdf_row(query_id, module.PDF_PENDING_FILE_IDENTITY_DRAFT) for query_id in PDF_PENDING_IDS
        ]
        + [pdf_row(query_id, module.PDF_EXCLUDE_DRAFT) for query_id in pdf_exclude_ids],
        "text_unresolved_carry_forward_summary": {
            "unresolved_user_review_count": 23,
            "unresolved_user_review_rows": text_ids,
            "summary_buckets": {},
        },
    }


def xlsx_row(query_id: str, decision: str) -> dict:
    return {
        "query_id": query_id,
        "question_input": f"question {query_id}",
        "proposed_user_decision": decision,
        "candidate_expected_answer": {"text": "" if query_id == "gq_xlsx_aggregation_001" else f"answer {query_id}"},
        "candidate_expected_evidence": {"summary": ""},
        "source_citation_target": {"sheet": "Sheet1", "range": "A1:B2"},
    }


def pdf_row(query_id: str, decision: str) -> dict:
    return {
        "query_id": query_id,
        "proposed_user_decision": decision,
        "current_issue_tags": ["GENERIC_FILENAME"] if decision == "KEEP_PENDING_FILE_IDENTITY_REVIEW" else [],
        "current_conflict_tags": ["GENERIC_FILENAME"] if decision == "KEEP_PENDING_FILE_IDENTITY_REVIEW" else [],
        "stable_document_identity": {"available": False, "basis": "none", "value": ""},
    }
