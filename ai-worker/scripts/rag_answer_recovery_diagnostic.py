"""Generate report-only answer sufficiency and recovery diagnostics.

The harness uses deterministic sample cases and the existing internal agent
loop through ``AgenticRetrievalLoopAdapter``. It does not open official answer
denominators, mutate production indexes, train profiles, or promote shadow-lane
evidence.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent
if str(AI_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_WORKER_ROOT))

from app.capabilities.rag.answer_recovery import (
    ADJACENT_CONTEXT_EXPANSION,
    AGENTIC_RETRIEVAL_LOOP,
    AMBIGUOUS_QUERY,
    IDP_SHADOW,
    MULTIMODAL_SHADOW,
    NEEDS_CLARIFICATION,
    OCR_SHADOW,
    PDF_CONTENT,
    PDF_FILE_LOOKUP,
    SUPPORTED,
    TEXT,
    XLSX,
    AgenticRetrievalLoopAdapter,
    AnswerEvidenceCandidate,
    AnswerSufficiencyJudge,
    RecoveryPolicyRouter,
)
from app.capabilities.rag.generation import RetrievedChunk
from app.capabilities.rag.shadow_lane_contract import (
    IDP_TABLE_MEDIUM,
    MULTIMODAL_CAPTION_LOW,
    NATIVE_TEXT_HIGH,
    OCR_MEDIUM,
    STRUCTURED_XLSX_HIGH,
)


DEFAULT_REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"


@dataclass(frozen=True)
class DiagnosticCase:
    case_id: str
    lane: str
    query: str
    draft_answer: str
    evidence: tuple[AnswerEvidenceCandidate, ...]
    metadata: Mapping[str, Any]
    recovery_mode: str = ""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report_dir = resolve_path(args.reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    components = build_existing_components_report()
    plan = build_recovery_loop_plan()
    diagnostic = run_diagnostic_cases()
    expanded = run_expanded_diagnostic_cases()

    write_json(report_dir / "answer_recovery_existing_components_report.json", components)
    write_text(report_dir / "answer_recovery_existing_components_report.md", render_components_md(components))
    write_text(report_dir / "answer_recovery_loop_plan.md", plan)
    write_json(report_dir / "answer_sufficiency_diagnostic_report.json", diagnostic["report"])
    write_text(report_dir / "answer_sufficiency_diagnostic_report.md", render_diagnostic_md(diagnostic["report"]))
    write_jsonl(report_dir / "answer_recovery_trace.jsonl", diagnostic["trace_rows"])
    write_csv(report_dir / "clarification_question_samples.csv", diagnostic["clarifications"])
    write_csv(report_dir / "agentic_loop_recovery_cases.csv", diagnostic["recovery_cases"])
    write_csv(report_dir / "unsupported_after_recovery_cases.csv", diagnostic["unsupported_cases"])
    write_json(report_dir / "answer_sufficiency_expanded_diagnostic_report.json", expanded["report"])
    write_text(
        report_dir / "answer_sufficiency_expanded_diagnostic_report.md",
        render_expanded_diagnostic_md(expanded["report"]),
    )
    write_jsonl(report_dir / "answer_recovery_expanded_trace.jsonl", expanded["trace_rows"])
    write_text(report_dir / "answer_recovery_lane_breakdown.md", render_lane_breakdown_md(expanded["report"]))
    write_text(report_dir / "answer_recovery_failure_taxonomy.md", render_failure_taxonomy_md(expanded["report"]))
    write_csv(
        report_dir / "answer_recovery_wrongly_supported_review.csv",
        expanded["wrongly_supported_rows"],
        fieldnames=[
            "case_id",
            "lane",
            "case_type",
            "source_artifact",
            "failure_type",
            "support_score",
            "citation_coverage",
            "diagnostic_reason",
        ],
    )

    print(
        json.dumps(
            {
                "status": "PASS",
                "total_evaluated": diagnostic["report"]["counts"]["total_evaluated"],
                "expanded_total_evaluated": expanded["report"]["counts"]["total_evaluated"],
                "recovered_after_loop": diagnostic["report"]["counts"]["recovered_after_loop"],
                "report": repo_relative(report_dir / "answer_sufficiency_diagnostic_report.json"),
                "expanded_report": repo_relative(report_dir / "answer_sufficiency_expanded_diagnostic_report.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORT_DIR))
    return parser.parse_args(argv)


def build_existing_components_report() -> dict[str, Any]:
    targets = [
        ("app.capabilities.agent.loop", ["AgentLoopController", "LoopBudget", "LoopOutcome", "ExecuteFn"]),
        ("app.capabilities.agent.graph_loop.adapters", ["AgentLoopGraph"]),
        ("app.capabilities.agent.critic", ["RuleCritic", "LlmCritic", "CritiqueResult"]),
        ("app.capabilities.agent.rewriter", ["NoOpQueryRewriter", "LlmQueryRewriter", "QueryRewriterProvider"]),
        ("app.capabilities.rag.query_parser", ["RegexQueryParser", "LlmQueryParser", "ParsedQuery"]),
        ("app.capabilities.rag.generation", ["ExtractiveGenerator", "RetrievedChunk"]),
        ("app.capabilities.rag_orchestrator.evidence", ["Evidence", "QueryPolicy"]),
        ("app.capabilities.rag_orchestrator.citation_verify", ["citation_verify_tool", "verify_evidence"]),
        ("app.capabilities.rag_orchestrator.evidence_merge", ["evidence_merge_tool"]),
        ("app.capabilities.rag_orchestrator.answer_policy", ["prepare_answer_handoff", "build_no_evidence_response"]),
        ("eval.harness.pdf_xlsx_answer_evidence_serializer", ["serialize_input_row", "serialize_input_rows"]),
        ("eval.harness.pdf_xlsx_deterministic_answer_compiler", ["compile_evidence_row", "compile_evidence_rows"]),
    ]
    discovered = []
    for module_name, symbols in targets:
        try:
            module = importlib.import_module(module_name)
            available = [symbol for symbol in symbols if hasattr(module, symbol)]
            status = "FOUND" if available else "MISSING_SYMBOLS"
        except Exception as exc:
            available = []
            status = f"IMPORT_FAILED:{type(exc).__name__}"
        discovered.append({"module": module_name, "symbols": available, "status": status})
    return {
        "schema_version": "answer_recovery_existing_components_report_v1",
        "status": "PASS",
        "discovered_components": discovered,
        "reuse_decision": {
            "agentic_loop_component": "app.capabilities.agent.loop.AgentLoopController",
            "graph_loop_component_available": has_found(discovered, "app.capabilities.agent.graph_loop.adapters"),
            "citation_components": [
                "app.capabilities.rag_orchestrator.citation_verify.citation_verify_tool",
                "app.capabilities.rag_orchestrator.answer_policy.prepare_answer_handoff",
            ],
            "answer_compiler_components": [
                "eval.harness.pdf_xlsx_answer_evidence_serializer.serialize_input_row",
                "eval.harness.pdf_xlsx_deterministic_answer_compiler.compile_evidence_row",
            ],
            "new_code_required": [
                "AnswerSufficiencyJudge",
                "RecoveryPolicyRouter",
                "AgenticRetrievalLoopAdapter",
                "report-only diagnostic harness",
            ],
        },
        "risk_notes": [
            "Do not promote answer denominators from this diagnostic bridge.",
            "Do not use PDF FILE lookup as content evidence.",
            "Do not expose hidden XLSX content.",
            "OCR, IDP, and multimodal evidence remains diagnostic-only by default.",
            "Local LLM smoke output is diagnostic-only and not promotion evidence.",
        ],
        "no_production_mutation_proof": {
            "production_index_mutation": False,
            "broad_indexing": False,
            "official_denominator_registry_changed": False,
            "training_on_frozen_gold": False,
            "profile_selection_on_frozen_gold": False,
        },
    }


def build_recovery_loop_plan() -> str:
    return "\n".join(
        [
            "# Answer Recovery Loop Plan",
            "",
            "- Status: `diagnostic_runtime_bridge_only`.",
            "- Reused loop: `app.capabilities.agent.loop.AgentLoopController` through `AgenticRetrievalLoopAdapter`.",
            "- Max iterations: `2`; max query rewrites: `3`.",
            "- Production index mutation: `false`; broad indexing: `false`; official denominator mutation: `false`.",
            "- TEXT: allow query rewrite, title/entity disambiguation, section expansion, adjacent chunk expansion; keep `tuned_text_section_boost_bm25` diagnostic-only.",
            "- XLSX: use only strict wrapper context; preserve parser_version, location_json, citation_text; hidden content cannot surface.",
            "- PDF CONTENT: prefer native PDF text; OCR fallback is lower-trust diagnostic metadata; report native/OCR conflicts.",
            "- PDF FILE LOOKUP: file identity only; no content, page, bbox, table, row, column, or value success claims.",
            "- OCR/IDP/multimodal: diagnostic hints and retrieval expansion only; cannot make official support by default.",
            "",
        ]
    )


def run_diagnostic_cases() -> dict[str, Any]:
    judge = AnswerSufficiencyJudge()
    router = RecoveryPolicyRouter()
    adapter = AgenticRetrievalLoopAdapter()
    trace_rows: list[dict[str, Any]] = []
    clarifications: list[dict[str, Any]] = []
    recovery_cases: list[dict[str, Any]] = []
    unsupported_cases: list[dict[str, Any]] = []
    case_reports: list[dict[str, Any]] = []
    loop_iterations: list[int] = []
    before_coverages: list[float] = []
    after_coverages: list[float] = []

    for case in diagnostic_cases():
        before = judge.evaluate(
            user_query=case.query,
            lane=case.lane,
            draft_answer=case.draft_answer,
            retrieved_evidence_candidates=case.evidence,
            answer_shape_metadata=case.metadata,
        )
        route = router.route(user_query=case.query, lane=case.lane, decision=before)
        loop_result = None
        after = before
        recovered_evidence = case.evidence
        recovered_answer = case.draft_answer
        if route.action in {AGENTIC_RETRIEVAL_LOOP, ADJACENT_CONTEXT_EXPANSION}:
            executor = recoverable_executor if case.recovery_mode == "recoverable" else None
            loop_result = adapter.run(user_query=case.query, lane=case.lane, route=route, recovery_executor=executor)
            loop_iterations.append(loop_result.loop_iterations)
            recovered_answer = loop_result.final_answer or case.draft_answer
            if case.recovery_mode == "recoverable":
                recovered_evidence = (
                    evidence(TEXT, NATIVE_TEXT_HIGH, "Recovered TEXT citation", {"section": "recovered"}, "Recovered cited context."),
                )
            after = judge.evaluate(
                user_query=case.query,
                lane=case.lane,
                draft_answer=recovered_answer,
                retrieved_evidence_candidates=recovered_evidence,
                answer_shape_metadata={**case.metadata, "has_user_constraint": True},
            )
            recovery_cases.append(
                {
                    "case_id": case.case_id,
                    "lane": case.lane,
                    "route_action": route.action,
                    "loop_iterations": loop_result.loop_iterations,
                    "recovered": loop_result.recovered and after.sufficiency_status == SUPPORTED,
                    "stop_reason": loop_result.stop_reason,
                }
            )
        if route.action == "ASK_CLARIFICATION":
            clarifications.append(
                {
                    "case_id": case.case_id,
                    "lane": case.lane,
                    "failure_type": before.failure_type,
                    "question": route.clarification_question,
                }
            )
        if after.sufficiency_status != SUPPORTED and (
            loop_result is not None or before.sufficiency_status == "UNSUPPORTED"
        ):
            unsupported_cases.append(
                {
                    "case_id": case.case_id,
                    "lane": case.lane,
                    "failure_type": after.failure_type,
                    "sufficiency_status": after.sufficiency_status,
                    "diagnostic_reason": after.diagnostic_reason,
                }
            )
        before_coverages.append(before.citation_coverage)
        after_coverages.append(after.citation_coverage)
        trace_row = {
            "case_id": case.case_id,
            "lane": case.lane,
            "query": case.query,
            "before_decision": before.to_dict(),
            "route": route.to_dict(),
            "loop_result": loop_result.to_dict() if loop_result else None,
            "after_decision": after.to_dict(),
            "policies": {
                "official_denominator_registry_changed": False,
                "production_index_mutation": False,
                "broad_indexing": False,
                "promotion_evidence": False,
            },
        }
        trace_rows.append(trace_row)
        case_reports.append(trace_row)

    counts = {
        "total_evaluated": len(case_reports),
        "initially_supported": sum(1 for row in case_reports if row["before_decision"]["sufficiency_status"] == SUPPORTED),
        "recovered_after_loop": sum(
            1
            for row in case_reports
            if row["loop_result"] and row["after_decision"]["sufficiency_status"] == SUPPORTED
        ),
        "clarification_needed": len(clarifications),
        "unsupported_after_recovery": len(unsupported_cases),
        "lane_mismatch": sum(1 for row in case_reports if row["before_decision"]["failure_type"] == "LANE_MISMATCH"),
        "hidden_xlsx_blocked": sum(
            1 for row in case_reports if "XLSX_HIDDEN_CONTENT" in row["before_decision"]["blocked_lanes"]
        ),
        "pdf_file_lookup_content_mixing_blocked": sum(
            1
            for row in case_reports
            if row["lane"] == PDF_FILE_LOOKUP and row["before_decision"]["failure_type"] == "LANE_MISMATCH"
        ),
        "ocr_diagnostic_evidence_used": diagnostic_evidence_count(OCR_SHADOW, OCR_MEDIUM),
        "idp_diagnostic_evidence_used": diagnostic_evidence_count(IDP_SHADOW, IDP_TABLE_MEDIUM),
        "multimodal_diagnostic_evidence_used": diagnostic_evidence_count(MULTIMODAL_SHADOW, MULTIMODAL_CAPTION_LOW),
        "average_loop_iterations": average(loop_iterations),
        "citation_coverage_before": average(before_coverages),
        "citation_coverage_after": average(after_coverages),
    }
    return {
        "report": {
            "schema_version": "answer_sufficiency_diagnostic_report_v1",
            "status": "PASS",
            "counts": counts,
            "policy": {
                "diagnostic_runtime_bridge_only": True,
                "official_denominator_registry_changed": False,
                "production_index_mutation": False,
                "broad_indexing": False,
                "frozen_gold_training_rows": 0,
                "frozen_gold_profile_selection": False,
                "tuned_text_section_boost_bm25_promotion_status": "diagnostic_only",
                "pdf_file_lookup_semantics": "file_identity_only",
                "ocr_idp_multimodal_denominator_role": "DIAGNOSTIC_ONLY",
            },
            "case_results": case_reports,
        },
        "trace_rows": trace_rows,
        "clarifications": clarifications,
        "recovery_cases": recovery_cases,
        "unsupported_cases": unsupported_cases,
    }


EXPANDED_TARGETS = {
    TEXT: (50, 100),
    XLSX: (30, 50),
    PDF_CONTENT: (30, 50),
    PDF_FILE_LOOKUP: (15, 30),
    OCR_SHADOW: (10, 20),
    IDP_SHADOW: (10, 20),
    MULTIMODAL_SHADOW: (10, 20),
}


def run_expanded_diagnostic_cases() -> dict[str, Any]:
    cases, sampler = expanded_diagnostic_cases()
    judge = AnswerSufficiencyJudge()
    router = RecoveryPolicyRouter()
    adapter = AgenticRetrievalLoopAdapter()
    trace_rows: list[dict[str, Any]] = []
    recovery_rows: list[dict[str, Any]] = []

    for case in cases:
        before = judge.evaluate(
            user_query=case.query,
            lane=case.lane,
            draft_answer=case.draft_answer,
            retrieved_evidence_candidates=case.evidence,
            answer_shape_metadata=case.metadata,
        )
        route = router.route(user_query=case.query, lane=case.lane, decision=before)
        loop_result = None
        after = before
        recovered_evidence = case.evidence
        recovered_answer = case.draft_answer
        if route.action in {AGENTIC_RETRIEVAL_LOOP, ADJACENT_CONTEXT_EXPANSION}:
            executor = recoverable_executor if case.recovery_mode == "recoverable" else None
            loop_result = adapter.run(user_query=case.query, lane=case.lane, route=route, recovery_executor=executor)
            recovered_answer = loop_result.final_answer or case.draft_answer
            if case.recovery_mode == "recoverable":
                recovered_evidence = recovered_evidence_for(case)
            after = judge.evaluate(
                user_query=case.query,
                lane=case.lane,
                draft_answer=recovered_answer,
                retrieved_evidence_candidates=recovered_evidence,
                answer_shape_metadata={**case.metadata, "has_user_constraint": True},
            )
            recovery_rows.append(
                {
                    "case_id": case.case_id,
                    "lane": case.lane,
                    "route_action": route.action,
                    "loop_iterations": loop_result.loop_iterations,
                    "recovered": loop_result.recovered and after.sufficiency_status == SUPPORTED,
                    "stop_reason": loop_result.stop_reason,
                }
            )

        expected_support = bool(case.metadata.get("expected_official_support_allowed"))
        trace_rows.append(
            {
                "case_id": case.case_id,
                "lane": case.lane,
                "query": case.query,
                "case_type": case.metadata.get("case_type", ""),
                "source_artifact": case.metadata.get("source_artifact", ""),
                "expected_official_support_allowed": expected_support,
                "before_decision": before.to_dict(),
                "route": route.to_dict(),
                "loop_result": loop_result.to_dict() if loop_result else None,
                "after_decision": after.to_dict(),
                "diagnostic_policy": {
                    "official_answer_denominator_opened": False,
                    "official_denominator_registry_changed": False,
                    "production_index_mutation": False,
                    "broad_indexing": False,
                    "promotion_evidence": False,
                    "tuned_text_section_boost_bm25_promotion_status": "diagnostic_only",
                    "pdf_file_lookup_semantics": "file_identity_only",
                },
            }
        )

    taxonomy = build_expanded_taxonomy(trace_rows)
    report = {
        "schema_version": "answer_sufficiency_expanded_diagnostic_report_v1",
        "status": "PASS",
        "counts": {
            "total_evaluated": len(trace_rows),
            "initially_supported": sum(
                1 for row in trace_rows if row["before_decision"]["sufficiency_status"] == SUPPORTED
            ),
            "recovered_after_loop": sum(
                1
                for row in trace_rows
                if row["loop_result"] and row["after_decision"]["sufficiency_status"] == SUPPORTED
            ),
            **taxonomy["counts"],
        },
        "sampler": sampler,
        "lane_breakdown": taxonomy["lane_breakdown"],
        "failure_taxonomy": taxonomy["failure_taxonomy"],
        "policy": {
            "diagnostic_runtime_bridge_only": True,
            "official_answer_denominator_opened": False,
            "official_denominator_registry_changed": False,
            "production_index_mutation": False,
            "broad_indexing": False,
            "frozen_gold_training_rows": 0,
            "frozen_gold_profile_selection": False,
            "tuned_text_section_boost_bm25_promotion_status": "diagnostic_only",
            "pdf_file_lookup_semantics": "file_identity_only",
            "pdf_file_lookup_success_claims": {
                "content": False,
                "page": False,
                "bbox": False,
                "table": False,
                "row": False,
                "column": False,
                "value": False,
            },
            "hidden_xlsx_content_surface": False,
            "ocr_idp_multimodal_denominator_role": "DIAGNOSTIC_ONLY",
            "native_pdf_text_outranks_ocr_fallback": True,
            "max_loop_iterations": adapter.guardrails.max_iterations,
        },
        "case_results": trace_rows,
    }
    return {
        "report": report,
        "trace_rows": trace_rows,
        "recovery_rows": recovery_rows,
        "wrongly_supported_rows": taxonomy["wrongly_supported_rows"],
    }


def expanded_diagnostic_cases() -> tuple[list[DiagnosticCase], dict[str, Any]]:
    sampler_rows = [
        sample_text_cases(),
        sample_xlsx_cases(),
        sample_pdf_content_cases(),
        sample_pdf_file_lookup_cases(),
        sample_shadow_cases(OCR_SHADOW, AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "ocr_shadow_small_sample_report.json"),
        sample_shadow_cases(IDP_SHADOW, AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "idp_shadow_small_sample_report.json"),
        sample_shadow_cases(
            MULTIMODAL_SHADOW,
            AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "multimodal_shadow_small_sample_report.json",
        ),
    ]
    cases: list[DiagnosticCase] = []
    artifacts: list[str] = []
    sampler_details: list[dict[str, Any]] = []
    limitations: list[str] = []
    for lane_cases, detail in sampler_rows:
        cases.extend(lane_cases)
        sampler_details.append(detail)
        artifacts.extend(detail.get("source_artifacts", []))
        if detail.get("limitation"):
            limitations.append(detail["limitation"])

    lane_counts = dict(Counter(case.lane for case in cases))
    for lane, (target_min, target_max) in EXPANDED_TARGETS.items():
        actual = lane_counts.get(lane, 0)
        if actual and actual < target_min and not any(item.startswith(f"{lane}:") for item in limitations):
            limitations.append(f"{lane}: only {actual} existing diagnostic cases available; target was {target_min}-{target_max}.")
        if not actual:
            limitations.append(f"{lane}: no existing diagnostic cases available for expanded sampler.")

    sampler = {
        "schema_version": "answer_recovery_expanded_sampler_v1",
        "deterministic": True,
        "uses_existing_reviewed_silver_diagnostic_artifacts_only": True,
        "official_answer_denominator_opened": False,
        "official_denominator_registry_changed": False,
        "production_index_mutation": False,
        "broad_indexing": False,
        "lane_counts": lane_counts,
        "targets": {
            lane: {"min": target_min, "max": target_max}
            for lane, (target_min, target_max) in EXPANDED_TARGETS.items()
        },
        "samplers": sampler_details,
        "source_artifacts": sorted(set(artifacts)),
        "limitations": sorted(set(limitations)),
    }
    return cases, sampler


def sample_text_cases() -> tuple[list[DiagnosticCase], dict[str, Any]]:
    path = AI_WORKER_ROOT / "eval" / "review" / "gold_silver_tuning" / "silver_text_positive_train.csv"
    rows = read_csv_rows(path)
    cases: list[DiagnosticCase] = []
    for index, row in enumerate(rows[:75], start=1):
        query = first_present(row, "query") or f"TEXT diagnostic query {index}"
        source_quote = compact_text(first_present(row, "source_evidence_quote") or "reviewed silver text evidence")
        citation = " > ".join(
            part
            for part in [
                first_present(row, "expected_document_ids") or "silver_text_document",
                first_present(row, "expected_section_path") or "section",
                first_present(row, "expected_chunk_ids") or "chunk",
            ]
            if part
        )
        metadata = base_case_metadata(
            "TEXT",
            path,
            row,
            case_type="silver_text_positive",
            expected_official_support_allowed=True,
        )
        if index % 15 == 0:
            cases.append(
                DiagnosticCase(
                    f"expanded_text_recovery_{index:03d}",
                    TEXT,
                    query,
                    "",
                    (),
                    {**metadata, "case_type": "silver_text_recoverable_missing_retrieval"},
                    recovery_mode="recoverable",
                )
            )
        elif index % 22 == 0:
            cases.append(
                DiagnosticCase(
                    f"expanded_text_uncited_{index:03d}",
                    TEXT,
                    query,
                    "This diagnostic draft is intentionally missing concrete citation support.",
                    (
                        AnswerEvidenceCandidate(
                            lane=TEXT,
                            text=source_quote,
                            citation_text="",
                            location_json=None,
                            trust_tier=NATIVE_TEXT_HIGH,
                        ),
                    ),
                    {
                        **metadata,
                        "case_type": "silver_text_uncited_block",
                        "expected_official_support_allowed": False,
                    },
                )
            )
        else:
            cases.append(
                DiagnosticCase(
                    f"expanded_text_supported_{index:03d}",
                    TEXT,
                    query,
                    "The diagnostic TEXT answer is grounded in the cited retrieved section.",
                    (
                        evidence(
                            TEXT,
                            NATIVE_TEXT_HIGH,
                            citation,
                            {
                                "document_id": first_present(row, "expected_document_ids"),
                                "section_path": first_present(row, "expected_section_path"),
                                "chunk_id": first_present(row, "expected_chunk_ids"),
                                "source": "silver_text_positive_train",
                            },
                            source_quote,
                        ),
                    ),
                    metadata,
                )
            )
    return cases, sampler_detail(TEXT, path, len(rows), len(cases))


def sample_xlsx_cases() -> tuple[list[DiagnosticCase], dict[str, Any]]:
    positive_path = AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_xlsx_v3_positive_reviewed.csv"
    hidden_path = AI_WORKER_ROOT / "eval" / "review" / "gold_set_review" / "a_b_c_user_review_signal_normalized.csv"
    rows = read_csv_rows(positive_path)
    hidden_rows = [
        row
        for row in read_csv_rows(hidden_path)
        if "hidden" in (first_present(row, "review_group", "bucket", "derived_policy_reasons") or "").lower()
        or "hidden" in (first_present(row, "query_id") or "").lower()
    ]
    cases: list[DiagnosticCase] = []
    for index, row in enumerate(rows[:40], start=1):
        query = first_present(row, "query", "original_query") or f"XLSX diagnostic query {index}"
        sheet = first_present(row, "expected_sheet_name", "sheet") or "Sheet1"
        cell_range = first_present(row, "expected_cell_range", "range") or "A1:B2"
        file_name = first_present(row, "expected_file_name", "citation_locator_file") or "workbook.xlsx"
        answer_text = first_present(row, "expected_answer_text", "current_evidence_summary") or "visible XLSX strict wrapper evidence"
        metadata = base_case_metadata(
            "XLSX",
            positive_path,
            row,
            case_type="xlsx_strict_wrapper_visible",
            expected_official_support_allowed=True,
        )
        if index % 13 == 0:
            cases.append(
                DiagnosticCase(
                    f"expanded_xlsx_constraint_{index:03d}",
                    XLSX,
                    "엑셀에서 어떤 값을 봐야 해?",
                    "",
                    (),
                    {
                        **metadata,
                        "case_type": "xlsx_needs_user_constraint",
                        "requires_user_constraint": True,
                        "expected_official_support_allowed": False,
                    },
                )
            )
        else:
            cases.append(
                DiagnosticCase(
                    f"expanded_xlsx_supported_{index:03d}",
                    XLSX,
                    query,
                    "The diagnostic XLSX answer is grounded in visible strict wrapper evidence.",
                    (
                        evidence(
                            XLSX,
                            STRUCTURED_XLSX_HIGH,
                            f"{file_name} > {sheet} > {cell_range}",
                            {
                                "file": file_name,
                                "sheet_name": sheet,
                                "cell_range": cell_range,
                                "source": "xlsx_strict_wrapper_reviewed",
                            },
                            compact_text(answer_text),
                            metadata={"strict_wrapper": True},
                        ),
                    ),
                    metadata,
                )
            )
    for index, row in enumerate(hidden_rows[:3], start=1):
        cases.append(
            DiagnosticCase(
                f"expanded_xlsx_hidden_blocked_{index:03d}",
                XLSX,
                "숨김 XLSX 범위는 답으로 노출하지 않는지 확인",
                "Hidden XLSX content is redacted and must not be surfaced.",
                (
                    evidence(
                        XLSX,
                        STRUCTURED_XLSX_HIGH,
                        "workbook.xlsx > hidden-range-redacted",
                        {"hidden": True, "redacted": True, "source": "xlsx_hidden_policy_review"},
                        "hidden content redacted",
                        hidden=True,
                        metadata={"strict_wrapper": True},
                    ),
                ),
                base_case_metadata(
                    "XLSX",
                    hidden_path,
                    row,
                    case_type="xlsx_hidden_surface_attempt_blocked",
                    expected_official_support_allowed=False,
                ),
            )
        )
    source_count = len(rows) + len(hidden_rows)
    return cases, sampler_detail(XLSX, positive_path, source_count, len(cases), extra_artifacts=[repo_relative(hidden_path)])


def sample_pdf_content_cases() -> tuple[list[DiagnosticCase], dict[str, Any]]:
    path = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_pdf_supplemental_answer_evidence_diagnostic.csv"
    rows = read_csv_rows(path)
    cases: list[DiagnosticCase] = []
    for index, row in enumerate(rows[:40], start=1):
        query = f"PDF 본문 진단 근거 {first_present(row, 'query_id') or index} 확인"
        citation = first_present(row, "citation") or f"{first_present(row, 'file_name') or 'document.pdf'} native PDF text"
        excerpt = compact_text(first_present(row, "evidence_text_excerpt") or "native PDF text evidence")
        metadata = base_case_metadata(
            "PDF_CONTENT",
            path,
            row,
            case_type="pdf_native_text_content",
            expected_official_support_allowed=True,
        )
        if index % 17 == 0:
            cases.append(
                DiagnosticCase(
                    f"expanded_pdf_content_uncited_{index:03d}",
                    PDF_CONTENT,
                    query,
                    "This PDF content draft intentionally lacks concrete citation support.",
                    (
                        AnswerEvidenceCandidate(
                            lane=PDF_CONTENT,
                            text=excerpt,
                            citation_text="",
                            location_json=None,
                            trust_tier=NATIVE_TEXT_HIGH,
                        ),
                    ),
                    {
                        **metadata,
                        "case_type": "pdf_content_uncited_block",
                        "expected_official_support_allowed": False,
                    },
                )
            )
        else:
            cases.append(
                DiagnosticCase(
                    f"expanded_pdf_content_supported_{index:03d}",
                    PDF_CONTENT,
                    query,
                    "The diagnostic PDF content answer is grounded in native PDF text evidence.",
                    (
                        evidence(
                            PDF_CONTENT,
                            NATIVE_TEXT_HIGH,
                            citation,
                            pdf_content_location(row),
                            excerpt,
                        ),
                    ),
                    metadata,
                )
            )
    return cases, sampler_detail(PDF_CONTENT, path, len(rows), len(cases))


def sample_pdf_file_lookup_cases() -> tuple[list[DiagnosticCase], dict[str, Any]]:
    paths = [
        AI_WORKER_ROOT / "eval" / "review" / "gold_silver_tuning" / "silver_pdf_file_lookup_positive_train.csv",
        AI_WORKER_ROOT / "eval" / "review" / "gold_silver_tuning" / "silver_pdf_file_lookup_hard_negative_v2.csv",
        AI_WORKER_ROOT / "eval" / "review" / "gold_silver_tuning" / "pdf_file_lookup_diagnostic_clean.csv",
        AI_WORKER_ROOT / "eval" / "review" / "gold_silver_tuning" / "pdf_file_lookup_gold_positive_clean.csv",
    ]
    rows: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        rows.extend((path, row) for row in read_csv_rows(path))
    cases: list[DiagnosticCase] = []
    for index, (path, row) in enumerate(rows[:28], start=1):
        query = first_present(row, "query") or f"PDF 파일 identity 진단 {index}"
        file_name = first_present(row, "expected_file_name", "source_file_name") or "file.pdf"
        document_version_id = first_present(row, "expected_document_version_id") or ""
        is_hard_negative = "hard_negative" in path.name or "HARD_NEGATIVE" in json.dumps(row, ensure_ascii=False)
        is_content_mixing = index % 7 == 0
        metadata = base_case_metadata(
            "PDF_FILE_LOOKUP",
            path,
            row,
            case_type="pdf_file_lookup_content_mixing" if is_content_mixing else "pdf_file_lookup_identity",
            expected_official_support_allowed=not is_hard_negative and not is_content_mixing,
        )
        if is_content_mixing:
            metadata = {**metadata, "answer_intent": "table"}
            query = f"{query} 본문 표 값까지 알려줘"
        else:
            metadata = {**metadata, "answer_intent": "file_identity"}
        cases.append(
            DiagnosticCase(
                f"expanded_pdf_file_lookup_{index:03d}",
                PDF_FILE_LOOKUP,
                query,
                f"The diagnostic answer identifies file identity `{file_name}` only.",
                (
                    evidence(
                        PDF_FILE_LOOKUP,
                        NATIVE_TEXT_HIGH,
                        file_name,
                        {
                            "type": "file_identity",
                            "expected_file_name": file_name,
                            "document_version_id_present": bool(document_version_id),
                        },
                        f"file identity: {file_name}",
                    ),
                ),
                metadata,
            )
        )
    return cases, sampler_detail(PDF_FILE_LOOKUP, paths[0], len(rows), len(cases), extra_artifacts=[repo_relative(path) for path in paths[1:]])


def sample_shadow_cases(lane: str, path: Path) -> tuple[list[DiagnosticCase], dict[str, Any]]:
    payload = read_json_object(path)
    rows = [row for row in payload.get("diagnostic_rows", []) if row.get("lane") == lane]
    cases: list[DiagnosticCase] = []
    for index, row in enumerate(rows[:20], start=1):
        trust = first_present(row, "trust_tier") or {
            OCR_SHADOW: OCR_MEDIUM,
            IDP_SHADOW: IDP_TABLE_MEDIUM,
            MULTIMODAL_SHADOW: MULTIMODAL_CAPTION_LOW,
        }[lane]
        cases.append(
            DiagnosticCase(
                f"expanded_{lane.lower()}_{index:03d}",
                lane,
                first_present(row, "extra.source_question") or f"{lane} diagnostic evidence cannot be official support",
                "Diagnostic-only shadow evidence is not sufficient for official support.",
                (
                    evidence(
                        lane,
                        trust,
                        first_present(row, "citation_text") or f"{lane} diagnostic citation",
                        row.get("location_json") if isinstance(row.get("location_json"), dict) else {"type": "diagnostic"},
                        compact_text(first_present(row, "display_text", "embedding_text", "bm25_text") or "diagnostic evidence"),
                        diagnostic=True,
                        metadata={"confidence_bucket": row.get("extra", {}).get("ocr_confidence_bucket", "")},
                    ),
                ),
                {
                    "case_type": f"{lane.lower()}_diagnostic_only_blocked",
                    "source_artifact": repo_relative(path),
                    "source_row_id": first_present(row, "unit_id", "search_unit_id"),
                    "denominator_role": "DIAGNOSTIC_ONLY",
                    "official_answer_denominator_opened": False,
                    "expected_official_support_allowed": False,
                },
            )
        )
    return cases, sampler_detail(lane, path, len(rows), len(cases))


def recovered_evidence_for(case: DiagnosticCase) -> tuple[AnswerEvidenceCandidate, ...]:
    if case.lane == XLSX:
        return (
            evidence(
                XLSX,
                STRUCTURED_XLSX_HIGH,
                "recovered_workbook.xlsx > Sheet1 > A1:B2",
                {"sheet_name": "Sheet1", "cell_range": "A1:B2", "source": "bounded_recovery"},
                "Recovered visible XLSX strict wrapper context.",
                metadata={"strict_wrapper": True},
            ),
        )
    if case.lane == PDF_CONTENT:
        return (
            evidence(
                PDF_CONTENT,
                NATIVE_TEXT_HIGH,
                "recovered.pdf native text",
                {"source": "bounded_recovery", "type": "native_pdf_text"},
                "Recovered native PDF text context.",
            ),
        )
    return (
        evidence(
            TEXT,
            NATIVE_TEXT_HIGH,
            "Recovered TEXT citation",
            {"section": "recovered", "source": "bounded_recovery"},
            "Recovered cited context.",
        ),
    )


def build_expanded_taxonomy(case_reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    lane_breakdown: dict[str, dict[str, Any]] = {}
    coverage_delta_by_lane: dict[str, list[float]] = defaultdict(list)
    wrongly_supported_rows: list[dict[str, Any]] = []
    recovery_success_by_lane: Counter[str] = Counter()
    clarification_by_failure_type: Counter[str] = Counter()
    loop_iteration_distribution: Counter[str] = Counter()
    failure_type_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    diagnostic_only_blocked = 0
    hidden_xlsx_attempts = 0
    pdf_file_content_mixing_attempts = 0

    for row in case_reports:
        lane = str(row["lane"])
        before = row["before_decision"]
        after = row["after_decision"]
        route = row["route"]
        loop_result = row.get("loop_result")
        expected_support = bool(row.get("expected_official_support_allowed"))
        after_status = after["sufficiency_status"]
        before_failure = before.get("failure_type", "")
        after_failure = after.get("failure_type", "")
        failure_type_counts[after_failure or "NONE"] += 1
        status_counts[after_status] += 1
        coverage_delta_by_lane[lane].append(float(after["citation_coverage"]) - float(before["citation_coverage"]))
        lane_item = lane_breakdown.setdefault(
            lane,
            {
                "total": 0,
                "initially_supported": 0,
                "supported_after_recovery": 0,
                "clarification_needed": 0,
                "unsupported_after_recovery": 0,
                "wrongly_supported": 0,
                "unsupported_correctly_blocked": 0,
            },
        )
        lane_item["total"] += 1
        if before["sufficiency_status"] == SUPPORTED:
            lane_item["initially_supported"] += 1
        if after_status == SUPPORTED:
            lane_item["supported_after_recovery"] += 1
        if route["action"] == "ASK_CLARIFICATION":
            lane_item["clarification_needed"] += 1
            clarification_by_failure_type[before_failure or "NONE"] += 1
        if after_status != SUPPORTED:
            lane_item["unsupported_after_recovery"] += 1
        if loop_result:
            loop_iteration_distribution[str(loop_result["loop_iterations"])] += 1
            if after_status == SUPPORTED:
                recovery_success_by_lane[lane] += 1
        blocked = set(before.get("blocked_lanes", [])) | set(after.get("blocked_lanes", []))
        if lane in {OCR_SHADOW, IDP_SHADOW, MULTIMODAL_SHADOW} and after_status != SUPPORTED:
            diagnostic_only_blocked += 1
        if any(item in {OCR_SHADOW, IDP_SHADOW, MULTIMODAL_SHADOW} for item in blocked):
            diagnostic_only_blocked += 1
        if "XLSX_HIDDEN_CONTENT" in blocked:
            hidden_xlsx_attempts += 1
        if lane == PDF_FILE_LOOKUP and before_failure == "LANE_MISMATCH":
            pdf_file_content_mixing_attempts += 1
        if after_status == SUPPORTED and not expected_support:
            lane_item["wrongly_supported"] += 1
            wrongly_supported_rows.append(
                {
                    "case_id": row["case_id"],
                    "lane": lane,
                    "case_type": row.get("case_type", ""),
                    "source_artifact": row.get("source_artifact", ""),
                    "failure_type": after_failure,
                    "support_score": after.get("support_score", 0.0),
                    "citation_coverage": after.get("citation_coverage", 0.0),
                    "diagnostic_reason": after.get("diagnostic_reason", ""),
                }
            )
        if after_status != SUPPORTED and not expected_support:
            lane_item["unsupported_correctly_blocked"] += 1

    counts = {
        "wrongly_supported_count": len(wrongly_supported_rows),
        "unsupported_correctly_blocked_count": sum(
            item["unsupported_correctly_blocked"] for item in lane_breakdown.values()
        ),
        "diagnostic_only_evidence_blocked_count": diagnostic_only_blocked,
        "hidden_xlsx_surface_attempt_count": hidden_xlsx_attempts,
        "pdf_file_lookup_content_mixing_attempt_count": pdf_file_content_mixing_attempts,
    }
    failure_taxonomy = {
        "status_counts": dict(sorted(status_counts.items())),
        "failure_type_counts": dict(sorted(failure_type_counts.items())),
        "recovery_success_by_lane": dict(sorted(recovery_success_by_lane.items())),
        "clarification_by_failure_type": dict(sorted(clarification_by_failure_type.items())),
        "loop_iteration_distribution": dict(sorted(loop_iteration_distribution.items())),
        "citation_coverage_delta_by_lane": {
            lane: average(values) for lane, values in sorted(coverage_delta_by_lane.items())
        },
    }
    return {
        "counts": counts,
        "lane_breakdown": dict(sorted(lane_breakdown.items())),
        "failure_taxonomy": failure_taxonomy,
        "wrongly_supported_rows": wrongly_supported_rows,
    }


def diagnostic_cases() -> list[DiagnosticCase]:
    return [
        DiagnosticCase(
            "text_supported",
            TEXT,
            "작품의 기본 설정을 알려줘",
            "The answer is grounded in the cited text evidence and includes the requested setting.",
            (evidence(TEXT, NATIVE_TEXT_HIGH, "text doc > section", {"section": "overview"}, "setting evidence"),),
            {},
        ),
        DiagnosticCase(
            "text_recoverable",
            TEXT,
            "누락된 줄거리 근거를 찾아줘",
            "",
            (),
            {},
            recovery_mode="recoverable",
        ),
        DiagnosticCase(
            "xlsx_ambiguous",
            XLSX,
            "매출 알려줘",
            "",
            (),
            {"ambiguous_query": True},
        ),
        DiagnosticCase(
            "xlsx_hidden_blocked",
            XLSX,
            "숨김 시트 값을 알려줘",
            "hidden answer",
            (
                evidence(
                    XLSX,
                    STRUCTURED_XLSX_HIGH,
                    "workbook.xlsx > Hidden > A1:B2",
                    {"sheet_name": "Hidden", "cell_range": "A1:B2"},
                    "hidden row",
                    hidden=True,
                    metadata={"strict_wrapper": True},
                ),
            ),
            {"has_user_constraint": True},
        ),
        DiagnosticCase(
            "xlsx_strict_supported",
            XLSX,
            "Sheet1 2024 매출 합계 알려줘",
            "Sheet1 2024 revenue total is supported by the strict wrapper evidence.",
            (
                evidence(
                    XLSX,
                    STRUCTURED_XLSX_HIGH,
                    "workbook.xlsx > Sheet1 > A1:B5",
                    {"sheet_name": "Sheet1", "cell_range": "A1:B5"},
                    "2024 revenue total",
                    metadata={"strict_wrapper": True},
                ),
            ),
            {"has_user_constraint": True},
        ),
        DiagnosticCase(
            "pdf_file_content_mismatch",
            PDF_FILE_LOOKUP,
            "이 PDF의 3페이지 표 값을 알려줘",
            "file.pdf",
            (
                evidence(
                    PDF_FILE_LOOKUP,
                    NATIVE_TEXT_HIGH,
                    "file.pdf",
                    {"type": "file_identity"},
                    "file identity only",
                ),
            ),
            {"answer_intent": "table"},
        ),
        DiagnosticCase(
            "pdf_native_with_ocr_hint",
            PDF_CONTENT,
            "PDF 본문 요약해줘",
            "Native PDF text supports this summary; OCR is diagnostic only.",
            (
                evidence(PDF_CONTENT, NATIVE_TEXT_HIGH, "report.pdf > p.1", {"page": 1}, "native text"),
                evidence(OCR_SHADOW, OCR_MEDIUM, "report.pdf OCR", {"page": 1}, "ocr text", diagnostic=True),
            ),
            {"has_user_constraint": True},
        ),
        DiagnosticCase(
            "idp_diagnostic_only",
            IDP_SHADOW,
            "표 추출값을 답으로 써줘",
            "IDP table says value.",
            (
                evidence(IDP_SHADOW, IDP_TABLE_MEDIUM, "idp table diagnostic", {"table_index": 0}, "idp table", diagnostic=True),
            ),
            {"has_user_constraint": True},
        ),
        DiagnosticCase(
            "multimodal_diagnostic_only",
            MULTIMODAL_SHADOW,
            "이미지 캡션으로 정답을 말해줘",
            "caption says something",
            (
                evidence(
                    MULTIMODAL_SHADOW,
                    MULTIMODAL_CAPTION_LOW,
                    "caption diagnostic",
                    {"image": "sample.png"},
                    "caption",
                    diagnostic=True,
                ),
            ),
            {"has_user_constraint": True},
        ),
        DiagnosticCase(
            "unsupported_no_citation",
            PDF_CONTENT,
            "근거 없는 답을 해줘",
            "Unsupported draft answer without citations.",
            (
                AnswerEvidenceCandidate(
                    lane=PDF_CONTENT,
                    text="uncited text",
                    citation_text="",
                    location_json=None,
                    trust_tier=NATIVE_TEXT_HIGH,
                ),
            ),
            {"has_user_constraint": True},
        ),
    ]


def evidence(
    lane: str,
    trust_tier: str,
    citation_text: str,
    location_json: Mapping[str, Any],
    text: str,
    *,
    diagnostic: bool = False,
    hidden: bool = False,
    metadata: Mapping[str, Any] | None = None,
) -> AnswerEvidenceCandidate:
    return AnswerEvidenceCandidate(
        lane=lane,
        text=text,
        citation_text=citation_text,
        location_json=location_json,
        trust_tier=trust_tier,
        evidence_role="diagnostic" if diagnostic else "official",
        denominator_role="DIAGNOSTIC_ONLY" if diagnostic else "",
        diagnostic_only=diagnostic,
        hidden=hidden,
        metadata=dict(metadata or {}),
    )


def recoverable_executor(parsed_query: Any) -> tuple[str, list[RetrievedChunk], int]:
    chunk = RetrievedChunk(
        chunk_id="recovered_chunk_001",
        doc_id="recovered_doc",
        section="recovered_section",
        text="Recovered cited context with enough concrete content to answer the diagnostic query.",
        score=1.0,
    )
    answer = "Recovered answer grounded in newly retrieved cited context with enough detail to pass the deterministic rule critic."
    return answer, [chunk], 0


def diagnostic_evidence_count(lane: str, trust_tier: str) -> int:
    count = 0
    for case in diagnostic_cases():
        for item in case.evidence:
            if item.lane == lane or item.trust_tier == trust_tier:
                count += 1
    return count


def has_found(rows: Sequence[Mapping[str, Any]], module_name: str) -> bool:
    return any(row["module"] == module_name and row["status"] == "FOUND" for row in rows)


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def first_present(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value: Any = row
        for part in key.split("."):
            if not isinstance(value, Mapping) or part not in value:
                value = ""
                break
            value = value[part]
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def compact_text(value: Any, limit: int = 280) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def base_case_metadata(
    lane: str,
    source_path: Path,
    row: Mapping[str, Any],
    *,
    case_type: str,
    expected_official_support_allowed: bool,
) -> dict[str, Any]:
    return {
        "lane": lane,
        "case_type": case_type,
        "source_artifact": repo_relative(source_path),
        "source_row_id": first_present(row, "query_id", "source_query_id", "unit_id", "search_unit_id"),
        "source_denominator_role": first_present(row, "denominator_role", "denominator_kind", "derived_denominator_policy"),
        "denominator_role": "DIAGNOSTIC_EVAL_ONLY",
        "official_answer_denominator_opened": False,
        "expected_official_support_allowed": expected_official_support_allowed,
        "profile_selection_input": False,
        "training_input": False,
    }


def sampler_detail(
    lane: str,
    source_path: Path,
    available_count: int,
    selected_count: int,
    *,
    extra_artifacts: Sequence[str] | None = None,
) -> dict[str, Any]:
    target_min, target_max = EXPANDED_TARGETS[lane]
    artifacts = [repo_relative(source_path), *(extra_artifacts or [])]
    limitation = ""
    if selected_count < target_min:
        limitation = f"{lane}: selected {selected_count}; target was {target_min}-{target_max} and only existing artifacts were used."
    return {
        "lane": lane,
        "available_rows": available_count,
        "selected_cases": selected_count,
        "target_min": target_min,
        "target_max": target_max,
        "source_artifacts": sorted(set(artifacts)),
        "limitation": limitation,
    }


def pdf_content_location(row: Mapping[str, Any]) -> dict[str, Any]:
    citation = first_present(row, "citation")
    if citation:
        try:
            parsed = json.loads(citation)
            if isinstance(parsed, dict):
                return {**parsed, "type": "native_pdf_text"}
        except json.JSONDecodeError:
            pass
    return {
        "type": "native_pdf_text",
        "file": first_present(row, "file_name"),
        "relative_path": first_present(row, "relative_path"),
    }


def render_components_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Answer Recovery Existing Components Report",
        "",
        f"- Status: `{payload['status']}`.",
        "- Production index mutation: `false`.",
        "- Broad indexing: `false`.",
        "- Official denominator registry changed: `false`.",
        "",
        "## Reuse Decision",
        "",
        f"- Agentic loop component: `{payload['reuse_decision']['agentic_loop_component']}`.",
        "- New code is limited to the sufficiency judge, policy router, loop adapter, and report-only harness.",
        "",
        "## Discovered Components",
        "",
        "| module | status | symbols |",
        "|---|---|---|",
    ]
    for item in payload["discovered_components"]:
        lines.append(f"| `{item['module']}` | `{item['status']}` | `{', '.join(item['symbols'])}` |")
    lines.extend(["", "## Risk Notes", ""])
    for note in payload["risk_notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def render_diagnostic_md(payload: Mapping[str, Any]) -> str:
    counts = payload["counts"]
    lines = [
        "# Answer Sufficiency Diagnostic Report",
        "",
        f"- Status: `{payload['status']}`.",
        "- Diagnostic/runtime bridge only; no official answer denominator opened.",
        "- Production index mutation: `false`; broad indexing: `false`.",
        "",
        "## Counts",
        "",
    ]
    for key, value in counts.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Policy", ""])
    for key, value in payload["policy"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def render_expanded_diagnostic_md(payload: Mapping[str, Any]) -> str:
    counts = payload["counts"]
    sampler = payload["sampler"]
    lines = [
        "# Answer Sufficiency Expanded Diagnostic Report",
        "",
        f"- Status: `{payload['status']}`.",
        "- Scope: lane-separated diagnostic evaluation only; no official answer denominator opened.",
        "- Production index mutation: `false`; broad indexing: `false`; official denominator registry changed: `false`.",
        "- TEXT profile: `tuned_text_section_boost_bm25` remains `diagnostic_only`.",
        "",
        "## Counts",
        "",
    ]
    for key, value in counts.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Lane Counts", ""])
    for lane, count in sorted(sampler["lane_counts"].items()):
        target = sampler["targets"].get(lane, {})
        lines.append(f"- {lane}: `{count}` cases (target `{target.get('min')}-{target.get('max')}`)")
    if sampler["limitations"]:
        lines.extend(["", "## Limitations", ""])
        for item in sampler["limitations"]:
            lines.append(f"- {item}")
    lines.extend(["", "## Guardrails", ""])
    for key, value in payload["policy"].items():
        if isinstance(value, Mapping):
            compact = ", ".join(f"{subkey}={subvalue}" for subkey, subvalue in value.items())
            lines.append(f"- {key}: `{compact}`")
        else:
            lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def render_lane_breakdown_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Answer Recovery Lane Breakdown",
        "",
        "| lane | total | initially_supported | supported_after_recovery | clarification_needed | unsupported_after_recovery | wrongly_supported | unsupported_correctly_blocked | citation_delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    deltas = payload["failure_taxonomy"]["citation_coverage_delta_by_lane"]
    for lane, item in payload["lane_breakdown"].items():
        lines.append(
            "| {lane} | {total} | {initially_supported} | {supported_after_recovery} | "
            "{clarification_needed} | {unsupported_after_recovery} | {wrongly_supported} | "
            "{unsupported_correctly_blocked} | {delta} |".format(
                lane=lane,
                total=item["total"],
                initially_supported=item["initially_supported"],
                supported_after_recovery=item["supported_after_recovery"],
                clarification_needed=item["clarification_needed"],
                unsupported_after_recovery=item["unsupported_after_recovery"],
                wrongly_supported=item["wrongly_supported"],
                unsupported_correctly_blocked=item["unsupported_correctly_blocked"],
                delta=deltas.get(lane, 0.0),
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_failure_taxonomy_md(payload: Mapping[str, Any]) -> str:
    taxonomy = payload["failure_taxonomy"]
    lines = [
        "# Answer Recovery Failure Taxonomy",
        "",
        "## Status Counts",
        "",
    ]
    for key, value in taxonomy["status_counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failure Types", ""])
    for key, value in taxonomy["failure_type_counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Recovery Success By Lane", ""])
    if taxonomy["recovery_success_by_lane"]:
        for key, value in taxonomy["recovery_success_by_lane"].items():
            lines.append(f"- {key}: `{value}`")
    else:
        lines.append("- none: `0`")
    lines.extend(["", "## Clarification By Failure Type", ""])
    if taxonomy["clarification_by_failure_type"]:
        for key, value in taxonomy["clarification_by_failure_type"].items():
            lines.append(f"- {key}: `{value}`")
    else:
        lines.append("- none: `0`")
    lines.extend(["", "## Loop Iteration Distribution", ""])
    if taxonomy["loop_iteration_distribution"]:
        for key, value in taxonomy["loop_iteration_distribution"].items():
            lines.append(f"- {key}: `{value}`")
    else:
        lines.append("- none: `0`")
    lines.append("")
    return "\n".join(lines)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(fieldnames or sorted({key for row in rows for key in row.keys()}) or ["empty"])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def average(values: Sequence[float | int]) -> float:
    return round(sum(float(value) for value in values) / len(values), 6) if values else 0.0


def resolve_path(value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai-worker":
        return REPO_ROOT / path
    return AI_WORKER_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
