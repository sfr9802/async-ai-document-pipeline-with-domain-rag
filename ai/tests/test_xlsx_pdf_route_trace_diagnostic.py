from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai" / "eval" / "harness" / "xlsx_pdf_route_trace.py"


def load_module():
    spec = importlib.util.spec_from_file_location("xlsx_pdf_route_trace_for_tests", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


trace = load_module()
DEFAULT_LOCATION = object()


def test_xlsx_strict_wrapper_route_detection(tmp_path: Path):
    paths = fixture_paths(tmp_path, xlsx_rows=[xlsx_query_result()])

    payload = trace.build_route_trace_report(config(paths, max_xlsx=1, max_pdf=0))
    row = payload["route_trace_rows"][0]

    assert payload["promotion_evidence"] is False
    assert payload["official_denominator_changed"] is False
    assert row["actual_route"] == trace.ROUTE_XLSX_WRAPPER
    assert row["route_status"] == trace.STATUS_PASS
    assert row["hidden_excluded_leakage"] == trace.STATUS_PASS
    assert row["allowUnscoped"] is False
    assert row["parser_version"] == trace.XLSX_PARSER_VERSION


def test_xlsx_strict_wrapper_fails_closed_on_non_wrapper_inputs(tmp_path: Path):
    variants = [
        {"xlsx_namespace": "rag-ingestion-v2-text"},
        {"official_route_guard": {"agent_orchestrator_enabled": True, "combined_retrieval_enabled": False}},
        {"official_route_guard": {"agent_orchestrator_enabled": False, "combined_retrieval_enabled": True}},
        {"xlsx_rows": [xlsx_query_result(hit=xlsx_hit(parser_version="xlsx-extract-v1"))]},
    ]
    for kwargs in variants:
        fixture_kwargs = {"xlsx_rows": [xlsx_query_result()]}
        fixture_kwargs.update(kwargs)
        paths = fixture_paths(tmp_path / str(len(kwargs)) / str(hash(str(kwargs))), **fixture_kwargs)

        payload = trace.build_route_trace_report(config(paths, max_xlsx=1, max_pdf=0))
        row = payload["route_trace_rows"][0]

        assert payload["promotion_evidence"] is False
        assert payload["xlsx_answer_denominator"] == 0
        assert row["route_status"] == trace.STATUS_FAIL
        assert trace.FAIL_XLSX_STRICT_ROUTE in row["failure_categories"]


def test_xlsx_hidden_excluded_leakage_probe_fails_closed(tmp_path: Path):
    paths = fixture_paths(
        tmp_path,
        xlsx_rows=[xlsx_query_result()],
        hidden_metrics={"hidden_content_leakage_count": 1, "hidden_negative_pass_count": 1, "search_error_count": 0},
    )

    payload = trace.build_route_trace_report(config(paths, max_xlsx=1, max_pdf=0))
    row = payload["route_trace_rows"][0]

    assert payload["xlsx_leakage_probe"]["status"] == trace.STATUS_FAIL
    assert payload["xlsx_leakage_probe"]["query_surface_hidden_leakage"] is True
    assert row["route_status"] == trace.STATUS_FAIL
    assert trace.FAIL_HIDDEN_LEAKAGE in row["failure_categories"]


def test_xlsx_hidden_search_error_fails_closed(tmp_path: Path):
    paths = fixture_paths(
        tmp_path,
        xlsx_rows=[xlsx_query_result()],
        hidden_metrics={"hidden_content_leakage_count": 0, "hidden_negative_pass_count": 0, "search_error_count": 1},
    )

    payload = trace.build_route_trace_report(config(paths, max_xlsx=1, max_pdf=0))

    assert payload["xlsx_leakage_probe"]["status"] == trace.STATUS_FAIL
    assert trace.FAIL_HIDDEN_LEAKAGE in payload["route_trace_rows"][0]["failure_categories"]


def test_xlsx_hidden_probe_without_negative_rows_is_diagnostic_only(tmp_path: Path):
    paths = fixture_paths(
        tmp_path,
        xlsx_rows=[xlsx_query_result()],
        hidden_negative_row_count=0,
        hidden_metrics={"hidden_content_leakage_count": 0, "hidden_negative_pass_count": 0, "search_error_count": 0},
    )

    payload = trace.build_route_trace_report(config(paths, max_xlsx=1, max_pdf=0))

    assert payload["xlsx_leakage_probe"]["status"] == trace.STATUS_DIAGNOSTIC_ONLY
    assert payload["xlsx_leakage_probe"]["positive_metric_mix_allowed"] is False
    assert payload["xlsx_leakage_probe"]["excluded_from_positive_metrics"] is True


def test_pdf_native_text_preferred_over_ocr_fallback_when_native_exists(tmp_path: Path):
    pdf_row = pdf_query_result(
        hits=[
            pdf_hit(rank=1, search_unit_id="ocr-hit", ocr_used=True, identity=True),
            pdf_hit(rank=2, search_unit_id="native-hit", ocr_used=False, identity=True),
        ]
    )
    paths = fixture_paths(tmp_path, pdf_rows=[pdf_row])

    payload = trace.build_route_trace_report(config(paths, max_xlsx=0, max_pdf=1))
    row = payload["route_trace_rows"][0]

    assert row["search_unit_id"] == "native-hit"
    assert row["evidence_source"] == "native_pdf_text"
    assert row["native_pdf_text_used"] is True
    assert row["ocr_fallback_used"] is False


def test_pdf_native_text_precedence_even_when_ocr_has_better_identity_and_rank(tmp_path: Path):
    pdf_row = pdf_query_result(
        hits=[
            pdf_hit(rank=1, search_unit_id="ocr-identity", ocr_used=True, identity=True),
            pdf_hit(rank=2, search_unit_id="native-nonidentity", ocr_used=False, identity=False),
        ]
    )
    paths = fixture_paths(tmp_path, pdf_rows=[pdf_row])

    payload = trace.build_route_trace_report(config(paths, max_xlsx=0, max_pdf=1))
    row = payload["route_trace_rows"][0]

    assert row["search_unit_id"] == "native-nonidentity"
    assert row["evidence_source"] == "native_pdf_text"
    assert payload["pdf_native_ocr_routing"]["top_k_ocr_fallback_candidate_count"] == 1


def test_pdf_file_vs_content_route_classification(tmp_path: Path):
    paths = fixture_paths(
        tmp_path,
        pdf_rows=[
            pdf_query_result(query_id="pdf-file", bucket="pdf_page_lookup"),
            pdf_query_result(query_id="pdf-content", bucket="pdf_section_question"),
        ],
    )

    payload = trace.build_route_trace_report(config(paths, max_xlsx=0, max_pdf=2))
    routes = {row["query_id"]: row["actual_route"] for row in payload["route_trace_rows"]}

    assert routes["pdf-file"] == trace.ROUTE_PDF_FILE
    assert routes["pdf-content"] == trace.ROUTE_PDF_CONTENT
    assert payload["pdf_file_vs_content_routing"]["file_lookup_route_count"] == 1
    assert payload["pdf_file_vs_content_routing"]["content_lookup_route_count"] == 1


def test_pdf_file_lookup_requires_file_match(tmp_path: Path):
    paths = fixture_paths(
        tmp_path,
        pdf_rows=[pdf_query_result(bucket="pdf_page_lookup", hits=[pdf_hit(file_match=False)])],
    )

    payload = trace.build_route_trace_report(config(paths, max_xlsx=0, max_pdf=1))
    row = payload["route_trace_rows"][0]

    assert row["route_status"] == trace.STATUS_FAIL
    assert trace.FAIL_FILE_CONTENT_MISMATCH in row["failure_categories"]
    assert payload["pdf_file_vs_content_routing"]["file_content_mismatch_count"] == 1


def test_pdf_content_lookup_rejects_page_only_hit(tmp_path: Path):
    paths = fixture_paths(
        tmp_path,
        pdf_rows=[pdf_query_result(bucket="pdf_section_question", hits=[pdf_hit(chunk_type="page")])],
    )

    payload = trace.build_route_trace_report(config(paths, max_xlsx=0, max_pdf=1))
    row = payload["route_trace_rows"][0]

    assert row["route_status"] == trace.STATUS_FAIL
    assert trace.FAIL_FILE_CONTENT_MISMATCH in row["failure_categories"]


def test_missing_citation_text_failure_category(tmp_path: Path):
    paths = fixture_paths(tmp_path, xlsx_rows=[xlsx_query_result(hit=xlsx_hit(citation_text=""))])

    payload = trace.build_route_trace_report(config(paths, max_xlsx=1, max_pdf=0))
    row = payload["route_trace_rows"][0]

    assert row["route_status"] == trace.STATUS_FAIL
    assert row["failure_category"] == trace.FAIL_MISSING_CITATION


def test_pdf_missing_citation_fails_not_review_required(tmp_path: Path):
    paths = fixture_paths(
        tmp_path,
        pdf_rows=[pdf_query_result(hits=[pdf_hit(citation_text="")])],
    )

    payload = trace.build_route_trace_report(config(paths, max_xlsx=0, max_pdf=1))
    row = payload["route_trace_rows"][0]

    assert row["route_status"] == trace.STATUS_FAIL
    assert row["failure_category"] == trace.FAIL_MISSING_CITATION


def test_invalid_and_missing_location_json_failure_categories(tmp_path: Path):
    paths = fixture_paths(
        tmp_path,
        xlsx_rows=[
            xlsx_query_result(query_id="bad-location", hit=xlsx_hit(location_json={"type": "xlsx"})),
            xlsx_query_result(query_id="missing-location", hit=xlsx_hit(location_json=None)),
        ],
    )

    payload = trace.build_route_trace_report(config(paths, max_xlsx=2, max_pdf=0))
    failures = {row["query_id"]: row["failure_category"] for row in payload["route_trace_rows"]}

    assert failures["bad-location"] == trace.FAIL_INVALID_LOCATION
    assert failures["missing-location"] == trace.FAIL_MISSING_LOCATION


def test_location_validation_accepts_pdf_page_variants_and_xlsx_camel_case():
    assert trace.location_valid({"type": "pdf", "page": 1}, file_type="PDF") is True
    assert trace.location_valid({"type": "pdf", "pageNo": 1}, file_type="PDF") is True
    assert trace.location_valid({"type": "pdf", "physical_page_index": 0}, file_type="PDF") is True
    assert trace.location_valid({"type": "xlsx", "sheetName": "Sheet1", "cellRange": "A1:B2"}, file_type="XLSX") is True


def test_allow_unscoped_true_is_a_failure(tmp_path: Path):
    paths = fixture_paths(tmp_path, xlsx_rows=[xlsx_query_result()], xlsx_allow_unscoped=True)

    payload = trace.build_route_trace_report(config(paths, max_xlsx=1, max_pdf=0))
    row = payload["route_trace_rows"][0]

    assert row["allowUnscoped"] is True
    assert trace.FAIL_ALLOW_UNSCOPED in row["failure_categories"]


def test_official_denominator_registry_is_not_written(tmp_path: Path):
    paths = fixture_paths(tmp_path, xlsx_rows=[xlsx_query_result()])
    before = paths["registry"].read_bytes()

    payload = trace.build_route_trace_report(config(paths, max_xlsx=1, max_pdf=0))
    after = paths["registry"].read_bytes()

    assert before == after
    assert payload["official_denominator_changed"] is False
    assert payload["official_denominator_registry_diff"]["official_denominator_changed"] is False


def test_route_report_metadata_is_diagnostic_only_and_no_mutation_execution(tmp_path: Path):
    paths = fixture_paths(tmp_path, xlsx_rows=[xlsx_query_result()])

    payload = trace.build_route_trace_report(config(paths, max_xlsx=1, max_pdf=0))

    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert payload["answer_generation_execution"] == "not_run_by_this_script"
    assert payload["broad_candidate_indexing_execution"] == "not_run_by_this_script"
    assert payload["search_unit_indexing_cli_execution"] == "not_run_by_this_script"
    assert payload["baseline_mutation_execution"] == "not_run_by_this_script"
    assert payload["candidate_artifact_mutation_execution"] == "not_run_by_this_script"
    assert payload["answer_denominators_collapsed"] is False
    assert payload["xlsx_answer_denominator"] == 0
    assert payload["pdf_answer_denominator"] == 0
    assert payload["commands"]["route_trace"].startswith("python scripts\\rag_xlsx_pdf_route_trace_diagnostic.py")


def test_denominator_registry_diff_surfaces_dirty_registry(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, xlsx_rows=[xlsx_query_result()])

    def fake_git_capture(args):
        if args[:2] == ["git", "diff"]:
            return {"ok": True, "stdout": "diff -- official registry\n", "stderr": ""}
        return {"ok": True, "stdout": "", "stderr": ""}

    monkeypatch.setattr(trace, "git_capture", fake_git_capture)
    monkeypatch.setattr(trace, "is_under_root", lambda path: True)
    payload = trace.build_route_trace_report(config(paths, max_xlsx=1, max_pdf=0))

    assert payload["official_denominator_registry_diff"]["git_diff_empty"] is False
    assert payload["official_denominator_changed"] is True
    assert "official_denominator_registry_git_diff_not_empty" in payload["guardrail_failures"]
    assert payload["status"] == trace.STATUS_FAIL


def test_protected_artifact_diff_reports_index_mutation(monkeypatch):
    def fake_git_capture(args):
        if args[:2] == ["git", "status"]:
            return {"ok": True, "stdout": " M ai/eval/indexes/rag-data-pdf-candidate-v1/build.json\n", "stderr": ""}
        return {"ok": True, "stdout": "", "stderr": ""}

    monkeypatch.setattr(trace, "git_capture", fake_git_capture)
    protected = trace.protected_artifact_diff()

    assert protected["protected_artifact_changed"] is True
    assert "rag-data-pdf-candidate-v1" in protected["git_status_entries"][0]


def test_source_report_promotion_evidence_true_fails_guardrail(tmp_path: Path):
    paths = fixture_paths(tmp_path, xlsx_rows=[xlsx_query_result()])
    payload = json.loads(paths["xlsx"].read_text(encoding="utf-8"))
    payload["promotion_evidence"] = True
    write_json(paths["xlsx"], payload)

    report = trace.build_route_trace_report(config(paths, max_xlsx=1, max_pdf=0))

    assert report["status"] == trace.STATUS_FAIL
    assert any(item.startswith("source_report_promotion_evidence_true") for item in report["guardrail_failures"])


def fixture_paths(
    tmp_path: Path,
    *,
    xlsx_rows: list[dict] | None = None,
    pdf_rows: list[dict] | None = None,
    hidden_metrics: dict | None = None,
    xlsx_allow_unscoped: bool = False,
    xlsx_namespace: str | None = None,
    official_route_guard: dict | None = None,
    hidden_negative_row_count: int = 2,
) -> dict[str, Path]:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True)
    paths = {
        "xlsx": reports / "xlsx.json",
        "hidden": reports / "hidden.json",
        "pdf": reports / "pdf.json",
        "registry": tmp_path / "official_denominator_registry.json",
    }
    write_json(
        paths["xlsx"],
        {
            "status": "COMPLETED",
            "promotion_evidence": False,
            "namespace": xlsx_namespace or trace.XLSX_INDEX_VERSION,
            "allowUnscoped": xlsx_allow_unscoped,
            "official_route_guard": official_route_guard or {
                "agent_orchestrator_enabled": False,
                "combined_retrieval_enabled": False,
            },
            "query_results": xlsx_rows or [],
        },
    )
    write_json(
        paths["hidden"],
        {
            "status": "COMPLETED",
            "promotion_evidence": False,
            "hidden_negative_row_count": hidden_negative_row_count,
            "positive_metric_mix_allowed": False,
            "excluded_from_positive_metrics": True,
            "metrics": hidden_metrics
            or {"hidden_content_leakage_count": 0, "hidden_negative_pass_count": 2, "search_error_count": 0},
        },
    )
    write_json(
        paths["pdf"],
        {
            "status": "PASS_WITH_WARNINGS",
            "promotion_evidence": False,
            "namespace": trace.PDF_INDEX_VERSION,
            "allowUnscoped": False,
            "query_results": pdf_rows or [],
        },
    )
    write_json(paths["registry"], {"current_defaults": {"track_a_xlsx": {"official_xlsx_answer_generation_denominator": 0}}})
    return paths


def config(paths: dict[str, Path], *, max_xlsx: int, max_pdf: int):
    return trace.TraceConfig(
        max_xlsx_queries=max_xlsx,
        max_pdf_queries=max_pdf,
        xlsx_report=paths["xlsx"],
        xlsx_hidden_report=paths["hidden"],
        pdf_report=paths["pdf"],
        official_registry=paths["registry"],
    )


def xlsx_query_result(query_id: str = "xlsx-q1", hit: dict | None = None) -> dict:
    return {
        "query_id": query_id,
        "bucket": "xlsx_lookup",
        "query": "lookup",
        "expected_location_type": "xlsx",
        "top_k_results": [hit or xlsx_hit()],
        "final_match_outcome": "matched",
    }


def xlsx_hit(
    citation_text: str = "book.xlsx > Sheet1 > A1:B2",
    location_json=DEFAULT_LOCATION,
    parser_version: str = trace.XLSX_PARSER_VERSION,
) -> dict:
    if location_json is DEFAULT_LOCATION:
        location_json = {"type": "xlsx", "sheet_name": "Sheet1", "cell_range": "A1:B2"}
    return {
        "rank": 1,
        "search_unit_id": "su-xlsx",
        "source_file_name": "book.xlsx",
        "parser_version": parser_version,
        "citation_text": citation_text,
        "location_json": location_json,
        "embedding_status": "EMBEDDED",
        "index_version": trace.XLSX_INDEX_VERSION,
        "match_breakdown": {"identity_match": True, "location_match": True},
    }


def pdf_query_result(query_id: str = "pdf-q1", bucket: str = "pdf_page_lookup", hits: list[dict] | None = None) -> dict:
    return {
        "query_id": query_id,
        "bucket": bucket,
        "query": "find pdf",
        "expected_location_type": "pdf",
        "top_k_results": hits or [pdf_hit()],
        "final_match_outcome": "matched",
    }


def pdf_hit(
    rank: int = 1,
    search_unit_id: str = "su-pdf",
    ocr_used: bool = False,
    identity: bool = True,
    citation_text: str = "doc.pdf > p.1 > bbox [1, 2, 3, 4]",
    location_json=DEFAULT_LOCATION,
    chunk_type: str = "paragraph",
    file_match: bool = True,
) -> dict:
    if location_json is DEFAULT_LOCATION:
        location_json = {
            "type": "pdf",
            "page_no": 1,
            "physical_page_index": 0,
            "ocr_used": ocr_used,
            "bbox": [1, 2, 3, 4],
        }
    return {
        "rank": rank,
        "search_unit_id": search_unit_id,
        "source_file_name": "doc.pdf",
        "source_file_type": "PDF",
        "chunk_type": chunk_type,
        "parser_version": "pdf-extract-v1",
        "citation_text": citation_text,
        "location_json": location_json,
        "embedding_status": "EMBEDDED",
        "index_version": trace.PDF_INDEX_VERSION,
        "match_breakdown": {
            "file_match": file_match,
            "identity_match": identity,
            "location_match": True,
        },
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
