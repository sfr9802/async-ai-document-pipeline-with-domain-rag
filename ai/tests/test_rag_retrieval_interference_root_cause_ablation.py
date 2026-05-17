from __future__ import annotations

import csv
import builtins
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_retrieval_interference_root_cause_ablation.py"
OFFICIAL_REGISTRY = ROOT / "ai" / "eval" / "eval_queries" / "official_denominator_registry.json"
HIDDEN_SENTINEL = "DO_NOT_EXPOSE_HIDDEN_XLSX"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_retrieval_interference_root_cause_ablation_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_text_namu_metadata_hard_negative_objective_and_guardrails(tmp_path: Path):
    module = load_module()
    config = fixture_config(tmp_path)
    before_registry = read_registry_bytes()

    report, by_query = module.build_report(config, run_reranker=False)
    serialized = json.dumps({"report": report, "by_query": by_query}, ensure_ascii=False)

    assert read_registry_bytes() == before_registry
    assert HIDDEN_SENTINEL not in serialized
    assert report["production_index_mutation"] is False
    assert report["vector_write_attempted"] is False
    assert report["official_denominator_registry_changed"] is False
    assert report["hidden_xlsx_exposed"] is False
    assert report["text_namu_root_cause"]["primary_cause"] == "near_duplicate_metadata_hard_negative_objective_without_query_echo"
    assert report["text_namu_root_cause"]["metric_artifact_or_real_instability"] == (
        "text_near_duplicate_condition_now_metadata_only_diagnostic"
    )
    assert report["text_namu_ablation"]["near_duplicate_distractor_policy"] == "metadata_hard_negative_without_query_echo"
    assert report["text_namu_ablation"]["near_duplicate_query_echo_loss"] == report["text_namu_ablation"]["near_duplicate_without_query_echo_loss"]
    assert report["phase3_optuna_diagnostic_ready"] is False
    assert any(
        priority.startswith("TEXT_NAMU: add near-duplicate metadata hard negatives")
        for priority in report["dataset_supplementation_priorities"]
    )


def test_reranker_disabled_report_does_not_import_torch_or_transformers(tmp_path: Path, monkeypatch):
    module = load_module()
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in {"torch", "sentence_transformers", "transformers"}:
            raise AssertionError(f"heavy import should be isolated from run_reranker=false tests: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    report, _ = module.build_report(fixture_config(tmp_path), run_reranker=False)

    assert report["reranker_availability"]["probe_mode"] == "skipped_reranker_disabled"
    assert report["reranker_availability"]["package_available"] is None


def test_metric_sanity_adjusts_text_citation_location_when_location_json_missing(tmp_path: Path):
    module = load_module()
    report, by_query = module.build_report(fixture_config(tmp_path), run_reranker=False)

    sanity = report["metric_sanity"]
    text_e = sanity["component_means_by_lane_condition"]["TEXT_NAMU"]["E_baseline_plus_near_duplicate_metadata_file_name_distractors"]

    assert sanity["passed"] is True
    assert sanity["text_namu_citation_location_degradation_counted_as_real_failure"] is False
    assert text_e["citation_location_degradation_raw"] == 1.0
    assert text_e["citation_location_degradation_effective"] == 0.0
    assert any(
        row["analysis_type"] == "metric_sanity"
        and row["lane"] == "TEXT_NAMU"
        and row["condition"] == "E_baseline_plus_near_duplicate_metadata_file_name_distractors"
        and row["citation_location_degradation_effective"] == 0
        for row in by_query
    )


def test_pdf_file_identity_ablation_stays_identity_only(tmp_path: Path):
    module = load_module()
    report, _ = module.build_report(fixture_config(tmp_path), run_reranker=False)
    pdf = report["pdf_file_identity_ablation"]

    assert pdf["pdf_file_lookup_policy"] == module.vector_diag.PDF_FILE_IDENTITY_ONLY_POLICY
    assert pdf["content_identity_mixing_risk"] is False
    assert report["guardrails"]["pdf_file_lookup_content_claimed"] is False
    assert "exact_canonical_identity_mismatch" in pdf["classification_counts"]


def fixture_config(tmp_path: Path) -> dict:
    diversity_json = tmp_path / "retrieval_corpus_diversity_profile.json"
    ood_json = tmp_path / "retrieval_ood_split_report.json"
    vector_json = tmp_path / "vector_interference_diagnostic.json"
    by_query_csv = tmp_path / "vector_interference_diagnostic_by_query.csv"
    text_q = tmp_path / "text_queries.csv"
    text_chunks = tmp_path / "rag_chunks.jsonl"
    pdf_file_q = tmp_path / "pdf_file_queries.csv"

    write_csv(
        text_q,
        ["query_id", "query", "bucket", "expected_page_ids", "expected_document_ids", "expected_chunk_ids"],
        [["t1", "alpha overview", "fact", "doc-alpha", "doc-alpha", "chunk-alpha"]],
    )
    write_jsonl(
        text_chunks,
        [
            {
                "chunk_id": "chunk-alpha",
                "doc_id": "doc-alpha",
                "title": "Alpha",
                "section_path": ["개요"],
                "section_type": "summary",
                "chunk_text": "alpha overview",
                "embedding_text": "제목: Alpha\n섹션: 개요\n본문:\nalpha overview",
            },
            {
                "chunk_id": "chunk-beta",
                "doc_id": "doc-beta",
                "title": "Beta",
                "section_path": ["개요"],
                "section_type": "summary",
                "chunk_text": "beta unrelated",
                "embedding_text": "제목: Beta\n섹션: 개요\n본문:\nbeta unrelated",
            },
        ],
    )
    write_csv(
        pdf_file_q,
        ["query_id", "query", "expected_file_name", "source_file_name", "expected_document_version_id"],
        [["pf1", "2024 04 bill pdf", "2024_04_bill.pdf", "2024_04_bill.pdf", "docv-1"]],
    )

    diversity = {
        "schema_version": "retrieval_corpus_diversity_profile_v1",
        "production_index_mutation": False,
        "vector_write_attempted": False,
        "official_denominator_registry_changed": False,
        "hidden_xlsx_exposed": False,
        "lanes": {
            "TEXT_NAMU": {
                "classification": "SUFFICIENT_DIVERSITY_FOR_DIAGNOSTIC",
                "row_count": 1,
                "source_document_count": 2,
                "document_family_count": 2,
                "chunk_near_duplicate_rate": 0.0,
                "location_json_availability": {"available_count": 0},
            },
            "XLSX": {
                "classification": "LOW_DIVERSITY_HIGH_OVERFIT_RISK",
                "row_count": 1,
                "source_document_count": 1,
                "document_family_count": 1,
                "chunk_near_duplicate_rate": 0.9,
            },
            "PDF_CONTENT": {
                "classification": "LOW_DIVERSITY_HIGH_OVERFIT_RISK",
                "row_count": 1,
                "source_document_count": 1,
                "document_family_count": 1,
                "chunk_near_duplicate_rate": 0.9,
            },
        },
    }
    write_json(diversity_json, diversity)
    write_json(
        ood_json,
        {
            "schema_version": "retrieval_ood_split_report_v1",
            "production_index_mutation": False,
            "vector_write_attempted": False,
            "official_denominator_registry_changed": False,
            "hidden_xlsx_exposed": False,
        },
    )
    write_json(
        vector_json,
        {
            "schema_version": "vector_interference_diagnostic_v1",
            "production_index_mutation": False,
            "vector_write_attempted": False,
            "official_denominator_registry_changed": False,
            "hidden_xlsx_exposed": False,
            "pdf_file_lookup_content_page_bbox_table_row_column_value_claimed": False,
            "lane_summary": {
                "TEXT_NAMU": {"baseline_mrr_at_10": 1.0},
                "XLSX": {"baseline_mrr_at_10": 1.0},
                "PDF_CONTENT": {"baseline_mrr_at_10": 1.0},
            },
            "lane_condition_metrics": {
                "TEXT_NAMU": {
                    "A_baseline_corpus_only": {"vector_interference_loss": 0.0},
                    "E_baseline_plus_near_duplicate_metadata_file_name_distractors": {"vector_interference_loss": 0.205},
                },
                "PDF_FILE_IDENTITY": {
                    "A_baseline_corpus_only": {"vector_interference_loss": 0.0},
                    "E_baseline_plus_near_duplicate_metadata_file_name_distractors": {"vector_interference_loss": 0.255},
                },
            },
        },
    )
    write_csv(
        by_query_csv,
        [
            "lane",
            "condition",
            "query_id",
            "query_hash",
            "hit_rank",
            "hit_at_1",
            "hit_at_3",
            "hit_at_5",
            "hit_at_10",
            "mrr_at_10",
            "rank_loss",
            "score_margin",
            "score_margin_collapse",
            "false_positive_top10_count",
            "false_positive_increase",
            "source_document_confusion",
            "lane_confusion",
            "xlsx_table_header_confusion",
            "pdf_file_identity_confusion",
            "citation_location_degradation",
            "vector_interference_loss",
        ],
        [
            ["TEXT_NAMU", "A_baseline_corpus_only", "t1", "hash", "1", "1", "1", "1", "1", "1.0", "0", "0.5", "0.0", "0", "0", "0", "0", "0", "0", "0", "0.0"],
            ["TEXT_NAMU", "E_baseline_plus_near_duplicate_metadata_file_name_distractors", "t1", "hash", "2", "0", "1", "1", "1", "0.5", "1", "-0.1", "0.6", "1", "1", "0", "0", "0", "0", "1", "0.205"],
            ["PDF_FILE_IDENTITY", "A_baseline_corpus_only", "pf1", "hash", "1", "1", "1", "1", "1", "1.0", "0", "0.1", "0.0", "1", "0", "0", "0", "0", "1", "0", "0.0"],
            ["PDF_FILE_IDENTITY", "E_baseline_plus_near_duplicate_metadata_file_name_distractors", "pf1", "hash", "2", "0", "1", "1", "1", "0.5", "1", "-0.3", "0.4", "2", "1", "1", "0", "0", "1", "0", "0.255"],
        ],
    )

    return {
        "schema_version": "retrieval_ood_interference_diagnostic_config_v1",
        "prerequisites": {"phase1_corpus_diversity_profile": str(diversity_json)},
        "interference": {"max_baseline_candidates_per_lane": 20},
        "lanes": [
            {
                "name": "TEXT_NAMU",
                "query_sources": [{"role": "text", "path": str(text_q)}],
                "chunk_sources": [{"type": "jsonl", "path": str(text_chunks)}],
            },
            {
                "name": "PDF_FILE_IDENTITY",
                "identity_only": True,
                "query_sources": [{"role": "pdf-file", "path": str(pdf_file_q)}],
            },
        ],
        "outputs": {
            "split_report_json": str(ood_json),
            "interference_report_json": str(vector_json),
            "interference_by_query_csv": str(by_query_csv),
        },
    }


def read_registry_bytes() -> bytes:
    return OFFICIAL_REGISTRY.read_bytes() if OFFICIAL_REGISTRY.exists() else b""


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def write_csv(path: Path, fields: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        writer.writerows(rows)
