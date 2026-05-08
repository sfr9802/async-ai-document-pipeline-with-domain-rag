from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-worker" / "eval" / "harness" / "xlsx_pdf_route_trace.py"


def load_module():
    spec = importlib.util.spec_from_file_location("xlsx_pdf_route_trace_loop_for_tests", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


trace = load_module()


def test_agentic_loop_retries_at_most_two_times():
    row = {
        "query_id": "q1",
        "query_text": "lookup",
        "file_type": "XLSX",
        "actual_route": trace.ROUTE_XLSX_WRAPPER,
        "route_status": trace.STATUS_FAIL,
        "search_unit_id": "su1",
        "failure_categories": [trace.FAIL_MISSING_CITATION],
    }
    retriever = trace.ScopedRetriever([row])
    controller = trace.RouteRetryController(max_retries=2)

    result = controller.run_case(row, retriever)

    assert result["attempt_count"] == 3
    assert result["max_retries"] == 2
    assert result["retry_exhausted"] is True
    assert all(iteration["allowUnscoped"] is False for iteration in result["iterations"])


def test_pdf_retry_alternates_file_and_content_until_exhausted():
    row = {
        "query_id": "q1",
        "query_text": "lookup",
        "file_type": "PDF",
        "actual_route": trace.ROUTE_PDF_FILE,
        "route_status": trace.STATUS_FAIL,
        "search_unit_id": "su1",
        "failure_categories": [trace.FAIL_FILE_CONTENT_MISMATCH],
    }
    retriever = trace.ScopedRetriever([row])
    controller = trace.RouteRetryController(max_retries=2)

    result = controller.run_case(row, retriever)

    assert [iteration["route"] for iteration in result["iterations"]] == [
        trace.ROUTE_PDF_FILE,
        trace.ROUTE_PDF_CONTENT,
        trace.ROUTE_PDF_FILE,
    ]
    assert result["retry_exhausted"] is True


def test_retry_controller_rejects_retry_bounds_outside_zero_to_two():
    for value in (-1, 3):
        try:
            trace.RouteRetryController(max_retries=value)
        except ValueError as exc:
            assert "max_retries" in str(exc)
        else:  # pragma: no cover - assertion guard
            raise AssertionError("invalid max_retries should fail")


def test_non_retryable_failures_do_not_retry():
    row = {
        "query_id": "q1",
        "query_text": "lookup",
        "file_type": "PDF",
        "actual_route": trace.ROUTE_PDF_FILE,
        "route_status": trace.STATUS_FAIL,
        "search_unit_id": "su1",
        "failure_categories": [trace.FAIL_INDEX_SCOPE],
    }
    result = trace.RouteRetryController(max_retries=2).run_case(row, trace.ScopedRetriever([row]))

    assert result["attempt_count"] == 1
    assert result["retry_exhausted"] is False
    assert result["iterations"][0]["selected_context_ids"] == ["su1"]


def test_agentic_loop_enforces_allow_unscoped_false():
    row = {
        "query_id": "q1",
        "query_text": "lookup",
        "file_type": "PDF",
        "actual_route": trace.ROUTE_PDF_FILE,
        "route_status": trace.STATUS_REVIEW_REQUIRED,
        "search_unit_id": "su1",
        "failure_categories": [],
    }
    retriever = trace.ScopedRetriever([row])

    try:
        retriever.retrieve("q1", route=trace.ROUTE_PDF_FILE, allow_unscoped=True)
    except ValueError as exc:
        assert "allowUnscoped" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("allowUnscoped=true should fail closed")


def test_agentic_report_metadata_is_diagnostic_only(tmp_path: Path):
    route_test = load_route_test_module()
    paths = route_test.fixture_paths(tmp_path, xlsx_rows=[route_test.xlsx_query_result()])
    payload = trace.build_agentic_loop_report(route_test.config(paths, max_xlsx=1, max_pdf=0))

    assert payload["promotion_evidence"] is False
    assert payload["official_denominator_changed"] is False
    assert payload["xlsx_answer_denominator"] == 0
    assert payload["pdf_answer_denominator"] == 0
    assert payload["agentic_loop_execution"] == "bounded_route_verification_only"
    assert payload["agentic_retry_summary"]["allow_unscoped_true_count"] == 0


def test_agentic_report_preserves_source_allow_unscoped_failure(tmp_path: Path):
    route_test = load_route_test_module()
    paths = route_test.fixture_paths(
        tmp_path,
        xlsx_rows=[route_test.xlsx_query_result()],
        xlsx_allow_unscoped=True,
    )

    payload = trace.build_agentic_loop_report(route_test.config(paths, max_xlsx=1, max_pdf=0))
    row = payload["route_trace_rows"][0]

    assert trace.FAIL_ALLOW_UNSCOPED in row["failure_categories"]
    assert payload["failure_category_counts"][trace.FAIL_ALLOW_UNSCOPED] == 1
    assert all(
        iteration["allowUnscoped"] is False
        for loop_row in payload["agentic_route_loop_rows"]
        for iteration in loop_row["iterations"]
    )


def load_route_test_module():
    path = ROOT / "ai-worker" / "tests" / "test_xlsx_pdf_route_trace_diagnostic.py"
    spec = importlib.util.spec_from_file_location("xlsx_pdf_route_trace_diagnostic_helpers", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
