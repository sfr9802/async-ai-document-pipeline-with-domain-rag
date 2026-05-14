from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_xlsx_answer_citation_diagnostic.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_xlsx_answer_citation_diagnostic_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_xlsx_review_input_uses_structured_evidence_only_and_stays_diagnostic(tmp_path: Path):
    module = load_module()
    paths = write_xlsx_fixture(tmp_path)
    output_jsonl = tmp_path / "review_input.jsonl"
    report_json = tmp_path / "report.json"
    report_md = tmp_path / "report.md"
    leakage_json = tmp_path / "leakage_reprobe.json"

    report = module.run_generation(
        strict_report=paths["strict_report"],
        strict_manifest=paths["strict_manifest"],
        leakage_report=paths["leakage_report"],
        output_jsonl=output_jsonl,
        output_report=report_json,
        output_md=report_md,
        leakage_reprobe_output=leakage_json,
    )

    assert report["status"] == "PASS"
    assert report["counts"]["input_strict_silver_rows"] == 1
    assert report["counts"]["generated_review_input_rows"] == 1
    assert report["counts"]["answer_claim_supported_rows"] == 1
    assert report["counts"]["citation_locator_resolved_rows"] == 1
    assert report["diagnostic_metric_preview"]["generated_answer_rows"] == 1
    assert report["diagnostic_metric_preview"]["answer_citation_clean_pass_rows"] == 1
    assert report["diagnostic_metric_preview"]["clean_pass_rows"] == 1
    assert report["diagnostic_metric_preview"]["cleanup_rows"] == 0
    assert report["diagnostic_metric_preview"]["rewrite_unresolved_rows"] == 0
    assert report["diagnostic_metric_preview"]["citation_fully_supported_rows"] == 1
    assert report["diagnostic_metric_preview"]["citation_locator_valid_rows"] == 1
    assert report["diagnostic_metric_preview"]["leakage_count"] == 0
    assert report["diagnostic_metric_preview"]["official_metric_input_rows"] == 0
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["guardrails"]["official_metric_input_remains_false"] is True
    assert report["guardrails"]["promotion_evidence_remains_false"] is True

    rows = read_jsonl(output_jsonl)
    assert len(rows) == 1
    row = rows[0]
    assert row["query_id"] == "gq_xlsx_lookup_001"
    assert row["diagnostic_only"] is True
    assert row["official_metric_input"] is False
    assert row["promotion_evidence"] is False
    assert row["local_llm_run"] is False
    assert row["formatter_input"].keys() == module.STRUCTURED_EVIDENCE_KEYS
    serialized_prompt_input = json.dumps(row["formatter_input"], ensure_ascii=False)
    assert "debug_text" not in serialized_prompt_input
    assert "embedding_text" not in serialized_prompt_input
    assert "hidden_value_payload" not in serialized_prompt_input
    assert row["verifier"]["answer_claim_support_status"] == "PASS"
    assert row["verifier"]["citation_locator_status"] == "PASS"
    assert row["citation_items"][0]["locator"]["sheet"] == "철도"
    assert leakage_json.exists()
    assert json.loads(leakage_json.read_text(encoding="utf-8"))["status"] == "PASS"


def test_missing_strict_report_can_fallback_to_explicit_manifest(tmp_path: Path):
    module = load_module()
    paths = write_xlsx_fixture(tmp_path)
    paths["strict_report"].unlink()

    report = module.build_report(
        strict_report=paths["strict_report"],
        strict_manifest=paths["strict_manifest"],
        leakage_report=paths["leakage_report"],
    )

    assert report["status"] == "PASS"
    assert report["source_artifacts"]["strict_report"]["exists"] is False
    assert report["source_artifacts"]["strict_report_fallback_used"] is True
    assert report["counts"]["input_strict_silver_rows"] == 1


def test_pending_or_flattened_rows_fail_closed(tmp_path: Path):
    module = load_module()
    paths = write_xlsx_fixture(
        tmp_path,
        rows=[
            xlsx_manifest_row("gq_xlsx_date_number_format_003"),
            {**xlsx_manifest_row("gq_xlsx_lookup_flattened"), "diagnostic_only": True, "diagnostic_only_reason": "flattened_only"},
        ],
    )

    report = module.build_report(
        strict_report=paths["strict_report"],
        strict_manifest=paths["strict_manifest"],
        leakage_report=paths["leakage_report"],
    )

    assert report["status"] == "FAIL"
    assert "pending evidence rows appeared in answer/citation input: gq_xlsx_date_number_format_003" in report[
        "validation"
    ]["errors"]
    assert any("flattened-only evidence cannot enter answer/citation review input" in error for error in report["validation"]["errors"])


def test_run_generation_does_not_emit_review_input_when_prevalidation_fails(tmp_path: Path):
    module = load_module()
    paths = write_xlsx_fixture(tmp_path, rows=[xlsx_manifest_row("gq_xlsx_date_number_format_003")])
    output_jsonl = tmp_path / "blocked_review_input.jsonl"

    report = module.run_generation(
        strict_report=paths["strict_report"],
        strict_manifest=paths["strict_manifest"],
        leakage_report=paths["leakage_report"],
        output_jsonl=output_jsonl,
        output_report=tmp_path / "report.json",
        output_md=tmp_path / "report.md",
        leakage_reprobe_output=tmp_path / "leakage_reprobe.json",
    )

    assert report["status"] == "FAIL"
    assert not output_jsonl.exists()
    assert report["artifact_paths"]["review_input_jsonl_written"] is False


def test_hidden_excluded_reprobe_scans_answer_and_citation_surfaces(tmp_path: Path):
    module = load_module()
    normalized_csv = tmp_path / "normalized.csv"
    normalized_csv.write_text(
        "\n".join(
            [
                "query_id,derived_denominator_policy,query,evidence_summary,evidence_headers,evidence_row_values,evidence_cell_values,normalized_expected_answer_text,normalized_must_contain_terms_json,citation_locator",
                "hidden_001,EXCLUDED,FORBIDDENVALUE,,,,,,,{}",
            ]
        ),
        encoding="utf-8",
    )
    official_csv = tmp_path / "official.csv"
    official_csv.write_text("query_id\nshown_001\n", encoding="utf-8")
    route_json = tmp_path / "route.json"
    fallback_json = tmp_path / "fallback.json"
    guard_row = {
        "query_id": "guard",
        "blocked_flags": ["hidden_negative_or_excluded_row_guard"],
        "official_metric_input": False,
    }
    route_json.write_text(json.dumps({"applied_human_review_rows": [guard_row]}, ensure_ascii=False), encoding="utf-8")
    fallback_json.write_text(json.dumps({"applied_human_review_rows": [guard_row]}, ensure_ascii=False), encoding="utf-8")
    three_track_json = tmp_path / "three_track.json"
    three_track_json.write_text(json.dumps({"tracks": {}}, ensure_ascii=False), encoding="utf-8")
    registry_json = tmp_path / "registry.json"
    registry_json.write_text("{}", encoding="utf-8")
    answer_surface = tmp_path / "answer.jsonl"
    answer_surface.write_text(json.dumps({"answer": "FORBIDDENVALUE"}, ensure_ascii=False), encoding="utf-8")

    report = module.run_hidden_excluded_reprobe(
        generated_surface_paths=[answer_surface],
        normalized_csv=normalized_csv,
        official_positive_csv=official_csv,
        route_applied_json=route_json,
        fallback_applied_json=fallback_json,
        three_track_report_json=three_track_json,
        official_denominator_registry=registry_json,
    )

    assert report["status"] == "FAIL"
    assert report["counts"]["surface_leakage_count"] == 1
    assert report["surface_coverage"]["answer"]["status"] == "FAIL"


def test_metric_preview_holds_clean_pass_when_leakage_reprobe_fails(tmp_path: Path):
    module = load_module()
    paths = write_xlsx_fixture(tmp_path)

    report = module.run_generation(
        strict_report=paths["strict_report"],
        strict_manifest=paths["strict_manifest"],
        leakage_report=paths["leakage_report"],
        output_jsonl=tmp_path / "review_input.jsonl",
        output_report=tmp_path / "report.json",
        output_md=tmp_path / "report.md",
        leakage_reprobe_output=tmp_path / "leakage_reprobe.json",
    )
    report["leakage_reprobe"] = {"status": "FAIL", "surface_leakage_count": 2}
    module.apply_xlsx_metric_preview(report)

    assert report["diagnostic_metric_preview"]["answer_citation_clean_pass_rows"] == 1
    assert report["diagnostic_metric_preview"]["clean_pass_rows"] == 0
    assert report["diagnostic_metric_preview"]["cleanup_rows"] == 1
    assert report["diagnostic_metric_preview"]["leakage_count"] == 2


def test_contextual_leakage_annotation_does_not_clear_raw_failures():
    module = load_module()
    raw = {
        "status": "FAIL",
        "counts": {"surface_leakage_count": 1},
        "surface_coverage": {
            "answer": {
                "configured_file_count": 1,
                "existing_file_count": 1,
                "leakage_count": 1,
                "status": "FAIL",
            }
        },
        "surface_scan": [
            {
                "surface": "answer",
                "path": "surface.jsonl",
                "exists": True,
                "status": "FAIL",
                "leakage_count": 1,
                "violations": [
                    {
                        "surface": "answer",
                        "path": "surface.jsonl",
                        "query_id": "excluded",
                        "token_sha256": ["shared-token"],
                    }
                ],
            }
        ],
        "surface_violations": [
            {
                "surface": "answer",
                "path": "surface.jsonl",
                "query_id": "excluded",
                "token_sha256": ["shared-token"],
            }
        ],
        "validation": {"ok": False, "errors": ["excluded or hidden-negative raw content surfaced"]},
        "guardrails": {"hidden_excluded_content_exposed": True},
    }

    report = module.contextualize_leakage_reprobe(raw, allowed_token_hashes={"shared-token"})

    assert report["status"] == "FAIL"
    assert report["counts"]["surface_leakage_count"] == 1
    assert report["allowlist_policy"]["allowlisted_surface_violation_count"] == 1
    assert report["allowlist_policy"]["status_effect"] == "annotation_only"


def write_xlsx_fixture(tmp_path: Path, rows: list[dict] | None = None) -> dict[str, Path]:
    rows = rows or [xlsx_manifest_row("gq_xlsx_lookup_001")]
    strict_manifest = tmp_path / "strict_manifest.jsonl"
    strict_manifest.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    strict_report = tmp_path / "strict_report.json"
    strict_report.write_text(
        json.dumps(
            {
                "status": "COMPLETED_DIAGNOSTIC_ONLY",
                "counts": {
                    "input_denominator_row_count": len(rows),
                    "generated_silver_row_count": len(rows),
                    "pending_evidence_row_count": 2,
                },
                "included_query_ids": [row["query_id"] for row in rows],
                "excluded_query_ids": {
                    "pending_evidence": ["gq_xlsx_aggregation_001", "gq_xlsx_date_number_format_003"],
                    "normalized_excluded": [],
                    "normalized_hidden_negative": [],
                },
                "silver_artifact_policy": {
                    "external_silver_artifact": {"path": str(strict_manifest), "exists": True}
                },
                "guardrails": {
                    "official_denominator_registry_changed": False,
                    "xlsx_answer_generation_denominator_opened": False,
                    "production_namespace_mutated": False,
                    "production_vector_index_mutated": False,
                    "production_vector_written": False,
                    "candidate_artifact_mutated": False,
                    "immutable_baseline_mutated": False,
                    "hidden_xlsx_exposed": False,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    leakage_report = tmp_path / "leakage.json"
    leakage_report.write_text(
        json.dumps(
            {
                "status": "PASS",
                "counts": {"surface_leakage_count": 0, "probe_target_row_count": 0},
                "target_rows": [],
                "surface_coverage": {"answer": {"status": "NOT_OPENED"}, "citation": {"status": "NOT_OPENED"}},
                "guardrails": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"strict_report": strict_report, "strict_manifest": strict_manifest, "leakage_report": leakage_report}


def xlsx_manifest_row(query_id: str) -> dict:
    return {
        "schema_version": "xlsx_strict_retrieval_evidence_silver_v1",
        "query_id": query_id,
        "track": "xlsx_business_structured",
        "evidence_lane": "xlsx_structured_evidence",
        "diagnostic_only": False,
        "diagnostic_only_reason": "",
        "answer_generation_denominator_included": False,
        "official_metric_input": False,
        "promotion_evidence": False,
        "citation_metadata": {
            "file": "sample.xlsx",
            "sheet": "철도",
            "table_id": "table-1",
            "table_range": "A2:D2",
            "matched_cells": ["A2:D2"],
            "header_rows": [1],
            "target_rows": [2],
            "target_columns": ["A", "B", "C", "D"],
            "row_values": [
                {"column_label": "노선명", "value": "1호선"},
                {"column_label": "승차총승객수", "value": "8,633,618"},
            ],
            "column_headers": ["노선명", "승차총승객수"],
            "nearby_rows": [{"row_text": "노선명: 1호선 | 승차총승객수: 8,633,618"}],
            "merged_cell_context": [],
        },
        "citation_locator": {
            "file": "sample.xlsx",
            "sheet": "철도",
            "range": "A2:D2",
            "document_version_id": "docv1",
            "search_unit_id": "su1",
        },
    }


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
