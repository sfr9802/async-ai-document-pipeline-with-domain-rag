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
V4_7_8_SHORT_KEY = "v4_7_8"
V4_7_8_SHORT_RUN_ID = "v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion"
V4_7_8_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_8_"
    "test_doc_dependency_decoupling_and_legacy_runner_alias_expansion_nonprod"
)
V4_7_8_STATUS = "V4_7_8_TEST_DOC_DEPENDENCY_DECOUPLING_RUNNER_ALIAS_EXPANSION_NONPROD_READY"
V4_7_8_REPORT = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "runs" / "v4_7_8" / "report.json"
V4_7_9_SHORT_KEY = "v4_7_9"
V4_7_9_SHORT_RUN_ID = "v4_7_9_pdf_evidence_residual_answer_quality_replay"
V4_7_9_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_9_"
    "pdf_evidence_residual_answer_quality_replay_nonprod"
)
V4_7_9_STATUS = "V4_7_9_PDF_EVIDENCE_RESIDUAL_ANSWER_QUALITY_REPLAY_NONPROD_READY"
V4_7_9_REPORT = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "runs" / "v4_7_9" / "report.json"
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
        "v4_7_8": "ai/eval/reports/rag-ingestion/runs/v4_7_8/report.json",
        "v4_7_9": "ai/eval/reports/rag-ingestion/runs/v4_7_9/report.json",
        "current": "ai/eval/reports/rag-ingestion/runs/v4_7_9/report.json",
    }
    for key, rel_path in expected.items():
        resolved = registry.resolve_run(key, root=ROOT)
        assert resolved.report_path == ROOT / rel_path
        assert resolved.report_path.exists(), key

    loaded = registry.load_report("current", root=ROOT)
    assert loaded["short_run_id"] == V4_7_9_SHORT_RUN_ID
    assert loaded["canonical_long_run_id"] == V4_7_9_LONG_RUN_ID
    assert loaded["status"] == V4_7_9_STATUS


def test_v477_runner_dispatches_current_previous_and_safe_legacy_checks() -> None:
    import ai.scripts.rag_eval as runner

    assert runner.DEFAULT_RUN_KEY == V4_7_9_SHORT_KEY
    assert "v3_18" in runner.SAFE_LEGACY_CHECK_ALIASES
    assert "v3_19" in runner.SAFE_LEGACY_CHECK_ALIASES
    assert "v3_20" in runner.SAFE_LEGACY_CHECK_ALIASES
    assert "v3_22" in runner.SAFE_LEGACY_CHECK_ALIASES
    assert "v3_21" in runner.SAFE_LEGACY_CHECK_ALIASES
    assert "v3_16" not in runner.SAFE_LEGACY_CHECK_ALIASES

    for args, expected_key, expected_status in (
        (["--check"], V4_7_9_SHORT_KEY, V4_7_9_STATUS),
        (["current", "--check"], V4_7_9_SHORT_KEY, V4_7_9_STATUS),
        (["v4_7_8", "--check"], V4_7_8_SHORT_KEY, V4_7_8_STATUS),
        (["v4_7_7", "--check"], V4_7_7_SHORT_KEY, V4_7_7_STATUS),
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
    latest = next(
        event
        for event in reversed(_read_jsonl(STATUS_JSONL))
        if event.get("short_run_id") == V4_7_7_SHORT_RUN_ID
    )
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

    for text in (progress, measurements, triage, eval_readme):
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


def test_v478_report_manifest_status_docs_and_alias_expansion_stay_closed() -> None:
    report = _read_json(V4_7_8_REPORT)
    latest = next(
        event
        for event in reversed(_read_jsonl(STATUS_JSONL))
        if event.get("short_run_id") == V4_7_8_SHORT_RUN_ID
    )
    manifest_rows = _read_jsonl(ROOT / report["artifact_paths"]["v3_legacy_hold_reduction_manifest_jsonl"])
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")

    assert report["short_run_id"] == V4_7_8_SHORT_RUN_ID
    assert report["canonical_long_run_id"] == V4_7_8_LONG_RUN_ID
    assert report["status"] == V4_7_8_STATUS
    assert report["diagnostic_only"] is True
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

    assert report["v3_legacy_artifact_count"] == len(manifest_rows)
    assert report["unclassified_count"] == 0
    assert report["archive_copy_failed_count"] == 0
    assert report["hash_verification_failed_count"] == 0
    assert report["after_hold_counts_by_classification"]["EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT"] <= 80
    assert report["after_hold_counts_by_classification"].get("EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE", 0) <= 20
    assert report["v3_legacy_manual_hold_count"] <= 120
    assert report["documented_review_packet_hold_count_before"] == 16
    assert report["documented_review_packet_hold_count_after"] == 16
    assert report["resolved_current_test_or_doc_contract_count"] > 0
    assert report["resolved_ambiguous_generated_surface_count"] > 0
    assert report["archived_count"] == report["removed_count"]

    aliases = set(report["script_consolidation"]["safe_check_aliases"])
    assert {"v3_18", "v3_19", "v3_20", "v3_21", "v3_22"}.issubset(aliases)
    assert "v3_16" in report["script_consolidation"]["held_legacy_entrypoints"]
    assert "v3_17" in report["script_consolidation"]["held_legacy_entrypoints"]
    assert report["safe_runner_check_alias_count_before"] == 2
    assert report["safe_runner_check_alias_count_after"] >= 5
    assert not list((ROOT / "ai" / "scripts").glob("rag_v4_7_8*.py"))

    assert latest["short_run_id"] == V4_7_8_SHORT_RUN_ID
    assert latest["artifact_paths"]["report_json"] == "ai/eval/reports/rag-ingestion/runs/v4_7_8/report.json"
    assert latest["artifact_sha256"]["report_json_sha256"] == _sha256_file(V4_7_8_REPORT)
    assert latest["official_metric"] is False
    assert latest["official_metric_input_rows"] == 0

    for text in (progress, measurements, triage, eval_readme, scripts_readme):
        assert V4_7_8_SHORT_RUN_ID in text
        assert "official_metric=false" in text or "official metric" in text
    assert "v4_7_8" in root_readme
    assert "official metrics" in root_readme or "official_metric=false" in root_readme

    generated_text = "\n".join(
        [
            json.dumps(report, ensure_ascii=False),
            json.dumps(latest, ensure_ascii=False),
            measurements.split("### v4_7_8", 1)[1].split("\n### ", 1)[0],
            triage.split("### v4_7_8", 1)[1].split("\n### ", 1)[0],
        ]
    )
    for pattern in (
        r"\b[A-Z]:[\\/]",
        r"prompt_payload",
        r"raw_response_payload",
        r"promotion-ready",
    ):
        assert not re.search(pattern, generated_text), pattern


def test_v479_pdf_residual_replay_repairs_only_residual_rows_and_fails_closed_without_llm() -> None:
    report = _read_json(V4_7_9_REPORT)
    latest = _read_jsonl(STATUS_JSONL)[-1]
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")

    assert report["short_run_id"] == V4_7_9_SHORT_RUN_ID
    assert report["canonical_long_run_id"] == V4_7_9_LONG_RUN_ID
    assert report["status"] == V4_7_9_STATUS
    assert report["source_run_id"] == "v4_7_5_pdf_evidence_repair_eval_compaction"
    assert report["prior_replay_run_id"] == "official_answer_citation_agentic_loop_run_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod"
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
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

    counters = report["counters"]
    assert counters["pdf_survivor_row_count"] == 58
    assert counters["prior_answer_ready_evidence_bundle_count"] == 48
    assert counters["residual_weak_evidence_window_count_before"] == 10
    assert counters["residual_weak_evidence_window_count_after"] < 10
    assert counters["missing_neighbor_context_count_before"] == 10
    assert counters["missing_neighbor_context_count_after"] == counters["residual_weak_evidence_window_count_after"]
    assert counters["repaired_evidence_bundle_count"] == counters["answer_replay_candidate_count"]
    assert counters["llm_invoked_count"] == 0
    assert counters["local_llm_unavailable_fail_closed_count"] == counters["answer_replay_candidate_count"]
    assert counters["generated_response_count"] == 0
    assert counters["parsed_final_answer_present_count"] == 0
    assert counters["citation_rendered_count"] == 0
    assert counters["claim_support_verifier_fail_count"] == 0
    assert counters["unsupported_claim_risk_count"] == 0
    assert counters["regression_count_for_prior_answer_ready_rows"] == 0
    assert counters["official_metric_input_rows"] == 0
    assert counters["protected_namespaces_touched"] == []

    rows = report["pdf_residual_replay_rows"]
    assert len(rows) == 58
    prior_ready_rows = [row for row in rows if row["prior_answer_ready_evidence_bundle"]]
    residual_rows = [row for row in rows if row["v4_7_5_residual_weak_evidence_window"]]
    repaired_rows = [row for row in rows if row["v4_7_9_repair_applied"]]
    assert len(prior_ready_rows) == 48
    assert len(residual_rows) == 10
    assert len(repaired_rows) == counters["repaired_evidence_bundle_count"]
    assert all(row["answer_ready_evidence_bundle"] for row in prior_ready_rows)
    assert all(row["SourceAtom_EvidenceBundle_role"] == "evidence_truth" for row in rows)
    assert all(row["SearchView_vector_payload_role"] == "candidate_only" for row in rows)
    assert all(row["raw_pdf_query_time_parsing"] is False for row in rows)
    assert all(row["hidden_target_locator_used"] is False for row in rows)
    assert all(row["expected_or_supporting_gold_text_used"] is False for row in rows)
    assert all(row["source_file_title_shortcut_used"] is False for row in rows)
    assert all(row["direct_answer_value_matching_used"] is False for row in rows)
    assert all(row["full_page_dump_used"] is False for row in rows)
    assert all(row["preserved_locator_metadata"]["page_candidate"] == row["page_candidate"] for row in rows)
    assert all(row["repair_audit"]["decision"] in {"protected_no_regression", "repaired", "dropped"} for row in rows)
    assert all(
        row["answer_replay_audit"]["status"] == "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"
        for row in repaired_rows
    )
    assert all(row["answer_replay_audit"]["raw_llm_response_created"] is False for row in repaired_rows)
    assert all(row["answer_replay_audit"]["claim_support_verifier_status"] == "not_run_local_llm_unavailable" for row in repaired_rows)

    assert latest["short_run_id"] == V4_7_9_SHORT_RUN_ID
    assert latest["artifact_paths"]["report_json"] == "ai/eval/reports/rag-ingestion/runs/v4_7_9/report.json"
    assert latest["artifact_sha256"]["report_json_sha256"] == _sha256_file(V4_7_9_REPORT)
    assert latest["official_metric"] is False
    assert latest["official_metric_input_rows"] == 0
    assert latest["local_llm_available"] is False
    assert latest["local_llm_unavailable_fail_closed_count"] == counters["local_llm_unavailable_fail_closed_count"]

    for text in (progress, measurements, triage, root_readme, eval_readme, scripts_readme):
        assert V4_7_9_SHORT_RUN_ID in text
        assert "official_metric=false" in text or "official metric" in text
    assert "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED" in measurements
    assert "SourceAtom/EvidenceBundle remains evidence truth" in triage

    generated_text = "\n".join(
        [
            json.dumps(report, ensure_ascii=False),
            json.dumps(latest, ensure_ascii=False),
            measurements.split("### v4_7_9", 1)[1].split("\n### ", 1)[0],
            triage.split("### v4_7_9", 1)[1].split("\n### ", 1)[0],
        ]
    )
    for pattern in (
        r"\b[A-Z]:[\\/]",
        r"prompt_payload",
        r"raw_response_payload",
        r"promotion-ready",
    ):
        assert not re.search(pattern, generated_text), pattern


def test_v477_stable_runner_executes_safe_legacy_check_aliases() -> None:
    for alias, expected_status in (
        ("v3_18", "DIAGNOSTIC_V3_18_AGENT_RUNTIME_TOOL_INVOCATION_CONTRACT_NONPROD_READY"),
        ("v3_19", "DIAGNOSTIC_V3_19_LOCATOR_AMBIGUITY_DEICTIC_RESPONSE_POLICY_NONPROD_READY"),
        ("v3_20", "DIAGNOSTIC_V3_20_LIVE_RUNTIME_LIKE_DB_INDEX_CACHE_SMOKE_NONPROD_READY"),
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
