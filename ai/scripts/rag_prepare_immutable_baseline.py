"""Validate or materialize an immutable RAG-ingestion baseline report.

This script does not promote anything. It prepares C3 evidence by rejecting
candidate snapshots and writing a readiness report with the exact blockers.
When the supplied baseline report is valid, it can also materialize a compact
immutable baseline descriptor that carries hash/provenance fields for gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/a5_c3_immutable_baseline_readiness.json")
INITIAL_BASELINE_BOOTSTRAP = "INITIAL_BASELINE_BOOTSTRAP"
BOOTSTRAP_READY_NOT_PROMOTION = "BOOTSTRAP_READY_NOT_PROMOTION"
VECTOR_BACKENDS = {"faiss"}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    baseline_path = Path(args.baseline_report)
    payload, raw = read_json_with_raw(baseline_path)
    report_hash = hashlib.sha256(raw).hexdigest()
    effective_payload = dict(payload)
    if args.eval_dataset_version:
        effective_payload.setdefault("eval_dataset_version", args.eval_dataset_version)
        effective_payload.setdefault("baseline_dataset_version", args.eval_dataset_version)
    if args.baseline_provenance:
        effective_payload.setdefault("baseline_provenance", args.baseline_provenance)
    metrics = extract_metrics(effective_payload)
    reasons = validate_baseline(
        effective_payload,
        metrics=metrics,
        baseline_index_version=args.baseline_index_version,
        candidate_index_version=args.candidate_index_version,
        require_vector_backend=not args.allow_non_vector_backend,
    )
    readiness = {
        "run_id": utc_run_id(),
        "status": "PASS" if not reasons else "FAIL",
        "baseline_report": str(baseline_path),
        "baseline_report_hash": report_hash,
        "baseline_type": effective_payload.get("baseline_type"),
        "bootstrap_status": effective_payload.get("bootstrap_status"),
        "baseline_index_version": args.baseline_index_version,
        "candidate_index_version": args.candidate_index_version,
        "candidate_snapshot": bool(effective_payload.get("candidate_snapshot") or metrics.get("candidate_snapshot_baseline")),
        "immutable_baseline": bool(effective_payload.get("immutable_baseline") or metrics.get("immutable_baseline")),
        "eval_dataset_version": effective_payload.get("eval_dataset_version"),
        "retrieval_backend": metrics.get("retrieval_backend") or effective_payload.get("retrieval_backend"),
        "baseline_provenance": effective_payload.get("baseline_provenance"),
        "promotion_evidence": effective_payload.get("promotion_evidence"),
        "usable_as_baseline_for_future_candidates": effective_payload.get(
            "usable_as_baseline_for_future_candidates"
        ),
        "reasons": reasons,
        "write_immutable_baseline": bool(args.immutable_output and not reasons),
    }
    write_json(Path(args.output), readiness)
    if args.immutable_output and not reasons:
        immutable = immutable_baseline_payload(
            effective_payload,
            metrics=metrics,
            source_path=baseline_path,
            report_hash=report_hash,
            baseline_index_version=args.baseline_index_version,
            candidate_index_version=args.candidate_index_version,
            eval_dataset_version=args.eval_dataset_version,
            baseline_provenance=args.baseline_provenance or payload.get("baseline_provenance"),
        )
        write_json(Path(args.immutable_output), immutable)
    print(json.dumps(readiness, ensure_ascii=False, indent=2))
    return 0 if not reasons else 2


def validate_baseline(
    payload: Mapping[str, Any],
    *,
    metrics: Mapping[str, Any],
    baseline_index_version: str,
    candidate_index_version: str,
    require_vector_backend: bool,
) -> list[str]:
    reasons: list[str] = []
    if payload.get("candidate_snapshot") is True or metrics.get("candidate_snapshot_baseline") is True:
        reasons.append("candidate_snapshot baseline cannot be immutable")
    if not baseline_index_version:
        reasons.append("baseline_index_version is required")
    if baseline_index_version and baseline_index_version == candidate_index_version:
        reasons.append("baseline_index_version must differ from candidate_index_version")
    backend = metrics.get("retrieval_backend") or payload.get("retrieval_backend")
    if backend == "library_search":
        reasons.append("library_search report cannot be an immutable baseline")
    if require_vector_backend and backend != "vector":
        reasons.append("immutable baseline must be vector-backed")
    if not (payload.get("eval_dataset_version") or metrics.get("eval_dataset_version")):
        reasons.append("eval_dataset_version is required")
    if not (payload.get("baseline_provenance") or metrics.get("baseline_provenance")):
        reasons.append("baseline_provenance is required")
    if not metrics:
        reasons.append("baseline metrics are required")
    for key in ("Hit@10", "MRR@10", "citation_accuracy"):
        if first_present(metrics, key, key.lower().replace("@", "_at_")) is None:
            reasons.append(f"{key} metric is required")
    if payload.get("baseline_type") == INITIAL_BASELINE_BOOTSTRAP:
        reasons.extend(
            validate_initial_bootstrap_baseline(
                payload,
                baseline_index_version=baseline_index_version,
                candidate_index_version=candidate_index_version,
            )
        )
    return reasons


def validate_initial_bootstrap_baseline(
    payload: Mapping[str, Any],
    *,
    baseline_index_version: str,
    candidate_index_version: str,
) -> list[str]:
    reasons: list[str] = []
    if payload.get("immutable_baseline") is not True:
        reasons.append("INITIAL_BASELINE_BOOTSTRAP must declare immutable_baseline=true")
    if payload.get("candidate_snapshot") is not False:
        reasons.append("INITIAL_BASELINE_BOOTSTRAP must declare candidate_snapshot=false")
    if payload.get("promotion_evidence") is not False:
        reasons.append("INITIAL_BASELINE_BOOTSTRAP must declare promotion_evidence=false")
    if payload.get("usable_as_baseline_for_future_candidates") is not True:
        reasons.append("INITIAL_BASELINE_BOOTSTRAP must be usable_as_baseline_for_future_candidates=true")
    if payload.get("bootstrap_status") != BOOTSTRAP_READY_NOT_PROMOTION:
        reasons.append(f"INITIAL_BASELINE_BOOTSTRAP bootstrap_status must be {BOOTSTRAP_READY_NOT_PROMOTION}")
    if payload.get("promotion_gate_effect") != "none":
        reasons.append("INITIAL_BASELINE_BOOTSTRAP promotion_gate_effect must be none")
    if payload.get("baseline_index_version") != baseline_index_version:
        reasons.append("INITIAL_BASELINE_BOOTSTRAP baseline_index_version must match CLI baseline_index_version")

    source_candidate_index_version = first_present(payload, "source_candidate_index_version")
    if not source_candidate_index_version:
        reasons.append("source_candidate_index_version is required")
    elif source_candidate_index_version != candidate_index_version:
        reasons.append("source_candidate_index_version must match CLI candidate_index_version for bootstrap readiness")
    if source_candidate_index_version and source_candidate_index_version == baseline_index_version:
        reasons.append("baseline_index_version must differ from source_candidate_index_version")

    backend_identity = payload.get("backend_identity") or payload.get("retrieval_backend_identity")
    if not isinstance(backend_identity, Mapping):
        reasons.append("backend_identity is required")
    else:
        if backend_identity.get("backend") not in VECTOR_BACKENDS:
            reasons.append("backend_identity.backend must identify a vector backend")
        namespace_filter = first_present(backend_identity, "index_namespace_filter")
        if not namespace_filter:
            reasons.append("backend_identity.index_namespace_filter is required")
        elif namespace_filter != payload.get("candidate_namespace_filter"):
            reasons.append("candidate_namespace_filter must match backend_identity.index_namespace_filter")
        if source_candidate_index_version and namespace_filter != source_candidate_index_version:
            reasons.append("candidate_namespace_filter must match source_candidate_index_version")

    for key in (
        "candidate_namespace_filter",
        "eval_dataset_id",
        "eval_dataset_version",
        "eval_dataset_sha256",
        "gold_query_row_count",
        "document_version_scope",
        "embedding_model",
        "retrieval_report_path",
        "retrieval_report_sha256",
        "metrics_report_path",
        "metrics_report_sha256",
        "created_at",
        "bootstrap_reason",
    ):
        if first_present(payload, key) in (None, "", []):
            reasons.append(f"{key} is required")
    if not (payload.get("created_by") or payload.get("bootstrap_actor")):
        reasons.append("created_by or bootstrap_actor is required")
    if not (payload.get("vector_index_hash") or payload.get("faiss_artifact_hash")):
        reasons.append("vector_index_hash or faiss_artifact_hash is required")
    return reasons


def immutable_baseline_payload(
    payload: Mapping[str, Any],
    *,
    metrics: Mapping[str, Any],
    source_path: Path,
    report_hash: str,
    baseline_index_version: str,
    candidate_index_version: str,
    eval_dataset_version: str | None,
    baseline_provenance: str | None,
) -> dict[str, Any]:
    result = {
        "schema": "rag-ingestion-immutable-baseline-v1",
        "created_at": utc_run_id(),
        "immutable_baseline": True,
        "candidate_snapshot": False,
        "baseline_index_version": baseline_index_version,
        "candidate_index_version": candidate_index_version,
        "eval_dataset_version": eval_dataset_version or payload.get("eval_dataset_version"),
        "baseline_dataset_version": eval_dataset_version or payload.get("eval_dataset_version"),
        "baseline_provenance": baseline_provenance,
        "immutable_baseline_report_hash": report_hash,
        "source_report": str(source_path),
        "retrieval_backend": metrics.get("retrieval_backend") or payload.get("retrieval_backend"),
        "metrics": dict(metrics),
    }
    if payload.get("baseline_type") == INITIAL_BASELINE_BOOTSTRAP:
        for key in (
            "baseline_type",
            "bootstrap_status",
            "source_candidate_index_version",
            "candidate_namespace_filter",
            "backend_identity",
            "eval_dataset_id",
            "eval_dataset_sha256",
            "gold_query_row_count",
            "document_version_scope",
            "embedding_model",
            "vector_index_hash",
            "faiss_artifact_hash",
            "retrieval_report_path",
            "retrieval_report_sha256",
            "metrics_report_path",
            "metrics_report_sha256",
            "bootstrap_actor",
            "bootstrap_reason",
            "promotion_evidence",
            "promotion_gate_effect",
            "usable_as_baseline_for_future_candidates",
        ):
            if key in payload:
                result[key] = payload[key]
    return result


def extract_metrics(payload: Mapping[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics")
    if isinstance(metrics, Mapping):
        result = dict(metrics)
    else:
        result = dict(payload)
    for key in (
        "retrieval_backend",
        "immutable_baseline",
        "baseline_type",
        "eval_dataset_version",
        "baseline_dataset_version",
        "baseline_provenance",
        "candidate_snapshot_baseline",
        "promotion_evidence",
    ):
        if key in payload and key not in result:
            result[key] = payload[key]
    return result


def first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return None


def read_json_with_raw(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"baseline report must be a JSON object: {path}")
    return payload, raw


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-report", required=True)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--immutable-output")
    parser.add_argument("--baseline-index-version", required=True)
    parser.add_argument("--candidate-index-version", required=True)
    parser.add_argument("--eval-dataset-version")
    parser.add_argument("--baseline-provenance")
    parser.add_argument(
        "--allow-non-vector-backend",
        action="store_true",
        help="Diagnostic-only escape hatch; promotion baselines should not use it.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
