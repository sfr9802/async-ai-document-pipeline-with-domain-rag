from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report"
V7_0_RUN_KEY = "v7_0_e2e_eval_architecture_closeout_nonprod"
V6_4_RUN_KEY = "v6_4_e2e_coverage_and_failure_taxonomy_nonprod"
ROLLBACK_KEY = "v6_2_source_derived_materialization_scaleout_and_denominator_reality_check"
STATUS = "V6_3_E2E_BGE_M3_FAISS_AGENTIC_RAG_SMOKE_SINGLE_REPORT_NONPROD_READY"

FORBIDDEN_SEPARATE_REPORT_FILES = {
    "metric_results.json",
    "metric_tiers.json",
    "leakage_probe_summary.json",
    "denominator_manifest.jsonl",
    "row_eligibility_ledger.jsonl",
    "exclusion_ledger.jsonl",
    "candidate_text_quality_audit.json",
    "materialization_coverage.json",
    "retrieval_metric_coverage.json",
    "agentic_loop_trace.jsonl",
    "structured_tool_diagnostics.jsonl",
    "true_rag_candidate_diagnostics.jsonl",
}

REQUIRED_FALSE_FIELDS = {
    "official_metric",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_routing_enabled",
    "production_db_mutated",
    "production_index_mutation",
    "production_namespace_mutated",
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "relevance_label_mutation",
    "answerability_label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "source_registry_mutated",
    "training_dataset_created",
    "fine_tuning_dataset_export_created",
    "fine_tuning_started",
    "fine_tuning_executed",
    "ft_a_execution",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
}


class StubBgeM3Embedder:
    instances: list["StubBgeM3Embedder"] = []

    def __init__(self, model_name: str, **kwargs: object) -> None:
        self.model_name = model_name
        self.max_seq_length = kwargs.get("max_seq_length")
        self.passage_batches: list[list[str]] = []
        self.query_batches: list[list[str]] = []
        self._dimension = 16
        StubBgeM3Embedder.instances.append(self)

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        self.passage_batches.append(list(texts))
        return np.vstack([self._vector(text) for text in texts]).astype(np.float32)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        self.query_batches.append(list(texts))
        return np.vstack([self._vector(text) for text in texts]).astype(np.float32)

    def _vector(self, text: str) -> np.ndarray:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = np.array([(digest[i] + 1) / 256.0 for i in range(self._dimension)], dtype=np.float32)
        norm = float(np.linalg.norm(values))
        return values / norm


@pytest.fixture(autouse=True)
def _reset_stub() -> None:
    StubBgeM3Embedder.instances.clear()


@pytest.fixture(scope="module")
def v63_module():
    from ai.eval import rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report as v63

    return v63


@pytest.fixture()
def report(v63_module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, object]:
    monkeypatch.setattr(v63_module, "SentenceTransformerEmbedder", StubBgeM3Embedder)
    built = v63_module.build_report(
        root=ROOT,
        generated_at="2026-06-06T00:00:00Z",
        run_artifact_root=tmp_path / "v6_3_run",
    )
    v63_module.check_report(built)
    return built


def test_v63_registers_current_and_keeps_v62_rollback(report: dict[str, object]) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_eval_registry as registry

    assert registry.resolve_run(RUN_KEY, root=ROOT).logical_key == RUN_KEY
    assert registry.resolve_run("current", root=ROOT).logical_key in {RUN_KEY, V7_0_RUN_KEY, V6_4_RUN_KEY}
    assert runner.DEFAULT_RUN_KEY in {RUN_KEY, V7_0_RUN_KEY, V6_4_RUN_KEY}
    assert report["status"] == STATUS
    assert report["current_resolves_to"] == RUN_KEY
    assert report["current_alias_policy"]["current_moved_from"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["current_moved_to"] == RUN_KEY
    assert report["rollback_key"] == ROLLBACK_KEY
    assert runner.check_run(RUN_KEY)["logical_run_key"] == RUN_KEY
    assert runner.check_run("current")["logical_run_key"] in {RUN_KEY, V7_0_RUN_KEY, V6_4_RUN_KEY}
    assert runner.check_run(ROLLBACK_KEY)["logical_run_key"] == ROLLBACK_KEY


def test_bge_m3_faiss_vector_retrieval_and_hydration_are_real_and_separate(report: dict[str, object]) -> None:
    assert StubBgeM3Embedder.instances
    embedder = StubBgeM3Embedder.instances[0]
    assert embedder.model_name == "BAAI/bge-m3"
    assert embedder.passage_batches
    assert embedder.query_batches

    bge = report["bge_m3_status"]
    faiss_status = report["faiss_status"]
    materialization = report["materialization_summary"]
    hydration = report["hydration_summary"]
    metrics = report["metric_results"]

    assert bge["embedding_model_name"] == "bge-m3"
    assert bge["embedding_model_identifier"] == "BAAI/bge-m3"
    assert bge["model_ready"] is True
    assert bge["embedding_dim"] == 16
    assert bge["embedding_count"] == materialization["source_derived_search_view_count"]
    assert bge["normalize_embeddings"] is True
    assert bge["fake_random_or_zero_embeddings_rejected"] is True

    assert faiss_status["faiss_available"] is True
    assert faiss_status["index_build_invoked"] is True
    assert faiss_status["index_query_invoked"] is True
    assert faiss_status["faiss_index_type"] == "IndexFlatIP"
    assert faiss_status["vector_count"] == bge["embedding_count"]
    assert faiss_status["id_map_count"] == faiss_status["vector_count"]
    assert faiss_status["namespace"].startswith("v6_3_true_rag_nonprod_")
    assert faiss_status["production_index_mutation"] is False
    assert faiss_status["protected_namespaces_touched"] == []

    assert materialization["source_family_counts"] == {"PDF": 100, "TEXT": 100, "XLSX": 100}
    assert materialization["query_time_raw_pdf_xlsx_text_parse_in_true_rag"] is False
    assert hydration["hydration_attempted_rows"] >= 3
    assert hydration["hydration_success_rows"] >= 3
    assert hydration["evidence_bundle_count"] >= 3
    assert hydration["evidence_truth_violation_count"] == 0
    assert hydration["raw_source_query_time_parse_count"] == 0

    assert set(metrics) == {
        "vector_retrieval_smoke_metric",
        "bm25_retrieval_smoke_metric",
        "hybrid_retrieval_smoke_metric",
        "structured_tool_metric",
        "e2e_pipeline_smoke_metric",
        "agentic_answer_metric",
        "denominator_reality_metric",
    }
    assert metrics["vector_retrieval_smoke_metric"]["backend"] == "bge_m3_faiss"
    assert metrics["bm25_retrieval_smoke_metric"]["backend"] == "repo_local_sqlite_bm25"
    assert metrics["hybrid_retrieval_smoke_metric"]["fixed_weight_policy"] == "v6_3_fixed_0_5_vector_0_5_bm25_no_tuning"
    assert metrics["structured_tool_metric"]["tool_outputs_counted_as_rag_hit"] is False


def test_e2e_answer_render_citation_and_agentic_guardrails(report: dict[str, object]) -> None:
    e2e = report["e2e_pipeline_smoke_metric"]
    answer = report["agentic_answer_metric"]
    tool = report["structured_tool_metric"]
    trace = report["agentic_loop_trace_summary"]

    assert e2e["rows_attempted_by_family"] == {"PDF": 1, "TEXT": 1, "XLSX": 1}
    assert e2e["e2e_rows_attempted"] >= 3
    assert e2e["e2e_rows_retrieved"] >= 3
    assert e2e["e2e_rows_hydrated"] >= 3
    assert e2e["e2e_rows_answer_rendered"] >= 3
    assert e2e["e2e_rows_citation_verified"] >= 3
    assert e2e["citation_verification_passed"] is True
    assert e2e["answer_quality_metric_computed"] is False
    assert e2e["not_product_answer"] is True

    assert tool["tool_required_rows"] >= 1
    assert tool["tool_attempted_rows"] == tool["tool_required_rows"]
    assert tool["tool_success_rows"] >= 1
    assert tool["tool_success_contributed_to_hit_at_k"] is False
    assert tool["tool_success_contributed_to_mrr"] is False
    assert tool["tool_success_contributed_to_ndcg"] is False

    assert answer["evidence_only_render_count"] >= 3
    assert answer["local_llm_invoked_count"] == 0
    assert answer["answer_quality_metric_computed"] is False
    assert answer["raw_prompt_payload_written"] is False
    assert answer["raw_response_payload_written"] is False

    assert {
        "classify",
        "true_rag_retrieve",
        "hydrate",
        "tool_plan",
        "tool_execute",
        "synthesize_or_render",
        "citation_verify",
        "retry_or_finalize",
    } <= set(trace["agentic_nodes_executed"])
    assert trace["max_retry_count"] <= 2
    assert len(trace["sampled_agentic_trace_rows"]) <= 10


def test_single_report_policy_and_artifact_hashes(tmp_path: Path, v63_module, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(v63_module, "SentenceTransformerEmbedder", StubBgeM3Embedder)
    for doc in (
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ):
        path = tmp_path / doc
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Ledger\n\nLast updated: 2026-06-06 KST.\n", encoding="utf-8")

    built = v63_module.build_report(
        root=ROOT,
        generated_at="2026-06-06T00:00:00Z",
        run_artifact_root=tmp_path / "ai/eval/reports/rag-ingestion/runs" / RUN_KEY,
    )
    written, hashes = v63_module.write_report_bundle(tmp_path, built)
    v63_module.check_report(written, root=tmp_path)
    v63_module.update_docs(tmp_path, written)
    v63_module.append_status(tmp_path, written, artifact_hashes=hashes)
    v63_module.require_status_report_hash(tmp_path, written)

    run_root = tmp_path / "ai/eval/reports/rag-ingestion/runs" / RUN_KEY
    assert (run_root / "report.json").exists()
    for name in FORBIDDEN_SEPARATE_REPORT_FILES:
        assert not (run_root / name).exists(), name
    assert (run_root / "true_rag_faiss.index").exists()
    assert (run_root / "faiss_id_map.json").exists()
    assert written["consolidated_report_policy"]["primary_report_only"] is True
    assert written["consolidated_report_policy"]["large_candidate_text_dump_written"] is False
    assert written["artifact_sha256"]["report_json_sha256"] == hashlib.sha256((run_root / "report.json").read_bytes()).hexdigest()
    assert "true_rag_faiss_index_sha256" in written["artifact_sha256"]
    assert "faiss_id_map_json_sha256" in written["artifact_sha256"]

    status_rows = [
        json.loads(line)
        for line in (tmp_path / "ai/eval/reports/rag-ingestion/status.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert status_rows[-1]["current_resolves_to"] == RUN_KEY
    assert status_rows[-1]["rollback_key"] == ROLLBACK_KEY
    assert status_rows[-1]["artifact_sha256"]["report_json_sha256"] == written["artifact_sha256"]["report_json_sha256"]
    for doc in (
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ):
        text = (tmp_path / doc).read_text(encoding="utf-8")
        assert "diagnostic-only" in text
        assert "bge-m3" in text
        assert "FAISS" in text
        assert f"current moved from `{ROLLBACK_KEY}` to `{RUN_KEY}`" in text
        assert f"rollback key is `{ROLLBACK_KEY}`" in text
        assert "one primary report.json" in text
        assert "no official/product/promotion/live-readiness claim" in text


def test_required_report_fields_leakage_and_protected_surfaces_are_closed(report: dict[str, object]) -> None:
    assert report["run_id"] == RUN_KEY
    assert report["canonical_long_run_id"] == RUN_KEY
    assert report["schema_version"].endswith("_report_v1")
    assert report["diagnostic_only"] is True
    assert report["current_resolves_to"] == RUN_KEY
    assert report["rollback_key"] == ROLLBACK_KEY
    assert report["official_metric_input_rows"] == 0
    assert report["official_metric_input_rows_created"] == 0
    assert report["official_metric_input_rows_consumed"] == 0
    for field in REQUIRED_FALSE_FIELDS:
        assert report[field] is False, field

    leakage = report["leakage_probe_summary"]
    assert leakage["passed"] is True
    assert leakage["forbidden_input_forwarded_count"] == 0
    assert leakage["forbidden_input_forwarded_fields"] == []
    assert leakage["faiss_candidate_ids_changed_by_poisoned_fields"] is False
    assert leakage["faiss_candidate_scores_changed_by_poisoned_fields"] is False
    assert leakage["bm25_candidate_ids_changed_by_poisoned_fields"] is False
    assert leakage["hybrid_rank_changed_by_poisoned_fields"] is False
    assert leakage["answer_render_inputs_changed_by_poisoned_fields"] is False
    assert leakage["status_hash_changed_by_forbidden_fields"] is False

    protected = report["protected_surface_check"]
    assert protected["passed"] is True
    assert protected["mutated_paths"] == []
    assert protected["gold_qrels_expected_supporting_relevance_answerability_clean"] is True
    assert protected["official_denominator_clean"] is True
    assert protected["production_index_namespace_clean"] is True

    assert len(report["sampled_rows"]) <= 10
    for row in report["sampled_rows"]:
        assert len(row["sampled_candidates"]) <= 5
        assert "candidate_text" not in row
        for candidate in row["sampled_candidates"]:
            assert "candidate_text" not in candidate
            assert len(candidate.get("text_preview", "")) <= 160


def test_embedding_matrix_rejects_fake_zero_and_random_vectors(v63_module) -> None:
    zeros = np.zeros((2, 4), dtype=np.float32)
    with pytest.raises(ValueError, match="zero"):
        v63_module.validate_embedding_matrix(zeros, expected_count=2, embedding_model_identifier="BAAI/bge-m3")

    randomish = np.eye(2, 4, dtype=np.float32)
    with pytest.raises(ValueError, match="fake|random|one-hot"):
        v63_module.validate_embedding_matrix(randomish, expected_count=2, embedding_model_identifier="BAAI/bge-m3")

    wrong_model = np.ones((2, 4), dtype=np.float32)
    with pytest.raises(ValueError, match="bge-m3"):
        v63_module.validate_embedding_matrix(wrong_model, expected_count=2, embedding_model_identifier="hashing-embedder")
