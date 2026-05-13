from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "route_label_review_packs.py"

REQUIRED_COLUMNS = [
    "query_id",
    "safe_query_text",
    "source_type_hint",
    "reviewed_primary_route",
    "reviewed_candidate_routes",
    "expected_evidence_lane",
    "fallback_allowed",
    "fallback_expected_route",
    "fallback_outcome_label",
    "wrong_route_label",
    "denominator_scope",
    "reviewer",
    "reviewed_time",
    "notes",
]


def load_module():
    spec = importlib.util.spec_from_file_location("route_label_review_packs", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_review_packs_separates_human_labels_from_codex_diagnostics(tmp_path: Path):
    module = load_module()
    report_path = tmp_path / "three_track_orchestration_report.json"
    report_path.write_text(json.dumps(fixture_report(), ensure_ascii=False) + "\n", encoding="utf-8")
    registry = tmp_path / "official_denominator_registry.json"
    registry.write_text(json.dumps({"schema_version": "official_denominator_registry_v1"}) + "\n", encoding="utf-8")

    packs = module.build_review_packs(report_path=report_path, official_denominator_registry=registry)

    route_pack = packs["route_gold_label_review_pack"]
    fallback_pack = packs["fallback_outcome_label_review_pack"]
    assert route_pack["diagnostic_only"] is True
    assert fallback_pack["diagnostic_only"] is True
    assert route_pack["route_metrics_official"] is False
    assert fallback_pack["fallback_metrics_official"] is False
    assert route_pack["required_columns"] == REQUIRED_COLUMNS
    assert fallback_pack["required_columns"] == REQUIRED_COLUMNS
    assert route_pack["counts"]["human_review_rows"] == 5
    assert route_pack["counts"]["codex_diagnostic_only_rows"] == 4
    assert fallback_pack["counts"]["human_review_rows"] == 3
    assert fallback_pack["counts"]["codex_diagnostic_only_rows"] == 4
    assert route_pack["counts"]["tracks_present"] == [
        "text_namuwiki_animation",
        "xlsx_business_structured",
        "pdf_business_ocr_mm",
    ]
    assert fallback_pack["bounded_fallback_policy"]["maximum_fallback_attempts"] == 1
    assert fallback_pack["bounded_fallback_policy"]["allow_unscoped"] is False


def test_review_rows_preserve_required_columns_and_guardrails(tmp_path: Path):
    module = load_module()
    report_path = tmp_path / "three_track_orchestration_report.json"
    report_path.write_text(json.dumps(fixture_report(), ensure_ascii=False) + "\n", encoding="utf-8")
    registry = tmp_path / "official_denominator_registry.json"
    registry.write_text(json.dumps({"schema_version": "official_denominator_registry_v1"}) + "\n", encoding="utf-8")

    packs = module.build_review_packs(report_path=report_path, official_denominator_registry=registry)
    serialized = json.dumps(packs, ensure_ascii=False)

    for pack in packs.values():
        for section in ("human_review_rows", "codex_diagnostic_only_rows"):
            for row in pack[section]:
                assert list(row.keys())[: len(REQUIRED_COLUMNS)] == REQUIRED_COLUMNS
                assert row["diagnostic_only"] is True
                assert row["official_metric_input"] is False
                assert row["denominator_scope"] in module.DENOMINATOR_SCOPES.values()

    route_pack = packs["route_gold_label_review_pack"]
    assert route_pack["guardrails"]["official_denominator_registry_changed"] is False
    assert route_pack["guardrails"]["production_namespace_mutated"] is False
    assert route_pack["guardrails"]["production_vector_index_mutated"] is False
    assert route_pack["guardrails"]["hidden_xlsx_content_exposed"] is False
    assert route_pack["guardrails"]["pdf_content_and_file_identity_aggregated"] is False
    assert "hidden cell value" not in serialized
    assert "xlsx_hidden_source_payload" not in serialized

    pdf_rows = [
        row
        for row in route_pack["human_review_rows"] + route_pack["codex_diagnostic_only_rows"]
        if row["source_type_hint"].startswith("pdf")
    ]
    assert {row["expected_evidence_lane"] for row in pdf_rows} >= {
        "pdf_content_evidence",
        "pdf_file_identity",
    }


def test_main_writes_all_review_pack_artifacts_without_registry_mutation(tmp_path: Path):
    module = load_module()
    report_path = tmp_path / "three_track_orchestration_report.json"
    report_path.write_text(json.dumps(fixture_report(), ensure_ascii=False) + "\n", encoding="utf-8")
    registry = tmp_path / "official_denominator_registry.json"
    registry.write_text(json.dumps({"schema_version": "official_denominator_registry_v1"}) + "\n", encoding="utf-8")
    registry_before = registry.read_text(encoding="utf-8")

    result = module.main(
        [
            "--report-json",
            str(report_path),
            "--official-denominator-registry",
            str(registry),
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert (tmp_path / "route_gold_label_review_pack_v1.json").exists()
    assert (tmp_path / "route_gold_label_review_pack_v1.md").exists()
    assert (tmp_path / "fallback_outcome_label_review_pack_v1.json").exists()
    assert (tmp_path / "fallback_outcome_label_review_pack_v1.md").exists()
    assert registry.read_text(encoding="utf-8") == registry_before
    route_json = json.loads((tmp_path / "route_gold_label_review_pack_v1.json").read_text(encoding="utf-8"))
    fallback_json = json.loads((tmp_path / "fallback_outcome_label_review_pack_v1.json").read_text(encoding="utf-8"))
    assert route_json["status"] == "PASS"
    assert fallback_json["status"] == "PASS"


def fixture_report() -> dict:
    return {
        "schema_version": "three_track_orchestration_report_v3",
        "diagnostic_only": True,
        "route_metrics_official": False,
        "production_namespace_mutated": False,
        "production_vector_index_mutated": False,
        "production_vector_written": False,
        "official_denominator_registry_changed": False,
        "official_denominator_opened_or_frozen": False,
        "bounded_fallback_loop": {
            "maximum_fallback_attempts": 1,
            "allow_unscoped": False,
            "production_mutation": False,
        },
        "tracks": {
            "text_namuwiki_animation": {
                "evidence_lane": "text_content",
                "denominator_scope": "text_namuwiki_bound_diagnostic_denominator_47_answer_citation_denominator_not_open",
            },
            "xlsx_business_structured": {
                "evidence_lane": "xlsx_structured_evidence",
                "denominator_scope": "xlsx_retrieval_evidence_diagnostic_denominator_23_answer_generation_denominator_0",
            },
            "pdf_business_ocr_mm": {
                "content_evidence_lane": "pdf_content_evidence",
                "file_document_identity_lane": "pdf_file_identity",
                "denominator_scope": "pdf_conservative_content_and_file_identity_denominators_separate_answer_denominator_0",
            },
        },
        "route_diagnostic_contract": {
            "sample_diagnostics": [
                {
                    "query_id": "req-graph-1",
                    "safe_query_text": "합계?",
                    "primary_route": "xlsx_business_structured",
                    "candidate_routes": ["xlsx_business_structured"],
                    "evidence_lane": "xlsx_structured_evidence",
                    "fallback_plan": ["pdf_business_ocr_mm"],
                    "fallback_attempts": [{"attempt": 1, "route": "pdf_business_ocr_mm"}],
                    "final_diagnostic_status": "fallback_blocked",
                    "denominator_scope": "xlsx_retrieval_evidence_diagnostic_denominator_23_answer_generation_denominator_0",
                    "diagnostic_only": True,
                },
                {
                    "query_id": "generic-pdf-file-identity",
                    "safe_query_text": "계약서 PDF 파일 찾아줘",
                    "primary_route": "policy_blocked",
                    "candidate_routes": ["pdf_business_ocr_mm"],
                    "evidence_lane": "pdf_file_identity",
                    "blocked_flags": ["stable_identity_required"],
                    "fallback_attempts": [],
                    "final_diagnostic_status": "policy_blocked",
                    "diagnostic_only": True,
                },
            ]
        },
    }
