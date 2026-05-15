from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_human_audit_packet_v1.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_human_audit_packet_v1_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_human_audit_packet_includes_only_user_owned_decision_rows(tmp_path: Path) -> None:
    module = load_module()
    paths = write_audit_sources(tmp_path)

    packet = module.run_packet(
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        pdf_query_report_path=paths["pdf_query_report"],
        route_applied_path=paths["route_applied"],
        fallback_applied_path=paths["fallback_applied"],
        answer_recovery_report_path=paths["answer_recovery_md"],
        output_report=tmp_path / "rag_human_audit_packet_v1.json",
        output_md=tmp_path / "rag_human_audit_packet_v1.md",
    )

    rows = packet["actionable_rows"]
    row_ids = {row["row_id"] for row in rows}

    assert packet["status"] == "HUMAN_AUDIT_PACKET_READY"
    assert packet["official_metric_input_rows"] == 0
    assert packet["promotion_evidence"] is False
    assert packet["summary"]["total_user_action_rows"] == 5
    assert row_ids == {
        "text_namu_v2_0005",
        "text_namu_v2_0017",
        "gq_pdf_page_lookup_001",
        "expanded_pdf_file_lookup_017",
        "expanded_xlsx_constraint_013",
    }
    assert "text_namu_v2_clean_sample" not in row_ids
    assert "expanded_xlsx_hidden_blocked_001" not in row_ids
    assert all(row["official_denominator_current"] is False for row in rows)
    assert all(row["promotion_evidence"] is False for row in rows)
    assert all(row["codex_recommendation_binding"] is False for row in rows)
    assert all(row["human_label"] is None and row["human_notes"] is None for row in rows)
    for row in rows:
        assert "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE" in row["allowed_decision_values"]
        assert "DO_NOT_INCLUDE_IN_OFFICIAL_DENOMINATOR" in row["allowed_decision_values"]
    assert packet["summary"]["rows_by_track"] == {
        "pdf_business_ocr_mm": 2,
        "text_namu_v2_1": 2,
        "xlsx_business_structured": 1,
    }
    assert packet["summary"]["decision_type_counts"]["official_denominator_inclusion"] == 5


def test_human_audit_packet_keeps_hidden_xlsx_and_pdf_file_identity_non_action(tmp_path: Path) -> None:
    module = load_module()
    paths = write_audit_sources(tmp_path)

    packet = module.run_packet(
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        pdf_query_report_path=paths["pdf_query_report"],
        route_applied_path=paths["route_applied"],
        fallback_applied_path=paths["fallback_applied"],
        answer_recovery_report_path=paths["answer_recovery_md"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    pdf_rows = [row for row in packet["actionable_rows"] if row["track"] == "pdf_business_ocr_mm"]

    assert packet["sections"]["xlsx_business_structured"]["hidden_excluded_rows_candidate_count"] == 0
    assert packet["sections"]["xlsx_business_structured"]["hidden_excluded_rows_summarized_not_action"] == 5
    assert packet["sections"]["pdf_business_ocr_mm"]["content_file_identity_lane_merge_detected"] is False
    assert packet["sections"]["pdf_business_ocr_mm"]["filename_only_identity_accepted"] is False
    assert packet["sections"]["pdf_business_ocr_mm"]["file_identity_rows_actionable"] == 1
    assert packet["sections"]["pdf_business_ocr_mm"]["filename_only_identity_rows_accepted"] == 0
    assert any(row["lane_decision_scope"] == "CONTENT_LANE_ONLY" for row in pdf_rows)
    assert any(row["lane_decision_scope"] == "FILE_IDENTITY_LANE_ONLY" for row in pdf_rows)
    assert all(row["content_file_identity_lane_merge"] is False for row in pdf_rows)
    assert all(row["filename_only_identity_accepted"] is False for row in pdf_rows)


def test_human_audit_packet_summarizes_diagnostic_only_and_route_rows_without_promotion(
    tmp_path: Path,
) -> None:
    module = load_module()
    paths = write_audit_sources(tmp_path)

    packet = module.run_packet(
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        pdf_query_report_path=paths["pdf_query_report"],
        route_applied_path=paths["route_applied"],
        fallback_applied_path=paths["fallback_applied"],
        answer_recovery_report_path=paths["answer_recovery_md"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    assert packet["sections"]["route_fallback"]["actionable_rows"] == []
    assert packet["sections"]["route_fallback"]["route_metrics_official"] is False
    assert packet["sections"]["route_fallback"]["fallback_metrics_official"] is False
    assert packet["sections"]["answer_recovery"]["gold_policy_required_rows"] == 2
    assert packet["sections"]["answer_recovery"]["non_action_summary"]["policy_blocked_correctly"] == 1
    assert packet["sections"]["answer_recovery"]["non_action_summary"]["diagnostic_only_do_not_promote"] == 1
    assert packet["sections"]["answer_recovery"]["non_action_summary"]["promotion_candidate"] == 0
    assert packet["summary"]["rows_not_requiring_user_action"] >= 1
    assert packet["validation"]["ok"] is True


def test_human_audit_packet_fails_if_hidden_xlsx_pending_row_is_candidate(tmp_path: Path) -> None:
    module = load_module()
    paths = write_audit_sources(tmp_path)
    xlsx = json.loads(paths["xlsx_packet"].read_text(encoding="utf-8"))
    xlsx["pending_evidence_rows"] = [
        {
            "query_id": "xlsx_neutral_pending_001",
            "question": "이번 달 매출 조건 확인",
            "status": "pending_evidence",
            "hidden": True,
            "official_metric_input": False,
            "promotion_evidence": False,
        }
    ]
    write_json(paths["xlsx_packet"], xlsx)

    packet = module.run_packet(
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        pdf_query_report_path=paths["pdf_query_report"],
        route_applied_path=paths["route_applied"],
        fallback_applied_path=paths["fallback_applied"],
        answer_recovery_report_path=paths["answer_recovery_md"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    assert packet["status"] == "FAILED_GUARDRAIL"
    assert packet["sections"]["xlsx_business_structured"]["hidden_excluded_rows_candidate_count"] == 1
    assert "xlsx_neutral_pending_001" not in {row["row_id"] for row in packet["actionable_rows"]}
    assert "hidden/excluded XLSX candidate count must be 0" in packet["validation"]["errors"]


def test_human_audit_packet_fails_if_source_official_rows_open(tmp_path: Path) -> None:
    module = load_module()
    paths = write_audit_sources(tmp_path)
    xlsx = json.loads(paths["xlsx_packet"].read_text(encoding="utf-8"))
    xlsx["official_metric_input_rows"] = 1
    write_json(paths["xlsx_packet"], xlsx)

    packet = module.run_packet(
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        pdf_query_report_path=paths["pdf_query_report"],
        route_applied_path=paths["route_applied"],
        fallback_applied_path=paths["fallback_applied"],
        answer_recovery_report_path=paths["answer_recovery_md"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    assert packet["status"] == "FAILED_GUARDRAIL"
    assert "xlsx_business_structured official_metric_input_rows must remain 0" in packet["validation"]["errors"]


def test_human_audit_packet_fails_if_source_artifact_is_official_or_promotion(tmp_path: Path) -> None:
    module = load_module()
    paths = write_audit_sources(tmp_path)
    xlsx = json.loads(paths["xlsx_packet"].read_text(encoding="utf-8"))
    xlsx["promotion_evidence"] = True
    write_json(paths["xlsx_packet"], xlsx)
    pdf = json.loads(paths["pdf_answer_packet"].read_text(encoding="utf-8"))
    pdf["official_metric"] = True
    write_json(paths["pdf_answer_packet"], pdf)

    packet = module.run_packet(
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        pdf_query_report_path=paths["pdf_query_report"],
        route_applied_path=paths["route_applied"],
        fallback_applied_path=paths["fallback_applied"],
        answer_recovery_report_path=paths["answer_recovery_md"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    assert packet["status"] == "FAILED_GUARDRAIL"
    assert "xlsx_business_structured source artifact must keep promotion_evidence=false" in packet["validation"]["errors"]
    assert "pdf_business_ocr_mm source artifact must keep official_metric=false" in packet["validation"]["errors"]


def test_human_audit_packet_fails_if_source_validation_is_missing(tmp_path: Path) -> None:
    module = load_module()
    paths = write_audit_sources(tmp_path)
    xlsx = json.loads(paths["xlsx_packet"].read_text(encoding="utf-8"))
    xlsx.pop("validation")
    write_json(paths["xlsx_packet"], xlsx)

    packet = module.run_packet(
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        pdf_query_report_path=paths["pdf_query_report"],
        route_applied_path=paths["route_applied"],
        fallback_applied_path=paths["fallback_applied"],
        answer_recovery_report_path=paths["answer_recovery_md"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    assert packet["status"] == "FAILED_GUARDRAIL"
    assert "xlsx_business_structured source validation.ok must be true" in packet["validation"]["errors"]


def test_human_audit_packet_fails_if_source_protected_guardrail_is_true(tmp_path: Path) -> None:
    module = load_module()
    paths = write_audit_sources(tmp_path)
    xlsx = json.loads(paths["xlsx_packet"].read_text(encoding="utf-8"))
    xlsx["guardrails"] = {"production_vector_written": True}
    write_json(paths["xlsx_packet"], xlsx)
    pdf = json.loads(paths["pdf_answer_packet"].read_text(encoding="utf-8"))
    pdf["guardrails"] = {"official_denominator_registry_mutation": True}
    write_json(paths["pdf_answer_packet"], pdf)

    packet = module.run_packet(
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        pdf_query_report_path=paths["pdf_query_report"],
        route_applied_path=paths["route_applied"],
        fallback_applied_path=paths["fallback_applied"],
        answer_recovery_report_path=paths["answer_recovery_md"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    assert packet["status"] == "FAILED_GUARDRAIL"
    assert (
        "xlsx_business_structured source protected guardrail violation: production_vector_written"
        in packet["validation"]["errors"]
    )
    assert (
        "pdf_business_ocr_mm source protected guardrail violation: official_denominator_registry_mutation"
        in packet["validation"]["errors"]
    )


def test_human_audit_packet_fails_if_answer_recovery_rows_are_missing_or_mismatched(tmp_path: Path) -> None:
    module = load_module()
    paths = write_audit_sources(tmp_path)
    paths["answer_recovery_md"].write_text(
        "\n".join(
            [
                "# Answer Recovery Tuning Report",
                "- category_counts: `POLICY_BLOCKED_CORRECTLY=1, GOLD_POLICY_REQUIRED=3, DIAGNOSTIC_ONLY_DO_NOT_PROMOTE=1`",
                "- row_groups: `promotion_candidate=[], policy_blocked_correctly=['expanded_xlsx_hidden_blocked_001'], diagnostic_only=['expanded_ocr_shadow_001'], gold_policy_required=['expanded_pdf_file_lookup_017', 'expanded_xlsx_constraint_013']`",
                "- gold_policy_required_user_review: `[{\"row_id\":\"expanded_pdf_file_lookup_017\",\"lane\":\"PDF_FILE_LOOKUP\",\"case_type\":\"pdf_file_lookup_identity\",\"reason\":\"Exact or canonical file identity is missing or ambiguous.\",\"judgment_needed\":\"User gold-policy judgment only.\"},{\"row_id\":\"expanded_xlsx_constraint_013\",\"lane\":\"XLSX\",\"case_type\":\"xlsx_needs_user_constraint\",\"reason\":\"Needs user metric or period; strict wrapper expansion must not guess.\",\"judgment_needed\":\"User gold-policy judgment only.\"}]`",
            ]
        ),
        encoding="utf-8",
    )

    packet = module.run_packet(
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        pdf_query_report_path=paths["pdf_query_report"],
        route_applied_path=paths["route_applied"],
        fallback_applied_path=paths["fallback_applied"],
        answer_recovery_report_path=paths["answer_recovery_md"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    assert packet["status"] == "FAILED_GUARDRAIL"
    assert "answer recovery GOLD_POLICY_REQUIRED rows must match category_counts and row_groups" in packet["validation"]["errors"]


def test_human_audit_packet_fails_if_answer_recovery_ids_do_not_match_row_groups(tmp_path: Path) -> None:
    module = load_module()
    paths = write_audit_sources(tmp_path)
    paths["answer_recovery_md"].write_text(
        "\n".join(
            [
                "# Answer Recovery Tuning Report",
                "- category_counts: `POLICY_BLOCKED_CORRECTLY=1, GOLD_POLICY_REQUIRED=2, DIAGNOSTIC_ONLY_DO_NOT_PROMOTE=1`",
                "- row_groups: `promotion_candidate=[], policy_blocked_correctly=['expanded_xlsx_hidden_blocked_001'], diagnostic_only=['expanded_ocr_shadow_001'], gold_policy_required=['expanded_pdf_file_lookup_017', 'expanded_xlsx_constraint_013']`",
                "- gold_policy_required_user_review: `[{\"row_id\":\"expanded_pdf_file_lookup_999\",\"lane\":\"PDF_FILE_LOOKUP\",\"case_type\":\"pdf_file_lookup_identity\",\"reason\":\"Exact or canonical file identity is missing or ambiguous.\",\"judgment_needed\":\"User gold-policy judgment only.\"},{\"row_id\":\"expanded_xlsx_constraint_999\",\"lane\":\"XLSX\",\"case_type\":\"xlsx_needs_user_constraint\",\"reason\":\"Needs user metric or period; strict wrapper expansion must not guess.\",\"judgment_needed\":\"User gold-policy judgment only.\"}]`",
            ]
        ),
        encoding="utf-8",
    )

    packet = module.run_packet(
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        pdf_query_report_path=paths["pdf_query_report"],
        route_applied_path=paths["route_applied"],
        fallback_applied_path=paths["fallback_applied"],
        answer_recovery_report_path=paths["answer_recovery_md"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    assert packet["status"] == "FAILED_GUARDRAIL"
    assert "answer recovery GOLD_POLICY_REQUIRED row ids must match row_groups" in packet["validation"]["errors"]


def test_human_audit_packet_fails_if_required_source_artifact_is_missing(tmp_path: Path) -> None:
    module = load_module()
    paths = write_audit_sources(tmp_path)
    paths["xlsx_packet"].unlink()

    packet = module.run_packet(
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_answer_packet_path=paths["pdf_answer_packet"],
        pdf_review_input_path=paths["pdf_review_input"],
        pdf_query_report_path=paths["pdf_query_report"],
        route_applied_path=paths["route_applied"],
        fallback_applied_path=paths["fallback_applied"],
        answer_recovery_report_path=paths["answer_recovery_md"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
    )

    assert packet["status"] == "FAILED_GUARDRAIL"
    assert "required source artifacts missing or empty: xlsx_packet" in packet["validation"]["errors"]


def write_audit_sources(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "text_packet": tmp_path / "text_packet.json",
        "xlsx_packet": tmp_path / "xlsx_packet.json",
        "pdf_answer_packet": tmp_path / "pdf_answer_packet.json",
        "pdf_review_input": tmp_path / "pdf_review_input.jsonl",
        "pdf_query_report": tmp_path / "pdf_query_report.json",
        "route_applied": tmp_path / "route_applied.json",
        "fallback_applied": tmp_path / "fallback_applied.json",
        "answer_recovery_md": tmp_path / "answer_recovery_tuning_report.md",
    }
    write_json(
        paths["text_packet"],
        {
            "status": "POLICY_REVIEW_PACKET_READY",
            "diagnostic_only": True,
            "validation": {"ok": True, "errors": []},
            "diagnostic_metric_preview": {"official_metric_input_rows": 0},
            "row_groups": {
                "cleanup_rows": {"row_count": 1},
                "unresolved_rows": {"row_count": 1},
            },
            "user_review": {
                "rows_requiring_human_decision": [
                    text_row("text_namu_v2_0005", "cleanup", True),
                    text_row("text_namu_v2_0017", "unresolved", True),
                    text_row("text_namu_v2_clean_sample", "clean_pass_audit_sample", False),
                ]
            },
        },
    )
    write_json(
        paths["xlsx_packet"],
        {
            "status": "DIAGNOSTIC_POLICY_PACKET_READY",
            "diagnostic_only": True,
            "official_metric_input_rows": 0,
            "validation": {"ok": True, "errors": []},
            "strict_silver_rows": 23,
            "hidden_negative_rows": 2,
            "normalized_excluded_rows": 3,
            "pending_excluded_rows": 0,
            "diagnostic_metric_preview": {
                "clean_pass_rows": 23,
                "cleanup_rows": 0,
                "rewrite_unresolved_rows": 0,
                "official_metric_input_rows": 0,
            },
        },
    )
    write_json(
        paths["pdf_answer_packet"],
        {
            "status": "DIAGNOSTIC_POLICY_PACKET_READY",
            "diagnostic_only": True,
            "official_metric_input_rows": 0,
            "input_rows": 2,
            "clean_pass_rows": 2,
            "cleanup_rows": 0,
            "unresolved_rows": 0,
            "lane_policy_blocked_rows": 0,
            "content_file_identity_lane_merge": False,
            "filename_only_identity_accepted": False,
            "validation": {"ok": True, "errors": []},
        },
    )
    write_jsonl(
        paths["pdf_review_input"],
        [
            pdf_row("gq_pdf_page_lookup_001", "pdf_content_evidence", "clean_pass"),
            pdf_row("expanded_pdf_file_lookup_017", "pdf_file_identity", "file_identity_policy_review"),
        ],
    )
    write_json(
        paths["pdf_query_report"],
        {
            "per_query": [
                {"query_id": "gq_pdf_page_lookup_001", "query": "최근 경제 동향 표지"},
                {"query_id": "expanded_pdf_file_lookup_017", "query": "문서 파일 신원 확인"},
            ],
            "query_results": [],
        },
    )
    write_json(
        paths["route_applied"],
        {
            "diagnostic_only": True,
            "route_metrics_official": False,
            "fallback_metrics_official": False,
            "validation": {"ok": True, "errors": []},
            "counts": {"official_metric_input_rows": 0, "applied_human_review_rows": 1},
            "applied_human_review_rows": [
                {"query_id": "route_resolved", "label_status": "applied_user_review", "official_metric_input": False}
            ],
        },
    )
    write_json(
        paths["fallback_applied"],
        {
            "diagnostic_only": True,
            "route_metrics_official": False,
            "fallback_metrics_official": False,
            "validation": {"ok": True, "errors": []},
            "counts": {"official_metric_input_rows": 0, "applied_human_review_rows": 0},
            "applied_human_review_rows": [],
        },
    )
    paths["answer_recovery_md"].write_text(
        "\n".join(
            [
                "# Answer Recovery Tuning Report",
                "- official_denominator_registry_changed: `False`",
                "- category_counts: `POLICY_BLOCKED_CORRECTLY=1, GOLD_POLICY_REQUIRED=2, DIAGNOSTIC_ONLY_DO_NOT_PROMOTE=1`",
                "- row_groups: `promotion_candidate=[], policy_blocked_correctly=['expanded_xlsx_hidden_blocked_001'], diagnostic_only=['expanded_ocr_shadow_001'], gold_policy_required=['expanded_pdf_file_lookup_017', 'expanded_xlsx_constraint_013']`",
                "- gold_policy_required_user_review: `[{\"row_id\":\"expanded_pdf_file_lookup_017\",\"lane\":\"PDF_FILE_LOOKUP\",\"case_type\":\"pdf_file_lookup_identity\",\"reason\":\"Exact or canonical file identity is missing or ambiguous.\",\"judgment_needed\":\"User gold-policy judgment only.\"},{\"row_id\":\"expanded_xlsx_constraint_013\",\"lane\":\"XLSX\",\"case_type\":\"xlsx_needs_user_constraint\",\"reason\":\"Needs user metric or period; strict wrapper expansion must not guess.\",\"judgment_needed\":\"User gold-policy judgment only.\"}]`",
            ]
        ),
        encoding="utf-8",
    )
    return paths


def text_row(query_id: str, bucket: str, human_needed: bool) -> dict[str, object]:
    return {
        "query_id": query_id,
        "review_bucket": bucket,
        "query": f"{query_id} 질문",
        "generated_short_answer": f"{query_id} 진단 답변",
        "suggested_extractive_answer_not_gold": f"{query_id} 제안 답변",
        "evidence_spans": [f"{query_id} 근거"],
        "cited_chunk_ids": [f"{query_id}-chunk"],
        "assistant_review_action": "KEEP_WITH_CLEANUP",
        "human_decision_needed": human_needed,
        "official_metric_input": False,
        "promotion_evidence": False,
        "not_human_approved": True,
    }


def pdf_row(query_id: str, lane: str, bucket: str) -> dict[str, object]:
    return {
        "query_id": query_id,
        "track": "pdf_business_ocr_mm",
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "content_evidence_lane": lane,
        "bucket": bucket,
        "diagnostic_answer": f"{query_id} 진단 답변",
        "matched_text": f"{query_id} 근거",
        "citation_text": "doc.pdf > p.1 > bbox [1,2,3,4]",
        "citation_locator": {"file": "doc.pdf", "page": 1, "bbox": [1, 2, 3, 4], "search_unit_id": "su-1"},
        "citation_locator_valid": True,
        "answer_claims_supported": True,
        "file_identity_lane": {
            "lane": "pdf_file_identity",
            "blocker": "stable_identity_required",
            "merged_with_content_evidence": False,
            "filename_only_identity_accepted": False,
        },
        "no_file_identity_lane_used_as_content_evidence": lane != "pdf_file_identity",
        "no_filename_only_identity_acceptance": True,
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
