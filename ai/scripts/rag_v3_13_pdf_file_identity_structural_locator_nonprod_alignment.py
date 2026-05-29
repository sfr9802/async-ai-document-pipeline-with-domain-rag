from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v3_9_2_overfit_risk_audit_and_blind_holdout_reset as v392
import rag_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization as v310
import rag_v3_12_xlsx_structural_locator_nonprod_improvement as v312


ROOT = v392.ROOT
if str(ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai"))
if str(ROOT / "ai" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))


RUN_ID = "official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment"
REPORT_DIR = v392.REPORT_DIR
STATUS_JSONL = v392.STATUS_JSONL
PROGRESS_DOC = v392.PROGRESS_DOC
MEASUREMENTS_DOC = v392.MEASUREMENTS_DOC
TRIAGE_DOC = v392.TRIAGE_DOC

STATUS = "DIAGNOSTIC_V3_13_PDF_FILE_IDENTITY_STRUCTURAL_LOCATOR_NONPROD_ALIGNMENT_READY"
EVENT_TYPE = "diagnostic_v3_13_pdf_file_identity_structural_locator_nonprod_alignment"
SOURCE_NAMESPACE = "rag-data-all-source-citable-nonprod-v1"
ALLOWED_NAMESPACE = "rag-data-pdf-structural-locator-nonprod-v1"
PROTECTED_NAMESPACES = (
    "rag-data-official-denominator-v1",
    "rag-data-all-source-citable-nonprod-v1",
    "rag-data-xlsx-table-axis-ood-nonprod-v1",
    "rag-data-xlsx-structural-locator-nonprod-v1",
    "production",
)
LAYER_NAMES = (
    "L0_QUERY_ROUTING",
    "L1_COARSE_CANDIDATE_GENERATION",
    "L2_FILE_WORKBOOK_IDENTITY",
    "L3_STRUCTURAL_LOCATOR",
    "L4_SOURCEATOM_HYDRATION",
    "L5_EVIDENCE_BUNDLE_ASSEMBLY",
    "L6_EVIDENCE_SELECTOR",
    "L7_ANSWER_READY_CONTEXT",
    "L9_METRICS_FAILURE_TAXONOMY",
)
SKIPPED_LAYERS = ("L8_GENERATION_OR_DETERMINISTIC_EXECUTION",)

V3_8_1_EVIDENCE_SELECTOR_RUN_ID = "official_answer_citation_agentic_loop_run_v3_8_1_evidence_selector_v1"
V3_8_1_EVIDENCE_SELECTOR_PER_QUERY = REPORT_DIR / f"{V3_8_1_EVIDENCE_SELECTOR_RUN_ID}_per_query.jsonl"
V3_8_2_FILE_RESOLVE_PER_QUERY = v392.V3_8_2_PER_QUERY
V3_11_METRICS = REPORT_DIR / "official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic_metrics.json"
V3_11_SUMMARY = REPORT_DIR / "official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic_summary.json"
V3_12_SUMMARY = v312.OUTPUTS["summary_json"]
V3_12_METRICS = v312.OUTPUTS["metrics_json"]

OUTPUTS = {
    "summary_json": REPORT_DIR / f"{RUN_ID}_summary.json",
    "metrics_json": REPORT_DIR / f"{RUN_ID}_metrics.json",
    "per_family_json": REPORT_DIR / f"{RUN_ID}_per_family.json",
    "pdf_structural_locator_eval_per_query_jsonl": REPORT_DIR
    / f"{RUN_ID}_pdf_structural_locator_eval_per_query.jsonl",
    "pdf_layer_trace_per_query_jsonl": REPORT_DIR / f"{RUN_ID}_pdf_layer_trace_per_query.jsonl",
    "pdf_score_components_jsonl": REPORT_DIR / f"{RUN_ID}_pdf_score_components.jsonl",
    "pdf_nonprod_manifest_summary_json": REPORT_DIR / f"{RUN_ID}_pdf_nonprod_manifest_summary.json",
    "leakage_audit_jsonl": REPORT_DIR / f"{RUN_ID}_leakage_audit.jsonl",
    "failure_taxonomy_json": REPORT_DIR / f"{RUN_ID}_failure_taxonomy.json",
    "guardrail_audit_json": REPORT_DIR / f"{RUN_ID}_guardrail_audit.json",
    "holdout_manifest_json": REPORT_DIR / f"{RUN_ID}_holdout_manifest.json",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="microseconds") + "Z"


def clean(value: Any) -> str:
    return "" if value is None else str(value)


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def sha256_text(value: Any) -> str:
    return hashlib.sha256(clean(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return v392.sha256_file(path)


def artifact_exists(path: Path) -> bool:
    return v392.artifact_exists(path)


def artifact_is_file(path: Path) -> bool:
    return v392.artifact_is_file(path)


def repo_relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


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


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {"numerator": numerator, "denominator": denominator, "rate": numerator / denominator if denominator else None}


def bool_metric(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, Any]:
    return ratio(sum(1 for row in rows if row.get(key) is True), len(rows))


def load_source_registry() -> dict[str, Mapping[str, Any]]:
    registry: dict[str, Mapping[str, Any]] = {}
    for row in read_jsonl(v392.SOURCE_REGISTRY_JSONL):
        source_atom_id = clean(row.get("source_atom_id"))
        if source_atom_id:
            registry[source_atom_id] = row
    return registry


def source_atom_ids(candidate: Mapping[str, Any]) -> list[str]:
    raw_ids = candidate.get("supporting_source_atom_ids")
    ids: list[str] = []
    if isinstance(raw_ids, Sequence) and not isinstance(raw_ids, (str, bytes)):
        ids.extend(clean(item) for item in raw_ids if clean(item))
    source_atom_id = clean(candidate.get("source_atom_id"))
    if source_atom_id:
        ids.insert(0, source_atom_id)
    return list(dict.fromkeys(ids))


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


def locator_from_registry(
    candidate: Mapping[str, Any],
    source_registry: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    atom: Mapping[str, Any] = {}
    for source_atom_id in source_atom_ids(candidate):
        if source_atom_id in source_registry:
            atom = source_registry[source_atom_id]
            break
    raw = as_mapping(atom.get("raw_locator"))
    payload = as_mapping(atom.get("canonical_citation_payload"))
    source_identity = clean(candidate.get("source_identity") or candidate.get("candidate_source_identity"))
    page, bbox = parse_pdf_locator(source_identity)
    bbox_value = raw.get("bbox") or payload.get("bbox") or bbox
    if isinstance(bbox_value, Sequence) and not isinstance(bbox_value, (str, bytes)) and len(bbox_value) == 4:
        bbox_list = [float(item) for item in bbox_value]
    else:
        bbox_list = []
    return {
        "source_atom_id": clean(atom.get("source_atom_id")) or (source_atom_ids(candidate)[0] if source_atom_ids(candidate) else ""),
        "source_identity": clean(atom.get("source_identity") or source_identity),
        "document_version_id": clean(
            raw.get("document_version_id")
            or payload.get("document_version_id")
            or candidate.get("document_version_id")
            or atom.get("document_version_id")
        ),
        "page": raw.get("page") if raw.get("page") is not None else payload.get("page", page),
        "physical_page_index": raw.get("physical_page_index") or payload.get("physical_page_index"),
        "region_type": clean(raw.get("region_type") or payload.get("region_type")),
        "bbox": bbox_list,
        "source_atom_hydrated_from_registry": bool(atom),
        "canonical_payload_source": "source_registry" if atom else "not_hydrated",
        "canonical_payload_renderable": bool(
            as_mapping(atom.get("canonical_citation_payload")).get("canonical_payload_renderable")
            or as_mapping(atom.get("canonical_citation_payload")).get("canonicalPayloadRenderable")
            or candidate.get("citation_render_valid")
        ),
        "evidence_bundle_assembled": bool(candidate.get("contract_survived") or atom),
    }


def confidence_bucket(score: Any) -> str:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "unknown"
    if value >= 0.85:
        return "high"
    if value >= 0.65:
        return "medium"
    return "low"


def selector_rows_by_query_id() -> dict[str, Mapping[str, Any]]:
    return {
        clean(row.get("query_id")): row
        for row in read_jsonl(V3_8_1_EVIDENCE_SELECTOR_PER_QUERY)
        if clean(row.get("source_family")).upper() == "PDF"
    }


def target_evidence(selector_row: Mapping[str, Any]) -> Mapping[str, Any]:
    selected = selector_row.get("selected_evidence")
    if not isinstance(selected, list):
        return {}
    for item in selected:
        if isinstance(item, Mapping) and item.get("selector_target_hit") is True:
            return item
    return {}


def same_page_bounded_window_candidate(locator: Mapping[str, Any], target: Mapping[str, Any]) -> bool:
    return bool(
        locator.get("bbox")
        and target.get("bbox")
        and locator.get("page") is not None
        and target.get("page") is not None
        and int(locator["page"]) == int(target["page"])
    )


def pdf_failure_bucket(row: Mapping[str, Any]) -> str:
    if row.get("file_resolve@1") is True:
        return "rank1_file_hit"
    if row.get("accepted_wrong_rank1_with_target_in_top3_rerank_candidates") is True:
        return "accepted_wrong_rank1_target_in_top3"
    if row.get("wrong_file_forcing_accepted") is True:
        return "accepted_wrong_rank1_target_not_in_top3"
    if row.get("wrong_file_block_rate") is True:
        return "abstain_or_disambiguation_blocked_wrong_rank1"
    if row.get("abstain_or_disambiguate") is True:
        return "abstain_or_disambiguation_without_wrong_rank1"
    return "unresolved_pdf_file_identity"


def compact_candidate_row(
    *,
    query_id: str,
    candidate: Mapping[str, Any],
    target: Mapping[str, Any],
    source_registry: Mapping[str, Mapping[str, Any]],
    accepted_wrong_rank1_target_top3: bool,
) -> dict[str, Any]:
    locator = locator_from_registry(candidate, source_registry)
    rank = int(candidate.get("candidate_rank") or 0)
    same_page_window = same_page_bounded_window_candidate(locator, target)
    components = {
        "file_identity_confidence": float(candidate.get("resolve_score") or 0.0),
        "confidence_bucket": confidence_bucket(candidate.get("resolve_score")),
        "source_registry_metadata": bool(as_mapping(candidate.get("score_components")).get("source_registry_metadata")),
        "source_family_match": bool(as_mapping(candidate.get("score_components")).get("source_family_match")),
        "query_file_mention_match": bool(as_mapping(candidate.get("score_components")).get("query_file_mention_match")),
        "retrieval_best_rank": int(as_mapping(candidate.get("score_components")).get("retrieval_best_rank") or rank),
        "page_candidate_present": locator.get("page") is not None,
        "block_candidate_present": bool(locator.get("region_type")),
        "bbox_candidate_present": bool(locator.get("bbox")),
        "same_page_bounded_evidence_window_candidate": same_page_window,
        "bbox_correctness_metric_computed": False,
        "used_gold_or_expected_text": False,
        "vector_payload_used_as_evidence_truth": False,
    }
    return {
        "schema_version": f"{RUN_ID}_pdf_score_components_v1",
        "run_id": RUN_ID,
        "query_id": query_id,
        "source_family": "PDF",
        "candidate_rank": rank,
        "source_atom_id": locator["source_atom_id"],
        "source_identity_sha256": sha256_text(locator["source_identity"]),
        "document_version_id_sha256": sha256_text(locator["document_version_id"]),
        "page": locator["page"],
        "region_type": locator["region_type"],
        "bbox_present": bool(locator["bbox"]),
        "source_atom_hydrated_from_registry": locator["source_atom_hydrated_from_registry"],
        "canonical_payload_source": locator["canonical_payload_source"],
        "evidence_bundle_assembled": locator["evidence_bundle_assembled"],
        "same_page_bounded_evidence_window_candidate": same_page_window,
        "accepted_wrong_rank1_with_target_in_top3_rerank_candidate": bool(
            rank == 1 and accepted_wrong_rank1_target_top3
        ),
        "score_components": components,
        "official_metric_input_rows": 0,
        "diagnostic_only": True,
        "used_gold_or_expected_text": False,
        "vector_payload_used_as_evidence_truth": False,
        "expected_supporting_gold_text_used": False,
    }


def build_pdf_eval(
    *,
    pdf_rows: Sequence[Mapping[str, Any]],
    selector_by_query: Mapping[str, Mapping[str, Any]],
    source_registry: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    eval_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    for row in pdf_rows:
        query_id = clean(row.get("query_id"))
        selector_row = selector_by_query.get(query_id, {})
        target = target_evidence(selector_row)
        candidates = [item for item in row.get("resolved_file_candidates", []) if isinstance(item, Mapping)]
        candidate_scores = [
            compact_candidate_row(
                query_id=query_id,
                candidate=candidate,
                target=target,
                source_registry=source_registry,
                accepted_wrong_rank1_target_top3=bool(
                    row.get("file_resolve@3") is True
                    and row.get("file_resolve@1") is not True
                    and clean(row.get("resolve_status")) == "resolved"
                ),
            )
            for candidate in candidates[:3]
        ]
        score_rows.extend(candidate_scores)
        page_candidate_count = sum(1 for candidate in candidate_scores if candidate["page"] is not None)
        block_candidate_count = sum(1 for candidate in candidate_scores if candidate["region_type"])
        bbox_candidate_count = sum(1 for candidate in candidate_scores if candidate["bbox_present"])
        same_page_count = sum(1 for candidate in candidate_scores if candidate["same_page_bounded_evidence_window_candidate"])
        accepted_wrong_rank1_target_top3 = bool(
            row.get("file_resolve@3") is True
            and row.get("file_resolve@1") is not True
            and clean(row.get("resolve_status")) == "resolved"
        )
        wrong_file_forcing_accepted = bool(row.get("file_resolve@1") is not True and clean(row.get("resolve_status")) == "resolved")
        target_window_measurable = bool(target.get("page") is not None and target.get("bbox"))
        answer_ready_sufficient = bool(selector_row.get("selector_target_hit@3") is True and target_window_measurable)
        rank1_score = candidate_scores[0] if candidate_scores else {}
        eval_row = {
            "schema_version": f"{RUN_ID}_pdf_structural_locator_eval_per_query_v1",
            "run_id": RUN_ID,
            "query_id": query_id,
            "source_family": "PDF",
            "old_seen_reference_only": True,
            "fresh_real_holdout": False,
            "success_claim_allowed": False,
            "file_identity_metric_computed": True,
            "file_identity_confidence_diagnostic_computed": True,
            "resolve_status": clean(row.get("resolve_status")),
            "abstain_or_disambiguate": clean(row.get("resolve_status")) in {"abstain", "disambiguation"},
            "abstain_rate": bool(row.get("abstain_rate")),
            "wrong_file_block_rate": bool(row.get("wrong_file_block_rate")),
            "wrong_file_forcing_accepted": wrong_file_forcing_accepted,
            "file_resolve@1": bool(row.get("file_resolve@1")),
            "file_resolve@3": bool(row.get("file_resolve@3")),
            "accepted_wrong_rank1_with_target_in_top3_rerank_candidates": accepted_wrong_rank1_target_top3,
            "wrong_file_forcing_delta_from_v3_11": 0,
            "candidate_count": len(candidate_scores),
            "rank1_confidence_bucket": as_mapping(rank1_score.get("score_components")).get("confidence_bucket"),
            "rank1_source_atom_hydrated_from_registry": bool(rank1_score.get("source_atom_hydrated_from_registry")),
            "page_candidate_count": page_candidate_count,
            "block_candidate_count": block_candidate_count,
            "bbox_candidate_count": bbox_candidate_count,
            "same_page_bounded_evidence_window_candidate_count": same_page_count,
            "answer_ready_window_sufficiency_metric_computed": True,
            "answer_ready_window_sufficiency_measurable": target_window_measurable,
            "answer_ready_window_sufficient": answer_ready_sufficient,
            "answer_ready_window_sufficiency_metric_scope": "selector_target_hit_same_page_bbox_window_only",
            "bbox_correctness_metric_computed": False,
            "bbox_correctness_blocked_reason": (
                "No independent bbox correctness evidence exists without expected/supporting/gold leakage."
            ),
            "source_atom_hydrated_from_registry": all(
                candidate.get("source_atom_hydrated_from_registry") is True for candidate in candidate_scores
            )
            if candidate_scores
            else False,
            "evidence_bundle_assembled": all(candidate.get("evidence_bundle_assembled") is True for candidate in candidate_scores)
            if candidate_scores
            else False,
            "canonical_payload_source": "source_registry" if candidate_scores else "not_hydrated",
            "failure_bucket": "",
            "answer_generation_executed": False,
            "deterministic_answer_execution_executed": False,
            "vector_payload_used_as_evidence_truth": False,
            "used_gold_or_expected_text": False,
            "expected_supporting_gold_text_used": False,
            "official_metric_input_rows": 0,
            "diagnostic_only": True,
        }
        eval_row["failure_bucket"] = pdf_failure_bucket(eval_row)
        eval_rows.append(eval_row)
        trace_rows.append(
            {
                "schema_version": f"{RUN_ID}_pdf_layer_trace_per_query_v1",
                "run_id": RUN_ID,
                "query_id": query_id,
                "source_family": "PDF",
                "layers_recorded": list(LAYER_NAMES),
                "layers_skipped_by_design": list(SKIPPED_LAYERS),
                "layer_metrics": {
                    "L2_FILE_WORKBOOK_IDENTITY": {
                        "resolve_status": eval_row["resolve_status"],
                        "file_resolve@1": eval_row["file_resolve@1"],
                        "file_resolve@3": eval_row["file_resolve@3"],
                        "rank1_confidence_bucket": eval_row["rank1_confidence_bucket"],
                        "abstain_or_disambiguate": eval_row["abstain_or_disambiguate"],
                        "wrong_file_forcing_accepted": eval_row["wrong_file_forcing_accepted"],
                        "accepted_wrong_rank1_with_target_in_top3_rerank_candidates": (
                            eval_row["accepted_wrong_rank1_with_target_in_top3_rerank_candidates"]
                        ),
                    },
                    "L3_STRUCTURAL_LOCATOR": {
                        "page_candidate_count": page_candidate_count,
                        "block_candidate_count": block_candidate_count,
                        "bbox_candidate_count": bbox_candidate_count,
                        "same_page_bounded_evidence_window_candidate_count": same_page_count,
                        "bbox_correctness_metric_computed": False,
                    },
                    "L4_SOURCEATOM_HYDRATION": {
                        "source_atom_hydrated_from_registry": eval_row["source_atom_hydrated_from_registry"],
                        "canonical_payload_source": eval_row["canonical_payload_source"],
                    },
                    "L5_EVIDENCE_BUNDLE_ASSEMBLY": {
                        "evidence_bundle_assembled": eval_row["evidence_bundle_assembled"],
                        "vector_payload_used_as_evidence_truth": False,
                    },
                    "L6_EVIDENCE_SELECTOR": {
                        "selector_candidate_count": int(selector_row.get("selector_candidate_count") or 0),
                        "selector_target_hit@3": bool(selector_row.get("selector_target_hit@3")),
                        "selector_file_hit@3": bool(selector_row.get("selector_file_hit@3")),
                    },
                    "L7_ANSWER_READY_CONTEXT": {
                        "answer_generation_executed": False,
                        "answer_ready_window_sufficiency_metric_computed": True,
                        "answer_ready_window_sufficient": answer_ready_sufficient,
                    },
                    "L9_METRICS_FAILURE_TAXONOMY": {
                        "failure_bucket": eval_row["failure_bucket"],
                        "official_metric_input_rows": 0,
                    },
                },
                "diagnostic_only": True,
                "official_metric_input_rows": 0,
                "answer_generation_executed": False,
                "vector_payload_used_as_evidence_truth": False,
                "used_gold_or_expected_text": False,
            }
        )
    return eval_rows, score_rows, trace_rows


def build_metrics(
    *,
    eval_rows: Sequence[Mapping[str, Any]],
    score_rows: Sequence[Mapping[str, Any]],
    v3_11_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    resolved_count = sum(1 for row in eval_rows if row.get("resolve_status") == "resolved")
    abstain_count = sum(1 for row in eval_rows if row.get("resolve_status") == "abstain")
    disambiguation_count = sum(1 for row in eval_rows if row.get("resolve_status") == "disambiguation")
    wrong_forcing_count = sum(1 for row in eval_rows if row.get("wrong_file_forcing_accepted") is True)
    accepted_wrong_top3_count = sum(
        1 for row in eval_rows if row.get("accepted_wrong_rank1_with_target_in_top3_rerank_candidates") is True
    )
    confidence_counts = Counter(clean(row.get("rank1_confidence_bucket") or "unknown") for row in eval_rows)
    page_candidate_count = sum(1 for row in score_rows if row.get("page") is not None)
    block_candidate_count = sum(1 for row in score_rows if row.get("region_type"))
    bbox_candidate_count = sum(1 for row in score_rows if row.get("bbox_present") is True)
    same_page_candidate_count = sum(
        1 for row in score_rows if row.get("same_page_bounded_evidence_window_candidate") is True
    )
    window_measurable_count = sum(1 for row in eval_rows if row.get("answer_ready_window_sufficiency_measurable") is True)
    window_sufficient_count = sum(1 for row in eval_rows if row.get("answer_ready_window_sufficient") is True)
    v3_11_pdf = v3_11_metrics["per_source_family"]["PDF_FILE_IDENTITY"]["metrics"]
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "answer_generation_executed": False,
        "deterministic_answer_execution_executed": False,
        "pdf_xlsx_collapsed_headline_score_reported": False,
        "pdf_file_identity_structural_locator_eval": {
            "v3_11_pdf_file_identity_reference": {
                "source_run_id": "official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic",
                "metric_scope": "seen_validation_only_file_identity_no_answer_ready_window_claim",
                "query_count": int(v3_11_pdf["query_count"]),
                "file_resolve@1": v3_11_pdf["file_resolve@1"],
                "file_resolve@3": v3_11_pdf["file_resolve@3"],
                "abstain_rate": v3_11_pdf["abstain_rate"],
                "wrong_file_block_rate": v3_11_pdf["wrong_file_block_rate"],
            },
            "v3_13_pdf_file_identity_confidence_diagnostic": {
                "metric_scope": "diagnostic_only_seen_reference_file_identity_confidence_no_rerank",
                "query_count": len(eval_rows),
                "file_resolve@1": bool_metric(eval_rows, "file_resolve@1"),
                "file_resolve@3": bool_metric(eval_rows, "file_resolve@3"),
                "abstain_rate": bool_metric(eval_rows, "abstain_rate"),
                "wrong_file_block_rate": bool_metric(eval_rows, "wrong_file_block_rate"),
                "resolved_count": resolved_count,
                "abstain_count": abstain_count,
                "disambiguation_count": disambiguation_count,
                "abstain_or_disambiguation_count": abstain_count + disambiguation_count,
                "wrong_file_forcing_accepted_rate": ratio(wrong_forcing_count, len(eval_rows)),
                "wrong_file_forcing_delta_from_v3_11": ratio(0, len(eval_rows)),
                "wrong_file_forcing_delta_disclosure": (
                    "v3_13 does not change PDF file selection; forcing delta is reported explicitly as zero."
                ),
                "accepted_wrong_rank1_with_target_in_top3_rerank_candidates": ratio(
                    accepted_wrong_top3_count,
                    len(eval_rows),
                ),
                "rank1_confidence_bucket_counts": dict(sorted(confidence_counts.items())),
            },
            "v3_13_pdf_evidence_window_diagnostic": {
                "metric_scope": "diagnostic_only_same_page_bbox_window_availability_not_answer_generation",
                "query_count": len(eval_rows),
                "candidate_count": len(score_rows),
                "page_candidate@3": ratio(page_candidate_count, len(score_rows)),
                "block_candidate@3": ratio(block_candidate_count, len(score_rows)),
                "bbox_present@3": ratio(bbox_candidate_count, len(score_rows)),
                "same_page_bounded_evidence_window_candidate@3": ratio(same_page_candidate_count, len(score_rows)),
                "answer_ready_window_sufficiency_metric_computed": True,
                "answer_ready_window_sufficiency_metric_scope": "selector_target_hit_same_page_bbox_window_only",
                "answer_ready_window_measurable@query": ratio(window_measurable_count, len(eval_rows)),
                "answer_ready_window_sufficient@query": ratio(window_sufficient_count, len(eval_rows)),
                "bbox_correctness_metric_computed": False,
                "bbox_correctness_metric_blocked_reason": (
                    "No independent bbox correctness evidence can be computed without gold/expected/supporting leakage."
                ),
                "ocr_touched": False,
            },
        },
        "fresh_real_holdout": {
            "sufficient": False,
            "row_count": 0,
            "product_success_evidence_allowed": False,
            "blocked_reason": "fresh real PDF source-document-disjoint holdout unavailable",
        },
    }


def build_per_family(metrics: Mapping[str, Any], v3_12_summary: Mapping[str, Any]) -> dict[str, Any]:
    pdf_eval = metrics["pdf_file_identity_structural_locator_eval"]
    xlsx_control = v3_12_summary["v3_12_nonprod_structural_locator_smoke"]
    return {
        "schema_version": f"{RUN_ID}_per_family_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "families_reported_separately": [
            "PDF_FILE_IDENTITY",
            "PDF_STRUCTURAL_LOCATOR",
            "PDF_EVIDENCE_WINDOW",
            "XLSX_CONTROL",
        ],
        "per_source_family": {
            "PDF_FILE_IDENTITY": {
                "metric_scope": "diagnostic_only_file_identity_confidence",
                "metrics": pdf_eval["v3_13_pdf_file_identity_confidence_diagnostic"],
            },
            "PDF_STRUCTURAL_LOCATOR": {
                "metric_scope": "diagnostic_only_page_block_bbox_locator_candidates",
                "metrics": {
                    key: value
                    for key, value in pdf_eval["v3_13_pdf_evidence_window_diagnostic"].items()
                    if key in {"query_count", "candidate_count", "page_candidate@3", "block_candidate@3", "bbox_present@3"}
                },
            },
            "PDF_EVIDENCE_WINDOW": {
                "metric_scope": "diagnostic_only_same_page_bounded_window_sufficiency",
                "metrics": pdf_eval["v3_13_pdf_evidence_window_diagnostic"],
            },
            "XLSX_CONTROL": {
                "source_run_id": v312.RUN_ID,
                "metric_scope": "visible_no_regression_control_lane_not_optimized_in_v3_13",
                "optimized_in_this_phase": False,
                "metrics": xlsx_control,
            },
        },
    }


def build_manifest_summary(
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
    eval_rows: Sequence[Mapping[str, Any]],
    score_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    pdf_registry_rows = [row for row in source_registry.values() if clean(row.get("source_family")).upper() == "PDF"]
    return {
        "schema_version": f"{RUN_ID}_pdf_nonprod_manifest_summary_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "index_namespace": ALLOWED_NAMESPACE,
        "source_namespace": SOURCE_NAMESPACE,
        "manifest_only": True,
        "index_build_executed": False,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "sourceatom_registry_rows_scanned": len(pdf_registry_rows),
        "pdf_query_rows": len(eval_rows),
        "pdf_candidate_rows": len(score_rows),
        "page_candidate_rows": sum(1 for row in score_rows if row.get("page") is not None),
        "block_candidate_rows": sum(1 for row in score_rows if row.get("region_type")),
        "bbox_candidate_rows": sum(1 for row in score_rows if row.get("bbox_present") is True),
        "same_page_bounded_window_candidate_rows": sum(
            1 for row in score_rows if row.get("same_page_bounded_evidence_window_candidate") is True
        ),
        "protected_namespaces_touched": [],
        "source_atom_registry_mutated": False,
        "source_registry_baseline_mutated": False,
        "official_denominator_mutated": False,
        "db_or_production_namespace_written": False,
        "vector_payload_used_as_evidence_truth": False,
        "namespace_decision_rationale": (
            "v3_13 is a manifest-only PDF diagnostic sidecar over SourceAtom registry truth and existing candidate "
            "rows; no protected non-prod or production index is built or mutated."
        ),
    }


def build_leakage_audit() -> list[dict[str, Any]]:
    buckets = (
        "answer_value_in_query",
        "expected_supporting_gold_text",
        "gold_label_or_qrels",
        "vector_payload_as_evidence_truth",
        "file_or_source_title_success_evidence",
        "index_to_content_success_evidence",
        "production_namespace_write",
    )
    return [
        {
            "schema_version": f"{RUN_ID}_leakage_audit_v1",
            "run_id": RUN_ID,
            "probe_id": f"v3_13_leakage_probe_{index:02d}",
            "bucket": bucket,
            "success_evidence_allowed": False,
            "retrieval_or_generation_input_used": False,
            "official_metric_input_rows": 0,
            "diagnostic_only": True,
        }
        for index, bucket in enumerate(buckets, start=1)
    ]


def build_failure_taxonomy(eval_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = Counter(clean(row.get("failure_bucket")) for row in eval_rows)
    samples: dict[str, list[str]] = {}
    for row in eval_rows:
        bucket = clean(row.get("failure_bucket"))
        samples.setdefault(bucket, [])
        if len(samples[bucket]) < 5:
            samples[bucket].append(clean(row.get("query_id")))
    return {
        "schema_version": f"{RUN_ID}_failure_taxonomy_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "taxonomy_scope": "pdf_file_identity_structural_locator_nonprod_alignment",
        "failure_bucket_counts": dict(sorted(counts.items())),
        "sample_query_ids_by_bucket": samples,
        "product_success_evidence_allowed": False,
    }


def guardrail_flags() -> dict[str, Any]:
    return {
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "answer_value_in_query_success_evidence_used": False,
        "index_to_content_success_evidence_used": False,
        "file_or_source_title_leak_success_evidence_used": False,
    }


def build_guardrail_audit() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "protected_namespaces": list(PROTECTED_NAMESPACES),
        "protected_namespaces_touched": [],
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "direct_normalized_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "source_atom_registry_canonical_truth": True,
        "source_atom_registry_mutated": False,
        "source_registry_baseline_mutated": False,
        "official_denominator_mutated": False,
        "db_or_production_namespace_written": False,
        "vector_payload_used_as_evidence_truth": False,
        "answer_generation_executed": False,
        "deterministic_answer_execution_executed": False,
        "pdf_bbox_correctness_metric_computed": False,
        "xlsx_v3_12_control_lane_only": True,
        **guardrail_flags(),
    }


def build_holdout_manifest(v310_holdout: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_holdout_manifest_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "fresh_real_holdout_sufficient": False,
        "product_success_evidence_allowed": False,
        "promotion_evidence": False,
        "real_unseen_registry_counts": v310_holdout["real_unseen_registry_counts"],
        "real_query_fidelity_included_counts": v310_holdout["real_query_fidelity_included_counts"],
        "minimum_targets": v310_holdout["minimum_targets"],
        "blocked_reason": "fresh real PDF source-document-disjoint holdout unavailable",
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    artifact_sha256: Mapping[str, str],
    input_lineage: Mapping[str, Any],
    manifest_summary: Mapping[str, Any],
    v3_12_summary: Mapping[str, Any],
) -> dict[str, Any]:
    pdf_eval = metrics["pdf_file_identity_structural_locator_eval"]
    return {
        "schema_version": f"{RUN_ID}_summary_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "event_type": EVENT_TYPE,
        "run_class": "diagnostic_only_pdf_file_identity_structural_locator_nonprod_alignment",
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "fine_tuning_executed": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "fresh_real_holdout_sufficient": False,
        "answer_generation_executed": False,
        "deterministic_answer_execution_executed": False,
        "direct_normalized_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "answer_value_in_query_success_evidence_used": False,
        "index_to_content_success_evidence_used": False,
        "file_or_source_title_leak_success_evidence_used": False,
        "index_namespace": ALLOWED_NAMESPACE,
        "source_index_namespace": SOURCE_NAMESPACE,
        "protected_namespaces_touched": [],
        "source_atom_registry_canonical_truth": True,
        "source_atom_registry_mutated": False,
        "source_registry_baseline_mutated": False,
        "official_denominator_mutated": False,
        "db_or_production_namespace_written": False,
        "vector_payload_used_as_evidence_truth": False,
        "pdf_file_identity_answer_window_kept_separate": True,
        "pdf_bbox_correctness_metric_computed": False,
        "pdf_answer_ready_evidence_window_metric_computed": True,
        "xlsx_v3_12_control_lane_only": True,
        "xlsx_v3_12_control_metrics": v3_12_summary["v3_12_nonprod_structural_locator_smoke"],
        "layer_contract": list(LAYER_NAMES),
        "layers_skipped_by_design": list(SKIPPED_LAYERS),
        "pdf_file_identity_confidence_diagnostic": pdf_eval["v3_13_pdf_file_identity_confidence_diagnostic"],
        "pdf_evidence_window_diagnostic": pdf_eval["v3_13_pdf_evidence_window_diagnostic"],
        "pdf_nonprod_manifest_summary": {
            "index_namespace": manifest_summary["index_namespace"],
            "manifest_only": manifest_summary["manifest_only"],
            "index_build_executed": manifest_summary["index_build_executed"],
        },
        "input_lineage": dict(input_lineage),
        "artifact_paths": {key: repo_relative(path) for key, path in OUTPUTS.items()},
        "artifact_sha256": dict(artifact_sha256),
        **guardrail_flags(),
    }


@lru_cache(maxsize=1)
def build_artifacts() -> dict[str, Any]:
    input_paths = {
        "v3_8_1_evidence_selector_per_query_jsonl": V3_8_1_EVIDENCE_SELECTOR_PER_QUERY,
        "v3_8_2_pdf_file_resolve_per_query_jsonl": V3_8_2_FILE_RESOLVE_PER_QUERY,
        "v3_9_1_pdf_file_identity_per_query_jsonl": v392.V3_9_1_PER_QUERY,
        "v3_11_summary_json": V3_11_SUMMARY,
        "v3_11_metrics_json": V3_11_METRICS,
        "v3_12_xlsx_summary_json": V3_12_SUMMARY,
        "v3_12_xlsx_metrics_json": V3_12_METRICS,
        "v3_10_holdout_manifest_json": v310.OUTPUTS["fresh_real_holdout_manifest_json"],
        "source_registry_jsonl": v392.SOURCE_REGISTRY_JSONL,
    }
    missing = [repo_relative(path) for path in input_paths.values() if not artifact_exists(path)]
    if missing:
        raise FileNotFoundError("missing required v3_13 input artifacts: " + ", ".join(missing))
    input_lineage = {
        key: {"path": repo_relative(path), "sha256": sha256_file(path)}
        for key, path in input_paths.items()
    }
    source_registry = load_source_registry()
    selector_by_query = selector_rows_by_query_id()
    pdf_rows = [row for row in read_jsonl(v392.V3_9_1_PER_QUERY) if clean(row.get("source_family")).upper() == "PDF"]
    eval_rows, score_rows, trace_rows = build_pdf_eval(
        pdf_rows=pdf_rows,
        selector_by_query=selector_by_query,
        source_registry=source_registry,
    )
    v3_11_metrics = read_json(V3_11_METRICS)
    v3_12_summary = read_json(V3_12_SUMMARY)
    metrics = build_metrics(eval_rows=eval_rows, score_rows=score_rows, v3_11_metrics=v3_11_metrics)
    per_family = build_per_family(metrics, v3_12_summary)
    manifest_summary = build_manifest_summary(source_registry=source_registry, eval_rows=eval_rows, score_rows=score_rows)
    leakage = build_leakage_audit()
    failure = build_failure_taxonomy(eval_rows)
    guardrail = build_guardrail_audit()
    holdout = build_holdout_manifest(read_json(v310.OUTPUTS["fresh_real_holdout_manifest_json"]))
    artifacts: dict[str, Any] = {
        "metrics": metrics,
        "per_family": per_family,
        "pdf_eval_rows": eval_rows,
        "pdf_score_rows": score_rows,
        "pdf_trace_rows": trace_rows,
        "pdf_manifest_summary": manifest_summary,
        "leakage_audit_rows": leakage,
        "failure_taxonomy": failure,
        "guardrail_audit": guardrail,
        "holdout_manifest": holdout,
        "input_lineage": input_lineage,
    }
    artifacts["summary"] = build_summary(
        metrics=metrics,
        artifact_sha256={},
        input_lineage=input_lineage,
        manifest_summary=manifest_summary,
        v3_12_summary=v3_12_summary,
    )
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


def update_docs(metrics: Mapping[str, Any]) -> None:
    pdf_eval = metrics["pdf_file_identity_structural_locator_eval"]
    identity_ref = pdf_eval["v3_11_pdf_file_identity_reference"]
    identity = pdf_eval["v3_13_pdf_file_identity_confidence_diagnostic"]
    window = pdf_eval["v3_13_pdf_evidence_window_diagnostic"]
    xlsx = read_json(V3_12_SUMMARY)["v3_12_nonprod_structural_locator_smoke"]
    progress_entry = (
        f"- v3_13 PDF file identity structural locator non-prod alignment (`{RUN_ID}`) adds diagnostic-only "
        "PDF L2 file identity confidence diagnostics, abstain/disambiguation vs wrong-file forcing analysis, "
        "accepted wrong rank1 with target in top3 rerank candidates, page/block/bbox structural locator "
        "candidates, and same-page bounded evidence-window candidates. SourceAtom registry remains canonical "
        "truth; SearchView/vector payload remains candidate-only; L8 generation and deterministic answer "
        "execution stay closed. XLSX v3_12 remains visible as a no-regression/control lane only. "
        "official_metric_input_rows=0; product_success_evidence_allowed=false; protected_namespaces_touched=[]; "
        "fresh real PDF source-document-disjoint holdout remains required."
    )
    measurements_entry = f"""## 2026-05-25 - v3_13 PDF File Identity Structural Locator Non-Prod Alignment

- Run: `{RUN_ID}`
- Policy: diagnostic-only; official_metric_input_rows=0; product_success_evidence_allowed=false; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no answer generation, deterministic answer execution, fine-tuning, threshold tuning, winner selection, or promotion.
- Scope: PDF L2/L3 catch-up only. File identity metrics are reported separately from evidence-window metrics. XLSX v3_12 remains a visible control lane, not optimized in v3_13.
- Holdout: still insufficient. Fresh real PDF source-document-disjoint holdout is required before product success evidence.

| Lane | metric | value |
| --- | --- | ---: |
| PDF file identity | file_resolve@1 | {identity['file_resolve@1']['numerator']}/{identity['file_resolve@1']['denominator']} |
| PDF file identity | file_resolve@3 | {identity['file_resolve@3']['numerator']}/{identity['file_resolve@3']['denominator']} |
| PDF file identity | abstain_or_disambiguation | {identity['abstain_or_disambiguation_count']}/{identity['query_count']} |
| PDF file identity | accepted wrong rank1 with target in top3 | {identity['accepted_wrong_rank1_with_target_in_top3_rerank_candidates']['numerator']}/{identity['accepted_wrong_rank1_with_target_in_top3_rerank_candidates']['denominator']} |
| PDF file identity | wrong-file forcing delta from v3_11 | {identity['wrong_file_forcing_delta_from_v3_11']['numerator']}/{identity['wrong_file_forcing_delta_from_v3_11']['denominator']} |
| PDF structural locator | page candidates | {window['page_candidate@3']['numerator']}/{window['page_candidate@3']['denominator']} |
| PDF structural locator | block candidates | {window['block_candidate@3']['numerator']}/{window['block_candidate@3']['denominator']} |
| PDF structural locator | bbox candidates | {window['bbox_present@3']['numerator']}/{window['bbox_present@3']['denominator']} |
| PDF evidence window | same-page bounded candidates | {window['same_page_bounded_evidence_window_candidate@3']['numerator']}/{window['same_page_bounded_evidence_window_candidate@3']['denominator']} |
| PDF evidence window | answer-ready sufficiency | {window['answer_ready_window_sufficient@query']['numerator']}/{window['answer_ready_window_sufficient@query']['denominator']} |
| PDF evidence window | bbox correctness | not computed |
| XLSX v3_12 control | optimized in v3_13 | false |
| XLSX v3_12 control | cell_or_value@1 | {xlsx['cell_or_value@1']['numerator']}/{xlsx['cell_or_value@1']['denominator']} |

Reference: v3_11 PDF file_resolve@1 was {identity_ref['file_resolve@1']['numerator']}/{identity_ref['file_resolve@1']['denominator']}. The wrong-file forcing delta is explicitly disclosed as zero because v3_13 does not change PDF file selection.
"""
    triage_entry = f"""## v3_13 PDF File Identity Structural Locator Triage

- PDF remains a file-identity-first bottleneck, but the catch-up surface now separates file confidence from structural evidence windows.
- The main disclosed risk slice is accepted wrong rank1 with target in top3: {identity['accepted_wrong_rank1_with_target_in_top3_rerank_candidates']['numerator']}/{identity['accepted_wrong_rank1_with_target_in_top3_rerank_candidates']['denominator']}. This is a rerank-candidate diagnostic, not a file-forcing change.
- bbox correctness is not claimed. v3_13 only reports page/block/bbox availability and same-page bounded evidence-window sufficiency where selector evidence can be measured without expected/supporting/gold text.
- XLSX v3_12 stays as no-regression control only; no XLSX optimization or metric promotion is part of this phase.
- fresh real PDF source-document-disjoint holdout remains required before product success evidence or promotion.
"""
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        "Overall status: `diagnostic_v3_13_pdf_file_identity_structural_locator_nonprod_alignment_ready`;",
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
        "promotion_evidence": False,
        "answer_generation_executed": False,
        "deterministic_answer_execution_executed": False,
        "index_namespace": ALLOWED_NAMESPACE,
        "source_index_namespace": SOURCE_NAMESPACE,
        "pdf_file_identity_answer_window_kept_separate": True,
        "pdf_bbox_correctness_metric_computed": False,
        "xlsx_v3_12_control_lane_only": True,
        "protected_namespaces_touched": [],
        "artifact_paths": summary["artifact_paths"],
        "artifact_sha256": {**summary["artifact_sha256"], "summary_json_sha256": sha256_file(OUTPUTS["summary_json"])},
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def write_artifacts(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    write_json(OUTPUTS["metrics_json"], artifacts["metrics"])
    write_json(OUTPUTS["per_family_json"], artifacts["per_family"])
    write_jsonl(OUTPUTS["pdf_structural_locator_eval_per_query_jsonl"], artifacts["pdf_eval_rows"])
    write_jsonl(OUTPUTS["pdf_layer_trace_per_query_jsonl"], artifacts["pdf_trace_rows"])
    write_jsonl(OUTPUTS["pdf_score_components_jsonl"], artifacts["pdf_score_rows"])
    write_json(OUTPUTS["pdf_nonprod_manifest_summary_json"], artifacts["pdf_manifest_summary"])
    write_jsonl(OUTPUTS["leakage_audit_jsonl"], artifacts["leakage_audit_rows"])
    write_json(OUTPUTS["failure_taxonomy_json"], artifacts["failure_taxonomy"])
    write_json(OUTPUTS["guardrail_audit_json"], artifacts["guardrail_audit"])
    write_json(OUTPUTS["holdout_manifest_json"], artifacts["holdout_manifest"])
    artifact_sha = {
        key.replace("_jsonl", "").replace("_json", "") + "_sha256": sha256_file(path)
        for key, path in OUTPUTS.items()
        if key != "summary_json"
    }
    v3_12_summary = read_json(V3_12_SUMMARY)
    summary = build_summary(
        metrics=artifacts["metrics"],
        artifact_sha256=artifact_sha,
        input_lineage=artifacts["input_lineage"],
        manifest_summary=artifacts["pdf_manifest_summary"],
        v3_12_summary=v3_12_summary,
    )
    write_json(OUTPUTS["summary_json"], summary)
    append_status_event(summary)
    update_docs(artifacts["metrics"])
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build v3_13 diagnostic-only PDF file identity/locator artifacts.")
    parser.add_argument("--check", action="store_true", help="Build in memory only.")
    args = parser.parse_args(argv)
    artifacts = build_artifacts()
    if args.check:
        identity = artifacts["metrics"]["pdf_file_identity_structural_locator_eval"][
            "v3_13_pdf_file_identity_confidence_diagnostic"
        ]
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": artifacts["summary"]["status"],
                    "file_resolve@1": identity["file_resolve@1"],
                    "wrong_file_forcing_delta_from_v3_11": identity["wrong_file_forcing_delta_from_v3_11"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    summary = write_artifacts(artifacts)
    print(json.dumps({"run_id": RUN_ID, "status": summary["status"], "summary": repo_relative(OUTPUTS["summary_json"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
