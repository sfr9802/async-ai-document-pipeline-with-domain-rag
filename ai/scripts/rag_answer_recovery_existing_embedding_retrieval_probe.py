"""Read-only retrieval probe over already-embedded answer recovery source rows."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent
for import_root in (SCRIPT_DIR, AI_WORKER_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import rag_answer_recovery_embedding_readiness as readiness  # noqa: E402

STAGE = "answer_recovery_existing_embedding_retrieval_probe_v1"
DEFAULT_TOP_K = 10


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = readiness.report_artifacts.with_reporting_overrides(
        readiness.load_config(readiness.resolve_path(args.config)),
        readiness.report_artifacts.reporting_overrides_from_args(args),
    )
    readiness_report_path = readiness.resolve_path(args.readiness_report)
    readiness_report = readiness.read_json(readiness_report_path)
    report = run_probe(
        config=config,
        readiness_report=readiness_report,
        top_k=int(args.top_k),
    )
    write_outputs(config, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "stage": report["stage"],
                "probe_row_count": report["summary"]["probe_row_count"],
                "target_found_top_k_count": report["summary"]["target_found_top_k_count"],
                "all_targets_found_top_k": report["summary"]["all_targets_found_top_k"],
                "vector_write_attempted": report["guardrails"]["vector_write_attempted"],
                "namespace_created": report["guardrails"]["namespace_created"],
                "production_mutation": report["guardrails"]["production_mutation"],
                "official_denominator_opened": report["guardrails"]["official_denominator_opened"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(readiness.DEFAULT_CONFIG))
    parser.add_argument(
        "--readiness-report",
        default="reports/rag_eval/rag-ingestion/answer_recovery_embedding_readiness.json",
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    readiness.report_artifacts.add_reporting_args(parser)
    return parser.parse_args(argv)


def run_probe(*, config: Mapping[str, Any], readiness_report: Mapping[str, Any], top_k: int) -> dict[str, Any]:
    backend = readiness_report.get("embedding_backend", {})
    safe_rows = list(readiness_report.get("safe_existing_rows", []))
    guardrails = guardrail_summary(config)
    if backend.get("embedding_backend_available") is not True:
        return {
            "schema_version": "answer_recovery_existing_embedding_retrieval_probe_report_v1",
            "stage": STAGE,
            "status": "DEFERRED",
            "defer_reason": "embedding backend is not confirmed available",
            "summary": {
                "probe_row_count": 0,
                "target_found_top_k_count": 0,
                "all_targets_found_top_k": False,
                "top_k": top_k,
                "query_embedding_count": 0,
                "expected_answer_or_label_embedding_count": 0,
            },
            "guardrails": guardrails,
            "rows": [],
        }

    namespace = choose_existing_namespace(safe_rows)
    index_dir = AI_WORKER_ROOT / "eval" / "indexes" / namespace
    chunks_path = index_dir / "chunks.jsonl"
    chunks = load_chunks(chunks_path)
    chunks_by_id = {str(row.get("chunk_id")): row for row in chunks if row.get("chunk_id")}
    chunks_by_faiss_row_id = {
        int(row["faiss_row_id"]): row
        for row in chunks
        if str(row.get("faiss_row_id", "")).isdigit()
    }

    provider_class, resolve_max_seq_length = readiness.import_embedding_provider()
    vector_class = readiness.import_vector_index_provider()
    settings = readiness.load_worker_settings()
    embedder = readiness.construct_canonical_embedder(
        settings=settings,
        provider_class=provider_class,
        resolve_max_seq_length=resolve_max_seq_length,
    )
    index = vector_class(index_dir)
    info = index.load()

    rows: list[dict[str, Any]] = []
    for safe_row in safe_rows:
        chunk_id = str(safe_row["chunk_id"])
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            rows.append(row_failure(safe_row, "target chunk missing from chunks.jsonl"))
            continue
        source_text = source_text_for_probe(chunk)
        if not source_text:
            rows.append(row_failure(safe_row, "target chunk has no source text"))
            continue
        query_vector = embedder.embed_queries([source_text])
        hits = index.search(query_vector, top_k)
        hit_rows = hits[0] if hits else []
        top_hits = [
            {
                "rank": rank,
                "faiss_row_id": faiss_row_id,
                "chunk_id": str(chunks_by_faiss_row_id.get(faiss_row_id, {}).get("chunk_id", "")),
                "score": score,
            }
            for rank, (faiss_row_id, score) in enumerate(hit_rows, start=1)
        ]
        target_rank = next((hit["rank"] for hit in top_hits if hit["chunk_id"] == chunk_id), None)
        rows.append(
            {
                "row_id": safe_row["row_id"],
                "chunk_id": chunk_id,
                "canonical_source_id": safe_row["canonical_source_id"],
                "namespace": namespace,
                "faiss_row_id": int(chunk["faiss_row_id"]),
                "source_text_length": len(source_text),
                "source_text_sha256": readiness.sha256_text(source_text),
                "query_text_source": "already_embedded_safe_source_chunk_text",
                "target_found_top_k": target_rank is not None,
                "target_rank": target_rank,
                "top_k": top_k,
                "top_hits": top_hits,
                "vector_write_attempted": False,
                "namespace_created": False,
            }
        )

    target_found_count = sum(1 for row in rows if row.get("target_found_top_k"))
    all_targets_found = bool(rows) and target_found_count == len(rows)
    status = "PASS" if all_targets_found and guardrails_preserved(guardrails) else "FAIL"
    return {
        "schema_version": "answer_recovery_existing_embedding_retrieval_probe_report_v1",
        "stage": STAGE,
        "status": status,
        "mode": "read_only_existing_embedding_retrieval_probe",
        "namespace": namespace,
        "index_dir": readiness.repo_relative(index_dir),
        "chunks_path": readiness.repo_relative(chunks_path),
        "index_version": info.index_version,
        "index_embedding_model": info.embedding_model,
        "index_dimension": info.dimension,
        "runtime_embedding_model": embedder.model_name,
        "runtime_embedding_dimension": embedder.dimension,
        "summary": {
            "probe_row_count": len(rows),
            "target_found_top_k_count": target_found_count,
            "all_targets_found_top_k": all_targets_found,
            "top_k": top_k,
            "query_embedding_count": len(rows),
            "expected_answer_or_label_embedding_count": 0,
        },
        "guardrails": guardrails,
        "rows": rows,
    }


def choose_existing_namespace(rows: Sequence[Mapping[str, Any]]) -> str:
    namespaces = [
        namespace
        for row in rows
        for namespace in row.get("existing_embedding_namespaces", [])
        if namespace
    ]
    if not namespaces:
        raise ValueError("No existing embedding namespace found for safe rows")
    if len(set(namespaces)) != 1:
        raise ValueError("Safe rows span multiple namespaces; keep this probe narrow")
    return namespaces[0]


def load_chunks(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def source_text_for_probe(chunk: Mapping[str, Any]) -> str:
    return str(chunk.get("text") or chunk.get("embedding_text") or chunk.get("chunk_text") or "").strip()


def row_failure(safe_row: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        "row_id": safe_row.get("row_id"),
        "chunk_id": safe_row.get("chunk_id"),
        "canonical_source_id": safe_row.get("canonical_source_id"),
        "target_found_top_k": False,
        "target_rank": None,
        "failure_reason": reason,
        "vector_write_attempted": False,
        "namespace_created": False,
    }


def guardrail_summary(config: Mapping[str, Any]) -> dict[str, Any]:
    assertions = dict(config["guardrail_assertions"])
    return {
        "official_denominator_registry_changed": False,
        "official_denominator_opened": False,
        "official_answer_denominator_opened": False,
        "production_index_mutation": False,
        "production_mutation": False,
        "broad_indexing": False,
        "frozen_gold_training_rows": 0,
        "frozen_gold_profile_selection": False,
        "expected_answer_or_label_embedding_count": 0,
        "hidden_xlsx_support_eligible_count": int(assertions.get("hidden_xlsx_support_eligible_count") or 0),
        "pdf_file_content_mixing_support_eligible_count": int(
            assertions.get("pdf_file_content_mixing_support_eligible_count") or 0
        ),
        "diagnostic_only_support_eligible_count": int(assertions.get("diagnostic_only_support_eligible_count") or 0),
        "production_promotion_ready": False,
        "official_answer_denominator_ready": False,
        "vector_write_attempted": False,
        "namespace_created": False,
    }


def guardrails_preserved(guardrails: Mapping[str, Any]) -> bool:
    return (
        not guardrails["official_denominator_registry_changed"]
        and not guardrails["official_denominator_opened"]
        and not guardrails["official_answer_denominator_opened"]
        and not guardrails["production_index_mutation"]
        and not guardrails["production_mutation"]
        and not guardrails["broad_indexing"]
        and guardrails["frozen_gold_training_rows"] == 0
        and not guardrails["frozen_gold_profile_selection"]
        and guardrails["expected_answer_or_label_embedding_count"] == 0
        and guardrails["hidden_xlsx_support_eligible_count"] == 0
        and guardrails["pdf_file_content_mixing_support_eligible_count"] == 0
        and guardrails["diagnostic_only_support_eligible_count"] == 0
        and not guardrails["production_promotion_ready"]
        and not guardrails["official_answer_denominator_ready"]
        and not guardrails["vector_write_attempted"]
        and not guardrails["namespace_created"]
    )


def write_outputs(config: Mapping[str, Any], report: Mapping[str, Any]) -> None:
    options = readiness.report_artifacts.reporting_options(config)
    paths = config["report_paths"]
    json_path = readiness.resolve_path(
        paths.get(
            "existing_embedding_retrieval_probe_json",
            "reports/rag_eval/rag-ingestion/answer_recovery_existing_embedding_retrieval_probe.json",
        )
    )
    md_path = readiness.resolve_path(
        paths.get(
            "existing_embedding_retrieval_probe_md",
            "reports/rag_eval/rag-ingestion/answer_recovery_existing_embedding_retrieval_probe.md",
        )
    )
    csv_path = readiness.resolve_path(
        paths.get(
            "existing_embedding_retrieval_probe_csv",
            "reports/rag_eval/rag-ingestion/answer_recovery_existing_embedding_retrieval_probe.csv",
        )
    )
    if options["emit_stage_reports"]:
        readiness.write_json(json_path, report)
        readiness.write_text(md_path, render_md(report))
    if options["emit_csv"]:
        write_rows_csv(csv_path, report["rows"])


def render_md(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Answer Recovery Existing Embedding Retrieval Probe",
        "",
        f"- Status: `{report['status']}`.",
        f"- Stage: `{report['stage']}`.",
        f"- Namespace: `{report.get('namespace', '')}`.",
        f"- Probe rows: `{summary['probe_row_count']}`.",
        f"- Target found top-k: `{summary['target_found_top_k_count']}`.",
        f"- All targets found top-k: `{summary['all_targets_found_top_k']}`.",
        f"- Query embedding count: `{summary['query_embedding_count']}`.",
        "- Vector write attempted: `false`.",
        "- Namespace created: `false`.",
        "- Production mutation: `false`.",
        "- Official denominator opened: `false`.",
        "",
        "## Rows",
        "",
    ]
    for row in report["rows"]:
        lines.append(
            f"- `{row['row_id']}` chunk=`{row['chunk_id']}` "
            f"target_found_top_k=`{row['target_found_top_k']}` target_rank=`{row['target_rank']}`"
        )
    lines.extend(["", "## Guardrails", ""])
    for key, value in report["guardrails"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def write_rows_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "row_id",
        "chunk_id",
        "canonical_source_id",
        "namespace",
        "faiss_row_id",
        "source_text_length",
        "source_text_sha256",
        "query_text_source",
        "target_found_top_k",
        "target_rank",
        "top_k",
        "vector_write_attempted",
        "namespace_created",
        "failure_reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: readiness.serialize_csv_value(row.get(key, "")) for key in fieldnames})


if __name__ == "__main__":
    sys.exit(main())
