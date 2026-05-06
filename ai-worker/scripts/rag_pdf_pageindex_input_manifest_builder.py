"""Build diagnostic-only PageIndex PDF comparison inputs.

The manifest is a read-only bridge from the existing Track C PDF evidence to a
PageIndex page/section navigation experiment. It keeps XLSX out of scope and
does not run retrieval, indexing, promotion, or PageIndex itself.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER = SCRIPT_DIR.parent
ROOT = AI_WORKER.parent

DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_pdf_v1_review_draft.csv")
DEFAULT_C5_REPORT = Path("eval/reports/rag-ingestion/rag_retrieval_eval_pdf_vector_diagnostic_report.json")
DEFAULT_C6_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_vector_quality_breakdown.json")
DEFAULT_C7_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_gold_policy_review.json")
DEFAULT_C7_DECISION_PACK = Path("eval/reports/rag-ingestion/rag_pdf_c7_decision_pack.csv")
DEFAULT_OUTPUT_ROOT = Path("eval/artifacts/eval_runs")
DEFAULT_SEARCH_ROOTS = (
    Path("eval/datasets"),
    Path("datasets"),
    Path("local-storage"),
)

GUARDRAILS = {
    "promotion_evidence": False,
    "evidence_role": "diagnostic",
    "xlsx_scope_excluded": True,
    "pdf_scope_only": True,
    "live_pageindex_run": False,
    "external_cloud_llm_run": False,
    "bbox_contract_success_not_claimed": True,
    "table_semantics_success_not_claimed": True,
    "pdf_c7_policy_decision_applied": False,
    "retrieval_tuning_applied": False,
    "parser_expansion_applied": False,
    "official_denominator_changed": False,
}

PDF_PAGEINDEX_COMPARISON_NOTES = (
    "Manifest builder is diagnostic-only and does not run PageIndex.",
    "XLSX rows are excluded; XLSX Track A remains hidden-safe v2 plus vector retrieval plus answer evidence serialization.",
    "PageIndex is evaluated only as a PDF page/section navigator candidate.",
    "bbox, table semantics, and C7 gold policy are not claimed as solved by this manifest.",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    blockers: list[str] = []
    warnings: list[str] = []

    gold_path = resolve_existing_path(Path(args.gold))
    c5_path = resolve_existing_path(Path(args.c5_report))
    c6_path = resolve_existing_path(Path(args.c6_report))
    c7_path = resolve_existing_path(Path(args.c7_report))
    c7_pack_path = resolve_existing_path(Path(args.c7_decision_pack))
    output_root = resolve_output_root(Path(args.output_root))
    run_id = args.run_id or utc_run_id()
    artifact_dir = output_root / f"pdf_pageindex_comparison_{run_id}"

    gold_rows = read_csv(gold_path, blockers, "gold")
    c5_report = read_json(c5_path, blockers, "c5_report")
    c6_report = read_json(c6_path, blockers, "c6_report")
    c7_report = read_json(c7_path, blockers, "c7_report")
    c7_pack_rows = read_csv(c7_pack_path, blockers, "c7_decision_pack")

    search_roots = [resolve_search_root(Path(item)) for item in args.search_root]
    payload = build_manifest(
        run_id=run_id,
        artifact_dir=artifact_dir,
        gold_path=gold_path,
        c5_path=c5_path,
        c6_path=c6_path,
        c7_path=c7_path,
        c7_pack_path=c7_pack_path,
        gold_rows=gold_rows,
        c5_report=c5_report,
        c6_report=c6_report,
        c7_report=c7_report,
        c7_pack_rows=c7_pack_rows,
        search_roots=search_roots,
        blockers=blockers,
        warnings=warnings,
    )

    write_outputs(artifact_dir, payload)
    print_json(summary_for_stdout(payload))
    return 0 if payload["status"] in {"READY_FOR_PAGEINDEX_RUN", "READY_WITH_WARNINGS"} else 2


def build_manifest(
    *,
    run_id: str,
    artifact_dir: Path,
    gold_path: Path,
    c5_path: Path,
    c6_path: Path,
    c7_path: Path,
    c7_pack_path: Path,
    gold_rows: list[dict[str, str]],
    c5_report: Mapping[str, Any],
    c6_report: Mapping[str, Any],
    c7_report: Mapping[str, Any],
    c7_pack_rows: list[dict[str, str]],
    search_roots: list[Path],
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    validate_guardrail_source("c5_report", c5_report, blockers)
    validate_guardrail_source("c6_report", c6_report, blockers)
    validate_guardrail_source("c7_report", c7_report, blockers)

    c5_by_id = rows_by_query_id(c5_report.get("query_results") or [])
    c6_by_id = rows_by_query_id(c6_report.get("query_breakdown") or [])
    c7_by_id = rows_by_query_id(c7_report.get("c7_review_rows") or [])
    c7_pack_by_id = rows_by_query_id(c7_pack_rows)
    pdf_index = build_pdf_index(search_roots)

    included_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    missing_pdf_path_query_ids: list[str] = []
    c7_policy_pending_query_ids: list[str] = []

    for gold in gold_rows:
        query_id = str(gold.get("query_id") or "").strip()
        expected_type = str(gold.get("expected_location_type") or "").strip().lower()
        bucket = str(gold.get("bucket") or "").strip()
        if expected_type != "pdf" and not bucket.startswith("pdf"):
            excluded_rows.append({
                "query_id": query_id,
                "bucket": bucket,
                "expected_location_type": expected_type,
                "exclusion_reason": "xlsx_or_non_pdf_row_excluded_from_pageindex_pdf_comparison",
            })
            continue

        c5 = c5_by_id.get(query_id, {})
        c6 = c6_by_id.get(query_id, {})
        c7 = c7_by_id.get(query_id, {})
        c7_pack = c7_pack_by_id.get(query_id, {})
        expected_file = first_non_empty(
            gold.get("expected_file_name"),
            nested(c6, "expected", "file_name"),
            c5.get("expected_file_name"),
            c7_pack.get("expected_file_name"),
        )
        pdf_match = find_pdf_path(expected_file, pdf_index)
        if not pdf_match.get("found"):
            missing_pdf_path_query_ids.append(query_id)
        c7_policy = c7_policy_state(c7, c7_pack)
        if c7_policy["c7_policy_pending"]:
            c7_policy_pending_query_ids.append(query_id)

        included_rows.append({
            "query_id": query_id,
            "bucket": bucket,
            "query": first_non_empty(gold.get("query"), c5.get("query"), c6.get("query"), c7_pack.get("query_text")),
            "expected_file": expected_file,
            "expected_document_version_id": first_non_empty(
                gold.get("expected_document_version_id"),
                nested(c6, "expected", "document_version_id"),
                c7_pack.get("expected_document_version_id"),
            ),
            "expected_page_no": to_int(first_non_empty(gold.get("expected_page_no"), nested(c6, "expected", "page_no"))),
            "expected_physical_page_index": to_int(first_non_empty(
                gold.get("expected_physical_page_index"),
                nested(c6, "expected", "physical_page_index"),
            )),
            "expected_page_label": first_non_empty(gold.get("expected_page_label"), nested(c6, "expected", "page_label")),
            "expected_bbox": parse_jsonish(first_non_empty(gold.get("expected_bbox"), nested(c6, "expected", "bbox"))),
            "expected_bbox_raw": first_non_empty(gold.get("expected_bbox"), nested(c6, "expected", "bbox")),
            "expected_chunk_type": first_non_empty(gold.get("expected_chunk_type"), nested(c6, "expected", "chunk_type")),
            "expected_location_type": first_non_empty(gold.get("expected_location_type"), nested(c6, "expected", "location_type")),
            "expected_table_id": gold.get("expected_table_id") or c7_pack.get("expected_table_id") or "",
            "expected_answer_text": gold.get("expected_answer_text") or c7_pack.get("expected_answer_text") or "",
            "must_contain_terms": split_terms(gold.get("must_contain_terms") or c7_pack.get("must_contain_terms") or ""),
            "must_not_contain_terms": split_terms(gold.get("must_not_contain_terms") or ""),
            "label_status": gold.get("label_status") or c5.get("label_status") or c6.get("label_status") or "",
            "source_sample_id": gold.get("source_sample_id") or "",
            "pdf_path_found": bool(pdf_match.get("found")),
            "pdf_path": pdf_match.get("path"),
            "pdf_path_resolution": pdf_match,
            "c5": c5_summary(c5),
            "c6_failure_type": c6.get("failure_type") or c7.get("c6_failure_type") or c7_pack.get("c6_failure_type") or "",
            "c6_failure_types": failure_types(c6, c7, c7_pack),
            "c6_primary_group": c6.get("primary_group") or c6.get("primary_disposition") or c7_pack.get("c6_primary_disposition") or "",
            "c6_primary_disposition": c6.get("primary_disposition") or c7.get("c6_primary_disposition") or c7_pack.get("c6_primary_disposition") or "",
            "c7_policy_group": c7_policy["c7_policy_group"],
            "c7_policy_pending": c7_policy["c7_policy_pending"],
            "c7_primary_classification": c7_policy["c7_primary_classification"],
            "c7_decision_group": c7_policy["c7_decision_group"],
            "codex_policy_decision_applied": False,
            "pageindex_scope_role": "pdf_page_section_navigation_candidate",
        })

    counts = {
        "gold_row_count": len(gold_rows),
        "included_pdf_row_count": len(included_rows),
        "excluded_non_pdf_row_count": len(excluded_rows),
        "missing_pdf_path_count": len(missing_pdf_path_query_ids),
        "pdf_path_found_count": len(included_rows) - len(missing_pdf_path_query_ids),
        "unique_expected_pdf_count": len({row["expected_file"] for row in included_rows if row.get("expected_file")}),
        "c7_policy_pending_count": len(c7_policy_pending_query_ids),
        "bucket_counts": dict(sorted(Counter(row["bucket"] for row in included_rows).items())),
        "c6_failure_type_counts": dict(sorted(Counter(row["c6_failure_type"] or "UNKNOWN" for row in included_rows).items())),
    }
    if len(included_rows) != 22:
        warnings.append(f"Expected 22 PDF review draft rows; got {len(included_rows)}")
    if excluded_rows:
        warnings.append(f"Excluded {len(excluded_rows)} non-PDF rows from PageIndex comparison")

    status = "READY_FOR_PAGEINDEX_RUN"
    if blockers:
        status = "FAIL_CLOSED_INPUT_ARTIFACT_ERROR"
    elif missing_pdf_path_query_ids:
        status = "FAIL_CLOSED_MISSING_PDF_PATHS"
    elif warnings:
        status = "READY_WITH_WARNINGS"

    documents = document_rows(included_rows)
    manifest_path = artifact_dir / "pageindex_pdf_input_manifest.json"
    queries_path = artifact_dir / "pageindex_pdf_queries.jsonl"
    return {
        "schema_version": "pdf_pageindex_comparison_manifest_v1",
        "run_id": run_id,
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "PageIndex PDF comparison manifest",
        "source_file_type": "PDF",
        **GUARDRAILS,
        "artifact_dir": display_path(artifact_dir),
        "output_artifacts": {
            "manifest_json": display_path(manifest_path),
            "queries_jsonl": display_path(queries_path),
        },
        "input_artifacts": [
            artifact_identity(gold_path),
            artifact_identity(c5_path),
            artifact_identity(c6_path),
            artifact_identity(c7_path),
            artifact_identity(c7_pack_path),
        ],
        "search_roots": [
            {"path": display_path(root), "exists": root.exists()}
            for root in search_roots
        ],
        "pageindex_role": "pdf_page_section_navigator_candidate_only",
        "scope_exclusions": {
            "xlsx_pageindex_adapter": "excluded",
            "xlsx_retrieval_indexing_changes": "excluded",
            "pdf_parser_expansion": "excluded",
            "retrieval_tuning": "excluded",
            "promotion": "excluded",
        },
        "counts": counts,
        "missing_pdf_path_query_ids": missing_pdf_path_query_ids,
        "c7_policy_pending_query_ids": c7_policy_pending_query_ids,
        "excluded_rows": excluded_rows,
        "documents": documents,
        "queries": included_rows,
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "notes": list(PDF_PAGEINDEX_COMPARISON_NOTES),
    }


def validate_guardrail_source(label: str, payload: Mapping[str, Any], blockers: list[str]) -> None:
    if not payload:
        return
    if payload.get("promotion_evidence") is not False:
        blockers.append(f"{label} must keep promotion_evidence=false")
    if payload.get("evidence_role") not in {None, "diagnostic"}:
        blockers.append(f"{label} must keep evidence_role=diagnostic when present")


def build_pdf_index(search_roots: list[Path]) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for root in search_roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in root.rglob("*.pdf"):
            if ".tmp" in path.parts:
                continue
            index.setdefault(path.name, []).append(path.resolve())
            match = re.match(r"^[0-9a-fA-F-]{36}-(.+\.pdf)$", path.name)
            if match:
                index.setdefault(match.group(1), []).append(path.resolve())
    for name, paths in index.items():
        paths.sort(key=pdf_path_preference)
    return index


def pdf_path_preference(path: Path) -> tuple[int, int, str]:
    text = path.as_posix()
    if "/eval/datasets/" in text:
        return (0, len(text), text)
    if "/datasets/" in text:
        return (1, len(text), text)
    if "/local-storage/" in text:
        return (2, len(text), text)
    return (3, len(text), text)


def find_pdf_path(expected_file: str, pdf_index: Mapping[str, list[Path]]) -> dict[str, Any]:
    if not expected_file:
        return {
            "found": False,
            "reason": "missing_expected_file_name",
            "path": None,
            "candidate_count": 0,
            "candidates": [],
        }
    candidates = list(pdf_index.get(expected_file) or [])
    if not candidates:
        return {
            "found": False,
            "reason": "expected_pdf_not_found_in_search_roots",
            "path": None,
            "candidate_count": 0,
            "candidates": [],
        }
    selected = candidates[0]
    return {
        "found": True,
        "reason": "exact_or_local_storage_suffix_match",
        "path": display_path(selected),
        "candidate_count": len(candidates),
        "candidates": [display_path(path) for path in candidates[:10]],
    }


def c5_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    top_hits = list(row.get("top_k_results") or [])
    return {
        "failure_reason": row.get("failure_reason"),
        "final_match_outcome": row.get("final_match_outcome"),
        "hit_rank": row.get("hit_rank"),
        "location_rank": row.get("location_rank"),
        "location_match": row.get("location_match"),
        "top_k_count": len(top_hits),
        "vector_page_hit": vector_page_hit(top_hits),
        "top_k_page_summary": summarize_top_k(top_hits),
    }


def vector_page_hit(top_hits: list[Mapping[str, Any]]) -> bool:
    return any(bool(((hit.get("match_breakdown") or {}).get("pdf_page_match"))) for hit in top_hits)


def summarize_top_k(top_hits: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for hit in top_hits[:10]:
        loc = hit.get("location_json") or {}
        br = hit.get("match_breakdown") or {}
        rows.append({
            "rank": hit.get("rank"),
            "source_file_name": hit.get("source_file_name"),
            "chunk_type": hit.get("chunk_type"),
            "page_no": loc.get("page_no"),
            "physical_page_index": loc.get("physical_page_index"),
            "bbox_present": bool(loc.get("bbox")),
            "score": hit.get("score"),
            "file_match": br.get("file_match"),
            "document_version_match": br.get("document_version_match"),
            "pdf_page_match": br.get("pdf_page_match"),
            "pdf_bbox_overlap": br.get("pdf_bbox_overlap"),
            "identity_match": br.get("identity_match"),
            "location_match": br.get("location_match"),
        })
    return rows


def c7_policy_state(c7: Mapping[str, Any], c7_pack: Mapping[str, Any]) -> dict[str, Any]:
    primary = str(c7.get("primary_c7_classification") or c7_pack.get("c7_primary_classification") or "").strip()
    decision_group = str(c7_pack.get("decision_group") or "").strip()
    human_decision_required = as_bool(c7.get("human_decision_required")) or bool(c7_pack.get("user_decision_needed_items"))
    if primary or decision_group or human_decision_required:
        group = decision_group or primary or "c7_policy_review_required"
        return {
            "c7_policy_group": group,
            "c7_policy_pending": True,
            "c7_primary_classification": primary,
            "c7_decision_group": decision_group,
        }
    return {
        "c7_policy_group": "not_in_c7_review",
        "c7_policy_pending": False,
        "c7_primary_classification": "",
        "c7_decision_group": "",
    }


def failure_types(c6: Mapping[str, Any], c7: Mapping[str, Any], c7_pack: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for source in (
        c6.get("failure_types"),
        c7.get("c6_failure_types"),
        c7_pack.get("c6_failure_types"),
        c6.get("failure_type"),
        c7.get("c6_failure_type"),
        c7_pack.get("c6_failure_type"),
    ):
        if isinstance(source, list):
            values.extend(str(item) for item in source if item)
        elif source:
            values.extend(re.split(r"[|;,]", str(source)))
    return dedupe([value.strip() for value in values if value and value.strip()])


def document_rows(query_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    for row in query_rows:
        key = str(row.get("expected_file") or "")
        if not key:
            key = f"missing:{row.get('query_id')}"
        doc = docs.setdefault(key, {
            "expected_file": row.get("expected_file"),
            "expected_document_version_ids": [],
            "pdf_path_found": row.get("pdf_path_found"),
            "pdf_path": row.get("pdf_path"),
            "query_ids": [],
            "expected_pages": [],
        })
        if row.get("expected_document_version_id") and row.get("expected_document_version_id") not in doc["expected_document_version_ids"]:
            doc["expected_document_version_ids"].append(row.get("expected_document_version_id"))
        doc["query_ids"].append(row.get("query_id"))
        if row.get("expected_page_no") is not None:
            doc["expected_pages"].append(row.get("expected_page_no"))
    result = []
    for doc in docs.values():
        doc["query_count"] = len(doc["query_ids"])
        doc["expected_pages"] = sorted(set(doc["expected_pages"]))
        result.append(doc)
    return sorted(result, key=lambda item: str(item.get("expected_file") or ""))


def rows_by_query_id(rows: Any) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if isinstance(row, Mapping):
            query_id = str(row.get("query_id") or "").strip()
            if query_id:
                result[query_id] = row
    return result


def nested(row: Mapping[str, Any], *keys: str) -> Any:
    value: Any = row
    for key in keys:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def first_non_empty(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def split_terms(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[;|]", value) if item.strip()]


def parse_jsonish(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, (list, dict)):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def write_outputs(artifact_dir: Path, payload: Mapping[str, Any]) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = artifact_dir / "pageindex_pdf_input_manifest.json"
    queries_path = artifact_dir / "pageindex_pdf_queries.jsonl"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with queries_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in payload.get("queries") or []:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def summary_for_stdout(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "artifact_dir": payload.get("artifact_dir"),
        "manifest_json": (payload.get("output_artifacts") or {}).get("manifest_json"),
        "queries_jsonl": (payload.get("output_artifacts") or {}).get("queries_jsonl"),
        "counts": payload.get("counts"),
        "blockers": payload.get("blockers"),
        "warnings": payload.get("warnings"),
    }


def read_json(path: Path, blockers: list[str], label: str) -> dict[str, Any]:
    if not path.exists():
        blockers.append(f"{label} missing: {display_path(path)}")
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        blockers.append(f"{label} must be a JSON object: {display_path(path)}")
        return {}
    return payload


def read_csv(path: Path, blockers: list[str], label: str) -> list[dict[str, str]]:
    if not path.exists():
        blockers.append(f"{label} CSV missing: {display_path(path)}")
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def artifact_identity(path: Path) -> dict[str, Any]:
    return {
        "path": display_path(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() and path.is_file() else None,
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_existing_path(path: Path) -> Path:
    candidates = candidate_paths(path)
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def resolve_output_root(path: Path) -> Path:
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0] == "eval":
        return (AI_WORKER / path).resolve()
    if parts and parts[0] == "ai-worker":
        return (ROOT / path).resolve()
    return (Path.cwd() / path).resolve()


def resolve_search_root(path: Path) -> Path:
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0] == "eval":
        return (AI_WORKER / path).resolve()
    if parts and parts[0] == "ai-worker":
        return (ROOT / path).resolve()
    return (ROOT / path).resolve()


def candidate_paths(path: Path) -> list[Path]:
    if path.is_absolute():
        return [path]
    paths: list[Path] = []
    parts = path.parts
    if parts and parts[0] == "eval":
        paths.append(AI_WORKER / path)
    if parts and parts[0] == "ai-worker":
        paths.append(ROOT / path)
    paths.extend([Path.cwd() / path, AI_WORKER / path, ROOT / path])
    result: list[Path] = []
    for candidate in paths:
        if candidate not in result:
            result.append(candidate)
    return result


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--c5-report", default=str(DEFAULT_C5_REPORT))
    parser.add_argument("--c6-report", default=str(DEFAULT_C6_REPORT))
    parser.add_argument("--c7-report", default=str(DEFAULT_C7_REPORT))
    parser.add_argument("--c7-decision-pack", default=str(DEFAULT_C7_DECISION_PACK))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--search-root",
        action="append",
        default=[str(item) for item in DEFAULT_SEARCH_ROOTS],
        help="PDF search root. May be passed multiple times.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
