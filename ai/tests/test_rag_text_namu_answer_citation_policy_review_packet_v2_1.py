from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = (
    ROOT
    / "ai"
    / "scripts"
    / "rag_text_namu_answer_citation_policy_review_packet_v2_1.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "rag_text_namu_answer_citation_policy_review_packet_v2_1",
        SCRIPT_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


packet_v2_1 = load_module()


def test_policy_packet_separates_human_decision_rows_and_preview_counts(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    packet = packet_v2_1.build_policy_review_packet(
        generated_answer_jsonl=paths["generated_jsonl"],
        review_draft_jsonl=paths["draft_jsonl"],
        applied_diagnostic_json=paths["applied_json"],
        improvement_report_json=paths["improvement_json"],
        expected_counts=packet_v2_1.ExpectedCounts(
            total_rows=16,
            clean_pass=12,
            cleanup=3,
            unresolved=1,
            citation_supported=15,
        ),
    )

    assert packet["status"] == "POLICY_REVIEW_PACKET_READY"
    assert packet["diagnostic_metric_preview"]["strict_clean_answer_preview"] == {
        "numerator": 12,
        "denominator": 16,
    }
    assert packet["diagnostic_metric_preview"]["cleanup_inclusive_answer_preview"] == {
        "numerator": 15,
        "denominator": 16,
    }
    assert packet["diagnostic_metric_preview"]["citation_supported_preview"] == {
        "numerator": 15,
        "denominator": 16,
    }
    assert packet["diagnostic_metric_preview"]["unresolved_count"] == 1
    assert packet["row_groups"]["clean_pass_rows"]["row_count"] == 12
    assert packet["row_groups"]["cleanup_rows"]["query_ids"] == [
        "text_fixture_0013",
        "text_fixture_0014",
        "text_fixture_0015",
    ]
    assert packet["row_groups"]["unresolved_rows"]["query_ids"] == ["text_fixture_0016"]
    assert packet["row_groups"]["official_metric_blocked_rows"]["row_count"] == 16

    user_rows = packet["user_review"]["rows_requiring_human_decision"]
    cleanup_rows = [row for row in user_rows if row["review_bucket"] == "cleanup"]
    unresolved_rows = [row for row in user_rows if row["review_bucket"] == "unresolved"]
    audit_rows = [row for row in user_rows if row["review_bucket"] == "clean_pass_audit_sample"]
    assert len(cleanup_rows) == 3
    assert len(unresolved_rows) == 1
    assert len(audit_rows) == 12
    assert all(row["human_decision_needed"] is True for row in cleanup_rows + unresolved_rows)
    assert all(row["included_for_audit"] is True for row in audit_rows)


def test_metric_pass_candidate_cannot_open_official_metrics_or_promotion(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    packet = packet_v2_1.build_policy_review_packet(
        generated_answer_jsonl=paths["generated_jsonl"],
        review_draft_jsonl=paths["draft_jsonl"],
        applied_diagnostic_json=paths["applied_json"],
        improvement_report_json=paths["improvement_json"],
        expected_counts=packet_v2_1.ExpectedCounts(
            total_rows=16,
            clean_pass=12,
            cleanup=3,
            unresolved=1,
            citation_supported=15,
        ),
    )

    assert packet["diagnostic_metric_preview"]["metric_pass_candidate"] is True
    assert packet["diagnostic_metric_preview"]["official_metric_input_rows"] == 0
    assert (
        packet["diagnostic_metric_preview"]["official_metric_status"]
        == "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY"
    )
    assert packet["guardrails"]["official_metrics_opened"] is False
    assert packet["guardrails"]["official_metric_candidate_opened"] is False
    assert packet["guardrails"]["promotion_evidence_rows"] == 0
    assert packet["guardrails"]["promotion_evidence_mutation"] is False
    assert all(
        row["official_metric_input"] is False
        for row in packet["user_review"]["rows_requiring_human_decision"]
    )
    assert all(
        row["promotion_evidence"] is False
        for row in packet["user_review"]["rows_requiring_human_decision"]
    )


def test_unresolved_rows_are_excluded_from_pass_and_expected_answers_are_not_carried(
    tmp_path: Path,
):
    paths = write_fixture_bundle(tmp_path)

    packet = packet_v2_1.build_policy_review_packet(
        generated_answer_jsonl=paths["generated_jsonl"],
        review_draft_jsonl=paths["draft_jsonl"],
        applied_diagnostic_json=paths["applied_json"],
        improvement_report_json=paths["improvement_json"],
        expected_counts=packet_v2_1.ExpectedCounts(
            total_rows=16,
            clean_pass=12,
            cleanup=3,
            unresolved=1,
            citation_supported=15,
        ),
    )

    assert "text_fixture_0016" not in packet["row_groups"]["clean_pass_rows"]["query_ids"]
    assert "text_fixture_0016" not in packet["row_groups"]["cleanup_rows"]["query_ids"]
    forbidden_keys = {
        key
        for key, _value in walk_items(packet)
        if "expected_answer" in key or key in {"gold_registry_payload", "official_denominator_payload"}
    }
    assert forbidden_keys == set()
    assert packet["guardrails"]["gold_registry_mutation"] is False
    assert packet["guardrails"]["official_denominator_registry_mutation"] is False
    assert packet["guardrails"]["candidate_artifact_mutation"] is False


def test_duplicate_query_ids_fail_closed_before_packet_ready(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    rows = read_jsonl(paths["generated_jsonl"])
    rows[1]["query_id"] = rows[0]["query_id"]
    write_jsonl(paths["generated_jsonl"], rows)

    packet = packet_v2_1.build_policy_review_packet(
        generated_answer_jsonl=paths["generated_jsonl"],
        review_draft_jsonl=paths["draft_jsonl"],
        applied_diagnostic_json=paths["applied_json"],
        improvement_report_json=paths["improvement_json"],
        expected_counts=packet_v2_1.ExpectedCounts(
            total_rows=16,
            clean_pass=12,
            cleanup=3,
            unresolved=1,
            citation_supported=15,
        ),
    )

    assert packet["status"] == "FAIL_CLOSED"
    assert "generated-answer rows must have unique query_id values: text_fixture_0001" in packet[
        "validation"
    ]["errors"]


def test_main_writes_packet_json_and_markdown_without_source_mutation(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    before = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    output_json = tmp_path / "packet.json"
    output_md = tmp_path / "packet.md"

    result = packet_v2_1.main(
        [
            "--generated-answer-jsonl",
            str(paths["generated_jsonl"]),
            "--review-draft-jsonl",
            str(paths["draft_jsonl"]),
            "--applied-diagnostic-json",
            str(paths["applied_json"]),
            "--improvement-report-json",
            str(paths["improvement_json"]),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
            "--expected-total-rows",
            "16",
            "--expected-clean-pass",
            "12",
            "--expected-cleanup",
            "3",
            "--expected-unresolved",
            "1",
            "--expected-citation-supported",
            "15",
        ]
    )

    assert result == 0
    assert output_json.exists()
    assert output_md.exists()
    assert json.loads(output_json.read_text(encoding="utf-8"))["status"] == "POLICY_REVIEW_PACKET_READY"
    markdown = output_md.read_text(encoding="utf-8")
    assert "Diagnostic Metric Preview" in markdown
    assert "model-assisted output is not human-approved gold" in markdown
    assert {name: path.read_text(encoding="utf-8") for name, path in paths.items()} == before


def write_fixture_bundle(tmp_path: Path) -> dict[str, Path]:
    generated_jsonl = tmp_path / "generated.jsonl"
    draft_jsonl = tmp_path / "draft.jsonl"
    applied_json = tmp_path / "applied.json"
    improvement_json = tmp_path / "improvement.json"

    query_ids = [f"text_fixture_{index:04d}" for index in range(1, 17)]
    clean_ids = query_ids[:12]
    cleanup_ids = query_ids[12:15]
    unresolved_ids = query_ids[15:]

    generated_rows = [
        generated_row(
            query_id,
            model_assisted=index % 2 == 0,
            deterministic_claim_repair=query_id == "text_fixture_0004",
        )
        for index, query_id in enumerate(query_ids, start=1)
    ]
    draft_rows = [
        draft_row(query_id, "KEEP_DIAGNOSTIC_CANDIDATE", "fully_supported")
        for query_id in clean_ids
    ]
    draft_rows.extend(
        draft_row(query_id, "KEEP_WITH_CLEANUP", "fully_supported")
        for query_id in cleanup_ids
    )
    draft_rows.extend(
        draft_row(
            query_id,
            "ANSWER_REWRITE_REQUIRED",
            "citation_contains_correct_answer_but_generated_answer_incomplete",
        )
        for query_id in unresolved_ids
    )

    write_jsonl(generated_jsonl, generated_rows)
    write_jsonl(draft_jsonl, draft_rows)
    write_json(
        applied_json,
        {
            "schema_version": "rag_text_namu_answer_citation_review_applied_diagnostic_v2_1",
            "status": "APPLIED_DIAGNOSTIC_ONLY",
            "row_count": 16,
            "generated_answer_row_count": 16,
            "draft_row_count": 16,
            "review_action_counts": {
                "KEEP_DIAGNOSTIC_CANDIDATE": 12,
                "KEEP_WITH_CLEANUP": 3,
                "ANSWER_REWRITE_REQUIRED": 1,
            },
            "assistant_citation_support_judgment_counts": {
                "fully_supported": 15,
                "citation_contains_correct_answer_but_generated_answer_incomplete": 1,
            },
            "diagnostic_metric_preview": {
                "answer_pass_preview_count": 12,
                "cleanup_pass_preview_count": 3,
                "rewrite_required_count": 1,
                "unresolved_diagnostic_count": 1,
                "citation_fully_supported_generated_answer_count": 15,
                "official_metric_input_rows": 0,
                "official_metric_status": "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY",
                "diagnostic_preview_not_official_metric": True,
            },
            "applied_rows": draft_rows,
            "guardrails": {
                "official_metrics_opened": False,
                "official_metric_input_rows": 0,
                "promotion_evidence_rows": 0,
            },
            "validation": {"ok": True, "errors": []},
        },
    )
    write_json(
        improvement_json,
        {
            "schema_version": "rag_text_namu_local_llm_rewrite_v2_1",
            "status": "DIAGNOSTIC_LOCAL_LLM_REWRITE_V2_1_COMPLETE",
            "v2_vs_v2_1": {
                "diagnostic_quality_target_status": {
                    "metric_preview_candidate": True,
                    "metric_pass_candidate": True,
                    "official_metric": False,
                },
                "official_metric_input_rows": 0,
                "official_metric_status": "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY",
                "rows_improved": ["text_fixture_0002", "text_fixture_0004"],
                "rows_regressed": [],
                "verifier_failures": unresolved_ids,
            },
            "guardrails": {
                "official_metrics_opened": False,
                "official_metric_input_rows": 0,
                "promotion_evidence_rows": 0,
            },
        },
    )
    return {
        "generated_jsonl": generated_jsonl,
        "draft_jsonl": draft_jsonl,
        "applied_json": applied_json,
        "improvement_json": improvement_json,
    }


def generated_row(
    query_id: str,
    *,
    model_assisted: bool,
    deterministic_claim_repair: bool,
) -> dict[str, Any]:
    return {
        "query_id": query_id,
        "safe_query_text": f"safe query {query_id}",
        "rewritten_answer": f"source-bound answer {query_id}",
        "original_generated_answer": f"original answer {query_id}",
        "answer_claims": [f"source-bound answer {query_id}"],
        "evidence_spans": [f"source-bound evidence {query_id}"],
        "cited_chunk_ids": [f"chunk-{query_id}"],
        "retrieved_chunk_ids": [f"chunk-{query_id}"],
        "rewrite_status": "KEEP_DIAGNOSTIC_CANDIDATE",
        "verifier_passed": True,
        "model_assisted": model_assisted,
        "local_llm_used": model_assisted,
        "deterministic_claim_repair": deterministic_claim_repair,
        "not_human_approved": True,
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
    }


def draft_row(query_id: str, action: str, citation_judgment: str) -> dict[str, Any]:
    return {
        "query_id": query_id,
        "query": f"safe query {query_id}",
        "generated_short_answer": f"short answer {query_id}",
        "suggested_extractive_answer_not_gold": f"extractive answer {query_id}",
        "evidence_spans": [f"source-bound evidence {query_id}"],
        "assistant_answer_judgment": (
            "rewrite_still_required"
            if action == "ANSWER_REWRITE_REQUIRED"
            else "source_supported_rewrite"
        ),
        "assistant_citation_support_judgment": citation_judgment,
        "assistant_review_action": action,
        "assistant_review_notes": "fixture diagnostic notes",
        "cited_chunk_ids": [f"chunk-{query_id}"],
        "retrieved_chunk_ids": [f"chunk-{query_id}"],
        "failure_causes": [] if action != "ANSWER_REWRITE_REQUIRED" else ["missing_answer_claims"],
        "human_approval_required_for_official_metric": True,
        "model_assisted": True,
        "not_human_approved": True,
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def walk_items(value: Any, prefix: str = ""):
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path, child
            yield from walk_items(child, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_items(child, f"{prefix}[{index}]")
