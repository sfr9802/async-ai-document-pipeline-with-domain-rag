from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.capabilities.rag.embeddings import HashingEmbedder
from app.capabilities.rag.faiss_index import FaissIndex, IndexBuildInfo
from app.capabilities.rag.search_unit_indexing import (
    IndexedSearchUnit,
    SearchUnitVectorIndexResult,
    SearchUnitVectorIndexer,
    document_from_claim,
)
from app.clients.schemas import (
    SearchUnitIndexClaimResponse,
    SearchUnitIndexCompletionResponse,
    SearchUnitIndexDocument as ClaimUnit,
)
from app.services.search_unit_indexing_loop import SearchUnitIndexingWorker
from ai_worker.search_unit_indexing import _has_hard_identity_scope, _resolved_index_version, _validate_cli_args


def _claim_unit(**overrides):
    data = {
        "searchUnitId": "unit-1",
        "claimToken": "claim-1",
        "indexId": "source_file:source-1:unit:PAGE:page:1",
        "sourceFileId": "source-1",
        "sourceFileName": "doc.pdf",
        "extractedArtifactId": "artifact-1",
        "artifactType": "OCR_RESULT_JSON",
        "unitType": "PAGE",
        "unitKey": "page:1",
        "title": "Page 1",
        "sectionPath": None,
        "pageStart": 1,
        "pageEnd": 1,
        "textContent": "searchable page text",
        "contentSha256": "hash-1",
        "metadataJson": {"indexable": True},
        "indexMetadata": {"source_file_name": "doc.pdf"},
    }
    data.update(overrides)
    return ClaimUnit.model_validate(data)


class _FakeCoreApi:
    def __init__(self, units=None, *, stale_embedded=False):
        self.units = units or []
        self.stale_embedded = stale_embedded
        self.claim_requests = []
        self.embedded_requests = []
        self.failed_requests = []

    def claim_search_unit_indexing(self, request):
        self.claim_requests.append(request)
        return SearchUnitIndexClaimResponse(units=self.units)

    def mark_search_unit_embedded(self, search_unit_id, request):
        self.embedded_requests.append((search_unit_id, request))
        if self.stale_embedded:
            return SearchUnitIndexCompletionResponse(
                applied=False,
                stale=True,
                detail="stale embedding result",
            )
        return SearchUnitIndexCompletionResponse(
            applied=True,
            stale=False,
            indexId=request.index_id,
        )

    def mark_search_unit_indexing_failed(self, search_unit_id, request):
        self.failed_requests.append((search_unit_id, request))
        return SearchUnitIndexCompletionResponse(applied=True, stale=False)


class _FakeIndexer:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.indexed_docs = []

    def index_documents(self, docs):
        self.indexed_docs.extend(docs)
        if self.fail:
            raise RuntimeError("index boom")
        indexed = [
            IndexedSearchUnit(
                search_unit_id=doc.search_unit_id,
                claim_token=doc.claim_token,
                content_sha256=doc.content_sha256,
                index_id=doc.index_id,
                vector_id=f"idx-v1:{doc.index_id}",
                faiss_row_id=i,
                embedding_text_sha256=f"embed-hash-{i}",
                model_input_text_sha256=f"model-input-hash-{i}",
            )
            for i, doc in enumerate(docs)
        ]
        return SearchUnitVectorIndexResult(
            indexed=indexed,
            info=IndexBuildInfo(
                index_version="idx-v1",
                embedding_model="fake",
                dimension=2,
                chunk_count=len(indexed),
            ),
            index_version="idx-v1",
        )


class _FakeMetadataStore:
    def __init__(self):
        self.documents = {}
        self.chunks = {}
        self.index_builds = []

    def list_chunks(self, index_version):
        return sorted(
            [
                chunk
                for chunk in self.chunks.values()
                if chunk.index_version == index_version
            ],
            key=lambda chunk: chunk.faiss_row_id,
        )

    def upsert_index_rows(self, *, documents, chunks):
        for doc in documents:
            self.documents[doc.doc_id] = doc
        for chunk in chunks:
            self.chunks[chunk.chunk_id] = chunk

    def record_index_build(self, **kwargs):
        self.index_builds.append(kwargs)


class _CountingEmbedder:
    model_name = "counting-embedder"
    dimension = 8

    def __init__(self):
        self.passages = []

    def embed_passages(self, texts):
        self.passages.extend(texts)
        rows = []
        for index, _text in enumerate(texts, start=1):
            row = np.zeros(self.dimension, dtype=np.float32)
            row[0] = float(index)
            rows.append(row)
        return np.vstack(rows).astype(np.float32) if rows else np.empty((0, self.dimension), dtype=np.float32)

    def embed_queries(self, texts):
        return self.embed_passages(texts)


def test_once_mode_claims_and_exits_when_empty():
    core = _FakeCoreApi(units=[])
    indexer = _FakeIndexer()
    worker = SearchUnitIndexingWorker(
        core_api=core,
        indexer=indexer,
        worker_id="worker-test",
        batch_size=50,
    )

    summary = worker.run_once()

    assert summary.claimed == 0
    assert len(core.claim_requests) == 1
    assert not indexer.indexed_docs


def test_nonblank_search_unit_is_indexed_and_marked_embedded():
    unit = _claim_unit()
    core = _FakeCoreApi(units=[unit])
    indexer = _FakeIndexer()
    worker = SearchUnitIndexingWorker(
        core_api=core,
        indexer=indexer,
        worker_id="worker-test",
        batch_size=50,
    )

    summary = worker.run_once()

    assert summary.claimed == 1
    assert summary.indexed == 1
    assert indexer.indexed_docs[0].search_unit_id == "unit-1"
    assert core.embedded_requests[0][0] == "unit-1"
    assert core.embedded_requests[0][1].content_sha256 == "hash-1"
    assert core.embedded_requests[0][1].embedding_model == "fake"
    assert core.embedded_requests[0][1].embedding_text_sha256 == "embed-hash-0"
    assert core.embedded_requests[0][1].vector_id == "idx-v1:source_file:source-1:unit:PAGE:page:1"


def test_worker_forwards_claim_scope_fields():
    core = _FakeCoreApi(units=[])
    worker = SearchUnitIndexingWorker(
        core_api=core,
        indexer=_FakeIndexer(),
        worker_id="worker-test",
        batch_size=10,
        source_file_id="source-1",
        document_version_id="docv-1",
        parsed_artifact_id="pa-1",
        search_unit_ids=["unit-1", "unit-2"],
    )

    worker.run_once()

    request = core.claim_requests[0]
    assert request.source_file_id == "source-1"
    assert request.document_version_id == "docv-1"
    assert request.parsed_artifact_id == "pa-1"
    assert request.search_unit_ids == ["unit-1", "unit-2"]


def test_blank_claim_is_not_embedded_and_is_failed_defensively():
    unit = _claim_unit(textContent="   ")
    core = _FakeCoreApi(units=[unit])
    indexer = _FakeIndexer()
    worker = SearchUnitIndexingWorker(
        core_api=core,
        indexer=indexer,
        worker_id="worker-test",
        batch_size=50,
    )

    summary = worker.run_once()

    assert summary.claimed == 1
    assert summary.skipped_local == 1
    assert summary.failed == 1
    assert not indexer.indexed_docs
    assert not core.embedded_requests
    assert core.failed_requests[0][1].detail.startswith("NOT_EMBEDDABLE")


def test_embedding_failure_marks_claimed_units_failed():
    unit = _claim_unit()
    core = _FakeCoreApi(units=[unit])
    worker = SearchUnitIndexingWorker(
        core_api=core,
        indexer=_FakeIndexer(fail=True),
        worker_id="worker-test",
        batch_size=50,
    )

    summary = worker.run_once()

    assert summary.claimed == 1
    assert summary.failed == 1
    assert not core.embedded_requests
    assert "index boom" in core.failed_requests[0][1].detail


def test_stale_completion_is_reported_but_not_counted_embedded():
    unit = _claim_unit()
    core = _FakeCoreApi(units=[unit], stale_embedded=True)
    worker = SearchUnitIndexingWorker(
        core_api=core,
        indexer=_FakeIndexer(),
        worker_id="worker-test",
        batch_size=50,
    )

    summary = worker.run_once()

    assert summary.indexed == 0
    assert summary.stale == 1
    assert core.embedded_requests


def test_vector_indexer_upserts_same_search_unit_with_stable_index_id(tmp_path: Path):
    metadata = _FakeMetadataStore()
    index = FaissIndex(tmp_path / "rag-index")
    embedder = HashingEmbedder(dim=16)
    indexer = SearchUnitVectorIndexer(
        embedder=embedder,
        metadata_store=metadata,
        index=index,
        embedding_text_variant="retrieval_title_section",
        max_seq_length=1024,
    )
    first = document_from_claim(_claim_unit().model_dump(by_alias=True))
    second = document_from_claim(
        _claim_unit(textContent="updated searchable page text", contentSha256="hash-2")
        .model_dump(by_alias=True)
    )

    first_result = indexer.index_documents([first])
    second_result = indexer.index_documents([second])

    assert first_result.indexed[0].index_id == second_result.indexed[0].index_id
    assert second_result.indexed[0].faiss_row_id == 0
    assert list(metadata.chunks) == [first.index_id]
    chunk = metadata.chunks[first.index_id]
    assert chunk.text == "updated searchable page text"
    assert chunk.extra["searchUnitId"] == "unit-1"
    assert chunk.extra["indexId"] == first.index_id
    assert chunk.extra["contentSha256"] == "hash-2"
    assert (tmp_path / "rag-index" / "ingest_manifest.json").exists()


def test_vector_indexer_skips_duplicate_same_content_model_and_variant(tmp_path: Path):
    metadata = _FakeMetadataStore()
    index = FaissIndex(tmp_path / "rag-index")
    embedder = _CountingEmbedder()
    indexer = SearchUnitVectorIndexer(
        embedder=embedder,
        metadata_store=metadata,
        index=index,
        embedding_text_variant="retrieval_title_section",
        max_seq_length=1024,
    )
    doc = document_from_claim(_claim_unit().model_dump(by_alias=True))

    first = indexer.index_documents([doc])
    second = indexer.index_documents([doc])

    assert first.indexed[0].faiss_row_id == second.indexed[0].faiss_row_id == 0
    assert len(embedder.passages) == 1
    assert embedder.passages[0] != doc.text_content
    assert "Source: doc.pdf" in embedder.passages[0]
    assert "Title: Page 1" in embedder.passages[0]
    assert "Page: 1" in embedder.passages[0]
    assert len(metadata.index_builds) == 1


def test_cli_defaults_index_version_to_expected_candidate_version():
    args = _cli_args(
        expected_index_version="rag-ingestion-v2-candidate",
        index_version=None,
        document_version_id="docv-1",
    )

    _validate_cli_args(args)

    assert _resolved_index_version(args) == "rag-ingestion-v2-candidate"


def test_cli_rejects_unscoped_candidate_non_dry_run():
    args = _cli_args(expected_index_version="rag-ingestion-v2-candidate")

    with pytest.raises(ValueError, match="requires a hard identity scope"):
        _validate_cli_args(args)


def test_cli_rejects_unscoped_candidate_index_version_non_dry_run():
    args = _cli_args(index_version="rag-ingestion-v2-candidate")

    with pytest.raises(ValueError, match="requires a hard identity scope"):
        _validate_cli_args(args)

    assert args.expected_index_version == "rag-ingestion-v2-candidate"


@pytest.mark.parametrize(
    "scope",
    [
        {"document_version_id": "docv-1"},
        {"document_version_ids": ["docv-1"]},
        {"source_file_id": "source-1"},
        {"source_file_ids": ["source-1"]},
        {"parsed_artifact_id": "parsed-1"},
        {"search_unit_id": ["unit-1"]},
    ],
)
def test_cli_accepts_hard_identity_scopes_for_candidate_indexing(scope):
    args = _cli_args(index_version="rag-ingestion-v2-candidate", **scope)

    _validate_cli_args(args)

    assert args.expected_index_version == "rag-ingestion-v2-candidate"
    assert _has_hard_identity_scope(args) is True


def test_cli_type_parser_limit_scope_is_not_enough_for_candidate_indexing():
    args = _cli_args(
        index_version="rag-ingestion-v2-candidate",
        source_file_type=["PDF"],
        parser_version=["pdf-extract-v2"],
        limit=10,
    )

    with pytest.raises(ValueError, match="requires a hard identity scope"):
        _validate_cli_args(args)


def test_cli_rejects_version_omitted_broad_live_indexing():
    args = _cli_args(
        source_file_type=["PDF"],
        parser_version=["pdf-extract-v2"],
        limit=10,
    )

    with pytest.raises(ValueError, match="without --index-version/--expected-index-version"):
        _validate_cli_args(args)


def test_cli_accepts_version_omitted_hard_identity_scope():
    args = _cli_args(source_file_id="source-1")

    _validate_cli_args(args)

    assert _resolved_index_version(args) is None


def test_worker_forwards_filled_expected_version_for_scoped_candidate_index():
    args = _cli_args(
        index_version="rag-ingestion-v2-candidate",
        expected_index_version=None,
        document_version_id="docv-1",
    )
    _validate_cli_args(args)
    core = _FakeCoreApi(units=[])
    worker = SearchUnitIndexingWorker(
        core_api=core,
        indexer=_FakeIndexer(),
        worker_id="worker-test",
        batch_size=10,
        document_version_id=args.document_version_id,
        expected_index_version=args.expected_index_version,
    )

    worker.run_once()

    assert core.claim_requests[0].expected_index_version == "rag-ingestion-v2-candidate"


def test_cli_rejects_index_version_expected_version_mismatch():
    args = _cli_args(
        index_version="other-index",
        expected_index_version="rag-ingestion-v2-candidate",
        document_version_id="docv-1",
    )

    with pytest.raises(ValueError, match="must match --expected-index-version"):
        _validate_cli_args(args)


def _cli_args(**overrides):
    defaults = {
        "index_version": None,
        "expected_index_version": None,
        "document_version_id": None,
        "document_version_ids": None,
        "source_file_id": None,
        "source_file_ids": None,
        "parsed_artifact_id": None,
        "search_unit_id": None,
        "source_file_type": None,
        "parser_version": None,
        "limit": None,
        "allow_unscoped": False,
        "dry_run": False,
    }
    defaults.update(overrides)
    return type("Args", (), defaults)()
