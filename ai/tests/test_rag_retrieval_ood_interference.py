from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPLIT_SCRIPT = ROOT / "ai" / "scripts" / "rag_retrieval_ood_split_builder.py"
VECTOR_SCRIPT = ROOT / "ai" / "scripts" / "rag_vector_interference_diagnostic.py"
OFFICIAL_REGISTRY = ROOT / "ai" / "eval" / "eval_queries" / "official_denominator_registry.json"
HIDDEN_SENTINEL = "DO_NOT_EXPOSE_HIDDEN_CELL"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_ood_split_builder_guardrails_manifest_schema_and_registry_unchanged(tmp_path: Path):
    split = load_module(SPLIT_SCRIPT, "rag_retrieval_ood_split_builder_for_tests")
    config = fixture_config(tmp_path)
    before_registry = read_registry_bytes()

    rows, report = split.build_splits(config)

    assert read_registry_bytes() == before_registry
    assert report["production_index_mutation"] is False
    assert report["vector_write_attempted"] is False
    assert report["official_denominator_registry_changed"] is False
    assert report["hidden_xlsx_exposed"] is False
    assert report["content_preview_emitted"] is False
    assert report["random_row_split_used_as_main_metric"] is False
    assert split.SPLIT_RANDOM not in report["main_metric_split_types"]
    assert len(rows) == report["manifest_row_count"]
    assert sum(counts["manifest_rows"] for counts in report["lane_counts"].values()) == len(rows)
    assert all(row["content_preview_emitted"] == "false" for row in rows)

    xlsx_rows = [row for row in rows if row["lane"] == "XLSX" and row["split_type"] != split.SPLIT_RANDOM]
    pdf_file_rows = [
        row
        for row in rows
        if row["lane"] == "PDF_FILE_IDENTITY" and row["split_type"] not in {split.SPLIT_RANDOM, split.SPLIT_LANE_CROSS}
    ]
    assert xlsx_rows
    assert pdf_file_rows
    assert all(row["hidden_xlsx_redacted"] == "true" for row in xlsx_rows)
    assert all(row["pdf_file_identity_only"] == "true" for row in pdf_file_rows)


def test_vector_diagnostic_in_memory_guardrails_and_pdf_identity_only(tmp_path: Path):
    vector = load_module(VECTOR_SCRIPT, "rag_vector_interference_diagnostic_for_tests")
    config = fixture_config(tmp_path)
    config["diagnostic_source_contract"] = diagnostic_source_contract()
    before_registry = read_registry_bytes()

    xlsx_lane = next(lane for lane in config["lanes"] if lane["name"] == "XLSX")
    xlsx_candidates = vector.load_candidates_for_lane(xlsx_lane, vector.load_query_cases(xlsx_lane), config)
    assert xlsx_candidates
    assert HIDDEN_SENTINEL not in " ".join(candidate.text for candidate in xlsx_candidates)

    report, by_query = vector.run_diagnostic(config)
    serialized = json.dumps({"report": report, "by_query": by_query}, ensure_ascii=False)

    assert read_registry_bytes() == before_registry
    assert HIDDEN_SENTINEL not in serialized
    assert report["production_index_mutation"] is False
    assert report["vector_write_attempted"] is False
    assert report["official_denominator_registry_changed"] is False
    assert report["hidden_xlsx_exposed"] is False
    assert report["local_llm_used_for_labels_or_judgments"] is False
    assert report["optuna_run"] is False
    assert report["diagnostic_namespace"]["namespace_name"].startswith("diagnostic_")
    assert report["diagnostic_namespace"]["name_has_diagnostic_marker"] is True
    assert report["diagnostic_namespace"]["created_or_reused"] == "not_required_in_memory_shadow_index"
    assert report["pdf_file_lookup_policy"] == vector.PDF_FILE_IDENTITY_ONLY_POLICY
    assert report["pdf_file_lookup_content_page_bbox_table_row_column_value_claimed"] is False
    assert report["near_duplicate_distractor_policy"] == "metadata_hard_negative_without_query_echo"
    assert report["diagnostic_source_contract"]["XLSX"]["target_sources"] == [
        "PUBLIC_DATA_PORTAL_XLSX",
        "KOSIS_EXCEL",
        "LOCAL_GOVERNMENT_STATISTICAL_YEARBOOK_EXCEL",
        "INTERNAL_WORK_EXCEL",
    ]
    assert set(report["conditions_run"]) == {
        vector.CONDITION_A,
        vector.CONDITION_B,
        vector.CONDITION_C,
        vector.CONDITION_D,
        vector.CONDITION_E,
    }
    assert set(report["lane_summary"]) == {"TEXT_NAMU", "XLSX", "PDF_CONTENT", "PDF_FILE_IDENTITY"}
    assert all("query" not in row for row in by_query)


def test_text_namu_near_duplicate_distractors_are_metadata_hard_negatives_without_query_echo():
    vector = load_module(VECTOR_SCRIPT, "rag_vector_interference_diagnostic_near_dup_for_tests")
    case = vector.query_case_from_row(
        "TEXT_NAMU",
        {
            "query_id": "t1",
            "query": "alpha overview",
            "bucket": "anime",
            "expected_document_ids": "doc-alpha",
            "parser_version": "namu-v4",
        },
    )

    distractor = vector.near_duplicate_distractors(case, 1)[0]

    assert distractor.is_synthetic_distractor is True
    assert distractor.distractor_kind == "near_duplicate_metadata_hard_negative"
    assert "alpha overview" not in distractor.text
    assert case.query_text not in distractor.text


def test_diagnostic_namespace_requires_sandbox_marker():
    vector = load_module(VECTOR_SCRIPT, "rag_vector_interference_diagnostic_namespace_for_tests")

    unsafe = vector.diagnostic_namespace_metadata({"diagnostic_namespace": {"required": True, "name": "prod_vectors"}})
    safe = vector.diagnostic_namespace_metadata({"diagnostic_namespace": {"required": True, "name": "sandbox_vectors"}})

    assert unsafe["name_has_diagnostic_marker"] is False
    assert safe["name_has_diagnostic_marker"] is True


def fixture_config(tmp_path: Path) -> dict:
    phase0 = tmp_path / "phase0.json"
    phase1 = tmp_path / "phase1.json"
    phase0.write_text(json.dumps({"status": "PASS", "schema_version": "preflight_v1"}), encoding="utf-8")
    phase1.write_text(json.dumps({"status": "PASS", "schema_version": "diversity_v1"}), encoding="utf-8")

    text_q = tmp_path / "text_queries.csv"
    text_chunks = tmp_path / "text_chunks.jsonl"
    xlsx_q = tmp_path / "xlsx_queries.csv"
    xlsx_chunks = tmp_path / "xlsx_chunks.jsonl"
    pdf_q = tmp_path / "pdf_queries.csv"
    pdf_chunks = tmp_path / "pdf_chunks.jsonl"
    pdf_file_q = tmp_path / "pdf_file_queries.csv"

    write_csv(
        text_q,
        ["query_id", "query", "bucket", "expected_page_ids", "expected_document_ids", "parser_version"],
        [
            ["t1", "alpha overview", "anime", "doc-alpha", "doc-alpha", "namu-v4"],
            ["t2", "beta overview", "anime", "doc-beta", "doc-beta", "namu-v4"],
        ],
    )
    write_jsonl(
        text_chunks,
        [
            {"chunk_id": "tc1", "doc_id": "doc-alpha", "title": "Alpha", "embedding_text": "alpha overview visible"},
            {"chunk_id": "tc2", "doc_id": "doc-beta", "title": "Beta", "embedding_text": "beta overview visible"},
        ],
    )

    write_csv(
        xlsx_q,
        [
            "query_id",
            "query",
            "expected_document_version_id",
            "expected_file_name",
            "expected_cell_range",
            "expected_table_id",
            "expected_sheet_name",
            "expected_chunk_type",
            "expected_location_type",
            "parser_version",
        ],
        [
            ["x1", "quarter total", "xlsx-doc-1", "finance.xlsx", "A1:B2", "table-1", "Sheet1", "table", "cell_range", "xlsx-v2"],
            ["x2", "quarter average", "xlsx-doc-2", "finance.xlsx", "C1:D2", "table-2", "Sheet1", "table", "cell_range", "xlsx-v2"],
        ],
    )
    write_jsonl(
        xlsx_chunks,
        [
            {
                "chunk_id": "xc1",
                "source_file_id": "xlsx-doc-1",
                "source_file_name": "finance.xlsx",
                "parser_version": "xlsx-v2",
                "chunk_type": "table",
                "cellRange": "A1:B2",
                "tableId": "table-1",
                "embedding_text": HIDDEN_SENTINEL,
                "text": HIDDEN_SENTINEL,
            },
            {
                "chunk_id": "xc2",
                "source_file_id": "xlsx-doc-2",
                "source_file_name": "finance.xlsx",
                "parser_version": "xlsx-v2",
                "chunk_type": "table",
                "cellRange": "C1:D2",
                "tableId": "table-2",
                "embedding_text": HIDDEN_SENTINEL,
                "text": HIDDEN_SENTINEL,
            },
        ],
    )

    write_csv(
        pdf_q,
        ["query_id", "query", "expected_document_version_id", "expected_file_name", "expected_page_no", "expected_bbox", "parser_version"],
        [["p1", "pdf content alpha", "pdf-doc-1", "report.pdf", "1", "0,0,1,1", "pdf-native"]],
    )
    write_jsonl(
        pdf_chunks,
        [
            {
                "chunk_id": "pc1",
                "source_file_id": "pdf-doc-1",
                "source_file_name": "report.pdf",
                "parser_version": "pdf-native",
                "embedding_text": "pdf content alpha",
                "citation_text": "p.1",
                "location_json": {"page": 1},
            }
        ],
    )

    write_csv(
        pdf_file_q,
        ["query_id", "query", "expected_file_name", "source_file_name", "expected_document_version_id", "parser_version"],
        [
            ["pf1", "2024 04 bill pdf", "2024_04_bill.pdf", "2024_04_bill.pdf", "pf-doc-1", "identity-only"],
            ["pf2", "2024 05 bill pdf", "2024_05_bill.pdf", "2024_05_bill.pdf", "pf-doc-2", "identity-only"],
        ],
    )

    return {
        "schema_version": "retrieval_ood_interference_diagnostic_config_v1",
        "prerequisites": {
            "phase0_local_resource_preflight": str(phase0),
            "phase1_corpus_diversity_profile": str(phase1),
        },
        "diagnostic_namespace": {
            "required": False,
            "name": "diagnostic_retrieval_ood_interference_test",
            "production_index_mutation": False,
            "vector_write_attempted": False,
        },
        "splits": {
            "random_seed": 9802,
            "random_holdout_modulo": 2,
            "max_groups_per_type": 3,
            "main_metric_split_types": [
                "random_row_split",
                "leave_document_family_out",
                "leave_template_or_table_shape_out",
                "leave_parser_version_out",
                "leave_source_artifact_out",
                "file_identity_confusion_split",
                "lane_cross_eval",
            ],
            "random_row_split_diagnostic_baseline_only": True,
        },
        "interference": {
            "scoring_method": "in_memory_shadow_token_vector",
            "max_baseline_candidates_per_lane": 50,
            "max_same_lane_distractors": 3,
            "max_cross_lane_distractors": 3,
            "max_safe_distractors": 3,
            "max_near_duplicate_distractors": 2,
            "conditions": [
                "A_baseline_corpus_only",
                "B_baseline_plus_safe_distractor_corpus",
                "C_baseline_plus_same_lane_hard_negatives",
                "D_baseline_plus_cross_lane_distractors",
                "E_baseline_plus_near_duplicate_metadata_file_name_distractors",
            ],
        },
        "lanes": [
            {
                "name": "TEXT_NAMU",
                "query_sources": [{"role": "text", "path": str(text_q)}],
                "chunk_sources": [{"type": "jsonl", "path": str(text_chunks), "embedding_text_fields": ["embedding_text"]}],
            },
            {
                "name": "XLSX",
                "hidden_xlsx_redaction": True,
                "query_sources": [{"role": "xlsx", "path": str(xlsx_q)}],
                "chunk_sources": [{"type": "jsonl", "path": str(xlsx_chunks), "metadata_only_text": True}],
            },
            {
                "name": "PDF_CONTENT",
                "query_sources": [{"role": "pdf", "path": str(pdf_q)}],
                "chunk_sources": [{"type": "jsonl", "path": str(pdf_chunks), "embedding_text_fields": ["embedding_text"]}],
            },
            {
                "name": "PDF_FILE_IDENTITY",
                "identity_only": True,
                "query_sources": [{"role": "pdf-file", "path": str(pdf_file_q)}],
            },
        ],
        "outputs": {},
    }


def read_registry_bytes() -> bytes:
    return OFFICIAL_REGISTRY.read_bytes() if OFFICIAL_REGISTRY.exists() else b""


def write_csv(path: Path, fields: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def diagnostic_source_contract() -> dict:
    return {
        "PDF_CONTENT": {
            "target_sources": [
                "DART_PDF",
                "PUBLIC_INSTITUTION_PDF",
                "LOCAL_GOVERNMENT_PDF",
                "INTERNAL_REPORT_PDF",
            ],
            "hard_negative_policy": "keep_file_identity_confusions_out_of_pdf_content_success",
        },
        "XLSX": {
            "target_sources": [
                "PUBLIC_DATA_PORTAL_XLSX",
                "KOSIS_EXCEL",
                "LOCAL_GOVERNMENT_STATISTICAL_YEARBOOK_EXCEL",
                "INTERNAL_WORK_EXCEL",
            ],
            "hard_negative_policy": "preserve_hidden_redaction_and_table_shape_confusions",
        },
        "PDF_FILE_IDENTITY": {
            "target_sources": ["DART_PDF", "PUBLIC_INSTITUTION_PDF", "STATISTICAL_YEARBOOK_PDF"],
            "hard_negative_policy": "year_version_and_similar_filename_confusions",
        },
        "TEXT_NAMU": {
            "target_sources": ["NAMU_NEAR_DUPLICATE_METADATA"],
            "hard_negative_policy": "near_duplicate_metadata_hard_negative_without_query_echo",
        },
    }
