from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONFIG = ROOT / "eval" / "configs" / "answer_recovery_safe_recall_missed_row_triage.yaml"
REPORT_DIR = ROOT / "eval" / "reports" / "rag-ingestion"


def test_missed_row_triage_excludes_frozen_gold_from_selection_and_training():
    module = _load_triage_script()
    config = module.load_config(CONFIG)
    report = module.run_triage(config=config, config_path=CONFIG)

    assert report["selection_policy"]["frozen_gold_used_for_selection"] is False
    assert report["selection_policy"]["frozen_gold_used_for_training"] is False
    assert report["selection_policy"]["selection_row_count"] == 173
    assert report["selection_policy"]["excluded_frozen_gold_row_count"] == 12


def test_missed_row_triage_preserves_core_guardrails():
    module = _load_triage_script()
    config = module.load_config(CONFIG)
    report = module.run_triage(config=config, config_path=CONFIG)

    assert report["decision"]["production_promotion_ready"] is False
    assert report["decision"]["official_answer_denominator_ready"] is False
    assert report["guardrail_status"]["hidden_xlsx_support_count"] == 0
    assert report["guardrail_status"]["pdf_file_content_mixing_support_count"] == 0
    assert report["guardrail_status"]["diagnostic_only_evidence_support_count"] == 0
    assert report["guardrail_status"]["pdf_file_lookup_semantics"] == "file_identity_only"
    assert report["guardrail_status"]["pdf_file_lookup_success_claims"] == {
        "content": False,
        "page": False,
        "bbox": False,
        "table": False,
        "row": False,
        "column": False,
        "value": False,
    }


def test_missed_row_triage_classifies_hidden_pdf_and_diagnostic_blocks():
    module = _load_triage_script()
    config = module.load_config(CONFIG)
    report = module.run_triage(config=config, config_path=CONFIG)
    rows = {row["row_id"]: row for row in report["rows"]}

    hidden = rows["expanded_xlsx_hidden_blocked_001"]
    assert hidden["hidden_xlsx_involved"] is True
    assert hidden["category"] == "POLICY_BLOCKED_CORRECTLY"
    assert hidden["after_status"] != "SUPPORTED"

    pdf_file = rows["expanded_pdf_file_lookup_007"]
    assert pdf_file["lane"] == "PDF_FILE_LOOKUP"
    assert pdf_file["pdf_file_identity_content_mixing_risk"] is True
    assert pdf_file["category"] == "POLICY_BLOCKED_CORRECTLY"

    ocr = rows["expanded_ocr_shadow_001"]
    assert ocr["evidence_is_diagnostic_only"] is True
    assert ocr["category"] == "DIAGNOSTIC_ONLY_DO_NOT_PROMOTE"
    assert ocr["evidence_is_production_safe"] is False


def test_missed_row_triage_report_includes_required_category_counts():
    module = _load_triage_script()
    config = module.load_config(CONFIG)
    report = module.run_triage(config=config, config_path=CONFIG)
    categories = report["counts"]["category_counts"]

    for category in module.CATEGORY_ORDER:
        assert category in categories
    assert report["counts"]["recovered_after_loop_focus_count"] == 5
    assert report["counts"]["citation_uncovered_focus_count"] == 7
    assert report["counts"]["unsupported_correctly_blocked_focus_count"] == 32
    assert categories["SAFE_RECOVERABLE_WITH_EXISTING_EVIDENCE"] == 5
    assert categories["UNKNOWN_NEEDS_MANUAL_REVIEW"] == 0


def test_missed_row_triage_unknown_rows_are_manual_review_not_promotion():
    module = _load_triage_script()
    row = _minimal_case()
    classified = module.classify_row(
        row,
        focus_groups=["CITATION_UNCOVERED"],
        trace_row={},
        missed_row={},
        selected_variant="baseline_selected_policy",
        excluded_sources=set(),
    )

    assert classified["category"] == "UNKNOWN_NEEDS_MANUAL_REVIEW"
    assert classified["human_gold_decision_required"] is True
    assert classified["evidence_is_production_safe"] is False


def test_missed_row_triage_script_emits_reports_and_preserves_registry_diff():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "rag_answer_recovery_safe_recall_missed_row_triage.py"),
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

    assert "triage_row_count" in result.stdout
    report = json.loads(
        (REPORT_DIR / "answer_recovery_safe_recall_missed_row_triage.json").read_text(encoding="utf-8")
    )
    assert report["decision"]["production_promotion_ready"] is False
    assert report["decision"]["official_answer_denominator_ready"] is False
    assert report["official_denominator_registry_diff_proof"]["diff_empty"] is True
    diff = subprocess.run(
        ["git", "diff", "--quiet", "--", "ai-worker/eval/eval_queries/official_denominator_registry.json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    assert diff.returncode == 0


def _minimal_case() -> dict:
    before = {
        "allowed_lanes": ["TEXT"],
        "best_trust_tier": "",
        "blocked_lanes": [],
        "citation_coverage": 0.0,
        "cited_evidence_count": 0,
        "diagnostic_reason": "synthetic",
        "evidence_count": 0,
        "failure_type": "",
        "official_support": False,
        "recommended_recovery_actions": [],
        "required_followup_question": "",
        "sufficiency_status": "NEEDS_RECOVERY",
        "support_score": 0.0,
    }
    after = dict(before)
    after["sufficiency_status"] = "NEEDS_RECOVERY"
    return {
        "after_decision": after,
        "before_decision": before,
        "case_id": "synthetic_unknown",
        "case_type": "synthetic_unknown",
        "diagnostic_policy": {
            "broad_indexing": False,
            "official_answer_denominator_opened": False,
            "official_denominator_registry_changed": False,
            "production_index_mutation": False,
        },
        "expected_official_support_allowed": True,
        "lane": "TEXT",
        "loop_result": None,
        "query": "synthetic unknown",
        "route": {
            "action": "ADJACENT_CONTEXT_EXPANSION",
            "clarification_question": "",
            "diagnostic_reason": "synthetic",
            "recovery_actions": [],
            "target_lane": "TEXT",
        },
        "source_artifact": "synthetic_non_frozen.csv",
    }


def _load_triage_script():
    module_path = ROOT / "scripts" / "rag_answer_recovery_safe_recall_missed_row_triage.py"
    spec = importlib.util.spec_from_file_location("rag_answer_recovery_safe_recall_missed_row_triage_for_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
