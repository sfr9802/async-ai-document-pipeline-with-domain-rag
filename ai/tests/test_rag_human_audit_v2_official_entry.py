from __future__ import annotations

import importlib.util
import json
import sys
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "ai" / "scripts"


def load_script(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_for_tests", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_v2_applied_decisions_maps_labels_by_track_without_opening_registry(tmp_path: Path) -> None:
    module = load_script("rag_human_audit_v2_applied_decisions")
    packet = tmp_path / "human_audit_v2.json"
    registry = tmp_path / "official_denominator_registry.json"
    write_json(packet, human_audit_packet())
    write_json(registry, registry_payload())
    before = registry.read_bytes()

    report = module.run_application(
        human_audit_packet_path=packet,
        official_denominator_registry=registry,
        output_report=tmp_path / "applied.json",
        output_md=tmp_path / "applied.md",
    )

    assert report["status"] == "HUMAN_AUDIT_V2_APPLIED_DECISIONS_READY"
    assert report["summary"]["approved_rows_by_track"] == {
        "pdf_business_ocr_mm": 1,
        "text_namu_v2_1": 1,
        "xlsx_business_structured": 1,
    }
    assert report["summary"]["non_approved_rows_by_label"] == {"DO_NOT_INCLUDE_IN_OFFICIAL_DENOMINATOR": 1}
    assert report["summary"]["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["guardrails"]["official_denominator_registry_changed"] is False
    assert registry.read_bytes() == before
    assert any(row["supersedes_rejected_row_id"] == "pdf_1" for row in report["approved_candidate_rows"])
    text_row = next(row for row in report["approved_candidate_rows"] if row["track"] == "text_namu_v2_1")
    assert text_row["expected_answer"] == "짧은 답변입니다."
    assert text_row["expected_answer_normalization"] == "extracted_short_answer_from_text_report"


def test_v2_applied_decisions_requires_bridge_for_rejected_bad_question_overlap(tmp_path: Path) -> None:
    module = load_script("rag_human_audit_v2_applied_decisions")
    payload = human_audit_packet()
    payload["actionable_rows"][0].pop("supersedes_rejected_row_id")
    payload["actionable_rows"][0].pop("query_id_bridge_policy")
    packet = tmp_path / "human_audit_v2.json"
    registry = tmp_path / "official_denominator_registry.json"
    write_json(packet, payload)
    write_json(registry, registry_payload())

    report = module.run_application(
        human_audit_packet_path=packet,
        official_denominator_registry=registry,
        output_report=tmp_path / "applied.json",
        output_md=tmp_path / "applied.md",
    )

    assert report["status"] == "HUMAN_AUDIT_V2_APPLIED_DECISIONS_FAIL_CLOSED"
    assert any("without explicit supersedes bridge" in error for error in report["validation"]["errors"])
    assert report["official_metric_input_rows"] == 0


def test_denominator_candidate_diff_preview_is_read_only_and_counts_by_track(tmp_path: Path) -> None:
    applied_module = load_script("rag_human_audit_v2_applied_decisions")
    preview_module = load_script("rag_official_denominator_candidate_diff_preview_v1")
    packet = tmp_path / "human_audit_v2.json"
    registry = tmp_path / "official_denominator_registry.json"
    applied_path = tmp_path / "applied.json"
    write_json(packet, human_audit_packet())
    write_json(registry, registry_payload())
    applied_module.run_application(
        human_audit_packet_path=packet,
        official_denominator_registry=registry,
        output_report=applied_path,
        output_md=tmp_path / "applied.md",
    )
    before = registry.read_bytes()

    preview = preview_module.run_preview(
        applied_decisions_path=applied_path,
        official_denominator_registry=registry,
        output_report=tmp_path / "preview.json",
        output_md=tmp_path / "preview.md",
    )

    assert preview["status"] == "OFFICIAL_DENOMINATOR_CANDIDATE_DIFF_PREVIEW_READY"
    assert preview["registry_diff_status"] == "PREVIEW_ONLY_NO_MUTATION"
    assert preview["summary"]["proposed_rows_by_track"] == {
        "pdf_business_ocr_mm": 1,
        "text_namu_v2_1": 1,
        "xlsx_business_structured": 1,
    }
    assert preview["official_metric_input_rows"] == 0
    assert preview["guardrails"]["official_denominator_registry_changed"] is False
    assert registry.read_bytes() == before


def test_denominator_candidate_diff_preview_fails_on_registry_key_overlap(tmp_path: Path) -> None:
    applied_module = load_script("rag_human_audit_v2_applied_decisions")
    preview_module = load_script("rag_official_denominator_candidate_diff_preview_v1")
    packet = tmp_path / "human_audit_v2.json"
    registry = tmp_path / "official_denominator_registry.json"
    applied_path = tmp_path / "applied.json"
    registry_payload_with_overlap = registry_payload()
    registry_payload_with_overlap["official_diagnostic_denominators"][
        "track_a_xlsx_question_gold_v2_human_audit_approved"
    ] = {"row_count": 99}
    write_json(packet, human_audit_packet())
    write_json(registry, registry_payload_with_overlap)
    applied_module.run_application(
        human_audit_packet_path=packet,
        official_denominator_registry=registry,
        output_report=applied_path,
        output_md=tmp_path / "applied.md",
    )

    preview = preview_module.run_preview(
        applied_decisions_path=applied_path,
        official_denominator_registry=registry,
        output_report=tmp_path / "preview.json",
        output_md=tmp_path / "preview.md",
    )

    assert preview["status"] == "OFFICIAL_DENOMINATOR_CANDIDATE_DIFF_PREVIEW_FAIL_CLOSED"
    assert any("already exist" in error for error in preview["validation"]["errors"])


def test_metric_input_config_stays_closed_until_registry_application(tmp_path: Path) -> None:
    applied_module = load_script("rag_human_audit_v2_applied_decisions")
    preview_module = load_script("rag_official_denominator_candidate_diff_preview_v1")
    config_module = load_script("rag_official_metric_input_config_v1")
    packet = tmp_path / "human_audit_v2.json"
    registry = tmp_path / "official_denominator_registry.json"
    applied_path = tmp_path / "applied.json"
    preview_path = tmp_path / "preview.json"
    write_json(packet, human_audit_packet())
    write_json(registry, registry_payload())
    applied_module.run_application(
        human_audit_packet_path=packet,
        official_denominator_registry=registry,
        output_report=applied_path,
        output_md=tmp_path / "applied.md",
    )
    preview_module.run_preview(
        applied_decisions_path=applied_path,
        official_denominator_registry=registry,
        output_report=preview_path,
        output_md=tmp_path / "preview.md",
    )

    config = config_module.run_config(
        applied_decisions_path=applied_path,
        denominator_diff_preview_path=preview_path,
        output_report=tmp_path / "config.json",
        output_md=tmp_path / "config.md",
    )

    assert config["status"] == "OFFICIAL_METRIC_INPUT_CONFIG_READY_PENDING_REGISTRY_APPLICATION"
    assert config["proposed_metric_input_rows"] == 3
    assert config["proposed_metric_input_rows_by_track"] == {
        "pdf_business_ocr_mm": 1,
        "text_namu_v2_1": 1,
        "xlsx_business_structured": 1,
    }
    assert config["official_metric_input_rows"] == 0
    assert config["official_metric_execution_started"] is False
    assert config["metric_execution_allowed"] is False
    assert config["promotion_evidence"] is False
    assert config["tuning_run_started"] is False


def test_registry_application_materializes_candidates_and_updates_registry(tmp_path: Path) -> None:
    applied_module = load_script("rag_human_audit_v2_applied_decisions")
    preview_module = load_script("rag_official_denominator_candidate_diff_preview_v1")
    apply_module = load_script("rag_official_question_gold_v2_registry_apply")
    config_module = load_script("rag_official_metric_input_config_v1")
    apply_module.TRACK_OUTPUTS = {
        "text_namu_v2_1": tmp_path / "eval_queries" / "gold_queries_text_namu_v2_1_question_gold_v2.csv",
        "xlsx_business_structured": tmp_path / "eval_queries" / "gold_queries_xlsx_question_gold_v2.csv",
        "pdf_business_ocr_mm": tmp_path / "eval_queries" / "gold_queries_pdf_question_gold_v2.csv",
    }
    packet = tmp_path / "human_audit_v2.json"
    registry = tmp_path / "official_denominator_registry.json"
    applied_path = tmp_path / "applied.json"
    preview_path = tmp_path / "preview.json"
    application_path = tmp_path / "application.json"
    write_json(packet, human_audit_packet())
    write_json(registry, registry_payload())
    applied_module.run_application(
        human_audit_packet_path=packet,
        official_denominator_registry=registry,
        output_report=applied_path,
        output_md=tmp_path / "applied.md",
    )
    preview_module.TRACK_OUTPUT_PATHS = {
        track: apply_module.repo_relative(path) for track, path in apply_module.TRACK_OUTPUTS.items()
    }
    preview_module.run_preview(
        applied_decisions_path=applied_path,
        official_denominator_registry=registry,
        output_report=preview_path,
        output_md=tmp_path / "preview.md",
    )

    report = apply_module.run_application(
        applied_decisions_path=applied_path,
        denominator_diff_preview_path=preview_path,
        registry_path=registry,
        output_report=application_path,
        output_md=tmp_path / "application.md",
    )

    assert report["status"] == "OFFICIAL_QUESTION_GOLD_V2_REGISTRY_APPLIED"
    assert report["registry_updated"] is True
    assert report["official_metric_input_rows_by_track"] == {
        "pdf_business_ocr_mm": 1,
        "text_namu_v2_1": 1,
        "xlsx_business_structured": 1,
    }
    for track, path in apply_module.TRACK_OUTPUTS.items():
        rows = read_csv(path)
        assert len(rows) == 1
        assert rows[0]["track"] == track
        assert rows[0]["official_metric_input"] == "TRUE"
        assert rows[0]["promotion_evidence"] == "FALSE"
        if track == "text_namu_v2_1":
            assert rows[0]["expected_answer"] == "짧은 답변입니다."
            assert "**Short answer:**" not in rows[0]["expected_answer"]
            assert "**Supporting passages:**" not in rows[0]["expected_answer"]
    registry_payload_after = json.loads(registry.read_text(encoding="utf-8"))
    denominators = registry_payload_after["official_diagnostic_denominators"]
    assert denominators["track_a_xlsx_question_gold_v2_human_audit_approved"]["row_count"] == 1
    assert denominators["track_a_xlsx_question_gold_v2_human_audit_approved"]["denominator_kind"] == "question_answer_citation_gold_v2"
    assert registry_payload_after["current_defaults"]["track_a_xlsx"]["denominator_key"] == "track_a_xlsx_human_review_normalized_v0"
    assert registry_payload_after["current_defaults"]["track_a_xlsx_question_gold_v2"]["official_metric_input_rows"] == 1

    config = config_module.run_config(
        applied_decisions_path=applied_path,
        denominator_diff_preview_path=preview_path,
        registry_application_report_path=application_path,
        output_report=tmp_path / "config.json",
        output_md=tmp_path / "config.md",
    )
    assert config["status"] == "OFFICIAL_METRIC_INPUT_CONFIG_READY_REGISTRY_BACKED_NOT_EXECUTED"
    assert config["official_metric_input_rows"] == 3
    assert config["metric_execution_allowed"] is True
    assert config["official_metric_execution_started"] is False
    assert config["tuning_run_started"] is False


def test_registry_application_fails_closed_on_existing_key_conflict(tmp_path: Path) -> None:
    applied_module = load_script("rag_human_audit_v2_applied_decisions")
    preview_module = load_script("rag_official_denominator_candidate_diff_preview_v1")
    apply_module = load_script("rag_official_question_gold_v2_registry_apply")
    apply_module.TRACK_OUTPUTS = {
        "text_namu_v2_1": tmp_path / "eval_queries" / "gold_queries_text_namu_v2_1_question_gold_v2.csv",
        "xlsx_business_structured": tmp_path / "eval_queries" / "gold_queries_xlsx_question_gold_v2.csv",
        "pdf_business_ocr_mm": tmp_path / "eval_queries" / "gold_queries_pdf_question_gold_v2.csv",
    }
    packet = tmp_path / "human_audit_v2.json"
    registry = tmp_path / "official_denominator_registry.json"
    applied_path = tmp_path / "applied.json"
    preview_path = tmp_path / "preview.json"
    write_json(packet, human_audit_packet())
    write_json(registry, registry_payload())
    applied_module.run_application(
        human_audit_packet_path=packet,
        official_denominator_registry=registry,
        output_report=applied_path,
        output_md=tmp_path / "applied.md",
    )
    preview_module.TRACK_OUTPUT_PATHS = {
        track: apply_module.repo_relative(path) for track, path in apply_module.TRACK_OUTPUTS.items()
    }
    preview_module.run_preview(
        applied_decisions_path=applied_path,
        official_denominator_registry=registry,
        output_report=preview_path,
        output_md=tmp_path / "preview.md",
    )
    registry_payload_with_conflict = json.loads(registry.read_text(encoding="utf-8"))
    registry_payload_with_conflict["official_diagnostic_denominators"][
        "track_c_pdf_question_gold_v2_human_audit_approved"
    ] = {"path": "different.csv", "denominator_kind": "other"}
    write_json(registry, registry_payload_with_conflict)
    before = registry.read_bytes()

    report = apply_module.run_application(
        applied_decisions_path=applied_path,
        denominator_diff_preview_path=preview_path,
        registry_path=registry,
        output_report=tmp_path / "application.json",
        output_md=tmp_path / "application.md",
    )

    assert report["status"] == "OFFICIAL_QUESTION_GOLD_V2_REGISTRY_APPLY_FAIL_CLOSED"
    assert any("registry key collision" in error for error in report["validation"]["errors"])
    assert registry.read_bytes() == before


def test_registry_application_fails_closed_on_preview_key_mismatch(tmp_path: Path) -> None:
    applied_module = load_script("rag_human_audit_v2_applied_decisions")
    preview_module = load_script("rag_official_denominator_candidate_diff_preview_v1")
    apply_module = load_script("rag_official_question_gold_v2_registry_apply")
    apply_module.TRACK_OUTPUTS = {
        "text_namu_v2_1": tmp_path / "eval_queries" / "gold_queries_text_namu_v2_1_question_gold_v2.csv",
        "xlsx_business_structured": tmp_path / "eval_queries" / "gold_queries_xlsx_question_gold_v2.csv",
        "pdf_business_ocr_mm": tmp_path / "eval_queries" / "gold_queries_pdf_question_gold_v2.csv",
    }
    packet = tmp_path / "human_audit_v2.json"
    registry = tmp_path / "official_denominator_registry.json"
    applied_path = tmp_path / "applied.json"
    preview_path = tmp_path / "preview.json"
    write_json(packet, human_audit_packet())
    write_json(registry, registry_payload())
    applied_module.run_application(
        human_audit_packet_path=packet,
        official_denominator_registry=registry,
        output_report=applied_path,
        output_md=tmp_path / "applied.md",
    )
    preview_module.TRACK_OUTPUT_PATHS = {
        track: apply_module.repo_relative(path) for track, path in apply_module.TRACK_OUTPUTS.items()
    }
    preview = preview_module.run_preview(
        applied_decisions_path=applied_path,
        official_denominator_registry=registry,
        output_report=preview_path,
        output_md=tmp_path / "preview.md",
    )
    entries = preview["proposed_registry_patch"]["entries"]
    xlsx_entry = entries.pop("track_a_xlsx_question_gold_v2_human_audit_approved")
    entries["track_a_xlsx_question_gold_v2_wrong_key"] = xlsx_entry
    write_json(preview_path, preview)
    before = registry.read_bytes()

    report = apply_module.run_application(
        applied_decisions_path=applied_path,
        denominator_diff_preview_path=preview_path,
        registry_path=registry,
        output_report=tmp_path / "application.json",
        output_md=tmp_path / "application.md",
    )

    assert report["status"] == "OFFICIAL_QUESTION_GOLD_V2_REGISTRY_APPLY_FAIL_CLOSED"
    assert any("preview denominator key mismatch" in error for error in report["validation"]["errors"])
    assert registry.read_bytes() == before


def human_audit_packet() -> dict[str, object]:
    rows = [
        action_row(
            "pdf_1",
            "pdf_business_ocr_mm",
            locator={"page": 1, "bbox": [1, 2, 3, 4], "search_unit_id": "su_1", "region_type": "paragraph"},
            supersedes=True,
        ),
        action_row(
            "xlsx_1",
            "xlsx_business_structured",
            locator={"workbook": "book.xlsx", "sheet": "Sheet1", "range": "A1:B2", "cells": ["B2"]},
        ),
        action_row("text_1", "text_namu_v2_1", locator={"doc_id": "doc_1"}),
        action_row(
            "xlsx_excluded_1",
            "xlsx_business_structured",
            label="DO_NOT_INCLUDE_IN_OFFICIAL_DENOMINATOR",
            locator={"workbook": "book.xlsx", "sheet": "Sheet1", "range": "A3:B3", "cells": ["B3"]},
        ),
    ]
    rows[2]["proposed_answer"] = (
        "**Query:** 테스트 질문\n\n"
        "**Short answer:** 짧은 답변입니다.\n\n"
        "**Supporting passages:**\n1. 근거 문장\n\n"
        "**Sources:** doc_1"
    )
    return {
        "status": "HUMAN_AUDIT_PACKET_V2_READY",
        "human_audit_completed": True,
        "human_audit_label_counts": {
            "DO_NOT_INCLUDE_IN_OFFICIAL_DENOMINATOR": 1,
            "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE": 3,
        },
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "actionable_rows": rows,
        "non_action_diagnostic_summary": {"rejected_bad_question_row_ids": ["pdf_1"]},
        "summary": {
            "human_audit_completed": True,
            "human_labeled_rows": 4,
            "human_unlabeled_rows": 0,
            "pdf_generated_candidates": 1,
            "xlsx_generated_candidates": 1,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
        },
    }


def action_row(
    query_id: str,
    track: str,
    *,
    label: str = "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE",
    locator: dict[str, object] | None = None,
    supersedes: bool = False,
) -> dict[str, object]:
    row = {
        "query_id": query_id,
        "row_id": query_id,
        "track": track,
        "question": f"{query_id} 질문은 무엇인가요?",
        "proposed_answer": f"{query_id} 답변",
        "proposed_evidence": f"{query_id} 근거",
        "citation_locator": locator or {},
        "human_label": label,
        "human_review_required": True,
        "human_review_status": "USER_REVIEWED_APPROVED",
        "allowed_decision_values": [
            "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE",
            "DO_NOT_INCLUDE_IN_OFFICIAL_DENOMINATOR",
        ],
        "model_assisted_diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "gold_promoted": False,
        "official_denominator_current": False,
        "source_packet_role": "manual_source_bound_pdf_context_v2" if track == "pdf_business_ocr_mm" else "test",
    }
    if supersedes:
        row["supersedes_rejected_row_id"] = query_id
        row["query_id_bridge_policy"] = "supersedes_bad_original_question_row"
    return row


def registry_payload() -> dict[str, object]:
    return {
        "schema_version": "official_denominator_registry_v1",
        "updated_at": "2026-05-16",
        "policy": {},
        "current_defaults": {
            "track_a_xlsx": {"denominator_key": "track_a_xlsx_human_review_normalized_v0"},
        },
        "official_diagnostic_denominators": {
            "track_a_xlsx_human_review_normalized_v0": {"row_count": 23},
        },
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
