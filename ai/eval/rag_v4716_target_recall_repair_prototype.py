from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v4712_layered_retrieval_generalization_and_overfit_audit as v4712
from ai.eval import rag_v4715_read_only_searchindex_replay_projection as v4715
from ai.eval import rag_v476_archive_purge as v476


LOGICAL_RUN_KEY = "v4_7_16"
SHORT_RUN_ID = "v4_7_16_target_recall_repair_prototype"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_16_"
    "target_recall_repair_prototype_nonprod"
)
STATUS = "V4_7_16_TARGET_RECALL_REPAIR_PROTOTYPE_NONPROD_READY"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
SOURCE_REGISTRY_JSONL = Path("ai/eval/source_registry/source_atom_registry_v1.jsonl")
SOURCE_RUN_ID = v4715.SHORT_RUN_ID
SOURCE_REPORT_JSON = v4715.SHORT_REPORT_PATH
SOURCE_TOPK_ROWS = v4712.V3_7_2_TOPK_ROWS
SOURCE_OVERLAY_JSON = v4715.SOURCE_OVERLAY_JSON

FAMILIES = ("TEXT", "PDF", "XLSX")
REPAIR_FAMILIES = ("TEXT", "XLSX")
EXPECTED_FAMILY_TOTALS = {"TEXT": 350, "PDF": 325, "XLSX": 325}
EXPECTED_BASELINE_HITS = {"TEXT": 20, "PDF": 265, "XLSX": 15}
EXPECTED_PROTOTYPE_CANDIDATES = {"TEXT": 1714, "PDF": 0, "XLSX": 133}
EXPECTED_COMBINED_HITS = {"TEXT": 232, "PDF": 265, "XLSX": 17}
EXPECTED_BASELINE_MISS_TO_HIT = {"TEXT": 212, "PDF": 0, "XLSX": 2}
KST_DOC_DATE = "2026-05-31"
CANDIDATE_BUDGET_PER_QUERY = 5
TEXT_MIN_TOKEN_OVERLAP = 2
XLSX_MIN_TOKEN_OVERLAP = 1
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")

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

_SOURCE_INDEX_CACHE: dict[str, dict[str, Any]] = {}


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


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _counter_dict(counter: Counter[str] | None = None) -> dict[str, int]:
    counter = counter or Counter()
    return {family: int(counter.get(family, 0)) for family in FAMILIES}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _tokenize(value: str) -> frozenset[str]:
    return frozenset(token.lower() for token in TOKEN_RE.findall(value or "") if len(token) >= 2)


def _load_source_report(root: Path, source_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    report = dict(source_report or registry.load_report("v4_7_15", root=root))
    v4715.check_report(report)
    return report


def _load_silver_topk_rows(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, resolution = v4715._load_silver_topk_rows(root)
    if len(rows) != 1000:
        raise ValueError("v4_7_16 expected the 1000-row archived silver top-k replay source")
    if not resolution.get("sha256_verified") or not resolution.get("resolved_via_archive"):
        raise ValueError("v4_7_16 requires the v3_7_2 archived top-k source to be sha-verified")
    return rows, resolution


def _baseline_atom_ids(row: Mapping[str, Any]) -> set[str]:
    atom_ids: set[str] = set()
    for envelope in row.get("top_result_envelopes") or []:
        atom_id = _clean(envelope.get("source_atom_id"))
        if atom_id:
            atom_ids.add(atom_id)
        for nested in envelope.get("source_atom_ids") or []:
            nested_id = _clean(nested)
            if nested_id:
                atom_ids.add(nested_id)
    return atom_ids


def _target_atom_ids(row: Mapping[str, Any]) -> set[str]:
    return {_clean(atom_id) for atom_id in row.get("target_source_atom_ids") or [] if _clean(atom_id)}


def _safe_source_registry_text(row: Mapping[str, Any], family: str) -> str:
    if family == "TEXT":
        return _clean(row.get("normalized_text_or_value_snapshot"))
    if family == "XLSX":
        locator = row.get("raw_locator") or {}
        if not isinstance(locator, Mapping):
            return ""
        return " ".join(
            _clean(locator.get(key))
            for key in ("sheet", "row_label", "column_label", "range")
            if _clean(locator.get(key))
        )
    return ""


def _needed_query_tokens(silver_topk_rows: Sequence[Mapping[str, Any]]) -> dict[str, frozenset[str]]:
    tokens_by_family: dict[str, set[str]] = {family: set() for family in REPAIR_FAMILIES}
    for row in silver_topk_rows:
        family = _clean(row.get("source_family")).upper()
        if family in tokens_by_family:
            tokens_by_family[family].update(_tokenize(_clean(row.get("query_text"))))
    return {family: frozenset(tokens) for family, tokens in tokens_by_family.items()}


def _index_cache_key(root: Path, needed_tokens: Mapping[str, frozenset[str]]) -> str:
    payload = {
        "source_registry": SOURCE_REGISTRY_JSONL.as_posix(),
        "needed_tokens": {family: sorted(tokens) for family, tokens in needed_tokens.items()},
        "text_fields": {
            "TEXT": ["normalized_text_or_value_snapshot"],
            "XLSX": ["raw_locator.sheet", "raw_locator.row_label", "raw_locator.column_label", "raw_locator.range"],
        },
        "root": str((root / SOURCE_REGISTRY_JSONL).resolve()),
    }
    return _sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _build_source_registry_candidate_index(
    *,
    root: Path,
    needed_tokens: Mapping[str, frozenset[str]],
) -> dict[str, Any]:
    cache_key = _index_cache_key(root, needed_tokens)
    cached = _SOURCE_INDEX_CACHE.get(cache_key)
    if cached is not None:
        return cached

    source_registry_path = root / SOURCE_REGISTRY_JSONL
    if not source_registry_path.exists():
        raise FileNotFoundError(f"missing source registry: {SOURCE_REGISTRY_JSONL}")

    postings: dict[str, dict[str, list[str]]] = {
        family: defaultdict(list) for family in REPAIR_FAMILIES
    }
    scanned = Counter()
    indexed = Counter()
    tokenized = Counter()

    with source_registry_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            family = _clean(row.get("source_family")).upper()
            if family not in REPAIR_FAMILIES:
                continue
            scanned[family] += 1
            atom_id = _clean(row.get("source_atom_id"))
            if not atom_id:
                continue
            safe_text = _safe_source_registry_text(row, family)
            source_tokens = _tokenize(safe_text)
            if not source_tokens:
                continue
            tokenized[family] += 1
            overlapping_tokens = source_tokens & needed_tokens.get(family, frozenset())
            if not overlapping_tokens:
                continue
            indexed[family] += 1
            for token in overlapping_tokens:
                postings[family][token].append(atom_id)

    index = {
        "schema_version": f"{SHORT_RUN_ID}_source_registry_candidate_index_v1",
        "source_registry_logical_path": SOURCE_REGISTRY_JSONL.as_posix(),
        "candidate_only": True,
        "raw_pdf_query_time_parsing": False,
        "raw_xlsx_query_time_parsing": False,
        "direct_normalized_answer_value_matching": False,
        "source_file_title_shortcut_used": False,
        "source_registry_mutated": False,
        "index_rebuilt": False,
        "source_atoms_scanned_count_by_family": _counter_dict(scanned),
        "source_atoms_tokenized_count_by_family": _counter_dict(tokenized),
        "source_atoms_indexed_count_by_family": _counter_dict(indexed),
        "postings": {family: dict(tokens) for family, tokens in postings.items()},
    }
    _SOURCE_INDEX_CACHE[cache_key] = index
    return index


def _rank_candidate_ids(
    *,
    family: str,
    query_tokens: frozenset[str],
    postings: Mapping[str, Sequence[str]],
) -> list[str]:
    scores: Counter[str] = Counter()
    for token in query_tokens:
        for atom_id in postings.get(token, ()):
            scores[atom_id] += 1
    min_overlap = TEXT_MIN_TOKEN_OVERLAP if family == "TEXT" else XLSX_MIN_TOKEN_OVERLAP
    ranked = [
        (atom_id, score)
        for atom_id, score in scores.items()
        if score >= min_overlap
    ]
    ranked.sort(key=lambda item: (-item[1], item[0]))
    return [atom_id for atom_id, _score in ranked[:CANDIDATE_BUDGET_PER_QUERY]]


def _candidate_sets_for_rows(
    *,
    silver_topk_rows: Sequence[Mapping[str, Any]],
    index: Mapping[str, Any],
) -> tuple[list[list[str]], str]:
    candidate_sets: list[list[str]] = []
    digest_rows: list[dict[str, Any]] = []
    postings_by_family = index["postings"]
    for ordinal, row in enumerate(silver_topk_rows):
        family = _clean(row.get("source_family")).upper()
        if family not in REPAIR_FAMILIES:
            candidate_sets.append([])
            continue
        query_text = _clean(row.get("query_text"))
        candidates = _rank_candidate_ids(
            family=family,
            query_tokens=_tokenize(query_text),
            postings=postings_by_family.get(family) or {},
        )
        candidate_sets.append(candidates)
        digest_rows.append(
            {
                "ordinal": ordinal,
                "family": family,
                "query_text_sha256": _sha256_text(query_text),
                "candidate_source_atom_ids": candidates,
            }
        )
    candidate_set_sha256 = _sha256_text(json.dumps(digest_rows, ensure_ascii=False, sort_keys=True))
    return candidate_sets, candidate_set_sha256


def _evaluate_candidate_sets(
    *,
    silver_topk_rows: Sequence[Mapping[str, Any]],
    candidate_sets: Sequence[Sequence[str]],
    candidate_set_sha256: str,
) -> dict[str, Any]:
    totals = Counter()
    baseline_hits = Counter()
    prototype_hits = Counter()
    combined_hits = Counter()
    baseline_miss_to_hit = Counter()
    baseline_hit_to_miss = Counter()
    candidate_counts = Counter()
    attempted = Counter()

    for row, candidate_ids in zip(silver_topk_rows, candidate_sets, strict=True):
        family = _clean(row.get("source_family")).upper()
        totals[family] += 1
        target_ids = _target_atom_ids(row)
        baseline_ids = _baseline_atom_ids(row)
        candidate_id_set = set(candidate_ids)
        baseline_hit = bool(target_ids & baseline_ids)
        prototype_hit = bool(target_ids & candidate_id_set)
        combined_hit = bool(target_ids & (baseline_ids | candidate_id_set))
        if family in REPAIR_FAMILIES:
            attempted[family] += 1
            candidate_counts[family] += len(candidate_ids)
        if baseline_hit:
            baseline_hits[family] += 1
        if prototype_hit:
            prototype_hits[family] += 1
        if combined_hit:
            combined_hits[family] += 1
        if not baseline_hit and combined_hit:
            baseline_miss_to_hit[family] += 1
        if baseline_hit and not combined_hit:
            baseline_hit_to_miss[family] += 1

    family_summaries: dict[str, dict[str, Any]] = {}
    for family in FAMILIES:
        total = int(totals.get(family, 0))
        baseline_hit = int(baseline_hits.get(family, 0))
        prototype_hit = int(prototype_hits.get(family, 0))
        combined_hit = int(combined_hits.get(family, 0))
        regression = int(baseline_hit_to_miss.get(family, 0))
        family_summaries[family] = {
            "row_count": total,
            "baseline_target_hit_count": baseline_hit,
            "baseline_target_miss_count": total - baseline_hit,
            "prototype_attempted_row_count": int(attempted.get(family, 0)),
            "prototype_candidate_count": int(candidate_counts.get(family, 0)),
            "prototype_target_hit_count": prototype_hit,
            "combined_target_hit_count": combined_hit,
            "combined_target_miss_count": total - combined_hit,
            "baseline_miss_to_hit_count": int(baseline_miss_to_hit.get(family, 0)),
            "baseline_hit_to_miss_count": regression,
            "target_hit_regression_count": regression,
        }

    baseline_target_hit_count = sum(baseline_hits.values())
    combined_target_hit_count = sum(combined_hits.values())
    baseline_hit_to_miss_count = sum(baseline_hit_to_miss.values())
    return {
        "schema_version": f"{SHORT_RUN_ID}_archive_1000_target_recall_v1",
        "scope": "archived_v3_7_2_silver_1000_read_only_topk",
        "candidate_set_sha256": candidate_set_sha256,
        "row_count": len(silver_topk_rows),
        "baseline_target_hit_count": int(baseline_target_hit_count),
        "baseline_target_miss_count": len(silver_topk_rows) - int(baseline_target_hit_count),
        "combined_target_hit_count": int(combined_target_hit_count),
        "combined_target_miss_count": len(silver_topk_rows) - int(combined_target_hit_count),
        "baseline_miss_to_hit_count": int(sum(baseline_miss_to_hit.values())),
        "baseline_hit_to_miss_count": int(baseline_hit_to_miss_count),
        "families": family_summaries,
    }


def _overlay_90_root_cause_summary(source_report: Mapping[str, Any]) -> dict[str, Any]:
    projection = source_report.get("diagnostic_retrieval_evidence_repair_projection") or {}
    primary = projection.get("primary_projection_counts") or {}
    overlap = projection.get("root_cause_overlap_matrix_by_family") or {}
    return {
        "schema_version": f"{SHORT_RUN_ID}_overlay_90_root_cause_summary_v1",
        "diagnostic_only": True,
        "source_run_id": SOURCE_RUN_ID,
        "source_overlay_json": SOURCE_OVERLAY_JSON.as_posix(),
        "row_count": _as_int(projection.get("projection_input_row_count")),
        "counts_by_family": projection.get("projection_counts_by_family") or {},
        "primary_projection_counts": primary,
        "root_cause_overlap_matrix_by_family": overlap,
        "silver_mutation": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
    }


def _candidate_construction_policy() -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_candidate_construction_policy_v1",
        "SearchView_vector_payload_role": "candidate_only",
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "candidate_budget_per_query": CANDIDATE_BUDGET_PER_QUERY,
        "text_min_token_overlap": TEXT_MIN_TOKEN_OVERLAP,
        "xlsx_min_token_overlap": XLSX_MIN_TOKEN_OVERLAP,
        "fixed_thresholds_declared_before_target_evaluation": True,
        "threshold_tuning_used": False,
        "diagnostic_target_labels_used_for_candidate_construction": False,
        "diagnostic_target_labels_used_for_candidate_scoring": False,
        "diagnostic_target_labels_used_for_after_the_fact_evaluation": True,
        "raw_pdf_query_time_parsing": False,
        "raw_xlsx_query_time_parsing": False,
        "direct_normalized_answer_value_matching": False,
        "formula_evaluation": False,
        "formula_text_exposure": False,
        "source_file_title_shortcut_used": False,
        "case_id_query_id_or_file_name_hack_used": False,
        "hidden_locator_or_gold_field_use_count": 0,
        "allowed_candidate_construction_fields": {
            "query": ["query_text", "source_family"],
            "source_registry": {
                "TEXT": ["source_family", "source_atom_id", "normalized_text_or_value_snapshot"],
                "XLSX": [
                    "source_family",
                    "source_atom_id",
                    "raw_locator.sheet",
                    "raw_locator.row_label",
                    "raw_locator.column_label",
                    "raw_locator.range",
                ],
            },
        },
        "forbidden_candidate_construction_fields": [
            "target_source_atom_ids",
            "target_hit_at_k",
            "target_hit_in_topk",
            "target_rank_at_k",
            "question_gold_locator_target",
            "official_manifest_target",
            "target_mapping_audit",
            "supporting_evidence",
            "expected_answer",
            "expected_evidence",
            "query_id",
            "case_id",
            "file_name",
            "workbook",
            "source_file_path",
            "source_path",
            "retrieval_title",
            "raw_locator.title",
            "raw_locator.workbook",
            "raw_locator.source_file_path",
            "raw_locator.source_path",
            "raw_locator.normalized_value",
            "raw_locator.cell",
            "formula",
            "formula_text",
        ],
    }


def _repair_idea_decisions(archive: Mapping[str, Any]) -> dict[str, Any]:
    families = archive["families"]
    return {
        "accepted": [
            {
                "idea_id": "TEXT_SAFE_LEXICAL_SEARCHUNIT_SEARCHVIEW_REPAIR",
                "family": "TEXT",
                "decision": "accepted_for_future_candidate_experimentation_only",
                "reason": "generalized source-registry text SearchUnit/SearchView tokens improved diagnostic target recall without oracle fields",
                "baseline_miss_to_hit_count": families["TEXT"]["baseline_miss_to_hit_count"],
                "target_hit_regression_count": families["TEXT"]["target_hit_regression_count"],
            }
        ],
        "inconclusive": [
            {
                "idea_id": "XLSX_SAFE_TABLE_AXIS_SEARCHUNIT_SEARCHVIEW_REPAIR",
                "family": "XLSX",
                "decision": "inconclusive_low_gain_under_guardrails",
                "reason": "safe sheet/row/column/range axis tokens add only two diagnostic target hits while normalized-value and raw-XLSX shortcuts stay rejected",
                "baseline_miss_to_hit_count": families["XLSX"]["baseline_miss_to_hit_count"],
                "target_hit_regression_count": families["XLSX"]["target_hit_regression_count"],
            }
        ],
        "rejected": [
            {
                "idea_id": "DIRECT_NORMALIZED_VALUE_MATCHING",
                "reason": "would use direct answer-value matching instead of generalized table-axis candidate construction",
            },
            {
                "idea_id": "RAW_XLSX_QUERY_TIME_PARSING",
                "reason": "would parse source workbooks at query time and bypass the candidate-only SearchView boundary",
            },
            {
                "idea_id": "SOURCE_FILE_TITLE_SHORTCUT",
                "reason": "would route by title/workbook/file identity instead of reusable SearchUnit/SearchView content",
            },
            {
                "idea_id": "TARGET_GOLD_EXPECTED_SUPPORTING_LOCATOR_USE",
                "reason": "would overfit candidate construction or scoring to hidden target/gold/supporting/expected locators",
            },
            {
                "idea_id": "ROW_SPECIFIC_THRESHOLD_OR_QUERY_ID_HACK",
                "reason": "would tune to known silver rows instead of fixed general rules",
            },
        ],
    }


def _anti_overfit_guardrails() -> dict[str, Any]:
    return {
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "protected_namespaces_touched": [],
        "silver_mutation": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "source_registry_mutated": False,
        "index_rebuilt": False,
        "cache_mutated": False,
        "production_db_mutated": False,
        "candidate_construction_uses_target_or_gold_labels": False,
        "candidate_scoring_uses_target_or_gold_labels": False,
        "expected_or_supporting_gold_text_used": False,
        "hidden_target_locator_used": False,
        "direct_answer_value_matching_used": False,
        "source_title_shortcut_used": False,
        "raw_pdf_query_time_parsing_used": False,
        "raw_xlsx_query_time_parsing_used": False,
        "formula_evaluation_used": False,
        "formula_text_exposure_used": False,
        "case_id_query_id_or_file_name_hack_used": False,
        "threshold_tuning_used": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def build_candidate_only_repair_prototype(
    *,
    root: Path,
    silver_topk_rows: Sequence[Mapping[str, Any]],
    source_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    needed_tokens = _needed_query_tokens(silver_topk_rows)
    index = _build_source_registry_candidate_index(root=root, needed_tokens=needed_tokens)
    candidate_sets, candidate_set_sha256 = _candidate_sets_for_rows(
        silver_topk_rows=silver_topk_rows,
        index=index,
    )
    archive = _evaluate_candidate_sets(
        silver_topk_rows=silver_topk_rows,
        candidate_sets=candidate_sets,
        candidate_set_sha256=candidate_set_sha256,
    )
    policy = _candidate_construction_policy()
    overlay_summary = _overlay_90_root_cause_summary(source_report or _load_source_report(root))
    return {
        "schema_version": f"{SHORT_RUN_ID}_target_recall_repair_prototype_v1",
        "status": "TEXT_XLSX_TARGET_RECALL_REPAIR_PROTOTYPE_READY_DIAGNOSTIC_ONLY",
        "candidate_set_sha256": candidate_set_sha256,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "candidate_budget_per_query": CANDIDATE_BUDGET_PER_QUERY,
        "candidate_construction": policy,
        "source_registry_candidate_index": {
            key: value
            for key, value in index.items()
            if key != "postings"
        },
        "archive_1000_candidate_only_target_recall": archive,
        "overlay_90_root_cause_summary": overlay_summary,
        "repair_idea_decisions": _repair_idea_decisions(archive),
        "per_query_candidates_written": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def _build_counters(prototype: Mapping[str, Any], source_report: Mapping[str, Any]) -> dict[str, Any]:
    archive = prototype["archive_1000_candidate_only_target_recall"]
    families = archive["families"]
    source_counters = source_report.get("counters") or {}
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
        "baseline_target_hit_count": archive["baseline_target_hit_count"],
        "baseline_target_miss_count": archive["baseline_target_miss_count"],
        "combined_target_hit_count": archive["combined_target_hit_count"],
        "combined_target_miss_count": archive["combined_target_miss_count"],
        "baseline_miss_to_hit_count": archive["baseline_miss_to_hit_count"],
        "baseline_hit_to_miss_count": archive["baseline_hit_to_miss_count"],
        "text_baseline_miss_to_hit_count": families["TEXT"]["baseline_miss_to_hit_count"],
        "xlsx_baseline_miss_to_hit_count": families["XLSX"]["baseline_miss_to_hit_count"],
        "pdf_target_hit_regression_count": families["PDF"]["target_hit_regression_count"],
        "text_prototype_candidate_count": families["TEXT"]["prototype_candidate_count"],
        "xlsx_prototype_candidate_count": families["XLSX"]["prototype_candidate_count"],
        "overlay_90_row_count": prototype["overlay_90_root_cause_summary"]["row_count"],
        "retrieval_target_not_in_topk_projection_count": (
            prototype["overlay_90_root_cause_summary"]["primary_projection_counts"]["retrieval_target_not_in_topk"][
                "row_count"
            ]
        ),
        "live_retrieval_precondition_unavailable_count": _as_int(
            source_counters.get("live_retrieval_precondition_unavailable_count")
        ),
        "live_retrieval_quality_failure_count": _as_int(source_counters.get("live_retrieval_quality_failure_count")),
        "llm_unavailable_skip_count": _as_int(source_counters.get("llm_unavailable_skip_count")),
        "generated_response_count": 0,
        "claim_support_fail_count": 0,
        "parser_failure_count": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def build_report(
    *,
    root: Path,
    generated_at: str | None = None,
    source_report: Mapping[str, Any] | None = None,
    check: bool = True,
) -> dict[str, Any]:
    v4715_report = _load_source_report(root, source_report=source_report)
    silver_topk_rows, topk_resolution = _load_silver_topk_rows(root)
    prototype = build_candidate_only_repair_prototype(
        root=root,
        silver_topk_rows=silver_topk_rows,
        source_report=v4715_report,
    )
    counters = _build_counters(prototype, v4715_report)
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
        },
        "artifact_sha256": {},
        "source_run_id": SOURCE_RUN_ID,
        "source_report_json": SOURCE_REPORT_JSON.as_posix(),
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
        "full_pdf_generation_rows": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "target_recall_repair_prototype": prototype,
        "anti_overfit_guardrails": _anti_overfit_guardrails(),
        "source_precondition_summary": {
            "v4_7_13_live_retrieval_precondition_status": (
                (v4715_report.get("source_precondition_summary") or {}).get(
                    "v4_7_13_live_retrieval_precondition_status"
                )
            ),
            "v4_7_13_local_llm_precondition_status": (
                (v4715_report.get("source_precondition_summary") or {}).get("v4_7_13_local_llm_precondition_status")
            ),
            "live_retrieval_quality_failure_count": _as_int(
                (v4715_report.get("counters") or {}).get("live_retrieval_quality_failure_count")
            ),
            "llm_unavailable_skip_count": _as_int((v4715_report.get("counters") or {}).get("llm_unavailable_skip_count")),
            "claim_support_fail_count": _as_int((v4715_report.get("counters") or {}).get("claim_support_fail_count")),
            "parser_failure_count": _as_int((v4715_report.get("counters") or {}).get("parser_failure_count")),
        },
        "counters": counters,
        "completion_branch": "candidate_only_target_recall_repair_prototype_diagnostic_ready",
        "residual_risks": [
            "TEXT recall improves under diagnostic-only candidate construction but still requires real retrieval-system integration before any product claim",
            "XLSX table-axis recall remains inconclusive and needs richer generalized SearchUnit/SearchView materialization without normalized-value shortcuts",
            "the prototype is not an official metric, promotion evidence, live-readiness signal, fine-tuning data, or training data",
        ],
    }
    if check:
        check_report(report)
    return report


def write_report_bundle(root: Path, report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    report = json.loads(json.dumps(report, ensure_ascii=False))
    write_json(root / SHORT_REPORT_PATH, report)
    hashes = {"report_json_sha256": sha256_file(root / SHORT_REPORT_PATH)}
    return report, hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    counters = report["counters"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "diagnostic_v4_7_16_target_recall_repair_prototype_nonprod",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "source_run_id": SOURCE_RUN_ID,
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
        "baseline_target_hit_count": counters["baseline_target_hit_count"],
        "combined_target_hit_count": counters["combined_target_hit_count"],
        "baseline_miss_to_hit_count": counters["baseline_miss_to_hit_count"],
        "baseline_hit_to_miss_count": counters["baseline_hit_to_miss_count"],
        "text_baseline_miss_to_hit_count": counters["text_baseline_miss_to_hit_count"],
        "xlsx_baseline_miss_to_hit_count": counters["xlsx_baseline_miss_to_hit_count"],
        "pdf_target_hit_regression_count": counters["pdf_target_hit_regression_count"],
        "text_prototype_candidate_count": counters["text_prototype_candidate_count"],
        "xlsx_prototype_candidate_count": counters["xlsx_prototype_candidate_count"],
        "overlay_90_row_count": counters["overlay_90_row_count"],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def append_status(root: Path, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    path = root / STATUS_JSONL_PATH
    rows = read_jsonl(path) if path.exists() else []
    rows = [
        row
        for row in rows
        if row.get("run_id") not in {SHORT_RUN_ID, CANONICAL_LONG_RUN_ID}
        and row.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID
        and row.get("event_type") != "diagnostic_v4_7_16_target_recall_repair_prototype_nonprod"
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


def _sync_last_updated(text: str) -> str:
    return re.sub(r"Last updated: .*? KST\.", f"Last updated: {KST_DOC_DATE} KST.", text, count=1)


def _replace_summary_block(text: str, *, block: str) -> str:
    start = "<!-- v4_7_16_summary_start -->"
    end = "<!-- v4_7_16_summary_end -->"
    wrapped = f"{start}\n{block.rstrip()}\n{end}"
    prior_current_summary = re.compile(r"<!-- v4_7[^>]*_summary_start -->.*?<!-- v4_7[^>]*_summary_end -->", re.S)
    if prior_current_summary.search(text):
        return prior_current_summary.sub(wrapped, text, count=1)
    return _upsert_block(text, start_marker=start, end_marker=end, block=block)


def update_docs(root: Path, report: Mapping[str, Any]) -> None:
    counters = report["counters"]
    prototype = report["target_recall_repair_prototype"]
    archive = prototype["archive_1000_candidate_only_target_recall"]
    families = archive["families"]
    progress = root / "docs/rag-ingestion-progress.md"
    measurements = root / "docs/rag-ingestion-measurements.md"
    triage = root / "docs/rag-ingestion-triage.md"
    readme = root / "README.md"
    eval_readme = root / "ai/eval/README.md"
    scripts_readme = root / "ai/scripts/README.md"

    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} is artifact-ready / candidate-only target-recall repair "
        f"prototype-ready. Artifact: `{SHORT_REPORT_PATH.as_posix()}`. Archived v4_7_15 baseline target hit count "
        f"{archive['baseline_target_hit_count']}/1000 moves to diagnostic combined target hit count "
        f"{archive['combined_target_hit_count']}/1000 under fixed candidate-only SearchUnit/SearchView expansion; "
        f"TEXT gains {families['TEXT']['baseline_miss_to_hit_count']} target hits, XLSX gains "
        f"{families['XLSX']['baseline_miss_to_hit_count']}, and PDF target-hit regression count is "
        f"{families['PDF']['target_hit_regression_count']}. Candidate construction uses sanitized query text/family plus "
        "TEXT normalized snapshots and XLSX sheet/row/column/range axes only; target/gold/supporting/expected locators, "
        "direct normalized value matching, raw XLSX parsing, source-title shortcuts, and row-specific hacks remain closed. "
        "official_metric_input_rows=0, silver_promoted_to_gold_count=0, promotion_evidence=false, "
        "product_success_evidence_allowed=false, live_db_index_cache_readiness=false; silver, gold, qrels, labels, "
        "expected/supporting evidence, denominator rows, source registry, indexes, cache, and production DB are not mutated."
    )
    progress.write_text(
        _sync_last_updated(
            _upsert_block(
                progress.read_text(encoding="utf-8"),
                start_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
                end_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
                block=progress_block,
                after_anchor="# RAG Ingestion Progress",
            )
        ),
        encoding="utf-8",
    )

    measurements_block = f"""## v4_7_16 target recall repair prototype

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`

| counter | value |
| --- | --- |
| status | {STATUS} |
| source_run_id | {SOURCE_RUN_ID} |
| candidate_budget_per_query | {prototype['candidate_budget_per_query']} |
| baseline_target_hit_count | {archive['baseline_target_hit_count']} |
| combined_target_hit_count | {archive['combined_target_hit_count']} |
| baseline_miss_to_hit_count | {archive['baseline_miss_to_hit_count']} |
| baseline_hit_to_miss_count | {archive['baseline_hit_to_miss_count']} |
| TEXT baseline_to_combined | {families['TEXT']['baseline_target_hit_count']} -> {families['TEXT']['combined_target_hit_count']} |
| TEXT prototype_candidate_count | {families['TEXT']['prototype_candidate_count']} |
| TEXT baseline_miss_to_hit_count | {families['TEXT']['baseline_miss_to_hit_count']} |
| XLSX baseline_to_combined | {families['XLSX']['baseline_target_hit_count']} -> {families['XLSX']['combined_target_hit_count']} |
| XLSX prototype_candidate_count | {families['XLSX']['prototype_candidate_count']} |
| XLSX baseline_miss_to_hit_count | {families['XLSX']['baseline_miss_to_hit_count']} |
| PDF baseline_to_combined | {families['PDF']['baseline_target_hit_count']} -> {families['PDF']['combined_target_hit_count']} |
| PDF target_hit_regression_count | {families['PDF']['target_hit_regression_count']} |
| overlay_90_retrieval_target_not_in_topk | {counters['retrieval_target_not_in_topk_projection_count']} |
| source_topk_sha256_verified | {str(report['source_topk_sha256_verified']).lower()} |
| source_topk_resolved_via_archive | {str(report['source_topk_resolved_via_archive']).lower()} |
| official_metric_input_rows | 0 |
| direct_normalized_answer_value_matching | false |
| raw_xlsx_query_time_parsing | false |
| source_file_title_shortcut_used | false |
"""
    measurements.write_text(
        _sync_last_updated(
            _upsert_block(
                measurements.read_text(encoding="utf-8"),
                start_marker="<!-- v4_7_16_measurements_start -->",
                end_marker="<!-- v4_7_16_measurements_end -->",
                block=measurements_block,
                after_anchor="# RAG Ingestion Measurements",
            )
        ),
        encoding="utf-8",
    )

    decisions = prototype["repair_idea_decisions"]
    triage_block = (
        f"- {SHORT_RUN_ID} diagnostic-only repair decisions: accepted "
        "TEXT_SAFE_LEXICAL_SEARCHUNIT_SEARCHVIEW_REPAIR because fixed candidate-only TEXT source-registry tokens "
        f"gain {families['TEXT']['baseline_miss_to_hit_count']} target hits with zero target-hit regressions; "
        "inconclusive XLSX_SAFE_TABLE_AXIS_SEARCHUNIT_SEARCHVIEW_REPAIR because safe sheet/row/column/range axes "
        f"gain only {families['XLSX']['baseline_miss_to_hit_count']} target hits; rejected "
        "DIRECT_NORMALIZED_VALUE_MATCHING, RAW_XLSX_QUERY_TIME_PARSING, SOURCE_FILE_TITLE_SHORTCUT, "
        "TARGET_GOLD_EXPECTED_SUPPORTING_LOCATOR_USE, and ROW_SPECIFIC_THRESHOLD_OR_QUERY_ID_HACK. "
        f"The 90-row v4_7_13 overlay remains summarized as diagnostic queues only: retrieval target not in top-k "
        f"{prototype['overlay_90_root_cause_summary']['primary_projection_counts']['retrieval_target_not_in_topk']['row_count']} "
        f"{prototype['overlay_90_root_cause_summary']['primary_projection_counts']['retrieval_target_not_in_topk']['counts_by_family']}. "
        "No silver/gold/qrels, label, expected/supporting evidence, denominator, source registry, cache, production DB, "
        "or index mutation."
    )
    assert decisions["accepted"] and decisions["rejected"]
    triage.write_text(
        _sync_last_updated(
            _upsert_block(
                triage.read_text(encoding="utf-8"),
                start_marker="<!-- v4_7_16_triage_start -->",
                end_marker="<!-- v4_7_16_triage_end -->",
                block=triage_block,
                after_anchor="# RAG Ingestion Triage",
            )
        ),
        encoding="utf-8",
    )

    summary_block = (
        "## Current RAG Diagnostic Status\n"
        f"Current RAG status: `{STATUS}`.\n"
        "`current` resolves to `v4_7_16`: non-production candidate-only target-recall repair prototype. "
        f"Archived v4_7_15 target hits {archive['baseline_target_hit_count']}/1000 become diagnostic combined target hits "
        f"{archive['combined_target_hit_count']}/1000 with TEXT +{families['TEXT']['baseline_miss_to_hit_count']}, "
        f"XLSX +{families['XLSX']['baseline_miss_to_hit_count']}, PDF regression "
        f"{families['PDF']['target_hit_regression_count']}. v4_7_15_read_only_searchindex_replay_projection remains explicit "
        "for historical checks, and v4_7_14_diagnostic_precondition_hardening remains explicit for fail-closed "
        "precondition checks. Candidate construction stays candidate-only: no target/gold/supporting/expected locators, "
        "no direct normalized value matching, no raw XLSX parsing, no source-title shortcut, no row-specific hacks, "
        "and no threshold tuning. Canonical details: `docs/rag-ingestion-progress.md`, "
        "`docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md`; prior v4_7 cleanup keys remain "
        "checkable through explicit aliases.\n"
        "Lineage breadcrumbs: v4_7 remains pre-official; it supersedes the abstract v4_7_1 Korean review packet; "
        "the hydrated packet has hydrated rows 204, PDF 100, XLSX 104 and non-empty `질의문` 204; "
        "v4_7_3 applies the user-reviewed Korean query candidate CSV and v4_7_3 applies the user-reviewed CSV "
        "decisions with 미검수=통과; PDF survivor 58 and v4_7_4 replays only the 58 user-passed PDF survivor "
        "candidates. official_metric_input_rows=0. "
        "## Korean human review packet. The previous v4_7_1 Korean review packet was abstract; "
        "review_packet_ko_hydrated.xlsx carries actual Korean query candidates. "
        "User-owned fields remain blank/default; not official metric. fine_tuning_executed=false.\n"
        "Hard boundary: diagnostic-only, non-production, not official metric, not gold/qrels/labels, "
        "not denominator/training/fine-tuning/FT-A, not promotion evidence, not product-success evidence, "
        "and not live readiness."
    )
    for path in (readme, eval_readme):
        path.write_text(_replace_summary_block(path.read_text(encoding="utf-8"), block=summary_block), encoding="utf-8")

    row = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        "`current` resolves to `v4_7_16`, `v4_7_15_read_only_searchindex_replay_projection` remains explicit, "
        "`v4_7_14_diagnostic_precondition_hardening` remains explicit, "
        "`v4_7_13_live_retrieval_answerability_and_full_pdf_replay` remains explicit, "
        "`v4_7_12_layered_retrieval_generalization_and_overfit_audit` records layered retrieval audit rows 1057, "
        "`v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness`, "
        "`v4_7_9_pdf_evidence_residual_answer_quality_replay`, and prior v4_7 cleanup keys remain checkable "
        "without opening official metrics. |"
    )
    scripts_text = scripts_readme.read_text(encoding="utf-8")
    scripts_text = re.sub(r"\| `rag_eval.py` \|.*?\|", row, scripts_text, count=1)
    scripts_readme.write_text(scripts_text, encoding="utf-8")


def _assert_no_raw_payload_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        forbidden = {"prompt", "raw_prompt", "raw_response", "response", "raw_llm_response", "final_answer"}
        overlap = forbidden & set(value)
        if overlap:
            raise ValueError(f"v4_7_16 raw prompt/response leakage keys present: {sorted(overlap)}")
        for child in value.values():
            _assert_no_raw_payload_keys(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_raw_payload_keys(child)


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v4_7_16 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v4_7_16 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v4_7_16 status mismatch")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v4_7_16 must remain diagnostic-only and non-production")
    for key in FORBIDDEN_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v4_7_16 opened forbidden gate: {key}")
    if report.get("official_metric_input_rows") != 0 or report.get("silver_official_metric_input_rows") != 0:
        raise ValueError("v4_7_16 opened official metric rows")
    if report.get("silver_promoted_to_gold_count") != 0:
        raise ValueError("v4_7_16 promoted silver")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_16 touched protected namespaces")
    if report.get("SearchView_vector_payload_role") != "candidate_only":
        raise ValueError("v4_7_16 SearchView/vector payload role changed")
    if report.get("SourceAtom_EvidenceBundle_role") != "evidence_truth":
        raise ValueError("v4_7_16 SourceAtom/EvidenceBundle role changed")
    if report.get("answer_generation_attempted") is not False or report.get("full_pdf_generation_rows") != []:
        raise ValueError("v4_7_16 must not generate substitute answers")
    if report.get("raw_prompt_payload_written") is not False or report.get("raw_response_payload_written") is not False:
        raise ValueError("v4_7_16 raw prompt/response payload must not be written")
    _assert_no_raw_payload_keys(report)

    prototype = report.get("target_recall_repair_prototype") or {}
    if prototype.get("status") != "TEXT_XLSX_TARGET_RECALL_REPAIR_PROTOTYPE_READY_DIAGNOSTIC_ONLY":
        raise ValueError("v4_7_16 prototype status mismatch")
    if prototype.get("official_metric") is not False or prototype.get("official_metric_input_rows") != 0:
        raise ValueError("v4_7_16 prototype opened official metric surface")
    if prototype.get("per_query_candidates_written") is not False:
        raise ValueError("v4_7_16 must not write per-query candidates")
    construction = prototype.get("candidate_construction") or {}
    for key in (
        "diagnostic_target_labels_used_for_candidate_construction",
        "diagnostic_target_labels_used_for_candidate_scoring",
    ):
        if construction.get(key) is not False:
            raise ValueError("v4_7_16 target labels used during candidate construction or scoring")
    if construction.get("diagnostic_target_labels_used_for_after_the_fact_evaluation") is not True:
        raise ValueError("v4_7_16 target labels must be evaluation-only")
    if construction.get("direct_normalized_answer_value_matching") is not False:
        raise ValueError("v4_7_16 used direct normalized value matching")
    if construction.get("raw_xlsx_query_time_parsing") is not False:
        raise ValueError("v4_7_16 used raw XLSX query-time parsing")
    if construction.get("source_file_title_shortcut_used") is not False:
        raise ValueError("v4_7_16 used a source title shortcut")
    if construction.get("threshold_tuning_used") is not False:
        raise ValueError("v4_7_16 used threshold tuning")
    if _as_int(construction.get("hidden_locator_or_gold_field_use_count")) != 0:
        raise ValueError("v4_7_16 used hidden target/gold/supporting locators")

    archive = prototype.get("archive_1000_candidate_only_target_recall") or {}
    if archive.get("row_count") != 1000:
        raise ValueError("v4_7_16 archive row count drift")
    if archive.get("baseline_target_hit_count") != 300:
        raise ValueError("v4_7_16 baseline target hit drift")
    if archive.get("combined_target_hit_count") != 514:
        raise ValueError("v4_7_16 combined target hit drift")
    if archive.get("baseline_miss_to_hit_count") != 214:
        raise ValueError("v4_7_16 combined target repair gain drift")
    if archive.get("baseline_hit_to_miss_count") != 0:
        raise ValueError("v4_7_16 regression detected in baseline hits")
    families = archive.get("families") or {}
    for family in FAMILIES:
        actual = families.get(family) or {}
        if actual.get("row_count") != EXPECTED_FAMILY_TOTALS[family]:
            raise ValueError(f"v4_7_16 family row count drift: {family}")
        if actual.get("baseline_target_hit_count") != EXPECTED_BASELINE_HITS[family]:
            raise ValueError(f"v4_7_16 family baseline hit drift: {family}")
        if actual.get("prototype_candidate_count") != EXPECTED_PROTOTYPE_CANDIDATES[family]:
            raise ValueError(f"v4_7_16 family candidate count drift: {family}")
        if actual.get("combined_target_hit_count") != EXPECTED_COMBINED_HITS[family]:
            raise ValueError(f"v4_7_16 family combined hit drift: {family}")
        if actual.get("baseline_miss_to_hit_count") != EXPECTED_BASELINE_MISS_TO_HIT[family]:
            raise ValueError(f"v4_7_16 family gain drift: {family}")
    if (families.get("PDF") or {}).get("target_hit_regression_count") != 0:
        raise ValueError("v4_7_16 PDF target-hit regression detected")

    overlay = prototype.get("overlay_90_root_cause_summary") or {}
    if overlay.get("row_count") != 90:
        raise ValueError("v4_7_16 overlay row count drift")
    primary = overlay.get("primary_projection_counts") or {}
    target_not_in_topk = primary.get("retrieval_target_not_in_topk") or {}
    if target_not_in_topk.get("row_count") != 68:
        raise ValueError("v4_7_16 overlay target-not-in-top-k drift")
    if target_not_in_topk.get("counts_by_family") != {"TEXT": 28, "PDF": 12, "XLSX": 28}:
        raise ValueError("v4_7_16 overlay family queue drift")
    for key in (
        "silver_mutation",
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "denominator_mutation",
    ):
        if overlay.get(key) is not False:
            raise ValueError(f"v4_7_16 overlay opened forbidden surface: {key}")

    guardrails = report.get("anti_overfit_guardrails") or {}
    if guardrails.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_16 guardrail touched protected namespaces")
    if guardrails.get("official_metric_input_rows") != 0 or guardrails.get("silver_official_metric_input_rows") != 0:
        raise ValueError("v4_7_16 guardrail opened official metric rows")
    for key, value in guardrails.items():
        if key.endswith("_allowed") or key.endswith("_used") or key.endswith("_created"):
            if value is not False:
                raise ValueError(f"v4_7_16 guardrail opened: {key}")

    counters = report.get("counters") or {}
    required = (
        "current_resolves_to",
        "official_metric_input_rows",
        "baseline_target_hit_count",
        "combined_target_hit_count",
        "baseline_miss_to_hit_count",
        "baseline_hit_to_miss_count",
        "text_baseline_miss_to_hit_count",
        "xlsx_baseline_miss_to_hit_count",
        "pdf_target_hit_regression_count",
        "live_retrieval_quality_failure_count",
        "llm_unavailable_skip_count",
        "generated_response_count",
        "claim_support_fail_count",
        "parser_failure_count",
    )
    missing = [key for key in required if key not in counters]
    if missing:
        raise ValueError(f"v4_7_16 missing counters: {missing}")
    if counters["current_resolves_to"] != LOGICAL_RUN_KEY:
        raise ValueError("current must resolve to v4_7_16")
    if counters["official_metric_input_rows"] != 0:
        raise ValueError("v4_7_16 opened official metric rows")
    for key, expected in (
        ("baseline_target_hit_count", 300),
        ("combined_target_hit_count", 514),
        ("baseline_miss_to_hit_count", 214),
        ("baseline_hit_to_miss_count", 0),
        ("text_baseline_miss_to_hit_count", 212),
        ("xlsx_baseline_miss_to_hit_count", 2),
        ("pdf_target_hit_regression_count", 0),
        ("generated_response_count", 0),
        ("claim_support_fail_count", 0),
        ("parser_failure_count", 0),
    ):
        if counters.get(key) != expected:
            raise ValueError(f"v4_7_16 counter drift: {key}")
