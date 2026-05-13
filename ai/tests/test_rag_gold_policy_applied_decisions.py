from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_gold_policy_applied_decisions.py"


XLSX_PENDING_IDS = ["gq_xlsx_date_number_format_003", "gq_xlsx_aggregation_001"]
XLSX_DRAFT_CANDIDATE_IDS = [
    "gq_xlsx_lookup_001",
    "gq_xlsx_lookup_004",
    "gq_xlsx_lookup_005",
    "gq_xlsx_lookup_006",
    "gq_xlsx_lookup_007",
    "gq_xlsx_lookup_008",
    "gq_xlsx_date_number_format_001",
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
PDF_EXCLUDED_IDS = [
    "pdf_file_lookup_content_anchor_004",
    "pdf_file_lookup_content_anchor_012",
    "pdf_file_lookup_content_anchor_013",
    "pdf_file_lookup_content_anchor_014",
    "pdf_file_lookup_content_anchor_015",
    "pdf_file_lookup_metadata_002",
]
PDF_STABLE_REQUIRED_IDS = [
    "pdf_file_lookup_content_anchor_017",
    "pdf_file_lookup_content_anchor_018",
    "pdf_file_lookup_content_anchor_020",
]
TEXT_UNRESOLVED_IDS = [
    "text_namu_v2_0006",
    "text_namu_v2_0010",
    "text_namu_v2_0013",
    "text_namu_v2_0019",
    "text_namu_v2_0020",
    "text_namu_v2_0023",
    "text_namu_v2_0024",
    "text_namu_v2_0027",
    "text_namu_v2_0029",
    "text_namu_v2_0031",
    "text_namu_v2_0033",
    "text_namu_v2_0043",
    "text_namu_v2_0044",
    "text_namu_v2_0066",
    "text_namu_v2_0067",
    "text_namu_v2_0078",
    "text_namu_v2_0080",
    "text_namu_v2_0082",
    "text_namu_v2_0091",
    "text_namu_v2_0092",
    "text_namu_v2_0093",
    "text_namu_v2_0094",
    "text_namu_v2_0095",
]


def load_module():
    spec = importlib.util.spec_from_file_location("rag_gold_policy_applied_decisions", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_applied_decisions_counts_manifest_and_guardrails(tmp_path: Path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path, module)
    registry_sha = module.sha256_file(paths["registry"])

    applied = module.build_applied_decisions(
        approved_resolutions=json.loads(paths["approved"].read_text(encoding="utf-8")),
        approved_resolutions_path=paths["approved"],
        review_sheet_path=paths["sheet"],
        official_denominator_registry=paths["registry"],
        registry_sha_before=registry_sha,
        registry_sha_after=registry_sha,
    )

    assert applied["schema_version"] == module.SCHEMA_VERSION
    assert applied["status"] == "PASS"
    assert applied["counts"] == {
        "pdf_excluded_applied": 6,
        "pdf_stable_identity_required_excluded_applied": 3,
        "text_unresolved_carried_forward": 23,
        "xlsx_draft_candidates_applied": 23,
        "xlsx_pending_evidence_applied": 2,
    }
    assert applied["guardrails"]["official_denominator_registry_changed"] is False
    assert applied["guardrails"]["retrieval_variants_run"] is False
    assert applied["guardrails"]["production_namespace_mutated"] is False
    assert applied["guardrails"]["pdf_content_and_file_identity_aggregated"] is False
    assert not set(XLSX_PENDING_IDS) & set(
        applied["draft_gold_v0_1_candidate_manifest"]["included_query_ids_by_track"]["xlsx_human_review"]
    )
    assert applied["draft_gold_v0_1_candidate_manifest"]["included_query_ids_by_track"]["xlsx_human_review"] == XLSX_DRAFT_CANDIDATE_IDS
    assert applied["applied_decisions"]["xlsx_pending_evidence"]["query_ids"] == XLSX_PENDING_IDS
    assert applied["applied_decisions"]["pdf_excluded_from_gold_v0_1"]["query_ids"] == PDF_EXCLUDED_IDS
    assert applied["applied_decisions"]["pdf_stable_identity_required_excluded"]["query_ids"] == PDF_STABLE_REQUIRED_IDS
    assert applied["applied_decisions"]["pdf_excluded_from_gold_v0_1"]["count_as_retrieval_failure"] is False
    assert applied["applied_decisions"]["text_namu_v2_unresolved_carry_forward"]["query_ids"] == TEXT_UNRESOLVED_IDS
    assert applied["applied_decisions"]["text_namu_v2_unresolved_carry_forward"]["resolution_attempted"] is False
    assert applied["applied_decisions"]["text_namu_v2_unresolved_carry_forward"]["include_in_gold_v0_1"] is False


def test_applied_review_sheet_marks_decisions_applied(tmp_path: Path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path, module)
    registry_sha = module.sha256_file(paths["registry"])
    applied = module.build_applied_decisions(
        approved_resolutions=json.loads(paths["approved"].read_text(encoding="utf-8")),
        approved_resolutions_path=paths["approved"],
        review_sheet_path=paths["sheet"],
        official_denominator_registry=paths["registry"],
        registry_sha_before=registry_sha,
        registry_sha_after=registry_sha,
    )

    sheet = module.render_applied_review_sheet(applied)

    assert "Status: `APPLIED`" in sheet
    assert "[x] XLSX include-candidate batch approved" in sheet
    assert "gq_xlsx_aggregation_001`: `KEEP_PENDING_EVIDENCE`" in sheet
    assert "generic filename identity rejected" in sheet
    assert "Resolution attempted: `false`" in sheet


def test_main_writes_applied_artifacts_and_updates_sheet_without_registry_mutation(tmp_path: Path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path, module)
    output_json = tmp_path / "applied.json"
    output_md = tmp_path / "applied.md"
    registry_before = paths["registry"].read_text(encoding="utf-8")

    result = module.main(
        [
            "--approved-resolutions-json",
            str(paths["approved"]),
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
    assert "Status: `APPLIED`" in paths["sheet"].read_text(encoding="utf-8")
    assert paths["registry"].read_text(encoding="utf-8") == registry_before


def write_fixture_inputs(tmp_path: Path, module) -> dict[str, Path]:
    registry = tmp_path / "official_denominator_registry.json"
    registry.write_text(json.dumps({"schema_version": "official_denominator_registry_v1"}) + "\n", encoding="utf-8")
    approved = tmp_path / "approved.json"
    approved.write_text(json.dumps(fixture_approved(module), ensure_ascii=False) + "\n", encoding="utf-8")
    sheet = tmp_path / "sheet.md"
    sheet.write_text("# Gold Policy User Review Sheet v1\n", encoding="utf-8")
    return {"registry": registry, "approved": approved, "sheet": sheet}


def fixture_approved(module) -> dict:
    return {
        "status": "PASS",
        "draft_gold_v0_1_candidate_manifest": {
            "included_query_ids_by_track": {"xlsx_human_review": XLSX_DRAFT_CANDIDATE_IDS},
            "excluded_pending_query_ids_by_track": {
                "xlsx_human_review": XLSX_PENDING_IDS,
                "pdf_file_lookup_companion": PDF_EXCLUDED_IDS + PDF_STABLE_REQUIRED_IDS,
                "text_namu_v2": TEXT_UNRESOLVED_IDS,
            },
        },
        "xlsx_human_review": {
            "approved_draft_candidate_query_ids": XLSX_DRAFT_CANDIDATE_IDS,
            "pending_evidence_query_ids": XLSX_PENDING_IDS,
        },
        "pdf_file_lookup_companion": {
            "approved_exclude_query_ids": PDF_EXCLUDED_IDS,
            "stable_identity_required_exclude_query_ids": PDF_STABLE_REQUIRED_IDS,
        },
        "text_namu_v2": {
            "unresolved_count": 23,
            "unresolved_query_ids": TEXT_UNRESOLVED_IDS,
        },
    }
