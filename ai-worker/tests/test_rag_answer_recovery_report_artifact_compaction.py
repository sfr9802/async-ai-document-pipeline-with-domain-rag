from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
REPORT_DIR = ROOT / "eval" / "reports" / "rag-ingestion"
REGISTRY = ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"


def test_compact_profile_emits_only_phase_reports_and_cleans_legacy_artifacts(tmp_path: Path):
    module = _load_compaction_script()
    bundle = _write_config_bundle(tmp_path, artifact_profile="compact")
    for filename in module.report_artifacts.COMPACT_CLEANUP_FILENAMES:
        (bundle["report_dir"] / filename).write_text("legacy\n", encoding="utf-8")
    registry_before = REGISTRY.read_bytes()

    result = module.run_tuning_report(
        config_path=bundle["embedding_config"],
        safe_recall_config_path=bundle["safe_config"],
        missed_row_triage_config_path=bundle["triage_config"],
        report_dir=bundle["report_dir"],
        top_k=10,
        reporting_overrides={"artifact_profile": "compact"},
        backend_contract_kwargs={"probe_embedding_allowed_override": False},
    )

    emitted = _generated_report_names(bundle["report_dir"])
    assert emitted == {"answer_recovery_tuning_report.md", "answer_recovery_tuning_report.json"}
    assert result["report"]["debug_artifacts_emitted"] is False
    assert result["report"]["artifact_compaction"]["cleanup_status"] == "CLEANED"
    assert not result["report"]["artifact_compaction"]["tracked_legacy_artifacts_detected"]
    assert REGISTRY.read_bytes() == registry_before


def test_compact_reports_have_required_sections_and_guardrails(tmp_path: Path):
    module = _load_compaction_script()
    bundle = _write_config_bundle(tmp_path, artifact_profile="compact")

    result = module.run_tuning_report(
        config_path=bundle["embedding_config"],
        safe_recall_config_path=bundle["safe_config"],
        missed_row_triage_config_path=bundle["triage_config"],
        report_dir=bundle["report_dir"],
        top_k=10,
        reporting_overrides={"artifact_profile": "compact"},
        backend_contract_kwargs={"probe_embedding_allowed_override": False},
    )
    report = json.loads((bundle["report_dir"] / "answer_recovery_tuning_report.json").read_text(encoding="utf-8"))
    md = (bundle["report_dir"] / "answer_recovery_tuning_report.md").read_text(encoding="utf-8")

    assert report == result["report"]
    for section in (
        "calibration",
        "missed_recovery",
        "triage",
        "embedding_backend",
        "embedding_readiness",
        "existing_embedding_retrieval_probe",
        "retrieval_probe",
        "guardrails",
        "verification",
    ):
        assert section in report
    for heading in (
        "## Status",
        "## Calibration Summary",
        "## Missed / Blocked Recovery Summary",
        "## Triage Consolidation",
        "## Embedding Backend Summary",
        "## Embedding Readiness Summary",
        "## Existing Embedding Retrieval Probe Summary",
        "## Guardrails",
        "## Verification",
    ):
        assert heading in md
    assert report["production_promotion_ready"] is False
    assert report["official_answer_denominator_ready"] is False
    assert report["guardrails"]["production_index_mutation"] is False
    assert report["guardrails"]["vector_write_attempted"] is False
    assert report["embedding_backend"]["backend_embedding_model"] == "BAAI/bge-m3"
    assert report["triage"]["category_counts"]["SAFE_RECOVERABLE_WITH_EXISTING_EVIDENCE"] == 5
    assert report["triage"]["category_counts"]["GOLD_POLICY_REQUIRED"] == 6
    assert report["triage"]["row_groups"]["promotion_candidate"] == []
    assert len(report["triage"]["row_groups"]["safe_recoverable_report_only"]) == 5
    assert len(report["triage"]["gold_policy_required_user_review"]) == 6
    assert report["triage"]["frozen_gold_sourced_excluded_count"] == 12
    assert report["triage"]["frozen_gold_used_for_selection"] is False
    assert report["triage"]["frozen_gold_used_for_training"] is False
    assert report["verification"]["official_denominator_registry_json_diff_status"] == "unchanged"
    assert report["verification"]["official_denominator_registry_json_cached_diff_status"] == "unchanged"


def test_compact_reports_do_not_include_raw_row_level_content(tmp_path: Path):
    module = _load_compaction_script()
    bundle = _write_config_bundle(tmp_path, artifact_profile="compact")

    module.run_tuning_report(
        config_path=bundle["embedding_config"],
        safe_recall_config_path=bundle["safe_config"],
        missed_row_triage_config_path=bundle["triage_config"],
        report_dir=bundle["report_dir"],
        top_k=10,
        reporting_overrides={"artifact_profile": "compact"},
        backend_contract_kwargs={"probe_embedding_allowed_override": False},
    )
    compact_text = "\n".join(
        [
            (bundle["report_dir"] / "answer_recovery_tuning_report.json").read_text(encoding="utf-8"),
            (bundle["report_dir"] / "answer_recovery_tuning_report.md").read_text(encoding="utf-8"),
        ]
    )

    forbidden = (
        "case_results",
        "expected_answer_text",
        "must_contain_terms",
        "answerPreview",
        "citation_text",
        "raw_eval_evidence_text",
        "hidden_xlsx_content",
        "pdf_content_snippet",
        "diagnostic_only_evidence_text",
    )
    assert all(fragment not in compact_text for fragment in forbidden)


def test_debug_profile_still_emits_legacy_detailed_artifacts(tmp_path: Path):
    module = _load_compaction_script()
    bundle = _write_config_bundle(tmp_path, artifact_profile="debug")

    result = module.run_tuning_report(
        config_path=bundle["embedding_config"],
        safe_recall_config_path=bundle["safe_config"],
        missed_row_triage_config_path=bundle["triage_config"],
        report_dir=bundle["report_dir"],
        top_k=10,
        reporting_overrides={"artifact_profile": "debug"},
        backend_contract_kwargs={"probe_embedding_allowed_override": False},
    )
    emitted = _generated_report_names(bundle["report_dir"])

    assert result["report"]["debug_artifacts_emitted"] is True
    assert "answer_recovery_tuning_report.md" in emitted
    assert "answer_recovery_tuning_report.json" in emitted
    assert "answer_recovery_embedding_readiness.md" in emitted
    assert "answer_recovery_embedding_readiness.json" in emitted
    assert "answer_recovery_embedding_readiness.csv" in emitted
    assert "answer_recovery_embedding_backfill_manifest.jsonl" in emitted
    assert "answer_recovery_embedding_namespace_inventory.json" in emitted
    assert "answer_recovery_embedding_backend_contract_recheck.csv" in emitted
    assert "answer_recovery_existing_embedding_retrieval_probe.csv" in emitted
    assert "answer_recovery_safe_recall_variants.csv" in emitted
    assert "answer_recovery_safe_recall_missed_row_triage.csv" in emitted


def test_failure_emits_debug_artifacts_when_enabled(tmp_path: Path):
    module = _load_compaction_script()
    bundle = _write_config_bundle(tmp_path, artifact_profile="compact")

    with pytest.raises(RuntimeError, match="forced compact-report failure"):
        module.run_tuning_report(
            config_path=bundle["embedding_config"],
            safe_recall_config_path=bundle["safe_config"],
            missed_row_triage_config_path=bundle["triage_config"],
            report_dir=bundle["report_dir"],
            top_k=10,
            reporting_overrides={
                "artifact_profile": "compact",
                "emit_debug_artifacts_on_failure": True,
            },
            backend_contract_kwargs={"probe_embedding_allowed_override": False},
            force_failure_after_stage_run=True,
        )

    emitted = _generated_report_names(bundle["report_dir"])
    assert "answer_recovery_embedding_readiness.json" in emitted
    assert "answer_recovery_embedding_backfill_manifest.jsonl" in emitted
    assert "answer_recovery_existing_embedding_retrieval_probe.csv" in emitted


def _write_config_bundle(tmp_path: Path, *, artifact_profile: str) -> dict[str, Path]:
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    (report_dir / "pdf_file_lookup_wrongly_supported_root_cause.json").write_text(
        (REPORT_DIR / "pdf_file_lookup_wrongly_supported_root_cause.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    config_dir = tmp_path / "configs"
    config_dir.mkdir()

    narrow_config = _load_yaml(ROOT / "eval" / "configs" / "answer_recovery_narrow_silver_calibration.yaml")
    safe_config = _load_yaml(ROOT / "eval" / "configs" / "answer_recovery_safe_recall_tuning.yaml")
    triage_config = _load_yaml(ROOT / "eval" / "configs" / "answer_recovery_safe_recall_missed_row_triage.yaml")
    embedding_config = _load_yaml(ROOT / "eval" / "configs" / "answer_recovery_embedding_readiness.yaml")

    _rewrite_report_paths(narrow_config, report_dir)
    _rewrite_report_paths(safe_config, report_dir)
    _rewrite_report_paths(triage_config, report_dir)
    _rewrite_report_paths(embedding_config, report_dir)
    for config in (narrow_config, safe_config, triage_config, embedding_config):
        config["reporting"] = {
            **config.get("reporting", {}),
            "artifact_profile": artifact_profile,
            "compact_report_basename": "answer_recovery_tuning_report",
            "emit_debug_artifacts_on_failure": True,
            "clean_legacy_stage_artifacts_on_compact_run": True,
        }

    narrow_path = config_dir / "answer_recovery_narrow_silver_calibration.yaml"
    safe_path = config_dir / "answer_recovery_safe_recall_tuning.yaml"
    triage_path = config_dir / "answer_recovery_safe_recall_missed_row_triage.yaml"
    embedding_path = config_dir / "answer_recovery_embedding_readiness.yaml"

    safe_config["baseline_policy"]["source_config"] = narrow_path.as_posix()
    safe_config["baseline_policy"]["source_report"] = narrow_config["report_paths"]["calibration_report_json"]
    safe_config["baseline_policy"]["source_selected_policy"] = narrow_config["report_paths"]["selected_policy_json"]

    _write_yaml(narrow_path, narrow_config)
    _write_yaml(safe_path, safe_config)
    _write_yaml(triage_path, triage_config)
    _write_yaml(embedding_path, embedding_config)

    return {
        "report_dir": report_dir,
        "narrow_config": narrow_path,
        "safe_config": safe_path,
        "triage_config": triage_path,
        "embedding_config": embedding_path,
    }


def _generated_report_names(report_dir: Path) -> set[str]:
    return {
        path.name
        for path in report_dir.iterdir()
        if path.is_file() and path.name != "pdf_file_lookup_wrongly_supported_root_cause.json"
    }


def _rewrite_report_paths(config: dict, report_dir: Path) -> None:
    for key, value in list(config.get("report_paths", {}).items()):
        config["report_paths"][key] = (report_dir / Path(value).name).as_posix()


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _load_compaction_script():
    module_path = ROOT / "scripts" / "rag_answer_recovery_tuning_report.py"
    spec = importlib.util.spec_from_file_location("rag_answer_recovery_tuning_report_for_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
