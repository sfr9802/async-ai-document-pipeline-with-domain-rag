from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v4710_pdf_korean_evidence_normalization_and_answer_replay_readiness as v4710
from ai.eval import rag_v476_archive_purge as v476
from ai.scripts import rag_local_llm_expected_answer_generation_v1 as local_llm


LOGICAL_RUN_KEY = "v4_7_11"
SHORT_RUN_ID = "v4_7_11_actual_llm_answer_replay_and_silver_diagnostic_smoke"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_11_"
    "actual_llm_answer_replay_and_silver_diagnostic_smoke_nonprod"
)
STATUS = "V4_7_11_ACTUAL_LLM_ANSWER_REPLAY_AND_SILVER_DIAGNOSTIC_SMOKE_NONPROD_READY"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
ANSWER_REVIEW_PACKET_JSONL_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "answer_review_packet_ko.jsonl"
SOURCE_RUN_ID = v4710.SHORT_RUN_ID
SOURCE_REPORT_JSON = v4710.SHORT_REPORT_PATH

ENABLE_ENV_VAR = "RAG_V4_7_11_ENABLE_LOCAL_LLM_REPLAY"
BASE_URL_ENV_VAR = "RAG_V4_7_11_LOCAL_LLM_BASE_URL"
MODEL_ENV_VAR = "RAG_V4_7_11_LOCAL_LLM_MODEL"
BACKEND_ENV_VAR = "RAG_V4_7_11_LOCAL_LLM_BACKEND"

REQUIRED_FALSE_KEYS = v4710.REQUIRED_FALSE_KEYS
STOP_TOKENS = set(v4710.STOP_TOKENS) | {"근거", "따르면", "관련", "내용", "입니다"}
FORBIDDEN_LEAKAGE_RE = re.compile(
    r"\b[A-Z]:[\\/]|prompt_payload|raw_response_payload|raw_llm_response|"
    r"\bgold\b|\bqrels\b|\bexpected\b|\bsupporting\b|source_file_title",
    re.I,
)
PATH_LEAKAGE_RE = re.compile(r"\b[A-Z]:[\\/]")

V3_7_2_NATURAL_SILVER_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_7_2_"
    "local_llm_natural_silver_query_regeneration"
)
V3_7_2_NATURAL_SILVER_MANIFEST_CANDIDATES = (
    REPORT_ROOT / f"{V3_7_2_NATURAL_SILVER_RUN_ID}_llm_natural_silver_manifest_core.jsonl",
    REPORT_ROOT / f"{V3_7_2_NATURAL_SILVER_RUN_ID}_llm_natural_silver_manifest_all.jsonl",
    REPORT_ROOT / "quality" / V3_7_2_NATURAL_SILVER_RUN_ID / "llm_natural_silver_manifest_core.jsonl",
    REPORT_ROOT / "quality" / V3_7_2_NATURAL_SILVER_RUN_ID / "llm_natural_silver_manifest_all.jsonl",
)


def utc_now_iso() -> str:
    return v476.utc_now_iso()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v476.read_jsonl(path)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v476.write_jsonl(path, rows)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v476.write_json(path, payload)


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bounded(value: Any, *, limit: int = 420) -> str:
    text = re.sub(r"\s+", " ", _clean(value)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _tokens(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", _clean(value))
        if token not in STOP_TOKENS
    }


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _repo_relative(path: Path, root: Path) -> str:
    return v476.repo_relative(path, root)


def _row_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (_clean(row.get("candidate_id_hash")), _clean(row.get("query_id_hash")))


def _env_value(env: Mapping[str, str], key: str, default: str = "") -> str:
    return _clean(env.get(key, default))


def _query_text_by_key(v474_report: Mapping[str, Any]) -> dict[tuple[str, str], str]:
    return {
        _row_key(row): _clean(row.get("query_text"))
        for row in v474_report.get("pdf_survivor_replay_ledger") or []
    }


def _citation_id(row: Mapping[str, Any]) -> str:
    key = _clean(row.get("evidence_snippet_sha256"))[:12] or str(row.get("row_index_1based") or "row")
    return f"evidence_1_{key}"


def _base_replay_row(row: Mapping[str, Any], query_text: str) -> dict[str, Any]:
    citation_id = _citation_id(row)
    evidence = _bounded(row.get("citation_span_preview"), limit=520)
    locator = _bounded(row.get("locator_preview_redacted"), limit=180)
    return {
        "row_index_1based": row.get("row_index_1based"),
        "source_family": "PDF",
        "candidate_id": row.get("candidate_id"),
        "candidate_id_hash": row.get("candidate_id_hash"),
        "query_id": row.get("query_id"),
        "query_id_hash": row.get("query_id_hash"),
        "query_text": query_text,
        "query_text_sha256": row.get("query_text_sha256") or _sha256_text(query_text),
        "query_text_source": "v4_7_4_prior_pdf_survivor_replay_ledger",
        "answer_replay_candidate": True,
        "answer_ready_evidence_bundle": True,
        "weak_evidence_window": False,
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "SearchView_vector_payload_role": "candidate_only",
        "evidence_bundle_source": row.get("evidence_bundle_source"),
        "evidence_bundle_version": row.get("evidence_bundle_version"),
        "evidence_snippet_sha256": row.get("evidence_snippet_sha256"),
        "citation_id": citation_id,
        "citation_span_preview": evidence,
        "citation_span_available": bool(evidence),
        "citation_candidate": row.get("citation_candidate") is True,
        "page_candidate": row.get("page_candidate"),
        "block_candidate": row.get("block_candidate"),
        "locator_preview_redacted": locator,
        "preserved_locator_metadata": {
            "page_candidate": row.get("page_candidate"),
            "block_candidate": row.get("block_candidate"),
            "locator_preview_redacted": locator,
            "citation_candidate": row.get("citation_candidate") is True,
            "evidence_snippet_sha256": row.get("evidence_snippet_sha256"),
        },
        "raw_pdf_query_time_parsing": False,
        "raw_xlsx_query_time_parsing": False,
        "broad_source_atom_scan_attempt_count": 0,
        "hidden_target_locator_used": False,
        "expected_or_supporting_gold_text_used": False,
        "source_file_title_shortcut_used": False,
        "direct_answer_value_matching_used": False,
        "full_page_dump_used": False,
        "vector_payload_evidence_truth_violation": False,
        "llm_invoked": False,
        "generated_response_created": False,
        "final_answer": "",
        "answer_replay_audit": {},
    }


def _select_pdf_answer_replay_rows(
    *,
    v4710_report: Mapping[str, Any],
    v474_report: Mapping[str, Any],
) -> list[dict[str, Any]]:
    queries = _query_text_by_key(v474_report)
    rows: list[dict[str, Any]] = []
    for row in v4710_report.get("pdf_residual_replay_rows") or []:
        audit = row.get("answer_replay_audit") or {}
        if audit.get("answer_replay_candidate") is not True:
            continue
        if row.get("answer_ready_evidence_bundle") is not True or row.get("weak_evidence_window") is True:
            continue
        rows.append(_base_replay_row(row, queries.get(_row_key(row), "")))
    return rows


def build_answer_prompt(row: Mapping[str, Any]) -> str:
    return json.dumps(
        {
            "task": "diagnostic_pdf_evidence_bound_korean_answer_replay",
            "instructions": [
                "Return exactly one JSON object.",
                "Use only the provided Korean query and bounded evidence excerpt.",
                "If the excerpt is insufficient, set abstain=true and final_answer=''.",
                "Do not add facts from memory or document titles.",
                "Citations must use the provided citation_id.",
            ],
            "required_schema": {
                "final_answer": "string",
                "abstain": "boolean",
                "citations": ["string"],
                "answer_plan": "string",
                "unsupported_claim_risk": "boolean",
                "evidence_underuse_flag": "boolean",
                "context_understanding_miss": "boolean",
                "over_abstain_candidate": "boolean",
            },
            "query_text": row["query_text"],
            "bounded_evidence_excerpt": row["citation_span_preview"],
            "citation_choice": {
                "citation_id": row["citation_id"],
                "page": row.get("page_candidate"),
                "block": row.get("block_candidate"),
                "locator": row.get("locator_preview_redacted"),
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def parse_json_object(value: Any) -> tuple[dict[str, Any], bool]:
    text = _clean(value)
    if not text:
        raise ValueError("empty local LLM response")
    recovered = False
    if text.startswith("```"):
        recovered = True
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I).strip()
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        recovered = True
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("local LLM response must be a JSON object")
    return parsed, recovered


def _call_local_answer_llm(
    *,
    backend: str,
    base_url: str,
    model: str,
    prompt: str,
    timeout_seconds: int,
    max_tokens: int,
    llm_client: Callable[[str], str] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = (
        llm_client(prompt)
        if llm_client is not None
        else local_llm.call_local_llm(
            backend=backend,
            base_url=base_url,
            model=model,
            prompt=prompt,
            temperature=0.0,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )
    )
    parsed, recovered = parse_json_object(raw)
    return parsed, {
        "raw_response_sha256": _sha256_text(_clean(raw)),
        "parser_recovered_json": recovered,
    }


def _local_llm_probe(
    *,
    execute: bool,
    env: Mapping[str, str],
    llm_client: Callable[[str], str] | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    env_enabled = _env_value(env, ENABLE_ENV_VAR) == "1"
    backend = _env_value(env, BACKEND_ENV_VAR, local_llm.DEFAULT_BACKEND) or local_llm.DEFAULT_BACKEND
    base_url = local_llm.resolve_base_url(backend, _env_value(env, BASE_URL_ENV_VAR))
    model = _env_value(env, MODEL_ENV_VAR, local_llm.DEFAULT_MODEL) or local_llm.DEFAULT_MODEL
    if not execute or not env_enabled:
        return {
            "status": "LOCAL_LLM_REPLAY_DISABLED_FAIL_CLOSED",
            "enabled_env_var": ENABLE_ENV_VAR,
            "env_enabled": env_enabled,
            "available": False,
            "backend": backend,
            "base_url_redacted": "localhost",
            "model": model,
            "blockers": ["RAG_V4_7_11_ENABLE_LOCAL_LLM_REPLAY_NOT_SET_TO_1"],
        }
    if llm_client is not None:
        return {
            "status": "LOCAL_LLM_AVAILABLE_DIAGNOSTIC_ONLY",
            "enabled_env_var": ENABLE_ENV_VAR,
            "env_enabled": True,
            "available": True,
            "backend": "injected-test-client",
            "base_url_redacted": "injected",
            "model": "injected",
            "blockers": [],
        }
    blockers = local_llm.local_llm_entry_blockers(
        backend=backend,
        base_url=base_url,
        model=model,
        check_endpoint=True,
        timeout_seconds=min(timeout_seconds, 10),
    )
    return {
        "status": "LOCAL_LLM_AVAILABLE_DIAGNOSTIC_ONLY" if not blockers else "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED",
        "enabled_env_var": ENABLE_ENV_VAR,
        "env_enabled": True,
        "available": not blockers,
        "backend": backend,
        "base_url_redacted": "localhost",
        "model": model,
        "blockers": blockers,
    }


def verify_claim_support(final_answer: str, evidence: str, abstain: bool, unsupported_flag: bool) -> bool:
    if abstain or unsupported_flag or not _clean(final_answer):
        return False
    return len(_tokens(final_answer) & _tokens(evidence)) >= 2


def _is_korean_answer_required(row: Mapping[str, Any]) -> bool:
    return bool(re.search(r"[가-힣]", _clean(row.get("query_text"))))


def _has_korean_text(value: Any) -> bool:
    return bool(re.search(r"[가-힣]", _clean(value)))


def _citation_is_grounded(row: Mapping[str, Any], citations: Sequence[Any]) -> bool:
    allowed = {_clean(row.get("citation_id")), "evidence_1"}
    allowed.add(_clean(row.get("evidence_snippet_sha256")))
    allowed.add(_clean(row.get("evidence_snippet_sha256"))[:12])
    for citation in citations:
        text = _clean(citation)
        if not text:
            continue
        if text in allowed or any(token and token in text for token in allowed):
            return True
    return False


def _fail_closed_audit(*, status: str, candidate: bool, reason: str) -> dict[str, Any]:
    return {
        "status": status,
        "answer_replay_candidate": candidate,
        "llm_invoked": False,
        "generated_response_created": False,
        "raw_prompt_created": False,
        "raw_llm_response_created": False,
        "parsed_final_answer_present": False,
        "citation_rendered": False,
        "citation_grounded_to_evidence": False,
        "claim_support_verifier_status": "not_run_fail_closed",
        "claim_support_verifier_pass": False,
        "claim_support_verifier_fail": False,
        "korean_final_answer": False,
        "non_korean_answer_flag": False,
        "abstain": False,
        "unsupported_claim_risk": False,
        "evidence_underuse_flag": False,
        "prompt_leakage_flag": False,
        "response_leakage_flag": False,
        "path_leakage_flag": False,
        "blocked_reason": reason,
    }


def run_pdf_answer_replay(
    rows: list[dict[str, Any]],
    *,
    execute: bool,
    env: Mapping[str, str],
    llm_timeout_seconds: int,
    llm_max_tokens: int,
    llm_client: Callable[[str], str] | None,
) -> dict[str, Any]:
    probe = _local_llm_probe(
        execute=execute,
        env=env,
        llm_client=llm_client,
        timeout_seconds=llm_timeout_seconds,
    )
    if not probe["available"]:
        reason = "; ".join(probe.get("blockers") or [probe["status"]])
        for row in rows:
            row["answer_replay_audit"] = _fail_closed_audit(
                status=probe["status"],
                candidate=True,
                reason=reason,
            )
        return probe

    backend = _env_value(env, BACKEND_ENV_VAR, local_llm.DEFAULT_BACKEND) or local_llm.DEFAULT_BACKEND
    base_url = local_llm.resolve_base_url(backend, _env_value(env, BASE_URL_ENV_VAR))
    model = _env_value(env, MODEL_ENV_VAR, local_llm.DEFAULT_MODEL) or local_llm.DEFAULT_MODEL
    if llm_client is not None:
        backend = "injected-test-client"
        base_url = "injected"
        model = "injected"

    for row in rows:
        prompt = build_answer_prompt(row)
        prompt_leakage = bool(FORBIDDEN_LEAKAGE_RE.search(prompt))
        audit: dict[str, Any] = {
            "status": "LOCAL_LLM_GENERATED_DIAGNOSTIC_ONLY",
            "answer_replay_candidate": True,
            "llm_invoked": True,
            "generated_response_created": False,
            "raw_prompt_created": False,
            "raw_llm_response_created": False,
            "raw_response_sha256": "",
            "prompt_sha256": _sha256_text(prompt),
            "strict_json_or_parser_compatible": True,
            "parser_recovered_json": False,
            "parsed_final_answer_present": False,
            "citation_rendered": False,
            "citation_grounded_to_evidence": False,
            "citation_malformed": False,
            "claim_support_verifier_status": "not_run",
            "claim_support_verifier_pass": False,
            "claim_support_verifier_fail": False,
            "korean_final_answer": False,
            "non_korean_answer_flag": False,
            "abstain": False,
            "unsupported_claim_risk": False,
            "evidence_underuse_flag": False,
            "prompt_leakage_flag": prompt_leakage,
            "response_leakage_flag": False,
            "path_leakage_flag": False,
            "invalid_json": False,
            "truncated_or_malformed_response": False,
            "blocked_reason": "",
        }
        try:
            parsed, meta = _call_local_answer_llm(
                backend=backend if backend != "injected-test-client" else local_llm.DEFAULT_BACKEND,
                base_url=base_url,
                model=model,
                prompt=prompt,
                timeout_seconds=llm_timeout_seconds,
                max_tokens=llm_max_tokens,
                llm_client=llm_client,
            )
            final_answer = _bounded(parsed.get("final_answer"), limit=520)
            abstain = parsed.get("abstain") is True
            citations = parsed.get("citations") if isinstance(parsed.get("citations"), list) else []
            unsupported = parsed.get("unsupported_claim_risk") is True
            verifier_pass = verify_claim_support(final_answer, row["citation_span_preview"], abstain, unsupported)
            citation_grounded = _citation_is_grounded(row, citations)
            korean_answer = _has_korean_text(final_answer)
            non_korean = _is_korean_answer_required(row) and bool(final_answer) and not korean_answer
            response_payload = json.dumps(
                {
                    "final_answer": final_answer,
                    "citations": citations,
                    "answer_plan": _clean(parsed.get("answer_plan")),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            response_leakage = bool(FORBIDDEN_LEAKAGE_RE.search(response_payload))
            path_leakage = bool(PATH_LEAKAGE_RE.search(response_payload))
            audit.update(
                {
                    "generated_response_created": True,
                    "raw_response_sha256": _clean(meta.get("raw_response_sha256")),
                    "parser_recovered_json": bool(meta.get("parser_recovered_json")),
                    "parsed_final_answer_present": bool(final_answer),
                    "citation_rendered": bool(citations),
                    "citation_grounded_to_evidence": citation_grounded,
                    "citation_malformed": bool(citations) and not citation_grounded,
                    "claim_support_verifier_status": "pass" if verifier_pass else "fail",
                    "claim_support_verifier_pass": verifier_pass,
                    "claim_support_verifier_fail": not verifier_pass,
                    "korean_final_answer": korean_answer,
                    "non_korean_answer_flag": non_korean,
                    "abstain": abstain,
                    "unsupported_claim_risk": unsupported or (bool(final_answer) and not verifier_pass),
                    "evidence_underuse_flag": parsed.get("evidence_underuse_flag") is True
                    or (bool(final_answer) and not verifier_pass),
                    "response_leakage_flag": response_leakage,
                    "path_leakage_flag": path_leakage,
                    "answer_plan_created": bool(_clean(parsed.get("answer_plan"))),
                }
            )
            row["final_answer"] = final_answer
            row["rendered_citations"] = [
                f"{_clean(citation)} page={row.get('page_candidate')} block={row.get('block_candidate')}"
                for citation in citations
                if _clean(citation)
            ]
            row["llm_invoked"] = True
            row["generated_response_created"] = True
            row["answer_replay_audit"] = audit
        except json.JSONDecodeError as exc:
            audit.update(
                {
                    "status": "LOCAL_LLM_INVALID_JSON_FAIL_CLOSED",
                    "invalid_json": True,
                    "truncated_or_malformed_response": True,
                    "claim_support_verifier_status": "not_run_invalid_json",
                    "blocked_reason": f"LOCAL_LLM_OUTPUT_INVALID_JSON:{type(exc).__name__}",
                }
            )
            row["answer_replay_audit"] = audit
            row["llm_invoked"] = True
        except Exception as exc:
            reason = f"LOCAL_LLM_INVOCATION_FAILED:{type(exc).__name__}: {_bounded(str(exc), limit=120)}"
            audit.update(
                {
                    "status": "LOCAL_LLM_INVOCATION_FAILED_FAIL_CLOSED",
                    "truncated_or_malformed_response": True,
                    "claim_support_verifier_status": "not_run_invocation_failed",
                    "blocked_reason": reason,
                }
            )
            row["answer_replay_audit"] = audit
            row["llm_invoked"] = True
    return probe


def _answer_review_packet_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    packet: list[dict[str, Any]] = []
    for row in rows:
        audit = row.get("answer_replay_audit") or {}
        packet.append(
            {
                "row_index_1based": row.get("row_index_1based"),
                "candidate_id_hash": row.get("candidate_id_hash"),
                "query_id": row.get("query_id"),
                "query_id_hash": row.get("query_id_hash"),
                "query_text": row.get("query_text"),
                "final_answer": row.get("final_answer", ""),
                "rendered_citations": row.get("rendered_citations", []),
                "cited_evidence_snippet": row.get("citation_span_preview"),
                "claim_support_verifier_status": audit.get("claim_support_verifier_status"),
                "claim_support_verifier_pass": audit.get("claim_support_verifier_pass") is True,
                "abstain": audit.get("abstain") is True,
                "status": audit.get("status"),
                "blocked_reason": audit.get("blocked_reason", ""),
                "unsupported_claim_risk": audit.get("unsupported_claim_risk") is True,
                "evidence_underuse_flag": audit.get("evidence_underuse_flag") is True,
                "prompt_sha256": audit.get("prompt_sha256", ""),
                "raw_response_sha256": audit.get("raw_response_sha256", ""),
                "raw_prompt_payload_written": False,
                "raw_response_payload_written": False,
                "diagnostic_only": True,
            }
        )
    return packet


def _silver_source_path(root: Path) -> Path | None:
    for rel_path in V3_7_2_NATURAL_SILVER_MANIFEST_CANDIDATES:
        path = root / rel_path
        if path.exists():
            return path
    return None


def _silver_smoke_plan(root: Path, *, llm_available: bool) -> dict[str, Any]:
    source_path = _silver_source_path(root)
    target_count = 30
    if source_path is None:
        return {
            "status": "SILVER_SOURCE_ARTIFACTS_UNAVAILABLE_FAIL_CLOSED",
            "executed": False,
            "diagnostic_silver_only": True,
            "target_sample_count": target_count,
            "source_manifest_path": "",
            "blocked_reason": "v3_7_2 natural silver manifest is not present in local ignored artifacts",
            "plan": {
                "source": "v3_7_2_local_llm_natural_silver_query_regeneration",
                "target_sample_count": target_count,
                "balanced_target_by_family": {"TEXT": 10, "PDF": 10, "XLSX": 10},
                "source_files_mutated": False,
                "official_metric_input_rows": 0,
            },
            "candidate_available_count": 0,
            "sample_count": 0,
            "sample_counts_by_family": {"TEXT": 0, "PDF": 0, "XLSX": 0},
            "llm_invoked_count": 0,
            "generated_response_count": 0,
            "parsed_final_answer_present_count": 0,
            "citation_rendered_count": 0,
            "claim_support_verifier_pass_count": 0,
            "claim_support_verifier_fail_count": 0,
            "abstain_count": 0,
            "fail_closed_count": 0,
            "silver_promoted_to_gold_count": 0,
            "official_metric_input_rows": 0,
        }
    rows = read_jsonl(source_path)
    by_family = {"TEXT": [], "PDF": [], "XLSX": []}
    for row in rows:
        family = _clean(row.get("source_family") or row.get("family")).upper()
        if family in by_family:
            by_family[family].append(row)
    selected_count = sum(min(10, len(items)) for items in by_family.values())
    return {
        "status": "SILVER_SMOKE_REQUIRES_SOURCEATOM_HYDRATION_REVIEW_FAIL_CLOSED"
        if llm_available
        else "SILVER_LLM_UNAVAILABLE_FAIL_CLOSED",
        "executed": False,
        "diagnostic_silver_only": True,
        "target_sample_count": target_count,
        "source_manifest_path": _repo_relative(source_path, root),
        "blocked_reason": "bounded silver source manifest was found, but this slice does not open a new SourceAtom hydration path",
        "plan": {
            "source": "v3_7_2_local_llm_natural_silver_query_regeneration",
            "target_sample_count": target_count,
            "balanced_target_by_family": {"TEXT": 10, "PDF": 10, "XLSX": 10},
            "source_files_mutated": False,
            "official_metric_input_rows": 0,
        },
        "candidate_available_count": len(rows),
        "sample_count": selected_count,
        "sample_counts_by_family": {family: min(10, len(items)) for family, items in by_family.items()},
        "llm_invoked_count": 0,
        "generated_response_count": 0,
        "parsed_final_answer_present_count": 0,
        "citation_rendered_count": 0,
        "claim_support_verifier_pass_count": 0,
        "claim_support_verifier_fail_count": 0,
        "abstain_count": 0,
        "fail_closed_count": selected_count,
        "silver_promoted_to_gold_count": 0,
        "official_metric_input_rows": 0,
    }


def _count(rows: Sequence[Mapping[str, Any]], audit_key: str) -> int:
    return sum(1 for row in rows if (row.get("answer_replay_audit") or {}).get(audit_key) is True)


def _build_counters(
    *,
    v4710_report: Mapping[str, Any],
    replay_rows: Sequence[Mapping[str, Any]],
    all_v4710_rows: Sequence[Mapping[str, Any]],
    local_probe: Mapping[str, Any],
    silver_smoke: Mapping[str, Any],
) -> dict[str, Any]:
    source_counters = v4710_report.get("counters") or {}
    statuses = [(row.get("answer_replay_audit") or {}).get("status") for row in replay_rows]
    llm_invoked_count = _count(replay_rows, "llm_invoked")
    generated_response_count = _count(replay_rows, "generated_response_created")
    invalid_json_count = _count(replay_rows, "invalid_json")
    malformed_count = _count(replay_rows, "truncated_or_malformed_response")
    replay_candidate_count = int(source_counters.get("answer_replay_candidate_count") or len(replay_rows))
    return {
        "pdf_survivor_row_count": int(source_counters.get("pdf_survivor_row_count") or len(all_v4710_rows)),
        "v4_7_10_answer_ready_evidence_bundle_count": int(
            source_counters.get("answer_ready_evidence_bundle_count") or 0
        ),
        "v4_7_10_answer_replay_candidate_count": replay_candidate_count,
        "v4_7_10_replayed_candidate_count": len(replay_rows),
        "v4_7_10_skipped_weak_residual_count": sum(1 for row in all_v4710_rows if row.get("weak_evidence_window") is True),
        "local_llm_available": bool(local_probe.get("available")),
        "local_llm_replay_env_enabled": bool(local_probe.get("env_enabled")),
        "llm_invoked_count": llm_invoked_count,
        "local_llm_unavailable_fail_closed_count": statuses.count("LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"),
        "local_llm_replay_disabled_fail_closed_count": statuses.count("LOCAL_LLM_REPLAY_DISABLED_FAIL_CLOSED"),
        "local_llm_invocation_failed_fail_closed_count": statuses.count("LOCAL_LLM_INVOCATION_FAILED_FAIL_CLOSED"),
        "generated_response_count": generated_response_count,
        "raw_llm_response_present_count": 0,
        "parsed_final_answer_present_count": _count(replay_rows, "parsed_final_answer_present"),
        "invalid_json_count": invalid_json_count,
        "truncated_or_malformed_response_count": malformed_count,
        "citation_rendered_count": _count(replay_rows, "citation_rendered"),
        "citation_grounded_to_evidence_count": _count(replay_rows, "citation_grounded_to_evidence"),
        "citation_malformed_count": _count(replay_rows, "citation_malformed"),
        "korean_final_answer_count": _count(replay_rows, "korean_final_answer"),
        "non_korean_answer_flag_count": _count(replay_rows, "non_korean_answer_flag"),
        "abstain_count": _count(replay_rows, "abstain"),
        "claim_support_verifier_pass_count": _count(replay_rows, "claim_support_verifier_pass"),
        "claim_support_verifier_fail_count": _count(replay_rows, "claim_support_verifier_fail"),
        "unsupported_claim_risk_count": _count(replay_rows, "unsupported_claim_risk"),
        "evidence_underuse_flag_count": _count(replay_rows, "evidence_underuse_flag"),
        "prompt_leakage_flag_count": _count(replay_rows, "prompt_leakage_flag"),
        "response_leakage_flag_count": _count(replay_rows, "response_leakage_flag"),
        "path_leakage_flag_count": _count(replay_rows, "path_leakage_flag"),
        "evidence_truth_violation_count": sum(
            1 for row in replay_rows if row.get("SourceAtom_EvidenceBundle_role") != "evidence_truth"
        ),
        "vector_payload_evidence_truth_violation_count": sum(
            1 for row in replay_rows if row.get("SearchView_vector_payload_role") != "candidate_only"
        ),
        "broad_source_atom_scan_attempt_count": sum(
            int(row.get("broad_source_atom_scan_attempt_count") or 0) for row in replay_rows
        ),
        "raw_pdf_query_time_parsing_count": sum(1 for row in replay_rows if row.get("raw_pdf_query_time_parsing") is True),
        "raw_xlsx_query_time_parsing_count": sum(1 for row in replay_rows if row.get("raw_xlsx_query_time_parsing") is True),
        "direct_answer_value_matching_used_count": sum(
            1 for row in replay_rows if row.get("direct_answer_value_matching_used") is True
        ),
        "expected_or_supporting_gold_text_used_count": sum(
            1 for row in replay_rows if row.get("expected_or_supporting_gold_text_used") is True
        ),
        "hidden_target_locator_used_count": sum(1 for row in replay_rows if row.get("hidden_target_locator_used") is True),
        "full_page_dump_used_count": sum(1 for row in replay_rows if row.get("full_page_dump_used") is True),
        "source_file_title_shortcut_used_count": sum(
            1 for row in replay_rows if row.get("source_file_title_shortcut_used") is True
        ),
        "noop_or_extractive_generator_used": False,
        "answer_review_packet_row_count": len(replay_rows),
        "silver_candidate_available_count": int(silver_smoke.get("candidate_available_count") or 0),
        "silver_smoke_sample_count": int(silver_smoke.get("sample_count") or 0),
        "silver_smoke_text_count": int((silver_smoke.get("sample_counts_by_family") or {}).get("TEXT") or 0),
        "silver_smoke_pdf_count": int((silver_smoke.get("sample_counts_by_family") or {}).get("PDF") or 0),
        "silver_smoke_xlsx_count": int((silver_smoke.get("sample_counts_by_family") or {}).get("XLSX") or 0),
        "silver_llm_invoked_count": int(silver_smoke.get("llm_invoked_count") or 0),
        "silver_generated_response_count": int(silver_smoke.get("generated_response_count") or 0),
        "silver_parsed_final_answer_present_count": int(silver_smoke.get("parsed_final_answer_present_count") or 0),
        "silver_citation_rendered_count": int(silver_smoke.get("citation_rendered_count") or 0),
        "silver_claim_support_verifier_pass_count": int(silver_smoke.get("claim_support_verifier_pass_count") or 0),
        "silver_claim_support_verifier_fail_count": int(silver_smoke.get("claim_support_verifier_fail_count") or 0),
        "silver_abstain_count": int(silver_smoke.get("abstain_count") or 0),
        "silver_fail_closed_count": int(silver_smoke.get("fail_closed_count") or 0),
        "silver_promoted_to_gold_count": int(silver_smoke.get("silver_promoted_to_gold_count") or 0),
        "silver_official_metric_input_rows": int(silver_smoke.get("official_metric_input_rows") or 0),
        "official_metric": False,
        "official_metric_input_rows": 0,
        "protected_namespaces_touched": [],
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
    }


def build_report(
    *,
    root: Path,
    execute: bool = False,
    sync_surfaces: bool = False,
    env: Mapping[str, str] | None = None,
    llm_timeout_seconds: int = 90,
    llm_max_tokens: int = 520,
    llm_client: Callable[[str], str] | None = None,
    generated_at: str | None = None,
    check: bool = True,
) -> dict[str, Any]:
    del sync_surfaces
    env = os.environ if env is None else env
    source_report = registry.load_report("v4_7_10", root=root)
    v4710.check_report(source_report)
    prior_report = registry.load_report("v4_7_4", root=root)
    all_v4710_rows = list(source_report.get("pdf_residual_replay_rows") or [])
    replay_rows = _select_pdf_answer_replay_rows(v4710_report=source_report, v474_report=prior_report)
    local_probe = run_pdf_answer_replay(
        replay_rows,
        execute=execute,
        env=env,
        llm_timeout_seconds=llm_timeout_seconds,
        llm_max_tokens=llm_max_tokens,
        llm_client=llm_client,
    )
    silver_smoke = _silver_smoke_plan(root, llm_available=bool(local_probe.get("available")))
    counters = _build_counters(
        v4710_report=source_report,
        replay_rows=replay_rows,
        all_v4710_rows=all_v4710_rows,
        local_probe=local_probe,
        silver_smoke=silver_smoke,
    )
    packet_rows = _answer_review_packet_rows(replay_rows)
    report = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated_at or utc_now_iso(),
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
            "answer_review_packet_jsonl": ANSWER_REVIEW_PACKET_JSONL_PATH.as_posix(),
        },
        "source_run_id": SOURCE_RUN_ID,
        "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "SearchView_vector_payload_role": "candidate_only",
        "raw_pdf_query_time_parsing": False,
        "raw_xlsx_query_time_parsing": False,
        "broad_source_atom_scan_attempt_count": 0,
        "hidden_target_locator_used": False,
        "expected_or_supporting_gold_text_used": False,
        "source_file_title_shortcut_used": False,
        "direct_answer_value_matching_used": False,
        "full_page_dump_used": False,
        "vector_payload_evidence_truth_violation_count": 0,
        "local_llm_probe": local_probe,
        "counters": counters,
        "pdf_survivor_row_count": counters["pdf_survivor_row_count"],
        "pdf_answer_replay_rows": replay_rows,
        "answer_review_packet_rows": packet_rows,
        "silver_diagnostic_smoke": silver_smoke,
        "answer_review_packet_policy": {
            "ignored_generated_artifact": True,
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
            "status_docs_record_counts_hashes_paths_only": True,
        },
        "completion_branch": "A_actual_local_llm_answer_replay_opened_diagnostic_only"
        if counters["generated_response_count"] > 0
        else "B_local_llm_replay_fail_closed_without_fake_answers",
        "non_gold_ambiguity_decisions": [
            {
                "decision": "replay_only_v4_7_10_answer_replay_candidates",
                "reason": "the single weak residual row remains excluded from answer generation",
            },
            {
                "decision": "local_llm_env_gate_required",
                "reason": f"{ENABLE_ENV_VAR}=1 is required before any local LLM call",
            },
            {
                "decision": "silver_smoke_plan_fail_closed_when_manifest_or_hydration_path_is_unavailable",
                "reason": "silver rows remain diagnostic_silver_only and cannot become official metric inputs",
            },
        ],
        "residual_risks": [
            "claim-support verification is a SourceAtom-only diagnostic proxy, not a gold judgment",
            "silver diagnostic smoke did not open a new SourceAtom hydration path in this slice",
        ],
    }
    if check:
        check_report(report)
    return report


def write_answer_review_packet(root: Path, report: Mapping[str, Any]) -> str:
    path = root / ANSWER_REVIEW_PACKET_JSONL_PATH
    write_jsonl(path, report.get("answer_review_packet_rows") or [])
    return v476.sha256_file(path)


def status_event(
    report: Mapping[str, Any],
    *,
    report_sha256: str,
    answer_packet_sha256: str,
) -> dict[str, Any]:
    counters = report["counters"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "event_type": "diagnostic_v4_7_11_actual_llm_answer_replay_and_silver_smoke_nonprod",
        "status": STATUS,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": {
            "report_json_sha256": report_sha256,
            "answer_review_packet_jsonl_sha256": answer_packet_sha256,
        },
        "source_run_id": report["source_run_id"],
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
        "completion_branch": report["completion_branch"],
        "local_llm_status": report["local_llm_probe"]["status"],
        "answer_review_packet_row_count": counters["answer_review_packet_row_count"],
        "silver_diagnostic_smoke_status": report["silver_diagnostic_smoke"]["status"],
        **counters,
    }


def append_status(
    root: Path,
    report: Mapping[str, Any],
    *,
    report_sha256: str,
    answer_packet_sha256: str,
) -> None:
    status_path = root / STATUS_JSONL_PATH
    existing = [
        row
        for row in read_jsonl(status_path)
        if row.get("short_run_id") != SHORT_RUN_ID and row.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID
    ]
    write_jsonl(
        status_path,
        [
            *existing,
            status_event(
                report,
                report_sha256=report_sha256,
                answer_packet_sha256=answer_packet_sha256,
            ),
        ],
    )


def _counter_table(counters: Mapping[str, Any]) -> str:
    return "\n".join(
        f"| {key} | {json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict, bool)) else value} |"
        for key, value in counters.items()
        if key != "protected_namespaces_touched"
    )


def update_progress_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-progress.md"
    counters = report["counters"]
    start = f"<!-- {SHORT_RUN_ID}:progress-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:progress-entry:end -->"
    block = (
        f"- {SHORT_RUN_ID} is {STATUS}. Artifact: `{SHORT_REPORT_PATH.as_posix()}`. "
        "This diagnostic-only slice consumes v4_7_10 and opens actual localhost LLM answer replay only for "
        f"{counters['v4_7_10_answer_replay_candidate_count']} v4_7_10 answer-replay candidates; "
        f"{counters['v4_7_10_skipped_weak_residual_count']} weak residual row stays excluded. "
        f"Env gate `{ENABLE_ENV_VAR}` enabled={str(counters['local_llm_replay_env_enabled']).lower()}, "
        f"local_llm_available={str(counters['local_llm_available']).lower()}, generated responses "
        f"{counters['generated_response_count']}, parsed answers {counters['parsed_final_answer_present_count']}, "
        f"citations rendered {counters['citation_rendered_count']}, claim-support pass/fail "
        f"{counters['claim_support_verifier_pass_count']}/{counters['claim_support_verifier_fail_count']}, "
        f"Korean answers {counters['korean_final_answer_count']}. Silver smoke remains diagnostic_silver_only: "
        f"sample {counters['silver_smoke_sample_count']} "
        f"(TEXT {counters['silver_smoke_text_count']}, PDF {counters['silver_smoke_pdf_count']}, "
        f"XLSX {counters['silver_smoke_xlsx_count']}), status `{report['silver_diagnostic_smoke']['status']}`. "
        "SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only. "
        "official_metric=false, official_metric_input_rows=0, and all gold/qrels, labels, denominator, training, "
        "FT-A, fine_tuning, promotion, product-success, and live-readiness gates stay closed."
    )
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"Last updated: .*? KST\.", "Last updated: 2026-05-30 KST.", text, count=1)
    text = re.sub(r"Overall status: `[^`]+`;", f"Overall status: `{STATUS}`;", text, count=1)
    anchor = "for behavior-changing runs or explicit forensic evidence requirements.\n"
    text = v476.upsert_block(text, start_marker=start, end_marker=end, block=block, after_anchor=anchor)
    path.write_text(text, encoding="utf-8")


def update_measurements_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-measurements.md"
    counters = report["counters"]
    start = f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->"
    block = f"""### v4_7_11 Actual LLM Answer Replay And Silver Diagnostic Smoke

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Answer review packet: `{ANSWER_REVIEW_PACKET_JSONL_PATH.as_posix()}`
- Source artifact: `{SOURCE_REPORT_JSON.as_posix()}`
- Local LLM env gate: `{ENABLE_ENV_VAR}`
- Boundary: diagnostic-only localhost LLM replay over v4_7_10 EvidenceBundle-ready rows. No raw prompt or raw response payload is written to Markdown/status; no official metric, gold/qrels/labels/expected/supporting evidence mutation, denominator mutation, training/fine_tuning/FT-A, promotion, product success, or live-readiness is opened.
- Replay result: candidates {counters['v4_7_10_answer_replay_candidate_count']}; skipped weak residual {counters['v4_7_10_skipped_weak_residual_count']}; generated {counters['generated_response_count']}; parsed answers {counters['parsed_final_answer_present_count']}; citations rendered {counters['citation_rendered_count']}; claim-support pass/fail {counters['claim_support_verifier_pass_count']}/{counters['claim_support_verifier_fail_count']}; unsupported/evidence-underuse {counters['unsupported_claim_risk_count']}/{counters['evidence_underuse_flag_count']}; Korean answers {counters['korean_final_answer_count']}; non-Korean flags {counters['non_korean_answer_flag_count']}.
- Silver diagnostic smoke: status `{report['silver_diagnostic_smoke']['status']}`; sample {counters['silver_smoke_sample_count']} (TEXT {counters['silver_smoke_text_count']}, PDF {counters['silver_smoke_pdf_count']}, XLSX {counters['silver_smoke_xlsx_count']}); generated {counters['silver_generated_response_count']}; official input rows {counters['silver_official_metric_input_rows']}.

| Counter | Value |
|---|---:|
{_counter_table(counters)}
"""
    text = path.read_text(encoding="utf-8")
    text = v476.upsert_block(text, start_marker=start, end_marker=end, block=block)
    path.write_text(text, encoding="utf-8")


def update_triage_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-triage.md"
    counters = report["counters"]
    start = f"<!-- {SHORT_RUN_ID}:triage-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:triage-entry:end -->"
    block = f"""### v4_7_11 Actual LLM Replay Boundary

- Scope: v4_7_10 answer-replay candidates only; the single weak residual row remains fail-closed and excluded from LLM generation.
- Local LLM policy: `{ENABLE_ENV_VAR}=1` plus localhost endpoint availability is required. Disabled/unavailable rows emit no fake, noop, deterministic extractive, raw prompt, or raw response payload.
- Answer audit: generated {counters['generated_response_count']}; parsed answers {counters['parsed_final_answer_present_count']}; citation rendered/grounded {counters['citation_rendered_count']}/{counters['citation_grounded_to_evidence_count']}; claim-support pass/fail {counters['claim_support_verifier_pass_count']}/{counters['claim_support_verifier_fail_count']}; unsupported claim risk {counters['unsupported_claim_risk_count']}; evidence underuse {counters['evidence_underuse_flag_count']}; non-Korean flags {counters['non_korean_answer_flag_count']}.
- Silver lane: diagnostic_silver_only, status `{report['silver_diagnostic_smoke']['status']}`, source files mutated=false, official metric input rows=0, promoted-to-gold count=0.
- Closed gates: official_metric=false, official_metric_input_rows=0, gold/qrels/labels/expected/supporting evidence/denominator/training/FT-A/fine_tuning/promotion/product-success/live-readiness remain closed.
"""
    text = path.read_text(encoding="utf-8")
    text = v476.upsert_block(text, start_marker=start, end_marker=end, block=block)
    path.write_text(text, encoding="utf-8")


def update_root_readme(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "README.md"
    counters = report["counters"]
    text = path.read_text(encoding="utf-8")
    snapshot = f"""## Current RAG Diagnostic Status

- Current RAG status: `{STATUS}`.
- Phase: v4_7 remains pre-official. `{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}` and opens diagnostic-only local LLM answer replay for the v4_7_10 EvidenceBundle-ready PDF candidates; it does not open official metrics, gold/qrels, labels, denominator, training, promotion, product-success, or live-readiness.
- Resolver wiring: use `current` or `v4_7_11` for actual LLM answer replay and silver diagnostic smoke readiness; use `v4_7_10` for the prior Korean evidence normalization/readiness report.
- Runner consolidation: `ai/scripts/rag_eval.py` remains the stable short-key runner for `current`, `v4_7_11`, `v4_7_10`, `v4_7_9`, `v4_7_8`, prior v4_7 cleanup keys, and verified check-only legacy aliases.
- Retained v4_7 resolver context: `v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness` is the prior Korean normalization/readiness report with weak evidence/window 3 -> 1, `v4_7_9_pdf_evidence_residual_answer_quality_replay` is the prior PDF residual evidence replay report, and `v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion` remains the prior cleanup/refactor report.
- Retained review lineage: v4_7_2 supersedes the abstract v4_7_1 Korean review packet with non-empty `질의문` 204 and hydrated rows 204, PDF 100, XLSX 104; v4_7_3 applies the user-reviewed Korean query candidate CSV with 미검수=통과; v4_7_4 keeps PDF survivor 58; these remain not official metric.
- PDF answer replay: v4_7_10 replay candidates {counters['v4_7_10_answer_replay_candidate_count']}; weak residual skipped {counters['v4_7_10_skipped_weak_residual_count']}; generated responses {counters['generated_response_count']}; parsed final answers {counters['parsed_final_answer_present_count']}; citations rendered {counters['citation_rendered_count']}; claim-support pass/fail {counters['claim_support_verifier_pass_count']}/{counters['claim_support_verifier_fail_count']}; Korean final answers {counters['korean_final_answer_count']}; local LLM env gate `{ENABLE_ENV_VAR}`.
- Silver diagnostic smoke: status `{report['silver_diagnostic_smoke']['status']}`; sample {counters['silver_smoke_sample_count']} (TEXT {counters['silver_smoke_text_count']}, PDF {counters['silver_smoke_pdf_count']}, XLSX {counters['silver_smoke_xlsx_count']}); silver_official_metric_input_rows=0 and silver_promoted_to_gold_count=0.
- Rolling evidence docs: `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md` remain the canonical human-readable status ledgers; answer review details stay in the ignored JSONL packet.
- Hard boundary: not official metric, not gold/qrels, not relevance/answerability labels, not expected answer/evidence approval, not product-success evidence, not promotion evidence, not FT-A execution, not fine_tuning, not actual fine-tuning/training, not threshold tuning, not winner selection, not training data, and not live DB/index/cache readiness. Locked flags remain `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `ft_a_execution=false`, `fine_tuning=false`, `fine_tuning_executed=false`, and `live_db_index_cache_readiness=false`.
"""
    text = re.sub(r"## Current RAG Diagnostic Status\n.*?(?=\n## )", snapshot.rstrip() + "\n\n", text, count=1, flags=re.S)
    path.write_text(text, encoding="utf-8")


def update_eval_readme(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "ai" / "eval" / "README.md"
    counters = report["counters"]
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"- Current RAG status: `[^`]+`", f"- Current RAG status: `{STATUS}`", text, count=1)
    text = text.replace("`current` now resolves to v4_7_10", "`current` now resolves to v4_7_11")
    marker = (
        f"- v4_7_11 diagnostic replay: `{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}` and "
        f"ignored answer packet `{ANSWER_REVIEW_PACKET_JSONL_PATH.as_posix()}` through `ai/scripts/rag_eval.py`; "
        f"generated {counters['generated_response_count']}, parsed {counters['parsed_final_answer_present_count']}, "
        f"citations {counters['citation_rendered_count']}, claim-support pass/fail "
        f"{counters['claim_support_verifier_pass_count']}/{counters['claim_support_verifier_fail_count']}, "
        f"silver sample {counters['silver_smoke_sample_count']}; official_metric=false. Prior resolver context remains "
        "`v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness`, "
        "`v4_7_9_pdf_evidence_residual_answer_quality_replay`, and "
        "`v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion`."
    )
    lines: list[str] = []
    inserted = False
    for line in text.splitlines():
        if line.startswith("- v4_7_11 diagnostic replay:"):
            if not inserted:
                lines.append(marker)
                inserted = True
            continue
        lines.append(line)
        if line == f"- Current RAG status: `{STATUS}`" and not inserted:
            lines.append(marker)
            inserted = True
    if not inserted:
        lines.append(marker)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_scripts_readme(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "ai" / "scripts" / "README.md"
    counters = report["counters"]
    text = path.read_text(encoding="utf-8")
    replacement = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        f"`{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}`, `current` resolves to `v4_7_11`, "
        f"answer replay generated {counters['generated_response_count']} responses, parsed "
        f"{counters['parsed_final_answer_present_count']} final answers, and writes the ignored "
        f"`{ANSWER_REVIEW_PACKET_JSONL_PATH.as_posix()}` packet without raw prompt/response payloads; prior resolver context "
        "`v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness` with weak evidence/window 3 -> 1, "
        "`v4_7_9_pdf_evidence_residual_answer_quality_replay`, and "
        "`v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion` remains checkable. |"
    )
    text = re.sub(r"\| `rag_eval\.py` \| .*? \|", replacement, text, count=1)
    if replacement not in text:
        text = text.replace("| Script | Role |\n|---|---|\n", "| Script | Role |\n|---|---|\n" + replacement + "\n", 1)
    path.write_text(text, encoding="utf-8")


def update_docs(root: Path, report: Mapping[str, Any]) -> None:
    update_progress_doc(root, report)
    update_measurements_doc(root, report)
    update_triage_doc(root, report)
    update_root_readme(root, report)
    update_eval_readme(root, report)
    update_scripts_readme(root, report)


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v4_7_11 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v4_7_11 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v4_7_11 status mismatch")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v4_7_11 must remain diagnostic-only and non-production")
    for key in REQUIRED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v4_7_11 closed guardrail mismatch: {key}")
    if report.get("official_metric_input_rows") != 0:
        raise ValueError("v4_7_11 official_metric_input_rows must stay zero")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_11 protected namespaces were touched")
    if report.get("SourceAtom_EvidenceBundle_role") != "evidence_truth":
        raise ValueError("v4_7_11 SourceAtom/EvidenceBundle role drifted")
    if report.get("SearchView_vector_payload_role") != "candidate_only":
        raise ValueError("v4_7_11 SearchView role drifted")
    counters = report.get("counters") or {}
    required_counter_keys = (
        "pdf_survivor_row_count",
        "v4_7_10_answer_ready_evidence_bundle_count",
        "v4_7_10_answer_replay_candidate_count",
        "v4_7_10_replayed_candidate_count",
        "v4_7_10_skipped_weak_residual_count",
        "local_llm_available",
        "local_llm_replay_env_enabled",
        "llm_invoked_count",
        "local_llm_unavailable_fail_closed_count",
        "local_llm_replay_disabled_fail_closed_count",
        "generated_response_count",
        "raw_llm_response_present_count",
        "parsed_final_answer_present_count",
        "invalid_json_count",
        "truncated_or_malformed_response_count",
        "citation_rendered_count",
        "citation_grounded_to_evidence_count",
        "citation_malformed_count",
        "korean_final_answer_count",
        "non_korean_answer_flag_count",
        "abstain_count",
        "claim_support_verifier_pass_count",
        "claim_support_verifier_fail_count",
        "unsupported_claim_risk_count",
        "evidence_underuse_flag_count",
        "prompt_leakage_flag_count",
        "response_leakage_flag_count",
        "path_leakage_flag_count",
        "evidence_truth_violation_count",
        "vector_payload_evidence_truth_violation_count",
        "broad_source_atom_scan_attempt_count",
        "raw_pdf_query_time_parsing_count",
        "raw_xlsx_query_time_parsing_count",
        "direct_answer_value_matching_used_count",
        "expected_or_supporting_gold_text_used_count",
        "hidden_target_locator_used_count",
        "full_page_dump_used_count",
        "source_file_title_shortcut_used_count",
        "silver_candidate_available_count",
        "silver_smoke_sample_count",
        "silver_smoke_text_count",
        "silver_smoke_pdf_count",
        "silver_smoke_xlsx_count",
        "silver_llm_invoked_count",
        "silver_generated_response_count",
        "silver_parsed_final_answer_present_count",
        "silver_citation_rendered_count",
        "silver_claim_support_verifier_pass_count",
        "silver_claim_support_verifier_fail_count",
        "silver_abstain_count",
        "silver_fail_closed_count",
        "silver_promoted_to_gold_count",
        "silver_official_metric_input_rows",
        "official_metric",
        "official_metric_input_rows",
        "protected_namespaces_touched",
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "denominator_mutation",
        "training_dataset_created",
        "ft_a_execution",
        "fine_tuning",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "live_db_index_cache_readiness",
    )
    missing = [key for key in required_counter_keys if key not in counters]
    if missing:
        raise ValueError(f"v4_7_11 missing counters: {missing}")
    if counters["pdf_survivor_row_count"] != 58:
        raise ValueError("v4_7_11 PDF survivor row count drifted")
    if counters["v4_7_10_answer_ready_evidence_bundle_count"] != 57:
        raise ValueError("v4_7_11 must consume v4_7_10 answer-ready count")
    if counters["v4_7_10_answer_replay_candidate_count"] != 9:
        raise ValueError("v4_7_11 must replay the nine v4_7_10 answer candidates")
    if counters["v4_7_10_replayed_candidate_count"] != 9:
        raise ValueError("v4_7_11 replay row count drifted")
    if counters["v4_7_10_skipped_weak_residual_count"] != 1:
        raise ValueError("v4_7_11 must keep the weak residual skipped")
    if counters["raw_llm_response_present_count"] != 0:
        raise ValueError("v4_7_11 must not store raw LLM response payloads")
    if counters["official_metric_input_rows"] != 0 or counters["silver_official_metric_input_rows"] != 0:
        raise ValueError("v4_7_11 official metric rows must stay zero")
    for key in REQUIRED_FALSE_KEYS:
        if counters.get(key) is not False:
            raise ValueError(f"v4_7_11 closed counter mismatch: {key}")
    if counters["protected_namespaces_touched"] != []:
        raise ValueError("v4_7_11 protected namespace counter drifted")
    for key in (
        "evidence_truth_violation_count",
        "vector_payload_evidence_truth_violation_count",
        "broad_source_atom_scan_attempt_count",
        "raw_pdf_query_time_parsing_count",
        "raw_xlsx_query_time_parsing_count",
        "direct_answer_value_matching_used_count",
        "expected_or_supporting_gold_text_used_count",
        "hidden_target_locator_used_count",
        "full_page_dump_used_count",
        "source_file_title_shortcut_used_count",
        "prompt_leakage_flag_count",
        "response_leakage_flag_count",
        "path_leakage_flag_count",
    ):
        if counters.get(key) != 0:
            raise ValueError(f"v4_7_11 guardrail counter must be zero: {key}")
    rows = list(report.get("pdf_answer_replay_rows") or [])
    if len(rows) != 9:
        raise ValueError("v4_7_11 PDF replay row ledger count drifted")
    for row in rows:
        if row.get("SourceAtom_EvidenceBundle_role") != "evidence_truth":
            raise ValueError("v4_7_11 row SourceAtom role drifted")
        if row.get("SearchView_vector_payload_role") != "candidate_only":
            raise ValueError("v4_7_11 row SearchView role drifted")
        audit = row.get("answer_replay_audit") or {}
        if audit.get("raw_prompt_created") is not False or audit.get("raw_llm_response_created") is not False:
            raise ValueError("v4_7_11 row wrote raw prompt/response payload")
        if audit.get("generated_response_created") is True:
            if audit.get("parsed_final_answer_present") is not True:
                raise ValueError("v4_7_11 generated row missing parsed final answer")
            if audit.get("korean_final_answer") is not True:
                raise ValueError("v4_7_11 generated row missing Korean final answer")
            if audit.get("citation_rendered") is not True:
                raise ValueError("v4_7_11 generated row missing rendered citation")
        else:
            if _clean(row.get("final_answer")) or row.get("rendered_citations"):
                raise ValueError("v4_7_11 fail-closed row carried answer payload")
            if audit.get("parsed_final_answer_present") is True:
                raise ValueError("v4_7_11 fail-closed row claimed parsed final answer")
    if counters.get("noop_or_extractive_generator_used") is not False:
        raise ValueError("v4_7_11 noop/extractive generator flag must stay false")
    silver = report.get("silver_diagnostic_smoke") or {}
    if silver.get("diagnostic_silver_only") is not True:
        raise ValueError("v4_7_11 silver smoke must stay diagnostic_silver_only")
    if silver.get("official_metric_input_rows") != 0 or silver.get("silver_promoted_to_gold_count") != 0:
        raise ValueError("v4_7_11 silver lane promoted or opened official metric")
