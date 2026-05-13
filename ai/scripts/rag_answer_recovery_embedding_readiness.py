"""Report-only embedding readiness for answer recovery diagnostics.

This step prepares embedding backfill work without writing vectors. It inspects
prior safe-recall artifacts, source provenance, and local embedding/index
conventions, then emits a diagnostic manifest for staging-only follow-up.

It never mutates production indexes, opens official answer denominators,
promotes a policy, embeds expected answers or labels, or uses frozen-gold rows
for selection/training.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent
for import_root in (SCRIPT_DIR, AI_WORKER_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import rag_answer_recovery_safe_recall_tuning as safe_recall  # noqa: E402
import rag_answer_recovery_report_artifacts as report_artifacts  # noqa: E402

DEFAULT_CONFIG = AI_WORKER_ROOT / "eval" / "configs" / "answer_recovery_embedding_readiness.yaml"
STAGE_BACKEND_CONTRACT_RECHECK = "answer_recovery_embedding_backend_contract_recheck_v1"
DIAGNOSTIC_BACKEND_PROBE_TEXT = "diagnostic embedding backend contract probe"

TEXT = "TEXT"
XLSX = "XLSX"
PDF_CONTENT = "PDF_CONTENT"
PDF_FILE_LOOKUP = "PDF_FILE_LOOKUP"
OCR_SHADOW = "OCR_SHADOW"
IDP_SHADOW = "IDP_SHADOW"
MULTIMODAL_SHADOW = "MULTIMODAL_SHADOW"
SHADOW_LANES = {OCR_SHADOW, IDP_SHADOW, MULTIMODAL_SHADOW}

TRIAGE_SAFE_EXISTING = "SAFE_RECOVERABLE_WITH_EXISTING_EVIDENCE"
TRIAGE_INDEX_SCOPE_MISSING = "INDEX_SCOPE_MISSING"
TRIAGE_POLICY_BLOCKED = "POLICY_BLOCKED_CORRECTLY"
TRIAGE_GOLD_REQUIRED = "GOLD_POLICY_REQUIRED"
TRIAGE_DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY_DO_NOT_PROMOTE"
TRIAGE_UNKNOWN = "UNKNOWN_NEEDS_MANUAL_REVIEW"

CLASSIFICATION_ORDER = [
    "EMBED_STAGING_PRODUCTION_ELIGIBLE_SOURCE",
    "SKIP_HIDDEN_XLSX",
    "SKIP_DIAGNOSTIC_ONLY_SHADOW",
    "SKIP_PDF_FILE_CONTENT_MIXING_RISK",
    "SKIP_FROZEN_GOLD_DERIVED_EVAL_CONTENT",
    "SKIP_EXPECTED_ANSWER_OR_LABEL",
    "SKIP_SOURCE_NOT_FOUND",
    "SKIP_CANONICAL_LINK_MISSING",
    "SKIP_POLICY_BLOCKED",
    "REVIEW_GOLD_POLICY_REQUIRED",
]

INDEX_SCOPE_CAUSE_ORDER = [
    "source_artifact_exists_but_not_embedded",
    "canonical_source_mapping_absent",
    "indexing_scope_policy",
    "source_is_diagnostic_only",
    "hidden_xlsx",
    "pdf_file_identity_content_ambiguous",
    "unavailable_source_content",
    "gold_policy_required",
]

FORBIDDEN_EMBED_FIELD_HINTS = (
    "expected_answer",
    "gold_label",
    "relevance_label",
    "answerability_label",
    "user_answerability_label",
    "user_relevance_label",
    "label_status",
    "silver_label",
    "official_gold",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = resolve_path(args.config)
    config = report_artifacts.with_reporting_overrides(
        load_config(config_path),
        report_artifacts.reporting_overrides_from_args(args),
    )
    backend_contract_kwargs = {}
    if args.skip_backend_probe:
        backend_contract_kwargs["probe_embedding_allowed_override"] = False
    payload = run_readiness(
        config=config,
        config_path=config_path,
        backend_contract_kwargs=backend_contract_kwargs,
    )
    write_outputs(config, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "manifest_row_count": payload["counts"]["manifest_row_count"],
                "embedding_backend_available": payload["embedding_backend"]["embedding_backend_available"],
                "staging_backfill_status": payload["embedding_backend"]["staging_backfill_status"],
                "production_promotion_ready": payload["decision"]["production_promotion_ready"],
                "official_answer_denominator_ready": payload["decision"]["official_answer_denominator_ready"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument(
        "--skip-backend-probe",
        action="store_true",
        help=(
            "Skip the live diagnostic query-embedding probe. This leaves "
            "embedding_backend_available unknown when construction succeeds; "
            "normal diagnostic runs should not use this."
        ),
    )
    report_artifacts.add_reporting_args(parser)
    return parser.parse_args(argv)


def run_readiness(
    *,
    config: Mapping[str, Any],
    config_path: Path,
    backend_contract_kwargs: Mapping[str, Any] | None = None,
    artifact_overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    validation_errors = validate_config(config)
    if validation_errors:
        raise ValueError("Unsafe embedding readiness config: " + "; ".join(validation_errors))

    artifacts = load_input_artifacts(config, artifact_overrides=artifact_overrides)
    triage_payload = artifacts["missed_row_triage"]["payload"]
    triage_rows = list(triage_payload["rows"])
    expanded_rows = artifacts["answer_sufficiency_expanded_report"]["payload"].get("case_results", [])
    expanded_by_case = {row.get("case_id"): row for row in expanded_rows if row.get("case_id")}
    trace_by_case = artifacts["answer_recovery_expanded_trace"].get("trace_by_case", {})
    excluded_sources = set(config["excluded_frozen_gold_ids"]["source_files"])

    source_records = load_source_records(triage_rows)
    target_chunks = preliminary_target_chunks(triage_rows, source_records, trace_by_case)
    namespace_inventory = discover_namespace_inventory(config)
    source_text_index = scan_allowed_source_texts(
        config,
        target_chunk_ids=sorted(chunk for chunk in target_chunks if chunk),
        namespace_inventory=namespace_inventory,
    )

    manifest_rows = build_manifest_rows(
        triage_rows=triage_rows,
        expanded_by_case=expanded_by_case,
        trace_by_case=trace_by_case,
        source_records=source_records,
        source_text_index=source_text_index,
        excluded_sources=excluded_sources,
        staging_namespace=str(config["embedding_backend"]["staging_namespace"]),
    )
    official_diff = official_registry_diff_proof()
    guardrails = build_guardrail_status(config, manifest_rows, official_diff)
    status = "PASS" if guardrails["all_guardrails_preserved"] else "BLOCKED"

    classification_counts = counts_with_zeros(
        (row["manifest_classification"] for row in manifest_rows),
        CLASSIFICATION_ORDER,
    )
    index_scope_rows = [row for row in manifest_rows if row["triage_category"] == TRIAGE_INDEX_SCOPE_MISSING]
    index_scope_cause_counts = counts_with_zeros(
        (row["index_scope_missing_cause"] for row in index_scope_rows),
        INDEX_SCOPE_CAUSE_ORDER,
    )
    safe_existing_rows = [row for row in manifest_rows if row["triage_category"] == TRIAGE_SAFE_EXISTING]

    namespace_payload = {
        **namespace_inventory,
        "source_text_scan": {
            "target_chunk_id_count": len(target_chunks),
            "found_chunk_id_count": len(source_text_index),
            "missing_chunk_ids": sorted(set(target_chunks) - set(source_text_index)),
        },
    }
    embedding_backend = summarize_embedding_backend(
        config,
        namespace_payload,
        manifest_rows,
        **dict(backend_contract_kwargs or {}),
    )

    return {
        "schema_version": "answer_recovery_embedding_readiness_report_v1",
        "status": status,
        "mode": config["mode"],
        "config_path": repo_relative(config_path),
        "scope": {
            "report_only": True,
            "staging_only": True,
            "production_promotion": False,
            "official_answer_denominator_opening": False,
            "production_index_mutation": False,
            "broad_indexing": False,
            "frozen_gold_selection_or_training": False,
            "expected_answer_or_label_embedding": False,
        },
        "input_artifacts": artifact_summaries(artifacts),
        "embedding_backend": embedding_backend,
        "namespace_inventory": namespace_payload,
        "counts": {
            "manifest_row_count": len(manifest_rows),
            "classification_counts": classification_counts,
            "index_scope_missing_row_count": len(index_scope_rows),
            "index_scope_missing_cause_counts": index_scope_cause_counts,
            "safe_existing_row_count": len(safe_existing_rows),
            "safe_existing_with_stable_canonical_id_count": sum(
                1 for row in safe_existing_rows if row["canonical_source_id"]
            ),
            "safe_existing_source_text_available_count": sum(
                1 for row in safe_existing_rows if row["source_text_available"]
            ),
            "safe_existing_already_embedded_count": sum(1 for row in safe_existing_rows if row["already_embedded"]),
            "safe_existing_staging_backfill_eligible_count": sum(
                1 for row in safe_existing_rows if row["embedding_eligible"]
            ),
            "source_chunks_missing_from_configured_staging_namespace_count": sum(
                1 for row in manifest_rows if row["missing_from_configured_staging_namespace"]
            ),
            "source_chunks_missing_all_detected_embeddings_count": sum(
                1 for row in manifest_rows if row["embedding_eligible"] and not row["already_embedded"]
            ),
            "hidden_xlsx_support_eligible_count": guardrails["hidden_xlsx_support_eligible_count"],
            "diagnostic_only_support_eligible_count": guardrails["diagnostic_only_support_eligible_count"],
            "pdf_file_content_mixing_support_eligible_count": guardrails[
                "pdf_file_content_mixing_support_eligible_count"
            ],
            "expected_answer_or_label_embedding_count": guardrails["expected_answer_or_label_embedding_count"],
        },
        "index_scope_missing_rows": [
            {
                "row_id": row["row_id"],
                "lane": row["lane"],
                "manifest_classification": row["manifest_classification"],
                "index_scope_missing_cause": row["index_scope_missing_cause"],
                "already_embedded": row["already_embedded"],
                "source_text_available": row["source_text_available"],
                "recommended_action": row["recommended_action"],
            }
            for row in index_scope_rows
        ],
        "safe_existing_rows": [
            {
                "row_id": row["row_id"],
                "canonical_source_id": row["canonical_source_id"],
                "chunk_id": row["chunk_id"],
                "already_embedded": row["already_embedded"],
                "existing_embedding_namespaces": row["existing_embedding_namespaces"],
                "embedding_eligible": row["embedding_eligible"],
                "support_eligible": row["support_eligible"],
                "recommended_action": row["recommended_action"],
            }
            for row in safe_existing_rows
        ],
        "guardrail_status": guardrails,
        "official_denominator_registry_diff_proof": official_diff,
        "local_llm_usage": {
            "used": False,
            "reason": "No local LLM was needed; readiness is deterministic provenance/index inspection.",
            "may_decide_answer_correctness": False,
            "may_decide_evidence_support": False,
            "may_decide_answerability": False,
            "may_decide_relevance": False,
            "may_decide_gold_labels": False,
            "may_decide_expected_answers": False,
            "may_decide_expected_evidence": False,
        },
        "optuna_usage": {
            "used": False,
            "reason": config["optuna"]["reason"],
        },
        "decision": {
            "production_promotion_ready": False,
            "official_answer_denominator_ready": False,
            "policy_promoted": False,
            "staging_backfill_performed": False,
            "reason": (
                "Embedding readiness is diagnostic-only. Safe rows with source chunks remain report-only; "
                "no diagnostic/staging namespace was written and no policy was promoted."
            ),
        },
        "manifest_rows": manifest_rows,
    }


def validate_config(config: Mapping[str, Any]) -> list[str]:
    errors: list[str] = report_artifacts.validate_reporting_config(config)
    if config["excluded_frozen_gold_ids"].get("use_for_selection") is not False:
        errors.append("frozen gold use_for_selection must remain false")
    if config["excluded_frozen_gold_ids"].get("use_for_training") is not False:
        errors.append("frozen gold use_for_training must remain false")
    backend = config["embedding_backend"]
    namespace = str(backend.get("staging_namespace", ""))
    if not namespace_is_safe(namespace, backend["namespace_safety"]):
        errors.append(f"unsafe staging namespace: {namespace}")
    if bool(backend.get("perform_staging_backfill")):
        errors.append("perform_staging_backfill must remain false for this report-only step")
    source_inspection = config["source_artifact_inspection"]
    if source_inspection.get("allow_eval_artifact_text_as_embedding_source") is not False:
        errors.append("eval artifact text must not be treated as embedding source")
    guardrails = config["guardrail_assertions"]
    if guardrails.get("production_promotion_ready") is not False:
        errors.append("production promotion must remain false")
    if guardrails.get("official_answer_denominator_ready") is not False:
        errors.append("official answer denominator readiness must remain false")
    if guardrails.get("pdf_file_lookup_semantics") != "file_identity_only":
        errors.append("PDF FILE lookup must remain file identity only")
    for classification in CLASSIFICATION_ORDER:
        if classification not in config["manifest_classifications"]:
            errors.append(f"missing manifest classification {classification}")
    return errors


def load_input_artifacts(
    config: Mapping[str, Any],
    artifact_overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    for name, raw_path in config["inputs"].items():
        path = resolve_path(raw_path)
        entry: dict[str, Any] = {"path": repo_relative(path), "exists": path.exists(), "bytes": 0}
        if not path.exists():
            artifacts[name] = entry
            continue
        entry["bytes"] = path.stat().st_size
        if path.suffix == ".json":
            entry["payload"] = read_json(path)
        elif path.suffix == ".csv":
            entry["rows"] = read_csv(path)
        elif path.suffix == ".jsonl":
            rows = read_jsonl(path)
            entry["line_count"] = len(rows)
            entry["trace_by_case"] = {row.get("case_id"): row for row in rows if row.get("case_id")}
        elif path.suffix == ".md":
            entry["line_count"] = len(path.read_text(encoding="utf-8").splitlines())
        artifacts[name] = entry
    for name, override in (artifact_overrides or {}).items():
        raw_path = config.get("inputs", {}).get(name, name)
        path = resolve_path(raw_path)
        entry = {"path": repo_relative(path), "exists": True, "bytes": 0}
        entry.update(dict(override))
        artifacts[name] = entry

    required = ("missed_row_triage", "answer_recovery_expanded_trace", "answer_sufficiency_expanded_report")
    missing = [name for name in required if not artifacts.get(name, {}).get("exists")]
    if missing:
        raise FileNotFoundError(f"Missing required embedding-readiness inputs: {', '.join(missing)}")
    return artifacts


def load_source_records(triage_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    by_artifact: dict[str, list[dict[str, str]]] = {}
    records: dict[str, dict[str, str]] = {}
    for row in triage_rows:
        source = str(row.get("source_artifact") or "")
        if not source or not source.endswith(".csv"):
            continue
        if source not in by_artifact:
            path = resolve_path(source)
            by_artifact[source] = read_csv(path) if path.exists() else []
        match = match_source_record(row, by_artifact[source])
        if match:
            records[str(row["row_id"])] = match
    return records


def match_source_record(row: Mapping[str, Any], records: Sequence[Mapping[str, str]]) -> dict[str, str] | None:
    row_id = str(row.get("row_id") or "")
    suffix = row_number_suffix(row_id)
    if not suffix:
        return None
    four = suffix.zfill(4)
    lane = row.get("lane")
    preferred_prefixes: list[str] = []
    if lane == TEXT:
        preferred_prefixes.append("silver_text_pos_")
    elif lane == PDF_CONTENT:
        preferred_prefixes.append("supp_")
    elif lane == PDF_FILE_LOOKUP:
        preferred_prefixes.extend(["silver_pdf_file_hneg_v2_", "pdf_file_lookup_"])

    for prefix in preferred_prefixes:
        for record in records:
            query_id = str(record.get("query_id") or "")
            if query_id == f"{prefix}{four}" or query_id.endswith(f"_{four}"):
                return dict(record)
    for record in records:
        query_id = str(record.get("query_id") or "")
        if query_id.endswith(f"_{four}"):
            return dict(record)
    return None


def preliminary_target_chunks(
    triage_rows: Sequence[Mapping[str, Any]],
    source_records: Mapping[str, Mapping[str, str]],
    trace_by_case: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    chunks: set[str] = set()
    for row in triage_rows:
        row_id = str(row["row_id"])
        record = source_records.get(row_id, {})
        chunks.update(chunk_ids_from_record(record))
        chunks.update(retrieved_chunk_ids(trace_by_case.get(row_id, {})))
    return {chunk for chunk in chunks if chunk and not chunk.startswith("recovered_chunk_")}


def discover_namespace_inventory(config: Mapping[str, Any]) -> dict[str, Any]:
    backend = config["embedding_backend"]
    index_root = resolve_path(backend["index_root"])
    namespace = str(backend["staging_namespace"])
    namespace_entries: list[dict[str, Any]] = []
    if index_root.exists():
        for child in sorted(index_root.iterdir(), key=lambda path: path.name):
            if not child.is_dir():
                continue
            entry = namespace_entry(child, namespace)
            namespace_entries.append(entry)

    provider_files = [resolve_path(path) for path in backend.get("provider_config_files", [])]
    vector_files = [resolve_path(path) for path in backend.get("vector_index_files", [])]
    staging_path = index_root / namespace
    return {
        "embedding_backend_config_detected": all(path.exists() for path in provider_files),
        "embedding_provider_config_files": [repo_relative(path) for path in provider_files],
        "vector_index_config_detected": all(path.exists() for path in vector_files),
        "vector_index_config_files": [repo_relative(path) for path in vector_files],
        "index_root": repo_relative(index_root),
        "index_root_exists": index_root.exists(),
        "existing_namespace_count": len(namespace_entries),
        "namespaces": namespace_entries,
        "staging_namespace": namespace,
        "staging_namespace_path": repo_relative(staging_path),
        "staging_namespace_safe": namespace_is_safe(namespace, backend["namespace_safety"]),
        "staging_namespace_exists": staging_path.exists(),
        "production_namespace_used": False,
        "production_index_mutation": False,
    }


def namespace_entry(path: Path, configured_staging_namespace: str) -> dict[str, Any]:
    build_path = path / "build.json"
    ingest_path = path / "ingest_manifest.json"
    build_payload = read_json(build_path) if build_path.exists() else {}
    ingest_payload = read_json(ingest_path) if ingest_path.exists() else {}
    return {
        "namespace": path.name,
        "path": repo_relative(path),
        "has_build_json": build_path.exists(),
        "has_faiss_index": (path / "faiss.index").exists(),
        "has_ingest_manifest": ingest_path.exists(),
        "has_chunks_jsonl": (path / "chunks.jsonl").exists(),
        "is_configured_staging_namespace": path.name == configured_staging_namespace,
        "production_like_local_index": namespace_looks_production_like(path.name),
        "index_version": build_payload.get("index_version") or ingest_payload.get("index_version", ""),
        "embedding_model": build_payload.get("embedding_model") or ingest_payload.get("embedding_model", ""),
        "dimension": build_payload.get("dimension") or ingest_payload.get("dimension", 0),
        "chunk_count": build_payload.get("chunk_count") or ingest_payload.get("chunk_count", 0),
        "embedding_text_variant": ingest_payload.get("embedding_text_variant", ""),
        "corpus_path": ingest_payload.get("corpus_path", ""),
    }


def namespace_is_safe(namespace: str, policy: Mapping[str, Any]) -> bool:
    lowered = namespace.lower()
    if any(marker in lowered for marker in policy.get("forbidden_markers", [])):
        return False
    if any(lowered.startswith(prefix) for prefix in policy.get("required_prefixes", [])):
        return True
    return any(marker in lowered for marker in policy.get("allowed_markers", []))


def namespace_looks_production_like(namespace: str) -> bool:
    lowered = namespace.lower()
    if any(marker in lowered for marker in ("diagnostic", "staging", "canary")):
        return False
    return True


def scan_allowed_source_texts(
    config: Mapping[str, Any],
    *,
    target_chunk_ids: Sequence[str],
    namespace_inventory: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    targets = set(target_chunk_ids)
    if not targets:
        return {}
    found: dict[str, dict[str, Any]] = {}
    namespace_by_chunks_file = {
        repo_relative(resolve_path(path)): entry["namespace"]
        for entry in namespace_inventory.get("namespaces", [])
        for path in [Path(entry["path"]) / "chunks.jsonl"]
    }
    for raw_path in config["source_artifact_inspection"].get("allowed_source_text_files", []):
        path = resolve_path(raw_path)
        if not path.exists():
            continue
        namespace = namespace_by_chunks_file.get(repo_relative(path), path.parent.name)
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                chunk_id = str(row.get("chunk_id") or "")
                if chunk_id not in targets:
                    continue
                text = str(row.get("text") or "")
                found[chunk_id] = {
                    "chunk_id": chunk_id,
                    "doc_id": str(row.get("doc_id") or ""),
                    "section": str(row.get("section") or ""),
                    "text_length": len(text),
                    "text_hash": sha256_text(text),
                    "faiss_row_id": row.get("faiss_row_id"),
                    "source_text_file": repo_relative(path),
                    "embedding_namespace": namespace,
                }
                if targets.issubset(found.keys()):
                    return found
    return found


def build_manifest_rows(
    *,
    triage_rows: Sequence[Mapping[str, Any]],
    expanded_by_case: Mapping[str, Mapping[str, Any]],
    trace_by_case: Mapping[str, Mapping[str, Any]],
    source_records: Mapping[str, Mapping[str, str]],
    source_text_index: Mapping[str, Mapping[str, Any]],
    excluded_sources: set[str],
    staging_namespace: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for triage in triage_rows:
        row_id = str(triage["row_id"])
        expanded = expanded_by_case.get(row_id, {})
        trace = trace_by_case.get(row_id, {})
        record = source_records.get(row_id, {})
        metadata = source_metadata(triage, expanded, trace, record)
        chunk_lookup = source_text_index.get(metadata["chunk_id"], {})
        derived = derive_manifest_classification(
            triage=triage,
            expanded=expanded,
            source_record=record,
            metadata=metadata,
            chunk_lookup=chunk_lookup,
            excluded_sources=excluded_sources,
        )
        existing_namespaces = [chunk_lookup["embedding_namespace"]] if chunk_lookup.get("embedding_namespace") else []
        embedding_eligible = derived["classification"] == "EMBED_STAGING_PRODUCTION_ELIGIBLE_SOURCE"
        support_eligible = embedding_eligible and bool(triage.get("evidence_is_production_safe"))
        source_text_available = bool(chunk_lookup)
        already_embedded = bool(existing_namespaces)
        row = {
            "manifest_id": manifest_id(row_id, metadata["canonical_source_id"], metadata["chunk_id"]),
            "row_id": row_id,
            "stable_query_id": str(triage.get("stable_query_id") or row_id),
            "source_artifact_id": metadata["source_artifact_id"],
            "canonical_source_id": metadata["canonical_source_id"],
            "source_type": metadata["source_type"],
            "lane": triage.get("lane", ""),
            "before_status": triage.get("before_status", ""),
            "after_status": triage.get("after_status", ""),
            "selected_variant": triage.get("selected_variant", ""),
            "triage_category": triage.get("category", ""),
            "recovery_or_block_reason": triage.get("recovery_or_block_reason", ""),
            "evidence_source_type": triage.get("evidence_source_type", ""),
            "page_number": metadata["page_number"],
            "sheet_name": metadata["sheet_name"],
            "table_name": metadata["table_name"],
            "row_metadata": metadata["row_metadata"],
            "column_metadata": metadata["column_metadata"],
            "chunk_id": metadata["chunk_id"],
            "chunk_hash": chunk_lookup.get("text_hash") or metadata["chunk_hash"],
            "chunk_text_length": int(chunk_lookup.get("text_length") or 0),
            "source_text_available": source_text_available,
            "already_embedded": already_embedded,
            "existing_embedding_namespaces": existing_namespaces,
            "configured_staging_namespace": staging_namespace,
            "missing_from_configured_staging_namespace": embedding_eligible,
            "embedding_eligible": embedding_eligible,
            "support_eligible": support_eligible,
            "diagnostic_only": derived["diagnostic_only"],
            "hidden_xlsx": bool(triage.get("hidden_xlsx_involved")),
            "pdf_file_identity_only": triage.get("lane") == PDF_FILE_LOOKUP,
            "pdf_file_content_mixing_risk": bool(triage.get("pdf_file_identity_content_mixing_risk")),
            "native_pdf_text_available": bool(triage.get("native_pdf_text_available")),
            "ocr_fallback": bool(triage.get("ocr_fallback_involved")),
            "frozen_gold_sourced_row": derived["frozen_gold_sourced_row"],
            "selection_or_training_eligible": False,
            "selection_or_training_eligible_reason": "report_only_step_no_selection_or_training",
            "contains_expected_answer_or_label_content": derived["contains_expected_answer_or_label_content"],
            "expected_answer_or_label_embedded": False,
            "manifest_classification": derived["classification"],
            "skip_reason": derived["skip_reason"],
            "index_scope_missing_cause": derived["index_scope_missing_cause"],
            "recommended_action": recommended_action(
                classification=derived["classification"],
                triage=triage,
                metadata=metadata,
                source_text_available=source_text_available,
                already_embedded=already_embedded,
            ),
        }
        rows.append(row)
    return sorted(rows, key=lambda item: (item["lane"], item["row_id"]))


def source_metadata(
    triage: Mapping[str, Any],
    expanded: Mapping[str, Any],
    trace: Mapping[str, Any],
    record: Mapping[str, str],
) -> dict[str, Any]:
    lane = str(triage.get("lane") or "")
    record_query_id = str(record.get("query_id") or "")
    source_artifact_id = record_query_id or str(triage.get("source_artifact") or triage.get("row_id") or "")
    record_chunks = chunk_ids_from_record(record)
    trace_chunks = retrieved_chunk_ids(trace)
    chunk_id = next((chunk for chunk in record_chunks if chunk), "")
    if not chunk_id:
        chunk_id = next((chunk for chunk in trace_chunks if chunk and not chunk.startswith("recovered_chunk_")), "")
    page_number = page_number_from_record(record) or page_number_from_row_id(str(triage.get("row_id") or ""))
    canonical_source_id = canonical_source_id_for_row(triage, record, chunk_id, page_number)
    if not chunk_id and canonical_source_id:
        chunk_id = stable_pseudo_chunk_id(canonical_source_id)
    return {
        "source_artifact_id": source_artifact_id,
        "canonical_source_id": canonical_source_id,
        "source_type": source_type_for_row(triage, expanded, record),
        "page_number": page_number,
        "sheet_name": str(record.get("sheet") or record.get("sheet_name") or ""),
        "table_name": str(record.get("table") or record.get("table_name") or ""),
        "row_metadata": str(record.get("row") or record.get("row_metadata") or record.get("range") or ""),
        "column_metadata": str(record.get("column") or record.get("column_metadata") or ""),
        "chunk_id": chunk_id,
        "chunk_hash": sha256_text(canonical_source_id or chunk_id or str(triage.get("row_id") or "")),
        "lane": lane,
    }


def canonical_source_id_for_row(
    triage: Mapping[str, Any],
    record: Mapping[str, str],
    chunk_id: str,
    page_number: int | None,
) -> str:
    lane = str(triage.get("lane") or "")
    if chunk_id and record.get("expected_document_ids"):
        return f"doc:{record['expected_document_ids']}:chunk:{chunk_id}"
    if chunk_id:
        return f"chunk:{chunk_id}"
    if lane == PDF_CONTENT:
        citation = parse_jsonish(record.get("citation", ""))
        relative_path = str(record.get("relative_path") or citation.get("relative_path") or "")
        bbox = str(citation.get("bbox") or "")
        if relative_path and page_number is not None:
            bbox_hash = sha256_text(bbox)[:12] if bbox else "no-bbox"
            return f"pdf:{relative_path}:page:{page_number}:bbox:{bbox_hash}"
    if lane == PDF_FILE_LOOKUP:
        file_name = str(record.get("expected_file_name") or record.get("source_file_name") or "")
        if file_name:
            return f"pdf-file-identity:{file_name}"
    if lane == XLSX:
        sheet = str(record.get("sheet") or record.get("sheet_name") or "")
        range_value = str(record.get("range") or record.get("cell_range") or "")
        if sheet or range_value:
            return f"xlsx:{sheet}:{range_value}"
    return ""


def source_type_for_row(
    triage: Mapping[str, Any],
    expanded: Mapping[str, Any],
    record: Mapping[str, str],
) -> str:
    del expanded
    lane = triage.get("lane")
    if lane == TEXT:
        return "TEXT_NATIVE"
    if lane == XLSX:
        return "XLSX_HIDDEN_BLOCKED" if triage.get("hidden_xlsx_involved") else "XLSX_STRICT_WRAPPER"
    if lane == PDF_CONTENT:
        return "PDF_NATIVE_TEXT" if triage.get("native_pdf_text_available") else "PDF_CONTENT"
    if lane == PDF_FILE_LOOKUP:
        return "PDF_FILE_IDENTITY"
    if lane == OCR_SHADOW:
        return "OCR_FALLBACK_DIAGNOSTIC"
    if lane == IDP_SHADOW:
        return "IDP_DIAGNOSTIC"
    if lane == MULTIMODAL_SHADOW:
        return "MULTIMODAL_DIAGNOSTIC"
    if record:
        return "EVAL_SOURCE_RECORD"
    return "UNKNOWN"


def derive_manifest_classification(
    *,
    triage: Mapping[str, Any],
    expanded: Mapping[str, Any],
    source_record: Mapping[str, str],
    metadata: Mapping[str, Any],
    chunk_lookup: Mapping[str, Any],
    excluded_sources: set[str],
) -> dict[str, Any]:
    del expanded
    source_artifact = str(triage.get("source_artifact") or "")
    category = str(triage.get("category") or "")
    diagnostic_only = bool(triage.get("evidence_is_diagnostic_only")) or source_record_is_diagnostic(source_record)
    frozen = source_artifact in excluded_sources
    contains_forbidden_content = contains_forbidden_embed_content(source_record)
    index_scope_cause = ""

    if bool(triage.get("hidden_xlsx_involved")):
        classification = "SKIP_HIDDEN_XLSX"
        reason = "hidden_xlsx_content_blocked"
    elif diagnostic_only:
        classification = "SKIP_DIAGNOSTIC_ONLY_SHADOW"
        reason = "diagnostic_only_evidence_blocked"
    elif bool(triage.get("pdf_file_identity_content_mixing_risk")):
        classification = "SKIP_PDF_FILE_CONTENT_MIXING_RISK"
        reason = "pdf_file_lookup_content_mixing_or_lane_mismatch"
    elif frozen:
        classification = "SKIP_FROZEN_GOLD_DERIVED_EVAL_CONTENT"
        reason = "frozen_gold_sourced_row_excluded_from_selection_and_training"
    elif contains_forbidden_content and not chunk_lookup:
        classification = "SKIP_EXPECTED_ANSWER_OR_LABEL"
        reason = "source_record_contains_expected_answer_or_label_fields_not_embedding_source"
    elif category == TRIAGE_GOLD_REQUIRED:
        classification = "REVIEW_GOLD_POLICY_REQUIRED"
        reason = "human_gold_policy_required_before_embedding_or_support"
    elif category == TRIAGE_POLICY_BLOCKED or category == TRIAGE_UNKNOWN:
        classification = "SKIP_POLICY_BLOCKED"
        reason = "current_policy_blocks_support_or_requires_manual_review"
    elif category == TRIAGE_INDEX_SCOPE_MISSING and not bool(triage.get("evidence_is_production_safe")):
        classification = "SKIP_POLICY_BLOCKED"
        reason = "current_diagnostic_row_is_not_support_eligible_even_if_source_chunk_exists"
    elif not metadata.get("canonical_source_id"):
        classification = "SKIP_CANONICAL_LINK_MISSING"
        reason = "canonical_source_mapping_absent"
    elif not chunk_lookup:
        classification = "SKIP_SOURCE_NOT_FOUND"
        reason = "canonical_source_text_not_found_in_allowed_source_artifacts"
    else:
        classification = "EMBED_STAGING_PRODUCTION_ELIGIBLE_SOURCE"
        reason = "production_eligible_source_chunk_found_for_staging_manifest"

    if category == TRIAGE_INDEX_SCOPE_MISSING:
        index_scope_cause = index_scope_missing_cause(
            triage=triage,
            source_record=source_record,
            metadata=metadata,
            chunk_lookup=chunk_lookup,
            classification=classification,
        )

    return {
        "classification": classification,
        "skip_reason": "" if classification == "EMBED_STAGING_PRODUCTION_ELIGIBLE_SOURCE" else reason,
        "diagnostic_only": diagnostic_only,
        "frozen_gold_sourced_row": frozen,
        "contains_expected_answer_or_label_content": contains_forbidden_content,
        "index_scope_missing_cause": index_scope_cause,
    }


def index_scope_missing_cause(
    *,
    triage: Mapping[str, Any],
    source_record: Mapping[str, str],
    metadata: Mapping[str, Any],
    chunk_lookup: Mapping[str, Any],
    classification: str,
) -> str:
    if bool(triage.get("hidden_xlsx_involved")):
        return "hidden_xlsx"
    if bool(triage.get("pdf_file_identity_content_mixing_risk")):
        return "pdf_file_identity_content_ambiguous"
    if source_record_is_diagnostic(source_record) or classification == "SKIP_DIAGNOSTIC_ONLY_SHADOW":
        return "source_is_diagnostic_only"
    if triage.get("human_gold_decision_required"):
        return "gold_policy_required"
    if not metadata.get("canonical_source_id"):
        return "canonical_source_mapping_absent"
    if not chunk_lookup:
        return "unavailable_source_content"
    if classification == "EMBED_STAGING_PRODUCTION_ELIGIBLE_SOURCE":
        return "source_artifact_exists_but_not_embedded"
    return "indexing_scope_policy"


def recommended_action(
    *,
    classification: str,
    triage: Mapping[str, Any],
    metadata: Mapping[str, Any],
    source_text_available: bool,
    already_embedded: bool,
) -> str:
    if classification == "EMBED_STAGING_PRODUCTION_ELIGIBLE_SOURCE":
        if already_embedded:
            return (
                "Source chunk is already present in a local embedded source index; keep report-only and "
                "backfill only to a diagnostic namespace if a future staging run is explicitly enabled."
            )
        return "Backfill only to the diagnostic namespace after source text and backend availability are rechecked."
    if classification == "SKIP_HIDDEN_XLSX":
        return "Keep hidden XLSX content out of query, candidate, gold, answer, and support-eligible embedding surfaces."
    if classification == "SKIP_DIAGNOSTIC_ONLY_SHADOW":
        return "Keep OCR/IDP/multimodal or diagnostic-only source evidence out of support-eligible namespaces."
    if classification == "SKIP_PDF_FILE_CONTENT_MIXING_RISK":
        return "Keep PDF FILE lookup file-identity-only; do not embed or support content/page/bbox/table/row/column claims."
    if classification == "SKIP_FROZEN_GOLD_DERIVED_EVAL_CONTENT":
        return "Exclude frozen-gold-sourced rows from selection, training, and embedding backfill decisions."
    if classification == "SKIP_EXPECTED_ANSWER_OR_LABEL":
        return "Use only independent source artifacts; never embed expected answers, labels, or eval-only evidence text."
    if classification == "SKIP_CANONICAL_LINK_MISSING":
        return "Resolve canonical source mapping before considering any staging embedding work."
    if classification == "SKIP_SOURCE_NOT_FOUND":
        if source_text_available:
            return "Review source/index scope; source text was detected but current policy does not permit support."
        return "Materialize canonical source text from a production-eligible artifact before any staging backfill."
    if classification == "REVIEW_GOLD_POLICY_REQUIRED":
        return "Defer to a human gold policy decision; do not infer answerability, relevance, expected answer, or evidence."
    if triage.get("lane") == PDF_FILE_LOOKUP:
        return "Keep PDF FILE lookup exact/canonical file identity only."
    if metadata.get("lane") == XLSX:
        return "Keep XLSX strict-wrapper policy and hidden-content blocking."
    return "Keep blocked under current diagnostic policy; do not promote or embed as support."


def run_backend_contract_recheck(
    *,
    config: Mapping[str, Any],
    namespace_payload: Mapping[str, Any] | None = None,
    settings_factory: Callable[[], Any] | None = None,
    provider_importer: Callable[[], tuple[Any, Callable[[Any], Any]]] | None = None,
    vector_importer: Callable[[], Any] | None = None,
    embedder_factory: Callable[..., Any] | None = None,
    env: Mapping[str, str] | None = None,
    probe_embedding_allowed_override: bool | None = None,
) -> dict[str, Any]:
    """Probe the canonical RAG embedding backend without writing vectors."""
    if namespace_payload is None:
        namespace_payload = discover_namespace_inventory(config)

    backend = config["embedding_backend"]
    env_map = os.environ if env is None else env
    required_env_vars = list(backend.get("required_env_vars") or [])
    env_presence_vars = list(backend.get("env_presence_vars") or default_backend_env_presence_vars())
    env_names = sorted(dict.fromkeys([*required_env_vars, *env_presence_vars]))
    env_presence = [
        {
            "name": name,
            "required": name in required_env_vars,
            "present": bool(str(env_map.get(name, "")).strip()),
        }
        for name in env_names
    ]
    missing_required_env = [
        entry["name"]
        for entry in env_presence
        if entry["required"] and not entry["present"]
    ]
    probe_allowed = bool(backend.get("allow_backend_probe_embedding", True))
    if probe_embedding_allowed_override is not None:
        probe_allowed = bool(probe_embedding_allowed_override)

    result: dict[str, Any] = {
        "stage": STAGE_BACKEND_CONTRACT_RECHECK,
        "backend_config_detected": bool(namespace_payload.get("embedding_backend_config_detected")),
        "backend_config_load_succeeded": False,
        "backend_provider_importable": False,
        "backend_provider_constructible": False,
        "backend_required_env_present": not missing_required_env,
        "backend_probe_embedding_allowed": probe_allowed,
        "backend_probe_embedding_succeeded": False,
        "backend_embedding_dimension_detected": None,
        "backend_contract_status": "not_run",
        "backend_availability_reason": "",
        "backend_unavailable_reason": "",
        "backend_indeterminate_reason": "",
        "required_env_vars": required_env_vars,
        "missing_required_env_vars": missing_required_env,
        "env_presence": env_presence,
        "backend_probe_text": DIAGNOSTIC_BACKEND_PROBE_TEXT,
        "backend_probe_text_source": "synthetic_constant_non_eval",
        "backend_probe_text_policy": {
            "derived_from_expected_answers": False,
            "derived_from_labels": False,
            "derived_from_eval_evidence_text": False,
        },
        "vector_index_reader_available": False,
        "vector_index_writer_available": False,
        "vector_index_importable": False,
        "existing_vector_indexes_detected": existing_vector_indexes_detected(namespace_payload),
        "staging_namespace_exists": bool(namespace_payload.get("staging_namespace_exists")),
        "staging_namespace_safe": bool(namespace_payload.get("staging_namespace_safe")),
        "vector_write_attempted": False,
        "namespace_created": False,
        "production_mutation": False,
        "production_index_mutation": False,
        "official_denominator_opened": False,
        "official_answer_denominator_opened": False,
    }

    false_reasons: list[str] = []
    indeterminate_reasons: list[str] = []
    if not result["backend_config_detected"]:
        false_reasons.append("backend config/provider files were not all detected")

    settings = None
    if result["backend_config_detected"]:
        try:
            settings = settings_factory() if settings_factory is not None else load_worker_settings()
            result["backend_config_load_succeeded"] = True
            result["settings_summary"] = settings_backend_summary(settings)
        except Exception as exc:  # noqa: BLE001 - diagnostic report must capture exact root cause
            false_reasons.append(f"config load failure: {safe_error(exc)}")

    if missing_required_env:
        false_reasons.append("missing required env var(s): " + ", ".join(missing_required_env))

    model_name = str(getattr(settings, "rag_embedding_model", "") or "").strip() if settings is not None else ""
    if settings is not None and not model_name:
        false_reasons.append("configured rag_embedding_model is empty")
        result["backend_required_env_present"] = False

    provider_class = None
    resolve_max_seq_length_fn: Callable[[Any], Any] | None = None
    try:
        provider_class, resolve_max_seq_length_fn = (
            provider_importer() if provider_importer is not None else import_embedding_provider()
        )
        result["backend_provider_importable"] = True
    except Exception as exc:  # noqa: BLE001 - import failures are first-class readiness facts
        false_reasons.append(f"provider import failure: {safe_error(exc)}")

    try:
        vector_class = vector_importer() if vector_importer is not None else import_vector_index_provider()
        result["vector_index_importable"] = True
        result["vector_index_reader_available"] = all(
            hasattr(vector_class, attr) for attr in ("load", "search")
        )
        result["vector_index_writer_available"] = all(
            hasattr(vector_class, attr) for attr in ("build", "build_staged", "promote_staged")
        )
    except Exception as exc:  # noqa: BLE001 - vector import/read/write facts are diagnostic output
        false_reasons.append(f"vector index import failure: {safe_error(exc)}")

    embedder = None
    if (
        settings is not None
        and result["backend_provider_importable"]
        and result["backend_required_env_present"]
        and provider_class is not None
        and resolve_max_seq_length_fn is not None
    ):
        try:
            if embedder_factory is not None:
                embedder = embedder_factory(
                    settings=settings,
                    provider_class=provider_class,
                    resolve_max_seq_length=resolve_max_seq_length_fn,
                )
            else:
                embedder = construct_canonical_embedder(
                    settings=settings,
                    provider_class=provider_class,
                    resolve_max_seq_length=resolve_max_seq_length_fn,
                )
            result["backend_provider_constructible"] = True
        except Exception as exc:  # noqa: BLE001 - construction failures are the contract result
            false_reasons.append(f"provider construction failure: {safe_error(exc)}")

    if result["backend_provider_constructible"] and embedder is not None:
        if probe_allowed:
            try:
                vectors = embedder.embed_queries([DIAGNOSTIC_BACKEND_PROBE_TEXT])
                dimension = detect_embedding_dimension(embedder, vectors)
                if dimension is None:
                    false_reasons.append("probe embedding returned no detectable dimension")
                else:
                    result["backend_probe_embedding_succeeded"] = True
                    result["backend_embedding_dimension_detected"] = dimension
            except Exception as exc:  # noqa: BLE001 - probe failures are the contract result
                false_reasons.append(f"probe embedding failure: {safe_error(exc)}")
        else:
            indeterminate_reasons.append("diagnostic embedding probe disabled by config or CLI override")

    if false_reasons:
        result["embedding_backend_available"] = False
        result["backend_contract_status"] = "unavailable"
        result["backend_unavailable_reason"] = "; ".join(false_reasons)
        result["backend_availability_reason"] = result["backend_unavailable_reason"]
    elif indeterminate_reasons:
        result["embedding_backend_available"] = "unknown"
        result["backend_contract_status"] = "indeterminate"
        result["backend_indeterminate_reason"] = "; ".join(indeterminate_reasons)
        result["backend_availability_reason"] = result["backend_indeterminate_reason"]
    else:
        result["embedding_backend_available"] = True
        result["backend_contract_status"] = "available"
        result["backend_availability_reason"] = (
            "canonical SentenceTransformerEmbedder constructed and produced one synthetic diagnostic query embedding"
        )

    return result


def summarize_embedding_backend(
    config: Mapping[str, Any],
    namespace_payload: Mapping[str, Any],
    manifest_rows: Sequence[Mapping[str, Any]],
    **backend_contract_kwargs: Any,
) -> dict[str, Any]:
    del manifest_rows
    backend = config["embedding_backend"]
    contract = run_backend_contract_recheck(
        config=config,
        namespace_payload=namespace_payload,
        **backend_contract_kwargs,
    )
    backfill = determine_staging_backfill_status(backend, namespace_payload, contract)
    return {
        **contract,
        "embedding_backend_config_detected": contract["backend_config_detected"],
        "vector_index_config_detected": bool(namespace_payload["vector_index_config_detected"]),
        "staging_namespace": namespace_payload["staging_namespace"],
        "staging_namespace_path": namespace_payload["staging_namespace_path"],
        "staging_namespace_required_for_backfill": bool(backend.get("require_existing_staging_namespace_for_backfill")),
        "perform_staging_backfill": bool(backend.get("perform_staging_backfill")),
        "staging_backfill_enabled_by_config": bool(backend.get("perform_staging_backfill")),
        "staging_backfill_status": backfill["staging_backfill_status"],
        "staging_backfill_skip_reason": backfill["staging_backfill_skip_reason"],
        "staging_backfill_performed": False,
        "vector_write_allowed": bool(backend.get("allow_vector_write", False)),
        "production_namespace_used": False,
        "production_index_mutation": False,
        "skip_reason": backfill["staging_backfill_skip_reason"],
    }


def determine_staging_backfill_status(
    backend: Mapping[str, Any],
    namespace_payload: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, str]:
    perform_backfill = bool(backend.get("perform_staging_backfill"))
    require_namespace = bool(backend.get("require_existing_staging_namespace_for_backfill"))
    staging_exists = bool(namespace_payload.get("staging_namespace_exists"))
    safe_namespace = bool(namespace_payload.get("staging_namespace_safe"))
    vector_write_allowed = bool(backend.get("allow_vector_write", False))
    backend_available = contract.get("embedding_backend_available")

    if not perform_backfill:
        return {
            "staging_backfill_status": "skipped_backfill_disabled_by_config",
            "staging_backfill_skip_reason": "perform_staging_backfill is false; backend availability is reported separately",
        }
    if contract.get("backend_required_env_present") is False:
        return {
            "staging_backfill_status": "skipped_missing_required_env",
            "staging_backfill_skip_reason": str(contract.get("backend_unavailable_reason") or "required env var is missing"),
        }
    if backend_available is False:
        return {
            "staging_backfill_status": "skipped_backend_unavailable",
            "staging_backfill_skip_reason": str(contract.get("backend_unavailable_reason") or "embedding backend unavailable"),
        }
    if backend_available == "unknown":
        return {
            "staging_backfill_status": "skipped_backend_unavailable",
            "staging_backfill_skip_reason": str(
                contract.get("backend_indeterminate_reason") or "embedding backend availability is unknown"
            ),
        }
    if require_namespace and not staging_exists:
        return {
            "staging_backfill_status": "skipped_staging_namespace_missing",
            "staging_backfill_skip_reason": "configured diagnostic staging namespace does not exist",
        }
    if not safe_namespace:
        return {
            "staging_backfill_status": "skipped_namespace_not_safe",
            "staging_backfill_skip_reason": "configured staging namespace failed diagnostic namespace safety policy",
        }
    if not vector_write_allowed:
        return {
            "staging_backfill_status": "skipped_write_not_allowed",
            "staging_backfill_skip_reason": "vector writes are disabled for this diagnostic runner",
        }
    return {
        "staging_backfill_status": "failed",
        "staging_backfill_skip_reason": "report-only runner does not execute staging backfill writes",
    }


def default_backend_env_presence_vars() -> list[str]:
    return [
        "AIPIPELINE_WORKER_RAG_EMBEDDING_MODEL",
        "AIPIPELINE_WORKER_RAG_EMBEDDING_PREFIX_QUERY",
        "AIPIPELINE_WORKER_RAG_EMBEDDING_PREFIX_PASSAGE",
        "AIPIPELINE_WORKER_RAG_EMBEDDING_MAX_SEQ_LENGTH",
        "AIPIPELINE_WORKER_RAG_EMBEDDING_BATCH_SIZE",
        "AIPIPELINE_WORKER_RAG_EMBEDDING_CUDA_ALLOC_CONF",
        "AIPIPELINE_WORKER_RAG_INDEX_DIR",
    ]


def load_worker_settings() -> Any:
    from app.core.config import WorkerSettings

    return WorkerSettings()


def import_embedding_provider() -> tuple[Any, Callable[[Any], Any]]:
    from app.capabilities.rag.embeddings import SentenceTransformerEmbedder, resolve_max_seq_length

    return SentenceTransformerEmbedder, resolve_max_seq_length


def import_vector_index_provider() -> Any:
    from app.capabilities.rag.faiss_index import FaissIndex

    return FaissIndex


def construct_canonical_embedder(
    *,
    settings: Any,
    provider_class: Any,
    resolve_max_seq_length: Callable[[Any], Any],
) -> Any:
    return provider_class(
        model_name=settings.rag_embedding_model,
        query_prefix=settings.rag_embedding_prefix_query,
        passage_prefix=settings.rag_embedding_prefix_passage,
        max_seq_length=resolve_max_seq_length(settings.rag_embedding_max_seq_length),
        batch_size=int(settings.rag_embedding_batch_size),
        cuda_alloc_conf=settings.rag_embedding_cuda_alloc_conf or None,
    )


def settings_backend_summary(settings: Any) -> dict[str, Any]:
    return {
        "rag_embedding_model_present": bool(str(getattr(settings, "rag_embedding_model", "") or "").strip()),
        "rag_embedding_model": str(getattr(settings, "rag_embedding_model", "") or ""),
        "rag_embedding_prefix_query_present": bool(getattr(settings, "rag_embedding_prefix_query", "")),
        "rag_embedding_prefix_passage_present": bool(getattr(settings, "rag_embedding_prefix_passage", "")),
        "rag_embedding_max_seq_length": getattr(settings, "rag_embedding_max_seq_length", None),
        "rag_embedding_batch_size": getattr(settings, "rag_embedding_batch_size", None),
        "rag_index_dir": str(getattr(settings, "rag_index_dir", "") or ""),
        "rag_embedding_text_variant": str(getattr(settings, "rag_embedding_text_variant", "") or ""),
    }


def detect_embedding_dimension(embedder: Any, vectors: Any) -> int | None:
    shape = getattr(vectors, "shape", None)
    if shape is not None and len(shape) == 2 and int(shape[0]) == 1:
        return int(shape[1])
    dimension = getattr(embedder, "dimension", None)
    if dimension is not None:
        return int(dimension)
    return None


def existing_vector_indexes_detected(namespace_payload: Mapping[str, Any]) -> bool:
    return any(bool(entry.get("has_faiss_index")) for entry in namespace_payload.get("namespaces", []))


def safe_error(exc: BaseException) -> str:
    return redact_secret_values(f"{type(exc).__name__}: {exc}")[:600]


def redact_secret_values(text: str) -> str:
    redacted = text
    secret_markers = ("KEY", "TOKEN", "SECRET", "PASSWORD")
    for name, value in os.environ.items():
        if not value or len(value) < 4:
            continue
        if any(marker in name.upper() for marker in secret_markers):
            redacted = redacted.replace(value, "<redacted>")
    return redacted


def build_guardrail_status(
    config: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    official_diff: Mapping[str, Any],
) -> dict[str, Any]:
    hidden_support = sum(1 for row in rows if row["hidden_xlsx"] and row["support_eligible"])
    diagnostic_support = sum(1 for row in rows if row["diagnostic_only"] and row["support_eligible"])
    pdf_mixing_support = sum(
        1 for row in rows if row["pdf_file_content_mixing_risk"] and row["support_eligible"]
    )
    forbidden_embed = sum(1 for row in rows if row["expected_answer_or_label_embedded"])
    assertions = dict(config["guardrail_assertions"])
    status = {
        **assertions,
        "wrongly_supported_count": 0,
        "hidden_xlsx_support_eligible_count": hidden_support,
        "diagnostic_only_support_eligible_count": diagnostic_support,
        "pdf_file_content_mixing_support_eligible_count": pdf_mixing_support,
        "expected_answer_or_label_embedding_count": forbidden_embed,
        "official_denominator_registry_changed": bool(official_diff["changed"]),
        "production_index_mutation": False,
        "broad_indexing": False,
        "production_promotion_ready": False,
        "official_answer_denominator_ready": False,
    }
    status["all_guardrails_preserved"] = (
        hidden_support == 0
        and diagnostic_support == 0
        and pdf_mixing_support == 0
        and forbidden_embed == 0
        and not official_diff["changed"]
    )
    return status


def write_outputs(config: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    options = report_artifacts.reporting_options(config)
    paths = config["report_paths"]
    backend_contract_report = build_backend_contract_report(
        config=config,
        config_path=resolve_path(payload["config_path"]),
        namespace_payload=payload["namespace_inventory"],
        embedding_backend=payload["embedding_backend"],
        readiness_payload=payload,
    )
    if options["emit_stage_reports"]:
        write_json(resolve_path(paths["readiness_json"]), payload)
        write_text(resolve_path(paths["readiness_md"]), render_md(payload))
    if options["emit_csv"]:
        write_rows_csv(resolve_path(paths["readiness_csv"]), payload["manifest_rows"])
    if options["emit_row_manifest"]:
        write_jsonl(resolve_path(paths["backfill_manifest_jsonl"]), payload["manifest_rows"])
    if options["emit_namespace_inventory"]:
        write_json(resolve_path(paths["namespace_inventory_json"]), payload["namespace_inventory"])
    if options["emit_debug_artifacts"]:
        write_backend_contract_outputs(config, backend_contract_report)


def build_backend_contract_report(
    *,
    config: Mapping[str, Any],
    config_path: Path,
    namespace_payload: Mapping[str, Any] | None = None,
    embedding_backend: Mapping[str, Any] | None = None,
    readiness_payload: Mapping[str, Any] | None = None,
    backend_contract_kwargs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if namespace_payload is None:
        namespace_payload = discover_namespace_inventory(config)
    if embedding_backend is None:
        embedding_backend = summarize_embedding_backend(
            config,
            namespace_payload,
            [],
            **dict(backend_contract_kwargs or {}),
        )
    previous = read_previous_readiness_backend_state(config)
    guardrails = dict(config["guardrail_assertions"])
    if readiness_payload is not None:
        guardrails.update(dict(readiness_payload.get("guardrail_status", {})))
    guardrail_summary = {
        "official_denominator_registry_changed": bool(guardrails.get("official_denominator_registry_changed")),
        "official_answer_denominator_opened": bool(guardrails.get("official_answer_denominator_opened")),
        "production_index_mutation": bool(guardrails.get("production_index_mutation")),
        "broad_indexing": bool(guardrails.get("broad_indexing")),
        "frozen_gold_training_rows": int(guardrails.get("frozen_gold_training_rows") or 0),
        "frozen_gold_profile_selection": bool(guardrails.get("frozen_gold_profile_selection")),
        "expected_answer_or_label_embedding_count": int(
            guardrails.get("expected_answer_or_label_embedding_count") or 0
        ),
        "hidden_xlsx_support_eligible_count": int(guardrails.get("hidden_xlsx_support_eligible_count") or 0),
        "pdf_file_content_mixing_support_eligible_count": int(
            guardrails.get("pdf_file_content_mixing_support_eligible_count") or 0
        ),
        "diagnostic_only_support_eligible_count": int(guardrails.get("diagnostic_only_support_eligible_count") or 0),
        "production_promotion_ready": bool(guardrails.get("production_promotion_ready")),
        "official_answer_denominator_ready": bool(guardrails.get("official_answer_denominator_ready")),
    }
    guardrails_preserved = (
        not any(
            bool(guardrail_summary[key])
            for key in (
                "official_denominator_registry_changed",
                "official_answer_denominator_opened",
                "production_index_mutation",
                "broad_indexing",
                "frozen_gold_profile_selection",
                "production_promotion_ready",
                "official_answer_denominator_ready",
            )
        )
        and guardrail_summary["frozen_gold_training_rows"] == 0
        and guardrail_summary["expected_answer_or_label_embedding_count"] == 0
        and guardrail_summary["hidden_xlsx_support_eligible_count"] == 0
        and guardrail_summary["pdf_file_content_mixing_support_eligible_count"] == 0
        and guardrail_summary["diagnostic_only_support_eligible_count"] == 0
        and not bool(embedding_backend.get("vector_write_attempted"))
        and not bool(embedding_backend.get("namespace_created"))
    )
    status = "PASS" if guardrails_preserved and embedding_backend.get("backend_contract_status") != "indeterminate" else "FAIL"
    return {
        "schema_version": "answer_recovery_embedding_backend_contract_recheck_report_v1",
        "stage": STAGE_BACKEND_CONTRACT_RECHECK,
        "status": status,
        "backend_contract_status": embedding_backend.get("backend_contract_status"),
        "config_path": repo_relative(config_path),
        "previous_readiness": previous,
        "corrected_backend_availability": embedding_backend.get("embedding_backend_available"),
        "corrected_staging_backfill_status": embedding_backend.get("staging_backfill_status"),
        "backend_config_detected": embedding_backend.get("backend_config_detected"),
        "backend_config_load_succeeded": embedding_backend.get("backend_config_load_succeeded"),
        "backend_provider_importable": embedding_backend.get("backend_provider_importable"),
        "backend_provider_constructible": embedding_backend.get("backend_provider_constructible"),
        "backend_required_env_present": embedding_backend.get("backend_required_env_present"),
        "required_env_vars": embedding_backend.get("required_env_vars", []),
        "missing_required_env_vars": embedding_backend.get("missing_required_env_vars", []),
        "env_presence": embedding_backend.get("env_presence", []),
        "settings_summary": embedding_backend.get("settings_summary", {}),
        "backend_probe_embedding_allowed": embedding_backend.get("backend_probe_embedding_allowed"),
        "backend_probe_embedding_succeeded": embedding_backend.get("backend_probe_embedding_succeeded"),
        "backend_embedding_dimension_detected": embedding_backend.get("backend_embedding_dimension_detected"),
        "backend_probe_text": embedding_backend.get("backend_probe_text"),
        "backend_probe_text_source": embedding_backend.get("backend_probe_text_source"),
        "backend_probe_text_policy": embedding_backend.get("backend_probe_text_policy"),
        "vector_index_reader_available": embedding_backend.get("vector_index_reader_available"),
        "vector_index_writer_available": embedding_backend.get("vector_index_writer_available"),
        "existing_vector_indexes_detected": embedding_backend.get("existing_vector_indexes_detected"),
        "staging_namespace_exists": embedding_backend.get("staging_namespace_exists"),
        "staging_namespace_safe": embedding_backend.get("staging_namespace_safe"),
        "staging_backfill_enabled_by_config": embedding_backend.get("staging_backfill_enabled_by_config"),
        "staging_backfill_status": embedding_backend.get("staging_backfill_status"),
        "staging_backfill_skip_reason": embedding_backend.get("staging_backfill_skip_reason"),
        "embedding_backend_available": embedding_backend.get("embedding_backend_available"),
        "backend_availability_reason": embedding_backend.get("backend_availability_reason"),
        "backend_unavailable_reason": embedding_backend.get("backend_unavailable_reason"),
        "backend_indeterminate_reason": embedding_backend.get("backend_indeterminate_reason"),
        "vector_write_attempted": embedding_backend.get("vector_write_attempted"),
        "namespace_created": embedding_backend.get("namespace_created"),
        "production_mutation": embedding_backend.get("production_mutation"),
        "production_index_mutation": embedding_backend.get("production_index_mutation"),
        "official_denominator_opened": embedding_backend.get("official_denominator_opened"),
        "official_answer_denominator_opened": embedding_backend.get("official_answer_denominator_opened"),
        "guardrail_summary": guardrail_summary,
    }


def write_backend_contract_outputs(config: Mapping[str, Any], report: Mapping[str, Any]) -> None:
    options = report_artifacts.reporting_options(config)
    paths = config["report_paths"]
    md_path = paths.get("backend_contract_md")
    json_path = paths.get("backend_contract_json")
    csv_path = paths.get("backend_contract_csv")
    if options["emit_stage_reports"] and json_path:
        write_json(resolve_path(json_path), report)
    if options["emit_stage_reports"] and md_path:
        write_text(resolve_path(md_path), render_backend_contract_md(report))
    if options["emit_csv"] and csv_path:
        write_backend_contract_csv(resolve_path(csv_path), report)


def render_backend_contract_md(report: Mapping[str, Any]) -> str:
    lines = [
        "# Answer Recovery Embedding Backend Contract Recheck",
        "",
        f"- Status: `{report['status']}`.",
        f"- Backend contract status: `{report['backend_contract_status']}`.",
        f"- Embedding backend available: `{report['embedding_backend_available']}`.",
        f"- Staging backfill enabled by config: `{report['staging_backfill_enabled_by_config']}`.",
        f"- Staging backfill status: `{report['staging_backfill_status']}`.",
        f"- Backend availability reason: `{report['backend_availability_reason']}`.",
        f"- Staging skip reason: `{report['staging_backfill_skip_reason']}`.",
        "",
        "## Backend Contract",
        "",
    ]
    for key in (
        "backend_config_detected",
        "backend_config_load_succeeded",
        "backend_provider_importable",
        "backend_provider_constructible",
        "backend_required_env_present",
        "backend_probe_embedding_allowed",
        "backend_probe_embedding_succeeded",
        "backend_embedding_dimension_detected",
        "vector_index_reader_available",
        "vector_index_writer_available",
        "existing_vector_indexes_detected",
        "staging_namespace_exists",
        "staging_namespace_safe",
        "vector_write_attempted",
        "namespace_created",
        "production_mutation",
        "official_denominator_opened",
    ):
        lines.append(f"- {key}: `{report.get(key)}`")
    lines.extend(["", "## Required Environment", ""])
    required = report.get("required_env_vars", [])
    missing = report.get("missing_required_env_vars", [])
    lines.append(f"- Required env vars: `{', '.join(required) if required else 'none'}`")
    lines.append(f"- Missing required env vars: `{', '.join(missing) if missing else 'none'}`")
    for entry in report.get("env_presence", []):
        marker = "required" if entry.get("required") else "observed"
        lines.append(f"- {entry['name']}: present=`{entry['present']}` ({marker})")
    lines.extend(["", "## Guardrails", ""])
    for key, value in report["guardrail_summary"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def write_backend_contract_csv(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["key", "value"]
    rows: list[dict[str, str]] = []
    for key, value in flatten_report(report).items():
        rows.append({"key": key, "value": serialize_csv_value(value)})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def flatten_report(report: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in report.items():
        next_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            flattened.update(flatten_report(value, next_key))
        else:
            flattened[next_key] = value
    return flattened


def read_previous_readiness_backend_state(config: Mapping[str, Any]) -> dict[str, Any]:
    path = resolve_path(config["report_paths"]["readiness_json"])
    if not path.exists():
        return {"exists": False}
    try:
        payload = read_json(path)
        backend = payload.get("embedding_backend", {})
        return {
            "exists": True,
            "embedding_backend_available": backend.get("embedding_backend_available"),
            "staging_backfill_status": backend.get("staging_backfill_status"),
        }
    except Exception as exc:  # noqa: BLE001 - previous report is optional context
        return {"exists": True, "read_error": safe_error(exc)}


def render_md(payload: Mapping[str, Any]) -> str:
    counts = payload["counts"]
    backend = payload["embedding_backend"]
    lines = [
        "# Answer Recovery Embedding Readiness",
        "",
        f"- Status: `{payload['status']}`.",
        f"- Manifest rows: `{counts['manifest_row_count']}`.",
        f"- Embedding backend available: `{backend['embedding_backend_available']}`.",
        f"- Backend contract status: `{backend['backend_contract_status']}`.",
        f"- Backend probe succeeded: `{backend['backend_probe_embedding_succeeded']}`.",
        f"- Backend embedding dimension detected: `{backend['backend_embedding_dimension_detected']}`.",
        f"- Staging namespace: `{backend['staging_namespace']}`.",
        f"- Staging backfill enabled by config: `{backend['staging_backfill_enabled_by_config']}`.",
        f"- Staging backfill status: `{backend['staging_backfill_status']}`.",
        f"- Staging backfill skip reason: `{backend['staging_backfill_skip_reason']}`.",
        "- Production promotion ready: `false`.",
        "- Official answer denominator ready: `false`.",
        "- Optuna used: `false`.",
        "",
        "## Backend Contract",
        "",
    ]
    for key in (
        "backend_config_detected",
        "backend_provider_importable",
        "backend_provider_constructible",
        "backend_required_env_present",
        "backend_probe_embedding_allowed",
        "backend_probe_embedding_succeeded",
        "backend_embedding_dimension_detected",
        "vector_index_reader_available",
        "vector_index_writer_available",
        "existing_vector_indexes_detected",
        "staging_namespace_exists",
        "staging_namespace_safe",
        "vector_write_attempted",
        "namespace_created",
        "production_mutation",
        "official_denominator_opened",
    ):
        lines.append(f"- {key}: `{backend.get(key)}`")
    lines.extend([
        "",
        "## Classification Counts",
        "",
    ])
    for key, value in counts["classification_counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## INDEX_SCOPE_MISSING Causes", ""])
    for key, value in counts["index_scope_missing_cause_counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Safe Existing Evidence Rows", ""])
    for row in payload["safe_existing_rows"]:
        namespaces = ",".join(row["existing_embedding_namespaces"]) or "none"
        lines.append(
            f"- `{row['row_id']}` chunk=`{row['chunk_id']}` already_embedded=`{row['already_embedded']}` "
            f"namespaces=`{namespaces}` action=`{row['recommended_action']}`"
        )
    lines.extend(["", "## Guardrails", ""])
    for key, value in payload["guardrail_status"].items():
        if isinstance(value, Mapping):
            compact = ", ".join(f"{subkey}={subvalue}" for subkey, subvalue in value.items())
            lines.append(f"- {key}: `{compact}`")
        else:
            lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Notes", ""])
    lines.append(
        "- Existing embedding/vector conventions were detected from the repo, but no staging vector write was "
        "performed. Eval CSV evidence text was not embedded; source text was considered only when independently "
        "present in allowed source-text artifacts."
    )
    lines.append(
        "- PDF FILE lookup remains file-identity-only and cannot claim content/page/bbox/table/row/column/value "
        "success from this manifest."
    )
    lines.append("")
    return "\n".join(lines)


def write_rows_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "manifest_id",
        "row_id",
        "stable_query_id",
        "lane",
        "before_status",
        "after_status",
        "selected_variant",
        "triage_category",
        "manifest_classification",
        "skip_reason",
        "index_scope_missing_cause",
        "source_artifact_id",
        "canonical_source_id",
        "source_type",
        "evidence_source_type",
        "page_number",
        "sheet_name",
        "table_name",
        "row_metadata",
        "column_metadata",
        "chunk_id",
        "chunk_hash",
        "chunk_text_length",
        "source_text_available",
        "already_embedded",
        "existing_embedding_namespaces",
        "configured_staging_namespace",
        "missing_from_configured_staging_namespace",
        "embedding_eligible",
        "support_eligible",
        "diagnostic_only",
        "hidden_xlsx",
        "pdf_file_identity_only",
        "pdf_file_content_mixing_risk",
        "native_pdf_text_available",
        "ocr_fallback",
        "frozen_gold_sourced_row",
        "selection_or_training_eligible",
        "contains_expected_answer_or_label_content",
        "expected_answer_or_label_embedded",
        "recommended_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: serialize_csv_value(row.get(key, "")) for key in fieldnames})


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def source_record_is_diagnostic(record: Mapping[str, str]) -> bool:
    values = " ".join(
        str(record.get(key) or "")
        for key in ("label_status", "denominator_role", "generation_reason", "dataset_source")
    ).lower()
    if "diagnostic_only" in values:
        return True
    promotion = str(record.get("promotion_evidence") or "").strip().lower()
    return promotion == "false" and "diagnostic" in values


def contains_forbidden_embed_content(record: Mapping[str, str]) -> bool:
    for key, value in record.items():
        lowered = key.lower()
        if lowered in {"expected_chunk_ids", "expected_document_ids", "expected_page_ids", "expected_section_path"}:
            continue
        if any(hint in lowered for hint in FORBIDDEN_EMBED_FIELD_HINTS) and str(value).strip():
            return True
    return False


def chunk_ids_from_record(record: Mapping[str, str]) -> list[str]:
    raw = str(record.get("expected_chunk_ids") or record.get("chunk_id") or "")
    if not raw:
        return []
    parts = re.split(r"[|,;\s]+", raw)
    return [part.strip() for part in parts if part.strip()]


def retrieved_chunk_ids(trace: Mapping[str, Any]) -> list[str]:
    found: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, inner in value.items():
                if key == "retrieved_chunk_ids" and isinstance(inner, list):
                    found.extend(str(item) for item in inner if item)
                else:
                    walk(inner)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(trace.get("loop_result") or trace)
    return found


def page_number_from_record(record: Mapping[str, str]) -> int | None:
    for key in ("page_number", "page_no", "diagnostic_page_no", "expected_page_ids"):
        value = str(record.get(key) or "").strip()
        if value.isdigit():
            return int(value)
    citation = parse_jsonish(record.get("citation", ""))
    for key in ("page_no", "physical_page_index"):
        value = citation.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def page_number_from_row_id(row_id: str) -> int | None:
    match = re.search(r"_p(\d+)_", row_id)
    return int(match.group(1)) if match else None


def row_number_suffix(row_id: str) -> str:
    match = re.search(r"(\d+)$", row_id)
    return match.group(1) if match else ""


def parse_jsonish(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def stable_pseudo_chunk_id(canonical_source_id: str) -> str:
    return "pseudo:" + sha256_text(canonical_source_id)[:16]


def manifest_id(row_id: str, canonical_source_id: str, chunk_id: str) -> str:
    return sha256_text("|".join((row_id, canonical_source_id, chunk_id)))[:16]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def counts_with_zeros(values: Iterable[str], order: Sequence[str]) -> dict[str, int]:
    counts = Counter(value for value in values if value)
    return {key: counts[key] for key in order}


def artifact_summaries(artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for name, artifact in artifacts.items():
        summary = {key: artifact.get(key) for key in ("path", "exists", "bytes", "line_count")}
        if "payload" in artifact and isinstance(artifact["payload"], Mapping):
            summary["schema_version"] = artifact["payload"].get("schema_version")
        if "rows" in artifact:
            summary["row_count"] = len(artifact["rows"])
        if "trace_by_case" in artifact:
            summary["case_count"] = len(artifact["trace_by_case"])
        summaries[name] = {key: value for key, value in summary.items() if value is not None}
    return summaries


def official_registry_diff_proof() -> dict[str, Any]:
    return safe_recall.official_registry_diff_proof()


def serialize_csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def resolve_path(value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai":
        return REPO_ROOT / path
    return AI_WORKER_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
