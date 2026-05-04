"""Create the first immutable vector baseline descriptor.

This is a bootstrap-only helper. It freezes an already validated vector
diagnostic artifact by hash so future candidates can compare against it. It
does not promote the current candidate and it refuses candidate snapshot
baseline files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_RETRIEVAL_REPORT = Path("reports/rag_retrieval_eval_full72_vector_diagnostic_report.json")
DEFAULT_METRICS_REPORT = Path("reports/rag_ingestion_a5_promotion_gate_metrics.json")
DEFAULT_GOLD = Path("eval/gold_queries_v0.csv")
DEFAULT_INDEX_DIR = Path("rag-data-canary")
DEFAULT_CONSISTENCY_REPORT = Path("reports/pdf_xlsx_candidate_embedding_consistency_report.json")
DEFAULT_SCOPE_READINESS_REPORT = Path("reports/rag_candidate_scope_path_readiness.json")
DEFAULT_DESCRIPTOR = Path("reports/initial_immutable_vector_baseline_descriptor.json")
DEFAULT_READINESS = Path("reports/initial_baseline_bootstrap_readiness.json")

BASELINE_TYPE = "INITIAL_BASELINE_BOOTSTRAP"
BOOTSTRAP_STATUS = "BOOTSTRAP_READY_NOT_PROMOTION"
SCHEMA = "rag-initial-vector-baseline-bootstrap-v1"
VECTOR_BACKENDS = {"faiss"}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    descriptor, blockers, warnings = build_descriptor(args)

    descriptor_path = Path(args.descriptor_output)
    readiness_path = Path(args.readiness_output)
    descriptor_sha256 = None
    if not blockers:
        write_json(descriptor_path, descriptor)
        descriptor_sha256 = file_sha256(descriptor_path)

    readiness = {
        "run_id": utc_run_id(),
        "status": "PASS" if not blockers else "FAIL",
        "schema": SCHEMA,
        "baseline_type": BASELINE_TYPE,
        "bootstrap_status": BOOTSTRAP_STATUS if not blockers else "BOOTSTRAP_BLOCKED",
        "promotion_gate_effect": "none",
        "promotion_evidence": False,
        "descriptor_path": str(descriptor_path),
        "descriptor_sha256": descriptor_sha256,
        "baseline_index_version": args.baseline_index_version,
        "source_candidate_index_version": descriptor.get("source_candidate_index_version"),
        "candidate_namespace_filter": descriptor.get("candidate_namespace_filter"),
        "retrieval_report_path": str(Path(args.retrieval_report)),
        "metrics_report_path": str(Path(args.metrics_report)),
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "This readiness report is for initial immutable baseline bootstrap only.",
            "It is not promotion evidence and does not mark the current candidate promoted.",
            "Candidate snapshot baselines remain invalid immutable baseline inputs.",
        ],
    }
    write_json(readiness_path, readiness)
    print(json.dumps(readiness, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


def build_descriptor(args: argparse.Namespace) -> tuple[dict[str, Any], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []

    retrieval_path = Path(args.retrieval_report)
    metrics_path = Path(args.metrics_report)
    gold_path = Path(args.gold)
    index_dir = Path(args.vector_index_dir)
    retrieval = read_json(retrieval_path, blockers, label="retrieval_report")
    read_json(metrics_path, blockers, label="metrics_report")
    consistency = read_optional_json(Path(args.consistency_report), warnings, label="consistency_report")
    scope_readiness = read_optional_json(Path(args.scope_readiness_report), warnings, label="scope_readiness_report")
    build_meta = read_optional_json(index_dir / "build.json", warnings, label="faiss_build_meta")
    ingest_manifest = read_optional_json(index_dir / "ingest_manifest.json", warnings, label="faiss_ingest_manifest")
    gold_rows = read_gold_rows(gold_path, blockers)

    metrics = dict(retrieval.get("metrics") or {}) if isinstance(retrieval, Mapping) else {}
    backend_identity = dict(retrieval.get("backend_identity") or {}) if isinstance(retrieval, Mapping) else {}
    retrieval_backend = retrieval.get("retrieval_backend") if isinstance(retrieval, Mapping) else None
    source_candidate_index_version = (
        args.source_candidate_index_version
        or retrieval.get("candidate_index_version")
        or retrieval.get("required_index_version")
        or backend_identity.get("index_namespace_filter")
    )
    candidate_namespace_filter = backend_identity.get("index_namespace_filter")
    embedding_model = (
        args.embedding_model
        or ingest_manifest.get("embedding_model")
        or build_meta.get("embedding_model")
        or backend_identity.get("embedding_model")
    )
    document_version_ids = document_version_scope(consistency, gold_rows)
    faiss_path = index_dir / "faiss.index"
    faiss_hash = file_sha256(faiss_path) if faiss_path.exists() else None
    artifact_hashes = artifact_hash_map(index_dir, ("faiss.index", "build.json", "ingest_manifest.json"))
    vector_index_hash = combined_artifact_hash(index_dir, ("faiss.index", "build.json", "ingest_manifest.json"))
    retrieval_report_sha256 = file_sha256(retrieval_path) if retrieval_path.exists() else None

    if retrieval.get("candidate_snapshot") is True or metrics.get("candidate_snapshot_baseline") is True:
        blockers.append("candidate snapshot baseline cannot be used for INITIAL_BASELINE_BOOTSTRAP")
    if retrieval_backend == "library_search":
        blockers.append("library_search report cannot be used for INITIAL_BASELINE_BOOTSTRAP")
    if retrieval_backend != "vector":
        blockers.append("retrieval_report must be vector-backed")
    if retrieval.get("promotion_evidence") is not False:
        blockers.append("retrieval_report must declare promotion_evidence=false for bootstrap")
    if retrieval.get("evidence_role") == "promotion":
        blockers.append("retrieval_report evidence_role must not be promotion for bootstrap")
    if not isinstance(backend_identity, dict) or not backend_identity:
        blockers.append("backend_identity is required")
    elif backend_identity.get("backend") not in VECTOR_BACKENDS:
        blockers.append("backend_identity.backend must identify a vector backend")
    if not candidate_namespace_filter:
        blockers.append("backend_identity.index_namespace_filter is required")
    if not source_candidate_index_version:
        blockers.append("source_candidate_index_version is required")
    if source_candidate_index_version and candidate_namespace_filter != source_candidate_index_version:
        blockers.append("candidate_namespace_filter must match source_candidate_index_version")
    if args.baseline_index_version == source_candidate_index_version:
        blockers.append("baseline_index_version must differ from source_candidate_index_version")
    if build_meta.get("index_version") and build_meta.get("index_version") != source_candidate_index_version:
        blockers.append("faiss build index_version must match source_candidate_index_version")
    if not embedding_model:
        blockers.append("embedding_model is required")
    if not faiss_hash:
        blockers.append("faiss.index hash is required")
    if not gold_rows:
        blockers.append("gold query rows are required")
    if not document_version_ids:
        blockers.append("document_version_scope is required")
    for key in ("Hit@10", "MRR@10", "citation_accuracy"):
        if first_present(metrics, key, key.lower().replace("@", "_at_")) is None:
            blockers.append(f"{key} metric is required")

    descriptor = {
        "schema": SCHEMA,
        "baseline_type": BASELINE_TYPE,
        "bootstrap_status": BOOTSTRAP_STATUS,
        "immutable_baseline": True,
        "candidate_snapshot": False,
        "candidate_snapshot_baseline": False,
        "baseline_index_version": args.baseline_index_version,
        "source_candidate_index_version": source_candidate_index_version,
        "retrieval_backend": "vector",
        "backend_identity": backend_identity,
        "candidate_namespace_filter": candidate_namespace_filter,
        "eval_dataset_id": args.eval_dataset_id,
        "eval_dataset_version": args.eval_dataset_version,
        "baseline_dataset_version": args.eval_dataset_version,
        "eval_dataset_sha256": file_sha256(gold_path) if gold_path.exists() else None,
        "gold_query_row_count": len(gold_rows),
        "document_version_scope": {
            "source": "consistency_report" if consistency else "gold_queries",
            "document_version_id_count": len(document_version_ids),
            "document_version_ids": document_version_ids,
        },
        "embedding_model": embedding_model,
        "embedding_text_variant": ingest_manifest.get("embedding_text_variant"),
        "embedding_text_builder_version": ingest_manifest.get("embedding_text_builder_version"),
        "embedding_text_sha256": ingest_manifest.get("embed_text_sha256"),
        "vector_index_hash": vector_index_hash,
        "faiss_artifact_hash": faiss_hash,
        "faiss_artifact_hashes": artifact_hashes,
        "retrieval_report_path": str(retrieval_path),
        "retrieval_report_sha256": retrieval_report_sha256,
        "immutable_baseline_report_hash": retrieval_report_sha256,
        "metrics_report_path": str(metrics_path),
        "metrics_report_sha256": file_sha256(metrics_path) if metrics_path.exists() else None,
        "consistency_report_path": str(Path(args.consistency_report)),
        "consistency_report_sha256": file_sha256(Path(args.consistency_report))
        if Path(args.consistency_report).exists()
        else None,
        "candidate_scope_readiness_report_path": str(Path(args.scope_readiness_report)),
        "candidate_scope_readiness_report_sha256": file_sha256(Path(args.scope_readiness_report))
        if Path(args.scope_readiness_report).exists()
        else None,
        "created_at": utc_run_id(),
        "created_by": args.bootstrap_actor,
        "bootstrap_actor": args.bootstrap_actor,
        "bootstrap_reason": args.bootstrap_reason,
        "baseline_provenance": (
            f"initial-bootstrap:{args.baseline_index_version}:"
            f"{source_candidate_index_version}:{retrieval_report_sha256[:16] if retrieval_report_sha256 else 'missing'}"
        ),
        "promotion_evidence": False,
        "promotion_gate_effect": "none",
        "bootstrap_is_not_promotion": True,
        "current_candidate_promotion_evidence": False,
        "usable_as_baseline_for_future_candidates": True,
        "metrics": {
            "Hit@10": first_present(metrics, "Hit@10", "hit_at_10"),
            "MRR@10": first_present(metrics, "MRR@10", "mrr_at_10"),
            "hit_at_10": first_present(metrics, "hit_at_10", "Hit@10"),
            "mrr_at_10": first_present(metrics, "mrr_at_10", "MRR@10"),
            "citation_accuracy": metrics.get("citation_accuracy"),
            "citation_location_accuracy": metrics.get("citation_location_accuracy"),
            "xlsx_citation_location_accuracy": metrics.get("xlsx_citation_location_accuracy"),
            "pdf_citation_location_accuracy": metrics.get("pdf_citation_location_accuracy"),
        },
        "source_reports": [
            str(retrieval_path),
            str(metrics_path),
            str(Path(args.consistency_report)),
            str(Path(args.scope_readiness_report)),
        ],
        "guardrails": [
            "promotion_evidence=false is required",
            "library_search is rejected",
            "candidate snapshot baselines are rejected",
            "baseline_index_version must differ from source_candidate_index_version",
            "descriptor hashes retrieval, metrics, gold, and FAISS artifacts",
        ],
    }
    if scope_readiness:
        descriptor["candidate_scope_readiness_status"] = scope_readiness.get("status")
    if consistency:
        descriptor["candidate_embedding_consistency_status"] = consistency.get("status")
    return descriptor, dedupe(blockers), warnings


def document_version_scope(consistency: Mapping[str, Any], gold_rows: list[dict[str, str]]) -> list[str]:
    from_report = consistency.get("document_version_ids") if isinstance(consistency, Mapping) else None
    if isinstance(from_report, list) and from_report:
        return sorted(str(item) for item in from_report if item)
    return sorted({row.get("expected_document_version_id", "").strip() for row in gold_rows if row.get("expected_document_version_id")})


def read_gold_rows(path: Path, blockers: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        blockers.append(f"gold CSV missing: {path}")
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


def read_json(path: Path, blockers: list[str], *, label: str) -> dict[str, Any]:
    if not path.exists():
        blockers.append(f"{label} missing: {path}")
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        blockers.append(f"{label} must be a JSON object: {path}")
        return {}
    return payload


def read_optional_json(path: Path, warnings: list[str], *, label: str) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"{label} missing: {path}")
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def artifact_hash_map(index_dir: Path, names: tuple[str, ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in names:
        path = index_dir / name
        if path.exists():
            result[name] = file_sha256(path)
    return result


def combined_artifact_hash(index_dir: Path, names: tuple[str, ...]) -> str | None:
    h = hashlib.sha256()
    found = False
    for name in names:
        path = index_dir / name
        if path.exists():
            found = True
            h.update(name.encode("utf-8"))
            h.update(b"\0")
            h.update(path.read_bytes())
            h.update(b"\0")
    return h.hexdigest() if found else None


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return None


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval-report", default=str(DEFAULT_RETRIEVAL_REPORT))
    parser.add_argument("--metrics-report", default=str(DEFAULT_METRICS_REPORT))
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--vector-index-dir", default=str(DEFAULT_INDEX_DIR))
    parser.add_argument("--consistency-report", default=str(DEFAULT_CONSISTENCY_REPORT))
    parser.add_argument("--scope-readiness-report", default=str(DEFAULT_SCOPE_READINESS_REPORT))
    parser.add_argument("--descriptor-output", default=str(DEFAULT_DESCRIPTOR))
    parser.add_argument("--readiness-output", default=str(DEFAULT_READINESS))
    parser.add_argument("--baseline-index-version", default="initial-full72-vector-baseline-v0")
    parser.add_argument("--source-candidate-index-version")
    parser.add_argument("--eval-dataset-id", default="gold_queries_v0")
    parser.add_argument("--eval-dataset-version", default="full72_vector_diagnostic_v0")
    parser.add_argument("--embedding-model")
    parser.add_argument("--bootstrap-actor", default="codex")
    parser.add_argument(
        "--bootstrap-reason",
        default="No prior immutable promoted vector baseline exists for the full72 PDF/XLSX scope.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
