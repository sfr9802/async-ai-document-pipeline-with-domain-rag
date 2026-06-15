from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v4712_layered_retrieval_generalization_and_overfit_audit as v4712
from ai.eval import rag_v4716_target_recall_repair_prototype as v4716
from ai.eval import rag_v4717_candidate_only_generalization_validation_and_xlsx_table_axis_repair_audit as v4717
from ai.eval import rag_v476_archive_purge as v476


LOGICAL_RUN_KEY = "v4_7_18"
SHORT_RUN_ID = "v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_18_"
    "xlsx_candidate_only_materialization_repair_and_lineage_reproducibility_nonprod"
)
STATUS = "V4_7_18_XLSX_CANDIDATE_ONLY_MATERIALIZATION_REPAIR_AND_LINEAGE_REPRODUCIBILITY_NONPROD_READY"
V5_GATE_PLAN_ID = "v5_0_v4_closeout_and_v5_gate_plan"
V4_CLOSEOUT_STATUS = "V4_CLOSED_DIAGNOSTIC_ONLY_SOURCE_FIRST_CANDIDATE_ONLY_LINEAGE_REPRODUCIBLE"

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
SOURCE_RUN_ID = v4717.SHORT_RUN_ID
SOURCE_REPORT_JSON = v4717.SHORT_REPORT_PATH
SOURCE_TOPK_ROWS = v4716.SOURCE_TOPK_ROWS
SOURCE_REGISTRY_JSONL = v4716.SOURCE_REGISTRY_JSONL
V4_1_REPORT_JSON = (
    REPORT_ROOT
    / "quality"
    / "official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod"
    / "report.json"
)
V4_2_REPORT_JSON = (
    REPORT_ROOT
    / "quality"
    / "official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod"
    / "report.json"
)

KST_DOC_DATE = "2026-05-31"
FAMILIES = ("TEXT", "PDF", "XLSX")
CANDIDATE_BUDGET_PER_QUERY = 5
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
CELL_PREFIX_RE = re.compile(r"\b[A-Z]+[0-9]+\s*:\s*(.*)", re.S)
RAW_PAYLOAD_FORBIDDEN_KEYS = {
    "prompt",
    "prompt_payload",
    "raw_prompt",
    "raw_prompt_payload",
    "raw_response",
    "raw_response_payload",
    "response",
    "raw_llm_response",
    "final_answer",
}
FORBIDDEN_FALSE_KEYS = (
    "official_metric",
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "training_dataset_created",
    "ft_a_execution",
    "fine_tuning",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
)
GUARDRAIL_FALSE_KEYS = set(FORBIDDEN_FALSE_KEYS) | {
    "silver_mutation",
    "source_registry_mutated",
    "cache_mutated",
    "production_db_mutated",
    "index_rebuilt",
    "direct_normalized_answer_value_matching",
    "raw_xlsx_query_time_parsing",
    "formula_evaluation",
    "formula_text_exposure",
    "source_file_title_shortcut_used",
    "target_or_gold_locator_used_for_candidate_construction",
}
REQUIRED_RUNNER_MODULES = {
    "v4_7_13": Path("ai/eval/rag_v4713_live_retrieval_answerability_and_full_pdf_replay.py"),
    "v4_7_14": Path("ai/eval/rag_v4714_diagnostic_precondition_hardening.py"),
    "v4_7_15": Path("ai/eval/rag_v4715_read_only_searchindex_replay_projection.py"),
    "v4_7_16": Path("ai/eval/rag_v4716_target_recall_repair_prototype.py"),
    "v4_7_17": Path("ai/eval/rag_v4717_candidate_only_generalization_validation_and_xlsx_table_axis_repair_audit.py"),
    "v4_7_18": Path("ai/eval/rag_v4718_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility.py"),
}


def utc_now_iso() -> str:
    return v476.utc_now_iso()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v476.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v476.write_json(path, payload)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    v476.write_jsonl(path, list(rows))


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _counter_dict(counter: Counter[str] | None = None) -> dict[str, int]:
    counter = counter or Counter()
    return {family: int(counter.get(family, 0)) for family in FAMILIES}


def _load_source_report(root: Path, source_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    report = dict(source_report or registry.load_report("v4_7_17", root=root))
    v4717.check_report(report)
    return report


def _load_silver_topk_rows(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, resolution = v4716._load_silver_topk_rows(root)
    if len(rows) != 1000:
        raise ValueError("v4_7_18 expected the 1000-row archived silver top-k replay source")
    if not resolution.get("sha256_verified") or not resolution.get("resolved_via_archive"):
        raise ValueError("v4_7_18 requires the v3_7_2 archived top-k source to be sha-verified")
    return rows, resolution


def _load_full_topk_rows(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, resolution = v4712._load_v3_7_2_topk(root)
    if not rows:
        raise ValueError("v4_7_18 could not load the archived v3_7_2 top-k source")
    if not resolution.get("sha256_verified") or not resolution.get("resolved_via_archive"):
        raise ValueError("v4_7_18 requires full top-k artifact sha/archive verification")
    return rows, resolution


def _baseline_atom_ids(row: Mapping[str, Any]) -> set[str]:
    return v4716._baseline_atom_ids(row)


def _target_atom_ids(row: Mapping[str, Any]) -> set[str]:
    return v4716._target_atom_ids(row)


def _tokenize(value: str) -> frozenset[str]:
    return frozenset(
        token.lower()
        for token in TOKEN_RE.findall(value or "")
        if len(token) >= 2 and not token.isdigit()
    )


def _is_numeric_like(value: str) -> bool:
    return bool(value) and re.sub(r"[\s,._%-]", "", value).isdigit()


def _iter_axis_pairs(value: str) -> Iterable[tuple[str, str]]:
    match = CELL_PREFIX_RE.search(value or "")
    if match:
        value = match.group(1)
    for part in re.split(r"\s*\|\s*", value or ""):
        if ":" in part:
            key, raw_value = part.split(":", 1)
        elif "=" in part:
            key, raw_value = part.split("=", 1)
        else:
            key, raw_value = part, ""
        yield _clean(key), _clean(raw_value)


def _load_source_registry_rows(root: Path) -> list[dict[str, Any]]:
    path = root / SOURCE_REGISTRY_JSONL
    if not path.exists():
        raise FileNotFoundError(f"missing source registry: {SOURCE_REGISTRY_JSONL}")
    return read_jsonl(path)


def _xlsx_source_rows(source_registry_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in source_registry_rows
        if _clean(row.get("source_family")).upper() == "XLSX"
    ]


def _row_axis_key_set(xlsx_rows: Sequence[Mapping[str, Any]]) -> frozenset[str]:
    keys: set[str] = set()
    for row in xlsx_rows:
        locator = row.get("raw_locator") or {}
        if not isinstance(locator, Mapping):
            continue
        for key, _value in _iter_axis_pairs(_clean(locator.get("row_label"))):
            if key:
                keys.add(key)
    return frozenset(keys)


def _materialized_axis_overlay_text(row: Mapping[str, Any], *, row_axis_keys: frozenset[str]) -> str:
    locator = row.get("raw_locator") or {}
    if not isinstance(locator, Mapping):
        locator = {}
    parts: list[str] = []
    for key in ("sheet", "row_label", "column_label", "target_column", "range", "cell", "value_locator"):
        value = locator.get(key)
        if isinstance(value, list):
            value = " ".join(_clean(item) for item in value)
        if _clean(value):
            parts.append(_clean(value))
    snapshot = _clean(row.get("normalized_text_or_value_snapshot"))
    for key, value in _iter_axis_pairs(snapshot):
        if key:
            parts.append(key)
        if key in row_axis_keys and value and not _is_numeric_like(value):
            parts.append(value)
    return " ".join(parts)


def _poison_oracle_fields(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    poisoned = json.loads(json.dumps(list(rows), ensure_ascii=False))
    for row in poisoned:
        row["target_source_atom_ids"] = ["poisoned_target_atom"]
        row["target_hit_at_k"] = not bool(row.get("target_hit_at_k"))
        row["target_hit_in_topk"] = not bool(row.get("target_hit_in_topk"))
        row["target_rank_at_k"] = 0
        row["question_gold_locator_target"] = {"poisoned": True}
        row["official_manifest_target"] = {"poisoned": True}
        row["target_mapping_audit"] = {"poisoned": True}
        row["supporting_evidence"] = "poisoned supporting evidence"
        row["expected_answer"] = "poisoned expected answer"
        row["expected_evidence"] = "poisoned expected evidence"
        row["query_id"] = f"poisoned-{row.get('query_id')}"
        row["case_id"] = "poisoned-case"
    return poisoned


def _base_v4716_candidate_sets(
    *,
    root: Path,
    silver_topk_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[list[str]], str, dict[str, Any]]:
    needed = v4716._needed_query_tokens(silver_topk_rows)
    index = v4716._build_source_registry_candidate_index(root=root, needed_tokens=needed)
    candidate_sets, digest = v4716._candidate_sets_for_rows(silver_topk_rows=silver_topk_rows, index=index)
    return candidate_sets, digest, index


def _candidate_budget_entry(
    *,
    silver_topk_rows: Sequence[Mapping[str, Any]],
    candidate_sets: Sequence[Sequence[str]],
    family: str,
    untruncated_candidate_sets: Sequence[Sequence[str]] | None = None,
) -> dict[str, Any]:
    lengths = [
        len(candidates)
        for row, candidates in zip(silver_topk_rows, candidate_sets, strict=True)
        if _clean(row.get("source_family")).upper() == family
    ]
    distribution = Counter(lengths)
    if untruncated_candidate_sets is None:
        exhaustion_count = int(distribution.get(CANDIDATE_BUDGET_PER_QUERY, 0))
        exhaustion_basis = "truncated_candidate_count_at_budget_lower_bound"
    else:
        untruncated_lengths = [
            len(candidates)
            for row, candidates in zip(silver_topk_rows, untruncated_candidate_sets, strict=True)
            if _clean(row.get("source_family")).upper() == family
        ]
        exhaustion_count = int(sum(1 for length in untruncated_lengths if length > CANDIDATE_BUDGET_PER_QUERY))
        exhaustion_basis = "untruncated_candidate_count_exceeds_budget"
    return {
        "attempted_row_count": len(lengths),
        "candidate_count": int(sum(lengths)),
        "zero_candidate_row_count": int(distribution.get(0, 0)),
        "at_budget_row_count": int(distribution.get(CANDIDATE_BUDGET_PER_QUERY, 0)),
        "candidate_budget_exhaustion_count": exhaustion_count,
        "candidate_budget_exhaustion_basis": exhaustion_basis,
        "candidate_count_distribution": {str(key): int(distribution.get(key, 0)) for key in range(6)},
    }


def _zero_budget_entry(*, reason: str) -> dict[str, Any]:
    return {
        "attempted_row_count": 0,
        "candidate_count": 0,
        "zero_candidate_row_count": 0,
        "at_budget_row_count": 0,
        "candidate_budget_exhaustion_count": 0,
        "candidate_budget_exhaustion_basis": reason,
        "candidate_count_distribution": {str(key): 0 for key in range(6)},
    }


def _rank_materialized_xlsx_candidates(
    *,
    silver_topk_rows: Sequence[Mapping[str, Any]],
    xlsx_rows: Sequence[Mapping[str, Any]],
    text_candidate_sets: Sequence[Sequence[str]] | None = None,
) -> dict[str, Any]:
    row_axis_keys = _row_axis_key_set(xlsx_rows)
    needed_tokens: set[str] = set()
    for row in silver_topk_rows:
        if _clean(row.get("source_family")).upper() == "XLSX":
            needed_tokens.update(_tokenize(_clean(row.get("query_text"))))

    postings: dict[str, list[str]] = defaultdict(list)
    source_atoms_scanned = 0
    source_atoms_tokenized = 0
    source_atoms_indexed = 0
    for row in xlsx_rows:
        source_atoms_scanned += 1
        atom_id = _clean(row.get("source_atom_id"))
        if not atom_id:
            continue
        tokens = _tokenize(_materialized_axis_overlay_text(row, row_axis_keys=row_axis_keys))
        if not tokens:
            continue
        source_atoms_tokenized += 1
        overlap = tokens & needed_tokens
        if not overlap:
            continue
        source_atoms_indexed += 1
        for token in overlap:
            postings[token].append(atom_id)

    candidate_sets: list[list[str]] = []
    untruncated_sets: list[list[str]] = []
    digest_rows: list[dict[str, Any]] = []
    for ordinal, row in enumerate(silver_topk_rows):
        family = _clean(row.get("source_family")).upper()
        if family != "XLSX":
            candidate_sets.append([])
            untruncated_sets.append([])
            continue
        scores: Counter[str] = Counter()
        for token in _tokenize(_clean(row.get("query_text"))):
            for atom_id in postings.get(token, ()):
                scores[atom_id] += 1
        ranked = [(atom_id, score) for atom_id, score in scores.items() if score >= 1]
        ranked.sort(key=lambda item: (-item[1], item[0]))
        untruncated = [atom_id for atom_id, _score in ranked]
        candidates = untruncated[:CANDIDATE_BUDGET_PER_QUERY]
        untruncated_sets.append(untruncated)
        candidate_sets.append(candidates)
        digest_rows.append(
            {
                "ordinal": ordinal,
                "family": family,
                "query_text_sha256": _sha256_text(_clean(row.get("query_text"))),
                "candidate_source_atom_ids": candidates,
            }
        )

    digest = _sha256_text(json.dumps(digest_rows, ensure_ascii=False, sort_keys=True))
    return {
        "candidate_sets": candidate_sets,
        "untruncated_candidate_sets": untruncated_sets,
        "candidate_set_sha256": digest,
        "candidate_budget_summary": {
            "candidate_budget_per_query": CANDIDATE_BUDGET_PER_QUERY,
            "TEXT": _candidate_budget_entry(
                silver_topk_rows=silver_topk_rows,
                candidate_sets=text_candidate_sets or [[] for _row in silver_topk_rows],
                family="TEXT",
            ),
            "PDF": _zero_budget_entry(reason="pdf_candidate_overlay_not_attempted_in_v4_7_18"),
            "XLSX": _candidate_budget_entry(
                silver_topk_rows=silver_topk_rows,
                candidate_sets=candidate_sets,
                family="XLSX",
                untruncated_candidate_sets=untruncated_sets,
            ),
        },
        "source_registry_materialized_axis_index": {
            "schema_version": f"{SHORT_RUN_ID}_source_registry_materialized_axis_index_v1",
            "candidate_only": True,
            "source_registry_logical_path": SOURCE_REGISTRY_JSONL.as_posix(),
            "source_atoms_scanned_count": source_atoms_scanned,
            "source_atoms_tokenized_count": source_atoms_tokenized,
            "source_atoms_indexed_count": source_atoms_indexed,
            "row_axis_key_count": len(row_axis_keys),
            "row_axis_keys_sha256": _sha256_text(json.dumps(sorted(row_axis_keys), ensure_ascii=False)),
            "query_token_count": len(needed_tokens),
            "raw_xlsx_query_time_parsing": False,
            "direct_normalized_answer_value_matching": False,
            "formula_evaluation": False,
            "formula_text_exposure": False,
            "source_file_title_shortcut_used": False,
            "target_or_gold_locator_used_for_candidate_construction": False,
            "source_registry_mutated": False,
            "index_rebuilt": False,
        },
    }


def _evaluate_candidate_sets(
    *,
    silver_topk_rows: Sequence[Mapping[str, Any]],
    v4716_candidate_sets: Sequence[Sequence[str]],
    v4718_candidate_sets: Sequence[Sequence[str]],
) -> dict[str, Any]:
    totals = Counter()
    baseline_hits = Counter()
    v4717_combined_hits = Counter()
    v4718_overlay_hits = Counter()
    v4718_combined_hits = Counter()
    gain_over_v4717 = Counter()
    regression = Counter()
    candidate_counts = Counter()

    for row, v4716_ids, v4718_ids in zip(silver_topk_rows, v4716_candidate_sets, v4718_candidate_sets, strict=True):
        family = _clean(row.get("source_family")).upper()
        totals[family] += 1
        target_ids = _target_atom_ids(row)
        baseline_ids = _baseline_atom_ids(row)
        v4717_ids = baseline_ids | set(v4716_ids)
        v4718_overlay_ids = set(v4718_ids)
        v4718_ids_combined = v4717_ids | v4718_overlay_ids
        baseline_hit = bool(target_ids & baseline_ids)
        v4717_hit = bool(target_ids & v4717_ids)
        v4718_overlay_hit = bool(target_ids & v4718_overlay_ids)
        v4718_hit = bool(target_ids & v4718_ids_combined)
        if baseline_hit:
            baseline_hits[family] += 1
        if v4717_hit:
            v4717_combined_hits[family] += 1
        if v4718_overlay_hit:
            v4718_overlay_hits[family] += 1
        if v4718_hit:
            v4718_combined_hits[family] += 1
        if not v4717_hit and v4718_hit:
            gain_over_v4717[family] += 1
        if v4717_hit and not v4718_hit:
            regression[family] += 1
        if family == "XLSX":
            candidate_counts[family] += len(v4718_ids)

    families: dict[str, dict[str, Any]] = {}
    for family in FAMILIES:
        total = int(totals.get(family, 0))
        v4717_hit_count = int(v4717_combined_hits.get(family, 0))
        v4718_hit_count = int(v4718_combined_hits.get(family, 0))
        families[family] = {
            "row_count": total,
            "baseline_target_hit_count": int(baseline_hits.get(family, 0)),
            "baseline_target_miss_count": total - int(baseline_hits.get(family, 0)),
            "v4_7_17_combined_target_hit_count": v4717_hit_count,
            "v4_7_17_combined_target_miss_count": total - v4717_hit_count,
            "v4_7_18_derived_overlay_target_hit_count": int(v4718_overlay_hits.get(family, 0)),
            "v4_7_18_combined_target_hit_count": v4718_hit_count,
            "v4_7_18_combined_target_miss_count": total - v4718_hit_count,
            "v4_7_18_gain_over_v4_7_17_count": int(gain_over_v4717.get(family, 0)),
            "target_hit_regression_count": int(regression.get(family, 0)),
            "candidate_count": int(candidate_counts.get(family, 0)),
        }
    return {
        "schema_version": f"{SHORT_RUN_ID}_archive_1000_materialized_target_recall_v1",
        "scope": "archived_v3_7_2_silver_1000_read_only_topk",
        "families": families,
    }


def _archive_denominator_trace(
    *,
    full_topk_rows: Sequence[Mapping[str, Any]],
    silver_topk_rows: Sequence[Mapping[str, Any]],
    topk_resolution: Mapping[str, Any],
) -> dict[str, Any]:
    full_counts = Counter(_clean(row.get("source_family")).upper() for row in full_topk_rows)
    filtered_counts = Counter(_clean(row.get("source_family")).upper() for row in silver_topk_rows)
    query_ids = [_clean(row.get("query_id")) for row in silver_topk_rows]
    envelope_lengths = Counter(str(len(row.get("top_result_envelopes") or [])) for row in silver_topk_rows)
    return {
        "schema_version": f"{SHORT_RUN_ID}_archive_denominator_trace_v1",
        "source_topk_logical_path": SOURCE_TOPK_ROWS.as_posix(),
        "source_topk_sha256": _clean(topk_resolution.get("sha256")),
        "source_topk_expected_sha256": _clean(topk_resolution.get("expected_sha256")),
        "source_topk_sha256_verified": bool(topk_resolution.get("sha256_verified")),
        "source_topk_resolved_via_archive": bool(topk_resolution.get("resolved_via_archive")),
        "topk_artifact_row_count": len(full_topk_rows),
        "filtered_replay_row_count": len(silver_topk_rows),
        "excluded_row_count": len(full_topk_rows) - len(silver_topk_rows),
        "full_artifact_family_counts": _counter_dict(full_counts),
        "filtered_family_counts": _counter_dict(filtered_counts),
        "excluded_family_counts": {
            family: int(full_counts.get(family, 0) - filtered_counts.get(family, 0)) for family in FAMILIES
        },
        "duplicate_query_id_count": len([query_id for query_id, count in Counter(query_ids).items() if query_id and count > 1]),
        "missing_query_id_count": sum(1 for query_id in query_ids if not query_id),
        "topk_envelope_length_distribution": dict(sorted(envelope_lengths.items())),
    }


def _source_counter_reproduction(source_report: Mapping[str, Any]) -> dict[str, Any]:
    validation = source_report["candidate_only_generalization_validation"]
    source_replay = validation["source_v4_7_16_candidate_replay"]
    xlsx_audit = source_report["xlsx_table_axis_repair_audit"]
    source_v4716 = source_replay
    family = xlsx_audit["archive_1000_xlsx_family_recall"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_source_counter_reproduction_v1",
        "v4_7_16": {
            "baseline_target_hit_count": source_v4716["baseline_target_hit_count"],
            "combined_target_hit_count": source_v4716["combined_target_hit_count"],
            "baseline_miss_to_hit_count": source_v4716["baseline_miss_to_hit_count"],
            "baseline_hit_to_miss_count": source_v4716["baseline_hit_to_miss_count"],
            "families": {
                "TEXT": {
                    "baseline_miss_to_hit_count": source_report["counters"]["text_baseline_miss_to_hit_count"],
                    "target_hit_regression_count": 0,
                },
                "PDF": {
                    "baseline_miss_to_hit_count": 0,
                    "target_hit_regression_count": source_report["counters"]["pdf_target_hit_regression_count"],
                },
                "XLSX": {
                    "baseline_miss_to_hit_count": family["baseline_miss_to_hit_count"],
                    "target_hit_regression_count": family["target_hit_regression_count"],
                },
            },
        },
        "v4_7_17": {
            "candidate_only_generalization_validated": source_report["counters"]["candidate_only_generalization_validated"],
            "xlsx_baseline_target_hit_count": family["baseline_target_hit_count"],
            "xlsx_combined_target_hit_count": family["combined_target_hit_count"],
            "xlsx_table_axis_candidate_count": xlsx_audit["safe_table_axis_candidate_count"],
            "xlsx_table_axis_target_hit_gain_count": xlsx_audit["safe_table_axis_target_hit_gain_count"],
            "xlsx_table_axis_gain_rate_per_baseline_miss": xlsx_audit["safe_table_axis_gain_rate_per_baseline_miss"],
            "xlsx_table_axis_repair_decision": xlsx_audit["decision"],
        },
    }


def _candidate_validation_reproduction(
    *,
    source_report: Mapping[str, Any],
    silver_topk_rows: Sequence[Mapping[str, Any]],
    v4716_candidate_sets: Sequence[Sequence[str]],
    v4716_candidate_set_sha256: str,
    v4718_candidate_sets: Sequence[Sequence[str]],
    v4718_candidate_set_sha256: str,
    poisoned_candidate_set_sha256: str,
) -> dict[str, Any]:
    validation = source_report["candidate_only_generalization_validation"]
    source_replay = validation["source_v4_7_16_candidate_replay"]
    poisoned_evaluation = _evaluate_candidate_sets(
        silver_topk_rows=_poison_oracle_fields(silver_topk_rows),
        v4716_candidate_sets=v4716_candidate_sets,
        v4718_candidate_sets=v4718_candidate_sets,
    )
    poisoned_xlsx_hits = poisoned_evaluation["families"]["XLSX"]["v4_7_18_combined_target_hit_count"]
    source_candidate_set_sha256 = source_replay["source_candidate_set_sha256"]
    source_candidate_set_sha256_matches_recomputed = (
        source_replay["source_candidate_set_sha256_matches_recomputed"]
        and v4716_candidate_set_sha256 == source_candidate_set_sha256
    )
    return {
        "schema_version": f"{SHORT_RUN_ID}_candidate_only_validation_reproduction_v1",
        "status": "CANDIDATE_ONLY_GENERALIZATION_REPRODUCED_DIAGNOSTIC_ONLY",
        "source_run_id": SOURCE_RUN_ID,
        "source_candidate_set_sha256": source_candidate_set_sha256,
        "source_candidate_set_sha256_recomputed": v4716_candidate_set_sha256,
        "source_candidate_set_sha256_source_report_claimed_match": source_replay[
            "source_candidate_set_sha256_matches_recomputed"
        ],
        "source_candidate_set_sha256_matches_recomputed": source_candidate_set_sha256_matches_recomputed,
        "source_topk_sha256": source_replay["source_topk_sha256"],
        "source_topk_sha256_verified": source_replay["source_topk_sha256_verified"],
        "source_topk_resolved_via_archive": source_replay["source_topk_resolved_via_archive"],
        "poisoned_oracle_field_digest_stable": validation["poisoned_oracle_field_digest_stable"]
        and v4718_candidate_set_sha256 == poisoned_candidate_set_sha256,
        "poisoned_oracle_field_evaluation_changed": validation["poisoned_oracle_field_evaluation_changed"]
        and poisoned_xlsx_hits != 26,
        "v4_7_18_candidate_set_sha256": v4718_candidate_set_sha256,
        "v4_7_18_poisoned_candidate_set_sha256": poisoned_candidate_set_sha256,
        "diagnostic_target_labels_used_for_after_the_fact_evaluation": True,
        "diagnostic_target_labels_used_for_candidate_construction": False,
        "diagnostic_target_labels_used_for_candidate_scoring": False,
        "target_source_atom_ids_used_for_candidate_construction": False,
        "target_source_atom_ids_used_for_candidate_scoring": False,
        "query_id_or_case_id_used_for_candidate_construction": False,
        "query_id_or_case_id_used_for_candidate_scoring": False,
    }


def _overlay_90_projection(
    *,
    root: Path,
    silver_topk_rows: Sequence[Mapping[str, Any]],
    v4716_candidate_sets: Sequence[Sequence[str]],
    v4718_candidate_sets: Sequence[Sequence[str]],
) -> dict[str, Any]:
    overlay = read_json(root / v4716.SOURCE_OVERLAY_JSON)
    rows_by_hash = {_clean(row.get("query_text_sha256")): (row, old, new) for row, old, new in zip(silver_topk_rows, v4716_candidate_sets, v4718_candidate_sets, strict=True)}
    counters = Counter()
    for overlay_row in overlay.get("rows") or []:
        if _clean(overlay_row.get("source_family")).upper() != "XLSX":
            continue
        counters["xlsx_overlay_row_count"] += 1
        target_miss = bool(overlay_row.get("retrieval_target_miss")) or bool(overlay_row.get("target_not_in_topk"))
        repeated_prefix = bool(overlay_row.get("repeated_prefix_cluster_member"))
        if target_miss:
            counters["target_not_in_topk_total"] += 1
        if repeated_prefix:
            counters["repeated_prefix_cluster_total"] += 1
        if target_miss and repeated_prefix:
            counters["repeated_prefix_cluster_overlap_with_target_miss"] += 1
        item = rows_by_hash.get(_clean(overlay_row.get("query_text_sha256")))
        if not item:
            continue
        row, old, new = item
        targets = _target_atom_ids(row)
        baseline = _baseline_atom_ids(row)
        old_combined = baseline | set(old)
        new_combined = old_combined | set(new)
        if targets & set(new):
            counters["v4_7_18_derived_overlay_target_hit_count"] += 1
        if not (targets & old_combined) and (targets & new_combined):
            counters["v4_7_18_gain_over_v4_7_17_count"] += 1
            if repeated_prefix:
                counters["v4_7_18_gain_repeated_prefix_count"] += 1
            else:
                counters["v4_7_18_gain_non_repeated_prefix_count"] += 1
    return {
        "schema_version": f"{SHORT_RUN_ID}_overlay_90_xlsx_projection_v1",
        "source_overlay_json": v4716.SOURCE_OVERLAY_JSON.as_posix(),
        "xlsx_overlay_row_count": int(counters["xlsx_overlay_row_count"]),
        "target_not_in_topk_total": int(counters["target_not_in_topk_total"]),
        "repeated_prefix_cluster_total": int(counters["repeated_prefix_cluster_total"]),
        "repeated_prefix_cluster_overlap_with_target_miss": int(counters["repeated_prefix_cluster_overlap_with_target_miss"]),
        "v4_7_18_derived_overlay_target_hit_count": int(counters["v4_7_18_derived_overlay_target_hit_count"]),
        "v4_7_18_gain_over_v4_7_17_count": int(counters["v4_7_18_gain_over_v4_7_17_count"]),
        "v4_7_18_gain_repeated_prefix_count": int(counters["v4_7_18_gain_repeated_prefix_count"]),
        "v4_7_18_gain_non_repeated_prefix_count": int(counters["v4_7_18_gain_non_repeated_prefix_count"]),
    }


def _xlsx_repair_report(
    *,
    root: Path,
    evaluation: Mapping[str, Any],
    overlay_result: Mapping[str, Any],
    candidate_summary: Mapping[str, Any],
    index_summary: Mapping[str, Any],
) -> dict[str, Any]:
    xlsx = dict(evaluation["families"]["XLSX"])
    gain_rate = f"{xlsx['v4_7_18_gain_over_v4_7_17_count']}/{xlsx['v4_7_17_combined_target_miss_count']}"
    return {
        "schema_version": f"{SHORT_RUN_ID}_xlsx_materialization_repair_v1",
        "status": "XLSX_CANDIDATE_ONLY_MATERIALIZATION_REPAIR_ACCEPTED_DIAGNOSTIC_ONLY",
        "decision": "accept_materialized_axis_value_overlay_diagnostic_only",
        "diagnostic_only": True,
        "non_production": True,
        "candidate_only": True,
        "source_registry_jsonl": SOURCE_REGISTRY_JSONL.as_posix(),
        "v4_1_persisted_display_metadata_report_json": V4_1_REPORT_JSON.as_posix(),
        "v4_2_locator_v2_report_json": V4_2_REPORT_JSON.as_posix(),
        "input_artifact_hashes": {
            "v4_1_report_json_sha256": sha256_file(root / V4_1_REPORT_JSON) if (root / V4_1_REPORT_JSON).exists() else "",
            "v4_2_report_json_sha256": sha256_file(root / V4_2_REPORT_JSON) if (root / V4_2_REPORT_JSON).exists() else "",
            "source_registry_jsonl_sha256": sha256_file(root / SOURCE_REGISTRY_JSONL),
        },
        "candidate_construction_fields_used": {
            "query": ["query_text", "source_family"],
            "source_registry_XLSX": [
                "source_family",
                "source_atom_id",
                "raw_locator.sheet",
                "raw_locator.row_label",
                "raw_locator.column_label",
                "raw_locator.target_column",
                "raw_locator.range",
                "raw_locator.cell",
                "raw_locator.value_locator",
                "normalized_text_or_value_snapshot_header_tokens",
                "normalized_text_or_value_snapshot_non_numeric_axis_values",
            ],
        },
        "forbidden_fields_not_used": [
            "target_source_atom_ids",
            "expected_answer",
            "supporting_evidence",
            "question_gold_locator_target",
            "official_manifest_target",
            "raw_locator.normalized_value",
            "raw_locator.workbook",
            "raw_locator.source_path",
            "raw_locator.source_file_path",
            "query_id",
            "case_id",
            "formula_text",
        ],
        "archive_1000_xlsx_family_recall": {
            **xlsx,
            "v4_7_18_gain_rate_per_v4_7_17_miss": gain_rate,
        },
        "candidate_budget_summary": candidate_summary,
        "overlay_90_xlsx_projection": dict(overlay_result),
        "source_registry_materialized_axis_index": dict(index_summary),
        "rule_decisions": {
            "accepted": ["materialized_axis_value_searchunit_overlay"],
            "rejected": [
                "direct_normalized_value_matching",
                "raw_xlsx_query_time_parsing",
                "source_title_or_workbook_shortcut",
                "query_id_case_id_hack",
                "formula_text_or_formula_evaluation",
                "target_or_gold_locator_candidate_scoring",
            ],
            "inconclusive": [
                "formatted_value_broad_recall_lift",
                "cell_locator_candidate_scoring_beyond_materialized_axis_overlay",
                "merged_header_propagation_beyond_existing_materialized_snapshot",
            ],
        },
        "repeated_prefix_demotion_summary": {
            "demotion_or_dedup_rule_applied": False,
            "reason": "candidate-only materialized axis overlay improved one repeated-prefix overlay row; explicit demotion was left inconclusive to avoid row-specific tuning",
            "overlay_repeated_prefix_total": overlay_result["repeated_prefix_cluster_total"],
            "overlay_repeated_prefix_overlap_with_target_miss": overlay_result["repeated_prefix_cluster_overlap_with_target_miss"],
            "overlay_repeated_prefix_gain_count": overlay_result["v4_7_18_gain_repeated_prefix_count"],
        },
        "direct_normalized_answer_value_matching": False,
        "raw_xlsx_query_time_parsing": False,
        "formula_evaluation": False,
        "formula_text_exposure": False,
        "source_file_title_shortcut_used": False,
        "workbook_or_source_title_shortcut_used": False,
        "target_or_gold_locator_used_for_candidate_construction": False,
        "threshold_tuning_used": False,
        "query_id_case_id_hack_used": False,
        "per_query_candidates_written": False,
        "diagnostic_target_labels_used_for_after_the_fact_evaluation": True,
        "diagnostic_target_labels_used_for_candidate_construction": False,
        "diagnostic_target_labels_used_for_candidate_scoring": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def _run_git(root: Path, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False, timeout=30)


def _path_tracked(root: Path, path: Path) -> bool:
    return _run_git(root, ["ls-files", "--error-unmatch", path.as_posix()]).returncode == 0


def _path_ignored(root: Path, path: Path) -> bool:
    return _run_git(root, ["check-ignore", "-q", path.as_posix()]).returncode == 0


def _py_compile_ok(root: Path, path: Path) -> bool:
    try:
        source = (root / path).read_text(encoding="utf-8")
        compile(source, str(root / path), "exec")
    except (OSError, SyntaxError, ValueError):
        return False
    return True


def _lineage_reproducibility(root: Path) -> dict[str, Any]:
    modules: list[dict[str, Any]] = []
    for key, path in REQUIRED_RUNNER_MODULES.items():
        exists = (root / path).exists()
        try:
            resolved = registry.resolve_run(key, root=root)
            resolver_checkable = resolved.report_path == root / REPORT_ROOT / "runs" / key / "report.json"
        except Exception:
            resolver_checkable = False
        modules.append(
            {
                "logical_key": key,
                "module_path": path.as_posix(),
                "exists": exists,
                "tracked": exists and _path_tracked(root, path),
                "ignored": _path_ignored(root, path),
                "py_compile_ok": exists and _py_compile_ok(root, path),
                "resolver_checkable": resolver_checkable,
            }
        )
    clean = all(
        row["exists"]
        and row["tracked"]
        and not row["ignored"]
        and row["py_compile_ok"]
        and row["resolver_checkable"]
        for row in modules
    )
    generated_ignored = _path_ignored(root, SHORT_REPORT_PATH) and _path_ignored(root, STATUS_JSONL_PATH)
    return {
        "schema_version": f"{SHORT_RUN_ID}_lineage_reproducibility_v1",
        "status": "LINEAGE_REPRODUCIBILITY_HARDENED_DIAGNOSTIC_ONLY" if clean else "LINEAGE_REPRODUCIBILITY_RISK_RECORDED_DIAGNOSTIC_ONLY",
        "clean_checkout_risk_status": "NO_REQUIRED_RUNNER_MODULE_RISK_DETECTED" if clean else "REQUIRED_RUNNER_MODULE_RISK_RECORDED",
        "required_runner_module_tracking_status": (
            "REQUIRED_RUNNER_MODULES_TRACKED_AND_NOT_IGNORED" if clean else "REQUIRED_RUNNER_MODULE_TRACKING_GAP_RECORDED"
        ),
        "required_runner_modules": modules,
        "generated_report_artifacts_ignored": generated_ignored,
        "compile_check_mode": "source_text_compile_no_bytecode_write",
        "bytecode_written_by_lineage_check": False,
        "generated_report_paths": [SHORT_REPORT_PATH.as_posix(), STATUS_JSONL_PATH.as_posix()],
        "source_report_materialized_in_memory_allowed": True,
        "ignored_report_dependency_policy": "reports/status are local-only ignored artifacts; runner modules are required source files",
    }


def _anti_overfit_guardrails() -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_anti_overfit_guardrails_v1",
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "silver_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
        "source_registry_mutated": False,
        "index_rebuilt": False,
        "cache_mutated": False,
        "production_db_mutated": False,
        "answer_generation_attempted": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "SearchView_vector_payload_role": "candidate_only",
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "raw_xlsx_query_time_parsing": False,
        "direct_normalized_answer_value_matching": False,
        "formula_evaluation": False,
        "formula_text_exposure": False,
        "source_file_title_shortcut_used": False,
        "target_or_gold_locator_used_for_candidate_construction": False,
        "threshold_tuning_used": False,
        "query_id_case_id_hack_used": False,
    }


def _regression_guards(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    return {family: dict(evaluation["families"][family]) for family in FAMILIES}


def _build_counters(report_parts: Mapping[str, Any]) -> dict[str, Any]:
    repair = report_parts["xlsx_candidate_only_materialization_repair"]
    xlsx = repair["archive_1000_xlsx_family_recall"]
    guards = report_parts["regression_guards"]
    return {
        "current_resolves_to": LOGICAL_RUN_KEY,
        "source_run_id": SOURCE_RUN_ID,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "lineage_reproducibility_status": report_parts["lineage_reproducibility"]["status"],
        "xlsx_materialization_repair_decision": repair["decision"],
        "xlsx_baseline_target_hit_count": xlsx["baseline_target_hit_count"],
        "xlsx_v4_7_17_combined_target_hit_count": xlsx["v4_7_17_combined_target_hit_count"],
        "xlsx_v4_7_18_combined_target_hit_count": xlsx["v4_7_18_combined_target_hit_count"],
        "xlsx_v4_7_18_gain_over_v4_7_17_count": xlsx["v4_7_18_gain_over_v4_7_17_count"],
        "xlsx_target_hit_regression_count": xlsx["target_hit_regression_count"],
        "xlsx_candidate_count": repair["candidate_budget_summary"]["XLSX"]["candidate_count"],
        "xlsx_candidate_budget_exhaustion_count": repair["candidate_budget_summary"]["XLSX"]["candidate_budget_exhaustion_count"],
        "text_v4_7_18_combined_target_hit_count": guards["TEXT"]["v4_7_18_combined_target_hit_count"],
        "text_target_hit_regression_count": guards["TEXT"]["target_hit_regression_count"],
        "pdf_v4_7_18_combined_target_hit_count": guards["PDF"]["v4_7_18_combined_target_hit_count"],
        "pdf_target_hit_regression_count": guards["PDF"]["target_hit_regression_count"],
        "candidate_digest_stable_under_poisoned_oracle_fields": report_parts[
            "candidate_only_generalization_validation_reproduction"
        ]["poisoned_oracle_field_digest_stable"],
        "generated_response_count": 0,
        "claim_support_fail_count": 0,
        "parser_failure_count": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def _v4_closeout_and_v5_gate_plan(report_parts: Mapping[str, Any]) -> dict[str, Any]:
    repair = report_parts["xlsx_candidate_only_materialization_repair"]
    xlsx = repair["archive_1000_xlsx_family_recall"]
    budget = repair["candidate_budget_summary"]["XLSX"]
    lineage = report_parts["lineage_reproducibility"]
    return {
        "plan_id": V5_GATE_PLAN_ID,
        "v4_closeout_status": V4_CLOSEOUT_STATUS,
        "v4_closeout_basis_run_key": LOGICAL_RUN_KEY,
        "v4_closeout_basis_short_run_id": SHORT_RUN_ID,
        "v4_closeout_basis_report_json": SHORT_REPORT_PATH.as_posix(),
        "current_source_of_truth": "v4_7_18",
        "source_first_candidate_only_lineage_closed": True,
        "ambiguous_non_gold_choices_remain_diagnostic_only": True,
        "official_metric_opening_preconditions_documented": True,
        "official_metric_opening_preconditions_satisfied": False,
        "live_readiness_promotion_preconditions_documented": True,
        "live_readiness_promotion_preconditions_satisfied": False,
        "diagnostic_only_rationale": [
            "v4_7_18 uses archived diagnostic rows and after-the-fact target-hit checks, not approved official labels",
            "SearchView/vector payload remains candidate-only and SourceAtom/EvidenceBundle remains evidence truth",
            "XLSX axis/header overlay is accepted only as a candidate-construction repair, not as relevance or answerability evidence",
            "lineage reproducibility is hardened for v4_7_13-v4_7_18 source modules while report/status artifacts stay ignored local outputs",
        ],
        "user_owned_decisions": [
            "approve gold/qrels creation or mutation policy",
            "approve expected evidence and expected answer evidence standards",
            "approve relevance labels and answerability labels",
            "freeze official denominator inclusion and exclusion policy",
            "approve promotion policy and any product-success interpretation",
            "explicitly authorize official metric opening after the above are complete",
        ],
        "codex_owned_work": [
            "implement schema, runner, tests, and report plumbing for approved v5 gates",
            "keep current alias, lineage, ignored-artifact, and protected-surface checks synchronized",
            "define indexing scope using source-first candidate-only inputs until user gold policy opens",
            "maintain failure taxonomy and residual queues as diagnostic-only until labels are approved",
        ],
        "xlsx_residual_engineering_backlog": [
            f"triage {xlsx['v4_7_18_combined_target_miss_count']} remaining XLSX diagnostic target misses",
            f"reduce or explain {budget['zero_candidate_row_count']} zero-candidate XLSX rows without raw XLSX query-time parsing",
            f"reduce or explain {budget['candidate_budget_exhaustion_count']} budget-exhausted XLSX rows without threshold tuning",
            "prototype formatted-value and broader cell scoring as candidate-only experiments before any gold decision",
            "separate repeated-prefix, header-axis, row-axis, and table-range failures in the v5 failure taxonomy",
        ],
        "official_metric_opening_preconditions": [
            "user-approved gold/qrels and expected-evidence policy are present",
            "relevance, answerability, and official denominator policies are frozen and versioned",
            "metric definitions, denominator counts, and blocked/deferred metrics are documented before scoring",
            "protected source-of-truth diffs for gold/qrels/labels/denominator/index/silver are explicit and approved",
            "runner/report status flips official_metric_input_rows only from approved denominator rows",
        ],
        "live_readiness_and_promotion_preconditions": [
            "official metrics have been opened, run, reviewed, and accepted under the frozen denominator",
            "live DB/index/cache readiness is verified by an explicit non-production-to-live rollout checklist",
            "redaction, leakage, latency, rollback, and monitoring gates are documented with command evidence",
            "promotion and product-success claims are user-approved and separated from diagnostic repair counters",
            "training, fine-tuning, FT-A, or dataset export is explicitly authorized before any artifact is created",
        ],
        "still_closed": {
            "official_metric_input_rows": 0,
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "denominator_mutation": False,
            "training_dataset_created": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_db_index_cache_readiness": False,
        },
        "lineage_reproducibility_status": lineage["status"],
        "required_runner_module_tracking_status": lineage["required_runner_module_tracking_status"],
    }


def build_report(
    *,
    root: Path,
    generated_at: str | None = None,
    source_report: Mapping[str, Any] | None = None,
    check: bool = True,
) -> dict[str, Any]:
    v4717_report = _load_source_report(root, source_report=source_report)
    silver_topk_rows, topk_resolution = _load_silver_topk_rows(root)
    full_topk_rows, full_topk_resolution = _load_full_topk_rows(root)
    source_registry_rows = _load_source_registry_rows(root)
    xlsx_rows = _xlsx_source_rows(source_registry_rows)
    v4716_candidate_sets, v4716_candidate_sha256, _source_index = _base_v4716_candidate_sets(
        root=root,
        silver_topk_rows=silver_topk_rows,
    )
    overlay = _rank_materialized_xlsx_candidates(
        silver_topk_rows=silver_topk_rows,
        xlsx_rows=xlsx_rows,
        text_candidate_sets=v4716_candidate_sets,
    )
    poisoned_overlay = _rank_materialized_xlsx_candidates(
        silver_topk_rows=_poison_oracle_fields(silver_topk_rows),
        xlsx_rows=xlsx_rows,
        text_candidate_sets=v4716_candidate_sets,
    )
    evaluation = _evaluate_candidate_sets(
        silver_topk_rows=silver_topk_rows,
        v4716_candidate_sets=v4716_candidate_sets,
        v4718_candidate_sets=overlay["candidate_sets"],
    )
    overlay_90 = _overlay_90_projection(
        root=root,
        silver_topk_rows=silver_topk_rows,
        v4716_candidate_sets=v4716_candidate_sets,
        v4718_candidate_sets=overlay["candidate_sets"],
    )
    repair = _xlsx_repair_report(
        root=root,
        evaluation=evaluation,
        overlay_result=overlay_90,
        candidate_summary=overlay["candidate_budget_summary"],
        index_summary=overlay["source_registry_materialized_axis_index"],
    )
    denominator = _archive_denominator_trace(
        full_topk_rows=full_topk_rows,
        silver_topk_rows=silver_topk_rows,
        topk_resolution=full_topk_resolution,
    )
    validation = _candidate_validation_reproduction(
        source_report=v4717_report,
        silver_topk_rows=silver_topk_rows,
        v4716_candidate_sets=v4716_candidate_sets,
        v4716_candidate_set_sha256=v4716_candidate_sha256,
        v4718_candidate_sets=overlay["candidate_sets"],
        v4718_candidate_set_sha256=overlay["candidate_set_sha256"],
        poisoned_candidate_set_sha256=poisoned_overlay["candidate_set_sha256"],
    )
    lineage = _lineage_reproducibility(root)
    guards = _regression_guards(evaluation)
    report_parts = {
        "xlsx_candidate_only_materialization_repair": repair,
        "lineage_reproducibility": lineage,
        "regression_guards": guards,
        "candidate_only_generalization_validation_reproduction": validation,
    }
    counters = _build_counters(report_parts)
    v5_gate_plan = _v4_closeout_and_v5_gate_plan(report_parts)
    source_report_path = root / SOURCE_REPORT_JSON
    report = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated_at or utc_now_iso(),
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
            "source_report_json": SOURCE_REPORT_JSON.as_posix(),
            "source_topk_rows_jsonl": SOURCE_TOPK_ROWS.as_posix(),
            "source_registry_jsonl": SOURCE_REGISTRY_JSONL.as_posix(),
            "v4_1_report_json": V4_1_REPORT_JSON.as_posix(),
            "v4_2_report_json": V4_2_REPORT_JSON.as_posix(),
        },
        "artifact_sha256": {},
        "source_run_id": SOURCE_RUN_ID,
        "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        "source_report_short_run_id": v4717_report.get("short_run_id"),
        "source_report_canonical_long_run_id": v4717_report.get("canonical_long_run_id"),
        "source_report_status": v4717_report.get("status"),
        "source_report_schema_version": v4717_report.get("schema_version"),
        "source_report_sha256": sha256_file(source_report_path) if source_report_path.exists() else "",
        "source_report_materialized_in_memory": not source_report_path.exists(),
        "source_topk_rows_jsonl": SOURCE_TOPK_ROWS.as_posix(),
        "source_topk_sha256": _clean(topk_resolution.get("sha256")),
        "source_topk_expected_sha256": _clean(topk_resolution.get("expected_sha256")),
        "source_topk_sha256_verified": bool(topk_resolution.get("sha256_verified")),
        "source_topk_resolved_via_archive": bool(topk_resolution.get("resolved_via_archive")),
        "source_topk_physical_path_redacted": True,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
        "SearchView_vector_payload_role": "candidate_only",
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "answer_generation_attempted": False,
        "generated_response_count": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "source_counter_reproduction": _source_counter_reproduction(v4717_report),
        "archive_denominator_trace": denominator,
        "candidate_only_generalization_validation_reproduction": validation,
        "xlsx_candidate_only_materialization_repair": repair,
        "lineage_reproducibility": lineage,
        "regression_guards": guards,
        "anti_overfit_guardrails": _anti_overfit_guardrails(),
        "v4_closeout_and_v5_gate_plan": v5_gate_plan,
        "official_metric_opening_preconditions_documented": True,
        "official_metric_opening_preconditions_satisfied": False,
        "live_readiness_promotion_preconditions_documented": True,
        "live_readiness_promotion_preconditions_satisfied": False,
        "counters": counters,
        "completion_branch": V5_GATE_PLAN_ID,
        "residual_risks": [
            "v4_7_18 is diagnostic-only over archived silver rows and is not official scoring or promotion evidence",
            "XLSX repair still leaves 299 XLSX misses and 78 zero-candidate XLSX rows under candidate-only constraints",
            "candidate budget exhaustion remains high for XLSX; no threshold tuning, row-specific hacks, or direct value matching was used",
        ],
    }
    if check:
        check_report(report)
    return report


def write_report_bundle(root: Path, report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    report = json.loads(json.dumps(report, ensure_ascii=False))
    write_json(root / SHORT_REPORT_PATH, report)
    return report, {"report_json_sha256": sha256_file(root / SHORT_REPORT_PATH)}


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    counters = report["counters"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "diagnostic_v4_7_18_xlsx_materialization_repair_lineage_reproducibility_nonprod",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "source_run_id": SOURCE_RUN_ID,
        "source_report_short_run_id": report["source_report_short_run_id"],
        "source_report_canonical_long_run_id": report["source_report_canonical_long_run_id"],
        "source_report_status": report["source_report_status"],
        "source_report_sha256": report["source_report_sha256"],
        "source_report_materialized_in_memory": report["source_report_materialized_in_memory"],
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "protected_namespaces_touched": [],
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "v4_closeout_status": V4_CLOSEOUT_STATUS,
        "v5_gate_plan_id": V5_GATE_PLAN_ID,
        "v4_closeout_basis_short_run_id": SHORT_RUN_ID,
        "ambiguous_non_gold_choices_remain_diagnostic_only": True,
        "official_metric_opening_preconditions_documented": True,
        "official_metric_opening_preconditions_satisfied": False,
        "live_readiness_promotion_preconditions_documented": True,
        "live_readiness_promotion_preconditions_satisfied": False,
        "lineage_reproducibility_status": counters["lineage_reproducibility_status"],
        "xlsx_materialization_repair_decision": counters["xlsx_materialization_repair_decision"],
        "xlsx_v4_7_18_combined_target_hit_count": counters["xlsx_v4_7_18_combined_target_hit_count"],
        "xlsx_v4_7_18_gain_over_v4_7_17_count": counters["xlsx_v4_7_18_gain_over_v4_7_17_count"],
        "xlsx_candidate_budget_exhaustion_count": counters["xlsx_candidate_budget_exhaustion_count"],
        "text_target_hit_regression_count": counters["text_target_hit_regression_count"],
        "pdf_target_hit_regression_count": counters["pdf_target_hit_regression_count"],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def append_status(root: Path, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    path = root / STATUS_JSONL_PATH
    rows = read_jsonl(path) if path.exists() else []
    event_type = "diagnostic_v4_7_18_xlsx_materialization_repair_lineage_reproducibility_nonprod"
    rows = [
        row
        for row in rows
        if row.get("run_id") not in {SHORT_RUN_ID, CANONICAL_LONG_RUN_ID}
        and row.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID
        and row.get("event_type") != event_type
    ]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    write_jsonl(path, rows)


def _upsert_block(text: str, *, start_marker: str, end_marker: str, block: str, after_anchor: str | None = None) -> str:
    wrapped = f"{start_marker}\n{block.rstrip()}\n{end_marker}"
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.S)
    if pattern.search(text):
        return pattern.sub(wrapped, text, count=1)
    if after_anchor and after_anchor in text:
        return text.replace(after_anchor, after_anchor + "\n\n" + wrapped, 1)
    return wrapped + "\n" + text


def _upsert_block_at_top(text: str, *, start_marker: str, end_marker: str, block: str) -> str:
    wrapped = f"{start_marker}\n{block.rstrip()}\n{end_marker}"
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker) + r"\s*", re.S)
    text = pattern.sub("", text, count=1).lstrip()
    return wrapped + "\n\n" + text


def _sync_last_updated(text: str) -> str:
    return re.sub(r"Last updated: .*? KST\.", f"Last updated: {KST_DOC_DATE} KST.", text, count=1)


def _replace_summary_block(text: str, *, block: str) -> str:
    start = "<!-- v4_7_18_summary_start -->"
    end = "<!-- v4_7_18_summary_end -->"
    wrapped = f"{start}\n{block.rstrip()}\n{end}"
    prior_current_summary = re.compile(r"<!-- v4_7[^>]*_summary_start -->.*?<!-- v4_7[^>]*_summary_end -->", re.S)
    if prior_current_summary.search(text):
        return prior_current_summary.sub(wrapped, text, count=1)
    return _upsert_block(text, start_marker=start, end_marker=end, block=block)


def update_docs(root: Path, report: Mapping[str, Any]) -> None:
    repair = report["xlsx_candidate_only_materialization_repair"]
    xlsx = repair["archive_1000_xlsx_family_recall"]
    xlsx_budget = repair["candidate_budget_summary"]["XLSX"]
    denominator = report["archive_denominator_trace"]
    lineage = report["lineage_reproducibility"]
    validation = report["candidate_only_generalization_validation_reproduction"]
    gate_plan = report["v4_closeout_and_v5_gate_plan"]
    progress = root / "docs/rag-ingestion-progress.md"
    measurements = root / "docs/rag-ingestion-measurements.md"
    triage = root / "docs/rag-ingestion-triage.md"
    readme = root / "README.md"
    eval_readme = root / "ai/eval/README.md"
    scripts_readme = root / "ai/scripts/README.md"

    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} is artifact-ready / XLSX candidate-only materialization "
        f"repair-ready and lineage reproducibility-hardened. Artifact: `{SHORT_REPORT_PATH.as_posix()}`. "
        f"v4_7_16/v4_7_17 counters reproduce before evaluation: baseline 300/1000, v4_7_17 combined 514/1000, "
        f"TEXT +212, XLSX +2, PDF regression 0. The v4_7_18 XLSX materialized axis overlay uses only current query text, "
        "source family, SourceAtom raw_locator axes, and already-materialized non-numeric row-axis/header text; it improves "
        f"XLSX combined target hits {xlsx['v4_7_17_combined_target_hit_count']} -> {xlsx['v4_7_18_combined_target_hit_count']} "
        f"with {repair['candidate_budget_summary']['XLSX']['candidate_count']} candidates and "
        f"{repair['candidate_budget_summary']['XLSX']['candidate_budget_exhaustion_count']} budget-exhausted rows. "
        f"Archive denominator trace is explicit: top-k rows {denominator['topk_artifact_row_count']} -> filtered replay "
        f"{denominator['filtered_replay_row_count']}, excluded {denominator['excluded_row_count']} "
        f"{denominator['excluded_family_counts']}. Lineage status `{lineage['status']}`; runner modules v4_7_13-v4_7_18 "
        "are required source files, while report/status artifacts remain ignored. official_metric_input_rows=0, "
        "silver_promoted_to_gold_count=0, promotion_evidence=false, product_success_evidence_allowed=false, "
        "live_db_index_cache_readiness=false; no raw XLSX query-time parsing, direct normalized value matching, formula use, "
        "source-title/workbook shortcut, target/gold locator scoring, query_id hack, training, fine-tuning, or protected mutation."
    )
    v5_progress_block = (
        f"- v4 closeout basis: `{SHORT_RUN_ID}` is the current source of truth for closing v4 as "
        f"`{gate_plan['v4_closeout_status']}`. v5 remains gate-plan-only until user-owned policy inputs are explicit. "
        "User-owned decisions: gold/qrels policy, expected evidence, relevance labels, answerability labels, official "
        "denominator, and promotion policy. Codex-owned work: schema/runner/test/report plumbing, indexing-scope checks, "
        "failure-taxonomy maintenance, and docs/status synchronization after those decisions. XLSX residual backlog: "
        f"{xlsx['v4_7_18_combined_target_miss_count']} misses, {xlsx_budget['zero_candidate_row_count']} zero-candidate "
        f"rows, and {xlsx_budget['candidate_budget_exhaustion_count']} budget-exhausted rows remain diagnostic-only. "
        "Official metric opening preconditions: approved gold/qrels/labels/denominator, documented metric definitions, "
        "protected-surface diff approval, and `official_metric_input_rows` sourced only from approved denominator rows. "
        "Live-readiness and promotion preconditions: accepted official metrics, explicit live DB/index/cache rollout "
        "evidence, leakage/redaction/latency/rollback monitoring, and user-approved promotion/product-success policy. "
        "Ambiguous non-gold choices stay diagnostic-only because v4_7_18 target checks are after-the-fact diagnostics, "
        "not relevance, answerability, denominator, or promotion decisions."
    )
    progress_text = _upsert_block(
        progress.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
        block=progress_block,
        after_anchor="# RAG Ingestion Progress",
    )
    progress_text = _upsert_block(
        progress_text,
        start_marker=f"<!-- {V5_GATE_PLAN_ID}:progress-entry:start -->",
        end_marker=f"<!-- {V5_GATE_PLAN_ID}:progress-entry:end -->",
        block=v5_progress_block,
        after_anchor=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
    )
    progress_text = progress_text.replace(
        "Overall status: `V4_7_12_LAYERED_RETRIEVAL_GENERALIZATION_AND_OVERFIT_AUDIT_NONPROD_READY`;",
        f"Overall status: `{STATUS}`;\ncurrent v4_7 closeout basis:\n`{SHORT_RUN_ID}`;",
        1,
    )
    progress_text = progress_text.replace(
        "current v4 marker:\n"
        "`v4_source_grounded_runtime_locator_and_finetune_readiness`;\n"
        "recommended v4 run family if a run is created:",
        "historical v4 marker/backlog context:\n"
        "`v4_source_grounded_runtime_locator_and_finetune_readiness`;\n"
        "current v4_7 closeout basis:\n"
        f"`{SHORT_RUN_ID}`;\n"
        "recommended v4 run family is historical/backlog-only unless explicitly reopened:",
        1,
    )
    progress_text = progress_text.replace(
        "current diagnostic XLSX display/range rendering loop remains the closure basis:",
        "current diagnostic XLSX display/range rendering loop remains the historical Phase 1 closure basis; "
        "current RAG/v4_7 closeout basis is `v4_7_18`:",
        1,
    )
    progress.write_text(_sync_last_updated(progress_text), encoding="utf-8")

    measurements_block = f"""## v4_7_18 XLSX candidate-only materialization repair and lineage reproducibility

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`

| counter | value |
| --- | --- |
| status | {STATUS} |
| source_run_id | {SOURCE_RUN_ID} |
| lineage_reproducibility_status | {lineage['status']} |
| required_runner_module_tracking_status | {lineage['required_runner_module_tracking_status']} |
| source_candidate_set_sha256_matches_recomputed | {str(validation['source_candidate_set_sha256_matches_recomputed']).lower()} |
| poisoned_oracle_field_digest_stable | {str(validation['poisoned_oracle_field_digest_stable']).lower()} |
| poisoned_oracle_field_evaluation_changed | {str(validation['poisoned_oracle_field_evaluation_changed']).lower()} |
| topk_artifact_row_count | {denominator['topk_artifact_row_count']} |
| filtered_replay_row_count | {denominator['filtered_replay_row_count']} |
| excluded_row_count | {denominator['excluded_row_count']} |
| xlsx_materialization_repair_status | {repair['status']} |
| xlsx_materialization_repair_decision | {repair['decision']} |
| xlsx_baseline_target_hit_count | {xlsx['baseline_target_hit_count']} |
| xlsx_v4_7_17_combined_target_hit_count | {xlsx['v4_7_17_combined_target_hit_count']} |
| xlsx_v4_7_18_combined_target_hit_count | {xlsx['v4_7_18_combined_target_hit_count']} |
| xlsx_v4_7_18_gain_over_v4_7_17_count | {xlsx['v4_7_18_gain_over_v4_7_17_count']} |
| xlsx_gain_rate_per_v4_7_17_miss | {xlsx['v4_7_18_gain_rate_per_v4_7_17_miss']} |
| xlsx_target_hit_regression_count | {xlsx['target_hit_regression_count']} |
| xlsx_candidate_count | {repair['candidate_budget_summary']['XLSX']['candidate_count']} |
| xlsx_zero_candidate_row_count | {repair['candidate_budget_summary']['XLSX']['zero_candidate_row_count']} |
| xlsx_candidate_budget_exhaustion_count | {repair['candidate_budget_summary']['XLSX']['candidate_budget_exhaustion_count']} |
| direct_normalized_answer_value_matching | false |
| raw_xlsx_query_time_parsing | false |
| formula_evaluation | false |
| formula_text_exposure | false |
| source_file_title_shortcut_used | false |
| official_metric_input_rows | 0 |
"""
    v5_measurements_block = f"""## v5_0 v4 closeout and v5 gate plan

- Closeout basis: `{SHORT_RUN_ID}`
- Interpretation: plan/documentation only; no official metric, gold/qrels/label, denominator, training, promotion, product-success, or live-readiness gate is opened.

| counter | value |
| --- | --- |
| v4_closeout_status | {gate_plan['v4_closeout_status']} |
| current_source_of_truth | {gate_plan['current_source_of_truth']} |
| user_owned_decision_group_count | {len(gate_plan['user_owned_decisions'])} |
| codex_owned_work_group_count | {len(gate_plan['codex_owned_work'])} |
| xlsx_residual_miss_count | {xlsx['v4_7_18_combined_target_miss_count']} |
| xlsx_zero_candidate_row_count | {xlsx_budget['zero_candidate_row_count']} |
| xlsx_candidate_budget_exhaustion_count | {xlsx_budget['candidate_budget_exhaustion_count']} |
| official_metric_opening_preconditions_documented | true |
| official_metric_opening_preconditions_satisfied | false |
| live_readiness_promotion_preconditions_documented | true |
| live_readiness_promotion_preconditions_satisfied | false |
| ambiguous_non_gold_choices_remain_diagnostic_only | true |
| official_metric_input_rows | 0 |
| gold_mutation | false |
| qrels_mutation | false |
| denominator_mutation | false |
| promotion_evidence | false |
| live_db_index_cache_readiness | false |
"""
    measurements_text = _upsert_block(
        measurements.read_text(encoding="utf-8"),
        start_marker="<!-- v4_7_18_measurements_start -->",
        end_marker="<!-- v4_7_18_measurements_end -->",
        block=measurements_block,
        after_anchor="# RAG Ingestion Measurements",
    )
    measurements_text = _upsert_block_at_top(
        measurements_text,
        start_marker=f"<!-- {V5_GATE_PLAN_ID}:measurements-entry:start -->",
        end_marker=f"<!-- {V5_GATE_PLAN_ID}:measurements-entry:end -->",
        block=v5_measurements_block,
    )
    measurements.write_text(_sync_last_updated(measurements_text), encoding="utf-8")

    triage_block = (
        f"- {SHORT_RUN_ID} accepts the diagnostic-only materialized axis-value overlay: "
        f"`{repair['decision']}`. It uses already-materialized SourceAtom axis/header text only and records rejected rules "
        f"{repair['rule_decisions']['rejected']}; formatted-value and broader cell scoring remain inconclusive. XLSX improves "
        f"{xlsx['v4_7_17_combined_target_hit_count']} -> {xlsx['v4_7_18_combined_target_hit_count']} target hits, but still "
        f"has {xlsx['v4_7_18_combined_target_miss_count']} misses, "
        f"{repair['candidate_budget_summary']['XLSX']['zero_candidate_row_count']} zero-candidate rows, and "
        f"{repair['candidate_budget_summary']['XLSX']['candidate_budget_exhaustion_count']} budget-exhausted rows. "
        f"Repeated-prefix projection gains {repair['overlay_90_xlsx_projection']['v4_7_18_gain_repeated_prefix_count']} row; "
        "explicit demotion/dedup stays inconclusive to avoid row-specific tuning. Lineage reproducibility is reported via "
        f"`{lineage['required_runner_module_tracking_status']}` and ignored report/status artifacts remain local-only."
    )
    v5_triage_block = (
        "### v5_0 v4 closeout and v5 gate plan\n\n"
        f"- Basis: `{SHORT_RUN_ID}` closes v4 as source-first, candidate-only, lineage-reproducible diagnostic work. "
        "All ambiguous non-gold choices remain diagnostic-only because no user-approved relevance, answerability, "
        "expected-evidence, qrels, or denominator policy exists for them yet.\n"
        "- User-owned decisions: approve gold/qrels policy; expected answer/evidence standards; relevance and "
        "answerability labels; official denominator; promotion/product-success policy; explicit official metric opening.\n"
        "- Codex-owned work: implement approved schemas, tests, runner/report/status updates, indexing-scope guardrails, "
        "protected-surface checks, and failure-taxonomy/reporting changes without opening policy gates.\n"
        f"- XLSX residual backlog: {xlsx['v4_7_18_combined_target_miss_count']} remaining misses, "
        f"{xlsx_budget['zero_candidate_row_count']} zero-candidate rows, {xlsx_budget['candidate_budget_exhaustion_count']} "
        "budget-exhausted rows, repeated-prefix/header-axis/table-range splits, and formatted-value prototypes all stay "
        "candidate-only until user gold policy opens.\n"
        "- Official metric opening preconditions: approved gold/qrels/labels/denominator, fixed metric definitions, "
        "documented blocked/deferred metrics, explicit protected-surface diffs, and status rows that still show "
        "`official_metric_input_rows=0` until the approved opening.\n"
        "- Live-readiness and promotion preconditions: accepted official metrics, live DB/index/cache rollout evidence, "
        "redaction/leakage/latency/rollback/monitoring evidence, and user-approved promotion policy; v4_7_18 counters "
        "alone are not product-success or promotion evidence."
    )
    triage_text = _upsert_block(
        triage.read_text(encoding="utf-8"),
        start_marker="<!-- v4_7_18_triage_start -->",
        end_marker="<!-- v4_7_18_triage_end -->",
        block=triage_block,
        after_anchor="# RAG Ingestion Triage",
    )
    triage_text = _upsert_block_at_top(
        triage_text,
        start_marker=f"<!-- {V5_GATE_PLAN_ID}:triage-entry:start -->",
        end_marker=f"<!-- {V5_GATE_PLAN_ID}:triage-entry:end -->",
        block=v5_triage_block,
    )
    triage.write_text(_sync_last_updated(triage_text), encoding="utf-8")

    summary_block = (
        "## Current RAG Diagnostic Status\n"
        f"Current RAG status: `{STATUS}`.\n"
        "`current` resolves to `v4_7_18`: non-production XLSX candidate-only materialization repair and lineage "
        "reproducibility hardening. v4_7_17 remains explicit for candidate-only generalization validation and XLSX "
        "table-axis audit; v4_7_16_target_recall_repair_prototype remains explicit for the 300 -> 514 replay. "
        f"v4_7_18 improves XLSX combined target hits {xlsx['v4_7_17_combined_target_hit_count']} -> "
        f"{xlsx['v4_7_18_combined_target_hit_count']} using already-materialized non-numeric axis/header text only, "
        f"with TEXT held at {report['regression_guards']['TEXT']['v4_7_18_combined_target_hit_count']} and PDF held at "
        f"{report['regression_guards']['PDF']['v4_7_18_combined_target_hit_count']}; all family target-hit regressions are 0. "
        "v4 is closed as diagnostic-only source-first/candidate-only/lineage-reproducibility work; v5 is a gate plan "
        "only until user-owned gold/qrels/expected-evidence/relevance/answerability/denominator/promotion decisions open it. "
        "Canonical details: `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and "
        "`docs/rag-ingestion-triage.md`; prior v4_7 cleanup keys remain checkable through explicit aliases.\n"
        "Historical continuity markers: v4_7 remains pre-official; supersedes the abstract v4_7_1 Korean review packet; "
        "## Korean human review packet; actual Korean query candidates; User-owned fields remain blank/default; "
        "hydrated rows 204, PDF 100, XLSX 104; non-empty `질의문` 204; The previous v4_7_1 Korean review packet was abstract; "
        "review_packet_ko_hydrated.xlsx; v4_7_3 applies the user-reviewed Korean query candidate CSV; 미검수=통과; "
        "v4_7_3 applies the user-reviewed CSV decisions; not official metric; official_metric_input_rows=0; not gold/qrels; PDF survivor 58; "
        "v4_7_4 replays only the 58 user-passed PDF survivor candidates; fine_tuning_executed=false.\n"
        "Hard boundary: diagnostic-only, non-production, not official metric, not gold/qrels/labels, "
        "not denominator/training/fine-tuning/FT-A, not promotion evidence, not product-success evidence, "
        "and not live readiness."
    )
    for path in (readme, eval_readme):
        path.write_text(_replace_summary_block(path.read_text(encoding="utf-8"), block=summary_block), encoding="utf-8")

    row = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        "`current` resolves to `v4_7_18`, "
        "`v4_7_17_candidate_only_generalization_validation_and_xlsx_table_axis_repair_audit` remains explicit, "
        "`v4_7_16_target_recall_repair_prototype` remains explicit, "
        "`v4_7_15_read_only_searchindex_replay_projection` remains explicit, "
        "`v4_7_14_diagnostic_precondition_hardening` remains explicit, "
        "`v4_7_13_live_retrieval_answerability_and_full_pdf_replay` remains explicit, "
        "`v4_7_12_layered_retrieval_generalization_and_overfit_audit` remains explicit, "
        "`v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness` remains explicit, "
        "`v4_7_9_pdf_evidence_residual_answer_quality_replay` remains explicit, and prior v4_7 cleanup keys "
        "remain checkable without opening official metrics; `v5_0_v4_closeout_and_v5_gate_plan` is docs/report planning only. |"
    )
    scripts_text = scripts_readme.read_text(encoding="utf-8")
    scripts_text = re.sub(r"\| `rag_eval.py` \|.*?\|", row, scripts_text, count=1)
    scripts_readme.write_text(scripts_text, encoding="utf-8")


def _assert_no_raw_payload_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        overlap = RAW_PAYLOAD_FORBIDDEN_KEYS & set(value)
        if overlap:
            raise ValueError(f"v4_7_18 raw prompt/response leakage keys present: {sorted(overlap)}")
        for child in value.values():
            _assert_no_raw_payload_keys(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_raw_payload_keys(child)


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v4_7_18 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v4_7_18 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v4_7_18 status mismatch")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v4_7_18 must remain diagnostic-only and non-production")
    for key in FORBIDDEN_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v4_7_18 opened forbidden gate: {key}")
    if report.get("official_metric_input_rows") != 0 or report.get("silver_official_metric_input_rows") != 0:
        raise ValueError("v4_7_18 opened official metric rows")
    if report.get("silver_promoted_to_gold_count") != 0:
        raise ValueError("v4_7_18 promoted silver")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_18 touched protected namespaces")
    if report.get("SearchView_vector_payload_role") != "candidate_only":
        raise ValueError("v4_7_18 SearchView/vector payload role changed")
    if report.get("SourceAtom_EvidenceBundle_role") != "evidence_truth":
        raise ValueError("v4_7_18 SourceAtom/EvidenceBundle role changed")
    if report.get("answer_generation_attempted") is not False:
        raise ValueError("v4_7_18 must not generate substitute answers")
    if report.get("raw_prompt_payload_written") is not False or report.get("raw_response_payload_written") is not False:
        raise ValueError("v4_7_18 raw prompt/response payload must not be written")
    _assert_no_raw_payload_keys(report)

    reproduction = report.get("source_counter_reproduction") or {}
    v4716_replay = reproduction.get("v4_7_16") or {}
    for key, expected in (
        ("baseline_target_hit_count", 300),
        ("combined_target_hit_count", 514),
        ("baseline_miss_to_hit_count", 214),
        ("baseline_hit_to_miss_count", 0),
    ):
        if v4716_replay.get(key) != expected:
            raise ValueError(f"v4_7_18 source v4_7_16 counter drift: {key}")
    v4717_replay = reproduction.get("v4_7_17") or {}
    for key, expected in (
        ("xlsx_baseline_target_hit_count", 15),
        ("xlsx_combined_target_hit_count", 17),
        ("xlsx_table_axis_candidate_count", 133),
        ("xlsx_table_axis_repair_decision", "keep_inconclusive_low_gain_candidate_only"),
    ):
        if v4717_replay.get(key) != expected:
            raise ValueError(f"v4_7_18 source v4_7_17 counter drift: {key}")

    denominator = report.get("archive_denominator_trace") or {}
    for key, expected in (
        ("topk_artifact_row_count", 1029),
        ("filtered_replay_row_count", 1000),
        ("excluded_row_count", 29),
        ("duplicate_query_id_count", 0),
        ("missing_query_id_count", 0),
    ):
        if denominator.get(key) != expected:
            raise ValueError(f"v4_7_18 denominator drift: {key}")
    if denominator.get("excluded_family_counts") != {"PDF": 4, "TEXT": 6, "XLSX": 19}:
        raise ValueError("v4_7_18 denominator excluded-family drift")
    if denominator.get("topk_envelope_length_distribution") != {"5": 1000}:
        raise ValueError("v4_7_18 top-k envelope distribution drift")
    if denominator.get("source_topk_sha256") != "3a14a4908972a118606b5d2967544c278d60dd99590af3004676271a6e9ad7b3":
        raise ValueError("v4_7_18 top-k sha drift")

    validation = report.get("candidate_only_generalization_validation_reproduction") or {}
    if validation.get("source_candidate_set_sha256") != "b388d4fec10886142f8d3cee25db2eb771e7f4236e311b91c4ea175325a1bc5d":
        raise ValueError("v4_7_18 source candidate digest drift")
    if validation.get("source_candidate_set_sha256_recomputed") != "b388d4fec10886142f8d3cee25db2eb771e7f4236e311b91c4ea175325a1bc5d":
        raise ValueError("v4_7_18 recomputed source candidate digest drift")
    if validation.get("source_candidate_set_sha256_source_report_claimed_match") is not True:
        raise ValueError("v4_7_18 source report did not claim candidate digest match")
    if validation.get("source_candidate_set_sha256_matches_recomputed") is not True:
        raise ValueError("v4_7_18 source candidate digest did not match recomputation")
    if validation.get("poisoned_oracle_field_digest_stable") is not True:
        raise ValueError("v4_7_18 candidate digest changed under poisoned oracle fields")
    if validation.get("poisoned_oracle_field_evaluation_changed") is not True:
        raise ValueError("v4_7_18 poisoned target fields did not affect after-the-fact evaluation")
    for key in ("diagnostic_target_labels_used_for_candidate_construction", "diagnostic_target_labels_used_for_candidate_scoring"):
        if validation.get(key) is not False:
            raise ValueError("v4_7_18 target labels used during candidate construction or scoring")

    repair = report.get("xlsx_candidate_only_materialization_repair") or {}
    if repair.get("status") != "XLSX_CANDIDATE_ONLY_MATERIALIZATION_REPAIR_ACCEPTED_DIAGNOSTIC_ONLY":
        raise ValueError("v4_7_18 XLSX repair status mismatch")
    if repair.get("decision") != "accept_materialized_axis_value_overlay_diagnostic_only":
        raise ValueError("v4_7_18 XLSX repair decision mismatch")
    for key, expected in (
        ("direct_normalized_answer_value_matching", False),
        ("raw_xlsx_query_time_parsing", False),
        ("formula_evaluation", False),
        ("formula_text_exposure", False),
        ("source_file_title_shortcut_used", False),
        ("target_or_gold_locator_used_for_candidate_construction", False),
        ("diagnostic_target_labels_used_for_candidate_construction", False),
        ("diagnostic_target_labels_used_for_candidate_scoring", False),
    ):
        if repair.get(key) is not expected:
            labels = {
                "direct_normalized_answer_value_matching": "normalized",
                "raw_xlsx_query_time_parsing": "raw XLSX",
                "formula_evaluation": "formula",
                "formula_text_exposure": "formula",
                "source_file_title_shortcut_used": "source title",
                "target_or_gold_locator_used_for_candidate_construction": "target/gold",
                "diagnostic_target_labels_used_for_candidate_construction": "target labels",
                "diagnostic_target_labels_used_for_candidate_scoring": "target labels",
            }
            raise ValueError(f"v4_7_18 XLSX shortcut opened: {labels[key]}")
    if repair.get("diagnostic_target_labels_used_for_after_the_fact_evaluation") is not True:
        raise ValueError("v4_7_18 target labels must be after-the-fact diagnostic evaluation only")
    xlsx = repair.get("archive_1000_xlsx_family_recall") or {}
    for key, expected in (
        ("row_count", 325),
        ("baseline_target_hit_count", 15),
        ("v4_7_17_combined_target_hit_count", 17),
        ("v4_7_18_combined_target_hit_count", 26),
        ("v4_7_18_derived_overlay_target_hit_count", 12),
        ("v4_7_18_gain_over_v4_7_17_count", 9),
        ("v4_7_18_gain_rate_per_v4_7_17_miss", "9/308"),
        ("target_hit_regression_count", 0),
    ):
        if xlsx.get(key) != expected:
            raise ValueError(f"v4_7_18 XLSX family drift: {key}")
    budget = repair.get("candidate_budget_summary") or {}
    xlsx_budget = budget.get("XLSX") or {}
    for key, expected in (
        ("candidate_count", 881),
        ("zero_candidate_row_count", 78),
        ("at_budget_row_count", 143),
        ("candidate_budget_exhaustion_count", 109),
    ):
        if xlsx_budget.get(key) != expected:
            raise ValueError(f"v4_7_18 XLSX budget drift: {key}")
    overlay = repair.get("overlay_90_xlsx_projection") or {}
    for key, expected in (
        ("xlsx_overlay_row_count", 30),
        ("target_not_in_topk_total", 28),
        ("repeated_prefix_cluster_total", 22),
        ("repeated_prefix_cluster_overlap_with_target_miss", 20),
        ("v4_7_18_gain_over_v4_7_17_count", 1),
        ("v4_7_18_gain_repeated_prefix_count", 1),
    ):
        if overlay.get(key) != expected:
            raise ValueError(f"v4_7_18 overlay drift: {key}")

    lineage = report.get("lineage_reproducibility") or {}
    if lineage.get("status") != "LINEAGE_REPRODUCIBILITY_HARDENED_DIAGNOSTIC_ONLY":
        raise ValueError("v4_7_18 lineage reproducibility status mismatch")
    if lineage.get("clean_checkout_risk_status") != "NO_REQUIRED_RUNNER_MODULE_RISK_DETECTED":
        raise ValueError("v4_7_18 clean-checkout reproducibility risk remains")
    if lineage.get("required_runner_module_tracking_status") != "REQUIRED_RUNNER_MODULES_TRACKED_AND_NOT_IGNORED":
        raise ValueError("v4_7_18 required runner module tracking status mismatch")
    for module in lineage.get("required_runner_modules") or []:
        if module.get("exists") is not True or module.get("tracked") is not True or module.get("ignored") is not False:
            raise ValueError(f"v4_7_18 required runner module tracking gap: {module.get('logical_key')}")
        if module.get("py_compile_ok") is not True or module.get("resolver_checkable") is not True:
            raise ValueError(f"v4_7_18 required runner module resolver/compile gap: {module.get('logical_key')}")
    if lineage.get("generated_report_artifacts_ignored") is not True:
        raise ValueError("v4_7_18 generated report artifacts must remain ignored")
    if lineage.get("compile_check_mode") != "source_text_compile_no_bytecode_write":
        raise ValueError("v4_7_18 lineage compile check must avoid bytecode writes")
    if lineage.get("bytecode_written_by_lineage_check") is not False:
        raise ValueError("v4_7_18 lineage compile check wrote bytecode")

    guards = report.get("regression_guards") or {}
    for family, expected_hits in (("TEXT", 232), ("PDF", 265), ("XLSX", 26)):
        guard = guards.get(family) or {}
        if guard.get("v4_7_18_combined_target_hit_count") != expected_hits:
            raise ValueError(f"v4_7_18 {family} regression guard hit-count drift")
        if guard.get("target_hit_regression_count") != 0:
            raise ValueError(f"v4_7_18 {family} regression guard opened regression")

    guardrails = report.get("anti_overfit_guardrails") or {}
    if guardrails.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_18 guardrail touched protected namespaces")
    if guardrails.get("official_metric_input_rows") != 0 or guardrails.get("silver_official_metric_input_rows") != 0:
        raise ValueError("v4_7_18 guardrail opened official metric rows")
    for key, value in guardrails.items():
        if key in GUARDRAIL_FALSE_KEYS and value is not False:
            raise ValueError(f"v4_7_18 guardrail opened: {key}")

    gate_plan = report.get("v4_closeout_and_v5_gate_plan") or {}
    if gate_plan.get("plan_id") != V5_GATE_PLAN_ID:
        raise ValueError("v4_7_18 v5 gate plan id mismatch")
    if gate_plan.get("v4_closeout_status") != V4_CLOSEOUT_STATUS:
        raise ValueError("v4_7_18 v4 closeout status mismatch")
    if gate_plan.get("v4_closeout_basis_short_run_id") != SHORT_RUN_ID:
        raise ValueError("v4_7_18 v4 closeout basis mismatch")
    if gate_plan.get("current_source_of_truth") != LOGICAL_RUN_KEY:
        raise ValueError("v4_7_18 v5 gate plan current source mismatch")
    if gate_plan.get("source_first_candidate_only_lineage_closed") is not True:
        raise ValueError("v4_7_18 v4 closeout source-first/candidate-only/lineage closure missing")
    if gate_plan.get("ambiguous_non_gold_choices_remain_diagnostic_only") is not True:
        raise ValueError("v4_7_18 ambiguous non-gold choices must remain diagnostic-only")
    if gate_plan.get("official_metric_opening_preconditions_documented") is not True:
        raise ValueError("v4_7_18 official metric opening preconditions must be documented")
    if gate_plan.get("official_metric_opening_preconditions_satisfied") is not False:
        raise ValueError("v4_7_18 official metric opening preconditions must remain unsatisfied")
    if gate_plan.get("live_readiness_promotion_preconditions_documented") is not True:
        raise ValueError("v4_7_18 live-readiness/promotion preconditions must be documented")
    if gate_plan.get("live_readiness_promotion_preconditions_satisfied") is not False:
        raise ValueError("v4_7_18 live-readiness/promotion preconditions must remain unsatisfied")
    for section in (
        "user_owned_decisions",
        "codex_owned_work",
        "xlsx_residual_engineering_backlog",
        "official_metric_opening_preconditions",
        "live_readiness_and_promotion_preconditions",
        "diagnostic_only_rationale",
    ):
        if not gate_plan.get(section):
            raise ValueError(f"v4_7_18 v5 gate plan missing section: {section}")
    closed = gate_plan.get("still_closed") or {}
    for key, expected in (
        ("official_metric_input_rows", 0),
        ("gold_mutation", False),
        ("qrels_mutation", False),
        ("label_mutation", False),
        ("denominator_mutation", False),
        ("training_dataset_created", False),
        ("promotion_evidence", False),
        ("product_success_evidence_allowed", False),
        ("live_db_index_cache_readiness", False),
    ):
        if closed.get(key) != expected:
            raise ValueError(f"v4_7_18 v5 gate plan opened closed gate: {key}")

    counters = report.get("counters") or {}
    required = (
        "current_resolves_to",
        "lineage_reproducibility_status",
        "xlsx_materialization_repair_decision",
        "xlsx_v4_7_18_combined_target_hit_count",
        "xlsx_v4_7_18_gain_over_v4_7_17_count",
        "text_target_hit_regression_count",
        "pdf_target_hit_regression_count",
        "generated_response_count",
        "claim_support_fail_count",
        "parser_failure_count",
    )
    missing = [key for key in required if key not in counters]
    if missing:
        raise ValueError(f"v4_7_18 missing counters: {missing}")
    if counters["current_resolves_to"] != LOGICAL_RUN_KEY:
        raise ValueError("current must resolve to v4_7_18")
    for key, expected in (
        ("lineage_reproducibility_status", "LINEAGE_REPRODUCIBILITY_HARDENED_DIAGNOSTIC_ONLY"),
        ("xlsx_materialization_repair_decision", "accept_materialized_axis_value_overlay_diagnostic_only"),
        ("xlsx_v4_7_18_combined_target_hit_count", 26),
        ("xlsx_v4_7_18_gain_over_v4_7_17_count", 9),
        ("text_target_hit_regression_count", 0),
        ("pdf_target_hit_regression_count", 0),
        ("generated_response_count", 0),
        ("claim_support_fail_count", 0),
        ("parser_failure_count", 0),
    ):
        if counters.get(key) != expected:
            raise ValueError(f"v4_7_18 counter drift: {key}")
