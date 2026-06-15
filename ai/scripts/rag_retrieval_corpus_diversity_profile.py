"""Profile retrieval corpus diversity and overfit risk by lane.

This is a diagnostic/report-only profiler. It reads query metadata, local
corpus/index metadata, and optional read-only ragmeta rows; it never mutates
indexes, writes vectors, changes denominator registries, runs Optuna, or asks
an LLM to judge labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only in stripped envs.
    yaml = None  # type: ignore[assignment]


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent

DEFAULT_CONFIG = AI_WORKER_ROOT / "eval" / "configs" / "retrieval_corpus_diversity_profile.yaml"
DEFAULT_REPORT_JSON = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "retrieval_corpus_diversity_profile.json"
DEFAULT_REPORT_MD = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "retrieval_corpus_diversity_profile.md"

RISK_LOW = "LOW_DIVERSITY_HIGH_OVERFIT_RISK"
RISK_MODERATE = "MODERATE_DIVERSITY"
RISK_SUFFICIENT = "SUFFICIENT_DIVERSITY_FOR_DIAGNOSTIC"
RISK_UNKNOWN = "UNKNOWN_INSUFFICIENT_METADATA"

PDF_FILE_IDENTITY_ONLY_POLICY = "file_identity_only_no_content_page_bbox_table_row_column_value_support"

TEXT_SPLIT_RE = re.compile(r"[\s,;|]+")
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
YEAR_RE = re.compile(r"(?:19|20)\d{2}")
MONTH_RE = re.compile(r"(?<!\d)(?:0?[1-9]|1[0-2])(?!\d)")


@dataclass(frozen=True)
class ChunkProfile:
    chunk_id: str
    source_document_id: str
    document_family: str
    source_artifact_id: str
    parser_version: str
    embedding_text: str
    bm25_text: str
    citation_text: str
    location_json_available: bool
    citation_text_available: bool
    table_metadata_available: bool
    header_metadata_available: bool
    raw_text_for_duplicate: str


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(resolve_path(args.config))
    report = build_report(config)
    json_path = resolve_path(args.output_json or config.get("outputs", {}).get("json") or DEFAULT_REPORT_JSON)
    md_path = resolve_path(args.output_md or config.get("outputs", {}).get("markdown") or DEFAULT_REPORT_MD)
    write_json(json_path, report)
    write_text(md_path, render_markdown(report))
    print(json.dumps({
        "status": report["status"],
        "phase2_recommendation": report["phase2_recommendation"],
        "output_json": repo_relative(json_path),
        "output_md": repo_relative(md_path),
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"PASS", "PASS_WITH_RISK"} else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-md", default=None)
    return parser.parse_args(argv)


def load_config(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("pyyaml is required to load retrieval corpus diversity config")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"config must be a mapping: {path}")
    return raw


def build_report(config: Mapping[str, Any]) -> dict[str, Any]:
    lanes = config.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        raise ValueError("config.lanes must be a non-empty list")

    lane_reports: dict[str, Any] = {}
    for lane_cfg in lanes:
        if not isinstance(lane_cfg, Mapping):
            raise ValueError("each lane config must be a mapping")
        lane_report = profile_lane(lane_cfg, config)
        lane_reports[lane_report["lane"]] = lane_report

    classifications = Counter(report["classification"] for report in lane_reports.values())
    metadata_gap_count = sum(len(report["metadata_gaps"]) for report in lane_reports.values())
    phase2 = phase2_recommendation(lane_reports)
    status = "PASS_WITH_RISK" if classifications.get(RISK_LOW) or classifications.get(RISK_UNKNOWN) else "PASS"
    return {
        "schema_version": "retrieval_corpus_diversity_profile_v1",
        "task": "rag_retrieval_corpus_diversity_profile_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        "scope": "diagnostic_report_only",
        "production_index_mutation": False,
        "vector_write_attempted": False,
        "official_denominator_registry_changed": False,
        "hidden_xlsx_exposed": False,
        "local_llm_used_for_labels_or_judgments": False,
        "optuna_run": False,
        "pdf_file_lookup_policy": PDF_FILE_IDENTITY_ONLY_POLICY,
        "diagnostic_source_contract": diagnostic_source_contract(config),
        "lanes": lane_reports,
        "classification_counts": dict(sorted(classifications.items())),
        "metadata_gap_count": metadata_gap_count,
        "phase2_recommendation": phase2["decision"],
        "phase2_can_proceed": phase2["can_proceed"],
        "phase2_conditions": phase2["conditions"],
    }


def profile_lane(lane_cfg: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    lane = required_str(lane_cfg, "name")
    identity_only = bool(lane_cfg.get("identity_only"))
    hidden_redaction = bool(lane_cfg.get("hidden_xlsx_redaction"))
    query_rows = load_query_rows(lane_cfg.get("query_sources", []))
    chunks = [] if identity_only else load_chunk_profiles(lane_cfg, config)

    query_texts = [clean_text(row.get("query")) for row in query_rows if clean_text(row.get("query"))]
    query_duplicates = duplicate_profile(query_texts)
    query_near_duplicates = near_duplicate_profile(query_texts)
    query_source_ids = source_ids_from_query_rows(query_rows)
    query_families = families_from_query_rows(query_rows)

    chunk_texts = [chunk.raw_text_for_duplicate for chunk in chunks if chunk.raw_text_for_duplicate]
    chunk_duplicates = duplicate_profile(chunk_texts)
    chunk_near_duplicates = near_duplicate_profile(
        chunk_texts,
        max_bucket_candidates=int(config.get("near_duplicate", {}).get("max_bucket_candidates", 50)),
        hamming_threshold=int(config.get("near_duplicate", {}).get("simhash_hamming_threshold", 6)),
    )

    source_document_ids = [chunk.source_document_id for chunk in chunks if chunk.source_document_id]
    if not source_document_ids:
        source_document_ids = sorted(query_source_ids)
    family_ids = [chunk.document_family for chunk in chunks if chunk.document_family]
    if not family_ids:
        family_ids = sorted(query_families)

    source_artifacts = [chunk.source_artifact_id for chunk in chunks if chunk.source_artifact_id]
    if not source_artifacts:
        source_artifacts = sorted(query_source_ids)

    parser_versions = Counter(chunk.parser_version or "UNKNOWN" for chunk in chunks)
    if not chunks:
        parser_versions = Counter({"NOT_APPLICABLE_IDENTITY_ONLY" if identity_only else "UNKNOWN": len(query_rows)})

    length_profiles = {
        "embedding_text": length_distribution([chunk.embedding_text for chunk in chunks]),
        "bm25_text": length_distribution([chunk.bm25_text for chunk in chunks]),
        "citation_text": length_distribution([chunk.citation_text for chunk in chunks]),
    }
    availability = availability_report(chunks, identity_only=identity_only)
    file_identity = file_identity_distribution(query_rows) if identity_only else empty_file_identity_distribution()
    concentration = concentration_report(source_artifacts)
    effective = effective_diversity_estimate(
        row_count=len(query_rows),
        unique_query_count=query_duplicates["unique_count"],
        source_document_count=len(set(source_document_ids)),
        document_family_count=len(set(family_ids)),
        unique_chunk_count=chunk_duplicates["unique_count"],
        source_artifact_top_share=concentration["top_share"],
        identity_only=identity_only,
        file_identity_unique_count=file_identity["unique_file_identity_count"],
    )
    metadata_gaps = metadata_gaps_for_lane(
        chunks=chunks,
        identity_only=identity_only,
        availability=availability,
        length_profiles=length_profiles,
        parser_versions=parser_versions,
    )
    classification = classify_lane(
        row_count=len(query_rows),
        source_document_count=len(set(source_document_ids)),
        document_family_count=len(set(family_ids)),
        source_top_share=concentration["top_share"],
        query_near_duplicate_rate=query_near_duplicates["near_duplicate_rate"],
        chunk_near_duplicate_rate=chunk_near_duplicates["near_duplicate_rate"],
        effective_diversity=effective,
        metadata_gaps=metadata_gaps,
        identity_only=identity_only,
        file_identity_unique_count=file_identity["unique_file_identity_count"],
    )

    return {
        "lane": lane,
        "classification": classification,
        "row_count": len(query_rows),
        "query_source_count": len(lane_cfg.get("query_sources", []) or []),
        "source_document_count": len(set(source_document_ids)),
        "document_family_count": len(set(family_ids)),
        "parser_version_distribution": dict(sorted(parser_versions.items())),
        "source_artifact_concentration": concentration,
        "query_duplicate_rate": query_duplicates["duplicate_rate"],
        "query_duplicate_profile": query_duplicates,
        "query_near_duplicate_rate": query_near_duplicates["near_duplicate_rate"],
        "query_near_duplicate_profile": query_near_duplicates,
        "chunk_count_profiled": len(chunks),
        "chunk_duplicate_rate": chunk_duplicates["duplicate_rate"],
        "chunk_duplicate_profile": chunk_duplicates,
        "chunk_near_duplicate_rate": chunk_near_duplicates["near_duplicate_rate"],
        "chunk_near_duplicate_profile": chunk_near_duplicates,
        "embedding_text_length_distribution": length_profiles["embedding_text"],
        "bm25_text_length_distribution": length_profiles["bm25_text"],
        "citation_text_length_distribution": length_profiles["citation_text"],
        "location_json_availability": availability["location_json"],
        "citation_text_availability": availability["citation_text"],
        "table_header_metadata_availability": availability["table_header_metadata"],
        "file_identity_token_distribution": file_identity,
        "effective_diversity_estimate": effective,
        "metadata_gaps": metadata_gaps,
        "hidden_xlsx_redaction": {
            "enabled": hidden_redaction,
            "content_preview_emitted": False,
            "raw_hidden_content_counted_only_as_metadata": hidden_redaction,
        },
        "diagnostic_source_contract": diagnostic_source_contract(config).get(lane, {}),
        "pdf_file_identity_policy": (
            PDF_FILE_IDENTITY_ONLY_POLICY if identity_only else "not_pdf_file_identity_lane"
        ),
        "content_previews_emitted": False,
    }


def diagnostic_source_contract(config: Mapping[str, Any]) -> dict[str, Any]:
    raw = config.get("diagnostic_source_contract")
    if not isinstance(raw, Mapping):
        return {}
    return {str(lane): value for lane, value in raw.items() if isinstance(value, Mapping)}


def load_query_rows(sources: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not isinstance(sources, list):
        raise ValueError("lane.query_sources must be a list")
    for source in sources:
        if not isinstance(source, Mapping):
            raise ValueError("query source must be a mapping")
        path = resolve_path(required_str(source, "path"))
        role = str(source.get("role") or "")
        if not path.exists():
            raise FileNotFoundError(path)
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                cleaned = {str(k): clean_text(v) for k, v in row.items() if k is not None}
                cleaned["_source_role"] = role
                cleaned["_source_path_hash"] = short_hash(repo_relative(path))
                rows.append(cleaned)
    return rows


def load_chunk_profiles(lane_cfg: Mapping[str, Any], config: Mapping[str, Any]) -> list[ChunkProfile]:
    sources = lane_cfg.get("chunk_sources", [])
    if not isinstance(sources, list):
        raise ValueError("lane.chunk_sources must be a list")
    chunks: list[ChunkProfile] = []
    for source in sources:
        if not isinstance(source, Mapping):
            raise ValueError("chunk source must be a mapping")
        kind = required_str(source, "type")
        if kind == "jsonl":
            chunks.extend(load_jsonl_chunks(source))
        elif kind == "ragmeta":
            chunks.extend(load_ragmeta_chunks(source, config.get("postgres", {})))
        else:
            raise ValueError(f"unsupported chunk source type: {kind}")
    return chunks


def load_jsonl_chunks(source: Mapping[str, Any]) -> list[ChunkProfile]:
    path = resolve_path(required_str(source, "path"))
    if not path.exists():
        raise FileNotFoundError(path)
    text_fields = list(source.get("text_fields") or ["chunk_text", "text"])
    embedding_fields = list(source.get("embedding_text_fields") or ["embedding_text"])
    bm25_fields = list(source.get("bm25_text_fields") or ["bm25_text"])
    citation_fields = list(source.get("citation_text_fields") or ["citation_text"])
    doc_fields = list(source.get("source_document_fields") or ["doc_id", "document_id"])
    family_fields = list(source.get("document_family_fields") or ["title", "display_title", "retrieval_title"])
    artifact_fields = list(source.get("source_artifact_fields") or ["source_artifact_id", "doc_id"])
    parser_fields = list(source.get("parser_version_fields") or ["parser_version"])
    loaded: list[ChunkProfile] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            raw_text = first_text(row, text_fields)
            embedding_text = first_text(row, embedding_fields) or raw_text
            bm25_text = first_text(row, bm25_fields)
            citation_text = first_text(row, citation_fields)
            doc_id = first_text(row, doc_fields)
            family = first_text(row, family_fields) or doc_id
            artifact = first_text(row, artifact_fields) or doc_id
            parser_version = first_text(row, parser_fields) or "UNKNOWN"
            loaded.append(ChunkProfile(
                chunk_id=first_text(row, ["chunk_id", "id"]) or short_hash(raw_text),
                source_document_id=doc_id,
                document_family=family_key(family),
                source_artifact_id=artifact,
                parser_version=parser_version,
                embedding_text=embedding_text,
                bm25_text=bm25_text,
                citation_text=citation_text,
                location_json_available=bool(first_value(row, ["location_json", "locationJson"])),
                citation_text_available=bool(citation_text),
                table_metadata_available=bool(first_value(row, ["table_metadata", "tableMetadata", "tableId", "table_id"])),
                header_metadata_available=bool(first_value(row, ["header_context", "headerContext", "headers", "header"])),
                raw_text_for_duplicate=raw_text,
            ))
    return loaded


def load_ragmeta_chunks(source: Mapping[str, Any], postgres_cfg: Any) -> list[ChunkProfile]:
    index_version = required_str(source, "index_version")
    if not isinstance(postgres_cfg, Mapping):
        raise ValueError("postgres config must be a mapping for ragmeta sources")
    try:
        import psycopg2
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("psycopg2 is required for ragmeta sources") from exc

    conn = psycopg2.connect(
        host=str(postgres_cfg.get("host", "127.0.0.1")),
        port=int(postgres_cfg.get("port", 5433)),
        dbname=str(postgres_cfg.get("database", "aipipeline")),
        user=str(postgres_cfg.get("user", "aipipeline")),
        password=str(postgres_cfg.get("password", "aipipeline_pw")),
        connect_timeout=int(postgres_cfg.get("connect_timeout_seconds", 5)),
    )
    conn.set_session(readonly=True, autocommit=True)
    rows: list[tuple[Any, ...]]
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_id, doc_id, section, text, extra_json
                  FROM ragmeta.chunks
                 WHERE index_version = %s
                 ORDER BY faiss_row_id ASC
                """,
                (index_version,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    profiles: list[ChunkProfile] = []
    for chunk_id, doc_id, section, text, extra_json in rows:
        extra = parse_mapping(extra_json)
        raw_text = clean_text(text)
        source_doc = first_text(extra, ["source_file_id", "sourceFileId", "document_version_id", "documentVersionId"]) or clean_text(doc_id)
        source_name = first_text(extra, ["source_file_name", "sourceFileName", "original_filename"]) or source_doc
        family = family_key(source_name or clean_text(section) or source_doc)
        artifact = first_text(extra, [
            "extracted_artifact_id",
            "extractedArtifactId",
            "parsed_artifact_id",
            "parsedArtifactId",
            "source_file_id",
            "sourceFileId",
        ]) or source_doc
        parser_version = first_text(extra, ["parser_version", "parserVersion"]) or "UNKNOWN"
        citation_text = first_text(extra, ["citation_text", "citationText"])
        bm25_text = first_text(extra, ["bm25_text", "bm25Text"])
        embedding_text = first_text(extra, ["embedding_text", "embeddingText"]) or raw_text
        location_value = first_value(extra, ["location_json", "locationJson"])
        profiles.append(ChunkProfile(
            chunk_id=clean_text(chunk_id),
            source_document_id=source_doc,
            document_family=family,
            source_artifact_id=artifact,
            parser_version=parser_version,
            embedding_text=embedding_text,
            bm25_text=bm25_text,
            citation_text=citation_text,
            location_json_available=location_value is not None and clean_text(location_value) != "",
            citation_text_available=bool(citation_text),
            table_metadata_available=has_any(extra, [
                "table_metadata",
                "tableMetadata",
                "tableId",
                "table_id",
                "cellRange",
                "sheetName",
                "rowStart",
                "columnStart",
            ]),
            header_metadata_available=has_any(extra, [
                "header_context",
                "headerContext",
                "headers",
                "header",
                "headerRow",
            ]),
            raw_text_for_duplicate=raw_text,
        ))
    return profiles


def source_ids_from_query_rows(rows: Sequence[Mapping[str, str]]) -> set[str]:
    fields = [
        "expected_document_ids",
        "expected_page_ids",
        "expected_document_version_id",
        "expected_file_name",
        "source_file_name",
        "expected_chunk_ids",
    ]
    values: set[str] = set()
    for row in rows:
        for field in fields:
            values.update(split_multi_value(row.get(field)))
    return {value for value in values if value}


def families_from_query_rows(rows: Sequence[Mapping[str, str]]) -> set[str]:
    families: set[str] = set()
    for row in rows:
        for field in ("expected_file_name", "source_file_name", "expected_document_ids", "expected_page_ids"):
            for value in split_multi_value(row.get(field)):
                families.add(family_key(value))
    return {item for item in families if item}


def duplicate_profile(values: Sequence[str]) -> dict[str, Any]:
    cleaned = [normalize_for_duplicate(value) for value in values if normalize_for_duplicate(value)]
    total = len(cleaned)
    counts = Counter(cleaned)
    duplicate_rows = sum(count - 1 for count in counts.values() if count > 1)
    return {
        "total_count": total,
        "unique_count": len(counts),
        "duplicate_row_count": duplicate_rows,
        "duplicate_rate": safe_ratio(duplicate_rows, total),
    }


def near_duplicate_profile(
    values: Sequence[str],
    *,
    max_bucket_candidates: int = 50,
    hamming_threshold: int = 6,
) -> dict[str, Any]:
    cleaned = [normalize_for_duplicate(value) for value in values if normalize_for_duplicate(value)]
    total = len(cleaned)
    if total == 0:
        return {"total_count": 0, "near_duplicate_row_count": 0, "near_duplicate_rate": 0.0, "method": "simhash_lsh"}
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    marked: set[int] = set()
    fingerprints: list[int] = []
    for idx, text in enumerate(cleaned):
        fp = simhash(text)
        fingerprints.append(fp)
        candidate_indexes: set[int] = set()
        for band, value in simhash_bands(fp):
            candidate_indexes.update(buckets[(band, value)][:max_bucket_candidates])
        for other_idx in candidate_indexes:
            if hamming_distance(fp, fingerprints[other_idx]) <= hamming_threshold:
                marked.add(idx)
                marked.add(other_idx)
                break
        for band, value in simhash_bands(fp):
            bucket = buckets[(band, value)]
            if len(bucket) < max_bucket_candidates:
                bucket.append(idx)
    return {
        "total_count": total,
        "near_duplicate_row_count": len(marked),
        "near_duplicate_rate": safe_ratio(len(marked), total),
        "method": "simhash_lsh",
        "hamming_threshold": hamming_threshold,
    }


def simhash(text: str) -> int:
    weights = [0] * 64
    tokens = TOKEN_RE.findall(text.lower())
    if not tokens:
        tokens = [text.lower()]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        value = int.from_bytes(digest[:8], byteorder="big", signed=False)
        for bit in range(64):
            weights[bit] += 1 if value & (1 << bit) else -1
    out = 0
    for bit, weight in enumerate(weights):
        if weight >= 0:
            out |= 1 << bit
    return out


def simhash_bands(value: int) -> Iterable[tuple[int, int]]:
    for band in range(8):
        yield band, (value >> (band * 8)) & 0xFF


def hamming_distance(left: int, right: int) -> int:
    return int((left ^ right).bit_count())


def length_distribution(values: Sequence[str]) -> dict[str, Any]:
    lengths = [len(value) for value in values if clean_text(value)]
    missing = len(values) - len(lengths)
    if not lengths:
        return {
            "available_count": 0,
            "missing_count": missing,
            "min": None,
            "p50": None,
            "p90": None,
            "p95": None,
            "max": None,
            "mean": None,
        }
    sorted_lengths = sorted(lengths)
    return {
        "available_count": len(lengths),
        "missing_count": missing,
        "min": sorted_lengths[0],
        "p50": percentile(sorted_lengths, 0.50),
        "p90": percentile(sorted_lengths, 0.90),
        "p95": percentile(sorted_lengths, 0.95),
        "max": sorted_lengths[-1],
        "mean": round(statistics.fmean(sorted_lengths), 2),
    }


def availability_report(chunks: Sequence[ChunkProfile], *, identity_only: bool) -> dict[str, Any]:
    total = len(chunks)
    if identity_only:
        return {
            "location_json": availability_counts(0, 0, not_applicable=True),
            "citation_text": availability_counts(0, 0, not_applicable=True),
            "table_header_metadata": {
                "table_metadata": availability_counts(0, 0, not_applicable=True),
                "header_metadata": availability_counts(0, 0, not_applicable=True),
            },
        }
    location = sum(1 for chunk in chunks if chunk.location_json_available)
    citation = sum(1 for chunk in chunks if chunk.citation_text_available)
    table = sum(1 for chunk in chunks if chunk.table_metadata_available)
    header = sum(1 for chunk in chunks if chunk.header_metadata_available)
    return {
        "location_json": availability_counts(location, total),
        "citation_text": availability_counts(citation, total),
        "table_header_metadata": {
            "table_metadata": availability_counts(table, total),
            "header_metadata": availability_counts(header, total),
        },
    }


def availability_counts(count: int, total: int, *, not_applicable: bool = False) -> dict[str, Any]:
    return {
        "available_count": count,
        "missing_count": max(total - count, 0),
        "availability_rate": safe_ratio(count, total),
        "not_applicable": not_applicable,
    }


def file_identity_distribution(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    identities: list[str] = []
    extensions = Counter()
    token_counts: list[int] = []
    year_token_rows = 0
    month_token_rows = 0
    generic_token_rows = 0
    for row in rows:
        identity = clean_text(row.get("expected_file_name")) or clean_text(row.get("source_file_name"))
        if not identity:
            continue
        identities.append(identity)
        suffix = Path(identity).suffix.lower() or "NO_EXTENSION"
        extensions[suffix] += 1
        tokens = TOKEN_RE.findall(identity.lower())
        token_counts.append(len(tokens))
        if YEAR_RE.search(identity):
            year_token_rows += 1
        if MONTH_RE.search(identity):
            month_token_rows += 1
        if any(token in {"file", "document", "report", "pdf"} for token in tokens):
            generic_token_rows += 1
    return {
        "identity_only": True,
        "row_count_with_file_identity": len(identities),
        "unique_file_identity_count": len(set(normalize_for_duplicate(value) for value in identities)),
        "duplicate_file_identity_rate": duplicate_profile(identities)["duplicate_rate"],
        "extension_distribution": dict(sorted(extensions.items())),
        "token_count_distribution": length_distribution(["x" * count for count in token_counts]),
        "rows_with_year_token": year_token_rows,
        "rows_with_month_token": month_token_rows,
        "rows_with_generic_file_token": generic_token_rows,
        "content_page_bbox_table_row_column_value_claimed": False,
        "raw_file_identity_preview_emitted": False,
    }


def empty_file_identity_distribution() -> dict[str, Any]:
    return {
        "identity_only": False,
        "row_count_with_file_identity": 0,
        "unique_file_identity_count": 0,
        "duplicate_file_identity_rate": 0.0,
        "extension_distribution": {},
        "token_count_distribution": length_distribution([]),
        "rows_with_year_token": 0,
        "rows_with_month_token": 0,
        "rows_with_generic_file_token": 0,
        "content_page_bbox_table_row_column_value_claimed": False,
        "raw_file_identity_preview_emitted": False,
    }


def concentration_report(values: Sequence[str]) -> dict[str, Any]:
    cleaned = [value for value in values if clean_text(value)]
    counts = Counter(cleaned)
    total = sum(counts.values())
    top = counts.most_common(5)
    return {
        "total_count": total,
        "unique_artifact_count": len(counts),
        "top_count": top[0][1] if top else 0,
        "top_share": safe_ratio(top[0][1], total) if top else 0.0,
        "top_artifacts_redacted": [
            {
                "artifact_hash": short_hash(value),
                "count": count,
                "share": safe_ratio(count, total),
            }
            for value, count in top
        ],
        "raw_artifact_ids_emitted": False,
    }


def effective_diversity_estimate(
    *,
    row_count: int,
    unique_query_count: int,
    source_document_count: int,
    document_family_count: int,
    unique_chunk_count: int,
    source_artifact_top_share: float,
    identity_only: bool,
    file_identity_unique_count: int,
) -> int:
    components = [max(unique_query_count, 0)]
    if source_document_count:
        concentration_penalty = max(0.25, 1.0 - source_artifact_top_share)
        components.append(max(1, int(round(source_document_count * concentration_penalty * 2))))
    if document_family_count:
        components.append(max(1, document_family_count * 3))
    if unique_chunk_count and not identity_only:
        components.append(max(1, int(math.sqrt(unique_chunk_count))))
    if identity_only and file_identity_unique_count:
        components.append(file_identity_unique_count)
    if not components:
        return 0
    return max(0, min(row_count, max(1, min(components))))


def metadata_gaps_for_lane(
    *,
    chunks: Sequence[ChunkProfile],
    identity_only: bool,
    availability: Mapping[str, Any],
    length_profiles: Mapping[str, Mapping[str, Any]],
    parser_versions: Counter[str],
) -> list[str]:
    gaps: list[str] = []
    if identity_only:
        return gaps
    if not chunks:
        return ["chunk_metadata_unavailable"]
    if parser_versions.get("UNKNOWN", 0) == len(chunks):
        gaps.append("parser_version_missing")
    if availability["location_json"]["availability_rate"] == 0:
        gaps.append("location_json_missing")
    if availability["citation_text"]["availability_rate"] == 0:
        gaps.append("citation_text_missing")
    if length_profiles["bm25_text"]["available_count"] == 0:
        gaps.append("bm25_text_not_materialized")
    if length_profiles["embedding_text"]["available_count"] == 0:
        gaps.append("embedding_text_not_materialized")
    return gaps


def classify_lane(
    *,
    row_count: int,
    source_document_count: int,
    document_family_count: int,
    source_top_share: float,
    query_near_duplicate_rate: float,
    chunk_near_duplicate_rate: float,
    effective_diversity: int,
    metadata_gaps: Sequence[str],
    identity_only: bool,
    file_identity_unique_count: int,
) -> str:
    if row_count == 0 or (source_document_count == 0 and not identity_only):
        return RISK_UNKNOWN
    if "chunk_metadata_unavailable" in metadata_gaps and not identity_only:
        return RISK_UNKNOWN
    if identity_only:
        if file_identity_unique_count < 5 or row_count < 10:
            return RISK_LOW
        if file_identity_unique_count >= 10 and row_count >= 20 and query_near_duplicate_rate <= 0.30:
            return RISK_SUFFICIENT
        return RISK_MODERATE
    if source_document_count <= 3 and row_count <= 30:
        return RISK_LOW
    if source_top_share >= 0.75 or query_near_duplicate_rate >= 0.50 or chunk_near_duplicate_rate >= 0.65:
        return RISK_LOW
    if (
        row_count >= 20
        and source_document_count >= 5
        and document_family_count >= 5
        and effective_diversity >= 12
        and query_near_duplicate_rate <= 0.30
        and source_top_share <= 0.60
    ):
        return RISK_SUFFICIENT
    return RISK_MODERATE


def phase2_recommendation(lane_reports: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    low = [name for name, report in lane_reports.items() if report["classification"] == RISK_LOW]
    unknown = [name for name, report in lane_reports.items() if report["classification"] == RISK_UNKNOWN]
    if unknown:
        return {
            "decision": "DO_NOT_PROCEED_METADATA_BLOCKED",
            "can_proceed": False,
            "conditions": [f"resolve insufficient metadata for {', '.join(sorted(unknown))}"],
        }
    if low:
        return {
            "decision": "CONDITIONAL_DIAGNOSTIC_ONLY",
            "can_proceed": True,
            "conditions": [
                f"keep low-diversity lanes isolated: {', '.join(sorted(low))}",
                "do not promote profiles or denominators",
                "collect fresh non-frozen diagnostic rows before tuning",
            ],
        }
    return {
        "decision": "PROCEED_DIAGNOSTIC_ONLY",
        "can_proceed": True,
        "conditions": [
            "diagnostic/report-only only",
            "no denominator mutation",
            "no production index mutation",
        ],
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Retrieval Corpus Diversity Profile",
        "",
        f"Status: `{report['status']}`",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "Scope: diagnostic/report-only. No tuning, Optuna execution, LLM labeling/judgment, production index mutation, vector write, or official denominator registry change was performed.",
        "",
        "## Summary",
        "",
        "| Lane | Rows | Sources | Families | Effective diversity | Classification |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for lane, lane_report in report["lanes"].items():
        lines.append(
            "| {lane} | {rows} | {sources} | {families} | {effective} | `{classification}` |".format(
                lane=lane,
                rows=lane_report["row_count"],
                sources=lane_report["source_document_count"],
                families=lane_report["document_family_count"],
                effective=lane_report["effective_diversity_estimate"],
                classification=lane_report["classification"],
            )
        )
    lines.extend([
        "",
        f"Phase 2 recommendation: `{report['phase2_recommendation']}`",
        "",
        "Conditions:",
    ])
    for condition in report["phase2_conditions"]:
        lines.append(f"- {condition}")
    if report.get("diagnostic_source_contract"):
        lines.extend(["", "## Diagnostic Source Contract", ""])
        for lane, contract in report["diagnostic_source_contract"].items():
            targets = ", ".join(contract.get("target_sources") or [])
            lines.append(
                f"- `{lane}`: targets=`{targets}`, hard_negative_policy=`{contract.get('hard_negative_policy', '')}`"
            )
    lines.extend(["", "## Lane Details", ""])
    for lane, lane_report in report["lanes"].items():
        lines.extend([
            f"### {lane}",
            "",
            f"- Classification: `{lane_report['classification']}`",
            f"- Row count: `{lane_report['row_count']}`",
            f"- Source document count: `{lane_report['source_document_count']}`",
            f"- Document family count: `{lane_report['document_family_count']}`",
            f"- Effective diversity estimate: `{lane_report['effective_diversity_estimate']}`",
            f"- Query duplicate rate: `{lane_report['query_duplicate_rate']}`",
            f"- Query near-duplicate rate: `{lane_report['query_near_duplicate_rate']}`",
            f"- Chunk duplicate rate: `{lane_report['chunk_duplicate_rate']}`",
            f"- Chunk near-duplicate rate: `{lane_report['chunk_near_duplicate_rate']}`",
            f"- Source artifact top share: `{lane_report['source_artifact_concentration']['top_share']}`",
            f"- Location JSON availability: `{lane_report['location_json_availability']['availability_rate']}`",
            f"- Citation text availability: `{lane_report['citation_text_availability']['availability_rate']}`",
            f"- PDF FILE policy: `{lane_report['pdf_file_identity_policy']}`",
            f"- Content previews emitted: `{lane_report['content_previews_emitted']}`",
        ])
        gaps = lane_report["metadata_gaps"]
        lines.append(f"- Metadata gaps: `{', '.join(gaps) if gaps else 'none'}`")
        lines.append("")
    lines.extend([
        "## Guardrails",
        "",
        f"- `production_index_mutation`: `{str(report['production_index_mutation']).lower()}`",
        f"- `vector_write_attempted`: `{str(report['vector_write_attempted']).lower()}`",
        f"- `official_denominator_registry_changed`: `{str(report['official_denominator_registry_changed']).lower()}`",
        f"- `hidden_xlsx_exposed`: `{str(report['hidden_xlsx_exposed']).lower()}`",
        f"- `local_llm_used_for_labels_or_judgments`: `{str(report['local_llm_used_for_labels_or_judgments']).lower()}`",
        f"- `optuna_run`: `{str(report['optuna_run']).lower()}`",
        f"- PDF FILE lookup remains `{PDF_FILE_IDENTITY_ONLY_POLICY}`.",
        "",
    ])
    return "\n".join(lines)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def required_str(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"missing required value: {key}")
    return str(value)


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def normalize_for_duplicate(value: str) -> str:
    value = clean_text(value).lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^\w가-힣 ]+", "", value)
    return value.strip()


def split_multi_value(value: Any) -> set[str]:
    text = clean_text(value)
    if not text:
        return set()
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return {clean_text(item) for item in parsed if clean_text(item)}
        except json.JSONDecodeError:
            pass
    return {part for part in (item.strip() for item in TEXT_SPLIT_RE.split(text)) if part}


def first_value(mapping: Mapping[str, Any], fields: Sequence[str]) -> Any:
    for field in fields:
        if field in mapping and mapping[field] not in (None, ""):
            return mapping[field]
    return None


def first_text(mapping: Mapping[str, Any], fields: Sequence[str]) -> str:
    return clean_text(first_value(mapping, fields))


def has_any(mapping: Mapping[str, Any], fields: Sequence[str]) -> bool:
    return any(clean_text(mapping.get(field)) for field in fields if field in mapping)


def parse_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def family_key(value: str) -> str:
    text = clean_text(value).lower()
    if not text:
        return ""
    text = Path(text).stem
    text = re.sub(r"(?:19|20)\d{2}", "YEAR", text)
    text = re.sub(r"(?<!\d)(?:0?[1-9]|1[0-2])(?!\d)", "MONTH", text)
    text = re.sub(r"\d+", "NUM", text)
    text = re.sub(r"[_\-\s]+", " ", text)
    return text.strip() or clean_text(value)


def percentile(sorted_values: Sequence[int], ratio: float) -> int:
    if not sorted_values:
        return 0
    index = int(round((len(sorted_values) - 1) * ratio))
    index = min(max(index, 0), len(sorted_values) - 1)
    return int(sorted_values[index])


def safe_ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def short_hash(value: str) -> str:
    return hashlib.sha256(clean_text(value).encode("utf-8")).hexdigest()[:12]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
