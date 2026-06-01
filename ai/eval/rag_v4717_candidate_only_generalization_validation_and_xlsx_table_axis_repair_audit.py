from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v4716_target_recall_repair_prototype as v4716
from ai.eval import rag_v476_archive_purge as v476


LOGICAL_RUN_KEY = "v4_7_17"
SHORT_RUN_ID = "v4_7_17_candidate_only_generalization_validation_and_xlsx_table_axis_repair_audit"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_17_"
    "candidate_only_generalization_validation_and_xlsx_table_axis_repair_audit_nonprod"
)
STATUS = "V4_7_17_CANDIDATE_ONLY_GENERALIZATION_VALIDATION_AND_XLSX_TABLE_AXIS_REPAIR_AUDIT_NONPROD_READY"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
SOURCE_RUN_ID = v4716.SHORT_RUN_ID
SOURCE_REPORT_JSON = v4716.SHORT_REPORT_PATH
SOURCE_TOPK_ROWS = v4716.SOURCE_TOPK_ROWS
SOURCE_REGISTRY_JSONL = v4716.SOURCE_REGISTRY_JSONL

KST_DOC_DATE = "2026-05-31"
XLSX_SAFE_TABLE_AXIS_FIELDS = [
    "raw_locator.sheet",
    "raw_locator.row_label",
    "raw_locator.column_label",
    "raw_locator.range",
]
RAW_PAYLOAD_FORBIDDEN_KEYS = {
    "prompt",
    "prompt_payload",
    "raw_prompt",
    "raw_prompt_payload",
    "raw_response",
    "raw_response_payload",
    "response",
    "raw_llm_response",
    "final_answer",
}
FORBIDDEN_FALSE_KEYS = (
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
)
GUARDRAIL_FALSE_KEYS = set(FORBIDDEN_FALSE_KEYS) | {
    "silver_mutation",
    "source_registry_mutated",
    "cache_mutated",
    "production_db_mutated",
    "index_rebuilt",
}


def utc_now_iso() -> str:
    return v476.utc_now_iso()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v476.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v476.write_json(path, payload)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    v476.write_jsonl(path, list(rows))


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _load_source_report(root: Path, source_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    report = dict(source_report or registry.load_report("v4_7_16", root=root))
    v4716.check_report(report)
    return report


def _load_silver_topk_rows(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, resolution = v4716._load_silver_topk_rows(root)
    if len(rows) != 1000:
        raise ValueError("v4_7_17 expected the 1000-row archived silver top-k replay source")
    if not resolution.get("sha256_verified") or not resolution.get("resolved_via_archive"):
        raise ValueError("v4_7_17 requires the v3_7_2 archived top-k source to be sha-verified")
    return rows, resolution


def _poison_oracle_fields(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    poisoned = json.loads(json.dumps(list(rows), ensure_ascii=False))
    for row in poisoned:
        row["target_source_atom_ids"] = ["poisoned_target_atom"]
        row["target_hit_at_k"] = not bool(row.get("target_hit_at_k"))
        row["target_hit_in_topk"] = not bool(row.get("target_hit_in_topk"))
        row["target_rank_at_k"] = 0
        row["question_gold_locator_target"] = {"poisoned": True}
        row["official_manifest_target"] = {"poisoned": True}
        row["target_mapping_audit"] = {"poisoned": True}
        row["supporting_evidence"] = "poisoned supporting evidence"
        row["expected_answer"] = "poisoned expected answer"
        row["expected_evidence"] = "poisoned expected evidence"
        row["query_id"] = f"poisoned-{row.get('query_id')}"
        row["case_id"] = "poisoned-case"
    return poisoned


def _field_scope(construction: Mapping[str, Any]) -> dict[str, Any]:
    allowed = construction.get("allowed_candidate_construction_fields") or {}
    source_registry = allowed.get("source_registry") or {}
    forbidden = list(construction.get("forbidden_candidate_construction_fields") or [])
    return {
        "schema_version": f"{SHORT_RUN_ID}_candidate_construction_field_scope_v1",
        "allowed_field_count_by_scope": {
            "query": len(allowed.get("query") or []),
            "source_registry_TEXT": len(source_registry.get("TEXT") or []),
            "source_registry_XLSX": len(source_registry.get("XLSX") or []),
        },
        "allowed_fields": allowed,
        "forbidden_fields": forbidden,
        "candidate_only": True,
    }


def _build_candidate_only_generalization_validation(
    *,
    root: Path,
    source_report: Mapping[str, Any],
    silver_topk_rows: Sequence[Mapping[str, Any]],
    topk_resolution: Mapping[str, Any],
) -> dict[str, Any]:
    source_prototype = source_report["target_recall_repair_prototype"]
    source_archive = source_prototype["archive_1000_candidate_only_target_recall"]
    recomputed = v4716.build_candidate_only_repair_prototype(
        root=root,
        silver_topk_rows=silver_topk_rows,
        source_report=source_report,
    )
    poisoned = v4716.build_candidate_only_repair_prototype(
        root=root,
        silver_topk_rows=_poison_oracle_fields(silver_topk_rows),
        source_report=source_report,
    )
    source_candidate_set_sha256 = _clean(source_prototype.get("candidate_set_sha256"))
    recomputed_candidate_set_sha256 = _clean(recomputed.get("candidate_set_sha256"))
    poisoned_candidate_set_sha256 = _clean(poisoned.get("candidate_set_sha256"))
    recomputed_archive = recomputed["archive_1000_candidate_only_target_recall"]
    poisoned_archive = poisoned["archive_1000_candidate_only_target_recall"]
    construction = source_prototype["candidate_construction"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_candidate_only_generalization_validation_v1",
        "status": "CANDIDATE_ONLY_GENERALIZATION_VALIDATED_DIAGNOSTIC_ONLY",
        "diagnostic_only": True,
        "non_production": True,
        "source_run_id": SOURCE_RUN_ID,
        "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        "source_v4_7_16_candidate_replay": {
            "row_count": recomputed_archive["row_count"],
            "baseline_target_hit_count": recomputed_archive["baseline_target_hit_count"],
            "combined_target_hit_count": recomputed_archive["combined_target_hit_count"],
            "baseline_miss_to_hit_count": recomputed_archive["baseline_miss_to_hit_count"],
            "baseline_hit_to_miss_count": recomputed_archive["baseline_hit_to_miss_count"],
            "source_candidate_set_sha256": source_candidate_set_sha256,
            "recomputed_candidate_set_sha256": recomputed_candidate_set_sha256,
            "source_candidate_set_sha256_matches_recomputed": (
                source_candidate_set_sha256 == recomputed_candidate_set_sha256
                == _clean(source_archive.get("candidate_set_sha256"))
            ),
            "source_topk_sha256": _clean(topk_resolution.get("sha256")),
            "source_topk_expected_sha256": _clean(topk_resolution.get("expected_sha256")),
            "source_topk_sha256_verified": bool(topk_resolution.get("sha256_verified")),
            "source_topk_resolved_via_archive": bool(topk_resolution.get("resolved_via_archive")),
        },
        "poisoned_oracle_field_candidate_set_sha256": poisoned_candidate_set_sha256,
        "poisoned_oracle_field_digest_stable": recomputed_candidate_set_sha256 == poisoned_candidate_set_sha256,
        "poisoned_oracle_field_evaluation_changed": (
            recomputed_archive["combined_target_hit_count"] != poisoned_archive["combined_target_hit_count"]
        ),
        "candidate_construction_field_scope": _field_scope(construction),
        "candidate_budget_per_query": source_prototype["candidate_budget_per_query"],
        "fixed_thresholds_declared_before_target_evaluation": bool(
            construction.get("fixed_thresholds_declared_before_target_evaluation")
        ),
        "threshold_tuning_used": bool(construction.get("threshold_tuning_used")),
        "diagnostic_target_labels_used_for_candidate_construction": bool(
            construction.get("diagnostic_target_labels_used_for_candidate_construction")
        ),
        "diagnostic_target_labels_used_for_candidate_scoring": bool(
            construction.get("diagnostic_target_labels_used_for_candidate_scoring")
        ),
        "diagnostic_target_labels_used_for_after_the_fact_evaluation": bool(
            construction.get("diagnostic_target_labels_used_for_after_the_fact_evaluation")
        ),
        "per_query_candidates_written": bool(source_prototype.get("per_query_candidates_written")),
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
    }


def _xlsx_axis_presence_summary(root: Path) -> dict[str, Any]:
    counts = {
        "source_atoms_audited": 0,
        "sheet_present_count": 0,
        "row_label_present_count": 0,
        "column_label_present_count": 0,
        "target_column_present_count": 0,
        "column_label_missing_target_column_present_count": 0,
        "cell_level_locator_count": 0,
        "range_present_count": 0,
        "range_only_locator_count": 0,
        "normalized_value_present_but_forbidden_count": 0,
        "workbook_present_but_forbidden_count": 0,
    }
    path = root / SOURCE_REGISTRY_JSONL
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if _clean(row.get("source_family")).upper() != "XLSX":
                continue
            locator = row.get("raw_locator") or {}
            if not isinstance(locator, Mapping):
                locator = {}
            counts["source_atoms_audited"] += 1
            if _clean(locator.get("sheet")):
                counts["sheet_present_count"] += 1
            if _clean(locator.get("row_label")):
                counts["row_label_present_count"] += 1
            if _clean(locator.get("column_label")):
                counts["column_label_present_count"] += 1
            if _clean(locator.get("target_column")):
                counts["target_column_present_count"] += 1
            if _clean(locator.get("target_column")) and not _clean(locator.get("column_label")):
                counts["column_label_missing_target_column_present_count"] += 1
            if _clean(locator.get("cell")):
                counts["cell_level_locator_count"] += 1
            if _clean(locator.get("range")):
                counts["range_present_count"] += 1
            if _clean(locator.get("range")) and not _clean(locator.get("cell")):
                counts["range_only_locator_count"] += 1
            if _clean(locator.get("normalized_value")):
                counts["normalized_value_present_but_forbidden_count"] += 1
            if _clean(locator.get("workbook")):
                counts["workbook_present_but_forbidden_count"] += 1
    return {
        "schema_version": f"{SHORT_RUN_ID}_xlsx_axis_presence_summary_v1",
        "source_registry_jsonl": SOURCE_REGISTRY_JSONL.as_posix(),
        "raw_source_paths_redacted": True,
        **counts,
    }


def _build_xlsx_table_axis_repair_audit(*, root: Path, source_report: Mapping[str, Any]) -> dict[str, Any]:
    prototype = source_report["target_recall_repair_prototype"]
    archive = prototype["archive_1000_candidate_only_target_recall"]
    xlsx_family = archive["families"]["XLSX"]
    overlay = prototype["overlay_90_root_cause_summary"]
    primary = overlay["primary_projection_counts"]
    xlsx_overlap = overlay["root_cause_overlap_matrix_by_family"]["XLSX"]
    source_index = prototype["source_registry_candidate_index"]
    gain = _as_int(xlsx_family.get("baseline_miss_to_hit_count"))
    miss = _as_int(xlsx_family.get("baseline_target_miss_count"))
    return {
        "schema_version": f"{SHORT_RUN_ID}_xlsx_table_axis_repair_audit_v1",
        "status": "XLSX_TABLE_AXIS_REPAIR_AUDIT_INCONCLUSIVE_DIAGNOSTIC_ONLY",
        "decision": "keep_inconclusive_low_gain_candidate_only",
        "diagnostic_only": True,
        "non_production": True,
        "source_run_id": SOURCE_RUN_ID,
        "safe_table_axis_fields": list(XLSX_SAFE_TABLE_AXIS_FIELDS),
        "archive_1000_xlsx_family_recall": dict(xlsx_family),
        "safe_table_axis_candidate_count": _as_int(xlsx_family.get("prototype_candidate_count")),
        "safe_table_axis_target_hit_gain_count": gain,
        "safe_table_axis_gain_rate_per_baseline_miss": f"{gain}/{miss}",
        "source_registry_xlsx_axis_index_summary": {
            "source_atoms_scanned_count": _as_int(
                (source_index.get("source_atoms_scanned_count_by_family") or {}).get("XLSX")
            ),
            "source_atoms_tokenized_count": _as_int(
                (source_index.get("source_atoms_tokenized_count_by_family") or {}).get("XLSX")
            ),
            "source_atoms_indexed_count": _as_int(
                (source_index.get("source_atoms_indexed_count_by_family") or {}).get("XLSX")
            ),
            "candidate_only": bool(source_index.get("candidate_only")),
            "source_registry_mutated": bool(source_index.get("source_registry_mutated")),
            "index_rebuilt": bool(source_index.get("index_rebuilt")),
        },
        "source_registry_xlsx_axis_presence_summary": _xlsx_axis_presence_summary(root),
        "overlay_90_xlsx_queue_context": {
            "row_count": _as_int(xlsx_overlap.get("row_count")),
            "target_not_in_topk_total": _as_int(xlsx_overlap.get("target_not_in_topk_total")),
            "repeated_prefix_cluster_total": _as_int(xlsx_overlap.get("repeated_prefix_cluster_total")),
            "repeated_prefix_cluster_overlap_with_target_miss": _as_int(
                xlsx_overlap.get("repeated_prefix_cluster_overlap_with_target_miss")
            ),
            "target_hit_evidence_context_repair_count": _as_int(
                (primary.get("target_hit_evidence_context_repair") or {}).get("counts_by_family", {}).get("XLSX")
            ),
        },
        "direct_normalized_value_matching_used_count": 0,
        "raw_xlsx_query_time_parsing_used_count": 0,
        "workbook_or_source_title_shortcut_used_count": 0,
        "formula_evaluation_used_count": 0,
        "formula_text_exposure_used_count": 0,
        "target_or_gold_locator_used_count": 0,
        "future_repair_boundary": {
            "candidate_only_searchview_materialization_required": True,
            "raw_xlsx_query_time_parsing": False,
            "direct_normalized_answer_value_matching": False,
            "source_file_title_shortcut_used": False,
            "formula_evaluation": False,
            "formula_text_exposure": False,
            "gold_or_target_locator_use": False,
        },
        "residual_risk": (
            "safe table-axis tokens add only two diagnostic target hits across 310 XLSX baseline misses; "
            "future work needs richer candidate-only SearchUnit/SearchView materialization, including explicit row/column "
            "axis bridging, not raw workbook parsing"
        ),
    }


def _anti_overfit_guardrails() -> dict[str, Any]:
    guardrails = dict(v4716._anti_overfit_guardrails())
    guardrails["schema_version"] = f"{SHORT_RUN_ID}_anti_overfit_guardrails_v1"
    return guardrails


def _build_counters(
    validation: Mapping[str, Any],
    xlsx_audit: Mapping[str, Any],
    source_report: Mapping[str, Any],
) -> dict[str, Any]:
    source_counters = source_report.get("counters") or {}
    source_replay = validation["source_v4_7_16_candidate_replay"]
    xlsx_family = xlsx_audit["archive_1000_xlsx_family_recall"]
    return {
        "current_resolves_to": LOGICAL_RUN_KEY,
        "source_run_id": SOURCE_RUN_ID,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "candidate_only_generalization_validated": validation["poisoned_oracle_field_digest_stable"],
        "poisoned_oracle_field_evaluation_changed": validation["poisoned_oracle_field_evaluation_changed"],
        "source_v4_7_16_baseline_target_hit_count": source_replay["baseline_target_hit_count"],
        "source_v4_7_16_combined_target_hit_count": source_replay["combined_target_hit_count"],
        "source_v4_7_16_baseline_miss_to_hit_count": source_replay["baseline_miss_to_hit_count"],
        "xlsx_table_axis_repair_decision": xlsx_audit["decision"],
        "xlsx_table_axis_candidate_count": xlsx_audit["safe_table_axis_candidate_count"],
        "xlsx_table_axis_target_hit_gain_count": xlsx_audit["safe_table_axis_target_hit_gain_count"],
        "xlsx_table_axis_gain_rate_per_baseline_miss": xlsx_audit["safe_table_axis_gain_rate_per_baseline_miss"],
        "xlsx_baseline_target_hit_count": xlsx_family["baseline_target_hit_count"],
        "xlsx_combined_target_hit_count": xlsx_family["combined_target_hit_count"],
        "xlsx_target_hit_regression_count": xlsx_family["target_hit_regression_count"],
        "text_baseline_miss_to_hit_count": _as_int(source_counters.get("text_baseline_miss_to_hit_count")),
        "pdf_target_hit_regression_count": _as_int(source_counters.get("pdf_target_hit_regression_count")),
        "generated_response_count": 0,
        "claim_support_fail_count": 0,
        "parser_failure_count": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def build_report(
    *,
    root: Path,
    generated_at: str | None = None,
    source_report: Mapping[str, Any] | None = None,
    check: bool = True,
) -> dict[str, Any]:
    v4716_report = _load_source_report(root, source_report=source_report)
    silver_topk_rows, topk_resolution = _load_silver_topk_rows(root)
    validation = _build_candidate_only_generalization_validation(
        root=root,
        source_report=v4716_report,
        silver_topk_rows=silver_topk_rows,
        topk_resolution=topk_resolution,
    )
    xlsx_audit = _build_xlsx_table_axis_repair_audit(root=root, source_report=v4716_report)
    counters = _build_counters(validation, xlsx_audit, v4716_report)
    report = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated_at or utc_now_iso(),
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
            "source_report_json": SOURCE_REPORT_JSON.as_posix(),
            "source_topk_rows_jsonl": SOURCE_TOPK_ROWS.as_posix(),
            "source_registry_jsonl": SOURCE_REGISTRY_JSONL.as_posix(),
        },
        "artifact_sha256": {},
        "source_run_id": SOURCE_RUN_ID,
        "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        "source_topk_rows_jsonl": SOURCE_TOPK_ROWS.as_posix(),
        "source_registry_jsonl": SOURCE_REGISTRY_JSONL.as_posix(),
        "source_topk_sha256": _clean(topk_resolution.get("sha256")),
        "source_topk_expected_sha256": _clean(topk_resolution.get("expected_sha256")),
        "source_topk_sha256_verified": bool(topk_resolution.get("sha256_verified")),
        "source_topk_resolved_via_archive": bool(topk_resolution.get("resolved_via_archive")),
        "source_topk_physical_path_redacted": True,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
        "SearchView_vector_payload_role": "candidate_only",
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "answer_generation_attempted": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "candidate_only_generalization_validation": validation,
        "xlsx_table_axis_repair_audit": xlsx_audit,
        "anti_overfit_guardrails": _anti_overfit_guardrails(),
        "counters": counters,
        "completion_branch": "candidate_only_generalization_validated_xlsx_table_axis_audit_ready",
        "residual_risks": [
            "candidate-only target recall validation is diagnostic-only and uses target ids only after candidate construction for evaluation",
            "XLSX table-axis repair remains inconclusive because safe sheet/row/column/range axes add only two target hits",
            "no official metric, gold/qrels/labels, denominator mutation, training data, promotion evidence, product-success evidence, or live-readiness surface is opened",
        ],
    }
    if check:
        check_report(report)
    return report


def write_report_bundle(root: Path, report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    report = json.loads(json.dumps(report, ensure_ascii=False))
    write_json(root / SHORT_REPORT_PATH, report)
    hashes = {"report_json_sha256": sha256_file(root / SHORT_REPORT_PATH)}
    return report, hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    counters = report["counters"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "diagnostic_v4_7_17_candidate_only_generalization_validation_xlsx_table_axis_audit_nonprod",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "source_run_id": SOURCE_RUN_ID,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "protected_namespaces_touched": [],
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "candidate_only_generalization_validated": counters["candidate_only_generalization_validated"],
        "poisoned_oracle_field_evaluation_changed": counters["poisoned_oracle_field_evaluation_changed"],
        "source_v4_7_16_baseline_target_hit_count": counters["source_v4_7_16_baseline_target_hit_count"],
        "source_v4_7_16_combined_target_hit_count": counters["source_v4_7_16_combined_target_hit_count"],
        "source_v4_7_16_baseline_miss_to_hit_count": counters["source_v4_7_16_baseline_miss_to_hit_count"],
        "xlsx_table_axis_repair_decision": counters["xlsx_table_axis_repair_decision"],
        "xlsx_table_axis_candidate_count": counters["xlsx_table_axis_candidate_count"],
        "xlsx_table_axis_target_hit_gain_count": counters["xlsx_table_axis_target_hit_gain_count"],
        "xlsx_table_axis_gain_rate_per_baseline_miss": counters["xlsx_table_axis_gain_rate_per_baseline_miss"],
        "xlsx_target_hit_regression_count": counters["xlsx_target_hit_regression_count"],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def append_status(root: Path, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    path = root / STATUS_JSONL_PATH
    rows = read_jsonl(path) if path.exists() else []
    event_type = "diagnostic_v4_7_17_candidate_only_generalization_validation_xlsx_table_axis_audit_nonprod"
    rows = [
        row
        for row in rows
        if row.get("run_id") not in {SHORT_RUN_ID, CANONICAL_LONG_RUN_ID}
        and row.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID
        and row.get("event_type") != event_type
    ]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    write_jsonl(path, rows)


def _upsert_block(text: str, *, start_marker: str, end_marker: str, block: str, after_anchor: str | None = None) -> str:
    wrapped = f"{start_marker}\n{block.rstrip()}\n{end_marker}"
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.S)
    if pattern.search(text):
        return pattern.sub(wrapped, text, count=1)
    if after_anchor and after_anchor in text:
        return text.replace(after_anchor, after_anchor + "\n\n" + wrapped, 1)
    return wrapped + "\n" + text


def _sync_last_updated(text: str) -> str:
    return re.sub(r"Last updated: .*? KST\.", f"Last updated: {KST_DOC_DATE} KST.", text, count=1)


def _replace_summary_block(text: str, *, block: str) -> str:
    start = "<!-- v4_7_17_summary_start -->"
    end = "<!-- v4_7_17_summary_end -->"
    wrapped = f"{start}\n{block.rstrip()}\n{end}"
    prior_current_summary = re.compile(r"<!-- v4_7[^>]*_summary_start -->.*?<!-- v4_7[^>]*_summary_end -->", re.S)
    if prior_current_summary.search(text):
        return prior_current_summary.sub(wrapped, text, count=1)
    return _upsert_block(text, start_marker=start, end_marker=end, block=block)


def update_docs(root: Path, report: Mapping[str, Any]) -> None:
    counters = report["counters"]
    validation = report["candidate_only_generalization_validation"]
    source_replay = validation["source_v4_7_16_candidate_replay"]
    xlsx_audit = report["xlsx_table_axis_repair_audit"]
    xlsx_family = xlsx_audit["archive_1000_xlsx_family_recall"]
    overlay = xlsx_audit["overlay_90_xlsx_queue_context"]
    progress = root / "docs/rag-ingestion-progress.md"
    measurements = root / "docs/rag-ingestion-measurements.md"
    triage = root / "docs/rag-ingestion-triage.md"
    readme = root / "README.md"
    eval_readme = root / "ai/eval/README.md"
    scripts_readme = root / "ai/scripts/README.md"

    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} is artifact-ready / candidate-only generalization "
        f"validation-ready and XLSX table-axis repair audit-ready. Artifact: `{SHORT_REPORT_PATH.as_posix()}`. "
        f"v4_7_16 candidate replay digest matches recomputation={str(source_replay['source_candidate_set_sha256_matches_recomputed']).lower()} "
        f"and remains stable under poisoned target/gold/supporting/query-id fields={str(validation['poisoned_oracle_field_digest_stable']).lower()}, "
        f"while evaluation changes after target poisoning={str(validation['poisoned_oracle_field_evaluation_changed']).lower()}. "
        f"XLSX safe table-axis audit stays inconclusive: {xlsx_audit['safe_table_axis_target_hit_gain_count']} target-hit gains "
        f"from {xlsx_family['baseline_target_miss_count']} baseline misses and {xlsx_audit['safe_table_axis_candidate_count']} "
        "candidate-only axis candidates; raw XLSX parsing, direct normalized value matching, workbook/source-title shortcuts, "
        "formula exposure, target/gold locators, and row-specific hacks remain closed. official_metric_input_rows=0, "
        "silver_promoted_to_gold_count=0, promotion_evidence=false, product_success_evidence_allowed=false, "
        "live_db_index_cache_readiness=false; silver, gold, qrels, labels, expected/supporting evidence, denominator rows, "
        "source registry, indexes, cache, and production DB are not mutated."
    )
    progress.write_text(
        _sync_last_updated(
            _upsert_block(
                progress.read_text(encoding="utf-8"),
                start_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
                end_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
                block=progress_block,
                after_anchor="# RAG Ingestion Progress",
            )
        ),
        encoding="utf-8",
    )

    measurements_block = f"""## v4_7_17 candidate-only generalization validation and XLSX table-axis repair audit

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`

| counter | value |
| --- | --- |
| status | {STATUS} |
| source_run_id | {SOURCE_RUN_ID} |
| candidate_only_generalization_status | {validation['status']} |
| source_candidate_set_sha256_matches_recomputed | {str(source_replay['source_candidate_set_sha256_matches_recomputed']).lower()} |
| poisoned_oracle_field_digest_stable | {str(validation['poisoned_oracle_field_digest_stable']).lower()} |
| poisoned_oracle_field_evaluation_changed | {str(validation['poisoned_oracle_field_evaluation_changed']).lower()} |
| source_v4_7_16_baseline_target_hit_count | {source_replay['baseline_target_hit_count']} |
| source_v4_7_16_combined_target_hit_count | {source_replay['combined_target_hit_count']} |
| source_v4_7_16_baseline_miss_to_hit_count | {source_replay['baseline_miss_to_hit_count']} |
| xlsx_table_axis_audit_status | {xlsx_audit['status']} |
| xlsx_table_axis_repair_decision | {xlsx_audit['decision']} |
| xlsx_baseline_to_combined | {xlsx_family['baseline_target_hit_count']} -> {xlsx_family['combined_target_hit_count']} |
| xlsx_table_axis_candidate_count | {xlsx_audit['safe_table_axis_candidate_count']} |
| xlsx_table_axis_target_hit_gain_count | {xlsx_audit['safe_table_axis_target_hit_gain_count']} |
| xlsx_table_axis_gain_rate_per_baseline_miss | {xlsx_audit['safe_table_axis_gain_rate_per_baseline_miss']} |
| xlsx_target_hit_regression_count | {xlsx_family['target_hit_regression_count']} |
| xlsx_overlay_target_not_in_topk_total | {overlay['target_not_in_topk_total']} |
| xlsx_repeated_prefix_cluster_overlap_with_target_miss | {overlay['repeated_prefix_cluster_overlap_with_target_miss']} |
| source_topk_sha256_verified | {str(report['source_topk_sha256_verified']).lower()} |
| source_topk_resolved_via_archive | {str(report['source_topk_resolved_via_archive']).lower()} |
| official_metric_input_rows | 0 |
| direct_normalized_answer_value_matching | false |
| raw_xlsx_query_time_parsing | false |
| source_file_title_shortcut_used | false |
"""
    measurements.write_text(
        _sync_last_updated(
            _upsert_block(
                measurements.read_text(encoding="utf-8"),
                start_marker="<!-- v4_7_17_measurements_start -->",
                end_marker="<!-- v4_7_17_measurements_end -->",
                block=measurements_block,
                after_anchor="# RAG Ingestion Measurements",
            )
        ),
        encoding="utf-8",
    )

    triage_block = (
        f"- {SHORT_RUN_ID} validates the v4_7_16 candidate-only generalization boundary: candidate-set digest "
        f"matches recomputation and stays stable when target/gold/supporting/query-id fields are poisoned, proving those "
        "fields do not construct or score candidates; target labels remain after-the-fact diagnostic evaluation only. "
        f"XLSX table-axis repair decision remains {xlsx_audit['decision']}: safe sheet/row/column/range axes add "
        f"{xlsx_audit['safe_table_axis_target_hit_gain_count']} target hits from "
        f"{xlsx_family['baseline_target_miss_count']} baseline misses, with overlay XLSX target_not_in_topk "
        f"{overlay['target_not_in_topk_total']} and repeated-prefix overlap with target miss "
        f"{overlay['repeated_prefix_cluster_overlap_with_target_miss']}. No direct normalized value matching, raw XLSX "
        "query-time parsing, source-title/workbook shortcut, formula exposure, target/gold locator use, silver/gold/qrels, "
        "label, expected/supporting evidence, denominator, source registry, cache, production DB, or index mutation."
    )
    triage.write_text(
        _sync_last_updated(
            _upsert_block(
                triage.read_text(encoding="utf-8"),
                start_marker="<!-- v4_7_17_triage_start -->",
                end_marker="<!-- v4_7_17_triage_end -->",
                block=triage_block,
                after_anchor="# RAG Ingestion Triage",
            )
        ),
        encoding="utf-8",
    )

    summary_block = (
        "## Current RAG Diagnostic Status\n"
        f"Current RAG status: `{STATUS}`.\n"
        "`current` resolves to `v4_7_17`: non-production candidate-only generalization validation and XLSX table-axis "
        "repair audit. The v4_7_16 candidate replay digest is recomputed and poison-field stable, while target poisoning "
        "changes only after-the-fact evaluation. v4_7_16_target_recall_repair_prototype remains explicit for historical "
        f"checks: archived baseline target hits {source_replay['baseline_target_hit_count']}/1000 became diagnostic "
        f"combined target hits {source_replay['combined_target_hit_count']}/1000. XLSX remains inconclusive: safe "
        f"sheet/row/column/range axes add {xlsx_audit['safe_table_axis_target_hit_gain_count']} target hits from "
        f"{xlsx_family['baseline_target_miss_count']} baseline misses, so future work must stay candidate-only and avoid "
        "raw XLSX parsing, direct normalized value matching, source-title shortcuts, formula exposure, target/gold locators, "
        "and threshold tuning. Canonical details: `docs/rag-ingestion-progress.md`, "
        "`docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md`; prior v4_7 cleanup keys remain "
        "checkable through explicit aliases.\n"
        "Lineage breadcrumbs: v4_7 remains pre-official; it supersedes the abstract v4_7_1 Korean review packet; "
        "the hydrated packet has hydrated rows 204, PDF 100, XLSX 104 and non-empty `질의문` 204; "
        "v4_7_3 applies the user-reviewed Korean query candidate CSV and v4_7_3 applies the user-reviewed CSV "
        "decisions with 미검수=통과; PDF survivor 58 and v4_7_4 replays only the 58 user-passed PDF survivor "
        "candidates. official_metric_input_rows=0. "
        "## Korean human review packet. The previous v4_7_1 Korean review packet was abstract; "
        "review_packet_ko_hydrated.xlsx carries actual Korean query candidates. "
        "User-owned fields remain blank/default; not official metric. fine_tuning_executed=false.\n"
        "Hard boundary: diagnostic-only, non-production, not official metric, not gold/qrels/labels, "
        "not denominator/training/fine-tuning/FT-A, not promotion evidence, not product-success evidence, "
        "and not live readiness."
    )
    for path in (readme, eval_readme):
        path.write_text(_replace_summary_block(path.read_text(encoding="utf-8"), block=summary_block), encoding="utf-8")

    row = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        "`current` resolves to `v4_7_17`, `v4_7_16_target_recall_repair_prototype` remains explicit, "
        "`v4_7_15_read_only_searchindex_replay_projection` remains explicit, "
        "`v4_7_14_diagnostic_precondition_hardening` remains explicit, "
        "`v4_7_13_live_retrieval_answerability_and_full_pdf_replay` remains explicit, "
        "`v4_7_12_layered_retrieval_generalization_and_overfit_audit` records layered retrieval audit rows 1057, "
        "`v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness`, "
        "`v4_7_9_pdf_evidence_residual_answer_quality_replay`, and prior v4_7 cleanup keys remain checkable "
        "without opening official metrics. |"
    )
    scripts_text = scripts_readme.read_text(encoding="utf-8")
    scripts_text = re.sub(r"\| `rag_eval.py` \|.*?\|", row, scripts_text, count=1)
    scripts_readme.write_text(scripts_text, encoding="utf-8")


def _assert_no_raw_payload_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        overlap = RAW_PAYLOAD_FORBIDDEN_KEYS & set(value)
        if overlap:
            raise ValueError(f"v4_7_17 raw prompt/response leakage keys present: {sorted(overlap)}")
        for child in value.values():
            _assert_no_raw_payload_keys(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_raw_payload_keys(child)


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v4_7_17 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v4_7_17 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v4_7_17 status mismatch")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v4_7_17 must remain diagnostic-only and non-production")
    for key in FORBIDDEN_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v4_7_17 opened forbidden gate: {key}")
    if report.get("official_metric_input_rows") != 0 or report.get("silver_official_metric_input_rows") != 0:
        raise ValueError("v4_7_17 opened official metric rows")
    if report.get("silver_promoted_to_gold_count") != 0:
        raise ValueError("v4_7_17 promoted silver")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_17 touched protected namespaces")
    if report.get("SearchView_vector_payload_role") != "candidate_only":
        raise ValueError("v4_7_17 SearchView/vector payload role changed")
    if report.get("SourceAtom_EvidenceBundle_role") != "evidence_truth":
        raise ValueError("v4_7_17 SourceAtom/EvidenceBundle role changed")
    if report.get("answer_generation_attempted") is not False:
        raise ValueError("v4_7_17 must not generate substitute answers")
    if report.get("raw_prompt_payload_written") is not False or report.get("raw_response_payload_written") is not False:
        raise ValueError("v4_7_17 raw prompt/response payload must not be written")
    _assert_no_raw_payload_keys(report)

    validation = report.get("candidate_only_generalization_validation") or {}
    if validation.get("status") != "CANDIDATE_ONLY_GENERALIZATION_VALIDATED_DIAGNOSTIC_ONLY":
        raise ValueError("v4_7_17 candidate-only validation status mismatch")
    source_replay = validation.get("source_v4_7_16_candidate_replay") or {}
    for key, expected in (
        ("row_count", 1000),
        ("baseline_target_hit_count", 300),
        ("combined_target_hit_count", 514),
        ("baseline_miss_to_hit_count", 214),
        ("baseline_hit_to_miss_count", 0),
    ):
        if source_replay.get(key) != expected:
            raise ValueError(f"v4_7_17 source replay drift: {key}")
    if source_replay.get("source_candidate_set_sha256_matches_recomputed") is not True:
        raise ValueError("v4_7_17 candidate digest did not match recomputation")
    if source_replay.get("source_topk_sha256_verified") is not True or source_replay.get("source_topk_resolved_via_archive") is not True:
        raise ValueError("v4_7_17 top-k source was not sha-verified through archive")
    if validation.get("poisoned_oracle_field_digest_stable") is not True:
        raise ValueError("v4_7_17 candidate digest changed under poisoned oracle fields")
    if validation.get("poisoned_oracle_field_evaluation_changed") is not True:
        raise ValueError("v4_7_17 poisoned target fields did not affect after-the-fact evaluation")
    if validation.get("per_query_candidates_written") is not False:
        raise ValueError("v4_7_17 wrote per-query candidates")
    for key in ("diagnostic_target_labels_used_for_candidate_construction", "diagnostic_target_labels_used_for_candidate_scoring"):
        if validation.get(key) is not False:
            raise ValueError("v4_7_17 target labels used during candidate construction or scoring")
    if validation.get("diagnostic_target_labels_used_for_after_the_fact_evaluation") is not True:
        raise ValueError("v4_7_17 target labels must be after-the-fact diagnostic evaluation only")
    field_scope = validation.get("candidate_construction_field_scope") or {}
    counts = field_scope.get("allowed_field_count_by_scope") or {}
    if counts != {"query": 2, "source_registry_TEXT": 3, "source_registry_XLSX": 6}:
        raise ValueError("v4_7_17 candidate construction field-scope drift")
    forbidden_fields = set(field_scope.get("forbidden_fields") or [])
    for key in ("target_source_atom_ids", "expected_answer", "raw_locator.normalized_value", "raw_locator.cell"):
        if key not in forbidden_fields:
            raise ValueError(f"v4_7_17 missing forbidden field: {key}")

    xlsx = report.get("xlsx_table_axis_repair_audit") or {}
    if xlsx.get("status") != "XLSX_TABLE_AXIS_REPAIR_AUDIT_INCONCLUSIVE_DIAGNOSTIC_ONLY":
        raise ValueError("v4_7_17 XLSX audit status mismatch")
    if xlsx.get("decision") != "keep_inconclusive_low_gain_candidate_only":
        raise ValueError("v4_7_17 XLSX audit decision must stay inconclusive")
    if xlsx.get("safe_table_axis_fields") != XLSX_SAFE_TABLE_AXIS_FIELDS:
        raise ValueError("v4_7_17 XLSX safe table-axis field drift")
    family = xlsx.get("archive_1000_xlsx_family_recall") or {}
    for key, expected in (
        ("row_count", 325),
        ("baseline_target_hit_count", 15),
        ("combined_target_hit_count", 17),
        ("baseline_miss_to_hit_count", 2),
        ("target_hit_regression_count", 0),
        ("prototype_candidate_count", 133),
    ):
        if family.get(key) != expected:
            raise ValueError(f"v4_7_17 XLSX family drift: {key}")
    if xlsx.get("safe_table_axis_target_hit_gain_count") != 2:
        raise ValueError("v4_7_17 XLSX table-axis gain drift")
    if xlsx.get("safe_table_axis_candidate_count") != 133:
        raise ValueError("v4_7_17 XLSX table-axis candidate count drift")
    if xlsx.get("safe_table_axis_gain_rate_per_baseline_miss") != "2/310":
        raise ValueError("v4_7_17 XLSX gain-rate drift")
    overlay = xlsx.get("overlay_90_xlsx_queue_context") or {}
    if overlay.get("target_not_in_topk_total") != 28:
        raise ValueError("v4_7_17 XLSX overlay target-not-in-topk drift")
    if overlay.get("repeated_prefix_cluster_total") != 22:
        raise ValueError("v4_7_17 XLSX repeated-prefix queue drift")
    if overlay.get("repeated_prefix_cluster_overlap_with_target_miss") != 20:
        raise ValueError("v4_7_17 XLSX repeated-prefix overlap drift")
    axis_presence = xlsx.get("source_registry_xlsx_axis_presence_summary") or {}
    for key, expected in (
        ("source_atoms_audited", 343),
        ("row_label_present_count", 19),
        ("column_label_present_count", 19),
        ("target_column_present_count", 19),
        ("cell_level_locator_count", 96),
        ("range_only_locator_count", 247),
        ("normalized_value_present_but_forbidden_count", 19),
    ):
        if axis_presence.get(key) != expected:
            raise ValueError(f"v4_7_17 XLSX axis presence drift: {key}")
    for key, expected in (
        ("direct_normalized_value_matching_used_count", 0),
        ("raw_xlsx_query_time_parsing_used_count", 0),
        ("workbook_or_source_title_shortcut_used_count", 0),
        ("formula_text_exposure_used_count", 0),
        ("target_or_gold_locator_used_count", 0),
    ):
        if xlsx.get(key) != expected:
            labels = {
                "direct_normalized_value_matching_used_count": "normalized value",
                "raw_xlsx_query_time_parsing_used_count": "raw XLSX",
                "workbook_or_source_title_shortcut_used_count": "source title",
                "formula_text_exposure_used_count": "formula",
                "target_or_gold_locator_used_count": "target/gold locator",
            }
            label = labels[key]
            raise ValueError(f"v4_7_17 XLSX shortcut opened: {label}")
    boundary = xlsx.get("future_repair_boundary") or {}
    for key in (
        "raw_xlsx_query_time_parsing",
        "direct_normalized_answer_value_matching",
        "source_file_title_shortcut_used",
        "formula_evaluation",
        "formula_text_exposure",
        "gold_or_target_locator_use",
    ):
        if boundary.get(key) is not False:
            raise ValueError(f"v4_7_17 XLSX future repair boundary opened: {key}")
    if boundary.get("candidate_only_searchview_materialization_required") is not True:
        raise ValueError("v4_7_17 XLSX boundary must require candidate-only SearchView materialization")

    guardrails = report.get("anti_overfit_guardrails") or {}
    if guardrails.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_17 guardrail touched protected namespaces")
    if guardrails.get("official_metric_input_rows") != 0 or guardrails.get("silver_official_metric_input_rows") != 0:
        raise ValueError("v4_7_17 guardrail opened official metric rows")
    for key, value in guardrails.items():
        if key.endswith("_allowed") or key.endswith("_used") or key.endswith("_created"):
            if value is not False:
                raise ValueError(f"v4_7_17 guardrail opened: {key}")
        if key in GUARDRAIL_FALSE_KEYS and value is not False:
            raise ValueError(f"v4_7_17 guardrail opened: {key}")

    counters = report.get("counters") or {}
    required = (
        "current_resolves_to",
        "candidate_only_generalization_validated",
        "source_v4_7_16_baseline_target_hit_count",
        "source_v4_7_16_combined_target_hit_count",
        "source_v4_7_16_baseline_miss_to_hit_count",
        "xlsx_table_axis_repair_decision",
        "xlsx_table_axis_candidate_count",
        "xlsx_table_axis_target_hit_gain_count",
        "xlsx_target_hit_regression_count",
        "generated_response_count",
        "claim_support_fail_count",
        "parser_failure_count",
    )
    missing = [key for key in required if key not in counters]
    if missing:
        raise ValueError(f"v4_7_17 missing counters: {missing}")
    if counters["current_resolves_to"] != LOGICAL_RUN_KEY:
        raise ValueError("current must resolve to v4_7_17")
    for key, expected in (
        ("candidate_only_generalization_validated", True),
        ("source_v4_7_16_baseline_target_hit_count", 300),
        ("source_v4_7_16_combined_target_hit_count", 514),
        ("source_v4_7_16_baseline_miss_to_hit_count", 214),
        ("xlsx_table_axis_repair_decision", "keep_inconclusive_low_gain_candidate_only"),
        ("xlsx_table_axis_candidate_count", 133),
        ("xlsx_table_axis_target_hit_gain_count", 2),
        ("xlsx_target_hit_regression_count", 0),
        ("generated_response_count", 0),
        ("claim_support_fail_count", 0),
        ("parser_failure_count", 0),
    ):
        if counters.get(key) != expected:
            raise ValueError(f"v4_7_17 counter drift: {key}")
