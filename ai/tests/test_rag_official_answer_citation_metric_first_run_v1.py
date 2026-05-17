from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_official_answer_citation_metric_first_run_v1.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "rag_official_answer_citation_metric_first_run_v1_for_tests",
        SCRIPT_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_blocked_report_consumes_registry_backed_29_rows_and_preserves_guardrails(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)

    report = module.build_report(
        metric_input_config_path=paths["config"],
        denominator_registry_path=paths["registry"],
        pre_execution_smoke_path=paths["smoke"],
        scorer=None,
    )

    assert report["status"] == "BLOCKED_OR_PARTIAL"
    assert report["blocker_category"] == "SCORER_BACKEND_UNAVAILABLE"
    assert report["official_metric_execution_started"] is False
    assert report["tuning_run_started"] is False
    assert report["promotion_evidence"] is False
    assert report["threshold_tuning"] is False
    assert report["gold_mutation"] is False
    assert report["denominator_mutation"] is False
    assert report["production_mutation"] is False
    assert report["cross_track_averages_computed"] is False
    assert report["winner_selection"] is False
    assert report["official_input_summary"]["row_count"] == 29
    assert report["official_input_summary"]["row_count_by_track"] == {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 6,
        "xlsx_business_structured": 19,
    }
    assert report["consumed_csvs"]["pdf_business_ocr_mm"]["sha256"] == paths["sha_by_track"]["pdf_business_ocr_mm"]
    assert len(report["row_results"]) == 29
    assert all(row["scoring_attempted"] is False for row in report["row_results"])
    assert {row["failure_category"] for row in report["row_results"]} == {"SCORER_BACKEND_UNAVAILABLE"}
    assert report["track_aggregates"]["text_namu_v2_1"]["row_count"] == 6
    assert report["track_aggregates"]["text_namu_v2_1"]["error_count"] == 6
    assert report["skipped_or_error_rows"][0]["failure_category"] == "SCORER_BACKEND_UNAVAILABLE"
    assert report["diagnostic_warnings"] == [
        {
            "query_id": "text_namu_v2_0017",
            "track": "text_namu_v2_1",
            "warning": "potential_support_coverage_gap",
            "reason": "expected_answer_not_exactly_covered_by_cited_chunk_text_after_normalization",
            "diagnostic_only": True,
        }
    ]
    assert "not tuning" in report["run_boundary"]["statement"]
    assert "not promotion evidence" in report["run_boundary"]["statement"]


def test_injected_scorer_marks_execution_started_and_keeps_track_counts_separate(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)

    def scorer(row: Mapping[str, str]) -> dict[str, Any]:
        return {
            "answer_score": 1.0,
            "citation_support_score": 1.0,
            "failure_category": "PASS",
            "failure_detail": "",
        }

    report = module.build_report(
        metric_input_config_path=paths["config"],
        denominator_registry_path=paths["registry"],
        pre_execution_smoke_path=paths["smoke"],
        scorer=scorer,
    )

    assert report["status"] == "PASS_WITH_DIAGNOSTIC_WARNINGS"
    assert report["official_metric_execution_started"] is True
    assert report["official_scoring_attempt_count"] == 29
    assert report["track_aggregates"]["pdf_business_ocr_mm"]["scored_count"] == 4
    assert report["track_aggregates"]["text_namu_v2_1"]["scored_count"] == 6
    assert report["track_aggregates"]["xlsx_business_structured"]["scored_count"] == 19
    assert report["track_aggregates"]["xlsx_business_structured"]["answer_score_pass_count"] == 19
    assert report["track_aggregates"]["xlsx_business_structured"]["citation_support_score_pass_count"] == 19
    assert "cross_track_average" not in json.dumps(report["track_aggregates"], ensure_ascii=False)
    assert report["cross_track_averages_computed"] is False
    assert report["promotion_evidence"] is False
    assert report["tuning_run_started"] is False


def test_sha_mismatch_fails_closed_before_any_scoring_attempt(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)
    registry = read_json(paths["registry"])
    registry["official_diagnostic_denominators"]["track_a_xlsx_question_gold_v2_human_audit_approved"][
        "sha256"
    ] = "bad"
    write_json(paths["registry"], registry)

    def scorer(_row: Mapping[str, str]) -> dict[str, Any]:
        raise AssertionError("scorer must not be called when input validation fails")

    report = module.build_report(
        metric_input_config_path=paths["config"],
        denominator_registry_path=paths["registry"],
        pre_execution_smoke_path=paths["smoke"],
        scorer=scorer,
    )

    assert report["status"] == "FAIL_CLOSED_INPUT_VALIDATION"
    assert report["official_metric_execution_started"] is False
    assert report["official_scoring_attempt_count"] == 0
    assert any("sha256 mismatch against registry" in error for error in report["validation"]["errors"])


def test_partial_scorer_failure_records_taxonomy_fields(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)

    def scorer(row: Mapping[str, str]) -> dict[str, Any]:
        if row["query_id"] == "gq_xlsx_000":
            return {
                "answer_score": 0.0,
                "citation_support_score": 0.0,
                "failure_category": "ANSWER_UNSUPPORTED",
                "failure_detail": "expected answer was not present in generated answer",
            }
        return {
            "answer_score": 1.0,
            "citation_support_score": 1.0,
            "failure_category": "PASS",
            "failure_detail": "",
        }

    report = module.build_report(
        metric_input_config_path=paths["config"],
        denominator_registry_path=paths["registry"],
        pre_execution_smoke_path=paths["smoke"],
        scorer=scorer,
    )

    assert report["status"] == "BLOCKED_OR_PARTIAL"
    assert report["official_metric_execution_started"] is True
    failed = [row for row in report["row_results"] if row["query_id"] == "gq_xlsx_000"][0]
    assert failed["answer_score"] == 0.0
    assert failed["citation_support_score"] == 0.0
    assert failed["failure_category"] == "ANSWER_UNSUPPORTED"
    assert failed["failure_detail"] == "expected answer was not present in generated answer"
    assert report["track_aggregates"]["xlsx_business_structured"]["failure_category_counts"][
        "ANSWER_UNSUPPORTED"
    ] == 1
    assert report["skipped_or_error_rows"] == [
        {
            "query_id": "gq_xlsx_000",
            "track": "xlsx_business_structured",
            "failure_category": "ANSWER_UNSUPPORTED",
            "failure_detail": "expected answer was not present in generated answer",
        }
    ]


def test_cli_returns_nonzero_when_backend_unavailable_but_writes_report(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)
    output_json = tmp_path / "first_run.json"
    output_md = tmp_path / "first_run.md"

    exit_code = module.main(
        [
            "--metric-input-config",
            str(paths["config"]),
            "--denominator-registry",
            str(paths["registry"]),
            "--pre-execution-smoke",
            str(paths["smoke"]),
            "--disable-scorer-backend",
            "--output-report",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
    )

    assert exit_code == 3
    report = read_json(output_json)
    assert report["status"] == "BLOCKED_OR_PARTIAL"
    assert report["blocker_category"] == "SCORER_BACKEND_UNAVAILABLE"
    assert report["official_metric_execution_started"] is False
    assert output_md.exists()


def test_cli_runs_configured_backend_and_writes_official_scorer_results_jsonl(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)
    write_generation_artifacts_for_fixture(module, tmp_path)
    output_json = tmp_path / "first_run.json"
    scorer_results = tmp_path / "official_scorer_results.jsonl"

    exit_code = module.main(
        [
            "--metric-input-config",
            str(paths["config"]),
            "--denominator-registry",
            str(paths["registry"]),
            "--pre-execution-smoke",
            str(paths["smoke"]),
            "--scorer-results-output",
            str(scorer_results),
            "--output-report",
            str(output_json),
            "--output-md",
            str(tmp_path / "first_run.md"),
        ]
    )

    report = read_json(output_json)
    result_rows = [json.loads(line) for line in scorer_results.read_text(encoding="utf-8").splitlines()]
    assert exit_code == 0
    assert report["status"] == "PASS_WITH_DIAGNOSTIC_WARNINGS"
    assert report["blocker_category"] is None
    assert report["official_metric_execution_started"] is True
    assert report["official_scoring_attempt_count"] == 29
    assert report["scored_count"] == 29
    assert report["skipped_count"] == 0
    assert report["error_count"] == 0
    assert report["artifact_paths"]["scorer_results_jsonl"] == module.repo_relative(scorer_results)
    assert len(result_rows) == 29
    assert {row["scorer_backend_name"] for row in result_rows} == {"official_deterministic_artifact_scorer"}
    assert all(row["production_mutation"] is False for row in result_rows)
    assert all(row["scoring_attempted"] is True for row in result_rows)
    assert all(row["failure_category"] == "PASS" for row in result_rows)
    first_row = report["row_results"][0]
    assert first_row["generated_answer"]
    assert first_row["generated_citations"]
    assert first_row["scorer_backend_name"] == "official_deterministic_artifact_scorer"
    assert report["baseline_metric_policy"]["cross_track_average"] == "not optimization, not tuning target"
    assert report["production_mutation"] is False
    assert report["denominator_mutation"] is False
    assert report["gold_mutation"] is False
    assert report["promotion_evidence"] is False
    assert report["tuning_run_started"] is False
    assert report["threshold_tuning"] is False


def test_cli_skips_builtin_backend_when_input_validation_fails(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)
    write_generation_artifacts_for_fixture(module, tmp_path)
    registry = read_json(paths["registry"])
    registry["official_diagnostic_denominators"]["track_a_xlsx_question_gold_v2_human_audit_approved"][
        "sha256"
    ] = "bad"
    write_json(paths["registry"], registry)
    output_json = tmp_path / "first_run.json"
    scorer_results = tmp_path / "official_scorer_results.jsonl"

    exit_code = module.main(
        [
            "--metric-input-config",
            str(paths["config"]),
            "--denominator-registry",
            str(paths["registry"]),
            "--pre-execution-smoke",
            str(paths["smoke"]),
            "--scorer-results-output",
            str(scorer_results),
            "--output-report",
            str(output_json),
            "--output-md",
            str(tmp_path / "first_run.md"),
        ]
    )

    report = read_json(output_json)
    assert exit_code == 2
    assert not scorer_results.exists()
    assert report["status"] == "FAIL_CLOSED_INPUT_VALIDATION"
    assert report["official_metric_execution_started"] is False
    assert report["official_scoring_attempt_count"] == 0
    assert report["scorer_backend"]["backend_skipped_before_execution"] is True
    assert report["scorer_backend"]["validation"]["ok"] is False


def test_cli_can_consume_official_scorer_results_jsonl(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)
    scorer_results = tmp_path / "scorer_results.jsonl"
    write_all_pass_scorer_results(scorer_results)
    output_json = tmp_path / "first_run.json"

    exit_code = module.main(
        [
            "--metric-input-config",
            str(paths["config"]),
            "--denominator-registry",
            str(paths["registry"]),
            "--pre-execution-smoke",
            str(paths["smoke"]),
            "--scorer-results-jsonl",
            str(scorer_results),
            "--output-report",
            str(output_json),
            "--output-md",
            str(tmp_path / "first_run.md"),
        ]
    )

    report = read_json(output_json)
    assert exit_code == 0
    assert report["status"] == "PASS_WITH_DIAGNOSTIC_WARNINGS"
    assert report["official_metric_execution_started"] is True
    assert report["official_scoring_attempt_count"] == 29
    assert report["track_aggregates"]["pdf_business_ocr_mm"]["scored_count"] == 4
    assert report["track_aggregates"]["xlsx_business_structured"]["scored_count"] == 19


def test_missing_official_query_in_scorer_jsonl_is_result_missing(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)
    scorer_results = tmp_path / "scorer_results.jsonl"
    write_all_pass_scorer_results(scorer_results, skip_query_id="gq_xlsx_000")
    output_json = tmp_path / "first_run.json"

    exit_code = module.main(
        [
            "--metric-input-config",
            str(paths["config"]),
            "--denominator-registry",
            str(paths["registry"]),
            "--pre-execution-smoke",
            str(paths["smoke"]),
            "--scorer-results-jsonl",
            str(scorer_results),
            "--output-report",
            str(output_json),
            "--output-md",
            str(tmp_path / "first_run.md"),
        ]
    )

    report = read_json(output_json)
    missing = [row for row in report["row_results"] if row["query_id"] == "gq_xlsx_000"][0]
    assert exit_code == 4
    assert report["blocker_category"] == "SCORER_RESULT_MISSING"
    assert missing["failure_category"] == "SCORER_RESULT_MISSING"
    assert missing["scoring_attempted"] is True


def test_cli_fail_closes_on_duplicate_extra_scorer_result_row(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)
    scorer_results = tmp_path / "scorer_results.jsonl"
    write_all_pass_scorer_results(scorer_results)
    with scorer_results.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(
                {
                    "query_id": "gq_xlsx_000",
                    "answer_score": 0.0,
                    "citation_support_score": 0.0,
                    "failure_category": "ANSWER_UNSUPPORTED",
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    output_json = tmp_path / "first_run.json"

    exit_code = module.main(
        [
            "--metric-input-config",
            str(paths["config"]),
            "--denominator-registry",
            str(paths["registry"]),
            "--pre-execution-smoke",
            str(paths["smoke"]),
            "--scorer-results-jsonl",
            str(scorer_results),
            "--output-report",
            str(output_json),
            "--output-md",
            str(tmp_path / "first_run.md"),
        ]
    )

    report = read_json(output_json)
    assert exit_code == 2
    assert report["status"] == "FAIL_CLOSED_INPUT_VALIDATION"
    assert report["official_scoring_attempt_count"] == 0
    assert any("duplicate scorer result query_id gq_xlsx_000" in error for error in report["validation"]["errors"])


def test_source_guardrail_flags_fail_closed_before_scoring(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)
    application = read_json(paths["application"])
    application["promotion_evidence"] = True
    write_json(paths["application"], application)
    smoke = read_json(paths["smoke"])
    smoke["artifact_consistency"]["registry_application_report_sha256"] = module.sha256_file(paths["application"])
    write_json(paths["smoke"], smoke)

    def scorer(_row: Mapping[str, str]) -> dict[str, Any]:
        raise AssertionError("scorer must not be called when upstream guardrails fail")

    report = module.build_report(
        metric_input_config_path=paths["config"],
        denominator_registry_path=paths["registry"],
        pre_execution_smoke_path=paths["smoke"],
        scorer=scorer,
    )

    assert report["status"] == "FAIL_CLOSED_INPUT_VALIDATION"
    assert report["official_scoring_attempt_count"] == 0
    assert "registry application report promotion_evidence must be false" in report["validation"]["errors"]


def test_malformed_pass_scorer_result_is_invalid(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)

    def scorer(_row: Mapping[str, str]) -> dict[str, Any]:
        return {"failure_category": "PASS"}

    report = module.build_report(
        metric_input_config_path=paths["config"],
        denominator_registry_path=paths["registry"],
        pre_execution_smoke_path=paths["smoke"],
        scorer=scorer,
    )

    assert report["status"] == "BLOCKED_OR_PARTIAL"
    assert report["blocker_category"] == "SCORER_INVALID_RESULT"
    assert {row["failure_category"] for row in report["row_results"]} == {"SCORER_INVALID_RESULT"}


def test_answer_citation_score_combinations_are_classified_without_scorer_labels(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)

    outcomes = {
        "gq_pdf_000": {"answer_score": 1.0, "citation_support_score": 0.0},
        "gq_pdf_001": {"answer_score": 0.0, "citation_support_score": 1.0},
        "gq_pdf_002": {"answer_score": 0.0, "citation_support_score": 0.0},
    }

    def scorer(row: Mapping[str, str]) -> dict[str, Any]:
        return outcomes.get(
            row["query_id"],
            {"answer_score": 1.0, "citation_support_score": 1.0},
        )

    report = module.build_report(
        metric_input_config_path=paths["config"],
        denominator_registry_path=paths["registry"],
        pre_execution_smoke_path=paths["smoke"],
        scorer=scorer,
    )

    by_id = {row["query_id"]: row for row in report["row_results"]}
    assert by_id["gq_pdf_000"]["failure_category"] == "CITATION_UNSUPPORTED"
    assert by_id["gq_pdf_001"]["failure_category"] == "ANSWER_UNSUPPORTED"
    assert by_id["gq_pdf_002"]["failure_category"] == "PARTIAL_OR_UNSUPPORTED"


def test_xlsx_hidden_excluded_leakage_guardrail_blocks_citation_pass(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)
    write_generation_artifacts_for_fixture(module, tmp_path, xlsx_surface_leakage_count=1)
    output_json = tmp_path / "first_run.json"

    exit_code = module.main(
        [
            "--metric-input-config",
            str(paths["config"]),
            "--denominator-registry",
            str(paths["registry"]),
            "--pre-execution-smoke",
            str(paths["smoke"]),
            "--scorer-results-output",
            str(tmp_path / "official_scorer_results.jsonl"),
            "--output-report",
            str(output_json),
            "--output-md",
            str(tmp_path / "first_run.md"),
        ]
    )

    report = read_json(output_json)
    xlsx_rows = [row for row in report["row_results"] if row["track"] == "xlsx_business_structured"]
    assert exit_code == 4
    assert report["blocker_category"] == "CITATION_UNSUPPORTED"
    assert {row["failure_category"] for row in xlsx_rows} == {"CITATION_UNSUPPORTED"}
    assert all(row["answer_score"] == 1.0 for row in xlsx_rows)
    assert all(row["citation_support_score"] == 0.0 for row in xlsx_rows)


def test_generation_artifact_load_errors_fail_closed_for_affected_track(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)
    write_generation_artifacts_for_fixture(module, tmp_path)
    xlsx_jsonl = tmp_path / "ai" / "eval" / "reports" / "rag-ingestion" / "xlsx_answer_citation_diagnostic_review_input.jsonl"
    first_line = xlsx_jsonl.read_text(encoding="utf-8").splitlines()[0]
    with xlsx_jsonl.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(first_line + "\n")
    output_json = tmp_path / "first_run.json"

    exit_code = module.main(
        [
            "--metric-input-config",
            str(paths["config"]),
            "--denominator-registry",
            str(paths["registry"]),
            "--pre-execution-smoke",
            str(paths["smoke"]),
            "--scorer-results-output",
            str(tmp_path / "official_scorer_results.jsonl"),
            "--output-report",
            str(output_json),
            "--output-md",
            str(tmp_path / "first_run.md"),
        ]
    )

    report = read_json(output_json)
    xlsx_rows = [row for row in report["row_results"] if row["track"] == "xlsx_business_structured"]
    assert exit_code == 4
    assert report["blocker_category"] == "SCORER_EXCEPTION"
    assert {row["failure_category"] for row in xlsx_rows} == {"SCORER_EXCEPTION"}
    assert all("duplicate scorer result query_id" in row["failure_detail"] for row in xlsx_rows)


def test_scorer_result_mutation_flags_are_invalid(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)

    def scorer(_row: Mapping[str, str]) -> dict[str, Any]:
        return {
            "answer_score": 1.0,
            "citation_support_score": 1.0,
            "failure_category": "PASS",
            "production_mutation": True,
            "promotion_evidence": True,
            "threshold_tuning": True,
            "denominator_mutation": True,
            "gold_mutation": True,
        }

    report = module.build_report(
        metric_input_config_path=paths["config"],
        denominator_registry_path=paths["registry"],
        pre_execution_smoke_path=paths["smoke"],
        scorer=scorer,
    )

    assert report["status"] == "BLOCKED_OR_PARTIAL"
    assert report["blocker_category"] == "SCORER_INVALID_RESULT"
    assert {row["failure_category"] for row in report["row_results"]} == {"SCORER_INVALID_RESULT"}
    assert all("forbidden scorer result guardrail flag" in row["failure_detail"] for row in report["row_results"])
    assert all(row["production_mutation"] is False for row in report["row_results"])


def test_expected_answer_subset_does_not_pass_directional_matching(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)
    write_generation_artifacts_for_fixture(module, tmp_path)
    pdf_jsonl = tmp_path / "ai" / "eval" / "reports" / "rag-ingestion" / "pdf_answer_citation_diagnostic_review_input.jsonl"
    rows = read_jsonl(pdf_jsonl)
    rows[0]["generated_answer"] = "answer"
    write_jsonl(pdf_jsonl, rows)
    output_json = tmp_path / "first_run.json"

    exit_code = module.main(
        [
            "--metric-input-config",
            str(paths["config"]),
            "--denominator-registry",
            str(paths["registry"]),
            "--pre-execution-smoke",
            str(paths["smoke"]),
            "--scorer-results-output",
            str(tmp_path / "official_scorer_results.jsonl"),
            "--output-report",
            str(output_json),
            "--output-md",
            str(tmp_path / "first_run.md"),
        ]
    )

    report = read_json(output_json)
    failed = [row for row in report["row_results"] if row["query_id"] == "gq_pdf_000"][0]
    assert exit_code == 4
    assert failed["answer_score"] == 0.0
    assert failed["failure_category"] == "ANSWER_UNSUPPORTED"


def test_xlsx_internal_formatter_input_does_not_support_or_emit_citation_surface(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)
    write_generation_artifacts_for_fixture(module, tmp_path)
    xlsx_jsonl = tmp_path / "ai" / "eval" / "reports" / "rag-ingestion" / "xlsx_answer_citation_diagnostic_review_input.jsonl"
    rows = read_jsonl(xlsx_jsonl)
    rows[0]["citation_items"][0]["citation_text"] = "public citation without answer"
    rows[0]["formatter_input"]["nearby_rows"] = [{"row_text": "hidden internal answer 0"}]
    write_jsonl(xlsx_jsonl, rows)
    output_json = tmp_path / "first_run.json"

    exit_code = module.main(
        [
            "--metric-input-config",
            str(paths["config"]),
            "--denominator-registry",
            str(paths["registry"]),
            "--pre-execution-smoke",
            str(paths["smoke"]),
            "--scorer-results-output",
            str(tmp_path / "official_scorer_results.jsonl"),
            "--output-report",
            str(output_json),
            "--output-md",
            str(tmp_path / "first_run.md"),
        ]
    )

    report = read_json(output_json)
    failed = [row for row in report["row_results"] if row["query_id"] == "gq_xlsx_000"][0]
    assert exit_code == 4
    assert failed["failure_category"] == "CITATION_UNSUPPORTED"
    assert failed["citation_support_score"] == 0.0
    assert failed["retrieved_support"] == ["public citation without answer"]


def write_official_fixture_bundle(module, tmp_path: Path) -> dict[str, Any]:
    module.REPO_ROOT = tmp_path
    eval_queries = tmp_path / "ai" / "eval" / "eval_queries"
    reports = tmp_path / "ai" / "eval" / "reports" / "rag-ingestion"
    eval_queries.mkdir(parents=True)
    reports.mkdir(parents=True)

    csv_paths = {
        "pdf_business_ocr_mm": eval_queries / "gold_queries_pdf_question_gold_v2.csv",
        "text_namu_v2_1": eval_queries / "gold_queries_text_namu_v2_1_question_gold_v2.csv",
        "xlsx_business_structured": eval_queries / "gold_queries_xlsx_question_gold_v2.csv",
    }
    write_csv(csv_paths["pdf_business_ocr_mm"], rows_for_track("pdf_business_ocr_mm", 4, "gq_pdf"))
    write_csv(csv_paths["text_namu_v2_1"], rows_for_track("text_namu_v2_1", 6, "text_namu_v2"))
    write_csv(csv_paths["xlsx_business_structured"], rows_for_track("xlsx_business_structured", 19, "gq_xlsx"))

    sha_by_track = {track: module.sha256_file(path) for track, path in csv_paths.items()}
    paths = {
        "registry": eval_queries / "official_denominator_registry.json",
        "application": reports / "official_question_gold_v2_registry_application_report.json",
        "config": reports / "official_metric_input_config_v1.json",
        "smoke": reports / "official_metric_pre_execution_smoke_report_v1.json",
        "sha_by_track": sha_by_track,
    }
    write_json(paths["registry"], registry_payload(module, csv_paths, sha_by_track))
    write_json(paths["application"], application_payload(module, csv_paths, sha_by_track))
    write_json(paths["config"], config_payload(module, csv_paths, sha_by_track))
    write_json(paths["smoke"], smoke_payload(module, paths, csv_paths, sha_by_track))
    return paths


def write_all_pass_scorer_results(path: Path, *, skip_query_id: str = "") -> None:
    query_ids = (
        [f"gq_pdf_{idx:03d}" for idx in range(4)]
        + [f"text_namu_v2_{idx:03d}" for idx in range(3)]
        + ["text_namu_v2_0017"]
        + [f"text_namu_v2_{idx:03d}" for idx in range(4, 6)]
        + [f"gq_xlsx_{idx:03d}" for idx in range(19)]
    )
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for query_id in query_ids:
            if query_id == skip_query_id:
                continue
            handle.write(
                json.dumps(
                    {
                        "query_id": query_id,
                        "answer_score": 1.0,
                        "citation_support_score": 1.0,
                        "failure_category": "PASS",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def write_generation_artifacts_for_fixture(
    module,
    tmp_path: Path,
    *,
    xlsx_surface_leakage_count: int = 0,
) -> None:
    reports = tmp_path / "ai" / "eval" / "reports" / "rag-ingestion"
    review = tmp_path / "ai" / "eval" / "review"
    reports.mkdir(parents=True, exist_ok=True)
    review.mkdir(parents=True, exist_ok=True)

    pdf_rows = rows_for_track("pdf_business_ocr_mm", 4, "gq_pdf")
    xlsx_rows = rows_for_track("xlsx_business_structured", 19, "gq_xlsx")
    text_rows = rows_for_track("text_namu_v2_1", 6, "text_namu_v2")

    write_jsonl(
        reports / "pdf_answer_citation_diagnostic_review_input.jsonl",
        [generation_row_from_gold(row) for row in pdf_rows],
    )
    write_jsonl(
        reports / "xlsx_answer_citation_diagnostic_review_input.jsonl",
        [xlsx_generation_row_from_gold(row) for row in xlsx_rows],
    )
    write_json(
        reports / "xlsx_answer_citation_hidden_excluded_leakage_reprobe.json",
        {
            "status": "PASS" if xlsx_surface_leakage_count == 0 else "FAIL",
            "counts": {"surface_leakage_count": xlsx_surface_leakage_count},
            "guardrails": {
                "hidden_excluded_content_exposed": xlsx_surface_leakage_count > 0,
                "production_namespace_mutated": False,
                "production_vector_index_mutated": False,
                "production_vector_written": False,
            },
        },
    )
    write_json(
        review / "rag_text_namu_answer_citation_policy_review_packet_v2_1.json",
        {
            "status": "POLICY_REVIEW_PACKET_READY",
            "diagnostic_only": True,
            "not_official_metric": True,
            "promotion_evidence": False,
            "user_review": {
                "rows_requiring_human_decision": [
                    text_packet_row_from_gold(row) for row in text_rows
                ]
            },
        },
    )


def generation_row_from_gold(row: Mapping[str, str]) -> dict[str, Any]:
    locator = json.loads(row["citation_locator"])
    return {
        "query_id": row["query_id"],
        "track": row["track"],
        "generated_answer": row["expected_answer"],
        "answer_claims": [row["expected_answer"]],
        "citation_items": [
            {
                "citation_text": row["supporting_evidence"],
                "citation_locator": locator,
                "locator": locator,
                "search_unit_id": locator.get("search_unit_id", ""),
            }
        ],
        "citation_locator": locator,
        "matched_text": row["supporting_evidence"],
        "nearby_paragraphs": [row["supporting_evidence"]],
        "citation_locator_valid": True,
        "citation_text_matches_source_bound_evidence": True,
        "bucket": "clean_pass",
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
    }


def xlsx_generation_row_from_gold(row: Mapping[str, str]) -> dict[str, Any]:
    payload = generation_row_from_gold(row)
    locator = payload["citation_locator"]
    payload["formatter_input"] = {
        "citation_locator_metadata": {
            "file": locator.get("file", ""),
            "sheet": locator.get("sheet", ""),
            "range": locator.get("range", ""),
            "document_version_id": locator.get("document_version_id", ""),
            "search_unit_id": locator.get("search_unit_id", ""),
        },
        "matched_cells": locator.get("matched_cells", []),
        "target_rows": locator.get("target_rows", []),
        "target_columns": locator.get("target_columns", []),
        "row_values": [{"column_label": "answer", "value": row["expected_answer"]}],
        "nearby_rows": [{"row_text": row["supporting_evidence"]}],
    }
    payload["citation_items"] = [
        {
            "citation_text": row["supporting_evidence"] + " " + row["expected_answer"],
            "citation_type": "xlsx_sheet_range",
            "locator": {
                "file": locator.get("file", ""),
                "sheet": locator.get("sheet", ""),
                "range": locator.get("range", ""),
                "matched_cells": locator.get("matched_cells", []),
                "target_rows": locator.get("target_rows", []),
                "target_columns": locator.get("target_columns", []),
                "document_version_id": locator.get("document_version_id", ""),
                "search_unit_id": locator.get("search_unit_id", ""),
            },
        }
    ]
    payload["verifier"] = {
        "answer_claim_support_status": "PASS",
        "citation_locator_status": "PASS",
        "flattened_only_status": "PASS",
    }
    return payload


def text_packet_row_from_gold(row: Mapping[str, str]) -> dict[str, Any]:
    locator = json.loads(row["citation_locator"])
    return {
        "query_id": row["query_id"],
        "query": row["question"],
        "generated_short_answer": row["expected_answer"],
        "suggested_extractive_answer_not_gold": row["expected_answer"],
        "evidence_spans": [row["supporting_evidence"]],
        "cited_chunk_ids": locator.get("cited_chunk_ids", []),
        "assistant_review_action": "KEEP_WITH_CLEANUP",
        "assistant_answer_judgment": "source_supported_rewrite",
        "assistant_citation_support_judgment": "fully_supported",
        "failure_causes": [],
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
    }


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rows_for_track(track: str, count: int, prefix: str) -> list[dict[str, str]]:
    rows = []
    for idx in range(count):
        query_id = "text_namu_v2_0017" if track == "text_namu_v2_1" and idx == 3 else f"{prefix}_{idx:03d}"
        rows.append(
            {
                "query_id": query_id,
                "question": f"question {query_id}",
                "expected_answer": f"answer {idx}",
                "supporting_evidence": f"evidence {idx}",
                "track": track,
                "citation_locator": json.dumps(locator_for_track(track, idx), ensure_ascii=False),
                "human_label": "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE",
                "human_review_status": "USER_REVIEWED_APPROVED",
                "human_approved_gold": "TRUE",
                "model_assisted_source": "TRUE",
                "model_assisted_diagnostic_only_before_human_approval": "TRUE",
                "official_denominator_current": "TRUE",
                "official_metric_input": "TRUE",
                "promotion_evidence": "FALSE",
                "gold_promoted": "TRUE",
            }
        )
    return rows


def locator_for_track(track: str, idx: int) -> dict[str, Any]:
    if track == "pdf_business_ocr_mm":
        return {"page": idx + 1, "bbox": [1, 2, 3, 4], "region_type": "paragraph", "search_unit_id": f"su-pdf-{idx}"}
    if track == "text_namu_v2_1":
        return {"cited_chunk_ids": [f"chunk-{idx}"]}
    return {
        "file": "book.xlsx",
        "sheet": "Sheet1",
        "range": "A1:D20",
        "matched_cells": [f"D{idx + 1}"],
        "search_unit_id": f"su-xlsx-{idx}",
        "document_version_id": f"docv-{idx}",
    }


def registry_payload(module, csv_paths: Mapping[str, Path], sha_by_track: Mapping[str, str]) -> dict[str, Any]:
    return {
        "schema_version": "official_denominator_registry_v1",
        "official_diagnostic_denominators": {
            "track_c_pdf_question_gold_v2_human_audit_approved": registry_entry(
                module, csv_paths["pdf_business_ocr_mm"], 4, sha_by_track["pdf_business_ocr_mm"]
            ),
            "track_b_text_namu_v2_1_question_gold_v2_human_audit_approved": registry_entry(
                module, csv_paths["text_namu_v2_1"], 6, sha_by_track["text_namu_v2_1"]
            ),
            "track_a_xlsx_question_gold_v2_human_audit_approved": registry_entry(
                module, csv_paths["xlsx_business_structured"], 19, sha_by_track["xlsx_business_structured"]
            ),
        },
    }


def registry_entry(module, path: Path, rows: int, sha: str) -> dict[str, Any]:
    return {
        "path": module.repo_relative(path),
        "row_count": rows,
        "official_metric_input_rows": rows,
        "sha256": sha,
        "denominator_kind": "question_answer_citation_gold_v2",
        "metric_lane": "answer_citation",
    }


def application_payload(module, csv_paths: Mapping[str, Path], sha_by_track: Mapping[str, str]) -> dict[str, Any]:
    return {
        "status": "OFFICIAL_QUESTION_GOLD_V2_REGISTRY_APPLIED",
        "promotion_evidence": False,
        "official_metric_execution_started": False,
        "tuning_run_started": False,
        "official_metric_input_rows": 29,
        "official_metric_input_rows_by_track": {"pdf_business_ocr_mm": 4, "text_namu_v2_1": 6, "xlsx_business_structured": 19},
        "official_metric_input_artifacts": artifact_map(module, csv_paths, sha_by_track),
    }


def config_payload(module, csv_paths: Mapping[str, Path], sha_by_track: Mapping[str, str]) -> dict[str, Any]:
    artifacts = artifact_map(module, csv_paths, sha_by_track)
    return {
        "status": "OFFICIAL_METRIC_INPUT_CONFIG_READY_REGISTRY_BACKED_NOT_EXECUTED",
        "promotion_evidence": False,
        "official_metric": False,
        "official_metric_execution_started": False,
        "metric_execution_allowed": True,
        "metric_execution_requires_explicit_command": True,
        "tuning_run_started": False,
        "cross_track_average_optimization_allowed": False,
        "cross_track_averages_computed": False,
        "official_metric_input_rows": 29,
        "official_metric_input_rows_by_track": {"pdf_business_ocr_mm": 4, "text_namu_v2_1": 6, "xlsx_business_structured": 19},
        "official_metric_input_artifacts": artifacts,
        "metric_lanes": artifacts,
        "source_artifacts": {
            "registry_application_report": "ai/eval/reports/rag-ingestion/official_question_gold_v2_registry_application_report.json"
        },
        "validation": {"ok": True, "errors": []},
    }


def smoke_payload(module, paths: Mapping[str, Any], csv_paths: Mapping[str, Path], sha_by_track: Mapping[str, str]) -> dict[str, Any]:
    return {
        "schema_version": "official_metric_pre_execution_smoke_report_v1",
        "status": "OFFICIAL_METRIC_PRE_EXECUTION_SMOKE_PASS_WITH_DIAGNOSTIC_WARNINGS",
        "official_metric_execution_started": False,
        "tuning_run_started": False,
        "promotion_evidence": False,
        "promotion_evidence_created": False,
        "artifact_consistency": {
            "config_sha256": module.sha256_file(paths["config"]),
            "registry_sha256": module.sha256_file(paths["registry"]),
            "registry_application_report_sha256": module.sha256_file(paths["application"]),
            "metric_lanes": artifact_map(module, csv_paths, sha_by_track),
        },
        "csv_checks": artifact_map(module, csv_paths, sha_by_track),
        "official_input_summary": {
            "row_count": 29,
            "row_count_by_track": {"pdf_business_ocr_mm": 4, "text_namu_v2_1": 6, "xlsx_business_structured": 19},
        },
        "text_support_diagnostic": {
            "potential_support_coverage_gap": [
                {
                    "query_id": "text_namu_v2_0017",
                    "reason": "expected_answer_not_exactly_covered_by_cited_chunk_text_after_normalization",
                    "diagnostic_only": True,
                }
            ]
        },
        "guardrails": {
            "official_metric_execution_started": False,
            "tuning_run_started": False,
            "promotion_evidence": False,
            "promotion_evidence_created": False,
        },
        "validation": {"ok": True, "errors": [], "warnings": ["TEXT expected_answer support coverage has diagnostic-only potential gaps"]},
    }


def artifact_map(module, csv_paths: Mapping[str, Path], sha_by_track: Mapping[str, str]) -> dict[str, Any]:
    keys = {
        "pdf_business_ocr_mm": "track_c_pdf_question_gold_v2_human_audit_approved",
        "text_namu_v2_1": "track_b_text_namu_v2_1_question_gold_v2_human_audit_approved",
        "xlsx_business_structured": "track_a_xlsx_question_gold_v2_human_audit_approved",
    }
    rows = {"pdf_business_ocr_mm": 4, "text_namu_v2_1": 6, "xlsx_business_structured": 19}
    return {
        track: {
            "path": module.repo_relative(path),
            "csv_path": module.repo_relative(path),
            "candidate_path": module.repo_relative(path),
            "row_count": rows[track],
            "official_metric_input_rows_current": rows[track],
            "sha256": sha_by_track[track],
            "denominator_key": keys[track],
            "metric_lane": "answer_citation",
        }
        for track, path in csv_paths.items()
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
