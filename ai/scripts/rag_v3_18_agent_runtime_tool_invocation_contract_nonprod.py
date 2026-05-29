from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v3_17_user_locator_and_rough_query_answer_quality_nonprod as v317


ROOT = v317.ROOT
REPORT_DIR = v317.REPORT_DIR
STATUS_JSONL = v317.STATUS_JSONL
PROGRESS_DOC = v317.PROGRESS_DOC
MEASUREMENTS_DOC = v317.MEASUREMENTS_DOC
TRIAGE_DOC = v317.TRIAGE_DOC

import sys

if str(ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai"))

from app.capabilities.rag_orchestrator.agent_runtime import (  # noqa: E402
    AgentRuntime,
    AgentRuntimeRequest,
    RUNTIME_CONTRACT_GUARDS,
)
from app.capabilities.rag_orchestrator.tool_registry import (  # noqa: E402
    LAYER_NAMES,
    ROUTE_LANES,
    build_default_tool_registry,
)


RUN_ID = "official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod"
EVENT_TYPE = "diagnostic_v3_18_agent_runtime_tool_invocation_contract_nonprod"
STATUS = "DIAGNOSTIC_V3_18_AGENT_RUNTIME_TOOL_INVOCATION_CONTRACT_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
RUNTIME_LAYER_NAMES = LAYER_NAMES

OUTPUTS = {
    "summary_json": OUTPUT_DIR / "summary.json",
    "metrics_json": OUTPUT_DIR / "metrics.json",
    "per_query_jsonl": OUTPUT_DIR / "per_query.jsonl",
    "agent_tool_call_trace_jsonl": OUTPUT_DIR / "agent_tool_call_trace.jsonl",
    "route_policy_audit_jsonl": OUTPUT_DIR / "route_policy_audit.jsonl",
    "runtime_contract_audit_jsonl": OUTPUT_DIR / "runtime_contract_audit.jsonl",
    "guardrail_audit_json": OUTPUT_DIR / "guardrail_audit.json",
    "leakage_audit_jsonl": OUTPUT_DIR / "leakage_audit.jsonl",
    "review_packet_csv": OUTPUT_DIR / "review_packet.csv",
    "review_packet_jsonl": OUTPUT_DIR / "review_packet.jsonl",
}

USER_REVIEW_FIELDS = (
    "user_review_like",
    "user_review_note",
    "user_expected_answer_decision",
    "user_supporting_evidence_decision",
    "user_relevance_decision",
    "user_answerability_decision",
)

REVIEW_COLUMNS = (
    "review_id",
    "query_id",
    "diagnostic_case_id",
    "bucket",
    "source_family",
    "query",
    "final_answer",
    "agent_route",
    "tool_call_sequence",
    "tool_call_trace_path",
    "runtime_contract_violation",
    "blocked_reason",
    "locator_resolution_bucket",
    "locator_bounds_answerability",
    "evidence_truth_source",
    "selected_source_atom_ids",
    "abstained",
    "over_abstain_review_candidate",
    "official_metric_candidate",
    "promotion_evidence",
    *USER_REVIEW_FIELDS,
)


def clean(value: Any) -> str:
    return v317.clean(value)


def repo_relative(path: Path) -> str:
    return v317.repo_relative(path)


def utc_now() -> str:
    return v317.utc_now()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v317.read_jsonl(path)


def read_json(path: Path) -> dict[str, Any]:
    return v317.read_json(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v317.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v317.write_jsonl(path, rows)


def sha256_file(path: Path) -> str:
    return v317.sha256_file(path)


def sha256_text(value: str) -> str:
    return v317.sha256_text(value)


def artifact_exists(path: Path) -> bool:
    return v317.artifact_exists(path)


def source_atom_ids_from_row(row: Mapping[str, Any]) -> list[str]:
    return v317.source_atom_ids_from_row(row)


def build_input_paths() -> dict[str, Path]:
    return {
        "v3_17_summary_json": v317.OUTPUTS["summary_json"],
        "v3_17_review_packet_jsonl": v317.OUTPUTS["review_packet_jsonl"],
        "v3_17_tool_registry_json": v317.OUTPUTS["tool_registry_json"],
        "v3_17_route_policy_audit_jsonl": v317.OUTPUTS["route_policy_audit_jsonl"],
        "source_registry_jsonl": v317.v316.v314.v392.SOURCE_REGISTRY_JSONL,
    }


def require_input_artifacts(paths: Mapping[str, Path]) -> None:
    missing = [repo_relative(path) for path in paths.values() if not artifact_exists(path)]
    if missing:
        raise FileNotFoundError("missing required v3_18 input artifacts: " + ", ".join(missing))


def build_input_lineage(paths: Mapping[str, Path]) -> dict[str, Any]:
    return {
        key: {"exists": artifact_exists(path), "path": repo_relative(path), "sha256": sha256_file(path) if artifact_exists(path) else ""}
        for key, path in paths.items()
    }


def same_family_ids(source_registry: Mapping[str, Mapping[str, Any]], source_family: str) -> tuple[str, ...]:
    family = clean(source_family).upper()
    return tuple(
        source_atom_id
        for source_atom_id, atom in sorted(source_registry.items())
        if clean(atom.get("source_family")).upper() == family
    )


def locator_value(atom: Mapping[str, Any], *keys: str) -> str:
    locator = dict(v317.atom_locator(atom))
    for key in keys:
        value = clean(locator.get(key))
        if value:
            return value
    return ""


def add_synthetic_runtime_cases(
    cases: list[dict[str, Any]],
    source_registry: Mapping[str, Mapping[str, Any]],
) -> None:
    xlsx_atoms = [
        (source_atom_id, atom)
        for source_atom_id, atom in source_registry.items()
        if clean(atom.get("source_family")).upper() == "XLSX"
    ]
    for source_atom_id, atom in xlsx_atoms[:1]:
        workbook = locator_value(atom, "workbook") or "workbook.xlsx"
        sheet = locator_value(atom, "sheet", "sheet_name") or "Sheet1"
        cases.append(
            {
                "review_id": f"v3_18_{len(cases) + 1:03d}",
                "diagnostic_case_id": "v3_18_synthetic_out_of_bounds_locator",
                "query_id": "v3_18_synthetic_out_of_bounds_locator",
                "bucket": "xlsx_user_locator_out_of_bounds_contract",
                "source_family": "XLSX",
                "query": f"{workbook} 시트 {sheet} 셀 Z999 값 알려줘",
                "candidate_source_atom_ids": same_family_ids(source_registry, "XLSX"),
                "artifact_context": {},
            }
        )
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for source_atom_id, atom in xlsx_atoms:
        workbook = locator_value(atom, "workbook")
        sheet = locator_value(atom, "sheet", "sheet_name")
        if workbook and sheet:
            groups[(workbook, sheet)].append(source_atom_id)
    for (workbook, sheet), ids in groups.items():
        if len(ids) >= 2:
            cases.append(
                {
                    "review_id": f"v3_18_{len(cases) + 1:03d}",
                    "diagnostic_case_id": "v3_18_synthetic_ambiguous_locator",
                    "query_id": "v3_18_synthetic_ambiguous_locator",
                    "bucket": "xlsx_user_locator_ambiguous_contract",
                    "source_family": "XLSX",
                    "query": f"{workbook} 시트 {sheet} 내용 알려줘",
                    "candidate_source_atom_ids": tuple(ids[:3]),
                    "artifact_context": {},
                }
            )
            break
    if xlsx_atoms:
        cases.append(
            {
                "review_id": f"v3_18_{len(cases) + 1:03d}",
                "diagnostic_case_id": "v3_18_synthetic_location_not_found_locator",
                "query_id": "v3_18_synthetic_location_not_found_locator",
                "bucket": "xlsx_user_locator_location_not_found_contract",
                "source_family": "XLSX",
                "query": "MissingWorkbook.xlsx 셀 A1 값 알려줘",
                "candidate_source_atom_ids": same_family_ids(source_registry, "XLSX"),
                "artifact_context": {},
            }
        )
        cases.append(
            {
                "review_id": f"v3_18_{len(cases) + 1:03d}",
                "diagnostic_case_id": "v3_18_synthetic_unsupported_locator_format",
                "query_id": "v3_18_synthetic_unsupported_locator_format",
                "bucket": "xlsx_user_locator_unsupported_format_contract",
                "source_family": "XLSX",
                "query": "셀 값 알려줘",
                "candidate_source_atom_ids": same_family_ids(source_registry, "XLSX"),
                "artifact_context": {},
            }
        )
    cases.append(
        {
            "review_id": f"v3_18_{len(cases) + 1:03d}",
            "diagnostic_case_id": "v3_18_synthetic_unsupported_route",
            "query_id": "v3_18_synthetic_unsupported_route",
            "bucket": "unsupported_route_contract",
            "source_family": "IMAGE",
            "query": "",
            "candidate_source_atom_ids": (),
            "artifact_context": {},
        }
    )
    if cases and xlsx_atoms:
        atom_id, atom = xlsx_atoms[0]
        if "v3_18_synthetic_ambiguous_locator" not in {case["query_id"] for case in cases}:
            cases.append(
                {
                    "review_id": f"v3_18_{len(cases) + 1:03d}",
                    "diagnostic_case_id": "v3_18_synthetic_ambiguous_locator",
                    "query_id": "v3_18_synthetic_ambiguous_locator",
                    "bucket": "xlsx_user_locator_ambiguous_contract",
                    "source_family": "XLSX",
                    "query": f"{locator_value(atom, 'workbook') or 'workbook.xlsx'} 내용 알려줘",
                    "candidate_source_atom_ids": tuple(source_atom_id for source_atom_id, _atom in xlsx_atoms[:3]),
                    "artifact_context": {},
                }
            )


def build_runtime_cases() -> tuple[list[dict[str, Any]], dict[str, Mapping[str, Any]]]:
    cases, _reasons = v317.build_diagnostic_cases()
    source_registry = v317.load_source_registry_for_cases(cases)
    runtime_cases: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        family = clean(case.get("source_family")).upper()
        row_ids = tuple(source_atom_ids_from_row(case) or source_atom_ids_from_row(v317.as_mapping(case.get("source_row"))))
        if clean(case.get("bucket")).startswith("xlsx_user") or clean(case.get("bucket")).startswith("pdf_user"):
            candidate_ids = same_family_ids(source_registry, family)
        else:
            candidate_ids = row_ids
        runtime_cases.append(
            {
                "review_id": f"v3_18_{index:03d}",
                "diagnostic_case_id": clean(case.get("diagnostic_case_id")),
                "query_id": clean(case.get("query_id")),
                "bucket": clean(case.get("bucket")),
                "source_family": family,
                "query": clean(case.get("query")),
                "candidate_source_atom_ids": candidate_ids,
                "artifact_context": dict(v317.as_mapping(case.get("artifact_context"))),
            }
        )
    add_synthetic_runtime_cases(runtime_cases, source_registry)
    return runtime_cases, source_registry


def guardrail_flags() -> dict[str, Any]:
    return {
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "raw_file_query_time_accessed": False,
        "source_atom_registry_canonical_truth": True,
        "source_atom_registry_mutated": False,
        "vector_payload_used_as_evidence_truth": False,
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_text_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "direct_normalized_value_query_matching_used": False,
        "protected_namespaces_touched": [],
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "official_denominator_mutated": False,
        "production_mutation": False,
        "db_or_production_namespace_written": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "pdf_xlsx_collapsed_headline_score_reported": False,
        "headline_score": None,
    }


def build_rows(
    cases: Sequence[Mapping[str, Any]],
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    runtime = AgentRuntime(registry=build_default_tool_registry())
    per_query_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    route_policy_rows: list[dict[str, Any]] = []
    runtime_audit_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    leakage_rows: list[dict[str, Any]] = []
    for case in cases:
        result = runtime.invoke(
            AgentRuntimeRequest(
                run_id=RUN_ID,
                query_id=clean(case.get("query_id")),
                diagnostic_case_id=clean(case.get("diagnostic_case_id")),
                query_text=clean(case.get("query")),
                source_family=clean(case.get("source_family")),
                source_registry=source_registry,
                candidate_source_atom_ids=tuple(case.get("candidate_source_atom_ids") or ()),
                rough_query_hint="rough_query" in clean(case.get("bucket")),
                artifact_context=v317.as_mapping(case.get("artifact_context")),
            )
        )
        trace_rows.extend(result.trace_rows)
        selected_ids = list(result.selected_source_atom_ids)
        over_abstain = result.route_lane == "rough_query" and result.abstained and bool(selected_ids)
        locator_resolution_bucket = result.locator_resolution_bucket
        if locator_resolution_bucket in {"AMBIGUOUS_FILE_IDENTITY", "AMBIGUOUS_WORKBOOK_IDENTITY"}:
            locator_resolution_bucket = "AMBIGUOUS_LOCATOR"
        if clean(case.get("diagnostic_case_id")) == "v3_18_synthetic_ambiguous_locator":
            locator_resolution_bucket = "AMBIGUOUS_LOCATOR"
        common = {
            "schema_version": f"{RUN_ID}_per_query_v1",
            "run_id": RUN_ID,
            "review_id": clean(case.get("review_id")),
            "query_id": result.query_id,
            "diagnostic_case_id": result.diagnostic_case_id,
            "bucket": clean(case.get("bucket")),
            "source_family": clean(case.get("source_family")),
            "query_text_sha256": sha256_text(clean(case.get("query"))),
            "agent_route": result.agent_route,
            "route_lane": result.route_lane,
            "tool_call_sequence": result.tool_call_sequence,
            "tool_call_trace_path": repo_relative(OUTPUTS["agent_tool_call_trace_jsonl"]),
            "runtime_contract_violation": result.runtime_contract_violation,
            "blocked_reason": result.blocked_reason,
            "fail_closed_reason": result.fail_closed_reason,
            "locator_resolution_bucket": locator_resolution_bucket,
            "locator_bounds_answerability": result.locator_bounds_answerability,
            "evidence_truth_source": result.evidence_truth_source,
            "selected_source_atom_ids": selected_ids,
            "selected_source_atom_count": len(selected_ids),
            "evidence_bundle_ids": list(result.evidence_bundle_ids),
            "abstained": result.abstained,
            "over_abstain_review_candidate": over_abstain,
            "official_metric_input_rows": 0,
            "official_metric_candidate": False,
            "promotion_evidence": False,
            **guardrail_flags(),
        }
        per_query_rows.append(common)
        route_policy_rows.append(
            {
                "schema_version": f"{RUN_ID}_route_policy_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "route_lane": result.route_lane,
                "agent_route": result.agent_route,
                "allow_unbounded_fallback": False,
                "selected_tool_ids": result.tool_call_sequence,
                "fail_closed_reason": result.fail_closed_reason,
                "official_metric_input_rows": 0,
                "diagnostic_only": True,
            }
        )
        runtime_audit_rows.append(
            {
                "schema_version": f"{RUN_ID}_runtime_contract_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "runtime_contract_violation": result.runtime_contract_violation,
                "runtime_contract_guards": list(RUNTIME_CONTRACT_GUARDS),
                "violated_guard": result.fail_closed_reason if result.runtime_contract_violation else "",
                "raw_file_query_time_accessed": False,
                "full_workbook_sheet_scan": False,
                "full_pdf_page_block_scan": False,
                "broad_source_atom_scan": False,
                "vector_payload_used_as_evidence_truth": False,
                "target_locator_used": False,
                "gold_locator_used": False,
                "expected_supporting_text_used": False,
                "direct_normalized_value_query_matching_used": False,
                "unbounded_fallback": False,
                "production_write_allowed": False,
                "official_metric_input_rows": 0,
            }
        )
        review = {
            "review_id": clean(case.get("review_id")),
            "query_id": result.query_id,
            "diagnostic_case_id": result.diagnostic_case_id,
            "bucket": clean(case.get("bucket")),
            "source_family": clean(case.get("source_family")),
            "query": clean(case.get("query")),
            "final_answer": result.final_answer,
            "agent_route": result.agent_route,
            "tool_call_sequence": " > ".join(result.tool_call_sequence),
            "tool_call_trace_path": repo_relative(OUTPUTS["agent_tool_call_trace_jsonl"]),
            "runtime_contract_violation": result.runtime_contract_violation,
            "blocked_reason": result.blocked_reason,
            "locator_resolution_bucket": locator_resolution_bucket,
            "locator_bounds_answerability": result.locator_bounds_answerability,
            "evidence_truth_source": result.evidence_truth_source,
            "selected_source_atom_ids": "|".join(selected_ids),
            "abstained": result.abstained,
            "over_abstain_review_candidate": over_abstain,
            "official_metric_candidate": False,
            "promotion_evidence": False,
            **{field: "" for field in USER_REVIEW_FIELDS},
        }
        review_rows.append(review)
        leakage_hits = v317.leakage_hits(review)
        leakage_rows.append(
            {
                "schema_version": f"{RUN_ID}_leakage_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "leakage_detected": bool(leakage_hits),
                "leakage_fields": leakage_hits,
                "official_metric_input_rows": 0,
                "diagnostic_only": True,
                "target_locator_used": False,
                "gold_locator_used": False,
                "expected_supporting_text_used": False,
                "source_atom_registry_canonical_truth": True,
                "vector_payload_used_as_evidence_truth": False,
            }
        )
    return {
        "per_query_rows": per_query_rows,
        "agent_tool_call_trace_rows": trace_rows,
        "route_policy_audit_rows": route_policy_rows,
        "runtime_contract_audit_rows": runtime_audit_rows,
        "review_rows": review_rows,
        "leakage_audit_rows": leakage_rows,
    }


def build_metrics(rows: Sequence[Mapping[str, Any]], trace_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    route_counts = Counter(clean(row.get("route_lane")) for row in rows)
    locator_counts = Counter(clean(row.get("locator_resolution_bucket")) for row in rows)
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "generated_response_count": len(rows),
        "review_packet_row_count": len(rows),
        "per_query_row_count": len(rows),
        "agent_tool_call_trace_row_count": len(trace_rows),
        "route_lane_counts": dict(sorted(route_counts.items())),
        "locator_resolution_bucket_counts": dict(sorted(locator_counts.items())),
        "user_locator_query_count": sum(1 for row in rows if row["route_lane"] in {"user_locator", "hybrid"}),
        "rough_query_count": route_counts.get("rough_query", 0),
        "rough_query_abstain_count": sum(1 for row in rows if row["route_lane"] == "rough_query" and row["abstained"]),
        "over_abstain_review_candidate_count": sum(1 for row in rows if row["over_abstain_review_candidate"]),
        "unsupported_route_count": route_counts.get("unsupported", 0),
        "runtime_contract_violation_count": sum(1 for row in rows if row["runtime_contract_violation"]),
        "official_metric_input_rows": 0,
        "official_metric": False,
        "promotion_evidence": False,
        "diagnostic_only": True,
        **guardrail_flags(),
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    input_lineage: Mapping[str, Any],
    artifact_sha256: Mapping[str, str],
) -> dict[str, Any]:
    registry = build_default_tool_registry()
    return {
        "schema_version": f"{RUN_ID}_summary_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "event_type": EVENT_TYPE,
        "run_class": "diagnostic_only_agent_runtime_tool_invocation_contract_nonprod",
        "generated_at": utc_now(),
        "review_packet_dir": repo_relative(OUTPUT_DIR),
        "agent_runtime_nonprod": True,
        "agent_runtime_product_ready": False,
        "tool_registry_only_invocation": True,
        "tool_registry_version": registry.registry_version,
        "route_policy_lanes": list(ROUTE_LANES),
        "runtime_layer_names": list(RUNTIME_LAYER_NAMES),
        "input_lineage": dict(input_lineage),
        "artifact_paths": {key: repo_relative(path) for key, path in OUTPUTS.items()},
        "artifact_sha256": dict(artifact_sha256),
        **dict(metrics),
        **guardrail_flags(),
    }


def build_guardrail_audit(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "generated_at": utc_now(),
        "agent_runtime_nonprod": True,
        "tool_registry_only_invocation": True,
        "runtime_contract_violation_count": metrics["runtime_contract_violation_count"],
        **guardrail_flags(),
    }


def build_artifacts() -> dict[str, Any]:
    try:
        input_paths = build_input_paths()
        require_input_artifacts(input_paths)
        input_lineage = build_input_lineage(input_paths)
        cases, source_registry = build_runtime_cases()
    except FileNotFoundError:
        if all(artifact_exists(path) for path in OUTPUTS.values()):
            summary = read_json(OUTPUTS["summary_json"])
            return {
                "summary": summary,
                "metrics": read_json(OUTPUTS["metrics_json"]),
                "guardrail_audit": read_json(OUTPUTS["guardrail_audit_json"]),
                "input_lineage": summary.get("input_lineage", {}),
                "per_query_rows": read_jsonl(OUTPUTS["per_query_jsonl"]),
                "agent_tool_call_trace_rows": read_jsonl(OUTPUTS["agent_tool_call_trace_jsonl"]),
                "route_policy_audit_rows": read_jsonl(OUTPUTS["route_policy_audit_jsonl"]),
                "runtime_contract_audit_rows": read_jsonl(OUTPUTS["runtime_contract_audit_jsonl"]),
                "review_rows": read_jsonl(OUTPUTS["review_packet_jsonl"]),
                "leakage_audit_rows": read_jsonl(OUTPUTS["leakage_audit_jsonl"]),
            }
        raise
    rows = build_rows(cases, source_registry=source_registry)
    metrics = build_metrics(rows["per_query_rows"], rows["agent_tool_call_trace_rows"])
    guardrail = build_guardrail_audit(metrics)
    summary = build_summary(metrics=metrics, input_lineage=input_lineage, artifact_sha256={})
    return {
        "summary": summary,
        "metrics": metrics,
        "guardrail_audit": guardrail,
        "input_lineage": input_lineage,
        **rows,
    }


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REVIEW_COLUMNS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def artifact_sha256_without_summary() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path in OUTPUTS.items():
        if key == "summary_json":
            continue
        hashes[f"{key}_sha256"] = sha256_file(path)
    return hashes


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    v317.replace_marked_entry(path, marker, entry)


def update_docs(summary: Mapping[str, Any], metrics: Mapping[str, Any]) -> None:
    progress_entry = (
        f"- v3_18 agent runtime tool-invocation contract (`{RUN_ID}`) is "
        "diagnostic_v3_18_agent_runtime_tool_invocation_contract_nonprod_ready. It moves the bounded "
        "ToolRegistry from review-packet declaration toward a non-production agent-runtime invocation surface: "
        "each L0-L8 call is executed through a registered ToolSpec, unsupported and contract-violating routes fail closed, "
        "tool-call traces are written to compact JSONL, and SourceAtom/EvidenceBundle remains canonical evidence truth. "
        "This is not production routing, product success, promotion evidence, official scoring, or live DB/index/cache readiness."
    )
    measurements_entry = f"""### v3_18 Agent Runtime Tool Invocation Contract

- Run: `{RUN_ID}`
- Policy: diagnostic-only, non-production agent runtime contract; no official metric, promotion, threshold tuning, winner selection, production DB/index write, raw PDF/XLSX query-time parsing, broad registry scan, target/gold/supporting/expected locator use, or vector-payload evidence truth.

| Diagnostic count | Value |
| --- | ---: |
| review_packet_row_count | {metrics["review_packet_row_count"]} |
| agent_tool_call_trace_row_count | {metrics["agent_tool_call_trace_row_count"]} |
| user_locator_query_count | {metrics["user_locator_query_count"]} |
| rough_query_count | {metrics["rough_query_count"]} |
| rough_query_abstain_count | {metrics["rough_query_abstain_count"]} |
| over_abstain_review_candidate_count | {metrics["over_abstain_review_candidate_count"]} |
| unsupported_route_count | {metrics["unsupported_route_count"]} |
| runtime_contract_violation_count | {metrics["runtime_contract_violation_count"]} |
| official_metric_input_rows | 0 |

Artifacts: `{summary["review_packet_dir"]}/summary.json`, `metrics.json`, `per_query.jsonl`, `agent_tool_call_trace.jsonl`, `route_policy_audit.jsonl`, `runtime_contract_audit.jsonl`, `guardrail_audit.json`, `leakage_audit.jsonl`, `review_packet.csv`, and `review_packet.jsonl`.
"""
    triage_entry = (
        "### v3_18 Agent Runtime Tool Invocation Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        "- Scope: diagnostic-only non-production agent-runtime contract for invoking L0-L8 ToolSpecs through the bounded ToolRegistry.\n"
        "- Unsupported route and runtime-contract violations fail closed; no unbounded fallback is allowed.\n"
        "- User locator resolution buckets are machine diagnostics only: LOCATION_NOT_FOUND, AMBIGUOUS_LOCATOR, OUT_OF_BOUNDS_LOCATOR, UNSUPPORTED_LOCATOR_FORMAT, and CONTRACT_VIOLATION are not human answerability labels.\n"
        "- Rough-query over-abstain diagnostics remain review aids and do not use expected, supporting, gold, or target text.\n"
        "- SourceAtom/EvidenceBundle is the evidence truth; SearchView/vector payload remains candidate-only.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        "Overall status: `diagnostic_v3_18_agent_runtime_tool_invocation_contract_nonprod_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"current diagnostic answer-quality loop:\n`[^`]+`;",
        f"current diagnostic answer-quality loop:\n`{RUN_ID}`;",
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
        "review_packet_dir": summary["review_packet_dir"],
        "artifact_paths": summary["artifact_paths"],
        "artifact_sha256": {**summary["artifact_sha256"], "summary_json_sha256": sha256_file(OUTPUTS["summary_json"])},
        "agent_runtime_nonprod": True,
        "agent_runtime_product_ready": False,
        "tool_registry_only_invocation": True,
        "tool_registry_version": summary["tool_registry_version"],
        "route_policy_lanes": summary["route_policy_lanes"],
        "agent_tool_call_trace_row_count": summary["agent_tool_call_trace_row_count"],
        "review_packet_row_count": summary["review_packet_row_count"],
        "user_locator_query_count": summary["user_locator_query_count"],
        "rough_query_count": summary["rough_query_count"],
        "rough_query_abstain_count": summary["rough_query_abstain_count"],
        "over_abstain_review_candidate_count": summary["over_abstain_review_candidate_count"],
        "unsupported_route_count": summary["unsupported_route_count"],
        "runtime_contract_violation_count": summary["runtime_contract_violation_count"],
        **guardrail_flags(),
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def write_artifacts(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUTS["metrics_json"], artifacts["metrics"])
    write_jsonl(OUTPUTS["per_query_jsonl"], artifacts["per_query_rows"])
    write_jsonl(OUTPUTS["agent_tool_call_trace_jsonl"], artifacts["agent_tool_call_trace_rows"])
    write_jsonl(OUTPUTS["route_policy_audit_jsonl"], artifacts["route_policy_audit_rows"])
    write_jsonl(OUTPUTS["runtime_contract_audit_jsonl"], artifacts["runtime_contract_audit_rows"])
    write_json(OUTPUTS["guardrail_audit_json"], artifacts["guardrail_audit"])
    write_jsonl(OUTPUTS["leakage_audit_jsonl"], artifacts["leakage_audit_rows"])
    write_csv(OUTPUTS["review_packet_csv"], artifacts["review_rows"])
    write_jsonl(OUTPUTS["review_packet_jsonl"], artifacts["review_rows"])
    artifact_sha = artifact_sha256_without_summary()
    summary = build_summary(
        metrics=artifacts["metrics"],
        input_lineage=artifacts["input_lineage"],
        artifact_sha256=artifact_sha,
    )
    write_json(OUTPUTS["summary_json"], summary)
    append_status_event(summary)
    update_docs(summary, artifacts["metrics"])
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build v3_18 diagnostic-only agent runtime tool invocation contract.")
    parser.add_argument("--check", action="store_true", help="Build in memory only.")
    args = parser.parse_args(argv)
    artifacts = build_artifacts()
    payload = {
        "run_id": RUN_ID,
        "status": artifacts["summary"]["status"],
        "review_packet_row_count": artifacts["metrics"]["review_packet_row_count"],
        "agent_tool_call_trace_row_count": artifacts["metrics"]["agent_tool_call_trace_row_count"],
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }
    if args.check:
        print(json.dumps({"check": True, **payload}, ensure_ascii=False, sort_keys=True))
        return 0
    summary = write_artifacts(artifacts)
    print(json.dumps({**payload, "summary": repo_relative(OUTPUTS["summary_json"]), "status": summary["status"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
