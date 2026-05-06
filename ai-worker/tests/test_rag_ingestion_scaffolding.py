from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
LINEAGE_ARCHIVE_SCRIPTS = (
    ROOT
    / "archive"
    / "results"
    / "2026-05-05-eval-query-lineage-cleanup"
    / "scripts"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


gate_module = load_module(
    "rag_ingestion_promotion_gate",
    ROOT / "ai-worker" / "eval" / "harness" / "rag_ingestion_promotion_gate.py",
)
batch_module = load_module(
    "rag_ingestion_sample_batch",
    ROOT / "ai-worker" / "scripts" / "rag_ingestion_sample_batch.py",
)
pdf_module = load_module(
    "rag_pdf_ingestion_smoke",
    ROOT / "ai-worker" / "scripts" / "rag_pdf_ingestion_smoke.py",
)
pdf_batch_module = load_module(
    "rag_pdf_ingestion_sample_batch",
    ROOT / "ai-worker" / "scripts" / "rag_pdf_ingestion_sample_batch.py",
)
promotion_metrics_module = load_module(
    "rag_build_promotion_gate_metrics",
    ROOT / "ai-worker" / "scripts" / "rag_build_promotion_gate_metrics.py",
)
path_readiness_module = load_module(
    "rag_path_separation_readiness",
    ROOT / "ai-worker" / "scripts" / "rag_path_separation_readiness.py",
)
embedding_consistency_module = load_module(
    "pdf_xlsx_candidate_embedding_consistency",
    LINEAGE_ARCHIVE_SCRIPTS / "pdf_xlsx_candidate_embedding_consistency.py",
)
immutable_baseline_module = load_module(
    "rag_prepare_immutable_baseline",
    ROOT / "ai-worker" / "scripts" / "rag_prepare_immutable_baseline.py",
)
bootstrap_baseline_module = load_module(
    "rag_bootstrap_initial_vector_baseline",
    LINEAGE_ARCHIVE_SCRIPTS / "rag_bootstrap_initial_vector_baseline.py",
)
quality_breakdown_module = load_module(
    "rag_full72_vector_quality_breakdown",
    LINEAGE_ARCHIVE_SCRIPTS / "rag_full72_vector_quality_breakdown.py",
)
query_cleanup_module = load_module(
    "rag_query_evidence_cleanup_plan",
    LINEAGE_ARCHIVE_SCRIPTS / "rag_query_evidence_cleanup_plan.py",
)
promotion_eval_readiness_module = load_module(
    "rag_promotion_grade_vector_eval_readiness",
    LINEAGE_ARCHIVE_SCRIPTS / "rag_promotion_grade_vector_eval_readiness.py",
)
source_qualified_readiness_module = load_module(
    "rag_source_qualified_gate_input_readiness",
    ROOT / "ai-worker" / "scripts" / "rag_source_qualified_gate_input_readiness.py",
)


def test_promotion_gate_blocks_missing_required_metadata():
    result = gate_module.evaluate_promotion_gate(
        index_version="candidate-20260503-001",
        metrics={
            "parser_success_rate": 0.98,
            "unsupported_file_rate": 0.01,
            "zero_indexable_chunk_count": 0,
            "required_metadata_completeness": 0.99,
            "missing_required_metadata_count": 1,
            "xlsx_citation_location_accuracy": 0.90,
            "pdf_citation_location_accuracy": 0.85,
            "table_detection_accuracy": 0.82,
            "Hit@10": 0.80,
            "MRR@10": 0.70,
            "citation_accuracy": 0.90,
            "parsing_latency_p95": 12.0,
            "indexing_latency_p95": 20.0,
            "fatal_warning_count": 0,
        },
        baseline_metrics={"Hit@10": 0.82, "MRR@10": 0.72},
    )

    assert result.decision == "BLOCKED"
    assert "missing_required_metadata_count must be 0" in result.reasons


def test_promotion_gate_passes_clean_candidate_with_baseline_margin():
    result = gate_module.evaluate_promotion_gate(
        index_version="candidate-clean",
        metrics={
            "parser_success_rate": 0.95,
            "unsupported_file_rate": 0.05,
            "zero_indexable_chunk_count": 0,
            "required_metadata_completeness": 0.98,
            "missing_required_metadata_count": 0,
            "xlsx_citation_location_accuracy": 0.90,
            "pdf_citation_location_accuracy": 0.85,
            "table_detection_accuracy": 0.80,
            "Hit@10": 0.77,
            "MRR@10": 0.67,
            "citation_accuracy": 0.85,
            "parsing_latency_p95": 30.0,
            "indexing_latency_p95": 60.0,
            "fatal_warning_count": 0,
            "hidden_content_leakage_count": 0,
            "retrieval_backend": "vector",
            "retrieval_backend_identity": {
                "backend": "faiss",
                "index_namespace_filter": "candidate-clean",
            },
            "promotion_evidence": True,
            "evidence_role": "promotion",
            "embedding_filtered_eval": True,
            "required_embedding_status": "EMBEDDED",
            "required_index_version": "candidate-clean",
            "gate_input_missing_count": 0,
            "indexing_filtered_hit_count": 0,
            "candidate_index_mismatch_count": 0,
            "required_index_version_mismatch_count": 0,
            "embedding_status_mismatch_count": 0,
            "eval_dataset_id": "gold_queries_v0",
            "eval_dataset_version": "strict_B_vector_v1",
            "eval_dataset_sha256": "gold-sha",
            "gold_query_row_count": 72,
        },
        baseline_metrics={
            "Hit@10": 0.80,
            "MRR@10": 0.70,
            "_baseline_immutable": True,
            "immutable_baseline_report_hash": "hash",
            "baseline_provenance": "previous-promoted-index",
            "baseline_dataset_version": "strict_B_vector_v1",
            "eval_dataset_id": "gold_queries_v0",
            "eval_dataset_sha256": "gold-sha",
            "gold_query_row_count": 72,
        },
    )

    assert result.to_dict()["decision"] == "PASSED"
    assert result.reasons == []


def test_promotion_gate_blocks_omitted_required_metadata_count():
    metrics = _clean_gate_metrics("candidate-clean")
    metrics.pop("missing_required_metadata_count")

    result = gate_module.evaluate_promotion_gate(
        index_version="candidate-clean",
        metrics=metrics,
        baseline_metrics={"Hit@10": 0.80, "MRR@10": 0.70},
    )

    assert result.decision == "BLOCKED"
    assert "missing_required_metadata_count is required" in result.reasons


def test_promotion_gate_blocks_omitted_hidden_leakage_metric():
    metrics = _clean_gate_metrics("candidate-clean")
    metrics.pop("hidden_content_leakage_count")

    result = gate_module.evaluate_promotion_gate(
        index_version="candidate-clean",
        metrics=metrics,
        baseline_metrics={"Hit@10": 0.80, "MRR@10": 0.70},
    )

    assert result.decision == "BLOCKED"
    assert "hidden_content_leakage_count is required" in result.reasons


def test_promotion_gate_blocks_required_index_version_mismatch():
    metrics = _clean_gate_metrics("other-candidate")

    result = gate_module.evaluate_promotion_gate(
        index_version="candidate-clean",
        metrics=metrics,
        baseline_metrics={"Hit@10": 0.80, "MRR@10": 0.70},
    )

    assert result.decision == "BLOCKED"
    assert "required_index_version must match promoted index_version" in result.reasons


def test_promotion_gate_blocks_library_search_backend_even_when_metrics_are_clean():
    metrics = _clean_gate_metrics("candidate-clean")
    metrics["retrieval_backend"] = "library_search"

    result = gate_module.evaluate_promotion_gate(
        index_version="candidate-clean",
        metrics=metrics,
        baseline_metrics={
            "Hit@10": 0.80,
            "MRR@10": 0.70,
            "_baseline_immutable": True,
            "immutable_baseline_report_hash": "hash",
            "baseline_provenance": "previous-promoted-index",
            "baseline_dataset_version": "strict_B_vector_v1",
        },
    )

    assert result.decision == "BLOCKED"
    assert "retrieval_backend=library_search is diagnostic-only and cannot be promotion evidence" in result.reasons


def test_promotion_gate_blocks_missing_vector_backend_identity():
    metrics = _clean_gate_metrics("candidate-clean")
    metrics.pop("retrieval_backend_identity")

    result = gate_module.evaluate_promotion_gate(
        index_version="candidate-clean",
        metrics=metrics,
        baseline_metrics={
            "Hit@10": 0.80,
            "MRR@10": 0.70,
            "_baseline_immutable": True,
            "immutable_baseline_report_hash": "hash",
            "baseline_provenance": "previous-promoted-index",
            "baseline_dataset_version": "strict_B_vector_v1",
        },
    )

    assert result.decision == "BLOCKED"
    assert "retrieval_backend_identity is required for promotion" in result.reasons


def test_promotion_gate_blocks_vector_namespace_mismatch():
    metrics = _clean_gate_metrics("candidate-clean")
    metrics["retrieval_backend_identity"] = {
        "backend": "faiss",
        "index_namespace_filter": "other-candidate",
    }

    result = gate_module.evaluate_promotion_gate(
        index_version="candidate-clean",
        metrics=metrics,
        baseline_metrics={
            "Hit@10": 0.80,
            "MRR@10": 0.70,
            "_baseline_immutable": True,
            "immutable_baseline_report_hash": "hash",
            "baseline_provenance": "previous-promoted-index",
            "baseline_dataset_version": "strict_B_vector_v1",
        },
    )

    assert result.decision == "BLOCKED"
    assert "retrieval_backend_identity.index_namespace_filter must match promoted index_version" in result.reasons


def test_batch_manifest_resolves_paths_from_cwd_fallback():
    manifest_path = ROOT / "ai-worker" / "fixtures" / "manifests" / "rag_ingestion_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sample = manifest["samples"][0]

    resolved = batch_module.resolve_sample_path(sample["file_path"], manifest_path)

    assert resolved == ROOT / "ai-worker" / sample["file_path"]


def test_batch_db_report_validation_fails_on_missing_metadata():
    with pytest.raises(AssertionError, match="missing_required_metadata_count"):
        batch_module.validate_sample_db_report(
            {
                "search_unit_count": 3,
                "missing_required_metadata_count": 1,
                "citation_pattern_counts": [],
            },
            sample={"expected_min_search_units": 3},
            defaults={},
        )


def test_pdf_report_validation_requires_metadata_and_locations():
    pdf_module.validate_pdf_report(
        {
            "pdf_search_unit_count": 2,
            "missing_pdf_citation_metadata": 0,
            "invalid_pdf_location_count": 0,
            "missing_pdf_citation_text_count": 0,
            "pdf_page_metadata_count": 1,
            "missing_page_metadata_count": 0,
        }
    )

    with pytest.raises(AssertionError, match="invalid_pdf_location_count"):
        pdf_module.validate_pdf_report(
            {
                "pdf_search_unit_count": 2,
                "missing_pdf_citation_metadata": 0,
                "invalid_pdf_location_count": 1,
                "missing_pdf_citation_text_count": 0,
            }
        )


def test_pdf_batch_manifest_resolves_real_sample_paths():
    manifest_path = ROOT / "ai-worker" / "fixtures" / "manifests" / "rag_pdf_ingestion_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["samples"]) >= 8

    for sample in manifest["samples"]:
        resolved = pdf_batch_module.resolve_sample_path(
            sample.get("file_path") or sample["path"],
            manifest_path,
        )
        assert resolved.exists(), sample["sample_id"]


def test_promotion_metrics_builder_reports_missing_critical_counters(tmp_path):
    xlsx_report = tmp_path / "xlsx.json"
    pdf_report = tmp_path / "pdf.json"
    retrieval_report = tmp_path / "retrieval.json"
    ocr_report = tmp_path / "ocr.json"
    output = tmp_path / "metrics.json"
    xlsx_report.write_text(json.dumps({
        "metrics": {
            "parser_success_rate": 1.0,
            "missing_required_metadata_count": 0,
            "zero_indexable_chunk_count": 0,
            "unsupported_file_rate": 0.0,
            "fatal_warning_count": 0,
            "missing_table_metadata_count": 0,
            "hidden_search_unit_leakage_count": 0,
        }
    }), encoding="utf-8")
    pdf_report.write_text(json.dumps({
        "metrics": {
            "parser_success_rate": 1.0,
            "missing_required_metadata_count": 0,
            "zero_indexable_chunk_count": 0,
            "unsupported_file_rate": 0.0,
            "fatal_warning_count": 0,
            "missing_page_metadata_count": 0,
            "inconsistent_location_page_metadata_count": 0,
        }
    }), encoding="utf-8")
    retrieval_report.write_text(json.dumps({
        "metrics": {
            "xlsx_citation_location_accuracy": 1.0,
            "pdf_citation_location_accuracy": 1.0,
            "Hit@10": 1.0,
            "MRR@10": 1.0,
            "citation_accuracy": 1.0,
            "citation_location_accuracy": 1.0,
            "embedding_filtered_eval": True,
            "required_embedding_status": "EMBEDDED",
            "required_index_version": "candidate-clean",
        }
    }), encoding="utf-8")
    ocr_report.write_text(json.dumps({
        "status": "SKIPPED",
        "metrics": {"fatal_warning_count": 0},
    }), encoding="utf-8")

    rc = promotion_metrics_module.main([
        "--xlsx-report", str(xlsx_report),
        "--pdf-report", str(pdf_report),
        "--retrieval-report", str(retrieval_report),
        "--ocr-report", str(ocr_report),
        "--output", str(output),
        "--candidate-index-version", "candidate-clean",
    ])

    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    missing = payload["metrics"]["gate_input_missing"]
    assert "retrieval.hidden_content_leakage_count" in missing
    assert "retrieval.indexing_filtered_hit_count" in missing
    assert payload["metrics"]["gate_input_missing_count"] == len(missing)


def test_promotion_metrics_builder_does_not_clear_missing_with_derived_values(tmp_path):
    xlsx_report = tmp_path / "xlsx.json"
    pdf_report = tmp_path / "pdf.json"
    retrieval_report = tmp_path / "retrieval.json"
    output = tmp_path / "metrics.json"
    xlsx_report.write_text(json.dumps({"metrics": {
        "parser_success_rate": 1.0,
        "missing_required_metadata_count": 0,
        "zero_indexable_chunk_count": 0,
        "unsupported_file_rate": 0.0,
        "fatal_warning_count": 0,
        "missing_table_metadata_count": 0,
        "hidden_search_unit_leakage_count": 0,
        "parsing_latency_p95_seconds": 1.0,
        "indexing_latency_p95_seconds": 1.0,
    }}), encoding="utf-8")
    pdf_report.write_text(json.dumps({"status": "COMPLETED", "failed": 0, "metrics": {
        "parser_success_rate": 1.0,
        "missing_required_metadata_count": 0,
        "zero_indexable_chunk_count": 0,
        "missing_page_metadata_count": 0,
        "inconsistent_location_page_metadata_count": 0,
        "invalid_pdf_location_count": 0,
        "missing_pdf_citation_text_count": 0,
        "parsing_latency_p95_seconds": 1.0,
        "indexing_latency_p95_seconds": 1.0,
    }}), encoding="utf-8")
    retrieval_report.write_text(json.dumps({"metrics": {
        "Hit@10": 1.0,
        "MRR@10": 1.0,
        "citation_accuracy": 1.0,
        "hidden_content_leakage_count": 0,
        "indexing_filtered_hit_count": 0,
        "required_index_version_mismatch_count": 0,
        "embedding_status_mismatch_count": 0,
        "candidate_index_mismatch_count": 0,
        "result_empty_count": 0,
        "gold_label_invalid_count": 0,
        "embedding_filtered_eval": True,
        "required_embedding_status": "EMBEDDED",
        "required_index_version": "candidate-clean",
    }}), encoding="utf-8")

    rc = promotion_metrics_module.main([
        "--xlsx-report", str(xlsx_report),
        "--pdf-report", str(pdf_report),
        "--retrieval-report", str(retrieval_report),
        "--ocr-report", str(tmp_path / "missing-ocr.json"),
        "--output", str(output),
        "--candidate-index-version", "candidate-clean",
    ])

    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    missing = payload["metrics"]["gate_input_missing"]
    assert "xlsx.hidden_content_leakage_count" in missing
    assert "pdf.unsupported_file_rate" in missing
    assert payload["metrics"]["derived_metric_sources"]["pdf.unsupported_file_rate"].startswith("diagnostic_only:")


def test_immutable_baseline_prep_rejects_candidate_snapshot(tmp_path):
    baseline = tmp_path / "candidate-baseline.json"
    readiness = tmp_path / "readiness.json"
    baseline.write_text(json.dumps({
        "candidate_snapshot": True,
        "metrics": {"Hit@10": 0.8, "MRR@10": 0.7, "citation_accuracy": 0.9},
    }), encoding="utf-8")

    rc = immutable_baseline_module.main([
        "--baseline-report", str(baseline),
        "--output", str(readiness),
        "--baseline-index-version", "rag-ingestion-v2-baseline",
        "--candidate-index-version", "rag-ingestion-v2-candidate",
        "--eval-dataset-version", "strict_B_vector_v1",
        "--baseline-provenance", "previous-promoted-index",
    ])

    assert rc == 2
    payload = json.loads(readiness.read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert "candidate_snapshot baseline cannot be immutable" in payload["reasons"]


def test_immutable_baseline_prep_writes_descriptor_for_valid_vector_report(tmp_path):
    baseline = tmp_path / "vector-baseline.json"
    readiness = tmp_path / "readiness.json"
    immutable = tmp_path / "immutable.json"
    baseline.write_text(json.dumps({
        "immutable_baseline": True,
        "retrieval_backend": "vector",
        "eval_dataset_version": "strict_B_vector_v1",
        "baseline_provenance": "previous-promoted-index",
        "metrics": {"Hit@10": 0.8, "MRR@10": 0.7, "citation_accuracy": 0.9},
    }), encoding="utf-8")

    rc = immutable_baseline_module.main([
        "--baseline-report", str(baseline),
        "--output", str(readiness),
        "--immutable-output", str(immutable),
        "--baseline-index-version", "rag-ingestion-v2-baseline",
        "--candidate-index-version", "rag-ingestion-v2-candidate",
        "--eval-dataset-version", "strict_B_vector_v1",
        "--baseline-provenance", "previous-promoted-index",
    ])

    assert rc == 0
    payload = json.loads(immutable.read_text(encoding="utf-8"))
    assert payload["candidate_snapshot"] is False
    assert payload["immutable_baseline"] is True
    assert payload["baseline_dataset_version"] == "strict_B_vector_v1"


def test_initial_baseline_bootstrap_writes_non_promotional_descriptor(tmp_path):
    paths = _write_bootstrap_inputs(tmp_path)

    rc = bootstrap_baseline_module.main([
        "--retrieval-report", str(paths["retrieval"]),
        "--metrics-report", str(paths["metrics"]),
        "--gold", str(paths["gold"]),
        "--vector-index-dir", str(paths["index_dir"]),
        "--consistency-report", str(paths["consistency"]),
        "--scope-readiness-report", str(paths["scope"]),
        "--descriptor-output", str(paths["descriptor"]),
        "--readiness-output", str(paths["readiness"]),
        "--baseline-index-version", "initial-full72-vector-baseline-v0",
        "--source-candidate-index-version", "candidate-v2",
        "--eval-dataset-version", "full72_vector_diagnostic_v0",
    ])

    assert rc == 0
    readiness = json.loads(paths["readiness"].read_text(encoding="utf-8"))
    descriptor = json.loads(paths["descriptor"].read_text(encoding="utf-8"))
    assert readiness["status"] == "PASS"
    assert descriptor["baseline_type"] == "INITIAL_BASELINE_BOOTSTRAP"
    assert descriptor["bootstrap_status"] == "BOOTSTRAP_READY_NOT_PROMOTION"
    assert descriptor["promotion_evidence"] is False
    assert descriptor["promotion_gate_effect"] == "none"
    assert descriptor["candidate_snapshot"] is False
    assert descriptor["usable_as_baseline_for_future_candidates"] is True
    assert descriptor["source_candidate_index_version"] == "candidate-v2"
    assert descriptor["candidate_namespace_filter"] == "candidate-v2"
    assert descriptor["baseline_index_version"] == "initial-full72-vector-baseline-v0"
    assert descriptor["retrieval_report_sha256"]
    assert descriptor["immutable_baseline_report_hash"] == descriptor["retrieval_report_sha256"]
    assert descriptor["metrics_report_sha256"]
    assert descriptor["eval_dataset_sha256"]
    assert descriptor["vector_index_hash"]


def test_initial_baseline_bootstrap_descriptor_passes_c3_readiness(tmp_path):
    paths = _write_bootstrap_inputs(tmp_path)
    assert bootstrap_baseline_module.main([
        "--retrieval-report", str(paths["retrieval"]),
        "--metrics-report", str(paths["metrics"]),
        "--gold", str(paths["gold"]),
        "--vector-index-dir", str(paths["index_dir"]),
        "--consistency-report", str(paths["consistency"]),
        "--scope-readiness-report", str(paths["scope"]),
        "--descriptor-output", str(paths["descriptor"]),
        "--readiness-output", str(paths["readiness"]),
        "--baseline-index-version", "initial-full72-vector-baseline-v0",
        "--source-candidate-index-version", "candidate-v2",
    ]) == 0

    c3_readiness = tmp_path / "c3.json"
    rc = immutable_baseline_module.main([
        "--baseline-report", str(paths["descriptor"]),
        "--output", str(c3_readiness),
        "--baseline-index-version", "initial-full72-vector-baseline-v0",
        "--candidate-index-version", "candidate-v2",
    ])

    assert rc == 0
    payload = json.loads(c3_readiness.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["baseline_type"] == "INITIAL_BASELINE_BOOTSTRAP"
    assert payload["promotion_evidence"] is False


def test_initial_baseline_bootstrap_fails_without_namespace_filter(tmp_path):
    paths = _write_bootstrap_inputs(tmp_path)
    retrieval = json.loads(paths["retrieval"].read_text(encoding="utf-8"))
    retrieval["backend_identity"].pop("index_namespace_filter")
    paths["retrieval"].write_text(json.dumps(retrieval), encoding="utf-8")

    rc = bootstrap_baseline_module.main([
        "--retrieval-report", str(paths["retrieval"]),
        "--metrics-report", str(paths["metrics"]),
        "--gold", str(paths["gold"]),
        "--vector-index-dir", str(paths["index_dir"]),
        "--consistency-report", str(paths["consistency"]),
        "--scope-readiness-report", str(paths["scope"]),
        "--descriptor-output", str(paths["descriptor"]),
        "--readiness-output", str(paths["readiness"]),
        "--baseline-index-version", "initial-full72-vector-baseline-v0",
        "--source-candidate-index-version", "candidate-v2",
    ])

    assert rc == 2
    payload = json.loads(paths["readiness"].read_text(encoding="utf-8"))
    assert "backend_identity.index_namespace_filter is required" in payload["blockers"]


def test_immutable_baseline_prep_rejects_library_search_even_when_allowed(tmp_path):
    baseline = tmp_path / "library-search-baseline.json"
    readiness = tmp_path / "readiness.json"
    baseline.write_text(json.dumps({
        "immutable_baseline": True,
        "retrieval_backend": "library_search",
        "eval_dataset_version": "strict_B_vector_v1",
        "baseline_provenance": "previous-report",
        "metrics": {"Hit@10": 0.8, "MRR@10": 0.7, "citation_accuracy": 0.9},
    }), encoding="utf-8")

    rc = immutable_baseline_module.main([
        "--baseline-report", str(baseline),
        "--output", str(readiness),
        "--baseline-index-version", "rag-ingestion-v2-baseline",
        "--candidate-index-version", "rag-ingestion-v2-candidate",
        "--allow-non-vector-backend",
    ])

    assert rc == 2
    payload = json.loads(readiness.read_text(encoding="utf-8"))
    assert "library_search report cannot be an immutable baseline" in payload["reasons"]


def test_quality_breakdown_separates_pdf_metadata_projection_from_ranking():
    retrieval = {
        "retrieval_backend": "vector",
        "evidence_role": "diagnostic",
        "promotion_evidence": False,
        "metrics": {},
        "bucket_metrics": {},
        "query_results": [
            {
                "query_id": "q-pdf",
                "bucket": "pdf_page_lookup",
                "query": "title",
                "expected_file_name": "report.pdf",
                "expected_page_no": "1",
                "expected_physical_page_index": "0",
                "expected_bbox": "[1, 2, 3, 4]",
                "hit_rank": 1,
                "location_rank": None,
                "location_match": False,
                "failure_reason": "expected_page_not_found",
                "top_k_results": [
                    {
                        "rank": 1,
                        "source_file_name": "report.pdf",
                        "chunk_type": "paragraph",
                        "citation_text": "report.pdf > p.1 > bbox [1,2,3,4]",
                        "location_json": {"type": "pdf", "document_version_id": "docv_pdf", "page_no": 1},
                        "match_breakdown": {
                            "file_match": True,
                            "document_version_match": True,
                            "location_match": False,
                            "pdf_page_match": False,
                            "pdf_bbox_overlap": False,
                        },
                    }
                ],
            }
        ],
    }
    gold_rows = [{
        "query_id": "q-pdf",
        "expected_location_type": "pdf",
        "expected_file_name": "report.pdf",
        "expected_document_version_id": "docv_pdf",
        "expected_chunk_type": "paragraph",
        "expected_page_no": "1",
        "expected_physical_page_index": "0",
        "expected_bbox": "[1, 2, 3, 4]",
    }]

    payload = quality_breakdown_module.build_breakdown(
        retrieval=retrieval,
        gold_rows=gold_rows,
        candidate_scope={"status": "PASS"},
        global_hygiene={"status": "FAIL"},
        retrieval_report_path=Path("retrieval.json"),
        gold_path=Path("gold.csv"),
    )

    assert payload["failure_category_counts"]["pdf_page_policy_missing_physical_or_label"] == 1
    assert payload["suspect_group_counts"]["policy_or_matching_rule_suspect"] == 1
    row = payload["policy_matching_rule_suspect_rows"][0]
    assert "correct_page_no_hit_but_missing_physical_page_index" in row["diagnostic_flags"]
    assert row["supporting_hit_ranks"] == [1]
    assert row["supporting_hits"][0]["page_no"] == 1


def test_query_cleanup_plan_keeps_pdf_bbox_and_hidden_policy_separate():
    breakdown = {
        "classified_query_rows": [
            {
                "query_id": "q-ok",
                "bucket": "xlsx_lookup",
                "query": "visible",
                "failure_category": "ok",
                "suspect_group": "matched",
                "diagnostic_flags": [],
            },
            {
                "query_id": "q-pdf",
                "bucket": "pdf_page_lookup",
                "query": "page",
                "failure_category": "pdf_page_policy_missing_physical_or_label",
                "suspect_group": "policy_or_matching_rule_suspect",
                "diagnostic_flags": [
                    "correct_page_no_hit_but_missing_physical_page_index",
                    "correct_page_no_hit_but_missing_bbox",
                ],
            },
            {
                "query_id": "q-hidden-negative",
                "bucket": "xlsx_hidden_policy",
                "query": "hidden",
                "failure_category": "xlsx_expected_file_absent_in_top10",
                "suspect_group": "retrieval_text_or_ranking_suspect",
                "diagnostic_flags": [],
            },
            {
                "query_id": "q-hidden-visible",
                "bucket": "xlsx_hidden_policy",
                "query": "visible",
                "failure_category": "xlsx_expected_file_absent_in_top10",
                "suspect_group": "retrieval_text_or_ranking_suspect",
                "diagnostic_flags": [],
            },
        ],
    }
    gold_rows = [
        {"query_id": "q-ok", "hidden_policy": "exclude_hidden"},
        {"query_id": "q-pdf", "expected_location_type": "pdf", "expected_bbox": "[1,2,3,4]"},
        {
            "query_id": "q-hidden-negative",
            "hidden_policy": "exclude_hidden",
            "must_not_contain_terms": "secret",
            "notes": "negative hidden leakage query",
        },
        {
            "query_id": "q-hidden-visible",
            "hidden_policy": "exclude_hidden",
            "must_contain_terms": "visible",
            "notes": "visible control query",
        },
    ]

    payload = query_cleanup_module.build_cleanup_plan(
        breakdown=breakdown,
        gold_rows=gold_rows,
        quality_breakdown_path=Path("breakdown.json"),
        gold_path=Path("gold.csv"),
    )

    assert payload["status"] == "NEEDS_CLEANUP"
    assert payload["ready_query_count"] == 1
    assert payload["unresolved_query_count"] == 3
    assert payload["cleanup_action_counts"]["pdf_location_metadata_projection_or_matching_rule"] == 1
    assert payload["cleanup_action_counts"]["gold_policy_negative_relabel_or_exclude"] == 1
    assert payload["cleanup_action_counts"]["hidden_policy_visible_control_rebind_review"] == 1
    assert payload["pdf_page_bbox_resolution"]["metadata_projection_or_matching_policy_count"] == 1
    assert payload["promotion_grade_vector_eval_input"]["ready_now"] is False


def test_query_cleanup_plan_keeps_hidden_negative_rows_when_policy_is_explicit():
    breakdown = {
        "classified_query_rows": [
            {
                "query_id": "q-hidden-negative",
                "bucket": "xlsx_hidden_policy",
                "query": "secret",
                "failure_category": "xlsx_expected_file_absent_in_top10",
                "suspect_group": "retrieval_text_or_ranking_suspect",
                "diagnostic_flags": [],
            },
        ],
    }
    gold_rows = [{
        "query_id": "q-hidden-negative",
        "hidden_policy": "negative",
        "must_not_contain_terms": "secret",
    }]

    payload = query_cleanup_module.build_cleanup_plan(
        breakdown=breakdown,
        gold_rows=gold_rows,
        quality_breakdown_path=Path("breakdown.json"),
        gold_path=Path("gold.csv"),
    )

    assert payload["status"] == "READY"
    assert payload["ready_query_count"] == 1
    assert payload["cleanup_action_counts"]["keep_hidden_negative_policy_check"] == 1


def test_query_cleanup_plan_splits_table_chunk_ranking_from_gold_binding():
    breakdown = {
        "classified_query_rows": [
            {
                "query_id": "q-table",
                "bucket": "xlsx_header_ambiguous",
                "query": "header",
                "failure_category": "xlsx_table_metadata_or_gold_binding_mismatch",
                "suspect_group": "gold_binding_or_label_suspect",
                "diagnostic_flags": ["expected_table_id_not_present_on_range_hit"],
                "top_hits": [
                    {
                        "rank": 1,
                        "xlsx_range_policy_match": True,
                        "xlsx_table_match": False,
                    }
                ],
            },
        ],
    }
    gold_rows = [{
        "query_id": "q-table",
        "expected_chunk_type": "table",
        "expected_table_id": "DetectedTable1",
    }]

    payload = query_cleanup_module.build_cleanup_plan(
        breakdown=breakdown,
        gold_rows=gold_rows,
        quality_breakdown_path=Path("breakdown.json"),
        gold_path=Path("gold.csv"),
    )

    assert payload["cleanup_action_counts"]["xlsx_table_chunk_ranking_or_query_contract_review"] == 1
    assert payload["owner_counts"]["query_contract_or_ranking"] == 1


def test_promotion_grade_vector_readiness_rejects_diagnostic_report_and_unresolved_cleanup(tmp_path):
    retrieval = tmp_path / "retrieval.json"
    cleanup = tmp_path / "cleanup.json"
    metrics = tmp_path / "metrics.json"
    source_qualified = tmp_path / "c2.json"
    consistency = tmp_path / "consistency.json"
    scope = tmp_path / "scope.json"
    c3 = tmp_path / "c3.json"
    breakdown = tmp_path / "breakdown.json"
    gate = tmp_path / "gate.json"
    output = tmp_path / "readiness.json"
    retrieval.write_text(json.dumps({
        "retrieval_backend": "vector",
        "backend_identity": {"backend": "faiss", "index_namespace_filter": "candidate-v2"},
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
    }), encoding="utf-8")
    cleanup.write_text(json.dumps({
        "status": "NEEDS_CLEANUP",
        "promotion_evidence": False,
        "unresolved_query_count": 1,
    }), encoding="utf-8")
    metrics.write_text(json.dumps({
        "metrics": {
            "gate_input_missing_count": 0,
            "gate_input_missing": [],
            "retrieval_backend": "vector",
            "promotion_evidence": False,
            "source_reports": ["xlsx.json", "pdf.json", "retrieval.json"],
        }
    }), encoding="utf-8")
    source_qualified.write_text(json.dumps({
        "status": "PASS",
        "gate_input_missing_count": 0,
        "gate_input_missing": [],
        "derived_metric_sources": {},
        "retrieval_backend": "vector",
    }), encoding="utf-8")
    consistency.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    scope.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    c3.write_text(json.dumps({
        "status": "PASS",
        "candidate_snapshot": False,
        "baseline_type": "INITIAL_BASELINE_BOOTSTRAP",
        "promotion_evidence": False,
    }), encoding="utf-8")
    breakdown.write_text(json.dumps({"status": "COMPLETED"}), encoding="utf-8")
    gate.write_text(json.dumps({"decision": "BLOCKED", "reasons": ["citation_accuracy must be >= 0.85"]}), encoding="utf-8")

    rc = promotion_eval_readiness_module.main([
        "--retrieval-report", str(retrieval),
        "--quality-breakdown", str(breakdown),
        "--cleanup-plan", str(cleanup),
        "--metrics-report", str(metrics),
        "--source-qualified-readiness-report", str(source_qualified),
        "--consistency-report", str(consistency),
        "--candidate-scope-report", str(scope),
        "--c3-readiness-report", str(c3),
        "--gate-report", str(gate),
        "--output", str(output),
        "--candidate-index-version", "candidate-v2",
        "--baseline-index-version", "baseline-v1",
    ])

    assert rc == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "BLOCKED"
    assert payload["source_qualified_gate_input"]["status"] == "PASS"
    assert "current retrieval report is diagnostic-only; rerun with --promotion-evidence after cleanup" in payload["blockers"]
    assert "source-qualified retrieval metrics are not promotion evidence" in payload["blockers"]
    assert "query-level evidence cleanup must have unresolved_query_count=0" in payload["blockers"]
    assert payload["global_path_hygiene_separation"]["candidate_scope_status"] == "PASS"


def test_promotion_grade_vector_readiness_fails_closed_without_gate_report(tmp_path):
    retrieval = tmp_path / "retrieval.json"
    cleanup = tmp_path / "cleanup.json"
    metrics = tmp_path / "metrics.json"
    source_qualified = tmp_path / "c2.json"
    consistency = tmp_path / "consistency.json"
    scope = tmp_path / "scope.json"
    c3 = tmp_path / "c3.json"
    breakdown = tmp_path / "breakdown.json"
    output = tmp_path / "readiness.json"
    retrieval.write_text(json.dumps({
        "retrieval_backend": "vector",
        "backend_identity": {"backend": "faiss", "index_namespace_filter": "candidate-v2"},
        "promotion_evidence": True,
        "evidence_role": "promotion",
    }), encoding="utf-8")
    cleanup.write_text(json.dumps({
        "status": "READY",
        "promotion_evidence": False,
        "unresolved_query_count": 0,
    }), encoding="utf-8")
    metrics.write_text(json.dumps({
        "metrics": {
            "gate_input_missing_count": 0,
            "gate_input_missing": [],
            "retrieval_backend": "vector",
            "promotion_evidence": True,
        }
    }), encoding="utf-8")
    source_qualified.write_text(json.dumps({
        "status": "PASS",
        "gate_input_missing_count": 0,
        "gate_input_missing": [],
        "derived_metric_sources": {},
        "retrieval_backend": "vector",
    }), encoding="utf-8")
    consistency.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    scope.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    c3.write_text(json.dumps({
        "status": "PASS",
        "candidate_snapshot": False,
        "baseline_type": "INITIAL_BASELINE_BOOTSTRAP",
        "promotion_evidence": False,
    }), encoding="utf-8")
    breakdown.write_text(json.dumps({"status": "COMPLETED"}), encoding="utf-8")

    rc = promotion_eval_readiness_module.main([
        "--retrieval-report", str(retrieval),
        "--quality-breakdown", str(breakdown),
        "--cleanup-plan", str(cleanup),
        "--metrics-report", str(metrics),
        "--source-qualified-readiness-report", str(source_qualified),
        "--consistency-report", str(consistency),
        "--candidate-scope-report", str(scope),
        "--c3-readiness-report", str(c3),
        "--gate-report", str(tmp_path / "missing-gate.json"),
        "--output", str(output),
        "--candidate-index-version", "candidate-v2",
        "--baseline-index-version", "baseline-v1",
    ])

    assert rc == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert f"gate_report missing: {tmp_path / 'missing-gate.json'}" in payload["blockers"]


def test_source_qualified_gate_input_readiness_passes_diagnostic_vector_contract(tmp_path):
    required = source_qualified_readiness_module.required_canonical_names()
    metrics_report = tmp_path / "metrics.json"
    output = tmp_path / "c2.json"
    metrics_report.write_text(json.dumps({
        "metrics": {
            "canonical_metric_names": required,
            "gate_input_missing_count": 0,
            "gate_input_missing": [],
            "derived_metric_sources": {},
            "retrieval_backend": "vector",
            "promotion_evidence": False,
            "source_reports": ["xlsx.json", "pdf.json", "retrieval.json"],
        }
    }), encoding="utf-8")

    rc = source_qualified_readiness_module.main([
        "--metrics-report", str(metrics_report),
        "--output", str(output),
    ])

    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["promotion_evidence"] is False
    assert payload["gate_input_missing_count"] == 0
    assert payload["warnings"] == [
        "retrieval metrics are diagnostic-only; C2 source-qualified input can PASS without implying promotion"
    ]


def test_source_qualified_gate_input_readiness_rejects_library_search_and_derived_sources(tmp_path):
    required = source_qualified_readiness_module.required_canonical_names()
    metrics_report = tmp_path / "metrics.json"
    output = tmp_path / "c2.json"
    metrics_report.write_text(json.dumps({
        "metrics": {
            "canonical_metric_names": required,
            "gate_input_missing_count": 0,
            "gate_input_missing": [],
            "derived_metric_sources": {"xlsx.hidden_content_leakage_count": "diagnostic_only:0"},
            "retrieval_backend": "library_search",
            "promotion_evidence": True,
        }
    }), encoding="utf-8")

    rc = source_qualified_readiness_module.main([
        "--metrics-report", str(metrics_report),
        "--output", str(output),
    ])

    assert rc == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert "derived_metric_sources must be empty for source-qualified readiness" in payload["blockers"]
    assert "library_search report cannot be source-qualified promotion-grade vector input" in payload["blockers"]


def test_path_separation_readiness_fails_on_candidate_contract_gaps():
    payload = path_readiness_module.build_readiness_payload(
        snapshot={
            "text_path_summary": {"candidate_count": 3},
            "xlsx_path_summary": {
                "candidate_count": 2,
                "hidden_content_leakage_count": 1,
                "xlsx_hidden_policy_mismatch_count": 1,
                "xlsx_hidden_policy_version_mismatch_count": 1,
            },
            "pdf_path_summary": {"candidate_count": 1},
            "search_unit_contract_completeness": {
                "pdf_xlsx_candidate_count": 3,
                "missing_parser_version_count": 0,
                "missing_location_json_count": 1,
                "missing_citation_text_count": 0,
                "missing_embedding_text_count": 0,
            },
            "normalized_metadata_coverage": {
                "xlsx_table_like_search_unit_count": 1,
                "xlsx_table_metadata_count": 0,
                "xlsx_missing_table_metadata_count": 1,
                "xlsx_cell_metadata_count": 0,
                "xlsx_search_unit_metadata_matched_count": 1,
                "xlsx_search_unit_metadata_unmatched_count": 1,
                "pdf_page_metadata_count": 1,
                "pdf_missing_page_metadata_count": 0,
            },
            "embedding_index_contract_summary": {
                "not_embedded_count": 0,
                "index_version_mismatch_count": 0,
                "embedding_record_missing_count": 1,
                "candidate_chunk_missing_count": 0,
                "vector_namespace_mismatch_count": 0,
                "chunk_sha_mismatch_count": 0,
            },
            "path_mixing_findings": [],
        },
        retrieval_backend_separation_summary={"reports": []},
        blockers=[],
        warnings=[],
        expected_index_version="rag-ingestion-v2-candidate",
    )

    assert payload["status"] == "FAIL"
    assert "missing_location_json_count must be 0 for PDF/XLSX candidate SearchUnits" in payload["blockers"]
    assert "hidden XLSX leakage count must be 0" in payload["blockers"]
    assert "xlsx_hidden_policy_mismatch_count must be 0" in payload["blockers"]
    assert "xlsx_hidden_policy_version_mismatch_count must be 0" in payload["blockers"]
    assert "xlsx_search_unit_metadata_unmatched_count must be 0" in payload["blockers"]
    assert "embedding_record_missing_count must be 0 for candidate PDF/XLSX rows" in payload["blockers"]


def test_embedding_consistency_fails_on_xlsx_hidden_policy_mismatch():
    payload = embedding_consistency_module.build_consistency_payload(
        snapshot={
            "scoped_summary": {
                "scoped_count": 2,
                "not_embedded_count": 0,
                "index_version_mismatch_count": 0,
                "embedding_record_missing_count": 0,
                "candidate_chunk_missing_count": 0,
                "vector_namespace_mismatch_count": 0,
                "chunk_sha_mismatch_count": 0,
                "hidden_leakage_count": 0,
                "xlsx_hidden_policy_mismatch_count": 1,
                "xlsx_hidden_policy_version_mismatch_count": 1,
                "outside_scope_recent_embedded_count": 0,
            },
        },
        explicit_document_version_ids=["docv_1", "docv_2"],
        derived_document_version_ids=[],
        blockers=[],
        warnings=[],
        expected_document_version_count=2,
        expected_index_version="rag-ingestion-v2-candidate",
        source_file_types=["SPREADSHEET", "PDF"],
        parser_versions=["xlsx-extract-v2-hidden-safe", "pdf-extract-v1", "pdf-extract-v2"],
        allow_unscoped=False,
        run_started_at=None,
    )

    assert payload["status"] == "FAIL"
    assert "xlsx_hidden_policy_mismatch_count must be 0" in payload["blockers"]
    assert "xlsx_hidden_policy_version_mismatch_count must be 0" in payload["blockers"]


def test_embedding_consistency_is_diagnostic_when_full72_scope_is_incomplete():
    payload = embedding_consistency_module.build_consistency_payload(
        snapshot={
            "scoped_summary": {
                "scoped_count": 10,
                "not_embedded_count": 0,
                "index_version_mismatch_count": 0,
                "embedding_record_missing_count": 0,
                "candidate_chunk_missing_count": 0,
                "vector_namespace_mismatch_count": 0,
                "chunk_sha_mismatch_count": 0,
                "hidden_leakage_count": 0,
                "outside_scope_recent_embedded_count": 0,
            },
        },
        explicit_document_version_ids=[],
        derived_document_version_ids=["docv_1", "docv_2"],
        blockers=[],
        warnings=[],
        expected_document_version_count=72,
        expected_index_version="rag-ingestion-v2-candidate",
        source_file_types=["SPREADSHEET", "PDF"],
        parser_versions=["xlsx-extract-v2-hidden-safe", "pdf-extract-v1", "pdf-extract-v2"],
        allow_unscoped=False,
        run_started_at=None,
    )

    assert payload["status"] == "DIAGNOSTIC_ONLY"
    assert payload["scope"]["complete"] is False
    assert "expected_document_version_ids incomplete: expected 72, got 2" in payload["scope"]["missing_contracts"]


def test_embedding_consistency_gold_scope_tracks_rows_and_unique_document_versions(tmp_path):
    gold = tmp_path / "gold.csv"
    gold.write_text(
        "\n".join([
            "query_id,expected_document_version_id",
            "q1,docv_a",
            "q2,docv_a",
            "q3,docv_b",
        ]),
        encoding="utf-8",
    )
    warnings: list[str] = []
    gold_scope = embedding_consistency_module.load_gold_document_version_scope(gold, 3, warnings)
    payload = embedding_consistency_module.build_consistency_payload(
        snapshot={
            "scoped_summary": {
                "scoped_count": 2,
                "not_embedded_count": 0,
                "index_version_mismatch_count": 0,
                "embedding_record_missing_count": 0,
                "candidate_chunk_missing_count": 0,
                "vector_namespace_mismatch_count": 0,
                "chunk_sha_mismatch_count": 0,
                "hidden_leakage_count": 0,
                "outside_scope_recent_embedded_count": 0,
            },
            "missing_expected_document_version_ids": [],
        },
        explicit_document_version_ids=gold_scope["document_version_ids"],
        derived_document_version_ids=[],
        gold_scope=gold_scope,
        document_version_scope_source=["gold_query_file"],
        blockers=[],
        warnings=warnings,
        expected_document_version_count=gold_scope["gold_unique_document_version_count"],
        expected_index_version="rag-ingestion-v2-candidate",
        source_file_types=["SPREADSHEET", "PDF"],
        parser_versions=["xlsx-extract-v2-hidden-safe", "pdf-extract-v1", "pdf-extract-v2"],
        allow_unscoped=False,
        run_started_at=None,
    )

    assert payload["status"] == "PASS"
    assert payload["gold"]["gold_row_count"] == 3
    assert payload["gold"]["gold_unique_document_version_count"] == 2
    assert payload["document_version_ids"] == ["docv_a", "docv_b"]
    assert payload["scope"]["complete"] is True


def test_pdf_batch_db_report_validation_requires_artifacts_metadata_and_bbox():
    clean_report = {
        "source_status": "READY",
        "search_unit_count": 4,
        "page_count_from_location": 2,
        "parsed_pdf_page_count": 2,
        "pdf_page_metadata_count": 2,
        "missing_page_metadata_count": 0,
        "inconsistent_location_page_metadata_count": 0,
        "pdf_parsed_artifact_count": 1,
        "pdf_plaintext_artifact_count": 1,
        "missing_required_metadata_count": 0,
        "invalid_pdf_location_count": 0,
        "missing_pdf_citation_text_count": 0,
        "missing_text_block_bbox_count": 0,
        "parsed_artifact_parser_names": ["pymupdf"],
        "parsed_artifact_parser_versions": ["pdf-extract-v1"],
        "search_unit_parser_names": ["pymupdf"],
        "search_unit_parser_versions": ["pdf-extract-v1"],
    }
    defaults = {
        "min_search_units": 3,
        "min_pages": 1,
        "require_parser_name": "pymupdf",
        "require_parser_version": "pdf-extract-v1",
        "require_bbox_if_text_block": True,
    }

    pdf_batch_module.validate_sample_db_report(clean_report, sample={}, defaults=defaults)

    bad_report = dict(clean_report)
    bad_report["missing_text_block_bbox_count"] = 1
    with pytest.raises(AssertionError, match="missing_text_block_bbox_count"):
        pdf_batch_module.validate_sample_db_report(bad_report, sample={}, defaults=defaults)

    bad_page_report = dict(clean_report)
    bad_page_report["missing_page_metadata_count"] = 1
    with pytest.raises(AssertionError, match="missing_page_metadata_count"):
        pdf_batch_module.validate_sample_db_report(bad_page_report, sample={}, defaults=defaults)


def _write_bootstrap_inputs(tmp_path: Path) -> dict[str, Path]:
    retrieval = tmp_path / "retrieval.json"
    metrics = tmp_path / "metrics.json"
    gold = tmp_path / "gold.csv"
    consistency = tmp_path / "consistency.json"
    scope = tmp_path / "scope.json"
    descriptor = tmp_path / "descriptor.json"
    readiness = tmp_path / "readiness.json"
    index_dir = tmp_path / "faiss"
    index_dir.mkdir()
    (index_dir / "faiss.index").write_bytes(b"fake-faiss-index")
    (index_dir / "build.json").write_text(json.dumps({
        "index_version": "candidate-v2",
        "embedding_model": "BAAI/bge-m3",
        "dimension": 1024,
        "chunk_count": 2,
    }), encoding="utf-8")
    (index_dir / "ingest_manifest.json").write_text(json.dumps({
        "embedding_text_variant": "retrieval_title_section",
        "embedding_text_builder_version": "v4-1",
        "embedding_model": "BAAI/bge-m3",
        "max_seq_length": 1024,
        "chunk_count": 2,
        "document_count": 1,
        "dimension": 1024,
        "index_version": "candidate-v2",
        "embed_text_sha256": "embed-sha",
    }), encoding="utf-8")
    retrieval.write_text(json.dumps({
        "status": "COMPLETED",
        "retrieval_backend": "vector",
        "backend_identity": {
            "backend": "faiss",
            "index_dir": str(index_dir),
            "index_namespace_filter": "candidate-v2",
        },
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "candidate_index_version": "candidate-v2",
        "required_index_version": "candidate-v2",
        "metrics": {
            "Hit@10": 0.8,
            "MRR@10": 0.7,
            "hit_at_10": 0.8,
            "mrr_at_10": 0.7,
            "citation_accuracy": 0.6,
            "citation_location_accuracy": 0.6,
            "xlsx_citation_location_accuracy": 0.8,
            "pdf_citation_location_accuracy": 0.2,
        },
    }), encoding="utf-8")
    metrics.write_text(json.dumps({"metrics": {"Hit@10": 0.8, "MRR@10": 0.7}}), encoding="utf-8")
    gold.write_text(
        "\n".join([
            "query_id,expected_document_version_id",
            "q1,docv_1",
            "q2,docv_1",
        ]),
        encoding="utf-8",
    )
    consistency.write_text(json.dumps({
        "status": "PASS",
        "document_version_ids": ["docv_1"],
    }), encoding="utf-8")
    scope.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    return {
        "retrieval": retrieval,
        "metrics": metrics,
        "gold": gold,
        "consistency": consistency,
        "scope": scope,
        "descriptor": descriptor,
        "readiness": readiness,
        "index_dir": index_dir,
    }


def _clean_gate_metrics(index_version: str) -> dict[str, object]:
    return {
        "parser_success_rate": 0.95,
        "unsupported_file_rate": 0.05,
        "zero_indexable_chunk_count": 0,
        "required_metadata_completeness": 0.98,
        "missing_required_metadata_count": 0,
        "xlsx_citation_location_accuracy": 0.90,
        "pdf_citation_location_accuracy": 0.85,
        "table_detection_accuracy": 0.80,
        "Hit@10": 0.77,
        "MRR@10": 0.67,
        "citation_accuracy": 0.85,
        "parsing_latency_p95": 30.0,
        "indexing_latency_p95": 60.0,
        "fatal_warning_count": 0,
        "hidden_content_leakage_count": 0,
        "retrieval_backend": "vector",
        "retrieval_backend_identity": {
            "backend": "faiss",
            "index_namespace_filter": index_version,
        },
        "promotion_evidence": True,
        "evidence_role": "promotion",
        "embedding_filtered_eval": True,
        "required_embedding_status": "EMBEDDED",
        "required_index_version": index_version,
        "gate_input_missing_count": 0,
        "indexing_filtered_hit_count": 0,
        "candidate_index_mismatch_count": 0,
        "required_index_version_mismatch_count": 0,
        "embedding_status_mismatch_count": 0,
        "eval_dataset_id": "gold_queries_v0",
        "eval_dataset_version": "strict_B_vector_v1",
        "eval_dataset_sha256": "gold-sha",
        "gold_query_row_count": 72,
    }
