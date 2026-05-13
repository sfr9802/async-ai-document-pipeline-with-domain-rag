from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "ai" / "scripts"


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


common = load_module("rag_pdf_supplemental_common")
pageindex = load_module("rag_pdf_supplemental_pageindex_diagnostic")
parse_canary = load_module("rag_pdf_supplemental_parse_canary")
failure_summary = load_module("rag_pdf_supplemental_evidence_failure_analysis_summary")


def test_supplemental_output_paths_reject_protected_and_non_supplemental_names():
    protected_path = common.ROOT / "ai/eval/eval_queries/gold_queries_pdf_v0.csv"
    generic_report = common.REPORT_DIR / "rag_pdf_report.json"
    safe_paths = {
        "query_csv": common.EVAL_QUERIES_DIR / "gold_queries_pdf_supplemental_tmp_diagnostic.csv",
        "review_csv": common.REVIEW_DIR / "pdf_supplemental_tmp_review_pack.csv",
        "json_report": common.REPORT_DIR / "rag_pdf_supplemental_tmp_report.json",
    }

    findings = common.supplemental_output_path_findings({
        "protected_query_csv": protected_path,
        "generic_json_report": generic_report,
    })

    assert "protected_query_csv" in findings
    assert any("protected" in reason for reason in findings["protected_query_csv"])
    assert "generic_json_report" in findings
    assert any("supplemental-specific" in reason for reason in findings["generic_json_report"])
    assert common.supplemental_output_path_findings(safe_paths) == {}


def test_protected_source_blockers_fail_closed_on_missing_or_hash_drift(tmp_path: Path, monkeypatch):
    protected_rel = "ai/eval/eval_queries/gold_queries_pdf_v0.csv"
    protected_path = tmp_path / protected_rel
    protected_path.parent.mkdir(parents=True)
    protected_path.write_text("stable\n", encoding="utf-8")
    digest = hashlib.sha256(protected_path.read_bytes()).hexdigest()

    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(common, "PROTECTED_SOURCE_SHA256", {protected_rel: digest})
    monkeypatch.setattr(common, "PROTECTED_REGISTRY_PATHS", set())

    assert common.protected_source_blockers() == []

    protected_path.write_text("drift\n", encoding="utf-8")
    assert common.protected_source_blockers() == [f"protected source hash drift: {protected_rel}"]

    protected_path.unlink()
    assert common.protected_source_blockers() == [f"protected source missing: {protected_rel}"]


def test_protected_registry_uses_policy_validation_not_static_hash(tmp_path: Path, monkeypatch):
    registry_rel = "ai/eval/eval_queries/official_denominator_registry.json"
    registry_path = tmp_path / registry_rel
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "official_denominator_registry_v1",
                "current_defaults": {
                    "track_a_xlsx": {
                        "denominator_key": "track_a_xlsx_human_review_normalized_v0",
                    }
                },
                "official_diagnostic_denominators": {
                    "track_a_xlsx_human_review_normalized_v0": {
                        "official_positive_denominator": 23,
                        "official_xlsx_answer_generation_denominator": 0,
                        "sha256": "normalized-sha",
                        "official_positive_retrieval_subset_sha256": "retrieval-sha",
                    },
                    "track_a_xlsx_reviewed_positive": {
                        "row_count": 35,
                        "current_default": False,
                        "superseded_by": "track_a_xlsx_human_review_normalized_v0",
                    },
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(common, "PROTECTED_SOURCE_SHA256", {})
    monkeypatch.setattr(common, "PROTECTED_REGISTRY_PATHS", {registry_rel})

    assert common.protected_source_blockers() == []

    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["official_diagnostic_denominators"]["track_a_xlsx_human_review_normalized_v0"][
        "official_positive_denominator"
    ] = 24
    registry_path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")

    assert common.protected_source_blockers() == [f"protected registry validation failed: {registry_rel}"]


def test_pageindex_manifest_identity_rejects_stale_or_mismatched_manifest(tmp_path: Path):
    input_manifest = {"run_id": "fresh-run"}
    input_manifest_path = tmp_path / "pageindex_supplemental_input_manifest.json"
    input_manifest_sha256 = "expected-sha"

    blockers = pageindex.pageindex_manifest_identity_blockers(
        {
            "run_id": "old-run",
            "input_manifest": "old-input.json",
            "input_manifest_sha256": "old-sha",
            "status": "COMPLETED",
        },
        input_manifest=input_manifest,
        input_manifest_path=input_manifest_path,
        input_manifest_sha256=input_manifest_sha256,
        runner_returncode=1,
    )

    assert any("run_id" in blocker for blocker in blockers)
    assert any("input_manifest path" in blocker for blocker in blockers)
    assert any("input_manifest_sha256" in blocker for blocker in blockers)
    assert any("non-zero" in blocker for blocker in blockers)


def test_pageindex_manifest_identity_allows_explicit_fail_closed_manifest(tmp_path: Path):
    input_manifest = {"run_id": "fresh-run"}
    input_manifest_path = tmp_path / "pageindex_supplemental_input_manifest.json"
    input_manifest_sha256 = "expected-sha"

    blockers = pageindex.pageindex_manifest_identity_blockers(
        {
            "run_id": "fresh-run",
            "input_manifest": pageindex.display_path(input_manifest_path),
            "input_manifest_sha256": input_manifest_sha256,
            "status": "FAIL_CLOSED_PAGEINDEX_UNAVAILABLE",
        },
        input_manifest=input_manifest,
        input_manifest_path=input_manifest_path,
        input_manifest_sha256=input_manifest_sha256,
        runner_returncode=2,
    )

    assert blockers == []


def test_parse_canary_merges_existing_ocr_fallback_as_lower_trust_diagnostic():
    pdf_row = {
        "dataset_source": "elec",
        "relative_path": "ai/eval/datasets/elec/sample.pdf",
        "file_name": "sample.pdf",
        "sha256": "abc",
    }
    csv_row = {
        "ocr_fallback_attempted": True,
        "ocr_fallback_success": False,
        "ocr_fallback_unavailable": False,
        "ocr_used_page_count": 0,
        "ocr_used_block_count": 0,
        "ocr_engine": "",
        "ocr_confidence_avg": None,
        "ocr_warning_codes": [],
        "ocr_fallback_error": None,
        "block_count": 0,
        "block_with_bbox_count": 0,
        "table_like_block_candidate_count": 0,
        "empty_text_page_count": 1,
    }
    page_rows = [
        {
            "page_no": 1,
            "page_text": "",
            "page_text_excerpt": "",
            "text_char_count": 0,
            "empty_text_page": True,
            "block_count": 0,
            "ocr_used": False,
        }
    ]
    block_rows: list[dict[str, object]] = []

    parse_canary.merge_existing_ocr_payload(
        pdf_row=pdf_row,
        payload={
            "parser_name": "pymupdf+paddleocr",
            "parser_version": "pdf-extract-v2",
            "warnings": [],
            "pages": [
                {
                    "page_no": 1,
                    "physical_page_index": 0,
                    "ocr_used": True,
                    "ocr_engine": "paddleocr",
                    "ocr_confidence_avg": 0.91,
                    "blocks": [
                        {
                            "text": "OCR fallback text 123",
                            "bbox": [1, 2, 100, 30],
                            "ocr_used": True,
                            "ocr_engine": "paddleocr",
                            "ocr_language": "korean",
                            "ocr_confidence": 0.91,
                        }
                    ],
                }
            ],
        },
        csv_row=csv_row,
        page_rows=page_rows,
        block_rows=block_rows,
    )

    assert csv_row["ocr_fallback_success"] is True
    assert csv_row["ocr_used_page_count"] == 1
    assert csv_row["ocr_used_block_count"] == 1
    assert csv_row["ocr_engine"] == "paddleocr"
    assert csv_row["ocr_confidence_avg"] == 0.91
    assert page_rows[0]["ocr_used"] is True
    assert page_rows[0]["lower_trust_ocr"] is True
    assert block_rows[0]["ocr_used"] is True
    assert block_rows[0]["lower_trust_ocr"] is True
    assert block_rows[0]["promotion_evidence"] is False


def test_failure_summary_rejects_upstream_llm_or_table_success_claims():
    blockers: list[str] = []
    payload = {
        **failure_summary.REQUIRED_GUARDRAILS,
        "actual_llm_answer_generation_run": True,
        "actual_generated_answer_output": False,
        "answer_draft_is_actual_generated_llm_answer": False,
        "table_semantics_success_claimed": True,
        "row_column_value_semantics_claimed": False,
    }

    failure_summary.validate_guardrails("draft_shape_audit", payload, blockers)

    assert any("actual_llm_answer_generation_run" in blocker for blocker in blockers)
    assert any("table_semantics_success_claimed" in blocker for blocker in blockers)


def test_failure_summary_required_csv_missing_fails_closed(tmp_path: Path):
    blockers: list[str] = []
    missing_csv = tmp_path / "rag_pdf_supplemental_missing.csv"

    rows = failure_summary.required_read_csv(missing_csv, blockers, "table_like_csv")

    assert rows == []
    assert blockers == [f"table_like_csv missing: {failure_summary.display_path(missing_csv)}"]
