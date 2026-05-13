from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_hyperparameter_tuning_readiness_plan.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_hyperparameter_tuning_readiness_plan_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_readiness_plan_is_report_only_and_keeps_official_metrics_closed(tmp_path: Path):
    module = load_module()

    plan = module.run_plan(
        output_report=tmp_path / "hyperparameter_tuning_readiness_plan.json",
        output_md=tmp_path / "hyperparameter_tuning_readiness_plan.md",
    )

    assert plan["status"] == "REPORT_ONLY_READY"
    assert plan["tuning_run_started"] is False
    assert plan["official_metrics_closed"] is True
    assert plan["cross_track_average_optimization_allowed"] is False
    assert plan["current_text_66_rows_policy"] == "diagnostic_dev_not_final_holdout"
    assert plan["guardrails"]["official_denominator_registry_mutation"] is False
    assert plan["guardrails"]["production_namespace_vector_index_mutation"] is False
    assert plan["guardrails"]["candidate_artifact_mutation"] is False
    assert plan["guardrails"]["official_metric_input_rows"] == 0
    assert plan["guardrails"]["promotion_evidence"] is False
    assert plan["validation"]["ok"] is True
    assert set(plan["track_policies"]) == {
        "text_namu_v2_1",
        "xlsx_business_structured",
        "pdf_business_ocr_mm",
    }


def test_readiness_plan_has_track_specific_dev_holdout_and_allowed_parameters():
    module = load_module()

    plan = module.build_plan()

    assert plan["track_policies"]["text_namu_v2_1"]["dev_policy"] == "diagnostic_dev_only"
    assert plan["track_policies"]["text_namu_v2_1"]["holdout_policy"] == "not_final_holdout"
    assert "rewrite_formatter_mode" in plan["track_policies"]["text_namu_v2_1"]["allowed_parameters"]
    assert plan["track_policies"]["xlsx_business_structured"]["holdout_policy"] == "strict_silver_not_official_holdout"
    assert "structured_evidence_field_subset" in plan["track_policies"]["xlsx_business_structured"]["allowed_parameters"]
    assert plan["track_policies"]["pdf_business_ocr_mm"]["dev_policy"] == "readiness_artifact_only"
    assert plan["track_policies"]["pdf_business_ocr_mm"]["allowed_parameters"] == [
        "layout_metadata_completeness_threshold",
        "citation_locator_required_fields",
        "stable_identity_policy_variant_report_only",
    ]


def test_plan_fails_closed_if_a_guardrail_requests_mutation():
    module = load_module()

    plan = module.build_plan(
        guardrail_overrides={
            "official_denominator_registry_mutation": True,
            "production_namespace_vector_index_mutation": True,
        }
    )

    assert plan["status"] == "FAILED_GUARDRAIL"
    assert "official_denominator_registry_mutation must remain false" in plan["validation"]["errors"]
    assert "production_namespace_vector_index_mutation must remain false" in plan["validation"]["errors"]
