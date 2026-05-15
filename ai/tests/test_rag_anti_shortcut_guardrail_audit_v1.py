from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_anti_shortcut_guardrail_audit_v1.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_anti_shortcut_guardrail_audit_v1_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_anti_shortcut_audit_passes_clean_diagnostic_pack(tmp_path: Path) -> None:
    module = load_module()
    paths = write_guardrail_sources(tmp_path)

    audit = module.run_audit(
        xlsx_packet_path=paths["xlsx_packet"],
        xlsx_leakage_reprobe_path=paths["xlsx_leakage"],
        xlsx_review_input_path=paths["xlsx_review_input"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        human_audit_packet_path=paths["human_audit_packet"],
        dry_run_plan_path=paths["dry_run_plan"],
        output_report=tmp_path / "anti_shortcut_guardrail_audit_v1.json",
        output_md=tmp_path / "anti_shortcut_guardrail_audit_v1.md",
    )

    assert audit["status"] == "ANTI_SHORTCUT_GUARDRAIL_AUDIT_PASS"
    assert audit["validation"]["ok"] is True
    assert audit["checks"]["xlsx_public_private_surface_separation"]["public_surface_leakage_count"] == 0
    assert audit["checks"]["pdf_bbox_source_bound_proof"]["strict_ready_rows_checked"] == 7
    assert audit["checks"]["pdf_answer_citation_packet"]["official_metric_input_rows"] == 0
    assert audit["checks"]["human_audit_packet"]["gold_policy_required_count_matches_report"] is True
    assert audit["checks"]["dry_run_plan"]["tuning_run_started"] is False


def test_anti_shortcut_audit_fails_on_synthetic_or_page_anchor_bbox(tmp_path: Path) -> None:
    module = load_module()
    paths = write_guardrail_sources(tmp_path)
    repair = read_json(paths["pdf_repair"])
    repair["repair_rows"][0]["bbox_source"] = "synthetic.generated_bbox"
    repair["repair_rows"][1]["bbox_source"] = "page_anchor_only"
    repair["repair_rows"][1]["layout_resolution_method"] = "full_page_fallback"
    write_json(paths["pdf_repair"], repair)

    audit = module.run_audit(
        xlsx_packet_path=paths["xlsx_packet"],
        xlsx_leakage_reprobe_path=paths["xlsx_leakage"],
        xlsx_review_input_path=paths["xlsx_review_input"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        human_audit_packet_path=paths["human_audit_packet"],
        dry_run_plan_path=paths["dry_run_plan"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    errors = audit["validation"]["errors"]
    assert audit["status"] == "ANTI_SHORTCUT_GUARDRAIL_AUDIT_FAIL_CLOSED"
    assert "PDF bbox source must be source-bound for gq_pdf_page_lookup_001" in errors
    assert "PDF bbox source must be source-bound for gq_pdf_section_question_001" in errors
    assert "full-page/page-anchor fallback cannot make strict-ready row gq_pdf_section_question_001" in errors


def test_anti_shortcut_audit_fails_if_formerly_blocked_pdf_rows_lack_source_bound_bbox(tmp_path: Path) -> None:
    module = load_module()
    paths = write_guardrail_sources(tmp_path)
    repair = read_json(paths["pdf_repair"])
    row = next(item for item in repair["repair_rows"] if item["query_id"] == "gq_auto_010")
    row["bbox_source"] = "inferred_from_page_anchor"
    write_json(paths["pdf_repair"], repair)

    audit = module.run_audit(
        xlsx_packet_path=paths["xlsx_packet"],
        xlsx_leakage_reprobe_path=paths["xlsx_leakage"],
        xlsx_review_input_path=paths["xlsx_review_input"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        human_audit_packet_path=paths["human_audit_packet"],
        dry_run_plan_path=paths["dry_run_plan"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    assert "formerly blocked PDF row gq_auto_010 must use source-bound bbox" in audit["validation"]["errors"]


def test_anti_shortcut_audit_fails_if_pdf_file_lane_is_content_or_filename_only(tmp_path: Path) -> None:
    module = load_module()
    paths = write_guardrail_sources(tmp_path)
    rows = read_jsonl(paths["pdf_review_input"])
    rows[0]["no_file_identity_lane_used_as_content_evidence"] = False
    rows[0]["content_evidence_lane"] = "pdf_file_identity"
    rows[1]["no_filename_only_identity_acceptance"] = False
    write_jsonl(paths["pdf_review_input"], rows)

    audit = module.run_audit(
        xlsx_packet_path=paths["xlsx_packet"],
        xlsx_leakage_reprobe_path=paths["xlsx_leakage"],
        xlsx_review_input_path=paths["xlsx_review_input"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        human_audit_packet_path=paths["human_audit_packet"],
        dry_run_plan_path=paths["dry_run_plan"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    errors = audit["validation"]["errors"]
    assert "PDF FILE identity lane used as CONTENT evidence" in errors
    assert "PDF filename-only identity accepted" in errors


def test_anti_shortcut_audit_fails_if_pdf_answer_packet_ready_counts_are_not_clean(tmp_path: Path) -> None:
    module = load_module()
    paths = write_guardrail_sources(tmp_path)
    packet = read_json(paths["pdf_answer_packet"])
    packet["clean_pass_rows"] = 0
    packet["cleanup_rows"] = 7
    packet["unresolved_rows"] = 7
    packet["lane_policy_blocked_rows"] = 7
    packet["answer_support_pass_count"] = 0
    packet["citation_locator_valid_count"] = 0
    write_json(paths["pdf_answer_packet"], packet)

    audit = module.run_audit(
        xlsx_packet_path=paths["xlsx_packet"],
        xlsx_leakage_reprobe_path=paths["xlsx_leakage"],
        xlsx_review_input_path=paths["xlsx_review_input"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        human_audit_packet_path=paths["human_audit_packet"],
        dry_run_plan_path=paths["dry_run_plan"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    errors = audit["validation"]["errors"]
    assert "PDF answer/citation packet must have 7 clean pass rows" in errors
    assert "PDF answer/citation packet must have 0 cleanup/unresolved/lane-policy rows" in errors
    assert "PDF answer/citation packet must have 7 support and citation-valid rows" in errors


def test_anti_shortcut_audit_fails_if_xlsx_public_leakage_or_annotation_allowlist_pass(tmp_path: Path) -> None:
    module = load_module()
    paths = write_guardrail_sources(tmp_path)
    leakage = read_json(paths["xlsx_leakage"])
    leakage["metrics"]["surface_leakage_count"] = 1
    leakage["query_results"][0]["surface_violation_count"] = 1
    leakage["allowlist_policy"]["annotation_only_allowlist_promoted_to_pass"] = True
    write_json(paths["xlsx_leakage"], leakage)

    audit = module.run_audit(
        xlsx_packet_path=paths["xlsx_packet"],
        xlsx_leakage_reprobe_path=paths["xlsx_leakage"],
        xlsx_review_input_path=paths["xlsx_review_input"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        human_audit_packet_path=paths["human_audit_packet"],
        dry_run_plan_path=paths["dry_run_plan"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    errors = audit["validation"]["errors"]
    assert "XLSX hidden/excluded row appeared on public surface" in errors
    assert "annotation-only allowlist cannot create PASS" in errors


def test_anti_shortcut_audit_fails_if_human_audit_drops_answer_recovery_gold_policy_ids(tmp_path: Path) -> None:
    module = load_module()
    paths = write_guardrail_sources(tmp_path)
    human = read_json(paths["human_audit_packet"])
    human["sections"]["answer_recovery"]["gold_policy_required_count_matches_report"] = False
    human["sections"]["answer_recovery"]["gold_policy_required_ids_match_report"] = False
    write_json(paths["human_audit_packet"], human)

    audit = module.run_audit(
        xlsx_packet_path=paths["xlsx_packet"],
        xlsx_leakage_reprobe_path=paths["xlsx_leakage"],
        xlsx_review_input_path=paths["xlsx_review_input"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        human_audit_packet_path=paths["human_audit_packet"],
        dry_run_plan_path=paths["dry_run_plan"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    errors = audit["validation"]["errors"]
    assert "human audit answer recovery GOLD_POLICY_REQUIRED count mismatch" in errors
    assert "human audit answer recovery GOLD_POLICY_REQUIRED id mismatch" in errors


def test_anti_shortcut_audit_fails_if_dry_run_starts_tuning_or_cross_track_average(tmp_path: Path) -> None:
    module = load_module()
    paths = write_guardrail_sources(tmp_path)
    plan = read_json(paths["dry_run_plan"])
    plan["tuning_run_started"] = True
    plan["cross_track_average_optimization_allowed"] = True
    plan["official_metric_input_rows"] = 1
    plan["split_policy"]["cross_track_average_computed"] = True
    write_json(paths["dry_run_plan"], plan)

    audit = module.run_audit(
        xlsx_packet_path=paths["xlsx_packet"],
        xlsx_leakage_reprobe_path=paths["xlsx_leakage"],
        xlsx_review_input_path=paths["xlsx_review_input"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        human_audit_packet_path=paths["human_audit_packet"],
        dry_run_plan_path=paths["dry_run_plan"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    errors = audit["validation"]["errors"]
    assert "dry-run plan must not start tuning" in errors
    assert "dry-run plan must not compute or optimize cross-track averages" in errors
    assert "dry-run plan official_metric_input_rows must remain 0" in errors


def test_anti_shortcut_audit_fails_if_dry_run_nested_split_cross_track_average_is_computed(tmp_path: Path) -> None:
    module = load_module()
    paths = write_guardrail_sources(tmp_path)
    plan = read_json(paths["dry_run_plan"])
    plan["split_policy"]["cross_track_average_computed"] = True
    write_json(paths["dry_run_plan"], plan)

    audit = module.run_audit(
        xlsx_packet_path=paths["xlsx_packet"],
        xlsx_leakage_reprobe_path=paths["xlsx_leakage"],
        xlsx_review_input_path=paths["xlsx_review_input"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        human_audit_packet_path=paths["human_audit_packet"],
        dry_run_plan_path=paths["dry_run_plan"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    assert audit["status"] == "ANTI_SHORTCUT_GUARDRAIL_AUDIT_FAIL_CLOSED"
    assert "dry-run plan must not compute or optimize cross-track averages" in audit["validation"]["errors"]


def write_guardrail_sources(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "xlsx_packet": tmp_path / "xlsx_packet.json",
        "xlsx_leakage": tmp_path / "xlsx_leakage.json",
        "xlsx_review_input": tmp_path / "xlsx_review_input.jsonl",
        "pdf_repair": tmp_path / "pdf_repair.json",
        "pdf_answer_packet": tmp_path / "pdf_answer_packet.json",
        "pdf_review_input": tmp_path / "pdf_review_input.jsonl",
        "human_audit_packet": tmp_path / "human_audit_packet.json",
        "dry_run_plan": tmp_path / "dry_run_plan.json",
    }
    write_json(paths["xlsx_packet"], xlsx_packet())
    write_json(paths["xlsx_leakage"], xlsx_leakage())
    write_jsonl(paths["xlsx_review_input"], [xlsx_row("gq_xlsx_lookup_001")])
    write_json(paths["pdf_repair"], pdf_repair())
    write_json(paths["pdf_answer_packet"], pdf_answer_packet())
    write_jsonl(paths["pdf_review_input"], [pdf_review_row(qid) for qid in PDF_QUERY_IDS])
    write_json(paths["human_audit_packet"], human_audit_packet())
    write_json(paths["dry_run_plan"], dry_run_plan())
    return paths


PDF_QUERY_IDS = [
    "gq_pdf_page_lookup_001",
    "gq_pdf_section_question_001",
    "gq_auto_010",
    "gq_auto_015",
    "gq_auto_030",
    "gq_pdf_table_lookup_001",
    "gq_pdf_summary_001",
]


def xlsx_packet() -> dict[str, object]:
    return {
        "status": "DIAGNOSTIC_POLICY_PACKET_READY",
        "diagnostic_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "leakage_raw_status": "PASS",
        "leakage_raw_total": 0,
        "validation": {"ok": True, "errors": []},
    }


def xlsx_leakage() -> dict[str, object]:
    return {
        "status": "PASS",
        "diagnostic_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "metrics": {"surface_leakage_count": 0},
        "allowlist_policy": {"annotation_only_allowlist_promoted_to_pass": False},
        "notes": ["public surfaces only: generated_answer, answer_claims, citation_items"],
        "query_results": [
            {
                "query_id": "hidden_xlsx_001",
                "row_source": "normalized_excluded",
                "surface_violation_count": 0,
                "official_metric_input": False,
            }
        ],
        "validation": {"ok": True, "errors": []},
    }


def xlsx_row(query_id: str) -> dict[str, object]:
    return {
        "query_id": query_id,
        "generated_answer": "public answer",
        "answer_claims": ["public claim"],
        "citation_items": [{"locator": "Sheet1!A1"}],
        "formatter_input": {"private_context_may_contain_hidden_tokens": True},
        "official_metric_input": False,
        "promotion_evidence": False,
    }


def pdf_repair() -> dict[str, object]:
    rows = []
    for query_id in PDF_QUERY_IDS:
        rows.append(
            {
                "query_id": query_id,
                "strict_ready": True,
                "search_unit_id": f"su-{query_id}",
                "source_file_id": f"sf-{query_id}",
                "stable_source_identity": f"docv-{query_id}",
                "parser_version": "pdf-extract-v2",
                "source_metadata": {"metadata_source": "local_db_readonly"},
                "page": 1,
                "bbox": [1.0, 2.0, 3.0, 4.0],
                "region_type": "paragraph",
                "bbox_source": "local_db.search_unit.location_json.bbox",
                "layout_resolution_method": "source_bound_bbox_from_search_unit_location_json",
                "citation_locator": {"page": 1, "bbox": [1.0, 2.0, 3.0, 4.0], "search_unit_id": f"su-{query_id}"},
                "content_evidence_lane": "pdf_content_evidence",
                "file_identity_lane": {
                    "lane": "pdf_file_identity",
                    "filename_only_identity_accepted": False,
                    "merged_with_content_evidence": False,
                },
                "official_metric_input": False,
                "promotion_evidence": False,
            }
        )
    return {
        "status": "READY_FOR_DIAGNOSTIC_STRICT_GATE_RERUN",
        "diagnostic_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "strict_ready_rows": 7,
        "diagnostic_only_fallback_rows": 0,
        "repair_rows": rows,
        "validation": {"ok": True, "errors": []},
    }


def pdf_answer_packet() -> dict[str, object]:
    return {
        "status": "DIAGNOSTIC_POLICY_PACKET_READY",
        "diagnostic_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "input_rows": 7,
        "strict_ready_rows": 7,
        "generated_answer_rows": 7,
        "clean_pass_rows": 7,
        "cleanup_rows": 0,
        "unresolved_rows": 0,
        "answer_support_pass_count": 7,
        "citation_locator_valid_count": 7,
        "lane_policy_blocked_rows": 0,
        "diagnostic_fallback_rows_used": 0,
        "content_file_identity_lane_merge": False,
        "filename_only_identity_accepted": False,
        "pdf_answer_generation_denominator_opened": False,
        "validation": {"ok": True, "errors": []},
    }


def pdf_review_row(query_id: str) -> dict[str, object]:
    return {
        "query_id": query_id,
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "content_evidence_lane": "pdf_content_evidence",
        "no_file_identity_lane_used_as_content_evidence": True,
        "no_filename_only_identity_acceptance": True,
        "no_diagnostic_fallback_row_used": True,
        "citation_locator_valid": True,
        "bucket": "clean_pass",
        "bbox_source": "local_db.search_unit.location_json.bbox",
    }


def human_audit_packet() -> dict[str, object]:
    return {
        "status": "HUMAN_AUDIT_PACKET_READY",
        "diagnostic_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "summary": {"total_user_action_rows": 19},
        "sections": {
            "xlsx_business_structured": {"hidden_excluded_rows_candidate_count": 0},
            "pdf_business_ocr_mm": {"filename_only_identity_accepted": False},
            "answer_recovery": {
                "gold_policy_required_rows": 6,
                "expected_gold_policy_required_rows": 6,
                "row_group_gold_policy_required_rows": 6,
                "gold_policy_required_count_matches_report": True,
                "gold_policy_required_ids_match_report": True,
            },
        },
        "validation": {"ok": True, "errors": []},
    }


def dry_run_plan() -> dict[str, object]:
    return {
        "status": "REPORT_ONLY_DRY_RUN_PLAN_READY",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_by_track": {
            "text_namu_v2_1": 0,
            "xlsx_business_structured": 0,
            "pdf_business_ocr_mm": 0,
        },
        "tuning_run_started": False,
        "official_metrics_closed": True,
        "cross_track_average_optimization_allowed": False,
        "cross_track_averages_computed": False,
        "split_policy": {"parameter_winner_selected": False, "cross_track_average_computed": False},
        "track_dev_set_policy": {
            "text_namu_v2_1": {"dev_set_role": "diagnostic_dev_not_final_holdout"},
            "xlsx_business_structured": {"dev_set_role": "diagnostic_dev_not_final_holdout"},
            "pdf_business_ocr_mm": {"answer_citation_dry_run_eligibility": "eligible"},
        },
        "validation": {"ok": True, "errors": []},
    }


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
