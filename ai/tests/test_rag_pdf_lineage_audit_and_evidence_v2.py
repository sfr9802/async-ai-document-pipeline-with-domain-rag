from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "ai" / "scripts"


def load_script(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_for_tests", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_pdf_lineage_audit_finds_bad_vector_surface_and_locator_only_repair(tmp_path: Path) -> None:
    module = load_script("rag_pdf_gold_evidence_lineage_audit_v1")
    paths = write_lineage_fixture(tmp_path)

    report = module.run_audit(
        vector_report=paths["vector_report"],
        repair_report=paths["repair_report"],
        pdf_review_input=paths["pdf_review_input"],
        human_audit_packet=paths["human_audit_packet"],
        source_candidate_files=[paths["source_csv"]],
        output_report=tmp_path / "lineage.json",
        output_md=tmp_path / "lineage.md",
    )

    assert report["status"] == "PDF_GOLD_EVIDENCE_LINEAGE_AUDIT_COMPLETE"
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["tuning_run_started"] is False
    assert report["official_denominator_registry_opened"] is False
    assert report["summary"]["current_pdf_rows"] == 2
    assert report["summary"]["vector_query_surface_already_bad_rows"] == 1
    assert report["summary"]["repair_nearby_context_locator_only_rows"] == 1
    assert report["summary"]["answer_input_echoes_matched_text_rows"] == 1
    assert report["summary"]["human_audit_inherited_bad_query_rows"] == 1
    assert report["summary"]["prior_good_candidate_rows"] == 1
    assert report["summary"]["matching_prior_review_rows"] == 2
    assert report["summary"]["matching_prior_review_positive_rows"] == 2

    rows = {row["query_id"]: row for row in report["lineage_rows"]}
    bad = rows["gq_auto_015"]
    assert bad["vector_diagnostic"]["query"] == "경상수지 추이"
    assert "PDF_HEADING_OR_TITLE_AS_QUERY" in bad["surface_classifications"]
    assert "VECTOR_QUERY_SURFACE_ALREADY_BAD" in bad["degradation_stages"]
    assert "REPAIR_NEARBY_CONTEXT_LOCATOR_ONLY" in bad["degradation_stages"]
    assert "ANSWER_INPUT_ECHOES_MATCHED_TEXT" in bad["degradation_stages"]
    assert "HUMAN_AUDIT_INHERITED_BAD_QUERY" in bad["degradation_stages"]
    assert bad["root_cause"] == "VECTOR_BAD_QUERY_SURFACE_AND_REPAIR_LOCATOR_ONLY"

    good = rows["gq_good_001"]
    assert good["surface_classifications"] == ["NATURAL_LANGUAGE_QUESTION"]
    assert good["degradation_stages"] == []

    source = report["source_candidate_files"][0]
    assert source["path"].endswith("reviewed_pdf.csv")
    assert source["row_count"] == 3
    assert source["candidate_role"] == "diagnostic_prior_review_source"
    assert report["prior_good_candidate_rows"][0]["query"] == "2024년 수출은 전년 대비 어떻게 변했나요?"
    matches = {row["query_id"]: row for row in report["matching_prior_review_rows"]}
    assert matches["gq_auto_015"]["review_decision"] == "KEEP_REVIEWED_POSITIVE"


def test_pdf_evidence_object_v2_canary_blocks_titles_tables_and_preserves_rich_paragraph_evidence(
    tmp_path: Path,
) -> None:
    lineage_module = load_script("rag_pdf_gold_evidence_lineage_audit_v1")
    canary_module = load_script("rag_pdf_evidence_object_v2_canary")
    paths = write_lineage_fixture(tmp_path)
    lineage = lineage_module.run_audit(
        vector_report=paths["vector_report"],
        repair_report=paths["repair_report"],
        pdf_review_input=paths["pdf_review_input"],
        human_audit_packet=paths["human_audit_packet"],
        source_candidate_files=[paths["source_csv"]],
        output_report=tmp_path / "lineage.json",
        output_md=tmp_path / "lineage.md",
    )
    write_json(tmp_path / "lineage.json", lineage)

    report = canary_module.run_canary(
        repair_report=paths["repair_report"],
        lineage_report=tmp_path / "lineage.json",
        output_report=tmp_path / "canary.json",
        output_md=tmp_path / "canary.md",
        include_prior_review_rows=True,
    )

    assert report["status"] == "PDF_EVIDENCE_OBJECT_V2_CANARY_COMPLETE"
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["summary"]["repair_rows"] == 2
    assert report["summary"]["prior_review_rows"] == 1
    assert report["summary"]["candidate_for_local_llm_rows"] == 2
    assert report["summary"]["table_parser_required_rows"] == 1
    assert report["summary"]["locator_only_context_rows"] == 1

    rows = {row["query_id"]: row for row in report["canary_rows"]}
    table_label = rows["gq_auto_015"]
    assert table_label["chunk_type"] == "table_label"
    assert table_label["answerability_gate"] == "TABLE_PARSER_REQUIRED"
    assert table_label["candidate_for_local_llm"] is False
    assert table_label["nearby_native_paragraphs"] == []

    paragraph = rows["gq_good_001"]
    assert paragraph["chunk_type"] == "paragraph"
    assert paragraph["answerability_gate"] == "ANSWERABLE"
    assert paragraph["candidate_for_local_llm"] is True
    assert paragraph["answerable_evidence_text"] == "2024년 수출은 전년 대비 7.0% 증가했다."
    assert paragraph["citation_locator"]["page"] == 5
    assert paragraph["citation_locator"]["bbox"] == [1, 2, 3, 4]
    assert paragraph["citation_locator"]["search_unit_id"] == "su-good"
    assert paragraph["pdf_evidence_context_v2"]["text_context"]["native_block_text"] == (
        "2024년 수출은 전년 대비 7.0% 증가했다."
    )
    assert paragraph["pdf_evidence_context_v2"]["table_context"]["structured_table_claim_allowed"] is False

    prior = rows["prior_good_pdf_review_001"]
    assert prior["source_kind"] == "prior_review_source"
    assert prior["candidate_for_local_llm"] is True
    assert prior["answerable_evidence_text"] == "2024년 수출은 전년 대비 7.0% 증가했다."
    assert prior["citation_locator"]["page"] == 5
    assert prior["citation_locator"]["bbox"] == [1, 2, 3, 4]
    assert prior["pdf_evidence_context_v2"]["source_identity"]["source_file_id"] == ""
    assert "storage://raw-local-pdf" not in json.dumps(report, ensure_ascii=False)


def test_lineage_audit_fails_closed_when_source_candidate_points_to_protected_registry(tmp_path: Path) -> None:
    module = load_script("rag_pdf_gold_evidence_lineage_audit_v1")
    paths = write_lineage_fixture(tmp_path)
    protected = tmp_path / "ai" / "eval" / "eval_queries" / "official_denominator_registry.json"
    write_json(protected, {"should_not_be_read": True})

    report = module.run_audit(
        vector_report=paths["vector_report"],
        repair_report=paths["repair_report"],
        pdf_review_input=paths["pdf_review_input"],
        human_audit_packet=paths["human_audit_packet"],
        source_candidate_files=[protected],
        output_report=tmp_path / "lineage.json",
        output_md=tmp_path / "lineage.md",
    )

    assert report["status"] == "FAILED_GUARDRAIL"
    assert report["official_denominator_registry_opened"] is False
    assert any("PROTECTED_SOURCE_CANDIDATE_PATH" in error for error in report["validation"]["errors"])


def test_canary_reports_blocked_when_all_rows_lack_context_and_rejects_file_identity_prior_rows(
    tmp_path: Path,
) -> None:
    lineage_module = load_script("rag_pdf_gold_evidence_lineage_audit_v1")
    canary_module = load_script("rag_pdf_evidence_object_v2_canary")
    paths = write_lineage_fixture(tmp_path)
    repair_payload = json.loads(paths["repair_report"].read_text(encoding="utf-8"))
    repair_payload["repair_rows"] = [repair_payload["repair_rows"][0]]
    write_json(paths["repair_report"], repair_payload)
    vector_payload = json.loads(paths["vector_report"].read_text(encoding="utf-8"))
    vector_payload["per_query"] = [vector_payload["per_query"][0]]
    write_json(paths["vector_report"], vector_payload)
    write_jsonl(paths["pdf_review_input"], [json.loads(paths["pdf_review_input"].read_text(encoding="utf-8").splitlines()[0])])
    human_payload = json.loads(paths["human_audit_packet"].read_text(encoding="utf-8"))
    human_payload["actionable_rows"] = [human_payload["actionable_rows"][0]]
    write_json(paths["human_audit_packet"], human_payload)
    write_file_identity_prior_rows(paths["source_csv"])

    lineage = lineage_module.run_audit(
        vector_report=paths["vector_report"],
        repair_report=paths["repair_report"],
        pdf_review_input=paths["pdf_review_input"],
        human_audit_packet=paths["human_audit_packet"],
        source_candidate_files=[paths["source_csv"]],
        output_report=tmp_path / "lineage.json",
        output_md=tmp_path / "lineage.md",
    )
    write_json(tmp_path / "lineage.json", lineage)

    report = canary_module.run_canary(
        repair_report=paths["repair_report"],
        lineage_report=tmp_path / "lineage.json",
        output_report=tmp_path / "canary.json",
        output_md=tmp_path / "canary.md",
        include_prior_review_rows=True,
    )

    assert report["status"] == "PDF_EVIDENCE_OBJECT_V2_CANARY_BLOCKED_BY_CONTEXT_GAPS"
    assert report["summary"]["candidate_for_local_llm_rows"] == 0
    file_row = next(row for row in report["canary_rows"] if row["query_id"] == "pdf_file_lookup_content_anchor_001")
    assert file_row["answerability_gate"] == "FILE_IDENTITY_ONLY"
    assert file_row["candidate_for_local_llm"] is False
    assert file_row["content_evidence_lane"] == "pdf_file_identity"
    assert file_row["answerable_evidence_text"] == ""
    assert file_row["matched_text"] == ""
    assert file_row["nearby_native_paragraphs"] == []
    assert file_row["identity_reference_text"] == "국번없이 123으로 전기상담을 받을 수 있다."


def test_canary_fails_closed_when_lineage_source_failed_or_promotion_bearing(tmp_path: Path) -> None:
    lineage_module = load_script("rag_pdf_gold_evidence_lineage_audit_v1")
    canary_module = load_script("rag_pdf_evidence_object_v2_canary")
    paths = write_lineage_fixture(tmp_path)
    lineage = lineage_module.run_audit(
        vector_report=paths["vector_report"],
        repair_report=paths["repair_report"],
        pdf_review_input=paths["pdf_review_input"],
        human_audit_packet=paths["human_audit_packet"],
        source_candidate_files=[paths["source_csv"]],
        output_report=tmp_path / "lineage.json",
        output_md=tmp_path / "lineage.md",
    )
    lineage["status"] = "FAILED_GUARDRAIL"
    lineage["promotion_evidence"] = True
    lineage["validation"] = {"ok": False, "errors": ["synthetic failure"]}
    write_json(tmp_path / "lineage.json", lineage)

    report = canary_module.run_canary(
        repair_report=paths["repair_report"],
        lineage_report=tmp_path / "lineage.json",
        output_report=tmp_path / "canary.json",
        output_md=tmp_path / "canary.md",
    )

    assert report["status"] == "FAILED_GUARDRAIL"
    assert "lineage_report validation.ok must be true" in report["validation"]["errors"]
    assert "lineage_report promotion_evidence must remain false" in report["validation"]["errors"]


def write_lineage_fixture(tmp_path: Path) -> dict[str, Path]:
    vector_report = tmp_path / "vector.json"
    repair_report = tmp_path / "repair.json"
    pdf_review_input = tmp_path / "pdf_input.jsonl"
    human_audit_packet = tmp_path / "human.json"
    source_csv = tmp_path / "reviewed_pdf.csv"

    write_json(
        vector_report,
        {
            "status": "DIAGNOSTIC_ONLY",
            "promotion_evidence": False,
            "per_query": [
                {"query_id": "gq_auto_015", "query": "경상수지 추이", "bucket": "pdf_table_lookup"},
                {
                    "query_id": "gq_good_001",
                    "query": "2024년 수출은 전년 대비 어떻게 변했나요?",
                    "bucket": "pdf_section_question",
                },
            ],
        },
    )
    repair_rows = [
        repair_row(
            "gq_auto_015",
            matched_text="경상수지 추이",
            nearby_paragraphs=["경제동향.pdf > p.29 > bbox [1,2,3,4]"],
            region_type="paragraph",
            page=29,
            bbox=[10, 20, 30, 40],
            search_unit_id="su-table-label",
            bucket="pdf_table_lookup",
        ),
        repair_row(
            "gq_good_001",
            matched_text="2024년 수출은 전년 대비 7.0% 증가했다.",
            nearby_paragraphs=["2024년 수출은 전년 대비 7.0% 증가했다."],
            region_type="paragraph",
            page=5,
            bbox=[1, 2, 3, 4],
            search_unit_id="su-good",
            bucket="pdf_section_question",
        ),
    ]
    write_json(
        repair_report,
        {
            "status": "DIAGNOSTIC_POLICY_PACKET_READY",
            "strict_ready_rows": 2,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "guardrails": {"official_denominator_registry_opened": False},
            "repair_rows": repair_rows,
        },
    )
    write_jsonl(
        pdf_review_input,
        [
            {
                **repair_rows[0],
                "generated_answer": "경상수지 추이",
                "diagnostic_answer": "경상수지 추이",
            },
            {
                **repair_rows[1],
                "generated_answer": "2024년 수출은 전년 대비 7.0% 증가했다.",
                "diagnostic_answer": "2024년 수출은 전년 대비 7.0% 증가했다.",
            },
        ],
    )
    write_json(
        human_audit_packet,
        {
            "status": "HUMAN_AUDIT_READY",
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "actionable_rows": [
                {
                    "track": "pdf_business_ocr_mm",
                    "query_id": "gq_auto_015",
                    "question": "경상수지 추이",
                    "proposed_answer": "경상수지 추이",
                    "proposed_evidence": "경상수지 추이",
                    "issue_type": "PDF_CONTENT_EXPECTED_EVIDENCE_LANE_REVIEW",
                },
                {
                    "track": "pdf_business_ocr_mm",
                    "query_id": "gq_good_001",
                    "question": "2024년 수출은 전년 대비 어떻게 변했나요?",
                    "proposed_answer": "2024년 수출은 전년 대비 7.0% 증가했다.",
                    "proposed_evidence": "2024년 수출은 전년 대비 7.0% 증가했다.",
                    "issue_type": "PDF_CONTENT_EXPECTED_EVIDENCE_LANE_REVIEW",
                },
            ],
        },
    )
    write_csv(
        source_csv,
        [
            {
                "query_id": "prior_good_pdf_review_001",
                "query": "2024년 수출은 전년 대비 어떻게 변했나요?",
                "expected_answer_text": "2024년 수출은 전년 대비 7.0% 증가했다.",
                "expected_file_name": "경제동향.pdf",
                "expected_page_no": "5",
                "expected_bbox": "[1, 2, 3, 4]",
                "expected_chunk_type": "paragraph",
                "label_status": "reviewed",
                "review_decision": "KEEP_REVIEWED_POSITIVE",
            },
            {
                "query_id": "gq_auto_015",
                "query": "경상수지 추이",
                "expected_answer_text": "경상수지 추이",
                "expected_file_name": "경제동향.pdf",
                "expected_page_no": "29",
                "expected_bbox": "[10, 20, 30, 40]",
                "expected_chunk_type": "table_label",
                "label_status": "reviewed",
                "review_decision": "KEEP_REVIEWED_POSITIVE",
            },
            {
                "query_id": "gq_good_001",
                "query": "2024년 수출은 전년 대비 어떻게 변했나요?",
                "expected_answer_text": "",
                "expected_file_name": "경제동향.pdf",
                "expected_page_no": "5",
                "expected_bbox": "[1, 2, 3, 4]",
                "expected_chunk_type": "paragraph",
                "label_status": "reviewed",
                "review_decision": "KEEP_REVIEWED_POSITIVE",
            },
        ],
    )
    return {
        "vector_report": vector_report,
        "repair_report": repair_report,
        "pdf_review_input": pdf_review_input,
        "human_audit_packet": human_audit_packet,
        "source_csv": source_csv,
    }


def repair_row(
    query_id: str,
    *,
    matched_text: str,
    nearby_paragraphs: list[str],
    region_type: str,
    page: int,
    bbox: list[int],
    search_unit_id: str,
    bucket: str,
) -> dict:
    return {
        "query_id": query_id,
        "bucket": bucket,
        "matched_text": matched_text,
        "citation_text": matched_text,
        "nearby_paragraphs": nearby_paragraphs,
        "content_evidence_lane": "pdf_content_evidence",
        "file_identity_lane": {"filename_only_identity_accepted": False, "merged_with_content_evidence": False},
        "native_text_available": True,
        "OCR_fallback_used": False,
        "page": page,
        "physical_page_index": page - 1,
        "bbox": bbox,
        "region_type": region_type,
        "search_unit_id": search_unit_id,
        "document_version_id": "docv-1",
        "file": "경제동향.pdf",
        "source_metadata": {
            "native_block_text": matched_text,
            "parser_version": "pdf-extract-v2",
            "parsed_artifact": {"id": "parsed-1", "storage_uri": "storage://raw-local-pdf"},
            "location_json": {"block_type": region_type, "page_label": str(page)},
        },
        "citation_locator": {
            "file": "경제동향.pdf",
            "document_version_id": "docv-1",
            "page": page,
            "physical_page_index": page - 1,
            "bbox": bbox,
            "region_type": region_type,
            "search_unit_id": search_unit_id,
        },
        "strict_ready": True,
        "official_metric_input": False,
        "promotion_evidence": False,
    }


def write_file_identity_prior_rows(path: Path) -> None:
    write_csv(
        path,
        [
            {
                "query_id": "pdf_file_lookup_content_anchor_001",
                "query": "전기상담을 받을 수 있는 대표 전화번호는 무엇인가요?",
                "expected_answer_text": "국번없이 123으로 전기상담을 받을 수 있다.",
                "expected_file_name": "전기요금표.pdf",
                "expected_page_no": "1",
                "expected_bbox": "[1, 2, 3, 4]",
                "expected_chunk_type": "paragraph",
                "label_status": "reviewed",
                "review_decision": "KEEP_REVIEWED_POSITIVE",
            }
        ],
    )
