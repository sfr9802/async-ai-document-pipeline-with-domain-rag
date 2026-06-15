from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import rag_local_llm_expected_answer_generation_v1 as local_llm
import rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod as v47


ROOT = v47.ROOT
REPORT_DIR = v47.REPORT_DIR
STATUS_JSONL = v47.STATUS_JSONL
PROGRESS_DOC = v47.PROGRESS_DOC
MEASUREMENTS_DOC = v47.MEASUREMENTS_DOC
TRIAGE_DOC = v47.TRIAGE_DOC
README = v47.README
EVAL_README = v47.EVAL_README
SCRIPTS_README = ROOT / "ai" / "scripts" / "README.md"

V4_NAME = v47.V4_NAME
V4_RUN_FAMILY = v47.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod"
EVENT_TYPE = "diagnostic_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod"
STATUS = "V4_7_4_PDF_SURVIVOR_RETRIEVAL_EVIDENCE_ANSWER_QUALITY_REPLAY_NONPROD_READY"
REPORT_SCHEMA_VERSION = "rag_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_report_v1"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"

SOURCE_RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod"
SOURCE_HYDRATION_RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod"
SOURCE_REPORT_JSON = REPORT_DIR / "quality" / SOURCE_RUN_ID / "report.json"
HYDRATION_PACKET_CSV = REPORT_DIR / "quality" / SOURCE_HYDRATION_RUN_ID / "review_packet_ko_hydrated.csv"
HYDRATION_REPORT_JSON = REPORT_DIR / "quality" / SOURCE_HYDRATION_RUN_ID / "report.json"

ALLOWED_ARTIFACT_NAMES = {"report.json"}
FAILURE_BUCKETS = (
    "FILE_IDENTITY_MISS",
    "FILE_IDENTITY_AMBIGUOUS",
    "RIGHT_FILE_WRONG_PAGE",
    "RIGHT_PAGE_WEAK_WINDOW",
    "TABLE_OR_FIGURE_STRUCTURE_LOST",
    "CONTEXT_NEIGHBOR_MISSING",
    "EVIDENCE_UNDERUSE",
    "OVER_ABSTAIN",
    "UNSUPPORTED_CLAIM_RISK",
    "ANSWER_READY",
    "CONTRACT_FAIL_CLOSED",
)
FORBIDDEN_TEXT_PATTERNS = (
    r"\bD:[\\/]",
    r"v4_7_external_pdf_document_sha256_",
    r"v4_7_external_xlsx_workbook_sha256_",
    r"source_identity_key",
    r"(?<!hidden_)target_locator",
    r"(?<!hidden_target_or_)gold_locator",
    r"expected_answer_used_as_source",
    r"supporting_evidence_used_as_source",
    r"official_metric_input_rows\.jsonl",
    r"prompt_payload",
    r"raw_llm_response",
    r"raw_response_payload",
    r"checkpoint artifact written",
    r"formula_text",
)
STOP_TOKENS = {
    "그리고",
    "관련",
    "대한",
    "무엇",
    "무엇인가요",
    "설명",
    "어떤",
    "있나요",
    "있습니까",
    "해주세요",
}


def clean(value: Any) -> str:
    return v47.clean(value)


def utc_now() -> str:
    return v47.utc_now()


def sha256_file(path: Path) -> str:
    return v47.sha256_file(path)


def repo_relative(path: Path) -> str:
    return v47.repo_relative(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v47.write_json(path, payload)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v47.read_jsonl(path)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v47.write_jsonl(path, rows)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise AssertionError(f"CSV has no rows: {path}")
    return rows


def stable_payload_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", value)
        if token not in STOP_TOKENS
    }


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {"numerator": numerator, "denominator": denominator, "rate": numerator / denominator if denominator else None}


def contains_forbidden_text(payload: Any) -> bool:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return any(re.search(pattern, text) for pattern in FORBIDDEN_TEXT_PATTERNS)


def bounded(value: Any, *, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", clean(value)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def validate_source_report(source_report: Mapping[str, Any]) -> None:
    if source_report.get("run_id") != SOURCE_RUN_ID:
        raise AssertionError("unexpected v4_7_3 source report")
    if source_report.get("status") != "V4_7_3_HUMAN_REVIEWED_KOREAN_QUERY_CANDIDATE_PASS_EXCLUSION_APPLICATION_NONPROD_READY":
        raise AssertionError("v4_7_3 source report status drifted")
    if source_report.get("official_metric_input_rows") != 0:
        raise AssertionError("v4_7_3 source report must not contain official metric input rows")
    if source_report.get("passed_counts_by_family") != {"PDF": 58, "TEXT": 0, "XLSX": 0}:
        raise AssertionError("v4_7_3 passed family counts drifted")
    if len(source_report.get("passed_query_candidates") or []) != 58:
        raise AssertionError("v4_7_3 passed query candidate count drifted")


def select_pdf_survivors(
    source_report: Mapping[str, Any],
    hydration_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    validate_source_report(source_report)
    by_hash = {
        (clean(row.get("candidate_id_hash")), clean(row.get("query_id_hash"))): row
        for row in hydration_rows
    }
    survivors: list[dict[str, Any]] = []
    for passed in source_report["passed_query_candidates"]:
        if clean(passed.get("source_family")).upper() != "PDF":
            continue
        if passed.get("query_candidate_passed") is not True:
            continue
        key = (clean(passed.get("candidate_id_hash")), clean(passed.get("query_id_hash")))
        hydrated = by_hash.get(key)
        if hydrated is None:
            raise AssertionError(f"missing v4_7_2 hydrated row for survivor {key}")
        if clean(hydrated.get("source_family") or hydrated.get("소스계열")).upper() != "PDF":
            raise AssertionError("v4_7_3 PDF survivor matched non-PDF hydrated row")
        survivors.append({"decision": dict(passed), "hydrated": dict(hydrated)})
    if len(survivors) != 58:
        raise AssertionError("v4_7_4 must select exactly 58 PDF survivors")
    return survivors


def build_answer_prompt(row: Mapping[str, Any]) -> str:
    return json.dumps(
        {
            "task": "diagnostic_pdf_evidence_bound_answer_replay",
            "instructions": [
                "Return exactly one JSON object.",
                "Use only the provided Korean query and bounded evidence excerpt.",
                "If the excerpt is insufficient, set abstain=true and final_answer=''.",
                "Do not add facts from memory or from document titles.",
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
            "query": row["query_text"],
            "bounded_evidence_excerpt": row["evidence_snippet_preview"],
            "locator": row["locator_preview_redacted"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def verify_claim_support(final_answer: str, evidence: str, abstain: bool, unsupported_flag: bool) -> bool:
    if abstain or unsupported_flag or not clean(final_answer):
        return False
    return len(tokens(final_answer) & tokens(evidence)) >= 2


def classify_row_base(row: Mapping[str, Any]) -> list[str]:
    buckets: list[str] = []
    if row["document_candidate_count"] == 0:
        buckets.append("FILE_IDENTITY_MISS")
    if row["document_candidate_count"] > 1:
        buckets.append("FILE_IDENTITY_AMBIGUOUS")
    if not row["page_locator_signal_present"]:
        buckets.append("RIGHT_FILE_WRONG_PAGE")
    if row["weak_evidence_window"]:
        buckets.append("RIGHT_PAGE_WEAK_WINDOW")
        buckets.append("CONTEXT_NEIGHBOR_MISSING")
    if row["table_or_figure_candidate_available"] and row["weak_evidence_window"]:
        buckets.append("TABLE_OR_FIGURE_STRUCTURE_LOST")
    if row["answer_ready_evidence_bundle"]:
        buckets.append("ANSWER_READY")
    else:
        buckets.append("CONTRACT_FAIL_CLOSED")
    return list(dict.fromkeys(buckets))


def local_llm_status(
    *,
    execute_llm: bool,
    llm_backend: str,
    llm_base_url: str,
    llm_model: str,
    timeout_seconds: int,
    llm_client: Any | None,
) -> dict[str, Any]:
    resolved = local_llm.resolve_base_url(llm_backend, llm_base_url)
    if not execute_llm:
        return {
            "local_llm_available": False,
            "local_llm_unavailable": True,
            "local_llm_blockers": ["L8_GENERATION_DISABLED_BY_CHECK_OR_IDEMPOTENCE_MODE"],
            "backend": llm_backend,
            "base_url_redacted": "localhost",
            "model": clean(llm_model),
        }
    if llm_client is not None:
        return {
            "local_llm_available": True,
            "local_llm_unavailable": False,
            "local_llm_blockers": [],
            "backend": "injected-test-client",
            "base_url_redacted": "injected",
            "model": "injected",
        }
    blockers = local_llm.local_llm_entry_blockers(
        backend=llm_backend,
        base_url=resolved,
        model=llm_model,
        check_endpoint=True,
        timeout_seconds=min(timeout_seconds, 10),
    )
    return {
        "local_llm_available": not blockers,
        "local_llm_unavailable": bool(blockers),
        "local_llm_blockers": blockers,
        "backend": llm_backend,
        "base_url_redacted": "localhost",
        "model": clean(llm_model),
    }


def build_base_replay_rows(survivors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_locators: Counter[tuple[str, str, str]] = Counter()
    for index, item in enumerate(survivors, start=1):
        decision = item["decision"]
        hydrated = item["hydrated"]
        snippet = clean(hydrated.get("근거후보_스니펫") or hydrated.get("evidence_preview_redacted"))
        locator = clean(hydrated.get("근거후보_위치") or hydrated.get("locator_preview_redacted"))
        page = clean(hydrated.get("페이지_후보") or hydrated.get("page_or_sheet_locator_redacted"))
        paragraph = clean(hydrated.get("문단_후보"))
        sufficiency = clean(hydrated.get("근거후보_충분성_기계판단"))
        query_text = clean(decision.get("query_text") or hydrated.get("질의문"))
        evidence_tokens = tokens(snippet + " " + clean(hydrated.get("섹션_후보")))
        query_overlap = len(tokens(query_text) & evidence_tokens)
        document_hash = clean(hydrated.get("document_or_workbook_identity_hash"))
        doc_count = 1 if document_hash else 0
        page_present = bool(page and re.search(r"\d+", page))
        block_present = "block=" in locator or bool(paragraph)
        table_or_figure = bool(re.search(r"(표|table|figure|그림)", snippet + " " + clean(hydrated.get("섹션_후보")), re.I))
        evidence_created = bool(snippet and locator and doc_count)
        answer_ready = evidence_created and sufficiency == "충분후보"
        weak_window = evidence_created and not answer_ready
        locator_key = (document_hash, page, paragraph or locator)
        seen_locators[locator_key] += 1
        row = {
            "row_index_1based": index,
            "source_family": "PDF",
            "candidate_id": clean(decision.get("candidate_id")),
            "query_id": clean(decision.get("query_id")),
            "candidate_id_hash": clean(decision.get("candidate_id_hash")),
            "query_id_hash": clean(decision.get("query_id_hash")),
            "decision_status": "user_passed_query_candidate",
            "query_candidate_passed": True,
            "query_text": query_text,
            "query_text_sha256": sha256_text(query_text),
            "document_candidate_count": doc_count,
            "file_identity_hit_proxy_at1": doc_count == 1 and evidence_created,
            "file_identity_hit_proxy_at3": doc_count >= 1 and evidence_created,
            "query_visible_locator_signal_present": query_overlap > 0,
            "query_evidence_token_overlap_count": query_overlap,
            "page_locator_signal_present": page_present,
            "page_candidate_hit_proxy_at1": page_present and evidence_created,
            "page_candidate_hit_proxy_at3": page_present and evidence_created,
            "block_candidate_available": block_present,
            "table_or_figure_candidate_available": table_or_figure,
            "bbox_metric_computed": False,
            "evidence_bundle_created": evidence_created,
            "source_atom_hydration_success": evidence_created,
            "evidence_window_sufficient_proxy": answer_ready,
            "weak_evidence_window": weak_window,
            "missing_neighbor_context": weak_window,
            "duplicate_or_redundant_evidence": False,
            "citation_candidate": evidence_created,
            "citation_support_proxy": answer_ready and query_overlap > 0,
            "vector_payload_evidence_truth_violation": False,
            "answer_ready_evidence_bundle": answer_ready,
            "evidence_bundle_source": "v4_7_2_hydrated_packet_bounded_preview",
            "SearchView_vector_payload_role": "candidate_only",
            "SourceAtom_EvidenceBundle_role": "evidence_truth",
            "evidence_snippet_sha256": sha256_text(snippet),
            "evidence_snippet_preview": bounded(snippet, limit=360),
            "locator_preview_redacted": bounded(locator, limit=160),
            "page_candidate": page,
            "block_candidate": paragraph,
            "raw_pdf_query_time_parsing": False,
            "broad_source_atom_scan_attempted": False,
            "hidden_target_locator_used": False,
            "expected_or_supporting_gold_text_used": False,
            "source_file_title_shortcut_used": False,
            "llm_invoked": False,
            "answer_quality_diagnostics": {},
            "failure_buckets": [],
        }
        row["failure_buckets"] = classify_row_base(row)
        rows.append(row)
    duplicate_keys = {key for key, count in seen_locators.items() if count > 1}
    for row in rows:
        duplicate = (clean(row.get("document_or_workbook_identity_hash")), row["page_candidate"], row["block_candidate"]) in duplicate_keys
        row["duplicate_or_redundant_evidence"] = duplicate
    return rows


def run_llm_answer_replay(
    rows: list[dict[str, Any]],
    *,
    execute_llm: bool,
    llm_backend: str,
    llm_base_url: str,
    llm_model: str,
    llm_timeout_seconds: int,
    llm_max_tokens: int,
    llm_client: Any | None,
) -> dict[str, Any]:
    status = local_llm_status(
        execute_llm=execute_llm,
        llm_backend=llm_backend,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        timeout_seconds=llm_timeout_seconds,
        llm_client=llm_client,
    )
    if not status["local_llm_available"]:
        for row in rows:
            if row["answer_ready_evidence_bundle"] and "CONTRACT_FAIL_CLOSED" not in row["failure_buckets"]:
                row["failure_buckets"].append("CONTRACT_FAIL_CLOSED")
        return status
    resolved = local_llm.resolve_base_url(llm_backend, llm_base_url)
    for row in rows:
        if not row["answer_ready_evidence_bundle"]:
            continue
        prompt = build_answer_prompt(row)
        diagnostics: dict[str, Any] = {
            "prompt_sha256": sha256_text(prompt),
            "strict_json": True,
            "raw_response_sha256": "",
            "parse_status": "not_invoked",
            "final_answer_preview": "",
            "abstain": False,
            "citation_count": 0,
            "claim_support_verifier_pass": False,
            "unsupported_claim_risk": False,
            "evidence_underuse_flag": False,
            "context_understanding_miss": False,
            "over_abstain_candidate": False,
            "answer_plan_created": False,
        }
        try:
            parsed, meta = local_llm.call_local_llm_strict_json(
                backend=llm_backend,
                base_url=resolved,
                model=llm_model,
                prompt=prompt,
                temperature=0.0,
                max_tokens=llm_max_tokens,
                timeout_seconds=llm_timeout_seconds,
                llm_client=llm_client,
            )
            final_answer = bounded(parsed.get("final_answer"), limit=420)
            abstain = parsed.get("abstain") is True
            citations = parsed.get("citations") if isinstance(parsed.get("citations"), list) else []
            unsupported = parsed.get("unsupported_claim_risk") is True
            underuse = parsed.get("evidence_underuse_flag") is True
            context_miss = parsed.get("context_understanding_miss") is True
            over_abstain = parsed.get("over_abstain_candidate") is True or (abstain and row["answer_ready_evidence_bundle"])
            verifier_pass = verify_claim_support(final_answer, row["evidence_snippet_preview"], abstain, unsupported)
            diagnostics.update(
                {
                    "raw_response_sha256": clean(meta.get("raw_response_sha256")),
                    "parse_status": "parsed",
                    "final_answer_preview": final_answer,
                    "parsed_final_answer_present": bool(final_answer),
                    "abstain": abstain,
                    "citation_count": len([item for item in citations if clean(item)]),
                    "citation_rendered": bool(citations),
                    "claim_support_verifier_pass": verifier_pass,
                    "unsupported_claim_risk": unsupported or (bool(final_answer) and not verifier_pass),
                    "evidence_underuse_flag": underuse or (bool(final_answer) and len(tokens(final_answer) & tokens(row["evidence_snippet_preview"])) < 2),
                    "context_understanding_miss": context_miss,
                    "over_abstain_candidate": over_abstain,
                    "answer_plan_created": bool(clean(parsed.get("answer_plan"))),
                }
            )
            row["llm_invoked"] = True
            row["answer_quality_diagnostics"] = diagnostics
            if diagnostics["unsupported_claim_risk"]:
                row["failure_buckets"].append("UNSUPPORTED_CLAIM_RISK")
            if diagnostics["evidence_underuse_flag"]:
                row["failure_buckets"].append("EVIDENCE_UNDERUSE")
            if diagnostics["over_abstain_candidate"]:
                row["failure_buckets"].append("OVER_ABSTAIN")
            if diagnostics["context_understanding_miss"]:
                row["failure_buckets"].append("CONTEXT_NEIGHBOR_MISSING")
        except Exception as exc:
            diagnostics.update(
                {
                    "parse_status": "fail_closed",
                    "failure_reason": type(exc).__name__,
                }
            )
            row["answer_quality_diagnostics"] = diagnostics
            row["failure_buckets"].append("CONTRACT_FAIL_CLOSED")
    return status


def build_metrics(rows: Sequence[Mapping[str, Any]], llm_status: Mapping[str, Any]) -> dict[str, Any]:
    row_count = len(rows)
    answer_ready = [row for row in rows if row["answer_ready_evidence_bundle"]]
    llm_rows = [row for row in rows if row["llm_invoked"]]
    diagnostics = [row.get("answer_quality_diagnostics") or {} for row in llm_rows]
    taxonomy_counter: Counter[str] = Counter()
    for row in rows:
        taxonomy_counter.update(row.get("failure_buckets") or [])
    taxonomy = {bucket: taxonomy_counter.get(bucket, 0) for bucket in FAILURE_BUCKETS}
    return {
        "file_identity": {
            "pdf_survivor_row_count": row_count,
            "document_candidate_count_by_row": [int(row["document_candidate_count"]) for row in rows],
            "file_identity_hit_proxy_at1": sum(1 for row in rows if row["file_identity_hit_proxy_at1"]),
            "file_identity_hit_proxy_at3": sum(1 for row in rows if row["file_identity_hit_proxy_at3"]),
            "file_identity_hit_proxy_at1_ratio": ratio(sum(1 for row in rows if row["file_identity_hit_proxy_at1"]), row_count),
            "file_identity_hit_proxy_at3_ratio": ratio(sum(1 for row in rows if row["file_identity_hit_proxy_at3"]), row_count),
            "abstain_or_disambiguation_count": sum(1 for row in rows if row["document_candidate_count"] != 1),
            "wrong_file_forcing_risk_count": 0,
            "query_visible_locator_signal_present_count": sum(
                1 for row in rows if row["query_visible_locator_signal_present"]
            ),
            "hidden_target_or_gold_locator_used": False,
        },
        "locator": {
            "page_locator_signal_present_count": sum(1 for row in rows if row["page_locator_signal_present"]),
            "page_candidate_hit_proxy_at1": sum(1 for row in rows if row["page_candidate_hit_proxy_at1"]),
            "page_candidate_hit_proxy_at3": sum(1 for row in rows if row["page_candidate_hit_proxy_at3"]),
            "block_candidate_available_count": sum(1 for row in rows if row["block_candidate_available"]),
            "table_or_figure_candidate_available_count": sum(
                1 for row in rows if row["table_or_figure_candidate_available"]
            ),
            "bbox_metric_computed": False,
        },
        "evidence_bundle": {
            "evidence_bundle_created_count": sum(1 for row in rows if row["evidence_bundle_created"]),
            "source_atom_hydration_success_count": sum(1 for row in rows if row["source_atom_hydration_success"]),
            "evidence_window_sufficient_proxy_count": sum(
                1 for row in rows if row["evidence_window_sufficient_proxy"]
            ),
            "weak_evidence_window_count": sum(1 for row in rows if row["weak_evidence_window"]),
            "missing_neighbor_context_count": sum(1 for row in rows if row["missing_neighbor_context"]),
            "duplicate_or_redundant_evidence_count": sum(
                1 for row in rows if row["duplicate_or_redundant_evidence"]
            ),
            "citation_candidate_count": sum(1 for row in rows if row["citation_candidate"]),
            "citation_support_proxy_count": sum(1 for row in rows if row["citation_support_proxy"]),
            "vector_payload_evidence_truth_violation_count": 0,
        },
        "llm_answer_quality": {
            "local_llm_available": bool(llm_status["local_llm_available"]),
            "local_llm_unavailable": bool(llm_status["local_llm_unavailable"]),
            "local_llm_blocker_count": len(llm_status.get("local_llm_blockers") or []),
            "local_llm_backend": clean(llm_status.get("backend")),
            "local_llm_model": clean(llm_status.get("model")),
            "answer_ready_evidence_bundle_count": len(answer_ready),
            "L8_generation_executed": bool(llm_status["local_llm_available"] and llm_rows),
            "generated_response_count": len(llm_rows),
            "parsed_final_answer_present_count": sum(
                1 for diag in diagnostics if diag.get("parsed_final_answer_present") is True
            ),
            "citation_rendered_count": sum(1 for diag in diagnostics if diag.get("citation_rendered") is True),
            "abstain_count": sum(1 for diag in diagnostics if diag.get("abstain") is True)
            + (len(answer_ready) if not llm_status["local_llm_available"] else 0),
            "unsupported_claim_risk_count": sum(1 for diag in diagnostics if diag.get("unsupported_claim_risk") is True),
            "evidence_underuse_flag_count": sum(1 for diag in diagnostics if diag.get("evidence_underuse_flag") is True),
            "over_abstain_candidate_count": sum(
                1 for diag in diagnostics if diag.get("over_abstain_candidate") is True
            ),
            "context_understanding_miss_count": sum(
                1 for diag in diagnostics if diag.get("context_understanding_miss") is True
            ),
            "answer_plan_created_count": sum(1 for diag in diagnostics if diag.get("answer_plan_created") is True),
            "claim_support_verifier_pass_count": sum(
                1 for diag in diagnostics if diag.get("claim_support_verifier_pass") is True
            ),
            "claim_support_verifier_fail_count": sum(
                1
                for diag in diagnostics
                if diag.get("parse_status") == "parsed" and diag.get("claim_support_verifier_pass") is not True
            ),
            "fail_closed_before_llm_count": sum(1 for row in rows if not row["answer_ready_evidence_bundle"]),
            "fake_answer_emitted_count": 0,
        },
        "failure_taxonomy": taxonomy,
    }


def build_report(
    *,
    source_report_path: Path = SOURCE_REPORT_JSON,
    hydration_packet_csv_path: Path = HYDRATION_PACKET_CSV,
    generated_at: str | None = None,
    execute_llm: bool = True,
    llm_backend: str = local_llm.DEFAULT_BACKEND,
    llm_base_url: str = "",
    llm_model: str = local_llm.DEFAULT_MODEL,
    llm_timeout_seconds: int = 90,
    llm_max_tokens: int = 520,
    llm_client: Any | None = None,
) -> dict[str, Any]:
    source_report = read_json(source_report_path)
    hydration_rows = read_csv_rows(hydration_packet_csv_path)
    survivors = select_pdf_survivors(source_report, hydration_rows)
    rows = build_base_replay_rows(survivors)
    llm_status = run_llm_answer_replay(
        rows,
        execute_llm=execute_llm,
        llm_backend=llm_backend,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_timeout_seconds=llm_timeout_seconds,
        llm_max_tokens=llm_max_tokens,
        llm_client=llm_client,
    )
    metrics = build_metrics(rows, llm_status)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "source_run_id": SOURCE_RUN_ID,
        "source_hydration_run_id": SOURCE_HYDRATION_RUN_ID,
        "status": STATUS,
        "generated_at": generated_at or utc_now(),
        "diagnostic_only": True,
        "non_production": True,
        "pdf_survivor_row_count": len(rows),
        "xlsx_rows_in_scope": 0,
        "text_rows_in_scope": 0,
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
        "raw_pdf_query_time_parsing": False,
        "broad_source_atom_scan_attempt_count": 0,
        "vector_payload_evidence_truth_violation_count": 0,
        "hidden_target_locator_used": False,
        "expected_or_supporting_gold_text_used": False,
        "source_file_title_shortcut_used": False,
        "SearchView_vector_payload_role": "candidate_only",
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "source_report_path": repo_relative(source_report_path),
        "source_hydration_packet_path": repo_relative(hydration_packet_csv_path),
        "source_report_sha256": sha256_file(source_report_path),
        "source_hydration_packet_sha256": sha256_file(hydration_packet_csv_path),
        "artifact_paths": {"report_json": repo_relative(REPORT_JSON)},
        "sidecar_artifacts_created": [],
        "metrics": metrics,
        "pdf_survivor_replay_ledger": rows,
        "pdf_survivor_selection_sha256": stable_payload_sha256(
            [(row["candidate_id_hash"], row["query_id_hash"]) for row in rows]
        ),
        "deterministic_replay_input_sha256": stable_payload_sha256(
            [
                {
                    "candidate_id_hash": row["candidate_id_hash"],
                    "query_id_hash": row["query_id_hash"],
                    "query_text_sha256": row["query_text_sha256"],
                    "evidence_snippet_sha256": row["evidence_snippet_sha256"],
                    "locator": row["locator_preview_redacted"],
                }
                for row in rows
            ]
        ),
        "residual_risks": [
            "only PDF survivor candidates are measured",
            "no official labels/gold/expected evidence are available",
            "evidence hit metrics are proxy diagnostics unless user later opens gold/evidence adjudication",
            "XLSX remains parked because v4_7_3 passed XLSX count is 0",
        ],
    }
    check_report(report)
    return report


def check_report(report: Mapping[str, Any]) -> None:
    false_flags = (
        "official_metric",
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
        "raw_pdf_query_time_parsing",
        "vector_payload_evidence_truth_violation_count",
        "hidden_target_locator_used",
        "expected_or_supporting_gold_text_used",
        "source_file_title_shortcut_used",
    )
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise AssertionError("unexpected v4_7_4 report schema")
    if report.get("run_id") != RUN_ID or report.get("status") != STATUS:
        raise AssertionError("unexpected v4_7_4 report identity/status")
    if report.get("source_run_id") != SOURCE_RUN_ID:
        raise AssertionError("v4_7_4 source run id drifted")
    if report.get("source_hydration_run_id") != SOURCE_HYDRATION_RUN_ID:
        raise AssertionError("v4_7_4 hydration source run id drifted")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise AssertionError("v4_7_4 must remain diagnostic-only and non-production")
    if report.get("pdf_survivor_row_count") != 58 or report.get("xlsx_rows_in_scope") != 0:
        raise AssertionError("v4_7_4 target row counts drifted")
    if report.get("official_metric_input_rows") != 0:
        raise AssertionError("official metric input rows must remain 0")
    for flag in false_flags:
        if report.get(flag) not in {False, 0}:
            raise AssertionError(f"{flag} must remain false/zero")
    if report.get("broad_source_atom_scan_attempt_count") != 0:
        raise AssertionError("broad source atom scans are forbidden")
    if report.get("protected_namespaces_touched") != []:
        raise AssertionError("protected namespaces must remain untouched")
    metrics = report.get("metrics") if isinstance(report.get("metrics"), Mapping) else {}
    for key in ("file_identity", "locator", "evidence_bundle", "llm_answer_quality", "failure_taxonomy"):
        if key not in metrics:
            raise AssertionError(f"missing metric section: {key}")
    evidence = metrics["evidence_bundle"]
    if evidence.get("evidence_bundle_created_count") != 58:
        raise AssertionError("all PDF survivors must have evidence bundles from the hydrated packet")
    if evidence.get("evidence_window_sufficient_proxy_count") != 35:
        raise AssertionError("expected 35 sufficient evidence-window proxies")
    if evidence.get("weak_evidence_window_count") != 23:
        raise AssertionError("expected 23 weak evidence-window proxies")
    if metrics["llm_answer_quality"].get("answer_ready_evidence_bundle_count") != 35:
        raise AssertionError("LLM replay answer-ready count must be 35")
    rows = list(report.get("pdf_survivor_replay_ledger") or [])
    if len(rows) != 58:
        raise AssertionError("PDF survivor replay ledger must have 58 rows")
    if any(row.get("source_family") != "PDF" for row in rows):
        raise AssertionError("v4_7_4 ledger must be PDF-only")
    if any(row.get("llm_invoked") and row.get("answer_ready_evidence_bundle") is not True for row in rows):
        raise AssertionError("LLM must not run for non-answer-ready rows")
    if contains_forbidden_text(report):
        raise AssertionError("forbidden local/source/oracle text leaked into v4_7_4 report")


def write_artifacts(report: Mapping[str, Any], *, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    unexpected = {path.name for path in output_dir.iterdir() if path.name not in ALLOWED_ARTIFACT_NAMES}
    if unexpected:
        raise RuntimeError(f"unexpected v4_7_4 artifacts present: {sorted(unexpected)}")
    write_json(output_dir / "report.json", report)
    return dict(report)


def check_written_artifacts(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    files = {path.name for path in output_dir.iterdir()} if output_dir.exists() else set()
    if files != ALLOWED_ARTIFACT_NAMES:
        raise AssertionError(f"unexpected v4_7_4 artifact set: {sorted(files)}")
    report = read_json(output_dir / "report.json")
    check_report(report)
    return report


def status_event(report: Mapping[str, Any]) -> dict[str, Any]:
    metrics = report["metrics"]
    return {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": {"report_json_sha256": sha256_file(REPORT_JSON)},
        "diagnostic_only": True,
        "non_production": True,
        "pdf_survivor_row_count": 58,
        "xlsx_rows_in_scope": 0,
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
        "raw_pdf_query_time_parsing": False,
        "broad_source_atom_scan_attempt_count": 0,
        "vector_payload_evidence_truth_violation_count": 0,
        "hidden_target_locator_used": False,
        "expected_or_supporting_gold_text_used": False,
        "source_file_title_shortcut_used": False,
        "file_identity_hit_proxy_at1": metrics["file_identity"]["file_identity_hit_proxy_at1"],
        "file_identity_hit_proxy_at3": metrics["file_identity"]["file_identity_hit_proxy_at3"],
        "page_locator_signal_present_count": metrics["locator"]["page_locator_signal_present_count"],
        "evidence_bundle_created_count": metrics["evidence_bundle"]["evidence_bundle_created_count"],
        "evidence_window_sufficient_proxy_count": metrics["evidence_bundle"]["evidence_window_sufficient_proxy_count"],
        "weak_evidence_window_count": metrics["evidence_bundle"]["weak_evidence_window_count"],
        "generated_response_count": metrics["llm_answer_quality"]["generated_response_count"],
        "local_llm_available": metrics["llm_answer_quality"]["local_llm_available"],
        "source_run_id": SOURCE_RUN_ID,
        "source_hydration_run_id": SOURCE_HYDRATION_RUN_ID,
        "pdf_survivor_selection_sha256": report["pdf_survivor_selection_sha256"],
        "deterministic_replay_input_sha256": report["deterministic_replay_input_sha256"],
    }


def update_status(report: Mapping[str, Any]) -> None:
    event = status_event(report)
    rows = [
        row
        for row in read_jsonl(STATUS_JSONL)
        if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)
    ]
    rows.append(event)
    write_jsonl(STATUS_JSONL, rows)


def update_root_readme(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    snapshot = f"""## Current RAG Diagnostic Status

- Current RAG status: `{STATUS}`.
- Phase: v4_7 remains pre-official. v4_7_4 replays the v4_7_3 user-passed PDF survivor set only; XLSX remains parked because v4_7_3 passed XLSX count is 0.
- v4_7_2 supersedes the abstract v4_7_1 Korean review packet with source-grounded Korean query candidates; hydrated rows 204, PDF 100, XLSX 104, and non-empty `질의문` 204. v4_7_3 applies the user-reviewed Korean query candidate CSV with `미검수=통과`; v4_7_4 now measures PDF survivor retrieval/evidence/answer-quality proxies.
- v4_7_4 counters: PDF survivor 58, evidence_bundle_created {metrics["evidence_bundle"]["evidence_bundle_created_count"]}, evidence_window_sufficient_proxy {metrics["evidence_bundle"]["evidence_window_sufficient_proxy_count"]}, weak_evidence_window {metrics["evidence_bundle"]["weak_evidence_window_count"]}, generated_response_count {metrics["llm_answer_quality"]["generated_response_count"]}.
- Rolling evidence docs: `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md` remain the canonical human-readable status ledgers; this replay is not production promotion evidence.
- Hard boundary: not official metric, not gold/qrels, not relevance/answerability labels, not expected answer/evidence approval, not product-success evidence, not promotion evidence, not FT-A execution, not fine-tuning, not training data, and not live DB/index/cache readiness. Locked flags remain `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `ft_a_execution=false`, `fine_tuning=false`, `fine_tuning_executed=false`, and `live_db_index_cache_readiness=false`.
"""
    text = README.read_text(encoding="utf-8")
    if "## Current RAG Diagnostic Status" in text:
        text = re.sub(
            r"## Current RAG Diagnostic Status\n.*?(?=\n## (?:Recent Focus:|전체 구조|구성 요소|폴더 구조))",
            snapshot.rstrip() + "\n",
            text,
            count=1,
            flags=re.S,
        )
    elif "\n## 전체 구조" in text:
        text = text.replace("\n## 전체 구조", "\n" + snapshot.rstrip() + "\n\n## 전체 구조", 1)
    else:
        text = text.rstrip() + "\n\n" + snapshot.rstrip() + "\n"
    script_name = "rag_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod.py"
    if "## 로컬 실행 메모" in text and "## 라이선스와 외부 데이터" in text:
        start = text.index("## 로컬 실행 메모")
        end = text.index("## 라이선스와 외부 데이터")
        section = text[start:end]
        compile_cmd = f"python -X utf8 -m py_compile ai\\scripts\\{script_name}"
        check_cmd = f"python -X utf8 ai\\scripts\\{script_name} --check"
        if compile_cmd not in section:
            section = section.replace(
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod.py\n",
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod.py\n"
                f"{compile_cmd}\n",
                1,
            )
        if check_cmd not in section:
            section = section.replace(
                "python -X utf8 ai\\scripts\\rag_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod.py --check\n",
                "python -X utf8 ai\\scripts\\rag_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod.py --check\n"
                f"{check_cmd}\n",
                1,
            )
        text = text[:start] + section + text[end:]
    README.write_text(text, encoding="utf-8")


def update_eval_readme(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    text = EVAL_README.read_text(encoding="utf-8")
    text = re.sub(r"- Current RAG status: `[^`]+`", f"- Current RAG status: `{STATUS}`", text, count=1)
    section = f"""## Korean human review packet

The previous v4_7_1 Korean review packet was abstract because v4_7 registration contained source-disjoint candidate identities but not query text. v4_7_2 superseded it with `reports/rag_eval/rag-ingestion/quality/{SOURCE_HYDRATION_RUN_ID}/review_packet_ko_hydrated.xlsx`, plus CSV/JSONL equivalents, containing actual Korean query candidates, bounded evidence previews, and locator previews. User-owned fields remain blank/default for expected answers, evidence judgment, relevance labels, answerability labels, official denominator inclusion, exclusion reasons, policy memo, reviewer, and review timestamp. v4_7_3 applies the user-reviewed CSV decisions with `검수상태=미검수` interpreted as pass when `제외사유` is blank.

v4_7_4 replays only the {report["pdf_survivor_row_count"]} user-passed PDF survivor candidates. It separates file-identity proxy, page/block locator proxy, EvidenceBundle sufficiency proxy, local-LLM answer replay, citation support proxy, and context-understanding failure buckets. Current counters include evidence_window_sufficient_proxy {metrics["evidence_bundle"]["evidence_window_sufficient_proxy_count"]}, weak_evidence_window {metrics["evidence_bundle"]["weak_evidence_window_count"]}, and generated_response_count {metrics["llm_answer_quality"]["generated_response_count"]}.

This is diagnostic-only replay. It is not official metric, not gold/qrels, not relevance or answerability labels, not expected answer/evidence approval, not training data, not product-success evidence, not promotion evidence, not FT-A execution, not fine-tuning, and not live DB/index/cache readiness. Locked flags include `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `fine_tuning=false`, `fine_tuning_executed=false`, and `live_db_index_cache_readiness=false`.
"""
    if "## Korean human review packet" in text:
        text = re.sub(
            r"## Korean human review packet\n.*?(?=\n## (?:Evaluation Boundary|평가 경계))",
            section.rstrip() + "\n",
            text,
            count=1,
            flags=re.S,
        )
    elif "\n## 평가 경계" in text:
        text = text.replace("\n## 평가 경계", "\n" + section.rstrip() + "\n\n## 평가 경계", 1)
    else:
        text = text.rstrip() + "\n\n" + section.rstrip() + "\n"
    EVAL_README.write_text(text, encoding="utf-8")


def update_scripts_readme() -> None:
    text = SCRIPTS_README.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod.py` | "
        "Replays only the v4_7_3 user-passed PDF survivor candidates through retrieval/evidence/answer-quality proxy diagnostics, "
        "using v4_7_2 bounded EvidenceBundle previews and optional local LLM generation while keeping official metrics, gold/qrels, "
        "labels, FT-A execution, fine-tuning, training data, promotion evidence, and live readiness closed. |"
    )
    pattern = r"\n?\| `rag_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod\.py` \| .*?\|"
    text = re.sub(pattern, "", text)
    text = text.replace(
        "\n\nv4 scripts remain diagnostic/non-production",
        f"\n{row}\n\nv4 scripts remain diagnostic/non-production",
        1,
    )
    SCRIPTS_README.write_text(text, encoding="utf-8")


def update_progress_doc(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    entry = (
        f"- v4_7_4 PDF survivor retrieval/evidence/answer quality replay (`{RUN_ID}`) is {STATUS}. "
        f"It replays only PDF survivor 58 rows from v4_7_3; XLSX remains out of scope because passed XLSX count is 0. "
        f"EvidenceBundle created {metrics['evidence_bundle']['evidence_bundle_created_count']} rows, sufficient proxy "
        f"{metrics['evidence_bundle']['evidence_window_sufficient_proxy_count']} rows, weak window "
        f"{metrics['evidence_bundle']['weak_evidence_window_count']} rows, generated_response_count "
        f"{metrics['llm_answer_quality']['generated_response_count']}. It is not official metric, gold/qrels, labels, "
        "expected-answer/evidence approval, training data, product-success evidence, promotion evidence, FT-A execution, "
        "fine-tuning, or live readiness."
    )
    v47.v4610.v469.v467.replace_marked_entry(PROGRESS_DOC, RUN_ID, entry)
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    text = re.sub(r"Overall status: `[^`]+`;", f"Overall status: `{STATUS}`;", text, count=1)
    PROGRESS_DOC.write_text(text, encoding="utf-8")


def update_measurements_doc(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    entry = f"""### v4_7_4 PDF Survivor Retrieval/Evidence/Answer Quality Replay

- Run: `{RUN_ID}`
- Primary artifact: `{repo_relative(REPORT_JSON)}`; row-level replay detail is embedded in `report.json` only.
- Interpretation: all metrics are diagnostic proxies over the v4_7_3 PDF survivor candidate set. They are not official metric rows and do not use gold/qrels, expected answers, supporting evidence approvals, hidden target locators, or source-file title shortcuts.

| Counter | Value |
|---|---:|
| pdf_survivor_row_count | {report["pdf_survivor_row_count"]} |
| xlsx_rows_in_scope | {report["xlsx_rows_in_scope"]} |
| file_identity_hit_proxy_at1 | {metrics["file_identity"]["file_identity_hit_proxy_at1"]} |
| file_identity_hit_proxy_at3 | {metrics["file_identity"]["file_identity_hit_proxy_at3"]} |
| page_locator_signal_present_count | {metrics["locator"]["page_locator_signal_present_count"]} |
| block_candidate_available_count | {metrics["locator"]["block_candidate_available_count"]} |
| evidence_bundle_created_count | {metrics["evidence_bundle"]["evidence_bundle_created_count"]} |
| source_atom_hydration_success_count | {metrics["evidence_bundle"]["source_atom_hydration_success_count"]} |
| evidence_window_sufficient_proxy_count | {metrics["evidence_bundle"]["evidence_window_sufficient_proxy_count"]} |
| weak_evidence_window_count | {metrics["evidence_bundle"]["weak_evidence_window_count"]} |
| citation_support_proxy_count | {metrics["evidence_bundle"]["citation_support_proxy_count"]} |
| generated_response_count | {metrics["llm_answer_quality"]["generated_response_count"]} |
| unsupported_claim_risk_count | {metrics["llm_answer_quality"]["unsupported_claim_risk_count"]} |
| context_understanding_miss_count | {metrics["llm_answer_quality"]["context_understanding_miss_count"]} |
| official_metric_input_rows | 0 |
| training_dataset_created | false |
"""
    v47.v4610.v469.v467.replace_marked_entry(MEASUREMENTS_DOC, RUN_ID, entry)


def update_triage_doc(report: Mapping[str, Any]) -> None:
    taxonomy = report["metrics"]["failure_taxonomy"]
    entry = f"""### v4_7_4 PDF Survivor Failure Taxonomy And Decision Boundary

- Run: `{RUN_ID}`
- Scope: PDF survivor 58 rows from v4_7_3 only. XLSX remains parked because v4_7_3 passed XLSX count is 0.
- Evidence boundary: SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only. Query-time raw PDF parsing, broad SourceAtom scans, hidden target/gold locator use, expected/supporting gold text use, and source-file title shortcuts remain disabled.
- Failure buckets: FILE_IDENTITY_MISS {taxonomy["FILE_IDENTITY_MISS"]}; FILE_IDENTITY_AMBIGUOUS {taxonomy["FILE_IDENTITY_AMBIGUOUS"]}; RIGHT_FILE_WRONG_PAGE {taxonomy["RIGHT_FILE_WRONG_PAGE"]}; RIGHT_PAGE_WEAK_WINDOW {taxonomy["RIGHT_PAGE_WEAK_WINDOW"]}; TABLE_OR_FIGURE_STRUCTURE_LOST {taxonomy["TABLE_OR_FIGURE_STRUCTURE_LOST"]}; CONTEXT_NEIGHBOR_MISSING {taxonomy["CONTEXT_NEIGHBOR_MISSING"]}; EVIDENCE_UNDERUSE {taxonomy["EVIDENCE_UNDERUSE"]}; OVER_ABSTAIN {taxonomy["OVER_ABSTAIN"]}; UNSUPPORTED_CLAIM_RISK {taxonomy["UNSUPPORTED_CLAIM_RISK"]}; ANSWER_READY {taxonomy["ANSWER_READY"]}; CONTRACT_FAIL_CLOSED {taxonomy["CONTRACT_FAIL_CLOSED"]}.
- It is not official metric, not product-success evidence, not promotion evidence, not FT-A execution, not fine-tuning, not training data, and not live DB/index/cache readiness.
"""
    v47.v4610.v469.v467.replace_marked_entry(TRIAGE_DOC, RUN_ID, entry)


def update_human_docs(report: Mapping[str, Any]) -> None:
    update_root_readme(report)
    update_eval_readme(report)
    update_scripts_readme()
    update_progress_doc(report)
    update_measurements_doc(report)
    update_triage_doc(report)


def run_write(
    *,
    source_report_path: Path = SOURCE_REPORT_JSON,
    hydration_packet_csv_path: Path = HYDRATION_PACKET_CSV,
    output_dir: Path = OUTPUT_DIR,
    update_docs: bool = True,
    execute_llm: bool = True,
    llm_backend: str = local_llm.DEFAULT_BACKEND,
    llm_base_url: str = "",
    llm_model: str = local_llm.DEFAULT_MODEL,
    llm_timeout_seconds: int = 90,
    llm_max_tokens: int = 520,
) -> dict[str, Any]:
    report = build_report(
        source_report_path=source_report_path,
        hydration_packet_csv_path=hydration_packet_csv_path,
        execute_llm=execute_llm,
        llm_backend=llm_backend,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_timeout_seconds=llm_timeout_seconds,
        llm_max_tokens=llm_max_tokens,
    )
    written = write_artifacts(report, output_dir=output_dir)
    check_written_artifacts(output_dir)
    if update_docs and output_dir == OUTPUT_DIR:
        update_status(written)
        update_human_docs(written)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--source-report", type=Path, default=SOURCE_REPORT_JSON)
    parser.add_argument("--hydration-packet-csv", type=Path, default=HYDRATION_PACKET_CSV)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--no-docs", action="store_true")
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--llm-backend", default=local_llm.DEFAULT_BACKEND, choices=["llamacpp", "openai-compatible", "ollama"])
    parser.add_argument("--llm-base-url", default="")
    parser.add_argument("--llm-model", default=local_llm.DEFAULT_MODEL)
    parser.add_argument("--llm-timeout-seconds", type=int, default=90)
    parser.add_argument("--llm-max-tokens", type=int, default=520)
    args = parser.parse_args(argv)
    if args.check:
        report = check_written_artifacts(args.output_dir)
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": report["status"],
                    "pdf_survivor_row_count": report["pdf_survivor_row_count"],
                    "xlsx_rows_in_scope": report["xlsx_rows_in_scope"],
                    "evidence_window_sufficient_proxy_count": report["metrics"]["evidence_bundle"][
                        "evidence_window_sufficient_proxy_count"
                    ],
                    "weak_evidence_window_count": report["metrics"]["evidence_bundle"]["weak_evidence_window_count"],
                    "generated_response_count": report["metrics"]["llm_answer_quality"]["generated_response_count"],
                    "official_metric_input_rows": 0,
                    "gold_mutation": False,
                    "qrels_mutation": False,
                    "label_mutation": False,
                    "training_dataset_created": False,
                    "ft_a_execution": False,
                    "fine_tuning": False,
                    "promotion_evidence": False,
                    "product_success_evidence_allowed": False,
                    "live_db_index_cache_readiness": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    report = run_write(
        source_report_path=args.source_report,
        hydration_packet_csv_path=args.hydration_packet_csv,
        output_dir=args.output_dir,
        update_docs=not args.no_docs,
        execute_llm=not args.skip_llm,
        llm_backend=args.llm_backend,
        llm_base_url=args.llm_base_url,
        llm_model=args.llm_model,
        llm_timeout_seconds=args.llm_timeout_seconds,
        llm_max_tokens=args.llm_max_tokens,
    )
    print(json.dumps({"run_id": RUN_ID, "status": report["status"], "report": report["artifact_paths"]["report_json"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
