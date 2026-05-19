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
