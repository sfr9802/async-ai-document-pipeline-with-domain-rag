from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SOURCE_REGISTRY_JSONL = Path("ai/eval/source_registry/source_atom_registry_v1.jsonl")
SCHEMA_VERSION = "v5_7_2_runlocal_live_candidate_generator_v1"
SEALED_SCHEMA_VERSION = "v5_7_2_runlocal_live_candidate_sealed_output_v1"
ROUTE_POLICY_MANIFEST_ID = "v5_7_2_candidate_generation_fence_policy_v1"
TOP_K = 5
LIVE_ORIGIN = "live_hybrid_search"
ALLOWED_FAMILIES = {"TEXT", "PDF", "XLSX"}
ALLOWED_REQUEST_FIELDS = frozenset(
    {
        "query_text",
        "source_family",
        "top_k",
        "route_policy_manifest_id",
    }
)
FORBIDDEN_REQUEST_FIELDS = frozenset(
    {
        "row_id",
        "query_id",
        "target_search_unit_id",
        "baseline_target_search_unit_id",
        "baseline_topk_new",
        "topk_new",
        "v5_7_candidate_ids",
        "candidate_ids",
        "qrels_positive_candidate_id",
        "qrels_positive_candidate_ids",
        "qrels_positive_id",
        "qrels_positive_ids",
        "expected_answer",
        "expected_answer_ko",
        "expected_answer_text",
        "supporting_evidence_id",
        "supporting_evidence_ids",
        "supporting_evidence",
        "supporting_evidence_note",
        "citation_locator",
        "gold_locator",
        "target_locator",
        "source_title",
        "source_file_name",
        "source_filename",
        "source_workbook",
        "workbook",
        "workbook_id",
        "source_identity",
        "raw_local_path",
        "raw_path",
        "source_path",
        "source_pdf_path",
        "raw_locator",
        "canonical_citation_payload",
        "official_denominator_overlap",
        "source_bound_official_denominator",
        "include_in_official_denominator",
    }
)
FORBIDDEN_PROJECTION_KEYS = frozenset(
    {
        "row_id",
        "query_id",
        "target_search_unit_id",
        "baseline_target_search_unit_id",
        "baseline_topk_new",
        "topk_new",
        "qrels_positive_candidate_ids",
        "expected_answer",
        "expected_answer_ko",
        "supporting_evidence_ids",
        "citation_locator",
        "gold_locator",
        "target_locator",
        "raw_locator",
        "canonical_citation_payload",
        "source_identity",
        "source_path",
        "source_pdf_path",
        "source_workbook",
        "workbook",
        "workbook_id",
        "source_file_name",
        "official_denominator_overlap",
        "source_bound_official_denominator",
        "include_in_official_denominator",
    }
)
PROTECTED_ARTIFACT_PATH_TOKENS = frozenset(
    {
        "official_metric_input.jsonl",
        "v5_7_vector_llm_candidate_routing",
        "v5_7_1_retrieval_metric_integrity_audit",
        "v5_6_full_packet_route_retrieval_comparison",
        "eval_queries",
        "qrels",
        "gold_queries",
        "baseline_topk",
    }
)
FORBIDDEN_IMPORT_TOKENS = frozenset(
    {
        "rag_v56",
        "rag_v57",
        "rag_v571",
        "rag_v550",
    }
)

TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
LOCAL_PATH_RE = re.compile(
    r"([A-Za-z]:[/\\][^\s|)]+|//\?/D:/[^\s|)]+|local-storage/[^\s|)]+|[^\s|)]+\.pdf|[^\s|)]+\.xlsx)",
    re.I,
)
PAGE_SHORTCUT_RE = re.compile(r"\bpage\s+\d+\b", re.I)


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def candidate_ids_sha256(candidate_ids: Sequence[str]) -> str:
    return _sha256_text(json.dumps(list(candidate_ids), ensure_ascii=False))


def tokenize(value: str) -> tuple[str, ...]:
    return tuple(token.lower() for token in TOKEN_RE.findall(value or "") if len(token) >= 2)


def request_fence_violations(request: Mapping[str, Any]) -> dict[str, Any]:
    fields = set(request)
    return {
        "forbidden_fields_present": sorted(fields & FORBIDDEN_REQUEST_FIELDS),
        "unknown_fields_present": sorted(fields - ALLOWED_REQUEST_FIELDS),
        "missing_required_fields": sorted({"query_text", "source_family"} - fields),
    }


def assert_candidate_request_fence(request: Mapping[str, Any]) -> None:
    violations = request_fence_violations(request)
    problems = {key: value for key, value in violations.items() if value}
    if problems:
        raise ValueError(f"candidate generation request fence violation: {problems}")
    if _clean(request.get("source_family")).upper() not in ALLOWED_FAMILIES:
        raise ValueError("candidate generation request source_family is not allowed")
    if not _clean(request.get("query_text")):
        raise ValueError("candidate generation request query_text is required")


def sanitized_candidate_request(
    *,
    query_text: str,
    source_family: str,
    top_k: int = TOP_K,
    route_policy_manifest_id: str = ROUTE_POLICY_MANIFEST_ID,
) -> dict[str, Any]:
    request = {
        "query_text": _clean(query_text),
        "source_family": _clean(source_family).upper(),
        "top_k": int(top_k),
        "route_policy_manifest_id": route_policy_manifest_id,
    }
    assert_candidate_request_fence(request)
    return request


def _redact_search_text(value: str) -> str:
    text = LOCAL_PATH_RE.sub(" ", value or "")
    text = PAGE_SHORTCUT_RE.sub(" ", text)
    return " ".join(text.split())


def _candidate_id_for_source_atom(row: Mapping[str, Any], family: str) -> str:
    raw_locator = row.get("raw_locator") if isinstance(row.get("raw_locator"), Mapping) else {}
    text_locator = row.get("text_locator") if isinstance(row.get("text_locator"), Mapping) else {}
    if family == "TEXT":
        return _clean(raw_locator.get("chunk_id") or text_locator.get("chunk_id") or row.get("search_unit_id"))
    return _clean(row.get("search_unit_id") or raw_locator.get("search_unit_id") or row.get("unitId"))


def _safe_search_text(row: Mapping[str, Any], family: str) -> str:
    raw_locator = row.get("raw_locator") if isinstance(row.get("raw_locator"), Mapping) else {}
    parts = [_redact_search_text(_clean(row.get("normalized_text_or_value_snapshot")))]
    if family == "XLSX":
        for key in ("sheet", "row_label", "column_label", "target_column"):
            value = _clean(raw_locator.get(key) or row.get(key))
            if value and ".xlsx" not in value.lower():
                parts.append(value)
    elif family == "PDF":
        for key in ("row_label", "region_type", "target_column"):
            value = _clean(raw_locator.get(key) or row.get(key))
            if value and ".pdf" not in value.lower() and "local-storage" not in value.lower():
                parts.append(value)
    return _redact_search_text(" ".join(part for part in parts if part))


@dataclass(frozen=True)
class RunLocalHybridIndex:
    postings_by_family: Mapping[str, Mapping[str, Mapping[str, int]]]
    candidate_token_counts: Mapping[str, int]
    metadata: Mapping[str, Any]


def _needed_tokens_by_family(requests: Sequence[Mapping[str, Any]]) -> dict[str, set[str]]:
    needed: dict[str, set[str]] = {family: set() for family in ALLOWED_FAMILIES}
    for request in requests:
        assert_candidate_request_fence(request)
        family = _clean(request.get("source_family")).upper()
        needed[family].update(tokenize(_clean(request.get("query_text"))))
    return needed


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {family: int(counter.get(family, 0)) for family in sorted(ALLOWED_FAMILIES)}


def build_runlocal_hybrid_index(*, root: Path | str, requests: Sequence[Mapping[str, Any]]) -> RunLocalHybridIndex:
    repo_root = Path(root)
    source_registry_path = repo_root / SOURCE_REGISTRY_JSONL
    generated_at = time.perf_counter()
    if not source_registry_path.exists():
        return RunLocalHybridIndex(
            postings_by_family={family: {} for family in sorted(ALLOWED_FAMILIES)},
            candidate_token_counts={},
            metadata={
                "schema_version": f"{SCHEMA_VERSION}_index_metadata_v1",
                "source_registry_logical_path": SOURCE_REGISTRY_JSONL.as_posix(),
                "index_available": False,
                "fail_closed": True,
                "fail_closed_reason": "missing_source_registry",
                "candidate_only": True,
                "vector_payload_role": "candidate_only",
                "evidence_truth_source": "SourceAtom/EvidenceBundle posthoc only",
                "source_registry_mutated": False,
                "index_rebuilt": False,
                "source_title_workbook_shortcut_used": False,
                "raw_local_path_used": False,
                "direct_expected_answer_or_qrels_matching": False,
                "source_atoms_scanned_count_by_family": {family: 0 for family in sorted(ALLOWED_FAMILIES)},
                "source_atoms_indexed_count_by_family": {family: 0 for family in sorted(ALLOWED_FAMILIES)},
                "projection_forbidden_field_violation_count": 0,
                "build_latency_ms": 0.0,
            },
        )

    needed_tokens = _needed_tokens_by_family(requests)
    postings: dict[str, dict[str, Counter[str]]] = {
        family: defaultdict(Counter) for family in sorted(ALLOWED_FAMILIES)
    }
    candidate_token_counts: dict[str, int] = {}
    scanned = Counter()
    indexed = Counter()
    tokenized = Counter()

    with source_registry_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            family = _clean(row.get("source_family")).upper()
            if family not in ALLOWED_FAMILIES:
                continue
            scanned[family] += 1
            candidate_id = _candidate_id_for_source_atom(row, family)
            if not candidate_id:
                continue
            search_text = _safe_search_text(row, family)
            tokens = tokenize(search_text)
            if not tokens:
                continue
            tokenized[family] += 1
            overlap = set(tokens) & needed_tokens.get(family, set())
            if not overlap:
                continue
            indexed[family] += 1
            token_counts = Counter(tokens)
            candidate_token_counts[candidate_id] = sum(token_counts.values())
            for token in overlap:
                postings[family][token][candidate_id] += int(token_counts[token])

    metadata = {
        "schema_version": f"{SCHEMA_VERSION}_index_metadata_v1",
        "source_registry_logical_path": SOURCE_REGISTRY_JSONL.as_posix(),
        "source_registry_sha256": hashlib.sha256(source_registry_path.read_bytes()).hexdigest(),
        "index_available": True,
        "fail_closed": False,
        "fail_closed_reason": "",
        "candidate_only": True,
        "vector_payload_role": "candidate_only",
        "evidence_truth_source": "SourceAtom/EvidenceBundle posthoc only",
        "source_registry_mutated": False,
        "index_rebuilt": False,
        "source_title_workbook_shortcut_used": False,
        "raw_local_path_used": False,
        "direct_expected_answer_or_qrels_matching": False,
        "allowed_projection_fields": [
            "candidate_id",
            "source_family",
            "sanitized_search_text_tokens",
            "search_text_sha256",
        ],
        "forbidden_projection_fields": sorted(FORBIDDEN_PROJECTION_KEYS),
        "projection_forbidden_field_violation_count": 0,
        "source_atoms_scanned_count_by_family": _counter_dict(scanned),
        "source_atoms_tokenized_count_by_family": _counter_dict(tokenized),
        "source_atoms_indexed_count_by_family": _counter_dict(indexed),
        "build_latency_ms": round((time.perf_counter() - generated_at) * 1000, 3),
    }
    return RunLocalHybridIndex(
        postings_by_family={
            family: {token: dict(counter) for token, counter in token_postings.items()}
            for family, token_postings in postings.items()
        },
        candidate_token_counts=dict(candidate_token_counts),
        metadata=metadata,
    )


def rank_candidates(
    request: Mapping[str, Any],
    *,
    index: RunLocalHybridIndex,
) -> dict[str, Any]:
    start = time.perf_counter()
    assert_candidate_request_fence(request)
    family = _clean(request.get("source_family")).upper()
    top_k = int(request.get("top_k") or TOP_K)
    if not index.metadata.get("index_available"):
        return {
            "candidate_ids": [],
            "candidate_origin": [],
            "candidate_count": 0,
            "origin": LIVE_ORIGIN,
            "fail_closed": True,
            "fail_closed_reason": index.metadata.get("fail_closed_reason") or "index_unavailable",
            "latency_ms": round((time.perf_counter() - start) * 1000, 3),
            "answer_generated": False,
            "fake_noop_answer_used": False,
        }
    query_tokens = tokenize(_clean(request.get("query_text")))
    query_counts = Counter(query_tokens)
    postings = index.postings_by_family.get(family) or {}
    lexical_scores: Counter[str] = Counter()
    for token, query_weight in query_counts.items():
        for candidate_id, source_weight in (postings.get(token) or {}).items():
            lexical_scores[candidate_id] += int(query_weight) * int(source_weight)
    scored: list[tuple[str, float, int, float]] = []
    query_len = max(1, sum(query_counts.values()))
    for candidate_id, lexical_score in lexical_scores.items():
        candidate_len = max(1, int(index.candidate_token_counts.get(candidate_id, 1)))
        sparse_cosine = float(lexical_score) / math.sqrt(query_len * candidate_len)
        hybrid_score = float(lexical_score) + sparse_cosine
        scored.append((candidate_id, hybrid_score, int(lexical_score), sparse_cosine))
    scored.sort(key=lambda item: (-item[1], item[0]))
    top = scored[:top_k]
    candidate_ids = [candidate_id for candidate_id, _score, _lexical, _cosine in top]
    return {
        "candidate_ids": candidate_ids,
        "candidate_origin": [
            {
                "candidate_id": candidate_id,
                "candidate_origin": LIVE_ORIGIN,
                "rank": rank,
                "score_sha256": _sha256_text(f"{score:.8f}:{lexical}:{cosine:.8f}"),
            }
            for rank, (candidate_id, score, lexical, cosine) in enumerate(top, start=1)
        ],
        "candidate_count": len(candidate_ids),
        "origin": LIVE_ORIGIN,
        "fail_closed": False,
        "fail_closed_reason": "",
        "latency_ms": round((time.perf_counter() - start) * 1000, 3),
        "answer_generated": False,
        "fake_noop_answer_used": False,
    }


def generate_sealed_candidates_in_process(
    *,
    root: Path | str,
    requests: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    safe_requests = [_json_clone(request) for request in requests]
    for request in safe_requests:
        assert_candidate_request_fence(request)
    index = build_runlocal_hybrid_index(root=root, requests=safe_requests)
    rows = []
    for ordinal, request in enumerate(safe_requests):
        ranked = rank_candidates(request, index=index)
        rows.append(
            {
                "ordinal": ordinal,
                "source_family": _clean(request.get("source_family")).upper(),
                "query_text_sha256": _sha256_text(_clean(request.get("query_text"))),
                "route_policy_manifest_id": _clean(request.get("route_policy_manifest_id")),
                **ranked,
                "candidate_ids_sha256": candidate_ids_sha256(ranked["candidate_ids"]),
            }
        )
    sealed = {
        "schema_version": SEALED_SCHEMA_VERSION,
        "generator_schema_version": SCHEMA_VERSION,
        "candidate_generation_process": "subprocess_worker_compatible",
        "candidate_generation_fence_verified": True,
        "allowed_request_fields": sorted(ALLOWED_REQUEST_FIELDS),
        "forbidden_request_fields": sorted(FORBIDDEN_REQUEST_FIELDS),
        "candidate_generator_reads_query_id": False,
        "candidate_generator_reads_row_id": False,
        "candidate_generator_reads_target_qrels_baseline": False,
        "candidate_generator_reads_expected_supporting_or_citation": False,
        "candidate_generator_reads_source_title_workbook_or_raw_path": False,
        "source_registry_logical_path": SOURCE_REGISTRY_JSONL.as_posix(),
        "index_metadata": dict(index.metadata),
        "candidate_rows": rows,
    }
    sealed["sealed_candidate_sha256"] = _sha256_text(
        json.dumps(sealed["candidate_rows"], ensure_ascii=False, sort_keys=True)
    )
    return sealed


def candidate_generator_dependency_audit() -> dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    import_pattern = re.compile(r"^\s*(?:from|import)\s+([A-Za-z0-9_.]+)", re.M)
    path_literal_pattern = re.compile(r"Path\([\"']([^\"']+)[\"']\)")
    imported_modules = sorted(match.group(1) for match in import_pattern.finditer(source))
    path_literals = sorted(match.group(1) for match in path_literal_pattern.finditer(source))
    forbidden_imports = [
        module
        for module in imported_modules
        if any(token in module for token in FORBIDDEN_IMPORT_TOKENS)
    ]
    protected_path_mentions = sorted(
        literal
        for literal in path_literals
        if literal != SOURCE_REGISTRY_JSONL.as_posix()
        and any(token in literal for token in PROTECTED_ARTIFACT_PATH_TOKENS)
    )
    return {
        "schema_version": f"{SCHEMA_VERSION}_dependency_audit_v1",
        "candidate_generator_module": "ai.eval.rag_v572_live_candidate_generator",
        "forbidden_import_modules_present": forbidden_imports,
        "forbidden_import_count": len(forbidden_imports),
        "protected_artifact_path_mentions": protected_path_mentions,
        "protected_artifact_path_mention_count": len(protected_path_mentions),
        "allowed_read_artifacts": [SOURCE_REGISTRY_JSONL.as_posix()],
        "source_registry_only_external_artifact_read": True,
    }


def _worker_main() -> None:
    payload = json.loads(sys.stdin.read() or "{}")
    requests = payload.get("requests") or []
    sealed = generate_sealed_candidates_in_process(root=Path.cwd(), requests=requests)
    print(json.dumps(sealed, ensure_ascii=False, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    if args == ["--worker"]:
        _worker_main()
        return 0
    raise SystemExit("usage: python -m ai.eval.rag_v572_live_candidate_generator --worker")


if __name__ == "__main__":
    raise SystemExit(main())
