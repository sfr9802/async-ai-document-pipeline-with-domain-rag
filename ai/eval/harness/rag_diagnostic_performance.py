"""Reusable performance and tuning summaries for RAG diagnostics."""

from __future__ import annotations

import math
import statistics
from typing import Any, Mapping, Sequence


def safe_ratio(numerator: float | int | None, denominator: float | int | None, *, digits: int = 4) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(float(numerator) / float(denominator), digits)


def percentile_nearest_rank(values: Sequence[float | int], percentile: int) -> float | None:
    if not values:
        return None
    if percentile < 0 or percentile > 100:
        raise ValueError("percentile must be between 0 and 100")
    ordered = sorted(float(value) for value in values)
    if percentile == 0:
        return ordered[0]
    rank = math.ceil((percentile / 100) * len(ordered))
    return ordered[max(rank - 1, 0)]


def candidate_count_stats(rows: Sequence[Mapping[str, Any]], *, field: str) -> dict[str, Any]:
    values = [int(row[field]) for row in rows if row.get(field) is not None]
    if not values:
        return {
            "row_count": len(rows),
            "nonzero_count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "p50": None,
            "p95": None,
        }
    return {
        "row_count": len(rows),
        "nonzero_count": sum(1 for value in values if value > 0),
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.fmean(values), 4),
        "p50": percentile_nearest_rank(values, 50),
        "p95": percentile_nearest_rank(values, 95),
    }


def latency_summary(rows: Sequence[Mapping[str, Any]], *, field: str) -> dict[str, Any]:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    if not values:
        return {
            "row_count": len(rows),
            "measured_count": 0,
            "missing_count": len(rows),
            "min_ms": None,
            "max_ms": None,
            "mean_ms": None,
            "p50_ms": None,
            "p95_ms": None,
        }
    return {
        "row_count": len(rows),
        "measured_count": len(values),
        "missing_count": len(rows) - len(values),
        "min_ms": min(values),
        "max_ms": max(values),
        "mean_ms": round(statistics.fmean(values), 4),
        "p50_ms": percentile_nearest_rank(values, 50),
        "p95_ms": percentile_nearest_rank(values, 95),
    }
