from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v6_6_structured_tool_operation_taxonomy_nonprod"
ROLLBACK_KEY = "v6_5_1_gold29_actual_response_smoke_nonprod"
STATUS = "V6_6_STRUCTURED_TOOL_OPERATION_TAXONOMY_NONPROD_READY"
LATEST_CURRENT_RUN_KEY = "v6_9_answer_quality_gate_packet_nonprod"
PROTECTED_PATHS = (
    "ai/eval/eval_queries",
    "ai/eval/source_registry",
    "ai/eval/indexes",
    "ai/eval/silver",
)
REQUIRED_TAXONOMY = {
    "pdf_page_span_extract",
    "pdf_locator_lookup",
    "text_span_lookup",
    "xlsx_table_slice",
    "xlsx_cell_lookup",
    "xlsx_filter",
    "xlsx_aggregate",
    "no_tool_required",
    "unsupported_tool_request",
    "tool_surface_unavailable",
    "tool_execution_failed",
    "tool_result_empty",
    "tool_result_hydration_failed",
}
REQUIRED_FALSE_FIELDS = {
    "official_metric",
    "retrieval_quality_metric_computed",
    "answer_quality_metric_computed",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_routing_enabled",
    "production_db_mutated",
    "production_index_mutation",
    "production_namespace_mutated",
    "production_cache_mutated",
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "relevance_label_mutation",
    "answerability_label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "official_denominator_mutation",
    "source_registry_mutated",
    "training_dataset_created",
    "fine_tuning_dataset_export_created",
    "fine_tuning_started",
    "fine_tuning_executed",
    "ft_a_execution",
    "raw_tool_payload_written",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
}
FORBIDDEN_PAYLOAD_KEYS = {
    "raw_tool_payload",
    "raw_prompt_payload",
    "raw_response_payload",
    "raw_llm_response",
    "expected_answer",
    "expected_answer_text",
    "supporting_evidence",
    "supporting_evidence_ids",
    "qrels_positive_ids",
    "qrels_positive_candidate_ids",
    "target_search_unit_id",
    "source_title",
    "source_file_name",
    "workbook",
    "row_id",
    "case_id",
}


def assert_no_exact_keys(value: object, forbidden_keys: set[str]) -> None:
    if isinstance(value, dict):
        assert not (set(value) & forbidden_keys)
        for child in value.values():
            assert_no_exact_keys(child, forbidden_keys)
    elif isinstance(value, list):
        for child in value:
            assert_no_exact_keys(child, forbidden_keys)


@pytest.fixture(scope="module")
def v66_module():
    from ai.eval import rag_v66_structured_tool_operation_taxonomy_nonprod as v66

    return v66


@pytest.fixture()
def report(v66_module) -> dict[str, object]:
    built = v66_module.build_report(root=ROOT, generated_at="2026-06-07T03:00:00Z")
    v66_module.check_report(built)
    return built


def test_v66_schema_current_and_rollback(report: dict[str, object]) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_eval_registry as registry

    assert registry.resolve_run(RUN_KEY, root=ROOT).logical_key == RUN_KEY
    assert registry.resolve_run("current", root=ROOT).logical_key == LATEST_CURRENT_RUN_KEY
    assert registry.resolve_run(ROLLBACK_KEY, root=ROOT).logical_key == ROLLBACK_KEY
    assert runner.DEFAULT_RUN_KEY == LATEST_CURRENT_RUN_KEY
    assert runner.check_run(RUN_KEY)["logical_run_key"] == RUN_KEY
    assert runner.check_run("current")["logical_run_key"] == LATEST_CURRENT_RUN_KEY
    assert runner.check_run(ROLLBACK_KEY)["logical_run_key"] == ROLLBACK_KEY

    assert report["run_id"] == RUN_KEY
    assert report["schema_version"] == "v6_6_structured_tool_operation_taxonomy_nonprod_report_v1"
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["current_resolves_to"] == RUN_KEY
    assert report["rollback_key"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["current_moved_from"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["current_moved_to"] == RUN_KEY


def test_v66_reads_v651_actual_response_smoke_as_rollback(report: dict[str, object]) -> None:
    source = report["source_v6_5_1_report_check"]

    assert source["run_key"] == ROLLBACK_KEY
    assert source["actual_response_rows_attempted"] == 29
    assert source["actual_response_rows_rendered"] == 10
    assert source["citation_verified_rows"] == 10
    assert source["fail_closed_rows"] == 19
    assert source["retrieval_quality_metric_computed"] is False
    assert source["answer_quality_metric_computed"] is False


def test_v66_tool_and_rag_metrics_are_separate(report: dict[str, object]) -> None:
    assert report["retrieval_quality_metric_computed"] is False
    assert report["answer_quality_metric_computed"] is False
    assert report["tool_metric_official"] is False
    assert report["tool_outputs_excluded_from_true_rag_metrics"] is True
    guard = report["tool_to_rag_leakage_guard"]
    assert guard["tool_success_contributed_to_hit_at_k"] is False
    assert guard["tool_success_contributed_to_mrr"] is False
    assert guard["tool_success_contributed_to_ndcg"] is False
    assert guard["tool_outputs_counted_as_rag_hit"] is False


def test_v66_tool_taxonomy_is_exhaustive(report: dict[str, object]) -> None:
    taxonomy = set(report["structured_tool_operation_taxonomy"])
    assert REQUIRED_TAXONOMY.issubset(taxonomy)
    assert report["tool_operation_summary"]["tool_operation_rows"] == 29
    assert report["tool_operation_summary"]["silently_dropped_rows"] == 0
    for row in report["tool_operation_rows"]:
        assert row["operation_state"] in taxonomy
        assert row["source_family"] in {"PDF", "TEXT", "XLSX"}
        assert row["gold_row_hash"]
        assert row["query_hash"]
        assert isinstance(row["tool_required"], bool)
        assert row["tool_supported"] is False
        assert row["tool_executed"] is False
        assert row["tool_result_available"] is False
        assert row["tool_result_hydrated_to_evidence_bundle"] is False
        assert isinstance(row["rag_candidate_count"], int)
        assert row["tool_output_used_for_rag_metric"] is False
        assert row["fail_closed_reason"] == "tool_surface_unavailable"
        assert row["raw_tool_payload_written"] is False
        assert row["raw_prompt_payload_written"] is False
        assert row["raw_response_payload_written"] is False
        assert_no_exact_keys(row, FORBIDDEN_PAYLOAD_KEYS)


def test_v66_structured_tool_family_coverage_is_diagnostic_only(report: dict[str, object]) -> None:
    summary = report["tool_operation_summary"]
    by_family = summary["rows_by_family"]

    assert by_family["PDF"] >= 1
    assert by_family["TEXT"] >= 3
    assert by_family["XLSX"] >= 5
    assert summary["tool_supported_rows"] == 0
    assert summary["tool_executed_rows"] == 0
    assert summary["tool_result_available_rows"] == 0
    assert summary["tool_result_hydrated_rows"] == 0
    assert summary["tool_metric_rows"] == 29
    assert summary["tool_metric_official"] is False


def test_v66_protected_boundaries_stay_closed(report: dict[str, object]) -> None:
    for field in REQUIRED_FALSE_FIELDS:
        assert report[field] is False, field
    assert report["official_metric_input_rows"] == 0
    assert report["official_metric_input_rows_created"] == 0
    assert report["official_metric_input_rows_consumed"] == 0
    assert report["candidate_generation_input_policy"]["expected_supporting_qrels_used_for_candidate_generation"] is False
    assert report["candidate_generation_input_policy"]["tool_outputs_used_for_candidate_generation"] is False
    assert report["candidate_generation_input_policy"]["prior_route_diagnostics_used_for_candidate_generation"] is False
    evidence = report["evidence_truth_boundary"]
    assert evidence["source_atom_evidence_bundle_role"] == "evidence_truth"
    assert evidence["search_view_vector_payload_role"] == "candidate_only"
    assert evidence["tool_output_role"] == "diagnostic_tool_result_only"
    assert evidence["tool_output_used_as_evidence_truth"] is False
    protected = report["protected_surface_check"]
    assert protected["passed"] is True
    assert protected["mutated_paths"] == []
    assert protected["protected_namespaces_touched"] == []
    assert_no_exact_keys(report, {"raw_tool_payload", "raw_prompt_payload", "raw_response_payload", "raw_llm_response"})


def test_v66_single_primary_report_status_docs_and_hash_contract(
    tmp_path: Path,
    v66_module,
    report: dict[str, object],
) -> None:
    written, hashes = v66_module.write_report_bundle(tmp_path, report)
    v66_module.check_report(written, root=tmp_path)
    v66_module.update_docs(tmp_path, written)
    v66_module.append_status(tmp_path, written, artifact_hashes=hashes)
    v66_module.require_status_report_hash(tmp_path, written)

    run_root = tmp_path / "reports/rag_eval/rag-ingestion/runs" / RUN_KEY
    assert (run_root / "report.json").exists()
    assert set(path.name for path in run_root.iterdir()) == {"report.json"}
    assert written["consolidated_report_policy"]["primary_report_only"] is True
    assert written["artifact_sha256"]["report_json_sha256"] == hashlib.sha256(
        (run_root / "report.json").read_bytes()
    ).hexdigest()

    status_rows = [
        json.loads(line)
        for line in (tmp_path / "reports/rag_eval/rag-ingestion/status.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert status_rows[-1]["logical_run_key"] == RUN_KEY
    assert status_rows[-1]["current_resolves_to"] == RUN_KEY
    assert status_rows[-1]["rollback_key"] == ROLLBACK_KEY
    assert status_rows[-1]["official_metric"] is False
    assert status_rows[-1]["artifact_sha256"]["report_json_sha256"] == written["artifact_sha256"]["report_json_sha256"]

    forbidden_sidecars = {
        "structured_tool_diagnostics.jsonl",
        "tool_metrics.json",
        "review_packet.csv",
        "review_packet.xlsx",
        "review_packet.jsonl",
        "metric_results.json",
        "agentic_loop_trace.jsonl",
        "true_rag_candidate_diagnostics.jsonl",
    }
    assert not (forbidden_sidecars & {path.name for path in run_root.iterdir()})

    for doc_name in ("rag-ingestion-progress.md", "rag-ingestion-measurements.md", "rag-ingestion-triage.md"):
        text = (tmp_path / "docs" / doc_name).read_text(encoding="utf-8")
        assert RUN_KEY in text
        assert "tool outputs are excluded from Hit@k/MRR/nDCG" in text
        assert "no official/product/promotion/live-readiness claim" in text.lower()


def test_protected_namespace_git_status_is_clean_for_v66() -> None:
    result = subprocess.run(
        ["git", "status", "--short", "--", *PROTECTED_PATHS],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.strip() == ""


@pytest.mark.parametrize(
    ("patch", "message"),
    (
        ({"current_resolves_to": ROLLBACK_KEY}, "current"),
        ({"tool_operation_summary": {"silently_dropped_rows": 1}}, "dropped"),
        ({"retrieval_quality_metric_computed": True}, "retrieval quality"),
        ({"tool_to_rag_leakage_guard": {"tool_success_contributed_to_hit_at_k": True}}, "tool"),
        ({"candidate_generation_input_policy": {"expected_supporting_qrels_used_for_candidate_generation": True}}, "candidate"),
    ),
)
def test_check_report_rejects_boundary_drift(
    report: dict[str, object],
    v66_module,
    patch: dict[str, object],
    message: str,
) -> None:
    poisoned = json.loads(json.dumps(report))
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(poisoned.get(key), dict):
            poisoned[key] = dict(poisoned[key], **value)
        else:
            poisoned[key] = value

    with pytest.raises(ValueError, match=message):
        v66_module.check_report(poisoned)
