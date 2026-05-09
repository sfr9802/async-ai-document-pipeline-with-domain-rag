from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from app.capabilities.rag.answer_recovery import (
    ADJACENT_CONTEXT_EXPANSION,
    AGENTIC_RETRIEVAL_LOOP,
    AMBIGUOUS_QUERY,
    IDP_SHADOW,
    INSUFFICIENT_EVIDENCE,
    INSUFFICIENT_RETRIEVAL,
    LANE_MISMATCH,
    MULTIMODAL_SHADOW,
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


def test_pdf_file_lookup_file_identity_intent_ignores_filename_table_marker():
    decision = AnswerSufficiencyJudge().evaluate(
        user_query="2024년 4월 전기요금표 자료를 파일 목록에서 찾아줘",
        lane=PDF_FILE_LOOKUP,
        draft_answer="The answer identifies the requested PDF file identity only.",
        retrieved_evidence_candidates=[
            _candidate(
                lane=PDF_FILE_LOOKUP,
                trust=NATIVE_TEXT_HIGH,
                citation="2024년 4월 전기요금표.pdf",
                location={"type": "file_identity", "candidate_file_name": "2024년 4월 전기요금표.pdf"},
            )
        ],
        answer_shape_metadata={
            "answer_intent": "file_identity",
            "target_file_name": "2024년 4월 전기요금표.pdf",
            "identity_match": True,
        },
    )
    route = RecoveryPolicyRouter().route(
        user_query="2024년 4월 전기요금표 자료를 파일 목록에서 찾아줘",
        lane=PDF_FILE_LOOKUP,
        decision=decision,
    )

    assert decision.sufficiency_status == SUPPORTED
    assert decision.official_support is True
    assert PDF_FILE_LOOKUP not in decision.blocked_lanes
    assert route.target_lane == PDF_FILE_LOOKUP


def test_pdf_file_lookup_hard_negative_identity_row_is_not_supported():
    decision = AnswerSufficiencyJudge().evaluate(
        user_query="2024년 4월 전기요금 종합표 자료를 파일 목록에서 찾아줘",
        lane=PDF_FILE_LOOKUP,
        draft_answer="The diagnostic answer identifies the wrong similar file identity.",
        retrieved_evidence_candidates=[
            _candidate(
                lane=PDF_FILE_LOOKUP,
                trust=NATIVE_TEXT_HIGH,
                citation="2024년도+7월+1일+시행+전기요금표(종합).pdf",
                location={
                    "type": "file_identity",
                    "candidate_file_name": "2024년도+7월+1일+시행+전기요금표(종합).pdf",
                },
            )
        ],
        answer_shape_metadata={
            "answer_intent": "file_identity",
            "target_file_name": "2024년도+4월+1일+시행+전기요금표(종합)_출력용.pdf",
            "candidate_file_name": "2024년도+7월+1일+시행+전기요금표(종합).pdf",
            "silver_label": "SILVER_FILE_LOOKUP_HARD_NEGATIVE_V2",
            "negative_strategy": "same_metadata_family_wrong_file_identity",
        },
    )

    assert decision.sufficiency_status == UNSUPPORTED
    assert "PDF_FILE_HARD_NEGATIVE_IDENTITY" in decision.blocked_lanes


def test_pdf_file_lookup_filename_token_overlap_alone_is_not_supported():
    decision = AnswerSufficiencyJudge().evaluate(
        user_query="2025년 4월 전기요금 종합표 자료를 파일 목록에서 찾아줘",
        lane=PDF_FILE_LOOKUP,
        draft_answer="The answer cites a similar electricity rate table file.",
        retrieved_evidence_candidates=[
            _candidate(
                lane=PDF_FILE_LOOKUP,
                trust=NATIVE_TEXT_HIGH,
                citation="2024년도+4월+1일+시행+전기요금표(종합)_출력용.pdf",
                location={
                    "type": "file_identity",
                    "candidate_file_name": "2024년도+4월+1일+시행+전기요금표(종합)_출력용.pdf",
                },
            )
        ],
        answer_shape_metadata={
            "answer_intent": "file_identity",
            "target_file_name": "2025년도+4월+1일+시행+전기요금표(종합).pdf",
        },
    )

    assert decision.sufficiency_status == UNSUPPORTED
    assert "PDF_FILE_IDENTITY_MISMATCH" in decision.blocked_lanes


def test_pdf_file_lookup_generic_filename_requires_stronger_identity():
    decision = AnswerSufficiencyJudge().evaluate(
        user_query="LH 자료 파일 찾아줘",
        lane=PDF_FILE_LOOKUP,
        draft_answer="The answer identifies file.pdf.",
        retrieved_evidence_candidates=[
            _candidate(
                lane=PDF_FILE_LOOKUP,
                trust=NATIVE_TEXT_HIGH,
                citation="file.pdf",
                location={"type": "file_identity", "candidate_file_name": "file.pdf"},
            )
        ],
        answer_shape_metadata={"answer_intent": "file_identity", "target_file_name": "file.pdf"},
    )

    assert decision.sufficiency_status == NEEDS_CLARIFICATION
    assert "PDF_FILE_GENERIC_FILENAME_AMBIGUOUS" in decision.blocked_lanes


def test_pdf_file_lookup_document_version_id_mismatch_fails_closed():
    decision = AnswerSufficiencyJudge().evaluate(
        user_query="정확한 PDF 파일 찾아줘",
        lane=PDF_FILE_LOOKUP,
        draft_answer="The answer identifies the requested file name.",
        retrieved_evidence_candidates=[
            _candidate(
                lane=PDF_FILE_LOOKUP,
                trust=NATIVE_TEXT_HIGH,
                citation="report.pdf",
                location={
                    "type": "file_identity",
                    "candidate_file_name": "report.pdf",
                    "candidate_document_version_id": "docv_wrong",
                },
            )
        ],
        answer_shape_metadata={
            "answer_intent": "file_identity",
            "target_file_name": "report.pdf",
            "target_document_version_id": "docv_expected",
        },
    )

    assert decision.sufficiency_status == UNSUPPORTED
    assert "PDF_FILE_DOCUMENT_VERSION_ID_MISMATCH" in decision.blocked_lanes


def test_pdf_file_lookup_source_file_id_mismatch_fails_closed():
    decision = AnswerSufficiencyJudge().evaluate(
        user_query="정확한 PDF 파일 찾아줘",
        lane=PDF_FILE_LOOKUP,
        draft_answer="The answer identifies the requested file name.",
        retrieved_evidence_candidates=[
            _candidate(
                lane=PDF_FILE_LOOKUP,
                trust=NATIVE_TEXT_HIGH,
                citation="report.pdf",
                location={
                    "type": "file_identity",
                    "candidate_file_name": "report.pdf",
                    "candidate_source_file_id": "source_wrong",
                },
            )
        ],
        answer_shape_metadata={
            "answer_intent": "file_identity",
            "target_file_name": "report.pdf",
            "target_source_file_id": "source_expected",
        },
    )

    assert decision.sufficiency_status == UNSUPPORTED
    assert "PDF_FILE_SOURCE_FILE_ID_MISMATCH" in decision.blocked_lanes


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
    expanded = json.loads((tmp_path / "answer_sufficiency_expanded_diagnostic_report.json").read_text(encoding="utf-8"))
    trace = (tmp_path / "answer_recovery_trace.jsonl").read_text(encoding="utf-8").strip().splitlines()
    expanded_trace = (tmp_path / "answer_recovery_expanded_trace.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert report["policy"]["official_denominator_registry_changed"] is False
    assert report["policy"]["production_index_mutation"] is False
    assert report["counts"]["total_evaluated"] > 0
    assert expanded["policy"]["official_answer_denominator_opened"] is False
    assert expanded["policy"]["official_denominator_registry_changed"] is False
    assert expanded["policy"]["production_index_mutation"] is False
    assert expanded["counts"]["total_evaluated"] > report["counts"]["total_evaluated"]
    assert trace
    assert expanded_trace
    assert (tmp_path / "answer_recovery_lane_breakdown.md").exists()
    assert (tmp_path / "answer_recovery_failure_taxonomy.md").exists()
    assert (tmp_path / "answer_recovery_wrongly_supported_review.csv").exists()
    readiness = json.loads((tmp_path / "answer_recovery_tuning_readiness_after_calibration.json").read_text(encoding="utf-8"))
    assert readiness["decision"]["tuning_ready"] == "true_for_narrow_silver_only_calibration"
    assert readiness["decision"]["production_promotion_ready"] is False
    assert readiness["decision"]["official_answer_denominator_ready"] is False
    assert readiness["counts"]["wrongly_supported_count"] == 0
    if registry_before is not None:
        assert registry.read_text(encoding="utf-8") == registry_before


def test_expanded_sampler_keeps_lanes_separate_and_pdf_file_identity_only():
    module = _load_diagnostic_script()
    cases, sampler = module.expanded_diagnostic_cases()

    assert sampler["official_answer_denominator_opened"] is False
    assert sampler["official_denominator_registry_changed"] is False
    assert sampler["lane_counts"][TEXT] >= 50
    assert sampler["lane_counts"][XLSX] >= 30
    assert sampler["lane_counts"][PDF_CONTENT] >= 30
    assert sampler["lane_counts"][PDF_FILE_LOOKUP] >= 15
    assert {OCR_SHADOW, IDP_SHADOW, MULTIMODAL_SHADOW}.issubset(sampler["lane_counts"].keys())
    assert all(case.metadata.get("denominator_role") in {"DIAGNOSTIC_EVAL_ONLY", "DIAGNOSTIC_ONLY"} for case in cases)
    assert all(case.metadata.get("official_answer_denominator_opened") is False for case in cases)

    pdf_file_cases = [case for case in cases if case.lane == PDF_FILE_LOOKUP]
    assert pdf_file_cases
    for case in pdf_file_cases:
        assert case.metadata.get("answer_intent") in {"file_identity", "table"}
        for item in case.evidence:
            assert item.location_json.get("type") == "file_identity"
            assert not any(
                key in item.location_json
                for key in ("page_success", "bbox_success", "table_success", "row_success", "column_success", "value_success")
            )


def test_expanded_report_surfaces_taxonomy_and_blocks_diagnostic_evidence():
    module = _load_diagnostic_script()
    expanded = module.run_expanded_diagnostic_cases()
    report = expanded["report"]

    assert report["counts"]["wrongly_supported_count"] == len(expanded["wrongly_supported_rows"])
    assert "wrongly_supported_count" in report["counts"]
    assert "unsupported_correctly_blocked_count" in report["counts"]
    assert "recovery_success_by_lane" in report["failure_taxonomy"]
    assert "clarification_by_failure_type" in report["failure_taxonomy"]
    assert "loop_iteration_distribution" in report["failure_taxonomy"]
    assert "citation_coverage_delta_by_lane" in report["failure_taxonomy"]
    assert report["counts"]["diagnostic_only_evidence_blocked_count"] >= 3
    assert report["counts"]["hidden_xlsx_surface_attempt_count"] >= 1
    assert report["counts"]["pdf_file_lookup_content_mixing_attempt_count"] >= 1
    assert report["policy"]["production_index_mutation"] is False
    assert report["policy"]["broad_indexing"] is False
    assert report["policy"]["max_loop_iterations"] == 2
    assert report["counts"]["wrongly_supported_count"] == 0
    assert all(
        int(iteration_count) <= report["policy"]["max_loop_iterations"]
        for iteration_count in report["failure_taxonomy"]["loop_iteration_distribution"].keys()
    )
    assert report["policy"]["pdf_file_lookup_success_claims"] == {
        "content": False,
        "page": False,
        "bbox": False,
        "table": False,
        "row": False,
        "column": False,
        "value": False,
    }


def test_expanded_wrongly_supported_review_csv_has_schema(tmp_path: Path):
    module = _load_diagnostic_script()
    expanded = module.run_expanded_diagnostic_cases()
    path = tmp_path / "answer_recovery_wrongly_supported_review.csv"
    module.write_csv(
        path,
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

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [
            "case_id",
            "lane",
            "case_type",
            "source_artifact",
            "failure_type",
            "support_score",
            "citation_coverage",
            "diagnostic_reason",
        ]
        assert len(list(reader)) == report_count(expanded, "wrongly_supported_count")


def _load_diagnostic_script():
    module_path = REPO_ROOT / "ai-worker" / "scripts" / "rag_answer_recovery_diagnostic.py"
    spec = importlib.util.spec_from_file_location("rag_answer_recovery_diagnostic_for_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def report_count(expanded: dict, key: str) -> int:
    return int(expanded["report"]["counts"][key])


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
