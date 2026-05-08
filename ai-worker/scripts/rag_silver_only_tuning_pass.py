"""Run an explicit silver-only diagnostic tuning pass for cleaned RAG lanes.

The runner is intentionally report-only. It reads the silver training CSVs,
selects deterministic retrieval profiles using only silver rows, then evaluates
the selected profiles on frozen cleaned gold candidates. It does not mutate
official denominators, production indexes, or runtime settings.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
DEFAULT_CONFIG = AI_WORKER_ROOT / "eval" / "configs" / "silver_only_tuning_config.yaml"


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    doc_id: str
    section_id: str
    title: str
    section_path: list[str]
    aliases: list[str]
    chunk_text: str
    search_text: str


@dataclass(frozen=True)
class TextIndex:
    profile_name: str
    chunks: list[ChunkRecord]
    postings: dict[str, list[tuple[int, int]]]
    doc_lengths: list[int]
    avg_doc_length: float

    def retrieve(self, query: str, top_k: int) -> list[dict[str, Any]]:
        terms = Counter(tokenize(query))
        if not terms:
            return []
        scores: dict[int, float] = defaultdict(float)
        k1 = 1.5
        b = 0.75
        for token, query_tf in terms.items():
            postings = self.postings.get(token)
            if not postings:
                continue
            df = len(postings)
            idf = math.log(1.0 + (len(self.chunks) - df + 0.5) / (df + 0.5))
            query_boost = 1.0 + min(query_tf - 1, 3) * 0.15
            for doc_index, term_frequency in postings:
                doc_length = max(self.doc_lengths[doc_index], 1)
                denom = term_frequency + k1 * (1 - b + b * doc_length / self.avg_doc_length)
                scores[doc_index] += idf * ((term_frequency * (k1 + 1)) / denom) * query_boost
        ranked = sorted(
            ((self.chunks[index], score) for index, score in scores.items()),
            key=lambda item: (-item[1], item[0].title, item[0].chunk_id),
        )
        return [
            {
                "rank": rank,
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "section_id": chunk.section_id,
                "title": chunk.title,
                "section_path": chunk.section_path,
                "score": round(float(score), 6),
            }
            for rank, (chunk, score) in enumerate(ranked[:top_k], start=1)
        ]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(Path(args.config))
    result = run_pass(config)
    selected = (result.get("silver_tuning") or {}).get("selected_profiles") or {}
    print(
        json.dumps(
            {
                "status": result["status"],
                "selected_text_profile": selected.get("text"),
                "selected_pdf_file_lookup_profile": selected.get("pdf_file_lookup"),
                "baseline_report": result["outputs"]["baseline_json"],
                "silver_tuning_report": result["outputs"]["silver_tuning_run_json"],
                "gold_eval_report": result["outputs"]["gold_eval_after_silver_tuning_json"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"] == "PASS" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    return parser.parse_args(argv)


def run_pass(config: Mapping[str, Any]) -> dict[str, Any]:
    guard = validate_guards(config)
    outputs = output_paths(config)
    if guard["status"] != "PASS":
        failure = {
            "schema_version": "silver_only_tuning_pass_v1",
            "status": "FAIL",
            "generated_at": utc_timestamp(),
            "guard": guard,
            "policy": config.get("policy", {}),
            "outputs": {key: repo_relative(path) for key, path in outputs.items()},
        }
        write_json(outputs["baseline_json"], failure)
        write_text(outputs["baseline_md"], render_guard_failure(failure))
        return failure

    top_k = int(config.get("tuning", {}).get("top_k", 10))
    rows = load_all_rows(config)
    pdf_eval_pool = build_pdf_candidate_pool(rows)
    pdf_selection_pool = build_pdf_candidate_pool_from_row_lists(
        [
            rows["silver_pdf_file_lookup_positive"],
            rows["silver_pdf_file_lookup_hard_negative"],
        ]
    )
    pdf_selection_pool_audit = build_pdf_selection_pool_audit(rows, pdf_selection_pool)
    xlsx_status = load_xlsx_status(config)

    text_indexes = {
        profile["name"]: build_text_index(
            resolve_path(config["corpora"]["text_rag_chunks_jsonl"]),
            profile,
        )
        for profile in config.get("tuning", {}).get("text_profiles", [])
    }
    if not text_indexes:
        raise ValueError("config.tuning.text_profiles must not be empty")

    pdf_profiles = list(config.get("tuning", {}).get("pdf_file_lookup_profiles", []))
    if not pdf_profiles:
        raise ValueError("config.tuning.pdf_file_lookup_profiles must not be empty")

    baseline_text_name = next(iter(text_indexes))
    baseline_pdf_name = pdf_profiles[0]["name"]

    baseline = {
        "schema_version": "silver_only_tuning_baseline_v1",
        "status": "PASS",
        "generated_at": utc_timestamp(),
        "policy": policy_payload(config),
        "guard": guard,
        "standard_command_note": standard_command_note(),
        "lanes": {
            "TEXT_MAIN_POSITIVE": evaluate_text_positive(
                rows["text_gold_main_positive"],
                text_indexes[baseline_text_name],
                top_k=top_k,
                lane="TEXT_MAIN_POSITIVE",
            ),
            "TEXT_ABSTAIN_DIAGNOSTIC": evaluate_text_abstain(
                rows["text_gold_abstain_diagnostic"],
                text_indexes[baseline_text_name],
                top_k=top_k,
                lane="TEXT_ABSTAIN_DIAGNOSTIC",
            ),
            "PDF_FILE_LOOKUP": evaluate_pdf_positive(
                rows["pdf_file_lookup_gold_positive"],
                pdf_eval_pool,
                pdf_profiles[0],
                top_k=top_k,
                lane="PDF_FILE_LOOKUP",
            ),
            "PDF_FILE_LOOKUP_DIAGNOSTIC": evaluate_pdf_diagnostic(
                rows["pdf_file_lookup_diagnostic"],
                pdf_eval_pool,
                pdf_profiles[0],
                top_k=top_k,
                lane="PDF_FILE_LOOKUP_DIAGNOSTIC",
            ),
            "XLSX": xlsx_status,
        },
    }

    text_candidates = []
    for profile_name, index in text_indexes.items():
        pos = evaluate_text_positive(rows["silver_text_positive"], index, top_k=top_k, lane="SILVER_TEXT_POSITIVE")
        hneg = evaluate_text_hard_negative(rows["silver_text_hard_negative"], index, top_k=top_k)
        abstain = evaluate_text_abstain(rows["silver_text_abstain_diagnostic"], index, top_k=top_k, lane="SILVER_TEXT_ABSTAIN_DIAGNOSTIC")
        score = objective_score(config, pos["metrics"], hneg["metrics"])
        text_candidates.append(
            {
                "profile": profile_name,
                "objective_score": score,
                "positive": pos["metrics"],
                "hard_negative": hneg["metrics"],
                "abstain_diagnostic": abstain["metrics"],
            }
        )
    text_candidates.sort(key=lambda item: (-item["objective_score"], item["profile"]))
    selected_text_name = text_candidates[0]["profile"]

    pdf_candidates = []
    for profile in pdf_profiles:
        pos = evaluate_pdf_positive(
            rows["silver_pdf_file_lookup_positive"],
            pdf_selection_pool,
            profile,
            top_k=top_k,
            lane="SILVER_PDF_FILE_LOOKUP_POSITIVE",
        )
        hneg = evaluate_pdf_hard_negative(
            rows["silver_pdf_file_lookup_hard_negative"],
            pdf_selection_pool,
            profile,
            top_k=top_k,
        )
        score = objective_score(config, pos["metrics"], hneg["metrics"])
        pdf_candidates.append(
            {
                "profile": profile["name"],
                "objective_score": score,
                "positive": pos["metrics"],
                "hard_negative": hneg["metrics"],
            }
        )
    pdf_candidates.sort(key=lambda item: (-item["objective_score"], item["profile"]))
    selected_pdf_name = pdf_candidates[0]["profile"]
    selected_pdf_profile = next(profile for profile in pdf_profiles if profile["name"] == selected_pdf_name)

    silver_tuning = {
        "schema_version": "silver_only_tuning_run_v1",
        "status": "PASS",
        "generated_at": utc_timestamp(),
        "selection_data": "silver_only",
        "gold_used_for_selection": False,
        "frozen_gold_training_rows": 0,
        "selected_profiles": {
            "text": selected_text_name,
            "pdf_file_lookup": selected_pdf_name,
        },
        "pdf_file_lookup_selection_pool": pdf_selection_pool_audit,
        "text_candidates": text_candidates,
        "pdf_file_lookup_candidates": pdf_candidates,
        "guard": guard,
    }

    gold_after = {
        "schema_version": "gold_eval_after_silver_tuning_v1",
        "status": "PASS",
        "generated_at": utc_timestamp(),
        "policy": policy_payload(config),
        "selected_profiles": dict(silver_tuning["selected_profiles"]),
        "gold_used_for_selection": False,
        "lanes": {
            "TEXT_MAIN_POSITIVE": evaluate_text_positive(
                rows["text_gold_main_positive"],
                text_indexes[selected_text_name],
                top_k=top_k,
                lane="TEXT_MAIN_POSITIVE",
            ),
            "TEXT_ABSTAIN_DIAGNOSTIC": evaluate_text_abstain(
                rows["text_gold_abstain_diagnostic"],
                text_indexes[selected_text_name],
                top_k=top_k,
                lane="TEXT_ABSTAIN_DIAGNOSTIC",
            ),
            "PDF_FILE_LOOKUP": evaluate_pdf_positive(
                rows["pdf_file_lookup_gold_positive"],
                pdf_eval_pool,
                selected_pdf_profile,
                top_k=top_k,
                lane="PDF_FILE_LOOKUP",
            ),
            "PDF_FILE_LOOKUP_DIAGNOSTIC": evaluate_pdf_diagnostic(
                rows["pdf_file_lookup_diagnostic"],
                pdf_eval_pool,
                selected_pdf_profile,
                top_k=top_k,
                lane="PDF_FILE_LOOKUP_DIAGNOSTIC",
            ),
            "XLSX": xlsx_status,
        },
    }

    delta = build_delta_report(baseline, gold_after)
    result = {
        "schema_version": "silver_only_tuning_pass_v1",
        "status": "PASS",
        "generated_at": utc_timestamp(),
        "outputs": {key: repo_relative(path) for key, path in outputs.items()},
        "baseline": baseline,
        "silver_tuning": silver_tuning,
        "gold_eval_after_silver_tuning": gold_after,
        "delta": delta,
    }
    write_json(outputs["baseline_json"], baseline)
    write_text(outputs["baseline_md"], render_baseline_md(baseline))
    write_json(outputs["silver_tuning_run_json"], silver_tuning)
    write_text(outputs["silver_tuning_run_md"], render_silver_tuning_md(silver_tuning))
    write_json(outputs["gold_eval_after_silver_tuning_json"], gold_after)
    write_text(outputs["gold_eval_after_silver_tuning_md"], render_gold_eval_md(gold_after))
    write_text(outputs["before_after_metric_delta_md"], render_delta_md(delta))
    return result


def load_config(path: Path) -> dict[str, Any]:
    resolved = resolve_path(path)
    data = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"config must be a mapping: {resolved}")
    return data


def load_all_rows(config: Mapping[str, Any]) -> dict[str, list[dict[str, str]]]:
    silver = config["input_silver_train_files"]
    gold = config["frozen_gold_eval_files"]
    return {
        "silver_text_positive": read_csv(resolve_path(silver["text_positive"])),
        "silver_text_hard_negative": read_csv(resolve_path(silver["text_hard_negative"])),
        "silver_text_abstain_diagnostic": read_csv(resolve_path(silver["text_abstain_diagnostic"])),
        "silver_pdf_file_lookup_positive": read_csv(resolve_path(silver["pdf_file_lookup_positive"])),
        "silver_pdf_file_lookup_hard_negative": read_csv(resolve_path(silver["pdf_file_lookup_hard_negative"])),
        "text_gold_main_positive": read_csv(resolve_path(gold["text_main_positive"])),
        "text_gold_abstain_diagnostic": read_csv(resolve_path(gold["text_abstain_diagnostic"])),
        "pdf_file_lookup_gold_positive": read_csv(resolve_path(gold["pdf_file_lookup_positive"])),
        "pdf_file_lookup_diagnostic": read_csv(resolve_path(gold["pdf_file_lookup_diagnostic"])),
    }


def validate_guards(config: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    guard_cfg = config.get("leakage_guard_settings", {})
    manifest_path = resolve_path(guard_cfg["denominator_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    leakage = (((manifest.get("silver") or {}).get("leakage")) or {})
    expected = {
        "status": guard_cfg.get("require_silver_leakage_status", "PASS"),
        "query_text_overlap_count": int(guard_cfg.get("require_query_overlap_count", 0)),
        "query_id_overlap_count": int(guard_cfg.get("require_query_id_overlap_count", 0)),
        "source_query_id_overlap_count": int(guard_cfg.get("require_source_query_id_overlap_count", 0)),
        "expected_id_overlap_count": int(guard_cfg.get("require_expected_id_overlap_count", 0)),
    }
    for key, expected_value in expected.items():
        if leakage.get(key) != expected_value:
            failures.append(f"silver leakage {key}={leakage.get(key)!r}, expected {expected_value!r}")
    if (manifest.get("gold_frozen") or {}).get("official_denominator_registry_changed") is not False:
        failures.append("denominator manifest reports official registry changed")

    rows = load_all_rows(config)
    silver_rows = [
        *rows["silver_text_positive"],
        *rows["silver_text_hard_negative"],
        *rows["silver_text_abstain_diagnostic"],
        *rows["silver_pdf_file_lookup_positive"],
        *rows["silver_pdf_file_lookup_hard_negative"],
    ]
    gold_rows = [
        *rows["text_gold_main_positive"],
        *rows["text_gold_abstain_diagnostic"],
        *rows["pdf_file_lookup_gold_positive"],
        *rows["pdf_file_lookup_diagnostic"],
    ]
    if guard_cfg.get("require_silver_official_gold_false", True):
        bad = [row.get("query_id", "<missing>") for row in silver_rows if clean(row.get("official_gold")) != "false"]
        if bad:
            failures.append(f"silver rows with official_gold != false: {bad[:10]}")
    if guard_cfg.get("require_frozen_gold_official_gold_false", True):
        bad = [row.get("query_id", "<missing>") for row in gold_rows if clean(row.get("official_gold")) != "false"]
        if bad:
            failures.append(f"frozen cleaned gold candidates with official_gold != false: {bad[:10]}")
    pdf_policy_bad = [
        row.get("query_id", "<missing>")
        for row in [*rows["silver_pdf_file_lookup_positive"], *rows["silver_pdf_file_lookup_hard_negative"]]
        if row.get("retrieval_lane") != "pdf_file_lookup"
        or row.get("expected_evidence_policy") != "EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY"
    ]
    if pdf_policy_bad:
        failures.append(f"PDF FILE lookup silver policy mismatch: {pdf_policy_bad}")
    return {
        "status": "FAIL" if failures else "PASS",
        "manifest": repo_relative(manifest_path),
        "failures": failures,
        "checks": {
            "silver_leakage": leakage,
            "official_denominator_registry_changed": (manifest.get("gold_frozen") or {}).get(
                "official_denominator_registry_changed"
            ),
            "silver_row_count": len(silver_rows),
            "frozen_cleaned_gold_candidate_row_count": len(gold_rows),
        },
    }


def build_text_index(path: Path, profile: Mapping[str, Any]) -> TextIndex:
    chunks: list[ChunkRecord] = []
    postings_by_token: dict[str, dict[int, int]] = defaultdict(dict)
    doc_lengths: list[int] = []
    for record in iter_jsonl(path):
        chunk = chunk_record_from_json(record, profile)
        index = len(chunks)
        chunks.append(chunk)
        counts = Counter(tokenize(chunk.search_text))
        doc_lengths.append(sum(counts.values()))
        for token, count in counts.items():
            postings_by_token[token][index] = count
    postings = {token: sorted(entries.items()) for token, entries in postings_by_token.items()}
    avg_doc_length = mean(length for length in doc_lengths if length) or 1.0
    return TextIndex(
        profile_name=str(profile["name"]),
        chunks=chunks,
        postings=postings,
        doc_lengths=doc_lengths,
        avg_doc_length=avg_doc_length,
    )


def chunk_record_from_json(record: Mapping[str, Any], profile: Mapping[str, Any]) -> ChunkRecord:
    title = first_non_empty(record.get("retrieval_title"), record.get("display_title"), record.get("title"))
    aliases = [clean(alias) for alias in record.get("aliases") or [] if clean(alias)]
    section_path = [clean(part) for part in record.get("section_path") or [] if clean(part)]
    chunk_text = clean(record.get("chunk_text"))
    parts: list[str] = []
    parts.extend([title] * int(profile.get("title_weight", 1)))
    for alias in aliases:
        parts.extend([alias] * int(profile.get("alias_weight", 1)))
    parts.extend([" ".join(section_path)] * int(profile.get("section_weight", 1)))
    parts.extend([chunk_text] * int(profile.get("chunk_weight", 1)))
    return ChunkRecord(
        chunk_id=clean(record.get("chunk_id")),
        doc_id=clean(record.get("doc_id") or record.get("page_id")),
        section_id=clean(record.get("section_id")),
        title=title,
        section_path=section_path,
        aliases=aliases,
        chunk_text=chunk_text,
        search_text=" ".join(part for part in parts if part),
    )


def evaluate_text_positive(
    rows: list[dict[str, str]],
    index: TextIndex,
    *,
    top_k: int,
    lane: str,
) -> dict[str, Any]:
    query_results = []
    ranks: list[int | None] = []
    recalls: list[float] = []
    failure_reasons: Counter[str] = Counter()
    for row in rows:
        hits = index.retrieve(row.get("query", ""), top_k)
        expected_doc_ids = split_ids(row.get("expected_page_ids") or row.get("expected_document_ids"))
        expected_chunk_ids = split_ids(row.get("expected_chunk_ids"))
        rank = min_rank(first_rank(expected_doc_ids, hits, "doc_id"), first_rank(expected_chunk_ids, hits, "chunk_id"))
        ranks.append(rank)
        recalls.append(recall_at(expected_doc_ids, [hit["doc_id"] for hit in hits]))
        reason = text_failure_reason(rank, expected_doc_ids, expected_chunk_ids, hits)
        if reason:
            failure_reasons[reason] += 1
        query_results.append(
            {
                "query_id": row.get("query_id"),
                "rank": rank,
                "hit_at_10": rank is not None and rank <= 10,
                "expected_document_ids": expected_doc_ids,
                "expected_chunk_ids": expected_chunk_ids,
                "top_ids": [hit["doc_id"] for hit in hits[:3]],
                "failure_reason": reason,
            }
        )
    return {
        "lane": lane,
        "profile": index.profile_name,
        "metrics": metric_payload(ranks, recalls) | {
            "false_positive_patterns": dict(sorted(failure_reasons.items())),
        },
        "sample_failures": [row for row in query_results if row["failure_reason"]][:10],
    }


def evaluate_text_hard_negative(
    rows: list[dict[str, str]],
    index: TextIndex,
    *,
    top_k: int,
) -> dict[str, Any]:
    outcomes = []
    for row in rows:
        hits = index.retrieve(row.get("query", ""), top_k)
        negative_ids = split_ids(row.get("expected_page_ids") or row.get("expected_document_ids"))
        positive_ids = split_ids(row.get("positive_expected_document_ids"))
        negative_rank = first_rank(negative_ids, hits, "doc_id")
        positive_rank = first_rank(positive_ids, hits, "doc_id")
        confused = negative_rank is not None and (positive_rank is None or negative_rank < positive_rank)
        outcomes.append(
            {
                "query_id": row.get("query_id"),
                "negative_rank": negative_rank,
                "positive_rank": positive_rank,
                "confused": confused,
                "negative_top1": negative_rank == 1,
            }
        )
    return {
        "lane": "SILVER_TEXT_HARD_NEGATIVE",
        "profile": index.profile_name,
        "metrics": hard_negative_metrics(outcomes),
        "sample_confusions": [row for row in outcomes if row["confused"]][:10],
    }


def evaluate_text_abstain(
    rows: list[dict[str, str]],
    index: TextIndex,
    *,
    top_k: int,
    lane: str,
) -> dict[str, Any]:
    outcomes = []
    for row in rows:
        hits = index.retrieve(row.get("query", ""), top_k)
        expected_ids = split_ids(row.get("expected_page_ids") or row.get("expected_document_ids"))
        expected_rank = first_rank(expected_ids, hits, "doc_id") if expected_ids else None
        outcomes.append(
            {
                "query_id": row.get("query_id"),
                "result_count": len(hits),
                "expected_rank": expected_rank,
                "top_id": hits[0]["doc_id"] if hits else None,
            }
        )
    count = len(outcomes)
    return {
        "lane": lane,
        "profile": index.profile_name,
        "metrics": {
            "row_count": count,
            "official_denominator_count": 0,
            "any_result_rate": mean(item["result_count"] > 0 for item in outcomes),
            "diagnostic_expected_hit@10": mean(
                item["expected_rank"] is not None and item["expected_rank"] <= 10 for item in outcomes
            ),
            "abstain_retrieval_behavior": "diagnostic_only_not_main_positive",
        },
        "sample_rows": outcomes[:10],
    }


def build_pdf_candidate_pool(rows: Mapping[str, list[dict[str, str]]]) -> list[str]:
    return build_pdf_candidate_pool_from_row_lists(rows.values())


def build_pdf_candidate_pool_from_row_lists(row_lists: Iterable[list[dict[str, str]]]) -> list[str]:
    names: set[str] = set()
    for row_list in row_lists:
        for row in row_list:
            for key in ("expected_file_name", "source_file_name", "positive_expected_file_name"):
                value = clean(row.get(key))
                if value:
                    names.add(value)
    return sorted(names)


def build_pdf_document_version_pool_from_row_lists(row_lists: Iterable[list[dict[str, str]]]) -> list[str]:
    document_version_ids: set[str] = set()
    for row_list in row_lists:
        for row in row_list:
            for key in ("expected_document_version_id", "positive_expected_document_version_id"):
                value = clean(row.get(key))
                if value:
                    document_version_ids.add(value)
    return sorted(document_version_ids)


def build_pdf_selection_pool_audit(rows: Mapping[str, list[dict[str, str]]], selection_pool: list[str]) -> dict[str, Any]:
    silver_pool = set(selection_pool)
    frozen_gold_pool = set(
        build_pdf_candidate_pool_from_row_lists(
            [
                rows["pdf_file_lookup_gold_positive"],
                rows["pdf_file_lookup_diagnostic"],
            ]
        )
    )
    silver_docv_pool = set(
        build_pdf_document_version_pool_from_row_lists(
            [
                rows["silver_pdf_file_lookup_positive"],
                rows["silver_pdf_file_lookup_hard_negative"],
            ]
        )
    )
    frozen_gold_docv_pool = set(
        build_pdf_document_version_pool_from_row_lists(
            [
                rows["pdf_file_lookup_gold_positive"],
                rows["pdf_file_lookup_diagnostic"],
            ]
        )
    )
    return {
        "source": "silver_pdf_file_lookup_train_rows_only",
        "frozen_gold_eval_rows_used": False,
        "candidate_count": len(selection_pool),
        "frozen_gold_only_identity_used_count": 0,
        "frozen_gold_only_identity_excluded_count": len(frozen_gold_pool - silver_pool),
        "frozen_gold_identity_in_selection_pool_count": len(frozen_gold_pool & silver_pool),
        "selection_pool_document_version_ids": sorted(silver_docv_pool),
        "frozen_gold_document_version_id_in_selection_pool_count": len(frozen_gold_docv_pool & silver_docv_pool),
        "frozen_gold_only_document_version_id_used_count": 0,
        "frozen_gold_only_document_version_id_excluded_count": len(frozen_gold_docv_pool - silver_docv_pool),
        "selection_pool_file_names": selection_pool,
    }


def evaluate_pdf_positive(
    rows: list[dict[str, str]],
    pool: list[str],
    profile: Mapping[str, Any],
    *,
    top_k: int,
    lane: str,
) -> dict[str, Any]:
    ranks: list[int | None] = []
    recalls: list[float] = []
    failures: Counter[str] = Counter()
    query_results = []
    for row in rows:
        hits = retrieve_pdf_files(row.get("query", ""), pool, profile, top_k)
        expected = clean(row.get("expected_file_name") or row.get("source_file_name"))
        rank = first_file_rank(expected, hits)
        ranks.append(rank)
        recalls.append(1.0 if rank is not None and rank <= top_k else 0.0)
        reason = None if rank is not None else "expected_file_identity_not_found"
        if reason:
            failures[reason] += 1
        query_results.append(
            {
                "query_id": row.get("query_id"),
                "rank": rank,
                "expected_file_name": expected,
                "top_files": [hit["file_name"] for hit in hits[:3]],
                "failure_reason": reason,
            }
        )
    return {
        "lane": lane,
        "profile": profile["name"],
        "metrics": metric_payload(ranks, recalls) | {
            "file_identity_confusion_rate": mean(
                bool(item["top_files"] and item["top_files"][0] != item["expected_file_name"]) for item in query_results
            ),
            "false_positive_patterns": dict(sorted(failures.items())),
            "pdf_file_lookup_semantics": "file_identity_only",
            "page_bbox_table_row_column_value_success_claimed": False,
        },
        "sample_failures": [row for row in query_results if row["failure_reason"]][:10],
    }


def evaluate_pdf_hard_negative(
    rows: list[dict[str, str]],
    pool: list[str],
    profile: Mapping[str, Any],
    *,
    top_k: int,
) -> dict[str, Any]:
    outcomes = []
    for row in rows:
        hits = retrieve_pdf_files(row.get("query", ""), pool, profile, top_k)
        negative_file = clean(row.get("expected_file_name"))
        positive_file = clean(row.get("positive_expected_file_name"))
        negative_rank = first_file_rank(negative_file, hits)
        positive_rank = first_file_rank(positive_file, hits)
        confused = negative_rank is not None and (positive_rank is None or negative_rank < positive_rank)
        outcomes.append(
            {
                "query_id": row.get("query_id"),
                "negative_rank": negative_rank,
                "positive_rank": positive_rank,
                "confused": confused,
                "negative_top1": negative_rank == 1,
            }
        )
    return {
        "lane": "SILVER_PDF_FILE_LOOKUP_HARD_NEGATIVE",
        "profile": profile["name"],
        "metrics": hard_negative_metrics(outcomes) | {
            "pdf_file_lookup_semantics": "file_identity_only",
        },
        "sample_confusions": [row for row in outcomes if row["confused"]][:10],
    }


def evaluate_pdf_diagnostic(
    rows: list[dict[str, str]],
    pool: list[str],
    profile: Mapping[str, Any],
    *,
    top_k: int,
    lane: str,
) -> dict[str, Any]:
    positive = evaluate_pdf_positive(rows, pool, profile, top_k=top_k, lane=lane)
    positive["metrics"]["official_denominator_count"] = 0
    positive["metrics"]["diagnostic_only"] = True
    return positive


def retrieve_pdf_files(
    query: str,
    pool: list[str],
    profile: Mapping[str, Any],
    top_k: int,
) -> list[dict[str, Any]]:
    query_features = file_features(query)
    ranked = []
    for file_name in pool:
        features = file_features(file_name)
        token_overlap = len(query_features["tokens"] & features["tokens"])
        score = float(profile.get("lexical_weight", 1.0)) * token_overlap
        score += float(profile.get("year_weight", 1.0)) * len(query_features["years"] & features["years"])
        score += float(profile.get("month_weight", 1.0)) * len(query_features["months"] & features["months"])
        score += float(profile.get("family_weight", 1.0)) * len(query_features["families"] & features["families"])
        ranked.append({"file_name": file_name, "score": round(score, 6)})
    ranked.sort(key=lambda item: (-item["score"], item["file_name"]))
    return [
        {"rank": rank, **item}
        for rank, item in enumerate(ranked[:top_k], start=1)
    ]


def file_features(value: str) -> dict[str, set[str]]:
    text = clean(value).lower()
    tokens = set(tokenize(text))
    years = set(re.findall(r"20\d{2}", text))
    month_suffix = chr(0xC6D4)
    day_suffix = chr(0xC77C)
    months = set(
        re.findall(
            rf"(?<!\d)(0?[1-9]|1[0-2])(?={month_suffix}|\+|_|-|\)|{day_suffix}|\s|$)",
            text,
        )
    )
    date_match = re.findall(r"(20\d{2})(0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])", text)
    for year, month in date_match:
        years.add(year)
        months.add(str(int(month)))
        months.add(month)
    months.update(str(int(month)) for month in list(months) if month.isdigit())
    families: set[str] = set()
    if "종합" in text or "total" in text:
        families.add("total")
    if "저압" in text or "low" in text or "law" in text:
        families.add("low")
    if "고압" in text or "high" in text:
        families.add("high")
    if "전기요금" in text or "요금표" in text:
        families.add("electricity_rate")
    return {"tokens": tokens, "years": years, "months": months, "families": families}


def metric_payload(ranks: Sequence[int | None], recalls: Sequence[float]) -> dict[str, Any]:
    return {
        "row_count": len(ranks),
        "Hit@1": hit_at(ranks, 1),
        "Hit@3": hit_at(ranks, 3),
        "Hit@5": hit_at(ranks, 5),
        "Hit@10": hit_at(ranks, 10),
        "MRR@10": mrr_at(ranks, 10),
        "recall@10": mean(recalls),
    }


def hard_negative_metrics(outcomes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(outcomes),
        "hard_negative_confusion_rate": mean(item["confused"] for item in outcomes),
        "hard_negative_top1_rate": mean(item["negative_top1"] for item in outcomes),
        "positive_identity_recovery_rate": mean(
            item["positive_rank"] is not None and item["positive_rank"] <= 10 for item in outcomes
        ),
    }


def objective_score(
    config: Mapping[str, Any],
    positive_metrics: Mapping[str, Any],
    hard_negative_metrics_payload: Mapping[str, Any],
) -> float:
    objective = config.get("tuning", {}).get("objective", {})
    return round(
        float(objective.get("hit_at_10_weight", 0.45)) * float(positive_metrics.get("Hit@10", 0.0))
        + float(objective.get("mrr_at_10_weight", 0.35)) * float(positive_metrics.get("MRR@10", 0.0))
        + float(objective.get("recall_at_10_weight", 0.20)) * float(positive_metrics.get("recall@10", 0.0))
        - float(objective.get("hard_negative_confusion_penalty", 0.25))
        * float(hard_negative_metrics_payload.get("hard_negative_confusion_rate", 0.0)),
        6,
    )


def build_delta_report(baseline: Mapping[str, Any], gold_after: Mapping[str, Any]) -> dict[str, Any]:
    lanes = {}
    for lane_name in ("TEXT_MAIN_POSITIVE", "TEXT_ABSTAIN_DIAGNOSTIC", "PDF_FILE_LOOKUP", "PDF_FILE_LOOKUP_DIAGNOSTIC"):
        before_metrics = ((baseline.get("lanes") or {}).get(lane_name) or {}).get("metrics") or {}
        after_metrics = ((gold_after.get("lanes") or {}).get(lane_name) or {}).get("metrics") or {}
        lane_delta = {}
        for metric in ("Hit@1", "Hit@3", "Hit@5", "Hit@10", "MRR@10", "recall@10", "file_identity_confusion_rate"):
            if metric in before_metrics or metric in after_metrics:
                before = before_metrics.get(metric)
                after = after_metrics.get(metric)
                lane_delta[metric] = {
                    "before": before,
                    "after": after,
                    "delta": round(float(after or 0.0) - float(before or 0.0), 6),
                }
        lanes[lane_name] = lane_delta
    return {
        "schema_version": "before_after_metric_delta_v1",
        "status": "PASS",
        "generated_at": utc_timestamp(),
        "baseline_profiles": {
            "text": ((baseline.get("lanes") or {}).get("TEXT_MAIN_POSITIVE") or {}).get("profile"),
            "pdf_file_lookup": ((baseline.get("lanes") or {}).get("PDF_FILE_LOOKUP") or {}).get("profile"),
        },
        "after_profiles": gold_after.get("selected_profiles"),
        "lanes": lanes,
    }


def load_xlsx_status(config: Mapping[str, Any]) -> dict[str, Any]:
    xlsx = config.get("approved_xlsx_strict_wrapper", {})
    report_json = resolve_path(xlsx.get("report_json", ""))
    if xlsx.get("enabled_if_report_exists") and report_json.exists():
        payload = json.loads(report_json.read_text(encoding="utf-8"))
        return {
            "lane": "XLSX",
            "status": "REPORT_ONLY_INCLUDED",
            "source_report": repo_relative(report_json),
            "metrics": {
                "row_count": payload.get("silver_row_count") or payload.get("row_count"),
                "promotion_evidence": payload.get("promotion_evidence", False),
                "official_denominator_changed": payload.get("official_denominator_changed", False),
            },
        }
    return {
        "lane": "XLSX",
        "status": "SKIPPED_NO_APPROVED_STRICT_WRAPPER_REPORT",
        "metrics": {"row_count": 0},
    }


def output_paths(config: Mapping[str, Any]) -> dict[str, Path]:
    outputs = config["output_report_paths"]
    return {key: resolve_path(value) for key, value in outputs.items()}


def policy_payload(config: Mapping[str, Any]) -> dict[str, Any]:
    policy = dict(config.get("policy") or {})
    policy["lanes_kept_separate"] = list((config.get("lanes") or {}).keys())
    return policy


def standard_command_note() -> str:
    return (
        "phase7_human_gold_tune.py remains the older gold-50/silver-500 CLI. "
        "This pass uses the explicit silver_only_tuning_config.yaml so frozen "
        "cleaned gold candidates are evaluated only after silver profile selection."
    )


def render_guard_failure(payload: Mapping[str, Any]) -> str:
    lines = ["# Silver-Only Tuning Baseline Failure", "", "- Status: `FAIL`.", "", "## Guard Failures", ""]
    for failure in payload.get("guard", {}).get("failures", []):
        lines.append(f"- {failure}")
    lines.append("")
    return "\n".join(lines)


def render_baseline_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Silver Tuning Baseline Report",
        "",
        f"- Status: `{payload['status']}`.",
        "- Role: baseline before silver-only diagnostic profile selection.",
        "- Official denominator registry changed: `false`.",
        "- PDF FILE lookup semantics: file identity only.",
        "",
        "## Lane Metrics",
        "",
    ]
    append_lane_table(lines, payload["lanes"])
    lines.extend(["", "## Notes", "", f"- {payload['standard_command_note']}", ""])
    return "\n".join(lines)


def render_silver_tuning_md(payload: Mapping[str, Any]) -> str:
    pdf_pool = payload.get("pdf_file_lookup_selection_pool") or {}
    lines = [
        "# Silver Tuning Run Report",
        "",
        f"- Status: `{payload['status']}`.",
        "- Selection data: `silver_only`.",
        "- Frozen gold rows used for training: `0`.",
        f"- Selected TEXT profile: `{payload['selected_profiles']['text']}`.",
        f"- Selected PDF FILE lookup profile: `{payload['selected_profiles']['pdf_file_lookup']}`.",
        f"- PDF FILE lookup selection pool: `{pdf_pool.get('source', 'unknown')}`; frozen gold eval rows used: `{str(pdf_pool.get('frozen_gold_eval_rows_used')).lower()}`.",
        f"- PDF FILE lookup selection pool candidate count: `{pdf_pool.get('candidate_count')}`; frozen-gold-only identities used: `{pdf_pool.get('frozen_gold_only_identity_used_count')}`.",
        f"- PDF FILE lookup frozen-gold document_version_id values used: `{pdf_pool.get('frozen_gold_only_document_version_id_used_count', 0)}`.",
        "",
        "## TEXT Candidates",
        "",
        "| profile | objective | Hit@10 | MRR@10 | recall@10 | hard_negative_confusion_rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in payload["text_candidates"]:
        pos = item["positive"]
        hneg = item["hard_negative"]
        lines.append(
            f"| `{item['profile']}` | {fmt(item['objective_score'])} | {fmt(pos.get('Hit@10'))} | "
            f"{fmt(pos.get('MRR@10'))} | {fmt(pos.get('recall@10'))} | "
            f"{fmt(hneg.get('hard_negative_confusion_rate'))} |"
        )
    lines.extend(["", "## PDF FILE Lookup Candidates", "", "| profile | objective | Hit@10 | MRR@10 | recall@10 | hard_negative_confusion_rate |", "|---|---:|---:|---:|---:|---:|"])
    for item in payload["pdf_file_lookup_candidates"]:
        pos = item["positive"]
        hneg = item["hard_negative"]
        lines.append(
            f"| `{item['profile']}` | {fmt(item['objective_score'])} | {fmt(pos.get('Hit@10'))} | "
            f"{fmt(pos.get('MRR@10'))} | {fmt(pos.get('recall@10'))} | "
            f"{fmt(hneg.get('hard_negative_confusion_rate'))} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_gold_eval_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Gold Eval After Silver Tuning Report",
        "",
        f"- Status: `{payload['status']}`.",
        "- Evaluation data: frozen cleaned gold candidates only.",
        "- Training data: `0` frozen gold rows.",
        f"- Selected TEXT profile: `{payload['selected_profiles']['text']}`.",
        f"- Selected PDF FILE lookup profile: `{payload['selected_profiles']['pdf_file_lookup']}`.",
        "",
        "## Lane Metrics",
        "",
    ]
    append_lane_table(lines, payload["lanes"])
    lines.append("")
    return "\n".join(lines)


def render_delta_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Before/After Metric Delta",
        "",
        f"- Status: `{payload['status']}`.",
        f"- Baseline TEXT profile: `{payload['baseline_profiles']['text']}`.",
        f"- After TEXT profile: `{payload['after_profiles']['text']}`.",
        f"- Baseline PDF FILE lookup profile: `{payload['baseline_profiles']['pdf_file_lookup']}`.",
        f"- After PDF FILE lookup profile: `{payload['after_profiles']['pdf_file_lookup']}`.",
        "",
    ]
    for lane, metrics in payload["lanes"].items():
        lines.extend([f"## {lane}", "", "| metric | before | after | delta |", "|---|---:|---:|---:|"])
        for metric, values in metrics.items():
            lines.append(f"| {metric} | {fmt(values['before'])} | {fmt(values['after'])} | {fmt(values['delta'])} |")
        lines.append("")
    return "\n".join(lines)


def append_lane_table(lines: list[str], lanes: Mapping[str, Any]) -> None:
    lines.extend(["| lane | profile/status | rows | Hit@10 | MRR@10 | recall@10 | notes |", "|---|---|---:|---:|---:|---:|---|"])
    for lane, payload in lanes.items():
        metrics = payload.get("metrics", {})
        profile = payload.get("profile") or payload.get("status", "")
        row_count = metrics.get("row_count", "")
        row_count_cell = "" if row_count is None else row_count
        notes = []
        if metrics.get("hard_negative_confusion_rate") is not None:
            notes.append(f"hard_negative_confusion_rate={fmt(metrics.get('hard_negative_confusion_rate'))}")
        if metrics.get("file_identity_confusion_rate") is not None:
            notes.append(f"file_identity_confusion_rate={fmt(metrics.get('file_identity_confusion_rate'))}")
        if metrics.get("abstain_retrieval_behavior"):
            notes.append(str(metrics.get("abstain_retrieval_behavior")))
        if metrics.get("pdf_file_lookup_semantics"):
            notes.append(str(metrics.get("pdf_file_lookup_semantics")))
        lines.append(
            f"| {lane} | `{profile}` | {row_count_cell} | {fmt(metrics.get('Hit@10'))} | "
            f"{fmt(metrics.get('MRR@10'))} | {fmt(metrics.get('recall@10'))} | {'; '.join(notes)} |"
        )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def iter_jsonl(path: Path) -> Iterable[Mapping[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, Mapping):
                raise ValueError(f"{path}: line {line_no} is not an object")
            yield row


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def resolve_path(value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai-worker":
        return REPO_ROOT / path
    return AI_WORKER_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def split_ids(value: Any) -> list[str]:
    return [clean(part) for part in re.split(r"[|;]", clean(value)) if clean(part)]


def first_rank(expected_ids: Sequence[str], hits: Sequence[Mapping[str, Any]], field: str) -> int | None:
    expected = set(expected_ids)
    if not expected:
        return None
    for hit in hits:
        if clean(hit.get(field)) in expected:
            return int(hit["rank"])
    return None


def first_file_rank(expected_file: str, hits: Sequence[Mapping[str, Any]]) -> int | None:
    if not expected_file:
        return None
    for hit in hits:
        if clean(hit.get("file_name")) == expected_file:
            return int(hit["rank"])
    return None


def min_rank(*ranks: int | None) -> int | None:
    present = [rank for rank in ranks if rank is not None]
    return min(present) if present else None


def hit_at(ranks: Sequence[int | None], k: int) -> float:
    return mean(rank is not None and rank <= k for rank in ranks)


def mrr_at(ranks: Sequence[int | None], k: int) -> float:
    return mean((1.0 / rank) if rank is not None and rank <= k else 0.0 for rank in ranks)


def recall_at(expected: Sequence[str], observed: Sequence[str]) -> float:
    if not expected:
        return 0.0
    return len(set(expected) & set(observed)) / len(set(expected))


def mean(values: Iterable[Any]) -> float:
    items = [float(value) for value in values]
    return sum(items) / len(items) if items else 0.0


def text_failure_reason(
    rank: int | None,
    expected_doc_ids: Sequence[str],
    expected_chunk_ids: Sequence[str],
    hits: Sequence[Mapping[str, Any]],
) -> str | None:
    if rank is not None:
        return None
    if not hits:
        return "empty_result"
    if expected_doc_ids and not first_rank(expected_doc_ids, hits, "doc_id"):
        return "expected_source_missing"
    if expected_chunk_ids and not first_rank(expected_chunk_ids, hits, "chunk_id"):
        return "expected_chunk_missing"
    return "expected_evidence_missing"


def tokenize(text: str) -> list[str]:
    return re.findall(r"[0-9a-zA-Z가-힣]+", clean(text).lower())


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = clean(value)
        if text:
            return text
    return ""


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def fmt(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        return f"{float(value):.4f}"
    return str(value)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    sys.exit(main())
