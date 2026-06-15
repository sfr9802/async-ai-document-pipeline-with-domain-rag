from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sample_probe_row() -> dict[str, object]:
    return {
        "row_id": "row-001",
        "query_id": "query-001",
        "source_family": "TEXT",
        "retrieval_metric_eligible": True,
        "target_search_unit_id": "target-su",
        "qrels_positive_candidate_ids": ["target-su"],
        "baseline_topk_new": ["target-su", "diagnostic-text-a", "diagnostic-text-b"],
        "candidate_ids": ["target-su", "diagnostic-text-a", "diagnostic-text-b"],
        "supporting_evidence_id": "supporting-001",
        "citation_locator": "page=1",
        "expected_answer": "forbidden for candidate scoring",
    }


def test_v571_report_restates_v57_ones_as_baseline_parity_without_live_metric() -> None:
    from ai.eval import rag_v571_retrieval_metric_integrity_audit_diagnostic_nonprod as v571

    report = v571.build_report(root=ROOT, generated_at="2026-06-06T00:00:00Z")
    v571.check_report(report)

    assert report["logical_run_key"] == "v5_7_1_retrieval_metric_integrity_audit"
    assert report["short_run_id"] == "v5_7_1_retrieval_metric_integrity_audit_diagnostic_nonprod"
    assert report["source_v5_7_logical_run_key"] == "v5_7_vector_llm_candidate_routing"
    assert report["current_resolves_to"] == "v5_6"
    assert report["diagnostic_only"] is True
    assert report["official_metric"] is False
    assert report["answer_metric_rows"] == 0
    assert report["scored_answer_rows"] == 0
    assert report["answer_quality_metric_computed"] is False
    assert report["source_official_metric_input_rows"] == 29
    assert report["route_comparison_rows"] == 29
    assert report["retrieval_metric_eligible_rows_prior"] == 28
    assert report["metric_restatement_required"] is True
    assert (
        report["v5_7_prior_metric_interpretation"]
        == "diagnostic parity/replay only; not product retrieval quality"
    )
    assert report["product_retrieval_quality_claim_supported"] is False

    assert report["baseline_parity_only_rows"] == 28
    assert report["oracle_or_target_seeded_rows"] == 0
    assert report["synthetic_distractor_only_rows"] == 0
    assert report["valid_live_retrieval_metric_rows"] == 0
    assert report["valid_live_retrieval_metric_computed"] is False

    restatement = report["metric_restatement"]
    assert restatement["v5_7_valid_live_retrieval_metric"]["computed"] is False
    assert restatement["v5_7_valid_live_retrieval_metric"]["denominator"] == 0
    assert restatement["v5_7_baseline_parity_metric"]["denominator"] == 28
    assert restatement["v5_7_baseline_parity_metric"]["metrics"] == {
        "hit_at_1": 1.0,
        "hit_at_3": 1.0,
        "hit_at_5": 1.0,
        "mrr_at_5": 1.0,
        "ndcg_at_5": 1.0,
    }
    assert restatement["v5_7_oracle_seeded_or_synthetic_candidate_metric"]["denominator"] == 0


def test_v571_candidate_origin_audit_records_baseline_replay_and_synthetic_distractors() -> None:
    from ai.eval import rag_v571_retrieval_metric_integrity_audit_diagnostic_nonprod as v571

    report = v571.build_report(root=ROOT, generated_at="2026-06-06T00:00:00Z")
    rows = report["candidate_origin_audit"]
    eligible_rows = [row for row in rows if row["retrieval_metric_eligible"] is True]

    assert len(rows) == 29
    assert len(eligible_rows) == 28
    assert report["candidate_list_identical_to_baseline_topk_new_count"] == 29
    assert report["top1_equals_target_search_unit_id_count"] == 29
    assert report["baseline_topk_replay_count"] == 145
    assert report["target_seeded_candidate_count"] == 0
    assert report["qrels_seeded_candidate_count"] == 0
    assert report["synthetic_candidate_count"] == 116
    assert report["real_non_target_candidate_count"] == 0

    first = rows[0]
    required = {
        "row_id",
        "query_id",
        "source_family",
        "retrieval_metric_eligible",
        "target_search_unit_id",
        "candidate_ids",
        "candidate_origin",
        "top1_origin",
        "target_rank",
        "candidate_count",
        "synthetic_candidate_count",
        "real_non_target_candidate_count",
        "candidate_list_identical_to_baseline_topk_new",
        "top1_equals_target_search_unit_id",
        "metric_validity_bucket",
    }
    assert required <= set(first)
    assert first["candidate_list_identical_to_baseline_topk_new"] is True
    assert first["top1_equals_target_search_unit_id"] is True
    assert first["top1_origin"] == "baseline_topk_replay"
    assert first["target_rank"] == 1
    assert first["candidate_count"] == 5
    assert first["synthetic_candidate_count"] == 4
    assert first["real_non_target_candidate_count"] == 0
    assert first["metric_validity_bucket"] == "baseline_parity_only"
    assert first["candidate_origin"][0]["candidate_origin"] == "baseline_topk_replay"
    assert {entry["candidate_origin"] for entry in first["candidate_origin"][1:]} == {
        "diagnostic_synthetic_distractor"
    }


def test_v571_probe_helpers_fail_target_qrels_baseline_and_identity_dependent_generators() -> None:
    from ai.eval import rag_v571_retrieval_metric_integrity_audit_diagnostic_nonprod as v571

    row = _sample_probe_row()

    target_probe = v571.run_leakage_probes_for_row(
        row,
        candidate_generator=lambda mutated: [mutated["target_search_unit_id"], "diagnostic-text-a"],
    )
    assert target_probe["probes"]["target_search_unit_id_poison"]["candidate_list_changed"] is True
    assert target_probe["leakage_probe_failed"] is True

    qrels_probe = v571.run_leakage_probes_for_row(
        row,
        candidate_generator=lambda mutated: list(mutated["qrels_positive_candidate_ids"]),
    )
    assert qrels_probe["probes"]["qrels_positive_poison"]["candidate_list_changed"] is True
    assert qrels_probe["leakage_probe_failed"] is True

    baseline_probe = v571.run_leakage_probes_for_row(
        row,
        candidate_generator=lambda mutated: list(mutated["baseline_topk_new"]),
    )
    assert baseline_probe["probes"]["baseline_topk_new_shuffle"]["candidate_list_changed"] is True
    assert baseline_probe["leakage_probe_failed"] is True

    identity_probe = v571.run_leakage_probes_for_row(
        row,
        candidate_generator=lambda mutated: ["id-sensitive"] if mutated["query_id"] == "query-001" else [],
    )
    assert identity_probe["probes"]["query_row_id_poison"]["candidate_list_changed"] is True
    assert identity_probe["identity_poison_failed"] is True
    assert identity_probe["leakage_probe_failed"] is True


def test_v571_live_metric_excludes_baseline_replay_synthetic_only_and_poison_failed_rows() -> None:
    from ai.eval import rag_v571_retrieval_metric_integrity_audit_diagnostic_nonprod as v571

    baseline_row = {
        **_sample_probe_row(),
        "candidate_ids": ["target-su", "diagnostic-text-a"],
        "baseline_topk_new": ["target-su", "diagnostic-text-a"],
    }
    baseline_audit = v571.audit_candidate_origin_row(baseline_row, leakage_probe_failed=True)
    assert baseline_audit["metric_validity_bucket"] == "baseline_parity_only"
    assert v571.row_counts_for_valid_live_retrieval_metric(baseline_audit) is False

    synthetic_row = {
        **_sample_probe_row(),
        "target_search_unit_id": "target-su",
        "candidate_ids": ["diagnostic-text-a", "diagnostic-text-b"],
        "baseline_topk_new": ["diagnostic-text-a", "diagnostic-text-b"],
    }
    synthetic_audit = v571.audit_candidate_origin_row(synthetic_row, leakage_probe_failed=False)
    assert synthetic_audit["metric_validity_bucket"] == "synthetic_distractor_only"
    assert v571.row_counts_for_valid_live_retrieval_metric(synthetic_audit) is False

    live_row = {
        **_sample_probe_row(),
        "candidate_ids": ["live-su-1", "target-su"],
        "baseline_topk_new": ["target-su", "diagnostic-text-a"],
        "candidate_origin_override": {
            "live-su-1": "live_vector_search",
            "target-su": "live_vector_search",
        },
    }
    live_audit = v571.audit_candidate_origin_row(live_row, leakage_probe_failed=False)
    assert live_audit["metric_validity_bucket"] == "valid_live_retrieval"
    assert v571.row_counts_for_valid_live_retrieval_metric(live_audit) is True


def test_v571_written_artifacts_status_and_runner_are_additive(tmp_path: Path) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_v571_retrieval_metric_integrity_audit_diagnostic_nonprod as v571

    report = v571.build_report(root=ROOT, generated_at="2026-06-06T00:00:00Z")
    written, artifact_hashes = v571.write_report_bundle(tmp_path, report)
    v571.check_report(written, root=tmp_path)
    v571.append_status(tmp_path, written, artifact_hashes=artifact_hashes)

    expected_paths = {
        "report_json": "reports/rag_eval/rag-ingestion/runs/v5_7_1_retrieval_metric_integrity_audit/report.json",
        "metric_integrity_audit_jsonl": (
            "reports/rag_eval/rag-ingestion/runs/v5_7_1_retrieval_metric_integrity_audit/"
            "metric_integrity_audit.jsonl"
        ),
        "candidate_origin_audit_jsonl": (
            "reports/rag_eval/rag-ingestion/runs/v5_7_1_retrieval_metric_integrity_audit/"
            "candidate_origin_audit.jsonl"
        ),
        "leakage_probe_results_jsonl": (
            "reports/rag_eval/rag-ingestion/runs/v5_7_1_retrieval_metric_integrity_audit/"
            "leakage_probe_results.jsonl"
        ),
        "metric_restatement_json": (
            "reports/rag_eval/rag-ingestion/runs/v5_7_1_retrieval_metric_integrity_audit/"
            "metric_restatement.json"
        ),
        "status_jsonl": "reports/rag_eval/rag-ingestion/status.jsonl",
    }
    assert written["artifact_paths"] == expected_paths
    for key, path in expected_paths.items():
        if key == "status_jsonl":
            continue
        assert artifact_hashes[f"{key}_sha256"] == _sha256_file(tmp_path / path)

    assert len(_read_jsonl(tmp_path / expected_paths["metric_integrity_audit_jsonl"])) == 29
    assert len(_read_jsonl(tmp_path / expected_paths["candidate_origin_audit_jsonl"])) == 29
    assert len(_read_jsonl(tmp_path / expected_paths["leakage_probe_results_jsonl"])) == 29

    status_rows = _read_jsonl(tmp_path / "reports/rag_eval/rag-ingestion/status.jsonl")
    latest = status_rows[-1]
    assert latest["short_run_id"] == written["short_run_id"]
    assert latest["metric_restatement_required"] is True
    assert latest["valid_live_retrieval_metric_rows"] == 0
    assert latest["valid_live_retrieval_metric_computed"] is False
    assert latest["baseline_parity_only_rows"] == 28
    assert latest["leakage_probe_failed_count"] == 29
    assert latest["current_resolves_to"] == "v5_6"

    checked = runner.check_run("v5_7_1_retrieval_metric_integrity_audit")
    assert checked["short_run_id"] == written["short_run_id"]
    assert runner.check_run("current")["short_run_id"] == "v5_6_official_metric_scored_execution_and_failure_attribution_nonprod"


def test_v571_check_report_rejects_product_claims_opened_gates_and_protected_mutations() -> None:
    from ai.eval import rag_v571_retrieval_metric_integrity_audit_diagnostic_nonprod as v571

    report = v571.build_report(root=ROOT, generated_at="2026-06-06T00:00:00Z")
    v571.check_report(report)

    for path, value, message in (
        (("diagnostic_only",), False, "diagnostic"),
        (("official_metric",), True, "official"),
        (("answer_metric_rows",), 1, "answer metric"),
        (("scored_answer_rows",), 1, "scored answer"),
        (("answer_quality_metric_computed",), True, "answer quality"),
        (("valid_live_retrieval_metric_computed",), True, "valid live retrieval metric"),
        (("valid_live_retrieval_metric_rows",), 1, "valid live retrieval denominator"),
        (("metric_restatement_required",), False, "metric restatement"),
        (("product_retrieval_quality_claim_supported",), True, "product retrieval quality"),
        (("source_official_metric_input_rows",), 30, "source official"),
        (("route_comparison_rows",), 30, "route comparison"),
        (("retrieval_metric_eligible_rows_prior",), 29, "retrieval metric"),
        (("protected_namespaces_touched",), ["ai/eval/eval_queries"], "protected"),
        (("gold_mutation",), True, "closed gate"),
        (("qrels_mutation",), True, "closed gate"),
        (("expected_answer_mutation",), True, "closed gate"),
        (("supporting_evidence_mutation",), True, "closed gate"),
        (("denominator_mutation",), True, "closed gate"),
        (("metric_restatement", "v5_7_valid_live_retrieval_metric", "computed"), True, "valid live retrieval metric"),
        (("candidate_origin_audit", 0, "metric_validity_bucket"), "valid_live_retrieval", "bucket"),
    ):
        mutated = json.loads(json.dumps(report))
        cursor = mutated
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        with pytest.raises(ValueError, match=message):
            v571.check_report(mutated)
