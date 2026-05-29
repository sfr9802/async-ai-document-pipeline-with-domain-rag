from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v3_9_2_overfit_risk_audit_and_blind_holdout_reset as v392
import rag_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization as v310


ROOT = v392.ROOT
if str(ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai"))

from app.capabilities.rag.layered_retrieval import (  # noqa: E402
    LAYER_NAMES,
    LayerCandidate,
    LayerDecision,
    LayeredRetrievalTrace,
    serialize_layered_trace,
)
from app.capabilities.rag.source_registry import evidence_bundle_from_search_view  # noqa: E402


RUN_ID = "official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic"
REPORT_DIR = v392.REPORT_DIR
STATUS_JSONL = v392.STATUS_JSONL
PROGRESS_DOC = v392.PROGRESS_DOC
MEASUREMENTS_DOC = v392.MEASUREMENTS_DOC
TRIAGE_DOC = v392.TRIAGE_DOC

STATUS = "DIAGNOSTIC_V3_11_LAYERED_RETRIEVAL_READY"
EVENT_TYPE = "diagnostic_v3_11_layered_retrieval"
SKIPPED_LAYERS = ("L8_GENERATION_OR_DETERMINISTIC_EXECUTION",)
PROTECTED_NAMESPACES = (
    "rag-data-official-denominator-v1",
    "rag-data-all-source-citable-nonprod-v1",
    "production",
)

OUTPUTS = {
    "summary_json": REPORT_DIR / f"{RUN_ID}_summary.json",
    "bootstrap_json": REPORT_DIR / f"{RUN_ID}_bootstrap.json",
    "metrics_json": REPORT_DIR / f"{RUN_ID}_metrics.json",
    "per_family_json": REPORT_DIR / f"{RUN_ID}_per_family.json",
    "per_query_jsonl": REPORT_DIR / f"{RUN_ID}_per_query.jsonl",
    "layer_trace_sample_jsonl": REPORT_DIR / f"{RUN_ID}_layer_trace_sample.jsonl",
    "query_routing_audit_jsonl": REPORT_DIR / f"{RUN_ID}_query_routing_audit.jsonl",
    "query_guardrail_summary_json": REPORT_DIR / f"{RUN_ID}_query_guardrail_summary.json",
    "selected_evidence_jsonl": REPORT_DIR / f"{RUN_ID}_selected_evidence.jsonl",
    "failure_taxonomy_json": REPORT_DIR / f"{RUN_ID}_failure_taxonomy.json",
    "guardrail_audit_json": REPORT_DIR / f"{RUN_ID}_guardrail_audit.json",
    "holdout_manifest_json": REPORT_DIR / f"{RUN_ID}_holdout_manifest.json",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="microseconds") + "Z"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return v392.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v392.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def sha256_file(path: Path) -> str:
    return v392.sha256_file(path)


def artifact_exists(path: Path) -> bool:
    return v392.artifact_exists(path)


def artifact_is_file(path: Path) -> bool:
    return v392.artifact_is_file(path)


def repo_relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {"numerator": numerator, "denominator": denominator, "rate": numerator / denominator if denominator else None}


def metric_count(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, Any]:
    return ratio(sum(1 for row in rows if bool(row.get(field))), len(rows))


def clean(value: Any) -> str:
    return "" if value is None else str(value)


def first_source_atom_id(candidate: Mapping[str, Any]) -> str:
    source_atom_id = clean(candidate.get("source_atom_id"))
    if source_atom_id:
        return source_atom_id
    ids = candidate.get("supporting_source_atom_ids")
    if isinstance(ids, Sequence) and not isinstance(ids, (str, bytes)) and ids:
        return clean(ids[0])
    return ""


def first_search_view_id(candidate: Mapping[str, Any]) -> str:
    search_view_id = clean(candidate.get("search_view_id"))
    if search_view_id:
        return search_view_id
    ids = candidate.get("supporting_search_view_ids")
    if isinstance(ids, Sequence) and not isinstance(ids, (str, bytes)) and ids:
        return clean(ids[0])
    return ""


def parse_pdf_locator(source_identity: str) -> tuple[int | None, tuple[float, float, float, float] | None]:
    match = re.search(r":(\d+):\[(.*?)\]\s*$", source_identity)
    if not match:
        return None, None
    try:
        page = int(match.group(1))
        coords = tuple(float(item.strip()) for item in match.group(2).split(","))
    except ValueError:
        return None, None
    if len(coords) != 4:
        return page, None
    return page, coords  # type: ignore[return-value]


def candidate_id(query_id: str, layer_name: str, index: int) -> str:
    return f"{query_id}:{layer_name}:{index}"


def layer_candidate_from_row_candidate(
    *,
    query_id: str,
    layer_name: str,
    source_family: str,
    candidate: Mapping[str, Any],
    index: int,
) -> LayerCandidate:
    source_identity = clean(candidate.get("source_identity") or candidate.get("candidate_source_identity"))
    page, bbox = parse_pdf_locator(source_identity)
    return LayerCandidate(
        candidate_id=candidate_id(query_id, layer_name, index),
        source_family=source_family,
        layer_name=layer_name,
        source_atom_id=first_source_atom_id(candidate),
        search_view_id=first_search_view_id(candidate),
        source_identity=source_identity,
        document_version_id=clean(candidate.get("document_version_id") or candidate.get("workbook_version_id")),
        workbook_id=clean(candidate.get("workbook") or candidate.get("workbook_id") or candidate.get("file_key")),
        source_file_name=clean(candidate.get("source_file_name") or candidate.get("file_key")),
        sheet_name=clean(candidate.get("sheet") or candidate.get("sheet_name")),
        table_range=clean(candidate.get("range") or candidate.get("table_range") or candidate.get("cell_range")),
        cell=clean(candidate.get("cell")),
        page=page,
        bbox=bbox,
        score_components=dict(candidate.get("score_components") or {}),
        source_atom_hydrated_from_registry=bool(candidate.get("source_atom_hydrated_from_registry") or first_source_atom_id(candidate)),
        evidence_bundle_assembled=bool(candidate.get("contract_survived") or first_source_atom_id(candidate)),
        vector_payload_used_as_evidence_truth=bool(candidate.get("vector_metadata_used_as_evidence_truth", False)),
        canonical_payload_source="source_registry" if first_source_atom_id(candidate) else "not_hydrated",
    )


def top_candidates(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    candidates = row.get("scoped_cell_candidates")
    if not isinstance(candidates, list):
        candidates = row.get("resolved_file_candidates")
    if not isinstance(candidates, list):
        return []
    return [candidate for candidate in candidates[:3] if isinstance(candidate, Mapping)]


def load_source_registry() -> dict[str, Mapping[str, Any]]:
    registry: dict[str, Mapping[str, Any]] = {}
    for row in read_jsonl(v392.SOURCE_REGISTRY_JSONL):
        source_atom_id = clean(row.get("source_atom_id"))
        if source_atom_id:
            registry[source_atom_id] = row
    return registry


def route_decision(row: Mapping[str, Any]) -> LayerDecision:
    family = clean(row.get("source_family")).upper()
    query_id = clean(row.get("query_id"))
    flags = tuple(clean(reason) for reason in (row.get("query_drift_audit") or {}).get("reasons", []) if clean(reason))
    return LayerDecision(
        query_id=query_id,
        source_family=family,
        layer_name="L0_QUERY_ROUTING",
        signals={
            "query_text_sha256": clean(row.get("query_text_sha256")) or sha256_text(query_id),
            "requested_family": family,
            "intent_type": "cell_or_value_lookup" if family == "XLSX" else "pdf_document_lookup",
        },
        guardrail_flags=tuple(sorted(flags)),
        headline_eligible=not bool(flags),
    )


def build_trace(
    row: Mapping[str, Any],
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    query_id = clean(row.get("query_id"))
    family = clean(row.get("source_family")).upper()
    candidates = top_candidates(row)
    l1_candidates = tuple(
        layer_candidate_from_row_candidate(
            query_id=query_id,
            layer_name="L1_COARSE_CANDIDATE_GENERATION",
            source_family=family,
            candidate=candidate,
            index=index,
        )
        for index, candidate in enumerate(candidates, 1)
    )
    l2_candidates = tuple(
        layer_candidate_from_row_candidate(
            query_id=query_id,
            layer_name="L2_FILE_WORKBOOK_IDENTITY",
            source_family=family,
            candidate=candidate,
            index=index,
        )
        for index, candidate in enumerate(candidates, 1)
    )
    l3_candidates = tuple(
        layer_candidate_from_row_candidate(
            query_id=query_id,
            layer_name="L3_STRUCTURAL_LOCATOR",
            source_family=family,
            candidate=candidate,
            index=index,
        )
        for index, candidate in enumerate(candidates, 1)
    )
    selected_ids = (l3_candidates[0].candidate_id,) if l3_candidates else ()
    selected_source_atoms = tuple(candidate.source_atom_id for candidate in l3_candidates[:1] if candidate.source_atom_id)
    hydration_result: Mapping[str, Any] = {}
    if l3_candidates and l3_candidates[0].source_atom_id:
        hydration_result = evidence_bundle_from_search_view(
            {
                "search_view_id": l3_candidates[0].search_view_id,
                "source_atom_id": l3_candidates[0].source_atom_id,
            },
            source_registry=source_registry,
        )
    hydrated = bool(hydration_result.get("valid") and hydration_result.get("source_atom_hydrated_from_registry"))
    evidence_bundle_assembled = bool(hydrated and hydration_result.get("evidence_bundle"))
    hydrated_candidates = (
        (
            replace(
                l3_candidates[0],
                source_atom_hydrated_from_registry=hydrated,
                evidence_bundle_assembled=evidence_bundle_assembled,
                canonical_payload_source="source_registry" if hydrated else "not_hydrated",
            ),
        )
        if l3_candidates
        else ()
    )
    decisions = (
        route_decision(row),
        LayerDecision(
            query_id=query_id,
            source_family=family,
            layer_name="L1_COARSE_CANDIDATE_GENERATION",
            selected_candidate_ids=tuple(candidate.candidate_id for candidate in l1_candidates),
            candidates=l1_candidates,
            signals={"candidate_count": len(candidates), "vector_db_role": "candidate_generator_only"},
        ),
        LayerDecision(
            query_id=query_id,
            source_family=family,
            layer_name="L2_FILE_WORKBOOK_IDENTITY",
            selected_candidate_ids=selected_ids,
            candidates=l2_candidates,
            signals={
                "resolve_status": clean(row.get("resolve_status")),
                "file_resolve@1": bool(row.get("file_resolve@1", False)),
                "file_resolve@3": bool(row.get("file_resolve@3", False)),
                "workbook_gate_resolved": bool(row.get("v3_8_2_gate_resolved", False)),
            },
            abstain_or_disambiguate=clean(row.get("resolve_status")) in {"abstain", "disambiguation"},
        ),
        LayerDecision(
            query_id=query_id,
            source_family=family,
            layer_name="L3_STRUCTURAL_LOCATOR",
            selected_candidate_ids=selected_ids,
            candidates=l3_candidates,
            signals={
                "sheet@1": bool(row.get("sheet_resolve@1", False)),
                "table_or_range@1": bool(row.get("table_or_range_resolve@1", False)),
                "cell_or_value@1": bool(row.get("cell_or_value_resolve@1", False)),
                "pdf_bbox_present": any(candidate.bbox is not None for candidate in l3_candidates),
                "pdf_bbox_correctness_metric_computed": False,
            },
            failure_bucket=clean((row.get("xlsx_miss_taxonomy") or {}).get("primary_category"))
            or clean(row.get("abstain_vs_wrong_file_taxonomy")),
        ),
        LayerDecision(
            query_id=query_id,
            source_family=family,
            layer_name="L4_SOURCEATOM_HYDRATION",
            selected_candidate_ids=selected_ids,
            candidates=hydrated_candidates,
            signals={
                "selected_source_atom_ids": selected_source_atoms,
                "hydration_valid": bool(hydration_result.get("valid")),
                "hydration_failure_bucket": clean(hydration_result.get("failure_bucket")),
            },
            source_atom_hydrated_from_registry=hydrated,
            vector_payload_used_as_evidence_truth=False,
        ),
        LayerDecision(
            query_id=query_id,
            source_family=family,
            layer_name="L5_EVIDENCE_BUNDLE_ASSEMBLY",
            selected_candidate_ids=selected_ids,
            candidates=hydrated_candidates,
            evidence_bundle_assembled=evidence_bundle_assembled,
            vector_payload_used_as_evidence_truth=False,
        ),
        LayerDecision(
            query_id=query_id,
            source_family=family,
            layer_name="L6_EVIDENCE_SELECTOR",
            selected_candidate_ids=selected_ids,
            candidates=hydrated_candidates,
            signals={"selected_evidence_count": 1 if selected_ids else 0},
            vector_payload_used_as_evidence_truth=False,
        ),
        LayerDecision(
            query_id=query_id,
            source_family=family,
            layer_name="L7_ANSWER_READY_CONTEXT",
            selected_candidate_ids=selected_ids,
            signals={"answer_generation_executed": False, "context_builder_diagnostic_only": True},
            vector_payload_used_as_evidence_truth=False,
        ),
        LayerDecision(
            query_id=query_id,
            source_family=family,
            layer_name="L9_METRICS_FAILURE_TAXONOMY",
            signals={"official_metric_input_rows": 0, "product_success_evidence_allowed": False},
            vector_payload_used_as_evidence_truth=False,
        ),
    )
    trace = LayeredRetrievalTrace(
        query_id=query_id,
        query_text_sha256=clean(row.get("query_text_sha256")) or sha256_text(query_id),
        source_family=family,
        decisions=decisions,
    )
    return serialize_layered_trace(trace)


def per_query_from_trace(trace: Mapping[str, Any]) -> dict[str, Any]:
    decisions = trace["decisions"]
    failure = next((decision.get("failure_bucket", "") for decision in decisions if decision["layer_name"] == "L3_STRUCTURAL_LOCATOR"), "")
    return {
        "schema_version": f"{RUN_ID}_per_query_v1",
        "run_id": RUN_ID,
        "query_id": trace["query_id"],
        "source_family": trace["source_family"],
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "used_gold_or_expected_text": False,
        "used_answer_value_shortcut": False,
        "direct_normalized_value_query_matching_used": False,
        "vector_payload_used_as_evidence_truth": False,
        "layers_recorded": [decision["layer_name"] for decision in decisions],
        "selected_evidence_count": next(
            (
                decision.get("signals", {}).get("selected_evidence_count", 0)
                for decision in decisions
                if decision["layer_name"] == "L6_EVIDENCE_SELECTOR"
            ),
            0,
        ),
        "failure_bucket": failure,
    }


def selected_evidence_from_trace(trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for decision in trace["decisions"]:
        if decision["layer_name"] != "L6_EVIDENCE_SELECTOR":
            continue
        for candidate in decision.get("candidates", []):
            rows.append(
                {
                    "schema_version": f"{RUN_ID}_selected_evidence_v1",
                    "run_id": RUN_ID,
                    "query_id": trace["query_id"],
                    "source_family": trace["source_family"],
                    "source_atom_id": clean(candidate.get("source_atom_id")),
                    "search_view_id": clean(candidate.get("search_view_id")),
                    "source_identity": clean(candidate.get("source_identity")),
                    "document_version_id": clean(candidate.get("document_version_id")),
                    "workbook_id": clean(candidate.get("workbook_id")),
                    "sheet_name": clean(candidate.get("sheet_name")),
                    "table_range": clean(candidate.get("table_range")),
                    "cell": clean(candidate.get("cell")),
                    "page": candidate.get("page"),
                    "bbox_present": bool(candidate.get("bbox")),
                    "canonical_payload_source": clean(candidate.get("canonical_payload_source")),
                    "source_atom_hydrated_from_registry": bool(candidate.get("source_atom_hydrated_from_registry")),
                    "evidence_bundle_assembled": bool(candidate.get("evidence_bundle_assembled")),
                    "vector_payload_used_as_evidence_truth": False,
                    "diagnostic_only": True,
                    "official_metric_input_rows": 0,
                }
            )
    return rows


def build_bootstrap(input_paths: Mapping[str, Path]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_bootstrap_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "layer_contract": list(LAYER_NAMES),
        "layers_skipped_by_design": list(SKIPPED_LAYERS),
        "source_of_truth_inputs": {key: repo_relative(path) for key, path in input_paths.items()},
        "protected_namespaces": list(PROTECTED_NAMESPACES),
        "protected_namespaces_touched": [],
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "direct_normalized_value_query_matching_used": False,
    }


def build_metrics(
    *,
    v310_metrics: Mapping[str, Any],
    xlsx_rows: Sequence[Mapping[str, Any]],
    pdf_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    xlsx_seen = v310_metrics["xlsx_table_axis_eval"]["nonprod_seen_materialization_smoke"]
    pdf_seen = v310_metrics["pdf_file_identity_baseline"]["seen_reference_v3_9_1"]
    pdf_candidate_count = sum(len(top_candidates(row)) for row in pdf_rows)
    pdf_bbox_present = sum(
        1
        for row in pdf_rows
        for candidate in top_candidates(row)
        if parse_pdf_locator(clean(candidate.get("source_identity") or candidate.get("candidate_source_identity")))[1]
        is not None
    )
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "answer_generation_executed": False,
        "pdf_xlsx_collapsed_headline_score_reported": False,
        "per_source_family": {
            "XLSX": {
                "metric_scope": "seen_validation_only_materialized_table_axis_no_success_claim",
                "metrics": {
                    "query_count": len(xlsx_rows),
                    "sheet@1": xlsx_seen["sheet@1"],
                    "sheet@3": xlsx_seen["sheet@3"],
                    "table_or_range@1": xlsx_seen["table_or_range@1"],
                    "table_or_range@3": xlsx_seen["table_or_range@3"],
                    "cell_or_value@1": xlsx_seen["cell_or_value@1"],
                    "cell_or_value@3": xlsx_seen["cell_or_value@3"],
                    "signal_empty_rank1_rate": xlsx_seen["signal_empty_rank1_rate"],
                    "table_or_range_miss_after_sheet_hit": xlsx_seen["table_or_range_miss_after_sheet_hit"],
                },
            },
            "PDF_FILE_IDENTITY": {
                "metric_scope": "seen_validation_only_file_identity_no_answer_ready_window_claim",
                "metrics": {
                    "query_count": len(pdf_rows),
                    "file_resolve@1": pdf_seen["file_resolve@1"],
                    "file_resolve@3": pdf_seen["file_resolve@3"],
                    "abstain_rate": pdf_seen["abstain_rate"],
                    "wrong_file_block_rate": pdf_seen["wrong_file_block_rate"],
                },
            },
            "PDF_EVIDENCE_WINDOW": {
                "metric_scope": "diagnostic_decomposition_only_bbox_availability_not_correctness",
                "metrics": {
                    "query_count": len(pdf_rows),
                    "candidate_count": pdf_candidate_count,
                    "bbox_present@3": ratio(pdf_bbox_present, pdf_candidate_count),
                    "page_candidate_metric_available": True,
                    "bbox_correctness_metric_computed": False,
                    "answer_ready_window_sufficiency_metric_computed": False,
                    "ocr_touched": False,
                },
            },
        },
    }


def build_failure_taxonomy(v391_metrics: Mapping[str, Any]) -> dict[str, Any]:
    failure = v391_metrics.get("failure_taxonomy", {})
    return {
        "schema_version": f"{RUN_ID}_failure_taxonomy_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "layer_failure_buckets": {
            "L0_QUERY_ROUTING": ["source_family_ambiguous", "query_fidelity_excluded"],
            "L1_COARSE_CANDIDATE_GENERATION": ["candidate_pool_empty", "source_family_candidate_miss"],
            "L2_FILE_WORKBOOK_IDENTITY": ["pdf_file_identity_miss", "workbook_gate_disambiguation"],
            "L3_STRUCTURAL_LOCATOR": [
                "sheet_miss_after_workbook_gate",
                "table_or_range_miss_after_sheet_hit",
                "cell_or_value_miss_after_range_hit",
                "pdf_page_or_bbox_window_missing",
            ],
            "L4_SOURCEATOM_HYDRATION": ["source_atom_not_hydrated"],
            "L5_EVIDENCE_BUNDLE_ASSEMBLY": ["evidence_bundle_incomplete"],
            "L6_EVIDENCE_SELECTOR": ["selector_prefers_wrong_evidence"],
            "L7_ANSWER_READY_CONTEXT": ["answer_ready_window_not_computed"],
        },
        "xlsx_seen_reference": failure.get("xlsx", {}),
        "pdf_file_identity_seen_reference": failure.get("pdf_file_identity", {}),
        "pdf_answer_ready_evidence_window": {
            "computed_in_this_run": False,
            "bbox_correctness_metric_computed": False,
            "ocr_touched": False,
        },
    }


def build_guardrail_audit() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "protected_namespaces_touched": [],
        "blocked_namespaces": list(PROTECTED_NAMESPACES),
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "staging_or_commit_performed": False,
        "answer_generation_executed": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "direct_normalized_value_query_matching_used": False,
        "answer_value_in_query_success_evidence_used": False,
        "index_to_content_success_evidence_used": False,
        "file_or_source_title_leak_success_evidence_used": False,
        "vector_payload_used_as_evidence_truth": False,
        "source_atom_registry_mutated": False,
        "official_denominator_mutated": False,
        "db_or_production_namespace_written": False,
    }


def build_query_guardrail_summary(routing_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    flags = Counter(flag for row in routing_rows for flag in row.get("guardrail_flags", []))
    return {
        "schema_version": f"{RUN_ID}_query_guardrail_summary_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "headline_excluded_rows": sum(1 for row in routing_rows if not row["headline_eligible"]),
        "guardrail_flag_counts": dict(sorted(flags.items())),
        "shortcut_success_evidence_allowed": False,
        "excluded_buckets_retained_for_audit": [
            "answer_value_in_query",
            "index_to_content",
            "source_title_leak",
            "file_title_leak",
            "exact_query_hack",
            "major_topic_drift",
            "unnatural_sheet_or_cell_reference",
        ],
    }


def build_per_family(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_per_family_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "families_reported_separately": ["PDF_EVIDENCE_WINDOW", "PDF_FILE_IDENTITY", "XLSX"],
        "per_source_family": metrics["per_source_family"],
    }


def build_holdout_manifest(v310_holdout: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_holdout_manifest_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "fresh_real_holdout_sufficient": False,
        "product_success_evidence_allowed": False,
        "real_unseen_registry_counts": v310_holdout["real_unseen_registry_counts"],
        "real_query_fidelity_included_counts": v310_holdout["real_query_fidelity_included_counts"],
        "minimum_targets": v310_holdout["minimum_targets"],
        "synthetic_ood_guard": {
            "candidate_count": v310_holdout["synthetic_ood_guard"]["candidate_count"],
            "product_success_evidence_allowed": False,
        },
    }


def build_summary(
    artifacts: Mapping[str, Any],
    artifact_sha256: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_summary_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "event_type": EVENT_TYPE,
        "run_class": "diagnostic_only_layered_retrieval",
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "fine_tuning_executed": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "staging_or_commit_performed": False,
        "fresh_real_holdout_sufficient": False,
        "product_success_evidence_allowed": False,
        "answer_generation_executed": False,
        "direct_normalized_value_query_matching_used": False,
        "answer_value_in_query_success_evidence_used": False,
        "index_to_content_success_evidence_used": False,
        "file_or_source_title_leak_success_evidence_used": False,
        "layer_contract": list(LAYER_NAMES),
        "layers_skipped_by_design": list(SKIPPED_LAYERS),
        "source_atom_registry_canonical_truth": True,
        "vector_payload_used_as_evidence_truth": False,
        "pdf_file_identity_answer_window_kept_separate": True,
        "pdf_answer_ready_evidence_window_metric_computed": False,
        "pdf_bbox_correctness_metric_computed": False,
        "ocr_touched": False,
        "xlsx_seen_validation_only": True,
        "protected_namespaces_touched": [],
        "artifact_paths": {key: repo_relative(path) for key, path in OUTPUTS.items()},
        "artifact_sha256": dict(artifact_sha256),
    }


@lru_cache(maxsize=1)
def build_artifacts() -> dict[str, Any]:
    input_paths = {
        "v3_9_1_metrics_json": v392.V3_9_1_METRICS,
        "v3_9_1_per_query_jsonl": v392.V3_9_1_PER_QUERY,
        "v3_10_metrics_json": v310.OUTPUTS["metrics_json"],
        "v3_10_holdout_manifest_json": v310.OUTPUTS["fresh_real_holdout_manifest_json"],
        "v3_10_xlsx_eval_per_query_jsonl": v310.OUTPUTS["xlsx_table_axis_eval_per_query_jsonl"],
        "source_registry_jsonl": v392.SOURCE_REGISTRY_JSONL,
    }
    missing = [repo_relative(path) for path in input_paths.values() if not artifact_exists(path)]
    if missing:
        raise FileNotFoundError("missing required v3_11 input artifacts: " + ", ".join(missing))

    v391_metrics = read_json(v392.V3_9_1_METRICS)
    v391_rows = read_jsonl(v392.V3_9_1_PER_QUERY)
    v310_metrics = read_json(v310.OUTPUTS["metrics_json"])
    v310_holdout = read_json(v310.OUTPUTS["fresh_real_holdout_manifest_json"])
    source_registry = load_source_registry()

    xlsx_rows = [row for row in v391_rows if clean(row.get("source_family")).upper() == "XLSX"]
    pdf_rows = [row for row in v391_rows if clean(row.get("source_family")).upper() == "PDF"]
    traces = [build_trace(row, source_registry=source_registry) for row in (*xlsx_rows, *pdf_rows)]
    per_query_rows = [per_query_from_trace(trace) for trace in traces]
    routing_rows = [
        {
            "schema_version": f"{RUN_ID}_query_routing_audit_v1",
            "run_id": RUN_ID,
            "query_id": trace["query_id"],
            "source_family": trace["source_family"],
            "query_text_sha256": trace["query_text_sha256"],
            "layer_name": "L0_QUERY_ROUTING",
            "intent_type": trace["decisions"][0]["signals"]["intent_type"],
            "guardrail_flags": trace["decisions"][0]["guardrail_flags"],
            "headline_eligible": trace["decisions"][0]["headline_eligible"],
            "used_gold_or_expected_text": False,
            "used_answer_value_shortcut": False,
            "direct_normalized_value_query_matching_used": False,
            "diagnostic_only": True,
            "official_metric_input_rows": 0,
        }
        for trace in traces
    ]
    selected_evidence_rows = [row for trace in traces for row in selected_evidence_from_trace(trace)]
    metrics = build_metrics(v310_metrics=v310_metrics, xlsx_rows=xlsx_rows, pdf_rows=pdf_rows)
    per_family = build_per_family(metrics)
    query_guardrail_summary = build_query_guardrail_summary(routing_rows)
    failure_taxonomy = build_failure_taxonomy(v391_metrics)
    guardrail_audit = build_guardrail_audit()
    holdout_manifest = build_holdout_manifest(v310_holdout)
    bootstrap = build_bootstrap(input_paths)
    artifacts = {
        "bootstrap": bootstrap,
        "metrics": metrics,
        "per_family": per_family,
        "per_query_rows": per_query_rows,
        "layer_trace_sample_rows": traces[:20] + traces[len(xlsx_rows) : len(xlsx_rows) + 20],
        "query_routing_rows": routing_rows,
        "query_guardrail_summary": query_guardrail_summary,
        "selected_evidence_rows": selected_evidence_rows,
        "failure_taxonomy": failure_taxonomy,
        "guardrail_audit": guardrail_audit,
        "holdout_manifest": holdout_manifest,
    }
    artifacts["summary"] = build_summary(artifacts, {})
    return artifacts


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"Last updated: [^.]+\.", "Last updated: 2026-05-25 KST.", text, count=1)
    start = f"<!-- {marker}:start -->"
    end = f"<!-- {marker}:end -->"
    marked = f"{start}\n{entry.rstrip()}\n{end}\n"
    text = re.sub(rf"\n?{re.escape(start)}.*?{re.escape(end)}\n?", "\n", text, flags=re.DOTALL)
    insertion_candidates = [index for index in (text.find("\n<!-- "), text.find("\n## ")) if index != -1]
    insert_at = min(insertion_candidates) if insertion_candidates else -1
    if insert_at == -1:
        text = text.rstrip() + "\n\n" + marked
    else:
        text = text[:insert_at].rstrip() + "\n\n" + marked + "\n" + text[insert_at:].lstrip("\n")
    path.write_text(text, encoding="utf-8")


def update_docs(summary: Mapping[str, Any], metrics: Mapping[str, Any]) -> None:
    xlsx = metrics["per_source_family"]["XLSX"]["metrics"]
    pdf = metrics["per_source_family"]["PDF_FILE_IDENTITY"]["metrics"]
    bbox = metrics["per_source_family"]["PDF_EVIDENCE_WINDOW"]["metrics"]["bbox_present@3"]
    progress_entry = (
        f"- v3_11 layered retrieval diagnostic (`{RUN_ID}`) adds a sidecar trace contract for "
        "L0 query routing through L7 answer-ready context plus L9 metrics/failure taxonomy. It keeps "
        "XLSX workbook/sheet/table/range/cell resolution separate from PDF file/page/block/bbox-window "
        "diagnostics, hydrates selected evidence through SourceAtom ids, and leaves L8 generation closed. "
        "official_metric_input_rows=0; no gold/qrels/labels/expected/supporting/denominator/prod mutation; "
        "fresh real holdout remains insufficient, so product success claims stay blocked."
    )
    measurements_entry = f"""## 2026-05-25 - v3_11 Layered Retrieval Diagnostic

- Run: `{RUN_ID}`
- Policy: diagnostic-only; official_metric_input_rows=0; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no answer generation, fine-tuning, threshold tuning, or winner selection.
- Layer contract: L0 query routing, L1 coarse candidates, L2 file/workbook identity, L3 structural locator, L4 SourceAtom hydration, L5 EvidenceBundle assembly, L6 evidence selector, L7 answer-ready context, L9 metrics/failure taxonomy. L8 generation/deterministic execution is skipped by design.
- Holdout: still insufficient. Existing seen validation is retained only for no-regression and layer attribution.

| Family/lane | Diagnostic metric | Value |
| --- | --- | ---: |
| XLSX | sheet@1 | {xlsx['sheet@1']['numerator']}/{xlsx['sheet@1']['denominator']} |
| XLSX | table_or_range@3 | {xlsx['table_or_range@3']['numerator']}/{xlsx['table_or_range@3']['denominator']} |
| XLSX | cell_or_value@3 | {xlsx['cell_or_value@3']['numerator']}/{xlsx['cell_or_value@3']['denominator']} |
| XLSX | signal-empty rank1 | {xlsx['signal_empty_rank1_rate']['numerator']}/{xlsx['signal_empty_rank1_rate']['denominator']} |
| PDF file identity | file_resolve@1 | {pdf['file_resolve@1']['numerator']}/{pdf['file_resolve@1']['denominator']} |
| PDF file identity | file_resolve@3 | {pdf['file_resolve@3']['numerator']}/{pdf['file_resolve@3']['denominator']} |
| PDF evidence window | bbox_present@3 | {bbox['numerator']}/{bbox['denominator']} |

PDF bbox correctness and answer-ready window sufficiency are explicitly not computed in this run; the lane records availability/decomposition only.
"""
    triage_entry = f"""## v3_11 Layered Retrieval Diagnostic Triage

- XLSX remains blocked mainly at table/range and cell locator layers after workbook/sheet routing: table_or_range@3={xlsx['table_or_range@3']['numerator']}/{xlsx['table_or_range@3']['denominator']}, cell_or_value@3={xlsx['cell_or_value@3']['numerator']}/{xlsx['cell_or_value@3']['denominator']}.
- PDF remains a file-identity-first bottleneck: file_resolve@1={pdf['file_resolve@1']['numerator']}/{pdf['file_resolve@1']['denominator']}, file_resolve@3={pdf['file_resolve@3']['numerator']}/{pdf['file_resolve@3']['denominator']}. Page/block/bbox evidence-window rows are diagnostic decomposition only.
- SourceAtom hydration and EvidenceBundle assembly are recorded as separate layers so vector metadata remains candidate-only, not evidence truth.
- Fresh real holdout insufficiency is unchanged; no product performance or promotion claim is made.
"""
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        "Overall status: `diagnostic_v3_11_layered_retrieval_ready`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)


def append_status_event(summary: Mapping[str, Any]) -> None:
    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "generated_at": utc_now(),
        "run_class": summary["run_class"],
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "fresh_real_holdout_sufficient": False,
        "product_success_evidence_allowed": False,
        "answer_generation_executed": False,
        "layer_contract": list(LAYER_NAMES),
        "layers_skipped_by_design": list(SKIPPED_LAYERS),
        "pdf_file_identity_answer_window_kept_separate": True,
        "pdf_bbox_correctness_metric_computed": False,
        "ocr_touched": False,
        "direct_normalized_value_query_matching_used": False,
        "protected_namespaces_touched": [],
        "artifact_paths": summary["artifact_paths"],
        "artifact_sha256": {**summary["artifact_sha256"], "summary_json_sha256": sha256_file(OUTPUTS["summary_json"])},
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def write_artifacts(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    write_json(OUTPUTS["bootstrap_json"], artifacts["bootstrap"])
    write_json(OUTPUTS["metrics_json"], artifacts["metrics"])
    write_json(OUTPUTS["per_family_json"], artifacts["per_family"])
    write_jsonl(OUTPUTS["per_query_jsonl"], artifacts["per_query_rows"])
    write_jsonl(OUTPUTS["layer_trace_sample_jsonl"], artifacts["layer_trace_sample_rows"])
    write_jsonl(OUTPUTS["query_routing_audit_jsonl"], artifacts["query_routing_rows"])
    write_json(OUTPUTS["query_guardrail_summary_json"], artifacts["query_guardrail_summary"])
    write_jsonl(OUTPUTS["selected_evidence_jsonl"], artifacts["selected_evidence_rows"])
    write_json(OUTPUTS["failure_taxonomy_json"], artifacts["failure_taxonomy"])
    write_json(OUTPUTS["guardrail_audit_json"], artifacts["guardrail_audit"])
    write_json(OUTPUTS["holdout_manifest_json"], artifacts["holdout_manifest"])
    artifact_sha = {
        key.replace("_jsonl", "").replace("_json", "") + "_sha256": sha256_file(path)
        for key, path in OUTPUTS.items()
        if key != "summary_json"
    }
    summary = build_summary(artifacts, artifact_sha)
    write_json(OUTPUTS["summary_json"], summary)
    append_status_event(summary)
    update_docs(summary, artifacts["metrics"])
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build v3_11 diagnostic-only layered retrieval artifacts.")
    parser.add_argument("--check", action="store_true", help="Build in memory only.")
    args = parser.parse_args(argv)
    artifacts = build_artifacts()
    if args.check:
        print(json.dumps({"run_id": RUN_ID, "status": artifacts["summary"]["status"]}, ensure_ascii=False))
        return 0
    summary = write_artifacts(artifacts)
    print(json.dumps({"run_id": RUN_ID, "status": summary["status"], "summary": repo_relative(OUTPUTS["summary_json"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
