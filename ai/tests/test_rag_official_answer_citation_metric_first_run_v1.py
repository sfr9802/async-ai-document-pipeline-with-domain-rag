from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_official_answer_citation_metric_first_run_v1.py"
REPORT_DIR = ROOT / "reports" / "rag_eval" / "rag-ingestion"
REPORT_ARCHIVE_DIR = REPORT_DIR / "_archive" / "legacy"


def windows_long_path(path: Path) -> Path:
    if sys.platform != "win32":
        return path
    path_text = str(path)
    if path_text.startswith("\\\\?\\"):
        return path
    if path.is_absolute():
        return Path("\\\\?\\" + path_text)
    return path


EXTERNAL_REPORT_ARCHIVE_DIRS = (
    windows_long_path(Path(
        "D:/_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/"
        "rag-ingestion/repo-wide-cleanup-20260521/reports/rag-ingestion-legacy"
    )),
    windows_long_path(Path(
        "D:/_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/"
        "rag-ingestion/repo-wide-cleanup-20260519/reports/rag-ingestion-legacy"
    )),
)


def resolve_report_artifact_path(path: Path) -> Path:
    if path.exists():
        return path
    if path.parent == REPORT_DIR:
        for archive_dir in EXTERNAL_REPORT_ARCHIVE_DIRS:
            archived = archive_dir / path.name
            if archived.exists():
                return archived
        legacy = REPORT_ARCHIVE_DIR / path.name
        if legacy.exists():
            return legacy
    return path


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
    assert report["execution_blocker_category"] is None
    assert report["primary_failure_category"] is None
    assert report["status_detail"] == "SCORED_BASELINE_PASS_WITH_DIAGNOSTIC_WARNINGS"
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
    assert report["execution_blocker_category"] is None
    assert report["primary_failure_category"] == "ANSWER_UNSUPPORTED"
    assert report["status_detail"] == "SCORED_BASELINE_PARTIAL"
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


def test_xlsx_diagnostic_subtype_preserves_official_failure_category(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)

    def scorer(row: Mapping[str, str]) -> dict[str, Any]:
        if row["query_id"] == "gq_xlsx_000":
            return {
                "answer_score": 1.0,
                "citation_support_score": 0.0,
                "failure_category": "CITATION_UNSUPPORTED",
                "failure_detail": "XLSX citation unsupported: leakage_ok=True, locator_match=True, support_match=False",
                "generated_answer": "answer 0",
                "generated_citations": [
                    {
                        "citation_text": "answer 0",
                        "locator": {"range": "A1:D20", "matched_cells": ["A1:D20"]},
                    }
                ],
                "score_details": {
                    "expected_answer": "answer 0",
                    "supporting_evidence": "D1",
                    "xlsx_hidden_excluded_surface_leakage_count": 0,
                },
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

    failed = [row for row in report["row_results"] if row["query_id"] == "gq_xlsx_000"][0]
    assert failed["failure_category"] == "CITATION_UNSUPPORTED"
    assert failed["diagnostic_xlsx_citation_failure_subtype"] == (
        "support_cell_inside_locator_range_but_locator_too_broad"
    )
    assert failed["diagnostic_xlsx_citation_failure_subtype_policy"] == {
        "diagnostic_only": True,
        "official_failure_category_unchanged": True,
        "tuning_target": False,
        "threshold_tuning": False,
        "promotion_evidence": False,
    }
    assert report["diagnostic_xlsx_citation_failure_subtype_counts"] == {
        "support_cell_inside_locator_range_but_locator_too_broad": 1
    }
    assert "SCORER_BACKEND_UNAVAILABLE" not in report["failure_taxonomy"]


def test_xlsx_answer_target_missing_subtype_when_citation_has_value_but_answer_omits_it(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)

    def scorer(row: Mapping[str, str]) -> dict[str, Any]:
        if row["query_id"] == "gq_xlsx_000":
            return {
                "answer_score": 0.0,
                "citation_support_score": 0.0,
                "failure_category": "PARTIAL_OR_UNSUPPORTED",
                "failure_detail": (
                    "generated_answer did not support expected_answer after deterministic normalization; "
                    "XLSX citation unsupported: leakage_ok=True, locator_match=True, support_match=False"
                ),
                "generated_answer": "다른 열만 답했습니다.",
                "generated_citations": [
                    {
                        "citation_text": "target column answer 0",
                        "locator": {"range": "A1:D20", "matched_cells": ["A1:D20"]},
                    }
                ],
                "score_details": {
                    "expected_answer": "answer 0",
                    "supporting_evidence": "D1",
                    "xlsx_hidden_excluded_surface_leakage_count": 0,
                },
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

    failed = [row for row in report["row_results"] if row["query_id"] == "gq_xlsx_000"][0]
    assert failed["failure_category"] == "PARTIAL_OR_UNSUPPORTED"
    assert failed["diagnostic_xlsx_citation_failure_subtype"] == "answer_target_column_missing"
    assert report["track_aggregates"]["xlsx_business_structured"][
        "diagnostic_xlsx_citation_failure_subtype_counts"
    ] == {"answer_target_column_missing": 1}


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
            "--scorer-results-jsonl",
            "",
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


def test_empty_scorer_results_jsonl_fails_closed_before_scoring(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)
    scorer_results = tmp_path / "empty_scorer_results.jsonl"
    scorer_results.write_text("", encoding="utf-8")

    report = module.build_report(
        metric_input_config_path=paths["config"],
        denominator_registry_path=paths["registry"],
        pre_execution_smoke_path=paths["smoke"],
        scorer=module.scorer_from_results_jsonl(scorer_results),
    )

    assert report["status"] == "FAIL_CLOSED_INPUT_VALIDATION"
    assert report["official_metric_execution_started"] is False
    assert report["official_scoring_attempt_count"] == 0
    assert "scorer results row count must be 29, got 0" in report["validation"]["errors"]
    assert any("scorer results missing official query_ids" in error for error in report["validation"]["errors"])


def test_scorer_guardrail_true_flag_fails_closed_before_scoring(tmp_path: Path) -> None:
    module = load_module()
    paths = write_official_fixture_bundle(module, tmp_path)
    scorer_results = tmp_path / "scorer_results.jsonl"
    write_all_pass_scorer_results(scorer_results)
    rows = [json.loads(line) for line in scorer_results.read_text(encoding="utf-8").splitlines()]
    rows[0]["production_mutation"] = True
    scorer_results.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    report = module.build_report(
        metric_input_config_path=paths["config"],
        denominator_registry_path=paths["registry"],
        pre_execution_smoke_path=paths["smoke"],
        scorer=module.scorer_from_results_jsonl(scorer_results),
    )

    assert report["status"] == "FAIL_CLOSED_INPUT_VALIDATION"
    assert report["official_metric_execution_started"] is False
    assert report["official_scoring_attempt_count"] == 0
    assert "scorer result gq_pdf_000 production_mutation must be false" in report["validation"]["errors"]


def test_latest_first_run_artifacts_are_scored_baseline_not_backend_unavailable() -> None:
    report_path = REPORT_DIR / "baseline_v1.json"
    report = read_json(report_path)
    measurements_text = (ROOT / "docs" / "rag-ingestion-measurements.md").read_text(encoding="utf-8")

    assert report["official_scoring_attempt_count"] == 29
    assert report["scored_count"] == 29
    assert report["artifact_paths"]["scorer_results_jsonl"] == (
        "reports/rag_eval/rag-ingestion/scorer_v1.jsonl"
    )
    assert report["execution_blocker_category"] is None
    assert report["primary_failure_category"] == "CITATION_UNSUPPORTED"
    assert report["status_detail"] == "SCORED_BASELINE_PARTIAL"
    assert report["tuning_run_started"] is False
    assert report["promotion_evidence"] is False
    assert report["production_mutation"] is False
    assert "SCORER_BACKEND_UNAVAILABLE" not in json.dumps(report, ensure_ascii=False)
    assert "SCORER_BACKEND_UNAVAILABLE" not in measurements_text
    assert "scorer backend blocker" in measurements_text


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


def write_official_fixture_bundle(module, tmp_path: Path) -> dict[str, Any]:
    module.REPO_ROOT = tmp_path
    eval_queries = tmp_path / "ai" / "eval" / "eval_queries"
    reports = tmp_path / "reports" / "rag_eval" / "rag-ingestion"
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
        "config": reports / "metric_input_v1.json",
        "smoke": reports / "smoke_v1.json",
        "sha_by_track": sha_by_track,
    }
    write_json(paths["registry"], registry_payload(module, csv_paths, sha_by_track))
    write_json(paths["application"], application_payload(module, csv_paths, sha_by_track))
    write_json(paths["config"], config_payload(module, csv_paths, sha_by_track))
    write_json(paths["smoke"], smoke_payload(module, paths, csv_paths, sha_by_track))
    return paths


def write_all_pass_scorer_results(path: Path) -> None:
    query_ids = (
        [f"gq_pdf_{idx:03d}" for idx in range(4)]
        + [f"text_namu_v2_{idx:03d}" for idx in range(3)]
        + ["text_namu_v2_0017"]
        + [f"text_namu_v2_{idx:03d}" for idx in range(4, 6)]
        + [f"gq_xlsx_{idx:03d}" for idx in range(19)]
    )
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for query_id in query_ids:
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


def rows_for_track(track: str, count: int, prefix: str) -> list[dict[str, str]]:
    rows = []
    for idx in range(count):
        query_id = "text_namu_v2_0017" if track == "text_namu_v2_1" and idx == 3 else f"{prefix}_{idx:03d}"
        rows.append(
            {
                "query_id": query_id,
                "question": f"question {query_id}",
                "expected_answer": f"answer {idx}",
                "supporting_evidence": f"D{idx + 1}" if track == "xlsx_business_structured" else f"evidence {idx}",
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
            "registry_application_report": "reports/rag_eval/rag-ingestion/official_question_gold_v2_registry_application_report.json"
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
    return json.loads(resolve_report_artifact_path(path).read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
