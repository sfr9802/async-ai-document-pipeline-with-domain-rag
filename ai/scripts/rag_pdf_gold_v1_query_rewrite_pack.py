"""Build a manually rewritten PDF gold v1 query pack.

The v1 pack keeps the existing PDF evidence bindings from v0, but replaces
overly literal query surfaces with manually written Korean search-style
queries. It is diagnostic-only and does not promote, retrieve, index, or mutate
the v0 gold CSV.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
EVAL_QUERY_DIR = AI_WORKER_ROOT / "eval" / "eval_queries"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review" / "pdf_gold_v1"

DEFAULT_SOURCE_GOLD = EVAL_QUERY_DIR / "gold_queries_pdf_v0.csv"
DEFAULT_OUTPUT_GOLD = EVAL_QUERY_DIR / "gold_queries_pdf_v1_review_draft.csv"
DEFAULT_C7_PACK = REPORT_DIR / "rag_pdf_c7_decision_pack.csv"
DEFAULT_C7_SUMMARY = REPORT_DIR / "rag_pdf_c7_decision_pack_summary.json"
DEFAULT_SUMMARY = REPORT_DIR / "rag_pdf_gold_v1_review_draft_report.json"
DEFAULT_LINEAGE = REVIEW_DIR / "pdf_gold_v1_review_draft_pack.csv"
DEFAULT_GUIDE = REVIEW_DIR / "pdf_gold_v1_review_draft_guide.md"

REQUIRED_GOLD_COLUMNS = [
    "query_id",
    "bucket",
    "query",
    "expected_file_name",
    "expected_document_version_id",
    "expected_chunk_type",
    "expected_location_type",
    "expected_sheet_name",
    "expected_cell_range",
    "expected_table_id",
    "expected_physical_page_index",
    "expected_page_no",
    "expected_page_label",
    "expected_bbox",
    "expected_answer_text",
    "must_contain_terms",
    "must_not_contain_terms",
    "range_match_policy",
    "hidden_policy",
    "requires_formula_value",
    "requires_formatted_value",
    "requires_aggregation",
    "source_sample_id",
    "label_status",
    "notes",
]

LINEAGE_COLUMNS = [
    "query_id",
    "bucket",
    "source_gold_file",
    "output_gold_file",
    "old_query",
    "new_query",
    "query_generation_method",
    "source_keywords",
    "must_contain_terms",
    "expected_answer_text",
    "expected_file_name",
    "expected_page_no",
    "expected_physical_page_index",
    "expected_bbox",
    "expected_table_id",
    "c7_decision_group",
    "c7_primary_classification",
    "c7_secondary_classifications",
    "v1_query_surface_status",
    "user_review_required",
    "user_query_surface_decision",
    "user_expected_evidence_decision",
    "user_answerability_label",
    "user_relevance_label",
    "user_notes",
    "rewrite_rationale",
    "leakage_check",
]

USER_QUERY_DECISION_OPTIONS = [
    "KEEP_V1_QUERY",
    "REVISE_QUERY",
    "REVISE_EXPECTED_EVIDENCE",
    "RELABEL_NEGATIVE",
    "DEFER",
    "DIAGNOSTIC_ONLY_EXCLUDE",
    "REQUIRE_PARSER_OR_CHUNK_FIX",
]


@dataclass(frozen=True)
class ManualRewrite:
    query: str
    source_keywords: str
    rationale: str


MANUAL_REWRITES: dict[str, ManualRewrite] = {
    "gq_pdf_page_lookup_001": ManualRewrite(
        query="최근 경제동향 2025년 12월호 표지 제목 확인",
        source_keywords="최 근 경 제 동 향;2025. 12.",
        rationale="Turns the cover-title lookup into a natural request with issue context.",
    ),
    "gq_pdf_page_lookup_002": ManualRewrite(
        query="최근 경제동향 2025년 12월호 발행월 표기 찾아줘",
        source_keywords="2025. 12.;발행월",
        rationale="Asks for the cover date as a document field, not only the literal date string.",
    ),
    "gq_pdf_page_lookup_003": ManualRewrite(
        query="부문별 동향 항목이 정리된 목차 페이지 찾아줘",
        source_keywords="목 차;부문별 동향",
        rationale="Uses the table-of-contents role and nearby heading instead of the bare title.",
    ),
    "gq_pdf_section_question_001": ManualRewrite(
        query="수출입 통관 표에서 FOB 수출과 CIF 수입 항목이 함께 나온 부분 찾아줘",
        source_keywords="수 출(FOB);수 입(CIF);수출입 통관",
        rationale="Frames the row as a section/table lookup using the economic context.",
    ),
    "gq_pdf_section_question_002": ManualRewrite(
        query="수입 CIF와 수출입차가 같이 정리된 수출입 통관 표 찾아줘",
        source_keywords="수 입(CIF);수출입차;수출입 통관",
        rationale="Keeps the key terms but asks for the table where they co-occur.",
    ),
    "gq_pdf_section_question_003": ManualRewrite(
        query="2024년 수출액 6,836.1이 적힌 수출입 통관 표 위치 알려줘",
        source_keywords="2024;6,836.1;수출입 통관",
        rationale="Adds the semantic role of the numeric value so the query is not just a number.",
    ),
    "gq_pdf_table_lookup_001": ManualRewrite(
        query="2024년 수출입차가 흑자로 표시된 수출입 통관 표 찾아줘",
        source_keywords="수출입차;518.4;흑자",
        rationale="Queries the meaning of the target value while retaining the table anchor.",
    ),
    "gq_pdf_table_lookup_002": ManualRewrite(
        query="수출입 통관 표에서 2024년 수출입차 518.4 값 확인해줘",
        source_keywords="2024;수출입차;518.4",
        rationale="Makes the value lookup answerable from row and column context.",
    ),
    "gq_auto_009": ManualRewrite(
        query="주요국가 GDP 규모 표의 기간중 헤더가 있는 행 찾아줘",
        source_keywords="주요국가의 GDP규모;기간중",
        rationale="Disambiguates the repeated header by naming the GDP table.",
    ),
    "gq_auto_010": ManualRewrite(
        query="2021년 2월 실업률이 모든 연령계층에서 상승했다는 문장 찾아줘",
        source_keywords="실업률;모든 연령계층;상승",
        rationale="Rephrases the bullet as a user asking for the claim.",
    ),
    "gq_auto_011": ManualRewrite(
        query="주요국가 1인당 GDP 표에서 2018년 행 찾아줘",
        source_keywords="주요국가의 1인당 GDP;2018",
        rationale="Adds table context to the year-only lookup.",
    ),
    "gq_auto_014": ManualRewrite(
        query="주요국가 1인당 GDP 표의 단위가 달러인지 확인해줘",
        source_keywords="주요국가의 1인당 GDP;달러",
        rationale="Turns the unit label into a natural verification request.",
    ),
    "gq_auto_015": ManualRewrite(
        query="국제수지 부분에서 경상수지 추이 그래프 찾아줘",
        source_keywords="경상수지 추이;국제수지",
        rationale="Adds section context to the chart title.",
    ),
    "gq_auto_016": ManualRewrite(
        query="주요국가 1인당 GDP 표에서 2020년 행 찾아줘",
        source_keywords="주요국가의 1인당 GDP;2020",
        rationale="Adds table context to the year-only lookup.",
    ),
    "gq_auto_019": ManualRewrite(
        query="1인당 GDP 표에서 기간중 열 머리글이 있는 부분 찾아줘",
        source_keywords="1인당 GDP;기간중",
        rationale="Disambiguates the repeated header by naming the relevant table.",
    ),
    "gq_auto_020": ManualRewrite(
        query="2월 국제유가가 감산과 미국 한파 영향으로 상승했다는 설명 찾아줘",
        source_keywords="국제유가;원유 감산;미국 한파;상승",
        rationale="Uses the causal claim around the clipped phrase instead of the phrase alone.",
    ),
    "gq_auto_021": ManualRewrite(
        query="국제금리와 원유 가격 표에서 2021년 1월 행 찾아줘",
        source_keywords="국제금리;원유 가격;2021. 1",
        rationale="Adds the table topic to the date lookup.",
    ),
    "gq_auto_024": ManualRewrite(
        query="1월 산업활동에서 광공업과 서비스업 생산 및 건설투자가 감소했다는 문장 찾아줘",
        source_keywords="광공업 생산;서비스업 생산;건설투자;감소",
        rationale="Asks for the summary claim in natural prose.",
    ),
    "gq_auto_025": ManualRewrite(
        query="2021년 3월호 최근 경제동향의 목차 페이지 찾아줘",
        source_keywords="목 차;2021년 3월호",
        rationale="Adds issue context to the table-of-contents lookup.",
    ),
    "gq_auto_026": ManualRewrite(
        query="국제금리 원유 가격 표에서 2020년 Dubai 현물유가 50.23 값을 찾아줘",
        source_keywords="Dubai;현물유가;2020;50.23",
        rationale="Adds row, column, and table semantics to the numeric lookup.",
    ),
    "gq_auto_029": ManualRewrite(
        query="금융시장 종합평가에서 달러강세로 환율이 상승했다는 문장 찾아줘",
        source_keywords="달러강세;환율;상승;종합 평가",
        rationale="Compresses the long clipped sentence into the claim a user would search for.",
    ),
    "gq_auto_030": ManualRewrite(
        query="주요국가의 환율변동 비교 표 찾아줘",
        source_keywords="주요국가의 환율변동 비교;환율",
        rationale="Uses the table title as a natural lookup, not a pasted heading with prefix markers.",
    ),
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run_pdf_gold_v1_query_rewrite(
        source_gold=Path(args.source_gold),
        output_gold=Path(args.output_gold),
        c7_pack=Path(args.c7_pack),
        c7_summary=Path(args.c7_summary),
        summary_path=Path(args.summary),
        lineage_path=Path(args.lineage),
        guide_path=Path(args.guide),
    )
    print(json.dumps(summary_for_stdout(summary), ensure_ascii=False, indent=2))
    return 1 if summary.get("blockers") else 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-gold", default=str(DEFAULT_SOURCE_GOLD))
    parser.add_argument("--output-gold", default=str(DEFAULT_OUTPUT_GOLD))
    parser.add_argument("--c7-pack", default=str(DEFAULT_C7_PACK))
    parser.add_argument("--c7-summary", default=str(DEFAULT_C7_SUMMARY))
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--lineage", default=str(DEFAULT_LINEAGE))
    parser.add_argument("--guide", default=str(DEFAULT_GUIDE))
    return parser.parse_args(argv)


def run_pdf_gold_v1_query_rewrite(
    *,
    source_gold: Path,
    output_gold: Path,
    c7_pack: Path,
    c7_summary: Path,
    summary_path: Path,
    lineage_path: Path,
    guide_path: Path,
) -> dict[str, Any]:
    generated_at = utc_timestamp()
    blockers = entry_blockers(source_gold=source_gold, output_gold=output_gold)
    warnings: list[str] = []
    source_rows = read_csv_if_exists(source_gold)
    c7_rows = read_csv_if_exists(c7_pack)
    c7_by_id = {row.get("query_id", ""): row for row in c7_rows}
    c7_summary_payload = read_json_if_exists(c7_summary)

    missing_rewrites = sorted(
        row.get("query_id", "") for row in source_rows if row.get("query_id", "") not in MANUAL_REWRITES
    )
    extra_rewrites = sorted(set(MANUAL_REWRITES) - {row.get("query_id", "") for row in source_rows})
    if missing_rewrites:
        blockers.append("manual rewrite map missing query ids: " + ", ".join(missing_rewrites))
    if extra_rewrites:
        warnings.append("manual rewrite map has query ids absent from source gold: " + ", ".join(extra_rewrites))

    source_sha_before = sha256(source_gold) if source_gold.exists() else None
    rewritten_rows: list[dict[str, str]] = []
    lineage_rows: list[dict[str, str]] = []
    if not blockers:
        rewritten_rows, lineage_rows = build_rewritten_rows(
            source_rows=source_rows,
            source_gold=source_gold,
            output_gold=output_gold,
            c7_by_id=c7_by_id,
        )

    summary = {
        "status": "NEEDS_USER_REVIEW" if not blockers else "NEEDS_REVIEW",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "generated_at": generated_at,
        "source_gold_csv": describe_source(source_gold),
        "output_gold_csv": repo_relative(output_gold),
        "lineage_review_csv": repo_relative(lineage_path),
        "review_guide": repo_relative(guide_path),
        "c7_pack": describe_source(c7_pack),
        "c7_summary": summarize_c7(c7_summary_payload),
        "row_count": len(rewritten_rows) if not blockers else len(source_rows),
        "old_query_surface_metrics": query_surface_metrics(source_rows),
        "new_query_surface_metrics": query_surface_metrics(rewritten_rows),
        "bucket_counts": dict(Counter(row.get("bucket", "") for row in rewritten_rows)),
        "c7_policy_pending_count": len(c7_rows),
        "matched_positive_control_count": max(0, len(rewritten_rows) - len(c7_rows)),
        "manual_query_rewrite_count": len(rewritten_rows),
        "codex_query_surface_generated": True,
        "codex_gold_policy_decision_applied": False,
        "user_review_required": True,
        "user_query_decision_options": USER_QUERY_DECISION_OPTIONS,
        "gold_v0_modified": False,
        "historical_reports_modified": False,
        "official_denominator_changed": False,
        "retrieval_run": False,
        "indexing_run": False,
        "db_mutation_run": False,
        "live_llm_run": False,
        "optional_judge_run": False,
        "promotion_ready": False,
        "blockers": blockers,
        "warnings": warnings,
        "guardrails": {
            "source_gold_overwritten": False,
            "promotion_execution": False,
            "promotion_evidence_true_generated": False,
            "retrieval_tuning": False,
            "reranking": False,
            "parser_expansion": False,
            "threshold_relaxation": False,
            "broad_indexing": False,
            "candidate_artifact_mutation": False,
            "rag_data_canary_changed": False,
        },
    }

    if not blockers:
        output_gold.parent.mkdir(parents=True, exist_ok=True)
        lineage_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        guide_path.parent.mkdir(parents=True, exist_ok=True)
        write_csv(output_gold, rewritten_rows, REQUIRED_GOLD_COLUMNS)
        write_csv(lineage_path, lineage_rows, LINEAGE_COLUMNS)
        write_json(summary_path, summary)
        write_guide(guide_path, summary)
        source_sha_after = sha256(source_gold) if source_gold.exists() else None
        summary["source_gold_sha256_after_generation"] = source_sha_after
        summary["gold_v0_modified"] = source_sha_before != source_sha_after
        write_json(summary_path, summary)
    else:
        write_json(summary_path, summary)

    return summary


def entry_blockers(*, source_gold: Path, output_gold: Path) -> list[str]:
    blockers: list[str] = []
    if not source_gold.exists():
        blockers.append("missing source PDF v0 gold CSV")
    else:
        rows = read_csv_if_exists(source_gold)
        columns = set(rows[0].keys()) if rows else set()
        missing_columns = [column for column in REQUIRED_GOLD_COLUMNS if column not in columns]
        if missing_columns:
            blockers.append("source PDF v0 gold CSV missing columns: " + ", ".join(missing_columns))
    if source_gold.resolve() == output_gold.resolve():
        blockers.append("output gold path must not overwrite source PDF v0 gold CSV")
    return blockers


def build_rewritten_rows(
    *,
    source_rows: list[dict[str, str]],
    source_gold: Path,
    output_gold: Path,
    c7_by_id: Mapping[str, Mapping[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rewritten_rows: list[dict[str, str]] = []
    lineage_rows: list[dict[str, str]] = []
    for row in source_rows:
        query_id = row.get("query_id", "")
        rewrite = MANUAL_REWRITES[query_id]
        new_row = {column: row.get(column, "") for column in REQUIRED_GOLD_COLUMNS}
        old_query = row.get("query", "")
        new_row["query"] = rewrite.query
        new_row["notes"] = append_note(
            row.get("notes", ""),
            "pdf_v1_manual_query_rewrite; source_gold=gold_queries_pdf_v0.csv; user_review_required=true",
        )
        c7 = c7_by_id.get(query_id, {})
        rewritten_rows.append(new_row)
        lineage_rows.append(
            {
                "query_id": query_id,
                "bucket": row.get("bucket", ""),
                "source_gold_file": repo_relative(source_gold),
                "output_gold_file": repo_relative(output_gold),
                "old_query": old_query,
                "new_query": rewrite.query,
                "query_generation_method": "manual_codex_pdf_page_review_no_llm_call",
                "source_keywords": rewrite.source_keywords,
                "must_contain_terms": row.get("must_contain_terms", ""),
                "expected_answer_text": row.get("expected_answer_text", ""),
                "expected_file_name": row.get("expected_file_name", ""),
                "expected_page_no": row.get("expected_page_no", ""),
                "expected_physical_page_index": row.get("expected_physical_page_index", ""),
                "expected_bbox": row.get("expected_bbox", ""),
                "expected_table_id": row.get("expected_table_id", ""),
                "c7_decision_group": c7.get("decision_group", "matched_positive_control"),
                "c7_primary_classification": c7.get("c7_primary_classification", ""),
                "c7_secondary_classifications": c7.get("c7_secondary_classifications", ""),
                "v1_query_surface_status": "manual_naturalized_needs_user_review",
                "user_review_required": "true",
                "user_query_surface_decision": "",
                "user_expected_evidence_decision": "",
                "user_answerability_label": "",
                "user_relevance_label": "",
                "user_notes": "",
                "rewrite_rationale": rewrite.rationale,
                "leakage_check": leakage_check(rewrite.query),
            }
        )
    return rewritten_rows, lineage_rows


def query_surface_metrics(rows: list[Mapping[str, str]]) -> dict[str, Any]:
    too_short = []
    exact_keyword_like = []
    direct_file_mentions = []
    for row in rows:
        query = row.get("query", "").strip()
        query_id = row.get("query_id", "")
        terms = split_terms(row.get("must_contain_terms", ""))
        expected_answer = row.get("expected_answer_text", "").strip()
        if len(query.replace(" ", "")) < 8 or len(query.split()) < 2:
            too_short.append(query_id)
        if query and (query in terms or query == expected_answer):
            exact_keyword_like.append(query_id)
        if leakage_check(query) != "pass":
            direct_file_mentions.append(query_id)
    return {
        "row_count": len(rows),
        "too_short_or_single_phrase_count": len(too_short),
        "too_short_or_single_phrase_query_ids": too_short,
        "exact_keyword_like_count": len(exact_keyword_like),
        "exact_keyword_like_query_ids": exact_keyword_like,
        "direct_file_name_mention_count": len(direct_file_mentions),
        "direct_file_name_mention_query_ids": direct_file_mentions,
    }


def leakage_check(query: str) -> str:
    lowered = query.lower()
    if ".pdf" in lowered or "recent_economic_trends" in lowered:
        return "direct_file_name_mention"
    return "pass"


def summarize_c7(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "promotion_evidence": payload.get("promotion_evidence"),
        "evidence_role": payload.get("evidence_role"),
        "human_decision_required_count": payload.get("human_decision_required_count"),
        "matched_positive_control_count": payload.get("matched_positive_control_count"),
        "classification_counts": payload.get("classification_counts"),
        "official_denominator_change": payload.get("official_denominator_change"),
    }


def describe_source(path: Path) -> dict[str, Any]:
    descriptor: dict[str, Any] = {
        "path": repo_relative(path),
        "exists": path.exists(),
        "sha256": sha256(path) if path.exists() else None,
    }
    if path.exists() and path.suffix.lower() == ".csv":
        rows = read_csv_if_exists(path)
        descriptor["row_count"] = len(rows)
        descriptor["columns"] = list(rows[0].keys()) if rows else []
    return descriptor


def write_csv(path: Path, rows: list[Mapping[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_guide(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# PDF Gold v1 Query Rewrite Review",
        "",
        "This pack replaces the overly literal PDF v0 query surfaces with manually written Korean search-style queries. Evidence bindings are copied from v0; Codex did not decide PDF table/page/bbox policy or promote any denominator.",
        "",
        "## Files",
        "",
        f"- Gold v1 candidate CSV: `{summary['output_gold_csv']}`",
        f"- Query rewrite review CSV: `{summary['lineage_review_csv']}`",
        f"- Summary JSON: `{repo_relative(DEFAULT_SUMMARY)}`",
        "",
        "## User Review Columns",
        "",
        "Fill these columns in the review CSV if you want to approve or revise the rewrite:",
        "",
        "- `user_query_surface_decision`",
        "- `user_expected_evidence_decision`",
        "- `user_answerability_label`",
        "- `user_relevance_label`",
        "- `user_notes`",
        "",
        "## Decision Options",
        "",
    ]
    lines.extend(f"- `{option}`" for option in USER_QUERY_DECISION_OPTIONS)
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- `promotion_evidence=false`",
            "- `official_denominator_changed=false`",
            "- v0 gold CSV was not overwritten",
            "- no retrieval, indexing, DB mutation, live LLM, optional judge, parser expansion, or reranking was run",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def read_csv_if_exists(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def split_terms(value: str) -> list[str]:
    return [term.strip() for term in value.split(";") if term.strip()]


def append_note(existing: str, note: str) -> str:
    existing = existing.strip()
    return f"{existing}; {note}" if existing else note


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def summary_for_stdout(summary: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": summary.get("status"),
        "output_gold_csv": summary.get("output_gold_csv"),
        "lineage_review_csv": summary.get("lineage_review_csv"),
        "row_count": summary.get("row_count"),
        "old_exact_keyword_like_count": summary.get("old_query_surface_metrics", {}).get(
            "exact_keyword_like_count"
        ),
        "new_exact_keyword_like_count": summary.get("new_query_surface_metrics", {}).get(
            "exact_keyword_like_count"
        ),
        "promotion_evidence": summary.get("promotion_evidence"),
        "official_denominator_changed": summary.get("official_denominator_changed"),
        "blockers": summary.get("blockers"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
