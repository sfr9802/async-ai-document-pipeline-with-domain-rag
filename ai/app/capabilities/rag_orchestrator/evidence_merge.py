"""Deterministic Evidence merge helpers for the RAG orchestrator POC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal, Mapping

from app.capabilities.rag_orchestrator.evidence import Evidence
from app.capabilities.rag_orchestrator.tools import ToolResult

MergeStrategy = Literal["rank_rrf_then_type_balance", "input_order"]


@dataclass(frozen=True)
class EvidenceMergeResult:
    merged_evidence: tuple[Evidence, ...]
    dedupe_stats: Mapping[str, int]
    source_type_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "merged_evidence": [item.to_dict() for item in self.merged_evidence],
            "dedupe_stats": dict(self.dedupe_stats),
            "source_type_counts": dict(self.source_type_counts),
        }


def evidence_merge_tool(
    evidence_batches: Iterable[ToolResult],
    *,
    strategy: MergeStrategy = "rank_rrf_then_type_balance",
    max_evidence: int = 12,
) -> EvidenceMergeResult:
    """Merge verified Evidence from tool results.

    The merge is intentionally deterministic. It never reads rejected evidence
    from tool results and never promotes unverified evidence to answer handoff.
    """

    if max_evidence < 1:
        raise ValueError("max_evidence must be positive")
    if strategy not in ("rank_rrf_then_type_balance", "input_order"):
        raise ValueError(f"unsupported evidence merge strategy: {strategy}")

    candidates = _collect_candidates(evidence_batches)
    ordered = (
        _rank_rrf_then_type_balance(candidates)
        if strategy == "rank_rrf_then_type_balance"
        else candidates
    )

    merged: list[Evidence] = []
    stats = {
        "candidate_count": len(candidates),
        "merged_count": 0,
        "skipped_unverified_count": 0,
        "deduped_by_search_unit_id_count": 0,
        "deduped_by_chunk_id_count": 0,
        "deduped_by_source_unit_count": 0,
        "truncated_count": 0,
    }
    seen_search_units: set[str] = set()
    seen_chunks: set[str] = set()
    seen_source_units: set[tuple[str, str]] = set()

    for evidence in ordered:
        if evidence.verification_status != "verified":
            stats["skipped_unverified_count"] += 1
            continue

        if evidence.search_unit_id and evidence.search_unit_id in seen_search_units:
            stats["deduped_by_search_unit_id_count"] += 1
            continue
        if evidence.chunk_id and evidence.chunk_id in seen_chunks:
            stats["deduped_by_chunk_id_count"] += 1
            continue
        source_unit_key = _source_unit_key(evidence)
        if source_unit_key and source_unit_key in seen_source_units:
            stats["deduped_by_source_unit_count"] += 1
            continue

        if len(merged) >= max_evidence:
            stats["truncated_count"] += 1
            continue

        merged.append(evidence)
        if evidence.search_unit_id:
            seen_search_units.add(evidence.search_unit_id)
        if evidence.chunk_id:
            seen_chunks.add(evidence.chunk_id)
        if source_unit_key:
            seen_source_units.add(source_unit_key)

    stats["merged_count"] = len(merged)
    return EvidenceMergeResult(
        merged_evidence=tuple(merged),
        dedupe_stats=stats,
        source_type_counts=_source_type_counts(merged),
    )


def _collect_candidates(evidence_batches: Iterable[Any]) -> list[Evidence]:
    candidates: list[Evidence] = []
    for batch in evidence_batches:
        if not isinstance(batch, ToolResult):
            raise TypeError("evidence_merge_tool accepts ToolResult batches only")
        for item in batch.evidence:
            candidates.append(item)
    return candidates


def _rank_rrf_then_type_balance(candidates: list[Evidence]) -> list[Evidence]:
    indexed = list(enumerate(candidates))
    indexed.sort(
        key=lambda pair: (
            -_rrf_score(pair[1]),
            _source_type_order(pair[1].source_file_type),
            pair[1].rank,
            pair[0],
        )
    )
    return [item for _, item in indexed]


def _rrf_score(evidence: Evidence) -> float:
    final_score = evidence.scores.get("final") if evidence.scores else None
    if isinstance(final_score, (int, float)):
        return float(final_score)
    return 1.0 / (60.0 + max(evidence.rank, 1))


def _source_type_order(source_file_type: str) -> int:
    order = {"PDF": 0, "SPREADSHEET": 1, "TEXT": 2}
    return order.get(source_file_type, 99)


def _source_unit_key(evidence: Evidence) -> tuple[str, str] | None:
    if not evidence.source_file_id or not evidence.unit_key:
        return None
    return (evidence.source_file_id, evidence.unit_key)


def _source_type_counts(evidence_items: Iterable[Evidence]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for evidence in evidence_items:
        counts[evidence.source_file_type] = counts.get(evidence.source_file_type, 0) + 1
    return counts
