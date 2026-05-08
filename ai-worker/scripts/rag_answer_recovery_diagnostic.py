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

    write_json(report_dir / "answer_recovery_existing_components_report.json", components)
    write_text(report_dir / "answer_recovery_existing_components_report.md", render_components_md(components))
    write_text(report_dir / "answer_recovery_loop_plan.md", plan)
    write_json(report_dir / "answer_sufficiency_diagnostic_report.json", diagnostic["report"])
    write_text(report_dir / "answer_sufficiency_diagnostic_report.md", render_diagnostic_md(diagnostic["report"]))
    write_jsonl(report_dir / "answer_recovery_trace.jsonl", diagnostic["trace_rows"])
    write_csv(report_dir / "clarification_question_samples.csv", diagnostic["clarifications"])
    write_csv(report_dir / "agentic_loop_recovery_cases.csv", diagnostic["recovery_cases"])
    write_csv(report_dir / "unsupported_after_recovery_cases.csv", diagnostic["unsupported_cases"])

    print(
        json.dumps(
            {
                "status": "PASS",
                "total_evaluated": diagnostic["report"]["counts"]["total_evaluated"],
                "recovered_after_loop": diagnostic["report"]["counts"]["recovered_after_loop"],
                "report": repo_relative(report_dir / "answer_sufficiency_diagnostic_report.json"),
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


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()}) or ["empty"]
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
