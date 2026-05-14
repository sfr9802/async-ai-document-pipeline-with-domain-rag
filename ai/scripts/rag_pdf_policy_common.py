from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


PDF_CANDIDATE_NAMESPACE = "rag-ingestion-v2-pdf-candidate-v1"
PDF_ARTIFACT_DIR = "rag-data-pdf-candidate-v1"
EVIDENCE_ROLE = "diagnostic"

DECISIONS = {
    "ACCEPT_PAGE_WITH_OPTIONAL_BBOX",
    "ACCEPT_CHUNK_TYPE_POLICY_RELABEL",
    "DEFER_TO_TABLE_EXTRACTION",
    "EXCLUDE_FROM_POSITIVE_METRIC",
    "KEEP_AS_FAILURE",
    "REQUIRE_GOLD_BINDING_FIX",
}

TRUE_RANKING_TYPES = {
    "PDF_EXPECTED_FILE_ABSENT_IN_TOP10",
    "PDF_EXPECTED_PAGE_ABSENT_IN_TOP10",
    "PDF_TRUE_RETRIEVAL_RANKING_FAILURE",
}

REVIEWED_MANIFEST_COLUMNS = [
    "query_id",
    "bucket",
    "query",
    "expected_file_name",
    "expected_document_version_id",
    "expected_chunk_type",
    "expected_location_type",
    "expected_physical_page_index",
    "expected_page_no",
    "expected_page_label",
    "expected_bbox",
    "expected_answer_text",
    "must_contain_terms",
    "source_sample_id",
    "label_status",
    "pdf_review_label",
    "pdf_match_policy",
    "pdf_table_policy",
    "pdf_bbox_policy",
    "review_decision",
    "positive_metric_eligible",
    "notes",
]


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON report must be an object: {path}")
    return payload


def read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv_rows(path: Path, rows: list[Mapping[str, Any]], *, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fieldnames})


def csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n", ""}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def bool_cell(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def clean(value: Any) -> str:
    return str(value or "").strip()


def to_int(value: Any) -> int | None:
    text = clean(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def counter_dict(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean(row.get(key)) or "UNKNOWN"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def artifact_identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() and path.is_file() else None,
    }


def report_ref(report: Mapping[str, Any], path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() and path.is_file() else None,
        "status": report.get("status"),
        "promotion_evidence": report.get("promotion_evidence"),
        "evidence_role": report.get("evidence_role"),
    }


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def mean_bool(values: list[bool]) -> float:
    if not values:
        return 0.0
    return round(sum(1 for value in values if value) / len(values), 4)


def hit_at(ranks: list[int | None], k: int) -> float:
    if not ranks:
        return 0.0
    return round(sum(1 for rank in ranks if rank is not None and rank <= k) / len(ranks), 4)


def mrr_at(ranks: list[int | None], k: int) -> float:
    if not ranks:
        return 0.0
    total = 0.0
    for rank in ranks:
        if rank is not None and rank <= k:
            total += 1.0 / rank
    return round(total / len(ranks), 4)


def location(hit: Mapping[str, Any]) -> Mapping[str, Any]:
    value = hit.get("location_json")
    return value if isinstance(value, Mapping) else {}


def match_breakdown(hit: Mapping[str, Any]) -> Mapping[str, Any]:
    value = hit.get("match_breakdown")
    return value if isinstance(value, Mapping) else {}


def hit_rank(hit: Mapping[str, Any]) -> int | None:
    return to_int(hit.get("rank"))


def expected_page(row: Mapping[str, Any]) -> int | None:
    return to_int(row.get("expected_page_no") or ((row.get("expected") or {}).get("page_no") if isinstance(row.get("expected"), Mapping) else None))


def expected_physical_page(row: Mapping[str, Any]) -> int | None:
    return to_int(
        row.get("expected_physical_page_index")
        or ((row.get("expected") or {}).get("physical_page_index") if isinstance(row.get("expected"), Mapping) else None)
    )


def expected_docv(row: Mapping[str, Any]) -> str:
    expected = row.get("expected") if isinstance(row.get("expected"), Mapping) else {}
    return clean(row.get("expected_document_version_id") or expected.get("document_version_id"))


def expected_file(row: Mapping[str, Any]) -> str:
    expected = row.get("expected") if isinstance(row.get("expected"), Mapping) else {}
    return clean(row.get("expected_file_name") or expected.get("file_name"))


def hit_file_match(hit: Mapping[str, Any], expected_name: str) -> bool:
    breakdown = match_breakdown(hit)
    if "file_match" in breakdown:
        return bool(breakdown.get("file_match"))
    return not expected_name or clean(hit.get("source_file_name")) == expected_name


def hit_docv_match(hit: Mapping[str, Any], expected_document_version_id: str) -> bool:
    breakdown = match_breakdown(hit)
    if "document_version_match" in breakdown:
        return bool(breakdown.get("document_version_match"))
    loc = location(hit)
    actual = clean(
        hit.get("document_version_id")
        or loc.get("document_version_id")
        or loc.get("documentVersionId")
    )
    return not expected_document_version_id or actual == expected_document_version_id


def hit_page_match(hit: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    breakdown = match_breakdown(hit)
    if "pdf_page_match" in breakdown:
        return bool(breakdown.get("pdf_page_match"))
    loc = location(hit)
    page_no = expected_page(row)
    physical = expected_physical_page(row)
    if page_no is not None and to_int(loc.get("page_no")) != page_no:
        return False
    if physical is not None and to_int(loc.get("physical_page_index")) != physical:
        return False
    return page_no is not None or physical is not None


def summarize_top_hit(hit: Mapping[str, Any]) -> dict[str, Any]:
    loc = location(hit)
    br = match_breakdown(hit)
    return {
        "rank": hit.get("rank"),
        "score": hit.get("score"),
        "search_unit_id": hit.get("search_unit_id"),
        "source_file_name": hit.get("source_file_name"),
        "chunk_type": hit.get("chunk_type"),
        "page_no": loc.get("page_no"),
        "physical_page_index": loc.get("physical_page_index"),
        "page_label": loc.get("page_label"),
        "bbox_present": bool(loc.get("bbox")),
        "file_match": br.get("file_match"),
        "document_version_match": br.get("document_version_match"),
        "chunk_type_match": br.get("chunk_type_match"),
        "pdf_page_match": br.get("pdf_page_match"),
        "pdf_bbox_overlap": br.get("pdf_bbox_overlap"),
        "pdf_exact_bbox": br.get("pdf_exact_bbox"),
        "location_match": br.get("location_match"),
        "citation_text": hit.get("citation_text"),
    }
