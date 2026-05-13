from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_text_namu_local_llm_rewrite_v2.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_text_namu_local_llm_rewrite_v2", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rewrite_v2 = load_module()


def test_local_llm_unavailable_fails_closed_with_explicit_blocker():
    blockers = rewrite_v2.local_llm_entry_blockers(
        backend="llamacpp",
        base_url="http://example.com/v1",
        model="gemma4-e2b-local",
        check_endpoint=False,
    )

    assert "external/cloud LLM endpoints are forbidden; use localhost only" in blockers


def test_db_unavailable_fails_closed_with_explicit_blocker():
    status = rewrite_v2.load_db_context(
        [candidate_row()],
        db_dsn="host=localhost port=1 dbname=missing user=missing password=missing connect_timeout=1",
    )

    assert status["status"] == "DB_UNAVAILABLE_FAIL_CLOSED"
    assert status["db_context_used"] is False
    assert status["blocker"]


def test_rewrite_prompt_excludes_expected_gold_and_human_fields():
    row = candidate_row()
    row["expected_answer"] = "do not pass"
    row["human_review_notes"] = "do not pass"
    row["embedding_text"] = "do not pass"
    row["debug_text"] = "do not pass"
    context = rewrite_v2.build_source_context(row, {})
    prompt = rewrite_v2.build_rewrite_prompt(row, context, prompt_version="test-v1")

    lowered = prompt.lower()
    assert "expected_answer" not in lowered
    assert "human_review_notes" not in lowered
    assert "embedding_text" not in lowered
    assert "debug_text" not in lowered
    assert "gold_seed" not in lowered
    assert "gold.csv" not in lowered
    assert "answer_claims must use the same language" in prompt
    assert "each answer_claim must be copied from evidence_spans" in prompt
    assert "감독은 홍길동" in prompt


def test_local_llm_output_must_be_strict_json():
    assert rewrite_v2.parse_strict_json_object('{"rewritten_answer": "답변"}') == {"rewritten_answer": "답변"}

    try:
        rewrite_v2.parse_strict_json_object('```json\n{"rewritten_answer": "답변"}\n```')
    except ValueError as exc:
        assert "strict JSON object" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("markdown fenced JSON must fail strict parsing")


def test_missing_answer_claims_are_repaired_when_rewritten_answer_is_supported():
    payload = valid_llm_payload()
    payload["rewritten_answer"] = "감독은 홍길동이고 방영 시기는 2024년 4월이다."
    payload["evidence_spans"] = ["감독은 홍길동이고 방영 시기는 2024년 4월이다."]
    payload["answer_claims"] = []

    result = rewrite_v2.verify_llm_output(candidate_row(), source_context(), payload)

    assert result["verifier_passed"] is True
    assert result["answer_claims"] == ["감독은 홍길동이고 방영 시기는 2024년 4월이다."]
    assert result["deterministic_claim_repair"] is True
    assert result["official_metric_input"] is False
    assert result["promotion_evidence"] is False


def test_missing_answer_claims_repair_fails_closed_when_answer_has_unsupported_fact():
    payload = valid_llm_payload()
    payload["rewritten_answer"] = "감독은 홍길동이고 제작사는 없는회사이다."
    payload["evidence_spans"] = ["감독은 홍길동이다."]
    payload["answer_claims"] = []

    result = rewrite_v2.verify_llm_output(candidate_row(), source_context(), payload)

    assert result["verifier_passed"] is False
    assert result["deterministic_claim_repair"] is False
    assert "answer_claims are required" in result["verifier_errors"]
    assert result["rewrite_status"] == "ANSWER_REWRITE_REQUIRED"


def test_unsupported_claims_fail_closed():
    result = rewrite_v2.verify_llm_output(candidate_row(), source_context(), valid_llm_payload(unsupported=["추가 주장"]))

    assert result["verifier_passed"] is False
    assert "unsupported_claims must be empty" in result["verifier_errors"]


def test_supported_claim_plus_unsupported_extra_fact_fails_closed():
    payload = valid_llm_payload()
    payload["rewritten_answer"] = "감독은 홍길동이고 제작사는 없는회사이다."
    payload["evidence_spans"] = ["감독은 홍길동이다."]
    payload["evidence_span_chunk_ids"] = ["chunk-1"]
    payload["answer_claims"] = ["감독은 홍길동이다", "제작사는 없는회사이다"]

    result = rewrite_v2.verify_llm_output(candidate_row(), source_context(), payload)

    assert result["verifier_passed"] is False
    assert "answer claim is not supported by evidence spans: 제작사는 없는회사이다" in result["verifier_errors"]


def test_evidence_spans_must_appear_in_cited_context():
    payload = valid_llm_payload()
    payload["evidence_spans"] = ["문맥에 없는 근거"]

    result = rewrite_v2.verify_llm_output(candidate_row(), source_context(), payload)

    assert result["verifier_passed"] is False
    assert any("evidence span not found in cited context" in err for err in result["verifier_errors"])


def test_cited_chunks_must_be_from_candidate_cited_or_retrieved_chunks():
    payload = valid_llm_payload()
    payload["cited_chunk_ids"] = ["chunk-not-allowed"]
    payload["evidence_span_chunk_ids"] = ["chunk-not-allowed"]

    result = rewrite_v2.verify_llm_output(candidate_row(), source_context(), payload)

    assert result["verifier_passed"] is False
    assert "local LLM output cites chunks outside candidate cited/retrieved chunks: chunk-not-allowed" in result[
        "verifier_errors"
    ]


def test_single_candidate_chunk_id_is_normalized_across_multiple_evidence_spans():
    payload = valid_llm_payload()
    payload["evidence_spans"] = ["감독은 홍길동", "방영 시기는 2024년 4월"]
    payload["evidence_span_chunk_ids"] = ["chunk-1"]

    result = rewrite_v2.verify_llm_output(candidate_row(), source_context(), payload)

    assert result["verifier_passed"] is True
    assert result["evidence_span_chunk_ids"] == ["chunk-1", "chunk-1"]
    assert "repeated single evidence_span_chunk_id for same candidate chunk" in result["normalization_notes"]


def test_claim_support_allows_korean_particle_and_copula_variants():
    payload = valid_llm_payload()
    payload["rewritten_answer"] = "감독은 홍길동입니다."
    payload["evidence_spans"] = ["감독은 홍길동이고 방영 시기는 2024년 4월이다."]
    payload["evidence_span_chunk_ids"] = ["chunk-1"]
    payload["answer_claims"] = ["감독은 홍길동입니다"]

    result = rewrite_v2.verify_llm_output(candidate_row(), source_context(), payload)

    assert result["verifier_passed"] is True


def test_claim_tokens_split_across_unrelated_spans_do_not_pass():
    row = candidate_row()
    row["citation_items"][0]["citation_text"] = "감독은 홍길동이다. 제작사는 스튜디오 바인드이다."
    payload = valid_llm_payload()
    payload["rewritten_answer"] = "감독은 홍길동이고 제작사는 스튜디오 바인드이다."
    payload["evidence_spans"] = ["감독은 홍길동이다.", "제작사는 스튜디오 바인드이다."]
    payload["evidence_span_chunk_ids"] = ["chunk-1", "chunk-1"]
    payload["answer_claims"] = ["감독은 홍길동이고 제작사는 스튜디오 바인드이다"]

    result = rewrite_v2.verify_llm_output(row, rewrite_v2.build_source_context(row, {}), payload)

    assert result["verifier_passed"] is False
    assert any("answer claim is not supported by evidence spans" in err for err in result["verifier_errors"])


def test_split_span_support_must_be_explicit_for_compound_claim():
    row = candidate_row()
    row["citation_items"][0]["citation_text"] = "2024년 1월 27일 공개 예정인 일본 영화. 원작의 6,7권 분량을 다루고 있다."
    payload = valid_llm_payload()
    payload["rewritten_answer"] = "2024년 1월 27일 공개 예정인 일본 영화이며 원작의 6,7권 분량을 다루고 있다."
    payload["evidence_spans"] = ["2024년 1월 27일 공개 예정인 일본 영화.", "원작의 6,7권 분량을 다루고 있다."]
    payload["evidence_span_chunk_ids"] = ["chunk-1", "chunk-1"]
    payload["answer_claims"] = [
        "2024년 1월 27일 공개 예정인 일본 영화이며 원작의 6,7권 분량을 다루고 있다."
    ]

    result_without_flag = rewrite_v2.verify_llm_output(row, rewrite_v2.build_source_context(row, {}), payload)

    assert result_without_flag["verifier_passed"] is False
    assert result_without_flag["split_span_support"] is False

    result_with_flag = rewrite_v2.verify_llm_output(
        row,
        rewrite_v2.build_source_context(row, {}),
        {**payload, "split_span_support": True},
    )

    assert result_with_flag["verifier_passed"] is True
    assert result_with_flag["split_span_support"] is True


def test_claim_support_rejects_negation_mismatch():
    payload = valid_llm_payload()
    payload["rewritten_answer"] = "감독은 홍길동이 아니다."
    payload["evidence_spans"] = ["감독은 홍길동이다."]
    payload["evidence_span_chunk_ids"] = ["chunk-1"]
    payload["answer_claims"] = ["감독은 홍길동이 아니다"]

    result = rewrite_v2.verify_llm_output(candidate_row(), source_context(), payload)

    assert result["verifier_passed"] is False
    assert any("answer claim is not supported by evidence spans" in err for err in result["verifier_errors"])


def test_negation_detection_ignores_embedded_title_word_without_weakening_explicit_negation():
    positive_claim = "감독은 마츠다 키요시이다."
    title_span = "터무니없는 스킬로 이세계 방랑 밥의 감독은 마츠다 키요시이다."

    assert rewrite_v2.negation_matches(positive_claim, title_span) is True
    assert rewrite_v2.negation_matches("감독은 마츠다 키요시가 아니다.", title_span) is False


def test_claim_support_preserves_common_role_binding():
    row = candidate_row()
    row["citation_items"][0]["citation_text"] = "감독은 김철수이고 제작사는 홍길동이다."
    payload = valid_llm_payload()
    payload["rewritten_answer"] = "감독은 홍길동이다."
    payload["evidence_spans"] = ["감독은 김철수이고 제작사는 홍길동이다."]
    payload["evidence_span_chunk_ids"] = ["chunk-1"]
    payload["answer_claims"] = ["감독은 홍길동이다"]

    result = rewrite_v2.verify_llm_output(row, rewrite_v2.build_source_context(row, {}), payload)

    assert result["verifier_passed"] is False
    assert any("answer claim is not supported by evidence spans" in err for err in result["verifier_errors"])


def test_span_matching_normalizes_punctuation_spacing():
    payload = valid_llm_payload()
    payload["rewritten_answer"] = "감독은 홍길동이다."
    payload["evidence_spans"] = ["감독은 홍길동."]
    payload["evidence_span_chunk_ids"] = ["chunk-1"]
    payload["answer_claims"] = ["감독은 홍길동"]

    row = candidate_row()
    row["citation_items"][0]["citation_text"] = "감독은 홍길동 ."
    result = rewrite_v2.verify_llm_output(row, rewrite_v2.build_source_context(row, {}), payload)

    assert result["verifier_passed"] is True


def test_verified_rewrite_output_keeps_official_and_promotion_flags_false():
    result = rewrite_v2.verify_llm_output(candidate_row(), source_context(), valid_llm_payload())

    assert result["verifier_passed"] is True
    assert result["diagnostic_only"] is True
    assert result["official_metric_input"] is False
    assert result["promotion_evidence"] is False


def test_llm_payload_cannot_set_official_metric_or_promotion_flags():
    payload = valid_llm_payload()
    payload["official_metric_input"] = True
    payload["promotion_evidence"] = True

    result = rewrite_v2.verify_llm_output(candidate_row(), source_context(), payload)

    assert result["verifier_passed"] is False
    assert "official_metric_input must remain false" in result["verifier_errors"]
    assert "promotion_evidence must remain false" in result["verifier_errors"]
    assert result["official_metric_input"] is False
    assert result["promotion_evidence"] is False
    assert result["rewrite_status"] == "ANSWER_REWRITE_REQUIRED"


def test_evidence_span_must_match_declared_chunk_not_any_allowed_chunk():
    row = candidate_row()
    row["cited_chunk_ids"] = ["chunk-1", "chunk-2"]
    row["retrieved_chunk_ids"] = ["chunk-1", "chunk-2"]
    row["citation_items"].append(
        {
            "chunk_id": "chunk-2",
            "citation_text": "제작사는 스튜디오 바인드이다.",
            "citation_locator": {"page_id": "page-2"},
        }
    )
    payload = valid_llm_payload()
    payload["rewritten_answer"] = "제작사는 스튜디오 바인드이다."
    payload["cited_chunk_ids"] = ["chunk-2"]
    payload["evidence_spans"] = ["제작사는 스튜디오 바인드이다."]
    payload["evidence_span_chunk_ids"] = ["chunk-1"]
    payload["answer_claims"] = ["제작사는 스튜디오 바인드이다"]

    result = rewrite_v2.verify_llm_output(row, rewrite_v2.build_source_context(row, {}), payload)

    assert result["verifier_passed"] is False
    assert any("evidence span not found in cited context" in err for err in result["verifier_errors"])


def test_failed_verifier_keep_status_does_not_count_as_improved():
    report = rewrite_v2.build_v2_reports(
        generated_rows=[candidate_row("text_001")],
        applied_v1={
            "applied_rows": [applied_row("text_001", "ANSWER_REWRITE_REQUIRED")],
            "diagnostic_metric_preview": {
                "answer_pass_preview_count": 0,
                "cleanup_pass_preview_count": 0,
                "rewrite_required_count": 1,
                "citation_fully_supported_generated_answer_count": 0,
                "citation_contains_correct_answer_but_generated_answer_incomplete_count": 1,
            },
        },
        rewritten_rows=[
            {
                **rewrite_v2.verify_llm_output(
                    candidate_row("text_001"),
                    source_context(),
                    {**valid_llm_payload(unsupported=["추가 주장"]), "rewrite_status": "KEEP_DIAGNOSTIC_CANDIDATE"},
                ),
                "query_id": "text_001",
            }
        ],
        db_context_report={"status": "NO_CANDIDATE_DB_MATCHES", "db_context_used": False},
        llm_provenance={"backend": "llamacpp", "model": "gemma4-e2b-local"},
    )

    assert report["applied_v2"]["diagnostic_metric_preview"]["answer_pass_preview_count"] == 0
    assert report["applied_v2"]["diagnostic_metric_preview"]["rewrite_required_count"] == 1
    assert report["applied_v2"]["diagnostic_metric_preview"]["unresolved_diagnostic_count"] == 1
    assert report["comparison"]["rows_improved"] == []


def test_metric_pass_candidate_still_cannot_open_official_metrics():
    rows = [
        {
            "assistant_review_action": "KEEP_DIAGNOSTIC_CANDIDATE",
            "assistant_citation_support_judgment": "fully_supported",
            "official_metric_input": False,
            "promotion_evidence": False,
        }
        for _ in range(60)
    ]

    metric = rewrite_v2.metric_preview_from_draft(rows)
    target = rewrite_v2.target_status(metric)

    assert target["metric_pass_candidate"] is True
    assert target["official_metric"] is False
    assert target["official_metric_blocker"]
    assert metric["official_metric_input_rows"] == 0
    assert metric["official_metric_status"] == "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY"


def test_v2_1_markdown_labels_compare_v2_against_v2_1():
    report = rewrite_v2.build_v2_1_reports(
        generated_rows=[candidate_row("text_001"), candidate_row("text_002")],
        applied_v2={
            "schema_version": "rag_text_namu_answer_citation_review_applied_diagnostic_v2",
            "applied_rows": [
                applied_row("text_001", "ANSWER_REWRITE_REQUIRED"),
                applied_row("text_002", "KEEP_DIAGNOSTIC_CANDIDATE"),
            ],
            "diagnostic_metric_preview": {
                "answer_pass_preview_count": 1,
                "cleanup_pass_preview_count": 0,
                "rewrite_required_count": 1,
                "citation_fully_supported_generated_answer_count": 1,
                "citation_contains_correct_answer_but_generated_answer_incomplete_count": 1,
            },
        },
        rewritten_rows=[
            {**rewrite_v2.verify_llm_output(candidate_row("text_001"), source_context(), valid_llm_payload()), "query_id": "text_001"},
            rewrite_v2.preserved_v2_row(candidate_row("text_002"), applied_row("text_002", "KEEP_DIAGNOSTIC_CANDIDATE")),
        ],
        db_context_report={"status": "NO_CANDIDATE_DB_MATCHES", "db_context_used": False},
        llm_provenance={"backend": "llamacpp", "model": "gemma4-e2b-local"},
        target_query_ids=["text_001"],
    )

    markdown = rewrite_v2.compact_md_report(report)

    assert "Diagnostic V2.1" in markdown
    assert "## V2 vs V2.1" in markdown
    assert "| Metric | V2 | V2.1 |" in markdown


def test_verified_llm_cleanup_status_counts_as_cleanup_not_clean_pass():
    payload = {**valid_llm_payload(), "rewrite_status": "KEEP_WITH_CLEANUP"}
    report = rewrite_v2.build_v2_reports(
        generated_rows=[candidate_row("text_001")],
        applied_v1={
            "applied_rows": [applied_row("text_001", "ANSWER_REWRITE_REQUIRED")],
            "diagnostic_metric_preview": {
                "answer_pass_preview_count": 0,
                "cleanup_pass_preview_count": 0,
                "rewrite_required_count": 1,
                "citation_fully_supported_generated_answer_count": 0,
                "citation_contains_correct_answer_but_generated_answer_incomplete_count": 1,
            },
        },
        rewritten_rows=[
            {
                **rewrite_v2.verify_llm_output(candidate_row("text_001"), source_context(), payload),
                "query_id": "text_001",
            }
        ],
        db_context_report={"status": "NO_CANDIDATE_DB_MATCHES", "db_context_used": False},
        llm_provenance={"backend": "llamacpp", "model": "gemma4-e2b-local"},
    )

    assert report["applied_v2"]["diagnostic_metric_preview"]["answer_pass_preview_count"] == 0
    assert report["applied_v2"]["diagnostic_metric_preview"]["cleanup_pass_preview_count"] == 1
    assert report["comparison"]["rows_improved"] == ["text_001"]


def test_build_reports_preserves_v1_artifact_and_keeps_cleanup_separate(tmp_path: Path):
    generated_path = tmp_path / "generated.jsonl"
    applied_v1_path = tmp_path / "applied_v1.json"
    write_jsonl(generated_path, [candidate_row("text_001"), candidate_row("text_002"), candidate_row("text_003")])
    write_json(
        applied_v1_path,
        {
            "applied_rows": [
                applied_row("text_001", "KEEP_DIAGNOSTIC_CANDIDATE"),
                applied_row("text_002", "KEEP_WITH_CLEANUP"),
                applied_row("text_003", "ANSWER_REWRITE_REQUIRED"),
            ],
            "diagnostic_metric_preview": {
                "answer_pass_preview_count": 1,
                "cleanup_pass_preview_count": 1,
                "rewrite_required_count": 1,
                "citation_fully_supported_generated_answer_count": 2,
                "citation_contains_correct_answer_but_generated_answer_incomplete_count": 1,
            },
        },
    )
    before_v1 = applied_v1_path.read_text(encoding="utf-8")
    rewritten_rows = [
        rewrite_v2.preserved_v2_row(candidate_row("text_001"), applied_row("text_001", "KEEP_DIAGNOSTIC_CANDIDATE")),
        rewrite_v2.preserved_v2_row(candidate_row("text_002"), applied_row("text_002", "KEEP_WITH_CLEANUP")),
        {**rewrite_v2.verify_llm_output(candidate_row("text_003"), source_context(), valid_llm_payload()), "query_id": "text_003"},
    ]

    report = rewrite_v2.build_v2_reports(
        generated_rows=read_jsonl(generated_path),
        applied_v1=json.loads(applied_v1_path.read_text(encoding="utf-8")),
        rewritten_rows=rewritten_rows,
        db_context_report={"status": "NO_CANDIDATE_DB_MATCHES", "db_context_used": False},
        llm_provenance={"backend": "llamacpp", "model": "gemma4-e2b-local"},
    )

    assert applied_v1_path.read_text(encoding="utf-8") == before_v1
    assert report["applied_v2"]["diagnostic_metric_preview"]["answer_pass_preview_count"] == 2
    assert report["applied_v2"]["diagnostic_metric_preview"]["cleanup_pass_preview_count"] == 1
    assert report["applied_v2"]["diagnostic_metric_preview"]["rewrite_required_count"] == 0
    assert report["applied_v2"]["diagnostic_metric_preview"]["official_metric_input_rows"] == 0
    assert report["comparison"]["rows_improved"] == ["text_003"]


def test_official_denominator_registry_path_is_not_a_write_target():
    assert rewrite_v2.OFFICIAL_DENOMINATOR_REGISTRY not in rewrite_v2.default_output_paths().values()
    assert rewrite_v2.DEFAULT_APPLIED_V1 not in rewrite_v2.default_output_paths().values()


def test_run_rewrite_blocks_when_local_llm_unavailable_without_calling_model(tmp_path: Path, monkeypatch):
    paths = write_run_fixture(tmp_path, action="ANSWER_REWRITE_REQUIRED")
    monkeypatch.setattr(
        rewrite_v2,
        "load_db_context",
        lambda rows, db_dsn: {"status": "NO_CANDIDATE_DB_MATCHES", "db_context_used": False, "by_id": {}, "provenance": {}},
    )
    monkeypatch.setattr(
        rewrite_v2,
        "local_llm_entry_blockers",
        lambda **kwargs: ["local llamacpp unavailable: test"],
    )

    def fail_call(**kwargs):
        raise AssertionError("call_local_llm must not be called")

    monkeypatch.setattr(rewrite_v2, "call_local_llm", fail_call)

    report = rewrite_v2.run_rewrite(
        generated_input=paths["generated"],
        applied_v1_path=paths["applied_v1"],
        output_paths=paths["outputs"],
    )

    assert report["comparison"]["rows_blocked_by_local_llm_unavailable"] == 1
    assert report["applied_v2"]["diagnostic_metric_preview"]["rewrite_required_count"] == 1
    row = report["rewritten_rows"][0]
    assert row["local_llm_used"] is False
    assert row["official_metric_input"] is False
    assert row["promotion_evidence"] is False


def test_run_rewrite_blocks_when_db_read_only_guard_fails(tmp_path: Path, monkeypatch):
    paths = write_run_fixture(tmp_path, action="ANSWER_REWRITE_REQUIRED")
    monkeypatch.setattr(
        rewrite_v2,
        "load_db_context",
        lambda rows, db_dsn: {
            "status": "DB_READ_ONLY_GUARD_FAILED",
            "blocker": "transaction_read_only was not on",
            "db_context_used": False,
            "by_id": {},
            "provenance": {},
        },
    )
    monkeypatch.setattr(rewrite_v2, "local_llm_entry_blockers", lambda **kwargs: [])

    def fail_call(**kwargs):
        raise AssertionError("call_local_llm must not be called")

    monkeypatch.setattr(rewrite_v2, "call_local_llm", fail_call)

    report = rewrite_v2.run_rewrite(
        generated_input=paths["generated"],
        applied_v1_path=paths["applied_v1"],
        output_paths=paths["outputs"],
    )

    assert report["comparison"]["rows_blocked_by_db_unavailable"] == 1
    assert report["comparison"]["rows_blocked_by_db_guard_failed"] == 1
    assert report["applied_v2"]["diagnostic_metric_preview"]["rewrite_required_count"] == 1


def test_run_rewrite_keeps_rewrite_required_on_non_strict_llm_response(tmp_path: Path, monkeypatch):
    paths = write_run_fixture(tmp_path, action="ANSWER_REWRITE_REQUIRED")
    monkeypatch.setattr(
        rewrite_v2,
        "load_db_context",
        lambda rows, db_dsn: {"status": "NO_CANDIDATE_DB_MATCHES", "db_context_used": False, "by_id": {}, "provenance": {}},
    )
    monkeypatch.setattr(rewrite_v2, "local_llm_entry_blockers", lambda **kwargs: [])
    monkeypatch.setattr(rewrite_v2, "call_local_llm", lambda **kwargs: '```json\n{"rewritten_answer":"답"}\n```')

    report = rewrite_v2.run_rewrite(
        generated_input=paths["generated"],
        applied_v1_path=paths["applied_v1"],
        output_paths=paths["outputs"],
    )

    assert report["comparison"]["rows_improved"] == []
    assert report["applied_v2"]["diagnostic_metric_preview"]["rewrite_required_count"] == 1
    assert "LOCAL_LLM_REWRITE_FAILED" in report["rewritten_rows"][0]["verifier_errors"][0]


def test_run_rewrite_preserves_applied_v1_and_writes_only_v2_outputs(tmp_path: Path, monkeypatch):
    paths = write_run_fixture(tmp_path, action="ANSWER_REWRITE_REQUIRED")
    before_v1 = paths["applied_v1"].read_text(encoding="utf-8")
    monkeypatch.setattr(
        rewrite_v2,
        "load_db_context",
        lambda rows, db_dsn: {"status": "NO_CANDIDATE_DB_MATCHES", "db_context_used": False, "by_id": {}, "provenance": {}},
    )
    monkeypatch.setattr(rewrite_v2, "local_llm_entry_blockers", lambda **kwargs: [])
    monkeypatch.setattr(rewrite_v2, "call_local_llm", lambda **kwargs: json.dumps(valid_llm_payload(), ensure_ascii=False))

    report = rewrite_v2.run_rewrite(
        generated_input=paths["generated"],
        applied_v1_path=paths["applied_v1"],
        output_paths=paths["outputs"],
    )

    assert paths["applied_v1"].read_text(encoding="utf-8") == before_v1
    assert rewrite_v2.OFFICIAL_DENOMINATOR_REGISTRY not in paths["outputs"].values()
    assert rewrite_v2.DEFAULT_APPLIED_V1 not in paths["outputs"].values()
    assert all(path.exists() for path in paths["outputs"].values())
    assert report["guardrails"]["official_denominator_registry_mutation"] is False
    assert report["guardrails"]["candidate_artifact_mutation"] is False


def test_run_v2_1_repair_preserves_v2_artifacts_and_repairs_only_targets(tmp_path: Path, monkeypatch):
    paths = write_v2_1_fixture(tmp_path)
    before_v2_jsonl = paths["v2_jsonl"].read_text(encoding="utf-8")
    before_applied_v2 = paths["applied_v2"].read_text(encoding="utf-8")
    calls: list[str] = []

    monkeypatch.setattr(
        rewrite_v2,
        "load_db_context",
        lambda rows, db_dsn: {"status": "NO_CANDIDATE_DB_MATCHES", "db_context_used": False, "by_id": {}, "provenance": {}},
    )
    monkeypatch.setattr(rewrite_v2, "local_llm_entry_blockers", lambda **kwargs: [])

    def call_once(**kwargs):
        calls.append(kwargs["prompt"])
        return json.dumps(valid_llm_payload(), ensure_ascii=False)

    monkeypatch.setattr(rewrite_v2, "call_local_llm", call_once)

    report = rewrite_v2.run_v2_1_repair(
        generated_input=paths["generated"],
        v2_rewrite_jsonl=paths["v2_jsonl"],
        applied_v2_path=paths["applied_v2"],
        target_query_ids=["text_001"],
        output_paths=paths["outputs"],
    )

    assert paths["v2_jsonl"].read_text(encoding="utf-8") == before_v2_jsonl
    assert paths["applied_v2"].read_text(encoding="utf-8") == before_applied_v2
    assert len(calls) == 1
    assert report["comparison"]["rows_improved"] == ["text_001"]
    assert report["comparison"]["rows_regressed"] == []
    assert all(path.exists() for path in paths["outputs"].values())
    assert all("_v2_1" in path.name for path in paths["outputs"].values())


def test_run_v2_1_repair_retry_exhaustion_keeps_row_fail_closed(tmp_path: Path, monkeypatch):
    paths = write_v2_1_fixture(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(
        rewrite_v2,
        "load_db_context",
        lambda rows, db_dsn: {"status": "NO_CANDIDATE_DB_MATCHES", "db_context_used": False, "by_id": {}, "provenance": {}},
    )
    monkeypatch.setattr(rewrite_v2, "local_llm_entry_blockers", lambda **kwargs: [])

    def invalid_json(**kwargs):
        calls.append(kwargs["prompt"])
        return "not json"

    monkeypatch.setattr(rewrite_v2, "call_local_llm", invalid_json)

    report = rewrite_v2.run_v2_1_repair(
        generated_input=paths["generated"],
        v2_rewrite_jsonl=paths["v2_jsonl"],
        applied_v2_path=paths["applied_v2"],
        target_query_ids=["text_001"],
        output_paths=paths["outputs"],
        strict_json_retries=2,
    )

    assert len(calls) == 2
    assert report["comparison"]["rows_improved"] == []
    assert report["comparison"]["rows_blocked_by_verifier"] == 1
    assert report["applied_v2"]["diagnostic_metric_preview"]["rewrite_required_count"] == 1
    assert "LOCAL_LLM_REWRITE_FAILED" in report["rewritten_rows"][0]["verifier_errors"][0]
    assert report["rewritten_rows"][0]["official_metric_input"] is False
    assert report["rewritten_rows"][0]["promotion_evidence"] is False


def candidate_row(query_id: str = "text_001") -> dict:
    return {
        "query_id": query_id,
        "safe_query_text": "감독과 방영 시기를 알려줘",
        "generated_answer": "감독만 홍길동입니다.",
        "cited_chunk_ids": ["chunk-1"],
        "retrieved_chunk_ids": ["chunk-1", "chunk-2"],
        "citation_items": [
            {
                "chunk_id": "chunk-1",
                "citation_text": "감독은 홍길동이고 방영 시기는 2024년 4월이다.",
                "citation_locator": {
                    "page_id": "page-1",
                    "section_id": "section-1",
                    "section_path": "개요",
                    "source_url": "https://example.test/work",
                    "source_locator": "source_query_id=gold_seed_0001; source_artifact=gold.csv",
                },
            }
        ],
        "generation_provenance": {"generator_name": "extractive-v1"},
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
    }


def applied_row(query_id: str, action: str) -> dict:
    return {
        "query_id": query_id,
        "assistant_review_action": action,
        "assistant_citation_support_judgment": "fully_supported"
        if action != "ANSWER_REWRITE_REQUIRED"
        else "citation_contains_correct_answer_but_generated_answer_incomplete",
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
    }


def source_context() -> dict:
    return rewrite_v2.build_source_context(candidate_row(), {})


def valid_llm_payload(unsupported: list[str] | None = None) -> dict:
    return {
        "rewritten_answer": "감독은 홍길동이고 방영 시기는 2024년 4월이다.",
        "cited_chunk_ids": ["chunk-1"],
        "evidence_spans": ["감독은 홍길동이고 방영 시기는 2024년 4월이다."],
        "evidence_span_chunk_ids": ["chunk-1"],
        "answer_claims": ["감독은 홍길동이다", "방영 시기는 2024년 4월이다"],
        "unsupported_claims": unsupported or [],
        "missing_information": [],
        "answerability_from_cited_context": True,
        "rewrite_status": "KEEP_DIAGNOSTIC_CANDIDATE",
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_run_fixture(tmp_path: Path, *, action: str) -> dict:
    generated = tmp_path / "generated.jsonl"
    applied_v1 = tmp_path / "applied_v1.json"
    write_jsonl(generated, [candidate_row("text_001")])
    write_json(
        applied_v1,
        {
            "applied_rows": [applied_row("text_001", action)],
            "diagnostic_metric_preview": {
                "answer_pass_preview_count": 0,
                "cleanup_pass_preview_count": 0,
                "rewrite_required_count": 1 if action == "ANSWER_REWRITE_REQUIRED" else 0,
                "citation_fully_supported_generated_answer_count": 0,
                "citation_contains_correct_answer_but_generated_answer_incomplete_count": 1
                if action == "ANSWER_REWRITE_REQUIRED"
                else 0,
            },
        },
    )
    outputs = {
        "v2_jsonl": tmp_path / "out" / "v2.jsonl",
        "v2_report_json": tmp_path / "out" / "v2_report.json",
        "v2_report_md": tmp_path / "out" / "v2_report.md",
        "draft_jsonl": tmp_path / "out" / "draft.jsonl",
        "draft_summary_json": tmp_path / "out" / "draft_summary.json",
        "applied_json": tmp_path / "out" / "applied_v2.json",
        "applied_md": tmp_path / "out" / "applied_v2.md",
        "improvement_json": tmp_path / "out" / "improvement.json",
        "improvement_md": tmp_path / "out" / "improvement.md",
    }
    return {"generated": generated, "applied_v1": applied_v1, "outputs": outputs}


def write_v2_1_fixture(tmp_path: Path) -> dict:
    generated = tmp_path / "generated.jsonl"
    v2_jsonl = tmp_path / "existing" / "rag_text_namu_generated_answer_review_input_local_llm_v2.jsonl"
    applied_v2 = tmp_path / "existing" / "rag_text_namu_answer_citation_review_applied_diagnostic_v2.json"
    v2_jsonl.parent.mkdir(parents=True)
    write_jsonl(generated, [candidate_row("text_001"), candidate_row("text_002")])
    write_jsonl(
        v2_jsonl,
        [
            {
                **rewrite_v2.failure_row(
                    candidate_row("text_001"),
                    source_context(),
                    reason="answer_claims are required",
                    local_llm_provenance={"backend": "llamacpp"},
                    local_llm_used=True,
                ),
                "failure_causes": ["missing_answer_claims"],
            },
            rewrite_v2.preserved_v2_row(candidate_row("text_002"), applied_row("text_002", "KEEP_DIAGNOSTIC_CANDIDATE")),
        ],
    )
    write_json(
        applied_v2,
        {
            "schema_version": "rag_text_namu_answer_citation_review_applied_diagnostic_v2",
            "applied_rows": [
                applied_row("text_001", "ANSWER_REWRITE_REQUIRED"),
                applied_row("text_002", "KEEP_DIAGNOSTIC_CANDIDATE"),
            ],
            "diagnostic_metric_preview": {
                "answer_pass_preview_count": 1,
                "cleanup_pass_preview_count": 0,
                "rewrite_required_count": 1,
                "citation_fully_supported_generated_answer_count": 1,
                "citation_contains_correct_answer_but_generated_answer_incomplete_count": 1,
                "official_metric_input_rows": 0,
            },
        },
    )
    outputs = {
        "v2_jsonl": tmp_path / "out" / "rag_text_namu_generated_answer_review_input_local_llm_v2_1.jsonl",
        "v2_report_json": tmp_path / "out" / "rag_text_namu_generated_answer_review_input_local_llm_v2_1_report.json",
        "v2_report_md": tmp_path / "out" / "rag_text_namu_generated_answer_review_input_local_llm_v2_1_report.md",
        "draft_jsonl": tmp_path / "out" / "rag_text_namu_answer_citation_review_draft_local_llm_v2_1.jsonl",
        "draft_summary_json": tmp_path / "out" / "rag_text_namu_answer_citation_review_draft_local_llm_v2_1_summary.json",
        "draft_summary_md": tmp_path / "out" / "rag_text_namu_answer_citation_review_draft_local_llm_v2_1_summary.md",
        "applied_json": tmp_path / "out" / "rag_text_namu_answer_citation_review_applied_diagnostic_v2_1.json",
        "applied_md": tmp_path / "out" / "rag_text_namu_answer_citation_review_applied_diagnostic_v2_1.md",
        "improvement_json": tmp_path / "out" / "rag_text_namu_answer_citation_local_llm_improvement_report_v2_1.json",
        "improvement_md": tmp_path / "out" / "rag_text_namu_answer_citation_local_llm_improvement_report_v2_1.md",
    }
    return {"generated": generated, "v2_jsonl": v2_jsonl, "applied_v2": applied_v2, "outputs": outputs}
