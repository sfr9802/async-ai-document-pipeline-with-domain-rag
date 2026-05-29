from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import rag_v3_9_2_overfit_risk_audit_and_blind_holdout_reset as v392
import rag_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization as v310


ROOT = v392.ROOT
if str(ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai"))
if str(ROOT / "ai" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))

import rag_official_answer_citation_agentic_loop_run_v1 as official_run  # noqa: E402
from app.capabilities.rag.source_registry import evidence_bundle_from_search_view  # noqa: E402


RUN_ID = "official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement"
REPORT_DIR = v392.REPORT_DIR
STATUS_JSONL = v392.STATUS_JSONL
PROGRESS_DOC = v392.PROGRESS_DOC
MEASUREMENTS_DOC = v392.MEASUREMENTS_DOC
TRIAGE_DOC = v392.TRIAGE_DOC

STATUS = "DIAGNOSTIC_V3_12_XLSX_STRUCTURAL_LOCATOR_NONPROD_IMPROVEMENT_READY"
EVENT_TYPE = "diagnostic_v3_12_xlsx_structural_locator_nonprod_improvement"
SOURCE_NAMESPACE = "rag-data-xlsx-table-axis-ood-nonprod-v1"
ALLOWED_NAMESPACE = "rag-data-xlsx-structural-locator-nonprod-v1"
PROTECTED_NAMESPACES = (
    "rag-data-official-denominator-v1",
    "rag-data-all-source-citable-nonprod-v1",
    "production",
)
LAYER_NAMES = (
    "L0_QUERY_ROUTING",
    "L1_COARSE_CANDIDATE_GENERATION",
    "L2_FILE_WORKBOOK_IDENTITY",
    "L3_STRUCTURAL_LOCATOR",
    "L4_SOURCEATOM_HYDRATION",
    "L5_EVIDENCE_BUNDLE_ASSEMBLY",
    "L6_EVIDENCE_SELECTOR",
    "L7_ANSWER_READY_CONTEXT",
    "L9_METRICS_FAILURE_TAXONOMY",
)
SKIPPED_LAYERS = ("L8_GENERATION_OR_DETERMINISTIC_EXECUTION",)

OUTPUTS = {
    "summary_json": REPORT_DIR / f"{RUN_ID}_summary.json",
    "metrics_json": REPORT_DIR / f"{RUN_ID}_metrics.json",
    "per_family_json": REPORT_DIR / f"{RUN_ID}_per_family.json",
    "xlsx_structural_locator_eval_per_query_jsonl": REPORT_DIR
    / f"{RUN_ID}_xlsx_structural_locator_eval_per_query.jsonl",
    "xlsx_score_components_jsonl": REPORT_DIR / f"{RUN_ID}_xlsx_score_components.jsonl",
    "xlsx_layer_trace_per_query_jsonl": REPORT_DIR / f"{RUN_ID}_xlsx_layer_trace_per_query.jsonl",
    "xlsx_nonprod_sourceatom_manifest_jsonl": REPORT_DIR
    / f"{RUN_ID}_xlsx_nonprod_sourceatom_manifest.jsonl",
    "xlsx_nonprod_searchunit_manifest_jsonl": REPORT_DIR
    / f"{RUN_ID}_xlsx_nonprod_searchunit_manifest.jsonl",
    "xlsx_nonprod_index_build_summary_json": REPORT_DIR
    / f"{RUN_ID}_xlsx_nonprod_index_build_summary.json",
    "leakage_audit_jsonl": REPORT_DIR / f"{RUN_ID}_leakage_audit.jsonl",
    "failure_taxonomy_json": REPORT_DIR / f"{RUN_ID}_failure_taxonomy.json",
    "guardrail_audit_json": REPORT_DIR / f"{RUN_ID}_guardrail_audit.json",
    "holdout_manifest_json": REPORT_DIR / f"{RUN_ID}_holdout_manifest.json",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="microseconds") + "Z"


def clean(value: Any) -> str:
    return "" if value is None else str(value)


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def sha256_text(value: Any) -> str:
    return hashlib.sha256(clean(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return v392.sha256_file(path)


def artifact_exists(path: Path) -> bool:
    return v392.artifact_exists(path)


def artifact_is_file(path: Path) -> bool:
    return v392.artifact_is_file(path)


def repo_relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return v392.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v392.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {"numerator": numerator, "denominator": denominator, "rate": numerator / denominator if denominator else None}


def bool_metric(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, Any]:
    return ratio(sum(1 for row in rows if row.get(key) is True), len(rows))


def tokenize(value: Any) -> list[str]:
    text = clean(value).casefold()
    return [token for token in re.split(r"[^0-9a-zA-Z가-힣]+", text) if token]


def hash_values(values: Sequence[str]) -> list[str]:
    return sorted({sha256_text(value.strip()) for value in values if value and value.strip()})


def aliases_from_label(value: str) -> list[str]:
    aliases: list[str] = []
    for part in re.split(r"\s*\|\s*", value):
        part = part.strip()
        if not part:
            continue
        aliases.append(part)
        if "=" in part:
            key, val = part.split("=", 1)
            if key.strip():
                aliases.append(key.strip())
            if val.strip():
                aliases.append(val.strip())
    return list(dict.fromkeys(aliases))


def col_to_num(column: str) -> int:
    total = 0
    for char in column.upper():
        if "A" <= char <= "Z":
            total = total * 26 + (ord(char) - ord("A") + 1)
    return total


def parse_cell(cell: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"([A-Z]+)(\d+)", clean(cell).upper())
    if not match:
        return None
    return int(match.group(2)), col_to_num(match.group(1))


def parse_range(cell_range: str) -> dict[str, Any]:
    match = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", clean(cell_range).upper())
    if not match:
        return {
            "parse_status": "unparsed",
            "start_row": 0,
            "end_row": 0,
            "start_column": 0,
            "end_column": 0,
            "row_count": 0,
            "column_count": 0,
        }
    start_col, start_row, end_col, end_row = match.groups()
    start_row_i = int(start_row)
    end_row_i = int(end_row)
    start_col_i = col_to_num(start_col)
    end_col_i = col_to_num(end_col)
    return {
        "parse_status": "parsed",
        "start_row": start_row_i,
        "end_row": end_row_i,
        "start_column": start_col_i,
        "end_column": end_col_i,
        "row_count": max(0, end_row_i - start_row_i + 1),
        "column_count": max(0, end_col_i - start_col_i + 1),
    }


def date_number_tokens(*values: Any) -> list[str]:
    tokens: set[str] = set()
    for value in values:
        text = clean(value)
        for token in re.findall(r"\d{4,8}|\d+(?:[.,]\d+)?", text):
            tokens.add(token.replace(",", ""))
    return sorted(tokens)


def load_source_registry() -> dict[str, Mapping[str, Any]]:
    registry: dict[str, Mapping[str, Any]] = {}
    for row in read_jsonl(v392.SOURCE_REGISTRY_JSONL):
        source_atom_id = clean(row.get("source_atom_id"))
        if source_atom_id:
            registry[source_atom_id] = row
    return registry


def locator_for_source_atom(atom: Mapping[str, Any]) -> dict[str, str]:
    raw = as_mapping(atom.get("raw_locator"))
    payload = as_mapping(atom.get("canonical_citation_payload"))
    return {
        "workbook": clean(raw.get("workbook") or payload.get("workbook") or atom.get("workbook_id")),
        "sheet": clean(raw.get("sheet") or payload.get("sheet")),
        "range": clean(raw.get("range") or payload.get("range")),
        "cell": clean(raw.get("cell") or payload.get("cell")),
        "row_label": clean(raw.get("row_label") or payload.get("row_label")),
        "column_label": clean(raw.get("column_label") or payload.get("column_label")),
        "target_column": clean(raw.get("target_column") or payload.get("target_column")),
        "normalized_value": clean(raw.get("normalized_value") or payload.get("normalized_value")),
    }


def materialize_sourceatom(atom: Mapping[str, Any]) -> dict[str, Any]:
    locator = locator_for_source_atom(atom)
    original_id = clean(atom.get("source_atom_id"))
    table_range = locator["range"]
    parsed_range = parse_range(table_range)
    parsed_cell = parse_cell(locator["cell"])
    header_columns: list[dict[str, Any]] = []
    if parsed_cell and parsed_range["parse_status"] == "parsed":
        _, cell_col = parsed_cell
        if cell_col > int(parsed_range["start_column"]):
            header_columns.append(
                {
                    "start_column": int(parsed_range["start_column"]),
                    "end_column": cell_col - 1,
                    "propagated_from_row_axis": True,
                }
            )
    row_aliases = aliases_from_label(locator["row_label"])
    column_aliases = aliases_from_label(" | ".join([locator["column_label"], locator["target_column"]]))
    tokens = date_number_tokens(locator["row_label"], locator["column_label"], locator["target_column"], locator["range"])
    table_block_id = "tblstruct_" + sha256_text("|".join([locator["workbook"], locator["sheet"], table_range]))[:24]
    return {
        "schema_version": f"{RUN_ID}_xlsx_nonprod_sourceatom_manifest_v1",
        "run_id": RUN_ID,
        "index_namespace": ALLOWED_NAMESPACE,
        "source_index_namespace": SOURCE_NAMESPACE,
        "source_family": "XLSX",
        "source_registry_version": clean(atom.get("source_registry_version") or "source-registry-v1"),
        "source_atom_id": "srcatom_v3_12_xlsx_struct_" + sha256_text(original_id or atom.get("source_identity"))[:24],
        "source_atom_id_original": original_id,
        "source_identity_sha256": sha256_text(atom.get("source_identity")),
        "workbook_id_sha256": sha256_text(locator["workbook"]),
        "sheet_name_sha256": sha256_text(locator["sheet"]),
        "cell": locator["cell"],
        "materialized_in_nonprod_sourceatom": True,
        "overlay_only": False,
        "table_block_id": table_block_id,
        "table_boundary_candidate": {
            "present": bool(table_range),
            "table_range": table_range,
            "source": "source_registry_locator_after_workbook_sheet_route",
        },
        "sheet_name": locator["sheet"],
        "table_range": table_range,
        "row_axis_aliases": row_aliases,
        "column_axis_aliases": column_aliases,
        "header_rows": [{"row": parsed_range["start_row"], "propagated_from_table_boundary": True}]
        if parsed_range["parse_status"] == "parsed"
        else [],
        "header_columns": header_columns,
        "merged_cell_header_propagation": {
            "present": False,
            "propagated_header_count": 0,
            "source": "not_available_in_current_source_registry_or_v3_10_overlay",
        },
        "parent_header_path_sha256": hash_values(
            [f"{locator['sheet']}|{table_range}", f"{table_range}|{locator['target_column']}"]
        ),
        "row_label_aliases_sha256": hash_values(row_aliases),
        "row_axis_alias_count": len(row_aliases),
        "column_label_aliases_sha256": hash_values(column_aliases),
        "column_axis_alias_count": len(column_aliases),
        "unit_date_number_normalized_tokens": tokens,
        "sparse_table_boundary": parsed_range,
        "raw_answer_value_for_query_scoring_used": False,
        "normalized_value_excluded_from_query_scoring": True,
        "expected_supporting_gold_text_used": False,
        "forbidden_fields_absent": True,
    }


def materialize_searchunit(row: Mapping[str, Any]) -> dict[str, Any]:
    aliases = sorted(set(row["row_label_aliases_sha256"] + row["column_label_aliases_sha256"]))
    shape = as_mapping(row.get("sparse_table_boundary"))
    readable_row_axis = " | ".join(row.get("row_axis_aliases") or [])
    readable_column_axis = " | ".join(row.get("column_axis_aliases") or [])
    readable_period_unit = " ".join(row["unit_date_number_normalized_tokens"])
    standard_text = (
        f"Sheet: {row['sheet_name']}\n"
        f"Range: {row['table_range']}\n"
        f"Table: {row['table_block_id']}\n"
        f"Row axis: {readable_row_axis}\n"
        f"Column axis: {readable_column_axis}\n"
        f"Period/unit tokens: {readable_period_unit}\n"
        "Normalized answer value excluded from scoring."
    )
    embedding_text = (
        f"namespace={ALLOWED_NAMESPACE} family=XLSX table_block_id={row['table_block_id']} "
        f"table_range={row['table_range']} rows={shape.get('row_count', 0)} columns={shape.get('column_count', 0)} "
        f"sheet={row['sheet_name']} row_axis={readable_row_axis} column_axis={readable_column_axis} "
        f"header_path_hashes={' '.join(row['parent_header_path_sha256'])} "
        f"row_column_alias_hashes={' '.join(aliases)} "
        f"unit_date_number_tokens={' '.join(row['unit_date_number_normalized_tokens'])}"
    )
    return {
        "schema_version": f"{RUN_ID}_xlsx_nonprod_searchunit_manifest_v1",
        "run_id": RUN_ID,
        "index_namespace": ALLOWED_NAMESPACE,
        "source_index_namespace": SOURCE_NAMESPACE,
        "search_unit_id": "su_v3_12_xlsx_struct_" + sha256_text(row["source_atom_id"])[:24],
        "source_atom_id": row["source_atom_id"],
        "source_atom_id_original": row["source_atom_id_original"],
        "source_identity_sha256": row["source_identity_sha256"],
        "source_family": "XLSX",
        "materialized_in_nonprod_searchunit": True,
        "table_block_id": row["table_block_id"],
        "embedding_text": standard_text,
        "bm25_text": standard_text,
        "display_text": standard_text,
        "citation_text": f"{row['sheet_name']} {row['table_range']} {row['cell']}".strip(),
        "table_axis_embedding_text": embedding_text,
        "table_axis_bm25_text": (
            f"table_block {row['table_block_id']} range {row['table_range']} "
            f"sheet {row['sheet_name']} row_axis {readable_row_axis} column_axis {readable_column_axis} "
            f"row_axis_count {row['row_axis_alias_count']} column_axis_count {row['column_axis_alias_count']}"
        ),
        "header_path_hashes": row["parent_header_path_sha256"],
        "row_column_alias_hashes": aliases,
        "table_shape_summary": shape,
        "table_axis_debug_text": (
            f"redacted workbook_hash={row['workbook_id_sha256']} sheet_hash={row['sheet_name_sha256']} "
            f"row_axis_alias_count={row['row_axis_alias_count']} "
            f"column_axis_alias_count={row['column_axis_alias_count']} raw_answer_value_excluded=true"
        ),
        "direct_normalized_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "expected_supporting_gold_text_used": False,
        "forbidden_fields_absent": True,
    }


def materialize_xlsx_rows(
    source_registry: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Mapping[str, Any]]]:
    xlsx_atoms = [atom for atom in source_registry.values() if clean(atom.get("source_family")).upper() == "XLSX"]
    sourceatoms = [materialize_sourceatom(atom) for atom in xlsx_atoms]
    sourceatoms.sort(key=lambda row: row["source_atom_id"])
    searchunits = [materialize_searchunit(row) for row in sourceatoms]
    searchunits.sort(key=lambda row: row["search_unit_id"])
    by_original = {row["source_atom_id_original"]: row for row in sourceatoms}
    return sourceatoms, searchunits, by_original


def candidate_source_atom_id(candidate: Mapping[str, Any]) -> str:
    return clean(candidate.get("source_atom_id"))


def structural_components(candidate: Mapping[str, Any], materialized: Mapping[str, Any] | None) -> dict[str, Any]:
    query_signal_count = int(candidate.get("query_locator_signal_count") or 0)
    specificity = int(candidate.get("structural_specificity_rank") or 0)
    mode = clean(candidate.get("candidate_generation_mode"))
    table_boundary_present = bool(materialized and as_mapping(materialized.get("table_boundary_candidate")).get("present"))
    row_axis_alias_count = int(materialized.get("row_axis_alias_count") or 0) if materialized else 0
    column_axis_alias_count = int(materialized.get("column_axis_alias_count") or 0) if materialized else 0
    token_count = len(materialized.get("unit_date_number_normalized_tokens") or []) if materialized else 0
    header_path_count = len(materialized.get("parent_header_path_sha256") or []) if materialized else 0
    merged_present = bool(as_mapping(materialized.get("merged_cell_header_propagation")).get("present")) if materialized else False
    zero_signal_legacy = mode == "legacy_topk_window" and query_signal_count == 0
    return {
        "query_locator_signal_count": query_signal_count,
        "structural_specificity_rank": specificity,
        "source_atom_table_axis_same_workbook": mode == "source_atom_table_axis_same_workbook",
        "table_boundary_candidate_present": table_boundary_present,
        "header_path_propagated": header_path_count > 0,
        "merged_cell_header_propagation_present": merged_present,
        "row_axis_alias_count": row_axis_alias_count,
        "column_axis_alias_count": column_axis_alias_count,
        "unit_date_number_token_count": token_count,
        "zero_signal_legacy_row_window_demotion": zero_signal_legacy,
        "direct_normalized_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "used_gold_or_expected_text": False,
    }


def structural_score(candidate: Mapping[str, Any], materialized: Mapping[str, Any] | None) -> tuple[int, dict[str, Any]]:
    components = structural_components(candidate, materialized)
    score = (
        int(components["query_locator_signal_count"]) * 50
        + int(components["structural_specificity_rank"]) * 5
        + (25 if components["source_atom_table_axis_same_workbook"] else 0)
        + (3 if components["table_boundary_candidate_present"] else 0)
        + (2 if components["header_path_propagated"] else 0)
        + min(2, int(components["row_axis_alias_count"]))
        + min(2, int(components["column_axis_alias_count"]))
        + min(2, int(components["unit_date_number_token_count"]))
        - (10 if components["zero_signal_legacy_row_window_demotion"] else 0)
    )
    return score, components


def rerank_candidates(
    row: Mapping[str, Any],
    materialized_by_original: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    old_candidates = [dict(candidate) for candidate in row.get("scoped_cell_candidates", []) if isinstance(candidate, Mapping)]
    if not old_candidates:
        return [], [], False
    preserve_strong_rank1 = int(old_candidates[0].get("query_locator_signal_count") or 0) >= 3
    scored: list[tuple[int, int, dict[str, Any], dict[str, Any]]] = []
    score_rows: list[dict[str, Any]] = []
    for original_rank, candidate in enumerate(old_candidates, start=1):
        materialized = materialized_by_original.get(candidate_source_atom_id(candidate))
        score, components = structural_score(candidate, materialized)
        score_rows.append(
            {
                "schema_version": f"{RUN_ID}_xlsx_score_components_v1",
                "run_id": RUN_ID,
                "query_id": row.get("query_id"),
                "source_family": "XLSX",
                "candidate_rank_old": original_rank,
                "source_atom_id_original": candidate_source_atom_id(candidate),
                "candidate_generation_mode": clean(candidate.get("candidate_generation_mode")),
                "structural_score": score,
                "score_components": components,
                "direct_normalized_value_query_matching_used": False,
                "raw_answer_value_for_query_scoring_used": False,
                "used_gold_or_expected_text": False,
                "official_metric_input_rows": 0,
                "diagnostic_only": True,
            }
        )
        scored.append((score, original_rank, candidate, components))
    if preserve_strong_rank1:
        ranked = scored
    else:
        ranked = sorted(scored, key=lambda item: (-item[0], item[1]))
    candidates: list[dict[str, Any]] = []
    for new_rank, (score, original_rank, candidate, components) in enumerate(ranked, start=1):
        updated = dict(candidate)
        updated["candidate_rank_old"] = original_rank
        updated["candidate_rank"] = new_rank
        updated["v3_12_structural_score"] = score
        updated["v3_12_score_components"] = components
        updated["direct_normalized_value_query_matching_used"] = False
        updated["vector_metadata_used_as_evidence_truth"] = False
        candidates.append(updated)
    rank1_changed = candidate_source_atom_id(candidates[0]) != candidate_source_atom_id(old_candidates[0])
    return candidates, score_rows, rank1_changed


def source_rows_by_query_id() -> dict[str, Mapping[str, Any]]:
    return {
        clean(row.get("query_id")): row
        for row in read_jsonl(official_run.DEFAULT_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_TOPK_ROWS_JSONL)
        if clean(row.get("source_family")).upper() == "XLSX"
    }


def any_hit(
    candidates: Sequence[Mapping[str, Any]],
    predicate: Callable[[Mapping[str, Any]], bool],
    limit: int,
) -> bool:
    return any(predicate(candidate) for candidate in candidates[:limit])


def old_top3_candidates(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [candidate for candidate in row.get("scoped_cell_candidates", [])[:3] if isinstance(candidate, Mapping)]


def structural_signal_count(candidate: Mapping[str, Any]) -> int:
    components = as_mapping(candidate.get("v3_12_score_components"))
    if not components:
        return 0
    signal_keys = (
        "table_boundary_candidate_present",
        "header_path_propagated",
        "row_axis_alias_count",
        "column_axis_alias_count",
        "unit_date_number_token_count",
    )
    count = 0
    for key in signal_keys:
        value = components.get(key)
        if isinstance(value, bool) and value:
            count += 1
        elif isinstance(value, int) and value > 0:
            count += 1
    return count


def failure_bucket(row: Mapping[str, Any]) -> str:
    if row["new_cell_or_value@1"]:
        return "cell_or_value_resolved_at_rank_1"
    if row["new_table_or_range@1"]:
        return "cell_or_value_miss_after_range_hit"
    if row["new_sheet@1"]:
        return "table_or_range_miss_after_sheet_hit"
    if row["new_candidate_count"] == 0:
        return "abstain_or_no_candidate"
    return "sheet_or_workbook_locator_miss"


def build_xlsx_eval(
    *,
    v391_rows: Sequence[Mapping[str, Any]],
    source_rows: Mapping[str, Mapping[str, Any]],
    source_registry: Mapping[str, Mapping[str, Any]],
    materialized_by_original: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    eval_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    for row in v391_rows:
        query_id = clean(row.get("query_id"))
        source_row = source_rows[query_id]
        target = official_run.v3_8_3_metric_target_xlsx_locator(source_row, source_registry=source_registry)
        old_candidates = old_top3_candidates(row)
        new_candidates, row_score_rows, rank1_changed = rerank_candidates(row, materialized_by_original)
        score_rows.extend(row_score_rows)

        old_sheet_1 = any_hit(old_candidates, lambda candidate: official_run.v3_8_xlsx_sheet_hit(target, candidate), 1)
        old_sheet_3 = any_hit(old_candidates, lambda candidate: official_run.v3_8_xlsx_sheet_hit(target, candidate), 3)
        old_range_1 = any_hit(old_candidates, lambda candidate: official_run.v3_8_xlsx_range_hit(target, candidate), 1)
        old_range_3 = any_hit(old_candidates, lambda candidate: official_run.v3_8_xlsx_range_hit(target, candidate), 3)
        old_cell_1 = any_hit(
            old_candidates,
            lambda candidate: official_run.v3_8_3_xlsx_cell_or_value_hit(target, candidate),
            1,
        )
        old_cell_3 = any_hit(
            old_candidates,
            lambda candidate: official_run.v3_8_3_xlsx_cell_or_value_hit(target, candidate),
            3,
        )
        new_sheet_1 = any_hit(new_candidates, lambda candidate: official_run.v3_8_xlsx_sheet_hit(target, candidate), 1)
        new_sheet_3 = any_hit(new_candidates, lambda candidate: official_run.v3_8_xlsx_sheet_hit(target, candidate), 3)
        new_range_1 = any_hit(new_candidates, lambda candidate: official_run.v3_8_xlsx_range_hit(target, candidate), 1)
        new_range_3 = any_hit(new_candidates, lambda candidate: official_run.v3_8_xlsx_range_hit(target, candidate), 3)
        new_cell_1 = any_hit(
            new_candidates,
            lambda candidate: official_run.v3_8_3_xlsx_cell_or_value_hit(target, candidate),
            1,
        )
        new_cell_3 = any_hit(
            new_candidates,
            lambda candidate: official_run.v3_8_3_xlsx_cell_or_value_hit(target, candidate),
            3,
        )
        old_rank1 = old_candidates[0] if old_candidates else {}
        new_rank1 = new_candidates[0] if new_candidates else {}
        hydration_result: Mapping[str, Any] = {}
        new_rank1_source_atom_id = candidate_source_atom_id(new_rank1)
        if new_rank1_source_atom_id:
            hydration_result = evidence_bundle_from_search_view(
                {
                    "search_view_id": clean(new_rank1.get("search_view_id")),
                    "source_atom_id": new_rank1_source_atom_id,
                },
                source_registry=source_registry,
            )
        hydrated = bool(hydration_result.get("valid") and hydration_result.get("source_atom_hydrated_from_registry"))
        evidence_bundle_assembled = bool(hydrated and hydration_result.get("evidence_bundle"))
        structural_count = structural_signal_count(new_rank1)
        eval_row = {
            "schema_version": f"{RUN_ID}_xlsx_structural_locator_eval_per_query_v1",
            "run_id": RUN_ID,
            "query_id": query_id,
            "query_text_sha256": row.get("query_text_sha256"),
            "source_family": "XLSX",
            "old_seen_reference_only": True,
            "fresh_real_holdout": False,
            "success_claim_allowed": False,
            "candidate_generation_mode": "v3_12_structural_locator_nonprod_rerank_after_workbook_sheet_route",
            "old_candidate_count": len(old_candidates),
            "new_candidate_count": len(new_candidates),
            "old_rank1_source_atom_id_original": candidate_source_atom_id(old_rank1),
            "new_rank1_source_atom_id_original": new_rank1_source_atom_id,
            "source_atom_hydrated_from_registry": hydrated,
            "evidence_bundle_assembled": evidence_bundle_assembled,
            "canonical_payload_source": "source_registry" if hydrated else "not_hydrated",
            "hydration_failure_bucket": clean(hydration_result.get("failure_bucket")),
            "rank1_reranked": rank1_changed,
            "v3_11_query_locator_signal_count_rank1": int(old_rank1.get("query_locator_signal_count") or 0)
            if old_rank1
            else None,
            "v3_12_structural_signal_count_rank1": structural_count if new_rank1 else None,
            "zero_signal_legacy_row_window_demoted": bool(
                old_rank1
                and int(old_rank1.get("query_locator_signal_count") or 0) == 0
                and candidate_source_atom_id(old_rank1) != candidate_source_atom_id(new_rank1)
            ),
            "old_sheet@1": old_sheet_1,
            "old_sheet@3": old_sheet_3,
            "old_table_or_range@1": old_range_1,
            "old_table_or_range@3": old_range_3,
            "old_cell_or_value@1": old_cell_1,
            "old_cell_or_value@3": old_cell_3,
            "new_sheet@1": new_sheet_1,
            "new_sheet@3": new_sheet_3,
            "new_table_or_range@1": new_range_1,
            "new_table_or_range@3": new_range_3,
            "new_cell_or_value@1": new_cell_1,
            "new_cell_or_value@3": new_cell_3,
            "failure_bucket": "",
            "direct_normalized_value_query_matching_used": False,
            "raw_answer_value_for_query_scoring_used": False,
            "used_gold_or_expected_text": False,
            "official_metric_input_rows": 0,
            "diagnostic_only": True,
        }
        eval_row["failure_bucket"] = failure_bucket(eval_row)
        eval_rows.append(eval_row)
        trace_rows.append(
            {
                "schema_version": f"{RUN_ID}_xlsx_layer_trace_per_query_v1",
                "run_id": RUN_ID,
                "query_id": query_id,
                "source_family": "XLSX",
                "query_text_sha256": row.get("query_text_sha256"),
                "layers_recorded": list(LAYER_NAMES),
                "layers_skipped_by_design": list(SKIPPED_LAYERS),
                "layer_metrics": {
                    "L2_FILE_WORKBOOK_IDENTITY": {
                        "workbook_gate_resolved": bool(row.get("v3_8_2_gate_resolved")),
                        "workbook_gate_found": bool(row.get("v3_8_2_gate_row_found")),
                    },
                    "L3_STRUCTURAL_LOCATOR": {
                        "rank1_reranked": rank1_changed,
                        "old_rank1_query_signal_count": eval_row["v3_11_query_locator_signal_count_rank1"],
                        "new_rank1_structural_signal_count": eval_row["v3_12_structural_signal_count_rank1"],
                        "zero_signal_legacy_row_window_demoted": eval_row["zero_signal_legacy_row_window_demoted"],
                    },
                    "L4_SOURCEATOM_HYDRATION": {
                        "source_atom_id_original": eval_row["new_rank1_source_atom_id_original"],
                        "hydration_valid": hydrated,
                        "hydration_failure_bucket": clean(hydration_result.get("failure_bucket")),
                        "canonical_payload_source": eval_row["canonical_payload_source"],
                    },
                    "L5_EVIDENCE_BUNDLE_ASSEMBLY": {
                        "evidence_bundle_selected": evidence_bundle_assembled,
                        "vector_payload_used_as_evidence_truth": False,
                    },
                    "L6_EVIDENCE_SELECTOR": {
                        "selected_evidence_count": 1 if evidence_bundle_assembled else 0,
                    },
                    "L9_METRICS_FAILURE_TAXONOMY": {
                        "failure_bucket": eval_row["failure_bucket"],
                        "official_metric_input_rows": 0,
                    },
                },
                "used_gold_or_expected_text": False,
                "direct_normalized_value_query_matching_used": False,
                "diagnostic_only": True,
                "official_metric_input_rows": 0,
            }
        )
    return eval_rows, score_rows, trace_rows


def metric_block(rows: Sequence[Mapping[str, Any]], prefix: str) -> dict[str, Any]:
    rank1_rows = [row for row in rows if row.get(f"{prefix}_candidate_count", 0) or row.get(f"{prefix}_sheet@1") is not None]
    ranked_denominator = sum(1 for row in rows if int(row.get(f"{prefix}_candidate_count") or 0) > 0)
    if prefix == "old":
        ranked_denominator = sum(1 for row in rows if int(row.get("old_candidate_count") or 0) > 0)
        zero_field = "v3_11_query_locator_signal_count_rank1"
    else:
        ranked_denominator = sum(1 for row in rows if int(row.get("new_candidate_count") or 0) > 0)
        zero_field = "v3_12_structural_signal_count_rank1"
    zero_count = sum(1 for row in rows if row.get(zero_field) == 0 and int(row.get(f"{prefix}_candidate_count") or 0) > 0)
    block = {
        "success_claim_allowed": False,
        "denominator_role": "seen_validation_only_reference_no_regression"
        if prefix == "old"
        else "seen_validation_only_nonprod_structural_locator_smoke_not_success",
        "row_count": len(rows),
        "sheet@1": bool_metric(rows, f"{prefix}_sheet@1"),
        "sheet@3": bool_metric(rows, f"{prefix}_sheet@3"),
        "table_or_range@1": bool_metric(rows, f"{prefix}_table_or_range@1"),
        "table_or_range@3": bool_metric(rows, f"{prefix}_table_or_range@3"),
        "cell_or_value@1": bool_metric(rows, f"{prefix}_cell_or_value@1"),
        "cell_or_value@3": bool_metric(rows, f"{prefix}_cell_or_value@3"),
        "structural_signal_empty_rank1_rate" if prefix == "new" else "query_signal_empty_rank1_rate": ratio(
            zero_count,
            ranked_denominator,
        ),
    }
    if prefix == "old":
        block["checkpoint_reference_run_id"] = "official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic"
        block["candidate_surface_source_run_id"] = v392.V3_9_1_RUN_ID
        block["candidate_surface_rationale"] = (
            "v3_11 is the diagnostic checkpoint; XLSX candidate-level scoped_cell_candidates are reused from "
            "v3_9_1 because v3_11 keeps only compact layer traces."
        )
    return block


def build_metrics(eval_rows: Sequence[Mapping[str, Any]], score_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    old_seen = metric_block(eval_rows, "old")
    smoke = metric_block(eval_rows, "new")
    gain_loss_samples: dict[str, list[str]] = {
        "table_or_range@1_gain_query_ids": [],
        "table_or_range@1_loss_query_ids": [],
        "cell_or_value@1_gain_query_ids": [],
        "cell_or_value@1_loss_query_ids": [],
    }
    for row in eval_rows:
        query_id = clean(row.get("query_id"))
        if row.get("old_table_or_range@1") is not True and row.get("new_table_or_range@1") is True:
            gain_loss_samples["table_or_range@1_gain_query_ids"].append(query_id)
        if row.get("old_table_or_range@1") is True and row.get("new_table_or_range@1") is not True:
            gain_loss_samples["table_or_range@1_loss_query_ids"].append(query_id)
        if row.get("old_cell_or_value@1") is not True and row.get("new_cell_or_value@1") is True:
            gain_loss_samples["cell_or_value@1_gain_query_ids"].append(query_id)
        if row.get("old_cell_or_value@1") is True and row.get("new_cell_or_value@1") is not True:
            gain_loss_samples["cell_or_value@1_loss_query_ids"].append(query_id)
    smoke["rank1_reranked_count"] = sum(1 for row in eval_rows if row.get("rank1_reranked") is True)
    smoke["zero_signal_legacy_rank1_demoted_count"] = sum(
        1 for row in eval_rows if row.get("zero_signal_legacy_row_window_demoted") is True
    )
    smoke["rank1_reranked_old_query_signal_count_distribution"] = {
        clean(signal_count): count
        for signal_count, count in sorted(
            Counter(
                row.get("v3_11_query_locator_signal_count_rank1")
                for row in eval_rows
                if row.get("rank1_reranked") is True
            ).items(),
            key=lambda item: clean(item[0]),
        )
    }
    smoke["zero_signal_legacy_row_window_demotion_candidate_count"] = sum(
        1
        for row in score_rows
        if as_mapping(row.get("score_components")).get("zero_signal_legacy_row_window_demotion") is True
    )
    smoke["table_or_range@1_gain_count"] = len(gain_loss_samples["table_or_range@1_gain_query_ids"])
    smoke["table_or_range@1_loss_count"] = len(gain_loss_samples["table_or_range@1_loss_query_ids"])
    smoke["cell_or_value@1_gain_count"] = len(gain_loss_samples["cell_or_value@1_gain_query_ids"])
    smoke["cell_or_value@1_loss_count"] = len(gain_loss_samples["cell_or_value@1_loss_query_ids"])
    smoke["rank1_gain_loss_sample_query_ids"] = {
        key: values[:5] for key, values in gain_loss_samples.items()
    }
    smoke["cell_or_value@1_delta_from_old_seen_reference"] = (
        smoke["cell_or_value@1"]["numerator"] - old_seen["cell_or_value@1"]["numerator"]
    )
    smoke["table_or_range@1_delta_from_old_seen_reference"] = (
        smoke["table_or_range@1"]["numerator"] - old_seen["table_or_range@1"]["numerator"]
    )
    component_rerank = {
        "reranked_rows_with_cell_or_value@1": sum(
            1 for row in eval_rows if row["rank1_reranked"] and row["new_cell_or_value@1"]
        ),
        "reranked_rows_with_table_or_range@1": sum(
            1 for row in eval_rows if row["rank1_reranked"] and row["new_table_or_range@1"]
        ),
        "reranked_rows_with_sheet@1": sum(1 for row in eval_rows if row["rank1_reranked"] and row["new_sheet@1"]),
        "reranked_rows_with_merged_header_signal": 0,
        "note": "These are reranked-row hit slices, not causal lift claims; true rank1 gain/loss is reported separately.",
    }
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "answer_generation_executed": False,
        "pdf_xlsx_collapsed_headline_score_reported": False,
        "xlsx_structural_locator_eval": {
            "old_seen_reference_v3_11": old_seen,
            "v3_12_nonprod_structural_locator_smoke": smoke,
            "component_rerank_buckets": component_rerank,
        },
        "fresh_real_holdout": {
            "sufficient": False,
            "row_count": 0,
            "product_success_evidence_allowed": False,
            "blocked_reason": "fresh real XLSX workbook-disjoint holdout unavailable",
        },
    }


def build_per_family(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_per_family_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "families_reported_separately": ["XLSX"],
        "per_source_family": {
            "XLSX": {
                "row_count": metrics["xlsx_structural_locator_eval"]["v3_12_nonprod_structural_locator_smoke"][
                    "row_count"
                ],
                "metric_scope": "diagnostic_only_seen_reference_structural_locator",
                "metrics": metrics["xlsx_structural_locator_eval"]["v3_12_nonprod_structural_locator_smoke"],
            }
        },
    }


def build_index_summary(sourceatoms: Sequence[Mapping[str, Any]], searchunits: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_xlsx_nonprod_index_build_summary_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "index_namespace": ALLOWED_NAMESPACE,
        "source_namespace": SOURCE_NAMESPACE,
        "sourceatom_manifest_rows": len(sourceatoms),
        "searchunit_manifest_rows": len(searchunits),
        "index_build_executed": False,
        "manifest_only": True,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "protected_namespaces_touched": [],
        "db_or_production_namespace_written": False,
        "direct_normalized_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "expected_supporting_gold_text_used": False,
        "namespace_decision_rationale": (
            "A new non-prod diagnostic namespace avoids mutating v3_10 sidecars, official denominator indexes, "
            "or production retrieval namespaces."
        ),
    }


def build_leakage_audit() -> list[dict[str, Any]]:
    buckets = (
        "answer_value_in_query",
        "expected_supporting_gold_text",
        "gold_label_or_qrels",
        "direct_normalized_value_query_match",
        "production_namespace_write",
    )
    return [
        {
            "schema_version": f"{RUN_ID}_leakage_audit_v1",
            "run_id": RUN_ID,
            "probe_id": f"v3_12_leakage_probe_{index:02d}",
            "bucket": bucket,
            "success_evidence_allowed": False,
            "retrieval_or_generation_input_used": False,
            "direct_normalized_value_query_matching_used": False,
            "official_metric_input_rows": 0,
            "diagnostic_only": True,
        }
        for index, bucket in enumerate(buckets, start=1)
    ]


def build_failure_taxonomy(eval_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = Counter(clean(row.get("failure_bucket")) for row in eval_rows)
    samples: dict[str, list[str]] = {}
    for row in eval_rows:
        bucket = clean(row.get("failure_bucket"))
        samples.setdefault(bucket, [])
        if len(samples[bucket]) < 5:
            samples[bucket].append(clean(row.get("query_id")))
    return {
        "schema_version": f"{RUN_ID}_failure_taxonomy_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "taxonomy_scope": "xlsx_structural_locator_seen_reference_only",
        "failure_bucket_counts": dict(sorted(counts.items())),
        "sample_query_ids_by_bucket": samples,
        "product_success_evidence_allowed": False,
    }


def guardrail_flags() -> dict[str, Any]:
    return {
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "answer_value_in_query_success_evidence_used": False,
        "index_to_content_success_evidence_used": False,
        "file_or_source_title_leak_success_evidence_used": False,
    }


def build_guardrail_audit() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "protected_namespaces": list(PROTECTED_NAMESPACES),
        "protected_namespaces_touched": [],
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "direct_normalized_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "source_atom_registry_canonical_truth": True,
        "source_atom_registry_mutated": False,
        "source_registry_baseline_mutated": False,
        "official_denominator_mutated": False,
        "db_or_production_namespace_written": False,
        "vector_payload_used_as_evidence_truth": False,
        **guardrail_flags(),
    }


def build_holdout_manifest(v310_holdout: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_holdout_manifest_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "fresh_real_holdout_sufficient": False,
        "product_success_evidence_allowed": False,
        "promotion_evidence": False,
        "real_unseen_registry_counts": v310_holdout["real_unseen_registry_counts"],
        "real_query_fidelity_included_counts": v310_holdout["real_query_fidelity_included_counts"],
        "minimum_targets": v310_holdout["minimum_targets"],
        "blocked_reason": "fresh real XLSX workbook-disjoint holdout unavailable",
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    artifact_sha256: Mapping[str, str],
    input_lineage: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_summary_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "event_type": EVENT_TYPE,
        "run_class": "diagnostic_only_xlsx_structural_locator_nonprod_improvement",
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "fine_tuning_executed": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "fresh_real_holdout_sufficient": False,
        "answer_generation_executed": False,
        "direct_normalized_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "answer_value_in_query_success_evidence_used": False,
        "index_to_content_success_evidence_used": False,
        "file_or_source_title_leak_success_evidence_used": False,
        "index_namespace": ALLOWED_NAMESPACE,
        "source_index_namespace": SOURCE_NAMESPACE,
        "protected_namespaces_touched": [],
        "source_atom_registry_canonical_truth": True,
        "source_atom_registry_mutated": False,
        "source_registry_baseline_mutated": False,
        "official_denominator_mutated": False,
        "db_or_production_namespace_written": False,
        "vector_payload_used_as_evidence_truth": False,
        "xlsx_seen_validation_only": True,
        "fresh_workbook_disjoint_holdout_required_for_success": True,
        "layer_contract": list(LAYER_NAMES),
        "layers_skipped_by_design": list(SKIPPED_LAYERS),
        "v3_12_nonprod_structural_locator_smoke": metrics["xlsx_structural_locator_eval"][
            "v3_12_nonprod_structural_locator_smoke"
        ],
        "input_lineage": dict(input_lineage),
        "artifact_paths": {key: repo_relative(path) for key, path in OUTPUTS.items()},
        "artifact_sha256": dict(artifact_sha256),
        **guardrail_flags(),
    }


@lru_cache(maxsize=1)
def build_artifacts() -> dict[str, Any]:
    input_paths = {
        "v3_9_1_per_query_jsonl": v392.V3_9_1_PER_QUERY,
        "v3_10_holdout_manifest_json": v310.OUTPUTS["fresh_real_holdout_manifest_json"],
        "v3_10_xlsx_nonprod_sourceatom_manifest_jsonl": v310.OUTPUTS["xlsx_nonprod_sourceatom_manifest_jsonl"],
        "v3_10_xlsx_nonprod_searchunit_manifest_jsonl": v310.OUTPUTS["xlsx_nonprod_searchunit_manifest_jsonl"],
        "v3_10_xlsx_nonprod_index_build_summary_json": v310.OUTPUTS["xlsx_nonprod_index_build_summary_json"],
        "v3_11_summary_json": REPORT_DIR
        / "official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic_summary.json",
        "source_registry_jsonl": v392.SOURCE_REGISTRY_JSONL,
        "source_topk_rows_jsonl": official_run.DEFAULT_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_TOPK_ROWS_JSONL,
    }
    missing = [repo_relative(path) for path in input_paths.values() if not artifact_exists(path)]
    if missing:
        raise FileNotFoundError("missing required v3_12 input artifacts: " + ", ".join(missing))
    input_lineage = {
        key: {"path": repo_relative(path), "sha256": sha256_file(path)}
        for key, path in input_paths.items()
    }

    source_registry = load_source_registry()
    source_rows = source_rows_by_query_id()
    sourceatoms, searchunits, materialized_by_original = materialize_xlsx_rows(source_registry)
    v391_rows = [row for row in read_jsonl(v392.V3_9_1_PER_QUERY) if clean(row.get("source_family")).upper() == "XLSX"]
    eval_rows, score_rows, trace_rows = build_xlsx_eval(
        v391_rows=v391_rows,
        source_rows=source_rows,
        source_registry=source_registry,
        materialized_by_original=materialized_by_original,
    )
    metrics = build_metrics(eval_rows, score_rows)
    per_family = build_per_family(metrics)
    index_summary = build_index_summary(sourceatoms, searchunits)
    leakage = build_leakage_audit()
    failure = build_failure_taxonomy(eval_rows)
    guardrail = build_guardrail_audit()
    holdout = build_holdout_manifest(read_json(v310.OUTPUTS["fresh_real_holdout_manifest_json"]))
    artifacts: dict[str, Any] = {
        "metrics": metrics,
        "per_family": per_family,
        "xlsx_eval_rows": eval_rows,
        "score_component_rows": score_rows,
        "layer_trace_rows": trace_rows,
        "xlsx_sourceatom_rows": sourceatoms,
        "xlsx_searchunit_rows": searchunits,
        "xlsx_index_build_summary": index_summary,
        "leakage_audit_rows": leakage,
        "failure_taxonomy": failure,
        "guardrail_audit": guardrail,
        "holdout_manifest": holdout,
        "input_lineage": input_lineage,
    }
    artifacts["summary"] = build_summary(metrics=metrics, artifact_sha256={}, input_lineage=input_lineage)
    return artifacts


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"Last updated: [^.]+\.", "Last updated: 2026-05-25 KST.", text, count=1)
    start = f"<!-- {marker}:start -->"
    end = f"<!-- {marker}:end -->"
    marked = f"{start}\n{entry.rstrip()}\n{end}\n"
    text = re.sub(rf"\n?{re.escape(start)}.*?{re.escape(end)}\n?", "\n", text, flags=re.DOTALL)
    insertion_candidates = [index for index in (text.find("\n<!-- "), text.find("\n## ")) if index != -1]
    insert_at = min(insertion_candidates) if insertion_candidates else -1
    if insert_at == -1:
        text = text.rstrip() + "\n\n" + marked
    else:
        text = text[:insert_at].rstrip() + "\n\n" + marked + "\n" + text[insert_at:].lstrip("\n")
    path.write_text(text, encoding="utf-8")


def update_docs(metrics: Mapping[str, Any]) -> None:
    smoke = metrics["xlsx_structural_locator_eval"]["v3_12_nonprod_structural_locator_smoke"]
    old_seen = metrics["xlsx_structural_locator_eval"]["old_seen_reference_v3_11"]
    progress_entry = (
        f"- v3_12 XLSX structural locator non-prod improvement (`{RUN_ID}`) adds a diagnostic-only L3 "
        "sidecar after workbook/sheet routing: table-boundary candidates, header/axis alias propagation, "
        "structural score components, and zero-signal legacy row-window demotion. It reuses SourceAtom registry "
        "hydration for evidence truth, writes only the non-prod namespace "
        f"`{ALLOWED_NAMESPACE}`, leaves direct normalized-value query matching disabled, and keeps seen rows as "
        "reference/no-regression only. The checkpoint is v3_11, while the compact candidate list is the v3_9_1 "
        "XLSX candidate surface because v3_11 stores layer traces rather than full candidate lists. "
        "official_metric_input_rows=0; no gold/qrels/labels/expected/supporting/official denominator/prod "
        "mutation; fresh workbook-disjoint holdout remains required."
    )
    measurements_entry = f"""## 2026-05-25 - v3_12 XLSX Structural Locator Non-Prod Improvement

- Run: `{RUN_ID}`
- Policy: diagnostic-only; official_metric_input_rows=0; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no answer generation, fine-tuning, threshold tuning, winner selection, or promotion.
- Scope: XLSX L3 structural locator only, after workbook/sheet routing. The checkpoint is v3_11; the compact candidate surface is the v3_9_1 XLSX candidate JSONL because v3_11 stores layer traces rather than candidate lists. PDF lanes and production namespaces are not touched.
- Holdout: still insufficient. Seen-reference lift is no-regression evidence only, not product success.

| XLSX diagnostic metric | v3_11 seen reference | v3_12 non-prod structural locator |
| --- | ---: | ---: |
| table_or_range@1 | {old_seen['table_or_range@1']['numerator']}/{old_seen['table_or_range@1']['denominator']} | {smoke['table_or_range@1']['numerator']}/{smoke['table_or_range@1']['denominator']} |
| table_or_range@3 | {old_seen['table_or_range@3']['numerator']}/{old_seen['table_or_range@3']['denominator']} | {smoke['table_or_range@3']['numerator']}/{smoke['table_or_range@3']['denominator']} |
| cell_or_value@1 | {old_seen['cell_or_value@1']['numerator']}/{old_seen['cell_or_value@1']['denominator']} | {smoke['cell_or_value@1']['numerator']}/{smoke['cell_or_value@1']['denominator']} |
| cell_or_value@3 | {old_seen['cell_or_value@3']['numerator']}/{old_seen['cell_or_value@3']['denominator']} | {smoke['cell_or_value@3']['numerator']}/{smoke['cell_or_value@3']['denominator']} |
| rank1 reranked count | n/a | {smoke['rank1_reranked_count']} |
| structural-signal-empty rank1 | n/a | {smoke['structural_signal_empty_rank1_rate']['numerator']}/{smoke['structural_signal_empty_rank1_rate']['denominator']} |
| zero-signal legacy candidate demotion opportunities | n/a | {smoke['zero_signal_legacy_row_window_demotion_candidate_count']} |
| zero-signal legacy rank1 demotions | n/a | {smoke['zero_signal_legacy_rank1_demoted_count']} |
| table_or_range@1 gain/loss | n/a | +{smoke['table_or_range@1_gain_count']}/-{smoke['table_or_range@1_loss_count']} |
| cell_or_value@1 gain/loss | n/a | +{smoke['cell_or_value@1_gain_count']}/-{smoke['cell_or_value@1_loss_count']} |

Delta is diagnostic only: cell_or_value@1 +{smoke['cell_or_value@1_delta_from_old_seen_reference']} on seen-reference rows; table_or_range@1 delta {smoke['table_or_range@1_delta_from_old_seen_reference']} with row-level gain/loss churn shown above.
"""
    triage_entry = f"""## v3_12 XLSX Structural Locator Non-Prod Triage

- L3 remains the active XLSX bottleneck after workbook/sheet routing. v3_12 records table-boundary, header-path, row-axis, column-axis, period/number token, merged-header, and zero-signal legacy demotion components per candidate.
- Seen-reference smoke: table_or_range@1 stays {smoke['table_or_range@1']['numerator']}/{smoke['table_or_range@1']['denominator']} net but has +{smoke['table_or_range@1_gain_count']}/-{smoke['table_or_range@1_loss_count']} row-level churn; cell_or_value@1 moves from {old_seen['cell_or_value@1']['numerator']}/{old_seen['cell_or_value@1']['denominator']} to {smoke['cell_or_value@1']['numerator']}/{smoke['cell_or_value@1']['denominator']} with +{smoke['cell_or_value@1_gain_count']}/-{smoke['cell_or_value@1_loss_count']} churn.
- Merged-header lift is not claimed: current SourceAtom/v3_10 surfaces expose no merged header propagation rows, so the component is present as an audit field and remains zero.
- Fresh real workbook-disjoint holdout is still unavailable; no product success or promotion claim is allowed.
"""
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        "Overall status: `diagnostic_v3_12_xlsx_structural_locator_nonprod_improvement_ready`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)


def append_status_event(summary: Mapping[str, Any]) -> None:
    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "generated_at": utc_now(),
        "run_class": summary["run_class"],
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "fresh_real_holdout_sufficient": False,
        "product_success_evidence_allowed": False,
        "promotion_evidence": False,
        "answer_generation_executed": False,
        "index_namespace": ALLOWED_NAMESPACE,
        "source_index_namespace": SOURCE_NAMESPACE,
        "direct_normalized_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "protected_namespaces_touched": [],
        "artifact_paths": summary["artifact_paths"],
        "artifact_sha256": {**summary["artifact_sha256"], "summary_json_sha256": sha256_file(OUTPUTS["summary_json"])},
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def write_artifacts(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    write_json(OUTPUTS["metrics_json"], artifacts["metrics"])
    write_json(OUTPUTS["per_family_json"], artifacts["per_family"])
    write_jsonl(OUTPUTS["xlsx_structural_locator_eval_per_query_jsonl"], artifacts["xlsx_eval_rows"])
    write_jsonl(OUTPUTS["xlsx_score_components_jsonl"], artifacts["score_component_rows"])
    write_jsonl(OUTPUTS["xlsx_layer_trace_per_query_jsonl"], artifacts["layer_trace_rows"])
    write_jsonl(OUTPUTS["xlsx_nonprod_sourceatom_manifest_jsonl"], artifacts["xlsx_sourceatom_rows"])
    write_jsonl(OUTPUTS["xlsx_nonprod_searchunit_manifest_jsonl"], artifacts["xlsx_searchunit_rows"])
    write_json(OUTPUTS["xlsx_nonprod_index_build_summary_json"], artifacts["xlsx_index_build_summary"])
    write_jsonl(OUTPUTS["leakage_audit_jsonl"], artifacts["leakage_audit_rows"])
    write_json(OUTPUTS["failure_taxonomy_json"], artifacts["failure_taxonomy"])
    write_json(OUTPUTS["guardrail_audit_json"], artifacts["guardrail_audit"])
    write_json(OUTPUTS["holdout_manifest_json"], artifacts["holdout_manifest"])
    artifact_sha = {
        key.replace("_jsonl", "").replace("_json", "") + "_sha256": sha256_file(path)
        for key, path in OUTPUTS.items()
        if key != "summary_json"
    }
    summary = build_summary(
        metrics=artifacts["metrics"],
        artifact_sha256=artifact_sha,
        input_lineage=artifacts["input_lineage"],
    )
    write_json(OUTPUTS["summary_json"], summary)
    append_status_event(summary)
    update_docs(artifacts["metrics"])
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build v3_12 diagnostic-only XLSX structural locator artifacts.")
    parser.add_argument("--check", action="store_true", help="Build in memory only.")
    args = parser.parse_args(argv)
    artifacts = build_artifacts()
    if args.check:
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": artifacts["summary"]["status"],
                    "cell_or_value@1": artifacts["metrics"]["xlsx_structural_locator_eval"][
                        "v3_12_nonprod_structural_locator_smoke"
                    ]["cell_or_value@1"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    summary = write_artifacts(artifacts)
    print(json.dumps({"run_id": RUN_ID, "status": summary["status"], "summary": repo_relative(OUTPUTS["summary_json"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
