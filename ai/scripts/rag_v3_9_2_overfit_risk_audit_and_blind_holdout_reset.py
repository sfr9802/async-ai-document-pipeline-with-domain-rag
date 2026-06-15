from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from eval.harness import rag_diagnostic_common as diagnostic_common  # noqa: E402

REPORT_DIR = ROOT / "reports" / "rag_eval" / "rag-ingestion"
QUALITY_DIR = REPORT_DIR / "quality"
SOURCE_REGISTRY_JSONL = ROOT / "ai" / "eval" / "source_registry" / "source_atom_registry_v1.jsonl"
STATUS_JSONL = REPORT_DIR / "status.jsonl"
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"
MEASUREMENTS_DOC = ROOT / "docs" / "rag-ingestion-measurements.md"
TRIAGE_DOC = ROOT / "docs" / "rag-ingestion-triage.md"

RUN_ID = "official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset"
V3_8_2_RUN_ID = "official_answer_citation_agentic_loop_run_v3_8_2_oracle_free_file_resolve"
V3_8_3_RUN_ID = "official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic"
V3_9_RUN_ID = "official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement"
V3_9_1_RUN_ID = "official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic"

V3_8_2_PER_QUERY = REPORT_DIR / f"{V3_8_2_RUN_ID}_per_query.jsonl"
V3_8_3_METRICS = REPORT_DIR / f"{V3_8_3_RUN_ID}_metrics.json"
V3_8_3_PER_QUERY = REPORT_DIR / f"{V3_8_3_RUN_ID}_per_query.jsonl"
V3_9_METRICS = REPORT_DIR / f"{V3_9_RUN_ID}_metrics.json"
V3_9_PER_QUERY = REPORT_DIR / f"{V3_9_RUN_ID}_per_query.jsonl"
V3_9_QUERY_FIDELITY = REPORT_DIR / f"{V3_9_RUN_ID}_query_fidelity_audit.jsonl"
V3_9_1_SUMMARY = REPORT_DIR / f"{V3_9_1_RUN_ID}_summary.json"
V3_9_1_METRICS = REPORT_DIR / f"{V3_9_1_RUN_ID}_metrics.json"
V3_9_1_PER_QUERY = REPORT_DIR / f"{V3_9_1_RUN_ID}_per_query.jsonl"
V3_9_1_QUERY_FIDELITY = REPORT_DIR / f"{V3_9_1_RUN_ID}_query_fidelity_audit.jsonl"
V3_9_1_SPLIT = REPORT_DIR / f"{V3_9_1_RUN_ID}_split_manifest.json"

OUTPUTS = {
    "summary_json": REPORT_DIR / f"{RUN_ID}_summary.json",
    "metrics_json": REPORT_DIR / f"{RUN_ID}_metrics.json",
    "overfit_risk_by_delta_jsonl": REPORT_DIR / f"{RUN_ID}_overfit_risk_by_delta.jsonl",
    "seen_surface_manifest_json": REPORT_DIR / f"{RUN_ID}_seen_surface_manifest.json",
    "fresh_holdout_candidate_manifest_json": REPORT_DIR / f"{RUN_ID}_fresh_holdout_candidate_manifest.json",
    "fresh_holdout_split_manifest_json": REPORT_DIR / f"{RUN_ID}_fresh_holdout_split_manifest.json",
    "query_fidelity_audit_jsonl": REPORT_DIR / f"{RUN_ID}_query_fidelity_audit.jsonl",
    "leakage_audit_jsonl": REPORT_DIR / f"{RUN_ID}_leakage_audit.jsonl",
    "architecture_scope_assessment_json": REPORT_DIR / f"{RUN_ID}_architecture_scope_assessment.json",
    "failure_taxonomy_json": REPORT_DIR / f"{RUN_ID}_failure_taxonomy.json",
    "proposed_sourceatom_table_axis_schema_json": REPORT_DIR / f"{RUN_ID}_proposed_sourceatom_table_axis_schema.json",
    "proposed_searchunit_table_axis_fields_json": REPORT_DIR / f"{RUN_ID}_proposed_searchunit_table_axis_fields.json",
    "proposed_nonprod_rematerialization_plan_json": REPORT_DIR / f"{RUN_ID}_proposed_nonprod_rematerialization_plan.json",
}

USER_OWNED_FIELDS = (
    "query_approval",
    "relevance",
    "answerability",
    "expected_answer",
    "supporting_evidence",
    "pass_fail",
    "denominator_eligibility",
)
EXCLUDED_BUCKETS = (
    "answer_value_in_query",
    "index_to_content",
    "source_title_leak",
    "file_title_leak",
    "exact_query_hack",
    "major_topic_drift",
    "unnatural_sheet_or_cell_reference",
)
XLSX_LOCATOR_METRICS = (
    "sheet_resolve@1",
    "sheet_resolve@3",
    "table_or_range_resolve@1",
    "table_or_range_resolve@3",
    "cell_or_value_resolve@1",
    "cell_or_value_resolve@3",
)
PDF_FILE_METRICS = (
    "file_resolve@1",
    "file_resolve@3",
    "abstain_rate",
    "wrong_file_block_rate",
)


def read_json(path: Path) -> dict[str, Any]:
    return diagnostic_common.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return diagnostic_common.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def sha256_file(path: Path) -> str:
    return diagnostic_common.sha256_file(path)


def artifact_exists(path: Path) -> bool:
    return diagnostic_common.artifact_exists(path)


def artifact_is_file(path: Path) -> bool:
    return diagnostic_common.artifact_is_file(path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": int(numerator),
        "denominator": int(denominator),
        "rate": (float(numerator) / float(denominator)) if denominator else 0.0,
    }


def metric_delta(base: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    base_n = int(base.get("numerator") or 0)
    base_d = int(base.get("denominator") or 0)
    curr_n = int(current.get("numerator") or 0)
    curr_d = int(current.get("denominator") or 0)
    base_rate = (base_n / base_d) if base_d else 0.0
    curr_rate = (curr_n / curr_d) if curr_d else 0.0
    return {
        "baseline": {"numerator": base_n, "denominator": base_d, "rate": base_rate},
        "current": {"numerator": curr_n, "denominator": curr_d, "rate": curr_rate},
        "delta_numerator": curr_n - base_n,
        "delta_rate": curr_rate - base_rate,
    }


def metric_counts(rows: Sequence[Mapping[str, Any]], metric: str) -> dict[str, Any]:
    return rate(sum(1 for row in rows if bool(row.get(metric))), len(rows))


def group_metric_delta(
    *,
    rows: Sequence[Mapping[str, Any]],
    baseline_field: str,
    metric: str,
) -> dict[str, Any]:
    baseline_count = sum(1 for row in rows if bool(as_mapping(row.get(baseline_field)).get(metric)))
    current_count = sum(1 for row in rows if bool(row.get(metric)))
    return metric_delta(rate(baseline_count, len(rows)), rate(current_count, len(rows)))


def load_registry_pdf_xlsx() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not SOURCE_REGISTRY_JSONL.exists():
        return rows
    with SOURCE_REGISTRY_JSONL.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if clean(row.get("source_family")).upper() in {"PDF", "XLSX"}:
                rows.append(row)
    return rows


def registry_document_key(row: Mapping[str, Any]) -> str:
    raw = as_mapping(row.get("raw_locator"))
    return clean(row.get("document_version_id") or raw.get("document_version_id") or row.get("source_identity"))


def registry_workbook_key(row: Mapping[str, Any]) -> str:
    raw = as_mapping(row.get("raw_locator"))
    return clean(raw.get("workbook") or row.get("workbook_id") or registry_document_key(row))


def xlsx_workbook_from_row(row: Mapping[str, Any]) -> str:
    gate = as_mapping(row.get("workbook_gate"))
    if gate:
        return clean(gate.get("source_file_name") or gate.get("workbook") or gate.get("workbook_id"))
    candidates = row.get("scoped_cell_candidates") or []
    if candidates:
        first = as_mapping(candidates[0])
        return clean(first.get("workbook") or first.get("source_file_name") or first.get("workbook_id"))
    return ""


def collect_source_identity_from_candidate(candidate: Mapping[str, Any]) -> str:
    return clean(
        candidate.get("source_identity")
        or candidate.get("candidate_source_identity")
        or candidate.get("workbook")
        or candidate.get("source_file_name")
    )


def build_seen_surface_manifest(
    *,
    registry_rows: Sequence[Mapping[str, Any]],
    v3_8_3_rows: Sequence[Mapping[str, Any]],
    v3_9_rows: Sequence[Mapping[str, Any]],
    v3_9_1_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    registry_by_atom = {clean(row.get("source_atom_id")): row for row in registry_rows if clean(row.get("source_atom_id"))}
    seen_atom_ids: set[str] = set()
    seen_source_identities: set[str] = set()
    seen_workbooks: set[str] = set()
    seen_documents: set[str] = set()

    for row in [*v3_8_3_rows, *v3_9_1_rows]:
        family = clean(row.get("source_family")).upper()
        if family == "XLSX":
            workbook = xlsx_workbook_from_row(row)
            if workbook:
                seen_workbooks.add(workbook)
        for field in ("scoped_cell_candidates", "resolved_file_candidates"):
            for candidate in row.get(field, []) or []:
                candidate_map = as_mapping(candidate)
                atom_id = clean(candidate_map.get("source_atom_id"))
                if atom_id:
                    seen_atom_ids.add(atom_id)
                identity = collect_source_identity_from_candidate(candidate_map)
                if identity:
                    seen_source_identities.add(identity)
                if family == "PDF":
                    document_version_id = clean(candidate_map.get("document_version_id"))
                    if document_version_id:
                        seen_documents.add(document_version_id)
                if family == "XLSX":
                    workbook = clean(candidate_map.get("workbook") or candidate_map.get("source_file_name"))
                    if workbook:
                        seen_workbooks.add(workbook)

    for row in v3_9_rows:
        source_hash = clean(row.get("source_identity_sha256"))
        if source_hash:
            seen_source_identities.add(f"sha256:{source_hash}")

    for atom_id in seen_atom_ids:
        atom = registry_by_atom.get(atom_id)
        if not atom:
            continue
        family = clean(atom.get("source_family")).upper()
        if family == "XLSX":
            seen_workbooks.add(registry_workbook_key(atom))
        elif family == "PDF":
            seen_documents.add(registry_document_key(atom))

    all_xlsx_workbooks = {registry_workbook_key(row) for row in registry_rows if clean(row.get("source_family")).upper() == "XLSX"}
    all_pdf_documents = {registry_document_key(row) for row in registry_rows if clean(row.get("source_family")).upper() == "PDF"}
    xlsx_unseen_workbooks = sorted(item for item in all_xlsx_workbooks - seen_workbooks if item)
    pdf_unseen_documents = sorted(item for item in all_pdf_documents - seen_documents if item)

    return {
        "schema_version": f"{RUN_ID}_seen_surface_manifest_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "seen_runs": [V3_8_3_RUN_ID, V3_9_RUN_ID, V3_9_1_RUN_ID],
        "seen_policy": (
            "All v3_8_3/v3_9/v3_9_1 dev, validation, row, candidate, workbook, source-document, "
            "and source-identity surfaces are treated as seen for future success interpretation."
        ),
        "registry_counts": {
            "PDF_source_atoms": sum(1 for row in registry_rows if clean(row.get("source_family")).upper() == "PDF"),
            "XLSX_source_atoms": sum(1 for row in registry_rows if clean(row.get("source_family")).upper() == "XLSX"),
            "PDF_source_documents": len(all_pdf_documents),
            "XLSX_workbooks": len(all_xlsx_workbooks),
        },
        "seen_counts": {
            "candidate_or_metric_source_atom_ids": len(seen_atom_ids),
            "source_identity_or_hashes": len(seen_source_identities),
            "PDF_source_documents": len(seen_documents),
            "XLSX_workbooks": len(seen_workbooks),
            "v3_9_quality_rows": len(v3_9_rows),
            "v3_9_1_metric_rows": len(v3_9_1_rows),
        },
        "real_unseen_counts": {
            "PDF_source_document_disjoint": len(pdf_unseen_documents),
            "XLSX_workbook_disjoint": len(xlsx_unseen_workbooks),
        },
        "real_unseen_source_document_disjoint_available": bool(pdf_unseen_documents),
        "real_unseen_workbook_disjoint_available": bool(xlsx_unseen_workbooks),
        "real_unseen_holdout_sufficient": False,
        "real_unseen_insufficiency_reason": (
            "The current PDF/XLSX source registry has no source-document-disjoint PDF documents and no "
            "workbook-disjoint XLSX workbooks outside the seen v3_8_3/v3_9/v3_9_1 surfaces."
        ),
        "unseen_pdf_document_candidates": pdf_unseen_documents,
        "unseen_xlsx_workbook_candidates": xlsx_unseen_workbooks,
        "success_evidence_policy": "No future performance success may be claimed on the seen validation split.",
    }


def synthetic_holdout_candidates() -> list[dict[str, Any]]:
    xlsx_rows = [
        ("xlsx_single_sheet_simple_table", "terse_question", "지역별 집계표에서 가장 최근 기준 행의 증가 방향만 확인해 줘."),
        ("xlsx_multi_sheet_workbook", "messy_user_like", "그 파일 여러 시트 중에 서비스 구분별로 요약된 표 있잖아요, 이번 분기 쪽 행만 찾아줘"),
        ("xlsx_merged_header_workbook", "implicit_context", "상단 병합 머리글 아래 세부 항목이 나뉘는 표에서 비용 항목 위치를 잡아줘."),
        ("xlsx_sparse_table", "short_fragment", "빈칸 많은 표, 합계 직전 행"),
        ("xlsx_long_table", "colloquial_korean", "엄청 긴 목록에서 기관 유형이 바뀌는 지점 근처 행 좀 봐줘"),
        ("xlsx_multi_row_header", "no_source_title", "두 줄짜리 헤더에서 단위가 붙은 세부 열을 기준으로 비교할 행을 골라줘."),
        ("xlsx_date_number_unit_heavy_table", "messy_user_like", "날짜랑 단위가 섞여 있는 표에서 월별 값 말고 단위 설명 있는 열부터 확인해 줄래?"),
        ("xlsx_korean_public_data_style_sheet", "implicit_context", "공공데이터식 긴 컬럼명 표에서 시군구 단위 요약 행을 찾아줘."),
    ]
    pdf_rows = [
        ("pdf_native_text_policy_doc", "terse_question", "정책 문서에서 적용 대상 설명이 시작되는 단락은?"),
        ("pdf_form_like_pdf", "short_fragment", "신청서 양식, 제출 서류 칸"),
        ("pdf_table_like_pdf", "implicit_context", "본문 안 표 형태 구간에서 항목별 기준을 설명하는 행을 찾아줘."),
        ("pdf_heading_body_heavy_pdf", "messy_user_like", "제목이 많고 본문이 이어지는 보고서에서 추진 배경 부분만 먼저 잡아줘"),
        ("pdf_dot_leader_artifact_pdf", "colloquial_korean", "목차 점선 때문에 헷갈리는 문서에서 실제 본문 쪽 근거 창으로 가야 해"),
        ("pdf_multi_page_section_pdf", "no_source_title", "여러 페이지에 걸친 절에서 첫 페이지 제목 말고 다음 페이지 본문 근거를 확인해 줘."),
    ]
    rows: list[dict[str, Any]] = []
    for index, (ood_type, style, query) in enumerate(xlsx_rows, start=1):
        rows.append(
            synthetic_candidate(
                index=index,
                family="XLSX",
                ood_type=ood_type,
                query_style=style,
                query_text=query,
            )
        )
    for index, (ood_type, style, query) in enumerate(pdf_rows, start=1):
        rows.append(
            synthetic_candidate(
                index=index,
                family="PDF",
                ood_type=ood_type,
                query_style=style,
                query_text=query,
            )
        )
    return rows


def synthetic_candidate(*, index: int, family: str, ood_type: str, query_style: str, query_text: str) -> dict[str, Any]:
    prefix = family.lower()
    source_identity = f"synthetic_ood:{prefix}:{ood_type}:doc-{index:02d}"
    row: dict[str, Any] = {
        "candidate_id": f"{prefix}_synthetic_ood_{index:02d}",
        "source_family": family,
        "source_identity": source_identity,
        "source_identity_sha256": sha256_text(source_identity),
        "ood_type": ood_type,
        "fixture_role": "diagnostic_only_anti_overfit_guard",
        "synthetic": True,
        "real_unseen": False,
        "product_success_evidence_allowed": False,
        "anti_overfit_guard_allowed": True,
        "query_style": query_style,
        "query_text": query_text,
        "query_text_sha256": sha256_text(query_text),
        "official_metric_input": False,
        "official_metric_input_rows": 0,
    }
    for field in USER_OWNED_FIELDS:
        row[field] = ""
    if family == "XLSX":
        row["workbook_disjoint_key"] = f"synthetic_workbook:{ood_type}"
        row["source_document_disjoint_key"] = ""
    else:
        row["workbook_disjoint_key"] = ""
        row["source_document_disjoint_key"] = f"synthetic_pdf_document:{ood_type}"
    return row


def query_fidelity_bucket_for_holdout(row: Mapping[str, Any]) -> tuple[str, str]:
    query = clean(row.get("query_text"))
    source_identity = clean(row.get("source_identity"))
    source_leaf = source_identity.rsplit(":", 1)[-1].replace("_", " ").replace("-", " ")
    lowered = query.casefold()
    reasons: list[str] = []
    if re.search(r"\b[A-Z]{1,3}\d{1,5}\b", query):
        reasons.append("unnatural_sheet_or_cell_reference")
    if source_leaf and source_leaf.casefold() in lowered:
        reasons.append("source_title_leak")
    if ".pdf" in lowered or ".xlsx" in lowered:
        reasons.append("file_title_leak")
    if "정답" in query or "answer" in lowered:
        reasons.append("answer_value_in_query")
    if "page " in lowered or "페이지 3" in query or "시트1" in query:
        reasons.append("index_to_content")
    bucket = reasons[0] if reasons else "included"
    return bucket, "|".join(reasons)


def build_query_fidelity_audit(candidate_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidate_rows:
        bucket, reason = query_fidelity_bucket_for_holdout(candidate)
        included = bucket == "included"
        row = {
            "schema_version": f"{RUN_ID}_query_fidelity_audit_v1",
            "run_id": RUN_ID,
            "candidate_id": candidate["candidate_id"],
            "source_family": candidate["source_family"],
            "source_identity_sha256": candidate["source_identity_sha256"],
            "ood_type": candidate["ood_type"],
            "query_style": candidate["query_style"],
            "query_text_sha256": candidate["query_text_sha256"],
            "query_fidelity_bucket": bucket,
            "query_fidelity_headline_included": included,
            "query_fidelity_exclusion_reason": "" if included else reason,
            "answer_value_in_query": "answer_value_in_query" in reason,
            "index_to_content": "index_to_content" in reason,
            "source_title_leak": "source_title_leak" in reason,
            "file_title_leak": "file_title_leak" in reason,
            "exact_query_hack": False,
            "major_topic_drift": False,
            "unnatural_sheet_or_cell_reference": "unnatural_sheet_or_cell_reference" in reason,
            "official_metric_input": False,
            "official_metric_input_rows": 0,
            "product_success_evidence_allowed": False,
            "anti_overfit_guard_allowed": True,
        }
        for field in USER_OWNED_FIELDS:
            row[field] = ""
        rows.append(row)
    return rows


def build_fresh_holdout_candidate_manifest(seen_manifest: Mapping[str, Any]) -> dict[str, Any]:
    candidates = synthetic_holdout_candidates()
    counts_by_family = Counter(candidate["source_family"] for candidate in candidates)
    counts_by_type = Counter(candidate["ood_type"] for candidate in candidates)
    return {
        "schema_version": f"{RUN_ID}_fresh_holdout_candidate_manifest_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "real_unseen_holdout_sufficient": False,
        "real_unseen_holdout_shortage": seen_manifest["real_unseen_counts"],
        "real_unseen_shortage_declared": True,
        "synthetic_ood_fixture_created": True,
        "synthetic_fixture_policy": (
            "Synthetic rows are diagnostic-only anti-overfit guards. They are not product success evidence, "
            "not official denominator input, not qrels, not labels, and not a source for expected/supporting answers."
        ),
        "query_styles_required": [
            "terse_question",
            "messy_user_like",
            "short_fragment",
            "implicit_context",
            "no_source_title",
            "colloquial_korean",
        ],
        "source_type_coverage_requested": {
            "XLSX": [
                "single-sheet simple table",
                "multi-sheet workbook",
                "merged header workbook",
                "sparse table",
                "long table",
                "multi-row header",
                "date/number/unit-heavy table",
                "Korean public-data style sheet",
            ],
            "PDF": [
                "native text policy doc",
                "form-like PDF",
                "table-like PDF",
                "heading/body heavy PDF",
                "dot-leader artifact PDF",
                "multi-page section PDF",
            ],
        },
        "candidate_count": len(candidates),
        "candidate_counts_by_family": dict(sorted(counts_by_family.items())),
        "candidate_counts_by_ood_type": dict(sorted(counts_by_type.items())),
        "candidates": candidates,
    }


def build_fresh_holdout_split_manifest(
    candidate_manifest: Mapping[str, Any],
    query_fidelity_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    candidates = list(candidate_manifest["candidates"])
    headline_ids = {
        row["candidate_id"]
        for row in query_fidelity_rows
        if bool(row.get("query_fidelity_headline_included"))
    }
    headline_candidates = [row for row in candidates if row["candidate_id"] in headline_ids]
    excluded_candidates = [row for row in candidates if row["candidate_id"] not in headline_ids]
    xlsx_workbooks = [clean(row.get("workbook_disjoint_key")) for row in headline_candidates if row["source_family"] == "XLSX"]
    pdf_docs = [clean(row.get("source_document_disjoint_key")) for row in headline_candidates if row["source_family"] == "PDF"]
    return {
        "schema_version": f"{RUN_ID}_fresh_holdout_split_manifest_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "split_policy": "fresh_blind_or_ood_rows_only; existing v3_8_3/v3_9/v3_9_1 validation is seen.",
        "real_unseen_holdout_sufficient": False,
        "synthetic_ood_guard_used": True,
        "product_success_evidence_allowed": False,
        "headline_candidate_count": len(headline_candidates),
        "excluded_candidate_count": len(excluded_candidates),
        "headline_counts_by_family": dict(sorted(Counter(row["source_family"] for row in headline_candidates).items())),
        "excluded_counts_by_family": dict(sorted(Counter(row["source_family"] for row in excluded_candidates).items())),
        "workbook_disjoint_guard": {
            "family": "XLSX",
            "required": True,
            "passed_for_synthetic_ood": len(xlsx_workbooks) == len(set(xlsx_workbooks)),
            "real_unseen_workbook_disjoint_available": False,
            "seen_validation_reuse_allowed": False,
        },
        "source_document_disjoint_guard": {
            "family": "PDF",
            "required": True,
            "passed_for_synthetic_ood": len(pdf_docs) == len(set(pdf_docs)),
            "real_unseen_source_document_disjoint_available": False,
            "seen_validation_reuse_allowed": False,
        },
        "user_owned_fields_blank": all(clean(row.get(field)) == "" for row in candidates for field in USER_OWNED_FIELDS),
        "query_fidelity_audit": {
            "rows": len(query_fidelity_rows),
            "headline_included": sum(bool(row.get("query_fidelity_headline_included")) for row in query_fidelity_rows),
            "excluded": sum(not bool(row.get("query_fidelity_headline_included")) for row in query_fidelity_rows),
            "excluded_buckets_retained": True,
            "exclusion_counts": dict(
                sorted(
                    Counter(
                        clean(row.get("query_fidelity_bucket"))
                        for row in query_fidelity_rows
                        if not bool(row.get("query_fidelity_headline_included"))
                    ).items()
                )
            ),
        },
        "split_rows": [
            {
                "candidate_id": row["candidate_id"],
                "source_family": row["source_family"],
                "ood_type": row["ood_type"],
                "split": "fresh_blind_synthetic_ood_guard"
                if row["candidate_id"] in headline_ids
                else "fresh_blind_synthetic_ood_excluded_from_headline",
                "query_fidelity_headline_included": row["candidate_id"] in headline_ids,
                "product_success_evidence_allowed": False,
                "anti_overfit_guard_allowed": True,
            }
            for row in candidates
        ],
    }


def query_fidelity_delta_rows(v3_9_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split in sorted({clean(row.get("split")) for row in v3_9_rows if clean(row.get("split"))}):
        for family in sorted({clean(row.get("source_family")) for row in v3_9_rows if clean(row.get("source_family"))}):
            for included in (True, False):
                bucket_rows = [
                    row
                    for row in v3_9_rows
                    if clean(row.get("split")) == split
                    and clean(row.get("source_family")) == family
                    and bool(row.get("query_fidelity_headline_included")) is included
                ]
                if not bucket_rows:
                    continue
                base = rate(sum(bool(row.get("raw_final_pass_like")) for row in bucket_rows), len(bucket_rows))
                current = rate(sum(bool(row.get("answer_pass_like")) for row in bucket_rows), len(bucket_rows))
                rows.append(
                    {
                        "delta_type": "query_fidelity_included_delta" if included else "query_fidelity_excluded_delta",
                        "run_id": V3_9_RUN_ID,
                        "split": split,
                        "source_family": family,
                        "metric": "answer_pass_like_minus_raw_final_pass_like",
                        "delta": metric_delta(base, current),
                        "overfit_risk_labels": ["scorer_surface_overfit", "insufficient_blind_evidence"]
                        if included
                        else ["leakage_adjacent", "scorer_surface_overfit", "insufficient_blind_evidence"],
                        "future_success_evidence": False,
                        "interpretation": (
                            "Query-fidelity included/excluded movement is from the repeated v3_9 seen split; "
                            "it can guide residual triage but cannot certify future success."
                        ),
                    }
                )
    return rows


def build_leakage_audit(
    *,
    v3_9_rows: Sequence[Mapping[str, Any]],
    v3_9_1_fidelity: Sequence[Mapping[str, Any]],
    fresh_fidelity: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_name, source_rows in (
        ("v3_9_quality_seen_split", v3_9_rows),
        ("v3_9_1_xlsx_seen_validation", v3_9_1_fidelity),
        ("v3_9_2_fresh_synthetic_ood_guard", fresh_fidelity),
    ):
        bucket_counter: Counter[str] = Counter()
        included_counter: Counter[str] = Counter()
        for row in source_rows:
            bucket = clean(row.get("query_fidelity_bucket")) or "included"
            bucket_counter[bucket] += 1
            if bool(row.get("query_fidelity_headline_included")):
                included_counter[bucket] += 1
        for bucket, count in sorted(bucket_counter.items()):
            rows.append(
                {
                    "schema_version": f"{RUN_ID}_leakage_audit_v1",
                    "run_id": RUN_ID,
                    "source_surface": source_name,
                    "bucket": bucket,
                    "row_count": count,
                    "headline_included_count": included_counter.get(bucket, 0),
                    "excluded_from_success_evidence": bucket in EXCLUDED_BUCKETS,
                    "source_title_file_title_leak_adjacency": bucket in {"source_title_leak", "file_title_leak"},
                    "answer_value_in_query_adjacency": bucket == "answer_value_in_query",
                    "index_to_content_adjacency": bucket == "index_to_content",
                    "success_evidence_allowed": False if bucket in EXCLUDED_BUCKETS else source_name.endswith("fresh_synthetic_ood_guard"),
                    "diagnostic_only": True,
                    "official_metric_input_rows": 0,
                }
            )
    return rows


def build_xlsx_delta_rows(
    *,
    v3_9_1_rows: Sequence[Mapping[str, Any]],
    v3_9_1_metrics: Mapping[str, Any],
    v3_9_1_split: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    xlsx = as_mapping(as_mapping(v3_9_1_metrics.get("per_source_family")).get("XLSX"))
    baseline_metrics = as_mapping(xlsx.get("baseline_v3_8_3_metrics"))
    current_metrics = as_mapping(xlsx.get("metrics"))
    for metric in XLSX_LOCATOR_METRICS:
        delta = metric_delta(as_mapping(baseline_metrics.get(metric)), as_mapping(current_metrics.get(metric)))
        labels = ["insufficient_blind_evidence"]
        if delta["delta_numerator"] > 0:
            labels.append("weak_general")
            labels.append("dev_or_seen_validation_only")
        if metric == "table_or_range_resolve@3" and delta["delta_numerator"] < 0:
            labels.append("metric_tradeoff")
        rows.append(
            {
                "delta_type": "dev_delta",
                "run_id": V3_9_1_RUN_ID,
                "source_family": "XLSX",
                "metric": metric,
                "delta": delta,
                "overfit_risk_labels": labels,
                "future_success_evidence": False,
                "interpretation": "Full v3_9_1 current-surface delta over a seen 344-row XLSX surface.",
            }
        )

    validation = as_mapping(v3_9_1_split.get("validation"))
    validation_metrics = as_mapping(validation.get("metrics"))
    validation_baseline = {
        "sheet_resolve@1": rate(112, 170),
        "sheet_resolve@3": rate(112, 170),
        "table_or_range_resolve@1": rate(2, 170),
        "table_or_range_resolve@3": rate(6, 170),
        "cell_or_value_resolve@1": rate(2, 170),
        "cell_or_value_resolve@3": rate(6, 170),
    }
    for metric in XLSX_LOCATOR_METRICS:
        delta = metric_delta(validation_baseline.get(metric, rate(0, 0)), as_mapping(validation_metrics.get(metric)))
        labels = ["dev_or_seen_validation_only", "insufficient_blind_evidence"]
        if delta["delta_numerator"] > 0:
            labels.insert(0, "weak_general")
        if metric == "table_or_range_resolve@3" and delta["delta_numerator"] < 0:
            labels.insert(0, "metric_tradeoff")
        rows.append(
            {
                "delta_type": "old_validation_delta",
                "run_id": V3_9_1_RUN_ID,
                "source_family": "XLSX",
                "metric": metric,
                "delta": delta,
                "overfit_risk_labels": labels,
                "future_success_evidence": False,
                "interpretation": "Workbook-disjoint validation was already repeatedly exposed by v3_8_3/v3_9/v3_9_1.",
            }
        )

    leave_one = as_mapping(v3_9_1_split.get("leave_one_workbook_out"))
    for workbook, payload in sorted(leave_one.items()):
        metrics = as_mapping(as_mapping(payload).get("metrics"))
        for metric in ("table_or_range_resolve@3", "cell_or_value_resolve@3"):
            rows.append(
                {
                    "delta_type": "leave_one_workbook_out_delta",
                    "run_id": V3_9_1_RUN_ID,
                    "source_family": "XLSX",
                    "workbook_sha256": sha256_text(workbook),
                    "metric": metric,
                    "current": as_mapping(metrics.get(metric)),
                    "overfit_risk_labels": ["dev_or_seen_validation_only", "insufficient_blind_evidence"],
                    "future_success_evidence": False,
                    "interpretation": "Leave-one-workbook diagnostic is useful only as seen-surface stress after this loop.",
                }
            )

    fidelity_by_query = {
        clean(row.get("query_id")): row
        for row in read_jsonl(V3_9_1_QUERY_FIDELITY)
        if clean(row.get("query_id"))
    }
    for bucket in sorted({clean(row.get("query_fidelity_bucket")) for row in fidelity_by_query.values()}):
        bucket_rows = [
            row
            for row in v3_9_1_rows
            if clean(as_mapping(fidelity_by_query.get(clean(row.get("query_id")))).get("query_fidelity_bucket")) == bucket
        ]
        if not bucket_rows:
            continue
        delta = group_metric_delta(rows=bucket_rows, baseline_field="baseline_v3_8_3", metric="table_or_range_resolve@3")
        rows.append(
            {
                "delta_type": "leakage_bucket_delta",
                "run_id": V3_9_1_RUN_ID,
                "source_family": "XLSX",
                "bucket": bucket,
                "metric": "table_or_range_resolve@3",
                "row_count": len(bucket_rows),
                "delta": delta,
                "overfit_risk_labels": ["leakage_adjacent", "insufficient_blind_evidence"]
                if bucket in EXCLUDED_BUCKETS
                else ["dev_or_seen_validation_only", "insufficient_blind_evidence"],
                "future_success_evidence": False,
            }
        )

    for signal_bucket in ("0", "1", "2+"):
        if signal_bucket == "0":
            bucket_rows = [row for row in v3_9_1_rows if int(row.get("locator_signal_count_rank1") or 0) == 0]
        elif signal_bucket == "1":
            bucket_rows = [row for row in v3_9_1_rows if int(row.get("locator_signal_count_rank1") or 0) == 1]
        else:
            bucket_rows = [row for row in v3_9_1_rows if int(row.get("locator_signal_count_rank1") or 0) >= 2]
        for metric in ("table_or_range_resolve@3", "cell_or_value_resolve@3"):
            rows.append(
                {
                    "delta_type": "locator_signal_count_delta",
                    "run_id": V3_9_1_RUN_ID,
                    "source_family": "XLSX",
                    "locator_signal_count_bucket": signal_bucket,
                    "metric": metric,
                    "row_count": len(bucket_rows),
                    "delta": group_metric_delta(
                        rows=bucket_rows,
                        baseline_field="baseline_v3_8_3",
                        metric=metric,
                    ),
                    "overfit_risk_labels": ["dev_or_seen_validation_only", "insufficient_blind_evidence"],
                    "future_success_evidence": False,
                }
            )

    signal_dist = as_mapping(xlsx.get("locator_signal_count_distribution"))
    rows.append(
        {
            "delta_type": "rank1_signal_empty_delta",
            "run_id": V3_9_1_RUN_ID,
            "source_family": "XLSX",
            "metric": "rank1_locator_signal_count_zero",
            "baseline": {"zero_signal_rank1": 261, "rank1_candidate_count": 300},
            "current": {
                "zero_signal_rank1": int(signal_dist.get("signal_empty_rank1_count") or 0),
                "rank1_candidate_count": int(signal_dist.get("rank1_candidate_count") or 0),
            },
            "delta_numerator": int(signal_dist.get("signal_empty_rank1_count") or 0) - 261,
            "overfit_risk_labels": ["weak_general", "dev_or_seen_validation_only", "insufficient_blind_evidence"],
            "future_success_evidence": False,
            "interpretation": "Signal-empty rank1 pressure improved only slightly and remains dominant.",
        }
    )

    regressions = [
        row
        for row in v3_9_1_rows
        if bool(as_mapping(row.get("baseline_v3_8_3")).get("table_or_range_resolve@3"))
        and not bool(row.get("table_or_range_resolve@3"))
    ]
    for row in regressions:
        rows.append(
            {
                "delta_type": "table_range_at3_regression_case",
                "run_id": V3_9_1_RUN_ID,
                "source_family": "XLSX",
                "query_id": clean(row.get("query_id")),
                "query_scope": clean(row.get("query_scope")),
                "locator_signal_count_rank1": int(row.get("locator_signal_count_rank1") or 0),
                "xlsx_miss_taxonomy": clean(row.get("xlsx_miss_taxonomy")),
                "overfit_risk_labels": ["metric_tradeoff", "insufficient_blind_evidence"],
                "future_success_evidence": False,
            }
        )
    return rows


def build_pdf_delta_rows(
    *,
    v3_8_2_rows: Sequence[Mapping[str, Any]],
    v3_9_1_rows: Sequence[Mapping[str, Any]],
    v3_9_1_metrics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    baseline_by_query = {clean(row.get("query_id")): row for row in v3_8_2_rows if clean(row.get("source_family")).upper() == "PDF"}
    pdf_rows = [row for row in v3_9_1_rows if clean(row.get("source_family")).upper() == "PDF"]
    current_by_query = {clean(row.get("query_id")): row for row in pdf_rows}
    v391_pdf_metrics = as_mapping(as_mapping(as_mapping(v3_9_1_metrics.get("per_source_family")).get("PDF_FILE_IDENTITY")).get("metrics"))
    baseline_metrics = {
        "file_resolve@1": rate(65, 329),
        "file_resolve@3": rate(129, 329),
        "abstain_rate": rate(182, 329),
        "wrong_file_block_rate": rate(57, 329),
    }
    for metric in PDF_FILE_METRICS:
        delta = metric_delta(baseline_metrics[metric], as_mapping(v391_pdf_metrics.get(metric)))
        labels = ["insufficient_blind_evidence"]
        if metric == "file_resolve@1" and delta["delta_numerator"] > 0:
            labels += ["weak_general", "dev_or_seen_validation_only"]
        if metric == "wrong_file_block_rate" and delta["delta_numerator"] > 0:
            labels += ["metric_tradeoff", "dev_or_seen_validation_only"]
        rows.append(
            {
                "delta_type": "pdf_file1_gain_vs_wrong_file_disambiguation_abstain_movement",
                "run_id": V3_9_1_RUN_ID,
                "source_family": "PDF",
                "metric": metric,
                "delta": delta,
                "overfit_risk_labels": labels,
                "future_success_evidence": False,
                "answer_ready_evidence_window_mixed": False,
            }
        )

    gains: list[dict[str, Any]] = []
    for query_id, current in sorted(current_by_query.items()):
        baseline = as_mapping(baseline_by_query.get(query_id))
        if not bool(baseline.get("file_resolve@1")) and bool(current.get("file_resolve@1")):
            candidates = [as_mapping(candidate) for candidate in current.get("resolved_file_candidates", [])]
            top = candidates[0] if candidates else {}
            signals = list(top.get("source_identity_normalization_signals") or [])
            gains.append(
                {
                    "query_id": query_id,
                    "query_scope": clean(current.get("query_scope")),
                    "movement": "file_resolve@1_false_to_true",
                    "resolve_status": clean(current.get("resolve_status")),
                    "source_identity_normalization_signals": signals,
                    "category": "query_source_title_or_date_alias_adjacency"
                    if signals
                    else "retrieval_order_confidence_movement",
                    "success_evidence_allowed": False,
                }
            )
    rows.append(
        {
            "delta_type": "pdf_file_at1_gain_case_review",
            "run_id": V3_9_1_RUN_ID,
            "source_family": "PDF",
            "gain_case_count": len(gains),
            "gain_cases": gains,
            "overfit_risk_labels": ["leakage_adjacent", "weak_general", "insufficient_blind_evidence"]
            if gains
            else ["insufficient_blind_evidence"],
            "future_success_evidence": False,
            "interpretation": "The +1 rank1 file identity gain is not enough to offset unchanged @3/abstain and wrong-file block movement.",
        }
    )
    return rows


def build_overfit_delta_rows(
    *,
    v3_8_2_rows: Sequence[Mapping[str, Any]],
    v3_9_rows: Sequence[Mapping[str, Any]],
    v3_9_1_rows: Sequence[Mapping[str, Any]],
    v3_9_1_metrics: Mapping[str, Any],
    v3_9_1_split: Mapping[str, Any],
) -> list[dict[str, Any]]:
    xlsx_rows = [row for row in v3_9_1_rows if clean(row.get("source_family")).upper() == "XLSX"]
    rows = [
        *build_xlsx_delta_rows(v3_9_1_rows=xlsx_rows, v3_9_1_metrics=v3_9_1_metrics, v3_9_1_split=v3_9_1_split),
        *query_fidelity_delta_rows(v3_9_rows),
        *build_pdf_delta_rows(v3_8_2_rows=v3_8_2_rows, v3_9_1_rows=v3_9_1_rows, v3_9_1_metrics=v3_9_1_metrics),
    ]
    for index, row in enumerate(rows, start=1):
        row.setdefault("schema_version", f"{RUN_ID}_overfit_risk_by_delta_v1")
        row.setdefault("run_id", RUN_ID)
        row["delta_row_id"] = f"delta_{index:04d}"
        row.setdefault("diagnostic_only", True)
        row.setdefault("official_metric_input_rows", 0)
    return rows


def overfit_label_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        for label in row.get("overfit_risk_labels", []) or []:
            counts[clean(label)] += 1
    for label in (
        "likely_general",
        "weak_general",
        "dev_or_seen_validation_only",
        "leakage_adjacent",
        "metric_tradeoff",
        "scorer_surface_overfit",
        "insufficient_blind_evidence",
    ):
        counts.setdefault(label, 0)
    return dict(sorted(counts.items()))


def build_architecture_scope_assessment(v3_9_1_summary: Mapping[str, Any], pdf_delta_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_architecture_scope_assessment_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "v3_9_1_hash_lock": {
            "source_registry_sha256_unchanged": bool(v3_9_1_summary.get("source_registry_sha256_unchanged")),
            "index_artifact_sha256_unchanged": bool(v3_9_1_summary.get("index_artifact_sha256_unchanged")),
            "official_denominator_index_sha256_unchanged": bool(v3_9_1_summary.get("official_denominator_index_sha256_unchanged")),
            "source_registry_sha256_before": clean(v3_9_1_summary.get("source_registry_sha256_before")),
            "source_registry_sha256_after": clean(v3_9_1_summary.get("source_registry_sha256_after")),
            "index_artifact_sha256_before": clean(v3_9_1_summary.get("index_artifact_sha256_before")),
            "index_artifact_sha256_after": clean(v3_9_1_summary.get("index_artifact_sha256_after")),
        },
        "xlsx_sourceatom_searchunit_table_axis_materialization": {
            "materialized_in_v3_9_1": False,
            "scope": "overlay_rerank_only",
            "evidence": (
                "v3_9_1 source_registry/index/export hashes stayed unchanged and table_axis_metadata was emitted "
                "inside candidate artifacts, not persisted as canonical SourceAtom/SearchUnit fields."
            ),
            "nonprod_rematerialization_needed_for_next_performance_phase": True,
            "required_before_success_claim": True,
            "proposal_artifacts": {
                "sourceatom_schema": repo_relative(OUTPUTS["proposed_sourceatom_table_axis_schema_json"]),
                "searchunit_fields": repo_relative(OUTPUTS["proposed_searchunit_table_axis_fields_json"]),
                "nonprod_plan": repo_relative(OUTPUTS["proposed_nonprod_rematerialization_plan_json"]),
            },
        },
        "pdf_file_identity_scope": {
            "file_identity_metric_computed": True,
            "answer_ready_evidence_window_metric_computed_in_v3_9_2": False,
            "file_identity_gain_mixed_with_answer_ready_gain": False,
            "movement_interpretation": (
                "file@1 moved by +1, file@3 and abstain stayed unchanged, and wrong-file block increased. "
                "This is a tradeoff-prone file identity movement, not an answer-ready evidence-window gain."
            ),
            "gain_case_rows": [
                row
                for row in pdf_delta_rows
                if row.get("delta_type") == "pdf_file_at1_gain_case_review"
            ],
        },
        "protected_surface_check": {
            "gold_qrels_labels_expected_supporting_denominator_changed": False,
            "db_or_production_namespace_changed": False,
            "fine_tuning_executed": False,
            "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        },
    }


def proposed_sourceatom_schema() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_proposed_sourceatom_table_axis_schema_v1",
        "run_id": RUN_ID,
        "proposal_only": True,
        "diagnostic_only": True,
        "production_namespace_allowed": False,
        "fields": {
            "table_block_id": "stable synthetic or parser-derived id for a logical table block",
            "table_range": "bounded A1-style range for XLSX table atoms",
            "header_rows": "row indexes or spans that define column headers",
            "header_columns": "column indexes or spans that define row headers",
            "merged_cell_header_propagation": "propagated parent header labels with source cell provenance",
            "row_label_aliases_sha256": "hashed row label aliases, never raw target values for scoring",
            "column_label_aliases_sha256": "hashed column label aliases",
            "parent_header_path_sha256": "hashed multi-row or multi-column header paths",
            "unit_date_number_normalized_tokens": "bounded normalized date/number/unit tokens for locator search",
            "sparse_table_boundary": "detected table boundary and blank-density summary",
        },
        "forbidden_fields": [
            "expected_answer",
            "supporting_evidence",
            "gold_label",
            "qrels",
            "pass_fail",
            "raw_answer_value_for_query_scoring",
        ],
    }


def proposed_searchunit_fields() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_proposed_searchunit_table_axis_fields_v1",
        "run_id": RUN_ID,
        "proposal_only": True,
        "diagnostic_only": True,
        "fields": {
            "table_axis_bm25_text": "header/row/column/table context text, excluding expected/supporting/gold text",
            "table_axis_embedding_text": "bounded locator-rich text for non-prod diagnostic index rebuild",
            "table_axis_debug_text": "redacted source-local diagnostics for audit only",
            "table_block_id": "join key to SourceAtom table block",
            "header_path_hashes": "hashes for parent header path matching",
            "row_column_alias_hashes": "hashes for row and column aliases",
            "table_shape_summary": "row/column counts and sparse density",
        },
        "candidate_only_until_hydrated": True,
        "canonical_truth_owner": "SourceAtom/source_registry after explicit non-prod rematerialization",
    }


def proposed_nonprod_rematerialization_plan() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_proposed_nonprod_rematerialization_plan_v1",
        "run_id": RUN_ID,
        "proposal_only": True,
        "diagnostic_only": True,
        "allowed_namespace": "rag-data-xlsx-table-axis-ood-nonprod-v1",
        "blocked_namespaces": [
            "rag-data-official-denominator-v1",
            "rag-data-all-source-citable-nonprod-v1",
            "production",
        ],
        "steps": [
            "materialize table-axis SourceAtom/SearchUnit fields into a new non-prod registry/export only",
            "build a new non-prod index from the rematerialized export",
            "run fresh synthetic OOD anti-overfit guard and any later real unseen holdout separately",
            "compare against v3_9_1 only as diagnostic, never promotion or winner selection",
        ],
        "guards": [
            "official_metric_input_rows stays 0",
            "gold/qrels/labels/expected/supporting/denominator stay unchanged",
            "no direct normalized-value query matching",
            "no source/file title leak success evidence",
            "no DB/prod namespace writes",
        ],
    }


def build_metrics(
    *,
    overfit_rows: Sequence[Mapping[str, Any]],
    seen_manifest: Mapping[str, Any],
    candidate_manifest: Mapping[str, Any],
    split_manifest: Mapping[str, Any],
    architecture: Mapping[str, Any],
) -> dict[str, Any]:
    labels = overfit_label_counts(overfit_rows)
    preserve = [
        {
            "signal": "v3_9_1_xlsx_table_axis_overlay_direction",
            "preservation": "diagnostic_direction_only",
            "future_success_evidence": False,
            "reason": "Small seen-surface movement with remaining 257/300 rank1 locator_signal_count=0.",
        },
        {
            "signal": "v3_9_pdf_answer_ready_window",
            "preservation": "architecture_evidence_window_signal_only",
            "future_success_evidence": False,
            "reason": "Answer-ready evidence-window gain is separate from file identity and comes from repeated seen validation.",
        },
        {
            "signal": "v3_9_1_pdf_file_identity_file_at1_plus_one",
            "preservation": "weak_tradeoff_signal_only",
            "future_success_evidence": False,
            "reason": "file@1 +1 accompanies unchanged file@3/abstain and wrong-file block movement.",
        },
    ]
    degrade = [
        "v3_8_3/v3_9/v3_9_1 validation rows are now seen-validation-only.",
        "Leakage-adjacent or query-fidelity-excluded improvements are excluded from headline success evidence.",
        "Synthetic OOD holdout is anti-overfit guard only, not product success evidence.",
    ]
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": "DIAGNOSTIC_V3_9_2_OVERFIT_RISK_AUDIT_AND_BLIND_HOLDOUT_RESET_READY",
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "fine_tuning_executed": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "direct_normalized_value_query_matching_used": False,
        "answer_value_in_query_success_evidence_used": False,
        "index_to_content_success_evidence_used": False,
        "file_or_source_title_leak_success_evidence_used": False,
        "overfit_risk_label_counts": labels,
        "delta_row_count": len(overfit_rows),
        "future_success_evidence_preservation": preserve,
        "seen_validation_downgrade": degrade,
        "fresh_holdout": {
            "real_unseen_holdout_sufficient": seen_manifest["real_unseen_holdout_sufficient"],
            "real_unseen_counts": seen_manifest["real_unseen_counts"],
            "synthetic_ood_candidate_count": candidate_manifest["candidate_count"],
            "headline_candidate_count": split_manifest["headline_candidate_count"],
            "product_success_evidence_allowed": False,
            "anti_overfit_guard_allowed": True,
        },
        "architecture_scope": {
            "xlsx_overlay_only": architecture["xlsx_sourceatom_searchunit_table_axis_materialization"]["scope"]
            == "overlay_rerank_only",
            "xlsx_nonprod_rematerialization_needed": architecture["xlsx_sourceatom_searchunit_table_axis_materialization"][
                "nonprod_rematerialization_needed_for_next_performance_phase"
            ],
            "pdf_file_identity_answer_window_kept_separate": not architecture["pdf_file_identity_scope"][
                "file_identity_gain_mixed_with_answer_ready_gain"
            ],
        },
    }


def build_failure_taxonomy(
    *,
    overfit_rows: Sequence[Mapping[str, Any]],
    v3_9_1_metrics: Mapping[str, Any],
    seen_manifest: Mapping[str, Any],
    split_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    label_counts = overfit_label_counts(overfit_rows)
    v391_failure = as_mapping(v3_9_1_metrics.get("failure_taxonomy"))
    return {
        "schema_version": f"{RUN_ID}_failure_taxonomy_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "overfit_risk_label_counts": label_counts,
        "primary_failure_modes": {
            "insufficient_blind_evidence": "Existing validation is seen after repeated loop exposure.",
            "metric_tradeoff": "XLSX table/range@3 regressions and PDF wrong-file block movement limit interpretation.",
            "leakage_adjacent": "Source/file-title and answer-value adjacency cannot be success evidence.",
            "scorer_surface_overfit": "Small v3_9 answer-quality deltas depend on query-fidelity and repeated LLM scoring surface.",
            "fresh_real_holdout_shortage": seen_manifest["real_unseen_insufficiency_reason"],
        },
        "v3_9_1_xlsx_failure_taxonomy": as_mapping(v391_failure.get("xlsx")),
        "v3_9_1_pdf_file_identity_taxonomy": as_mapping(v391_failure.get("pdf_file_identity")),
        "fresh_holdout_failure_taxonomy": {
            "real_unseen_holdout_sufficient": False,
            "synthetic_ood_guard_used": True,
            "query_fidelity_excluded_rows_retained": True,
            "headline_candidate_count": split_manifest["headline_candidate_count"],
        },
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    seen_manifest: Mapping[str, Any],
    candidate_manifest: Mapping[str, Any],
    split_manifest: Mapping[str, Any],
    architecture: Mapping[str, Any],
    failure_taxonomy: Mapping[str, Any],
    input_paths: Mapping[str, Path],
) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_summary_v1",
        "run_id": RUN_ID,
        "generated_at": utc_timestamp(),
        "status": metrics["status"],
        "event_type": "diagnostic_v3_9_2_overfit_risk_audit_and_blind_holdout_reset",
        "run_class": "diagnostic_only_overfit_risk_audit_and_blind_holdout_reset",
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "fine_tuning_executed": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "staging_or_commit_performed": False,
        "direct_normalized_value_query_matching_used": False,
        "answer_value_in_query_success_evidence_used": False,
        "index_to_content_success_evidence_used": False,
        "file_or_source_title_leak_success_evidence_used": False,
        "source_identity_success_evidence_used": False,
        "input_artifacts": {name: repo_relative(path) for name, path in input_paths.items()},
        "artifact_paths": {name: repo_relative(path) for name, path in OUTPUTS.items()},
        "seen_validation_is_strong_blind_validation": False,
        "seen_validation_downgraded_to_seen_validation_only": True,
        "generalizable_signal_conclusion": (
            "No v3_9_1 metric improvement is preserved as future success evidence. The best preserved signal is "
            "diagnostic direction: XLSX likely needs real SourceAtom/SearchUnit table-axis rematerialization and PDF "
            "file identity must be evaluated separately from answer-ready evidence windows."
        ),
        "fresh_holdout_sufficient": False,
        "fresh_holdout_status": {
            "real_unseen_holdout_sufficient": seen_manifest["real_unseen_holdout_sufficient"],
            "synthetic_ood_guard_used": candidate_manifest["synthetic_ood_fixture_created"],
            "synthetic_product_success_evidence_allowed": False,
            "headline_candidate_count": split_manifest["headline_candidate_count"],
        },
        "xlsx_architecture_conclusion": architecture["xlsx_sourceatom_searchunit_table_axis_materialization"],
        "pdf_architecture_conclusion": architecture["pdf_file_identity_scope"],
        "performance_phase_recommendation": (
            "Pause success-claiming performance work until real fresh blind/OOD holdout exists. It is acceptable "
            "to continue diagnostic-only non-prod XLSX rematerialization proposals and synthetic OOD anti-overfit guards."
        ),
        "metrics_summary": {
            "overfit_risk_label_counts": metrics["overfit_risk_label_counts"],
            "delta_row_count": metrics["delta_row_count"],
            "fresh_holdout": metrics["fresh_holdout"],
        },
        "failure_taxonomy_summary": failure_taxonomy["primary_failure_modes"],
        "artifact_sha256": {},
    }


def append_unique_status_event(event: Mapping[str, Any]) -> None:
    existing: list[dict[str, Any]] = []
    if STATUS_JSONL.exists():
        existing = read_jsonl(STATUS_JSONL)
    filtered = [
        row
        for row in existing
        if not (row.get("run_id") == RUN_ID and row.get("event_type") == event.get("event_type"))
    ]
    filtered.append(dict(event))
    write_jsonl(STATUS_JSONL, filtered)


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"Last updated: [^.]+\.", "Last updated: 2026-05-24 KST.", text, count=1)
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


def update_docs(summary: Mapping[str, Any], metrics: Mapping[str, Any]) -> None:
    run_id = summary["run_id"]
    fresh = as_mapping(metrics.get("fresh_holdout"))
    label_counts = as_mapping(metrics.get("overfit_risk_label_counts"))
    progress_entry = f"""- v3_9_2 overfit-risk audit and blind/OOD holdout reset (`{run_id}`) downgrades the repeated v3_8_3/v3_9/v3_9_1 validation surface to seen-validation-only. Real unseen PDF/XLSX source coverage is insufficient (PDF document-disjoint=0, XLSX workbook-disjoint=0), so the new holdout manifest is synthetic OOD anti-overfit guard only, not product success evidence. XLSX remains overlay/rerank-only and needs a non-prod SourceAtom/SearchUnit table-axis rematerialization before the next performance-success claim; PDF file identity is kept separate from answer-ready evidence windows. official_metric_input_rows=0, future scored adapter disabled, no fine-tuning, no gold/qrels/labels/expected/supporting/denominator/prod mutation."""
    measurements_entry = f"""## 2026-05-24 - v3_9_2 Overfit Risk Audit and Blind/OOD Holdout Reset

Run ID: `{run_id}`.

Scope:

- Diagnostic-only audit over v3_8_3, v3_9, and v3_9_1 artifacts.
- `official_metric_input_rows=0`; future scored adapter remains `DISABLED_PENDING_USER_APPROVAL`.
- Existing validation rows are now seen-validation-only and cannot be future success evidence.
- Fresh real holdout is insufficient: PDF source-document-disjoint `{fresh.get('real_unseen_counts', {}).get('PDF_source_document_disjoint', 0)}`, XLSX workbook-disjoint `{fresh.get('real_unseen_counts', {}).get('XLSX_workbook_disjoint', 0)}`.

Key counts:

| Item | Count |
|---|---:|
| overfit delta rows | {metrics.get('delta_row_count', 0)} |
| insufficient_blind_evidence labels | {label_counts.get('insufficient_blind_evidence', 0)} |
| metric_tradeoff labels | {label_counts.get('metric_tradeoff', 0)} |
| synthetic OOD guard candidates | {fresh.get('synthetic_ood_candidate_count', 0)} |
| headline synthetic OOD guard rows | {fresh.get('headline_candidate_count', 0)} |

Conclusion: no v3_9_1 improvement is preserved as future product success evidence. The useful retained signal is diagnostic direction: XLSX needs non-prod table-axis rematerialization, while PDF file identity must be evaluated separately from answer-ready evidence-window quality."""
    triage_entry = f"""## v3_9_2 Overfit Risk and Holdout Reset Triage

Run ID: `{run_id}`.

Triage result:

- `likely_general` future-success evidence count is `{label_counts.get('likely_general', 0)}`.
- `weak_general` rows are retained as diagnostic direction only and are also marked insufficient-blind-evidence.
- Leakage-adjacent, query-fidelity-excluded, source/file-title, answer-value-in-query, and index-to-content rows are excluded from success evidence.
- The new synthetic OOD holdout is an anti-overfit guard only; it must not be used for representative product performance.

Next boundary:

- Pause performance success claims until real fresh blind/OOD PDF/XLSX sources are available.
- Continue only diagnostic-only proposal work for a new non-prod XLSX table-axis SourceAtom/SearchUnit rematerialization.
- Keep PDF file identity and PDF answer-ready evidence-window metrics separate."""
    replace_marked_entry(PROGRESS_DOC, f"{run_id}:progress-entry", progress_entry)
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        "Overall status: `diagnostic_v3_9_2_overfit_risk_audit_holdout_reset_ready`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")
    replace_marked_entry(MEASUREMENTS_DOC, f"{run_id}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{run_id}:triage-entry", triage_entry)


def build_artifacts() -> dict[str, Any]:
    input_paths = {
        "v3_8_2_per_query_jsonl": V3_8_2_PER_QUERY,
        "v3_8_3_metrics_json": V3_8_3_METRICS,
        "v3_8_3_per_query_jsonl": V3_8_3_PER_QUERY,
        "v3_9_metrics_json": V3_9_METRICS,
        "v3_9_per_query_jsonl": V3_9_PER_QUERY,
        "v3_9_query_fidelity_jsonl": V3_9_QUERY_FIDELITY,
        "v3_9_1_summary_json": V3_9_1_SUMMARY,
        "v3_9_1_metrics_json": V3_9_1_METRICS,
        "v3_9_1_per_query_jsonl": V3_9_1_PER_QUERY,
        "v3_9_1_query_fidelity_jsonl": V3_9_1_QUERY_FIDELITY,
        "v3_9_1_split_manifest_json": V3_9_1_SPLIT,
        "source_registry_jsonl": SOURCE_REGISTRY_JSONL,
    }
    missing = [repo_relative(path) for path in input_paths.values() if not artifact_exists(path)]
    if missing:
        raise FileNotFoundError("missing required v3_9_2 input artifacts: " + ", ".join(missing))

    registry_rows = load_registry_pdf_xlsx()
    v3_8_2_rows = read_jsonl(V3_8_2_PER_QUERY)
    v3_8_3_rows = read_jsonl(V3_8_3_PER_QUERY)
    v3_9_rows = read_jsonl(V3_9_PER_QUERY)
    v3_9_1_rows = read_jsonl(V3_9_1_PER_QUERY)
    v3_9_1_fidelity = read_jsonl(V3_9_1_QUERY_FIDELITY)
    v3_9_1_summary = read_json(V3_9_1_SUMMARY)
    v3_9_1_metrics = read_json(V3_9_1_METRICS)
    v3_9_1_split = read_json(V3_9_1_SPLIT)

    seen_manifest = build_seen_surface_manifest(
        registry_rows=registry_rows,
        v3_8_3_rows=v3_8_3_rows,
        v3_9_rows=v3_9_rows,
        v3_9_1_rows=v3_9_1_rows,
    )
    candidate_manifest = build_fresh_holdout_candidate_manifest(seen_manifest)
    fresh_query_fidelity = build_query_fidelity_audit(candidate_manifest["candidates"])
    split_manifest = build_fresh_holdout_split_manifest(candidate_manifest, fresh_query_fidelity)
    overfit_rows = build_overfit_delta_rows(
        v3_8_2_rows=v3_8_2_rows,
        v3_9_rows=v3_9_rows,
        v3_9_1_rows=v3_9_1_rows,
        v3_9_1_metrics=v3_9_1_metrics,
        v3_9_1_split=v3_9_1_split,
    )
    pdf_delta_rows = [
        row
        for row in overfit_rows
        if clean(row.get("delta_type")).startswith("pdf_")
        or clean(row.get("source_family")).upper() == "PDF"
    ]
    architecture = build_architecture_scope_assessment(v3_9_1_summary, pdf_delta_rows)
    leakage_audit = build_leakage_audit(
        v3_9_rows=v3_9_rows,
        v3_9_1_fidelity=v3_9_1_fidelity,
        fresh_fidelity=fresh_query_fidelity,
    )
    metrics = build_metrics(
        overfit_rows=overfit_rows,
        seen_manifest=seen_manifest,
        candidate_manifest=candidate_manifest,
        split_manifest=split_manifest,
        architecture=architecture,
    )
    failure_taxonomy = build_failure_taxonomy(
        overfit_rows=overfit_rows,
        v3_9_1_metrics=v3_9_1_metrics,
        seen_manifest=seen_manifest,
        split_manifest=split_manifest,
    )
    summary = build_summary(
        metrics=metrics,
        seen_manifest=seen_manifest,
        candidate_manifest=candidate_manifest,
        split_manifest=split_manifest,
        architecture=architecture,
        failure_taxonomy=failure_taxonomy,
        input_paths=input_paths,
    )
    return {
        "summary": summary,
        "metrics": metrics,
        "overfit_rows": overfit_rows,
        "seen_manifest": seen_manifest,
        "candidate_manifest": candidate_manifest,
        "split_manifest": split_manifest,
        "query_fidelity_rows": fresh_query_fidelity,
        "leakage_audit_rows": leakage_audit,
        "architecture": architecture,
        "failure_taxonomy": failure_taxonomy,
        "proposed_sourceatom_schema": proposed_sourceatom_schema(),
        "proposed_searchunit_fields": proposed_searchunit_fields(),
        "proposed_nonprod_rematerialization_plan": proposed_nonprod_rematerialization_plan(),
    }


def write_artifacts(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    write_json(OUTPUTS["metrics_json"], artifacts["metrics"])
    write_jsonl(OUTPUTS["overfit_risk_by_delta_jsonl"], artifacts["overfit_rows"])
    write_json(OUTPUTS["seen_surface_manifest_json"], artifacts["seen_manifest"])
    write_json(OUTPUTS["fresh_holdout_candidate_manifest_json"], artifacts["candidate_manifest"])
    write_json(OUTPUTS["fresh_holdout_split_manifest_json"], artifacts["split_manifest"])
    write_jsonl(OUTPUTS["query_fidelity_audit_jsonl"], artifacts["query_fidelity_rows"])
    write_jsonl(OUTPUTS["leakage_audit_jsonl"], artifacts["leakage_audit_rows"])
    write_json(OUTPUTS["architecture_scope_assessment_json"], artifacts["architecture"])
    write_json(OUTPUTS["failure_taxonomy_json"], artifacts["failure_taxonomy"])
    write_json(OUTPUTS["proposed_sourceatom_table_axis_schema_json"], artifacts["proposed_sourceatom_schema"])
    write_json(OUTPUTS["proposed_searchunit_table_axis_fields_json"], artifacts["proposed_searchunit_fields"])
    write_json(OUTPUTS["proposed_nonprod_rematerialization_plan_json"], artifacts["proposed_nonprod_rematerialization_plan"])

    summary = dict(artifacts["summary"])
    summary["artifact_sha256"] = {
        key.replace("_jsonl", "").replace("_json", "") + "_sha256": sha256_file(path)
        for key, path in OUTPUTS.items()
        if key != "summary_json"
    }
    write_json(OUTPUTS["summary_json"], summary)
    update_docs(summary, artifacts["metrics"])

    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": summary["event_type"],
        "status": summary["status"],
        "generated_at": utc_timestamp(),
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "fine_tuning_executed": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "seen_validation_downgraded_to_seen_validation_only": True,
        "fresh_holdout_sufficient": False,
        "real_unseen_holdout_sufficient": False,
        "synthetic_ood_guard_used": True,
        "product_success_evidence_allowed": False,
        "xlsx_nonprod_rematerialization_needed": True,
        "pdf_file_identity_answer_window_kept_separate": True,
        "artifact_paths": {name: repo_relative(path) for name, path in OUTPUTS.items()},
        "artifact_sha256": {**summary["artifact_sha256"], "summary_json_sha256": sha256_file(OUTPUTS["summary_json"])},
    }
    append_unique_status_event(event)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build v3_9_2 overfit-risk audit and blind/OOD holdout reset artifacts.")
    parser.add_argument("--check", action="store_true", help="Build artifacts in memory without writing files.")
    args = parser.parse_args(argv)
    artifacts = build_artifacts()
    if args.check:
        print(json.dumps({"run_id": RUN_ID, "status": artifacts["summary"]["status"]}, ensure_ascii=False))
        return 0
    summary = write_artifacts(artifacts)
    print(json.dumps({"run_id": RUN_ID, "status": summary["status"], "summary": repo_relative(OUTPUTS["summary_json"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
