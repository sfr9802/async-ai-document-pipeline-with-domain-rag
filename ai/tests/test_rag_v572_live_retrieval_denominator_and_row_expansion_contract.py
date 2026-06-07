from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def v572_report() -> dict[str, object]:
    from ai.eval import rag_v572_live_retrieval_denominator_and_row_expansion_diagnostic_nonprod as v572

    report = v572.build_report(root=ROOT, generated_at="2026-06-06T00:00:00Z")
    v572.check_report(report)
    return report


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_v572_candidate_generator_fence_rejects_target_qrels_baseline_identity_and_gold_fields() -> None:
    from ai.eval import rag_v572_live_candidate_generator as generator

    safe = generator.sanitized_candidate_request(query_text="질문 본문", source_family="TEXT")
    assert set(safe) == set(generator.ALLOWED_REQUEST_FIELDS)

    forbidden_fields = {
        "target_search_unit_id": "target",
        "qrels_positive_candidate_ids": ["target"],
        "baseline_topk_new": ["target"],
        "query_id": "qid",
        "row_id": "rid",
        "expected_answer_ko": "answer",
        "supporting_evidence_ids": ["evidence"],
        "citation_locator": {"page": 1},
        "source_workbook": "shortcut.xlsx",
        "raw_local_path": "D:/secret/source.xlsx",
    }
    for field, value in forbidden_fields.items():
        request = dict(safe)
        request[field] = value
        with pytest.raises(ValueError, match="fence violation"):
            generator.assert_candidate_request_fence(request)


def test_v572_candidate_generator_dependency_audit_and_missing_index_fail_closed_without_answer() -> None:
    from ai.eval import rag_v572_live_candidate_generator as generator

    audit = generator.candidate_generator_dependency_audit()
    assert audit["forbidden_import_count"] == 0
    assert audit["protected_artifact_path_mention_count"] == 0
    assert audit["allowed_read_artifacts"] == ["ai/eval/source_registry/source_atom_registry_v1.jsonl"]

    request = generator.sanitized_candidate_request(query_text="없는 인덱스에서도 답을 만들면 안 된다", source_family="TEXT")
    sealed = generator.generate_sealed_candidates_in_process(root=ROOT / "does-not-exist", requests=[request])
    row = sealed["candidate_rows"][0]
    assert row["fail_closed"] is True
    assert row["fail_closed_reason"] == "missing_source_registry"
    assert row["candidate_ids"] == []
    assert row["answer_generated"] is False
    assert row["fake_noop_answer_used"] is False


def test_v572_report_opens_runlocal_live_denominator_without_product_or_answer_quality_claims(
    v572_report: dict[str, object],
) -> None:
    report = v572_report
    assert report["logical_run_key"] == "v5_7_2_live_retrieval_denominator_and_row_expansion"
    assert report["current_resolves_to"] == "v5_6"
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["source_official_metric_input_rows"] == 29
    assert report["answer_metric_rows"] == 0
    assert report["scored_answer_rows"] == 0
    assert report["answer_quality_metric_computed"] is False
    assert report["quality_delta_claim_supported"] is False
    assert report["product_retrieval_quality_claim_supported"] is False
    assert report["prior_v5_7_metric_reclassified_as"] == "baseline_parity_metric"

    assert report["candidate_generation_fence_verified"] is True
    assert report["candidate_generation_process_isolated"] is True
    assert report["candidate_generator_query_id_feature_used"] is False
    assert report["candidate_generator_row_id_feature_used"] is False
    assert report["candidate_generator_target_qrels_baseline_feature_used"] is False
    assert report["valid_live_retrieval_metric_rows"] > 0
    assert report["valid_live_retrieval_metric_computed"] is True
    assert report["valid_live_retrieval_metric"]["computed"] is True
    assert report["valid_live_retrieval_metric"]["denominator"] == report["valid_live_retrieval_metric_rows"]
    assert report["valid_live_retrieval_metric"]["not_product_retrieval_quality"] is True


def test_v572_leakage_probes_pass_for_sealed_generation_and_fail_when_poison_changes_candidates(
    v572_report: dict[str, object],
) -> None:
    from ai.eval import rag_v572_live_retrieval_denominator_and_row_expansion_diagnostic_nonprod as v572

    report = v572_report
    assert report["leakage_probe_failed_count"] == 0
    assert report["target_qrels_baseline_leakage_failed_count"] == 0
    assert report["identity_leakage_failed_count"] == 0
    assert report["source_shortcut_dependency_failed_count"] == 0
    for row in report["leakage_probe_results"]:
        assert all(probe["candidate_list_changed"] is False for probe in row["probes"].values())

    bad = v572.classify_leakage_probe_result(
        scoring_row={"row_id": "r", "query_id": "q", "source_family": "TEXT", "retrieval_metric_eligible": True},
        original_candidate_ids=["a", "b"],
        mutated_candidate_ids_by_probe={
            "target_search_unit_id_poison": ["target"],
            "qrels_positive_poison": ["qrels"],
            "baseline_topk_new_removed_or_shuffled": ["b", "a"],
            "supporting_expected_citation_removed": ["a"],
            "query_row_id_poison": ["identity-sensitive"],
            "source_title_workbook_filename_redaction": ["shortcut-sensitive"],
        },
    )
    assert bad["leakage_probe_failed"] is True
    assert bad["target_qrels_baseline_leakage_failed"] is True
    assert bad["identity_leakage_failed"] is True
    assert bad["source_shortcut_dependency_failed"] is True


def test_v572_query_id_row_id_poison_does_not_change_sanitized_candidate_requests() -> None:
    from ai.eval import rag_v572_live_retrieval_denominator_and_row_expansion_diagnostic_nonprod as v572

    v57_report = json.loads((ROOT / v572.SOURCE_V57_REPORT_PATH).read_text(encoding="utf-8"))
    official_rows = _read_jsonl(ROOT / v572.SOURCE_OFFICIAL_INPUT_PATH)
    v57_rows = list(v57_report["route_candidate_diagnostics"])
    original = v572.build_sanitized_requests_from_packet(v57_rows=v57_rows, official_rows=official_rows)
    poisoned = [dict(row, query_id=f"poison-{index}", row_id=f"poison-row-{index}") for index, row in enumerate(v57_rows)]
    mutated = v572.build_sanitized_requests_from_packet(v57_rows=poisoned, official_rows=official_rows)
    assert mutated == original


def test_v572_baseline_replay_and_synthetic_only_rows_are_excluded_from_live_denominator() -> None:
    from ai.eval import rag_v572_live_retrieval_denominator_and_row_expansion_diagnostic_nonprod as v572

    base_row = {
        "row_id": "row",
        "query_id": "query",
        "source_family": "TEXT",
        "retrieval_metric_eligible": True,
        "baseline_target_search_unit_id": "target",
        "baseline_topk_new": ["target", "diagnostic-a"],
    }
    stable_leakage = {
        "leakage_probe_failed": False,
        "identity_leakage_failed": False,
        "source_shortcut_dependency_failed": False,
    }
    baseline_audit = v572.audit_candidate_origin_row(
        base_row,
        {
            "candidate_ids": ["target", "diagnostic-a"],
            "candidate_origin": [
                {"candidate_id": "target", "candidate_origin": "baseline_topk_replay", "rank": 1},
                {"candidate_id": "diagnostic-a", "candidate_origin": "diagnostic_synthetic_distractor", "rank": 2},
            ],
        },
        stable_leakage,
    )
    assert baseline_audit["metric_validity_bucket"] == "baseline_parity_only"
    assert v572.row_counts_for_valid_live_retrieval_metric(baseline_audit) is False

    synthetic_audit = v572.audit_candidate_origin_row(
        {**base_row, "baseline_topk_new": []},
        {
            "candidate_ids": ["diagnostic-a", "diagnostic-b"],
            "candidate_origin": [
                {"candidate_id": "diagnostic-a", "candidate_origin": "diagnostic_synthetic_distractor", "rank": 1},
                {"candidate_id": "diagnostic-b", "candidate_origin": "diagnostic_synthetic_distractor", "rank": 2},
            ],
        },
        stable_leakage,
    )
    assert synthetic_audit["metric_validity_bucket"] == "synthetic_distractor_only"
    assert v572.row_counts_for_valid_live_retrieval_metric(synthetic_audit) is False


def test_v572_row_expansion_is_diagnostic_only_and_not_official_qrels(v572_report: dict[str, object]) -> None:
    report = v572_report
    assert report["row_expansion_attempted"] is True
    assert report["row_expansion_rows"] == 90
    assert report["row_expansion_metric_rows"] > 0
    assert report["expanded_diagnostic_live_retrieval_metric_computed"] is True
    assert report["not_official_qrels"] is True
    assert report["official_qrels_created"] is False
    assert report["machine_owned_diagnostic_proxy_labels_only"] is True
    assert report["row_expansion_family_breakdown"] == {"XLSX": 90}


def test_v572_vector_payload_stays_candidate_only_and_sourceatom_evidence_truth(v572_report: dict[str, object]) -> None:
    report = v572_report
    assert report["vector_payload_role"] == "candidate_only"
    assert report["vector_payload_evidence_truth_violation_count"] == 0
    assert report["SourceAtom_EvidenceBundle_role"] == "evidence_truth"
    assert report["missing_live_index_fail_closed_without_fake_noop_answer"] is True
    assert report["live_db_index_cache_readiness"] is False


def test_v572_written_artifacts_status_runner_and_current_alias(tmp_path: Path, v572_report: dict[str, object]) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_v572_live_retrieval_denominator_and_row_expansion_diagnostic_nonprod as v572

    written, artifact_hashes = v572.write_report_bundle(tmp_path, v572_report)
    v572.check_report(written, root=tmp_path)
    v572.append_status(tmp_path, written, artifact_hashes=artifact_hashes)

    assert len(_read_jsonl(tmp_path / v572.ARTIFACT_PATHS["candidate_origin_audit_jsonl"])) == 29
    assert len(_read_jsonl(tmp_path / v572.ARTIFACT_PATHS["leakage_probe_results_jsonl"])) == 29
    assert len(_read_jsonl(tmp_path / v572.ARTIFACT_PATHS["live_metric_denominator_audit_jsonl"])) == 29
    assert (tmp_path / v572.ARTIFACT_PATHS["metric_restatement_json"]).exists()
    assert (tmp_path / v572.ARTIFACT_PATHS["expanded_live_retrieval_metrics_json"]).exists()

    status_rows = _read_jsonl(tmp_path / "ai/eval/reports/rag-ingestion/status.jsonl")
    latest = status_rows[-1]
    assert latest["short_run_id"] == written["short_run_id"]
    assert latest["valid_live_retrieval_metric_rows"] == written["valid_live_retrieval_metric_rows"]
    assert latest["row_expansion_metric_rows"] == written["row_expansion_metric_rows"]
    assert latest["current_resolves_to"] == "v5_6"

    checked = runner.check_run("v5_7_2_live_retrieval_denominator_and_row_expansion")
    assert checked["short_run_id"] == written["short_run_id"]
    assert runner.check_run("current")["short_run_id"] == "v5_6_official_metric_scored_execution_and_failure_attribution_nonprod"


def test_v572_check_report_rejects_product_claims_opened_gates_and_protected_mutations(
    v572_report: dict[str, object],
) -> None:
    from ai.eval import rag_v572_live_retrieval_denominator_and_row_expansion_diagnostic_nonprod as v572

    for path, value, message in (
        (("official_metric",), True, "official"),
        (("official_metric_input_rows",), 29, "official metric input"),
        (("answer_metric_rows",), 1, "answer metric"),
        (("scored_answer_rows",), 1, "scored answer"),
        (("answer_quality_metric_computed",), True, "answer quality"),
        (("quality_delta_claim_supported",), True, "quality delta"),
        (("product_retrieval_quality_claim_supported",), True, "product retrieval quality"),
        (("candidate_generation_fence_verified",), False, "candidate generation fence"),
        (("candidate_generator_query_id_feature_used",), True, "query id"),
        (("candidate_generator_row_id_feature_used",), True, "row id"),
        (("candidate_generator_target_qrels_baseline_feature_used",), True, "target/qrels/baseline"),
        (("leakage_probe_failed_count",), 1, "leakage"),
        (("valid_live_retrieval_metric_rows",), 0, "live denominator"),
        (("valid_live_retrieval_metric_computed",), False, "valid live"),
        (("protected_namespaces_touched",), ["ai/eval/eval_queries"], "protected"),
        (("gold_mutation",), True, "closed gate"),
        (("qrels_mutation",), True, "closed gate"),
        (("expected_answer_mutation",), True, "closed gate"),
        (("supporting_evidence_mutation",), True, "closed gate"),
        (("denominator_mutation",), True, "closed gate"),
        (("training_dataset_created",), True, "closed gate"),
        (("fine_tuning_executed",), True, "closed gate"),
        (("ft_a_execution",), True, "closed gate"),
        (("live_db_index_cache_readiness",), True, "closed gate"),
    ):
        mutated = json.loads(json.dumps(v572_report))
        cursor = mutated
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        with pytest.raises(ValueError, match=message):
            v572.check_report(mutated)
