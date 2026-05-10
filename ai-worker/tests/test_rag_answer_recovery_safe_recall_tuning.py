from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONFIG = ROOT / "eval" / "configs" / "answer_recovery_safe_recall_tuning.yaml"
REPORT_DIR = ROOT / "eval" / "reports" / "rag-ingestion"


def test_safe_recall_tuning_rejects_false_support_and_pdf_file_identity_relaxation():
    module = _load_safe_recall_script()
    config = module.load_config(CONFIG)
    baseline, rows = _baseline(module, config)
    unsafe = {
        "name": "unsafe_pdf_file_token_overlap_support",
        "base_policy": "calibrated_identity_exact_v1",
        "enabled_lanes": ["PDF_FILE_LOOKUP"],
        "pdf_file_identity_exactness_rule": "filename_token_overlap_allowed",
        "filename_token_overlap_support": True,
        "hidden_xlsx_blocking": "enabled",
        "diagnostic_only_support": "disabled",
        "max_loop_iterations": 2,
        "max_query_rewrites": 3,
    }

    metrics = module.variant_metrics(rows, unsafe, baseline_counts=baseline)
    reasons = module.rejection_reasons(metrics, unsafe, baseline, config)

    assert metrics["counts"]["wrongly_supported_count"] > 0
    assert "wrongly_supported_count > 0" in reasons
    assert "weakens PDF FILE identity exactness" in reasons
    assert "allows filename token overlap support" in reasons


def test_safe_recall_tuning_rejects_hidden_xlsx_and_diagnostic_only_support():
    module = _load_safe_recall_script()
    config = module.load_config(CONFIG)
    baseline, rows = _baseline(module, config)
    hidden_variant = {
        "name": "unsafe_hidden_xlsx_support",
        "base_policy": "calibrated_identity_exact_v1",
        "enabled_lanes": ["XLSX"],
        "pdf_file_identity_exactness_rule": "exact_or_canonical_identity_required",
        "hidden_xlsx_blocking": "disabled",
        "diagnostic_only_support": "disabled",
        "max_loop_iterations": 2,
        "max_query_rewrites": 3,
    }
    diagnostic_variant = {
        "name": "unsafe_diagnostic_only_support",
        "base_policy": "calibrated_identity_exact_v1",
        "enabled_lanes": ["OCR_SHADOW", "IDP_SHADOW", "MULTIMODAL_SHADOW"],
        "pdf_file_identity_exactness_rule": "exact_or_canonical_identity_required",
        "hidden_xlsx_blocking": "enabled",
        "diagnostic_only_support": "enabled",
        "max_loop_iterations": 2,
        "max_query_rewrites": 3,
    }

    hidden_metrics = module.variant_metrics(rows, hidden_variant, baseline_counts=baseline)
    hidden_reasons = module.rejection_reasons(hidden_metrics, hidden_variant, baseline, config)
    diagnostic_metrics = module.variant_metrics(rows, diagnostic_variant, baseline_counts=baseline)
    diagnostic_reasons = module.rejection_reasons(diagnostic_metrics, diagnostic_variant, baseline, config)

    assert hidden_metrics["counts"]["hidden_xlsx_surface_attempt_count"] < baseline["counts"]["hidden_xlsx_surface_attempt_count"]
    assert "weakens hidden XLSX blocking" in hidden_reasons
    assert diagnostic_metrics["counts"]["diagnostic_only_evidence_blocked_count"] < baseline["counts"]["diagnostic_only_evidence_blocked_count"]
    assert "allows diagnostic-only evidence as support" in diagnostic_reasons
    assert "weakens diagnostic-only evidence blocking" in diagnostic_reasons


def test_safe_recall_selected_policy_remains_diagnostic_only_and_non_mutating():
    module = _load_safe_recall_script()
    config = module.load_config(CONFIG)
    report = module.run_safe_recall_tuning(config=config, config_path=CONFIG, report_dir=REPORT_DIR)["tuning_report"]
    selected = report["selected_policy"]

    assert report["selection_excluded_frozen_gold_row_count"] == 12
    assert report["selection_baseline_counts"]["total_evaluated"] == 173
    assert report["baseline_counts"]["total_evaluated"] == 185
    assert selected["diagnostic_only"] is True
    assert selected["production_promotion_ready"] is False
    assert selected["official_answer_denominator_ready"] is False
    assert selected["counts"]["wrongly_supported_count"] == 0
    assert selected["policy"]["max_loop_iterations"] == 2
    assert selected["policy"]["max_query_rewrites"] == 3
    assert selected["guardrails"]["production_index_mutation"] is False
    assert selected["guardrails"]["broad_indexing"] is False
    assert selected["guardrails"]["native_pdf_text_outranks_ocr_fallback"] is True
    assert selected["guardrails"]["pdf_file_lookup_success_claims"] == {
        "content": False,
        "page": False,
        "bbox": False,
        "table": False,
        "row": False,
        "column": False,
        "value": False,
    }


def test_safe_recall_variants_do_not_simulate_support_without_post_expansion_evidence():
    module = _load_safe_recall_script()
    row = _minimal_case(
        case_id="synthetic_text_positive_missing_context",
        lane="TEXT",
        expected=True,
        status="UNSUPPORTED",
        failure_type="INSUFFICIENT_EVIDENCE",
    )
    variant = {
        "name": "text_adjacent_context_v1",
        "base_policy": "calibrated_identity_exact_v1",
        "enabled_lanes": ["TEXT"],
        "text_context_expansion": "adjacent_chunk_or_section_once",
        "pdf_file_identity_exactness_rule": "exact_or_canonical_identity_required",
        "hidden_xlsx_blocking": "enabled",
        "diagnostic_only_support": "disabled",
        "max_loop_iterations": 2,
        "max_query_rewrites": 3,
    }

    metrics = module.variant_metrics([row], variant, baseline_counts=None)

    assert metrics["safe_context_opportunity_case_ids"] == ["synthetic_text_positive_missing_context"]
    assert metrics["safe_context_recovered_case_ids"] == []
    assert metrics["counts"]["recovered_after_loop"] == 0
    assert metrics["lane_breakdown"]["TEXT"]["supported_after_recovery"] == 0


def test_safe_recall_source_guardrail_blocks_loop_and_rewrite_over_cap():
    module = _load_safe_recall_script()
    config = module.load_config(CONFIG)
    row = _minimal_case(
        case_id="synthetic_loop_over_cap",
        lane="TEXT",
        expected=False,
        status="UNSUPPORTED",
        failure_type="INSUFFICIENT_EVIDENCE",
    )
    row["loop_result"] = {"loop_iterations": 3, "query_rewrite_count": 4}

    violations = module.source_guardrail_violations([row], config)

    assert {"case_id": "synthetic_loop_over_cap", "field": "loop_iterations", "observed": 3, "cap": 2} in violations
    assert {"case_id": "synthetic_loop_over_cap", "field": "query_rewrite_count", "observed": 4, "cap": 3} in violations


def test_safe_recall_config_respects_xlsx_strict_wrapper_and_loop_caps():
    module = _load_safe_recall_script()
    config = module.load_config(CONFIG)
    variants = {row["name"]: row for row in config["variants"]}

    assert config["allowed_tuning_knobs"]["max_loop_iterations"] == 2
    assert config["allowed_tuning_knobs"]["max_query_rewrites"] == 3
    assert variants["xlsx_strict_context_v1"]["xlsx_strict_wrapper_only"] is True
    assert variants["xlsx_strict_context_v1"]["hidden_xlsx_blocking"] == "enabled"
    assert variants["pdf_content_native_page_context_v1"]["pdf_content_native_text_only"] is True
    assert module.validate_config(config) == []

    unsafe_config = copy.deepcopy(config)
    unsafe_config["variants"][0]["max_loop_iterations"] = 3
    assert "max loop iterations exceeds 2" in module.validate_config(unsafe_config)


def test_safe_recall_script_emits_reports_and_preserves_registry_diff():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "rag_answer_recovery_safe_recall_tuning.py"),
            "--config",
            str(CONFIG),
            "--artifact-profile",
            "debug",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "official_answer_denominator_ready" in result.stdout
    report = json.loads((REPORT_DIR / "answer_recovery_safe_recall_tuning_report.json").read_text(encoding="utf-8"))
    selected = json.loads((REPORT_DIR / "answer_recovery_safe_recall_selected_policy.json").read_text(encoding="utf-8"))
    assert report["decision"]["production_promotion_ready"] is False
    assert report["decision"]["official_answer_denominator_ready"] is False
    assert report["official_denominator_registry_diff_proof"]["diff_empty"] is True
    assert report["official_denominator_registry_diff_proof"]["staged_diff_empty"] is True
    assert report["official_denominator_registry_diff_proof"]["unstaged_diff_empty"] is True
    assert " --quiet -- " in report["official_denominator_registry_diff_proof"]["command"]
    assert report["official_denominator_registry_diff_proof"]["diff_stdout_bytes"] == 0
    assert selected["counts"]["wrongly_supported_count"] == 0
    diff = subprocess.run(
        ["git", "diff", "--quiet", "--", "ai-worker/eval/eval_queries/official_denominator_registry.json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    assert diff.returncode == 0


def _baseline(module, config):
    rows = module.read_json(module.resolve_path(config["diagnostic_inputs"]["answer_sufficiency_expanded_report"]))[
        "case_results"
    ]
    baseline = module.variant_metrics(rows, module.baseline_variant_from_config(config), baseline_counts=None)
    return baseline, rows


def _minimal_case(
    *,
    case_id: str,
    lane: str,
    expected: bool,
    status: str,
    failure_type: str,
) -> dict:
    decision = {
        "allowed_lanes": [lane],
        "best_trust_tier": "NATIVE_TEXT_HIGH",
        "blocked_lanes": [],
        "citation_coverage": 0.0,
        "cited_evidence_count": 0,
        "diagnostic_reason": "synthetic",
        "evidence_count": 0,
        "failure_type": failure_type,
        "official_support": False,
        "recommended_recovery_actions": [],
        "required_followup_question": "",
        "sufficiency_status": status,
        "support_score": 0.0,
    }
    return {
        "after_decision": dict(decision),
        "before_decision": dict(decision),
        "case_id": case_id,
        "case_type": "synthetic",
        "diagnostic_policy": {
            "broad_indexing": False,
            "official_answer_denominator_opened": False,
            "official_denominator_registry_changed": False,
            "production_index_mutation": False,
        },
        "expected_official_support_allowed": expected,
        "lane": lane,
        "loop_result": None,
        "query": "synthetic query",
        "route": {
            "action": "ADJACENT_CONTEXT_EXPANSION",
            "clarification_question": "",
            "diagnostic_reason": "synthetic",
            "recovery_actions": [],
            "target_lane": lane,
        },
        "source_artifact": "synthetic_non_frozen.csv",
    }


def _load_safe_recall_script():
    module_path = ROOT / "scripts" / "rag_answer_recovery_safe_recall_tuning.py"
    spec = importlib.util.spec_from_file_location("rag_answer_recovery_safe_recall_tuning_for_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
