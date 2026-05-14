from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "ai" / "eval" / "review"
REPORT_DIR = ROOT / "ai" / "eval" / "reports" / "rag-ingestion"
OFFICIAL_DENOMINATOR_REGISTRY = ROOT / "ai" / "eval" / "eval_queries" / "official_denominator_registry.json"

DEFAULT_GENERATED_INPUT = REPORT_DIR / "rag_text_namu_generated_answer_review_input.jsonl"
DEFAULT_APPLIED_V1 = REVIEW_DIR / "rag_text_namu_answer_citation_review_applied_diagnostic_v1.json"
DEFAULT_V2_REWRITE_JSONL = REVIEW_DIR / "rag_text_namu_generated_answer_review_input_local_llm_v2.jsonl"
DEFAULT_APPLIED_V2 = REVIEW_DIR / "rag_text_namu_answer_citation_review_applied_diagnostic_v2.json"
DEFAULT_DB_DSN = (
    os.environ.get("RAG_DB_DSN")
    or os.environ.get("AIPIPELINE_WORKER_RAG_DB_DSN")
    or "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw connect_timeout=2"
)
DEFAULT_BACKEND = os.environ.get("AIPIPELINE_WORKER_LLM_BACKEND", "llamacpp")
DEFAULT_LLAMACPP_BASE_URL = "http://localhost:8081/v1"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = os.environ.get("LOCAL_LLM_MODEL") or os.environ.get("AIPIPELINE_WORKER_LLM_LLAMACPP_MODEL") or "gemma4-e2b-local"
PROMPT_VERSION = "rag_text_namu_local_llm_rewrite_v2_source_bound_v1"
PROMPT_VERSION_V2_1 = "rag_text_namu_local_llm_rewrite_v2_1_source_bound_v1"
SCHEMA_VERSION = "rag_text_namu_local_llm_rewrite_v2"
SCHEMA_VERSION_V2_1 = "rag_text_namu_local_llm_rewrite_v2_1"

DEFAULT_V2_1_TARGET_QUERY_IDS = (
    "text_namu_v2_0002",
    "text_namu_v2_0017",
    "text_namu_v2_0035",
    "text_namu_v2_0051",
    "text_namu_v2_0053",
    "text_namu_v2_0057",
    "text_namu_v2_0065",
    "text_namu_v2_0085",
    "text_namu_v2_0088",
)

REWRITE_REQUIRED = "ANSWER_REWRITE_REQUIRED"
KEEP_CLEAN = "KEEP_DIAGNOSTIC_CANDIDATE"
KEEP_CLEANUP = "KEEP_WITH_CLEANUP"
CITATION_INADEQUATE = "CITATION_INADEQUATE"
SOURCE_BINDING_REVIEW_REQUIRED = "SOURCE_BINDING_REVIEW_REQUIRED"
NOT_ANSWERABLE = "NOT_ANSWERABLE_FROM_CITED_CONTEXT"

FORBIDDEN_PROMPT_MARKERS = (
    "expected_answer",
    "expected_evidence",
    "expected_chunk",
    "expected_page",
    "gold_seed",
    "gold_queries",
    "human_review",
    "user_answerability",
    "user_relevance",
    "user_expected",
    "source_locator",
    "embedding_text",
    "debug_text",
)


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_payload(value: Any) -> str:
    return sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def default_output_paths(version: str = "v2") -> dict[str, Path]:
    if version == "v2":
        return {
            "v2_jsonl": REVIEW_DIR / "rag_text_namu_generated_answer_review_input_local_llm_v2.jsonl",
            "v2_report_json": REVIEW_DIR / "rag_text_namu_generated_answer_review_input_local_llm_v2_report.json",
            "v2_report_md": REVIEW_DIR / "rag_text_namu_generated_answer_review_input_local_llm_v2_report.md",
            "draft_jsonl": REVIEW_DIR / "rag_text_namu_answer_citation_review_draft_local_llm_v2.jsonl",
            "draft_summary_json": REVIEW_DIR / "rag_text_namu_answer_citation_review_draft_local_llm_v2_summary.json",
            "applied_json": REVIEW_DIR / "rag_text_namu_answer_citation_review_applied_diagnostic_v2.json",
            "applied_md": REVIEW_DIR / "rag_text_namu_answer_citation_review_applied_diagnostic_v2.md",
            "improvement_json": REPORT_DIR / "rag_text_namu_answer_citation_local_llm_improvement_report.json",
            "improvement_md": REPORT_DIR / "rag_text_namu_answer_citation_local_llm_improvement_report.md",
        }
    if version != "v2_1":
        raise ValueError(f"unsupported output version: {version}")
    return {
        "v2_jsonl": REVIEW_DIR / "rag_text_namu_generated_answer_review_input_local_llm_v2_1.jsonl",
        "v2_report_json": REVIEW_DIR / "rag_text_namu_generated_answer_review_input_local_llm_v2_1_report.json",
        "v2_report_md": REVIEW_DIR / "rag_text_namu_generated_answer_review_input_local_llm_v2_1_report.md",
        "draft_jsonl": REVIEW_DIR / "rag_text_namu_answer_citation_review_draft_local_llm_v2_1.jsonl",
        "draft_summary_json": REVIEW_DIR / "rag_text_namu_answer_citation_review_draft_local_llm_v2_1_summary.json",
        "draft_summary_md": REVIEW_DIR / "rag_text_namu_answer_citation_review_draft_local_llm_v2_1_summary.md",
        "applied_json": REVIEW_DIR / "rag_text_namu_answer_citation_review_applied_diagnostic_v2_1.json",
        "applied_md": REVIEW_DIR / "rag_text_namu_answer_citation_review_applied_diagnostic_v2_1.md",
        "improvement_json": REPORT_DIR / "rag_text_namu_answer_citation_local_llm_improvement_report_v2_1.json",
        "improvement_md": REPORT_DIR / "rag_text_namu_answer_citation_local_llm_improvement_report_v2_1.md",
    }


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL row must be an object at {path}:{line_number}")
            rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def resolve_base_url(backend: str, base_url: str = "") -> str:
    if clean(base_url):
        return clean(base_url)
    if backend == "ollama":
        return os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    return (
        os.environ.get("OPENAI_COMPATIBLE_LOCAL_BASE_URL")
        or os.environ.get("LOCAL_LLM_BASE_URL")
        or os.environ.get("AIPIPELINE_WORKER_LLM_LLAMACPP_BASE_URL")
        or DEFAULT_LLAMACPP_BASE_URL
    )


def local_llm_entry_blockers(
    *,
    backend: str,
    base_url: str,
    model: str,
    check_endpoint: bool = True,
    timeout_seconds: int = 5,
) -> list[str]:
    blockers: list[str] = []
    if backend not in {"llamacpp", "openai-compatible", "ollama"}:
        blockers.append(f"unsupported local LLM backend: {backend}")
    if not clean(model):
        blockers.append("local LLM model is required")
    resolved = resolve_base_url(backend, base_url)
    parsed = urlparse(resolved)
    if parsed.scheme not in {"http", "https"}:
        blockers.append("local LLM base URL must be http(s)")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        blockers.append("external/cloud LLM endpoints are forbidden; use localhost only")
    if blockers or not check_endpoint:
        return blockers

    try:
        if backend == "ollama":
            request_json(f"{resolved.rstrip('/')}/api/tags", payload=None, timeout_seconds=timeout_seconds)
        else:
            request_json(f"{resolved.rstrip('/')}/models", payload=None, timeout_seconds=timeout_seconds)
    except Exception as exc:
        blockers.append(f"local {backend} unavailable: {type(exc).__name__}: {exc}")
    return blockers


def request_json(url: str, *, payload: Mapping[str, Any] | None, timeout_seconds: int) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def call_local_llm(
    *,
    backend: str,
    base_url: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
) -> str:
    resolved = resolve_base_url(backend, base_url)
    if backend == "ollama":
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature, "num_predict": int(max_tokens)},
        }
        response = request_json(f"{resolved.rstrip('/')}/api/generate", payload=payload, timeout_seconds=timeout_seconds)
        if isinstance(response, Mapping):
            return clean(response.get("response")) or json.dumps(response, ensure_ascii=False)
        return json.dumps(response, ensure_ascii=False)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Return exactly one JSON object. No markdown, no prose, no hidden reasoning.",
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "stream": False,
        "max_tokens": int(max_tokens),
        "temperature": temperature,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    response = request_json(
        f"{resolved.rstrip('/')}/chat/completions",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    if isinstance(response, Mapping):
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], Mapping) else {}
            message = first.get("message") if isinstance(first.get("message"), Mapping) else {}
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return json.dumps(response, ensure_ascii=False)


def parse_strict_json_object(value: Any) -> dict[str, Any]:
    text = clean(value)
    if not text:
        raise ValueError("local LLM output must be a strict JSON object")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"local LLM output must be a strict JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("local LLM output must be a strict JSON object")
    return parsed


def call_local_llm_strict_json(
    *,
    backend: str,
    base_url: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
    retries: int = 1,
) -> tuple[dict[str, Any], dict[str, Any]]:
    attempts = max(1, int(retries))
    prompt_for_attempt = prompt
    raw_hashes: list[str] = []
    last_error = ""
    for attempt in range(1, attempts + 1):
        raw = call_local_llm(
            backend=backend,
            base_url=base_url,
            model=model,
            prompt=prompt_for_attempt,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )
        raw_hashes.append(sha256_text(raw))
        try:
            return parse_strict_json_object(raw), {
                "strict_json_attempts": attempt,
                "strict_json_retry_count": attempt - 1,
                "raw_response_sha256": raw_hashes[-1],
                "raw_response_sha256_attempts": raw_hashes,
            }
        except ValueError as exc:
            last_error = str(exc)
            prompt_for_attempt = (
                prompt
                + "\n\nPrevious response failed strict JSON validation. "
                + "Return exactly one minified JSON object with no markdown or prose. "
                + f"Validation error: {last_error}"
            )
    raise ValueError(f"local LLM output must be a strict JSON object after {attempts} attempts: {last_error}")


def candidate_chunk_ids(row: Mapping[str, Any]) -> list[str]:
    ids: list[str] = []
    for key in ("cited_chunk_ids", "retrieved_chunk_ids"):
        values = row.get(key)
        if isinstance(values, list):
            ids.extend(clean(value) for value in values if clean(value))
    for item in row.get("citation_items") or []:
        if isinstance(item, Mapping):
            chunk_id = clean(item.get("chunk_id"))
            if chunk_id:
                ids.append(chunk_id)
    return sorted(set(ids))


def collect_db_lookup_values(rows: list[Mapping[str, Any]]) -> list[str]:
    values: set[str] = set()
    for row in rows:
        values.update(candidate_chunk_ids(row))
        for item in row.get("citation_items") or []:
            if not isinstance(item, Mapping):
                continue
            locator = item.get("citation_locator") if isinstance(item.get("citation_locator"), Mapping) else {}
            for key in ("chunk_text_sha256", "page_id", "section_id"):
                value = clean(locator.get(key))
                if value:
                    values.add(value)
    return sorted(values)


def empty_db_context(status: str, blocker: str = "") -> dict[str, Any]:
    return {
        "status": status,
        "blocker": blocker,
        "db_context_used": False,
        "db_read_only_confirmed": False,
        "candidate_lookup_value_count": 0,
        "loaded_search_unit_count": 0,
        "by_id": {},
        "provenance": {
            "db_read_only_mode": "not_connected",
            "selected_fields_exclude": ["embedding_text", "debug_text"],
        },
    }


def load_db_context(rows: list[Mapping[str, Any]], *, db_dsn: str = DEFAULT_DB_DSN) -> dict[str, Any]:
    lookup_values = collect_db_lookup_values(rows)
    if not lookup_values:
        report = empty_db_context("NO_CANDIDATE_LOOKUP_VALUES")
        return {**report, "candidate_lookup_value_count": 0}

    try:
        import psycopg2
        import psycopg2.extras
    except Exception as exc:  # pragma: no cover - optional dependency
        report = empty_db_context("DB_UNAVAILABLE_FAIL_CLOSED", f"psycopg2 unavailable: {type(exc).__name__}: {exc}")
        return {**report, "candidate_lookup_value_count": len(lookup_values)}

    try:
        with psycopg2.connect(db_dsn, cursor_factory=psycopg2.extras.RealDictCursor) as conn:
            conn.set_session(readonly=True, autocommit=True)
            with conn.cursor() as cur:
                cur.execute("SHOW transaction_read_only")
                read_only_value = clean(cur.fetchone()["transaction_read_only"])
                if read_only_value.lower() not in {"on", "true", "1"}:
                    report = empty_db_context("DB_READ_ONLY_GUARD_FAILED", "transaction_read_only was not on")
                    return {**report, "candidate_lookup_value_count": len(lookup_values)}
                cur.execute(
                    """
                    SELECT id, index_id, unit_key, source_file_id, source_file_name,
                           source_file_type, document_version_id, parsed_artifact_id,
                           extracted_artifact_id, unit_type, chunk_type, location_json,
                           bm25_text, display_text, citation_text,
                           parser_name, parser_version, index_version, embedding_status
                      FROM search_unit
                     WHERE id = ANY(%s)
                        OR index_id = ANY(%s)
                        OR unit_key = ANY(%s)
                        OR content_sha256 = ANY(%s)
                        OR indexed_content_sha256 = ANY(%s)
                    """,
                    (lookup_values, lookup_values, lookup_values, lookup_values, lookup_values),
                )
                db_rows = [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        report = empty_db_context("DB_UNAVAILABLE_FAIL_CLOSED", f"{type(exc).__name__}: {exc}")
        return {**report, "candidate_lookup_value_count": len(lookup_values)}

    by_id: dict[str, dict[str, Any]] = {}
    for row in db_rows:
        slim = {
            "id": clean(row.get("id")),
            "index_id": clean(row.get("index_id")),
            "unit_key": clean(row.get("unit_key")),
            "source_file_id": clean(row.get("source_file_id")),
            "source_file_name": clean(row.get("source_file_name")),
            "source_file_type": clean(row.get("source_file_type")),
            "document_version_id": clean(row.get("document_version_id")),
            "parsed_artifact_id": clean(row.get("parsed_artifact_id")),
            "extracted_artifact_id": clean(row.get("extracted_artifact_id")),
            "unit_type": clean(row.get("unit_type")),
            "chunk_type": clean(row.get("chunk_type")),
            "location_json": row.get("location_json") if isinstance(row.get("location_json"), Mapping) else {},
            "bm25_text": clean(row.get("bm25_text")),
            "display_text": clean(row.get("display_text")),
            "citation_text": clean(row.get("citation_text")),
            "parser_name": clean(row.get("parser_name")),
            "parser_version": clean(row.get("parser_version")),
            "index_version": clean(row.get("index_version")),
            "embedding_status": clean(row.get("embedding_status")),
        }
        for key in ("id", "index_id", "unit_key"):
            value = clean(slim.get(key))
            if value:
                by_id[value] = slim

    return {
        "status": "DB_CONTEXT_LOADED" if db_rows else "NO_CANDIDATE_DB_MATCHES",
        "blocker": "",
        "db_context_used": bool(db_rows),
        "db_read_only_confirmed": True,
        "candidate_lookup_value_count": len(lookup_values),
        "loaded_search_unit_count": len(db_rows),
        "by_id": by_id,
        "provenance": {
            "db_read_only_mode": "transaction_read_only=on; autocommit=true; select_only",
            "query_scope": "candidate cited/retrieved chunk ids and citation locator ids only",
            "selected_fields_include": [
                "id",
                "index_id",
                "unit_key",
                "source_file_id",
                "source_file_name",
                "source_file_type",
                "document_version_id",
                "parsed_artifact_id",
                "extracted_artifact_id",
                "location_json",
                "bm25_text",
                "display_text",
                "citation_text",
                "parser_name",
                "parser_version",
                "index_version",
                "embedding_status",
            ],
            "selected_fields_exclude": ["embedding_text", "debug_text"],
        },
    }


def sanitized_locator(locator: Mapping[str, Any]) -> dict[str, Any]:
    allowed = (
        "page_id",
        "section_id",
        "section_path",
        "page_title",
        "source_url",
        "chunk_text_sha256",
        "source_file_id",
        "source_file_name",
        "location_json",
    )
    return {key: locator.get(key) for key in allowed if clean(locator.get(key)) or isinstance(locator.get(key), Mapping)}


def build_source_context(row: Mapping[str, Any], db_context: Mapping[str, Any]) -> dict[str, Any]:
    db_by_id = db_context.get("by_id") if isinstance(db_context.get("by_id"), Mapping) else {}
    chunks: list[dict[str, Any]] = []
    for item in row.get("citation_items") or []:
        if not isinstance(item, Mapping):
            continue
        chunk_id = clean(item.get("chunk_id"))
        db_row = db_by_id.get(chunk_id) if isinstance(db_by_id, Mapping) else None
        db_fields: dict[str, Any] = {}
        if isinstance(db_row, Mapping):
            db_fields = {
                "source_file_id": db_row.get("source_file_id"),
                "source_file_name": db_row.get("source_file_name"),
                "source_file_type": db_row.get("source_file_type"),
                "document_version_id": db_row.get("document_version_id"),
                "parsed_artifact_id": db_row.get("parsed_artifact_id"),
                "extracted_artifact_id": db_row.get("extracted_artifact_id"),
                "location_json": db_row.get("location_json") if isinstance(db_row.get("location_json"), Mapping) else {},
                "display_text": db_row.get("display_text"),
                "bm25_text": db_row.get("bm25_text"),
                "citation_text": db_row.get("citation_text"),
                "parser_name": db_row.get("parser_name"),
                "parser_version": db_row.get("parser_version"),
                "index_version": db_row.get("index_version"),
            }
        citation_locator = item.get("citation_locator") if isinstance(item.get("citation_locator"), Mapping) else {}
        texts = [
            clean(item.get("citation_text")),
            clean(db_fields.get("citation_text")),
            clean(db_fields.get("display_text")),
            clean(db_fields.get("bm25_text")),
        ]
        combined = "\n".join(dict.fromkeys(text for text in texts if text))
        chunks.append(
            {
                "chunk_id": chunk_id,
                "citation_text": clean(item.get("citation_text")),
                "citation_locator": sanitized_locator(citation_locator),
                "db_context": {key: value for key, value in db_fields.items() if value not in ("", {}, None)},
                "combined_context_text": combined,
                "db_context_used": bool(db_fields),
            }
        )
    return {
        "query_id": clean(row.get("query_id")),
        "safe_query_text": clean(row.get("safe_query_text") or row.get("query")),
        "allowed_cited_chunk_ids": [clean(value) for value in row.get("cited_chunk_ids") or [] if clean(value)],
        "allowed_retrieved_chunk_ids": [clean(value) for value in row.get("retrieved_chunk_ids") or [] if clean(value)],
        "chunks": chunks,
        "db_context_used": any(chunk["db_context_used"] for chunk in chunks),
        "db_context_provenance": db_context.get("provenance") if isinstance(db_context.get("provenance"), Mapping) else {},
    }


def prompt_forbidden_markers(prompt: str) -> list[str]:
    lowered = prompt.lower()
    return [marker for marker in FORBIDDEN_PROMPT_MARKERS if marker in lowered]


def build_rewrite_prompt(row: Mapping[str, Any], source_context: Mapping[str, Any], *, prompt_version: str) -> str:
    payload = {
        "task": "text_namu_diagnostic_source_bound_rewrite",
        "prompt_version": prompt_version,
        "query_id": clean(row.get("query_id")),
        "safe_query_text": clean(row.get("safe_query_text") or row.get("query")),
        "allowed_cited_chunk_ids": source_context.get("allowed_cited_chunk_ids") or [],
        "allowed_retrieved_chunk_ids": source_context.get("allowed_retrieved_chunk_ids") or [],
        "source_context": source_context.get("chunks") or [],
        "output_schema": {
            "rewritten_answer": "string",
            "cited_chunk_ids": ["candidate chunk ids used by the answer"],
            "evidence_spans": ["exact substrings copied from source_context"],
            "evidence_span_chunk_ids": ["chunk id for each evidence_spans entry"],
            "answer_claims": ["atomic factual claims in rewritten_answer"],
            "unsupported_claims": [],
            "missing_information": [],
            "answerability_from_cited_context": True,
            "rewrite_status": KEEP_CLEAN,
        },
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    forbidden = prompt_forbidden_markers(body)
    if forbidden:
        raise ValueError(f"prompt input contains forbidden source-review fields: {', '.join(forbidden)}")
    return f"""You are rewriting a diagnostic TEXT/Namu RAG answer from cited source context only.

Rules:
- Use only the supplied source_context. Do not use outside knowledge.
- Preserve the query language.
- Answer all requested fields when the supplied context supports them.
- Keep rewritten_answer concise: one or two sentences.
- Every factual claim in rewritten_answer must be backed by an exact evidence_spans substring.
- evidence_spans must be copied exactly from source_context text.
- Use at most three evidence_spans and at most three answer_claims.
- Keep each evidence_span short; prefer the exact sentence or clause that supports the claim.
- cited_chunk_ids and evidence_span_chunk_ids must come from the allowed ids.
- evidence_span_chunk_ids must have exactly the same number of items as evidence_spans; repeat the same chunk id when multiple spans come from the same chunk.
- answer_claims must use the same language as rewritten_answer; do not translate Korean claims into English.
- Keep answer_claims extractive: each answer_claim must be copied from evidence_spans or be a direct shorter substring of evidence_spans.
- For multi-field answers, prefer one short answer_claim per field copied exactly from evidence_spans.
- Do not add title, query subject, role labels, or connective wording to answer_claims unless the words appear in evidence_spans.
- Do not add page titles, work titles, entity names, or query words into answer_claims unless those exact words appear in evidence_spans.
- If rewritten_answer includes a title for readability but the evidence span starts after that title, answer_claims must start from the evidence span wording, not from the rewritten_answer title prefix.
- If you need the title from safe_query_text to make rewritten_answer readable, keep it minimal and do not treat it as a supported answer_claim unless it appears in evidence_spans.
- If the supplied context is insufficient, say what is missing in missing_information and set answerability_from_cited_context to false.
- Return exactly one JSON object and no markdown.

Diagnostic input:
{body}
"""


def normalized_space(value: str) -> str:
    return re.sub(r"\s+", " ", clean(value))


def canonical_for_match(value: str) -> str:
    text = normalized_space(value)
    text = re.sub(r"\s+([.,;:!?%])", r"\1", text)
    text = re.sub(r"([([{])\s+", r"\1", text)
    text = re.sub(r"\s+([])}])", r"\1", text)
    return re.sub(r"\s+", "", text)


def span_in_text(span: str, text: str) -> bool:
    return canonical_for_match(span) in canonical_for_match(text)


def clean_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    if isinstance(value, str) and clean(value):
        return [clean(value)]
    return []


def split_answer_claim_candidates(answer: str) -> list[str]:
    text = normalized_space(answer)
    if not text:
        return []
    parts = [part.strip() for part in re.split(r"(?<=[.!?。])\s+", text) if part.strip()]
    return parts or [text]


def derive_answer_claims_from_supported_answer(answer: str, evidence_spans: list[str]) -> list[str]:
    if not clean(answer) or not evidence_spans:
        return []
    candidates = split_answer_claim_candidates(answer)
    if candidates and all(any(span_in_text(candidate, span) for span in evidence_spans) for candidate in candidates):
        return candidates
    if any(span_in_text(answer, span) for span in evidence_spans):
        return [clean(answer)]
    return []


def exact_evidence_claim_repair(
    *,
    rewritten_answer: str,
    answer_claims: list[str],
    evidence_spans: list[str],
) -> list[str]:
    if not rewritten_answer or not answer_claims or not evidence_spans:
        return []
    repaired: list[str] = []
    changed = False
    for claim in answer_claims:
        if claim_has_single_span_support(claim, evidence_spans):
            repaired.append(claim)
            continue
        claim_tokens = tokens_for_support(claim)
        answer_tokens = tokens_for_support(rewritten_answer)
        candidates = [
            span
            for span in evidence_spans
            if negation_matches(claim, span)
            and role_binding_matches(claim, span)
            and (not claim_tokens or len(claim_tokens.intersection(tokens_for_support(span))) >= 2)
            and len(claim_tokens.difference(tokens_for_support(span))) <= max(2, len(claim_tokens) // 4)
            and len(tokens_for_support(span).difference(answer_tokens)) <= max(2, len(tokens_for_support(span)) // 4)
        ]
        if not candidates:
            return []
        replacement = max(candidates, key=lambda span: len(tokens_for_support(span).intersection(claim_tokens)))
        repaired.append(replacement)
        changed = True
    if not changed:
        return []
    deduped = list(dict.fromkeys(repaired))
    if all(claim_has_single_span_support(claim, evidence_spans) for claim in deduped):
        return deduped
    return []


def normalize_support_token(token: str) -> str:
    value = clean(token).lower()
    for suffix in (
        "였습니다",
        "입니다",
        "이기도",
        "되었다",
        "이었다",
        "였다",
        "이며",
        "이고",
        "이다",
        "한다",
        "했다",
    ):
        if value.endswith(suffix) and len(value) >= len(suffix) + 1:
            value = value[: -len(suffix)]
            break
    for suffix in ("으로는", "에서는", "에게는", "에는", "으로", "에서", "에게"):
        if value.endswith(suffix) and len(value) >= len(suffix) + 1:
            value = value[: -len(suffix)]
            break
    for suffix in ("은", "는", "이", "가", "을", "를", "의", "와", "과", "도", "만", "에", "로"):
        if value.endswith(suffix) and len(value) >= len(suffix) + 1:
            value = value[: -len(suffix)]
            break
    return value


def tokens_for_support(value: str) -> set[str]:
    raw_tokens = re.findall(r"[0-9]+(?:\.[0-9]+)?|[A-Za-z가-힣]{2,}", value)
    stopwords = {
        "그리고",
        "또한",
        "정보",
        "시기",
        "작품",
        "애니메이션",
        "animation",
        "anime",
        "the",
        "and",
        "for",
        "from",
        "with",
    }
    tokens = {normalize_support_token(token) for token in raw_tokens}
    return {token for token in tokens if len(token) >= 2 and token not in stopwords}


def claim_has_span_support(claim: str, spans: list[str]) -> bool:
    supported, _ = claim_support_detail(claim, spans, allow_split=False)
    return supported


def claim_support_detail(claim: str, spans: list[str], *, allow_split: bool) -> tuple[bool, bool]:
    if claim_has_single_span_support(claim, spans):
        return True, False
    if not allow_split:
        return False, False
    parts = split_compound_claim(claim)
    if len(parts) < 2:
        return False, False
    if all(claim_has_single_span_support(part, spans) for part in parts):
        return True, True
    return False, False


def claim_has_single_span_support(claim: str, spans: list[str]) -> bool:
    claim_tokens = tokens_for_support(claim)
    if not claim_tokens:
        return True
    for span in spans:
        if not negation_matches(claim, span):
            continue
        if not role_binding_matches(claim, span):
            continue
        if claim_tokens.issubset(tokens_for_support(span)):
            return True
    return False


def split_compound_claim(claim: str) -> list[str]:
    normalized = normalized_space(claim)
    parts = re.split(r"\s*(?:이고|이며|그리고|및)\s*", normalized)
    return [part.strip(" .,;:!?") for part in parts if part.strip(" .,;:!?")]


def contains_negation(value: str) -> bool:
    text = clean(value).lower()
    return any(marker in text for marker in ("아니다", "없다", "않", "못", "not ", "no "))


def negation_matches(claim: str, span: str) -> bool:
    return contains_negation(claim) == contains_negation(span)


COMMON_ROLE_MARKERS = (
    "감독",
    "제작사",
    "방영",
    "개봉",
    "공개",
    "상영일",
    "정식 제목",
    "작가",
    "원작",
)


def value_tokens_for_role(text: str, marker: str) -> set[str]:
    source = clean(text)
    marker_index = source.find(marker)
    if marker_index < 0:
        return set()
    tail = source[marker_index + len(marker) :]
    tail = re.sub(r"^[\s은는이가:：\-]+", "", tail)
    other_positions = [
        pos
        for other in COMMON_ROLE_MARKERS
        if other != marker
        for pos in [tail.find(other)]
        if pos > 0
    ]
    connector_positions = [
        pos
        for connector in ("이며", "이고", "이고,", "이고 ", "이며,", "이며 ", "이고,", "그리고", "\n")
        for pos in [tail.find(connector)]
        if pos > 0
    ]
    stop_positions = other_positions + connector_positions
    if stop_positions:
        tail = tail[: min(stop_positions)]
    tail = re.split(r"[.,;:!?。]", tail, maxsplit=1)[0]
    return tokens_for_support(tail)


def role_binding_matches(claim: str, span: str) -> bool:
    for marker in COMMON_ROLE_MARKERS:
        if marker not in claim:
            continue
        claim_values = value_tokens_for_role(claim, marker)
        if not claim_values:
            continue
        span_values = value_tokens_for_role(span, marker)
        if not span_values or not claim_values.issubset(span_values):
            return False
    return True


def verify_llm_output(
    candidate_row: Mapping[str, Any],
    source_context: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    local_llm_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    normalization_notes: list[str] = []
    deterministic_claim_repair = False
    split_span_support = False
    rewritten_answer = clean(payload.get("rewritten_answer"))
    cited_chunk_ids = clean_list(payload.get("cited_chunk_ids"))
    evidence_spans = clean_list(payload.get("evidence_spans"))
    evidence_span_chunk_ids = clean_list(payload.get("evidence_span_chunk_ids"))
    answer_claims = clean_list(payload.get("answer_claims"))
    unsupported_claims = clean_list(payload.get("unsupported_claims"))
    missing_information = clean_list(payload.get("missing_information"))
    answerability = payload.get("answerability_from_cited_context")

    if not rewritten_answer:
        errors.append("rewritten_answer is required")
    if not cited_chunk_ids:
        errors.append("cited_chunk_ids are required")
    if not evidence_spans:
        errors.append("evidence_spans are required")
    if not answer_claims:
        repaired_claims = derive_answer_claims_from_supported_answer(rewritten_answer, evidence_spans)
        if repaired_claims:
            answer_claims = repaired_claims
            deterministic_claim_repair = True
            normalization_notes.append("deterministically derived answer_claims from extractive answer and evidence_spans")
        else:
            errors.append("answer_claims are required")
    if unsupported_claims:
        errors.append("unsupported_claims must be empty")
    if answerability is not True:
        errors.append("answerability_from_cited_context must be true for a diagnostic pass candidate")
    if payload.get("official_metric_input") is True:
        errors.append("official_metric_input must remain false")
    if payload.get("promotion_evidence") is True:
        errors.append("promotion_evidence must remain false")

    allowed_chunks = set(candidate_chunk_ids(candidate_row))
    if (
        len(evidence_spans) > 1
        and len(evidence_span_chunk_ids) == 1
        and evidence_span_chunk_ids[0] in allowed_chunks
        and len(set(cited_chunk_ids)) == 1
        and cited_chunk_ids[0] == evidence_span_chunk_ids[0]
    ):
        evidence_span_chunk_ids = evidence_span_chunk_ids * len(evidence_spans)
        normalization_notes.append("repeated single evidence_span_chunk_id for same candidate chunk")

    if len(evidence_span_chunk_ids) != len(evidence_spans):
        errors.append("evidence_span_chunk_ids must align with evidence_spans")

    outside = sorted(set(cited_chunk_ids + evidence_span_chunk_ids) - allowed_chunks)
    if outside:
        errors.append(f"local LLM output cites chunks outside candidate cited/retrieved chunks: {', '.join(outside)}")

    context_by_chunk: dict[str, str] = {}
    for chunk in source_context.get("chunks") or []:
        if not isinstance(chunk, Mapping):
            continue
        chunk_id = clean(chunk.get("chunk_id"))
        if chunk_id:
            context_by_chunk[chunk_id] = "\n".join(
                clean(value)
                for value in (
                    chunk.get("combined_context_text"),
                    chunk.get("citation_text"),
                    (chunk.get("db_context") or {}).get("citation_text")
                    if isinstance(chunk.get("db_context"), Mapping)
                    else "",
                    (chunk.get("db_context") or {}).get("display_text")
                    if isinstance(chunk.get("db_context"), Mapping)
                    else "",
                    (chunk.get("db_context") or {}).get("bm25_text")
                    if isinstance(chunk.get("db_context"), Mapping)
                    else "",
                )
                if clean(value)
            )

    for index, span in enumerate(evidence_spans):
        chunk_id = evidence_span_chunk_ids[index] if index < len(evidence_span_chunk_ids) else ""
        context_text = context_by_chunk.get(chunk_id, "") if chunk_id else "\n".join(context_by_chunk.values())
        if not span_in_text(span, context_text):
            errors.append(f"evidence span not found in cited context: {span[:80]}")

    declared_split_span_support = payload.get("split_span_support") is True
    claim_support_errors: list[str] = []
    for claim in answer_claims:
        supported, used_split = claim_support_detail(
            claim,
            evidence_spans,
            allow_split=declared_split_span_support,
        )
        if used_split:
            split_span_support = True
        if not supported:
            claim_support_errors.append(f"answer claim is not supported by evidence spans: {claim[:80]}")

    if claim_support_errors:
        repaired_claims = exact_evidence_claim_repair(
            rewritten_answer=rewritten_answer,
            answer_claims=answer_claims,
            evidence_spans=evidence_spans,
        )
        if repaired_claims:
            answer_claims = repaired_claims
            deterministic_claim_repair = True
            normalization_notes.append("deterministically replaced unsupported answer_claims with exact evidence_spans")
            claim_support_errors = []
    errors.extend(claim_support_errors)

    verifier_passed = not errors
    source_hash = sha256_payload(source_context)
    llm_rewrite_status = clean(payload.get("rewrite_status"))
    verified_rewrite_status = llm_rewrite_status or KEEP_CLEAN
    if not verifier_passed:
        verified_rewrite_status = REWRITE_REQUIRED

    return {
        "query_id": clean(candidate_row.get("query_id")),
        "safe_query_text": clean(candidate_row.get("safe_query_text") or candidate_row.get("query")),
        "original_generated_answer": clean(candidate_row.get("generated_answer") or candidate_row.get("answer_text")),
        "rewritten_answer": rewritten_answer,
        "cited_chunk_ids": cited_chunk_ids,
        "retrieved_chunk_ids": [clean(value) for value in candidate_row.get("retrieved_chunk_ids") or [] if clean(value)],
        "evidence_spans": evidence_spans,
        "evidence_span_chunk_ids": evidence_span_chunk_ids,
        "answer_claims": answer_claims,
        "unsupported_claims": unsupported_claims,
        "missing_information": missing_information,
        "answerability_from_cited_context": answerability is True,
        "llm_rewrite_status": llm_rewrite_status,
        "rewrite_status": verified_rewrite_status,
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "local_llm_used": True,
        "local_llm_provenance": dict(local_llm_provenance or {}),
        "db_context_used": bool(source_context.get("db_context_used")),
        "db_context_provenance": source_context.get("db_context_provenance") or {},
        "source_context_hash": source_hash,
        "verifier_passed": verifier_passed,
        "verifier_errors": errors,
        "normalization_notes": normalization_notes,
        "deterministic_claim_repair": deterministic_claim_repair,
        "split_span_support": split_span_support,
        "source_context_discrepancy": "",
        "model_assisted": True,
        "not_human_approved": True,
    }


def failure_row(
    candidate_row: Mapping[str, Any],
    source_context: Mapping[str, Any],
    *,
    reason: str,
    local_llm_provenance: Mapping[str, Any],
    local_llm_used: bool,
) -> dict[str, Any]:
    return {
        "query_id": clean(candidate_row.get("query_id")),
        "safe_query_text": clean(candidate_row.get("safe_query_text") or candidate_row.get("query")),
        "original_generated_answer": clean(candidate_row.get("generated_answer") or candidate_row.get("answer_text")),
        "rewritten_answer": "",
        "cited_chunk_ids": [clean(value) for value in candidate_row.get("cited_chunk_ids") or [] if clean(value)],
        "retrieved_chunk_ids": [clean(value) for value in candidate_row.get("retrieved_chunk_ids") or [] if clean(value)],
        "evidence_spans": [],
        "evidence_span_chunk_ids": [],
        "answer_claims": [],
        "unsupported_claims": [],
        "missing_information": [reason],
        "answerability_from_cited_context": False,
        "llm_rewrite_status": "",
        "rewrite_status": REWRITE_REQUIRED,
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "local_llm_used": local_llm_used,
        "local_llm_provenance": dict(local_llm_provenance),
        "db_context_used": bool(source_context.get("db_context_used")),
        "db_context_provenance": source_context.get("db_context_provenance") or {},
        "source_context_hash": sha256_payload(source_context),
        "verifier_passed": False,
        "verifier_errors": [reason],
        "normalization_notes": [],
        "deterministic_claim_repair": False,
        "split_span_support": False,
        "source_context_discrepancy": "",
        "model_assisted": local_llm_used,
        "not_human_approved": True,
    }


def preserved_v2_row(candidate_row: Mapping[str, Any], applied_row: Mapping[str, Any]) -> dict[str, Any]:
    citation_items = candidate_row.get("citation_items") if isinstance(candidate_row.get("citation_items"), list) else []
    evidence_spans = [clean(item.get("citation_text")) for item in citation_items if isinstance(item, Mapping) and clean(item.get("citation_text"))]
    action = clean(applied_row.get("assistant_review_action"))
    return {
        "query_id": clean(candidate_row.get("query_id")),
        "safe_query_text": clean(candidate_row.get("safe_query_text") or candidate_row.get("query")),
        "original_generated_answer": clean(candidate_row.get("generated_answer") or candidate_row.get("answer_text")),
        "rewritten_answer": clean(candidate_row.get("generated_answer") or candidate_row.get("answer_text")),
        "cited_chunk_ids": [clean(value) for value in candidate_row.get("cited_chunk_ids") or [] if clean(value)],
        "retrieved_chunk_ids": [clean(value) for value in candidate_row.get("retrieved_chunk_ids") or [] if clean(value)],
        "evidence_spans": evidence_spans,
        "evidence_span_chunk_ids": [clean(item.get("chunk_id")) for item in citation_items if isinstance(item, Mapping) and clean(item.get("chunk_id"))],
        "answer_claims": [],
        "unsupported_claims": [],
        "missing_information": [],
        "answerability_from_cited_context": True,
        "llm_rewrite_status": "",
        "rewrite_status": action or KEEP_CLEAN,
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "local_llm_used": False,
        "local_llm_provenance": {"baseline_preserved": True, "prompt_version": PROMPT_VERSION},
        "db_context_used": False,
        "db_context_provenance": {},
        "source_context_hash": "",
        "verifier_passed": True,
        "verifier_errors": [],
        "normalization_notes": [],
        "deterministic_claim_repair": False,
        "split_span_support": False,
        "source_context_discrepancy": "",
        "model_assisted": False,
        "not_human_approved": True,
    }


def classify_failure_causes(candidate_row: Mapping[str, Any], applied_row: Mapping[str, Any]) -> list[str]:
    causes: set[str] = set()
    query = clean(candidate_row.get("safe_query_text") or candidate_row.get("query"))
    citation_text = " ".join(
        clean(item.get("citation_text"))
        for item in candidate_row.get("citation_items") or []
        if isinstance(item, Mapping)
    )
    judgment = clean(applied_row.get("assistant_citation_support_judgment"))
    answer_judgment = clean(applied_row.get("assistant_answer_judgment"))
    if not candidate_row.get("cited_chunk_ids") or not candidate_row.get("citation_items"):
        causes.add("missing required field")
    if any(token in query for token in ("와", "과", "및", "그리고")) or len(re.findall(r"\?", query)) > 1:
        causes.add("multi-field question answered partially")
    if "citation_contains_correct_answer_but_generated_answer_incomplete" in judgment:
        causes.add("cited evidence adequate but extraction incomplete")
    if "claim" in answer_judgment:
        causes.add("claim-check judgment missing")
    if "title" in answer_judgment or "entity" in answer_judgment:
        causes.add("title/entity disambiguation incomplete")
    if len(citation_text) < 30:
        causes.add("cited evidence inadequate")
    if not any(isinstance(item, Mapping) and item.get("citation_locator") for item in candidate_row.get("citation_items") or []):
        causes.add("citation locator missing or weak")
    if not causes:
        causes.add("section summary collapsed to first sentence")
    return sorted(causes)


def classify_v2_verifier_failure(row: Mapping[str, Any]) -> list[str]:
    errors = " ".join(clean_list(row.get("verifier_errors")))
    classes: set[str] = set()
    if "strict JSON object" in errors or "JSONDecodeError" in errors or "Unterminated string" in errors:
        classes.add("strict_json_output_failure")
    if "answer_claims are required" in errors:
        classes.add("missing_answer_claims")
    if "answer claim is not supported by evidence spans" in errors:
        classes.add("span_claim_binding_failure")
    if (
        classes.intersection({"missing_answer_claims", "span_claim_binding_failure"})
        and len(row.get("evidence_spans") or []) > 1
    ):
        classes.add("evidence_span_split_required")
    if (
        "citation_inadequate" in errors
        or "not_answerable" in errors
        or row.get("answerability_from_cited_context") is False
        and not classes.intersection({"strict_json_output_failure"})
    ):
        classes.add("genuine_not_answerable_or_citation_inadequate")
    if not classes:
        classes.add("span_claim_binding_failure")
    return sorted(classes)


def applied_rows_by_id(applied_v1: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = applied_v1.get("applied_rows") if isinstance(applied_v1.get("applied_rows"), list) else []
    return {clean(row.get("query_id")): dict(row) for row in rows if isinstance(row, Mapping) and clean(row.get("query_id"))}


def original_action(applied_map: Mapping[str, Mapping[str, Any]], query_id: str) -> str:
    return clean((applied_map.get(query_id) or {}).get("assistant_review_action"))


def v2_action_for_row(row: Mapping[str, Any], original: str) -> str:
    if original == KEEP_CLEANUP:
        return KEEP_CLEANUP
    if original == KEEP_CLEAN:
        return KEEP_CLEAN
    if row.get("verifier_passed") is True and row.get("answerability_from_cited_context") is True:
        status = clean(row.get("rewrite_status"))
        if status == KEEP_CLEANUP:
            return KEEP_CLEANUP
        return KEEP_CLEAN
    errors = " ".join(row.get("verifier_errors") or [])
    if "LOCAL_LLM" in errors or "DB_" in errors:
        return REWRITE_REQUIRED
    if "outside candidate" in errors:
        return SOURCE_BINDING_REVIEW_REQUIRED
    if "evidence span not found" in errors:
        return CITATION_INADEQUATE
    if row.get("answerability_from_cited_context") is False and row.get("missing_information"):
        return NOT_ANSWERABLE
    return REWRITE_REQUIRED


def citation_judgment_for_row(row: Mapping[str, Any], action: str) -> str:
    if action in {KEEP_CLEAN, KEEP_CLEANUP} and row.get("verifier_passed") is True:
        return "fully_supported"
    if action == CITATION_INADEQUATE:
        return "citation_inadequate"
    if action == NOT_ANSWERABLE:
        return "not_answerable_from_cited_context"
    if action == SOURCE_BINDING_REVIEW_REQUIRED:
        return "source_binding_review_required"
    return "citation_contains_correct_answer_but_generated_answer_incomplete"


def build_draft_rows(
    *,
    rewritten_rows: list[Mapping[str, Any]],
    applied_v1: Mapping[str, Any],
) -> list[dict[str, Any]]:
    applied_map = applied_rows_by_id(applied_v1)
    draft_rows: list[dict[str, Any]] = []
    for row in rewritten_rows:
        query_id = clean(row.get("query_id"))
        original = original_action(applied_map, query_id)
        action = v2_action_for_row(row, original)
        citation_judgment = citation_judgment_for_row(row, action)
        draft_rows.append(
            {
                "query_id": query_id,
                "query": clean(row.get("safe_query_text")),
                "generated_short_answer": clean(row.get("rewritten_answer")),
                "assistant_answer_judgment": "source_supported_rewrite" if action in {KEEP_CLEAN, KEEP_CLEANUP} else "rewrite_still_required",
                "assistant_citation_support_judgment": citation_judgment,
                "assistant_review_action": action,
                "failure_causes": row.get("failure_causes") if isinstance(row.get("failure_causes"), list) else [],
                "suggested_extractive_answer_not_gold": clean(row.get("rewritten_answer")),
                "assistant_review_notes": "; ".join(row.get("verifier_errors") or []) or "diagnostic local LLM v2 review draft",
                "cited_chunk_ids": row.get("cited_chunk_ids") or [],
                "retrieved_chunk_ids": row.get("retrieved_chunk_ids") or [],
                "evidence_spans": row.get("evidence_spans") or [],
                "model_assisted": bool(row.get("model_assisted")),
                "not_human_approved": True,
                "diagnostic_only": True,
                "official_metric_input": False,
                "promotion_evidence": False,
                "human_approval_required_for_official_metric": True,
                "model_reviewer": "local_llm_rewrite_v2_verifier",
            }
        )
    return draft_rows


def metric_preview_from_draft(draft_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    actions = Counter(clean(row.get("assistant_review_action")) for row in draft_rows)
    citations = Counter(clean(row.get("assistant_citation_support_judgment")) for row in draft_rows)
    official_rows = sum(1 for row in draft_rows if row.get("official_metric_input") is True)
    unresolved_actions = {
        REWRITE_REQUIRED,
        CITATION_INADEQUATE,
        SOURCE_BINDING_REVIEW_REQUIRED,
        NOT_ANSWERABLE,
    }
    unresolved_count = sum(count for action, count in actions.items() if action in unresolved_actions)
    return {
        "answer_pass_preview_count": actions.get(KEEP_CLEAN, 0),
        "cleanup_pass_preview_count": actions.get(KEEP_CLEANUP, 0),
        "rewrite_required_count": unresolved_count,
        "literal_answer_rewrite_required_count": actions.get(REWRITE_REQUIRED, 0),
        "citation_inadequate_count": actions.get(CITATION_INADEQUATE, 0),
        "source_binding_review_required_count": actions.get(SOURCE_BINDING_REVIEW_REQUIRED, 0),
        "not_answerable_from_cited_context_count": actions.get(NOT_ANSWERABLE, 0),
        "unresolved_diagnostic_count": unresolved_count,
        "citation_fully_supported_generated_answer_count": citations.get("fully_supported", 0),
        "citation_contains_correct_answer_but_generated_answer_incomplete_count": citations.get(
            "citation_contains_correct_answer_but_generated_answer_incomplete", 0
        ),
        "official_metric_input_rows": official_rows,
        "official_metric_status": "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY"
        if official_rows == 0
        else "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_NONZERO",
        "official_answer_success_count": 0,
        "official_citation_success_count": 0,
        "diagnostic_preview_not_official_metric": True,
    }


def target_status(metric: Mapping[str, Any]) -> dict[str, Any]:
    clean_count = int(metric.get("answer_pass_preview_count") or 0)
    cleanup_count = int(metric.get("cleanup_pass_preview_count") or 0)
    rewrite_count = int(metric.get("unresolved_diagnostic_count") or metric.get("rewrite_required_count") or 0)
    citation_count = int(metric.get("citation_fully_supported_generated_answer_count") or 0)
    return {
        "minimum_diagnostic_improvement": rewrite_count <= 20,
        "metric_preview_candidate": clean_count >= 47 and rewrite_count <= 13,
        "metric_pass_candidate": clean_count >= 53 and rewrite_count <= 10 and citation_count >= 60,
        "official_metric": False,
        "official_metric_blocker": "human-approved policy artifact required before opening official answer/citation denominators",
        "thresholds": {
            "minimum_diagnostic_improvement": "rewrite_required <= 20",
            "metric_preview_candidate": "clean_pass >= 47 and rewrite_required <= 13",
            "metric_pass_candidate": "clean_pass >= 53 and rewrite_required <= 10 and citation_supported >= 60",
        },
    }


def build_v2_reports(
    *,
    generated_rows: list[Mapping[str, Any]],
    applied_v1: Mapping[str, Any],
    rewritten_rows: list[Mapping[str, Any]],
    db_context_report: Mapping[str, Any],
    llm_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    generated_ids = [clean(row.get("query_id")) for row in generated_rows]
    draft_rows = build_draft_rows(rewritten_rows=rewritten_rows, applied_v1=applied_v1)
    metric_v2 = metric_preview_from_draft(draft_rows)
    applied_map = applied_rows_by_id(applied_v1)
    v1_metric = applied_v1.get("diagnostic_metric_preview") if isinstance(applied_v1.get("diagnostic_metric_preview"), Mapping) else {}
    improved: list[str] = []
    regressed: list[str] = []
    unchanged: list[str] = []
    for draft in draft_rows:
        query_id = clean(draft.get("query_id"))
        old_action = original_action(applied_map, query_id)
        new_action = clean(draft.get("assistant_review_action"))
        if old_action == REWRITE_REQUIRED and new_action in {KEEP_CLEAN, KEEP_CLEANUP}:
            improved.append(query_id)
        elif old_action in {KEEP_CLEAN, KEEP_CLEANUP} and new_action not in {old_action, KEEP_CLEAN, KEEP_CLEANUP}:
            regressed.append(query_id)
        elif old_action == new_action:
            unchanged.append(query_id)
        else:
            unchanged.append(query_id)

    action_counts = Counter(clean(row.get("assistant_review_action")) for row in draft_rows)
    citation_counts = Counter(clean(row.get("assistant_citation_support_judgment")) for row in draft_rows)
    verifier_failures = [clean(row.get("query_id")) for row in rewritten_rows if row.get("verifier_passed") is not True]
    local_llm_unavailable = [
        clean(row.get("query_id"))
        for row in rewritten_rows
        if "LOCAL_LLM_UNAVAILABLE" in " ".join(row.get("verifier_errors") or [])
    ]
    db_unavailable = db_context_report.get("status") in {
        "DB_UNAVAILABLE_FAIL_CLOSED",
        "DB_READ_ONLY_GUARD_FAILED",
    }
    applied_v2 = {
        "schema_version": "rag_text_namu_answer_citation_review_applied_diagnostic_v2",
        "generated_at": now_utc(),
        "status": "APPLIED_DIAGNOSTIC_ONLY",
        "diagnostic_only": True,
        "not_official_gold": True,
        "promotion_evidence": False,
        "official_metric_input": False,
        "row_count": len(draft_rows),
        "generated_answer_row_count": len(generated_rows),
        "draft_row_count": len(draft_rows),
        "review_action_counts": dict(sorted(action_counts.items())),
        "assistant_citation_support_judgment_counts": dict(sorted(citation_counts.items())),
        "diagnostic_metric_preview": metric_v2,
        "applied_rows": draft_rows,
        "guardrails": {
            "official_metrics_opened": False,
            "official_metric_input_rows": metric_v2["official_metric_input_rows"],
            "promotion_evidence_rows": sum(1 for row in draft_rows if row.get("promotion_evidence") is True),
            "model_assisted_not_human_approved": True,
            "production_index_mutation": False,
            "official_denominator_registry_mutation": False,
        },
        "validation": {
            "ok": metric_v2["official_metric_input_rows"] == 0
            and all(row.get("promotion_evidence") is False for row in draft_rows),
            "errors": [],
        },
        "remaining_blockers": [
            "official answer/citation denominator requires explicit human-approved policy artifact",
            "model-assisted diagnostic output is not official gold",
        ],
    }
    comparison = {
        "v1_clean_pass": int(v1_metric.get("answer_pass_preview_count") or 0),
        "v1_cleanup": int(v1_metric.get("cleanup_pass_preview_count") or 0),
        "v1_rewrite_required": int(v1_metric.get("rewrite_required_count") or 0),
        "v1_citation_fully_supported_generated_answer": int(
            v1_metric.get("citation_fully_supported_generated_answer_count") or 0
        ),
        "v1_citation_contains_correct_answer_but_generated_answer_incomplete": int(
            v1_metric.get("citation_contains_correct_answer_but_generated_answer_incomplete_count") or 0
        ),
        "v2_clean_pass": metric_v2["answer_pass_preview_count"],
        "v2_cleanup": metric_v2["cleanup_pass_preview_count"],
        "v2_rewrite_required": metric_v2["rewrite_required_count"],
        "v2_literal_answer_rewrite_required": metric_v2["literal_answer_rewrite_required_count"],
        "v2_unresolved_diagnostic_count": metric_v2["unresolved_diagnostic_count"],
        "v2_citation_fully_supported_generated_answer": metric_v2[
            "citation_fully_supported_generated_answer_count"
        ],
        "v2_citation_contains_correct_answer_but_generated_answer_incomplete": metric_v2[
            "citation_contains_correct_answer_but_generated_answer_incomplete_count"
        ],
        "rewrite_reduction_count": int(v1_metric.get("rewrite_required_count") or 0) - metric_v2["rewrite_required_count"],
        "rows_improved": improved,
        "rows_regressed": regressed,
        "rows_unchanged": unchanged,
        "rows_blocked_by_db_unavailable": len([row for row in generated_rows if original_action(applied_map, clean(row.get("query_id"))) == REWRITE_REQUIRED])
        if db_unavailable
        else 0,
        "rows_blocked_by_db_guard_failed": len(
            [
                row
                for row in generated_rows
                if original_action(applied_map, clean(row.get("query_id"))) == REWRITE_REQUIRED
            ]
        )
        if db_context_report.get("status") == "DB_READ_ONLY_GUARD_FAILED"
        else 0,
        "rows_blocked_by_local_llm_unavailable": len(local_llm_unavailable),
        "rows_blocked_by_verifier": len(verifier_failures),
        "verifier_failure_query_ids": verifier_failures,
        "official_metric_input_rows": metric_v2["official_metric_input_rows"],
        "official_metric_status": metric_v2["official_metric_status"],
        "diagnostic_quality_target_status": target_status(metric_v2),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "status": "DIAGNOSTIC_LOCAL_LLM_REWRITE_V2_COMPLETE",
        "generated_query_ids": generated_ids,
        "generated_answer_rows": len(generated_rows),
        "rewritten_rows": [dict(row) for row in rewritten_rows],
        "draft_rows": draft_rows,
        "draft_summary": {
            "schema_version": "rag_text_namu_answer_citation_review_draft_local_llm_v2_summary",
            "row_count": len(draft_rows),
            "review_action_counts": dict(sorted(action_counts.items())),
            "assistant_citation_support_judgment_counts": dict(sorted(citation_counts.items())),
            "official_metric_input_rows": metric_v2["official_metric_input_rows"],
            "promotion_evidence_rows": sum(1 for row in draft_rows if row.get("promotion_evidence") is True),
            "model_assisted": True,
            "not_human_approved": True,
        },
        "applied_v2": applied_v2,
        "db_context_report": dict(db_context_report),
        "local_llm_provenance": dict(llm_provenance),
        "comparison": comparison,
        "guardrails": {
            "diagnostic_only": True,
            "official_metric_input_rows": 0,
            "official_metrics_opened": False,
            "promotion_evidence": False,
            "official_denominator_registry_mutation": False,
            "production_namespace_vector_index_mutation": False,
            "candidate_artifact_mutation": False,
            "immutable_baseline_mutation": False,
            "gold_registry_mutation": False,
            "route_fallback_labels_diagnostic_only": True,
        },
    }


def build_v2_1_reports(
    *,
    generated_rows: list[Mapping[str, Any]],
    applied_v2: Mapping[str, Any],
    rewritten_rows: list[Mapping[str, Any]],
    db_context_report: Mapping[str, Any],
    llm_provenance: Mapping[str, Any],
    target_query_ids: list[str],
) -> dict[str, Any]:
    report = build_v2_reports(
        generated_rows=generated_rows,
        applied_v1=applied_v2,
        rewritten_rows=rewritten_rows,
        db_context_report=db_context_report,
        llm_provenance=llm_provenance,
    )
    report["schema_version"] = SCHEMA_VERSION_V2_1
    report["status"] = "DIAGNOSTIC_LOCAL_LLM_REWRITE_V2_1_COMPLETE"
    report["target_query_ids"] = target_query_ids
    report["non_target_rows_preserved_from_v2"] = len(
        [row for row in rewritten_rows if clean(row.get("query_id")) not in set(target_query_ids)]
    )
    report["rewrite_required_query_ids"] = target_query_ids
    report["draft_summary"]["schema_version"] = "rag_text_namu_answer_citation_review_draft_local_llm_v2_1_summary"
    report["applied_v2"]["schema_version"] = "rag_text_namu_answer_citation_review_applied_diagnostic_v2_1"
    report["applied_v2"]["status"] = "APPLIED_DIAGNOSTIC_ONLY"
    report["applied_v2"]["v2_baseline_schema_version"] = applied_v2.get("schema_version")
    report["applied_v2"]["target_query_ids"] = target_query_ids

    comparison = report["comparison"]
    v2_vs_v2_1 = {
        "v2_clean_pass": comparison["v1_clean_pass"],
        "v2_cleanup": comparison["v1_cleanup"],
        "v2_rewrite_required": comparison["v1_rewrite_required"],
        "v2_citation_fully_supported": comparison["v1_citation_fully_supported_generated_answer"],
        "v2_1_clean_pass": comparison["v2_clean_pass"],
        "v2_1_cleanup": comparison["v2_cleanup"],
        "v2_1_rewrite_required": comparison["v2_rewrite_required"],
        "v2_1_citation_fully_supported": comparison["v2_citation_fully_supported_generated_answer"],
        "rows_improved": comparison["rows_improved"],
        "rows_regressed": comparison["rows_regressed"],
        "rows_unchanged": comparison["rows_unchanged"],
        "verifier_failures": comparison["verifier_failure_query_ids"],
        "official_metric_input_rows": comparison["official_metric_input_rows"],
        "official_metric_status": comparison["official_metric_status"],
        "diagnostic_quality_target_status": comparison["diagnostic_quality_target_status"],
    }
    comparison.update({f"v2_1_explicit_{key}": value for key, value in v2_vs_v2_1.items()})
    report["v2_vs_v2_1"] = v2_vs_v2_1
    report["guardrails"]["official_metrics_opened"] = False
    report["guardrails"]["official_metric_input_rows"] = 0
    report["guardrails"]["promotion_evidence"] = False
    report["guardrails"]["model_assisted_not_human_approved"] = True
    return report


def compact_md_report(report: Mapping[str, Any]) -> str:
    comparison = report.get("comparison") if isinstance(report.get("comparison"), Mapping) else {}
    v2_compare = report.get("v2_vs_v2_1") if isinstance(report.get("v2_vs_v2_1"), Mapping) else {}
    db_report = report.get("db_context_report") if isinstance(report.get("db_context_report"), Mapping) else {}
    llm = report.get("local_llm_provenance") if isinstance(report.get("local_llm_provenance"), Mapping) else {}
    target = comparison.get("diagnostic_quality_target_status") if isinstance(comparison.get("diagnostic_quality_target_status"), Mapping) else {}
    is_v2_1 = clean(report.get("schema_version")) == SCHEMA_VERSION_V2_1
    version_label = "V2.1" if is_v2_1 else "V2"
    baseline_label = "V2" if is_v2_1 else "V1"
    current_label = "V2.1" if is_v2_1 else "V2"
    baseline_clean = v2_compare.get("v2_clean_pass") if is_v2_1 else comparison.get("v1_clean_pass")
    baseline_cleanup = v2_compare.get("v2_cleanup") if is_v2_1 else comparison.get("v1_cleanup")
    baseline_rewrite = v2_compare.get("v2_rewrite_required") if is_v2_1 else comparison.get("v1_rewrite_required")
    baseline_citation = (
        v2_compare.get("v2_citation_fully_supported")
        if is_v2_1
        else comparison.get("v1_citation_fully_supported_generated_answer")
    )
    baseline_citation_incomplete = (
        comparison.get("v1_citation_contains_correct_answer_but_generated_answer_incomplete")
    )
    current_clean = v2_compare.get("v2_1_clean_pass") if is_v2_1 else comparison.get("v2_clean_pass")
    current_cleanup = v2_compare.get("v2_1_cleanup") if is_v2_1 else comparison.get("v2_cleanup")
    current_rewrite = v2_compare.get("v2_1_rewrite_required") if is_v2_1 else comparison.get("v2_rewrite_required")
    current_literal_rewrite = comparison.get("v2_literal_answer_rewrite_required")
    current_citation = (
        v2_compare.get("v2_1_citation_fully_supported")
        if is_v2_1
        else comparison.get("v2_citation_fully_supported_generated_answer")
    )
    current_citation_incomplete = comparison.get("v2_citation_contains_correct_answer_but_generated_answer_incomplete")
    lines = [
        f"# TEXT/Namu Local LLM Answer/Citation Diagnostic {version_label}",
        "",
        f"Status: `{report.get('status')}`",
        "",
        "## Local Context",
        "",
        f"- DB status: `{db_report.get('status')}`; read-only confirmed: `{db_report.get('db_read_only_confirmed')}`; loaded SearchUnits: `{db_report.get('loaded_search_unit_count')}`.",
        f"- Local LLM: `{llm.get('backend')}` `{llm.get('model')}` at `{llm.get('base_url')}`.",
        "- Prompt input excludes expected-answer, review-label, human-label, embedding_text, debug_text, and raw source_locator fields.",
        "",
        f"## {baseline_label} vs {current_label}",
        "",
        f"| Metric | {baseline_label} | {current_label} |",
        "|---|---:|---:|",
        f"| Clean pass preview | {baseline_clean} | {current_clean} |",
        f"| Cleanup preview | {baseline_cleanup} | {current_cleanup} |",
        f"| Unresolved / rewrite required | {baseline_rewrite} | {current_rewrite} |",
        f"| Literal answer rewrite required | {baseline_rewrite} | {current_literal_rewrite} |",
        f"| Citation fully supported generated answer | {baseline_citation} | {current_citation} |",
        f"| Citation contains answer but generated answer incomplete | {baseline_citation_incomplete} | {current_citation_incomplete} |",
        "",
        "## Row Movement",
        "",
        f"- Improved rows: `{len(comparison.get('rows_improved') or [])}`.",
        f"- Regressed rows: `{len(comparison.get('rows_regressed') or [])}`.",
        f"- Unchanged rows: `{len(comparison.get('rows_unchanged') or [])}`.",
        f"- Rows blocked by DB unavailable: `{comparison.get('rows_blocked_by_db_unavailable')}`.",
        f"- Rows blocked by local LLM unavailable: `{comparison.get('rows_blocked_by_local_llm_unavailable')}`.",
        f"- Rows blocked by verifier: `{comparison.get('rows_blocked_by_verifier')}`.",
        "",
        "## Target Status",
        "",
        f"- Minimum diagnostic improvement: `{target.get('minimum_diagnostic_improvement')}`.",
        f"- Metric preview candidate: `{target.get('metric_preview_candidate')}`.",
        f"- Metric pass candidate: `{target.get('metric_pass_candidate')}`.",
        f"- Official metric: `{target.get('official_metric')}`.",
        "",
        "## Guardrails",
        "",
        "- `official_metric_input_rows=0`.",
        "- `promotion_evidence=false` for all rows.",
        "- Official denominator registry, production namespace/vector/index, candidate artifacts, immutable baselines, and gold registries were not write targets.",
        "- This is model-assisted diagnostic output only and is not human-approved gold.",
        "",
    ]
    return "\n".join(lines)


def applied_md_report(applied: Mapping[str, Any]) -> str:
    metric = applied.get("diagnostic_metric_preview") if isinstance(applied.get("diagnostic_metric_preview"), Mapping) else {}
    schema = clean(applied.get("schema_version"))
    version_label = "V2.1" if schema.endswith("_v2_1") else "V2"
    return "\n".join(
        [
            f"# TEXT/Namu Answer/Citation Review Applied Diagnostic {version_label}",
            "",
            f"Status: `{applied.get('status')}`",
            "",
            "## Diagnostic Metric Preview",
            "",
            f"- answer_pass_preview_count: `{metric.get('answer_pass_preview_count')}`",
            f"- cleanup_pass_preview_count: `{metric.get('cleanup_pass_preview_count')}`",
            f"- rewrite_required_count: `{metric.get('rewrite_required_count')}`",
            f"- literal_answer_rewrite_required_count: `{metric.get('literal_answer_rewrite_required_count')}`",
            f"- unresolved_diagnostic_count: `{metric.get('unresolved_diagnostic_count')}`",
            f"- citation_fully_supported_generated_answer_count: `{metric.get('citation_fully_supported_generated_answer_count')}`",
            f"- citation_contains_correct_answer_but_generated_answer_incomplete_count: `{metric.get('citation_contains_correct_answer_but_generated_answer_incomplete_count')}`",
            f"- official_metric_input_rows: `{metric.get('official_metric_input_rows')}`",
            f"- official_metric_status: `{metric.get('official_metric_status')}`",
            "",
            "All rows remain `diagnostic_only=true`, `official_metric_input=false`, and `promotion_evidence=false`.",
            "",
        ]
    )


def draft_summary_md_report(summary: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# TEXT/Namu Answer/Citation Review Draft Local LLM V2.1 Summary",
            "",
            f"- row_count: `{summary.get('row_count')}`",
            f"- official_metric_input_rows: `{summary.get('official_metric_input_rows')}`",
            f"- promotion_evidence_rows: `{summary.get('promotion_evidence_rows')}`",
            f"- model_assisted: `{summary.get('model_assisted')}`",
            f"- not_human_approved: `{summary.get('not_human_approved')}`",
            "",
        ]
    )


def v2_input_report_md(report: Mapping[str, Any]) -> str:
    comparison = report.get("comparison") if isinstance(report.get("comparison"), Mapping) else {}
    version_label = "V2.1" if clean(report.get("schema_version")) == SCHEMA_VERSION_V2_1 else "V2"
    return "\n".join(
        [
            f"# TEXT/Namu Generated Answer Review Input Local LLM {version_label} Report",
            "",
            f"Generated answer rows: `{report.get('generated_answer_rows')}`.",
            f"Rows improved: `{len(comparison.get('rows_improved') or [])}`.",
            f"Rows blocked by verifier: `{comparison.get('rows_blocked_by_verifier')}`.",
            "",
            "The artifact is diagnostic-only and is not official metric input.",
            "",
        ]
    )


def write_report_bundle(paths: Mapping[str, Path], report: Mapping[str, Any]) -> None:
    write_jsonl(paths["v2_jsonl"], report["rewritten_rows"])
    write_json(paths["v2_report_json"], report)
    paths["v2_report_md"].parent.mkdir(parents=True, exist_ok=True)
    paths["v2_report_md"].write_text(v2_input_report_md(report), encoding="utf-8")
    write_jsonl(paths["draft_jsonl"], report["draft_rows"])
    write_json(paths["draft_summary_json"], report["draft_summary"])
    if paths.get("draft_summary_md"):
        paths["draft_summary_md"].write_text(draft_summary_md_report(report["draft_summary"]), encoding="utf-8")
    write_json(paths["applied_json"], report["applied_v2"])
    paths["applied_md"].write_text(applied_md_report(report["applied_v2"]), encoding="utf-8")
    write_json(paths["improvement_json"], report)
    paths["improvement_md"].write_text(compact_md_report(report), encoding="utf-8")


def run_v2_1_repair(
    *,
    generated_input: Path = DEFAULT_GENERATED_INPUT,
    v2_rewrite_jsonl: Path = DEFAULT_V2_REWRITE_JSONL,
    applied_v2_path: Path = DEFAULT_APPLIED_V2,
    target_query_ids: list[str] | None = None,
    db_dsn: str = DEFAULT_DB_DSN,
    backend: str = DEFAULT_BACKEND,
    base_url: str = "",
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    max_tokens: int = 1200,
    timeout_seconds: int = 120,
    strict_json_retries: int = 2,
    output_paths: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    generated_rows = read_jsonl(generated_input)
    v2_rows = read_jsonl(v2_rewrite_jsonl)
    applied_v2 = read_json(applied_v2_path)
    target_ids = list(target_query_ids or DEFAULT_V2_1_TARGET_QUERY_IDS)
    target_set = set(target_ids)
    generated_by_id = {clean(row.get("query_id")): row for row in generated_rows if clean(row.get("query_id"))}
    target_generated_rows = [generated_by_id[query_id] for query_id in target_ids if query_id in generated_by_id]
    db_context = load_db_context(target_generated_rows, db_dsn=db_dsn)
    resolved_base_url = resolve_base_url(backend, base_url)
    llm_provenance = {
        "backend": backend,
        "base_url": resolved_base_url,
        "model": model,
        "prompt_version": PROMPT_VERSION_V2_1,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timestamp": now_utc(),
        "local_endpoint_only": True,
        "external_cloud_llm_run": False,
        "targeted_v2_1_repair": True,
    }
    blockers = local_llm_entry_blockers(
        backend=backend,
        base_url=resolved_base_url,
        model=model,
        check_endpoint=True,
        timeout_seconds=5,
    )
    llm_provenance["entry_blockers"] = blockers

    rewritten_rows: list[dict[str, Any]] = []
    for v2_row in v2_rows:
        query_id = clean(v2_row.get("query_id"))
        if query_id not in target_set:
            rewritten_rows.append(dict(v2_row))
            continue

        candidate = generated_by_id.get(query_id)
        if not candidate:
            failed = dict(v2_row)
            failed.update(
                {
                    "rewrite_status": REWRITE_REQUIRED,
                    "verifier_passed": False,
                    "verifier_errors": [f"V2_1_TARGET_GENERATED_ROW_MISSING: {query_id}"],
                    "deterministic_claim_repair": False,
                    "split_span_support": False,
                }
            )
            failed["verifier_failure_classification"] = classify_v2_verifier_failure(v2_row)
            rewritten_rows.append(failed)
            continue

        context = build_source_context(candidate, db_context)
        classification = classify_v2_verifier_failure(v2_row)
        if db_context.get("status") in {"DB_UNAVAILABLE_FAIL_CLOSED", "DB_READ_ONLY_GUARD_FAILED"}:
            failed = failure_row(
                candidate,
                context,
                reason=f"{db_context.get('status')}: {db_context.get('blocker')}",
                local_llm_provenance=llm_provenance,
                local_llm_used=False,
            )
            failed["failure_causes"] = classification
            failed["verifier_failure_classification"] = classification
            rewritten_rows.append(failed)
            continue
        if blockers:
            failed = failure_row(
                candidate,
                context,
                reason="LOCAL_LLM_UNAVAILABLE: " + "; ".join(blockers),
                local_llm_provenance=llm_provenance,
                local_llm_used=False,
            )
            failed["failure_causes"] = classification
            failed["verifier_failure_classification"] = classification
            rewritten_rows.append(failed)
            continue

        try:
            prompt = build_rewrite_prompt(candidate, context, prompt_version=PROMPT_VERSION_V2_1)
            parsed, strict_json_meta = call_local_llm_strict_json(
                backend=backend,
                base_url=resolved_base_url,
                model=model,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
                retries=strict_json_retries,
            )
            provenance = {
                **llm_provenance,
                **strict_json_meta,
                "prompt_sha256": sha256_text(prompt),
            }
            verified = verify_llm_output(candidate, context, parsed, local_llm_provenance=provenance)
            verified["failure_causes"] = classification
            verified["verifier_failure_classification"] = classification
            rewritten_rows.append(verified)
        except Exception as exc:
            failed = failure_row(
                candidate,
                context,
                reason=f"LOCAL_LLM_REWRITE_FAILED: {type(exc).__name__}: {exc}",
                local_llm_provenance=llm_provenance,
                local_llm_used=True,
            )
            failed["failure_causes"] = classification
            failed["verifier_failure_classification"] = classification
            rewritten_rows.append(failed)

    report = build_v2_1_reports(
        generated_rows=generated_rows,
        applied_v2=applied_v2,
        rewritten_rows=rewritten_rows,
        db_context_report=db_context,
        llm_provenance=llm_provenance,
        target_query_ids=target_ids,
    )
    paths = dict(output_paths or default_output_paths("v2_1"))
    write_report_bundle(paths, report)
    return report


def run_rewrite(
    *,
    generated_input: Path = DEFAULT_GENERATED_INPUT,
    applied_v1_path: Path = DEFAULT_APPLIED_V1,
    db_dsn: str = DEFAULT_DB_DSN,
    backend: str = DEFAULT_BACKEND,
    base_url: str = "",
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    max_tokens: int = 900,
    timeout_seconds: int = 120,
    strict_json_retries: int = 1,
    output_paths: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    generated_rows = read_jsonl(generated_input)
    applied_v1 = read_json(applied_v1_path)
    applied_map = applied_rows_by_id(applied_v1)
    rewrite_ids = [
        clean(row.get("query_id"))
        for row in generated_rows
        if original_action(applied_map, clean(row.get("query_id"))) == REWRITE_REQUIRED
    ]
    db_context = load_db_context(generated_rows, db_dsn=db_dsn)
    resolved_base_url = resolve_base_url(backend, base_url)
    llm_provenance = {
        "backend": backend,
        "base_url": resolved_base_url,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timestamp": now_utc(),
        "local_endpoint_only": True,
        "external_cloud_llm_run": False,
    }
    blockers = local_llm_entry_blockers(
        backend=backend,
        base_url=resolved_base_url,
        model=model,
        check_endpoint=True,
        timeout_seconds=5,
    )
    llm_provenance["entry_blockers"] = blockers

    rewritten_rows: list[dict[str, Any]] = []
    for row in generated_rows:
        query_id = clean(row.get("query_id"))
        applied_row = applied_map.get(query_id, {})
        action = clean(applied_row.get("assistant_review_action"))
        if action != REWRITE_REQUIRED:
            rewritten_rows.append(preserved_v2_row(row, applied_row))
            continue

        context = build_source_context(row, db_context)
        causes = classify_failure_causes(row, applied_row)
        if db_context.get("status") in {"DB_UNAVAILABLE_FAIL_CLOSED", "DB_READ_ONLY_GUARD_FAILED"}:
            failed = failure_row(
                row,
                context,
                reason=f"{db_context.get('status')}: {db_context.get('blocker')}",
                local_llm_provenance=llm_provenance,
                local_llm_used=False,
            )
            failed["failure_causes"] = causes
            rewritten_rows.append(failed)
            continue
        if blockers:
            failed = failure_row(
                row,
                context,
                reason="LOCAL_LLM_UNAVAILABLE: " + "; ".join(blockers),
                local_llm_provenance=llm_provenance,
                local_llm_used=False,
            )
            failed["failure_causes"] = causes
            rewritten_rows.append(failed)
            continue
        try:
            prompt = build_rewrite_prompt(row, context, prompt_version=PROMPT_VERSION)
            parsed, strict_json_meta = call_local_llm_strict_json(
                backend=backend,
                base_url=resolved_base_url,
                model=model,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
                retries=strict_json_retries,
            )
            provenance = {
                **llm_provenance,
                **strict_json_meta,
                "prompt_sha256": sha256_text(prompt),
            }
            verified = verify_llm_output(row, context, parsed, local_llm_provenance=provenance)
            verified["failure_causes"] = causes
            rewritten_rows.append(verified)
        except Exception as exc:
            failed = failure_row(
                row,
                context,
                reason=f"LOCAL_LLM_REWRITE_FAILED: {type(exc).__name__}: {exc}",
                local_llm_provenance=llm_provenance,
                local_llm_used=True,
            )
            failed["failure_causes"] = causes
            rewritten_rows.append(failed)

    report = build_v2_reports(
        generated_rows=generated_rows,
        applied_v1=applied_v1,
        rewritten_rows=rewritten_rows,
        db_context_report=db_context,
        llm_provenance=llm_provenance,
    )
    report["rewrite_required_query_ids"] = rewrite_ids
    paths = dict(output_paths or default_output_paths())
    write_jsonl(paths["v2_jsonl"], rewritten_rows)
    write_json(paths["v2_report_json"], report)
    paths["v2_report_md"].parent.mkdir(parents=True, exist_ok=True)
    paths["v2_report_md"].write_text(v2_input_report_md(report), encoding="utf-8")
    write_jsonl(paths["draft_jsonl"], report["draft_rows"])
    write_json(paths["draft_summary_json"], report["draft_summary"])
    write_json(paths["applied_json"], report["applied_v2"])
    paths["applied_md"].write_text(applied_md_report(report["applied_v2"]), encoding="utf-8")
    write_json(paths["improvement_json"], report)
    paths["improvement_md"].write_text(compact_md_report(report), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("v2", "v2_1"), default="v2_1")
    parser.add_argument("--generated-input", type=Path, default=DEFAULT_GENERATED_INPUT)
    parser.add_argument("--applied-v1", type=Path, default=DEFAULT_APPLIED_V1)
    parser.add_argument("--v2-rewrite-jsonl", type=Path, default=DEFAULT_V2_REWRITE_JSONL)
    parser.add_argument("--applied-v2", type=Path, default=DEFAULT_APPLIED_V2)
    parser.add_argument("--target-query-id", action="append", dest="target_query_ids")
    parser.add_argument("--db-dsn", default=DEFAULT_DB_DSN)
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--strict-json-retries", type=int, default=2)
    args = parser.parse_args(argv)
    if args.mode == "v2":
        report = run_rewrite(
            generated_input=args.generated_input,
            applied_v1_path=args.applied_v1,
            db_dsn=args.db_dsn,
            backend=args.backend,
            base_url=args.base_url,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout_seconds=args.timeout_seconds,
            strict_json_retries=args.strict_json_retries,
        )
    else:
        report = run_v2_1_repair(
            generated_input=args.generated_input,
            v2_rewrite_jsonl=args.v2_rewrite_jsonl,
            applied_v2_path=args.applied_v2,
            target_query_ids=args.target_query_ids,
            db_dsn=args.db_dsn,
            backend=args.backend,
            base_url=args.base_url,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout_seconds=args.timeout_seconds,
            strict_json_retries=args.strict_json_retries,
        )
    print(
        json.dumps(
            {
                "status": report["status"],
                "generated_answer_rows": report["generated_answer_rows"],
                "comparison": report["comparison"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
