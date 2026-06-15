"""Generate detailed diagnostics after the silver-only tuning pass.

This script is report-only. It reuses the silver-only tuning runner's
deterministic scoring helpers to explain query-level deltas, PDF FILE lookup
rank errors, and small OCR/IDP/multimodal shadow-lane samples. It does not
train, tune, index, or mutate official denominator artifacts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(AI_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_WORKER_ROOT))

import rag_silver_only_tuning_pass as silver_pass
from app.capabilities.rag.shadow_lane_contract import (
    IDP_TABLE_MEDIUM,
    MULTIMODAL_CAPTION_LOW,
    NATIVE_TEXT_HIGH,
    OCR_MEDIUM,
    ExtractionUnit,
    assert_can_enter_official_denominator,
    rank_by_trust,
    to_diagnostic_search_unit,
)


DEFAULT_CONFIG = silver_pass.DEFAULT_CONFIG
DEFAULT_REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
REPORT_NAMES = {
    "query_delta_json": "silver_tuning_query_delta_report.json",
    "query_delta_md": "silver_tuning_query_delta_report.md",
    "hit5_json": "text_hit5_regression_review.json",
    "hit5_md": "text_hit5_regression_review.md",
    "pdf_rank_json": "pdf_file_lookup_rank_error_analysis.json",
    "pdf_rank_md": "pdf_file_lookup_rank_error_analysis.md",
    "ocr_json": "ocr_shadow_small_sample_report.json",
    "ocr_md": "ocr_shadow_small_sample_report.md",
    "idp_json": "idp_shadow_small_sample_report.json",
    "idp_md": "idp_shadow_small_sample_report.md",
    "multimodal_json": "multimodal_shadow_small_sample_report.json",
    "multimodal_md": "multimodal_shadow_small_sample_report.md",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = silver_pass.load_config(Path(args.config))
    report_dir = silver_pass.resolve_path(args.reports_dir)
    outputs = run_analysis(config, report_dir)
    print(json.dumps({"status": "PASS", "outputs": outputs}, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORT_DIR))
    return parser.parse_args(argv)


def run_analysis(config: Mapping[str, Any], report_dir: Path) -> dict[str, str]:
    output_paths = {key: report_dir / name for key, name in REPORT_NAMES.items()}
    baseline = read_json(silver_pass.output_paths(config)["baseline_json"])
    silver_tuning = read_json(silver_pass.output_paths(config)["silver_tuning_run_json"])
    gold_after = read_json(silver_pass.output_paths(config)["gold_eval_after_silver_tuning_json"])
    rows = silver_pass.load_all_rows(config)
    top_k = int(config.get("tuning", {}).get("top_k", 10))

    text_profiles = {profile["name"]: profile for profile in config.get("tuning", {}).get("text_profiles", [])}
    baseline_text_profile = ((baseline.get("lanes") or {}).get("TEXT_MAIN_POSITIVE") or {}).get("profile")
    selected_text_profile = (silver_tuning.get("selected_profiles") or {}).get("text")
    if baseline_text_profile not in text_profiles:
        raise ValueError(f"baseline TEXT profile not found in config: {baseline_text_profile}")
    if selected_text_profile not in text_profiles:
        raise ValueError(f"selected TEXT profile not found in config: {selected_text_profile}")

    corpus_path = silver_pass.resolve_path(config["corpora"]["text_rag_chunks_jsonl"])
    baseline_text_index = silver_pass.build_text_index(corpus_path, text_profiles[baseline_text_profile])
    selected_text_index = silver_pass.build_text_index(corpus_path, text_profiles[selected_text_profile])

    query_delta = build_text_query_delta_report(
        config=config,
        baseline=baseline,
        silver_tuning=silver_tuning,
        gold_after=gold_after,
        gold_rows=rows["text_gold_main_positive"],
        silver_hard_negative_rows=rows["silver_text_hard_negative"],
        baseline_index=baseline_text_index,
        selected_index=selected_text_index,
        top_k=top_k,
    )
    hit5 = build_hit5_regression_report(query_delta)
    pdf_rank = build_pdf_rank_error_report(config, rows, gold_after, top_k=top_k)
    ocr_report = build_ocr_shadow_report()
    idp_report = build_idp_shadow_report()
    multimodal_report = build_multimodal_shadow_report()

    silver_pass.write_json(output_paths["query_delta_json"], query_delta)
    silver_pass.write_text(output_paths["query_delta_md"], render_query_delta_md(query_delta))
    silver_pass.write_json(output_paths["hit5_json"], hit5)
    silver_pass.write_text(output_paths["hit5_md"], render_hit5_md(hit5))
    silver_pass.write_json(output_paths["pdf_rank_json"], pdf_rank)
    silver_pass.write_text(output_paths["pdf_rank_md"], render_pdf_rank_md(pdf_rank))
    silver_pass.write_json(output_paths["ocr_json"], ocr_report)
    silver_pass.write_text(output_paths["ocr_md"], render_shadow_md("OCR Shadow Small Sample Report", ocr_report))
    silver_pass.write_json(output_paths["idp_json"], idp_report)
    silver_pass.write_text(output_paths["idp_md"], render_shadow_md("IDP Shadow Small Sample Report", idp_report))
    silver_pass.write_json(output_paths["multimodal_json"], multimodal_report)
    silver_pass.write_text(
        output_paths["multimodal_md"],
        render_shadow_md("Multimodal Shadow Small Sample Report", multimodal_report),
    )
    return {key: silver_pass.repo_relative(path) for key, path in output_paths.items()}


def build_text_query_delta_report(
    *,
    config: Mapping[str, Any],
    baseline: Mapping[str, Any],
    silver_tuning: Mapping[str, Any],
    gold_after: Mapping[str, Any],
    gold_rows: list[dict[str, str]],
    silver_hard_negative_rows: list[dict[str, str]],
    baseline_index: silver_pass.TextIndex,
    selected_index: silver_pass.TextIndex,
    top_k: int,
) -> dict[str, Any]:
    query_deltas = [
        compare_text_query(row, baseline_index, selected_index, top_k=top_k)
        for row in gold_rows
    ]
    improved = [row for row in query_deltas if row["movement"] == "improved"]
    regressed = [row for row in query_deltas if row["movement"] == "regressed"]
    unchanged = [row for row in query_deltas if row["movement"] == "unchanged"]

    hard_before = silver_pass.evaluate_text_hard_negative(silver_hard_negative_rows, baseline_index, top_k=top_k)
    hard_after = silver_pass.evaluate_text_hard_negative(silver_hard_negative_rows, selected_index, top_k=top_k)
    metric_comparison = compare_lane_metrics(
        ((baseline.get("lanes") or {}).get("TEXT_MAIN_POSITIVE") or {}).get("metrics") or {},
        ((gold_after.get("lanes") or {}).get("TEXT_MAIN_POSITIVE") or {}).get("metrics") or {},
        ("Hit@1", "Hit@3", "Hit@5", "Hit@10", "MRR@10", "recall@10"),
    )
    abstain_behavior = compare_lane_metrics(
        ((baseline.get("lanes") or {}).get("TEXT_ABSTAIN_DIAGNOSTIC") or {}).get("metrics") or {},
        ((gold_after.get("lanes") or {}).get("TEXT_ABSTAIN_DIAGNOSTIC") or {}).get("metrics") or {},
        ("any_result_rate", "diagnostic_expected_hit@10"),
    )
    hit5_regressions = [row for row in query_deltas if row["before_hit@5"] and not row["after_hit@5"]]
    concerning_regression = bool(hit5_regressions) or float(metric_comparison["Hit@5"]["delta"]) < 0.0
    hard_negative_worse = (
        float(hard_after["metrics"].get("hard_negative_confusion_rate", 0.0))
        > float(hard_before["metrics"].get("hard_negative_confusion_rate", 0.0))
    )
    decision = "remain_diagnostic_only" if (concerning_regression or hard_negative_worse) else "candidate_profile_for_review"
    decision_reason = (
        "Hit@5 regressed on frozen cleaned gold; keep selected TEXT profile diagnostic-only until the lost hits are reviewed."
        if concerning_regression
        else "No Hit@5 or hard-negative regression detected in this diagnostic pass; still requires human promotion review."
    )

    return {
        "schema_version": "silver_tuning_query_delta_report_v1",
        "status": "PASS",
        "generated_at": silver_pass.utc_timestamp(),
        "selection_policy": {
            "selection_data": silver_tuning.get("selection_data"),
            "gold_used_for_selection": silver_tuning.get("gold_used_for_selection"),
            "frozen_gold_training_rows": silver_tuning.get("frozen_gold_training_rows"),
            "profile_selected_from_frozen_gold": False,
            "official_denominator_registry_changed": False,
        },
        "profiles": {
            "baseline_text": baseline_index.profile_name,
            "selected_text": selected_index.profile_name,
        },
        "metrics": metric_comparison,
        "abstain_diagnostic_behavior": abstain_behavior | {
            "behavior": (((gold_after.get("lanes") or {}).get("TEXT_ABSTAIN_DIAGNOSTIC") or {}).get("metrics") or {}).get(
                "abstain_retrieval_behavior"
            )
        },
        "hard_negative_confusion_behavior": {
            "before": hard_before["metrics"],
            "after": hard_after["metrics"],
            "sample_confusions_before": hard_before.get("sample_confusions", []),
            "sample_confusions_after": hard_after.get("sample_confusions", []),
        },
        "query_summary": {
            "row_count": len(query_deltas),
            "improved_count": len(improved),
            "regressed_count": len(regressed),
            "unchanged_count": len(unchanged),
            "hit5_lost_count": len(hit5_regressions),
            "hit5_recovered_count": len([row for row in query_deltas if not row["before_hit@5"] and row["after_hit@5"]]),
        },
        "bucket_level_delta": bucket_level_delta(query_deltas),
        "improved_queries": compact_query_list(improved),
        "regressed_queries": compact_query_list(regressed),
        "unchanged_queries": compact_query_list(unchanged),
        "query_deltas": query_deltas,
        "selected_profile_assessment": {
            "profile": selected_index.profile_name,
            "decision": decision,
            "promotion_candidate": decision == "candidate_profile_for_review",
            "production_ready_claimed": False,
            "reason": decision_reason,
        },
        "constraints": report_constraints_payload(config),
    }


def compare_text_query(
    row: Mapping[str, str],
    baseline_index: silver_pass.TextIndex,
    selected_index: silver_pass.TextIndex,
    *,
    top_k: int,
) -> dict[str, Any]:
    before_hits = baseline_index.retrieve(row.get("query", ""), top_k)
    after_hits = selected_index.retrieve(row.get("query", ""), top_k)
    expected_doc_ids = silver_pass.split_ids(row.get("expected_page_ids") or row.get("expected_document_ids"))
    expected_chunk_ids = silver_pass.split_ids(row.get("expected_chunk_ids"))
    before_rank = silver_pass.min_rank(
        silver_pass.first_rank(expected_doc_ids, before_hits, "doc_id"),
        silver_pass.first_rank(expected_chunk_ids, before_hits, "chunk_id"),
    )
    after_rank = silver_pass.min_rank(
        silver_pass.first_rank(expected_doc_ids, after_hits, "doc_id"),
        silver_pass.first_rank(expected_chunk_ids, after_hits, "chunk_id"),
    )
    before_score = rank_score(before_rank, top_k)
    after_score = rank_score(after_rank, top_k)
    movement = "unchanged"
    if after_score < before_score:
        movement = "improved"
    elif after_score > before_score:
        movement = "regressed"
    return {
        "query_id": row.get("query_id"),
        "bucket": row.get("bucket") or "UNSPECIFIED",
        "query": row.get("query"),
        "expected_document_ids": expected_doc_ids,
        "expected_chunk_ids": expected_chunk_ids,
        "before_rank": before_rank,
        "after_rank": after_rank,
        "rank_delta_positive_is_better": before_score - after_score,
        "movement": movement,
        "before_hit@1": hit(before_rank, 1),
        "after_hit@1": hit(after_rank, 1),
        "before_hit@3": hit(before_rank, 3),
        "after_hit@3": hit(after_rank, 3),
        "before_hit@5": hit(before_rank, 5),
        "after_hit@5": hit(after_rank, 5),
        "before_hit@10": hit(before_rank, 10),
        "after_hit@10": hit(after_rank, 10),
        "before_top3": [hit_row["doc_id"] for hit_row in before_hits[:3]],
        "after_top3": [hit_row["doc_id"] for hit_row in after_hits[:3]],
    }


def build_hit5_regression_report(query_delta: Mapping[str, Any]) -> dict[str, Any]:
    deltas = list(query_delta.get("query_deltas") or [])
    lost = [row for row in deltas if row["before_hit@5"] and not row["after_hit@5"]]
    recovered = [row for row in deltas if not row["before_hit@5"] and row["after_hit@5"]]
    stable_hit = [row for row in deltas if row["before_hit@5"] and row["after_hit@5"]]
    stable_miss = [row for row in deltas if not row["before_hit@5"] and not row["after_hit@5"]]
    selected_assessment = dict(query_delta["selected_profile_assessment"])
    if lost:
        selected_assessment.update(
            {
                "decision": "remain_diagnostic_only",
                "promotion_candidate": False,
                "reason": "At least one frozen cleaned gold query lost Hit@5 after silver-only profile selection.",
            }
        )
    return {
        "schema_version": "text_hit5_regression_review_v1",
        "status": "PASS",
        "generated_at": silver_pass.utc_timestamp(),
        "profiles": query_delta.get("profiles"),
        "metrics": {"Hit@5": query_delta["metrics"]["Hit@5"], "MRR@10": query_delta["metrics"]["MRR@10"]},
        "summary": {
            "lost_hit5_count": len(lost),
            "recovered_hit5_count": len(recovered),
            "stable_hit5_count": len(stable_hit),
            "stable_miss_count": len(stable_miss),
            "net_hit5_delta_count": len(recovered) - len(lost),
        },
        "lost_hit5_queries": compact_query_list(lost, limit=100),
        "recovered_hit5_queries": compact_query_list(recovered, limit=100),
        "selected_profile_assessment": selected_assessment,
        "production_ready_claimed": False,
    }


def build_pdf_rank_error_report(
    config: Mapping[str, Any],
    rows: Mapping[str, list[dict[str, str]]],
    gold_after: Mapping[str, Any],
    *,
    top_k: int,
) -> dict[str, Any]:
    pool = silver_pass.build_pdf_candidate_pool(rows)
    pdf_profiles = {profile["name"]: profile for profile in config.get("tuning", {}).get("pdf_file_lookup_profiles", [])}
    selected_pdf_profile_name = (gold_after.get("selected_profiles") or {}).get("pdf_file_lookup")
    selected_pdf_profile = pdf_profiles.get(selected_pdf_profile_name)
    if selected_pdf_profile is None:
        raise ValueError(f"selected PDF FILE lookup profile not found in config: {selected_pdf_profile_name}")

    gold_details = pdf_rank_details(
        rows["pdf_file_lookup_gold_positive"],
        pool,
        selected_pdf_profile,
        top_k=top_k,
        split="gold_positive",
    )
    diagnostic_details = pdf_rank_details(
        rows["pdf_file_lookup_diagnostic"],
        pool,
        selected_pdf_profile,
        top_k=top_k,
        split="diagnostic",
    )
    all_details = [*gold_details, *diagnostic_details]
    top10_not_top3 = [row for row in all_details if row["expected_rank"] is not None and 3 < row["expected_rank"] <= 10]
    generic_confusions = [row for row in all_details if row["generic_filename_risk"] and row["top1_file_name"] != row["expected_file_name"]]
    similar_confusions = [row for row in all_details if row["similar_filename_confusion"]]
    docv_confusions = [row for row in all_details if row["document_version_id_confusion"]]
    return {
        "schema_version": "pdf_file_lookup_rank_error_analysis_v1",
        "status": "PASS",
        "generated_at": silver_pass.utc_timestamp(),
        "profile": selected_pdf_profile_name,
        "policy": {
            "pdf_file_lookup_semantics": "file_identity_only",
            "content_success_claimed": False,
            "page_success_claimed": False,
            "bbox_success_claimed": False,
            "table_success_claimed": False,
            "row_success_claimed": False,
            "column_success_claimed": False,
            "value_success_claimed": False,
            "page_bbox_table_row_column_value_success_claimed": False,
            "official_denominator_policy_changed": False,
        },
        "summary": {
            "gold_positive_count": len(gold_details),
            "diagnostic_count": len(diagnostic_details),
            "expected_file_in_top10_not_top3_count": len(top10_not_top3),
            "generic_filename_confusion_count": len(generic_confusions),
            "similar_filename_confusion_count": len(similar_confusions),
            "document_version_id_confusion_count": len(docv_confusions),
            "document_version_id_missing_in_rows_count": len([row for row in all_details if not row["expected_document_version_id"]]),
        },
        "expected_file_in_top10_not_top3": compact_pdf_list(top10_not_top3),
        "generic_filename_confusions": compact_pdf_list(generic_confusions),
        "similar_filename_confusions": compact_pdf_list(similar_confusions),
        "document_version_id_confusions": compact_pdf_list(docv_confusions),
        "recommended_hard_negative_expansion_rules": [
            "Add same-year and same-month files from a different family as hard negatives.",
            "Add same family with adjacent month or adjacent effective-date files as hard negatives.",
            "Add generic filename families such as file.pdf, file (3).pdf, and file (10).pdf as identity-confusion negatives.",
            "When document_version_id is populated, add same filename with mismatched document_version_id as a separate identity negative.",
            "Keep content-anchor text only as query provenance; success remains expected file identity.",
        ],
        "query_level_ranks": all_details,
    }


def pdf_rank_details(
    rows: list[dict[str, str]],
    pool: list[str],
    profile: Mapping[str, Any],
    *,
    top_k: int,
    split: str,
) -> list[dict[str, Any]]:
    details = []
    for row in rows:
        hits = silver_pass.retrieve_pdf_files(row.get("query", ""), pool, profile, top_k)
        expected = silver_pass.clean(row.get("expected_file_name") or row.get("source_file_name"))
        rank = silver_pass.first_file_rank(expected, hits)
        top1 = hits[0]["file_name"] if hits else None
        expected_docv = silver_pass.clean(row.get("expected_document_version_id"))
        generic = is_generic_filename(expected) or "GENERIC" in (row.get("risk_tags") or "") + (row.get("cleanup_issue_tags") or "")
        similar = bool(top1 and top1 != expected and is_similar_file_identity(expected, top1))
        details.append(
            {
                "split": split,
                "query_id": row.get("query_id"),
                "query": row.get("query"),
                "expected_file_name": expected,
                "expected_rank": rank,
                "top1_file_name": top1,
                "top10_file_names": [hit["file_name"] for hit in hits],
                "generic_filename_risk": generic,
                "similar_filename_confusion": similar,
                "expected_document_version_id": expected_docv,
                "document_version_id_confusion": False,
                "document_version_id_confusion_note": (
                    "not_evaluable_no_expected_document_version_id"
                    if not expected_docv
                    else "not_evaluable_candidate_pool_has_file_names_only"
                ),
                "file_identity_success_only": rank is not None and rank <= top_k,
            }
        )
    return details


def build_ocr_shadow_report() -> dict[str, Any]:
    canary_csv = DEFAULT_REPORT_DIR / "rag_pdf_supplemental_parse_canary.csv"
    canary_json = DEFAULT_REPORT_DIR / "rag_pdf_supplemental_parse_canary_report.json"
    rows = silver_pass.read_csv(canary_csv) if canary_csv.exists() else []
    ocr_row = first_row(rows, lambda row: truthy(row.get("ocr_required_candidate")) or truthy(row.get("ocr_fallback_success")))
    native_row = first_row(rows, lambda row: truthy(row.get("native_text_pdf"))) or ocr_row
    canary = read_json(canary_json) if canary_json.exists() else {}
    confidence = parse_float((ocr_row or {}).get("ocr_confidence_avg"))
    if confidence is None:
        confidence = parse_float((((canary.get("counts") or {}).get("ocr_confidence_avg"))))

    source_file = (ocr_row or native_row or {}).get("file_name") or "diagnostic-pdf-sample.pdf"
    native_unit = ExtractionUnit(
        unit_id="ocr-shadow-native-compare-001",
        lane="PDF_CONTENT",
        trust_tier=NATIVE_TEXT_HIGH,
        parser_version="shadow-lane-diagnostic-v1",
        location_json={"type": "native_pdf_text_compare", "source_report": silver_pass.repo_relative(canary_csv)},
        citation_text=f"{source_file} native text diagnostic comparison",
        embedding_text="native PDF text diagnostic comparison sample",
        bm25_text="native PDF text diagnostic comparison sample",
        display_text="Native PDF text diagnostic comparison sample",
        debug_text="Report-only native-vs-OCR trust ordering sample",
        confidence=0.70,
        source_file_name=source_file,
        unit_type="PDF_NATIVE_TEXT_DIAGNOSTIC",
    )
    ocr_unit = ExtractionUnit(
        unit_id="ocr-shadow-fallback-001",
        lane="OCR_SHADOW",
        trust_tier=OCR_MEDIUM,
        parser_version="shadow-lane-diagnostic-v1",
        location_json={"type": "ocr_fallback", "source_report": silver_pass.repo_relative(canary_csv)},
        citation_text=f"{source_file} OCR fallback diagnostic text",
        embedding_text="OCR fallback diagnostic text sample",
        bm25_text="OCR fallback diagnostic text sample",
        display_text="OCR fallback diagnostic text sample",
        debug_text="Report-only OCR fallback; lower trust than native PDF text",
        confidence=confidence,
        source_file_name=source_file,
        unit_type="OCR_FALLBACK_DIAGNOSTIC",
        extra={"ocr_confidence_bucket": confidence_bucket(confidence), "native_text_conflict": False},
    )
    ranked = rank_by_trust([ocr_unit, native_unit])
    payloads = [to_diagnostic_search_unit(ocr_unit), to_diagnostic_search_unit(native_unit)]
    return {
        "schema_version": "ocr_shadow_small_sample_report_v1",
        "status": "PASS",
        "generated_at": silver_pass.utc_timestamp(),
        "sample_scope": "small_report_only_existing_parse_canary",
        "source_artifacts": [silver_pass.repo_relative(canary_csv), silver_pass.repo_relative(canary_json)],
        "policy": shadow_policy_payload(),
        "counts": {
            "diagnostic_unit_count": len(payloads),
            "ocr_unit_count": 1,
            "native_compare_unit_count": 1,
        },
        "ocr_confidence_bucket": confidence_bucket(confidence),
        "native_text_conflict": False,
        "native_outranks_ocr_fallback": ranked[0].trust_tier == NATIVE_TEXT_HIGH,
        "required_search_unit_shaped_fields_present": all(contract_fields_present(row) for row in payloads),
        "diagnostic_rows": payloads,
    }


def build_idp_shadow_report() -> dict[str, Any]:
    xlsx_report = DEFAULT_REPORT_DIR / "xlsx_strict_silver_generation_20260507.json"
    source_ref = silver_pass.repo_relative(xlsx_report)
    units = [
        ExtractionUnit(
            unit_id="idp-shadow-key-value-001",
            lane="IDP_SHADOW",
            trust_tier=IDP_TABLE_MEDIUM,
            parser_version="shadow-lane-diagnostic-v1",
            location_json={"type": "idp_key_value", "source_report": source_ref, "field": "sample_policy_key"},
            citation_text="IDP key-value diagnostic sample",
            embedding_text="IDP key-value diagnostic sample",
            bm25_text="IDP key-value diagnostic sample",
            display_text="IDP key-value diagnostic sample",
            debug_text="Report-only IDP key-value unit; no official value success claimed",
            confidence=0.74,
            unit_type="IDP_KEY_VALUE_DIAGNOSTIC",
            extra={"official_key_value_success_claimed": False},
        ),
        ExtractionUnit(
            unit_id="idp-shadow-table-001",
            lane="IDP_SHADOW",
            trust_tier=IDP_TABLE_MEDIUM,
            parser_version="shadow-lane-diagnostic-v1",
            location_json={"type": "idp_table", "source_report": source_ref, "table_index": 0},
            citation_text="IDP table diagnostic sample",
            embedding_text="IDP table diagnostic sample",
            bm25_text="IDP table diagnostic sample",
            display_text="IDP table diagnostic sample",
            debug_text="Report-only IDP table unit; no row, column, or value success claimed",
            confidence=0.71,
            unit_type="IDP_TABLE_DIAGNOSTIC",
            extra={
                "official_table_success_claimed": False,
                "official_row_success_claimed": False,
                "official_column_success_claimed": False,
                "official_value_success_claimed": False,
            },
        ),
    ]
    rows = [to_diagnostic_search_unit(unit) for unit in units]
    official_denominator_blocks = denominator_block_results(units)
    return {
        "schema_version": "idp_shadow_small_sample_report_v1",
        "status": "PASS",
        "generated_at": silver_pass.utc_timestamp(),
        "sample_scope": "small_report_only_extraction_unit_contract",
        "source_artifacts": [source_ref],
        "policy": shadow_policy_payload(),
        "counts": {
            "diagnostic_unit_count": len(rows),
            "key_value_unit_count": 1,
            "table_unit_count": 1,
        },
        "claims": {
            "official_table_success_claimed": False,
            "official_row_success_claimed": False,
            "official_column_success_claimed": False,
            "official_value_success_claimed": False,
        },
        "official_denominator_blocks": official_denominator_blocks,
        "required_search_unit_shaped_fields_present": all(contract_fields_present(row) for row in rows),
        "diagnostic_rows": rows,
    }


def build_multimodal_shadow_report() -> dict[str, Any]:
    dataset = AI_WORKER_ROOT / "eval" / "datasets" / "multimodal_anime_kr.jsonl"
    row = first_multimodal_row_with_local_image(dataset)
    if row is None:
        return {
            "schema_version": "multimodal_shadow_small_sample_report_v1",
            "status": "SKIPPED_NO_LOCAL_ARTIFACT",
            "generated_at": silver_pass.utc_timestamp(),
            "sample_scope": "small_report_only_caption_diagnostic",
            "source_artifacts": [silver_pass.repo_relative(dataset)],
            "policy": shadow_policy_payload() | {"external_llm_used": False},
            "counts": {"diagnostic_unit_count": 0},
            "diagnostic_rows": [],
        }
    image_path = resolve_dataset_relative(dataset, row["image"])
    caption_result = describe_local_image(image_path, row.get("question"))
    if caption_result["status"] != "PASS":
        return {
            "schema_version": "multimodal_shadow_small_sample_report_v1",
            "status": caption_result["status"],
            "generated_at": silver_pass.utc_timestamp(),
            "sample_scope": "small_report_only_caption_diagnostic",
            "source_artifacts": [silver_pass.repo_relative(dataset), silver_pass.repo_relative(image_path)],
            "policy": shadow_policy_payload() | {"external_llm_used": False},
            "counts": {"diagnostic_unit_count": 0},
            "diagnostic_rows": [],
            "warning": caption_result.get("warning"),
        }
    unit = ExtractionUnit(
        unit_id="multimodal-shadow-caption-001",
        lane="MULTIMODAL_SHADOW",
        trust_tier=MULTIMODAL_CAPTION_LOW,
        parser_version="shadow-lane-diagnostic-v1",
        location_json={"type": "figure_caption", "image": silver_pass.repo_relative(image_path), "page": 1},
        citation_text=f"Caption diagnostic for {Path(row['image']).name}",
        embedding_text=caption_result["caption"],
        bm25_text=caption_result["caption"],
        display_text=caption_result["caption"],
        debug_text="Report-only multimodal caption; retrieval expansion only, not official evidence",
        confidence=None,
        source_file_name=Path(row["image"]).name,
        unit_type="MULTIMODAL_CAPTION_DIAGNOSTIC",
        extra={
            "caption_role": "retrieval_expansion_only",
            "official_evidence": False,
            "external_llm_used": False,
            "vision_provider": caption_result["provider"],
            "source_question": row.get("question"),
            "expected_keywords": row.get("expected_keywords") or [],
        },
    )
    payload = to_diagnostic_search_unit(unit)
    return {
        "schema_version": "multimodal_shadow_small_sample_report_v1",
        "status": "PASS",
        "generated_at": silver_pass.utc_timestamp(),
        "sample_scope": "small_report_only_local_heuristic_caption",
        "source_artifacts": [silver_pass.repo_relative(dataset), silver_pass.repo_relative(image_path)],
        "policy": shadow_policy_payload()
        | {
            "external_llm_used": False,
            "caption_role": "retrieval_expansion_only",
            "official_evidence_claimed": False,
        },
        "counts": {"diagnostic_unit_count": 1, "caption_unit_count": 1},
        "required_search_unit_shaped_fields_present": contract_fields_present(payload),
        "diagnostic_rows": [payload],
    }


def compare_lane_metrics(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    metrics: Sequence[str],
) -> dict[str, dict[str, float | None]]:
    comparison: dict[str, dict[str, float | None]] = {}
    for metric in metrics:
        before_value = before.get(metric)
        after_value = after.get(metric)
        comparison[metric] = {
            "before": to_float(before_value),
            "after": to_float(after_value),
            "delta": round(float(after_value or 0.0) - float(before_value or 0.0), 6),
        }
    return comparison


def bucket_level_delta(query_deltas: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in query_deltas:
        buckets[str(row.get("bucket") or "UNSPECIFIED")].append(row)
    result = {}
    for bucket, rows in sorted(buckets.items()):
        before_ranks = [row.get("before_rank") for row in rows]
        after_ranks = [row.get("after_rank") for row in rows]
        result[bucket] = {
            "row_count": len(rows),
            "Hit@1": before_after_hit(before_ranks, after_ranks, 1),
            "Hit@3": before_after_hit(before_ranks, after_ranks, 3),
            "Hit@5": before_after_hit(before_ranks, after_ranks, 5),
            "Hit@10": before_after_hit(before_ranks, after_ranks, 10),
            "MRR@10": before_after_mrr(before_ranks, after_ranks, 10),
            "improved_count": len([row for row in rows if row["movement"] == "improved"]),
            "regressed_count": len([row for row in rows if row["movement"] == "regressed"]),
            "unchanged_count": len([row for row in rows if row["movement"] == "unchanged"]),
        }
    return result


def before_after_hit(before_ranks: Sequence[Any], after_ranks: Sequence[Any], k: int) -> dict[str, float]:
    before = silver_pass.hit_at([rank if isinstance(rank, int) else None for rank in before_ranks], k)
    after = silver_pass.hit_at([rank if isinstance(rank, int) else None for rank in after_ranks], k)
    return {"before": before, "after": after, "delta": round(after - before, 6)}


def before_after_mrr(before_ranks: Sequence[Any], after_ranks: Sequence[Any], k: int) -> dict[str, float]:
    before = silver_pass.mrr_at([rank if isinstance(rank, int) else None for rank in before_ranks], k)
    after = silver_pass.mrr_at([rank if isinstance(rank, int) else None for rank in after_ranks], k)
    return {"before": before, "after": after, "delta": round(after - before, 6)}


def compact_query_list(rows: Sequence[Mapping[str, Any]], *, limit: int = 50) -> list[dict[str, Any]]:
    return [
        {
            "query_id": row.get("query_id"),
            "bucket": row.get("bucket"),
            "query": row.get("query"),
            "before_rank": row.get("before_rank"),
            "after_rank": row.get("after_rank"),
            "rank_delta_positive_is_better": row.get("rank_delta_positive_is_better"),
        }
        for row in rows[:limit]
    ]


def compact_pdf_list(rows: Sequence[Mapping[str, Any]], *, limit: int = 100) -> list[dict[str, Any]]:
    return [
        {
            "split": row.get("split"),
            "query_id": row.get("query_id"),
            "expected_file_name": row.get("expected_file_name"),
            "expected_rank": row.get("expected_rank"),
            "top1_file_name": row.get("top1_file_name"),
            "generic_filename_risk": row.get("generic_filename_risk"),
            "similar_filename_confusion": row.get("similar_filename_confusion"),
        }
        for row in rows[:limit]
    ]


def render_query_delta_md(payload: Mapping[str, Any]) -> str:
    metrics = payload["metrics"]
    summary = payload["query_summary"]
    assessment = payload["selected_profile_assessment"]
    lines = [
        "# Silver Tuning Query Delta Report",
        "",
        f"- Status: `{payload['status']}`.",
        f"- Baseline TEXT profile: `{payload['profiles']['baseline_text']}`.",
        f"- Selected TEXT profile: `{payload['profiles']['selected_text']}`.",
        f"- Selection data: `{payload['selection_policy']['selection_data']}`; gold used for selection: `{payload['selection_policy']['gold_used_for_selection']}`.",
        f"- Assessment: `{assessment['decision']}`. Production-ready claimed: `false`.",
        f"- Reason: {assessment['reason']}",
        "",
        "## Metrics",
        "",
        "| metric | before | after | delta |",
        "|---|---:|---:|---:|",
    ]
    for metric in ("Hit@1", "Hit@3", "Hit@5", "Hit@10", "MRR@10", "recall@10"):
        row = metrics[metric]
        lines.append(f"| {metric} | {fmt(row['before'])} | {fmt(row['after'])} | {fmt(row['delta'])} |")
    lines.extend(
        [
            "",
            "## Query Movement",
            "",
            f"- Improved: `{summary['improved_count']}`.",
            f"- Regressed: `{summary['regressed_count']}`.",
            f"- Unchanged: `{summary['unchanged_count']}`.",
            f"- Hit@5 lost: `{summary['hit5_lost_count']}`; Hit@5 recovered: `{summary['hit5_recovered_count']}`.",
            "",
            "## Regressed Queries",
            "",
        ]
    )
    append_query_table(lines, payload["regressed_queries"])
    lines.extend(["", "## Improved Queries", ""])
    append_query_table(lines, payload["improved_queries"][:25])
    lines.extend(["", "## Abstain And Hard Negatives", ""])
    abstain = payload["abstain_diagnostic_behavior"]
    hard = payload["hard_negative_confusion_behavior"]
    lines.append(
        f"- Abstain diagnostic expected Hit@10: `{fmt(abstain['diagnostic_expected_hit@10']['before'])}` -> "
        f"`{fmt(abstain['diagnostic_expected_hit@10']['after'])}`."
    )
    lines.append(
        f"- Hard negative confusion rate: `{fmt(hard['before']['hard_negative_confusion_rate'])}` -> "
        f"`{fmt(hard['after']['hard_negative_confusion_rate'])}`."
    )
    lines.append("")
    return "\n".join(lines)


def render_hit5_md(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    assessment = payload["selected_profile_assessment"]
    lines = [
        "# TEXT Hit@5 Regression Review",
        "",
        f"- Status: `{payload['status']}`.",
        f"- Selected TEXT profile assessment: `{assessment['decision']}`.",
        f"- Promotion candidate: `{str(assessment['promotion_candidate']).lower()}`.",
        f"- Reason: {assessment['reason']}",
        "",
        "## Hit@5 Summary",
        "",
        f"- Lost Hit@5: `{summary['lost_hit5_count']}`.",
        f"- Recovered Hit@5: `{summary['recovered_hit5_count']}`.",
        f"- Stable Hit@5: `{summary['stable_hit5_count']}`.",
        f"- Stable misses: `{summary['stable_miss_count']}`.",
        f"- Net Hit@5 delta count: `{summary['net_hit5_delta_count']}`.",
        "",
        "## Lost Hit@5 Queries",
        "",
    ]
    append_query_table(lines, payload["lost_hit5_queries"])
    lines.extend(["", "## Recovered Hit@5 Queries", ""])
    append_query_table(lines, payload["recovered_hit5_queries"])
    lines.append("")
    return "\n".join(lines)


def render_pdf_rank_md(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PDF FILE Lookup Rank Error Analysis",
        "",
        f"- Status: `{payload['status']}`.",
        f"- Profile: `{payload['profile']}`.",
        "- Semantics: `file_identity_only`.",
        "- Content/page/bbox/table/row/column/value success claimed: `false`.",
        "",
        "## Summary",
        "",
        f"- Gold positive rows: `{summary['gold_positive_count']}`.",
        f"- Diagnostic rows: `{summary['diagnostic_count']}`.",
        f"- Expected file in top 10 but not top 3: `{summary['expected_file_in_top10_not_top3_count']}`.",
        f"- Generic filename confusions: `{summary['generic_filename_confusion_count']}`.",
        f"- Similar filename confusions: `{summary['similar_filename_confusion_count']}`.",
        f"- Document-version-id confusions: `{summary['document_version_id_confusion_count']}`.",
        "",
        "## Top 10 But Not Top 3",
        "",
    ]
    append_pdf_table(lines, payload["expected_file_in_top10_not_top3"])
    lines.extend(["", "## Generic Filename Confusions", ""])
    append_pdf_table(lines, payload["generic_filename_confusions"])
    lines.extend(["", "## Recommended Hard Negatives", ""])
    for rule in payload["recommended_hard_negative_expansion_rules"]:
        lines.append(f"- {rule}")
    lines.append("")
    return "\n".join(lines)


def render_shadow_md(title: str, payload: Mapping[str, Any]) -> str:
    policy = payload.get("policy") or {}
    counts = payload.get("counts") or {}
    lines = [
        f"# {title}",
        "",
        f"- Status: `{payload['status']}`.",
        f"- Scope: `{payload.get('sample_scope')}`.",
        "- Official denominator changed: `false`.",
        f"- Denominator role: `{policy.get('denominator_role')}`.",
        f"- Production index mutation: `{policy.get('production_index_mutation')}`.",
        f"- Diagnostic unit count: `{counts.get('diagnostic_unit_count', 0)}`.",
    ]
    if "native_outranks_ocr_fallback" in payload:
        lines.append(f"- Native text outranks OCR fallback: `{str(payload['native_outranks_ocr_fallback']).lower()}`.")
    if "claims" in payload:
        lines.append("- Official row/column/value/table success claimed: `false`.")
    if policy.get("caption_role"):
        lines.append(f"- Caption role: `{policy.get('caption_role')}`.")
    lines.extend(["", "## Source Artifacts", ""])
    for artifact in payload.get("source_artifacts") or []:
        lines.append(f"- `{artifact}`")
    lines.append("")
    return "\n".join(lines)


def append_query_table(lines: list[str], rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        lines.append("- None.")
        return
    lines.extend(["| query_id | bucket | before_rank | after_rank | rank_delta |", "|---|---|---:|---:|---:|"])
    for row in rows:
        lines.append(
            f"| `{row.get('query_id')}` | {row.get('bucket') or ''} | {fmt(row.get('before_rank'))} | "
            f"{fmt(row.get('after_rank'))} | {fmt(row.get('rank_delta_positive_is_better'))} |"
        )


def append_pdf_table(lines: list[str], rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        lines.append("- None.")
        return
    lines.extend(["| split | query_id | expected_file | rank | top1 |", "|---|---|---|---:|---|"])
    for row in rows:
        lines.append(
            f"| `{row.get('split')}` | `{row.get('query_id')}` | `{row.get('expected_file_name')}` | "
            f"{fmt(row.get('expected_rank'))} | `{row.get('top1_file_name')}` |"
        )


def report_constraints_payload(config: Mapping[str, Any]) -> dict[str, Any]:
    policy = config.get("policy") or {}
    return {
        "official_denominator_registry_changed": False,
        "train_on_frozen_gold": policy.get("train_on_frozen_gold", False),
        "tune_thresholds_on_frozen_gold": policy.get("tune_thresholds_on_frozen_gold", False),
        "mutate_production_indexes": policy.get("mutate_production_indexes", False),
        "broad_indexing": policy.get("broad_indexing", False),
    }


def shadow_policy_payload() -> dict[str, Any]:
    return {
        "denominator_role": "DIAGNOSTIC_ONLY",
        "evidence_role": "diagnostic",
        "official_denominator_eligible": False,
        "official_denominator_registry_changed": False,
        "production_index_mutation": False,
        "broad_indexing": False,
    }


def denominator_block_results(units: Sequence[ExtractionUnit]) -> list[dict[str, Any]]:
    results = []
    for unit in units:
        blocked = False
        reason = ""
        try:
            assert_can_enter_official_denominator(unit)
        except ValueError as exc:
            blocked = True
            reason = str(exc)
        results.append({"unit_id": unit.unit_id, "blocked_without_explicit_policy": blocked, "reason": reason})
    return results


def first_multimodal_row_with_local_image(dataset: Path) -> dict[str, Any] | None:
    if not dataset.exists():
        return None
    for row in iter_jsonl_allow_comments(dataset):
        image = row.get("image")
        if image and resolve_dataset_relative(dataset, image).exists():
            return row
    return None


def describe_local_image(image_path: Path, question: str | None) -> dict[str, Any]:
    try:
        from app.capabilities.multimodal.heuristic_vision import HeuristicVisionProvider
    except Exception as exc:  # pragma: no cover - local import health varies by env
        return {"status": "SKIPPED_LOCAL_PROVIDER_UNAVAILABLE", "warning": f"{type(exc).__name__}: {exc}"}
    try:
        result = HeuristicVisionProvider().describe_image(
            image_path.read_bytes(),
            mime_type="image/png",
            hint=question,
            page_number=1,
        )
    except Exception as exc:  # pragma: no cover - data/decoder health varies by env
        return {"status": "SKIPPED_LOCAL_IMAGE_DECODE_FAILED", "warning": f"{type(exc).__name__}: {exc}"}
    return {
        "status": "PASS",
        "provider": result.provider_name,
        "caption": result.caption,
        "details": result.details,
        "warnings": result.warnings,
        "latency_ms": result.latency_ms,
    }


def iter_jsonl_allow_comments(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            row = json.loads(stripped)
            if isinstance(row, dict):
                yield row


def resolve_dataset_relative(dataset: Path, value: str) -> Path:
    return (dataset.parent / value).resolve()


def contract_fields_present(payload: Mapping[str, Any]) -> bool:
    return all(bool(payload.get(field)) for field in silver_pass.CONTRACT_FIELDS) if hasattr(silver_pass, "CONTRACT_FIELDS") else all(
        bool(payload.get(field))
        for field in (
            "parser_version",
            "location_json",
            "citation_text",
            "embedding_text",
            "bm25_text",
            "display_text",
            "debug_text",
        )
    )


def first_row(rows: Sequence[dict[str, str]], predicate) -> dict[str, str] | None:
    for row in rows:
        if predicate(row):
            return row
    return None


def is_generic_filename(name: str) -> bool:
    stem = Path(name).stem.lower()
    return bool(re.fullmatch(r"file(?:\s*\(\d+\))?", stem))


def is_similar_file_identity(expected: str, observed: str) -> bool:
    expected_features = silver_pass.file_features(expected)
    observed_features = silver_pass.file_features(observed)
    if expected_features["years"] & observed_features["years"]:
        return True
    if expected_features["months"] & observed_features["months"]:
        return True
    if expected_features["families"] & observed_features["families"]:
        return True
    if is_generic_filename(expected) and is_generic_filename(observed):
        return True
    expected_tokens = expected_features["tokens"]
    observed_tokens = observed_features["tokens"]
    return bool(expected_tokens and len(expected_tokens & observed_tokens) >= max(1, min(len(expected_tokens), 2)))


def confidence_bucket(confidence: float | None) -> str:
    if confidence is None:
        return "UNKNOWN"
    if confidence >= 0.90:
        return "HIGH"
    if confidence >= 0.70:
        return "MEDIUM"
    return "LOW"


def rank_score(rank: int | None, top_k: int) -> int:
    return int(rank) if rank is not None else top_k + 1


def hit(rank: int | None, k: int) -> bool:
    return rank is not None and rank <= k


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def parse_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return f"{float(value):.4f}"
    return str(value)


if __name__ == "__main__":
    sys.exit(main())
