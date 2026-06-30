from __future__ import annotations

import csv
import hashlib
import json
import inspect
import os
import sqlite3
import subprocess
import sys
import types
from pathlib import Path

import pytest

from ai.eval import actual_rag_eval
from ai.eval.actual_rag_eval import (
    DatasetSchemaError,
    ExpectedEvidenceResolver,
    EvidenceResolutionConfig,
    FakeDeterministicEmbeddingProvider,
    FakeVectorAdapter,
    RepoCurrentBm25Adapter,
    SourceNativeCorpusLoader,
    SourceNativeHybridAdapter,
    append_actual_rag_status_event,
    build_backend_comparison_metrics,
    build_parser,
    build_corpus_coverage_audit_report,
    build_legacy_real_rag_quality_gate_report,
    build_evidence_gate_summary,
    build_source_native_legacy_cleanup_report,
    apply_selected_evidence_composer_to_outputs,
    apply_evidence_gate_to_outputs,
    build_source_native_bge_m3_index_artifact,
    build_run_comparison,
    answer_correct,
    abstains,
    heuristic_judge_answer,
    load_eval_dataset,
    make_actual_rag_run_id,
    normalize_answer_text,
    _public_report_row,
    _report_path_value,
    resolve_quality_gate_baseline_report,
    run_eval_from_paths,
    score_rag_eval_items,
    select_composer_evidence,
    validate_evidence_package_for_gate,
    validate_actual_rag_guardrails,
    write_source_native_legacy_cleanup_report,
    write_latest_pointers,
)
from ai.eval.weaviate_source_atom import (
    BgeM3EmbeddingBuilder,
    WEAVIATE_SOURCE_ATOM_REQUIRED_PROPERTIES,
    WEAVIATE_SOURCE_ATOM_V2_EXTRA_PROPERTIES,
    FakeWeaviateSourceAtomClient,
    WeaviateSourceAtomAdapter,
    WeaviateSourceAtomClient,
    WeaviateSourceAtomConfig,
    WeaviateSourceAtomIndexer,
    WeaviateUnavailableError,
    _write_json_atomic,
    build_default_weaviate_adapter,
    build_weaviate_source_atom_schema,
    derive_weaviate_route_taxonomy,
    plan_weaviate_query_variants,
    plan_weaviate_retrieval_route,
    source_atom_record_from_mapping,
)
import ai.scripts.rag_weaviate_source_atom_index as weaviate_index_script
from ai.scripts.rag_weaviate_source_atom_index import build_parser as build_weaviate_index_parser

from ai.tests.actual_rag_eval_helpers import (
    FakeBgeM3EmbeddingProvider,
    FakeWeaviateBgeM3EmbeddingProvider,
    output_file_names,
    weaviate_source_atom_record,
    write_jsonl,
)

def test_weaviate_route_selected_collapses_same_doc_duplicates_and_fetches_bounded_neighbors_by_id(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_route_selected_neighbors"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "2020년 11월 sheet row amount 승인 금액은?",
                "answerability": "unknown",
                "expected_evidence": [{"text": "XLSX approved amount cell is 15446522."}],
            }
        ],
    )
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    objects = [
        {
            **weaviate_source_atom_record(1, text="XLSX approved amount row summary."),
            "source_family": "XLSX",
            "doc_id": "workbook-1",
            "chunk_id": "table-row-1",
            "source_atom_id": "srcatom-table-row-1",
            "granularity": "table_row",
            "retrieval_route": "xlsx_table",
            "text_sha256": "sha-row-1",
            "sheet": "Approvals",
            "cell_range": "A2:D2",
            "row_index_1based": "2",
        },
        {
            **weaviate_source_atom_record(2, text="XLSX approved amount row duplicate."),
            "source_family": "XLSX",
            "doc_id": "workbook-1",
            "chunk_id": "table-row-1b",
            "source_atom_id": "srcatom-table-row-1b",
            "granularity": "table_row",
            "retrieval_route": "xlsx_table",
            "text_sha256": "sha-row-1b",
            "sheet": "Approvals",
            "cell_range": "A2:D2",
            "row_index_1based": "2",
        },
        {
            **weaviate_source_atom_record(3, text="XLSX approved amount cell is 15446522."),
            "source_family": "XLSX",
            "doc_id": "workbook-1",
            "chunk_id": "cell-B2",
            "source_atom_id": "srcatom-cell-b2",
            "granularity": "cell",
            "retrieval_route": "xlsx_cell_trace",
            "text_sha256": "sha-cell-b2",
            "vectorized_semantic_content": "false",
            "sheet": "Approvals",
            "cell_range": "A2:D2",
            "cell": "B2",
            "row_index_1based": "2",
        },
    ]
    client = FakeWeaviateSourceAtomClient(objects=objects)
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="route_selected",
        route_filter_fields_available={"source_family": True, "granularity": True, "retrieval_route": True},
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=3,
        run_id="weaviate_route_selected_neighbors",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    contexts = report["items"][0]["retrieved_contexts"]

    assert [context["source_atom_id"] for context in contexts] == ["srcatom-table-row-1", "srcatom-cell-b2"]
    assert contexts[1]["retrieval_backend"] == "weaviate_neighbor_by_id"
    assert contexts[1]["neighbor_expansion_source_atom_id"] == "srcatom-table-row-1"
    assert report["weaviate_post_processing"]["duplicate_collapse_enabled"] is True
    assert report["weaviate_post_processing"]["same_doc_duplicate_collapse_removed_count"] == 1
    assert report["weaviate_post_processing"]["neighbor_expansion_query_count"] == 1
    assert report["weaviate_post_processing"]["neighbor_expansion_candidate_generation"] == "weaviate_id_only_no_local_corpus_scan"
    neighbor_queries = [query for query in client.query_log if query["mode"] == "neighbor_by_id"]
    assert len(neighbor_queries) == 1
    assert neighbor_queries[0]["filters"]["source_atom_id"] == "srcatom-table-row-1"
    assert neighbor_queries[0]["filters"]["neighbor_granularity"] == "cell"


def test_weaviate_route_selected_reports_base_filter_not_route_filter_when_route_fields_unavailable(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_route_selected_base_only"
    write_jsonl(dataset, [{"id": "q1", "query": "2020년 11월 sheet cell row amount 승인 금액은?", "answerability": "unknown"}])
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    client = FakeWeaviateSourceAtomClient(
        objects=[
            {
                **weaviate_source_atom_record(1, text="TEXT Project Orion launch is scheduled for April 2026."),
                "granularity": "paragraph",
                "retrieval_route": "text_general",
            },
            {
                **weaviate_source_atom_record(2, text="XLSX approved amount cell is 15446522."),
                "source_family": "XLSX",
                "granularity": "table_row",
                "retrieval_route": "xlsx_table",
            },
        ]
    )
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="route_selected",
        route_filter_fields_available={"source_family": False, "granularity": False, "retrieval_route": False},
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=5,
        run_id="weaviate_route_selected_base_only",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert report["weaviate_filter_sent"] is False
    assert report["weaviate_filter_policy"]["base_filter_sent"] is True
    assert report["weaviate_filter_policy"]["route_filter_sent"] is False
    assert report["weaviate_filter_policy"]["weaviate_filter_sent"] is False
    assert report["weaviate_filter_policy"]["schema_index_v2_rebuild_required"] is True


def test_weaviate_route_ab_mode_writes_explicit_comparison_artifacts_only_when_requested(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_route_ab"
    write_jsonl(
        dataset,
        [
            {
                "id": "text_q1",
                "query": "Project Orion 애니 April 2026",
                "answerability": "unknown",
                "expected_evidence": [{"text": "Project Orion launch is scheduled for April 2026."}],
            },
            {
                "id": "xlsx_q1",
                "query": "2020년 11월 sheet cell row amount 승인 금액은?",
                "answerability": "unknown",
                "expected_evidence": [{"text": "XLSX approved amount cell is 15446522."}],
            },
        ],
    )
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "WEAVIATE_INDEX_MANIFEST_PATH": str(tmp_path / "weaviate_source_atom_v2_manifest.json"),
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    Path(config.index_manifest_path).write_text(
        json.dumps(
            {
                "valid": True,
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "index_object_count": 3,
                "indexed_count": 3,
                "vectorized_object_count": 2,
                "metadata_only_object_count": 1,
                "vectorized_object_ratio": 0.666667,
                "vectorized_by_granularity": {"paragraph": 1, "table_row": 1},
                "metadata_only_by_granularity": {"cell": 1},
                "metadata_only_by_source_family": {"XLSX": 1},
                "route_taxonomy_available": True,
                "route_taxonomy_filterable_fields": [
                    "source_family",
                    "granularity",
                    "retrieval_route",
                    "vectorized_semantic_content",
                ],
                "schema_index_v2_rebuild_required_for_metadata_only_policy": False,
                "vectorization_policy": {
                    "current_index_vectorizes_all_source_atoms": False,
                    "index_time_metadata_only_supported": True,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    objects = [
        {
            **weaviate_source_atom_record(1, text="Project Orion launch is scheduled for April 2026."),
            "granularity": "paragraph",
            "retrieval_route": "text_general",
        },
        {
            **weaviate_source_atom_record(2, text="PDF Project Orion table noise."),
            "source_family": "PDF",
            "granularity": "table_row",
            "retrieval_route": "pdf_table",
            "text_sha256": "sha-index-1",
        },
        {
            **weaviate_source_atom_record(3, text="XLSX approved amount cell is 15446522."),
            "source_family": "XLSX",
            "granularity": "table_row",
            "retrieval_route": "xlsx_table",
        },
    ]

    def lane_factory(route_mode: str) -> WeaviateSourceAtomAdapter:
        return WeaviateSourceAtomAdapter(
            config=config,
            client=FakeWeaviateSourceAtomClient(objects=[dict(obj) for obj in objects]),
            embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
            requested_backend="weaviate-hybrid",
            retrieval_route_mode=route_mode,
            route_filter_fields_available={"source_family": True, "granularity": True, "retrieval_route": True},
        )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=3,
        run_id="weaviate_route_ab",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=lane_factory("route_selected"),
        weaviate_route_ab_mode="text,mixed,routed",
        weaviate_route_ab_lane_factory=lane_factory,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    ab_report_path = output_dir / "route_selected_hybrid_evidence_store_ab_report.json"
    ab_items_path = output_dir / "route_selected_hybrid_evidence_store_ab_items.jsonl"
    ab_report = json.loads(ab_report_path.read_text(encoding="utf-8"))
    ab_rows = [json.loads(line) for line in ab_items_path.read_text(encoding="utf-8").splitlines()]

    assert output_file_names(output_dir) == [
        "report.json",
        "route_selected_hybrid_evidence_store_ab_items.jsonl",
        "route_selected_hybrid_evidence_store_ab_report.json",
    ]
    assert report["artifact_contract"]["route_ab_sidecar_exception"] is True
    assert report["artifact_paths"]["route_selected_hybrid_evidence_store_ab_report_json"] == ab_report_path.as_posix()
    assert report["promotion_decision"] == ab_report["recommendation"]
    assert report["promotion_blockers"] == ab_report["promotion_blockers"]
    assert report["weaviate_route_ab_report_path"] == ab_report_path.as_posix()
    assert report["next_recommended_goal"] == "selected_evidence_answer_composer_citation_formatter_nonprod"
    assert set(ab_report["lanes"]) == {
        "lane_a_full_index",
        "lane_b_text_only",
        "lane_c_mixed_pool",
        "lane_d_route_selected",
    }
    assert ab_report["lanes"]["lane_a_full_index"]["active_retrieval_service_boundary"] == "weaviate"
    assert ab_report["lanes"]["lane_a_full_index"]["weaviate_filter_policy"]["route_mode"] == "full_index"
    assert ab_report["lanes"]["lane_a_full_index"]["weaviate_filter_policy"]["route_filter_sent"] is False
    assert ab_report["lanes"]["lane_b_text_only"]["weaviate_filter_policy"]["source_family_filter_sent"] is True
    assert ab_report["lanes"]["lane_c_mixed_pool"]["mixed_pool_diagnostic_only"] is True
    assert ab_report["lanes"]["lane_d_route_selected"]["route_planner_version"] == "weaviate_route_planner_v1"
    assert ab_report["lanes"]["lane_d_route_selected"]["schema_version_source_atom"] == "weaviate_source_atom_v2"
    assert ab_report["lanes"]["lane_d_route_selected"]["metadata_only_object_count"] == 1
    assert ab_report["lanes"]["lane_d_route_selected"]["metadata_only_by_granularity"] == {"cell": 1}
    assert ab_report["lanes"]["lane_d_route_selected"]["route_filter_sent"] is True
    assert ab_report["lanes"]["lane_d_route_selected"]["retrieval_route_filter_sent"] is True
    assert ab_report["lanes"]["lane_d_route_selected"]["weaviate_post_processing"]["duplicate_collapse_enabled"] is True
    assert ab_report["vectorization_policy"]["route_selected_metadata_only_policy_proven"] is True
    assert ab_report["route_selected_recovery_result"]["all_route_filters_sent"] is True
    assert ab_report["lanes"]["lane_c_mixed_pool"]["duplicate_result_count"] > 0
    assert ab_report["lanes"]["lane_c_mixed_pool"]["duplicate_result_rate"] > 0
    assert ab_report["lanes"]["lane_c_mixed_pool"]["same_doc_duplicate_count"] > 0
    assert ab_report["lanes"]["lane_c_mixed_pool"]["mixed_pool_pollution_count"] > 0
    assert ab_report["lanes"]["lane_c_mixed_pool"]["wrong_source_family_count"] > 0
    assert "wrong_granularity_count" in ab_report["lanes"]["lane_c_mixed_pool"]
    assert ab_report["guardrail_status"]["valid"] is True
    for lane in ab_report["lanes"].values():
        guardrails = lane["guardrail_status"]
        assert guardrails["valid"] is True
        assert guardrails["violations"] == []
        assert guardrails["active_retrieval_service_boundary"] == "weaviate"
        assert guardrails["external_vector_db_invoked"] is True
        assert guardrails["python_local_corpus_scan_used_for_candidate_generation"] is False
        assert guardrails["source_native_layered_retrieval_used_for_candidate_generation"] is False
        assert guardrails["diagnostic_hash_vector_used"] is False
        assert guardrails["faiss_used_for_active_retrieval"] is False
        assert guardrails["searchunit_searchview_used_as_candidate_surface"] is False
    assert ab_report["datasets"]["gold_mutation"] is False
    assert ab_report["recommendation"] in {
        "keep_current_weaviate_full_index",
        "promote_route_selected_nonprod_default",
        "rebuild_schema_v2_required",
        "defer_due_to_latency",
        "defer_due_to_pollution",
        "invalid_due_to_guardrail_violation",
    }
    assert len(ab_rows) == 8
    assert all("raw_prompt_payload" not in row for row in ab_rows)
    assert all("raw_response_payload" not in row for row in ab_rows)


def test_weaviate_route_ab_sidecar_includes_mixed_route_diagnostic_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("ai.eval.actual_rag_eval.ROOT", tmp_path)
    mixed_path = tmp_path / "reports" / "rag_eval" / "rag-ingestion" / "runs" / "v5_5" / "official_metric_input.jsonl"
    mixed_path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(
        mixed_path,
        [
            {
                "question_ko": "2020년 11월 sheet row amount 승인 금액은?",
                "supporting_evidence_note": "XLSX approved amount cell is 15446522.",
                "track": "xlsx_business_structured",
            }
        ],
    )
    dataset = tmp_path / "gold_queries_text_namu_v2_1_question_gold_v2.csv"
    dataset.write_text("id,query,answerability\ntext_q1,Project Orion April 2026,unknown\n", encoding="utf-8")
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_route_ab_mixed_sidecar"
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "WEAVIATE_INDEX_MANIFEST_PATH": str(tmp_path / "weaviate_source_atom_v2_manifest.json"),
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    Path(config.index_manifest_path).write_text(
        json.dumps(
            {
                "valid": True,
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "index_object_count": 2,
                "indexed_count": 2,
                "vectorized_object_count": 2,
                "metadata_only_object_count": 0,
                "vectorized_by_granularity": {"paragraph": 1, "table_row": 1},
                "route_taxonomy_available": True,
                "route_taxonomy_filterable_fields": ["source_family", "granularity", "retrieval_route"],
                "schema_index_v2_rebuild_required_for_metadata_only_policy": False,
                "vectorization_policy": {
                    "current_index_vectorizes_all_source_atoms": False,
                    "index_time_metadata_only_supported": True,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    objects = [
        {
            **weaviate_source_atom_record(1, text="Project Orion launch is scheduled for April 2026."),
            "granularity": "paragraph",
            "retrieval_route": "text_general",
        },
        {
            **weaviate_source_atom_record(2, text="XLSX approved amount cell is 15446522."),
            "source_family": "XLSX",
            "granularity": "table_row",
            "retrieval_route": "xlsx_table",
        },
    ]

    def lane_factory(route_mode: str) -> WeaviateSourceAtomAdapter:
        return WeaviateSourceAtomAdapter(
            config=config,
            client=FakeWeaviateSourceAtomClient(objects=[dict(obj) for obj in objects]),
            embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
            requested_backend="weaviate-hybrid",
            retrieval_route_mode=route_mode,
            route_filter_fields_available={"source_family": True, "granularity": True, "retrieval_route": True},
        )

    run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=3,
        run_id="weaviate_route_ab_mixed_sidecar",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=lane_factory("full_index"),
        weaviate_route_ab_mode="mixed,routed",
        weaviate_route_ab_lane_factory=lane_factory,
    )

    ab_report = json.loads((output_dir / "route_selected_hybrid_evidence_store_ab_report.json").read_text(encoding="utf-8"))
    ab_rows = [
        json.loads(line)
        for line in (output_dir / "route_selected_hybrid_evidence_store_ab_items.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert ab_report["mixed_route_dataset_diagnostic"]["executed"] is True
    assert {
        (row["dataset_role"], row["lane_id"])
        for row in ab_rows
        if row["dataset_role"] == "mixed_route_diagnostic"
    } == {
        ("mixed_route_diagnostic", "lane_c_mixed_pool"),
        ("mixed_route_diagnostic", "lane_d_route_selected"),
    }
    assert all("raw_prompt_payload" not in row for row in ab_rows)
    assert all("raw_response_payload" not in row for row in ab_rows)


def test_weaviate_route_ab_report_counts_text_route_degradation(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_route_ab_degradation"
    write_jsonl(
        dataset,
        [
            {
                "id": "text_q1",
                "query": "Project Orion 애니 April 2026",
                "answerability": "unknown",
                "expected_evidence": [{"text": "Project Orion launch is scheduled for April 2026."}],
            }
        ],
    )
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )

    def lane_factory(route_mode: str) -> WeaviateSourceAtomAdapter:
        text = (
            "Budget workbook approval amount is 15446522."
            if route_mode == "route_selected"
            else "Project Orion launch is scheduled for April 2026."
        )
        return WeaviateSourceAtomAdapter(
            config=config,
            client=FakeWeaviateSourceAtomClient(
                objects=[
                    {
                        **weaviate_source_atom_record(1, text=text),
                        "granularity": "paragraph",
                        "retrieval_route": "text_general",
                    }
                ]
            ),
            embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
            requested_backend="weaviate-hybrid",
            retrieval_route_mode=route_mode,
            route_filter_fields_available={"source_family": True, "granularity": True},
        )

    run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=10,
        run_id="weaviate_route_ab_degradation",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=lane_factory("full_index"),
        weaviate_route_ab_mode="text,routed",
        weaviate_route_ab_lane_factory=lane_factory,
    )

    ab_report = json.loads((output_dir / "route_selected_hybrid_evidence_store_ab_report.json").read_text(encoding="utf-8"))
    assert ab_report["text_degradation_result"]["text_route_degradation_count"] == 1
    assert ab_report["text_degradation_result"]["text_route_degradation_ok"] is False
    assert ab_report["lanes"]["lane_d_route_selected"]["text_route_degradation_count"] == 1
    assert ab_report["recommendation"] != "promote_route_selected_nonprod_default"


def test_weaviate_route_ab_mixed_diagnostic_failure_invalidates_report(tmp_path: Path) -> None:
    dataset = tmp_path / "gold_queries_text_namu_v2_1_question_gold_v2.csv"
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_route_ab_mixed_diag_failure"
    dataset.write_text(
        "id,query,answerability,expected_evidence\n"
        "text_q1,Project Orion 애니 April 2026,unknown,\"[{\"\"text\"\":\"\"Project Orion launch is scheduled for April 2026.\"\"}]\"\n",
        encoding="utf-8",
    )
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    call_counts: dict[str, int] = {}

    def lane_factory(route_mode: str) -> WeaviateSourceAtomAdapter:
        call_counts[route_mode] = call_counts.get(route_mode, 0) + 1
        if route_mode == "mixed_pool" and call_counts[route_mode] > 1:
            raise WeaviateUnavailableError("weaviate_unavailable: forced mixed diagnostic failure")
        return WeaviateSourceAtomAdapter(
            config=config,
            client=FakeWeaviateSourceAtomClient(
                objects=[
                    {
                        **weaviate_source_atom_record(
                            1,
                            text="Project Orion launch is scheduled for April 2026.",
                        ),
                        "granularity": "paragraph",
                        "retrieval_route": "text_general",
                    }
                ]
            ),
            embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
            requested_backend="weaviate-hybrid",
            retrieval_route_mode=route_mode,
            route_filter_fields_available={"source_family": True, "granularity": True},
        )

    run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=1,
        run_id="weaviate_route_ab_mixed_diag_failure",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=lane_factory("full_index"),
        weaviate_route_ab_mode="mixed,routed",
        weaviate_route_ab_lane_factory=lane_factory,
    )

    ab_report = json.loads((output_dir / "route_selected_hybrid_evidence_store_ab_report.json").read_text(encoding="utf-8"))
    assert ab_report["mixed_route_dataset_diagnostic"]["executed"] is False
    assert ab_report["mixed_route_dataset_diagnostic"]["unavailable_reason"].startswith("mixed_route_diagnostic_failed")
    assert ab_report["guardrail_status"]["valid"] is False
    assert any("mixed_route_dataset_diagnostic" in item for item in ab_report["guardrail_status"]["violations"])
    assert ab_report["recommendation"] == "invalid_due_to_guardrail_violation"


def test_weaviate_unavailable_fails_without_source_native_local_scan(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    write_jsonl(dataset, [{"id": "q1", "query": "Project Orion", "answerability": "unknown"}])
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    client = FakeWeaviateSourceAtomClient(available=False)
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
    )

    with pytest.raises(WeaviateUnavailableError, match="weaviate_unavailable"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=tmp_path / "reports" / "rag_eval" / "weaviate_unavailable",
            top_k=1,
            run_id="weaviate_unavailable",
            retrieval_surface="source-native",
            retrieval_backend="weaviate-hybrid",
            retrieval_adapter=adapter,
        )

    assert client.local_scan_used is False
    assert client.query_log == []


def test_weaviate_query_failure_marks_run_failed_without_report_disguise(tmp_path: Path) -> None:
    class QueryFailingWeaviateClient(FakeWeaviateSourceAtomClient):
        def query(self, **kwargs: object) -> list[dict]:
            self.query_log.append(dict(kwargs))
            raise WeaviateUnavailableError("weaviate_unavailable: forced query failure")

    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_query_failure"
    write_jsonl(dataset, [{"id": "q1", "query": "Project Orion", "answerability": "unknown"}])
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    client = QueryFailingWeaviateClient()
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
    )

    with pytest.raises(WeaviateUnavailableError, match="forced query failure"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=output_dir,
            top_k=1,
            run_id="weaviate_query_failure",
            retrieval_surface="source-native",
            retrieval_backend="weaviate-hybrid",
            retrieval_adapter=adapter,
        )

    assert not (output_dir / "report.json").exists()
    assert client.local_scan_used is False
    assert client.query_log


def test_weaviate_evidence_resolution_query_failure_fails_run_without_report(tmp_path: Path) -> None:
    class EvidenceLookupFailingAdapter(WeaviateSourceAtomAdapter):
        def evidence_candidates(self, query: str, *, top_k: int) -> list[dict]:
            raise WeaviateUnavailableError("weaviate_unavailable: forced evidence lookup failure")

    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_resolution_failure"
    write_jsonl(
        dataset,
        [
                {
                    "id": "q1",
                    "query": "Project Orion April 2026",
                    "expected_evidence": [
                        {
                            "doc_id": "doc-weaviate",
                            "chunk_id": "chunk-weaviate-1",
                            "text": "Project Orion launch is scheduled for April 2026.",
                            "required": True,
                        }
                    ],
                    "answerability": "unknown",
                }
            ],
    )
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    adapter = EvidenceLookupFailingAdapter(
        config=config,
        client=FakeWeaviateSourceAtomClient(
            objects=[
                {
                    "source_atom_id": "srcatom-weaviate-lookup-1",
                    "evidence_bundle_id": "bundle-weaviate-lookup-1",
                    "doc_id": "doc-weaviate",
                    "chunk_id": "chunk-weaviate-1",
                    "source_family": "TEXT",
                    "source_track": "namu",
                    "title": "Project Orion",
                    "section": "Launch",
                    "text": "Project Orion launch is scheduled for April 2026.",
                    "text_sha256": "sha-weaviate-lookup-1",
                    "source_uri_hash": "uri-sha",
                    "source_hash": "source-sha",
                    "ingestion_run_id": "ingestion-nonprod",
                    "ingestion_version": "v1",
                    "namespace": "actual_rag_eval_nonprod",
                    "visibility": "nonprod",
                }
            ]
        ),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
    )

    with pytest.raises(WeaviateUnavailableError, match="forced evidence lookup failure"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=output_dir,
            top_k=1,
            run_id="weaviate_resolution_failure",
            retrieval_surface="source-native",
            retrieval_backend="weaviate-hybrid",
            retrieval_adapter=adapter,
            evidence_resolution_scope="index-candidate-lookup",
        )

    assert not (output_dir / "report.json").exists()


def test_weaviate_index_cli_defaults_to_streaming_bge_m3_and_rejects_faiss_transfer() -> None:
    parser = build_weaviate_index_parser()

    args = parser.parse_args([])
    v2_args = parser.parse_args(["--schema-version", "weaviate_source_atom_v2"])

    assert args.vector_source == "streaming-bge-m3"
    assert v2_args.schema_version == "weaviate_source_atom_v2"
    assert Path(args.source_native_index_dir).name == "rag-data-all-source-citable-nonprod-bge-m3-v1"
    with pytest.raises(SystemExit):
        parser.parse_args(["--vector-source", "source-native-faiss-bge-m3"])


def test_weaviate_streaming_indexer_checkpoints_and_resumes_without_faiss_transfer(tmp_path: Path) -> None:
    class CountingBgeM3Provider(FakeWeaviateBgeM3EmbeddingProvider):
        def __init__(self) -> None:
            self.embedded_texts: list[str] = []

        def embed_passages(self, texts: list[str]) -> object:
            self.embedded_texts.extend(texts)
            return super().embed_passages(texts)

    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
            "EMBEDDING_DEVICE": "cuda",
        }
    )
    checkpoint_path = tmp_path / "weaviate-index-checkpoint.json"
    first_provider = CountingBgeM3Provider()
    first_client = FakeWeaviateSourceAtomClient()
    first_indexer = WeaviateSourceAtomIndexer(
        config=config,
        client=first_client,
        embedding_builder=BgeM3EmbeddingBuilder(
            model_name="BAAI/bge-m3",
            device="cuda",
            batch_size=2,
            embedding_provider=first_provider,
        ),
    )
    records = [weaviate_source_atom_record(1), weaviate_source_atom_record(2), weaviate_source_atom_record(3)]

    first_manifest = first_indexer.index_records_streaming(
        iter(records[:2]),
        checkpoint_path=checkpoint_path,
        source_atom_registry_path="ai/eval/fixtures/source_atoms.jsonl",
    )

    assert first_manifest["index_vector_source"] == "streaming-bge-m3"
    assert first_manifest["faiss_used_for_index_seed"] is False
    assert first_manifest["indexed_count"] == 2
    assert first_manifest["checkpoint_path"] == checkpoint_path.as_posix()
    assert len(first_client.upsert_log) == 1
    assert first_provider.embedded_texts == [records[0]["text"], records[1]["text"]]

    second_provider = CountingBgeM3Provider()
    second_client = FakeWeaviateSourceAtomClient()
    second_indexer = WeaviateSourceAtomIndexer(
        config=config,
        client=second_client,
        embedding_builder=BgeM3EmbeddingBuilder(
            model_name="BAAI/bge-m3",
            device="cuda",
            batch_size=2,
            embedding_provider=second_provider,
        ),
    )

    resumed_manifest = second_indexer.index_records_streaming(
        iter(records),
        checkpoint_path=checkpoint_path,
        source_atom_registry_path="ai/eval/fixtures/source_atoms.jsonl",
    )
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    assert resumed_manifest["checkpoint_resumed"] is True
    assert resumed_manifest["indexed_count"] == 3
    assert resumed_manifest["upserted_count_this_run"] == 1
    assert resumed_manifest["skipped_count"] == 2
    assert resumed_manifest["embedding_count"] == 3
    assert resumed_manifest["embedding_count_this_run"] == 1
    assert resumed_manifest["faiss_used_for_index_seed"] is False
    assert resumed_manifest["faiss_used_for_active_retrieval"] is False
    assert resumed_manifest["diagnostic_hash_vector_used"] is False
    assert second_provider.embedded_texts == [records[2]["text"]]
    assert len(second_client.upsert_log) == 1
    assert second_client.upsert_log[0]["objects"][0]["source_atom_id"] == "srcatom-index-3"
    assert checkpoint["completed_count"] == 3
    assert checkpoint["completed_source_atom_ids"] == [
        "srcatom-index-1",
        "srcatom-index-2",
        "srcatom-index-3",
    ]
    assert checkpoint["source_atom_text_sha256"]["srcatom-index-3"] == "sha-index-3"


def test_weaviate_streaming_indexer_can_recreate_nonprod_candidate_collection(tmp_path: Path) -> None:
    class RecreateAwareClient(FakeWeaviateSourceAtomClient):
        def __init__(self) -> None:
            super().__init__()
            self.recreate_schema_log: list[dict[str, object]] = []

        def recreate_collection(self, schema: Mapping[str, object]) -> None:
            self.recreate_schema_log.append(dict(schema))
            self.objects.clear()

    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
            "EMBEDDING_DEVICE": "cuda",
        }
    )
    client = RecreateAwareClient()
    indexer = WeaviateSourceAtomIndexer(
        config=config,
        client=client,
        embedding_builder=BgeM3EmbeddingBuilder(
            model_name="BAAI/bge-m3",
            device="cuda",
            batch_size=2,
            embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        ),
    )

    manifest = indexer.index_records_streaming(
        iter([weaviate_source_atom_record(1)]),
        checkpoint_path=tmp_path / "weaviate-index-checkpoint.json",
        source_atom_registry_path="ai/eval/fixtures/source_atoms.jsonl",
        recreate_collection=True,
    )

    assert manifest["collection_recreate_requested"] is True
    assert manifest["collection_recreated_this_run"] is True
    assert len(client.recreate_schema_log) == 1
    assert client.schema_log == []


def test_weaviate_indexer_reports_vectorization_policy_by_granularity() -> None:
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    indexer = WeaviateSourceAtomIndexer(
        config=config,
        client=FakeWeaviateSourceAtomClient(),
        embedding_builder=BgeM3EmbeddingBuilder(
            model_name="BAAI/bge-m3",
            batch_size=2,
            embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        ),
    )

    xlsx_cell = weaviate_source_atom_record(
        2,
        text="workbook=Budget.xlsx | sheet=Approvals | cell=B2 | amount=42",
    )
    xlsx_cell["source_family"] = "XLSX"
    manifest = indexer.index_records([weaviate_source_atom_record(1), xlsx_cell])

    assert manifest["index_object_count"] == 2
    assert manifest["vectorized_object_count"] == 2
    assert manifest["vectorized_object_ratio"] == 1.0
    assert manifest["vectorized_by_granularity"] == {"cell": 1, "paragraph": 1}
    assert manifest["metadata_only_recommended_granularity_counts"] == {"cell": 1}
    assert "cell" in manifest["vectorization_policy"]["metadata_only_by_default"]
    assert manifest["schema_index_v2_rebuild_required_for_metadata_only_policy"] is True


def test_weaviate_v2_config_uses_explicit_nonprod_schema_and_collection() -> None:
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )

    schema = build_weaviate_source_atom_schema(config)

    assert config.schema_version == "weaviate_source_atom_v2"
    assert config.collection_name == "SourceAtomNonprodV2"
    assert schema["schema_version"] == "weaviate_source_atom_v2"
    assert schema["metadata_vector_policy"]["index_time_metadata_only_supported"] is True
    assert "cell" in schema["metadata_vector_policy"]["metadata_only_by_default"]


def test_weaviate_default_backend_uses_explicit_route_selected_nonprod_config_path() -> None:
    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    config_report = adapter.config["weaviate_default_config"]
    rollback = config_report["rollback"]

    assert adapter.retrieval_route_mode == "route_selected"
    assert adapter.config_obj.collection_name == "SourceAtomNonprodRouteSelectedV2"
    assert adapter.config_obj.schema_version == "weaviate_source_atom_v2"
    assert adapter.config_obj.production_namespace is False
    assert config_report["selection"] == "route_selected_nonprod_default"
    assert config_report["explicit_nonprod_config_path"] is True
    assert config_report["config_path"].endswith("ai/eval/configs/weaviate_route_selected_nonprod_default.json")
    assert config_report["fallback_used"] is False
    assert config_report["fail_closed_on_unavailable"] is True
    assert rollback["rollback_key"] == "weaviate_full_index_nonprod_rollback"
    assert rollback["retrieval_route_mode"] == "full_index"
    assert rollback["collection"] == "SourceAtomNonprod"
    assert rollback["schema_version_source_atom"] == "weaviate_source_atom_v1"


def test_weaviate_candidate_surface_config_is_explicit_nonprod_and_not_default(tmp_path: Path) -> None:
    candidate_config_path = tmp_path / "weaviate_route_selected_candidate_surface_v1.json"
    candidate_config_path.write_text(
        json.dumps(
            {
                "selection": "route_selected_candidate_surface_v1",
                "vector_db": "weaviate",
                "url": "http://localhost:8080",
                "grpc_port": 50051,
                "collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV1",
                "namespace": "actual_rag_eval_nonprod",
                "visibility": "nonprod",
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "index_manifest_path": "reports/rag_eval/weaviate_source_atom_index_manifest_nonprod_route_selected_candidate_surface_v1/index_manifest.json",
                "retrieval_route_mode": "route_selected",
                "route_planner_version": "weaviate_route_planner_v1",
                "embedding_model": "BAAI/bge-m3",
                "embedding_device": "auto",
                "hybrid_alpha": 0.5,
                "use_local_docker": True,
                "fallback_used": False,
                "fail_closed_on_unavailable": True,
                "candidate_surface_rebuild": {
                    "schema_version": "actual_rag_eval.candidate_surface_rebuild.v1",
                    "report_only_diagnostic": True,
                    "official_metric": False,
                    "official_metric_input_rows": 0,
                    "candidate_collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV1",
                    "source_collection": "SourceAtomNonprodRouteSelectedV2",
                    "xlsx_row_value_bundle_materialization": True,
                    "production_namespace": False,
                    "source_registry_mutated": False,
                    "latest_current_mutated": False,
                    "external_archive_profiled": False,
                    "external_archive_indexed": False,
                    "source_intake_approval_required": False,
                },
                "rollback": {
                    "rollback_key": "weaviate_full_index_nonprod_rollback",
                    "config_path": "ai/eval/configs/weaviate_full_index_nonprod_rollback.json",
                    "retrieval_route_mode": "full_index",
                    "collection": "SourceAtomNonprod",
                    "schema_version_source_atom": "weaviate_source_atom_v1",
                    "index_manifest_path": "reports/rag_eval/weaviate_source_atom_index_manifest_nonprod/index_manifest.json",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    default_adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        config_path=candidate_config_path.as_posix(),
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    config_report = adapter.config["weaviate_default_config"]
    candidate_surface = config_report["candidate_surface_rebuild"]
    rollback = config_report["rollback"]

    assert default_adapter.config_obj.collection_name == "SourceAtomNonprodRouteSelectedV2"
    assert default_adapter.config["weaviate_default_config"]["selection"] == "route_selected_nonprod_default"
    assert adapter.retrieval_route_mode == "route_selected"
    assert adapter.config_obj.collection_name == "SourceAtomNonprodRouteSelectedCandidateSurfaceV1"
    assert adapter.config_obj.schema_version == "weaviate_source_atom_v2"
    assert adapter.config_obj.production_namespace is False
    assert config_report["selection"] == "route_selected_candidate_surface_v1"
    assert config_report["config_path"] == candidate_config_path.as_posix()
    assert config_report["fallback_used"] is False
    assert config_report["fail_closed_on_unavailable"] is True
    assert candidate_surface["report_only_diagnostic"] is True
    assert candidate_surface["official_metric"] is False
    assert candidate_surface["candidate_collection"] == "SourceAtomNonprodRouteSelectedCandidateSurfaceV1"
    assert candidate_surface["source_collection"] == "SourceAtomNonprodRouteSelectedV2"
    assert candidate_surface["xlsx_row_value_bundle_materialization"] is True
    assert candidate_surface["production_namespace"] is False
    assert candidate_surface["source_registry_mutated"] is False
    assert candidate_surface["latest_current_mutated"] is False
    assert candidate_surface["official_metric_input_rows"] == 0
    assert rollback["rollback_key"] == "weaviate_full_index_nonprod_rollback"
    assert rollback["collection"] == "SourceAtomNonprod"


def test_weaviate_candidate_surface_canonical_config_path_loads() -> None:
    candidate_config_path = Path("ai/eval/configs/weaviate_route_selected_candidate_surface_v1.json")
    assert candidate_config_path.exists()

    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        config_path=candidate_config_path.as_posix(),
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    config_report = adapter.config["weaviate_default_config"]
    candidate_surface = config_report["candidate_surface_rebuild"]
    rollback = config_report["rollback"]

    assert adapter.config_obj.collection_name == "SourceAtomNonprodRouteSelectedCandidateSurfaceV1"
    assert adapter.retrieval_route_mode == "route_selected"
    assert config_report["selection"] == "route_selected_candidate_surface_v1"
    assert config_report["config_path"] == candidate_config_path.as_posix()
    assert config_report["use_local_docker"] is True
    assert config_report["fail_closed_on_unavailable"] is True
    assert candidate_surface["report_only_diagnostic"] is True
    assert candidate_surface["surface_status"] == "dirty_partial"
    assert candidate_surface["metric_blocked_until_complete_manifest"] is True
    assert candidate_surface["official_metric"] is False
    assert candidate_surface["official_metric_input_rows"] == 0
    assert candidate_surface["xlsx_row_value_bundle_materialization"] is True
    assert candidate_surface["source_registry_mutated"] is False
    assert candidate_surface["latest_current_mutated"] is False
    assert candidate_surface["external_archive_profiled"] is False
    assert candidate_surface["external_archive_indexed"] is False
    assert rollback["rollback_key"] == "weaviate_full_index_nonprod_rollback"


def test_weaviate_dirty_candidate_surface_blocks_metric_readiness() -> None:
    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        config_path="ai/eval/configs/weaviate_route_selected_candidate_surface_v1.json",
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    with pytest.raises(WeaviateUnavailableError, match="candidate_surface_dirty_partial_metrics_blocked"):
        adapter.validate_ready_for_run()


def test_weaviate_candidate_surface_v2_requires_complete_manifest(tmp_path: Path) -> None:
    candidate_config_path = Path("ai/eval/configs/weaviate_route_selected_candidate_surface_v2.json")
    assert candidate_config_path.exists()
    candidate_config = json.loads(candidate_config_path.read_text(encoding="utf-8"))
    missing_manifest_path = tmp_path / "missing_index_manifest.json"
    candidate_config["index_manifest_path"] = missing_manifest_path.as_posix()
    isolated_config_path = tmp_path / "weaviate_route_selected_candidate_surface_v2.json"
    isolated_config_path.write_text(
        json.dumps(candidate_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        config_path=isolated_config_path.as_posix(),
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    candidate_surface = adapter.config["weaviate_default_config"]["candidate_surface_rebuild"]
    assert adapter.config_obj.collection_name == "SourceAtomNonprodRouteSelectedCandidateSurfaceV2"
    assert candidate_surface["surface_status"] == "awaiting_complete_manifest"
    assert candidate_surface["metric_blocked_until_complete_manifest"] is True
    with pytest.raises(WeaviateUnavailableError, match="candidate_surface_complete_manifest"):
        adapter.validate_ready_for_run()


def test_weaviate_candidate_surface_complete_manifest_allows_metric_readiness(tmp_path: Path) -> None:
    manifest_path = tmp_path / "index_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "weaviate_source_atom_index_manifest_v1",
                "valid": True,
                "candidate_surface_complete_manifest": True,
                "candidate_surface_complete_manifest_schema_version": "candidate_surface_complete_manifest.v1",
                "candidate_surface_full_corpus_index": True,
                "collection_name": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "indexed_count": 3,
                "skipped_count": 0,
                "failed_count": 0,
                "checkpoint_resumed": False,
                "upserted_count_this_run": 3,
                "collection_recreate_requested": True,
                "collection_recreated_this_run": True,
                "production_namespace": False,
                "source_registry_mutated": False,
                "latest_current_mutated": False,
                "official_metric_input_rows": 0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "weaviate_route_selected_candidate_surface_v2.json"
    config_path.write_text(
        json.dumps(
            {
                "selection": "route_selected_candidate_surface_v2_recreate",
                "vector_db": "weaviate",
                "collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
                "namespace": "actual_rag_eval_nonprod",
                "visibility": "nonprod",
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "index_manifest_path": manifest_path.as_posix(),
                "retrieval_route_mode": "route_selected",
                "fallback_used": False,
                "fail_closed_on_unavailable": True,
                "candidate_surface_rebuild": {
                    "schema_version": "actual_rag_eval.candidate_surface_rebuild.v1",
                    "report_only_diagnostic": True,
                    "surface_status": "awaiting_complete_manifest",
                    "metric_blocked_until_complete_manifest": True,
                    "complete_manifest_required": True,
                    "official_metric": False,
                    "official_metric_input_rows": 0,
                    "candidate_collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
                    "source_collection": "SourceAtomNonprodRouteSelectedV2",
                    "production_namespace": False,
                    "source_registry_mutated": False,
                    "latest_current_mutated": False,
                    "external_archive_profiled": False,
                    "external_archive_indexed": False,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        config_path=config_path.as_posix(),
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    adapter.validate_ready_for_run()
    candidate_surface = adapter.active_path_report["candidate_surface_rebuild"]
    metric_gate = candidate_surface["metric_gate"]
    active_default_surface = adapter.active_path_report["weaviate_default_config"]["candidate_surface_rebuild"]
    config_default_surface = adapter.config["weaviate_default_config"]["candidate_surface_rebuild"]

    assert candidate_surface["surface_status"] == "ready"
    assert candidate_surface["metric_blocked_until_complete_manifest"] is False
    assert "metrics_blocked_reason" not in candidate_surface
    assert metric_gate["complete_manifest_verified"] is True
    assert metric_gate["surface_status"] == "ready"
    assert metric_gate["metric_blocked_until_complete_manifest"] is False
    assert "blocked_reason" not in metric_gate
    assert active_default_surface["surface_status"] == "ready"
    assert active_default_surface["metric_blocked_until_complete_manifest"] is False
    assert "metrics_blocked_reason" not in active_default_surface
    assert config_default_surface["surface_status"] == "ready"
    assert config_default_surface["metric_blocked_until_complete_manifest"] is False
    assert "metrics_blocked_reason" not in config_default_surface


def test_weaviate_candidate_surface_complete_manifest_rejects_newer_partial_checkpoint(
    tmp_path: Path,
) -> None:
    checkpoint_path = tmp_path / "index_checkpoint.json"
    checkpoint_path.write_text(
        json.dumps(
            {
                "schema_version": "weaviate_source_atom_index_checkpoint_v1",
                "collection_name": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
                "completed_count": 2,
                "upserted_count_this_run": 2,
                "skipped_count_this_run": 0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "index_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "weaviate_source_atom_index_manifest_v1",
                "valid": True,
                "candidate_surface_complete_manifest": True,
                "candidate_surface_complete_manifest_schema_version": "candidate_surface_complete_manifest.v1",
                "candidate_surface_full_corpus_index": True,
                "collection_name": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "indexed_count": 3,
                "skipped_count": 0,
                "failed_count": 0,
                "checkpoint_resumed": False,
                "checkpoint_path": checkpoint_path.as_posix(),
                "checkpoint_completed_count": 3,
                "upserted_count_this_run": 3,
                "collection_recreate_requested": True,
                "collection_recreated_this_run": True,
                "production_namespace": False,
                "source_registry_mutated": False,
                "latest_current_mutated": False,
                "official_metric_input_rows": 0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    os.utime(manifest_path, (1_800_000_000, 1_800_000_000))
    os.utime(checkpoint_path, (1_800_000_010, 1_800_000_010))
    config_path = tmp_path / "weaviate_route_selected_candidate_surface_v2.json"
    config_path.write_text(
        json.dumps(
            {
                "selection": "route_selected_candidate_surface_v2_recreate",
                "vector_db": "weaviate",
                "collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
                "namespace": "actual_rag_eval_nonprod",
                "visibility": "nonprod",
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "index_manifest_path": manifest_path.as_posix(),
                "retrieval_route_mode": "route_selected",
                "fallback_used": False,
                "fail_closed_on_unavailable": True,
                "candidate_surface_rebuild": {
                    "schema_version": "actual_rag_eval.candidate_surface_rebuild.v1",
                    "report_only_diagnostic": True,
                    "surface_status": "awaiting_complete_manifest",
                    "metric_blocked_until_complete_manifest": True,
                    "complete_manifest_required": True,
                    "official_metric": False,
                    "official_metric_input_rows": 0,
                    "candidate_collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
                    "source_collection": "SourceAtomNonprodRouteSelectedV2",
                    "production_namespace": False,
                    "source_registry_mutated": False,
                    "latest_current_mutated": False,
                    "external_archive_profiled": False,
                    "external_archive_indexed": False,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        config_path=config_path.as_posix(),
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    with pytest.raises(
        WeaviateUnavailableError,
        match="candidate_surface_complete_manifest_checkpoint_newer_than_manifest",
    ):
        adapter.validate_ready_for_run()


def test_weaviate_candidate_surface_complete_manifest_rejects_schema_mismatch_without_rebuild_block(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "index_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "weaviate_source_atom_index_manifest_v1",
                "valid": True,
                "candidate_surface_complete_manifest": True,
                "candidate_surface_complete_manifest_schema_version": "candidate_surface_complete_manifest.v1",
                "candidate_surface_full_corpus_index": True,
                "collection_name": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
                "schema_version_source_atom": "weaviate_source_atom_v1",
                "indexed_count": 3,
                "skipped_count": 0,
                "failed_count": 0,
                "checkpoint_resumed": False,
                "upserted_count_this_run": 3,
                "collection_recreate_requested": True,
                "collection_recreated_this_run": True,
                "production_namespace": False,
                "source_registry_mutated": False,
                "latest_current_mutated": False,
                "official_metric_input_rows": 0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "weaviate_route_selected_candidate_surface_v2_no_rebuild_block.json"
    config_path.write_text(
        json.dumps(
            {
                "selection": "route_selected_candidate_surface_v2_recreate",
                "vector_db": "weaviate",
                "collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
                "namespace": "actual_rag_eval_nonprod",
                "visibility": "nonprod",
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "index_manifest_path": manifest_path.as_posix(),
                "retrieval_route_mode": "route_selected",
                "fallback_used": False,
                "fail_closed_on_unavailable": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        config_path=config_path.as_posix(),
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    with pytest.raises(
        WeaviateUnavailableError,
        match="candidate_surface_complete_manifest_schema_version_source_atom_mismatch",
    ):
        adapter.validate_ready_for_run()


def test_weaviate_candidate_surface_complete_manifest_requires_exact_v2_collection_allowlist(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "index_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "weaviate_source_atom_index_manifest_v1",
                "valid": True,
                "candidate_surface_complete_manifest": True,
                "candidate_surface_complete_manifest_schema_version": "candidate_surface_complete_manifest.v1",
                "candidate_surface_full_corpus_index": True,
                "collection_name": "SourceAtomNonprodOtherCandidateSurfaceV2",
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "indexed_count": 3,
                "skipped_count": 0,
                "failed_count": 0,
                "checkpoint_resumed": False,
                "upserted_count_this_run": 3,
                "collection_recreate_requested": True,
                "collection_recreated_this_run": True,
                "production_namespace": False,
                "source_registry_mutated": False,
                "latest_current_mutated": False,
                "official_metric_input_rows": 0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "weaviate_route_selected_other_candidate_surface_v2.json"
    config_path.write_text(
        json.dumps(
            {
                "selection": "route_selected_candidate_surface_v2_recreate",
                "vector_db": "weaviate",
                "collection": "SourceAtomNonprodOtherCandidateSurfaceV2",
                "namespace": "actual_rag_eval_nonprod",
                "visibility": "nonprod",
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "index_manifest_path": manifest_path.as_posix(),
                "retrieval_route_mode": "route_selected",
                "fallback_used": False,
                "fail_closed_on_unavailable": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        config_path=config_path.as_posix(),
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    with pytest.raises(
        WeaviateUnavailableError,
        match="candidate_surface_complete_manifest_collection_allowlist_blocked",
    ):
        adapter.validate_ready_for_run()


@pytest.mark.parametrize(
    ("manifest_override", "match"),
    [
        ({"valid": False}, "candidate_surface_complete_manifest_invalid"),
        ({"candidate_surface_complete_manifest": False}, "candidate_surface_complete_manifest_missing"),
        (
            {"candidate_surface_complete_manifest_schema_version": "candidate_surface_complete_manifest.v0"},
            "candidate_surface_complete_manifest_schema_version_invalid",
        ),
        ({"collection_name": "SourceAtomNonprodRouteSelectedCandidateSurfaceV1"}, "candidate_surface_complete_manifest_collection_mismatch"),
        (
            {"schema_version_source_atom": "weaviate_source_atom_v1"},
            "candidate_surface_complete_manifest_schema_version_source_atom_mismatch",
        ),
        ({"candidate_surface_full_corpus_index": False}, "candidate_surface_complete_manifest_full_corpus_index_missing"),
        ({"production_namespace": True}, "candidate_surface_complete_manifest_production_namespace_blocked"),
        ({"source_registry_mutated": True}, "candidate_surface_complete_manifest_source_registry_mutated_blocked"),
        ({"latest_current_mutated": True}, "candidate_surface_complete_manifest_latest_current_mutated_blocked"),
        ({"official_metric_input_rows": 1}, "candidate_surface_complete_manifest_official_metric_input_rows_blocked"),
        ({"failed_count": 1}, "candidate_surface_complete_manifest_failed_count_blocked"),
        ({"checkpoint_resumed": True}, "candidate_surface_complete_manifest_checkpoint_resumed_blocked"),
        ({"collection_recreated_this_run": False}, "candidate_surface_complete_manifest_collection_recreate_missing"),
        ({"skipped_count": 1}, "candidate_surface_complete_manifest_skipped_count_blocked"),
        ({"upserted_count_this_run": 2}, "candidate_surface_complete_manifest_upserted_indexed_count_mismatch"),
        ({"indexed_count": 0, "upserted_count_this_run": 0}, "candidate_surface_complete_manifest_indexed_count_invalid"),
        ({"indexed_count": "not-an-int"}, "candidate_surface_complete_manifest_count_invalid"),
        ({"skipped_count": None}, "candidate_surface_complete_manifest_count_invalid"),
        ({"skipped_count": "not-an-int"}, "candidate_surface_complete_manifest_count_invalid"),
        ({"failed_count": "not-an-int"}, "candidate_surface_complete_manifest_count_invalid"),
        ({"upserted_count_this_run": "not-an-int"}, "candidate_surface_complete_manifest_count_invalid"),
        ({"official_metric_input_rows": "not-an-int"}, "candidate_surface_complete_manifest_count_invalid"),
    ],
)
def test_weaviate_candidate_surface_complete_manifest_rejects_invalid_edges(
    tmp_path: Path,
    manifest_override: dict,
    match: str,
) -> None:
    manifest = {
        "schema_version": "weaviate_source_atom_index_manifest_v1",
        "valid": True,
        "candidate_surface_complete_manifest": True,
        "candidate_surface_complete_manifest_schema_version": "candidate_surface_complete_manifest.v1",
        "candidate_surface_full_corpus_index": True,
        "collection_name": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
        "schema_version_source_atom": "weaviate_source_atom_v2",
        "indexed_count": 3,
        "skipped_count": 0,
        "failed_count": 0,
        "checkpoint_resumed": False,
        "upserted_count_this_run": 3,
        "collection_recreate_requested": True,
        "collection_recreated_this_run": True,
        "production_namespace": False,
        "source_registry_mutated": False,
        "latest_current_mutated": False,
        "official_metric_input_rows": 0,
    }
    manifest.update(manifest_override)
    manifest_path = tmp_path / "index_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    config_path = tmp_path / "weaviate_route_selected_candidate_surface_v2.json"
    config_path.write_text(
        json.dumps(
            {
                "selection": "route_selected_candidate_surface_v2_recreate",
                "vector_db": "weaviate",
                "collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
                "namespace": "actual_rag_eval_nonprod",
                "visibility": "nonprod",
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "index_manifest_path": manifest_path.as_posix(),
                "retrieval_route_mode": "route_selected",
                "fallback_used": False,
                "fail_closed_on_unavailable": True,
                "candidate_surface_rebuild": {
                    "schema_version": "actual_rag_eval.candidate_surface_rebuild.v1",
                    "report_only_diagnostic": True,
                    "surface_status": "awaiting_complete_manifest",
                    "metric_blocked_until_complete_manifest": True,
                    "complete_manifest_required": True,
                    "official_metric": False,
                    "official_metric_input_rows": 0,
                    "candidate_collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
                    "source_collection": "SourceAtomNonprodRouteSelectedV2",
                    "production_namespace": False,
                    "source_registry_mutated": False,
                    "latest_current_mutated": False,
                    "external_archive_profiled": False,
                    "external_archive_indexed": False,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        config_path=config_path.as_posix(),
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    with pytest.raises(WeaviateUnavailableError, match=match):
        adapter.validate_ready_for_run()


@pytest.mark.parametrize(
    "missing_field",
    [
        "official_metric_input_rows",
        "indexed_count",
        "skipped_count",
        "failed_count",
        "upserted_count_this_run",
    ],
)
def test_weaviate_candidate_surface_complete_manifest_rejects_missing_count_fields(
    tmp_path: Path,
    missing_field: str,
) -> None:
    manifest = {
        "schema_version": "weaviate_source_atom_index_manifest_v1",
        "valid": True,
        "candidate_surface_complete_manifest": True,
        "candidate_surface_complete_manifest_schema_version": "candidate_surface_complete_manifest.v1",
        "candidate_surface_full_corpus_index": True,
        "collection_name": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
        "schema_version_source_atom": "weaviate_source_atom_v2",
        "indexed_count": 3,
        "skipped_count": 0,
        "failed_count": 0,
        "checkpoint_resumed": False,
        "upserted_count_this_run": 3,
        "collection_recreate_requested": True,
        "collection_recreated_this_run": True,
        "production_namespace": False,
        "source_registry_mutated": False,
        "latest_current_mutated": False,
        "official_metric_input_rows": 0,
    }
    manifest.pop(missing_field)
    manifest_path = tmp_path / "index_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    config_path = tmp_path / "weaviate_route_selected_candidate_surface_v2.json"
    config_path.write_text(
        json.dumps(
            {
                "selection": "route_selected_candidate_surface_v2_recreate",
                "vector_db": "weaviate",
                "collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
                "namespace": "actual_rag_eval_nonprod",
                "visibility": "nonprod",
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "index_manifest_path": manifest_path.as_posix(),
                "retrieval_route_mode": "route_selected",
                "fallback_used": False,
                "fail_closed_on_unavailable": True,
                "candidate_surface_rebuild": {
                    "schema_version": "actual_rag_eval.candidate_surface_rebuild.v1",
                    "report_only_diagnostic": True,
                    "surface_status": "awaiting_complete_manifest",
                    "metric_blocked_until_complete_manifest": True,
                    "complete_manifest_required": True,
                    "official_metric": False,
                    "official_metric_input_rows": 0,
                    "candidate_collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
                    "source_collection": "SourceAtomNonprodRouteSelectedV2",
                    "production_namespace": False,
                    "source_registry_mutated": False,
                    "latest_current_mutated": False,
                    "external_archive_profiled": False,
                    "external_archive_indexed": False,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        config_path=config_path.as_posix(),
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    with pytest.raises(WeaviateUnavailableError, match="candidate_surface_complete_manifest_count_invalid"):
        adapter.validate_ready_for_run()


def test_weaviate_index_parser_exposes_candidate_surface_xlsx_row_bundle_flag() -> None:
    parser = build_weaviate_index_parser()

    args = parser.parse_args(
        [
            "--schema-version",
            "weaviate_source_atom_v2",
            "--weaviate-collection-name",
            "SourceAtomNonprodRouteSelectedCandidateSurfaceV1",
            "--synthesize-xlsx-row-value-bundles",
        ]
    )

    assert args.synthesize_xlsx_row_value_bundles is True


def test_weaviate_candidate_surface_v2_index_success_writes_complete_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeStreamingIndexer:
        def __init__(self, **kwargs: object) -> None:
            self.config = kwargs["config"]
            self.client = FakeWeaviateSourceAtomClient()
            self.recreate_requested = False

        def index_records_streaming(self, records: object, **kwargs: object) -> dict:
            list(records)
            self.recreate_requested = bool(kwargs.get("recreate_collection"))
            return {
                "schema_version": "weaviate_source_atom_index_manifest_v1",
                "valid": True,
                "collection_name": self.config.collection_name,
                "schema_version_source_atom": self.config.schema_version,
                "indexed_count": 3,
                "skipped_count": 0,
                "failed_count": 0,
                "checkpoint_resumed": False,
                "upserted_count_this_run": 3,
                "production_namespace": False,
                "collection_recreate_requested": self.recreate_requested,
                "collection_recreated_this_run": self.recreate_requested,
                "diagnostic_hash_vector_used": False,
                "faiss_used_for_active_retrieval": False,
            }

    class FakeLoader:
        def __init__(self, **kwargs: object) -> None:
            self.synthesize_xlsx_row_value_bundles = bool(kwargs["synthesize_xlsx_row_value_bundles"])

        def iter_units(self) -> list[dict]:
            return [
                {
                    "source_atom_id": "srcatom-v2-candidate-1",
                    "source_family": "XLSX",
                    "text": "source-owned row/value bundle",
                }
            ]

        def describe(self) -> dict:
            return {"synthesize_xlsx_row_value_bundles": self.synthesize_xlsx_row_value_bundles}

    monkeypatch.setattr(weaviate_index_script, "WeaviateSourceAtomIndexer", FakeStreamingIndexer)
    monkeypatch.setattr(weaviate_index_script, "SourceNativeCorpusLoader", FakeLoader)
    manifest_path = tmp_path / "index_manifest.json"
    checkpoint_path = tmp_path / "index_checkpoint.json"

    rc = weaviate_index_script.main(
        [
            "--schema-version",
            "weaviate_source_atom_v2",
            "--weaviate-collection-name",
            "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
            "--source-native-index-dir",
            str(tmp_path),
            "--source-atom-registry-path",
            str(tmp_path / "source_atoms.jsonl"),
            "--manifest-path",
            str(manifest_path),
            "--checkpoint-path",
            str(checkpoint_path),
            "--reset-checkpoint",
            "--synthesize-xlsx-row-value-bundles",
        ]
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert rc == 0
    assert manifest["valid"] is True
    assert manifest["collection_name"] == "SourceAtomNonprodRouteSelectedCandidateSurfaceV2"
    assert manifest["collection_recreate_requested"] is True
    assert manifest["collection_recreated_this_run"] is True
    assert manifest["candidate_surface_complete_manifest"] is True
    assert manifest["candidate_surface_complete_manifest_schema_version"] == "candidate_surface_complete_manifest.v1"
    assert manifest["candidate_surface_full_corpus_index"] is True
    assert manifest["index_limit"] == 0
    assert manifest["candidate_surface_metric_blocked_until_complete_manifest"] is False
    assert manifest["candidate_surface_restart_policy"] == "recreate_collection_with_fresh_manifest_v2"
    assert manifest["synthesize_xlsx_row_value_bundles"] is True
    assert manifest["source_native_loader"]["synthesize_xlsx_row_value_bundles"] is True
    assert manifest["official_metric_input_rows"] == 0
    assert manifest["production_namespace"] is False
    assert manifest["source_registry_mutated"] is False
    assert manifest["latest_current_mutated"] is False


def test_weaviate_candidate_surface_v2_complete_manifest_requires_collection_recreate_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class NoRecreateStreamingIndexer:
        def __init__(self, **kwargs: object) -> None:
            self.config = kwargs["config"]
            self.client = FakeWeaviateSourceAtomClient()

        def index_records_streaming(self, records: object, **kwargs: object) -> dict:
            list(records)
            return {
                "schema_version": "weaviate_source_atom_index_manifest_v1",
                "valid": True,
                "collection_name": self.config.collection_name,
                "schema_version_source_atom": self.config.schema_version,
                "indexed_count": 3,
                "skipped_count": 0,
                "failed_count": 0,
                "checkpoint_resumed": False,
                "upserted_count_this_run": 3,
                "production_namespace": False,
                "collection_recreate_requested": False,
                "collection_recreated_this_run": False,
                "diagnostic_hash_vector_used": False,
                "faiss_used_for_active_retrieval": False,
            }

    class FakeLoader:
        def __init__(self, **kwargs: object) -> None:
            self.synthesize_xlsx_row_value_bundles = bool(kwargs["synthesize_xlsx_row_value_bundles"])

        def iter_units(self) -> list[dict]:
            return [{"source_atom_id": "srcatom-v2-candidate-1", "source_family": "XLSX", "text": "bundle"}]

        def describe(self) -> dict:
            return {"synthesize_xlsx_row_value_bundles": self.synthesize_xlsx_row_value_bundles}

    monkeypatch.setattr(weaviate_index_script, "WeaviateSourceAtomIndexer", NoRecreateStreamingIndexer)
    monkeypatch.setattr(weaviate_index_script, "SourceNativeCorpusLoader", FakeLoader)
    manifest_path = tmp_path / "index_manifest.json"
    checkpoint_path = tmp_path / "index_checkpoint.json"

    rc = weaviate_index_script.main(
        [
            "--schema-version",
            "weaviate_source_atom_v2",
            "--weaviate-collection-name",
            "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
            "--source-native-index-dir",
            str(tmp_path),
            "--source-atom-registry-path",
            str(tmp_path / "source_atoms.jsonl"),
            "--manifest-path",
            str(manifest_path),
            "--checkpoint-path",
            str(checkpoint_path),
            "--reset-checkpoint",
            "--synthesize-xlsx-row-value-bundles",
        ]
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert rc == 0
    assert manifest["valid"] is True
    assert manifest["collection_recreate_requested"] is True
    assert manifest["collection_recreated_this_run"] is False
    assert manifest["candidate_surface_complete_manifest"] is False
    assert manifest["candidate_surface_complete_manifest_schema_version"] == ""
    assert manifest["candidate_surface_metric_blocked_until_complete_manifest"] is True
    assert manifest["official_metric_input_rows"] == 0


def test_weaviate_candidate_surface_v2_index_requires_schema_v2_for_complete_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeStreamingIndexer:
        def __init__(self, **kwargs: object) -> None:
            self.config = kwargs["config"]
            self.client = FakeWeaviateSourceAtomClient()

        def index_records_streaming(self, records: object, **kwargs: object) -> dict:
            list(records)
            return {
                "schema_version": "weaviate_source_atom_index_manifest_v1",
                "valid": True,
                "collection_name": self.config.collection_name,
                "schema_version_source_atom": self.config.schema_version,
                "indexed_count": 3,
                "skipped_count": 0,
                "failed_count": 0,
                "checkpoint_resumed": False,
                "upserted_count_this_run": 3,
                "production_namespace": False,
                "diagnostic_hash_vector_used": False,
                "faiss_used_for_active_retrieval": False,
            }

    class FakeLoader:
        def __init__(self, **kwargs: object) -> None:
            self.synthesize_xlsx_row_value_bundles = bool(kwargs["synthesize_xlsx_row_value_bundles"])

        def iter_units(self) -> list[dict]:
            return [{"source_atom_id": "srcatom-v2-candidate-1", "source_family": "XLSX", "text": "bundle"}]

        def describe(self) -> dict:
            return {"synthesize_xlsx_row_value_bundles": self.synthesize_xlsx_row_value_bundles}

    monkeypatch.setattr(weaviate_index_script, "WeaviateSourceAtomIndexer", FakeStreamingIndexer)
    monkeypatch.setattr(weaviate_index_script, "SourceNativeCorpusLoader", FakeLoader)
    monkeypatch.delenv("WEAVIATE_SCHEMA_VERSION", raising=False)
    monkeypatch.delenv("ACTUAL_RAG_EVAL_WEAVIATE_SCHEMA_VERSION", raising=False)
    manifest_path = tmp_path / "index_manifest.json"

    rc = weaviate_index_script.main(
        [
            "--weaviate-collection-name",
            "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
            "--source-native-index-dir",
            str(tmp_path),
            "--source-atom-registry-path",
            str(tmp_path / "source_atoms.jsonl"),
            "--manifest-path",
            str(manifest_path),
            "--synthesize-xlsx-row-value-bundles",
        ]
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert rc == 0
    assert manifest["valid"] is True
    assert manifest["collection_name"] == "SourceAtomNonprodRouteSelectedCandidateSurfaceV2"
    assert manifest["schema_version_source_atom"] == "weaviate_source_atom_v1"
    assert manifest["candidate_surface_complete_manifest"] is False
    assert manifest["candidate_surface_complete_manifest_schema_version"] == ""
    assert manifest["candidate_surface_metric_blocked_until_complete_manifest"] is True
    assert manifest["candidate_surface_restart_policy"] == "recreate_collection_with_fresh_manifest_v2"
    assert manifest["official_metric_input_rows"] == 0


def test_weaviate_candidate_surface_v2_index_limit_keeps_complete_manifest_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeStreamingIndexer:
        def __init__(self, **kwargs: object) -> None:
            self.config = kwargs["config"]
            self.client = FakeWeaviateSourceAtomClient()

        def index_records_streaming(self, records: object, **kwargs: object) -> dict:
            list(records)
            return {
                "schema_version": "weaviate_source_atom_index_manifest_v1",
                "valid": True,
                "collection_name": self.config.collection_name,
                "schema_version_source_atom": self.config.schema_version,
                "indexed_count": 1,
                "skipped_count": 0,
                "failed_count": 0,
                "checkpoint_resumed": False,
                "upserted_count_this_run": 1,
                "production_namespace": False,
                "diagnostic_hash_vector_used": False,
                "faiss_used_for_active_retrieval": False,
            }

    class FakeLoader:
        def __init__(self, **kwargs: object) -> None:
            self.synthesize_xlsx_row_value_bundles = bool(kwargs["synthesize_xlsx_row_value_bundles"])

        def iter_units(self) -> list[dict]:
            return [
                {"source_atom_id": "srcatom-v2-candidate-1", "source_family": "XLSX", "text": "bundle one"},
                {"source_atom_id": "srcatom-v2-candidate-2", "source_family": "XLSX", "text": "bundle two"},
            ]

        def describe(self) -> dict:
            return {"synthesize_xlsx_row_value_bundles": self.synthesize_xlsx_row_value_bundles}

    monkeypatch.setattr(weaviate_index_script, "WeaviateSourceAtomIndexer", FakeStreamingIndexer)
    monkeypatch.setattr(weaviate_index_script, "SourceNativeCorpusLoader", FakeLoader)
    manifest_path = tmp_path / "index_manifest.json"

    rc = weaviate_index_script.main(
        [
            "--schema-version",
            "weaviate_source_atom_v2",
            "--weaviate-collection-name",
            "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
            "--source-native-index-dir",
            str(tmp_path),
            "--source-atom-registry-path",
            str(tmp_path / "source_atoms.jsonl"),
            "--manifest-path",
            str(manifest_path),
            "--limit",
            "1",
            "--synthesize-xlsx-row-value-bundles",
        ]
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert rc == 0
    assert manifest["valid"] is True
    assert manifest["index_limit"] == 1
    assert manifest["candidate_surface_full_corpus_index"] is False
    assert manifest["candidate_surface_complete_manifest"] is False
    assert manifest["candidate_surface_complete_manifest_schema_version"] == ""
    assert manifest["candidate_surface_metric_blocked_until_complete_manifest"] is True
    assert manifest["official_metric_input_rows"] == 0
    assert manifest["source_registry_mutated"] is False
    assert manifest["latest_current_mutated"] is False


@pytest.mark.parametrize(
    ("collection_name", "args_extra", "expected_restart_policy"),
    [
        ("SourceAtomNonprodRouteSelectedCandidateSurfaceV2", [], "recreate_collection_with_fresh_manifest_v2"),
        (
            "SourceAtomNonprodRouteSelectedCandidateSurfaceV1",
            ["--synthesize-xlsx-row-value-bundles"],
            "dirty_partial_reindex_required",
        ),
        (
            "SourceAtomNonprodOtherCandidateSurfaceV2",
            ["--reset-checkpoint", "--synthesize-xlsx-row-value-bundles"],
            "dirty_partial_reindex_required",
        ),
    ],
)
def test_weaviate_candidate_surface_index_complete_manifest_requires_v2_and_xlsx_bundle_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    collection_name: str,
    args_extra: list[str],
    expected_restart_policy: str,
) -> None:
    class FakeStreamingIndexer:
        def __init__(self, **kwargs: object) -> None:
            self.config = kwargs["config"]
            self.client = FakeWeaviateSourceAtomClient()

        def index_records_streaming(self, records: object, **kwargs: object) -> dict:
            list(records)
            return {
                "schema_version": "weaviate_source_atom_index_manifest_v1",
                "valid": True,
                "collection_name": self.config.collection_name,
                "schema_version_source_atom": self.config.schema_version,
                "indexed_count": 3,
                "skipped_count": 0,
                "failed_count": 0,
                "checkpoint_resumed": False,
                "upserted_count_this_run": 3,
                "production_namespace": False,
                "diagnostic_hash_vector_used": False,
                "faiss_used_for_active_retrieval": False,
            }

    class FakeLoader:
        def __init__(self, **kwargs: object) -> None:
            self.synthesize_xlsx_row_value_bundles = bool(kwargs["synthesize_xlsx_row_value_bundles"])

        def iter_units(self) -> list[dict]:
            return [{"source_atom_id": "srcatom-v2-candidate-1", "source_family": "XLSX", "text": "bundle"}]

        def describe(self) -> dict:
            return {"synthesize_xlsx_row_value_bundles": self.synthesize_xlsx_row_value_bundles}

    monkeypatch.setattr(weaviate_index_script, "WeaviateSourceAtomIndexer", FakeStreamingIndexer)
    monkeypatch.setattr(weaviate_index_script, "SourceNativeCorpusLoader", FakeLoader)
    manifest_path = tmp_path / "index_manifest.json"

    rc = weaviate_index_script.main(
        [
            "--schema-version",
            "weaviate_source_atom_v2",
            "--weaviate-collection-name",
            collection_name,
            "--source-native-index-dir",
            str(tmp_path),
            "--source-atom-registry-path",
            str(tmp_path / "source_atoms.jsonl"),
            "--manifest-path",
            str(manifest_path),
            *args_extra,
        ]
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert rc == 0
    assert manifest["valid"] is True
    assert manifest["candidate_surface_complete_manifest"] is False
    assert manifest["candidate_surface_complete_manifest_schema_version"] == ""
    assert manifest["candidate_surface_metric_blocked_until_complete_manifest"] is True
    assert manifest["candidate_surface_restart_policy"] == expected_restart_policy
    assert manifest["source_native_loader"]["synthesize_xlsx_row_value_bundles"] is bool(args_extra)
    assert manifest["official_metric_input_rows"] == 0
    assert manifest["source_registry_mutated"] is False
    assert manifest["latest_current_mutated"] is False


@pytest.mark.parametrize(
    "manifest_override",
    [
        {"indexed_count": 0, "upserted_count_this_run": 0},
        {"failed_count": 1},
        {"indexed_count": "not-an-int"},
        {"checkpoint_resumed": True},
        {"skipped_count": 1},
        {"upserted_count_this_run": 2},
    ],
)
def test_weaviate_candidate_surface_v2_index_incomplete_counts_keep_metrics_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    manifest_override: dict,
) -> None:
    class IncompleteStreamingIndexer:
        def __init__(self, **kwargs: object) -> None:
            self.config = kwargs["config"]
            self.client = FakeWeaviateSourceAtomClient()

        def index_records_streaming(self, records: object, **kwargs: object) -> dict:
            list(records)
            manifest = {
                "schema_version": "weaviate_source_atom_index_manifest_v1",
                "valid": True,
                "collection_name": self.config.collection_name,
                "schema_version_source_atom": self.config.schema_version,
                "indexed_count": 3,
                "skipped_count": 0,
                "failed_count": 0,
                "checkpoint_resumed": False,
                "upserted_count_this_run": 3,
                "production_namespace": False,
                "diagnostic_hash_vector_used": False,
                "faiss_used_for_active_retrieval": False,
            }
            manifest.update(manifest_override)
            return manifest

    class FakeLoader:
        def __init__(self, **kwargs: object) -> None:
            self.synthesize_xlsx_row_value_bundles = bool(kwargs["synthesize_xlsx_row_value_bundles"])

        def iter_units(self) -> list[dict]:
            return [{"source_atom_id": "srcatom-v2-candidate-1", "source_family": "XLSX", "text": "bundle"}]

        def describe(self) -> dict:
            return {"synthesize_xlsx_row_value_bundles": self.synthesize_xlsx_row_value_bundles}

    monkeypatch.setattr(weaviate_index_script, "WeaviateSourceAtomIndexer", IncompleteStreamingIndexer)
    monkeypatch.setattr(weaviate_index_script, "SourceNativeCorpusLoader", FakeLoader)
    manifest_path = tmp_path / "index_manifest.json"

    rc = weaviate_index_script.main(
        [
            "--schema-version",
            "weaviate_source_atom_v2",
            "--weaviate-collection-name",
            "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
            "--source-native-index-dir",
            str(tmp_path),
            "--source-atom-registry-path",
            str(tmp_path / "source_atoms.jsonl"),
            "--manifest-path",
            str(manifest_path),
            "--synthesize-xlsx-row-value-bundles",
        ]
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert rc == 0
    assert manifest["valid"] is True
    assert manifest["candidate_surface_complete_manifest"] is False
    assert manifest["candidate_surface_complete_manifest_schema_version"] == ""
    assert manifest["candidate_surface_metric_blocked_until_complete_manifest"] is True
    assert manifest["official_metric_input_rows"] == 0
    assert manifest["source_registry_mutated"] is False
    assert manifest["latest_current_mutated"] is False


def test_weaviate_candidate_surface_v2_resumed_checkpoint_keeps_metrics_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class ResumedStreamingIndexer:
        def __init__(self, **kwargs: object) -> None:
            self.config = kwargs["config"]
            self.client = FakeWeaviateSourceAtomClient()

        def index_records_streaming(self, records: object, **kwargs: object) -> dict:
            list(records)
            return {
                "schema_version": "weaviate_source_atom_index_manifest_v1",
                "valid": True,
                "collection_name": self.config.collection_name,
                "schema_version_source_atom": self.config.schema_version,
                "indexed_count": 3,
                "skipped_count": 1,
                "failed_count": 0,
                "checkpoint_resumed": True,
                "upserted_count_this_run": 2,
                "production_namespace": False,
                "diagnostic_hash_vector_used": False,
                "faiss_used_for_active_retrieval": False,
            }

    class FakeLoader:
        def __init__(self, **kwargs: object) -> None:
            self.synthesize_xlsx_row_value_bundles = bool(kwargs["synthesize_xlsx_row_value_bundles"])

        def iter_units(self) -> list[dict]:
            return [{"source_atom_id": "srcatom-v2-candidate-1", "source_family": "XLSX", "text": "bundle"}]

        def describe(self) -> dict:
            return {"synthesize_xlsx_row_value_bundles": self.synthesize_xlsx_row_value_bundles}

    monkeypatch.setattr(weaviate_index_script, "WeaviateSourceAtomIndexer", ResumedStreamingIndexer)
    monkeypatch.setattr(weaviate_index_script, "SourceNativeCorpusLoader", FakeLoader)
    manifest_path = tmp_path / "index_manifest.json"

    rc = weaviate_index_script.main(
        [
            "--schema-version",
            "weaviate_source_atom_v2",
            "--weaviate-collection-name",
            "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
            "--source-native-index-dir",
            str(tmp_path),
            "--source-atom-registry-path",
            str(tmp_path / "source_atoms.jsonl"),
            "--manifest-path",
            str(manifest_path),
            "--synthesize-xlsx-row-value-bundles",
        ]
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert rc == 0
    assert manifest["valid"] is True
    assert manifest["checkpoint_resumed"] is True
    assert manifest["candidate_surface_complete_manifest"] is False
    assert manifest["candidate_surface_complete_manifest_schema_version"] == ""
    assert manifest["candidate_surface_metric_blocked_until_complete_manifest"] is True
    assert manifest["candidate_surface_restart_policy"] == "recreate_collection_with_fresh_manifest_v2"
    assert manifest["official_metric_input_rows"] == 0
    assert manifest["source_registry_mutated"] is False
    assert manifest["latest_current_mutated"] is False


def test_weaviate_candidate_surface_v2_index_failure_manifest_keeps_metrics_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FailingStreamingIndexer:
        def __init__(self, **kwargs: object) -> None:
            self.config = kwargs["config"]
            self.client = FakeWeaviateSourceAtomClient()

        def index_records_streaming(self, records: object, **kwargs: object) -> dict:
            raise RuntimeError("boom")

    class FakeLoader:
        def __init__(self, **kwargs: object) -> None:
            self.synthesize_xlsx_row_value_bundles = bool(kwargs["synthesize_xlsx_row_value_bundles"])

        def iter_units(self) -> list[dict]:
            return [{"source_atom_id": "srcatom-v2-candidate-1", "source_family": "XLSX", "text": "bundle"}]

        def describe(self) -> dict:
            return {"synthesize_xlsx_row_value_bundles": self.synthesize_xlsx_row_value_bundles}

    monkeypatch.setattr(weaviate_index_script, "WeaviateSourceAtomIndexer", FailingStreamingIndexer)
    monkeypatch.setattr(weaviate_index_script, "SourceNativeCorpusLoader", FakeLoader)
    manifest_path = tmp_path / "index_manifest.json"

    rc = weaviate_index_script.main(
        [
            "--schema-version",
            "weaviate_source_atom_v2",
            "--weaviate-collection-name",
            "SourceAtomNonprodRouteSelectedCandidateSurfaceV2",
            "--source-native-index-dir",
            str(tmp_path),
            "--source-atom-registry-path",
            str(tmp_path / "source_atoms.jsonl"),
            "--manifest-path",
            str(manifest_path),
            "--synthesize-xlsx-row-value-bundles",
        ]
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert rc == 1
    assert manifest["valid"] is False
    assert manifest["collection_name"] == "SourceAtomNonprodRouteSelectedCandidateSurfaceV2"
    assert manifest["candidate_surface_complete_manifest"] is False
    assert manifest["candidate_surface_complete_manifest_schema_version"] == ""
    assert manifest["candidate_surface_metric_blocked_until_complete_manifest"] is True
    assert manifest["candidate_surface_restart_policy"] == "recreate_collection_with_fresh_manifest_v2"
    assert manifest["official_metric_input_rows"] == 0
    assert manifest["source_registry_mutated"] is False
    assert manifest["latest_current_mutated"] is False
    assert manifest["python_local_corpus_scan_used_for_candidate_generation"] is False
    assert manifest["source_native_layered_retrieval_used_for_candidate_generation"] is False
    assert manifest["faiss_used_for_active_retrieval"] is False
    assert "RuntimeError: boom" in manifest["fallback_reason"]


def test_weaviate_candidate_surface_config_rejects_protected_surface_flags(tmp_path: Path) -> None:
    config_path = tmp_path / "weaviate_route_selected_candidate_surface_v1.json"
    base_candidate_surface = {
        "schema_version": "actual_rag_eval.candidate_surface_rebuild.v1",
        "report_only_diagnostic": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "candidate_collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV1",
        "source_collection": "SourceAtomNonprodRouteSelectedV2",
        "production_namespace": False,
        "source_registry_mutated": False,
        "latest_current_mutated": False,
    }

    for override, match in [
        ({"report_only_diagnostic": False}, "report_only_diagnostic"),
        ({"official_metric": True}, "official_metric"),
        ({"official_metric_input_rows": 1}, "official_metric_input_rows"),
        ({"source_registry_mutated": True}, "source_registry_mutated"),
        ({"latest_current_mutated": True}, "latest_current_mutated"),
        ({"production_namespace": True}, "production_namespace"),
        ({"external_archive_profiled": True}, "external_archive_profiled"),
        ({"external_archive_indexed": True}, "external_archive_indexed"),
    ]:
        candidate_surface = dict(base_candidate_surface)
        candidate_surface.update(override)
        config_path.write_text(
            json.dumps(
                {
                    "selection": "route_selected_candidate_surface_v1",
                    "vector_db": "weaviate",
                    "collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV1",
                    "namespace": "actual_rag_eval_nonprod",
                    "visibility": "nonprod",
                    "schema_version_source_atom": "weaviate_source_atom_v2",
                    "retrieval_route_mode": "route_selected",
                    "fallback_used": False,
                    "fail_closed_on_unavailable": True,
                    "candidate_surface_rebuild": candidate_surface,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        with pytest.raises(WeaviateUnavailableError, match=match):
            build_default_weaviate_adapter(
                requested_backend="weaviate-hybrid",
                config_path=config_path.as_posix(),
                client=FakeWeaviateSourceAtomClient(),
                embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
            )


def test_weaviate_candidate_surface_config_rejects_production_namespace_claiming_nonprod(tmp_path: Path) -> None:
    config_path = tmp_path / "weaviate_route_selected_candidate_surface_v1.json"
    config_path.write_text(
        json.dumps(
            {
                "selection": "route_selected_candidate_surface_v1",
                "vector_db": "weaviate",
                "collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV1",
                "namespace": "actual_rag_eval_prod",
                "visibility": "nonprod",
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "retrieval_route_mode": "route_selected",
                "fallback_used": False,
                "fail_closed_on_unavailable": True,
                "candidate_surface_rebuild": {
                    "schema_version": "actual_rag_eval.candidate_surface_rebuild.v1",
                    "report_only_diagnostic": True,
                    "official_metric": False,
                    "official_metric_input_rows": 0,
                    "candidate_collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV1",
                    "source_collection": "SourceAtomNonprodRouteSelectedV2",
                    "production_namespace": False,
                    "source_registry_mutated": False,
                    "latest_current_mutated": False,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with pytest.raises(WeaviateUnavailableError, match="production_or_ambiguous_namespace_blocked"):
        build_default_weaviate_adapter(
            requested_backend="weaviate-hybrid",
            config_path=config_path.as_posix(),
            client=FakeWeaviateSourceAtomClient(),
            embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        )


def test_weaviate_candidate_surface_report_hashes_manifest_file_bytes(tmp_path: Path) -> None:
    manifest_path = tmp_path / "index_manifest.json"
    manifest_payload = {
        "valid": True,
        "collection_name": "SourceAtomNonprodRouteSelectedCandidateSurfaceV1",
        "schema_version_source_atom": "weaviate_source_atom_v2",
        "indexed_count": 3,
        "vectorized_object_count": 2,
        "metadata_only_object_count": 1,
        "vectorized_by_granularity": {"paragraph": 2},
        "metadata_only_by_granularity": {"cell": 1},
        "metadata_only_by_source_family": {"XLSX": 1},
        "vectorization_policy": {
            "current_index_vectorizes_all_source_atoms": False,
            "index_time_metadata_only_supported": True,
        },
    }
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    normalized_manifest_hash = "sha256:" + hashlib.sha256(
        json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    file_bytes_hash = "sha256:" + hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert file_bytes_hash != normalized_manifest_hash

    config_path = tmp_path / "weaviate_route_selected_candidate_surface_v1.json"
    config_path.write_text(
        json.dumps(
            {
                "selection": "route_selected_candidate_surface_v1",
                "vector_db": "weaviate",
                "collection": "SourceAtomNonprodRouteSelectedCandidateSurfaceV1",
                "namespace": "actual_rag_eval_nonprod",
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "retrieval_route_mode": "route_selected",
                "index_manifest_path": manifest_path.as_posix(),
                "fallback_used": False,
                "fail_closed_on_unavailable": True,
                "candidate_surface_rebuild": {
                    "schema_version": "actual_rag_eval.candidate_surface_rebuild.v1",
                    "report_only_diagnostic": True,
                    "source_collection": "SourceAtomNonprodRouteSelectedV2",
                },
                "rollback": {
                    "rollback_key": "weaviate_full_index_nonprod_rollback",
                    "config_path": "ai/eval/configs/weaviate_full_index_nonprod_rollback.json",
                    "retrieval_route_mode": "full_index",
                    "collection": "SourceAtomNonprod",
                    "schema_version_source_atom": "weaviate_source_atom_v1",
                    "index_manifest_path": "reports/rag_eval/weaviate_source_atom_index_manifest_nonprod/index_manifest.json",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        config_path=config_path.as_posix(),
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    report = adapter.active_path_report
    candidate_surface = report["candidate_surface_rebuild"]

    assert candidate_surface["index_manifest_path"] == manifest_path.as_posix()
    assert candidate_surface["index_manifest_sha256"] == file_bytes_hash
    assert candidate_surface["index_manifest_sha256"] != normalized_manifest_hash
    assert candidate_surface["axis_materialization_summary"]["metadata_only_by_source_family"] == {"XLSX": 1}


def test_weaviate_full_index_rollback_config_path_is_preserved() -> None:
    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        config_path="ai/eval/configs/weaviate_full_index_nonprod_rollback.json",
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    config_report = adapter.config["weaviate_default_config"]

    assert adapter.retrieval_route_mode == "full_index"
    assert adapter.config_obj.collection_name == "SourceAtomNonprod"
    assert adapter.config_obj.schema_version == "weaviate_source_atom_v1"
    assert config_report["selection"] == "weaviate_full_index_nonprod_rollback"
    assert config_report["rollback_key"] == "weaviate_full_index_nonprod_rollback"
    assert config_report["fallback_used"] is False
    assert config_report["fail_closed_on_unavailable"] is True


def test_weaviate_full_index_route_mode_uses_rollback_even_when_default_config_env_is_route_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ACTUAL_RAG_EVAL_WEAVIATE_CONFIG_PATH",
        "ai/eval/configs/weaviate_route_selected_nonprod_default.json",
    )

    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="full_index",
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    config_report = adapter.config["weaviate_default_config"]

    assert adapter.retrieval_route_mode == "full_index"
    assert adapter.config_obj.collection_name == "SourceAtomNonprod"
    assert adapter.config_obj.schema_version == "weaviate_source_atom_v1"
    assert config_report["selection"] == "weaviate_full_index_nonprod_rollback"
    assert config_report["config_path"].endswith("ai/eval/configs/weaviate_full_index_nonprod_rollback.json")
    assert config_report["fallback_used"] is False
    assert config_report["fail_closed_on_unavailable"] is True


def test_weaviate_route_selected_default_report_records_config_path_filters_and_no_fallback(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_route_selected_default"
    manifest_path = tmp_path / "weaviate_source_atom_route_selected_v2_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "valid": True,
                "schema_version_source_atom": "weaviate_source_atom_v2",
                "index_object_count": 2,
                "indexed_count": 2,
                "route_taxonomy_available": True,
                "route_taxonomy_filterable_fields": ["source_family", "granularity", "retrieval_route"],
                "schema_index_v2_rebuild_required_for_metadata_only_policy": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    config_data = json.loads(Path("ai/eval/configs/weaviate_route_selected_nonprod_default.json").read_text(encoding="utf-8"))
    config_data["index_manifest_path"] = manifest_path.as_posix()
    config_path = tmp_path / "weaviate_route_selected_nonprod_default.json"
    config_path.write_text(json.dumps(config_data, ensure_ascii=False), encoding="utf-8")
    write_jsonl(dataset, [{"id": "q1", "query": "2020년 11월 sheet cell row amount 승인 금액은?", "answerability": "unknown"}])
    client = FakeWeaviateSourceAtomClient(
        objects=[
            {
                **weaviate_source_atom_record(1, text="TEXT Project Orion launch is scheduled for April 2026."),
                "granularity": "paragraph",
                "retrieval_route": "text_general",
            },
            {
                **weaviate_source_atom_record(2, text="XLSX approved amount cell is 15446522."),
                "source_family": "XLSX",
                "granularity": "table_row",
                "retrieval_route": "xlsx_table",
            },
        ]
    )
    adapter = build_default_weaviate_adapter(
        requested_backend="weaviate-hybrid",
        config_path=config_path.as_posix(),
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=5,
        run_id="weaviate_route_selected_default",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    assert report["active_retrieval_backend"] == "weaviate_hybrid"
    assert report["active_retrieval_service_boundary"] == "weaviate"
    assert report["collection"] == "SourceAtomNonprodRouteSelectedV2"
    assert report["schema_version_source_atom"] == "weaviate_source_atom_v2"
    assert report["route_planner_version"] == "weaviate_route_planner_v1"
    assert report["fallback_used"] is False
    assert report["fail_closed_on_unavailable"] is True
    assert report["route_filters_sent_to_weaviate"]["source_family"] == "XLSX"
    assert report["route_filters_sent_to_weaviate"]["granularity"] == ["table_summary", "table_row", "cell"]
    assert report["route_filters_sent_to_weaviate"]["retrieval_route"] == "xlsx_table"
    assert report["weaviate_filter_policy"]["python_post_filtering"] == "safety_validation_only"
    assert report["weaviate_default_config"]["selection"] == "route_selected_nonprod_default"
    assert report["weaviate_default_config"]["config_path"] == config_path.as_posix()
    assert report["weaviate_default_config"]["index_manifest_path"] == manifest_path.as_posix()
    assert report["weaviate_index_manifest_path"] == manifest_path.as_posix()
    assert report["weaviate_default_config"]["explicit_nonprod_config_path"] is True
    assert report["rollback_key"] == "weaviate_full_index_nonprod_rollback"
    assert report["rollback_config"]["collection"] == "SourceAtomNonprod"
    assert report["promotion_decision"] in {"promote_route_selected_nonprod_default", "blocked_keep_full_index_rollback"}
    assert isinstance(report["promotion_blockers"], list)
    assert report["residual_risks"]
    assert report["next_recommended_goal"] == "selected_evidence_answer_composer_citation_formatter_nonprod"
    assert report["python_local_corpus_scan_used_for_candidate_generation"] is False
    assert report["source_native_layered_retrieval_used_for_candidate_generation"] is False
    assert report["diagnostic_hash_vector_used"] is False
    assert report["faiss_used_for_active_retrieval"] is False
    assert report["searchunit_searchview_used_as_candidate_surface"] is False
    assert report["external_vector_db"]["invoked"] is True
    assert report["external_vector_db"]["production_namespace"] is False
    assert all(query["filters"]["source_family"] == "XLSX" for query in client.query_log)
    assert all(query["filters"]["granularity"] == ["table_summary", "table_row", "cell"] for query in client.query_log)
    assert all(query["filters"]["retrieval_route"] == "xlsx_table" for query in client.query_log)


def test_weaviate_v2_indexer_keeps_cells_metadata_only_without_embedding() -> None:
    class CountingBgeM3Provider(FakeWeaviateBgeM3EmbeddingProvider):
        def __init__(self) -> None:
            self.embedded_texts: list[str] = []

        def embed_passages(self, texts: list[str]) -> object:
            self.embedded_texts.extend(texts)
            return super().embed_passages(texts)

    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    provider = CountingBgeM3Provider()
    client = FakeWeaviateSourceAtomClient()
    indexer = WeaviateSourceAtomIndexer(
        config=config,
        client=client,
        embedding_builder=BgeM3EmbeddingBuilder(
            model_name="BAAI/bge-m3",
            batch_size=2,
            embedding_provider=provider,
        ),
    )
    paragraph = weaviate_source_atom_record(1, text="Project Orion launch is scheduled for April 2026.")
    xlsx_cell = weaviate_source_atom_record(
        2,
        text="workbook=Budget.xlsx | sheet=Approvals | cell=B2 | amount=42",
    )
    xlsx_cell["source_family"] = "XLSX"

    manifest = indexer.index_records([paragraph, xlsx_cell])

    assert provider.embedded_texts == [paragraph["text"]]
    assert manifest["schema_version_source_atom"] == "weaviate_source_atom_v2"
    assert manifest["index_object_count"] == 2
    assert manifest["indexed_count"] == 2
    assert manifest["vectorized_object_count"] == 1
    assert manifest["metadata_only_object_count"] == 1
    assert manifest["vectorized_object_ratio"] == 0.5
    assert manifest["vectorized_by_granularity"] == {"paragraph": 1}
    assert manifest["metadata_only_by_granularity"] == {"cell": 1}
    assert manifest["schema_index_v2_rebuild_required_for_metadata_only_policy"] is False
    assert manifest["vectorization_policy"]["current_index_vectorizes_all_source_atoms"] is False
    assert len(client.upsert_log) == 1
    assert client.upsert_log[0]["objects"][0]["source_atom_id"] == paragraph["source_atom_id"]
    assert len(client.metadata_only_upsert_log) == 1
    assert client.metadata_only_upsert_log[0]["objects"][0]["source_atom_id"] == xlsx_cell["source_atom_id"]
    assert {obj["source_atom_id"]: obj["_vector_dim"] for obj in client.objects} == {
        paragraph["source_atom_id"]: 4,
        xlsx_cell["source_atom_id"]: 0,
    }


def test_xlsx_source_atom_materializes_general_table_axes_for_vector_db() -> None:
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
        }
    )
    record = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                501,
                text="sheet=2019년 2월 | row_label=5호선 | column_label=승차총승객수 | value=15,446,522명",
            ),
            "source_family": "XLSX",
            "granularity": "table_row",
            "retrieval_route": "xlsx_table",
            "sheet": "2019년 2월",
            "cell_range": "A7:J7",
            "cell": "F7",
            "row_index_1based": 7,
            "row_label": "5호선",
            "column_label": "승차총승객수",
            "target_column": "승차총승객수",
            "header": "승차총승객수",
            "header_path": "승하차 > 승차총승객수",
            "table_id": "sheet-201902-main-table",
            "display_value": "15,446,522명",
            "locator_fingerprint": "xlsx-locator-fp",
        },
        config,
    )
    schema = build_weaviate_source_atom_schema(config)
    properties = {prop["name"]: prop for prop in schema["properties"]}

    for field in (
        "sheet",
        "cell_range",
        "cell",
        "row_index_1based",
        "row_label",
        "column_label",
        "target_column",
        "header",
        "header_path",
        "table_id",
        "display_value",
        "locator_fingerprint",
    ):
        assert record[field]
        assert properties[field]["index_filterable"] is True
    assert "formula" not in record
    assert "normalized_value" not in record


def test_xlsx_source_atom_record_materializes_source_owned_tags_without_value_or_file_shortcuts() -> None:
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
        }
    )
    record = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                503,
                text=(
                    "Sheet=2019년 2월 | RANGE=A7:J7 | Cell=F7 | Row_Label=5호선 | "
                    "Column_Label=승차총승객수 | TARGET_COLUMN=승차총승객수 | "
                    "Header_Path=승하차 > 승차총승객수 | Table_ID=subway-201902-main | "
                    "Display_Value=15,446,522명 | Value=15,446,522 | NORMALIZED_VALUE=15446522 | Formula==SUM(F7:F7) | "
                    "Source_Title=서울교통공사 승하차 workbook | Workbook_ID=subway-workbook | "
                    "Workbook_Version_ID=subway-workbook-v1 | Workbook=서울교통공사.xlsx | "
                    "Source_Workbook=서울교통공사-source.xlsx | Title=서울교통공사 shortcut title | "
                    "Source_Path=D:/private/subway.xlsx | File_Name=subway.xlsx"
                ),
            ),
            "source_family": "XLSX",
            "granularity": "table_row",
            "retrieval_route": "xlsx_table",
        },
        config,
    )

    assert record["sheet"] == "2019년 2월"
    assert record["cell_range"] == "A7:J7"
    assert record["cell"] == "F7"
    assert record["row_index_1based"] == "7"
    assert record["row_label"] == "5호선"
    assert record["column_label"] == "승차총승객수"
    assert record["target_column"] == "승차총승객수"
    assert record["header_path"] == "승하차 > 승차총승객수"
    assert record["table_id"] == "subway-201902-main"
    assert record["display_value"] == "15,446,522명"
    for forbidden in (
        "value",
        "normalized_value",
        "formula",
        "source_path",
        "source_file_name",
        "file_name",
    ):
        assert forbidden not in record
    searchable_text = record["text"]
    assert "Sheet=2019년 2월" in searchable_text
    assert "Cell=F7" in searchable_text
    assert "Value=15,446,522" in searchable_text
    assert "normalized_value" not in searchable_text
    assert "NORMALIZED_VALUE" not in searchable_text
    assert "15446522" not in searchable_text
    assert "formula" not in searchable_text
    assert "Formula" not in searchable_text
    assert "=SUM" not in searchable_text
    assert "source_path" not in searchable_text
    assert "Source_Path" not in searchable_text
    assert "file_name" not in searchable_text
    assert "File_Name" not in searchable_text
    assert "subway.xlsx" not in searchable_text
    assert "source_title" not in searchable_text
    assert "Source_Title" not in searchable_text
    assert "서울교통공사 승하차 workbook" not in searchable_text
    assert "workbook_id" not in searchable_text
    assert "Workbook_ID" not in searchable_text
    assert "subway-workbook" not in searchable_text
    assert "workbook_version_id" not in searchable_text
    assert "Workbook_Version_ID" not in searchable_text
    assert "workbook=서울교통공사.xlsx" not in searchable_text
    assert "Workbook=서울교통공사.xlsx" not in searchable_text
    assert "source_workbook" not in searchable_text
    assert "Source_Workbook" not in searchable_text
    assert "서울교통공사-source.xlsx" not in searchable_text
    assert "title=서울교통공사 shortcut title" not in searchable_text
    assert "Title=서울교통공사 shortcut title" not in searchable_text
    assert record["text_sha256"] == hashlib.sha256(searchable_text.encode("utf-8")).hexdigest()


def test_source_atom_record_materializes_semicolon_delimited_source_owned_tags_without_shortcuts() -> None:
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodRouteSelectedV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )

    record = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                988,
                text=(
                    "value=15,446,522명; sheet=2019년 2월; row_label=5호선; "
                    "column_label=승차총승객수; target_column=승차총승객수; "
                    "header_path=승하차 > 승차총승객수; table_id=subway-201902-main; "
                    "formula==SUM(F1:F6); source_file_name=D:/private/Subway.xlsx; "
                    "2019년 2월 5호선 승차총승객수는 15,446,522명입니다."
                ),
            ),
            "source_atom_id": "srcatom-semicolon-tags",
            "evidence_bundle_id": "bundle-semicolon-tags",
            "doc_id": "doc-subway",
            "chunk_id": "chunk-semicolon-tags",
            "source_family": "XLSX",
            "granularity": "table_row",
            "retrieval_route": "xlsx_table",
        },
        config,
    )

    assert record["sheet"] == "2019년 2월"
    assert record["row_label"] == "5호선"
    assert record["column_label"] == "승차총승객수"
    assert record["target_column"] == "승차총승객수"
    assert record["header_path"] == "승하차 > 승차총승객수"
    assert record["table_id"] == "subway-201902-main"
    assert "15,446,522명" in record["text"]
    assert "=SUM" not in record["text"]
    assert "D:/private/Subway.xlsx" not in record["text"]


def test_xlsx_pdf_query_properties_exclude_title_shortcut_when_family_filtered() -> None:
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
        }
    )
    client = WeaviateSourceAtomClient(config)

    assert client._query_properties_for_filters({"source_family": "XLSX"}) == ["text"]
    assert client._query_properties_for_filters({"source_family": ["PDF"]}) == ["text"]
    assert client._query_properties_for_filters({"source_family": ["XLSX", "PDF"]}) == ["text"]
    assert client._query_properties_for_filters({"source_family": ["TEXT", "PDF", "XLSX"]}) == ["text"]
    assert client._query_properties_for_filters({}) == ["text"]
    assert client._query_properties_for_filters({"source_family": "TEXT"}) == ["text", "title"]


def test_weaviate_bm25_and_hybrid_mixed_family_filters_pass_text_only_query_properties() -> None:
    class SpyResponse:
        objects: list[object] = []

    class SpyQuery:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def bm25(self, **kwargs: object) -> SpyResponse:
            self.calls.append({"method": "bm25", **kwargs})
            return SpyResponse()

        def hybrid(self, **kwargs: object) -> SpyResponse:
            self.calls.append({"method": "hybrid", **kwargs})
            return SpyResponse()

    class SpyCollection:
        def __init__(self) -> None:
            self.query = SpyQuery()

    class SpyWeaviateSourceAtomClient(WeaviateSourceAtomClient):
        def __init__(self, config: WeaviateSourceAtomConfig, collection: SpyCollection) -> None:
            super().__init__(config)
            self._spy_collection = collection

        def _use_collection(self) -> SpyCollection:
            return self._spy_collection

        def _filters(self, filters: Mapping[str, object]) -> dict[str, object]:
            return dict(filters)

        def _metadata_query(self, *, mode: str) -> dict[str, str]:
            return {"mode": mode}

    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
        }
    )
    collection = SpyCollection()
    client = SpyWeaviateSourceAtomClient(config, collection)
    filters = {"source_family": ["TEXT", "PDF", "XLSX"], "namespace": "actual_rag_eval_nonprod"}

    client.query(mode="bm25", query_text="ambiguous document query", query_vector=None, filters=filters, limit=3, alpha=0.5)
    client.query(mode="hybrid", query_text="ambiguous document query", query_vector=[0.1, 0.2], filters=filters, limit=3, alpha=0.5)

    assert [call["method"] for call in collection.query.calls] == ["bm25", "hybrid"]
    assert all(call["query_properties"] == ["text"] for call in collection.query.calls)


def test_normalize_citation_preserves_source_native_axes_without_shortcuts() -> None:
    citation = actual_rag_eval._normalize_citation(
        {
            "doc_id": "doc-xlsx",
            "chunk_id": "chunk-1",
            "text": "value=15,446,522",
            "source_atom_id": "srcatom-xlsx-1",
            "evidence_bundle_id": "bundle-1",
            "sheet": "2019년 2월",
            "cell_range": "A7:J7",
            "cell": "F7",
            "row_index_1based": "7",
            "row_label": "5호선",
            "column_label": "승차총승객수",
            "target_column": "승차총승객수",
            "header_path": "승하차 > 승차총승객수",
            "table_id": "subway-201902-main",
            "source_title": "서울교통공사 shortcut title",
            "workbook": "서울교통공사.xlsx",
            "file_name": "subway.xlsx",
            "normalized_value": "15446522",
            "formula": "=SUM(F7)",
        }
    )

    for field in (
        "sheet",
        "cell_range",
        "cell",
        "row_index_1based",
        "row_label",
        "column_label",
        "target_column",
        "header_path",
        "table_id",
    ):
        assert citation[field]
    for forbidden in ("source_title", "workbook", "file_name", "normalized_value", "formula"):
        assert forbidden not in citation


def test_xlsx_vector_db_query_uses_query_text_and_source_axes_without_value_shortcut(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "xlsx_query.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_vector_axes"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx-axis-query",
                "query": "2019년 2월 5호선 승차총승객수는 얼마야?",
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            }
        ],
    )
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
        }
    )
    record = {
        **weaviate_source_atom_record(
            601,
            text=(
                "2019년 2월 지하철 5호선 row_label=5호선 "
                "column_label=승차총승객수 value=15,446,522명"
            ),
        ),
        "source_family": "XLSX",
        "granularity": "table_row",
        "retrieval_route": "xlsx_table",
        "sheet": "2019년 2월",
        "cell_range": "A7:J7",
        "cell": "F7",
        "row_index_1based": "7",
        "row_label": "5호선",
        "column_label": "승차총승객수",
        "target_column": "승차총승객수",
        "header_path": "승하차 > 승차총승객수",
        "table_id": "sheet-201902-main-table",
        "locator_fingerprint": "xlsx-locator-fp",
    }
    client = FakeWeaviateSourceAtomClient(objects=[source_atom_record_from_mapping(record, config)])
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="route_selected",
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=3,
        run_id="xlsx_vector_axes",
        output_mode="single",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="markdown-portfolio",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    context = row["retrieved_contexts"][0]
    selected = row["evidence_gate"]["selected_evidence"][0]
    assert context["row_label"] == "5호선"
    assert context["column_label"] == "승차총승객수"
    assert context["header_path"] == "승하차 > 승차총승객수"
    assert context["table_id"] == "sheet-201902-main-table"
    assert selected["row_label"] == "5호선"
    assert selected["column_label"] == "승차총승객수"
    assert report["evidence_gate"]["allowed_answer_count"] == 1
    primary_queries = [query for query in client.query_log if query["mode"] != "neighbor_by_id"]
    assert primary_queries
    assert all(query["query_text"] for query in primary_queries)
    query_payload = json.dumps(client.query_log, ensure_ascii=False)
    assert "15,446,522" not in query_payload
    assert "normalized_value" not in query_payload
    assert "formula" not in query_payload
    assert "expected_answer" not in query_payload
    assert "qrels" not in query_payload
    assert "labels" not in query_payload
    assert "row_id" not in query_payload
    assert output_file_names(output_dir) == ["report.json"]


def test_pdf_source_atom_materializes_page_section_table_axes_for_vector_db() -> None:
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
        }
    )
    record = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                801,
                text=(
                    "page=7 | section_title=연결 손익계산서 | table_caption=영업실적 표 | "
                    "row_label=영업이익 | column_label=2024년 | value=12.3억원"
                ),
            ),
            "source_family": "PDF",
            "granularity": "table_row",
            "retrieval_route": "pdf_table",
            "page_number": 7,
            "physical_page_index": 6,
            "block_index": 14,
            "bbox": [72.0, 260.0, 510.0, 318.0],
            "region_type": "table",
            "section_title": "연결 손익계산서",
            "table_caption": "영업실적 표",
            "row_label": "영업이익",
            "column_label": "2024년",
            "locator_fingerprint": "pdf-locator-fp",
            "source_file_name": "do-not-use-file-name-shortcut.pdf",
            "file_name": "do-not-use-file-name-shortcut.pdf",
        },
        config,
    )
    schema = build_weaviate_source_atom_schema(config)
    properties = {prop["name"]: prop for prop in schema["properties"]}

    assert record["source_family"] == "PDF"
    filterable_fields = (
        "page_number",
        "physical_page_index",
        "block_index",
        "region_type",
        "section_title",
        "table_caption",
        "row_label",
        "column_label",
        "locator_fingerprint",
    )
    for field in filterable_fields:
        assert record[field]
        assert properties[field]["index_filterable"] is True
    assert record["bbox"]
    assert properties["bbox"]["index_filterable"] is False
    serialized = json.dumps(record, ensure_ascii=False)
    assert "source_file_name" not in serialized
    assert "file_name" not in serialized
    assert "do-not-use-file-name-shortcut" not in serialized


def test_pdf_source_atom_record_materializes_source_owned_tags_without_file_shortcuts() -> None:
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
        }
    )
    record = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                804,
                text=(
                    "Page=7 | Physical_Page_Index=6 | Block_Index=14 | Region_Type=table | "
                    "Section_Title=연결 손익계산서 | Table_Caption=영업실적 표 | "
                    "Row_Label=영업이익 | Column_Label=2024년 | BBox=[72,260,510,318] | "
                    "Value=12.3억원 | File_Name=do-not-use-file-name-shortcut.pdf | "
                    "Source_File_Name=do-not-use-source-file-shortcut.pdf"
                ),
            ),
            "source_family": "PDF",
            "granularity": "table_row",
            "retrieval_route": "pdf_table",
        },
        config,
    )

    assert record["page_number"] == "7"
    assert record["physical_page_index"] == "6"
    assert record["block_index"] == "14"
    assert record["region_type"] == "table"
    assert record["section_title"] == "연결 손익계산서"
    assert record["table_caption"] == "영업실적 표"
    assert record["row_label"] == "영업이익"
    assert record["column_label"] == "2024년"
    assert record["bbox"] == "[72,260,510,318]"
    assert "value" not in record
    assert "file_name" not in record
    assert "source_file_name" not in record
    searchable_text = record["text"]
    assert "Value=12.3억원" in searchable_text
    assert "File_Name" not in searchable_text
    assert "Source_File_Name" not in searchable_text
    assert "do-not-use-file-name-shortcut" not in searchable_text
    assert "do-not-use-source-file-shortcut" not in searchable_text


def test_pdf_vector_db_query_uses_page_section_caption_axes_without_filename_shortcut(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "pdf_query.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "pdf_vector_axes"
    write_jsonl(
        dataset,
        [
            {
                "id": "pdf-axis-query",
                "query": "2024년 연결 손익계산서 영업이익은 얼마야?",
                "answerability": "answerable",
                "track": "pdf_business_ocr_mm",
            }
        ],
    )
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
        }
    )
    record = {
        **weaviate_source_atom_record(
            802,
            text=(
                "2024년 연결 손익계산서 영업실적 표에서 "
                "영업이익 row_label=영업이익 column_label=2024년 value=12.3억원"
            ),
        ),
        "source_family": "PDF",
        "granularity": "table_row",
        "retrieval_route": "pdf_table",
        "title": "do-not-use-title-shortcut-999억원.pdf",
        "page_number": "7",
        "physical_page_index": "6",
        "block_index": "14",
        "bbox": "[72.0,260.0,510.0,318.0]",
        "region_type": "table",
        "section_title": "연결 손익계산서",
        "table_caption": "영업실적 표",
        "row_label": "영업이익",
        "column_label": "2024년",
        "locator_fingerprint": "pdf-locator-fp",
        "source_file_name": "do-not-use-file-name-shortcut-999억원.pdf",
        "file_name": "do-not-use-file-name-shortcut-999억원.pdf",
    }
    client = FakeWeaviateSourceAtomClient(objects=[source_atom_record_from_mapping(record, config)])
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="route_selected",
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=3,
        run_id="pdf_vector_axes",
        output_mode="single",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="markdown-portfolio",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    context = row["retrieved_contexts"][0]
    selected = row["evidence_gate"]["selected_evidence"][0]
    assert context["page_number"] == "7"
    assert context["section_title"] == "연결 손익계산서"
    assert context["table_caption"] == "영업실적 표"
    assert context["row_label"] == "영업이익"
    assert context["column_label"] == "2024년"
    assert selected["page_number"] == "7"
    assert selected["section_title"] == "연결 손익계산서"
    assert selected["table_caption"] == "영업실적 표"
    metadata_text, metadata_fields = actual_rag_eval.source_derived_evidence_metadata(selected)
    assert "page_number=7" in metadata_text
    assert "section_title=연결 손익계산서" in metadata_text
    assert "table_caption=영업실적 표" in metadata_text
    assert "title" not in metadata_fields
    assert "file_name" not in metadata_fields
    assert "source_file_name" not in metadata_fields
    assert report["evidence_gate"]["allowed_answer_count"] == 1
    primary_queries = [query for query in client.query_log if query["mode"] != "neighbor_by_id"]
    assert primary_queries
    assert all(query["query_text"] for query in primary_queries)
    query_payload = json.dumps(client.query_log, ensure_ascii=False)
    assert "12.3억원" not in query_payload
    assert "999억원" not in query_payload
    assert "do-not-use-title-shortcut" not in query_payload
    assert "do-not-use-file-name-shortcut" not in query_payload
    assert "expected_answer" not in query_payload
    assert "expected_evidence" not in query_payload
    assert "qrels" not in query_payload
    assert "labels" not in query_payload
    assert "row_id" not in query_payload
    assert output_file_names(output_dir) == ["report.json"]


def test_pdf_same_page_or_section_vector_expansion_is_bounded_by_source_owned_scope(tmp_path: Path) -> None:
    class SamePageSensitiveWeaviateClient(FakeWeaviateSourceAtomClient):
        def query(self, **kwargs: object) -> list[dict]:
            self.query_log.append(
                {
                    "mode": kwargs["mode"],
                    "query_text": kwargs["query_text"],
                    "vector_dim": len(kwargs.get("query_vector") or []),
                    "filters": dict(kwargs["filters"]),
                    "limit": int(kwargs["limit"]),
                    "alpha": float(kwargs["alpha"]),
                }
            )
            filters = dict(kwargs["filters"])
            scoped = (
                filters.get("source_family") == "PDF"
                and filters.get("doc_id") == "doc-financial"
                and filters.get("page_number") == "7"
                and filters.get("table_caption") == "영업실적 표"
            )
            rows: list[dict] = []
            for obj in self.objects:
                if _filter_mismatch(obj, filters):
                    continue
                source_atom_id = obj.get("source_atom_id")
                if scoped and source_atom_id == "srcatom-financial-operating-profit":
                    row = dict(obj)
                    row["_score"] = 1.0
                    row["_backend"] = kwargs["mode"]
                    rows.append(row)
                elif not scoped and source_atom_id == "srcatom-financial-table-summary":
                    row = dict(obj)
                    row["_score"] = 1.0
                    row["_backend"] = kwargs["mode"]
                    rows.append(row)
            return rows[: int(kwargs["limit"])]

    def _filter_mismatch(obj: dict, filters: dict) -> bool:
        for key, value in filters.items():
            if not value:
                continue
            if isinstance(value, list):
                if obj.get(key) not in value:
                    return True
            elif obj.get(key) != value:
                return True
        return False

    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "pdf_same_page_scope"
    write_jsonl(
        dataset,
        [
            {
                "id": "pdf-same-page",
                "query": "2024년 보고서 도표 연결 손익계산서 영업이익은 얼마야?",
                "answerability": "answerable",
            }
        ],
    )
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodRouteSelectedV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    summary = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                811,
                text="2024년 보고서 연결 손익계산서 영업실적 표는 주요 손익 항목을 제공한다.",
            ),
            "source_atom_id": "srcatom-financial-table-summary",
            "evidence_bundle_id": "bundle-financial-table-summary",
            "doc_id": "doc-financial",
            "chunk_id": "chunk-financial-table-summary",
            "source_family": "PDF",
            "granularity": "table_summary",
            "retrieval_route": "pdf_table",
            "page_number": "7",
            "section_title": "연결 손익계산서",
            "table_caption": "영업실적 표",
        },
        config,
    )
    target = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                812,
                text="2024년 연결 손익계산서 영업실적 표에서 영업이익은 12.3억원입니다.",
            ),
            "source_atom_id": "srcatom-financial-operating-profit",
            "evidence_bundle_id": "bundle-financial-operating-profit",
            "doc_id": "doc-financial",
            "chunk_id": "chunk-financial-operating-profit",
            "source_family": "PDF",
            "granularity": "table_row",
            "retrieval_route": "pdf_table",
            "page_number": "7",
            "physical_page_index": "6",
            "block_index": "14",
            "bbox": "[72.0,260.0,510.0,318.0]",
            "region_type": "table",
            "section_title": "연결 손익계산서",
            "table_caption": "영업실적 표",
            "row_label": "영업이익",
            "column_label": "2024년",
            "locator_fingerprint": "pdf-locator-fp",
        },
        config,
    )
    wrong_page = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                813,
                text="2024년 다른 페이지 영업이익은 12.3억원입니다.",
            ),
            "source_atom_id": "srcatom-financial-wrong-page",
            "evidence_bundle_id": "bundle-financial-wrong-page",
            "doc_id": "doc-financial",
            "chunk_id": "chunk-financial-wrong-page",
            "source_family": "PDF",
            "granularity": "table_row",
            "retrieval_route": "pdf_table",
            "page_number": "9",
            "section_title": "별도 손익계산서",
            "table_caption": "영업실적 표",
            "row_label": "영업이익",
            "column_label": "2024년",
        },
        config,
    )
    client = SamePageSensitiveWeaviateClient(objects=[summary, target, wrong_page])
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="route_selected",
        route_filter_fields_available={"source_family": True, "granularity": True, "retrieval_route": True},
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=5,
        run_id="pdf_same_page_scope",
        output_mode="single",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="markdown-portfolio",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    contexts = report["items"][0]["retrieved_contexts"]
    scoped_queries = [
        query
        for query in client.query_log
        if query["filters"].get("doc_id") == "doc-financial"
        and query["filters"].get("page_number") == "7"
        and query["filters"].get("table_caption") == "영업실적 표"
    ]
    assert scoped_queries
    assert contexts[0]["source_atom_id"] == "srcatom-financial-operating-profit"
    assert contexts[0]["pdf_scoped_expansion_policy"] == "bounded_source_owned_pdf_scope_weaviate_v1"
    assert contexts[0]["pdf_scoped_expansion_scope_type"] == "same_table"
    assert all(query["filters"]["source_family"] == "PDF" for query in scoped_queries)
    assert all(query["filters"]["page_number"] == "7" for query in scoped_queries)
    assert report["items"][0]["weaviate_pdf_scoped_expansion"]["added_count"] == 1
    assert report["items"][0]["weaviate_pdf_scoped_expansion"]["uses_ids"] is False
    assert report["items"][0]["weaviate_pdf_scoped_expansion"]["uses_protected_eval_ids"] is False
    assert report["items"][0]["weaviate_pdf_scoped_expansion"]["uses_source_owned_scope_ids"] is True
    assert report["weaviate_post_processing"]["pdf_scoped_expansion_added_count"] == 1
    query_payload = json.dumps(client.query_log, ensure_ascii=False)
    assert "12.3억원" not in query_payload
    assert "expected_answer" not in query_payload
    assert "expected_evidence" not in query_payload
    assert "qrels" not in query_payload
    assert "labels" not in query_payload
    assert "row_id" not in query_payload
    assert "target_id" not in query_payload
    assert output_file_names(output_dir) == ["report.json"]


def test_pdf_scoped_expansion_anchor_survives_route_selected_doc_cap_collapse() -> None:
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodRouteSelectedV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=FakeWeaviateSourceAtomClient(),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="route_selected",
        route_filter_fields_available={"source_family": True, "granularity": True, "retrieval_route": True},
    )
    summary = {
        "source_atom_id": "srcatom-financial-table-summary",
        "doc_id": "doc-financial",
        "chunk_id": "chunk-financial-table-summary",
        "source_family": "PDF",
        "granularity": "table_summary",
        "retrieval_route": "pdf_table",
        "text": "2024년 보고서 연결 손익계산서 영업실적 표는 주요 손익 항목을 제공한다.",
        "page_number": "7",
        "table_caption": "영업실적 표",
        "score": 0.91,
    }
    scoped_target = {
        "source_atom_id": "srcatom-financial-operating-profit",
        "doc_id": "doc-financial",
        "chunk_id": "chunk-financial-operating-profit",
        "source_family": "PDF",
        "granularity": "table_row",
        "retrieval_route": "pdf_table",
        "text": "2024년 연결 손익계산서 영업실적 표에서 영업이익은 12.3억원입니다.",
        "page_number": "7",
        "physical_page_index": "6",
        "block_index": "14",
        "bbox": "[72.0,260.0,510.0,318.0]",
        "region_type": "table",
        "table_caption": "영업실적 표",
        "row_label": "영업이익",
        "column_label": "2024년",
        "pdf_scoped_expansion_policy": "bounded_source_owned_pdf_scope_weaviate_v1",
        "pdf_scoped_expansion_scope_type": "same_table",
        "pdf_scoped_expansion_source_atom_id": "srcatom-financial-table-summary",
        "score": 0.87,
    }

    collapsed, _removed = adapter._collapse_route_selected_duplicates(
        [summary, scoped_target],
        top_k=5,
    )

    assert [context["source_atom_id"] for context in collapsed] == [
        "srcatom-financial-table-summary",
        "srcatom-financial-operating-profit",
    ]


def test_pdf_scoped_expansion_query_uses_source_owned_axis_terms(tmp_path: Path) -> None:
    class AxisSensitiveWeaviateClient(FakeWeaviateSourceAtomClient):
        def query(self, **kwargs: object) -> list[dict]:
            self.query_log.append(
                {
                    "mode": kwargs["mode"],
                    "query_text": kwargs["query_text"],
                    "vector_dim": len(kwargs.get("query_vector") or []),
                    "filters": dict(kwargs["filters"]),
                    "limit": int(kwargs["limit"]),
                    "alpha": float(kwargs["alpha"]),
                }
            )
            filters = dict(kwargs["filters"])
            query_text = str(kwargs["query_text"])
            scoped = (
                filters.get("source_family") == "PDF"
                and filters.get("doc_id") == "doc-financial"
                and filters.get("page_number") == "7"
                and filters.get("table_caption") == "영업실적 표"
            )
            rows: list[dict] = []
            for obj in self.objects:
                if _filter_mismatch(obj, filters):
                    continue
                source_atom_id = obj.get("source_atom_id")
                if scoped and source_atom_id == "srcatom-financial-operating-profit":
                    if "영업이익" not in query_text:
                        continue
                    row = dict(obj)
                    row["_score"] = 1.0
                    row["_backend"] = kwargs["mode"]
                    rows.append(row)
                elif not scoped and source_atom_id == "srcatom-financial-table-summary":
                    row = dict(obj)
                    row["_score"] = 1.0
                    row["_backend"] = kwargs["mode"]
                    rows.append(row)
            return rows[: int(kwargs["limit"])]

    def _filter_mismatch(obj: dict, filters: dict) -> bool:
        for key, value in filters.items():
            if not value:
                continue
            if isinstance(value, list):
                if obj.get(key) not in value:
                    return True
            elif obj.get(key) != value:
                return True
        return False

    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "pdf_source_axis_scope"
    write_jsonl(
        dataset,
        [
            {
                "id": "pdf-source-axis-scope",
                "query": "2024년 보고서 도표 해당 항목 금액은 얼마야?",
                "answerability": "answerable",
            }
        ],
    )
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodRouteSelectedV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    summary = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                814,
                text="2024년 보고서 연결 손익계산서 영업실적 표는 주요 항목의 금액을 제공한다.",
            ),
            "source_atom_id": "srcatom-financial-table-summary",
            "evidence_bundle_id": "bundle-financial-table-summary",
            "doc_id": "doc-financial",
            "chunk_id": "chunk-financial-table-summary",
            "source_family": "PDF",
            "granularity": "table_summary",
            "retrieval_route": "pdf_table",
            "page_number": "7",
            "section_title": "연결 손익계산서",
            "table_caption": "영업실적 표",
            "row_label": "영업이익",
            "column_label": "2024년",
        },
        config,
    )
    target = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                815,
                text="2024년 연결 손익계산서 영업실적 표에서 영업이익은 12.3억원입니다.",
            ),
            "source_atom_id": "srcatom-financial-operating-profit",
            "evidence_bundle_id": "bundle-financial-operating-profit",
            "doc_id": "doc-financial",
            "chunk_id": "chunk-financial-operating-profit",
            "source_family": "PDF",
            "granularity": "table_row",
            "retrieval_route": "pdf_table",
            "page_number": "7",
            "physical_page_index": "6",
            "block_index": "14",
            "bbox": "[72.0,260.0,510.0,318.0]",
            "region_type": "table",
            "section_title": "연결 손익계산서",
            "table_caption": "영업실적 표",
            "row_label": "영업이익",
            "column_label": "2024년",
            "locator_fingerprint": "pdf-locator-fp",
        },
        config,
    )
    client = AxisSensitiveWeaviateClient(objects=[summary, target])
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="route_selected",
        route_filter_fields_available={"source_family": True, "granularity": True, "retrieval_route": True},
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=5,
        run_id="pdf_source_axis_scope",
        output_mode="single",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="markdown-portfolio",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    contexts = report["items"][0]["retrieved_contexts"]
    scoped_queries = [
        query
        for query in client.query_log
        if query["filters"].get("doc_id") == "doc-financial"
        and query["filters"].get("page_number") == "7"
        and query["filters"].get("table_caption") == "영업실적 표"
    ]
    assert scoped_queries
    assert contexts[0]["source_atom_id"] == "srcatom-financial-operating-profit"
    assert any("영업이익" in query["query_text"] for query in scoped_queries)
    query_payload = json.dumps(client.query_log, ensure_ascii=False)
    assert "12.3억원" not in query_payload
    assert "expected_answer" not in query_payload
    assert "expected_evidence" not in query_payload
    assert "qrels" not in query_payload
    assert "labels" not in query_payload
    assert "row_id" not in query_payload
    assert "target_id" not in query_payload
    assert output_file_names(output_dir) == ["report.json"]


def test_pdf_selected_evidence_requires_value_and_page_section_axes_to_cooccur() -> None:
    selected = select_composer_evidence(
        "2024년 보고서 도표 연결 손익계산서 영업이익은 얼마야?",
        [
            {
                "doc_id": "doc-pdf",
                "chunk_id": "chunk-value-only",
                "source_atom_id": "src-pdf-value-only",
                "evidence_bundle_id": "bundle-pdf-value-only",
                "source_family": "PDF",
                "granularity": "table_row",
                "text": "12.3억원",
            },
            {
                "doc_id": "doc-pdf",
                "chunk_id": "chunk-axis-only",
                "source_atom_id": "src-pdf-axis-only",
                "evidence_bundle_id": "bundle-pdf-axis-only",
                "source_family": "PDF",
                "granularity": "table_row",
                "text": "2024년 보고서 도표 연결 손익계산서 영업이익 행입니다.",
                "page_number": "7",
                "section_title": "연결 손익계산서",
                "table_caption": "영업실적 표",
                "row_label": "영업이익",
                "column_label": "2024년",
            },
            {
                "doc_id": "doc-pdf",
                "chunk_id": "chunk-value-axis",
                "source_atom_id": "src-pdf-value-axis",
                "evidence_bundle_id": "bundle-pdf-value-axis",
                "source_family": "PDF",
                "granularity": "table_row",
                "text": "2024년 연결 손익계산서 영업실적 표에서 영업이익은 12.3억원입니다.",
                "page_number": "7",
                "section_title": "연결 손익계산서",
                "table_caption": "영업실적 표",
                "row_label": "영업이익",
                "column_label": "2024년",
            },
        ],
    )

    assert [row["source_atom_id"] for row in selected] == ["src-pdf-value-axis"]


def test_weaviate_v2_streaming_indexer_checkpoints_metadata_only_without_embedding(tmp_path: Path) -> None:
    class CountingBgeM3Provider(FakeWeaviateBgeM3EmbeddingProvider):
        def __init__(self) -> None:
            self.embedded_texts: list[str] = []

        def embed_passages(self, texts: list[str]) -> object:
            self.embedded_texts.extend(texts)
            return super().embed_passages(texts)

    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    provider = CountingBgeM3Provider()
    client = FakeWeaviateSourceAtomClient()
    indexer = WeaviateSourceAtomIndexer(
        config=config,
        client=client,
        embedding_builder=BgeM3EmbeddingBuilder(
            model_name="BAAI/bge-m3",
            batch_size=2,
            embedding_provider=provider,
        ),
    )
    paragraph = weaviate_source_atom_record(1, text="Project Orion launch is scheduled for April 2026.")
    xlsx_cell = weaviate_source_atom_record(
        2,
        text="workbook=Budget.xlsx | sheet=Approvals | cell=B2 | amount=42",
    )
    xlsx_cell["source_family"] = "XLSX"
    checkpoint_path = tmp_path / "weaviate-source-atom-v2-checkpoint.json"

    manifest = indexer.index_records_streaming(
        iter([paragraph, xlsx_cell]),
        checkpoint_path=checkpoint_path,
        source_atom_registry_path="ai/eval/fixtures/source_atoms.jsonl",
    )
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    assert provider.embedded_texts == [paragraph["text"]]
    assert manifest["indexed_count"] == 2
    assert manifest["embedding_count_this_run"] == 1
    assert manifest["metadata_only_object_count"] == 1
    assert checkpoint["completed_count"] == 2
    assert checkpoint["metadata_only_object_count"] == 1
    assert set(checkpoint["completed_source_atom_ids"]) == {
        paragraph["source_atom_id"],
        xlsx_cell["source_atom_id"],
    }


def test_source_native_corpus_loader_preserves_structural_route_metadata(tmp_path: Path) -> None:
    manifest = tmp_path / "search_view_manifest.jsonl"
    write_jsonl(
        manifest,
        [
            {
                "source_atom_id": "srcatom-xlsx-1",
                "evidence_bundle_id": "bundle-xlsx-1",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-1",
                "bm25_text": "Workbook Budget.xlsx Sheet Approvals Range A2:D2 cell B2 amount 15446522",
                "embedding_text": "Workbook Budget.xlsx Sheet Approvals Range A2:D2 amount 15446522",
                "source_identity": "Budget.xlsx|Approvals|A2:D2|B2",
                "workbook_id": "workbook-budget",
                "workbook_version_id": "workbook-version-budget",
                "sheet": "Approvals",
                "range": "A2:D2",
                "cell": "B2",
                "row_index_1based": 2,
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
                "faiss_row_id": 7,
            }
        ],
    )

    loader = SourceNativeCorpusLoader(search_view_manifest_path=manifest, source_atom_registry_path=tmp_path / "atoms.jsonl")
    unit = loader.load_units()[0]
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    record = source_atom_record_from_mapping(unit, config)

    assert unit["metadata"]["sheet"] == "Approvals"
    assert unit["metadata"]["cell_range"] == "A2:D2"
    assert unit["metadata"]["cell"] == "B2"
    assert unit["metadata"]["row_index_1based"] == "2"
    assert "Budget.xlsx|Approvals|A2:D2|B2" not in json.dumps(unit, ensure_ascii=False)
    assert record["sheet"] == "Approvals"
    assert record["cell_range"] == "A2:D2"
    assert record["cell"] == "B2"
    assert record["row_index_1based"] == "2"


def test_source_native_corpus_loader_bridges_source_registry_structural_metadata_only(tmp_path: Path) -> None:
    manifest = tmp_path / "search_view_manifest.jsonl"
    registry = tmp_path / "source_atom_registry_v1.jsonl"
    write_jsonl(
        manifest,
        [
            {
                "source_atom_id": "srcatom-xlsx-registry-only",
                "evidence_bundle_id": "bundle-xlsx-registry-only",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-registry-only",
                "bm25_text": "Approved amount row summary.",
                "embedding_text": "Approved amount row summary.",
                "source_identity": "registry-only-source-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            }
        ],
    )
    write_jsonl(
        registry,
        [
            {
                "source_atom_id": "srcatom-xlsx-registry-only",
                "source_family": "XLSX",
                "workbook_id": "Budget.xlsx",
                "workbook_version_id": "docv-budget",
                "raw_locator": {
                    "document_version_id": "docv-budget",
                    "sheet": "Approvals",
                    "range": "A2:D2",
                    "cell": "B2",
                    "row_index_1based": 2,
                    "row_label": "department=Ops | month=202602",
                    "column_label": "approved_amount",
                    "target_column": "approved_amount",
                    "header_path": ["budget", "approved_amount"],
                    "table_id": "approvals-main-table",
                    "normalized_value": "15446522",
                    "formula": "=SUM(B1:B6)",
                    "source_path": "D:/private/Budget.xlsx",
                    "stable_locator_fingerprint": "locator-sha",
                },
                "canonical_citation_payload": {
                    "sheet": "Approvals",
                    "range": "A2:D2",
                    "cell": "B2",
                    "row_label": "department=Ops | month=202602",
                    "column_label": "approved_amount",
                    "target_column": "approved_amount",
                    "header_path": ["budget", "approved_amount"],
                    "table_id": "approvals-main-table",
                    "locator_fingerprint": "locator-sha",
                },
            }
        ],
    )

    loader = SourceNativeCorpusLoader(search_view_manifest_path=manifest, source_atom_registry_path=registry)
    unit = loader.load_units()[0]
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    record = source_atom_record_from_mapping(unit, config)
    serialized_unit = json.dumps(unit, ensure_ascii=False)
    serialized_record = json.dumps(record, ensure_ascii=False)

    assert unit["doc_id"] == "docv-budget"
    assert record["doc_id"] == "docv-budget"
    assert unit["metadata"]["sheet"] == "Approvals"
    assert unit["metadata"]["cell_range"] == "A2:D2"
    assert unit["metadata"]["cell"] == "B2"
    assert unit["metadata"]["row_index_1based"] == "2"
    assert unit["metadata"]["row_label"] == "department=Ops | month=202602"
    assert unit["metadata"]["column_label"] == "approved_amount"
    assert unit["metadata"]["target_column"] == "approved_amount"
    assert unit["metadata"]["header_path"] == '["budget","approved_amount"]'
    assert unit["metadata"]["table_id"] == "approvals-main-table"
    assert unit["metadata"]["locator_fingerprint"] == "locator-sha"
    assert record["sheet"] == "Approvals"
    assert record["cell_range"] == "A2:D2"
    assert record["cell"] == "B2"
    assert record["row_index_1based"] == "2"
    assert record["row_label"] == "department=Ops | month=202602"
    assert record["column_label"] == "approved_amount"
    assert record["target_column"] == "approved_amount"
    assert record["header_path"] == '["budget","approved_amount"]'
    assert record["table_id"] == "approvals-main-table"
    assert "D:/private/Budget.xlsx" not in serialized_unit
    assert "D:/private/Budget.xlsx" not in serialized_record
    assert "source_path" not in serialized_unit
    assert "source_path" not in serialized_record
    assert "15446522" not in serialized_unit
    assert "15446522" not in serialized_record
    assert "=SUM" not in serialized_unit
    assert "=SUM" not in serialized_record


def test_source_native_corpus_loader_derives_display_value_from_source_owned_snapshot_not_normalized_value(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "search_view_manifest.jsonl"
    registry = tmp_path / "source_atom_registry_v1.jsonl"
    write_jsonl(
        manifest,
        [
            {
                "source_atom_id": "srcatom-xlsx-display-snapshot",
                "evidence_bundle_id": "bundle-xlsx-display-snapshot",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-display-snapshot",
                "bm25_text": (
                    "sheet=Approvals | range=A2:D2 | row_label=department=Ops | month=202602 | "
                    "target_column=approved_amount\n"
                    "snapshot=Approvals B2: department=Ops | month=202602 | approved_amount=15,446,522명"
                ),
                "embedding_text": "department Ops month 202602 approved amount",
                "source_identity": "registry-only-source-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            }
        ],
    )
    write_jsonl(
        registry,
        [
            {
                "source_atom_id": "srcatom-xlsx-display-snapshot",
                "source_family": "XLSX",
                "raw_locator": {
                    "document_version_id": "docv-budget",
                    "sheet": "Approvals",
                    "range": "A2:D2",
                    "cell": "B2",
                    "row_index_1based": 2,
                    "row_label": "department=Ops | month=202602",
                    "target_column": "approved_amount",
                    "normalized_value": "15446522",
                    "formula": "=SUM(B1:B6)",
                    "source_path": "D:/private/Budget.xlsx",
                },
            }
        ],
    )

    loader = SourceNativeCorpusLoader(search_view_manifest_path=manifest, source_atom_registry_path=registry)
    unit = loader.load_units()[0]
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    record = source_atom_record_from_mapping(unit, config)
    serialized_unit = json.dumps(unit, ensure_ascii=False)
    serialized_record = json.dumps(record, ensure_ascii=False)

    assert unit["metadata"]["display_value"] == "15,446,522명"
    assert record["display_value"] == "15,446,522명"
    assert "15446522" not in serialized_unit
    assert "15446522" not in serialized_record
    assert "normalized_value" not in serialized_unit
    assert "normalized_value" not in serialized_record
    assert "=SUM" not in serialized_unit
    assert "=SUM" not in serialized_record
    assert "D:/private/Budget.xlsx" not in serialized_unit
    assert "D:/private/Budget.xlsx" not in serialized_record


def test_source_native_corpus_loader_synthesizes_candidate_surface_xlsx_row_value_bundles(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "search_view_manifest.jsonl"
    registry = tmp_path / "source_atom_registry_v1.jsonl"
    write_jsonl(
        manifest,
        [
            {
                "source_atom_id": "srcatom-xlsx-approved-amount",
                "evidence_bundle_id": "bundle-xlsx-approved-amount",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-approved-amount",
                "bm25_text": (
                    "sheet=Approvals | range=A2:D2 | row_label=department=Ops | month=202602 | "
                    "target_column=approved_amount\n"
                    "snapshot=Approvals B2: department=Ops | month=202602 | approved_amount=15,446,522명"
                ),
                "embedding_text": "department Ops month 202602 approved amount",
                "source_identity": "safe-source-row-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            }
        ],
    )
    write_jsonl(
        registry,
        [
            {
                "source_atom_id": "srcatom-xlsx-approved-amount",
                "source_family": "XLSX",
                "raw_locator": {
                    "document_version_id": "docv-budget",
                    "sheet": "Approvals",
                    "range": "A2:D2",
                    "cell": "B2",
                    "row_index_1based": 2,
                    "row_label": "department=Ops | month=202602",
                    "column_label": "approved_amount",
                    "target_column": "approved_amount",
                    "normalized_value": "15446522",
                    "formula": "=SUM(B1:B6)",
                    "source_path": "D:/private/Budget.xlsx",
                },
            }
        ],
    )

    loader = SourceNativeCorpusLoader(
        search_view_manifest_path=manifest,
        source_atom_registry_path=registry,
        synthesize_xlsx_row_value_bundles=True,
    )
    units = loader.load_units()
    bundles = [
        unit
        for unit in units
        if unit["metadata"].get("candidate_surface_materialization") == "xlsx_row_value_bundle_v1"
    ]
    assert len(bundles) == 1
    bundle = bundles[0]
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    record = source_atom_record_from_mapping(bundle, config)
    serialized_bundle = json.dumps(bundle, ensure_ascii=False)
    serialized_record = json.dumps(record, ensure_ascii=False)

    assert bundle["source_family"] == "XLSX"
    assert bundle["granularity"] == "table_row"
    assert bundle["retrieval_route"] == "xlsx_table"
    assert bundle["metadata"]["source_atom_ids"] == ["srcatom-xlsx-approved-amount"]
    assert bundle["metadata"]["target_column"] == "approved_amount"
    assert bundle["metadata"]["display_value"] == "15,446,522명"
    assert "row_label=department=Ops | month=202602" in bundle["text"]
    assert "target_column=approved_amount" in bundle["text"]
    assert "display_value=15,446,522명" in bundle["text"]
    assert "cell=" not in bundle["text"].casefold()
    assert record["granularity"] == "table_row"
    assert record["vectorized_semantic_content"] == "true"
    assert record["target_column"] == "approved_amount"
    assert record["display_value"] == "15,446,522명"
    assert "15446522" not in serialized_bundle
    assert "15446522" not in serialized_record
    assert "normalized_value" not in serialized_bundle
    assert "normalized_value" not in serialized_record
    assert "=SUM" not in serialized_bundle
    assert "=SUM" not in serialized_record
    assert "D:/private/Budget.xlsx" not in serialized_bundle
    assert "D:/private/Budget.xlsx" not in serialized_record


def test_xlsx_row_value_bundle_preserves_same_candidate_axis_contract(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "search_view_manifest.jsonl"
    registry = tmp_path / "source_atom_registry_v1.jsonl"
    write_jsonl(
        manifest,
        [
            {
                "source_atom_id": "srcatom-xlsx-ridership",
                "evidence_bundle_id": "bundle-xlsx-ridership",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-ridership",
                "bm25_text": (
                    "sheet=철도 | range=A302:D351 | row_label=노선명=안산선 | period=201902 | "
                    "target_column=수송인원\n"
                    "snapshot=철도 A302: 노선명=안산선 | period=201902 | 수송인원=999명"
                ),
                "embedding_text": "안산선 201902 수송인원",
                "source_identity": "safe-source-row-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            }
        ],
    )
    write_jsonl(
        registry,
        [
            {
                "source_atom_id": "srcatom-xlsx-ridership",
                "source_family": "XLSX",
                "raw_locator": {
                    "document_version_id": "docv-ridership",
                    "sheet": "철도",
                    "range": "A302:D351",
                    "cell": "D302",
                    "row_index_1based": 302,
                    "row_label": "노선명=안산선",
                    "column_label": "수송인원",
                    "target_column": "수송인원",
                },
            }
        ],
    )

    loader = SourceNativeCorpusLoader(
        search_view_manifest_path=manifest,
        source_atom_registry_path=registry,
        synthesize_xlsx_row_value_bundles=True,
    )
    units = loader.load_units()
    bundles = [
        unit
        for unit in units
        if unit["metadata"].get("candidate_surface_materialization") == "xlsx_row_value_bundle_v1"
    ]

    assert len(bundles) == 1
    bundle = bundles[0]
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    record = source_atom_record_from_mapping(bundle, config)
    serialized_bundle = json.dumps(bundle, ensure_ascii=False)
    serialized_record = json.dumps(record, ensure_ascii=False)

    assert bundle["metadata"]["source_date_aliases"] == ["2019년 2월", "2019년", "2월"]
    assert bundle["metadata"]["sheet"] == "철도"
    assert bundle["metadata"]["cell_range"] == "A302:D351"
    assert bundle["metadata"]["row_label"] == "노선명=안산선"
    assert bundle["metadata"]["target_column"] == "수송인원"
    assert bundle["metadata"]["display_value"] == "999명"
    assert "sheet=철도" in bundle["text"]
    assert "range=A302:D351" in bundle["text"]
    assert "row_label=노선명=안산선" in bundle["text"]
    assert "target_column=수송인원" in bundle["text"]
    assert "display_value=999명" in bundle["text"]
    assert "source_date_alias=2019년 2월" in bundle["text"]
    assert "source_date_alias=2019년" in bundle["text"]
    assert "source_date_alias=2월" in bundle["text"]
    assert record["text"] == bundle["text"]
    assert "normalized_value" not in serialized_bundle
    assert "formula" not in serialized_bundle
    assert "source_path" not in serialized_bundle
    assert "normalized_value" not in serialized_record
    assert "formula" not in serialized_record
    assert "source_path" not in serialized_record


def test_weaviate_source_atom_v2_preserves_xlsx_axis_contract_from_bundle(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "search_view_manifest.jsonl"
    registry = tmp_path / "source_atom_registry_v1.jsonl"
    write_jsonl(
        manifest,
        [
            {
                "source_atom_id": "srcatom-xlsx-axis-contract",
                "evidence_bundle_id": "bundle-xlsx-axis-contract",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-axis-contract",
                "bm25_text": (
                    "sheet=철도 | range=A302:D351 | row_label=노선명=안산선 | 년월=201902 | "
                    "target_column=수송인원\n"
                    "snapshot=철도 A302: 노선명=안산선 | 년월=201902 | 수송인원=999명"
                ),
                "embedding_text": "안산선 201902 수송인원",
                "source_identity": "safe-source-row-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            }
        ],
    )
    write_jsonl(
        registry,
        [
            {
                "source_atom_id": "srcatom-xlsx-axis-contract",
                "source_family": "XLSX",
                "raw_locator": {
                    "document_version_id": "docv-axis-contract",
                    "sheet": "철도",
                    "range": "A302:D351",
                    "cell": "D302",
                    "row_index_1based": 302,
                    "row_label": "노선명=안산선",
                    "column_label": "수송인원",
                    "target_column": "수송인원",
                    "normalized_value": "999",
                    "formula": "=SUM(D1:D2)",
                    "source_path": "D:/private/ridership.xlsx",
                },
            }
        ],
    )
    loader = SourceNativeCorpusLoader(
        search_view_manifest_path=manifest,
        source_atom_registry_path=registry,
        synthesize_xlsx_row_value_bundles=True,
    )
    bundle = next(
        unit
        for unit in loader.load_units()
        if unit["metadata"].get("candidate_surface_materialization") == "xlsx_row_value_bundle_v1"
    )
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )

    record = source_atom_record_from_mapping(bundle, config)

    assert record["sheet"] == "철도"
    assert record["cell_range"] == "A302:D351"
    assert record["row_index_1based"] == "302"
    assert record["row_label"] == "노선명=안산선"
    assert record["target_column"] == "수송인원"
    assert record["display_value"] == "999명"
    assert record["candidate_surface_materialization"] == "xlsx_row_value_bundle_v1"
    assert record["candidate_surface_materialization_policy"] == (
        "source_owned_manifest_snapshot_no_gold_qrels_labels_or_normalized_fields_v1"
    )
    assert json.loads(record["source_date_aliases_json"]) == ["2019년 2월", "2019년", "2월"]
    assert json.loads(record["source_atom_ids_json"]) == ["srcatom-xlsx-axis-contract"]

    encoded = json.dumps(record, ensure_ascii=False)
    assert "normalized_value" not in encoded
    assert "formula" not in encoded
    assert "D:/private/ridership.xlsx" not in encoded


def test_xlsx_locator_accepts_only_same_candidate_complete_axis_package(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "search_view_manifest.jsonl"
    registry = tmp_path / "source_atom_registry_v1.jsonl"
    write_jsonl(
        manifest,
        [
            {
                "source_atom_id": "srcatom-xlsx-locator-contract",
                "evidence_bundle_id": "bundle-xlsx-locator-contract",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-locator-contract",
                "bm25_text": (
                    "sheet=철도 | range=A302:D351 | row_label=노선명=안산선 | 년월=201902 | "
                    "target_column=수송인원\n"
                    "snapshot=철도 A302: 노선명=안산선 | 년월=201902 | 수송인원=999명"
                ),
                "embedding_text": "안산선 201902 수송인원",
                "source_identity": "safe-source-row-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            }
        ],
    )
    write_jsonl(
        registry,
        [
            {
                "source_atom_id": "srcatom-xlsx-locator-contract",
                "source_family": "XLSX",
                "raw_locator": {
                    "document_version_id": "docv-locator-contract",
                    "sheet": "철도",
                    "range": "A302:D351",
                    "cell": "D302",
                    "row_index_1based": 302,
                    "row_label": "노선명=안산선",
                    "column_label": "수송인원",
                    "target_column": "수송인원",
                },
            }
        ],
    )
    loader = SourceNativeCorpusLoader(
        search_view_manifest_path=manifest,
        source_atom_registry_path=registry,
        synthesize_xlsx_row_value_bundles=True,
    )
    bundle = next(
        unit
        for unit in loader.load_units()
        if unit["metadata"].get("candidate_surface_materialization") == "xlsx_row_value_bundle_v1"
    )
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    context = source_atom_record_from_mapping(bundle, config)
    query = "2019년 2월 안산선의 수송인원은 몇 명입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"period": "2019-02", "line_name": "안산선"},
            "target_axis": {"column": "수송인원", "value_type": "number"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2019-02", "2019년 2월"],
                "row_entity": ["안산선"],
                "target_column": ["수송인원"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "xlsx-row-value-bundle-source-atom-contract",
        "query": query,
        "generated_answer": "999명",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
    }

    candidate = actual_rag_eval._xlsx_locator_candidate_from_context(row, context)

    assert candidate is not None
    assert candidate["source_owned_same_candidate_package"] is True
    assert candidate["accepted_for_regating"] is True
    assert candidate["matched_validated_required_axes"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert candidate["missing_validated_required_axes"] == []

    split_context = dict(context)
    split_context["source_atom_id"] = "srcatom-xlsx-locator-contract-split"
    split_context["text"] = (
        "sheet=철도 | range=A302:D351 | 년월=201902 | "
        "target_column=수송인원 | display_value=999명"
    )
    split_context.pop("row_index_1based", None)
    split_context.pop("row_label", None)

    split_candidate = actual_rag_eval._xlsx_locator_candidate_from_context(row, split_context)

    assert split_candidate is not None
    assert split_candidate.get("source_owned_same_candidate_package") is not True
    assert split_candidate["accepted_for_regating"] is False
    assert "row_entity" in split_candidate["missing_validated_required_axes"]


def test_source_native_corpus_loader_adds_same_row_date_aliases_to_xlsx_value_bundle(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "search_view_manifest.jsonl"
    registry = tmp_path / "source_atom_registry_v1.jsonl"
    write_jsonl(
        manifest,
        [
            {
                "source_atom_id": "srcatom-xlsx-care-address",
                "evidence_bundle_id": "bundle-xlsx-care-address",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-care-address",
                "bm25_text": (
                    "sheet=일반현황 | range=A5002:J5051 | "
                    "row_label=장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | "
                    "target_column=기관별 상세주소 | 기관별 상세주소=충청남도 부여군 석성면 왕릉로 773"
                ),
                "embedding_text": "부여효요양원 기관별 상세주소",
                "source_identity": "care-address-source-row-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            },
            {
                "source_atom_id": "srcatom-xlsx-care-date",
                "evidence_bundle_id": "bundle-xlsx-care-date",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-care-date",
                "bm25_text": (
                    "sheet=일반현황 | range=A5002:J5051 | "
                    "row_label=장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | "
                    "target_column=지정일자 | 지정일자=2015-06-01"
                ),
                "embedding_text": "부여효요양원 지정일자 2015-06-01",
                "source_identity": "care-date-source-row-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            },
        ],
    )
    write_jsonl(
        registry,
        [
            {
                "source_atom_id": "srcatom-xlsx-care-address",
                "source_family": "XLSX",
                "raw_locator": {
                    "document_version_id": "docv-care",
                    "sheet": "일반현황",
                    "range": "A5002:J5051",
                    "cell": "J5002",
                    "row_index_1based": 5002,
                    "row_label": "장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원",
                    "column_label": "기관별 상세주소",
                    "target_column": "기관별 상세주소",
                },
            },
            {
                "source_atom_id": "srcatom-xlsx-care-date",
                "source_family": "XLSX",
                "raw_locator": {
                    "document_version_id": "docv-care",
                    "sheet": "일반현황",
                    "range": "A5002:J5051",
                    "cell": "H5002",
                    "row_index_1based": 5002,
                    "row_label": "장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원",
                    "column_label": "지정일자",
                    "target_column": "지정일자",
                },
            },
        ],
    )

    loader = SourceNativeCorpusLoader(
        search_view_manifest_path=manifest,
        source_atom_registry_path=registry,
        synthesize_xlsx_row_value_bundles=True,
    )
    units = loader.load_units()
    bundles = [
        unit
        for unit in units
        if unit["metadata"].get("candidate_surface_materialization") == "xlsx_row_value_bundle_v1"
        and unit["metadata"].get("target_column") == "기관별 상세주소"
    ]

    assert len(bundles) == 1
    bundle = bundles[0]
    serialized_bundle = json.dumps(bundle, ensure_ascii=False)
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    record = source_atom_record_from_mapping(bundle, config)
    serialized_record = json.dumps(record, ensure_ascii=False)
    assert bundle["doc_id"] == "docv-care"
    assert bundle["metadata"]["source_atom_ids"] == [
        "srcatom-xlsx-care-address",
        "srcatom-xlsx-care-date",
    ]
    assert bundle["metadata"]["source_date_aliases"] == ["2015년 6월", "2015년", "6월", "1일"]
    assert "source_date_alias=2015년 6월" in bundle["text"]
    assert "source_date_alias=2015년" in bundle["text"]
    assert "source_date_alias=6월" in bundle["text"]
    assert "source_date_alias=1일" in bundle["text"]
    assert record["text"] == bundle["text"]
    assert "source_date_alias=2015년 6월" in record["text"]
    assert "normalized_value" not in serialized_bundle
    assert "normalized_value" not in serialized_record
    assert "formula" not in serialized_bundle
    assert "formula" not in serialized_record
    assert "source_path" not in serialized_bundle
    assert "source_path" not in serialized_record


def test_source_native_corpus_loader_does_not_bleed_same_row_date_aliases_across_rows_or_docs(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "search_view_manifest.jsonl"
    registry = tmp_path / "source_atom_registry_v1.jsonl"
    write_jsonl(
        manifest,
        [
            {
                "source_atom_id": "srcatom-xlsx-address",
                "evidence_bundle_id": "bundle-xlsx-address",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-address",
                "bm25_text": (
                    "sheet=일반현황 | range=A5002:J5051 | "
                    "row_label=장기요양기관이름=부여효요양원 | "
                    "target_column=기관별 상세주소 | 기관별 상세주소=충청남도 부여군 석성면 왕릉로 773"
                ),
                "embedding_text": "부여효요양원 기관별 상세주소",
                "source_identity": "care-address-source-row-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            },
            {
                "source_atom_id": "srcatom-xlsx-date-other-row",
                "evidence_bundle_id": "bundle-xlsx-date-other-row",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-date-other-row",
                "bm25_text": (
                    "sheet=일반현황 | range=A5002:J5051 | "
                    "row_label=장기요양기관이름=다른요양원 | "
                    "target_column=지정일자 | 지정일자=2015-06-01"
                ),
                "embedding_text": "다른요양원 지정일자 2015-06-01",
                "source_identity": "other-row-date-source-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            },
            {
                "source_atom_id": "srcatom-xlsx-date-other-doc",
                "evidence_bundle_id": "bundle-xlsx-date-other-doc",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-date-other-doc",
                "bm25_text": (
                    "sheet=일반현황 | range=A5002:J5051 | "
                    "row_label=장기요양기관이름=부여효요양원 | "
                    "target_column=지정일자 | 지정일자=2020-11-01"
                ),
                "embedding_text": "부여효요양원 지정일자 2020-11-01",
                "source_identity": "other-doc-date-source-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            },
        ],
    )
    write_jsonl(
        registry,
        [
            {
                "source_atom_id": "srcatom-xlsx-address",
                "source_family": "XLSX",
                "raw_locator": {
                    "document_version_id": "docv-care",
                    "sheet": "일반현황",
                    "range": "A5002:J5051",
                    "cell": "J5002",
                    "row_index_1based": 5002,
                    "row_label": "장기요양기관이름=부여효요양원",
                    "column_label": "기관별 상세주소",
                    "target_column": "기관별 상세주소",
                },
            },
            {
                "source_atom_id": "srcatom-xlsx-date-other-row",
                "source_family": "XLSX",
                "raw_locator": {
                    "document_version_id": "docv-care",
                    "sheet": "일반현황",
                    "range": "A5002:J5051",
                    "cell": "H5003",
                    "row_index_1based": 5003,
                    "row_label": "장기요양기관이름=다른요양원",
                    "column_label": "지정일자",
                    "target_column": "지정일자",
                },
            },
            {
                "source_atom_id": "srcatom-xlsx-date-other-doc",
                "source_family": "XLSX",
                "raw_locator": {
                    "document_version_id": "docv-other-care",
                    "sheet": "일반현황",
                    "range": "A5002:J5051",
                    "cell": "H5002",
                    "row_index_1based": 5002,
                    "row_label": "장기요양기관이름=부여효요양원",
                    "column_label": "지정일자",
                    "target_column": "지정일자",
                },
            },
        ],
    )

    loader = SourceNativeCorpusLoader(
        search_view_manifest_path=manifest,
        source_atom_registry_path=registry,
        synthesize_xlsx_row_value_bundles=True,
    )
    bundles = [
        unit
        for unit in loader.load_units()
        if unit["metadata"].get("candidate_surface_materialization") == "xlsx_row_value_bundle_v1"
        and unit["metadata"].get("target_column") == "기관별 상세주소"
    ]

    assert len(bundles) == 1
    bundle = bundles[0]
    serialized_bundle = json.dumps(bundle, ensure_ascii=False)
    assert "source_date_aliases" not in bundle["metadata"]
    assert bundle["metadata"]["source_atom_ids"] == ["srcatom-xlsx-address"]
    assert "source_date_alias=" not in bundle["text"]
    assert "srcatom-xlsx-date-other-row" not in serialized_bundle
    assert "srcatom-xlsx-date-other-doc" not in serialized_bundle
    assert "2015년 6월" not in serialized_bundle
    assert "2020년 11월" not in serialized_bundle


def test_source_native_corpus_loader_does_not_propagate_date_aliases_from_forbidden_segments(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "search_view_manifest.jsonl"
    registry = tmp_path / "source_atom_registry_v1.jsonl"
    write_jsonl(
        manifest,
        [
            {
                "source_atom_id": "srcatom-xlsx-safe-address",
                "evidence_bundle_id": "bundle-xlsx-safe-address",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-safe-address",
                "bm25_text": (
                    "sheet=일반현황 | range=A5002:J5051 | row_label=장기요양기관이름=부여효요양원 | "
                    "target_column=기관별 상세주소 | 기관별 상세주소=충청남도 부여군 석성면 왕릉로 773"
                ),
                "embedding_text": "부여효요양원 기관별 상세주소",
                "source_identity": "safe-address-source-row-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            },
            {
                "source_atom_id": "srcatom-xlsx-forbidden-date",
                "evidence_bundle_id": "bundle-xlsx-forbidden-date",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-forbidden-date",
                "bm25_text": (
                    "sheet=일반현황 | range=A5002:J5051 | row_label=장기요양기관이름=부여효요양원 | "
                    "target_column=지정일자 | formula=2015-06-01 | "
                    "normalized_value=2015-06-01 | source_path=D:/private/2015-06.xlsx"
                ),
                "embedding_text": "부여효요양원 forbidden date",
                "source_identity": "forbidden-date-source-row-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            },
        ],
    )
    write_jsonl(
        registry,
        [
            {
                "source_atom_id": "srcatom-xlsx-safe-address",
                "source_family": "XLSX",
                "raw_locator": {
                    "document_version_id": "docv-care",
                    "sheet": "일반현황",
                    "range": "A5002:J5051",
                    "cell": "J5002",
                    "row_index_1based": 5002,
                    "row_label": "장기요양기관이름=부여효요양원",
                    "column_label": "기관별 상세주소",
                    "target_column": "기관별 상세주소",
                },
            },
            {
                "source_atom_id": "srcatom-xlsx-forbidden-date",
                "source_family": "XLSX",
                "raw_locator": {
                    "document_version_id": "docv-care",
                    "sheet": "일반현황",
                    "range": "A5002:J5051",
                    "cell": "H5002",
                    "row_index_1based": 5002,
                    "row_label": "장기요양기관이름=부여효요양원",
                    "column_label": "지정일자",
                    "target_column": "지정일자",
                },
            },
        ],
    )

    loader = SourceNativeCorpusLoader(
        search_view_manifest_path=manifest,
        source_atom_registry_path=registry,
        synthesize_xlsx_row_value_bundles=True,
    )
    bundles = [
        unit
        for unit in loader.load_units()
        if unit["metadata"].get("candidate_surface_materialization") == "xlsx_row_value_bundle_v1"
        and unit["metadata"].get("target_column") == "기관별 상세주소"
    ]

    assert len(bundles) == 1
    bundle = bundles[0]
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    record = source_atom_record_from_mapping(bundle, config)
    serialized_bundle = json.dumps(bundle, ensure_ascii=False)
    serialized_record = json.dumps(record, ensure_ascii=False)
    assert "source_date_aliases" not in bundle["metadata"]
    assert bundle["metadata"]["source_atom_ids"] == ["srcatom-xlsx-safe-address"]
    assert "source_date_alias=" not in bundle["text"]
    assert "srcatom-xlsx-forbidden-date" not in serialized_bundle
    assert "formula" not in serialized_bundle
    assert "formula" not in serialized_record
    assert "normalized_value" not in serialized_bundle
    assert "normalized_value" not in serialized_record
    assert "source_path" not in serialized_bundle
    assert "source_path" not in serialized_record


def test_source_native_corpus_loader_ignores_metadata_only_date_aliases_for_row_value_bundles(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "search_view_manifest.jsonl"
    registry = tmp_path / "source_atom_registry_v1.jsonl"
    write_jsonl(
        manifest,
        [
            {
                "source_atom_id": "srcatom-xlsx-address-metadata-only-alias",
                "evidence_bundle_id": "bundle-xlsx-address-metadata-only-alias",
                "source_family": "XLSX",
                "search_view_id": "sv-xlsx-address-metadata-only-alias",
                "bm25_text": (
                    "sheet=일반현황 | range=A5002:J5051 | row_label=장기요양기관이름=부여효요양원 | "
                    "target_column=기관별 상세주소 | 기관별 상세주소=충청남도 부여군 석성면 왕릉로 773"
                ),
                "embedding_text": "부여효요양원 기관별 상세주소",
                "source_date_aliases": ["2015년 6월", "2015년", "6월"],
                "source_identity": "metadata-only-address-source-row-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            }
        ],
    )
    write_jsonl(
        registry,
        [
            {
                "source_atom_id": "srcatom-xlsx-address-metadata-only-alias",
                "source_family": "XLSX",
                "source_date_aliases": ["2015년 6월", "2015년", "6월"],
                "raw_locator": {
                    "document_version_id": "docv-care",
                    "sheet": "일반현황",
                    "range": "A5002:J5051",
                    "cell": "J5002",
                    "row_index_1based": 5002,
                    "row_label": "장기요양기관이름=부여효요양원",
                    "column_label": "기관별 상세주소",
                    "target_column": "기관별 상세주소",
                },
            }
        ],
    )

    loader = SourceNativeCorpusLoader(
        search_view_manifest_path=manifest,
        source_atom_registry_path=registry,
        synthesize_xlsx_row_value_bundles=True,
    )
    bundles = [
        unit
        for unit in loader.load_units()
        if unit["metadata"].get("candidate_surface_materialization") == "xlsx_row_value_bundle_v1"
    ]

    assert len(bundles) == 1
    bundle = bundles[0]
    serialized_bundle = json.dumps(bundle, ensure_ascii=False)
    assert "source_date_aliases" not in bundle["metadata"]
    assert "source_date_alias=" not in bundle["text"]
    assert "2015년 6월" not in serialized_bundle


def test_preserve_xlsx_locator_source_contexts_keeps_verified_bundle_source_date_aliases_for_period_axis() -> None:
    query = "2015년 6월 부여효요양원의 상세주소는 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"period": "2015-06", "line_name": "부여효요양원"},
            "target_axis": {"column": "상세주소", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2015-06", "2015년 6월"],
                "row_entity": ["부여효요양원"],
                "target_column": ["상세주소", "기관별 상세주소"],
                "display_value": [],
            },
        },
    )
    retrieved_context = {
        "doc_id": "docv-care",
        "chunk_id": "srcatom-xlsx-care-address-bundle",
        "source_atom_id": "srcatom-xlsx-care-address-bundle",
        "evidence_bundle_id": "bundle-srcatom-xlsx-care-address-bundle",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": (
            "sheet=일반현황 | range=A5002:J5051 | row_index_1based=5002 | "
            "row_label=장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | "
            "target_column=기관별 상세주소 | display_value=충청남도 부여군 석성면 왕릉로 773"
        ),
        "sheet": "일반현황",
        "cell_range": "A5002:J5051",
        "row_index_1based": "5002",
        "row_label": "장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원",
        "column_label": "기관별 상세주소",
        "target_column": "기관별 상세주소",
        "display_value": "충청남도 부여군 석성면 왕릉로 773",
        "metadata": {
            "candidate_surface_materialization": "xlsx_row_value_bundle_v1",
            "source_date_aliases": ["2015년 6월", "2015년", "6월"],
        },
    }
    row = {
        "id": "xlsx-preserved-source-date-aliases",
        "query": query,
        "generated_answer": "충청남도 부여군 석성면 왕릉로 773",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [retrieved_context],
    }

    preserved = actual_rag_eval.preserve_xlsx_locator_source_contexts([row])[0]
    candidates = actual_rag_eval._xlsx_locator_tool_candidates(preserved)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["accepted_for_regating"] is True
    assert candidate["source_owned_same_candidate_package"] is True
    assert candidate["source_date_aliases"] == ["2015년 6월", "2015년", "6월"]
    assert "source_date_aliases" in candidate["input_fields_used"]
    assert candidate["matched_validated_required_axes"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert candidate["missing_validated_required_axes"] == []


def test_verified_bundle_source_date_aliases_do_not_accept_incomplete_locator_candidate() -> None:
    query = "2015년 6월 부여효요양원의 상세주소는 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"period": "2015-06", "line_name": "부여효요양원"},
            "target_axis": {"column": "상세주소", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2015-06", "2015년 6월"],
                "row_entity": ["부여효요양원"],
                "target_column": ["상세주소", "기관별 상세주소"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "xlsx-incomplete-source-date-aliases",
        "query": query,
        "generated_answer": "근거만으로는 알 수 없습니다.",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "docv-care",
                "chunk_id": "srcatom-xlsx-care-alias-only",
                "source_atom_id": "srcatom-xlsx-care-alias-only",
                "evidence_bundle_id": "bundle-srcatom-xlsx-care-alias-only",
                "source_family": "XLSX",
                "granularity": "table_row",
                "text": "sheet=일반현황 | range=A1:J30761 | target_column=기관별 상세주소",
                "sheet": "일반현황",
                "cell_range": "A1:J30761",
                "target_column": "기관별 상세주소",
                "metadata": {
                    "candidate_surface_materialization": "xlsx_row_value_bundle_v1",
                    "source_date_aliases": ["2015년 6월", "2015년", "6월"],
                },
            }
        ],
    }

    preserved = actual_rag_eval.preserve_xlsx_locator_source_contexts([row])[0]
    snapshot = preserved[actual_rag_eval.INTERNAL_XLSX_LOCATOR_SOURCE_CONTEXTS_KEY][0]
    assert snapshot["source_date_aliases"] == ["2015년 6월", "2015년", "6월"]
    assert snapshot["candidate_surface_materialization"] == "xlsx_row_value_bundle_v1"
    candidates = actual_rag_eval._xlsx_locator_tool_candidates(preserved)

    assert len(candidates) == 1
    candidate = candidates[0]
    if candidate.get("source_date_aliases"):
        assert candidate["source_date_aliases"] == ["2015년 6월", "2015년", "6월"]
    assert candidate["accepted_for_regating"] is False
    assert candidate["rejection_reason"] == "missing_validated_required_axes_after_tool"
    assert {"row_entity", "display_value"}.issubset(set(candidate["missing_validated_required_axes"]))


@pytest.mark.parametrize(
    ("forbidden_target", "forbidden_segment", "raises_schema_error"),
    [
        ("normalized_value", "normalized_value=15446522", False),
        ("formula", "formula==SUM(B1:B6)", False),
        ("source_path", "source_path=D:/private/Budget.xlsx", False),
        ("raw_prompt_payload", "raw_prompt_payload=SECRET_PROMPT_PAYLOAD", True),
    ],
)
def test_source_native_corpus_loader_refuses_forbidden_xlsx_row_value_bundle_targets(
    tmp_path: Path,
    forbidden_target: str,
    forbidden_segment: str,
    raises_schema_error: bool,
) -> None:
    manifest = tmp_path / "search_view_manifest.jsonl"
    registry = tmp_path / "source_atom_registry_v1.jsonl"
    write_jsonl(
        manifest,
        [
            {
                "source_atom_id": f"srcatom-xlsx-forbidden-{forbidden_target}",
                "evidence_bundle_id": f"bundle-xlsx-forbidden-{forbidden_target}",
                "source_family": "XLSX",
                "search_view_id": f"sv-xlsx-forbidden-{forbidden_target}",
                "bm25_text": (
                    "sheet=Approvals | range=A2:D2 | row_label=department=Ops | "
                    f"target_column={forbidden_target}\n"
                    f"snapshot=Approvals B2: department=Ops | {forbidden_segment}"
                ),
                "embedding_text": "department Ops normalized forbidden",
                "source_identity": "safe-source-row-identity",
                "source_registry_version": "source_registry_v1",
                "materialization_bucket": "source_atom_value",
                "canonical_payload_source": "source_atom",
            }
        ],
    )
    write_jsonl(
        registry,
        [
            {
                "source_atom_id": f"srcatom-xlsx-forbidden-{forbidden_target}",
                "source_family": "XLSX",
                "raw_locator": {
                    "document_version_id": "docv-budget",
                    "sheet": "Approvals",
                    "range": "A2:D2",
                    "row_index_1based": 2,
                    "row_label": "department=Ops",
                    "column_label": forbidden_target,
                    "target_column": forbidden_target,
                },
            }
        ],
    )

    loader = SourceNativeCorpusLoader(
        search_view_manifest_path=manifest,
        source_atom_registry_path=registry,
        synthesize_xlsx_row_value_bundles=True,
    )

    if raises_schema_error:
        with pytest.raises(DatasetSchemaError, match="forbidden candidate text markers"):
            loader.load_units()
        return

    units = loader.load_units()
    bundles = [
        unit
        for unit in units
        if unit["metadata"].get("candidate_surface_materialization") == "xlsx_row_value_bundle_v1"
    ]

    assert bundles == []


def test_weaviate_streaming_indexer_rejects_faiss_seeded_checkpoint(tmp_path: Path) -> None:
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    checkpoint_path = tmp_path / "weaviate-index-checkpoint.json"
    checkpoint_path.write_text(
        json.dumps(
            {
                "schema_version": "weaviate_source_atom_index_checkpoint_v1",
                "collection_name": "SourceAtomNonprod",
                "namespace": "actual_rag_eval_nonprod",
                "embedding_model": "BAAI/bge-m3",
                "index_vector_source": "source-native-faiss-bge-m3",
                "faiss_used_for_index_seed": True,
                "diagnostic_hash_vector_used": False,
                "completed_source_atom_ids": ["srcatom-index-1"],
                "source_atom_text_sha256": {"srcatom-index-1": "sha-index-1"},
                "source_atom_registry_path_hash": "sha256:stale",
            }
        ),
        encoding="utf-8",
    )
    indexer = WeaviateSourceAtomIndexer(
        config=config,
        client=FakeWeaviateSourceAtomClient(),
        embedding_builder=BgeM3EmbeddingBuilder(
            model_name="BAAI/bge-m3",
            embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        ),
    )

    with pytest.raises(WeaviateUnavailableError, match="checkpoint_vector_source_mismatch"):
        indexer.index_records_streaming(
            iter([weaviate_source_atom_record(1)]),
            checkpoint_path=checkpoint_path,
            source_atom_registry_path="ai/eval/fixtures/source_atoms.jsonl",
        )


def test_weaviate_streaming_indexer_reupserts_same_id_when_text_hash_changes(tmp_path: Path) -> None:
    class CountingBgeM3Provider(FakeWeaviateBgeM3EmbeddingProvider):
        def __init__(self) -> None:
            self.embedded_texts: list[str] = []

        def embed_passages(self, texts: list[str]) -> object:
            self.embedded_texts.extend(texts)
            return super().embed_passages(texts)

    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    checkpoint_path = tmp_path / "weaviate-index-checkpoint.json"
    registry_path = "ai/eval/fixtures/source_atoms.jsonl"
    checkpoint_path.write_text(
        json.dumps(
            {
                "schema_version": "weaviate_source_atom_index_checkpoint_v1",
                "collection_name": "SourceAtomNonprod",
                "namespace": "actual_rag_eval_nonprod",
                "visibility": "nonprod",
                "embedding_model": "BAAI/bge-m3",
                "index_vector_source": "streaming-bge-m3",
                "faiss_used_for_index_seed": False,
                "faiss_used_for_active_retrieval": False,
                "diagnostic_hash_vector_used": False,
                "completed_source_atom_ids": ["srcatom-index-1"],
                "source_atom_text_sha256": {"srcatom-index-1": "old-sha"},
                "source_atom_registry_path_hash": (
                    "sha256:"
                    + hashlib.sha256(Path(registry_path).as_posix().encode("utf-8")).hexdigest()
                ),
            }
        ),
        encoding="utf-8",
    )
    provider = CountingBgeM3Provider()
    client = FakeWeaviateSourceAtomClient()
    indexer = WeaviateSourceAtomIndexer(
        config=config,
        client=client,
        embedding_builder=BgeM3EmbeddingBuilder(
            model_name="BAAI/bge-m3",
            batch_size=2,
            embedding_provider=provider,
        ),
    )
    record = weaviate_source_atom_record(1, text="Project Orion text changed after checkpoint.")
    record["text_sha256"] = "new-sha"

    manifest = indexer.index_records_streaming(
        iter([record]),
        checkpoint_path=checkpoint_path,
        source_atom_registry_path=registry_path,
    )
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    assert manifest["checkpoint_resumed"] is True
    assert manifest["skipped_count"] == 0
    assert manifest["upserted_count_this_run"] == 1
    assert provider.embedded_texts == [record["text"]]
    assert client.upsert_log[0]["objects"][0]["source_atom_id"] == "srcatom-index-1"
    assert checkpoint["source_atom_text_sha256"]["srcatom-index-1"] == "new-sha"


def test_weaviate_index_cli_failure_writes_invalid_manifest_without_local_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FailingStreamingIndexer:
        def __init__(self, **kwargs: object) -> None:
            self.client = FakeWeaviateSourceAtomClient()

        def index_records_streaming(self, *args: object, **kwargs: object) -> dict:
            raise WeaviateUnavailableError("weaviate_unavailable: forced streaming failure")

    monkeypatch.setattr(weaviate_index_script, "WeaviateSourceAtomIndexer", FailingStreamingIndexer)
    manifest_path = tmp_path / "index_manifest.json"
    checkpoint_path = tmp_path / "index_checkpoint.json"

    rc = weaviate_index_script.main(
        [
            "--source-native-index-dir",
            str(tmp_path),
            "--source-atom-registry-path",
            str(tmp_path / "source_atoms.jsonl"),
            "--manifest-path",
            str(manifest_path),
            "--checkpoint-path",
            str(checkpoint_path),
        ]
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert rc == 2
    assert manifest["valid"] is False
    assert manifest["vector_db_backend"] == "weaviate"
    assert manifest["index_vector_source"] == "streaming-bge-m3"
    assert "forced streaming failure" in manifest["fallback_reason"]
    assert manifest["fallback_action"] == "fix_weaviate_connection_or_configuration_then_rerun_index_command"
    assert manifest["python_local_corpus_scan_used_for_candidate_generation"] is False
    assert manifest["source_native_layered_retrieval_used_for_candidate_generation"] is False
    assert manifest["diagnostic_hash_vector_used"] is False
    assert manifest["faiss_used_for_index_seed"] is False
    assert manifest["faiss_used_for_active_retrieval"] is False
    assert manifest["searchunit_searchview_used_as_candidate_surface"] is False


def test_weaviate_indexer_upserts_bge_m3_vectors_and_rejects_gold_shortcuts() -> None:
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
            "EMBEDDING_DEVICE": "cuda",
        }
    )
    client = FakeWeaviateSourceAtomClient()
    indexer = WeaviateSourceAtomIndexer(
        config=config,
        client=client,
        embedding_builder=BgeM3EmbeddingBuilder(
            model_name="BAAI/bge-m3",
            device="cuda",
            batch_size=2,
            embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        ),
    )
    record = {
        "source_atom_id": "srcatom-index-1",
        "evidence_bundle_id": "bundle-index-1",
        "doc_id": "doc-index",
        "chunk_id": "chunk-index-1",
        "source_family": "TEXT",
        "source_track": "namu",
        "title": "Project Orion",
        "section": "Launch",
        "text": "Project Orion launch is scheduled for April 2026.",
        "text_sha256": "sha-index-1",
        "source_uri_hash": "uri-sha",
        "source_hash": "source-sha",
        "ingestion_run_id": "ingestion-nonprod",
        "ingestion_version": "v1",
        "namespace": "actual_rag_eval_nonprod",
        "visibility": "nonprod",
    }

    manifest = indexer.index_records([record], source_atom_registry_path="ai/eval/fixtures/source_atoms.jsonl")

    assert manifest["vector_db_backend"] == "weaviate"
    assert manifest["embedding_model"] == "BAAI/bge-m3"
    assert manifest["embedding_device"] == "cuda:0"
    assert manifest["embedding_dim"] == 4
    assert manifest["indexed_count"] == 1
    assert manifest["diagnostic_hash_vector_used"] is False
    assert client.upsert_log[0]["vectors"][0] == pytest.approx(
        FakeWeaviateBgeM3EmbeddingProvider().embed_passages([record["text"]])[0].tolist()
    )

    for field in ("query_id", "raw_prompt_payload", "raw_response_payload", "target_locator", "gold_locator", "baseline_topk"):
        forbidden = dict(record)
        forbidden[field] = "protected"
        with pytest.raises(ValueError, match="forbidden_candidate_generation_field"):
            source_atom_record_from_mapping(forbidden, config)

    nested_forbidden = dict(record)
    nested_forbidden["metadata"] = {"supporting_evidence": ["protected"], "human_decision": "protected"}
    with pytest.raises(ValueError, match="forbidden_candidate_generation_field"):
        source_atom_record_from_mapping(nested_forbidden, config)
