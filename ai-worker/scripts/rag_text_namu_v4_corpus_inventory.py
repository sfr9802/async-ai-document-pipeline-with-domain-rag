"""Inventory Track B R2 namu-v4 corpus artifacts.

The R2 inventory proves that the active namu-v4 corpus is parseable and that
answer-context assembly can use raw chunk text from rag_chunks.jsonl without
falling back to embedding/debug text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


DEFAULT_CORPUS_DIR = Path("ai-worker/eval/corpora/namu-v4-structured-combined")
DEFAULT_REPORT = Path("eval/reports/rag-ingestion/rag_text_namu_v4_corpus_inventory_report.json")

REQUIRED_FILES = ["pages_v4.jsonl", "chunks_v4.jsonl", "rag_chunks.jsonl"]
HARDENED_AUXILIARY_FILES = ["validation_report.json", "split_manifest.json", "split_manifest.report.json"]
ALLOWED_CONTEXT_FIELDS = ["chunk_text", "text"]
DISALLOWED_CONTEXT_FIELDS = ["embedding_text", "text_for_embedding", "debug_text"]
TITLE_FIELDS = ["title", "display_title", "retrieval_title", "page_title"]
STRICT_INTERNAL_CONTEXT_MARKERS = [
    "__HIDDEN__",
    "[[INTERNAL]]",
    "BEGIN_INTERNAL",
    "END_INTERNAL",
    "text_for_embedding:",
    "debug_text:",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(Path(args.corpus_dir))
    write_json(Path(args.report), report)
    print_json({
        "status": report["status"],
        "corpus_dir": report["corpus_dir"],
        "report": str(Path(args.report)),
        "blocker_count": len(report["blockers"]),
        "raw_context_field": report["rag_chunks_schema"]["raw_context_field"],
    })
    return 0 if report["status"] == "PASS" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", default=str(DEFAULT_CORPUS_DIR))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    return parser.parse_args(argv)


def build_report(corpus_dir: Path) -> dict[str, Any]:
    corpus_exists = corpus_dir.exists() and corpus_dir.is_dir()
    pages_inspector = PagesInspector()
    rag_inspector = RagChunksInspector()
    files: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_FILES:
        callback = None
        if name == "pages_v4.jsonl":
            callback = pages_inspector.inspect_record
        elif name == "rag_chunks.jsonl":
            callback = rag_inspector.inspect_record
        files[name] = inspect_jsonl_file(corpus_dir / name, on_record=callback)
    auxiliary_files: dict[str, dict[str, Any]] = {}
    auxiliary_data: dict[str, Mapping[str, Any] | None] = {}
    for name in HARDENED_AUXILIARY_FILES:
        auxiliary_files[name], auxiliary_data[name] = inspect_json_file(corpus_dir / name)

    pages_schema = pages_inspector.summary(files["pages_v4.jsonl"]["row_count"])
    rag_chunks_schema = rag_inspector.summary(
        files["rag_chunks.jsonl"]["row_count"],
        page_ids=pages_inspector.page_ids,
    )
    hardened_consistency = build_hardened_consistency(
        files=files,
        pages_schema=pages_schema,
        page_ids=pages_inspector.page_ids,
        auxiliary_files=auxiliary_files,
        auxiliary_data=auxiliary_data,
    )
    context_policy = build_context_policy(rag_chunks_schema)
    blockers = build_blockers(
        corpus_dir=corpus_dir,
        corpus_exists=corpus_exists,
        files=files,
        hardened_consistency=hardened_consistency,
        pages_schema=pages_schema,
        rag_chunks_schema=rag_chunks_schema,
        context_policy=context_policy,
    )
    warnings = build_warnings(files, rag_chunks_schema, context_policy)
    completion_criteria = {
        "corpus_dir_exists": corpus_exists,
        "required_files_exist": all(files[name]["exists"] for name in REQUIRED_FILES),
        "required_files_parseable": all(files[name]["parse_error_count"] == 0 for name in REQUIRED_FILES),
        "required_files_non_zero_rows": all(files[name]["row_count"] > 0 for name in REQUIRED_FILES),
        "hardened_auxiliary_files_present": hardened_consistency["auxiliary_files_present"],
        "hardened_auxiliary_files_parseable": hardened_consistency["auxiliary_files_parseable"],
        "validation_report_counts_match_jsonl": hardened_consistency["validation_report_counts_match_jsonl"],
        "validation_report_duplicate_and_empty_counts_clean": hardened_consistency[
            "validation_report_duplicate_and_empty_counts_clean"
        ],
        "split_manifest_doc_ids_match_pages_v4": hardened_consistency["split_manifest_doc_ids_match_pages_v4"],
        "split_manifest_doc_counts_clean": hardened_consistency["split_manifest_doc_counts_clean"],
        "split_manifest_metadata_expected": hardened_consistency["split_manifest_metadata_expected"],
        "split_manifest_report_clean": hardened_consistency["split_manifest_report_clean"],
        "pages_v4_page_id_unique": pages_schema["page_id_unique"],
        "rag_chunks_is_production_join_source": True,
        "rag_chunks_chunk_id_unique": rag_chunks_schema["chunk_id_unique"],
        "rag_chunks_page_identity_complete": rag_chunks_schema["page_identity_complete"],
        "rag_chunks_page_identity_matches_pages_v4": rag_chunks_schema["page_identity_matches_pages_v4"],
        "raw_context_field_allowed": context_policy["selected_context_field_allowed"],
        "raw_context_non_empty": rag_chunks_schema["empty_raw_context_count"] == 0,
        "raw_context_trust_counters_clean": rag_chunks_schema["raw_context_trust_counters_clean"],
        "disallowed_context_field_not_selected": context_policy["selected_disallowed_context_field"] is False,
        "promotion_evidence_false": True,
    }
    status = "PASS" if not blockers and all(completion_criteria.values()) else "FAIL"
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "schema_version": "rag_text_namu_v4_corpus_inventory_v2",
        "hardening_revision": "r2_aux_consistency_raw_context_and_split_count_v2",
        "status": status,
        "report_role": "rag_text_namu_v4_corpus_inventory",
        "scope": "track_b_text_retrieval_e2e",
        "phase": "R2",
        "corpus_dir": normalise_path(corpus_dir),
        "corpus_dir_exists": corpus_exists,
        "files": files,
        "auxiliary_files": auxiliary_files,
        "hardened_consistency": hardened_consistency,
        "pages_schema": pages_schema,
        "rag_chunks_schema": rag_chunks_schema,
        "context_policy": context_policy,
        "join_policy": {
            "production_join_source": "rag_chunks.jsonl",
            "forbidden_join_source_for_current_answerability": "chunks_v4.jsonl",
            "reason": (
                "rag_chunks.jsonl is the production retrieval / answerability join "
                "fixture; chunks_v4.jsonl uses a different chunk_id namespace."
            ),
        },
        "completion_criteria": completion_criteria,
        "blockers": blockers,
        "warnings": warnings,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "next_phase_recommendation": (
            "Proceed to R3 namu-v4 gold binding only if this report remains PASS."
        ),
    }


def inspect_jsonl_file(
    path: Path,
    *,
    on_record: Callable[[Mapping[str, Any]], None] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": normalise_path(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else None,
        "sha256": None,
        "row_count": 0,
        "blank_line_count": 0,
        "parse_error_count": 0,
        "first_parse_error": None,
        "non_object_row_count": 0,
        "sample_keys": [],
    }
    if not path.exists():
        return result

    digest = hashlib.sha256()
    sample_keys: list[str] = []
    with path.open("rb") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            digest.update(raw_line)
            stripped = raw_line.strip()
            if not stripped:
                result["blank_line_count"] += 1
                continue
            result["row_count"] += 1
            try:
                decoded = stripped.decode("utf-8")
                record = json.loads(decoded.lstrip("\ufeff"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                result["parse_error_count"] += 1
                if result["first_parse_error"] is None:
                    result["first_parse_error"] = f"line {line_no}: {type(exc).__name__}: {exc}"
                continue
            if not isinstance(record, dict):
                result["non_object_row_count"] += 1
                if result["first_parse_error"] is None:
                    result["first_parse_error"] = (
                        f"line {line_no}: expected object, got {type(record).__name__}"
                    )
                continue
            if not sample_keys:
                sample_keys = list(record.keys())
            if on_record is not None:
                on_record(record)
    result["sha256"] = digest.hexdigest()
    result["sample_keys"] = sample_keys
    return result


def inspect_json_file(path: Path) -> tuple[dict[str, Any], Mapping[str, Any] | None]:
    result: dict[str, Any] = {
        "path": normalise_path(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else None,
        "sha256": None,
        "parse_error": None,
        "top_level_keys": [],
    }
    if not path.exists():
        return result, None

    digest = hashlib.sha256()
    raw = path.read_bytes()
    digest.update(raw)
    result["sha256"] = digest.hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        result["parse_error"] = f"{type(exc).__name__}: {exc}"
        return result, None
    if not isinstance(payload, dict):
        result["parse_error"] = f"expected object, got {type(payload).__name__}"
        return result, None
    result["top_level_keys"] = list(payload.keys())
    return result, payload


class RagChunksInspector:
    def __init__(self) -> None:
        self.seen_chunk_ids: set[str] = set()
        self.duplicate_chunk_id_count = 0
        self.duplicate_chunk_ids_sample: list[str] = []
        self.page_id_counts: Counter[str] = Counter()
        self.doc_id_counts: Counter[str] = Counter()
        self.missing_chunk_id_count = 0
        self.missing_page_id_count = 0
        self.missing_doc_id_count = 0
        self.missing_section_path_count = 0
        self.missing_title_count = 0
        self.missing_any_title_count = 0
        self.strict_internal_marker_count = 0
        self.raw_json_like_chunk_text_count = 0
        self.chunk_text_equals_embedding_text_count = 0
        self.field_presence_counts: Counter[str] = Counter()
        self.empty_counts: Counter[str] = Counter()

    def inspect_record(self, record: Mapping[str, Any]) -> None:
        chunk_id = clean(record.get("chunk_id"))
        if not chunk_id:
            self.missing_chunk_id_count += 1
        elif chunk_id in self.seen_chunk_ids:
            self.duplicate_chunk_id_count += 1
            if len(self.duplicate_chunk_ids_sample) < 10:
                self.duplicate_chunk_ids_sample.append(chunk_id)
        else:
            self.seen_chunk_ids.add(chunk_id)

        for field in [
            "chunk_id",
            "page_id",
            "doc_id",
            "section_path",
            "chunk_text",
            "text",
            "embedding_text",
            "text_for_embedding",
            "debug_text",
            *TITLE_FIELDS,
        ]:
            if field in record:
                self.field_presence_counts[field] += 1
            if field in record and is_empty(record.get(field)):
                self.empty_counts[field] += 1

        if is_empty(record.get("page_id")):
            self.missing_page_id_count += 1
        else:
            self.page_id_counts[clean(record.get("page_id"))] += 1
        if is_empty(record.get("doc_id")):
            self.missing_doc_id_count += 1
        else:
            self.doc_id_counts[clean(record.get("doc_id"))] += 1
        if is_empty(record.get("section_path")):
            self.missing_section_path_count += 1
        if is_empty(record.get("title")):
            self.missing_title_count += 1
        if not any(not is_empty(record.get(field)) for field in TITLE_FIELDS):
            self.missing_any_title_count += 1
        chunk_text = clean(record.get("chunk_text"))
        embedding_text = clean(record.get("embedding_text"))
        if chunk_text:
            if any(marker in chunk_text for marker in STRICT_INTERNAL_CONTEXT_MARKERS):
                self.strict_internal_marker_count += 1
            if is_json_like_text(chunk_text):
                self.raw_json_like_chunk_text_count += 1
            if embedding_text and chunk_text == embedding_text:
                self.chunk_text_equals_embedding_text_count += 1

    def summary(self, row_count: int, *, page_ids: set[str]) -> dict[str, Any]:
        raw_context_field, fallback_used = self.raw_context_field(row_count)
        if raw_context_field is None:
            empty_raw_context_count = row_count
        else:
            empty_raw_context_count = row_count - self.non_empty_field_count(raw_context_field)
        page_identifier_field = self.page_identifier_field(row_count)
        identity_counter = self.identity_counter(page_identifier_field)
        missing_identity_values = sorted(value for value in identity_counter if value not in page_ids)
        missing_identity_row_count = sum(identity_counter[value] for value in missing_identity_values)
        return {
            "row_count": row_count,
            "chunk_id_unique": self.missing_chunk_id_count == 0 and self.duplicate_chunk_id_count == 0,
            "unique_chunk_id_count": len(self.seen_chunk_ids),
            "duplicate_chunk_id_count": self.duplicate_chunk_id_count,
            "duplicate_chunk_ids_sample": self.duplicate_chunk_ids_sample,
            "missing_chunk_id_count": self.missing_chunk_id_count,
            "page_identity_complete": page_identifier_field is not None,
            "page_identity_matches_pages_v4": (
                page_identifier_field is not None and missing_identity_row_count == 0
            ),
            "page_identity_missing_from_pages_v4_count": missing_identity_row_count,
            "page_identity_missing_from_pages_v4_unique_count": len(missing_identity_values),
            "page_identity_missing_from_pages_v4_sample": missing_identity_values[:10],
            "raw_context_field": raw_context_field,
            "text_fallback_accepted": fallback_used,
            "empty_raw_context_count": empty_raw_context_count,
            "missing_chunk_text_count": row_count - self.field_presence_counts.get("chunk_text", 0),
            "empty_chunk_text_count": self.empty_counts.get("chunk_text", 0),
            "missing_text_count": row_count - self.field_presence_counts.get("text", 0),
            "empty_text_count": self.empty_counts.get("text", 0),
            "missing_page_id_count": self.missing_page_id_count,
            "missing_doc_id_count": self.missing_doc_id_count,
            "unique_page_id_count": len(self.page_id_counts),
            "unique_doc_id_count": len(self.doc_id_counts),
            "page_identifier_field": page_identifier_field,
            "missing_section_path_count": self.missing_section_path_count,
            "missing_title_count": self.missing_title_count,
            "missing_any_title_count": self.missing_any_title_count,
            "raw_context_trust_counters": {
                "strict_internal_marker_count": self.strict_internal_marker_count,
                "raw_json_like_chunk_text_count": self.raw_json_like_chunk_text_count,
                "chunk_text_equals_embedding_text_count": self.chunk_text_equals_embedding_text_count,
            },
            "raw_context_trust_counters_clean": (
                self.strict_internal_marker_count == 0
                and self.raw_json_like_chunk_text_count == 0
                and self.chunk_text_equals_embedding_text_count == 0
            ),
            "field_presence_counts": dict(sorted(self.field_presence_counts.items())),
            "disallowed_context_field_presence": {
                field: self.field_presence_counts.get(field, 0)
                for field in DISALLOWED_CONTEXT_FIELDS
            },
        }

    def raw_context_field(self, row_count: int) -> tuple[str | None, bool]:
        if row_count <= 0:
            return None, False
        if self.field_presence_counts.get("chunk_text", 0) > 0:
            return "chunk_text", False
        if self.field_presence_counts.get("text", 0) > 0:
            return "text", True
        return None, False

    def page_identifier_field(self, row_count: int) -> str | None:
        if row_count <= 0:
            return None
        if self.missing_page_id_count == 0:
            return "page_id"
        if self.missing_doc_id_count == 0:
            return "doc_id"
        return None

    def identity_counter(self, page_identifier_field: str | None) -> Counter[str]:
        if page_identifier_field == "page_id":
            return self.page_id_counts
        if page_identifier_field == "doc_id":
            return self.doc_id_counts
        return Counter()

    def non_empty_field_count(self, field: str) -> int:
        return self.field_presence_counts.get(field, 0) - self.empty_counts.get(field, 0)


class PagesInspector:
    def __init__(self) -> None:
        self.page_ids: set[str] = set()
        self.duplicate_page_id_count = 0
        self.duplicate_page_ids_sample: list[str] = []
        self.missing_page_id_count = 0

    def inspect_record(self, record: Mapping[str, Any]) -> None:
        page_id = clean(record.get("page_id"))
        if not page_id:
            self.missing_page_id_count += 1
            return
        if page_id in self.page_ids:
            self.duplicate_page_id_count += 1
            if len(self.duplicate_page_ids_sample) < 10:
                self.duplicate_page_ids_sample.append(page_id)
            return
        self.page_ids.add(page_id)

    def summary(self, row_count: int) -> dict[str, Any]:
        return {
            "row_count": row_count,
            "unique_page_id_count": len(self.page_ids),
            "missing_page_id_count": self.missing_page_id_count,
            "duplicate_page_id_count": self.duplicate_page_id_count,
            "duplicate_page_ids_sample": self.duplicate_page_ids_sample,
            "page_id_unique": self.missing_page_id_count == 0 and self.duplicate_page_id_count == 0,
        }


def build_context_policy(rag_chunks_schema: Mapping[str, Any]) -> dict[str, Any]:
    raw_context_field = rag_chunks_schema.get("raw_context_field")
    return {
        "allowed_context_fields": ALLOWED_CONTEXT_FIELDS,
        "disallowed_context_fields": DISALLOWED_CONTEXT_FIELDS,
        "selected_context_field": raw_context_field,
        "selected_context_field_allowed": raw_context_field in ALLOWED_CONTEXT_FIELDS,
        "selected_disallowed_context_field": raw_context_field in DISALLOWED_CONTEXT_FIELDS,
        "disallowed_fields_present": {
            field: count > 0
            for field, count in rag_chunks_schema["disallowed_context_field_presence"].items()
        },
        "llm_context_binding_policy": (
            "Use chunk_text from rag_chunks.jsonl. Use text only for an alternate raw-text "
            "fixture shape where chunk_text is absent. Never use embedding_text, "
            "text_for_embedding, or debug_text as answer context."
        ),
    }


def build_hardened_consistency(
    *,
    files: Mapping[str, Mapping[str, Any]],
    pages_schema: Mapping[str, Any],
    page_ids: set[str],
    auxiliary_files: Mapping[str, Mapping[str, Any]],
    auxiliary_data: Mapping[str, Mapping[str, Any] | None],
) -> dict[str, Any]:
    validation = auxiliary_data.get("validation_report.json") or {}
    split_manifest = auxiliary_data.get("split_manifest.json") or {}
    split_report = auxiliary_data.get("split_manifest.report.json") or {}

    validation_summary = {
        "input_count": validation.get("input_count"),
        "pages_count": validation.get("pages_count"),
        "chunks_count": validation.get("chunks_count"),
        "duplicate_page_id_count": validation.get("duplicate_page_id_count"),
        "duplicate_chunk_id_count": validation.get("duplicate_chunk_id_count"),
        "empty_section_count": validation.get("empty_section_count"),
        "empty_chunk_count": validation.get("empty_chunk_count"),
        "schema_version_mismatch_pages": validation.get("schema_version_mismatch_pages"),
        "schema_version_mismatch_chunks": validation.get("schema_version_mismatch_chunks"),
        "warnings_truncated": validation.get("warnings_truncated"),
        "input_count_matches_pages_v4": validation.get("input_count") == files["pages_v4.jsonl"]["row_count"],
        "pages_count_matches_pages_v4": validation.get("pages_count") == files["pages_v4.jsonl"]["row_count"],
        "chunks_count_matches_chunks_v4": validation.get("chunks_count") == files["chunks_v4.jsonl"]["row_count"],
        "duplicate_page_id_count_clean": validation.get("duplicate_page_id_count") == 0,
        "duplicate_chunk_id_count_clean": validation.get("duplicate_chunk_id_count") == 0,
        "empty_section_count_clean": validation.get("empty_section_count") == 0,
        "empty_chunk_count_clean": validation.get("empty_chunk_count") == 0,
        "schema_version_mismatch_counts_clean": (
            validation.get("schema_version_mismatch_pages") == 0
            and validation.get("schema_version_mismatch_chunks") == 0
        ),
        "warnings_not_truncated": validation.get("warnings_truncated") is False,
    }
    validation_counts_match = (
        validation_summary["input_count_matches_pages_v4"]
        and validation_summary["pages_count_matches_pages_v4"]
        and validation_summary["chunks_count_matches_chunks_v4"]
    )
    validation_clean = (
        validation_summary["duplicate_page_id_count_clean"]
        and validation_summary["duplicate_chunk_id_count_clean"]
        and validation_summary["empty_section_count_clean"]
        and validation_summary["empty_chunk_count_clean"]
        and validation_summary["schema_version_mismatch_counts_clean"]
        and validation_summary["warnings_not_truncated"]
    )

    manifest_doc_ids_by_split = split_manifest_doc_ids_by_split(split_manifest)
    manifest_doc_ids = [doc_id for split_ids in manifest_doc_ids_by_split.values() for doc_id in split_ids]
    manifest_doc_id_counter = Counter(manifest_doc_ids)
    manifest_doc_id_set = set(manifest_doc_ids)
    manifest_duplicate_doc_ids = sorted(
        doc_id for doc_id, count in manifest_doc_id_counter.items() if count > 1
    )
    missing_from_manifest = sorted(page_ids - manifest_doc_id_set)
    extra_in_manifest = sorted(manifest_doc_id_set - page_ids)
    manifest_counts = split_manifest.get("counts", {}) if isinstance(split_manifest.get("counts"), dict) else {}
    manifest_doc_counts = manifest_counts.get("docs", {}) if isinstance(manifest_counts.get("docs"), dict) else {}
    declared_split_doc_counts = {
        split_name: manifest_doc_counts.get(split_name)
        for split_name in ("train", "valid", "test")
    }
    actual_split_doc_counts = {
        split_name: len(manifest_doc_ids_by_split.get(split_name, []))
        for split_name in ("train", "valid", "test")
    }
    declared_total_docs = manifest_doc_counts.get("total")
    declared_doc_count_fields_present = all(
        is_plain_int(manifest_doc_counts.get(split_name))
        for split_name in ("train", "valid", "test", "total")
    )
    declared_split_doc_counts_sum = (
        sum(manifest_doc_counts[split_name] for split_name in ("train", "valid", "test"))
        if declared_doc_count_fields_present
        else None
    )
    declared_split_doc_counts_match_doc_ids = all(
        declared_split_doc_counts[split_name] == actual_split_doc_counts[split_name]
        for split_name in ("train", "valid", "test")
    )
    manifest_doc_counts_clean = (
        declared_doc_count_fields_present
        and declared_split_doc_counts_sum == declared_total_docs
        and declared_split_doc_counts_sum == pages_schema["row_count"]
        and declared_total_docs == len(manifest_doc_ids)
        and declared_split_doc_counts_match_doc_ids
    )
    split_manifest_summary = {
        "schema_version": split_manifest.get("schema_version"),
        "seed": split_manifest.get("seed"),
        "strategy": split_manifest.get("strategy"),
        "warnings_count": len(split_manifest.get("warnings") or []) if isinstance(split_manifest.get("warnings"), list) else None,
        "metadata_expected": (
            split_manifest.get("schema_version") == "namu_anime_v4_split_manifest"
            and split_manifest.get("seed") == 42
            and split_manifest.get("strategy") == "group_level_split"
            and split_manifest.get("warnings") == []
        ),
        "doc_id_count": len(manifest_doc_ids),
        "unique_doc_id_count": len(manifest_doc_id_set),
        "duplicate_doc_id_count": len(manifest_duplicate_doc_ids),
        "duplicate_doc_ids_sample": manifest_duplicate_doc_ids[:10],
        "declared_split_doc_counts": declared_split_doc_counts,
        "actual_split_doc_counts": actual_split_doc_counts,
        "declared_doc_count_fields_present": declared_doc_count_fields_present,
        "declared_split_doc_counts_sum": declared_split_doc_counts_sum,
        "declared_split_doc_counts_sum_matches_total": declared_split_doc_counts_sum == declared_total_docs,
        "declared_split_doc_counts_sum_matches_pages_v4": declared_split_doc_counts_sum == pages_schema["row_count"],
        "declared_split_doc_counts_match_doc_ids": declared_split_doc_counts_match_doc_ids,
        "missing_page_ids_from_split_manifest_count": len(missing_from_manifest),
        "missing_page_ids_from_split_manifest_sample": missing_from_manifest[:10],
        "extra_doc_ids_not_in_pages_v4_count": len(extra_in_manifest),
        "extra_doc_ids_not_in_pages_v4_sample": extra_in_manifest[:10],
        "declared_total_docs": declared_total_docs,
        "declared_total_docs_matches_pages_v4": declared_total_docs == pages_schema["row_count"],
        "declared_total_docs_matches_doc_ids": declared_total_docs == len(manifest_doc_ids),
        "doc_counts_clean": manifest_doc_counts_clean,
        "doc_ids_match_pages_v4": (
            len(manifest_doc_ids) == pages_schema["row_count"]
            and not manifest_duplicate_doc_ids
            and not missing_from_manifest
            and not extra_in_manifest
        ),
    }

    split_doc_counts = split_report.get("split_doc_counts", {})
    if not isinstance(split_doc_counts, dict):
        split_doc_counts = {}
    leakage = split_report.get("leakage", {}) if isinstance(split_report.get("leakage"), dict) else {}
    doc_id_overlap = leakage.get("doc_id_overlap") if isinstance(leakage.get("doc_id_overlap"), list) else []
    group_id_overlap = leakage.get("group_id_overlap") if isinstance(leakage.get("group_id_overlap"), list) else []
    split_report_warnings = split_report.get("warnings") if isinstance(split_report.get("warnings"), list) else []
    distribution = split_report.get("distribution", {}) if isinstance(split_report.get("distribution"), dict) else {}
    chunk_distribution = distribution.get("chunks", {}) if isinstance(distribution.get("chunks"), dict) else {}
    chunk_distribution_sum = sum(int(value) for value in chunk_distribution.values() if isinstance(value, int))
    split_doc_counts_sum = sum(int(value) for value in split_doc_counts.values() if isinstance(value, int))
    split_report_summary = {
        "schema_version": split_report.get("schema_version"),
        "total_docs": split_report.get("total_docs"),
        "total_docs_matches_pages_v4": split_report.get("total_docs") == pages_schema["row_count"],
        "split_doc_counts_sum": split_doc_counts_sum,
        "split_doc_counts_sum_matches_pages_v4": split_doc_counts_sum == pages_schema["row_count"],
        "chunk_distribution_sum": chunk_distribution_sum,
        "chunk_distribution_sum_matches_rag_chunks": chunk_distribution_sum == files["rag_chunks.jsonl"]["row_count"],
        "doc_id_overlap_count": len(doc_id_overlap),
        "group_id_overlap_count": len(group_id_overlap),
        "warnings_count": len(split_report_warnings),
        "clean": (
            split_report.get("schema_version") == "namu_anime_v4_split_report"
            and split_report.get("total_docs") == pages_schema["row_count"]
            and split_doc_counts_sum == pages_schema["row_count"]
            and chunk_distribution_sum == files["rag_chunks.jsonl"]["row_count"]
            and len(doc_id_overlap) == 0
            and len(group_id_overlap) == 0
            and len(split_report_warnings) == 0
        ),
    }

    auxiliary_files_present = all(auxiliary_files[name]["exists"] for name in HARDENED_AUXILIARY_FILES)
    auxiliary_files_parseable = all(
        auxiliary_files[name]["exists"] and auxiliary_files[name]["parse_error"] is None
        for name in HARDENED_AUXILIARY_FILES
    )
    return {
        "auxiliary_files_present": auxiliary_files_present,
        "auxiliary_files_parseable": auxiliary_files_parseable,
        "validation_report": validation_summary,
        "validation_report_counts_match_jsonl": validation_counts_match,
        "validation_report_duplicate_and_empty_counts_clean": validation_clean,
        "split_manifest": split_manifest_summary,
        "split_manifest_doc_ids_match_pages_v4": split_manifest_summary["doc_ids_match_pages_v4"],
        "split_manifest_doc_counts_clean": split_manifest_summary["doc_counts_clean"],
        "split_manifest_metadata_expected": split_manifest_summary["metadata_expected"],
        "split_manifest_report": split_report_summary,
        "split_manifest_report_clean": split_report_summary["clean"],
    }


def split_manifest_doc_ids(split_manifest: Mapping[str, Any]) -> list[str]:
    return [
        doc_id
        for split_ids in split_manifest_doc_ids_by_split(split_manifest).values()
        for doc_id in split_ids
    ]


def split_manifest_doc_ids_by_split(split_manifest: Mapping[str, Any]) -> dict[str, list[str]]:
    doc_ids = split_manifest.get("doc_ids")
    out: dict[str, list[str]] = {"train": [], "valid": [], "test": []}
    if not isinstance(doc_ids, dict):
        return out
    for split_name in ("train", "valid", "test"):
        split_values = doc_ids.get(split_name, [])
        if not isinstance(split_values, list):
            continue
        out[split_name] = [str(value) for value in split_values if str(value)]
    return out


def is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def build_blockers(
    *,
    corpus_dir: Path,
    corpus_exists: bool,
    files: Mapping[str, Mapping[str, Any]],
    hardened_consistency: Mapping[str, Any],
    pages_schema: Mapping[str, Any],
    rag_chunks_schema: Mapping[str, Any],
    context_policy: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if not corpus_exists:
        blockers.append(f"corpus directory does not exist: {normalise_path(corpus_dir)}")
    for name in REQUIRED_FILES:
        file_info = files[name]
        if not file_info["exists"]:
            blockers.append(f"required file missing: {name}")
            continue
        if file_info["parse_error_count"]:
            blockers.append(f"{name} has JSONL parse errors")
        if file_info["non_object_row_count"]:
            blockers.append(f"{name} has non-object JSONL rows")
        if file_info["row_count"] == 0:
            blockers.append(f"{name} has zero JSONL rows")
    if files["pages_v4.jsonl"]["exists"] and not pages_schema["page_id_unique"]:
        blockers.append("pages_v4.jsonl page_id values are missing or duplicated")
    if not hardened_consistency["auxiliary_files_present"]:
        blockers.append("hardened auxiliary corpus reports are missing")
    if not hardened_consistency["auxiliary_files_parseable"]:
        blockers.append("hardened auxiliary corpus reports are not parseable")
    if not hardened_consistency["validation_report_counts_match_jsonl"]:
        blockers.append("validation_report.json counts do not match pages_v4/chunks_v4 row counts")
    if not hardened_consistency["validation_report_duplicate_and_empty_counts_clean"]:
        blockers.append("validation_report.json reports duplicate ids or empty chunks")
    if not hardened_consistency["split_manifest_doc_ids_match_pages_v4"]:
        blockers.append("split_manifest.json doc ids do not match pages_v4.page_id")
    if not hardened_consistency["split_manifest_doc_counts_clean"]:
        blockers.append("split_manifest.json doc counts do not match doc_ids/pages_v4")
    if not hardened_consistency["split_manifest_metadata_expected"]:
        blockers.append("split_manifest.json metadata does not match expected v4 split policy")
    if not hardened_consistency["split_manifest_report_clean"]:
        blockers.append("split_manifest.report.json reports leakage, warnings, or doc-count mismatch")
    if not files["rag_chunks.jsonl"]["exists"]:
        return blockers
    if not rag_chunks_schema["chunk_id_unique"]:
        blockers.append("rag_chunks.jsonl chunk_id values are missing or duplicated")
    if not rag_chunks_schema["page_identity_complete"]:
        blockers.append("rag_chunks.jsonl has no complete page_id or doc_id identity")
    if rag_chunks_schema["page_identity_missing_from_pages_v4_count"] > 0:
        blockers.append("rag_chunks.jsonl page/document ids are not present in pages_v4.page_id")
    if not context_policy["selected_context_field_allowed"]:
        blockers.append("rag_chunks.jsonl has no allowed raw context field")
    if context_policy["selected_disallowed_context_field"]:
        blockers.append("rag_chunks.jsonl selected a disallowed context field")
    if rag_chunks_schema["empty_raw_context_count"] > 0:
        blockers.append("rag_chunks.jsonl has empty raw context text rows")
    if not rag_chunks_schema["raw_context_trust_counters_clean"]:
        blockers.append("rag_chunks.jsonl raw context trust counters are not clean")
    return blockers


def build_warnings(
    files: Mapping[str, Mapping[str, Any]],
    rag_chunks_schema: Mapping[str, Any],
    context_policy: Mapping[str, Any],
) -> list[str]:
    warnings: list[str] = []
    if rag_chunks_schema["missing_page_id_count"] and rag_chunks_schema["page_identifier_field"] == "doc_id":
        warnings.append("rag_chunks.jsonl has no literal page_id; doc_id is populated as the page/document identity.")
    if context_policy["disallowed_fields_present"].get("embedding_text"):
        warnings.append("embedding_text is present in rag_chunks.jsonl but is not selected as answer context.")
    if rag_chunks_schema["text_fallback_accepted"]:
        warnings.append("chunk_text is absent; text was accepted as the raw context field for this fixture shape.")
    if files["chunks_v4.jsonl"]["row_count"] != files["rag_chunks.jsonl"]["row_count"]:
        warnings.append("chunks_v4.jsonl and rag_chunks.jsonl row counts differ; use rag_chunks.jsonl for current joins.")
    return warnings


def clean(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return " > ".join(str(item).strip() for item in value if str(item).strip()).strip()
    return str(value or "").strip()


def is_empty(value: Any) -> bool:
    return clean(value) == ""


def is_json_like_text(value: str) -> bool:
    text = value.strip()
    if not ((text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]"))):
        return False
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return False
    return True


def normalise_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    sys.exit(main())
