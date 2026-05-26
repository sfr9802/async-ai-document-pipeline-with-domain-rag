from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod as v322


ROOT = v322.ROOT
REPORT_DIR = v322.REPORT_DIR
STATUS_JSONL = v322.STATUS_JSONL
PROGRESS_DOC = v322.PROGRESS_DOC
MEASUREMENTS_DOC = v322.MEASUREMENTS_DOC
TRIAGE_DOC = v322.TRIAGE_DOC
README = ROOT / "README.md"
EVAL_README = ROOT / "ai" / "eval" / "README.md"

V4_NAME = "v4_source_grounded_runtime_locator_and_finetune_readiness"
V4_RUN_FAMILY = "official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod"
RUN_ID = "official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod"
EVENT_TYPE = "diagnostic_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod"
STATUS = "DIAGNOSTIC_V4_1_PERSISTED_XLSX_SOURCEATOM_DISPLAY_METADATA_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"
ADAPTER_NAMESPACE = "rag-data-v4-1-xlsx-sourceatom-display-metadata-nonprod"

SOURCE_SCHEMA_VERSION = "rag_v4_1_persisted_xlsx_sourceatom_display_metadata_row_v1"
REPORT_SCHEMA_VERSION = "rag_v4_1_persisted_xlsx_sourceatom_display_metadata_report_v1"
DISPLAY_METADATA_VERSION = "source_atom_materialized_xlsx_display_metadata_v4_1"
FORMULA_POLICY = "cached_values_only"
FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            *v322.FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES,
            "metrics.json",
            "per_query.jsonl",
            "persisted_sourceatom_manifest.jsonl",
            "review_packet.csv",
            "summary.json",
        }
    )
)


def clean(value: Any) -> str:
    return v322.clean(value)


def repo_relative(path: Path) -> str:
    return v322.repo_relative(path)


def artifact_path_text(path: Path) -> str:
    return v322.artifact_path_text(path)


def utc_now() -> str:
    return v322.utc_now()


def sha256_file(path: Path) -> str:
    return v322.sha256_file(path)


def sha256_text(value: str) -> str:
    return v322.sha256_text(value)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v322.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v322.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v322.write_jsonl(path, rows)


def replay_v3_22_fake_llm(prompt: str, *, query_id: str, **_: object) -> str:
    return json.dumps(
        {
            "final_answer": f"v4_1 deterministic display contract replay for {query_id}",
            "citation_or_provenance_summary": "SourceAtom/EvidenceBundle replay only",
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def stable_row_hash(row: Mapping[str, Any]) -> str:
    return sha256_text(json.dumps(row, ensure_ascii=False, sort_keys=True))


def materialize_persisted_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_atom_id, atom in sorted(v322.source_atoms().items()):
        locator = dict(atom["raw_locator"])
        contract = dict(atom["xlsx_display_contract"])
        row = {
            "schema_version": SOURCE_SCHEMA_VERSION,
            "source_atom_id": source_atom_id,
            "source_family": "XLSX",
            "source_identity": clean(atom.get("source_identity")),
            "content_hash": stable_row_hash(
                {
                    "source_atom_id": source_atom_id,
                    "source_identity": atom.get("source_identity"),
                    "raw_locator": locator,
                    "xlsx_display_contract": contract,
                }
            ),
            "extraction_version": DISPLAY_METADATA_VERSION,
            "workbook_id": clean(locator.get("workbook")),
            "workbook_version_id": f"{clean(locator.get('workbook'))}#v3_22_display_contract_fixture",
            "sheet_name": clean(locator.get("sheet")),
            "cell": clean(locator.get("cell")),
            "cell_range": clean(locator.get("range")),
            "table_id": clean(locator.get("table_id")),
            "row_label": clean(locator.get("row_label")),
            "column_label": clean(locator.get("column_label")),
            "target_column": clean(locator.get("target_column")),
            "value_locator": {
                "workbook": clean(locator.get("workbook")),
                "sheet": clean(locator.get("sheet")),
                "cell": clean(locator.get("cell")),
                "range": clean(locator.get("range")),
                "row_label": clean(locator.get("row_label")),
                "column_label": clean(locator.get("column_label")),
                "target_column": clean(locator.get("target_column")),
            },
            "raw_value": clean(contract.get("raw_value")),
            "normalized_value": clean(contract.get("normalized_value")),
            "display_value": clean(contract.get("display_value")),
            "number_format": clean(contract.get("number_format")),
            "value_type": clean(contract.get("value_type")),
            "formula_cached_value": clean(contract.get("formula_cached_value")),
            "format_confidence": clean(contract.get("format_confidence")),
            "format_provenance": clean(contract.get("format_provenance")),
            "format_drop_reason": clean(contract.get("format_drop_reason")),
            "formula_policy": FORMULA_POLICY,
            "formula_text_visible_to_user": False,
            "formula_evaluated_at_query_time": False,
            "formula_text_retained_extractor_only": False,
            "merged_cell": bool(contract.get("merged_cell")),
            "merged_range": clean(contract.get("merged_range")),
            "merged_owner_cell": clean(contract.get("merged_owner_cell")),
            "raw_file_required_at_query_time": False,
            "raw_xlsx_query_time_parsing": False,
            "extraction_snapshot_present": True,
            "raw_file_exists_claimed": False,
            "parent_pointers": [v322.RUN_ID],
            "hidden_policy_version": "rag_v4_1_formula_text_hidden_v1",
            "macros_executed": False,
            "canonical_citation_payload_includes_display_contract": True,
            "source_atom_evidence_bundle_truth_only": True,
            "searchview_vector_payload_candidate_only": True,
            "vector_payload_used_as_evidence_truth": False,
            "materialized_from_v3_22_contract": True,
            "adapter_namespace": ADAPTER_NAMESPACE,
            "diagnostic_only": True,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
        }
        rows.append(row)
    return rows


def build_v3_22_replay() -> dict[str, Any]:
    artifacts = v322.build_artifacts(llm_client=replay_v3_22_fake_llm)
    report = artifacts["report"]
    metrics = report["metrics"]
    return {
        "schema_version": f"{RUN_ID}_v3_22_rendering_contract_replay_v1",
        "source_run_id": v322.RUN_ID,
        "source_report_schema_version": report["schema_version"],
        "v3_22_report_row_count": metrics["report_row_count"],
        "display_value_used_count": metrics["display_value_used_count"],
        "raw_value_fallback_count": metrics["raw_value_fallback_count"],
        "format_metadata_unavailable_count": metrics["format_metadata_unavailable_count"],
        "formula_cached_value_used_count": metrics["formula_cached_value_used_count"],
        "runtime_contract_violation_count": metrics["runtime_contract_violation_count"],
        "vector_payload_evidence_truth_violation_count": metrics["vector_payload_evidence_truth_violation_count"],
        "raw_file_query_time_accessed": metrics["raw_file_query_time_accessed"],
        "official_metric_input_rows": metrics["official_metric_input_rows"],
        "promotion_evidence": metrics["promotion_evidence"],
        "diagnostic_only": metrics["diagnostic_only"],
        "replay_llm_client": "deterministic_non_metric_contract_replay",
        "local_llm_or_gpu_inference_required": False,
    }


def build_guardrails() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "persisted_xlsx_sourceatom_display_metadata": True,
        "source_atom_evidence_bundle_evidence_truth": True,
        "source_atom_registry_canonical_truth": True,
        "searchview_vector_payload_candidate_only": True,
        "vector_payload_used_as_evidence_truth": False,
        "raw_file_query_time_accessed": False,
        "raw_xlsx_query_time_parsing_forbidden": True,
        "full_workbook_sheet_scan_forbidden": True,
        "formula_evaluation_at_query_time": False,
        "formula_text_visible_to_user_default": False,
        "direct_normalized_value_query_matching_used": False,
        "direct_normalized_answer_value_query_matching_used": False,
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "source_atom_registry_mutated": False,
        "db_or_production_namespace_written": False,
        "protected_namespaces_touched": [],
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "production_routing": False,
        "official_metric": False,
        "official_metric_lift": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "representative_product_performance": False,
        "pdf_xlsx_text_collapsed_headline_product_score": False,
        "fine_tuning_readiness_only": True,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "ft_route_policy_dry_run_executed": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "live_db_index_cache_readiness": False,
        "gpu_required_for_this_slice": False,
        "local_llm_or_gpu_inference_required": False,
    }


def build_metrics(rows: Sequence[Mapping[str, Any]], replay: Mapping[str, Any]) -> dict[str, Any]:
    runtime_contract_violation_count = sum(
        1
        for row in rows
        if row["raw_xlsx_query_time_parsing"]
        or row["formula_evaluated_at_query_time"]
        or row["formula_text_visible_to_user"]
        or row["vector_payload_used_as_evidence_truth"]
    )
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "persisted_xlsx_sourceatom_display_metadata_rows": len(rows),
        "persisted_display_value_available_count": sum(1 for row in rows if clean(row.get("display_value"))),
        "persisted_raw_value_fallback_count": sum(
            1 for row in rows if row.get("format_drop_reason") == "FORMAT_METADATA_UNAVAILABLE"
        ),
        "formula_cached_value_used_count": sum(1 for row in rows if clean(row.get("formula_cached_value"))),
        "format_confidence_high_count": sum(1 for row in rows if row.get("format_confidence") == "high"),
        "format_confidence_low_count": sum(1 for row in rows if row.get("format_confidence") == "low"),
        "format_metadata_unavailable_count": sum(
            1 for row in rows if row.get("format_drop_reason") == "FORMAT_METADATA_UNAVAILABLE"
        ),
        "merged_cell_count": sum(1 for row in rows if row.get("merged_cell")),
        "runtime_contract_violation_count": runtime_contract_violation_count,
        "vector_payload_evidence_truth_violation_count": sum(
            1 for row in rows if row.get("vector_payload_used_as_evidence_truth")
        ),
        "raw_xlsx_query_time_parsing_count": sum(1 for row in rows if row.get("raw_xlsx_query_time_parsing")),
        "formula_evaluated_at_query_time_count": sum(
            1 for row in rows if row.get("formula_evaluated_at_query_time")
        ),
        "formula_text_visible_to_user_count": sum(1 for row in rows if row.get("formula_text_visible_to_user")),
        "canonical_citation_payload_display_contract_rows": sum(
            1 for row in rows if row.get("canonical_citation_payload_includes_display_contract")
        ),
        "v3_22_report_row_count": replay["v3_22_report_row_count"],
        "v3_22_display_value_used_count": replay["display_value_used_count"],
        "v3_22_raw_value_fallback_count": replay["raw_value_fallback_count"],
        "single_report_artifact_contract": True,
        "sidecar_primary_artifacts_suppressed": True,
        "review_csv_created": False,
        "human_review_required": False,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_lift": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "fine_tuning_readiness_only": True,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "live_db_index_cache_readiness": False,
        "gpu_required_for_this_slice": False,
        "local_llm_or_gpu_inference_required": False,
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
    replay: Mapping[str, Any],
) -> dict[str, Any]:
    summary = dict(metrics)
    summary.update(
        {
            "schema_version": f"{RUN_ID}_summary_v1",
            "run_id": RUN_ID,
            "event_type": EVENT_TYPE,
            "status": STATUS,
            "v4_name": V4_NAME,
            "run_family": V4_RUN_FAMILY,
            "run_class": "diagnostic_only_persisted_xlsx_sourceatom_display_metadata_nonprod",
            "generated_at": utc_now(),
            "artifact_paths": dict(artifact_paths),
            "review_packet_dir": repo_relative(OUTPUT_DIR),
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "review_csv_created": False,
            "human_review_required": False,
            "v3_22_rendering_contract_replay": dict(replay),
            "diagnostic_only": True,
            "production_routing": False,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "official_metric_lift": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "fine_tuning_readiness_only": True,
            "fine_tuning_started": False,
            "fine_tuning_executed": False,
            "live_db_index_cache_readiness": False,
            "agent_runtime_product_ready": False,
        }
    )
    return summary


def build_verification_section() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_verification_v1",
        "run_id": RUN_ID,
        "commands_required_by_goal": [
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod.py",
            "python -X utf8 ai\\scripts\\rag_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod.py --check",
            "targeted v4_1 persisted SourceAtom display metadata tests",
            "targeted artifact/status/guardrail tests",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "git diff --check",
            "git diff --cached --check",
            "git check-ignore -v for v4_1 report.json and status.jsonl",
        ],
        "results_recorded_in_final_response": True,
    }


def build_report(
    *,
    rows: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
    replay: Mapping[str, Any],
    guardrails: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    summary = build_summary(metrics=metrics, artifact_paths=artifact_paths, replay=replay)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "production_routing": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_lift": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "fine_tuning_readiness_only": True,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "live_db_index_cache_readiness": False,
        "single_report_artifact_contract": True,
        "human_review_required": False,
        "review_csv_created": False,
        "artifact_paths": dict(artifact_paths),
        "summary": summary,
        "metrics": dict(metrics),
        "persisted_sourceatom_manifest": list(rows),
        "v3_22_rendering_contract_replay": dict(replay),
        "guardrails": dict(guardrails),
        "guardrail_audit": dict(guardrails),
        "verification": build_verification_section(),
        "changed_files": [
            "ai/scripts/rag_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod.py",
            "ai/tests/test_rag_answer_citation_silver_manifest_v1.py",
            "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py",
            "ai/tests/test_rag_diagnostic_guardrail_git_diff.py",
            "ai/tests/test_rag_diagnostic_status_sync.py",
            "ai/tests/test_rag_current_focused_test_profile_v1.py",
            "docs/rag-ingestion-progress.md",
            "docs/rag-ingestion-measurements.md",
            "docs/rag-ingestion-triage.md",
            "README.md",
            "ai/eval/README.md",
            "ai/eval/reports/rag-ingestion/status.jsonl",
        ],
        "residual_risks": [
            "v4_1 materializes the v3_22 XLSX display contract into a non-production persisted SourceAtom manifest; it does not claim production routing.",
            "The canonical source registry is not mutated by v4_1; wiring the optional display contract into live registry hydration remains a later gated lane.",
            "No official metric input rows, promotion evidence, product-success evidence, or fine-tuning execution are emitted.",
            "GPU inference is not required for this slice because no model, embedding, or index rebuild workload is run.",
        ],
        "next_recommendation": (
            "Proceed to v4_2 XLSX locator v2 table/range/cell structural materialization while preserving the v4_1 "
            "display metadata contract and the SourceAtom/EvidenceBundle evidence-truth boundary."
        ),
    }


def build_artifacts(*, output_dir: Path | None = None) -> dict[str, Any]:
    rows = materialize_persisted_rows()
    replay = build_v3_22_replay()
    metrics = build_metrics(rows, replay)
    guardrails = build_guardrails()
    target_dir = output_dir or OUTPUT_DIR
    artifact_paths = {"report_json": artifact_path_text(target_dir / "report.json")}
    report = build_report(
        rows=rows,
        metrics=metrics,
        replay=replay,
        guardrails=guardrails,
        artifact_paths=artifact_paths,
    )
    return {
        "report": report,
        "metrics": metrics,
        "persisted_sourceatom_manifest": rows,
        "v3_22_rendering_contract_replay": replay,
        "guardrails": guardrails,
    }


def remove_stale_sidecar_artifacts(target_dir: Path) -> None:
    for artifact_name in FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES:
        stale_path = target_dir / artifact_name
        if stale_path.is_file():
            stale_path.unlink()


def write_artifacts(artifacts: Mapping[str, Any], *, output_dir: Path | None = None) -> dict[str, Any]:
    target_dir = output_dir or OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    report_path = target_dir / "report.json"
    report = dict(artifacts["report"])
    report["artifact_paths"] = {"report_json": artifact_path_text(report_path)}
    report["summary"] = dict(report["summary"])
    report["summary"]["artifact_paths"] = dict(report["artifact_paths"])
    report["summary"]["single_report_artifact_contract"] = True
    report["summary"]["sidecar_primary_artifacts_suppressed"] = True
    report["summary"]["review_csv_created"] = False
    report["review_csv_created"] = False
    report["human_review_required"] = False
    report["metrics"] = dict(report["metrics"])
    report["metrics"]["review_csv_created"] = False
    report["metrics"]["human_review_required"] = False
    remove_stale_sidecar_artifacts(target_dir)
    write_json(report_path, report)
    return report


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    v322.replace_marked_entry(path, marker, entry)


def update_current_status_lines() -> None:
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{EVENT_TYPE}_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"(?:current diagnostic v4_1 persisted XLSX SourceAtom display metadata loop:\n`[^`]+`;\n)?"
        r"current diagnostic Phase 1 closure marker:\n`[^`]+`;",
        "current diagnostic v4_1 persisted XLSX SourceAtom display metadata loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic Phase 1 closure marker:\n`phase1_diagnostic_contract_closure_after_v3_22`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")

    readme_text = README.read_text(encoding="utf-8")
    readme_text = re.sub(
        r"Current RAG status: `[^`]+`\.",
        f"Current RAG status: `{EVENT_TYPE}_ready`.",
        readme_text,
        count=1,
    )
    README.write_text(readme_text, encoding="utf-8")

    eval_readme_text = EVAL_README.read_text(encoding="utf-8")
    eval_readme_text = re.sub(
        r"- Current RAG status: `[^`]+`",
        f"- Current RAG status: `{EVENT_TYPE}_ready`",
        eval_readme_text,
        count=1,
    )
    eval_readme_text = eval_readme_text.replace(
        "v4 is opened as `v4_source_grounded_runtime_locator_and_finetune_readiness_opened`.",
        f"v4 is opened as `v4_source_grounded_runtime_locator_and_finetune_readiness_opened`; v4_1 is `{EVENT_TYPE}_ready`.",
    )
    EVAL_README.write_text(eval_readme_text, encoding="utf-8")


def update_docs(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    report_path = report["artifact_paths"]["report_json"]
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v322.v321.v320.v319.refresh_last_updated(doc_path)
    progress_entry = (
        f"- v4_1 persisted XLSX SourceAtom display metadata (`{RUN_ID}`) is {EVENT_TYPE}_ready. "
        "It materializes the v3_22 XLSX display contract into a runtime-adjacent persisted SourceAtom manifest "
        "with raw_value, normalized_value, display_value, number_format, value_type, formula cached value, "
        "format confidence/provenance/drop reason, and merged-cell metadata. The run writes one primary artifact, "
        f"`{report_path}`, and suppresses summary/metrics/per-query/manifest sidecars. SourceAtom/EvidenceBundle "
        "remains evidence truth; SearchView/vector payload remains candidate-only; raw XLSX query-time parsing, "
        "query-time formula evaluation, formula text exposure, direct normalized-value query matching, target/gold "
        "locator use, and expected/supporting gold text use remain forbidden. This is not production routing, not "
        "product success evidence, not promotion evidence, not official metric lift, not live DB/index/cache readiness, "
        "and not fine-tuning execution."
    )
    measurements_entry = f"""### v4_1 Persisted XLSX SourceAtom Display Metadata

- Run: `{RUN_ID}`
- v4 marker: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Policy: diagnostic-only, non-production, single `report.json`; persisted/runtime-adjacent XLSX SourceAtom display metadata only.
- Primary artifact: `{report_path}`

| Diagnostic count | Value |
| --- | ---: |
| persisted_xlsx_sourceatom_display_metadata_rows | {metrics["persisted_xlsx_sourceatom_display_metadata_rows"]} |
| persisted_display_value_available_count | {metrics["persisted_display_value_available_count"]} |
| persisted_raw_value_fallback_count | {metrics["persisted_raw_value_fallback_count"]} |
| formula_cached_value_used_count | {metrics["formula_cached_value_used_count"]} |
| format_confidence_high_count | {metrics["format_confidence_high_count"]} |
| format_confidence_low_count | {metrics["format_confidence_low_count"]} |
| runtime_contract_violation_count | {metrics["runtime_contract_violation_count"]} |
| vector_payload_evidence_truth_violation_count | {metrics["vector_payload_evidence_truth_violation_count"]} |
| raw_xlsx_query_time_parsing_count | {metrics["raw_xlsx_query_time_parsing_count"]} |
| formula_evaluated_at_query_time_count | {metrics["formula_evaluated_at_query_time_count"]} |
| official_metric_input_rows | 0 |
| product_success_evidence_allowed | false |
| promotion_evidence | false |
| fine_tuning_executed | false |
| live_db_index_cache_readiness | false |
| gpu_required_for_this_slice | false |

Counter source-of-truth: `report.json` embeds summary, metrics, persisted_sourceatom_manifest, v3_22_rendering_contract_replay, guardrails, verification, changed_files, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no review CSV or per-run Markdown is created.
"""
    triage_entry = (
        "### v4_1 Persisted XLSX SourceAtom Display Metadata Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract is active.\n"
        "- v4_1 closes the first persisted/runtime-adjacent gap after v3_22: XLSX display metadata now exists as SourceAtom-owned manifest fields instead of only report-local runtime fixture data.\n"
        "- Formula cells carry cached values only; formula text is not exposed and formulas are not evaluated at query time.\n"
        "- Missing display metadata remains explicit low-confidence raw fallback with FORMAT_METADATA_UNAVAILABLE.\n"
        "- SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only.\n"
        "- No raw XLSX query-time parsing, direct normalized-value query matching, target/gold locator use, expected/supporting gold text use, official metric rows, promotion evidence, product-success evidence, production mutation, or fine-tuning execution is allowed.\n"
        "- GPU is not required for this slice because the runner performs deterministic materialization/replay only; future embedding/LLM/index workloads should prefer GPU when available.\n"
        "- Next lane: v4_2 XLSX locator v2 table/range/cell structural materialization.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)
    update_current_status_lines()
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v322.v321.v320.v319.refresh_last_updated(doc_path)


def artifact_sha256_from_report_paths(artifact_paths: Mapping[str, str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path_text in artifact_paths.items():
        path = Path(path_text)
        if not path.is_absolute():
            path = ROOT / path_text
        if path.exists():
            hashes[f"{key}_sha256"] = sha256_file(path)
    return hashes


def append_status_event(report: Mapping[str, Any]) -> None:
    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "generated_at": utc_now(),
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "review_packet_dir": repo_relative(OUTPUT_DIR),
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": artifact_sha256_from_report_paths(report["artifact_paths"]),
        "report_json_created": True,
        "review_csv_created": False,
        "summary_json_created": False,
        "per_run_markdown_created": False,
        "raw_llm_response_payload_created": False,
        "prompt_payload_created": False,
        "persisted_sourceatom_manifest_jsonl_created": False,
        **dict(report["metrics"]),
        **dict(report["guardrails"]),
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def run_write() -> dict[str, Any]:
    artifacts = build_artifacts()
    report = write_artifacts(artifacts)
    update_docs(report)
    append_status_event(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        artifacts = build_artifacts()
        metrics = artifacts["metrics"]
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": artifacts["report"]["summary"]["status"],
                    "persisted_xlsx_sourceatom_display_metadata_rows": metrics[
                        "persisted_xlsx_sourceatom_display_metadata_rows"
                    ],
                    "persisted_display_value_available_count": metrics["persisted_display_value_available_count"],
                    "runtime_contract_violation_count": metrics["runtime_contract_violation_count"],
                    "official_metric_input_rows": metrics["official_metric_input_rows"],
                    "gpu_required_for_this_slice": metrics["gpu_required_for_this_slice"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    report = run_write()
    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "report": report["artifact_paths"]["report_json"],
                "status": report["summary"]["status"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
