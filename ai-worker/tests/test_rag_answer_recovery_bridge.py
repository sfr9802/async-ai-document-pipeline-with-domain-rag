from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.capabilities.rag.answer_recovery import (
    ADJACENT_CONTEXT_EXPANSION,
    AGENTIC_RETRIEVAL_LOOP,
    AMBIGUOUS_QUERY,
    INSUFFICIENT_EVIDENCE,
    INSUFFICIENT_RETRIEVAL,
    LANE_MISMATCH,
    NEEDS_CLARIFICATION,
    NEEDS_RECOVERY,
    OCR_SHADOW,
    PDF_CONTENT,
    PDF_FILE_LOOKUP,
    SUPPORTED,
    TEXT,
    UNSUPPORTED,
    XLSX,
    AgenticRetrievalLoopAdapter,
    AnswerEvidenceCandidate,
    AnswerSufficiencyJudge,
    RecoveryPolicyRouter,
    rank_candidates_by_trust,
)
from app.capabilities.rag.generation import RetrievedChunk
from app.capabilities.rag.shadow_lane_contract import (
    IDP_TABLE_MEDIUM,
    MULTIMODAL_CAPTION_LOW,
    NATIVE_TEXT_HIGH,
    OCR_MEDIUM,
    STRUCTURED_XLSX_HIGH,
)


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent


def test_insufficient_retrieval_triggers_agentic_recovery_and_trace():
    judge = AnswerSufficiencyJudge()
    decision = judge.evaluate(
        user_query="근거가 부족한 질문",
        lane=TEXT,
        draft_answer="",
        retrieved_evidence_candidates=[],
    )
    route = RecoveryPolicyRouter().route(user_query="근거가 부족한 질문", lane=TEXT, decision=decision)
    adapter = AgenticRetrievalLoopAdapter()

    result = adapter.run(
        user_query="근거가 부족한 질문",
        lane=TEXT,
        route=route,
        recovery_executor=_recovering_executor,
    )

    assert decision.sufficiency_status == NEEDS_RECOVERY
    assert decision.failure_type == INSUFFICIENT_RETRIEVAL
    assert route.action == AGENTIC_RETRIEVAL_LOOP
    assert result.existing_loop_invoked is True
    assert result.loop_iterations <= 2
    assert result.recovered is True
    assert result.trace


def test_ambiguous_query_triggers_targeted_clarification():
    decision = AnswerSufficiencyJudge().evaluate(
        user_query="매출 알려줘",
        lane=XLSX,
        draft_answer="",
        retrieved_evidence_candidates=[],
        answer_shape_metadata={"ambiguous_query": True},
    )
    route = RecoveryPolicyRouter().route(user_query="매출 알려줘", lane=XLSX, decision=decision)

    assert decision.sufficiency_status == NEEDS_CLARIFICATION
    assert decision.failure_type == AMBIGUOUS_QUERY
    assert route.clarification_question
    assert "시트" in route.clarification_question
    assert "기간" in route.clarification_question
    assert "지표" in route.clarification_question
    assert "자세히" not in route.clarification_question


def test_unsupported_answer_does_not_become_supported_without_citations():
    decision = AnswerSufficiencyJudge().evaluate(
        user_query="PDF 본문 알려줘",
        lane=PDF_CONTENT,
        draft_answer="This answer has no usable citation support.",
        retrieved_evidence_candidates=[
            AnswerEvidenceCandidate(lane=PDF_CONTENT, text="body", citation_text="", location_json=None)
        ],
        answer_shape_metadata={"has_user_constraint": True},
    )

    assert decision.sufficiency_status == UNSUPPORTED
    assert decision.failure_type == INSUFFICIENT_EVIDENCE
    assert decision.official_support is False


def test_hidden_xlsx_content_cannot_be_surfaced():
    decision = AnswerSufficiencyJudge().evaluate(
        user_query="숨김 시트 값을 알려줘",
        lane=XLSX,
        draft_answer="hidden value",
        retrieved_evidence_candidates=[
            _candidate(
                lane=XLSX,
                trust=STRUCTURED_XLSX_HIGH,
                citation="book.xlsx > Hidden > A1:B2",
                location={"sheet_name": "Hidden", "cell_range": "A1:B2"},
                hidden=True,
                metadata={"strict_wrapper": True},
            )
        ],
        answer_shape_metadata={"has_user_constraint": True},
    )

    assert decision.sufficiency_status == UNSUPPORTED
    assert "XLSX_HIDDEN_CONTENT" in decision.blocked_lanes


def test_xlsx_strict_wrapper_policy_is_respected():
    blocked = AnswerSufficiencyJudge().evaluate(
        user_query="Sheet1 2024 매출 합계",
        lane=XLSX,
        draft_answer="Sheet1 2024 revenue total is supported by visible evidence.",
        retrieved_evidence_candidates=[
            _candidate(
                lane=XLSX,
                trust=STRUCTURED_XLSX_HIGH,
                citation="book.xlsx > Sheet1 > A1:B2",
                location={"sheet_name": "Sheet1", "cell_range": "A1:B2"},
                metadata={"strict_wrapper": False},
            )
        ],
        answer_shape_metadata={"has_user_constraint": True},
    )
    supported = AnswerSufficiencyJudge().evaluate(
        user_query="Sheet1 2024 매출 합계",
        lane=XLSX,
        draft_answer="Sheet1 2024 revenue total is supported by visible strict wrapper evidence.",
        retrieved_evidence_candidates=[
            _candidate(
                lane=XLSX,
                trust=STRUCTURED_XLSX_HIGH,
                citation="book.xlsx > Sheet1 > A1:B2",
                location={"sheet_name": "Sheet1", "cell_range": "A1:B2"},
                metadata={"strict_wrapper": True},
            )
        ],
        answer_shape_metadata={"has_user_constraint": True},
    )

    assert blocked.sufficiency_status == UNSUPPORTED
    assert "NON_STRICT_XLSX_WRAPPER" in blocked.blocked_lanes
    assert supported.sufficiency_status == SUPPORTED


def test_pdf_file_lookup_cannot_support_content_or_page_answers():
    decision = AnswerSufficiencyJudge().evaluate(
        user_query="이 PDF의 3페이지 표 값을 알려줘",
        lane=PDF_FILE_LOOKUP,
        draft_answer="file.pdf",
        retrieved_evidence_candidates=[
            _candidate(
                lane=PDF_FILE_LOOKUP,
                trust=NATIVE_TEXT_HIGH,
                citation="file.pdf",
                location={"type": "file_identity"},
            )
        ],
        answer_shape_metadata={"answer_intent": "table"},
    )
    route = RecoveryPolicyRouter().route(
        user_query="이 PDF의 3페이지 표 값을 알려줘",
        lane=PDF_FILE_LOOKUP,
        decision=decision,
    )

    assert decision.sufficiency_status == NEEDS_RECOVERY
    assert decision.failure_type == LANE_MISMATCH
    assert PDF_FILE_LOOKUP in decision.blocked_lanes
    assert route.target_lane == PDF_CONTENT


def test_native_pdf_text_outranks_ocr_fallback():
    ranked = rank_candidates_by_trust(
        [
            _candidate(
                lane=OCR_SHADOW,
                trust=OCR_MEDIUM,
                citation="report.pdf OCR",
                location={"page": 1},
                diagnostic=True,
            ),
            _candidate(
                lane=PDF_CONTENT,
                trust=NATIVE_TEXT_HIGH,
                citation="report.pdf > p.1",
                location={"page": 1},
            ),
        ]
    )

    assert ranked[0].trust_tier == NATIVE_TEXT_HIGH
    assert ranked[1].trust_tier == OCR_MEDIUM


def test_shadow_evidence_stays_diagnostic_only():
    for trust in (OCR_MEDIUM, IDP_TABLE_MEDIUM, MULTIMODAL_CAPTION_LOW):
        decision = AnswerSufficiencyJudge().evaluate(
            user_query="diagnostic evidence answer",
            lane=OCR_SHADOW,
            draft_answer="A diagnostic-only item cannot make this officially supported.",
            retrieved_evidence_candidates=[
                _candidate(
                    lane=OCR_SHADOW,
                    trust=trust,
                    citation="diagnostic citation",
                    location={"page": 1},
                    diagnostic=True,
                )
            ],
            answer_shape_metadata={"has_user_constraint": True},
        )
        assert decision.sufficiency_status != SUPPORTED
        assert decision.official_support is False


def test_local_llm_diagnostic_output_is_not_promotion_evidence():
    decision = AnswerSufficiencyJudge().evaluate(
        user_query="local smoke output",
        lane=TEXT,
        draft_answer="Local LLM smoke output should stay diagnostic only even when it looks useful.",
        retrieved_evidence_candidates=[
            _candidate(lane=TEXT, trust=NATIVE_TEXT_HIGH, citation="text > section", location={"section": "s"})
        ],
        answer_shape_metadata={"local_llm_smoke_output": True, "has_user_constraint": True},
    )

    assert decision.sufficiency_status != SUPPORTED
    assert "LOCAL_LLM_SMOKE_PROMOTION_EVIDENCE" in decision.blocked_lanes


def test_recovery_guardrails_block_mutation_and_enforce_iteration_cap():
    decision = AnswerSufficiencyJudge().evaluate(
        user_query="missing evidence",
        lane=TEXT,
        draft_answer="",
        retrieved_evidence_candidates=[],
    )
    route = RecoveryPolicyRouter().route(user_query="missing evidence", lane=TEXT, decision=decision)
    adapter = AgenticRetrievalLoopAdapter()
    result = adapter.run(user_query="missing evidence", lane=TEXT, route=route, recovery_executor=_never_recovering_executor)

    assert adapter.guardrails.production_index_mutation is False
    assert adapter.guardrails.official_denominator_mutation is False
    assert adapter.guardrails.allow_broad_indexing is False
    assert result.loop_iterations <= 2
    assert result.stop_reason == "iter_cap"


def test_diagnostic_harness_emits_reports_and_trace(tmp_path: Path):
    registry = REPO_ROOT / "ai-worker" / "eval" / "eval_queries" / "official_denominator_registry.json"
    registry_before = registry.read_text(encoding="utf-8") if registry.exists() else None
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "ai-worker" / "scripts" / "rag_answer_recovery_diagnostic.py"),
            "--reports-dir",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "PASS" in result.stdout
    report = json.loads((tmp_path / "answer_sufficiency_diagnostic_report.json").read_text(encoding="utf-8"))
    trace = (tmp_path / "answer_recovery_trace.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert report["policy"]["official_denominator_registry_changed"] is False
    assert report["policy"]["production_index_mutation"] is False
    assert report["counts"]["total_evaluated"] > 0
    assert trace
    if registry_before is not None:
        assert registry.read_text(encoding="utf-8") == registry_before


def _candidate(
    *,
    lane: str,
    trust: str,
    citation: str,
    location: dict,
    diagnostic: bool = False,
    hidden: bool = False,
    metadata: dict | None = None,
) -> AnswerEvidenceCandidate:
    return AnswerEvidenceCandidate(
        lane=lane,
        text="visible evidence text",
        citation_text=citation,
        location_json=location,
        trust_tier=trust,
        evidence_role="diagnostic" if diagnostic else "official",
        denominator_role="DIAGNOSTIC_ONLY" if diagnostic else "",
        diagnostic_only=diagnostic,
        hidden=hidden,
        metadata=metadata or {},
    )


def _recovering_executor(parsed_query):
    del parsed_query
    return (
        "Recovered answer grounded in cited evidence with enough detail to pass the deterministic recovery loop.",
        [
            RetrievedChunk(
                chunk_id="c1",
                doc_id="d1",
                section="s1",
                text="Recovered cited evidence",
                score=1.0,
            )
        ],
        0,
    )


def _never_recovering_executor(parsed_query):
    del parsed_query
    return ("", [], 0)
