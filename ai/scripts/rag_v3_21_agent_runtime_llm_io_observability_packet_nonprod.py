from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import rag_v3_20_live_runtime_like_db_index_cache_smoke_nonprod as v320
from rag_local_llm_expected_answer_generation_v1 import (  # noqa: E402
    DEFAULT_BACKEND,
    DEFAULT_MODEL,
    call_local_llm,
    local_llm_entry_blockers,
    resolve_base_url,
)

ROOT = v320.ROOT
REPORT_DIR = v320.REPORT_DIR
STATUS_JSONL = v320.STATUS_JSONL
PROGRESS_DOC = v320.PROGRESS_DOC
MEASUREMENTS_DOC = v320.MEASUREMENTS_DOC
TRIAGE_DOC = v320.TRIAGE_DOC

if str(ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai"))

from eval.harness import rag_diagnostic_common as diagnostic_common  # noqa: E402

from app.capabilities.rag_orchestrator.agent_runtime import (  # noqa: E402
    AgentRuntime,
    AgentRuntimeRequest,
    RUNTIME_CONTRACT_GUARDS,
)
from app.capabilities.rag_orchestrator.runtime_adapters import (  # noqa: E402
    InMemoryRuntimeCacheAdapter,
    InMemorySearchIndexAdapter,
    InMemorySourceAtomStoreAdapter,
    cache_key_for_query,
)
from app.capabilities.rag_orchestrator.tool_registry import (  # noqa: E402
    LAYER_NAMES,
    build_default_tool_registry,
)


RUN_ID = "official_answer_citation_agentic_loop_run_v3_21_agent_runtime_llm_io_observability_packet_nonprod"
EVENT_TYPE = "diagnostic_v3_21_agent_runtime_llm_io_observability_packet_nonprod"
STATUS = "DIAGNOSTIC_V3_21_AGENT_RUNTIME_LLM_IO_OBSERVABILITY_PACKET_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
RUNTIME_LAYER_NAMES = LAYER_NAMES
ADAPTER_NAMESPACE = "rag-data-llm-io-observability-nonprod"
DIAGNOSTIC_TENANT_ID = v320.DIAGNOSTIC_TENANT_ID
CACHE_NAMESPACE = "rag-v3-21-llm-io-cache"
PROMPT_TEMPLATE_VERSION = "rag_agent_runtime_llm_io_packet_prompt_v1"
PROMPT_TEMPLATE = """You are a non-production diagnostic RAG answer generator.
Answer in Korean using only the provided SourceAtom/EvidenceBundle evidence.
Return exactly one JSON object with keys:
- final_answer: concise user-visible answer
- citation_or_provenance_summary: short provenance summary using only the provided evidence ids

Do not use hidden target, gold, expected answer, supporting evidence, vector payload, raw files, or local file paths.

User query:
{query}

Evidence:
{evidence}
"""

OUTPUTS = {
    "summary_json": OUTPUT_DIR / "summary.json",
    "metrics_json": OUTPUT_DIR / "metrics.json",
    "per_query_jsonl": OUTPUT_DIR / "per_query.jsonl",
    "agent_tool_call_trace_jsonl": OUTPUT_DIR / "agent_tool_call_trace.jsonl",
    "route_policy_audit_jsonl": OUTPUT_DIR / "route_policy_audit.jsonl",
    "runtime_contract_audit_jsonl": OUTPUT_DIR / "runtime_contract_audit.jsonl",
    "user_response_policy_audit_jsonl": OUTPUT_DIR / "user_response_policy_audit.jsonl",
    "db_contract_audit_jsonl": OUTPUT_DIR / "db_contract_audit.jsonl",
    "index_contract_audit_jsonl": OUTPUT_DIR / "index_contract_audit.jsonl",
    "cache_contract_audit_jsonl": OUTPUT_DIR / "cache_contract_audit.jsonl",
    "live_runtime_smoke_audit_jsonl": OUTPUT_DIR / "live_runtime_smoke_audit.jsonl",
    "llm_io_packet_jsonl": OUTPUT_DIR / "llm_io_packet.jsonl",
    "llm_io_packet_csv": OUTPUT_DIR / "llm_io_packet.csv",
    "llm_invocation_audit_jsonl": OUTPUT_DIR / "llm_invocation_audit.jsonl",
    "local_llm_readiness_json": OUTPUT_DIR / "local_llm_readiness.json",
    "prompt_manifest_json": OUTPUT_DIR / "prompt_manifest.json",
    "guardrail_audit_json": OUTPUT_DIR / "guardrail_audit.json",
    "leakage_audit_jsonl": OUTPUT_DIR / "leakage_audit.jsonl",
    "review_packet_jsonl": OUTPUT_DIR / "review_packet.jsonl",
    "review_packet_csv": OUTPUT_DIR / "review_packet.csv",
}

USER_REVIEW_FIELDS = (
    "user_review_like",
    "user_review_note",
    "user_expected_answer_decision",
    "user_supporting_evidence_decision",
    "user_relevance_decision",
    "user_answerability_decision",
)

REVIEW_COLUMNS = (
    "review_id",
    "query_id",
    "diagnostic_case_id",
    "live_runtime_smoke_case",
    "bucket",
    "source_family",
    "actual_input_query",
    "agent_route",
    "route_lane",
    "response_policy_bucket",
    "answer_allowed_by_policy",
    "abstained",
    "llm_invoked",
    "raw_llm_response",
    "parsed_final_answer",
    "final_user_visible_answer",
    "sanitized_evidence_preview",
    "prompt_sha256",
    "llm_backend",
    "llm_model_label",
    "llm_unavailable_reason",
    "db_contract_status",
    "index_contract_status",
    "cache_contract_status",
    "cache_hit",
    "cache_key_namespace",
    "adapter_fail_closed_reason",
    "runtime_adapter_trace_path",
    "tool_call_trace_path",
    "evidence_truth_source",
    "selected_source_atom_ids",
    "evidence_bundle_ids",
    "vector_payload_candidate_only",
    "production_write_attempted",
    "broad_scan_attempted",
    "runtime_contract_violation",
    "official_metric_candidate",
    "promotion_evidence",
    *USER_REVIEW_FIELDS,
)
LOCAL_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"']+|\\\\[^\\\s]+\\[^\s\"']+")


def clean(value: Any) -> str:
    return diagnostic_common.clean(value)


def repo_relative(path: Path) -> str:
    return diagnostic_common.repo_relative(path, root=ROOT)


def utc_now() -> str:
    return diagnostic_common.utc_now()


def sha256_file(path: Path) -> str:
    return diagnostic_common.sha256_file(path)


def sha256_text(value: str) -> str:
    return diagnostic_common.sha256_text(value)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return diagnostic_common.read_jsonl(path)


def artifact_exists(path: Path) -> bool:
    return diagnostic_common.artifact_exists(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    diagnostic_common.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    diagnostic_common.write_jsonl(path, rows)


def build_input_paths() -> dict[str, Path]:
    return {
        "v3_20_summary_json": v320.OUTPUT_DIR / "summary.json",
        "v3_20_metrics_json": v320.OUTPUT_DIR / "metrics.json",
        "v3_20_per_query_jsonl": v320.OUTPUT_DIR / "per_query.jsonl",
        "v3_20_agent_tool_call_trace_jsonl": v320.OUTPUT_DIR / "agent_tool_call_trace.jsonl",
        "v3_20_route_policy_audit_jsonl": v320.OUTPUT_DIR / "route_policy_audit.jsonl",
        "v3_20_runtime_contract_audit_jsonl": v320.OUTPUT_DIR / "runtime_contract_audit.jsonl",
        "v3_20_user_response_policy_audit_jsonl": v320.OUTPUT_DIR / "user_response_policy_audit.jsonl",
        "v3_20_db_contract_audit_jsonl": v320.OUTPUT_DIR / "db_contract_audit.jsonl",
        "v3_20_index_contract_audit_jsonl": v320.OUTPUT_DIR / "index_contract_audit.jsonl",
        "v3_20_cache_contract_audit_jsonl": v320.OUTPUT_DIR / "cache_contract_audit.jsonl",
        "v3_20_live_runtime_smoke_audit_jsonl": v320.OUTPUT_DIR / "live_runtime_smoke_audit.jsonl",
        "v3_20_guardrail_audit_json": v320.OUTPUT_DIR / "guardrail_audit.json",
        "v3_20_review_packet_jsonl": v320.OUTPUT_DIR / "review_packet.jsonl",
    }


def require_input_artifacts(paths: Mapping[str, Path]) -> None:
    missing = [repo_relative(path) for path in paths.values() if not artifact_exists(path)]
    if missing:
        raise FileNotFoundError("missing required v3_20 input artifacts: " + ", ".join(missing))


def build_input_lineage(paths: Mapping[str, Path]) -> dict[str, Any]:
    return {
        key: {"exists": artifact_exists(path), "path": repo_relative(path), "sha256": sha256_file(path) if artifact_exists(path) else ""}
        for key, path in paths.items()
    }


def guardrail_flags() -> dict[str, Any]:
    flags = dict(v320.guardrail_flags())
    flags.update(
        {
            "llm_io_observability_packet": True,
            "actual_llm_responses_are_required_when_llm_invoked": True,
            "noop_or_extractive_generator_used": False,
            "noop_or_extractive_substitute_accepted_as_raw_llm_response": False,
            "prompt_preview_sanitized": True,
            "evidence_preview_source": "source_atom_evidence_bundle",
            "local_absolute_paths_exposed": False,
        }
    )
    return flags


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for index, original in enumerate(v320.build_cases(), start=1):
        case = dict(original)
        for key in ("query_id", "diagnostic_case_id", "review_id"):
            value = clean(case.get(key))
            case[key] = value.replace("v3_20", "v3_21") if value else f"v3_21_{index:03d}"
        case["review_id"] = f"v3_21_{index:03d}"
        case["cache_namespace"] = CACHE_NAMESPACE if clean(case.get("cache_namespace")) == v320.CACHE_NAMESPACE else case.get("cache_namespace")
        if clean(case.get("expected_cache_namespace")) == v320.CACHE_NAMESPACE:
            case["expected_cache_namespace"] = CACHE_NAMESPACE
        return_case = dict(case)
        cases.append(return_case)
    return cases


def cache_items_for_cases(cases: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not case.get("cache_hit"):
            continue
        namespace = clean(case.get("cache_namespace")) or CACHE_NAMESPACE
        key = cache_key_for_query(run_id=RUN_ID, query_id=clean(case.get("query_id")), namespace=namespace)
        items[key] = {"source_atom_ids": ["atom-pdf-p3"], "evidence_bundle_ids": ["bundle:atom-pdf-p3"]}
    return items


def build_runtime_for_case(case: Mapping[str, Any], cache_items: Mapping[str, Mapping[str, Any]]) -> AgentRuntime:
    return AgentRuntime(
        registry=build_default_tool_registry(),
        search_index=InMemorySearchIndexAdapter(
            search_views=v320.search_views(),
            namespace=ADAPTER_NAMESPACE,
            available=case.get("index_available", True) is not False,
        ),
        source_atom_store=InMemorySourceAtomStoreAdapter(
            source_atoms=v320.source_atoms(),
            namespace=ADAPTER_NAMESPACE,
            available=case.get("db_available", True) is not False,
        ),
        runtime_cache=InMemoryRuntimeCacheAdapter(
            namespace=clean(case.get("cache_namespace")) or CACHE_NAMESPACE,
            cache_items=cache_items,
            available=case.get("cache_available", True) is not False,
        ),
    )


def base_request_context(case: Mapping[str, Any]) -> dict[str, Any]:
    context = {
        "diagnostic_tenant_id": DIAGNOSTIC_TENANT_ID,
        "namespace": ADAPTER_NAMESPACE,
        "cache_namespace": clean(case.get("cache_namespace")) or CACHE_NAMESPACE,
        "expected_cache_namespace": clean(case.get("expected_cache_namespace")) or clean(case.get("cache_namespace")) or CACHE_NAMESPACE,
    }
    context.update(v320.v319.v317.as_mapping(case.get("request_context")))
    return context


def selected_evidence_preview(source_atom_ids: Sequence[str], *, max_chars: int = 700) -> str:
    atoms = v320.source_atoms()
    snippets: list[str] = []
    for atom_id in source_atom_ids:
        atom = atoms.get(clean(atom_id), {})
        if not atom:
            continue
        family = clean(atom.get("source_family"))
        identity = clean(atom.get("source_identity"))
        text = clean(atom.get("normalized_text_or_value_snapshot"))
        citation = atom.get("canonical_citation_payload") if isinstance(atom.get("canonical_citation_payload"), Mapping) else {}
        locator = ", ".join(f"{key}={clean(value)}" for key, value in citation.items() if clean(value))
        snippets.append(f"{family} {identity} ({locator}): {text}")
    return sanitize_preview("\n".join(snippets), max_chars=max_chars)


def citation_summary(source_atom_ids: Sequence[str], evidence_bundle_ids: Sequence[str]) -> str:
    if not source_atom_ids:
        return ""
    return (
        "SourceAtom ids="
        + "|".join(clean(value) for value in source_atom_ids)
        + "; EvidenceBundle ids="
        + "|".join(clean(value) for value in evidence_bundle_ids)
    )


def sanitize_preview(value: Any, *, max_chars: int = 420) -> str:
    text = clean(value)
    if not text:
        return ""
    text = text.replace(str(ROOT), "[REPO_ROOT]").replace(ROOT.as_posix(), "[REPO_ROOT]")
    text = LOCAL_PATH_RE.sub("[LOCAL_PATH]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def build_prompt(*, query: str, evidence_preview: str) -> str:
    return PROMPT_TEMPLATE.format(query=clean(query), evidence=clean(evidence_preview))


def parse_llm_json(raw: str) -> tuple[str, str, str]:
    text = clean(raw)
    if not text:
        return "", "", "LOCAL_LLM_EMPTY_RESPONSE_FAIL_CLOSED"
    if text.startswith("```"):
        return "", "", "LOCAL_LLM_MALFORMED_RESPONSE_FAIL_CLOSED"
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return "", "", "LOCAL_LLM_MALFORMED_RESPONSE_FAIL_CLOSED"
    if not isinstance(payload, Mapping):
        return "", "", "LOCAL_LLM_MALFORMED_RESPONSE_FAIL_CLOSED"
    final_answer = clean(payload.get("final_answer"))
    provenance = clean(payload.get("citation_or_provenance_summary"))
    if not final_answer:
        return "", provenance, "LOCAL_LLM_EMPTY_FINAL_ANSWER_FAIL_CLOSED"
    return final_answer, provenance, ""


def leakage_flags(row: Mapping[str, Any]) -> dict[str, bool]:
    packet_text = json.dumps(row, ensure_ascii=False)
    prompt_text = clean(row.get("sanitized_prompt_preview"))
    response_text = clean(row.get("raw_llm_response")) + " " + clean(row.get("parsed_final_answer"))
    forbidden_terms = ("expected_answer", "supporting_evidence", "target_locator", "gold_locator")
    return {
        "prompt_leakage": any(term in prompt_text for term in forbidden_terms),
        "response_leakage": any(term in response_text for term in forbidden_terms),
        "path_leakage": bool(LOCAL_PATH_RE.search(packet_text)) or str(ROOT) in packet_text or ROOT.as_posix() in packet_text,
        "evidence_truth_violation": clean(row.get("evidence_truth_source")) not in {"source_atom_evidence_bundle", "none"},
        "vector_payload_evidence_truth_violation": clean(row.get("evidence_truth_source")).lower().startswith("vector"),
    }


def build_readiness(
    *,
    backend: str,
    base_url: str,
    model: str,
    blockers: Sequence[str],
    llm_client_provided: bool,
) -> dict[str, Any]:
    available = llm_client_provided or not blockers
    return {
        "schema_version": f"{RUN_ID}_local_llm_readiness_v1",
        "run_id": RUN_ID,
        "status": "LOCAL_LLM_AVAILABLE_DIAGNOSTIC_ONLY" if available else "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED",
        "generated_at": utc_now(),
        "local_llm_available": available,
        "backend": clean(backend),
        "base_url": sanitize_preview(base_url, max_chars=200),
        "model": clean(model),
        "blockers": list(blockers),
        "llm_client_provided_for_test": bool(llm_client_provided),
        "localhost_only": True,
        "noop_or_extractive_generator_used": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }


def build_prompt_manifest(*, backend: str, base_url: str, model: str) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_prompt_manifest_v1",
        "run_id": RUN_ID,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "prompt_sha256": sha256_text(PROMPT_TEMPLATE),
        "backend": clean(backend),
        "base_url": sanitize_preview(base_url, max_chars=200),
        "model": clean(model),
        "requires_korean_answer": True,
        "requires_supplied_evidence_only": True,
        "requires_strict_json_object": True,
        "uses_expected_or_supporting_gold_text": False,
        "uses_raw_file_query_time_access": False,
        "uses_target_or_gold_locator_text": False,
        "uses_vector_payload_as_evidence": False,
        "source_atom_evidence_bundle_truth_only": True,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }


def build_live_audit_row(result: Any) -> dict[str, Any]:
    row = v320.build_live_audit_row(result)
    row["schema_version"] = f"{RUN_ID}_live_runtime_smoke_audit_v1"
    row["input_schema_version"] = "rag_v3_21_live_runtime_smoke_input_v1"
    row["output_schema_version"] = "rag_v3_21_live_runtime_smoke_output_v1"
    row["diagnostic_tenant_id"] = DIAGNOSTIC_TENANT_ID
    row["tenant_id"] = DIAGNOSTIC_TENANT_ID
    row["namespace"] = ADAPTER_NAMESPACE
    return row


def invoke_llm(
    *,
    prompt: str,
    query_id: str,
    backend: str,
    base_url: str,
    model: str,
    max_tokens: int,
    timeout_seconds: int,
    llm_client: Callable[..., str] | None,
) -> tuple[str, int, float, str]:
    request_id = f"{RUN_ID}:{query_id}"
    start = time.perf_counter()
    if llm_client is not None:
        raw = llm_client(
            prompt,
            query_id=query_id,
            backend=backend,
            base_url=base_url,
            model=model,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )
    else:
        raw = call_local_llm(
            backend=backend,
            base_url=base_url,
            model=model,
            prompt=prompt,
            temperature=0.0,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )
    elapsed_ms = round((time.perf_counter() - start) * 1000.0, 3)
    return clean(raw), len(clean(raw)), elapsed_ms, request_id


def build_rows(
    *,
    backend: str,
    base_url: str,
    model: str,
    readiness: Mapping[str, Any],
    max_tokens: int,
    timeout_seconds: int,
    llm_client: Callable[..., str] | None,
) -> dict[str, list[dict[str, Any]]]:
    cases = build_cases()
    cache_items = cache_items_for_cases(cases)
    per_query_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    route_policy_rows: list[dict[str, Any]] = []
    runtime_audit_rows: list[dict[str, Any]] = []
    user_response_policy_rows: list[dict[str, Any]] = []
    db_rows: list[dict[str, Any]] = []
    index_rows: list[dict[str, Any]] = []
    cache_rows: list[dict[str, Any]] = []
    live_rows: list[dict[str, Any]] = []
    llm_rows: list[dict[str, Any]] = []
    llm_audit_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    leakage_rows: list[dict[str, Any]] = []
    local_llm_available = bool(readiness.get("local_llm_available"))
    unavailable_reason = "; ".join(clean(value) for value in readiness.get("blockers", []) if clean(value))
    for case in cases:
        runtime = build_runtime_for_case(case, cache_items)
        context = base_request_context(case)
        result = runtime.invoke(
            AgentRuntimeRequest(
                run_id=RUN_ID,
                query_id=clean(case.get("query_id")),
                diagnostic_case_id=clean(case.get("diagnostic_case_id")),
                query_text=clean(case.get("query")),
                source_family=clean(case.get("source_family")),
                source_registry={},
                candidate_source_atom_ids=tuple(case.get("candidate_source_atom_ids") or ()),
                rough_query_hint=bool(case.get("rough_query_hint")),
                request_context=context,
                runtime_flags=v320.v319.v317.as_mapping(case.get("runtime_flags")),
                internal_replay_adapter=True,
            )
        )
        trace_rows.extend(result.trace_rows)
        adapter_rows = list(result.runtime_adapter_trace_rows)
        db_rows.extend(row for row in adapter_rows if row["adapter_name"] == "InMemorySourceAtomStoreAdapter")
        index_rows.extend(row for row in adapter_rows if row["adapter_name"] == "InMemorySearchIndexAdapter")
        cache_rows.extend(row for row in adapter_rows if row["adapter_name"] == "InMemoryRuntimeCacheAdapter")
        live_row = build_live_audit_row(result)
        live_rows.append(live_row)
        selected_ids = list(result.selected_source_atom_ids)
        evidence_bundle_ids = list(result.evidence_bundle_ids)
        evidence_preview = selected_evidence_preview(selected_ids)
        prompt = build_prompt(query=clean(case.get("query")), evidence_preview=evidence_preview) if result.answer_allowed_by_policy else ""
        prompt_sha = sha256_text(prompt) if prompt else ""
        active_context = bool(context.get("active_source_atom_ids"))
        llm_invoked = False
        raw_response = ""
        raw_response_sha = ""
        parsed_answer = ""
        provenance = citation_summary(selected_ids, evidence_bundle_ids)
        blocked_reason = clean(result.fail_closed_reason or result.blocked_reason)
        llm_latency_ms = 0.0
        llm_request_id = ""
        llm_unavailable_reason = ""
        llm_parse_error = ""
        if result.answer_allowed_by_policy:
            if not local_llm_available:
                blocked_reason = "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"
                llm_unavailable_reason = unavailable_reason or "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"
            else:
                llm_invoked = True
                try:
                    raw_response, _raw_len, llm_latency_ms, llm_request_id = invoke_llm(
                        prompt=prompt,
                        query_id=result.query_id,
                        backend=backend,
                        base_url=base_url,
                        model=model,
                        max_tokens=max_tokens,
                        timeout_seconds=timeout_seconds,
                        llm_client=llm_client,
                    )
                except Exception as exc:
                    raw_response = ""
                    blocked_reason = "LOCAL_LLM_INVOCATION_FAILED_FAIL_CLOSED"
                    llm_unavailable_reason = f"{type(exc).__name__}: {exc}"
                if raw_response:
                    raw_response_sha = sha256_text(raw_response)
                    parsed_answer, parsed_provenance, llm_parse_error = parse_llm_json(raw_response)
                    provenance = parsed_provenance or provenance
                    if llm_parse_error:
                        blocked_reason = llm_parse_error
                elif llm_invoked and not llm_unavailable_reason:
                    blocked_reason = "LOCAL_LLM_EMPTY_RESPONSE_FAIL_CLOSED"
                    llm_parse_error = blocked_reason
        elif not blocked_reason:
            blocked_reason = "ANSWER_NOT_ALLOWED_BY_POLICY"
        final_user_visible_answer = parsed_answer
        if result.answer_allowed_by_policy and not parsed_answer:
            final_user_visible_answer = blocked_reason or "LOCAL_LLM_RESPONSE_FAIL_CLOSED"
        elif not result.answer_allowed_by_policy:
            final_user_visible_answer = result.final_answer
        packet_row = {
            "schema_version": f"{RUN_ID}_llm_io_packet_v1",
            "run_id": RUN_ID,
            "query_id": result.query_id,
            "diagnostic_case_id": result.diagnostic_case_id,
            "source_family": clean(case.get("source_family")),
            "route_lane": result.route_lane,
            "live_runtime_smoke_case": clean(case.get("live_runtime_smoke_case")),
            "actual_input_query": clean(case.get("query")),
            "active_context_present": active_context,
            "response_policy_bucket": result.response_policy_bucket,
            "answer_allowed_by_policy": result.answer_allowed_by_policy,
            "abstained": result.abstained,
            "llm_invoked": llm_invoked,
            "llm_backend": clean(backend),
            "llm_model_label": clean(model),
            "llm_request_id": llm_request_id,
            "llm_latency_ms": llm_latency_ms,
            "prompt_template_version": PROMPT_TEMPLATE_VERSION if prompt else "",
            "prompt_sha256": prompt_sha,
            "sanitized_prompt_preview": sanitize_preview(prompt),
            "evidence_truth_source": result.evidence_truth_source,
            "selected_source_atom_ids": selected_ids,
            "evidence_bundle_ids": evidence_bundle_ids,
            "sanitized_evidence_preview": evidence_preview,
            "raw_llm_response": raw_response,
            "raw_llm_response_sha256": raw_response_sha,
            "parsed_final_answer": parsed_answer,
            "final_user_visible_answer": final_user_visible_answer,
            "citation_or_provenance_summary": provenance,
            "blocked_reason": blocked_reason,
            "llm_unavailable_reason": llm_unavailable_reason,
            "llm_parse_error": llm_parse_error,
            "runtime_contract_violation": result.runtime_contract_violation,
            "official_metric_candidate": False,
            "promotion_evidence": False,
            "vector_payload_candidate_only": True,
        }
        leaks = leakage_flags(packet_row)
        packet_row.update(leaks)
        llm_rows.append(packet_row)
        if llm_invoked:
            llm_audit_rows.append(
                {
                    "schema_version": f"{RUN_ID}_llm_invocation_audit_v1",
                    "run_id": RUN_ID,
                    "query_id": result.query_id,
                    "diagnostic_case_id": result.diagnostic_case_id,
                    "route_lane": result.route_lane,
                    "live_runtime_smoke_case": clean(case.get("live_runtime_smoke_case")),
                    "llm_backend": clean(backend),
                    "llm_model_label": clean(model),
                    "llm_request_id": llm_request_id,
                    "llm_invoked": True,
                    "answer_allowed_by_policy": result.answer_allowed_by_policy,
                    "prompt_template_version": PROMPT_TEMPLATE_VERSION,
                    "prompt_sha256": prompt_sha,
                    "raw_llm_response_present": bool(raw_response),
                    "raw_llm_response_sha256": raw_response_sha,
                    "parsed_final_answer_present": bool(parsed_answer),
                    "fail_closed": bool(blocked_reason and not parsed_answer),
                    "fail_closed_reason": blocked_reason if not parsed_answer else "",
                    "latency_ms": llm_latency_ms,
                    "timeout_ms": timeout_seconds * 1000,
                    "selected_source_atom_ids": selected_ids,
                    "evidence_bundle_ids": evidence_bundle_ids,
                    "evidence_truth_source": result.evidence_truth_source,
                    "official_metric_candidate": False,
                    "promotion_evidence": False,
                }
            )
        common = {
            "schema_version": f"{RUN_ID}_per_query_v1",
            "run_id": RUN_ID,
            "review_id": clean(case.get("review_id")),
            "query_id": result.query_id,
            "diagnostic_case_id": result.diagnostic_case_id,
            "live_runtime_smoke_case": clean(case.get("live_runtime_smoke_case")),
            "bucket": clean(case.get("bucket")),
            "source_family": clean(case.get("source_family")),
            "actual_input_query_sha256": sha256_text(clean(case.get("query"))),
            "agent_route": result.agent_route,
            "route_lane": result.route_lane,
            "tool_call_sequence": result.tool_call_sequence,
            "tool_call_trace_path": repo_relative(OUTPUTS["agent_tool_call_trace_jsonl"]),
            "runtime_adapter_trace_path": repo_relative(OUTPUTS["live_runtime_smoke_audit_jsonl"]),
            "llm_io_packet_path": repo_relative(OUTPUTS["llm_io_packet_jsonl"]),
            "runtime_contract_violation": result.runtime_contract_violation,
            "blocked_reason": blocked_reason,
            "fail_closed_reason": result.fail_closed_reason,
            "adapter_fail_closed_reason": result.adapter_fail_closed_reason,
            "response_policy_bucket": result.response_policy_bucket,
            "answer_allowed_by_policy": result.answer_allowed_by_policy,
            "llm_invoked": llm_invoked,
            "db_contract_status": result.db_contract_status,
            "index_contract_status": result.index_contract_status,
            "cache_contract_status": result.cache_contract_status,
            "cache_hit": result.cache_hit,
            "cache_key_namespace": result.cache_key_namespace,
            "evidence_truth_source": result.evidence_truth_source,
            "selected_source_atom_ids": selected_ids,
            "selected_source_atom_count": len(selected_ids),
            "evidence_bundle_ids": evidence_bundle_ids,
            "vector_payload_candidate_only": True,
            "production_write_attempted": False,
            "broad_scan_attempted": False,
            "abstained": result.abstained,
            "official_metric_input_rows": 0,
            "official_metric_candidate": False,
            "promotion_evidence": False,
            **guardrail_flags(),
        }
        per_query_rows.append(common)
        route_policy_rows.append(
            {
                "schema_version": f"{RUN_ID}_route_policy_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "route_lane": result.route_lane,
                "agent_route": result.agent_route,
                "response_policy_bucket": result.response_policy_bucket,
                "allow_unbounded_fallback": False,
                "selected_tool_ids": result.tool_call_sequence,
                "fail_closed_reason": result.fail_closed_reason,
                "llm_invoked": llm_invoked,
                "official_metric_input_rows": 0,
                "diagnostic_only": True,
            }
        )
        runtime_audit_rows.append(
            {
                "schema_version": f"{RUN_ID}_runtime_contract_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "runtime_contract_violation": result.runtime_contract_violation,
                "runtime_contract_guards": list(RUNTIME_CONTRACT_GUARDS),
                "violated_guard": result.fail_closed_reason if result.runtime_contract_violation else "",
                "raw_file_query_time_accessed": False,
                "full_workbook_sheet_scan": False,
                "full_pdf_page_block_scan": False,
                "broad_source_atom_scan": False,
                "vector_payload_used_as_evidence_truth": False,
                "target_locator_used": False,
                "gold_locator_used": False,
                "expected_supporting_text_used": False,
                "direct_normalized_value_query_matching_used": False,
                "unbounded_fallback": False,
                "production_write_allowed": False,
                "llm_invoked_after_l7_answer_ready": bool(llm_invoked and result.answer_allowed_by_policy),
                "official_metric_input_rows": 0,
            }
        )
        user_response_policy_rows.append(
            {
                "schema_version": f"{RUN_ID}_user_response_policy_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "agent_route": result.agent_route,
                "route_lane": result.route_lane,
                "response_policy_bucket": result.response_policy_bucket,
                "answer_allowed_by_policy": result.answer_allowed_by_policy,
                "abstained": result.abstained,
                "blocked_reason": blocked_reason,
                "fail_closed_reason": result.fail_closed_reason,
                "llm_invoked": llm_invoked,
                "evidence_truth_source": result.evidence_truth_source,
                "selected_source_atom_count": len(selected_ids),
                "runtime_contract_violation": result.runtime_contract_violation,
                "official_metric_input_rows": 0,
                "diagnostic_only": True,
            }
        )
        review_rows.append(
            {
                "review_id": clean(case.get("review_id")),
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "live_runtime_smoke_case": clean(case.get("live_runtime_smoke_case")),
                "bucket": clean(case.get("bucket")),
                "source_family": clean(case.get("source_family")),
                "actual_input_query": clean(case.get("query")),
                "agent_route": result.agent_route,
                "route_lane": result.route_lane,
                "response_policy_bucket": result.response_policy_bucket,
                "answer_allowed_by_policy": result.answer_allowed_by_policy,
                "abstained": result.abstained,
                "llm_invoked": llm_invoked,
                "raw_llm_response": raw_response,
                "parsed_final_answer": parsed_answer,
                "final_user_visible_answer": final_user_visible_answer,
                "sanitized_evidence_preview": evidence_preview,
                "prompt_sha256": prompt_sha,
                "llm_backend": clean(backend),
                "llm_model_label": clean(model),
                "llm_unavailable_reason": llm_unavailable_reason,
                "db_contract_status": result.db_contract_status,
                "index_contract_status": result.index_contract_status,
                "cache_contract_status": result.cache_contract_status,
                "cache_hit": result.cache_hit,
                "cache_key_namespace": result.cache_key_namespace,
                "adapter_fail_closed_reason": result.adapter_fail_closed_reason,
                "runtime_adapter_trace_path": repo_relative(OUTPUTS["live_runtime_smoke_audit_jsonl"]),
                "tool_call_trace_path": repo_relative(OUTPUTS["agent_tool_call_trace_jsonl"]),
                "evidence_truth_source": result.evidence_truth_source,
                "selected_source_atom_ids": "|".join(selected_ids),
                "evidence_bundle_ids": "|".join(evidence_bundle_ids),
                "vector_payload_candidate_only": True,
                "production_write_attempted": False,
                "broad_scan_attempted": False,
                "runtime_contract_violation": result.runtime_contract_violation,
                "official_metric_candidate": False,
                "promotion_evidence": False,
                **{field: "" for field in USER_REVIEW_FIELDS},
            }
        )
        leakage_rows.append(
            {
                "schema_version": f"{RUN_ID}_leakage_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "leakage_detected": any(leaks.values()),
                "leakage_fields": [key for key, value in leaks.items() if value],
                "prompt_leakage": leaks["prompt_leakage"],
                "response_leakage": leaks["response_leakage"],
                "path_leakage": leaks["path_leakage"],
                "official_metric_input_rows": 0,
                "diagnostic_only": True,
                "target_locator_used": False,
                "gold_locator_used": False,
                "expected_supporting_text_used": False,
                "source_atom_registry_canonical_truth": True,
                "source_atom_store_canonical_truth": True,
                "vector_payload_used_as_evidence_truth": False,
            }
        )
    return {
        "per_query_rows": per_query_rows,
        "agent_tool_call_trace_rows": trace_rows,
        "route_policy_audit_rows": route_policy_rows,
        "runtime_contract_audit_rows": runtime_audit_rows,
        "user_response_policy_audit_rows": user_response_policy_rows,
        "db_contract_audit_rows": db_rows,
        "index_contract_audit_rows": index_rows,
        "cache_contract_audit_rows": cache_rows,
        "live_runtime_smoke_audit_rows": live_rows,
        "llm_io_packet_rows": llm_rows,
        "llm_invocation_audit_rows": llm_audit_rows,
        "review_rows": review_rows,
        "leakage_audit_rows": leakage_rows,
    }


def build_metrics(rows: Mapping[str, Sequence[Mapping[str, Any]]], readiness: Mapping[str, Any]) -> dict[str, Any]:
    per_query = list(rows["per_query_rows"])
    llm_rows = list(rows["llm_io_packet_rows"])
    db_rows = list(rows["db_contract_audit_rows"])
    index_rows = list(rows["index_contract_audit_rows"])
    cache_rows = list(rows["cache_contract_audit_rows"])
    route_counts = Counter(clean(row.get("route_lane")) for row in per_query)
    response_counts = Counter(clean(row.get("response_policy_bucket")) for row in per_query)
    local_unavailable_allowed_rows = [
        row for row in llm_rows if row["answer_allowed_by_policy"] and row["blocked_reason"] == "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"
    ]
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "live_runtime_smoke_row_count": len(per_query),
        "llm_io_packet_row_count": len(llm_rows),
        "llm_invocation_audit_row_count": len(rows["llm_invocation_audit_rows"]),
        "review_packet_row_count": len(rows["review_rows"]),
        "per_query_row_count": len(per_query),
        "agent_tool_call_trace_row_count": len(rows["agent_tool_call_trace_rows"]),
        "route_policy_audit_row_count": len(rows["route_policy_audit_rows"]),
        "runtime_contract_audit_row_count": len(rows["runtime_contract_audit_rows"]),
        "user_response_policy_audit_row_count": len(rows["user_response_policy_audit_rows"]),
        "db_contract_audit_row_count": len(db_rows),
        "index_contract_audit_row_count": len(index_rows),
        "cache_contract_audit_row_count": len(cache_rows),
        "route_lane_counts": dict(sorted(route_counts.items())),
        "response_policy_bucket_counts": dict(sorted(response_counts.items())),
        "llm_invoked_count": sum(1 for row in llm_rows if row["llm_invoked"]),
        "raw_llm_response_present_count": sum(1 for row in llm_rows if clean(row.get("raw_llm_response"))),
        "parsed_final_answer_present_count": sum(1 for row in llm_rows if clean(row.get("parsed_final_answer"))),
        "fail_closed_no_llm_invocation_count": sum(1 for row in llm_rows if row["abstained"] and not row["llm_invoked"]),
        "local_llm_unavailable_fail_closed_count": len(local_unavailable_allowed_rows),
        "prompt_leakage_flag_count": sum(1 for row in llm_rows if row["prompt_leakage"]),
        "response_leakage_flag_count": sum(1 for row in llm_rows if row["response_leakage"]),
        "path_leakage_flag_count": sum(1 for row in llm_rows if row["path_leakage"]),
        "evidence_truth_violation_count": sum(1 for row in llm_rows if row["evidence_truth_violation"]),
        "vector_payload_evidence_truth_violation_count": sum(
            1 for row in [*llm_rows, *db_rows, *index_rows, *cache_rows] if row.get("vector_payload_evidence_truth_violation") or row.get("vector_payload_used_as_evidence_truth")
        ),
        "noop_or_extractive_substitute_response_count": 0,
        "db_available_count": sum(1 for row in db_rows if row["status"] == "available"),
        "db_unavailable_fail_closed_count": sum(
            1 for row in per_query if row["db_contract_status"] == "unavailable" and row["fail_closed_reason"] == "SOURCE_ATOM_STORE_UNAVAILABLE"
        ),
        "index_available_count": sum(1 for row in index_rows if row["status"] == "available"),
        "index_unavailable_fail_closed_count": sum(
            1 for row in per_query if row["index_contract_status"] == "unavailable" and row["fail_closed_reason"] == "INDEX_UNAVAILABLE"
        ),
        "cache_hit_count": sum(1 for row in per_query if row["cache_hit"]),
        "cache_miss_count": sum(1 for row in per_query if row["cache_contract_status"] == "miss"),
        "cache_unavailable_count": sum(1 for row in per_query if row["cache_contract_status"] == "unavailable"),
        "cache_namespace_mismatch_blocked_count": sum(1 for row in per_query if row["fail_closed_reason"] == "CACHE_NAMESPACE_MISMATCH"),
        "production_write_attempt_count": sum(1 for row in [*db_rows, *index_rows, *cache_rows] if row["production_write_attempted"]),
        "broad_source_atom_scan_attempt_count": sum(1 for row in [*db_rows, *index_rows, *cache_rows] if row["broad_scan_attempted"]),
        "raw_file_query_time_accessed": False,
        "runtime_contract_violation_count": sum(1 for row in per_query if row["runtime_contract_violation"]),
        "local_llm_available": bool(readiness.get("local_llm_available")),
        "official_metric_input_rows": 0,
        "official_metric": False,
        "promotion_evidence": False,
        "diagnostic_only": True,
        **guardrail_flags(),
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    input_lineage: Mapping[str, Any],
    artifact_sha256: Mapping[str, str],
    readiness: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_summary_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "event_type": EVENT_TYPE,
        "run_class": "diagnostic_only_agent_runtime_llm_io_observability_packet_nonprod",
        "generated_at": utc_now(),
        "review_packet_dir": repo_relative(OUTPUT_DIR),
        "tool_registry_version": "rag_tool_registry_l0_l8_v1",
        "route_policy_lanes": ["user_locator", "rough_query", "hybrid", "unsupported"],
        "runtime_layer_names": list(RUNTIME_LAYER_NAMES),
        "input_lineage": dict(input_lineage),
        "artifact_paths": {key: repo_relative(path) for key, path in OUTPUTS.items()},
        "artifact_sha256": dict(artifact_sha256),
        "local_llm_readiness": dict(readiness),
        **dict(metrics),
    }


def build_guardrail_audit(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "runtime_contract_violation_count": metrics["runtime_contract_violation_count"],
        "prompt_leakage_flag_count": metrics["prompt_leakage_flag_count"],
        "response_leakage_flag_count": metrics["response_leakage_flag_count"],
        "path_leakage_flag_count": metrics["path_leakage_flag_count"],
        "evidence_truth_violation_count": metrics["evidence_truth_violation_count"],
        "production_write_attempt_count": metrics["production_write_attempt_count"],
        "broad_source_atom_scan_attempt_count": metrics["broad_source_atom_scan_attempt_count"],
        "vector_payload_evidence_truth_violation_count": metrics["vector_payload_evidence_truth_violation_count"],
        **guardrail_flags(),
    }


def build_artifacts(
    *,
    backend: str = DEFAULT_BACKEND,
    base_url: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 420,
    timeout_seconds: int = 90,
    llm_client: Callable[..., str] | None = None,
) -> dict[str, Any]:
    input_paths = build_input_paths()
    require_input_artifacts(input_paths)
    input_lineage = build_input_lineage(input_paths)
    resolved_base_url = resolve_base_url(backend, base_url)
    blockers: list[str] = []
    if llm_client is None:
        blockers = local_llm_entry_blockers(
            backend=backend,
            base_url=resolved_base_url,
            model=model,
            check_endpoint=True,
            timeout_seconds=min(timeout_seconds, 10),
        )
    readiness = build_readiness(
        backend=backend,
        base_url=resolved_base_url,
        model=model,
        blockers=blockers,
        llm_client_provided=llm_client is not None,
    )
    rows = build_rows(
        backend=backend,
        base_url=resolved_base_url,
        model=model,
        readiness=readiness,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        llm_client=llm_client,
    )
    metrics = build_metrics(rows, readiness)
    prompt_manifest = build_prompt_manifest(backend=backend, base_url=resolved_base_url, model=model)
    guardrail = build_guardrail_audit(metrics)
    summary = build_summary(metrics=metrics, input_lineage=input_lineage, artifact_sha256={}, readiness=readiness)
    return {
        "summary": summary,
        "metrics": metrics,
        "prompt_manifest": prompt_manifest,
        "local_llm_readiness": readiness,
        "guardrail_audit": guardrail,
        **rows,
    }


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str] | None = None) -> None:
    diagnostic_common.write_csv(path, rows, columns)


def csv_value(value: Any) -> str:
    return diagnostic_common.csv_value(value)


def artifact_sha256_without_summary() -> dict[str, str]:
    return diagnostic_common.artifact_sha256_without_summary(OUTPUTS)


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    diagnostic_common.replace_marked_entry(path, marker, entry)


def update_docs(summary: Mapping[str, Any], metrics: Mapping[str, Any]) -> None:
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v320.v319.refresh_last_updated(doc_path)
    progress_entry = (
        f"- v3_21 agent-runtime LLM I/O observability packet (`{RUN_ID}`) is "
        "diagnostic_v3_21_agent_runtime_llm_io_observability_packet_nonprod_ready. It reuses the v3_20 "
        "non-production ToolRegistry-only agent runtime, SourceAtomStoreContract, SearchIndexContract, and "
        "RuntimeCacheContract smoke cases, then records user-observable actual input queries plus actual raw LLM "
        "responses only for rows that reached L7 answer-ready context and were allowed by response policy. "
        "Fail-closed rows do not invoke LLM. If the localhost local LLM backend is unavailable, answer-allowed rows "
        "fail closed with LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED and no fake raw response is emitted. SourceAtom/EvidenceBundle "
        "remains canonical evidence truth; SearchView/vector payload remains candidate-only. This is not production routing, "
        "not product success, not promotion evidence, not official scoring, and not live DB/index/cache readiness."
    )
    measurements_entry = f"""### v3_21 Agent Runtime LLM I/O Observability Packet

- Run: `{RUN_ID}`
- Policy: diagnostic-only, non-production LLM I/O observability; fail-closed rows do not invoke LLM, local LLM unavailable rows emit no fake raw response, and all raw I/O stays in ignored JSONL/CSV artifacts rather than status or Markdown.

| Diagnostic count | Value |
| --- | ---: |
| llm_io_packet_row_count | {metrics["llm_io_packet_row_count"]} |
| llm_invocation_audit_row_count | {metrics["llm_invocation_audit_row_count"]} |
| llm_invoked_count | {metrics["llm_invoked_count"]} |
| raw_llm_response_present_count | {metrics["raw_llm_response_present_count"]} |
| parsed_final_answer_present_count | {metrics["parsed_final_answer_present_count"]} |
| fail_closed_no_llm_invocation_count | {metrics["fail_closed_no_llm_invocation_count"]} |
| local_llm_unavailable_fail_closed_count | {metrics["local_llm_unavailable_fail_closed_count"]} |
| prompt_leakage_flag_count | {metrics["prompt_leakage_flag_count"]} |
| response_leakage_flag_count | {metrics["response_leakage_flag_count"]} |
| path_leakage_flag_count | {metrics["path_leakage_flag_count"]} |
| evidence_truth_violation_count | {metrics["evidence_truth_violation_count"]} |
| vector_payload_evidence_truth_violation_count | {metrics["vector_payload_evidence_truth_violation_count"]} |
| runtime_contract_violation_count | {metrics["runtime_contract_violation_count"]} |
| production_write_attempt_count | {metrics["production_write_attempt_count"]} |
| broad_source_atom_scan_attempt_count | {metrics["broad_source_atom_scan_attempt_count"]} |
| official_metric_input_rows | 0 |

Artifacts: `{summary["review_packet_dir"]}/summary.json`, `metrics.json`, `per_query.jsonl`, `agent_tool_call_trace.jsonl`, `route_policy_audit.jsonl`, `runtime_contract_audit.jsonl`, `user_response_policy_audit.jsonl`, `db_contract_audit.jsonl`, `index_contract_audit.jsonl`, `cache_contract_audit.jsonl`, `live_runtime_smoke_audit.jsonl`, `llm_io_packet.jsonl`, `llm_io_packet.csv`, `llm_invocation_audit.jsonl`, `local_llm_readiness.json`, `prompt_manifest.json`, `guardrail_audit.json`, `leakage_audit.jsonl`, `review_packet.jsonl`, and `review_packet.csv`.

Counter source-of-truth: `metrics.json` carries the LLM invocation, leakage, adapter, and guardrail counters; `status.jsonl` records only counts, paths, hashes, and policy flags, not raw prompts or raw responses.
"""
    triage_entry = (
        "### v3_21 Agent Runtime LLM I/O Observability Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        "- Scope: diagnostic-only non-production packet for actual input query and actual raw LLM response observability after L7 answer-ready context.\n"
        "- Fail-closed rows do not invoke LLM; unsupported, deictic-context-missing, index unavailable, DB unavailable, and stale cache namespace cases remain policy or adapter fail-closed.\n"
        "- LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED is recorded when the localhost local LLM backend is unavailable; no noop, deterministic extractive substitute, or smoke final_answer is emitted as raw_llm_response.\n"
        "- SourceAtom/EvidenceBundle remains evidence truth for prompt evidence previews and parsed final answers; SearchView/vector payload remains candidate-only.\n"
        "- User-owned review fields remain blank and non-scoring; official_metric_input_rows stays 0.\n"
        "- This is not production routing and not live DB/index/cache readiness.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        "Overall status: `diagnostic_v3_21_agent_runtime_llm_io_observability_packet_nonprod_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"current diagnostic (?:answer-quality|response-policy|live-runtime-like smoke) loop:\n`[^`]+`;",
        f"current diagnostic LLM I/O observability loop:\n`{RUN_ID}`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v320.v319.refresh_last_updated(doc_path)


def append_status_event(summary: Mapping[str, Any]) -> None:
    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": summary["status"],
        "generated_at": utc_now(),
        "review_packet_dir": summary["review_packet_dir"],
        "artifact_paths": summary["artifact_paths"],
        "artifact_sha256": {**summary["artifact_sha256"], "summary_json_sha256": sha256_file(OUTPUTS["summary_json"])},
        "tool_registry_version": summary["tool_registry_version"],
        "route_policy_lanes": summary["route_policy_lanes"],
        "llm_io_packet_row_count": summary["llm_io_packet_row_count"],
        "llm_invocation_audit_row_count": summary["llm_invocation_audit_row_count"],
        "llm_invoked_count": summary["llm_invoked_count"],
        "raw_llm_response_present_count": summary["raw_llm_response_present_count"],
        "parsed_final_answer_present_count": summary["parsed_final_answer_present_count"],
        "fail_closed_no_llm_invocation_count": summary["fail_closed_no_llm_invocation_count"],
        "local_llm_unavailable_fail_closed_count": summary["local_llm_unavailable_fail_closed_count"],
        "runtime_contract_violation_count": summary["runtime_contract_violation_count"],
        "prompt_leakage_flag_count": summary["prompt_leakage_flag_count"],
        "response_leakage_flag_count": summary["response_leakage_flag_count"],
        "path_leakage_flag_count": summary["path_leakage_flag_count"],
        "evidence_truth_violation_count": summary["evidence_truth_violation_count"],
        **guardrail_flags(),
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def write_artifacts(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUTS["metrics_json"], artifacts["metrics"])
    write_jsonl(OUTPUTS["per_query_jsonl"], artifacts["per_query_rows"])
    write_jsonl(OUTPUTS["agent_tool_call_trace_jsonl"], artifacts["agent_tool_call_trace_rows"])
    write_jsonl(OUTPUTS["route_policy_audit_jsonl"], artifacts["route_policy_audit_rows"])
    write_jsonl(OUTPUTS["runtime_contract_audit_jsonl"], artifacts["runtime_contract_audit_rows"])
    write_jsonl(OUTPUTS["user_response_policy_audit_jsonl"], artifacts["user_response_policy_audit_rows"])
    write_jsonl(OUTPUTS["db_contract_audit_jsonl"], artifacts["db_contract_audit_rows"])
    write_jsonl(OUTPUTS["index_contract_audit_jsonl"], artifacts["index_contract_audit_rows"])
    write_jsonl(OUTPUTS["cache_contract_audit_jsonl"], artifacts["cache_contract_audit_rows"])
    write_jsonl(OUTPUTS["live_runtime_smoke_audit_jsonl"], artifacts["live_runtime_smoke_audit_rows"])
    write_jsonl(OUTPUTS["llm_io_packet_jsonl"], artifacts["llm_io_packet_rows"])
    write_csv(OUTPUTS["llm_io_packet_csv"], artifacts["llm_io_packet_rows"])
    write_jsonl(OUTPUTS["llm_invocation_audit_jsonl"], artifacts["llm_invocation_audit_rows"])
    write_json(OUTPUTS["local_llm_readiness_json"], artifacts["local_llm_readiness"])
    write_json(OUTPUTS["prompt_manifest_json"], artifacts["prompt_manifest"])
    write_json(OUTPUTS["guardrail_audit_json"], artifacts["guardrail_audit"])
    write_jsonl(OUTPUTS["leakage_audit_jsonl"], artifacts["leakage_audit_rows"])
    write_jsonl(OUTPUTS["review_packet_jsonl"], artifacts["review_rows"])
    write_csv(OUTPUTS["review_packet_csv"], artifacts["review_rows"], REVIEW_COLUMNS)
    artifact_hashes = artifact_sha256_without_summary()
    summary = dict(artifacts["summary"])
    summary["artifact_sha256"] = artifact_hashes
    write_json(OUTPUTS["summary_json"], summary)
    return summary


def run_write(*, backend: str, base_url: str, model: str, max_tokens: int, timeout_seconds: int) -> dict[str, Any]:
    artifacts = build_artifacts(
        backend=backend,
        base_url=base_url,
        model=model,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )
    summary = write_artifacts(artifacts)
    update_docs(summary, artifacts["metrics"])
    append_status_event(summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--backend", default=DEFAULT_BACKEND, choices=["llamacpp", "openai-compatible", "ollama"])
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=420)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    args = parser.parse_args(argv)
    if args.check:
        artifacts = build_artifacts(
            backend=args.backend,
            base_url=args.base_url,
            model=args.model,
            max_tokens=args.max_tokens,
            timeout_seconds=args.timeout_seconds,
        )
        payload = {
            "run_id": RUN_ID,
            "status": artifacts["summary"]["status"],
            "llm_io_packet_row_count": artifacts["metrics"]["llm_io_packet_row_count"],
            "llm_invoked_count": artifacts["metrics"]["llm_invoked_count"],
            "raw_llm_response_present_count": artifacts["metrics"]["raw_llm_response_present_count"],
            "local_llm_unavailable_fail_closed_count": artifacts["metrics"]["local_llm_unavailable_fail_closed_count"],
            "runtime_contract_violation_count": artifacts["metrics"]["runtime_contract_violation_count"],
            "official_metric_input_rows": artifacts["metrics"]["official_metric_input_rows"],
            "local_llm_readiness_status": artifacts["local_llm_readiness"]["status"],
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    summary = run_write(
        backend=args.backend,
        base_url=args.base_url,
        model=args.model,
        max_tokens=args.max_tokens,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps({"run_id": RUN_ID, "summary": repo_relative(OUTPUTS["summary_json"]), "status": summary["status"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
