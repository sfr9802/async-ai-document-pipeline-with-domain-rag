from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_pdf_answer_citation_policy_review_packet_v1.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_pdf_answer_citation_policy_review_packet_v1_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pdf_policy_packet_ready_when_all_rows_are_supported_and_cited(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture(tmp_path)

    packet = module.run_packet(
        diagnostic_report=paths["diagnostic_report"],
        review_input_jsonl=paths["review_input"],
        output_report=tmp_path / "packet.json",
        output_md=tmp_path / "packet.md",
    )

    assert packet["status"] == "DIAGNOSTIC_POLICY_PACKET_READY"
    assert packet["input_rows"] == 2
    assert packet["strict_ready_rows"] == 2
    assert packet["generated_answer_rows"] == 2
    assert packet["answer_support_pass_count"] == 2
    assert packet["citation_locator_valid_count"] == 2
    assert packet["clean_pass_rows"] == 2
    assert packet["cleanup_rows"] == 0
    assert packet["unresolved_rows"] == 0
    assert packet["lane_policy_blocked_rows"] == 0
    assert packet["official_metric_input_rows"] == 0
    assert packet["official_metric"] is False
    assert packet["promotion_evidence"] is False
    assert packet["denominator_policy"] == "closed"
    assert packet["answer_generation_scope"] == "diagnostic_only"
    assert packet["pdf_answer_generation_denominator_opened"] is False
    assert packet["content_file_identity_lane_merge"] is False
    assert packet["filename_only_identity_accepted"] is False


def test_pdf_policy_packet_ready_with_cleanup_for_unsupported_answer_without_guardrail_failure(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture(tmp_path)
    rows = read_jsonl(paths["review_input"])
    rows[0]["answer_claims_supported"] = False
    rows[0]["answer_supported_by_matched_text_or_nearby_paragraph"] = False
    rows[0]["bucket"] = "unsupported_answer"
    write_jsonl(paths["review_input"], rows)
    diagnostic = json.loads(paths["diagnostic_report"].read_text(encoding="utf-8"))
    diagnostic["answer_support_pass_count"] = 1
    diagnostic["clean_pass_rows"] = 1
    diagnostic["cleanup_rows"] = 1
    diagnostic["unsupported_answer_rows"] = 1
    diagnostic["bucket_counts"]["clean_pass"] = 1
    diagnostic["bucket_counts"]["unsupported_answer"] = 1
    paths["diagnostic_report"].write_text(json.dumps(diagnostic, ensure_ascii=False), encoding="utf-8")

    packet = module.run_packet(
        diagnostic_report=paths["diagnostic_report"],
        review_input_jsonl=paths["review_input"],
        output_report=tmp_path / "packet.json",
        output_md=tmp_path / "packet.md",
    )

    assert packet["status"] == "DIAGNOSTIC_POLICY_PACKET_READY_WITH_CLEANUP"
    assert packet["clean_pass_rows"] == 1
    assert packet["cleanup_rows"] == 1
    assert packet["unresolved_rows"] == 0
    assert packet["lane_policy_blocked_rows"] == 0
    assert packet["official_metric_input_rows"] == 0


def test_pdf_policy_packet_blocks_lane_or_evidence_guardrail_failures(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture(tmp_path)
    rows = read_jsonl(paths["review_input"])
    rows[0]["no_file_identity_lane_used_as_content_evidence"] = False
    rows[0]["content_evidence_lane"] = "pdf_file_identity"
    rows[0]["bucket"] = "lane_policy_blocked"
    rows[1]["no_diagnostic_fallback_row_used"] = False
    write_jsonl(paths["review_input"], rows)

    packet = module.run_packet(
        diagnostic_report=paths["diagnostic_report"],
        review_input_jsonl=paths["review_input"],
        output_report=tmp_path / "packet.json",
        output_md=tmp_path / "packet.md",
    )

    assert packet["status"] == "DIAGNOSTIC_POLICY_PACKET_BLOCKED_BY_LANE_OR_EVIDENCE_GUARD"
    assert packet["lane_policy_blocked_rows"] == 1
    assert packet["diagnostic_fallback_rows_used"] == 1
    assert packet["content_file_identity_lane_merge"] is False
    assert packet["official_metric_input_rows"] == 0


def test_pdf_policy_packet_fails_if_official_metric_input_opens(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture(tmp_path)
    rows = read_jsonl(paths["review_input"])
    rows[0]["official_metric_input"] = True
    write_jsonl(paths["review_input"], rows)

    packet = module.run_packet(
        diagnostic_report=paths["diagnostic_report"],
        review_input_jsonl=paths["review_input"],
        output_report=tmp_path / "packet.json",
        output_md=tmp_path / "packet.md",
    )

    assert packet["status"] == "FAILED_GUARDRAIL"
    assert packet["official_metric_input_rows"] == 1
    assert "official_metric_input_rows must remain 0" in packet["validation"]["errors"]


def test_pdf_policy_packet_fails_if_review_input_missing_or_empty(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture(tmp_path)
    paths["review_input"].unlink()

    missing_packet = module.run_packet(
        diagnostic_report=paths["diagnostic_report"],
        review_input_jsonl=paths["review_input"],
        output_report=tmp_path / "missing_packet.json",
        output_md=tmp_path / "missing_packet.md",
    )

    assert missing_packet["status"] == "FAILED_GUARDRAIL"
    assert "pdf answer/citation review input JSONL is missing" in missing_packet["validation"]["errors"]
    assert "pdf answer/citation review input JSONL must contain row-level audit data" in missing_packet["validation"]["errors"]

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    paths = write_fixture(empty_dir)
    paths["review_input"].write_text("", encoding="utf-8")
    empty_packet = module.run_packet(
        diagnostic_report=paths["diagnostic_report"],
        review_input_jsonl=paths["review_input"],
        output_report=tmp_path / "empty_packet.json",
        output_md=tmp_path / "empty_packet.md",
    )

    assert empty_packet["status"] == "FAILED_GUARDRAIL"
    assert "pdf answer/citation review input JSONL must contain row-level audit data" in empty_packet["validation"]["errors"]


def test_pdf_policy_packet_fails_if_review_input_count_mismatches_diagnostic(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture(tmp_path)
    rows = read_jsonl(paths["review_input"])
    write_jsonl(paths["review_input"], rows[:1])

    packet = module.run_packet(
        diagnostic_report=paths["diagnostic_report"],
        review_input_jsonl=paths["review_input"],
        output_report=tmp_path / "packet.json",
        output_md=tmp_path / "packet.md",
    )

    assert packet["status"] == "FAILED_GUARDRAIL"
    assert packet["expected_review_input_rows"] == 2
    assert "pdf answer/citation review input row count must match diagnostic expected rows: 1 != 2" in packet["validation"]["errors"]


def test_pdf_policy_packet_fails_if_diagnostic_report_is_not_pass(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture(tmp_path)
    diagnostic = json.loads(paths["diagnostic_report"].read_text(encoding="utf-8"))
    diagnostic["status"] = "FAILED_GUARDRAIL"
    diagnostic["validation"] = {"ok": False, "errors": ["synthetic stale diagnostic failure"]}
    paths["diagnostic_report"].write_text(json.dumps(diagnostic, ensure_ascii=False), encoding="utf-8")

    packet = module.run_packet(
        diagnostic_report=paths["diagnostic_report"],
        review_input_jsonl=paths["review_input"],
        output_report=tmp_path / "packet.json",
        output_md=tmp_path / "packet.md",
    )

    assert packet["status"] == "FAILED_GUARDRAIL"
    assert "pdf diagnostic report status must be PASS" in packet["validation"]["errors"]
    assert "pdf diagnostic report validation.ok must be true" in packet["validation"]["errors"]


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def write_fixture(tmp_path: Path) -> dict[str, Path]:
    diagnostic_report = tmp_path / "pdf_answer_report.json"
    review_input = tmp_path / "pdf_review_input.jsonl"
    rows = [review_row("pdf_001"), review_row("pdf_002")]
    write_jsonl(review_input, rows)
    diagnostic_report.write_text(
        json.dumps(
            {
                "schema_version": "pdf_answer_citation_diagnostic_report_v1",
                "generated_at": "2026-05-15T00:00:00+00:00",
                "status": "PASS",
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "diagnostic_answer_generation_run": True,
                "answer_generation_scope": "diagnostic_only",
                "pdf_answer_generation_denominator_opened": False,
                "input_rows": 2,
                "strict_ready_rows": 2,
                "generated_answer_rows": 2,
                "answer_support_pass_count": 2,
                "citation_locator_valid_count": 2,
                "clean_pass_rows": 2,
                "cleanup_rows": 0,
                "unresolved_rows": 0,
                "lane_policy_blocked_rows": 0,
                "official_metric_input_rows": 0,
                "bucket_counts": {
                    "clean_pass": 2,
                    "cleanup_required": 0,
                    "answer_rewrite_required": 0,
                    "citation_locator_incomplete": 0,
                    "unsupported_answer": 0,
                    "lane_policy_blocked": 0,
                    "unresolved_diagnostic": 0,
                },
                "guardrails": {
                    "official_metric_input_rows_remain_zero": True,
                    "official_denominator_registry_opened": False,
                    "official_denominator_registry_mutation": False,
                    "promotion_evidence_created": False,
                },
                "lane_guard": {
                    "content_file_identity_lane_merge": False,
                    "file_identity_rows_used_as_content_evidence": False,
                    "filename_only_identity_accepted": False,
                    "policy_excluded_rows_used": False,
                    "diagnostic_fallback_rows_used": False,
                },
                "validation": {"ok": True, "errors": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"diagnostic_report": diagnostic_report, "review_input": review_input}


def review_row(query_id: str) -> dict[str, object]:
    return {
        "query_id": query_id,
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "content_evidence_lane": "pdf_content_evidence",
        "file_identity_lane": {
            "lane": "pdf_file_identity",
            "merged_with_content_evidence": False,
            "filename_only_identity_accepted": False,
        },
        "answer_claims_supported": True,
        "answer_supported_by_matched_text_or_nearby_paragraph": True,
        "citation_locator_valid": True,
        "citation_locator_has_page_bbox_region_search_unit": True,
        "citation_text_matches_source_bound_evidence": True,
        "no_file_identity_lane_used_as_content_evidence": True,
        "no_filename_only_identity_acceptance": True,
        "no_policy_excluded_row_used": True,
        "no_diagnostic_fallback_row_used": True,
        "bucket": "clean_pass",
    }
