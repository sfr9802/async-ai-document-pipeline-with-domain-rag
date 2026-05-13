from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "route_label_review_applied.py"


def load_module():
    spec = importlib.util.spec_from_file_location("route_label_review_applied", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_korean_route_memos_are_normalized_into_required_columns(tmp_path: Path):
    module = load_module()
    registry = write_registry(tmp_path)
    applied = module.build_applied_artifacts(
        route_pack=fixture_route_pack(),
        fallback_pack=fixture_fallback_pack(),
        route_pack_path=tmp_path / "route_pack.json",
        fallback_pack_path=tmp_path / "fallback_pack.json",
        official_denominator_registry=registry,
    )["route_gold_label_review_applied"]

    rows = keyed(applied["applied_human_review_rows"])
    assert applied["counts"]["applied_human_review_rows"] == 5
    assert applied["route_metrics_official"] is False
    assert applied["reviewed_route_metrics_diagnostic"]["official_metric"] is False
    assert rows["route_review_text_namuwiki_animation_001"]["reviewed_primary_route"] == "text_namuwiki_animation"
    assert rows["route_review_text_namuwiki_animation_001"]["reviewed_candidate_routes"] == [
        "text_namuwiki_animation"
    ]
    assert rows["route_review_text_namuwiki_animation_001"]["wrong_route_label"] == "correct_route"
    assert rows["route_review_text_namuwiki_animation_001"]["reviewer"] == "user_korean_memo"
    assert rows["route_review_text_namuwiki_animation_001"]["source_user_memo_ko"] == "올바른 라우트"

    xlsx = rows["route_review_xlsx_business_structured_001"]
    assert xlsx["fallback_allowed"] is False
    assert xlsx["fallback_expected_route"] is None
    assert xlsx["fallback_outcome_label"] == "fallback_to_user_clarification"
    assert xlsx["wrong_route_label"] == "correct_track_but_query_under_specified"
    assert xlsx["final_action"] == "clarification_required"
    assert "PDF" in xlsx["notes"]
    assert "success" in xlsx["notes"]


def test_fallback_memos_prevent_silent_cross_track_success(tmp_path: Path):
    module = load_module()
    registry = write_registry(tmp_path)
    applied = module.build_applied_artifacts(
        route_pack=fixture_route_pack(),
        fallback_pack=fixture_fallback_pack(),
        route_pack_path=tmp_path / "route_pack.json",
        fallback_pack_path=tmp_path / "fallback_pack.json",
        official_denominator_registry=registry,
    )["fallback_outcome_label_review_applied"]

    rows = keyed(applied["applied_human_review_rows"])
    assert applied["counts"]["applied_human_review_rows"] == 3
    assert applied["fallback_metrics_official"] is False
    assert applied["reviewed_fallback_metrics_diagnostic"]["route_retrieval_fallback_success_count"] == 0
    assert applied["reviewed_fallback_metrics_diagnostic"]["cross_track_fallback_success_count"] == 0

    xlsx = rows["fallback_review_xlsx_to_pdf_001"]
    assert xlsx["reviewed_primary_route"] == "xlsx_business_structured"
    assert xlsx["reviewed_candidate_routes"] == ["xlsx_business_structured"]
    assert xlsx["fallback_allowed"] is False
    assert xlsx["fallback_expected_route"] is None
    assert xlsx["fallback_outcome_label"] == "fallback_to_user_clarification"
    assert xlsx["wrong_route_label"] == "pdf_fallback_not_success"
    assert xlsx["original_prefilled_fallback_expected_route"] == "pdf_business_ocr_mm"
    assert xlsx["clarification_fallback_allowed"] is True

    text_pdf = rows["fallback_review_text_pdf_ambiguous_001"]
    assert text_pdf["fallback_allowed"] is False
    assert text_pdf["fallback_expected_route"] is None
    assert text_pdf["fallback_outcome_label"] == "fallback_to_user_clarification"
    assert text_pdf["wrong_route_label"] == "ambiguous_requires_user_clarification"


def test_pdf_content_and_file_identity_lanes_remain_separate(tmp_path: Path):
    module = load_module()
    registry = write_registry(tmp_path)
    artifacts = module.build_applied_artifacts(
        route_pack=fixture_route_pack(),
        fallback_pack=fixture_fallback_pack(),
        route_pack_path=tmp_path / "route_pack.json",
        fallback_pack_path=tmp_path / "fallback_pack.json",
        official_denominator_registry=registry,
    )
    route_rows = keyed(artifacts["route_gold_label_review_applied"]["applied_human_review_rows"])
    fallback_rows = keyed(artifacts["fallback_outcome_label_review_applied"]["applied_human_review_rows"])

    assert route_rows["route_review_pdf_content_evidence_001"]["expected_evidence_lane"] == "pdf_content_evidence"
    assert route_rows["route_review_pdf_file_identity_001"]["expected_evidence_lane"] == "pdf_file_identity"
    assert fallback_rows["fallback_review_pdf_content_file_identity_lane_001"]["expected_evidence_lane"] == (
        "pdf_content_evidence"
    )
    assert fallback_rows["fallback_review_pdf_content_file_identity_lane_001"]["fallback_allowed"] is True
    assert fallback_rows["fallback_review_pdf_content_file_identity_lane_001"]["pdf_lane_separation_required"] is True
    assert fallback_rows["fallback_review_pdf_content_file_identity_lane_001"]["fallback_outcome_label"] == (
        "fallback_deferred_until_ocr_parse_keywords"
    )
    assert artifacts["route_gold_label_review_applied"]["guardrails"][
        "pdf_content_and_file_identity_aggregated"
    ] is False


def test_guardrails_and_hidden_xlsx_surface_remain_closed(tmp_path: Path):
    module = load_module()
    registry = write_registry(tmp_path)
    before = registry.read_text(encoding="utf-8")
    artifacts = module.build_applied_artifacts(
        route_pack=fixture_route_pack(),
        fallback_pack=fixture_fallback_pack(),
        route_pack_path=tmp_path / "route_pack.json",
        fallback_pack_path=tmp_path / "fallback_pack.json",
        official_denominator_registry=registry,
    )
    serialized = json.dumps(artifacts, ensure_ascii=False)

    assert registry.read_text(encoding="utf-8") == before
    for artifact in artifacts.values():
        assert artifact["diagnostic_only"] is True
        assert artifact["counts"]["official_metric_input_rows"] == 0
        assert artifact["counts"]["codex_diagnostic_only_rows_unchanged"] == 4
        assert artifact["original_review_pack_modified"] is False
        assert artifact["guardrails"]["official_denominator_registry_changed"] is False
        assert artifact["guardrails"]["production_namespace_mutated"] is False
        assert artifact["guardrails"]["production_vector_index_mutated"] is False
        assert artifact["guardrails"]["production_vector_written"] is False
        assert artifact["guardrails"]["diagnostic_only_row_promoted"] is False
        assert artifact["guardrails"]["hidden_xlsx_content_exposed"] is False
        assert artifact["guardrails"]["policy_excluded_rows_counted_as_retrieval_failures"] is False
    assert "hidden cell value" not in serialized
    assert "xlsx_hidden_source_payload" not in serialized


def test_main_writes_applied_artifacts_without_registry_mutation(tmp_path: Path):
    module = load_module()
    route_pack_path = tmp_path / "route_pack.json"
    fallback_pack_path = tmp_path / "fallback_pack.json"
    route_pack_path.write_text(json.dumps(fixture_route_pack(), ensure_ascii=False) + "\n", encoding="utf-8")
    fallback_pack_path.write_text(json.dumps(fixture_fallback_pack(), ensure_ascii=False) + "\n", encoding="utf-8")
    registry = write_registry(tmp_path)
    before = registry.read_text(encoding="utf-8")

    result = module.main(
        [
            "--route-pack-json",
            str(route_pack_path),
            "--fallback-pack-json",
            str(fallback_pack_path),
            "--official-denominator-registry",
            str(registry),
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert (tmp_path / "route_gold_label_review_applied_v1.json").exists()
    assert (tmp_path / "route_gold_label_review_applied_v1.md").exists()
    assert (tmp_path / "fallback_outcome_label_review_applied_v1.json").exists()
    assert (tmp_path / "fallback_outcome_label_review_applied_v1.md").exists()
    assert registry.read_text(encoding="utf-8") == before


def write_registry(tmp_path: Path) -> Path:
    registry = tmp_path / "official_denominator_registry.json"
    registry.write_text(json.dumps({"schema_version": "official_denominator_registry_v1"}) + "\n", encoding="utf-8")
    return registry


def keyed(rows: list[dict]) -> dict[str, dict]:
    return {row["query_id"]: row for row in rows}


def fixture_route_pack() -> dict:
    return {
        "schema_version": "route_fallback_label_review_pack_v1",
        "pack_type": "route_gold_label_review",
        "diagnostic_only": True,
        "route_metrics_official": False,
        "required_columns": [
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
        ],
        "human_review_rows": [
            route_row("route_review_text_namuwiki_animation_001", "애니 작품 내용과 등장인물 설명을 찾아줘"),
            route_row("route_review_xlsx_business_structured_001", "합계?", fallback_expected_route="pdf_business_ocr_mm"),
            route_row("route_review_pdf_content_evidence_001", "PDF 본문 근거를 찾아줘"),
            route_row("route_review_pdf_file_identity_001", "안정적인 문서 식별자가 있는 PDF 파일을 찾아줘"),
            route_row("route_review_ambiguous_multi_route_001", "이 자료에서 확인해줘"),
        ],
        "codex_diagnostic_only_rows": [auto_row(f"route_auto_{index}") for index in range(4)],
        "guardrails": guardrails(),
    }


def fixture_fallback_pack() -> dict:
    return {
        "schema_version": "route_fallback_label_review_pack_v1",
        "pack_type": "fallback_outcome_label_review",
        "diagnostic_only": True,
        "fallback_metrics_official": False,
        "required_columns": fixture_route_pack()["required_columns"],
        "human_review_rows": [
            route_row("fallback_review_xlsx_to_pdf_001", "합계?", fallback_expected_route="pdf_business_ocr_mm"),
            route_row("fallback_review_text_pdf_ambiguous_001", "본문 내용을 찾아줘"),
            route_row(
                "fallback_review_pdf_content_file_identity_lane_001",
                "PDF에서 이 문서와 본문 근거를 확인해줘",
                fallback_expected_route="pdf_business_ocr_mm",
            ),
        ],
        "codex_diagnostic_only_rows": [auto_row(f"fallback_auto_{index}") for index in range(4)],
        "bounded_fallback_policy": {
            "maximum_fallback_attempts": 1,
            "allow_unscoped": False,
            "production_mutation": False,
        },
        "guardrails": guardrails(),
    }


def route_row(query_id: str, safe_query_text: str, *, fallback_expected_route: str = "") -> dict:
    return {
        "query_id": query_id,
        "safe_query_text": safe_query_text,
        "source_type_hint": "",
        "reviewed_primary_route": "",
        "reviewed_candidate_routes": [],
        "expected_evidence_lane": "",
        "fallback_allowed": "",
        "fallback_expected_route": fallback_expected_route,
        "fallback_outcome_label": "",
        "wrong_route_label": "",
        "denominator_scope": "",
        "reviewer": "",
        "reviewed_time": "",
        "notes": "",
        "diagnostic_only": True,
        "official_metric_input": False,
        "production_namespace_mutation": False,
        "production_vector_write": False,
    }


def auto_row(query_id: str) -> dict:
    return {
        "query_id": query_id,
        "safe_query_text": "[redacted xlsx excluded-row guard probe]" if query_id.endswith("1") else "auto row",
        "source_type_hint": "guard",
        "reviewed_primary_route": "policy_blocked",
        "reviewed_candidate_routes": [],
        "expected_evidence_lane": "none",
        "fallback_allowed": False,
        "fallback_expected_route": "",
        "fallback_outcome_label": "fallback_blocked_by_policy",
        "wrong_route_label": "not_official_metric_input",
        "denominator_scope": "reviewed_route_label_diagnostic_only",
        "reviewer": "",
        "reviewed_time": "",
        "notes": "",
        "diagnostic_only": True,
        "official_metric_input": False,
    }


def guardrails() -> dict:
    return {
        "official_denominator_registry_changed": False,
        "official_denominator_opened_or_frozen": False,
        "production_namespace_mutated": False,
        "production_vector_index_mutated": False,
        "production_vector_written": False,
        "diagnostic_only_row_promoted": False,
        "pdf_content_and_file_identity_aggregated": False,
        "hidden_xlsx_content_exposed": False,
        "policy_excluded_rows_counted_as_retrieval_failures": False,
    }
