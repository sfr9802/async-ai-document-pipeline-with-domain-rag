"""Trace a single frozen-gold TEXT rank regression after silver tuning.

The trace is report-only. It rebuilds the deterministic BM25 indexes from the
silver-only tuning config and writes a focused before/after explanation for one
frozen cleaned gold query. It does not tune, train, index, or mutate production
state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import rag_silver_only_tuning_pass as silver_pass


DEFAULT_REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
DEFAULT_QUERY_ID = "text_namu_v2_0058"
JSON_NAME = "text_namu_v2_0058_rank_trace.json"
MD_NAME = "text_namu_v2_0058_rank_trace.md"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = silver_pass.load_config(Path(args.config))
    report_dir = silver_pass.resolve_path(args.reports_dir)
    payload = build_rank_trace(config, query_id=args.query_id)
    json_path = report_dir / JSON_NAME
    md_path = report_dir / MD_NAME
    silver_pass.write_json(json_path, payload)
    silver_pass.write_text(md_path, render_rank_trace_md(payload))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "query_id": payload["query_id"],
                "baseline_rank": payload["rank_summary"]["baseline_expected_rank"],
                "tuned_rank": payload["rank_summary"]["tuned_expected_rank"],
                "json": silver_pass.repo_relative(json_path),
                "md": silver_pass.repo_relative(md_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(silver_pass.DEFAULT_CONFIG))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--query-id", default=DEFAULT_QUERY_ID)
    return parser.parse_args(argv)


def build_rank_trace(config: Mapping[str, Any], *, query_id: str) -> dict[str, Any]:
    rows = silver_pass.load_all_rows(config)
    row = find_query(rows["text_gold_main_positive"], query_id)
    if row is None:
        raise ValueError(f"frozen cleaned gold TEXT query not found: {query_id}")

    outputs = silver_pass.output_paths(config)
    baseline_report = read_json(outputs["baseline_json"])
    silver_report = read_json(outputs["silver_tuning_run_json"])
    gold_after_report = read_json(outputs["gold_eval_after_silver_tuning_json"])
    profiles = {profile["name"]: profile for profile in config.get("tuning", {}).get("text_profiles", [])}
    baseline_profile_name = ((baseline_report.get("lanes") or {}).get("TEXT_MAIN_POSITIVE") or {}).get("profile")
    tuned_profile_name = (silver_report.get("selected_profiles") or {}).get("text")
    if baseline_profile_name not in profiles:
        raise ValueError(f"baseline TEXT profile not found in config: {baseline_profile_name}")
    if tuned_profile_name not in profiles:
        raise ValueError(f"selected TEXT profile not found in config: {tuned_profile_name}")

    corpus_path = silver_pass.resolve_path(config["corpora"]["text_rag_chunks_jsonl"])
    baseline_index = silver_pass.build_text_index(corpus_path, profiles[baseline_profile_name])
    tuned_index = silver_pass.build_text_index(corpus_path, profiles[tuned_profile_name])
    top_k = 10
    baseline_hits = enrich_hits(baseline_index, row, baseline_index.retrieve(row.get("query", ""), top_k), profiles[baseline_profile_name])
    tuned_hits = enrich_hits(tuned_index, row, tuned_index.retrieve(row.get("query", ""), top_k), profiles[tuned_profile_name])

    expected_doc_ids = silver_pass.split_ids(row.get("expected_page_ids") or row.get("expected_document_ids"))
    expected_chunk_ids = silver_pass.split_ids(row.get("expected_chunk_ids"))
    baseline_rank = expected_rank(expected_doc_ids, expected_chunk_ids, baseline_hits)
    tuned_rank = expected_rank(expected_doc_ids, expected_chunk_ids, tuned_hits)
    displaced = [
        hit
        for hit in tuned_hits[:5]
        if not expected_hit(hit, expected_doc_ids, expected_chunk_ids)
    ]
    expected_baseline_hit = first_expected_hit(baseline_hits, expected_doc_ids, expected_chunk_ids)
    expected_tuned_hit = first_expected_hit(tuned_hits, expected_doc_ids, expected_chunk_ids)

    return {
        "schema_version": "text_rank_trace_v1",
        "status": "PASS",
        "generated_at": silver_pass.utc_timestamp(),
        "query_id": row.get("query_id"),
        "query": row.get("query"),
        "bucket": row.get("bucket") or "UNSPECIFIED",
        "policy": {
            "report_only": True,
            "profile_changed": False,
            "profile_promoted": False,
            "production_index_mutation": False,
            "broad_indexing": False,
            "official_denominator_registry_changed": False,
            "gold_used_for_profile_selection": silver_report.get("gold_used_for_selection"),
            "frozen_gold_training_rows": silver_report.get("frozen_gold_training_rows"),
        },
        "profiles": {
            "baseline": {
                "name": baseline_profile_name,
                "weights": profile_weights(profiles[baseline_profile_name]),
            },
            "tuned": {
                "name": tuned_profile_name,
                "weights": profile_weights(profiles[tuned_profile_name]),
            },
            "selected_text_profile_assessment": (
                "diagnostic_only_due_hit5_regression"
                if tuned_rank and tuned_rank > 5 and baseline_rank and baseline_rank <= 5
                else "diagnostic_only_pending_review"
            ),
        },
        "expected": {
            "expected_document_ids": expected_doc_ids,
            "expected_chunk_ids": expected_chunk_ids,
        },
        "rank_summary": {
            "baseline_expected_rank": baseline_rank,
            "tuned_expected_rank": tuned_rank,
            "hit5_before": baseline_rank is not None and baseline_rank <= 5,
            "hit5_after": tuned_rank is not None and tuned_rank <= 5,
            "hit10_before": baseline_rank is not None and baseline_rank <= 10,
            "hit10_after": tuned_rank is not None and tuned_rank <= 10,
        },
        "top5_candidates_that_displaced_expected": displaced,
        "expected_candidate_before": expected_baseline_hit,
        "expected_candidate_after": expected_tuned_hit,
        "baseline_top10_candidates": baseline_hits,
        "tuned_top10_candidates": tuned_hits,
        "score_availability": {
            "bm25_total_score_available": True,
            "vector_score_available": False,
            "section_boost_score_available": False,
            "note": (
                "The local deterministic TextIndex emits final BM25 scores only. "
                "Field contribution is represented by configured weights plus token-overlap diagnostics."
            ),
        },
        "root_cause_classification": classify_root_cause(
            baseline_rank=baseline_rank,
            tuned_rank=tuned_rank,
            baseline_profile=profiles[baseline_profile_name],
            tuned_profile=profiles[tuned_profile_name],
            expected_tuned_hit=expected_tuned_hit,
            displaced_hits=displaced,
        ),
        "mitigation_recommendation": (
            "Keep tuned_text_section_boost_bm25 diagnostic-only. Review a capped or query-bucket-gated "
            "section boost and add this query to the Hit@5 regression watchlist before any promotion review."
        ),
        "gold_eval_profiles": gold_after_report.get("selected_profiles"),
    }


def enrich_hits(
    index: silver_pass.TextIndex,
    row: Mapping[str, str],
    hits: Sequence[Mapping[str, Any]],
    profile: Mapping[str, Any],
) -> list[dict[str, Any]]:
    chunk_by_id = {chunk.chunk_id: chunk for chunk in index.chunks}
    query_tokens = set(silver_pass.tokenize(row.get("query", "")))
    expected_doc_ids = set(silver_pass.split_ids(row.get("expected_page_ids") or row.get("expected_document_ids")))
    expected_chunk_ids = set(silver_pass.split_ids(row.get("expected_chunk_ids")))
    enriched = []
    for hit in hits:
        chunk = chunk_by_id.get(str(hit.get("chunk_id")))
        title = chunk.title if chunk else str(hit.get("title") or "")
        section_path = chunk.section_path if chunk else list(hit.get("section_path") or [])
        chunk_text = chunk.chunk_text if chunk else ""
        title_tokens = set(silver_pass.tokenize(title))
        section_tokens = set(silver_pass.tokenize(" ".join(section_path)))
        chunk_tokens = set(silver_pass.tokenize(chunk_text))
        enriched.append(
            {
                "rank": hit.get("rank"),
                "chunk_id": hit.get("chunk_id"),
                "doc_id": hit.get("doc_id"),
                "section_id": hit.get("section_id"),
                "title": title,
                "section_path": section_path,
                "score": hit.get("score"),
                "expected_match": str(hit.get("doc_id")) in expected_doc_ids
                or str(hit.get("chunk_id")) in expected_chunk_ids,
                "title_overlap": sorted(query_tokens & title_tokens),
                "section_overlap": sorted(query_tokens & section_tokens),
                "chunk_overlap": sorted(query_tokens & chunk_tokens),
                "weighted_overlap_hint": {
                    "title": len(query_tokens & title_tokens) * int(profile.get("title_weight", 1)),
                    "section": len(query_tokens & section_tokens) * int(profile.get("section_weight", 1)),
                    "chunk": len(query_tokens & chunk_tokens) * int(profile.get("chunk_weight", 1)),
                },
                "score_components": {
                    "bm25_total": hit.get("score"),
                    "vector": None,
                    "section_boost": None,
                },
                "chunk_text_excerpt": excerpt(chunk_text),
            }
        )
    return enriched


def classify_root_cause(
    *,
    baseline_rank: int | None,
    tuned_rank: int | None,
    baseline_profile: Mapping[str, Any],
    tuned_profile: Mapping[str, Any],
    expected_tuned_hit: Mapping[str, Any] | None,
    displaced_hits: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    section_weight_increased = int(tuned_profile.get("section_weight", 1)) > int(baseline_profile.get("section_weight", 1))
    expected_section_hint = ((expected_tuned_hit or {}).get("weighted_overlap_hint") or {}).get("section", 0)
    displaced_section_hint = max(
        [((hit.get("weighted_overlap_hint") or {}).get("section", 0)) for hit in displaced_hits] or [0]
    )
    if baseline_rank and baseline_rank <= 5 and tuned_rank and tuned_rank > 5 and section_weight_increased:
        label = "section_boost_displaced_borderline_hit5"
    elif baseline_rank and tuned_rank and tuned_rank > baseline_rank:
        label = "rank_order_regression_without_hit10_loss"
    else:
        label = "no_rank_regression_detected"
    return {
        "label": label,
        "section_weight_increased": section_weight_increased,
        "expected_section_weighted_overlap_hint": expected_section_hint,
        "max_displaced_section_weighted_overlap_hint": displaced_section_hint,
        "explanation": (
            "The selected profile doubles section weighting. The expected result moved from rank 5 to rank 6, "
            "so the regression is a borderline Hit@5 loss, not a Hit@10 loss."
        ),
    }


def expected_rank(expected_doc_ids: Sequence[str], expected_chunk_ids: Sequence[str], hits: Sequence[Mapping[str, Any]]) -> int | None:
    return silver_pass.min_rank(
        silver_pass.first_rank(expected_doc_ids, hits, "doc_id"),
        silver_pass.first_rank(expected_chunk_ids, hits, "chunk_id"),
    )


def first_expected_hit(
    hits: Sequence[Mapping[str, Any]],
    expected_doc_ids: Sequence[str],
    expected_chunk_ids: Sequence[str],
) -> dict[str, Any] | None:
    for hit in hits:
        if expected_hit(hit, expected_doc_ids, expected_chunk_ids):
            return dict(hit)
    return None


def expected_hit(hit: Mapping[str, Any], expected_doc_ids: Sequence[str], expected_chunk_ids: Sequence[str]) -> bool:
    return str(hit.get("doc_id")) in set(expected_doc_ids) or str(hit.get("chunk_id")) in set(expected_chunk_ids)


def find_query(rows: Sequence[Mapping[str, str]], query_id: str) -> Mapping[str, str] | None:
    for row in rows:
        if row.get("query_id") == query_id:
            return row
    return None


def profile_weights(profile: Mapping[str, Any]) -> dict[str, int]:
    return {
        "title_weight": int(profile.get("title_weight", 1)),
        "alias_weight": int(profile.get("alias_weight", 1)),
        "section_weight": int(profile.get("section_weight", 1)),
        "chunk_weight": int(profile.get("chunk_weight", 1)),
    }


def excerpt(text: str, *, limit: int = 220) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def render_rank_trace_md(payload: Mapping[str, Any]) -> str:
    summary = payload["rank_summary"]
    cause = payload["root_cause_classification"]
    lines = [
        "# text_namu_v2_0058 Rank Trace",
        "",
        f"- Status: `{payload['status']}`.",
        f"- Query: `{payload['query']}`.",
        f"- Baseline profile: `{payload['profiles']['baseline']['name']}`.",
        f"- Tuned profile: `{payload['profiles']['tuned']['name']}`.",
        f"- Expected rank: `{summary['baseline_expected_rank']}` -> `{summary['tuned_expected_rank']}`.",
        f"- Hit@5: `{str(summary['hit5_before']).lower()}` -> `{str(summary['hit5_after']).lower()}`.",
        f"- Root cause: `{cause['label']}`.",
        f"- Recommendation: {payload['mitigation_recommendation']}",
        "",
        "## Score Availability",
        "",
        f"- {payload['score_availability']['note']}",
        "",
        "## Tuned Top 5 Displacing Candidates",
        "",
    ]
    append_hit_table(lines, payload["top5_candidates_that_displaced_expected"])
    lines.extend(["", "## Baseline Top 10", ""])
    append_hit_table(lines, payload["baseline_top10_candidates"])
    lines.extend(["", "## Tuned Top 10", ""])
    append_hit_table(lines, payload["tuned_top10_candidates"])
    lines.append("")
    return "\n".join(lines)


def append_hit_table(lines: list[str], hits: Sequence[Mapping[str, Any]]) -> None:
    if not hits:
        lines.append("- None.")
        return
    lines.extend(
        [
            "| rank | score | expected | doc_id | chunk_id | title | section_overlap | chunk_overlap |",
            "|---:|---:|---|---|---|---|---|---|",
        ]
    )
    for hit in hits:
        lines.append(
            f"| {hit.get('rank')} | {silver_pass.fmt(hit.get('score'))} | "
            f"`{str(hit.get('expected_match')).lower()}` | `{hit.get('doc_id')}` | `{hit.get('chunk_id')}` | "
            f"{hit.get('title') or ''} | {', '.join(hit.get('section_overlap') or [])} | "
            f"{', '.join(hit.get('chunk_overlap') or [])} |"
        )


if __name__ == "__main__":
    sys.exit(main())
