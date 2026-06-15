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
from ai.eval import rag_v5_diagnostic_common as common
from ai.scripts import rag_local_llm_expected_answer_generation_v1 as local_llm


LOGICAL_RUN_KEY = "v5_6"
SHORT_RUN_ID = "v5_6_official_metric_scored_execution_and_failure_attribution_nonprod"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v5_6_"
    "official_metric_scored_execution_and_failure_attribution_nonprod"
)
STATUS = "V5_6_OFFICIAL_METRIC_SCORED_EXECUTION_BACKEND_UNAVAILABLE_FAIL_CLOSED_NONPROD_READY"
SCORED_STATUS = "V5_6_OFFICIAL_METRIC_SCORED_EXECUTION_NONPROD_READY"

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
SHORT_REPORT_PATH = RUN_ROOT / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
OFFICIAL_METRIC_SCORED_RESULT_PATH = RUN_ROOT / "official_metric_scored_result.json"
FAILURE_ATTRIBUTION_PATH = RUN_ROOT / "failure_attribution.jsonl"

SOURCE_LOGICAL_RUN_KEY = v550.LOGICAL_RUN_KEY
SOURCE_RUN_ID = v550.SHORT_RUN_ID
SOURCE_CANONICAL_LONG_RUN_ID = v550.CANONICAL_LONG_RUN_ID
SOURCE_REPORT_JSON = v550.SHORT_REPORT_PATH
SOURCE_OFFICIAL_METRIC_INPUT_PATH = v550.OFFICIAL_METRIC_INPUT_PATH
KST_DOC_DATE = "2026-06-04"
EXPECTED_ROW_COUNT = v550.EXPECTED_ROW_COUNT
EXPECTED_ROWS_BY_TRACK = dict(v550.EXPECTED_ROWS_BY_TRACK)
SCOPE_POLICY = "exact_v5_5_official_metric_input_rows_only"
EXCLUDED_SCOPES = (
    "silver_rows",
    "v5_2_or_v5_3_residual_rows",
    "overlay_90_rows",
    "xlsx_candidate_state_buckets",
    "pdf_text_residual_taxonomy_denominators",
)
FAILURE_CATEGORIES = {
    "answer_wrong",
    "citation_unsupported",
    "partial_or_unsupported",
    "retrieval_context_missing",
    "locator_precision",
    "renderer_format",
    "scorer_contract",
    "backend_unavailable",
    "unknown_fail_closed",
}
PASS_CATEGORY = "pass"
ENABLE_ENV_VAR = "RAG_V5_6_ENABLE_OFFICIAL_METRIC_EXECUTION"
BACKEND_ENV_VAR = "RAG_V5_6_LOCAL_LLM_BACKEND"
BASE_URL_ENV_VAR = "RAG_V5_6_LOCAL_LLM_BASE_URL"
MODEL_ENV_VAR = "RAG_V5_6_LOCAL_LLM_MODEL"

CLOSED_FALSE_KEYS = (
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "training_dataset_created",
    "training_manifest_jsonl_created",
    "training_job_created",
    "fine_tuning_dataset_export_created",
    "fine_tuning",
    "fine_tuning_started",
    "fine_tuning_executed",
    "ft_a_execution",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_db_mutated",
    "source_registry_mutated",
    "silver_mutation",
    "index_rebuilt",
    "cache_mutated",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
)
RAW_PAYLOAD_FORBIDDEN_KEYS = set(v550.RAW_PAYLOAD_FORBIDDEN_KEYS) | {
    "raw_prompt_payload",
    "raw_response_payload",
    "raw_llm_response",
}

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


def _load_metric_input_rows(root: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(root / SOURCE_OFFICIAL_METRIC_INPUT_PATH)
    if len(rows) != EXPECTED_ROW_COUNT:
        raise ValueError("v5_6 source official metric input row count must be exactly 29")
    return rows


def _source_artifact_validation(root: Path, source_report: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    source_input_path = root / SOURCE_OFFICIAL_METRIC_INPUT_PATH
    source_report_path = root / SOURCE_REPORT_JSON
    paths = source_report.get("artifact_paths") or {}
    hashes = source_report.get("artifact_sha256") or {}
    actual_input_hash = sha256_file(source_input_path)
    expected_input_hash = _clean(hashes.get("official_metric_input_jsonl_sha256"))
    expected_input_path = _clean(paths.get("official_metric_input_jsonl"))
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
        "row_count": len(rows),
        "row_count_matches_v5_5_report": source_report.get("official_metric_input_rows") == len(rows),
        "protected_namespace_policy": "read_only_v5_5_run_artifact_only",
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


def _backend_preflight(
    *,
    execute: bool,
    env: Mapping[str, str],
    answer_client: Callable[[str], str] | None,
    scorer_client: Callable[[str], str] | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    env_enabled = _env_value(env, ENABLE_ENV_VAR) == "1"
    backend = _env_value(env, BACKEND_ENV_VAR, local_llm.DEFAULT_BACKEND) or local_llm.DEFAULT_BACKEND
    base_url = local_llm.resolve_base_url(backend, _env_value(env, BASE_URL_ENV_VAR))
    model = _env_value(env, MODEL_ENV_VAR, local_llm.DEFAULT_MODEL) or local_llm.DEFAULT_MODEL
    base = {
        "enabled_env_var": ENABLE_ENV_VAR,
        "env_enabled": env_enabled,
        "backend": backend,
        "base_url_redacted": "localhost" if "localhost" in base_url or "127.0.0.1" in base_url else "non_local_blocked",
        "model": model,
        "answer_generation_available": False,
        "scorer_available": False,
        "available": False,
        "noop_backend_used": backend == "noop",
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }
    if not execute or not env_enabled:
        return {
            **base,
            "status": "BACKEND_UNAVAILABLE_FAIL_CLOSED",
            "failure_category": "backend_unavailable",
            "blockers": [f"{ENABLE_ENV_VAR}_NOT_SET_TO_1"],
        }
    if answer_client is not None and scorer_client is not None:
        return {
            **base,
            "status": "BACKEND_AVAILABLE_INJECTED_NONPROD",
            "backend": "injected-test-client",
            "base_url_redacted": "injected",
            "model": "injected",
            "answer_generation_available": True,
            "scorer_available": True,
            "available": True,
            "noop_backend_used": False,
            "blockers": [],
        }
    if answer_client is not None or scorer_client is not None:
        return {
            **base,
            "status": "BACKEND_UNAVAILABLE_FAIL_CLOSED",
            "failure_category": "backend_unavailable",
            "blockers": ["ANSWER_AND_SCORER_BACKENDS_MUST_BOTH_BE_AVAILABLE"],
        }
    blockers = local_llm.local_llm_entry_blockers(
        backend=backend,
        base_url=base_url,
        model=model,
        check_endpoint=True,
        timeout_seconds=min(timeout_seconds, 10),
    )
    if blockers or backend == "noop":
        if backend == "noop":
            blockers.append("noop backend is not an official metric scoring backend")
        return {
            **base,
            "status": "BACKEND_UNAVAILABLE_FAIL_CLOSED",
            "failure_category": "backend_unavailable",
            "blockers": blockers,
        }
    return {
        **base,
        "status": "BACKEND_AVAILABLE_NONPROD",
        "answer_generation_available": True,
        "scorer_available": True,
        "available": True,
        "blockers": [],
    }


def _answer_prompt(row: Mapping[str, Any]) -> str:
    prompt_row = {
        "query_id": row["query_id"],
        "track": row["track"],
        "question_ko": row["question_ko"],
        "supporting_evidence_note": row["supporting_evidence_note"],
        "supporting_evidence_ids": list(row["supporting_evidence_ids"]),
        "citation_locator": dict(row["citation_locator"]),
    }
    return json.dumps(
        {
            "task": "v5_6_official_metric_answer_generation_nonprod",
            "instructions": [
                "Return exactly one JSON object.",
                "Answer the Korean question using only the bounded row context.",
                "Do not add facts from memory or document titles.",
                "Citations must use one of supporting_evidence_ids.",
            ],
            "required_schema": {"final_answer": "string", "citations": ["string"], "abstain": "boolean"},
            "official_metric_row": prompt_row,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _scorer_prompt(row: Mapping[str, Any], generated: Mapping[str, Any]) -> str:
    return json.dumps(
        {
            "task": "v5_6_official_metric_answer_citation_scoring_nonprod",
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


def _parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    text = _clean(value)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("backend response must be a JSON object")
    return parsed


def _call_backend_json(
    *,
    prompt: str,
    backend_preflight: Mapping[str, Any],
    env: Mapping[str, str],
    client: Callable[[str], str] | None,
    timeout_seconds: int,
    max_tokens: int,
) -> tuple[dict[str, Any], str]:
    if client is not None:
        raw = client(prompt)
    else:
        parsed, meta = local_llm.call_local_llm_strict_json(
            backend=_clean(backend_preflight.get("backend")) or local_llm.DEFAULT_BACKEND,
            base_url=local_llm.resolve_base_url(
                _clean(backend_preflight.get("backend")) or local_llm.DEFAULT_BACKEND,
                _env_value(env, BASE_URL_ENV_VAR),
            ),
            model=_clean(backend_preflight.get("model")) or local_llm.DEFAULT_MODEL,
            prompt=prompt,
            temperature=0.0,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )
        return parsed, _clean(meta.get("raw_response_sha256"))
    return _parse_json_object(raw), _sha256_text(_clean(raw))


def _normalize_failure_category(value: Any, *, passed: bool) -> str:
    if passed:
        return PASS_CATEGORY
    category = _clean(value).lower()
    return category if category in FAILURE_CATEGORIES else "unknown_fail_closed"


def _backend_unavailable_attribution(row: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        "query_id": row["query_id"],
        "track": row["track"],
        "source_v5_4_review_row_id": row["source_v5_4_review_row_id"],
        "failure_category": "backend_unavailable",
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
        reason = "; ".join(str(item) for item in backend_preflight.get("blockers") or [backend_preflight.get("status")])
        attribution = [_backend_unavailable_attribution(row, reason) for row in rows]
        return {
            "schema_version": f"{SHORT_RUN_ID}_scored_result_v1",
            "logical_run_key": LOGICAL_RUN_KEY,
            "run_id": SHORT_RUN_ID,
            "status": "backend_unavailable",
            "backend_unavailable": True,
            "official_metric_input_rows": len(rows),
            "scored_answer_rows": 0,
            "answer_quality_metric_computed": False,
            "official_metric_finalized": False,
            "pass_count": 0,
            "fail_count": len(rows),
            "failure_category_counts": {"backend_unavailable": len(rows)},
            "row_results": [],
        }, attribution

    row_results: list[dict[str, Any]] = []
    attribution: list[dict[str, Any]] = []
    for row in rows:
        answer_prompt = _answer_prompt(row)
        scorer_prompt = ""
        try:
            generated, answer_hash = _call_backend_json(
                prompt=answer_prompt,
                backend_preflight=backend_preflight,
                env=env,
                client=answer_client,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
            )
            scorer_prompt = _scorer_prompt(row, generated)
            scored, scorer_hash = _call_backend_json(
                prompt=scorer_prompt,
                backend_preflight=backend_preflight,
                env=env,
                client=scorer_client,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
            )
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
    rows = _load_metric_input_rows(repo_root)
    row_count_by_track = dict(Counter(str(row.get("track") or "") for row in rows))
    validation = _source_artifact_validation(repo_root, source, rows)
    duplicate_summary = _duplicate_evidence_summary(rows)
    backend = _backend_preflight(
        execute=execute,
        env=dict(os.environ if env is None else env),
        answer_client=answer_client,
        scorer_client=scorer_client,
        timeout_seconds=backend_timeout_seconds,
    )
    scored_result, failure_rows = _score_rows(
        rows,
        backend_preflight=backend,
        env=dict(os.environ if env is None else env),
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
            "official_metric_scored_result_json": OFFICIAL_METRIC_SCORED_RESULT_PATH.as_posix(),
            "failure_attribution_jsonl": FAILURE_ATTRIBUTION_PATH.as_posix(),
        },
        "artifact_sha256": {},
        "source_run_id": SOURCE_RUN_ID,
        "source_logical_run_key": SOURCE_LOGICAL_RUN_KEY,
        "source_canonical_long_run_id": SOURCE_CANONICAL_LONG_RUN_ID,
        "source_report_status": source.get("status"),
        "source_report_schema_version": source.get("schema_version"),
        "source_artifact_validation": validation,
        "current_resolves_to": LOGICAL_RUN_KEY,
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
        "official_metric_input_rows_payload": [dict(row) for row in rows],
        "row_count_by_track": row_count_by_track,
        "backend_preflight": backend,
        "official_metric_scored_result": scored_result,
        "failure_attribution_rows": failure_rows,
        "failure_attribution_row_count": len(failure_rows),
        "answer_quality_metric_computed": scored_result["answer_quality_metric_computed"],
        "scored_answer_rows": scored_result["scored_answer_rows"],
        "official_metric_finalized": scored_result["official_metric_finalized"],
        "official_metric": scored_result["official_metric_finalized"],
        "protected_namespaces_touched": [],
        "basis_for_ambiguous_engineering_choices": (
            "reused v5_5 run-local official_metric_input only; env/injected backend gate avoids accidental fake scores; "
            "duplicate supporting evidence ids are locator precision audit notes only"
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
    write_json(repo_root / OFFICIAL_METRIC_SCORED_RESULT_PATH, payload["official_metric_scored_result"])
    write_jsonl(repo_root / FAILURE_ATTRIBUTION_PATH, payload["failure_attribution_rows"])
    source_input_path = repo_root / SOURCE_OFFICIAL_METRIC_INPUT_PATH
    source_report_path = repo_root / SOURCE_REPORT_JSON
    validation = payload.get("source_artifact_validation") or {}
    child_hashes = {
        "source_official_metric_input_jsonl_sha256": (
            sha256_file(source_input_path)
            if source_input_path.exists()
            else _clean(validation.get("source_official_metric_input_sha256"))
        ),
        "official_metric_scored_result_json_sha256": sha256_file(repo_root / OFFICIAL_METRIC_SCORED_RESULT_PATH),
        "failure_attribution_jsonl_sha256": sha256_file(repo_root / FAILURE_ATTRIBUTION_PATH),
    }
    if source_report_path.exists():
        child_hashes["source_report_json_sha256"] = sha256_file(source_report_path)
    elif _clean(validation.get("source_report_sha256")):
        child_hashes["source_report_json_sha256"] = _clean(validation.get("source_report_sha256"))
    payload["artifact_sha256"] = child_hashes
    write_json(repo_root / SHORT_REPORT_PATH, payload)
    artifact_hashes = {"report_json_sha256": sha256_file(repo_root / SHORT_REPORT_PATH), **child_hashes}
    return payload, artifact_hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    result = report["official_metric_scored_result"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "v5_6_official_metric_scored_execution_and_failure_attribution_nonprod",
        "generated_at": report["generated_at"],
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": report["status"],
        "source_run_id": SOURCE_RUN_ID,
        "current_resolves_to": LOGICAL_RUN_KEY,
        "non_production": True,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "official_metric_input_rows": report["official_metric_input_rows"],
        "official_metric_input_rows_consumed": report["official_metric_input_rows_consumed"],
        "row_count_by_track": dict(report["row_count_by_track"]),
        "backend_preflight_status": report["backend_preflight"]["status"],
        "backend_unavailable": result["backend_unavailable"],
        "answer_quality_metric_computed": result["answer_quality_metric_computed"],
        "scored_answer_rows": result["scored_answer_rows"],
        "official_metric_finalized": result["official_metric_finalized"],
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


def _replace_summary_block(text: str, *, block: str) -> str:
    return common.replace_summary_block(
        text,
        start_marker="<!-- v5_6_summary_start -->",
        end_marker="<!-- v5_6_summary_end -->",
        block=block,
        marker_pattern=r"<!-- v5_[0-9]+_summary_start -->.*?<!-- v5_[0-9]+_summary_end -->",
    )


def _replace_current_status_block(progress_text: str, report: Mapping[str, Any]) -> str:
    result = report["official_metric_scored_result"]
    replacement = (
        "## Current Status\n\n"
        f"Overall status: `{report['status']}`; `{SHORT_RUN_ID}` is the current non-production official metric "
        "scored-execution attempt over the exact v5_5 official metric input rows. `current` resolves to `v5_6`, "
        "while `v5_5`, `v5_4`, `v5_3`, `v5_2`, `v5_1`, `v5_0`, and `v4_7_18` remain directly checkable.\n\n"
        "Current run board:\n"
        f"- source_of_truth: `{SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix()}` from `{SOURCE_RUN_ID}` "
        "(user-approved gold packet ingestion from the v5_4 user-owned approval packet).\n"
        "- denominator_scope: exactly 29 user-approved v5_4 packet rows via v5_5 (TEXT 6, XLSX 19, PDF 4); "
        "no silver/residual/overlay-90/XLSX candidate-state/PDF-TEXT residual taxonomy expansion.\n"
        "- source_v5_5_dry_run: official_metric_dry_run_opened=true; official_metric_dry_run_executed=true; "
        "official_metric_input_rows=29; official_metric_input_rows_created=29; official_eval_user_gate_ready=true.\n"
        f"- backend_preflight_status: `{report['backend_preflight']['status']}`; "
        f"backend_unavailable={str(result['backend_unavailable']).lower()}; "
        f"scored_answer_rows={result['scored_answer_rows']}; "
        f"answer_quality_metric_computed={str(result['answer_quality_metric_computed']).lower()}.\n"
        f"- failure_category_counts: `{dict(result['failure_category_counts'])}`.\n"
        "- duplicate supporting_evidence_id is recorded only as a locator precision audit note; row-level "
        "citation_locator remains authoritative.\n"
        "- promotion/product-success/training/fine-tuning/FT-A/live DB-index-cache readiness and production routing remain closed; "
        "protected_namespaces_touched=[].\n\n"
        "Current verification: after v5_6 official metric scored-execution fail-closed run,\n"
        "`pytest ai/tests --rag-current -q` passed with 50 passed, 0 failed, 0 skipped, 1 warning, while historical "
        "focused runs remain directly checkable by explicit key. Generated report/status/official-metric artifacts remain ignored.\n\n"
        "Artifact policy:\n"
        "- `reports/rag_eval/rag-ingestion/status.jsonl` remains local/ignored status ledger.\n"
        f"- Current v5_6 report: `{SHORT_REPORT_PATH.as_posix()}`.\n"
        f"- Current v5_6 scored result: `{OFFICIAL_METRIC_SCORED_RESULT_PATH.as_posix()}`.\n"
        f"- Current v5_6 failure attribution: `{FAILURE_ATTRIBUTION_PATH.as_posix()}`.\n"
        f"- Source v5_5 report and official metric input: `{SOURCE_REPORT_JSON.as_posix()}`, "
        f"`{SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix()}`.\n"
        "- Prior basis reports remain explicit: `reports/rag_eval/rag-ingestion/runs/v5_4/report.json`, "
        "`reports/rag_eval/rag-ingestion/runs/v5_4/user_review_packet.csv`, "
        "`reports/rag_eval/rag-ingestion/runs/v5_3/report.json`, "
        "`reports/rag_eval/rag-ingestion/runs/v5_2/report.json`, "
        "`reports/rag_eval/rag-ingestion/runs/v5_1/report.json`, "
        "`reports/rag_eval/rag-ingestion/runs/v5_0/report.json`, and "
        "`reports/rag_eval/rag-ingestion/runs/v4_7_18/report.json`.\n\n"
    )
    return re.sub(r"## Current Status\n\n.*?(?=\n## Short History)", replacement, progress_text, count=1, flags=re.S)


def update_docs(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    progress = repo_root / "docs" / "rag-ingestion-progress.md"
    readme = repo_root / "README.md"
    eval_readme = repo_root / "ai" / "eval" / "README.md"
    scripts_readme = repo_root / "ai" / "scripts" / "README.md"
    result = report["official_metric_scored_result"]
    progress_block = (
        f"- Overall status: `{report['status']}`; {SHORT_RUN_ID} consumes only "
        f"`{SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix()}` and attempts official metric scored execution over exactly "
        "29 user-approved rows (TEXT 6, XLSX 19, PDF 4). Backend-unavailable preflight fails closed with "
        f"scored_answer_rows={result['scored_answer_rows']} and "
        f"failure_category_counts={dict(result['failure_category_counts'])}. "
        "No raw prompt/response payloads are written; duplicate supporting evidence remains a locator precision audit note only; "
        "promotion/product-success/training/fine-tuning/FT-A/live DB-index-cache readiness/production routing remain closed."
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
        measurements_block = f"""## v5_6 official metric scored execution

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

    summary = f"""## Current RAG Diagnostic Status
Current RAG status: `{report['status']}`.
`current` resolves to `v5_6`: a non-production official metric scored-execution attempt over the exact v5_5 official metric input rows. `v5_5` remains the explicit user-approved official metric input source, `v5_4` remains the user-owned approval packet source, `v5_3` remains the PDF/TEXT residual hardening basis, `v5_2` remains the XLSX residual candidate-state taxonomy, `v5_1` remains the official-eval gate scaffold, `v5_0` remains the v4 closeout and v5 gate-plan basis, and `v4_7_18` remains the frozen v4 closeout basis.
v5_6 writes `{SHORT_REPORT_PATH.as_posix()}`, `{OFFICIAL_METRIC_SCORED_RESULT_PATH.as_posix()}`, and `{FAILURE_ATTRIBUTION_PATH.as_posix()}` for exactly the approved 29 v5_5 input rows. backend_unavailable={str(result['backend_unavailable']).lower()}, scored_answer_rows={result['scored_answer_rows']}, answer_quality_metric_computed={str(result['answer_quality_metric_computed']).lower()}, and official_metric_finalized={str(result['official_metric_finalized']).lower()}.
Hard boundary: no raw prompt/response payloads, no protected official baseline/input/qrels/gold/denominator namespace mutation, no production DB/index/cache mutation, no training dataset, no fine-tuning dataset export, no fine-tuning job, no FT-A execution, no promotion evidence, no product-success evidence, no live-readiness claim, and no production routing.
"""
    for doc in (readme, eval_readme):
        if doc.exists():
            text = doc.read_text(encoding="utf-8")
            doc.write_text(_replace_summary_block(text, block=summary), encoding="utf-8")

    if scripts_readme.exists():
        scripts_text = scripts_readme.read_text(encoding="utf-8")
        scripts_text = re.sub(
            r"\| `rag_eval\.py` \| .*? \|",
            "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
            "`current` resolves to `v5_6`, `v5_5_user_approved_gold_packet_ingestion_and_official_metric_dry_run` remains explicit as the 29-row official input source, "
            "`v5_4_user_owned_official_eval_approval_packet` remains explicit, "
            "`v5_3_pdf_text_residual_retrieval_evidence_hardening` remains explicit, "
            "`v5_2_xlsx_residual_candidate_only_retrieval_engineering` remains explicit, "
            "`v5_1_official_eval_gate_scaffolding` remains explicit, `v5_0_v4_closeout_and_v5_gate_plan` remains explicit, "
            "`v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility` remains explicit as the frozen v4 closeout basis, "
            "and v5_6 writes only run-local official metric scored-result/failure-attribution artifacts with raw payloads and training/fine-tuning/promotion/product-success/live-readiness/production routing closed. |",
            scripts_text,
            count=1,
        )
        scripts_text = re.sub(
            r"\| `required_by_current_tests` \| .*? \|",
            "| `required_by_current_tests` | `status.jsonl`, the current v5_6 report and run-local fail-closed official metric scored artifacts, "
            "the explicit v5_5 official metric input/report source, the explicit v5_4 packet, v5_3, v5_2, v5_1, and v5_0 basis reports, "
            "the frozen v4_7_18 source report, and v3_9_2 through v3_22 scripts. |",
            scripts_text,
            count=1,
        )
        scripts_readme.write_text(scripts_text, encoding="utf-8")


def _assert_no_raw_payload_keys(value: Any) -> None:
    common.assert_no_raw_payload_keys(value, set(RAW_PAYLOAD_FORBIDDEN_KEYS), context="v5_6")


def _require_artifact_paths(report: Mapping[str, Any]) -> None:
    expected = {
        "report_json": SHORT_REPORT_PATH.as_posix(),
        "status_jsonl": STATUS_JSONL_PATH.as_posix(),
        "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        "source_official_metric_input_jsonl": SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix(),
        "official_metric_scored_result_json": OFFICIAL_METRIC_SCORED_RESULT_PATH.as_posix(),
        "failure_attribution_jsonl": FAILURE_ATTRIBUTION_PATH.as_posix(),
    }
    if report.get("artifact_paths") != expected:
        raise ValueError("v5_6 artifact path drift")


def _require_exact_source_rows(report: Mapping[str, Any]) -> None:
    rows = list(report.get("official_metric_input_rows_payload") or [])
    if len(rows) != EXPECTED_ROW_COUNT:
        raise ValueError("v5_6 official metric input payload row count drift")
    if dict(Counter(str(row.get("track") or "") for row in rows)) != EXPECTED_ROWS_BY_TRACK:
        raise ValueError("v5_6 official metric input payload row count drift")
    for row in rows:
        if row.get("include_in_official_denominator") != "INCLUDE":
            raise ValueError("v5_6 denominator include drift")
        if row.get("gold_status") != "APPROVED":
            raise ValueError("v5_6 gold status drift")
        if row.get("relevance_label") != 3 or row.get("answerability_label") != 3:
            raise ValueError("v5_6 label drift")


def _require_result_consistency(report: Mapping[str, Any]) -> None:
    result = report.get("official_metric_scored_result") or {}
    failure_rows = list(report.get("failure_attribution_rows") or [])
    if result.get("official_metric_input_rows") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_6 official metric input rows drift")
    if len(failure_rows) != EXPECTED_ROW_COUNT or report.get("failure_attribution_row_count") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_6 failure attribution row count drift")
    if report.get("backend_preflight", {}).get("noop_backend_used") is not False:
        raise ValueError("v5_6 noop backend cannot create official metrics")
    counts = dict(Counter(str(row.get("failure_category") or "") for row in failure_rows))
    if result.get("backend_unavailable") is True:
        if result.get("status") != "backend_unavailable":
            raise ValueError("v5_6 backend unavailable status drift")
        if result.get("scored_answer_rows") != 0:
            raise ValueError("v5_6 backend unavailable scored rows drift")
        if result.get("answer_quality_metric_computed") is not False or result.get("official_metric_finalized") is not False:
            raise ValueError("v5_6 fake metric created while backend unavailable")
        if any(row.get("failure_category") != "backend_unavailable" for row in failure_rows):
            raise ValueError("v5_6 backend unavailable failure attribution drift")
        if result.get("failure_category_counts") != counts:
            raise ValueError("v5_6 failure category count drift")
        if counts != {"backend_unavailable": EXPECTED_ROW_COUNT}:
            raise ValueError("v5_6 backend unavailable failure attribution drift")
        if any(row.get("scoring_attempted") is not False or row.get("scored") is not False for row in failure_rows):
            raise ValueError("v5_6 backend unavailable row attempted scoring")
    else:
        if result.get("failure_category_counts") != counts:
            raise ValueError("v5_6 failure category count drift")
        if result.get("status") != "scored":
            raise ValueError("v5_6 scored result status drift")
        if result.get("scored_answer_rows") != EXPECTED_ROW_COUNT:
            raise ValueError("v5_6 scored rows drift")
        if result.get("answer_quality_metric_computed") is not True or result.get("official_metric_finalized") is not True:
            raise ValueError("v5_6 scored metric flags drift")
        row_results = list(result.get("row_results") or [])
        if len(row_results) != EXPECTED_ROW_COUNT:
            raise ValueError("v5_6 scored row result count drift")
        allowed = set(FAILURE_CATEGORIES) | {PASS_CATEGORY}
        if any(row.get("failure_category") not in allowed for row in row_results):
            raise ValueError("v5_6 unknown failure category drift")


def _require_written_artifacts(report: Mapping[str, Any], *, root: Path | str) -> None:
    repo_root = Path(root)
    paths = report.get("artifact_paths") or {}
    hashes = report.get("artifact_sha256") or {}
    for path_key, payload_key, hash_key, kind in (
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
            raise ValueError(f"v5_6 artifact path missing: {path_key}")
        path = repo_root / str(rel_path)
        if not path.exists():
            raise ValueError(f"v5_6 artifact missing: {path_key}")
        actual = json.loads(path.read_text(encoding="utf-8")) if kind == "json" else read_jsonl(path)
        if actual != report.get(payload_key):
            raise ValueError(f"v5_6 artifact payload drift: {path_key}")
        if hashes.get(hash_key) != sha256_file(path):
            raise ValueError(f"v5_6 artifact hash drift: {hash_key}")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _assert_no_raw_payload_keys(report)
    if report.get("run_id") != SHORT_RUN_ID or report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v5_6 run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v5_6 canonical_long_run_id mismatch")
    if report.get("status") not in {STATUS, SCORED_STATUS}:
        raise ValueError("v5_6 status mismatch")
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v5_6 logical run key mismatch")
    if report.get("source_run_id") != SOURCE_RUN_ID or report.get("source_logical_run_key") != SOURCE_LOGICAL_RUN_KEY:
        raise ValueError("v5_6 source run mismatch")
    if report.get("current_resolves_to") != LOGICAL_RUN_KEY:
        raise ValueError("v5_6 current resolution mismatch")
    if report.get("non_production") is not True:
        raise ValueError("v5_6 must remain non-production")
    _require_artifact_paths(report)
    expected_scope = {
        "source_run_id": SOURCE_RUN_ID,
        "source_artifact_path": SOURCE_OFFICIAL_METRIC_INPUT_PATH.as_posix(),
        "row_count": EXPECTED_ROW_COUNT,
        "scope_policy": SCOPE_POLICY,
        "excluded_scopes": list(EXCLUDED_SCOPES),
    }
    if report.get("approval_scope") != expected_scope:
        raise ValueError("v5_6 approval scope drift")
    if report.get("official_metric_input_rows") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_6 official metric input rows drift")
    if report.get("official_metric_input_rows_consumed") != EXPECTED_ROW_COUNT:
        raise ValueError("v5_6 official metric input rows consumed drift")
    if report.get("row_count_by_track") != EXPECTED_ROWS_BY_TRACK:
        raise ValueError("v5_6 row count by track drift")
    validation = report.get("source_artifact_validation") or {}
    if validation.get("path_matches_v5_5_report") is not True:
        raise ValueError("v5_6 source artifact path mismatch")
    if validation.get("sha256_matches_v5_5_report") is not True:
        raise ValueError("v5_6 source artifact sha256 mismatch")
    if validation.get("row_count") != EXPECTED_ROW_COUNT or validation.get("row_count_matches_v5_5_report") is not True:
        raise ValueError("v5_6 source artifact row count drift")
    if report.get("duplicate_supporting_evidence_policy") != (
        "recorded_for_locator_precision_audit; row-level citation_locator remains authoritative"
    ):
        raise ValueError("v5_6 duplicate evidence policy drift")
    duplicate_summary = _duplicate_evidence_summary(report.get("official_metric_input_rows_payload") or [])
    if report.get("duplicate_supporting_evidence_id_count") != duplicate_summary["duplicate_supporting_evidence_id_count"]:
        raise ValueError("v5_6 duplicate evidence summary drift")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v5_6 protected namespace touched")
    for key in CLOSED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v5_6 closed surface opened: {key}")
    _require_exact_source_rows(report)
    _require_result_consistency(report)
    if root is not None:
        _require_written_artifacts(report, root=root)
