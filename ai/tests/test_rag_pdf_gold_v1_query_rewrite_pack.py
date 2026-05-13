from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_pdf_gold_v1_query_rewrite_pack.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rewrite = load_module(SCRIPT_PATH, "rag_pdf_gold_v1_query_rewrite_pack_for_tests")


def test_pdf_gold_v1_rewrite_keeps_bindings_and_replaces_query_surface(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    source_before = paths["source_gold"].read_text(encoding="utf-8")

    summary = rewrite.run_pdf_gold_v1_query_rewrite(**paths)
    output_rows = read_csv(paths["output_gold"])
    lineage_rows = read_csv(paths["lineage_path"])

    assert summary["status"] == "NEEDS_USER_REVIEW"
    assert summary["promotion_evidence"] is False
    assert summary["evidence_role"] == "diagnostic"
    assert summary["official_denominator_changed"] is False
    assert summary["retrieval_run"] is False
    assert summary["indexing_run"] is False
    assert summary["live_llm_run"] is False
    assert summary["old_query_surface_metrics"]["exact_keyword_like_count"] == 2
    assert summary["new_query_surface_metrics"]["exact_keyword_like_count"] == 0
    assert len(output_rows) == 2
    assert len(lineage_rows) == 2
    assert output_rows[0]["query"] == "최근 경제동향 2025년 12월호 표지 제목 확인"
    assert output_rows[0]["expected_page_no"] == "1"
    assert output_rows[0]["expected_bbox"] == "[1,2,3,4]"
    assert output_rows[0]["label_status"] == "bound"
    assert "pdf_v1_manual_query_rewrite" in output_rows[0]["notes"]
    assert lineage_rows[0]["user_review_required"] == "true"
    assert lineage_rows[0]["user_query_surface_decision"] == ""
    assert paths["source_gold"].read_text(encoding="utf-8") == source_before
    assert json.loads(paths["summary_path"].read_text(encoding="utf-8"))["gold_v0_modified"] is False


def test_pdf_gold_v1_rewrite_fails_closed_if_output_would_overwrite_source(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    source_before = paths["source_gold"].read_text(encoding="utf-8")

    summary = rewrite.run_pdf_gold_v1_query_rewrite(
        **{
            **paths,
            "output_gold": paths["source_gold"],
        }
    )

    assert summary["status"] == "NEEDS_REVIEW"
    assert any("must not overwrite" in blocker for blocker in summary["blockers"])
    assert paths["source_gold"].read_text(encoding="utf-8") == source_before


def test_pdf_gold_v1_rewrite_requires_complete_manual_map(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path, include_unmapped=True)

    summary = rewrite.run_pdf_gold_v1_query_rewrite(**paths)

    assert summary["status"] == "NEEDS_REVIEW"
    assert any("manual rewrite map missing query ids" in blocker for blocker in summary["blockers"])
    assert not paths["output_gold"].exists()


def write_fixture_bundle(tmp_path: Path, *, include_unmapped: bool = False) -> dict[str, Path]:
    source_gold = tmp_path / "gold_queries_pdf_v0.csv"
    output_gold = tmp_path / "gold_queries_pdf_v1_review_draft.csv"
    c7_pack = tmp_path / "rag_pdf_c7_decision_pack.csv"
    c7_summary = tmp_path / "rag_pdf_c7_decision_pack_summary.json"
    summary_path = tmp_path / "rag_pdf_gold_v1_review_draft_report.json"
    lineage_path = tmp_path / "pdf_gold_v1_review_draft_pack.csv"
    guide_path = tmp_path / "pdf_gold_v1_review_draft_guide.md"

    rows = [
        pdf_row("gq_pdf_page_lookup_001", "pdf_page_lookup", "최 근 경 제 동 향", "최근 경제 동향 표지", "최 근 경 제 동 향", "1"),
        pdf_row("gq_pdf_table_lookup_002", "pdf_table_lookup", "518.4", "2024 수출입차 값", "518.4;2024", "61"),
    ]
    if include_unmapped:
        rows.append(pdf_row("unmapped_pdf_row", "pdf_page_lookup", "기간중", "기간중", "기간중", "2"))
    write_csv(source_gold, rows, rewrite.REQUIRED_GOLD_COLUMNS)
    write_csv(
        c7_pack,
        [
            {
                "decision_group": "table_gold_policy_review_required",
                "query_id": "gq_pdf_table_lookup_002",
                "c7_primary_classification": "table_gold_policy_review_required",
                "c7_secondary_classifications": "diagnostic_only_exclude_candidate",
            }
        ],
        [
            "decision_group",
            "query_id",
            "c7_primary_classification",
            "c7_secondary_classifications",
        ],
    )
    c7_summary.write_text(
        json.dumps(
            {
                "status": "NEEDS_USER_DECISION",
                "promotion_evidence": False,
                "evidence_role": "diagnostic",
                "human_decision_required_count": 1,
                "matched_positive_control_count": 1,
            }
        ),
        encoding="utf-8",
    )
    return {
        "source_gold": source_gold,
        "output_gold": output_gold,
        "c7_pack": c7_pack,
        "c7_summary": c7_summary,
        "summary_path": summary_path,
        "lineage_path": lineage_path,
        "guide_path": guide_path,
    }


def pdf_row(
    query_id: str,
    bucket: str,
    query: str,
    expected_answer_text: str,
    must_contain_terms: str,
    page_no: str,
) -> dict[str, str]:
    return {
        column: ""
        for column in rewrite.REQUIRED_GOLD_COLUMNS
    } | {
        "query_id": query_id,
        "bucket": bucket,
        "query": query,
        "expected_file_name": "sample.pdf",
        "expected_document_version_id": "docv_pdf",
        "expected_chunk_type": "paragraph",
        "expected_location_type": "pdf",
        "expected_physical_page_index": str(int(page_no) - 1),
        "expected_page_no": page_no,
        "expected_page_label": page_no,
        "expected_bbox": "[1,2,3,4]",
        "expected_answer_text": expected_answer_text,
        "must_contain_terms": must_contain_terms,
        "range_match_policy": "none",
        "requires_formula_value": "false",
        "requires_formatted_value": "false",
        "requires_aggregation": "false",
        "source_sample_id": "fixture",
        "label_status": "bound",
        "notes": "fixture row",
    }


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))
