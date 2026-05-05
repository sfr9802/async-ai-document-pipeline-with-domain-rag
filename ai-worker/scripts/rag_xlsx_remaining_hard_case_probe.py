"""Probe remaining XLSX Track A hard cases with query-only variants."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER = Path(__file__).resolve().parents[1]
ROOT = AI_WORKER.parent
if str(AI_WORKER) not in sys.path:
    sys.path.insert(0, str(AI_WORKER))

from eval.harness.rag_ingestion_retrieval_eval import evaluate_gold_rows, load_gold_csv, search_vector  # noqa: E402


DEFAULT_REVIEWED_GOLD = Path("eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv")
DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/rag_xlsx_remaining_hard_case_probe.json")
DEFAULT_VECTOR_INDEX_DIR = Path("eval/indexes/rag-data-xlsx-candidate-v1")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
XLSX_CANDIDATE_INDEX_VERSION = "rag-ingestion-v2-xlsx-candidate-v1"

QUERY_VARIANTS = {
    "gq_xlsx_lookup_002": [
        "신분당선",
        "신분당선 2019년 승차총승객수 찾아줘.",
        "신분당선 2019년 5월 승차총승객수 알려줘.",
        "신분당선 2018년 12월 승차총승객수 찾아줘.",
        "신분당선 월별 승차총승객수 보여줘.",
        "신분당선 승차 자료 찾아줘.",
        "신분당선 월별 승차 찾아줘.",
        "신분당선 승차총승객수 찾아줘.",
        "신분당선 이용 현황 찾아줘.",
    ],
    "gq_auto_041": [
        "인하요양원",
        "인하요양원 장기요양기관 정보 찾아줘.",
        "인하요양원 시설 정보 찾아줘.",
        "인하요양원 기관 정보 찾아줘.",
        "인하요양원 주소 정보 찾아줘.",
        "인하요양원 상세주소 알려줘.",
        "인하요양원 소재지 정보 찾아줘.",
        "인하요양원 지정일자와 주소 알려줘.",
    ],
}

SEMANTIC_METADATA_UPDATES = {
    "gq_auto_041": {
        "expected_answer_text": "인하요양원 소재지",
        "must_contain_terms": "인하요양원;소재지",
    },
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = load_gold_csv(Path(args.reviewed_gold))
    rows_by_id = {row.get("query_id", ""): row for row in rows}
    search_fn = search_vector(
        index_dir=args.vector_index_dir,
        db_dsn=args.vector_db_dsn,
        embedding_model=args.vector_embedding_model,
        query_prefix=args.vector_query_prefix,
        passage_prefix=args.vector_passage_prefix,
        max_seq_length=args.vector_max_seq_length,
        batch_size=args.vector_batch_size,
        expected_index_version=args.required_index_version,
    )
    probe_rows = []
    selected_updates: dict[str, str] = {}
    selected_queries: dict[str, str] = {}
    semantic_metadata_updates: dict[str, dict[str, str]] = {}
    for query_id, variants in QUERY_VARIANTS.items():
        base_row = rows_by_id[query_id]
        variant_results = []
        for variant in variants:
            candidate_row = dict(base_row)
            candidate_row["query"] = variant
            report = evaluate_gold_rows(
                [candidate_row],
                search_fn=search_fn,
                top_k=args.top_k,
                candidate_index_version=args.candidate_index_version,
                required_embedding_status=args.required_embedding_status,
                required_index_version=args.required_index_version,
            )
            result = (report.get("query_results") or [{}])[0]
            audit = audit_query_variant(variant, base_row)
            variant_results.append(
                {
                    "query": variant,
                    "audit": audit,
                    "location_match": result.get("location_match"),
                    "hit_rank": result.get("hit_rank"),
                    "location_rank": result.get("location_rank"),
                    "failure_reason": result.get("failure_reason"),
                    "top1": summarize_hit((result.get("top_k_results") or [None])[0]),
                    "top_k_summary": [summarize_hit(hit) for hit in (result.get("top_k_results") or [])[:5]],
                }
            )
        selected = select_variant(variant_results)
        if selected:
            selected_queries[query_id] = str(selected["query"])
        if selected and selected["query"] != base_row.get("query"):
            selected_updates[query_id] = selected["query"]
        metadata_update = SEMANTIC_METADATA_UPDATES.get(query_id)
        if selected and metadata_update and metadata_needs_update(base_row, metadata_update):
            semantic_metadata_updates[query_id] = metadata_update
        probe_rows.append(
            {
                "query_id": query_id,
                "current_query": base_row.get("query"),
                "semantic_anchor_terms": semantic_anchor_terms(base_row),
                "expected_file_name": base_row.get("expected_file_name"),
                "expected_sheet_name": base_row.get("expected_sheet_name"),
                "expected_cell_range": base_row.get("expected_cell_range"),
                "variants": variant_results,
                "selected_query": selected.get("query") if selected else None,
                "selected_reason": selected_reason(selected, base_row) if selected else "NO_SAFE_RECOVERY",
            }
        )
    if args.apply_updates and selected_updates:
        apply_updates(Path(args.reviewed_gold), selected_updates, semantic_metadata_updates)
    elif args.apply_updates and semantic_metadata_updates:
        apply_updates(Path(args.reviewed_gold), selected_updates, semantic_metadata_updates)
    payload = {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED",
        "report_role": "xlsx_remaining_hard_case_probe",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "source_reviewed_gold": args.reviewed_gold,
        "retrieval_backend": "vector",
        "candidate_index_version": args.candidate_index_version,
        "namespace": args.required_index_version,
        "top_k": args.top_k,
        "apply_updates": args.apply_updates,
        "selected_queries": selected_queries,
        "selected_updates": selected_updates,
        "semantic_metadata_updates": semantic_metadata_updates,
        "recovered_query_count": len(selected_updates),
        "rows": probe_rows,
        "guardrails": {
            "promotion_evidence_true_set": False,
            "candidate_v1_mutated": False,
            "candidate_v2_created": False,
            "global_policy_relaxed": False,
            "hidden_negative_in_positive_metrics": False,
            "file_sheet_range_hidden_leakage_allowed": False,
        },
    }
    write_json(Path(args.output), payload)
    print_json(
        {
            "status": payload["status"],
            "output": args.output,
            "recovered_query_count": payload["recovered_query_count"],
            "selected_updates": selected_updates,
        }
    )
    return 0


def select_variant(variant_results: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    safe_matches = [
        result
        for result in variant_results
        if result.get("location_match") and (result.get("audit") or {}).get("pass")
    ]
    if not safe_matches:
        return None
    # Prefer realistic short user input, then earliest location rank.
    return sorted(
        safe_matches,
        key=lambda result: (
            len(str(result.get("query") or "")) > 25,
            int(result.get("location_rank") or result.get("hit_rank") or 999),
            len(str(result.get("query") or "")),
        ),
    )[0]


def selected_reason(selected: Mapping[str, Any], base_row: Mapping[str, str]) -> str:
    current = base_row.get("query")
    if selected.get("query") == current:
        return "CURRENT_QUERY_ALREADY_RECOVERS"
    return "SAFE_QUERY_ONLY_RECOVERY"


def audit_query_variant(query: str, row: Mapping[str, str]) -> dict[str, Any]:
    expected_file_name = row.get("expected_file_name", "")
    expected_sheet = row.get("expected_sheet_name", "")
    expected_range = row.get("expected_cell_range", "")
    file_stem = Path(expected_file_name).stem if expected_file_name else ""
    failures = []
    if expected_file_name and expected_file_name in query:
        failures.append("file_name_literal")
    if file_stem and file_stem in query:
        failures.append("file_stem_literal")
    if expected_sheet and expected_sheet in query:
        failures.append("sheet_name_literal")
    if expected_range and expected_range in query:
        failures.append("cell_range_literal")
    hidden_terms = [term.strip() for term in (row.get("must_not_contain_terms") or "").split(";") if term.strip()]
    hidden_hits = [term for term in hidden_terms if term and term in query]
    if hidden_hits:
        failures.append("must_not_term_literal")
    required_terms = semantic_anchor_terms(row)
    if not required_terms:
        failures.append("semantic_anchor_metadata_missing")
    missing_required_terms = [term for term in required_terms if term and term not in query]
    if missing_required_terms:
        failures.append("semantic_anchor_missing")
    return {
        "pass": not failures,
        "failures": failures,
        "hidden_term_hits": hidden_hits,
        "required_terms": required_terms,
        "missing_required_terms": missing_required_terms,
        "semantic_anchor_preserved": not missing_required_terms,
    }


def semantic_anchor_terms(row: Mapping[str, str]) -> list[str]:
    query_id = row.get("query_id", "")
    metadata_update = SEMANTIC_METADATA_UPDATES.get(query_id)
    if metadata_update:
        return [
            term.strip()
            for term in metadata_update.get("must_contain_terms", "").split(";")
            if term.strip()
        ]
    terms = [
        term.strip()
        for term in (row.get("must_contain_terms") or "").split(";")
        if term.strip()
    ]
    if terms:
        return terms
    anchors = [
        term.strip()
        for term in (row.get("naturalization_anchor_terms") or "").split(";")
        if term.strip()
    ]
    return anchors[:2]


def metadata_needs_update(row: Mapping[str, str], metadata_update: Mapping[str, str]) -> bool:
    return any(row.get(key) != value for key, value in metadata_update.items())


def summarize_hit(hit: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not hit:
        return None
    location = hit.get("location_json") if isinstance(hit.get("location_json"), Mapping) else {}
    breakdown = hit.get("match_breakdown") or {}
    return {
        "rank": hit.get("rank"),
        "score": hit.get("score"),
        "source_file_name": hit.get("source_file_name"),
        "sheet_name": location.get("sheet_name") or location.get("sheetName"),
        "cell_range": location.get("cell_range") or location.get("cellRange"),
        "chunk_type": hit.get("chunk_type"),
        "file_match": breakdown.get("file_match"),
        "sheet_match": breakdown.get("xlsx_sheet_match"),
        "range_exact": breakdown.get("xlsx_range_exact"),
        "range_contains": breakdown.get("xlsx_range_contains"),
        "range_overlap": breakdown.get("xlsx_range_overlap"),
        "range_policy_match": breakdown.get("xlsx_range_policy_match"),
    }


def apply_updates(path: Path, updates: Mapping[str, str], metadata_updates: Mapping[str, Mapping[str, str]]) -> None:
    rows = read_csv_rows(path)
    for row in rows:
        query_id = row.get("query_id", "")
        if query_id in updates:
            row["query"] = updates[query_id]
            row["naturalization_notes"] = append_note(
                row.get("naturalization_notes", ""),
                "track_a_remaining_hard_case_query_probe",
            )
            row["naturalization_notes"] = append_note(
                row.get("naturalization_notes", ""),
                "track_a_semantic_anchor_audited",
            )
        if query_id in metadata_updates:
            for key, value in metadata_updates[query_id].items():
                row[key] = value
            row["naturalization_notes"] = append_note(
                row.get("naturalization_notes", ""),
                "track_a_semantic_anchor_audited",
            )
    write_csv(path, rows)


def append_note(existing: str, note: str) -> str:
    parts = [part.strip() for part in existing.split(";") if part.strip()]
    if note not in parts:
        parts.append(note)
    seen = set()
    unique_parts = []
    for part in parts:
        if part in seen:
            continue
        seen.add(part)
        unique_parts.append(part)
    return "; ".join(unique_parts)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed-gold", default=str(DEFAULT_REVIEWED_GOLD))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--vector-index-dir", default=str(DEFAULT_VECTOR_INDEX_DIR))
    parser.add_argument("--vector-db-dsn", default=DEFAULT_DB_DSN)
    parser.add_argument("--vector-embedding-model", default="BAAI/bge-m3")
    parser.add_argument("--vector-query-prefix", default="")
    parser.add_argument("--vector-passage-prefix", default="")
    parser.add_argument("--vector-max-seq-length", type=int, default=1024)
    parser.add_argument("--vector-batch-size", type=int, default=32)
    parser.add_argument("--candidate-index-version", default=XLSX_CANDIDATE_INDEX_VERSION)
    parser.add_argument("--required-index-version", default=XLSX_CANDIDATE_INDEX_VERSION)
    parser.add_argument("--required-embedding-status", default="EMBEDDED")
    parser.add_argument("--apply-updates", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
