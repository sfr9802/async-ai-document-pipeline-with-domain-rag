from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_silver_only_tuning_pass.py"
DIAG_SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_silver_tuning_diagnostic_analysis.py"
PDF_HNEG_V2_SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_pdf_file_lookup_hard_negative_v2.py"


def load_module():
    return load_module_from_path("rag_silver_only_tuning_pass", SCRIPT_PATH)


def load_diag_module():
    return load_module_from_path("rag_silver_tuning_diagnostic_analysis", DIAG_SCRIPT_PATH)


def load_pdf_hneg_v2_module():
    return load_module_from_path("rag_pdf_file_lookup_hard_negative_v2", PDF_HNEG_V2_SCRIPT_PATH)


def load_module_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_silver_only_tuning_selects_without_gold_training(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)

    result = module.main(["--config", str(paths["config"])])

    assert result == 0
    silver_report = json.loads(paths["silver_report"].read_text(encoding="utf-8"))
    gold_report = json.loads(paths["gold_report"].read_text(encoding="utf-8"))
    delta = paths["delta"].read_text(encoding="utf-8")

    assert silver_report["selection_data"] == "silver_only"
    assert silver_report["frozen_gold_training_rows"] == 0
    assert silver_report["gold_used_for_selection"] is False
    assert silver_report["pdf_file_lookup_selection_pool"]["frozen_gold_eval_rows_used"] is False
    assert silver_report["pdf_file_lookup_selection_pool"]["frozen_gold_only_identity_used_count"] == 0
    assert silver_report["pdf_file_lookup_selection_pool"]["frozen_gold_only_identity_excluded_count"] >= 1
    assert "file.pdf" not in silver_report["pdf_file_lookup_selection_pool"]["selection_pool_file_names"]
    assert "gold_only_2024_04_total.pdf" not in silver_report["pdf_file_lookup_selection_pool"]["selection_pool_file_names"]
    assert (
        silver_report["pdf_file_lookup_selection_pool"]["frozen_gold_document_version_id_in_selection_pool_count"] == 0
    )
    assert silver_report["pdf_file_lookup_selection_pool"]["frozen_gold_only_document_version_id_used_count"] == 0
    assert "gold_docv_2024_04" not in silver_report["pdf_file_lookup_selection_pool"]["selection_pool_document_version_ids"]
    assert "gold_docv_file" not in silver_report["pdf_file_lookup_selection_pool"]["selection_pool_document_version_ids"]
    assert gold_report["gold_used_for_selection"] is False
    assert gold_report["lanes"]["PDF_FILE_LOOKUP"]["metrics"]["page_bbox_table_row_column_value_success_claimed"] is False
    assert "TEXT_MAIN_POSITIVE" in delta


def test_guard_failure_writes_baseline_failure_before_tuning(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path, leakage_status="FAIL")

    result = module.main(["--config", str(paths["config"])])

    assert result == 1
    baseline = json.loads(paths["baseline_report"].read_text(encoding="utf-8"))
    assert baseline["status"] == "FAIL"
    assert baseline["guard"]["failures"]
    assert not paths["silver_report"].exists()


def test_diagnostic_analysis_writes_policy_reports(tmp_path: Path, monkeypatch):
    tuning_module = load_module()
    diag_module = load_diag_module()
    paths = write_fixture_bundle(tmp_path)
    write_shadow_fixture_inputs(tmp_path)
    monkeypatch.setattr(diag_module, "DEFAULT_REPORT_DIR", paths["reports"])
    monkeypatch.setattr(diag_module, "AI_WORKER_ROOT", tmp_path)

    result = tuning_module.main(["--config", str(paths["config"])])
    diag_result = diag_module.main(["--config", str(paths["config"]), "--reports-dir", str(paths["reports"])])

    assert result == 0
    assert diag_result == 0
    query_delta = json.loads((paths["reports"] / "silver_tuning_query_delta_report.json").read_text(encoding="utf-8"))
    hit5 = json.loads((paths["reports"] / "text_hit5_regression_review.json").read_text(encoding="utf-8"))
    pdf_rank = json.loads((paths["reports"] / "pdf_file_lookup_rank_error_analysis.json").read_text(encoding="utf-8"))
    ocr = json.loads((paths["reports"] / "ocr_shadow_small_sample_report.json").read_text(encoding="utf-8"))
    idp = json.loads((paths["reports"] / "idp_shadow_small_sample_report.json").read_text(encoding="utf-8"))
    multimodal = json.loads((paths["reports"] / "multimodal_shadow_small_sample_report.json").read_text(encoding="utf-8"))

    assert query_delta["selection_policy"]["gold_used_for_selection"] is False
    assert query_delta["selection_policy"]["profile_selected_from_frozen_gold"] is False
    assert query_delta["selection_policy"]["frozen_gold_training_rows"] == 0
    silver_report = json.loads(paths["silver_report"].read_text(encoding="utf-8"))
    assert silver_report["pdf_file_lookup_selection_pool"]["source"] == "silver_pdf_file_lookup_train_rows_only"
    assert silver_report["pdf_file_lookup_selection_pool"]["frozen_gold_eval_rows_used"] is False
    assert silver_report["pdf_file_lookup_selection_pool"]["frozen_gold_only_identity_used_count"] == 0
    assert silver_report["pdf_file_lookup_selection_pool"]["frozen_gold_only_document_version_id_used_count"] == 0
    assert hit5["status"] == "PASS"
    assert hit5["production_ready_claimed"] is False
    for key in [
        "content_success_claimed",
        "page_success_claimed",
        "bbox_success_claimed",
        "table_success_claimed",
        "row_success_claimed",
        "column_success_claimed",
        "value_success_claimed",
    ]:
        assert pdf_rank["policy"][key] is False
    assert pdf_rank["policy"]["pdf_file_lookup_semantics"] == "file_identity_only"
    assert ocr["native_outranks_ocr_fallback"] is True
    for payload in [ocr, idp, multimodal]:
        assert payload["policy"]["official_denominator_registry_changed"] is False
        for row in payload["diagnostic_rows"]:
            assert row["denominator_role"] == "DIAGNOSTIC_ONLY"
            assert row["official_denominator_eligible"] is False
            assert row["evidence_role"] == "diagnostic"
    assert multimodal["policy"]["caption_role"] == "retrieval_expansion_only"
    assert multimodal["policy"]["official_evidence_claimed"] is False


def test_pdf_file_lookup_hard_negative_v2_uses_silver_only_and_excludes_gold_identities(tmp_path: Path):
    module = load_pdf_hneg_v2_module()
    paths = write_fixture_bundle(tmp_path)
    output_csv = paths["reports"] / "silver_pdf_file_lookup_hard_negative_v2.csv"
    report_json = paths["reports"] / "pdf_file_lookup_hard_negative_v2_report.json"
    report_md = paths["reports"] / "pdf_file_lookup_hard_negative_v2_report.md"

    result = module.main(
        [
            "--config",
            str(paths["config"]),
            "--output-csv",
            str(output_csv),
            "--report-json",
            str(report_json),
            "--report-md",
            str(report_md),
        ]
    )

    assert result == 0
    report = json.loads(report_json.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(output_csv.open("r", encoding="utf-8", newline="")))
    assert report["policy"]["source_rows"] == "silver_pdf_file_lookup_train_rows_only"
    assert report["policy"]["frozen_gold_values_used_for_sampling"] is False
    assert report["policy"]["frozen_gold_values_used_for_exclusion_guard_only"] is True
    assert report["validation"]["generated_rows_exclude_frozen_gold_file_identities"] is True
    assert report["validation"]["generated_rows_exclude_frozen_gold_document_version_ids"] is True
    assert rows
    for row in rows:
        assert row["denominator_role"] == "TUNING_ONLY"
        assert row["official_gold"] == "false"
        assert row["expected_file_name"] not in {"gold_only_2024_04_total.pdf", "file.pdf"}
        assert row["positive_expected_file_name"] not in {"gold_only_2024_04_total.pdf", "file.pdf"}
        assert row["expected_document_version_id"] not in {"gold_docv_2024_04", "gold_docv_file"}
        assert row["positive_expected_document_version_id"] not in {"gold_docv_2024_04", "gold_docv_file"}
    assert "Content/page/bbox/table/row/column/value success claimed: `false`" in report_md.read_text(encoding="utf-8")


def write_fixture_bundle(tmp_path: Path, *, leakage_status: str = "PASS") -> dict[str, Path]:
    base = tmp_path / "gold_silver"
    base.mkdir()
    reports = tmp_path / "reports"
    reports.mkdir()
    corpus = tmp_path / "rag_chunks.jsonl"
    corpus.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "chunk_id": "chunk_a",
                        "doc_id": "doc_a",
                        "section_id": "sec_a",
                        "title": "Alpha",
                        "retrieval_title": "Alpha",
                        "section_path": ["Overview"],
                        "chunk_text": "alpha magic library director spring",
                    }
                ),
                json.dumps(
                    {
                        "chunk_id": "chunk_b",
                        "doc_id": "doc_b",
                        "section_id": "sec_b",
                        "title": "Beta",
                        "retrieval_title": "Beta",
                        "section_path": ["Other"],
                        "chunk_text": "beta unrelated winter",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    write_csv(
        base / "silver_text_positive_train.csv",
        ["query_id", "source_query_id", "query", "expected_document_ids", "expected_page_ids", "expected_section_path", "expected_chunk_ids", "official_gold"],
        [["silver_text_pos_1", "src_silver_1", "alpha director spring", "doc_a", "doc_a", "Overview", "chunk_a", "false"]],
    )
    write_csv(
        base / "silver_text_hard_negative_train.csv",
        ["query_id", "source_query_id", "query", "expected_document_ids", "expected_page_ids", "expected_section_path", "expected_chunk_ids", "positive_expected_document_ids", "official_gold"],
        [["silver_text_hneg_1", "src_silver_1", "alpha director spring", "doc_b", "doc_b", "Other", "chunk_b", "doc_a", "false"]],
    )
    write_csv(
        base / "silver_text_abstain_diagnostic.csv",
        ["query_id", "source_query_id", "query", "expected_document_ids", "expected_page_ids", "expected_section_ids", "expected_chunk_ids", "official_gold"],
        [["silver_text_abs_1", "src_abs_1", "not answerable", "", "", "", "", "false"]],
    )
    write_csv(
        base / "text_gold_main_positive_clean.csv",
        ["query_id", "source_query_id", "query", "expected_document_ids", "expected_page_ids", "expected_section_ids", "expected_chunk_ids", "official_gold"],
        [["gold_text_1", "gold_src_1", "alpha library director", "doc_a", "doc_a", "sec_a", "chunk_a", "false"]],
    )
    write_csv(
        base / "text_gold_abstain_diagnostic_clean.csv",
        ["query_id", "source_query_id", "query", "expected_document_ids", "expected_page_ids", "expected_section_ids", "expected_chunk_ids", "official_gold"],
        [["gold_abs_1", "gold_src_abs_1", "unknown budget", "", "", "", "", "false"]],
    )
    write_csv(
        base / "silver_pdf_file_lookup_positive_train.csv",
        ["query_id", "source_query_id", "query", "retrieval_lane", "expected_file_name", "source_file_name", "expected_document_version_id", "expected_evidence_policy", "official_gold"],
        [["silver_pdf_pos_1", "pdf_src_1", "2024 4 total electricity file", "pdf_file_lookup", "2024_04_total.pdf", "2024_04_total.pdf", "silver_docv_2024_04", "EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY", "false"]],
    )
    write_csv(
        base / "silver_pdf_file_lookup_hard_negative_train.csv",
        ["query_id", "source_query_id", "query", "retrieval_lane", "expected_file_name", "source_file_name", "expected_document_version_id", "positive_expected_file_name", "expected_evidence_policy", "official_gold"],
        [["silver_pdf_hneg_1", "pdf_src_1", "2024 4 total electricity file", "pdf_file_lookup", "2024_07_total.pdf", "2024_07_total.pdf", "silver_docv_2024_07", "2024_04_total.pdf", "EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY", "false"]],
    )
    write_csv(
        base / "pdf_file_lookup_gold_positive_clean.csv",
        ["query_id", "source_query_id", "query", "retrieval_lane", "retrieval_lane_clean", "expected_file_name", "source_file_name", "expected_document_version_id", "official_gold"],
        [["gold_pdf_1", "", "gold only 2024 4 total electricity file", "PDF_FILE_LOOKUP_BY_CONTENT_ANCHOR", "pdf_file_lookup", "gold_only_2024_04_total.pdf", "gold_only_2024_04_total.pdf", "gold_docv_2024_04", "false"]],
    )
    write_csv(
        base / "pdf_file_lookup_diagnostic_clean.csv",
        ["query_id", "source_query_id", "query", "retrieval_lane", "retrieval_lane_clean", "expected_file_name", "source_file_name", "expected_document_version_id", "official_gold"],
        [["gold_pdf_diag_1", "", "generic file", "PDF_FILE_LOOKUP_BY_CONTENT_ANCHOR", "pdf_file_lookup", "file.pdf", "file.pdf", "gold_docv_file", "false"]],
    )
    manifest = {
        "gold_frozen": {"official_denominator_registry_changed": False},
        "silver": {
            "leakage": {
                "status": leakage_status,
                "query_text_overlap_count": 0,
                "query_id_overlap_count": 0,
                "source_query_id_overlap_count": 0,
                "expected_id_overlap_count": 0,
            }
        },
    }
    manifest_path = reports / "denominator_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    config = tmp_path / "silver_only_tuning_config.yaml"
    baseline_report = reports / "baseline.json"
    silver_report = reports / "silver.json"
    gold_report = reports / "gold.json"
    delta = reports / "delta.md"
    config.write_text(
        f"""
schema_version: silver_only_tuning_config_v1
policy:
  modify_official_denominator_registry: false
corpora:
  text_rag_chunks_jsonl: {corpus.as_posix()}
input_silver_train_files:
  text_positive: {(base / 'silver_text_positive_train.csv').as_posix()}
  text_hard_negative: {(base / 'silver_text_hard_negative_train.csv').as_posix()}
  text_abstain_diagnostic: {(base / 'silver_text_abstain_diagnostic.csv').as_posix()}
  pdf_file_lookup_positive: {(base / 'silver_pdf_file_lookup_positive_train.csv').as_posix()}
  pdf_file_lookup_hard_negative: {(base / 'silver_pdf_file_lookup_hard_negative_train.csv').as_posix()}
frozen_gold_eval_files:
  text_main_positive: {(base / 'text_gold_main_positive_clean.csv').as_posix()}
  text_abstain_diagnostic: {(base / 'text_gold_abstain_diagnostic_clean.csv').as_posix()}
  pdf_file_lookup_positive: {(base / 'pdf_file_lookup_gold_positive_clean.csv').as_posix()}
  pdf_file_lookup_diagnostic: {(base / 'pdf_file_lookup_diagnostic_clean.csv').as_posix()}
leakage_guard_settings:
  denominator_manifest: {manifest_path.as_posix()}
  require_silver_leakage_status: PASS
  require_query_overlap_count: 0
  require_query_id_overlap_count: 0
  require_source_query_id_overlap_count: 0
  require_expected_id_overlap_count: 0
  require_silver_official_gold_false: true
  require_frozen_gold_official_gold_false: true
tuning:
  top_k: 3
  text_profiles:
    - name: baseline_text_title_section_bm25
      title_weight: 2
      alias_weight: 1
      section_weight: 1
      chunk_weight: 1
    - name: tuned_text_chunk_balanced_bm25
      title_weight: 1
      alias_weight: 1
      section_weight: 1
      chunk_weight: 2
  pdf_file_lookup_profiles:
    - name: baseline_pdf_file_identity_tokens
      lexical_weight: 1.0
      year_weight: 1.0
      month_weight: 1.0
      family_weight: 1.0
  objective:
    hit_at_10_weight: 0.45
    mrr_at_10_weight: 0.35
    recall_at_10_weight: 0.20
    hard_negative_confusion_penalty: 0.25
approved_xlsx_strict_wrapper:
  enabled_if_report_exists: false
output_report_paths:
  baseline_json: {baseline_report.as_posix()}
  baseline_md: {(reports / 'baseline.md').as_posix()}
  silver_tuning_run_json: {silver_report.as_posix()}
  silver_tuning_run_md: {(reports / 'silver.md').as_posix()}
  gold_eval_after_silver_tuning_json: {gold_report.as_posix()}
  gold_eval_after_silver_tuning_md: {(reports / 'gold.md').as_posix()}
  before_after_metric_delta_md: {delta.as_posix()}
""",
        encoding="utf-8",
    )
    return {
        "config": config,
        "reports": reports,
        "baseline_report": baseline_report,
        "silver_report": silver_report,
        "gold_report": gold_report,
        "delta": delta,
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fieldnames)
        writer.writerows(rows)


def write_shadow_fixture_inputs(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    write_csv(
        reports / "rag_pdf_supplemental_parse_canary.csv",
        [
            "file_name",
            "native_text_pdf",
            "ocr_required_candidate",
            "ocr_fallback_success",
            "ocr_confidence_avg",
        ],
        [["fixture.pdf", "True", "True", "True", "0.93"]],
    )
    (reports / "rag_pdf_supplemental_parse_canary_report.json").write_text(
        json.dumps({"counts": {"ocr_confidence_avg": 0.93}}),
        encoding="utf-8",
    )
    (reports / "xlsx_strict_silver_generation_20260507.json").write_text(
        json.dumps(
            {
                "status": "DIAGNOSTIC_ONLY",
                "promotion_evidence": False,
                "official_denominator_changed": False,
            }
        ),
        encoding="utf-8",
    )
    dataset_dir = tmp_path / "eval" / "datasets"
    image_dir = tmp_path / "fixtures" / "posters"
    dataset_dir.mkdir(parents=True)
    image_dir.mkdir(parents=True)
    image_path = image_dir / "sample.png"
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow not installed; multimodal shadow diagnostic cannot decode local image")
    Image.new("RGB", (2, 3), color=(220, 30, 30)).save(image_path, format="PNG")
    (dataset_dir / "multimodal_anime_kr.jsonl").write_text(
        json.dumps(
            {
                "image": "../../fixtures/posters/sample.png",
                "question": "what is shown?",
                "expected_keywords": ["sample"],
                "expected_labels": [],
                "requires_ocr": False,
                "language": "eng",
            }
        )
        + "\n",
        encoding="utf-8",
    )
