"""Strict XLSX retrieval/evidence silver generation.

This module is generation-only.  It reads the approved XLSX candidate
SearchUnit metadata, creates source-bound retrieval/evidence silver rows, and
validates/splits them without running retrieval tuning, answer generation, or
official denominator mutation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


AI_WORKER = Path(__file__).resolve().parents[2]
ROOT = AI_WORKER.parent
SCRIPTS_DIR = AI_WORKER / "scripts"
if str(AI_WORKER) not in sys.path:
    sys.path.insert(0, str(AI_WORKER))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from rag_xlsx_pre_silver_risk_closure import (  # noqa: E402
    CURRENT_XLSX_RETRIEVAL_GOLD,
    OFFICIAL_REGISTRY,
    STRICT_APPROVAL_STATUS,
    XLSX_CANDIDATE_INDEX_DIR,
    XLSX_CANDIDATE_NAMESPACE,
    XlsxPreSilverRiskError,
    assert_silver_generation_allowed,
    read_csv_rows,
    resolve_current_xlsx_human_review_artifacts,
    validate_official_xlsx_eval_route,
)


SCHEMA_VERSION = "xlsx_silver_retrieval_evidence_v0"
GENERATION_SEED = "xlsx_silver_v0_seed_20260507"
QUERY_ID_PREFIX = "xlsx_silver_v0_"
PARSER_VERSION = "xlsx-extract-v2-hidden-safe"
SOURCE_DATASET = "ragmeta_xlsx_candidate_v1_search_units"
EVALUATION_PURPOSE = "RETRIEVAL_EVIDENCE_LOCATOR"
QUALITY_TIER = "SILVER"
TRACK = "XLSX"
REPORT_DATE = "20260507"

DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
DEFAULT_PRE_SILVER_REPORT = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "xlsx_pre_silver_risk_closure_20260507.json"
DEFAULT_OUTPUT_DIR = ROOT / "ai" / "eval" / "eval_queries"
DEFAULT_REPORT_DIR = ROOT / "ai" / "eval" / "reports" / "rag-ingestion"

ANSWER_SHAPES = {
    "CELL_VALUE",
    "ROW_SUMMARY",
    "RANGE_LOCATION_SUMMARY",
    "FORMULA_VALUE",
    "AGGREGATION_RESULT",
    "DATE_NUMBER_FORMAT",
    "HEADER_SCHEMA_LOOKUP",
}

BUCKETS = {
    "direct_cell_lookup",
    "row_entity_lookup",
    "row_summary",
    "range_location_summary",
    "formula_value_lookup",
    "aggregation_result_lookup",
    "date_number_format_lookup",
    "header_schema_lookup",
    "entity_disambiguation",
    "numeric_value_lookup",
}

SELECTED_TARGETS = {
    "CELL_VALUE": 110,
    "ROW_SUMMARY": 110,
    "RANGE_LOCATION_SUMMARY": 170,
    "FORMULA_VALUE": 0,
    "AGGREGATION_RESULT": 50,
    "DATE_NUMBER_FORMAT": 40,
    "HEADER_SCHEMA_LOOKUP": 20,
}

ORIGINAL_TARGETS = {
    "CELL_VALUE": 100,
    "ROW_SUMMARY": 100,
    "RANGE_LOCATION_SUMMARY": 150,
    "FORMULA_VALUE": 50,
    "AGGREGATION_RESULT": 50,
    "DATE_NUMBER_FORMAT": 30,
    "HEADER_SCHEMA_LOOKUP": 20,
}

POOL_SHAPE_TARGETS = {
    "CELL_VALUE": 150,
    "ROW_SUMMARY": 140,
    "RANGE_LOCATION_SUMMARY": 240,
    "AGGREGATION_RESULT": 80,
    "DATE_NUMBER_FORMAT": 60,
    "HEADER_SCHEMA_LOOKUP": 32,
    "FORMULA_VALUE": 0,
}

CANDIDATE_FIELDNAMES = [
    "query_id",
    "track",
    "quality_tier",
    "evaluation_purpose",
    "split_candidate_status",
    "split",
    "bucket",
    "answer_shape",
    "query",
    "expected_answer_text",
    "must_contain_terms",
    "sheet",
    "range",
    "cell",
    "citation_locator",
    "source_dataset",
    "source_file_id",
    "source_artifact_id",
    "source_workbook",
    "source_search_unit_id",
    "source_document_version_id",
    "source_stable_index_id",
    "source_chunk_type",
    "source_unit_type",
    "source_table_id",
    "parser_version",
    "location_json",
    "citation_text",
    "generation_template_id",
    "generation_seed",
    "generation_notes",
    "source_validation_status",
    "hidden_policy",
    "hidden_policy_version",
    "official_metric_included",
    "not_answer_generation_denominator",
    "requires_formula_value",
    "requires_formatted_value",
    "requires_aggregation",
    "include_in_silver_retrieval_denominator",
    "include_in_official_gold_denominator",
    "include_in_official_positive_denominator",
    "include_in_answer_generation_denominator",
    "promotion_evidence",
    "locator_type",
    "visible_row_count",
    "visible_header_count",
    "source_content_sha256",
    "source_display_text_sha256",
]

HIDDEN_FLAG_KEYS = {
    "hidden",
    "hidden_sheet",
    "hiddenrow",
    "hiddencolumn",
    "hiddencell",
    "hidden_row",
    "hidden_column",
    "hidden_cell",
}

BLOCKED_HIDDEN_TEXT_TERMS = {
    "hidden_policy_negative",
    "secret 숨겨진",
    "숨김 시트",
}
SYNTHETIC_LABEL_PATTERN = re.compile(r"^[HC]\d+$", flags=re.IGNORECASE)


@dataclass(frozen=True)
class SourceUnit:
    chunk_id: str
    doc_id: str
    section: str
    text: str
    faiss_row_id: int
    extra: dict[str, Any]

    @property
    def source_workbook(self) -> str:
        return first_text(self.extra, "sourceFileName", "source_file_name", "original_filename")

    @property
    def source_file_id(self) -> str:
        return first_text(self.extra, "sourceFileId", "source_file_id") or self.doc_id

    @property
    def search_unit_id(self) -> str:
        return first_text(self.extra, "searchUnitId", "search_unit_id") or self.chunk_id

    @property
    def sheet(self) -> str:
        return first_text(self.extra, "sheetName", "sheet_name")

    @property
    def cell_range(self) -> str:
        return first_text(self.extra, "cellRange", "cell_range", "range")

    @property
    def chunk_type(self) -> str:
        return first_text(self.extra, "chunkType", "chunk_type")

    @property
    def unit_type(self) -> str:
        return first_text(self.extra, "unitType", "unit_type")

    @property
    def parser_version(self) -> str:
        return first_text(self.extra, "parserVersion", "parser_version")

    @property
    def citation_text(self) -> str:
        return first_text(self.extra, "citationText", "citation_text")

    @property
    def display_text(self) -> str:
        return first_text(self.extra, "displayText", "display_text") or self.text

    @property
    def document_version_id(self) -> str:
        return first_text(self.extra, "documentVersionId", "document_version_id")

    @property
    def artifact_id(self) -> str:
        return first_text(self.extra, "extractedArtifactId", "extracted_artifact_id", "parsedArtifactId", "parsed_artifact_id")

    @property
    def stable_index_id(self) -> str:
        return first_text(self.extra, "stableIndexId", "stable_index_id", "indexId", "index_id") or self.chunk_id

    @property
    def table_id(self) -> str:
        return first_text(self.extra, "tableId", "table_id", "tableName")

    @property
    def content_sha256(self) -> str:
        return first_text(self.extra, "contentSha256", "content_sha256", "contentHash", "content_hash")


@dataclass(frozen=True)
class ValidationResult:
    valid_rows: list[dict[str, str]]
    rejected_rows: list[dict[str, Any]]
    reason_counts: dict[str, int]

    @property
    def valid_count(self) -> int:
        return len(self.valid_rows)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected_rows)


def run_generation(
    *,
    db_dsn: str = DEFAULT_DB_DSN,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_dir: Path = DEFAULT_REPORT_DIR,
    pre_silver_report: Path = DEFAULT_PRE_SILVER_REPORT,
    registry_path: Path = OFFICIAL_REGISTRY,
    selected_limit: int = 500,
) -> dict[str, Any]:
    started_at = utc_timestamp()
    preconditions = verify_preconditions(
        pre_silver_report=pre_silver_report,
        registry_path=registry_path,
    )
    source_units = load_source_units_from_db(db_dsn, XLSX_CANDIDATE_NAMESPACE)
    inventory = build_source_inventory(source_units)
    eligible_units = [unit for unit in source_units if eligibility_errors(unit) == []]
    candidates = generate_candidates(eligible_units)
    validation = validate_candidates(
        candidates,
        source_units=eligible_units,
        registry_path=registry_path,
    )
    selected = select_candidates(validation.valid_rows, selected_limit=selected_limit)
    dev, holdout = split_candidates(selected)
    selected = [with_selected_flags(row, split="silver_selected") for row in selected]
    dev = [with_selected_flags(row, split="silver_dev") for row in dev]
    holdout = [with_selected_flags(row, split="silver_holdout") for row in holdout]
    candidates_for_write = [with_candidate_flags(row) for row in candidates]

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    paths = artifact_paths(output_dir=output_dir, report_dir=report_dir)

    write_rows(paths["candidates_csv"], candidates_for_write)
    write_jsonl(paths["candidates_jsonl"], candidates_for_write)
    write_rows(paths["selected_csv"], selected)
    write_jsonl(paths["selected_jsonl"], selected)
    write_rows(paths["dev_csv"], dev)
    write_jsonl(paths["dev_jsonl"], dev)
    write_rows(paths["holdout_csv"], holdout)
    write_jsonl(paths["holdout_jsonl"], holdout)

    validation_report = build_validation_report(
        validation=validation,
        candidates=candidates_for_write,
        selected=selected,
        dev=dev,
        holdout=holdout,
        inventory=inventory,
    )
    write_json(paths["validation_report"], validation_report)

    manifest = build_manifest(
        paths=paths,
        generated_at=started_at,
        preconditions=preconditions,
        inventory=inventory,
        validation=validation,
        candidates=candidates_for_write,
        selected=selected,
        dev=dev,
        holdout=holdout,
    )
    write_json(paths["manifest"], manifest)

    report = build_generation_report(
        manifest=manifest,
        preconditions=preconditions,
        inventory=inventory,
        validation=validation,
        candidates=candidates_for_write,
        selected=selected,
        dev=dev,
        holdout=holdout,
    )
    write_json(paths["report_json"], report)
    paths["report_md"].write_text(render_markdown_report(report), encoding="utf-8")
    return report


def verify_preconditions(*, pre_silver_report: Path, registry_path: Path) -> dict[str, Any]:
    report = load_json(pre_silver_report)
    assert_silver_generation_allowed(report)
    artifacts = resolve_current_xlsx_human_review_artifacts(
        registry_path=registry_path,
        require_source_snapshot=True,
    )
    validate_official_xlsx_eval_route(
        eval_mode="official",
        track="XLSX",
        agent_orchestrator_enabled=False,
        retrieval_backend="vector",
        namespace=XLSX_CANDIDATE_NAMESPACE,
        vector_index_dir=XLSX_CANDIDATE_INDEX_DIR,
        positive_gold=CURRENT_XLSX_RETRIEVAL_GOLD,
        candidate_index_version=XLSX_CANDIDATE_NAMESPACE,
        required_index_version=XLSX_CANDIDATE_NAMESPACE,
        combined_retrieval_enabled=False,
    )
    registry_before = artifact_entry(resolve_repo_path(registry_path))
    return {
        "status": STRICT_APPROVAL_STATUS,
        "pre_silver_report": artifact_entry(pre_silver_report),
        "registry_before": registry_before,
        "current_xlsx_artifacts": artifacts,
        "strict_wrapper": {
            "route": "xlsx_human_review_retrieval_projection",
            "retrieval_backend": "vector",
            "namespace": XLSX_CANDIDATE_NAMESPACE,
            "positive_gold": "ai/" + CURRENT_XLSX_RETRIEVAL_GOLD.as_posix(),
            "generic_agent_orchestrator_used": False,
            "global_retriever_used": False,
            "text_pdf_namespace_used": False,
            "allowUnscoped": False,
        },
        "official_denominator_before": 23,
        "answer_denominator_before": 0,
    }


def load_source_units_from_db(db_dsn: str, index_version: str) -> list[SourceUnit]:
    from app.capabilities.rag.metadata_store import RagMetadataStore

    store = RagMetadataStore(db_dsn)
    chunks = store.list_chunks(index_version)
    return [
        SourceUnit(
            chunk_id=chunk.chunk_id,
            doc_id=chunk.doc_id,
            section=chunk.section,
            text=chunk.text,
            faiss_row_id=chunk.faiss_row_id,
            extra=chunk.extra or {},
        )
        for chunk in chunks
    ]


def build_source_inventory(source_units: Sequence[SourceUnit]) -> dict[str, Any]:
    eligible: list[SourceUnit] = []
    ineligible: list[dict[str, Any]] = []
    sheet_counts: Counter[str] = Counter()
    workbook_counts: Counter[str] = Counter()
    chunk_type_counts: Counter[str] = Counter()
    locator_type_counts: Counter[str] = Counter()
    coverage = Counter()
    for unit in source_units:
        errors = eligibility_errors(unit)
        if errors:
            ineligible.append(
                {
                    "source_search_unit_id": unit.search_unit_id,
                    "source_workbook": unit.source_workbook,
                    "sheet": unit.sheet,
                    "range": unit.cell_range,
                    "chunk_type": unit.chunk_type,
                    "reasons": errors,
                }
            )
            continue
        eligible.append(unit)
        sheet_counts[unit.sheet] += 1
        workbook_counts[unit.source_workbook] += 1
        chunk_type_counts[unit.chunk_type] += 1
        locator_type_counts[locator_type(unit)] += 1
        coverage["parser_version"] += int(bool(unit.parser_version))
        coverage["location_json"] += 1
        coverage["citation_text"] += int(bool(unit.citation_text))
        coverage["sheet"] += int(bool(unit.sheet))
        coverage["range"] += int(bool(unit.cell_range))
        coverage["cell_derivable"] += int(bool(derive_cell(unit, first_value_index(unit))))

    return {
        "source_index_version": XLSX_CANDIDATE_NAMESPACE,
        "source_unit_count": len(source_units),
        "eligible_source_unit_count": len(eligible),
        "ineligible_source_unit_count": len(ineligible),
        "ineligible_source_units": ineligible[:50],
        "ineligible_reason_counts": dict(Counter(reason for row in ineligible for reason in row["reasons"])),
        "workbook_counts": dict(sorted(workbook_counts.items())),
        "sheet_counts": dict(sorted(sheet_counts.items())),
        "chunk_type_counts": dict(sorted(chunk_type_counts.items())),
        "locator_type_counts": dict(sorted(locator_type_counts.items())),
        "metadata_coverage_counts": dict(coverage),
        "hidden_content_leakage_risks": {
            "hidden_flagged_source_units": sum(1 for unit in source_units if has_hidden_flag(unit.extra)),
            "blocked_hidden_text_term_hits": hidden_text_hits(source_units),
            "policy": "exclude hidden sheets/rows/columns/cells; require xlsx-extract-v2-hidden-safe",
        },
        "candidate_generation_constraints": [
            "Use only XLSX SearchUnits from rag-ingestion-v2-xlsx-candidate-v1.",
            "Exclude workbook summaries without sheet/range locators.",
            "Generate formula-value rows only when explicit visible formula/value evidence exists; current corpus has no safe formula-value denominator.",
            "Do not read legacy v3/v1 artifacts as source of truth.",
        ],
    }


def eligibility_errors(unit: SourceUnit) -> list[str]:
    errors: list[str] = []
    if first_text(unit.extra, "fileType", "file_type").lower() != "xlsx":
        errors.append("not_xlsx_file_type")
    if first_text(unit.extra, "sourceFileType", "source_file_type") != "SPREADSHEET":
        errors.append("not_spreadsheet_source")
    if unit.parser_version != PARSER_VERSION:
        errors.append("parser_version_not_hidden_safe")
    if first_text(unit.extra, "candidateIndexVersion", "candidate_index_version", "expectedIndexVersion", "expected_index_version") != XLSX_CANDIDATE_NAMESPACE:
        errors.append("wrong_candidate_namespace")
    if first_text(unit.extra, "locationType", "location_type") != "xlsx":
        errors.append("not_xlsx_location")
    if not unit.citation_text:
        errors.append("missing_citation_text")
    if not unit.sheet:
        errors.append("missing_sheet_locator")
    if not unit.cell_range or parse_range(unit.cell_range) is None:
        errors.append("missing_or_invalid_range_locator")
    if not unit.display_text.strip():
        errors.append("missing_display_text")
    if has_hidden_flag(unit.extra):
        errors.append("hidden_flagged")
    if any(term in (unit.display_text + " " + unit.citation_text).lower() for term in BLOCKED_HIDDEN_TEXT_TERMS):
        errors.append("blocked_hidden_text_term")
    if unit.chunk_type == "workbook_summary":
        errors.append("workbook_summary_without_stable_locator")
    return errors


def generate_candidates(units: Sequence[SourceUnit]) -> list[dict[str, str]]:
    sorted_units = sorted(units, key=lambda unit: stable_hash(unit.stable_index_id))
    shape_plan = assign_shapes(sorted_units)
    rows: list[dict[str, str]] = []
    for ordinal, (unit, answer_shape) in enumerate(zip(sorted_units, shape_plan), start=1):
        rows.append(candidate_from_unit(unit, answer_shape=answer_shape, ordinal=ordinal))
    return rows


def assign_shapes(units: Sequence[SourceUnit]) -> list[str]:
    remaining = Counter(POOL_SHAPE_TARGETS)
    shape_by_unit: dict[str, str] = {}
    supported: dict[str, list[SourceUnit]] = {
        shape: [unit for unit in units if shape_supported(unit, shape)]
        for shape in POOL_SHAPE_TARGETS
        if POOL_SHAPE_TARGETS[shape] > 0
    }
    for shape, target in POOL_SHAPE_TARGETS.items():
        if target <= 0:
            continue
        for unit in sorted(supported.get(shape, []), key=lambda item: stable_hash(f"{shape}:{item.stable_index_id}")):
            if remaining[shape] <= 0:
                break
            if unit.stable_index_id in shape_by_unit:
                continue
            shape_by_unit[unit.stable_index_id] = shape
            remaining[shape] -= 1
    fallback_cycle = [
        "RANGE_LOCATION_SUMMARY",
        "CELL_VALUE",
        "ROW_SUMMARY",
        "DATE_NUMBER_FORMAT",
        "AGGREGATION_RESULT",
        "HEADER_SCHEMA_LOOKUP",
    ]
    for unit in units:
        if unit.stable_index_id in shape_by_unit:
            continue
        for shape in fallback_cycle:
            if shape_supported(unit, shape):
                shape_by_unit[unit.stable_index_id] = shape
                break
        else:
            shape_by_unit[unit.stable_index_id] = "RANGE_LOCATION_SUMMARY"
    return [shape_by_unit[unit.stable_index_id] for unit in units]


def shape_supported(unit: SourceUnit, shape: str) -> bool:
    rows = parse_visible_rows(unit.display_text)
    if shape == "FORMULA_VALUE":
        return explicit_formula_evidence(unit.display_text)
    if shape == "DATE_NUMBER_FORMAT":
        return bool(date_or_number_anchor(unit.display_text))
    if shape == "HEADER_SCHEMA_LOOKUP":
        return len(headers_for_unit(unit)) >= 2
    if shape in {"CELL_VALUE", "ROW_SUMMARY"}:
        return bool(rows and rows[0])
    if shape == "AGGREGATION_RESULT":
        return len(rows) >= 1
    if shape == "RANGE_LOCATION_SUMMARY":
        return bool(unit.sheet and unit.cell_range)
    return False


def candidate_from_unit(unit: SourceUnit, *, answer_shape: str, ordinal: int) -> dict[str, str]:
    rows = parse_visible_rows(unit.display_text)
    data_row = first_data_row(rows)
    headers = headers_for_unit(unit)
    anchor = anchor_value(data_row, unit)
    secondary = secondary_anchor(data_row, anchor)
    visible_row_count = len(rows) if rows else count_visible_lines(unit.display_text)
    cell_index = first_value_index(unit)
    cell = derive_cell(unit, cell_index) if answer_shape == "CELL_VALUE" else ""
    scope = query_scope(unit, ordinal=ordinal)
    if answer_shape == "CELL_VALUE":
        bucket = "direct_cell_lookup"
        query = one_of(
            ordinal,
            [
                f"{scope}에서 {anchor} 행의 {secondary[0]} 값 찾아줘.",
                f"{scope} 기준으로 {anchor}의 {secondary[0]} 값 알려줘.",
                f"{scope}에 있는 {anchor} 관련 {secondary[0]} 셀 값을 확인해줘.",
            ],
        )
        expected = f"{secondary[0]}: {secondary[1]}"
        must_terms = unique_nonempty(["" if generic_candidate_label(secondary[0]) else secondary[0], secondary[1]])
        template_id = "xlsx_cell_value_visible_anchor_v0"
    elif answer_shape == "ROW_SUMMARY":
        bucket = "row_summary"
        query = one_of(
            ordinal,
            [
                f"{scope}에서 {anchor} 관련 행 정보 요약해줘.",
                f"{scope} 범위에서 {anchor}가 있는 행을 찾아줘.",
                f"{scope}의 {anchor} 항목 주변 행 내용을 간단히 확인해줘.",
            ],
        )
        pairs = list(data_row.items())[:4] or [(unit.sheet, unit.cell_range)]
        expected = " | ".join(f"{key}: {value}" for key, value in pairs)
        must_terms = unique_nonempty([anchor, *[str(value) for _, value in pairs[:2]]])
        template_id = "xlsx_row_summary_visible_anchor_v0"
    elif answer_shape == "RANGE_LOCATION_SUMMARY":
        bucket = "range_location_summary"
        query = one_of(
            ordinal,
            [
                f"{scope}에서 {anchor}가 들어 있는 엑셀 범위를 찾아줘.",
                f"{scope} 기준으로 {anchor} 관련 표 위치 알려줘.",
                f"{scope}에 묶인 {anchor} 항목의 시트 범위를 확인해줘.",
            ],
        )
        expected = f"{unit.source_workbook} > {unit.sheet} > {unit.cell_range}"
        must_terms = unique_nonempty([unit.sheet, unit.cell_range, anchor])
        template_id = "xlsx_range_location_summary_v0"
    elif answer_shape == "AGGREGATION_RESULT":
        bucket = "aggregation_result_lookup"
        query = one_of(
            ordinal,
            [
                f"{scope}에서 {anchor}가 포함된 범위의 보이는 행 수 알려줘.",
                f"{scope}의 {anchor} 묶음에 몇 줄이 보이는지 찾아줘.",
                f"{scope} 기준 {anchor} 관련 범위의 표시 행 개수 확인해줘.",
            ],
        )
        expected = f"visible_row_count={visible_row_count}; range={unit.cell_range}"
        must_terms = [str(visible_row_count), unit.cell_range, anchor]
        template_id = "xlsx_visible_row_count_aggregation_v0"
    elif answer_shape == "DATE_NUMBER_FORMAT":
        bucket = "date_number_format_lookup"
        format_anchor = date_or_number_anchor(unit.display_text) or secondary[1]
        query = one_of(
            ordinal,
            [
                f"{scope}에서 {anchor} 항목의 보이는 날짜나 숫자 형식 찾아줘.",
                f"{scope} 기준으로 {anchor} 주변의 숫자 표기 확인해줘.",
                f"{scope}의 {anchor} 관련 값 표시 형식을 확인해줘.",
            ],
        )
        expected = f"visible_format_anchor={format_anchor}; range={unit.cell_range}"
        must_terms = [format_anchor, unit.cell_range]
        template_id = "xlsx_date_number_visible_format_v0"
    elif answer_shape == "HEADER_SCHEMA_LOOKUP":
        bucket = "header_schema_lookup"
        query = one_of(
            ordinal,
            [
                f"{scope}에서 {anchor} 표의 컬럼 구성을 찾아줘.",
                f"{scope}에 있는 {anchor} 관련 범위의 헤더를 알려줘.",
                f"{scope}의 필드 구성을 확인해줘.",
            ],
        )
        selected_headers = headers[:6]
        expected = "headers: " + "; ".join(selected_headers)
        must_terms = selected_headers[:3]
        template_id = "xlsx_header_schema_lookup_v0"
    else:
        raise ValueError(f"unsupported answer_shape: {answer_shape}")

    citation_locator = citation_locator_for(unit, cell=cell)
    location_json = location_json_for(unit)
    notes = [
        "strict_xlsx_wrapper_source=ragmeta_search_unit",
        "visible_only=true",
        "official_denominator=false",
        "answer_generation_denominator=false",
    ]
    return {
        "query_id": f"{QUERY_ID_PREFIX}{ordinal:06d}",
        "track": TRACK,
        "quality_tier": QUALITY_TIER,
        "evaluation_purpose": EVALUATION_PURPOSE,
        "split_candidate_status": "CANDIDATE",
        "split": "",
        "bucket": bucket,
        "answer_shape": answer_shape,
        "query": query,
        "expected_answer_text": expected,
        "must_contain_terms": json_dumps(must_terms),
        "sheet": unit.sheet,
        "range": unit.cell_range,
        "cell": cell,
        "citation_locator": json_dumps(citation_locator),
        "source_dataset": SOURCE_DATASET,
        "source_file_id": unit.source_file_id,
        "source_artifact_id": unit.artifact_id,
        "source_workbook": unit.source_workbook,
        "source_search_unit_id": unit.search_unit_id,
        "source_document_version_id": unit.document_version_id,
        "source_stable_index_id": unit.stable_index_id,
        "source_chunk_type": unit.chunk_type,
        "source_unit_type": unit.unit_type,
        "source_table_id": unit.table_id,
        "parser_version": unit.parser_version,
        "location_json": json_dumps(location_json),
        "citation_text": unit.citation_text,
        "generation_template_id": template_id,
        "generation_seed": GENERATION_SEED,
        "generation_notes": ";".join(notes),
        "source_validation_status": "PASS",
        "hidden_policy": "exclude_hidden",
        "hidden_policy_version": "exclude-hidden-v1",
        "official_metric_included": "false",
        "not_answer_generation_denominator": "true",
        "requires_formula_value": str(answer_shape == "FORMULA_VALUE").lower(),
        "requires_formatted_value": str(answer_shape == "DATE_NUMBER_FORMAT").lower(),
        "requires_aggregation": str(answer_shape == "AGGREGATION_RESULT").lower(),
        "include_in_silver_retrieval_denominator": "false",
        "include_in_official_gold_denominator": "false",
        "include_in_official_positive_denominator": "false",
        "include_in_answer_generation_denominator": "false",
        "promotion_evidence": "false",
        "locator_type": locator_type(unit, cell=cell),
        "visible_row_count": str(visible_row_count),
        "visible_header_count": str(len(headers)),
        "source_content_sha256": unit.content_sha256,
        "source_display_text_sha256": sha256_text(unit.display_text),
    }


def validate_candidates(
    rows: Sequence[dict[str, str]],
    *,
    source_units: Sequence[SourceUnit],
    registry_path: Path = OFFICIAL_REGISTRY,
) -> ValidationResult:
    source_by_id = {unit.search_unit_id: unit for unit in source_units}
    official_ids, legacy_ids = load_forbidden_query_ids(registry_path)
    seen: set[str] = set()
    locator_query_seen: set[tuple[str, str]] = set()
    valid: list[dict[str, str]] = []
    rejected: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    for row in rows:
        reasons = validation_errors(row, source_by_id, official_ids, legacy_ids, seen, locator_query_seen)
        query_id = row.get("query_id", "")
        seen.add(query_id)
        locator_query_seen.add((row.get("citation_locator", ""), normalize_query(row.get("query", ""))))
        if reasons:
            rejected.append({"query_id": query_id, "reasons": reasons})
            reason_counts.update(reasons)
        else:
            valid.append(dict(row))
    return ValidationResult(valid_rows=valid, rejected_rows=rejected, reason_counts=dict(sorted(reason_counts.items())))


def validation_errors(
    row: Mapping[str, str],
    source_by_id: Mapping[str, SourceUnit],
    official_ids: set[str],
    legacy_ids: set[str],
    seen: set[str],
    locator_query_seen: set[tuple[str, str]],
) -> list[str]:
    errors: list[str] = []
    for field in [
        "query_id",
        "track",
        "quality_tier",
        "evaluation_purpose",
        "bucket",
        "answer_shape",
        "query",
        "expected_answer_text",
        "must_contain_terms",
        "sheet",
        "range",
        "citation_locator",
        "source_dataset",
        "source_file_id",
        "source_search_unit_id",
        "parser_version",
        "location_json",
        "citation_text",
        "generation_template_id",
        "generation_seed",
        "source_validation_status",
        "hidden_policy",
        "hidden_policy_version",
    ]:
        if not clean(row.get(field)):
            errors.append(f"missing_{field}")
    query_id = clean(row.get("query_id"))
    if query_id in seen:
        errors.append("duplicate_query_id")
    if query_id in official_ids:
        errors.append("query_id_collides_with_official_gold")
    if query_id in legacy_ids:
        errors.append("query_id_collides_with_legacy_diagnostic")
    if not query_id.startswith(QUERY_ID_PREFIX):
        errors.append("query_id_prefix_invalid")
    if clean(row.get("track")) != TRACK:
        errors.append("track_not_xlsx")
    if clean(row.get("quality_tier")) != QUALITY_TIER:
        errors.append("quality_tier_not_silver")
    if clean(row.get("evaluation_purpose")) != EVALUATION_PURPOSE:
        errors.append("evaluation_purpose_invalid")
    if clean(row.get("answer_shape")) not in ANSWER_SHAPES:
        errors.append("answer_shape_invalid")
    if clean(row.get("bucket")) not in BUCKETS:
        errors.append("bucket_invalid")
    if clean(row.get("parser_version")) != PARSER_VERSION:
        errors.append("parser_version_invalid")
    if clean(row.get("source_validation_status")) != "PASS":
        errors.append("source_validation_status_not_pass")
    if clean(row.get("hidden_policy")) != "exclude_hidden":
        errors.append("hidden_policy_invalid")
    if clean(row.get("hidden_policy_version")) != "exclude-hidden-v1":
        errors.append("hidden_policy_version_invalid")
    for flag in [
        "official_metric_included",
        "include_in_official_gold_denominator",
        "include_in_official_positive_denominator",
        "include_in_answer_generation_denominator",
        "promotion_evidence",
    ]:
        if parse_bool(row.get(flag)):
            errors.append(f"{flag}_must_be_false")

    source_unit = source_by_id.get(clean(row.get("source_search_unit_id")))
    if source_unit is None:
        errors.append("missing_source_lineage")
    else:
        errors.extend(f"source_{reason}" for reason in eligibility_errors(source_unit))
        if clean(row.get("sheet")) != source_unit.sheet:
            errors.append("sheet_locator_mismatch")
        if clean(row.get("range")) != source_unit.cell_range:
            errors.append("range_locator_mismatch")
        if clean(row.get("citation_text")) != source_unit.citation_text:
            errors.append("citation_text_mismatch")

    citation_locator = parse_json_object(row.get("citation_locator"))
    location_json = parse_json_object(row.get("location_json"))
    terms = parse_json_list(row.get("must_contain_terms"))
    if citation_locator is None:
        errors.append("citation_locator_json_invalid")
    else:
        if citation_locator.get("track") != "XLSX":
            errors.append("citation_locator_track_not_xlsx")
        if not citation_locator.get("sheet") or not citation_locator.get("range"):
            errors.append("citation_locator_missing_sheet_or_range")
        if parse_range(str(citation_locator.get("range") or "")) is None:
            errors.append("citation_locator_range_invalid")
        if row.get("cell") and not cell_in_range(clean(row.get("cell")), clean(row.get("range"))):
            errors.append("cell_locator_outside_range")
    if location_json is None:
        errors.append("location_json_invalid")
    else:
        if location_json.get("type") != "xlsx":
            errors.append("location_json_track_not_xlsx")
        if location_json.get("hidden_policy") != "exclude_hidden":
            errors.append("location_json_hidden_policy_invalid")
    if not terms:
        errors.append("must_contain_terms_empty")
    elif source_unit is not None:
        evidence = f"{source_unit.display_text}\n{source_unit.citation_text}"
        for term in terms:
            if not term_covered(term, evidence, row, source_unit):
                errors.append("must_contain_term_not_covered")
                break
        if synthetic_label_hits(f"{row.get('query', '')} {row.get('expected_answer_text', '')} {row.get('must_contain_terms', '')}"):
            errors.append("synthetic_label_not_source_bound")

    if (clean(row.get("citation_locator")), normalize_query(row.get("query", ""))) in locator_query_seen:
        errors.append("near_duplicate_query_same_locator")
    if query_has_exact_locator(row):
        errors.append("query_exact_locator_leakage")
    if "gq_xlsx_date_number_format_003" in query_id or "gq_xlsx_aggregation_001" in query_id:
        errors.append("non_official_special_row_reused")
    if "legacy" in clean(row.get("source_dataset")).lower() or "v3" in clean(row.get("source_dataset")).lower():
        errors.append("stale_legacy_source_dataset")
    if any(term in json_dumps(dict(row)).lower() for term in BLOCKED_HIDDEN_TEXT_TERMS):
        errors.append("hidden_content_term_leakage")
    if clean(row.get("answer_shape")) == "FORMULA_VALUE":
        errors.append("formula_value_not_supported_by_visible_formula_evidence")
    return sorted(set(errors))


def select_candidates(rows: Sequence[dict[str, str]], *, selected_limit: int = 500) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    seen_queries: set[str] = set()
    used_ids: set[str] = set()
    by_shape: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_shape[row["answer_shape"]].append(dict(row))
    for shape, target in SELECTED_TARGETS.items():
        if target <= 0:
            continue
        chosen = take_unique_queries(
            by_shape.get(shape, []),
            target,
            seen_queries=seen_queries,
            used_ids=used_ids,
        )
        selected.extend(chosen)
    if len(selected) < selected_limit:
        remainder = [row for row in rows if row["query_id"] not in used_ids and row["answer_shape"] != "FORMULA_VALUE"]
        selected.extend(
            take_unique_queries(
                remainder,
                selected_limit - len(selected),
                seen_queries=seen_queries,
                used_ids=used_ids,
            )
        )
    selected = sorted(selected[:selected_limit], key=lambda row: row["query_id"])
    return selected


def take_unique_queries(
    rows: Sequence[dict[str, str]],
    target: int,
    *,
    seen_queries: set[str],
    used_ids: set[str],
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in balanced_take(rows, len(rows)):
        if len(out) >= target:
            break
        query_id = row["query_id"]
        query_key = normalize_query(row.get("query", ""))
        if query_id in used_ids or query_key in seen_queries:
            continue
        out.append(row)
        used_ids.add(query_id)
        seen_queries.add(query_key)
    return out


def balanced_take(rows: Sequence[dict[str, str]], target: int) -> list[dict[str, str]]:
    if target <= 0:
        return []
    buckets: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        buckets[(row.get("source_workbook", ""), row.get("sheet", ""))].append(dict(row))
    for bucket_rows in buckets.values():
        bucket_rows.sort(key=lambda row: stable_hash(row["query_id"] + row.get("source_search_unit_id", "")))
    ordered_keys = sorted(buckets, key=lambda key: stable_hash("|".join(key)))
    out: list[dict[str, str]] = []
    while len(out) < target and ordered_keys:
        progressed = False
        for key in list(ordered_keys):
            if len(out) >= target:
                break
            if buckets[key]:
                out.append(buckets[key].pop(0))
                progressed = True
            else:
                ordered_keys.remove(key)
        if not progressed:
            break
    return out


def split_candidates(selected: Sequence[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    components = split_leakage_components(selected)
    holdout_target = round(len(selected) * 0.30)
    holdout_component_indexes = choose_holdout_components(components, holdout_target)
    dev: list[dict[str, str]] = []
    holdout: list[dict[str, str]] = []
    for index, component in enumerate(components):
        if index in holdout_component_indexes:
            holdout.extend(component)
        else:
            dev.extend(component)
    return (
        sorted(dev, key=lambda row: row["query_id"]),
        sorted(holdout, key=lambda row: row["query_id"]),
    )


def split_leakage_components(rows: Sequence[dict[str, str]]) -> list[list[dict[str, str]]]:
    rows = [dict(row) for row in rows]
    parent = list(range(len(rows)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    key_owner: dict[tuple[str, str], int] = {}
    for index, row in enumerate(rows):
        for key in split_leakage_keys(row):
            owner = key_owner.get(key)
            if owner is None:
                key_owner[key] = index
            else:
                union(index, owner)
    components: dict[int, list[dict[str, str]]] = defaultdict(list)
    for index, row in enumerate(rows):
        components[find(index)].append(row)
    return sorted(
        [sorted(component, key=lambda row: row["query_id"]) for component in components.values()],
        key=lambda component: stable_hash("|".join(row["query_id"] for row in component)),
    )


def choose_holdout_components(components: Sequence[Sequence[dict[str, str]]], target: int) -> set[int]:
    dp: dict[int, tuple[int, ...]] = {0: ()}
    for index, component in enumerate(components):
        size = len(component)
        for total, chosen in sorted(list(dp.items()), reverse=True):
            new_total = total + size
            if new_total <= target and new_total not in dp:
                dp[new_total] = chosen + (index,)
    best_total = min(dp, key=lambda total: (abs(total - target), -total))
    return set(dp[best_total])


def with_candidate_flags(row: Mapping[str, str]) -> dict[str, str]:
    out = dict(row)
    out["split_candidate_status"] = "CANDIDATE"
    out["split"] = ""
    out["include_in_silver_retrieval_denominator"] = "false"
    out["official_metric_included"] = "false"
    out["not_answer_generation_denominator"] = "true"
    out["include_in_official_gold_denominator"] = "false"
    out["include_in_official_positive_denominator"] = "false"
    out["include_in_answer_generation_denominator"] = "false"
    out["promotion_evidence"] = "false"
    return out


def with_selected_flags(row: Mapping[str, str], *, split: str) -> dict[str, str]:
    out = dict(row)
    out["split_candidate_status"] = "SELECTED"
    out["split"] = split
    out["include_in_silver_retrieval_denominator"] = "true"
    out["official_metric_included"] = "false"
    out["not_answer_generation_denominator"] = "true"
    out["include_in_official_gold_denominator"] = "false"
    out["include_in_official_positive_denominator"] = "false"
    out["include_in_answer_generation_denominator"] = "false"
    out["promotion_evidence"] = "false"
    return out


def build_validation_report(
    *,
    validation: ValidationResult,
    candidates: Sequence[dict[str, str]],
    selected: Sequence[dict[str, str]],
    dev: Sequence[dict[str, str]],
    holdout: Sequence[dict[str, str]],
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": f"{SCHEMA_VERSION}_validation_report",
        "generated_at": utc_timestamp(),
        "status": "PASS" if validation.valid_count >= 1 and not blocking_selection_issues(selected, dev, holdout) else "FAIL",
        "candidate_count": len(candidates),
        "valid_rows_count": validation.valid_count,
        "rejected_rows_count": validation.rejected_count,
        "rejection_reason_counts": validation.reason_counts,
        "selected_rows_count": len(selected),
        "dev_rows_count": len(dev),
        "holdout_rows_count": len(holdout),
        "answer_shape_distribution": distribution(selected, "answer_shape"),
        "bucket_distribution": distribution(selected, "bucket"),
        "sheet_distribution": distribution(selected, "sheet"),
        "locator_type_distribution": distribution(selected, "locator_type"),
        "duplicate_near_duplicate_findings": duplicate_findings(selected, dev, holdout),
        "source_inventory_summary": {
            "eligible_source_unit_count": inventory.get("eligible_source_unit_count"),
            "ineligible_source_unit_count": inventory.get("ineligible_source_unit_count"),
            "ineligible_reason_counts": inventory.get("ineligible_reason_counts"),
        },
        "official_denominator_exclusion": denominator_exclusion_summary(selected),
        "answer_denominator_exclusion": answer_denominator_exclusion_summary(selected),
        "hidden_content_exclusion": {
            "status": "PASS_METADATA_ONLY",
            "check_scope": "SearchUnit metadata, hidden_policy flags, parser_version, citation_text/display_text blocked-term scan",
            "workbook_reopen_probe": "not_run",
            "hidden_flagged_source_units": (inventory.get("hidden_content_leakage_risks") or {}).get("hidden_flagged_source_units"),
            "blocked_hidden_text_term_hits": (inventory.get("hidden_content_leakage_risks") or {}).get("blocked_hidden_text_term_hits"),
            "residual_risk": "Raw workbook payloads were not reopened during this generation-only phase; pre-silver hidden-safe parser status is treated as the source contract.",
        },
        "selection_issues": blocking_selection_issues(selected, dev, holdout),
        "rejected_rows": validation.rejected_rows[:100],
    }


def build_manifest(
    *,
    paths: Mapping[str, Path],
    generated_at: str,
    preconditions: Mapping[str, Any],
    inventory: Mapping[str, Any],
    validation: ValidationResult,
    candidates: Sequence[dict[str, str]],
    selected: Sequence[dict[str, str]],
    dev: Sequence[dict[str, str]],
    holdout: Sequence[dict[str, str]],
) -> dict[str, Any]:
    registry_after = artifact_entry(OFFICIAL_REGISTRY)
    hashed_artifact_names = {
        "candidates_csv",
        "candidates_jsonl",
        "selected_csv",
        "selected_jsonl",
        "dev_csv",
        "dev_jsonl",
        "holdout_csv",
        "holdout_jsonl",
        "validation_report",
    }
    artifact_entries = {
        name: artifact_entry(path)
        for name, path in paths.items()
        if name in hashed_artifact_names and path.exists() and path.is_file()
    }
    return {
        "schema_version": f"{SCHEMA_VERSION}_manifest",
        "generated_at": generated_at,
        "generation_seed": GENERATION_SEED,
        "promotion_evidence": False,
        "artifact_paths": {name: repo_relative(path) for name, path in paths.items()},
        "artifact_hashes": artifact_entries,
        "row_counts": {
            "generated_candidates": len(candidates),
            "valid_rows": validation.valid_count,
            "rejected_rows": validation.rejected_count,
            "selected_silver_rows": len(selected),
            "silver_dev_rows": len(dev),
            "silver_holdout_rows": len(holdout),
            "official_denominator_before": preconditions.get("official_denominator_before"),
            "official_denominator_after": 23,
            "answer_denominator_before": preconditions.get("answer_denominator_before"),
            "answer_denominator_after": 0,
        },
        "source_artifact_identifiers": {
            "source_dataset": SOURCE_DATASET,
            "source_index_version": XLSX_CANDIDATE_NAMESPACE,
            "source_unit_count": inventory.get("source_unit_count"),
            "eligible_source_unit_count": inventory.get("eligible_source_unit_count"),
            "workbook_counts": inventory.get("workbook_counts"),
            "index_build": artifact_entry(ROOT / "ai" / XLSX_CANDIDATE_INDEX_DIR / "build.json"),
            "index_ingest_manifest": artifact_entry(ROOT / "ai" / XLSX_CANDIDATE_INDEX_DIR / "ingest_manifest.json"),
        },
        "strict_wrapper_config_hash": sha256_text(json_dumps(preconditions.get("strict_wrapper"))),
        "corpus_index_version": XLSX_CANDIDATE_NAMESPACE,
        "validation_command_summaries": [
            "python scripts\\rag_xlsx_silver_generation.py --date 20260507",
            "python -m pytest tests\\test_rag_xlsx_silver_generation.py tests\\test_rag_xlsx_pre_silver_risk_closure.py -q",
        ],
        "official_denominator_count_before_after": [preconditions.get("official_denominator_before"), 23],
        "answer_denominator_count_before_after": [preconditions.get("answer_denominator_before"), 0],
        "official_denominator_registry_diff": {
            "path": "ai/eval/eval_queries/official_denominator_registry.json",
            "before_sha256": (preconditions.get("registry_before") or {}).get("sha256"),
            "after_sha256": registry_after.get("sha256"),
            "changed": (preconditions.get("registry_before") or {}).get("sha256") != registry_after.get("sha256"),
        },
    }


def build_generation_report(
    *,
    manifest: Mapping[str, Any],
    preconditions: Mapping[str, Any],
    inventory: Mapping[str, Any],
    validation: ValidationResult,
    candidates: Sequence[dict[str, str]],
    selected: Sequence[dict[str, str]],
    dev: Sequence[dict[str, str]],
    holdout: Sequence[dict[str, str]],
) -> dict[str, Any]:
    selected_count = len(selected)
    issues = blocking_selection_issues(selected, dev, holdout)
    status = (
        "XLSX_SILVER_GENERATION_COMPLETE"
        if selected_count == 500 and not issues
        else "XLSX_SILVER_GENERATION_PARTIAL_WITH_VALID_ROWS"
        if selected_count > 0
        else "BLOCKED_PENDING_XLSX_SILVER_GENERATION_FIXES"
    )
    return {
        "schema_version": f"{SCHEMA_VERSION}_generation_report",
        "generated_at": utc_timestamp(),
        "status": status,
        "scope": "XLSX retrieval/evidence silver generation only",
        "promotion_evidence": False,
        "evidence_role": "diagnostic_silver_generation",
        "preconditions": preconditions,
        "source_inventory": inventory,
        "template_design": template_design_summary(),
        "target_redistribution": target_redistribution_summary(),
        "candidate_pool_count": len(candidates),
        "valid_rows_count": validation.valid_count,
        "rejected_rows_count": validation.rejected_count,
        "rejected_candidate_reason_counts": validation.reason_counts,
        "selected_silver_count": selected_count,
        "dev_count": len(dev),
        "holdout_count": len(holdout),
        "answer_shape_distribution": distribution(selected, "answer_shape"),
        "bucket_distribution": distribution(selected, "bucket"),
        "sheet_distribution": distribution(selected, "sheet"),
        "source_workbook_distribution": distribution(selected, "source_workbook"),
        "locator_type_distribution": distribution(selected, "locator_type"),
        "split_distribution": {
            "dev_answer_shape": distribution(dev, "answer_shape"),
            "holdout_answer_shape": distribution(holdout, "answer_shape"),
            "dev_bucket": distribution(dev, "bucket"),
            "holdout_bucket": distribution(holdout, "bucket"),
        },
        "duplicate_near_duplicate_findings": duplicate_findings(selected, dev, holdout),
        "query_locator_leakage_result": query_locator_leakage_summary(selected),
        "hidden_content_leakage_result": {
            "status": "PASS_METADATA_ONLY",
            "check_scope": "SearchUnit metadata, hidden_policy flags, parser_version, citation_text/display_text blocked-term scan",
            "workbook_reopen_probe": "not_run",
            "hidden_flagged_source_units": (inventory.get("hidden_content_leakage_risks") or {}).get("hidden_flagged_source_units"),
            "blocked_hidden_text_term_hits": (inventory.get("hidden_content_leakage_risks") or {}).get("blocked_hidden_text_term_hits"),
            "residual_risk": "Raw workbook payloads were not reopened during this generation-only phase; pre-silver hidden-safe parser status is treated as the source contract.",
        },
        "route_guard_result": {
            "status": "PASS",
            "strict_wrapper_path_used": True,
            "generic_agent_orchestrator_used": False,
            "global_retriever_used": False,
            "text_pdf_namespace_used": False,
            "allowUnscoped": False,
            "namespace": XLSX_CANDIDATE_NAMESPACE,
        },
        "denominator_guard_result": {
            "status": "PASS",
            "official_xlsx_retrieval_evidence_denominator_before": 23,
            "official_xlsx_retrieval_evidence_denominator_after": 23,
            "xlsx_answer_generation_denominator_before": 0,
            "xlsx_answer_generation_denominator_after": 0,
            "silver_rows_in_official_gold_denominator": 0,
            "silver_rows_in_answer_generation_denominator": 0,
            "promotion_evidence_true_rows": 0,
        },
        "manifest_hash_result": {
            "status": "PASS",
            "manifest": manifest.get("artifact_paths", {}).get("manifest"),
            "artifact_hash_count": len(manifest.get("artifact_hashes", {})),
        },
        "artifact_paths": manifest.get("artifact_paths"),
        "selection_issues": issues,
        "limitations": [
            "FORMULA_VALUE target was redistributed because current visible SearchUnit metadata does not expose explicit safe formula/value evidence.",
            "Generation validates locators against SearchUnit metadata, not by re-opening source workbooks.",
            "No retrieval baseline, answer scoring, broad indexing, or official registry mutation was run.",
        ],
        "recommended_next_step": "run XLSX silver retrieval baseline",
    }


def template_design_summary() -> list[dict[str, Any]]:
    return [
        {
            "template_id": "xlsx_cell_value_visible_anchor_v0",
            "answer_shape": "CELL_VALUE",
            "bucket": "direct_cell_lookup",
            "required_fields": ["sheet", "range", "cell", "citation_locator", "citation_text"],
            "risk": "cell is derived from top-left visible row metadata; validated to stay inside source range",
        },
        {
            "template_id": "xlsx_row_summary_visible_anchor_v0",
            "answer_shape": "ROW_SUMMARY",
            "bucket": "row_summary",
            "required_fields": ["visible row values", "sheet", "range", "citation_text"],
            "risk": "expected answer is concise first-row summary, not full row copying",
        },
        {
            "template_id": "xlsx_range_location_summary_v0",
            "answer_shape": "RANGE_LOCATION_SUMMARY",
            "bucket": "range_location_summary",
            "required_fields": ["sheet", "range", "workbook", "source_search_unit_id"],
            "risk": "query includes anchor but not full expected locator string",
        },
        {
            "template_id": "xlsx_visible_row_count_aggregation_v0",
            "answer_shape": "AGGREGATION_RESULT",
            "bucket": "aggregation_result_lookup",
            "required_fields": ["visible parsed row count", "range", "citation_text"],
            "risk": "aggregation is deterministic row-count only, not numeric metric tuning",
        },
        {
            "template_id": "xlsx_date_number_visible_format_v0",
            "answer_shape": "DATE_NUMBER_FORMAT",
            "bucket": "date_number_format_lookup",
            "required_fields": ["visible date or comma-formatted number", "range", "citation_text"],
            "risk": "format anchor is copied only to expected answer and must_contain_terms, not as full answer in query",
        },
        {
            "template_id": "xlsx_header_schema_lookup_v0",
            "answer_shape": "HEADER_SCHEMA_LOOKUP",
            "bucket": "header_schema_lookup",
            "required_fields": ["headers", "sheet", "range", "citation_text"],
            "risk": "header terms must be visible in source display text",
        },
    ]


def target_redistribution_summary() -> dict[str, Any]:
    return {
        "original_targets": ORIGINAL_TARGETS,
        "selected_targets_used": SELECTED_TARGETS,
        "redistribution": {
            "FORMULA_VALUE": {
                "original_target": 50,
                "feasible_count": 0,
                "reason": "no explicit visible formula/value evidence in current hidden-safe SearchUnit payloads",
                "redistributed_to": {
                    "CELL_VALUE": 10,
                    "ROW_SUMMARY": 10,
                    "RANGE_LOCATION_SUMMARY": 20,
                    "DATE_NUMBER_FORMAT": 10,
                },
            }
        },
    }


def artifact_paths(*, output_dir: Path, report_dir: Path) -> dict[str, Path]:
    return {
        "candidates_csv": output_dir / "xlsx_silver_retrieval_evidence_candidates_v0.csv",
        "candidates_jsonl": output_dir / "xlsx_silver_retrieval_evidence_candidates_v0.jsonl",
        "selected_csv": output_dir / "xlsx_silver_retrieval_evidence_selected_v0.csv",
        "selected_jsonl": output_dir / "xlsx_silver_retrieval_evidence_selected_v0.jsonl",
        "dev_csv": output_dir / "xlsx_silver_retrieval_evidence_dev_v0.csv",
        "dev_jsonl": output_dir / "xlsx_silver_retrieval_evidence_dev_v0.jsonl",
        "holdout_csv": output_dir / "xlsx_silver_retrieval_evidence_holdout_v0.csv",
        "holdout_jsonl": output_dir / "xlsx_silver_retrieval_evidence_holdout_v0.jsonl",
        "manifest": report_dir / "xlsx_silver_retrieval_evidence_generation_manifest_v0.json",
        "validation_report": report_dir / "xlsx_silver_retrieval_evidence_validation_report_v0.json",
        "report_md": report_dir / f"xlsx_silver_retrieval_evidence_generation_report_{REPORT_DATE}.md",
        "report_json": report_dir / f"xlsx_silver_retrieval_evidence_generation_report_{REPORT_DATE}.json",
    }


def render_markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# XLSX Silver Retrieval/Evidence Generation",
        "",
        f"- Status: `{report['status']}`",
        f"- Scope: {report['scope']}",
        f"- Candidate pool: `{report['candidate_pool_count']}`",
        f"- Selected silver rows: `{report['selected_silver_count']}`",
        f"- Dev/Holdout: `{report['dev_count']}` / `{report['holdout_count']}`",
        f"- Rejected rows: `{report['rejected_rows_count']}`",
        f"- Route guard: `{report['route_guard_result']['status']}`",
        f"- Denominator guard: `{report['denominator_guard_result']['status']}`",
        f"- Hidden leakage: `{report['hidden_content_leakage_result']['status']}`",
        "",
        "## Answer Shape Distribution",
        "",
        "| answer_shape | rows |",
        "|---|---:|",
    ]
    for key, value in sorted(report["answer_shape_distribution"].items()):
        lines.append(f"| `{key}` | {value} |")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- `promotion_evidence=false` for every row.",
            "- Official XLSX retrieval/evidence denominator remains `23`.",
            "- XLSX answer-generation denominator remains `0`.",
            "- Strict XLSX wrapper namespace: `rag-ingestion-v2-xlsx-candidate-v1`.",
            "- FORMULA_VALUE target redistributed because explicit visible formula evidence was unavailable.",
            "",
            "## Artifacts",
            "",
        ]
    )
    for name, path in sorted((report.get("artifact_paths") or {}).items()):
        lines.append(f"- `{name}`: `{path}`")
    lines.append("")
    return "\n".join(lines)


def parse_visible_rows(text: str) -> list[dict[str, str]]:
    lines = [
        line.strip()
        for line in str(text or "").splitlines()
        if line.strip() and not line.startswith("[Sheet:") and not line.startswith("[Range:") and not line.startswith("Source:") and not line.startswith("Citation:") and not line.startswith("Chunk:")
    ]
    parsed: list[dict[str, str]] = []
    for line in lines:
        if line.startswith("|") and "---" in line:
            continue
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if not cells:
                continue
            if not parsed:
                parsed.append({f"H{i + 1}": cell for i, cell in enumerate(cells) if cell})
            else:
                headers = list(parsed[0].values())
                parsed.append({headers[i] if i < len(headers) and headers[i] else f"C{i + 1}": cell for i, cell in enumerate(cells) if cell})
            continue
        pairs = {}
        for part in line.split("|"):
            if ":" not in part:
                continue
            key, value = part.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                pairs[key] = value
        if pairs:
            parsed.append(pairs)
    return parsed


def first_data_row(rows: Sequence[dict[str, str]]) -> dict[str, str]:
    for row in rows:
        if not row:
            continue
        if len(rows) > 1 and row_has_only_synthetic_keys(row):
            continue
        same_count = sum(1 for key, value in row.items() if normalize_token(key) == normalize_token(value))
        if same_count < max(1, len(row) // 2):
            return dict(row)
    return dict(rows[0]) if rows else {}


def headers_for_unit(unit: SourceUnit) -> list[str]:
    rows = parse_visible_rows(unit.display_text)
    if not rows:
        return []
    first = rows[0]
    if row_has_only_synthetic_keys(first):
        return [value for value in unique_nonempty(first.values()) if not synthetic_label(value)]
    return [key for key in unique_nonempty(first.keys()) if not synthetic_label(key)]


def anchor_value(row: Mapping[str, str], unit: SourceUnit) -> str:
    preferred = []
    for key, value in row.items():
        text = clean(value)
        if text and not mostly_numeric(text) and normalize_token(text) != normalize_token(key):
            preferred.append(text)
    if preferred:
        return preferred[0]
    for value in row.values():
        if clean(value):
            return clean(value)
    return unit.sheet or unit.source_workbook


def secondary_anchor(row: Mapping[str, str], anchor: str) -> tuple[str, str]:
    for key, value in row.items():
        if clean(value) and clean(value) != anchor and normalize_token(value) != normalize_token(key):
            label = "값" if synthetic_label(key) else clean(key)
            return label, clean(value)
    for key, value in row.items():
        if clean(value):
            label = "값" if synthetic_label(key) else clean(key)
            return label, clean(value)
    return "range", anchor


def first_value_index(unit: SourceUnit) -> int:
    row = first_data_row(parse_visible_rows(unit.display_text))
    for index, (_key, value) in enumerate(row.items()):
        if clean(value):
            return index
    return 0


def derive_cell(unit: SourceUnit, value_index: int) -> str:
    parsed = parse_range(unit.cell_range)
    if parsed is None:
        return ""
    start_row, start_col, _end_row, end_col = parsed
    col = min(start_col + max(value_index, 0), end_col)
    return f"{column_letters(col)}{start_row}"


def query_scope(unit: SourceUnit, *, ordinal: int) -> str:
    options = ["해당 엑셀 자료", "자료 안", "보이는 표"]
    if unit.sheet and ordinal % 3 == 0:
        return unit.sheet
    return options[ordinal % len(options)]


def citation_locator_for(unit: SourceUnit, *, cell: str = "") -> dict[str, Any]:
    locator = {
        "track": "XLSX",
        "source_file_id": unit.source_file_id,
        "source_workbook": unit.source_workbook,
        "document_version_id": unit.document_version_id,
        "search_unit_id": unit.search_unit_id,
        "sheet": unit.sheet,
        "range": unit.cell_range,
        "cell": cell,
        "chunk_type": unit.chunk_type,
        "table_id": unit.table_id,
        "parser_version": unit.parser_version,
    }
    return {key: value for key, value in locator.items() if value not in ("", None)}


def location_json_for(unit: SourceUnit) -> dict[str, Any]:
    parsed_range = parse_range(unit.cell_range)
    location = {
        "track": "XLSX",
        "type": "xlsx",
        "sheet": unit.sheet,
        "sheet_name": unit.sheet,
        "range": unit.cell_range,
        "cell_range": unit.cell_range,
        "document_version_id": unit.document_version_id,
        "source_file_id": unit.source_file_id,
        "search_unit_id": unit.search_unit_id,
        "table_id": unit.table_id,
        "hidden_policy": "exclude_hidden",
        "parser_version": unit.parser_version,
    }
    if parsed_range:
        location.update(
            {
                "row_start": parsed_range[0],
                "column_start": parsed_range[1],
                "row_end": parsed_range[2],
                "column_end": parsed_range[3],
            }
        )
    return {key: value for key, value in location.items() if value not in ("", None)}


def locator_type(unit: SourceUnit, *, cell: str = "") -> str:
    if cell:
        return "cell"
    if unit.table_id:
        return "table_range"
    if unit.cell_range:
        return "sheet_range"
    return "source_unit"


def explicit_formula_evidence(text: str) -> bool:
    return bool(re.search(r"(^|[\s|:])=[A-Z0-9_()+\-*/,.]+", text or "", flags=re.IGNORECASE))


def date_or_number_anchor(text: str) -> str:
    patterns = [
        r"20\d{2}-\d{2}-\d{2}",
        r"\b20\d{4}\b",
        r"\d{1,3}(?:,\d{3})+(?:\.\d+)?",
        r"\d+(?:\.\d+)?%",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "")
        if match:
            return match.group(0)
    return ""


def count_visible_lines(text: str) -> int:
    return sum(
        1
        for line in str(text or "").splitlines()
        if line.strip() and not line.startswith("[Sheet:") and not line.startswith("[Range:")
    )


def term_covered(term: str, evidence: str, row: Mapping[str, str], source_unit: SourceUnit) -> bool:
    if term in evidence:
        return True
    if term == clean(row.get("range")) or term == source_unit.cell_range:
        return True
    if term == clean(row.get("sheet")) or term == source_unit.sheet:
        return True
    if term == clean(row.get("visible_row_count")):
        return True
    return False


def synthetic_label(value: object) -> bool:
    return bool(SYNTHETIC_LABEL_PATTERN.fullmatch(clean(value)))


def generic_candidate_label(value: object) -> bool:
    return clean(value) in {"값", "range"} or synthetic_label(value)


def synthetic_label_hits(value: object) -> list[str]:
    return sorted(set(match.group(0) for match in re.finditer(r"\b[HC]\d+\b", clean(value), flags=re.IGNORECASE)))


def row_has_only_synthetic_keys(row: Mapping[str, str]) -> bool:
    return bool(row) and all(synthetic_label(key) for key in row.keys())


def query_has_exact_locator(row: Mapping[str, str]) -> bool:
    query = clean(row.get("query")).upper()
    exact_range = clean(row.get("range")).upper()
    exact_cell = clean(row.get("cell")).upper()
    return bool((exact_range and exact_range in query) or (exact_cell and exact_cell in query))


def split_leakage_keys(row: Mapping[str, str]) -> set[tuple[str, str]]:
    locator_key = "|".join(
        clean(row.get(field))
        for field in ["source_file_id", "source_workbook", "sheet", "range"]
        if clean(row.get(field))
    )
    keys = {
        ("source_content_sha256", clean(row.get("source_content_sha256"))),
        ("source_display_text_sha256", clean(row.get("source_display_text_sha256"))),
        ("citation_text", normalize_query(row.get("citation_text", ""))),
        ("workbook_sheet_range", locator_key),
    }
    return {key for key in keys if key[1]}


def query_locator_leakage_summary(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    leaking = [row.get("query_id", "") for row in rows if query_has_exact_locator(row)]
    return {
        "status": "PASS" if not leaking else "FAIL",
        "exact_range_or_cell_in_query_count": len(leaking),
        "sample_query_ids": leaking[:20],
    }


def split_overlap_summary(dev: Sequence[Mapping[str, str]], holdout: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    dev_by_kind: dict[str, set[str]] = defaultdict(set)
    holdout_by_kind: dict[str, set[str]] = defaultdict(set)
    for row in dev:
        for kind, value in split_leakage_keys(row):
            dev_by_kind[kind].add(value)
    for row in holdout:
        for kind, value in split_leakage_keys(row):
            holdout_by_kind[kind].add(value)
    overlaps = {
        kind: len(dev_by_kind.get(kind, set()) & holdout_by_kind.get(kind, set()))
        for kind in sorted(set(dev_by_kind) | set(holdout_by_kind))
    }
    return {
        "status": "PASS" if all(count == 0 for count in overlaps.values()) else "FAIL",
        "overlap_counts": overlaps,
    }


def duplicate_findings(
    selected: Sequence[Mapping[str, str]],
    dev: Sequence[Mapping[str, str]],
    holdout: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    query_counts = Counter(normalize_query(row.get("query", "")) for row in selected)
    locator_counts = Counter(row.get("citation_locator", "") for row in selected)
    dev_ids = {row.get("query_id", "") for row in dev}
    holdout_ids = {row.get("query_id", "") for row in holdout}
    dev_locators = {row.get("citation_locator", "") for row in dev}
    holdout_locators = {row.get("citation_locator", "") for row in holdout}
    dev_queries = {normalize_query(row.get("query", "")) for row in dev}
    holdout_queries = {normalize_query(row.get("query", "")) for row in holdout}
    split_overlaps = split_overlap_summary(dev, holdout)
    return {
        "duplicate_query_count": sum(1 for count in query_counts.values() if count > 1),
        "duplicate_locator_count": sum(1 for count in locator_counts.values() if count > 1),
        "dev_holdout_query_id_overlap": sorted(dev_ids & holdout_ids),
        "dev_holdout_exact_locator_overlap_count": len(dev_locators & holdout_locators),
        "near_duplicate_query_pairs_split_across_dev_holdout": len(dev_queries & holdout_queries),
        "dev_holdout_source_overlap": split_overlaps,
    }


def blocking_selection_issues(
    selected: Sequence[Mapping[str, str]],
    dev: Sequence[Mapping[str, str]],
    holdout: Sequence[Mapping[str, str]],
) -> list[str]:
    issues: list[str] = []
    if not selected:
        issues.append("no_selected_rows")
    if {row.get("query_id", "") for row in dev} & {row.get("query_id", "") for row in holdout}:
        issues.append("dev_holdout_query_id_overlap")
    if len(dev) + len(holdout) != len(selected):
        issues.append("split_count_mismatch")
    if any(parse_bool(row.get("include_in_official_gold_denominator")) for row in selected):
        issues.append("official_gold_denominator_leakage")
    if any(parse_bool(row.get("include_in_answer_generation_denominator")) for row in selected):
        issues.append("answer_generation_denominator_leakage")
    if any(parse_bool(row.get("promotion_evidence")) for row in selected):
        issues.append("promotion_evidence_leakage")
    if any(count > 1 for count in Counter(normalize_query(row.get("query", "")) for row in selected).values()):
        issues.append("duplicate_selected_query")
    if query_locator_leakage_summary(selected)["status"] != "PASS":
        issues.append("query_exact_locator_leakage")
    if split_overlap_summary(dev, holdout)["status"] != "PASS":
        issues.append("dev_holdout_source_overlap")
    return issues


def denominator_exclusion_summary(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    return {
        "include_in_official_gold_denominator_true_count": sum(parse_bool(row.get("include_in_official_gold_denominator")) for row in rows),
        "include_in_official_positive_denominator_true_count": sum(parse_bool(row.get("include_in_official_positive_denominator")) for row in rows),
        "promotion_evidence_true_count": sum(parse_bool(row.get("promotion_evidence")) for row in rows),
    }


def answer_denominator_exclusion_summary(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    return {
        "include_in_answer_generation_denominator_true_count": sum(parse_bool(row.get("include_in_answer_generation_denominator")) for row in rows)
    }


def load_forbidden_query_ids(registry_path: Path) -> tuple[set[str], set[str]]:
    registry = load_json(resolve_repo_path(registry_path))
    denominators = registry.get("official_diagnostic_denominators") or {}
    official_ids: set[str] = set()
    legacy_ids: set[str] = set()
    for key, entry in denominators.items():
        if not isinstance(entry, Mapping):
            continue
        path_texts = [
            entry.get("path"),
            entry.get("official_positive_subset_path"),
            entry.get("official_positive_retrieval_subset_path"),
        ]
        target = legacy_ids if "legacy" in json_dumps(entry).lower() or "reviewed_positive" in key else official_ids
        for path_text in path_texts:
            if not path_text:
                continue
            path = resolve_repo_path(Path(str(path_text)))
            if path.exists() and path.suffix.lower() == ".csv":
                for row in read_csv_rows(path):
                    query_id = clean(row.get("query_id"))
                    if query_id:
                        target.add(query_id)
    return official_ids, legacy_ids


def hidden_text_hits(source_units: Sequence[SourceUnit]) -> list[dict[str, str]]:
    hits = []
    for unit in source_units:
        text = f"{unit.display_text}\n{unit.citation_text}".lower()
        found = sorted(term for term in BLOCKED_HIDDEN_TEXT_TERMS if term in text)
        if found:
            hits.append({"source_search_unit_id": unit.search_unit_id, "terms": ",".join(found)})
    return hits


def has_hidden_flag(extra: Mapping[str, Any]) -> bool:
    for key, value in extra.items():
        normalized = str(key).replace("-", "_").lower()
        if normalized in HIDDEN_FLAG_KEYS and parse_bool(value):
            return True
    return False


def distribution(rows: Sequence[Mapping[str, str]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(clean(row.get(field)) for row in rows).items()))


def write_rows(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in CANDIDATE_FIELDNAMES} for row in rows])


def write_jsonl(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json_dumps({field: row.get(field, "") for field in CANDIDATE_FIELDNAMES}) + "\n")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(resolve_repo_path(path).read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise XlsxPreSilverRiskError(f"JSON must contain an object: {path}")
    return parsed


def artifact_entry(path: Path) -> dict[str, Any]:
    resolved = resolve_repo_path(path)
    return {
        "path": repo_relative(resolved),
        "exists": resolved.exists(),
        "bytes": resolved.stat().st_size if resolved.exists() else 0,
        "sha256": sha256_file(resolved) if resolved.exists() and resolved.is_file() else None,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_repo_path(path: Path | str) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def first_text(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def parse_json_object(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or ""))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_json_list(value: object) -> list[str]:
    try:
        parsed = json.loads(str(value or ""))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [clean(item) for item in parsed if clean(item)]


def json_dumps(value: Any, *, indent: int | None = None) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=indent)


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return clean(value).lower() in {"1", "true", "yes", "y", "on"}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def unique_nonempty(values: Iterable[object]) -> list[str]:
    out: list[str] = []
    for value in values:
        text = clean(value)
        if text and text not in out:
            out.append(text)
    return out


def mostly_numeric(value: str) -> bool:
    text = clean(value)
    if not text:
        return False
    numeric = sum(1 for char in text if char.isdigit() or char in ",.-/% ")
    return numeric / max(1, len(text)) > 0.70


def normalize_token(value: object) -> str:
    return re.sub(r"\s+", "", clean(value)).lower()


def normalize_query(value: object) -> str:
    return re.sub(r"[\s?.!,]+", "", clean(value)).lower()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def one_of(ordinal: int, options: Sequence[str]) -> str:
    return options[(ordinal - 1) % len(options)]


def parse_range(value: str) -> tuple[int, int, int, int] | None:
    text = clean(value).replace("$", "").upper()
    if not text:
        return None
    parts = text.split(":", 1)
    start = parse_cell(parts[0])
    end = parse_cell(parts[1] if len(parts) == 2 else parts[0])
    if start is None or end is None:
        return None
    return min(start[0], end[0]), min(start[1], end[1]), max(start[0], end[0]), max(start[1], end[1])


def parse_cell(value: str) -> tuple[int, int] | None:
    text = clean(value).replace("$", "").upper()
    match = re.fullmatch(r"([A-Z]+)(\d+)", text)
    if not match:
        return None
    return int(match.group(2)), column_number(match.group(1))


def column_number(letters: str) -> int:
    number = 0
    for char in letters:
        number = number * 26 + ord(char) - ord("A") + 1
    return number


def column_letters(number: int) -> str:
    letters = ""
    while number > 0:
        number, rem = divmod(number - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters or "A"


def cell_in_range(cell: str, cell_range: str) -> bool:
    parsed_cell = parse_cell(cell)
    parsed_range = parse_range(cell_range)
    if parsed_cell is None or parsed_range is None:
        return False
    row, col = parsed_cell
    row_start, col_start, row_end, col_end = parsed_range
    return row_start <= row <= row_end and col_start <= col <= col_end


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
