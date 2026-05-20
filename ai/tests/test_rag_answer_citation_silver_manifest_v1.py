from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "ai" / "eval" / "reports" / "rag-ingestion"
REPORT_ARCHIVE_DIR = REPORT_DIR / "_archive" / "legacy"
EXTERNAL_REPORT_ARCHIVE_DIR = Path(
    "D:/_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/"
    "rag-ingestion/repo-wide-cleanup-20260519/reports/rag-ingestion-legacy"
)
SILVER_DIR = ROOT / "ai" / "eval" / "silver"
MANIFEST = SILVER_DIR / "answer_citation_silver_manifest_v1.json"
READINESS = SILVER_DIR / "answer_citation_silver_readiness_v1.json"
STATUS_JSONL = REPORT_DIR / "status.jsonl"
V3_5_0_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_5_0_"
    "strict_non_official_source_bound_capacity_expansion"
)
V3_5_0_CAPACITY_SUMMARY = REPORT_DIR / f"{V3_5_0_RUN_ID}_capacity_summary.json"
V3_5_0_MANIFEST_READY = REPORT_DIR / f"{V3_5_0_RUN_ID}_manifest_ready_candidates.jsonl"
V3_5_0_BLOCKED_OR_CONVERTIBLE = (
    REPORT_DIR / f"{V3_5_0_RUN_ID}_blocked_or_convertible_candidates.jsonl"
)
V3_5_0_ACQUISITION_PLAN = REPORT_DIR / f"{V3_5_0_RUN_ID}_acquisition_plan.json"
V3_5_1_RUN_ID = "official_answer_citation_agentic_loop_run_v3_5_1_pilot_silver_source_manifest_freeze"
V3_5_1_PILOT_SOURCE_MANIFEST = REPORT_DIR / f"{V3_5_1_RUN_ID}_pilot_source_manifest.jsonl"
V3_5_1_FREEZE_SUMMARY = REPORT_DIR / f"{V3_5_1_RUN_ID}_freeze_summary.json"
V3_5_1_FREEZE_AUDIT = REPORT_DIR / f"{V3_5_1_RUN_ID}_freeze_audit.jsonl"
V3_5_1_SELECTION_RATIONALE = REPORT_DIR / f"{V3_5_1_RUN_ID}_selection_rationale.json"
V3_5_2_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_5_2_"
    "xlsx_source_value_manifest_repair_and_acquisition"
)
V3_5_2_XLSX_MANIFEST_READY = REPORT_DIR / f"{V3_5_2_RUN_ID}_xlsx_manifest_ready_candidates.jsonl"
V3_5_2_XLSX_BLOCKED_OR_CONVERTIBLE = (
    REPORT_DIR / f"{V3_5_2_RUN_ID}_xlsx_blocked_or_convertible_candidates.jsonl"
)
V3_5_2_XLSX_SOURCE_COLLECTION_MANIFEST = (
    REPORT_DIR / f"{V3_5_2_RUN_ID}_xlsx_source_collection_manifest.json"
)
V3_5_2_POST_XLSX_CAPACITY_SUMMARY = REPORT_DIR / f"{V3_5_2_RUN_ID}_post_xlsx_capacity_summary.json"
V3_5_3_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_5_3_"
    "pdf_page_bbox_source_text_manifest_repair_and_acquisition"
)
V3_5_3_PDF_MANIFEST_READY = REPORT_DIR / f"{V3_5_3_RUN_ID}_pdf_manifest_ready_candidates.jsonl"
V3_5_3_PDF_BLOCKED_OR_CONVERTIBLE = (
    REPORT_DIR / f"{V3_5_3_RUN_ID}_pdf_blocked_or_convertible_candidates.jsonl"
)
V3_5_3_PDF_SOURCE_COLLECTION_MANIFEST = REPORT_DIR / f"{V3_5_3_RUN_ID}_pdf_source_collection_manifest.json"
V3_5_3_POST_PDF_CAPACITY_SUMMARY = REPORT_DIR / f"{V3_5_3_RUN_ID}_post_pdf_capacity_summary.json"
V3_5_3_BALANCED_CAPACITY_SUMMARY = REPORT_DIR / f"{V3_5_3_RUN_ID}_balanced_capacity_summary.json"
V3_5_4_RUN_ID = "official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze"
V3_5_4_BALANCED_SOURCE_MANIFEST = REPORT_DIR / f"{V3_5_4_RUN_ID}_balanced_source_manifest.jsonl"
V3_5_4_FREEZE_SUMMARY = REPORT_DIR / f"{V3_5_4_RUN_ID}_freeze_summary.json"
V3_5_4_FREEZE_AUDIT = REPORT_DIR / f"{V3_5_4_RUN_ID}_freeze_audit.jsonl"
V3_5_4_AUDIT_SAMPLE_PACKET = REPORT_DIR / f"{V3_5_4_RUN_ID}_audit_sample_packet.jsonl"
V3_5_4_NEXT_PHASE_POLICY_BOUNDARY = (
    REPORT_DIR / f"{V3_5_4_RUN_ID}_next_phase_policy_boundary.json"
)
V3_5_5_RUN_ID = "official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit"
V3_5_5_QUALITY_SUMMARY = REPORT_DIR / f"{V3_5_5_RUN_ID}_quality_summary.json"
V3_5_5_MANIFEST_VALIDATION = REPORT_DIR / f"{V3_5_5_RUN_ID}_manifest_validation.jsonl"
V3_5_5_AUDIT_SAMPLE_REVIEW_PACKET = REPORT_DIR / f"{V3_5_5_RUN_ID}_audit_sample_review_packet.jsonl"
V3_5_5_DUPLICATE_HASH_AUDIT = REPORT_DIR / f"{V3_5_5_RUN_ID}_duplicate_hash_audit.jsonl"
V3_5_5_RECOMMENDED_REPAIR_QUEUE = REPORT_DIR / f"{V3_5_5_RUN_ID}_recommended_repair_queue.jsonl"
V3_5_5_NEXT_PHASE_POLICY_BOUNDARY = REPORT_DIR / f"{V3_5_5_RUN_ID}_next_phase_policy_boundary.json"
SOURCE_BOUND_SEARCH_UNIT_MANIFEST = (
    ROOT / "ai" / "eval" / "indexes" / "rag-data-official-denominator-v1" / "search_unit_manifest.jsonl"
)
SILVER_JSONL_BY_SPLIT = {
    "contract": SILVER_DIR / "answer_citation_silver_contract_v1.jsonl",
    "dev": SILVER_DIR / "answer_citation_silver_dev_v1.jsonl",
    "holdout": SILVER_DIR / "answer_citation_silver_holdout_v1.jsonl",
}
OFFICIAL_INPUT_CONFIG = REPORT_DIR / "metric_input_v1.json"
FIRST_RUN = REPORT_DIR / "baseline_v1.json"
XLSX_CANDIDATE = REPORT_DIR / "xlsx_candidate_v1.jsonl"
PDF_CANDIDATE = REPORT_DIR / "pdf_candidate_v1.jsonl"
AGENTIC_SUMMARY = REPORT_ARCHIVE_DIR / "agentic_v1_summary.json"
AGENTIC_ATTRIBUTION = REPORT_ARCHIVE_DIR / "agentic_v1_failure.json"
README = ROOT / "README.md"
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"


def test_answer_citation_silver_manifest_locks_policy_and_taxonomy() -> None:
    manifest = read_json(MANIFEST)

    assert manifest["purpose"] == "anti_overfit_generalization_and_source_bound_contract"
    assert manifest["silver_set_is_gold"] is False
    assert manifest["silver_set_is_official_metric_denominator"] is False
    assert manifest["silver_set_is_promotion_evidence"] is False
    assert manifest["silver_set_used_for_generation"] is False
    assert manifest["expected_values_used_for_audit_only"] is True
    assert manifest["official_denominator_query_ids_excluded_from_tuning_silver"] is True
    assert manifest["candidate_artifacts_used_as_generation_source"] is False
    assert manifest["production_index_path_used"] is False
    assert manifest["minimum_safe_source_candidate_schema"] == {
        "id_field": "query_id_or_candidate_id",
        "required_fields": [
            "source_family",
            "source_bound_locator",
            "document_version_id",
            "search_unit_id",
            "source_text_available",
            "generation_source",
            "promotion_evidence",
            "official_denominator_overlap",
        ],
        "required_boolean_values": {
            "generation_source": False,
            "promotion_evidence": False,
            "official_denominator_overlap": False,
        },
        "forbidden_fields": [
            "expected_answer",
            "supporting_evidence",
            "relevance_label",
            "answerability_label",
            "gold_label",
            "human_label",
        ],
    }
    assert manifest["non_production_index"]["target_index_path"] == (
        "ai/eval/indexes/rag-data-official-denominator-v1"
    )
    assert manifest["non_production_index"]["production_index_path_used"] is False
    overlap_scan = manifest["source_bound_material_audit"]["official_denominator_overlap_scan"]
    assert overlap_scan["source_bound_search_unit_manifest_rows"] == 29
    assert overlap_scan["official_denominator_overlap_true_count"] == 29
    assert overlap_scan["official_denominator_overlap_false_count"] == 0
    assert overlap_scan["eligible_dev_holdout_source_candidate_count"] == 0
    assert manifest["source_bound_material_audit"]["safe_source_manifests_can_be_created"] is False

    assert set(manifest["splits"]) == {"contract", "dev", "holdout", "sealed"}
    assert manifest["splits"]["contract"]["allowed_use"] == "implementation_regression_only"
    assert manifest["splits"]["dev"]["allowed_use"] == "tuning_allowed"
    assert manifest["splits"]["holdout"]["allowed_use"] == "aggregate_monitoring_only_during_tuning"
    assert manifest["splits"]["sealed"]["allowed_use"] == "final_pre_promotion_sanity_only"
    assert manifest["splits"]["contract"]["tuning_allowed"] is False
    assert manifest["splits"]["dev"]["tuning_allowed"] is True
    assert manifest["splits"]["holdout"]["tuning_allowed"] is False
    assert manifest["splits"]["sealed"]["tuning_allowed"] is False

    assert manifest["label_confidence"] == ["high", "medium", "low"]
    leakage_policy = manifest["leakage_policy"]
    assert leakage_policy["same_leakage_group_id_cannot_cross"] == [
        "dev",
        "holdout",
        "sealed",
    ]
    assert leakage_policy["same_query_template_family_and_source_locator_family_should_not_cross_dev_holdout"] is True
    assert leakage_policy["official_query_ids_must_not_appear_in_dev_or_holdout_tuning_silver"] is True

    serialized = json.dumps(manifest, ensure_ascii=False)
    assert "expected_answer_used_for_generation" not in serialized
    assert "supporting_evidence_used_for_generation" not in serialized
    assert "prod-index" not in json.dumps(manifest["non_production_index"], ensure_ascii=False).lower()


def test_answer_citation_silver_rows_or_readiness_are_source_bound_and_non_leaky() -> None:
    official_query_ids = official_denominator_query_ids()
    rows_by_split = {split: read_jsonl_if_exists(path) for split, path in SILVER_JSONL_BY_SPLIT.items()}
    all_rows = [row for rows in rows_by_split.values() for row in rows]

    if not all_rows:
        readiness = read_json(READINESS)
        assert readiness["status"] == "BLOCKED_SOURCE_BOUND_SILVER_SOURCE_DATA_MISSING"
        assert readiness["silver_jsonl_files_created"] == {
            "contract": False,
            "dev": False,
            "holdout": False,
        }
        assert readiness["per_track_counts"] == {
            "text_namu_v2_1": 0,
            "xlsx_business_structured": 0,
            "pdf_business_ocr_mm": 0,
        }
        assert readiness["official_denominator_query_ids_excluded_from_tuning_silver"] is True
        assert readiness["candidate_artifacts_used_as_generation_source"] is False
        assert readiness["expected_values_used_for_audit_only"] is True
        assert readiness["silver_set_used_for_generation"] is False
        assert readiness["minimum_safe_source_candidate_schema"]["required_boolean_values"] == {
            "generation_source": False,
            "promotion_evidence": False,
            "official_denominator_overlap": False,
        }
        blocker = readiness["source_data_decision"]
        assert blocker["safe_source_bound_answer_citation_source_data_available"] is False
        assert blocker["safe_source_manifests_can_be_created"] is False
        assert blocker["precise_blocker"] == (
            "Only official-denominator source-bound SearchUnits are currently available; all 29 overlap "
            "the official denominator and cannot satisfy official_denominator_overlap=false for "
            "dev/holdout tuning silver."
        )
        return

    case_ids = [clean(row.get("silver_case_id")) for row in all_rows]
    assert len(case_ids) == len(set(case_ids))
    assert all(case_ids)
    for split, rows in rows_by_split.items():
        for row in rows:
            assert row["split"] == split
            assert row["used_for_generation"] is False
            assert row["promotion_evidence"] is False
            assert row.get("silver_set_is_gold") is not True
            assert row.get("silver_set_is_official_metric_denominator") is not True
            assert row.get("candidate_artifacts_used_as_generation_source") is not True
            assert row.get("expected_values_used_for_generation") is not True
            assert row.get("supporting_evidence_used_for_generation") is not True
            assert "production" not in json.dumps(row, ensure_ascii=False).lower()
            assert clean(row.get("label_confidence")) in {"high", "medium", "low"}
            assert clean(row.get("query_template_family"))
            assert clean(row.get("leakage_group_id"))
            if split in {"dev", "holdout"}:
                assert clean(row.get("query_id")) not in official_query_ids
            if row["track"] == "text_namu_v2_1":
                assert_text_locator(row)
            elif row["track"] == "xlsx_business_structured":
                assert_xlsx_locator(row)
            elif row["track"] == "pdf_business_ocr_mm":
                assert_pdf_locator(row)
            else:
                raise AssertionError(f"unknown silver track: {row['track']}")

    assert split_group_ids(rows_by_split["dev"]).isdisjoint(split_group_ids(rows_by_split["holdout"]))
    assert split_group_ids(rows_by_split["dev"]).isdisjoint(split_group_ids(read_jsonl_if_exists(SILVER_DIR / "answer_citation_silver_sealed_v1.jsonl")))
    assert template_locator_families(rows_by_split["dev"]).isdisjoint(
        template_locator_families(rows_by_split["holdout"])
    )


def test_answer_citation_silver_readiness_records_exact_current_blockers() -> None:
    readiness = read_json(READINESS)

    assert readiness["purpose"] == "anti_overfit_generalization_and_source_bound_contract"
    assert readiness["not_gold"] is True
    assert readiness["not_official_metric_denominator"] is True
    assert readiness["not_promotion_evidence"] is True
    assert readiness["not_performance_rerun"] is True
    assert readiness["no_tuning_performed"] is True
    assert readiness["gold_csvs_mutated"] is False
    assert readiness["official_denominator_registry_mutated"] is False
    assert readiness["human_labels_mutated"] is False
    assert readiness["production_namespace_or_vector_path_mutated"] is False
    assert readiness["first_run_baseline_overwritten"] is False
    assert readiness["xlsx_pdf_candidates_promoted"] is False
    assert readiness["candidate_result_rows_used_as_silver_generation_source"] is False

    assert readiness["official_denominator_query_ids"]["dev_holdout_tuning_silver_overlap_count"] == 0
    assert readiness["source_bound_nonproduction_index"]["target_index_path"] == (
        "ai/eval/indexes/rag-data-official-denominator-v1"
    )
    assert readiness["source_bound_nonproduction_index"]["production_index_path_used"] is False

    blockers = readiness["blockers_by_track"]
    assert blockers["text_namu_v2_1"]["status"] == "blocked"
    assert blockers["text_namu_v2_1"]["missing_source_bound_fields"] == [
        "document_version_id",
        "search_unit_id",
        "text_locator",
    ]
    assert blockers["xlsx_business_structured"]["status"] == "blocked"
    assert blockers["xlsx_business_structured"]["missing_source_bound_fields"] == [
        "cell",
        "row_label",
        "target_column",
        "normalized_value_for_audit_only",
    ]
    assert blockers["pdf_business_ocr_mm"]["status"] == "blocked"
    assert blockers["pdf_business_ocr_mm"]["missing_source_bound_fields"] == [
        "source_pdf_path",
        "document_version_id",
        "search_unit_id",
        "row_label",
        "target_column",
    ]
    overlap_scan = readiness["official_denominator_overlap_scan"]
    assert overlap_scan["source_bound_search_unit_manifest_rows"] == 29
    assert overlap_scan["official_denominator_overlap_true_count"] == 29
    assert overlap_scan["official_denominator_overlap_false_count"] == 0
    assert overlap_scan["eligible_dev_holdout_source_candidate_count"] == 0
    assert overlap_scan["excluded_official_query_id_count"] == 29


def test_answer_citation_silver_use_policy_matches_current_artifact_boundaries() -> None:
    first_run = read_json(FIRST_RUN)
    xlsx_rows = read_jsonl(XLSX_CANDIDATE)
    pdf_rows = read_jsonl(PDF_CANDIDATE)
    summary = read_json(AGENTIC_SUMMARY)
    attribution = read_json(AGENTIC_ATTRIBUTION)

    assert first_run["scored_count"] == 29
    assert first_run["failure_category_counts"] == {
        "CITATION_UNSUPPORTED": 11,
        "PARTIAL_OR_UNSUPPORTED": 10,
        "PASS": 8,
    }
    assert len(xlsx_rows) == 29
    assert len(pdf_rows) == 29
    assert all(row["promotion_evidence"] is False for row in xlsx_rows)
    assert all(row["promotion_evidence"] is False for row in pdf_rows)
    assert all(row["expected_answer_used_for_generation"] is False for row in xlsx_rows)
    assert all(row["supporting_evidence_used_for_generation"] is False for row in xlsx_rows)
    assert all(row["expected_answer_used_for_generation"] is False for row in pdf_rows)
    assert all(row["supporting_evidence_used_for_generation"] is False for row in pdf_rows)

    assert summary["measurement_classification"] == (
        "diagnostic_live_generation_fixture_all_index_not_official_denominator_representative"
    )
    assert summary["baseline_comparison_is_model_quality_comparable"] is False
    assert summary["performance_interpretation"] == (
        "diagnostic_retrieval_agent_loop_not_final_answer_generation_quality"
    )
    assert summary["diagnostic_limitations"]["current_pass_is_promotion_evidence"] is False
    assert attribution["baseline_comparison_is_model_quality_comparable"] is False
    assert attribution["structured_adapter_wiring_verdict"]["xlsx_candidate_adapter_wired_into_live_path"] is False
    assert attribution["structured_adapter_wiring_verdict"]["pdf_candidate_adapter_wired_into_live_path"] is False


def test_docs_record_answer_citation_silver_strategy_without_promotion_claims() -> None:
    readme = README.read_text(encoding="utf-8")
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_progress = progress.split("## Short History", 1)[0]

    for text in (readme, current_progress):
        normalized = " ".join(text.split())
        assert "answer_citation_silver_manifest_v1.json" in text
        assert "answer_citation_silver_readiness_v1.json" in text
        assert "anti-overfit" in normalized
        assert "silver is not gold" in normalized
        assert "not official denominator" in normalized
        assert "not promotion evidence" in normalized
        assert "expected values are audit-only" in normalized
        assert "official 29 query_ids are excluded from dev/holdout tuning silver" in normalized
        assert "TEXT=0, XLSX=0, PDF=0" in normalized

    current_normalized = " ".join(current_progress.split())
    assert "official-denominator source-bound index, build/load check, and canonical SearchUnit citation payload wiring are already available" in current_normalized
    assert "29/29 source-bound SearchUnits overlap the official denominator" in current_normalized
    assert "safe non-official source-bound source manifests are still missing" in current_normalized
    assert "silver generation stays closed until safe silver-source data coverage is settled" in current_normalized

    assert "silver promotion evidence" not in current_progress.lower()


def test_answer_citation_silver_source_material_is_not_official_denominator_overlap() -> None:
    readiness = read_json(READINESS)
    manifest = read_json(MANIFEST)
    source_bound_rows = read_jsonl(SOURCE_BOUND_SEARCH_UNIT_MANIFEST)
    official_query_ids = official_denominator_query_ids()

    assert len(source_bound_rows) == 29
    assert {clean(row.get("query_id")) for row in source_bound_rows} == official_query_ids
    assert all(row["source_bound_official_denominator"] is True for row in source_bound_rows)
    assert all(row["promotion_evidence"] is False for row in source_bound_rows)
    assert all(row["candidate_artifact_generation_source"] is False for row in source_bound_rows)
    assert all(has_value(row.get("document_version_id")) for row in source_bound_rows)
    assert all(has_value(row.get("search_unit_id")) for row in source_bound_rows)
    assert all(has_value(row.get("embedding_text") or row.get("bm25_text") or row.get("display_text")) for row in source_bound_rows)

    assert readiness["official_denominator_overlap_scan"]["eligible_dev_holdout_source_candidate_count"] == 0
    assert readiness["per_track_counts"] == {"text_namu_v2_1": 0, "xlsx_business_structured": 0, "pdf_business_ocr_mm": 0}
    assert manifest["source_bound_material_audit"]["per_source_family_safe_candidate_counts"] == {
        "TEXT": 0,
        "XLSX": 0,
        "PDF": 0,
    }
    for split in ("dev", "holdout", "contract"):
        assert SILVER_JSONL_BY_SPLIT[split].exists() is False


def test_v3_3_1_status_event_records_silver_source_manifest_blocker_without_generation() -> None:
    run_id = "official_answer_citation_agentic_loop_run_v3_3_1_answer_citation_silver_source_manifest_readiness"
    event = next(
        item
        for item in reversed(read_jsonl(STATUS_JSONL))
        if item.get("event_type") == "answer_citation_silver_source_manifest_readiness_v3_3_1"
        and item.get("run_id") == run_id
    )

    assert event["run_class"] == "status_ledger_only_silver_source_manifest_readiness"
    assert event["safe_source_manifests_can_be_created"] is False
    assert event["silver_jsonl_files_created"] == {"contract": False, "dev": False, "holdout": False}
    assert event["source_data_blocker"]["official_denominator_overlap_true_count"] == 29
    assert event["source_data_blocker"]["eligible_dev_holdout_source_candidate_count"] == 0
    assert event["guardrails"]["silver_generation_run"] is False
    assert event["guardrails"]["generation_source_mutation"] is False
    assert event["guardrails"]["promotion_evidence"] is False
    assert event["guardrails"]["gold_mutation"] is False
    assert event["guardrails"]["expected_answer_mutation"] is False
    assert event["guardrails"]["supporting_evidence_mutation"] is False
    assert event["guardrails"]["official_denominator_query_id_set_mutation"] is False
    assert event["guardrails"]["official_retrieval_metrics_computed"] is False
    assert event["guardrails"]["production_mutation"] is False


def test_v3_5_0_capacity_summary_locks_schema_and_previous_strict_inventory() -> None:
    summary = read_json(V3_5_0_CAPACITY_SUMMARY)
    manifest_ready_rows = read_jsonl(V3_5_0_MANIFEST_READY)

    assert summary["run_id"] == V3_5_0_RUN_ID
    assert summary["artifact_kind"] == "strict_non_official_source_bound_capacity_summary"
    assert summary["schema_version"] == "v3_5_0_strict_non_official_source_bound_capacity_summary_v1"
    assert summary["previous_strict_inventory"] == {"TEXT": 0, "PDF": 3, "XLSX": 4, "total": 7}
    assert summary["new_manifest_ready_inventory"] == {
        "TEXT": 350,
        "PDF": 3,
        "XLSX": 4,
        "total": 357,
    }
    assert len(manifest_ready_rows) == summary["new_manifest_ready_inventory"]["total"]
    assert summary["pilot_threshold_rows"] == 100
    assert summary["target_rows"] == 1000
    assert summary["preferred_target_by_source_family"] == {"TEXT": 350, "PDF": 325, "XLSX": 325}
    assert summary["pilot_threshold_met"] is True
    assert summary["target_threshold_met"] is False
    assert summary["recommended_next_phase"] == "v3_5_1_pilot_silver_source_manifest_freeze"
    assert summary["silver_generation_allowed"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["official_denominator_rows_reused"] is False
    assert summary["official_29_query_ids_copied_or_relabelled"] is False
    assert summary["candidate_artifacts_used_as_generation_source"] is False
    assert summary["source_inventory_differs_from_v3_4_4"] is True
    assert summary["source_inventory_change_reason"] == (
        "v3_5_0 deterministically reconstructs TEXT document/search-unit locator fields from existing "
        "rag_chunks source rows without creating questions, answers, labels, or silver rows."
    )


def test_v3_5_0_manifest_ready_candidates_are_source_bound_and_non_official() -> None:
    rows = read_jsonl(V3_5_0_MANIFEST_READY)
    official_query_ids = official_denominator_query_ids()
    official_search_unit_ids = {
        clean(row.get("search_unit_id")) for row in read_jsonl(SOURCE_BOUND_SEARCH_UNIT_MANIFEST)
    }
    by_family: dict[str, int] = defaultdict(int)

    assert rows
    assert len({row["candidate_id"] for row in rows}) == len(rows)
    for row in rows:
        by_family[row["source_family"]] += 1
        assert row["classification"] == "strict_manifest_ready"
        assert row["official_denominator_overlap"] is False
        assert row["generation_source"] is False
        assert row["promotion_evidence"] is False
        assert row["not_gold"] is True
        assert row["not_official_denominator"] is True
        assert row["silver_expected_values_policy"] == "audit_only"
        assert row["candidate_artifacts_used_as_generation_source"] is False
        assert row["source_text_available"] is True
        assert has_value(row.get("source_hash") or row.get("excerpt_hash"))
        assert clean(row.get("provenance_query_id")) not in official_query_ids
        assert clean(row.get("search_unit_id")) not in official_search_unit_ids
        assert "expected_answer" not in row
        assert "supporting_evidence" not in row
        assert "relevance_label" not in row
        assert "answerability_label" not in row

        locator = row["source_locator"]
        if row["source_family"] == "TEXT":
            assert_required(row, ("candidate_id", "document_version_id", "search_unit_id"))
            assert_required(
                locator,
                (
                    "source_corpus_path",
                    "doc_id",
                    "chunk_id",
                    "section_id",
                    "jsonl_line_number",
                    "char_start",
                    "char_end",
                ),
            )
            assert locator["source_corpus_path"] == "ai/eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl"
        elif row["source_family"] == "PDF":
            assert_required(row, ("candidate_id", "document_version_id", "search_unit_id", "source_pdf_path"))
            assert_required(locator, ("source_pdf_path", "page", "physical_page_index", "bbox", "region_type"))
            assert isinstance(locator["bbox"], list)
            assert len(locator["bbox"]) == 4
            assert row["extract_provenance"]["source_manifest_kind"] == "pdf_answer_citation_diagnostic_review_input"
        elif row["source_family"] == "XLSX":
            assert_required(row, ("candidate_id", "document_version_id", "search_unit_id", "source_workbook"))
            assert_required(locator, ("workbook", "sheet", "range"))
            assert has_value(locator.get("matched_cells") or locator.get("cell") or locator.get("range"))
            assert row["extract_provenance"]["source_manifest_kind"] == (
                "xlsx_strict_silver_retrieval_evidence_manifest"
            )
        else:
            raise AssertionError(row["source_family"])

    assert by_family == {"TEXT": 350, "PDF": 3, "XLSX": 4}


def test_v3_5_0_keeps_silver_rows_closed_and_official_ids_excluded() -> None:
    summary = read_json(V3_5_0_CAPACITY_SUMMARY)
    manifest_ready_rows = read_jsonl(V3_5_0_MANIFEST_READY)
    official_query_ids = official_denominator_query_ids()

    for split in ("contract", "dev", "holdout"):
        assert SILVER_JSONL_BY_SPLIT[split].exists() is False

    assert summary["silver_jsonl_rows_created"] is False
    assert summary["silver_generation_allowed"] is False
    assert summary["official_denominator_rows_reused"] is False
    assert summary["official_29_query_ids_copied_or_relabelled"] is False
    assert {
        clean(row.get("provenance_query_id"))
        for row in manifest_ready_rows
        if clean(row.get("provenance_query_id"))
    }.isdisjoint(official_query_ids)
    assert {
        clean(row.get("query_id"))
        for row in manifest_ready_rows
        if clean(row.get("query_id"))
    }.isdisjoint(official_query_ids)


def test_v3_5_0_acquisition_plan_is_track_separated_and_non_generating() -> None:
    summary = read_json(V3_5_0_CAPACITY_SUMMARY)
    plan = read_json(V3_5_0_ACQUISITION_PLAN)
    blocked_or_convertible = read_jsonl(V3_5_0_BLOCKED_OR_CONVERTIBLE)

    assert plan["run_id"] == V3_5_0_RUN_ID
    assert plan["artifact_kind"] == "strict_non_official_source_bound_acquisition_plan"
    assert set(plan["recommendations_by_source_family"]) == {"TEXT", "PDF", "XLSX"}
    for family, section in plan["recommendations_by_source_family"].items():
        assert family in {"TEXT", "PDF", "XLSX"}
        assert "existing_material_convertible" in section
        assert "existing_material_blocked" in section
        assert "new_source_collection_needed" in section

    assert plan["minimum_viable_pilot_plan"]["target_manifest_ready_rows"] >= 100
    assert plan["target_expansion_plan"]["target_rows"] == 1000
    assert plan["target_expansion_plan"]["preferred_mix"] == {"TEXT": 350, "PDF": 325, "XLSX": 325}
    for key in (
        "no_official_denominator_overlap",
        "no_expected_answer_or_supporting_evidence_generation",
        "no_label_mutation",
        "no_promotion_evidence",
        "no_readme_representative_performance_claim",
        "no_candidate_artifact_as_generation_source",
    ):
        assert plan["risk_notes"][key] is True

    assert summary["convertible_inventory"]["TEXT"]["candidate_count"] >= 135000
    assert summary["convertible_inventory"]["XLSX"]["candidate_count"] == 761
    assert summary["convertible_inventory"]["PDF"]["candidate_count"] == 148
    assert any(row["classification"] == "convertible_with_existing_source" for row in blocked_or_convertible)
    assert any(row["classification"].startswith("blocked_") for row in blocked_or_convertible)


def test_v3_5_1_pilot_source_manifest_freeze_is_source_only_and_text_heavy() -> None:
    summary = read_json(V3_5_1_FREEZE_SUMMARY)
    rows = read_jsonl(V3_5_1_PILOT_SOURCE_MANIFEST)
    audit_rows = read_jsonl(V3_5_1_FREEZE_AUDIT)
    rationale = read_json(V3_5_1_SELECTION_RATIONALE)
    official_query_ids = official_denominator_query_ids()
    official_search_unit_ids = {
        clean(row.get("search_unit_id")) for row in read_jsonl(SOURCE_BOUND_SEARCH_UNIT_MANIFEST)
    }

    assert summary["run_id"] == V3_5_1_RUN_ID
    assert summary["artifact_kind"] == "pilot_source_manifest_freeze"
    assert summary["source_run_id"] == V3_5_0_RUN_ID
    assert summary["previous_manifest_ready_inventory"] == {"TEXT": 350, "PDF": 3, "XLSX": 4, "total": 357}
    assert summary["frozen_manifest_row_count"] == len(rows) == 357
    assert summary["frozen_counts_by_source_family"] == {"TEXT": 350, "PDF": 3, "XLSX": 4, "total": 357}
    assert summary["excluded_during_freeze_counts_by_reason"] == {}
    assert summary["pilot_threshold_met"] is True
    assert summary["balanced_pilot_threshold_met"] is False
    assert summary["target_threshold_met"] is False
    assert summary["source_family_imbalance_warning"] is True
    assert summary["silver_generation_allowed"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["questions_created"] is False
    assert summary["expected_answers_created"] is False
    assert summary["supporting_evidence_created"] is False
    assert summary["relevance_labels_created"] is False
    assert summary["answerability_labels_created"] is False
    assert summary["qrels_created"] is False
    assert summary["official_denominator_rows_reused"] is False
    assert summary["official_29_query_ids_copied_or_relabelled"] is False
    assert summary["candidate_artifacts_used_as_generation_source"] is False
    assert summary["recommended_next_phase"] == "v3_5_2_xlsx_source_value_manifest_repair_and_acquisition"
    assert rationale["silver_generation_allowed"] is False
    assert audit_rows

    assert len({row["candidate_id"] for row in rows}) == len(rows)
    for row in rows:
        assert_source_only_manifest_row(row)
        assert row["run_id"] == V3_5_1_RUN_ID
        assert row["classification"] == "pilot_source_manifest_frozen"
        assert row["source_family"] in {"TEXT", "PDF", "XLSX"}
        assert row["official_denominator_overlap"] is False
        assert row["not_official_denominator"] is True
        assert row["not_gold"] is True
        assert has_value(row.get("document_version_id"))
        assert has_value(row.get("search_unit_id"))
        assert has_value(row.get("source_bound_locator"))
        assert has_value(row.get("locator_fingerprint"))
        assert has_value(row.get("source_content_sha256"))
        assert has_value(row.get("canonical_citation_payload"))
        assert clean(row.get("search_unit_id")) not in official_search_unit_ids
        assert clean(row.get("query_id")) not in official_query_ids
        assert clean(row.get("provenance_query_id")) not in official_query_ids
        assert row.get("source_text_available") is True or row.get("source_value_available") is True


def test_v3_5_2_xlsx_repair_uses_actual_workbook_values_not_query_or_expected_answer() -> None:
    summary = read_json(V3_5_2_POST_XLSX_CAPACITY_SUMMARY)
    rows = read_jsonl(V3_5_2_XLSX_MANIFEST_READY)
    blocked_or_convertible = read_jsonl(V3_5_2_XLSX_BLOCKED_OR_CONVERTIBLE)
    source_collection = read_json(V3_5_2_XLSX_SOURCE_COLLECTION_MANIFEST)
    official_search_unit_ids = {
        clean(row.get("search_unit_id")) for row in read_jsonl(SOURCE_BOUND_SEARCH_UNIT_MANIFEST)
    }

    assert summary["run_id"] == V3_5_2_RUN_ID
    assert summary["artifact_kind"] == "xlsx_source_value_manifest_repair_and_acquisition"
    assert summary["source_run_ids"] == [V3_5_0_RUN_ID, V3_5_1_RUN_ID]
    assert summary["starting_xlsx_manifest_ready_count"] == 4
    assert summary["target_xlsx_rows"] == 325
    assert summary["xlsx_gap_before"] == 321
    assert summary["manifest_ready_count"] == len(rows) == 321
    assert summary["xlsx_repaired_count"] == 321
    assert summary["repaired_from_locator_complete_candidates_count"] >= 321
    assert summary["locator_complete_candidate_rows"] == 700
    assert summary["repaired_from_source_collection_workbooks_count"] == 0
    assert summary["newly_collected_workbook_count"] == 0
    assert summary["newly_collected_manifest_ready_count"] == 0
    assert summary["xlsx_newly_collected_source_count"] == 0
    assert summary["xlsx_final_count"] == 325
    assert summary["xlsx_manifest_ready_count_after"] == 325
    assert summary["xlsx_gap_after"] == 0
    assert summary["target_xlsx_met"] is True
    assert summary["remaining_preferred_gap_by_source_family"] == {"TEXT": 0, "PDF": 322, "XLSX": 0}
    assert summary["combined_source_family_counts_after_phase"] == {"TEXT": 350, "PDF": 3, "XLSX": 325, "total": 678}
    assert summary["target_threshold_met"] is False
    assert summary["acquisition_performed"] is False
    assert summary["acquisition_reason"] == "existing_xlsx_candidate_workbooks_sufficient_for_preferred_gap"
    assert set(summary["blocked_counts_by_reason"]) == {
        "blocked_candidate_artifact_only",
        "blocked_source_unavailable",
        "blocked_missing_locator",
        "blocked_missing_source_value",
        "blocked_formula_without_cached_value",
        "blocked_hidden_policy",
        "blocked_duplicate_or_near_duplicate",
        "blocked_official_denominator_overlap",
        "blocked_license_or_provenance_unclear",
        "blocked_other",
    }
    assert summary["blocked_counts_by_reason"]["blocked_source_unavailable"] == 2
    assert summary["blocked_counts_by_reason"]["blocked_hidden_policy"] >= 0
    assert summary["silver_generation_allowed"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["candidate_artifacts_used_as_generation_source"] is False
    assert summary["no_candidate_artifact_as_generation_source"] is True
    assert summary["query_or_expected_answer_used_as_generation_source"] is False
    assert source_collection["acquisition_performed"] is False
    assert source_collection["newly_collected_workbook_count"] == 0
    assert source_collection["candidate_artifacts_used_as_generation_source"] is False
    assert blocked_or_convertible
    assert len(blocked_or_convertible) == 702

    for row in rows:
        assert_source_only_manifest_row(row)
        assert row["run_id"] == V3_5_2_RUN_ID
        assert row["classification"] == "xlsx_source_value_manifest_ready"
        assert row["source_family"] == "XLSX"
        assert row["official_denominator_overlap"] is False
        assert clean(row.get("search_unit_id")) not in official_search_unit_ids
        assert has_value(row.get("source_workbook"))
        assert has_value(row.get("workbook_path"))
        assert has_value(row.get("workbook_id") or row.get("document_version_id"))
        assert has_value(row.get("workbook_sha256"))
        assert has_value(row.get("sheet_name"))
        assert "row_label" in row
        assert "column_label" in row
        assert has_value(row.get("source_value"))
        assert has_value(row.get("source_value_type"))
        assert "display_value" in row
        assert "normalized_value" in row
        assert "number_format" in row
        assert "formula_present" in row
        assert "formula_cached_value_available" in row
        assert "hidden_policy" in row
        assert "hidden_status_detected" in row
        assert "sheet_hidden" in row
        assert "hidden_rows" in row
        assert "hidden_columns" in row
        assert has_value(row.get("source_value_hash"))
        locator = row["source_bound_locator"]
        assert_required(locator, ("workbook", "sheet", "range"))
        assert "cell" in locator
        assert has_value(row.get("locator_fingerprint"))
        assert row["source_value_available"] is True
        assert row["query_or_expected_answer_used_as_generation_source"] is False
        assert "query" not in row
        assert "expected_answer_text" not in row
        assert row["extract_provenance"]["candidate_artifacts_used_as_generation_source"] is False
        assert row["extract_provenance"]["query_or_expected_answer_used_as_generation_source"] is False


def test_v3_5_3_pdf_repair_records_page_bbox_text_hash_and_provenance() -> None:
    summary = read_json(V3_5_3_POST_PDF_CAPACITY_SUMMARY)
    rows = read_jsonl(V3_5_3_PDF_MANIFEST_READY)
    blocked_or_convertible = read_jsonl(V3_5_3_PDF_BLOCKED_OR_CONVERTIBLE)
    source_collection = read_json(V3_5_3_PDF_SOURCE_COLLECTION_MANIFEST)
    balanced = read_json(V3_5_3_BALANCED_CAPACITY_SUMMARY)
    official_search_unit_ids = {
        clean(row.get("search_unit_id")) for row in read_jsonl(SOURCE_BOUND_SEARCH_UNIT_MANIFEST)
    }

    assert summary["run_id"] == V3_5_3_RUN_ID
    assert summary["artifact_kind"] == "pdf_page_bbox_source_text_manifest_repair_and_acquisition"
    assert summary["source_run_ids"] == [V3_5_0_RUN_ID, V3_5_1_RUN_ID, V3_5_2_RUN_ID]
    assert summary["manifest_ready_count"] == len(rows) == 322
    assert summary["pdf_repaired_count"] == 322
    assert summary["starting_pdf_manifest_ready_count"] == 3
    assert summary["target_pdf_rows"] == 325
    assert summary["pdf_gap_before"] == 322
    assert summary["repaired_from_existing_source_pdfs_count"] == 322
    assert summary["newly_collected_pdf_count"] == 0
    assert summary["newly_collected_manifest_ready_count"] == 0
    assert summary["pdf_newly_collected_source_count"] == 0
    assert summary["pdf_final_count"] == 325
    assert summary["pdf_manifest_ready_count_after"] == 325
    assert summary["pdf_gap_after"] == 0
    assert summary["target_pdf_met"] is True
    assert summary["remaining_preferred_gap_by_source_family"] == {"TEXT": 0, "PDF": 0, "XLSX": 0}
    assert summary["combined_source_family_counts_after_phase"] == {"TEXT": 350, "PDF": 325, "XLSX": 325, "total": 1000}
    assert summary["balanced_pilot_threshold_met"] is True
    assert summary["target_threshold_met"] is True
    assert summary["silver_generation_allowed"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["candidate_artifacts_used_as_generation_source"] is False
    assert summary["acquisition_performed"] is False
    assert summary["acquisition_reason"] == "existing_148_pdf_source_collection_sufficient_for_preferred_gap"
    assert summary["extraction_methods_used"] == {"pymupdf_native_text_block_v1": 322}
    assert summary["per_document_cap"] == 4
    assert set(summary["blocked_counts_by_reason"]) == {
        "blocked_missing_locator",
        "blocked_missing_source_text",
        "blocked_unstable_extraction",
        "blocked_candidate_artifact_only",
        "blocked_duplicate_or_near_duplicate",
        "blocked_official_denominator_overlap",
        "blocked_source_unavailable",
        "blocked_license_or_provenance_unclear",
        "blocked_other",
    }
    assert summary["blocked_counts_by_reason"]["blocked_missing_locator"] == 8194
    assert summary["blocked_counts_by_reason"]["blocked_candidate_artifact_only"] == 7
    assert source_collection["acquisition_performed"] is False
    assert source_collection["newly_collected_pdf_count"] == 0
    assert source_collection["newly_collected_manifest_ready_count"] == 0
    assert blocked_or_convertible
    assert balanced["artifact_kind"] == "post_v3_5_3_balanced_source_capacity_summary"
    assert balanced["final_manifest_ready_counts_by_source_family"] == {
        "TEXT": 350,
        "PDF": 325,
        "XLSX": 325,
        "total": 1000,
    }
    assert balanced["preferred_target_by_source_family"] == {
        "TEXT": 350,
        "PDF": 325,
        "XLSX": 325,
        "total": 1000,
    }
    assert balanced["gaps_by_source_family"] == {"TEXT": 0, "PDF": 0, "XLSX": 0, "total": 0}
    assert balanced["pilot_threshold_rows"] == 100
    assert balanced["pilot_threshold_met"] is True
    assert balanced["balanced_pilot_possible"] is True
    assert balanced["target_rows"] == 1000
    assert balanced["target_threshold_met"] is True
    assert balanced["preferred_mix_met"] is True
    assert balanced["source_family_imbalance_warning"] is False
    assert balanced["silver_generation_allowed"] is False
    assert balanced["silver_jsonl_rows_created"] is False
    assert balanced["recommended_next_phase"] == "v3_5_4_balanced_silver_source_manifest_freeze"

    for row in rows:
        assert_source_only_manifest_row(row)
        assert row["run_id"] == V3_5_3_RUN_ID
        assert row["classification"] == "pdf_source_text_manifest_ready"
        assert row["source_family"] == "PDF"
        assert row["official_denominator_overlap"] is False
        assert clean(row.get("search_unit_id")) not in official_search_unit_ids
        assert_required(
            row,
            (
                "source_pdf_path",
                "stable_pdf_identity",
                "document_version_id",
                "search_unit_id",
                "page",
                "page_index",
                "physical_page_index",
                "bbox",
                "region_type",
                "locator_fingerprint",
                "source_text",
                "source_text_hash",
                "source_pdf_sha256",
                "extraction_method",
                "extraction_provenance",
            ),
        )
        assert row["extraction_method"] == "pymupdf_native_text_block_v1"
        locator = row["source_bound_locator"]
        assert_required(locator, ("source_pdf_path", "page", "page_index", "physical_page_index", "bbox", "region_type"))
        assert isinstance(locator["bbox"], list)
        assert len(locator["bbox"]) == 4
        provenance = row["extract_provenance"]
        assert provenance["source_manifest_kind"] == "source_collection_20260510_manifest"
        assert provenance["candidate_artifacts_used_as_generation_source"] is False
        assert provenance["extraction_method"] == "pymupdf_native_text_block_v1"
        assert has_value(provenance.get("source_page")) or has_value(provenance.get("download_url"))


def test_v3_5_4_balanced_source_manifest_freeze_locks_counts_and_source_only_policy() -> None:
    summary = read_json(V3_5_4_FREEZE_SUMMARY)
    rows = read_jsonl(V3_5_4_BALANCED_SOURCE_MANIFEST)
    audit_rows = read_jsonl(V3_5_4_FREEZE_AUDIT)
    policy = read_json(V3_5_4_NEXT_PHASE_POLICY_BOUNDARY)

    assert summary["run_id"] == V3_5_4_RUN_ID
    assert summary["artifact_kind"] == "balanced_silver_source_manifest_freeze_source_only"
    assert summary["source_run_ids"] == [V3_5_1_RUN_ID, V3_5_2_RUN_ID, V3_5_3_RUN_ID]
    assert summary["input_counts_by_component"]["v3_5_1_frozen_text_pdf_xlsx_manifest"][
        "counts_by_source_family"
    ] == {"TEXT": 350, "PDF": 3, "XLSX": 4, "total": 357}
    assert summary["input_counts_by_component"]["v3_5_2_xlsx_overlay"]["counts_by_source_family"] == {
        "TEXT": 0,
        "PDF": 0,
        "XLSX": 321,
        "total": 321,
    }
    assert summary["input_counts_by_component"]["v3_5_3_pdf_overlay"]["counts_by_source_family"] == {
        "TEXT": 0,
        "PDF": 322,
        "XLSX": 0,
        "total": 322,
    }
    assert summary["frozen_manifest_row_count"] == len(rows) == 1000
    assert summary["frozen_counts_by_source_family"] == {"TEXT": 350, "PDF": 325, "XLSX": 325, "total": 1000}
    assert summary["preferred_target_by_source_family"] == {
        "TEXT": 350,
        "PDF": 325,
        "XLSX": 325,
        "total": 1000,
    }
    assert summary["target_rows"] == 1000
    assert summary["target_threshold_met"] is True
    assert summary["preferred_mix_met"] is True
    assert summary["balanced_pilot_possible"] is True
    assert summary["excluded_during_freeze_counts_by_reason"] == {}
    assert summary["backfill_performed"] is False
    assert summary["backfill_source_artifacts"] == []
    assert summary["recommended_next_phase"] == "v3_5_5_balanced_source_manifest_quality_audit"
    assert summary["silver_generation_allowed"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["candidate_artifacts_used_as_generation_source"] is False
    assert policy["v3_5_4_is_silver_generation"] is False
    assert policy["codex_must_not_decide_gold_expected_evidence_or_label_policy"] is True
    assert "question_generation_policy" in policy["user_owned_decisions_needed_before_silver_generation"]

    for split in ("contract", "dev", "holdout"):
        assert SILVER_JSONL_BY_SPLIT[split].exists() is False

    assert len({row["candidate_id"] for row in rows}) == len(rows)
    assert len({row["source_identity"] for row in rows}) == len(rows)
    assert len({row["locator_fingerprint"] for row in rows}) == len(rows)
    assert len(audit_rows) == len(rows)

    for row in rows:
        assert_source_only_manifest_row(row)
        assert_no_generation_payload_keys(row)
        assert row["run_id"] == V3_5_4_RUN_ID
        assert row["classification"] == "balanced_source_manifest_frozen"
        assert row["official_denominator_overlap"] is False
        assert row["not_official_denominator"] is True
        assert row["not_gold"] is True


def test_v3_5_4_balanced_manifest_rows_are_non_official_with_family_locator_hash_contracts() -> None:
    rows = read_jsonl(V3_5_4_BALANCED_SOURCE_MANIFEST)
    official_rows = read_jsonl(SOURCE_BOUND_SEARCH_UNIT_MANIFEST)
    official_query_ids = {clean(row.get("query_id")) for row in official_rows}
    official_search_unit_ids = {clean(row.get("search_unit_id")) for row in official_rows}
    official_locator_fingerprints = {
        source_locator_fingerprint(row.get("locator")) for row in official_rows if has_value(row.get("locator"))
    }

    assert rows
    for row in rows:
        assert row["official_denominator_overlap"] is False
        assert clean(row.get("query_id")) not in official_query_ids
        assert clean(row.get("provenance_query_id")) not in official_query_ids
        assert clean(row.get("search_unit_id")) not in official_search_unit_ids
        assert clean(row.get("locator_fingerprint")) not in official_locator_fingerprints

        family = row["source_family"]
        locator = row["source_bound_locator"]
        assert_required(row, ("candidate_id", "document_version_id", "search_unit_id", "locator_fingerprint"))
        assert has_value(row.get("source_content_sha256") or row.get("source_hash"))
        if family == "TEXT":
            assert_required(locator, ("source_corpus_path", "chunk_id", "doc_id", "jsonl_line_number"))
            assert "char_start" in locator
            assert "char_end" in locator
            assert has_value(row.get("source_excerpt") or row.get("source_text_preview"))
            assert has_value(row.get("source_excerpt_hash") or row.get("excerpt_hash"))
        elif family == "PDF":
            assert_required(row, ("source_pdf_path", "page", "page_index", "bbox", "extraction_method"))
            assert has_value(row.get("source_pdf_sha256") or row.get("source_hash"))
            assert has_value(row.get("extraction_provenance") or row.get("extract_provenance"))
            assert has_value(row.get("source_text"))
            assert has_value(row.get("source_text_hash"))
            assert row["source_content_sha256"] == row["source_text_hash"]
            assert isinstance(row["bbox"], list)
            assert len(row["bbox"]) == 4
            assert all(isinstance(value, (int, float)) for value in row["bbox"])
        elif family == "XLSX":
            assert has_value(row.get("workbook_path") or row.get("source_workbook") or row.get("workbook_id"))
            assert has_value(row.get("workbook_sha256") or row.get("source_hash"))
            assert has_value(row.get("sheet_name"))
            assert has_value(row.get("cell") or row.get("range") or row.get("row_label") or row.get("column_label"))
            assert has_value(row.get("source_value"))
            assert has_value(row.get("source_value_hash"))
            assert row["source_content_sha256"] == row["source_value_hash"]
            assert "hidden_policy" in row
            assert "formula_present" in row
            assert "formula_cached_value_available" in row
        else:
            raise AssertionError(f"unexpected family: {family}")


def test_v3_5_4_sample_packet_is_manifest_derived_source_only_and_balanced() -> None:
    summary = read_json(V3_5_4_FREEZE_SUMMARY)
    rows = read_jsonl(V3_5_4_BALANCED_SOURCE_MANIFEST)
    samples = read_jsonl(V3_5_4_AUDIT_SAMPLE_PACKET)
    manifest_candidate_ids = {row["candidate_id"] for row in rows}

    assert summary["audit_sample_packet_counts_by_source_family"] == {
        "TEXT": 25,
        "PDF": 25,
        "XLSX": 25,
        "total": 75,
    }
    assert len(samples) == 75
    assert {sample["candidate_id"] for sample in samples} <= manifest_candidate_ids
    assert count_by_source_family(samples) == {"TEXT": 25, "PDF": 25, "XLSX": 25, "total": 75}
    for sample in samples:
        assert_source_only_manifest_row(sample)
        assert_no_generation_payload_keys(sample)
        assert has_value(sample.get("source_locator"))
        assert has_value(sample.get("source_excerpt_or_value"))
        assert has_value(sample.get("source_hash"))
        assert has_value(sample.get("locator_fingerprint"))


def test_v3_5_5_quality_audit_summary_artifacts_and_v3_5_4_inputs_are_locked() -> None:
    summary = read_json(V3_5_5_QUALITY_SUMMARY)
    validation_rows = read_jsonl(V3_5_5_MANIFEST_VALIDATION)
    v3_5_4_rows = read_jsonl(V3_5_4_BALANCED_SOURCE_MANIFEST)
    policy = read_json(V3_5_5_NEXT_PHASE_POLICY_BOUNDARY)

    assert summary["run_id"] == V3_5_5_RUN_ID
    assert summary["artifact_kind"] == "balanced_source_manifest_quality_audit_source_only"
    assert summary["source_run_id"] == V3_5_4_RUN_ID
    assert summary["input_manifest_path"].endswith(f"{V3_5_4_RUN_ID}_balanced_source_manifest.jsonl")
    assert summary["input_manifest_sha256_before"] == sha256_file(V3_5_4_BALANCED_SOURCE_MANIFEST)
    assert summary["input_manifest_sha256_after"] == summary["input_manifest_sha256_before"]
    assert summary["input_manifest_row_count"] == len(v3_5_4_rows) == len(validation_rows) == 1000
    assert summary["input_counts_by_source_family"] == {"TEXT": 350, "PDF": 325, "XLSX": 325, "total": 1000}
    assert summary["full_manifest_validation_completed"] is True
    assert summary["audit_sample_review_completed"] is True
    assert summary["source_only_boundary_preserved"] is True
    assert summary["silver_generation_allowed"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["questions_created"] is False
    assert summary["expected_answers_created"] is False
    assert summary["supporting_evidence_created"] is False
    assert summary["relevance_labels_created"] is False
    assert summary["answerability_labels_created"] is False
    assert summary["qrels_created"] is False
    assert summary["candidate_artifact_source_leak_detected_count"] >= 0
    assert summary["official_denominator_overlap_detected_count"] >= 0
    assert summary["normalized_source_hash_repetition_group_count"] == 17
    assert summary["normalized_source_hash_repetition_row_count"] == 57
    assert summary["recommended_next_phase"] in {
        "v3_6_0_silver_generation_policy_packet",
        "v3_5_6_source_manifest_quality_repair",
    }
    assert policy["v3_5_5_is_source_quality_audit_only"] is True
    assert policy["v3_5_5_authorizes_silver_generation"] is False
    assert "question_generation_policy" in policy["user_owned_decisions_needed_before_silver_generation"]

    for path_key in (
        "quality_summary_json",
        "manifest_validation_jsonl",
        "audit_sample_review_packet_jsonl",
        "duplicate_hash_audit_jsonl",
        "recommended_repair_queue_jsonl",
        "next_phase_policy_boundary_json",
    ):
        assert path_key in summary["artifact_paths"]

    for row in validation_rows:
        assert row["run_id"] == V3_5_5_RUN_ID
        assert row["source_run_id"] == V3_5_4_RUN_ID
        assert row["source_quality_status"] in {
            "pass_source_quality",
            "review_duplicate_or_near_duplicate",
            "review_short_source_text_or_value",
            "review_pdf_extraction_order",
            "review_pdf_header_footer_or_boilerplate",
            "review_pdf_numeric_or_table_context",
            "review_xlsx_hidden_policy_boundary",
            "review_xlsx_formula_or_cached_value",
            "review_xlsx_value_context",
            "repair_required_missing_document_identity",
            "repair_required_locator_unresolvable",
            "repair_required_source_text_or_value_missing",
            "repair_required_source_hash_missing",
            "repair_required_official_denominator_overlap",
            "repair_required_candidate_artifact_source_leak",
            "repair_required_provenance_or_license_unclear",
            "blocked_other",
        }
        assert row["source_only_boundary_preserved"] is True
        assert_no_generation_payload_keys(row)


def test_v3_5_5_duplicate_hash_audit_sample_packet_and_repair_queue_are_source_only() -> None:
    summary = read_json(V3_5_5_QUALITY_SUMMARY)
    rows = read_jsonl(V3_5_4_BALANCED_SOURCE_MANIFEST)
    samples = read_jsonl(V3_5_5_AUDIT_SAMPLE_REVIEW_PACKET)
    duplicate_rows = read_jsonl(V3_5_5_DUPLICATE_HASH_AUDIT)
    repair_rows = read_jsonl(V3_5_5_RECOMMENDED_REPAIR_QUEUE)
    manifest_candidate_ids = {row["candidate_id"] for row in rows}
    source_hash_counts: dict[str, int] = {}
    for row in rows:
        source_hash = (
            clean(row.get("source_text_hash"))
            or clean(row.get("source_value_hash"))
            or clean(row.get("source_hash"))
            or clean(row.get("excerpt_hash"))
            or clean(row.get("source_content_sha256"))
        )
        source_hash_counts[source_hash] = source_hash_counts.get(source_hash, 0) + 1
    repeated_hashes = {source_hash: count for source_hash, count in source_hash_counts.items() if count > 1}

    assert len(duplicate_rows) == len(repeated_hashes) == 17
    assert sum(row["group_size"] for row in duplicate_rows) == 57
    assert summary["normalized_source_hash_repetition_group_count"] == len(duplicate_rows)
    assert summary["recommended_repair_queue_count"] == len(repair_rows)
    for duplicate in duplicate_rows:
        assert duplicate["source_quality_status"] == "review_duplicate_or_near_duplicate"
        assert duplicate["duplicate_hash_retained_reason"] == "distinct_source_identity_or_locator"
        assert duplicate["silver_generation_allowed"] is False
        assert len(set(duplicate["source_identities"])) == duplicate["group_size"]
        assert len(set(duplicate["locator_fingerprints"])) == duplicate["group_size"]
        assert_no_generation_payload_keys(duplicate)

    assert len(samples) >= 75
    assert {sample["candidate_id"] for sample in samples} <= manifest_candidate_ids
    sample_counts = count_by_source_family(samples)
    assert sample_counts["TEXT"] >= 25
    assert sample_counts["PDF"] >= 25
    assert sample_counts["XLSX"] >= 25
    assert sample_counts == summary["audit_sample_counts_by_source_family"]
    assert any(sample["sample_reason"] == "normalized_source_hash_repetition" for sample in samples)

    for sample in samples:
        assert_source_only_manifest_row(sample)
        assert_no_generation_payload_keys(sample)
        assert has_value(sample.get("source_locator"))
        assert has_value(sample.get("source_excerpt_or_value"))
        assert has_value(sample.get("source_hash"))
        if sample["source_family"] == "PDF":
            assert_required(sample, ("source_pdf_path", "page", "page_index", "extraction_method", "source_text_hash"))
        elif sample["source_family"] == "XLSX":
            assert_required(sample, ("source_workbook", "sheet_name", "source_value_hash"))
            assert has_value(sample.get("cell") or sample.get("range"))
        elif sample["source_family"] == "TEXT":
            assert_required(sample, ("source_corpus_path", "chunk_id", "doc_id", "source_excerpt_hash"))

    for repair in repair_rows:
        assert_required(repair, ("candidate_id", "source_family", "source_quality_status", "recommended_action"))
        assert repair["source_quality_status"].startswith("repair_required_")
        assert repair["silver_generation_allowed"] is False
        assert_no_generation_payload_keys(repair)


def test_v3_5_source_material_phases_create_no_silver_rows_or_label_payloads() -> None:
    summaries = [
        read_json(V3_5_1_FREEZE_SUMMARY),
        read_json(V3_5_2_POST_XLSX_CAPACITY_SUMMARY),
        read_json(V3_5_3_POST_PDF_CAPACITY_SUMMARY),
        read_json(V3_5_4_FREEZE_SUMMARY),
        read_json(V3_5_5_QUALITY_SUMMARY),
    ]
    manifest_rows = (
        read_jsonl(V3_5_1_PILOT_SOURCE_MANIFEST)
        + read_jsonl(V3_5_2_XLSX_MANIFEST_READY)
        + read_jsonl(V3_5_3_PDF_MANIFEST_READY)
        + read_jsonl(V3_5_4_BALANCED_SOURCE_MANIFEST)
    )
    official_query_ids = official_denominator_query_ids()

    for split in ("contract", "dev", "holdout"):
        assert SILVER_JSONL_BY_SPLIT[split].exists() is False

    for summary in summaries:
        assert summary["silver_generation_allowed"] is False
        assert summary["silver_jsonl_rows_created"] is False
        assert summary["questions_created"] is False
        assert summary["expected_answers_created"] is False
        assert summary["supporting_evidence_created"] is False
        assert summary["relevance_labels_created"] is False
        assert summary["answerability_labels_created"] is False
        assert summary["qrels_created"] is False
        assert summary["official_denominator_rows_reused"] is False
        assert summary["official_29_query_ids_copied_or_relabelled"] is False
        assert summary["candidate_artifacts_used_as_generation_source"] is False

    assert manifest_rows
    for row in manifest_rows:
        assert_source_only_manifest_row(row)
        assert row["official_denominator_overlap"] is False
        assert clean(row.get("query_id")) not in official_query_ids
        assert clean(row.get("provenance_query_id")) not in official_query_ids


def assert_text_locator(row: dict[str, Any]) -> None:
    required = ("document_id", "document_version_id", "search_unit_id", "text_locator")
    assert_required(row, required)


def assert_xlsx_locator(row: dict[str, Any]) -> None:
    required = (
        "workbook",
        "sheet",
        "range",
        "cell",
        "row_label",
        "target_column",
        "document_version_id",
        "search_unit_id",
        "source_basis",
    )
    assert_required(row, required)
    assert clean(row.get("normalized_value_for_audit_only"))


def assert_pdf_locator(row: dict[str, Any]) -> None:
    required = (
        "source_pdf_path",
        "page",
        "physical_page_index",
        "bbox",
        "region_type",
        "document_version_id",
        "search_unit_id",
        "source_basis",
    )
    assert_required(row, required)
    assert isinstance(row["bbox"], list)
    assert len(row["bbox"]) == 4
    assert all(isinstance(value, (int, float)) for value in row["bbox"])
    if row["label_confidence"] == "high":
        assert clean(row.get("row_label"))
        assert clean(row.get("target_column"))


def assert_required(row: dict[str, Any], fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if not has_value(row.get(field))]
    assert missing == []


def assert_source_only_manifest_row(row: dict[str, Any]) -> None:
    forbidden_fields = (
        "query",
        "question",
        "expected_answer",
        "expected_answer_text",
        "supporting_evidence",
        "relevance_label",
        "answerability_label",
        "qrel",
        "qrels",
        "gold_label",
        "human_label",
        "generated_answer",
        "answer_claims",
    )
    for field in forbidden_fields:
        assert field not in row
    assert row["generation_source"] is False
    assert row["promotion_evidence"] is False
    assert row["official_denominator_overlap"] is False
    assert row["silver_generation_allowed"] is False
    assert row["silver_jsonl_row"] is False
    assert row["questions_created"] is False
    assert row["expected_answers_created"] is False
    assert row["supporting_evidence_created"] is False
    assert row["relevance_labels_created"] is False
    assert row["answerability_labels_created"] is False
    assert row["qrels_created"] is False
    assert row["candidate_artifacts_used_as_generation_source"] is False


def assert_no_generation_payload_keys(value: Any) -> None:
    forbidden_keys = {
        "query",
        "question",
        "question_text",
        "expected_answer",
        "expected_answer_text",
        "expected_answer_final",
        "answer_text",
        "supporting_evidence",
        "supporting_evidence_final",
        "relevance_label",
        "answerability_label",
        "label_status",
        "qrel",
        "qrels",
        "qrels_candidate_id",
        "gold_label",
        "human_label",
        "generated_answer",
        "answer_claims",
    }
    if isinstance(value, dict):
        overlap = forbidden_keys & set(value)
        assert overlap == set()
        for nested in value.values():
            assert_no_generation_payload_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_no_generation_payload_keys(nested)


def count_by_source_family(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"TEXT": 0, "PDF": 0, "XLSX": 0}
    for row in rows:
        family = clean(row.get("source_family")).upper()
        if family in counts:
            counts[family] += 1
    counts["total"] = sum(counts.values())
    return counts


def source_locator_fingerprint(locator: Any) -> str:
    return json_hash(locator)


def json_hash(value: Any) -> str:
    import hashlib

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(resolve_report_artifact_path(path).read_bytes()).hexdigest()


def split_group_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {clean(row.get("leakage_group_id")) for row in rows if clean(row.get("leakage_group_id"))}


def template_locator_families(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    return {
        (clean(row.get("query_template_family")), clean(row.get("source_locator_family")))
        for row in rows
        if clean(row.get("query_template_family")) and clean(row.get("source_locator_family"))
    }


def official_denominator_query_ids() -> set[str]:
    config = read_json(OFFICIAL_INPUT_CONFIG)
    return {row["query_id"] for row in config["candidate_manifest"]}


def resolve_report_artifact_path(path: Path) -> Path:
    if path.exists():
        return path
    if path.parent == REPORT_ARCHIVE_DIR:
        archived_external = EXTERNAL_REPORT_ARCHIVE_DIR / path.name
        return archived_external if archived_external.exists() else path
    if path.parent == REPORT_DIR:
        archived_external = EXTERNAL_REPORT_ARCHIVE_DIR / path.name
        if archived_external.exists():
            return archived_external
        archived = REPORT_ARCHIVE_DIR / path.name
        if archived.exists():
            return archived
    return path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(resolve_report_artifact_path(path).read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with resolve_report_artifact_path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_jsonl_if_exists(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return read_jsonl(path)


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
