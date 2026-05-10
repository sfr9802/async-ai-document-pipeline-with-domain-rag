from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONFIG = ROOT / "eval" / "configs" / "answer_recovery_narrow_silver_calibration.yaml"
REPORT_DIR = ROOT / "eval" / "reports" / "rag-ingestion"


def test_narrow_calibration_rejects_unsafe_variants():
    module = _load_calibration_script()
    config = module.load_config(CONFIG)
    report = module.run_calibration(config=config, config_path=CONFIG, report_dir=REPORT_DIR)
    variants = {row["variant_name"]: row for row in report["variants"]}

    assert variants["unsafe_pdf_file_token_overlap_support"]["accepted"] is False
    assert "wrongly_supported_count > 0" in variants["unsafe_pdf_file_token_overlap_support"]["rejection_reasons"]
    assert "weakens PDF FILE identity exactness" in variants["unsafe_pdf_file_token_overlap_support"]["rejection_reasons"]
    assert variants["unsafe_hidden_xlsx_support"]["accepted"] is False
    assert "weakens hidden XLSX blocking" in variants["unsafe_hidden_xlsx_support"]["rejection_reasons"]
    assert variants["unsafe_diagnostic_only_support"]["accepted"] is False
    assert "weakens diagnostic-only evidence blocking" in variants["unsafe_diagnostic_only_support"]["rejection_reasons"]


def test_narrow_calibration_selected_policy_remains_diagnostic_only():
    module = _load_calibration_script()
    config = module.load_config(CONFIG)
    report = module.run_calibration(config=config, config_path=CONFIG, report_dir=REPORT_DIR)
    selected = report["selected_policy"]

    assert selected["variant_name"] == "calibrated_identity_exact_v1"
    assert selected["diagnostic_only"] is True
    assert selected["production_promotion_ready"] is False
    assert selected["official_answer_denominator_ready"] is False
    assert selected["counts"]["wrongly_supported_count"] == 0
    assert selected["policy"]["max_loop_iterations"] == 2
    assert selected["policy"]["max_query_rewrites"] == 3
    assert selected["guardrails"]["production_index_mutation"] is False
    assert selected["guardrails"]["broad_indexing"] is False
    assert selected["guardrails"]["pdf_file_lookup_success_claims"] == {
        "content": False,
        "page": False,
        "bbox": False,
        "table": False,
        "row": False,
        "column": False,
        "value": False,
    }


def test_narrow_calibration_config_excludes_frozen_gold_from_selection():
    module = _load_calibration_script()
    config = module.load_config(CONFIG)

    assert config["excluded_frozen_gold_ids"]["use_for_selection"] is False
    assert config["excluded_frozen_gold_ids"]["use_for_training"] is False
    assert len(config["excluded_frozen_gold_ids"]["ids"]) > 0
    assert config["blocked_knobs"]["frozen_gold_selection_or_training"] is True
    assert config["blocked_knobs"]["official_denominator_changes"] is True
    assert config["blocked_knobs"]["broad_indexing"] is True


def test_narrow_calibration_script_emits_reports_and_preserves_registry(tmp_path: Path):
    registry = ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"
    registry_before = registry.read_text(encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "rag_answer_recovery_narrow_calibration.py"),
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

    assert "true_for_narrow_silver_only_calibration" in result.stdout
    report = json.loads((REPORT_DIR / "answer_recovery_narrow_calibration_report.json").read_text(encoding="utf-8"))
    selected = json.loads((REPORT_DIR / "answer_recovery_narrow_calibration_selected_policy.json").read_text(encoding="utf-8"))
    assert report["decision"]["production_promotion_ready"] is False
    assert report["decision"]["official_answer_denominator_ready"] is False
    assert selected["counts"]["wrongly_supported_count"] == 0
    assert registry.read_text(encoding="utf-8") == registry_before


def _load_calibration_script():
    module_path = ROOT / "scripts" / "rag_answer_recovery_narrow_calibration.py"
    spec = importlib.util.spec_from_file_location("rag_answer_recovery_narrow_calibration_for_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
