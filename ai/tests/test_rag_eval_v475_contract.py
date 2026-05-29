from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
AI_DIR = ROOT / "ai"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

V4_7_4_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_4_"
    "pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod"
)
V4_7_5_SHORT_RUN_ID = "v4_7_5_pdf_evidence_repair_eval_compaction"
V4_7_5_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_5_pdf_survivor_"
    "evidence_window_repair_and_eval_surface_compaction_nonprod"
)
V4_7_5_STATUS = "V4_7_5_PDF_EVIDENCE_REPAIR_EVAL_COMPACTION_NONPROD_READY"
V4_7_4_REPORT = (
    ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / V4_7_4_LONG_RUN_ID / "report.json"
)
V4_7_5_REPORT = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "runs" / "v4_7_5" / "report.json"
STATUS_JSONL = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "status.jsonl"
ARCHIVE_MANIFEST = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "archive_manifest.jsonl"
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"
MEASUREMENTS_DOC = ROOT / "docs" / "rag-ingestion-measurements.md"
TRIAGE_DOC = ROOT / "docs" / "rag-ingestion-triage.md"


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v475_registry_resolves_short_current_and_legacy_aliases_fail_closed(tmp_path: Path) -> None:
    from ai.eval import rag_eval_registry as registry

    legacy = registry.resolve_run("v4_7_4", root=ROOT)
    current = registry.resolve_run("current", root=ROOT)
    v475_run = registry.resolve_run("v4_7_5", root=ROOT)

    assert legacy.report_path == ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "runs" / "v4_7_4" / "report.json"
    assert legacy.canonical_long_run_id == V4_7_4_LONG_RUN_ID
    assert legacy.legacy_long_path_supported is True
    assert v475_run.report_path == V4_7_5_REPORT
    assert v475_run.short_run_id == V4_7_5_SHORT_RUN_ID
    assert v475_run.canonical_long_run_id == V4_7_5_LONG_RUN_ID
    assert current.logical_key == "v4_7_7"

    loaded = registry.load_report("v4_7_5", root=ROOT)
    assert loaded["short_run_id"] == V4_7_5_SHORT_RUN_ID
    assert loaded["canonical_long_run_id"] == V4_7_5_LONG_RUN_ID
    assert loaded["status"] == V4_7_5_STATUS

    with pytest.raises(registry.ReportResolutionError, match="missing report"):
        registry.load_report("v4_7_5", root=tmp_path)
    with pytest.raises(registry.ReportResolutionError, match="sha256"):
        registry.load_report("v4_7_5", root=ROOT, expected_sha256="0" * 64)


def test_v475_core_accepts_explicit_report_dict_and_does_not_import_artifact_registry() -> None:
    from ai.eval import rag_v475_evidence_repair as v475

    source_report = _read_json(V4_7_4_REPORT)
    built = v475.build_report_from_v474_report(
        source_report=source_report,
        generated_at="2026-05-30T00:00:00Z",
        inventory_before={"long_path_literal_count": 3, "direct_report_path_dependency_count": 2},
        inventory_after={"long_path_literal_count": 1, "direct_report_path_dependency_count": 0},
        obsolete_artifact_inventory_count=1,
        archive_manifest_path="ai/eval/reports/rag-ingestion/archive_manifest.jsonl",
    )

    module_source = inspect.getsource(v475)
    assert "rag_eval_registry" not in module_source
    assert "ai/eval/reports/rag-ingestion/quality/official_answer_citation" not in module_source
    assert "status.jsonl" not in module_source
    assert built["short_run_id"] == V4_7_5_SHORT_RUN_ID
    assert built["pdf_survivor_row_count"] == 58
    assert built["xlsx_rows_in_scope"] == 0
    assert built["artifact_compaction"]["direct_report_path_dependency_count_after"] == 0


def test_v475_report_records_required_boundaries_and_artifact_compaction() -> None:
    from ai.eval import rag_eval_registry as registry

    report = registry.load_report("v4_7_5", root=ROOT)
    artifact_compaction = report["artifact_compaction"]

    assert V4_7_5_REPORT.exists()
    assert report["schema_version"] == "rag_v4_7_5_pdf_evidence_repair_eval_compaction_report_v1"
    assert report["short_run_id"] == V4_7_5_SHORT_RUN_ID
    assert report["canonical_long_run_id"] == V4_7_5_LONG_RUN_ID
    assert report["status"] == V4_7_5_STATUS
    assert report["source_run_id"] == V4_7_4_LONG_RUN_ID
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["gold_mutation"] is False
    assert report["qrels_mutation"] is False
    assert report["label_mutation"] is False
    assert report["expected_answer_mutation"] is False
    assert report["supporting_evidence_mutation"] is False
    assert report["denominator_mutation"] is False
    assert report["training_dataset_created"] is False
    assert report["ft_a_execution"] is False
    assert report["fine_tuning"] is False
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["protected_namespaces_touched"] == []
    assert report["raw_pdf_query_time_parsing"] is False
    assert report["broad_source_atom_scan_attempt_count"] == 0
    assert report["vector_payload_evidence_truth_violation_count"] == 0
    assert report["hidden_target_locator_used"] is False
    assert report["expected_or_supporting_gold_text_used"] is False
    assert report["source_file_title_shortcut_used"] is False
    assert report["pdf_survivor_row_count"] == 58
    assert report["xlsx_rows_in_scope"] == 0

    assert report["artifact_paths"] == {
        "report_json": "ai/eval/reports/rag-ingestion/runs/v4_7_5/report.json",
        "archive_manifest_jsonl": "ai/eval/reports/rag-ingestion/archive_manifest.jsonl",
    }
    assert artifact_compaction["registry_created_or_updated"] is True
    assert artifact_compaction["short_run_path_used"] == report["artifact_paths"]["report_json"]
    assert artifact_compaction["backward_compat_long_paths_supported"] is True
    assert artifact_compaction["long_path_literal_count_after"] <= artifact_compaction["long_path_literal_count_before"]
    assert artifact_compaction["direct_report_path_dependency_count_after"] == 0
    assert artifact_compaction["direct_report_path_dependency_count_after"] <= artifact_compaction[
        "direct_report_path_dependency_count_before"
    ]
    assert artifact_compaction["obsolete_artifact_inventory_count"] >= 1
    assert artifact_compaction["archived_or_removed_artifact_count"] == 0
    assert artifact_compaction["physical_cleanup_skipped_reason"]
    assert artifact_compaction["archive_manifest_path"] == report["artifact_paths"]["archive_manifest_jsonl"]
    assert "ignored" in artifact_compaction["generated_artifact_retention_policy"]
    assert ARCHIVE_MANIFEST.exists()
    manifest_rows = _read_jsonl(ARCHIVE_MANIFEST)
    assert manifest_rows
    assert all(row["sha256"] and row["classification"] for row in manifest_rows[:20])
    assert any(row["classification"] == "external_archive_candidate" for row in manifest_rows)


def test_v475_evidence_bundle_v2_metrics_repair_weak_windows_without_regressing_prior_ready_rows() -> None:
    from ai.eval import rag_eval_registry as registry

    report = registry.load_report("v4_7_5", root=ROOT)
    metrics = report["evidence_repair_metrics"]
    before = metrics["before"]
    after = metrics["after"]
    delta = metrics["delta"]
    ledger = report["pdf_survivor_replay_ledger"]

    assert len(ledger) == 58
    assert all(row["source_family"] == "PDF" for row in ledger)
    assert all(row["decision_status"] == "user_passed_query_candidate" for row in ledger)
    assert all(row["query_candidate_passed"] is True for row in ledger)
    assert all(row["evidence_bundle_version"] == "v2" for row in ledger)
    assert all(row["SourceAtom_EvidenceBundle_role"] == "evidence_truth" for row in ledger)
    assert all(row["SearchView_vector_payload_role"] == "candidate_only" for row in ledger)
    assert all(row["raw_pdf_query_time_parsing"] is False for row in ledger)
    assert all(row["broad_source_atom_scan_attempt_count"] == 0 for row in ledger)
    assert all(not row["llm_invoked"] for row in ledger if not row["answer_ready_evidence_bundle"])

    assert before["evidence_window_sufficient_proxy_count"] == 35
    assert before["weak_evidence_window_count"] == 23
    assert before["missing_neighbor_context_count"] == 23
    assert before["answer_ready_evidence_bundle_count"] == 35
    assert before["claim_support_verifier_pass_count"] == 25
    assert before["claim_support_verifier_fail_count"] == 8
    assert before["unsupported_claim_risk_count"] == 8
    assert before["evidence_underuse_flag_count"] == 7

    assert after["evidence_window_sufficient_proxy_count"] >= 45
    assert after["weak_evidence_window_count"] <= 13
    assert after["missing_neighbor_context_count"] <= 13
    assert after["answer_ready_evidence_bundle_count"] >= 45
    assert after["fail_closed_before_llm_count"] == after["weak_evidence_window_count"]
    assert after["table_or_figure_structure_repaired_count"] == 2
    assert after["regression_count_for_prior_answer_ready_rows"] == 0
    assert after["non_korean_answer_flag_count"] >= 0
    assert delta["evidence_window_sufficient_proxy_count"] == (
        after["evidence_window_sufficient_proxy_count"] - before["evidence_window_sufficient_proxy_count"]
    )
    assert metrics["regression_rows"] == []
    assert len(metrics["repaired_rows"]) == delta["evidence_window_sufficient_proxy_count"]
    assert all(row["repair_targeted"] is True for row in metrics["repaired_rows"])
    assert len([row for row in ledger if row["repair_targeted"]]) == 23
    assert len([row for row in ledger if row["repair_applied"]]) == len(metrics["repaired_rows"])


def test_v475_llm_guard_flags_non_korean_and_rejects_unsupported_claims() -> None:
    from ai.eval import rag_v475_evidence_repair as v475

    row = {
        "candidate_id_hash": "c",
        "query_id_hash": "q",
        "citation_span_preview": "증거에는 한국어 문장만 있습니다.",
    }

    diagnostics = v475.evaluate_answer_against_citation(row, "This is an English answer without cited support.")

    assert diagnostics["parsed_final_answer_present"] is True
    assert diagnostics["non_korean_answer_flag"] is True
    assert diagnostics["claim_support_verifier_pass"] is False
    assert diagnostics["claim_support_verifier_fail"] is True
    assert diagnostics["unsupported_claim_risk"] is True


def test_v475_status_docs_and_readme_sync_use_short_key_and_preserve_closed_gates() -> None:
    from ai.eval import rag_eval_registry as registry

    report = registry.load_report("v4_7_5", root=ROOT)
    events = _read_jsonl(STATUS_JSONL)
    latest = next(row for row in reversed(events) if row.get("short_run_id") == V4_7_5_SHORT_RUN_ID)
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")

    assert latest["short_run_id"] == V4_7_5_SHORT_RUN_ID
    assert latest["canonical_long_run_id"] == V4_7_5_LONG_RUN_ID
    assert latest["status"] == V4_7_5_STATUS
    assert latest["artifact_paths"]["report_json"] == report["artifact_paths"]["report_json"]
    assert latest["artifact_sha256"]["report_json_sha256"] == _sha256_file(V4_7_5_REPORT)
    assert latest["official_metric"] is False
    assert latest["official_metric_input_rows"] == 0
    assert latest["training_dataset_created"] is False
    assert latest["promotion_evidence"] is False
    assert latest["live_db_index_cache_readiness"] is False

    short_report_path = "ai/eval/reports/rag-ingestion/runs/v4_7_5/report.json"
    assert V4_7_5_SHORT_RUN_ID in current_text
    assert V4_7_5_SHORT_RUN_ID in measurements
    assert V4_7_5_SHORT_RUN_ID in triage
    assert short_report_path in current_text
    assert short_report_path in measurements
    assert short_report_path in triage
    assert "python -X utf8 ai\\scripts\\rag_eval.py v4_7_5 --check" in readme
    assert "`rag_eval.py`" in scripts_readme
    assert "official metric" in current_text
    assert "gold/qrels" in current_text
    assert "XLSX remains parked" in triage

    progress_v475_section = current_text.split(
        "<!-- v4_7_5_pdf_evidence_repair_eval_compaction:progress-entry:start -->",
        1,
    )[1].split(
        "<!-- v4_7_5_pdf_evidence_repair_eval_compaction:progress-entry:end -->",
        1,
    )[0]
    generated_text = "\n".join(
        [
            json.dumps(report, ensure_ascii=False),
            json.dumps(latest, ensure_ascii=False),
            progress_v475_section,
            measurements.split("### v4_7_5", 1)[1].split("\n### ", 1)[0],
            triage.split("### v4_7_5", 1)[1].split("\n### ", 1)[0],
        ]
    )
    for pattern in (
        r"\b[A-Z]:[\\/]",
        r"source_identity_key",
        r"(?<!hidden_)target_locator",
        r"(?<!hidden_target_or_)gold_locator",
        r"expected_answer_used_as_source",
        r"supporting_evidence_used_as_source",
        r"raw_response_payload",
        r"prompt_payload",
        r"checkpoint artifact written",
    ):
        assert not re.search(pattern, generated_text), pattern


def test_v475_no_protected_namespaces_or_training_artifacts_are_modified() -> None:
    from ai.eval import rag_eval_registry as registry

    report = registry.load_report("v4_7_5", root=ROOT)
    protected_paths = (
        "ai/eval/eval_queries",
        "ai/eval/source_registry",
        "ai/eval/indexes",
        "ai/eval/silver",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(["git", "diff", "--quiet", "--", protected_path], cwd=ROOT, check=False)
        staged = subprocess.run(["git", "diff", "--cached", "--quiet", "--", protected_path], cwd=ROOT, check=False)
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    assert report["protected_namespaces_touched"] == []
    assert report["training_dataset_created"] is False
    assert "training_dataset_path" not in json.dumps(report, ensure_ascii=False)
    assert "training_dataset_artifact" not in json.dumps(report, ensure_ascii=False)
    assert "prompt_manifest" not in json.dumps(report, ensure_ascii=False)


def test_v475_stable_runner_is_importable_and_current_profile_knows_contract_test() -> None:
    runner_path = ROOT / "ai" / "scripts" / "rag_eval.py"
    spec = importlib.util.spec_from_file_location("rag_eval_runner", runner_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.DEFAULT_RUN_KEY == "v4_7_7"
    assert callable(module.main)
    assert module.check_run("v4_7_5")["short_run_id"] == V4_7_5_SHORT_RUN_ID

    import ai.tests.conftest as rag_conftest

    nodeid = "ai/tests/test_rag_eval_v475_contract.py::test_v475_report_records_required_boundaries_and_artifact_compaction"
    assert "ai/tests/test_rag_eval_v475_contract.py" in rag_conftest.CURRENT_RAG_TEST_FILES
    assert rag_conftest.is_rag_current_required_nodeid(nodeid)
