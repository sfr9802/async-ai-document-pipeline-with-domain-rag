from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V4_7_7_SHORT_KEY = "v4_7_7"
V4_7_7_SHORT_RUN_ID = "v4_7_7_v3_legacy_archive_and_runner_consolidation"
V4_7_7_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_7_"
    "v3_legacy_artifact_archive_and_diagnostic_runner_consolidation_nonprod"
)
V4_7_7_STATUS = "V4_7_7_V3_LEGACY_ARCHIVE_RUNNER_CONSOLIDATION_NONPROD_READY"
V4_7_7_REPORT = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "runs" / "v4_7_7" / "report.json"
REPORT_ROOT = ROOT / "ai" / "eval" / "reports" / "rag-ingestion"
STATUS_JSONL = REPORT_ROOT / "status.jsonl"
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"
MEASUREMENTS_DOC = ROOT / "docs" / "rag-ingestion-measurements.md"
TRIAGE_DOC = ROOT / "docs" / "rag-ingestion-triage.md"


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v477_registry_resolves_current_and_previous_short_keys() -> None:
    from ai.eval import rag_eval_registry as registry

    expected = {
        "v4_7_preofficial": "ai/eval/reports/rag-ingestion/runs/v4_7_preofficial/report.json",
        "v4_7_2": "ai/eval/reports/rag-ingestion/runs/v4_7_2/report.json",
        "v4_7_3": "ai/eval/reports/rag-ingestion/runs/v4_7_3/report.json",
        "v4_7_4": "ai/eval/reports/rag-ingestion/runs/v4_7_4/report.json",
        "v4_7_5": "ai/eval/reports/rag-ingestion/runs/v4_7_5/report.json",
        "v4_7_6": "ai/eval/reports/rag-ingestion/runs/v4_7_6/report.json",
        "v4_7_7": "ai/eval/reports/rag-ingestion/runs/v4_7_7/report.json",
        "current": "ai/eval/reports/rag-ingestion/runs/v4_7_7/report.json",
    }
    for key, rel_path in expected.items():
        resolved = registry.resolve_run(key, root=ROOT)
        assert resolved.report_path == ROOT / rel_path
        assert resolved.report_path.exists(), key

    loaded = registry.load_report("current", root=ROOT)
    assert loaded["short_run_id"] == V4_7_7_SHORT_RUN_ID
    assert loaded["canonical_long_run_id"] == V4_7_7_LONG_RUN_ID
    assert loaded["status"] == V4_7_7_STATUS


def test_v477_runner_dispatches_current_previous_and_safe_legacy_checks() -> None:
    import ai.scripts.rag_eval as runner

    assert runner.DEFAULT_RUN_KEY == V4_7_7_SHORT_KEY
    assert "v3_22" in runner.SAFE_LEGACY_CHECK_ALIASES
    assert "v3_21" in runner.SAFE_LEGACY_CHECK_ALIASES
    assert "v3_16" not in runner.SAFE_LEGACY_CHECK_ALIASES

    for args, expected_key, expected_status in (
        (["--check"], V4_7_7_SHORT_KEY, V4_7_7_STATUS),
        (["current", "--check"], V4_7_7_SHORT_KEY, V4_7_7_STATUS),
        (["v4_7_6", "--check"], "v4_7_6", "V4_7_6_EVAL_ARTIFACT_ARCHIVE_PURGE_NONPROD_READY"),
    ):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "ai/scripts/rag_eval.py", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["run_key"] == expected_key
        assert payload["status"] == expected_status


def test_v477_manifest_classifies_every_v3_legacy_artifact_with_action_or_hold_reason() -> None:
    from ai.eval import rag_eval_registry as registry

    report = registry.load_report("v4_7_7", root=ROOT)
    manifest_path = ROOT / str(report["artifact_paths"]["v3_legacy_manifest_jsonl"])
    manifest_rows = _read_jsonl(manifest_path)

    assert report["archive_aware_eval_surface"] is True
    assert report["v3_legacy_artifact_count"] == len(manifest_rows)
    assert report["v3_legacy_unclassified_count"] == 0
    assert report["v3_legacy_artifact_count"] == (
        report["v3_legacy_archived_or_removed_count"]
        + report["v3_legacy_deleted_count"]
        + report["v3_legacy_manual_hold_count"]
    )
    assert report["archive_copy_failed_count"] == 0
    assert report["hash_verification_failed_count"] == 0
    assert report["v3_legacy_archived_or_removed_count"] > 0
    assert report["v3_legacy_manual_hold_count"] > 0
    assert sum(report["v3_legacy_hold_counts_by_classification"].values()) == report["v3_legacy_manual_hold_count"]
    assert report["v3_legacy_hold_counts_by_classification"]["EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT"] > 0
    assert report["v3_legacy_hold_counts_by_classification"]["EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE"] > 0

    seen: set[tuple[str, str]] = set()
    classifications = {row["classification"] for row in manifest_rows}
    assert "EXTERNALLY_ARCHIVED_REMOVED" in classifications
    assert "EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT" in classifications
    for row in manifest_rows:
        key = (str(row["original_relative_path"]), str(row["classification"]))
        assert key not in seen
        seen.add(key)
        assert str(row["original_relative_path"]).startswith("ai/eval/reports/rag-ingestion/")
        assert ".." not in Path(str(row["original_relative_path"])).parts
        assert "D:\\" not in json.dumps(row, ensure_ascii=False)
        if row["classification"].startswith("EXPLICIT_HOLD"):
            assert row["hold_reason"]
        if row["classification"] in {"EXTERNALLY_ARCHIVED_REMOVED", "ARCHIVE_THEN_REMOVE"}:
            assert row["sha256"]


def test_v477_status_docs_and_script_consolidation_stay_closed_and_compact() -> None:
    report = _read_json(V4_7_7_REPORT)
    latest = _read_jsonl(STATUS_JSONL)[-1]
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")

    assert report["short_run_id"] == V4_7_7_SHORT_RUN_ID
    assert report["status"] == V4_7_7_STATUS
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
    assert report["script_consolidation"]["stable_runner"] == "ai/scripts/rag_eval.py"
    assert "v3_22" in report["script_consolidation"]["safe_check_aliases"]
    assert "v3_16" in report["script_consolidation"]["held_legacy_entrypoints"]
    assert not list((ROOT / "ai" / "scripts").glob("rag_v4_7_7*.py"))

    assert latest["short_run_id"] == V4_7_7_SHORT_RUN_ID
    assert latest["artifact_paths"]["report_json"] == "ai/eval/reports/rag-ingestion/runs/v4_7_7/report.json"
    assert latest["artifact_sha256"]["report_json_sha256"] == _sha256_file(V4_7_7_REPORT)
    assert latest["v3_legacy_hold_counts_by_classification"] == report["v3_legacy_hold_counts_by_classification"]

    for text in (progress, measurements, triage, root_readme, eval_readme, scripts_readme):
        assert V4_7_7_SHORT_RUN_ID in text
    assert "v4_7_6 cleanup/refactor" in eval_readme
    v476_line = next(line for line in eval_readme.splitlines() if "v4_7_6 cleanup/refactor" in line)
    assert "resolver key `current`" not in v476_line
    assert "use resolver key `v4_7_6` for this prior archive-purge report" in eval_readme

    generated_text = "\n".join(
        [
            json.dumps(report, ensure_ascii=False),
            json.dumps(latest, ensure_ascii=False),
            measurements.split("### v4_7_7", 1)[1].split("\n### ", 1)[0],
            triage.split("### v4_7_7", 1)[1].split("\n### ", 1)[0],
        ]
    )
    for pattern in (
        r"\b[A-Z]:[\\/]",
        r"source_identity_key",
        r"prompt_payload",
        r"raw_response_payload",
        r"fine[-_ ]?tuned",
        r"promotion-ready",
    ):
        assert not re.search(pattern, generated_text), pattern


def test_v477_stable_runner_executes_safe_legacy_check_aliases() -> None:
    for alias, expected_status in (
        ("v3_21", "DIAGNOSTIC_V3_21_AGENT_RUNTIME_LLM_IO_OBSERVABILITY_PACKET_NONPROD_READY"),
        ("v3_22", "DIAGNOSTIC_V3_22_XLSX_VALUE_FORMATTING_AND_CELL_RANGE_ANSWER_RENDERING_NONPROD_READY"),
    ):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "ai/scripts/rag_eval.py", alias, "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
            timeout=180,
        )
        payload = json.loads(result.stdout)
        assert payload["run_key"] == alias
        assert payload["status"] == expected_status
        assert payload["safe_legacy_alias"] == alias
        assert payload["write_supported"] is False
        assert payload["official_metric_input_rows"] == 0
