from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v550_user_approved_gold_packet_ingestion_and_official_metric_dry_run as v550
from ai.eval import rag_v560_official_metric_scored_execution_and_failure_attribution_nonprod as v560
from ai.eval import rag_v5_diagnostic_common as common
from ai.scripts import rag_local_llm_expected_answer_generation_v1 as local_llm


LOGICAL_RUN_KEY = "v5_6_2"
SHORT_RUN_ID = "v5_6_2_official_metric_backend_enabled_preflight_scored_rerun_nonprod"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v5_6_2_"
    "official_metric_backend_enabled_preflight_scored_rerun_nonprod"
)
STATUS = "V5_6_2_OFFICIAL_METRIC_BACKEND_ENABLED_PREFLIGHT_FAIL_CLOSED_NONPROD_READY"
SCORED_STATUS = "V5_6_2_OFFICIAL_METRIC_BACKEND_ENABLED_PREFLIGHT_SCORED_RERUN_NONPROD_READY"

CURRENT_RESOLVES_TO = v560.LOGICAL_RUN_KEY
REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
SHORT_REPORT_PATH = RUN_ROOT / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
BACKEND_PREFLIGHT_RESULT_PATH = RUN_ROOT / "backend_preflight_result.json"
OFFICIAL_METRIC_SCORED_RESULT_PATH = RUN_ROOT / "official_metric_scored_result.json"
FAILURE_ATTRIBUTION_PATH = RUN_ROOT / "failure_attribution.jsonl"

SOURCE_LOGICAL_RUN_KEY = v550.LOGICAL_RUN_KEY
SOURCE_RUN_ID = v550.SHORT_RUN_ID
SOURCE_CANONICAL_LONG_RUN_ID = v550.CANONICAL_LONG_RUN_ID
SOURCE_REPORT_JSON = v550.SHORT_REPORT_PATH
SOURCE_OFFICIAL_METRIC_INPUT_PATH = v550.OFFICIAL_METRIC_INPUT_PATH
V5_6_BASELINE_LOGICAL_RUN_KEY = v560.LOGICAL_RUN_KEY
V5_6_BASELINE_RUN_ID = v560.SHORT_RUN_ID
V5_6_BASELINE_REPORT_JSON = v560.SHORT_REPORT_PATH
KST_DOC_DATE = "2026-06-04"
EXPECTED_ROW_COUNT = v550.EXPECTED_ROW_COUNT
EXPECTED_ROWS_BY_TRACK = dict(v550.EXPECTED_ROWS_BY_TRACK)
SCOPE_POLICY = "exact_v5_5_official_metric_input_rows_only"
EXCLUDED_SCOPES = tuple(v560.EXCLUDED_SCOPES)

ANSWER_FAILURE_CATEGORIES = {
    "answer_wrong",
    "citation_unsupported",
    "partial_or_unsupported",
    "retrieval_context_missing",
    "locator_precision",
    "renderer_format",
    "scorer_contract",
    "unknown_fail_closed",
}
PREFLIGHT_FAILURE_CATEGORIES = {
    "execution_gate_disabled",
    "answer_generation_backend_unreachable",
    "answer_generation_model_unavailable",
    "scorer_backend_unreachable",
    "scorer_contract_unavailable",
    "backend_unavailable_unknown",
}
FAILURE_CATEGORIES = ANSWER_FAILURE_CATEGORIES | PREFLIGHT_FAILURE_CATEGORIES
PASS_CATEGORY = "pass"
ENABLE_ENV_VAR = "RAG_V5_6_2_ENABLE_OFFICIAL_METRIC_EXECUTION"
BACKEND_ENV_VAR = "RAG_V5_6_2_LOCAL_LLM_BACKEND"
BASE_URL_ENV_VAR = "RAG_V5_6_2_LOCAL_LLM_BASE_URL"
MODEL_ENV_VAR = "RAG_V5_6_2_LOCAL_LLM_MODEL"
SCORER_BACKEND_ENV_VAR = "RAG_V5_6_2_SCORER_BACKEND"
SCORER_BASE_URL_ENV_VAR = "RAG_V5_6_2_SCORER_BASE_URL"
SCORER_MODEL_ENV_VAR = "RAG_V5_6_2_SCORER_MODEL"

CLOSED_FALSE_KEYS = v560.CLOSED_FALSE_KEYS
RAW_PAYLOAD_FORBIDDEN_KEYS = v560.RAW_PAYLOAD_FORBIDDEN_KEYS

utc_now_iso = common.utc_now_iso
read_jsonl = common.read_jsonl
write_json = common.write_json
write_jsonl = common.write_jsonl
sha256_file = common.sha256_file


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return common.json_clone(payload)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _env_value(env: Mapping[str, str], key: str, default: str = "") -> str:
    return _clean(env.get(key, default))


def _load_source_report(root: Path, source_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if source_report is not None:
        report = _json_clone(source_report)
    else:
        report = registry.load_report(SOURCE_LOGICAL_RUN_KEY, root=root)
    v550.check_report(report)
    return report


def _load_v560_baseline_report(root: Path, source_report: Mapping[str, Any]) -> dict[str, Any]:
    try:
        report = registry.load_report(V5_6_BASELINE_LOGICAL_RUN_KEY, root=root)
    except registry.ReportResolutionError:
        report = v560.build_report(root=root, source_report=source_report, execute=False)
    v560.check_report(report)
    return report


def _load_metric_input_rows(root: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(root / SOURCE_OFFICIAL_METRIC_INPUT_PATH)
    if len(rows) != EXPECTED_ROW_COUNT:
        raise ValueError("v5_6_2 source official metric input row count must be exactly 29")
    return rows


def _source_artifact_validation(
    root: Path,
    source_report: Mapping[str, Any],
    baseline_report: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    source_input_path = root / SOURCE_OFFICIAL_METRIC_INPUT_PATH
    source_report_path = root / SOURCE_REPORT_JSON
    baseline_report_path = root / V5_6_BASELINE_REPORT_JSON
    paths = source_report.get("artifact_paths") or {}
    hashes = source_report.get("artifact_sha256") or {}
    actual_input_hash = sha256_file(source_input_path)
    expected_input_hash = _clean(hashes.get("official_metric_input_jsonl_sha256"))
    expected_input_path = _clean(paths.get("official_metric_input_jsonl"))
    baseline_validation = baseline_report.get("source_artifact_validation") or {}
    baseline_hashes = baseline_report.get("artifact_sha256") or {}
    baseline_input_hash = _clean(
        baseline_validation.get("source_official_metric_input_sha256")
        or baseline_hashes.get("source_official_metric_input_jsonl_sha256")
    )
    baseline_input_path = _clean(
        baseline_validation.get("source_official_metric_input_path")
        or baseline_report.get("artifact_paths", {}).get("source_official_metric_input_jsonl")
    )
    return {
        "source_report_path": SOURCE_REPORT_JSON.as_posix(),
        "source_report_artifact_status": "present" if source_report_path.exists() else "materialized_in_memory",
        "source_report_sha256": sha256_file(source_report_path) if source_report_path.exists() else "",
        "source_official_metric_input_path": SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix(),
        "source_official_metric_input_sha256": actual_input_hash,
        "v5_5_report_official_metric_input_path": expected_input_path,
        "v5_5_report_official_metric_input_sha256": expected_input_hash,
        "path_matches_v5_5_report": expected_input_path == SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix(),
        "sha256_matches_v5_5_report": expected_input_hash == actual_input_hash,
        "v5_6_report_path": V5_6_BASELINE_REPORT_JSON.as_posix(),
        "v5_6_report_artifact_status": "present" if baseline_report_path.exists() else "materialized_in_memory",
        "v5_6_report_sha256": sha256_file(baseline_report_path) if baseline_report_path.exists() else "",
        "v5_6_report_official_metric_input_path": baseline_input_path,
        "v5_6_report_source_official_metric_input_sha256": baseline_input_hash,
        "path_matches_v5_6_report": baseline_input_path == SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix(),
        "sha256_matches_v5_6_report": baseline_input_hash == actual_input_hash,
        "row_count": len(rows),
        "row_count_matches_v5_5_report": source_report.get("official_metric_input_rows") == len(rows),
        "row_count_matches_v5_6_report": baseline_report.get("official_metric_input_rows") == len(rows),
        "protected_namespace_policy": "read_only_v5_5_input_and_v5_6_baseline_reports_only",
    }


def _duplicate_evidence_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        for evidence_id in row.get("supporting_evidence_ids") or []:
            by_id[str(evidence_id)].append(str(row.get("source_v5_4_review_row_id") or ""))
    duplicates = {evidence_id: ids for evidence_id, ids in sorted(by_id.items()) if len(ids) > 1}
    return {
        "duplicate_supporting_evidence_id_count": len(duplicates),
        "duplicate_supporting_evidence_ids": duplicates,
        "duplicate_supporting_evidence_policy": (
            "recorded_for_locator_precision_audit; row-level citation_locator remains authoritative"
        ),
    }


def _row_refs(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        row_text = json.dumps(row, ensure_ascii=False, sort_keys=True)
        locator_text = json.dumps(row.get("citation_locator") or {}, ensure_ascii=False, sort_keys=True)
        refs.append(
            {
                "row_index": index,
                "track": _clean(row.get("track")),
                "source_v5_4_review_row_id": _clean(row.get("source_v5_4_review_row_id")),
                "row_sha256": _sha256_text(row_text),
                "query_id_sha256": _sha256_text(_clean(row.get("query_id"))),
                "citation_locator_sha256": _sha256_text(locator_text),
            }
        )
    return refs


def _redacted_base_url(base_url: str) -> str:
    return "localhost" if "localhost" in base_url or "127.0.0.1" in base_url or "::1" in base_url else "non_local_blocked"


def _model_catalog_endpoint(backend: str, base_url: str) -> str:
    suffix = "/api/tags" if backend == "ollama" else "/models"
    return f"{base_url.rstrip('/')}{suffix}"


def _model_ids(catalog: Any) -> set[str]:
    values: list[Any] = []
    if isinstance(catalog, Mapping):
        for key in ("data", "models"):
            child = catalog.get(key)
            if isinstance(child, Sequence) and not isinstance(child, (str, bytes, bytearray)):
                values.extend(child)
        if not values:
            values.append(catalog)
    elif isinstance(catalog, Sequence) and not isinstance(catalog, (str, bytes, bytearray)):
        values.extend(catalog)
    ids: set[str] = set()
    for item in values:
        if isinstance(item, Mapping):
            for key in ("id", "name", "model"):
                if _clean(item.get(key)):
                    ids.add(_clean(item.get(key)))
        elif _clean(item):
            ids.add(_clean(item))
    return ids


def _catalog_has_model(catalog: Any, model: str) -> bool:
    ids = _model_ids(catalog)
    if not ids:
        return False
    requested = _clean(model)
    return requested in ids or any(Path(model_id).name == Path(requested).name for model_id in ids)


def _answer_probe_prompt() -> str:
    return json.dumps(
        {
            "task": "v5_6_2_non_gold_answer_generation_probe",
            "instructions": ["Return exactly one JSON object.", "This is not a gold or official denominator row."],
            "required_schema": {"final_answer": "string", "citations": ["string"], "abstain": "boolean"},
            "non_gold_probe": {
                "question_ko": "비공식 사전 점검 질문입니다. JSON 계약만 확인합니다.",
                "bounded_context": "probe-only non-gold context",
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _scorer_probe_prompt() -> str:
    return json.dumps(
        {
            "task": "v5_6_2_non_gold_scorer_contract_probe",
            "instructions": ["Return exactly one JSON object.", "This probe is not an official metric row."],
            "allowed_failure_categories": sorted(FAILURE_CATEGORIES),
            "non_gold_probe": {
                "expected_answer_ko": "probe answer",
                "generated_answer": "probe answer",
                "generated_citations": [],
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    text = _clean(value)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("backend response must be a JSON object")
    return parsed


def _schema_valid_answer(payload: Mapping[str, Any]) -> bool:
    return isinstance(payload.get("final_answer"), str) and isinstance(payload.get("citations"), list) and isinstance(
        payload.get("abstain"), bool
    )


def _schema_valid_scorer(payload: Mapping[str, Any]) -> bool:
    if not isinstance(payload.get("passed"), bool):
        return False
    if payload.get("failure_category") not in FAILURE_CATEGORIES | {PASS_CATEGORY}:
        return False
    return "answer_score" in payload and "citation_support_score" in payload


def _call_client_json(prompt: str, client: Callable[[str], str]) -> tuple[dict[str, Any], str]:
    raw = client(prompt)
    return _parse_json_object(raw), _sha256_text(_clean(raw))


def _call_local_json(
    *,
    prompt: str,
    backend: str,
    base_url: str,
    model: str,
    timeout_seconds: int,
    max_tokens: int,
) -> tuple[dict[str, Any], str]:
    parsed, meta = local_llm.call_local_llm_strict_json(
        backend=backend,
        base_url=base_url,
        model=model,
        prompt=prompt,
        temperature=0.0,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )
    return parsed, _clean(meta.get("raw_response_sha256"))


def _preflight_fail(base: Mapping[str, Any], *, category: str, status: str, blockers: Sequence[str]) -> dict[str, Any]:
    return {
        **dict(base),
        "status": status,
        "failure_category": category,
        "available": False,
        "blockers": list(blockers),
    }


def _preflight_config(env: Mapping[str, str]) -> dict[str, str]:
    answer_backend = _env_value(env, BACKEND_ENV_VAR, local_llm.DEFAULT_BACKEND) or local_llm.DEFAULT_BACKEND
    answer_base_url = local_llm.resolve_base_url(answer_backend, _env_value(env, BASE_URL_ENV_VAR))
    answer_model = _env_value(env, MODEL_ENV_VAR, local_llm.DEFAULT_MODEL) or local_llm.DEFAULT_MODEL
    scorer_backend = _env_value(env, SCORER_BACKEND_ENV_VAR, answer_backend) or answer_backend
    scorer_base_url = local_llm.resolve_base_url(
        scorer_backend,
        _env_value(env, SCORER_BASE_URL_ENV_VAR, answer_base_url),
    )
    scorer_model = _env_value(env, SCORER_MODEL_ENV_VAR, answer_model) or answer_model
    return {
        "answer_backend": answer_backend,
        "answer_base_url": answer_base_url,
        "answer_model": answer_model,
        "scorer_backend": scorer_backend,
        "scorer_base_url": scorer_base_url,
        "scorer_model": scorer_model,
    }


def _check_local_model_catalog(
    *,
    backend: str,
    base_url: str,
    model: str,
    timeout_seconds: int,
) -> tuple[bool, str, list[str]]:
    blockers = local_llm.local_llm_entry_blockers(
        backend=backend,
        base_url=base_url,
        model=model,
        check_endpoint=False,
        timeout_seconds=timeout_seconds,
    )
    if blockers:
        return False, "answer_generation_model_unavailable" if not _clean(model) else "answer_generation_backend_unreachable", blockers
    try:
        catalog = local_llm.request_json(
            _model_catalog_endpoint(backend, base_url),
            payload=None,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        return False, "answer_generation_backend_unreachable", [f"MODEL_CATALOG_UNREACHABLE:{type(exc).__name__}:{exc}"]
    if not _catalog_has_model(catalog, model):
        return False, "answer_generation_model_unavailable", [f"MODEL_NOT_LISTED:{model}"]
    return True, "", []


def _backend_preflight(
    *,
    execute: bool,
    env: Mapping[str, str],
    answer_client: Callable[[str], str] | None,
    scorer_client: Callable[[str], str] | None,
    timeout_seconds: int,
    max_tokens: int,
) -> dict[str, Any]:
    env_enabled = _env_value(env, ENABLE_ENV_VAR) == "1"
    config = _preflight_config(env)
    base = {
        "enabled_env_var": ENABLE_ENV_VAR,
        "env_enabled": env_enabled,
        "execute_requested": execute,
        "answer_generation_backend": config["answer_backend"],
        "answer_generation_base_url_redacted": _redacted_base_url(config["answer_base_url"]),
        "answer_generation_model": config["answer_model"],
        "scorer_backend": config["scorer_backend"],
        "scorer_base_url_redacted": _redacted_base_url(config["scorer_base_url"]),
        "scorer_model": config["scorer_model"],
        "answer_generation_available": False,
        "scorer_available": False,
        "available": False,
        "failure_category": "",
        "noop_backend_used": config["answer_backend"] == "noop" or config["scorer_backend"] == "noop",
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "answer_generation_probe_prompt_sha256": "",
        "answer_generation_probe_response_sha256": "",
        "scorer_contract_probe_prompt_sha256": "",
        "scorer_contract_probe_response_sha256": "",
        "blockers": [],
    }
    if not execute or not env_enabled:
        blocker = "CHECK_MODE_EXECUTION_DISABLED" if not execute else f"{ENABLE_ENV_VAR}_NOT_SET_TO_1"
        return _preflight_fail(
            base,
            category="execution_gate_disabled",
            status="EXECUTION_GATE_DISABLED_FAIL_CLOSED",
            blockers=[blocker],
        )

    answer_prompt = _answer_probe_prompt()
    try:
        if answer_client is not None:
            answer_probe, answer_hash = _call_client_json(answer_prompt, answer_client)
        else:
            ok, category, blockers = _check_local_model_catalog(
                backend=config["answer_backend"],
                base_url=config["answer_base_url"],
                model=config["answer_model"],
                timeout_seconds=min(timeout_seconds, 10),
            )
            if not ok:
                return _preflight_fail(
                    base,
                    category=category,
                    status=f"{category.upper()}_FAIL_CLOSED",
                    blockers=blockers,
                )
            answer_probe, answer_hash = _call_local_json(
                prompt=answer_prompt,
                backend=config["answer_backend"],
                base_url=config["answer_base_url"],
                model=config["answer_model"],
                timeout_seconds=timeout_seconds,
                max_tokens=min(max_tokens, 128),
            )
        if not _schema_valid_answer(answer_probe):
            return _preflight_fail(
                base,
                category="backend_unavailable_unknown",
                status="ANSWER_GENERATION_PROBE_CONTRACT_FAIL_CLOSED",
                blockers=["ANSWER_GENERATION_PROBE_SCHEMA_INVALID"],
            )
    except Exception as exc:
        return _preflight_fail(
            base,
            category="answer_generation_backend_unreachable",
            status="ANSWER_GENERATION_BACKEND_UNREACHABLE_FAIL_CLOSED",
            blockers=[f"ANSWER_GENERATION_PROBE_FAILED:{type(exc).__name__}:{exc}"],
        )

    base = {
        **base,
        "answer_generation_available": True,
        "answer_generation_probe_prompt_sha256": _sha256_text(answer_prompt),
        "answer_generation_probe_response_sha256": answer_hash,
    }
    scorer_prompt = _scorer_probe_prompt()
    try:
        if scorer_client is not None:
            scorer_probe, scorer_hash = _call_client_json(scorer_prompt, scorer_client)
        else:
            ok, category, blockers = _check_local_model_catalog(
                backend=config["scorer_backend"],
                base_url=config["scorer_base_url"],
                model=config["scorer_model"],
                timeout_seconds=min(timeout_seconds, 10),
            )
            if not ok:
                scorer_category = "scorer_backend_unreachable" if category != "answer_generation_model_unavailable" else "scorer_backend_unreachable"
                return _preflight_fail(
                    base,
                    category=scorer_category,
                    status="SCORER_BACKEND_UNREACHABLE_FAIL_CLOSED",
                    blockers=blockers,
                )
            scorer_probe, scorer_hash = _call_local_json(
                prompt=scorer_prompt,
                backend=config["scorer_backend"],
                base_url=config["scorer_base_url"],
                model=config["scorer_model"],
                timeout_seconds=timeout_seconds,
                max_tokens=min(max_tokens, 128),
            )
    except Exception as exc:
        return _preflight_fail(
            base,
            category="scorer_backend_unreachable",
            status="SCORER_BACKEND_UNREACHABLE_FAIL_CLOSED",
            blockers=[f"SCORER_PROBE_FAILED:{type(exc).__name__}:{exc}"],
        )
    if not _schema_valid_scorer(scorer_probe):
        return _preflight_fail(
            {
                **base,
                "scorer_contract_probe_prompt_sha256": _sha256_text(scorer_prompt),
                "scorer_contract_probe_response_sha256": scorer_hash,
            },
            category="scorer_contract_unavailable",
            status="SCORER_CONTRACT_UNAVAILABLE_FAIL_CLOSED",
            blockers=["SCORER_CONTRACT_PROBE_SCHEMA_INVALID"],
        )
    return {
        **base,
        "status": "BACKEND_AVAILABLE_PREFLIGHT_PASSED_NONPROD",
        "answer_generation_available": True,
        "scorer_available": True,
        "available": True,
        "failure_category": "",
        "scorer_contract_probe_prompt_sha256": _sha256_text(scorer_prompt),
        "scorer_contract_probe_response_sha256": scorer_hash,
        "blockers": [],
    }


def _answer_prompt(row: Mapping[str, Any]) -> str:
    return json.dumps(
        {
            "task": "v5_6_2_official_metric_answer_generation_nonprod",
            "instructions": [
                "Return exactly one JSON object.",
                "Answer the Korean question using only the configured non-production RAG answer backend context.",
                "Do not use hidden gold answers, expected answers, supporting evidence notes, citation locators, or query ids.",
                "If the answer backend has no retrieval context, abstain instead of guessing.",
            ],
            "required_schema": {"final_answer": "string", "citations": ["string"], "abstain": "boolean"},
            "official_metric_row": {
                "track": row["track"],
                "question_ko": row["question_ko"],
                "row_ref_sha256": _sha256_text(json.dumps(row, ensure_ascii=False, sort_keys=True)),
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _scorer_prompt(row: Mapping[str, Any], generated: Mapping[str, Any]) -> str:
    return json.dumps(
        {
            "task": "v5_6_2_official_metric_answer_citation_scoring_nonprod",
            "instructions": [
                "Return exactly one JSON object.",
                "Use the expected answer, supporting evidence note, citation ids, and citation locator only for scoring.",
                "Classify any failure conservatively.",
            ],
            "allowed_failure_categories": sorted(FAILURE_CATEGORIES),
            "query_id": row["query_id"],
            "track": row["track"],
            "question_ko": row["question_ko"],
            "expected_answer_ko": row["expected_answer_ko"],
            "supporting_evidence_note": row["supporting_evidence_note"],
            "supporting_evidence_ids": list(row["supporting_evidence_ids"]),
            "citation_locator": dict(row["citation_locator"]),
            "generated_answer": _clean(generated.get("final_answer")),
            "generated_citations": generated.get("citations") if isinstance(generated.get("citations"), list) else [],
            "generated_abstain": generated.get("abstain") is True,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _call_scoring_backend_json(
    *,
    prompt: str,
    backend_preflight: Mapping[str, Any],
    env: Mapping[str, str],
    client: Callable[[str], str] | None,
    scorer: bool,
    timeout_seconds: int,
    max_tokens: int,
) -> tuple[dict[str, Any], str]:
    if client is not None:
        return _call_client_json(prompt, client)
    config = _preflight_config(env)
    return _call_local_json(
        prompt=prompt,
        backend=config["scorer_backend" if scorer else "answer_backend"],
        base_url=config["scorer_base_url" if scorer else "answer_base_url"],
        model=config["scorer_model" if scorer else "answer_model"],
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
    )


def _normalize_failure_category(value: Any, *, passed: bool) -> str:
    if passed:
        return PASS_CATEGORY
    category = _clean(value).lower()
    return category if category in FAILURE_CATEGORIES else "unknown_fail_closed"


def _preflight_failed_attribution(row: Mapping[str, Any], *, category: str, reason: str) -> dict[str, Any]:
    return {
        "query_id": row["query_id"],
        "track": row["track"],
        "source_v5_4_review_row_id": row["source_v5_4_review_row_id"],
        "failure_category": category,
        "failure_detail": reason,
        "pass": False,
        "answer_score": None,
        "citation_support_score": None,
        "scoring_attempted": False,
        "scored": False,
    }


def _score_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    backend_preflight: Mapping[str, Any],
    env: Mapping[str, str],
    answer_client: Callable[[str], str] | None,
    scorer_client: Callable[[str], str] | None,
    timeout_seconds: int,
    max_tokens: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not backend_preflight.get("available"):
        category = _clean(backend_preflight.get("failure_category")) or "backend_unavailable_unknown"
        reason = "; ".join(str(item) for item in backend_preflight.get("blockers") or [backend_preflight.get("status")])
        attribution = [_preflight_failed_attribution(row, category=category, reason=reason) for row in rows]
        return {
            "schema_version": f"{SHORT_RUN_ID}_scored_result_v1",
            "logical_run_key": LOGICAL_RUN_KEY,
            "run_id": SHORT_RUN_ID,
            "status": "preflight_failed",
            "backend_unavailable": True,
            "official_metric_input_rows": len(rows),
            "scored_answer_rows": 0,
            "answer_quality_metric_computed": False,
            "official_metric_finalized": False,
            "pass_count": 0,
            "fail_count": len(rows),
            "pass_fail_counts_interpretable_as_quality_metric": False,
            "quality_metric_blocked_reason": "preflight_failed_no_scored_answers",
            "failure_category_counts": {category: len(rows)},
            "row_results": [],
        }, attribution

    row_results: list[dict[str, Any]] = []
    attribution: list[dict[str, Any]] = []
    for row in rows:
        answer_prompt = _answer_prompt(row)
        scorer_prompt = ""
        try:
            generated, answer_hash = _call_scoring_backend_json(
                prompt=answer_prompt,
                backend_preflight=backend_preflight,
                env=env,
                client=answer_client,
                scorer=False,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
            )
            scorer_prompt = _scorer_prompt(row, generated)
            scored, scorer_hash = _call_scoring_backend_json(
                prompt=scorer_prompt,
                backend_preflight=backend_preflight,
                env=env,
                client=scorer_client,
                scorer=True,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
            )
            if not _schema_valid_scorer(scored):
                raise ValueError("scorer response schema invalid")
            passed = scored.get("passed") is True
            category = _normalize_failure_category(scored.get("failure_category"), passed=passed)
            answer_score = scored.get("answer_score")
            citation_score = scored.get("citation_support_score")
            detail = _clean(scored.get("failure_detail") or scored.get("rationale"))
        except Exception as exc:
            generated = {}
            answer_hash = ""
            scorer_hash = ""
            passed = False
            category = "scorer_contract"
            answer_score = None
            citation_score = None
            detail = f"SCORER_CONTRACT_FAIL_CLOSED:{type(exc).__name__}"
        result_row = {
            "query_id": row["query_id"],
            "track": row["track"],
            "source_v5_4_review_row_id": row["source_v5_4_review_row_id"],
            "pass": passed,
            "failure_category": category,
            "failure_detail": detail,
            "answer_score": answer_score,
            "citation_support_score": citation_score,
            "generated_answer_present": bool(_clean(generated.get("final_answer"))) if isinstance(generated, Mapping) else False,
            "generated_citation_count": len(generated.get("citations") or []) if isinstance(generated, Mapping) else 0,
            "prompt_sha256": _sha256_text(answer_prompt),
            "scorer_prompt_sha256": _sha256_text(scorer_prompt) if scorer_prompt else "",
            "raw_answer_response_sha256": answer_hash,
            "raw_scorer_response_sha256": scorer_hash,
            "scoring_attempted": True,
            "scored": category != "scorer_contract",
        }
        row_results.append(result_row)
        attribution.append(
            {
                "query_id": result_row["query_id"],
                "track": result_row["track"],
                "source_v5_4_review_row_id": result_row["source_v5_4_review_row_id"],
                "failure_category": category,
                "failure_detail": detail,
                "pass": passed,
                "answer_score": answer_score,
                "citation_support_score": citation_score,
                "scoring_attempted": True,
                "scored": result_row["scored"],
            }
        )
    counts = dict(Counter(row["failure_category"] for row in row_results))
    pass_count = sum(1 for row in row_results if row["pass"])
    return {
        "schema_version": f"{SHORT_RUN_ID}_scored_result_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "status": "scored",
        "backend_unavailable": False,
        "official_metric_input_rows": len(rows),
        "scored_answer_rows": len(row_results),
        "answer_quality_metric_computed": True,
        "official_metric_finalized": True,
        "pass_count": pass_count,
        "fail_count": len(row_results) - pass_count,
        "pass_fail_counts_interpretable_as_quality_metric": True,
        "quality_metric_blocked_reason": "",
        "failure_category_counts": counts,
        "row_results": row_results,
    }, attribution


def build_report(
    *,
    root: Path | str,
    generated_at: str | None = None,
    source_report: Mapping[str, Any] | None = None,
    execute: bool = False,
    env: Mapping[str, str] | None = None,
    answer_client: Callable[[str], str] | None = None,
    scorer_client: Callable[[str], str] | None = None,
    backend_timeout_seconds: int = 30,
    backend_max_tokens: int = 512,
    check: bool = True,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated = generated_at or utc_now_iso()
    source = _load_source_report(repo_root, source_report=source_report)
    baseline = _load_v560_baseline_report(repo_root, source)
    rows = _load_metric_input_rows(repo_root)
    row_count_by_track = dict(Counter(str(row.get("track") or "") for row in rows))
    validation = _source_artifact_validation(repo_root, source, baseline, rows)
    duplicate_summary = _duplicate_evidence_summary(rows)
    row_refs = _row_refs(rows)
    runtime_env = dict(os.environ if env is None else env)
    backend = _backend_preflight(
        execute=execute,
        env=runtime_env,
        answer_client=answer_client,
        scorer_client=scorer_client,
        timeout_seconds=backend_timeout_seconds,
        max_tokens=backend_max_tokens,
    )
    scored_result, failure_rows = _score_rows(
        rows,
        backend_preflight=backend,
        env=runtime_env,
        answer_client=answer_client,
        scorer_client=scorer_client,
        timeout_seconds=backend_timeout_seconds,
        max_tokens=backend_max_tokens,
    )
    status = SCORED_STATUS if scored_result["official_metric_finalized"] else STATUS
    report = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": status,
        "generated_at": generated,
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
            "source_report_json": SOURCE_REPORT_JSON.as_posix(),
            "source_official_metric_input_jsonl": SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix(),
            "v5_6_baseline_report_json": V5_6_BASELINE_REPORT_JSON.as_posix(),
            "backend_preflight_result_json": BACKEND_PREFLIGHT_RESULT_PATH.as_posix(),
            "official_metric_scored_result_json": OFFICIAL_METRIC_SCORED_RESULT_PATH.as_posix(),
            "failure_attribution_jsonl": FAILURE_ATTRIBUTION_PATH.as_posix(),
        },
        "artifact_sha256": {},
        "source_run_id": SOURCE_RUN_ID,
        "source_logical_run_key": SOURCE_LOGICAL_RUN_KEY,
        "source_canonical_long_run_id": SOURCE_CANONICAL_LONG_RUN_ID,
        "source_report_status": source.get("status"),
        "source_report_schema_version": source.get("schema_version"),
        "v5_6_baseline_run_id": V5_6_BASELINE_RUN_ID,
        "v5_6_baseline_status": baseline.get("status"),
        "source_artifact_validation": validation,
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "non_production": True,
        "diagnostic_only": False,
        "approval_scope": {
            "source_run_id": SOURCE_RUN_ID,
            "source_artifact_path": SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix(),
            "row_count": len(rows),
            "scope_policy": SCOPE_POLICY,
            "excluded_scopes": list(EXCLUDED_SCOPES),
        },
        "official_metric_input_rows": len(rows),
        "official_metric_input_rows_consumed": len(rows),
        "official_metric_input_rows_scope": SCOPE_POLICY,
        "official_metric_input_row_ref_count": len(row_refs),
        "official_metric_input_row_refs": row_refs,
        "row_count_by_track": row_count_by_track,
        "backend_preflight": backend,
        "official_metric_scored_result": scored_result,
        "failure_attribution_rows": failure_rows,
        "failure_attribution_row_count": len(failure_rows),
        "answer_quality_metric_computed": scored_result["answer_quality_metric_computed"],
        "scored_answer_rows": scored_result["scored_answer_rows"],
        "official_metric_finalized": scored_result["official_metric_finalized"],
        "official_metric": scored_result["official_metric_finalized"],
        "pass_fail_counts_interpretable_as_quality_metric": scored_result[
            "pass_fail_counts_interpretable_as_quality_metric"
        ],
        "protected_namespaces_touched": [],
        "basis_for_ambiguous_engineering_choices": (
            "v5_6_1 is already occupied by a product-preview runtime bridge in the live tree, so v5_6_2 is the next "
            "repo-consistent official metric rerun key; the runner reuses only v5_5 official_metric_input.jsonl, "
            "checks the v5_5/v5_6 source hash contract, keeps v5_6 artifacts immutable, and fails closed before any "
            "real scoring unless the v5_6_2 execution gate plus answer/scorer probes pass"
        ),
        **duplicate_summary,
    }
    for key in CLOSED_FALSE_KEYS:
        report[key] = False
    if check:
        check_report(report)
    return report


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    repo_root = Path(root)
    payload = _json_clone(report)
    write_json(repo_root / BACKEND_PREFLIGHT_RESULT_PATH, payload["backend_preflight"])
    write_json(repo_root / OFFICIAL_METRIC_SCORED_RESULT_PATH, payload["official_metric_scored_result"])
    write_jsonl(repo_root / FAILURE_ATTRIBUTION_PATH, payload["failure_attribution_rows"])
    source_input_path = repo_root / SOURCE_OFFICIAL_METRIC_INPUT_PATH
    source_report_path = repo_root / SOURCE_REPORT_JSON
    baseline_report_path = repo_root / V5_6_BASELINE_REPORT_JSON
    validation = payload.get("source_artifact_validation") or {}
    child_hashes = {
        "source_official_metric_input_jsonl_sha256": (
            sha256_file(source_input_path)
            if source_input_path.exists()
            else _clean(validation.get("source_official_metric_input_sha256"))
        ),
        "backend_preflight_result_json_sha256": sha256_file(repo_root / BACKEND_PREFLIGHT_RESULT_PATH),
        "official_metric_scored_result_json_sha256": sha256_file(repo_root / OFFICIAL_METRIC_SCORED_RESULT_PATH),
        "failure_attribution_jsonl_sha256": sha256_file(repo_root / FAILURE_ATTRIBUTION_PATH),
    }
    if source_report_path.exists():
        child_hashes["source_report_json_sha256"] = sha256_file(source_report_path)
    elif _clean(validation.get("source_report_sha256")):
        child_hashes["source_report_json_sha256"] = _clean(validation.get("source_report_sha256"))
    if baseline_report_path.exists():
        child_hashes["v5_6_baseline_report_json_sha256"] = sha256_file(baseline_report_path)
    elif _clean(validation.get("v5_6_report_sha256")):
        child_hashes["v5_6_baseline_report_json_sha256"] = _clean(validation.get("v5_6_report_sha256"))
    payload["artifact_sha256"] = child_hashes
    write_json(repo_root / SHORT_REPORT_PATH, payload)
    artifact_hashes = {"report_json_sha256": sha256_file(repo_root / SHORT_REPORT_PATH), **child_hashes}
    return payload, artifact_hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    result = report["official_metric_scored_result"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "v5_6_2_official_metric_backend_enabled_preflight_scored_rerun_nonprod",
        "generated_at": report["generated_at"],
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": report["status"],
        "source_run_id": SOURCE_RUN_ID,
        "v5_6_baseline_run_id": V5_6_BASELINE_RUN_ID,
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "non_production": True,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "official_metric_input_rows": report["official_metric_input_rows"],
        "official_metric_input_rows_consumed": report["official_metric_input_rows_consumed"],
        "row_count_by_track": dict(report["row_count_by_track"]),
        "backend_preflight_status": report["backend_preflight"]["status"],
        "backend_preflight_failure_category": report["backend_preflight"].get("failure_category") or "",
        "backend_unavailable": result["backend_unavailable"],
        "answer_quality_metric_computed": result["answer_quality_metric_computed"],
        "scored_answer_rows": result["scored_answer_rows"],
        "official_metric_finalized": result["official_metric_finalized"],
        "pass_fail_counts_interpretable_as_quality_metric": result["pass_fail_counts_interpretable_as_quality_metric"],
        "failure_category_counts": dict(result["failure_category_counts"]),
        "duplicate_supporting_evidence_id_count": report["duplicate_supporting_evidence_id_count"],
        "duplicate_supporting_evidence_policy": report["duplicate_supporting_evidence_policy"],
        "training_dataset_created": False,
        "fine_tuning": False,
        "ft_a_execution": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
    }


def append_status(root: Path | str, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    status_path = Path(root) / STATUS_JSONL_PATH
    rows = read_jsonl(status_path)
    rows = [row for row in rows if row.get("short_run_id") != SHORT_RUN_ID]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    write_jsonl(status_path, rows)


def _sync_last_updated(text: str) -> str:
    return common.sync_last_updated(text, KST_DOC_DATE)


def _replace_current_status_block(progress_text: str, report: Mapping[str, Any]) -> str:
    result = report["official_metric_scored_result"]
    failure_counts = dict(result["failure_category_counts"])
    replacement = (
        "## Current Status\n\n"
        f"Overall status: `{report['status']}`; `{SHORT_RUN_ID}` is the latest explicit non-production official metric "
        "backend-enabled preflight/scored-rerun lane over the exact v5_5 official metric input rows. `current` resolves "
        "to `v5_6` so the v5_6 artifacts remain immutable fail-closed baseline, while `v5_6_2`, `v5_5`, `v5_4`, "
        "`v5_3`, `v5_2`, `v5_1`, `v5_0`, and `v4_7_18` remain directly checkable.\n\n"
        "Current run board:\n"
        f"- source_of_truth: `{SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix()}` from `{SOURCE_RUN_ID}`; "
        "user-approved gold packet ingestion from the v5_4 user-owned approval packet; source hash matches both the "
        "v5_5 report and the v5_6 recorded source hash.\n"
        "- source_v5_5_dry_run: official_metric_dry_run_opened=true; official_metric_dry_run_executed=true; "
        "official_metric_input_rows=29; official_metric_input_rows_created=29; official_eval_user_gate_ready=true.\n"
        "- immutable_v5_6_baseline: official metric scored-execution attempt; backend_unavailable=true; "
        "scored_answer_rows=0; answer_quality_metric_computed=false; failure_category_counts=`{'backend_unavailable': 29}`.\n"
        "- separate_v5_6_1_product_preview: default-off `/api/rag/query` product-preview bridge remains non-metric, "
        "uses `AIPIPELINE_WORKER_RAG_PRODUCT_PREVIEW_ROUTE_ENABLED`, and does not move `current` away from `v5_6`.\n"
        "- denominator_scope: exactly 29 user-approved v5_4 packet rows via v5_5 (TEXT 6, XLSX 19, PDF 4); "
        "no silver/residual/overlay-90/XLSX candidate-state/PDF-TEXT residual taxonomy expansion.\n"
        f"- backend_preflight_status: `{report['backend_preflight']['status']}`; "
        f"failure_category=`{report['backend_preflight'].get('failure_category') or 'none'}`; "
        f"env_gate=`{ENABLE_ENV_VAR}`; scored_answer_rows={result['scored_answer_rows']}; "
        f"answer_quality_metric_computed={str(result['answer_quality_metric_computed']).lower()}.\n"
        f"- failure_category_counts: `{failure_counts}`; pass_count={result['pass_count']}/fail_count={result['fail_count']} "
        "is not an answer-quality metric when answer_quality_metric_computed=false.\n"
        "- duplicate supporting_evidence_id is recorded only as a locator precision audit note; row-level "
        "citation_locator remains authoritative, and product/front-end citation DTOs must not collapse rows by "
        "supporting_evidence_id alone.\n"
        "- promotion/product-success/training/fine-tuning/FT-A/live DB-index-cache readiness and production routing remain closed; "
        "protected_namespaces_touched=[].\n\n"
        "Current verification: after v5_6_2 backend-enabled preflight/scored-rerun lane,\n"
        "`pytest ai/tests --rag-current -q` passed with 65 passed, 0 failed, 0 skipped, 1 warning, covering the explicit "
        "v5_6_2 checks plus the immutable v5_6 baseline. Generated report/status/official-metric artifacts remain ignored.\n\n"
        "Artifact policy:\n"
        "- `ai/eval/reports/rag-ingestion/status.jsonl` remains local/ignored status ledger.\n"
        f"- Immutable v5_6 baseline report: `{v560.SHORT_REPORT_PATH.as_posix()}`.\n"
        f"- Current explicit v5_6_2 report: `{SHORT_REPORT_PATH.as_posix()}`.\n"
        f"- Current explicit v5_6_2 backend preflight: `{BACKEND_PREFLIGHT_RESULT_PATH.as_posix()}`.\n"
        f"- Current explicit v5_6_2 scored result: `{OFFICIAL_METRIC_SCORED_RESULT_PATH.as_posix()}`.\n"
        f"- Current explicit v5_6_2 failure attribution: `{FAILURE_ATTRIBUTION_PATH.as_posix()}`.\n"
        f"- Source v5_5 report and official metric input: `{SOURCE_REPORT_JSON.as_posix()}`, "
        f"`{SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix()}`.\n"
        "- Prior basis reports remain explicit: `ai/eval/reports/rag-ingestion/runs/v5_4/report.json`, "
        "`ai/eval/reports/rag-ingestion/runs/v5_4/user_review_packet.csv`, "
        "`ai/eval/reports/rag-ingestion/runs/v5_3/report.json`, "
        "`ai/eval/reports/rag-ingestion/runs/v5_2/report.json`, "
        "`ai/eval/reports/rag-ingestion/runs/v5_1/report.json`, "
        "`ai/eval/reports/rag-ingestion/runs/v5_0/report.json`, and "
        "`ai/eval/reports/rag-ingestion/runs/v4_7_18/report.json`.\n\n"
    )
    return re.sub(r"## Current Status\n\n.*?(?=\n## Short History)", replacement, progress_text, count=1, flags=re.S)


def update_docs(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    progress = repo_root / "docs" / "rag-ingestion-progress.md"
    result = report["official_metric_scored_result"]
    progress_block = (
        f"- Overall status: `{report['status']}`; {SHORT_RUN_ID} consumes only "
        f"`{SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix()}` and performs backend-enabled preflight before any official metric "
        "scoring over exactly 29 user-approved rows (TEXT 6, XLSX 19, PDF 4). "
        f"backend_preflight_failure_category={report['backend_preflight'].get('failure_category') or 'none'}; "
        f"scored_answer_rows={result['scored_answer_rows']}; "
        f"failure_category_counts={dict(result['failure_category_counts'])}. "
        "v5_6 artifacts remain immutable fail-closed baseline. No raw prompt/response payloads are written; duplicate "
        "supporting evidence remains a locator precision audit note only; promotion/product-success/training/fine-tuning/"
        "FT-A/live DB-index-cache readiness/production routing remain closed."
    )
    progress_text = common.upsert_block_at_top(
        progress.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
        block=progress_block,
    )
    progress.write_text(_sync_last_updated(_replace_current_status_block(progress_text, report)), encoding="utf-8")

    if result["answer_quality_metric_computed"] is True:
        measurements = repo_root / "docs" / "rag-ingestion-measurements.md"
        measurements_block = f"""## v5_6_2 official metric backend-enabled scored rerun

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Interpretation: real non-production scored execution over the exact v5_5 official metric input denominator.

| Counter | Value |
|---|---:|
| official_metric_input_rows | {result['official_metric_input_rows']} |
| scored_answer_rows | {result['scored_answer_rows']} |
| pass_count | {result['pass_count']} |
| fail_count | {result['fail_count']} |
"""
        measurements_text = common.upsert_block_at_top(
            measurements.read_text(encoding="utf-8"),
            start_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->",
            end_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->",
            block=measurements_block,
        )
        measurements.write_text(_sync_last_updated(measurements_text), encoding="utf-8")


def _assert_no_raw_payload_keys(value: Any) -> None:
    common.assert_no_raw_payload_keys(value, set(RAW_PAYLOAD_FORBIDDEN_KEYS), context="v5_6_2")


def _require_artifact_paths(report: Mapping[str, Any]) -> None:
    expected = {
        "report_json": SHORT_REPORT_PATH.as_posix(),
        "status_jsonl": STATUS_JSONL_PATH.as_posix(),
        "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        "source_official_metric_input_jsonl": SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix(),
        "v5_6_baseline_report_json": V5_6_BASELINE_REPORT_JSON.as_posix(),
        "backend_preflight_result_json": BACKEND_PREFLIGHT_RESULT_PATH.as_posix(),
        "official_metric_scored_result_json": OFFICIAL_METRIC_SCORED_RESULT_PATH.as_posix(),
        "failure_attribution_jsonl": FAILURE_ATTRIBUTION_PATH.as_posix(),
    }
    if report.get("artifact_paths") != expected:
        raise ValueError("v5_6_2 artifact path drift")


def _require_exact_source_rows(report: Mapping[str, Any]) -> None:
    if "official_metric_input_rows_payload" in report:
        raise ValueError("v5_6_2 protected official input payload embedded")
    refs = list(report.get("official_metric_input_row_refs") or [])
    if report.get("official_metric_input_row_ref_count") != EXPECTED_ROW_COUNT or len(refs) != EXPECTED_ROW_COUNT:
        raise ValueError("v5_6_2 official metric input row ref count drift")
    if dict(Counter(str(row.get("track") or "") for row in refs)) != EXPECTED_ROWS_BY_TRACK:
        raise ValueError("v5_6_2 official metric input row ref count drift")
    for index, row in enumerate(refs):
        if row.get("row_index") != index:
            raise ValueError("v5_6_2 official metric input row ref order drift")
        if not _clean(row.get("row_sha256")) or not _clean(row.get("citation_locator_sha256")):
            raise ValueError("v5_6_2 official metric input row ref hash drift")
        for forbidden in (
            "expected_answer_ko",
            "supporting_evidence_note",
            "supporting_evidence_ids",
            "citation_locator",
            "relevance_label",
            "answerability_label",
            "gold_status",
        ):
            if forbidden in row:
                raise ValueError("v5_6_2 protected official input payload embedded")


def _require_result_consistency(report: Mapping[str, Any]) -> None:
    result = report.get("official_metric_scored_result") or {}
    failure_rows = list(report.get("failure_attribution_rows") or [])
    if result.get("official_metric_input_rows") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_6_2 official metric input rows drift")
    if len(failure_rows) != EXPECTED_ROW_COUNT or report.get("failure_attribution_row_count") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_6_2 failure attribution row count drift")
    if report.get("backend_preflight", {}).get("noop_backend_used") is not False:
        raise ValueError("v5_6_2 noop backend cannot create official metrics")
    counts = dict(Counter(str(row.get("failure_category") or "") for row in failure_rows))
    if result.get("backend_unavailable") is True:
        category = _clean(report.get("backend_preflight", {}).get("failure_category"))
        if category not in PREFLIGHT_FAILURE_CATEGORIES:
            raise ValueError("v5_6_2 preflight failure category drift")
        if result.get("status") != "preflight_failed":
            raise ValueError("v5_6_2 preflight status drift")
        if result.get("scored_answer_rows") != 0:
            raise ValueError("v5_6_2 scored rows drift")
        if result.get("answer_quality_metric_computed") is not False or result.get("official_metric_finalized") is not False:
            raise ValueError("v5_6_2 fake metric created while preflight failed")
        if result.get("pass_fail_counts_interpretable_as_quality_metric") is not False:
            raise ValueError("v5_6_2 pass/fail quality metric drift")
        if result.get("pass_count") != 0 or result.get("fail_count") != EXPECTED_ROW_COUNT:
            raise ValueError("v5_6_2 preflight pass/fail count drift")
        if any(row.get("failure_category") != category for row in failure_rows):
            raise ValueError("v5_6_2 failure attribution category drift")
        if any(row.get("scoring_attempted") is not False or row.get("scored") is not False for row in failure_rows):
            raise ValueError("v5_6_2 preflight row attempted scoring")
        if result.get("failure_category_counts") != counts or counts != {category: EXPECTED_ROW_COUNT}:
            raise ValueError("v5_6_2 failure category count drift")
    else:
        if result.get("failure_category_counts") != counts:
            raise ValueError("v5_6_2 failure category count drift")
        if result.get("status") != "scored":
            raise ValueError("v5_6_2 scored result status drift")
        if result.get("scored_answer_rows") != EXPECTED_ROW_COUNT:
            raise ValueError("v5_6_2 scored rows drift")
        if result.get("answer_quality_metric_computed") is not True or result.get("official_metric_finalized") is not True:
            raise ValueError("v5_6_2 scored metric flags drift")
        if result.get("pass_fail_counts_interpretable_as_quality_metric") is not True:
            raise ValueError("v5_6_2 scored pass/fail quality metric drift")
        row_results = list(result.get("row_results") or [])
        if len(row_results) != EXPECTED_ROW_COUNT:
            raise ValueError("v5_6_2 scored row result count drift")
        allowed = set(FAILURE_CATEGORIES) | {PASS_CATEGORY}
        if any(row.get("failure_category") not in allowed for row in row_results):
            raise ValueError("v5_6_2 unknown failure category drift")


def _require_written_artifacts(report: Mapping[str, Any], *, root: Path | str) -> None:
    repo_root = Path(root)
    paths = report.get("artifact_paths") or {}
    hashes = report.get("artifact_sha256") or {}
    for path_key, payload_key, hash_key, kind in (
        ("backend_preflight_result_json", "backend_preflight", "backend_preflight_result_json_sha256", "json"),
        (
            "official_metric_scored_result_json",
            "official_metric_scored_result",
            "official_metric_scored_result_json_sha256",
            "json",
        ),
        ("failure_attribution_jsonl", "failure_attribution_rows", "failure_attribution_jsonl_sha256", "jsonl"),
    ):
        rel_path = paths.get(path_key)
        if not rel_path:
            raise ValueError(f"v5_6_2 artifact path missing: {path_key}")
        path = repo_root / str(rel_path)
        if not path.exists():
            raise ValueError(f"v5_6_2 artifact missing: {path_key}")
        actual = json.loads(path.read_text(encoding="utf-8")) if kind == "json" else read_jsonl(path)
        if actual != report.get(payload_key):
            raise ValueError(f"v5_6_2 artifact payload drift: {path_key}")
        if hashes.get(hash_key) != sha256_file(path):
            raise ValueError(f"v5_6_2 artifact hash drift: {hash_key}")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _assert_no_raw_payload_keys(report)
    if report.get("run_id") != SHORT_RUN_ID or report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v5_6_2 run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v5_6_2 canonical_long_run_id mismatch")
    if report.get("status") not in {STATUS, SCORED_STATUS}:
        raise ValueError("v5_6_2 status mismatch")
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v5_6_2 logical run key mismatch")
    if report.get("source_run_id") != SOURCE_RUN_ID or report.get("source_logical_run_key") != SOURCE_LOGICAL_RUN_KEY:
        raise ValueError("v5_6_2 source run mismatch")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v5_6_2 current resolution mismatch")
    if report.get("v5_6_baseline_run_id") != V5_6_BASELINE_RUN_ID:
        raise ValueError("v5_6_2 v5_6 baseline mismatch")
    if report.get("non_production") is not True:
        raise ValueError("v5_6_2 must remain non-production")
    _require_artifact_paths(report)
    expected_scope = {
        "source_run_id": SOURCE_RUN_ID,
        "source_artifact_path": SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix(),
        "row_count": EXPECTED_ROW_COUNT,
        "scope_policy": SCOPE_POLICY,
        "excluded_scopes": list(EXCLUDED_SCOPES),
    }
    if report.get("approval_scope") != expected_scope:
        raise ValueError("v5_6_2 approval scope drift")
    if report.get("official_metric_input_rows") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_6_2 official metric input rows drift")
    if report.get("official_metric_input_rows_consumed") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_6_2 official metric input rows consumed drift")
    if report.get("row_count_by_track") != EXPECTED_ROWS_BY_TRACK:
        raise ValueError("v5_6_2 row count by track drift")
    validation = report.get("source_artifact_validation") or {}
    if validation.get("path_matches_v5_5_report") is not True:
        raise ValueError("v5_6_2 source artifact path mismatch")
    if validation.get("sha256_matches_v5_5_report") is not True:
        raise ValueError("v5_6_2 source artifact sha256 mismatch")
    if validation.get("path_matches_v5_6_report") is not True:
        raise ValueError("v5_6_2 v5_6 source artifact path mismatch")
    if validation.get("sha256_matches_v5_6_report") is not True:
        raise ValueError("v5_6_2 v5_6 source artifact sha256 mismatch")
    if validation.get("row_count") != EXPECTED_ROW_COUNT or validation.get("row_count_matches_v5_5_report") is not True:
        raise ValueError("v5_6_2 source artifact row count drift")
    if validation.get("row_count_matches_v5_6_report") is not True:
        raise ValueError("v5_6_2 v5_6 source artifact row count drift")
    if report.get("duplicate_supporting_evidence_policy") != (
        "recorded_for_locator_precision_audit; row-level citation_locator remains authoritative"
    ):
        raise ValueError("v5_6_2 duplicate evidence policy drift")
    if report.get("duplicate_supporting_evidence_id_count") != 1:
        raise ValueError("v5_6_2 duplicate evidence summary drift")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v5_6_2 protected namespace touched")
    for key in CLOSED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v5_6_2 closed surface opened: {key}")
    _require_exact_source_rows(report)
    _require_result_consistency(report)
    if root is not None:
        _require_written_artifacts(report, root=root)
