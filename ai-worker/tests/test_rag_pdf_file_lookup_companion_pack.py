from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "ai-worker" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


companion = load_module("rag_pdf_file_lookup_companion_pack")


def test_file_lookup_companion_row_counts_and_lane_balance(tmp_path: Path):
    source_csv = copy_manual_v1(tmp_path)

    report = companion.build_file_lookup_pack(
        source_csv=source_csv,
        output_dir=tmp_path / "review",
        report_dir=tmp_path / "reports",
    )

    assert report["status"] == "PASS"
    assert 25 <= report["companion_row_count"] <= 30
    assert report["companion_row_count"] == 28
    assert report["content_anchor_count"] == 21
    assert report["metadata_count"] == 7
    assert report["content_anchor_count"] > report["metadata_count"]
    assert report["merged_row_count"] == 108

    rows = read_csv(tmp_path / "review" / companion.COMPANION_CSV_NAME)
    assert len(rows) == report["companion_row_count"]
    assert count_lane(rows, companion.CONTENT_LANE) == 21
    assert count_lane(rows, companion.METADATA_LANE) == 7


def test_file_lookup_user_columns_blank_and_source_not_overwritten(tmp_path: Path):
    source_csv = copy_manual_v1(tmp_path)
    before = source_csv.read_bytes()

    companion.build_file_lookup_pack(
        source_csv=source_csv,
        output_dir=tmp_path / "review",
        report_dir=tmp_path / "reports",
    )

    assert source_csv.read_bytes() == before
    companion_rows = read_csv(tmp_path / "review" / companion.COMPANION_CSV_NAME)
    merged_rows = read_csv(tmp_path / "review" / companion.MERGED_CSV_NAME)
    for row in [*companion_rows, *merged_rows]:
        for column in companion.USER_COLUMNS:
            assert row[column] == ""


def test_file_lookup_rows_do_not_require_page_bbox_or_table_success(tmp_path: Path):
    source_csv = copy_manual_v1(tmp_path)

    companion.build_file_lookup_pack(
        source_csv=source_csv,
        output_dir=tmp_path / "review",
        report_dir=tmp_path / "reports",
    )

    rows = read_csv(tmp_path / "review" / companion.COMPANION_CSV_NAME)
    summary = json.loads((tmp_path / "reports" / companion.SUMMARY_NAME).read_text(encoding="utf-8"))

    assert summary["file_lookup_rows_require_page_success"] is False
    assert summary["file_lookup_rows_require_bbox_success"] is False
    assert summary["file_lookup_rows_require_table_value_success"] is False
    assert summary["bbox_contract_success_not_claimed"] is True
    assert summary["table_semantics_success_claimed"] is False
    assert summary["row_column_value_semantics_claimed"] is False
    assert summary["file_lookup_success_claimed"] is False

    for row in rows:
        assert row["suggested_expected_evidence_policy"] == "EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY"
        assert row["suggested_denominator_policy"] == "INCLUDE_FILE_LOOKUP_DENOMINATOR_CANDIDATE"
        assert "NO_PAGE_OR_BBOX_REQUIRED" in row["risk_tags"].split(";")
        assert "table_semantics_success" not in row["risk_tags"].lower()
        assert "row_column_value" not in row["risk_tags"].lower()


def test_existing_outputs_are_not_overwritten(tmp_path: Path):
    source_csv = copy_manual_v1(tmp_path)
    output_dir = tmp_path / "review"
    report_dir = tmp_path / "reports"
    output_dir.mkdir()
    report_dir.mkdir()
    (output_dir / companion.COMPANION_CSV_NAME).write_text("existing", encoding="utf-8")

    with pytest.raises(companion.FileLookupCompanionError, match="Refusing to overwrite existing output"):
        companion.build_file_lookup_pack(
            source_csv=source_csv,
            output_dir=output_dir,
            report_dir=report_dir,
        )


def test_missing_summary_guardrail_key_fails_closed():
    summary = dict(companion.REQUIRED_SUMMARY_GUARDRAILS)
    summary.pop("promotion_evidence")

    with pytest.raises(companion.FileLookupCompanionError, match="Missing summary guardrail"):
        companion.validate_summary_guardrails(summary)


def test_disallowed_table_parent_fails_closed(tmp_path: Path):
    source_csv = copy_manual_v1(tmp_path)
    rows = companion.read_csv(source_csv)
    table_parent = next(row for row in rows if "pdf_review_lane:READY_RESTRICTED_TABLE_CONTEXT" in row["suggested_issue_tags"])

    with pytest.raises(companion.FileLookupCompanionError, match="disallowed lane"):
        companion.companion_row(
            query_id="pdf_file_lookup_content_anchor_999",
            spec={
                "parent_query_id": table_parent["query_id"],
                "retrieval_lane": companion.CONTENT_LANE,
                "query": "표 값으로 파일을 찾는 잘못된 후보",
            },
            parent=table_parent,
        )


def copy_manual_v1(tmp_path: Path) -> Path:
    src = ROOT / "ai-worker" / "eval" / "review" / "pdf_supplemental_gold_review" / "pdf_gold_review_pack_manual_v1.csv"
    assert src.exists(), src
    dst = tmp_path / "pdf_gold_review_pack_manual_v1.csv"
    shutil.copyfile(src, dst)
    return dst


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def count_lane(rows: list[dict[str, str]], lane: str) -> int:
    return sum(1 for row in rows if row["retrieval_lane"] == lane)
