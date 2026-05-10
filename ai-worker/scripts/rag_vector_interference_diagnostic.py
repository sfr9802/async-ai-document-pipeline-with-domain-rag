"""Run diagnostic in-memory vector interference checks for retrieval lanes.

The diagnostic uses a local shadow token-vector scorer. It does not write to
production indexes, production vector stores, or diagnostic namespaces. XLSX
uses metadata-only shadow text so hidden workbook content is not exposed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent

DEFAULT_CONFIG = AI_WORKER_ROOT / "eval" / "configs" / "retrieval_ood_interference_diagnostic.yaml"
DEFAULT_REPORT_JSON = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "vector_interference_diagnostic.json"
DEFAULT_REPORT_MD = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "vector_interference_diagnostic.md"
DEFAULT_BY_QUERY_CSV = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "vector_interference_diagnostic_by_query.csv"

PDF_FILE_IDENTITY_ONLY_POLICY = "file_identity_only_no_content_page_bbox_table_row_column_value_support"
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
MONTH_RE = re.compile(r"(?<!\d)(?:0?[1-9]|1[0-2])(?!\d)")
YEAR_RE = re.compile(r"(?:19|20)\d{2}")

CONDITION_A = "A_baseline_corpus_only"
CONDITION_B = "B_baseline_plus_safe_distractor_corpus"
CONDITION_C = "C_baseline_plus_same_lane_hard_negatives"
CONDITION_D = "D_baseline_plus_cross_lane_distractors"
CONDITION_E = "E_baseline_plus_near_duplicate_metadata_file_name_distractors"

BY_QUERY_FIELDS = [
    "lane",
    "condition",
    "query_id",
    "query_hash",
    "hit_rank",
    "hit_at_1",
    "hit_at_3",
    "hit_at_5",
    "hit_at_10",
    "mrr_at_10",
    "rank_loss",
    "score_margin",
    "score_margin_collapse",
    "false_positive_top10_count",
    "false_positive_increase",
    "source_document_confusion",
    "lane_confusion",
    "xlsx_table_header_confusion",
    "pdf_file_identity_confusion",
    "citation_location_degradation",
    "vector_interference_loss",
]


@dataclass(frozen=True)
class QueryCase:
    lane: str
    query_id: str
    query_text: str
    expected_keys: frozenset[str]
    expected_family: str
    expected_file_identity: str
    template_shape: str
    parser_version: str


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    lane: str
    source_document_id: str
    document_family: str
    source_artifact_id: str
    parser_version: str
    file_identity: str
    template_shape: str
    text: str
    citation_available: bool
    location_available: bool
    table_metadata_available: bool
    header_metadata_available: bool
    is_synthetic_distractor: bool = False
    distractor_kind: str = ""

    @property
    def match_keys(self) -> set[str]:
        return {
            value
            for value in [
                self.candidate_id,
                self.source_document_id,
                self.source_artifact_id,
                self.file_identity,
                self.document_family,
            ]
            if value
        }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(resolve_path(args.config))
    report, by_query_rows = run_diagnostic(config)
    report_json = resolve_path(args.output_json or config["outputs"].get("interference_report_json") or DEFAULT_REPORT_JSON)
    report_md = resolve_path(args.output_md or config["outputs"].get("interference_report_md") or DEFAULT_REPORT_MD)
    by_query_csv = resolve_path(args.by_query_csv or config["outputs"].get("interference_by_query_csv") or DEFAULT_BY_QUERY_CSV)
    report["outputs"] = {
        "interference_report_json": repo_relative(report_json),
        "interference_report_md": repo_relative(report_md),
        "interference_by_query_csv": repo_relative(by_query_csv),
    }
    write_json(report_json, report)
    write_text(report_md, render_markdown(report))
    write_by_query(by_query_csv, by_query_rows)
    print(json.dumps({
        "status": report["status"],
        "worst_lane": report["worst_lane"],
        "by_query_rows": len(by_query_rows),
        "report_json": repo_relative(report_json),
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"PASS", "PASS_WITH_RISK"} else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-md", default=None)
    parser.add_argument("--by-query-csv", default=None)
    return parser.parse_args(argv)


def load_config(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("pyyaml is required")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"config must be a mapping: {path}")
    return raw


def run_diagnostic(config: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    prerequisite = prerequisite_status(config.get("prerequisites", {}))
    lanes_cfg = [lane for lane in config.get("lanes", []) if isinstance(lane, Mapping)]
    cases_by_lane = {lane_name(lane): load_query_cases(lane) for lane in lanes_cfg}
    candidates_by_lane = {
        lane_name(lane): load_candidates_for_lane(lane, cases_by_lane[lane_name(lane)], config)
        for lane in lanes_cfg
    }
    conditions = list(config.get("interference", {}).get("conditions") or [
        CONDITION_A,
        CONDITION_B,
        CONDITION_C,
        CONDITION_D,
        CONDITION_E,
    ])
    by_query: list[dict[str, Any]] = []
    baseline_by_query: dict[tuple[str, str], dict[str, Any]] = {}
    for lane in cases_by_lane:
        for condition in conditions:
            condition_rows = evaluate_condition(
                lane=lane,
                condition=condition,
                cases=cases_by_lane[lane],
                candidates_by_lane=candidates_by_lane,
                config=config,
                baseline_by_query=baseline_by_query,
            )
            by_query.extend(condition_rows)
            if condition == CONDITION_A:
                for row in condition_rows:
                    baseline_by_query[(lane, row["query_id"])] = row

    lane_condition = aggregate_lane_condition(by_query)
    lane_summary = summarize_lanes(lane_condition)
    worst_lane = max(lane_summary.items(), key=lambda item: item[1]["max_vector_interference_loss"])[0] if lane_summary else ""
    status = "PASS_WITH_RISK" if any(v["max_vector_interference_loss"] > 0.20 for v in lane_summary.values()) else "PASS"
    namespace = diagnostic_namespace_metadata(config)
    report = {
        "schema_version": "vector_interference_diagnostic_v1",
        "task": "rag_retrieval_ood_split_and_vector_interference_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        "scope": "diagnostic_report_only",
        "prerequisites": prerequisite,
        "conditions_run": conditions,
        "scoring_method": config.get("interference", {}).get("scoring_method", "in_memory_shadow_token_vector"),
        "diagnostic_namespace": namespace,
        "production_index_mutation": False,
        "vector_write_attempted": False,
        "official_denominator_registry_changed": False,
        "hidden_xlsx_exposed": False,
        "local_llm_used_for_labels_or_judgments": False,
        "optuna_run": False,
        "pdf_file_lookup_policy": PDF_FILE_IDENTITY_ONLY_POLICY,
        "pdf_file_lookup_content_page_bbox_table_row_column_value_claimed": False,
        "diagnostic_source_contract": diagnostic_source_contract(config),
        "near_duplicate_distractor_policy": "metadata_hard_negative_without_query_echo",
        "lane_condition_metrics": lane_condition,
        "lane_summary": lane_summary,
        "worst_lane": worst_lane,
        "vector_interference_loss_by_lane": {
            lane: summary["max_vector_interference_loss"]
            for lane, summary in lane_summary.items()
        },
        "phase3_optuna_diagnostic_tuning": phase3_recommendation(lane_summary),
        "by_query_row_count": len(by_query),
        "content_preview_emitted": False,
    }
    if not all(item["present"] for item in prerequisite.values()):
        report["status"] = "FAIL_CLOSED_PREREQUISITE_MISSING"
        report["phase3_optuna_diagnostic_tuning"]["safe"] = False
        report["phase3_optuna_diagnostic_tuning"]["decision"] = "NOT_SAFE_PREREQUISITE_MISSING"
    elif not namespace["name_has_diagnostic_marker"]:
        report["status"] = "FAIL_UNSAFE_DIAGNOSTIC_NAMESPACE_NAME"
        report["phase3_optuna_diagnostic_tuning"]["safe"] = False
        report["phase3_optuna_diagnostic_tuning"]["decision"] = "NOT_SAFE_UNSAFE_DIAGNOSTIC_NAMESPACE_NAME"
    return report, by_query


def diagnostic_namespace_metadata(config: Mapping[str, Any]) -> dict[str, Any]:
    raw = config.get("diagnostic_namespace", {})
    namespace_cfg = raw if isinstance(raw, Mapping) else {}
    name = str(namespace_cfg.get("name", ""))
    required = bool(namespace_cfg.get("required"))
    name_has_marker = bool((not name and not required) or re.search(r"(diagnostic|sandbox|shadow|temp)", name, re.IGNORECASE))
    return {
        "required": required,
        "namespace_name": name,
        "name_has_diagnostic_marker": name_has_marker,
        "created_or_reused": "not_required_in_memory_shadow_index",
        "cleanup_status": "not_required",
        "production_index_mutation": False,
        "vector_write_attempted": False,
    }


def evaluate_condition(
    *,
    lane: str,
    condition: str,
    cases: Sequence[QueryCase],
    candidates_by_lane: Mapping[str, Sequence[Candidate]],
    config: Mapping[str, Any],
    baseline_by_query: Mapping[tuple[str, str], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base_candidates = list(candidates_by_lane.get(lane, []))
    for case in cases:
        candidates = candidates_for_condition(case, lane, condition, base_candidates, candidates_by_lane, config)
        result = evaluate_query(case, condition, candidates)
        baseline = baseline_by_query.get((lane, case.query_id))
        if baseline:
            result["rank_loss"] = rank_loss(baseline.get("hit_rank"), result.get("hit_rank"))
            result["score_margin_collapse"] = max(0.0, round(float(baseline.get("score_margin", 0.0)) - float(result["score_margin"]), 6))
            result["false_positive_increase"] = max(0, int(result["false_positive_top10_count"]) - int(baseline.get("false_positive_top10_count", 0)))
            result["citation_location_degradation"] = int(
                bool(baseline.get("citation_location_degradation") == 0)
                and bool(result["citation_location_degradation"])
            )
            result["vector_interference_loss"] = vector_loss(result)
        else:
            result["rank_loss"] = 0
            result["score_margin_collapse"] = 0.0
            result["false_positive_increase"] = 0
            result["vector_interference_loss"] = 0.0
        rows.append(result)
    return rows


def candidates_for_condition(
    case: QueryCase,
    lane: str,
    condition: str,
    base_candidates: Sequence[Candidate],
    candidates_by_lane: Mapping[str, Sequence[Candidate]],
    config: Mapping[str, Any],
) -> list[Candidate]:
    limits = config.get("interference", {}) if isinstance(config.get("interference"), Mapping) else {}
    candidates = list(base_candidates)
    if condition == CONDITION_A:
        return candidates
    if condition == CONDITION_B:
        candidates.extend(safe_distractors(case, lane, candidates_by_lane, int(limits.get("max_safe_distractors", 80))))
    elif condition == CONDITION_C:
        candidates.extend(same_lane_hard_negatives(case, lane, base_candidates, int(limits.get("max_same_lane_distractors", 80))))
    elif condition == CONDITION_D:
        candidates.extend(cross_lane_distractors(case, lane, candidates_by_lane, int(limits.get("max_cross_lane_distractors", 120))))
    elif condition == CONDITION_E:
        candidates.extend(near_duplicate_distractors(case, int(limits.get("max_near_duplicate_distractors", 2))))
    return candidates


def evaluate_query(case: QueryCase, condition: str, candidates: Sequence[Candidate]) -> dict[str, Any]:
    query_tokens = token_weights(case.query_text)
    scored: list[tuple[float, Candidate]] = []
    for candidate in candidates:
        score = cosine_score(query_tokens, token_weights(candidate.text))
        if case.expected_family and candidate.document_family == case.expected_family:
            score += 0.08
        if case.expected_file_identity and normalize(candidate.file_identity) == normalize(case.expected_file_identity):
            score += 0.15
        scored.append((round(score, 8), candidate))
    scored.sort(key=lambda item: (-item[0], item[1].candidate_id))
    top10 = scored[:10]
    relevant_ranks = [
        idx + 1
        for idx, (_, candidate) in enumerate(scored[:50])
        if is_relevant(case, candidate)
    ]
    hit_rank = relevant_ranks[0] if relevant_ranks else None
    top_relevant_score = max((score for score, candidate in scored if is_relevant(case, candidate)), default=0.0)
    top_false_score = max((score for score, candidate in top10 if not is_relevant(case, candidate)), default=0.0)
    false_top10 = [candidate for _, candidate in top10 if not is_relevant(case, candidate)]
    top_false = false_top10[0] if false_top10 else None
    source_confusion = int(bool(top_false and top_false.document_family == case.expected_family))
    lane_confusion = int(bool(top_false and top_false.lane != case.lane))
    xlsx_confusion = int(bool(case.lane == "XLSX" and top_false and top_false.template_shape != case.template_shape))
    pdf_identity_confusion = int(bool(
        case.lane == "PDF_FILE_IDENTITY"
        and top_false
        and normalize(top_false.file_identity) != normalize(case.expected_file_identity)
    ))
    citation_degradation = int(bool(hit_rank and hit_rank > 1 and top_false and not top_false.location_available))
    return {
        "lane": case.lane,
        "condition": condition,
        "query_id": case.query_id,
        "query_hash": short_hash(case.query_text),
        "hit_rank": hit_rank or "",
        "hit_at_1": int(bool(hit_rank and hit_rank <= 1)),
        "hit_at_3": int(bool(hit_rank and hit_rank <= 3)),
        "hit_at_5": int(bool(hit_rank and hit_rank <= 5)),
        "hit_at_10": int(bool(hit_rank and hit_rank <= 10)),
        "mrr_at_10": round((1.0 / hit_rank) if hit_rank and hit_rank <= 10 else 0.0, 6),
        "score_margin": round(top_relevant_score - top_false_score, 6),
        "false_positive_top10_count": len(false_top10),
        "source_document_confusion": source_confusion,
        "lane_confusion": lane_confusion,
        "xlsx_table_header_confusion": xlsx_confusion,
        "pdf_file_identity_confusion": pdf_identity_confusion,
        "citation_location_degradation": citation_degradation,
    }


def is_relevant(case: QueryCase, candidate: Candidate) -> bool:
    if case.expected_keys and case.expected_keys.intersection({normalize(v) for v in candidate.match_keys}):
        return True
    if case.expected_file_identity and normalize(candidate.file_identity) == normalize(case.expected_file_identity):
        return True
    return bool(case.expected_family and candidate.document_family == case.expected_family and case.lane != "PDF_FILE_IDENTITY")


def rank_loss(base_rank: Any, rank: Any) -> int:
    base = int(base_rank) if str(base_rank).strip().isdigit() else 11
    current = int(rank) if str(rank).strip().isdigit() else 11
    return max(0, current - base)


def vector_loss(row: Mapping[str, Any]) -> float:
    loss = 0.0
    loss += min(float(row.get("rank_loss", 0)) / 10.0, 1.0) * 0.35
    loss += min(float(row.get("score_margin_collapse", 0.0)), 1.0) * 0.25
    loss += min(float(row.get("false_positive_increase", 0)) / 10.0, 1.0) * 0.20
    loss += 0.10 * int(row.get("lane_confusion", 0))
    loss += 0.10 * int(row.get("pdf_file_identity_confusion", 0) or row.get("xlsx_table_header_confusion", 0))
    return round(loss, 6)


def aggregate_lane_condition(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["lane"]), str(row["condition"]))].append(row)
    out: dict[str, dict[str, Any]] = defaultdict(dict)
    for (lane, condition), items in grouped.items():
        out[lane][condition] = {
            "query_count": len(items),
            "hit_at_1": mean(items, "hit_at_1"),
            "hit_at_3": mean(items, "hit_at_3"),
            "hit_at_5": mean(items, "hit_at_5"),
            "hit_at_10": mean(items, "hit_at_10"),
            "mrr_at_10": mean(items, "mrr_at_10"),
            "mean_rank_loss": mean(items, "rank_loss"),
            "mean_score_margin_collapse": mean(items, "score_margin_collapse"),
            "false_positive_increase": mean(items, "false_positive_increase"),
            "source_document_confusion": mean(items, "source_document_confusion"),
            "lane_confusion": mean(items, "lane_confusion"),
            "xlsx_table_header_confusion": mean(items, "xlsx_table_header_confusion"),
            "pdf_file_identity_confusion": mean(items, "pdf_file_identity_confusion"),
            "citation_location_degradation": mean(items, "citation_location_degradation"),
            "vector_interference_loss": mean(items, "vector_interference_loss"),
        }
    return {lane: dict(conditions) for lane, conditions in sorted(out.items())}


def summarize_lanes(lane_condition: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for lane, conditions in lane_condition.items():
        non_base = {
            condition: metrics
            for condition, metrics in conditions.items()
            if condition != CONDITION_A
        }
        worst_condition = ""
        max_loss = 0.0
        for condition, metrics in non_base.items():
            loss = float(metrics.get("vector_interference_loss", 0.0))
            if loss >= max_loss:
                max_loss = loss
                worst_condition = condition
        out[lane] = {
            "max_vector_interference_loss": round(max_loss, 6),
            "worst_condition": worst_condition,
            "baseline_mrr_at_10": conditions.get(CONDITION_A, {}).get("mrr_at_10", 0.0),
            "worst_condition_mrr_at_10": non_base.get(worst_condition, {}).get("mrr_at_10", 0.0) if worst_condition else 0.0,
        }
    return out


def phase3_recommendation(lane_summary: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    high_loss = [lane for lane, metrics in lane_summary.items() if float(metrics.get("max_vector_interference_loss", 0.0)) > 0.20]
    if high_loss:
        return {
            "safe": False,
            "decision": "NOT_SAFE_FOR_PHASE3_OPTUNA",
            "reason": "high vector interference loss in diagnostic shadow test",
            "blocked_lanes": sorted(high_loss),
        }
    return {
        "safe": True,
        "decision": "SAFE_ONLY_FOR_DIAGNOSTIC_OPTUNA_AFTER_HUMAN_POLICY_REVIEW",
        "reason": "no high-loss lane detected, but tuning remains diagnostic-only and cannot use frozen gold for selection",
        "blocked_lanes": [],
    }


def safe_distractors(case: QueryCase, lane: str, candidates_by_lane: Mapping[str, Sequence[Candidate]], limit: int) -> list[Candidate]:
    pool = [
        c for other_lane, candidates in candidates_by_lane.items()
        if other_lane != lane
        for c in candidates
        if c.document_family != case.expected_family and normalize(c.file_identity) != normalize(case.expected_file_identity)
    ]
    return deterministic_sample(pool, limit, "safe:" + case.query_id)


def same_lane_hard_negatives(case: QueryCase, lane: str, base: Sequence[Candidate], limit: int) -> list[Candidate]:
    pool = [
        c for c in base
        if not is_relevant(case, c)
        and (c.document_family == case.expected_family or c.template_shape == case.template_shape or same_file_family(c.file_identity, case.expected_file_identity))
    ]
    sampled = deterministic_sample(pool or [c for c in base if not is_relevant(case, c)], limit, "same:" + case.query_id)
    return [
        synthetic_candidate(c, suffix=f"same_hard_{i}", kind="same_lane_hard_negative")
        for i, c in enumerate(sampled)
    ]


def cross_lane_distractors(case: QueryCase, lane: str, candidates_by_lane: Mapping[str, Sequence[Candidate]], limit: int) -> list[Candidate]:
    pool = [c for other_lane, candidates in candidates_by_lane.items() if other_lane != lane for c in candidates]
    sampled = deterministic_sample(pool, limit, "cross:" + case.query_id)
    return [synthetic_candidate(c, suffix=f"cross_{i}", kind="cross_lane_distractor") for i, c in enumerate(sampled)]


def near_duplicate_distractors(case: QueryCase, limit: int) -> list[Candidate]:
    out: list[Candidate] = []
    base_identity = case.expected_file_identity or case.expected_family or case.query_id
    for idx in range(max(1, limit)):
        identity = mutate_identity(base_identity, idx)
        out.append(Candidate(
            candidate_id=f"synthetic_near_duplicate:{case.lane}:{case.query_id}:{idx}",
            lane=case.lane,
            source_document_id=f"synthetic-near-doc-{idx}",
            document_family=family_key(identity),
            source_artifact_id=f"synthetic-near-artifact-{idx}",
            parser_version=case.parser_version,
            file_identity=identity,
            template_shape=case.template_shape,
            text=near_duplicate_distractor_text(case, identity),
            citation_available=False,
            location_available=False,
            table_metadata_available=False,
            header_metadata_available=False,
            is_synthetic_distractor=True,
            distractor_kind=near_duplicate_distractor_kind(case),
        ))
    return out


def near_duplicate_distractor_text(case: QueryCase, identity: str) -> str:
    parts = [identity, case.template_shape]
    if case.lane == "TEXT_NAMU":
        return " ".join(part for part in parts if part)
    return " ".join(part for part in [identity, case.template_shape, file_identity_family(identity)] if part)


def near_duplicate_distractor_kind(case: QueryCase) -> str:
    if case.lane == "TEXT_NAMU":
        return "near_duplicate_metadata_hard_negative"
    if case.lane == "PDF_FILE_IDENTITY":
        return "near_duplicate_file_identity_hard_negative"
    return "near_duplicate_metadata_file_name"


def synthetic_candidate(candidate: Candidate, *, suffix: str, kind: str) -> Candidate:
    return Candidate(
        candidate_id=f"{candidate.candidate_id}:synthetic:{suffix}",
        lane=candidate.lane,
        source_document_id=candidate.source_document_id,
        document_family=candidate.document_family,
        source_artifact_id=candidate.source_artifact_id,
        parser_version=candidate.parser_version,
        file_identity=candidate.file_identity,
        template_shape=candidate.template_shape,
        text=candidate.text,
        citation_available=candidate.citation_available,
        location_available=candidate.location_available,
        table_metadata_available=candidate.table_metadata_available,
        header_metadata_available=candidate.header_metadata_available,
        is_synthetic_distractor=True,
        distractor_kind=kind,
    )


def load_query_cases(lane_cfg: Mapping[str, Any]) -> list[QueryCase]:
    lane = lane_name(lane_cfg)
    rows = load_query_rows(lane_cfg)
    return [query_case_from_row(lane, row) for row in rows]


def load_query_rows(lane_cfg: Mapping[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source in lane_cfg.get("query_sources", []) or []:
        path = resolve_path(required_str(source, "path"))
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                rows.append({str(k): clean_text(v) for k, v in row.items() if k is not None})
    return rows


def query_case_from_row(lane: str, row: Mapping[str, str]) -> QueryCase:
    expected = expected_keys(row)
    expected_file = clean_text(row.get("expected_file_name")) or clean_text(row.get("source_file_name"))
    family = family_key(expected_file or first_multi(row.get("expected_document_ids")) or first_multi(row.get("expected_page_ids")))
    return QueryCase(
        lane=lane,
        query_id=clean_text(row.get("query_id")) or short_hash(clean_text(row.get("query"))),
        query_text=clean_text(row.get("query")),
        expected_keys=frozenset(normalize(value) for value in expected if value),
        expected_family=family,
        expected_file_identity=expected_file,
        template_shape=template_shape(row, lane),
        parser_version=clean_text(row.get("parser_version")) or "UNKNOWN",
    )


def load_candidates_for_lane(lane_cfg: Mapping[str, Any], cases: Sequence[QueryCase], config: Mapping[str, Any]) -> list[Candidate]:
    lane = lane_name(lane_cfg)
    if bool(lane_cfg.get("identity_only")):
        return identity_candidates(lane_cfg)
    candidates: list[Candidate] = []
    expected_keys_union = {key for case in cases for key in case.expected_keys}
    max_candidates = int(config.get("interference", {}).get("max_baseline_candidates_per_lane", 2500))
    for source in lane_cfg.get("chunk_sources", []) or []:
        if not isinstance(source, Mapping):
            continue
        if source.get("type") == "jsonl":
            candidates.extend(load_jsonl_candidates(
                lane,
                source,
                expected_keys_union,
                max_candidates=max_candidates,
                metadata_only=bool(source.get("metadata_only_text")),
            ))
        elif source.get("type") == "ragmeta":
            candidates.extend(load_ragmeta_candidates(lane, source, config.get("postgres", {}), metadata_only=bool(source.get("metadata_only_text"))))
    return candidates


def load_jsonl_candidates(
    lane: str,
    source: Mapping[str, Any],
    expected_keys: set[str],
    *,
    max_candidates: int,
    metadata_only: bool,
) -> list[Candidate]:
    path = resolve_path(required_str(source, "path"))
    candidates: list[Candidate] = []
    sampled: list[Candidate] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            candidate = candidate_from_mapping(lane, row, source, metadata_only=metadata_only)
            if candidate.match_keys and {normalize(v) for v in candidate.match_keys}.intersection(expected_keys):
                candidates.append(candidate)
            elif len(sampled) < max_candidates and stable_int(candidate.candidate_id) % 17 == 0:
                sampled.append(candidate)
    candidates.extend(sampled[:max(0, max_candidates - len(candidates))])
    if not candidates:
        candidates = sampled[:max_candidates]
    return dedupe_candidates(candidates)


def load_ragmeta_candidates(
    lane: str,
    source: Mapping[str, Any],
    postgres_cfg: Any,
    *,
    metadata_only: bool,
) -> list[Candidate]:
    try:
        import psycopg2
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("psycopg2 is required for ragmeta candidates") from exc
    if not isinstance(postgres_cfg, Mapping):
        raise ValueError("postgres config must be a mapping")
    conn = psycopg2.connect(
        host=str(postgres_cfg.get("host", "127.0.0.1")),
        port=int(postgres_cfg.get("port", 5433)),
        dbname=str(postgres_cfg.get("database", "aipipeline")),
        user=str(postgres_cfg.get("user", "aipipeline")),
        password=str(postgres_cfg.get("password", "aipipeline_pw")),
        connect_timeout=int(postgres_cfg.get("connect_timeout_seconds", 5)),
    )
    conn.set_session(readonly=True, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_id, doc_id, section, text, extra_json
                  FROM ragmeta.chunks
                 WHERE index_version = %s
                 ORDER BY faiss_row_id ASC
                """,
                (required_str(source, "index_version"),),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    candidates = []
    for chunk_id, doc_id, section, text, extra_json in rows:
        extra = parse_mapping(extra_json)
        extra.update({"chunk_id": chunk_id, "doc_id": doc_id, "section": section, "text": text})
        candidates.append(candidate_from_mapping(lane, extra, {}, metadata_only=metadata_only))
    return dedupe_candidates(candidates)


def identity_candidates(lane_cfg: Mapping[str, Any]) -> list[Candidate]:
    lane = lane_name(lane_cfg)
    candidates: list[Candidate] = []
    for row in load_query_rows(lane_cfg):
        identity = clean_text(row.get("expected_file_name")) or clean_text(row.get("source_file_name"))
        docv = clean_text(row.get("expected_document_version_id"))
        if not identity and not docv:
            continue
        text = " ".join([identity, docv, family_key(identity), clean_text(row.get("query"))])
        candidates.append(Candidate(
            candidate_id=f"identity:{short_hash(identity + docv)}",
            lane=lane,
            source_document_id=docv,
            document_family=family_key(identity),
            source_artifact_id=docv or identity,
            parser_version="NOT_APPLICABLE_IDENTITY_ONLY",
            file_identity=identity,
            template_shape=file_identity_family(identity),
            text=text,
            citation_available=False,
            location_available=False,
            table_metadata_available=False,
            header_metadata_available=False,
        ))
    return dedupe_candidates(candidates)


def candidate_from_mapping(lane: str, row: Mapping[str, Any], source_cfg: Mapping[str, Any], *, metadata_only: bool) -> Candidate:
    chunk_id = first_text(row, ["chunk_id", "id", "index_id", "indexId"]) or short_hash(json.dumps(row, sort_keys=True, default=str))
    source_doc = first_text(row, ["source_file_id", "sourceFileId", "document_version_id", "documentVersionId", "doc_id", "document_id"]) or chunk_id
    file_identity = first_text(row, ["source_file_name", "sourceFileName", "expected_file_name", "original_filename"])
    family = family_key(file_identity or first_text(row, ["title", "display_title", "retrieval_title", "section"]) or source_doc)
    artifact = first_text(row, ["extracted_artifact_id", "extractedArtifactId", "parsed_artifact_id", "parsedArtifactId", "source_file_id", "sourceFileId"]) or source_doc
    parser = first_text(row, ["parser_version", "parserVersion"]) or "UNKNOWN"
    if metadata_only:
        text = " ".join([
            file_identity,
            source_doc,
            parser,
            first_text(row, ["chunk_type", "chunkType", "unit_type", "unitType"]),
            first_text(row, ["sheetName", "cellRange", "range", "tableId", "location_type", "locationType"]),
        ])
    else:
        text = first_text(row, list(source_cfg.get("embedding_text_fields") or ["embedding_text", "embeddingText"]))
        if not text:
            text = first_text(row, list(source_cfg.get("text_fields") or ["chunk_text", "text", "display_text", "displayText"]))
    template = "|".join(part for part in [
        lane.lower(),
        first_text(row, ["chunk_type", "chunkType", "unit_type", "unitType"]),
        first_text(row, ["location_type", "locationType"]),
        range_shape(first_text(row, ["cellRange", "range"])),
        bool_text(bool(first_text(row, ["tableId", "table_id"]))),
        bool_text(bool(first_text(row, ["headers", "headerContext", "header_context"]))),
    ] if part)
    return Candidate(
        candidate_id=chunk_id,
        lane=lane,
        source_document_id=source_doc,
        document_family=family,
        source_artifact_id=artifact,
        parser_version=parser,
        file_identity=file_identity,
        template_shape=template,
        text=text,
        citation_available=bool(first_text(row, ["citation_text", "citationText"])),
        location_available=first_value(row, ["location_json", "locationJson"]) is not None,
        table_metadata_available=has_any(row, ["tableId", "table_id", "cellRange", "sheetName"]),
        header_metadata_available=has_any(row, ["headers", "headerContext", "header_context"]),
    )


def dedupe_candidates(candidates: Sequence[Candidate]) -> list[Candidate]:
    by_id: dict[str, Candidate] = {}
    for candidate in candidates:
        by_id.setdefault(candidate.candidate_id, candidate)
    return list(by_id.values())


def expected_keys(row: Mapping[str, str]) -> set[str]:
    fields = [
        "expected_chunk_ids",
        "expected_page_ids",
        "expected_document_ids",
        "expected_document_version_id",
        "expected_file_name",
        "source_file_name",
    ]
    out: set[str] = set()
    for field in fields:
        out.update(split_multi(row.get(field)))
    return {value for value in out if value}


def token_weights(text: str) -> Counter[str]:
    return Counter(tokenize(text))


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "") if len(token) > 1]


def cosine_score(query: Counter[str], doc: Counter[str]) -> float:
    if not query or not doc:
        return 0.0
    overlap = sum(query[token] * doc.get(token, 0) for token in query)
    q_norm = math.sqrt(sum(value * value for value in query.values()))
    d_norm = math.sqrt(sum(value * value for value in doc.values()))
    if not q_norm or not d_norm:
        return 0.0
    return overlap / (q_norm * d_norm)


def deterministic_sample(candidates: Sequence[Candidate], limit: int, salt: str) -> list[Candidate]:
    ranked = sorted(candidates, key=lambda c: hashlib.sha256((salt + c.candidate_id).encode("utf-8")).hexdigest())
    return ranked[: max(0, limit)]


def same_file_family(left: str, right: str) -> bool:
    return bool(left and right and family_key(left) == family_key(right))


def mutate_identity(identity: str, idx: int) -> str:
    text = identity or "unknown_file.pdf"
    if idx % 2 == 0 and YEAR_RE.search(text):
        return YEAR_RE.sub("2099", text, count=1)
    if MONTH_RE.search(text):
        return MONTH_RE.sub("12", text, count=1)
    stem = Path(text).stem or text
    suffix = Path(text).suffix or ".pdf"
    return f"{stem}_near_duplicate_{idx}{suffix}"


def prerequisite_status(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, Mapping):
        return {}
    status: dict[str, dict[str, Any]] = {}
    for name, value in raw.items():
        path = resolve_path(str(value))
        item: dict[str, Any] = {"path": repo_relative(path), "present": path.exists()}
        if path.exists() and path.suffix.lower() == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                item["status"] = payload.get("status")
                item["schema_version"] = payload.get("schema_version")
            except json.JSONDecodeError:
                item["status"] = "UNREADABLE_JSON"
        status[str(name)] = item
    return status


def mean(items: Sequence[Mapping[str, Any]], key: str) -> float:
    if not items:
        return 0.0
    values = [float(item.get(key) or 0.0) for item in items]
    return round(sum(values) / len(values), 6)


def write_by_query(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BY_QUERY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in BY_QUERY_FIELDS})


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Vector Interference Diagnostic",
        "",
        f"Status: `{report['status']}`",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "Scope: diagnostic/report-only. In-memory shadow vectors were used; no namespace or index was created.",
        "",
        f"Worst lane: `{report['worst_lane']}`",
        "",
        "## Interference Loss By Lane",
        "",
        "| Lane | Max loss | Worst condition | Baseline MRR@10 | Worst MRR@10 |",
        "|---|---:|---|---:|---:|",
    ]
    for lane, summary in report["lane_summary"].items():
        lines.append(
            f"| `{lane}` | {summary['max_vector_interference_loss']} | `{summary['worst_condition']}` | "
            f"{summary['baseline_mrr_at_10']} | {summary['worst_condition_mrr_at_10']} |"
        )
    lines.extend([
        "",
        "## Conditions Run",
        "",
    ])
    for condition in report["conditions_run"]:
        lines.append(f"- `{condition}`")
    if report.get("diagnostic_source_contract"):
        lines.extend(["", "## Diagnostic Source Contract", ""])
        for lane, contract in report["diagnostic_source_contract"].items():
            targets = ", ".join(contract.get("target_sources") or [])
            lines.append(
                f"- `{lane}`: targets=`{targets}`, hard_negative_policy=`{contract.get('hard_negative_policy', '')}`"
            )
    lines.extend([
        "",
        "## Phase 3 Optuna Diagnostic Tuning",
        "",
        f"- Decision: `{report['phase3_optuna_diagnostic_tuning']['decision']}`",
        f"- Safe: `{str(report['phase3_optuna_diagnostic_tuning']['safe']).lower()}`",
        f"- Reason: {report['phase3_optuna_diagnostic_tuning']['reason']}",
        "",
        "## Guardrails",
        "",
        f"- `production_index_mutation`: `{str(report['production_index_mutation']).lower()}`",
        f"- `vector_write_attempted`: `{str(report['vector_write_attempted']).lower()}`",
        f"- `official_denominator_registry_changed`: `{str(report['official_denominator_registry_changed']).lower()}`",
        f"- `hidden_xlsx_exposed`: `{str(report['hidden_xlsx_exposed']).lower()}`",
        f"- PDF FILE lookup policy: `{report['pdf_file_lookup_policy']}`",
        f"- Diagnostic namespace: `{report['diagnostic_namespace']['created_or_reused']}`",
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


def diagnostic_source_contract(config: Mapping[str, Any]) -> dict[str, Any]:
    raw = config.get("diagnostic_source_contract")
    if not isinstance(raw, Mapping):
        return {}
    return {str(lane): value for lane, value in raw.items() if isinstance(value, Mapping)}


def lane_name(lane_cfg: Mapping[str, Any]) -> str:
    return required_str(lane_cfg, "name")


def split_multi(value: Any) -> set[str]:
    text = clean_text(value)
    if not text:
        return set()
    return {part for part in re.split(r"[\s,;|]+", text) if part}


def first_multi(value: Any) -> str:
    parts = sorted(split_multi(value))
    return parts[0] if parts else ""


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


def template_shape(row: Mapping[str, str], lane: str) -> str:
    if lane == "XLSX":
        return "|".join(part for part in [
            "xlsx",
            clean_text(row.get("expected_chunk_type")),
            clean_text(row.get("expected_location_type")),
            range_shape(clean_text(row.get("expected_cell_range"))),
            bool_text(bool(clean_text(row.get("expected_table_id")))),
        ] if part)
    if lane == "PDF_CONTENT":
        return "|".join(part for part in [
            "pdf",
            clean_text(row.get("expected_chunk_type")),
            clean_text(row.get("expected_location_type")),
            bool_text(bool(clean_text(row.get("expected_bbox")))),
        ] if part)
    if lane == "PDF_FILE_IDENTITY":
        return file_identity_family(clean_text(row.get("expected_file_name")) or clean_text(row.get("source_file_name")))
    return "text|" + clean_text(row.get("bucket"))


def file_identity_family(value: str) -> str:
    return family_key(value)


def range_shape(value: str) -> str:
    return re.sub(r"\d+", "N", value.upper()) if value else ""


def family_key(value: str) -> str:
    text = clean_text(value).lower()
    if not text:
        return ""
    text = Path(text).stem
    text = YEAR_RE.sub("YEAR", text)
    text = MONTH_RE.sub("MONTH", text)
    text = re.sub(r"\d+", "NUM", text)
    text = re.sub(r"[_\-\s]+", " ", text)
    return text.strip() or clean_text(value)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", clean_text(value).lower()).strip()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def short_hash(value: str) -> str:
    return hashlib.sha256(clean_text(value).encode("utf-8")).hexdigest()[:12]


def stable_int(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)


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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
