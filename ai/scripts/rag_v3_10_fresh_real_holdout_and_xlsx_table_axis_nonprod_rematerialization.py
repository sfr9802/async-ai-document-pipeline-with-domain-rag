from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v3_9_2_overfit_risk_audit_and_blind_holdout_reset as v392


RUN_ID = "official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization"
V3_8_2_RUN_ID = v392.V3_8_2_RUN_ID
V3_8_3_RUN_ID = v392.V3_8_3_RUN_ID
V3_9_RUN_ID = v392.V3_9_RUN_ID
V3_9_1_RUN_ID = v392.V3_9_1_RUN_ID
V3_9_2_RUN_ID = v392.RUN_ID

ROOT = v392.ROOT
REPORT_DIR = v392.REPORT_DIR
SOURCE_REGISTRY_JSONL = v392.SOURCE_REGISTRY_JSONL
STATUS_JSONL = v392.STATUS_JSONL
PROGRESS_DOC = v392.PROGRESS_DOC
MEASUREMENTS_DOC = v392.MEASUREMENTS_DOC
TRIAGE_DOC = v392.TRIAGE_DOC

ALLOWED_NAMESPACE = "rag-data-xlsx-table-axis-ood-nonprod-v1"
BLOCKED_NAMESPACES = (
    "rag-data-official-denominator-v1",
    "rag-data-all-source-citable-nonprod-v1",
    "production",
)

REQUIRED_SOURCEATOM_TABLE_AXIS_FIELDS = (
    "table_block_id",
    "table_range",
    "header_rows",
    "header_columns",
    "merged_cell_header_propagation",
    "parent_header_path_sha256",
    "row_label_aliases_sha256",
    "column_label_aliases_sha256",
    "unit_date_number_normalized_tokens",
    "sparse_table_boundary",
)
REQUIRED_SEARCHUNIT_TABLE_AXIS_FIELDS = (
    "table_block_id",
    "table_axis_embedding_text",
    "table_axis_bm25_text",
    "header_path_hashes",
    "row_column_alias_hashes",
    "table_shape_summary",
    "table_axis_debug_text",
)
FORBIDDEN_TABLE_AXIS_FIELDS = (
    "expected_answer",
    "supporting_evidence",
    "gold_label",
    "qrels",
    "pass_fail",
    "raw_answer_value_for_query_scoring",
)
USER_OWNED_FIELDS = (
    "query_approval",
    "relevance",
    "answerability",
    "expected_answer",
    "supporting_evidence",
    "pass_fail",
    "denominator_eligibility",
)
QUERY_STYLES = (
    "terse_question",
    "messy_user_like",
    "short_fragment",
    "implicit_context",
    "no_source_title",
    "colloquial_korean",
)
EXCLUDED_FIDELITY_BUCKETS = (
    "answer_value_in_query",
    "index_to_content",
    "source_title_leak",
    "file_title_leak",
    "exact_query_hack",
    "major_topic_drift",
    "unnatural_sheet_or_cell_reference",
)

OUTPUTS = {
    "summary_json": REPORT_DIR / f"{RUN_ID}_summary.json",
    "metrics_json": REPORT_DIR / f"{RUN_ID}_metrics.json",
    "fresh_real_holdout_manifest_json": REPORT_DIR / f"{RUN_ID}_fresh_real_holdout_manifest.json",
    "seen_surface_manifest_json": REPORT_DIR / f"{RUN_ID}_seen_surface_manifest.json",
    "query_fidelity_audit_jsonl": REPORT_DIR / f"{RUN_ID}_query_fidelity_audit.jsonl",
    "leakage_audit_jsonl": REPORT_DIR / f"{RUN_ID}_leakage_audit.jsonl",
    "xlsx_nonprod_sourceatom_manifest_jsonl": REPORT_DIR / f"{RUN_ID}_xlsx_nonprod_sourceatom_manifest.jsonl",
    "xlsx_nonprod_searchunit_manifest_jsonl": REPORT_DIR / f"{RUN_ID}_xlsx_nonprod_searchunit_manifest.jsonl",
    "xlsx_nonprod_index_build_summary_json": REPORT_DIR / f"{RUN_ID}_xlsx_nonprod_index_build_summary.json",
    "xlsx_table_axis_eval_per_query_jsonl": REPORT_DIR / f"{RUN_ID}_xlsx_table_axis_eval_per_query.jsonl",
    "failure_taxonomy_json": REPORT_DIR / f"{RUN_ID}_failure_taxonomy.json",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="microseconds") + "Z"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_values(values: Sequence[str]) -> list[str]:
    return sorted({sha256_text(value.strip()) for value in values if value and value.strip()})


def repo_relative(path: Path) -> str:
    return v392.repo_relative(path)


def read_json(path: Path) -> dict[str, Any]:
    return v392.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v392.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v392.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v392.write_jsonl(path, rows)


def sha256_file(path: Path) -> str:
    return v392.sha256_file(path)


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def normalize_pathish(value: str) -> str:
    return value.replace("\\", "/").replace("//", "/").strip().lower()


def col_to_num(column: str) -> int:
    total = 0
    for char in column.upper():
        if not ("A" <= char <= "Z"):
            continue
        total = total * 26 + (ord(char) - ord("A") + 1)
    return total


def parse_range(value: str) -> dict[str, int | str]:
    match = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", (value or "").upper())
    if not match:
        return {
            "start_column": 1,
            "end_column": 1,
            "start_row": 1,
            "end_row": 1,
            "parse_status": "unparsed",
        }
    start_col, start_row, end_col, end_row = match.groups()
    return {
        "start_column": col_to_num(start_col),
        "end_column": col_to_num(end_col),
        "start_row": int(start_row),
        "end_row": int(end_row),
        "parse_status": "parsed",
    }


def range_shape(value: str) -> dict[str, Any]:
    parsed = parse_range(value)
    row_count = max(1, int(parsed["end_row"]) - int(parsed["start_row"]) + 1)
    column_count = max(1, int(parsed["end_column"]) - int(parsed["start_column"]) + 1)
    return {
        "row_count": row_count,
        "column_count": column_count,
        "blank_density": None,
        "boundary_inferred_from_range": parsed["parse_status"] == "parsed",
    }


def aliases_from_text(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"\s*\|\s*|,|/|>|=", value)
    aliases = [part.strip() for part in parts if part and part.strip()]
    if value.strip():
        aliases.append(value.strip())
    return sorted(set(aliases))


def normalized_locator_tokens(*values: str) -> list[str]:
    text = " ".join(value for value in values if value)
    tokens = re.findall(r"\d{4,8}|\d+(?:\.\d+)?|%|원|명|건|개|년|월|일", text)
    return sorted(set(tokens))[:16]


def raw_locator(row: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = as_mapping(row.get("raw_locator"))
    if raw:
        return raw
    return as_mapping(row.get("canonical_citation_payload"))


def row_source_family(row: Mapping[str, Any]) -> str:
    canonical = as_mapping(row.get("canonical_citation_payload"))
    return str(row.get("source_family") or canonical.get("source_family") or canonical.get("sourceFamily") or "")


def local_file_inventory() -> dict[str, Any]:
    excluded_fragments = ("/.git/", "/node_modules/", "/.venv/", "/venv/", "/__pycache__/")
    rows: list[dict[str, Any]] = []
    for suffix in ("*.pdf", "*.xlsx"):
        for path in ROOT.rglob(suffix):
            rel = repo_relative(path)
            norm = "/" + normalize_pathish(rel)
            if any(fragment in norm for fragment in excluded_fragments):
                continue
            rows.append(
                {
                    "path": rel,
                    "suffix": path.suffix.lower(),
                    "filename": path.name,
                    "size_bytes": path.stat().st_size,
                }
            )
    return {
        "scanned_suffixes": [".pdf", ".xlsx"],
        "file_count": len(rows),
        "files": sorted(rows, key=lambda item: item["path"]),
    }


def load_registry_inventory() -> dict[str, Any]:
    registry_counts: Counter[str] = Counter()
    pdf_documents: dict[str, dict[str, Any]] = {}
    xlsx_workbooks: dict[str, dict[str, Any]] = {}
    xlsx_rows: list[dict[str, Any]] = []
    source_identity_hashes: set[str] = set()
    source_atom_ids: set[str] = set()
    pdf_paths: set[str] = set()
    pdf_filenames: set[str] = set()

    with SOURCE_REGISTRY_JSONL.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            family = row_source_family(row)
            if family not in {"PDF", "XLSX"}:
                continue
            registry_counts[f"{family}_source_atoms"] += 1
            source_identity = str(row.get("source_identity") or "")
            if source_identity:
                source_identity_hashes.add(sha256_text(source_identity))
            source_atom_id = str(row.get("source_atom_id") or "")
            if source_atom_id:
                source_atom_ids.add(source_atom_id)
            locator = raw_locator(row)

            if family == "PDF":
                source_path = str(
                    locator.get("source_pdf_path")
                    or as_mapping(row.get("canonical_citation_payload")).get("source_pdf_path")
                    or ""
                )
                source_path_norm = normalize_pathish(source_path)
                filename = Path(source_path_norm).name if source_path_norm else str(locator.get("source_pdf_filename") or "")
                doc_id = str(
                    row.get("document_version_id")
                    or locator.get("document_version_id")
                    or row.get("document_id")
                    or source_path_norm
                )
                if source_path_norm:
                    pdf_paths.add(source_path_norm)
                if filename:
                    pdf_filenames.add(filename.lower())
                if doc_id and doc_id not in pdf_documents:
                    pdf_documents[doc_id] = {
                        "document_version_id": doc_id,
                        "source_pdf_path": source_path_norm,
                        "source_pdf_filename": filename,
                    }
            elif family == "XLSX":
                workbook = str(
                    row.get("workbook_id")
                    or locator.get("workbook")
                    or as_mapping(row.get("canonical_citation_payload")).get("workbook")
                    or ""
                )
                workbook_version = str(row.get("workbook_version_id") or locator.get("document_version_id") or "")
                if workbook and workbook not in xlsx_workbooks:
                    xlsx_workbooks[workbook] = {
                        "workbook": workbook,
                        "workbook_version_id": workbook_version,
                    }
                xlsx_rows.append(row)

    registry_counts["PDF_source_documents"] = len(pdf_documents)
    registry_counts["XLSX_workbooks"] = len(xlsx_workbooks)
    return {
        "registry_counts": dict(sorted(registry_counts.items())),
        "pdf_documents": pdf_documents,
        "xlsx_workbooks": xlsx_workbooks,
        "xlsx_rows": xlsx_rows,
        "source_identity_hashes": source_identity_hashes,
        "source_atom_ids": source_atom_ids,
        "pdf_paths": pdf_paths,
        "pdf_filenames": pdf_filenames,
    }


def classify_local_files(local_files: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    seen_pdf_paths = set(registry["pdf_paths"])
    seen_pdf_filenames = set(registry["pdf_filenames"])
    seen_xlsx_workbooks = {name.lower() for name in registry["xlsx_workbooks"]}
    ignored_assets: list[dict[str, Any]] = []
    seen_local_files: list[dict[str, Any]] = []
    unseen_pdf_candidates: list[dict[str, Any]] = []
    unseen_xlsx_candidates: list[dict[str, Any]] = []

    for item in local_files["files"]:
        rel = item["path"]
        norm = normalize_pathish(rel)
        filename = item["filename"].lower()
        if norm.startswith("ai/scripts/assets/"):
            ignored_assets.append({**item, "reason": "script_demo_asset_not_holdout_eligible"})
            continue
        if item["suffix"] == ".pdf":
            is_seen = norm in seen_pdf_paths or filename in seen_pdf_filenames
            if is_seen:
                seen_local_files.append({**item, "seen_reason": "path_or_filename_in_source_registry"})
            else:
                unseen_pdf_candidates.append(
                    {
                        **item,
                        "source_document_disjoint_from_seen": True,
                        "document_sha256": sha256_file(ROOT / rel),
                    }
                )
        elif item["suffix"] == ".xlsx":
            is_seen = filename in seen_xlsx_workbooks
            if is_seen:
                seen_local_files.append({**item, "seen_reason": "workbook_in_source_registry"})
            else:
                unseen_xlsx_candidates.append(
                    {
                        **item,
                        "workbook_disjoint_from_seen": True,
                        "workbook_sha256": sha256_file(ROOT / rel),
                    }
                )

    return {
        "scanned_file_count": local_files["file_count"],
        "seen_local_files": seen_local_files,
        "ignored_non_holdout_assets": ignored_assets,
        "unseen_pdf_source_document_candidates": unseen_pdf_candidates,
        "unseen_xlsx_workbook_candidates": unseen_xlsx_candidates,
        "candidate_file_paths_outside_registry": [
            item["path"] for item in unseen_pdf_candidates + unseen_xlsx_candidates
        ],
    }


def candidate_base(
    *,
    query_id: str,
    source_family: str,
    query_style: str,
    query_text: str,
    fixture_category: str,
    synthetic: bool,
    real_unseen: bool,
) -> dict[str, Any]:
    row = {
        "query_id": query_id,
        "source_family": source_family,
        "query_style": query_style,
        "query_text": query_text,
        "query_text_sha256": sha256_text(query_text),
        "fixture_category": fixture_category,
        "synthetic": synthetic,
        "real_unseen": real_unseen,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "diagnostic_only": True,
        "direct_normalized_value_query_matching_used": False,
        "source_title_or_file_title_used_as_success_evidence": False,
        "answer_value_used_as_success_evidence": False,
        "index_to_content_used_as_success_evidence": False,
    }
    row.update({field: "" for field in USER_OWNED_FIELDS})
    return row


def synthetic_query_text(source_family: str, style: str, topic: str) -> str:
    if source_family == "XLSX":
        templates = {
            "terse_question": f"{topic}에서 비교 기준이 뭐야?",
            "messy_user_like": f"이 표에서 {topic} 관련해서 차이 나는 부분 좀 찾아줘",
            "short_fragment": f"{topic} 비교",
            "implicit_context": f"앞뒤 항목을 같이 보면 {topic} 흐름이 어떻게 돼?",
            "no_source_title": f"표 안의 {topic} 기준으로 묶어서 봐줘",
            "colloquial_korean": f"{topic} 쪽은 뭐가 튀어?",
        }
    else:
        templates = {
            "terse_question": f"{topic}의 핵심 조건은?",
            "messy_user_like": f"문서에서 {topic} 얘기하는 부분 대충 정리해줘",
            "short_fragment": f"{topic} 요지",
            "implicit_context": f"해당 절의 앞뒤 문맥상 {topic}이 어떻게 설명돼?",
            "no_source_title": f"본문 기준으로 {topic} 관련 내용을 찾아줘",
            "colloquial_korean": f"{topic} 부분은 무슨 말이야?",
        }
    return templates[style]


def build_query_candidates(local_scan: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    pdf_real = list(local_scan["unseen_pdf_source_document_candidates"])
    xlsx_real = list(local_scan["unseen_xlsx_workbook_candidates"])
    for family, real_rows in (("PDF", pdf_real), ("XLSX", xlsx_real)):
        for source_index, _source in enumerate(real_rows[:20]):
            for style in QUERY_STYLES:
                query = synthetic_query_text(family, style, "핵심 항목")
                candidates.append(
                    candidate_base(
                        query_id=f"v3_10_real_{family.lower()}_{source_index:03d}_{style}",
                        source_family=family,
                        query_style=style,
                        query_text=query,
                        fixture_category="local_real_unseen_candidate",
                        synthetic=False,
                        real_unseen=True,
                    )
                )

    xlsx_categories = (
        "single_sheet_simple_table",
        "multi_sheet_workbook",
        "merged_header_workbook",
        "sparse_table",
        "long_table",
        "multi_row_header",
        "date_number_unit_heavy_table",
        "korean_public_data_style_sheet",
    )
    pdf_categories = (
        "native_text_policy_doc",
        "form_like_pdf",
        "table_like_pdf",
        "heading_body_heavy_pdf",
        "dot_leader_artifact_pdf",
        "multi_page_section_pdf",
    )
    xlsx_topics = (
        "기관별 현황",
        "월별 추이",
        "지역별 분포",
        "항목별 합계",
        "기간별 증감",
        "분류별 기준",
        "단위가 섞인 수치",
        "빈칸이 많은 구간",
        "머리글 아래 세부 항목",
        "여러 시트의 공통 기준",
    )
    pdf_topics = (
        "정책 목적",
        "적용 대상",
        "제출 절차",
        "표 안의 기준",
        "본문 근거",
        "장별 요약",
        "점선 목차 주변 항목",
        "양식 입력 조건",
        "다음 단계",
        "예외 조항",
    )
    for family, categories, topics in (
        ("XLSX", xlsx_categories, xlsx_topics),
        ("PDF", pdf_categories, pdf_topics),
    ):
        for index in range(100):
            style = QUERY_STYLES[index % len(QUERY_STYLES)]
            topic = topics[index % len(topics)]
            category = categories[index % len(categories)]
            candidates.append(
                candidate_base(
                    query_id=f"v3_10_synthetic_ood_{family.lower()}_{index:03d}",
                    source_family=family,
                    query_style=style,
                    query_text=synthetic_query_text(family, style, topic),
                    fixture_category=category,
                    synthetic=True,
                    real_unseen=False,
                )
            )
    return candidates


def classify_query_fidelity(candidate: Mapping[str, Any]) -> dict[str, Any]:
    query = str(candidate.get("query_text") or "")
    lower = query.lower()
    flags = {
        "answer_value_in_query": False,
        "index_to_content": bool(re.search(r"\b(sourceatom|searchunit|faiss|jsonl|bbox|chunk|index)\b", lower)),
        "source_title_leak": False,
        "file_title_leak": bool(re.search(r"\.(pdf|xlsx)\b", lower)),
        "exact_query_hack": False,
        "major_topic_drift": False,
        "unnatural_sheet_or_cell_reference": bool(
            re.search(r"\b[A-Z]{1,3}\d{1,7}\b|sheet\s*\d+|시트\s*\d+", query)
        ),
    }
    excluded = [bucket for bucket, flag in flags.items() if flag]
    row = {
        "schema_version": f"{RUN_ID}_query_fidelity_audit_v1",
        "run_id": RUN_ID,
        "query_id": candidate["query_id"],
        "source_family": candidate["source_family"],
        "query_style": candidate["query_style"],
        "query_text_sha256": candidate["query_text_sha256"],
        "query_fidelity_bucket": excluded[0] if excluded else "included",
        "query_fidelity_exclusion_reason": excluded[0] if excluded else "",
        "query_fidelity_headline_included": not excluded,
        "official_metric_input": False,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "synthetic": candidate["synthetic"],
        "real_unseen": candidate["real_unseen"],
        **flags,
    }
    row.update({field: "" for field in USER_OWNED_FIELDS})
    return row


def build_query_fidelity_audit(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [classify_query_fidelity(candidate) for candidate in candidates]


def build_leakage_audit() -> list[dict[str, Any]]:
    probes = {
        "answer_value_in_query": "정답값 12345가 맞는지 찾아줘",
        "index_to_content": "sourceatom jsonl 행의 bbox 값을 그대로 보여줘",
        "source_title_leak": "기관_정책_보고서 제목 파일에서 핵심을 찾아줘",
        "file_title_leak": "sample_report.pdf 안의 답을 알려줘",
        "exact_query_hack": "seed query 그대로",
        "major_topic_drift": "축구 경기 결과와 선수 이적",
        "unnatural_sheet_or_cell_reference": "A12 셀하고 Sheet1 값을 비교해줘",
    }
    rows: list[dict[str, Any]] = []
    for index, (bucket, query) in enumerate(probes.items(), start=1):
        rows.append(
            {
                "schema_version": f"{RUN_ID}_leakage_audit_v1",
                "run_id": RUN_ID,
                "probe_id": f"v3_10_leakage_probe_{index:02d}",
                "bucket": bucket,
                "query_text_sha256": sha256_text(query),
                "query_fidelity_headline_included": False,
                "success_evidence_allowed": False,
                "official_metric_input_rows": 0,
                "diagnostic_only": True,
                "direct_normalized_value_query_matching_used": False,
                "excluded_from_headline": True,
            }
        )
    return rows


def materialize_sourceatom(row: Mapping[str, Any]) -> dict[str, Any]:
    locator = raw_locator(row)
    source_atom_id = str(row.get("source_atom_id") or "")
    source_identity = str(row.get("source_identity") or "")
    workbook = str(row.get("workbook_id") or locator.get("workbook") or "")
    sheet = str(locator.get("sheet") or as_mapping(row.get("canonical_citation_payload")).get("sheet") or "")
    table_range = str(locator.get("range") or as_mapping(row.get("canonical_citation_payload")).get("range") or "")
    cell = str(locator.get("cell") or as_mapping(row.get("canonical_citation_payload")).get("cell") or "")
    row_label = str(locator.get("row_label") or as_mapping(row.get("canonical_citation_payload")).get("row_label") or "")
    column_label = str(locator.get("column_label") or locator.get("target_column") or "")
    target_column = str(locator.get("target_column") or column_label)
    parsed = parse_range(table_range)
    target_col_num = col_to_num(re.match(r"([A-Z]+)", cell or "A").group(1)) if re.match(r"([A-Z]+)", cell or "") else 1
    header_rows = [{"row": parsed["start_row"], "inferred": True}]
    header_columns = []
    if target_col_num > int(parsed["start_column"]):
        header_columns.append(
            {
                "start_column": int(parsed["start_column"]),
                "end_column": target_col_num - 1,
                "inferred": True,
            }
        )
    row_aliases = aliases_from_text(row_label)
    column_aliases = aliases_from_text(" | ".join(value for value in (column_label, target_column) if value))
    parent_hashes = hash_values([f"{sheet}|{table_range}|{target_column}", f"{table_range}|{target_column}"])
    row_hashes = hash_values(row_aliases)
    column_hashes = hash_values(column_aliases)
    table_block_id = "tblaxis_" + sha256_text(f"{workbook}|{sheet}|{table_range}")[:24]
    unit_tokens = normalized_locator_tokens(row_label, column_label, target_column, table_range)
    return {
        "schema_version": f"{RUN_ID}_xlsx_nonprod_sourceatom_manifest_v1",
        "run_id": RUN_ID,
        "index_namespace": ALLOWED_NAMESPACE,
        "source_family": "XLSX",
        "source_registry_version": str(row.get("source_registry_version") or "source-registry-v1"),
        "source_atom_id": "srcatom_v3_10_xlsx_axis_" + sha256_text(source_atom_id or source_identity)[:24],
        "source_atom_id_original": source_atom_id,
        "source_identity_sha256": sha256_text(source_identity),
        "workbook_id_sha256": sha256_text(workbook),
        "sheet_name_sha256": sha256_text(sheet),
        "cell": cell,
        "materialized_in_nonprod_sourceatom": True,
        "overlay_only": False,
        "table_block_id": table_block_id,
        "table_range": table_range,
        "header_rows": header_rows,
        "header_columns": header_columns,
        "merged_cell_header_propagation": {
            "present": False,
            "propagated_header_count": 0,
            "source": "not_available_in_current_registry",
        },
        "parent_header_path_sha256": parent_hashes,
        "row_label_aliases_sha256": row_hashes,
        "column_label_aliases_sha256": column_hashes,
        "unit_date_number_normalized_tokens": unit_tokens,
        "sparse_table_boundary": range_shape(table_range),
        "raw_answer_value_for_query_scoring_used": False,
        "normalized_value_excluded_from_query_scoring": True,
        "expected_supporting_gold_text_used": False,
        "forbidden_fields_absent": True,
    }


def materialize_searchunit(row: Mapping[str, Any]) -> dict[str, Any]:
    row_column_hashes = sorted(set(row["row_label_aliases_sha256"] + row["column_label_aliases_sha256"]))
    shape = row["sparse_table_boundary"]
    embedding_text = (
        f"namespace={ALLOWED_NAMESPACE} family=XLSX table_block_id={row['table_block_id']} "
        f"table_range={row['table_range']} rows={shape['row_count']} columns={shape['column_count']} "
        f"header_path_hashes={' '.join(row['parent_header_path_sha256'])} "
        f"row_column_alias_hashes={' '.join(row_column_hashes)} "
        f"unit_date_number_tokens={' '.join(row['unit_date_number_normalized_tokens'])}"
    )
    bm25_text = (
        f"table_block {row['table_block_id']} range {row['table_range']} "
        f"shape rows {shape['row_count']} columns {shape['column_count']} "
        f"axis_hash {' '.join(row_column_hashes)}"
    )
    return {
        "schema_version": f"{RUN_ID}_xlsx_nonprod_searchunit_manifest_v1",
        "run_id": RUN_ID,
        "index_namespace": ALLOWED_NAMESPACE,
        "search_unit_id": "su_v3_10_xlsx_axis_" + sha256_text(row["source_atom_id"])[:24],
        "source_atom_id": row["source_atom_id"],
        "source_atom_id_original": row["source_atom_id_original"],
        "source_identity_sha256": row["source_identity_sha256"],
        "source_family": "XLSX",
        "materialized_in_nonprod_searchunit": True,
        "table_block_id": row["table_block_id"],
        "table_axis_embedding_text": embedding_text,
        "table_axis_bm25_text": bm25_text,
        "header_path_hashes": row["parent_header_path_sha256"],
        "row_column_alias_hashes": row_column_hashes,
        "table_shape_summary": shape,
        "table_axis_debug_text": (
            f"redacted workbook_hash={row['workbook_id_sha256']} sheet_hash={row['sheet_name_sha256']} "
            f"row_alias_count={len(row['row_label_aliases_sha256'])} "
            f"column_alias_count={len(row['column_label_aliases_sha256'])} raw_answer_value_excluded=true"
        ),
        "direct_normalized_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "expected_supporting_gold_text_used": False,
        "forbidden_fields_absent": True,
    }


def materialize_xlsx_nonprod_rows(xlsx_rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sourceatoms = [materialize_sourceatom(row) for row in xlsx_rows]
    searchunits = [materialize_searchunit(row) for row in sourceatoms]
    sourceatoms.sort(key=lambda row: row["source_atom_id"])
    searchunits.sort(key=lambda row: row["search_unit_id"])
    return sourceatoms, searchunits


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": (numerator / denominator) if denominator else None,
    }


def bool_metric(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, Any]:
    return ratio(sum(1 for row in rows if row.get(key) is True), len(rows))


def xlsx_query_fidelity_counts() -> dict[str, int]:
    rows = [row for row in read_jsonl(v392.V3_9_1_QUERY_FIDELITY) if row.get("source_family") == "XLSX"]
    return {
        "included": sum(1 for row in rows if row.get("query_fidelity_headline_included") is True),
        "excluded": sum(1 for row in rows if row.get("query_fidelity_headline_included") is not True),
        "rows": len(rows),
    }


def build_xlsx_eval(
    sourceatom_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    per_query = [row for row in read_jsonl(v392.V3_9_1_PER_QUERY) if row.get("source_family") == "XLSX"]
    materialized = {row["source_atom_id_original"]: row for row in sourceatom_rows}
    eval_rows: list[dict[str, Any]] = []
    rank1_old_empty = 0
    rank1_new_empty = 0
    rank1_denominator = 0
    for row in per_query:
        candidates = list(row.get("scoped_cell_candidates") or [])
        rank1 = candidates[0] if candidates else {}
        rank1_denominator += 1 if rank1 else 0
        old_signal_count = int(row.get("locator_signal_count_rank1") or 0)
        if rank1 and old_signal_count == 0:
            rank1_old_empty += 1
        materialized_row = materialized.get(str(rank1.get("source_atom_id") or ""))
        new_signal_count = 0
        if materialized_row:
            new_signal_count += 1 if materialized_row.get("table_block_id") else 0
            new_signal_count += 1 if materialized_row.get("parent_header_path_sha256") else 0
            new_signal_count += 1 if materialized_row.get("row_label_aliases_sha256") else 0
            new_signal_count += 1 if materialized_row.get("column_label_aliases_sha256") else 0
            new_signal_count += 1 if materialized_row.get("unit_date_number_normalized_tokens") else 0
        if rank1 and new_signal_count == 0:
            rank1_new_empty += 1
        eval_rows.append(
            {
                "schema_version": f"{RUN_ID}_xlsx_table_axis_eval_per_query_v1",
                "run_id": RUN_ID,
                "query_id": row.get("query_id"),
                "query_scope": row.get("query_scope"),
                "source_family": "XLSX",
                "old_seen_reference_only": True,
                "fresh_real_holdout": False,
                "success_claim_allowed": False,
                "candidate_generation_mode": "table_block_axis_pair_row_slice_cell_candidate_manifest",
                "rank1_source_atom_id_original": rank1.get("source_atom_id", ""),
                "materialized_rank1_sourceatom_found": bool(materialized_row),
                "v3_9_1_locator_signal_count_rank1": old_signal_count,
                "v3_10_materialized_axis_signal_count_rank1": new_signal_count,
                "v3_9_1_signal_empty_rank1": bool(rank1 and old_signal_count == 0),
                "v3_10_signal_empty_rank1": bool(rank1 and new_signal_count == 0),
                "sheet@1": row.get("sheet_resolve@1") is True,
                "sheet@3": row.get("sheet_resolve@3") is True,
                "table_or_range@1": row.get("table_or_range_resolve@1") is True,
                "table_or_range@3": row.get("table_or_range_resolve@3") is True,
                "cell_or_value@1": row.get("cell_or_value_resolve@1") is True,
                "cell_or_value@3": row.get("cell_or_value_resolve@3") is True,
                "direct_normalized_value_query_matching_used": False,
                "official_metric_input_rows": 0,
            }
        )

    old_reference = {
        "success_claim_allowed": False,
        "denominator_role": "seen_validation_only_reference_no_regression",
        "row_count": len(per_query),
        "sheet@1": bool_metric(per_query, "sheet_resolve@1"),
        "sheet@3": bool_metric(per_query, "sheet_resolve@3"),
        "table_or_range@1": bool_metric(per_query, "table_or_range_resolve@1"),
        "table_or_range@3": bool_metric(per_query, "table_or_range_resolve@3"),
        "cell_or_value@1": bool_metric(per_query, "cell_or_value_resolve@1"),
        "cell_or_value@3": bool_metric(per_query, "cell_or_value_resolve@3"),
        "wrong_workbook_block_rate": bool_metric(per_query, "wrong_workbook_block_rate"),
        "abstain_rate": bool_metric(per_query, "abstain_rate"),
        "table_or_range_miss_after_sheet_hit": sum(
            1
            for row in per_query
            if as_mapping(row.get("xlsx_miss_taxonomy")).get("primary_category")
            == "table_or_range_miss_after_sheet_hit"
        ),
        "signal_empty_rank1_rate": ratio(rank1_old_empty, rank1_denominator),
        "query_fidelity": xlsx_query_fidelity_counts(),
    }
    nonprod = {
        **old_reference,
        "success_claim_allowed": False,
        "denominator_role": "seen_validation_only_materialization_smoke_not_success",
        "signal_empty_rank1_rate": ratio(rank1_new_empty, rank1_denominator),
        "materialized_rank1_signal_delta": rank1_old_empty - rank1_new_empty,
        "table_range_cell_metrics_changed_by_manifest_only": False,
    }
    fresh = {
        "success_claim_allowed": False,
        "row_count": 0,
        "sheet@1": ratio(0, 0),
        "sheet@3": ratio(0, 0),
        "table_or_range@1": ratio(0, 0),
        "table_or_range@3": ratio(0, 0),
        "cell_or_value@1": ratio(0, 0),
        "cell_or_value@3": ratio(0, 0),
        "signal_empty_rank1_rate": ratio(0, 0),
        "query_fidelity": {"included": 0, "excluded": 0, "rows": 0},
        "blocked_reason": "fresh real XLSX workbook-disjoint holdout unavailable",
    }
    return {
        "old_seen_reference": old_reference,
        "nonprod_seen_materialization_smoke": nonprod,
        "fresh_real_holdout": fresh,
    }, eval_rows


def pdf_file_identity_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "file_resolve@1": bool_metric(rows, "file_resolve@1"),
        "file_resolve@3": bool_metric(rows, "file_resolve@3"),
        "wrong_file_block_rate": bool_metric(rows, "wrong_file_block_rate"),
        "abstain_rate": bool_metric(rows, "abstain_rate"),
    }


def build_pdf_baseline() -> dict[str, Any]:
    v382_pdf = [row for row in read_jsonl(v392.V3_8_2_PER_QUERY) if row.get("source_family") == "PDF"]
    v391_pdf = [row for row in read_jsonl(v392.V3_9_1_PER_QUERY) if row.get("source_family") == "PDF"]
    return {
        "metric_scope": "file_identity_only",
        "answer_ready_evidence_window_metric_computed": False,
        "ocr_touched": False,
        "old_seen_reference_only": True,
        "fresh_real_holdout": {
            "measurable_rows": 0,
            "baseline_remeasured": False,
            "blocked_reason": "fresh real PDF source-document-disjoint holdout unavailable",
        },
        "seen_reference_v3_8_2": pdf_file_identity_counts(v382_pdf),
        "seen_reference_v3_9_1": pdf_file_identity_counts(v391_pdf),
    }


def build_seen_surface_manifest(registry: Mapping[str, Any], local_scan: Mapping[str, Any]) -> dict[str, Any]:
    v392_seen = read_json(v392.OUTPUTS["seen_surface_manifest_json"])
    return {
        "schema_version": f"{RUN_ID}_seen_surface_manifest_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "seen_policy": "v3_8_3/v3_9/v3_9_1 rows, candidates, source_identity, workbook, and source_document surfaces are fixed as seen-validation-only.",
        "seen_runs": [V3_8_3_RUN_ID, V3_9_RUN_ID, V3_9_1_RUN_ID],
        "v3_9_2_policy_source_run_id": V3_9_2_RUN_ID,
        "v3_9_2_seen_validation_downgraded_to_seen_validation_only": True,
        "registry_counts": registry["registry_counts"],
        "seen_counts_from_v3_9_2": v392_seen.get("seen_counts", {}),
        "real_unseen_registry_counts": {
            "PDF_source_document_disjoint": 0,
            "XLSX_workbook_disjoint": 0,
        },
        "real_unseen_local_fixture_counts": {
            "PDF_source_document_disjoint": len(local_scan["unseen_pdf_source_document_candidates"]),
            "XLSX_workbook_disjoint": len(local_scan["unseen_xlsx_workbook_candidates"]),
        },
        "ignored_non_holdout_asset_count": len(local_scan["ignored_non_holdout_assets"]),
        "source_identity_hash_seen_count": len(registry["source_identity_hashes"]),
        "source_atom_id_seen_count": len(registry["source_atom_ids"]),
        "success_evidence_policy": "Success claims require future real source-document/workbook-disjoint holdout and are blocked in this run.",
    }


def build_fresh_holdout_manifest(
    registry: Mapping[str, Any],
    local_scan: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    fidelity_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    real_candidates = [row for row in candidates if row.get("real_unseen") is True]
    synthetic_candidates = [row for row in candidates if row.get("synthetic") is True]
    real_included = Counter(
        row["source_family"]
        for row in fidelity_rows
        if row.get("real_unseen") is True and row.get("query_fidelity_headline_included") is True
    )
    synthetic_included = Counter(
        row["source_family"]
        for row in fidelity_rows
        if row.get("synthetic") is True and row.get("query_fidelity_headline_included") is True
    )
    minimum_targets = {
        "xlsx_unseen_workbooks": 8,
        "pdf_unseen_source_documents": 20,
        "query_fidelity_included_rows_per_family": 100,
    }
    return {
        "schema_version": f"{RUN_ID}_fresh_real_holdout_manifest_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "minimum_targets": minimum_targets,
        "real_holdout_sufficient": False,
        "real_holdout_acquired": False,
        "product_success_evidence_allowed": False,
        "real_unseen_registry_counts": {
            "PDF_source_document_disjoint": 0,
            "XLSX_workbook_disjoint": 0,
        },
        "real_unseen_local_fixture_counts": {
            "PDF_source_document_disjoint": len(local_scan["unseen_pdf_source_document_candidates"]),
            "XLSX_workbook_disjoint": len(local_scan["unseen_xlsx_workbook_candidates"]),
        },
        "real_unseen_insufficiency_reason": (
            "Current source registry has no unseen PDF source documents or XLSX workbooks; local fixture "
            "inventory has no holdout-eligible unseen real PDF/XLSX candidates."
        ),
        "query_candidate_count": len(candidates),
        "real_query_candidate_count": len(real_candidates),
        "synthetic_query_candidate_count": len(synthetic_candidates),
        "real_query_fidelity_included_counts": {
            "PDF": int(real_included["PDF"]),
            "XLSX": int(real_included["XLSX"]),
        },
        "synthetic_query_fidelity_included_counts": {
            "PDF": int(synthetic_included["PDF"]),
            "XLSX": int(synthetic_included["XLSX"]),
        },
        "synthetic_ood_guard": {
            "candidate_count": len(synthetic_candidates),
            "expanded_from_v3_9_2_count": 14,
            "anti_overfit_guard_allowed": True,
            "product_success_evidence_allowed": False,
        },
        "local_fixture_scan": local_scan,
        "registry_counts": registry["registry_counts"],
        "query_candidates": list(candidates),
    }


def build_index_summary(
    sourceatoms: Sequence[Mapping[str, Any]],
    searchunits: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_xlsx_nonprod_index_build_summary_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "index_namespace": ALLOWED_NAMESPACE,
        "allowed_namespace": ALLOWED_NAMESPACE,
        "blocked_namespaces": list(BLOCKED_NAMESPACES),
        "protected_namespaces_touched": [],
        "materialization_scope": "nonprod_manifest_materialized",
        "overlay_only": False,
        "sourceatom_manifest_rows": len(sourceatoms),
        "searchunit_manifest_rows": len(searchunits),
        "faiss_index_file_created": False,
        "db_or_production_namespace_written": False,
        "source_registry_baseline_mutated": False,
        "official_denominator_mutated": False,
        "candidate_generation_modes": [
            "table_block",
            "axis_pair",
            "row_slice",
            "cell_candidate",
            "legacy_row_window_reference_only",
        ],
        "forbidden_fields": list(FORBIDDEN_TABLE_AXIS_FIELDS),
        "direct_normalized_value_query_matching_used": False,
    }


def build_metrics(
    holdout: Mapping[str, Any],
    xlsx_eval: Mapping[str, Any],
    pdf_baseline: Mapping[str, Any],
    sourceatoms: Sequence[Mapping[str, Any]],
    searchunits: Sequence[Mapping[str, Any]],
    fidelity_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    included = Counter(row["source_family"] for row in fidelity_rows if row.get("query_fidelity_headline_included") is True)
    excluded = Counter(row["source_family"] for row in fidelity_rows if row.get("query_fidelity_headline_included") is not True)
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "fine_tuning_executed": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "direct_normalized_value_query_matching_used": False,
        "answer_value_in_query_success_evidence_used": False,
        "index_to_content_success_evidence_used": False,
        "file_or_source_title_leak_success_evidence_used": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "fresh_real_holdout": {
            "sufficient": False,
            "acquired": False,
            "product_success_evidence_allowed": False,
            "real_unseen_counts": holdout["real_unseen_registry_counts"],
            "minimum_targets": holdout["minimum_targets"],
            "real_query_fidelity_included_counts": holdout["real_query_fidelity_included_counts"],
        },
        "query_fidelity": {
            "included_counts": {"PDF": int(included["PDF"]), "XLSX": int(included["XLSX"])},
            "excluded_counts": {"PDF": int(excluded["PDF"]), "XLSX": int(excluded["XLSX"])},
            "excluded_buckets_retained_in_leakage_audit": list(EXCLUDED_FIDELITY_BUCKETS),
        },
        "xlsx_table_axis_materialization": {
            "index_namespace": ALLOWED_NAMESPACE,
            "materialized": True,
            "overlay_only": False,
            "sourceatom_manifest_rows": len(sourceatoms),
            "searchunit_manifest_rows": len(searchunits),
            "required_sourceatom_fields": list(REQUIRED_SOURCEATOM_TABLE_AXIS_FIELDS),
            "required_searchunit_fields": list(REQUIRED_SEARCHUNIT_TABLE_AXIS_FIELDS),
            "forbidden_fields_absent": True,
        },
        "xlsx_table_axis_eval": xlsx_eval,
        "pdf_file_identity_baseline": pdf_baseline,
    }


def build_failure_taxonomy(holdout: Mapping[str, Any], xlsx_eval: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_failure_taxonomy_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "fresh_real_holdout_failure": {
            "real_holdout_sufficient": False,
            "primary_reason": "insufficient_real_unseen_sources",
            "xlsx_unseen_workbook_target_met": False,
            "pdf_unseen_source_document_target_met": False,
            "query_fidelity_included_target_met": False,
            "synthetic_ood_guard_product_success_evidence_allowed": False,
        },
        "xlsx_materialization_scope": {
            "materialized": True,
            "overlay_only": False,
            "success_claim_blocked_without_real_holdout": True,
            "signal_empty_rank1_reduced_in_seen_smoke": (
                xlsx_eval["nonprod_seen_materialization_smoke"]["signal_empty_rank1_rate"]["numerator"]
                < xlsx_eval["old_seen_reference"]["signal_empty_rank1_rate"]["numerator"]
            ),
        },
        "pdf_scope": {
            "file_identity_baseline_only": True,
            "answer_ready_evidence_window_metric_computed": False,
            "ocr_touched": False,
        },
        "leakage_shortcuts_blocked": list(EXCLUDED_FIDELITY_BUCKETS),
        "performance_success_claim_allowed": False,
    }


def build_summary(
    artifacts: Mapping[str, Any],
    artifact_sha256: Mapping[str, str],
) -> dict[str, Any]:
    metrics = artifacts["metrics"]
    xlsx_eval = metrics["xlsx_table_axis_eval"]
    return {
        "schema_version": f"{RUN_ID}_summary_v1",
        "run_id": RUN_ID,
        "status": "DIAGNOSTIC_V3_10_FRESH_REAL_HOLDOUT_INSUFFICIENT_XLSX_TABLE_AXIS_NONPROD_MATERIALIZED",
        "event_type": "diagnostic_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization",
        "run_class": "diagnostic_only_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization",
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "fine_tuning_executed": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "staging_or_commit_performed": False,
        "seen_validation_locked_to_seen_validation_only": True,
        "fresh_real_holdout_acquired": False,
        "fresh_real_holdout_sufficient": False,
        "product_success_evidence_allowed": False,
        "synthetic_ood_product_success_evidence_allowed": False,
        "direct_normalized_value_query_matching_used": False,
        "answer_value_in_query_success_evidence_used": False,
        "index_to_content_success_evidence_used": False,
        "file_or_source_title_leak_success_evidence_used": False,
        "xlsx_nonprod_table_axis_materialized": True,
        "xlsx_nonprod_overlay_only": False,
        "xlsx_nonprod_namespace": ALLOWED_NAMESPACE,
        "blocked_namespaces": list(BLOCKED_NAMESPACES),
        "protected_namespaces_touched": [],
        "signal_empty_rank1_rate": {
            "old_seen_reference": xlsx_eval["old_seen_reference"]["signal_empty_rank1_rate"],
            "nonprod_seen_materialization_smoke": xlsx_eval["nonprod_seen_materialization_smoke"][
                "signal_empty_rank1_rate"
            ],
        },
        "xlsx_success_claim_allowed": False,
        "pdf_file_identity_baseline_only": True,
        "pdf_answer_ready_evidence_window_metric_computed": False,
        "ocr_touched": False,
        "artifact_paths": {key: repo_relative(path) for key, path in OUTPUTS.items()},
        "artifact_sha256": dict(artifact_sha256),
    }


def append_status_event(summary: Mapping[str, Any]) -> None:
    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": summary["event_type"],
        "status": summary["status"],
        "run_class": summary["run_class"],
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "fresh_real_holdout_acquired": False,
        "fresh_real_holdout_sufficient": False,
        "product_success_evidence_allowed": False,
        "xlsx_nonprod_table_axis_materialized": True,
        "xlsx_nonprod_overlay_only": False,
        "xlsx_nonprod_namespace": ALLOWED_NAMESPACE,
        "pdf_file_identity_baseline_only": True,
        "pdf_answer_ready_evidence_window_metric_computed": False,
        "ocr_touched": False,
        "direct_normalized_value_query_matching_used": False,
        "artifact_paths": summary["artifact_paths"],
        "artifact_sha256": {
            **summary["artifact_sha256"],
            "summary_json_sha256": sha256_file(OUTPUTS["summary_json"]),
        },
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [
        row
        for row in existing
        if not (row.get("run_id") == RUN_ID and row.get("event_type") == event["event_type"])
    ]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def update_docs(summary: Mapping[str, Any], metrics: Mapping[str, Any], holdout: Mapping[str, Any]) -> None:
    old_signal = metrics["xlsx_table_axis_eval"]["old_seen_reference"]["signal_empty_rank1_rate"]
    new_signal = metrics["xlsx_table_axis_eval"]["nonprod_seen_materialization_smoke"]["signal_empty_rank1_rate"]
    pdf_seen = metrics["pdf_file_identity_baseline"]["seen_reference_v3_9_1"]["file_resolve@1"]
    progress_entry = (
        f"- v3_10 fresh real holdout and XLSX table-axis non-prod rematerialization (`{RUN_ID}`) keeps "
        "v3_8_3/v3_9/v3_9_1 validation fixed as seen-validation-only. Fresh real holdout is still "
        "insufficient (PDF source-document-disjoint=0, XLSX workbook-disjoint=0), so product success "
        f"claims stay blocked. XLSX SourceAtom/SearchUnit table-axis fields are materialized in `{ALLOWED_NAMESPACE}` "
        "as non-prod manifests, not overlay-only; protected official/source registry/all-source/prod namespaces were "
        "not touched. PDF is baseline-only for file identity, with answer-ready evidence-window and OCR closed."
    )
    measurements_entry = f"""## 2026-05-24 - v3_10 Fresh Real Holdout and XLSX Table-Axis Non-Prod Rematerialization

- Run: `{RUN_ID}`
- Policy: diagnostic-only; official_metric_input_rows=0; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no fine-tuning, no threshold tuning, no winner selection.
- Fresh real holdout: insufficient. PDF source-document-disjoint=0/20 target, XLSX workbook-disjoint=0/8 target, real query-fidelity included rows PDF=0 and XLSX=0 against the 100/family target.
- Synthetic OOD guard: {holdout['synthetic_ood_guard']['candidate_count']} query candidates, anti-overfit guard only, product success evidence disallowed.
- XLSX table-axis materialization: `{ALLOWED_NAMESPACE}`, SourceAtom rows={metrics['xlsx_table_axis_materialization']['sourceatom_manifest_rows']}, SearchUnit rows={metrics['xlsx_table_axis_materialization']['searchunit_manifest_rows']}, overlay_only=false.

| XLSX lane | old seen reference | v3_10 non-prod seen smoke | fresh real holdout |
| --- | --- | --- | --- |
| signal-empty rank1 | {old_signal['numerator']}/{old_signal['denominator']} | {new_signal['numerator']}/{new_signal['denominator']} | 0/0 |
| table_or_range@3 | {metrics['xlsx_table_axis_eval']['old_seen_reference']['table_or_range@3']['numerator']}/{metrics['xlsx_table_axis_eval']['old_seen_reference']['table_or_range@3']['denominator']} | {metrics['xlsx_table_axis_eval']['nonprod_seen_materialization_smoke']['table_or_range@3']['numerator']}/{metrics['xlsx_table_axis_eval']['nonprod_seen_materialization_smoke']['table_or_range@3']['denominator']} | 0/0 |
| cell_or_value@3 | {metrics['xlsx_table_axis_eval']['old_seen_reference']['cell_or_value@3']['numerator']}/{metrics['xlsx_table_axis_eval']['old_seen_reference']['cell_or_value@3']['denominator']} | {metrics['xlsx_table_axis_eval']['nonprod_seen_materialization_smoke']['cell_or_value@3']['numerator']}/{metrics['xlsx_table_axis_eval']['nonprod_seen_materialization_smoke']['cell_or_value@3']['denominator']} | 0/0 |

PDF file identity baseline is kept separate from answer-ready evidence windows: v3_9_1 seen reference file_resolve@1={pdf_seen['numerator']}/{pdf_seen['denominator']}; fresh real PDF baseline is blocked by missing source-document-disjoint holdout.
"""
    triage_entry = f"""## v3_10 Fresh Holdout and XLSX Rematerialization Triage

- Fresh real holdout remains the blocker. There is no performance success claim in v3_10.
- XLSX table-axis is now materialized into non-prod SourceAtom/SearchUnit manifests under `{ALLOWED_NAMESPACE}`. This proves the phase is no longer overlay-only, but old seen metrics remain reference/no-regression only.
- Signal-empty rank1 moved from {old_signal['numerator']}/{old_signal['denominator']} to {new_signal['numerator']}/{new_signal['denominator']} in the seen materialization smoke. Table/range/cell rates are not claimed as improved until a real fresh holdout exists.
- PDF work is limited to file identity baseline accounting. Answer-ready evidence-window improvements and OCR remain closed.
- Leakage/shortcut buckets are excluded from headline and retained in audit: answer_value_in_query, index_to_content, source_title_leak, file_title_leak, exact_query_hack, major_topic_drift, unnatural_sheet_or_cell_reference.
"""
    v392.replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        "Overall status: `diagnostic_v3_10_fresh_real_holdout_insufficient_xlsx_table_axis_nonprod_materialized`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")
    v392.replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    v392.replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)


@lru_cache(maxsize=1)
def build_artifacts() -> dict[str, Any]:
    required_inputs = (
        SOURCE_REGISTRY_JSONL,
        v392.V3_8_2_PER_QUERY,
        v392.V3_9_1_PER_QUERY,
        v392.V3_9_1_QUERY_FIDELITY,
        v392.OUTPUTS["seen_surface_manifest_json"],
        v392.OUTPUTS["proposed_sourceatom_table_axis_schema_json"],
        v392.OUTPUTS["proposed_searchunit_table_axis_fields_json"],
        v392.OUTPUTS["proposed_nonprod_rematerialization_plan_json"],
    )
    missing = [repo_relative(path) for path in required_inputs if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required v3_10 input artifacts: " + ", ".join(missing))

    registry = load_registry_inventory()
    local_scan = classify_local_files(local_file_inventory(), registry)
    candidates = build_query_candidates(local_scan)
    fidelity_rows = build_query_fidelity_audit(candidates)
    leakage_rows = build_leakage_audit()
    sourceatom_rows, searchunit_rows = materialize_xlsx_nonprod_rows(registry["xlsx_rows"])
    xlsx_eval, xlsx_eval_rows = build_xlsx_eval(sourceatom_rows)
    pdf_baseline = build_pdf_baseline()
    holdout = build_fresh_holdout_manifest(registry, local_scan, candidates, fidelity_rows)
    seen = build_seen_surface_manifest(registry, local_scan)
    index_summary = build_index_summary(sourceatom_rows, searchunit_rows)
    metrics = build_metrics(holdout, xlsx_eval, pdf_baseline, sourceatom_rows, searchunit_rows, fidelity_rows)
    failure_taxonomy = build_failure_taxonomy(holdout, xlsx_eval)
    return {
        "metrics": metrics,
        "fresh_holdout_manifest": holdout,
        "seen_surface_manifest": seen,
        "query_fidelity_rows": fidelity_rows,
        "leakage_audit_rows": leakage_rows,
        "xlsx_sourceatom_rows": sourceatom_rows,
        "xlsx_searchunit_rows": searchunit_rows,
        "xlsx_index_build_summary": index_summary,
        "xlsx_eval_rows": xlsx_eval_rows,
        "failure_taxonomy": failure_taxonomy,
        "summary": build_summary(
            {
                "metrics": metrics,
                "fresh_holdout_manifest": holdout,
                "seen_surface_manifest": seen,
            },
            {},
        ),
    }


def write_artifacts(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    write_json(OUTPUTS["metrics_json"], artifacts["metrics"])
    write_json(OUTPUTS["fresh_real_holdout_manifest_json"], artifacts["fresh_holdout_manifest"])
    write_json(OUTPUTS["seen_surface_manifest_json"], artifacts["seen_surface_manifest"])
    write_jsonl(OUTPUTS["query_fidelity_audit_jsonl"], artifacts["query_fidelity_rows"])
    write_jsonl(OUTPUTS["leakage_audit_jsonl"], artifacts["leakage_audit_rows"])
    write_jsonl(OUTPUTS["xlsx_nonprod_sourceatom_manifest_jsonl"], artifacts["xlsx_sourceatom_rows"])
    write_jsonl(OUTPUTS["xlsx_nonprod_searchunit_manifest_jsonl"], artifacts["xlsx_searchunit_rows"])
    write_json(OUTPUTS["xlsx_nonprod_index_build_summary_json"], artifacts["xlsx_index_build_summary"])
    write_jsonl(OUTPUTS["xlsx_table_axis_eval_per_query_jsonl"], artifacts["xlsx_eval_rows"])
    write_json(OUTPUTS["failure_taxonomy_json"], artifacts["failure_taxonomy"])
    artifact_sha = {
        key.replace("_jsonl", "").replace("_json", "") + "_sha256": sha256_file(path)
        for key, path in OUTPUTS.items()
        if key != "summary_json"
    }
    summary = build_summary(artifacts, artifact_sha)
    write_json(OUTPUTS["summary_json"], summary)
    append_status_event(summary)
    update_docs(summary, artifacts["metrics"], artifacts["fresh_holdout_manifest"])
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build v3_10 fresh real holdout and XLSX table-axis non-prod rematerialization artifacts."
    )
    parser.add_argument("--check", action="store_true", help="Build in memory only.")
    args = parser.parse_args(argv)
    artifacts = build_artifacts()
    if args.check:
        print(json.dumps({"run_id": RUN_ID, "status": artifacts["summary"]["status"]}, ensure_ascii=False))
        return 0
    summary = write_artifacts(artifacts)
    print(
        json.dumps(
            {"run_id": RUN_ID, "status": summary["status"], "summary": repo_relative(OUTPUTS["summary_json"])},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
