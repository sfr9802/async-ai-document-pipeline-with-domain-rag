from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable, Mapping, Sequence

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v4710_pdf_korean_evidence_normalization_and_answer_replay_readiness as v4710
from ai.eval import rag_v4711_actual_llm_answer_replay_and_silver_diagnostic_smoke as v4711
from ai.eval import rag_v4712_layered_retrieval_generalization_and_overfit_audit as v4712
from ai.eval import rag_v476_archive_purge as v476
from ai.scripts import rag_local_llm_expected_answer_generation_v1 as local_llm


LOGICAL_RUN_KEY = "v4_7_13"
SHORT_RUN_ID = "v4_7_13_live_retrieval_answerability_and_full_pdf_replay"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_13_"
    "live_retrieval_answerability_and_full_pdf_replay_nonprod"
)
STATUS = "V4_7_13_LIVE_RETRIEVAL_ANSWERABILITY_AND_FULL_PDF_REPLAY_NONPROD_READY"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
FULL_PDF_ANSWER_REVIEW_PACKET_JSONL = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "full_pdf_answer_review_packet_ko.jsonl"
SILVER_ANSWERABILITY_OVERLAY_JSON = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "silver_answerability_overlay.json"
SILVER_EXPANDED_ANSWER_SMOKE_JSONL = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "silver_expanded_answer_smoke_ko.jsonl"
LIVE_SILVER_RETRIEVAL_REPLAY_JSON = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "live_silver_retrieval_replay.json"

SOURCE_RUN_ID = v4712.SHORT_RUN_ID
SOURCE_REPORT_JSON = v4712.SHORT_REPORT_PATH
SOURCE_PDF_SURFACE_RUN_ID = v4710.SHORT_RUN_ID
SOURCE_PDF_SURFACE_REPORT_JSON = v4710.SHORT_REPORT_PATH

ENABLE_LIVE_SILVER_RETRIEVAL_REPLAY_ENV_VAR = "RAG_V4_7_13_ENABLE_LIVE_SILVER_RETRIEVAL_REPLAY"
ENABLE_FULL_PDF_LLM_REPLAY_ENV_VAR = "RAG_V4_7_13_ENABLE_FULL_PDF_LLM_REPLAY"
ENABLE_SILVER_LLM_EXPANDED_SMOKE_ENV_VAR = "RAG_V4_7_13_ENABLE_SILVER_LLM_EXPANDED_SMOKE"
BASE_URL_ENV_VAR = "RAG_V4_7_13_LOCAL_LLM_BASE_URL"
MODEL_ENV_VAR = "RAG_V4_7_13_LOCAL_LLM_MODEL"
BACKEND_ENV_VAR = "RAG_V4_7_13_LOCAL_LLM_BACKEND"

REQUIRED_FALSE_KEYS = v4712.REQUIRED_FALSE_KEYS
FAMILIES = ("TEXT", "PDF", "XLSX")


def utc_now_iso() -> str:
    return v476.utc_now_iso()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v476.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v476.write_json(path, payload)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    v476.write_jsonl(path, list(rows))


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bounded(value: Any, *, limit: int = 520) -> str:
    text = re.sub(r"\s+", " ", _clean(value)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _sha256_file(path: Path) -> str:
    return v476.sha256_file(path)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _env_enabled(env: Mapping[str, str], key: str) -> bool:
    return _clean(env.get(key)).lower() in {"1", "true", "yes", "on"}


def _counter_dict(value: int = 0) -> dict[str, int]:
    return {family: int(value) for family in FAMILIES}


def _family_counts(rows: Sequence[Mapping[str, Any]], *, key: str = "source_family") -> dict[str, int]:
    counts = Counter(_clean(row.get(key)).upper() for row in rows)
    return {family: int(counts.get(family, 0)) for family in FAMILIES}


def _local_llm_probe(*, execute: bool, env: Mapping[str, str]) -> dict[str, Any]:
    backend = _clean(env.get(BACKEND_ENV_VAR, local_llm.DEFAULT_BACKEND)) or local_llm.DEFAULT_BACKEND
    base_url = local_llm.resolve_base_url(backend, _clean(env.get(BASE_URL_ENV_VAR)))
    model = _clean(env.get(MODEL_ENV_VAR, local_llm.DEFAULT_MODEL)) or local_llm.DEFAULT_MODEL
    if not execute:
        return {
            "available": False,
            "status": "LOCAL_LLM_NOT_PROBED_CHECK_ONLY",
            "backend": backend,
            "base_url_redacted": "localhost",
            "model": model,
            "blockers": ["execute_false"],
        }
    blockers = local_llm.local_llm_entry_blockers(
        backend=backend,
        base_url=base_url,
        model=model,
        check_endpoint=True,
        timeout_seconds=10,
    )
    return {
        "available": not blockers,
        "status": "LOCAL_LLM_AVAILABLE_DIAGNOSTIC_ONLY" if not blockers else "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED",
        "backend": backend,
        "base_url_redacted": "localhost",
        "model": model,
        "blockers": blockers,
    }


def _load_v4712_artifacts(root: Path, v4712_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    report = dict(v4712_report or registry.load_report("v4_7_12", root=root))
    v4712.check_report(report)
    artifact_paths = report.get("artifact_paths") or {}
    silver_audit_path = root / _clean(
        artifact_paths.get("silver_layered_retrieval_audit_json") or v4712.SILVER_LAYERED_RETRIEVAL_AUDIT_JSON.as_posix()
    )
    silver_smoke_path = root / _clean(
        artifact_paths.get("silver_answer_smoke_ko_jsonl") or v4712.SILVER_ANSWER_SMOKE_JSONL.as_posix()
    )
    silver_audit = read_json(silver_audit_path) if silver_audit_path.exists() else report.get("silver_layered_retrieval_audit", {})
    silver_smoke_rows = read_jsonl(silver_smoke_path) if silver_smoke_path.exists() else (report.get("silver_answer_smoke") or {}).get("rows") or []
    return {
        "report": report,
        "silver_audit": silver_audit,
        "silver_smoke_rows": list(silver_smoke_rows),
        "silver_audit_path": silver_audit_path,
        "silver_smoke_path": silver_smoke_path,
        "report_path": root / v4712.SHORT_REPORT_PATH,
    }


def live_silver_retrieval_replay(
    *,
    env: Mapping[str, str],
    execute: bool,
    v4712_report: Mapping[str, Any],
    silver_audit: Mapping[str, Any],
) -> dict[str, Any]:
    enabled = _env_enabled(env, ENABLE_LIVE_SILVER_RETRIEVAL_REPLAY_ENV_VAR)
    base = {
        "schema_version": f"{SHORT_RUN_ID}_live_silver_retrieval_replay_v1",
        "diagnostic_only": True,
        "read_only": True,
        "protected_namespaces_touched": [],
        "index_rebuilt": False,
        "source_registry_mutated": False,
        "silver_mutated": False,
        "cache_mutated": False,
        "production_db_mutated": False,
        "vector_payload_used_as_evidence_truth_violation_count": 0,
        "raw_pdf_query_time_parsing_attempt_count": 0,
        "raw_xlsx_query_time_parsing_attempt_count": 0,
        "source_title_shortcut_used_count": 0,
        "direct_answer_value_matching_used_count": 0,
        "hidden_target_locator_used_count": 0,
        "expected_or_supporting_gold_text_used_count": 0,
        "rows": [],
    }
    if not enabled:
        return {
            **base,
            "status": "LIVE_SILVER_RETRIEVAL_REPLAY_DISABLED_FAIL_CLOSED",
            "env_enabled": False,
            "blocked_reason": f"{ENABLE_LIVE_SILVER_RETRIEVAL_REPLAY_ENV_VAR} is not enabled",
            "row_count": 0,
            "family_counts": _counter_dict(),
            "same_family_at_k_count_by_family": _counter_dict(),
            "target_in_topk_count_by_family": _counter_dict(),
            "target_rank_by_family": {family: [] for family in FAMILIES},
            "sourceatom_hydration_success_count_by_family": _counter_dict(),
            "evidencebundle_created_count_by_family": _counter_dict(),
            "citation_render_success_count_by_family": _counter_dict(),
            "retrieval_fail_closed_count_by_family": _counter_dict(),
            "top_fail_reason_by_family": {family: "" for family in FAMILIES},
            "persisted_topk_match_count_by_family": _counter_dict(),
            "persisted_topk_drift_count_by_family": _counter_dict(),
            "route_mismatch_count_by_family": _counter_dict(),
            "sourceatom_mismatch_count_by_family": _counter_dict(),
        }
    if not execute:
        return {
            **base,
            "status": "LIVE_SILVER_RETRIEVAL_REPLAY_UNAVAILABLE_FAIL_CLOSED",
            "env_enabled": True,
            "blocked_reason": "execute=false prevents live retrieval replay from touching runtime adapters",
            "row_count": 0,
            "family_counts": _counter_dict(),
            "same_family_at_k_count_by_family": _counter_dict(),
            "target_in_topk_count_by_family": _counter_dict(),
            "target_rank_by_family": {family: [] for family in FAMILIES},
            "sourceatom_hydration_success_count_by_family": _counter_dict(),
            "evidencebundle_created_count_by_family": _counter_dict(),
            "citation_render_success_count_by_family": _counter_dict(),
            "retrieval_fail_closed_count_by_family": _counter_dict(),
            "top_fail_reason_by_family": {family: "live_replay_execute_false" for family in FAMILIES},
            "persisted_topk_match_count_by_family": _counter_dict(),
            "persisted_topk_drift_count_by_family": _counter_dict(),
            "route_mismatch_count_by_family": _counter_dict(),
            "sourceatom_mismatch_count_by_family": _counter_dict(),
        }
    # The current repository has contract/in-memory runtime adapters, but no
    # configured read-only all-1000 live index handle for this silver surface.
    # Fail closed instead of rebuilding or writing a replay top-k artifact.
    return {
        **base,
        "status": "LIVE_SILVER_RETRIEVAL_REPLAY_UNAVAILABLE_FAIL_CLOSED",
        "env_enabled": True,
        "blocked_reason": (
            "no configured read-only live SearchIndexContract for all 1000 v3_7_2 silver rows; "
            "v4_7_12 persisted top-k remains comparison source"
        ),
        "comparison_sources": {
            "v4_7_12_report": v4712.SHORT_REPORT_PATH.as_posix(),
            "v4_7_12_silver_audit_rows": int(silver_audit.get("audit_rows_total") or 0),
            "v3_7_2_topk_sha256": (v4712_report.get("counters") or {}).get("silver_topk_sha256", ""),
        },
        "row_count": 0,
        "family_counts": _counter_dict(),
        "same_family_at_k_count_by_family": _counter_dict(),
        "target_in_topk_count_by_family": _counter_dict(),
        "target_rank_by_family": {family: [] for family in FAMILIES},
        "sourceatom_hydration_success_count_by_family": _counter_dict(),
        "evidencebundle_created_count_by_family": _counter_dict(),
        "citation_render_success_count_by_family": _counter_dict(),
        "retrieval_fail_closed_count_by_family": _counter_dict(),
        "top_fail_reason_by_family": {family: "live_retrieval_read_only_index_unavailable" for family in FAMILIES},
        "persisted_topk_match_count_by_family": _counter_dict(),
        "persisted_topk_drift_count_by_family": _counter_dict(),
        "route_mismatch_count_by_family": _counter_dict(),
        "sourceatom_mismatch_count_by_family": _counter_dict(),
    }


def _citation_id(row: Mapping[str, Any]) -> str:
    return f"evidence_1_{_clean(row.get('evidence_snippet_sha256'))[:12] or row.get('row_index_1based')}"


def _build_pdf_prompt(row: Mapping[str, Any]) -> str:
    citation_id = _citation_id(row)
    return json.dumps(
        {
            "task": "diagnostic_v4_7_13_full_pdf_answer_replay",
            "instructions": [
                "Return exactly one JSON object.",
                "Answer in Korean.",
                "Use only the query and bounded EvidenceBundle atom.",
                "Use insufficient_evidence or abstain when the evidence does not answer the query.",
                "Citations must use citation_id.",
            ],
            "required_schema": {
                "final_answer": "Korean string",
                "answer_type": "answer|insufficient_evidence|abstain",
                "insufficiency_reason": "string",
                "citations": ["citation_id"],
                "unsupported_claim_risk": "boolean",
                "evidence_underuse_flag": "boolean",
            },
            "query_text": row.get("query_text"),
            "bounded_evidence_excerpt": row.get("citation_span_preview"),
            "citation_id": citation_id,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _claim_supported(answer: str, evidence: str) -> bool:
    terms = v4712._tokens(answer)
    compact_evidence = v4712._compact(evidence)
    matched = [v4712._compact(token) for token in terms if v4712._compact(token) in compact_evidence]
    return len(matched) >= 2 or any(len(token) >= 12 for token in matched)


def run_full_pdf_llm_replay(
    rows: Sequence[Mapping[str, Any]],
    *,
    execute: bool,
    env: Mapping[str, str],
    local_probe: Mapping[str, Any],
    llm_client: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    enabled = _env_enabled(env, ENABLE_FULL_PDF_LLM_REPLAY_ENV_VAR)
    if not enabled:
        return {
            "status": "FULL_PDF_LLM_REPLAY_DISABLED_FAIL_CLOSED",
            "env_enabled": False,
            "eligible_count": len(rows),
            "llm_invoked_count": 0,
            "generated_response_count": 0,
            "parsed_final_answer_present_count": 0,
            "korean_final_answer_count": 0,
            "citation_rendered_count": 0,
            "citation_grounded_to_evidence_count": 0,
            "claim_support_pass_count": 0,
            "claim_support_fail_count": 0,
            "supported_insufficient_evidence_count": 0,
            "unsupported_answer_count": 0,
            "evidence_underuse_count": 0,
            "over_abstain_count": 0,
            "parser_fail_count": 0,
            "rows": [],
        }
    if not execute or not local_probe.get("available"):
        return {
            "status": "FULL_PDF_LLM_REPLAY_UNAVAILABLE_FAIL_CLOSED",
            "env_enabled": True,
            "eligible_count": len(rows),
            "blocked_reason": "local LLM unavailable or execute=false",
            "llm_invoked_count": 0,
            "generated_response_count": 0,
            "parsed_final_answer_present_count": 0,
            "korean_final_answer_count": 0,
            "citation_rendered_count": 0,
            "citation_grounded_to_evidence_count": 0,
            "claim_support_pass_count": 0,
            "claim_support_fail_count": len(rows),
            "supported_insufficient_evidence_count": 0,
            "unsupported_answer_count": 0,
            "evidence_underuse_count": 0,
            "over_abstain_count": 0,
            "parser_fail_count": 0,
            "rows": [],
        }
    output_rows: list[dict[str, Any]] = []
    for row in rows:
        citation_id = _citation_id(row)
        prompt = _build_pdf_prompt(row)
        parsed: dict[str, Any] = {}
        raw_sha = ""
        parser_fail = False
        status = "FULL_PDF_LLM_GENERATED_DIAGNOSTIC_ONLY"
        try:
            parsed, meta = local_llm.call_local_llm_strict_json(
                backend=_clean(local_probe.get("backend")) or local_llm.DEFAULT_BACKEND,
                base_url=_clean(env.get(BASE_URL_ENV_VAR)),
                model=_clean(local_probe.get("model")) or local_llm.DEFAULT_MODEL,
                prompt=prompt,
                max_tokens=420,
                timeout_seconds=90,
                llm_client=llm_client,
            )
            raw_sha = _clean(meta.get("raw_response_sha256"))
        except Exception as exc:
            status = f"FULL_PDF_LLM_OUTPUT_FAIL_CLOSED:{type(exc).__name__}"
            parser_fail = True
        final_answer = _bounded(parsed.get("final_answer"), limit=520)
        answer_type = _clean(parsed.get("answer_type"))
        citations = parsed.get("citations") if isinstance(parsed.get("citations"), list) else []
        grounded = any(citation_id and citation_id in _clean(citation) for citation in citations)
        supported = bool(final_answer and grounded and _claim_supported(final_answer, _clean(row.get("citation_span_preview"))))
        insufficient = answer_type == "insufficient_evidence"
        unsupported = bool(final_answer and not supported and not insufficient)
        over_abstain = answer_type == "abstain" and supported
        output_rows.append(
            {
                "query_id": row.get("query_id"),
                "row_index_1based": row.get("row_index_1based"),
                "source_family": "PDF",
                "query_text_sha256": _sha256_text(_clean(row.get("query_text"))),
                "evidence_snippet_sha256": row.get("evidence_snippet_sha256"),
                "page_candidate": row.get("page_candidate"),
                "block_candidate": row.get("block_candidate"),
                "locator_preview_redacted": row.get("locator_preview_redacted"),
                "citation_id": citation_id,
                "final_answer": final_answer if not parser_fail else "",
                "final_answer_sha256": _sha256_text(final_answer) if final_answer else "",
                "answer_type": answer_type,
                "insufficiency_reason": _bounded(parsed.get("insufficiency_reason"), limit=260),
                "citations": citations if not parser_fail else [],
                "raw_response_sha256": raw_sha,
                "status": status,
                "llm_invoked": True,
                "parsed_final_answer_present": bool(final_answer),
                "korean_final_answer": bool(re.search(r"[가-힣]", final_answer)),
                "citation_rendered": bool(citations),
                "citation_grounded_to_evidence": grounded,
                "claim_support_pass": supported,
                "claim_support_fail": not supported,
                "supported_insufficient_evidence": insufficient and supported,
                "unsupported_answer": unsupported,
                "evidence_underuse": parsed.get("evidence_underuse_flag") is True or (bool(final_answer) and not supported),
                "over_abstain": over_abstain,
                "parser_fail": parser_fail,
                "diagnostic_only": True,
            }
        )
    return {
        "status": "FULL_PDF_LLM_REPLAY_COMPLETED_DIAGNOSTIC_ONLY",
        "env_enabled": True,
        "eligible_count": len(rows),
        "llm_invoked_count": sum(1 for row in output_rows if row.get("llm_invoked")),
        "generated_response_count": sum(1 for row in output_rows if row.get("final_answer")),
        "parsed_final_answer_present_count": sum(1 for row in output_rows if row.get("parsed_final_answer_present")),
        "korean_final_answer_count": sum(1 for row in output_rows if row.get("korean_final_answer")),
        "citation_rendered_count": sum(1 for row in output_rows if row.get("citation_rendered")),
        "citation_grounded_to_evidence_count": sum(1 for row in output_rows if row.get("citation_grounded_to_evidence")),
        "claim_support_pass_count": sum(1 for row in output_rows if row.get("claim_support_pass")),
        "claim_support_fail_count": sum(1 for row in output_rows if row.get("claim_support_fail")),
        "supported_insufficient_evidence_count": sum(1 for row in output_rows if row.get("supported_insufficient_evidence")),
        "unsupported_answer_count": sum(1 for row in output_rows if row.get("unsupported_answer")),
        "evidence_underuse_count": sum(1 for row in output_rows if row.get("evidence_underuse")),
        "over_abstain_count": sum(1 for row in output_rows if row.get("over_abstain")),
        "parser_fail_count": sum(1 for row in output_rows if row.get("parser_fail")),
        "rows": output_rows,
    }


def silver_answerability_overlay(
    *,
    silver_audit: Mapping[str, Any],
    silver_smoke_rows: Sequence[Mapping[str, Any]],
    topk_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    audit_by_id = {
        _clean(row.get("query_id")): dict(row)
        for row in silver_audit.get("audit_rows") or []
        if _clean(row.get("query_id"))
    }
    topk_by_id = v4712._topk_by_query_id(topk_rows)
    overlay_rows: list[dict[str, Any]] = []
    category_counts: dict[str, Counter[str]] = {
        "retrieval_target_miss": Counter(),
        "evidence_window_insufficient": Counter(),
        "query_too_broad": Counter(),
        "query_deictic_or_ambiguous": Counter(),
        "repeated_prefix_cluster_member": Counter(),
        "source_family_route_ok_but_evidence_mismatch": Counter(),
        "supported_insufficient_evidence": Counter(),
        "unsupported_insufficient_evidence": Counter(),
        "over_abstain_candidate": Counter(),
        "answer_parser_fail": Counter(),
        "likely_answerable_but_answer_failed": Counter(),
    }
    for smoke in silver_smoke_rows:
        query_id = _clean(smoke.get("query_id"))
        audit = audit_by_id.get(query_id, {})
        family = _clean(smoke.get("source_family") or audit.get("source_family")).upper()
        if family not in FAMILIES:
            family = "TEXT"
        answer_type = _clean(smoke.get("answer_type"))
        topk = topk_by_id.get(query_id, {})
        envelopes = topk.get("top_result_envelopes") if isinstance(topk.get("top_result_envelopes"), list) else []
        top1_source_atom_id = _clean(envelopes[0].get("source_atom_id")) if envelopes else ""
        smoke_source_atom_id = _clean(smoke.get("source_atom_id"))
        weak_status = _clean(audit.get("weak_answerability_status") or topk.get("weak_answerability_status"))
        target_hit = topk.get("target_hit_at_k") is True
        target_not_in_topk = topk.get("target_hit_at_k") is False or _clean(
            topk.get("primary_retrieval_diagnostic_bucket")
        ) == "target_not_in_topk"
        claim_fail = smoke.get("claim_support_fail") is True
        parser_fail = smoke.get("status") != "SILVER_LLM_GENERATED_DIAGNOSTIC_ONLY" or not _clean(smoke.get("final_answer"))
        insufficient = answer_type == "insufficient_evidence"
        flags = {
            "retrieval_target_miss": target_not_in_topk,
            "evidence_window_insufficient": insufficient,
            "query_too_broad": audit.get("too_broad_query") is True,
            "query_deictic_or_ambiguous": audit.get("deictic_or_ambiguous_query") is True,
            "repeated_prefix_cluster_member": audit.get("repeated_prefix_cluster") is True,
            "source_family_route_ok_but_evidence_mismatch": topk.get("same_track_hit_at_k") is True and (insufficient or claim_fail),
            "supported_insufficient_evidence": insufficient and smoke.get("claim_support_pass") is True,
            "unsupported_insufficient_evidence": insufficient and claim_fail,
            "over_abstain_candidate": answer_type == "abstain" and not claim_fail,
            "answer_parser_fail": parser_fail,
            "likely_answerable_but_answer_failed": audit.get("likely_unanswerable") is not True and (claim_fail or parser_fail or insufficient),
        }
        for name, enabled in flags.items():
            if enabled:
                category_counts[name][family] += 1
        overlay_rows.append(
            {
                "query_id": query_id,
                "source_family": family,
                "manifest_partition": _clean(smoke.get("manifest_partition") or audit.get("manifest_partition")),
                "prior_status": _clean(smoke.get("status")),
                "prior_answer_type": answer_type,
                "prior_claim_support_pass": smoke.get("claim_support_pass") is True,
                "prior_claim_support_fail": claim_fail,
                "target_hit_at_k": target_hit,
                "target_not_in_topk": target_not_in_topk,
                "target_rank_at_k": topk.get("target_rank_at_k"),
                "primary_retrieval_diagnostic_bucket": _clean(topk.get("primary_retrieval_diagnostic_bucket")),
                "top1_source_atom_id_matches_smoke": bool(top1_source_atom_id and smoke_source_atom_id == top1_source_atom_id),
                "weak_answerability_status": weak_status,
                "query_text_sha256": _clean(smoke.get("query_text_sha256") or audit.get("query_text_sha256")),
                **flags,
                "diagnostic_silver_only": True,
            }
        )
    family_counts = _family_counts(overlay_rows)
    insufficient_count = sum(1 for row in overlay_rows if row["prior_answer_type"] == "insufficient_evidence")
    return {
        "schema_version": f"{SHORT_RUN_ID}_silver_answerability_overlay_v1",
        "status": "SILVER_ANSWERABILITY_OVERLAY_READY_DIAGNOSTIC_ONLY",
        "diagnostic_silver_only": True,
        "silver_regenerated": False,
        "official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "row_count": len(overlay_rows),
        "prior_smoke_row_count": len(silver_smoke_rows),
        "prior_smoke_counts_by_family": family_counts,
        "prior_insufficient_evidence_count": insufficient_count,
        "prior_claim_support_pass_count": sum(1 for row in overlay_rows if row["prior_claim_support_pass"]),
        "prior_claim_support_fail_count": sum(1 for row in overlay_rows if row["prior_claim_support_fail"]),
        "category_counts_by_family": {name: _family_counts_from_counter(counter) for name, counter in category_counts.items()},
        "target_not_in_topk_count_by_family": _family_counts([row for row in overlay_rows if row["target_not_in_topk"]]),
        "target_hit_but_insufficient_evidence_count_by_family": _family_counts(
            [row for row in overlay_rows if row["target_hit_at_k"] and row["prior_answer_type"] == "insufficient_evidence"]
        ),
        "top1_source_atom_id_match_count": sum(1 for row in overlay_rows if row["top1_source_atom_id_matches_smoke"]),
        "weak_likely_answerable_but_insufficient_evidence_count_by_family": _family_counts(
            [
                row
                for row in overlay_rows
                if row["weak_answerability_status"] == "auto_weak_silver_likely_answerable"
                and row["prior_answer_type"] == "insufficient_evidence"
            ]
        ),
        "weak_likely_answerable_but_claim_support_fail_count_by_family": _family_counts(
            [
                row
                for row in overlay_rows
                if row["weak_answerability_status"] == "auto_weak_silver_likely_answerable"
                and row["prior_claim_support_fail"]
            ]
        ),
        "text_failure_explanation": (
            "TEXT smoke failures are mainly weak-likely-answerable queries whose family route survived but whose target "
            "SourceAtom was usually not in top-k, so the selected evidence did not contain enough answer-bearing context. "
            "The model therefore produced supported or unsupported insufficient_evidence despite query-level likely_unanswerable=false."
        ),
        "rows": overlay_rows,
    }


def _family_counts_from_counter(counter: Counter[str]) -> dict[str, int]:
    return {family: int(counter.get(family, 0)) for family in FAMILIES}


def run_silver_expanded_answer_smoke(
    *,
    env: Mapping[str, str],
    execute: bool,
    local_probe: Mapping[str, Any],
) -> dict[str, Any]:
    enabled = _env_enabled(env, ENABLE_SILVER_LLM_EXPANDED_SMOKE_ENV_VAR)
    if not enabled:
        return {
            "status": "SILVER_EXPANDED_LLM_SMOKE_DISABLED_FAIL_CLOSED",
            "env_enabled": False,
            "planned_sample_count": 150,
            "sample_count": 0,
            "llm_invoked_count": 0,
            "generated_response_count": 0,
            "rows": [],
        }
    return {
        "status": "SILVER_EXPANDED_LLM_SMOKE_UNAVAILABLE_FAIL_CLOSED",
        "env_enabled": True,
        "blocked_reason": "expanded smoke is gated after overlay; no stratified sample opened in this slice",
        "planned_sample_count": 150,
        "sample_count": 0,
        "llm_invoked_count": 0 if not local_probe.get("available") or not execute else 0,
        "generated_response_count": 0,
        "rows": [],
    }


def retrieval_tooling_audit(v4712_report: Mapping[str, Any], live_replay: Mapping[str, Any]) -> dict[str, Any]:
    counters = v4712_report.get("counters") or {}
    observed_rows = int(counters.get("layered_retrieval_audit_row_count") or 0)
    return {
        "schema_version": f"{SHORT_RUN_ID}_retrieval_tooling_audit_v1",
        "scope": "retrieval_only",
        "source_observation_run_id": v4712.SHORT_RUN_ID,
        "live_replay_status": live_replay.get("status"),
        "family_router_invoked_count": int(counters.get("family_router_invoked_count") or observed_rows),
        "sourceatom_hydration_invoked_count": int(counters.get("sourceatom_hydration_tool_invoked_count") or observed_rows),
        "evidencebundle_builder_invoked_count": int(counters.get("evidencebundle_builder_invoked_count") or observed_rows),
        "citation_renderer_invoked_count": int(counters.get("citation_renderer_invoked_count") or observed_rows),
        "wrong_family_tool_invocation_count": int(counters.get("wrong_family_tool_invocation_count") or 0),
        "missing_required_layer_count": int(counters.get("missing_required_layer_count") or 0),
        "answer_generator_invoked_count": 0,
    }


def answer_generation_tooling_audit(full_pdf_replay: Mapping[str, Any], expanded_smoke: Mapping[str, Any]) -> dict[str, Any]:
    llm_invoked = int(full_pdf_replay.get("llm_invoked_count") or 0) + int(expanded_smoke.get("llm_invoked_count") or 0)
    parsed = int(full_pdf_replay.get("parsed_final_answer_present_count") or 0) + int(expanded_smoke.get("generated_response_count") or 0)
    verified = int(full_pdf_replay.get("claim_support_pass_count") or 0) + int(full_pdf_replay.get("claim_support_fail_count") or 0)
    return {
        "schema_version": f"{SHORT_RUN_ID}_answer_generation_tooling_audit_v1",
        "scope": "answer_generation_only",
        "llm_invoked_count": llm_invoked,
        "parser_invoked_count": parsed,
        "claim_verifier_invoked_count": verified,
    }


def _median_by_family(live_replay: Mapping[str, Any]) -> dict[str, int | None]:
    ranks = live_replay.get("target_rank_by_family") or {}
    result: dict[str, int | None] = {}
    for family in FAMILIES:
        values = [int(value) for value in ranks.get(family, []) if value]
        result[family] = int(median(values)) if values else None
    return result


def _build_counters(
    *,
    v4712_report: Mapping[str, Any],
    pdf_rows: Sequence[Mapping[str, Any]],
    live_replay: Mapping[str, Any],
    full_pdf_replay: Mapping[str, Any],
    overlay: Mapping[str, Any],
    expanded_smoke: Mapping[str, Any],
    retrieval_tooling: Mapping[str, Any],
    answer_tooling: Mapping[str, Any],
    local_probe: Mapping[str, Any],
) -> dict[str, Any]:
    overlay_counts = overlay.get("category_counts_by_family") or {}
    live_counts = live_replay.get("family_counts") or _counter_dict()
    counters: dict[str, Any] = {
        "diagnostic_only": True,
        "non_production": True,
        "current_resolves_to": LOGICAL_RUN_KEY,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
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
        "layered_retrieval_architecture_preserved": True,
        "retrieval_tooling_family_router_invoked_count": int(retrieval_tooling.get("family_router_invoked_count") or 0),
        "retrieval_tooling_sourceatom_hydration_invoked_count": int(retrieval_tooling.get("sourceatom_hydration_invoked_count") or 0),
        "retrieval_tooling_evidencebundle_builder_invoked_count": int(retrieval_tooling.get("evidencebundle_builder_invoked_count") or 0),
        "retrieval_tooling_citation_renderer_invoked_count": int(retrieval_tooling.get("citation_renderer_invoked_count") or 0),
        "retrieval_tooling_wrong_family_tool_invocation_count": int(retrieval_tooling.get("wrong_family_tool_invocation_count") or 0),
        "retrieval_tooling_missing_required_layer_count": int(retrieval_tooling.get("missing_required_layer_count") or 0),
        "answer_generation_tooling_llm_invoked_count": int(answer_tooling.get("llm_invoked_count") or 0),
        "answer_generation_tooling_parser_invoked_count": int(answer_tooling.get("parser_invoked_count") or 0),
        "answer_generation_tooling_claim_verifier_invoked_count": int(answer_tooling.get("claim_verifier_invoked_count") or 0),
        "tooling_counter_scope_mismatch_count": 0,
        "pdf_survivor_row_count": int((v4712_report.get("counters") or {}).get("pdf_survivor_row_count") or 58),
        "pdf_answer_ready_evidencebundle_count": int((v4712_report.get("counters") or {}).get("pdf_answer_ready_evidencebundle_count") or 57),
        "pdf_full_replay_eligible_count": len(pdf_rows),
        "pdf_full_replay_excluded_weak_residual_count": 1,
        "pdf_full_replay_env_enabled": bool(full_pdf_replay.get("env_enabled")),
        "local_llm_available": bool(local_probe.get("available")),
        "pdf_llm_invoked_count": int(full_pdf_replay.get("llm_invoked_count") or 0),
        "pdf_generated_response_count": int(full_pdf_replay.get("generated_response_count") or 0),
        "pdf_parsed_final_answer_present_count": int(full_pdf_replay.get("parsed_final_answer_present_count") or 0),
        "pdf_korean_final_answer_count": int(full_pdf_replay.get("korean_final_answer_count") or 0),
        "pdf_citation_rendered_count": int(full_pdf_replay.get("citation_rendered_count") or 0),
        "pdf_citation_grounded_to_evidence_count": int(full_pdf_replay.get("citation_grounded_to_evidence_count") or 0),
        "pdf_claim_support_pass_count": int(full_pdf_replay.get("claim_support_pass_count") or 0),
        "pdf_claim_support_fail_count": int(full_pdf_replay.get("claim_support_fail_count") or 0),
        "pdf_supported_insufficient_evidence_count": int(full_pdf_replay.get("supported_insufficient_evidence_count") or 0),
        "pdf_unsupported_answer_count": int(full_pdf_replay.get("unsupported_answer_count") or 0),
        "pdf_evidence_underuse_count": int(full_pdf_replay.get("evidence_underuse_count") or 0),
        "pdf_over_abstain_count": int(full_pdf_replay.get("over_abstain_count") or 0),
        "pdf_parser_fail_count": int(full_pdf_replay.get("parser_fail_count") or 0),
        "live_silver_retrieval_env_enabled": bool(live_replay.get("env_enabled")),
        "live_silver_retrieval_row_count": int(live_replay.get("row_count") or 0),
        "live_silver_text_count": int(live_counts.get("TEXT") or 0),
        "live_silver_pdf_count": int(live_counts.get("PDF") or 0),
        "live_silver_xlsx_count": int(live_counts.get("XLSX") or 0),
        "live_family_route_selected_count_by_family": dict(live_replay.get("family_counts") or _counter_dict()),
        "live_same_family_at_k_count_by_family": dict(live_replay.get("same_family_at_k_count_by_family") or _counter_dict()),
        "live_target_in_topk_count_by_family": dict(live_replay.get("target_in_topk_count_by_family") or _counter_dict()),
        "live_target_rank_median_by_family": _median_by_family(live_replay),
        "live_sourceatom_hydration_success_count_by_family": dict(
            live_replay.get("sourceatom_hydration_success_count_by_family") or _counter_dict()
        ),
        "live_evidencebundle_created_count_by_family": dict(live_replay.get("evidencebundle_created_count_by_family") or _counter_dict()),
        "live_citation_render_success_count_by_family": dict(live_replay.get("citation_render_success_count_by_family") or _counter_dict()),
        "live_retrieval_fail_closed_count_by_family": dict(live_replay.get("retrieval_fail_closed_count_by_family") or _counter_dict()),
        "live_top_fail_reason_by_family": dict(live_replay.get("top_fail_reason_by_family") or {family: "" for family in FAMILIES}),
        "persisted_topk_match_count_by_family": dict(live_replay.get("persisted_topk_match_count_by_family") or _counter_dict()),
        "persisted_topk_drift_count_by_family": dict(live_replay.get("persisted_topk_drift_count_by_family") or _counter_dict()),
        "live_vs_persisted_route_mismatch_count_by_family": dict(live_replay.get("route_mismatch_count_by_family") or _counter_dict()),
        "live_vs_persisted_sourceatom_mismatch_count_by_family": dict(live_replay.get("sourceatom_mismatch_count_by_family") or _counter_dict()),
        "live_vector_payload_evidence_truth_violation_count": int(
            live_replay.get("vector_payload_used_as_evidence_truth_violation_count") or 0
        ),
        "live_raw_pdf_query_time_parsing_attempt_count": int(live_replay.get("raw_pdf_query_time_parsing_attempt_count") or 0),
        "live_raw_xlsx_query_time_parsing_attempt_count": int(live_replay.get("raw_xlsx_query_time_parsing_attempt_count") or 0),
        "live_source_title_shortcut_used_count": int(live_replay.get("source_title_shortcut_used_count") or 0),
        "live_direct_answer_value_matching_used_count": int(live_replay.get("direct_answer_value_matching_used_count") or 0),
        "live_hidden_target_locator_used_count": int(live_replay.get("hidden_target_locator_used_count") or 0),
        "live_expected_or_supporting_gold_text_used_count": int(live_replay.get("expected_or_supporting_gold_text_used_count") or 0),
        "silver_answerability_overlay_row_count": int(overlay.get("row_count") or 0),
        "silver_prior_smoke_row_count": int(overlay.get("prior_smoke_row_count") or 0),
        "silver_prior_smoke_text_count": int((overlay.get("prior_smoke_counts_by_family") or {}).get("TEXT") or 0),
        "silver_prior_smoke_pdf_count": int((overlay.get("prior_smoke_counts_by_family") or {}).get("PDF") or 0),
        "silver_prior_smoke_xlsx_count": int((overlay.get("prior_smoke_counts_by_family") or {}).get("XLSX") or 0),
        "silver_prior_insufficient_evidence_count": int(overlay.get("prior_insufficient_evidence_count") or 0),
        "silver_prior_claim_support_pass_count": int(overlay.get("prior_claim_support_pass_count") or 0),
        "silver_prior_claim_support_fail_count": int(overlay.get("prior_claim_support_fail_count") or 0),
        "silver_retrieval_target_miss_count_by_family": dict(overlay_counts.get("retrieval_target_miss") or _counter_dict()),
        "silver_evidence_window_insufficient_count_by_family": dict(overlay_counts.get("evidence_window_insufficient") or _counter_dict()),
        "silver_query_too_broad_count_by_family": dict(overlay_counts.get("query_too_broad") or _counter_dict()),
        "silver_query_deictic_or_ambiguous_count_by_family": dict(overlay_counts.get("query_deictic_or_ambiguous") or _counter_dict()),
        "silver_repeated_prefix_cluster_member_count_by_family": dict(overlay_counts.get("repeated_prefix_cluster_member") or _counter_dict()),
        "silver_source_family_route_ok_but_evidence_mismatch_count_by_family": dict(
            overlay_counts.get("source_family_route_ok_but_evidence_mismatch") or _counter_dict()
        ),
        "silver_supported_insufficient_evidence_count_by_family": dict(overlay_counts.get("supported_insufficient_evidence") or _counter_dict()),
        "silver_unsupported_insufficient_evidence_count_by_family": dict(
            overlay_counts.get("unsupported_insufficient_evidence") or _counter_dict()
        ),
        "silver_over_abstain_candidate_count_by_family": dict(overlay_counts.get("over_abstain_candidate") or _counter_dict()),
        "silver_answer_parser_fail_count_by_family": dict(overlay_counts.get("answer_parser_fail") or _counter_dict()),
        "silver_likely_answerable_but_answer_failed_count_by_family": dict(
            overlay_counts.get("likely_answerable_but_answer_failed") or _counter_dict()
        ),
        "silver_target_not_in_topk_count_by_family": dict(overlay.get("target_not_in_topk_count_by_family") or _counter_dict()),
        "silver_target_hit_but_insufficient_evidence_count_by_family": dict(
            overlay.get("target_hit_but_insufficient_evidence_count_by_family") or _counter_dict()
        ),
        "silver_top1_source_atom_id_match_count": int(overlay.get("top1_source_atom_id_match_count") or 0),
        "silver_weak_likely_answerable_but_insufficient_evidence_count_by_family": dict(
            overlay.get("weak_likely_answerable_but_insufficient_evidence_count_by_family") or _counter_dict()
        ),
        "silver_weak_likely_answerable_but_claim_support_fail_count_by_family": dict(
            overlay.get("weak_likely_answerable_but_claim_support_fail_count_by_family") or _counter_dict()
        ),
    }
    if counters["answer_generation_tooling_llm_invoked_count"] != counters["pdf_llm_invoked_count"] + int(
        expanded_smoke.get("llm_invoked_count") or 0
    ):
        counters["tooling_counter_scope_mismatch_count"] += 1
    return counters


def build_report(
    *,
    root: Path,
    execute: bool = False,
    sync_surfaces: bool = False,
    env: Mapping[str, str] | None = None,
    llm_client: Callable[[str], str] | None = None,
    generated_at: str | None = None,
    check: bool = True,
    v4712_report: Mapping[str, Any] | None = None,
    v4710_report: Mapping[str, Any] | None = None,
    prior_v474_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    del sync_surfaces
    env = os.environ if env is None else env
    artifacts = _load_v4712_artifacts(root, v4712_report=v4712_report)
    source_report = artifacts["report"]
    v4710_report = registry.load_report("v4_7_10", root=root) if v4710_report is None else dict(v4710_report)
    prior_v474_report = registry.load_report("v4_7_4", root=root) if prior_v474_report is None else dict(prior_v474_report)
    pdf_rows = v4712._full_pdf_replay_rows(v4710_report, prior_v474_report)
    topk_rows, _topk_resolution = v4712._load_v3_7_2_topk(root)
    silver_topk_rows = v4712._topk_silver_rows(topk_rows)
    llm_needed = _env_enabled(env, ENABLE_FULL_PDF_LLM_REPLAY_ENV_VAR) or _env_enabled(env, ENABLE_SILVER_LLM_EXPANDED_SMOKE_ENV_VAR)
    local_probe = _local_llm_probe(execute=execute and llm_needed, env=env)
    live_replay = live_silver_retrieval_replay(
        env=env,
        execute=execute,
        v4712_report=source_report,
        silver_audit=artifacts["silver_audit"],
    )
    full_pdf_replay = run_full_pdf_llm_replay(
        pdf_rows,
        execute=execute,
        env=env,
        local_probe=local_probe,
        llm_client=llm_client,
    )
    overlay = silver_answerability_overlay(
        silver_audit=artifacts["silver_audit"],
        silver_smoke_rows=artifacts["silver_smoke_rows"],
        topk_rows=silver_topk_rows,
    )
    expanded_smoke = run_silver_expanded_answer_smoke(env=env, execute=execute, local_probe=local_probe)
    retrieval_tooling = retrieval_tooling_audit(source_report, live_replay)
    answer_tooling = answer_generation_tooling_audit(full_pdf_replay, expanded_smoke)
    counters = _build_counters(
        v4712_report=source_report,
        pdf_rows=pdf_rows,
        live_replay=live_replay,
        full_pdf_replay=full_pdf_replay,
        overlay=overlay,
        expanded_smoke=expanded_smoke,
        retrieval_tooling=retrieval_tooling,
        answer_tooling=answer_tooling,
        local_probe=local_probe,
    )
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
            "full_pdf_answer_review_packet_ko_jsonl": FULL_PDF_ANSWER_REVIEW_PACKET_JSONL.as_posix(),
            "silver_answerability_overlay_json": SILVER_ANSWERABILITY_OVERLAY_JSON.as_posix(),
            "silver_expanded_answer_smoke_ko_jsonl": SILVER_EXPANDED_ANSWER_SMOKE_JSONL.as_posix(),
            "live_silver_retrieval_replay_json": LIVE_SILVER_RETRIEVAL_REPLAY_JSON.as_posix(),
        },
        "artifact_sha256": {},
        "source_run_id": SOURCE_RUN_ID,
        "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        "source_pdf_surface_run_id": SOURCE_PDF_SURFACE_RUN_ID,
        "source_pdf_surface_report_json": SOURCE_PDF_SURFACE_REPORT_JSON.as_posix(),
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
        "retrieval_tooling_audit": retrieval_tooling,
        "answer_generation_tooling_audit": answer_tooling,
        "live_silver_retrieval_replay": live_replay,
        "full_pdf_llm_replay": full_pdf_replay,
        "silver_answerability_overlay": overlay,
        "silver_expanded_answer_smoke": expanded_smoke,
        "local_llm_probe": local_probe,
        "counters": counters,
        "completion_branch": (
            "A_full_pdf_and_live_silver_retrieval_replay_completed"
            if live_replay.get("status") == "LIVE_SILVER_RETRIEVAL_REPLAY_COMPLETED_DIAGNOSTIC_ONLY"
            and full_pdf_replay.get("status") == "FULL_PDF_LLM_REPLAY_COMPLETED_DIAGNOSTIC_ONLY"
            else "B_live_or_full_pdf_lane_fail_closed_with_answerability_overlay"
        ),
        "non_gold_ambiguity_decisions": [
            {
                "decision": "v4_7_12_artifacts_are_read_only_source_observations",
                "reason": "v4_7_13 must not rewrite v4_7_12 report, silver audit, or silver smoke artifacts",
            },
            {
                "decision": "silver_answerability_overlay_is_diagnostic_only",
                "reason": "the overlay explains smoke outcomes without changing silver, gold, qrels, labels, or denominator rows",
            },
        ],
        "residual_risks": [
            "live silver retrieval replay remains fail-closed unless a read-only current SearchIndexContract is explicitly configured",
            "silver expanded LLM smoke remains optional and disabled unless its explicit env gate is set",
        ],
    }
    if check:
        check_report(report)
    return report


def write_artifacts(root: Path, report: Mapping[str, Any]) -> dict[str, str]:
    pdf_path = root / FULL_PDF_ANSWER_REVIEW_PACKET_JSONL
    overlay_path = root / SILVER_ANSWERABILITY_OVERLAY_JSON
    expanded_path = root / SILVER_EXPANDED_ANSWER_SMOKE_JSONL
    live_path = root / LIVE_SILVER_RETRIEVAL_REPLAY_JSON
    write_jsonl(pdf_path, (report.get("full_pdf_llm_replay") or {}).get("rows") or [])
    write_json(overlay_path, report.get("silver_answerability_overlay") or {})
    write_jsonl(expanded_path, (report.get("silver_expanded_answer_smoke") or {}).get("rows") or [])
    write_json(live_path, report.get("live_silver_retrieval_replay") or {})
    return {
        "full_pdf_answer_review_packet_ko_jsonl_sha256": _sha256_file(pdf_path),
        "silver_answerability_overlay_json_sha256": _sha256_file(overlay_path),
        "silver_expanded_answer_smoke_ko_jsonl_sha256": _sha256_file(expanded_path),
        "live_silver_retrieval_replay_json_sha256": _sha256_file(live_path),
    }


def write_report_bundle(root: Path, report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    hashes = write_artifacts(root, report)
    report = json.loads(json.dumps(report, ensure_ascii=False))
    report["artifact_sha256"].update(hashes)
    write_json(root / SHORT_REPORT_PATH, report)
    hashes["report_json_sha256"] = _sha256_file(root / SHORT_REPORT_PATH)
    return report, hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    counters = report["counters"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "diagnostic_v4_7_13_live_retrieval_answerability_and_full_pdf_replay_nonprod",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "source_run_id": SOURCE_RUN_ID,
        "source_pdf_surface_run_id": SOURCE_PDF_SURFACE_RUN_ID,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
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
        "live_silver_retrieval_env_enabled": counters["live_silver_retrieval_env_enabled"],
        "live_silver_retrieval_row_count": counters["live_silver_retrieval_row_count"],
        "pdf_full_replay_env_enabled": counters["pdf_full_replay_env_enabled"],
        "pdf_full_replay_eligible_count": counters["pdf_full_replay_eligible_count"],
        "pdf_generated_response_count": counters["pdf_generated_response_count"],
        "silver_answerability_overlay_row_count": counters["silver_answerability_overlay_row_count"],
        "silver_prior_insufficient_evidence_count": counters["silver_prior_insufficient_evidence_count"],
        "tooling_counter_scope_mismatch_count": counters["tooling_counter_scope_mismatch_count"],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def append_status(root: Path, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    path = root / STATUS_JSONL_PATH
    rows = read_jsonl(path) if path.exists() else []
    rows = [
        row
        for row in rows
        if row.get("run_id") not in {SHORT_RUN_ID, CANONICAL_LONG_RUN_ID}
        and row.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID
        and row.get("event_type") != "diagnostic_v4_7_13_live_retrieval_answerability_and_full_pdf_replay_nonprod"
    ]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    write_jsonl(path, rows)


def _upsert_block(text: str, *, start_marker: str, end_marker: str, block: str, after_anchor: str | None = None) -> str:
    wrapped = f"{start_marker}\n{block.rstrip()}\n{end_marker}"
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.S)
    if pattern.search(text):
        return pattern.sub(wrapped, text, count=1)
    if after_anchor and after_anchor in text:
        return text.replace(after_anchor, after_anchor + "\n\n" + wrapped, 1)
    return wrapped + "\n" + text


def update_docs(root: Path, report: Mapping[str, Any]) -> None:
    counters = report["counters"]
    progress = root / "docs/rag-ingestion-progress.md"
    measurements = root / "docs/rag-ingestion-measurements.md"
    triage = root / "docs/rag-ingestion-triage.md"
    readme = root / "README.md"
    eval_readme = root / "ai/eval/README.md"
    scripts_readme = root / "ai/scripts/README.md"

    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} is {STATUS}. Artifact: `{SHORT_REPORT_PATH.as_posix()}`. "
        f"Live silver retrieval env_enabled={str(counters['live_silver_retrieval_env_enabled']).lower()} rows {counters['live_silver_retrieval_row_count']}; "
        f"full PDF replay env_enabled={str(counters['pdf_full_replay_env_enabled']).lower()} generated {counters['pdf_generated_response_count']} of {counters['pdf_full_replay_eligible_count']}; "
        f"silver answerability overlay rows {counters['silver_answerability_overlay_row_count']} and prior claim-support pass/fail "
        f"{counters['silver_prior_claim_support_pass_count']}/{counters['silver_prior_claim_support_fail_count']}. "
        "Diagnostic-only: official_metric_input_rows=0, silver_official_metric_input_rows=0, silver_promoted_to_gold_count=0, "
        "promotion_evidence=false, product_success_evidence_allowed=false, live_db_index_cache_readiness=false."
    )
    progress_text = progress.read_text(encoding="utf-8")
    progress.write_text(
        _upsert_block(
            progress_text,
            start_marker="<!-- v4_7_13_start -->",
            end_marker="<!-- v4_7_13_end -->",
            block=progress_block,
            after_anchor="# RAG Ingestion Progress",
        ),
        encoding="utf-8",
    )

    measurements_block = f"""## v4_7_13 live retrieval answerability and full PDF replay

| counter | value |
| --- | --- |
| status | {STATUS} |
| live_silver_retrieval_env_enabled | {str(counters['live_silver_retrieval_env_enabled']).lower()} |
| live_silver_retrieval_row_count | {counters['live_silver_retrieval_row_count']} |
| pdf_full_replay_env_enabled | {str(counters['pdf_full_replay_env_enabled']).lower()} |
| pdf_full_replay_eligible_count | {counters['pdf_full_replay_eligible_count']} |
| pdf_generated_response_count | {counters['pdf_generated_response_count']} |
| silver_answerability_overlay_row_count | {counters['silver_answerability_overlay_row_count']} |
| silver_prior_insufficient_evidence_count | {counters['silver_prior_insufficient_evidence_count']} |
| silver_prior_claim_support_pass/fail | {counters['silver_prior_claim_support_pass_count']}/{counters['silver_prior_claim_support_fail_count']} |
| tooling_counter_scope_mismatch_count | {counters['tooling_counter_scope_mismatch_count']} |
| official_metric_input_rows | 0 |
"""
    measurements.write_text(
        _upsert_block(
            measurements.read_text(encoding="utf-8"),
            start_marker="<!-- v4_7_13_measurements_start -->",
            end_marker="<!-- v4_7_13_measurements_end -->",
            block=measurements_block,
            after_anchor="# RAG Ingestion Measurements",
        ),
        encoding="utf-8",
    )

    triage_block = (
        f"- v4_7_13 live replay status: `{report['live_silver_retrieval_replay']['status']}`. "
        f"Full PDF status: `{report['full_pdf_llm_replay']['status']}`. "
        f"TEXT silver explanation: {report['silver_answerability_overlay']['text_failure_explanation']} "
        "SearchView/vector payload remains candidate-only; SourceAtom/EvidenceBundle remains evidence truth."
    )
    triage.write_text(
        _upsert_block(
            triage.read_text(encoding="utf-8"),
            start_marker="<!-- v4_7_13_triage_start -->",
            end_marker="<!-- v4_7_13_triage_end -->",
            block=triage_block,
            after_anchor="# RAG Ingestion Triage",
        ),
        encoding="utf-8",
    )

    for path in (readme, eval_readme):
        text = path.read_text(encoding="utf-8")
        path.write_text(
            _upsert_block(
                text,
                start_marker="<!-- v4_7_13_summary_start -->",
                end_marker="<!-- v4_7_13_summary_end -->",
                block=(
                    f"Current RAG status: `{STATUS}`.\n"
                    f"`current` resolves to `v4_7_13`: diagnostic-only live retrieval/full-PDF replay readiness. "
                    f"Live silver retrieval rows {counters['live_silver_retrieval_row_count']}; "
                    f"full PDF generated {counters['pdf_generated_response_count']}; "
                    f"silver overlay rows {counters['silver_answerability_overlay_row_count']}; official_metric_input_rows=0.\n"
                    "Canonical progress/details: `docs/rag-ingestion-progress.md`, "
                    "`docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md`. "
                    "prior v4_7 cleanup keys remain explicit for historical checks.\n"
                    "Historical README anchors preserved: ## Current RAG Diagnostic Status; "
                    "## Korean human review packet; "
                    "review_packet_ko_hydrated.xlsx; actual Korean query candidates; "
                    "User-owned fields remain blank/default; "
                    "v4_7 remains pre-official; supersedes the abstract v4_7_1 Korean review packet; "
                    "The previous v4_7_1 Korean review packet was abstract; "
                    "hydrated rows 204, PDF 100, XLSX 104; non-empty `질의문` 204; "
                    "v4_7_3 applies the user-reviewed Korean query candidate CSV; 미검수=통과; "
                    "v4_7_3 applies the user-reviewed CSV decisions; "
                    "not gold/qrels; "
                    "PDF survivor 58; v4_7_4 replays only the 58 user-passed PDF survivor candidates; "
                    "fine_tuning_executed=false; not official metric."
                ),
            ),
            encoding="utf-8",
        )

    scripts_text = scripts_readme.read_text(encoding="utf-8")
    scripts_text = re.sub(r"`current` resolves to `v4_7_\d+`", "`current` resolves to `v4_7_13`", scripts_text)
    scripts_readme.write_text(scripts_text, encoding="utf-8")


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v4_7_13 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v4_7_13 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v4_7_13 status mismatch")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v4_7_13 must remain diagnostic-only and non-production")
    for key in REQUIRED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v4_7_13 opened forbidden gate: {key}")
    if report.get("official_metric_input_rows") != 0:
        raise ValueError("v4_7_13 official_metric_input_rows must stay 0")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_13 touched protected namespaces")
    counters = report.get("counters") or {}
    required = (
        "diagnostic_only",
        "non_production",
        "current_resolves_to",
        "official_metric_input_rows",
        "silver_official_metric_input_rows",
        "silver_promoted_to_gold_count",
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
        "layered_retrieval_architecture_preserved",
        "retrieval_tooling_family_router_invoked_count",
        "retrieval_tooling_sourceatom_hydration_invoked_count",
        "retrieval_tooling_evidencebundle_builder_invoked_count",
        "retrieval_tooling_citation_renderer_invoked_count",
        "retrieval_tooling_wrong_family_tool_invocation_count",
        "retrieval_tooling_missing_required_layer_count",
        "answer_generation_tooling_llm_invoked_count",
        "answer_generation_tooling_parser_invoked_count",
        "answer_generation_tooling_claim_verifier_invoked_count",
        "tooling_counter_scope_mismatch_count",
        "pdf_survivor_row_count",
        "pdf_answer_ready_evidencebundle_count",
        "pdf_full_replay_eligible_count",
        "pdf_full_replay_excluded_weak_residual_count",
        "pdf_full_replay_env_enabled",
        "local_llm_available",
        "pdf_llm_invoked_count",
        "pdf_generated_response_count",
        "pdf_parsed_final_answer_present_count",
        "pdf_korean_final_answer_count",
        "pdf_citation_rendered_count",
        "pdf_citation_grounded_to_evidence_count",
        "pdf_claim_support_pass_count",
        "pdf_claim_support_fail_count",
        "pdf_supported_insufficient_evidence_count",
        "pdf_unsupported_answer_count",
        "pdf_evidence_underuse_count",
        "pdf_over_abstain_count",
        "pdf_parser_fail_count",
        "live_silver_retrieval_env_enabled",
        "live_silver_retrieval_row_count",
        "live_silver_text_count",
        "live_silver_pdf_count",
        "live_silver_xlsx_count",
        "live_same_family_at_k_count_by_family",
        "live_target_in_topk_count_by_family",
        "live_sourceatom_hydration_success_count_by_family",
        "live_evidencebundle_created_count_by_family",
        "live_citation_render_success_count_by_family",
        "persisted_topk_match_count_by_family",
        "persisted_topk_drift_count_by_family",
        "live_retrieval_fail_closed_count_by_family",
        "silver_answerability_overlay_row_count",
        "silver_prior_smoke_row_count",
        "silver_prior_smoke_text_count",
        "silver_prior_smoke_pdf_count",
        "silver_prior_smoke_xlsx_count",
        "silver_prior_insufficient_evidence_count",
        "silver_prior_claim_support_pass_count",
        "silver_prior_claim_support_fail_count",
        "silver_retrieval_target_miss_count_by_family",
        "silver_evidence_window_insufficient_count_by_family",
        "silver_query_too_broad_count_by_family",
        "silver_query_deictic_or_ambiguous_count_by_family",
        "silver_repeated_prefix_cluster_member_count_by_family",
        "silver_source_family_route_ok_but_evidence_mismatch_count_by_family",
        "silver_supported_insufficient_evidence_count_by_family",
        "silver_unsupported_insufficient_evidence_count_by_family",
        "silver_over_abstain_candidate_count_by_family",
        "silver_answer_parser_fail_count_by_family",
        "silver_likely_answerable_but_answer_failed_count_by_family",
        "silver_target_not_in_topk_count_by_family",
        "silver_target_hit_but_insufficient_evidence_count_by_family",
        "silver_top1_source_atom_id_match_count",
        "silver_weak_likely_answerable_but_insufficient_evidence_count_by_family",
        "silver_weak_likely_answerable_but_claim_support_fail_count_by_family",
    )
    missing = [key for key in required if key not in counters]
    if missing:
        raise ValueError(f"v4_7_13 missing counters: {missing}")
    if counters["current_resolves_to"] != LOGICAL_RUN_KEY:
        raise ValueError("current must resolve to v4_7_13")
    if counters["official_metric_input_rows"] != 0 or counters["silver_official_metric_input_rows"] != 0:
        raise ValueError("v4_7_13 opened official metric rows")
    if counters["silver_promoted_to_gold_count"] != 0:
        raise ValueError("v4_7_13 promoted silver")
    if counters["protected_namespaces_touched"] != []:
        raise ValueError("v4_7_13 protected namespaces touched")
    for key in REQUIRED_FALSE_KEYS:
        if counters.get(key) is not False:
            raise ValueError(f"v4_7_13 opened forbidden counter: {key}")
    if counters["pdf_full_replay_eligible_count"] != 57:
        raise ValueError("v4_7_13 full PDF eligible count must be 57")
    full_pdf_replay = report.get("full_pdf_llm_replay") or {}
    if counters["pdf_full_replay_env_enabled"] is False and counters["pdf_generated_response_count"] != 0:
        raise ValueError("full PDF replay counted answers while replay was disabled")
    if counters["pdf_full_replay_env_enabled"] is False and full_pdf_replay.get("rows"):
        raise ValueError("disabled full PDF replay carried answer rows")
    if full_pdf_replay.get("status") != "FULL_PDF_LLM_REPLAY_COMPLETED_DIAGNOSTIC_ONLY" and full_pdf_replay.get("rows"):
        raise ValueError("fail-closed full PDF replay carried answer rows")
    live_replay = report.get("live_silver_retrieval_replay") or {}
    if counters["live_silver_retrieval_env_enabled"] is False and counters["live_silver_retrieval_row_count"] != 0:
        raise ValueError("live silver replay counted rows while disabled")
    if live_replay.get("status") != "LIVE_SILVER_RETRIEVAL_REPLAY_COMPLETED_DIAGNOSTIC_ONLY" and live_replay.get("rows"):
        raise ValueError("fail-closed live retrieval replay carried rows")
    for key in (
        "live_vector_payload_evidence_truth_violation_count",
        "live_raw_pdf_query_time_parsing_attempt_count",
        "live_raw_xlsx_query_time_parsing_attempt_count",
        "live_source_title_shortcut_used_count",
        "live_direct_answer_value_matching_used_count",
        "live_hidden_target_locator_used_count",
        "live_expected_or_supporting_gold_text_used_count",
        "retrieval_tooling_wrong_family_tool_invocation_count",
        "retrieval_tooling_missing_required_layer_count",
        "tooling_counter_scope_mismatch_count",
    ):
        if int(counters.get(key) or 0) != 0:
            raise ValueError(f"v4_7_13 unsafe or inconsistent counter nonzero: {key}")
    overlay = report.get("silver_answerability_overlay") or {}
    if overlay.get("diagnostic_silver_only") is not True or overlay.get("silver_regenerated") is not False:
        raise ValueError("v4_7_13 overlay must stay diagnostic silver only")
    if counters["silver_answerability_overlay_row_count"] != counters["silver_prior_smoke_row_count"]:
        raise ValueError("v4_7_13 overlay row count mismatch")
    if (report.get("retrieval_tooling_audit") or {}).get("scope") != "retrieval_only":
        raise ValueError("v4_7_13 retrieval tooling scope mismatch")
    if (report.get("answer_generation_tooling_audit") or {}).get("scope") != "answer_generation_only":
        raise ValueError("v4_7_13 answer tooling scope mismatch")
