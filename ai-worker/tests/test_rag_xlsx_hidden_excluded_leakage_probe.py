from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_xlsx_hidden_excluded_leakage_probe.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_xlsx_hidden_excluded_leakage_probe", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_probe_passes_when_normalized_excluded_rows_stay_off_surfaces(tmp_path: Path):
    module = load_module()
    fixture = write_fixture(tmp_path)
    before = fixture["registry"].read_text(encoding="utf-8")

    report = module.build_probe_report(
        normalized_csv=fixture["normalized_csv"],
        official_positive_csv=fixture["official_positive_csv"],
        route_applied_json=fixture["route_applied_json"],
        fallback_applied_json=fixture["fallback_applied_json"],
        three_track_report_json=fixture["three_track_report_json"],
        official_denominator_registry=fixture["registry"],
        surface_specs=[
            module.SurfaceSpec("debug_public", fixture["clean_surface"]),
            module.SurfaceSpec("candidate", fixture["official_positive_csv"]),
        ],
    )
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["status"] == "PASS"
    assert report["diagnostic_only"] is True
    assert report["promotion_evidence"] is False
    assert report["counts"]["normalized_excluded_row_count"] == 2
    assert report["counts"]["normalized_hidden_negative_row_count"] == 1
    assert report["counts"]["hidden_excluded_guard_row_count"] == 2
    assert report["counts"]["probe_target_row_count"] == 4
    assert report["counts"]["surface_leakage_count"] == 0
    assert report["guardrails"]["official_denominator_registry_changed"] is False
    assert report["guardrails"]["policy_excluded_rows_counted_as_retrieval_failures"] is False
    assert report["guardrails"]["answer_citation_debug_surface_exposed"] is False
    assert fixture["registry"].read_text(encoding="utf-8") == before
    assert "SECRET_EXCLUDED_VALUE" not in serialized
    assert "HIDDEN_NEGATIVE_PAYLOAD" not in serialized


def test_probe_fails_closed_when_excluded_content_appears_on_surface(tmp_path: Path):
    module = load_module()
    fixture = write_fixture(tmp_path)

    report = module.build_probe_report(
        normalized_csv=fixture["normalized_csv"],
        official_positive_csv=fixture["official_positive_csv"],
        route_applied_json=fixture["route_applied_json"],
        fallback_applied_json=fixture["fallback_applied_json"],
        three_track_report_json=fixture["three_track_report_json"],
        official_denominator_registry=fixture["registry"],
        surface_specs=[
            module.SurfaceSpec("answer", fixture["leaky_surface"]),
            module.SurfaceSpec("candidate", fixture["official_positive_csv"]),
        ],
    )
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["status"] == "FAIL"
    assert report["counts"]["surface_leakage_count"] == 1
    assert report["guardrails"]["answer_citation_debug_surface_exposed"] is True
    assert report["surface_violations"][0]["surface"] == "answer"
    assert report["surface_violations"][0]["query_id"] == "gq_xlsx_hidden_policy_001"
    assert "HIDDEN_NEGATIVE_PAYLOAD" not in serialized


def test_main_writes_json_and_md_without_registry_mutation(tmp_path: Path):
    module = load_module()
    fixture = write_fixture(tmp_path)
    json_output = tmp_path / "probe.json"
    md_output = tmp_path / "probe.md"
    before = fixture["registry"].read_text(encoding="utf-8")

    code = module.main(
        [
            "--normalized-csv",
            str(fixture["normalized_csv"]),
            "--official-positive-csv",
            str(fixture["official_positive_csv"]),
            "--route-applied-json",
            str(fixture["route_applied_json"]),
            "--fallback-applied-json",
            str(fixture["fallback_applied_json"]),
            "--three-track-report-json",
            str(fixture["three_track_report_json"]),
            "--official-denominator-registry",
            str(fixture["registry"]),
            "--surface-file",
            f"debug_public={fixture['clean_surface']}",
            "--surface-file",
            f"candidate={fixture['official_positive_csv']}",
            "--json-output",
            str(json_output),
            "--md-output",
            str(md_output),
        ]
    )

    assert code == 0
    assert json_output.exists()
    assert md_output.exists()
    assert json.loads(json_output.read_text(encoding="utf-8"))["status"] == "PASS"
    assert fixture["registry"].read_text(encoding="utf-8") == before


def write_fixture(tmp_path: Path) -> dict[str, Path]:
    normalized_csv = tmp_path / "gold_queries_xlsx_human_review_normalized_v0.csv"
    write_csv(
        normalized_csv,
        [
            {
                "query_id": "gq_xlsx_hidden_policy_001",
                "query": "do not surface HIDDEN_NEGATIVE_PAYLOAD",
                "derived_denominator_policy": "EXCLUDED",
                "derived_policy_reasons": "human_policy_excluded",
                "user_relevance_label": "POLICY_EXCLUDED",
                "user_answerability_label": "NOT_ANSWERABLE",
                "evidence_summary": "HIDDEN_NEGATIVE_PAYLOAD",
                "evidence_headers": "",
                "evidence_row_values": "",
                "evidence_cell_values": "",
                "deterministic_compiled_answer": "",
                "expected_answer_text_existing": "",
                "user_expected_answer_text": "",
                "normalized_expected_answer_text": "",
                "must_contain_terms_existing": "",
                "normalized_must_contain_terms_json": "[]",
                "citation_locator": "{}",
                "sheet": "",
                "range": "",
                "include_in_official_positive_denominator": "FALSE",
                "not_answer_generation_denominator": "TRUE",
            },
            {
                "query_id": "gq_xlsx_formula_value_001",
                "query": "do not surface SECRET_EXCLUDED_VALUE",
                "derived_denominator_policy": "EXCLUDED",
                "derived_policy_reasons": "human_policy_excluded",
                "user_relevance_label": "POLICY_EXCLUDED",
                "user_answerability_label": "ANSWERABLE_NEEDS_SOURCE_VERIFICATION",
                "evidence_summary": "SECRET_EXCLUDED_VALUE",
                "evidence_headers": "",
                "evidence_row_values": "",
                "evidence_cell_values": "",
                "deterministic_compiled_answer": "",
                "expected_answer_text_existing": "",
                "user_expected_answer_text": "",
                "normalized_expected_answer_text": "",
                "must_contain_terms_existing": "",
                "normalized_must_contain_terms_json": "[]",
                "citation_locator": "{}",
                "sheet": "",
                "range": "",
                "include_in_official_positive_denominator": "FALSE",
                "not_answer_generation_denominator": "TRUE",
            },
            {
                "query_id": "gq_xlsx_lookup_001",
                "query": "safe positive",
                "derived_denominator_policy": "OFFICIAL_POSITIVE",
                "derived_policy_reasons": "strict_official_contract_satisfied",
                "user_relevance_label": "EVIDENCE_RELEVANT",
                "user_answerability_label": "ANSWERABLE_CONFIRMED",
                "evidence_summary": "safe",
                "evidence_headers": "",
                "evidence_row_values": "",
                "evidence_cell_values": "",
                "deterministic_compiled_answer": "safe",
                "expected_answer_text_existing": "safe",
                "user_expected_answer_text": "",
                "normalized_expected_answer_text": "safe",
                "must_contain_terms_existing": "safe",
                "normalized_must_contain_terms_json": "[\"safe\"]",
                "citation_locator": "{\"sheet\":\"Sheet1\",\"range\":\"A1:B2\"}",
                "sheet": "Sheet1",
                "range": "A1:B2",
                "include_in_official_positive_denominator": "TRUE",
                "not_answer_generation_denominator": "TRUE",
            },
        ],
    )

    official_positive_csv = tmp_path / "gold_queries_xlsx_human_review_official_positive_v0_retrieval.csv"
    write_csv(
        official_positive_csv,
        [
            {
                "query_id": "gq_xlsx_lookup_001",
                "query": "safe positive",
                "hidden_policy": "exclude_hidden",
            }
        ],
    )

    route_applied_json = tmp_path / "route_gold_label_review_applied_v1.json"
    write_json(
        route_applied_json,
        {
            "diagnostic_only": True,
            "route_metrics_official": False,
            "guardrails": guardrails(),
            "codex_diagnostic_only_rows": [
                {
                    "query_id": "route_auto_xlsx_hidden_excluded_guard_001",
                    "safe_query_text": "[redacted xlsx excluded-row guard probe]",
                    "source_type_hint": "xlsx_hidden_or_excluded_guard",
                    "blocked_flags": ["hidden_negative_or_excluded_row_guard"],
                    "diagnostic_only": True,
                    "official_metric_input": False,
                    "production_vector_write": False,
                }
            ],
        },
    )
    fallback_applied_json = tmp_path / "fallback_outcome_label_review_applied_v1.json"
    write_json(
        fallback_applied_json,
        {
            "diagnostic_only": True,
            "fallback_metrics_official": False,
            "guardrails": guardrails(),
            "codex_diagnostic_only_rows": [
                {
                    "query_id": "fallback_auto_xlsx_hidden_excluded_blocked_001",
                    "safe_query_text": "[redacted xlsx excluded-row fallback guard]",
                    "source_type_hint": "xlsx_hidden_or_excluded_guard",
                    "blocked_flags": ["hidden_negative_or_excluded_row_guard"],
                    "diagnostic_only": True,
                    "official_metric_input": False,
                    "production_vector_write": False,
                }
            ],
        },
    )
    three_track_report_json = tmp_path / "three_track_orchestration_report.json"
    write_json(
        three_track_report_json,
        {
            "diagnostic_only": True,
            "official_denominator_registry_changed": False,
            "official_denominator_opened_or_frozen": False,
            "production_namespace_mutated": False,
            "production_vector_index_mutated": False,
            "production_vector_written": False,
            "promotion_evidence_created": False,
            "diagnostic_only_row_promoted": False,
            "tracks": {
                "xlsx_business_structured": {
                    "answer_generation_denominator": 0,
                    "guardrails": ["hidden_negative_or_excluded_row_guard"],
                },
                "pdf_business_ocr_mm": {
                    "guardrails": [
                        "content_evidence_and_file_document_identity_lanes_not_aggregated",
                        "policy_excluded_rows_not_counted_as_retrieval_failures",
                    ]
                },
            },
        },
    )
    registry = tmp_path / "official_denominator_registry.json"
    write_json(registry, {"schema_version": "official_denominator_registry_v1", "query_ids": ["gq_xlsx_lookup_001"]})
    clean_surface = tmp_path / "clean_surface.md"
    clean_surface.write_text("No excluded row content here.\n", encoding="utf-8")
    leaky_surface = tmp_path / "answer_surface.md"
    leaky_surface.write_text("The answer says HIDDEN_NEGATIVE_PAYLOAD.\n", encoding="utf-8")

    return {
        "normalized_csv": normalized_csv,
        "official_positive_csv": official_positive_csv,
        "route_applied_json": route_applied_json,
        "fallback_applied_json": fallback_applied_json,
        "three_track_report_json": three_track_report_json,
        "registry": registry,
        "clean_surface": clean_surface,
        "leaky_surface": leaky_surface,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    columns = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def guardrails() -> dict:
    return {
        "official_denominator_registry_changed": False,
        "official_denominator_opened_or_frozen": False,
        "production_namespace_mutated": False,
        "production_vector_index_mutated": False,
        "production_vector_written": False,
        "candidate_artifact_mutated": False,
        "immutable_baseline_mutated": False,
        "diagnostic_only_row_promoted": False,
        "pdf_content_and_file_identity_aggregated": False,
        "hidden_xlsx_content_exposed": False,
        "policy_excluded_rows_counted_as_retrieval_failures": False,
        "route_metrics_official": False,
        "fallback_metrics_official": False,
    }
