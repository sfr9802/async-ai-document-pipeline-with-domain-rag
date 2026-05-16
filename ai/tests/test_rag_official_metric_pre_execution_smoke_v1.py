from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_official_metric_pre_execution_smoke_v1.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_official_metric_pre_execution_smoke_v1_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pre_execution_smoke_passes_registry_backed_29_rows_with_text_warning(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture_bundle(module, tmp_path)

    report = module.build_report(
        metric_input_config=read_json(paths["config"]),
        metric_input_config_path=paths["config"],
        denominator_registry=read_json(paths["registry"]),
        denominator_registry_path=paths["registry"],
        registry_application_report=read_json(paths["application"]),
        registry_application_report_path=paths["application"],
        xlsx_leakage_reprobe=read_json(paths["xlsx_leakage"]),
        xlsx_leakage_reprobe_path=paths["xlsx_leakage"],
        text_corpus_path=paths["text_corpus"],
    )

    assert report["validation"]["ok"] is True
    assert report["status"] == "OFFICIAL_METRIC_PRE_EXECUTION_SMOKE_PASS_WITH_DIAGNOSTIC_WARNINGS"
    assert report["official_input_summary"]["row_count"] == 29
    assert report["official_input_summary"]["row_count_by_track"] == {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 6,
        "xlsx_business_structured": 19,
    }
    assert report["csv_checks"]["xlsx_business_structured"]["sha256"] == paths["sha_by_track"]["xlsx_business_structured"]
    assert report["pdf_locator_diagnostic"]["table_bbox_locator_rows"][0]["diagnostic_scorer_compatible"] is True
    assert report["xlsx_locator_diagnostic"]["hidden_excluded_surface_leakage_count"] == 0
    assert report["text_support_diagnostic"]["cited_chunk_ids_found"] == 6
    assert [row["query_id"] for row in report["text_support_diagnostic"]["potential_support_coverage_gap"]] == [
        "text_namu_v2_0017"
    ]
    assert report["official_metric_execution_started"] is False
    assert report["tuning_run_started"] is False
    assert report["promotion_evidence"] is False


def test_pre_execution_smoke_fails_on_config_sha_mismatch(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture_bundle(module, tmp_path)
    config = read_json(paths["config"])
    config["official_metric_input_artifacts"]["xlsx_business_structured"]["sha256"] = "bad"

    report = module.build_report(
        metric_input_config=config,
        metric_input_config_path=paths["config"],
        denominator_registry=read_json(paths["registry"]),
        denominator_registry_path=paths["registry"],
        registry_application_report=read_json(paths["application"]),
        registry_application_report_path=paths["application"],
        xlsx_leakage_reprobe=read_json(paths["xlsx_leakage"]),
        xlsx_leakage_reprobe_path=paths["xlsx_leakage"],
        text_corpus_path=paths["text_corpus"],
    )

    assert report["validation"]["ok"] is False
    assert any("sha256 mismatch against metric input config" in error for error in report["validation"]["errors"])


def test_pre_execution_smoke_fails_on_xlsx_locator_gap(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture_bundle(module, tmp_path, xlsx_missing_locator=True)

    report = module.build_report(
        metric_input_config=read_json(paths["config"]),
        metric_input_config_path=paths["config"],
        denominator_registry=read_json(paths["registry"]),
        denominator_registry_path=paths["registry"],
        registry_application_report=read_json(paths["application"]),
        registry_application_report_path=paths["application"],
        xlsx_leakage_reprobe=read_json(paths["xlsx_leakage"]),
        xlsx_leakage_reprobe_path=paths["xlsx_leakage"],
        text_corpus_path=paths["text_corpus"],
    )

    assert report["validation"]["ok"] is False
    assert "XLSX official rows missing required locator fields" in report["validation"]["errors"]


def test_pre_execution_smoke_fails_on_csv_expected_answer_rewrite_even_if_sha_refs_match(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture_bundle(module, tmp_path)
    csv_path = paths["csv_paths"]["text_namu_v2_1"]
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8", newline="")))
    rows[0]["expected_answer"] = "rewritten expected answer"
    write_csv(csv_path, rows)
    refresh_sha_references(paths, "text_namu_v2_1", module)

    report = module.build_report(
        metric_input_config=read_json(paths["config"]),
        metric_input_config_path=paths["config"],
        denominator_registry=read_json(paths["registry"]),
        denominator_registry_path=paths["registry"],
        registry_application_report=read_json(paths["application"]),
        registry_application_report_path=paths["application"],
        xlsx_leakage_reprobe=read_json(paths["xlsx_leakage"]),
        xlsx_leakage_reprobe_path=paths["xlsx_leakage"],
        text_corpus_path=paths["text_corpus"],
    )

    assert report["validation"]["ok"] is False
    assert "text_namu_v2_0000 expected_answer differs from metric input config candidate_manifest" in report[
        "validation"
    ]["errors"]


def test_pre_execution_smoke_fails_on_human_inclusion_change(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture_bundle(module, tmp_path)
    csv_path = paths["csv_paths"]["pdf_business_ocr_mm"]
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8", newline="")))
    rows[0]["human_label"] = "EXCLUDE_FROM_OFFICIAL_GOLD"
    write_csv(csv_path, rows)
    refresh_sha_references(paths, "pdf_business_ocr_mm", module)

    report = module.build_report(
        metric_input_config=read_json(paths["config"]),
        metric_input_config_path=paths["config"],
        denominator_registry=read_json(paths["registry"]),
        denominator_registry_path=paths["registry"],
        registry_application_report=read_json(paths["application"]),
        registry_application_report_path=paths["application"],
        xlsx_leakage_reprobe=read_json(paths["xlsx_leakage"]),
        xlsx_leakage_reprobe_path=paths["xlsx_leakage"],
        text_corpus_path=paths["text_corpus"],
    )

    assert report["validation"]["ok"] is False
    assert any("human_label must stay INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE" in error for error in report["validation"]["errors"])


def write_fixture_bundle(module, tmp_path: Path, *, xlsx_missing_locator: bool = False) -> dict[str, object]:
    module.REPO_ROOT = tmp_path
    eval_queries = tmp_path / "ai" / "eval" / "eval_queries"
    reports = tmp_path / "ai" / "eval" / "reports" / "rag-ingestion"
    corpus = tmp_path / "ai" / "eval" / "corpora" / "namu-v4-structured-combined"
    eval_queries.mkdir(parents=True)
    reports.mkdir(parents=True)
    corpus.mkdir(parents=True)

    csv_paths = {
        "pdf_business_ocr_mm": eval_queries / "gold_queries_pdf_question_gold_v2.csv",
        "text_namu_v2_1": eval_queries / "gold_queries_text_namu_v2_1_question_gold_v2.csv",
        "xlsx_business_structured": eval_queries / "gold_queries_xlsx_question_gold_v2.csv",
    }
    write_csv(csv_paths["pdf_business_ocr_mm"], pdf_rows())
    write_csv(csv_paths["text_namu_v2_1"], text_rows())
    write_csv(csv_paths["xlsx_business_structured"], xlsx_rows(missing_locator=xlsx_missing_locator))
    text_corpus = corpus / "rag_chunks.jsonl"
    text_corpus.write_text(
        "\n".join(
            json.dumps({"chunk_id": f"chunk-{idx}", "chunk_text": text}, ensure_ascii=False)
            for idx, text in enumerate(
                [
                    "text answer 0",
                    "text answer 1",
                    "text answer 2",
                    "text answer 3",
                    "text answer 4",
                    "alpha something beta",
                ]
            )
        )
        + "\n",
        encoding="utf-8",
    )

    sha_by_track = {track: module.sha256_file(path) for track, path in csv_paths.items()}
    registry = registry_payload(csv_paths, sha_by_track, module)
    application = application_payload(csv_paths, sha_by_track, module)
    config = config_payload(csv_paths, sha_by_track, module)
    xlsx_leakage = {
        "status": "PASS",
        "metrics": {"surface_leakage_count": 0},
        "counts": {"surface_leakage_count": 0},
        "query_results": [{"query_id": "hidden_xlsx_001", "row_source": "normalized_excluded", "hidden_negative": True}],
    }
    paths = {
        "registry": eval_queries / "official_denominator_registry.json",
        "application": reports / "official_question_gold_v2_registry_application_report.json",
        "config": reports / "official_metric_input_config_v1.json",
        "xlsx_leakage": reports / "xlsx_answer_citation_hidden_excluded_leakage_reprobe.json",
        "text_corpus": text_corpus,
        "sha_by_track": sha_by_track,
        "csv_paths": csv_paths,
    }
    write_json(paths["registry"], registry)
    write_json(paths["application"], application)
    write_json(paths["config"], config)
    write_json(paths["xlsx_leakage"], xlsx_leakage)
    return paths


def pdf_rows() -> list[dict[str, str]]:
    rows = []
    for idx in range(4):
        locator = {
            "file": f"pdf-{idx}",
            "page": idx + 1,
            "physical_page_index": idx,
            "bbox": [1.0, 2.0, 3.0, 4.0],
            "region_type": "table_body" if idx >= 2 else "paragraph",
            "search_unit_id": f"su-pdf-{idx}",
            "bbox_granularity": "row_only" if idx == 2 else ("table_only" if idx == 3 else ""),
        }
        rows.append(base_row(f"gq_pdf_{idx:03d}", "pdf_business_ocr_mm", locator, expected=f"pdf answer {idx}"))
    return rows


def text_rows() -> list[dict[str, str]]:
    rows = []
    for idx in range(5):
        rows.append(
            base_row(
                f"text_namu_v2_000{idx}",
                "text_namu_v2_1",
                {"cited_chunk_ids": [f"chunk-{idx}"]},
                expected=f"text answer {idx}",
            )
        )
    rows.append(
        base_row(
            "text_namu_v2_0017",
            "text_namu_v2_1",
            {"cited_chunk_ids": ["chunk-5"]},
            expected="alpha beta",
            supporting="alpha something beta",
        )
    )
    return rows


def xlsx_rows(*, missing_locator: bool) -> list[dict[str, str]]:
    rows = []
    for idx in range(19):
        locator = {
            "file": "book.xlsx",
            "sheet": "Sheet1",
            "range": "A1:J20",
            "matched_cells": [f"B{idx + 1}"],
            "search_unit_id": f"su-xlsx-{idx}",
            "document_version_id": f"docv-xlsx-{idx}",
        }
        if missing_locator and idx == 0:
            locator.pop("matched_cells")
        rows.append(base_row(f"gq_xlsx_{idx:03d}", "xlsx_business_structured", locator, expected=f"xlsx answer {idx}"))
    return rows


def base_row(
    query_id: str,
    track: str,
    locator: dict[str, object],
    *,
    expected: str,
    supporting: str | None = None,
) -> dict[str, str]:
    return {
        "query_id": query_id,
        "question": f"question for {query_id}",
        "expected_answer": expected,
        "supporting_evidence": supporting or expected,
        "track": track,
        "citation_locator": json.dumps(locator, ensure_ascii=False),
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


def registry_payload(csv_paths: dict[str, Path], sha_by_track: dict[str, str], module) -> dict[str, object]:
    return {
        "schema_version": "official_denominator_registry_v1",
        "official_diagnostic_denominators": {
            "track_c_pdf_question_gold_v2_human_audit_approved": registry_entry(
                csv_paths["pdf_business_ocr_mm"], 4, sha_by_track["pdf_business_ocr_mm"], module
            ),
            "track_b_text_namu_v2_1_question_gold_v2_human_audit_approved": registry_entry(
                csv_paths["text_namu_v2_1"], 6, sha_by_track["text_namu_v2_1"], module
            ),
            "track_a_xlsx_question_gold_v2_human_audit_approved": registry_entry(
                csv_paths["xlsx_business_structured"], 19, sha_by_track["xlsx_business_structured"], module
            ),
        },
    }


def registry_entry(path: Path, rows: int, sha: str, module) -> dict[str, object]:
    return {
        "path": module.repo_relative(path),
        "row_count": rows,
        "official_metric_input_rows": rows,
        "sha256": sha,
        "denominator_kind": "question_answer_citation_gold_v2",
        "metric_lane": "answer_citation",
    }


def application_payload(csv_paths: dict[str, Path], sha_by_track: dict[str, str], module) -> dict[str, object]:
    return {
        "status": "OFFICIAL_QUESTION_GOLD_V2_REGISTRY_APPLIED",
        "promotion_evidence": False,
        "official_metric_execution_started": False,
        "tuning_run_started": False,
        "official_metric_input_rows": 29,
        "official_metric_input_rows_by_track": {
            "pdf_business_ocr_mm": 4,
            "text_namu_v2_1": 6,
            "xlsx_business_structured": 19,
        },
        "official_metric_input_artifacts": {
            track: {"path": module.repo_relative(path), "row_count": rows, "sha256": sha_by_track[track]}
            for track, path, rows in [
                ("pdf_business_ocr_mm", csv_paths["pdf_business_ocr_mm"], 4),
                ("text_namu_v2_1", csv_paths["text_namu_v2_1"], 6),
                ("xlsx_business_structured", csv_paths["xlsx_business_structured"], 19),
            ]
        },
    }


def config_payload(csv_paths: dict[str, Path], sha_by_track: dict[str, str], module) -> dict[str, object]:
    rows_by_track = {"pdf_business_ocr_mm": 4, "text_namu_v2_1": 6, "xlsx_business_structured": 19}
    keys = {
        "pdf_business_ocr_mm": "track_c_pdf_question_gold_v2_human_audit_approved",
        "text_namu_v2_1": "track_b_text_namu_v2_1_question_gold_v2_human_audit_approved",
        "xlsx_business_structured": "track_a_xlsx_question_gold_v2_human_audit_approved",
    }
    return {
        "status": "OFFICIAL_METRIC_INPUT_CONFIG_READY_REGISTRY_BACKED_NOT_EXECUTED",
        "promotion_evidence": False,
        "official_metric_execution_started": False,
        "metric_execution_allowed": True,
        "registry_application_status": "APPLIED",
        "tuning_run_started": False,
        "official_metric_input_rows": 29,
        "official_metric_input_rows_by_track": rows_by_track,
        "metric_lanes": {
            track: {
                "candidate_path": module.repo_relative(path),
                "csv_path": module.repo_relative(path),
                "denominator_key": keys[track],
                "official_metric_input_rows_current": rows_by_track[track],
                "row_count": rows_by_track[track],
                "sha256": sha_by_track[track],
                "metric_lane": "answer_citation",
            }
            for track, path in csv_paths.items()
        },
        "official_metric_input_artifacts": {
            track: {
                "path": module.repo_relative(path),
                "csv_path": module.repo_relative(path),
                "row_count": rows_by_track[track],
                "sha256": sha_by_track[track],
                "denominator_key": keys[track],
                "metric_lane": "answer_citation",
            }
            for track, path in csv_paths.items()
        },
        "candidate_manifest": candidate_manifest(csv_paths),
        "validation": {"ok": True, "errors": []},
    }


def candidate_manifest(csv_paths: dict[str, Path]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in csv_paths.values():
        for row in csv.DictReader(path.open(encoding="utf-8", newline="")):
            rows.append(
                {
                    "query_id": row["query_id"],
                    "track": row["track"],
                    "question": row["question"],
                    "expected_answer": row["expected_answer"],
                    "supporting_evidence": row["supporting_evidence"],
                    "citation_locator": json.loads(row["citation_locator"]),
                    "official_metric_input": row["official_metric_input"].upper() == "TRUE",
                    "promotion_evidence": row["promotion_evidence"].upper() == "TRUE",
                }
            )
    return sorted(rows, key=lambda row: (str(row["track"]), str(row["query_id"])))


def refresh_sha_references(paths: dict[str, object], track: str, module) -> None:
    csv_path = paths["csv_paths"][track]
    new_sha = module.sha256_file(csv_path)
    registry = read_json(paths["registry"])
    for entry in registry["official_diagnostic_denominators"].values():
        if entry["path"] == module.repo_relative(csv_path):
            entry["sha256"] = new_sha
    write_json(paths["registry"], registry)

    application = read_json(paths["application"])
    application["official_metric_input_artifacts"][track]["sha256"] = new_sha
    write_json(paths["application"], application)

    config = read_json(paths["config"])
    config["official_metric_input_artifacts"][track]["sha256"] = new_sha
    config["metric_lanes"][track]["sha256"] = new_sha
    write_json(paths["config"], config)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
