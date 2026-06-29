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

def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def output_file_names(path: Path) -> list[str]:
    return sorted(item.name for item in path.iterdir() if item.is_file())


class FakeBgeM3EmbeddingProvider:
    model_name = "BAAI/bge-m3-test"

    def embed_passages(self, texts: list[str]) -> object:
        return self._embed(texts)

    def embed_queries(self, texts: list[str]) -> object:
        return self._embed(texts)

    def _embed(self, texts: list[str]) -> object:
        import numpy as np

        rows: list[list[float]] = []
        for text in texts:
            lower = text.casefold()
            rows.append(
                [
                    1.0 if "orion" in lower else 0.0,
                    1.0 if "atlas" in lower else 0.0,
                    1.0 if "april" in lower or "2026" in lower else 0.0,
                    1.0,
                ]
            )
        matrix = np.asarray(rows, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms


class FakeWeaviateBgeM3EmbeddingProvider(FakeBgeM3EmbeddingProvider):
    model_name = "BAAI/bge-m3"
    device = "cuda:0"


def weaviate_source_atom_record(index: int, *, text: str | None = None) -> dict:
    return {
        "source_atom_id": f"srcatom-index-{index}",
        "evidence_bundle_id": f"bundle-index-{index}",
        "doc_id": "doc-index",
        "chunk_id": f"chunk-index-{index}",
        "source_family": "TEXT",
        "source_track": "namu",
        "title": "Project Orion",
        "section": "Launch",
        "text": text or f"Project Orion checkpoint batch text {index}.",
        "text_sha256": f"sha-index-{index}",
        "source_uri_hash": "uri-sha",
        "source_hash": "source-sha",
        "ingestion_run_id": "ingestion-nonprod",
        "ingestion_version": "v1",
        "namespace": "actual_rag_eval_nonprod",
        "visibility": "nonprod",
    }


def test_weaviate_retrieval_backend_cli_choices_are_available() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "--dataset",
            "ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv",
            "--retrieval-surface",
            "source-native",
            "--retrieval-backend",
            "weaviate-hybrid",
            "--output-mode",
            "single",
        ]
    )

    assert args.retrieval_backend == "weaviate-hybrid"


def test_weaviate_source_atom_config_and_schema_are_nonprod_filterable() -> None:
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_GRPC_PORT": "50051",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_TIMEOUT_SECONDS": "12",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
            "EMBEDDING_DEVICE": "auto",
        }
    )
    schema = build_weaviate_source_atom_schema(config)
    properties = {row["name"]: row for row in schema["properties"]}

    assert config.configured is True
    assert config.production_namespace is False
    assert schema["schema_version"] == "weaviate_source_atom_v1"
    assert schema["vectorizer"] == "none"
    assert set(WEAVIATE_SOURCE_ATOM_REQUIRED_PROPERTIES).issubset(properties)
    for field in (
        "source_atom_id",
        "doc_id",
        "chunk_id",
        "evidence_bundle_id",
        "source_family",
        "source_track",
        "namespace",
        "visibility",
    ):
        assert properties[field]["index_filterable"] is True
    assert properties["text"]["index_searchable"] is True
    assert properties["title"]["index_searchable"] is True
    assert properties["text"]["tokenization"] == "word"
    for field in (
        "source_family",
        "granularity",
        "retrieval_route",
        "vectorized_semantic_content",
        "doc_id",
        "chunk_id",
        "evidence_bundle_id",
        "namespace",
        "visibility",
    ):
        assert properties[field]["index_filterable"] is True
        assert properties[field]["index_searchable"] is False
        assert properties[field]["tokenization"] == "field"


def test_weaviate_route_taxonomy_uses_source_owned_metadata_only() -> None:
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    row = {
        "source_atom_id": "srcatom-v1-pdf-route",
        "evidence_bundle_id": "bundle-v1-pdf-route",
        "source_family": "PDF",
        "text": "page 8 paragraph text from a source-owned PDF atom",
        "metadata": {
            "doc_id": "doc-pdf",
            "source_identity": "doc-pdf:report.pdf:8:[1,2,3,4]",
            "region_type": "paragraph",
            "target_column": "paragraph_text",
            "search_view_kind": "source_atom_embedding_view",
        },
    }

    taxonomy = derive_weaviate_route_taxonomy(row)
    record = source_atom_record_from_mapping(row, config)

    assert taxonomy["source_family"] == "PDF"
    assert taxonomy["granularity"] == "paragraph"
    assert taxonomy["retrieval_route"] == "pdf_paragraph"
    assert taxonomy["route_taxonomy_source"] == "source_owned_metadata_only"
    assert taxonomy["route_taxonomy_uses_gold_fields"] is False
    assert taxonomy["route_taxonomy_uses_expected_fields"] is False
    assert taxonomy["route_taxonomy_uses_qrels"] is False
    assert taxonomy["route_taxonomy_uses_labels"] is False
    assert taxonomy["route_taxonomy_uses_ids_or_legacy_outputs"] is False
    assert taxonomy["route_taxonomy_uses_legacy_fields"] is False
    assert record["source_family"] == "PDF"
    assert record["granularity"] == "paragraph"
    assert record["retrieval_route"] == "pdf_paragraph"
    assert record["vectorized_semantic_content"] == "true"

    with pytest.raises(ValueError, match="forbidden_candidate_generation_field"):
        derive_weaviate_route_taxonomy({**row, "expected_answer": "do not use me"})


def test_weaviate_route_taxonomy_rejects_all_gold_qrels_label_id_and_legacy_fields() -> None:
    row = {
        "source_atom_id": "srcatom-v1-text-route",
        "evidence_bundle_id": "bundle-v1-text-route",
        "source_family": "TEXT",
        "text": "source-owned paragraph text",
        "metadata": {"doc_id": "doc-text", "region_type": "paragraph"},
    }

    for field in (
        "expected_answer",
        "expected_evidence",
        "qrels",
        "gold_label",
        "labels",
        "query_id",
        "row_id",
        "search_unit_id",
        "search_view_id",
        "legacy_output",
    ):
        with pytest.raises(ValueError, match="forbidden_candidate_generation_field"):
            derive_weaviate_route_taxonomy({**row, field: "forbidden"})
        with pytest.raises(ValueError, match="forbidden_candidate_generation_field"):
            derive_weaviate_route_taxonomy({**row, "metadata": {**row["metadata"], field: "forbidden"}})


def test_weaviate_route_planner_uses_query_text_only_and_reports_filters() -> None:
    plan = plan_weaviate_retrieval_route("2020년 11월 sheet cell row amount 승인 금액은?")

    assert plan["selected_route"] == "xlsx_table"
    assert plan["selected_source_family_filter"] == ["XLSX"]
    assert "table_row" in plan["selected_granularity_filter"]
    assert plan["route_confidence"] >= 0.7
    assert plan["route_planner_version"] == "weaviate_route_planner_v1"
    assert plan["route_uses_gold_fields"] is False
    assert plan["route_uses_expected_fields"] is False
    assert plan["route_uses_qrels"] is False
    assert plan["route_uses_labels"] is False
    assert plan["route_uses_ids"] is False
    assert plan["route_uses_legacy_fields"] is False

    ambiguous = plan_weaviate_retrieval_route("문서에 적힌 주요 내용은 무엇인가요?")

    assert ambiguous["selected_route"] == "mixed_fallback"
    assert ambiguous["route_confidence"] < plan["route_confidence"]

    care_facility = plan_weaviate_retrieval_route("2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?")
    industry_pdf = plan_weaviate_retrieval_route("1월 산업활동에서 생산 지표는 어떻게 움직였나요?")

    assert care_facility["selected_route"] == "xlsx_table"
    assert care_facility["selected_source_family_filter"] == ["XLSX"]
    assert industry_pdf["selected_route"] == "pdf_paragraph"
    assert industry_pdf["selected_source_family_filter"] == ["PDF"]

    text_hint = plan_weaviate_retrieval_route(
        "2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?",
        source_family_hint="text",
    )
    pdf_hint = plan_weaviate_retrieval_route(
        "2020년 11월 sheet cell row amount 승인 금액은?",
        source_family_hint="pdf",
    )

    assert text_hint["selected_route"] == "text_general"
    assert text_hint["selected_source_family_filter"] == ["TEXT"]
    assert text_hint["source_family_hint"] == "text"
    assert "query_evidence_source_family_hint" in text_hint["route_reasons"]
    assert pdf_hint["selected_route"] == "pdf_paragraph"
    assert pdf_hint["selected_source_family_filter"] == ["PDF"]
    assert pdf_hint["route_uses_gold_fields"] is False


def test_weaviate_route_selected_lane_filter_plan_uses_query_evidence_source_family_hint() -> None:
    class Config:
        namespace = "actual_rag_eval_nonprod"
        visibility = "private"
        index_manifest_path = ""

    adapter = WeaviateSourceAtomAdapter.__new__(WeaviateSourceAtomAdapter)
    adapter.retrieval_route_mode = "route_selected"
    adapter.config_obj = Config()
    adapter._route_filter_fields_available_override = {"granularity": True, "retrieval_route": True}
    adapter._index_manifest = {}

    filters, plan = adapter._lane_filter_plan(
        "2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?",
        source_family_hint="text",
    )

    assert filters["source_family"] == "TEXT"
    assert filters["retrieval_route"] == "text_general"
    assert plan["source_family_hint"] == "text"
    assert plan["selected_source_family_filter"] == ["TEXT"]
    assert plan["weaviate_filter_policy"]["source_family_filter_sent"] is True


def test_weaviate_adapter_ignores_stale_query_evidence_planner_hash() -> None:
    class Config:
        namespace = "actual_rag_eval_nonprod"
        visibility = "private"
        index_manifest_path = ""

    adapter = WeaviateSourceAtomAdapter.__new__(WeaviateSourceAtomAdapter)
    adapter.retrieval_route_mode = "route_selected"
    adapter.config_obj = Config()
    adapter._route_filter_fields_available_override = {"granularity": True, "retrieval_route": True}
    adapter._index_manifest = {}
    query = "2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?"
    stale_query = "해오름요양원의 기관별 상세주소는 무엇입니까?"
    planner = {
        "planner_status": "planned_validated",
        "source_family_hint": "text",
        "query_sha256": f"sha256:{hashlib.sha256(stale_query.encode('utf-8')).hexdigest()}",
    }

    source_family_hint = adapter._query_evidence_source_family_hint_for_query(query, planner)
    filters, plan = adapter._lane_filter_plan(query, source_family_hint=source_family_hint)

    assert source_family_hint == ""
    assert filters["source_family"] == "XLSX"
    assert plan["selected_source_family_filter"] == ["XLSX"]
    assert "query_evidence_source_family_hint" not in plan["route_reasons"]


def test_weaviate_existing_collection_schema_mismatch_fails_closed() -> None:
    class ExistingProperty:
        def __init__(self, name: str, *, filterable: bool = False, searchable: bool = False, tokenization: str = "field") -> None:
            self.name = name
            self.index_filterable = filterable
            self.index_searchable = searchable
            self.tokenization = tokenization

    class ExistingCollectionConfig:
        vectorizer = "none"
        vector_config = {}

        def __init__(self) -> None:
            self.properties = [
                ExistingProperty("source_atom_id", filterable=True, tokenization="field"),
            ]

    class ExistingCollection:
        class Config:
            def get(self) -> ExistingCollectionConfig:
                return ExistingCollectionConfig()

        config = Config()

    class ExistingCollections:
        def exists(self, name: str) -> bool:
            return True

        def use(self, name: str) -> ExistingCollection:
            return ExistingCollection()

    class ExistingClient:
        collections = ExistingCollections()

    class ExistingSchemaWeaviateClient(WeaviateSourceAtomClient):
        def _connect(self) -> ExistingClient:
            return ExistingClient()

    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    client = ExistingSchemaWeaviateClient(config)

    with pytest.raises(WeaviateUnavailableError, match="collection_schema_mismatch"):
        client.ensure_collection(build_weaviate_source_atom_schema(config))


def test_weaviate_existing_v2_collection_adds_missing_metadata_properties() -> None:
    class ExistingProperty:
        def __init__(self, name: str, *, filterable: bool = False, searchable: bool = False, tokenization: str = "field") -> None:
            self.name = name
            self.index_filterable = filterable
            self.index_searchable = searchable
            self.tokenization = tokenization

    class ExistingCollectionConfig:
        vectorizer = "none"
        vector_config = {}

        def __init__(self, properties: list[object]) -> None:
            self.properties = properties

    class ExistingCollection:
        def __init__(self, properties: list[object]) -> None:
            self._properties = properties
            self.added_property_names: list[str] = []
            self.config = self.Config(self)

        class Config:
            def __init__(self, collection: "ExistingCollection") -> None:
                self.collection = collection

            def get(self) -> ExistingCollectionConfig:
                return ExistingCollectionConfig(list(self.collection._properties))

            def add_property(self, prop: object) -> None:
                self.collection.added_property_names.append(str(getattr(prop, "name", "")))
                self.collection._properties.append(prop)

    class ExistingCollections:
        def __init__(self, collection: ExistingCollection) -> None:
            self.collection = collection

        def exists(self, name: str) -> bool:
            return True

        def use(self, name: str) -> ExistingCollection:
            return self.collection

    class ExistingClient:
        def __init__(self, collection: ExistingCollection) -> None:
            self.collections = ExistingCollections(collection)

    class ExistingSchemaWeaviateClient(WeaviateSourceAtomClient):
        def __init__(self, config: WeaviateSourceAtomConfig, collection: ExistingCollection) -> None:
            super().__init__(config)
            self._fake_client = ExistingClient(collection)

        def _connect(self) -> ExistingClient:
            return self._fake_client

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
    schema = build_weaviate_source_atom_schema(config)
    missing_v2_names = {"row_label", "column_label", "target_column", "header", "header_path", "table_id"}
    existing_properties = [
        ExistingProperty(
            prop["name"],
            filterable=bool(prop["index_filterable"]),
            searchable=bool(prop["index_searchable"]),
            tokenization=str(prop["tokenization"]),
        )
        for prop in schema["properties"]
        if prop["name"] not in missing_v2_names
    ]
    collection = ExistingCollection(existing_properties)
    client = ExistingSchemaWeaviateClient(config, collection)

    client.ensure_collection(schema)

    assert sorted(collection.added_property_names) == sorted(missing_v2_names)
    assert set(collection.added_property_names).issubset(set(WEAVIATE_SOURCE_ATOM_V2_EXTRA_PROPERTIES))


def test_weaviate_existing_v2_schema_repair_does_not_partially_mutate_on_mismatch() -> None:
    class ExistingProperty:
        def __init__(self, name: str, *, filterable: bool = False, searchable: bool = False, tokenization: str = "field") -> None:
            self.name = name
            self.index_filterable = filterable
            self.index_searchable = searchable
            self.tokenization = tokenization

    class ExistingCollectionConfig:
        vectorizer = "none"
        vector_config = {}

        def __init__(self, properties: list[object]) -> None:
            self.properties = properties

    class ExistingCollection:
        def __init__(self, properties: list[object]) -> None:
            self._properties = properties
            self.added_property_names: list[str] = []
            self.config = self.Config(self)

        class Config:
            def __init__(self, collection: "ExistingCollection") -> None:
                self.collection = collection

            def get(self) -> ExistingCollectionConfig:
                return ExistingCollectionConfig(list(self.collection._properties))

            def add_property(self, prop: object) -> None:
                self.collection.added_property_names.append(str(getattr(prop, "name", "")))
                self.collection._properties.append(prop)

    class ExistingCollections:
        def __init__(self, collection: ExistingCollection) -> None:
            self.collection = collection

        def exists(self, name: str) -> bool:
            return True

        def use(self, name: str) -> ExistingCollection:
            return self.collection

    class ExistingClient:
        def __init__(self, collection: ExistingCollection) -> None:
            self.collections = ExistingCollections(collection)

    class ExistingSchemaWeaviateClient(WeaviateSourceAtomClient):
        def __init__(self, config: WeaviateSourceAtomConfig, collection: ExistingCollection) -> None:
            super().__init__(config)
            self._fake_client = ExistingClient(collection)

        def _connect(self) -> ExistingClient:
            return self._fake_client

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
    schema = build_weaviate_source_atom_schema(config)
    missing_v2_names = {"row_label", "column_label"}
    existing_properties = []
    for prop in schema["properties"]:
        if prop["name"] in missing_v2_names:
            continue
        tokenization = str(prop["tokenization"])
        if prop["name"] == "text":
            tokenization = "field"
        existing_properties.append(
            ExistingProperty(
                prop["name"],
                filterable=bool(prop["index_filterable"]),
                searchable=bool(prop["index_searchable"]),
                tokenization=tokenization,
            )
        )
    collection = ExistingCollection(existing_properties)
    client = ExistingSchemaWeaviateClient(config, collection)

    with pytest.raises(WeaviateUnavailableError, match="tokenization_mismatch:text"):
        client.ensure_collection(schema)

    assert collection.added_property_names == []


def test_weaviate_checkpoint_atomic_write_retries_transient_windows_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "index_checkpoint.json"
    original_replace = type(path).replace
    calls = {"count": 0}

    def flaky_replace(self: Path, target: Path) -> Path:
        if self.name == "index_checkpoint.json.tmp" and calls["count"] == 0:
            calls["count"] += 1
            raise PermissionError("transient Windows file lock")
        return original_replace(self, target)

    monkeypatch.setattr(type(path), "replace", flaky_replace)
    monkeypatch.setattr("ai.eval.weaviate_source_atom.time.sleep", lambda seconds: None)

    _write_json_atomic(path, {"ok": True})

    assert calls["count"] == 1
    assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}


def test_weaviate_source_atom_adapter_reports_service_boundary_without_local_fallback(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_hybrid"
    write_jsonl(dataset, [{"id": "q1", "query": "Project Orion April 2026", "answerability": "unknown"}])
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprod",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
            "EMBEDDING_DEVICE": "auto",
        }
    )
    client = FakeWeaviateSourceAtomClient(
        objects=[
            {
                "source_atom_id": "srcatom-weaviate-1",
                "evidence_bundle_id": "bundle-weaviate-1",
                "doc_id": "doc-weaviate",
                "chunk_id": "chunk-weaviate-1",
                "source_family": "TEXT",
                "source_track": "namu",
                "title": "Project Orion",
                "section": "Launch",
                "text": "Project Orion launch is scheduled for April 2026.",
                "text_sha256": "sha-weaviate-1",
                "source_uri_hash": "uri-sha",
                "source_hash": "source-sha",
                "ingestion_run_id": "ingestion-nonprod",
                "ingestion_version": "v1",
                "namespace": "actual_rag_eval_nonprod",
                "visibility": "nonprod",
            }
        ]
    )
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=10,
        run_id="weaviate_hybrid",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    assert report["artifact_contract"]["route_ab_sidecar_exception"] is False
    assert report["artifact_contract"]["route_ab_artifacts_allowed_only_by_weaviate_route_ab_mode"] is True
    assert report["artifact_paths"]["route_selected_hybrid_evidence_store_ab_report_json"] == ""
    assert report["artifact_paths"]["route_selected_hybrid_evidence_store_ab_items_jsonl"] == ""
    assert not (output_dir / "route_selected_hybrid_evidence_store_ab_report.json").exists()
    assert not (output_dir / "route_selected_hybrid_evidence_store_ab_items.jsonl").exists()
    assert client.query_log[0]["mode"] == "hybrid"
    assert client.query_log[0]["filters"] == {"namespace": "actual_rag_eval_nonprod", "visibility": "nonprod"}
    assert client.query_log[0]["query_text"] == "Project Orion April 2026"
    assert client.query_log[0]["vector_dim"] == 4
    for query_payload in client.query_log:
        for forbidden in (
            "expected_answer",
            "expected_evidence",
            "qrels",
            "gold_label",
            "labels",
            "query_id",
            "row_id",
            "target_id",
            "legacy_output",
        ):
            assert forbidden not in query_payload
    assert report["active_retrieval_backend"] == "weaviate_hybrid"
    assert report["active_retrieval_service_boundary"] == "weaviate"
    assert report["retrieval_backend"]["selected"] == "weaviate_hybrid"
    assert report["retrieval_backend"]["embedding_model"] == "BAAI/bge-m3"
    assert report["retrieval_backend"]["vector_index_kind"] == "weaviate_hnsw"
    assert report["external_vector_db"]["configured"] is True
    assert report["external_vector_db"]["invoked"] is True
    assert report["external_vector_db"]["backend"] == "weaviate"
    assert report["external_vector_db"]["production_namespace"] is False
    assert report["python_local_corpus_scan_used_for_candidate_generation"] is False
    assert report["source_native_layered_retrieval_used_for_candidate_generation"] is False
    assert report["diagnostic_hash_vector_used"] is False
    assert report["faiss_used_for_active_retrieval"] is False
    assert report["searchunit_searchview_used_as_candidate_surface"] is False
    assert report["source_native_layered_retrieval"]["enabled"] is False
    assert report["vector_index_audit"]["vector_backend"] == "weaviate"
    assert report["candidate_generation_input_policy"] == "query_text_and_query_embedding_only_no_gold_qrels_labels_ids_or_baseline"
    assert report["items"][0]["retrieved_contexts"][0]["source_atom_id"] == "srcatom-weaviate-1"


def test_weaviate_text_only_lane_sends_text_family_filter_to_weaviate(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_text_only"
    write_jsonl(dataset, [{"id": "q1", "query": "Project Orion April 2026", "answerability": "unknown"}])
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
                **weaviate_source_atom_record(1, text="Project Orion launch is scheduled for April 2026."),
                "granularity": "paragraph",
                "retrieval_route": "text_general",
            },
            {
                **weaviate_source_atom_record(2, text="Project Orion PDF table noise."),
                "source_family": "PDF",
                "granularity": "table_row",
                "retrieval_route": "pdf_table",
            },
        ]
    )
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="text_only",
        route_filter_fields_available={"source_family": True, "granularity": True},
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=5,
        run_id="weaviate_text_only",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert all(query["filters"]["source_family"] == "TEXT" for query in client.query_log)
    assert all(query["filters"]["granularity"] == ["paragraph", "heading_context_block", "caption"] for query in client.query_log)
    assert report["weaviate_filter_sent"] is True
    assert report["weaviate_filter_policy"]["route_mode"] == "text_only"
    assert report["weaviate_filter_policy"]["python_post_filtering"] == "safety_validation_only"
    assert report["items"][0]["retrieved_contexts"][0]["source_family"] == "TEXT"


def test_weaviate_mixed_pool_lane_intentionally_allows_all_source_families(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_mixed_pool"
    write_jsonl(dataset, [{"id": "q1", "query": "Project Orion April 2026", "answerability": "unknown"}])
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
                **weaviate_source_atom_record(2, text="PDF Project Orion table noise."),
                "source_family": "PDF",
                "granularity": "table_row",
                "retrieval_route": "pdf_table",
            },
            {
                **weaviate_source_atom_record(3, text="XLSX Project Orion cell noise."),
                "source_family": "XLSX",
                "granularity": "cell",
                "retrieval_route": "xlsx_table",
            },
        ]
    )
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="mixed_pool",
        route_filter_fields_available={"source_family": True, "granularity": True},
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=5,
        run_id="weaviate_mixed_pool",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert all(query["filters"]["source_family"] == ["TEXT", "PDF", "XLSX"] for query in client.query_log)
    assert all("granularity" not in query["filters"] for query in client.query_log)
    assert report["weaviate_filter_policy"]["route_mode"] == "mixed_pool"
    assert {context["source_family"] for context in report["items"][0]["retrieved_contexts"]} == {"TEXT", "PDF", "XLSX"}


def test_weaviate_route_selected_lane_sends_planner_filters_to_weaviate(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_route_selected"
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
        route_filter_fields_available={"source_family": True, "granularity": True, "retrieval_route": True},
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=5,
        run_id="weaviate_route_selected",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert all(query["filters"]["source_family"] == "XLSX" for query in client.query_log)
    assert all(query["filters"]["granularity"] == ["table_summary", "table_row", "cell"] for query in client.query_log)
    assert all(query["filters"]["retrieval_route"] == "xlsx_table" for query in client.query_log)
    assert report["weaviate_filter_policy"]["route_mode"] == "route_selected"
    assert report["weaviate_filter_policy"]["base_filter_sent"] is True
    assert report["weaviate_filter_policy"]["route_filter_sent"] is True
    assert report["weaviate_filter_policy"]["retrieval_route_filter_sent"] is True
    assert report["weaviate_filter_policy"]["requested_retrieval_route_filter"] == ["xlsx_table"]
    assert report["items"][0]["weaviate_route_plan"]["selected_route"] == "xlsx_table"
    assert report["items"][0]["weaviate_route_plan"]["route_uses_gold_fields"] is False
    assert report["items"][0]["retrieved_contexts"][0]["source_family"] == "XLSX"


def test_weaviate_route_selected_text_query_uses_query_only_number_and_anchor_variants(tmp_path: Path) -> None:
    class AliasSensitiveWeaviateClient(FakeWeaviateSourceAtomClient):
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
            query_text = str(kwargs["query_text"])
            filters = kwargs["filters"]

            def matches(obj: dict, key: str, value: object) -> bool:
                if not value:
                    return True
                if isinstance(value, list):
                    return obj.get(key) in value
                return obj.get(key) == value

            alias_query = "엑스맨" in query_text and "97" in query_text and "애드버서리" in query_text
            rows: list[dict] = []
            for obj in self.objects:
                if not all(matches(obj, key, value) for key, value in dict(filters).items()):
                    continue
                if alias_query and obj.get("source_atom_id") == "srcatom-xmen-97-adversary":
                    row = dict(obj)
                    row["_score"] = 1.0
                    row["_backend"] = kwargs["mode"]
                    rows.append(row)
            return rows[: int(kwargs["limit"])]

    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_route_selected_alias_variants"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "엑스맨 구십칠 등장인물 목록에 애드버서리는 어떤 식으로 올라와",
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
    client = AliasSensitiveWeaviateClient(
        objects=[
            {
                **weaviate_source_atom_record(
                    97,
                    text="엑스맨 '97 등장인물 목록에는 애드버서리 - 앨리슨 실리스미스 [카메오] 항목이 있다.",
                ),
                "source_atom_id": "srcatom-xmen-97-adversary",
                "evidence_bundle_id": "bundle-xmen-97-adversary",
                "doc_id": "text_namu_v2_1",
                "chunk_id": "98f5315b62c0282c",
                "title": "엑스맨 '97 등장인물",
                "granularity": "paragraph",
                "retrieval_route": "text_general",
            }
        ]
    )
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
        run_id="weaviate_route_selected_alias_variants",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    alias_queries = [
        query["query_text"]
        for query in client.query_log
        if "엑스맨" in query["query_text"] and "97" in query["query_text"] and "애드버서리" in query["query_text"]
    ]
    assert alias_queries
    assert report["items"][0]["retrieved_contexts"][0]["source_atom_id"] == "srcatom-xmen-97-adversary"
    assert report["items"][0]["retrieved_contexts"][0]["query_variant_provenance"] == [alias_queries[0]]
    assert report["items"][0]["weaviate_query_reformulation"]["uses_expected_fields"] is False
    assert report["items"][0]["weaviate_query_reformulation"]["uses_gold_fields"] is False
    assert report["items"][0]["weaviate_query_reformulation"]["uses_ids"] is False
    assert report["candidate_generation_input_policy"] == "query_text_and_query_embedding_only_no_gold_qrels_labels_ids_or_baseline"
    for query_payload in client.query_log:
        assert "expected_answer" not in query_payload
        assert "expected_evidence" not in query_payload
        assert "row_id" not in query_payload


def test_weaviate_route_selected_query_variants_probe_same_doc_without_gold_ids(tmp_path: Path) -> None:
    class SameDocSensitiveWeaviateClient(FakeWeaviateSourceAtomClient):
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
            query_text = str(kwargs["query_text"])
            filters = dict(kwargs["filters"])
            doc_filter = filters.get("doc_id")
            alias_title_query = "엑스맨" in query_text and "97" in query_text
            alias_entity_query = alias_title_query and "애드버서리" in query_text
            rows: list[dict] = []
            for obj in self.objects:
                if _filter_mismatch(obj, filters):
                    continue
                if doc_filter:
                    if alias_entity_query and obj.get("source_atom_id") == "srcatom-xmen-97-adversary":
                        row = dict(obj)
                        row["_score"] = 1.0
                        row["_backend"] = kwargs["mode"]
                        rows.append(row)
                    continue
                if alias_title_query and obj.get("source_atom_id") == "srcatom-xmen-97-overview":
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
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_route_selected_same_doc_variants"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "엑스맨 구십칠 등장인물 목록에 애드버서리는 어떤 식으로 올라와",
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
    client = SameDocSensitiveWeaviateClient(
        objects=[
            {
                **weaviate_source_atom_record(
                    971,
                    text="TV 애니메이션 시리즈 〈 엑스맨 '97 〉의 첫 번째 시즌이다.",
                ),
                "source_atom_id": "srcatom-xmen-97-overview",
                "evidence_bundle_id": "bundle-xmen-97-overview",
                "doc_id": "doc-xmen-97",
                "chunk_id": "chunk-xmen-97-overview",
                "title": "엑스맨 '97",
                "granularity": "paragraph",
                "retrieval_route": "text_general",
            },
            {
                **weaviate_source_atom_record(
                    972,
                    text="엑스맨 '97 등장인물 목록에는 애드버서리 - 앨리슨 실리스미스 [카메오] 항목이 있다.",
                ),
                "source_atom_id": "srcatom-xmen-97-adversary",
                "evidence_bundle_id": "bundle-xmen-97-adversary",
                "doc_id": "doc-xmen-97",
                "chunk_id": "chunk-xmen-97-adversary",
                "title": "엑스맨 '97 등장인물",
                "granularity": "paragraph",
                "retrieval_route": "text_general",
            },
        ]
    )
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
        run_id="weaviate_route_selected_same_doc_variants",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    contexts = report["items"][0]["retrieved_contexts"]
    same_doc_queries = [query for query in client.query_log if query["filters"].get("doc_id") == "doc-xmen-97"]
    assert same_doc_queries
    assert any("애드버서리" in query["query_text"] for query in same_doc_queries)
    assert contexts[0]["source_atom_id"] == "srcatom-xmen-97-adversary"
    assert contexts[0]["same_doc_residual_expansion_policy"] == "bounded_query_variant_same_doc_weaviate_v1"
    assert report["weaviate_post_processing"]["same_doc_residual_query_count"] >= 1
    assert report["weaviate_post_processing"]["same_doc_residual_added_count"] == 1
    for query_payload in client.query_log:
        assert "expected_answer" not in query_payload
        assert "expected_evidence" not in query_payload
        assert "row_id" not in query_payload
        assert "target_id" not in query_payload


def test_xlsx_same_table_vector_expansion_is_bounded_by_source_owned_scope(tmp_path: Path) -> None:
    class SameTableSensitiveWeaviateClient(FakeWeaviateSourceAtomClient):
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
            scoped = filters.get("doc_id") == "doc-subway" and filters.get("sheet") == "2019년 2월"
            scoped = scoped and filters.get("table_id") == "subway-201902-main"
            rows: list[dict] = []
            for obj in self.objects:
                if _filter_mismatch(obj, filters):
                    continue
                source_atom_id = obj.get("source_atom_id")
                if scoped and source_atom_id == "srcatom-subway-5line-target":
                    row = dict(obj)
                    row["_score"] = 1.0
                    row["_backend"] = kwargs["mode"]
                    rows.append(row)
                elif not scoped and source_atom_id == "srcatom-subway-table-summary":
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
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_same_table_scope"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx-same-table",
                "query": "2019년 2월 5호선 승차총승객수",
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
                701,
                text="2019년 2월 지하철 승하차 표는 노선별 승차총승객수와 하차총승객수를 제공한다.",
            ),
            "source_atom_id": "srcatom-subway-table-summary",
            "evidence_bundle_id": "bundle-subway-table-summary",
            "doc_id": "doc-subway",
            "chunk_id": "chunk-subway-table-summary",
            "source_family": "XLSX",
            "granularity": "table_summary",
            "retrieval_route": "xlsx_table",
            "sheet": "2019년 2월",
            "cell_range": "A1:J30",
            "table_id": "subway-201902-main",
        },
        config,
    )
    target = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                702,
                text="2019년 2월 5호선 승차총승객수는 15,446,522명입니다.",
            ),
            "source_atom_id": "srcatom-subway-5line-target",
            "evidence_bundle_id": "bundle-subway-5line-target",
            "doc_id": "doc-subway",
            "chunk_id": "chunk-subway-5line-target",
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
            "table_id": "subway-201902-main",
        },
        config,
    )
    wrong_sheet = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                703,
                text="2019년 3월 5호선 승차총승객수는 15,446,522명입니다.",
            ),
            "source_atom_id": "srcatom-subway-wrong-sheet",
            "evidence_bundle_id": "bundle-subway-wrong-sheet",
            "doc_id": "doc-subway",
            "chunk_id": "chunk-subway-wrong-sheet",
            "source_family": "XLSX",
            "granularity": "table_row",
            "retrieval_route": "xlsx_table",
            "sheet": "2019년 3월",
            "row_label": "5호선",
            "column_label": "승차총승객수",
            "target_column": "승차총승객수",
            "table_id": "subway-201903-main",
        },
        config,
    )
    client = SameTableSensitiveWeaviateClient(objects=[summary, target, wrong_sheet])
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
        run_id="xlsx_same_table_scope",
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
    scoped_queries = [query for query in client.query_log if query["filters"].get("table_id") == "subway-201902-main"]
    assert scoped_queries
    assert contexts[0]["source_atom_id"] == "srcatom-subway-5line-target"
    assert contexts[0]["xlsx_scoped_expansion_policy"] == "bounded_source_owned_xlsx_scope_weaviate_v1"
    assert contexts[0]["xlsx_scoped_expansion_scope_type"] == "same_table"
    assert all(query["filters"]["source_family"] == "XLSX" for query in scoped_queries)
    assert all(query["filters"]["sheet"] == "2019년 2월" for query in scoped_queries)
    assert all(query["filters"]["doc_id"] == "doc-subway" for query in scoped_queries)
    assert report["items"][0]["weaviate_xlsx_scoped_expansion"]["added_count"] == 1
    assert report["items"][0]["weaviate_xlsx_scoped_expansion"]["uses_ids"] is False
    assert report["items"][0]["weaviate_xlsx_scoped_expansion"]["uses_protected_eval_ids"] is False
    assert report["items"][0]["weaviate_xlsx_scoped_expansion"]["uses_source_owned_scope_ids"] is True
    assert report["weaviate_post_processing"]["xlsx_scoped_expansion_added_count"] == 1
    query_payload = json.dumps(client.query_log, ensure_ascii=False)
    assert "expected_answer" not in query_payload
    assert "expected_evidence" not in query_payload
    assert "qrels" not in query_payload
    assert "labels" not in query_payload
    assert "row_id" not in query_payload
    assert "target_id" not in query_payload
    assert "formula" not in query_payload
    assert "normalized_value" not in query_payload
    assert output_file_names(output_dir) == ["report.json"]


def test_xlsx_scoped_expansion_query_uses_source_owned_axis_terms(tmp_path: Path) -> None:
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
                filters.get("source_family") == "XLSX"
                and filters.get("doc_id") == "doc-subway"
                and filters.get("sheet") == "2019년 2월"
                and filters.get("table_id") == "subway-201902-main"
            )
            rows: list[dict] = []
            for obj in self.objects:
                if _filter_mismatch(obj, filters):
                    continue
                source_atom_id = obj.get("source_atom_id")
                if scoped and source_atom_id == "srcatom-subway-5line-target":
                    if "승차총승객수" not in query_text:
                        continue
                    row = dict(obj)
                    row["_score"] = 1.0
                    row["_backend"] = kwargs["mode"]
                    rows.append(row)
                elif not scoped and source_atom_id == "srcatom-subway-table-summary":
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
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_source_axis_scope"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx-source-axis-scope",
                "query": "2019년 2월 5호선 승차 인원은 얼마야?",
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
                704,
                text="2019년 2월 지하철 승하차 표는 노선별 승차와 하차 인원을 제공한다.",
            ),
            "source_atom_id": "srcatom-subway-table-summary",
            "evidence_bundle_id": "bundle-subway-table-summary",
            "doc_id": "doc-subway",
            "chunk_id": "chunk-subway-table-summary",
            "source_family": "XLSX",
            "granularity": "table_summary",
            "retrieval_route": "xlsx_table",
            "sheet": "2019년 2월",
            "cell_range": "A1:J30",
            "table_id": "subway-201902-main",
            "row_label": "5호선",
            "column_label": "승차총승객수",
            "target_column": "승차총승객수",
            "header_path": "승하차 > 승차총승객수",
        },
        config,
    )
    target = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                705,
                text="2019년 2월 5호선 승차총승객수는 15,446,522명입니다.",
            ),
            "source_atom_id": "srcatom-subway-5line-target",
            "evidence_bundle_id": "bundle-subway-5line-target",
            "doc_id": "doc-subway",
            "chunk_id": "chunk-subway-5line-target",
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
            "table_id": "subway-201902-main",
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
        run_id="xlsx_source_axis_scope",
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
    scoped_queries = [query for query in client.query_log if query["filters"].get("table_id") == "subway-201902-main"]
    assert scoped_queries
    assert contexts[0]["source_atom_id"] == "srcatom-subway-5line-target"
    assert any("승차총승객수" in query["query_text"] for query in scoped_queries)
    query_payload = json.dumps(client.query_log, ensure_ascii=False)
    assert "15,446,522" not in query_payload
    assert "expected_answer" not in query_payload
    assert "expected_evidence" not in query_payload
    assert "qrels" not in query_payload
    assert "labels" not in query_payload
    assert "row_id" not in query_payload
    assert "target_id" not in query_payload
    assert "formula" not in query_payload
    assert "normalized_value" not in query_payload
    assert output_file_names(output_dir) == ["report.json"]


def test_xlsx_scoped_expansion_filters_same_source_row_when_row_index_available(tmp_path: Path) -> None:
    class RowScopedWeaviateClient(FakeWeaviateSourceAtomClient):
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
            row_scoped = (
                filters.get("source_family") == "XLSX"
                and filters.get("doc_id") == "doc-care"
                and filters.get("sheet") == "일반현황"
                and filters.get("cell_range") == "A5002:J5051"
                and filters.get("row_index_1based") == "5002"
            )
            rows: list[dict] = []
            for obj in self.objects:
                if _filter_mismatch(obj, filters):
                    continue
                source_atom_id = obj.get("source_atom_id")
                if row_scoped and source_atom_id == "srcatom-care-date":
                    row = dict(obj)
                    row["_score"] = 1.0
                    row["_backend"] = kwargs["mode"]
                    rows.append(row)
                elif not row_scoped and source_atom_id == "srcatom-care-address":
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
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_same_source_row_scope"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx-same-source-row-scope",
                "query": "2015년 6월 부여효요양원 기관별 상세주소",
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
    address = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                706,
                text=(
                    "row_label=장기요양기관이름=부여효요양원 | "
                    "target_column=기관별 상세주소 | display_value=충청남도 부여군 석성면 왕릉로 773"
                ),
            ),
            "source_atom_id": "srcatom-care-address",
            "evidence_bundle_id": "bundle-care-address",
            "doc_id": "doc-care",
            "chunk_id": "chunk-care-address",
            "source_family": "XLSX",
            "granularity": "cell",
            "retrieval_route": "xlsx_cell_trace",
            "sheet": "일반현황",
            "cell_range": "A5002:J5051",
            "cell": "J5002",
            "row_index_1based": "5002",
            "row_label": "장기요양기관이름=부여효요양원",
            "column_label": "기관별 상세주소",
            "target_column": "기관별 상세주소",
            "display_value": "충청남도 부여군 석성면 왕릉로 773",
        },
        config,
    )
    date = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                707,
                text="row_label=장기요양기관이름=부여효요양원 | target_column=지정일자 | display_value=2015-06-01",
            ),
            "source_atom_id": "srcatom-care-date",
            "evidence_bundle_id": "bundle-care-date",
            "doc_id": "doc-care",
            "chunk_id": "chunk-care-date",
            "source_family": "XLSX",
            "granularity": "cell",
            "retrieval_route": "xlsx_cell_trace",
            "sheet": "일반현황",
            "cell_range": "A5002:J5051",
            "cell": "H5002",
            "row_index_1based": "5002",
            "row_label": "장기요양기관이름=부여효요양원",
            "column_label": "지정일자",
            "target_column": "지정일자",
            "display_value": "2015-06-01",
        },
        config,
    )
    wrong_row = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                708,
                text="row_label=장기요양기관이름=다른요양원 | target_column=지정일자 | display_value=2015-06-01",
            ),
            "source_atom_id": "srcatom-care-wrong-row-date",
            "evidence_bundle_id": "bundle-care-wrong-row-date",
            "doc_id": "doc-care",
            "chunk_id": "chunk-care-wrong-row-date",
            "source_family": "XLSX",
            "granularity": "cell",
            "retrieval_route": "xlsx_cell_trace",
            "sheet": "일반현황",
            "cell_range": "A5002:J5051",
            "cell": "H2",
            "row_index_1based": "2",
            "row_label": "장기요양기관이름=다른요양원",
            "column_label": "지정일자",
            "target_column": "지정일자",
            "display_value": "2015-06-01",
        },
        config,
    )
    client = RowScopedWeaviateClient(objects=[address, date, wrong_row])
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
        run_id="xlsx_same_source_row_scope",
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
    scoped_queries = [query for query in client.query_log if query["filters"].get("cell_range") == "A5002:J5051"]
    assert scoped_queries
    assert any(query["filters"].get("row_index_1based") == "5002" for query in scoped_queries)
    assert any(
        context["source_atom_id"] == "srcatom-care-date"
        and context["xlsx_scoped_expansion_scope_type"] == "same_cell_range_row"
        for context in contexts
    )
    assert all(context["source_atom_id"] != "srcatom-care-wrong-row-date" for context in contexts)
    query_payload = json.dumps(client.query_log, ensure_ascii=False)
    assert "expected_answer" not in query_payload
    assert "expected_evidence" not in query_payload
    assert "qrels" not in query_payload
    assert "labels" not in query_payload
    assert "row_id" not in query_payload
    assert "target_id" not in query_payload
    assert "formula" not in query_payload
    assert "normalized_value" not in query_payload
    assert output_file_names(output_dir) == ["report.json"]


def test_xlsx_scoped_expansion_post_filters_missing_or_wrong_row_index(tmp_path: Path) -> None:
    class OverbroadRowScopedWeaviateClient(FakeWeaviateSourceAtomClient):
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
            row_scoped = (
                filters.get("source_family") == "XLSX"
                and filters.get("doc_id") == "doc-care"
                and filters.get("sheet") == "일반현황"
                and filters.get("cell_range") == "A5002:J5051"
                and filters.get("row_index_1based") == "5002"
            )
            rows: list[dict] = []
            for obj in self.objects:
                source_atom_id = obj.get("source_atom_id")
                if row_scoped and source_atom_id in {"srcatom-care-missing-row-date", "srcatom-care-wrong-row-date"}:
                    row = dict(obj)
                    row["_score"] = 1.0
                    row["_backend"] = kwargs["mode"]
                    rows.append(row)
                    continue
                if not row_scoped and source_atom_id == "srcatom-care-address" and not _filter_mismatch(obj, filters):
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
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_same_source_row_scope_post_filter"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx-same-source-row-scope-post-filter",
                "query": "2015년 6월 부여효요양원 기관별 상세주소",
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
    common = {
        "doc_id": "doc-care",
        "source_family": "XLSX",
        "granularity": "cell",
        "retrieval_route": "xlsx_cell_trace",
        "sheet": "일반현황",
        "cell_range": "A5002:J5051",
    }
    address = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                709,
                text=(
                    "row_label=장기요양기관이름=부여효요양원 | "
                    "target_column=기관별 상세주소 | display_value=충청남도 부여군 석성면 왕릉로 773"
                ),
            ),
            **common,
            "source_atom_id": "srcatom-care-address",
            "evidence_bundle_id": "bundle-care-address",
            "chunk_id": "chunk-care-address",
            "cell": "J5002",
            "row_index_1based": "5002",
            "row_label": "장기요양기관이름=부여효요양원",
            "column_label": "기관별 상세주소",
            "target_column": "기관별 상세주소",
            "display_value": "충청남도 부여군 석성면 왕릉로 773",
        },
        config,
    )
    missing_row_date = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                710,
                text="row_label=장기요양기관이름=부여효요양원 | target_column=지정일자 | display_value=2015-06-01",
            ),
            **common,
            "source_atom_id": "srcatom-care-missing-row-date",
            "evidence_bundle_id": "bundle-care-missing-row-date",
            "chunk_id": "chunk-care-missing-row-date",
            "cell": "H5002",
            "row_label": "장기요양기관이름=부여효요양원",
            "column_label": "지정일자",
            "target_column": "지정일자",
            "display_value": "2015-06-01",
        },
        config,
    )
    wrong_row_date = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                711,
                text="row_label=장기요양기관이름=부여효요양원 | target_column=지정일자 | display_value=2015-06-01",
            ),
            **common,
            "source_atom_id": "srcatom-care-wrong-row-date",
            "evidence_bundle_id": "bundle-care-wrong-row-date",
            "chunk_id": "chunk-care-wrong-row-date",
            "cell": "H2",
            "row_index_1based": "2",
            "row_label": "장기요양기관이름=부여효요양원",
            "column_label": "지정일자",
            "target_column": "지정일자",
            "display_value": "2015-06-01",
        },
        config,
    )
    client = OverbroadRowScopedWeaviateClient(objects=[address, missing_row_date, wrong_row_date])
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
        run_id="xlsx_same_source_row_scope_post_filter",
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
    scoped_queries = [query for query in client.query_log if query["filters"].get("cell_range") == "A5002:J5051"]
    assert scoped_queries
    assert any(query["filters"].get("row_index_1based") == "5002" for query in scoped_queries)
    assert report["items"][0]["weaviate_xlsx_scoped_expansion"]["added_count"] == 0
    assert all(context["source_atom_id"] not in {"srcatom-care-missing-row-date", "srcatom-care-wrong-row-date"} for context in contexts)
    assert output_file_names(output_dir) == ["report.json"]


def test_xlsx_selected_evidence_requires_value_and_axes_to_cooccur() -> None:
    selected = select_composer_evidence(
        "2019년 2월 5호선 승차총승객수는 얼마야?",
        [
            {
                "doc_id": "doc-xlsx",
                "chunk_id": "chunk-value-only",
                "source_atom_id": "src-value-only",
                "evidence_bundle_id": "bundle-value-only",
                "source_family": "XLSX",
                "granularity": "table_row",
                "text": "15,446,522명",
            },
            {
                "doc_id": "doc-xlsx",
                "chunk_id": "chunk-axis-only",
                "source_atom_id": "src-axis-only",
                "evidence_bundle_id": "bundle-axis-only",
                "source_family": "XLSX",
                "granularity": "table_row",
                "text": "2019년 2월 5호선 승차총승객수 행입니다.",
                "sheet": "2019년 2월",
                "row_label": "5호선",
                "column_label": "승차총승객수",
                "target_column": "승차총승객수",
            },
            {
                "doc_id": "doc-xlsx",
                "chunk_id": "chunk-value-axis",
                "source_atom_id": "src-value-axis",
                "evidence_bundle_id": "bundle-value-axis",
                "source_family": "XLSX",
                "granularity": "table_row",
                "text": "2019년 2월 5호선 승차총승객수는 15,446,522명입니다.",
                "sheet": "2019년 2월",
                "row_label": "5호선",
                "column_label": "승차총승객수",
                "target_column": "승차총승객수",
            },
        ],
    )

    assert [row["source_atom_id"] for row in selected] == ["src-value-axis"]


def test_weaviate_query_variants_build_collision_aware_anchor_queries_from_query_text_only() -> None:
    plan = plan_weaviate_query_variants("엑스맨 구십칠 등장인물 목록에 애드버서리는 어떤 식으로 올라와")

    joined = " ".join(plan["query_variants"])
    assert "Adversary" not in joined
    assert "X-Men" not in joined
    assert "엑스맨 '97 등장인물 목록 애드버서리" in plan["query_variants"]
    assert "애드버서리 엑스맨 '97 등장인물 목록" not in plan["query_variants"]
    assert "collision_aware_anchor_query" not in plan["reasons"]
    assert "korean_sino_number_normalization" in plan["normalization_policies"]
    assert "punctuation_normalization" in plan["normalization_policies"]
    assert "query_text_only_content_anchor_compaction" in plan["normalization_policies"]
    assert "collision_aware_query_formulation" not in plan["normalization_policies"]
    assert plan["uses_expected_fields"] is False
    assert plan["uses_gold_fields"] is False
    assert plan["uses_ids"] is False
    assert plan["uses_qrels"] is False
    assert plan["uses_labels"] is False
    assert plan["uses_baseline_topk"] is False
    assert plan["uses_legacy_outputs"] is False
    assert "text_namu_v2_0014" not in " ".join(plan["query_variants"])


def test_weaviate_query_variants_build_synthetic_multilingual_year_anchor_from_query_text_only() -> None:
    plan = plan_weaviate_query_variants("프로젝트 이십육 출시 일정은 어떻게 적혀 있어")

    joined = " ".join(plan["query_variants"])
    assert "Project" not in joined
    assert "프로젝트 '26 출시 일정" in plan["query_variants"]
    assert "query_text_only_content_anchor_compaction" in plan["normalization_policies"]
    assert "korean_sino_number_normalization" in plan["normalization_policies"]
    assert "punctuation_normalization" in plan["normalization_policies"]
    assert plan["uses_expected_fields"] is False
    assert plan["uses_gold_fields"] is False
    assert plan["uses_ids"] is False
    assert plan["uses_qrels"] is False
    assert plan["uses_labels"] is False
    assert plan["uses_baseline_topk"] is False
    assert plan["uses_legacy_outputs"] is False
    assert "synthetic_project" not in " ".join(plan["query_variants"])


def test_weaviate_query_variants_do_not_add_x_men_hyphen_when_hyphen_is_absent() -> None:
    plan = plan_weaviate_query_variants("X Men 구십칠 등장인물")

    joined = " ".join(plan["query_variants"])
    assert "X-Men" not in joined
    assert "X Men '97 등장인물" in plan["query_variants"]


def test_weaviate_query_variants_do_not_compact_plain_korean_queries_without_numeric_anchor() -> None:
    query = "유우야키의 나이와 생일은 어떻게 적혀 있어"

    plan = plan_weaviate_query_variants(query)

    assert plan["query_variants"] == [query]
    assert plan["enabled"] is False
    assert "query_text_only_content_anchor_compaction" not in plan["normalization_policies"]


def test_weaviate_query_variants_replace_numeric_tokens_without_rewriting_substrings() -> None:
    for query in ("연구 구 결과", "구 연구 결과"):
        plan = plan_weaviate_query_variants(query)

        joined = " ".join(plan["query_variants"])
        assert "연9" not in joined
        assert "9 연9" not in joined
        assert any("9" in variant for variant in plan["query_variants"])
        assert any("연구" in variant for variant in plan["query_variants"])


def test_weaviate_route_selected_synthetic_multilingual_punctuation_query_uses_normal_query_variants(
    tmp_path: Path,
) -> None:
    class SyntheticAliasSensitiveWeaviateClient(FakeWeaviateSourceAtomClient):
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
            query_text = str(kwargs["query_text"])
            filters = dict(kwargs["filters"])
            if query_text != "프로젝트 '26 출시 일정":
                return []
            rows: list[dict] = []
            for obj in self.objects:
                if any(_filter_value_mismatch(obj, key, value) for key, value in filters.items()):
                    continue
                row = dict(obj)
                row["_score"] = 1.0
                row["_backend"] = kwargs["mode"]
                rows.append(row)
            return rows[: int(kwargs["limit"])]

    def _filter_value_mismatch(obj: dict, key: str, value: object) -> bool:
        if not value:
            return False
        if isinstance(value, list):
            return obj.get(key) not in value
        return obj.get(key) != value

    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "weaviate_route_selected_synthetic_alias_variants"
    write_jsonl(
        dataset,
        [
            {
                "id": "synthetic_project",
                "query": "프로젝트 이십육 출시 일정은 어떻게 적혀 있어",
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
    client = SyntheticAliasSensitiveWeaviateClient(
        objects=[
            {
                **weaviate_source_atom_record(2601, text="프로젝트 '26 출시 일정은 노트에 적혀 있다."),
                "source_atom_id": "srcatom-project-26",
                "evidence_bundle_id": "bundle-project-26",
                "doc_id": "doc-project-26",
                "chunk_id": "chunk-project-26",
                "title": "프로젝트 '26",
                "granularity": "paragraph",
                "retrieval_route": "text_general",
            }
        ]
    )
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
        run_id="weaviate_route_selected_synthetic_alias_variants",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert report["items"][0]["retrieved_contexts"][0]["source_atom_id"] == "srcatom-project-26"
    assert "프로젝트 '26 출시 일정" in [query["query_text"] for query in client.query_log]
    reformulation = report["items"][0]["weaviate_query_reformulation"]
    assert "synthetic_project" not in " ".join(reformulation["query_variants"])
    assert "query_text_only_content_anchor_compaction" in reformulation["normalization_policies"]
    for query_payload in client.query_log:
        assert "expected_answer" not in query_payload
        assert "expected_evidence" not in query_payload
        assert "row_id" not in query_payload
        assert "target_id" not in query_payload


def test_corpus_coverage_audit_classifies_route_filter_failure_report_only(tmp_path: Path) -> None:
    class CoverageAuditWeaviateClient(FakeWeaviateSourceAtomClient):
        def query(self, **kwargs: object) -> list[dict]:
            self.query_log.append(
                {
                    "mode": kwargs["mode"],
                    "query_text": kwargs["query_text"],
                    "filters": dict(kwargs["filters"]),
                    "limit": int(kwargs["limit"]),
                }
            )
            query_text = str(kwargs["query_text"])
            filters = dict(kwargs["filters"])
            rows: list[dict] = []
            for obj in self.objects:
                if _filter_mismatch(obj, filters):
                    continue
                target_query = "Adversary" in query_text and "Alison Sealy-Smith" in query_text
                if target_query and obj.get("source_atom_id") == "srcatom-xmen-97-adversary":
                    row = dict(obj)
                    row["_score"] = 1.0
                    row["_backend"] = kwargs["mode"]
                    rows.append(row)
                elif "X-Men" in query_text and obj.get("source_atom_id") == "srcatom-xmen-97-overview":
                    row = dict(obj)
                    row["_score"] = 0.5
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
    output_dir = tmp_path / "reports" / "rag_eval" / "corpus_coverage_audit"
    source_registry_path = tmp_path / "source_atom_registry_v1.jsonl"
    index_checkpoint_path = tmp_path / "index_checkpoint.json"
    write_jsonl(
        dataset,
        [
            {
                "id": "text_namu_v2_0014",
                "query": "엑스맨 구십칠 등장인물 목록에 애드버서리는 어떤 식으로 올라와",
                "expected_answer": "애드버서리 - 앨리슨 실리스미스 [카메오]",
                "expected_evidence": [{"text": "애드버서리 - 앨리슨 실리스미스 [카메오]"}],
            }
        ],
    )
    write_jsonl(
        source_registry_path,
        [
            {
                "source_atom_id": "srcatom-xmen-97-adversary",
                "document_id": "doc-xmen-97",
                "content_hash": "hash-xmen-97-adversary",
                "source_family": "TEXT",
                "normalized_text_or_value_snapshot": (
                    "X-Men '97 등장인물 목록에는 Adversary - Alison Sealy-Smith [카메오] 항목이 있다."
                ),
                "parent_pointers": {
                    "source_unit_id": "text_namu_v2_0014",
                    "search_unit_id": "su-text-namu-v2-0014",
                },
                "raw_locator": {
                    "chunk_id": "chunk-xmen-97-adversary",
                    "search_unit_id": "su-text-namu-v2-0014",
                    "title": "X-Men '97 등장인물",
                },
            }
        ],
    )
    index_checkpoint_path.write_text(
        json.dumps({"completed_source_atom_ids": ["srcatom-xmen-97-adversary"]}, ensure_ascii=False),
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
    objects = [
        {
            **weaviate_source_atom_record(
                971,
                text="TV 애니메이션 시리즈 〈 엑스맨 '97 〉의 첫 번째 시즌이다.",
            ),
            "source_atom_id": "srcatom-xmen-97-overview",
            "doc_id": "doc-xmen-97",
            "chunk_id": "chunk-xmen-97-overview",
            "title": "X-Men '97",
            "granularity": "paragraph",
            "retrieval_route": "text_general",
        },
        {
            **weaviate_source_atom_record(
                972,
                text="X-Men '97 등장인물 목록에는 Adversary - Alison Sealy-Smith [카메오] 항목이 있다.",
            ),
            "source_atom_id": "srcatom-xmen-97-adversary",
            "evidence_bundle_id": "bundle-xmen-97-adversary",
            "doc_id": "doc-xmen-97",
            "chunk_id": "chunk-xmen-97-adversary",
            "title": "X-Men '97 등장인물",
            "granularity": "metadata_only",
            "retrieval_route": "text_general",
        },
    ]
    active_client = CoverageAuditWeaviateClient(objects=objects)

    def lane_factory(route_mode: str) -> WeaviateSourceAtomAdapter:
        return WeaviateSourceAtomAdapter(
            config=config,
            client=CoverageAuditWeaviateClient(objects=objects),
            embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
            requested_backend="weaviate-hybrid",
            retrieval_route_mode=route_mode,
            route_filter_fields_available={"source_family": True, "granularity": True, "retrieval_route": True},
        )

    active_adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=active_client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="route_selected",
        route_filter_fields_available={"source_family": True, "granularity": True, "retrieval_route": True},
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=5,
        run_id="corpus_coverage_audit",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=active_adapter,
        corpus_coverage_audit_query_ids=["text_namu_v2_0014"],
        corpus_coverage_audit_target_anchors=["Adversary", "Alison Sealy-Smith", "애드버서리", "앨리슨 실리스미스"],
        corpus_coverage_audit_lane_factory=lane_factory,
        corpus_coverage_audit_source_registry_path=source_registry_path,
        corpus_coverage_audit_index_checkpoint_path=index_checkpoint_path,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    audit = report["corpus_coverage_audit"]
    row = audit["rows"][0]
    assert audit["enabled"] is True
    assert audit["report_only_diagnostic"] is True
    assert audit["gold_or_qrels_mutation"] is False
    assert audit["official_metric_input_rows"] == 0
    assert audit["classification_counts"] == {"route_filter_failure": 1}
    assert row["query_id"] == "text_namu_v2_0014"
    assert row["primary_classification"] == "route_filter_failure"
    assert row["corpus_presence"] == "corpus_present"
    assert row["source_registry_presence"]["target_anchor_hit"] is True
    assert row["source_registry_presence"]["matching_source_atom_count"] == 1
    assert row["source_registry_presence"]["source_atom_ids"] == ["srcatom-xmen-97-adversary"]
    assert row["active_index_presence"]["target_source_atom_indexed"] is True
    assert row["active_index_presence"]["source_atom_id_match_count"] == 1
    assert row["full_index_probe"]["target_anchor_hit"] is True
    assert row["route_selected_probe"]["target_anchor_hit"] is False
    assert row["route_selected_filter_failure"] is True
    assert row["target_anchors"] == ["Adversary", "Alison Sealy-Smith", "애드버서리", "앨리슨 실리스미스"]
    assert row["audit_uses_expected_fields_for_candidate_generation"] is False
    assert row["audit_uses_gold_fields_for_candidate_generation"] is False
    assert report["artifact_paths"]["corpus_coverage_audit_jsonl"] == ""
    assert output_file_names(output_dir) == ["report.json"]
    for query_payload in active_client.query_log:
        assert "expected_answer" not in query_payload
        assert "expected_evidence" not in query_payload
        assert "row_id" not in query_payload


def test_corpus_coverage_audit_query_id_without_explicit_anchors_fails_closed(tmp_path: Path) -> None:
    class NoProbeClient(FakeWeaviateSourceAtomClient):
        def query(self, **kwargs: object) -> list[dict]:
            self.query_log.append(dict(kwargs))
            return []

    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "corpus_coverage_audit_no_anchors"
    write_jsonl(
        dataset,
        [
            {
                "id": "text_namu_v2_0014",
                "query": "엑스맨 구십칠 등장인물 목록에 애드버서리는 어떤 식으로 올라와",
                "expected_answer": "SECRET_EXPECTED_ANSWER_NEVER_AUDIT",
                "expected_evidence": [{"text": "SECRET_EXPECTED_EVIDENCE_NEVER_AUDIT"}],
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
    active_client = NoProbeClient()
    active_adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=active_client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="route_selected",
        route_filter_fields_available={"source_family": True, "granularity": True, "retrieval_route": True},
    )

    def unexpected_lane_factory(route_mode: str) -> WeaviateSourceAtomAdapter:
        raise AssertionError(f"corpus audit probe should fail closed without explicit anchors: {route_mode}")

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=5,
        run_id="corpus_coverage_audit_no_anchors",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=active_adapter,
        corpus_coverage_audit_query_ids=["text_namu_v2_0014"],
        corpus_coverage_audit_lane_factory=unexpected_lane_factory,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    audit = report["corpus_coverage_audit"]
    assert audit["enabled"] is True
    assert audit["classification_counts"] == {"skipped_missing_explicit_target_anchors": 1}
    assert audit["official_metric_input_rows"] == 0
    assert audit["gold_or_qrels_mutation"] is False
    assert audit["uses_expected_fields_for_candidate_generation"] is False
    row = audit["rows"][0]
    assert row["query_id"] == "text_namu_v2_0014"
    assert row["primary_classification"] == "skipped_missing_explicit_target_anchors"
    assert row["target_anchors"] == []
    assert row["audit_skipped_reason"] == "explicit_target_anchors_required"
    assert active_client.query_log
    for query_payload in active_client.query_log:
        query_text = str(query_payload.get("query_text", ""))
        assert "SECRET_EXPECTED_ANSWER_NEVER_AUDIT" not in query_text
        assert "SECRET_EXPECTED_EVIDENCE_NEVER_AUDIT" not in query_text
        assert "Adversary" not in query_text
        assert "Alison Sealy-Smith" not in query_text
    encoded_report = json.dumps(audit, ensure_ascii=False)
    assert "SECRET_EXPECTED_ANSWER_NEVER_AUDIT" not in encoded_report
    assert "SECRET_EXPECTED_EVIDENCE_NEVER_AUDIT" not in encoded_report
    assert "Adversary" not in encoded_report
    assert "Alison Sealy-Smith" not in encoded_report


def test_run_eval_embeds_heuristic_risk_ledger_and_metric_continuity_checkpoint(tmp_path: Path) -> None:
    dataset = tmp_path / "selected_evidence_gate_gold.jsonl"
    context = tmp_path / "selected_evidence_gate_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "heuristic_checkpoint"
    gold_rows: list[dict[str, object]] = []
    context_rows: list[dict[str, object]] = []
    for index in range(5):
        query_id = f"safe_q_{index}"
        text = f"Apollo{index} Seoul home is confirmed by selected evidence."
        gold_rows.append({"id": query_id, "query": f"Apollo{index} Seoul home", "answerability": "unknown"})
        context_rows.append(
            {
                "id": query_id,
                "generated_answer": "",
                "retrieved_contexts": [
                    {
                        "doc_id": f"doc-{index}",
                        "chunk_id": f"chunk-{index}",
                        "source_atom_id": f"src-{index}",
                        "evidence_bundle_id": f"bundle-{index}",
                        "source_family": "TEXT",
                        "granularity": "paragraph",
                        "text": text,
                    }
                ],
                "citations": [],
            }
        )
    gold_rows.append(
        {
            "id": "text_namu_v2_0014",
            "query": "엑스맨 구십칠 등장인물 목록에 애드버서리는 어떤 식으로 올라와",
            "answerability": "unknown",
        }
    )
    context_rows.append(
        {
            "id": "text_namu_v2_0014",
            "generated_answer": "",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-xmen-97-overview",
                    "chunk_id": "chunk-xmen-97-overview",
                    "source_atom_id": "src-xmen-97-overview",
                    "evidence_bundle_id": "bundle-xmen-97-overview",
                    "source_family": "TEXT",
                    "granularity": "paragraph",
                    "text": "TV 애니메이션 시리즈 엑스맨 97의 첫 번째 시즌 개요다.",
                }
            ],
            "citations": [],
        }
    )
    write_jsonl(dataset, gold_rows)
    write_jsonl(context, context_rows)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        context_jsonl_path=context,
        output_dir=output_dir,
        top_k=1,
        run_id="heuristic_checkpoint",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    checkpoint = report["metric_continuity_checkpoint"]
    assert checkpoint["schema_version"] == "actual_rag_eval.metric_continuity_checkpoint.v1"
    assert checkpoint["official_metric"] is False
    assert checkpoint["gate_outcome"] == {
        "item_count": 6,
        "allowed_answer_count": 5,
        "blocked_or_would_block_count": 1,
        "allowed_over_item_count": "5/6",
    }
    assert checkpoint["selected_evidence_gate_outcome_preserved"] is True
    assert checkpoint["evidence_package_status_counts"]["sufficient"] == 5
    assert checkpoint["evidence_package_status_counts"]["insufficient"] == 1
    assert checkpoint["unsupported_answer_rate_after_gate"] == 0.0
    assert checkpoint["citation_supported_count"] == 6
    assert checkpoint["retrieved_context_only_diagnostic_count"] == 0
    assert checkpoint["selected_evidence_citation_precision"] == 1.0
    assert checkpoint["query_count_per_item"] == 1.0
    assert checkpoint["residual_taxonomy"]["allowed"] == 5
    assert checkpoint["residual_taxonomy"]["insufficient_evidence"] == 1
    assert checkpoint["guardrail_mutation_flags"] == {
        "gold_or_qrels_mutation": False,
        "expected_fields_used_for_candidate_generation": False,
        "query_id_used_for_candidate_generation": False,
        "row_id_used_for_candidate_generation": False,
        "target_id_used_for_candidate_generation": False,
        "qrels_used_for_candidate_generation": False,
        "answerability_labels_used_for_candidate_generation": False,
        "gate_uses_expected_fields": False,
        "gate_uses_gold_fields": False,
        "evidence_gate_retrieval_loop_triggered": False,
    }

    ledger = report["heuristic_risk_ledger"]
    assert ledger["schema_version"] == "actual_rag_eval.heuristic_risk_ledger.v1"
    assert ledger["official_metric"] is False
    assert ledger["forbidden_eval_row_shortcut_active"] is False
    assert set(ledger["allowed_classifications"]) == {
        "global_normalization",
        "source_derived_index_feature",
        "query_text_only_reformulation",
        "diagnostic_probe_only",
    }
    entries_by_id = {entry["rule_id"]: entry for entry in ledger["entries"]}
    assert entries_by_id["selected_evidence_composer"]["classification"] == "query_text_only_reformulation"
    assert entries_by_id["evidence_gate_enforcement"]["classification"] == "diagnostic_probe_only"
    assert entries_by_id["forbidden_query_id_row_id_target_id_aliasing"]["classification"] == "forbidden_eval_row_shortcut"
    assert entries_by_id["forbidden_query_id_row_id_target_id_aliasing"]["status"] == "rejected"
    active_entries = [entry for entry in ledger["entries"] if entry["status"] == "active"]
    assert active_entries
    for entry in active_entries:
        assert entry["uses_query_id_or_row_id_or_target_id"] is False
        assert entry["uses_expected_answer_or_evidence"] is False
        assert entry["uses_qrels_or_labels"] is False
        assert entry["per_row_alias_table"] is False
        assert entry["composer_or_gate_loosening_for_single_residual"] is False


def test_agentic_planner_dry_run_emits_diagnostics_without_executing_loops(tmp_path: Path) -> None:
    dataset = tmp_path / "agentic_planner_gold.jsonl"
    context = tmp_path / "agentic_planner_context.jsonl"
    gold_rows: list[dict[str, object]] = []
    context_rows: list[dict[str, object]] = []
    for index in range(5):
        query_id = f"safe_q_{index}"
        text = f"Apollo{index} Seoul home is confirmed by selected evidence."
        gold_rows.append({"id": query_id, "query": f"Apollo{index} Seoul home", "answerability": "unknown"})
        context_rows.append(
            {
                "id": query_id,
                "generated_answer": "",
                "retrieved_contexts": [
                    {
                        "doc_id": f"doc-{index}",
                        "chunk_id": f"chunk-{index}",
                        "source_atom_id": f"src-{index}",
                        "evidence_bundle_id": f"bundle-{index}",
                        "source_family": "TEXT",
                        "granularity": "paragraph",
                        "text": text,
                    }
                ],
                "citations": [],
            }
        )
    gold_rows.append(
        {
            "id": "text_namu_v2_0014",
            "query": "엑스맨 구십칠 등장인물 목록에 애드버서리는 어떤 식으로 올라와",
            "answerability": "unknown",
        }
    )
    context_rows.append(
        {
            "id": "text_namu_v2_0014",
            "generated_answer": "",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-xmen-97-overview",
                    "chunk_id": "chunk-xmen-97-overview",
                    "source_atom_id": "src-xmen-97-overview",
                    "evidence_bundle_id": "bundle-xmen-97-overview",
                    "source_family": "TEXT",
                    "granularity": "paragraph",
                    "text": "TV 애니메이션 시리즈 엑스맨 97의 첫 번째 시즌 개요다.",
                }
            ],
            "citations": [],
        }
    )
    write_jsonl(dataset, gold_rows)
    write_jsonl(context, context_rows)

    baseline_bundle = run_eval_from_paths(
        dataset_path=dataset,
        context_jsonl_path=context,
        output_dir=tmp_path / "reports" / "rag_eval" / "agentic_planner_off",
        top_k=1,
        run_id="agentic_planner_off",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
    )
    dry_run_bundle = run_eval_from_paths(
        dataset_path=dataset,
        context_jsonl_path=context,
        output_dir=tmp_path / "reports" / "rag_eval" / "agentic_planner_dry_run",
        top_k=1,
        run_id="agentic_planner_dry_run",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        agentic_planner_mode="dry-run",
    )

    baseline_report = json.loads(baseline_bundle.report_path.read_text(encoding="utf-8"))
    report = json.loads(dry_run_bundle.report_path.read_text(encoding="utf-8"))
    planner = report["agentic_planner_dry_run"]
    assert planner["schema_version"] == "actual_rag_eval.agentic_planner_dry_run.v1"
    assert planner["planner_enabled"] is True
    assert planner["planner_mode"] == "dry-run"
    assert planner["planner_version"] == "actual_rag_eval.agentic_planner_dry_run.v1"
    assert planner["ran_after_selected_evidence_composer"] is True
    assert planner["ran_after_evidence_gate"] is True
    assert planner["planner_decision_count"] == 1
    assert planner["planner_action_counts"] == {"query_text_only_reformulation": 1}
    assert planner["planner_failure_class_counts"] == {"missing_query_anchor": 1}
    assert planner["planner_no_safe_action_count"] == 0
    assert planner["planner_forbidden_shortcut_detected_count"] == 0
    assert planner["planner_expected_extra_query_count"] == 1
    assert planner["planner_expected_tool_call_count"] == 0
    assert planner["planner_heuristic_risk_class"] == "diagnostic_probe_only"
    assert planner["official_metric"] is False
    assert planner["raw_prompt_payload_written"] is False
    assert planner["raw_response_payload_written"] is False
    assert planner["retrieved_context_only_citation_policy"] == "diagnostic_only_never_promoted"
    assert planner["planner_execution"] == {
        "retrieval_executed": False,
        "tool_call_executed": False,
        "llm_retry_executed": False,
        "extra_query_count_executed": 0,
        "tool_call_count_executed": 0,
        "llm_retry_count_executed": 0,
    }
    assert planner["guardrail_flags"] == {
        "gold_or_qrels_mutation": False,
        "expected_fields_used_for_planner_selection": False,
        "query_id_used_for_planner_selection": False,
        "row_id_used_for_planner_selection": False,
        "target_id_used_for_planner_selection": False,
        "qrels_used_for_planner_selection": False,
        "labels_used_for_planner_selection": False,
        "baseline_topk_or_legacy_outputs_used": False,
        "row_specific_alias_or_shortcut_used": False,
        "retrieval_executed": False,
        "tool_call_executed": False,
        "llm_retry_executed": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "evidence_gate_loosened": False,
        "retrieved_context_only_citation_promoted": False,
        "official_metric": False,
        "production_routing_opened": False,
        "protected_namespace_mutation": False,
    }
    assert planner["gate_before"]["allowed_answer_count"] == 5
    assert planner["gate_before"]["unsupported_answer_blocked_count"] == 1
    assert planner["gate_after_unchanged_because_dry_run"] == planner["gate_before"]
    assert "agentic_planner_dry_run" not in baseline_report
    assert planner["gate_after_unchanged_because_dry_run"]["allowed_answer_count"] == baseline_report["evidence_gate"]["allowed_answer_count"]
    assert (
        planner["gate_after_unchanged_because_dry_run"]["unsupported_answer_blocked_count"]
        == baseline_report["evidence_gate"]["unsupported_answer_blocked_count"]
    )
    assert report["evidence_gate"]["allowed_answer_count"] == baseline_report["evidence_gate"]["allowed_answer_count"]
    assert report["evidence_gate"]["unsupported_answer_blocked_count"] == baseline_report["evidence_gate"]["unsupported_answer_blocked_count"]
    for baseline_row, dry_run_row in zip(baseline_report["items"], report["items"], strict=True):
        assert dry_run_row["generated_answer"] == baseline_row["generated_answer"]
        assert dry_run_row["citations"] == baseline_row["citations"]
        assert dry_run_row["retrieved_contexts"] == baseline_row["retrieved_contexts"]
        assert dry_run_row["evidence_gate"] == baseline_row["evidence_gate"]
    assert report["metric_continuity_checkpoint"]["selected_evidence_gate_outcome_preserved"] is True
    assert report["metric_continuity_checkpoint"]["retrieved_context_only_diagnostic_count"] == 0
    entries_by_id = {entry["rule_id"]: entry for entry in report["heuristic_risk_ledger"]["entries"]}
    assert entries_by_id["agentic_planner_dry_run"]["classification"] == "diagnostic_probe_only"
    assert entries_by_id["agentic_planner_dry_run"]["uses_query_id_or_row_id_or_target_id"] is False

    decision = planner["decisions"][0]
    assert decision["failure_class"] == "missing_query_anchor"
    assert decision["proposed_action"] == "query_text_only_reformulation"
    assert decision["executed"] is False
    assert decision["expected_extra_query_count"] == 1
    assert decision["expected_tool_call_count"] == 0
    forbidden_decision_keys = {
        "case_id",
        "query_id",
        "row_id",
        "target_id",
        "answerability",
        "answerability_label",
        "expected_answer",
        "expected_evidence",
        "supporting_evidence",
        "qrels",
        "label",
        "labels",
        "baseline_topk",
        "legacy_outputs",
        "source_title",
        "workbook",
        "gold_locator",
        "target_locator",
        "normalized_value",
        "formula",
        "raw_prompt_payload",
        "raw_response_payload",
    }
    assert forbidden_decision_keys.isdisjoint(decision)
    serialized_report = dry_run_bundle.report_path.read_text(encoding="utf-8")
    for forbidden_snippet in (
        '"prompt":',
        '"raw_prompt"',
        '"raw_response"',
        '"prompt_payload"',
        '"response_payload"',
        "Return exactly one JSON",
        "Payload:",
    ):
        assert forbidden_snippet not in serialized_report
    assert output_file_names(tmp_path / "reports" / "rag_eval" / "agentic_planner_dry_run") == ["report.json"]


def test_agentic_planner_dry_run_does_not_execute_extra_weaviate_retrieval(tmp_path: Path) -> None:
    dataset = tmp_path / "agentic_planner_weaviate_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {"id": "safe_q", "query": "Project Orion April 2026", "answerability": "unknown"},
            {
                "id": "text_namu_v2_0014",
                "query": "엑스맨 구십칠 등장인물 목록에 애드버서리는 어떤 식으로 올라와",
                "answerability": "unknown",
            },
        ],
    )
    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodRouteSelectedV2",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    objects = [
        {
            **weaviate_source_atom_record(1, text="Project Orion launch is scheduled for April 2026."),
            "granularity": "paragraph",
            "retrieval_route": "text_general",
        },
        {
            **weaviate_source_atom_record(
                2,
                text="TV 애니메이션 시리즈 엑스맨 97의 첫 번째 시즌 개요다.",
            ),
            "source_atom_id": "srcatom-xmen-97-overview",
            "evidence_bundle_id": "bundle-xmen-97-overview",
            "doc_id": "doc-xmen-97-overview",
            "chunk_id": "chunk-xmen-97-overview",
            "title": "엑스맨 97",
            "section": "개요",
            "granularity": "paragraph",
            "retrieval_route": "text_general",
        },
    ]

    def make_adapter(client: FakeWeaviateSourceAtomClient) -> WeaviateSourceAtomAdapter:
        return WeaviateSourceAtomAdapter(
            config=config,
            client=client,
            embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
            requested_backend="weaviate-hybrid",
            retrieval_route_mode="route_selected",
            route_filter_fields_available={"source_family": True, "granularity": True, "retrieval_route": True},
        )

    baseline_client = FakeWeaviateSourceAtomClient(objects=objects)
    baseline_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "agentic_planner_weaviate_off",
        top_k=1,
        run_id="agentic_planner_weaviate_off",
        output_mode="single",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=make_adapter(baseline_client),
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
    )
    dry_run_client = FakeWeaviateSourceAtomClient(objects=objects)
    dry_run_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "agentic_planner_weaviate_dry_run",
        top_k=1,
        run_id="agentic_planner_weaviate_dry_run",
        output_mode="single",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=make_adapter(dry_run_client),
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        agentic_planner_mode="dry-run",
    )

    baseline_report = json.loads(baseline_bundle.report_path.read_text(encoding="utf-8"))
    report = json.loads(dry_run_bundle.report_path.read_text(encoding="utf-8"))
    planner = report["agentic_planner_dry_run"]
    assert "agentic_planner_dry_run" not in baseline_report
    assert dry_run_client.query_log == baseline_client.query_log
    assert dry_run_client.upsert_log == []
    assert dry_run_client.metadata_only_upsert_log == []
    assert dry_run_client.local_scan_used is False
    assert len(dry_run_client.query_log) >= 2
    assert report["weaviate_filter_policy"]["route_mode"] == "route_selected"
    for query_payload in dry_run_client.query_log:
        assert query_payload["filters"]["namespace"] == "actual_rag_eval_nonprod"
        assert query_payload["filters"]["visibility"] == "nonprod"
        assert "source_family" in query_payload["filters"]
        for forbidden in (
            "query_id",
            "row_id",
            "target_id",
            "expected_answer",
            "expected_evidence",
            "qrels",
            "label",
            "labels",
            "baseline_topk",
            "legacy_outputs",
        ):
            assert forbidden not in query_payload
    assert planner["planner_execution"] == {
        "retrieval_executed": False,
        "tool_call_executed": False,
        "llm_retry_executed": False,
        "extra_query_count_executed": 0,
        "tool_call_count_executed": 0,
        "llm_retry_count_executed": 0,
    }
    assert planner["guardrail_flags"]["retrieval_executed"] is False
    assert planner["guardrail_flags"]["tool_call_executed"] is False
    assert planner["guardrail_flags"]["llm_retry_executed"] is False
    assert planner["gate_after_unchanged_because_dry_run"] == planner["gate_before"]
    assert report["evidence_gate"]["allowed_answer_count"] == baseline_report["evidence_gate"]["allowed_answer_count"]
    assert (
        report["evidence_gate"]["unsupported_answer_blocked_count"]
        == baseline_report["evidence_gate"]["unsupported_answer_blocked_count"]
    )
    assert report["official_metric"] is False
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False
    assert planner["retrieved_context_only_citation_policy"] == "diagnostic_only_never_promoted"


def test_agentic_planner_dry_run_ignores_scorer_failure_labels_for_selection() -> None:
    summary = {
        "run_id": "agentic_planner_label_guard",
        "generator_config": {"selected_evidence_composer_invoked": True},
        "evidence_gate": {"evidence_gate_mode": "enforce"},
        "items": [
            {
                "id": "unsafe_label_row",
                "query": "ordinary failed query",
                "answer_gate_decision": "block_answer",
                "failure_labels": ["collision", "answer_judge_fail", "evidence_not_retrieved"],
                "evidence_gate": {
                    "evidence_package_status": "sufficient",
                    "unsupported_answer_blocked": False,
                    "validation_reasons": [],
                    "abstention_reasons": [],
                    "unsupported_answer_reasons": [],
                },
                "retrieved_contexts": [],
                "citations": [],
            }
        ],
    }

    planner = actual_rag_eval.build_agentic_planner_dry_run_report(summary, mode="dry-run")

    assert planner["planner_failure_class_counts"] == {"no_safe_action": 1}
    assert planner["planner_action_counts"] == {"deterministic_abstain": 1}
    decision = planner["decisions"][0]
    assert decision["failure_class"] == "no_safe_action"
    assert decision["proposed_action"] == "deterministic_abstain"


def test_agentic_planner_execute_once_runs_one_bounded_query_text_probe_and_regates(tmp_path: Path) -> None:
    class RouteProbeAdapter:
        requested_backend = "hybrid"

        def __init__(self) -> None:
            self.query_log: list[dict[str, object]] = []

        @property
        def config(self) -> dict[str, object]:
            return {
                "adapter": "route_probe_adapter",
                "candidate_generation_input_policy": "query_text_only_no_reference_fields",
            }

        @property
        def retrieval_backend_report(self) -> dict[str, object]:
            return {
                "requested": self.requested_backend,
                "selected": "hybrid",
                "bm25_enabled": True,
                "vector_enabled": False,
                "hybrid_enabled": True,
                "embedding_model": "none",
                "embedding_device": "none",
                "gpu_used_for_embedding": False,
                "vector_index_kind": "none",
                "vector_index_type": "none",
                "vector_dim": 0,
                "indexed_unit_count": 2,
                "query_count": len(self.query_log),
                "fallback_reason": "",
            }

        def run_item(self, item: object, *, top_k: int) -> dict[str, object]:
            query = str(getattr(item, "query", ""))
            self.query_log.append(
                {
                    "query_text": query,
                    "top_k": top_k,
                    "item_id": str(getattr(item, "id", "")),
                    "expected_answer": str(getattr(item, "expected_answer", "")),
                }
            )
            wrong = {
                "rank": 1,
                "doc_id": "doc-orion",
                "chunk_id": "chunk-wrong",
                "source_atom_id": "src-orion-wrong",
                "evidence_bundle_id": "bundle-orion-wrong",
                "source_family": "TEXT",
                "granularity": "paragraph",
                "text": "Project Orion launch was delayed.",
            }
            right = {
                "rank": 2,
                "doc_id": "doc-orion",
                "chunk_id": "chunk-right",
                "source_atom_id": "src-orion-right",
                "evidence_bundle_id": "bundle-orion-right",
                "source_family": "TEXT",
                "granularity": "paragraph",
                "text": "Project Orion 2026 launch is scheduled.",
            }
            contexts = [wrong] if top_k <= 1 else [wrong, right]
            return {
                "id": str(getattr(item, "id", "")),
                "query": query,
                "answerability": str(getattr(item, "answerability", "unknown")) or "unknown",
                "generated_answer": contexts[0]["text"],
                "retrieved_contexts": [dict(context) for context in contexts],
                "citations": [dict(context) for context in contexts],
                "diagnostics": {
                    "retrieval_empty": False,
                    "generation_empty": False,
                    "citation_empty": False,
                    "gold_incomplete": True,
                },
            }

    dataset = tmp_path / "agentic_execute_once_gold.jsonl"
    write_jsonl(dataset, [{"id": "orion_q", "query": "Project Orion 2026", "answerability": "unknown"}])
    baseline_adapter = RouteProbeAdapter()
    baseline_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "agentic_execute_once_off",
        top_k=1,
        run_id="agentic_execute_once_off",
        output_mode="single",
        retrieval_adapter=baseline_adapter,
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
    )
    execute_adapter = RouteProbeAdapter()
    execute_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "agentic_execute_once",
        top_k=1,
        run_id="agentic_execute_once",
        output_mode="single",
        retrieval_adapter=execute_adapter,
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        agentic_planner_mode="execute-once",
    )

    baseline_report = json.loads(baseline_bundle.report_path.read_text(encoding="utf-8"))
    report = json.loads(execute_bundle.report_path.read_text(encoding="utf-8"))
    planner = report["agentic_planner_execute_once"]
    assert "agentic_planner_execute_once" not in baseline_report
    assert baseline_adapter.query_log == [
        {
            "query_text": "Project Orion 2026",
            "top_k": 1,
            "item_id": "orion_q",
            "expected_answer": "",
        }
    ]
    assert execute_adapter.query_log == [
        {
            "query_text": "Project Orion 2026",
            "top_k": 1,
            "item_id": "orion_q",
            "expected_answer": "",
        },
        {
            "query_text": "Project Orion 2026",
            "top_k": 2,
            "item_id": "",
            "expected_answer": "",
        },
    ]
    assert baseline_report["evidence_gate"]["allowed_answer_count"] == 0
    assert baseline_report["evidence_gate"]["unsupported_answer_blocked_count"] == 1
    assert report["evidence_gate"]["allowed_answer_count"] == 1
    assert report["evidence_gate"]["unsupported_answer_blocked_count"] == 0
    assert planner["planner_enabled"] is True
    assert planner["planner_mode"] == "execute-once"
    assert planner["planner_decision_count"] == 1
    assert planner["planner_executed_decision_count"] == 1
    assert planner["planner_action_counts"] == {"query_text_only_reformulation": 1}
    assert planner["planner_failure_class_counts"] == {"missing_query_anchor": 1}
    assert planner["planner_execution"] == {
        "retrieval_executed": True,
        "tool_call_executed": False,
        "llm_retry_executed": False,
        "extra_query_count_executed": 1,
        "tool_call_count_executed": 0,
        "llm_retry_count_executed": 0,
    }
    assert planner["gate_before"]["allowed_answer_count"] == 0
    assert planner["gate_after"]["allowed_answer_count"] == 1
    assert planner["gate_delta"]["allowed_answer_count_delta"] == 1
    assert planner["official_metric"] is False
    assert planner["raw_prompt_payload_written"] is False
    assert planner["raw_response_payload_written"] is False
    assert planner["guardrail_mutation_flags"]["gate_loosened"] is False
    assert planner["guardrail_mutation_flags"]["retrieved_context_only_citation_promoted"] is False
    loop_review = report["agentic_loop_review"]
    assert loop_review["schema_version"] == "actual_rag_eval.agentic_loop_review.v1"
    assert loop_review["review_only"] is True
    assert loop_review["official_metric"] is False
    assert loop_review["broader_agent_loop_ready"] is False
    assert loop_review["broader_agent_loop_opened"] is False
    assert loop_review["production_routing_opened"] is False
    assert loop_review["raw_prompt_payload_written"] is False
    assert loop_review["raw_response_payload_written"] is False
    assert loop_review["retrieved_context_only_citation_promoted"] is False
    assert loop_review["gate_loosened"] is False
    assert loop_review["bounded_action_evidence"]["planner_mode"] == "execute-once"
    assert loop_review["bounded_action_evidence"]["quality_improvement_measured"] is True
    assert loop_review["bounded_action_evidence"]["gate_delta"]["allowed_answer_count_delta"] == 1
    assert loop_review["recommendation"] == (
        "keep_broader_agent_loop_closed_continue_bounded_execute_once_evidence_gate_checkpoints"
    )
    assert "fresh_live_text_gold_report_with_weaviate_reachable" in loop_review["required_before_broader_loop"]
    decision = planner["decisions"][0]
    assert decision["executed"] is True
    assert decision["proposed_action"] == "query_text_only_reformulation"
    assert decision["execution_status"] == "executed"
    assert "query_id" not in decision
    assert "expected_answer" not in decision
    assert output_file_names(tmp_path / "reports" / "rag_eval" / "agentic_execute_once") == ["report.json"]


def test_agentic_planner_execute_once_defers_pdf_locator_tool_without_execution_gate(tmp_path: Path) -> None:
    class PdfToolAdapter:
        requested_backend = "hybrid"

        def __init__(self) -> None:
            self.query_log: list[dict[str, object]] = []

        @property
        def config(self) -> dict[str, object]:
            return {
                "adapter": "pdf_tool_adapter",
                "candidate_generation_input_policy": "query_text_only_no_reference_fields",
            }

        @property
        def retrieval_backend_report(self) -> dict[str, object]:
            return {
                "requested": self.requested_backend,
                "selected": "hybrid",
                "bm25_enabled": True,
                "vector_enabled": False,
                "hybrid_enabled": True,
                "embedding_model": "none",
                "embedding_device": "none",
                "gpu_used_for_embedding": False,
                "vector_index_kind": "none",
                "vector_index_type": "none",
                "vector_dim": 0,
                "indexed_unit_count": 1,
                "query_count": len(self.query_log),
                "fallback_reason": "",
            }

        def run_item(self, item: object, *, top_k: int) -> dict[str, object]:
            query = str(getattr(item, "query", ""))
            self.query_log.append(
                {
                    "query_text": query,
                    "top_k": top_k,
                    "item_id": str(getattr(item, "id", "")),
                    "expected_answer": str(getattr(item, "expected_answer", "")),
                }
            )
            context = {
                "rank": 1,
                "doc_id": "doc-nebula-pdf",
                "chunk_id": "page-7-summary",
                "source_atom_id": "src-nebula-pdf-summary",
                "evidence_bundle_id": "bundle-nebula-pdf-summary",
                "source_family": "PDF",
                "granularity": "page_summary",
                "page_number": 7,
                "text": "Nebula launch details are on the scanned page.",
                "pdf_locator_text": "Nebula 2026 launch approval is final.",
            }
            return {
                "id": str(getattr(item, "id", "")),
                "query": query,
                "answerability": str(getattr(item, "answerability", "unknown")) or "unknown",
                "generated_answer": context["text"],
                "retrieved_contexts": [dict(context)],
                "citations": [dict(context)],
                "diagnostics": {
                    "retrieval_empty": False,
                    "generation_empty": False,
                    "citation_empty": False,
                    "gold_incomplete": True,
                },
            }

    dataset = tmp_path / "agentic_pdf_tool_gold.jsonl"
    write_jsonl(dataset, [{"id": "pdf_q", "query": "Nebula 2026", "answerability": "unknown"}])
    baseline_adapter = PdfToolAdapter()
    baseline_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "agentic_pdf_tool_off",
        top_k=1,
        run_id="agentic_pdf_tool_off",
        output_mode="single",
        retrieval_adapter=baseline_adapter,
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
    )
    execute_adapter = PdfToolAdapter()
    execute_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "agentic_pdf_tool_execute_once",
        top_k=1,
        run_id="agentic_pdf_tool_execute_once",
        output_mode="single",
        retrieval_adapter=execute_adapter,
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        agentic_planner_mode="execute-once",
    )

    baseline_report = json.loads(baseline_bundle.report_path.read_text(encoding="utf-8"))
    report = json.loads(execute_bundle.report_path.read_text(encoding="utf-8"))
    planner = report["agentic_planner_execute_once"]
    assert baseline_adapter.query_log == [
        {
            "query_text": "Nebula 2026",
            "top_k": 1,
            "item_id": "pdf_q",
            "expected_answer": "",
        }
    ]
    assert execute_adapter.query_log == baseline_adapter.query_log
    assert baseline_report["evidence_gate"]["allowed_answer_count"] == 0
    assert baseline_report["evidence_gate"]["unsupported_answer_blocked_count"] == 1
    assert report["evidence_gate"]["allowed_answer_count"] == 0
    assert report["evidence_gate"]["unsupported_answer_blocked_count"] == 1
    assert planner["planner_action_counts"] == {"pdf_locator_tool": 1}
    assert planner["planner_failure_class_counts"] == {"tool_required_pdf": 1}
    assert planner["planner_execution"] == {
        "retrieval_executed": False,
        "tool_call_executed": False,
        "llm_retry_executed": False,
        "extra_query_count_executed": 0,
        "tool_call_count_executed": 0,
        "llm_retry_count_executed": 0,
    }
    assert planner["gate_delta"]["allowed_answer_count_delta"] == 0
    assert planner["guardrail_mutation_flags"]["gate_loosened"] is False
    assert planner["guardrail_mutation_flags"]["retrieved_context_only_citation_promoted"] is False
    decision = planner["decisions"][0]
    assert decision["executed"] is False
    assert decision["proposed_action"] == "pdf_locator_tool"
    assert decision["execution_status"] == "deferred_requires_explicit_execution_gate"
    assert decision["expected_extra_query_count"] == 0
    assert decision["expected_tool_call_count"] == 1
    assert decision["tool_call_count_executed"] == 0
    assert decision["execution_gate_required"] is True
    assert "agentic_planner_tool_use" not in report["items"][0]
    assert "Nebula 2026" not in report["items"][0]["retrieved_contexts"][0]["text"]
    assert "query_id" not in decision
    assert "expected_answer" not in decision
    assert output_file_names(tmp_path / "reports" / "rag_eval" / "agentic_pdf_tool_execute_once") == ["report.json"]


def test_agentic_planner_execute_once_runs_pdf_locator_tool_with_validated_axes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class PdfToolAdapter:
        requested_backend = "hybrid"

        def __init__(self) -> None:
            self.query_log: list[dict[str, object]] = []

        @property
        def config(self) -> dict[str, object]:
            return {
                "adapter": "pdf_tool_adapter",
                "candidate_generation_input_policy": "query_text_and_query_evidence_planner_only",
            }

        @property
        def retrieval_backend_report(self) -> dict[str, object]:
            return {
                "requested": self.requested_backend,
                "selected": "hybrid",
                "bm25_enabled": True,
                "vector_enabled": False,
                "hybrid_enabled": True,
                "embedding_model": "none",
                "embedding_device": "none",
                "gpu_used_for_embedding": False,
                "vector_index_kind": "none",
                "vector_index_type": "none",
                "vector_dim": 0,
                "indexed_unit_count": 1,
                "query_count": len(self.query_log),
                "fallback_reason": "",
            }

        def run_item(self, item: object, *, top_k: int) -> dict[str, object]:
            query = str(getattr(item, "query", ""))
            source_row = getattr(item, "source_row", {})
            planner = source_row.get("query_evidence_planner") if isinstance(source_row, dict) else {}
            self.query_log.append(
                {
                    "query_text": query,
                    "top_k": top_k,
                    "planner_status": planner.get("planner_status") if isinstance(planner, dict) else "",
                    "expected_answer": str(getattr(item, "expected_answer", "")),
                }
            )
            context = {
                "rank": 1,
                "doc_id": "doc-pdf-locator-axis",
                "chunk_id": "chunk-pdf-locator-axis",
                "source_atom_id": "src-pdf-locator-axis",
                "evidence_bundle_id": "bundle-pdf-locator-axis",
                "source_family": "PDF",
                "granularity": "page_block",
                "text": "7페이지 연결 손익계산서 영업실적 표에는 영업이익 항목이 있습니다.",
                "pdf_locator_text": "7페이지 연결 손익계산서 영업실적 표 영업이익은 123억원입니다.",
                "page_number": "7",
                "section_title": "연결 손익계산서",
                "table_caption": "영업실적 표",
                "target_column": "영업이익",
                "bbox": "[72,260,510,318]",
                "locator_fingerprint": "pdf-locator-axis-page-7-block-4",
            }
            return {
                "id": str(getattr(item, "id", "")),
                "query": query,
                "answerability": str(getattr(item, "answerability", "unknown")) or "unknown",
                "generated_answer": "제공된 증거에서 답을 확인할 수 없습니다.",
                "retrieved_contexts": [dict(context)],
                "citations": [],
                "diagnostics": {
                    "retrieval_empty": False,
                    "generation_empty": False,
                    "citation_empty": True,
                    "gold_incomplete": True,
                },
            }

    dataset = tmp_path / "agentic_pdf_locator_axes_gold.jsonl"
    query = "7페이지 연결 손익계산서 영업실적 표의 영업이익은 얼마입니까?"
    write_jsonl(dataset, [{"id": "pdf_locator_axes_q", "query": query, "answerability": "unknown"}])

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {
                "source_family_hint": "pdf",
                "query_task": "cell_lookup",
                "row_filters": {
                    "page_number": "7",
                    "section_title": "연결 손익계산서",
                    "table_caption": "영업실적 표",
                },
                "target_axis": {"column": "영업이익", "value_type": "number"},
                "evidence_contract": [
                    "page_number",
                    "section_title",
                    "table_caption",
                    "target_column",
                    "display_value",
                    "bbox",
                    "locator_fingerprint",
                ],
                "intent_tokens": ["얼마입니까"],
            },
            {"raw_response_sha256": "sha256:agentic-pdf-locator-axes"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    baseline_adapter = PdfToolAdapter()
    baseline_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "agentic_pdf_locator_axes_off",
        top_k=1,
        run_id="agentic_pdf_locator_axes_off",
        output_mode="single",
        retrieval_adapter=baseline_adapter,
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
    )
    execute_adapter = PdfToolAdapter()
    execute_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "agentic_pdf_locator_axes_execute_once",
        top_k=1,
        run_id="agentic_pdf_locator_axes_execute_once",
        output_mode="single",
        retrieval_adapter=execute_adapter,
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        agentic_planner_mode="execute-once",
        llm_query_anchor_classifier=True,
        local_llm_composer_model="gemma4-e2b-local",
        skip_local_llm_composer_endpoint_check=True,
    )

    baseline_report = json.loads(baseline_bundle.report_path.read_text(encoding="utf-8"))
    report = json.loads(execute_bundle.report_path.read_text(encoding="utf-8"))
    planner = report["agentic_planner_execute_once"]
    row = report["items"][0]
    decision = planner["decisions"][0]

    assert baseline_adapter.query_log == [
        {
            "query_text": query,
            "top_k": 1,
            "planner_status": "",
            "expected_answer": "",
        }
    ]
    assert execute_adapter.query_log == [
        {
            "query_text": query,
            "top_k": 1,
            "planner_status": "planned_validated",
            "expected_answer": "",
        }
    ]
    assert baseline_report["evidence_gate"]["allowed_answer_count"] == 0
    assert report["evidence_gate"]["allowed_answer_count"] == 1
    assert planner["planner_action_counts"] == {"pdf_locator_tool": 1}
    assert planner["planner_failure_class_counts"] == {"tool_required_pdf": 1}
    assert planner["planner_execution"] == {
        "retrieval_executed": False,
        "tool_call_executed": True,
        "llm_retry_executed": False,
        "extra_query_count_executed": 0,
        "tool_call_count_executed": 1,
        "llm_retry_count_executed": 0,
    }
    assert planner["gate_delta"]["allowed_answer_count_delta"] == 1
    assert decision["executed"] is True
    assert decision["proposed_action"] == "pdf_locator_tool"
    assert decision["execution_status"] == "accepted_after_regating"
    assert decision["tool_name"] == "pdf_locator_tool_v1"
    assert decision["tool_call_count_executed"] == 1
    assert decision["extra_query_count_executed"] == 0
    assert decision["llm_retry_count_executed"] == 0
    assert "query_id" not in decision
    assert "expected_answer" not in decision
    assert row["agentic_planner_tool_use"]["tool_implementation"] == "pdf_locator_tool_v1"
    assert row["agentic_planner_tool_use"]["pdf_locator_execution_status"] == "accepted_after_regating"
    assert row["query_evidence_planner"]["validated_required_axes"] == [
        "page_number",
        "section_title",
        "table_caption",
        "target_column",
        "display_value",
        "bbox",
        "locator_fingerprint",
    ]
    selected = row["evidence_gate"]["selected_evidence"][0]
    assert selected["tool_name"] == "pdf_locator_tool_v1"
    assert selected["tool_policy"] == "source_owned_pdf_locator_only_no_raw_pdf_query_time_parsing"
    assert selected["page_number"] == "7"
    assert selected["target_column"] == "영업이익"
    assert output_file_names(tmp_path / "reports" / "rag_eval" / "agentic_pdf_locator_axes_execute_once") == ["report.json"]


def test_agentic_pdf_locator_candidate_rejects_page_summary_without_local_axis() -> None:
    row = {
        "query": "7페이지 연결 손익계산서 영업실적 표의 영업이익은 얼마입니까?",
        "retrieved_contexts": [
            {
                "doc_id": "doc-pdf-page-summary",
                "chunk_id": "chunk-pdf-page-summary",
                "source_atom_id": "src-pdf-page-summary",
                "evidence_bundle_id": "bundle-pdf-page-summary",
                "source_family": "PDF",
                "granularity": "page_summary",
                "text": "7페이지 연결 손익계산서 요약입니다.",
                "pdf_locator_text": "7페이지 연결 손익계산서 영업실적 표 영업이익은 123억원입니다.",
                "page_number": "7",
                "section_title": "연결 손익계산서",
            }
        ],
    }

    candidate, status = actual_rag_eval._agentic_planner_pdf_locator_candidate(row)

    assert candidate is None
    assert status == "skipped_missing_source_locator"


def test_agentic_pdf_locator_candidate_rejects_low_confidence_ocr() -> None:
    row = {
        "query": "7페이지 연결 손익계산서 영업실적 표의 영업이익은 얼마입니까?",
        "retrieved_contexts": [
            {
                "doc_id": "doc-pdf-ocr",
                "chunk_id": "chunk-pdf-ocr",
                "source_atom_id": "src-pdf-ocr",
                "evidence_bundle_id": "bundle-pdf-ocr",
                "source_family": "PDF",
                "granularity": "page_block",
                "text": "",
                "ocr_text": "7페이지 연결 손익계산서 영업실적 표 영업이익은 123억원입니다.",
                "ocr_used": True,
                "ocr_confidence": 0.42,
                "page_number": "7",
                "section_title": "연결 손익계산서",
                "table_caption": "영업실적 표",
                "bbox": "[72,260,510,318]",
                "locator_fingerprint": "pdf-ocr-low-confidence",
            }
        ],
    }

    candidate, status = actual_rag_eval._agentic_planner_pdf_locator_candidate(row)

    assert candidate is None
    assert status == "skipped_missing_source_locator"


def test_agentic_planner_execute_once_runs_xlsx_locator_tool_after_checkpoint_c(tmp_path: Path) -> None:
    dataset = tmp_path / "agentic_xlsx_tool_gold.jsonl"
    context = tmp_path / "agentic_xlsx_tool_context.jsonl"
    table_text = (
        "sheet=일반현황 | range=A802:J851 | 장기요양기관이름 | 우편번호 | 시도코드 | "
        "시군구코드 | 법정동코드 | 시도 시군구 법정동명 | 지정일자 | 설치신고일자 | "
        "기관별 상세주소 12726000180 | 해오름요양원 | 42222 | 27 | 260 | 110 | "
        "대구광역시 수성구 파동 | 2012-03-06 | 2012-03-06 | "
        "대구광역시 수성구 파동로51길 96 (파동)"
    )
    write_jsonl(
        dataset,
        [
            {
                "id": "agentic_xlsx_q",
                "query": "2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 무엇입니까?",
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "agentic_xlsx_q",
                "generated_answer": "대구광역시 수성구 파동로51길 96 (파동)",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-agentic-xlsx",
                        "chunk_id": "chunk-agentic-table",
                        "source_atom_id": "src-agentic-xlsx",
                        "evidence_bundle_id": "bundle-agentic-xlsx",
                        "source_family": "XLSX",
                        "granularity": "table_range",
                        "text": table_text,
                        "sheet": "일반현황",
                        "cell_range": "A802:J851",
                    }
                ],
                "citations": [],
            }
        ],
    )

    baseline_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "agentic_xlsx_tool_off",
        context_jsonl_path=context,
        top_k=1,
        run_id="agentic_xlsx_tool_off",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
    )
    execute_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "agentic_xlsx_tool_execute_once",
        context_jsonl_path=context,
        top_k=1,
        run_id="agentic_xlsx_tool_execute_once",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        agentic_planner_mode="execute-once",
    )

    baseline_report = json.loads(baseline_bundle.report_path.read_text(encoding="utf-8"))
    report = json.loads(execute_bundle.report_path.read_text(encoding="utf-8"))
    planner = report["agentic_planner_execute_once"]
    row = report["items"][0]
    decision = planner["decisions"][0]

    assert baseline_report["evidence_gate"]["allowed_answer_count"] == 0
    assert report["evidence_gate"]["allowed_answer_count"] == 1
    assert "xlsx_locator_tool_execute_once" not in report
    assert planner["planner_action_counts"] == {"xlsx_cell_or_table_tool": 1}
    assert planner["planner_failure_class_counts"] == {"tool_required_xlsx": 1}
    assert planner["planner_execution"] == {
        "retrieval_executed": False,
        "tool_call_executed": True,
        "llm_retry_executed": False,
        "extra_query_count_executed": 0,
        "tool_call_count_executed": 1,
        "llm_retry_count_executed": 0,
    }
    assert planner["gate_delta"]["allowed_answer_count_delta"] == 1
    assert decision["executed"] is True
    assert decision["proposed_action"] == "xlsx_cell_or_table_tool"
    assert decision["execution_status"] == "accepted_after_regating"
    assert decision["tool_name"] == "xlsx_locator_tool_v1"
    assert decision["tool_call_count_executed"] == 1
    assert decision["extra_query_count_executed"] == 0
    assert decision["llm_retry_count_executed"] == 0
    assert "query_id" not in decision
    assert "expected_answer" not in decision
    assert row["xlsx_locator_tool_use"]["execution_status"] == "accepted_after_regating"
    assert row["agentic_planner_tool_use"]["tool_implementation"] == "xlsx_locator_tool_v1"
    selected = row["evidence_gate"]["selected_evidence"][0]
    assert selected["tool_name"] == "xlsx_locator_tool_v1"
    assert selected["row_label"] == "해오름요양원"
    assert selected["target_column"] == "기관별 상세주소"
    assert output_file_names(tmp_path / "reports" / "rag_eval" / "agentic_xlsx_tool_execute_once") == ["report.json"]


def test_agentic_planner_execute_once_runs_xlsx_locator_with_local_llm_composer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "agentic_xlsx_local_llm_gold.jsonl"
    context = tmp_path / "agentic_xlsx_local_llm_context.jsonl"
    table_text = (
        "sheet=일반현황 | range=A802:J851 | 장기요양기관이름 | 우편번호 | 시도코드 | "
        "시군구코드 | 법정동코드 | 시도 시군구 법정동명 | 지정일자 | 설치신고일자 | "
        "기관별 상세주소 12726000180 | 해오름요양원 | 42222 | 27 | 260 | 110 | "
        "대구광역시 수성구 파동 | 2012-03-06 | 2012-03-06 | "
        "대구광역시 수성구 파동로51길 96 (파동)"
    )
    write_jsonl(
        dataset,
        [
            {
                "id": "agentic_xlsx_local_llm_q",
                "query": "2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 무엇입니까?",
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "agentic_xlsx_local_llm_q",
                "generated_answer": "대구광역시 수성구 파동로51길 96 (파동)",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-agentic-xlsx-local-llm",
                        "chunk_id": "chunk-agentic-table-local-llm",
                        "source_atom_id": "src-agentic-xlsx-local-llm",
                        "evidence_bundle_id": "bundle-agentic-xlsx-local-llm",
                        "source_family": "XLSX",
                        "granularity": "table_range",
                        "text": table_text,
                        "sheet": "일반현황",
                        "cell_range": "A802:J851",
                    }
                ],
                "citations": [],
            }
        ],
    )
    captured_prompts: list[str] = []

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**kwargs: object) -> tuple[dict, dict]:
        prompt = str(kwargs["prompt"])
        captured_prompts.append(prompt)
        assert "해오름요양원" in prompt
        assert "기관별 상세주소" in prompt
        return (
            {
                "answer": "대구광역시 수성구 파동로51길 96 (파동)",
                "citation_evidence_ids": ["bundle-agentic-xlsx-local-llm"],
            },
            {
                "raw_response_sha256": "sha256:agentic-xlsx-local-llm-response",
                "strict_json": True,
            },
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    execute_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "agentic_xlsx_local_llm_execute_once",
        context_jsonl_path=context,
        top_k=1,
        run_id="agentic_xlsx_local_llm_execute_once",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-local-llm-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        agentic_planner_mode="execute-once",
        local_llm_composer_backend="llamacpp",
        local_llm_composer_base_url="http://localhost:8081/v1",
        local_llm_composer_model="gemma4-e2b-local",
        skip_local_llm_composer_endpoint_check=True,
    )

    report = json.loads(execute_bundle.report_path.read_text(encoding="utf-8"))
    planner = report["agentic_planner_execute_once"]
    row = report["items"][0]
    local_meta = row["answer_composer"]["local_llm"]

    assert captured_prompts and len(captured_prompts) == 1
    assert report["evidence_gate"]["allowed_answer_count"] == 1
    assert report["generator_config"]["provider"] == "selected-evidence-local-llm-v1"
    assert report["generator_config"]["local_llm_composer_generated_count"] == 1
    assert report["generator_config"]["local_llm_prompt_payload_written"] is False
    assert report["generator_config"]["local_llm_raw_response_payload_written"] is False
    assert planner["planner_action_counts"] == {"xlsx_cell_or_table_tool": 1}
    assert planner["planner_expected_llm_retry_count"] == 0
    assert planner["planner_execution"] == {
        "retrieval_executed": False,
        "tool_call_executed": True,
        "llm_retry_executed": False,
        "extra_query_count_executed": 0,
        "tool_call_count_executed": 1,
        "llm_retry_count_executed": 0,
    }
    assert row["answer_composer"]["provider"] == "selected-evidence-local-llm-v1"
    assert local_meta["status"] == "generated"
    assert local_meta["model"] == "gemma4-e2b-local"
    assert local_meta["raw_response_sha256"] == "sha256:agentic-xlsx-local-llm-response"
    assert "prompt" not in local_meta
    assert "raw_response" not in local_meta
    assert row["generated_answer"] == "대구광역시 수성구 파동로51길 96 (파동)"
    assert row["evidence_gate"]["selected_evidence"][0]["tool_name"] == "xlsx_locator_tool_v1"
    assert row["agentic_planner_tool_use"]["xlsx_locator_execution_status"] == "accepted_after_regating"
    assert "xlsx_locator_tool_execute_once" not in report
    assert output_file_names(tmp_path / "reports" / "rag_eval" / "agentic_xlsx_local_llm_execute_once") == ["report.json"]


def test_xlsx_locator_tool_execute_once_runs_source_owned_candidate_and_regates(tmp_path: Path) -> None:
    dataset = tmp_path / "xlsx_locator_tool_gold.jsonl"
    context = tmp_path / "xlsx_locator_tool_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_locator_tool_execute_once"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx_locator_q",
                "query": "2019년 2월 5호선 승차총승객수",
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "xlsx_locator_q",
                "generated_answer": "15,446,522명",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-xlsx-locator",
                        "chunk_id": "chunk-axis-sparse",
                        "source_atom_id": "src-xlsx-locator",
                        "evidence_bundle_id": "bundle-xlsx-locator",
                        "source_family": "XLSX",
                        "granularity": "table_row",
                        "text": "15,446,522명",
                        "xlsx_locator_text": "2019년 2월 5호선 승차총승객수 15,446,522명",
                        "xlsx_locator_metadata": {
                            "sheet": "2019년 2월",
                            "cell_range": "A7:J7",
                            "cell": "F7",
                            "row_index_1based": "7",
                            "row_label": "5호선",
                            "column_label": "승차총승객수",
                            "target_column": "승차총승객수",
                            "header_path": "승하차 > 승차총승객수",
                            "table_id": "sheet-201902-main-table",
                        },
                    }
                ],
                "citations": [],
            }
        ],
    )

    baseline_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "xlsx_locator_tool_off",
        context_jsonl_path=context,
        top_k=1,
        run_id="xlsx_locator_tool_off",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
    )
    execute_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="xlsx_locator_tool_execute_once",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        xlsx_locator_tool_execute_once=True,
    )

    baseline_report = json.loads(baseline_bundle.report_path.read_text(encoding="utf-8"))
    report = json.loads(execute_bundle.report_path.read_text(encoding="utf-8"))
    locator = report["xlsx_locator_tool_execute_once"]
    row = report["items"][0]
    tool_use = row["xlsx_locator_tool_use"]

    assert baseline_report["evidence_gate"]["allowed_answer_count"] == 0
    assert baseline_report["evidence_gate"]["unsupported_answer_blocked_count"] == 1
    assert report["evidence_gate"]["allowed_answer_count"] == 1
    assert report["evidence_gate"]["unsupported_answer_blocked_count"] == 0
    assert "agentic_planner_execute_once" not in report

    assert locator["schema_version"] == "actual_rag_eval.xlsx_locator_tool_execute_once.v1"
    assert locator["enabled"] is True
    assert locator["report_only_diagnostic"] is True
    assert locator["official_metric"] is False
    assert locator["tool_name"] == "xlsx_locator_tool_v1"
    assert locator["eligible_failed_row_count"] == 1
    assert locator["tool_invocation_count"] == 1
    assert locator["accepted_candidate_count"] == 1
    assert locator["rejected_candidate_count"] == 0
    assert locator["tool_execution_status_counts"] == {"accepted_after_regating": 1}
    assert locator["candidate_confidence_tier_counts"] == {"high": 1}
    assert locator["candidate_rejection_reason_counts"] == {"accepted_for_regating": 1}
    assert locator["candidate_source_family_counts"] == {"XLSX": 1}
    assert locator["query_anchor_tool_acceptance_diagnostic"]["source_family_hint_counts"] == {"unknown": 1}
    assert locator["query_anchor_tool_acceptance_diagnostic"]["query_task_counts"] == {"unknown": 1}
    assert locator["query_anchor_tool_acceptance_diagnostic"]["uses_expected_fields"] is False
    assert locator["query_anchor_tool_acceptance_diagnostic"]["uses_gold_fields"] is False
    assert locator["query_anchor_tool_acceptance_diagnostic"]["uses_qrels_or_labels"] is False
    assert all(
        "item_id" not in summary
        for summary in locator["query_anchor_tool_acceptance_diagnostic"]["item_summaries"]
    )
    encoded_query_anchor_diagnostic = json.dumps(
        locator["query_anchor_tool_acceptance_diagnostic"],
        ensure_ascii=False,
    )
    assert '"item_id"' not in encoded_query_anchor_diagnostic
    assert '"xlsx_locator_q"' not in encoded_query_anchor_diagnostic
    assert locator["official_metric_input_rows"] == 0
    assert locator["official_metric_input_rows_created"] == 0
    assert locator["official_metric_input_rows_consumed"] == 0
    assert locator["before_gate"]["allowed_answer_count"] == 0
    assert locator["after_gate"]["allowed_answer_count"] == 1
    assert locator["gate_delta"]["allowed_answer_count_delta"] == 1
    assert locator["run_record"] == {
        "contract": "typed_record_projection_v1",
        "record_type": "XlsxLocatorRunRecord",
        "serializer": "compact_report_projection",
    }
    assert locator["run_store"]["backend"] == "repo_local_sqlite"
    assert locator["run_store"]["path"].endswith("run.sqlite")
    assert set(locator["run_store"]["tables"]) >= {
        "runs",
        "items",
        "retrieved_contexts",
        "selected_evidence",
        "tool_invocations",
        "tool_candidates",
        "gate_results",
        "residuals",
        "guardrails",
    }
    assert "decisions" not in locator
    assert "candidates" not in locator
    assert "tool_uses" not in locator
    assert locator["guardrail_status"]["raw_xlsx_query_time_parsing_used"] is False
    assert locator["guardrail_status"]["gold_or_qrels_or_label_or_expected_used"] is False
    assert locator["guardrail_status"]["official_metric_input_rows"] == 0
    assert locator["forbidden_input_fields_used"] == []
    assert locator["raw_xlsx_query_time_parsing_used"] is False
    assert locator["gold_or_qrels_or_label_or_expected_used"] is False
    assert locator["residual_before"]["classification_counts"] == {
        "selected_evidence_has_value_missing_axis": 1,
    }
    assert locator["residual_after"]["classification_counts"] == {}

    assert tool_use["execution_status"] == "accepted_after_regating"
    assert tool_use["candidate_count"] == 1
    assert tool_use["accepted_candidate_count"] == 1
    assert set(tool_use["matched_query_anchors"]) >= {"2019년", "2월", "5호선", "승차총승객수"}
    assert tool_use["remaining_missing_query_anchors"] == []
    assert tool_use["input_policy"] == "source_owned_locator_only_no_raw_xlsx_query_time_parsing"
    assert tool_use["output_policy"] == "selected_evidence_candidate_must_pass_unchanged_gate"
    selected = row["evidence_gate"]["selected_evidence"][0]
    assert selected["tool_name"] == "xlsx_locator_tool_v1"
    assert selected["tool_policy"] == "source_owned_locator_only_no_raw_xlsx_query_time_parsing"
    assert selected["row_label"] == "5호선"
    assert selected["target_column"] == "승차총승객수"
    assert output_file_names(output_dir) == ["report.json", "run.sqlite"]

    sqlite_path = output_dir / "run.sqlite"
    with sqlite3.connect(sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert set(locator["run_store"]["tables"]).issubset(tables)
        run = conn.execute(
            "SELECT dataset_slug, collection, schema_version, schema_versions_json, backend, tool_name, "
            "official_metric_input_rows, guardrail_summary_json, record_json FROM runs"
        ).fetchone()
        assert run["dataset_slug"] == "xlsx_locator_tool_gold"
        assert run["collection"] == "deterministic_fixture_or_precomputed_pipeline_output"
        assert run["schema_version"] == "actual_rag_eval.xlsx_locator_tool_execute_once.v1"
        schema_versions = json.loads(run["schema_versions_json"])
        assert schema_versions["actual_rag_eval"] == "actual_rag_eval.v1"
        assert schema_versions["xlsx_locator_tool_execute_once"] == "actual_rag_eval.xlsx_locator_tool_execute_once.v1"
        assert run["backend"] == "repo_local_sqlite"
        assert run["tool_name"] == "xlsx_locator_tool_v1"
        assert run["official_metric_input_rows"] == 0
        guardrail_summary = json.loads(run["guardrail_summary_json"])
        assert guardrail_summary["official_metric_input_rows"] == 0
        assert guardrail_summary["forbidden_input_fields_used"] == []
        run_record = json.loads(run["record_json"])
        assert run_record["tool_invocation_count"] == 1
        assert run_record["tool_uses"][0]["source_family_hint"] == ""
        assert run_record["tool_uses"][0]["query_task"] == ""
        invocation_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(tool_invocations)")
        }
        assert "source_family_hint" not in invocation_columns
        assert "query_task" not in invocation_columns
        invocation = conn.execute(
            "SELECT execution_status, candidate_count, accepted_candidate_count FROM tool_invocations"
        ).fetchone()
        assert dict(invocation) == {
            "execution_status": "accepted_after_regating",
            "candidate_count": 1,
            "accepted_candidate_count": 1,
        }
        candidate = conn.execute(
            "SELECT row_label, target_column, locator_text_source, accepted_for_regating, rejection_reason, "
            "input_fields_used_json "
            "FROM tool_candidates"
        ).fetchone()
        assert candidate["row_label"] == "5호선"
        assert candidate["target_column"] == "승차총승객수"
        assert candidate["locator_text_source"] == "explicit_locator_text"
        assert candidate["accepted_for_regating"] == 1
        assert candidate["rejection_reason"] == ""
        assert "xlsx_locator_text" in json.loads(candidate["input_fields_used_json"])
        phases = {
            (row["phase"], row["classification"])
            for row in conn.execute("SELECT phase, classification FROM residuals ORDER BY phase")
        }
        assert ("before", "selected_evidence_has_value_missing_axis") in phases
        assert ("after", "no_residual") in phases
        gate_rows = {
            (row["phase"], row["answer_gate_decision"])
            for row in conn.execute("SELECT phase, answer_gate_decision FROM gate_results ORDER BY phase")
        }
        assert gate_rows == {("before", "block_unsupported_answer"), ("after", "allow_answer")}

    legacy_sqlite_path = tmp_path / "legacy-run-without-source-date-aliases.sqlite"
    with sqlite3.connect(sqlite_path) as source, sqlite3.connect(legacy_sqlite_path) as target:
        source.backup(target)
    with sqlite3.connect(legacy_sqlite_path) as conn:
        columns = [
            row[1]
            for row in conn.execute("PRAGMA table_info(tool_candidates)")
            if row[1] != "source_date_aliases_json"
        ]
        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        conn.execute("ALTER TABLE tool_candidates RENAME TO tool_candidates_with_source_date_aliases")
        conn.execute(f"CREATE TABLE tool_candidates AS SELECT {quoted_columns} FROM tool_candidates_with_source_date_aliases")
        conn.execute("DROP TABLE tool_candidates_with_source_date_aliases")
    legacy_locator = json.loads(json.dumps(locator))
    legacy_locator["run_store"]["path"] = legacy_sqlite_path.as_posix()
    actual_rag_eval.validate_xlsx_locator_run_store(
        "xlsx_locator_tool_execute_once",
        legacy_locator,
        run_store_path=legacy_sqlite_path,
    )

    bad_legacy_sqlite_path = tmp_path / "legacy-run-without-required-locator-source.sqlite"
    with sqlite3.connect(sqlite_path) as source, sqlite3.connect(bad_legacy_sqlite_path) as target:
        source.backup(target)
    with sqlite3.connect(bad_legacy_sqlite_path) as conn:
        columns = [
            row[1]
            for row in conn.execute("PRAGMA table_info(tool_candidates)")
            if row[1] != "locator_text_source"
        ]
        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        conn.execute("ALTER TABLE tool_candidates RENAME TO tool_candidates_missing_required_locator_source")
        conn.execute(
            "CREATE TABLE tool_candidates AS SELECT "
            f"{quoted_columns} FROM tool_candidates_missing_required_locator_source"
        )
        conn.execute("DROP TABLE tool_candidates_missing_required_locator_source")
    bad_legacy_locator = json.loads(json.dumps(locator))
    bad_legacy_locator["run_store"]["path"] = bad_legacy_sqlite_path.as_posix()
    with pytest.raises(DatasetSchemaError, match="tool_candidates missing column locator_text_source"):
        actual_rag_eval.validate_xlsx_locator_run_store(
            "xlsx_locator_tool_execute_once",
            bad_legacy_locator,
            run_store_path=bad_legacy_sqlite_path,
        )

    missing_invocation_column_path = tmp_path / "run-without-source-row-invocation-column.sqlite"
    with sqlite3.connect(sqlite_path) as source, sqlite3.connect(missing_invocation_column_path) as target:
        source.backup(target)
    with sqlite3.connect(missing_invocation_column_path) as conn:
        columns = [
            row[1]
            for row in conn.execute("PRAGMA table_info(tool_invocations)")
            if row[1] != "source_row_context_candidate_count"
        ]
        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        conn.execute("ALTER TABLE tool_invocations RENAME TO tool_invocations_missing_source_row_context")
        conn.execute(
            "CREATE TABLE tool_invocations AS SELECT "
            f"{quoted_columns} FROM tool_invocations_missing_source_row_context"
        )
        conn.execute("DROP TABLE tool_invocations_missing_source_row_context")
    missing_invocation_locator = json.loads(json.dumps(locator))
    missing_invocation_locator["run_store"]["path"] = missing_invocation_column_path.as_posix()
    with pytest.raises(DatasetSchemaError, match="tool_invocations missing column source_row_context_candidate_count"):
        actual_rag_eval.validate_xlsx_locator_run_store(
            "xlsx_locator_tool_execute_once",
            missing_invocation_locator,
            run_store_path=missing_invocation_column_path,
        )

    with sqlite3.connect(sqlite_path) as conn:
        conn.execute("UPDATE items SET query_task = 'gold_lookup'")
    with pytest.raises(DatasetSchemaError, match="items.query_task invalid"):
        actual_rag_eval.validate_xlsx_locator_run_store(
            "xlsx_locator_tool_execute_once",
            locator,
            run_store_path=sqlite_path,
        )

    bad_diagnostic_locator = json.loads(json.dumps(locator))
    bad_diagnostic_locator["query_anchor_tool_acceptance_diagnostic"]["schema_version"] = "wrong"
    with pytest.raises(DatasetSchemaError, match="query_anchor_tool_acceptance_diagnostic.schema_version"):
        actual_rag_eval.validate_xlsx_locator_tool_execute_once("xlsx_locator_tool_execute_once", bad_diagnostic_locator)

    metric_diagnostic_locator = json.loads(json.dumps(locator))
    metric_diagnostic_locator["query_anchor_tool_acceptance_diagnostic"]["official_metric"] = True
    with pytest.raises(DatasetSchemaError, match="query_anchor_tool_acceptance_diagnostic.official_metric"):
        actual_rag_eval.validate_xlsx_locator_tool_execute_once(
            "xlsx_locator_tool_execute_once",
            metric_diagnostic_locator,
        )

    leaked_diagnostic_locator = json.loads(json.dumps(locator))
    leaked_diagnostic_locator["query_anchor_tool_acceptance_diagnostic"]["item_summaries"][0][
        "source_atom_id"
    ] = "src-should-not-leak"
    with pytest.raises(DatasetSchemaError, match="query_anchor_tool_acceptance_diagnostic.*source_atom_id"):
        actual_rag_eval.validate_xlsx_locator_tool_execute_once(
            "xlsx_locator_tool_execute_once",
            leaked_diagnostic_locator,
        )

    nested_leaked_diagnostic_locator = json.loads(json.dumps(locator))
    nested_leaked_diagnostic_locator["query_anchor_tool_acceptance_diagnostic"]["item_summaries"][0][
        "debug"
    ] = {"raw_prompt": "SECRET_PROMPT"}
    with pytest.raises(DatasetSchemaError, match="query_anchor_tool_acceptance_diagnostic.*raw_prompt"):
        actual_rag_eval.validate_xlsx_locator_tool_execute_once(
            "xlsx_locator_tool_execute_once",
            nested_leaked_diagnostic_locator,
        )

    top_level_leaked_diagnostic_locator = json.loads(json.dumps(locator))
    top_level_leaked_diagnostic_locator["query_anchor_tool_acceptance_diagnostic"][
        "candidate_id"
    ] = "candidate-should-not-leak"
    with pytest.raises(DatasetSchemaError, match="query_anchor_tool_acceptance_diagnostic.*candidate_id"):
        actual_rag_eval.validate_xlsx_locator_tool_execute_once(
            "xlsx_locator_tool_execute_once",
            top_level_leaked_diagnostic_locator,
        )

    mismatched_diagnostic_locator = json.loads(json.dumps(locator))
    mismatched_diagnostic_locator["query_anchor_tool_acceptance_diagnostic"]["tool_invocation_count"] = 999
    with pytest.raises(DatasetSchemaError, match="query_anchor_tool_acceptance_diagnostic.tool_invocation_count"):
        actual_rag_eval.validate_xlsx_locator_tool_execute_once(
            "xlsx_locator_tool_execute_once",
            mismatched_diagnostic_locator,
        )

    missing_required_diagnostic_locator = json.loads(json.dumps(locator))
    del missing_required_diagnostic_locator["query_anchor_tool_acceptance_diagnostic"]["top_missing_query_anchors"]
    with pytest.raises(DatasetSchemaError, match="query_anchor_tool_acceptance_diagnostic.top_missing_query_anchors"):
        actual_rag_eval.validate_xlsx_locator_tool_execute_once(
            "xlsx_locator_tool_execute_once",
            missing_required_diagnostic_locator,
        )

    missing_store_locator = json.loads(json.dumps(locator))
    missing_store_locator["run_store"]["path"] = (tmp_path / "missing-run.sqlite").as_posix()
    with pytest.raises(DatasetSchemaError, match="RunStore missing"):
        actual_rag_eval.validate_xlsx_locator_run_store("xlsx_locator_tool_execute_once", missing_store_locator)

    corrupt_store_path = tmp_path / "corrupt-run.sqlite"
    with sqlite3.connect(corrupt_store_path) as conn:
        conn.execute("CREATE TABLE runs (run_id TEXT)")
    corrupt_store_locator = json.loads(json.dumps(locator))
    corrupt_store_locator["run_store"]["path"] = corrupt_store_path.as_posix()
    with pytest.raises(DatasetSchemaError, match="missing table"):
        actual_rag_eval.validate_xlsx_locator_run_store("xlsx_locator_tool_execute_once", corrupt_store_locator)


def test_xlsx_locator_tool_runstore_output_mode_writes_sqlite_without_report_json(tmp_path: Path) -> None:
    dataset = tmp_path / "xlsx_locator_runstore_gold.jsonl"
    context = tmp_path / "xlsx_locator_runstore_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_locator_runstore_only"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx_locator_runstore_q",
                "query": "2019년 2월 5호선 승차총승객수",
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "xlsx_locator_runstore_q",
                "generated_answer": "15,446,522명",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-xlsx-runstore",
                        "chunk_id": "chunk-axis-sparse",
                        "source_atom_id": "src-xlsx-runstore",
                        "evidence_bundle_id": "bundle-xlsx-runstore",
                        "source_family": "XLSX",
                        "granularity": "table_row",
                        "text": "15,446,522명",
                        "xlsx_locator_text": "2019년 2월 5호선 승차총승객수 15,446,522명",
                        "xlsx_locator_metadata": {
                            "sheet": "2019년 2월",
                            "cell_range": "A7:J7",
                            "cell": "F7",
                            "row_index_1based": "7",
                            "row_label": "5호선",
                            "column_label": "승차총승객수",
                            "target_column": "승차총승객수",
                            "header_path": "승하차 > 승차총승객수",
                            "table_id": "sheet-201902-main-table",
                        },
                    }
                ],
                "citations": [],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="xlsx_locator_runstore_only",
        output_mode="runstore",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        xlsx_locator_tool_execute_once=True,
    )

    run_store_path = output_dir / "run.sqlite"
    assert output_file_names(output_dir) == ["run.sqlite"]
    assert not (output_dir / "report.json").exists()
    assert bundle.report_path is None
    assert bundle.summary_path == run_store_path
    assert bundle.summary["artifact_paths"]["report_json"] == ""
    assert bundle.summary["artifact_paths"]["summary_json"] == ""
    assert bundle.summary["artifact_paths"]["xlsx_locator_run_sqlite"] == run_store_path.as_posix()
    assert bundle.summary["artifact_contract"]["output_mode"] == "runstore"
    assert bundle.summary["artifact_contract"]["runstore_only"] is True
    assert bundle.summary["artifact_contract"]["routine_run_file_policy"] == "run.sqlite_only_no_report_json"

    with sqlite3.connect(run_store_path) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute("SELECT run_id, backend, tool_name, enabled FROM runs").fetchone()
        assert dict(run) == {
            "run_id": "xlsx_locator_runstore_only",
            "backend": "repo_local_sqlite",
            "tool_name": "xlsx_locator_tool_v1",
            "enabled": 1,
        }
        invocation = conn.execute(
            "SELECT execution_status, candidate_count, accepted_candidate_count FROM tool_invocations"
        ).fetchone()
        assert dict(invocation) == {
            "execution_status": "accepted_after_regating",
            "candidate_count": 1,
            "accepted_candidate_count": 1,
        }
        selected = conn.execute(
            "SELECT tool_name, row_label, target_column FROM selected_evidence WHERE item_index = 0"
        ).fetchone()
        assert dict(selected) == {
            "tool_name": "xlsx_locator_tool_v1",
            "row_label": "5호선",
            "target_column": "승차총승객수",
        }


def test_runstore_output_mode_requires_xlsx_locator_execute_once(tmp_path: Path) -> None:
    dataset = tmp_path / "runstore_requires_locator_gold.jsonl"
    context = tmp_path / "runstore_requires_locator_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "runstore_requires_locator"
    write_jsonl(dataset, [{"id": "q1", "query": "capital?", "answerability": "answerable"}])
    write_jsonl(context, [{"id": "q1", "generated_answer": "Seoul", "retrieved_contexts": [], "citations": []}])

    with pytest.raises(DatasetSchemaError, match="output_mode=runstore requires xlsx locator tool execute-once"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=output_dir,
            context_jsonl_path=context,
            top_k=1,
            run_id="runstore_requires_locator",
            output_mode="runstore",
        )

    assert not output_dir.exists()


def test_xlsx_locator_tool_execute_once_reports_source_owned_support_text_inputs(tmp_path: Path) -> None:
    dataset = tmp_path / "xlsx_locator_tool_support_text_gold.jsonl"
    context = tmp_path / "xlsx_locator_tool_support_text_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_locator_tool_support_text"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx_locator_support_text_q",
                "query": "2019년 2월 5호선 승차총승객수",
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "xlsx_locator_support_text_q",
                "generated_answer": "15,446,522명",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-xlsx-locator",
                        "chunk_id": "chunk-support-text",
                        "source_atom_id": "src-xlsx-locator-support-text",
                        "evidence_bundle_id": "bundle-xlsx-locator-support-text",
                        "source_family": "XLSX",
                        "granularity": "table_row",
                        "title": "must-not-be-used.xlsx",
                        "text": "2019년 2월 5호선 승차총승객수 15,446,522명",
                        "xlsx_locator_metadata": {
                            "sheet": "2019년 2월",
                            "cell_range": "A7:J7",
                            "cell": "F7",
                            "row_index_1based": "7",
                            "row_label": "5호선",
                            "column_label": "승차총승객수",
                            "target_column": "승차총승객수",
                            "header_path": "승하차 > 승차총승객수",
                            "table_id": "sheet-201902-main-table",
                        },
                    }
                ],
                "citations": [],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="xlsx_locator_tool_support_text",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        xlsx_locator_tool_execute_once=True,
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    locator = report["xlsx_locator_tool_execute_once"]
    row = report["items"][0]

    assert report["evidence_gate"]["allowed_answer_count"] == 1
    assert locator["accepted_candidate_count"] == 1
    assert row["xlsx_locator_tool_use"]["execution_status"] == "accepted_after_regating"
    with sqlite3.connect(output_dir / "run.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        candidate = conn.execute(
            "SELECT locator_text_source, input_fields_used_json FROM tool_candidates"
        ).fetchone()
        assert candidate["locator_text_source"] == "source_owned_support_text"
        input_fields = set(json.loads(candidate["input_fields_used_json"]))
        assert "text" in input_fields
        assert "locator_text_source" in input_fields
        assert "xlsx_locator_text" not in input_fields
        assert {"sheet", "cell_range", "row_label", "target_column"}.issubset(input_fields)


def test_xlsx_locator_tool_execute_once_derives_table_row_from_source_owned_text(tmp_path: Path) -> None:
    dataset = tmp_path / "xlsx_locator_tool_table_text_gold.jsonl"
    context = tmp_path / "xlsx_locator_tool_table_text_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_locator_tool_table_text"
    table_text = (
        "sheet=일반현황 | range=A802:J851 | 장기요양기관이름 | 우편번호 | 시도코드 | "
        "시군구코드 | 법정동코드 | 시도 시군구 법정동명 | 지정일자 | 설치신고일자 | "
        "기관별 상세주소 12726000180 | 해오름요양원 | 42222 | 27 | 260 | 110 | "
        "대구광역시 수성구 파동 | 2012-03-06 | 2012-03-06 | "
        "대구광역시 수성구 파동로51길 96 (파동) 12726000192 | 어르신노인요양시설 | "
        "42216 | 27 | 260 | 111 | 대구광역시 수성구 두산동 | 2012-11-30 | "
        "2012-11-30 | 대구광역시 수성구 용학로25길 6 4층"
    )
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx_locator_table_text_q",
                "query": "2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 무엇입니까?",
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "xlsx_locator_table_text_q",
                "generated_answer": "대구광역시 수성구 파동로51길 96 (파동)",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-xlsx-locator-table",
                        "chunk_id": "chunk-table-range",
                        "source_atom_id": "src-xlsx-locator-table",
                        "evidence_bundle_id": "bundle-xlsx-locator-table",
                        "source_family": "XLSX",
                        "granularity": "table_range",
                        "text": table_text,
                        "sheet": "일반현황",
                        "cell_range": "A802:J851",
                    }
                ],
                "citations": [],
            }
        ],
    )

    baseline_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "xlsx_locator_tool_table_text_off",
        context_jsonl_path=context,
        top_k=1,
        run_id="xlsx_locator_tool_table_text_off",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
    )
    execute_bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="xlsx_locator_tool_table_text",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        xlsx_locator_tool_execute_once=True,
    )

    baseline_report = json.loads(baseline_bundle.report_path.read_text(encoding="utf-8"))
    report = json.loads(execute_bundle.report_path.read_text(encoding="utf-8"))
    locator = report["xlsx_locator_tool_execute_once"]
    row = report["items"][0]

    assert baseline_report["evidence_gate"]["allowed_answer_count"] == 0
    assert report["evidence_gate"]["allowed_answer_count"] == 1
    assert locator["gate_delta"]["allowed_answer_count_delta"] == 1
    assert locator["residual_before"]["classification_counts"] == {
        "selected_evidence_has_value_missing_axis": 1,
    }
    assert locator["residual_after"]["classification_counts"] == {}
    assert row["xlsx_locator_tool_use"]["execution_status"] == "accepted_after_regating"
    assert {"2012년", "3월", "해오름요양원", "기관별", "상세주소"}.issubset(
        set(row["xlsx_locator_tool_use"]["matched_query_anchors"])
    )
    selected = row["evidence_gate"]["selected_evidence"][0]
    assert selected["tool_name"] == "xlsx_locator_tool_v1"
    assert selected["row_label"] == "해오름요양원"
    assert selected["target_column"] == "기관별 상세주소"
    assert selected["display_value"] == "대구광역시 수성구 파동로51길 96 (파동)"
    assert selected["synthetic_table_id"].startswith("xlsx_locator_table:")
    assert "source_date_alias=2012년 3월" in selected["text"]
    with sqlite3.connect(output_dir / "run.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        candidate = conn.execute(
            "SELECT row_label, target_column, display_value, synthetic_table_id, locator_text_source, input_fields_used_json "
            "FROM tool_candidates WHERE accepted_for_regating = 1"
        ).fetchone()
        assert candidate["row_label"] == "해오름요양원"
        assert candidate["target_column"] == "기관별 상세주소"
        assert candidate["display_value"] == "대구광역시 수성구 파동로51길 96 (파동)"
        assert candidate["synthetic_table_id"].startswith("xlsx_locator_table:")
        assert candidate["locator_text_source"] == "source_owned_table_row_text"
        input_fields = set(json.loads(candidate["input_fields_used_json"]))
        assert {"text", "sheet", "cell_range", "row_label", "target_column", "display_value", "synthetic_table_id"}.issubset(input_fields)


def test_llm_query_anchor_classifier_keeps_structural_anchors_and_drops_intent_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**kwargs: object) -> tuple[dict, dict]:
        prompt = str(kwargs["prompt"])
        captured["prompt"] = prompt
        captured["timeout_seconds"] = kwargs.get("timeout_seconds")
        assert "2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 무엇입니까?" in prompt
        for forbidden in ("expected_answer", "expected_evidence", "qrels", "row_id", "baseline_topk"):
            assert forbidden not in prompt
        return (
            {
                "intent_tokens": ["무엇입니까", "지정된", "2012년"],
                "numeric_or_date_anchors": ["2012년", "3월"],
                "entity_anchors": ["해오름요양원"],
                "measure_anchors": ["기관별", "상세주소"],
            },
            {"raw_response_sha256": "sha256:anchor-classifier-response", "strict_json": True},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    result = actual_rag_eval.classify_query_focus_anchors_with_local_llm(
        "2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 무엇입니까?",
        backend="llamacpp",
        base_url="http://localhost:8081/v1",
        model="gemma4-e2b-local",
        timeout_seconds=7,
        skip_endpoint_check=True,
    )

    assert captured["prompt"]
    assert captured["timeout_seconds"] == 7
    assert result["enabled"] is True
    assert result["status"] == "classified_validated"
    assert result["model"] == "gemma4-e2b-local"
    assert result["prompt_version"] == "llm_query_anchor_classifier_v1"
    assert result["raw_payload_written"] is False
    assert set(result["required_anchor_before"]) == {
        "2012년",
        "3월",
        "기관별",
        "무엇입니까",
        "상세주소",
        "지정된",
        "해오름요양원",
    }
    assert set(result["required_anchor_after"]) == {
        "2012년",
        "3월",
        "기관별",
        "상세주소",
        "해오름요양원",
    }
    assert result["removed_intent_tokens"] == ["무엇입니까", "지정된"]
    assert result["protected_intent_tokens_restored"] == ["2012년"]


def test_agentic_xlsx_anchor_taxonomy_preserves_structural_anchors() -> None:
    records = actual_rag_eval.agentic_xlsx_query_anchor_taxonomy_tool(
        [
            "2020년",
            "2024년",
            "2월",
            "1월",
            "일산선",
            "수인선",
            "신논현",
            "신논현요양원",
            "청운노인요양원",
            "원달러",
            "1,234,567명",
            "15.2%",
            "승차총승객수",
            "기관별 상세주소",
            "금액",
            "비율",
            "인구",
            "낯선토큰",
        ]
    )
    by_token = {record.token: record for record in records}

    assert by_token["2020년"].category == "date_or_period"
    assert by_token["2024년"].category == "date_or_period"
    assert by_token["2월"].category == "date_or_period"
    assert by_token["1월"].category == "date_or_period"
    assert by_token["일산선"].category == "route_or_line"
    assert by_token["수인선"].category == "route_or_line"
    assert by_token["신논현"].category == "route_or_line"
    assert by_token["신논현요양원"].category == "organization_or_facility"
    assert by_token["청운노인요양원"].category == "organization_or_facility"
    assert by_token["원달러"].category == "numeric_or_unit"
    assert by_token["1,234,567명"].category == "numeric_or_unit"
    assert by_token["15.2%"].category == "numeric_or_unit"
    assert by_token["승차총승객수"].category == "measure_or_column"
    assert by_token["기관별 상세주소"].category == "measure_or_column"
    assert by_token["금액"].category == "measure_or_column"
    assert by_token["비율"].category == "measure_or_column"
    assert by_token["인구"].category == "measure_or_column"
    assert by_token["낯선토큰"].category == "unknown_protected"
    for record in by_token.values():
        assert record.is_protected_anchor is True
        assert record.is_removable_intent_token is False
        assert record.reason


def test_agentic_xlsx_anchor_taxonomy_drops_intent_only() -> None:
    records = actual_rag_eval.agentic_xlsx_query_anchor_taxonomy_tool(
        ["무엇입니까", "명입니까", "지정된", "알려주세요", "구하시오", "일산선", "확인되지않은토큰"]
    )
    by_token = {record.token: record for record in records}

    for token in ("무엇입니까", "명입니까", "지정된", "알려주세요", "구하시오"):
        assert by_token[token].category == "intent_token"
        assert by_token[token].is_removable_intent_token is True
        assert by_token[token].is_protected_anchor is False
    assert by_token["일산선"].category == "route_or_line"
    assert by_token["일산선"].is_removable_intent_token is False
    assert by_token["일산선"].is_protected_anchor is True
    assert by_token["확인되지않은토큰"].category == "unknown_protected"
    assert by_token["확인되지않은토큰"].is_protected_anchor is True
    assert by_token["확인되지않은토큰"].is_removable_intent_token is False


def test_agentic_xlsx_protected_anchor_verifier_rejects_llm_structural_removal() -> None:
    taxonomy = actual_rag_eval.agentic_xlsx_query_anchor_taxonomy_tool(
        ["무엇입니까", "일산선", "2024년", "신논현요양원", "원달러", "승차총승객수", "낯선토큰"]
    )

    verification = actual_rag_eval.agentic_xlsx_protected_anchor_verifier_tool(
        proposed_removed_tokens=["무엇입니까", "일산선", "2024년", "신논현요양원", "원달러", "승차총승객수", "낯선토큰"],
        taxonomy_records=taxonomy,
    )

    assert verification.approved_removed_tokens == ("무엇입니까",)
    assert verification.rejected_removed_tokens == (
        "일산선",
        "2024년",
        "신논현요양원",
        "원달러",
        "승차총승객수",
        "낯선토큰",
    )
    assert set(verification.protected_rejection_reasons) == {
        "일산선",
        "2024년",
        "신논현요양원",
        "원달러",
        "승차총승객수",
        "낯선토큰",
    }
    assert all(verification.protected_rejection_reasons[token] for token in verification.rejected_removed_tokens)


@pytest.mark.parametrize(
    ("record", "match"),
    [
        (
            actual_rag_eval.AgenticXlsxQueryAnchorTaxonomyRecord(
                token="일산선",
                category="station_line",
                is_removable_intent_token=False,
                is_protected_anchor=True,
                reason="unsupported category",
            ),
            "category unsupported",
        ),
        (
            actual_rag_eval.AgenticXlsxQueryAnchorTaxonomyRecord(
                token="무엇입니까",
                category="intent_token",
                is_removable_intent_token=True,
                is_protected_anchor=True,
                reason="intent tokens cannot be protected",
            ),
            "intent_token",
        ),
        (
            actual_rag_eval.AgenticXlsxQueryAnchorTaxonomyRecord(
                token="2020년",
                category="date_or_period",
                is_removable_intent_token=True,
                is_protected_anchor=True,
                reason="date cannot be removable",
            ),
            "only intent_token",
        ),
        (
            actual_rag_eval.AgenticXlsxQueryAnchorTaxonomyRecord(
                token="일산선",
                category="route_or_line",
                is_removable_intent_token=False,
                is_protected_anchor=False,
                reason="route must be protected",
            ),
            "non-intent",
        ),
        (
            actual_rag_eval.AgenticXlsxQueryAnchorTaxonomyRecord(
                token="",
                category="unknown_protected",
                is_removable_intent_token=False,
                is_protected_anchor=True,
                reason="empty token",
            ),
            "token must be non-empty",
        ),
        (
            actual_rag_eval.AgenticXlsxQueryAnchorTaxonomyRecord(
                token="낯선토큰",
                category="unknown_protected",
                is_removable_intent_token=False,
                is_protected_anchor=True,
                reason="",
            ),
            "reason must be non-empty",
        ),
    ],
)
def test_agentic_xlsx_tool_schema_validator_rejects_unknown_malformed_categories(
    record: object,
    match: str,
) -> None:
    with pytest.raises(DatasetSchemaError, match=match):
        actual_rag_eval.validate_agentic_xlsx_query_anchor_taxonomy_output("cp01", (record,))


def test_agentic_xlsx_repair_explainer_fails_closed_on_protected_removal() -> None:
    malformed_taxonomy = (
        actual_rag_eval.AgenticXlsxQueryAnchorTaxonomyRecord(
            token="일산선",
            category="route",
            is_removable_intent_token=False,
            is_protected_anchor=True,
            reason="malformed category should fail closed",
        ),
    )
    with pytest.raises(DatasetSchemaError, match="category unsupported"):
        actual_rag_eval.validate_agentic_xlsx_query_anchor_taxonomy_output("cp01", malformed_taxonomy)

    taxonomy = actual_rag_eval.agentic_xlsx_query_anchor_taxonomy_tool(["무엇입니까", "일산선"])
    verification = actual_rag_eval.agentic_xlsx_protected_anchor_verifier_tool(
        proposed_removed_tokens=["무엇입니까", "일산선"],
        taxonomy_records=taxonomy,
    )
    explanation = actual_rag_eval.AgenticXlsxRepairExplanationRecord(
        primary_failure_family="intent_anchor_only",
        secondary_failure_families=(),
        safe_to_simulate_intent_removal=True,
        repair_recommendation="diagnostic-only intent removal simulation",
        evidence_summary="LLM advisory proposed a protected route anchor removal.",
    )

    with pytest.raises(DatasetSchemaError, match="protected anchors were rejected"):
        actual_rag_eval.validate_agentic_xlsx_repair_explainer_output(
            "cp01",
            explanation,
            anchor_verification=verification,
        )


def test_agentic_xlsx_protected_anchor_verifier_fails_closed_without_taxonomy() -> None:
    unsafe_verification = actual_rag_eval.AgenticXlsxProtectedAnchorVerifierRecord(
        proposed_removed_tokens=("일산선",),
        approved_removed_tokens=("일산선",),
        rejected_removed_tokens=(),
        protected_rejection_reasons={},
    )

    with pytest.raises(DatasetSchemaError, match="approved_removed_tokens missing taxonomy"):
        actual_rag_eval.validate_agentic_xlsx_protected_anchor_verifier_output("cp01", unsafe_verification)

    coordinator = actual_rag_eval.AgenticXlsxCoordinatorRecord(
        taxonomy_records=(),
        anchor_verification=unsafe_verification,
    )
    with pytest.raises(DatasetSchemaError, match="approved_removed_tokens missing taxonomy"):
        actual_rag_eval.validate_agentic_xlsx_coordinator_output("cp01", coordinator)


def test_agentic_xlsx_regated_simulator_rejects_unapproved_removed_tokens() -> None:
    taxonomy = actual_rag_eval.agentic_xlsx_query_anchor_taxonomy_tool(["무엇입니까", "해오름요양원"])
    verification = actual_rag_eval.agentic_xlsx_protected_anchor_verifier_tool(
        proposed_removed_tokens=["무엇입니까", "해오름요양원"],
        taxonomy_records=taxonomy,
    )
    simulation = actual_rag_eval.AgenticXlsxRegatedCandidateSimulationRecord(
        original_rejection_reason="missing_query_anchor_after_tool",
        simulated_rejection_reason="accepted_after_regating",
        approved_removed_tokens=("무엇입니까", "해오름요양원"),
        protected_tokens_preserved=("해오름요양원",),
        axis_status_after_simulation={"missing_axes": []},
        would_be_accepted_by_existing_gate=True,
    )

    with pytest.raises(DatasetSchemaError, match="approved_removed_tokens must be verifier-approved"):
        actual_rag_eval.validate_agentic_xlsx_regated_candidate_simulator_output(
            "cp01",
            simulation,
            anchor_verification=verification,
        )


def test_agentic_xlsx_axis_inspector_rejects_nested_forbidden_evidence_fields() -> None:
    inspection = actual_rag_eval.AgenticXlsxAxisInspectionRecord(
        has_required_period_axis=True,
        has_required_entity_axis=True,
        has_required_measure_axis=True,
        has_display_value=True,
        missing_axes=(),
        source_owned_axis_evidence={
            "period": "2020년",
            "metadata": {"expected_answer": "protected oracle value"},
        },
    )

    with pytest.raises(DatasetSchemaError, match="expected_answer"):
        actual_rag_eval.validate_agentic_xlsx_axis_inspector_output("cp01", inspection)

    non_scalar = actual_rag_eval.AgenticXlsxAxisInspectionRecord(
        has_required_period_axis=True,
        has_required_entity_axis=True,
        has_required_measure_axis=True,
        has_display_value=True,
        missing_axes=(),
        source_owned_axis_evidence={"period": 2020},
    )
    with pytest.raises(DatasetSchemaError, match="source_owned_axis_evidence.period"):
        actual_rag_eval.validate_agentic_xlsx_axis_inspector_output("cp01", non_scalar)


@pytest.mark.parametrize(
    ("callable_validator", "match"),
    [
        (
            lambda: actual_rag_eval.validate_agentic_xlsx_query_anchor_taxonomy_output(
                "cp01",
                (
                    {
                        "schema_version": actual_rag_eval.AGENTIC_XLSX_QUERY_ANCHOR_TAXONOMY_SCHEMA_VERSION,
                        "token": 2020,
                        "category": "date_or_period",
                        "is_removable_intent_token": False,
                        "is_protected_anchor": True,
                        "reason": "numeric token should fail closed",
                    },
                ),
            ),
            "token must be a string",
        ),
        (
            lambda: actual_rag_eval.validate_agentic_xlsx_protected_anchor_verifier_output(
                "cp01",
                {
                    "schema_version": actual_rag_eval.AGENTIC_XLSX_PROTECTED_ANCHOR_VERIFIER_SCHEMA_VERSION,
                    "proposed_removed_tokens": [123],
                    "approved_removed_tokens": [],
                    "rejected_removed_tokens": ["123"],
                    "protected_rejection_reasons": {"123": "non-string proposed token"},
                },
            ),
            "proposed_removed_tokens must contain strings",
        ),
        (
            lambda: actual_rag_eval.validate_agentic_xlsx_regated_candidate_simulator_output(
                "cp01",
                {
                    "schema_version": actual_rag_eval.AGENTIC_XLSX_REGATED_CANDIDATE_SIMULATOR_SCHEMA_VERSION,
                    "original_rejection_reason": "missing_query_anchor_after_tool",
                    "simulated_rejection_reason": "missing_validated_required_axes_after_tool",
                    "approved_removed_tokens": [123],
                    "protected_tokens_preserved": [],
                    "axis_status_after_simulation": {},
                    "would_be_accepted_by_existing_gate": False,
                    "report_only_diagnostic": True,
                    "official_metric": False,
                },
            ),
            "approved_removed_tokens must contain strings",
        ),
    ],
)
def test_agentic_xlsx_validators_reject_non_string_tuple_payloads(
    callable_validator: object,
    match: str,
) -> None:
    with pytest.raises(DatasetSchemaError, match=match):
        callable_validator()


def test_llm_query_anchor_classifier_malformed_payload_falls_back_to_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return ({"intent_tokens": "not-a-list"}, {"raw_response_sha256": "sha256:bad"})

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    result = actual_rag_eval.classify_query_focus_anchors_with_local_llm(
        "2019년 2월 5호선 승차총승객수는 얼마야?",
        skip_endpoint_check=True,
    )

    assert result["status"] == "malformed_payload_deterministic_fallback"
    assert result["raw_payload_written"] is False
    assert result["required_anchor_before"] == result["required_anchor_after"]
    assert set(result["required_anchor_after"]) == {"2019년", "2월", "5호선", "승차총승객수", "얼마야"}


def test_llm_query_anchor_classifier_does_not_remove_entity_misclassified_as_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {
                "intent_tokens": ["해오름요양원", "무엇입니까"],
                "numeric_or_date_anchors": ["2012년", "3월"],
                "entity_anchors": [],
                "measure_anchors": ["기관별", "상세주소"],
            },
            {"raw_response_sha256": "sha256:entity-poison"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    result = actual_rag_eval.classify_query_focus_anchors_with_local_llm(
        "2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 무엇입니까?",
        skip_endpoint_check=True,
    )

    assert result["status"] == "classified_validated"
    assert "해오름요양원" in result["required_anchor_after"]
    assert result["removed_intent_tokens"] == ["무엇입니까"]
    assert result["protected_intent_tokens_restored"] == ["해오름요양원"]


def test_agentic_xlsx_classifier_verifier_preserves_diagnostic_structural_anchors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unsafe_tokens = [
        "일산선",
        "수인선",
        "신논현요양원",
        "청운노인요양원",
        "2020년",
        "2024년",
        "2월",
        "1월",
        "원달러",
    ]

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {
                "intent_tokens": ["무엇입니까", *unsafe_tokens],
                "numeric_or_date_anchors": [],
                "entity_anchors": [],
                "measure_anchors": [],
            },
            {"raw_response_sha256": "sha256:unsafe-agentic-xlsx-classifier"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    result = actual_rag_eval.classify_query_focus_anchors_with_local_llm(
        (
            "2020년 2월 일산선과 2024년 1월 수인선의 원달러 금액을 비교하고 "
            "신논현요양원 및 청운노인요양원 값은 무엇입니까?"
        ),
        skip_endpoint_check=True,
    )

    assert result["status"] == "classified_validated"
    assert result["removed_intent_tokens"] == ["무엇입니까"]
    assert set(unsafe_tokens).issubset(set(result["protected_intent_tokens_restored"]))
    assert set(unsafe_tokens).issubset(set(result["required_anchor_after"]))
    taxonomy = result["agentic_xlsx_anchor_taxonomy"]
    assert taxonomy["schema_version"] == "actual_rag_eval.agentic_xlsx_query_anchor_taxonomy.v1"
    assert taxonomy["category_counts"]["date_or_period"] >= 4
    assert taxonomy["category_counts"]["route_or_line"] >= 2
    assert taxonomy["category_counts"]["organization_or_facility"] >= 2
    assert taxonomy["category_counts"]["numeric_or_unit"] >= 1
    verifier = result["agentic_xlsx_protected_anchor_verifier"]
    assert verifier["schema_version"] == "actual_rag_eval.agentic_xlsx_protected_anchor_verifier.v1"
    assert verifier["approved_removed_tokens"] == ["무엇입니까"]
    assert set(unsafe_tokens).issubset(set(verifier["rejected_removed_tokens"]))
    assert all(verifier["protected_rejection_reasons"][token] for token in unsafe_tokens)
    assert result["raw_payload_written"] is False
    assert result["raw_prompt_payload_written"] is False
    assert result["raw_response_payload_written"] is False
    assert result["uses_gold_fields"] is False
    assert result["uses_expected_fields"] is False
    assert result["uses_qrels"] is False
    assert result["uses_labels"] is False
    assert result["uses_query_or_row_or_target_ids"] is False
    assert result["uses_baseline_topk_or_legacy_outputs"] is False
    encoded = json.dumps(result, ensure_ascii=False)
    for forbidden in ("expected_answer", "expected_evidence", "row_id", "candidate_id"):
        assert forbidden not in encoded


def test_agentic_xlsx_query_anchor_classifier_from_planner_preserves_protected_anchors() -> None:
    unsafe_tokens = [
        "일산선",
        "수인선",
        "신논현요양원",
        "청운노인요양원",
        "2020년",
        "2024년",
        "2월",
        "1월",
        "원달러",
    ]
    planner = {
        "planner_status": "planned_validated",
        "model": "local-test",
        "backend": "test",
        "base_url": "http://localhost",
        "raw_response_sha256": "sha256:planner-protected-anchors",
        "validated_axis_values": {},
    }

    result = actual_rag_eval._query_anchor_classifier_from_planner(
        (
            "2020년 2월 일산선과 2024년 1월 수인선의 원달러 금액을 비교하고 "
            "신논현요양원 및 청운노인요양원 값은 무엇입니까?"
        ),
        planner,
    )

    assert result["status"] == "classified_validated"
    assert result["removed_intent_tokens"] == ["무엇입니까"]
    assert set(unsafe_tokens).issubset(set(result["protected_intent_tokens_restored"]))
    assert set(unsafe_tokens).issubset(set(result["required_anchor_after"]))
    verifier = result["agentic_xlsx_protected_anchor_verifier"]
    assert verifier["approved_removed_tokens"] == ["무엇입니까"]
    assert set(unsafe_tokens).issubset(set(verifier["rejected_removed_tokens"]))


def test_query_evidence_planner_validates_structured_xlsx_axes_and_excludes_question_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**kwargs: object) -> tuple[dict, dict]:
        prompt = str(kwargs["prompt"])
        captured["prompt"] = prompt
        assert "source_family_hint" in prompt
        assert "query_task" in prompt
        assert "row_filters" in prompt
        assert "target_axis" in prompt
        assert "2019년 5월 우이신설선의 승차총승객수는 몇 명입니까?" in prompt
        for forbidden in ("expected_answer", "expected_evidence", "qrels", "row_id", "baseline_topk"):
            assert forbidden not in prompt
        return (
            {
                "source_family_hint": "xlsx",
                "query_task": "date_filtered_table_lookup",
                "row_filters": {"period": "201905", "line_name": "우이신설선"},
                "target_axis": {"column": "승차총승객수", "value_type": "number"},
                "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
                "intent_tokens": ["몇 명입니까"],
            },
            {"raw_response_sha256": "sha256:query-evidence-plan"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    result = actual_rag_eval.plan_query_evidence_with_local_llm(
        "2019년 5월 우이신설선의 승차총승객수는 몇 명입니까?",
        backend="llamacpp",
        base_url="http://localhost:8081/v1",
        model="gemma4-e2b-local",
        timeout_seconds=7,
        skip_endpoint_check=True,
    )

    assert captured["prompt"]
    assert result["enabled"] is True
    assert result["status"] == "planned_validated"
    assert result["planner_status"] == "planned_validated"
    assert result["prompt_version"] == "query_evidence_planner_v1"
    assert result["input_policy"] == "query_text_only_no_eval_fields_or_baseline"
    assert result["source_family_hint"] == "xlsx"
    assert result["query_task"] == "date_filtered_table_lookup"
    assert result["row_filters"] == {"line_name": "우이신설선", "period": "2019-05"}
    assert result["target_axis"] == {"column": "승차총승객수", "value_type": "number"}
    assert result["evidence_contract"] == ["period", "row_entity", "target_column", "display_value"]
    assert result["validated_required_axes"] == ["period", "row_entity", "target_column", "display_value"]
    assert result["validated_axis_values"]["period"] == ["2019-05", "2019년 5월", "201905"]
    assert result["validated_axis_values"]["row_entity"] == ["우이신설선"]
    assert result["validated_axis_values"]["target_column"] == ["승차총승객수"]
    assert result["intent_tokens"] == ["몇 명입니까"]
    assert "몇" not in result["validated_required_axes"]
    assert "명입니까" not in result["validated_required_axes"]
    assert result["raw_payload_written"] is False


def test_query_evidence_planner_rejects_extra_payload_keys_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {
                "source_family_hint": "xlsx",
                "query_task": "date_filtered_lookup",
                "row_filters": {"period": "201905", "line_name": "우이신설선"},
                "target_axis": {"column": "승차총승객수", "value_type": "number"},
                "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
                "intent_tokens": ["몇 명입니까"],
                "expected_answer": "1,234,567명",
            },
            {"raw_response_sha256": "sha256:query-evidence-extra-key"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    result = actual_rag_eval.plan_query_evidence_with_local_llm(
        "2019년 5월 우이신설선의 승차총승객수는 몇 명입니까?",
        skip_endpoint_check=True,
    )

    assert result["status"] == "malformed_payload_deterministic_fallback"
    assert result["raw_payload_written"] is False
    assert result["uses_expected_fields"] is False
    assert result["validated_required_axes"] == []


def test_query_evidence_planner_validates_pdf_locator_axes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {
                "source_family_hint": "pdf",
                "query_task": "cell_lookup",
                "row_filters": {
                    "page_number": "7",
                    "section_title": "연결 손익계산서",
                    "table_caption": "영업실적 표",
                },
                "target_axis": {"column": "영업이익", "value_type": "number"},
                "evidence_contract": [
                    "page_number",
                    "section_title",
                    "table_caption",
                    "target_column",
                    "display_value",
                    "bbox",
                ],
                "intent_tokens": ["얼마입니까"],
            },
            {"raw_response_sha256": "sha256:pdf-query-evidence-plan"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    result = actual_rag_eval.plan_query_evidence_with_local_llm(
        "7페이지 연결 손익계산서 영업실적 표의 영업이익은 얼마입니까?",
        skip_endpoint_check=True,
    )

    assert result["status"] == "planned_validated"
    assert result["source_family_hint"] == "pdf"
    assert result["query_task"] == "cell_lookup"
    assert result["row_filters"] == {
        "page_number": "7",
        "section_title": "연결 손익계산서",
        "table_caption": "영업실적 표",
    }
    assert result["target_axis"] == {"column": "영업이익", "value_type": "number"}
    assert result["evidence_contract"] == [
        "page_number",
        "section_title",
        "table_caption",
        "target_column",
        "display_value",
        "bbox",
    ]
    assert result["validated_required_axes"] == [
        "page_number",
        "section_title",
        "table_caption",
        "target_column",
        "display_value",
        "bbox",
    ]
    assert result["validated_axis_values"]["page_number"] == ["7", "7페이지", "page 7", "p. 7"]
    assert result["validated_axis_values"]["section_title"] == ["연결 손익계산서"]
    assert result["validated_axis_values"]["table_caption"] == ["영업실적 표"]
    assert result["validated_axis_values"]["target_column"] == ["영업이익"]


def test_query_evidence_planner_adds_task_required_display_axis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {
                "source_family_hint": "xlsx",
                "query_task": "date_filtered_table_lookup",
                "row_filters": {"period": "201905", "line_name": "우이신설선"},
                "target_axis": {"column": "승차총승객수", "value_type": "number"},
                "evidence_contract": ["period", "row_entity", "target_column"],
                "intent_tokens": ["몇 명입니까"],
            },
            {"raw_response_sha256": "sha256:query-evidence-task-required-axis"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    result = actual_rag_eval.plan_query_evidence_with_local_llm(
        "2019년 5월 우이신설선의 승차총승객수는 몇 명입니까?",
        skip_endpoint_check=True,
    )

    assert result["status"] == "planned_validated"
    assert result["query_task"] == "date_filtered_table_lookup"
    assert result["evidence_contract"] == ["period", "row_entity", "target_column", "display_value"]
    assert result["validated_required_axes"] == ["period", "row_entity", "target_column", "display_value"]


def test_evidence_gate_satisfies_pdf_locator_presence_axes_from_metadata() -> None:
    query = "7페이지 연결 손익계산서 영업실적 표의 영업이익은 얼마입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "pdf",
            "query_task": "cell_lookup",
            "row_filters": {
                "page_number": "7",
                "section_title": "연결 손익계산서",
                "table_caption": "영업실적 표",
            },
            "target_axis": {"column": "영업이익", "value_type": "number"},
            "evidence_contract": [
                "page_number",
                "section_title",
                "table_caption",
                "target_column",
                "display_value",
                "bbox",
            ],
            "intent_tokens": ["얼마입니까"],
            "validated_required_axes": [
                "page_number",
                "section_title",
                "table_caption",
                "target_column",
                "display_value",
                "bbox",
            ],
            "validated_axis_values": {
                "page_number": ["7"],
                "section_title": ["연결 손익계산서"],
                "table_caption": ["영업실적 표"],
                "target_column": ["영업이익"],
                "display_value": [],
                "bbox": [],
            },
        },
    )
    row = {
        "id": "gate_pdf_locator_presence_axes",
        "query": query,
        "generated_answer": "123억원",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-pdf-locator-axis",
                "chunk_id": "chunk-pdf-locator-axis",
                "source_atom_id": "src-pdf-locator-axis",
                "evidence_bundle_id": "bundle-pdf-locator-axis",
                "source_family": "PDF",
                "granularity": "page_block",
                "text": "연결 손익계산서 영업실적 표 영업이익은 123억원입니다.",
                "page_number": "7",
                "section_title": "연결 손익계산서",
                "table_caption": "영업실적 표",
                "bbox": "[72,260,510,318]",
            }
        ],
        "citations": [],
    }

    validation = validate_evidence_package_for_gate(row)

    assert validation["evidence_package_status"] == "sufficient"
    assert validation["matched_validated_required_axes"] == [
        "page_number",
        "section_title",
        "table_caption",
        "target_column",
        "display_value",
        "bbox",
    ]
    assert validation["missing_validated_required_axes"] == []


def test_run_eval_provides_query_evidence_planner_to_retrieval_adapter_before_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = tmp_path / "pre_retrieval_query_evidence_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "pre_retrieval_query_evidence"
    write_jsonl(
        dataset,
        [
            {
                "id": "pre_retrieval_query_evidence_q",
                "query": "해오름요양원의 기관별 상세주소는 무엇입니까?",
                "answerability": "answerable",
                "expected_answer": "대구광역시 수성구 파동로51길 96",
            }
        ],
    )

    class PlannerAwareAdapter:
        requested_backend = "hybrid"

        def __init__(self) -> None:
            self.seen_planners: list[dict[str, object]] = []

        @property
        def config(self) -> dict[str, object]:
            return {
                "adapter": "planner_aware_adapter",
                "candidate_generation_input_policy": "query_text_and_query_evidence_planner_only",
            }

        @property
        def retrieval_backend_report(self) -> dict[str, object]:
            return {
                "requested": self.requested_backend,
                "selected": "hybrid",
                "bm25_enabled": True,
                "vector_enabled": False,
                "hybrid_enabled": True,
                "embedding_model": "none",
                "embedding_device": "none",
                "gpu_used_for_embedding": False,
                "vector_index_kind": "none",
                "vector_index_type": "none",
                "vector_dim": 0,
                "indexed_unit_count": 1,
                "query_count": len(self.seen_planners),
                "fallback_reason": "",
            }

        def run_item(self, item: object, *, top_k: int) -> dict[str, object]:
            source_row = getattr(item, "source_row", {})
            planner = source_row.get("query_evidence_planner") if isinstance(source_row, dict) else {}
            self.seen_planners.append(dict(planner) if isinstance(planner, dict) else {})
            return {
                "id": str(getattr(item, "id", "")),
                "query": str(getattr(item, "query", "")),
                "answerability": "answerable",
                "generated_answer": "대구광역시 수성구 파동로51길 96",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-pre-retrieval-planner",
                        "chunk_id": "chunk-pre-retrieval-planner",
                        "source_atom_id": "src-pre-retrieval-planner",
                        "evidence_bundle_id": "bundle-pre-retrieval-planner",
                        "source_family": "TEXT",
                        "granularity": "paragraph",
                        "text": "해오름요양원의 기관별 상세주소는 대구광역시 수성구 파동로51길 96입니다.",
                    }
                ][:top_k],
                "citations": [],
                "diagnostics": {},
            }

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {
                "source_family_hint": "text",
                "query_task": "entity_attribute_lookup",
                "row_filters": {"facility_name": "해오름요양원"},
                "target_axis": {"column": "기관별 상세주소", "value_type": "text"},
                "evidence_contract": ["row_entity", "target_column", "display_value"],
                "intent_tokens": ["무엇입니까"],
            },
            {"raw_response_sha256": "sha256:pre-retrieval-query-evidence"},
        )

    adapter = PlannerAwareAdapter()
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        retrieval_adapter=adapter,
        top_k=1,
        run_id="pre_retrieval_query_evidence",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        answer_composer="extractive-v1",
        resolve_expected_evidence=False,
        llm_query_anchor_classifier=True,
        skip_local_llm_composer_endpoint_check=True,
    )

    assert adapter.seen_planners
    assert adapter.seen_planners[0]["planner_status"] == "planned_validated"
    assert adapter.seen_planners[0]["source_family_hint"] == "text"
    assert adapter.seen_planners[0]["query_task"] == "entity_attribute_lookup"


def test_xlsx_locator_uses_validated_required_axes_instead_of_question_anchor_words(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = tmp_path / "xlsx_locator_query_evidence_planner_gold.jsonl"
    context = tmp_path / "xlsx_locator_query_evidence_planner_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_locator_query_evidence_planner"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx_locator_query_evidence_planner_q",
                "query": "2019년 5월 우이신설선의 승차총승객수는 몇 명입니까?",
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "xlsx_locator_query_evidence_planner_q",
                "generated_answer": "1,234,567명",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-xlsx-query-evidence-planner",
                        "chunk_id": "chunk-query-evidence-planner",
                        "source_atom_id": "src-xlsx-query-evidence-planner",
                        "evidence_bundle_id": "bundle-xlsx-query-evidence-planner",
                        "source_family": "XLSX",
                        "granularity": "table_row",
                        "text": "1,234,567명",
                        "xlsx_locator_text": "2019년 5월 우이신설선 승차총승객수 1,234,567명",
                        "xlsx_locator_metadata": {
                            "sheet": "2019년 5월",
                            "cell_range": "A17:J17",
                            "cell": "F17",
                            "row_index_1based": "17",
                            "row_label": "우이신설선",
                            "column_label": "승차총승객수",
                            "target_column": "승차총승객수",
                            "header_path": "승하차 > 승차총승객수",
                            "table_id": "sheet-201905-main-table",
                            "display_value": "1,234,567명",
                        },
                    }
                ],
                "citations": [],
            }
        ],
    )

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {
                "source_family_hint": "xlsx",
                "query_task": "date_filtered_table_lookup",
                "row_filters": {"period": "201905", "line_name": "우이신설선"},
                "target_axis": {"column": "승차총승객수", "value_type": "number"},
                "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
                "intent_tokens": ["몇 명입니까"],
            },
            {"raw_response_sha256": "sha256:query-evidence-run"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="xlsx_locator_query_evidence_planner",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        xlsx_locator_tool_execute_once=True,
        llm_query_anchor_classifier=True,
        local_llm_composer_model="gemma4-e2b-local",
        skip_local_llm_composer_endpoint_check=True,
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    planner = row["query_evidence_planner"]
    tool_use = row["xlsx_locator_tool_use"]

    assert report["evidence_gate"]["allowed_answer_count"] == 1
    assert planner["query_task"] == "date_filtered_table_lookup"
    assert planner["source_family_hint"] == "xlsx"
    assert planner["row_filters"] == {"line_name": "우이신설선", "period": "2019-05"}
    assert planner["target_axis"] == {"column": "승차총승객수", "value_type": "number"}
    assert planner["validated_required_axes"] == ["period", "row_entity", "target_column", "display_value"]
    assert tool_use["execution_status"] == "accepted_after_regating"
    assert tool_use["matched_validated_required_axes"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert tool_use["remaining_missing_validated_required_axes"] == []
    assert "몇" not in tool_use["remaining_missing_query_anchors"]
    assert "명입니까" not in tool_use["remaining_missing_query_anchors"]

    selected = row["evidence_gate"]["selected_evidence"][0]
    assert selected["row_label"] == "우이신설선"
    assert selected["target_column"] == "승차총승객수"
    assert selected["display_value"] == "1,234,567명"

    with sqlite3.connect(output_dir / "run.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        item = conn.execute(
            "SELECT source_family_hint, query_task, planner_status, row_filters_json, "
            "target_axis_json, validated_required_axes_json FROM items"
        ).fetchone()
        assert item["source_family_hint"] == "xlsx"
        assert item["query_task"] == "date_filtered_table_lookup"
        assert item["planner_status"] == "planned_validated"
        assert json.loads(item["row_filters_json"]) == {"line_name": "우이신설선", "period": "2019-05"}
        assert json.loads(item["target_axis_json"]) == {"column": "승차총승객수", "value_type": "number"}
        assert json.loads(item["validated_required_axes_json"]) == [
            "period",
            "row_entity",
            "target_column",
            "display_value",
        ]
        candidate = conn.execute(
            "SELECT matched_validated_required_axes_json, missing_validated_required_axes_json "
            "FROM tool_candidates"
        ).fetchone()
        assert json.loads(candidate["matched_validated_required_axes_json"]) == [
            "period",
            "row_entity",
            "target_column",
            "display_value",
        ]
        assert json.loads(candidate["missing_validated_required_axes_json"]) == []


def test_xlsx_locator_candidate_budget_uses_source_owned_candidate_diversification() -> None:
    query = "2019년 2월 5호선 승차총승객수는 얼마야?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"line_name": "5호선", "period": "2019-02"},
            "target_axis": {"column": "승차총승객수", "value_type": "number"},
            "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2019-02", "2019년 2월"],
                "row_entity": ["5호선"],
                "target_column": ["승차총승객수"],
                "display_value": [],
            },
        },
    )
    contexts = []
    for index in range(7):
        contexts.append(
            {
                "doc_id": f"doc-{index}",
                "chunk_id": f"chunk-{index}",
                "source_atom_id": f"src-{index}",
                "evidence_bundle_id": f"bundle-{index}",
                "source_family": "XLSX",
                "granularity": "table_row",
                "text": "2019년 2월 5호선 승차총승객수 값은 15,446,522명입니다.",
                "sheet": f"2019년 {2 + (index % 3)}월",
                "cell_range": f"A{1 + index}:D{7 + index}",
                "row_label": "5호선",
                "column_label": "승차총승객수",
                "target_column": "승차총승객수",
                "table_id": f"table-{index % 4}",
                "display_value": "15,446,522",
            }
        )
    contexts[0]["formula"] = "SECRET_FORMULA_NEVER_USED"
    row = {
        "id": "xlsx-budget-diversity",
        "query": query,
        "generated_answer": "15,446,522명",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": contexts,
    }

    candidates = actual_rag_eval._xlsx_locator_tool_candidates(row)

    assert len(candidates) == actual_rag_eval.XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET
    assert all(candidate["candidate_budget_per_query"] == actual_rag_eval.XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET for candidate in candidates)
    assert all(candidate["candidate_pool_count_before_budget"] == 7 for candidate in candidates)
    assert all(candidate["candidate_budget_exhausted"] is True for candidate in candidates)
    assert all(candidate["source_owned_candidate_diversification"] is True for candidate in candidates)
    assert len({candidate["source_owned_diversification_key"] for candidate in candidates}) == len(candidates)
    assert sum(1 for candidate in candidates if candidate["same_sheet_candidate"]) >= 1
    assert sum(1 for candidate in candidates if candidate["same_table_candidate"]) >= 1
    assert sum(1 for candidate in candidates if candidate["same_range_candidate"]) >= 1
    encoded = json.dumps(candidates, ensure_ascii=False)
    assert "SECRET_FORMULA_NEVER_USED" not in encoded


def test_xlsx_locator_candidate_budget_exact_budget_is_not_exhausted() -> None:
    budget = actual_rag_eval.XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET
    ordered_candidates = [
        {
            "doc_id": f"doc-{index}",
            "chunk_id": f"chunk-{index}",
            "source_atom_id": f"src-{index}",
            "evidence_bundle_id": f"bundle-{index}",
            "source_family": "XLSX",
            "sheet": f"2019년 {index + 1}월",
            "cell_range": f"A{index}:D{index + 3}",
            "table_id": f"table-{index}",
            "target_column": "승차총승객수",
            "text": "2019년 2월 5호선 승차총승객수 값은 15,446,522명입니다.",
        }
        for index in range(budget)
    ]

    candidates = actual_rag_eval._select_xlsx_locator_budgeted_candidates(
        ordered_candidates,
        dedupe_removed_count=0,
    )
    meta = actual_rag_eval._xlsx_locator_tool_use_meta(
        status="skipped_missing_source_locator",
        candidates=candidates,
    )
    projection = actual_rag_eval.project_xlsx_locator_run_record(
        actual_rag_eval.XlsxLocatorRunRecord(
            schema_version=actual_rag_eval.XLSX_LOCATOR_TOOL_EXECUTE_ONCE_SCHEMA_VERSION,
            enabled=True,
            report_only_diagnostic=True,
            official_metric=False,
            tool_name=actual_rag_eval.XLSX_LOCATOR_TOOL_NAME,
            eligible_failed_row_count=1,
            tool_invocation_count=1,
            accepted_candidate_count=0,
            rejected_candidate_count=budget,
            gate_delta_record=actual_rag_eval.XlsxLocatorGateDeltaRecord(),
            guardrail_record=actual_rag_eval.XlsxLocatorGuardrailRecord(),
            tool_uses=(
                actual_rag_eval.XlsxLocatorToolUseRecord(
                    item_index=0,
                    item_id="exact-budget",
                    execution_status="skipped_missing_source_locator",
                    candidate_count=budget,
                    accepted_candidate_count=0,
                    candidate_pool_count_before_budget=budget,
                ),
            ),
        )
    )

    assert len(candidates) == budget
    assert all(candidate["candidate_pool_count_before_budget"] == budget for candidate in candidates)
    assert all(candidate["candidate_budget_exhausted"] is False for candidate in candidates)
    assert meta["candidate_pool_count_before_budget"] == budget
    assert meta["candidate_budget_exhausted"] is False
    assert projection["at_budget_row_count"] == 1
    assert projection["candidate_budget_exhaustion_count"] == 0


def test_xlsx_locator_tool_use_marks_split_validated_axes_without_accepting_candidate() -> None:
    candidates = [
        {
            "source_family": "XLSX",
            "doc_id": "doc-xlsx-split-axis",
            "source_atom_id": "src-xlsx-split-axis-value",
            "text": "row_label=해뜨는요양원2 | target_column=시도 시군구 법정동명 | display_value=대구광역시 북구 복현동",
            "sheet": "일반현황",
            "cell_range": "A752:J801",
            "row_label": "해뜨는요양원2",
            "target_column": "시도 시군구 법정동명",
            "display_value": "대구광역시 북구 복현동",
            "matched_validated_required_axes": ["row_entity", "target_column", "display_value"],
            "missing_validated_required_axes": ["period"],
            "accepted_for_regating": False,
            "rejection_reason": "missing_validated_required_axes_after_tool",
        },
        {
            "source_family": "XLSX",
            "doc_id": "doc-xlsx-split-axis",
            "source_atom_id": "src-xlsx-split-axis-period",
            "text": "2014년 12월 해뜨는요양원2 일반현황",
            "sheet": "일반현황",
            "cell_range": "A752:J801",
            "matched_validated_required_axes": ["period", "row_entity"],
            "missing_validated_required_axes": ["target_column", "display_value"],
            "accepted_for_regating": False,
            "rejection_reason": "missing_validated_required_axes_after_tool",
        },
    ]

    meta = actual_rag_eval._xlsx_locator_tool_use_meta(
        status="skipped_missing_source_locator",
        candidates=candidates,
    )

    assert meta["accepted_candidate_count"] == 0
    assert meta["matched_validated_required_axes"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert meta["remaining_missing_validated_required_axes"] == []
    assert meta["complete_validated_axis_candidate_count"] == 0
    assert meta["validated_axis_split_across_candidates"] is True
    assert meta["best_candidate_missing_validated_required_axes"] == ["period"]
    assert meta["source_row_context_candidate_count"] == 0
    assert meta["source_row_context_doc_identity_mismatch_candidate_count"] == 0
    assert meta["source_row_context_blocked_by_doc_identity_mismatch"] is False


def test_xlsx_locator_tool_use_reports_source_row_context_doc_mismatch_fail_closed() -> None:
    candidates = [
        {
            "source_family": "XLSX",
            "doc_id": "doc-cell",
            "source_atom_id": "src-cell",
            "text": "row_label=해뜨는요양원2 | target_column=시도 시군구 법정동명 | display_value=대구광역시 북구 복현동",
            "sheet": "일반현황",
            "cell_range": "A752:J801",
            "row_label": "해뜨는요양원2",
            "target_column": "시도 시군구 법정동명",
            "display_value": "대구광역시 북구 복현동",
            "matched_validated_required_axes": ["row_entity", "target_column", "display_value"],
            "missing_validated_required_axes": ["period"],
            "accepted_for_regating": False,
            "rejection_reason": "missing_validated_required_axes_after_tool",
        },
        {
            "source_family": "XLSX",
            "doc_id": "doc-row",
            "source_atom_id": "src-row",
            "text": "2014년 12월 해뜨는요양원2 일반현황",
            "sheet": "일반현황",
            "cell_range": "A752:J801",
            "matched_validated_required_axes": ["period", "row_entity"],
            "missing_validated_required_axes": ["target_column", "display_value"],
            "accepted_for_regating": False,
            "rejection_reason": "missing_validated_required_axes_after_tool",
        },
    ]

    meta = actual_rag_eval._xlsx_locator_tool_use_meta(
        status="skipped_missing_source_locator",
        candidates=candidates,
    )
    tool_use = actual_rag_eval._xlsx_locator_tool_use_record(
        item_index=0,
        item_id="xlsx-doc-mismatch",
        meta=meta,
    )
    projection = actual_rag_eval.project_xlsx_locator_run_record(
        actual_rag_eval.XlsxLocatorRunRecord(
            schema_version=actual_rag_eval.XLSX_LOCATOR_TOOL_EXECUTE_ONCE_SCHEMA_VERSION,
            enabled=True,
            report_only_diagnostic=True,
            official_metric=False,
            tool_name=actual_rag_eval.XLSX_LOCATOR_TOOL_NAME,
            eligible_failed_row_count=1,
            tool_invocation_count=1,
            accepted_candidate_count=0,
            rejected_candidate_count=len(candidates),
            gate_delta_record=actual_rag_eval.XlsxLocatorGateDeltaRecord(),
            guardrail_record=actual_rag_eval.XlsxLocatorGuardrailRecord(),
            tool_uses=(tool_use,),
        )
    )

    assert meta["validated_axis_split_across_candidates"] is True
    assert meta["source_row_context_candidate_count"] == 0
    assert meta["source_row_context_doc_identity_mismatch_candidate_count"] == 1
    assert meta["source_row_context_blocked_by_doc_identity_mismatch"] is True
    assert (
        meta["source_row_context_fail_closed_policy"]
        == "requires_same_doc_sheet_range_row_index_for_sibling_row_context"
    )
    assert tool_use.source_row_context_doc_identity_mismatch_candidate_count == 1
    assert tool_use.source_row_context_blocked_by_doc_identity_mismatch is True
    assert projection["source_row_context_doc_identity_mismatch_candidate_count"] == 1
    assert projection["source_row_context_doc_identity_mismatch_row_count"] == 1
    assert candidates[0]["source_row_context_source_atom_id"] == "src-row"
    assert candidates[0]["source_row_context_doc_id"] == "doc-row"


def test_xlsx_locator_builds_source_owned_sibling_row_composite_for_split_axes() -> None:
    query = "2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"line_name": "해뜨는요양원2", "period": "2014-12"},
            "target_axis": {"column": "시도 시군구 법정동명", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2014-12", "2014년 12월", "201412"],
                "row_entity": ["해뜨는요양원2"],
                "target_column": ["시도 시군구 법정동명"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "xlsx-split-axis-composite",
        "query": query,
        "generated_answer": "대구광역시 북구 복현동",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-cell",
                "chunk_id": "chunk-cell",
                "source_atom_id": "src-cell",
                "source_family": "XLSX",
                "granularity": "cell",
                "text": (
                    "sheet=일반현황 | range=A752:J801 | cell=G752 | "
                    "row_label=장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526 | "
                    "column_label=시도 시군구 법정동명 | target_column=시도 시군구 법정동명 | "
                    "value=국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 G752 | "
                    "시도 시군구 법정동명=대구광역시 북구 복현동"
                ),
                "title": "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx",
                "workbook_id": "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx",
                "workbook_version_id": "docv-forbidden-workbook-version",
                "sheet": "일반현황",
                "cell_range": "A752:J801",
                "cell": "G752",
                "row_index_1based": "752",
                "row_label": "장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526",
                "column_label": "시도 시군구 법정동명",
                "target_column": "시도 시군구 법정동명",
            },
            {
                "doc_id": "doc-cell",
                "chunk_id": "chunk-row",
                "source_atom_id": "src-row",
                "source_family": "XLSX",
                "granularity": "table_row",
                "text": (
                    "sheet=일반현황 | range=A752:J801 | "
                    "해뜨는요양원2 | 41526 | 27 | 230 | 112 | 대구광역시 북구 복현동 | "
                    "2014-12-31 | 2014-12-31 | 대구광역시 북구 공항로 10-7 (복현동)"
                ),
                "sheet": "일반현황",
                "cell_range": "A752:J801",
                "row_index_1based": "752",
            },
        ],
    }

    candidates = actual_rag_eval._xlsx_locator_tool_candidates(row)

    accepted = [candidate for candidate in candidates if candidate["accepted_for_regating"] is True]
    assert len(accepted) == 1
    candidate = accepted[0]
    assert candidate["locator_text_source"] == "source_owned_sibling_row_context"
    assert candidate["source_atom_id"] == "src-cell"
    assert candidate["source_row_context_source_atom_id"] == "src-row"
    assert candidate["source_row_context_doc_id"] == "doc-cell"
    assert candidate["display_value"] == "대구광역시 북구 복현동"
    assert candidate["target_column"] == "시도 시군구 법정동명"
    assert candidate["matched_validated_required_axes"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert candidate["missing_validated_required_axes"] == []
    assert "source_row_context_source_atom_id" in candidate["input_fields_used"]
    encoded = json.dumps(candidate, ensure_ascii=False)
    for forbidden in (
        "workbook_id",
        "workbook_version_id",
        "title",
        "file_name",
        "expected_answer",
        "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx",
    ):
        assert forbidden not in encoded


def test_xlsx_locator_sibling_row_composite_rejects_ambiguous_sibling_contexts() -> None:
    query = "2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"line_name": "해뜨는요양원2", "period": "2014-12"},
            "target_axis": {"column": "시도 시군구 법정동명", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2014-12", "2014년 12월", "201412"],
                "row_entity": ["해뜨는요양원2"],
                "target_column": ["시도 시군구 법정동명"],
                "display_value": [],
            },
        },
    )
    sibling_text = (
        "sheet=일반현황 | range=A752:J801 | "
        "해뜨는요양원2 | 41526 | 27 | 230 | 112 | 대구광역시 북구 복현동 | "
        "2014-12-31 | 2014-12-31 | 대구광역시 북구 공항로 10-7 (복현동)"
    )
    row = {
        "id": "xlsx-split-axis-composite-ambiguous",
        "query": query,
        "generated_answer": "대구광역시 북구 복현동",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-cell",
                "source_atom_id": "src-cell",
                "source_family": "XLSX",
                "granularity": "cell",
                "text": (
                    "sheet=일반현황 | range=A752:J801 | cell=G752 | "
                    "row_label=장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526 | "
                    "column_label=시도 시군구 법정동명 | target_column=시도 시군구 법정동명 | "
                    "시도 시군구 법정동명=대구광역시 북구 복현동"
                ),
                "sheet": "일반현황",
                "cell_range": "A752:J801",
                "cell": "G752",
                "row_index_1based": "752",
                "row_label": "장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526",
                "column_label": "시도 시군구 법정동명",
                "target_column": "시도 시군구 법정동명",
            },
            {
                "doc_id": "doc-cell",
                "source_atom_id": "src-row-a",
                "source_family": "XLSX",
                "granularity": "table_row",
                "text": sibling_text,
                "sheet": "일반현황",
                "cell_range": "A752:J801",
            },
            {
                "doc_id": "doc-cell",
                "source_atom_id": "src-row-b",
                "source_family": "XLSX",
                "granularity": "table_row",
                "text": sibling_text,
                "sheet": "일반현황",
                "cell_range": "A752:J801",
            },
        ],
    }

    candidates = actual_rag_eval._xlsx_locator_tool_candidates(row)

    assert all(candidate["accepted_for_regating"] is False for candidate in candidates)


def test_xlsx_locator_sibling_row_composite_rejects_source_document_mismatch() -> None:
    query = "2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"line_name": "해뜨는요양원2", "period": "2014-12"},
            "target_axis": {"column": "시도 시군구 법정동명", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2014-12", "2014년 12월", "201412"],
                "row_entity": ["해뜨는요양원2"],
                "target_column": ["시도 시군구 법정동명"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "xlsx-split-axis-composite-doc-mismatch",
        "query": query,
        "generated_answer": "대구광역시 북구 복현동",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-cell",
                "source_atom_id": "src-cell",
                "source_family": "XLSX",
                "granularity": "cell",
                "text": (
                    "sheet=일반현황 | range=A752:J801 | cell=G752 | "
                    "row_label=장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526 | "
                    "column_label=시도 시군구 법정동명 | target_column=시도 시군구 법정동명 | "
                    "시도 시군구 법정동명=대구광역시 북구 복현동"
                ),
                "sheet": "일반현황",
                "cell_range": "A752:J801",
                "cell": "G752",
                "row_index_1based": "752",
                "row_label": "장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526",
                "column_label": "시도 시군구 법정동명",
                "target_column": "시도 시군구 법정동명",
            },
            {
                "doc_id": "doc-row-other",
                "source_atom_id": "src-row",
                "source_family": "XLSX",
                "granularity": "table_row",
                "text": (
                    "sheet=일반현황 | range=A752:J801 | "
                    "해뜨는요양원2 | 41526 | 27 | 230 | 112 | 대구광역시 북구 복현동 | "
                    "2014-12-31 | 2014-12-31 | 대구광역시 북구 공항로 10-7 (복현동)"
                ),
                "sheet": "일반현황",
                "cell_range": "A752:J801",
                "row_index_1based": "752",
            },
        ],
    }

    candidates = actual_rag_eval._xlsx_locator_tool_candidates(row)

    assert all(candidate["accepted_for_regating"] is False for candidate in candidates)


def test_xlsx_locator_sibling_row_composite_requires_display_value_in_sibling_context() -> None:
    query = "2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"line_name": "해뜨는요양원2", "period": "2014-12"},
            "target_axis": {"column": "시도 시군구 법정동명", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2014-12", "2014년 12월", "201412"],
                "row_entity": ["해뜨는요양원2"],
                "target_column": ["시도 시군구 법정동명"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "xlsx-split-axis-composite-negative",
        "query": query,
        "generated_answer": "대구광역시 북구 복현동",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-cell",
                "source_atom_id": "src-cell",
                "source_family": "XLSX",
                "granularity": "cell",
                "text": (
                    "sheet=일반현황 | range=A752:J801 | cell=G752 | "
                    "row_label=장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526 | "
                    "column_label=시도 시군구 법정동명 | target_column=시도 시군구 법정동명 | "
                    "시도 시군구 법정동명=대구광역시 북구 복현동"
                ),
                "sheet": "일반현황",
                "cell_range": "A752:J801",
                "cell": "G752",
                "row_index_1based": "752",
                "row_label": "장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526",
                "column_label": "시도 시군구 법정동명",
                "target_column": "시도 시군구 법정동명",
            },
            {
                "doc_id": "doc-cell",
                "source_atom_id": "src-row",
                "source_family": "XLSX",
                "granularity": "table_row",
                "text": (
                    "sheet=일반현황 | range=A752:J801 | "
                    "해뜨는요양원2 | 41526 | 27 | 230 | 112 | "
                    "2014-12-31 | 2014-12-31 | 대구광역시 북구 공항로 10-7 (복현동)"
                ),
                "sheet": "일반현황",
                "cell_range": "A752:J801",
            },
        ],
    }

    candidates = actual_rag_eval._xlsx_locator_tool_candidates(row)

    assert all(candidate["accepted_for_regating"] is False for candidate in candidates)
    meta = actual_rag_eval._xlsx_locator_tool_use_meta(
        status="skipped_missing_source_locator",
        candidates=candidates,
    )
    assert meta["validated_axis_split_across_candidates"] is True
    assert meta["complete_validated_axis_candidate_count"] == 0


def test_xlsx_locator_sibling_row_composite_accepts_same_source_row_period_cell() -> None:
    query = "2015년 6월에 지정된 부여효요양원의 기관별 상세주소는 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"line_name": "부여효요양원", "period": "2015-06"},
            "target_axis": {"column": "기관별 상세주소", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2015-06", "2015년 6월", "201506"],
                "row_entity": ["부여효요양원"],
                "target_column": ["기관별 상세주소"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "xlsx-same-row-period-cell-composite",
        "query": query,
        "generated_answer": "충청남도 부여군 석성면 왕릉로 773",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-care",
                "chunk_id": "chunk-address",
                "source_atom_id": "src-address",
                "source_family": "XLSX",
                "granularity": "cell",
                "text": (
                    "sheet=일반현황 | range=A5002:J5051 | cell=J5002 | "
                    "row_label=장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176 | "
                    "column_label=기관별 상세주소 | target_column=기관별 상세주소 | "
                    "기관별 상세주소=충청남도 부여군 석성면 왕릉로 773"
                ),
                "sheet": "일반현황",
                "cell_range": "A5002:J5051",
                "cell": "J5002",
                "row_index_1based": "5002",
                "row_label": "장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176",
                "column_label": "기관별 상세주소",
                "target_column": "기관별 상세주소",
            },
            {
                "doc_id": "doc-care",
                "chunk_id": "chunk-date",
                "source_atom_id": "src-date",
                "source_family": "XLSX",
                "granularity": "cell",
                "text": (
                    "sheet=일반현황 | range=A5002:J5051 | cell=H5002 | "
                    "row_label=장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176 | "
                    "column_label=지정일자 | target_column=지정일자 | 지정일자=2015-06-01"
                ),
                "sheet": "일반현황",
                "cell_range": "A5002:J5051",
                "cell": "H5002",
                "row_index_1based": "5002",
                "row_label": "장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176",
                "column_label": "지정일자",
                "target_column": "지정일자",
            },
        ],
    }

    candidates = actual_rag_eval._xlsx_locator_tool_candidates(row)

    accepted = [candidate for candidate in candidates if candidate["accepted_for_regating"] is True]
    assert len(accepted) == 1
    candidate = accepted[0]
    assert candidate["locator_text_source"] == "source_owned_sibling_row_context"
    assert candidate["source_atom_id"] == "src-address"
    assert candidate["source_row_context_source_atom_id"] == "src-date"
    assert candidate["source_row_context_doc_id"] == "doc-care"
    assert candidate["display_value"] == "충청남도 부여군 석성면 왕릉로 773"
    assert candidate["matched_validated_required_axes"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert candidate["missing_validated_required_axes"] == []
    encoded = json.dumps(candidate, ensure_ascii=False)
    for forbidden in (
        "workbook_id",
        "workbook_version_id",
        "title",
        "file_name",
        "expected_answer",
    ):
        assert forbidden not in encoded


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sheet", "다른시트"),
        ("cell_range", "A2:J51"),
        ("row_index_1based", "2"),
        ("row_index_1based", ""),
    ],
)
def test_xlsx_locator_sibling_row_composite_rejects_period_cell_scope_mismatch(
    field: str,
    value: str,
) -> None:
    query = "2015년 6월에 지정된 부여효요양원의 기관별 상세주소는 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"line_name": "부여효요양원", "period": "2015-06"},
            "target_axis": {"column": "기관별 상세주소", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2015-06", "2015년 6월", "201506"],
                "row_entity": ["부여효요양원"],
                "target_column": ["기관별 상세주소"],
                "display_value": [],
            },
        },
    )
    sibling = {
        "doc_id": "doc-care",
        "chunk_id": "chunk-date",
        "source_atom_id": "src-date",
        "source_family": "XLSX",
        "granularity": "cell",
        "text": (
            "sheet=일반현황 | range=A5002:J5051 | cell=H5002 | "
            "row_label=장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176 | "
            "column_label=지정일자 | target_column=지정일자 | 지정일자=2015-06-01"
        ),
        "sheet": "일반현황",
        "cell_range": "A5002:J5051",
        "cell": "H5002",
        "row_index_1based": "5002",
        "row_label": "장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176",
        "column_label": "지정일자",
        "target_column": "지정일자",
    }
    if value:
        sibling[field] = value
    else:
        sibling.pop(field, None)
    row = {
        "id": "xlsx-same-row-period-cell-composite-scope-mismatch",
        "query": query,
        "generated_answer": "충청남도 부여군 석성면 왕릉로 773",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-care",
                "chunk_id": "chunk-address",
                "source_atom_id": "src-address",
                "source_family": "XLSX",
                "granularity": "cell",
                "text": (
                    "sheet=일반현황 | range=A5002:J5051 | cell=J5002 | "
                    "row_label=장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176 | "
                    "column_label=기관별 상세주소 | target_column=기관별 상세주소 | "
                    "기관별 상세주소=충청남도 부여군 석성면 왕릉로 773"
                ),
                "sheet": "일반현황",
                "cell_range": "A5002:J5051",
                "cell": "J5002",
                "row_index_1based": "5002",
                "row_label": "장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176",
                "column_label": "기관별 상세주소",
                "target_column": "기관별 상세주소",
            },
            sibling,
        ],
    }

    candidates = actual_rag_eval._xlsx_locator_tool_candidates(row)

    assert all(candidate["accepted_for_regating"] is False for candidate in candidates)
    assert not any(candidate.get("locator_text_source") == "source_owned_sibling_row_context" for candidate in candidates)


def test_xlsx_locator_sibling_row_composite_rejects_forbidden_sibling_context_fields() -> None:
    query = "2015년 6월에 지정된 부여효요양원의 기관별 상세주소는 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"line_name": "부여효요양원", "period": "2015-06"},
            "target_axis": {"column": "기관별 상세주소", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2015-06", "2015년 6월", "201506"],
                "row_entity": ["부여효요양원"],
                "target_column": ["기관별 상세주소"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "xlsx-same-row-period-cell-composite-forbidden-sibling",
        "query": query,
        "generated_answer": "충청남도 부여군 석성면 왕릉로 773",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-care",
                "chunk_id": "chunk-address",
                "source_atom_id": "src-address",
                "source_family": "XLSX",
                "granularity": "cell",
                "text": (
                    "sheet=일반현황 | range=A5002:J5051 | cell=J5002 | "
                    "row_label=장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176 | "
                    "column_label=기관별 상세주소 | target_column=기관별 상세주소 | "
                    "기관별 상세주소=충청남도 부여군 석성면 왕릉로 773"
                ),
                "sheet": "일반현황",
                "cell_range": "A5002:J5051",
                "cell": "J5002",
                "row_index_1based": "5002",
                "row_label": "장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176",
                "column_label": "기관별 상세주소",
                "target_column": "기관별 상세주소",
            },
            {
                "doc_id": "doc-care",
                "chunk_id": "chunk-date",
                "source_atom_id": "src-date",
                "source_family": "XLSX",
                "granularity": "cell",
                "text": (
                    "sheet=일반현황 | range=A5002:J5051 | cell=H5002 | "
                    "row_label=장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176 | "
                    "column_label=지정일자 | target_column=지정일자 | 지정일자=2015-06-01"
                ),
                "formula": "=SECRET_SIBLING_FORMULA",
                "raw_tool_payload": {"secret": "SECRET_SIBLING_RAW_TOOL_PAYLOAD"},
                "sheet": "일반현황",
                "cell_range": "A5002:J5051",
                "cell": "H5002",
                "row_index_1based": "5002",
                "row_label": "장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176",
                "column_label": "지정일자",
                "target_column": "지정일자",
            },
        ],
    }

    candidates = actual_rag_eval._xlsx_locator_tool_candidates(row)

    assert all(candidate["accepted_for_regating"] is False for candidate in candidates)
    assert not any(candidate.get("locator_text_source") == "source_owned_sibling_row_context" for candidate in candidates)
    encoded = json.dumps(candidates, ensure_ascii=False)
    assert "SECRET_SIBLING_FORMULA" not in encoded
    assert "SECRET_SIBLING_RAW_TOOL_PAYLOAD" not in encoded


def test_xlsx_locator_sibling_row_composite_rejects_forbidden_base_context_fields() -> None:
    query = "2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"line_name": "해뜨는요양원2", "period": "2014-12"},
            "target_axis": {"column": "시도 시군구 법정동명", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2014-12", "2014년 12월", "201412"],
                "row_entity": ["해뜨는요양원2"],
                "target_column": ["시도 시군구 법정동명"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "xlsx-split-axis-composite-forbidden-base",
        "query": query,
        "generated_answer": "대구광역시 북구 복현동",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-cell",
                "source_atom_id": "src-cell",
                "source_family": "XLSX",
                "granularity": "cell",
                "text": (
                    "sheet=일반현황 | range=A752:J801 | cell=G752 | "
                    "row_label=장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526 | "
                    "column_label=시도 시군구 법정동명 | target_column=시도 시군구 법정동명 | "
                    "시도 시군구 법정동명=대구광역시 북구 복현동"
                ),
                "formula": "=SECRET_FORMULA_NEVER_USED",
                "raw_tool_payload": {"secret": "SECRET_RAW_TOOL_PAYLOAD"},
                "sheet": "일반현황",
                "cell_range": "A752:J801",
                "cell": "G752",
                "row_index_1based": "752",
                "row_label": "장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526",
                "column_label": "시도 시군구 법정동명",
                "target_column": "시도 시군구 법정동명",
            },
            {
                "doc_id": "doc-cell",
                "source_atom_id": "src-row",
                "source_family": "XLSX",
                "granularity": "table_row",
                "text": (
                    "sheet=일반현황 | range=A752:J801 | "
                    "해뜨는요양원2 | 41526 | 27 | 230 | 112 | 대구광역시 북구 복현동 | "
                    "2014-12-31 | 2014-12-31 | 대구광역시 북구 공항로 10-7 (복현동)"
                ),
                "sheet": "일반현황",
                "cell_range": "A752:J801",
            },
        ],
    }

    candidates = actual_rag_eval._xlsx_locator_tool_candidates(row)

    assert all(candidate["accepted_for_regating"] is False for candidate in candidates)
    assert not any(
        candidate.get("locator_text_source") == "source_owned_sibling_row_context"
        for candidate in candidates
    )
    forbidden_candidates = [
        candidate
        for candidate in candidates
        if {"formula", "raw_tool_payload"} <= set(candidate.get("forbidden_input_fields_seen", []))
    ]
    assert forbidden_candidates
    assert all(
        candidate["rejection_reason"] == "forbidden_input_fields_present"
        for candidate in forbidden_candidates
    )
    encoded = json.dumps(candidates, ensure_ascii=False)
    assert "SECRET_FORMULA_NEVER_USED" not in encoded
    assert "SECRET_RAW_TOOL_PAYLOAD" not in encoded


def test_run_eval_xlsx_locator_sibling_row_composite_regates_and_persists_runstore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = tmp_path / "xlsx_locator_sibling_composite_gold.jsonl"
    context = tmp_path / "xlsx_locator_sibling_composite_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_locator_sibling_composite"
    query = "2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"line_name": "해뜨는요양원2", "period": "2014-12"},
            "target_axis": {"column": "시도 시군구 법정동명", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2014-12", "2014년 12월", "201412"],
                "row_entity": ["해뜨는요양원2"],
                "target_column": ["시도 시군구 법정동명"],
                "display_value": [],
            },
        },
    )
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx_locator_sibling_composite_q",
                "query": query,
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "xlsx_locator_sibling_composite_q",
                "generated_answer": "대구광역시 북구 복현동",
                "query_evidence_planner": planner,
                "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-xlsx-sibling",
                        "chunk_id": "chunk-cell",
                        "source_atom_id": "src-cell",
                        "source_family": "XLSX",
                        "granularity": "cell",
                        "text": (
                            "sheet=일반현황 | range=A752:J801 | cell=G752 | "
                            "row_label=장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526 | "
                            "column_label=시도 시군구 법정동명 | target_column=시도 시군구 법정동명 | "
                            "시도 시군구 법정동명=대구광역시 북구 복현동"
                        ),
                        "sheet": "일반현황",
                        "cell_range": "A752:J801",
                        "cell": "G752",
                        "row_index_1based": "752",
                        "row_label": "장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526",
                        "column_label": "시도 시군구 법정동명",
                        "target_column": "시도 시군구 법정동명",
                    },
                    {
                        "doc_id": "doc-xlsx-sibling",
                        "chunk_id": "chunk-row",
                        "source_atom_id": "src-row",
                        "source_family": "XLSX",
                        "granularity": "table_row",
                        "text": (
                            "sheet=일반현황 | range=A752:J801 | "
                            "해뜨는요양원2 | 41526 | 27 | 230 | 112 | 대구광역시 북구 복현동 | "
                            "2014-12-31 | 2014-12-31 | 대구광역시 북구 공항로 10-7 (복현동)"
                        ),
                        "sheet": "일반현황",
                        "cell_range": "A752:J801",
                        "row_index_1based": "752",
                    },
                ],
                "citations": [],
            }
        ],
    )

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {
                "source_family_hint": "xlsx",
                "query_task": "entity_attribute_lookup",
                "row_filters": {"line_name": "해뜨는요양원2", "period": "2014-12"},
                "target_axis": {"column": "시도 시군구 법정동명", "value_type": "text"},
                "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
                "intent_tokens": ["무엇입니까"],
            },
            {"raw_response_sha256": "sha256:sibling-composite-planner"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=2,
        run_id="xlsx_locator_sibling_composite",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        xlsx_locator_tool_execute_once=True,
        llm_query_anchor_classifier=True,
        local_llm_composer_model="gemma4-e2b-local",
        skip_local_llm_composer_endpoint_check=True,
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    assert row["xlsx_locator_tool_use"]["execution_status"] == "accepted_after_regating"
    assert row["xlsx_locator_tool_use"]["source_row_context_candidate_count"] == 1
    assert row["xlsx_locator_tool_use"]["source_row_context_doc_identity_mismatch_candidate_count"] == 0
    assert row["xlsx_locator_tool_use"]["source_row_context_blocked_by_doc_identity_mismatch"] is False
    assert row["evidence_gate"]["selected_evidence"][0]["locator_text_source"] == "source_owned_sibling_row_context"
    assert row["evidence_gate"]["selected_evidence"][0]["source_row_context_source_atom_id"] == "src-row"
    with sqlite3.connect(output_dir / "run.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        candidate = conn.execute(
            "SELECT locator_text_source, accepted_for_regating, source_row_context_source_atom_id, "
            "source_row_context_doc_id, source_date_aliases_json, matched_validated_required_axes_json, "
            "missing_validated_required_axes_json "
            "FROM tool_candidates WHERE locator_text_source = 'source_owned_sibling_row_context'"
        ).fetchone()
        assert candidate is not None
        assert candidate["accepted_for_regating"] == 1
        assert candidate["source_row_context_source_atom_id"] == "src-row"
        assert candidate["source_row_context_doc_id"] == "doc-xlsx-sibling"
        assert "2014년 12월" in json.loads(candidate["source_date_aliases_json"])
        assert json.loads(candidate["matched_validated_required_axes_json"]) == [
            "period",
            "row_entity",
            "target_column",
            "display_value",
        ]
        assert json.loads(candidate["missing_validated_required_axes_json"]) == []
        selected = conn.execute(
            "SELECT source_row_context_source_atom_id, source_row_context_doc_id "
            "FROM selected_evidence WHERE source_row_context_source_atom_id = 'src-row'"
        ).fetchone()
        assert selected is not None
        assert selected["source_row_context_doc_id"] == "doc-xlsx-sibling"
        invocation = conn.execute(
            "SELECT accepted_candidate_count, complete_validated_axis_candidate_count, "
            "validated_axis_split_across_candidates, source_row_context_candidate_count, "
            "source_row_context_doc_identity_mismatch_candidate_count, "
            "source_row_context_blocked_by_doc_identity_mismatch FROM tool_invocations"
        ).fetchone()
        assert dict(invocation) == {
            "accepted_candidate_count": 1,
            "complete_validated_axis_candidate_count": 1,
            "validated_axis_split_across_candidates": 0,
            "source_row_context_candidate_count": 1,
            "source_row_context_doc_identity_mismatch_candidate_count": 0,
            "source_row_context_blocked_by_doc_identity_mismatch": 0,
        }
        actual_rag_eval.validate_xlsx_locator_run_store(
            "xlsx_locator_sibling_composite",
            report["xlsx_locator_tool_execute_once"],
            run_store_path=output_dir / "run.sqlite",
        )


def test_run_eval_xlsx_locator_source_row_context_doc_mismatch_persists_fail_closed_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = tmp_path / "xlsx_locator_doc_mismatch_gold.jsonl"
    context = tmp_path / "xlsx_locator_doc_mismatch_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_locator_doc_mismatch"
    query = "2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"line_name": "해뜨는요양원2", "period": "2014-12"},
            "target_axis": {"column": "시도 시군구 법정동명", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2014-12", "2014년 12월", "201412"],
                "row_entity": ["해뜨는요양원2"],
                "target_column": ["시도 시군구 법정동명"],
                "display_value": [],
            },
        },
    )
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx_locator_doc_mismatch_q",
                "query": query,
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "xlsx_locator_doc_mismatch_q",
                "generated_answer": "대구광역시 북구 복현동",
                "query_evidence_planner": planner,
                "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-cell",
                        "chunk_id": "chunk-cell",
                        "source_atom_id": "src-cell",
                        "source_family": "XLSX",
                        "granularity": "cell",
                        "text": (
                            "sheet=일반현황 | range=A752:J801 | cell=G752 | "
                            "row_label=장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526 | "
                            "column_label=시도 시군구 법정동명 | target_column=시도 시군구 법정동명 | "
                            "시도 시군구 법정동명=대구광역시 북구 복현동"
                        ),
                        "sheet": "일반현황",
                        "cell_range": "A752:J801",
                        "cell": "G752",
                        "row_index_1based": "752",
                        "row_label": "장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526",
                        "column_label": "시도 시군구 법정동명",
                        "target_column": "시도 시군구 법정동명",
                    },
                    {
                        "doc_id": "doc-row-other",
                        "chunk_id": "chunk-row",
                        "source_atom_id": "src-row",
                        "source_family": "XLSX",
                        "granularity": "table_row",
                        "text": (
                            "sheet=일반현황 | range=A752:J801 | "
                            "해뜨는요양원2 | 41526 | 27 | 230 | 112 | 대구광역시 북구 복현동 | "
                            "2014-12-31 | 2014-12-31 | 대구광역시 북구 공항로 10-7 (복현동)"
                        ),
                        "sheet": "일반현황",
                        "cell_range": "A752:J801",
                    },
                ],
                "citations": [],
            }
        ],
    )

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {
                "source_family_hint": "xlsx",
                "query_task": "entity_attribute_lookup",
                "row_filters": {"line_name": "해뜨는요양원2", "period": "2014-12"},
                "target_axis": {"column": "시도 시군구 법정동명", "value_type": "text"},
                "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
                "intent_tokens": ["무엇입니까"],
            },
            {"raw_response_sha256": "sha256:doc-mismatch-planner"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=2,
        run_id="xlsx_locator_doc_mismatch",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        xlsx_locator_tool_execute_once=True,
        llm_query_anchor_classifier=True,
        local_llm_composer_model="gemma4-e2b-local",
        skip_local_llm_composer_endpoint_check=True,
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    locator = report["xlsx_locator_tool_execute_once"]
    row = report["items"][0]
    tool_use = row["xlsx_locator_tool_use"]

    assert report["evidence_gate"]["allowed_answer_count"] == 0
    assert tool_use["execution_status"] == "skipped_missing_source_locator"
    assert tool_use["accepted_candidate_count"] == 0
    assert tool_use["source_row_context_candidate_count"] == 0
    assert tool_use["source_row_context_doc_identity_mismatch_candidate_count"] == 1
    assert tool_use["source_row_context_blocked_by_doc_identity_mismatch"] is True
    assert (
        tool_use["source_row_context_fail_closed_policy"]
        == "requires_same_doc_sheet_range_row_index_for_sibling_row_context"
    )
    assert locator["official_metric"] is False
    assert locator["official_metric_input_rows"] == 0
    assert locator["guardrail_status"]["evidence_gate_loosened"] is False
    assert locator["guardrail_status"]["official_metric_input_rows"] == 0
    assert locator["accepted_candidate_count"] == 0
    assert locator["source_row_context_candidate_count"] == 0
    assert locator["source_row_context_doc_identity_mismatch_candidate_count"] == 1
    assert locator["source_row_context_doc_identity_mismatch_row_count"] == 1
    assert locator["candidate_budget_diagnostic"]["source_row_context_doc_identity_mismatch_candidate_count"] == 1
    assert locator["candidate_budget_diagnostic"]["source_row_context_doc_identity_mismatch_row_count"] == 1
    assert (
        locator["candidate_budget_diagnostic"]["source_row_context_fail_closed_policy"]
        == "requires_same_doc_sheet_range_row_index_for_sibling_row_context"
    )
    encoded = json.dumps(report, ensure_ascii=False)
    assert "source_owned_sibling_row_context" not in encoded

    with sqlite3.connect(output_dir / "run.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        invocation = conn.execute(
            "SELECT accepted_candidate_count, complete_validated_axis_candidate_count, "
            "validated_axis_split_across_candidates, source_row_context_candidate_count, "
            "source_row_context_doc_identity_mismatch_candidate_count, "
            "source_row_context_blocked_by_doc_identity_mismatch FROM tool_invocations"
        ).fetchone()
        assert dict(invocation) == {
            "accepted_candidate_count": 0,
            "complete_validated_axis_candidate_count": 0,
            "validated_axis_split_across_candidates": 1,
            "source_row_context_candidate_count": 0,
            "source_row_context_doc_identity_mismatch_candidate_count": 1,
            "source_row_context_blocked_by_doc_identity_mismatch": 1,
        }
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM selected_evidence WHERE source_row_context_source_atom_id != ''"
            ).fetchone()[0]
            == 0
        )
        diagnostic_candidate = conn.execute(
            "SELECT source_atom_id, doc_id, source_row_context_source_atom_id, source_row_context_doc_id "
            "FROM tool_candidates WHERE source_row_context_doc_id != ''"
        ).fetchone()
        assert dict(diagnostic_candidate) == {
            "source_atom_id": "src-cell",
            "doc_id": "doc-cell",
            "source_row_context_source_atom_id": "src-row",
            "source_row_context_doc_id": "doc-row-other",
        }
        actual_rag_eval.validate_xlsx_locator_run_store(
            "xlsx_locator_doc_mismatch",
            locator,
            run_store_path=output_dir / "run.sqlite",
        )
        conn.execute(
            "UPDATE tool_candidates SET source_row_context_source_atom_id = '', source_row_context_doc_id = ''"
        )
        conn.commit()
        with pytest.raises(DatasetSchemaError, match="doc mismatch diagnostics missing"):
            actual_rag_eval.validate_xlsx_locator_run_store(
                "xlsx_locator_doc_mismatch",
                locator,
                run_store_path=output_dir / "run.sqlite",
            )


def test_xlsx_locator_materializes_display_value_from_target_column_segment() -> None:
    query = "2008년 6월에 지정된 청운노인요양원의 기관별 상세주소는 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"period": "2008-06", "line_name": "청운노인요양원"},
            "target_axis": {"column": "기관별 상세주소", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2008-06", "2008년 6월"],
                "row_entity": ["청운노인요양원"],
                "target_column": ["기관별 상세주소"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "xlsx-display-value-materialize",
        "query": query,
        "generated_answer": "서울특별시 종로구 비봉길 76 (구기동)",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
    }
    context = {
        "doc_id": "doc-xlsx",
        "chunk_id": "chunk-xlsx",
        "source_atom_id": "src-xlsx",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": (
            "sheet=일반현황 | range=A2:J51 | cell=J2 | "
            "row_label=장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | "
            "column_label=기관별 상세주소 | target_column=기관별 상세주소 | "
            "지정일자=2008-06-25 | 기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동)"
        ),
        "sheet": "일반현황",
        "cell_range": "A2:J51",
        "cell": "J2",
        "row_index_1based": "2",
        "row_label": "장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001",
        "column_label": "기관별 상세주소",
        "target_column": "기관별 상세주소",
    }

    candidate = actual_rag_eval._xlsx_locator_candidate_from_context(row, context)

    assert candidate is not None
    assert candidate["display_value"] == "서울특별시 종로구 비봉길 76 (구기동)"
    assert candidate["display_value_source"] == "source_owned_target_column_segment"
    assert "display_value" in candidate["input_fields_used"]
    assert candidate["matched_validated_required_axes"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert candidate["missing_validated_required_axes"] == []
    assert candidate["accepted_for_regating"] is True
    encoded = json.dumps(candidate, ensure_ascii=False)
    assert "expected_answer" not in encoded
    assert "normalized_value" not in encoded
    assert "formula" not in encoded


def test_xlsx_locator_records_source_date_aliases_without_accepting_incomplete_candidate() -> None:
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
        "id": "xlsx-source-date-alias",
        "query": query,
        "generated_answer": "근거만으로는 알 수 없습니다.",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
    }
    context = {
        "doc_id": "doc-xlsx-date-alias",
        "chunk_id": "chunk-xlsx-date-alias",
        "source_atom_id": "src-xlsx-date-alias",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": "sheet=철도 | range=A302:D351 | 년월: 201902 | 노선명: 안산선 | 수송인원",
        "sheet": "철도",
        "cell_range": "A302:D351",
    }

    candidate = actual_rag_eval._xlsx_locator_candidate_from_context(row, context)

    assert candidate is not None
    assert candidate["source_date_aliases"] == ["2019년 2월", "2019년", "2월"]
    assert "source_date_aliases" in candidate["input_fields_used"]
    assert candidate["matched_validated_required_axes"] == ["period", "row_entity", "target_column"]
    assert candidate["missing_validated_required_axes"] == ["display_value"]
    assert candidate["accepted_for_regating"] is False
    encoded = json.dumps(candidate, ensure_ascii=False)
    assert "expected_answer" not in encoded
    assert "normalized_value" not in encoded
    assert "formula" not in encoded


def test_xlsx_locator_accepts_same_candidate_source_date_alias_package() -> None:
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
        "id": "xlsx-source-date-alias-package",
        "query": query,
        "generated_answer": "999명",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
    }
    context = {
        "doc_id": "doc-xlsx-date-alias-package",
        "chunk_id": "chunk-xlsx-date-alias-package",
        "source_atom_id": "src-xlsx-date-alias-package",
        "evidence_bundle_id": "bundle-xlsx-date-alias-package",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": (
            "sheet=철도 | range=A302:D351 | row_label=노선명=안산선 | "
            "period=201902 | target_column=수송인원 | display_value=999명"
        ),
        "sheet": "철도",
        "cell_range": "A302:D351",
        "row_index_1based": "302",
        "row_label": "노선명=안산선",
        "column_label": "수송인원",
        "target_column": "수송인원",
        "display_value": "999명",
    }

    candidate = actual_rag_eval._xlsx_locator_candidate_from_context(row, context)

    assert candidate is not None
    assert candidate["accepted_for_regating"] is True
    assert candidate["locator_text_source"] == "source_owned_support_text"
    assert candidate["source_owned_same_candidate_package"] is True
    assert candidate["source_owned_same_candidate_package_policy"].endswith("_v1")
    assert candidate["source_date_aliases"] == ["2019년 2월", "2019년", "2월"]
    assert "source_date_alias=2019년 2월" in candidate["text"]
    assert "source_date_aliases" in candidate["input_fields_used"]
    assert candidate["matched_validated_required_axes"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert candidate["missing_validated_required_axes"] == []
    encoded = json.dumps(candidate, ensure_ascii=False)
    assert "expected_answer" not in encoded
    assert "normalized_value" not in encoded
    assert "formula" not in encoded


def test_xlsx_locator_same_candidate_source_date_alias_package_survives_budget() -> None:
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
        "id": "xlsx-source-date-alias-budget",
        "query": query,
        "generated_answer": "999명",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
    }
    contexts = []
    for index in range(actual_rag_eval.XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET + 1):
        period_part = " | period=201902" if index == actual_rag_eval.XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET else ""
        context = {
            "doc_id": "doc-xlsx-date-alias-budget",
            "chunk_id": f"chunk-xlsx-date-alias-budget-{index}",
            "source_atom_id": f"src-xlsx-date-alias-budget-{index}",
            "evidence_bundle_id": f"bundle-xlsx-date-alias-budget-{index}",
            "source_family": "XLSX",
            "granularity": "table_row",
            "text": (
                "sheet=철도 | range=A302:D351 | row_label=노선명=안산선 | "
                f"target_column=수송인원 | display_value={900 + index}명{period_part}"
            ),
            "sheet": "철도",
            "cell_range": "A302:D351",
            "row_index_1based": str(302 + index),
            "row_label": "노선명=안산선",
            "column_label": "수송인원",
            "target_column": "수송인원",
            "display_value": f"{900 + index}명",
        }
        contexts.append(context)
    row[actual_rag_eval.INTERNAL_XLSX_LOCATOR_SOURCE_CONTEXTS_KEY] = contexts

    candidates = actual_rag_eval._xlsx_locator_tool_candidates(row)

    accepted = [candidate for candidate in candidates if candidate.get("accepted_for_regating") is True]
    assert len(candidates) == actual_rag_eval.XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET
    assert [candidate["source_atom_id"] for candidate in accepted] == [
        "src-xlsx-date-alias-budget-5"
    ]
    assert accepted[0]["candidate_budget_exhausted"] is True
    assert accepted[0]["candidate_pool_count_before_budget"] == 6
    assert accepted[0]["source_owned_same_candidate_package"] is True


def test_xlsx_locator_same_candidate_source_date_alias_package_ignores_generic_metadata_aliases() -> None:
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
        "id": "xlsx-source-date-alias-generic-metadata",
        "query": query,
        "generated_answer": "999명",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
    }
    context = {
        "doc_id": "doc-xlsx-date-alias-generic-metadata",
        "chunk_id": "chunk-xlsx-date-alias-generic-metadata",
        "source_atom_id": "src-xlsx-date-alias-generic-metadata",
        "evidence_bundle_id": "bundle-xlsx-date-alias-generic-metadata",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": (
            "sheet=철도 | range=A302:D351 | row_label=노선명=안산선 | "
            "target_column=수송인원 | display_value=999명"
        ),
        "sheet": "철도",
        "cell_range": "A302:D351",
        "row_index_1based": "302",
        "row_label": "노선명=안산선",
        "column_label": "수송인원",
        "target_column": "수송인원",
        "display_value": "999명",
        "metadata": {
            "source_date_aliases": ["2019년 2월", "2019년", "2월"],
        },
    }

    candidate = actual_rag_eval._xlsx_locator_candidate_from_context(row, context)

    assert candidate is not None
    assert candidate["accepted_for_regating"] is False
    assert candidate["rejection_reason"] == "missing_validated_required_axes_after_tool"
    assert candidate["missing_validated_required_axes"] == ["period"]
    assert "source_owned_same_candidate_package" not in candidate
    assert "source_date_aliases" not in candidate


def test_xlsx_locator_date_aliases_ignore_bare_or_non_date_compact_numbers() -> None:
    assert actual_rag_eval._xlsx_locator_date_aliases("201902") == []
    assert actual_rag_eval._xlsx_locator_date_aliases("관리번호: 201902") == []
    assert actual_rag_eval._xlsx_locator_date_aliases("row_id=201902") == []
    assert actual_rag_eval._xlsx_locator_date_aliases("영남대로 1351-12") == []
    assert actual_rag_eval._xlsx_locator_date_aliases("년월: 201902") == ["2019년 2월", "2019년", "2월"]


def test_run_eval_xlsx_locator_persists_source_date_aliases_for_rejected_candidate(tmp_path: Path) -> None:
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_locator_source_date_alias"
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
    context = {
        "doc_id": "doc-xlsx-date-alias",
        "chunk_id": "chunk-xlsx-date-alias",
        "source_atom_id": "src-xlsx-date-alias",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": "sheet=철도 | range=A302:D351 | 년월: 201902 | 노선명: 안산선 | 수송인원",
        "sheet": "철도",
        "cell_range": "A302:D351",
    }
    before_row = {
        "id": "xlsx_locator_source_date_alias_q",
        "query": query,
        "answerability": "answerable",
        "track": "xlsx_business_structured",
        "generated_answer": "안산선의 수송인원은 999명입니다.",
        "answer_gate_decision": "block_unsupported_answer",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [context],
        "citations": [],
        "evidence_gate": {
            "evidence_package_status": "insufficient",
            "answer_gate_decision": "block_unsupported_answer",
            "validation_reasons": ["missing_validated_required_axes"],
            "retrieved_evidence_candidates": [context],
            "selected_evidence": [],
        },
    }

    after_rows, record = actual_rag_eval.apply_xlsx_locator_tool_execute_once_to_outputs(
        [before_row],
        evidence_gate_mode="enforce",
        citation_format="evidence-id",
        composer_provider="selected-evidence-deterministic-v1",
        local_llm_model="gemma4-e2b-local",
        skip_local_llm_endpoint_check=True,
    )
    run_store_path = output_dir / "run.sqlite"
    actual_rag_eval.XlsxLocatorRunStore(run_store_path).write_run_record(
        run_id="xlsx_locator_source_date_alias",
        dataset_slug="unit",
        collection="unit",
        record=record,
        before_rows=[before_row],
        after_rows=after_rows,
    )
    locator = actual_rag_eval.project_xlsx_locator_run_record(record, run_store_path=run_store_path)

    assert locator["accepted_candidate_count"] == 0
    assert locator["gate_delta"]["allowed_answer_count_delta"] == 0
    assert after_rows[0]["xlsx_locator_tool_use"]["execution_status"] == "skipped_missing_source_locator"

    with sqlite3.connect(run_store_path) as conn:
        conn.row_factory = sqlite3.Row
        candidate = conn.execute(
            "SELECT source_date_aliases_json, input_fields_used_json, accepted_for_regating, "
            "rejection_reason, matched_validated_required_axes_json, "
            "missing_validated_required_axes_json "
            "FROM tool_candidates WHERE source_atom_id = 'src-xlsx-date-alias'"
        ).fetchone()
        assert candidate is not None
        assert json.loads(candidate["source_date_aliases_json"]) == ["2019년 2월", "2019년", "2월"]
        assert "source_date_aliases" in json.loads(candidate["input_fields_used_json"])
        assert candidate["accepted_for_regating"] == 0
        assert candidate["rejection_reason"] == "missing_validated_required_axes_after_tool"
        assert json.loads(candidate["matched_validated_required_axes_json"]) == [
            "period",
            "row_entity",
            "target_column",
        ]
        assert json.loads(candidate["missing_validated_required_axes_json"]) == ["display_value"]
        actual_rag_eval.validate_xlsx_locator_run_store(
            "xlsx_locator_source_date_alias",
            locator,
            run_store_path=run_store_path,
        )


def test_run_eval_xlsx_locator_same_candidate_source_date_alias_package_regates_and_persists(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_locator_source_date_alias_package"
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
    context = {
        "doc_id": "doc-xlsx-source-date-alias-package",
        "chunk_id": "chunk-xlsx-source-date-alias-package",
        "source_atom_id": "src-xlsx-source-date-alias-package",
        "evidence_bundle_id": "bundle-xlsx-source-date-alias-package",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": (
            "sheet=철도 | range=A302:D351 | row_label=노선명=안산선 | period=201902 | "
            "target_column=수송인원 | display_value=999명"
        ),
        "sheet": "철도",
        "cell_range": "A302:D351",
        "row_index_1based": "302",
        "row_label": "노선명=안산선",
        "column_label": "수송인원",
        "target_column": "수송인원",
        "display_value": "999명",
    }
    before_row = {
        "id": "xlsx_locator_source_date_alias_package_q",
        "query": query,
        "answerability": "answerable",
        "track": "xlsx_business_structured",
        "generated_answer": "안산선의 수송인원은 999명입니다.",
        "answer_gate_decision": "block_unsupported_answer",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [context],
        "citations": [],
        "evidence_gate": {
            "evidence_package_status": "insufficient",
            "answer_gate_decision": "block_unsupported_answer",
            "validation_reasons": ["missing_validated_required_axes"],
            "retrieved_evidence_candidates": [context],
            "selected_evidence": [],
        },
    }

    after_rows, record = actual_rag_eval.apply_xlsx_locator_tool_execute_once_to_outputs(
        [before_row],
        evidence_gate_mode="enforce",
        citation_format="evidence-id",
        composer_provider="selected-evidence-deterministic-v1",
        local_llm_model="gemma4-e2b-local",
        skip_local_llm_endpoint_check=True,
    )
    run_store_path = output_dir / "run.sqlite"
    actual_rag_eval.XlsxLocatorRunStore(run_store_path).write_run_record(
        run_id="xlsx_locator_source_date_alias_package",
        dataset_slug="unit",
        collection="unit",
        record=record,
        before_rows=[before_row],
        after_rows=after_rows,
    )
    locator = actual_rag_eval.project_xlsx_locator_run_record(record, run_store_path=run_store_path)

    row = after_rows[0]
    tool_use = row["xlsx_locator_tool_use"]
    assert locator["accepted_candidate_count"] == 1
    assert locator["complete_validated_axis_candidate_count"] == 1
    assert locator["gate_delta"]["allowed_answer_count_delta"] == 1
    assert tool_use["execution_status"] == "accepted_after_regating"
    assert tool_use["accepted_candidate_count"] == 1
    assert tool_use["output_policy"] == "selected_evidence_candidate_must_pass_unchanged_gate"
    selected = row["evidence_gate"]["selected_evidence"][0]
    assert selected["source_atom_id"] == "src-xlsx-source-date-alias-package"
    assert selected["locator_text_source"] == "source_owned_support_text"
    assert selected["source_owned_same_candidate_package"] is True
    assert "source_date_alias=2019년 2월" in selected["text"]
    assert selected["matched_validated_required_axes"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert selected["missing_validated_required_axes"] == []

    with sqlite3.connect(run_store_path) as conn:
        conn.row_factory = sqlite3.Row
        candidate = conn.execute(
            "SELECT source_date_aliases_json, input_fields_used_json, accepted_for_regating, "
            "rejection_reason, locator_text_source, matched_validated_required_axes_json, "
            "missing_validated_required_axes_json FROM tool_candidates "
            "WHERE source_atom_id = 'src-xlsx-source-date-alias-package'"
        ).fetchone()
        assert candidate is not None
        assert json.loads(candidate["source_date_aliases_json"]) == ["2019년 2월", "2019년", "2월"]
        assert "source_date_aliases" in json.loads(candidate["input_fields_used_json"])
        assert candidate["accepted_for_regating"] == 1
        assert candidate["rejection_reason"] == ""
        assert candidate["locator_text_source"] == "source_owned_support_text"
        assert json.loads(candidate["matched_validated_required_axes_json"]) == [
            "period",
            "row_entity",
            "target_column",
            "display_value",
        ]
        assert json.loads(candidate["missing_validated_required_axes_json"]) == []
        actual_rag_eval.validate_xlsx_locator_run_store(
            "xlsx_locator_source_date_alias_package",
            locator,
            run_store_path=run_store_path,
        )

    selected_encoded = json.dumps(selected, ensure_ascii=False)
    assert "expected_answer" not in selected_encoded
    assert "normalized_value" not in selected_encoded
    assert "formula" not in selected_encoded


def test_run_eval_xlsx_locator_materialized_display_value_regates_and_persists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = tmp_path / "xlsx_locator_materialized_display_gold.jsonl"
    context = tmp_path / "xlsx_locator_materialized_display_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_locator_materialized_display"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx_locator_materialized_display_q",
                "query": "2008년 6월에 지정된 청운노인요양원의 기관별 상세주소는 무엇입니까?",
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "xlsx_locator_materialized_display_q",
                "generated_answer": "서울특별시 종로구 비봉길 76 (구기동)",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-xlsx-materialized-display",
                        "chunk_id": "chunk-xlsx-materialized-display",
                        "source_atom_id": "src-xlsx-materialized-display",
                        "evidence_bundle_id": "bundle-xlsx-materialized-display",
                        "source_family": "XLSX",
                        "granularity": "table_row",
                        "text": "청운노인요양원 기관별 상세주소",
                        "xlsx_locator_text": (
                            "sheet=일반현황 | cell_range=A2:J51 | cell=J2 | "
                            "row_label=장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | "
                            "column_label=기관별 상세주소 | target_column=기관별 상세주소 | "
                            "지정일자=2008-06-25 | 기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동)"
                        ),
                        "xlsx_locator_metadata": {
                            "sheet": "일반현황",
                            "cell_range": "A2:J51",
                            "cell": "J2",
                            "row_index_1based": "2",
                            "row_label": "장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001",
                            "column_label": "기관별 상세주소",
                            "target_column": "기관별 상세주소",
                        },
                    }
                ],
                "citations": [],
            }
        ],
    )

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {
                "source_family_hint": "xlsx",
                "query_task": "date_filtered_lookup",
                "row_filters": {"period": "2008-06", "facility_name": "청운노인요양원"},
                "target_axis": {"column": "기관별 상세주소", "value_type": "text"},
                "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
                "intent_tokens": ["무엇입니까"],
            },
            {"raw_response_sha256": "sha256:xlsx-materialized-display"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="xlsx_locator_materialized_display",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        xlsx_locator_tool_execute_once=True,
        llm_query_anchor_classifier=True,
        local_llm_composer_model="gemma4-e2b-local",
        skip_local_llm_composer_endpoint_check=True,
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    locator = report["xlsx_locator_tool_execute_once"]

    assert report["evidence_gate"]["allowed_answer_count"] == 1
    assert row["xlsx_locator_tool_use"]["execution_status"] == "accepted_after_regating"
    assert locator["accepted_candidate_count"] == 1
    assert locator["complete_validated_axis_candidate_count"] == 1
    assert locator["validated_axis_split_row_count"] == 0
    selected = row["evidence_gate"]["selected_evidence"][0]
    assert selected["display_value"] == "서울특별시 종로구 비봉길 76 (구기동)"
    assert selected["target_column"] == "기관별 상세주소"

    with sqlite3.connect(output_dir / "run.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        candidate = conn.execute(
            "SELECT display_value, input_fields_used_json, accepted_for_regating, rejection_reason "
            "FROM tool_candidates"
        ).fetchone()
        assert candidate["display_value"] == "서울특별시 종로구 비봉길 76 (구기동)"
        assert "display_value" in json.loads(candidate["input_fields_used_json"])
        assert candidate["accepted_for_regating"] == 1
        assert candidate["rejection_reason"] == ""
        invocation = conn.execute(
            "SELECT complete_validated_axis_candidate_count, validated_axis_split_across_candidates, "
            "best_candidate_missing_validated_required_axes_json FROM tool_invocations"
        ).fetchone()
        assert invocation["complete_validated_axis_candidate_count"] == 1
        assert invocation["validated_axis_split_across_candidates"] == 0
        assert json.loads(invocation["best_candidate_missing_validated_required_axes_json"]) == []

    selected_encoded = json.dumps(selected, ensure_ascii=False)
    assert "expected_answer" not in selected_encoded
    assert "normalized_value" not in selected_encoded
    assert "formula" not in selected_encoded


def test_xlsx_locator_display_value_materialization_fails_closed_on_duplicate_target_segments() -> None:
    query = "2008년 6월에 지정된 청운노인요양원의 기관별 상세주소는 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"period": "2008-06", "line_name": "청운노인요양원"},
            "target_axis": {"column": "기관별 상세주소", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2008-06", "2008년 6월"],
                "row_entity": ["청운노인요양원"],
                "target_column": ["기관별 상세주소"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "xlsx-display-value-duplicate",
        "query": query,
        "generated_answer": "서울특별시 종로구 비봉길 76 (구기동)",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
    }
    context = {
        "doc_id": "doc-xlsx",
        "chunk_id": "chunk-xlsx",
        "source_atom_id": "src-xlsx",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": (
            "sheet=일반현황 | range=A2:J51 | cell=J2 | "
            "row_label=장기요양기관이름=청운노인요양원 | "
            "column_label=기관별 상세주소 | target_column=기관별 상세주소 | "
            "지정일자=2008-06-25 | 기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동) | "
            "기관별 상세주소=부산광역시 중복 주소"
        ),
        "sheet": "일반현황",
        "cell_range": "A2:J51",
        "cell": "J2",
        "row_index_1based": "2",
        "row_label": "장기요양기관이름=청운노인요양원",
        "column_label": "기관별 상세주소",
        "target_column": "기관별 상세주소",
    }

    candidate = actual_rag_eval._xlsx_locator_candidate_from_context(row, context)

    assert candidate is not None
    assert candidate.get("display_value", "") == ""
    assert candidate.get("display_value_source", "") == ""
    assert candidate["missing_validated_required_axes"] == ["display_value"]
    assert candidate["accepted_for_regating"] is False
    assert candidate["rejection_reason"] == "missing_validated_required_axes_after_tool"


def test_xlsx_locator_display_value_materialization_fails_closed_on_same_value_duplicate_target_segments() -> None:
    candidate = {
        "target_column": "기관별 상세주소",
        "column_label": "기관별 상세주소",
    }
    text = (
        "row_label=장기요양기관이름=청운노인요양원 | "
        "target_column=기관별 상세주소 | "
        "기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동) | "
        "기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동)"
    )

    display_value = actual_rag_eval._xlsx_locator_target_column_display_value_from_segments(
        candidate=candidate,
        text=text,
    )

    assert display_value == ""


def test_xlsx_locator_display_value_materialization_fails_closed_on_target_label_alias_collision() -> None:
    candidate = {
        "target_column": "기관별 상세주소",
        "column_label": "주소",
    }
    text = (
        "row_label=장기요양기관이름=청운노인요양원 | "
        "target_column=기관별 상세주소 | "
        "주소=서울특별시 종로구 비봉길 76 (구기동) | "
        "기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동)"
    )

    display_value = actual_rag_eval._xlsx_locator_target_column_display_value_from_segments(
        candidate=candidate,
        text=text,
    )

    assert display_value == ""


def test_xlsx_locator_materialization_ignores_generic_value_segment_without_target_label_key() -> None:
    candidate = {
        "target_column": "기관별 상세주소",
        "column_label": "기관별 상세주소",
    }
    text = (
        "row_label=장기요양기관이름=청운노인요양원 | "
        "target_column=기관별 상세주소 | "
        "value=서울특별시 종로구 비봉길 76 (구기동)"
    )

    display_value = actual_rag_eval._xlsx_locator_target_column_display_value_from_segments(
        candidate=candidate,
        text=text,
    )

    assert display_value == ""


def test_xlsx_locator_forbidden_input_scan_flags_raw_tool_payload_keys() -> None:
    seen = actual_rag_eval._collect_xlsx_locator_forbidden_input_fields(
        {
            "raw_tool_payload": {"secret": "SECRET_RAW_TOOL_PAYLOAD"},
            "rawToolPayload": {"secret": "SECRET_CAMEL_RAW_TOOL_PAYLOAD"},
            "tool_payload": {"secret": "SECRET_TOOL_PAYLOAD"},
            "toolPayload": {"secret": "SECRET_CAMEL_TOOL_PAYLOAD"},
            "text": "toolPayload={'secret':'SECRET_TEXT_TOOL_PAYLOAD'} | rawToolPayload={}",
        }
    )

    assert {"raw_tool_payload", "tool_payload"} <= seen


def test_xlsx_locator_forbidden_input_scan_flags_source_path_and_workbook_ids() -> None:
    text = (
        "row_label=장기요양기관이름=청운노인요양원 | "
        "target_column=기관별 상세주소 | "
        "source_path=C:/private/raw.xlsx | "
        "workbookId=secret-workbook | "
        "workbookVersionId=secret-version | "
        "기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동)"
    )
    seen = actual_rag_eval._collect_xlsx_locator_forbidden_input_fields(
        {
            "source_path": "C:/private/raw.xlsx",
            "workbook_id": "secret-workbook",
            "workbookVersionId": "secret-version",
            "text": text,
        }
    )
    stripped = actual_rag_eval._strip_xlsx_locator_forbidden_text_segments(text)

    assert {"source_path", "workbook_id", "workbook_version_id"} <= seen
    assert "source_path" not in stripped
    assert "workbookId" not in stripped
    assert "workbookVersionId" not in stripped
    assert "기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동)" in stripped


def test_xlsx_locator_rejects_explicit_locator_text_with_source_path_or_workbook_ids() -> None:
    query = "2008년 6월에 지정된 청운노인요양원의 기관별 상세주소는 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"period": "2008-06", "line_name": "청운노인요양원"},
            "target_axis": {"column": "기관별 상세주소", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2008-06", "2008년 6월"],
                "row_entity": ["청운노인요양원"],
                "target_column": ["기관별 상세주소"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "xlsx-source-path-workbook-id-reject",
        "query": query,
        "generated_answer": "서울특별시 종로구 비봉길 76 (구기동)",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
    }
    context = {
        "doc_id": "doc-xlsx",
        "chunk_id": "chunk-xlsx",
        "source_atom_id": "src-xlsx",
        "source_family": "XLSX",
        "granularity": "table_row",
        "xlsx_locator_text": (
            "sheet=일반현황 | cell_range=A2:J51 | cell=J2 | "
            "row_label=장기요양기관이름=청운노인요양원 | "
            "column_label=기관별 상세주소 | target_column=기관별 상세주소 | "
            "지정일자=2008-06-25 | 기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동) | "
            "source_path=C:/private/raw.xlsx | workbook_id=secret-workbook | workbook_version_id=secret-version"
        ),
        "xlsx_locator_metadata": {
            "sheet": "일반현황",
            "cell_range": "A2:J51",
            "cell": "J2",
            "row_index_1based": "2",
            "row_label": "장기요양기관이름=청운노인요양원",
            "column_label": "기관별 상세주소",
            "target_column": "기관별 상세주소",
        },
    }

    candidate = actual_rag_eval._xlsx_locator_candidate_from_context(row, context)

    assert candidate is not None
    assert candidate["accepted_for_regating"] is False
    assert candidate["rejection_reason"] == "forbidden_input_fields_present"
    assert {"source_path", "workbook_id", "workbook_version_id"} <= set(candidate["forbidden_input_fields_used_for_candidate"])


def test_public_report_sanitizer_strips_raw_tool_payload_keys() -> None:
    report = actual_rag_eval._sanitize_public_report_value(
        {
            "safe": "kept",
            "raw_tool_payload": {"secret": "SECRET_RAW_TOOL_PAYLOAD"},
            "tool_payload": {"secret": "SECRET_TOOL_PAYLOAD"},
            "nested": [{"rawToolPayload": "SECRET_CAMEL_TOOL_PAYLOAD"}],
        }
    )

    encoded = json.dumps(report, ensure_ascii=False)
    assert report["safe"] == "kept"
    assert "SECRET_RAW_TOOL_PAYLOAD" not in encoded
    assert "SECRET_TOOL_PAYLOAD" not in encoded
    assert "SECRET_CAMEL_TOOL_PAYLOAD" not in encoded
    assert "raw_tool_payload" not in encoded
    assert "tool_payload" not in encoded
    assert "rawToolPayload" not in encoded


def test_residual_anchor_matrix_reports_source_native_axes_without_shortcuts() -> None:
    query = "2019년 2월 5호선 승차총승객수는 얼마야?"
    source = {
        "doc_id": "doc-xlsx",
        "chunk_id": "chunk-xlsx",
        "source_atom_id": "src-xlsx",
        "evidence_bundle_id": "bundle-xlsx",
        "source_family": "XLSX",
        "text": "2019년 2월 5호선 승차총승객수 값은 15,446,522명입니다.",
        "sheet": "2019년 2월",
        "cell_range": "A1:D7",
        "row_label": "5호선",
        "target_column": "승차총승객수",
        "display_value": "15,446,522",
    }
    row = {
        "id": "xlsx-anchor-matrix",
        "query": query,
        "generated_answer": "15,446,522명",
        "expected_answer": "SECRET_EXPECTED_VALUE_NEVER_RUNTIME",
        "qrels": [{"text": "SECRET_QRELS_NEVER_RUNTIME"}],
        "baseline_topk": [{"text": "SECRET_BASELINE_TOPK_NEVER_RUNTIME"}],
        "retrieved_contexts": [{**source, "formula": "SECRET_FORMULA_NEVER_RUNTIME"}],
        "evidence_gate": {
            "evidence_package_status": "insufficient",
            "answer_gate_decision": "abstain",
            "validation_reasons": ["missing_validated_required_axes"],
            "retrieved_evidence_candidates": [source],
            "selected_evidence": [source],
        },
    }

    matrix = actual_rag_eval.build_residual_anchor_matrix(items=[], rows=[row])

    assert matrix["schema_version"] == "actual_rag_eval.residual_anchor_matrix.v1"
    assert matrix["report_only_diagnostic"] is True
    assert matrix["official_metric"] is False
    assert matrix["uses_expected_fields_as_runtime_inputs"] is False
    assert matrix["uses_qrels_or_labels_as_runtime_inputs"] is False
    matrix_row = matrix["rows"][0]
    assert matrix_row["query_shape"] == "table_lookup"
    assert matrix_row["topk_anchor_presence"]["axis_anchor_present"] is True
    assert matrix_row["selected_evidence_anchor_presence"]["value_anchor_present"] is True
    assert matrix_row["selected_evidence_anchor_presence"]["axis_anchor_present"] is True
    assert matrix_row["final_answer_anchor_presence"]["axis_anchor_present"] is False
    assert matrix_row["residual_classification"] == "selected_evidence_has_value_missing_axis"
    encoded = json.dumps(matrix, ensure_ascii=False)
    assert "SECRET_EXPECTED_VALUE_NEVER_RUNTIME" not in encoded
    assert "SECRET_QRELS_NEVER_RUNTIME" not in encoded
    assert "SECRET_BASELINE_TOPK_NEVER_RUNTIME" not in encoded
    assert "SECRET_FORMULA_NEVER_RUNTIME" not in encoded


def test_source_native_axis_provenance_reports_pdf_location_stages() -> None:
    row = {
        "id": "pdf-axis-provenance",
        "query": "2024년 영업이익 표의 값은 얼마야?",
        "generated_answer": "12.3억원",
        "retrieved_contexts": [
            {
                "doc_id": "doc-pdf",
                "chunk_id": "chunk-pdf",
                "source_atom_id": "src-pdf",
                "evidence_bundle_id": "bundle-pdf",
                "source_family": "PDF",
                "text": "2024년 영업이익 값은 12.3억원입니다.",
                "page_number": 7,
                "section_title": "재무 현황",
                "table_caption": "영업이익 표",
                "bbox": [10, 20, 200, 240],
                "raw_locator": {"page_number": 7, "bbox": [10, 20, 200, 240]},
            }
        ],
        "evidence_gate": {
            "selected_evidence": [
                {
                    "doc_id": "doc-pdf",
                    "source_family": "PDF",
                    "text": "2024년 영업이익 값은 12.3억원입니다.",
                    "page_number": 7,
                    "table_caption": "영업이익 표",
                }
            ],
        },
        "citations": [{"doc_id": "doc-pdf", "source_family": "PDF", "text": "12.3억원", "page_number": 7}],
    }

    provenance = actual_rag_eval.build_source_native_axis_provenance(items=[], rows=[row])

    assert provenance["schema_version"] == "actual_rag_eval.source_native_axis_provenance.v1"
    assert provenance["report_only_diagnostic"] is True
    assert provenance["official_metric"] is False
    assert provenance["stage_notes"]["source_registry_or_manifest"] == (
        "not_inspected_report_only_diagnostic_no_source_registry_or_manifest_runtime_input"
    )
    axis_stages = provenance["rows"][0]["axis_presence_by_stage"]
    assert axis_stages["source_registry_or_manifest"]["present"] == []
    assert axis_stages["source_registry_or_manifest"]["stage_status"] == "not_inspected"
    assert axis_stages["retrieved_context"]["present"] == [
        "page_number",
        "section_title",
        "table_caption",
        "bbox",
    ]
    assert axis_stages["selected_evidence"]["present"] == ["page_number", "table_caption"]
    assert axis_stages["final_citation"]["present"] == ["page_number"]


def test_pdf_source_native_decomposition_reports_page_bbox_table_and_ocr_counts() -> None:
    rows = [
        {
            "id": "pdf-decomposition-table-ocr",
            "query": "2024년 영업이익 표의 값은 얼마야?",
            "expected_answer": "SECRET_EXPECTED_NEVER_USED",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-pdf",
                    "source_family": "PDF",
                    "text": "2024년 영업이익 값은 12.3억원입니다.",
                    "page_number": 7,
                    "bbox": [10, 20, 200, 240],
                    "table_caption": "영업이익 표",
                    "ocr_confidence": 0.42,
                }
            ],
            "evidence_gate": {
                "retrieved_evidence_candidates": [
                    {
                        "doc_id": "doc-pdf",
                        "source_family": "PDF",
                        "text": "2024년 영업이익 값은 12.3억원입니다.",
                        "page_number": 7,
                        "bbox": [10, 20, 200, 240],
                        "table_caption": "영업이익 표",
                        "ocr_confidence": 0.42,
                    }
                ],
                "selected_evidence": [],
            },
        },
        {
            "id": "pdf-decomposition-page-only",
            "query": "보고서 2쪽의 문단은 무엇을 말하나요?",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-pdf-page",
                    "source_family": "PDF",
                    "text": "2쪽 문단 텍스트입니다.",
                    "page": 2,
                }
            ],
        },
        {
            "id": "pdf-decomposition-nested-locator",
            "query": "부록 표의 OCR 근거는 어디인가요?",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-pdf-nested",
                    "source_family": "PDF",
                    "text": "부록 표 OCR 근거입니다.",
                    "metadata": {"pageNumber": 9},
                    "citation_locator": {"boundingBox": [1, 2, 30, 40]},
                    "locator": {"tableId": "appendix-table-1"},
                    "ocrConfidence": "42",
                }
            ],
        },
        {
            "id": "xlsx-ignored",
            "query": "XLSX 행 값은?",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-xlsx",
                    "source_family": "XLSX",
                    "text": "sheet=철도 | display_value=1",
                }
            ],
        },
    ]

    decomposition = actual_rag_eval.build_pdf_source_native_decomposition(items=[], rows=rows)

    assert decomposition == {
        "schema_version": "actual_rag_eval.pdf_source_native_decomposition.v1",
        "report_only_diagnostic": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "pdf_query_count": 3,
        "page_present_count": 3,
        "bbox_present_count": 2,
        "page_bbox_co_located_count": 2,
        "section_or_table_axis_present_count": 2,
        "ocr_confidence_present_count": 2,
        "lower_trust_due_to_ocr_count": 2,
        "uses_expected_fields": False,
        "uses_gold_fields": False,
        "uses_qrels": False,
        "uses_labels": False,
        "uses_ids": False,
        "uses_raw_xlsx_or_pdf_query_time_parsing": False,
    }
    encoded = json.dumps(decomposition, ensure_ascii=False)
    assert "SECRET_EXPECTED_NEVER_USED" not in encoded


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("schema_version", "wrong", "pdf_source_native_decomposition.schema_version"),
        ("official_metric", True, "pdf_source_native_decomposition.official_metric"),
        ("official_metric_input_rows", 1, "pdf_source_native_decomposition.official_metric_input_rows"),
        ("uses_ids", True, "pdf_source_native_decomposition.uses_ids"),
    ],
)
def test_validate_actual_rag_guardrails_rejects_unsafe_pdf_source_native_decomposition(
    field: str,
    value: object,
    match: str,
) -> None:
    summary = {
        "run_id": "pdf-decomposition-guard",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
        "pdf_source_native_decomposition": {
            "schema_version": "actual_rag_eval.pdf_source_native_decomposition.v1",
            "report_only_diagnostic": True,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "pdf_query_count": 1,
            "page_present_count": 1,
            "bbox_present_count": 1,
            "page_bbox_co_located_count": 1,
            "section_or_table_axis_present_count": 1,
            "ocr_confidence_present_count": 1,
            "lower_trust_due_to_ocr_count": 0,
            "uses_expected_fields": False,
            "uses_gold_fields": False,
            "uses_qrels": False,
            "uses_labels": False,
            "uses_ids": False,
            "uses_raw_xlsx_or_pdf_query_time_parsing": False,
        },
    }
    summary["pdf_source_native_decomposition"][field] = value

    with pytest.raises(DatasetSchemaError, match=match):
        validate_actual_rag_guardrails(summary)


def test_xlsx_locator_projection_reports_candidate_budget_taxonomy() -> None:
    budget = actual_rag_eval.XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET
    tool_uses = (
        actual_rag_eval.XlsxLocatorToolUseRecord(
            item_index=0,
            item_id="zero-candidate",
            execution_status="skipped_missing_source_locator",
            candidate_count=0,
            accepted_candidate_count=0,
        ),
        actual_rag_eval.XlsxLocatorToolUseRecord(
            item_index=1,
            item_id="at-budget",
            execution_status="accepted_after_regating",
            candidate_count=budget,
            accepted_candidate_count=1,
            candidate_pool_count_before_budget=budget,
        ),
        actual_rag_eval.XlsxLocatorToolUseRecord(
            item_index=2,
            item_id="over-budget",
            execution_status="skipped_missing_source_locator",
            candidate_count=budget,
            accepted_candidate_count=0,
            candidate_pool_count_before_budget=budget + 2,
        ),
        actual_rag_eval.XlsxLocatorToolUseRecord(
            item_index=3,
            item_id="below-budget",
            execution_status="skipped_missing_source_locator",
            candidate_count=2,
            accepted_candidate_count=0,
        ),
    )
    candidate_records = tuple(
        actual_rag_eval.XlsxLocatorEvidenceCandidateRecord(
            item_index=item_index,
            candidate_index=index,
            source_family="XLSX",
            tool_name=actual_rag_eval.XLSX_LOCATOR_TOOL_NAME,
            tool_policy=actual_rag_eval.XLSX_LOCATOR_TOOL_POLICY,
            source_atom_id=f"src-{item_index}-{index}",
            evidence_bundle_id=f"bundle-{item_index}-{index}",
            doc_id=f"doc-{item_index}-{index}",
            sheet="2019년 2월" if index < 2 else f"2019년 {index}월",
            cell_range=f"A{index}:D{index + 3}",
            table_id="table-a" if index < 2 else f"table-{index}",
            display_value="15,446,522",
            accepted_for_regating=item_index == 1 and index == 0,
            rejection_reason="" if item_index == 1 and index == 0 else "missing_validated_required_axes_after_tool",
        )
        for item_index in (1, 2)
        for index in range(budget)
    )
    record = actual_rag_eval.XlsxLocatorRunRecord(
        schema_version=actual_rag_eval.XLSX_LOCATOR_TOOL_EXECUTE_ONCE_SCHEMA_VERSION,
        enabled=True,
        report_only_diagnostic=True,
        official_metric=False,
        tool_name=actual_rag_eval.XLSX_LOCATOR_TOOL_NAME,
        eligible_failed_row_count=4,
        tool_invocation_count=4,
        accepted_candidate_count=1,
        rejected_candidate_count=budget * 2 - 1,
        gate_delta_record=actual_rag_eval.XlsxLocatorGateDeltaRecord(),
        guardrail_record=actual_rag_eval.XlsxLocatorGuardrailRecord(),
        tool_uses=tool_uses,
        candidates=candidate_records,
    )

    projection = actual_rag_eval.project_xlsx_locator_run_record(record)
    budget_diagnostic = projection["candidate_budget_diagnostic"]

    assert budget_diagnostic["zero_candidate_row_count"] == 1
    assert budget_diagnostic["at_budget_row_count"] == 2
    assert budget_diagnostic["candidate_budget_exhaustion_count"] == 1
    assert budget_diagnostic["candidate_budget_per_query"] == budget
    assert budget_diagnostic["accepted_for_regating_count"] == 1
    assert budget_diagnostic["same_sheet_candidate_count"] == budget * 2
    assert budget_diagnostic["same_table_candidate_count"] == budget * 2
    assert budget_diagnostic["same_range_candidate_count"] == budget * 2
    assert budget_diagnostic["deduped_candidate_count"] == budget * 2
    assert budget_diagnostic["rejected_candidate_count_by_reason"] == {
        "missing_validated_required_axes_after_tool": budget * 2 - 1
    }


def test_xlsx_locator_projection_reports_query_anchor_tool_acceptance_diagnostic() -> None:
    tool_uses = (
        actual_rag_eval.XlsxLocatorToolUseRecord(
            item_index=0,
            item_id="xlsx-query-anchor-blocked",
            execution_status="skipped_missing_source_locator",
            candidate_count=3,
            accepted_candidate_count=0,
            source_family_hint="xlsx",
            query_task="date_filtered_lookup",
            before_gate_status="block_answer",
            after_gate_status="block_answer",
            before_residual_class="selected_evidence_has_value_missing_axis",
            after_residual_class="selected_evidence_has_value_missing_axis",
            matched_query_anchors=("2019년", "5월"),
            remaining_missing_query_anchors=("명입니까",),
            matched_validated_required_axes=("period", "row_entity", "target_column", "display_value"),
            remaining_missing_validated_required_axes=(),
        ),
        actual_rag_eval.XlsxLocatorToolUseRecord(
            item_index=1,
            item_id="xlsx-query-anchor-accepted",
            execution_status="accepted_after_regating",
            candidate_count=1,
            accepted_candidate_count=1,
            source_family_hint="xlsx",
            query_task="date_filtered_lookup",
            before_gate_status="block_answer",
            after_gate_status="allow_answer",
            before_residual_class="selected_evidence_has_value_missing_axis",
            after_residual_class="no_residual",
            matched_query_anchors=("2019년", "5월", "우이신설선"),
            remaining_missing_query_anchors=(),
            matched_validated_required_axes=("period", "row_entity", "target_column", "display_value"),
            remaining_missing_validated_required_axes=(),
        ),
    )
    candidates = (
        actual_rag_eval.XlsxLocatorEvidenceCandidateRecord(
            item_index=0,
            candidate_index=0,
            source_family="XLSX",
            tool_name=actual_rag_eval.XLSX_LOCATOR_TOOL_NAME,
            tool_policy=actual_rag_eval.XLSX_LOCATOR_TOOL_POLICY,
            source_atom_id="src-blocked-0",
            evidence_bundle_id="bundle-blocked-0",
            doc_id="doc-blocked",
            sheet="2019년 5월",
            cell_range="A1:D4",
            row_label="우이신설선",
            target_column="승차총승객수",
            display_value="15,446,522",
            matched_query_anchors=("2019년", "5월"),
            missing_query_anchors_after_tool=("명입니까",),
            matched_validated_required_axes=("period", "row_entity", "target_column", "display_value"),
            missing_validated_required_axes=(),
            confidence_tier="high",
            accepted_for_regating=False,
            rejection_reason="missing_query_anchor_after_tool",
        ),
        actual_rag_eval.XlsxLocatorEvidenceCandidateRecord(
            item_index=0,
            candidate_index=1,
            source_family="XLSX",
            tool_name=actual_rag_eval.XLSX_LOCATOR_TOOL_NAME,
            tool_policy=actual_rag_eval.XLSX_LOCATOR_TOOL_POLICY,
            source_atom_id="src-blocked-1",
            evidence_bundle_id="bundle-blocked-1",
            doc_id="doc-blocked",
            sheet="2019년 5월",
            cell_range="A5:D8",
            row_label="우이신설선",
            target_column="승차총승객수",
            display_value="15,446,522",
            matched_query_anchors=("2019년",),
            missing_query_anchors_after_tool=("5월", "명입니까"),
            matched_validated_required_axes=("period", "row_entity", "target_column"),
            missing_validated_required_axes=("display_value",),
            confidence_tier="high",
            accepted_for_regating=False,
            rejection_reason="missing_query_anchor_after_tool",
        ),
        actual_rag_eval.XlsxLocatorEvidenceCandidateRecord(
            item_index=0,
            candidate_index=2,
            source_family="XLSX",
            tool_name=actual_rag_eval.XLSX_LOCATOR_TOOL_NAME,
            tool_policy=actual_rag_eval.XLSX_LOCATOR_TOOL_POLICY,
            source_atom_id="src-blocked-2",
            evidence_bundle_id="bundle-blocked-2",
            doc_id="doc-blocked",
            sheet="",
            cell_range="",
            matched_query_anchors=(),
            missing_query_anchors_after_tool=("명입니까",),
            matched_validated_required_axes=(),
            missing_validated_required_axes=(),
            confidence_tier="low",
            accepted_for_regating=False,
            rejection_reason="missing_query_anchor_after_tool",
        ),
        actual_rag_eval.XlsxLocatorEvidenceCandidateRecord(
            item_index=1,
            candidate_index=0,
            source_family="XLSX",
            tool_name=actual_rag_eval.XLSX_LOCATOR_TOOL_NAME,
            tool_policy=actual_rag_eval.XLSX_LOCATOR_TOOL_POLICY,
            source_atom_id="src-accepted",
            evidence_bundle_id="bundle-accepted",
            doc_id="doc-accepted",
            sheet="2019년 5월",
            cell_range="A9:D12",
            row_label="우이신설선",
            target_column="승차총승객수",
            display_value="15,446,522",
            matched_query_anchors=("2019년", "5월", "우이신설선"),
            missing_query_anchors_after_tool=(),
            matched_validated_required_axes=("period", "row_entity", "target_column", "display_value"),
            missing_validated_required_axes=(),
            confidence_tier="high",
            accepted_for_regating=True,
            rejection_reason="",
        ),
    )
    record = actual_rag_eval.XlsxLocatorRunRecord(
        schema_version=actual_rag_eval.XLSX_LOCATOR_TOOL_EXECUTE_ONCE_SCHEMA_VERSION,
        enabled=True,
        report_only_diagnostic=True,
        official_metric=False,
        tool_name=actual_rag_eval.XLSX_LOCATOR_TOOL_NAME,
        eligible_failed_row_count=2,
        tool_invocation_count=2,
        accepted_candidate_count=1,
        rejected_candidate_count=3,
        gate_delta_record=actual_rag_eval.XlsxLocatorGateDeltaRecord(
            gate_delta={"allowed_answer_count_delta": 1}
        ),
        guardrail_record=actual_rag_eval.XlsxLocatorGuardrailRecord(),
        tool_uses=tool_uses,
        candidates=candidates,
    )

    diagnostic = actual_rag_eval.project_xlsx_locator_run_record(record)[
        "query_anchor_tool_acceptance_diagnostic"
    ]

    assert diagnostic["schema_version"] == "actual_rag_eval.xlsx_locator_query_anchor_tool_acceptance_diagnostic.v1"
    assert diagnostic["report_only_diagnostic"] is True
    assert diagnostic["official_metric"] is False
    assert diagnostic["official_metric_input_rows"] == 0
    assert diagnostic["candidate_count"] == 4
    assert diagnostic["accepted_for_regating_candidate_count"] == 1
    assert diagnostic["missing_query_anchor_after_tool_candidate_count"] == 3
    assert diagnostic["missing_query_anchor_after_tool_item_count"] == 1
    assert diagnostic["query_anchor_rejected_with_complete_axes_candidate_count"] == 1
    assert diagnostic["query_anchor_rejected_with_missing_axes_candidate_count"] == 1
    assert diagnostic["query_anchor_rejected_without_validated_axes_candidate_count"] == 1
    assert diagnostic["source_family_hint_counts"] == {"xlsx": 2}
    assert diagnostic["query_task_counts"] == {"date_filtered_lookup": 2}
    assert diagnostic["gate_flip_direction_counts"] == {
        "block_answer->allow_answer": 1,
        "block_answer->block_answer": 1,
    }
    assert diagnostic["residual_transition_counts"] == {
        "selected_evidence_has_value_missing_axis->no_residual": 1,
        "selected_evidence_has_value_missing_axis->selected_evidence_has_value_missing_axis": 1,
    }
    assert diagnostic["top_missing_query_anchors"] == [
        {"anchor": "명입니까", "candidate_count": 3},
        {"anchor": "5월", "candidate_count": 1},
    ]
    assert diagnostic["source_owned_field_presence_on_query_anchor_rejected_candidates"] == {
        "cell_range": 2,
        "display_value": 2,
        "row_label": 2,
        "source_date_aliases": 0,
        "target_column": 2,
    }
    assert diagnostic["item_summaries"] == [
        {
            "item_index": 0,
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "execution_status": "skipped_missing_source_locator",
            "candidate_count": 3,
            "accepted_candidate_count": 0,
            "missing_query_anchor_after_tool_candidate_count": 3,
            "remaining_missing_query_anchors": ["명입니까"],
            "remaining_missing_validated_required_axes": [],
            "gate_transition": "block_answer->block_answer",
            "residual_transition": (
                "selected_evidence_has_value_missing_axis->"
                "selected_evidence_has_value_missing_axis"
            ),
        },
        {
            "item_index": 1,
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "execution_status": "accepted_after_regating",
            "candidate_count": 1,
            "accepted_candidate_count": 1,
            "missing_query_anchor_after_tool_candidate_count": 0,
            "remaining_missing_query_anchors": [],
            "remaining_missing_validated_required_axes": [],
            "gate_transition": "block_answer->allow_answer",
            "residual_transition": "selected_evidence_has_value_missing_axis->no_residual",
        },
    ]
    assert diagnostic["uses_expected_fields"] is False
    assert diagnostic["uses_gold_fields"] is False
    assert diagnostic["uses_qrels_or_labels"] is False
    assert diagnostic["uses_ids_as_runtime_inputs"] is False
    assert diagnostic["uses_file_workbook_title"] is False
    assert diagnostic["uses_formula_or_normalized_value"] is False
    assert diagnostic["evidence_gate_loosened"] is False
    encoded = json.dumps(diagnostic, ensure_ascii=False)
    assert "src-blocked" not in encoded
    assert "bundle-blocked" not in encoded
    assert "doc-blocked" not in encoded
    assert "xlsx-query-anchor-blocked" not in encoded
    assert "xlsx-query-anchor-accepted" not in encoded


def test_evidence_gate_prefers_validated_required_axes_over_raw_date_anchor() -> None:
    query = "201905 우이신설선 승차총승객수는 몇 명입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"line_name": "우이신설선", "period": "2019-05"},
            "target_axis": {"column": "승차총승객수", "value_type": "number"},
            "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
            "intent_tokens": ["몇 명입니까"],
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2019-05", "2019년 5월", "201905"],
                "row_entity": ["우이신설선"],
                "target_column": ["승차총승객수"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "gate_prefers_validated_axes",
        "query": query,
        "generated_answer": "1,234,567명",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-xlsx-gate-axis",
                "chunk_id": "chunk-xlsx-gate-axis",
                "source_atom_id": "src-xlsx-gate-axis",
                "evidence_bundle_id": "bundle-xlsx-gate-axis",
                "source_family": "XLSX",
                "granularity": "table_row",
                "text": "2019년 5월 우이신설선 승차총승객수",
                "sheet": "2019년 5월",
                "row_label": "우이신설선",
                "target_column": "승차총승객수",
                "display_value": "1,234,567명",
            }
        ],
        "citations": [],
    }

    validation = actual_rag_eval.validate_evidence_package_for_gate(row)

    assert validation["evidence_package_status"] == "sufficient"
    assert validation["matched_validated_required_axes"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert validation["missing_validated_required_axes"] == []
    assert validation["validated_required_axes_coverage"] == 1.0
    assert "missing_query_anchor" not in validation["validation_reasons"]


def test_xlsx_locator_rejects_validated_axes_when_planner_routes_to_pdf() -> None:
    query = "2019년 5월 우이신설선의 승차총승객수는 몇 명입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "pdf",
            "query_task": "date_filtered_lookup",
            "row_filters": {"line_name": "우이신설선", "period": "2019-05"},
            "target_axis": {"column": "승차총승객수", "value_type": "number"},
            "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
            "intent_tokens": ["몇 명입니까"],
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2019-05", "2019년 5월", "201905"],
                "row_entity": ["우이신설선"],
                "target_column": ["승차총승객수"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "xlsx_locator_pdf_route_mismatch",
        "query": query,
        "generated_answer": "1,234,567명",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
    }
    context = {
        "doc_id": "doc-xlsx-route-mismatch",
        "chunk_id": "chunk-xlsx-route-mismatch",
        "source_atom_id": "src-xlsx-route-mismatch",
        "evidence_bundle_id": "bundle-xlsx-route-mismatch",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": "2019년 5월 우이신설선 승차총승객수 1,234,567명",
        "xlsx_locator_text": "2019년 5월 우이신설선 승차총승객수 1,234,567명",
        "sheet": "2019년 5월",
        "cell_range": "A17:J17",
        "row_label": "우이신설선",
        "target_column": "승차총승객수",
        "display_value": "1,234,567명",
    }

    candidate = actual_rag_eval._xlsx_locator_candidate_from_context(row, context)

    assert candidate is not None
    assert candidate["accepted_for_regating"] is False
    assert candidate["rejection_reason"] == "source_family_hint_mismatch"


def test_selected_evidence_composer_keeps_axis_valid_xlsx_locator_candidate() -> None:
    query = "201905 우이신설선 승차총승객수는 몇 명입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"line_name": "우이신설선", "period": "2019-05"},
            "target_axis": {"column": "승차총승객수", "value_type": "number"},
            "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
            "intent_tokens": ["몇 명입니까"],
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2019-05", "2019년 5월", "201905"],
                "row_entity": ["우이신설선"],
                "target_column": ["승차총승객수"],
                "display_value": [],
            },
        },
    )
    context = {
        "doc_id": "doc-xlsx-composer-axis",
        "chunk_id": "chunk-xlsx-composer-axis",
        "source_atom_id": "src-xlsx-composer-axis",
        "evidence_bundle_id": "bundle-xlsx-composer-axis",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": "2019년 5월 우이신설선 승차총승객수 1,234,567명",
        "xlsx_locator_tool_output": True,
        "accepted_for_regating": True,
        "matched_validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
        "missing_validated_required_axes": [],
        "sheet": "2019년 5월",
        "cell_range": "A17:J17",
        "row_label": "우이신설선",
        "target_column": "승차총승객수",
        "display_value": "1,234,567명",
    }

    selected = select_composer_evidence(query, [context], query_evidence_planner=planner)

    assert [row["source_atom_id"] for row in selected] == ["src-xlsx-composer-axis"]
    assert selected[0]["composer_validated_required_axis_hits"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]


def test_selected_evidence_composer_honors_text_source_family_hint() -> None:
    query = "해오름요양원의 기관별 상세주소는 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "text",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"facility_name": "해오름요양원"},
            "target_axis": {"column": "기관별 상세주소", "value_type": "text"},
            "evidence_contract": ["row_entity", "target_column", "display_value"],
            "intent_tokens": ["무엇입니까"],
            "validated_required_axes": ["row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "row_entity": ["해오름요양원"],
                "target_column": ["기관별 상세주소"],
                "display_value": [],
            },
        },
    )
    xlsx_distractor = {
        "doc_id": "doc-xlsx-text-distractor",
        "chunk_id": "chunk-xlsx-text-distractor",
        "source_atom_id": "src-xlsx-text-distractor",
        "evidence_bundle_id": "bundle-xlsx-text-distractor",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": "해오름요양원 기관별 상세주소 대구광역시 수성구 파동로51길 96",
        "sheet": "일반현황",
        "cell_range": "A802:J802",
        "row_label": "해오름요양원",
        "target_column": "기관별 상세주소",
        "display_value": "대구광역시 수성구 파동로51길 96",
    }
    text_context = {
        "doc_id": "doc-text-source",
        "chunk_id": "chunk-text-source",
        "source_atom_id": "src-text-source",
        "evidence_bundle_id": "bundle-text-source",
        "source_family": "TEXT",
        "granularity": "paragraph",
        "text": "해오름요양원의 기관별 상세주소는 대구광역시 수성구 파동로51길 96입니다.",
        "section_title": "기관 현황",
    }

    selected = select_composer_evidence(
        query,
        [xlsx_distractor, text_context],
        max_evidence=1,
        query_evidence_planner=planner,
    )

    assert [row["source_atom_id"] for row in selected] == ["src-text-source"]
    assert selected[0]["composer_source_family_hint"] == "text"


def test_evidence_gate_requires_text_display_value_beyond_query_axes() -> None:
    query = "해오름요양원의 기관별 상세주소는 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "text",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"facility_name": "해오름요양원"},
            "target_axis": {"column": "기관별 상세주소", "value_type": "text"},
            "evidence_contract": ["row_entity", "target_column", "display_value"],
            "intent_tokens": ["무엇입니까"],
            "validated_required_axes": ["row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "row_entity": ["해오름요양원"],
                "target_column": ["기관별 상세주소"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "gate_text_missing_display_value",
        "query": query,
        "generated_answer": "해오름요양원 기관별 상세주소",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-text-no-value",
                "chunk_id": "chunk-text-no-value",
                "source_atom_id": "src-text-no-value",
                "evidence_bundle_id": "bundle-text-no-value",
                "source_family": "TEXT",
                "granularity": "paragraph",
                "text": "해오름요양원 기관별 상세주소",
            }
        ],
        "citations": [],
    }

    validation = validate_evidence_package_for_gate(row)

    assert validation["evidence_package_status"] == "insufficient"
    assert validation["matched_validated_required_axes"] == ["row_entity", "target_column"]
    assert validation["missing_validated_required_axes"] == ["display_value"]
    assert "missing_validated_required_axes" in validation["validation_reasons"]


def test_evidence_gate_accepts_short_text_display_value_beyond_query_axes() -> None:
    query = "해오름요양원의 시도는 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "text",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"facility_name": "해오름요양원"},
            "target_axis": {"column": "시도", "value_type": "text"},
            "evidence_contract": ["row_entity", "target_column", "display_value"],
            "intent_tokens": ["무엇입니까"],
            "validated_required_axes": ["row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "row_entity": ["해오름요양원"],
                "target_column": ["시도"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "gate_text_short_display_value",
        "query": query,
        "generated_answer": "대구",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-text-short-value",
                "chunk_id": "chunk-text-short-value",
                "source_atom_id": "src-text-short-value",
                "evidence_bundle_id": "bundle-text-short-value",
                "source_family": "TEXT",
                "granularity": "paragraph",
                "text": "해오름요양원의 시도는 대구입니다.",
            }
        ],
        "citations": [],
    }

    validation = validate_evidence_package_for_gate(row)

    assert validation["evidence_package_status"] == "sufficient"
    assert validation["matched_validated_required_axes"] == ["row_entity", "target_column", "display_value"]
    assert validation["missing_validated_required_axes"] == []


def test_evidence_gate_rejects_source_family_hint_mismatch_even_when_axes_match() -> None:
    query = "201905 우이신설선 승차총승객수는 몇 명입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "pdf",
            "query_task": "date_filtered_lookup",
            "row_filters": {"line_name": "우이신설선", "period": "2019-05"},
            "target_axis": {"column": "승차총승객수", "value_type": "number"},
            "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
            "intent_tokens": ["몇 명입니까"],
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2019-05", "2019년 5월", "201905"],
                "row_entity": ["우이신설선"],
                "target_column": ["승차총승객수"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "gate_rejects_source_family_mismatch",
        "query": query,
        "generated_answer": "1,234,567명",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-text-wrong-family",
                "chunk_id": "chunk-text-wrong-family",
                "source_atom_id": "src-text-wrong-family",
                "evidence_bundle_id": "bundle-text-wrong-family",
                "source_family": "TEXT",
                "granularity": "paragraph",
                "text": "2019년 5월 우이신설선 승차총승객수는 1,234,567명입니다.",
                "section_title": "도시철도 통계",
            }
        ],
        "citations": [],
    }

    validation = validate_evidence_package_for_gate(row)

    assert validation["evidence_package_status"] == "insufficient"
    assert validation["source_family_hint"] == "pdf"
    assert validation["source_family_hint_matched_evidence_count"] == 0
    assert "source_family_hint_mismatch" in validation["validation_reasons"]


def test_evidence_gate_ignores_wrong_family_evidence_when_matching_family_is_incomplete() -> None:
    query = "201905 우이신설선 승차총승객수는 몇 명입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "pdf",
            "query_task": "date_filtered_lookup",
            "row_filters": {"line_name": "우이신설선", "period": "2019-05"},
            "target_axis": {"column": "승차총승객수", "value_type": "number"},
            "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
            "intent_tokens": ["몇 명입니까"],
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2019-05", "2019년 5월", "201905"],
                "row_entity": ["우이신설선"],
                "target_column": ["승차총승객수"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "gate_ignores_wrong_family",
        "query": query,
        "generated_answer": "1,234,567명",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-text-wrong-family-with-value",
                "chunk_id": "chunk-text-wrong-family-with-value",
                "source_atom_id": "src-text-wrong-family-with-value",
                "evidence_bundle_id": "bundle-text-wrong-family-with-value",
                "source_family": "TEXT",
                "granularity": "paragraph",
                "text": "2019년 5월 우이신설선 승차총승객수는 1,234,567명입니다.",
                "section_title": "도시철도 통계",
            },
            {
                "doc_id": "doc-pdf-matching-family-no-value",
                "chunk_id": "chunk-pdf-matching-family-no-value",
                "source_atom_id": "src-pdf-matching-family-no-value",
                "evidence_bundle_id": "bundle-pdf-matching-family-no-value",
                "source_family": "PDF",
                "granularity": "page_block",
                "text": "2019년 5월 승차총승객수는 1,234,567명입니다.",
                "page_number": "3",
                "block_index": "7",
                "table_caption": "도시철도 월별 승하차 통계",
            },
        ],
        "citations": [],
    }

    validation = validate_evidence_package_for_gate(row)

    assert validation["evidence_package_status"] == "insufficient"
    assert validation["source_family_hint"] == "pdf"
    assert validation["source_family_hint_matched_evidence_count"] == 1
    assert validation["missing_validated_required_axes"] == ["row_entity"]
    assert "missing_validated_required_axes" in validation["validation_reasons"]


def test_xlsx_locator_runstore_records_llm_anchor_classifier_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = tmp_path / "xlsx_locator_anchor_classifier_gold.jsonl"
    context = tmp_path / "xlsx_locator_anchor_classifier_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_locator_anchor_classifier"
    table_text = (
        "sheet=일반현황 | range=A802:J851 | 장기요양기관이름 | 우편번호 | 시도코드 | "
        "시군구코드 | 법정동코드 | 시도 시군구 법정동명 | 지정일자 | 설치신고일자 | "
        "기관별 상세주소 12726000180 | 해오름요양원 | 42222 | 27 | 260 | 110 | "
        "대구광역시 수성구 파동 | 2012-03-06 | 2012-03-06 | "
        "대구광역시 수성구 파동로51길 96 (파동)"
    )
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx_locator_anchor_classifier_q",
                "query": "2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 무엇입니까?",
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "xlsx_locator_anchor_classifier_q",
                "generated_answer": "대구광역시 수성구 파동로51길 96 (파동)",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-xlsx-anchor-classifier",
                        "chunk_id": "chunk-anchor-classifier",
                        "source_atom_id": "src-xlsx-anchor-classifier",
                        "evidence_bundle_id": "bundle-xlsx-anchor-classifier",
                        "source_family": "XLSX",
                        "granularity": "table_range",
                        "text": table_text,
                        "sheet": "일반현황",
                        "cell_range": "A802:J851",
                    }
                ],
                "citations": [],
            }
        ],
    )

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**kwargs: object) -> tuple[dict, dict]:
        prompt = str(kwargs["prompt"])
        assert "xlsx_locator_anchor_classifier_q" not in prompt
        assert "answerability" not in prompt
        assert "expected_answer" not in prompt
        assert "qrels" not in prompt
        return (
            {
                "intent_tokens": ["무엇입니까", "지정된"],
                "numeric_or_date_anchors": ["2012년", "3월"],
                "entity_anchors": ["해오름요양원"],
                "measure_anchors": ["기관별", "상세주소"],
            },
            {"raw_response_sha256": "sha256:classifier-runstore"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="xlsx_locator_anchor_classifier",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        xlsx_locator_tool_execute_once=True,
        llm_query_anchor_classifier=True,
        local_llm_composer_model="gemma4-e2b-local",
        local_llm_composer_timeout_seconds=7,
        skip_local_llm_composer_endpoint_check=True,
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    locator = report["xlsx_locator_tool_execute_once"]
    assert locator["anchor_classifier_model"] == "gemma4-e2b-local"
    assert locator["anchor_classifier_prompt_version"] == "llm_query_anchor_classifier_v1"
    assert locator["anchor_classifier_raw_payload_written"] is False
    assert locator["required_anchor_summary"]["before"]["anchor_count"] == 7
    assert locator["required_anchor_summary"]["after"]["anchor_count"] == 5
    assert locator["required_anchor_summary"]["removed_intent_tokens"] == ["무엇입니까", "지정된"]
    assert report["items"][0]["query_anchor_classifier"]["required_anchor_after"] == [
        "2012년",
        "3월",
        "기관별",
        "상세주소",
        "해오름요양원",
    ]
    with sqlite3.connect(output_dir / "run.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute(
            "SELECT anchor_classifier_model, anchor_classifier_prompt_version, "
            "anchor_classifier_raw_payload_written, required_anchor_summary_json FROM runs"
        ).fetchone()
        assert run["anchor_classifier_model"] == "gemma4-e2b-local"
        assert run["anchor_classifier_prompt_version"] == "llm_query_anchor_classifier_v1"
        assert run["anchor_classifier_raw_payload_written"] == 0
        summary = json.loads(run["required_anchor_summary_json"])
        assert summary["after"]["anchors"] == ["2012년", "3월", "기관별", "상세주소", "해오름요양원"]


def test_xlsx_locator_tool_execute_once_rejects_table_row_adjacent_date_only(tmp_path: Path) -> None:
    dataset = tmp_path / "xlsx_locator_tool_adjacent_date_gold.jsonl"
    context = tmp_path / "xlsx_locator_tool_adjacent_date_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_locator_tool_adjacent_date"
    table_text = (
        "sheet=일반현황 | range=A802:J851 | 장기요양기관이름 | 우편번호 | 시도코드 | "
        "시군구코드 | 법정동코드 | 시도 시군구 법정동명 | 지정일자 | 설치신고일자 | "
        "기관별 상세주소 12726000180 | 해오름요양원 | 42222 | 27 | 260 | 110 | "
        "대구광역시 수성구 파동 | 2010-01-01 | 2010-01-01 | "
        "대구광역시 수성구 파동로51길 96 (파동) 12726000192 | 어르신노인요양시설 | "
        "42216 | 27 | 260 | 111 | 대구광역시 수성구 두산동 | 2012-03-06 | "
        "2012-03-06 | 대구광역시 수성구 용학로25길 6 4층"
    )
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx_locator_adjacent_date_q",
                "query": "2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 무엇입니까?",
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "xlsx_locator_adjacent_date_q",
                "generated_answer": "대구광역시 수성구 파동로51길 96 (파동)",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-xlsx-locator-table",
                        "chunk_id": "chunk-table-range",
                        "source_atom_id": "src-xlsx-locator-table",
                        "evidence_bundle_id": "bundle-xlsx-locator-table",
                        "source_family": "XLSX",
                        "granularity": "table_range",
                        "text": table_text,
                        "sheet": "일반현황",
                        "cell_range": "A802:J851",
                    }
                ],
                "citations": [],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="xlsx_locator_tool_adjacent_date",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        xlsx_locator_tool_execute_once=True,
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    locator = report["xlsx_locator_tool_execute_once"]

    assert report["evidence_gate"]["allowed_answer_count"] == 0
    assert locator["accepted_candidate_count"] == 0
    assert locator["gate_delta"]["allowed_answer_count_delta"] == 0
    assert report["items"][0]["xlsx_locator_tool_use"]["execution_status"] == "skipped_missing_source_locator"
    with sqlite3.connect(output_dir / "run.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        candidates = conn.execute(
            "SELECT locator_text_source, accepted_for_regating, rejection_reason, missing_query_anchors_after_tool_json "
            "FROM tool_candidates"
        ).fetchall()
        assert candidates
        assert all(candidate["accepted_for_regating"] == 0 for candidate in candidates)
        assert "source_owned_table_row_text" not in {
            candidate["locator_text_source"]
            for candidate in candidates
            if candidate["accepted_for_regating"] == 1
        }
        missing_anchors = {
            anchor
            for candidate in candidates
            for anchor in json.loads(candidate["missing_query_anchors_after_tool_json"])
        }
        assert {"2012년", "3월"}.issubset(missing_anchors)


def test_xlsx_locator_tool_execute_once_rejects_forbidden_locator_shortcuts(tmp_path: Path) -> None:
    dataset = tmp_path / "xlsx_locator_tool_poison_gold.jsonl"
    context = tmp_path / "xlsx_locator_tool_poison_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_locator_tool_poison"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx_locator_poison_q",
                "query": "2019년 2월 5호선 승차총승객수는 얼마야?",
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "xlsx_locator_poison_q",
                "generated_answer": "15,446,523명",
                "retrieved_contexts": [
                        {
                            "doc_id": "doc-xlsx-locator",
                            "chunk_id": "chunk-poison",
                            "source_atom_id": "src-xlsx-locator",
                            "evidence_bundle_id": "bundle-xlsx-locator",
                            "source_family": "XLSX",
                            "granularity": "table_row",
                            "text": "승차총승객수",
                            "locator_text_source": "explicit_locator_text",
                            "locator_text_fields_used": ["xlsx_locator_text"],
                            "xlsx_locator_text": (
                                "2019년 2월 5호선 승차총승객수 15,446,522명 "
                            "normalizedValue=15446522 formula=SUM(F7) workbook=metro.xlsx "
                            "sourceTitle=shortcut title=shortcut sourceFileName=C:\\tmp\\metro.xlsx "
                            "targetLocator=F7 goldLocator=F7 queryId=x caseId=y "
                            "baselineTopK=1 expectedAnswer=15446522 "
                            "rawPromptPayload={} rawResponsePayload={}"
                        ),
                        "xlsx_locator_metadata": {
                            "sheet": "2019년 2월",
                            "cell_range": "A7:J7",
                            "cell": "F7",
                            "row_index_1based": "7",
                            "row_label": "5호선",
                            "column_label": "승차총승객수",
                            "target_column": "승차총승객수",
                            "header_path": "승하차 > 승차총승객수",
                            "table_id": "sheet-201902-main-table",
                            "normalizedValue": "15446522",
                            "sourceFileName": "metro.xlsx",
                            "rawPromptPayload": {},
                            "expectedAnswer": "15446522",
                            "baselineTopK": 1,
                        },
                    }
                ],
                "citations": [],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="xlsx_locator_tool_poison",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
        resolve_expected_evidence=False,
        xlsx_locator_tool_execute_once=True,
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    locator = report["xlsx_locator_tool_execute_once"]
    row = report["items"][0]
    tool_use = row["xlsx_locator_tool_use"]

    assert report["evidence_gate"]["allowed_answer_count"] == 0
    assert report["evidence_gate"]["unsupported_answer_blocked_count"] == 1
    assert locator["eligible_failed_row_count"] == 1
    assert locator["tool_invocation_count"] == 1
    assert locator["accepted_candidate_count"] == 0
    assert locator["rejected_candidate_count"] == 1
    assert locator["tool_execution_status_counts"] == {"skipped_missing_source_locator": 1}
    assert locator["candidate_confidence_tier_counts"] == {"high": 1}
    assert locator["candidate_rejection_reason_counts"] == {"forbidden_input_fields_present": 1}
    assert locator["candidate_source_family_counts"] == {"XLSX": 1}
    assert locator["forbidden_input_fields_used"] == []
    assert set(locator["forbidden_input_fields_rejected"]) >= {"expected_answer", "baseline_topk", "raw_prompt_payload"}
    assert not (
        set(locator["forbidden_input_fields_rejected"])
        & {"file_name", "source_file_name", "source_title", "title", "workbook"}
    )
    assert locator["raw_xlsx_query_time_parsing_used"] is False
    assert locator["gold_or_qrels_or_label_or_expected_used"] is False
    assert set(locator["forbidden_input_fields_seen"]) >= {
        "case_id",
        "baseline_topk",
        "expected_answer",
        "file_name",
        "formula",
        "gold_locator",
        "normalized_value",
        "query_id",
        "raw_prompt_payload",
        "raw_response_payload",
        "source_file_name",
        "source_title",
        "target_locator",
        "title",
        "workbook",
    }
    assert tool_use["execution_status"] == "skipped_missing_source_locator"
    assert tool_use["candidate_count"] == 1
    assert tool_use["accepted_candidate_count"] == 0
    assert output_file_names(output_dir) == ["report.json", "run.sqlite"]

    with sqlite3.connect(output_dir / "run.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        candidate = conn.execute(
            "SELECT accepted_for_regating, rejection_reason, matched_query_anchors_json FROM tool_candidates"
        ).fetchone()
        assert candidate["accepted_for_regating"] == 0
        assert candidate["rejection_reason"] == "forbidden_input_fields_present"
        assert set(json.loads(candidate["matched_query_anchors_json"])) >= {
            "2019년",
            "2월",
            "5호선",
            "승차총승객수",
        }
        invocation = conn.execute(
            "SELECT execution_status, candidate_count, accepted_candidate_count FROM tool_invocations"
        ).fetchone()
        assert dict(invocation) == {
            "execution_status": "skipped_missing_source_locator",
            "candidate_count": 1,
            "accepted_candidate_count": 0,
        }


def test_agentic_planner_execute_once_defers_llm_retry_without_execution_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NoRetrievalAdapter:
        def __init__(self) -> None:
            self.query_log: list[dict[str, object]] = []

        def run_item(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            self.query_log.append({"unexpected": True})
            raise AssertionError("LLM retry must not execute retrieval")

    selected_context = {
        "doc_id": "doc-hq",
        "chunk_id": "chunk-hq",
        "source_atom_id": "src-hq",
        "evidence_bundle_id": "bundle-hq",
        "source_family": "TEXT",
        "granularity": "paragraph",
        "text": "Apollo HQ is in Seoul.",
        "text_sha256": "hash-hq",
    }
    gated_row = {
        "id": "q-local-retry",
        "query": "Where is Apollo HQ?",
        "answerability": "unknown",
        "generated_answer": actual_rag_eval.BOUNDED_EVIDENCE_ABSTENTION_ANSWER,
        actual_rag_eval.INTERNAL_PRE_GATE_ANSWER_KEY: "Apollo HQ is in Busan.",
        "retrieved_contexts": [dict(selected_context)],
        "citations": [dict(selected_context)],
        "answer_gate_decision": "block_unsupported_answer",
        "answer_modified_by_gate": True,
        "unsupported_answer_blocked": True,
        "evidence_gate": {
            "evidence_package_status": "sufficient",
            "answer_gate_decision": "block_unsupported_answer",
            "unsupported_answer_blocked": True,
            "abstention_reason": "citation_unsupported",
            "validation_reasons": ["citation_unsupported"],
            "unsupported_answer_reasons": ["citation_unsupported"],
            "selected_evidence": [dict(selected_context)],
            "missing_query_anchors": [],
            "citation_retrieved_context_only_diagnostic_count": 0,
        },
    }
    captured_prompts: list[str] = []

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**kwargs: object) -> tuple[dict, dict]:
        prompt = str(kwargs["prompt"])
        captured_prompts.append(prompt)
        return (
            {
                "answer": "Apollo HQ is in Seoul.",
                "citation_evidence_ids": ["bundle-hq"],
            },
            {
                "raw_response_sha256": "sha256:planner-retry-response",
                "strict_json": True,
            },
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    updated_rows, planner = actual_rag_eval.apply_agentic_planner_execute_once_to_outputs(
        [gated_row],
        adapter=NoRetrievalAdapter(),
        top_k=1,
        evidence_gate_mode="enforce",
        citation_format="evidence-id",
        skip_local_llm_endpoint_check=True,
    )

    updated = updated_rows[0]
    decision = planner["decisions"][0]
    actual_rag_eval.validate_agentic_planner_execute_once("planner_llm_retry", planner)
    assert captured_prompts == []
    assert planner["planner_action_counts"] == {"selected_evidence_llm_rewrite": 1}
    assert planner["planner_failure_class_counts"] == {"unsupported_generation": 1}
    assert planner["planner_expected_llm_retry_count"] == 1
    assert planner["planner_execution"] == {
        "retrieval_executed": False,
        "tool_call_executed": False,
        "llm_retry_executed": False,
        "extra_query_count_executed": 0,
        "tool_call_count_executed": 0,
        "llm_retry_count_executed": 0,
    }
    assert planner["gate_delta"]["allowed_answer_count_delta"] == 0
    assert planner["guardrail_mutation_flags"]["gate_loosened"] is False
    assert planner["guardrail_mutation_flags"]["retrieved_context_only_citation_promoted"] is False
    assert decision["executed"] is False
    assert decision["proposed_action"] == "selected_evidence_llm_rewrite"
    assert decision["execution_status"] == "deferred_requires_explicit_execution_gate"
    assert decision["expected_llm_retry_count"] == 1
    assert decision["llm_retry_count_executed"] == 0
    assert decision["execution_gate_required"] is True
    assert "query_id" not in decision
    assert "expected_answer" not in decision
    assert updated["generated_answer"] == actual_rag_eval.BOUNDED_EVIDENCE_ABSTENTION_ANSWER
    assert updated["answer_gate_decision"] == "block_unsupported_answer"
    assert updated["evidence_gate"]["citation_retrieved_context_only_diagnostic_count"] == 0
    assert "agentic_planner_llm_retry" not in updated


def test_agentic_planner_execute_once_defers_run_local_selected_evidence_memory_without_execution_gate() -> None:
    class NoRetrievalAdapter:
        def __init__(self) -> None:
            self.query_log: list[dict[str, object]] = []

        def run_item(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            self.query_log.append({"unexpected": True})
            raise AssertionError("run-local memory must not execute retrieval")

    adapter = NoRetrievalAdapter()
    memory_context = {
        "doc_id": "doc-hq",
        "chunk_id": "chunk-hq",
        "source_atom_id": "src-hq",
        "evidence_bundle_id": "bundle-hq",
        "source_family": "TEXT",
        "granularity": "paragraph",
        "text": "Apollo HQ is in Seoul.",
        "text_sha256": "hash-hq",
    }
    allowed_memory_source = {
        "id": "memory-source-row-id-must-not-be-used",
        "query": "Apollo HQ location",
        "answerability": "unknown",
        "generated_answer": "**Short answer:** Apollo HQ is in Seoul.",
        "retrieved_contexts": [dict(memory_context)],
        "citations": [dict(memory_context)],
        "answer_gate_decision": "allow_answer",
        "answer_modified_by_gate": False,
        "unsupported_answer_blocked": False,
        "evidence_gate": {
            "evidence_package_status": "sufficient",
            "answer_gate_decision": "allow_answer",
            "unsupported_answer_blocked": False,
            "selected_evidence": [dict(memory_context)],
            "validation_reasons": [],
            "citation_supported_count": 1,
            "citation_retrieved_context_only_diagnostic_count": 0,
        },
    }
    failed_target = {
        "id": "memory-target-row-id-must-not-be-used",
        "query": "Where is Apollo HQ?",
        "answerability": "unknown",
        "generated_answer": actual_rag_eval.BOUNDED_EVIDENCE_ABSTENTION_ANSWER,
        "retrieved_contexts": [],
        "citations": [],
        "answer_gate_decision": "block_unsupported_answer",
        "answer_modified_by_gate": True,
        "unsupported_answer_blocked": True,
        "evidence_gate": {
            "evidence_package_status": "insufficient",
            "answer_gate_decision": "block_unsupported_answer",
            "unsupported_answer_blocked": True,
            "abstention_reason": "insufficient_evidence",
            "validation_reasons": ["no_selected_evidence"],
            "selected_evidence": [],
            "citation_retrieved_context_only_diagnostic_count": 0,
        },
    }

    updated_rows, planner = actual_rag_eval.apply_agentic_planner_execute_once_to_outputs(
        [allowed_memory_source, failed_target],
        adapter=adapter,
        top_k=1,
        evidence_gate_mode="enforce",
        citation_format="evidence-id",
    )

    decision = planner["decisions"][0]
    updated = updated_rows[1]
    actual_rag_eval.validate_agentic_planner_execute_once("planner_run_local_memory", planner)
    assert adapter.query_log == []
    assert planner["planner_action_counts"] == {"run_local_memory_reuse": 1}
    assert planner["planner_failure_class_counts"] == {"insufficient_evidence": 1}
    assert planner["planner_expected_memory_lookup_count"] == 1
    assert planner["planner_memory_lookup_count_executed"] == 0
    assert planner["planner_execution"] == {
        "retrieval_executed": False,
        "tool_call_executed": False,
        "llm_retry_executed": False,
        "extra_query_count_executed": 0,
        "tool_call_count_executed": 0,
        "llm_retry_count_executed": 0,
    }
    assert planner["gate_before"]["allowed_answer_count"] == 1
    assert planner["gate_after"]["allowed_answer_count"] == 1
    assert planner["gate_delta"]["allowed_answer_count_delta"] == 0
    assert planner["gate_delta"]["unsupported_answer_blocked_count_delta"] == 0
    assert decision["executed"] is False
    assert decision["proposed_action"] == "run_local_memory_reuse"
    assert decision["execution_status"] == "deferred_requires_explicit_execution_gate"
    assert decision["memory_lookup_count_executed"] == 0
    assert decision["execution_gate_required"] is True
    assert "query_id" not in decision
    assert "row_id" not in decision
    assert "target_id" not in decision
    assert "expected_answer" not in decision
    assert updated["generated_answer"] == actual_rag_eval.BOUNDED_EVIDENCE_ABSTENTION_ANSWER
    assert updated["answer_gate_decision"] == "block_unsupported_answer"
    assert updated["evidence_gate"]["citation_retrieved_context_only_diagnostic_count"] == 0
    assert "agentic_planner_run_local_memory" not in updated


def test_agentic_planner_dry_run_does_not_reuse_memory_when_missing_anchor_is_uncovered() -> None:
    memory_context = {
        "doc_id": "doc-hq",
        "chunk_id": "chunk-hq",
        "source_atom_id": "src-hq",
        "evidence_bundle_id": "bundle-hq",
        "source_family": "TEXT",
        "granularity": "paragraph",
        "text": "Apollo HQ is in Seoul.",
        "text_sha256": "hash-hq",
    }
    allowed_memory_source = {
        "id": "memory-source-row-id-must-not-be-used",
        "query": "Apollo HQ location",
        "answerability": "unknown",
        "generated_answer": "**Short answer:** Apollo HQ is in Seoul.",
        "retrieved_contexts": [dict(memory_context)],
        "citations": [dict(memory_context)],
        "answer_gate_decision": "allow_answer",
        "evidence_gate": {
            "evidence_package_status": "sufficient",
            "answer_gate_decision": "allow_answer",
            "selected_evidence": [dict(memory_context)],
            "validation_reasons": [],
            "citation_supported_count": 1,
            "citation_retrieved_context_only_diagnostic_count": 0,
        },
    }
    failed_target = {
        "id": "memory-target-row-id-must-not-be-used",
        "query": "Where is Apollo HQ Atlas?",
        "answerability": "unknown",
        "generated_answer": actual_rag_eval.BOUNDED_EVIDENCE_ABSTENTION_ANSWER,
        "retrieved_contexts": [],
        "citations": [],
        "answer_gate_decision": "block_unsupported_answer",
        "evidence_gate": {
            "evidence_package_status": "insufficient",
            "answer_gate_decision": "block_unsupported_answer",
            "abstention_reason": "missing_query_anchor",
            "validation_reasons": ["missing_query_anchor"],
            "missing_query_anchors": ["Atlas"],
            "selected_evidence": [],
            "citation_retrieved_context_only_diagnostic_count": 0,
        },
    }
    summary = {
        "run_id": "agentic_planner_memory_anchor_guard",
        "items": [allowed_memory_source, failed_target],
        "generator_config": {"selected_evidence_composer_invoked": True},
        "evidence_gate": {"evidence_gate_mode": "enforce"},
    }

    planner = actual_rag_eval.build_agentic_planner_dry_run_report(summary, mode="dry-run")

    decision = planner["decisions"][0]
    assert decision["proposed_action"] == "query_text_only_reformulation"
    assert decision["expected_memory_lookup_count"] == 0
    assert planner["planner_action_counts"] == {"query_text_only_reformulation": 1}
    assert planner["planner_expected_memory_lookup_count"] == 0


def test_agentic_planner_mode_parser_default_and_choices() -> None:
    parser = build_parser()
    assert parser.parse_args(["--dataset", "gold.jsonl"]).agentic_planner_mode == "off"
    assert (
        parser.parse_args(["--dataset", "gold.jsonl", "--agentic-planner-mode", "dry-run"]).agentic_planner_mode
        == "dry-run"
    )
    assert (
        parser.parse_args(["--dataset", "gold.jsonl", "--agentic-planner-mode", "execute-once"]).agentic_planner_mode
        == "execute-once"
    )
    assert parser.parse_args(["--dataset", "gold.jsonl", "--xlsx-locator-tool-execute-once"]).xlsx_locator_tool_execute_once
    assert parser.parse_args(["--dataset", "gold.jsonl", "--output-mode", "runstore"]).output_mode == "runstore"
    with pytest.raises(SystemExit):
        parser.parse_args(["--dataset", "gold.jsonl", "--agentic-planner-mode", "execute-twice"])

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


def test_source_native_corpus_loader_keeps_source_date_aliases_in_xlsx_row_value_bundle_text(
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


def test_schema_validation_preserves_partial_gold_without_promoting_to_headline(tmp_path: Path) -> None:
    dataset = tmp_path / "partial_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "Where did Mitsuha go?",
                "answerability": "answerable",
                "expected_answer": "Tokyo",
                "expected_answer_aliases": ["도쿄"],
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Tokyo", "required": True}],
            },
            {"id": "q2", "query": "Missing label is allowed as diagnostic partial gold."},
        ],
    )

    items = load_eval_dataset(dataset)

    assert [item.id for item in items] == ["q1", "q2"]
    assert items[1].answerability == "unknown"
    assert "missing_answerability_label" in items[1].validation_warnings
    assert "missing_expected_answer" in items[1].validation_warnings
    assert "missing_expected_evidence" in items[1].validation_warnings
    assert items[1].expected_evidence == ()


def test_schema_validation_fails_clearly_for_invalid_evidence_shape(tmp_path: Path) -> None:
    dataset = tmp_path / "bad_gold.jsonl"
    write_jsonl(
        dataset,
        [{"id": "q1", "query": "bad", "answerability": "answerable", "expected_evidence": "not-a-list"}],
    )

    with pytest.raises(DatasetSchemaError, match=r"q1.*expected_evidence must be a list"):
        load_eval_dataset(dataset)


def test_existing_csv_golden_shape_loads_with_warnings_not_conversion_work(tmp_path: Path) -> None:
    dataset = tmp_path / "gold.csv"
    dataset.write_text(
        "\n".join(
            [
                "query_id,question,expected_answer,supporting_evidence,citation_locator,user_answerability_label",
                'csv_1,Where?,Seoul,Seoul is the capital.,"{""file"": ""doc-a"", ""search_unit_id"": ""c1""}",ANSWERABLE_CONFIRMED',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    items = load_eval_dataset(dataset)

    assert items[0].id == "csv_1"
    assert items[0].query == "Where?"
    assert items[0].answerability == "answerable"
    assert items[0].expected_answer == "Seoul"
    assert items[0].expected_evidence[0].doc_id == "doc-a"
    assert items[0].expected_evidence[0].chunk_id == "c1"
    assert items[0].expected_evidence[0].text == "Seoul is the capital."
    assert "missing_expected_answer_aliases" in items[0].validation_warnings


def test_answer_normalization_aliases_and_abstention_detector() -> None:
    assert normalize_answer_text("  Seoul, Korea!  ") == "seoul korea"
    assert answer_correct("서울입니다.", expected_answer="Seoul", aliases=["서울입니다"])
    assert not answer_correct("Busan", expected_answer="Seoul", aliases=["서울"])
    assert abstains("문서에서 찾을 수 없습니다. 제공된 context에 답이 없습니다.")
    assert abstains("The answer is not available from the provided context.")
    assert not abstains("The answer is Seoul.")


def test_provisional_heuristic_judge_marks_semantic_contains_without_replacing_strict() -> None:
    result = heuristic_judge_answer(
        generated_answer="The answer is Seoul, based on the provided context.",
        expected_answer="Seoul",
        aliases=[],
        expected_evidence_texts=[],
        retrieved_context_texts=["Seoul is the capital city."],
        notes="",
    )

    assert result["judge_version"] == "heuristic_overlap_v1"
    assert result["provisional"] is True
    assert result["passed"] is True
    assert result["reason"] == "expected_answer_contained_in_generated_answer"
    assert answer_correct(
        "The answer is Seoul, based on the provided context.",
        expected_answer="Seoul",
        aliases=[],
    ) is False


def test_score_accepts_deterministic_fake_judge_adapter_without_model_calls(tmp_path: Path) -> None:
    class DeterministicFakeJudge:
        config = {
            "enabled": True,
            "tier": "provisional",
            "judge_kind": "deterministic_test_fake",
            "judge_version": "test_fake_v1",
            "threshold": 1.0,
            "prompt": "test fixture only",
            "external_api_calls": False,
        }

        def evaluate(self, *, item, generated_answer, retrieved_context_texts, expected_evidence_texts):
            return {
                "passed": item.id == "semantic",
                "available": True,
                "provisional": True,
                "judge_kind": "deterministic_test_fake",
                "judge_version": "test_fake_v1",
                "reason": "fixture",
            }

    dataset = tmp_path / "semantic_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "semantic",
                "query": "semantic answer?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul is the capital.", "required": True}],
            }
        ],
    )
    items = load_eval_dataset(dataset)
    outputs = [
        {
            "id": "semantic",
            "query": "semantic answer?",
            "answerability": "answerable",
            "generated_answer": "The capital city is Seoul.",
            "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul is the capital."}],
            "citations": [],
            "expected_answer": "Seoul",
            "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul is the capital.", "required": True}],
            "metric_inputs_available": {
                "has_expected_answer": True,
                "has_expected_evidence": True,
                "has_answerability_label": True,
                "has_citations": False,
            },
            "diagnostics": {},
        }
    ]

    summary, _rows = score_rag_eval_items(
        items,
        outputs,
        top_k_values=[1],
        judge_adapter=DeterministicFakeJudge(),
    )

    assert summary["judge_config"]["judge_kind"] == "deterministic_test_fake"
    assert summary["provisional_metrics"]["judged_answer_correctness_provisional"]["denominator"] == 1
    assert summary["provisional_metrics"]["judged_answer_correctness_provisional"]["numerator"] == 1
    assert summary["judge_config"]["external_api_calls"] is False
    assert "prompt" not in summary["judge_config"]
    assert summary["judge_config"]["prompt_sha256"]


def test_public_report_row_strips_raw_prompt_response_payloads_recursively() -> None:
    public = _public_report_row(
        {
            "id": "row-1",
            "generated_answer": "answer",
            "raw_prompt_payload": {"messages": ["secret prompt"]},
            "raw_response_payload": {"choices": ["secret response"]},
            "rawPromptPayload": {"messages": ["secret camel prompt"]},
            "raw_response_sha256": "abc123",
            "diagnostics": {
                "raw_prompt": "secret prompt",
                "rawPromptText": "secret camel raw prompt",
                "rawResponseText": "secret camel raw response",
                "llmPrompt": "secret llm prompt",
                "llmResponse": "secret llm response",
                "model_response_payload": {"text": "secret response"},
                "responseText": "secret bare response",
                "raw_response_sha256": "def456",
                "safe": [{"prompt_payload": "secret prompt"}, {"kept": True}],
            },
            "_generated_answer_before_evidence_gate": "internal answer",
        }
    )

    encoded = json.dumps(public, ensure_ascii=False)
    assert "raw_prompt_payload" not in encoded
    assert "raw_response_payload" not in encoded
    assert "secret prompt" not in encoded
    assert "secret response" not in encoded
    assert "secret camel" not in encoded
    assert "secret llm" not in encoded
    assert "secret bare response" not in encoded
    assert "_generated_answer_before_evidence_gate" not in public
    assert public["raw_response_sha256"] == "abc123"
    assert public["diagnostics"]["raw_response_sha256"] == "def456"
    assert public["diagnostics"]["safe"] == [{}, {"kept": True}]


def test_e2e_provisional_fails_when_judge_fails_despite_generic_overlap(tmp_path: Path) -> None:
    dataset = tmp_path / "generic_overlap_false_positive.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "anime_wrong_entity",
                "query": "자동판매기 미궁 방랑 애니 3기 감독과 방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "야마모토 타카시, 2026년 4월",
                "expected_evidence": [
                    {
                        "doc_id": "doc-expected",
                        "chunk_id": "chunk-expected",
                        "text": "일본 라이트 노벨 자동판매기로 다시 태어난 나는 미궁을 방랑한다 원작 TV 애니메이션 제3기 감독 야마모토 타카시 방영 시기는 2026년 4월",
                        "required": True,
                    }
                ],
            }
        ],
    )
    outputs = [
        {
            "id": "anime_wrong_entity",
            "query": "자동판매기 미궁 방랑 애니 3기 감독과 방영 시기는?",
            "answerability": "answerable",
            "generated_answer": "감독은 나베시마 오사무, 방영 시기는 2006년 10월입니다.",
            "retrieved_contexts": [
                {
                    "rank": 1,
                    "doc_id": "doc-other",
                    "chunk_id": "chunk-other",
                    "score": 0.9,
                    "text": "일본 만화 D.Gray-man 원작 TV 애니메이션 제3기 감독 나베시마 오사무 방영 시기는 2006년 10월",
                }
            ],
            "citations": [],
            "expected_answer": "야마모토 타카시, 2026년 4월",
            "expected_evidence": [],
            "metric_inputs_available": {
                "has_expected_answer": True,
                "has_expected_evidence": True,
                "has_answerability_label": True,
                "has_citations": False,
            },
            "diagnostics": {},
        }
    ]

    items = load_eval_dataset(dataset)
    summary, rows = score_rag_eval_items(items, outputs, top_k_values=[1])
    row = rows[0]

    assert row["metric_results"]["judged_answer_correctness_provisional"]["passed"] is False
    assert row["metric_results"]["weak_evidence_match_recall@1"] is False
    assert row["metric_results"]["e2e_rag_success_provisional"] is False
    assert summary["provisional_metrics"]["e2e_rag_success_provisional"]["numerator"] == 0


def test_anchor_based_weak_evidence_positive_case_without_id_match(tmp_path: Path) -> None:
    dataset = tmp_path / "anchor_positive.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "anchor_positive",
                "query": "자동판매기 3기 감독은?",
                "answerability": "answerable",
                "expected_answer": "야마모토 타카시",
                "expected_evidence": [
                    {
                        "doc_id": "doc-expected",
                        "chunk_id": "chunk-expected",
                        "text": "자동판매기 미궁 방랑 애니메이션 제3기 감독 야마모토 타카시",
                        "required": True,
                    }
                ],
            }
        ],
    )
    outputs = [
        {
            "id": "anchor_positive",
            "query": "자동판매기 3기 감독은?",
            "answerability": "answerable",
            "generated_answer": "야마모토 타카시",
            "retrieved_contexts": [
                {
                    "rank": 1,
                    "doc_id": "doc-other",
                    "chunk_id": "chunk-other",
                    "score": 0.8,
                    "text": "자동판매기 미궁 방랑 애니메이션 제3기 감독 야마모토 타카시",
                }
            ],
            "citations": [],
            "expected_answer": "야마모토 타카시",
            "expected_evidence": [],
            "metric_inputs_available": {
                "has_expected_answer": True,
                "has_expected_evidence": True,
                "has_answerability_label": True,
                "has_citations": False,
            },
            "diagnostics": {},
        }
    ]

    items = load_eval_dataset(dataset)
    _summary, rows = score_rag_eval_items(items, outputs, top_k_values=[1])

    assert rows[0]["metric_results"]["weak_evidence_match_recall@1"] is True
    assert rows[0]["metric_results"]["e2e_rag_success_provisional"] is True


def test_weak_evidence_rejects_same_entity_wrong_date_anchor(tmp_path: Path) -> None:
    dataset = tmp_path / "wrong_date_anchor.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "wrong_date",
                "query": "자동판매기 3기 감독과 방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "야마모토 타카시, 2026년 4월",
                "expected_evidence": [
                    {
                        "doc_id": "doc-expected",
                        "chunk_id": "chunk-expected",
                        "text": "자동판매기 미궁 방랑 애니메이션 제3기 감독 야마모토 타카시 방영 시기는 2026년 4월",
                        "required": True,
                    }
                ],
            }
        ],
    )
    outputs = [
        {
            "id": "wrong_date",
            "query": "자동판매기 3기 감독과 방영 시기는?",
            "answerability": "answerable",
            "generated_answer": "야마모토 타카시, 2025년 4월",
            "retrieved_contexts": [
                {
                    "rank": 1,
                    "doc_id": "doc-other",
                    "chunk_id": "chunk-other",
                    "score": 0.8,
                    "text": "자동판매기 미궁 방랑 애니메이션 제3기 감독 야마모토 타카시 방영 시기는 2025년 4월",
                }
            ],
            "citations": [],
            "expected_answer": "야마모토 타카시, 2026년 4월",
            "expected_evidence": [],
            "metric_inputs_available": {
                "has_expected_answer": True,
                "has_expected_evidence": True,
                "has_answerability_label": True,
                "has_citations": False,
            },
            "diagnostics": {},
        }
    ]

    items = load_eval_dataset(dataset)
    _summary, rows = score_rag_eval_items(items, outputs, top_k_values=[1])

    assert rows[0]["metric_results"]["judged_answer_correctness_provisional"]["passed"] is False
    assert rows[0]["metric_results"]["weak_evidence_match_recall@1"] is False
    assert rows[0]["metric_results"]["e2e_rag_success_provisional"] is False


def test_inferred_answerable_metrics_do_not_mutate_unknown_gold_label(tmp_path: Path) -> None:
    dataset = tmp_path / "unknown_with_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "unknown_gold",
                "query": "What is the capital?",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul is the capital.", "required": True}],
            }
        ],
    )
    outputs = [
        {
            "id": "unknown_gold",
            "query": "What is the capital?",
            "answerability": "answerable",
            "generated_answer": "Seoul",
            "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul is the capital."}],
            "citations": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul is the capital."}],
            "expected_answer": "Seoul",
            "expected_evidence": [],
            "metric_inputs_available": {
                "has_expected_answer": True,
                "has_expected_evidence": True,
                "has_answerability_label": False,
                "has_citations": False,
            },
            "diagnostics": {},
        }
    ]

    items = load_eval_dataset(dataset)
    summary, rows = score_rag_eval_items(items, outputs, top_k_values=[1])

    assert items[0].answerability == "unknown"
    assert rows[0]["answerability"] == "unknown"
    assert summary["strict_metrics"]["exact_or_alias_answer_correctness"]["denominator"] == 0
    assert summary["strict_metrics"]["citation_precision"]["denominator"] == 0
    assert summary["strict_metrics"]["citation_recall"]["denominator"] == 0
    assert summary["strict_metrics"]["citation_precision"]["exclusion_reasons"] == {
        "answerability_unknown_not_in_citation_denominator": 1
    }
    assert summary["inferred_answerable_metrics"]["exact_or_alias_answer_correctness_inferred_answerable"]["denominator"] == 1
    assert summary["inferred_answerable_metrics"]["exact_or_alias_answer_correctness_inferred_answerable"]["numerator"] == 1
    assert summary["inferred_answerable_metrics"]["e2e_rag_success_inferred_answerable"]["numerator"] == 1
    assert rows[0]["metric_results"]["answerability_inferred_for_metrics_only"] is True


def test_score_rag_eval_items_separates_headline_denominators_from_diagnostics(tmp_path: Path) -> None:
    dataset = tmp_path / "gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "good",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_answer_aliases": ["서울"],
                "expected_evidence": [
                    {"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul is the capital.", "required": True}
                ],
            },
            {
                "id": "rank3",
                "query": "rank three evidence?",
                "answerability": "answerable",
                "expected_answer": "evidence three",
                "expected_evidence": [{"doc_id": "doc-c", "chunk_id": "c3", "text": "evidence three", "required": True}],
            },
            {"id": "partial", "query": "partial gold", "answerability": "answerable"},
            {"id": "empty", "query": "unknown label"},
            {"id": "unanswerable", "query": "not in corpus", "answerability": "unanswerable"},
            {
                "id": "provisional",
                "query": "partial answer support?",
                "answerability": "answerable",
                "expected_evidence": [
                    {"doc_id": "doc-p", "chunk_id": "cp", "text": "Seoul is the capital city.", "required": True}
                ],
                "notes": "Expected answer is missing, but evidence text can support provisional scoring.",
            },
        ],
    )
    items = load_eval_dataset(dataset)
    outputs = [
        {
            "id": "good",
            "query": "capital?",
            "answerability": "answerable",
            "generated_answer": "Seoul",
            "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul"}],
            "citations": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul"}],
            "expected_answer": "Seoul",
            "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul", "required": True}],
            "metric_inputs_available": {
                "has_expected_answer": True,
                "has_expected_evidence": True,
                "has_answerability_label": True,
                "has_citations": True,
            },
            "diagnostics": {},
        },
        {
            "id": "rank3",
            "query": "rank three evidence?",
            "answerability": "answerable",
            "generated_answer": "evidence three",
            "retrieved_contexts": [
                {"rank": 1, "doc_id": "doc-x", "chunk_id": "cx", "score": 0.9, "text": "wrong"},
                {"rank": 2, "doc_id": "doc-y", "chunk_id": "cy", "score": 0.8, "text": "wrong"},
                {"rank": 3, "doc_id": "doc-c", "chunk_id": "c3", "score": 0.7, "text": "evidence three"},
            ],
            "citations": [
                {"doc_id": "doc-c", "chunk_id": "c3", "text": "evidence three"},
                {"doc_id": "doc-x", "chunk_id": "cx", "text": "wrong"},
            ],
            "expected_answer": "evidence three",
            "expected_evidence": [{"doc_id": "doc-c", "chunk_id": "c3", "text": "evidence three", "required": True}],
            "metric_inputs_available": {
                "has_expected_answer": True,
                "has_expected_evidence": True,
                "has_answerability_label": True,
                "has_citations": True,
            },
            "diagnostics": {},
        },
        {
            "id": "partial",
            "query": "partial gold",
            "answerability": "answerable",
            "generated_answer": "some answer",
            "retrieved_contexts": [],
            "citations": [],
            "expected_answer": "",
            "expected_evidence": [],
            "metric_inputs_available": {
                "has_expected_answer": False,
                "has_expected_evidence": False,
                "has_answerability_label": True,
                "has_citations": False,
            },
            "diagnostics": {"gold_incomplete": True},
        },
        {
            "id": "empty",
            "query": "unknown label",
            "answerability": "unknown",
            "generated_answer": "",
            "retrieved_contexts": [],
            "citations": [],
            "expected_answer": "",
            "expected_evidence": [],
            "metric_inputs_available": {
                "has_expected_answer": False,
                "has_expected_evidence": False,
                "has_answerability_label": False,
                "has_citations": False,
            },
            "diagnostics": {"retrieval_empty": True, "generation_empty": True, "gold_incomplete": True},
        },
        {
            "id": "unanswerable",
            "query": "not in corpus",
            "answerability": "unanswerable",
            "generated_answer": "문서에서 찾을 수 없습니다.",
            "retrieved_contexts": [],
            "citations": [],
            "expected_answer": "",
            "expected_evidence": [],
            "metric_inputs_available": {
                "has_expected_answer": False,
                "has_expected_evidence": False,
                "has_answerability_label": True,
                "has_citations": False,
            },
            "diagnostics": {"retrieval_empty": True, "citation_empty": True},
        },
        {
            "id": "provisional",
            "query": "partial answer support?",
            "answerability": "answerable",
            "generated_answer": "Seoul is the capital city.",
            "retrieved_contexts": [
                {"rank": 1, "doc_id": "doc-p", "chunk_id": "cp", "score": 0.9, "text": "Seoul is the capital city."}
            ],
            "citations": [],
            "expected_answer": "",
            "expected_evidence": [
                {"doc_id": "doc-p", "chunk_id": "cp", "text": "Seoul is the capital city.", "required": True}
            ],
            "metric_inputs_available": {
                "has_expected_answer": False,
                "has_expected_evidence": True,
                "has_answerability_label": True,
                "has_citations": False,
            },
            "diagnostics": {"citation_empty": True, "gold_incomplete": True},
        },
    ]

    summary, scored_rows = score_rag_eval_items(items, outputs, top_k_values=[1, 3])

    strict = summary["strict_metrics"]
    provisional = summary["provisional_metrics"]
    assert strict["exact_or_alias_answer_correctness"]["numerator"] == 2
    assert strict["exact_or_alias_answer_correctness"]["denominator"] == 2
    assert strict["evidence_recall@1"]["numerator"] == 2
    assert strict["evidence_recall@1"]["denominator"] == 3
    assert strict["evidence_recall@3"]["numerator"] == 3
    assert strict["citation_precision"]["numerator"] == 2
    assert strict["citation_precision"]["denominator"] == 3
    assert strict["citation_recall"]["numerator"] == 2
    assert strict["citation_recall"]["denominator"] == 2
    assert strict["abstention_accuracy"]["numerator"] == 1
    assert strict["abstention_accuracy"]["denominator"] == 1
    assert strict["e2e_rag_success_strict"]["denominator"] == 2
    assert strict["e2e_rag_success_strict"]["numerator"] == 1
    assert provisional["judged_answer_correctness_provisional"]["denominator"] == 3
    assert provisional["judged_answer_correctness_provisional"]["numerator"] == 3
    assert provisional["weak_evidence_match_recall@1"]["numerator"] == 2
    assert provisional["e2e_rag_success_provisional"]["numerator"] == 3
    assert "answer_supported_by_retrieved_context_provisional" not in provisional
    assert summary["diagnostic_metric_details"]["answer_extracted_from_retrieved_context_rate"]["denominator"] == 3
    assert summary["diagnostic_metric_details"]["citation_points_to_retrieved_context_rate"]["denominator"] == 3
    assert "citation_overlap_provisional" not in provisional
    assert summary["diagnostic_metrics"]["missing_expected_answer_count"] == 4
    assert summary["diagnostic_metrics"]["missing_answerability_label_count"] == 1
    assert summary["diagnostic_metrics"]["gold_missing_count"] == 3
    assert summary["diagnostic_metrics"]["expected_evidence_id_missing_count"] == 0
    assert summary["diagnostic_metrics"]["expected_evidence_id_unresolved_count"] == 0
    assert "gold_missing_expected_answer" in {label for row in scored_rows for label in row["failure_labels"]}
    assert "provisional_metric_used" in next(row for row in scored_rows if row["id"] == "provisional")["failure_labels"]
    assert "strict_metric_not_applicable" in next(row for row in scored_rows if row["id"] == "provisional")["failure_labels"]
    assert "citation_wrong" in next(row for row in scored_rows if row["id"] == "rank3")["failure_labels"]


def test_expected_evidence_resolver_exact_id_and_high_confidence_text_candidate(tmp_path: Path) -> None:
    dataset = tmp_path / "resolver_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "exact",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [
                    {"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul is the capital.", "required": True}
                ],
            },
            {
                "id": "candidate",
                "query": "자동판매기 3기 방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "2026년 4월",
                "expected_evidence": [
                    {
                        "text": "자동판매기 미궁 방랑 애니메이션 제3기 방영 시기는 2026년 4월",
                        "required": True,
                    }
                ],
            },
        ],
    )
    items = {item.id: item for item in load_eval_dataset(dataset)}
    resolver = ExpectedEvidenceResolver(EvidenceResolutionConfig(scope="both", max_candidates=3))

    exact = resolver.resolve_item(
        items["exact"],
        retrieved_contexts=[{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul"}],
        index_candidates=[],
    )
    candidate = resolver.resolve_item(
        items["candidate"],
        retrieved_contexts=[],
        index_candidates=[
            {
                "rank": 1,
                "doc_id": "doc-auto",
                "chunk_id": "chunk-2026",
                "score": 0.88,
                "text": "자동판매기 미궁 방랑 애니메이션 제3기 방영 시기는 2026년 4월입니다.",
            }
        ],
    )

    assert exact["rows"][0]["id_status"] == "resolved_exact"
    assert exact["rows"][0]["selected_candidate"]["confidence"] == "high"
    assert exact["rows"][0]["selected_candidate"]["source"] == "retrieved_contexts"
    assert candidate["rows"][0]["id_status"] == "resolved_candidate"
    assert candidate["rows"][0]["selected_candidate"]["doc_id"] == "doc-auto"
    assert candidate["rows"][0]["selected_candidate"]["confidence"] == "high"
    assert "numeric_or_date_anchors_satisfied" in candidate["rows"][0]["candidates"][0]["match_reasons"]


def test_expected_evidence_resolver_rejects_generic_overlap_and_numeric_mismatch(tmp_path: Path) -> None:
    dataset = tmp_path / "resolver_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "generic",
                "query": "source text?",
                "answerability": "answerable",
                "expected_answer": "document answer",
                "expected_evidence": [{"text": "document source answer text", "required": True}],
            },
            {
                "id": "date",
                "query": "방영 시기?",
                "answerability": "answerable",
                "expected_answer": "2026년 4월",
                "expected_evidence": [{"text": "방영 시기는 2026년 4월", "required": True}],
            },
        ],
    )
    items = {item.id: item for item in load_eval_dataset(dataset)}
    resolver = ExpectedEvidenceResolver(EvidenceResolutionConfig(scope="both", max_candidates=3))

    generic = resolver.resolve_item(
        items["generic"],
        retrieved_contexts=[
            {"rank": 1, "doc_id": "doc-generic", "chunk_id": "c1", "score": 0.7, "text": "document source text answer"}
        ],
        index_candidates=[],
    )
    date_mismatch = resolver.resolve_item(
        items["date"],
        retrieved_contexts=[],
        index_candidates=[
            {"rank": 1, "doc_id": "doc-date", "chunk_id": "c2", "score": 0.7, "text": "방영 시기는 2025년 4월"}
        ],
    )

    assert generic["resolved_count"] == 0
    assert generic["rows"][0]["resolved"] is False
    assert "no_non_generic_anchor_overlap" in generic["rows"][0]["resolution_warnings"]
    assert date_mismatch["resolved_count"] == 0
    assert date_mismatch["rows"][0]["candidates"][0]["confidence"] == "low"
    assert "numeric_or_date_anchor_missing" in date_mismatch["rows"][0]["candidates"][0]["match_reasons"]


def test_medium_confidence_resolution_counts_only_when_configured(tmp_path: Path) -> None:
    dataset = tmp_path / "medium_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "medium",
                "query": "capital city?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"text": "Seoul is the capital city of Korea", "required": True}],
            }
        ],
    )
    item = load_eval_dataset(dataset)[0]
    contexts = [
        {"rank": 1, "doc_id": "doc-medium", "chunk_id": "c1", "score": 0.7, "text": "Seoul is the capital city of Korea"}
    ]

    default_resolution = ExpectedEvidenceResolver(EvidenceResolutionConfig(scope="retrieved-only")).resolve_item(
        item,
        retrieved_contexts=contexts,
        index_candidates=[],
    )
    medium_counted = ExpectedEvidenceResolver(
        EvidenceResolutionConfig(scope="retrieved-only", count_medium=True)
    ).resolve_item(item, retrieved_contexts=contexts, index_candidates=[])

    assert default_resolution["rows"][0]["selected_candidate"]["confidence"] == "medium"
    assert default_resolution["resolved_count"] == 0
    assert default_resolution["rows"][0]["resolved"] is False
    assert medium_counted["resolved_count"] == 1
    assert medium_counted["rows"][0]["resolved"] is True


def test_full_corpus_expected_evidence_resolution_finds_source_native_candidate_without_retrieval_leakage(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "full_corpus_resolution"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-full-corpus",
                "query": "Project Orion status dashboard",
                "answerability": "unknown",
                "expected_answer": "2026-04-12",
                "expected_evidence": [
                    {
                        "text": "Mercury launch window opens on 2026-04-12",
                        "required": True,
                    }
                ],
            }
        ],
    )
    source_units = [
        {
            "unit_id": "src-distractor",
            "source_atom_id": "srcatom-distractor",
            "doc_id": "doc-distractor",
            "chunk_id": "chunk-distractor",
            "source_family": "TEXT",
            "title": "Project Orion",
            "section": "Dashboard",
            "text": "Project Orion status dashboard has no launch-window answer.",
            "surface": "source_atom",
            "text_sha256": "src-distractor-sha",
            "metadata": {},
        },
        {
            "unit_id": "src-target",
            "source_atom_id": "srcatom-target",
            "evidence_bundle_id": "bundle-target",
            "doc_id": "doc-target",
            "chunk_id": "chunk-target",
            "source_family": "XLSX",
            "title": "Mercury Launch",
            "section": "Schedule",
            "text": (
                "sheet=Schedule | display_value=Mercury launch window opens on 2026-04-12. | "
                "normalized_value=SECRET_NORMALIZED_VALUE | formula=SECRET_FORMULA"
            ),
            "surface": "evidence_bundle",
            "text_sha256": "src-target-sha",
            "metadata": {},
        },
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=1,
        run_id="full_corpus_resolution",
        retrieval_surface="auto",
        retrieval_backend="bm25",
        source_native_units=source_units,
        evidence_resolution_scope="full-corpus",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    assert report["retrieval_surface"]["selected"] == "source_native"
    assert report["items"][0]["retrieved_contexts"][0]["doc_id"] == "doc-distractor"
    assert "gold_missing_answerability" in report["items"][0]["canonical_failure_labels"]
    assert "metric_not_applicable" in report["items"][0]["canonical_failure_labels"]
    diagnostics = report["diagnostic_metrics"]
    assert "gold_missing_answerability" in diagnostics["canonical_failure_labels"]
    assert diagnostics["canonical_failure_category_counts"]["gold_missing_answerability"] == 1
    assert diagnostics["expected_evidence_resolution_scope"] == "full-corpus"
    assert diagnostics["expected_evidence_full_corpus_candidate_count"] >= 1
    assert diagnostics["expected_evidence_full_corpus_high_confidence_count"] == 1
    assert diagnostics["expected_evidence_full_corpus_resolved_candidate_count"] == 1
    assert diagnostics["expected_evidence_full_corpus_unresolved_count"] == 0
    assert diagnostics["gold_or_qrels_mutation"] is False
    assert diagnostics["human_decision_fields_filled_by_codex"] is False
    assert report["gold_or_qrels_mutation"] is False
    assert report["human_decision_fields_filled_by_codex"] is False
    assert report["expected_evidence_resolution"]["scope"] == "full-corpus"
    assert report["expected_evidence_resolution"]["full_corpus_candidate_count"] >= 1

    candidate = report["evidence_resolution_candidates"][0]["candidates"][0]
    assert candidate["source"] == "full_corpus_source_native"
    assert candidate["doc_id"] == "doc-target"
    assert candidate["chunk_id"] == "chunk-target"
    assert candidate["source_atom_id"] == "srcatom-target"
    assert candidate["evidence_bundle_id"] == "bundle-target"
    assert candidate["candidate_text_hash"]
    assert candidate["candidate_full_text_hash"] == candidate["candidate_text_hash"]
    encoded_candidates = json.dumps(report["evidence_resolution_candidates"], ensure_ascii=False)
    assert "normalized_value=" not in encoded_candidates
    assert "SECRET_NORMALIZED_VALUE" not in encoded_candidates
    assert "formula=" not in encoded_candidates
    assert "SECRET_FORMULA" not in encoded_candidates
    assert candidate["normalized_match_info"]["normalized_expected_in_candidate"] is True
    assert candidate["match_type"] in {"exact_match", "normalized_match"}
    assert candidate["collision_warning"] == ""
    assert candidate["missing_numeric_or_date_anchors"] == []
    assert report["guardrails"]["expected_fields_used_for_candidate_generation"] is False
    assert report["guardrails"]["qrels_used_for_candidate_generation"] is False
    assert report["guardrails"]["gold_fields_used_for_candidate_generation"] is False
    assert set(report["strict_metrics"]).issubset(set(report["metric_tiers"]["strict"]))
    assert set(report["provisional_metrics"]).issubset(set(report["metric_tiers"]["provisional"]))
    assert set(report["inferred_answerable_metrics"]).issubset(set(report["metric_tiers"]["inferred_answerable"]))
    assert set(report["diagnostic_metrics"]).issubset(set(report["metric_tiers"]["diagnostic"]))
    assert set(report["diagnostic_metric_details"]).issubset(set(report["metric_tiers"]["diagnostic"]))


def test_full_corpus_review_only_scope_ignores_retrieved_context_candidates(tmp_path: Path) -> None:
    dataset = tmp_path / "resolver_scope_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "scope",
                "query": "Mercury launch window",
                "answerability": "unknown",
                "expected_answer": "2026-04-12",
                "expected_evidence": [{"text": "Mercury launch window opens on 2026-04-12", "required": True}],
            }
        ],
    )
    item = load_eval_dataset(dataset)[0]
    resolver = ExpectedEvidenceResolver(EvidenceResolutionConfig(scope="full-corpus-review-only", max_candidates=3))

    result = resolver.resolve_item(
        item,
        retrieved_contexts=[
            {
                "rank": 1,
                "doc_id": "doc-retrieved",
                "chunk_id": "chunk-retrieved",
                "score": 0.99,
                "text": "Mercury launch window opens on 2026-04-12.",
            }
        ],
        index_candidates=[
            {
                "rank": 99,
                "doc_id": "doc-full-corpus",
                "chunk_id": "chunk-full-corpus",
                "score": 0.91,
                "text": "Mercury launch window opens on 2026-04-12.",
                "_resolution_source": "full_corpus_source_native",
            }
        ],
    )

    selected = result["rows"][0]["selected_candidate"]
    assert selected["doc_id"] == "doc-full-corpus"
    assert selected["source"] == "full_corpus_source_native"
    assert all(
        candidate["doc_id"] != "doc-retrieved"
        for candidate in result["rows"][0]["candidates"]
    )


def test_default_run_writes_single_report_json_with_embedded_sections(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "single"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "Seoul",
                "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul"}],
                "citations": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul"}],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="single",
        command="unit-test single",
    )

    assert output_file_names(output_dir) == ["report.json"]
    assert bundle.summary_path == output_dir / "report.json"
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["artifact_contract"]["output_mode"] == "single"
    assert report["artifact_contract"]["primary_report_json"] == (output_dir / "report.json").as_posix()
    assert report["artifact_contract"]["legacy_sidecars_written"] is False
    assert report["items"][0]["id"] == "q1"
    assert report["evidence_resolution"]["enabled"] is True
    assert report["backend_comparison"]["vector_index_available"] is False
    assert report["gpu_preflight"]["checked"] is True
    assert report["retrieval_backend"]["requested"] == "auto"
    assert report["generator_config"]["provider"] == "extractive-v1"
    assert report["human_review_packet"]["enabled"] is False


def test_legacy_output_mode_writes_old_artifacts_only_when_requested(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "legacy"
    write_jsonl(dataset, [{"id": "q1", "query": "capital?", "answerability": "answerable", "expected_answer": "Seoul"}])
    write_jsonl(context, [{"id": "q1", "generated_answer": "Seoul", "retrieved_contexts": [], "citations": []}])

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="legacy",
        output_mode="legacy",
    )

    assert bundle.summary_path == output_dir / "rag_eval_summary.json"
    assert "report.json" not in output_file_names(output_dir)
    assert {"rag_eval_items.jsonl", "rag_eval_summary.json", "rag_eval_report.md"}.issubset(output_file_names(output_dir))


def test_human_review_packet_mode_writes_exactly_one_additional_csv(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "review"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "자동판매기 3기 방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "2026년 4월",
                "expected_evidence": [{"text": "자동판매기 제3기 방영 시기는 2026년 4월", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "2026년 4월",
                "retrieved_contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-auto",
                        "chunk_id": "chunk-2026",
                        "score": 0.95,
                        "text": "TEXT source text 자동판매기 제3기 방영 시기는 2026년 4월입니다.",
                        "source_family": "TEXT",
                    }
                ],
                "citations": [{"doc_id": "doc-auto", "chunk_id": "chunk-2026", "text": "자동판매기 2026년 4월"}],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="review",
        write_human_review_packet=True,
    )

    assert output_file_names(output_dir) == ["human_review_packet.csv", "report.json"]
    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    packet = report["human_review_packet"]
    assert packet["enabled"] is True
    assert packet["path"].endswith("human_review_packet.csv")
    assert packet["row_count"] >= 1
    assert packet["format"] == "csv"
    assert packet["human_decision_fields_blank"] is True
    assert packet["gold_qrels_labels_mutated"] is False
    with (output_dir / "human_review_packet.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert rows
    required_columns = {
        "query_id",
        "query",
        "expected_answer",
        "expected_evidence_text",
        "candidate_doc_id",
        "candidate_chunk_id",
        "candidate_source_atom_id",
        "candidate_evidence_bundle_id",
        "candidate_text_preview",
        "candidate_text_hash",
        "candidate_score",
        "candidate_confidence",
        "match_type",
        "match_reasons",
        "anchor_hits",
        "missing_numeric_or_date_anchors",
        "collision_warning",
        "machine_recommendation",
        "human_accept",
        "human_reject_reason",
        "human_expected_answer_override",
        "human_expected_evidence_override",
        "human_answerability_label",
        "human_notes",
    }
    assert required_columns.issubset(set(reader.fieldnames or []))
    assert all(row["human_mapping_decision"] == "" for row in rows)
    for row in rows:
        for field in (
            "human_accept",
            "human_reject_reason",
            "human_expected_answer_override",
            "human_expected_evidence_override",
            "human_answerability_label",
            "human_notes",
        ):
            assert row[field] == ""


def test_fake_vector_adapter_selects_hybrid_and_records_backend_comparison(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "hybrid"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "서울 수도",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul is the capital.", "required": True}],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=2,
        run_id="hybrid",
        retrieval_backend="auto",
        retrieval_adapter=FakeVectorAdapter(),
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert report["retrieval_backend"]["requested"] == "auto"
    assert report["retrieval_backend"]["selected"] == "hybrid"
    assert report["retrieval_backend"]["vector_enabled"] is True
    assert report["backend_comparison"]["vector_index_available"] is True
    assert report["backend_comparison"]["bm25_candidate_count_avg"] > 0
    assert report["backend_comparison"]["vector_candidate_count_avg"] > 0
    assert report["backend_comparison"]["hybrid_candidate_count_avg"] > 0
    row = report["items"][0]["retrieval_backend_comparison"]
    assert row["selected_backend"] == "hybrid"
    assert row["bm25_top_k"]
    assert row["vector_top_k"]
    assert row["hybrid_top_k"]
    adapter_source = inspect.getsource(FakeVectorAdapter)
    for forbidden in ["expected_answer", "expected_evidence", "qrels", "query_id", "row_id", "target_id", "baseline_top"]:
        assert forbidden not in adapter_source


def test_auto_backend_falls_back_to_bm25_when_faiss_unavailable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payloads = RepoCurrentBm25Adapter()._load_payloads()
    assert payloads
    query = " ".join(_clean_token for _clean_token in str(payloads[0]["bm25_text"]).split()[:8])
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "no_faiss"
    write_jsonl(dataset, [{"id": "q1", "query": query, "answerability": "unknown"}])

    monkeypatch.setitem(sys.modules, "faiss", None)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=3,
        run_id="no_faiss",
        retrieval_backend="auto",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    assert report["retrieval_backend"]["requested"] == "auto"
    assert report["retrieval_backend"]["selected"] == "bm25"
    assert report["retrieval_backend"]["vector_enabled"] is False
    assert report["retrieval_backend"]["fallback_reason"].startswith("faiss_or_numpy_unavailable:")
    assert report["diagnostic_metrics"]["pipeline_error_count"] == 0
    assert report["backend_comparison"]["comparison_available"] is True
    assert report["backend_comparison"]["bm25_candidate_count_avg"] > 0
    assert report["items"][0]["retrieval_backend_comparison"]["selected_backend"] == "bm25"
    assert report["guardrails"]["gold_fields_used_for_candidate_generation"] is False


def test_backend_comparison_metrics_missing_rows_are_unavailable() -> None:
    class NoComparisonAdapter:
        backend_diagnostics = {
            "vector_index_available": False,
            "gpu_used_for_embedding": False,
            "fallback_reason": "unit_test_missing_comparison",
        }

    metrics = build_backend_comparison_metrics([{"id": "q1", "diagnostics": {}}], NoComparisonAdapter())

    assert metrics["comparison_available"] is False
    assert metrics["comparison_row_count"] == 0
    assert metrics["comparison_missing_row_count"] == 1
    assert metrics["bm25_retrieval_empty_rate"] is None
    assert metrics["vector_retrieval_empty_rate"] is None
    assert metrics["hybrid_retrieval_empty_rate"] is None
    assert metrics["bm25_candidate_count_avg"] is None
    assert metrics["fallback_reason"] == "unit_test_missing_comparison"


def test_source_native_corpus_loader_prefers_source_atom_rows_and_redacts_paths(tmp_path: Path) -> None:
    manifest = tmp_path / "search_view_manifest.jsonl"
    write_jsonl(
        manifest,
        [
            {
                "source_atom_id": "srcatom-1",
                "source_family": "TEXT",
                "search_view_id": "sv-1",
                "bm25_text": "needle evidence text from source atom",
                "embedding_text": "needle evidence text from source atom",
                "source_identity": "D:/secret/raw/path/source.txt",
                "workbook_id": "",
                "document_version_id": "doc-1",
                "faiss_row_id": 0,
            }
        ],
    )

    loader = SourceNativeCorpusLoader(search_view_manifest_path=manifest, source_atom_registry_path=tmp_path / "atoms.jsonl")
    units = loader.load_units()

    assert [unit["surface"] for unit in units] == ["source_atom"]
    assert units[0]["source_atom_id"] == "srcatom-1"
    assert units[0]["text"] == "needle evidence text from source atom"
    assert "D:/secret" not in json.dumps(units[0], ensure_ascii=False)
    assert units[0]["metadata"]["source_identity_hash"].startswith("sha256:")


def test_source_native_surface_auto_demotes_searchunit_when_source_native_wins(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "needle source-native answer",
                "answerability": "answerable",
                "expected_answer": "needle answer",
                "expected_evidence": [{"text": "needle answer appears in source native evidence", "required": True}],
            }
        ],
    )
    source_units = [
        {
            "unit_id": "src-unit-1",
            "source_atom_id": "srcatom-1",
            "doc_id": "source-doc",
            "chunk_id": "source-chunk",
            "source_family": "TEXT",
            "title": "Source Doc",
            "section": "Evidence",
            "text": "needle answer appears in source native evidence",
            "surface": "source_atom",
            "text_sha256": "src-sha",
            "metadata": {},
        }
    ]
    searchunit_units = [
        {
            "payload_id": "legacy-1",
            "search_unit_id": "legacy-chunk",
            "search_view_id": "legacy-view",
            "source_family": "TEXT",
            "bm25_text": "irrelevant legacy projection filler",
            "embedding_text": "irrelevant legacy projection filler",
            "metadata": {"source_safe_id": "legacy-doc", "source_text_sha256": "legacy-sha"},
        }
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=1,
        run_id="source_native",
        retrieval_surface="auto",
        retrieval_backend="hybrid",
        source_native_units=source_units,
        searchunit_units=searchunit_units,
        source_native_embedding_provider=FakeDeterministicEmbeddingProvider(),
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    assert report["retrieval_surface"]["requested"] == "auto"
    assert report["retrieval_surface"]["selected"] == "source_native"
    assert report["retrieval_surface_decision"]["searchunit_searchview_demoted"] is True
    source_native_loader = report["index_retrieval_config"]["source_native"]["source_native_loader"]
    assert "searchunit_searchview_fallback" not in source_native_loader["preferred_surface_order"]
    assert report["surface_migration"]["selected_surface"] == "source_native"
    assert report["surface_migration"]["searchunit_searchview_candidate_surface_enabled"] is False
    assert report["surface_migration"]["auto_fallback_to_searchunit_searchview"] is False
    assert report["surface_migration"]["deprecation_decision"] == "demote_from_routine_actual_rag_candidate_surface"
    assert report["surface_migration"]["remaining_failure_target"] == "source_native_ranking_query_formulation"
    assert report["legacy_cleanup"] == {
        "enabled": True,
        "searchunit_searchview_routine_candidate_surface_enabled": False,
        "searchunit_searchview_role": "explicit_legacy_comparison_debug_only",
        "auto_fallback_to_searchunit_searchview": False,
        "source_native_hard_switch_preserved": True,
    }
    assert report["artifact_cleanup"]["output_mode_single_report_json_only"] is True
    assert report["artifact_cleanup"]["legacy_sidecars_routine_disabled"] is True
    assert report["artifact_cleanup"]["human_review_packet_exception_preserved"] is True
    assert report["artifact_cleanup"]["raw_prompt_payload_written"] is False
    assert report["artifact_cleanup"]["raw_response_payload_written"] is False
    assert report["runner_alias_cleanup"]["current_moved"] is False
    assert "--legacy-surface-comparison" in report["runner_alias_cleanup"]["aliases_kept_check_only"]
    assert report["diagnostic_metrics"]["source_native_expected_evidence_text_presence_rate"] == 1.0
    assert report["diagnostic_metrics"]["searchunit_expected_evidence_text_presence_rate"] is None
    row = report["items"][0]
    assert row["retrieval_surface_comparison"]["selected"]["surface"] == "source_native"
    assert row["retrieval_surface_comparison"]["source_native"]["expected_evidence_retrieved"] is True
    assert row["retrieval_surface_comparison"]["searchunit_searchview"]["comparison_enabled"] is False
    assert row["retrieval_surface_comparison"]["searchunit_searchview"]["candidate_count"] is None
    assert report["guardrails"]["gold_fields_used_for_candidate_generation"] is False


def test_source_native_legacy_cleanup_report_records_inventory_guardrails_and_debt(tmp_path: Path) -> None:
    routine_summary = {
        "run_id": "routine_source_native",
        "retrieval_surface": {
            "requested": "auto",
            "selected": "source_native",
            "source_native_available": True,
            "source_native_selected": True,
            "searchunit_searchview_candidate_surface_enabled": False,
            "auto_fallback_to_searchunit_searchview": False,
        },
        "artifact_contract": {
            "output_mode": "single",
            "single_artifact_default": True,
            "legacy_sidecars_written": False,
            "human_review_packet_exception": False,
        },
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
    }
    report_path = (
        tmp_path
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / "runs"
        / "actual_rag_eval_source_native_legacy_cleanup_nonprod"
        / "report.json"
    )

    report = write_source_native_legacy_cleanup_report(
        report_path,
        routine_summary=routine_summary,
        changed_files=[
            "ai/eval/actual_rag_eval.py",
            "ai/tests/test_actual_rag_eval_metric_generation.py",
            "docs/rag-ingestion-progress.md",
        ],
        deleted_files=[],
        generated_at="2026-06-11T00:00:00+00:00",
    )

    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted == report
    assert output_file_names(report_path.parent) == ["report.json"]
    assert report["run_id"] == "actual_rag_eval_source_native_legacy_cleanup_nonprod"
    assert report["cleanup_decisions"]["deletions"] == []
    assert report["legacy_cleanup"]["source_native_hard_switch_preserved"] is True
    assert report["artifact_cleanup"]["output_mode_single_report_json_only"] is True
    assert report["artifact_cleanup"]["legacy_sidecars_routine_disabled"] is True
    assert report["runner_alias_cleanup"]["current_moved"] is False
    assert report["runner_alias_cleanup"]["aliases_removed"] == []
    assert report["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["answerability_label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["expected_evidence_mutation"] is False
    assert report["guardrails"]["denominator_mutation"] is False
    assert report["guardrails"]["current_moved"] is False
    assert report["classification_counts"]["EXPLICIT_LEGACY_DEBUG_KEEP"] >= 1
    assert report["classification_counts"]["EXPLICIT_LEGACY_COMPARISON_KEEP"] >= 1
    assert report["classification_counts"]["PROTECTED_HOLD"] >= 1
    assert report["classification_counts"]["DOCS_ONLY_UPDATE"] >= 1
    assert report["classification_counts"]["DEPRECATE_FAIL_CLOSED"] >= 1
    inventory_categories = {entry["category"] for entry in report["inventory"]}
    assert {
        "searchunit_searchview_runtime_reference",
        "searchunit_searchview_test_reference",
        "searchunit_searchview_docs_reference",
        "actual_rag_sidecar_writer",
        "legacy_report_writer",
        "legacy_cli_alias",
        "stale_generated_ignored_artifact",
        "protected_namespace_reference",
    }.issubset(inventory_categories)
    assert report["remaining_debt"] == [
        "source_native_ranking_query_formulation",
        "bge_m3_artifacts_held_read_only_future_remeasurement_when_explicitly_opened_or_not_current",
        "extractive_v1_answer_generation_replacement",
    ]


def test_source_native_legacy_cleanup_report_builder_validates_guardrails() -> None:
    unsafe_summary = {
        "run_id": "unsafe",
        "retrieval_surface": {"selected": "source_native"},
        "artifact_contract": {"output_mode": "single"},
        "official_metric_input_rows": 1,
        "guardrails": {"gold_mutation": False},
    }

    with pytest.raises(DatasetSchemaError, match="official_metric_input_rows"):
        build_source_native_legacy_cleanup_report(routine_summary=unsafe_summary)


def test_legacy_searchunit_comparison_requires_explicit_debug_flag(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native_legacy_comparison"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "needle source-native answer",
                "answerability": "answerable",
                "expected_answer": "needle answer",
                "expected_evidence": [{"text": "needle answer appears in source native evidence", "required": True}],
            }
        ],
    )
    source_units = [
        {
            "unit_id": "src-unit-1",
            "source_atom_id": "srcatom-1",
            "doc_id": "source-doc",
            "chunk_id": "source-chunk",
            "source_family": "TEXT",
            "title": "Source Doc",
            "section": "Evidence",
            "text": "needle answer appears in source native evidence",
            "surface": "source_atom",
            "text_sha256": "src-sha",
            "metadata": {},
        }
    ]
    searchunit_units = [
        {
            "payload_id": "legacy-1",
            "search_unit_id": "legacy-chunk",
            "search_view_id": "legacy-view",
            "source_family": "TEXT",
            "bm25_text": "needle answer appears in legacy searchunit evidence",
            "embedding_text": "needle answer appears in legacy searchunit evidence",
            "metadata": {"source_safe_id": "legacy-doc", "source_text_sha256": "legacy-sha"},
        }
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=1,
        run_id="source_native_legacy_comparison",
        retrieval_surface="auto",
        retrieval_backend="bm25",
        source_native_units=source_units,
        searchunit_units=searchunit_units,
        legacy_surface_comparison=True,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    assert report["surface_migration"]["searchunit_searchview_candidate_surface_enabled"] is False
    assert report["surface_migration"]["legacy_comparison_enabled"] is True
    row = report["items"][0]
    assert row["retrieval_surface_comparison"]["searchunit_searchview"]["comparison_enabled"] is True
    assert row["retrieval_surface_comparison"]["searchunit_searchview"]["candidate_count"] == 1
    assert report["diagnostic_metrics"]["searchunit_retrieval_empty_rate"] == 0.0


def test_searchunit_candidate_surface_requires_legacy_debug_flag(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    write_jsonl(dataset, [{"id": "q1", "query": "legacy debug", "answerability": "unknown"}])
    searchunit_units = [
        {
            "payload_id": "legacy-1",
            "search_unit_id": "legacy-chunk",
            "search_view_id": "legacy-view",
            "source_family": "TEXT",
            "bm25_text": "legacy debug candidate",
            "embedding_text": "legacy debug candidate",
            "metadata": {"source_safe_id": "legacy-doc", "source_text_sha256": "legacy-sha"},
        }
    ]

    with pytest.raises(DatasetSchemaError, match="legacy/debug only"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=tmp_path / "reports" / "rag_eval" / "searchunit_blocked",
            top_k=1,
            run_id="searchunit_blocked",
            retrieval_surface="searchunit-searchview",
            retrieval_backend="bm25",
            searchunit_units=searchunit_units,
        )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "searchunit_debug",
        top_k=1,
        run_id="searchunit_debug",
        retrieval_surface="searchunit-searchview",
        retrieval_backend="bm25",
        searchunit_units=searchunit_units,
        legacy_surface_comparison=True,
    )
    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(tmp_path / "reports" / "rag_eval" / "searchunit_debug") == ["report.json"]
    assert report["retrieval_surface"]["selected"] == "searchunit_searchview"
    assert report["retrieval_surface"]["searchunit_searchview_role"] == "legacy_comparison_debug_only"
    assert report["retrieval_surface"]["searchunit_searchview_candidate_surface_enabled"] is True
    assert report["source_native_layered_retrieval"]["enabled"] is False
    assert report["source_native_layered_retrieval"]["legacy_searchunit_comparison_enabled"] is True


def test_source_native_units_reject_forbidden_candidate_generation_fields(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    write_jsonl(dataset, [{"id": "q1", "query": "source-native safe", "answerability": "unknown"}])

    with pytest.raises(DatasetSchemaError, match="forbidden source-native candidate fields"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=tmp_path / "reports" / "rag_eval" / "source_native_forbidden",
            top_k=1,
            run_id="source_native_forbidden",
            retrieval_surface="auto",
            retrieval_backend="bm25",
            source_native_units=[
                {
                    "unit_id": "src-unit-bad",
                    "source_atom_id": "srcatom-bad",
                    "doc_id": "source-doc",
                    "chunk_id": "source-bad",
                    "source_family": "TEXT",
                    "text": "source-native safe text",
                    "surface": "source_atom",
                    "text_sha256": "src-bad-sha",
                    "expected_answer": "oracle token",
                }
            ],
        )


def test_source_native_vector_index_audit_records_invocation_hydration_and_nonoracle(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native_vector_audit"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-vector",
                "query": "Project Orion Atlas launch April 2026",
                "answerability": "answerable",
                "expected_answer": "April 2026",
                "expected_evidence": [{"text": "Project Orion Atlas launch is scheduled for April 2026", "required": True}],
            }
        ],
    )
    source_units = [
        {
            "unit_id": "src-vector-1",
            "source_atom_id": "srcatom-vector-1",
            "doc_id": "source-doc",
            "chunk_id": "source-vector-1",
            "source_family": "TEXT",
            "title": "Project Orion",
            "section": "Launch",
            "text": "Project Orion Atlas launch is scheduled for April 2026.",
            "surface": "source_atom",
            "text_sha256": "src-vector-1-sha",
            "metadata": {},
        },
        {
            "unit_id": "src-vector-2",
            "source_atom_id": "srcatom-vector-2",
            "doc_id": "source-doc",
            "chunk_id": "source-vector-2",
            "source_family": "TEXT",
            "title": "Project Orion",
            "section": "Background",
            "text": "Project Orion background context for semantic vector retrieval.",
            "surface": "source_atom",
            "text_sha256": "src-vector-2-sha",
            "metadata": {},
        },
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=2,
        run_id="source_native_vector_audit",
        retrieval_surface="auto",
        retrieval_backend="hybrid",
        source_native_units=source_units,
        source_native_embedding_provider=FakeDeterministicEmbeddingProvider(),
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    audit = report["vector_index_audit"]
    assert audit["enabled"] is True
    assert audit["status"] == "connected_semantic_quality_unproven"
    assert audit["vector_surface"] == "source_native"
    assert audit["vector_backend"] == "python_deterministic_test"
    assert audit["external_vector_db_configured"] is False
    assert audit["external_vector_db_invoked"] is False
    assert audit["embedding_model"] == "deterministic-test-source-native-vector"
    assert audit["embedding_dim"] == 16
    assert audit["gpu_used_for_embedding"] is False
    assert audit["bge_m3_replacement_needed"] is True
    assert audit["index_integrity_passed"] is True
    assert audit["query_invocation_passed"] is True
    assert audit["hydration_passed"] is True
    assert audit["hybrid_comparison_available"] is True
    assert audit["semantic_quality_claim_allowed"] is False
    assert audit["id_map_count"] == audit["source_native_unit_count"] == 2
    assert audit["id_map_matches_source_native_units"] is True
    assert audit["faiss_index_ntotal"] == audit["id_map_count"]
    assert audit["faiss_ntotal_matches_id_map"] is True
    assert audit["faiss_row_id_mismatch_count"] == 0
    assert audit["raw_local_paths_exposed"] is False
    assert audit["target_presence_diagnostics"]["expected_fields_used_for_candidate_generation"] is False
    assert audit["target_presence_diagnostics"]["gold_fields_used_for_candidate_generation"] is False
    assert audit["target_presence_diagnostics"]["qrels_used_for_candidate_generation"] is False
    assert audit["target_presence_diagnostics"]["ids_used_for_candidate_generation"] is False
    assert audit["target_presence_diagnostics"]["baseline_topk_used_for_candidate_generation"] is False
    assert audit["target_presence_diagnostics"]["expected_fields_used_for_post_retrieval_diagnostics"] is True
    assert audit["target_presence_diagnostics"]["vector_expected_anchor_recall@k_diagnostic"] >= 0.0
    assert report["final_rag_target"]["retrieval_surface"] == "source_native"
    assert report["final_rag_target"]["evidence_truth"] == "SourceAtom/EvidenceBundle"
    assert report["final_rag_target"]["searchunit_searchview_role"] == "legacy_comparison_debug_only"
    row_comparison = report["items"][0]["retrieval_backend_comparison"]
    assert row_comparison["bm25_top_k_count"] >= 1
    assert row_comparison["vector_top_k_count"] >= 1
    assert row_comparison["hybrid_top_k_count"] >= 1
    assert row_comparison["bm25_vector_topk_overlap_count"] >= 0
    assert row_comparison["hybrid_contains_vector_only_candidate_count"] >= 0
    assert row_comparison["hybrid_contains_bm25_only_candidate_count"] >= 0
    assert row_comparison["vector_contribution_to_selected_topk_count"] >= 0
    assert row_comparison["bm25_contribution_to_selected_topk_count"] >= 0
    assert isinstance(row_comparison["selected_topk_layer_provenance_counts"], dict)
    vector_invocation = row_comparison["source_native_vector_invocation"]
    assert vector_invocation["vector_backend_invoked"] is True
    assert vector_invocation["query_embedding_created_or_loaded"] is True
    assert vector_invocation["query_embedding_dim"] == 16
    assert vector_invocation["vector_top_k_count"] >= 1
    assert vector_invocation["vector_hydration_failure_count"] == 0
    assert vector_invocation["vector_hydration_success_count"] == vector_invocation["vector_top_k_count"]
    assert vector_invocation["vector_candidate_generation_input_policy"] == "query_text_only_no_gold_qrels_labels_ids_or_baseline_topk"
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False


def test_current_diagnostic_hash_faiss_source_native_audit_marks_semantic_quality_unproven() -> None:
    source_units = [
        {
            "unit_id": "src-audit-1",
            "source_atom_id": "srcatom-audit-1",
            "doc_id": "source-doc",
            "chunk_id": "source-audit-1",
            "source_family": "TEXT",
            "title": "Audit",
            "section": "Vector",
            "text": "diagnostic hash vector audit source-native text",
            "surface": "source_atom",
            "text_sha256": "src-audit-1-sha",
            "metadata": {},
        }
    ]
    adapter = SourceNativeHybridAdapter(units=source_units, requested_backend="auto")
    payloads = adapter._load_payloads()
    adapter._vector_attempted = True
    adapter._vector_ready = True
    adapter._existing_vector_mode = True
    adapter._existing_vector_index = type("FakeFaissIndex", (), {"ntotal": len(payloads)})()
    adapter._vector_id_map = payloads
    adapter._embedding_model = "codex-diagnostic-hashing-vector-v1"
    adapter._embedding_device = "cpu_existing_nonprod_index"
    adapter._gpu_used_for_embedding = False
    adapter._vector_dim = 128

    audit = adapter.vector_index_audit_report

    assert audit["status"] == "connected_semantic_quality_unproven"
    assert audit["vector_backend"] == "faiss"
    assert audit["embedding_model"] == "codex-diagnostic-hashing-vector-v1"
    assert audit["embedding_dim"] == 128
    assert audit["embedding_device"] == "cpu_existing_nonprod_index"
    assert audit["gpu_used_for_embedding"] is False
    assert audit["bge_m3_replacement_needed"] is True
    assert audit["semantic_quality_claim_allowed"] is False
    assert audit["index_integrity_passed"] is True
    assert audit["faiss_index_ntotal"] == 1
    assert audit["faiss_ntotal_matches_id_map"] is True


def test_source_native_bge_m3_persisted_index_supersedes_diagnostic_hash(tmp_path: Path) -> None:
    source_index = tmp_path / "source_index"
    source_index.mkdir(parents=True)
    manifest = source_index / "search_view_manifest.jsonl"
    rows = [
        {
            "source_atom_id": "srcatom-bge-1",
            "search_view_id": "view-bge-1",
            "source_family": "TEXT",
            "document_id": "doc-bge-1",
            "faiss_row_id": 0,
            "bm25_text": "Project Orion Atlas launch is scheduled for April 2026.",
            "embedding_text": "Project Orion Atlas launch is scheduled for April 2026.",
        },
        {
            "source_atom_id": "srcatom-bge-2",
            "search_view_id": "view-bge-2",
            "source_family": "TEXT",
            "document_id": "doc-bge-2",
            "faiss_row_id": 1,
            "bm25_text": "Unrelated archive note about a different project.",
            "embedding_text": "Unrelated archive note about a different project.",
        },
    ]
    write_jsonl(manifest, rows)
    loader = SourceNativeCorpusLoader(search_view_manifest_path=manifest)
    bge_index_dir = tmp_path / "bge_index"

    build = build_source_native_bge_m3_index_artifact(
        index_dir=bge_index_dir,
        loader=loader,
        embedding_provider=FakeBgeM3EmbeddingProvider(),
        force=True,
        gpu_preflight={"torch_cuda_available": True},
    )

    assert build["embedding_model"] == "BAAI/bge-m3-test"
    assert build["dimension"] == 4
    assert build["chunk_count"] == 2
    assert build["gpu_used_for_embedding"] is True
    assert (bge_index_dir / "faiss.index").exists()
    assert (bge_index_dir / "build.json").exists()
    assert (bge_index_dir / "search_view_manifest.jsonl").exists()

    adapter = SourceNativeHybridAdapter(
        requested_backend="vector",
        loader=SourceNativeCorpusLoader(search_view_manifest_path=bge_index_dir / "search_view_manifest.jsonl"),
        embedding_provider=FakeBgeM3EmbeddingProvider(),
        gpu_preflight={"torch_cuda_available": True},
    )

    contexts, _latency = adapter._vector_contexts("Project Orion Atlas April 2026", top_k=1)
    audit = adapter.vector_index_audit_report

    assert contexts[0]["chunk_id"] == "srcatom-bge-1"
    assert audit["status"] == "connected_bge_m3_candidate"
    assert audit["vector_backend"] == "faiss"
    assert audit["embedding_model"] == "BAAI/bge-m3-test"
    assert audit["embedding_dim"] == 4
    assert audit["embedding_device"] == "cuda:0"
    assert audit["gpu_used_for_embedding"] is True
    assert audit["bge_m3_replacement_needed"] is False
    assert audit["semantic_quality_claim_allowed"] is False
    assert audit["index_integrity_passed"] is True
    assert audit["faiss_index_ntotal"] == 2
    assert audit["faiss_ntotal_matches_id_map"] is True
    assert audit["faiss_row_id_mismatch_count"] == 0
    assert "diagnostic_hash" not in " ".join(audit["limitations"])


def test_sentence_transformer_embedder_local_files_only_forces_offline_model_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.capabilities.rag.embeddings import SentenceTransformerEmbedder

    captured: dict[str, object] = {}

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            captured["model_name"] = model_name
            captured["kwargs"] = dict(kwargs)
            captured["hf_hub_offline"] = os.environ.get("HF_HUB_OFFLINE")
            captured["transformers_offline"] = os.environ.get("TRANSFORMERS_OFFLINE")
            self.max_seq_length = 8192
            self.device = "cuda:0"

        def get_sentence_embedding_dimension(self) -> int:
            return 4

        def encode(self, texts: list[str], **_kwargs: object) -> object:
            import numpy as np

            return np.ones((len(texts), 4), dtype=np.float32)

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)

    embedder = SentenceTransformerEmbedder(
        model_name="BAAI/bge-m3",
        local_files_only=True,
        show_progress_bar=False,
    )
    vectors = embedder.embed_queries(["local bge-m3 only"])

    assert vectors.shape == (1, 4)
    assert captured["model_name"] == "BAAI/bge-m3"
    assert captured["kwargs"]["local_files_only"] is True
    assert captured["hf_hub_offline"] == "1"
    assert captured["transformers_offline"] == "1"


def test_sentence_transformer_embedder_local_files_only_overrides_false_offline_envs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.capabilities.rag.embeddings import SentenceTransformerEmbedder

    captured: dict[str, object] = {}

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            captured["model_name"] = model_name
            captured["kwargs"] = dict(kwargs)
            captured["hf_hub_offline"] = os.environ.get("HF_HUB_OFFLINE")
            captured["transformers_offline"] = os.environ.get("TRANSFORMERS_OFFLINE")
            captured["hf_datasets_offline"] = os.environ.get("HF_DATASETS_OFFLINE")
            self.max_seq_length = 8192
            self.device = "cuda:0"

        def get_sentence_embedding_dimension(self) -> int:
            return 4

        def encode(self, texts: list[str], **_kwargs: object) -> object:
            import numpy as np

            return np.ones((len(texts), 4), dtype=np.float32)

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    monkeypatch.setenv("HF_DATASETS_OFFLINE", "0")

    embedder = SentenceTransformerEmbedder(
        model_name="BAAI/bge-m3",
        local_files_only=True,
        show_progress_bar=False,
    )
    vectors = embedder.embed_queries(["local bge-m3 only"])

    assert vectors.shape == (1, 4)
    assert captured["model_name"] == "BAAI/bge-m3"
    assert captured["kwargs"]["local_files_only"] is True
    assert captured["hf_hub_offline"] == "1"
    assert captured["transformers_offline"] == "1"
    assert captured["hf_datasets_offline"] == "1"


def test_sentence_transformer_embedder_local_files_only_unsupported_kwarg_fallback_stays_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.capabilities.rag.embeddings import SentenceTransformerEmbedder

    calls: list[dict[str, object]] = []
    captured: dict[str, object] = {}

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            calls.append(dict(kwargs))
            if "local_files_only" in kwargs:
                raise TypeError("__init__() got an unexpected keyword argument 'local_files_only'")
            captured["model_name"] = model_name
            captured["hf_hub_offline"] = os.environ.get("HF_HUB_OFFLINE")
            captured["transformers_offline"] = os.environ.get("TRANSFORMERS_OFFLINE")
            captured["hf_datasets_offline"] = os.environ.get("HF_DATASETS_OFFLINE")
            self.max_seq_length = 8192
            self.device = "cuda:0"

        def get_sentence_embedding_dimension(self) -> int:
            return 4

        def encode(self, texts: list[str], **_kwargs: object) -> object:
            import numpy as np

            return np.ones((len(texts), 4), dtype=np.float32)

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    monkeypatch.setenv("HF_DATASETS_OFFLINE", "0")

    embedder = SentenceTransformerEmbedder(
        model_name="BAAI/bge-m3",
        local_files_only=True,
        show_progress_bar=False,
    )
    vectors = embedder.embed_queries(["local bge-m3 only"])

    assert vectors.shape == (1, 4)
    assert calls == [{"local_files_only": True}, {}]
    assert captured["model_name"] == "BAAI/bge-m3"
    assert captured["hf_hub_offline"] == "1"
    assert captured["transformers_offline"] == "1"
    assert captured["hf_datasets_offline"] == "1"


def test_sentence_transformer_embedder_local_files_only_restores_offline_env_for_later_loads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.capabilities.rag.embeddings import SentenceTransformerEmbedder

    loads: list[dict[str, object]] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            loads.append(
                {
                    "model_name": model_name,
                    "kwargs": dict(kwargs),
                    "hf_hub_offline": os.environ.get("HF_HUB_OFFLINE"),
                    "transformers_offline": os.environ.get("TRANSFORMERS_OFFLINE"),
                    "hf_datasets_offline": os.environ.get("HF_DATASETS_OFFLINE"),
                }
            )
            self.max_seq_length = 8192
            self.device = "cuda:0"

        def get_sentence_embedding_dimension(self) -> int:
            return 4

        def encode(self, texts: list[str], **_kwargs: object) -> object:
            import numpy as np

            return np.ones((len(texts), 4), dtype=np.float32)

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    monkeypatch.setenv("HF_DATASETS_OFFLINE", "0")

    local_embedder = SentenceTransformerEmbedder(
        model_name="BAAI/bge-m3",
        local_files_only=True,
        show_progress_bar=False,
    )
    nonlocal_embedder = SentenceTransformerEmbedder(
        model_name="BAAI/bge-m3",
        local_files_only=False,
        show_progress_bar=False,
    )

    assert local_embedder.embed_queries(["local bge-m3 only"]).shape == (1, 4)
    assert os.environ["HF_HUB_OFFLINE"] == "0"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "0"
    assert os.environ["HF_DATASETS_OFFLINE"] == "0"
    assert nonlocal_embedder.embed_queries(["non-local policy"]).shape == (1, 4)

    assert loads[0]["kwargs"] == {"local_files_only": True}
    assert loads[0]["hf_hub_offline"] == "1"
    assert loads[0]["transformers_offline"] == "1"
    assert loads[0]["hf_datasets_offline"] == "1"
    assert loads[1]["kwargs"] == {}
    assert loads[1]["hf_hub_offline"] == "0"
    assert loads[1]["transformers_offline"] == "0"
    assert loads[1]["hf_datasets_offline"] == "0"


def test_diagnostic_hit_mmr_ndcg_metrics_and_semantic_samples_are_reported_without_leakage(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native_quality_metrics"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-quality",
                "query": "Project Orion Atlas launch April 2026",
                "answerability": "answerable",
                "expected_answer": "April 2026",
                "expected_evidence": [
                    {
                        "text": "Project Orion Atlas launch is scheduled for April 2026",
                        "required": True,
                    }
                ],
            }
        ],
    )
    source_units = [
        {
            "unit_id": "src-quality-1",
            "source_atom_id": "srcatom-quality-1",
            "doc_id": "source-doc-quality-1",
            "chunk_id": "source-quality-1",
            "source_family": "TEXT",
            "title": "Project Orion",
            "section": "Launch",
            "text": "Project Orion Atlas launch is scheduled for April 2026.",
            "surface": "source_atom",
            "text_sha256": "src-quality-1-sha",
            "metadata": {},
        },
        {
            "unit_id": "src-quality-2",
            "source_atom_id": "srcatom-quality-2",
            "doc_id": "source-doc-quality-2",
            "chunk_id": "source-quality-2",
            "source_family": "TEXT",
            "title": "Project Orion",
            "section": "Archive",
            "text": "Project Orion archive contains background material unrelated to the April launch.",
            "surface": "source_atom",
            "text_sha256": "src-quality-2-sha",
            "metadata": {},
        },
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=2,
        run_id="source_native_quality_metrics",
        retrieval_surface="auto",
        retrieval_backend="hybrid",
        source_native_units=source_units,
        source_native_embedding_provider=FakeDeterministicEmbeddingProvider(),
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    metrics = report["diagnostic_retrieval_metrics"]
    assert metrics["enabled"] is True
    assert metrics["metric_policy"] == "diagnostic_only_not_official"
    assert metrics["denominator_policy"] == "rows_with_expected_evidence_for_post_retrieval_diagnostics_only"
    assert metrics["candidate_generation_input_policy"] == "query_text_only_no_gold_qrels_labels_ids_or_baseline_topk"
    assert metrics["gold_fields_used_for_candidate_generation"] is False
    assert metrics["expected_fields_used_for_candidate_generation"] is False
    assert metrics["qrels_used_for_candidate_generation"] is False
    assert metrics["ids_used_for_candidate_generation"] is False
    assert metrics["baseline_topk_used_for_candidate_generation"] is False
    assert metrics["rankings"]["selected"]["hit@1"] == 1.0
    assert metrics["rankings"]["selected"]["hit@2"] == 1.0
    assert metrics["rankings"]["selected"]["ndcg@2"] == 1.0
    assert metrics["rankings"]["mmr_selected"]["mmr_enabled"] is True
    assert metrics["rankings"]["mmr_selected"]["mmr_lambda"] == 0.65
    assert metrics["rankings"]["mmr_selected"]["hit@2"] == 1.0
    assert metrics["rankings"]["mmr_selected"]["ndcg@2"] >= 0.0

    row_metrics = report["items"][0]["diagnostic_retrieval_metrics"]
    assert row_metrics["selected"]["first_relevant_rank"] == 1
    assert row_metrics["mmr_selected"]["mmr_enabled"] is True
    assert row_metrics["mmr_selected"]["candidate_count"] >= 1
    assert row_metrics["mmr_selected"]["selected_chunk_ids"][0]

    samples = report["semantic_quality_samples"]
    assert samples["enabled"] is True
    assert samples["sample_policy"] == "bounded_query_response_context_examples_no_raw_prompt_or_full_raw_response"
    assert samples["semantic_quality_claim_allowed"] is False
    assert samples["samples"][0]["id"] == "q-quality"
    assert samples["samples"][0]["query"] == "Project Orion Atlas launch April 2026"
    assert "Project Orion" in samples["samples"][0]["generated_answer_excerpt"]
    assert samples["samples"][0]["retrieved_contexts"][0]["text_sha256"]
    assert len(samples["samples"][0]["retrieved_contexts"][0]["text_preview"]) <= 240
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False


def test_source_native_layered_retrieval_is_bounded_source_native_only_and_no_leakage(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native_layered"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-layered",
                "query": "Project Orion April 2026 Atlas launch status",
                "answerability": "answerable",
                "expected_answer": "FORBIDDEN_EXPECTED_ANSWER_TOKEN",
                "expected_evidence": [
                    {
                        "doc_id": "forbidden-expected-doc",
                        "chunk_id": "forbidden-expected-chunk",
                        "text": "FORBIDDEN_EXPECTED_EVIDENCE_TOKEN",
                        "required": True,
                    }
                ],
            }
        ],
    )
    source_units = [
        {
            "unit_id": "src-unit-target",
            "source_atom_id": "srcatom-target",
            "doc_id": "source-doc",
            "chunk_id": "source-target",
            "source_family": "TEXT",
            "title": "Project Orion",
            "section": "Launch",
            "text": "Source owned Project Orion status: Atlas launch milestone is scheduled for April 2026.",
            "surface": "source_atom",
            "text_sha256": "src-target-sha",
            "metadata": {"structure_kind": "paragraph"},
        },
        {
            "unit_id": "src-unit-neighbor",
            "source_atom_id": "srcatom-neighbor",
            "doc_id": "source-doc",
            "chunk_id": "source-neighbor",
            "source_family": "TEXT",
            "title": "Project Orion",
            "section": "Launch",
            "text": "Neighbor source-native context for the same Project Orion launch section.",
            "surface": "source_atom",
            "text_sha256": "src-neighbor-sha",
            "metadata": {"structure_kind": "paragraph"},
        },
    ]
    searchunit_units = [
        {
            "payload_id": "legacy-tempting",
            "search_unit_id": "legacy-winning-search-unit",
            "search_view_id": "legacy-winning-search-view",
            "source_family": "TEXT",
            "bm25_text": "Project Orion April 2026 Atlas legacy SearchUnit projection should not be routine.",
            "embedding_text": "Project Orion April 2026 Atlas legacy SearchUnit projection should not be routine.",
            "metadata": {"source_safe_id": "legacy-doc", "source_text_sha256": "legacy-sha"},
        }
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=2,
        run_id="source_native_layered",
        retrieval_surface="auto",
        retrieval_backend="hybrid",
        source_native_units=source_units,
        searchunit_units=searchunit_units,
        source_native_embedding_provider=FakeDeterministicEmbeddingProvider(),
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    layered = report["source_native_layered_retrieval"]
    assert layered["enabled"] is True
    assert layered["planner"] == "bounded_deterministic_source_native_layered_retrieval_v1"
    assert layered["selected_surface"] == "source_native"
    assert layered["selected_backend"] == "hybrid"
    assert layered["query_variant_count"] <= 8
    assert layered["backend_call_count"] <= 16
    assert layered["final_candidate_count"] <= 2
    assert layered["bounds"]["max_candidates_per_layer"] <= 50
    assert layered["bounds"]["max_merged_candidates"] <= 100
    assert layered["bounds"]["max_neighbor_expansion_windows"] <= 2
    assert {
        "L0_query_normalization",
        "L1_lexical_anchor_search",
        "L2_semantic_vector_search",
        "L3_query_variant_search",
        "L4_structure_aware_source_native_search",
        "L5_merge_dedupe",
        "L6_source_neighbor_expansion",
        "L7_anchor_aware_reranking_diagnostics",
    }.issubset(set(layered["layers"]))
    assert layered["per_layer_candidate_counts"]["L1_lexical_anchor_search"] >= 1
    assert layered["per_layer_candidate_counts"]["L5_merge_dedupe"] >= 1
    assert set(layered["per_layer_latency_ms"]) >= set(layered["layers"])
    assert layered["gold_fields_used_for_candidate_generation"] is False
    assert layered["expected_fields_used_for_candidate_generation"] is False
    assert layered["qrels_used_for_candidate_generation"] is False
    assert layered["answerability_labels_used_for_candidate_generation"] is False
    assert layered["ids_used_for_candidate_generation"] is False
    assert layered["baseline_topk_used_for_candidate_generation"] is False
    assert layered["searchunit_searchview_used_as_candidate_surface"] is False
    assert layered["legacy_searchunit_comparison_enabled"] is False
    assert all(
        forbidden.casefold() not in " ".join(layered["query_variants"]).casefold()
        for forbidden in [
            "FORBIDDEN_EXPECTED_ANSWER_TOKEN",
            "FORBIDDEN_EXPECTED_EVIDENCE_TOKEN",
            "q-layered",
            "forbidden-expected-doc",
            "forbidden-expected-chunk",
            "legacy-winning-search-unit",
            "legacy-winning-search-view",
        ]
    )
    row = report["items"][0]
    row_layered = row["source_native_layered_retrieval"]
    assert row_layered["enabled"] is True
    assert row_layered["query_variants"] == layered["query_variants"]
    assert row["retrieval_surface_comparison"]["searchunit_searchview"]["comparison_enabled"] is False
    assert row["retrieval_surface_comparison"]["selected"]["surface"] == "source_native"
    assert row["retrieved_contexts"]
    assert all(context["retrieval_surface"] == "source_native" for context in row["retrieved_contexts"])
    assert all(context.get("layer_provenance") for context in row["retrieved_contexts"])
    assert "legacy-winning-search-unit" not in json.dumps(row["retrieved_contexts"], ensure_ascii=False)


def test_source_native_surface_classifies_absent_and_present_not_retrieved(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native_absence"
    write_jsonl(
        dataset,
        [
            {
                "id": "present_missed",
                "query": "generic query",
                "answerability": "answerable",
                "expected_answer": "hidden target",
                "expected_evidence": [{"text": "hidden target span", "required": True}],
            },
            {
                "id": "absent",
                "query": "absent query",
                "answerability": "answerable",
                "expected_answer": "missing target",
                "expected_evidence": [{"text": "missing target span", "required": True}],
            },
        ],
    )
    source_units = [
        {
            "unit_id": "src-hidden",
            "source_atom_id": "srcatom-hidden",
            "doc_id": "source-doc",
            "chunk_id": "hidden",
            "source_family": "TEXT",
            "title": "Hidden",
            "section": "Evidence",
            "text": "hidden target span",
            "surface": "source_atom",
            "text_sha256": "hidden-sha",
            "metadata": {},
        }
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=1,
        run_id="source_native_absence",
        retrieval_surface="source-native",
        retrieval_backend="bm25",
        source_native_units=source_units,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    diagnostics = report["diagnostic_metrics"]
    assert diagnostics["source_native_target_span_present_but_not_retrieved_count"] == 1
    assert diagnostics["source_native_target_span_absent_count"] == 1
    assert diagnostics["searchunit_target_span_absent_count"] == 0
    assert diagnostics["both_surfaces_fail_count"] == 0
    assert report["items"][0]["retrieval_surface_comparison"]["searchunit_searchview"]["comparison_enabled"] is False


def test_source_native_unavailable_auto_does_not_use_searchunit_for_evidence_resolution(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native_unavailable_no_legacy_resolution"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "legacy-only evidence",
                "answerability": "answerable",
                "expected_answer": "legacy answer",
                "expected_evidence": [{"text": "legacy-only SearchUnit evidence", "required": True}],
            }
        ],
    )
    searchunit_units = [
        {
            "payload_id": "legacy-1",
            "search_unit_id": "legacy-search-unit",
            "search_view_id": "legacy-search-view",
            "source_family": "TEXT",
            "bm25_text": "legacy-only SearchUnit evidence",
            "embedding_text": "legacy-only SearchUnit evidence",
            "metadata": {"source_safe_id": "legacy-doc", "source_text_sha256": "legacy-sha"},
        }
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=1,
        run_id="source_native_unavailable_no_legacy_resolution",
        retrieval_surface="auto",
        retrieval_backend="bm25",
        source_native_units=[],
        searchunit_units=searchunit_units,
        resolve_expected_evidence=True,
        evidence_resolution_scope="both",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert report["retrieval_surface"]["selected"] == "unavailable"
    assert report["retrieval_surface"]["auto_fallback_to_searchunit_searchview"] is False
    assert report["diagnostic_metrics"]["expected_evidence_resolution_candidate_count"] == 0
    assert report["diagnostic_metrics"]["expected_evidence_id_unresolved_count"] == 1
    assert report["evidence_resolution_candidates"]
    assert all(row["candidates"] == [] for row in report["evidence_resolution_candidates"])
    candidate_payload_json = json.dumps(
        [candidate for row in report["evidence_resolution_candidates"] for candidate in row["candidates"]],
        ensure_ascii=False,
    )
    assert "legacy-search-unit" not in candidate_payload_json
    assert "legacy-only SearchUnit evidence" not in candidate_payload_json


def test_cli_smoke_with_fake_vector_adapter_hybrid_backend(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    output_dir = report_root / "cli_fake_hybrid"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul", "required": True}],
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai.scripts.rag_actual_eval",
            "--dataset",
            str(dataset),
            "--top-k",
            "2",
            "--run-id",
            "cli_fake_hybrid",
            "--output-dir",
            str(output_dir),
            "--report-root",
            str(report_root),
            "--retrieval-backend",
            "hybrid",
            "--output-mode",
            "single",
            "--use-fake-vector-adapter",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_file_names(output_dir) == ["report.json"]
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["retrieval_backend"]["requested"] == "hybrid"
    assert report["retrieval_backend"]["selected"] == "hybrid"
    assert report["backend_comparison"]["vector_index_available"] is True
    assert report["items"][0]["retrieval_backend_comparison"]["vector_top_k"]
    assert report["guardrails"]["gold_fields_used_for_candidate_generation"] is False
    assert report["gold_fields_used_for_candidate_generation"] is False


def test_cli_smoke_with_fake_source_native_fixture_beats_searchunit(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    output_dir = report_root / "cli_source_native"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "needle source-native answer",
                "answerability": "answerable",
                "expected_answer": "needle answer",
                "expected_evidence": [{"text": "needle answer appears in source native evidence", "required": True}],
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai.scripts.rag_actual_eval",
            "--dataset",
            str(dataset),
            "--top-k",
            "1",
            "--run-id",
            "cli_source_native",
            "--output-dir",
            str(output_dir),
            "--report-root",
            str(report_root),
            "--retrieval-surface",
            "auto",
            "--retrieval-backend",
            "auto",
            "--output-mode",
            "single",
            "--use-fake-source-native-fixture",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_file_names(output_dir) == ["report.json"]
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["retrieval_surface"]["selected"] == "source_native"
    assert report["retrieval_surface_decision"]["searchunit_searchview_demoted"] is True
    assert report["surface_migration"]["searchunit_searchview_candidate_surface_enabled"] is False
    assert report["items"][0]["retrieval_surface_comparison"]["source_native"]["expected_evidence_retrieved"] is True


def test_legacy_real_rag_quality_gate_report_scores_answer_evidence_and_critic(tmp_path: Path) -> None:
    dataset = tmp_path / "existing_gold.csv"
    dataset.write_text(
        "\n".join(
            [
                "query_id,question,expected_answer,supporting_evidence,human_review_status,human_approved_gold",
                "q1,Where is HQ?,Seoul,Seoul headquarters,USER_REVIEWED_APPROVED,TRUE",
                "q2,Which port?,Busan,Busan port,USER_REVIEWED_APPROVED,TRUE",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    items = load_eval_dataset(dataset)
    legacy_report = {
        "run_id": "legacy_searchunit_snapshot",
        "dataset_path": dataset.as_posix(),
        "total_item_count": 2,
        "index_retrieval_config": {"adapter": "repo_current_searchunit_vector_hybrid"},
        "items": [
            {
                "id": "q1",
                "query": "Where is HQ?",
                "generated_answer": "Seoul",
                "citations": [{"doc_id": "doc-hq", "chunk_id": "su-hq", "text": "Seoul headquarters"}],
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "su-hq",
                        "search_unit_id": "su-hq",
                        "source_atom_id": "src-hq",
                        "text": "Seoul headquarters",
                    }
                ],
                "failure_labels": [],
            },
            {
                "id": "q2",
                "query": "Which port?",
                "generated_answer": "Busan",
                "citations": [{"doc_id": "doc-port", "chunk_id": "su-port", "text": "Busan port"}],
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-port",
                        "chunk_id": "su-port",
                        "search_unit_id": "su-port",
                        "source_atom_id": "src-port",
                        "text": "Busan port",
                    }
                ],
                "failure_labels": [],
            },
        ],
    }
    real_report = {
        "run_id": "real_source_native_snapshot",
        "dataset_path": dataset.as_posix(),
        "output_dir": (tmp_path / "real").as_posix(),
        "total_item_count": 2,
        "retrieval_surface": {
            "selected": "source_native",
            "source_native_selected": True,
            "searchunit_searchview_candidate_surface_enabled": False,
            "auto_fallback_to_searchunit_searchview": False,
        },
        "source_native_layered_retrieval": {
            "selected_surface": "source_native",
            "source_native_units_only": True,
            "gold_fields_used_for_candidate_generation": False,
            "expected_fields_used_for_candidate_generation": False,
            "qrels_used_for_candidate_generation": False,
            "answerability_labels_used_for_candidate_generation": False,
            "ids_used_for_candidate_generation": False,
            "baseline_topk_used_for_candidate_generation": False,
        },
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "expected_fields_used_for_candidate_generation": False,
            "gold_fields_used_for_candidate_generation": False,
            "qrels_used_for_candidate_generation": False,
            "answerability_labels_used_for_candidate_generation": False,
            "baseline_topk_used_for_candidate_generation": False,
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
            "official_metric": False,
            "protected_namespaces_touched": [],
        },
        "items": [
            {
                "id": "q1",
                "query": "Where is HQ?",
                "expected_answer": "Seoul",
                "expected_answer_aliases": [],
                "expected_evidence": [{"doc_id": "doc-hq", "chunk_id": "src-hq", "text": "Seoul headquarters"}],
                "answerability": "unknown",
                "generated_answer": "Seoul",
                "citations": [{"doc_id": "doc-hq", "source_atom_id": "src-hq", "text": "Seoul headquarters"}],
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "retrieval_surface": "source_native",
                        "text": "Seoul headquarters",
                    }
                ],
                "failure_labels": [],
            },
            {
                "id": "q2",
                "query": "Which port?",
                "expected_answer": "Busan",
                "expected_answer_aliases": [],
                "expected_evidence": [{"doc_id": "doc-port", "chunk_id": "src-port", "text": "Busan port"}],
                "answerability": "unknown",
                "generated_answer": "Seoul",
                "citations": [{"doc_id": "doc-other", "source_atom_id": "src-other", "text": "Seoul office"}],
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-other",
                        "source_atom_id": "src-other",
                        "evidence_bundle_id": "bundle-other",
                        "retrieval_surface": "source_native",
                        "text": "Seoul office",
                    }
                ],
                "failure_labels": ["answer_judge_fail"],
            },
        ],
    }

    report, rows = build_legacy_real_rag_quality_gate_report(
        gold_items=items,
        existing_gold_set_path=dataset,
        legacy_baseline_report=legacy_report,
        legacy_baseline_path=tmp_path / "legacy_report.json",
        real_rag_report=real_report,
        real_rag_report_path=tmp_path / "real" / "report.json",
    )

    assert report["existing_gold_set_path"] == dataset.as_posix()
    assert report["gold_set_item_count"] == 2
    assert report["gold_mutation"] is False
    assert report["legacy_baseline_run_id"] == "legacy_searchunit_snapshot"
    assert report["legacy_baseline_replayed_not_executed"] is True
    assert report["real_rag_selected_surface"] == "source_native"
    assert report["guardrail_status"]["valid"] is True
    assert report["guardrail_status"]["source_native_selected"] is True
    assert report["guardrail_status"]["searchunit_searchview_not_used_in_real_rag_lane"] is True
    assert rows[0]["query_id"] == "q1"
    assert rows[0]["answer_delta_category"] == "same_answer_same_support"
    assert rows[0]["evidence_package_status"] == "sufficient"
    assert rows[0]["diagnostic_critic"]["critic_result_tier"] == "diagnostic"
    assert rows[0]["diagnostic_critic"]["answer_supported_by_evidence"] is True
    assert rows[1]["answer_delta_category"] == "legacy_correct_real_wrong"
    assert rows[1]["evidence_package_status"] == "insufficient"
    assert rows[1]["citation_points_to_expected_or_resolved_evidence"] is False
    assert rows[1]["citation_points_to_retrieved_context_diagnostic_only"] is True
    assert rows[1]["diagnostic_critic"]["citation_supported_by_evidence"] is False
    assert rows[1]["diagnostic_critic"]["citation_points_to_retrieved_context_diagnostic_only"] is True
    assert rows[1]["diagnostic_critic"]["should_abstain"] is True
    assert report["same_answer_same_support_count"] == 1
    assert report["legacy_correct_real_wrong_count"] == 1
    assert report["real_rag_supported_count"] == 1
    assert report["unsupported_same_answer_count"] == 0
    assert report["diagnostic_critic_summary"]["citation_supported_by_evidence_count"] == 1
    assert report["diagnostic_critic_summary"]["citation_points_to_expected_or_resolved_evidence_count"] == 1
    assert report["diagnostic_critic_summary"]["citation_points_to_retrieved_context_diagnostic_only_count"] == 2

    unsafe_real_report = dict(real_report)
    unsafe_real_report["guardrails"] = {
        **real_report["guardrails"],
        "expected_fields_used_for_candidate_generation": True,
    }
    unsafe_report, _unsafe_rows = build_legacy_real_rag_quality_gate_report(
        gold_items=items,
        existing_gold_set_path=dataset,
        legacy_baseline_report=legacy_report,
        legacy_baseline_path=tmp_path / "legacy_report.json",
        real_rag_report=unsafe_real_report,
        real_rag_report_path=tmp_path / "real" / "report.json",
    )
    assert unsafe_report["guardrail_status"]["valid"] is False
    assert "expected_fields_not_used_for_candidate_generation" in unsafe_report["guardrail_status"]["violations"]

    gate_unsafe_real_report = {
        **real_report,
        "evidence_gate": {
            "evidence_gate_mode": "enforce",
            "validator_version": "bounded_evidence_gate_v1",
            "guardrail_status": {
                "gate_uses_expected_fields": True,
                "gate_uses_gold_fields": False,
                "gate_uses_legacy_fields": False,
                "retrieval_loop_triggered": False,
            },
        },
    }
    gate_unsafe_report, _gate_unsafe_rows = build_legacy_real_rag_quality_gate_report(
        gold_items=items,
        existing_gold_set_path=dataset,
        legacy_baseline_report=legacy_report,
        legacy_baseline_path=tmp_path / "legacy_report.json",
        real_rag_report=gate_unsafe_real_report,
        real_rag_report_path=tmp_path / "real" / "report.json",
    )
    assert gate_unsafe_report["guardrail_status"]["valid"] is False
    assert "expected_gold_legacy_not_used_for_evidence_gate_enforcement" in gate_unsafe_report["guardrail_status"]["violations"]

    legacy_comparison_real_report = {
        **real_report,
        "retrieval_surface": {
            **real_report["retrieval_surface"],
            "legacy_surface_comparison_enabled": True,
        },
    }
    legacy_comparison_report, _legacy_comparison_rows = build_legacy_real_rag_quality_gate_report(
        gold_items=items,
        existing_gold_set_path=dataset,
        legacy_baseline_report=legacy_report,
        legacy_baseline_path=tmp_path / "legacy_report.json",
        real_rag_report=legacy_comparison_real_report,
        real_rag_report_path=tmp_path / "real" / "report.json",
    )
    assert legacy_comparison_report["guardrail_status"]["valid"] is False
    assert "searchunit_searchview_not_used_in_real_rag_lane" in legacy_comparison_report["guardrail_status"]["violations"]


def test_quality_gate_baseline_auto_selects_exact_query_id_coverage(tmp_path: Path) -> None:
    dataset = tmp_path / "existing_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {"id": "q1", "query": "Q1?", "expected_answer": "A1", "expected_evidence": [{"text": "A1 evidence"}]},
            {"id": "q2", "query": "Q2?", "expected_answer": "A2", "expected_evidence": [{"text": "A2 evidence"}]},
        ],
    )
    items = load_eval_dataset(dataset)
    report_root = tmp_path / "reports" / "rag_eval"
    dataset_report_path = _report_path_value(dataset)

    def _write_candidate(run_dir: str, run_id: str, item_ids: list[str]) -> Path:
        output = report_root / run_dir
        output.mkdir(parents=True, exist_ok=True)
        path = output / "report.json"
        path.write_text(
            json.dumps(
                    {
                        "run_id": run_id,
                        "dataset_path": dataset_report_path,
                        "total_item_count": len(item_ids),
                        "official_metric_input_rows": 0,
                        "official_metric_input_rows_created": 0,
                        "official_metric_input_rows_consumed": 0,
                        "protected_namespaces_touched": [],
                        "raw_prompt_payload_written": False,
                        "raw_response_payload_written": False,
                        "guardrails": {
                            "gold_mutation": False,
                            "qrels_mutation": False,
                            "label_mutation": False,
                            "answerability_label_mutation": False,
                            "expected_answer_mutation": False,
                            "expected_evidence_mutation": False,
                            "denominator_mutation": False,
                            "retriever_ranking_improvement": False,
                            "official_metric": False,
                            "official_metric_input_rows": 0,
                            "official_metric_input_rows_created": 0,
                            "official_metric_input_rows_consumed": 0,
                            "promotion_evidence": False,
                            "product_success_evidence_allowed": False,
                            "live_readiness_claim": False,
                            "protected_namespaces_touched": [],
                            "raw_prompt_payload_written": False,
                            "raw_response_payload_written": False,
                            "expected_fields_used_for_candidate_generation": False,
                            "gold_fields_used_for_candidate_generation": False,
                            "qrels_used_for_candidate_generation": False,
                            "answerability_labels_used_for_candidate_generation": False,
                            "baseline_topk_used_for_candidate_generation": False,
                            "ids_used_for_candidate_generation": False,
                        },
                        "index_retrieval_config": {"adapter": "repo_current_searchunit_vector_hybrid"},
                        "items": [{"id": item_id, "generated_answer": "answer"} for item_id in item_ids],
                    },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    _write_candidate("zzz_partial_single_vector_final", "zzz_partial_single_vector_final", ["q1"])
    expected = _write_candidate("aaa_exact_legacy", "aaa_exact_legacy", ["q1", "q2"])

    baseline, selected = resolve_quality_gate_baseline_report(
        "auto",
        dataset_path=dataset,
        gold_items=items,
        report_root=report_root,
    )

    assert selected == expected
    assert baseline["run_id"] == "aaa_exact_legacy"




def test_citation_validator_rejects_same_doc_chunk_with_different_source_identity() -> None:
    raw_outputs = [
        {
            "id": "q-identity",
            "query": "Where is Apollo HQ?",
            "generated_answer": "Apollo HQ is in Seoul.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-hq",
                    "chunk_id": "chunk-hq",
                    "source_atom_id": "src-selected",
                    "evidence_bundle_id": "bundle-selected",
                    "text": "Apollo HQ is in Seoul.",
                    "text_sha256": "hash-selected",
                }
            ],
            "citations": [
                {
                    "doc_id": "doc-hq",
                    "chunk_id": "chunk-hq",
                    "source_atom_id": "src-other",
                    "evidence_bundle_id": "bundle-other",
                    "text": "Apollo HQ is in Seoul.",
                    "text_sha256": "hash-other",
                }
            ],
        }
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="diagnostic")

    citation = gated_outputs[0]["evidence_gate"]["citation_validations"][0]
    assert citation["citation_target_exists"] is False
    assert citation["citation_target_in_selected_evidence"] is False
    assert citation["citation_support_status"] == "missing_target"
    assert gated_outputs[0]["answer_gate_decision"] == "block_unsupported_answer"
    assert gated_outputs[0]["unsupported_answer_blocked"] is False
    assert gated_outputs[0]["would_block_unsupported_answer"] is True
    assert summary["citation_supported_count"] == 0
    assert summary["citation_missing_target_count"] == 1
    assert summary["unsupported_answer_blocked_count"] == 0


def test_run_eval_preserves_citation_source_identity_for_evidence_gate(tmp_path: Path) -> None:
    dataset = tmp_path / "citation_identity_gold.jsonl"
    context = tmp_path / "citation_identity_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "citation_identity"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-identity",
                "query": "Where is Apollo HQ?",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-hq", "chunk_id": "chunk-hq", "text": "Apollo HQ is in Seoul."}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-identity",
                "generated_answer": "Apollo HQ is in Seoul.",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-selected",
                        "evidence_bundle_id": "bundle-selected",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-other",
                        "evidence_bundle_id": "bundle-other",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        context_jsonl_path=context,
        output_dir=output_dir,
        top_k=1,
        run_id="citation_identity",
        output_mode="single",
        evidence_gate_mode="diagnostic",
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    citation = row["evidence_gate"]["citation_validations"][0]
    assert row["citations"][0]["source_atom_id"] == "src-other"
    assert row["citations"][0]["evidence_bundle_id"] == "bundle-other"
    assert citation["cited_source_atom_id"] == "src-other"
    assert citation["cited_evidence_bundle_id"] == "bundle-other"
    assert citation["citation_target_exists"] is False
    assert citation["citation_target_in_selected_evidence"] is False
    assert citation["citation_support_status"] == "missing_target"


def test_evidence_gate_handles_empty_rows_and_invalid_mode() -> None:
    raw_outputs = [{"id": "empty", "query": "", "generated_answer": "", "retrieved_contexts": [], "citations": []}]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="diagnostic")
    off_outputs, off_summary = apply_evidence_gate_to_outputs(raw_outputs, mode="off")

    assert gated_outputs[0]["answer_gate_decision"] == "not_comparable"
    assert gated_outputs[0]["evidence_gate"]["evidence_package_status"] == "insufficient"
    assert summary["item_count"] == 1
    assert summary["unsupported_answer_rate_before_gate"] == 0.0
    assert summary["unsupported_answer_rate_after_gate"] == 0.0
    assert off_outputs[0]["evidence_gate_mode"] == "off"
    assert off_summary["gate_policy_not_applicable_count"] == 1
    with pytest.raises(DatasetSchemaError):
        apply_evidence_gate_to_outputs(raw_outputs, mode="agent-loop")


def test_evidence_gate_ignores_expected_evidence_resolution_for_enforcement() -> None:
    raw_outputs = [
        {
            "id": "q-resolution-leak",
            "query": "Where is Apollo HQ?",
            "generated_answer": "Apollo HQ is in Seoul.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-wrong",
                    "chunk_id": "chunk-wrong",
                    "source_atom_id": "src-wrong",
                    "evidence_bundle_id": "bundle-wrong",
                    "text": "Apollo HQ moved from Busan.",
                }
            ],
            "citations": [],
            "expected_evidence_resolution": {
                "rows": [
                    {
                        "resolved": True,
                        "selected_candidate": {
                            "doc_id": "doc-gold",
                            "source_atom_id": "src-gold",
                            "text": "Apollo HQ is in Seoul.",
                        },
                    }
                ]
            },
            "expected_answer": "Seoul",
            "expected_evidence": [{"text": "Apollo HQ is in Seoul."}],
        }
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="enforce")

    row = gated_outputs[0]
    assert row["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    assert row["evidence_gate"]["selected_evidence_count"] == 0
    assert row["evidence_gate"]["gate_uses_expected_fields"] is False
    assert row["evidence_gate"]["gate_uses_gold_fields"] is False
    assert summary["insufficient_evidence_abstained_count"] == 1
    assert summary["unsupported_answer_rate_after_gate"] == 0.0


def test_evidence_gate_does_not_use_title_or_workbook_metadata_as_support() -> None:
    raw_outputs = [
        {
            "id": "q-title-only",
            "query": "Where is Apollo HQ?",
            "generated_answer": "Apollo HQ is in Seoul.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-hq",
                    "chunk_id": "chunk-hq",
                    "source_atom_id": "src-hq",
                    "evidence_bundle_id": "bundle-hq",
                    "title": "Apollo HQ Seoul workbook",
                    "section": "Seoul locator",
                    "text": "Workbook metadata only; no answer sentence here.",
                }
            ],
            "citations": [],
        }
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="enforce")

    assert gated_outputs[0]["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    assert gated_outputs[0]["evidence_gate"]["selected_evidence_count"] == 0
    assert summary["insufficient_evidence_abstained_count"] == 1


def test_evidence_gate_does_not_use_xlsx_cell_axis_as_answer_value_support() -> None:
    raw_outputs = [
        {
            "id": "q-xlsx-cell-axis-only",
            "query": "2019년 2월 5호선 승차총승객수는 얼마야?",
            "generated_answer": "F7입니다.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-xlsx",
                    "chunk_id": "chunk-xlsx",
                    "source_atom_id": "src-xlsx",
                    "evidence_bundle_id": "bundle-xlsx",
                    "source_family": "XLSX",
                    "text": "2019년 2월 5호선 승차총승객수 항목입니다.",
                    "sheet": "2019년 2월",
                    "cell": "F7",
                    "row_label": "5호선",
                    "column_label": "승차총승객수",
                }
            ],
            "citations": [
                {
                    "doc_id": "doc-xlsx",
                    "chunk_id": "chunk-xlsx",
                    "source_atom_id": "src-xlsx",
                    "evidence_bundle_id": "bundle-xlsx",
                    "source_family": "XLSX",
                    "text": "2019년 2월 5호선 승차총승객수 항목입니다.",
                    "sheet": "2019년 2월",
                    "cell": "F7",
                    "row_label": "5호선",
                    "column_label": "승차총승객수",
                }
            ],
        }
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="enforce")

    assert gated_outputs[0]["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    assert gated_outputs[0]["answer_gate_decision"] == "block_unsupported_answer"
    assert gated_outputs[0]["evidence_gate"]["evidence_package_status"] == "insufficient"
    assert summary["allowed_answer_count"] == 0
    assert summary["insufficient_evidence_abstained_count"] == 1


def test_evidence_gate_does_not_use_pdf_page_axis_as_answer_value_support() -> None:
    raw_outputs = [
        {
            "id": "q-pdf-page-axis-only",
            "query": "2024년 영업이익 표의 값은 얼마야?",
            "generated_answer": "7입니다.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-pdf",
                    "chunk_id": "chunk-pdf",
                    "source_atom_id": "src-pdf",
                    "evidence_bundle_id": "bundle-pdf",
                    "source_family": "PDF",
                    "text": "2024년 영업이익 표 항목입니다.",
                    "page_number": "7",
                    "table_caption": "영업실적 표",
                    "bbox": "[10,20,30,40]",
                }
            ],
            "citations": [
                {
                    "doc_id": "doc-pdf",
                    "chunk_id": "chunk-pdf",
                    "source_atom_id": "src-pdf",
                    "evidence_bundle_id": "bundle-pdf",
                    "source_family": "PDF",
                    "text": "2024년 영업이익 표 항목입니다.",
                    "page_number": "7",
                    "table_caption": "영업실적 표",
                    "bbox": "[10,20,30,40]",
                }
            ],
        }
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="enforce")

    assert gated_outputs[0]["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    assert gated_outputs[0]["answer_gate_decision"] == "block_unsupported_answer"
    assert gated_outputs[0]["evidence_gate"]["evidence_package_status"] == "insufficient"
    assert summary["allowed_answer_count"] == 0
    assert summary["insufficient_evidence_abstained_count"] == 1


def test_validate_actual_rag_guardrails_rejects_semantic_raw_response_without_evidence_gate() -> None:
    summary = {
        "run_id": "raw-response-guard",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
        "semantic_quality_samples": {
            "enabled": True,
            "semantic_quality_claim_allowed": False,
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": True,
        },
    }

    with pytest.raises(DatasetSchemaError, match="semantic_quality_samples.raw_response_payload_written"):
        validate_actual_rag_guardrails(summary)


def test_validate_actual_rag_guardrails_accepts_evidence_gate_without_semantic_samples() -> None:
    summary = {
        "run_id": "gate_only_guardrail",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
        "evidence_gate": {
            "evidence_gate_mode": "diagnostic",
            "validator_version": "bounded_evidence_gate_v1",
            "guardrail_status": {
                "gate_uses_expected_fields": False,
                "gate_uses_gold_fields": False,
                "gate_uses_legacy_fields": False,
                "retrieval_loop_triggered": False,
            },
        },
    }

    validate_actual_rag_guardrails(summary)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("uses_query_id_or_row_id_or_target_id", True, "query_id_or_row_id_or_target_id"),
        ("uses_expected_answer_or_evidence", True, "expected_answer_or_evidence"),
        ("uses_qrels_or_labels", True, "qrels_or_labels"),
        ("per_row_alias_table", True, "per_row_alias_table"),
        ("composer_or_gate_loosening_for_single_residual", True, "single_residual"),
        ("classification", "forbidden_eval_row_shortcut", "forbidden_eval_row_shortcut"),
    ],
)
def test_validate_actual_rag_guardrails_rejects_forbidden_heuristic_risk_ledger_entries(
    field: str,
    value: object,
    match: str,
) -> None:
    entry = {
        "rule_id": "unsafe_shortcut",
        "classification": "query_text_only_reformulation",
        "status": "active",
        "uses_query_id_or_row_id_or_target_id": False,
        "uses_expected_answer_or_evidence": False,
        "uses_qrels_or_labels": False,
        "per_row_alias_table": False,
        "composer_or_gate_loosening_for_single_residual": False,
    }
    entry[field] = value
    summary = {
        "run_id": "guarded",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
        "heuristic_risk_ledger": {
            "schema_version": "actual_rag_eval.heuristic_risk_ledger.v1",
            "official_metric": False,
            "official_metric_input_rows": 0,
            "entries": [entry],
            "forbidden_eval_row_shortcut_active": False,
        },
    }

    with pytest.raises(DatasetSchemaError, match=match):
        validate_actual_rag_guardrails(summary)


def test_evidence_gate_summary_is_embedded_in_quality_gate_report() -> None:
    real_report = {
        "run_id": "real_gate",
        "retrieval_surface": {
            "selected": "source_native",
            "source_native_selected": True,
            "searchunit_searchview_candidate_surface_enabled": False,
            "auto_fallback_to_searchunit_searchview": False,
        },
        "source_native_layered_retrieval": {
            "selected_surface": "source_native",
            "source_native_units_only": True,
            "gold_fields_used_for_candidate_generation": False,
            "expected_fields_used_for_candidate_generation": False,
            "qrels_used_for_candidate_generation": False,
            "answerability_labels_used_for_candidate_generation": False,
            "ids_used_for_candidate_generation": False,
            "baseline_topk_used_for_candidate_generation": False,
        },
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "expected_fields_used_for_candidate_generation": False,
            "gold_fields_used_for_candidate_generation": False,
            "qrels_used_for_candidate_generation": False,
            "answerability_labels_used_for_candidate_generation": False,
            "baseline_topk_used_for_candidate_generation": False,
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
            "official_metric": False,
            "protected_namespaces_touched": [],
        },
        "evidence_gate": {
            "evidence_gate_mode": "enforce",
            "validator_version": "bounded_evidence_gate_v1",
            "item_count": 1,
            "sufficient_evidence_package_count": 0,
            "insufficient_evidence_package_count": 1,
            "allowed_answer_count": 0,
            "abstained_count": 1,
            "unsupported_answer_blocked_count": 1,
            "would_abstain_count": 1,
            "would_block_unsupported_answer_count": 1,
            "citation_supported_count": 0,
            "citation_retrieved_context_only_diagnostic_count": 1,
            "unsupported_answer_rate_before_gate": 1.0,
            "unsupported_answer_rate_after_gate": 0.0,
            "insufficient_evidence_abstained_count": 1,
            "sufficient_evidence_allowed_count": 0,
            "guardrail_status": {
                "gate_uses_expected_fields": False,
                "gate_uses_gold_fields": False,
                "gate_uses_legacy_fields": False,
                "retrieval_loop_triggered": False,
            },
        },
        "items": [
            {
                "id": "q1",
                "query": "Where?",
                "generated_answer": "제공된 근거만으로는 답할 수 없습니다.",
                "original_generated_answer_hash": "original-hash",
                "gated_answer_hash": "gated-hash",
                "retrieved_contexts": [{"doc_id": "doc-a", "source_atom_id": "src-a", "text": "Only Busan evidence"}],
                "citations": [{"doc_id": "doc-a", "source_atom_id": "src-a", "text": "Only Busan evidence"}],
                "evidence_gate": {
                    "evidence_package_status": "insufficient",
                    "answer_gate_decision": "block_unsupported_answer",
                    "answer_modified_by_gate": True,
                    "abstention_reason": "missing_entity_anchor",
                    "unsupported_answer_blocked": True,
                    "retrieval_loop_triggered": False,
                    "gate_uses_expected_fields": False,
                    "gate_uses_gold_fields": False,
                    "gate_uses_legacy_fields": False,
                },
            }
        ],
    }
    legacy_report = {"run_id": "legacy", "items": [{"id": "q1", "generated_answer": "Busan"}]}
    dataset = Path("unused.jsonl")
    items = [
        type(
            "EvalItemLike",
            (),
            {
                "id": "q1",
                "query": "Where?",
                "expected_answer": "Seoul",
                "expected_answer_aliases": [],
                "expected_evidence": [],
                "answerability": "unknown",
                "has_answerability_label": False,
                "has_expected_evidence": False,
            },
        )()
    ]

    report, rows = build_legacy_real_rag_quality_gate_report(
        gold_items=items,
        existing_gold_set_path=dataset,
        legacy_baseline_report=legacy_report,
        legacy_baseline_path=Path("legacy.json"),
        real_rag_report=real_report,
        real_rag_report_path=Path("real.json"),
    )

    assert report["evidence_gate_mode"] == "enforce"
    assert report["validator_version"] == "bounded_evidence_gate_v1"
    assert report["abstained_count"] == 1
    assert rows[0]["answer_gate_decision"] == "block_unsupported_answer"
    assert rows[0]["answer_modified_by_gate"] is True
    assert rows[0]["real_rag_supported_before_gate"] is False
    assert rows[0]["real_rag_supported_after_gate"] is False
    assert rows[0]["expected_answer_match_after_gate"] is False


def test_run_eval_writes_legacy_real_rag_quality_gate_artifacts_without_using_baseline_for_candidates(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "tiny_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "Where is the needle answer?",
                "expected_answer": "needle answer",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "src-a", "text": "needle answer appears"}],
            }
        ],
    )
    baseline = tmp_path / "legacy_report.json"
    baseline.write_text(
        json.dumps(
                {
                    "run_id": "legacy_searchunit_snapshot",
                    "dataset_path": dataset.as_posix(),
                    "total_item_count": 1,
                    "official_metric_input_rows": 0,
                    "official_metric_input_rows_created": 0,
                    "official_metric_input_rows_consumed": 0,
                    "protected_namespaces_touched": [],
                    "raw_prompt_payload_written": False,
                    "raw_response_payload_written": False,
                    "guardrails": {
                        "gold_mutation": False,
                        "qrels_mutation": False,
                        "label_mutation": False,
                        "answerability_label_mutation": False,
                        "expected_answer_mutation": False,
                        "expected_evidence_mutation": False,
                        "denominator_mutation": False,
                        "retriever_ranking_improvement": False,
                        "official_metric": False,
                        "official_metric_input_rows": 0,
                        "official_metric_input_rows_created": 0,
                        "official_metric_input_rows_consumed": 0,
                        "promotion_evidence": False,
                        "product_success_evidence_allowed": False,
                        "live_readiness_claim": False,
                        "protected_namespaces_touched": [],
                        "raw_prompt_payload_written": False,
                        "raw_response_payload_written": False,
                        "gold_fields_used_for_candidate_generation": False,
                        "query_id_used_for_candidate_generation": False,
                        "row_id_used_for_candidate_generation": False,
                        "target_id_used_for_candidate_generation": False,
                        "baseline_topk_used_for_candidate_generation": False,
                        "expected_fields_used_for_candidate_generation": False,
                        "qrels_used_for_candidate_generation": False,
                        "answerability_labels_used_for_candidate_generation": False,
                        "ids_used_for_candidate_generation": False,
                        "retriever_oracle_shortcut_used": False,
                    },
                    "index_retrieval_config": {"adapter": "repo_current_searchunit_vector_hybrid"},
                    "items": [
                    {
                        "id": "q1",
                        "query": "Where is the needle answer?",
                        "generated_answer": "needle answer",
                        "citations": [{"doc_id": "doc-a", "chunk_id": "su-a", "text": "needle answer appears"}],
                        "retrieved_contexts": [
                            {
                                "doc_id": "doc-a",
                                "chunk_id": "su-a",
                                "search_unit_id": "su-a",
                                "source_atom_id": "src-a",
                                "text": "needle answer appears",
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "quality_gate_run",
        top_k=3,
        run_id="quality_gate_run",
        command="unit-test",
        retrieval_surface="source-native",
        source_native_units=[
            {
                "unit_id": "src-a",
                "source_atom_id": "src-a",
                "doc_id": "doc-a",
                "source_family": "TEXT",
                "text": "needle answer appears",
                "surface": "source_atom",
            }
        ],
        source_native_embedding_provider=FakeDeterministicEmbeddingProvider(),
        quality_gate_baseline_path=baseline,
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    gate_report_path = Path(report["artifact_paths"]["legacy_real_rag_quality_gate_report_json"])
    gate_items_path = Path(report["artifact_paths"]["legacy_real_rag_quality_gate_items_jsonl"])
    assert report["artifact_contract"]["legacy_sidecars_written"] is False
    assert report["artifact_contract"]["quality_gate_sidecars_written"] is True
    assert report["artifact_contract"]["quality_gate_sidecar_exception"] is True
    assert gate_report_path.exists()
    assert gate_items_path.exists()
    gate_report = json.loads(gate_report_path.read_text(encoding="utf-8"))
    gate_rows = [json.loads(line) for line in gate_items_path.read_text(encoding="utf-8").splitlines()]
    assert gate_report["legacy_baseline_replayed_not_executed"] is True
    assert gate_report["guardrail_status"]["legacy_outputs_not_used_for_candidate_generation"] is True
    assert gate_report["guardrail_status"]["expected_fields_not_used_for_candidate_generation"] is True
    assert gate_report["guardrail_status"]["source_native_units_only"] is True
    assert gate_rows[0]["legacy_retrieved_context_ids"] == ["su-a"]
    assert gate_rows[0]["real_rag_source_atom_ids"] == ["src-a"]
    assert gate_rows[0]["candidate_generation_input_policy"] == "query_text_only"
    assert gate_rows[0]["diagnostic_critic"]["retrieval_loop_triggered"] is False


def test_run_eval_enforce_evidence_gate_before_quality_gate_artifacts_and_preserves_single_output_policy(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "gate_gold.jsonl"
    context = tmp_path / "gate_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "gate_enforce"
    write_jsonl(
        dataset,
        [
            {
                "id": "supported",
                "query": "Where is Apollo HQ?",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-hq", "chunk_id": "src-hq", "text": "Apollo HQ is in Seoul."}],
            },
            {
                "id": "blocked",
                "query": "When did Project Mercury launch?",
                "expected_answer": "2026-04-12",
                "expected_evidence": [{"doc_id": "doc-date", "chunk_id": "src-date", "text": "Project Mercury launched on 2026-04-12."}],
            },
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "supported",
                "generated_answer": "Apollo HQ is in Seoul.",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "src-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "src-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
            },
            {
                "id": "blocked",
                "generated_answer": "Project Mercury launched on 2027-05-01.",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-date",
                        "chunk_id": "src-date",
                        "source_atom_id": "src-date",
                        "evidence_bundle_id": "bundle-date",
                        "text": "Project Mercury launched on 2026-04-12.",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-date",
                        "chunk_id": "src-date",
                        "source_atom_id": "src-date",
                        "evidence_bundle_id": "bundle-date",
                        "text": "Project Mercury launched on 2026-04-12.",
                    }
                ],
            },
        ],
    )
    baseline = tmp_path / "legacy_report.json"
    baseline.write_text(
        json.dumps(
            {
                "run_id": "legacy_snapshot",
                "dataset_path": dataset.as_posix(),
                "total_item_count": 2,
                "official_metric_input_rows": 0,
                "official_metric_input_rows_created": 0,
                "official_metric_input_rows_consumed": 0,
                "protected_namespaces_touched": [],
                "raw_prompt_payload_written": False,
                "raw_response_payload_written": False,
                "guardrails": {
                    "gold_mutation": False,
                    "qrels_mutation": False,
                    "label_mutation": False,
                    "answerability_label_mutation": False,
                    "expected_answer_mutation": False,
                    "expected_evidence_mutation": False,
                    "denominator_mutation": False,
                    "retriever_ranking_improvement": False,
                    "official_metric": False,
                    "official_metric_input_rows": 0,
                    "official_metric_input_rows_created": 0,
                    "official_metric_input_rows_consumed": 0,
                    "promotion_evidence": False,
                    "product_success_evidence_allowed": False,
                    "live_readiness_claim": False,
                    "protected_namespaces_touched": [],
                    "raw_prompt_payload_written": False,
                    "raw_response_payload_written": False,
                    "expected_fields_used_for_candidate_generation": False,
                    "gold_fields_used_for_candidate_generation": False,
                    "qrels_used_for_candidate_generation": False,
                    "answerability_labels_used_for_candidate_generation": False,
                    "baseline_topk_used_for_candidate_generation": False,
                    "ids_used_for_candidate_generation": False,
                },
                "index_retrieval_config": {"adapter": "repo_current_searchunit_vector_hybrid"},
                "items": [
                    {"id": "supported", "generated_answer": "Seoul"},
                    {"id": "blocked", "generated_answer": "2026-04-12"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        context_jsonl_path=context,
        output_dir=output_dir,
        top_k=2,
        run_id="gate_enforce",
        output_mode="single",
        quality_gate_baseline_path=baseline,
        evidence_gate_mode="enforce",
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    assert sorted(output_file_names(output_dir)) == [
        "legacy_real_rag_quality_gate_items.jsonl",
        "legacy_real_rag_quality_gate_report.json",
        "report.json",
    ]
    assert report["artifact_contract"]["legacy_sidecars_written"] is False
    assert report["artifact_contract"]["quality_gate_sidecars_written"] is True
    assert report["evidence_gate"]["evidence_gate_mode"] == "enforce"
    assert report["evidence_gate"]["sufficient_evidence_allowed_count"] == 1
    assert report["evidence_gate"]["insufficient_evidence_abstained_count"] == 1
    supported, blocked = report["items"]
    assert supported["answer_gate_decision"] == "allow_answer"
    assert supported["generated_answer"] == "Apollo HQ is in Seoul."
    assert blocked["answer_gate_decision"] == "block_unsupported_answer"
    assert blocked["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    gate_report = json.loads((output_dir / "legacy_real_rag_quality_gate_report.json").read_text(encoding="utf-8"))
    gate_rows = [
        json.loads(line)
        for line in (output_dir / "legacy_real_rag_quality_gate_items.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert gate_report["evidence_gate_mode"] == "enforce"
    assert gate_report["insufficient_evidence_abstained_count"] == 1
    assert {row["answer_gate_decision"] for row in gate_rows} == {"allow_answer", "block_unsupported_answer"}
    assert {row["expected_answer_match_before_gate"] for row in gate_rows} == {False, True}
    assert {row["expected_evidence_match_before_gate"] for row in gate_rows} == {True}
    assert {row["expected_evidence_match_after_gate"] for row in gate_rows} == {True}
    blocked_gate_row = next(row for row in gate_rows if row["query_id"] == "blocked")
    assert blocked_gate_row["legacy_real_answer_delta_before_gate"] == "legacy_correct_real_wrong"
    assert blocked_gate_row["expected_answer_match_after_gate"] is False
    assert blocked_gate_row["unsupported_answer_blocked"] is True
    assert blocked_gate_row["would_block_unsupported_answer"] is False


def test_evidence_resolution_artifacts_summary_registry_status_and_markdown(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    status_path = tmp_path / "status.jsonl"
    original_dataset_bytes = dataset.read_bytes() if dataset.exists() else b""
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "자동판매기 3기 방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "2026년 4월",
                "expected_evidence": [
                    {
                        "text": "자동판매기 미궁 방랑 애니메이션 제3기 방영 시기는 2026년 4월",
                        "required": True,
                    }
                ],
            }
        ],
    )
    original_dataset_bytes = dataset.read_bytes()
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "2026년 4월",
                "retrieved_contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-auto",
                        "chunk_id": "chunk-2026",
                        "score": 0.9,
                        "text": "자동판매기 미궁 방랑 애니메이션 제3기 방영 시기는 2026년 4월입니다.",
                    }
                ],
                "citations": [{"doc_id": "doc-auto", "chunk_id": "chunk-2026", "text": "자동판매기 2026년 4월"}],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=report_root / "resolved",
        context_jsonl_path=context,
        top_k=3,
        run_id="resolved",
        report_root=report_root,
        status_jsonl_path=status_path,
        append_registry=True,
        write_latest=True,
        resolve_expected_evidence=True,
        evidence_resolution_scope="both",
    )

    assert dataset.read_bytes() == original_dataset_bytes
    summary = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    item_row = summary["items"][0]
    artifact_paths = summary["artifact_paths"]
    assert output_file_names(report_root / "resolved") == ["report.json"]
    assert artifact_paths["evidence_resolution_candidates_jsonl"] == ""
    assert summary["evidence_resolution_candidates"]
    assert summary["diagnostic_metrics"]["expected_evidence_resolution_enabled"] is True
    assert summary["diagnostic_metrics"]["expected_evidence_resolution_scope"] == "both"
    assert summary["diagnostic_metrics"]["expected_evidence_row_count"] == 1
    assert summary["diagnostic_metrics"]["expected_evidence_id_missing_count"] == 1
    assert summary["diagnostic_metrics"]["expected_evidence_id_resolved_candidate_count"] == 1
    assert summary["diagnostic_metrics"]["expected_evidence_id_unresolved_count"] == 0
    assert summary["provisional_metrics"]["resolved_evidence_available_rate"]["numerator"] == 1
    assert summary["provisional_metrics"]["resolved_evidence_recall@3_provisional"]["numerator"] == 1
    assert summary["provisional_metrics"]["citation_matches_resolved_evidence_precision_provisional"]["numerator"] == 1
    assert item_row["expected_evidence_resolution"]["resolved_count"] == 1
    assert item_row["expected_evidence_resolution"]["selected_candidates"][0]["doc_id"] == "doc-auto"
    assert summary["artifact_contract"]["output_mode"] == "single"
    assert summary["guardrails"]["gold_fields_used_for_candidate_generation"] is False

    registry_row = json.loads((report_root / "runs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    latest = json.loads((report_root / "latest_fixture.json").read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8").splitlines()[0])
    assert registry_row["evidence_resolution"]["enabled"] is True
    assert registry_row["evidence_resolution"]["expected_evidence_id_resolved_candidate_count"] == 1
    assert latest["evidence_resolution"]["expected_evidence_id_resolved_candidate_count"] == 1
    assert status["evidence_id_resolved_candidate_count"] == 1


def test_report_separates_selected_evidence_supported_and_gold_correct_citations(tmp_path: Path) -> None:
    dataset = tmp_path / "citation_terms_gold.jsonl"
    context = tmp_path / "citation_terms_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "citation_terms"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-citation-terms",
                "query": "Where is Apollo HQ?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"text": "Apollo headquarters is in Seoul.", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-citation-terms",
                "generated_answer": "Apollo HQ is in Seoul.",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-selected",
                        "chunk_id": "chunk-selected",
                        "source_atom_id": "src-selected",
                        "evidence_bundle_id": "bundle-selected",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-selected",
                        "chunk_id": "chunk-selected",
                        "source_atom_id": "src-selected",
                        "evidence_bundle_id": "bundle-selected",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="citation_terms",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        resolve_expected_evidence=False,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    gate = report["evidence_gate"]
    diagnostics = report["diagnostic_metrics"]
    assert gate["citation_supported_count"] == 1
    assert gate["citation_selected_evidence_supported_count"] == 1
    assert gate["citation_supported_definition"] == "citation_target_selected_and_text_supported_by_selected_evidence"
    assert diagnostics["citation_gold_correct_checked_count_diagnostic"] == 1
    assert diagnostics["citation_gold_correct_pass_count_diagnostic"] == 0
    assert diagnostics["citation_gold_correct_rate_diagnostic"] == 0.0
    assert diagnostics["citation_gold_correct_definition"] == (
        "citation_matches_expected_evidence_when_gold_fields_available_diagnostic_only"
    )


def test_citation_gold_correct_diagnostic_passes_when_expected_evidence_matches(tmp_path: Path) -> None:
    dataset = tmp_path / "citation_gold_correct_pass_gold.jsonl"
    context = tmp_path / "citation_gold_correct_pass_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "citation_gold_correct_pass"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-citation-pass",
                "query": "Where is Apollo HQ?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"text": "Apollo HQ is in Seoul.", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-citation-pass",
                "generated_answer": "Apollo HQ is in Seoul.",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-selected",
                        "chunk_id": "chunk-selected",
                        "source_atom_id": "src-selected",
                        "evidence_bundle_id": "bundle-selected",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-selected",
                        "chunk_id": "chunk-selected",
                        "source_atom_id": "src-selected",
                        "evidence_bundle_id": "bundle-selected",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="citation_gold_correct_pass",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        resolve_expected_evidence=False,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    diagnostics = report["diagnostic_metrics"]
    assert report["evidence_gate"]["citation_selected_evidence_supported_count"] == 1
    assert diagnostics["citation_gold_correct_checked_count_diagnostic"] == 1
    assert diagnostics["citation_gold_correct_pass_count_diagnostic"] == 1
    assert diagnostics["citation_gold_correct_rate_diagnostic"] == 1.0


def test_citation_gold_correct_diagnostic_rate_is_none_without_gold_fields(tmp_path: Path) -> None:
    dataset = tmp_path / "citation_no_gold.jsonl"
    context = tmp_path / "citation_no_gold_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "citation_no_gold"
    write_jsonl(
        dataset,
        [{"id": "q-citation-no-gold", "query": "Where is Apollo HQ?", "answerability": "answerable"}],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-citation-no-gold",
                "generated_answer": "Apollo HQ is in Seoul.",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-selected",
                        "chunk_id": "chunk-selected",
                        "source_atom_id": "src-selected",
                        "evidence_bundle_id": "bundle-selected",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-selected",
                        "chunk_id": "chunk-selected",
                        "source_atom_id": "src-selected",
                        "evidence_bundle_id": "bundle-selected",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="citation_no_gold",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        resolve_expected_evidence=False,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    diagnostics = report["diagnostic_metrics"]
    assert report["evidence_gate"]["citation_selected_evidence_supported_count"] == 1
    assert diagnostics["citation_gold_correct_checked_count_diagnostic"] == 0
    assert diagnostics["citation_gold_correct_pass_count_diagnostic"] == 0
    assert diagnostics["citation_gold_correct_rate_diagnostic"] is None


def test_evidence_mapping_packet_files_human_fields_and_summary_counts(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    status_path = tmp_path / "status.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q_accept",
                "query": "자동판매기 3기 방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "2026년 4월",
                "expected_evidence": [{"text": "자동판매기 제3기 방영 시기는 2026년 4월", "required": True}],
            },
            {
                "id": "q_reject",
                "query": "다른 작품 3기 방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "2026년 4월",
                "expected_evidence": [{"text": "자동판매기 제3기 방영 시기는 2026년 4월", "required": True}],
            },
            {
                "id": "q_review",
                "query": "미츠하는 어디로 향했어?",
                "answerability": "answerable",
                "expected_answer": "도쿄",
                "expected_evidence": [{"text": "미츠하가 타키를 만나러 도쿄로 향했다", "required": True}],
            },
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q_accept",
                "generated_answer": "2026년 4월",
                "retrieved_contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-auto",
                        "chunk_id": "chunk-2026",
                        "score": 0.95,
                        "text": "TEXT source text 자동판매기 제3기 방영 시기는 2026년 4월입니다.",
                        "source_family": "TEXT",
                        "source_kind": "source_derived_semantic_snippet",
                        "source_title": "safe text source",
                    }
                ],
                "citations": [{"doc_id": "doc-auto", "chunk_id": "chunk-2026", "text": "자동판매기 2026년 4월"}],
            },
            {
                "id": "q_reject",
                "generated_answer": "2006년 10월",
                "retrieved_contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-wrong",
                        "chunk_id": "chunk-2006",
                        "score": 0.8,
                        "text": "PDF source text 다른 만화 TV 애니메이션 방영 시기는 2006년 10월입니다.",
                        "source_family": "PDF",
                        "source_kind": "source_derived_semantic_snippet",
                    }
                ],
                "citations": [{"doc_id": "doc-wrong", "chunk_id": "chunk-2006", "text": "2006년 10월"}],
            },
            {
                "id": "q_review",
                "generated_answer": "도쿄",
                "retrieved_contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-mitsuha",
                        "chunk_id": "chunk-tokyo",
                        "score": 0.7,
                        "text": "TEXT source text 미츠하는 도쿄로 향했다.",
                        "source_family": "TEXT",
                        "source_path": "C:\\Users\\sfr99\\raw\\mitsuha.txt",
                    }
                ],
                "citations": [{"doc_id": "doc-mitsuha", "chunk_id": "chunk-tokyo", "text": "미츠하 도쿄"}],
            },
        ],
    )

    original_dataset = dataset.read_bytes()
    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=report_root / "mapping_packet",
        context_jsonl_path=context,
        top_k=3,
        run_id="mapping_packet",
        report_root=report_root,
        status_jsonl_path=status_path,
        append_registry=True,
        write_latest=True,
        resolve_expected_evidence=True,
        evidence_resolution_scope="both",
        write_evidence_mapping_packet=True,
    )

    assert dataset.read_bytes() == original_dataset
    summary = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    artifact_paths = summary["artifact_paths"]
    csv_path = Path(artifact_paths["human_review_packet_csv"])
    jsonl_path = artifact_paths["evidence_mapping_review_packet_jsonl"]
    md_path = artifact_paths["evidence_mapping_review_packet_md"]
    packet_summary_path = artifact_paths["evidence_mapping_packet_summary_json"]
    assert csv_path.exists()
    assert jsonl_path == ""
    assert md_path == ""
    assert packet_summary_path == ""
    assert output_file_names(report_root / "mapping_packet") == ["human_review_packet.csv", "report.json"]

    with csv_path.open(encoding="utf-8", newline="") as handle:
        packet_rows = list(csv.DictReader(handle))
    assert packet_rows
    for row in packet_rows:
        assert row["human_mapping_decision"] == ""
        assert row["human_accepted_doc_id"] == ""
        assert row["human_accepted_chunk_id"] == ""
        assert row["human_answerability_label"] == ""
        assert row["human_relevance_label"] == ""
        assert row["human_decision_fields_filled_by_codex"] in {"False", False}
        assert "C:\\Users" not in json.dumps(row, ensure_ascii=False)

    by_item = {row["item_id"]: row for row in packet_rows}
    assert by_item["q_accept"]["machine_recommendation"] == "likely_accept"
    assert by_item["q_reject"]["machine_recommendation"] == "likely_reject"
    assert by_item["q_review"]["machine_recommendation"] in {"review_needed", "possible_match"}
    assert "raw_path_redacted" in by_item["q_review"]["risk_flags"]

    diagnostics = summary["diagnostic_metrics"]
    assert diagnostics["evidence_mapping_packet_enabled"] is True
    assert diagnostics["evidence_mapping_packet_item_count"] == 3
    assert diagnostics["evidence_mapping_packet_likely_accept_count"] == 1
    assert diagnostics["evidence_mapping_packet_likely_reject_count"] >= 1
    assert diagnostics["source_metadata_redacted_path_count"] >= 1
    assert diagnostics["human_decision_fields_filled_by_codex"] is False
    assert summary["human_review_packet"]["row_count"] == len(packet_rows)

    registry_row = json.loads((report_root / "runs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    latest = json.loads((report_root / "latest_fixture.json").read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8").splitlines()[0])
    assert registry_row["evidence_mapping_packet"]["enabled"] is True
    assert latest["evidence_mapping_packet"]["human_decision_fields_filled_by_codex"] is False
    assert status["evidence_mapping_packet"]["evidence_mapping_packet_likely_accept_count"] == 1


def test_reviewed_evidence_mapping_csv_ingest_applies_run_local_overlay_and_opens_strict_denominators(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    reviewed_csv = tmp_path / "reviewed_mapping.csv"
    output_dir = tmp_path / "reports" / "rag_eval" / "reviewed_ingest"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-reviewed",
                "query": "Mercury launch date?",
                "answerability": "unknown",
                "expected_answer": "2026-04-12",
                "expected_evidence": [
                    {
                        "text": "Mercury launch window opens on 2026-04-12",
                        "required": True,
                    }
                ],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-reviewed",
                "generated_answer": "2026-04-12",
                "retrieved_contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-reviewed",
                        "chunk_id": "chunk-reviewed",
                        "score": 0.97,
                        "text": "Mercury launch window opens on 2026-04-12.",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-reviewed",
                        "chunk_id": "chunk-reviewed",
                        "text": "Mercury launch window opens on 2026-04-12.",
                    }
                ],
            }
        ],
    )
    with reviewed_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "query_id",
                "expected_evidence_index",
                "candidate_doc_id",
                "candidate_chunk_id",
                "candidate_text_hash",
                "machine_recommendation",
                "human_accept",
                "human_answerability_label",
                "human_notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "query_id": "q-reviewed",
                "expected_evidence_index": "0",
                "candidate_doc_id": "doc-reviewed",
                "candidate_chunk_id": "chunk-reviewed",
                "candidate_text_hash": "sha256:test-reviewed",
                "machine_recommendation": "likely_accept",
                "human_accept": "yes",
                "human_answerability_label": "answerable",
                "human_notes": "reviewer accepted source-native evidence mapping",
            }
        )

    original_dataset = dataset.read_bytes()
    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="reviewed_ingest",
        reviewed_evidence_mapping_csv=reviewed_csv,
    )

    assert dataset.read_bytes() == original_dataset
    assert output_file_names(output_dir) == ["report.json", "reviewed_evidence_mapping_patch.json"]
    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert report["reviewed_mapping_input_path"] == reviewed_csv.as_posix()
    assert report["reviewed_mapping_applied"] is True
    assert report["reviewed_mapping_row_count"] == 1
    assert report["reviewed_mapping"]["accepted_mapping_count"] == 1
    assert report["reviewed_mapping"]["answerability_label_applied_count"] == 1
    assert report["reviewed_mapping"]["gold_or_qrels_mutation"] is False
    assert report["reviewed_mapping"]["machine_recommendation_treated_as_gold"] is False
    assert report["diagnostic_metrics"]["reviewed_mapping_row_count"] == 1
    assert report["diagnostic_metrics"]["reviewed_mapping_applied"] is True
    assert report["strict_metrics"]["exact_or_alias_answer_correctness"]["denominator"] == 1
    assert report["strict_metrics"]["evidence_recall@1"]["denominator"] == 1
    assert report["strict_metrics"]["evidence_recall@1"]["numerator"] == 1
    assert report["answerability_distribution"]["answerable"] == 1
    assert report["answerability_distribution"]["unknown"] == 0
    assert report["denominator_changes"]["strict_answer_denominator"]["before"] == 0
    assert report["denominator_changes"]["strict_answer_denominator"]["after"] == 1
    assert report["denominator_changes"]["strict_evidence_denominator"]["before"] == 0
    assert report["denominator_changes"]["strict_evidence_denominator"]["after"] == 1
    assert report["items"][0]["reviewed_mapping_applied"] is True
    assert report["items"][0]["expected_evidence"][0]["doc_id"] == "doc-reviewed"
    assert report["items"][0]["expected_evidence"][0]["chunk_id"] == "chunk-reviewed"
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_fields_used_for_candidate_generation"] is False
    assert report["human_decision_fields_filled_by_codex"] is False
    patch = json.loads((output_dir / "reviewed_evidence_mapping_patch.json").read_text(encoding="utf-8"))
    assert patch["row_count"] == 1
    assert patch["changes"][0]["query_id"] == "q-reviewed"
    assert "answerability_label_applied" in patch["changes"][0]["change_types"]
    assert "expected_evidence_id_mapping_applied" in patch["changes"][0]["change_types"]


def test_reviewed_evidence_mapping_csv_rejects_machine_recommendation_as_human_decision(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    reviewed_csv = tmp_path / "reviewed_mapping.csv"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "Mercury launch date?",
                "answerability": "unknown",
                "expected_answer": "2026-04-12",
                "expected_evidence": [{"text": "Mercury launch window opens on 2026-04-12"}],
            }
        ],
    )
    write_jsonl(context, [{"id": "q1", "generated_answer": "", "retrieved_contexts": [], "citations": []}])
    with reviewed_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["query_id", "candidate_doc_id", "candidate_chunk_id", "machine_recommendation", "human_accept"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "query_id": "q1",
                "candidate_doc_id": "doc1",
                "candidate_chunk_id": "chunk1",
                "machine_recommendation": "likely_accept",
                "human_accept": "likely_accept",
            }
        )

    with pytest.raises(DatasetSchemaError, match="machine recommendation"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=tmp_path / "reports" / "rag_eval" / "reject_machine",
            context_jsonl_path=context,
            reviewed_evidence_mapping_csv=reviewed_csv,
        )


def test_reviewed_evidence_mapping_csv_rejects_unreviewed_blank_human_fields(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    reviewed_csv = tmp_path / "reviewed_mapping.csv"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "Mercury launch date?",
                "answerability": "unknown",
                "expected_answer": "2026-04-12",
                "expected_evidence": [{"text": "Mercury launch window opens on 2026-04-12"}],
            }
        ],
    )
    write_jsonl(context, [{"id": "q1", "generated_answer": "", "retrieved_contexts": [], "citations": []}])
    with reviewed_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["query_id", "candidate_doc_id", "candidate_chunk_id", "machine_recommendation", "human_accept"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "query_id": "q1",
                "candidate_doc_id": "doc1",
                "candidate_chunk_id": "chunk1",
                "machine_recommendation": "likely_accept",
                "human_accept": "",
            }
        )

    with pytest.raises(DatasetSchemaError, match="explicit human"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=tmp_path / "reports" / "rag_eval" / "reject_blank",
            context_jsonl_path=context,
            reviewed_evidence_mapping_csv=reviewed_csv,
        )


def test_cli_smoke_with_reviewed_evidence_mapping_csv_ingest(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    reviewed_csv = tmp_path / "reviewed_mapping.csv"
    output_dir = tmp_path / "reports" / "rag_eval" / "cli_reviewed_ingest"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-cli-reviewed",
                "query": "Mercury launch date?",
                "answerability": "unknown",
                "expected_answer": "2026-04-12",
                "expected_evidence": [{"text": "Mercury launch window opens on 2026-04-12", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-cli-reviewed",
                "generated_answer": "2026-04-12",
                "retrieved_contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-cli",
                        "chunk_id": "chunk-cli",
                        "score": 0.99,
                        "text": "Mercury launch window opens on 2026-04-12.",
                    }
                ],
                "citations": [{"doc_id": "doc-cli", "chunk_id": "chunk-cli", "text": "Mercury launch window opens on 2026-04-12."}],
            }
        ],
    )
    with reviewed_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "query_id",
                "expected_evidence_index",
                "candidate_doc_id",
                "candidate_chunk_id",
                "machine_recommendation",
                "human_accept",
                "human_answerability_label",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "query_id": "q-cli-reviewed",
                "expected_evidence_index": "0",
                "candidate_doc_id": "doc-cli",
                "candidate_chunk_id": "chunk-cli",
                "machine_recommendation": "likely_accept",
                "human_accept": "yes",
                "human_answerability_label": "answerable",
            }
        )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai.scripts.rag_actual_eval",
            "--dataset",
            str(dataset),
            "--context-jsonl",
            str(context),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "cli_reviewed_ingest",
            "--top-k",
            "1",
            "--reviewed-evidence-mapping-csv",
            str(reviewed_csv),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert output_file_names(output_dir) == ["report.json", "reviewed_evidence_mapping_patch.json"]
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["reviewed_mapping_applied"] is True
    assert report["reviewed_mapping_input_path"] == reviewed_csv.as_posix()
    assert report["strict_metrics"]["exact_or_alias_answer_correctness"]["denominator"] == 1
    assert report["strict_metrics"]["evidence_recall@1"]["denominator"] == 1
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["expected_fields_used_for_candidate_generation"] is False


def test_evidence_mapping_packet_comparison_metrics_are_new_or_unavailable() -> None:
    previous = {
        "run_id": "previous",
        "top_k": 3,
        "strict_metrics": {},
        "provisional_metrics": {},
        "diagnostic_metrics": {},
    }
    current = {
        "run_id": "current",
        "top_k": 3,
        "strict_metrics": {},
        "provisional_metrics": {},
        "diagnostic_metrics": {
            "evidence_mapping_packet_candidate_count": 3,
            "evidence_mapping_packet_likely_accept_count": 1,
            "evidence_mapping_packet_possible_match_count": 1,
            "evidence_mapping_packet_review_needed_count": 0,
            "evidence_mapping_packet_likely_reject_count": 1,
            "source_metadata_resolved_candidate_count": 2,
            "source_metadata_unresolved_candidate_count": 1,
        },
    }

    comparison = build_run_comparison(previous, current, target_label="previous")
    by_metric = {row["metric"]: row for row in comparison["rows"]}

    assert by_metric["evidence_mapping_packet_candidate_count"]["current"] == "3"
    assert by_metric["evidence_mapping_packet_likely_accept_count"]["interpretation"] == "unavailable"
    assert by_metric["source_metadata_resolved_candidate_count"]["current"] == "2"


def test_cli_smoke_with_evidence_mapping_packet_and_previous_comparison(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    status_path = tmp_path / "status.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"text": "Seoul is the capital city of Korea", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "Seoul",
                "retrieved_contexts": [
                    {"rank": 1, "doc_id": "doc-seoul", "chunk_id": "c1", "score": 0.9, "text": "Seoul is the capital city of Korea"}
                ],
                "citations": [{"doc_id": "doc-seoul", "chunk_id": "c1", "text": "Seoul is the capital city of Korea"}],
            }
        ],
    )

    first = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai.scripts.rag_actual_eval",
            "--dataset",
            str(dataset),
            "--context-jsonl",
            str(context),
            "--top-k",
            "3",
            "--run-id",
            "cli_mapping_before",
            "--output-dir",
            str(report_root / "cli_mapping_before"),
            "--report-root",
            str(report_root),
            "--status-jsonl",
            str(status_path),
            "--append-registry",
            "--write-latest",
            "--resolve-expected-evidence",
            "--evidence-resolution-scope",
            "both",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr

    second = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai.scripts.rag_actual_eval",
            "--dataset",
            str(dataset),
            "--context-jsonl",
            str(context),
            "--top-k",
            "3",
            "--run-id",
            "cli_mapping_after",
            "--output-dir",
            str(report_root / "cli_mapping_after"),
            "--report-root",
            str(report_root),
            "--status-jsonl",
            str(status_path),
            "--append-registry",
            "--write-latest",
            "--compare-to",
            "previous",
            "--resolve-expected-evidence",
            "--evidence-resolution-scope",
            "both",
            "--write-human-review-packet",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert second.returncode == 0, second.stderr
    summary = json.loads((report_root / "cli_mapping_after" / "report.json").read_text(encoding="utf-8"))
    assert summary["diagnostic_metrics"]["evidence_mapping_packet_enabled"] is True
    assert summary["comparison"]["target_run_id"] == "cli_mapping_before"
    assert output_file_names(report_root / "cli_mapping_after") == ["human_review_packet.csv", "report.json"]


def test_resolved_evidence_e2e_variant_still_requires_answer_judge_pass(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "2026년 4월",
                "expected_evidence": [{"text": "방영 시기는 2026년 4월", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "2025년 4월",
                "retrieved_contexts": [{"rank": 1, "doc_id": "doc-date", "chunk_id": "c1", "score": 0.9, "text": "방영 시기는 2026년 4월"}],
                "citations": [{"doc_id": "doc-date", "chunk_id": "c1", "text": "방영 시기는 2026년 4월"}],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "judge_fail",
        context_jsonl_path=context,
        top_k=1,
        run_id="judge_fail",
        resolve_expected_evidence=True,
        evidence_resolution_scope="both",
    )
    summary = json.loads(bundle.summary_path.read_text(encoding="utf-8"))

    assert summary["provisional_metrics"]["resolved_evidence_recall@1_provisional"]["numerator"] == 1
    assert summary["provisional_metrics"]["judged_answer_correctness_provisional"]["numerator"] == 0
    assert summary["provisional_metrics"]["e2e_rag_success_resolved_evidence_provisional"]["numerator"] == 0


def test_comparison_includes_new_evidence_resolution_metrics() -> None:
    def metric(name: str, numerator: int, denominator: int, tier: str = "provisional") -> dict:
        return {
            "name": name,
            "tier": tier,
            "numerator": numerator,
            "denominator": denominator,
            "score": None if denominator == 0 else round(numerator / denominator, 6),
        }

    previous = {
        "run_id": "previous",
        "top_k": 3,
        "strict_metrics": {},
        "provisional_metrics": {},
        "diagnostic_metrics": {},
    }
    current = {
        "run_id": "current",
        "top_k": 3,
        "strict_metrics": {},
        "provisional_metrics": {
            "resolved_evidence_available_rate": metric("resolved_evidence_available_rate", 1, 2),
            "resolved_evidence_recall@3_provisional": metric("resolved_evidence_recall@3_provisional", 1, 1),
            "citation_matches_resolved_evidence_precision_provisional": metric(
                "citation_matches_resolved_evidence_precision_provisional",
                1,
                1,
            ),
            "citation_matches_resolved_evidence_recall_provisional": metric(
                "citation_matches_resolved_evidence_recall_provisional",
                1,
                1,
            ),
            "e2e_rag_success_resolved_evidence_provisional": metric(
                "e2e_rag_success_resolved_evidence_provisional",
                0,
                1,
            ),
        },
        "diagnostic_metrics": {
            "expected_evidence_id_unresolved_count": 0,
            "expected_evidence_id_resolved_candidate_count": 1,
            "expected_evidence_resolution_candidate_count": 2,
        },
    }

    comparison = build_run_comparison(previous, current, target_label="previous")
    by_metric = {row["metric"]: row for row in comparison["rows"]}

    assert by_metric["resolved_evidence_available_rate"]["interpretation"] == "new metric"
    assert by_metric["resolved_evidence_available_rate"]["current"] == "1/2 (0.500000)"
    assert by_metric["expected_evidence_id_resolved_candidate_count"]["interpretation"] == "unavailable"


def test_cli_smoke_with_expected_evidence_resolution_both_scope(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    status_path = tmp_path / "status.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"text": "Seoul is the capital city of Korea", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "Seoul",
                "retrieved_contexts": [{"rank": 1, "doc_id": "doc-seoul", "chunk_id": "c1", "score": 0.9, "text": "Seoul is the capital city of Korea"}],
                "citations": [{"doc_id": "doc-seoul", "chunk_id": "c1", "text": "Seoul is the capital city of Korea"}],
            }
        ],
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai.scripts.rag_actual_eval",
            "--dataset",
            str(dataset),
            "--context-jsonl",
            str(context),
            "--top-k",
            "3",
            "--run-id",
            "cli_resolution",
            "--output-dir",
            str(report_root / "cli_resolution"),
            "--report-root",
            str(report_root),
            "--status-jsonl",
            str(status_path),
            "--append-registry",
            "--write-latest",
            "--resolve-expected-evidence",
            "--evidence-resolution-scope",
            "both",
            "--count-medium-evidence-resolution",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads((report_root / "cli_resolution" / "report.json").read_text(encoding="utf-8"))
    assert summary["diagnostic_metrics"]["expected_evidence_resolution_enabled"] is True
    assert summary["artifact_paths"]["evidence_resolution_candidates_jsonl"] == ""
    assert summary["evidence_resolution_candidates"]
    assert output_file_names(report_root / "cli_resolution") == ["report.json"]


def test_report_generation_and_cli_smoke_with_tiny_fixture_dataset(tmp_path: Path) -> None:
    dataset = tmp_path / "tiny_gold.jsonl"
    context = tmp_path / "tiny_context.jsonl"
    output_dir = tmp_path / "rag_eval_output"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "What is the capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_answer_aliases": ["서울"],
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul", "required": True}],
                "tags": ["smoke"],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "Seoul",
                "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul 서울"}],
                "citations": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul 서울"}],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=3,
        run_id="unit_smoke",
        command="unit-test",
    )

    assert bundle.summary_path.exists()
    assert bundle.items_path.exists()
    assert bundle.markdown_path.exists()
    summary = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert summary["strict_metrics"]["e2e_rag_success_strict"]["score"] == 1.0
    assert summary["provisional_metrics"]["e2e_rag_success_provisional"]["score"] == 1.0
    assert summary["diagnostic_metric_details"]["answer_extracted_from_retrieved_context_rate"]["score"] == 1.0
    assert summary["diagnostic_metric_details"]["citation_points_to_retrieved_context_rate"]["score"] == 1.0
    assert summary["official_metric_input_rows"] == 0
    assert summary["official_metric_input_rows_created"] == 0
    assert summary["official_metric_input_rows_consumed"] == 0
    assert summary["protected_namespaces_touched"] == []
    assert summary["raw_prompt_payload_written"] is False
    assert summary["raw_response_payload_written"] is False
    assert summary["guardrails"]["official_metric"] is False
    assert summary["guardrails"]["promotion_evidence"] is False
    assert summary["guardrails"]["product_success_evidence_allowed"] is False
    assert summary["guardrails"]["live_readiness_claim"] is False
    assert summary["artifact_contract"]["output_mode"] == "single"
    assert "strict denominators" in summary["denominator_policy"].lower()
    assert "e2e_rag_success_provisional" in summary["provisional_metrics"]
    assert "answer_extracted_from_retrieved_context_rate" in summary["diagnostic_metric_details"]
    assert "not answer correctness" in summary["denominator_policy"]

    cli_output = tmp_path / "cli_output"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai.scripts.rag_actual_eval",
            "--dataset",
            str(dataset),
            "--context-jsonl",
            str(context),
            "--output-dir",
            str(cli_output),
            "--top-k",
            "3",
            "--run-id",
            "cli_smoke",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert output_file_names(cli_output) == ["report.json"]


def test_registry_latest_status_and_index_accumulate_without_promoting_metrics(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    status_path = tmp_path / "status.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "Seoul",
                "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul"}],
                "citations": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul"}],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=report_root / "fixture_run",
        context_jsonl_path=context,
        top_k=3,
        run_id="fixture_run",
        command="unit-test accumulation",
        report_root=report_root,
        status_jsonl_path=status_path,
        append_registry=True,
        write_latest=True,
    )

    registry_path = report_root / "runs.jsonl"
    registry_rows = [json.loads(line) for line in registry_path.read_text(encoding="utf-8").splitlines()]
    assert [row["run_id"] for row in registry_rows] == ["fixture_run"]
    assert registry_rows[0]["summary_json"] == bundle.summary_path.as_posix()
    assert registry_rows[0]["strict_metrics_summary"]["e2e_rag_success_strict"]["score"] == 1.0
    assert registry_rows[0]["guardrails"]["gold_mutation"] is False
    assert registry_rows[0]["guardrails"]["official_metric"] is False
    assert (report_root / "latest.json").exists()
    assert (report_root / "latest_fixture.json").exists()
    latest_fixture = json.loads((report_root / "latest_fixture.json").read_text(encoding="utf-8"))
    assert latest_fixture["run_id"] == "fixture_run"
    assert latest_fixture["summary_json"] == bundle.summary_path.as_posix()
    assert (report_root / "README.md").read_text(encoding="utf-8").startswith("# Actual RAG Eval Runs")

    status_rows = [json.loads(line) for line in status_path.read_text(encoding="utf-8").splitlines()]
    assert status_rows[0]["event_type"] == "actual_rag_eval_run"
    assert status_rows[0]["run_id"] == "fixture_run"
    assert status_rows[0]["guardrails"]["qrels_mutation"] is False
    assert status_rows[0]["short_result_interpretation"] == "baseline recorded; no comparison target supplied"


def test_repeated_run_id_does_not_overwrite_historical_artifacts(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "same_run"
    write_jsonl(
        dataset,
        [{"id": "q1", "query": "capital?", "answerability": "answerable", "expected_answer": "Seoul"}],
    )
    write_jsonl(context, [{"id": "q1", "generated_answer": "Seoul", "retrieved_contexts": [], "citations": []}])

    run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="same_run",
    )

    with pytest.raises(DatasetSchemaError, match="already contains actual RAG eval artifacts"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=output_dir,
            context_jsonl_path=context,
            top_k=1,
            run_id="same_run",
        )


def test_actual_rag_guardrail_validation_rejects_ambiguous_registry_inputs() -> None:
    valid = {
        "run_id": "guarded",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
    }
    validate_actual_rag_guardrails(valid)

    missing = dict(valid)
    missing.pop("official_metric_input_rows")
    with pytest.raises(DatasetSchemaError, match="official_metric_input_rows"):
        validate_actual_rag_guardrails(missing)

    nonzero = dict(valid, official_metric_input_rows_consumed=1)
    with pytest.raises(DatasetSchemaError, match="official_metric_input_rows_consumed"):
        validate_actual_rag_guardrails(nonzero)

    touched = dict(valid, protected_namespaces_touched=["ai/eval/eval_queries"])
    with pytest.raises(DatasetSchemaError, match="protected_namespaces_touched"):
        validate_actual_rag_guardrails(touched)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("official_metric_input_rows", 1),
        ("official_metric_input_rows_created", 1),
        ("official_metric_input_rows_consumed", 1),
        ("raw_prompt_payload_written", True),
        ("raw_response_payload_written", True),
    ],
)
def test_actual_rag_guardrail_validation_rejects_forbidden_top_level_flags(field: str, value) -> None:
    summary = {
        "run_id": "guarded",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
    }
    summary[field] = value

    with pytest.raises(DatasetSchemaError, match=field):
        validate_actual_rag_guardrails(summary)


@pytest.mark.parametrize(
    "field",
    [
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "answerability_label_mutation",
        "expected_answer_mutation",
        "expected_evidence_mutation",
        "denominator_mutation",
        "retriever_ranking_improvement",
        "official_metric",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "live_readiness_claim",
    ],
)
def test_actual_rag_guardrail_validation_rejects_forbidden_guardrail_flags(field: str) -> None:
    summary = {
        "run_id": "guarded",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
    }
    summary["guardrails"][field] = True

    with pytest.raises(DatasetSchemaError, match=field):
        validate_actual_rag_guardrails(summary)


def test_run_comparison_handles_deltas_missing_metrics_and_denominator_changes() -> None:
    def metric(name: str, numerator: int, denominator: int, tier: str = "provisional") -> dict:
        return {
            "name": name,
            "tier": tier,
            "numerator": numerator,
            "denominator": denominator,
            "score": None if denominator == 0 else round(numerator / denominator, 6),
        }

    previous = {
        "run_id": "previous",
        "top_k": 10,
        "strict_metrics": {
            "exact_or_alias_answer_correctness": metric("exact_or_alias_answer_correctness", 1, 2, "strict"),
            "evidence_recall@10": metric("evidence_recall@10", 1, 2, "strict"),
            "citation_precision": metric("citation_precision", 1, 1, "strict"),
        },
        "provisional_metrics": {
            "judged_answer_correctness_provisional": metric("judged_answer_correctness_provisional", 1, 2),
            "weak_evidence_match_recall@10": metric("weak_evidence_match_recall@10", 1, 2),
        },
        "diagnostic_metric_details": {
            "answer_extracted_from_retrieved_context_rate": metric(
                "answer_extracted_from_retrieved_context_rate",
                1,
                2,
                "diagnostic",
            )
        },
        "diagnostic_metrics": {"retrieval_empty_rate": 0.5, "pipeline_error_count": 2},
    }
    current = {
        "run_id": "current",
        "top_k": 10,
        "strict_metrics": {
            "exact_or_alias_answer_correctness": metric("exact_or_alias_answer_correctness", 2, 4, "strict"),
            "evidence_recall@10": metric("evidence_recall@10", 2, 2, "strict"),
            "citation_precision": metric("citation_precision", 1, 1, "strict"),
            "citation_recall": metric("citation_recall", 0, 0, "strict"),
        },
        "provisional_metrics": {
            "judged_answer_correctness_provisional": metric("judged_answer_correctness_provisional", 2, 2),
            "weak_evidence_match_recall@10": metric("weak_evidence_match_recall@10", 1, 2),
            "e2e_rag_success_provisional": metric("e2e_rag_success_provisional", 1, 2),
        },
        "diagnostic_metric_details": {
            "answer_extracted_from_retrieved_context_rate": metric(
                "answer_extracted_from_retrieved_context_rate",
                2,
                2,
                "diagnostic",
            )
        },
        "diagnostic_metrics": {
            "retrieval_empty_rate": 0.25,
            "pipeline_error_count": 1,
            "expected_evidence_id_unresolved_count": 3,
        },
    }

    comparison = build_run_comparison(previous, current, target_label="previous")
    by_metric = {row["metric"]: row for row in comparison["rows"]}

    assert comparison["guardrails"]["official_metric"] is False
    assert comparison["guardrails"]["promotion_evidence"] is False
    assert comparison["interpretation_policy"] == "nonprod_diagnostic_comparison_only"
    assert by_metric["judged_answer_correctness_provisional"]["delta"] == 0.5
    assert by_metric["judged_answer_correctness_provisional"]["interpretation"] == "improved"
    assert by_metric["weak_evidence_match_recall@10"]["interpretation"] == "unchanged"
    assert by_metric["exact_or_alias_answer_correctness"]["interpretation"] == "denominator changed"
    assert by_metric["citation_recall"]["interpretation"] == "unavailable"
    assert by_metric["retrieval_empty_rate"]["interpretation"] == "improved"
    assert by_metric["pipeline_error_count"]["interpretation"] == "improved"
    assert by_metric["expected_evidence_id_unresolved_count"]["interpretation"] == "unavailable"
    assert by_metric["answer_extracted_from_retrieved_context_rate"]["interpretation"] == "diagnostic only"


def test_repo_current_bm25_adapter_does_not_use_raw_gold_or_xlsx_shortcuts() -> None:
    source = inspect.getsource(RepoCurrentBm25Adapter)
    forbidden_fragments = [
        "openpyxl",
        "load_workbook",
        "formula",
        "normalized_value",
        "target_locator",
        "gold_locator",
        "query_id",
        "case_id",
        "expected_answer",
        "expected_evidence",
    ]

    for fragment in forbidden_fragments:
        assert fragment not in source


def test_expected_evidence_resolver_does_not_use_raw_xlsx_or_gold_locator_shortcuts() -> None:
    source = inspect.getsource(ExpectedEvidenceResolver)
    forbidden_fragments = [
        "openpyxl",
        "load_workbook",
        "formula",
        "normalized_value",
        "target_locator",
        "gold_locator",
        "query_id",
        "case_id",
    ]

    for fragment in forbidden_fragments:
        assert fragment not in source


def test_markdown_report_includes_previous_run_comparison_section(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context_before = tmp_path / "context_before.jsonl"
    context_after = tmp_path / "context_after.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul", "required": True}],
            }
        ],
    )
    write_jsonl(context_before, [{"id": "q1", "generated_answer": "", "retrieved_contexts": [], "citations": []}])
    write_jsonl(
        context_after,
        [
            {
                "id": "q1",
                "generated_answer": "Seoul",
                "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul"}],
                "citations": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul"}],
            }
        ],
    )

    previous = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "before",
        context_jsonl_path=context_before,
        top_k=1,
        run_id="before",
        output_mode="legacy",
    )
    current = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "after",
        context_jsonl_path=context_after,
        top_k=1,
        run_id="after",
        comparison_summary=previous.summary,
        comparison_target="previous",
        output_mode="legacy",
    )

    report = current.markdown_path.read_text(encoding="utf-8")
    summary = json.loads(current.summary_path.read_text(encoding="utf-8"))
    assert "## Previous Run Comparison" in report
    assert "| Metric | Tier | Previous | Current | Delta | Interpretation |" in report
    assert summary["comparison"]["target_run_id"] == "before"
    assert summary["comparison"]["rows"]


def test_run_id_helper_is_filesystem_safe_and_collision_safe(tmp_path: Path) -> None:
    report_root = tmp_path / "reports" / "rag_eval"
    dataset = tmp_path / "gold_queries_text_namu_v2_1_question_gold_v2.csv"
    dataset.write_text("id,query\n", encoding="utf-8")

    explicit = make_actual_rag_run_id(dataset, explicit_run_id="manual_run_01", report_root=report_root)
    assert explicit == "manual_run_01"
    with pytest.raises(DatasetSchemaError, match="filesystem-safe"):
        make_actual_rag_run_id(dataset, explicit_run_id="../bad", report_root=report_root)

    first = make_actual_rag_run_id(dataset, generated_at="2026-06-10T01:02:03Z", report_root=report_root)
    (report_root / first).mkdir(parents=True)
    (report_root / first / "rag_eval_summary.json").write_text("{}", encoding="utf-8")
    second = make_actual_rag_run_id(dataset, generated_at="2026-06-10T01:02:03Z", report_root=report_root)
    assert first == "actual_rag_eval_text_gold_20260610_010203"
    assert second == "actual_rag_eval_text_gold_20260610_010203_02"


def test_latest_pointer_can_be_written_without_registry_append(tmp_path: Path) -> None:
    report_root = tmp_path / "reports" / "rag_eval"
    summary = {
        "run_id": "manual",
        "generated_at": "2026-06-10T01:02:03Z",
        "dataset_path": "ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv",
        "output_dir": "reports/rag_eval/manual",
        "artifact_paths": {
            "summary_json": "reports/rag_eval/manual/rag_eval_summary.json",
            "markdown_report": "reports/rag_eval/manual/rag_eval_report.md",
            "items_jsonl": "reports/rag_eval/manual/rag_eval_items.jsonl",
        },
        "schema_version": "actual_rag_eval.v1",
        "run_kind": "actual_rag_eval_metric_generation_nonprod",
        "total_item_count": 6,
        "top_k": 10,
        "judge_mode": "heuristic",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
    }

    pointers = write_latest_pointers(summary, report_root=report_root)

    assert (report_root / "latest.json") in pointers
    assert (report_root / "latest_text_gold.json") in pointers
    assert json.loads((report_root / "latest_text_gold.json").read_text(encoding="utf-8"))["run_id"] == "manual"


def test_status_event_append_is_compact_and_guardrailed(tmp_path: Path) -> None:
    status_path = tmp_path / "status.jsonl"
    summary = {
        "run_id": "run",
        "generated_at": "2026-06-10T01:02:03Z",
        "dataset_path": "fixture_gold.jsonl",
        "output_dir": "reports/rag_eval/run",
        "total_item_count": 1,
        "strict_metrics": {},
        "provisional_metrics": {},
        "diagnostic_metrics": {"pipeline_error_count": 0, "retrieval_empty_rate": 0.0},
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
    }

    event = append_actual_rag_status_event(summary, status_jsonl_path=status_path)

    assert event["event_type"] == "actual_rag_eval_run"
    assert event["next_suggested_repair_target"] == "monitor_accumulated_actual_rag_eval_runs"
    assert json.loads(status_path.read_text(encoding="utf-8"))["run_id"] == "run"


def test_cli_appends_registry_latest_status_and_compares_to_previous(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context_before = tmp_path / "context_before.jsonl"
    context_after = tmp_path / "context_after.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    status_path = tmp_path / "status.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul", "required": True}],
            }
        ],
    )
    write_jsonl(context_before, [{"id": "q1", "generated_answer": "", "retrieved_contexts": [], "citations": []}])
    write_jsonl(
        context_after,
        [
            {
                "id": "q1",
                "generated_answer": "Seoul",
                "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul"}],
                "citations": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul"}],
            }
        ],
    )

    base_cmd = [
        sys.executable,
        "-m",
        "ai.scripts.rag_actual_eval",
        "--dataset",
        str(dataset),
        "--top-k",
        "1",
        "--append-registry",
        "--write-latest",
        "--report-root",
        str(report_root),
        "--status-jsonl",
        str(status_path),
    ]
    first = subprocess.run(
        [
            *base_cmd,
            "--context-jsonl",
            str(context_before),
            "--run-id",
            "cli_previous",
            "--output-dir",
            str(report_root / "cli_previous"),
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    second = subprocess.run(
        [
            *base_cmd,
            "--context-jsonl",
            str(context_after),
            "--run-id",
            "cli_current",
            "--output-dir",
            str(report_root / "cli_current"),
            "--compare-to",
            "previous",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    registry_rows = [json.loads(line) for line in (report_root / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["run_id"] for row in registry_rows] == ["cli_previous", "cli_current"]
    assert json.loads((report_root / "latest_fixture.json").read_text(encoding="utf-8"))["run_id"] == "cli_current"
    status_rows = [json.loads(line) for line in status_path.read_text(encoding="utf-8").splitlines()]
    assert [row["run_id"] for row in status_rows] == ["cli_previous", "cli_current"]
    current_summary = json.loads((report_root / "cli_current" / "report.json").read_text(encoding="utf-8"))
    assert current_summary["comparison"]["target_run_id"] == "cli_previous"
    assert current_summary["comparison"]["rows"]
    assert output_file_names(report_root / "cli_current") == ["report.json"]
