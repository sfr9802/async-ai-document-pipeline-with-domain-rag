from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_xlsx_strict_silver_generation.py"
REGISTRY_PATH = ROOT / "ai-worker" / "eval" / "eval_queries" / "official_denominator_registry.json"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_xlsx_strict_silver_generation_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_strict_silver_report_uses_approved_wrapper_and_23_rows():
    module = load_module()
    before = REGISTRY_PATH.read_bytes()

    report, silver_rows = module.build_generation()

    assert report["status"] == "COMPLETED_DIAGNOSTIC_ONLY"
    assert report["approved_strict_wrapper"]["approval_status"] == "APPROVED_FOR_XLSX_SILVER_GENERATION_STRICT"
    assert report["approved_strict_wrapper"]["strict_guard_function"] == "assert_silver_generation_allowed"
    assert report["approved_strict_wrapper"]["retrieval_wrapper_script"] == (
        "ai-worker/scripts/rag_xlsx_retrieval_performance_diagnostic.py"
    )
    assert report["approved_strict_wrapper"]["legacy_track_a_diagnostic_default_used"] is False
    assert report["counts"]["input_denominator_row_count"] == 23
    assert report["counts"]["generated_silver_row_count"] == 23
    assert report["counts"]["pending_evidence_row_count"] == 2
    assert sorted(report["excluded_query_ids"]["pending_evidence"]) == [
        "gq_xlsx_aggregation_001",
        "gq_xlsx_date_number_format_003",
    ]
    pending_ids = set(report["excluded_query_ids"]["pending_evidence"])
    official_ids = {row["query_id"] for row in module.read_csv_rows(module.DEFAULT_OFFICIAL_POSITIVE_CSV)}
    retrieval_ids = {row["query_id"] for row in module.read_csv_rows(module.DEFAULT_OFFICIAL_RETRIEVAL_CSV)}
    assert set(report["included_query_ids"]).isdisjoint(pending_ids)
    assert official_ids.isdisjoint(pending_ids)
    assert retrieval_ids.isdisjoint(pending_ids)
    assert len(silver_rows) == 23
    assert {row["query_id"] for row in silver_rows} == set(report["included_query_ids"])
    assert all(
        row["strict_wrapper_path"] == "ai-worker/scripts/rag_xlsx_retrieval_performance_diagnostic.py"
        for row in silver_rows
    )
    assert all(row["answer_generation_denominator_included"] is False for row in silver_rows)
    assert all(row["official_metric_input"] is False for row in silver_rows)
    assert all(row["promotion_evidence"] is False for row in silver_rows)
    assert REGISTRY_PATH.read_bytes() == before


def test_hidden_excluded_answer_surfaces_and_guardrails_remain_closed():
    module = load_module()

    report = module.build_report()

    assert report["hidden_excluded_leakage_result"]["status"] == "PASS"
    assert report["hidden_excluded_leakage_result"]["surface_leakage_count"] == 0
    assert report["surface_status"]["answer"] == "NOT_OPENED"
    assert report["surface_status"]["citation"] == "NOT_OPENED"
    assert report["guardrails"]["official_denominator_registry_changed"] is False
    assert report["guardrails"]["official_denominator_opened_or_frozen"] is False
    assert report["guardrails"]["xlsx_answer_generation_denominator_opened"] is False
    assert report["guardrails"]["production_namespace_mutated"] is False
    assert report["guardrails"]["production_vector_index_mutated"] is False
    assert report["guardrails"]["production_vector_written"] is False
    assert report["guardrails"]["repo_local_silver_manifest_written"] is False
    assert report["guardrails"]["candidate_artifact_mutated"] is False
    assert report["guardrails"]["immutable_baseline_mutated"] is False
    assert report["guardrails"]["diagnostic_only_row_promoted"] is False
    assert report["guardrails"]["hidden_xlsx_exposed"] is False
    assert report["guardrails"]["policy_excluded_rows_counted_as_retrieval_failures"] is False
    assert report["guardrails"]["route_fallback_labels_promoted_to_official_metrics"] is False
    assert report["guardrails"]["pdf_content_file_lanes_aggregated"] is False


def test_repo_local_silver_manifest_path_is_rejected():
    module = load_module()
    forbidden_path = (
        ROOT
        / "ai-worker"
        / "eval"
        / "indexes"
        / "rag-data-xlsx-candidate-v1"
        / "xlsx_strict_silver_retrieval_evidence_manifest.jsonl"
    )

    with pytest.raises(ValueError, match="outside the repository"):
        module.build_generation(silver_output=forbidden_path)

    report = module.build_report()
    assert report["silver_artifact_policy"]["full_manifest_location_guard"] == "assert_external_silver_output_path"
    assert report["silver_artifact_policy"]["repo_local_full_manifest_allowed"] is False


def test_cli_does_not_write_silver_manifest_when_guardrail_failed(tmp_path: Path):
    module = load_module()
    leakage_payload = json.loads(module.DEFAULT_LEAKAGE_REPORT.read_text(encoding="utf-8"))
    leakage_payload["surface_coverage"]["answer"]["status"] = "PASS"
    leakage_path = tmp_path / "leakage_fail.json"
    leakage_path.write_text(json.dumps(leakage_payload, ensure_ascii=False), encoding="utf-8")
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"
    silver_path = tmp_path / "manifest.jsonl"

    code = module.main(
        [
            "--leakage-report",
            str(leakage_path),
            "--json-output",
            str(json_path),
            "--md-output",
            str(md_path),
            "--silver-output",
            str(silver_path),
        ]
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert code == 2
    assert payload["status"] == "FAILED_GUARDRAIL"
    assert payload["guardrails"]["answer_citation_surfaces_opened"] is True
    assert payload["silver_artifact_policy"]["external_silver_artifact_written"] is False
    assert not silver_path.exists()


def test_build_generation_rejects_noncanonical_official_or_retrieval_inputs(tmp_path: Path):
    module = load_module()
    official_clone = tmp_path / "official_positive.csv"
    official_clone.write_bytes(module.DEFAULT_OFFICIAL_POSITIVE_CSV.read_bytes())
    retrieval_clone = tmp_path / "official_retrieval.csv"
    retrieval_clone.write_bytes(module.DEFAULT_OFFICIAL_RETRIEVAL_CSV.read_bytes())

    with pytest.raises(ValueError, match="canonical XLSX strict input"):
        module.build_generation(official_positive_csv=official_clone)
    with pytest.raises(ValueError, match="canonical XLSX strict input"):
        module.build_generation(official_retrieval_csv=retrieval_clone)


def test_strict_generation_fails_on_production_mutation_guardrail(tmp_path: Path):
    module = load_module()
    three_track_payload = json.loads(module.DEFAULT_THREE_TRACK_REPORT.read_text(encoding="utf-8"))
    three_track_payload["production_vector_written"] = True
    three_track_path = tmp_path / "three_track_guardrail_fail.json"
    three_track_path.write_text(json.dumps(three_track_payload, ensure_ascii=False), encoding="utf-8")

    report = module.build_report(three_track_report=three_track_path)

    assert report["status"] == "FAILED_GUARDRAIL"
    assert report["guardrails"]["production_vector_written"] is True
    assert "guardrail violation: production_vector_written=true" in report["validation"]["errors"]


@pytest.mark.parametrize(
    ("key_path", "value", "expected_guardrail"),
    [
        (
            ("route_fallback_label_review_pack_generation", "candidate_artifact_mutated"),
            True,
            "candidate_artifact_mutated",
        ),
        (
            ("route_fallback_label_review_applied", "immutable_baseline_mutated"),
            True,
            "immutable_baseline_mutated",
        ),
        (
            ("route_fallback_label_review_applied", "fallback_metrics_official"),
            True,
            "route_fallback_labels_promoted_to_official_metrics",
        ),
        (
            ("route_fallback_label_review_pack_generation", "counts", "official_metric_input_rows"),
            1,
            "route_fallback_labels_promoted_to_official_metrics",
        ),
        (
            ("route_fallback_label_review_applied", "pdf_content_and_file_identity_aggregated"),
            True,
            "pdf_content_file_lanes_aggregated",
        ),
    ],
)
def test_strict_generation_fails_on_nested_three_track_guardrails(
    tmp_path: Path,
    key_path: tuple[str, ...],
    value: object,
    expected_guardrail: str,
):
    module = load_module()
    three_track_payload = json.loads(module.DEFAULT_THREE_TRACK_REPORT.read_text(encoding="utf-8"))
    target = three_track_payload
    for key in key_path[:-1]:
        target = target[key]
    target[key_path[-1]] = value
    three_track_path = tmp_path / "three_track_nested_guardrail_fail.json"
    three_track_path.write_text(json.dumps(three_track_payload, ensure_ascii=False), encoding="utf-8")

    report = module.build_report(three_track_report=three_track_path)

    assert report["status"] == "FAILED_GUARDRAIL"
    assert report["guardrails"][expected_guardrail] is True
    assert f"guardrail violation: {expected_guardrail}=true" in report["validation"]["errors"]


def test_structure_missing_rows_are_diagnostic_only_not_strict_silver():
    module = load_module()

    row = module.silver_row_from_sources(
        query_id="missing-structure",
        official_row={"citation_locator": "{}"},
        diagnostic_row={},
    )

    assert row["diagnostic_only"] is True
    assert row["diagnostic_only_reason"] == "flattened_only"
    assert set(row["missing_context_fields"]) >= {
        "file",
        "sheet",
        "table_range",
        "matched_cells",
        "header_rows",
        "target_rows",
        "target_columns",
        "row_values",
        "column_headers",
        "nearby_rows",
        "score",
    }


def test_citation_metadata_and_diagnostic_fallback_classification():
    module = load_module()

    report = module.build_report()

    required_fields = set(module.REQUIRED_XLSX_CITATION_METADATA_FIELDS)
    assert set(report["citation_metadata_completeness"]["required_fields"]) == required_fields
    assert report["citation_metadata_completeness"]["locator_completeness"] == 1.0
    assert report["citation_metadata_completeness"]["strict_structured_row_count"] == 23
    assert report["citation_metadata_completeness"]["diagnostic_only_fallback_row_count"] == 0
    assert report["diagnostic_only_fallback_rows"] == []
    for key in (
        "target_cell_hit",
        "target_row_hit",
        "header_included",
        "target_column_included",
        "surrounding_context_included",
        "sheet_resolution_accuracy",
        "citation_locator_completeness",
    ):
        assert report["strict_silver_evidence_metrics"][key] == 1.0


def test_cli_writes_json_and_markdown(tmp_path: Path):
    module = load_module()
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"

    code = module.main(["--json-output", str(json_path), "--md-output", str(md_path)])

    assert code == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["counts"]["generated_silver_row_count"] == 23
    assert "XLSX Strict Silver Generation Report" in md_path.read_text(encoding="utf-8")
