from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORTING_PATH = ROOT / "ai" / "eval" / "harness" / "e2e_baseline_reporting.py"
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_eval_baseline_snapshot.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reporting = load_module(REPORTING_PATH, "e2e_baseline_reporting_for_tests")
snapshot = load_module(SCRIPT_PATH, "rag_eval_baseline_snapshot_for_tests")


def test_validate_e2e_llm_io_schema_accepts_required_shape():
    record = reporting.build_io_record(
        run_id="run-1",
        track="B",
        case_id="case-1",
        gold_status="gold",
        query="query",
        retrieval={
            "namespace": "ns",
            "index_version": "idx",
            "top_k": 10,
            "retrieved_doc_ids": ["doc-1"],
            "expected_evidence_ids": ["doc-1"],
            "evidence_hit": True,
        },
        messages=[{"role": "user", "content": "hello"}],
        output_content="answer",
        finish_reason="dry_run",
        model="dry-run",
        temperature=0.0,
        latency_ms=0.0,
        answerability="answerable",
        verdict="needs_human_review",
        grounded=True,
        failure_type=None,
        notes="dry-run",
    )

    assert reporting.validate_e2e_llm_io_record(record) == []


def test_denominator_excludes_candidate_and_diagnostic_only_rows():
    records = [
        _minimal_record("gold-1", "gold", "pass"),
        _minimal_record("cand-1", "candidate", "diagnostic_only"),
        _minimal_record("diag-1", "diagnostic_only", "diagnostic_only"),
    ]

    summary = reporting.aggregate_summary(
        run_id="run-1",
        generated_at="2026-05-05T00:00:00+00:00",
        io_records=records,
        source_metrics={"B": {"Hit@10": 1.0}},
        live_call_executed=True,
    )

    track = summary["track_summaries"]["B"]
    assert track["official_denominator_count"] == 1
    assert track["e2e_evaluated_gold_count"] == 1
    assert track["e2e_pass_rate"] == 1.0
    assert summary["case_counts_by_gold_status"] == {
        "gold": 1,
        "candidate": 1,
        "diagnostic_only": 1,
    }


def test_diagnostic_only_rows_do_not_enter_official_denominator_when_only_rows():
    records = [
        _minimal_record("diag-1", "diagnostic_only", "diagnostic_only"),
        _minimal_record("diag-2", "diagnostic_only", "diagnostic_only"),
    ]

    summary = reporting.aggregate_summary(
        run_id="run-1",
        generated_at="2026-05-05T00:00:00+00:00",
        io_records=records,
        source_metrics={"C": {"pdf_file_hit@10": 1.0}},
        live_call_executed=False,
    )

    track = summary["track_summaries"]["B"]
    assert track["official_denominator_count"] == 0
    assert track["official_retrieval_evidence_hit_rate"] is None
    assert track["e2e_pass_rate"] is None


def test_redaction_covers_llm_io_prompt_output_and_sensitive_keys():
    payload = {
        "Authorization": "Bearer sk-secret-value-123456",
        "nested": {
            "api_key": "sk-ant-secret-value-123456",
            "message": (
                "email test@example.com phone 010-1234-5678 "
                "rrn 990101-1234567 password=secret"
            ),
            "usage": {"input_tokens": 12},
        },
    }

    redacted = reporting.redact(payload)
    dumped = json.dumps(redacted, ensure_ascii=False)

    assert "sk-secret-value" not in dumped
    assert "sk-ant-secret-value" not in dumped
    assert "test@example.com" not in dumped
    assert "010-1234-5678" not in dumped
    assert "990101-1234567" not in dumped
    assert reporting.redaction_marker() in dumped
    assert redacted["nested"]["usage"]["input_tokens"] == 12


def test_report_generation_smoke_writes_artifacts_and_markdown(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("E2E_BASELINE_LIVE_LLM", raising=False)
    paths = write_snapshot_fixture(tmp_path)

    exit_code = snapshot.main(
        [
            "--run-id",
            "test-run",
            "--artifact-root",
            str(paths["artifact_root"]),
            "--report-dir",
            str(paths["report_dir"]),
            "--a-gold",
            str(paths["a_gold"]),
            "--a-retrieval-report",
            str(paths["a_report"]),
            "--b-gold",
            str(paths["b_gold"]),
            "--b-retrieval-report",
            str(paths["b_report"]),
            "--b-context-emit",
            str(paths["b_context"]),
            "--b-context-report",
            str(paths["b_context_report"]),
            "--b-answer-report",
            str(paths["b_answer_report"]),
            "--b-answer-eval",
            str(paths["b_answer_eval"]),
            "--c-gold",
            str(paths["c_gold"]),
            "--c-retrieval-report",
            str(paths["c_report"]),
            "--c-consistency-report",
            str(paths["c_consistency"]),
            "--c-policy-report",
            str(paths["c_policy"]),
        ]
    )

    artifact_dir = paths["artifact_root"] / "test-run"
    io_rows = read_jsonl(artifact_dir / "e2e_llm_io.jsonl")
    summary = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))
    overview = (paths["report_dir"] / "base_before_tuning_overview.md").read_text(encoding="utf-8")
    track_b = (paths["report_dir"] / "base_before_tuning_B.md").read_text(encoding="utf-8")
    denominator = (paths["report_dir"] / "base_before_tuning_denominator_policy.md").read_text(encoding="utf-8")

    assert exit_code == 0
    assert len(io_rows) == 4
    assert reporting.validate_jsonl_records(io_rows) == []
    assert summary["track_summaries"]["A"]["official_denominator_count"] == 1
    assert summary["track_summaries"]["B"]["official_denominator_count"] == 1
    assert summary["track_summaries"]["C"]["official_denominator_count"] == 1
    assert summary["denominator_policy_summary"]["tracks"]["C"]["c7_status"] == "NEEDS_POLICY_DECISION"
    assert "E2E I/O capture path verified, live call not executed" in overview
    assert "## Freshness comparison" in overview
    assert "Track policies" in denominator
    assert "## Artifact paths" in track_b
    assert "RAW CONTEXT SECRET" not in track_b


def _minimal_record(case_id: str, gold_status: str, verdict: str):
    return reporting.build_io_record(
        run_id="run-1",
        track="B",
        case_id=case_id,
        gold_status=gold_status,
        query="query",
        retrieval={
            "namespace": "ns",
            "index_version": "idx",
            "top_k": 10,
            "retrieved_doc_ids": ["doc-1"],
            "expected_evidence_ids": ["doc-1"],
            "evidence_hit": True,
        },
        messages=[{"role": "user", "content": "hello"}],
        output_content="answer",
        finish_reason="stop",
        model="model",
        temperature=0.0,
        latency_ms=1.0,
        answerability="answerable",
        verdict=verdict,
        grounded=True,
        failure_type=None,
        notes="ok",
    )


def write_snapshot_fixture(tmp_path: Path) -> dict[str, Path]:
    a_gold = tmp_path / "a_gold.csv"
    a_gold.write_text(
        "query_id,query,expected_document_version_id,expected_sheet_name,expected_cell_range,label_status,review_decision\n"
        "a1,xlsx query,docv-a,Sheet1,A1:B2,bound,KEEP_AS_POSITIVE\n",
        encoding="utf-8",
    )
    a_report = tmp_path / "a_report.json"
    write_json(
        a_report,
        {
            "metrics": {"Hit@10": 1.0, "MRR@10": 1.0, "required_index_version": "xlsx-ns"},
            "per_query": [
                {
                    "query_id": "a1",
                    "query": "xlsx query",
                    "hit_at_10": True,
                    "top_hit": {
                        "source_file_name": "book.xlsx",
                        "search_unit_id": "su-a",
                        "index_version": "xlsx-ns",
                        "citation_text": "book.xlsx > Sheet1 > A1:B2",
                    },
                }
            ],
        },
    )

    b_gold = tmp_path / "b_gold.csv"
    b_gold.write_text(
        "query_id,bucket,query,expected_page_ids,expected_section_ids,expected_chunk_ids,"
        "expected_answer_summary,must_contain_terms,must_not_contain_terms,allowed_abstain,"
        "answer_type,label_status,source_dataset,notes\n"
        "b1,text_fact,question,doc-b,sec-b,chunk-b,answer,answer,,false,short_fact,bound,fixture,\n"
        "b2,text_fact,review me,doc-c,sec-c,chunk-c,answer,answer,,false,short_fact,needs_review,fixture,\n",
        encoding="utf-8",
    )
    b_report = tmp_path / "b_report.json"
    write_json(
        b_report,
        {
            "top_k": 10,
            "retrieval_backend": "fixture",
            "retrieval_backend_identity": {"name": "fixture-bm25", "corpus_source": "fixture"},
            "metrics": {"Hit@10": 1.0, "MRR@10": 1.0, "positive_denominator_count": 1},
        },
    )
    b_context = tmp_path / "b_context.jsonl"
    write_jsonl(
        b_context,
        [
            {
                "query_id": "b1",
                "query": "question",
                "label_status": "bound",
                "expected_page_ids": ["doc-b"],
                "expected_section_ids": ["sec-b"],
                "expected_chunk_ids": ["chunk-b"],
                "expected_source_present": True,
                "expected_chunk_present": True,
                "retrieval_result_count": 1,
                "contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-b",
                        "chunk_id": "chunk-b",
                        "text": "RAW CONTEXT SECRET should stay out of markdown reports",
                    }
                ],
            },
            {
                "query_id": "b2",
                "query": "review me",
                "label_status": "needs_review",
                "expected_page_ids": ["doc-c"],
                "expected_section_ids": ["sec-c"],
                "expected_chunk_ids": ["chunk-c"],
                "expected_source_present": False,
                "expected_chunk_present": False,
                "retrieval_result_count": 0,
                "contexts": [],
            },
        ],
    )
    b_context_report = tmp_path / "b_context_report.json"
    write_json(b_context_report, {"status": "PASS_WITH_WARNINGS", "r7_ready": True})
    b_answer_report = tmp_path / "b_answer_report.json"
    write_json(
        b_answer_report,
        {
            "status": "PASS_WITH_WARNINGS",
            "answerable_from_context_count": 1,
            "retrieval_context_miss_count": 0,
            "answer_generation_failure_count": 0,
            "live_llm_run": False,
            "context_field": "chunk_text",
        },
    )
    b_answer_eval = tmp_path / "b_answer_eval.jsonl"
    write_jsonl(
        b_answer_eval,
        [
            {
                "query_id": "b1",
                "primary_stage": "answerable_from_context",
                "stages": ["retrieval_context_available", "answerable_from_context", "answer_eval_pending_live_llm"],
                "answerable_from_context": True,
                "answer_eval_pending_live_llm": True,
            },
            {
                "query_id": "b2",
                "primary_stage": "denominator_excluded_needs_review",
                "stages": ["denominator_excluded_needs_review"],
                "answerable_from_context": False,
                "answer_eval_pending_live_llm": False,
            },
        ],
    )

    c_gold = tmp_path / "c_gold.csv"
    c_gold.write_text(
        "query_id,bucket,query,expected_document_version_id,expected_page_no,expected_bbox,label_status\n"
        "c1,pdf_page_lookup,pdf query,docv-c,1,\"[0,0,1,1]\",bound\n",
        encoding="utf-8",
    )
    c_report = tmp_path / "c_report.json"
    write_json(
        c_report,
        {
            "metrics": {"Hit@10": 1.0, "pdf_file_hit@10": 1.0, "required_index_version": "pdf-old"},
            "per_query": [
                {
                    "query_id": "c1",
                    "bucket": "pdf_page_lookup",
                    "query": "pdf query",
                    "hit_at_10": True,
                    "top_hit": {
                        "source_file_name": "doc.pdf",
                        "search_unit_id": "su-c",
                        "index_version": "pdf-old",
                        "citation_text": "doc.pdf > p.1",
                    },
                }
            ],
        },
    )
    c_consistency = tmp_path / "c_consistency.json"
    write_json(
        c_consistency,
        {
            "status": "PASS_WITH_WARNINGS",
            "c5_ready": True,
            "candidate_namespace_chunk_count": 1,
            "indexable_search_unit_count": 1,
            "policy_excluded_search_unit_count": 0,
        },
    )
    c_policy = tmp_path / "c_policy.json"
    write_json(
        c_policy,
        {
            "status": "NEEDS_POLICY_DECISION",
            "namespace": "rag-ingestion-v2-pdf-candidate-v1",
            "human_decision_required_count": 0,
            "gold_policy_change_candidate_count": 0,
            "diagnostic_only_exclude_candidate_count": 0,
            "c7_review_rows": [],
            "current_policy_positive_control_rows": [
                {
                    "query_id": "c1",
                    "primary_c7_classification": "keep_as_positive_current_policy",
                    "human_decision_required": False,
                }
            ],
        },
    )
    return {
        "artifact_root": tmp_path / "artifacts",
        "report_dir": tmp_path / "reports",
        "a_gold": a_gold,
        "a_report": a_report,
        "b_gold": b_gold,
        "b_report": b_report,
        "b_context": b_context,
        "b_context_report": b_context_report,
        "b_answer_report": b_answer_report,
        "b_answer_eval": b_answer_eval,
        "c_gold": c_gold,
        "c_report": c_report,
        "c_consistency": c_consistency,
        "c_policy": c_policy,
    }


def write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
