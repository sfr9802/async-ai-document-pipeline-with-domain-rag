from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_text_namu_answer_citation_review_apply_diagnostic.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "rag_text_namu_answer_citation_review_apply_diagnostic", SCRIPT_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


apply_diag = load_module()


def test_apply_diagnostic_review_preserves_preview_buckets_and_official_closed(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    report = apply_diag.build_applied_report(**paths)

    assert report["status"] == "APPLIED_DIAGNOSTIC_ONLY"
    assert report["row_count"] == 3
    assert report["review_action_counts"] == {
        "ANSWER_REWRITE_REQUIRED": 1,
        "KEEP_DIAGNOSTIC_CANDIDATE": 1,
        "KEEP_WITH_CLEANUP": 1,
    }
    assert report["diagnostic_metric_preview"]["answer_pass_preview_count"] == 1
    assert report["diagnostic_metric_preview"]["cleanup_pass_preview_count"] == 1
    assert report["diagnostic_metric_preview"]["rewrite_required_count"] == 1
    assert report["diagnostic_metric_preview"]["citation_fully_supported_generated_answer_count"] == 2
    assert (
        report["diagnostic_metric_preview"][
            "citation_contains_correct_answer_but_generated_answer_incomplete_count"
        ]
        == 1
    )
    assert report["diagnostic_metric_preview"]["official_metric_input_rows"] == 0
    assert report["diagnostic_metric_preview"]["official_metric_status"] == "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY"
    assert report["guardrails"]["official_metrics_opened"] is False
    assert report["guardrails"]["promotion_evidence_rows"] == 0
    assert report["validation"]["ok"] is True
    assert all(row["diagnostic_only"] is True for row in report["applied_rows"])
    assert all(row["official_metric_input"] is False for row in report["applied_rows"])
    assert all(row["promotion_evidence"] is False for row in report["applied_rows"])

    by_id = {row["query_id"]: row for row in report["applied_rows"]}
    assert by_id["text_001"]["answer_pass_preview"] is True
    assert by_id["text_002"]["cleanup_pass_preview"] is True
    assert by_id["text_003"]["rewrite_required"] is True
    assert by_id["text_003"]["answer_pass_preview"] is False
    assert by_id["text_003"]["official_citation_success"] is False


def test_model_assisted_diagnostic_draft_cannot_open_official_metrics(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    rows = read_jsonl(paths["draft_jsonl"])
    rows[0]["official_metric_input"] = True
    write_jsonl(paths["draft_jsonl"], rows)

    report = apply_diag.build_applied_report(**paths)

    assert report["status"] == "FAIL_CLOSED"
    assert "draft rows must keep official_metric_input=false" in report["validation"]["errors"]
    assert report["diagnostic_metric_preview"]["official_metric_input_rows"] == 0
    assert report["diagnostic_metric_preview"]["official_metric_status"] == "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY"


def test_model_assisted_diagnostic_draft_cannot_be_promotion_evidence(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    rows = read_jsonl(paths["draft_jsonl"])
    rows[0]["promotion_evidence"] = True
    write_jsonl(paths["draft_jsonl"], rows)

    report = apply_diag.build_applied_report(**paths)

    assert report["status"] == "FAIL_CLOSED"
    assert "draft rows must keep promotion_evidence=false" in report["validation"]["errors"]
    assert report["guardrails"]["promotion_evidence_rows"] == 1


def test_missing_or_extra_query_id_fails_closed(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    rows = read_jsonl(paths["draft_jsonl"])
    rows = rows[:-1] + [draft_row("text_extra", "KEEP_DIAGNOSTIC_CANDIDATE", "correct", "fully_supported")]
    write_jsonl(paths["draft_jsonl"], rows)

    report = apply_diag.build_applied_report(**paths)

    assert report["status"] == "FAIL_CLOSED"
    assert "draft missing generated query ids: text_003" in report["validation"]["errors"]
    assert "draft has extra query ids: text_extra" in report["validation"]["errors"]


def test_blank_query_id_rows_fail_closed(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    draft_rows = read_jsonl(paths["draft_jsonl"])
    generated_rows = read_jsonl(paths["generated_answer_jsonl"])
    draft_rows.append(draft_row("", "KEEP_DIAGNOSTIC_CANDIDATE", "correct", "fully_supported"))
    generated_rows.append(generated_row(""))
    write_jsonl(paths["draft_jsonl"], draft_rows)
    write_jsonl(paths["generated_answer_jsonl"], generated_rows)

    report = apply_diag.build_applied_report(**paths)

    assert report["status"] == "FAIL_CLOSED"
    assert "draft has blank query_id rows: 4" in report["validation"]["errors"]
    assert "generated-answer input has blank query_id rows: 4" in report["validation"]["errors"]
    assert "validated row count must match draft and generated-answer row counts" in report["validation"]["errors"]


def test_citation_incomplete_label_is_not_official_citation_success(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    report = apply_diag.build_applied_report(**paths)

    rewrite_row = next(row for row in report["applied_rows"] if row["query_id"] == "text_003")
    assert rewrite_row["assistant_citation_support_judgment"] == (
        "citation_contains_correct_answer_but_generated_answer_incomplete"
    )
    assert rewrite_row["diagnostic_citation_success_preview"] is False
    assert rewrite_row["official_citation_success"] is False
    assert report["diagnostic_metric_preview"]["official_citation_success_count"] == 0


def test_main_writes_applied_json_and_markdown_without_source_mutation(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    before_draft = paths["draft_jsonl"].read_text(encoding="utf-8")
    before_generated = paths["generated_answer_jsonl"].read_text(encoding="utf-8")
    output_json = tmp_path / "applied.json"
    output_md = tmp_path / "applied.md"

    result = apply_diag.main(
        [
            "--draft-jsonl",
            str(paths["draft_jsonl"]),
            "--draft-summary",
            str(paths["draft_summary"]),
            "--generated-answer-jsonl",
            str(paths["generated_answer_jsonl"]),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
    )

    assert result == 0
    assert output_json.exists()
    assert output_md.exists()
    assert paths["draft_jsonl"].read_text(encoding="utf-8") == before_draft
    assert paths["generated_answer_jsonl"].read_text(encoding="utf-8") == before_generated
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["status"] == "APPLIED_DIAGNOSTIC_ONLY"


def write_fixture_bundle(tmp_path: Path) -> dict[str, Path]:
    draft_jsonl = tmp_path / "draft.jsonl"
    draft_summary = tmp_path / "draft_summary.json"
    generated_answer_jsonl = tmp_path / "generated.jsonl"
    generated_rows = [generated_row("text_001"), generated_row("text_002"), generated_row("text_003")]
    draft_rows = [
        draft_row("text_001", "KEEP_DIAGNOSTIC_CANDIDATE", "correct", "fully_supported"),
        draft_row("text_002", "KEEP_WITH_CLEANUP", "correct_with_excess_context", "fully_supported"),
        draft_row(
            "text_003",
            "ANSWER_REWRITE_REQUIRED",
            "partially_correct_missing_requested_fact",
            "citation_contains_correct_answer_but_generated_answer_incomplete",
        ),
    ]
    write_jsonl(generated_answer_jsonl, generated_rows)
    write_jsonl(draft_jsonl, draft_rows)
    write_json(
        draft_summary,
        {
            "schema_version": "rag_text_namu_answer_citation_review_draft_gpt_v1",
            "scope": "diagnostic_model_assisted_answer_citation_review_draft_only",
            "not_official_gold": True,
            "not_promotion_evidence": True,
            "official_metric_input_rows": 0,
            "input_sha256": apply_diag.sha256_file(generated_answer_jsonl),
            "counts": {
                "total_rows": 3,
                "review_action": {
                    "KEEP_DIAGNOSTIC_CANDIDATE": 1,
                    "KEEP_WITH_CLEANUP": 1,
                    "ANSWER_REWRITE_REQUIRED": 1,
                },
                "official_metric_input_true": 0,
                "diagnostic_only_true": 3,
                "promotion_evidence_true": 0,
            },
        },
    )
    return {
        "draft_jsonl": draft_jsonl,
        "draft_summary": draft_summary,
        "generated_answer_jsonl": generated_answer_jsonl,
    }


def generated_row(query_id: str) -> dict:
    return {
        "query_id": query_id,
        "safe_query_text": f"safe query {query_id}",
        "generated_answer": f"generated answer {query_id}",
        "cited_chunk_ids": [f"chunk-{query_id}"],
        "retrieved_chunk_ids": [f"chunk-{query_id}"],
        "citation_items": [{"chunk_id": f"chunk-{query_id}", "citation_text": "citation"}],
        "generation_provenance": {"generator_name": "extractive-v1"},
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
    }


def draft_row(
    query_id: str,
    action: str,
    answer_judgment: str,
    citation_judgment: str,
) -> dict:
    return {
        "query_id": query_id,
        "query": f"safe query {query_id}",
        "generated_short_answer": f"short answer {query_id}",
        "assistant_answer_judgment": answer_judgment,
        "assistant_citation_support_judgment": citation_judgment,
        "assistant_review_action": action,
        "suggested_extractive_answer_not_gold": "",
        "assistant_review_notes": "notes",
        "cited_chunk_ids": f"chunk-{query_id}",
        "retrieved_chunk_ids": f"chunk-{query_id}",
        "citation_text_excerpt": "citation",
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "human_approval_required_for_official_metric": True,
        "model_reviewer": "fixture",
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows
