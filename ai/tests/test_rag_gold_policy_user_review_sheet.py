from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_gold_policy_user_review_sheet.py"


XLSX_PENDING_IDS = ["gq_xlsx_date_number_format_003", "gq_xlsx_aggregation_001"]
PDF_PENDING_IDS = [
    "pdf_file_lookup_content_anchor_017",
    "pdf_file_lookup_content_anchor_018",
    "pdf_file_lookup_content_anchor_020",
]
PDF_EXCLUDE_IDS = [
    "pdf_file_lookup_content_anchor_004",
    "pdf_file_lookup_content_anchor_012",
    "pdf_file_lookup_content_anchor_013",
    "pdf_file_lookup_content_anchor_014",
    "pdf_file_lookup_content_anchor_015",
    "pdf_file_lookup_metadata_002",
]


def load_module():
    spec = importlib.util.spec_from_file_location("rag_gold_policy_user_review_sheet", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_review_sheet_contains_actionable_rows_and_batch_sections(tmp_path: Path):
    module = load_module()
    draft = fixture_draft(module)
    pdf_rows = {row["query_id"]: row for row in fixture_pdf_rows()}

    sheet = module.render_review_sheet(draft, pdf_rows=pdf_rows)

    assert "## XLSX Pending Evidence Rows" in sheet
    assert "## PDF Pending File-Identity Rows" in sheet
    assert "## Batch Confirmation: XLSX Include Candidates" in sheet
    assert "## Batch Confirmation: PDF Exclude Candidates" in sheet
    assert "## TEXT/Namu Carry-Forward" in sheet
    for query_id in XLSX_PENDING_IDS + PDF_PENDING_IDS + PDF_EXCLUDE_IDS:
        assert query_id in sheet
    assert "사용자재와 장비가 모두 신품이고 설계도서 요구에 맞아야 한다는 기준 찾아줘" in sheet
    assert "confirm expected evidence" in sheet
    assert "decide whether stable document identity is required" in sheet
    assert "final denominator membership" in sheet
    assert "no retrieval variants" in sheet


def test_main_writes_sheet_without_registry_mutation(tmp_path: Path):
    module = load_module()
    draft_path = tmp_path / "draft.json"
    pdf_csv = tmp_path / "pdf.csv"
    registry = tmp_path / "official_denominator_registry.json"
    output_md = tmp_path / "sheet.md"
    draft_path.write_text(json.dumps(fixture_draft(module), ensure_ascii=False) + "\n", encoding="utf-8")
    write_pdf_csv(pdf_csv)
    registry.write_text(json.dumps({"schema_version": "official_denominator_registry_v1"}) + "\n", encoding="utf-8")
    before = registry.read_text(encoding="utf-8")

    result = module.main(
        [
            "--draft-json",
            str(draft_path),
            "--pdf-review-csv",
            str(pdf_csv),
            "--official-denominator-registry",
            str(registry),
            "--output-md",
            str(output_md),
        ]
    )

    assert result == 0
    assert output_md.exists()
    assert registry.read_text(encoding="utf-8") == before


def test_validate_sheet_inputs_rejects_wrong_counts():
    module = load_module()
    draft = fixture_draft(module)
    draft["xlsx_draft_decisions"] = draft["xlsx_draft_decisions"][:-1]

    assert module.validate_sheet_inputs(draft) is False


def fixture_draft(module) -> dict:
    xlsx_include_ids = [f"gq_include_{index:03d}" for index in range(23)]
    text_ids = [f"text_namu_v2_{index:04d}" for index in range(1, 24)]
    return {
        "status": "PASS",
        "source_resolution_packet": {"json_path": "ai/eval/review/rag_gold_policy_resolution_packet_v1.json"},
        "guardrail_status": {
            "official_denominator_registry_changed": False,
            "retrieval_variants_run": False,
            "production_namespace_mutated": False,
            "diagnostic_only_row_promoted": False,
            "pdf_content_and_file_identity_aggregated": False,
        },
        "xlsx_draft_decisions": [
            xlsx_row(module, query_id, module.XLSX_PENDING_EVIDENCE_DECISION) for query_id in XLSX_PENDING_IDS
        ]
        + [xlsx_row(module, query_id, module.XLSX_INCLUDE_DECISION) for query_id in xlsx_include_ids],
        "pdf_draft_decisions": [
            pdf_row(module, query_id, module.PDF_PENDING_FILE_IDENTITY_DECISION) for query_id in PDF_PENDING_IDS
        ]
        + [pdf_row(module, query_id, module.PDF_EXCLUDE_DECISION) for query_id in PDF_EXCLUDE_IDS],
        "text_unresolved_carry_forward_summary": {
            "unresolved_user_review_count": 23,
            "unresolved_user_review_rows": text_ids,
            "summary_buckets": {
                "expected_answer_or_evidence_revisions": text_ids[:3],
                "second_review": text_ids[3:6],
                "invalid_or_ambiguous_query": text_ids[6:18],
                "evidence_too_broad": text_ids[12:13],
                "source_binding_review_required": text_ids[18:],
            },
        },
    }


def xlsx_row(module, query_id: str, decision: str) -> dict:
    return {
        "query_id": query_id,
        "question_input": f"question {query_id}",
        "candidate_expected_answer": {"text": f"answer {query_id}"},
        "candidate_expected_evidence": {"summary": f"evidence {query_id}"},
        "source_citation_target": {
            "file": "book.xlsx",
            "sheet": "Sheet1",
            "range": "A1:B2",
            "citation_policy": "EXACT_ROW",
        },
        "proposed_user_decision": decision,
        "exact_user_decision_needed": (
            ["confirm expected evidence", "confirm citation target"]
            if decision == module.XLSX_PENDING_EVIDENCE_DECISION
            else ["confirm gold_v0.1 candidate inclusion before any candidate manifest or registry mutation"]
        ),
    }


def pdf_row(module, query_id: str, decision: str) -> dict:
    return {
        "query_id": query_id,
        "proposed_user_decision": decision,
        "stable_document_identity": {"available": False, "basis": "none", "value": ""},
        "proposed_expected_evidence_text_or_summary": {"text": f"pdf evidence {query_id}"},
        "exact_user_decision_needed": [
            "decide whether generic filename identity is acceptable",
            "decide whether stable document identity is required",
            "decide whether the row belongs to file/document identity lookup lane",
            "decide whether to exclude from gold_v0.1",
        ],
    }


def fixture_pdf_rows() -> list[dict[str, str]]:
    queries = {
        "pdf_file_lookup_content_anchor_017": "사용자재와 장비가 모두 신품이고 설계도서 요구에 맞아야 한다는 기준 찾아줘",
        "pdf_file_lookup_content_anchor_018": "경고장 3차 이상 받은 건설기술인 교체 기준 찾아줘",
        "pdf_file_lookup_content_anchor_020": "소방공사를 전기공사와 같이 도급받은 경우 하도급관리 기준을 따른다는 자료 찾아줘",
    }
    return [
        {
            "query_id": query_id,
            "query": query,
            "expected_file_name": "file (1).pdf",
            "expected_document_version_id": "",
            "expected_page_label": "1",
            "expected_page_no": "1",
            "expected_bbox": "",
        }
        for query_id, query in queries.items()
    ]


def write_pdf_csv(path: Path) -> None:
    rows = fixture_pdf_rows()
    columns = sorted({column for row in rows for column in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
