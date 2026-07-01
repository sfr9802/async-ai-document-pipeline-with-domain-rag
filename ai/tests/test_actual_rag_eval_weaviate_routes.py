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


def same_row_period_cell_packet(
    *,
    source_atom_id: str = "src-period-cell",
    doc_id: str = "doc-xlsx",
    sheet: str = "일반현황",
    cell_range: str = "A5002:J5051",
    cell: str = "H5002",
    row_index_1based: str = "5002",
    row_label: str = "장기요양기관이름=부여효요양원",
    column_label: str = "지정일자",
    raw_value: str = "2015-06-12",
    year: int = 2015,
    month: int = 6,
    day: int = 12,
) -> dict[str, object]:
    return {
        "schema_version": "actual_rag_eval.xlsx.same_row_period_cell.v1",
        "provenance_policy": "source_owned_same_row_period_cell_v1",
        "source_atom_id": source_atom_id,
        "doc_id": doc_id,
        "sheet": sheet,
        "cell_range": cell_range,
        "cell": cell,
        "row_index_1based": row_index_1based,
        "row_label": row_label,
        "column_label": column_label,
        "raw_value": raw_value,
        "parsed_date": raw_value,
        "year": year,
        "month": month,
        "day": day,
    }


def same_row_period_cells_json(**kwargs: object) -> str:
    return json.dumps([same_row_period_cell_packet(**kwargs)], ensure_ascii=False)


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


def test_xlsx_row_value_bundle_recall_preserves_materialization_hydration(tmp_path: Path) -> None:
    class BundleRecallWeaviateClient(FakeWeaviateSourceAtomClient):
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
            bundle_scoped = (
                filters.get("source_family") == "XLSX"
                and filters.get("doc_id") == "doc-care"
                and filters.get("sheet") == "일반현황"
                and filters.get("cell_range") == "A5002:J5051"
                and filters.get("row_index_1based") == "5002"
                and filters.get("candidate_surface_materialization") == "xlsx_row_value_bundle_v1"
            )
            rows: list[dict] = []
            for obj in self.objects:
                if _filter_mismatch(obj, filters):
                    continue
                source_atom_id = obj.get("source_atom_id")
                if bundle_scoped and source_atom_id == "srcatom-care-row-bundle":
                    row = dict(obj)
                    row["_score"] = 1.0
                    row["_backend"] = kwargs["mode"]
                    rows.append(row)
                elif not bundle_scoped and "candidate_surface_materialization" not in filters:
                    if source_atom_id == "srcatom-care-address":
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
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_row_value_bundle_recall"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx-row-value-bundle-recall",
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
                709,
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
    row_bundle = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                710,
                text=(
                    "xlsx_row_value_bundle_v1 | row_label=장기요양기관이름=부여효요양원 | "
                    "target_column=기관별 상세주소 | display_value=충청남도 부여군 석성면 왕릉로 773 | "
                    "source_date_alias=2015년 6월 | source_date_alias=2015년 | source_date_alias=6월"
                ),
            ),
            "source_atom_id": "srcatom-care-row-bundle",
            "evidence_bundle_id": "bundle-care-row-bundle",
            "doc_id": "doc-care",
            "chunk_id": "chunk-care-row-bundle",
            "source_family": "XLSX",
            "granularity": "table_row",
            "retrieval_route": "xlsx_table",
            "sheet": "일반현황",
            "cell_range": "A5002:J5051",
            "row_index_1based": "5002",
            "row_label": "장기요양기관이름=부여효요양원",
            "target_column": "기관별 상세주소",
            "display_value": "충청남도 부여군 석성면 왕릉로 773",
            "candidate_surface_materialization": "xlsx_row_value_bundle_v1",
            "candidate_surface_materialization_policy": (
                "source_native_xlsx_row_value_bundle_same_row_period_v1"
            ),
            "source_date_aliases_json": json.dumps(["2015년 6월", "2015년", "6월"], ensure_ascii=False),
            "source_atom_ids_json": json.dumps(["srcatom-care-address", "srcatom-care-date"], ensure_ascii=False),
        },
        config,
    )
    wrong_row_bundle = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                711,
                text=(
                    "xlsx_row_value_bundle_v1 | row_label=장기요양기관이름=다른요양원 | "
                    "target_column=기관별 상세주소 | display_value=충청남도 부여군 다른면 1 | "
                    "source_date_alias=2015년 6월"
                ),
            ),
            "source_atom_id": "srcatom-care-wrong-row-bundle",
            "evidence_bundle_id": "bundle-care-wrong-row-bundle",
            "doc_id": "doc-care",
            "chunk_id": "chunk-care-wrong-row-bundle",
            "source_family": "XLSX",
            "granularity": "table_row",
            "retrieval_route": "xlsx_table",
            "sheet": "일반현황",
            "cell_range": "A5002:J5051",
            "row_index_1based": "2",
            "row_label": "장기요양기관이름=다른요양원",
            "target_column": "기관별 상세주소",
            "display_value": "충청남도 부여군 다른면 1",
            "candidate_surface_materialization": "xlsx_row_value_bundle_v1",
            "candidate_surface_materialization_policy": (
                "source_native_xlsx_row_value_bundle_same_row_period_v1"
            ),
            "source_date_aliases_json": json.dumps(["2015년 6월"], ensure_ascii=False),
            "source_atom_ids_json": json.dumps(["srcatom-care-wrong-row-address"], ensure_ascii=False),
        },
        config,
    )
    client = BundleRecallWeaviateClient(objects=[address, row_bundle, wrong_row_bundle])
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="route_selected",
        route_filter_fields_available={
            "source_family": True,
            "granularity": True,
            "retrieval_route": True,
            "candidate_surface_materialization": True,
        },
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=5,
        run_id="xlsx_row_value_bundle_recall",
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
    bundle_context = next(
        context for context in contexts if context.get("source_atom_id") == "srcatom-care-row-bundle"
    )
    bundle_queries = [
        query
        for query in client.query_log
        if query["filters"].get("candidate_surface_materialization") == "xlsx_row_value_bundle_v1"
    ]
    assert bundle_queries
    assert any(query["filters"].get("row_index_1based") == "5002" for query in bundle_queries)
    assert bundle_context["candidate_surface_materialization"] == "xlsx_row_value_bundle_v1"
    assert bundle_context["candidate_surface_materialization_policy"] == (
        "source_native_xlsx_row_value_bundle_same_row_period_v1"
    )
    assert json.loads(bundle_context["source_date_aliases_json"]) == ["2015년 6월", "2015년", "6월"]
    assert json.loads(bundle_context["source_atom_ids_json"]) == ["srcatom-care-address", "srcatom-care-date"]
    assert bundle_context["xlsx_scoped_expansion_scope_type"] == "same_cell_range_row"
    assert bundle_context["xlsx_row_value_bundle_recall_policy"] == "source_owned_same_row_bundle_recall_v1"
    assert all(context["source_atom_id"] != "srcatom-care-wrong-row-bundle" for context in contexts)
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


def test_xlsx_row_value_bundle_initial_hit_survives_scoped_expansion_collapse(tmp_path: Path) -> None:
    class InitialBundleHitWeaviateClient(FakeWeaviateSourceAtomClient):
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
                and filters.get("doc_id") == "doc-row702"
                and filters.get("sheet") == "일반현황"
                and filters.get("cell_range") == "A702:J751"
                and filters.get("row_index_1based") == "702"
            )
            bundle_scoped = row_scoped and filters.get("candidate_surface_materialization") == "xlsx_row_value_bundle_v1"
            rows: list[dict] = []
            for obj in self.objects:
                if _filter_mismatch(obj, filters):
                    continue
                source_atom_id = obj.get("source_atom_id")
                if bundle_scoped and source_atom_id == "srcatom-row702-bundle":
                    row = dict(obj)
                    row["_score"] = 1.0
                    row["_backend"] = kwargs["mode"]
                    rows.append(row)
                elif row_scoped and "candidate_surface_materialization" not in filters:
                    if source_atom_id == "srcatom-row702-postal-cell":
                        row = dict(obj)
                        row["_score"] = 1.0
                        row["_backend"] = kwargs["mode"]
                        rows.append(row)
                elif not row_scoped and "candidate_surface_materialization" not in filters:
                    if source_atom_id == "srcatom-row702-bundle":
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
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_row_value_bundle_initial_hit"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx-row702-bundle-initial-hit",
                "query": "2020년 11월에 지정된 하얀민들레노인요양원의 우편번호",
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
        "doc_id": "doc-row702",
        "source_family": "XLSX",
        "retrieval_route": "xlsx_table",
        "sheet": "일반현황",
        "cell_range": "A702:J751",
        "row_index_1based": "702",
        "row_label": "장기요양기관이름=하얀민들레노인요양원",
        "target_column": "우편번호",
        "display_value": "41786",
    }
    postal_cell = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                709,
                text=(
                    "row_label=장기요양기관이름=하얀민들레노인요양원 | "
                    "target_column=우편번호 | display_value=41786"
                ),
            ),
            **common,
            "source_atom_id": "srcatom-row702-postal-cell",
            "evidence_bundle_id": "bundle-row702-postal-cell",
            "chunk_id": "chunk-row702-postal-cell",
            "granularity": "cell",
            "cell": "C702",
            "column_label": "우편번호",
        },
        config,
    )
    row_bundle = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                710,
                text=(
                    "xlsx_row_value_bundle_v1 | row_label=장기요양기관이름=하얀민들레노인요양원 | "
                    "target_column=우편번호 | display_value=41786 | "
                    "source_date_alias=2020년 11월 | source_date_alias=2020년 | source_date_alias=11월"
                ),
            ),
            **common,
            "source_atom_id": "srcatom-row702-bundle",
            "evidence_bundle_id": "bundle-row702-bundle",
            "chunk_id": "chunk-row702-bundle",
            "granularity": "table_row",
            "candidate_surface_materialization": "xlsx_row_value_bundle_v1",
            "candidate_surface_materialization_policy": (
                "source_native_xlsx_row_value_bundle_same_row_period_v1"
            ),
            "source_date_aliases_json": json.dumps(["2020년 11월", "2020년", "11월"], ensure_ascii=False),
            "source_atom_ids_json": json.dumps(
                ["srcatom-row702-postal-cell", "srcatom-row702-designated-date"],
                ensure_ascii=False,
            ),
            "cell": "C702",
            "column_label": "우편번호",
        },
        config,
    )
    client = InitialBundleHitWeaviateClient(objects=[row_bundle, postal_cell])
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="route_selected",
        route_filter_fields_available={
            "source_family": True,
            "granularity": True,
            "retrieval_route": True,
            "candidate_surface_materialization": True,
        },
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=5,
        run_id="xlsx_row_value_bundle_initial_hit",
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
    bundle_context = next(
        (context for context in contexts if context.get("source_atom_id") == "srcatom-row702-bundle"),
        None,
    )
    assert bundle_context is not None, json.dumps(contexts, ensure_ascii=False)
    assert bundle_context["candidate_surface_materialization"] == "xlsx_row_value_bundle_v1"
    assert bundle_context["candidate_surface_materialization_policy"] == (
        "source_native_xlsx_row_value_bundle_same_row_period_v1"
    )
    assert json.loads(bundle_context["source_date_aliases_json"]) == ["2020년 11월", "2020년", "11월"]
    assert json.loads(bundle_context["source_atom_ids_json"]) == [
        "srcatom-row702-postal-cell",
        "srcatom-row702-designated-date",
    ]
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


def test_xlsx_row_value_bundle_recall_skips_when_materialization_filter_unavailable() -> None:
    class RaisingBundleFilterClient(FakeWeaviateSourceAtomClient):
        def query(self, **kwargs: object) -> list[dict]:
            filters = dict(kwargs["filters"])
            if "candidate_surface_materialization" in filters:
                raise AssertionError("bundle materialization filter should be skipped when unavailable")
            self.query_log.append({"filters": filters})
            return []

    config = WeaviateSourceAtomConfig.from_env(
        {
            "RAG_VECTOR_DB": "weaviate",
            "WEAVIATE_URL": "http://localhost:8080",
            "WEAVIATE_COLLECTION_SOURCE_ATOM": "SourceAtomNonprodRouteSelectedV1",
            "WEAVIATE_NAMESPACE": "actual_rag_eval_nonprod",
            "WEAVIATE_SCHEMA_VERSION": "weaviate_source_atom_v2",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
        }
    )
    client = RaisingBundleFilterClient(objects=[])
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="route_selected",
        route_filter_fields_available={
            "source_family": True,
            "granularity": True,
            "retrieval_route": True,
            "candidate_surface_materialization": False,
        },
    )

    contexts = adapter._query_xlsx_row_value_bundle_contexts_for_scope(
        "bm25",
        "2015년 6월 부여효요양원 기관별 상세주소",
        {
            "scope_type": "same_cell_range_row",
            "filters": {
                "source_family": "XLSX",
                "doc_id": "doc-care",
                "sheet": "일반현황",
                "cell_range": "A5002:J5051",
                "row_index_1based": "5002",
            },
            "source_atom_id": "srcatom-care-address",
        },
        filters=adapter._base_filters(),
        existing_ids=set(),
    )

    assert contexts == []
    assert client.query_log == []


def test_xlsx_row_value_bundle_hydrates_same_row_period_cell_packet(tmp_path: Path) -> None:
    class PeriodCellPacketWeaviateClient(FakeWeaviateSourceAtomClient):
        def query(self, **kwargs: object) -> list[dict]:
            self.query_log.append({"filters": dict(kwargs["filters"])})
            return [dict(obj, _score=1.0, _backend=kwargs["mode"]) for obj in self.objects][
                : int(kwargs["limit"])
            ]

    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_row_value_bundle_period_cells"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx-row702-period-cell-packet",
                "query": "2020년 11월에 지정된 하얀민들레노인요양원의 우편번호",
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
    period_cells_json = json.dumps(
        [
            {
                "schema_version": "actual_rag_eval.xlsx.same_row_period_cell.v1",
                "provenance_policy": "source_owned_same_row_period_cell_v1",
                "source_atom_id": "srcatom-row702-designated-date",
                "doc_id": "doc-row702",
                "sheet": "일반현황",
                "cell_range": "A702:J751",
                "cell": "H702",
                "row_index_1based": "702",
                "row_label": "장기요양기관이름=하얀민들레노인요양원",
                "column_label": "지정일자",
                "raw_value": "2020-11-26",
                "parsed_date": "2020-11-26",
                "year": 2020,
                "month": 11,
                "day": 26,
            }
        ],
        ensure_ascii=False,
    )
    row_bundle = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(
                710,
                text=(
                    "xlsx_row_value_bundle_v1 | row_label=장기요양기관이름=하얀민들레노인요양원 | "
                    "target_column=우편번호 | display_value=41786"
                ),
            ),
            "source_atom_id": "srcatom-row702-bundle",
            "evidence_bundle_id": "bundle-row702-bundle",
            "doc_id": "doc-row702",
            "chunk_id": "chunk-row702-bundle",
            "source_family": "XLSX",
            "granularity": "table_row",
            "retrieval_route": "xlsx_table",
            "sheet": "일반현황",
            "cell_range": "A702:J751",
            "row_index_1based": "702",
            "row_label": "장기요양기관이름=하얀민들레노인요양원",
            "target_column": "우편번호",
            "display_value": "41786",
            "candidate_surface_materialization": "xlsx_row_value_bundle_v1",
            "candidate_surface_materialization_policy": (
                "source_owned_manifest_snapshot_no_gold_qrels_labels_or_normalized_fields_v1"
            ),
            "same_row_period_cells_json": period_cells_json,
        },
        config,
    )
    adapter = WeaviateSourceAtomAdapter(
        config=config,
        client=PeriodCellPacketWeaviateClient(objects=[row_bundle]),
        embedding_provider=FakeWeaviateBgeM3EmbeddingProvider(),
        requested_backend="weaviate-hybrid",
        retrieval_route_mode="route_selected",
        route_filter_fields_available={
            "source_family": True,
            "granularity": True,
            "retrieval_route": True,
            "candidate_surface_materialization": True,
        },
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=5,
        run_id="xlsx_row_value_bundle_period_cells",
        output_mode="single",
        retrieval_surface="source-native",
        retrieval_backend="weaviate-hybrid",
        retrieval_adapter=adapter,
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="markdown-portfolio",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    bundle_context = next(
        context
        for context in report["items"][0]["retrieved_contexts"]
        if context.get("source_atom_id") == "srcatom-row702-bundle"
    )
    period_cells = json.loads(bundle_context["same_row_period_cells_json"])
    assert period_cells[0]["cell"] == "H702"
    assert period_cells[0]["raw_value"] == "2020-11-26"
    assert period_cells[0]["parsed_date"] == "2020-11-26"
    assert period_cells[0]["year"] == 2020
    assert period_cells[0]["month"] == 11
    assert period_cells[0]["source_atom_id"] == "srcatom-row702-designated-date"
    assert bundle_context["candidate_surface_materialization"] == "xlsx_row_value_bundle_v1"


def test_weaviate_source_atom_rejects_poisoned_same_row_period_cell_packet() -> None:
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
    poisoned_packet = same_row_period_cell_packet(
        source_atom_id="srcatom-date",
        doc_id="doc-xlsx",
        sheet="일반현황",
        cell_range="A2:J51",
        cell="H2",
        row_index_1based="2",
        row_label="장기요양기관이름=청운노인요양원",
        column_label="지정일자",
        raw_value="2008-06-25",
        year=2008,
        month=6,
        day=25,
    )
    poisoned_packet["formula"] = "=SECRET()"

    record = source_atom_record_from_mapping(
        {
            **weaviate_source_atom_record(711, text="청운노인요양원 지정일자"),
            "source_family": "XLSX",
            "source_atom_id": "srcatom-bundle",
            "doc_id": "doc-xlsx",
            "same_row_period_cells_json": json.dumps([poisoned_packet], ensure_ascii=False),
        },
        config,
    )

    assert "same_row_period_cells_json" not in record


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


def test_agentic_xlsx_repair_explainer_rejects_intent_only_when_axes_missing() -> None:
    axis_inspection = actual_rag_eval.AgenticXlsxAxisInspectionRecord(
        has_required_period_axis=True,
        has_required_entity_axis=True,
        has_required_measure_axis=True,
        has_display_value=False,
        missing_axes=("display_value",),
        source_owned_axis_evidence={
            "period": "matched",
            "row_entity": "matched",
            "target_column": "matched",
            "display_value": "missing",
        },
    )
    explanation = actual_rag_eval.AgenticXlsxRepairExplanationRecord(
        primary_failure_family="intent_anchor_only",
        secondary_failure_families=(),
        safe_to_simulate_intent_removal=False,
        repair_recommendation="repair missing XLSX display_value axis before any intent-token simulation",
        evidence_summary="candidate is still missing display_value after the XLSX locator tool",
    )

    with pytest.raises(DatasetSchemaError, match="missing axes cannot be reported as intent-only"):
        actual_rag_eval.validate_agentic_xlsx_repair_explainer_output(
            "cp03",
            explanation,
            axis_inspection=axis_inspection,
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


def test_agentic_xlsx_regated_simulator_preserves_protected_tokens_and_axis_gap() -> None:
    candidate = actual_rag_eval.XlsxLocatorEvidenceCandidateRecord(
        item_index=0,
        candidate_index=0,
        source_family="XLSX",
        tool_name=actual_rag_eval.XLSX_LOCATOR_TOOL_NAME,
        tool_policy=actual_rag_eval.XLSX_LOCATOR_TOOL_POLICY,
        source_atom_id="src-regated-sim",
        evidence_bundle_id="bundle-regated-sim",
        doc_id="doc-regated-sim",
        sheet="2020년 2월",
        cell_range="A1:D4",
        row_label="일산선",
        target_column="수송인원",
        matched_query_anchors=("2020년", "2월"),
        missing_query_anchors_after_tool=("무엇입니까", "일산선"),
        matched_validated_required_axes=("period", "row_entity", "target_column"),
        missing_validated_required_axes=("display_value",),
        confidence_tier="high",
        accepted_for_regating=False,
        rejection_reason="missing_query_anchor_after_tool",
    )
    axis_inspection = actual_rag_eval.agentic_xlsx_axis_inspector_tool(candidate)
    verification = actual_rag_eval.AgenticXlsxProtectedAnchorVerifierRecord(
        proposed_removed_tokens=("무엇입니까", "일산선"),
        approved_removed_tokens=("무엇입니까",),
        rejected_removed_tokens=("일산선",),
        protected_rejection_reasons={"일산선": "route or line anchor must be preserved"},
    )

    simulation = actual_rag_eval.agentic_xlsx_regated_candidate_simulator_tool(
        candidate,
        approved_removed_tokens=("무엇입니까",),
        protected_tokens_preserved=("일산선",),
        axis_inspection=axis_inspection,
    )

    assert simulation.original_rejection_reason == "missing_query_anchor_after_tool"
    assert simulation.simulated_rejection_reason == "missing_query_anchor_after_tool"
    assert simulation.approved_removed_tokens == ("무엇입니까",)
    assert simulation.protected_tokens_preserved == ("일산선",)
    assert simulation.axis_status_after_simulation == {
        "missing_axes": ["display_value"],
        "remaining_missing_query_anchors": ["일산선"],
    }
    assert simulation.would_be_accepted_by_existing_gate is False
    assert simulation.report_only_diagnostic is True
    assert simulation.official_metric is False
    actual_rag_eval.validate_agentic_xlsx_regated_candidate_simulator_output(
        "cp04",
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


def _require_cp09_materializer_symbol(name: str) -> object:
    if not hasattr(actual_rag_eval, name):
        pytest.fail(
            f"CP09 RED: missing {name} for xlsx_required_axis_materializer_tool contract"
        )
    return getattr(actual_rag_eval, name)


def test_xlsx_required_axis_materializer_rejects_alias_only_period_package() -> None:
    tool = _require_cp09_materializer_symbol("xlsx_required_axis_materializer_tool")
    answer_candidate = {
        "source_family": "XLSX",
        "doc_id": "doc-row702",
        "source_atom_id": "srcatom-row702-postal-cell",
        "sheet": "일반현황",
        "cell_range": "A702:J751",
        "row_index_1based": "702",
        "row_label": "장기요양기관이름=하얀민들레노인요양원",
        "target_column": "우편번호",
        "display_value": "41786",
        "matched_validated_required_axes": ["row_entity", "target_column", "display_value"],
        "missing_validated_required_axes": ["period"],
    }

    materialized = tool(
        answer_candidate=answer_candidate,
        query_focus_contract={
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {"period": ["2020-11", "2020년 11월"]},
        },
        source_owned_contexts=[
            {
                "doc_id": "doc-row702",
                "sheet": "일반현황",
                "cell_range": "A702:J751",
                "row_index_1based": "702",
                "source_date_aliases_json": json.dumps(["2020년 11월", "2020년", "11월"], ensure_ascii=False),
            }
        ],
    )

    assert materialized.materialized_axes == ()
    assert materialized.rejected_context_count == 1


def test_xlsx_required_axis_materializer_validator_rejects_alias_only_period_package() -> None:
    validate_output = _require_cp09_materializer_symbol(
        "validate_agentic_xlsx_required_axis_materializer_output"
    )

    materialized = {
        "schema_version": actual_rag_eval.AGENTIC_XLSX_REQUIRED_AXIS_MATERIALIZER_SCHEMA_VERSION,
        "tool_name": "xlsx_required_axis_materializer_tool",
        "materialized_axes": ("period",),
        "scope_proof": {"doc_id": "doc-care", "sheet": "일반현황", "cell_range": "A5002:J5051"},
        "axis_packages": {
            "period": {
                "aliases": ["2015년 6월", "2015년", "6월"],
                "provenance_policy": "source_owned_same_row_period_alias_v1",
            }
        },
        "accepted_for_regating": False,
        "report_only_diagnostic": True,
        "official_metric": False,
    }

    with pytest.raises(DatasetSchemaError, match="missing period_cells"):
        validate_output("alias_only_period_package", materialized)


def test_xlsx_required_axis_materializer_uses_same_row_period_cell_packet() -> None:
    tool = _require_cp09_materializer_symbol("xlsx_required_axis_materializer_tool")
    validate_output = _require_cp09_materializer_symbol(
        "validate_agentic_xlsx_required_axis_materializer_output"
    )
    answer_candidate = {
        "source_family": "XLSX",
        "doc_id": "doc-row702",
        "source_atom_id": "srcatom-row702-postal-cell",
        "sheet": "일반현황",
        "cell_range": "A702:J751",
        "row_index_1based": "702",
        "row_label": "장기요양기관이름=하얀민들레노인요양원",
        "target_column": "우편번호",
        "display_value": "41786",
        "matched_validated_required_axes": ["row_entity", "target_column", "display_value"],
        "missing_validated_required_axes": ["period"],
    }

    materialized = tool(
        answer_candidate=answer_candidate,
        query_focus_contract={
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {"period": ["2020-11", "2020년 11월"]},
        },
        source_owned_contexts=[
            {
                "doc_id": "doc-row702",
                "sheet": "일반현황",
                "cell_range": "A702:J751",
                "row_index_1based": "702",
                "same_row_period_cells_json": json.dumps(
                    [
                        {
                            "schema_version": "actual_rag_eval.xlsx.same_row_period_cell.v1",
                            "provenance_policy": "source_owned_same_row_period_cell_v1",
                            "source_atom_id": "srcatom-row702-designated-date",
                            "doc_id": "doc-row702",
                            "sheet": "일반현황",
                            "cell_range": "A702:J751",
                            "cell": "H702",
                            "row_index_1based": "702",
                            "row_label": "장기요양기관이름=하얀민들레노인요양원",
                            "column_label": "지정일자",
                            "raw_value": "2020-11-26",
                            "parsed_date": "2020-11-26",
                            "year": 2020,
                            "month": 11,
                            "day": 26,
                        }
                    ],
                    ensure_ascii=False,
                ),
            }
        ],
    )

    validate_output("same_row_period_cell_packet", materialized)
    assert materialized.materialized_axes == ("period",)
    assert materialized.axis_packages["period"]["provenance_policy"] == "source_owned_same_row_period_cell_v1"
    assert materialized.axis_packages["period"]["period_cells"][0]["cell"] == "H702"
    assert materialized.accepted_for_regating is False
    assert materialized.report_only_diagnostic is True


def test_xlsx_required_axis_materializer_contract_materializes_same_row_period_without_acceptance() -> None:
    record_cls = _require_cp09_materializer_symbol("AgenticXlsxRequiredAxisMaterializerRecord")
    validate_output = _require_cp09_materializer_symbol(
        "validate_agentic_xlsx_required_axis_materializer_output"
    )
    tool = _require_cp09_materializer_symbol("xlsx_required_axis_materializer_tool")

    answer_candidate = {
        "source_family": "XLSX",
        "doc_id": "doc-care",
        "source_atom_id": "src-care-address",
        "sheet": "일반현황",
        "cell_range": "A5002:J5051",
        "row_index_1based": "5002",
        "row_label": "장기요양기관이름=부여효요양원",
        "target_column": "기관별 상세주소",
        "display_value": "충청남도 부여군 석성면 왕릉로 773",
        "matched_validated_required_axes": ["row_entity", "target_column", "display_value"],
        "missing_validated_required_axes": ["period"],
    }
    same_row_date_context = {
        "source_family": "XLSX",
        "doc_id": "doc-care",
        "source_atom_id": "src-care-date",
        "sheet": "일반현황",
        "cell_range": "A5002:J5051",
        "cell": "B5002",
        "row_index_1based": "5002",
        "row_label": "장기요양기관이름=부여효요양원",
        "column_label": "지정일자",
        "target_column": "지정일자",
        "display_value": "2015-06-12",
        "text": "target_column=지정일자 | 지정일자=2015-06-12",
        "same_row_period_cells_json": json.dumps(
            [
                same_row_period_cell_packet(
                    source_atom_id="src-care-date",
                    doc_id="doc-care",
                    cell="B5002",
                    row_label="장기요양기관이름=부여효요양원",
                )
            ],
            ensure_ascii=False,
        ),
    }
    broad_range_date_context = {
        "source_family": "XLSX",
        "doc_id": "doc-care",
        "source_atom_id": "src-care-range-date",
        "sheet": "일반현황",
        "cell_range": "A1:J9999",
        "target_column": "지정일자",
        "display_value": "2015-06-12",
        "text": "sheet=일반현황 | target_column=지정일자 | 지정일자=2015-06-12",
    }

    materialized = tool(
        answer_candidate=answer_candidate,
        query_focus_contract={
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2015-06", "2015년 6월"],
                "row_entity": ["부여효요양원"],
                "target_column": ["기관별 상세주소"],
                "display_value": [],
            },
        },
        source_owned_contexts=[same_row_date_context, broad_range_date_context],
    )

    assert isinstance(materialized, record_cls)
    validate_output("cp09_materializer_contract", materialized)
    assert materialized.tool_name == "xlsx_required_axis_materializer_tool"
    assert materialized.report_only_diagnostic is True
    assert materialized.official_metric is False
    assert materialized.materialized_axes == ("period",)
    assert materialized.rejected_context_count == 1
    assert materialized.scope_proof == {
        "doc_id": "doc-care",
        "sheet": "일반현황",
        "cell_range": "A5002:J5051",
        "row_index_1based": "5002",
        "row_label": "장기요양기관이름=부여효요양원",
    }
    period_package = materialized.axis_packages["period"]
    assert period_package["provenance_policy"] == "source_owned_same_row_period_cell_v1"
    assert period_package["query_period"] == {
        "year": 2015,
        "month": 6,
        "granularity": "month",
    }
    assert period_package["period_cells"] == [
        same_row_period_cell_packet(
            source_atom_id="src-care-date",
            doc_id="doc-care",
            cell="B5002",
            row_label="장기요양기관이름=부여효요양원",
        )
    ]
    assert materialized.axis_packages["period"]["provenance_policy"] == (
        "source_owned_same_row_period_cell_v1"
    )
    assert materialized.accepted_for_regating is False
    encoded = json.dumps(materialized.axis_packages, ensure_ascii=False)
    for forbidden in (
        "expected_answer",
        "expected_evidence",
        "qrels",
        "labels",
        "file_name",
        "title",
        "formula",
        "NORMALIZED_VALUE",
        "normalized_value",
    ):
        assert forbidden not in encoded


def test_xlsx_required_axis_materializer_runstore_contract_stays_separate_from_locator_acceptance(
    tmp_path: Path,
) -> None:
    action_record_cls = _require_cp09_materializer_symbol(
        "XlsxRequiredAxisMaterializerActionRecord"
    )
    run_record_cls = _require_cp09_materializer_symbol(
        "XlsxRequiredAxisMaterializerRunRecord"
    )
    run_store_cls = _require_cp09_materializer_symbol("XlsxRequiredAxisMaterializerRunStore")
    validate_run_store = _require_cp09_materializer_symbol(
        "validate_xlsx_required_axis_materializer_run_store"
    )

    action = action_record_cls(
        item_index=0,
        candidate_index=0,
        tool_name="xlsx_required_axis_materializer_tool",
        execution_status="materialized_axis_package",
        materialized_axes=("period",),
        missing_axes_before=("period",),
        missing_axes_after=(),
        scope_proof={
            "doc_id": "doc-care",
            "sheet": "일반현황",
            "cell_range": "A5002:J5051",
            "row_index_1based": "5002",
        },
        axis_packages={
            "period": {
                "period_cells": [
                    same_row_period_cell_packet(
                        source_atom_id="src-care-date",
                        doc_id="doc-care",
                        cell="B5002",
                        row_label="장기요양기관이름=부여효요양원",
                    )
                ],
                "provenance_policy": "source_owned_same_row_period_cell_v1",
            }
        },
        report_only_diagnostic=True,
        official_metric=False,
        accepted_for_regating=False,
    )
    record = run_record_cls(
        schema_version="actual_rag_eval.xlsx_required_axis_materializer.v1",
        enabled=True,
        report_only_diagnostic=True,
        official_metric=False,
        tool_name="xlsx_required_axis_materializer_tool",
        action_count=1,
        materialized_action_count=1,
        accepted_candidate_count=0,
        actions=(action,),
    )
    run_store_path = tmp_path / "run.sqlite"

    run_store_cls(run_store_path).write_run_record(
        run_id="cp09_xlsx_required_axis_materializer",
        dataset_slug="unit",
        collection="unit",
        record=record,
    )

    with sqlite3.connect(run_store_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "axis_materializer_actions" in tables
        row = conn.execute(
            "SELECT tool_name, materialized_axes_json, accepted_for_regating, "
            "report_only_diagnostic, official_metric, axis_packages_json "
            "FROM axis_materializer_actions"
        ).fetchone()
        assert row is not None
        assert row["tool_name"] == "xlsx_required_axis_materializer_tool"
        assert json.loads(row["materialized_axes_json"]) == ["period"]
        assert row["accepted_for_regating"] == 0
        assert row["report_only_diagnostic"] == 1
        assert row["official_metric"] == 0
        assert json.loads(row["axis_packages_json"]) == {
            "period": {
                "period_cells": [
                    same_row_period_cell_packet(
                        source_atom_id="src-care-date",
                        doc_id="doc-care",
                        cell="B5002",
                        row_label="장기요양기관이름=부여효요양원",
                    )
                ],
                "provenance_policy": "source_owned_same_row_period_cell_v1",
            }
        }

    validate_run_store(
        "cp09_xlsx_required_axis_materializer",
        run_store_path=run_store_path,
    )


def test_xlsx_required_axis_materializer_runstore_rejects_authoritative_or_forbidden_payloads(
    tmp_path: Path,
) -> None:
    action_record_cls = _require_cp09_materializer_symbol(
        "XlsxRequiredAxisMaterializerActionRecord"
    )
    run_record_cls = _require_cp09_materializer_symbol(
        "XlsxRequiredAxisMaterializerRunRecord"
    )
    run_store_cls = _require_cp09_materializer_symbol("XlsxRequiredAxisMaterializerRunStore")
    validate_run_store = _require_cp09_materializer_symbol(
        "validate_xlsx_required_axis_materializer_run_store"
    )

    authoritative_path = tmp_path / "authoritative.sqlite"
    run_store_cls(authoritative_path).write_run_record(
        run_id="cp10_authoritative_materializer",
        dataset_slug="unit",
        collection="unit",
        record=run_record_cls(
            schema_version="actual_rag_eval.xlsx_required_axis_materializer.v1",
            enabled=True,
            report_only_diagnostic=True,
            official_metric=False,
            tool_name="xlsx_required_axis_materializer_tool",
            action_count=0,
            materialized_action_count=0,
            accepted_candidate_count=1,
            actions=(),
        ),
    )
    with pytest.raises(ValueError, match="accepted_candidate_count"):
        validate_run_store(
            "cp10_authoritative_materializer",
            run_store_path=authoritative_path,
        )

    forbidden_path = tmp_path / "forbidden.sqlite"
    action = action_record_cls(
        item_index=0,
        candidate_index=0,
        tool_name="xlsx_required_axis_materializer_tool",
        execution_status="materialized_axis_package",
        materialized_axes=("period",),
        missing_axes_before=("period",),
        missing_axes_after=(),
        scope_proof={"doc_id": "doc-care", "sheet": "일반현황", "cell_range": "A5002:J5051"},
        axis_packages={
            "period": {
                "period_cells": [
                    same_row_period_cell_packet(
                        source_atom_id="src-care-date",
                        doc_id="doc-care",
                        cell="B5002",
                        row_label="장기요양기관이름=부여효요양원",
                    )
                ],
                "provenance_policy": "source_owned_same_row_period_cell_v1",
                "raw_tool_payload": {"expected_answer": "oracle shortcut"},
            }
        },
        report_only_diagnostic=True,
        official_metric=False,
        accepted_for_regating=False,
    )
    run_store_cls(forbidden_path).write_run_record(
        run_id="cp10_forbidden_materializer",
        dataset_slug="unit",
        collection="unit",
        record=run_record_cls(
            schema_version="actual_rag_eval.xlsx_required_axis_materializer.v1",
            enabled=True,
            report_only_diagnostic=True,
            official_metric=False,
            tool_name="xlsx_required_axis_materializer_tool",
            action_count=1,
            materialized_action_count=1,
            accepted_candidate_count=0,
            actions=(action,),
        ),
    )
    with pytest.raises(ValueError, match="forbidden"):
        validate_run_store(
            "cp10_forbidden_materializer",
            run_store_path=forbidden_path,
        )


def test_xlsx_required_axis_materializer_runstore_records_period_cell_without_direct_acceptance(
    tmp_path: Path,
) -> None:
    query = "2015년 6월에 지정된 부여효요양원의 기관별 상세주소는 무엇입니까?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"period": "2015-06", "facility_name": "부여효요양원"},
            "target_axis": {"column": "기관별 상세주소", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2015-06", "2015년 6월"],
                "row_entity": ["부여효요양원"],
                "target_column": ["기관별 상세주소"],
                "display_value": [],
            },
        },
    )
    answer_context = {
        "doc_id": "doc-care-materializer-runtime",
        "chunk_id": "chunk-care-address",
        "source_atom_id": "src-care-address",
        "evidence_bundle_id": "bundle-care-address",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": (
            "sheet=일반현황 | range=A5002:J5051 | row_label=장기요양기관이름=부여효요양원 | "
            "target_column=기관별 상세주소 | display_value=충청남도 부여군 석성면 왕릉로 773"
        ),
        "sheet": "일반현황",
        "cell_range": "A5002:J5051",
        "cell": "J5002",
        "row_index_1based": "5002",
        "row_label": "장기요양기관이름=부여효요양원",
        "column_label": "기관별 상세주소",
        "target_column": "기관별 상세주소",
        "display_value": "충청남도 부여군 석성면 왕릉로 773",
    }
    same_row_date_context = {
        "doc_id": "doc-care-materializer-runtime",
        "chunk_id": "chunk-care-date",
        "source_atom_id": "src-care-date",
        "evidence_bundle_id": "bundle-care-date",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": "target_column=지정일자 | 지정일자=2015-06-12",
        "sheet": "일반현황",
        "cell_range": "A5002:J5051",
        "cell": "B5002",
        "row_index_1based": "5002",
        "row_label": "장기요양기관이름=부여효요양원",
        "column_label": "지정일자",
        "target_column": "지정일자",
        "display_value": "2015-06-12",
        "same_row_period_cells_json": json.dumps(
            [
                same_row_period_cell_packet(
                    source_atom_id="src-care-date",
                    doc_id="doc-care-materializer-runtime",
                    cell="B5002",
                    row_label="장기요양기관이름=부여효요양원",
                )
            ],
            ensure_ascii=False,
        ),
    }
    broad_range_date_context = {
        "doc_id": "doc-care-materializer-runtime",
        "chunk_id": "chunk-care-range-date",
        "source_atom_id": "src-care-range-date",
        "evidence_bundle_id": "bundle-care-range-date",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": "sheet=일반현황 | range=A1:J9999 | target_column=지정일자 | 지정일자=2015-06-12",
        "sheet": "일반현황",
        "cell_range": "A1:J9999",
        "target_column": "지정일자",
        "display_value": "2015-06-12",
    }
    before_row = {
        "id": "xlsx-required-axis-materializer-runtime",
        "query": query,
        "answerability": "answerable",
        "track": "xlsx_business_structured",
        "generated_answer": "부여효요양원의 기관별 상세주소는 충청남도 부여군 석성면 왕릉로 773입니다.",
        "answer_gate_decision": "block_unsupported_answer",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [answer_context, same_row_date_context, broad_range_date_context],
        "citations": [],
        "evidence_gate": {
            "evidence_package_status": "insufficient",
            "answer_gate_decision": "block_unsupported_answer",
            "validation_reasons": ["missing_validated_required_axes"],
            "retrieved_evidence_candidates": [answer_context, same_row_date_context, broad_range_date_context],
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
    run_store_path = tmp_path / "run.sqlite"
    actual_rag_eval.XlsxLocatorRunStore(run_store_path).write_run_record(
        run_id="xlsx_required_axis_materializer_runtime",
        dataset_slug="unit",
        collection="unit",
        record=record,
        before_rows=[before_row],
        after_rows=after_rows,
    )

    tool_use = after_rows[0]["xlsx_locator_tool_use"]
    assert tool_use["execution_status"] == "skipped_missing_source_locator"
    assert tool_use["accepted_candidate_count"] == 0
    assert after_rows[0]["evidence_gate"]["selected_evidence"] == []

    with sqlite3.connect(run_store_path) as conn:
        conn.row_factory = sqlite3.Row
        candidate = conn.execute(
            "SELECT input_fields_used_json, accepted_for_regating, "
            "rejection_reason, matched_validated_required_axes_json, missing_validated_required_axes_json "
            "FROM tool_candidates WHERE source_atom_id = 'src-care-address'"
        ).fetchone()
        assert candidate is not None
        assert candidate["accepted_for_regating"] == 0
        assert candidate["rejection_reason"] == "missing_validated_required_axes_after_tool"
        assert json.loads(candidate["matched_validated_required_axes_json"]) == [
            "row_entity",
            "target_column",
            "display_value",
        ]
        assert json.loads(candidate["missing_validated_required_axes_json"]) == ["period"]
        run_row = conn.execute("SELECT record_json FROM runs").fetchone()
        run_record = json.loads(run_row["record_json"])
        materialized_candidate = next(
            item
            for item in run_record["candidates"]
            if item["source_atom_id"] == "src-care-address"
        )
        period_cells = materialized_candidate["same_row_period_cells"]
        assert period_cells == [
            same_row_period_cell_packet(
                source_atom_id="src-care-date",
                doc_id="doc-care-materializer-runtime",
                cell="B5002",
                row_label="장기요양기관이름=부여효요양원",
            )
        ]
        assert materialized_candidate["source_owned_same_candidate_package"] is True
        assert materialized_candidate["source_owned_same_candidate_package_policy"] == (
            "source_owned_same_row_period_cell_v1"
        )
        assert materialized_candidate["xlsx_required_axis_materializer_tool_output"] is True
        assert materialized_candidate["xlsx_required_axis_materializer_tool_name"] == (
            "xlsx_required_axis_materializer_tool"
        )
        assert materialized_candidate["xlsx_required_axis_materializer_execution_status"] == (
            "materialized_axis_package"
        )
        assert materialized_candidate["xlsx_required_axis_materializer_materialized_axes"] == ["period"]
        assert materialized_candidate["xlsx_required_axis_materializer_rejected_context_count"] == 2
        assert materialized_candidate["xlsx_required_axis_materializer_report_only_diagnostic"] is True
        assert materialized_candidate["xlsx_required_axis_materializer_official_metric"] is False
        assert materialized_candidate["xlsx_required_axis_materializer_accepted_for_regating"] is False
        period_cell_row = conn.execute(
            "SELECT source_atom_id, doc_id, cell, raw_value, parsed_date, year, month, day "
            "FROM tool_candidate_period_cells WHERE source_atom_id = 'src-care-date'"
        ).fetchone()
        assert dict(period_cell_row) == {
            "source_atom_id": "src-care-date",
            "doc_id": "doc-care-materializer-runtime",
            "cell": "B5002",
            "raw_value": "2015-06-12",
            "parsed_date": "2015-06-12",
            "year": 2015,
            "month": 6,
            "day": 12,
        }
        locator = actual_rag_eval.project_xlsx_locator_run_record(record, run_store_path=run_store_path)
        materializer_diagnostic = locator["xlsx_required_axis_materializer_runtime_diagnostic"]
        assert materializer_diagnostic["action_count"] == 2
        assert materializer_diagnostic["materialized_action_count"] == 1
        assert materializer_diagnostic["materializer_accepted_candidate_count"] == 0
        assert materializer_diagnostic["locator_accepted_after_materialization_count"] == 0
        assert materializer_diagnostic["execution_status_counts"] == {
            "materialized_axis_package": 1,
            "rejected_no_source_owned_same_row_period_cell": 1,
        }
        assert materializer_diagnostic["materialized_axes_counts"] == {"period": 1}
        assert materializer_diagnostic["rejected_context_count"] == 5
        assert materializer_diagnostic["period_cell_packet_count"] == 1
        assert materializer_diagnostic["period_cell_packet_policy_counts"] == {
            "source_owned_same_row_period_cell_v1": 1
        }
        assert materializer_diagnostic["source_owned_same_candidate_package_policy_counts"] == {
            "source_owned_same_row_period_cell_v1": 1
        }
        actual_rag_eval.validate_xlsx_locator_run_store(
            "xlsx_required_axis_materializer_runtime",
            locator,
            run_store_path=run_store_path,
        )

    selected_encoded = json.dumps(materialized_candidate, ensure_ascii=False)
    for forbidden in (
        "expected_answer",
        "expected_evidence",
        "qrels",
        "labels",
        "file_name",
        "title",
        "formula",
        "NORMALIZED_VALUE",
        "normalized_value",
    ):
        assert forbidden not in selected_encoded


def test_xlsx_required_axis_materializer_runtime_records_rejected_attempt() -> None:
    planner = actual_rag_eval._query_evidence_planner_summary(
        query="2020년 9월 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?",
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"period": "2020-09", "facility_name": "해뜨는요양원2"},
            "target_axis": {"column": "시도 시군구 법정동명", "value_type": "text"},
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
        },
    )
    answer_candidate = {
        "source_family": "XLSX",
        "source_atom_id": "src-no-date",
        "doc_id": "doc-no-date",
        "sheet": "일반현황",
        "cell_range": "A42:J42",
        "row_index_1based": "42",
        "row_label": "장기요양기관이름=해뜨는요양원2",
        "target_column": "시도 시군구 법정동명",
        "display_value": "대구광역시 북구 복현동",
        "text": "row_label=장기요양기관이름=해뜨는요양원2 | target_column=시도 시군구 법정동명 | display_value=대구광역시 북구 복현동",
        "matched_validated_required_axes": ["row_entity", "target_column", "display_value"],
        "missing_validated_required_axes": ["period"],
        "accepted_for_regating": False,
        "rejection_reason": "missing_validated_required_axes_after_tool",
        "input_fields_used": ["doc_id", "sheet", "cell_range", "row_label", "target_column", "display_value"],
    }
    row = {
        "query": "2020년 9월 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?",
        "query_evidence_planner": planner,
        "retrieved_contexts": [
            {
                "doc_id": "doc-no-date",
                "sheet": "일반현황",
                "cell_range": "A1:J9999",
                "target_column": "지정일자",
                "display_value": "2020-09-01",
                "text": "broad range date context only",
            }
        ],
    }

    candidates = actual_rag_eval._xlsx_locator_apply_required_axis_materializer_actions(
        row=row,
        candidates=[answer_candidate],
    )

    candidate = candidates[0]
    assert candidate["xlsx_required_axis_materializer_tool_output"] is True
    assert candidate["xlsx_required_axis_materializer_execution_status"] == (
        "rejected_no_source_owned_same_row_period_cell"
    )
    assert candidate["xlsx_required_axis_materializer_materialized_axes"] == []
    assert candidate["xlsx_required_axis_materializer_accepted_for_regating"] is False
    assert candidate["accepted_for_regating"] is False
    assert "xlsx_required_axis_materializer_tool" in candidate["input_fields_used"]


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


@pytest.mark.parametrize(
    "payload",
    [
        ["not-a-json-object"],
        {
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"period": "201905", "line_name": "우이신설선"},
            "target_axis": {"column": "승차총승객수", "value_type": "number"},
            "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
        },
        {
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": ["period", "201905"],
            "target_axis": {"column": "승차총승객수", "value_type": "number"},
            "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
            "intent_tokens": ["몇 명입니까"],
        },
        {
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"period": "201905", "line_name": "우이신설선"},
            "target_axis": ["승차총승객수"],
            "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
            "intent_tokens": ["몇 명입니까"],
        },
        {
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"period": "201905", "line_name": "우이신설선"},
            "target_axis": {"column": "승차총승객수", "value_type": "number"},
            "evidence_contract": "period,row_entity,target_column,display_value",
            "intent_tokens": ["몇 명입니까"],
        },
        {
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"period": "201905", "line_name": "우이신설선"},
            "target_axis": {"column": "승차총승객수", "value_type": "number"},
            "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
            "intent_tokens": "몇 명입니까",
        },
    ],
)
def test_query_evidence_planner_malformed_payload_variants_fall_back_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    payload: object,
) -> None:
    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[object, dict]:
        return payload, {"raw_response_sha256": "sha256:query-evidence-malformed"}

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    result = actual_rag_eval.plan_query_evidence_with_local_llm(
        "2019년 5월 우이신설선의 승차총승객수는 몇 명입니까?",
        skip_endpoint_check=True,
    )

    assert result["status"] == "malformed_payload_deterministic_fallback"
    assert result["planner_status"] == "malformed_payload_deterministic_fallback"
    assert result["validated_required_axes"] == []
    assert result["raw_payload_written"] is False
    assert result["raw_prompt_payload_written"] is False
    assert result["raw_response_payload_written"] is False
    assert result["uses_query_text_only"] is True
    assert result["uses_expected_fields"] is False
    assert result["uses_gold_fields"] is False
    assert result["uses_qrels"] is False
    assert result["uses_labels"] is False
    assert result["uses_query_or_row_or_target_ids"] is False
    assert result["uses_baseline_topk_or_legacy_outputs"] is False


def test_query_evidence_planner_empty_after_validation_falls_back_without_axes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {
                "source_family_hint": "xlsx",
                "query_task": "table_lookup",
                "row_filters": {},
                "target_axis": {"column": "SECRET_NOT_IN_QUERY", "value_type": "text"},
                "evidence_contract": ["row_entity", "target_column", "display_value"],
                "intent_tokens": ["무엇입니까"],
            },
            {"raw_response_sha256": "sha256:query-evidence-empty"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    result = actual_rag_eval.plan_query_evidence_with_local_llm(
        "무엇입니까?",
        skip_endpoint_check=True,
    )

    assert result["status"] == "empty_after_validation_deterministic_fallback"
    assert result["planner_status"] == "empty_after_validation_deterministic_fallback"
    assert result["validated_required_axes"] == []
    assert result["raw_payload_written"] is False
    assert result["uses_query_text_only"] is True
    assert result["uses_expected_fields"] is False
    assert result["uses_gold_fields"] is False
    assert result["uses_qrels"] is False
    assert result["uses_labels"] is False
    assert result["uses_query_or_row_or_target_ids"] is False


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
                        "same_row_period_cells_json": same_row_period_cells_json(
                            source_atom_id="src-xlsx-query-evidence-planner-period",
                            doc_id="doc-xlsx-query-evidence-planner",
                            sheet="2019년 5월",
                            cell_range="A17:J17",
                            cell="A17",
                            row_index_1based="17",
                            row_label="우이신설선",
                            column_label="년월",
                            raw_value="2019-05-01",
                            year=2019,
                            month=5,
                            day=1,
                        ),
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
                "same_row_period_cells_json": same_row_period_cells_json(
                    source_atom_id="src-row-period-cell",
                    doc_id="doc-cell",
                    sheet="일반현황",
                    cell_range="A752:J801",
                    cell="H752",
                    row_index_1based="752",
                    row_label=(
                        "장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526"
                    ),
                    column_label="지정일자",
                    raw_value="2014-12-31",
                    year=2014,
                    month=12,
                    day=31,
                ),
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
    assert candidate["locator_text_source"] == "source_owned_support_text"
    assert candidate["source_atom_id"] == "src-cell"
    assert "source_row_context_source_atom_id" not in candidate
    assert candidate["source_owned_same_candidate_package_policy"] == "source_owned_same_row_period_cell_v1"
    assert candidate["display_value"] == "대구광역시 북구 복현동"
    assert candidate["target_column"] == "시도 시군구 법정동명"
    assert candidate["matched_validated_required_axes"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert candidate["missing_validated_required_axes"] == []
    assert "same_row_period_cells_json" in candidate["input_fields_used"]
    assert not (
        set(candidate["input_fields_used"])
        & {"workbook_id", "workbook_version_id", "title", "file_name"}
    )
    encoded = json.dumps(candidate, ensure_ascii=False)
    for forbidden in (
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
                "row_index_1based": "752",
                "row_label": "장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526",
                "same_row_period_cells_json": same_row_period_cells_json(
                    source_atom_id="src-row-period-cell",
                    doc_id="doc-cell",
                    sheet="일반현황",
                    cell_range="A752:J801",
                    cell="H752",
                    row_index_1based="752",
                    row_label=(
                        "장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526"
                    ),
                    column_label="지정일자",
                    raw_value="2014-12-31",
                    year=2014,
                    month=12,
                    day=31,
                ),
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


def test_xlsx_locator_accepts_same_candidate_period_cell_packet_from_sibling_bundle() -> None:
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
                "same_row_period_cells_json": json.dumps(
                    [
                        same_row_period_cell_packet(
                            source_atom_id="src-date",
                            doc_id="doc-care",
                            sheet="일반현황",
                            cell_range="A5002:J5051",
                            cell="H5002",
                            row_index_1based="5002",
                            row_label=(
                                "장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176"
                            ),
                            column_label="지정일자",
                            raw_value="2015-06-01",
                            year=2015,
                            month=6,
                            day=1,
                        )
                    ],
                    ensure_ascii=False,
                ),
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
    assert candidate["locator_text_source"] == "source_owned_support_text"
    assert candidate["source_atom_id"] == "src-address"
    assert "source_row_context_source_atom_id" not in candidate
    assert candidate["source_owned_same_candidate_package_policy"] == "source_owned_same_row_period_cell_v1"
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
                        "same_row_period_cells_json": same_row_period_cells_json(
                            source_atom_id="src-row-period-cell",
                            doc_id="doc-xlsx-sibling",
                            sheet="일반현황",
                            cell_range="A752:J801",
                            cell="H752",
                            row_index_1based="752",
                            row_label=(
                                "장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526"
                            ),
                            column_label="지정일자",
                            raw_value="2014-12-31",
                            year=2014,
                            month=12,
                            day=31,
                        ),
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
    assert row["xlsx_locator_tool_use"]["source_row_context_candidate_count"] == 0
    assert row["xlsx_locator_tool_use"]["source_row_context_doc_identity_mismatch_candidate_count"] == 0
    assert row["xlsx_locator_tool_use"]["source_row_context_blocked_by_doc_identity_mismatch"] is False
    assert row["evidence_gate"]["selected_evidence"][0]["locator_text_source"] == "source_owned_support_text"
    assert "source_row_context_source_atom_id" not in row["evidence_gate"]["selected_evidence"][0]
    with sqlite3.connect(output_dir / "run.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        candidate = conn.execute(
            "SELECT locator_text_source, accepted_for_regating, source_row_context_source_atom_id, "
            "source_row_context_doc_id, input_fields_used_json, matched_validated_required_axes_json, "
            "missing_validated_required_axes_json "
            "FROM tool_candidates WHERE source_atom_id = 'src-cell'"
        ).fetchone()
        assert candidate is not None
        assert candidate["accepted_for_regating"] == 1
        assert candidate["locator_text_source"] == "source_owned_support_text"
        assert candidate["source_row_context_source_atom_id"] == ""
        assert candidate["source_row_context_doc_id"] == ""
        assert "same_row_period_cells_json" in json.loads(candidate["input_fields_used_json"])
        assert json.loads(candidate["matched_validated_required_axes_json"]) == [
            "period",
            "row_entity",
            "target_column",
            "display_value",
        ]
        assert json.loads(candidate["missing_validated_required_axes_json"]) == []
        selected = conn.execute(
            "SELECT source_atom_id, source_row_context_source_atom_id, source_row_context_doc_id "
            "FROM selected_evidence WHERE source_atom_id = 'src-cell'"
        ).fetchone()
        assert selected is not None
        assert selected["source_row_context_source_atom_id"] == ""
        assert selected["source_row_context_doc_id"] == ""
        period_cell = conn.execute(
            "SELECT source_atom_id, doc_id, row_index_1based, raw_value, provenance_policy "
            "FROM tool_candidate_period_cells WHERE source_atom_id = 'src-row-period-cell'"
        ).fetchone()
        assert dict(period_cell) == {
            "source_atom_id": "src-row-period-cell",
            "doc_id": "doc-xlsx-sibling",
            "row_index_1based": "752",
            "raw_value": "2014-12-31",
            "provenance_policy": "source_owned_same_row_period_cell_v1",
        }
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
            "source_row_context_candidate_count": 0,
            "source_row_context_doc_identity_mismatch_candidate_count": 0,
            "source_row_context_blocked_by_doc_identity_mismatch": 0,
        }
        actual_rag_eval.validate_xlsx_locator_run_store(
            "xlsx_locator_sibling_composite",
            report["xlsx_locator_tool_execute_once"],
            run_store_path=output_dir / "run.sqlite",
        )


def test_run_eval_row702_designated_query_accepts_source_owned_period_cell_without_intent_anchor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = tmp_path / "row702_designated_period_gold.jsonl"
    context = tmp_path / "row702_designated_period_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "row702_designated_period"
    query = "2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 무엇입니까?"
    row_label = "장기요양기관코드=12717000382 | 장기요양기관이름=하얀민들레노인요양원 | 시도코드=27"
    write_jsonl(
        dataset,
        [
            {
                "id": "gq_auto_018",
                "query": query,
                "answerability": "answerable",
                "track": "xlsx_business_structured",
                "target_id": "SECRET_TARGET_ID_NEVER_PROMPT",
                "baseline_topk": ["SECRET_BASELINE_NEVER_PROMPT"],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "gq_auto_018",
                "generated_answer": "41786",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-row702",
                        "chunk_id": "chunk-row702-postal-code",
                        "source_atom_id": "src-row702-postal-code",
                        "evidence_bundle_id": "bundle-row702-postal-code",
                        "source_family": "XLSX",
                        "granularity": "table_row",
                        "text": (
                            "sheet=일반현황 | range=A702:J751 | row_index_1based=702 | "
                            f"row_label={row_label} | target_column=우편번호 | display_value=41786"
                        ),
                        "sheet": "일반현황",
                        "cell_range": "A702:J751",
                        "cell": "C702",
                        "row_index_1based": "702",
                        "row_label": row_label,
                        "column_label": "우편번호",
                        "target_column": "우편번호",
                        "display_value": "41786",
                        "same_row_period_cells_json": json.dumps(
                            [
                                same_row_period_cell_packet(
                                    source_atom_id="src-row702-designated-date",
                                    doc_id="doc-row702",
                                    sheet="일반현황",
                                    cell_range="A702:J751",
                                    cell="H702",
                                    row_index_1based="702",
                                    row_label=row_label,
                                    column_label="지정일자",
                                    raw_value="2020-11-26",
                                    year=2020,
                                    month=11,
                                    day=26,
                                ),
                                same_row_period_cell_packet(
                                    source_atom_id="src-row702-install-date",
                                    doc_id="doc-row702",
                                    sheet="일반현황",
                                    cell_range="A702:J751",
                                    cell="I702",
                                    row_index_1based="702",
                                    row_label=row_label,
                                    column_label="설치신고일자",
                                    raw_value="2020-11-26",
                                    year=2020,
                                    month=11,
                                    day=26,
                                ),
                            ],
                            ensure_ascii=False,
                        ),
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
        for forbidden in (
            "gq_auto_018",
            "query_id",
            "row_id",
            "target_id",
            "SECRET_TARGET_ID_NEVER_PROMPT",
            "baseline_topk",
            "SECRET_BASELINE_NEVER_PROMPT",
            "retrieved_contexts",
            "generated_answer",
            "answerability",
            "track",
            "xlsx_business_structured",
            "expected_answer",
            "expected_evidence",
            "qrels",
            "labels",
            "41786",
            "C702",
            "H702",
            "I702",
            "src-row702",
            "allow_answer",
            "block_unsupported_answer",
            "previous_run",
            "outcome",
        ):
            assert forbidden not in prompt
        assert query in prompt
        return (
            {
                "source_family_hint": "xlsx",
                "query_task": "date_filtered_lookup",
                "row_filters": {"period": "2020-11", "facility_name": "하얀민들레노인요양원"},
                "target_axis": {"column": "우편번호", "value_type": "text"},
                "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
                "intent_tokens": ["무엇입니까", "지정된"],
            },
            {"raw_response_sha256": "sha256:row702-query-evidence-planner"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="row702_designated_period",
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
    assert row["answer_gate_decision"] == "allow_answer"
    assert row["evidence_gate"]["evidence_package_status"] == "sufficient"
    assert row["evidence_gate"]["missing_query_anchors"] == []
    assert row["evidence_gate"]["matched_validated_required_axes"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert planner["planner_status"] == "planned_validated"
    assert planner["validated_required_axes"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert planner["validated_axis_values"]["period"] == ["2020-11", "2020년 11월", "202011"]
    assert planner["raw_payload_written"] is False
    assert row["query_anchor_classifier"]["removed_intent_tokens"] == ["무엇입니까", "지정된"]
    assert row["query_anchor_classifier"]["required_anchor_after"] == [
        "11월",
        "2020년",
        "우편번호",
        "하얀민들레노인요양원",
    ]
    assert row["xlsx_locator_tool_use"]["execution_status"] == "accepted_after_regating"
    selected = row["evidence_gate"]["selected_evidence"][0]
    assert selected["source_atom_id"] == "src-row702-postal-code"
    assert selected["cell"] == "C702"
    assert selected["target_column"] == "우편번호"
    assert selected["display_value"] == "41786"

    with sqlite3.connect(output_dir / "run.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        candidate = conn.execute(
            "SELECT source_owned_same_candidate_package_policy, input_fields_used_json, "
            "accepted_for_regating, rejection_reason, matched_validated_required_axes_json, "
            "missing_validated_required_axes_json FROM tool_candidates "
            "WHERE source_atom_id = 'src-row702-postal-code'"
        ).fetchone()
        assert candidate is not None
        assert candidate["source_owned_same_candidate_package_policy"] == "source_owned_same_row_period_cell_v1"
        assert "same_row_period_cells_json" in json.loads(candidate["input_fields_used_json"])
        assert candidate["accepted_for_regating"] == 1
        assert candidate["rejection_reason"] == ""
        assert json.loads(candidate["matched_validated_required_axes_json"]) == [
            "period",
            "row_entity",
            "target_column",
            "display_value",
        ]
        assert json.loads(candidate["missing_validated_required_axes_json"]) == []
        period_cell = conn.execute(
            "SELECT source_atom_id, doc_id, cell, raw_value, parsed_date, year, month, day, provenance_policy "
            "FROM tool_candidate_period_cells WHERE source_atom_id = 'src-row702-designated-date'"
        ).fetchone()
        assert dict(period_cell) == {
            "source_atom_id": "src-row702-designated-date",
            "doc_id": "doc-row702",
            "cell": "H702",
            "raw_value": "2020-11-26",
            "parsed_date": "2020-11-26",
            "year": 2020,
            "month": 11,
            "day": 26,
            "provenance_policy": "source_owned_same_row_period_cell_v1",
        }

    encoded = json.dumps(report, ensure_ascii=False)
    assert "SECRET_TARGET_ID_NEVER_PROMPT" not in encoded
    assert "SECRET_BASELINE_NEVER_PROMPT" not in encoded
    assert "formula=" not in encoded
    assert "Formula=" not in encoded
    assert "normalized_value=" not in encoded
    assert "NORMALIZED_VALUE=" not in encoded
    assert row["expected_answer"] == ""
    assert row["expected_evidence"] == []
    assert row["gate_uses_expected_fields"] is False
    assert row["gate_uses_gold_fields"] is False
    assert planner["uses_expected_fields"] is False
    assert planner["uses_gold_fields"] is False
    assert planner["uses_qrels"] is False
    assert planner["uses_labels"] is False
    assert planner["uses_query_or_row_or_target_ids"] is False
    assert report["expected_fields_used_for_candidate_generation"] is False
    assert report["qrels_used_for_candidate_generation"] is False
    assert report["ids_used_for_candidate_generation"] is False
    assert report["target_id_used_for_candidate_generation"] is False
    assert report["baseline_topk_used_for_candidate_generation"] is False
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False


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
                        "row_index_1based": "752",
                        "row_label": "장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526",
                        "same_row_period_cells_json": same_row_period_cells_json(
                            source_atom_id="src-row-period-cell",
                            doc_id="doc-row-other",
                            sheet="일반현황",
                            cell_range="A752:J801",
                            cell="H752",
                            row_index_1based="752",
                            row_label=(
                                "장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526"
                            ),
                            column_label="지정일자",
                            raw_value="2014-12-31",
                            year=2014,
                            month=12,
                            day=31,
                        ),
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
        "same_row_period_cells_json": same_row_period_cells_json(
            source_atom_id="src-xlsx-period-cell",
            doc_id="doc-xlsx",
            sheet="일반현황",
            cell_range="A2:J51",
            cell="H2",
            row_index_1based="2",
            row_label="장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001",
            column_label="지정일자",
            raw_value="2008-06-25",
            year=2008,
            month=6,
            day=25,
        ),
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
    assert candidate["matched_validated_required_axes"] == ["row_entity", "target_column"]
    assert candidate["missing_validated_required_axes"] == ["period", "display_value"]
    assert candidate["accepted_for_regating"] is False
    encoded = json.dumps(candidate, ensure_ascii=False)
    assert "expected_answer" not in encoded
    assert "normalized_value" not in encoded
    assert "formula" not in encoded


def test_xlsx_locator_accepts_same_candidate_period_cell_packet() -> None:
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
        "id": "xlsx-source-period-cell-packet",
        "query": query,
        "generated_answer": "999명",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
    }
    context = {
        "doc_id": "doc-xlsx-period-cell-packet",
        "chunk_id": "chunk-xlsx-period-cell-packet",
        "source_atom_id": "src-xlsx-period-cell-packet",
        "evidence_bundle_id": "bundle-xlsx-period-cell-packet",
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
        "same_row_period_cells_json": json.dumps(
            [
                same_row_period_cell_packet(
                    source_atom_id="src-xlsx-period-cell",
                    doc_id="doc-xlsx-period-cell-packet",
                    sheet="철도",
                    cell_range="A302:D351",
                    cell="A302",
                    row_index_1based="302",
                    row_label="노선명=안산선",
                    column_label="년월",
                    raw_value="2019-02-01",
                    year=2019,
                    month=2,
                    day=1,
                )
            ],
            ensure_ascii=False,
        ),
    }

    candidate = actual_rag_eval._xlsx_locator_candidate_from_context(row, context)

    assert candidate is not None
    assert candidate["accepted_for_regating"] is True
    assert candidate["locator_text_source"] == "source_owned_support_text"
    assert candidate["source_owned_same_candidate_package"] is True
    assert candidate["source_owned_same_candidate_package_policy"] == "source_owned_same_row_period_cell_v1"
    assert candidate["same_row_period_cells"] == [
        same_row_period_cell_packet(
            source_atom_id="src-xlsx-period-cell",
            doc_id="doc-xlsx-period-cell-packet",
            sheet="철도",
            cell_range="A302:D351",
            cell="A302",
            row_index_1based="302",
            row_label="노선명=안산선",
            column_label="년월",
            raw_value="2019-02-01",
            year=2019,
            month=2,
            day=1,
        )
    ]
    assert "source_date_alias=" not in candidate["text"]
    assert "same_row_period_cells_json" in candidate["input_fields_used"]
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


def test_xlsx_locator_rejects_period_cell_packet_from_different_row() -> None:
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
        "id": "xlsx-source-period-cell-row-mismatch",
        "query": query,
        "generated_answer": "999명",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
    }
    context = {
        "doc_id": "doc-xlsx-period-cell-packet",
        "chunk_id": "chunk-xlsx-period-cell-packet",
        "source_atom_id": "src-xlsx-period-cell-packet",
        "evidence_bundle_id": "bundle-xlsx-period-cell-packet",
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
        "same_row_period_cells_json": same_row_period_cells_json(
            source_atom_id="src-xlsx-period-cell-other-row",
            doc_id="doc-xlsx-period-cell-packet",
            sheet="철도",
            cell_range="A302:D351",
            cell="A303",
            row_index_1based="303",
            row_label="노선명=다른노선",
            column_label="년월",
            raw_value="2019-02-01",
            year=2019,
            month=2,
            day=1,
        ),
    }

    candidate = actual_rag_eval._xlsx_locator_candidate_from_context(row, context)

    assert candidate is not None
    assert "same_row_period_cells" not in candidate
    assert candidate.get("source_owned_same_candidate_package") is not True
    assert candidate["accepted_for_regating"] is False
    assert candidate["matched_validated_required_axes"] == [
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert candidate["missing_validated_required_axes"] == ["period"]


def test_xlsx_locator_same_candidate_period_cell_packet_survives_budget() -> None:
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
        "id": "xlsx-source-period-cell-budget",
        "query": query,
        "generated_answer": "999명",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
    }
    contexts = []
    for index in range(actual_rag_eval.XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET + 1):
        context = {
            "doc_id": "doc-xlsx-period-cell-budget",
            "chunk_id": f"chunk-xlsx-period-cell-budget-{index}",
            "source_atom_id": f"src-xlsx-period-cell-budget-{index}",
            "evidence_bundle_id": f"bundle-xlsx-period-cell-budget-{index}",
            "source_family": "XLSX",
            "granularity": "table_row",
            "text": (
                "sheet=철도 | range=A302:D351 | row_label=노선명=안산선 | "
                f"target_column=수송인원 | display_value={900 + index}명"
            ),
            "sheet": "철도",
            "cell_range": "A302:D351",
            "row_index_1based": str(302 + index),
            "row_label": "노선명=안산선",
            "column_label": "수송인원",
            "target_column": "수송인원",
            "display_value": f"{900 + index}명",
        }
        if index == actual_rag_eval.XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET:
            context["same_row_period_cells_json"] = json.dumps(
                [
                    same_row_period_cell_packet(
                        source_atom_id="src-xlsx-period-cell-budget-date",
                        doc_id="doc-xlsx-period-cell-budget",
                        sheet="철도",
                        cell_range="A302:D351",
                        cell=f"A{302 + index}",
                        row_index_1based=str(302 + index),
                        row_label="노선명=안산선",
                        column_label="년월",
                        raw_value="2019-02-01",
                        year=2019,
                        month=2,
                        day=1,
                    )
                ],
                ensure_ascii=False,
            )
        contexts.append(context)
    row[actual_rag_eval.INTERNAL_XLSX_LOCATOR_SOURCE_CONTEXTS_KEY] = contexts

    candidates = actual_rag_eval._xlsx_locator_tool_candidates(row)

    accepted = [candidate for candidate in candidates if candidate.get("accepted_for_regating") is True]
    assert len(candidates) == actual_rag_eval.XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET
    assert [candidate["source_atom_id"] for candidate in accepted] == [
        "src-xlsx-period-cell-budget-5"
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
        assert candidate["accepted_for_regating"] == 0
        assert candidate["rejection_reason"] == "missing_validated_required_axes_after_tool"
        assert json.loads(candidate["matched_validated_required_axes_json"]) == [
            "row_entity",
            "target_column",
        ]
        assert json.loads(candidate["missing_validated_required_axes_json"]) == [
            "period",
            "display_value",
        ]
        actual_rag_eval.validate_xlsx_locator_run_store(
            "xlsx_locator_source_date_alias",
            locator,
            run_store_path=run_store_path,
        )


def test_run_eval_xlsx_locator_same_candidate_period_cell_packet_regates_without_alias_gate_opening(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_locator_period_cell_packet"
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
        "doc_id": "doc-xlsx-period-cell-packet",
        "chunk_id": "chunk-xlsx-period-cell-packet",
        "source_atom_id": "src-xlsx-period-cell-packet",
        "evidence_bundle_id": "bundle-xlsx-period-cell-packet",
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
        "same_row_period_cells_json": json.dumps(
            [
                same_row_period_cell_packet(
                    source_atom_id="src-xlsx-period-cell",
                    doc_id="doc-xlsx-period-cell-packet",
                    sheet="철도",
                    cell_range="A302:D351",
                    cell="A302",
                    row_index_1based="302",
                    row_label="노선명=안산선",
                    column_label="년월",
                    raw_value="2019-02-01",
                    year=2019,
                    month=2,
                    day=1,
                )
            ],
            ensure_ascii=False,
        ),
    }
    before_row = {
        "id": "xlsx_locator_period_cell_packet_q",
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
        run_id="xlsx_locator_period_cell_packet",
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
    assert row["answer_gate_decision"] == "allow_answer"
    assert row["evidence_gate"]["evidence_package_status"] == "sufficient"
    assert row["evidence_gate"]["selected_evidence"][0]["source_atom_id"] == "src-xlsx-period-cell-packet"

    with sqlite3.connect(run_store_path) as conn:
        conn.row_factory = sqlite3.Row
        candidate = conn.execute(
            "SELECT input_fields_used_json, accepted_for_regating, "
            "rejection_reason, locator_text_source, matched_validated_required_axes_json, "
            "missing_validated_required_axes_json FROM tool_candidates "
            "WHERE source_atom_id = 'src-xlsx-period-cell-packet'"
        ).fetchone()
        assert candidate is not None
        assert "same_row_period_cells_json" in json.loads(candidate["input_fields_used_json"])
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
        period_cell = conn.execute(
            "SELECT source_atom_id, doc_id, cell, raw_value, parsed_date, year, month, day "
            "FROM tool_candidate_period_cells WHERE source_atom_id = 'src-xlsx-period-cell'"
        ).fetchone()
        assert dict(period_cell) == {
            "source_atom_id": "src-xlsx-period-cell",
            "doc_id": "doc-xlsx-period-cell-packet",
            "cell": "A302",
            "raw_value": "2019-02-01",
            "parsed_date": "2019-02-01",
            "year": 2019,
            "month": 2,
            "day": 1,
        }
        actual_rag_eval.validate_xlsx_locator_run_store(
            "xlsx_locator_period_cell_packet",
            locator,
            run_store_path=run_store_path,
        )

    selected_encoded = json.dumps(row, ensure_ascii=False)
    assert "normalized_value=" not in selected_encoded
    assert "NORMALIZED_VALUE=" not in selected_encoded
    assert "formula=" not in selected_encoded
    assert "Formula=" not in selected_encoded


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
                        "same_row_period_cells_json": same_row_period_cells_json(
                            source_atom_id="src-xlsx-materialized-display-period",
                            doc_id="doc-xlsx-materialized-display",
                            sheet="일반현황",
                            cell_range="A2:J51",
                            cell="H2",
                            row_index_1based="2",
                            row_label=(
                                "장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001"
                            ),
                            column_label="지정일자",
                            raw_value="2008-06-25",
                            year=2008,
                            month=6,
                            day=25,
                        ),
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
        "same_row_period_cells_json": same_row_period_cells_json(
            source_atom_id="src-xlsx-period-cell",
            doc_id="doc-xlsx",
            sheet="일반현황",
            cell_range="A2:J51",
            cell="H2",
            row_index_1based="2",
            row_label="장기요양기관이름=청운노인요양원",
            column_label="지정일자",
            raw_value="2008-06-25",
            year=2008,
            month=6,
            day=25,
        ),
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


def test_xlsx_axis_materialization_rejects_title_file_formula_normalized_value_shortcuts() -> None:
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
        "id": "xlsx-forbidden-axis-shortcuts",
        "query": query,
        "generated_answer": "999명",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
    }
    context = {
        "doc_id": "doc-xlsx-forbidden-axis-shortcuts",
        "chunk_id": "chunk-xlsx-forbidden-axis-shortcuts",
        "source_atom_id": "src-xlsx-forbidden-axis-shortcuts",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": "sheet=철도 | range=A302:D351 | target_column=수송인원",
        "sheet": "철도",
        "cell_range": "A302:D351",
        "target_column": "수송인원",
        "title": "2019년 2월 안산선 수송인원 999명",
        "workbook": "2019년 2월 안산선.xlsx",
        "file_name": "2019-02-ansan-ridership.xlsx",
        "source_path": "D:/private/2019-02-ansan-ridership.xlsx",
        "formula": "=999",
        "normalized_value": "999",
    }

    candidate = actual_rag_eval._xlsx_locator_candidate_from_context(row, context)

    assert candidate is not None
    assert candidate["accepted_for_regating"] is False
    assert candidate["rejection_reason"] == "forbidden_input_fields_present"
    assert candidate["matched_validated_required_axes"] == ["target_column"]
    assert candidate["missing_validated_required_axes"] == ["period", "row_entity", "display_value"]
    forbidden_seen = set(candidate["forbidden_input_fields_seen"])
    assert {"source_path", "formula", "normalized_value"} <= forbidden_seen
    assert "title" not in candidate["input_fields_used"]
    assert "file_name" not in candidate["input_fields_used"]


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


def test_same_row_period_cell_packet_sanitizers_reject_extra_keys() -> None:
    poisoned_packet = same_row_period_cell_packet(
        source_atom_id="src-xlsx-period-cell",
        doc_id="doc-xlsx-period-cell",
        sheet="철도",
        cell_range="A302:D351",
        cell="A302",
        row_index_1based="302",
        row_label="노선명=안산선",
        column_label="년월",
        raw_value="2019-02-01",
        year=2019,
        month=2,
        day=1,
    )
    poisoned_packet["expected_answer"] = "SECRET_EXPECTED_NEVER_REPORT"
    poisoned_packet["raw_prompt"] = "SECRET_PROMPT_NEVER_REPORT"
    payload = {
        "source_family": "XLSX",
        "same_row_period_cells_json": json.dumps([poisoned_packet], ensure_ascii=False),
    }

    report = actual_rag_eval._sanitize_public_report_value(payload, source_native_context=True)
    runtime = actual_rag_eval._sanitize_source_native_runtime_value(payload, source_native_context=True)

    encoded = json.dumps({"report": report, "runtime": runtime}, ensure_ascii=False)
    assert "same_row_period_cells_json" not in report
    assert "same_row_period_cells_json" not in runtime
    assert "SECRET_EXPECTED_NEVER_REPORT" not in encoded
    assert "SECRET_PROMPT_NEVER_REPORT" not in encoded
    assert "expected_answer" not in encoded
    assert "raw_prompt" not in encoded


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


def test_xlsx_locator_projection_reports_agentic_axis_repair_diagnostic() -> None:
    tool_uses = (
        actual_rag_eval.XlsxLocatorToolUseRecord(
            item_index=0,
            item_id="xlsx-axis-repair-blocked",
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
            remaining_missing_query_anchors=("무엇입니까",),
            matched_validated_required_axes=("period", "row_entity", "target_column"),
            remaining_missing_validated_required_axes=("display_value",),
        ),
    )
    candidates = (
        actual_rag_eval.XlsxLocatorEvidenceCandidateRecord(
            item_index=0,
            candidate_index=0,
            source_family="XLSX",
            tool_name=actual_rag_eval.XLSX_LOCATOR_TOOL_NAME,
            tool_policy=actual_rag_eval.XLSX_LOCATOR_TOOL_POLICY,
            source_atom_id="src-axis-repair-0",
            evidence_bundle_id="bundle-axis-repair-0",
            doc_id="doc-axis-repair",
            sheet="2019년 5월",
            cell_range="A1:D4",
            row_label="우이신설선",
            target_column="승차총승객수",
            display_value="15,446,522",
            matched_query_anchors=("2019년", "5월"),
            missing_query_anchors_after_tool=("무엇입니까",),
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
            source_atom_id="src-axis-repair-1",
            evidence_bundle_id="bundle-axis-repair-1",
            doc_id="doc-axis-repair",
            sheet="2019년 5월",
            cell_range="A5:D8",
            row_label="우이신설선",
            target_column="승차총승객수",
            matched_query_anchors=("2019년",),
            missing_query_anchors_after_tool=("5월", "무엇입니까"),
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
            source_atom_id="src-axis-repair-2",
            evidence_bundle_id="bundle-axis-repair-2",
            doc_id="doc-axis-repair",
            sheet="2019년 5월",
            cell_range="A9:D12",
            row_label="우이신설선",
            target_column="승차총승객수",
            matched_query_anchors=("2019년", "5월", "우이신설선"),
            missing_query_anchors_after_tool=(),
            matched_validated_required_axes=("period", "row_entity", "target_column"),
            missing_validated_required_axes=("display_value",),
            confidence_tier="high",
            accepted_for_regating=False,
            rejection_reason="missing_validated_required_axes_after_tool",
        ),
    )
    record = actual_rag_eval.XlsxLocatorRunRecord(
        schema_version=actual_rag_eval.XLSX_LOCATOR_TOOL_EXECUTE_ONCE_SCHEMA_VERSION,
        enabled=True,
        report_only_diagnostic=True,
        official_metric=False,
        tool_name=actual_rag_eval.XLSX_LOCATOR_TOOL_NAME,
        eligible_failed_row_count=1,
        tool_invocation_count=1,
        accepted_candidate_count=0,
        rejected_candidate_count=3,
        gate_delta_record=actual_rag_eval.XlsxLocatorGateDeltaRecord(),
        guardrail_record=actual_rag_eval.XlsxLocatorGuardrailRecord(),
        tool_uses=tool_uses,
        candidates=candidates,
    )

    diagnostic = actual_rag_eval.project_xlsx_locator_run_record(record)[
        "agentic_xlsx_axis_repair_diagnostic"
    ]

    assert diagnostic["schema_version"] == "actual_rag_eval.agentic_xlsx_axis_repair_diagnostic.v1"
    assert diagnostic["axis_inspector_schema_version"] == "actual_rag_eval.agentic_xlsx_axis_inspector.v1"
    assert diagnostic["repair_explainer_schema_version"] == "actual_rag_eval.agentic_xlsx_repair_explainer.v1"
    assert diagnostic["report_only_diagnostic"] is True
    assert diagnostic["official_metric"] is False
    assert diagnostic["official_metric_input_rows"] == 0
    assert diagnostic["candidate_count"] == 3
    assert diagnostic["inspected_candidate_count"] == 3
    assert diagnostic["missing_axis_candidate_count"] == 2
    assert diagnostic["safe_to_simulate_intent_removal_candidate_count"] == 1
    assert diagnostic["primary_failure_family_counts"] == {
        "axis_materialization_gap": 1,
        "intent_anchor_only": 1,
        "query_anchor_and_axis_missing": 1,
    }
    assert diagnostic["missing_axis_counts"] == {"display_value": 2}
    assert diagnostic["candidate_summaries"] == [
        {
            "item_index": 0,
            "candidate_index": 0,
            "rejection_reason": "missing_query_anchor_after_tool",
            "primary_failure_family": "intent_anchor_only",
            "secondary_failure_families": [],
            "missing_axes": [],
            "safe_to_simulate_intent_removal": True,
        },
        {
            "item_index": 0,
            "candidate_index": 1,
            "rejection_reason": "missing_query_anchor_after_tool",
            "primary_failure_family": "query_anchor_and_axis_missing",
            "secondary_failure_families": ["axis_materialization_gap"],
            "missing_axes": ["display_value"],
            "safe_to_simulate_intent_removal": False,
        },
        {
            "item_index": 0,
            "candidate_index": 2,
            "rejection_reason": "missing_validated_required_axes_after_tool",
            "primary_failure_family": "axis_materialization_gap",
            "secondary_failure_families": [],
            "missing_axes": ["display_value"],
            "safe_to_simulate_intent_removal": False,
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
    for forbidden in (
        "src-axis-repair",
        "bundle-axis-repair",
        "doc-axis-repair",
        "xlsx-axis-repair-blocked",
        "expected_answer",
        "expected_evidence",
        "row_id",
        "candidate_id",
    ):
        assert forbidden not in encoded


def test_xlsx_locator_projection_reports_agentic_regated_simulation_diagnostic() -> None:
    candidates = (
        actual_rag_eval.XlsxLocatorEvidenceCandidateRecord(
            item_index=0,
            candidate_index=0,
            source_family="XLSX",
            tool_name=actual_rag_eval.XLSX_LOCATOR_TOOL_NAME,
            tool_policy=actual_rag_eval.XLSX_LOCATOR_TOOL_POLICY,
            source_atom_id="src-regated-projection-0",
            evidence_bundle_id="bundle-regated-projection-0",
            doc_id="doc-regated-projection",
            sheet="2020년 2월",
            cell_range="A1:D4",
            row_label="일산선",
            target_column="수송인원",
            display_value="123명",
            matched_query_anchors=("2020년", "2월"),
            missing_query_anchors_after_tool=("무엇입니까",),
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
            source_atom_id="src-regated-projection-1",
            evidence_bundle_id="bundle-regated-projection-1",
            doc_id="doc-regated-projection",
            sheet="2020년 2월",
            cell_range="A5:D8",
            row_label="일산선",
            target_column="수송인원",
            matched_query_anchors=("2020년", "2월"),
            missing_query_anchors_after_tool=("무엇입니까",),
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
            source_atom_id="src-regated-projection-2",
            evidence_bundle_id="bundle-regated-projection-2",
            doc_id="doc-regated-projection",
            sheet="2020년 2월",
            cell_range="A9:D12",
            row_label="일산선",
            target_column="수송인원",
            display_value="123명",
            matched_query_anchors=("2020년", "2월"),
            missing_query_anchors_after_tool=("일산선",),
            matched_validated_required_axes=("period", "row_entity", "target_column", "display_value"),
            missing_validated_required_axes=(),
            confidence_tier="high",
            accepted_for_regating=False,
            rejection_reason="missing_query_anchor_after_tool",
        ),
    )
    record = actual_rag_eval.XlsxLocatorRunRecord(
        schema_version=actual_rag_eval.XLSX_LOCATOR_TOOL_EXECUTE_ONCE_SCHEMA_VERSION,
        enabled=True,
        report_only_diagnostic=True,
        official_metric=False,
        tool_name=actual_rag_eval.XLSX_LOCATOR_TOOL_NAME,
        eligible_failed_row_count=1,
        tool_invocation_count=1,
        accepted_candidate_count=0,
        rejected_candidate_count=3,
        gate_delta_record=actual_rag_eval.XlsxLocatorGateDeltaRecord(),
        guardrail_record=actual_rag_eval.XlsxLocatorGuardrailRecord(),
        required_anchor_summary={
            "removed_intent_tokens": ["무엇입니까"],
            "protected_intent_tokens_restored": ["일산선", "2020년"],
        },
        candidates=candidates,
    )

    diagnostic = actual_rag_eval.project_xlsx_locator_run_record(record)[
        "agentic_xlsx_axis_repair_diagnostic"
    ]
    simulation = diagnostic["regated_simulation_summary"]

    assert simulation["schema_version"] == "actual_rag_eval.agentic_xlsx_regated_candidate_simulator.v1"
    assert simulation["report_only_diagnostic"] is True
    assert simulation["official_metric"] is False
    assert simulation["official_metric_input_rows"] == 0
    assert simulation["approved_removed_tokens"] == ["무엇입니까"]
    assert simulation["protected_tokens_preserved"] == ["일산선", "2020년"]
    assert simulation["simulated_rejection_reason_counts"] == {
        "accepted_after_regating": 1,
        "missing_query_anchor_after_tool": 1,
        "missing_validated_required_axes_after_tool": 1,
    }
    assert simulation["would_be_accepted_by_existing_gate_candidate_count"] == 1
    assert simulation["query_anchor_to_axis_materialization_candidate_count"] == 1
    assert simulation["query_anchor_to_accepted_candidate_count"] == 1
    assert simulation["quality_delta_claim_supported"] is False
    assert simulation["simulations"] == [
        {
            "item_index": 0,
            "candidate_index": 0,
            "original_rejection_reason": "missing_query_anchor_after_tool",
            "simulated_rejection_reason": "accepted_after_regating",
            "approved_removed_tokens": ["무엇입니까"],
            "protected_tokens_preserved": ["일산선", "2020년"],
            "axis_status_after_simulation": {
                "missing_axes": [],
                "remaining_missing_query_anchors": [],
            },
            "would_be_accepted_by_existing_gate": True,
        },
        {
            "item_index": 0,
            "candidate_index": 1,
            "original_rejection_reason": "missing_query_anchor_after_tool",
            "simulated_rejection_reason": "missing_validated_required_axes_after_tool",
            "approved_removed_tokens": ["무엇입니까"],
            "protected_tokens_preserved": ["일산선", "2020년"],
            "axis_status_after_simulation": {
                "missing_axes": ["display_value"],
                "remaining_missing_query_anchors": [],
            },
            "would_be_accepted_by_existing_gate": False,
        },
        {
            "item_index": 0,
            "candidate_index": 2,
            "original_rejection_reason": "missing_query_anchor_after_tool",
            "simulated_rejection_reason": "missing_query_anchor_after_tool",
            "approved_removed_tokens": ["무엇입니까"],
            "protected_tokens_preserved": ["일산선", "2020년"],
            "axis_status_after_simulation": {
                "missing_axes": [],
                "remaining_missing_query_anchors": ["일산선"],
            },
            "would_be_accepted_by_existing_gate": False,
        },
    ]
    encoded = json.dumps(simulation, ensure_ascii=False)
    for forbidden in (
        "src-regated-projection",
        "bundle-regated-projection",
        "doc-regated-projection",
        "expected_answer",
        "expected_evidence",
        "row_id",
        "candidate_id",
    ):
        assert forbidden not in encoded


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


def test_evidence_gate_accepts_source_owned_period_cell_without_text_date_alias() -> None:
    query = "2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 무엇입니까?"
    row_label = "장기요양기관이름=하얀민들레노인요양원"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"period": "2020-11", "facility_name": "하얀민들레노인요양원"},
            "target_axis": {"column": "우편번호", "value_type": "text"},
            "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
            "intent_tokens": ["무엇입니까", "지정된"],
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2020-11", "2020년 11월", "202011"],
                "row_entity": ["하얀민들레노인요양원"],
                "target_column": ["우편번호"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "gate_source_owned_period_cell",
        "query": query,
        "generated_answer": "41786",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-row702",
                "chunk_id": "chunk-row702",
                "source_atom_id": "src-row702-postal-code",
                "evidence_bundle_id": "bundle-row702",
                "source_family": "XLSX",
                "granularity": "table_row",
                "text": f"sheet=일반현황 | row_label={row_label} | target_column=우편번호 | display_value=41786",
                "sheet": "일반현황",
                "cell_range": "A702:J751",
                "cell": "C702",
                "row_index_1based": "702",
                "row_label": row_label,
                "target_column": "우편번호",
                "display_value": "41786",
                "same_row_period_cells_json": same_row_period_cells_json(
                    source_atom_id="src-row702-designated-date",
                    doc_id="doc-row702",
                    sheet="일반현황",
                    cell_range="A702:J751",
                    cell="H702",
                    row_index_1based="702",
                    row_label=row_label,
                    raw_value="2020-11-26",
                    year=2020,
                    month=11,
                    day=26,
                ),
            }
        ],
        "citations": [],
    }

    validation = actual_rag_eval.validate_evidence_package_for_gate(row)

    assert validation["evidence_package_status"] == "sufficient"
    assert validation["missing_query_anchors"] == []
    assert validation["matched_validated_required_axes"] == [
        "period",
        "row_entity",
        "target_column",
        "display_value",
    ]
    assert validation["missing_validated_required_axes"] == []
    assert validation["validated_required_axes_coverage"] == 1.0


@pytest.mark.parametrize(
    "packet_overrides",
    [
        None,
        {"raw_value": "2020-12-26", "year": 2020, "month": 12, "day": 26},
        {"doc_id": "doc-other"},
        {"sheet": "다른시트"},
        {"cell_range": "A703:J752"},
        {"row_index_1based": "703", "row_label": "장기요양기관이름=다른기관"},
    ],
)
def test_evidence_gate_rejects_invalid_source_owned_period_cell_without_text_date_alias(
    packet_overrides: dict[str, object] | None,
) -> None:
    query = "2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 무엇입니까?"
    row_label = "장기요양기관이름=하얀민들레노인요양원"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"period": "2020-11", "facility_name": "하얀민들레노인요양원"},
            "target_axis": {"column": "우편번호", "value_type": "text"},
            "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
            "intent_tokens": ["무엇입니까", "지정된"],
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2020-11", "2020년 11월", "202011"],
                "row_entity": ["하얀민들레노인요양원"],
                "target_column": ["우편번호"],
                "display_value": [],
            },
        },
    )
    context = {
        "doc_id": "doc-row702",
        "chunk_id": "chunk-row702",
        "source_atom_id": "src-row702-postal-code",
        "evidence_bundle_id": "bundle-row702",
        "source_family": "XLSX",
        "granularity": "table_row",
        "text": f"sheet=일반현황 | row_label={row_label} | target_column=우편번호 | display_value=41786",
        "sheet": "일반현황",
        "cell_range": "A702:J751",
        "cell": "C702",
        "row_index_1based": "702",
        "row_label": row_label,
        "target_column": "우편번호",
        "display_value": "41786",
    }
    if packet_overrides is not None:
        packet_kwargs = {
            "source_atom_id": "src-row702-designated-date",
            "doc_id": "doc-row702",
            "sheet": "일반현황",
            "cell_range": "A702:J751",
            "cell": "H702",
            "row_index_1based": "702",
            "row_label": row_label,
            "raw_value": "2020-11-26",
            "year": 2020,
            "month": 11,
            "day": 26,
        }
        packet_kwargs.update(packet_overrides)
        context["same_row_period_cells_json"] = same_row_period_cells_json(**packet_kwargs)
    row = {
        "id": "gate_invalid_source_owned_period_cell",
        "query": query,
        "generated_answer": "41786",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [context],
        "citations": [],
    }

    validation = actual_rag_eval.validate_evidence_package_for_gate(row)

    assert validation["evidence_package_status"] == "insufficient"
    assert validation["matched_validated_required_axes"] == ["row_entity", "target_column", "display_value"]
    assert validation["missing_validated_required_axes"] == ["period"]
    assert "missing_validated_required_axes" in validation["validation_reasons"]


def test_evidence_gate_does_not_apply_unknown_source_family_axes_to_text_evidence() -> None:
    query = "미츠하는 타키를 만나려고 어디로 향했어"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "unknown",
            "query_task": "entity_attribute_lookup",
            "row_filters": {"line_name": "미츠하"},
            "target_axis": {"column": "어디로 향했어", "value_type": "text"},
            "evidence_contract": ["row_entity", "target_column", "display_value"],
            "intent_tokens": ["어디로 향했어"],
            "validated_required_axes": ["row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "row_entity": ["미츠하"],
                "target_column": ["어디로 향했어"],
                "display_value": [],
            },
        },
    )
    row = {
        "id": "text_unknown_source_family_axes",
        "query": query,
        "generated_answer": "미츠하는 타키를 만나기 위해 도쿄로 향했습니다.",
        "query_evidence_planner": planner,
        "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
        "retrieved_contexts": [
            {
                "doc_id": "doc-text-kiminonawa",
                "chunk_id": "chunk-text-kiminonawa",
                "source_atom_id": "src-text-kiminonawa",
                "evidence_bundle_id": "bundle-text-kiminonawa",
                "source_family": "TEXT",
                "granularity": "paragraph",
                "text": "자신과 몸이 바뀌고 있는 타키를 실제로 만나기 위해 미츠하는 도쿄로 향했습니다.",
            }
        ],
        "citations": [],
    }

    validation = actual_rag_eval.validate_evidence_package_for_gate(row)

    assert validation["evidence_package_status"] == "sufficient"
    assert validation["validated_required_axes"] == []
    assert validation["missing_validated_required_axes"] == []
    assert validation["validated_required_axes_ignored_reason"] == "unknown_source_family_text_evidence"
    assert "missing_validated_required_axes" not in validation["validation_reasons"]


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
