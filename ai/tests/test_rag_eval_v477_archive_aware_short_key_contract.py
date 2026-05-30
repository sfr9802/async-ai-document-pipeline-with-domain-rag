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
V4_7_10_SHORT_KEY = "v4_7_10"
V4_7_10_SHORT_RUN_ID = "v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness"
V4_7_10_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_10_"
    "pdf_korean_evidence_normalization_and_answer_replay_readiness_nonprod"
)
V4_7_10_STATUS = "V4_7_10_PDF_KOREAN_EVIDENCE_NORMALIZATION_AND_ANSWER_REPLAY_READINESS_NONPROD_READY"
V4_7_10_REPORT = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "runs" / "v4_7_10" / "report.json"
V4_7_11_SHORT_KEY = "v4_7_11"
V4_7_11_SHORT_RUN_ID = "v4_7_11_actual_llm_answer_replay_and_silver_diagnostic_smoke"
V4_7_11_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_11_"
    "actual_llm_answer_replay_and_silver_diagnostic_smoke_nonprod"
)
V4_7_11_STATUS = "V4_7_11_ACTUAL_LLM_ANSWER_REPLAY_AND_SILVER_DIAGNOSTIC_SMOKE_NONPROD_READY"
V4_7_11_REPORT = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "runs" / "v4_7_11" / "report.json"
V4_7_12_SHORT_KEY = "v4_7_12"
V4_7_12_SHORT_RUN_ID = "v4_7_12_layered_retrieval_generalization_and_overfit_audit"
V4_7_12_ACTIVE_GOAL_ALIAS = "v4_7_12_answer_policy_calibration_and_silver_manifest_reconnect"
V4_7_12_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_12_"
    "layered_retrieval_generalization_and_overfit_audit_nonprod"
)
V4_7_12_STATUS = "V4_7_12_LAYERED_RETRIEVAL_GENERALIZATION_AND_OVERFIT_AUDIT_NONPROD_READY"
V4_7_12_REPORT = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "runs" / "v4_7_12" / "report.json"
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


def _load_v4710_report() -> dict[str, object]:
    if V4_7_10_REPORT.exists():
        return _read_json(V4_7_10_REPORT)
    import ai.scripts.rag_eval as runner

    return runner.check_run(V4_7_10_SHORT_KEY)


def _fake_strict_korean_answer(prompt: str) -> str:
    payload = json.loads(prompt)
    evidence = str(payload.get("bounded_evidence_excerpt") or payload.get("evidence") or "")
    terms = [token for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", evidence) if token]
    head = " ".join(terms[:2]) or "근거"
    return json.dumps(
        {
            "final_answer": f"근거에 따르면 {head} 관련 내용입니다.",
            "abstain": False,
            "citations": ["evidence_1"],
            "answer_plan": "제공된 근거 문장만 사용해 한 문장으로 답변합니다.",
            "unsupported_claim_risk": False,
            "evidence_underuse_flag": False,
            "context_understanding_miss": False,
            "over_abstain_candidate": False,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def test_v477_registry_resolves_current_and_previous_short_keys() -> None:
    from ai.eval import rag_eval_registry as registry
    import ai.scripts.rag_eval as runner

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
        "v4_7_10": "ai/eval/reports/rag-ingestion/runs/v4_7_10/report.json",
        "v4_7_11": "ai/eval/reports/rag-ingestion/runs/v4_7_11/report.json",
        "v4_7_12": "ai/eval/reports/rag-ingestion/runs/v4_7_12/report.json",
        V4_7_12_ACTIVE_GOAL_ALIAS: "ai/eval/reports/rag-ingestion/runs/v4_7_12/report.json",
        "current": "ai/eval/reports/rag-ingestion/runs/v4_7_12/report.json",
    }
    for key, rel_path in expected.items():
        resolved = registry.resolve_run(key, root=ROOT)
        assert resolved.report_path == ROOT / rel_path
        if key in {V4_7_11_SHORT_KEY, V4_7_12_SHORT_KEY, V4_7_12_ACTIVE_GOAL_ALIAS, "current"} and not resolved.report_path.exists():
            built = runner.check_run(key)
            assert built["artifact_paths"]["report_json"] == rel_path
        else:
            assert resolved.report_path.exists(), key

    prior = _load_v4710_report()
    assert prior["short_run_id"] == V4_7_10_SHORT_RUN_ID
    assert prior["canonical_long_run_id"] == V4_7_10_LONG_RUN_ID
    assert prior["status"] == V4_7_10_STATUS
    current = runner.check_run("current")
    assert current["short_run_id"] == V4_7_12_SHORT_RUN_ID
    assert current["canonical_long_run_id"] == V4_7_12_LONG_RUN_ID
    assert current["status"] == V4_7_12_STATUS
    explicit_prior = runner.check_run("v4_7_11")
    assert explicit_prior["short_run_id"] == V4_7_11_SHORT_RUN_ID
    assert explicit_prior["status"] == V4_7_11_STATUS


def test_v477_runner_dispatches_current_previous_and_safe_legacy_checks() -> None:
    import ai.scripts.rag_eval as runner

    assert runner.DEFAULT_RUN_KEY == V4_7_12_SHORT_KEY
    assert "v3_18" in runner.SAFE_LEGACY_CHECK_ALIASES
    assert "v3_19" in runner.SAFE_LEGACY_CHECK_ALIASES
    assert "v3_20" in runner.SAFE_LEGACY_CHECK_ALIASES
    assert "v3_22" in runner.SAFE_LEGACY_CHECK_ALIASES
    assert "v3_21" in runner.SAFE_LEGACY_CHECK_ALIASES
    assert "v3_16" not in runner.SAFE_LEGACY_CHECK_ALIASES

    for args, expected_key, expected_status in (
        (["--check"], V4_7_12_SHORT_KEY, V4_7_12_STATUS),
        (["current", "--check"], V4_7_12_SHORT_KEY, V4_7_12_STATUS),
        ([V4_7_12_ACTIVE_GOAL_ALIAS, "--check"], V4_7_12_SHORT_KEY, V4_7_12_STATUS),
        (["v4_7_11", "--check"], V4_7_11_SHORT_KEY, V4_7_11_STATUS),
        (["v4_7_10", "--check"], V4_7_10_SHORT_KEY, V4_7_10_STATUS),
        (["v4_7_9", "--check"], V4_7_9_SHORT_KEY, V4_7_9_STATUS),
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


def test_v4712_current_check_builds_in_memory_when_report_artifact_is_missing(monkeypatch) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_v4712_layered_retrieval_generalization_and_overfit_audit as v4712

    missing_report = Path("ai/eval/reports/rag-ingestion/runs/v4_7_12_missing_for_test/report.json")
    monkeypatch.setattr(v4712, "SHORT_REPORT_PATH", missing_report)

    current = runner.check_run("current")
    long_alias = runner.check_run(V4_7_12_LONG_RUN_ID)

    for report in (current, long_alias):
        v4712.check_report(report)
        assert report["short_run_id"] == V4_7_12_SHORT_RUN_ID
        assert report["artifact_paths"]["report_json"] == missing_report.as_posix()
    assert not (ROOT / missing_report).exists()


def test_v4712_layered_retrieval_audit_preserves_architecture_and_is_not_canary_limited() -> None:
    from ai.eval import rag_v4712_layered_retrieval_generalization_and_overfit_audit as v4712

    source_packet = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "runs" / "v4_7_11" / "answer_review_packet_ko.jsonl"
    source_packet_sha_before = _sha256_file(source_packet)
    report = v4712.build_report(
        root=ROOT,
        execute=False,
        sync_surfaces=False,
        env={},
        generated_at="2026-05-31T00:00:00Z",
    )
    v4712.check_report(report)
    counters = report["counters"]

    assert report["short_run_id"] == V4_7_12_SHORT_RUN_ID
    assert report["source_run_id"] == V4_7_11_SHORT_RUN_ID
    assert report["source_pdf_surface_run_id"] == V4_7_10_SHORT_RUN_ID
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["protected_namespaces_touched"] == []
    assert counters["v4_7_11_canary_row_count"] == 9
    assert counters["pdf_survivor_row_count"] == 58
    assert counters["pdf_answer_ready_evidencebundle_count"] == 57
    assert counters["pdf_full_replay_eligible_count"] == 57
    assert counters["layered_retrieval_audit_row_count"] >= 57
    assert counters["layered_retrieval_audit_row_count"] > counters["v4_7_11_canary_row_count"]
    assert counters["searchview_vector_payload_candidate_only_count"] >= counters["layered_retrieval_audit_row_count"]
    assert counters["sourceatom_evidencebundle_truth_count"] >= counters["layered_retrieval_audit_row_count"]
    assert counters["vector_payload_used_as_evidence_truth_violation_count"] == 0
    assert counters["raw_pdf_query_time_parsing_attempt_count"] == 0
    assert counters["raw_xlsx_query_time_parsing_attempt_count"] == 0
    assert counters["broad_source_atom_scan_attempt_count"] == 0
    assert counters["hidden_target_locator_used_count"] == 0
    assert counters["expected_or_supporting_gold_text_used_count"] == 0
    assert counters["source_file_title_shortcut_used_count"] == 0
    assert counters["direct_answer_value_matching_used_count"] == 0
    assert counters["full_page_dump_used_count"] == 0
    assert counters["agent_tool_layer_policy_violation_count"] == 0
    assert counters["family_router_invoked_count"] >= counters["layered_retrieval_audit_row_count"]
    assert counters["sourceatom_hydration_tool_invoked_count"] >= counters["layered_retrieval_audit_row_count"]
    assert counters["evidencebundle_builder_invoked_count"] >= counters["layered_retrieval_audit_row_count"]
    assert counters["citation_renderer_invoked_count"] >= counters["layered_retrieval_audit_row_count"]
    assert report["architecture_compliance_audit"]["layered_retrieval_architecture_preserved"] is True
    assert report["agent_tooling_audit"]["unsafe_shortcut_blocked_count"] >= 0
    assert counters["official_metric_input_rows"] == 0
    assert counters["silver_official_metric_input_rows"] == 0
    assert _sha256_file(source_packet) == source_packet_sha_before
    event = v4712.status_event(report, artifact_hashes={"report_json_sha256": "0" * 64})
    assert event["schema_version"] == f"{V4_7_12_SHORT_RUN_ID}_status_event_v1"
    assert event["logical_run_key"] == V4_7_12_SHORT_KEY
    assert event["short_run_id"] == V4_7_12_SHORT_RUN_ID
    assert event["non_production"] is True
    assert event["silver_topk_found"] == counters["silver_topk_found"]


def test_v4712_silver_reconnect_runs_retrieval_only_audit_or_fails_closed_without_promotion() -> None:
    from ai.eval import rag_v4712_layered_retrieval_generalization_and_overfit_audit as v4712

    report = v4712.build_report(
        root=ROOT,
        execute=False,
        sync_surfaces=False,
        env={},
        generated_at="2026-05-31T00:00:00Z",
    )
    v4712.check_report(report)
    audit = report["silver_layered_retrieval_audit"]
    counters = report["counters"]

    assert audit["diagnostic_silver_only"] is True
    assert audit["silver_regenerated"] is False
    assert counters["silver_promoted_to_gold_count"] == 0
    assert counters["silver_official_metric_input_rows"] == 0
    assert counters["official_metric_input_rows"] == 0
    if counters["silver_manifest_found"]:
        assert counters["silver_total_row_count"] == 1000
        assert counters["silver_topk_found"] is True
        assert counters["silver_unique_id_count"] == 1000
        assert counters["silver_unique_query_hash_count"] == 1000
        assert counters["silver_text_count"] == 350
        assert counters["silver_pdf_count"] == 325
        assert counters["silver_xlsx_count"] == 325
        assert counters["silver_core_count"] == 665
        assert counters["silver_review_only_count"] == 335
        assert counters["silver_quarantine_count"] == 0
        assert counters["silver_retrieval_audit_row_count"] == 1000
        assert counters["silver_query_hash_unique_count"] == 1000
        assert counters["silver_duplicate_query_hash_count"] == 0
        assert counters["silver_likely_unanswerable_count"] == 0
        assert audit["status"] == "SILVER_LAYERED_RETRIEVAL_AUDIT_COMPLETED_DIAGNOSTIC_ONLY"
        assert audit["audit_rows_total"] == 1000
        assert len(audit["audit_rows"]) == 1000
        assert all("too_broad_query" in row for row in audit["audit_rows"])
        assert all("likely_unanswerable" in row for row in audit["audit_rows"])
        assert not any(
            row["likely_unanswerable"]
            for row in audit["audit_rows"]
            if row.get("weak_answerability_status") == "auto_weak_silver_likely_answerable"
        )
        assert counters["silver_family_route_selected_count_by_family"]["TEXT"] == 350
        assert counters["silver_family_route_selected_count_by_family"]["PDF"] == 325
        assert counters["silver_family_route_selected_count_by_family"]["XLSX"] == 325
        assert counters["silver_sourceatom_hydration_success_count_by_family"]["PDF"] >= 0
        assert counters["silver_evidencebundle_created_count_by_family"]["XLSX"] >= 0
        assert counters["silver_citation_render_success_count_by_family"]["TEXT"] >= 0
        assert counters["silver_manifest_sha256"]
    else:
        assert audit["status"] == "SILVER_SOURCE_ARTIFACTS_UNAVAILABLE_FAIL_CLOSED"
        assert counters["silver_total_row_count"] == 0
        assert audit["artifact_resolution_evidence"]["searched_paths"]
        assert audit["artifact_resolution_evidence"]["archive_manifest_hints"]


def test_v4712_silver_reconnect_fails_closed_when_topk_artifact_is_missing(monkeypatch) -> None:
    from ai.eval import rag_v4712_layered_retrieval_generalization_and_overfit_audit as v4712

    def missing_topk(root: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
        logical_path = v4712.V3_7_2_TOPK_ROWS.as_posix()
        return [], {
            "found": False,
            "logical_path": logical_path,
            "sha256": "",
            "artifact_resolution_evidence": {
                "searched_paths": [{"path": logical_path, "resolved_exists": False}],
                "archive_manifest_hints": [],
            },
        }

    monkeypatch.setattr(v4712, "_load_v3_7_2_topk", missing_topk)
    report = v4712.build_report(
        root=ROOT,
        execute=False,
        sync_surfaces=False,
        env={},
        generated_at="2026-05-31T00:00:00Z",
    )
    v4712.check_report(report)
    audit = report["silver_layered_retrieval_audit"]
    counters = report["counters"]

    assert counters["silver_manifest_found"] is True
    assert counters["silver_topk_found"] is False
    assert counters["silver_total_row_count"] == 1000
    assert counters["silver_retrieval_audit_row_count"] == 0
    assert counters["layered_retrieval_audit_row_count"] == counters["pdf_full_replay_eligible_count"]
    assert audit["status"] == "SILVER_TOPK_ARTIFACT_UNAVAILABLE_FAIL_CLOSED"
    assert audit["blocked_reason"] == "exact v3_7_2 row-level retrieval top-k artifact unavailable or sha verification failed"
    assert report["completion_branch"] == "B_silver_unavailable_layered_retrieval_audit_fail_closed"


def test_v4712_full_pdf_replay_and_silver_smoke_are_env_gated_without_fake_answers() -> None:
    from ai.eval import rag_v4712_layered_retrieval_generalization_and_overfit_audit as v4712

    disabled = v4712.build_report(
        root=ROOT,
        execute=False,
        sync_surfaces=False,
        env={},
        generated_at="2026-05-31T00:00:00Z",
    )
    v4712.check_report(disabled)
    counters = disabled["counters"]
    assert counters["pdf_full_replay_env_enabled"] is False
    assert counters["pdf_llm_invoked_count"] == 0
    assert counters["pdf_generated_response_count"] == 0
    assert counters["silver_llm_smoke_env_enabled"] is False
    assert counters["silver_llm_invoked_count"] == 0
    assert counters["silver_generated_response_count"] == 0
    assert disabled["full_pdf_llm_replay"]["status"] == "FULL_PDF_LLM_REPLAY_DISABLED_FAIL_CLOSED"
    assert disabled["silver_answer_smoke"]["status"] in {
        "SILVER_LLM_SMOKE_DISABLED_FAIL_CLOSED",
        "SILVER_LLM_SMOKE_SOURCE_UNAVAILABLE_FAIL_CLOSED",
    }

    mutated = json.loads(json.dumps(disabled))
    mutated["full_pdf_llm_replay"]["rows"] = [{"final_answer": "fake deterministic answer"}]
    mutated["counters"]["pdf_generated_response_count"] = 1
    try:
        v4712.check_report(mutated)
    except ValueError as exc:
        assert "full PDF replay counted answers while replay was disabled" in str(exc)
    else:
        raise AssertionError("v4_7_12 accepted fake full PDF LLM answers")


def test_v4712_silver_llm_smoke_runs_bounded_balanced_when_enabled(monkeypatch) -> None:
    from ai.eval import rag_v4712_layered_retrieval_generalization_and_overfit_audit as v4712

    def fake_probe(*, execute: bool, env: object) -> dict[str, object]:
        return {
            "available": bool(execute),
            "status": "LOCAL_LLM_AVAILABLE_DIAGNOSTIC_ONLY",
            "backend": "injected-test-client",
            "base_url_redacted": "injected",
            "model": "injected",
            "blockers": [],
        }

    def fake_client(prompt: str) -> str:
        payload = json.loads(prompt)
        evidence = str(payload.get("evidence") or "")
        citation_id = str(payload.get("citation_id") or "")
        terms = [token for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", evidence) if token]
        head = " ".join(terms[:2]) or "근거 내용"
        return json.dumps(
            {
                "final_answer": f"근거에 따르면 {head} 관련 내용입니다.",
                "answer_type": "answer",
                "citations": [citation_id],
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    monkeypatch.setattr(v4712, "_local_llm_probe", fake_probe)
    report = v4712.build_report(
        root=ROOT,
        execute=True,
        sync_surfaces=False,
        env={"RAG_V4_7_12_ENABLE_SILVER_LLM_SMOKE": "1"},
        llm_client=fake_client,
        generated_at="2026-05-31T00:00:00Z",
    )
    v4712.check_report(report)
    counters = report["counters"]

    assert counters["silver_llm_smoke_env_enabled"] is True
    assert counters["silver_llm_smoke_sample_count"] == 90
    assert counters["silver_llm_smoke_text_count"] == 30
    assert counters["silver_llm_smoke_pdf_count"] == 30
    assert counters["silver_llm_smoke_xlsx_count"] == 30
    assert counters["silver_llm_invoked_count"] == 90
    assert counters["silver_generated_response_count"] == 90
    assert counters["silver_citation_rendered_count"] == 90
    assert counters["silver_official_metric_input_rows"] == 0
    assert counters["silver_promoted_to_gold_count"] == 0
    assert len(report["silver_answer_smoke"]["rows"]) == 90
    assert all(row["raw_response_sha256"] for row in report["silver_answer_smoke"]["rows"])


def test_v4712_status_docs_do_not_leave_stale_current_alias_text() -> None:
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")

    assert "`current` resolves to `v4_7_12`" in scripts_readme
    assert "`current` resolves to `v4_7_11`" not in scripts_readme
    assert "v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness" in scripts_readme
    assert "v4_7_9_pdf_evidence_residual_answer_quality_replay" in scripts_readme


def test_v4711_injected_local_llm_replays_v4710_candidates_and_records_answer_audits() -> None:
    from ai.eval import rag_v4711_actual_llm_answer_replay_and_silver_diagnostic_smoke as v4711

    prompts: list[str] = []

    def fake_client(prompt: str) -> str:
        prompts.append(prompt)
        return _fake_strict_korean_answer(prompt)

    report = v4711.build_report(
        root=ROOT,
        execute=True,
        sync_surfaces=False,
        env={"RAG_V4_7_11_ENABLE_LOCAL_LLM_REPLAY": "1"},
        llm_client=fake_client,
        generated_at="2026-05-30T00:00:00Z",
    )
    v4711.check_report(report)
    counters = report["counters"]

    assert report["short_run_id"] == V4_7_11_SHORT_RUN_ID
    assert report["source_run_id"] == V4_7_10_SHORT_RUN_ID
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert counters["v4_7_10_answer_ready_evidence_bundle_count"] == 57
    assert counters["v4_7_10_answer_replay_candidate_count"] == 9
    assert counters["v4_7_10_replayed_candidate_count"] == 9
    assert counters["v4_7_10_skipped_weak_residual_count"] == 1
    assert counters["local_llm_replay_env_enabled"] is True
    assert counters["local_llm_available"] is True
    assert counters["llm_invoked_count"] == 9
    assert counters["generated_response_count"] == 9
    assert counters["raw_llm_response_present_count"] == 0
    assert counters["parsed_final_answer_present_count"] == 9
    assert counters["citation_rendered_count"] == 9
    assert counters["citation_grounded_to_evidence_count"] == 9
    assert counters["korean_final_answer_count"] == 9
    assert counters["non_korean_answer_flag_count"] == 0
    assert counters["claim_support_verifier_pass_count"] + counters["claim_support_verifier_fail_count"] == 9
    assert counters["prompt_leakage_flag_count"] == 0
    assert counters["response_leakage_flag_count"] == 0
    assert counters["path_leakage_flag_count"] == 0
    assert counters["evidence_truth_violation_count"] == 0
    assert counters["vector_payload_evidence_truth_violation_count"] == 0
    assert len(prompts) == 9
    assert all(
        not re.search(r"\b[A-Z]:[\\/]|gold|qrels|expected|supporting|source_file_title", prompt, re.I)
        for prompt in prompts
    )

    rows = report["pdf_answer_replay_rows"]
    assert len(rows) == 9
    assert all(row["llm_invoked"] is True for row in rows)
    assert all(row["answer_replay_audit"]["status"] == "LOCAL_LLM_GENERATED_DIAGNOSTIC_ONLY" for row in rows)
    assert all(row["answer_replay_audit"]["parsed_final_answer_present"] is True for row in rows)
    assert all(row["answer_replay_audit"]["citation_grounded_to_evidence"] is True for row in rows)


def test_v4711_unavailable_or_disabled_local_llm_fails_closed_without_fake_answers() -> None:
    from ai.eval import rag_v4711_actual_llm_answer_replay_and_silver_diagnostic_smoke as v4711

    disabled = v4711.build_report(
        root=ROOT,
        execute=False,
        sync_surfaces=False,
        env={},
        generated_at="2026-05-30T00:00:00Z",
    )
    unavailable = v4711.build_report(
        root=ROOT,
        execute=True,
        sync_surfaces=False,
        env={
            "RAG_V4_7_11_ENABLE_LOCAL_LLM_REPLAY": "1",
            "RAG_V4_7_11_LOCAL_LLM_BASE_URL": "http://127.0.0.1:9/v1",
        },
        llm_timeout_seconds=1,
        generated_at="2026-05-30T00:00:00Z",
    )

    for report, expected_status, expected_counter in (
        (disabled, "LOCAL_LLM_REPLAY_DISABLED_FAIL_CLOSED", "local_llm_replay_disabled_fail_closed_count"),
        (unavailable, "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED", "local_llm_unavailable_fail_closed_count"),
    ):
        v4711.check_report(report)
        counters = report["counters"]
        assert counters["llm_invoked_count"] == 0
        assert counters["generated_response_count"] == 0
        assert counters["parsed_final_answer_present_count"] == 0
        assert counters["raw_llm_response_present_count"] == 0
        assert counters[expected_counter] == counters["v4_7_10_answer_replay_candidate_count"]
        assert counters["noop_or_extractive_generator_used"] is False
        assert all(row["answer_replay_audit"]["status"] == expected_status for row in report["pdf_answer_replay_rows"])
        assert all(row["answer_replay_audit"]["llm_invoked"] is False for row in report["pdf_answer_replay_rows"])
        assert all(row["answer_replay_audit"]["generated_response_created"] is False for row in report["pdf_answer_replay_rows"])
        assert all(row["answer_replay_audit"]["raw_prompt_created"] is False for row in report["pdf_answer_replay_rows"])
        assert all(row["answer_replay_audit"]["raw_llm_response_created"] is False for row in report["pdf_answer_replay_rows"])
        assert all(row["answer_replay_audit"]["parsed_final_answer_present"] is False for row in report["pdf_answer_replay_rows"])
        assert all(not row.get("final_answer") for row in report["pdf_answer_replay_rows"])

    mutated = json.loads(json.dumps(disabled))
    mutated["pdf_answer_replay_rows"][0]["final_answer"] = "old extractive fallback answer"
    mutated["pdf_answer_replay_rows"][0]["rendered_citations"] = ["evidence_1"]
    try:
        v4711.check_report(mutated)
    except ValueError as exc:
        assert "fail-closed row carried answer payload" in str(exc)
    else:
        raise AssertionError("v4_7_11 check_report accepted a fail-closed answer payload")


def test_v4711_response_leakage_flags_are_hard_failures() -> None:
    from ai.eval import rag_v4711_actual_llm_answer_replay_and_silver_diagnostic_smoke as v4711

    def leaking_client(prompt: str) -> str:
        payload = json.loads(prompt)
        evidence = str(payload.get("bounded_evidence_excerpt") or "근거")
        return json.dumps(
            {
                "final_answer": f"{evidence} expected supporting source_file_title",
                "abstain": False,
                "citations": ["evidence_1"],
                "answer_plan": "leakage regression fixture",
                "unsupported_claim_risk": False,
                "evidence_underuse_flag": False,
                "context_understanding_miss": False,
                "over_abstain_candidate": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    report = v4711.build_report(
        root=ROOT,
        execute=True,
        sync_surfaces=False,
        env={"RAG_V4_7_11_ENABLE_LOCAL_LLM_REPLAY": "1"},
        llm_client=leaking_client,
        generated_at="2026-05-30T00:00:00Z",
        check=False,
    )
    assert report["counters"]["response_leakage_flag_count"] == 9
    try:
        v4711.check_report(report)
    except ValueError as exc:
        assert "response_leakage_flag_count" in str(exc)
    else:
        raise AssertionError("v4_7_11 check_report accepted response leakage")


def test_v4711_answer_review_packet_is_ignored_compact_and_status_has_no_raw_payloads() -> None:
    from ai.eval import rag_v4711_actual_llm_answer_replay_and_silver_diagnostic_smoke as v4711

    report = v4711.build_report(
        root=ROOT,
        execute=True,
        sync_surfaces=False,
        env={"RAG_V4_7_11_ENABLE_LOCAL_LLM_REPLAY": "1"},
        llm_client=_fake_strict_korean_answer,
        generated_at="2026-05-30T00:00:00Z",
    )
    paths = report["artifact_paths"]
    answer_packet = ROOT / paths["answer_review_packet_jsonl"]
    assert paths["report_json"] == "ai/eval/reports/rag-ingestion/runs/v4_7_11/report.json"
    assert paths["answer_review_packet_jsonl"] == (
        "ai/eval/reports/rag-ingestion/runs/v4_7_11/answer_review_packet_ko.jsonl"
    )
    for rel_path in (paths["report_json"], paths["answer_review_packet_jsonl"]):
        result = subprocess.run(["git", "check-ignore", "-q", rel_path], cwd=ROOT)
        assert result.returncode == 0, rel_path
    assert answer_packet.parent == V4_7_11_REPORT.parent

    event = v4711.status_event(report, report_sha256="0" * 64, answer_packet_sha256="1" * 64)
    event_text = json.dumps(event, ensure_ascii=False)
    assert event["answer_review_packet_row_count"] == 9
    assert event["artifact_paths"]["answer_review_packet_jsonl"] == paths["answer_review_packet_jsonl"]
    assert event["raw_llm_response_present_count"] == 0
    for forbidden in ("raw_prompt_payload", "raw_response_payload", "prompt_payload", '"final_answer":'):
        assert forbidden not in event_text


def test_v4711_silver_diagnostic_smoke_is_bounded_or_fail_closed_plan_only() -> None:
    from ai.eval import rag_v4711_actual_llm_answer_replay_and_silver_diagnostic_smoke as v4711

    report = v4711.build_report(
        root=ROOT,
        execute=True,
        sync_surfaces=False,
        env={"RAG_V4_7_11_ENABLE_LOCAL_LLM_REPLAY": "1"},
        llm_client=_fake_strict_korean_answer,
        generated_at="2026-05-30T00:00:00Z",
    )
    v4711.check_report(report)
    smoke = report["silver_diagnostic_smoke"]
    counters = report["counters"]

    assert smoke["diagnostic_silver_only"] is True
    assert smoke["official_metric_input_rows"] == 0
    assert smoke["silver_promoted_to_gold_count"] == 0
    assert counters["silver_official_metric_input_rows"] == 0
    assert counters["silver_promoted_to_gold_count"] == 0
    if smoke["executed"]:
        assert counters["silver_smoke_sample_count"] <= smoke["target_sample_count"]
        assert counters["silver_smoke_text_count"] <= 10
        assert counters["silver_smoke_pdf_count"] <= 10
        assert counters["silver_smoke_xlsx_count"] <= 10
        assert counters["silver_llm_invoked_count"] == counters["silver_smoke_sample_count"]
    else:
        assert smoke["status"].endswith("_FAIL_CLOSED")
        assert smoke["blocked_reason"]
        assert smoke["plan"]["target_sample_count"] == 30
        assert counters["silver_llm_invoked_count"] == 0
        assert counters["silver_generated_response_count"] == 0


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
    latest = next(
        row
        for row in reversed(_read_jsonl(STATUS_JSONL))
        if row.get("short_run_id") == V4_7_9_SHORT_RUN_ID
    )
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
    assert counters["residual_weak_evidence_window_count_after"] == 3
    assert counters["missing_neighbor_context_count_before"] == 10
    assert counters["missing_neighbor_context_count_after"] == counters["residual_weak_evidence_window_count_after"]
    assert counters["repaired_evidence_bundle_count"] == 7
    assert counters["answer_replay_candidate_count"] == 7
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
    dropped_residual_rows = [row for row in residual_rows if not row["v4_7_9_repair_applied"]]
    assert len(prior_ready_rows) == 48
    assert len(residual_rows) == 10
    assert len(repaired_rows) == counters["repaired_evidence_bundle_count"]
    assert [row["query_id"] for row in dropped_residual_rows] == [
        "v4_7_pdf_query_04_03",
        "v4_7_pdf_query_04_04",
        "v4_7_pdf_query_04_05",
    ]
    assert all(row["repair_audit"]["decision"] == "dropped" for row in dropped_residual_rows)
    assert all(row["answer_replay_audit"]["answer_replay_candidate"] is False for row in dropped_residual_rows)
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


def test_v4710_korean_evidence_normalization_repairs_compacted_sourceatom_spans_without_gold() -> None:
    from ai.eval import rag_v4710_pdf_korean_evidence_normalization_and_answer_replay_readiness as v4710

    decision = v4710.korean_normalized_repair_decision(
        query_text="조달사업의 환경 변화에 따른 조달특별회계의 중장기적 운영 개선을 위한 수수료 체계 확립에 대해 어떤 내용이 제시되어 있습니까?",
        evidence_text="조달사업의환경변화에따른조달특별회계중장기적운영개선을위한수수료체계확립및",
        inherited_overlap=0,
    )

    assert decision["decision"] == "repaired"
    assert decision["reason"] == "spacing_insensitive_korean_query_evidence_overlap"
    assert decision["normalization_scope"] == "query_text_and_existing_sourceatom_span_only"
    assert decision["query_evidence_token_overlap_count"] >= 4
    assert decision["spacing_insensitive_korean_overlap_count"] >= 4
    assert decision["normalization_applied"] is True
    assert decision["source_text_added_from_raw_pdf"] is False
    assert decision["expected_or_supporting_gold_text_used"] is False
    assert decision["direct_answer_value_matching_used"] is False


def test_v4710_korean_evidence_normalization_drops_empty_short_or_unrelated_existing_spans() -> None:
    from ai.eval import rag_v4710_pdf_korean_evidence_normalization_and_answer_replay_readiness as v4710

    for evidence_text in (None, "", "조달사업", "친환경비료공장운영개선정책참고자료로활용"):
        decision = v4710.korean_normalized_repair_decision(
            query_text="조달특별회계 수수료 운영개선 방안은 무엇인가요?",
            evidence_text="" if evidence_text is None else evidence_text,
            inherited_overlap=0,
        )

        assert decision["decision"] == "dropped", evidence_text
        assert decision["raw_pdf_query_time_parsing"] is False
        assert decision["expected_or_supporting_gold_text_used"] is False
        assert decision["direct_answer_value_matching_used"] is False

    numeric_only = v4710.korean_normalized_repair_decision(
        query_text="2020년 조달특별회계 수수료 운영개선 방안은 무엇인가요?",
        evidence_text="2020년 친환경비료 공장 운영 개선 정책 참고자료로 활용되었습니다.",
        inherited_overlap=0,
    )

    assert numeric_only["decision"] == "dropped"
    assert numeric_only["numeric_overlap_count"] == 1
    assert numeric_only["spacing_insensitive_korean_overlap_count"] < 4


def test_v4710_pdf_korean_evidence_normalization_reduces_v479_residuals_and_records_replay_readiness() -> None:
    report = _load_v4710_report()
    status_rows = _read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    latest = next(
        (
            row
            for row in reversed(status_rows)
            if row.get("short_run_id") == V4_7_10_SHORT_RUN_ID
        ),
        None,
    )
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")

    assert report["short_run_id"] == V4_7_10_SHORT_RUN_ID
    assert report["canonical_long_run_id"] == V4_7_10_LONG_RUN_ID
    assert report["status"] == V4_7_10_STATUS
    assert report["source_run_id"] == V4_7_9_SHORT_RUN_ID
    assert report["source_report_json"] == "ai/eval/reports/rag-ingestion/runs/v4_7_9/report.json"
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
    assert counters["answer_ready_evidence_bundle_count_before"] == 55
    assert counters["answer_ready_evidence_bundle_count"] == 57
    assert counters["v4_7_9_residual_weak_evidence_window_count_before"] == 3
    assert counters["residual_weak_evidence_window_count_before"] == 3
    assert counters["residual_weak_evidence_window_count_after"] == 1
    assert counters["missing_neighbor_context_count_after"] == counters["residual_weak_evidence_window_count_after"]
    assert counters["korean_normalization_repair_count"] == 2
    assert counters["korean_normalized_evidence_repair_count"] == 2
    assert counters["newly_repaired_evidence_bundle_count"] == counters["korean_normalization_repair_count"]
    assert counters["new_answer_replay_ready_count"] == 2
    assert counters["answer_replay_ready_count"] == 9
    assert counters["regression_count_for_v4_7_9_answer_ready_rows"] == 0
    assert counters["llm_invoked_count"] == 0
    assert counters["generated_response_count"] == 0
    assert counters["local_llm_unavailable_fail_closed_count"] == counters["answer_replay_candidate_count"]
    assert counters["official_metric_input_rows"] == 0
    assert counters["protected_namespaces_touched"] == []

    rows = report["pdf_residual_replay_rows"]
    assert len(rows) == 58
    targeted_rows = [row for row in rows if row["v4_7_10_repair_targeted"]]
    repaired_rows = [row for row in rows if row["v4_7_10_repair_applied"]]
    remaining_rows = [row for row in rows if row["weak_evidence_window"]]
    assert len(targeted_rows) == 3
    assert [row["query_id"] for row in targeted_rows] == [
        "v4_7_pdf_query_04_03",
        "v4_7_pdf_query_04_04",
        "v4_7_pdf_query_04_05",
    ]
    assert [row["query_id"] for row in repaired_rows] == [
        "v4_7_pdf_query_04_04",
        "v4_7_pdf_query_04_05",
    ]
    assert [row["query_id"] for row in remaining_rows] == ["v4_7_pdf_query_04_03"]
    assert len(repaired_rows) == counters["korean_normalization_repair_count"]
    assert len(remaining_rows) == counters["residual_weak_evidence_window_count_after"]
    assert all(row["SourceAtom_EvidenceBundle_role"] == "evidence_truth" for row in rows)
    assert all(row["SearchView_vector_payload_role"] == "candidate_only" for row in rows)
    assert all(row["raw_pdf_query_time_parsing"] is False for row in rows)
    assert all(row["hidden_target_locator_used"] is False for row in rows)
    assert all(row["expected_or_supporting_gold_text_used"] is False for row in rows)
    assert all(row["source_file_title_shortcut_used"] is False for row in rows)
    assert all(row["direct_answer_value_matching_used"] is False for row in rows)
    assert all(row["full_page_dump_used"] is False for row in rows)
    assert all(
        row["repair_audit"]["reason"] == "spacing_insensitive_korean_query_evidence_overlap"
        for row in repaired_rows
    )
    assert all(
        row["repair_audit"]["spacing_insensitive_korean_overlap_count"] >= 2
        for row in repaired_rows
    )
    assert all(
        row["answer_replay_audit"]["status"] == "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"
        for row in rows
        if row["answer_replay_audit"]["answer_replay_candidate"]
    )
    assert report["remaining_residual_rows"] == [
        {
            "row_index_1based": row["row_index_1based"],
            "candidate_id_hash": row["candidate_id_hash"],
            "query_id_hash": row["query_id_hash"],
            "reason": row["repair_audit"]["reason"],
        }
        for row in remaining_rows
    ]

    if latest is not None:
        assert latest["short_run_id"] == V4_7_10_SHORT_RUN_ID
        assert latest["artifact_paths"]["report_json"] == "ai/eval/reports/rag-ingestion/runs/v4_7_10/report.json"
        if V4_7_10_REPORT.exists():
            assert latest["artifact_sha256"]["report_json_sha256"] == _sha256_file(V4_7_10_REPORT)
        assert latest["official_metric"] is False
        assert latest["official_metric_input_rows"] == 0

    before_after = (
        f"weak evidence/window {counters['residual_weak_evidence_window_count_before']} -> "
        f"{counters['residual_weak_evidence_window_count_after']}"
    )
    for text in (progress, measurements, triage, root_readme, eval_readme, scripts_readme):
        assert V4_7_10_SHORT_RUN_ID in text
        assert before_after in text
        assert "official_metric=false" in text or "official metric" in text
    assert "spacing-insensitive Korean evidence normalization" in triage
    assert "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED" in measurements

    generated_text = "\n".join(
        [
            json.dumps(report, ensure_ascii=False),
            json.dumps(latest or {}, ensure_ascii=False),
            measurements.split("### v4_7_10", 1)[1].split("\n### ", 1)[0],
            triage.split("### v4_7_10", 1)[1].split("\n### ", 1)[0],
        ]
    )
    for pattern in (
        r"\b[A-Z]:[\\/]",
        r"prompt_payload",
        r"raw_response_payload",
        r"promotion-ready",
    ):
        assert not re.search(pattern, generated_text), pattern


def test_v4711_docs_do_not_describe_current_as_v4710() -> None:
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    assert "use resolver key `current` for v4_7_10" not in eval_readme
    assert "use explicit resolver key `v4_7_10`" in eval_readme


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
