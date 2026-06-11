from __future__ import annotations

import argparse
import csv
import heapq
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
AI_DIR = ROOT / "ai"
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from app.capabilities.rag.generation import ExtractiveGenerator, RetrievedChunk


ANSWERABILITY_VALUES = {"answerable", "unanswerable", "unknown"}
DEFAULT_TOP_K_VALUES = (1, 3, 5, 10)
RUN_KIND = "actual_rag_eval_metric_generation_nonprod"
SCHEMA_VERSION = "actual_rag_eval.v1"
REGISTRY_SCHEMA_VERSION = "actual_rag_eval.run_registry.v1"
LATEST_POINTER_SCHEMA_VERSION = "actual_rag_eval.latest_pointer.v1"
STATUS_EVENT_SCHEMA_VERSION = "actual_rag_eval.run_status_event.v1"
REPORT_ROOT = ROOT / "reports" / "rag_eval"
STATUS_JSONL_PATH = AI_DIR / "eval" / "reports" / "rag-ingestion" / "status.jsonl"
SOURCE_NATIVE_INDEX_DIR = AI_DIR / "eval" / "indexes" / "rag-data-all-source-citable-nonprod-v1"
SOURCE_NATIVE_SEARCH_VIEW_MANIFEST_PATH = SOURCE_NATIVE_INDEX_DIR / "search_view_manifest.jsonl"
SOURCE_NATIVE_SOURCE_REGISTRY_PATH = AI_DIR / "eval" / "source_registry" / "source_atom_registry_v1.jsonl"
REGISTRY_FILENAME = "runs.jsonl"
SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
REPORT_ARTIFACT_FILENAMES = (
    "report.json",
    "human_review_packet.csv",
    "rag_eval_items.jsonl",
    "rag_eval_summary.json",
    "rag_eval_report.md",
    "evidence_resolution_candidates.jsonl",
    "evidence_resolution_review.md",
    "evidence_mapping_review_packet.csv",
    "evidence_mapping_review_packet.jsonl",
    "evidence_mapping_review_packet.md",
    "evidence_mapping_packet_summary.json",
)
LOWER_IS_BETTER_COMPARISON_METRICS = {
    "retrieval_empty_rate",
    "bm25_retrieval_empty_rate",
    "vector_retrieval_empty_rate",
    "hybrid_retrieval_empty_rate",
    "generation_empty_rate",
    "citation_empty_rate",
    "pipeline_error_count",
    "schema_warning_count",
    "gold_missing_count",
    "missing_expected_answer_count",
    "missing_expected_evidence_count",
    "missing_answerability_label_count",
    "expected_evidence_id_missing_count",
    "expected_evidence_id_unresolved_count",
    "source_native_retrieval_empty_rate",
    "searchunit_retrieval_empty_rate",
    "source_native_target_span_present_but_not_retrieved_count",
    "source_native_target_span_absent_count",
    "searchunit_target_span_absent_count",
    "both_surfaces_fail_count",
}
RESOLVED_EVIDENCE_COMPARISON_METRICS = {
    "resolved_evidence_available_rate",
    "citation_matches_resolved_evidence_precision_provisional",
    "citation_matches_resolved_evidence_recall_provisional",
    "e2e_rag_success_resolved_evidence_provisional",
}
EVIDENCE_MAPPING_PACKET_COMPARISON_METRICS = {
    "evidence_mapping_packet_candidate_count",
    "evidence_mapping_packet_likely_accept_count",
    "evidence_mapping_packet_possible_match_count",
    "evidence_mapping_packet_review_needed_count",
    "evidence_mapping_packet_likely_reject_count",
    "source_metadata_resolved_candidate_count",
    "source_metadata_unresolved_candidate_count",
}
BACKEND_COMPARISON_METRICS = {
    "bm25_retrieval_empty_rate",
    "vector_retrieval_empty_rate",
    "hybrid_retrieval_empty_rate",
    "bm25_candidate_count_avg",
    "vector_candidate_count_avg",
    "hybrid_candidate_count_avg",
    "bm25_vector_topk_overlap_avg",
    "vector_latency_ms_p50",
    "vector_latency_ms_p95",
    "bm25_latency_ms_p50",
    "bm25_latency_ms_p95",
    "hybrid_latency_ms_p50",
    "hybrid_latency_ms_p95",
    "embedding_build_latency_ms",
    "index_load_or_build_latency_ms",
    "gpu_used_for_embedding_count",
    "vector_index_available",
}
SURFACE_COMPARISON_METRICS = {
    "source_native_retrieval_empty_rate",
    "searchunit_retrieval_empty_rate",
    "source_native_expected_anchor_recall@k_diagnostic",
    "searchunit_expected_anchor_recall@k_diagnostic",
    "source_native_expected_evidence_text_presence_rate",
    "searchunit_expected_evidence_text_presence_rate",
    "expected_evidence_exact_present_in_source_native_count",
    "expected_evidence_normalized_present_in_source_native_count",
    "expected_anchor_present_in_source_native_count",
    "expected_anchor_present_in_searchunit_count",
    "source_native_target_span_present_but_not_retrieved_count",
    "source_native_target_span_absent_count",
    "searchunit_target_span_absent_count",
    "source_native_beats_searchunit_count",
    "searchunit_beats_source_native_count",
    "both_surfaces_fail_count",
}
DIAGNOSTIC_ONLY_COMPARISON_METRICS = {
    "answer_extracted_from_retrieved_context_rate",
    "citation_points_to_retrieved_context_rate",
}

DEFAULT_ABSTENTION_PHRASES = (
    "문서에서 찾을 수 없습니다",
    "문서에서 관련 정보를 찾을 수 없습니다",
    "제공된 context에 답이 없습니다",
    "제공된 문맥에 답이 없습니다",
    "답변할 수 없습니다",
    "근거가 없습니다",
    "not available from the provided context",
    "not found in the provided context",
    "cannot answer from the provided context",
    "no relevant passages were retrieved",
    "not enough information",
)

INFORMATIONAL_LABELS = {"provisional_metric_used", "inferred_answerable_metric_used"}

GENERIC_ANCHOR_STOPWORDS = {
    "a",
    "an",
    "and",
    "answer",
    "animation",
    "anime",
    "context",
    "document",
    "from",
    "source",
    "text",
    "the",
    "tv",
    "애니",
    "애니메이션",
    "감독",
    "기반",
    "대한",
    "만화",
    "문서",
    "방영",
    "시기",
    "시기는",
    "시리즈",
    "라이트",
    "노벨",
    "원작",
    "일본",
    "제3기",
    "정보",
}

KOREAN_GENERIC_SUFFIXES = ("은", "는", "이", "가", "을", "를", "의", "에", "에서", "으로", "로", "와", "과", "도", "만")


class DatasetSchemaError(ValueError):
    """Raised when the eval dataset shape is not executable."""


@dataclass(frozen=True)
class ExpectedEvidence:
    doc_id: str = ""
    chunk_id: str = ""
    text: str = ""
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "chunk_id": self.chunk_id,
            "text": self.text,
            "required": self.required,
        }


@dataclass(frozen=True)
class EvalItem:
    id: str
    query: str
    answerability: str = "unknown"
    expected_answer: str = ""
    expected_answer_aliases: tuple[str, ...] = ()
    expected_evidence: tuple[ExpectedEvidence, ...] = ()
    tags: tuple[str, ...] = ()
    notes: str = ""
    has_answerability_label: bool = False
    validation_warnings: tuple[str, ...] = ()
    source_row: Mapping[str, Any] = field(default_factory=dict)

    @property
    def has_expected_answer(self) -> bool:
        return bool(_clean(self.expected_answer) or any(_clean(alias) for alias in self.expected_answer_aliases))

    @property
    def has_expected_evidence(self) -> bool:
        return bool(self.expected_evidence)


@dataclass(frozen=True)
class RagEvalBundle:
    output_dir: Path
    items_path: Path
    summary_path: Path
    markdown_path: Path
    summary: Mapping[str, Any]
    report_path: Path | None = None


@dataclass(frozen=True)
class EvidenceResolutionConfig:
    enabled: bool = True
    scope: str = "retrieved-only"
    max_candidates: int = 5
    min_score: float = 0.35
    count_medium: bool = False


class ExpectedEvidenceResolver:
    """Diagnostic-only expected-evidence mapper.

    The resolver never mutates gold/qrels and never changes retrieval results.
    It only maps expected evidence rows onto retrieved or candidate index rows
    so reports can show whether evidence IDs are missing, exact, or resolvable.
    """

    def __init__(self, config: EvidenceResolutionConfig | None = None) -> None:
        self.config = config or EvidenceResolutionConfig()

    def resolve_item(
        self,
        item: EvalItem,
        *,
        retrieved_contexts: Sequence[Mapping[str, Any]],
        index_candidates: Sequence[Mapping[str, Any]] = (),
        limitations: Sequence[str] = (),
    ) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        selected_candidates: list[dict[str, Any]] = []
        total_candidate_count = 0
        missing_id_count = 0
        unresolved_count = 0
        exact_count = 0
        candidate_resolved_count = 0
        confidence_counts = Counter()

        for index, evidence in enumerate(item.expected_evidence):
            row = self._resolve_evidence_row(
                item,
                evidence,
                index=index,
                retrieved_contexts=retrieved_contexts,
                index_candidates=index_candidates,
                limitations=limitations,
            )
            rows.append(row)
            total_candidate_count += len(row["candidates"])
            if not evidence.doc_id or not evidence.chunk_id:
                missing_id_count += 1
            if row["id_status"] == "resolved_exact":
                exact_count += 1
            if row["id_status"] == "resolved_candidate":
                candidate_resolved_count += 1
            if row["selected_candidate"]:
                selected_candidates.append(row["selected_candidate"])
                confidence_counts[row["selected_candidate"]["confidence"]] += 1
            if not row["resolved"]:
                unresolved_count += 1

        return {
            "enabled": bool(self.config.enabled),
            "scope": self.config.scope,
            "count_medium": bool(self.config.count_medium),
            "resolved_count": exact_count + candidate_resolved_count,
            "unresolved_count": unresolved_count,
            "missing_id_count": missing_id_count,
            "candidate_count": total_candidate_count,
            "selected_candidates": selected_candidates,
            "confidence_counts": dict(sorted(confidence_counts.items())),
            "rows": rows,
            "limitations": list(limitations),
        }

    def _resolve_evidence_row(
        self,
        item: EvalItem,
        evidence: ExpectedEvidence,
        *,
        index: int,
        retrieved_contexts: Sequence[Mapping[str, Any]],
        index_candidates: Sequence[Mapping[str, Any]],
        limitations: Sequence[str],
    ) -> dict[str, Any]:
        row_candidates = self._candidate_rows(retrieved_contexts, index_candidates)
        warnings: list[str] = []
        if not evidence.doc_id or not evidence.chunk_id:
            warnings.append("missing_doc_or_chunk_id")
        if limitations:
            warnings.extend(limitations)

        candidates: list[dict[str, Any]] = []
        for rank, candidate in enumerate(row_candidates, start=1):
            scored = self._score_candidate(item, evidence, candidate, rank=rank)
            if scored is not None:
                candidates.append(scored)
        candidates.sort(
            key=lambda candidate: (
                {"high": 0, "medium": 1, "low": 2}.get(candidate["confidence"], 3),
                -float(candidate.get("score") or 0.0),
                int(candidate.get("rank") or 10**9),
            )
        )
        candidates = candidates[: max(1, int(self.config.max_candidates))]
        if not candidates:
            anchors = _evidence_resolution_anchors(item, evidence)
            if not anchors:
                warnings.append("no_non_generic_anchor_overlap")
            else:
                warnings.append("no_candidate_anchor_match")

        selected = candidates[0] if candidates else None
        resolved = bool(
            selected
            and (
                selected["confidence"] == "high"
                or (selected["confidence"] == "medium" and self.config.count_medium)
            )
        )
        if selected and not resolved and selected["confidence"] == "medium":
            warnings.append("medium_confidence_not_counted")
        if selected and selected["confidence"] == "low":
            warnings.append("low_confidence_review_only")
        if selected and "no_non_generic_anchor_overlap" in selected.get("match_reasons", []):
            warnings.append("no_non_generic_anchor_overlap")

        if evidence.doc_id and evidence.chunk_id:
            id_status = "present"
        else:
            id_status = "missing"
        if resolved and selected:
            id_status = "resolved_exact" if "exact_id_match" in selected["match_reasons"] else "resolved_candidate"
        elif (evidence.doc_id or evidence.chunk_id) and not resolved:
            id_status = "unresolved"

        return {
            "expected_evidence_index": index,
            "input_doc_id": evidence.doc_id,
            "input_chunk_id": evidence.chunk_id,
            "input_text": evidence.text,
            "id_status": id_status,
            "candidates": candidates,
            "selected_candidate": _selected_candidate(selected) if selected else None,
            "resolved": resolved,
            "resolution_warnings": sorted(set(warnings)),
        }

    def _candidate_rows(
        self,
        retrieved_contexts: Sequence[Mapping[str, Any]],
        index_candidates: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        if self.config.scope in {"retrieved-only", "both"}:
            for context in retrieved_contexts:
                row = dict(context)
                row["_resolution_source"] = "retrieved_contexts"
                key = _context_key(row)
                if key not in seen:
                    rows.append(row)
                    seen.add(key)
        if self.config.scope in {"index-candidate-lookup", "both"}:
            for candidate in index_candidates:
                row = dict(candidate)
                row["_resolution_source"] = "index_candidate_lookup"
                key = _context_key(row)
                if key not in seen:
                    rows.append(row)
                    seen.add(key)
        return rows

    def _score_candidate(
        self,
        item: EvalItem,
        evidence: ExpectedEvidence,
        row: Mapping[str, Any],
        *,
        rank: int,
    ) -> dict[str, Any] | None:
        reasons: list[str] = []
        text = _clean(row.get("text"))
        text_norm = normalize_answer_text(text)
        exact_id = bool((evidence.doc_id or evidence.chunk_id) and _evidence_id_matches_row(evidence, row))
        if exact_id:
            reasons.append("exact_id_match")

        anchors = _evidence_resolution_anchors(item, evidence)
        anchor_hits = sorted(anchor for anchor in anchors if _anchor_in_text([anchor], text))
        required_numeric = _numeric_or_date_anchors(
            _candidate_anchors(item.expected_answer, *item.expected_answer_aliases, evidence.text)
        )
        missing_numeric = sorted(anchor for anchor in required_numeric if not _anchor_in_text([anchor], text))
        if anchor_hits:
            reasons.append(f"anchor_hits:{len(anchor_hits)}")
        else:
            reasons.append("no_non_generic_anchor_overlap")
        if required_numeric and not missing_numeric:
            reasons.append("numeric_or_date_anchors_satisfied")
        elif required_numeric and missing_numeric:
            reasons.append("numeric_or_date_anchor_missing")

        overlap = _token_overlap_ratio(evidence.text, text)
        if overlap >= 0.45:
            reasons.append("strong_text_overlap")
        elif overlap > 0:
            reasons.append("weak_text_overlap")
        overlap_terms = sorted(_token_set(evidence.text) & _token_set(text))
        stopwords = _anchor_stopwords()
        generic_overlap_terms = [term for term in overlap_terms if _is_generic_anchor(term, stopwords)]
        non_generic_overlap_terms = [term for term in overlap_terms if not _is_generic_anchor(term, stopwords)]

        numeric_ok = not missing_numeric
        anchor_score = len(anchor_hits) / max(1, len(anchors))
        score = max(float(row.get("score") or 0.0), round((anchor_score + overlap) / 2, 6))
        confidence = "low"
        if exact_id:
            confidence = "high"
            score = max(score, 1.0)
        elif anchor_hits and numeric_ok and (len(anchor_hits) >= 2 or overlap >= 0.55):
            confidence = "high" if required_numeric else "medium"
        elif anchor_hits and overlap >= self.config.min_score and numeric_ok:
            confidence = "medium"

        if not exact_id and not anchor_hits and overlap < self.config.min_score:
            return None
        return {
            "rank": int(row.get("rank") or rank),
            "doc_id": _clean(row.get("doc_id")),
            "chunk_id": _clean(row.get("chunk_id")),
            "score": round(float(score), 6),
            "confidence": confidence,
            "source": _clean(row.get("_resolution_source")) or "retrieved_contexts",
            "match_reasons": sorted(set(reasons)),
            "text_preview": text[:240],
            "candidate_full_text_hash": _sha256_text(text),
            "anchor_hits": anchor_hits[:12],
            "missing_numeric_or_date_anchors": missing_numeric,
            "candidate_generic_overlap_terms": generic_overlap_terms[:12],
            "candidate_non_generic_anchor_overlap_terms": non_generic_overlap_terms[:12],
            "text_overlap": round(overlap, 6),
        }


def _selected_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": _clean(candidate.get("doc_id")),
        "chunk_id": _clean(candidate.get("chunk_id")),
        "confidence": _clean(candidate.get("confidence")),
        "score": candidate.get("score"),
        "source": _clean(candidate.get("source")),
        "rank": candidate.get("rank"),
        "match_reasons": list(candidate.get("match_reasons") or []),
    }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_clean(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = _clean(row.get(key))
        if value:
            return value
    return ""


def _parse_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    if not (text.startswith("{") or text.startswith("[")):
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _sha256_text(value: Any) -> str:
    return hashlib.sha256(_clean(value).encode("utf-8")).hexdigest() if _clean(value) else ""


def _looks_like_local_path(value: Any) -> bool:
    text = _clean(value)
    if not text:
        return False
    if re.match(r"^[A-Za-z]:[\\/]", text):
        return True
    if text.startswith("\\\\"):
        return True
    return bool(re.search(r"[\\/](Users|Documents|Downloads|Desktop|source_registry|indexes|eval_queries)[\\/]", text))


def _redact_pathish_metadata(value: Any) -> tuple[str, bool]:
    text = _clean(value)
    if not text:
        return "", False
    if _looks_like_local_path(text):
        return f"redacted_path_sha256:{_sha256_text(text)[:16]}", True
    return text, False


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetSchemaError(f"{path}:{line_no}: invalid JSONL row: {exc.msg}") from exc
        if not isinstance(row, dict):
            raise DatasetSchemaError(f"{path}:{line_no}: each JSONL row must be an object")
        rows.append(row)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _load_dataset_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise DatasetSchemaError(f"dataset does not exist: {path}")
    if path.suffix.lower() == ".jsonl":
        return read_jsonl(path)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise DatasetSchemaError(f"{path}: JSON dataset must be a list of objects")
        if not all(isinstance(row, dict) for row in payload):
            raise DatasetSchemaError(f"{path}: JSON dataset entries must be objects")
        return list(payload)
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise DatasetSchemaError(f"{path}: CSV dataset must include a header row")
            return [dict(row) for row in reader]
    raise DatasetSchemaError(f"{path}: unsupported dataset extension; expected .jsonl, .json, or .csv")


def _canonical_answerability(row: Mapping[str, Any]) -> tuple[str, bool]:
    raw = _first_clean(row, "answerability", "answerability_label")
    if raw:
        return raw.lower(), True
    label = _first_clean(row, "normalized_answerability_label", "user_answerability_label")
    if not label:
        return "unknown", False
    normalized = label.strip().upper()
    if "UNANSWERABLE" in normalized:
        return "unanswerable", True
    if normalized.startswith("ANSWERABLE"):
        return "answerable", True
    return "unknown", False


def _expected_answer_aliases(row: Mapping[str, Any]) -> list[str]:
    raw = row.get("expected_answer_aliases") or row.get("aliases") or []
    parsed = _parse_jsonish(raw)
    if isinstance(parsed, list):
        return [_clean(alias) for alias in parsed if isinstance(alias, str) and _clean(alias)]
    if isinstance(parsed, str) and _clean(parsed):
        return [_clean(parsed)]
    return []


def _locator_evidence_fields(row: Mapping[str, Any]) -> tuple[str, str]:
    locator = _parse_jsonish(row.get("citation_locator"))
    if not isinstance(locator, Mapping):
        return "", ""
    cited_chunk_ids = locator.get("cited_chunk_ids")
    chunk_id = ""
    if isinstance(cited_chunk_ids, list) and cited_chunk_ids:
        chunk_id = _clean(cited_chunk_ids[0])
    return (
        _clean(locator.get("file") or locator.get("document_version_id")),
        _clean(locator.get("search_unit_id") or locator.get("chunk_id") or chunk_id),
    )


def _expected_evidence_rows(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = row.get("expected_evidence")
    parsed = _parse_jsonish(raw)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    if raw is not None and _clean(raw):
        return parsed  # type: ignore[return-value]
    text = _first_clean(
        row,
        "supporting_evidence",
        "expected_evidence_text_or_summary",
        "user_expected_evidence_text_or_summary",
        "evidence_summary",
    )
    if not text:
        return []
    doc_id, chunk_id = _locator_evidence_fields(row)
    return [{"doc_id": doc_id, "chunk_id": chunk_id, "text": text, "required": True}]


def load_eval_dataset(path: Path | str) -> list[EvalItem]:
    rows = _load_dataset_rows(Path(path))
    items: list[EvalItem] = []
    seen: set[str] = set()
    for ordinal, row in enumerate(rows, start=1):
        row_id = _clean(row.get("id") or row.get("query_id"))
        context = row_id or f"<row:{ordinal}>"
        if not row_id:
            raise DatasetSchemaError(f"{context}: id is required")
        if row_id in seen:
            raise DatasetSchemaError(f"{row_id}: duplicate id")
        seen.add(row_id)
        query = _first_clean(row, "query", "query_text", "question")
        if not query:
            raise DatasetSchemaError(f"{row_id}: query is required")

        warnings: list[str] = []
        answerability, has_answerability_label = _canonical_answerability(row)
        if not has_answerability_label:
            warnings.append("missing_answerability_label")
        if answerability not in ANSWERABILITY_VALUES:
            raise DatasetSchemaError(
                f"{row_id}: answerability must be one of answerable, unanswerable, unknown"
            )

        aliases = _expected_answer_aliases(row)
        if not isinstance(aliases, list) or not all(isinstance(alias, str) for alias in aliases):
            raise DatasetSchemaError(f"{row_id}: expected_answer_aliases must be a list of strings")

        evidence_rows = _expected_evidence_rows(row)
        if not isinstance(evidence_rows, list):
            raise DatasetSchemaError(f"{row_id}: expected_evidence must be a list")
        evidence: list[ExpectedEvidence] = []
        for index, evidence_row in enumerate(evidence_rows, start=1):
            if not isinstance(evidence_row, dict):
                raise DatasetSchemaError(f"{row_id}: expected_evidence[{index}] must be an object")
            required_value = evidence_row.get("required", True)
            if not isinstance(required_value, bool):
                raise DatasetSchemaError(f"{row_id}: expected_evidence[{index}].required must be a boolean")
            ev = ExpectedEvidence(
                doc_id=_clean(evidence_row.get("doc_id") or evidence_row.get("docId")),
                chunk_id=_clean(evidence_row.get("chunk_id") or evidence_row.get("chunkId")),
                text=_clean(evidence_row.get("text")),
                required=required_value,
            )
            if not (ev.doc_id or ev.chunk_id or ev.text):
                raise DatasetSchemaError(
                    f"{row_id}: expected_evidence[{index}] must include doc_id, chunk_id, or text"
                )
            evidence.append(ev)

        tags = row.get("tags") or []
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise DatasetSchemaError(f"{row_id}: tags must be a list of strings")

        item = EvalItem(
            id=row_id,
            query=query,
            answerability=answerability,
            expected_answer=_first_clean(
                row,
                "expected_answer",
                "expected_answer_text",
                "normalized_expected_answer_text",
                "user_expected_answer_text",
                "expected_answer_text_existing",
            ),
            expected_answer_aliases=tuple(_clean(alias) for alias in aliases if _clean(alias)),
            expected_evidence=tuple(evidence),
            tags=tuple(_clean(tag) for tag in tags if _clean(tag)),
            notes=_clean(row.get("notes")),
            has_answerability_label=has_answerability_label,
            validation_warnings=tuple(warnings),
            source_row=_jsonable(row),
        )
        if not item.has_expected_answer:
            warnings.append("missing_expected_answer")
        if not item.has_expected_evidence:
            warnings.append("missing_expected_evidence")
        if not item.expected_answer_aliases:
            warnings.append("missing_expected_answer_aliases")
        item = EvalItem(
            id=item.id,
            query=item.query,
            answerability=item.answerability,
            expected_answer=item.expected_answer,
            expected_answer_aliases=item.expected_answer_aliases,
            expected_evidence=item.expected_evidence,
            tags=item.tags,
            notes=item.notes,
            has_answerability_label=item.has_answerability_label,
            validation_warnings=tuple(warnings),
            source_row=item.source_row,
        )
        items.append(item)
    return items


def normalize_answer_text(value: str) -> str:
    lowered = _clean(value).casefold()
    lowered = re.sub(r"[^\w\s가-힣ぁ-んァ-ン一-龯々]", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", lowered).strip()


def answer_correct(generated_answer: str, *, expected_answer: str = "", aliases: Sequence[str] = ()) -> bool:
    generated = normalize_answer_text(generated_answer)
    if not generated:
        return False
    expected_values = [expected_answer, *aliases]
    normalized_expected = [normalize_answer_text(value) for value in expected_values if normalize_answer_text(value)]
    return generated in normalized_expected


def abstains(answer: str, *, phrases: Sequence[str] = DEFAULT_ABSTENTION_PHRASES) -> bool:
    normalized = _clean(answer).casefold()
    if not normalized:
        return False
    return any(_clean(phrase).casefold() in normalized for phrase in phrases if _clean(phrase))


def _token_set(value: str) -> set[str]:
    normalized = normalize_answer_text(value)
    return {token for token in normalized.split() if len(token) > 1}


def _token_overlap_ratio(left: str, right: str) -> float:
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))


def _anchor_stopwords() -> set[str]:
    return {normalize_answer_text(value) for value in GENERIC_ANCHOR_STOPWORDS}


def _is_generic_anchor(normalized: str, stopwords: set[str]) -> bool:
    if normalized in stopwords:
        return True
    for stopword in stopwords:
        if not re.fullmatch(r"[가-힣]+", stopword):
            continue
        if any(normalized == f"{stopword}{suffix}" for suffix in KOREAN_GENERIC_SUFFIXES):
            return True
    return False


def _candidate_anchors(*values: str) -> set[str]:
    anchors: set[str] = set()
    stopwords = _anchor_stopwords()
    for value in values:
        raw = _clean(value)
        if not raw:
            continue
        bracketed = re.findall(r"[\[(（【](.*?)[\])）】]", raw)
        scan_values = [raw, *bracketed]
        for scan in scan_values:
            for token in re.findall(
                r"\d{1,4}(?:년|월|일)|\d{2,}|[A-Za-z][A-Za-z0-9_-]{3,}|[가-힣]{3,}|[ぁ-んァ-ン一-龯々]{2,}",
                scan,
            ):
                normalized = normalize_answer_text(token)
                if not normalized or _is_generic_anchor(normalized, stopwords):
                    continue
                anchors.add(normalized)
    return anchors


def _evidence_match_anchors(item: EvalItem, evidence: ExpectedEvidence) -> set[str]:
    return _candidate_anchors(item.expected_answer, *item.expected_answer_aliases, evidence.text)


def _evidence_resolution_anchors(item: EvalItem, evidence: ExpectedEvidence) -> set[str]:
    return _candidate_anchors(item.query, item.expected_answer, *item.expected_answer_aliases, evidence.text)


def _anchor_in_text(anchors: Iterable[str], text: str) -> bool:
    normalized = normalize_answer_text(text)
    token_set = set(normalized.split())
    return any(anchor and (anchor in token_set or anchor in normalized) for anchor in anchors)


def _numeric_or_date_anchors(anchors: Iterable[str]) -> set[str]:
    return {anchor for anchor in anchors if re.search(r"\d", anchor)}


def _anchor_requirements_satisfied(anchors: Iterable[str], text: str) -> bool:
    anchor_set = {anchor for anchor in anchors if anchor}
    if not _anchor_in_text(anchor_set, text):
        return False
    numeric_anchors = _numeric_or_date_anchors(anchor_set)
    if numeric_anchors and not all(_anchor_in_text([anchor], text) for anchor in numeric_anchors):
        return False
    return True


def heuristic_judge_answer(
    *,
    generated_answer: str,
    expected_answer: str = "",
    aliases: Sequence[str] = (),
    expected_evidence_texts: Sequence[str] = (),
    retrieved_context_texts: Sequence[str] = (),
    notes: str = "",
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Deterministic provisional judge used when exact matching is too strict.

    This is deliberately not a replacement for strict exact/alias scoring. It
    produces a separate provisional signal whose prompt/config/version are
    reported in the output bundle.
    """

    generated = _clean(generated_answer)
    if not generated:
        return {
            "passed": False,
            "provisional": True,
            "judge_version": "heuristic_overlap_v1",
            "judge_kind": "deterministic_heuristic",
            "threshold": threshold,
            "reason": "generation_empty",
        }
    expected_values = [expected_answer, *aliases]
    generated_norm = normalize_answer_text(generated)
    for value in expected_values:
        expected_norm = normalize_answer_text(value)
        if expected_norm and expected_norm in generated_norm:
            return {
                "passed": True,
                "provisional": True,
                "judge_version": "heuristic_overlap_v1",
                "judge_kind": "deterministic_heuristic",
                "threshold": threshold,
                "reason": "expected_answer_contained_in_generated_answer",
            }
    anchor_source_values = [value for value in expected_values if _clean(value)] or list(expected_evidence_texts)
    required_numeric_anchors = _numeric_or_date_anchors(_candidate_anchors(*anchor_source_values))
    if required_numeric_anchors and not all(
        _anchor_in_text([anchor], generated)
        for anchor in required_numeric_anchors
    ):
        return {
            "passed": False,
            "provisional": True,
            "judge_version": "heuristic_overlap_v1",
            "judge_kind": "deterministic_heuristic",
            "threshold": threshold,
            "reason": "expected_numeric_or_date_anchor_missing_from_generated_answer",
            "required_numeric_or_date_anchors": sorted(required_numeric_anchors),
        }
    best_evidence_overlap = max(
        [_token_overlap_ratio(generated, evidence_text) for evidence_text in expected_evidence_texts if _clean(evidence_text)]
        or [0.0]
    )
    if best_evidence_overlap >= threshold:
        return {
            "passed": True,
            "provisional": True,
            "judge_version": "heuristic_overlap_v1",
            "judge_kind": "deterministic_heuristic",
            "threshold": threshold,
            "reason": "generated_answer_overlaps_expected_evidence",
            "overlap": round(best_evidence_overlap, 6),
        }
    best_context_overlap = max(
        [_token_overlap_ratio(generated, context_text) for context_text in retrieved_context_texts if _clean(context_text)]
        or [0.0]
    )
    if best_context_overlap >= threshold and not expected_values and not expected_evidence_texts and _clean(notes):
        return {
            "passed": True,
            "provisional": True,
            "judge_version": "heuristic_overlap_v1",
            "judge_kind": "deterministic_heuristic",
            "threshold": threshold,
            "reason": "generated_answer_context_supported_with_notes_only",
            "overlap": round(best_context_overlap, 6),
        }
    return {
        "passed": False,
        "provisional": True,
        "judge_version": "heuristic_overlap_v1",
        "judge_kind": "deterministic_heuristic",
        "threshold": threshold,
        "reason": "insufficient_expected_answer_or_evidence_overlap",
        "best_evidence_overlap": round(best_evidence_overlap, 6),
        "best_context_overlap": round(best_context_overlap, 6),
    }


class HeuristicJudgeAdapter:
    def __init__(self, *, threshold: float = 0.5) -> None:
        self.threshold = float(threshold)

    @property
    def config(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "tier": "provisional",
            "judge_kind": "deterministic_heuristic",
            "judge_version": "heuristic_overlap_v1",
            "threshold": self.threshold,
            "prompt": "No LLM prompt is used by heuristic_overlap_v1; future LLM adapters must record prompt/model/config here.",
            "external_api_calls": False,
        }

    def evaluate(
        self,
        *,
        item: EvalItem,
        generated_answer: str,
        retrieved_context_texts: Sequence[str],
        expected_evidence_texts: Sequence[str],
    ) -> dict[str, Any]:
        return heuristic_judge_answer(
            generated_answer=generated_answer,
            expected_answer=item.expected_answer,
            aliases=item.expected_answer_aliases,
            expected_evidence_texts=expected_evidence_texts,
            retrieved_context_texts=retrieved_context_texts,
            notes=item.notes,
            threshold=self.threshold,
        )


LLM_JUDGE_PROMPT_VERSION = "local_llm_semantic_rag_judge_v1"
LLM_JUDGE_PROMPT_TEMPLATE = """You are a provisional RAG evaluation judge.
Return exactly one JSON object with keys: passed (boolean), confidence (number from 0 to 1), reason (string), and evidence_basis (string).
Judge whether the generated answer is semantically correct using only the expected answer, aliases, expected evidence, notes, and retrieved context below.
Do not use outside knowledge. If gold is partial, prefer conservative support from expected evidence or retrieved context.

Payload:
{payload}
"""


class LocalLLMJudgeAdapter:
    """Optional localhost-only LLM judge adapter using the repo's existing helper."""

    def __init__(
        self,
        *,
        backend: str = "",
        base_url: str = "",
        model: str = "",
        threshold: float = 0.6,
        max_tokens: int = 360,
        timeout_seconds: int = 60,
        check_endpoint: bool = True,
    ) -> None:
        from scripts import rag_local_llm_expected_answer_generation_v1 as local_llm

        self._local_llm = local_llm
        self.backend = _clean(backend) or local_llm.DEFAULT_BACKEND
        self.base_url = local_llm.resolve_base_url(self.backend, _clean(base_url))
        self.model = _clean(model) or local_llm.DEFAULT_MODEL
        self.threshold = float(threshold)
        self.max_tokens = int(max_tokens)
        self.timeout_seconds = int(timeout_seconds)
        self.check_endpoint = bool(check_endpoint)
        self.blockers = local_llm.local_llm_entry_blockers(
            backend=self.backend,
            base_url=self.base_url,
            model=self.model,
            check_endpoint=self.check_endpoint,
            timeout_seconds=min(self.timeout_seconds, 10),
        )

    @property
    def available(self) -> bool:
        return not self.blockers

    @property
    def config(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "tier": "provisional",
            "judge_kind": "local_llm_strict_json",
            "judge_version": LLM_JUDGE_PROMPT_VERSION,
            "backend": self.backend,
            "base_url": self.base_url,
            "model": self.model,
            "threshold": self.threshold,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "check_endpoint": self.check_endpoint,
            "available": self.available,
            "blockers": list(self.blockers),
            "prompt": LLM_JUDGE_PROMPT_TEMPLATE,
            "external_api_calls": False,
        }

    def evaluate(
        self,
        *,
        item: EvalItem,
        generated_answer: str,
        retrieved_context_texts: Sequence[str],
        expected_evidence_texts: Sequence[str],
    ) -> dict[str, Any]:
        if not self.available:
            return {
                "passed": False,
                "available": False,
                "provisional": True,
                "judge_kind": "local_llm_strict_json",
                "judge_version": LLM_JUDGE_PROMPT_VERSION,
                "threshold": self.threshold,
                "reason": "local_llm_unavailable",
                "blockers": list(self.blockers),
            }
        payload = {
            "id": item.id,
            "query": item.query,
            "answerability": item.answerability,
            "generated_answer": generated_answer,
            "expected_answer": item.expected_answer,
            "expected_answer_aliases": list(item.expected_answer_aliases),
            "expected_evidence_texts": list(expected_evidence_texts)[:6],
            "retrieved_context_texts": [text[:1200] for text in retrieved_context_texts[:6]],
            "notes": item.notes,
            "threshold": self.threshold,
        }
        prompt = LLM_JUDGE_PROMPT_TEMPLATE.format(payload=json.dumps(payload, ensure_ascii=False, sort_keys=True))
        try:
            parsed, meta = self._local_llm.call_local_llm_strict_json(
                backend=self.backend,
                base_url=self.base_url,
                model=self.model,
                prompt=prompt,
                temperature=0.0,
                max_tokens=self.max_tokens,
                timeout_seconds=self.timeout_seconds,
            )
        except Exception as exc:
            return {
                "passed": False,
                "available": False,
                "provisional": True,
                "judge_kind": "local_llm_strict_json",
                "judge_version": LLM_JUDGE_PROMPT_VERSION,
                "threshold": self.threshold,
                "reason": f"local_llm_judge_error: {type(exc).__name__}: {exc}",
            }
        confidence = float(parsed.get("confidence") or 0.0)
        passed = bool(parsed.get("passed")) and confidence >= self.threshold
        return {
            "passed": passed,
            "available": True,
            "provisional": True,
            "judge_kind": "local_llm_strict_json",
            "judge_version": LLM_JUDGE_PROMPT_VERSION,
            "threshold": self.threshold,
            "confidence": round(confidence, 6),
            "reason": _clean(parsed.get("reason")) or "local_llm_judge_completed",
            "evidence_basis": _clean(parsed.get("evidence_basis")),
            "raw_response_sha256": (meta or {}).get("raw_response_sha256"),
        }


def _context_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _clean(row.get("doc_id") or row.get("docId") or row.get("document_id") or row.get("documentId")),
        _clean(row.get("chunk_id") or row.get("chunkId") or row.get("search_unit_id") or row.get("searchUnitId")),
        normalize_answer_text(_clean(row.get("text"))),
    )


def _evidence_id_matches_row(evidence: ExpectedEvidence, row: Mapping[str, Any]) -> bool:
    doc_id, chunk_id, _text_norm = _context_key(row)
    if evidence.chunk_id and chunk_id == evidence.chunk_id and (not evidence.doc_id or doc_id == evidence.doc_id):
        return True
    if evidence.doc_id and doc_id == evidence.doc_id and not evidence.chunk_id:
        return True
    return False


def _evidence_matches_row(evidence: ExpectedEvidence, row: Mapping[str, Any]) -> bool:
    if _evidence_id_matches_row(evidence, row):
        return True
    _doc_id, _chunk_id, text_norm = _context_key(row)
    expected_text = normalize_answer_text(evidence.text)
    return bool(expected_text and expected_text in text_norm)


def _weak_evidence_matches_row(
    evidence: ExpectedEvidence,
    row: Mapping[str, Any],
    *,
    anchors: Iterable[str] = (),
    threshold: float = 0.45,
) -> bool:
    if _evidence_id_matches_row(evidence, row):
        return True
    expected_text = _clean(evidence.text)
    row_text = _clean(row.get("text"))
    return bool(
        expected_text
        and row_text
        and _token_overlap_ratio(expected_text, row_text) >= threshold
        and _anchor_requirements_satisfied(anchors, row_text)
    )


def _required_evidence(item: EvalItem) -> list[ExpectedEvidence]:
    required = [evidence for evidence in item.expected_evidence if evidence.required]
    return required or list(item.expected_evidence)


def _contexts_top_k(contexts: Sequence[Mapping[str, Any]], k: int) -> list[Mapping[str, Any]]:
    return [
        row
        for row in sorted(contexts, key=lambda item: int(item.get("rank") or 10**9))
        if int(row_rank(row)) <= k
    ]


def row_rank(row: Mapping[str, Any]) -> int:
    try:
        return int(row.get("rank") or 10**9)
    except (TypeError, ValueError):
        return 10**9


def _all_required_evidence_present(
    item: EvalItem,
    rows: Sequence[Mapping[str, Any]],
) -> bool:
    required = _required_evidence(item)
    return bool(required) and all(any(_evidence_matches_row(evidence, row) for row in rows) for evidence in required)


def _all_required_weak_evidence_present(
    item: EvalItem,
    rows: Sequence[Mapping[str, Any]],
) -> bool:
    required = _required_evidence(item)
    return bool(required) and all(
        any(_weak_evidence_matches_row(evidence, row, anchors=_evidence_match_anchors(item, evidence)) for row in rows)
        for evidence in required
    )


def _count_required_evidence_matches(
    item: EvalItem,
    rows: Sequence[Mapping[str, Any]],
) -> int:
    return sum(1 for evidence in _required_evidence(item) if any(_evidence_matches_row(evidence, row) for row in rows))


def _count_required_weak_evidence_matches(
    item: EvalItem,
    rows: Sequence[Mapping[str, Any]],
) -> int:
    return sum(
        1
        for evidence in _required_evidence(item)
        if any(_weak_evidence_matches_row(evidence, row, anchors=_evidence_match_anchors(item, evidence)) for row in rows)
    )


def _count_matching_citations(
    item: EvalItem,
    citations: Sequence[Mapping[str, Any]],
) -> int:
    return sum(1 for citation in citations if any(_evidence_matches_row(evidence, citation) for evidence in item.expected_evidence))


def _resolved_evidence_candidates(resolution: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in _as_list(resolution.get("rows")):
        if not isinstance(row, Mapping) or not row.get("resolved"):
            continue
        selected = row.get("selected_candidate")
        if isinstance(selected, Mapping):
            candidate = dict(selected)
            candidate["expected_evidence_index"] = row.get("expected_evidence_index")
            candidates.append(candidate)
    return candidates


def _candidate_matches_context(candidate: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    candidate_doc = _clean(candidate.get("doc_id"))
    candidate_chunk = _clean(candidate.get("chunk_id"))
    row_doc, row_chunk, _row_text = _context_key(row)
    if candidate_chunk and row_chunk == candidate_chunk and (not candidate_doc or row_doc == candidate_doc):
        return True
    if candidate_doc and row_doc == candidate_doc and not candidate_chunk:
        return True
    return False


def _all_resolved_candidates_present(
    candidates: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
) -> bool:
    return bool(candidates) and all(any(_candidate_matches_context(candidate, row) for row in rows) for candidate in candidates)


def _count_matching_resolved_candidate_rows(
    candidates: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
) -> int:
    return sum(1 for candidate in candidates if any(_candidate_matches_context(candidate, row) for row in rows))


def _count_citations_matching_resolved_candidates(
    candidates: Sequence[Mapping[str, Any]],
    citations: Sequence[Mapping[str, Any]],
) -> int:
    return sum(1 for citation in citations if any(_candidate_matches_context(candidate, citation) for candidate in candidates))


def _metric_template(name: str, denominator_policy: str, *, tier: str = "strict") -> dict[str, Any]:
    return {
        "name": name,
        "tier": tier,
        "numerator": 0,
        "denominator": 0,
        "score": None,
        "skipped_count": 0,
        "not_applicable_count": 0,
        "diagnostic_only_count": 0,
        "exclusion_reasons": {},
        "denominator_policy": denominator_policy,
    }


def _exclude(metric: dict[str, Any], reason: str, *, diagnostic_only: bool = False) -> None:
    metric["skipped_count"] += 1
    metric["not_applicable_count"] += 1
    if diagnostic_only:
        metric["diagnostic_only_count"] += 1
    metric["exclusion_reasons"][reason] = metric["exclusion_reasons"].get(reason, 0) + 1


def _finish_metric(metric: dict[str, Any]) -> dict[str, Any]:
    denominator = metric["denominator"]
    metric["score"] = None if denominator == 0 else round(metric["numerator"] / denominator, 6)
    metric["exclusion_reasons"] = dict(sorted(metric["exclusion_reasons"].items()))
    return metric


def score_rag_eval_items(
    items: Sequence[EvalItem],
    item_outputs: Sequence[Mapping[str, Any]],
    *,
    top_k_values: Sequence[int] = DEFAULT_TOP_K_VALUES,
    abstention_phrases: Sequence[str] = DEFAULT_ABSTENTION_PHRASES,
    judge_adapter: Any | None = None,
    provisional_require_citations: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    outputs_by_id = {_clean(output.get("id")): output for output in item_outputs}
    k_values = tuple(sorted({int(k) for k in top_k_values if int(k) > 0})) or DEFAULT_TOP_K_VALUES
    primary_k = max(k_values)
    judge_adapter = judge_adapter or HeuristicJudgeAdapter()

    answer_metric = _metric_template(
        "exact_or_alias_answer_correctness",
        "answerable items with expected_answer or aliases only",
    )
    abstention_metric = _metric_template("abstention_accuracy", "unanswerable items only")
    citation_precision = _metric_template(
        "citation_precision",
        "generated citation rows for items with citations and expected evidence",
    )
    citation_recall = _metric_template(
        "citation_recall",
        "required expected evidence rows for items with citations and expected evidence",
    )
    e2e_metric = _metric_template(
        "e2e_rag_success_strict",
        f"answerable items with expected answer and expected evidence; evidence recall@{primary_k}; citations required",
    )
    judged_answer = _metric_template(
        "judged_answer_correctness_provisional",
        "items with generated answers plus expected answer, aliases, notes, or expected evidence signal",
        tier="provisional",
    )
    answer_context_consistency = _metric_template(
        "answer_extracted_from_retrieved_context_rate",
        "diagnostic consistency check only: generated answer overlaps retrieved context; not answer correctness",
        tier="diagnostic",
    )
    citation_points_to_context = _metric_template(
        "citation_points_to_retrieved_context_rate",
        "diagnostic consistency check only: citation points to retrieved context; strict citation metrics handle gold evidence correctness",
        tier="diagnostic",
    )
    e2e_provisional = _metric_template(
        "e2e_rag_success_provisional",
        f"items with generated answer, context, judge signal, expected evidence, judge pass, context consistency, and weak/strict evidence at top-{primary_k}",
        tier="provisional",
    )
    inferred_answer_metric = _metric_template(
        "exact_or_alias_answer_correctness_inferred_answerable",
        "unknown-answerability rows with expected answer and expected evidence; answerable inferred for this metric only",
        tier="inferred_answerable",
    )
    inferred_evidence_metrics = {
        k: _metric_template(
            f"evidence_recall@{k}_inferred_answerable",
            f"unknown-answerability rows with expected answer/evidence; answerable inferred for evidence recall@{k} only",
            tier="inferred_answerable",
        )
        for k in k_values
    }
    inferred_e2e_metric = _metric_template(
        "e2e_rag_success_inferred_answerable",
        f"unknown-answerability rows with expected answer/evidence; requires exact/alias answer and evidence recall@{primary_k}; no gold label mutation",
        tier="inferred_answerable",
    )
    evidence_metrics = {
        k: _metric_template(
            f"evidence_recall@{k}",
            f"answerable items with expected evidence; all required evidence must appear in top-{k}",
        )
        for k in k_values
    }
    weak_evidence_metrics = {
        k: _metric_template(
            f"weak_evidence_match_recall@{k}",
            f"items with expected evidence; id match or weak text overlap in top-{k}",
            tier="provisional",
        )
        for k in k_values
    }
    resolved_evidence_available = _metric_template(
        "resolved_evidence_available_rate",
        "expected evidence rows with selected high-confidence diagnostic candidate; medium counted only when configured",
        tier="provisional",
    )
    resolved_evidence_recall_metrics = {
        k: _metric_template(
            f"resolved_evidence_recall@{k}_provisional",
            f"items with at least one resolved expected evidence candidate; all selected candidates appear in top-{k}",
            tier="provisional",
        )
        for k in k_values
    }
    resolved_citation_precision = _metric_template(
        "citation_matches_resolved_evidence_precision_provisional",
        "generated citation rows for items with resolved expected evidence candidates",
        tier="provisional",
    )
    resolved_citation_recall = _metric_template(
        "citation_matches_resolved_evidence_recall_provisional",
        "resolved expected evidence candidates for items with citations",
        tier="provisional",
    )
    e2e_resolved_evidence = _metric_template(
        "e2e_rag_success_resolved_evidence_provisional",
        f"items with judge signal and resolved evidence candidates; requires judge pass and resolved evidence recall@{primary_k}",
        tier="provisional",
    )

    diagnostics = {
        "retrieval_empty_count": 0,
        "retrieval_empty_rate": 0.0,
        "generation_empty_count": 0,
        "generation_empty_rate": 0.0,
        "citation_empty_count": 0,
        "citation_empty_rate": 0.0,
        "average_context_count": 0.0,
        "average_context_chars": 0.0,
        "gold_incomplete_count": 0,
        "gold_missing_count": 0,
        "missing_expected_answer_count": 0,
        "missing_expected_evidence_count": 0,
        "missing_answerability_label_count": 0,
        "expected_evidence_id_missing_count": 0,
        "expected_evidence_id_present_count": 0,
        "expected_evidence_id_resolved_exact_count": 0,
        "expected_evidence_id_resolved_candidate_count": 0,
        "expected_evidence_id_unresolved_count": 0,
        "expected_evidence_row_count": 0,
        "expected_evidence_text_match_candidate_count": 0,
        "expected_evidence_resolution_enabled": False,
        "expected_evidence_resolution_scope": "disabled",
        "expected_evidence_resolution_candidate_count": 0,
        "expected_evidence_resolution_high_confidence_count": 0,
        "expected_evidence_resolution_medium_confidence_count": 0,
        "expected_evidence_resolution_low_confidence_count": 0,
        "expected_evidence_resolution_review_only_count": 0,
        "schema_warning_count": 0,
        "pipeline_error_count": 0,
        "answerable_count": 0,
        "unanswerable_count": 0,
        "unknown_answerability_count": 0,
        "not_applicable_counts_by_metric": {},
        "failure_category_counts": {},
    }

    scored_rows: list[dict[str, Any]] = []
    total_context_count = 0
    total_context_chars = 0

    for item in items:
        output = dict(outputs_by_id.get(item.id) or _pipeline_error_output(item, "missing_pipeline_output"))
        contexts = [dict(row) for row in _as_list(output.get("retrieved_contexts")) if isinstance(row, Mapping)]
        citations = [dict(row) for row in _as_list(output.get("citations")) if isinstance(row, Mapping)]
        generated_answer = _clean(output.get("generated_answer"))
        answerability = item.answerability
        failure_labels: set[str] = set(output.get("failure_labels") or [])
        metric_results: dict[str, Any] = {}
        evidence_id_diagnostics: list[dict[str, Any]] = []
        evidence_resolution = (
            output.get("expected_evidence_resolution")
            if isinstance(output.get("expected_evidence_resolution"), Mapping)
            else {"enabled": False, "scope": "disabled", "rows": [], "selected_candidates": []}
        )
        resolution_enabled = bool(evidence_resolution.get("enabled"))

        total_context_count += len(contexts)
        total_context_chars += sum(len(_clean(row.get("text"))) for row in contexts)

        if not contexts:
            diagnostics["retrieval_empty_count"] += 1
            failure_labels.add("retrieval_empty")
        if not generated_answer:
            diagnostics["generation_empty_count"] += 1
            failure_labels.add("generation_empty")
        if not citations:
            diagnostics["citation_empty_count"] += 1

        if not item.has_answerability_label:
            diagnostics["missing_answerability_label_count"] += 1
            failure_labels.add("gold_missing_answerability")
        if not item.has_expected_answer:
            diagnostics["missing_expected_answer_count"] += 1
            if answerability == "answerable":
                failure_labels.add("gold_missing_expected_answer")
        if not item.has_expected_evidence:
            diagnostics["missing_expected_evidence_count"] += 1
            if answerability == "answerable":
                failure_labels.add("gold_missing_expected_evidence")
        diagnostics["schema_warning_count"] += len(item.validation_warnings)

        for evidence in item.expected_evidence:
            evidence_anchors = _evidence_match_anchors(item, evidence)
            if not resolution_enabled and (not evidence.doc_id or not evidence.chunk_id):
                diagnostics["expected_evidence_id_missing_count"] += 1
            id_match = any(_evidence_id_matches_row(evidence, context) for context in contexts)
            if not resolution_enabled and (evidence.doc_id or evidence.chunk_id) and not id_match:
                diagnostics["expected_evidence_id_unresolved_count"] += 1
            text_match_candidate = bool(
                not id_match
                and evidence.text
                and any(
                    _weak_evidence_matches_row(evidence, context, anchors=evidence_anchors)
                    for context in contexts
                )
            )
            if text_match_candidate:
                diagnostics["expected_evidence_text_match_candidate_count"] += 1
            evidence_id_diagnostics.append(
                {
                    "doc_id": evidence.doc_id,
                    "chunk_id": evidence.chunk_id,
                    "doc_id_missing": not bool(evidence.doc_id),
                    "chunk_id_missing": not bool(evidence.chunk_id),
                    "id_resolved_in_retrieved_contexts": id_match,
                    "text_match_candidate": text_match_candidate,
                    "match_type": "id" if id_match else "weak_text_candidate" if text_match_candidate else "unresolved",
                    "candidate_anchor_count": len(evidence_anchors),
                }
            )

        if resolution_enabled:
            diagnostics["expected_evidence_resolution_enabled"] = True
            diagnostics["expected_evidence_resolution_scope"] = _clean(evidence_resolution.get("scope")) or "retrieved-only"
            resolution_rows = [row for row in _as_list(evidence_resolution.get("rows")) if isinstance(row, Mapping)]
            diagnostics["expected_evidence_row_count"] += len(resolution_rows)
            for resolution_row in resolution_rows:
                selected = resolution_row.get("selected_candidate") if isinstance(resolution_row.get("selected_candidate"), Mapping) else {}
                confidence = _clean(selected.get("confidence"))
                if resolution_row.get("input_doc_id") and resolution_row.get("input_chunk_id"):
                    diagnostics["expected_evidence_id_present_count"] += 1
                else:
                    diagnostics["expected_evidence_id_missing_count"] += 1
                if resolution_row.get("id_status") == "resolved_exact":
                    diagnostics["expected_evidence_id_resolved_exact_count"] += 1
                if resolution_row.get("id_status") == "resolved_candidate":
                    diagnostics["expected_evidence_id_resolved_candidate_count"] += 1
                if not resolution_row.get("resolved"):
                    diagnostics["expected_evidence_id_unresolved_count"] += 1
                diagnostics["expected_evidence_resolution_candidate_count"] += len(
                    _as_list(resolution_row.get("candidates"))
                )
                if confidence == "high":
                    diagnostics["expected_evidence_resolution_high_confidence_count"] += 1
                elif confidence == "medium":
                    diagnostics["expected_evidence_resolution_medium_confidence_count"] += 1
                    if not resolution_row.get("resolved"):
                        diagnostics["expected_evidence_resolution_review_only_count"] += 1
                elif confidence == "low":
                    diagnostics["expected_evidence_resolution_low_confidence_count"] += 1
                    diagnostics["expected_evidence_resolution_review_only_count"] += 1
            if any(not row.get("resolved") for row in resolution_rows):
                failure_labels.add("expected_evidence_resolution_unresolved")
            if any(row.get("resolved") for row in resolution_rows):
                failure_labels.add("provisional_metric_used")
        else:
            diagnostics["expected_evidence_row_count"] += len(item.expected_evidence)

        gold_incomplete = (
            not item.has_answerability_label
            or (answerability == "answerable" and (not item.has_expected_answer or not item.has_expected_evidence))
        )
        if gold_incomplete:
            diagnostics["gold_incomplete_count"] += 1
            diagnostics["gold_missing_count"] += 1
            failure_labels.add("metric_not_applicable")

        answer_pass = False
        if answerability == "answerable" and item.has_expected_answer:
            answer_metric["denominator"] += 1
            answer_pass = answer_correct(
                generated_answer,
                expected_answer=item.expected_answer,
                aliases=item.expected_answer_aliases,
            )
            answer_metric["numerator"] += int(answer_pass)
            if not answer_pass:
                failure_labels.add("answer_exact_mismatch")
        else:
            reason = (
                "missing_expected_answer"
                if answerability == "answerable"
                else f"answerability_{answerability}_not_in_answer_correctness_denominator"
            )
            _exclude(answer_metric, reason, diagnostic_only=gold_incomplete)
            failure_labels.add("strict_metric_not_applicable")
        metric_results["exact_or_alias_answer_correctness"] = (
            answer_pass if answerability == "answerable" and item.has_expected_answer else None
        )

        evidence_pass_by_k: dict[int, bool | None] = {}
        for k, metric in evidence_metrics.items():
            if answerability == "answerable" and item.has_expected_evidence:
                metric["denominator"] += 1
                passed = _all_required_evidence_present(item, _contexts_top_k(contexts, k))
                evidence_pass_by_k[k] = passed
                metric["numerator"] += int(passed)
                if k == primary_k and not passed:
                    failure_labels.add("evidence_not_retrieved")
            else:
                reason = (
                    "missing_expected_evidence"
                    if answerability == "answerable"
                    else f"answerability_{answerability}_not_in_evidence_recall_denominator"
                )
                _exclude(metric, reason, diagnostic_only=gold_incomplete)
                evidence_pass_by_k[k] = None
                failure_labels.add("strict_metric_not_applicable")
        metric_results.update({f"evidence_recall@{k}": value for k, value in evidence_pass_by_k.items()})

        weak_evidence_pass_by_k: dict[int, bool | None] = {}
        for k, metric in weak_evidence_metrics.items():
            if item.has_expected_evidence:
                metric["denominator"] += 1
                weak_pass = _all_required_weak_evidence_present(item, _contexts_top_k(contexts, k))
                weak_evidence_pass_by_k[k] = weak_pass
                metric["numerator"] += int(weak_pass)
                if weak_pass:
                    failure_labels.add("provisional_metric_used")
            else:
                _exclude(metric, "missing_expected_evidence", diagnostic_only=True)
                weak_evidence_pass_by_k[k] = None
        metric_results.update(
            {f"weak_evidence_match_recall@{k}": value for k, value in weak_evidence_pass_by_k.items()}
        )

        resolved_candidates = _resolved_evidence_candidates(evidence_resolution)
        resolution_rows = [row for row in _as_list(evidence_resolution.get("rows")) if isinstance(row, Mapping)]
        for resolution_row in resolution_rows:
            resolved_evidence_available["denominator"] += 1
            resolved_evidence_available["numerator"] += int(bool(resolution_row.get("resolved")))
        metric_results["resolved_evidence_available_rate"] = {
            "resolved_count": sum(1 for row in resolution_rows if row.get("resolved")),
            "expected_evidence_row_count": len(resolution_rows),
            "provisional": True,
        } if resolution_rows else None

        resolved_recall_pass_by_k: dict[int, bool | None] = {}
        for k, metric in resolved_evidence_recall_metrics.items():
            if resolved_candidates:
                metric["denominator"] += 1
                passed = _all_resolved_candidates_present(resolved_candidates, _contexts_top_k(contexts, k))
                resolved_recall_pass_by_k[k] = passed
                metric["numerator"] += int(passed)
            else:
                _exclude(metric, "missing_resolved_expected_evidence", diagnostic_only=True)
                resolved_recall_pass_by_k[k] = None
        metric_results.update(
            {f"resolved_evidence_recall@{k}_provisional": value for k, value in resolved_recall_pass_by_k.items()}
        )

        if citations and resolved_candidates:
            resolved_citation_precision["denominator"] += len(citations)
            resolved_citation_precision["numerator"] += _count_citations_matching_resolved_candidates(
                resolved_candidates,
                citations,
            )
            resolved_citation_recall["denominator"] += len(resolved_candidates)
            resolved_citation_recall["numerator"] += _count_matching_resolved_candidate_rows(
                resolved_candidates,
                citations,
            )
        else:
            _exclude(
                resolved_citation_precision,
                "missing_citations_or_resolved_expected_evidence",
                diagnostic_only=True,
            )
            _exclude(
                resolved_citation_recall,
                "missing_citations_or_resolved_expected_evidence",
                diagnostic_only=True,
            )

        if citations and item.has_expected_evidence:
            matching_citations = _count_matching_citations(item, citations)
            citation_precision["denominator"] += len(citations)
            citation_precision["numerator"] += matching_citations
            citation_precision["eligible_item_count"] = citation_precision.get("eligible_item_count", 0) + 1
            if matching_citations != len(citations):
                failure_labels.add("citation_wrong")

            required_count = len(_required_evidence(item))
            cited_required_count = _count_required_evidence_matches(item, citations)
            citation_recall["denominator"] += required_count
            citation_recall["numerator"] += cited_required_count
            citation_recall["eligible_item_count"] = citation_recall.get("eligible_item_count", 0) + 1
            if cited_required_count != required_count:
                failure_labels.add("citation_wrong")
            citation_check_pass = matching_citations == len(citations) and cited_required_count == required_count
        else:
            reason = "missing_citations" if item.has_expected_evidence else "missing_expected_evidence"
            _exclude(citation_precision, reason, diagnostic_only=gold_incomplete)
            _exclude(citation_recall, reason, diagnostic_only=gold_incomplete)
            citation_check_pass = False
            if item.has_expected_evidence:
                failure_labels.add("citation_missing")
            failure_labels.add("strict_metric_not_applicable")
        metric_results["citation_check_pass"] = citation_check_pass if item.has_expected_evidence else None

        if citations:
            overlap_hits = 0
            for citation in citations:
                citation_text = _clean(citation.get("text"))
                context_match = any(
                    _weak_evidence_matches_row(
                        ExpectedEvidence(text=citation_text),
                        context,
                        anchors=_candidate_anchors(citation_text),
                    )
                    for context in contexts
                )
                id_context_match = any(
                    _context_key(citation)[:2] == _context_key(context)[:2]
                    and any(_context_key(citation)[:2])
                    for context in contexts
                )
                if context_match or id_context_match:
                    overlap_hits += 1
            citation_points_to_context["denominator"] += len(citations)
            citation_points_to_context["numerator"] += overlap_hits
            metric_results["citation_points_to_retrieved_context_rate"] = {
                "passed_count": overlap_hits,
                "citation_count": len(citations),
                "diagnostic_only": True,
            }
        else:
            _exclude(citation_points_to_context, "missing_citations", diagnostic_only=True)
            metric_results["citation_points_to_retrieved_context_rate"] = None

        if answerability == "unanswerable":
            abstention_metric["denominator"] += 1
            abstention_pass = abstains(generated_answer, phrases=abstention_phrases)
            abstention_metric["numerator"] += int(abstention_pass)
            if not abstention_pass:
                failure_labels.add("abstention_failed")
                if generated_answer:
                    failure_labels.add("answered_unanswerable")
        else:
            _exclude(
                abstention_metric,
                f"answerability_{answerability}_not_in_abstention_denominator",
                diagnostic_only=answerability == "unknown",
            )

        context_texts = [_clean(context.get("text")) for context in contexts if _clean(context.get("text"))]
        expected_evidence_texts = [evidence.text for evidence in item.expected_evidence if _clean(evidence.text)]
        judge_signal_available = bool(
            generated_answer
            and answerability != "unanswerable"
            and (
                item.has_expected_answer
                or expected_evidence_texts
                or _clean(item.notes)
            )
        )
        judge_result: dict[str, Any] | None = None
        judge_pass = False
        if judge_signal_available:
            judge_result = judge_adapter.evaluate(
                item=item,
                generated_answer=generated_answer,
                expected_evidence_texts=expected_evidence_texts,
                retrieved_context_texts=context_texts,
            )
            if judge_result.get("available", True) is False:
                _exclude(judged_answer, "judge_unavailable", diagnostic_only=True)
                failure_labels.add("answer_judge_unavailable")
            else:
                judged_answer["denominator"] += 1
                judge_pass = bool(judge_result["passed"])
                judged_answer["numerator"] += int(judge_pass)
                failure_labels.add("provisional_metric_used")
                if not judge_pass:
                    failure_labels.add("answer_judge_fail")
        else:
            _exclude(judged_answer, "missing_generated_answer_or_judge_signal", diagnostic_only=True)
            if generated_answer:
                failure_labels.add("answer_judge_unavailable")
        metric_results["judged_answer_correctness_provisional"] = judge_result

        support_pass = False
        if generated_answer and contexts:
            answer_context_consistency["denominator"] += 1
            best_context_overlap = max((_token_overlap_ratio(generated_answer, text) for text in context_texts), default=0.0)
            support_pass = best_context_overlap >= 0.35
            answer_context_consistency["numerator"] += int(support_pass)
            metric_results["answer_extracted_from_retrieved_context_rate"] = {
                "passed": support_pass,
                "best_context_overlap": round(best_context_overlap, 6),
                "threshold": 0.35,
                "diagnostic_only": True,
            }
            failure_labels.add("provisional_metric_used")
        else:
            _exclude(answer_context_consistency, "missing_generated_answer_or_context", diagnostic_only=True)
            metric_results["answer_extracted_from_retrieved_context_rate"] = None

        if answerability == "answerable" and item.has_expected_answer and item.has_expected_evidence:
            e2e_metric["denominator"] += 1
            evidence_pass = bool(evidence_pass_by_k.get(primary_k))
            with_citation_pass = answer_pass and evidence_pass and bool(citations) and citation_check_pass
            e2e_metric["numerator"] += int(with_citation_pass)
        else:
            reason = "missing_expected_answer_or_evidence" if answerability == "answerable" else f"answerability_{answerability}_not_in_e2e_denominator"
            _exclude(e2e_metric, reason, diagnostic_only=gold_incomplete)
            failure_labels.add("strict_metric_not_applicable")

        inferred_answerable_candidate = (
            answerability == "unknown"
            and not item.has_answerability_label
            and item.has_expected_answer
            and item.has_expected_evidence
        )
        inferred_evidence_pass_by_k: dict[int, bool | None] = {}
        if inferred_answerable_candidate:
            inferred_answer_metric["denominator"] += 1
            inferred_answer_pass = answer_correct(
                generated_answer,
                expected_answer=item.expected_answer,
                aliases=item.expected_answer_aliases,
            )
            inferred_answer_metric["numerator"] += int(inferred_answer_pass)
            for k, metric in inferred_evidence_metrics.items():
                metric["denominator"] += 1
                inferred_evidence_pass = _all_required_evidence_present(item, _contexts_top_k(contexts, k))
                inferred_evidence_pass_by_k[k] = inferred_evidence_pass
                metric["numerator"] += int(inferred_evidence_pass)
            inferred_e2e_metric["denominator"] += 1
            inferred_e2e_pass = bool(inferred_answer_pass and inferred_evidence_pass_by_k.get(primary_k))
            inferred_e2e_metric["numerator"] += int(inferred_e2e_pass)
            metric_results["answerability_inferred_for_metrics_only"] = True
            metric_results["exact_or_alias_answer_correctness_inferred_answerable"] = inferred_answer_pass
            metric_results.update(
                {f"evidence_recall@{k}_inferred_answerable": value for k, value in inferred_evidence_pass_by_k.items()}
            )
            metric_results["e2e_rag_success_inferred_answerable"] = inferred_e2e_pass
            failure_labels.add("inferred_answerable_metric_used")
        else:
            _exclude(inferred_answer_metric, "not_unknown_with_expected_answer_and_evidence", diagnostic_only=True)
            for metric in inferred_evidence_metrics.values():
                _exclude(metric, "not_unknown_with_expected_answer_and_evidence", diagnostic_only=True)
            _exclude(inferred_e2e_metric, "not_unknown_with_expected_answer_and_evidence", diagnostic_only=True)
            metric_results["answerability_inferred_for_metrics_only"] = False

        provisional_signal = bool(generated_answer and contexts and judge_signal_available and item.has_expected_evidence)
        if provisional_signal and answerability != "unanswerable":
            e2e_provisional["denominator"] += 1
            evidence_ok = bool(evidence_pass_by_k.get(primary_k)) or bool(weak_evidence_pass_by_k.get(primary_k))
            citation_ok = (not provisional_require_citations) or bool(citations and citation_check_pass)
            provisional_pass = bool(judge_pass and evidence_ok and support_pass and citation_ok)
            e2e_provisional["numerator"] += int(provisional_pass)
            metric_results["e2e_rag_success_provisional"] = provisional_pass
            failure_labels.add("provisional_metric_used")
        else:
            _exclude(e2e_provisional, "missing_generated_answer_context_judge_signal_or_expected_evidence", diagnostic_only=True)
            metric_results["e2e_rag_success_provisional"] = None

        if provisional_signal and answerability != "unanswerable" and resolved_candidates:
            e2e_resolved_evidence["denominator"] += 1
            resolved_evidence_ok = bool(resolved_recall_pass_by_k.get(primary_k))
            citation_ok = (not provisional_require_citations) or bool(
                citations
                and _count_matching_resolved_candidate_rows(resolved_candidates, citations) == len(resolved_candidates)
            )
            resolved_e2e_pass = bool(judge_pass and resolved_evidence_ok and support_pass and citation_ok)
            e2e_resolved_evidence["numerator"] += int(resolved_e2e_pass)
            metric_results["e2e_rag_success_resolved_evidence_provisional"] = resolved_e2e_pass
            failure_labels.add("provisional_metric_used")
        else:
            _exclude(
                e2e_resolved_evidence,
                "missing_generated_answer_context_judge_signal_or_resolved_expected_evidence",
                diagnostic_only=True,
            )
            metric_results["e2e_rag_success_resolved_evidence_provisional"] = None

        if output.get("diagnostics", {}).get("pipeline_error") or output.get("pipeline_error"):
            failure_labels.add("pipeline_error")
            diagnostics["pipeline_error_count"] += 1

        scored = dict(output)
        scored["answerability"] = item.answerability
        scored["expected_answer"] = item.expected_answer
        scored["expected_answer_aliases"] = list(item.expected_answer_aliases)
        scored["expected_evidence"] = [evidence.to_dict() for evidence in item.expected_evidence]
        scored["source_track"] = _clean(item.source_row.get("track") or item.source_row.get("source_family"))
        scored["evidence_id_diagnostics"] = evidence_id_diagnostics
        scored["expected_evidence_resolution"] = dict(evidence_resolution)
        scored["schema_warnings"] = list(item.validation_warnings)
        scored["metric_results"] = metric_results
        scored["failure_labels"] = sorted(failure_labels)
        scored_rows.append(scored)

    item_count = len(items)
    if item_count:
        diagnostics["retrieval_empty_rate"] = round(diagnostics["retrieval_empty_count"] / item_count, 6)
        diagnostics["generation_empty_rate"] = round(diagnostics["generation_empty_count"] / item_count, 6)
        diagnostics["citation_empty_rate"] = round(diagnostics["citation_empty_count"] / item_count, 6)
        diagnostics["average_context_count"] = round(total_context_count / item_count, 6)
        diagnostics["average_context_chars"] = round(total_context_chars / max(total_context_count, 1), 6)

    # Normalize dynamic answerability counts after the loop.
    answerability_counts = Counter(item.answerability for item in items)
    diagnostics["answerable_count"] = int(answerability_counts.get("answerable", 0))
    diagnostics["unanswerable_count"] = int(answerability_counts.get("unanswerable", 0))
    diagnostics["unknown_answerability_count"] = int(answerability_counts.get("unknown", 0))
    failure_counts = Counter(
        label
        for row in scored_rows
        for label in row["failure_labels"]
        if label not in INFORMATIONAL_LABELS
    )
    informational_counts = Counter(
        label
        for row in scored_rows
        for label in row["failure_labels"]
        if label in INFORMATIONAL_LABELS
    )
    diagnostics["failure_category_counts"] = dict(sorted(failure_counts.items()))
    diagnostics["informational_label_counts"] = dict(sorted(informational_counts.items()))

    strict_metrics = {
        "exact_or_alias_answer_correctness": _finish_metric(answer_metric),
        **{f"evidence_recall@{k}": _finish_metric(metric) for k, metric in evidence_metrics.items()},
        "citation_precision": _finish_metric(citation_precision),
        "citation_recall": _finish_metric(citation_recall),
        "abstention_accuracy": _finish_metric(abstention_metric),
        "e2e_rag_success_strict": _finish_metric(e2e_metric),
    }
    provisional_metrics = {
        "judged_answer_correctness_provisional": _finish_metric(judged_answer),
        **{f"weak_evidence_match_recall@{k}": _finish_metric(metric) for k, metric in weak_evidence_metrics.items()},
        "resolved_evidence_available_rate": _finish_metric(resolved_evidence_available),
        **{
            f"resolved_evidence_recall@{k}_provisional": _finish_metric(metric)
            for k, metric in resolved_evidence_recall_metrics.items()
        },
        "citation_matches_resolved_evidence_precision_provisional": _finish_metric(resolved_citation_precision),
        "citation_matches_resolved_evidence_recall_provisional": _finish_metric(resolved_citation_recall),
        "e2e_rag_success_provisional": _finish_metric(e2e_provisional),
        "e2e_rag_success_resolved_evidence_provisional": _finish_metric(e2e_resolved_evidence),
    }
    inferred_answerable_metrics = {
        "exact_or_alias_answer_correctness_inferred_answerable": _finish_metric(inferred_answer_metric),
        **{f"evidence_recall@{k}_inferred_answerable": _finish_metric(metric) for k, metric in inferred_evidence_metrics.items()},
        "e2e_rag_success_inferred_answerable": _finish_metric(inferred_e2e_metric),
    }
    diagnostic_metric_details = {
        "answer_extracted_from_retrieved_context_rate": _finish_metric(answer_context_consistency),
        "citation_points_to_retrieved_context_rate": _finish_metric(citation_points_to_context),
    }
    diagnostics["not_applicable_counts_by_metric"] = {
        **{name: metric["not_applicable_count"] for name, metric in strict_metrics.items()},
        **{name: metric["not_applicable_count"] for name, metric in provisional_metrics.items()},
        **{name: metric["not_applicable_count"] for name, metric in inferred_answerable_metrics.items()},
        **{name: metric["not_applicable_count"] for name, metric in diagnostic_metric_details.items()},
    }

    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_kind": RUN_KIND,
        "total_item_count": item_count,
        "answerability_distribution": {
            "answerable": diagnostics["answerable_count"],
            "unanswerable": diagnostics["unanswerable_count"],
            "unknown": diagnostics["unknown_answerability_count"],
        },
        "strict_metrics": strict_metrics,
        "provisional_metrics": provisional_metrics,
        "inferred_answerable_metrics": inferred_answerable_metrics,
        "diagnostic_metric_details": diagnostic_metric_details,
        "headline_metrics": strict_metrics,
        "diagnostic_metrics": diagnostics,
        "denominator_policy": denominator_policy_text(primary_k),
        "diagnostic_only_decisions": diagnostic_only_decisions(),
        "judge_config": dict(judge_adapter.config),
        "metric_tiers": {
            "strict": list(strict_metrics),
            "provisional": list(provisional_metrics),
            "inferred_answerable": list(inferred_answerable_metrics),
            "diagnostic": [*diagnostics, *diagnostic_metric_details],
        },
        "legacy_metric_aliases": {
            "answer_supported_by_retrieved_context_provisional": "answer_extracted_from_retrieved_context_rate",
            "citation_overlap_provisional": "citation_points_to_retrieved_context_rate",
        },
        "provisional_metric_policy": {
            "e2e_requires_judge_pass": True,
            "e2e_requires_weak_or_strict_evidence_at_primary_k": True,
            "e2e_requires_answer_context_consistency_when_context_available": True,
            "answer_context_consistency_is_standalone_diagnostic": True,
            "e2e_requires_citation_pass": bool(provisional_require_citations),
            "weak_evidence_requires_non_generic_anchor_for_text_overlap": True,
            "weak_evidence_requires_all_numeric_or_date_anchors_for_text_overlap": True,
        },
    }
    return summary, scored_rows


def denominator_policy_text(primary_k: int) -> str:
    return (
        "This run reports strict, provisional, and diagnostic tiers. Strict denominators include only rows with "
        "sufficient human-owned gold for the specific metric: exact/alias answer correctness requires answerable "
        "rows with expected answers or aliases; evidence recall requires answerable rows with expected evidence; "
        "citation precision/recall require generated citations plus expected evidence; abstention accuracy requires "
        "unanswerable labels; strict E2E success requires answerable rows with both expected answer and expected "
        f"evidence and uses evidence recall@{primary_k}. Provisional denominators are broader and keep rows with "
        "usable partial signal, such as generated answers plus expected evidence, notes, aliases, or retrieved "
        "contexts, but provisional E2E success still requires the provisional answer judge to pass and weak-or-strict "
        f"evidence at top-{primary_k}. Inferred-answerable metrics are reported separately for unknown-answerability "
        "rows that have expected answer and expected evidence; answerability is inferred only for metric computation "
        "and no gold labels are mutated. Diagnostic metrics run across executable rows for pipeline debugging. The "
        "answer/context consistency diagnostic is also used as a conservative guard inside provisional E2E because "
        "that metric requires answer/context support when available, but the standalone consistency rate is not answer "
        "correctness. Citation/retrieved-context consistency is likewise not citation correctness. "
        "Missing gold no longer blocks the run; it is recorded as warning/failure labels and excluded only from strict "
        "metric denominators that require it."
    )


def diagnostic_only_decisions() -> list[dict[str, Any]]:
    return [
        {
            "decision": "Use a deterministic provisional answer judge before final LLM judge policy is settled.",
            "rationale": "Forward progress is prioritized for this phase; strict exact/alias scoring remains separate and the heuristic judge is versioned as heuristic_overlap_v1.",
        },
        {
            "decision": "Incomplete gold rows stay executable and contribute to provisional or diagnostic signals when possible.",
            "rationale": "Missing expected answers, evidence, aliases, or answerability labels should not block actual RAG pipeline measurement.",
        },
        {
            "decision": "Retriever ranking is not tuned by this runner.",
            "rationale": "This lane measures actual RAG behavior and only adapts retrieval outputs into the metric contract.",
        },
        {
            "decision": "Metric-semantics repair demotes tautological consistency checks and tightens weak evidence matching.",
            "rationale": "Forward progress remains the default, but provisional E2E must fail when the answer judge fails, and weak evidence text overlap must include a non-generic anchor.",
        },
    ]


def _pipeline_error_output(item: EvalItem, reason: str) -> dict[str, Any]:
    return {
        "id": item.id,
        "query": item.query,
        "answerability": item.answerability,
        "generated_answer": "",
        "retrieved_contexts": [],
        "citations": [],
        "expected_answer": item.expected_answer,
        "expected_answer_aliases": list(item.expected_answer_aliases),
        "expected_evidence": [evidence.to_dict() for evidence in item.expected_evidence],
        "metric_inputs_available": _metric_inputs_available(item, has_citations=False),
        "diagnostics": {
            "retrieval_empty": True,
            "generation_empty": True,
            "citation_empty": True,
            "gold_incomplete": True,
            "pipeline_error": reason,
        },
        "pipeline_error": reason,
    }


def _metric_inputs_available(item: EvalItem, *, has_citations: bool) -> dict[str, bool]:
    return {
        "has_expected_answer": item.has_expected_answer,
        "has_expected_evidence": item.has_expected_evidence,
        "has_answerability_label": item.has_answerability_label,
        "has_citations": bool(has_citations),
    }


def _diagnostics_for_output(
    item: EvalItem,
    *,
    generated_answer: str,
    contexts: Sequence[Mapping[str, Any]],
    citations: Sequence[Mapping[str, Any]],
) -> dict[str, bool]:
    gold_incomplete = (
        not item.has_answerability_label
        or (item.answerability == "answerable" and (not item.has_expected_answer or not item.has_expected_evidence))
    )
    return {
        "retrieval_empty": not bool(contexts),
        "generation_empty": not bool(_clean(generated_answer)),
        "citation_empty": not bool(citations),
        "gold_incomplete": gold_incomplete,
    }


def load_context_overrides(path: Path | str) -> dict[str, dict[str, Any]]:
    overrides: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(Path(path)):
        row_id = _clean(row.get("id") or row.get("query_id"))
        if not row_id:
            raise DatasetSchemaError(f"{path}: context JSONL row missing id")
        if row_id in overrides:
            raise DatasetSchemaError(f"{path}: duplicate context row id {row_id}")
        overrides[row_id] = row
    return overrides


def _normalize_context(row: Mapping[str, Any], rank: int) -> dict[str, Any]:
    score = row.get("score", 0.0)
    try:
        numeric_score = float(score)
    except (TypeError, ValueError):
        numeric_score = 0.0
    normalized = {
        "rank": int(row.get("rank") or rank),
        "doc_id": _clean(row.get("doc_id") or row.get("docId") or row.get("document_id") or row.get("documentId")),
        "chunk_id": _clean(row.get("chunk_id") or row.get("chunkId") or row.get("search_unit_id") or row.get("searchUnitId")),
        "score": numeric_score,
        "text": _clean(row.get("text") or row.get("snippet") or row.get("textPreview")),
    }
    for source_key, target_key in [
        ("source_family", "source_family"),
        ("source_kind", "source_kind"),
        ("source_title", "source_title"),
        ("source_safe_id", "source_safe_id"),
        ("source_atom_id", "source_atom_id"),
        ("search_unit_id", "search_unit_id"),
        ("search_view_id", "search_view_id"),
        ("provenance_hash", "provenance_hash"),
        ("source_text_sha256", "source_text_sha256"),
    ]:
        value = _clean(row.get(source_key))
        if value:
            normalized[target_key] = value
    for source_key in ("source_path", "local_path", "file_path", "raw_path", "path"):
        value = _clean(row.get(source_key))
        if not value:
            continue
        redacted, was_redacted = _redact_pathish_metadata(value)
        if redacted:
            normalized[f"{source_key}_redacted"] = redacted
        if was_redacted:
            normalized["source_path_redacted"] = True
    return normalized


def _normalize_citation(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": _clean(row.get("doc_id") or row.get("docId") or row.get("document_id") or row.get("documentId")),
        "chunk_id": _clean(row.get("chunk_id") or row.get("chunkId") or row.get("search_unit_id") or row.get("searchUnitId")),
        "text": _clean(row.get("text") or row.get("snippet") or row.get("textPreview")),
    }


def _latency_distribution_ms(values: Sequence[float | int]) -> dict[str, float]:
    numeric = sorted(float(value) for value in values if isinstance(value, (int, float)))
    if not numeric:
        return {"p50": 0.0, "p95": 0.0}
    p50 = numeric[len(numeric) // 2] if len(numeric) % 2 else (numeric[len(numeric) // 2 - 1] + numeric[len(numeric) // 2]) / 2
    p95_index = min(len(numeric) - 1, max(0, math.ceil(len(numeric) * 0.95) - 1))
    return {"p50": round(float(p50), 6), "p95": round(float(numeric[p95_index]), 6)}


def _average(values: Sequence[float | int]) -> float:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return round(sum(numeric) / len(numeric), 6) if numeric else 0.0


def _context_backend_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _clean(row.get("doc_id")),
        _clean(row.get("chunk_id")),
        _sha256_text(_clean(row.get("text"))),
    )


def _context_preview(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rank": row.get("rank"),
        "doc_id": _clean(row.get("doc_id")),
        "chunk_id": _clean(row.get("chunk_id")),
        "score": row.get("score"),
        "retrieval_backend": _clean(row.get("retrieval_backend")),
        "text_sha256": _sha256_text(row.get("text")),
        "text_preview": _clean(row.get("text"))[:180],
    }


def fuse_hybrid_contexts(
    bm25_contexts: Sequence[Mapping[str, Any]],
    vector_contexts: Sequence[Mapping[str, Any]],
    *,
    top_k: int,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    fused: dict[tuple[str, str, str], dict[str, Any]] = {}
    for source, weight in ((bm25_contexts, 1.0), (vector_contexts, 1.0)):
        for position, row in enumerate(source, start=1):
            key = _context_backend_key(row)
            if key not in fused:
                fused[key] = dict(row)
                fused[key]["hybrid_sources"] = []
                fused[key]["fusion_score"] = 0.0
            fused[key]["fusion_score"] = float(fused[key].get("fusion_score") or 0.0) + weight / (rrf_k + position)
            fused[key]["hybrid_sources"].append(_clean(row.get("retrieval_backend")) or "unknown")
    ordered = sorted(
        fused.values(),
        key=lambda row: (
            -float(row.get("fusion_score") or 0.0),
            _clean(row.get("doc_id")),
            _clean(row.get("chunk_id")),
            _clean(row.get("text")),
        ),
    )[: max(0, int(top_k))]
    contexts: list[dict[str, Any]] = []
    for rank, row in enumerate(ordered, start=1):
        context = dict(row)
        context["rank"] = rank
        context["score"] = round(float(context.get("fusion_score") or context.get("score") or 0.0), 6)
        context["retrieval_backend"] = "hybrid"
        context["hybrid_sources"] = sorted(set(context.get("hybrid_sources") or []))
        contexts.append(context)
    return contexts


def _retrieval_backend_comparison(
    *,
    requested_backend: str,
    selected_backend: str,
    bm25_contexts: Sequence[Mapping[str, Any]],
    vector_contexts: Sequence[Mapping[str, Any]],
    hybrid_contexts: Sequence[Mapping[str, Any]],
    selected_contexts: Sequence[Mapping[str, Any]],
    bm25_latency_ms: float,
    vector_latency_ms: float,
    hybrid_latency_ms: float,
    vector_available: bool,
    vector_fallback_reason: str = "",
) -> dict[str, Any]:
    bm25_keys = {_context_backend_key(row) for row in bm25_contexts}
    vector_keys = {_context_backend_key(row) for row in vector_contexts}
    return {
        "requested_backend": requested_backend,
        "selected_backend": selected_backend,
        "bm25_top_k": [_context_preview(row) for row in bm25_contexts],
        "vector_top_k": [_context_preview(row) for row in vector_contexts],
        "hybrid_top_k": [_context_preview(row) for row in hybrid_contexts],
        "selected_top_k": [_context_preview(row) for row in selected_contexts],
        "latency_ms": {
            "bm25": round(float(bm25_latency_ms), 6),
            "vector": round(float(vector_latency_ms), 6),
            "hybrid": round(float(hybrid_latency_ms), 6),
        },
        "candidate_counts": {
            "bm25": len(bm25_contexts),
            "vector": len(vector_contexts),
            "hybrid": len(hybrid_contexts),
            "selected": len(selected_contexts),
        },
        "overlap_counts": {
            "bm25_vector_topk": len(bm25_keys & vector_keys),
        },
        "vector_available": bool(vector_available),
        "vector_fallback_reason": _clean(vector_fallback_reason),
        "candidate_generation_input_policy": "query_text_only_no_gold_qrels_labels_ids_or_baseline_topk",
    }


def _unavailable_retrieval_comparison(
    *,
    requested_backend: str,
    selected_backend: str,
    selected_contexts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return _retrieval_backend_comparison(
        requested_backend=requested_backend,
        selected_backend=selected_backend,
        bm25_contexts=selected_contexts if selected_backend == "bm25" else [],
        vector_contexts=[],
        hybrid_contexts=[],
        selected_contexts=selected_contexts,
        bm25_latency_ms=0.0,
        vector_latency_ms=0.0,
        hybrid_latency_ms=0.0,
        vector_available=False,
        vector_fallback_reason="vector_backend_not_invoked_for_precomputed_contexts",
    )


class JsonlContextAdapter:
    def __init__(self, path: Path | str, *, requested_backend: str = "auto") -> None:
        self.path = Path(path)
        self.requested_backend = _clean(requested_backend) or "auto"
        self.rows = load_context_overrides(self.path)
        self.generator = ExtractiveGenerator()

    @property
    def config(self) -> dict[str, Any]:
        return {
            "adapter": "jsonl_context_override",
            "context_jsonl": self.path.as_posix(),
            "retrieval_source": "deterministic_fixture_or_precomputed_pipeline_output",
            "candidate_generation_input_policy": "precomputed_fixture_rows_keyed_by_item_id_only",
        }

    @property
    def retrieval_backend_report(self) -> dict[str, Any]:
        return {
            "requested": self.requested_backend,
            "selected": "precomputed_context",
            "bm25_enabled": False,
            "vector_enabled": False,
            "hybrid_enabled": False,
            "embedding_model": "",
            "embedding_device": "unavailable",
            "gpu_used_for_embedding": False,
            "vector_index_kind": "unavailable",
            "vector_index_type": "unavailable",
            "vector_dim": 0,
            "indexed_unit_count": 0,
            "query_count": len(self.rows),
            "fallback_reason": "context_jsonl_precomputed_fixture_path",
        }

    def run_item(self, item: EvalItem, *, top_k: int) -> dict[str, Any]:
        row = self.rows.get(item.id)
        if row is None:
            contexts: list[dict[str, Any]] = []
            citations: list[dict[str, Any]] = []
            generated_answer = ""
        else:
            contexts = [
                _normalize_context(context, rank=index)
                for index, context in enumerate(_as_list(row.get("retrieved_contexts")), start=1)
                if isinstance(context, Mapping)
            ][:top_k]
            citations = [
                _normalize_citation(citation)
                for citation in _as_list(row.get("citations"))
                if isinstance(citation, Mapping)
            ]
            generated_answer = _clean(row.get("generated_answer"))
            if not generated_answer and contexts:
                generated_answer = self.generator.generate(item.query, [_context_to_chunk(context) for context in contexts])
        output = _item_output(item, generated_answer=generated_answer, contexts=contexts, citations=citations)
        output["retrieval_backend_comparison"] = _unavailable_retrieval_comparison(
            requested_backend=self.requested_backend,
            selected_backend="precomputed_context",
            selected_contexts=contexts,
        )
        output["diagnostics"]["retrieval_backend_comparison"] = output["retrieval_backend_comparison"]
        return output

    def evidence_candidates(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        return []


def _source_derived_searchview_payloads(root: Path) -> list[dict[str, Any]]:
    """Build candidate-only SearchUnit/SearchView payloads without importing FAISS."""
    from ai.eval import rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check as v62

    source_rows = v62._select_source_rows(root)  # type: ignore[attr-defined]
    payloads: list[dict[str, Any]] = []
    for ordinal, row in enumerate(source_rows, start=1):
        family = _clean(row.get("source_family") or row.get("sourceFamily")).upper()
        text = _clean(row.get("_v62_candidate_text"))
        if not text:
            text = v62._semantic_candidate_text(row)  # type: ignore[attr-defined]
        source_atom_id = _clean(row.get("source_atom_id") or row.get("sourceAtomId")) or f"source_atom_sha_{_sha256_text(text)[:24]}"
        source_safe_id = f"actual_rag_source_{_sha256_text(source_atom_id)[:24]}"
        search_unit_id = f"actual_rag_su_{family.lower()}_{ordinal:03d}_{_sha256_text(source_atom_id + text)[:12]}"
        search_view_id = f"actual_rag_sv_{family.lower()}_{ordinal:03d}_{_sha256_text(text + source_atom_id)[:12]}"
        provenance_hash = _sha256_text(json.dumps({"source_atom_id": source_atom_id, "text": text}, ensure_ascii=False, sort_keys=True))
        metadata = {
            "candidate_only_payload_role": "SearchView",
            "evidence_truth_role": "SourceAtom/EvidenceBundle",
            "materialization_bucket": _clean(row.get("materialization_bucket")) or "source_atom_ready",
            "meaningful_semantic_text": True,
            "provenance_hash": provenance_hash,
            "source_atom_id": source_atom_id,
            "source_family": family,
            "source_safe_id": source_safe_id,
            "source_text_sha256": _sha256_text(text),
            "unit_type": "source_derived_semantic_snippet",
        }
        payload = {
            "payload_id": f"actual_rag_payload_{ordinal:03d}_{_sha256_text(search_view_id)[:12]}",
            "namespace": "actual_rag_eval_nonprod_searchunit_searchview",
            "source_family": family,
            "search_unit_id": search_unit_id,
            "search_view_id": search_view_id,
            "source_atom_ids": [source_atom_id],
            "embedding_text": text,
            "bm25_text": text,
            "metadata": metadata,
            "provenance_hash": provenance_hash,
        }
        forbidden_paths = v62._forbidden_field_paths(payload)  # type: ignore[attr-defined]
        if forbidden_paths:
            raise ValueError(f"actual RAG SearchView payload contains forbidden fields: {forbidden_paths}")
        for field in ("embedding_text", "bm25_text"):
            v62._require_no_forbidden_candidate_text(_clean(payload.get(field)), context=f"actual_rag_eval {field}")  # type: ignore[attr-defined]
        payloads.append(payload)
    return payloads


class RepoCurrentBm25Adapter:
    """Use the repo's current SearchUnit/SearchView materialization with BM25 only.

    This is a compatibility adapter for actual-RAG eval execution. It reuses the
    v6.3 source-derived SearchUnit/SearchView surface and BM25 text fields, but
    does not tune or alter ranking algorithms.
    """

    def __init__(self, root: Path | str = ROOT, *, payloads: Sequence[Mapping[str, Any]] | None = None) -> None:
        self.root = Path(root)
        self.generator = ExtractiveGenerator()
        self._payloads: list[dict[str, Any]] | None = [dict(payload) for payload in payloads] if payloads is not None else None

    @property
    def config(self) -> dict[str, Any]:
        return {
            "adapter": "repo_current_v63_searchunit_bm25",
            "index": "current-searchunit-searchview-surface",
            "ranking_change": False,
            "external_api_calls": False,
        }

    def _load_payloads(self) -> list[dict[str, Any]]:
        if self._payloads is not None:
            return self._payloads
        self._payloads = [dict(payload) for payload in _source_derived_searchview_payloads(self.root)]
        return self._payloads

    def run_item(self, item: EvalItem, *, top_k: int) -> dict[str, Any]:
        payloads = self._load_payloads()
        contexts = self._bm25_contexts(item.query, payloads, top_k=top_k)
        citations = [_normalize_citation(context) for context in contexts]
        generated_answer = self.generator.generate(item.query, [_context_to_chunk(context) for context in contexts])
        return _item_output(item, generated_answer=generated_answer, contexts=contexts, citations=citations)

    def evidence_candidates(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        if not _clean(query):
            return []
        return self._bm25_contexts(query, self._load_payloads(), top_k=top_k)

    @staticmethod
    def _tokenize(value: str) -> list[str]:
        return [token for token in "".join(ch.casefold() if ch.isalnum() else " " for ch in value).split() if len(token) > 1]

    def _bm25_contexts(self, query: str, payloads: Sequence[Mapping[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
        query_terms = self._tokenize(query)
        docs = [self._tokenize(_clean(payload.get("bm25_text") or payload.get("embedding_text"))) for payload in payloads]
        doc_count = max(len(docs), 1)
        doc_freq = Counter(term for doc in docs for term in set(doc))
        avg_len = sum(len(doc) for doc in docs) / doc_count if docs else 1.0
        scored: list[tuple[float, Mapping[str, Any]]] = []
        for payload, doc_terms in zip(payloads, docs, strict=True):
            term_counts = Counter(doc_terms)
            doc_len = max(len(doc_terms), 1)
            score = 0.0
            for term in query_terms:
                if not term_counts[term]:
                    continue
                idf = math.log(1 + (doc_count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                score += idf * (term_counts[term] * 2.2) / (
                    term_counts[term] + 1.2 * (0.25 + 0.75 * doc_len / max(avg_len, 1e-9))
                )
            if score > 0:
                scored.append((score, payload))
        scored.sort(key=lambda item: (-item[0], _clean(item[1].get("search_unit_id"))))
        contexts: list[dict[str, Any]] = []
        for rank, (score, payload) in enumerate(scored[:top_k], start=1):
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
            contexts.append(
                {
                    "rank": rank,
                    "doc_id": _clean(metadata.get("source_safe_id") or payload.get("source_family")),
                    "chunk_id": _clean(payload.get("search_unit_id")),
                    "score": round(float(score), 6),
                    "text": _clean(payload.get("bm25_text") or payload.get("embedding_text")),
                    "retrieval_backend": "bm25",
                    "source_family": _clean(payload.get("source_family")),
                    "search_unit_id": _clean(payload.get("search_unit_id")),
                    "search_view_id": _clean(payload.get("search_view_id")),
                    "source_text_sha256": _clean(metadata.get("source_text_sha256")),
                    "source_atom_id": _clean(payload.get("source_atom_id") or metadata.get("source_atom_id")),
                    "evidence_bundle_id": _clean(payload.get("evidence_bundle_id") or metadata.get("evidence_bundle_id")),
                    "retrieval_surface": _clean(payload.get("retrieval_surface") or metadata.get("retrieval_surface") or "searchunit_searchview"),
                    "title": _clean(payload.get("title") or metadata.get("title")),
                    "section": _clean(payload.get("section") or metadata.get("section")),
                }
            )
        return contexts


class RepoCurrentHybridAdapter(RepoCurrentBm25Adapter):
    """Repo-current SearchUnit/SearchView BM25, vector, and hybrid retrieval.

    Candidate generation uses only the user query text and source-derived
    SearchView payload text. Gold, qrels, expected evidence, row ids, query ids,
    target ids, and baseline top-k are not inputs to this adapter.
    """

    def __init__(
        self,
        root: Path | str = ROOT,
        *,
        requested_backend: str = "auto",
        embedding_provider: Any | None = None,
        gpu_preflight: Mapping[str, Any] | None = None,
        external_vector_db: Mapping[str, Any] | None = None,
        payloads: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        super().__init__(root=root, payloads=payloads)
        self.requested_backend = _clean(requested_backend).lower() or "auto"
        if self.requested_backend not in {"auto", "bm25", "vector", "hybrid"}:
            raise DatasetSchemaError(f"unsupported retrieval backend: {requested_backend}")
        self.embedding_provider = embedding_provider
        self.gpu_preflight = dict(gpu_preflight or {})
        self.external_vector_db = dict(external_vector_db or {})
        self._vector_ready = False
        self._vector_attempted = False
        self._vector_fallback_reason = ""
        self._vector_index = None
        self._vector_id_map: list[dict[str, Any]] = []
        self._embedder: Any | None = None
        self._vector_dim = 0
        self._embedding_model = ""
        self._embedding_device = "unavailable"
        self._gpu_used_for_embedding = False
        self._embedding_build_latency_ms = 0.0
        self._index_load_or_build_latency_ms = 0.0
        self._query_count = 0

    @property
    def config(self) -> dict[str, Any]:
        return {
            "adapter": "repo_current_searchunit_vector_hybrid",
            "index": "current-searchunit-searchview-surface",
            "requested_backend": self.requested_backend,
            "selected_backend": self._selected_backend_name(),
            "ranking_change": True,
            "ranking_change_claimed_as_improvement": False,
            "external_api_calls": False,
            "candidate_generation_input_policy": "query_text_only_no_gold_qrels_labels_ids_or_baseline_topk",
        }

    @property
    def retrieval_backend_report(self) -> dict[str, Any]:
        self._ensure_vector_ready()
        selected = self._selected_backend_name()
        return {
            "requested": self.requested_backend,
            "selected": selected,
            "bm25_enabled": selected in {"bm25", "hybrid"} or self.requested_backend in {"auto", "bm25", "hybrid"},
            "vector_enabled": self._vector_ready and selected in {"vector", "hybrid"},
            "hybrid_enabled": self._vector_ready and selected == "hybrid",
            "embedding_model": self._embedding_model,
            "embedding_device": self._embedding_device,
            "gpu_used_for_embedding": self._gpu_used_for_embedding,
            "vector_index_kind": "faiss" if self._vector_ready else "unavailable",
            "vector_index_type": "IndexFlatIP" if self._vector_ready else "unavailable",
            "vector_dim": self._vector_dim,
            "indexed_unit_count": len(self._vector_id_map),
            "query_count": self._query_count,
            "fallback_reason": None if self._vector_ready else (self._vector_fallback_reason or "vector_backend_unavailable"),
        }

    @property
    def backend_diagnostics(self) -> dict[str, Any]:
        return {
            "embedding_build_latency_ms": self._embedding_build_latency_ms,
            "index_load_or_build_latency_ms": self._index_load_or_build_latency_ms,
            "vector_index_available": self._vector_ready,
            "gpu_used_for_embedding": self._gpu_used_for_embedding,
            "fallback_reason": "" if self._vector_ready else self._vector_fallback_reason,
        }

    def _selected_backend_name(self) -> str:
        if self.requested_backend == "bm25":
            return "bm25"
        if self._ensure_vector_ready():
            if self.requested_backend in {"auto", "hybrid"}:
                return "hybrid"
            if self.requested_backend == "vector":
                return "vector"
        return "bm25"

    def _ensure_vector_ready(self) -> bool:
        if self._vector_attempted:
            return self._vector_ready
        self._vector_attempted = True
        try:
            import numpy as np  # type: ignore
            import faiss  # type: ignore
        except Exception as exc:
            self._vector_fallback_reason = f"faiss_or_numpy_unavailable:{type(exc).__name__}: {exc}"
            return False

        payloads = self._load_payloads()
        texts = [_clean(payload.get("embedding_text") or payload.get("bm25_text")) for payload in payloads]
        try:
            embedder = self.embedding_provider
            if embedder is None:
                from app.capabilities.rag.embeddings import SentenceTransformerEmbedder, resolve_max_seq_length

                embedder = SentenceTransformerEmbedder(
                    model_name="BAAI/bge-m3",
                    max_seq_length=resolve_max_seq_length(
                        int(os.environ.get("ACTUAL_RAG_EVAL_BGE_M3_MAX_SEQ_LENGTH", "1024"))
                    ),
                    batch_size=int(os.environ.get("ACTUAL_RAG_EVAL_BGE_M3_BATCH_SIZE", "32")),
                    show_progress_bar=False,
                )
            embed_started = time.perf_counter()
            vectors = embedder.embed_passages(texts)
            self._embedding_build_latency_ms = round((time.perf_counter() - embed_started) * 1000, 6)
            vectors = np.ascontiguousarray(vectors, dtype=np.float32)
            if vectors.ndim != 2 or vectors.shape[0] != len(payloads) or vectors.shape[1] <= 0:
                raise RuntimeError("embedding_matrix_shape_invalid")
            build_started = time.perf_counter()
            index = faiss.IndexFlatIP(int(vectors.shape[1]))
            index.add(vectors)
            self._index_load_or_build_latency_ms = round((time.perf_counter() - build_started) * 1000, 6)
            self._vector_index = index
            self._vector_id_map = [dict(payload) for payload in payloads]
            self._embedder = embedder
            self._vector_dim = int(vectors.shape[1])
            self._embedding_model = _clean(getattr(embedder, "model_name", "")) or "BAAI/bge-m3"
            model = getattr(embedder, "_model", None)
            model_device = _clean(getattr(model, "device", ""))
            cuda_available = bool(self.gpu_preflight.get("torch_cuda_available"))
            self._embedding_device = model_device or ("cuda:0" if cuda_available else "cpu")
            self._gpu_used_for_embedding = "cuda" in self._embedding_device.lower()
            self._vector_ready = True
            self._vector_fallback_reason = ""
        except Exception as exc:
            self._vector_ready = False
            self._vector_fallback_reason = f"vector_build_failed:{type(exc).__name__}: {exc}"
        return self._vector_ready

    def _vector_contexts(self, query: str, *, top_k: int) -> tuple[list[dict[str, Any]], float]:
        if not _clean(query):
            return [], 0.0
        if not self._ensure_vector_ready() or self._vector_index is None:
            return [], 0.0
        try:
            import numpy as np  # type: ignore
        except Exception:
            return [], 0.0
        started = time.perf_counter()
        try:
            if self._embedder is None:
                raise RuntimeError("vector_embedder_not_loaded")
            query_vectors = self._embedder.embed_queries([query])
            qvec = np.ascontiguousarray(query_vectors, dtype=np.float32)
            scores, ids = self._vector_index.search(qvec, min(int(top_k), len(self._vector_id_map)))
        except Exception as exc:
            self._vector_fallback_reason = f"vector_query_failed:{type(exc).__name__}: {exc}"
            return [], round((time.perf_counter() - started) * 1000, 6)
        contexts: list[dict[str, Any]] = []
        for rank, (row_id, score) in enumerate(zip(ids[0], scores[0]), start=1):
            if int(row_id) < 0:
                continue
            payload = self._vector_id_map[int(row_id)]
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
            contexts.append(
                {
                    "rank": rank,
                    "doc_id": _clean(metadata.get("source_safe_id") or payload.get("source_family")),
                    "chunk_id": _clean(payload.get("search_unit_id")),
                    "score": round(float(score), 6),
                    "text": _clean(payload.get("embedding_text") or payload.get("bm25_text")),
                    "retrieval_backend": "vector",
                    "source_family": _clean(payload.get("source_family")),
                    "search_unit_id": _clean(payload.get("search_unit_id")),
                    "search_view_id": _clean(payload.get("search_view_id")),
                    "source_text_sha256": _clean(metadata.get("source_text_sha256")),
                }
            )
        self._query_count += 1
        return contexts, round((time.perf_counter() - started) * 1000, 6)

    def run_item(self, item: EvalItem, *, top_k: int) -> dict[str, Any]:
        payloads = self._load_payloads()
        bm25_started = time.perf_counter()
        bm25_contexts = self._bm25_contexts(item.query, payloads, top_k=top_k)
        bm25_latency = round((time.perf_counter() - bm25_started) * 1000, 6)
        vector_contexts, vector_latency = self._vector_contexts(item.query, top_k=top_k)
        hybrid_started = time.perf_counter()
        hybrid_contexts = fuse_hybrid_contexts(bm25_contexts, vector_contexts, top_k=top_k)
        hybrid_latency = round((time.perf_counter() - hybrid_started) * 1000, 6) + bm25_latency + vector_latency
        selected_backend = self._selected_backend_name()
        selected_contexts = {
            "bm25": bm25_contexts,
            "vector": vector_contexts,
            "hybrid": hybrid_contexts,
        }.get(selected_backend, bm25_contexts)
        citations = [_normalize_citation(context) for context in selected_contexts]
        generated_answer = self.generator.generate(item.query, [_context_to_chunk(context) for context in selected_contexts])
        output = _item_output(item, generated_answer=generated_answer, contexts=selected_contexts, citations=citations)
        output["retrieval_backend_comparison"] = _retrieval_backend_comparison(
            requested_backend=self.requested_backend,
            selected_backend=selected_backend,
            bm25_contexts=bm25_contexts,
            vector_contexts=vector_contexts,
            hybrid_contexts=hybrid_contexts,
            selected_contexts=selected_contexts,
            bm25_latency_ms=bm25_latency,
            vector_latency_ms=vector_latency,
            hybrid_latency_ms=hybrid_latency,
            vector_available=self._vector_ready,
            vector_fallback_reason=self._vector_fallback_reason,
        )
        output["diagnostics"]["retrieval_backend_comparison"] = output["retrieval_backend_comparison"]
        return output

    def evidence_candidates(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        selected_backend = self._selected_backend_name()
        bm25_contexts = self._bm25_contexts(query, self._load_payloads(), top_k=top_k)
        vector_contexts, _latency = self._vector_contexts(query, top_k=top_k)
        if selected_backend == "vector":
            return vector_contexts
        if selected_backend == "hybrid":
            return fuse_hybrid_contexts(bm25_contexts, vector_contexts, top_k=top_k)
        return bm25_contexts


class FakeVectorAdapter:
    """Deterministic test adapter that exposes BM25, vector, and hybrid rows."""

    def __init__(self, *, requested_backend: str = "auto") -> None:
        self.requested_backend = _clean(requested_backend) or "auto"
        self.generator = ExtractiveGenerator()

    @property
    def config(self) -> dict[str, Any]:
        return {
            "adapter": "deterministic_fake_vector_adapter",
            "requested_backend": self.requested_backend,
            "candidate_generation_input_policy": "query_text_only_no_reference_fields",
            "external_api_calls": False,
        }

    @property
    def retrieval_backend_report(self) -> dict[str, Any]:
        return {
            "requested": self.requested_backend,
            "selected": "hybrid",
            "bm25_enabled": True,
            "vector_enabled": True,
            "hybrid_enabled": True,
            "embedding_model": "deterministic-test-vector",
            "embedding_device": "cpu",
            "gpu_used_for_embedding": False,
            "vector_index_kind": "fake_in_memory",
            "vector_index_type": "deterministic",
            "vector_dim": 4,
            "indexed_unit_count": 2,
            "query_count": 1,
            "fallback_reason": None,
        }

    @property
    def backend_diagnostics(self) -> dict[str, Any]:
        return {
            "embedding_build_latency_ms": 1.0,
            "index_load_or_build_latency_ms": 1.0,
            "vector_index_available": True,
            "gpu_used_for_embedding": False,
            "fallback_reason": "",
        }

    def run_item(self, item: EvalItem, *, top_k: int) -> dict[str, Any]:
        bm25_contexts = [
            {
                "rank": 1,
                "doc_id": "doc-a",
                "chunk_id": "c1",
                "score": 2.0,
                "text": "Seoul is the capital.",
                "retrieval_backend": "bm25",
            }
        ][:top_k]
        vector_contexts = [
            {
                "rank": 1,
                "doc_id": "doc-a",
                "chunk_id": "c1",
                "score": 0.99,
                "text": "Seoul is the capital.",
                "retrieval_backend": "vector",
            },
            {
                "rank": 2,
                "doc_id": "doc-b",
                "chunk_id": "c2",
                "score": 0.5,
                "text": "Busan is a port city.",
                "retrieval_backend": "vector",
            },
        ][:top_k]
        hybrid_contexts = fuse_hybrid_contexts(bm25_contexts, vector_contexts, top_k=top_k)
        generated_answer = self.generator.generate(item.query, [_context_to_chunk(context) for context in hybrid_contexts])
        citations = [_normalize_citation(context) for context in hybrid_contexts]
        output = _item_output(item, generated_answer=generated_answer, contexts=hybrid_contexts, citations=citations)
        output["retrieval_backend_comparison"] = _retrieval_backend_comparison(
            requested_backend=self.requested_backend,
            selected_backend="hybrid",
            bm25_contexts=bm25_contexts,
            vector_contexts=vector_contexts,
            hybrid_contexts=hybrid_contexts,
            selected_contexts=hybrid_contexts,
            bm25_latency_ms=1.0,
            vector_latency_ms=2.0,
            hybrid_latency_ms=3.0,
            vector_available=True,
        )
        output["diagnostics"]["retrieval_backend_comparison"] = output["retrieval_backend_comparison"]
        return output

    def evidence_candidates(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        return self.run_item(EvalItem(id="lookup", query=query), top_k=top_k)["retrieved_contexts"]


def _sanitize_source_native_text(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""

    def redact_match(match: re.Match[str]) -> str:
        raw = match.group(0)
        return f"redacted_path_sha256:{_sha256_text(raw)[:16]}"

    text = re.sub(r"[A-Za-z]:[\\/][^\s|)]+", redact_match, text)
    text = re.sub(r"local-storage[\\/][^\s|)]+", redact_match, text)
    return text


def _diagnostic_hash_vectors(texts: Sequence[str], *, dimension: int = 128) -> Any:
    import numpy as np  # type: ignore

    rows: list[Any] = []
    for text in texts:
        vector = np.zeros((dimension,), dtype=np.float32)
        normalized = " ".join(_clean(text).casefold().split())
        tokens = normalized.split() or [normalized or "empty"]
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:4], "little") % dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = float(np.linalg.norm(vector))
        if norm > 0:
            vector /= norm
        rows.append(vector)
    return np.vstack(rows).astype(np.float32) if rows else np.zeros((0, dimension), dtype=np.float32)


class FakeDeterministicEmbeddingProvider:
    """Small deterministic embedder for source-native vector tests."""

    model_name = "deterministic-test-source-native-vector"

    def embed_passages(self, texts: Sequence[str]) -> Any:
        return _diagnostic_hash_vectors(list(texts), dimension=16)

    def embed_queries(self, texts: Sequence[str]) -> Any:
        return self.embed_passages(texts)


class SourceNativeCorpusLoader:
    """Read-only loader for source-owned SourceAtom/EvidenceBundle retrieval units."""

    def __init__(
        self,
        *,
        search_view_manifest_path: Path | str = SOURCE_NATIVE_SEARCH_VIEW_MANIFEST_PATH,
        source_atom_registry_path: Path | str = SOURCE_NATIVE_SOURCE_REGISTRY_PATH,
    ) -> None:
        self.search_view_manifest_path = Path(search_view_manifest_path)
        self.source_atom_registry_path = Path(source_atom_registry_path)

    @property
    def available(self) -> bool:
        return self.search_view_manifest_path.exists()

    def describe(self) -> dict[str, Any]:
        return {
            "preferred_surface_order": [
                "evidence_bundle",
                "source_atom",
                "source_registry_materialized_text",
                "raw_source_derived_chunks",
                "searchunit_searchview_fallback",
            ],
            "selected_source": "source_atom" if self.available else "unavailable",
            "search_view_manifest_path_hash": f"sha256:{_sha256_text(self.search_view_manifest_path.as_posix())}",
            "source_atom_registry_path_hash": f"sha256:{_sha256_text(self.source_atom_registry_path.as_posix())}",
            "source_atom_registry_available": self.source_atom_registry_path.exists(),
            "read_only": True,
            "raw_local_paths_exposed": False,
        }

    def iter_units(self) -> Iterable[dict[str, Any]]:
        if not self.search_view_manifest_path.exists():
            return
        with self.search_view_manifest_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if isinstance(row, Mapping):
                    unit = self._unit_from_row(row)
                    if unit.get("text"):
                        yield unit

    def load_units(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        units: list[dict[str, Any]] = []
        for unit in self.iter_units():
            units.append(unit)
            if limit is not None and len(units) >= limit:
                break
        return units

    def _unit_from_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        source_atom_id = _clean(row.get("source_atom_id") or row.get("sourceAtomId"))
        evidence_bundle_id = _clean(row.get("evidence_bundle_id") or row.get("evidenceBundleId"))
        search_view_id = _clean(row.get("search_view_id") or row.get("searchViewId"))
        source_identity = _clean(row.get("source_identity") or row.get("sourceIdentity"))
        text = _sanitize_source_native_text(
            row.get("bm25_text") or row.get("display_text") or row.get("embedding_text")
        )
        family = _clean(row.get("source_family") or row.get("sourceFamily") or "unknown").upper() or "unknown"
        if family not in {"TEXT", "PDF", "XLSX"}:
            family = "unknown"
        title = _clean(row.get("workbook_id") or row.get("document_version_id") or row.get("document_id") or family)
        unit_id = source_atom_id or evidence_bundle_id or search_view_id or f"source_native_{_sha256_text(text)[:24]}"
        surface = "evidence_bundle" if evidence_bundle_id else "source_atom"
        metadata = {
            "source_identity_hash": f"sha256:{_sha256_text(source_identity)}" if source_identity else "",
            "source_registry_version": _clean(row.get("source_registry_version") or row.get("sourceRegistryVersion")),
            "materialization_bucket": _clean(row.get("materialization_bucket")),
            "canonical_payload_source": _clean(row.get("canonical_payload_source") or row.get("canonicalPayloadSource")),
            "faiss_row_id": int(row.get("faiss_row_id")) if str(row.get("faiss_row_id", "")).isdigit() else None,
            "raw_local_paths_exposed": False,
        }
        return {
            "unit_id": unit_id,
            "source_atom_id": source_atom_id,
            "evidence_bundle_id": evidence_bundle_id,
            "doc_id": _clean(row.get("document_version_id") or row.get("document_id") or row.get("workbook_version_id"))
            or f"source_native_doc_{_sha256_text(source_identity or unit_id)[:16]}",
            "chunk_id": source_atom_id or evidence_bundle_id or search_view_id or unit_id,
            "source_family": family,
            "title": title,
            "section": _clean(row.get("section") or row.get("search_view_kind") or row.get("searchViewKind")),
            "text": text,
            "metadata": metadata,
            "surface": surface,
            "text_sha256": _sha256_text(text),
            "faiss_row_id": metadata["faiss_row_id"],
        }


def _unit_to_payload(unit: Mapping[str, Any]) -> dict[str, Any]:
    metadata = dict(unit.get("metadata") if isinstance(unit.get("metadata"), Mapping) else {})
    metadata.update(
        {
            "source_safe_id": _clean(unit.get("doc_id")),
            "source_text_sha256": _clean(unit.get("text_sha256")),
            "source_atom_id": _clean(unit.get("source_atom_id")),
            "evidence_bundle_id": _clean(unit.get("evidence_bundle_id")),
            "retrieval_surface": _clean(unit.get("surface")) or "source_native",
            "title": _clean(unit.get("title")),
            "section": _clean(unit.get("section")),
        }
    )
    return {
        "payload_id": _clean(unit.get("unit_id")),
        "search_unit_id": _clean(unit.get("chunk_id") or unit.get("unit_id")),
        "search_view_id": _clean(unit.get("unit_id")),
        "source_family": _clean(unit.get("source_family")),
        "embedding_text": _clean(unit.get("text")),
        "bm25_text": _clean(unit.get("text")),
        "metadata": metadata,
        "source_atom_id": _clean(unit.get("source_atom_id")),
        "evidence_bundle_id": _clean(unit.get("evidence_bundle_id")),
        "retrieval_surface": _clean(unit.get("surface")) or "source_native",
        "title": _clean(unit.get("title")),
        "section": _clean(unit.get("section")),
    }


class SourceNativeHybridAdapter(RepoCurrentHybridAdapter):
    """SourceAtom/EvidenceBundle-backed BM25, vector, and hybrid retrieval."""

    def __init__(
        self,
        root: Path | str = ROOT,
        *,
        requested_backend: str = "auto",
        loader: SourceNativeCorpusLoader | None = None,
        units: Sequence[Mapping[str, Any]] | None = None,
        embedding_provider: Any | None = None,
        gpu_preflight: Mapping[str, Any] | None = None,
        external_vector_db: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            root=root,
            requested_backend=requested_backend,
            embedding_provider=embedding_provider,
            gpu_preflight=gpu_preflight,
            external_vector_db=external_vector_db,
        )
        self.loader = loader or SourceNativeCorpusLoader()
        self._provided_units = [dict(unit) for unit in units] if units is not None else None
        self._bm25_cache: tuple[list[list[str]], Counter[str], float] | None = None
        self._existing_vector_index = None
        self._existing_vector_mode = False

    @property
    def config(self) -> dict[str, Any]:
        return {
            "adapter": "source_native_sourceatom_hybrid",
            "surface": "source_native",
            "source_native_loader": self.loader.describe(),
            "requested_backend": self.requested_backend,
            "selected_backend": self._selected_backend_name(),
            "candidate_generation_input_policy": "query_text_only_over_source_owned_corpus",
            "searchunit_searchview_role": "legacy_baseline_only",
            "external_api_calls": False,
        }

    def _load_payloads(self) -> list[dict[str, Any]]:
        if self._payloads is not None:
            return self._payloads
        units = self._provided_units if self._provided_units is not None else self.loader.load_units()
        self._payloads = [_unit_to_payload(unit) for unit in units]
        return self._payloads

    @property
    def retrieval_backend_report(self) -> dict[str, Any]:
        report = super().retrieval_backend_report
        if self._vector_ready and not self._gpu_used_for_embedding and self._vector_fallback_reason:
            report["fallback_reason"] = self._vector_fallback_reason
        report.update(
            {
                "retrieval_surface": "source_native",
                "source_native_corpus_available": bool(self._load_payloads()),
                "source_native_loader": self.loader.describe(),
                "gpu_fallback_reason": self._vector_fallback_reason if not self._gpu_used_for_embedding else "",
            }
        )
        return report

    @property
    def backend_diagnostics(self) -> dict[str, Any]:
        diagnostics = dict(super().backend_diagnostics)
        if self._vector_ready and not self._gpu_used_for_embedding and self._vector_fallback_reason:
            diagnostics["fallback_reason"] = self._vector_fallback_reason
        return diagnostics

    def _ensure_vector_ready(self) -> bool:
        if self._vector_attempted:
            return self._vector_ready
        self._vector_attempted = True
        payloads = self._load_payloads()
        if not payloads:
            self._vector_fallback_reason = "source_native_corpus_unavailable"
            return False
        try:
            import numpy as np  # type: ignore
            import faiss  # type: ignore
        except Exception as exc:
            self._vector_fallback_reason = f"faiss_or_numpy_unavailable:{type(exc).__name__}: {exc}"
            return False

        index_dir = self.loader.search_view_manifest_path.parent
        build_path = index_dir / "build.json"
        index_path = index_dir / "faiss.index"
        if self._provided_units is None and build_path.exists() and index_path.exists():
            try:
                build = json.loads(build_path.read_text(encoding="utf-8"))
                if _clean(build.get("embedding_model")) == "codex-diagnostic-hashing-vector-v1":
                    started = time.perf_counter()
                    self._existing_vector_index = faiss.read_index(str(index_path))
                    self._index_load_or_build_latency_ms = round((time.perf_counter() - started) * 1000, 6)
                    self._vector_id_map = payloads
                    self._vector_dim = int(build.get("dimension") or 128)
                    self._embedding_model = "codex-diagnostic-hashing-vector-v1"
                    self._embedding_device = "cpu_existing_nonprod_index"
                    self._gpu_used_for_embedding = False
                    self._existing_vector_mode = True
                    self._vector_ready = True
                    self._vector_fallback_reason = "existing_source_native_index_uses_diagnostic_hash_vectors_not_gpu_bge_m3"
                    return True
            except Exception as exc:
                self._vector_fallback_reason = f"existing_source_native_index_load_failed:{type(exc).__name__}: {exc}"

        try:
            embedder = self.embedding_provider
            if embedder is None:
                from app.capabilities.rag.embeddings import SentenceTransformerEmbedder, resolve_max_seq_length

                embedder = SentenceTransformerEmbedder(
                    model_name="BAAI/bge-m3",
                    max_seq_length=resolve_max_seq_length(
                        int(os.environ.get("ACTUAL_RAG_EVAL_BGE_M3_MAX_SEQ_LENGTH", "1024"))
                    ),
                    batch_size=int(os.environ.get("ACTUAL_RAG_EVAL_BGE_M3_BATCH_SIZE", "32")),
                    show_progress_bar=False,
                )
            texts = [_clean(payload.get("embedding_text") or payload.get("bm25_text")) for payload in payloads]
            embed_started = time.perf_counter()
            vectors = embedder.embed_passages(texts)
            self._embedding_build_latency_ms = round((time.perf_counter() - embed_started) * 1000, 6)
            vectors = np.ascontiguousarray(vectors, dtype=np.float32)
            build_started = time.perf_counter()
            index = faiss.IndexFlatIP(int(vectors.shape[1]))
            index.add(vectors)
            self._index_load_or_build_latency_ms = round((time.perf_counter() - build_started) * 1000, 6)
            self._vector_index = index
            self._vector_id_map = payloads
            self._embedder = embedder
            self._vector_dim = int(vectors.shape[1])
            self._embedding_model = _clean(getattr(embedder, "model_name", "")) or "BAAI/bge-m3"
            model = getattr(embedder, "_model", None)
            model_device = _clean(getattr(model, "device", ""))
            cuda_available = bool(self.gpu_preflight.get("torch_cuda_available"))
            self._embedding_device = model_device or ("cuda:0" if cuda_available else "cpu")
            self._gpu_used_for_embedding = "cuda" in self._embedding_device.lower()
            self._vector_ready = True
            self._vector_fallback_reason = "" if self._gpu_used_for_embedding else "gpu_not_used_for_source_native_embedding"
        except Exception as exc:
            self._vector_ready = False
            self._vector_fallback_reason = f"source_native_vector_build_failed:{type(exc).__name__}: {exc}"
        return self._vector_ready

    def _vector_contexts(self, query: str, *, top_k: int) -> tuple[list[dict[str, Any]], float]:
        if not _clean(query) or not self._ensure_vector_ready():
            return [], 0.0
        try:
            import numpy as np  # type: ignore
        except Exception:
            return [], 0.0
        started = time.perf_counter()
        try:
            if self._existing_vector_mode and self._existing_vector_index is not None:
                qvec = _diagnostic_hash_vectors([query], dimension=max(self._vector_dim, 1))
                scores, ids = self._existing_vector_index.search(qvec, min(int(top_k), len(self._vector_id_map)))
            else:
                if self._embedder is None or self._vector_index is None:
                    raise RuntimeError("source_native_vector_index_not_loaded")
                query_vectors = self._embedder.embed_queries([query])
                qvec = np.ascontiguousarray(query_vectors, dtype=np.float32)
                scores, ids = self._vector_index.search(qvec, min(int(top_k), len(self._vector_id_map)))
        except Exception as exc:
            self._vector_fallback_reason = f"source_native_vector_query_failed:{type(exc).__name__}: {exc}"
            return [], round((time.perf_counter() - started) * 1000, 6)
        contexts = [self._context_from_payload(self._vector_id_map[int(row_id)], rank, float(score), "vector") for rank, (row_id, score) in enumerate(zip(ids[0], scores[0]), start=1) if int(row_id) >= 0]
        self._query_count += 1
        return contexts, round((time.perf_counter() - started) * 1000, 6)

    def _bm25_contexts(self, query: str, payloads: Sequence[Mapping[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
        query_terms = self._tokenize(query)
        if not query_terms:
            return []
        docs, doc_freq, avg_len = self._bm25_stats(payloads)
        doc_count = max(len(docs), 1)
        scored: list[tuple[float, int, Mapping[str, Any]]] = []
        for index, (payload, doc_terms) in enumerate(zip(payloads, docs, strict=True)):
            term_counts = Counter(doc_terms)
            doc_len = max(len(doc_terms), 1)
            score = 0.0
            for term in query_terms:
                if not term_counts[term]:
                    continue
                idf = math.log(1 + (doc_count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                score += idf * (term_counts[term] * 2.2) / (
                    term_counts[term] + 1.2 * (0.25 + 0.75 * doc_len / max(avg_len, 1e-9))
                )
            if score > 0:
                scored.append((score, index, payload))
        scored.sort(key=lambda item: (-item[0], _clean(item[2].get("search_unit_id"))))
        return [self._context_from_payload(payload, rank, score, "bm25") for rank, (score, _index, payload) in enumerate(scored[:top_k], start=1)]

    def _bm25_stats(self, payloads: Sequence[Mapping[str, Any]]) -> tuple[list[list[str]], Counter[str], float]:
        if self._bm25_cache is not None:
            return self._bm25_cache
        docs = [self._tokenize(_clean(payload.get("bm25_text") or payload.get("embedding_text"))) for payload in payloads]
        doc_count = max(len(docs), 1)
        doc_freq = Counter(term for doc in docs for term in set(doc))
        avg_len = sum(len(doc) for doc in docs) / doc_count if docs else 1.0
        self._bm25_cache = (docs, doc_freq, avg_len)
        return self._bm25_cache

    def _context_from_payload(self, payload: Mapping[str, Any], rank: int, score: float, backend: str) -> dict[str, Any]:
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
        return {
            "rank": rank,
            "doc_id": _clean(metadata.get("source_safe_id") or payload.get("source_family")),
            "chunk_id": _clean(payload.get("search_unit_id")),
            "score": round(float(score), 6),
            "text": _clean(payload.get("bm25_text") or payload.get("embedding_text")),
            "retrieval_backend": backend,
            "retrieval_surface": "source_native",
            "source_family": _clean(payload.get("source_family")),
            "source_atom_id": _clean(payload.get("source_atom_id") or metadata.get("source_atom_id")),
            "evidence_bundle_id": _clean(payload.get("evidence_bundle_id") or metadata.get("evidence_bundle_id")),
            "title": _clean(payload.get("title") or metadata.get("title")),
            "section": _clean(payload.get("section") or metadata.get("section")),
            "source_text_sha256": _clean(metadata.get("source_text_sha256")),
        }

    def presence_probe(self, item: EvalItem) -> dict[str, Any]:
        evidence_texts = [_clean(evidence.text) for evidence in item.expected_evidence if _clean(evidence.text)]
        anchors = sorted(_candidate_anchors(item.expected_answer, *item.expected_answer_aliases, *evidence_texts))
        exact_present = False
        normalized_present = False
        anchor_present = False
        normalized_evidence = [normalize_answer_text(text) for text in evidence_texts if normalize_answer_text(text)]
        for payload in self._load_payloads():
            text = _clean(payload.get("bm25_text") or payload.get("embedding_text"))
            normalized = normalize_answer_text(text)
            if evidence_texts and any(text_value in text for text_value in evidence_texts):
                exact_present = True
            if normalized_evidence and any(text_value and text_value in normalized for text_value in normalized_evidence):
                normalized_present = True
            if anchors and _anchor_in_text(anchors, text):
                anchor_present = True
            if (not evidence_texts or exact_present or normalized_present) and (not anchors or anchor_present):
                break
        return {
            "expected_evidence_exact_present": exact_present,
            "expected_evidence_normalized_present": normalized_present,
            "expected_anchor_present": anchor_present,
            "anchor_count": len(anchors),
        }


def _contexts_match_expected(item: EvalItem, contexts: Sequence[Mapping[str, Any]]) -> bool:
    evidence_texts = [_clean(evidence.text) for evidence in item.expected_evidence if _clean(evidence.text)]
    normalized_evidence = [normalize_answer_text(text) for text in evidence_texts if normalize_answer_text(text)]
    anchors = sorted(_candidate_anchors(item.expected_answer, *item.expected_answer_aliases, *evidence_texts))
    for context in contexts:
        text = _clean(context.get("text"))
        normalized = normalize_answer_text(text)
        if normalized_evidence and any(value and value in normalized for value in normalized_evidence):
            return True
        if anchors and _anchor_requirements_satisfied(anchors, text):
            return True
    return False


def _surface_output_summary(item: EvalItem, output: Mapping[str, Any], presence: Mapping[str, Any], surface: str) -> dict[str, Any]:
    contexts = [dict(context) for context in _as_list(output.get("retrieved_contexts")) if isinstance(context, Mapping)]
    families = Counter(_clean(context.get("source_family")) or "unknown" for context in contexts)
    return {
        "surface": surface,
        "backend": (output.get("retrieval_backend_comparison") or {}).get("selected_backend")
        if isinstance(output.get("retrieval_backend_comparison"), Mapping)
        else "",
        "candidate_count": len(contexts),
        "retrieval_empty": not contexts,
        "latency_ms": (output.get("retrieval_backend_comparison") or {}).get("latency_ms")
        if isinstance(output.get("retrieval_backend_comparison"), Mapping)
        else {},
        "source_family_distribution": dict(sorted(families.items())),
        "top_k_previews": [
            {
                "rank": context.get("rank"),
                "doc_id": _clean(context.get("doc_id")),
                "chunk_id": _clean(context.get("chunk_id")),
                "source_atom_id": _clean(context.get("source_atom_id")),
                "source_family": _clean(context.get("source_family")),
                "score": context.get("score"),
                "text_preview": _clean(context.get("text"))[:240],
            }
            for context in contexts[:10]
        ],
        "expected_evidence_in_corpus_exact": bool(presence.get("expected_evidence_exact_present")),
        "expected_evidence_in_corpus_normalized": bool(presence.get("expected_evidence_normalized_present")),
        "expected_anchor_in_corpus": bool(presence.get("expected_anchor_present")),
        "expected_evidence_retrieved": _contexts_match_expected(item, contexts),
    }


class SurfaceComparingRagAdapter:
    """Runs source-native retrieval beside the legacy SearchUnit/SearchView baseline."""

    def __init__(
        self,
        *,
        requested_surface: str = "auto",
        requested_backend: str = "auto",
        source_adapter: SourceNativeHybridAdapter,
        searchunit_adapter: RepoCurrentHybridAdapter,
    ) -> None:
        self.requested_surface = _clean(requested_surface).replace("_", "-").lower() or "auto"
        if self.requested_surface not in {"auto", "source-native", "source-atom", "evidence-bundle", "searchunit-searchview"}:
            raise DatasetSchemaError(f"unsupported retrieval surface: {requested_surface}")
        self.requested_backend = requested_backend
        self.source_adapter = source_adapter
        self.searchunit_adapter = searchunit_adapter
        self._last_surface_comparisons: list[dict[str, Any]] = []

    @property
    def selected_surface(self) -> str:
        if self.requested_surface == "searchunit-searchview":
            return "searchunit_searchview"
        if self.source_available:
            return "source_native"
        return "searchunit_searchview"

    @property
    def source_available(self) -> bool:
        try:
            return bool(self.source_adapter._load_payloads())
        except Exception:
            return False

    @property
    def config(self) -> dict[str, Any]:
        return {
            "adapter": "surface_comparing_actual_rag_adapter",
            "requested_surface": self.requested_surface,
            "selected_surface": self.selected_surface,
            "requested_backend": self.requested_backend,
            "source_native": self.source_adapter.config,
            "searchunit_searchview": self.searchunit_adapter.config,
            "candidate_generation_input_policy": "query_text_only; expected fields diagnostics_only_after_retrieval",
        }

    @property
    def retrieval_backend_report(self) -> dict[str, Any]:
        selected = self.source_adapter if self.selected_surface == "source_native" else self.searchunit_adapter
        return dict(selected.retrieval_backend_report)

    @property
    def retrieval_surface_report(self) -> dict[str, Any]:
        fallback = ""
        if self.selected_surface != "source_native":
            fallback = "source_native_unavailable" if not self.source_available else "searchunit_surface_requested"
        return {
            "requested": self.requested_surface.replace("-", "_"),
            "selected": self.selected_surface,
            "source_native_available": self.source_available,
            "source_native_selected": self.selected_surface == "source_native",
            "searchunit_searchview_role": "legacy_baseline",
            "fallback_reason": fallback,
        }

    @property
    def backend_diagnostics(self) -> dict[str, Any]:
        selected = self.source_adapter if self.selected_surface == "source_native" else self.searchunit_adapter
        return dict(selected.backend_diagnostics)

    @property
    def retrieval_surface_decision(self) -> dict[str, Any]:
        source_wins = sum(1 for row in self._last_surface_comparisons if row.get("source_native_beats_searchunit"))
        searchunit_wins = sum(1 for row in self._last_surface_comparisons if row.get("searchunit_beats_source_native"))
        demoted = self.source_available and self.selected_surface == "source_native" and searchunit_wins == 0
        if not self.source_available:
            recommendation = "repair_source_native_corpus_loading_before_ranking_work"
            reason = "source_native_unavailable"
        elif source_wins > searchunit_wins:
            recommendation = "keep_source_native_as_default_and_repair_source_native_retrieval_misses"
            reason = "source_native_has_better_post_retrieval_expected_evidence_diagnostics"
        elif demoted:
            recommendation = "keep_source_native_as_default; searchunit_searchview_has_no_observed_advantage"
            reason = "source_native_available_and_searchunit_has_no_diagnostic_advantage"
        else:
            recommendation = "inspect_surface_diagnostics_before_default_change"
            reason = "surface_advantage_inconclusive"
        return {
            "selected_default_surface": self.selected_surface,
            "searchunit_searchview_demoted": demoted,
            "demotion_reason": reason if demoted else "",
            "source_native_available": self.source_available,
            "source_native_selected": self.selected_surface == "source_native",
            "fallback_reason": "" if self.source_available else "source_native_unavailable",
            "recommendation": recommendation,
        }

    def run_item(self, item: EvalItem, *, top_k: int) -> dict[str, Any]:
        searchunit_output = self.searchunit_adapter.run_item(item, top_k=top_k)
        source_output = self.source_adapter.run_item(item, top_k=top_k) if self.source_available else _pipeline_error_output(item, "source_native_unavailable")
        selected_output = source_output if self.selected_surface == "source_native" else searchunit_output
        output = dict(selected_output)
        output["retrieved_contexts"] = [dict(context) for context in _as_list(selected_output.get("retrieved_contexts"))]
        output["citations"] = [dict(citation) for citation in _as_list(selected_output.get("citations"))]
        output["retrieval_backend_comparison"] = selected_output.get("retrieval_backend_comparison")
        source_presence = self.source_adapter.presence_probe(item) if self.source_available else {}
        searchunit_presence = self._searchunit_presence_probe(item)
        source_summary = _surface_output_summary(item, source_output, source_presence, "source_native")
        searchunit_summary = _surface_output_summary(item, searchunit_output, searchunit_presence, "searchunit_searchview")
        comparison = {
            "searchunit_searchview": searchunit_summary,
            "source_native": source_summary,
            "selected": {
                "surface": self.selected_surface,
                "backend": (selected_output.get("retrieval_backend_comparison") or {}).get("selected_backend")
                if isinstance(selected_output.get("retrieval_backend_comparison"), Mapping)
                else "",
                "candidate_count": len(output["retrieved_contexts"]),
                "fallback_reason": self.retrieval_surface_report.get("fallback_reason"),
            },
            "source_native_beats_searchunit": bool(source_summary["expected_evidence_retrieved"] and not searchunit_summary["expected_evidence_retrieved"]),
            "searchunit_beats_source_native": bool(searchunit_summary["expected_evidence_retrieved"] and not source_summary["expected_evidence_retrieved"]),
            "both_surfaces_fail": not source_summary["expected_evidence_retrieved"] and not searchunit_summary["expected_evidence_retrieved"],
        }
        self._last_surface_comparisons.append(comparison)
        output["retrieval_surface_comparison"] = comparison
        output.setdefault("diagnostics", {})["retrieval_surface_comparison"] = comparison
        return output

    def evidence_candidates(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        if self.selected_surface == "source_native":
            return self.source_adapter.evidence_candidates(query, top_k=top_k)
        return self.searchunit_adapter.evidence_candidates(query, top_k=top_k)

    def _searchunit_presence_probe(self, item: EvalItem) -> dict[str, Any]:
        evidence_texts = [_clean(evidence.text) for evidence in item.expected_evidence if _clean(evidence.text)]
        anchors = sorted(_candidate_anchors(item.expected_answer, *item.expected_answer_aliases, *evidence_texts))
        exact_present = False
        normalized_present = False
        anchor_present = False
        normalized_evidence = [normalize_answer_text(text) for text in evidence_texts if normalize_answer_text(text)]
        for payload in self.searchunit_adapter._load_payloads():
            text = _clean(payload.get("bm25_text") or payload.get("embedding_text"))
            normalized = normalize_answer_text(text)
            if evidence_texts and any(text_value in text for text_value in evidence_texts):
                exact_present = True
            if normalized_evidence and any(text_value and text_value in normalized for text_value in normalized_evidence):
                normalized_present = True
            if anchors and _anchor_in_text(anchors, text):
                anchor_present = True
            if (not evidence_texts or exact_present or normalized_present) and (not anchors or anchor_present):
                break
        return {
            "expected_evidence_exact_present": exact_present,
            "expected_evidence_normalized_present": normalized_present,
            "expected_anchor_present": anchor_present,
            "anchor_count": len(anchors),
        }


def _context_to_chunk(context: Mapping[str, Any]) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=_clean(context.get("chunk_id")) or f"rank-{row_rank(context)}",
        doc_id=_clean(context.get("doc_id")) or "unknown-doc",
        section=_clean(context.get("section")) or _clean(context.get("chunk_id")) or "context",
        text=_clean(context.get("text")),
        score=float(context.get("score") or 0.0),
    )


def _item_output(
    item: EvalItem,
    *,
    generated_answer: str,
    contexts: Sequence[Mapping[str, Any]],
    citations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    context_rows = [dict(context) for context in contexts]
    citation_rows = [dict(citation) for citation in citations]
    return {
        "id": item.id,
        "query": item.query,
        "answerability": item.answerability,
        "generated_answer": generated_answer,
        "retrieved_contexts": context_rows,
        "citations": citation_rows,
        "expected_answer": item.expected_answer,
        "expected_answer_aliases": list(item.expected_answer_aliases),
        "expected_evidence": [evidence.to_dict() for evidence in item.expected_evidence],
        "metric_inputs_available": _metric_inputs_available(item, has_citations=bool(citation_rows)),
        "diagnostics": _diagnostics_for_output(
            item,
            generated_answer=generated_answer,
            contexts=context_rows,
            citations=citation_rows,
        ),
    }


def top_k_values_for(top_k: int) -> tuple[int, ...]:
    values = [value for value in DEFAULT_TOP_K_VALUES if value <= top_k]
    values.append(top_k)
    return tuple(sorted(set(value for value in values if value > 0)))


def build_judge_adapter(
    *,
    judge_mode: str = "heuristic",
    judge_backend: str = "",
    judge_base_url: str = "",
    judge_model: str = "",
    judge_threshold: float = 0.5,
    judge_timeout_seconds: int = 60,
    judge_max_tokens: int = 360,
    skip_judge_endpoint_check: bool = False,
) -> Any:
    mode = _clean(judge_mode).lower() or "heuristic"
    if mode == "heuristic":
        return HeuristicJudgeAdapter(threshold=judge_threshold)
    if mode in {"local-llm", "local_llm", "llm"}:
        return LocalLLMJudgeAdapter(
            backend=judge_backend,
            base_url=judge_base_url,
            model=judge_model,
            threshold=judge_threshold,
            timeout_seconds=judge_timeout_seconds,
            max_tokens=judge_max_tokens,
            check_endpoint=not skip_judge_endpoint_check,
        )
    raise DatasetSchemaError(f"unsupported judge mode: {judge_mode}")


def dataset_slug_for_path(path: Path | str) -> str:
    stem = Path(path).stem.casefold()
    if "text" in stem and "gold" in stem:
        return "text_gold"
    if "fixture" in stem or "smoke" in stem or "tiny" in stem:
        return "fixture"
    slug = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    return (slug[:48].strip("_") or "dataset")


def _run_id_timestamp(generated_at: str | None = None) -> str:
    value = _clean(generated_at)
    if value:
        match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z", value)
        if match:
            year, month, day, hour, minute, second = match.groups()
            return f"{year}{month}{day}_{hour}{minute}{second}"
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _output_dir_has_artifacts(path: Path) -> bool:
    return any((path / filename).exists() for filename in REPORT_ARTIFACT_FILENAMES)


def _output_dir_is_occupied(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def make_actual_rag_run_id(
    dataset_path: Path | str,
    *,
    explicit_run_id: str = "",
    generated_at: str | None = None,
    report_root: Path | str = REPORT_ROOT,
) -> str:
    explicit = _clean(explicit_run_id)
    if explicit:
        if not SAFE_RUN_ID_RE.fullmatch(explicit) or "/" in explicit or "\\" in explicit or ".." in explicit:
            raise DatasetSchemaError(f"run_id must be filesystem-safe: {explicit_run_id!r}")
        return explicit

    root = Path(report_root)
    base = f"actual_rag_eval_{dataset_slug_for_path(dataset_path)}_{_run_id_timestamp(generated_at)}"
    candidate = base
    suffix = 2
    while _output_dir_is_occupied(root / candidate):
        candidate = f"{base}_{suffix:02d}"
        suffix += 1
    return candidate


def validate_actual_rag_guardrails(summary: Mapping[str, Any]) -> None:
    run_id = _clean(summary.get("run_id")) or "<unknown-run>"
    expected_top_level = {
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }
    for key, expected in expected_top_level.items():
        if key not in summary:
            raise DatasetSchemaError(f"{run_id}: missing closed guardrail field {key}")
        if summary.get(key) != expected:
            raise DatasetSchemaError(f"{run_id}: {key} must be {expected!r}, got {summary.get(key)!r}")
    optional_false_top_level = (
        "gold_fields_used_for_candidate_generation",
        "query_id_used_for_candidate_generation",
        "row_id_used_for_candidate_generation",
        "target_id_used_for_candidate_generation",
        "baseline_topk_used_for_candidate_generation",
        "retriever_oracle_shortcut_used",
    )
    for key in optional_false_top_level:
        if key in summary and summary.get(key) is not False:
            raise DatasetSchemaError(f"{run_id}: {key} must be False, got {summary.get(key)!r}")

    guardrails = summary.get("guardrails")
    if not isinstance(guardrails, Mapping):
        raise DatasetSchemaError(f"{run_id}: guardrails must be present")
    expected_guardrails = {
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "answerability_label_mutation": False,
        "expected_answer_mutation": False,
        "expected_evidence_mutation": False,
        "denominator_mutation": False,
        "retriever_ranking_improvement": False,
        "official_metric": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_readiness_claim": False,
    }
    for key, expected in expected_guardrails.items():
        if key not in guardrails:
            raise DatasetSchemaError(f"{run_id}: missing guardrails.{key}")
        if guardrails.get(key) != expected:
            raise DatasetSchemaError(f"{run_id}: guardrails.{key} must be {expected!r}, got {guardrails.get(key)!r}")
    for key in optional_false_top_level:
        if key in guardrails and guardrails.get(key) is not False:
            raise DatasetSchemaError(f"{run_id}: guardrails.{key} must be False, got {guardrails.get(key)!r}")


def _compact_metric(metric: Any) -> dict[str, Any]:
    if not isinstance(metric, Mapping):
        return {"available": False}
    return {
        "tier": metric.get("tier"),
        "numerator": metric.get("numerator"),
        "denominator": metric.get("denominator"),
        "score": metric.get("score"),
        "skipped_count": metric.get("skipped_count"),
        "not_applicable_count": metric.get("not_applicable_count"),
        "diagnostic_only_count": metric.get("diagnostic_only_count"),
    }


def _metrics_subset(metrics: Mapping[str, Any], names: Sequence[str] | None = None) -> dict[str, Any]:
    selected = names or list(metrics)
    return {name: _compact_metric(metrics.get(name)) for name in selected if name in metrics}


def _lookup_metric(summary: Mapping[str, Any], name: str) -> dict[str, Any]:
    for section_name in ("strict_metrics", "provisional_metrics", "inferred_answerable_metrics", "diagnostic_metric_details"):
        section = summary.get(section_name)
        if isinstance(section, Mapping) and isinstance(section.get(name), Mapping):
            metric = dict(section[name])  # type: ignore[index]
            return {
                "available": metric.get("score") is not None,
                "kind": "metric",
                "tier": metric.get("tier") or section_name.replace("_metrics", ""),
                "numerator": metric.get("numerator"),
                "denominator": metric.get("denominator"),
                "score": metric.get("score"),
            }
    diagnostics = summary.get("diagnostic_metrics")
    if isinstance(diagnostics, Mapping) and name in diagnostics:
        value = diagnostics.get(name)
        return {
            "available": isinstance(value, (int, float)),
            "kind": "value",
            "tier": "diagnostic",
            "value": value,
        }
    return {"available": False, "kind": "missing", "tier": _comparison_tier_for_name(name)}


def _comparison_tier_for_name(name: str) -> str:
    if (
        name in {"judged_answer_correctness_provisional", "e2e_rag_success_provisional"}
        or name in RESOLVED_EVIDENCE_COMPARISON_METRICS
        or name.startswith("resolved_evidence_recall@")
    ):
        return "provisional"
    if name.startswith("weak_evidence_match_recall@"):
        return "provisional"
    if (
        name in DIAGNOSTIC_ONLY_COMPARISON_METRICS
        or name in LOWER_IS_BETTER_COMPARISON_METRICS
        or name in EVIDENCE_MAPPING_PACKET_COMPARISON_METRICS
        or name in BACKEND_COMPARISON_METRICS
        or name in SURFACE_COMPARISON_METRICS
    ):
        return "diagnostic"
    return "strict"


def _comparison_numeric_value(record: Mapping[str, Any]) -> float | None:
    if not record.get("available"):
        return None
    if record.get("kind") == "metric":
        value = record.get("score")
    else:
        value = record.get("value")
    return float(value) if isinstance(value, (int, float)) else None


def _format_comparison_value(record: Mapping[str, Any]) -> str:
    if not record.get("available"):
        if record.get("kind") == "metric" and record.get("denominator") == 0:
            return f"{record.get('numerator', 0)}/0 (unavailable)"
        return "unavailable"
    if record.get("kind") == "metric":
        score = record.get("score")
        rendered_score = "" if score is None else f"{float(score):.6f}"
        return f"{record.get('numerator')}/{record.get('denominator')} ({rendered_score})"
    value = record.get("value")
    return f"{float(value):.6f}" if isinstance(value, float) else str(value)


def _comparison_metric_names(current: Mapping[str, Any], previous: Mapping[str, Any]) -> list[str]:
    primary_k = int(current.get("top_k") or previous.get("top_k") or DEFAULT_TOP_K_VALUES[-1])
    names = [
        "judged_answer_correctness_provisional",
        f"weak_evidence_match_recall@{primary_k}",
        "e2e_rag_success_provisional",
        "exact_or_alias_answer_correctness",
        f"evidence_recall@{primary_k}",
        "citation_precision",
        "citation_recall",
        "retrieval_empty_rate",
        "generation_empty_rate",
        "citation_empty_rate",
        "pipeline_error_count",
        "schema_warning_count",
        "gold_missing_count",
        "expected_evidence_id_missing_count",
        "expected_evidence_id_unresolved_count",
        "expected_evidence_id_resolved_candidate_count",
        "expected_evidence_resolution_candidate_count",
        "evidence_mapping_packet_candidate_count",
        "evidence_mapping_packet_likely_accept_count",
        "evidence_mapping_packet_possible_match_count",
        "evidence_mapping_packet_review_needed_count",
        "evidence_mapping_packet_likely_reject_count",
        "source_metadata_resolved_candidate_count",
        "source_metadata_unresolved_candidate_count",
        "resolved_evidence_available_rate",
        f"resolved_evidence_recall@{primary_k}_provisional",
        "citation_matches_resolved_evidence_precision_provisional",
        "citation_matches_resolved_evidence_recall_provisional",
        "e2e_rag_success_resolved_evidence_provisional",
        *sorted(BACKEND_COMPARISON_METRICS),
        *sorted(SURFACE_COMPARISON_METRICS),
        *sorted(DIAGNOSTIC_ONLY_COMPARISON_METRICS),
    ]
    for summary in (current, previous):
        details = summary.get("diagnostic_metric_details")
        if isinstance(details, Mapping):
            for key in details:
                if key not in names:
                    names.append(str(key))
    return names


def _interpret_comparison(name: str, previous: Mapping[str, Any], current: Mapping[str, Any]) -> str:
    if not previous.get("available") and current.get("available"):
        return "new metric" if _comparison_tier_for_name(name) == "provisional" else "unavailable"
    if not previous.get("available") or not current.get("available"):
        return "unavailable"
    if (
        previous.get("kind") == "metric"
        and current.get("kind") == "metric"
        and previous.get("denominator") != current.get("denominator")
    ):
        return "denominator changed"
    if (
        name in DIAGNOSTIC_ONLY_COMPARISON_METRICS
        or name in EVIDENCE_MAPPING_PACKET_COMPARISON_METRICS
        or name in BACKEND_COMPARISON_METRICS
    ):
        return "diagnostic only"
    if name in RESOLVED_EVIDENCE_COMPARISON_METRICS or name.startswith("resolved_evidence_recall@"):
        return "provisional only"
    previous_value = _comparison_numeric_value(previous)
    current_value = _comparison_numeric_value(current)
    if previous_value is None or current_value is None:
        return "unavailable"
    if current_value == previous_value:
        return "unchanged"
    if name in LOWER_IS_BETTER_COMPARISON_METRICS:
        return "improved" if current_value < previous_value else "regressed"
    return "improved" if current_value > previous_value else "regressed"


def build_run_comparison(
    previous_summary: Mapping[str, Any],
    current_summary: Mapping[str, Any],
    *,
    target_label: str = "",
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for name in _comparison_metric_names(current_summary, previous_summary):
        previous = _lookup_metric(previous_summary, name)
        current = _lookup_metric(current_summary, name)
        previous_value = _comparison_numeric_value(previous)
        current_value = _comparison_numeric_value(current)
        delta = None if previous_value is None or current_value is None else round(current_value - previous_value, 6)
        rows.append(
            {
                "metric": name,
                "tier": current.get("tier") or previous.get("tier") or _comparison_tier_for_name(name),
                "previous": _format_comparison_value(previous),
                "current": _format_comparison_value(current),
                "delta": delta,
                "interpretation": _interpret_comparison(name, previous, current),
            }
        )
    return {
        "schema_version": "actual_rag_eval.run_comparison.v1",
        "target": target_label or _clean(previous_summary.get("run_id")) or "previous",
        "target_run_id": previous_summary.get("run_id"),
        "current_run_id": current_summary.get("run_id"),
        "target_generated_at": previous_summary.get("generated_at"),
        "current_generated_at": current_summary.get("generated_at"),
        "interpretation_policy": "nonprod_diagnostic_comparison_only",
        "guardrails": {
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
        "rows": rows,
    }


def _git_marker() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        ).stdout
        return {
            "commit": commit or "unavailable",
            "working_tree_dirty": bool(status.strip()),
            "working_tree_marker": "dirty" if status.strip() else "clean",
        }
    except Exception as exc:
        return {"commit": "unavailable", "working_tree_marker": f"unavailable:{type(exc).__name__}"}


def _artifact_path(summary: Mapping[str, Any], key: str) -> str:
    artifact_paths = summary.get("artifact_paths")
    if isinstance(artifact_paths, Mapping):
        return _clean(artifact_paths.get(key))
    return ""


def _evidence_resolution_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = summary.get("diagnostic_metrics") if isinstance(summary.get("diagnostic_metrics"), Mapping) else {}
    provisional = summary.get("provisional_metrics") if isinstance(summary.get("provisional_metrics"), Mapping) else {}
    keys = [
        "expected_evidence_resolution_enabled",
        "expected_evidence_resolution_scope",
        "expected_evidence_row_count",
        "expected_evidence_id_present_count",
        "expected_evidence_id_missing_count",
        "expected_evidence_id_resolved_exact_count",
        "expected_evidence_id_resolved_candidate_count",
        "expected_evidence_id_unresolved_count",
        "expected_evidence_resolution_candidate_count",
        "expected_evidence_resolution_high_confidence_count",
        "expected_evidence_resolution_medium_confidence_count",
        "expected_evidence_resolution_low_confidence_count",
        "expected_evidence_resolution_review_only_count",
    ]
    metric_names = [
        "resolved_evidence_available_rate",
        f"resolved_evidence_recall@{int(summary.get('top_k') or DEFAULT_TOP_K_VALUES[-1])}_provisional",
        "citation_matches_resolved_evidence_precision_provisional",
        "citation_matches_resolved_evidence_recall_provisional",
        "e2e_rag_success_resolved_evidence_provisional",
    ]
    return {
        "enabled": bool(diagnostics.get("expected_evidence_resolution_enabled")),
        **{key: diagnostics.get(key) for key in keys if key in diagnostics},
        "artifact_paths": {
            "evidence_resolution_candidates_jsonl": _artifact_path(summary, "evidence_resolution_candidates_jsonl"),
            "evidence_resolution_review_md": _artifact_path(summary, "evidence_resolution_review_md"),
        },
        "provisional_metrics": _metrics_subset(provisional, metric_names),
    }


def _evidence_mapping_packet_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = summary.get("diagnostic_metrics") if isinstance(summary.get("diagnostic_metrics"), Mapping) else {}
    keys = [
        "evidence_mapping_packet_enabled",
        "evidence_mapping_packet_row_count",
        "evidence_mapping_packet_item_count",
        "evidence_mapping_packet_candidate_count",
        "evidence_mapping_packet_likely_accept_count",
        "evidence_mapping_packet_possible_match_count",
        "evidence_mapping_packet_review_needed_count",
        "evidence_mapping_packet_likely_reject_count",
        "evidence_mapping_packet_p0_count",
        "evidence_mapping_packet_p1_count",
        "evidence_mapping_packet_p2_count",
        "evidence_mapping_packet_p3_count",
        "evidence_mapping_packet_p4_count",
        "source_metadata_resolved_candidate_count",
        "source_metadata_unresolved_candidate_count",
        "source_metadata_redacted_path_count",
        "human_decision_fields_filled_by_codex",
    ]
    return {
        "enabled": bool(diagnostics.get("evidence_mapping_packet_enabled")),
        **{key: diagnostics.get(key) for key in keys if key in diagnostics},
        "artifact_paths": {
            "evidence_mapping_review_packet_csv": _artifact_path(summary, "evidence_mapping_review_packet_csv"),
            "evidence_mapping_review_packet_jsonl": _artifact_path(summary, "evidence_mapping_review_packet_jsonl"),
            "evidence_mapping_review_packet_md": _artifact_path(summary, "evidence_mapping_review_packet_md"),
            "evidence_mapping_packet_summary_json": _artifact_path(summary, "evidence_mapping_packet_summary_json"),
        },
        "guardrails": {
            "diagnostic_review_packet_only": True,
            "human_decision_fields_filled_by_codex": False,
            "machine_recommendation_not_gold": True,
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
        },
    }


def build_registry_event(summary: Mapping[str, Any]) -> dict[str, Any]:
    validate_actual_rag_guardrails(summary)
    diagnostics = summary.get("diagnostic_metrics") if isinstance(summary.get("diagnostic_metrics"), Mapping) else {}
    top_k = int(summary.get("top_k") or DEFAULT_TOP_K_VALUES[-1])
    event = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "run_id": summary.get("run_id"),
        "generated_at": summary.get("generated_at"),
        "dataset_path": summary.get("dataset_path"),
        "dataset_slug": dataset_slug_for_path(_clean(summary.get("dataset_path"))),
        "output_dir": summary.get("output_dir"),
        "summary_json": _artifact_path(summary, "summary_json"),
        "markdown_report": _artifact_path(summary, "markdown_report"),
        "items_jsonl": _artifact_path(summary, "items_jsonl"),
        "top_k": summary.get("top_k"),
        "judge_mode": summary.get("judge_mode"),
        "judge_config": summary.get("judge_config"),
        "run_kind": summary.get("run_kind"),
        "total_item_count": summary.get("total_item_count"),
        "strict_metrics_summary": _metrics_subset(
            summary.get("strict_metrics") if isinstance(summary.get("strict_metrics"), Mapping) else {},
            [
                "exact_or_alias_answer_correctness",
                f"evidence_recall@{top_k}",
                "citation_precision",
                "citation_recall",
                "e2e_rag_success_strict",
            ],
        ),
        "provisional_metrics_summary": _metrics_subset(
            summary.get("provisional_metrics") if isinstance(summary.get("provisional_metrics"), Mapping) else {},
            [
                "judged_answer_correctness_provisional",
                f"weak_evidence_match_recall@{top_k}",
                "e2e_rag_success_provisional",
                f"resolved_evidence_recall@{top_k}_provisional",
                "resolved_evidence_available_rate",
                "citation_matches_resolved_evidence_precision_provisional",
                "citation_matches_resolved_evidence_recall_provisional",
                "e2e_rag_success_resolved_evidence_provisional",
            ],
        ),
        "diagnostic_metrics_summary": {
            key: diagnostics.get(key)
            for key in [
                "retrieval_empty_rate",
                "generation_empty_rate",
                "citation_empty_rate",
                "pipeline_error_count",
                "schema_warning_count",
                "gold_missing_count",
                "expected_evidence_id_missing_count",
                "expected_evidence_id_unresolved_count",
                "expected_evidence_id_resolved_candidate_count",
                "expected_evidence_resolution_candidate_count",
                "evidence_mapping_packet_candidate_count",
                "evidence_mapping_packet_likely_accept_count",
                "evidence_mapping_packet_possible_match_count",
                "evidence_mapping_packet_review_needed_count",
                "evidence_mapping_packet_likely_reject_count",
                "source_metadata_resolved_candidate_count",
                "source_metadata_unresolved_candidate_count",
                *sorted(BACKEND_COMPARISON_METRICS),
                *sorted(SURFACE_COMPARISON_METRICS),
            ]
            if key in diagnostics
        },
        "retrieval_backend": summary.get("retrieval_backend"),
        "retrieval_surface": summary.get("retrieval_surface"),
        "retrieval_surface_decision": summary.get("retrieval_surface_decision"),
        "backend_comparison": summary.get("backend_comparison"),
        "surface_comparison": summary.get("surface_comparison"),
        "gpu_preflight": summary.get("gpu_preflight"),
        "external_vector_db": summary.get("external_vector_db"),
        "evidence_resolution": _evidence_resolution_summary(summary),
        "evidence_mapping_packet": _evidence_mapping_packet_summary(summary),
        "guardrails": summary.get("guardrails"),
        "official_metric_input_rows": summary.get("official_metric_input_rows"),
        "official_metric_input_rows_created": summary.get("official_metric_input_rows_created"),
        "official_metric_input_rows_consumed": summary.get("official_metric_input_rows_consumed"),
        "protected_namespaces_touched": summary.get("protected_namespaces_touched"),
        "raw_prompt_payload_written": summary.get("raw_prompt_payload_written"),
        "raw_response_payload_written": summary.get("raw_response_payload_written"),
        "git": _git_marker(),
        "command": summary.get("command"),
        "elapsed_ms": summary.get("elapsed_ms"),
        "pipeline_error_count": diagnostics.get("pipeline_error_count", 0),
        "schema_warning_count": diagnostics.get("schema_warning_count", 0),
        "comparison_target": (summary.get("comparison") or {}).get("target_run_id")
        if isinstance(summary.get("comparison"), Mapping)
        else None,
        "notes": "nonprod actual-RAG eval infrastructure; not official, product-readiness, promotion, or live-readiness evidence",
        "warnings": sorted((diagnostics.get("failure_category_counts") or {}).keys())
        if isinstance(diagnostics.get("failure_category_counts"), Mapping)
        else [],
    }
    return event


def append_run_registry(summary: Mapping[str, Any], *, registry_path: Path | str) -> dict[str, Any]:
    event = build_registry_event(summary)
    path = Path(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def _latest_pointer_payload(summary: Mapping[str, Any]) -> dict[str, Any]:
    validate_actual_rag_guardrails(summary)
    return {
        "schema_version": LATEST_POINTER_SCHEMA_VERSION,
        "run_id": summary.get("run_id"),
        "generated_at": summary.get("generated_at"),
        "dataset_path": summary.get("dataset_path"),
        "dataset_slug": dataset_slug_for_path(_clean(summary.get("dataset_path"))),
        "run_kind": summary.get("run_kind"),
        "output_dir": summary.get("output_dir"),
        "summary_json": _artifact_path(summary, "summary_json"),
        "markdown_report": _artifact_path(summary, "markdown_report"),
        "items_jsonl": _artifact_path(summary, "items_jsonl"),
        "top_k": summary.get("top_k"),
        "judge_mode": summary.get("judge_mode"),
        "total_item_count": summary.get("total_item_count"),
        "guardrails": summary.get("guardrails"),
        "evidence_resolution": _evidence_resolution_summary(summary),
        "evidence_mapping_packet": _evidence_mapping_packet_summary(summary),
        "notes": "latest pointer only; historical run directories are append-only",
    }


def write_latest_pointers(summary: Mapping[str, Any], *, report_root: Path | str = REPORT_ROOT) -> list[Path]:
    root = Path(report_root)
    root.mkdir(parents=True, exist_ok=True)
    payload = _latest_pointer_payload(summary)
    paths = [root / "latest.json", root / f"latest_{payload['dataset_slug']}.json"]
    for path in paths:
        write_json(path, payload)
    return paths


def _short_result_interpretation(summary: Mapping[str, Any]) -> str:
    comparison = summary.get("comparison")
    if not isinstance(comparison, Mapping) or not comparison.get("target_run_id"):
        return "baseline recorded; no comparison target supplied"
    rows = comparison.get("rows") if isinstance(comparison.get("rows"), list) else []
    regressed = [row for row in rows if isinstance(row, Mapping) and row.get("interpretation") == "regressed"]
    improved = [row for row in rows if isinstance(row, Mapping) and row.get("interpretation") == "improved"]
    denominator_changed = [
        row for row in rows if isinstance(row, Mapping) and row.get("interpretation") == "denominator changed"
    ]
    if regressed:
        return f"comparison recorded with {len(regressed)} regression signal(s); inspect diagnostics before acting"
    if denominator_changed:
        return "comparison recorded with denominator changes; do not overclaim improvement"
    if improved:
        return f"comparison recorded with {len(improved)} improvement signal(s); nonprod diagnostic only"
    return "comparison recorded; no comparable metric changes"


def _next_repair_target(summary: Mapping[str, Any]) -> str:
    diagnostics = summary.get("diagnostic_metrics") if isinstance(summary.get("diagnostic_metrics"), Mapping) else {}
    if int(diagnostics.get("pipeline_error_count") or 0) > 0:
        return "debug_pipeline_errors"
    if int(diagnostics.get("evidence_mapping_packet_review_needed_count") or 0) > 0 or int(
        diagnostics.get("evidence_mapping_packet_likely_reject_count") or 0
    ) > 0:
        return "human_review_evidence_mapping_packet"
    if int(diagnostics.get("source_native_target_span_present_but_not_retrieved_count") or 0) > 0:
        return "repair_source_native_retrieval_ranking_query_formulation"
    if int(diagnostics.get("source_native_target_span_absent_count") or 0) > 0:
        return "repair_source_native_corpus_source_coverage"
    if float(diagnostics.get("retrieval_empty_rate") or 0.0) > 0:
        return "repair_retrieval_empty_queries"
    if int(diagnostics.get("expected_evidence_id_unresolved_count") or 0) > 0:
        return "repair_expected_evidence_id_resolution"
    if int(diagnostics.get("gold_missing_count") or 0) > 0:
        return "human_gold_review_for_missing_expected_fields"
    return "monitor_accumulated_actual_rag_eval_runs"


def append_actual_rag_status_event(
    summary: Mapping[str, Any],
    *,
    status_jsonl_path: Path | str = STATUS_JSONL_PATH,
) -> dict[str, Any]:
    validate_actual_rag_guardrails(summary)
    diagnostics = summary.get("diagnostic_metrics") if isinstance(summary.get("diagnostic_metrics"), Mapping) else {}
    top_k = int(summary.get("top_k") or DEFAULT_TOP_K_VALUES[-1])
    event = {
        "schema_version": STATUS_EVENT_SCHEMA_VERSION,
        "event_type": "actual_rag_eval_run",
        "status": "ACTUAL_RAG_EVAL_RUN_RECORDED_NONPROD",
        "run_id": summary.get("run_id"),
        "generated_at": summary.get("generated_at"),
        "dataset_path": summary.get("dataset_path"),
        "dataset_slug": dataset_slug_for_path(_clean(summary.get("dataset_path"))),
        "output_dir": summary.get("output_dir"),
        "total_item_count": summary.get("total_item_count"),
        "strict_metrics": _metrics_subset(
            summary.get("strict_metrics") if isinstance(summary.get("strict_metrics"), Mapping) else {},
            ["exact_or_alias_answer_correctness", f"evidence_recall@{top_k}", "e2e_rag_success_strict"],
        ),
        "provisional_metrics": _metrics_subset(
            summary.get("provisional_metrics") if isinstance(summary.get("provisional_metrics"), Mapping) else {},
            ["judged_answer_correctness_provisional", f"weak_evidence_match_recall@{top_k}", "e2e_rag_success_provisional"],
        ),
        "diagnostics": {
            key: diagnostics.get(key)
            for key in [
                "retrieval_empty_rate",
                "generation_empty_rate",
                "citation_empty_rate",
                "pipeline_error_count",
                "schema_warning_count",
                "gold_missing_count",
                "expected_evidence_id_missing_count",
                "expected_evidence_id_unresolved_count",
                "expected_evidence_id_resolved_candidate_count",
                "expected_evidence_resolution_candidate_count",
                "evidence_mapping_packet_candidate_count",
                "evidence_mapping_packet_likely_accept_count",
                "evidence_mapping_packet_possible_match_count",
                "evidence_mapping_packet_review_needed_count",
                "evidence_mapping_packet_likely_reject_count",
                "source_metadata_resolved_candidate_count",
                "source_metadata_unresolved_candidate_count",
                *sorted(BACKEND_COMPARISON_METRICS),
                *sorted(SURFACE_COMPARISON_METRICS),
            ]
            if key in diagnostics
        },
        "retrieval_backend": summary.get("retrieval_backend"),
        "retrieval_surface": summary.get("retrieval_surface"),
        "retrieval_surface_decision": summary.get("retrieval_surface_decision"),
        "backend_comparison": summary.get("backend_comparison"),
        "surface_comparison": summary.get("surface_comparison"),
        "gpu_preflight": summary.get("gpu_preflight"),
        "external_vector_db": summary.get("external_vector_db"),
        "evidence_id_missing_count": diagnostics.get("expected_evidence_id_missing_count"),
        "evidence_id_unresolved_count": diagnostics.get("expected_evidence_id_unresolved_count"),
        "evidence_id_resolved_candidate_count": diagnostics.get("expected_evidence_id_resolved_candidate_count"),
        "evidence_resolution_candidate_count": diagnostics.get("expected_evidence_resolution_candidate_count"),
        "evidence_resolution": _evidence_resolution_summary(summary),
        "evidence_mapping_packet": _evidence_mapping_packet_summary(summary),
        "guardrails": summary.get("guardrails"),
        "official_metric_input_rows": summary.get("official_metric_input_rows"),
        "official_metric_input_rows_created": summary.get("official_metric_input_rows_created"),
        "official_metric_input_rows_consumed": summary.get("official_metric_input_rows_consumed"),
        "protected_namespaces_touched": summary.get("protected_namespaces_touched"),
        "raw_prompt_payload_written": summary.get("raw_prompt_payload_written"),
        "raw_response_payload_written": summary.get("raw_response_payload_written"),
        "comparison_target": (summary.get("comparison") or {}).get("target_run_id")
        if isinstance(summary.get("comparison"), Mapping)
        else None,
        "short_result_interpretation": _short_result_interpretation(summary),
        "next_suggested_repair_target": _next_repair_target(summary),
    }
    path = Path(status_jsonl_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def _read_json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DatasetSchemaError(f"{path}: expected JSON object")
    return payload


def _load_summary_from_pointer_or_path(path: Path) -> dict[str, Any]:
    if path.is_dir():
        report_json = path / "report.json"
        legacy_summary = path / "rag_eval_summary.json"
        target = report_json if report_json.exists() else legacy_summary
    else:
        target = path
    payload = _read_json_file(target)
    if "summary_json" in payload and "run_id" in payload and "strict_metrics" not in payload:
        target = Path(_clean(payload["summary_json"]))
        payload = _read_json_file(target)
    validate_actual_rag_guardrails(payload)
    return payload


def _registry_rows(registry_path: Path) -> list[dict[str, Any]]:
    if not registry_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in registry_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def resolve_comparison_summary(
    compare_to: str,
    *,
    dataset_path: Path | str,
    report_root: Path | str = REPORT_ROOT,
    registry_path: Path | str | None = None,
) -> tuple[dict[str, Any] | None, str]:
    target = _clean(compare_to)
    if not target:
        return None, ""
    root = Path(report_root)
    registry = Path(registry_path) if registry_path is not None else root / REGISTRY_FILENAME
    slug = dataset_slug_for_path(dataset_path)
    if target == "latest":
        pointer = root / f"latest_{slug}.json"
        if not pointer.exists():
            pointer = root / "latest.json"
        if not pointer.exists():
            return None, "latest_unavailable"
        return _load_summary_from_pointer_or_path(pointer), "latest"
    if target == "previous":
        for row in reversed(_registry_rows(registry)):
            if row.get("dataset_slug") != slug:
                continue
            if row.get("run_kind") != RUN_KIND:
                continue
            summary_path = Path(_clean(row.get("summary_json")))
            if summary_path.exists():
                return _load_summary_from_pointer_or_path(summary_path), "previous"
        return None, "previous_unavailable"
    path = Path(target)
    if not path.exists():
        raise DatasetSchemaError(f"comparison target does not exist: {target}")
    return _load_summary_from_pointer_or_path(path), target


def write_report_index(*, report_root: Path | str = REPORT_ROOT) -> Path:
    root = Path(report_root)
    rows = _registry_rows(root / REGISTRY_FILENAME)
    pointer_paths = sorted(root.glob("latest*.json"))
    lines = [
        "# Actual RAG Eval Runs",
        "",
        "This directory accumulates non-production actual-RAG eval artifacts. Reports are diagnostic infrastructure only: they do not mutate gold/qrels, do not promote official metrics, and do not claim product or live readiness.",
        "",
        "## Latest Pointers",
        "",
        "| Pointer | Run id | Dataset | Summary |",
        "|---|---|---|---|",
    ]
    if pointer_paths:
        for path in pointer_paths:
            try:
                payload = _read_json_file(path)
            except Exception:
                continue
            lines.append(
                f"| `{path.name}` | `{payload.get('run_id')}` | `{payload.get('dataset_slug')}` | `{payload.get('summary_json')}` |"
            )
    else:
        lines.append("| none |  |  |  |")
    lines.extend(
        [
            "",
            "## Recent Runs",
            "",
            "| Generated at | Run id | Dataset | Items | Comparison target | Report |",
            "|---|---|---|---:|---|---|",
        ]
    )
    for row in rows[-12:]:
        lines.append(
            f"| `{row.get('generated_at')}` | `{row.get('run_id')}` | `{row.get('dataset_slug')}` | "
            f"{row.get('total_item_count') or ''} | `{row.get('comparison_target') or ''}` | `{row.get('markdown_report')}` |"
        )
    if not rows:
        lines.append("| none |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Compare Runs",
            "",
            "- Use `python -m ai.scripts.rag_actual_eval ... --append-registry --write-latest --compare-to previous` to compare the new run against the previous registered run for the same dataset slug.",
            "- Use `--compare-to latest` to compare against the current latest pointer before it is updated.",
            "- Denominator changes are called out separately; do not read score movement across changed denominators as quality improvement.",
        ]
    )
    path = root / "README.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _evidence_resolution_config(
    *,
    enabled: bool = True,
    scope: str = "retrieved-only",
    max_candidates: int = 5,
    min_score: float = 0.35,
    count_medium: bool = False,
) -> EvidenceResolutionConfig:
    normalized_scope = _clean(scope) or "retrieved-only"
    if normalized_scope not in {"retrieved-only", "index-candidate-lookup", "both"}:
        raise DatasetSchemaError(f"unsupported evidence resolution scope: {scope}")
    return EvidenceResolutionConfig(
        enabled=bool(enabled),
        scope=normalized_scope,
        max_candidates=max(1, int(max_candidates)),
        min_score=float(min_score),
        count_medium=bool(count_medium),
    )


def _resolution_index_candidates(
    adapter: Any,
    item: EvalItem,
    evidence: ExpectedEvidence,
    *,
    config: EvidenceResolutionConfig,
) -> tuple[list[dict[str, Any]], list[str]]:
    if config.scope not in {"index-candidate-lookup", "both"}:
        return [], []
    if not hasattr(adapter, "evidence_candidates"):
        return [], ["index_candidate_lookup_unavailable"]
    query = item.query
    try:
        candidates = adapter.evidence_candidates(query, top_k=config.max_candidates)
    except Exception as exc:
        return [], [f"index_candidate_lookup_error:{type(exc).__name__}"]
    return [dict(candidate) for candidate in candidates if isinstance(candidate, Mapping)], []


def apply_expected_evidence_resolution(
    *,
    items: Sequence[EvalItem],
    raw_outputs: Sequence[Mapping[str, Any]],
    adapter: Any,
    config: EvidenceResolutionConfig,
) -> list[dict[str, Any]]:
    if not config.enabled:
        return [dict(output) for output in raw_outputs]
    outputs_by_id = {_clean(output.get("id")): dict(output) for output in raw_outputs}
    resolver = ExpectedEvidenceResolver(config)
    resolved_outputs: list[dict[str, Any]] = []
    for item in items:
        output = dict(outputs_by_id.get(item.id) or _pipeline_error_output(item, "missing_pipeline_output"))
        contexts = [dict(row) for row in _as_list(output.get("retrieved_contexts")) if isinstance(row, Mapping)]
        all_index_candidates: list[dict[str, Any]] = []
        limitations: list[str] = []
        for evidence in item.expected_evidence:
            candidates, candidate_limitations = _resolution_index_candidates(adapter, item, evidence, config=config)
            all_index_candidates.extend(candidates)
            limitations.extend(candidate_limitations)
        output["expected_evidence_resolution"] = resolver.resolve_item(
            item,
            retrieved_contexts=contexts,
            index_candidates=all_index_candidates,
            limitations=sorted(set(limitations)),
        )
        resolved_outputs.append(output)
    return resolved_outputs


def evidence_resolution_candidate_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        resolution = row.get("expected_evidence_resolution") if isinstance(row.get("expected_evidence_resolution"), Mapping) else {}
        for evidence_row in resolution.get("rows") or []:
            if not isinstance(evidence_row, Mapping):
                continue
            candidates.append(
                {
                    "id": row.get("id"),
                    "query": row.get("query"),
                    "expected_answer": row.get("expected_answer"),
                    "expected_evidence": {
                        "index": evidence_row.get("expected_evidence_index"),
                        "doc_id": evidence_row.get("input_doc_id"),
                        "chunk_id": evidence_row.get("input_chunk_id"),
                        "text": evidence_row.get("input_text"),
                    },
                    "candidates": evidence_row.get("candidates") or [],
                    "selected_candidate": evidence_row.get("selected_candidate"),
                    "id_status": evidence_row.get("id_status"),
                    "resolved": evidence_row.get("resolved"),
                    "confidence": (evidence_row.get("selected_candidate") or {}).get("confidence")
                    if isinstance(evidence_row.get("selected_candidate"), Mapping)
                    else None,
                    "resolution_warnings": evidence_row.get("resolution_warnings") or [],
                }
            )
    return candidates


def render_evidence_resolution_review(summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    candidate_rows = evidence_resolution_candidate_rows(rows)

    def preview(value: Any, limit: int = 120) -> str:
        text = re.sub(r"\s+", " ", _clean(value))
        return text if len(text) <= limit else text[: max(0, limit - 3)].rstrip() + "..."

    lines = [
        "# Expected Evidence Resolution Review",
        "",
        "These mappings are diagnostic and do not mutate gold/qrels.",
        "",
        f"- Run id: `{summary.get('run_id')}`",
        f"- Enabled: `{(summary.get('diagnostic_metrics') or {}).get('expected_evidence_resolution_enabled')}`",
        f"- Scope: `{(summary.get('diagnostic_metrics') or {}).get('expected_evidence_resolution_scope')}`",
        "",
        "## High And Medium Confidence Candidates",
        "",
        "| Item | Evidence preview | Selected doc_id | Selected chunk_id | Confidence | Score | Match reasons |",
        "|---|---|---|---|---|---:|---|",
    ]
    visible = False
    for candidate in candidate_rows:
        selected = candidate.get("selected_candidate") if isinstance(candidate.get("selected_candidate"), Mapping) else {}
        if selected.get("confidence") not in {"high", "medium"}:
            continue
        visible = True
        lines.append(
            f"| `{candidate.get('id')}` | {preview((candidate.get('expected_evidence') or {}).get('text'))} | "
            f"`{selected.get('doc_id')}` | `{selected.get('chunk_id')}` | `{selected.get('confidence')}` | "
            f"{selected.get('score')} | {', '.join(selected.get('match_reasons') or [])} |"
        )
    if not visible:
        lines.append("| none |  |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Unresolved Evidence Rows",
            "",
            "| Item | Query | Expected answer | Evidence preview | Warnings | Top candidate preview |",
            "|---|---|---|---|---|---|",
        ]
    )
    visible = False
    for candidate in candidate_rows:
        if candidate.get("resolved"):
            continue
        visible = True
        top = (candidate.get("candidates") or [{}])[0] if candidate.get("candidates") else {}
        lines.append(
            f"| `{candidate.get('id')}` | {preview(candidate.get('query'))} | {preview(candidate.get('expected_answer'))} | "
            f"{preview((candidate.get('expected_evidence') or {}).get('text'))} | "
            f"{', '.join(candidate.get('resolution_warnings') or [])} | {preview(top.get('text_preview'))} |"
        )
    if not visible:
        lines.append("| none |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Low Confidence Review-Only Candidates",
            "",
            "| Item | Evidence preview | Candidate doc_id | Candidate chunk_id | Score | Match reasons | Preview |",
            "|---|---|---|---|---:|---|---|",
        ]
    )
    visible = False
    for candidate in candidate_rows:
        for row_candidate in candidate.get("candidates") or []:
            if not isinstance(row_candidate, Mapping) or row_candidate.get("confidence") != "low":
                continue
            visible = True
            lines.append(
                f"| `{candidate.get('id')}` | {preview((candidate.get('expected_evidence') or {}).get('text'))} | "
                f"`{row_candidate.get('doc_id')}` | `{row_candidate.get('chunk_id')}` | {row_candidate.get('score')} | "
                f"{', '.join(row_candidate.get('match_reasons') or [])} | {preview(row_candidate.get('text_preview'))} |"
            )
    if not visible:
        lines.append("| none |  |  |  |  |  |  |")
    return "\n".join(lines) + "\n"


def write_evidence_resolution_artifacts(
    *,
    output_dir: Path,
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> tuple[Path, Path]:
    candidates_path = output_dir / "evidence_resolution_candidates.jsonl"
    review_path = output_dir / "evidence_resolution_review.md"
    write_jsonl(candidates_path, evidence_resolution_candidate_rows(rows))
    review_path.write_text(render_evidence_resolution_review(summary, rows), encoding="utf-8")
    return candidates_path, review_path


HUMAN_EVIDENCE_MAPPING_FIELDS = (
    "human_mapping_decision",
    "human_accepted_doc_id",
    "human_accepted_chunk_id",
    "human_evidence_sufficient",
    "human_answerability_label",
    "human_relevance_label",
    "human_notes",
    "reviewed_by",
    "reviewed_at",
)

EVIDENCE_MAPPING_PACKET_FIELDS = (
    "run_id",
    "item_id",
    "query",
    "expected_answer",
    "expected_answer_aliases",
    "expected_evidence_index",
    "expected_evidence_text",
    "expected_input_doc_id",
    "expected_input_chunk_id",
    "candidate_rank",
    "candidate_doc_id",
    "candidate_chunk_id",
    "candidate_source_family",
    "candidate_source_kind",
    "candidate_source_title_or_safe_display_name",
    "candidate_score",
    "candidate_confidence",
    "candidate_match_reasons",
    "candidate_text_preview",
    "candidate_full_text_hash",
    "candidate_anchor_hits",
    "candidate_missing_numeric_or_date_anchors",
    "candidate_generic_overlap_terms",
    "candidate_non_generic_anchor_overlap_terms",
    "retrieval_rank_if_present",
    "candidate_source",
    "source_atom_id",
    "search_unit_id",
    "search_view_id",
    "registry_source_identity_hash",
    "manifest_path_kind",
    "source_metadata_resolved",
    "metadata_resolution_warnings",
    "machine_recommendation",
    "machine_recommendation_reason",
    "review_priority",
    "primary_blocker",
    "risk_flags",
    "guardrail_flags",
    "human_decision_fields_filled_by_codex",
    *HUMAN_EVIDENCE_MAPPING_FIELDS,
)


def _source_family_from_text(value: Any) -> str:
    text = _clean(value)
    match = re.match(r"^(TEXT|PDF|XLSX)\s+source\s+text\b", text, flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _expected_source_family(row: Mapping[str, Any]) -> str:
    track = _clean(row.get("source_track") or row.get("track")).casefold()
    if "text" in track:
        return "TEXT"
    if "pdf" in track:
        return "PDF"
    if "xlsx" in track or "excel" in track:
        return "XLSX"
    return ""


def _safe_metadata_from_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    metadata = mapping.get("metadata") if isinstance(mapping.get("metadata"), Mapping) else {}

    def first(*keys: str) -> str:
        for key in keys:
            value = _clean(mapping.get(key))
            if value:
                return value
            value = _clean(metadata.get(key))
            if value:
                return value
        return ""

    warnings: list[str] = []
    risk_flags: list[str] = []
    redacted_path_count = 0
    title = first(
        "source_title",
        "candidate_source_title_or_safe_display_name",
        "safe_display_name",
        "display_name",
        "source_safe_id",
    )
    redacted_title, title_redacted = _redact_pathish_metadata(title)
    if title_redacted:
        redacted_path_count += 1
        risk_flags.append("raw_path_redacted")
    source_family = (
        first("source_family", "family", "track").upper()
        or _source_family_from_text(first("text", "bm25_text", "embedding_text", "text_preview"))
    )
    source_kind = first("source_kind", "unit_type", "candidate_only_payload_role", "kind")
    source_atom_id = first("source_atom_id")
    search_unit_id = first("search_unit_id", "chunk_id")
    search_view_id = first("search_view_id", "payload_id")
    identity_hash = first("registry_source_identity_hash", "provenance_hash", "source_text_sha256")
    for key in ("source_path", "local_path", "file_path", "raw_path", "path"):
        raw_value = first(key)
        if not raw_value:
            continue
        redacted, was_redacted = _redact_pathish_metadata(raw_value)
        if was_redacted:
            redacted_path_count += 1
            risk_flags.append("raw_path_redacted")
            warnings.append(f"{key}_redacted:{redacted}")
    for key, value in list(mapping.items()) + list(metadata.items()):
        if key == "source_path_redacted" and value is True:
            redacted_path_count += 1
            risk_flags.append("raw_path_redacted")
            warnings.append("source_path_redacted")
        elif str(key).endswith("_redacted") and _clean(value).startswith("redacted_path_sha256:"):
            redacted_path_count += 1
            risk_flags.append("raw_path_redacted")
            warnings.append(f"{key}:{_clean(value)}")
    resolved = bool(source_family or source_kind or source_atom_id or search_unit_id or search_view_id or identity_hash)
    if not resolved:
        warnings.append("source_metadata_unresolved")
    return {
        "candidate_source_family": source_family,
        "candidate_source_kind": source_kind,
        "candidate_source_title_or_safe_display_name": redacted_title,
        "source_atom_id": source_atom_id,
        "search_unit_id": search_unit_id,
        "search_view_id": search_view_id,
        "registry_source_identity_hash": identity_hash,
        "manifest_path_kind": first("manifest_path_kind") or ("v63_payload_in_memory" if search_unit_id else ""),
        "source_metadata_resolved": resolved,
        "metadata_resolution_warnings": sorted(set(warnings)),
        "source_metadata_redacted_path_count": redacted_path_count,
        "risk_flags": sorted(set(risk_flags)),
    }


def _candidate_lookup_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return _clean(row.get("doc_id")), _clean(row.get("chunk_id"))


def _source_metadata_lookup(
    rows: Sequence[Mapping[str, Any]],
    adapter: Any,
) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        for context in _as_list(row.get("retrieved_contexts")):
            if not isinstance(context, Mapping):
                continue
            key = _candidate_lookup_key(context)
            if any(key):
                lookup[key] = _safe_metadata_from_mapping(context)
    if hasattr(adapter, "_load_payloads"):
        try:
            payloads = adapter._load_payloads()  # type: ignore[attr-defined]
        except Exception:
            payloads = []
        for payload in payloads:
            if not isinstance(payload, Mapping):
                continue
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
            doc_id = _clean(metadata.get("source_safe_id") or payload.get("source_family"))
            chunk_id = _clean(payload.get("search_unit_id"))
            if doc_id or chunk_id:
                lookup[(doc_id, chunk_id)] = _safe_metadata_from_mapping(payload)
    return lookup


def _retrieval_rank_for_candidate(row: Mapping[str, Any], candidate: Mapping[str, Any]) -> int | str:
    candidate_key = (_clean(candidate.get("doc_id")), _clean(candidate.get("chunk_id")))
    for context in _as_list(row.get("retrieved_contexts")):
        if not isinstance(context, Mapping):
            continue
        if _candidate_lookup_key(context) == candidate_key:
            return int(context.get("rank") or 0) or ""
    return ""


def _candidate_family_mismatch(expected_family: str, candidate_family: str) -> bool:
    return bool(expected_family and candidate_family and expected_family != candidate_family)


def _recommend_mapping(
    *,
    confidence: str,
    match_reasons: Sequence[str],
    anchor_hits: Sequence[str],
    missing_numeric: Sequence[str],
    generic_terms: Sequence[str],
    non_generic_terms: Sequence[str],
    expected_family: str,
    candidate_family: str,
) -> tuple[str, str, list[str], str, str]:
    reasons = set(match_reasons)
    risk_flags: list[str] = []
    if _candidate_family_mismatch(expected_family, candidate_family):
        risk_flags.append("source_family_mismatch")
        return (
            "likely_reject",
            f"source family mismatch: expected {expected_family}, candidate {candidate_family}",
            risk_flags,
            "P3",
            "source family mismatch",
        )
    if missing_numeric:
        risk_flags.append("missing_numeric_or_date_anchor")
        if anchor_hits and len([anchor for anchor in anchor_hits if anchor not in generic_terms]) >= 1:
            return (
                "review_needed",
                "rare/entity anchor present but required numeric/date anchor is missing",
                risk_flags,
                "P1",
                "missing numeric/date anchor",
            )
        return (
            "likely_reject",
            "required numeric/date anchor missing",
            risk_flags,
            "P1",
            "missing numeric/date anchor",
        )
    if "no_non_generic_anchor_overlap" in reasons or (not anchor_hits and not non_generic_terms):
        risk_flags.append("generic_overlap_only")
        return ("likely_reject", "generic overlap only", risk_flags, "P2", "generic overlap only")
    if confidence == "high" and (anchor_hits or non_generic_terms):
        return ("likely_accept", "high confidence candidate with required anchors satisfied", risk_flags, "P4", "control/high confidence")
    if confidence == "medium" and (anchor_hits or non_generic_terms):
        return ("possible_match", "medium confidence candidate needs human review", risk_flags, "P4", "medium confidence")
    if confidence == "low" and (anchor_hits or non_generic_terms):
        return ("review_needed", "low confidence candidate has some non-generic overlap", risk_flags, "P1", "low confidence with rare/entity overlap")
    return ("likely_reject", "candidate preview appears unrelated", risk_flags, "P2", "unrelated preview")


def _empty_mapping_packet_summary(enabled: bool) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "evidence_mapping_packet_enabled": bool(enabled),
        "evidence_mapping_packet_row_count": 0,
        "evidence_mapping_packet_item_count": 0,
        "evidence_mapping_packet_candidate_count": 0,
        "evidence_mapping_packet_likely_accept_count": 0,
        "evidence_mapping_packet_possible_match_count": 0,
        "evidence_mapping_packet_review_needed_count": 0,
        "evidence_mapping_packet_likely_reject_count": 0,
        "evidence_mapping_packet_p0_count": 0,
        "evidence_mapping_packet_p1_count": 0,
        "evidence_mapping_packet_p2_count": 0,
        "evidence_mapping_packet_p3_count": 0,
        "evidence_mapping_packet_p4_count": 0,
        "source_metadata_resolved_candidate_count": 0,
        "source_metadata_unresolved_candidate_count": 0,
        "source_metadata_redacted_path_count": 0,
        "human_decision_fields_filled_by_codex": False,
        "guardrails": {
            "diagnostic_review_packet_only": True,
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
        },
    }


def build_evidence_mapping_packet(
    *,
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    adapter: Any,
    enabled: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not enabled:
        return [], _empty_mapping_packet_summary(False)
    metadata_lookup = _source_metadata_lookup(rows, adapter)
    packet_rows: list[dict[str, Any]] = []
    recommendation_counts = Counter()
    priority_counts = Counter()
    item_ids: set[str] = set()
    source_metadata_resolved = 0
    source_metadata_unresolved = 0
    redacted_path_count = 0
    for row in rows:
        item_id = _clean(row.get("id"))
        item_ids.add(item_id)
        resolution = row.get("expected_evidence_resolution") if isinstance(row.get("expected_evidence_resolution"), Mapping) else {}
        expected_family = _expected_source_family(row)
        retrieval_empty = not bool(_as_list(row.get("retrieved_contexts")))
        generated_answer_preview = _clean(row.get("generated_answer"))[:240]
        top_context = ""
        contexts = [context for context in _as_list(row.get("retrieved_contexts")) if isinstance(context, Mapping)]
        if contexts:
            top_context = _clean(contexts[0].get("text"))[:240]
        for evidence_row in _as_list(resolution.get("rows")):
            if not isinstance(evidence_row, Mapping):
                continue
            candidates = [candidate for candidate in _as_list(evidence_row.get("candidates")) if isinstance(candidate, Mapping)]
            if not candidates:
                priority = "P0" if retrieval_empty else "P2"
                recommendation = "likely_reject"
                recommendation_reason = "no candidate available"
                base = {
                    "run_id": summary.get("run_id"),
                    "item_id": item_id,
                    "query": row.get("query"),
                    "expected_answer": row.get("expected_answer"),
                    "expected_answer_aliases": list(row.get("expected_answer_aliases") or []),
                    "expected_evidence_index": evidence_row.get("expected_evidence_index"),
                    "expected_evidence_text": evidence_row.get("input_text"),
                    "expected_input_doc_id": evidence_row.get("input_doc_id"),
                    "expected_input_chunk_id": evidence_row.get("input_chunk_id"),
                    "candidate_rank": "",
                    "candidate_doc_id": "",
                    "candidate_chunk_id": "",
                    "candidate_source_family": "",
                    "candidate_source_kind": "",
                    "candidate_source_title_or_safe_display_name": "",
                    "candidate_score": "",
                    "candidate_confidence": "",
                    "candidate_match_reasons": [],
                    "candidate_text_preview": "",
                    "candidate_full_text_hash": "",
                    "candidate_anchor_hits": [],
                    "candidate_missing_numeric_or_date_anchors": [],
                    "candidate_generic_overlap_terms": [],
                    "candidate_non_generic_anchor_overlap_terms": [],
                    "retrieval_rank_if_present": "",
                    "candidate_source": "",
                    "source_atom_id": "",
                    "search_unit_id": "",
                    "search_view_id": "",
                    "registry_source_identity_hash": "",
                    "manifest_path_kind": "",
                    "source_metadata_resolved": False,
                    "metadata_resolution_warnings": ["no_candidate"],
                    "machine_recommendation": recommendation,
                    "machine_recommendation_reason": recommendation_reason,
                    "review_priority": priority,
                    "primary_blocker": "no candidate",
                    "risk_flags": ["no_candidate"],
                    "guardrail_flags": ["diagnostic_review_packet_only", "human_decision_required"],
                    "human_decision_fields_filled_by_codex": False,
                    "generated_answer_preview": generated_answer_preview,
                    "top_retrieved_context_preview": top_context,
                    "retrieval_empty": retrieval_empty,
                }
                for human_field in HUMAN_EVIDENCE_MAPPING_FIELDS:
                    base[human_field] = ""
                packet_rows.append(base)
                recommendation_counts[recommendation] += 1
                priority_counts[priority] += 1
                source_metadata_unresolved += 1
                continue
            for candidate in candidates:
                candidate_doc_id = _clean(candidate.get("doc_id"))
                candidate_chunk_id = _clean(candidate.get("chunk_id"))
                metadata = metadata_lookup.get((candidate_doc_id, candidate_chunk_id)) or _safe_metadata_from_mapping(candidate)
                candidate_family = _clean(metadata.get("candidate_source_family")) or _source_family_from_text(candidate.get("text_preview"))
                metadata_resolved = bool(metadata.get("source_metadata_resolved"))
                if metadata_resolved:
                    source_metadata_resolved += 1
                else:
                    source_metadata_unresolved += 1
                redacted_path_count += int(metadata.get("source_metadata_redacted_path_count") or 0)
                match_reasons = list(candidate.get("match_reasons") or [])
                anchor_hits = list(candidate.get("anchor_hits") or [])
                missing_numeric = list(candidate.get("missing_numeric_or_date_anchors") or [])
                generic_terms = list(candidate.get("candidate_generic_overlap_terms") or [])
                non_generic_terms = list(candidate.get("candidate_non_generic_anchor_overlap_terms") or anchor_hits)
                recommendation, recommendation_reason, risk_flags, priority, blocker = _recommend_mapping(
                    confidence=_clean(candidate.get("confidence")),
                    match_reasons=match_reasons,
                    anchor_hits=anchor_hits,
                    missing_numeric=missing_numeric,
                    generic_terms=generic_terms,
                    non_generic_terms=non_generic_terms,
                    expected_family=expected_family,
                    candidate_family=candidate_family,
                )
                risk_flags = sorted(set([*risk_flags, *list(metadata.get("risk_flags") or [])]))
                metadata_warnings = list(metadata.get("metadata_resolution_warnings") or [])
                packet = {
                    "run_id": summary.get("run_id"),
                    "item_id": item_id,
                    "query": row.get("query"),
                    "expected_answer": row.get("expected_answer"),
                    "expected_answer_aliases": list(row.get("expected_answer_aliases") or []),
                    "expected_evidence_index": evidence_row.get("expected_evidence_index"),
                    "expected_evidence_text": evidence_row.get("input_text"),
                    "expected_input_doc_id": evidence_row.get("input_doc_id"),
                    "expected_input_chunk_id": evidence_row.get("input_chunk_id"),
                    "candidate_rank": candidate.get("rank"),
                    "candidate_doc_id": candidate_doc_id,
                    "candidate_chunk_id": candidate_chunk_id,
                    "candidate_source_family": candidate_family,
                    "candidate_source_kind": metadata.get("candidate_source_kind") or "",
                    "candidate_source_title_or_safe_display_name": metadata.get("candidate_source_title_or_safe_display_name") or "",
                    "candidate_score": candidate.get("score"),
                    "candidate_confidence": candidate.get("confidence"),
                    "candidate_match_reasons": match_reasons,
                    "candidate_text_preview": candidate.get("text_preview") or "",
                    "candidate_full_text_hash": candidate.get("candidate_full_text_hash") or _sha256_text(candidate.get("text_preview")),
                    "candidate_anchor_hits": anchor_hits,
                    "candidate_missing_numeric_or_date_anchors": missing_numeric,
                    "candidate_generic_overlap_terms": generic_terms,
                    "candidate_non_generic_anchor_overlap_terms": non_generic_terms,
                    "retrieval_rank_if_present": _retrieval_rank_for_candidate(row, candidate),
                    "candidate_source": candidate.get("source") or "",
                    "source_atom_id": metadata.get("source_atom_id") or "",
                    "search_unit_id": metadata.get("search_unit_id") or candidate_chunk_id,
                    "search_view_id": metadata.get("search_view_id") or "",
                    "registry_source_identity_hash": metadata.get("registry_source_identity_hash") or "",
                    "manifest_path_kind": metadata.get("manifest_path_kind") or "",
                    "source_metadata_resolved": metadata_resolved,
                    "metadata_resolution_warnings": metadata_warnings,
                    "machine_recommendation": recommendation,
                    "machine_recommendation_reason": recommendation_reason,
                    "review_priority": priority,
                    "primary_blocker": blocker,
                    "risk_flags": risk_flags,
                    "guardrail_flags": [
                        "diagnostic_review_packet_only",
                        "human_decision_required",
                        "machine_recommendation_not_gold",
                        "no_gold_qrels_label_mutation",
                        "no_retriever_ranking_change",
                    ],
                    "human_decision_fields_filled_by_codex": False,
                    "generated_answer_preview": generated_answer_preview,
                    "top_retrieved_context_preview": top_context,
                    "retrieval_empty": retrieval_empty,
                }
                for human_field in HUMAN_EVIDENCE_MAPPING_FIELDS:
                    packet[human_field] = ""
                packet_rows.append(packet)
                recommendation_counts[recommendation] += 1
                priority_counts[priority] += 1
    packet_summary = _empty_mapping_packet_summary(True)
    packet_summary.update(
        {
            "evidence_mapping_packet_row_count": len(packet_rows),
            "evidence_mapping_packet_item_count": len({row.get("item_id") for row in packet_rows if row.get("item_id")}),
            "evidence_mapping_packet_candidate_count": sum(1 for row in packet_rows if row.get("candidate_doc_id") or row.get("candidate_chunk_id")),
            "evidence_mapping_packet_likely_accept_count": recommendation_counts.get("likely_accept", 0),
            "evidence_mapping_packet_possible_match_count": recommendation_counts.get("possible_match", 0),
            "evidence_mapping_packet_review_needed_count": recommendation_counts.get("review_needed", 0),
            "evidence_mapping_packet_likely_reject_count": recommendation_counts.get("likely_reject", 0),
            "evidence_mapping_packet_p0_count": priority_counts.get("P0", 0),
            "evidence_mapping_packet_p1_count": priority_counts.get("P1", 0),
            "evidence_mapping_packet_p2_count": priority_counts.get("P2", 0),
            "evidence_mapping_packet_p3_count": priority_counts.get("P3", 0),
            "evidence_mapping_packet_p4_count": priority_counts.get("P4", 0),
            "source_metadata_resolved_candidate_count": source_metadata_resolved,
            "source_metadata_unresolved_candidate_count": source_metadata_unresolved,
            "source_metadata_redacted_path_count": redacted_path_count,
            "human_decision_fields_filled_by_codex": any(
                bool(_clean(packet.get(field)))
                for packet in packet_rows
                for field in HUMAN_EVIDENCE_MAPPING_FIELDS
            ),
        }
    )
    packet_summary["human_decision_fields_filled_by_codex"] = False
    return packet_rows, packet_summary


def _apply_mapping_packet_summary(summary: dict[str, Any], packet_summary: Mapping[str, Any]) -> None:
    diagnostics = summary.setdefault("diagnostic_metrics", {})
    for key, value in packet_summary.items():
        if key in {"enabled", "guardrails"}:
            continue
        diagnostics[key] = value
    summary["evidence_mapping_packet_summary"] = dict(packet_summary)


def render_evidence_mapping_packet_markdown(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    packet_summary: Mapping[str, Any],
) -> str:
    def preview(value: Any, limit: int = 140) -> str:
        text = re.sub(r"\s+", " ", _clean(value))
        return text if len(text) <= limit else text[: max(0, limit - 3)].rstrip() + "..."

    lines = [
        "# Evidence Mapping Review Packet",
        "",
        "This packet is diagnostic and human-reviewable. Machine recommendations are not gold, and human-owned fields are intentionally blank.",
        "",
        f"- Run id: `{summary.get('run_id')}`",
        f"- Enabled: `{packet_summary.get('evidence_mapping_packet_enabled')}`",
        f"- Packet rows: `{packet_summary.get('evidence_mapping_packet_row_count')}`",
        f"- Item count: `{packet_summary.get('evidence_mapping_packet_item_count')}`",
        f"- Human decision fields filled by Codex: `{packet_summary.get('human_decision_fields_filled_by_codex')}`",
        "",
        "## Compact Review Table",
        "",
        "| item_id | expected evidence preview | best candidate doc/chunk | confidence | recommendation | primary blocker | review priority |",
        "|---|---|---|---|---|---|---|",
    ]
    best_by_item: dict[str, Mapping[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        item_id = _clean(row.get("item_id"))
        if item_id and item_id not in best_by_item:
            best_by_item[item_id] = row
            order.append(item_id)
    if not order:
        lines.append("| none |  |  |  |  |  |  |")
    for item_id in order:
        row = best_by_item[item_id]
        lines.append(
            f"| `{item_id}` | {preview(row.get('expected_evidence_text'), 90)} | "
            f"`{row.get('candidate_doc_id')}` / `{row.get('candidate_chunk_id')}` | "
            f"`{row.get('candidate_confidence')}` | `{row.get('machine_recommendation')}` | "
            f"{preview(row.get('primary_blocker'), 80)} | `{row.get('review_priority')}` |"
        )
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_clean(row.get("item_id")), []).append(row)
    lines.extend(["", "## Items", ""])
    for item_id in order:
        item_rows = grouped.get(item_id, [])
        first = item_rows[0]
        lines.extend(
            [
                f"### `{item_id}`",
                "",
                f"- Query: {preview(first.get('query'), 220)}",
                f"- Expected answer: {preview(first.get('expected_answer'), 220)}",
                f"- Expected evidence: {preview(first.get('expected_evidence_text'), 260)}",
                f"- Current generated answer preview: {preview(first.get('generated_answer_preview'), 220)}",
                f"- Top retrieved context preview: {preview(first.get('top_retrieved_context_preview'), 260)}",
                f"- Retrieval empty: `{first.get('retrieval_empty')}`",
                "- Human review fields: `human_mapping_decision`, `human_accepted_doc_id`, `human_accepted_chunk_id`, `human_evidence_sufficient`, `human_answerability_label`, `human_relevance_label`, `human_notes`, `reviewed_by`, and `reviewed_at` are blank.",
                "",
                "| candidate | source | confidence | recommendation | failed high/medium reason | preview |",
                "|---|---|---|---|---|---|",
            ]
        )
        for candidate in item_rows:
            failed_reasons = ", ".join(
                [
                    *[str(value) for value in candidate.get("candidate_missing_numeric_or_date_anchors") or []],
                    *[str(value) for value in candidate.get("risk_flags") or []],
                    *[str(value) for value in candidate.get("metadata_resolution_warnings") or []],
                ]
            ) or candidate.get("machine_recommendation_reason")
            lines.append(
                f"| `{candidate.get('candidate_doc_id')}` / `{candidate.get('candidate_chunk_id')}` | "
                f"`{candidate.get('candidate_source')}` | `{candidate.get('candidate_confidence')}` | "
                f"`{candidate.get('machine_recommendation')}` | {preview(failed_reasons, 120)} | "
                f"{preview(candidate.get('candidate_text_preview'), 160)} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Guardrails",
            "",
            "- No gold/qrels/labels were mutated.",
            "- Human-owned fields are blank; machine recommendations are not accepted mappings.",
            "- Source metadata enrichment is diagnostic only and redacts raw local paths.",
            "- Retriever ranking and generated answers are not changed by this packet.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_evidence_mapping_packet_artifacts(
    *,
    output_dir: Path,
    summary: Mapping[str, Any],
    packet_rows: Sequence[Mapping[str, Any]],
    packet_summary: Mapping[str, Any],
) -> tuple[Path, Path, Path, Path]:
    csv_path = output_dir / "evidence_mapping_review_packet.csv"
    jsonl_path = output_dir / "evidence_mapping_review_packet.jsonl"
    md_path = output_dir / "evidence_mapping_review_packet.md"
    summary_path = output_dir / "evidence_mapping_packet_summary.json"
    write_jsonl(jsonl_path, packet_rows)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(EVIDENCE_MAPPING_PACKET_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in packet_rows:
            rendered = {
                key: json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            }
            writer.writerow(rendered)
    md_path.write_text(render_evidence_mapping_packet_markdown(summary, packet_rows, packet_summary), encoding="utf-8")
    write_json(summary_path, packet_summary)
    return csv_path, jsonl_path, md_path, summary_path


def build_gpu_preflight() -> dict[str, Any]:
    preflight: dict[str, Any] = {
        "checked": True,
        "gpu_available": False,
        "cuda_available": False,
        "device": "cpu",
        "device_name": "",
        "nvidia_smi_available": False,
        "torch_available": False,
        "torch_cuda_available": False,
        "torch_cuda_device_count": 0,
        "sentence_transformers_available": importlib.util.find_spec("sentence_transformers") is not None,
        "bge_m3_model": "BAAI/bge-m3",
        "bge_m3_cache_path": "",
        "bge_m3_cache_available": False,
        "faiss_available": False,
        "faiss_gpu_capable": False,
        "faiss_version": "",
        "fallback_reason": "",
    }
    try:
        import faiss  # type: ignore

        preflight["faiss_available"] = True
        preflight["faiss_version"] = _clean(getattr(faiss, "__version__", "unknown"))
        get_num_gpus = getattr(faiss, "get_num_gpus", None)
        faiss_gpu_count = int(get_num_gpus()) if callable(get_num_gpus) else 0
        preflight["faiss_gpu_count"] = faiss_gpu_count
        preflight["faiss_gpu_capable"] = bool(
            faiss_gpu_count > 0
            and hasattr(faiss, "StandardGpuResources")
            and hasattr(faiss, "index_cpu_to_gpu")
            and hasattr(faiss, "index_gpu_to_cpu")
        )
    except Exception as exc:
        preflight["faiss_error"] = f"{type(exc).__name__}: {exc}"

    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        if completed.returncode == 0:
            names = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
            preflight["nvidia_smi_available"] = True
            preflight["nvidia_smi_device_names"] = names
            if names and not preflight["device_name"]:
                preflight["device_name"] = names[0]
    except Exception as exc:
        preflight["nvidia_smi_error"] = f"{type(exc).__name__}: {exc}"

    try:
        import torch  # type: ignore

        preflight["torch_available"] = True
        cuda_available = bool(torch.cuda.is_available())
        preflight["torch_cuda_available"] = cuda_available
        preflight["cuda_available"] = cuda_available
        if cuda_available:
            count = int(torch.cuda.device_count())
            preflight["torch_cuda_device_count"] = count
            preflight["gpu_available"] = count > 0
            preflight["device"] = "cuda:0" if count > 0 else "cpu"
            if count > 0:
                preflight["device_name"] = _clean(torch.cuda.get_device_name(0))
    except Exception as exc:
        preflight["torch_error"] = f"{type(exc).__name__}: {exc}"

    cache_root = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface") / "hub" / "models--BAAI--bge-m3"
    preflight["bge_m3_cache_path"] = cache_root.as_posix()
    preflight["bge_m3_cache_available"] = cache_root.exists()
    if preflight["gpu_available"] and preflight["cuda_available"]:
        preflight["fallback_reason"] = ""
    elif not preflight["torch_available"]:
        preflight["fallback_reason"] = "torch_unavailable"
    elif not preflight["torch_cuda_available"]:
        preflight["fallback_reason"] = "torch_cuda_unavailable"
    elif not preflight["nvidia_smi_available"]:
        preflight["fallback_reason"] = "nvidia_smi_unavailable"
    return preflight


def discover_external_vector_db() -> dict[str, Any]:
    namespace = _clean(
        os.environ.get("ACTUAL_RAG_EVAL_VECTOR_NAMESPACE")
        or os.environ.get("RAG_VECTOR_NAMESPACE")
        or os.environ.get("VECTOR_DB_NAMESPACE")
    )
    dsn_present = bool(
        _clean(os.environ.get("ACTUAL_RAG_EVAL_VECTOR_DB_DSN"))
        or _clean(os.environ.get("RAG_VECTOR_DB_DSN"))
        or _clean(os.environ.get("VECTOR_DB_DSN"))
    )
    configured = bool(namespace or dsn_present)
    nonprod = bool(namespace and re.search(r"(nonprod|dev|test|local|diagnostic)", namespace, flags=re.I))
    allowed = os.environ.get("ACTUAL_RAG_EVAL_ALLOW_EXTERNAL_VECTOR_DB") == "1"
    return {
        "configured": configured,
        "invoked": False,
        "reachable": False,
        "namespace": namespace,
        "production_namespace": bool(configured and not nonprod),
        "fallback_reason": (
            "not_configured"
            if not configured
            else "production_or_ambiguous_namespace_blocked"
            if not nonprod
            else "explicit_external_vectordb_invocation_disabled" if not allowed else "adapter_not_implemented"
        ),
    }


def build_backend_comparison_metrics(raw_outputs: Sequence[Mapping[str, Any]], adapter: Any) -> dict[str, Any]:
    comparisons = [
        output.get("retrieval_backend_comparison")
        for output in raw_outputs
        if isinstance(output.get("retrieval_backend_comparison"), Mapping)
    ]
    item_count = max(len(comparisons), 1)

    def candidate_counts(name: str) -> list[int]:
        return [
            int(((comparison.get("candidate_counts") or {}).get(name)) or 0)
            for comparison in comparisons
            if isinstance(comparison, Mapping)
        ]

    def latency_values(name: str) -> list[float]:
        return [
            float(((comparison.get("latency_ms") or {}).get(name)) or 0.0)
            for comparison in comparisons
            if isinstance(comparison, Mapping)
        ]

    overlap = [
        int(((comparison.get("overlap_counts") or {}).get("bm25_vector_topk")) or 0)
        for comparison in comparisons
        if isinstance(comparison, Mapping)
    ]
    backend_diagnostics = (
        getattr(adapter, "backend_diagnostics", {})
        if isinstance(getattr(adapter, "backend_diagnostics", {}), Mapping)
        else {}
    )
    vector_available = bool(backend_diagnostics.get("vector_index_available", False))
    if not comparisons:
        return {
            "comparison_available": False,
            "comparison_row_count": 0,
            "comparison_missing_row_count": len(raw_outputs),
            "bm25_retrieval_empty_rate": None,
            "vector_retrieval_empty_rate": None,
            "hybrid_retrieval_empty_rate": None,
            "bm25_candidate_count_avg": None,
            "vector_candidate_count_avg": None,
            "hybrid_candidate_count_avg": None,
            "bm25_vector_topk_overlap_avg": None,
            "vector_latency_ms_p50": None,
            "vector_latency_ms_p95": None,
            "bm25_latency_ms_p50": None,
            "bm25_latency_ms_p95": None,
            "hybrid_latency_ms_p50": None,
            "hybrid_latency_ms_p95": None,
            "embedding_build_latency_ms": float(backend_diagnostics.get("embedding_build_latency_ms") or 0.0),
            "index_load_or_build_latency_ms": float(backend_diagnostics.get("index_load_or_build_latency_ms") or 0.0),
            "gpu_used_for_embedding_count": 0,
            "vector_index_available": vector_available,
            "fallback_reason": _clean(backend_diagnostics.get("fallback_reason")) or "item_backend_comparison_unavailable",
        }
    return {
        "comparison_available": True,
        "comparison_row_count": len(comparisons),
        "comparison_missing_row_count": max(len(raw_outputs) - len(comparisons), 0),
        "bm25_retrieval_empty_rate": round(sum(1 for value in candidate_counts("bm25") if value == 0) / item_count, 6),
        "vector_retrieval_empty_rate": round(sum(1 for value in candidate_counts("vector") if value == 0) / item_count, 6),
        "hybrid_retrieval_empty_rate": round(sum(1 for value in candidate_counts("hybrid") if value == 0) / item_count, 6),
        "bm25_candidate_count_avg": _average(candidate_counts("bm25")),
        "vector_candidate_count_avg": _average(candidate_counts("vector")),
        "hybrid_candidate_count_avg": _average(candidate_counts("hybrid")),
        "bm25_vector_topk_overlap_avg": _average(overlap),
        "vector_latency_ms_p50": _latency_distribution_ms(latency_values("vector"))["p50"],
        "vector_latency_ms_p95": _latency_distribution_ms(latency_values("vector"))["p95"],
        "bm25_latency_ms_p50": _latency_distribution_ms(latency_values("bm25"))["p50"],
        "bm25_latency_ms_p95": _latency_distribution_ms(latency_values("bm25"))["p95"],
        "hybrid_latency_ms_p50": _latency_distribution_ms(latency_values("hybrid"))["p50"],
        "hybrid_latency_ms_p95": _latency_distribution_ms(latency_values("hybrid"))["p95"],
        "embedding_build_latency_ms": float(backend_diagnostics.get("embedding_build_latency_ms") or 0.0),
        "index_load_or_build_latency_ms": float(backend_diagnostics.get("index_load_or_build_latency_ms") or 0.0),
        "gpu_used_for_embedding_count": sum(
            1 for _comparison in comparisons if bool(backend_diagnostics.get("gpu_used_for_embedding"))
        ),
        "vector_index_available": vector_available,
        "fallback_reason": _clean(backend_diagnostics.get("fallback_reason")),
    }


def build_surface_comparison_metrics(raw_outputs: Sequence[Mapping[str, Any]], top_k: int) -> dict[str, Any]:
    comparisons = [
        output.get("retrieval_surface_comparison")
        for output in raw_outputs
        if isinstance(output.get("retrieval_surface_comparison"), Mapping)
    ]
    denominator = max(len(comparisons), 1)

    def surface(name: str, comparison: Mapping[str, Any]) -> Mapping[str, Any]:
        value = comparison.get(name)
        return value if isinstance(value, Mapping) else {}

    source_rows = [surface("source_native", comparison) for comparison in comparisons]
    searchunit_rows = [surface("searchunit_searchview", comparison) for comparison in comparisons]
    source_retrieved = sum(1 for row in source_rows if row.get("expected_evidence_retrieved"))
    searchunit_retrieved = sum(1 for row in searchunit_rows if row.get("expected_evidence_retrieved"))
    metrics = {
        "surface_comparison_available": bool(comparisons),
        "surface_comparison_row_count": len(comparisons),
        "source_native_retrieval_empty_rate": round(
            sum(1 for row in source_rows if row.get("retrieval_empty")) / denominator,
            6,
        ),
        "searchunit_retrieval_empty_rate": round(
            sum(1 for row in searchunit_rows if row.get("retrieval_empty")) / denominator,
            6,
        ),
        "source_native_expected_anchor_recall@k_diagnostic": round(source_retrieved / denominator, 6),
        "searchunit_expected_anchor_recall@k_diagnostic": round(searchunit_retrieved / denominator, 6),
        f"source_native_expected_anchor_recall@{top_k}_diagnostic": round(source_retrieved / denominator, 6),
        f"searchunit_expected_anchor_recall@{top_k}_diagnostic": round(searchunit_retrieved / denominator, 6),
        "source_native_expected_evidence_text_presence_rate": round(
            sum(1 for row in source_rows if row.get("expected_evidence_in_corpus_normalized")) / denominator,
            6,
        ),
        "searchunit_expected_evidence_text_presence_rate": round(
            sum(1 for row in searchunit_rows if row.get("expected_evidence_in_corpus_normalized")) / denominator,
            6,
        ),
        "expected_evidence_exact_present_in_source_native_count": sum(
            1 for row in source_rows if row.get("expected_evidence_in_corpus_exact")
        ),
        "expected_evidence_normalized_present_in_source_native_count": sum(
            1 for row in source_rows if row.get("expected_evidence_in_corpus_normalized")
        ),
        "expected_anchor_present_in_source_native_count": sum(1 for row in source_rows if row.get("expected_anchor_in_corpus")),
        "expected_anchor_present_in_searchunit_count": sum(1 for row in searchunit_rows if row.get("expected_anchor_in_corpus")),
        "source_native_target_span_present_but_not_retrieved_count": sum(
            1
            for row in source_rows
            if row.get("expected_evidence_in_corpus_normalized") and not row.get("expected_evidence_retrieved")
        ),
        "source_native_target_span_absent_count": sum(
            1 for row in source_rows if not row.get("expected_evidence_in_corpus_normalized")
        ),
        "searchunit_target_span_absent_count": sum(
            1 for row in searchunit_rows if not row.get("expected_evidence_in_corpus_normalized")
        ),
        "source_native_beats_searchunit_count": sum(1 for row in comparisons if row.get("source_native_beats_searchunit")),
        "searchunit_beats_source_native_count": sum(1 for row in comparisons if row.get("searchunit_beats_source_native")),
        "both_surfaces_fail_count": sum(1 for row in comparisons if row.get("both_surfaces_fail")),
    }
    return metrics


def add_surface_metrics(summary: dict[str, Any], surface_metrics: Mapping[str, Any], *, top_k: int) -> None:
    summary["diagnostic_metrics"].update(surface_metrics)
    source_num = int(surface_metrics.get(f"source_native_expected_anchor_recall@{top_k}_diagnostic") is not None and round(float(surface_metrics.get(f"source_native_expected_anchor_recall@{top_k}_diagnostic") or 0) * int(surface_metrics.get("surface_comparison_row_count") or 0)))
    search_num = int(surface_metrics.get(f"searchunit_expected_anchor_recall@{top_k}_diagnostic") is not None and round(float(surface_metrics.get(f"searchunit_expected_anchor_recall@{top_k}_diagnostic") or 0) * int(surface_metrics.get("surface_comparison_row_count") or 0)))
    denominator = int(surface_metrics.get("surface_comparison_row_count") or 0)
    for name, numerator, tier in (
        ("source_native_resolved_evidence_available_rate_provisional", int(surface_metrics.get("expected_evidence_normalized_present_in_source_native_count") or 0), "provisional"),
        (f"source_native_weak_evidence_match_recall@{top_k}", source_num, "provisional"),
        ("surface_selected_e2e_rag_success_provisional", source_num, "provisional"),
        (f"source_native_expected_anchor_recall@{top_k}_diagnostic", source_num, "diagnostic"),
        (f"searchunit_expected_anchor_recall@{top_k}_diagnostic", search_num, "diagnostic"),
    ):
        metric = _metric_template(name, "surface comparison diagnostics; non-official", tier=tier)
        metric["numerator"] = numerator
        metric["denominator"] = denominator
        metric = _finish_metric(metric)
        if tier == "provisional":
            summary["provisional_metrics"][name] = metric
        else:
            summary.setdefault("diagnostic_metric_details", {})[name] = metric


def write_human_review_packet_csv(output_dir: Path, packet_rows: Sequence[Mapping[str, Any]]) -> tuple[Path, int]:
    path = output_dir / "human_review_packet.csv"
    fieldnames = list(EVIDENCE_MAPPING_PACKET_FIELDS)
    for row in packet_rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(str(key))
    output_dir.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in packet_rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return path, len(packet_rows)


def _artifact_contract(
    *,
    output_mode: str,
    report_path: Path,
    legacy_written: bool,
    human_review_packet_path: Path | None,
) -> dict[str, Any]:
    return {
        "output_mode": output_mode,
        "primary_report_json": report_path.as_posix() if output_mode in {"single", "both"} else "",
        "single_artifact_default": output_mode == "single",
        "legacy_sidecars_written": bool(legacy_written),
        "human_review_packet_exception": bool(human_review_packet_path),
        "human_review_packet_path": human_review_packet_path.as_posix() if human_review_packet_path else "",
        "routine_run_file_policy": "report.json_only_unless_legacy_or_human_review_packet_requested",
        "legacy_artifacts_allowed_only_by_output_mode": True,
    }


def run_eval_from_paths(
    *,
    dataset_path: Path | str,
    output_dir: Path | str,
    context_jsonl_path: Path | str | None = None,
    index: str = "current",
    top_k: int = 10,
    run_id: str | None = None,
    command: str = "",
    judge_mode: str = "heuristic",
    judge_backend: str = "",
    judge_base_url: str = "",
    judge_model: str = "",
    judge_threshold: float = 0.5,
    judge_timeout_seconds: int = 60,
    judge_max_tokens: int = 360,
    skip_judge_endpoint_check: bool = False,
    provisional_require_citations: bool = False,
    generated_at: str | None = None,
    comparison_summary: Mapping[str, Any] | None = None,
    comparison_target: str = "",
    report_root: Path | str = REPORT_ROOT,
    registry_path: Path | str | None = None,
    status_jsonl_path: Path | str = STATUS_JSONL_PATH,
    append_registry: bool = False,
    write_latest: bool = False,
    resolve_expected_evidence: bool = True,
    evidence_resolution_scope: str = "retrieved-only",
    max_evidence_candidates: int = 5,
    min_evidence_resolution_score: float = 0.35,
    count_medium_evidence_resolution: bool = False,
    write_evidence_mapping_packet: bool = False,
    write_human_review_packet: bool = False,
    output_mode: str = "single",
    retrieval_surface: str = "auto",
    retrieval_backend: str = "auto",
    retrieval_adapter: Any | None = None,
    source_native_units: Sequence[Mapping[str, Any]] | None = None,
    searchunit_units: Sequence[Mapping[str, Any]] | None = None,
    source_native_embedding_provider: Any | None = None,
) -> RagEvalBundle:
    dataset = Path(dataset_path)
    output = Path(output_dir)
    normalized_output_mode = _clean(output_mode).lower() or "single"
    if normalized_output_mode not in {"single", "legacy", "both"}:
        raise DatasetSchemaError(f"unsupported output mode: {output_mode}")
    normalized_retrieval_backend = _clean(retrieval_backend).lower() or "auto"
    if normalized_retrieval_backend not in {"auto", "bm25", "vector", "hybrid"}:
        raise DatasetSchemaError(f"unsupported retrieval backend: {retrieval_backend}")
    normalized_retrieval_surface = _clean(retrieval_surface).replace("_", "-").lower() or "auto"
    if normalized_retrieval_surface not in {"auto", "searchunit-searchview", "source-native", "source-atom", "evidence-bundle"}:
        raise DatasetSchemaError(f"unsupported retrieval surface: {retrieval_surface}")
    if _output_dir_has_artifacts(output):
        raise DatasetSchemaError(f"{output}: already contains actual RAG eval artifacts")
    items = load_eval_dataset(dataset)
    gpu_preflight = build_gpu_preflight()
    external_vector_db = discover_external_vector_db()
    if retrieval_adapter is not None:
        adapter = retrieval_adapter
        if hasattr(adapter, "requested_backend"):
            try:
                adapter.requested_backend = normalized_retrieval_backend
            except Exception:
                pass
    elif context_jsonl_path:
        adapter = JsonlContextAdapter(context_jsonl_path, requested_backend=normalized_retrieval_backend)
    else:
        source_adapter = SourceNativeHybridAdapter(
            ROOT,
            requested_backend=normalized_retrieval_backend,
            units=source_native_units,
            embedding_provider=source_native_embedding_provider,
            gpu_preflight=gpu_preflight,
            external_vector_db=external_vector_db,
        )
        searchunit_adapter = RepoCurrentHybridAdapter(
            ROOT,
            requested_backend=normalized_retrieval_backend,
            payloads=searchunit_units,
            gpu_preflight=gpu_preflight,
            external_vector_db=external_vector_db,
        )
        adapter = SurfaceComparingRagAdapter(
            requested_surface=normalized_retrieval_surface,
            requested_backend=normalized_retrieval_backend,
            source_adapter=source_adapter,
            searchunit_adapter=searchunit_adapter,
        )
    generated_at = generated_at or utc_now_iso()
    run_id = run_id or make_actual_rag_run_id(dataset, generated_at=generated_at, report_root=report_root)
    judge_adapter = build_judge_adapter(
        judge_mode=judge_mode,
        judge_backend=judge_backend,
        judge_base_url=judge_base_url,
        judge_model=judge_model,
        judge_threshold=judge_threshold,
        judge_timeout_seconds=judge_timeout_seconds,
        judge_max_tokens=judge_max_tokens,
        skip_judge_endpoint_check=skip_judge_endpoint_check,
    )
    started = time.perf_counter()

    raw_outputs: list[dict[str, Any]] = []
    for item in items:
        try:
            raw_outputs.append(adapter.run_item(item, top_k=top_k))
        except Exception as exc:  # keep row-level pipeline failures inspectable
            raw_outputs.append(_pipeline_error_output(item, f"{type(exc).__name__}: {exc}"))
    evidence_config = _evidence_resolution_config(
        enabled=resolve_expected_evidence,
        scope=evidence_resolution_scope,
        max_candidates=max_evidence_candidates,
        min_score=min_evidence_resolution_score,
        count_medium=count_medium_evidence_resolution,
    )
    if evidence_config.enabled:
        raw_outputs = apply_expected_evidence_resolution(
            items=items,
            raw_outputs=raw_outputs,
            adapter=adapter,
            config=evidence_config,
        )

    top_k_values = top_k_values_for(top_k)
    summary, scored_rows = score_rag_eval_items(
        items,
        raw_outputs,
        top_k_values=top_k_values,
        judge_adapter=judge_adapter,
        provisional_require_citations=provisional_require_citations,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    backend_comparison = build_backend_comparison_metrics(raw_outputs, adapter)
    summary["diagnostic_metrics"].update(backend_comparison)
    surface_comparison = build_surface_comparison_metrics(raw_outputs, top_k)
    add_surface_metrics(summary, surface_comparison, top_k=top_k)
    surface_next_repair_targets: list[str] = []
    if int(surface_comparison.get("source_native_target_span_present_but_not_retrieved_count") or 0) > 0:
        surface_next_repair_targets.append("repair source-native retrieval ranking/query formulation")
    if int(surface_comparison.get("source_native_target_span_absent_count") or 0) > 0:
        surface_next_repair_targets.append("repair source-native corpus/source coverage")
    if bool(surface_comparison.get("surface_comparison_available")):
        surface_next_repair_targets.append("keep SearchUnit/SearchView as legacy comparison baseline only")
    retrieval_backend_report = (
        dict(adapter.retrieval_backend_report)
        if isinstance(getattr(adapter, "retrieval_backend_report", None), Mapping)
        else {
            "requested": normalized_retrieval_backend,
            "selected": "unknown",
            "bm25_enabled": False,
            "vector_enabled": False,
            "hybrid_enabled": False,
            "embedding_model": "",
            "embedding_device": "unavailable",
            "gpu_used_for_embedding": False,
            "vector_index_kind": "unavailable",
            "vector_index_type": "unavailable",
            "vector_dim": 0,
            "indexed_unit_count": 0,
            "query_count": len(items),
            "fallback_reason": "adapter_did_not_report_backend",
        }
    )
    retrieval_surface_report = (
        dict(adapter.retrieval_surface_report)
        if isinstance(getattr(adapter, "retrieval_surface_report", None), Mapping)
        else {
            "requested": normalized_retrieval_surface.replace("-", "_"),
            "selected": "precomputed_context" if context_jsonl_path else "unknown",
            "source_native_available": False,
            "source_native_selected": False,
            "searchunit_searchview_role": "legacy_baseline",
            "fallback_reason": "adapter_did_not_report_surface",
        }
    )
    retrieval_surface_decision = (
        dict(adapter.retrieval_surface_decision)
        if isinstance(getattr(adapter, "retrieval_surface_decision", None), Mapping)
        else {
            "selected_default_surface": retrieval_surface_report.get("selected"),
            "searchunit_searchview_demoted": False,
            "demotion_reason": "",
            "source_native_available": bool(retrieval_surface_report.get("source_native_available")),
            "source_native_selected": bool(retrieval_surface_report.get("source_native_selected")),
            "fallback_reason": retrieval_surface_report.get("fallback_reason"),
            "recommendation": "surface_comparison_unavailable",
        }
    )
    generator_config = {
        "provider": "extractive-v1",
        "generator_provider": "extractive-v1",
        "extractive_only": True,
        "actual_generation_model_used": False,
        "local_llm_generation_available": False,
        "local_llm_not_used_reason": "local_llm_generator_not_wired_for_this_pass",
        "external_api_calls": False,
        "expected_answer_used_for_generation": False,
        "expected_evidence_used_for_generation": False,
    }
    summary.update(
        {
            "run_id": run_id,
            "generated_at": generated_at,
            "command": command,
            "dataset_path": dataset.as_posix(),
            "dataset_slug": dataset_slug_for_path(dataset),
            "output_dir": output.as_posix(),
            "index": index,
            "index_retrieval_config": adapter.config,
            "retrieval_backend": retrieval_backend_report,
            "retrieval_surface": retrieval_surface_report,
            "retrieval_surface_decision": retrieval_surface_decision,
            "gpu_preflight": gpu_preflight,
            "external_vector_db": external_vector_db,
            "backend_comparison": backend_comparison,
            "surface_comparison": surface_comparison,
            "generator_config": generator_config,
            "generator_model_config": generator_config,
            "top_k": top_k,
            "top_k_values": list(top_k_values),
            "judge_mode": judge_mode,
            "provisional_require_citations": bool(provisional_require_citations),
            "expected_evidence_resolution_config": {
                "enabled": bool(evidence_config.enabled),
                "scope": evidence_config.scope,
                "max_candidates": evidence_config.max_candidates,
                "min_score": evidence_config.min_score,
                "count_medium": evidence_config.count_medium,
                "diagnostic_candidate_lookup_only": True,
                "retriever_ranking_change": False,
                "gold_or_qrels_mutation": False,
                "candidate_generation_input_policy": "query_text_only_for_index_lookup; expected fields scoring_only",
            },
            "evidence_mapping_packet_config": {
                "enabled": bool(write_human_review_packet or write_evidence_mapping_packet),
                "diagnostic_review_packet_only": True,
                "machine_recommendation_not_gold": True,
                "human_decision_fields_filled_by_codex": False,
                "retriever_ranking_change": False,
                "gold_or_qrels_mutation": False,
                "single_review_artifact_format": "csv",
            },
            "elapsed_ms": elapsed_ms,
            "non_production": True,
            "official_metric_input_rows": 0,
            "official_metric_input_rows_created": 0,
            "official_metric_input_rows_consumed": 0,
            "protected_namespaces_touched": [],
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
            "gold_fields_used_for_candidate_generation": False,
            "query_id_used_for_candidate_generation": False,
            "row_id_used_for_candidate_generation": False,
            "target_id_used_for_candidate_generation": False,
            "baseline_topk_used_for_candidate_generation": False,
            "retriever_oracle_shortcut_used": False,
            "guardrails": {
                "non_production": True,
                "gold_mutation": False,
                "qrels_mutation": False,
                "label_mutation": False,
                "answerability_label_mutation": False,
                "expected_answer_mutation": False,
                "expected_evidence_mutation": False,
                "denominator_mutation": False,
                "retriever_ranking_improvement": False,
                "official_metric": False,
                "official_metric_input_rows": 0,
                "official_metric_input_rows_created": 0,
                "official_metric_input_rows_consumed": 0,
                "promotion_evidence": False,
                "product_success_evidence_allowed": False,
                "live_readiness_claim": False,
                "protected_namespaces_touched": [],
                "raw_prompt_payload_written": False,
                "raw_response_payload_written": False,
                "gold_fields_used_for_candidate_generation": False,
                "query_id_used_for_candidate_generation": False,
                "row_id_used_for_candidate_generation": False,
                "target_id_used_for_candidate_generation": False,
                "baseline_topk_used_for_candidate_generation": False,
                "retriever_oracle_shortcut_used": False,
            },
            "assumptions": [
                "actual RAG eval remains non-production diagnostic infrastructure",
                "SearchUnit/SearchView text is candidate-only retrieval input",
                "SourceAtom/EvidenceBundle remains the evidence truth surface",
                "missing GPU/vector dependencies are recorded as fallback reasons rather than silently ignored",
            ],
            "limitations": [
                "extractive-v1 remains the generator for this pass",
                "backend comparison metrics are diagnostic and not official retrieval metrics",
                "external VectorDB is optional and blocked unless explicitly non-production",
            ],
            "next_repair_targets": [
                *surface_next_repair_targets,
                "replace extractive-v1 only after a richer repo generator is ready",
                "use human-owned review before any gold/qrels/answerability updates",
                "add external VectorDB parity only against an explicitly non-production namespace",
            ],
        }
    )

    report_path = output / "report.json"
    legacy_items_path = output / "rag_eval_items.jsonl"
    legacy_summary_path = output / "rag_eval_summary.json"
    legacy_markdown_path = output / "rag_eval_report.md"
    single_mode = normalized_output_mode in {"single", "both"}
    legacy_mode = normalized_output_mode in {"legacy", "both"}
    legacy_mapping_packet_requested = bool(write_evidence_mapping_packet and legacy_mode and not write_human_review_packet)
    human_packet_requested = bool(write_human_review_packet or (write_evidence_mapping_packet and not legacy_mapping_packet_requested))
    summary["artifact_paths"] = {
        "report_json": report_path.as_posix() if single_mode else "",
        "items_jsonl": legacy_items_path.as_posix() if legacy_mode else "",
        "summary_json": report_path.as_posix() if single_mode else legacy_summary_path.as_posix(),
        "markdown_report": legacy_markdown_path.as_posix() if legacy_mode else "",
        "evidence_resolution_candidates_jsonl": (output / "evidence_resolution_candidates.jsonl").as_posix() if legacy_mode else "",
        "evidence_resolution_review_md": (output / "evidence_resolution_review.md").as_posix() if legacy_mode else "",
        "evidence_mapping_review_packet_csv": (output / "evidence_mapping_review_packet.csv").as_posix()
        if legacy_mapping_packet_requested
        else "",
        "evidence_mapping_review_packet_jsonl": (output / "evidence_mapping_review_packet.jsonl").as_posix()
        if legacy_mapping_packet_requested
        else "",
        "evidence_mapping_review_packet_md": (output / "evidence_mapping_review_packet.md").as_posix()
        if legacy_mapping_packet_requested
        else "",
        "evidence_mapping_packet_summary_json": (output / "evidence_mapping_packet_summary.json").as_posix()
        if legacy_mapping_packet_requested
        else "",
        "human_review_packet_csv": (output / "human_review_packet.csv").as_posix() if human_packet_requested else "",
    }
    packet_rows, packet_summary = build_evidence_mapping_packet(
        summary=summary,
        rows=scored_rows,
        adapter=adapter,
        enabled=bool(human_packet_requested or legacy_mapping_packet_requested),
    )
    _apply_mapping_packet_summary(summary, packet_summary)
    evidence_candidates = evidence_resolution_candidate_rows(scored_rows)
    human_review_packet_path: Path | None = None
    if human_packet_requested:
        human_review_packet_path, packet_row_count = write_human_review_packet_csv(output, packet_rows)
    else:
        packet_row_count = 0
    summary["human_review_packet"] = {
        "enabled": human_packet_requested,
        "path": human_review_packet_path.as_posix() if human_review_packet_path else "",
        "row_count": packet_row_count,
        "review_reason": "explicit_human_review_packet_flag" if human_packet_requested else "",
        "format": "csv" if human_packet_requested else "",
        "format_decision": "csv is the single review artifact because it is directly spreadsheet-reviewable and avoids JSONL/Markdown/summary sidecars",
        "human_decision_fields_blank": True,
        "gold_qrels_labels_mutated": False,
    }
    summary["evidence_resolution"] = _evidence_resolution_summary(summary)
    summary["evidence_mapping_packet"] = _evidence_mapping_packet_summary(summary)
    summary["artifact_contract"] = _artifact_contract(
        output_mode=normalized_output_mode,
        report_path=report_path,
        legacy_written=legacy_mode,
        human_review_packet_path=human_review_packet_path,
    )
    if comparison_summary is not None:
        validate_actual_rag_guardrails(comparison_summary)
        summary["comparison"] = build_run_comparison(
            comparison_summary,
            summary,
            target_label=comparison_target,
        )
    summary["items"] = scored_rows
    summary["evidence_resolution_candidates"] = evidence_candidates
    validate_actual_rag_guardrails(summary)
    output.mkdir(parents=True, exist_ok=True)
    if single_mode:
        write_json(report_path, summary)
    if legacy_mode:
        legacy_summary = dict(summary)
        legacy_summary.pop("items", None)
        legacy_summary.pop("evidence_resolution_candidates", None)
        write_jsonl(legacy_items_path, scored_rows)
        write_evidence_resolution_artifacts(output_dir=output, summary=legacy_summary, rows=scored_rows)
        write_json(legacy_summary_path, legacy_summary)
        legacy_markdown_path.write_text(render_markdown_report(legacy_summary, scored_rows), encoding="utf-8")
    if legacy_mapping_packet_requested:
        write_evidence_mapping_packet_artifacts(
            output_dir=output,
            summary=summary,
            packet_rows=packet_rows,
            packet_summary=packet_summary,
        )
    registry = Path(registry_path) if registry_path is not None else Path(report_root) / REGISTRY_FILENAME
    if append_registry:
        append_run_registry(summary, registry_path=registry)
        append_actual_rag_status_event(summary, status_jsonl_path=status_jsonl_path)
    if write_latest:
        write_latest_pointers(summary, report_root=report_root)
        write_report_index(report_root=report_root)
    summary_path = report_path if single_mode else legacy_summary_path
    items_path = report_path if single_mode else legacy_items_path
    markdown_path = report_path if single_mode else legacy_markdown_path
    return RagEvalBundle(
        output_dir=output,
        items_path=items_path,
        summary_path=summary_path,
        markdown_path=markdown_path,
        summary=summary,
        report_path=report_path if single_mode else None,
    )


def render_markdown_report(summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    strict = summary["strict_metrics"]
    provisional = summary["provisional_metrics"]
    inferred_answerable = summary.get("inferred_answerable_metrics") or {}
    diagnostic_details = summary.get("diagnostic_metric_details") or {}
    diagnostics = summary["diagnostic_metrics"]

    def append_metric_table(lines: list[str], metrics: Mapping[str, Any]) -> None:
        lines.extend(
            [
                "| Metric | Tier | Numerator | Denominator | Score | Skipped | N/A | Diagnostic-only |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for name, metric in metrics.items():
            score = "" if metric["score"] is None else f"{metric['score']:.6f}"
            lines.append(
                f"| {name} | {metric['tier']} | {metric['numerator']} | {metric['denominator']} | {score} | "
                f"{metric['skipped_count']} | {metric['not_applicable_count']} | {metric['diagnostic_only_count']} |"
            )

    def preview(value: Any, limit: int = 160) -> str:
        text = re.sub(r"\s+", " ", _clean(value))
        if len(text) <= limit:
            return text
        return text[: max(limit - 3, 0)].rstrip() + "..."

    def top_context_preview(row: Mapping[str, Any]) -> str:
        contexts = [context for context in _as_list(row.get("retrieved_contexts")) if isinstance(context, Mapping)]
        return preview(contexts[0].get("text") if contexts else "")

    def metric_failure_notes(row: Mapping[str, Any]) -> list[str]:
        labels = set(row.get("failure_labels") or [])
        results = row.get("metric_results") if isinstance(row.get("metric_results"), Mapping) else {}
        judge_result = results.get("judged_answer_correctness_provisional") if isinstance(results, Mapping) else None
        notes: list[str] = []
        if "retrieval_empty" in labels:
            notes.append("retrieval_empty")
        if isinstance(judge_result, Mapping) and judge_result.get("passed") is False:
            notes.append("answer_judge_failed")
        if any(
            str(name).startswith("evidence_recall@") and value is False
            for name, value in results.items()
        ) or any(
            str(name).startswith("weak_evidence_match_recall@") and value is False
            for name, value in results.items()
        ):
            notes.append("evidence_match_failed")
        if "citation_missing" in labels:
            notes.append("citation_missing")
        if "citation_wrong" in labels:
            notes.append("citation_wrong")
        if "answer_exact_mismatch" in labels:
            notes.append("answer_exact_mismatch")
        if results.get("e2e_rag_success_provisional") is False:
            notes.append("e2e_provisional_failed")
        return notes

    lines = [
        "# Actual RAG Eval Report",
        "",
        f"- Run id: `{summary.get('run_id')}`",
        f"- Generated at: `{summary.get('generated_at')}`",
        f"- Command used: `{summary.get('command') or 'not recorded'}`",
        f"- Dataset path: `{summary.get('dataset_path')}`",
        f"- Index/retrieval config: `{json.dumps(summary.get('index_retrieval_config'), ensure_ascii=False, sort_keys=True)}`",
        f"- Generator/model config: `{json.dumps(summary.get('generator_model_config'), ensure_ascii=False, sort_keys=True)}`",
        f"- Total item count: `{summary.get('total_item_count')}`",
        f"- Answerability distribution: `{json.dumps(summary.get('answerability_distribution'), ensure_ascii=False, sort_keys=True)}`",
        "",
    ]
    comparison = summary.get("comparison")
    if isinstance(comparison, Mapping) and comparison.get("rows"):
        lines.extend(
            [
                "## Previous Run Comparison",
                "",
                "| Metric | Tier | Previous | Current | Delta | Interpretation |",
                "|---|---|---:|---:|---:|---|",
            ]
        )
        for row in comparison.get("rows") or []:
            if not isinstance(row, Mapping):
                continue
            delta = row.get("delta")
            rendered_delta = "" if delta is None else f"{float(delta):.6f}"
            lines.append(
                f"| {row.get('metric')} | {row.get('tier')} | {row.get('previous')} | "
                f"{row.get('current')} | {rendered_delta} | {row.get('interpretation')} |"
            )
        lines.extend(
            [
                "",
                "Comparison rows are non-production diagnostics only. Denominator changes are not interpreted as quality improvement.",
                "",
            ]
        )
    lines.extend(["## Strict Headline Metrics", ""])
    append_metric_table(lines, strict)
    lines.extend(
        [
            "",
            "## Provisional RAG Metrics",
            "",
            f"- Judge config: `{json.dumps(summary.get('judge_config'), ensure_ascii=False, sort_keys=True)}`",
            f"- Provisional metric policy: `{json.dumps(summary.get('provisional_metric_policy'), ensure_ascii=False, sort_keys=True)}`",
            "- `e2e_rag_success_provisional` requires the provisional answer judge to pass; weak evidence overlap alone is insufficient.",
            "- The answer/context consistency diagnostic is used as a conservative E2E guard when context is available, but its standalone rate is not answer correctness.",
            "",
        ]
    )
    append_metric_table(lines, provisional)
    if inferred_answerable:
        lines.extend(
            [
                "",
                "## Inferred-Answerable Metrics",
                "",
                "These metrics infer answerability only for metric computation when answerability is unknown but expected answer and expected evidence exist. No gold label mutation occurred, and these are not official strict metrics.",
                "",
            ]
        )
        append_metric_table(lines, inferred_answerable)
    if diagnostic_details:
        lines.extend(
            [
                "",
                "## Diagnostic Consistency Metrics",
                "",
                "`answer_extracted_from_retrieved_context_rate` and `citation_points_to_retrieved_context_rate` are diagnostic consistency checks, not answer correctness and not citation correctness. The answer/context diagnostic can gate provisional E2E as a conservative support check, but it is not a standalone quality claim.",
                "",
            ]
        )
        append_metric_table(lines, diagnostic_details)
    lines.extend(
        [
            "",
            "## Diagnostic Metrics",
            "",
            "| Metric | Value |",
            "|---|---:|",
        ]
    )
    for key in sorted(diagnostics):
        value = diagnostics[key]
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            rendered = str(value)
        lines.append(f"| {key} | `{rendered}` |")

    resolution_rows = evidence_resolution_candidate_rows(rows)
    if diagnostics.get("expected_evidence_resolution_enabled"):
        lines.extend(
            [
                "",
                "## Expected Evidence Resolution Diagnostics",
                "",
                f"- Enabled/scope: `{diagnostics.get('expected_evidence_resolution_enabled')}` / `{diagnostics.get('expected_evidence_resolution_scope')}`",
                f"- Expected evidence rows: `{diagnostics.get('expected_evidence_row_count')}`",
                f"- Missing ID count: `{diagnostics.get('expected_evidence_id_missing_count')}`",
                f"- Exact resolved count: `{diagnostics.get('expected_evidence_id_resolved_exact_count')}`",
                f"- Candidate resolved count: `{diagnostics.get('expected_evidence_id_resolved_candidate_count')}`",
                f"- Unresolved count: `{diagnostics.get('expected_evidence_id_unresolved_count')}`",
                f"- Confidence counts: high=`{diagnostics.get('expected_evidence_resolution_high_confidence_count')}`, medium=`{diagnostics.get('expected_evidence_resolution_medium_confidence_count')}`, low=`{diagnostics.get('expected_evidence_resolution_low_confidence_count')}`",
                f"- Candidates JSONL: `{_artifact_path(summary, 'evidence_resolution_candidates_jsonl')}`",
                f"- Review Markdown: `{_artifact_path(summary, 'evidence_resolution_review_md')}`",
                "",
                "These mappings are diagnostic and do not mutate gold/qrels.",
                "",
                "### Top Unresolved Evidence Rows",
                "",
                "| Item | Query | Expected answer | Evidence preview | Reason unresolved | Top candidate preview |",
                "|---|---|---|---|---|---|",
            ]
        )
        unresolved = [row for row in resolution_rows if not row.get("resolved")]
        if unresolved:
            for row in unresolved[:10]:
                top = (row.get("candidates") or [{}])[0] if row.get("candidates") else {}
                lines.append(
                    f"| `{row.get('id')}` | {preview(row.get('query'), 90)} | {preview(row.get('expected_answer'), 80)} | "
                    f"{preview((row.get('expected_evidence') or {}).get('text'), 100)} | "
                    f"{', '.join(row.get('resolution_warnings') or [])} | {preview(top.get('text_preview'), 100)} |"
                )
        else:
            lines.append("| none |  |  |  |  |  |")
        lines.extend(
            [
                "",
                "### High/Medium Confidence Candidate Mappings",
                "",
                "| Item | Evidence preview | Selected doc_id | Selected chunk_id | Confidence | Score | Match reasons |",
                "|---|---|---|---|---|---:|---|",
            ]
        )
        mapped = False
        for row in resolution_rows:
            selected = row.get("selected_candidate") if isinstance(row.get("selected_candidate"), Mapping) else {}
            if selected.get("confidence") not in {"high", "medium"}:
                continue
            mapped = True
            lines.append(
                f"| `{row.get('id')}` | {preview((row.get('expected_evidence') or {}).get('text'), 100)} | "
                f"`{selected.get('doc_id')}` | `{selected.get('chunk_id')}` | `{selected.get('confidence')}` | "
                f"{selected.get('score')} | {', '.join(selected.get('match_reasons') or [])} |"
            )
        if not mapped:
            lines.append("| none |  |  |  |  |  |  |")

    if diagnostics.get("evidence_mapping_packet_enabled"):
        lines.extend(
            [
                "",
                "## Evidence Mapping Review Packet",
                "",
                f"- Enabled: `{diagnostics.get('evidence_mapping_packet_enabled')}`",
                f"- CSV: `{_artifact_path(summary, 'evidence_mapping_review_packet_csv')}`",
                f"- JSONL: `{_artifact_path(summary, 'evidence_mapping_review_packet_jsonl')}`",
                f"- Markdown: `{_artifact_path(summary, 'evidence_mapping_review_packet_md')}`",
                f"- Summary JSON: `{_artifact_path(summary, 'evidence_mapping_packet_summary_json')}`",
                f"- Packet rows: `{diagnostics.get('evidence_mapping_packet_row_count')}`",
                f"- Item count: `{diagnostics.get('evidence_mapping_packet_item_count')}`",
                f"- Recommendation counts: likely_accept=`{diagnostics.get('evidence_mapping_packet_likely_accept_count')}`, possible_match=`{diagnostics.get('evidence_mapping_packet_possible_match_count')}`, review_needed=`{diagnostics.get('evidence_mapping_packet_review_needed_count')}`, likely_reject=`{diagnostics.get('evidence_mapping_packet_likely_reject_count')}`",
                f"- Review priority counts: P0=`{diagnostics.get('evidence_mapping_packet_p0_count')}`, P1=`{diagnostics.get('evidence_mapping_packet_p1_count')}`, P2=`{diagnostics.get('evidence_mapping_packet_p2_count')}`, P3=`{diagnostics.get('evidence_mapping_packet_p3_count')}`, P4=`{diagnostics.get('evidence_mapping_packet_p4_count')}`",
                f"- Source metadata counts: resolved=`{diagnostics.get('source_metadata_resolved_candidate_count')}`, unresolved=`{diagnostics.get('source_metadata_unresolved_candidate_count')}`, redacted_paths=`{diagnostics.get('source_metadata_redacted_path_count')}`",
                f"- Human decision fields filled by Codex: `{diagnostics.get('human_decision_fields_filled_by_codex')}`",
                "",
                "Human decision fields remain blank. Machine recommendations are diagnostic review hints, not gold mappings. No gold/qrels mutation occurred.",
            ]
        )

    lines.extend(
        [
            "",
            "## Denominator Policy",
            "",
            str(summary.get("denominator_policy")),
            "",
            "## Failure Breakdown",
            "",
            "| Failure label | Count |",
            "|---|---:|",
        ]
    )
    failure_counts = diagnostics.get("failure_category_counts") or {}
    if failure_counts:
        for label, count in failure_counts.items():
            lines.append(f"| {label} | {count} |")
    else:
        lines.append("| none | 0 |")

    failed_rows = [
        row
        for row in rows
        if any(label not in INFORMATIONAL_LABELS for label in row.get("failure_labels") or [])
    ]
    lines.extend(["", "## Top Failed Examples", ""])
    if failed_rows:
        for row in failed_rows[:10]:
            labels = ", ".join(row.get("failure_labels") or [])
            notes = ", ".join(metric_failure_notes(row)) or "none"
            lines.extend(
                [
                    f"- `{row.get('id')}`",
                    f"  - Query: {preview(row.get('query'))}",
                    f"  - Expected answer: {preview(row.get('expected_answer'))}",
                    f"  - Generated answer: {preview(row.get('generated_answer'))}",
                    f"  - Top retrieved context: {top_context_preview(row)}",
                    f"  - Key metric failures: {notes}",
                    f"  - Retrieval empty: `{bool('retrieval_empty' in (row.get('failure_labels') or []))}`",
                    f"  - Answer judge failed: `{bool('answer_judge_failed' in notes or 'answer_judge_fail' in (row.get('failure_labels') or []))}`",
                    f"  - Evidence match failed: `{bool('evidence_match_failed' in notes or 'evidence_not_retrieved' in (row.get('failure_labels') or []))}`",
                    f"  - Citation missing/wrong: `{bool('citation_missing' in (row.get('failure_labels') or []) or 'citation_wrong' in (row.get('failure_labels') or []))}`",
                    f"  - Failure labels: {labels}",
                ]
            )
    else:
        lines.append("- No failed examples in this run.")

    lines.extend(
        [
            "",
            "## Gold/Data Quality Warnings",
            "",
            f"- Missing expected answer count: `{diagnostics.get('missing_expected_answer_count')}`",
            f"- Missing expected evidence count: `{diagnostics.get('missing_expected_evidence_count')}`",
            f"- Missing answerability label count: `{diagnostics.get('missing_answerability_label_count')}`",
            f"- Expected evidence ID missing count: `{diagnostics.get('expected_evidence_id_missing_count')}`",
            f"- Expected evidence ID unresolved count: `{diagnostics.get('expected_evidence_id_unresolved_count')}`",
            f"- Expected evidence text match candidate count: `{diagnostics.get('expected_evidence_text_match_candidate_count')}`",
            f"- Schema warning count: `{diagnostics.get('schema_warning_count')}`",
            f"- Gold missing count: `{diagnostics.get('gold_missing_count')}`",
            "",
            "## Assumptions Made By Codex",
            "",
        ]
    )
    for decision in summary.get("diagnostic_only_decisions") or []:
        lines.append(f"- {decision['decision']} Rationale: {decision['rationale']}")

    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Strict exact/alias answer scoring is deterministic and does not claim semantic equivalence.",
            "- Provisional judged answer correctness is computed with weak assumptions unless a future configured LLM judge is enabled and recorded.",
            "- Weak evidence matching now requires either an ID match or text overlap plus at least one non-generic anchor from expected answer/evidence, but it remains provisional.",
            "- Answer/context and citation/retrieved-context consistency metrics are diagnostic; they do not prove answer correctness or citation correctness.",
            "- Incomplete gold rows still run; they are marked with warning labels and excluded only from strict denominators that require the missing field.",
            "- This runner does not tune retriever ranking.",
            "",
            "## Follow-Up Items Reserved For Human Gold-Policy Decisions",
            "",
            "- Review or supply missing expected answers, expected evidence, answerability labels, relevance labels, and aliases where stricter coverage is desired.",
            "- Decide final citation policy and final semantic/LLM judge policy before any official metric lane is opened.",
            "- Decide which provisional metrics can be promoted, retired, or replaced after reviewing failure examples.",
            "",
            "## Next Repair Targets",
            "",
            "- Connect a real generator adapter if the repo exposes a richer answer-generation path than extractive-v1.",
            "- Add a configurable LLM judge adapter only when model invocation infrastructure and reproducible judge configuration are ready.",
            "- Improve per-item failure examples after larger golden sets expose common failure clusters.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run pragmatic actual RAG eval metric generation")
    parser.add_argument("--dataset", required=True, help="Eval dataset JSONL/JSON path")
    parser.add_argument("--index", default="current", help="Index/path/name label to record in reports")
    parser.add_argument(
        "--context-jsonl",
        default="",
        help="Optional deterministic per-item RAG output/context JSONL for smoke tests or precomputed runs",
    )
    parser.add_argument("--output-mode", default="single", choices=["single", "legacy", "both"])
    parser.add_argument("--retrieval-backend", default="auto", choices=["bm25", "vector", "hybrid", "auto"])
    parser.add_argument(
        "--retrieval-surface",
        default="auto",
        choices=["auto", "searchunit-searchview", "source-native", "source-atom", "evidence-bundle"],
        help="Retrieval corpus surface; auto prefers SourceAtom/EvidenceBundle source-native units when available.",
    )
    parser.add_argument("--use-fake-vector-adapter", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--use-fake-source-native-fixture", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--output-dir",
        default="",
        help="Output directory; defaults to reports/rag_eval/<run_id>",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--judge-mode", default="heuristic", choices=["heuristic", "local-llm"])
    parser.add_argument("--judge-backend", default="", choices=["", "llamacpp", "openai-compatible", "ollama"])
    parser.add_argument("--judge-base-url", default="")
    parser.add_argument("--judge-model", default="")
    parser.add_argument("--judge-threshold", type=float, default=0.5)
    parser.add_argument("--judge-timeout-seconds", type=int, default=60)
    parser.add_argument("--judge-max-tokens", type=int, default=360)
    parser.add_argument("--skip-judge-endpoint-check", action="store_true")
    parser.add_argument(
        "--provisional-require-citations",
        action="store_true",
        help="Require strict citation pass for e2e_rag_success_provisional; default keeps citation checks separate.",
    )
    parser.add_argument(
        "--resolve-expected-evidence",
        action="store_true",
        default=True,
        help="Run diagnostic expected-evidence resolution; enabled by default for retrieved contexts.",
    )
    parser.add_argument(
        "--no-resolve-expected-evidence",
        action="store_false",
        dest="resolve_expected_evidence",
        help="Disable expected-evidence resolution diagnostics.",
    )
    parser.add_argument(
        "--evidence-resolution-scope",
        default="retrieved-only",
        choices=["retrieved-only", "index-candidate-lookup", "both"],
        help="Candidate source for expected-evidence resolution diagnostics.",
    )
    parser.add_argument("--max-evidence-candidates", type=int, default=5)
    parser.add_argument("--min-evidence-resolution-score", type=float, default=0.35)
    parser.add_argument(
        "--count-medium-evidence-resolution",
        action="store_true",
        help="Count medium-confidence evidence resolution candidates as resolved in provisional resolved-evidence metrics.",
    )
    parser.add_argument(
        "--write-evidence-mapping-packet",
        action="store_true",
        help="Deprecated alias for writing a single human review packet in single mode; legacy packet sidecars require --output-mode legacy.",
    )
    parser.add_argument(
        "--write-human-review-packet",
        action="store_true",
        help="Write exactly one additional human review CSV packet with blank human-owned fields.",
    )
    parser.add_argument(
        "--compare-to",
        default="",
        help="Compare this run to a summary JSON/run directory, or to 'latest'/'previous'.",
    )
    parser.add_argument(
        "--write-latest",
        action="store_true",
        help="Update latest pointer JSON files under the report root after a successful run.",
    )
    parser.add_argument(
        "--append-registry",
        action="store_true",
        help="Append runs.jsonl and compact status.jsonl events after a successful run.",
    )
    parser.add_argument(
        "--report-root",
        default=str(REPORT_ROOT),
        help="Report root for registry/latest pointers; defaults to reports/rag_eval.",
    )
    parser.add_argument(
        "--status-jsonl",
        default=str(STATUS_JSONL_PATH),
        help="Status JSONL path for compact actual-RAG run events.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    generated_at = utc_now_iso()
    report_root = Path(args.report_root)
    try:
        run_id = make_actual_rag_run_id(
            Path(args.dataset),
            explicit_run_id=args.run_id,
            generated_at=generated_at,
            report_root=report_root,
        )
    except DatasetSchemaError as exc:
        print(f"dataset schema error: {exc}", file=sys.stderr)
        return 2
    output_dir = Path(args.output_dir) if _clean(args.output_dir) else report_root / run_id
    command = "python -m ai.scripts.rag_actual_eval " + " ".join(sys.argv[1:] if argv is None else argv)
    source_native_units: list[dict[str, Any]] | None = None
    searchunit_units: list[dict[str, Any]] | None = None
    source_native_embedding_provider: Any | None = None
    if args.use_fake_source_native_fixture:
        source_native_units = [
            {
                "unit_id": "fake-source-native-1",
                "source_atom_id": "fake-source-atom-1",
                "doc_id": "fake-source-doc",
                "chunk_id": "fake-source-chunk",
                "source_family": "TEXT",
                "title": "Fake Source Native",
                "section": "Evidence",
                "text": "needle answer appears in source native evidence",
                "surface": "source_atom",
                "text_sha256": _sha256_text("needle answer appears in source native evidence"),
                "metadata": {"fixture": "fake_source_native"},
            }
        ]
        searchunit_units = [
            {
                "payload_id": "fake-searchunit-1",
                "search_unit_id": "fake-searchunit-chunk",
                "search_view_id": "fake-searchunit-view",
                "source_family": "TEXT",
                "bm25_text": "irrelevant legacy projection filler",
                "embedding_text": "irrelevant legacy projection filler",
                "metadata": {"source_safe_id": "fake-searchunit-doc", "source_text_sha256": "fake-searchunit-sha"},
            }
        ]
        source_native_embedding_provider = FakeDeterministicEmbeddingProvider()
    try:
        comparison_summary, comparison_target = resolve_comparison_summary(
            args.compare_to,
            dataset_path=Path(args.dataset),
            report_root=report_root,
        )
        bundle = run_eval_from_paths(
            dataset_path=Path(args.dataset),
            output_dir=output_dir,
            context_jsonl_path=Path(args.context_jsonl) if _clean(args.context_jsonl) else None,
            index=args.index,
            top_k=args.top_k,
            run_id=run_id,
            command=command,
            judge_mode=args.judge_mode,
            judge_backend=args.judge_backend,
            judge_base_url=args.judge_base_url,
            judge_model=args.judge_model,
            judge_threshold=args.judge_threshold,
            judge_timeout_seconds=args.judge_timeout_seconds,
            judge_max_tokens=args.judge_max_tokens,
            skip_judge_endpoint_check=args.skip_judge_endpoint_check,
            provisional_require_citations=args.provisional_require_citations,
            generated_at=generated_at,
            comparison_summary=comparison_summary,
            comparison_target=comparison_target or args.compare_to,
            report_root=report_root,
            status_jsonl_path=Path(args.status_jsonl),
            append_registry=args.append_registry,
            write_latest=args.write_latest,
            resolve_expected_evidence=args.resolve_expected_evidence,
            evidence_resolution_scope=args.evidence_resolution_scope,
            max_evidence_candidates=args.max_evidence_candidates,
            min_evidence_resolution_score=args.min_evidence_resolution_score,
            count_medium_evidence_resolution=args.count_medium_evidence_resolution,
            write_evidence_mapping_packet=args.write_evidence_mapping_packet,
            write_human_review_packet=args.write_human_review_packet,
            output_mode=args.output_mode,
            retrieval_surface=args.retrieval_surface,
            retrieval_backend=args.retrieval_backend,
            source_native_units=source_native_units,
            searchunit_units=searchunit_units,
            source_native_embedding_provider=source_native_embedding_provider,
            retrieval_adapter=FakeVectorAdapter(requested_backend=args.retrieval_backend)
            if args.use_fake_vector_adapter
            else None,
        )
    except DatasetSchemaError as exc:
        print(f"dataset schema error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"execution error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "completed",
                "run_id": run_id,
                "report_json": _artifact_path(bundle.summary, "report_json"),
                "summary_json": bundle.summary_path.as_posix(),
                "items_jsonl": _artifact_path(bundle.summary, "items_jsonl"),
                "markdown_report": _artifact_path(bundle.summary, "markdown_report"),
                "human_review_packet_csv": _artifact_path(bundle.summary, "human_review_packet_csv"),
                "evidence_mapping_review_packet_csv": _artifact_path(bundle.summary, "evidence_mapping_review_packet_csv"),
                "evidence_mapping_review_packet_jsonl": _artifact_path(bundle.summary, "evidence_mapping_review_packet_jsonl"),
                "evidence_mapping_review_packet_md": _artifact_path(bundle.summary, "evidence_mapping_review_packet_md"),
                "evidence_mapping_packet_summary_json": _artifact_path(bundle.summary, "evidence_mapping_packet_summary_json"),
                "retrieval_backend": bundle.summary.get("retrieval_backend"),
                "retrieval_surface": bundle.summary.get("retrieval_surface"),
                "retrieval_surface_decision": bundle.summary.get("retrieval_surface_decision"),
                "registry_jsonl": (report_root / REGISTRY_FILENAME).as_posix() if args.append_registry else "",
                "latest_json": (report_root / "latest.json").as_posix() if args.write_latest else "",
                "status_jsonl": str(Path(args.status_jsonl)) if args.append_registry else "",
                "comparison_target": (bundle.summary.get("comparison") or {}).get("target_run_id")
                if isinstance(bundle.summary.get("comparison"), Mapping)
                else None,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
