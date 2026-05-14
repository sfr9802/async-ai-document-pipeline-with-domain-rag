from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_xlsx_answer_citation_policy_review_packet_v1.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_xlsx_answer_citation_policy_review_packet_v1_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_policy_packet_fail_closes_clean_rows_and_preserves_annotation_only_allowlist(tmp_path: Path):
    module = load_module()
    paths = write_fixture(tmp_path)

    packet = module.run_packet(
        answer_report=paths["answer_report"],
        leakage_reprobe=paths["leakage_reprobe"],
        review_input_jsonl=paths["review_input"],
        output_report=tmp_path / "packet.json",
        output_md=tmp_path / "packet.md",
    )

    assert packet["status"] == "DIAGNOSTIC_POLICY_PACKET_BLOCKED_BY_LEAKAGE"
    assert packet["input_rows"] == 2
    assert packet["strict_silver_rows"] == 2
    assert packet["pending_excluded_rows"] == 2
    assert packet["normalized_excluded_rows"] == 1
    assert packet["hidden_negative_rows"] == 1
    assert packet["answer_support_pass_count"] == 2
    assert packet["citation_locator_valid_count"] == 2
    assert packet["leakage_raw_status"] == "FAIL"
    assert packet["leakage_surface_counts"] == {
        "answer": 1,
        "citation": 1,
        "debug_public": 1,
        "official_denominator": 1,
        "public": 1,
    }
    assert packet["annotation_only_allowlist_used"] is True
    assert packet["official_metric_input_rows"] == 0
    assert packet["promotion_evidence"] is False
    assert packet["metric_preview_status"] == "FAIL_CLOSED_BY_LEAKAGE"
    assert packet["denominator_policy"] == "closed"
    assert packet["diagnostic_metric_preview"]["pre_leakage_support_pass_rows"] == 2
    assert packet["diagnostic_metric_preview"]["answer_citation_clean_pass_rows"] == 2
    assert packet["diagnostic_metric_preview"]["clean_pass_rows"] == 0
    assert packet["diagnostic_metric_preview"]["cleanup_rows"] == 2
    assert packet["diagnostic_metric_preview"]["blocked_by_leakage_rows"] == 2
    assert packet["terminology"]["pre_leakage_support_pass_rows"] == (
        "rows where answer support and citation locator checks passed before leakage fail-closed gating"
    )
    assert packet["terminology"]["clean_pass_rows"] == (
        "final diagnostic clean rows after raw leakage gating; forced to 0 while leakage_raw_status is FAIL"
    )

    by_id = {row["query_id"]: row for row in packet["leakage_by_row"]}
    assert "normalized_excluded_row_token" in by_id["excluded_001"]["classifications"]
    assert "answer_text_leaks_excluded_context" in by_id["excluded_001"]["classifications"]
    assert "citation_locator_leaks_excluded_context" in by_id["excluded_001"]["classifications"]
    assert "policy_excluded_public_surface" in by_id["excluded_001"]["classifications"]
    assert "ambiguous_strict_evidence_token_annotation_only" in by_id["excluded_001"]["classifications"]
    assert "hidden_negative_token" in by_id["hidden_001"]["classifications"]
    assert "official_denominator_surface_leakage" in by_id["hidden_001"]["classifications"]


def test_policy_packet_fails_when_review_input_marks_official_metric_input(tmp_path: Path):
    module = load_module()
    paths = write_fixture(tmp_path)
    paths["review_input"].write_text(
        json.dumps({"query_id": "strict_001", "official_metric_input": True}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    packet = module.run_packet(
        answer_report=paths["answer_report"],
        leakage_reprobe=paths["leakage_reprobe"],
        review_input_jsonl=paths["review_input"],
        output_report=tmp_path / "packet.json",
        output_md=tmp_path / "packet.md",
    )

    assert packet["status"] == "FAILED_GUARDRAIL"
    assert packet["official_metric_input_rows"] == 1
    assert "official_metric_input_rows must remain 0" in packet["validation"]["errors"]


def test_policy_packet_fails_when_source_report_opens_denominator_or_gold_guardrails(tmp_path: Path):
    module = load_module()
    paths = write_fixture(tmp_path)
    answer = json.loads(paths["answer_report"].read_text(encoding="utf-8"))
    answer["guardrails"] = {
        "official_denominator_registry_opened": True,
        "official_denominator_registry_mutation": True,
        "gold_registry_mutation": True,
    }
    paths["answer_report"].write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")

    packet = module.run_packet(
        answer_report=paths["answer_report"],
        leakage_reprobe=paths["leakage_reprobe"],
        review_input_jsonl=paths["review_input"],
        output_report=tmp_path / "packet.json",
        output_md=tmp_path / "packet.md",
    )

    assert packet["status"] == "FAILED_GUARDRAIL"
    assert "xlsx source guardrail violation: official_denominator_registry_opened=true" in packet[
        "validation"
    ]["errors"]
    assert "xlsx source guardrail violation: official_denominator_registry_mutation=true" in packet[
        "validation"
    ]["errors"]
    assert "xlsx source guardrail violation: gold_registry_mutation=true" in packet["validation"]["errors"]


def test_policy_packet_uses_pass_wording_when_raw_leakage_is_clean(tmp_path: Path):
    module = load_module()
    paths = write_fixture(tmp_path)
    answer = json.loads(paths["answer_report"].read_text(encoding="utf-8"))
    answer["status"] = "PASS"
    answer["diagnostic_metric_preview"]["leakage_count"] = 0
    answer["diagnostic_metric_preview"]["leakage_status"] = "PASS"
    answer["leakage_reprobe"] = {"status": "PASS", "surface_leakage_count": 0}
    paths["answer_report"].write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
    leakage = json.loads(paths["leakage_reprobe"].read_text(encoding="utf-8"))
    leakage["status"] = "PASS"
    leakage["counts"]["surface_leakage_count"] = 0
    leakage["allowlist_policy"]["allowlisted_surface_violation_count"] = 0
    leakage["surface_coverage"] = {
        "answer": {"leakage_count": 0, "status": "PASS"},
        "citation": {"leakage_count": 0, "status": "PASS"},
        "debug_public": {"leakage_count": 0, "status": "PASS"},
        "official_denominator": {"leakage_count": 0, "status": "PASS"},
        "public": {"leakage_count": 0, "status": "PASS"},
    }
    leakage["query_results"] = []
    paths["leakage_reprobe"].write_text(json.dumps(leakage, ensure_ascii=False), encoding="utf-8")

    packet = module.run_packet(
        answer_report=paths["answer_report"],
        leakage_reprobe=paths["leakage_reprobe"],
        review_input_jsonl=paths["review_input"],
        output_report=tmp_path / "packet.json",
        output_md=tmp_path / "packet.md",
    )

    joined_actions = "\n".join(packet["next_safe_actions"])
    rendered_md = (tmp_path / "packet.md").read_text(encoding="utf-8")
    assert packet["status"] == "DIAGNOSTIC_POLICY_PACKET_READY"
    assert packet["leakage_raw_status"] == "PASS"
    assert "Keep raw leakage PASS only while public answer/citation/debug/public/official surfaces remain free" in joined_actions
    assert "Keep raw leakage status as FAIL" not in joined_actions
    assert "Keep raw leakage status as FAIL" not in rendered_md


def write_fixture(tmp_path: Path) -> dict[str, Path]:
    answer_report = tmp_path / "answer_report.json"
    leakage_reprobe = tmp_path / "leakage_reprobe.json"
    review_input = tmp_path / "review_input.jsonl"

    answer_report.write_text(
        json.dumps(
            {
                "status": "FAIL",
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "official_metric_input_rows": 0,
                "counts": {
                    "input_strict_silver_rows": 2,
                    "generated_review_input_rows": 2,
                    "answer_claim_supported_rows": 2,
                    "citation_locator_resolved_rows": 2,
                },
                "excluded_query_ids": {
                    "pending_evidence": ["pending_a", "pending_b"],
                    "normalized_excluded": ["excluded_001"],
                    "normalized_hidden_negative": ["hidden_001"],
                },
                "diagnostic_metric_preview": {
                    "generated_answer_rows": 2,
                    "answer_citation_clean_pass_rows": 2,
                    "clean_pass_rows": 0,
                    "cleanup_rows": 2,
                    "rewrite_unresolved_rows": 0,
                    "citation_fully_supported_rows": 2,
                    "citation_locator_valid_rows": 2,
                    "leakage_count": 5,
                    "leakage_status": "FAIL",
                    "official_metric_input_rows": 0,
                },
                "leakage_reprobe": {"status": "FAIL", "surface_leakage_count": 5},
                "guardrails": {
                    "official_metric_input_rows_remain_zero": True,
                    "promotion_evidence_remains_false": True,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    leakage_reprobe.write_text(
        json.dumps(
            {
                "status": "FAIL",
                "counts": {
                    "surface_leakage_count": 5,
                    "normalized_excluded_row_count": 1,
                    "normalized_hidden_negative_row_count": 1,
                    "strict_evidence_shared_token_allowlist_count": 5,
                },
                "allowlist_policy": {
                    "strict_evidence_shared_token_allowlist": True,
                    "status_effect": "annotation_only",
                    "allowlisted_surface_violation_count": 5,
                },
                "surface_coverage": {
                    "answer": {"leakage_count": 1, "status": "FAIL"},
                    "citation": {"leakage_count": 1, "status": "FAIL"},
                    "debug_public": {"leakage_count": 1, "status": "FAIL"},
                    "official_denominator": {"leakage_count": 1, "status": "FAIL"},
                    "public": {"leakage_count": 1, "status": "FAIL"},
                },
                "query_results": [
                    {
                        "query_id": "excluded_001",
                        "row_source": "normalized_excluded",
                        "hidden_negative": False,
                        "surface_violation_count": 4,
                        "surface_violations": [
                            {"surface": "answer", "token_sha256": ["shared"]},
                            {"surface": "citation", "token_sha256": ["shared"]},
                            {"surface": "debug_public", "token_sha256": ["shared"]},
                            {"surface": "public", "token_sha256": ["shared"]},
                        ],
                    },
                    {
                        "query_id": "hidden_001",
                        "row_source": "normalized_excluded",
                        "hidden_negative": True,
                        "surface_violation_count": 1,
                        "surface_violations": [
                            {"surface": "official_denominator", "token_sha256": ["hidden"]},
                        ],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    review_input.write_text(
        "\n".join(
            [
                json.dumps({"query_id": "strict_001", "official_metric_input": False}, ensure_ascii=False),
                json.dumps({"query_id": "strict_002", "official_metric_input": False}, ensure_ascii=False),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"answer_report": answer_report, "leakage_reprobe": leakage_reprobe, "review_input": review_input}
