from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v6_4_e2e_coverage_and_failure_taxonomy_nonprod"
ROLLBACK_KEY = "v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report"
STATUS = "V6_4_E2E_COVERAGE_AND_FAILURE_TAXONOMY_NONPROD_READY"
EXPECTED_FAMILIES = {"PDF": 100, "TEXT": 100, "XLSX": 100}
PROTECTED_PATHS = (
    "ai/eval/eval_queries",
    "ai/eval/source_registry",
    "ai/eval/indexes",
    "ai/eval/silver",
)
EXPECTED_TAXONOMY_KEYS = {
    "no_candidate",
    "vector_no_candidate",
    "bm25_no_candidate",
    "hybrid_no_candidate",
    "hydration_failed",
    "citation_verification_failed",
    "tool_required",
    "tool_unsupported",
    "context_required",
    "local_llm_disabled",
    "label_unavailable",
    "answer_quality_gate_closed",
    "protected_surface_blocked",
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


def assert_no_exact_keys(value: object, forbidden_keys: set[str]) -> None:
    if isinstance(value, dict):
        assert not (set(value) & forbidden_keys)
        for child in value.values():
            assert_no_exact_keys(child, forbidden_keys)
    elif isinstance(value, list):
        for child in value:
            assert_no_exact_keys(child, forbidden_keys)


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
        return values / float(np.linalg.norm(values))


@pytest.fixture(autouse=True)
def _reset_stub() -> None:
    StubBgeM3Embedder.instances.clear()


@pytest.fixture(scope="module")
def v64_module():
    from ai.eval import rag_v64_e2e_coverage_and_failure_taxonomy_nonprod as v64

    return v64


@pytest.fixture()
def report(v64_module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, object]:
    monkeypatch.setattr(v64_module.v63, "SentenceTransformerEmbedder", StubBgeM3Embedder)
    built = v64_module.build_report(
        root=ROOT,
        generated_at="2026-06-07T00:10:00Z",
        run_artifact_root=tmp_path / "v6_4_runtime",
    )
    v64_module.check_report(built)
    return built


def test_v64_registers_current_and_keeps_v63_as_rollback(report: dict[str, object]) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_eval_registry as registry

    assert registry.resolve_run(RUN_KEY, root=ROOT).logical_key == RUN_KEY
    assert registry.resolve_run("current", root=ROOT).logical_key == RUN_KEY
    assert runner.DEFAULT_RUN_KEY == RUN_KEY
    assert runner.check_run(RUN_KEY)["logical_run_key"] == RUN_KEY
    assert runner.check_run("current")["logical_run_key"] == RUN_KEY
    assert runner.check_run(ROLLBACK_KEY)["logical_run_key"] == ROLLBACK_KEY

    assert report["status"] == STATUS
    assert report["current_resolves_to"] == RUN_KEY
    assert report["current_alias_policy"]["current_moved_from"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["current_moved_to"] == RUN_KEY
    assert report["rollback_key"] == ROLLBACK_KEY


def test_300_row_coverage_family_breakdown_and_candidate_availability(report: dict[str, object]) -> None:
    assert StubBgeM3Embedder.instances
    embedder = StubBgeM3Embedder.instances[0]
    assert embedder.model_name == "BAAI/bge-m3"
    assert sum(len(batch) for batch in embedder.passage_batches) == 300
    assert sum(len(batch) for batch in embedder.query_batches) == 300

    reuse = report["source_v6_3_reuse_summary"]
    coverage = report["candidate_coverage_summary"]
    availability = report["candidate_availability"]

    assert reuse["source_run_key"] == ROLLBACK_KEY
    assert reuse["search_unit_materialization_reused"] is True
    assert reuse["search_view_materialization_reused"] is True
    assert reuse["embedding_backend_reused"] == "BAAI/bge-m3"
    assert reuse["vector_backend_reused"] == "bge_m3_faiss"
    assert reuse["bm25_backend_reused"] == "repo_local_sqlite_bm25"
    assert reuse["hybrid_policy_reused"] == "v6_3_fixed_0_5_vector_0_5_bm25_no_tuning"

    assert coverage["attempted_rows"] == 300
    assert coverage["coverage_adjusted_denominator"] == 300
    assert coverage["computed_only_denominator"] == 0
    assert coverage["retrieval_metric_computed_count"] == 0
    assert coverage["label_available_rows"] == 0
    assert coverage["label_unavailable_exclusion_reason"] == "no_authorized_after_fact_label_available"
    assert coverage["family_breakdown"] == EXPECTED_FAMILIES

    assert set(availability) == {"vector", "bm25", "hybrid"}
    for backend, counters in availability.items():
        assert counters["attempted_rows"] == 300, backend
        assert counters["with_candidates_rows"] + counters["no_candidate_rows"] == 300, backend
        assert counters["hydrated_rows"] == counters["with_candidates_rows"], backend
        assert counters["coverage_adjusted_denominator"] == 300, backend
        assert counters["computed_only_denominator"] == 0, backend
        assert counters["tool_outputs_counted_as_rag_hit"] is False, backend
        assert counters["tool_success_contributed_to_hit_at_k"] is False, backend
        assert counters["tool_success_contributed_to_mrr"] is False, backend
        assert counters["tool_success_contributed_to_ndcg"] is False, backend

    assert report["vector_candidate_availability"] == availability["vector"]
    assert report["bm25_candidate_availability"] == availability["bm25"]
    assert report["hybrid_candidate_availability"] == availability["hybrid"]


def test_failure_taxonomy_and_metric_denominators_stay_fail_closed(report: dict[str, object]) -> None:
    taxonomy = report["failure_taxonomy"]
    availability = report["candidate_availability"]
    metrics = report["metric_results"]

    assert set(taxonomy) == EXPECTED_TAXONOMY_KEYS
    assert taxonomy["vector_no_candidate"] == availability["vector"]["no_candidate_rows"]
    assert taxonomy["bm25_no_candidate"] == availability["bm25"]["no_candidate_rows"]
    assert taxonomy["hybrid_no_candidate"] == availability["hybrid"]["no_candidate_rows"]
    assert taxonomy["no_candidate"] == max(
        availability["vector"]["no_candidate_rows"],
        availability["bm25"]["no_candidate_rows"],
        availability["hybrid"]["no_candidate_rows"],
    )
    assert taxonomy["tool_required"] == 100
    assert taxonomy["context_required"] == 100
    assert taxonomy["local_llm_disabled"] == report["bounded_e2e_render_expansion"]["evidence_only_render_count"]
    assert taxonomy["label_unavailable"] == 300
    assert taxonomy["answer_quality_gate_closed"] == 300
    assert taxonomy["protected_surface_blocked"] == 0

    for metric_name in (
        "vector_retrieval_smoke_metric",
        "bm25_retrieval_smoke_metric",
        "hybrid_retrieval_smoke_metric",
    ):
        metric = metrics[metric_name]
        assert metric["computed_only_denominator"] == 0
        assert metric["coverage_adjusted_denominator"] == 300
        assert metric["retrieval_metric_computed_count"] == 0
        assert metric["coverage_limited_reason"] == "no_authorized_after_fact_label_available"
        assert metric["tool_outputs_counted_as_rag_hit"] is False
        assert metric["tool_success_contributed_to_hit_at_k"] is False
        assert metric["tool_success_contributed_to_mrr"] is False
        assert metric["tool_success_contributed_to_ndcg"] is False


def test_bounded_e2e_render_hydrates_only_source_atom_evidence_bundle(report: dict[str, object]) -> None:
    expansion = report["bounded_e2e_render_expansion"]
    hydration = expansion["hydration_summary"]
    citation = expansion["citation_verification_summary"]
    rows = expansion["sampled_rows"]

    assert expansion["source_e2e_rows_attempted"] == 3
    assert expansion["expanded_rows_attempted"] == 30
    assert expansion["rows_attempted_by_family"] == {"PDF": 10, "TEXT": 10, "XLSX": 10}
    assert expansion["evidence_only_render_count"] == 30
    assert expansion["answer_quality_metric_computed"] is False
    assert expansion["raw_prompt_payload_written"] is False
    assert expansion["raw_response_payload_written"] is False

    assert hydration["hydration_source"] == "SourceAtom/EvidenceBundle"
    assert hydration["hydration_attempted_rows"] == 30
    assert hydration["hydration_success_rows"] == 30
    assert hydration["hydration_fail_closed_rows"] == 0
    assert hydration["evidence_truth_violation_count"] == 0
    assert hydration["raw_source_query_time_parse_count"] == 0
    assert citation["citation_verification_passed_rows"] == 30
    assert citation["citation_verification_failed_rows"] == 0
    assert citation["passed"] is True

    assert len(rows) == 30
    assert {row["source_family"] for row in rows} == {"PDF", "TEXT", "XLSX"}
    for row in rows:
        assert row["answer_mode"] == "evidence_only_answer_render_bounded_diagnostic"
        assert row["retrieved"] is True
        assert row["hydrated"] is True
        assert row["answer_rendered"] is True
        assert row["citation_verified"] is True
        assert row["evidence_ids"]
        assert row["not_answer_quality_metric"] is True
        assert row["not_product_answer"] is True
        assert row["raw_prompt_payload_written"] is False
        assert row["raw_response_payload_written"] is False
        assert "raw_prompt_payload" not in row
        assert "raw_response_payload" not in row


def test_report_leakage_guard_answer_quality_and_protected_surfaces_are_closed(report: dict[str, object]) -> None:
    assert report["diagnostic_only"] is True
    assert report["answer_quality_metric_computed"] is False
    assert report["retrieval_quality_metric_computed"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["official_metric_input_rows_created"] == 0
    assert report["official_metric_input_rows_consumed"] == 0
    for field in REQUIRED_FALSE_FIELDS:
        assert report[field] is False, field

    assert report["agentic_answer_metric"]["answer_quality_metric_computed"] is False
    assert report["agentic_answer_metric"]["scored_answer_rows"] == 0
    assert report["agentic_answer_metric"]["raw_prompt_payload_written"] is False
    assert report["agentic_answer_metric"]["raw_response_payload_written"] is False

    tool_guard = report["tool_to_rag_leakage_guard"]
    assert tool_guard["tool_outputs_counted_as_rag_hit"] is False
    assert tool_guard["tool_success_contributed_to_hit_at_k"] is False
    assert tool_guard["tool_success_contributed_to_mrr"] is False
    assert tool_guard["tool_success_contributed_to_ndcg"] is False
    assert tool_guard["tool_lane_created_retrieval_hit"] is False

    protected = report["protected_surface_check"]
    assert protected["passed"] is True
    assert protected["mutated_paths"] == []
    assert protected["protected_namespaces_touched"] == []
    assert protected["official_denominator_clean"] is True
    assert protected["source_registry_clean"] is True
    assert protected["production_index_namespace_clean"] is True

    assert_no_exact_keys(
        report,
        {
            "raw_prompt_payload",
            "raw_response_payload",
            "raw_llm_response",
            "formula_text",
            "formula_evaluation",
            "direct_normalized_answer_value",
            "expected_answer",
            "supporting_evidence",
            "qrels_positive_ids",
        },
    )


def test_protected_namespace_git_status_is_clean_for_v64() -> None:
    result = subprocess.run(
        ["git", "status", "--short", "--", *PROTECTED_PATHS],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.strip() == ""


def test_single_primary_report_status_docs_and_hash_contract(
    tmp_path: Path,
    v64_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(v64_module.v63, "SentenceTransformerEmbedder", StubBgeM3Embedder)
    built = v64_module.build_report(
        root=ROOT,
        generated_at="2026-06-07T00:10:00Z",
        run_artifact_root=tmp_path / "v6_4_runtime",
    )
    written, hashes = v64_module.write_report_bundle(tmp_path, built)
    v64_module.check_report(written, root=tmp_path)
    v64_module.update_docs(tmp_path, written)
    v64_module.append_status(tmp_path, written, artifact_hashes=hashes)
    v64_module.require_status_report_hash(tmp_path, written)

    run_root = tmp_path / "ai/eval/reports/rag-ingestion/runs" / RUN_KEY
    assert (run_root / "report.json").exists()
    assert set(path.name for path in run_root.iterdir()) == {"report.json"}
    assert written["consolidated_report_policy"]["primary_report_only"] is True
    assert written["consolidated_report_policy"]["large_candidate_text_dump_written"] is False
    assert written["artifact_sha256"]["report_json_sha256"] == hashlib.sha256(
        (run_root / "report.json").read_bytes()
    ).hexdigest()
    assert hashes["report_json_sha256"] == written["artifact_sha256"]["report_json_sha256"]

    status_rows = [
        json.loads(line)
        for line in (tmp_path / "ai/eval/reports/rag-ingestion/status.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert status_rows[-1]["logical_run_key"] == RUN_KEY
    assert status_rows[-1]["current_resolves_to"] == RUN_KEY
    assert status_rows[-1]["rollback_key"] == ROLLBACK_KEY
    assert status_rows[-1]["artifact_sha256"]["report_json_sha256"] == written["artifact_sha256"]["report_json_sha256"]

    for doc_name in ("rag-ingestion-progress.md", "rag-ingestion-measurements.md", "rag-ingestion-triage.md"):
        text = (tmp_path / "docs" / doc_name).read_text(encoding="utf-8")
        assert RUN_KEY in text
        assert f"current moved from `{ROLLBACK_KEY}` to `{RUN_KEY}`" in text
        assert "300-row" in text
        assert "failure taxonomy" in text
        assert "no official/product/promotion/live-readiness claim" in text.lower()


@pytest.mark.parametrize(
    ("patch", "message"),
    (
        ({"candidate_coverage_summary": {"computed_only_denominator": 1}}, "computed-only denominator"),
        ({"bounded_e2e_render_expansion": {"answer_quality_metric_computed": True}}, "answer quality"),
        ({"tool_to_rag_leakage_guard": {"tool_outputs_counted_as_rag_hit": True}}, "tool output"),
        ({"protected_surface_check": {"mutated_paths": ["ai/eval/eval_queries/x.json"]}}, "protected surface"),
    ),
)
def test_check_report_rejects_boundary_drift(
    report: dict[str, object],
    v64_module,
    patch: dict[str, object],
    message: str,
) -> None:
    poisoned = json.loads(json.dumps(report))
    for key, value in patch.items():
        poisoned[key] = dict(poisoned.get(key, {}), **value)

    with pytest.raises(ValueError, match=message):
        v64_module.check_report(poisoned)
