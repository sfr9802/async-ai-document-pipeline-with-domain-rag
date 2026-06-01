from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
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

V4_7_6_SHORT_RUN_ID = "v4_7_6_eval_artifact_archive_purge"
V4_7_6_LONG_RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_6_eval_artifact_external_archive_and_purge_nonprod"
V4_7_6_STATUS = "V4_7_6_EVAL_ARTIFACT_ARCHIVE_PURGE_NONPROD_READY"
V4_7_7_STATUS = "V4_7_7_V3_LEGACY_ARCHIVE_RUNNER_CONSOLIDATION_NONPROD_READY"
V4_7_8_STATUS = "V4_7_8_TEST_DOC_DEPENDENCY_DECOUPLING_RUNNER_ALIAS_EXPANSION_NONPROD_READY"
V4_7_9_STATUS = "V4_7_9_PDF_EVIDENCE_RESIDUAL_ANSWER_QUALITY_REPLAY_NONPROD_READY"
V4_7_10_STATUS = "V4_7_10_PDF_KOREAN_EVIDENCE_NORMALIZATION_AND_ANSWER_REPLAY_READINESS_NONPROD_READY"
V4_7_11_STATUS = "V4_7_11_ACTUAL_LLM_ANSWER_REPLAY_AND_SILVER_DIAGNOSTIC_SMOKE_NONPROD_READY"
V4_7_12_STATUS = "V4_7_12_LAYERED_RETRIEVAL_GENERALIZATION_AND_OVERFIT_AUDIT_NONPROD_READY"
V4_7_13_STATUS = "V4_7_13_LIVE_RETRIEVAL_ANSWERABILITY_AND_FULL_PDF_REPLAY_NONPROD_READY"
V4_7_14_STATUS = "V4_7_14_DIAGNOSTIC_PRECONDITION_HARDENING_NONPROD_READY"
V4_7_15_STATUS = "V4_7_15_READ_ONLY_SEARCHINDEX_REPLAY_PROJECTION_NONPROD_READY"
V4_7_16_STATUS = "V4_7_16_TARGET_RECALL_REPAIR_PROTOTYPE_NONPROD_READY"
V4_7_17_STATUS = "V4_7_17_CANDIDATE_ONLY_GENERALIZATION_VALIDATION_AND_XLSX_TABLE_AXIS_REPAIR_AUDIT_NONPROD_READY"
V4_7_18_STATUS = "V4_7_18_XLSX_CANDIDATE_ONLY_MATERIALIZATION_REPAIR_AND_LINEAGE_REPRODUCIBILITY_NONPROD_READY"
V5_0_STATUS = "V5_0_V4_CLOSEOUT_AND_V5_GATE_PLAN_DIAGNOSTIC_NONPROD_READY"
V5_3_STATUS = "V5_3_PDF_TEXT_RESIDUAL_RETRIEVAL_EVIDENCE_HARDENING_DIAGNOSTIC_NONPROD_READY"
V4_7_6_REPORT = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "runs" / "v4_7_6" / "report.json"
STATUS_JSONL = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "status.jsonl"
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"
MEASUREMENTS_DOC = ROOT / "docs" / "rag-ingestion-measurements.md"
TRIAGE_DOC = ROOT / "docs" / "rag-ingestion-triage.md"


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v476_external_archive_target_must_be_outside_repo_and_hash_verified(tmp_path: Path) -> None:
    from ai.eval import rag_v476_archive_purge as v476

    inside = v476.resolve_external_archive_target(
        root=tmp_path,
        env={"RAG_EVAL_EXTERNAL_ARCHIVE_ROOT": str(tmp_path / "inside")},
        existing_roots=[],
    )
    assert inside.resolved is False
    assert inside.skip_reason == "external_archive_target_inside_repo"

    outside_root = tmp_path.parent / f"{tmp_path.name}_external"
    target = v476.resolve_external_archive_target(
        root=tmp_path,
        env={"RAG_EVAL_EXTERNAL_ARCHIVE_ROOT": str(outside_root)},
        existing_roots=[],
    )
    assert target.resolved is True
    assert target.target_root == outside_root / "rag-ingestion" / V4_7_6_SHORT_RUN_ID
    assert target.redacted is True

    source = tmp_path / "ai" / "eval" / "reports" / "rag-ingestion" / "obsolete.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"status":"obsolete"}\n', encoding="utf-8")
    record = v476.archive_then_remove_file(
        source,
        repo_root=tmp_path,
        archive_namespace_root=target.target_root,
        removed_at="2026-05-30T00:00:00Z",
    )
    archived = target.target_root / "ai" / "eval" / "reports" / "rag-ingestion" / "obsolete.json"
    assert record["classification"] == "ARCHIVE_THEN_REMOVE"
    assert record["sha256"] == _sha256_file(archived)
    assert record["archive_sha256"] == record["sha256"]
    assert record["archive_copy_verified"] is True
    assert record["removed_from_repo_at"] == "2026-05-30T00:00:00Z"
    assert archived.exists()
    assert not source.exists()


def test_v476_inventory_classification_keeps_protected_current_and_manual_hold() -> None:
    from ai.eval import rag_v476_archive_purge as v476

    assert v476.classify_path(ROOT / "ai" / "eval" / "eval_queries", root=ROOT) == "KEEP_PROTECTED"
    assert v476.classify_path(ROOT / "ai" / "eval" / "source_registry", root=ROOT) == "KEEP_PROTECTED"
    assert v476.classify_path(ROOT / "ai" / "eval" / "indexes", root=ROOT) == "KEEP_PROTECTED"
    assert v476.classify_path(ROOT / "ai" / "eval" / "silver", root=ROOT) == "KEEP_PROTECTED"
    assert (
        v476.classify_path(
            ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "runs" / "v4_7_5" / "report.json",
            root=ROOT,
        )
        == "KEEP_CURRENT_MINIMAL"
    )
    assert v476.classify_path(ROOT / "ai" / "eval" / "__pycache__", root=ROOT) == "DELETE_ONLY"
    assert (
        v476.classify_path(
            ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "manual-review-generated-but-tracked.csv",
            root=ROOT,
            ignored=False,
        )
        == "REVIEW_MANUAL_HOLD"
    )


def test_v476_registry_resolves_current_lineage_short_paths_and_legacy_aliases() -> None:
    from ai.eval import rag_eval_registry as registry
    from ai.scripts import rag_eval as runner

    expected = {
        "v4_7_preofficial": "ai/eval/reports/rag-ingestion/runs/v4_7_preofficial/report.json",
        "v4_7_2": "ai/eval/reports/rag-ingestion/runs/v4_7_2/report.json",
        "v4_7_3": "ai/eval/reports/rag-ingestion/runs/v4_7_3/report.json",
        "v4_7_4": "ai/eval/reports/rag-ingestion/runs/v4_7_4/report.json",
        "v4_7_5": "ai/eval/reports/rag-ingestion/runs/v4_7_5/report.json",
        "v4_7_6": "ai/eval/reports/rag-ingestion/runs/v4_7_6/report.json",
        "v4_7_9": "ai/eval/reports/rag-ingestion/runs/v4_7_9/report.json",
        "v4_7_10": "ai/eval/reports/rag-ingestion/runs/v4_7_10/report.json",
        "v4_7_11": "ai/eval/reports/rag-ingestion/runs/v4_7_11/report.json",
        "v4_7_12": "ai/eval/reports/rag-ingestion/runs/v4_7_12/report.json",
        "v4_7_13": "ai/eval/reports/rag-ingestion/runs/v4_7_13/report.json",
        "v4_7_14": "ai/eval/reports/rag-ingestion/runs/v4_7_14/report.json",
        "v4_7_15": "ai/eval/reports/rag-ingestion/runs/v4_7_15/report.json",
        "v4_7_16": "ai/eval/reports/rag-ingestion/runs/v4_7_16/report.json",
        "v4_7_17": "ai/eval/reports/rag-ingestion/runs/v4_7_17/report.json",
        "v4_7_18": "ai/eval/reports/rag-ingestion/runs/v4_7_18/report.json",
        "v5_0": "ai/eval/reports/rag-ingestion/runs/v5_0/report.json",
        "v5_1": "ai/eval/reports/rag-ingestion/runs/v5_1/report.json",
        "v5_2": "ai/eval/reports/rag-ingestion/runs/v5_2/report.json",
        "v5_3": "ai/eval/reports/rag-ingestion/runs/v5_3/report.json",
        "current": "ai/eval/reports/rag-ingestion/runs/v5_3/report.json",
    }
    ignored_artifact_in_memory_keys = {
        "v4_7_11",
        "v4_7_12",
        "v4_7_13",
        "v4_7_14",
        "v4_7_15",
        "v4_7_16",
        "v4_7_17",
        "v4_7_18",
        "v5_0",
        "v5_1",
        "v5_2",
        "v5_3",
        "current",
    }
    for key, rel_path in expected.items():
        resolved = registry.resolve_run(key, root=ROOT)
        assert resolved.report_path == ROOT / rel_path
        if key in ignored_artifact_in_memory_keys and not resolved.report_path.exists():
            built = runner.check_run(key)
            assert built["artifact_paths"]["report_json"] == rel_path
        else:
            assert resolved.report_path.exists(), key

    legacy = registry.resolve_run(
        "official_answer_citation_agentic_loop_run_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod",
        root=ROOT,
    )
    assert legacy.logical_key == "v4_7_4"
    assert legacy.legacy_long_path_supported is True

    loaded = registry.load_report("v4_7_6", root=ROOT)
    assert loaded["short_run_id"] == V4_7_6_SHORT_RUN_ID
    assert loaded["canonical_long_run_id"] == V4_7_6_LONG_RUN_ID
    assert loaded["status"] == V4_7_6_STATUS


def test_v476_report_status_docs_and_cleanup_manifest_are_compact_and_closed() -> None:
    from ai.eval import rag_eval_registry as registry

    report = registry.load_report("v4_7_6", root=ROOT)
    latest = next(row for row in reversed(_read_jsonl(STATUS_JSONL)) if row.get("short_run_id") == V4_7_6_SHORT_RUN_ID)
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_progress = progress.split("## Short History", 1)[0]
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")

    assert report["short_run_id"] == V4_7_6_SHORT_RUN_ID
    assert report["canonical_long_run_id"] == V4_7_6_LONG_RUN_ID
    assert report["status"] == V4_7_6_STATUS
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["cleanup_only"] is True
    for key in (
        "official_metric",
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "denominator_mutation",
        "training_dataset_created",
        "ft_a_execution",
        "fine_tuning",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "live_db_index_cache_readiness",
    ):
        assert report[key] is False, key
    assert report["official_metric_input_rows"] == 0
    assert report["protected_namespaces_touched"] == []
    assert report["external_archive_target_redacted"] is True
    assert report["cleanup_manifest_path"] == "ai/eval/reports/rag-ingestion/runs/v4_7_6/cleanup_manifest.jsonl"
    assert report["archive_manifest_path"] == "ai/eval/reports/rag-ingestion/archive_manifest.jsonl"
    assert report["archived_count"] == report["removed_count"]
    assert report["archive_copy_failed_count"] == 0
    assert report["hash_verification_failed_count"] == 0
    assert report["repo_local_report_file_count_after"] <= report["repo_local_report_file_count_before"]
    assert report["repo_local_report_bytes_after"] <= report["repo_local_report_bytes_before"]
    assert report["current_lineage_short_path_migrated"] is True
    assert report["resolver_current_key_valid"] is True

    cleanup_manifest = ROOT / report["cleanup_manifest_path"]
    assert cleanup_manifest.exists()
    cleanup_rows = _read_jsonl(cleanup_manifest)
    assert len(cleanup_rows) >= report["archived_count"] + report["deleted_count"]
    assert all("original_relative_path" in row for row in cleanup_rows)
    assert all("D:\\" not in json.dumps(row, ensure_ascii=False) for row in cleanup_rows)

    assert latest["short_run_id"] == V4_7_6_SHORT_RUN_ID
    assert latest["status"] == V4_7_6_STATUS
    assert latest["artifact_paths"]["report_json"] == "ai/eval/reports/rag-ingestion/runs/v4_7_6/report.json"
    assert latest["artifact_sha256"]["report_json_sha256"] == _sha256_file(V4_7_6_REPORT)

    short_report_path = "ai/eval/reports/rag-ingestion/runs/v4_7_6/report.json"
    assert short_report_path in current_progress
    assert short_report_path in measurements
    assert short_report_path in triage
    assert f"Current RAG status: `{V5_3_STATUS}`" in readme
    assert f"Current RAG status: `{V5_3_STATUS}`" in eval_readme

    generated_text = "\n".join(
        [
            json.dumps(report, ensure_ascii=False),
            json.dumps(latest, ensure_ascii=False),
            current_progress.split(f"<!-- {V4_7_6_SHORT_RUN_ID}:progress-entry:start -->", 1)[1].split(
                f"<!-- {V4_7_6_SHORT_RUN_ID}:progress-entry:end -->",
                1,
            )[0],
            measurements.split("### v4_7_6", 1)[1].split("\n### ", 1)[0],
            triage.split("### v4_7_6", 1)[1].split("\n### ", 1)[0],
        ]
    )
    for pattern in (
        r"\b[A-Z]:[\\/]",
        r"source_identity_key",
        r"prompt_payload",
        r"raw_response_payload",
        r"checkpoint artifact written",
        r"fine[-_ ]?tuned",
        r"promotion-ready",
    ):
        assert not re.search(pattern, generated_text), pattern


def test_v476_protected_namespaces_and_generated_status_surfaces_stay_safe() -> None:
    from ai.eval import rag_eval_registry as registry

    report = registry.load_report("v4_7_6", root=ROOT)
    for protected_path in (
        "ai/eval/eval_queries",
        "ai/eval/source_registry",
        "ai/eval/indexes",
        "ai/eval/silver",
    ):
        unstaged = subprocess.run(["git", "diff", "--quiet", "--", protected_path], cwd=ROOT, check=False)
        staged = subprocess.run(["git", "diff", "--cached", "--quiet", "--", protected_path], cwd=ROOT, check=False)
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    assert report["protected_namespaces_touched"] == []
    assert "training_dataset_path" not in json.dumps(report, ensure_ascii=False)
    assert "prompt_manifest" not in json.dumps(report, ensure_ascii=False)
    for path in (
        V4_7_6_REPORT,
        ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "runs" / "v4_7_6" / "cleanup_manifest.jsonl",
        ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "status.jsonl",
    ):
        ignored = subprocess.run(["git", "check-ignore", "-q", str(path.relative_to(ROOT))], cwd=ROOT, check=False)
        assert ignored.returncode == 0, path


def test_v476_stable_runner_dispatch_and_cleanup_contract_is_historical() -> None:
    import ai.tests.conftest as rag_conftest

    assert "ai/tests/test_rag_eval_v476_cleanup_contract.py" in rag_conftest.NON_CURRENT_RAG_TEST_FILES
    assert not rag_conftest.is_rag_current_required_nodeid(
        "ai/tests/test_rag_eval_v476_cleanup_contract.py::test_v476_report_status_docs_and_cleanup_manifest_are_compact_and_closed"
    )

    result = subprocess.run(
        [sys.executable, "-X", "utf8", "ai/scripts/rag_eval.py", "v4_7_6", "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["run_key"] == "v4_7_6"
    assert payload["status"] == V4_7_6_STATUS
    assert payload["report_json"] == "ai/eval/reports/rag-ingestion/runs/v4_7_6/report.json"
