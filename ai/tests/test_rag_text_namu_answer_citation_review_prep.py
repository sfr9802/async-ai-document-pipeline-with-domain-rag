from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_text_namu_answer_citation_review_prep.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_text_namu_answer_citation_review_prep", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prep = load_module()


def test_text_answer_citation_denominator_remains_closed_by_default(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    report = prep.build_report(**paths)

    assert report["status"] == "BLOCKED_GENERATED_ANSWER_OUTPUT_MISSING"
    assert report["diagnostic_only"] is True
    assert report["promotion_evidence"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["official_denominator_policy"]["text_answer_citation_official_denominator_opened"] is False
    assert report["guardrails"]["text_answer_denominator_opened"] is False
    assert report["guardrails"]["text_citation_support_denominator_opened"] is False
    assert report["citation_support_metric_runner"]["status"] == "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY"


def test_partial_generated_answer_outputs_do_not_make_report_ready(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    answers = tmp_path / "answers.jsonl"
    write_jsonl(
        answers,
        [
            generated_answer_row("text_001"),
        ],
    )
    paths["generated_answer_artifacts"] = [answers]

    report = prep.build_report(**paths)

    assert report["status"] == "BLOCKED_GENERATED_ANSWER_OUTPUT_MISSING"
    assert report["generated_answer_availability"]["actual_generated_answer_query_ids"] == ["text_001"]
    assert report["answer_citation_review_preparation"]["generated_answer_missing_query_ids"] == ["text_002"]
    assert report["answer_citation_review_preparation"]["generated_answer_missing_counted_as_failure"] is False


def test_boolean_only_generated_answer_rows_are_not_actual_outputs(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    answers = tmp_path / "answers.jsonl"
    write_jsonl(
        answers,
        [
            {
                "query_id": "text_001",
                "live_llm_run": True,
                "official_metric_input": False,
            }
        ],
    )
    paths["generated_answer_artifacts"] = [answers]

    report = prep.build_report(**paths)

    assert report["generated_answer_availability"]["actual_generated_answer_row_count"] == 0
    assert report["answer_citation_review_preparation"]["generated_answer_missing_count"] == 2
    assert report["status"] == "BLOCKED_GENERATED_ANSWER_OUTPUT_MISSING"


def test_generated_answer_official_metric_leakage_fails_closed(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    answers = tmp_path / "answers.jsonl"
    write_jsonl(
        answers,
        [
            generated_answer_row("text_001", official_metric_input=True),
            generated_answer_row("text_002"),
        ],
    )
    paths["generated_answer_artifacts"] = [answers]

    report = prep.build_report(**paths)

    assert report["status"] == "FAIL"
    assert report["official_metric_input_rows"] == 1
    assert "official_metric_input_rows must remain 0" in report["validation"]["errors"]


def test_generated_answer_rows_missing_cited_chunk_ids_fail_closed(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    answers = tmp_path / "answers.jsonl"
    write_jsonl(
        answers,
        [
            generated_answer_row("text_001", cited_chunk_ids=[]),
            generated_answer_row("text_002"),
        ],
    )
    paths["generated_answer_artifacts"] = [answers]

    report = prep.build_report(**paths)

    assert report["status"] == "FAIL"
    assert report["generated_answer_availability"]["generated_answer_contract_error_count"] == 1
    assert any("cited chunk ids are required" in error for error in report["validation"]["errors"])


def test_generated_answer_rows_missing_generation_provenance_fail_closed(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    answers = tmp_path / "answers.jsonl"
    row = generated_answer_row("text_001")
    row.pop("generation_provenance")
    write_jsonl(answers, [row, generated_answer_row("text_002")])
    paths["generated_answer_artifacts"] = [answers]

    report = prep.build_report(**paths)

    assert report["status"] == "FAIL"
    assert report["generated_answer_availability"]["generated_answer_contract_error_count"] == 1
    assert any("generation provenance is required" in error for error in report["validation"]["errors"])


def test_generated_answer_jsonl_parse_errors_fail_closed(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    answers = tmp_path / "answers.jsonl"
    answers.write_text(
        "\n".join(
            [
                json.dumps(generated_answer_row("text_001"), ensure_ascii=False),
                "{not-json}",
                json.dumps(generated_answer_row("text_002"), ensure_ascii=False),
                "",
            ]
        ),
        encoding="utf-8",
    )
    paths["generated_answer_artifacts"] = [answers]

    report = prep.build_report(**paths)

    assert report["status"] == "FAIL"
    assert report["generated_answer_availability"]["generated_answer_parse_error_count"] == 1
    assert any("generated answer artifact JSONL parse error" in error for error in report["validation"]["errors"])


def test_generated_answer_rows_with_production_index_mutation_fail_closed(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    answers = tmp_path / "answers.jsonl"
    row = generated_answer_row("text_001")
    row["retrieval_provenance"]["production_index_mutation"] = True
    write_jsonl(answers, [row, generated_answer_row("text_002")])
    paths["generated_answer_artifacts"] = [answers]

    report = prep.build_report(**paths)

    assert report["status"] == "FAIL"
    assert any("production_index_mutation must be false" in error for error in report["validation"]["errors"])


def test_generated_answer_rows_require_explicit_no_denominator_mutation(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    answers = tmp_path / "answers.jsonl"
    row = generated_answer_row("text_001")
    row.pop("official_denominator_mutation")
    write_jsonl(answers, [row, generated_answer_row("text_002")])
    paths["generated_answer_artifacts"] = [answers]

    report = prep.build_report(**paths)

    assert report["status"] == "FAIL"
    assert any(
        "official_denominator_mutation must be explicit boolean false" in error
        for error in report["validation"]["errors"]
    )


def test_generated_answer_duplicate_or_extra_query_ids_fail_closed(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    answers = tmp_path / "answers.jsonl"
    write_jsonl(
        answers,
        [
            generated_answer_row("text_001"),
            generated_answer_row("text_001"),
            generated_answer_row("text_002"),
            generated_answer_row("text_extra"),
        ],
    )
    paths["generated_answer_artifacts"] = [answers]

    report = prep.build_report(**paths)

    assert report["status"] == "FAIL"
    assert "generated answer artifacts contain duplicate query ids: text_001" in report["validation"]["errors"]
    assert "generated answer artifacts contain non-candidate query ids: text_extra" in report["validation"]["errors"]


def test_generated_answer_rows_require_official_metric_input_explicit_false(tmp_path: Path):
    invalid_values = [None, "false", 0, True]
    for index, value in enumerate(invalid_values):
        case_dir = tmp_path / f"invalid_{index}"
        case_dir.mkdir()
        paths = write_fixture_bundle(case_dir)
        answers = paths["text_review_pack"].parent / "answers.jsonl"
        row = generated_answer_row("text_001", official_metric_input=value)
        write_jsonl(answers, [row, generated_answer_row("text_002")])
        paths["generated_answer_artifacts"] = [answers]

        report = prep.build_report(**paths)

        assert report["status"] == "FAIL"
        assert any(
            "official_metric_input must be explicit boolean false" in error
            for error in report["validation"]["errors"]
        )

    missing_dir = tmp_path / "missing"
    missing_dir.mkdir()
    paths = write_fixture_bundle(missing_dir)
    answers = paths["text_review_pack"].parent / "answers.jsonl"
    row = generated_answer_row("text_001")
    row.pop("official_metric_input")
    write_jsonl(answers, [row, generated_answer_row("text_002")])
    paths["generated_answer_artifacts"] = [answers]

    report = prep.build_report(**paths)

    assert report["status"] == "FAIL"
    assert any("official_metric_input must be explicit boolean false" in error for error in report["validation"]["errors"])


def test_complete_generated_answer_jsonl_allows_diagnostic_review_but_not_official_metric(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    answers = tmp_path / "answers.jsonl"
    write_jsonl(answers, [generated_answer_row("text_001"), generated_answer_row("text_002")])
    paths["generated_answer_artifacts"] = [answers]

    report = prep.build_report(**paths)

    assert report["status"] == "READY_DIAGNOSTIC_ONLY"
    assert report["validation"]["ok"] is True
    assert report["answer_citation_review_preparation"]["generated_answer_missing_count"] == 0
    assert report["generated_answer_availability"]["actual_generated_answer_row_count"] == 2
    assert report["official_metric_input_rows"] == 0
    assert report["citation_support_metric_runner"]["status"] == "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY"
    assert report["guardrails"]["text_answer_denominator_opened"] is False
    assert report["guardrails"]["text_citation_support_denominator_opened"] is False


def test_generated_answer_json_report_does_not_satisfy_required_jsonl(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    answers = tmp_path / "answers_report.json"
    write_json(answers, generated_answer_row("text_001"))
    paths["generated_answer_artifacts"] = [answers]

    report = prep.build_report(**paths)

    assert report["status"] == "BLOCKED_GENERATED_ANSWER_OUTPUT_MISSING"
    assert report["generated_answer_availability"]["actual_generated_answer_row_count"] == 0
    assert report["answer_citation_review_preparation"]["generated_answer_missing_count"] == 2
    assert report["generated_answer_availability"]["json_payloads_not_counted_as_required_jsonl"] is True


def test_registry_text_answer_or_citation_key_sets_guardrails_and_fails(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    write_json(
        paths["denominator_registry"],
        {
            "schema_version": "official_denominator_registry_v1",
            "current_defaults": {
                "track_b_text_answer_generation": {
                    "denominator_kind": "text_answer_generation",
                    "official_positive_denominator": 2,
                }
            },
        },
    )

    report = prep.build_report(**paths)

    assert report["status"] == "FAIL"
    assert report["official_denominator_policy"]["text_answer_citation_official_denominator_opened"] is True
    assert report["guardrails"]["text_answer_denominator_opened"] is True
    assert report["guardrails"]["text_citation_support_denominator_opened"] is True
    assert "TEXT answer/citation denominator appears opened in registry" in report["validation"]["errors"]


def test_unresolved_policy_blocked_and_missing_answer_rows_stay_diagnostic_only(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    report = prep.build_report(**paths)
    row_groups = report["row_groups"]
    prep_state = report["answer_citation_review_preparation"]

    assert prep_state["candidate_review_rows_count"] == 2
    assert prep_state["generated_answer_missing_count"] == 2
    assert prep_state["generated_answer_missing_rows_diagnostic_only"] is True
    assert prep_state["generated_answer_missing_counted_as_failure"] is False
    assert row_groups["applied_unresolved_carry_forward"]["query_ids"] == ["text_003", "text_004", "text_006"]
    assert row_groups["applied_unresolved_carry_forward"]["promoted"] is False
    assert row_groups["policy_blocked_not_failure"]["query_ids"] == ["text_003"]
    assert row_groups["policy_blocked_not_failure"]["counted_as_failure"] is False
    assert row_groups["source_binding_review_required"]["query_ids"] == ["text_004"]
    assert row_groups["diagnostic_only_default"]["query_ids"] == ["text_005"]


def test_route_fallback_applied_labels_remain_diagnostic_only(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    report = prep.build_report(**paths)
    route_state = report["route_fallback_applied_labels"]

    assert route_state["diagnostic_only"] is True
    assert route_state["route_metrics_official"] is False
    assert route_state["fallback_metrics_official"] is False
    assert route_state["official_metric_input_rows"] == 0
    assert report["guardrails"]["route_fallback_applied_labels_diagnostic_only"] is True
    assert report["validation"]["ok"] is True


def test_route_fallback_official_metric_or_missing_artifact_fails_closed(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    write_json(
        paths["route_applied"],
        {
            "pack_type": "route_gold_label_review_applied",
            "diagnostic_only": False,
            "route_metrics_official": True,
            "counts": {"official_metric_input_rows": 1},
            "applied_human_review_rows": [
                {"query_id": "route_001", "official_metric_input": True}
            ],
        },
    )

    report = prep.build_report(**paths)

    assert report["status"] == "FAIL"
    assert report["route_fallback_applied_labels"]["diagnostic_only"] is False
    assert report["route_fallback_applied_labels"]["official_metric_input_rows"] == 2
    assert "route/fallback applied labels must remain outside official metric input" in report["validation"]["errors"]
    assert "route/fallback applied labels must be diagnostic-only" in report["validation"]["errors"]


def test_missing_or_invalid_source_artifacts_fail_closed(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    paths["normalization_report"].write_text("{not-json", encoding="utf-8")
    paths["text_review_pack"].unlink()

    report = prep.build_report(**paths)

    assert report["status"] == "FAIL"
    assert "TEXT review pack is missing" in report["validation"]["errors"]
    assert "TEXT review pack has no rows" in report["validation"]["errors"]
    assert "reviewed gold policy normalization report is missing or invalid JSON" in report["validation"]["errors"]
    assert "normalization report missing tracks.text_namu_v2" in report["validation"]["errors"]
    assert "TEXT answer/citation prep candidate ids are missing" in report["validation"]["errors"]


def test_missing_route_or_fallback_artifact_fails_closed(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    paths["fallback_applied"].unlink()

    report = prep.build_report(**paths)

    assert report["status"] == "FAIL"
    assert report["route_fallback_applied_labels"]["fallback_artifact_exists"] is False
    assert "route/fallback applied artifacts must exist for this prep report" in report["validation"]["errors"]


def test_main_writes_compact_reports_without_registry_mutation(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    registry = paths["denominator_registry"]
    before = registry.read_text(encoding="utf-8")
    output_json = tmp_path / "prep_report.json"
    output_md = tmp_path / "prep_report.md"

    result = prep.main(
        [
            "--text-review-pack",
            str(paths["text_review_pack"]),
            "--normalization-report",
            str(paths["normalization_report"]),
            "--applied-decisions",
            str(paths["applied_decisions"]),
            "--denominator-registry",
            str(registry),
            "--route-applied",
            str(paths["route_applied"]),
            "--fallback-applied",
            str(paths["fallback_applied"]),
            "--generated-answer-artifact",
            str(tmp_path / "missing_answers.jsonl"),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
    )

    assert result == 0
    assert output_json.exists()
    assert output_md.exists()
    assert registry.read_text(encoding="utf-8") == before
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["status"] == "BLOCKED_GENERATED_ANSWER_OUTPUT_MISSING"


def write_fixture_bundle(tmp_path: Path) -> dict[str, Path | list[Path]]:
    text_review_pack = tmp_path / "text_namu_v2_review.csv"
    normalization_report = tmp_path / "normalization.json"
    applied_decisions = tmp_path / "applied.json"
    denominator_registry = tmp_path / "official_denominator_registry.json"
    route_applied = tmp_path / "route_applied.json"
    fallback_applied = tmp_path / "fallback_applied.json"

    write_review_pack(text_review_pack)
    write_json(normalization_report, normalization_fixture())
    write_json(applied_decisions, applied_fixture())
    write_json(denominator_registry, registry_fixture())
    write_json(route_applied, route_fixture("route_gold_label_review_applied"))
    write_json(fallback_applied, route_fixture("fallback_outcome_label_review_applied"))

    return {
        "text_review_pack": text_review_pack,
        "normalization_report": normalization_report,
        "applied_decisions": applied_decisions,
        "denominator_registry": denominator_registry,
        "route_applied": route_applied,
        "fallback_applied": fallback_applied,
        "generated_answer_artifacts": [tmp_path / "missing_answers.jsonl"],
    }


def write_review_pack(path: Path) -> None:
    fieldnames = [
        "query_id",
        "candidate_default_policy",
        "user_final_gold_policy",
        "user_answerability_label",
        "user_relevance_label",
    ]
    rows = [
        ("text_001", "OFFICIAL_REVIEW_CANDIDATE", "KEEP_POSITIVE", "ANSWERABLE", "RELEVANT"),
        ("text_002", "OFFICIAL_REVIEW_CANDIDATE", "KEEP_POSITIVE", "ANSWERABLE", "RELEVANT"),
        ("text_003", "OFFICIAL_REVIEW_CANDIDATE", "KEEP_POSITIVE", "INVALID_QUERY", "IRRELEVANT"),
        ("text_004", "OFFICIAL_REVIEW_CANDIDATE", "KEEP_POSITIVE", "ANSWERABLE", "RELEVANT"),
        ("text_005", "DIAGNOSTIC_ONLY_DEFAULT", "KEEP_POSITIVE", "ANSWERABLE", "RELEVANT"),
        ("text_006", "OFFICIAL_REVIEW_CANDIDATE", "REVISE_EXPECTED_ANSWER", "ANSWERABLE", "RELEVANT"),
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(zip(fieldnames, row)))


def normalization_fixture() -> dict:
    ids = [f"text_{index:03d}" for index in range(1, 7)]
    return {
        "tracks": {
            "text_namu_v2": {
                "row_count": 6,
                "normalized_bucket_counts": {
                    "PROPOSED_OFFICIAL_CANDIDATE": 2,
                    "POLICY_EXCLUDED": 1,
                    "SOURCE_BINDING_REVIEW_REQUIRED": 1,
                    "DIAGNOSTIC_ONLY": 1,
                    "EXPECTED_ANSWER_REVISION": 1,
                },
                "proposed_official_candidate_query_ids": ["text_001", "text_002"],
                "policy_excluded_query_ids": ["text_003"],
                "source_verification_required_query_ids": ["text_004"],
                "diagnostic_only_query_ids": ["text_005"],
                "expected_answer_or_evidence_revision_query_ids": ["text_006"],
                "unresolved_user_review_count": 3,
                "review_marker_buckets": {
                    "needs_second_review": [],
                    "evidence_too_broad": [],
                    "ambiguous_query": [],
                },
                "rows": [
                    {"query_id": query_id, "normalized_policy_bucket": "fixture"} for query_id in ids
                ],
            }
        }
    }


def applied_fixture() -> dict:
    return {
        "applied_decisions": {
            "text_namu_v2_unresolved_carry_forward": {
                "status": "APPLIED_CARRY_FORWARD_UNCHANGED",
                "include_in_gold_v0_1": False,
                "resolution_attempted": False,
                "query_ids": ["text_003", "text_004", "text_006"],
            }
        }
    }


def registry_fixture() -> dict:
    return {
        "schema_version": "official_denominator_registry_v1",
        "official_diagnostic_denominators": {
            "track_b_namu_v4_bound": {
                "path": "ai/eval/eval_queries/gold_queries_text_namu_v4_v0.csv",
                "row_count": 50,
                "official_positive_denominator": 47,
                "excluded_needs_review": 3,
                "promotion_evidence": False,
                "evidence_role": "diagnostic",
            }
        },
    }


def route_fixture(pack_type: str) -> dict:
    return {
        "pack_type": pack_type,
        "diagnostic_only": True,
        "route_metrics_official": False,
        "fallback_metrics_official": False,
        "counts": {"official_metric_input_rows": 0},
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def generated_answer_row(
    query_id: str,
    *,
    cited_chunk_ids: list[str] | None = None,
    official_metric_input: object = False,
) -> dict:
    cited = ["chunk-1"] if cited_chunk_ids is None else cited_chunk_ids
    return {
        "query_id": query_id,
        "safe_query_text": f"query for {query_id}",
        "actual_generated_answer_output": True,
        "generated_answer": f"answer for {query_id}",
        "cited_chunk_ids": cited,
        "retrieved_chunk_ids": cited or ["chunk-1"],
        "citation_items": [
            {"chunk_id": chunk_id, "citation_text": f"citation for {chunk_id}"}
            for chunk_id in cited
        ],
        "generation_provenance": {
            "generator_name": "extractive-v1",
            "answer_generation_execution": "source_bound_extractive_generator_no_llm",
            "actual_generated_answer_output": True,
            "official_metric_input": official_metric_input,
        },
        "retrieval_provenance": {
            "source_artifact_id": "fixture-review-pack.csv",
            "production_index_used": False,
            "production_index_mutation": False,
        },
        "prompt_model_config_provenance": {
            "prompt_template_sha256": "abc123",
            "model_name": "none_extractive_generator",
        },
        "diagnostic_only": True,
        "official_metric_input": official_metric_input,
        "official_denominator_mutation": False,
    }
