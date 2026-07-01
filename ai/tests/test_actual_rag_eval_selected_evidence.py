from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai.eval import actual_rag_eval
from ai.eval.actual_rag_eval import (
    DatasetSchemaError,
    apply_evidence_gate_to_outputs,
    apply_selected_evidence_composer_to_outputs,
    load_eval_dataset,
    run_eval_from_paths,
    select_composer_evidence,
    validate_evidence_package_for_gate,
)
from ai.tests.actual_rag_eval_helpers import output_file_names, write_jsonl


def test_public_report_sanitizer_strips_raw_tool_payload_keys() -> None:
    report = actual_rag_eval._sanitize_public_report_value(
        {
            "safe": "kept",
            "raw_tool_payload": {"secret": "SECRET_RAW_TOOL_PAYLOAD"},
            "tool_payload": {"secret": "SECRET_TOOL_PAYLOAD"},
            "nested": [
                {
                    "rawToolPayload": "SECRET_CAMEL_TOOL_PAYLOAD",
                    "toolPayload": "SECRET_CAMEL_TOOL_PAYLOAD_2",
                }
            ],
        }
    )

    encoded = json.dumps(report, ensure_ascii=False)
    assert report["safe"] == "kept"
    assert "SECRET_RAW_TOOL_PAYLOAD" not in encoded
    assert "SECRET_TOOL_PAYLOAD" not in encoded
    assert "SECRET_CAMEL_TOOL_PAYLOAD" not in encoded
    assert "SECRET_CAMEL_TOOL_PAYLOAD_2" not in encoded
    assert "raw_tool_payload" not in encoded
    assert "tool_payload" not in encoded
    assert "rawToolPayload" not in encoded
    assert "toolPayload" not in encoded


def test_runtime_safe_evidence_context_strips_nested_source_native_forbidden_metadata() -> None:
    context = {
        "source_family": "XLSX",
        "text": "sheet=현황 | value=국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx | 65세 이상 인구수 100명",
        "metadata": {
            "title": "SECRET_TITLE",
            "workbookId": "SECRET_WORKBOOK_ID",
            "sourcePath": "D:/secret/source.xlsx",
            "sheet": "현황",
        },
        "raw_locator": {
            "workbook_version_id": "SECRET_VERSION",
            "fileName": "source.xlsx",
            "cell": "B7",
        },
        "location_json": {
            "source_file_name": "source.xlsx",
            "formula": "=SUM(B1:B6)",
            "row_index_1based": 7,
        },
    }

    safe = actual_rag_eval._runtime_safe_evidence_context(context)
    encoded = json.dumps(safe, ensure_ascii=False)

    assert "SECRET_TITLE" not in encoded
    assert "SECRET_WORKBOOK_ID" not in encoded
    assert "SECRET_VERSION" not in encoded
    assert "source.xlsx" not in encoded
    assert ".xlsx" not in encoded
    assert "formula" not in encoded
    assert safe["metadata"] == {"sheet": "현황"}
    assert safe["raw_locator"] == {"cell": "B7"}
    assert safe["location_json"] == {"row_index_1based": 7}


def test_public_report_sanitizer_strips_nested_source_native_forbidden_metadata() -> None:
    public = actual_rag_eval._public_report_row(
        {
            "id": "nested-source-native",
            "retrieved_contexts": [
                {
                    "source_family": "PDF",
                    "text": "source.pdf | page 7 has the value",
                    "metadata": {
                        "sourcePath": "D:/secret/source.pdf",
                        "source_title": "SECRET_SOURCE_TITLE",
                        "page_number": 7,
                    },
                    "raw_locator": {
                        "fileName": "source.pdf",
                        "bbox": [1, 2, 3, 4],
                    },
                }
            ],
        }
    )

    encoded = json.dumps(public, ensure_ascii=False)
    assert "SECRET_SOURCE_TITLE" not in encoded
    assert "D:/secret/source.pdf" not in encoded
    assert "source.pdf" not in encoded
    assert ".pdf" not in encoded
    assert public["retrieved_contexts"][0]["metadata"] == {"page_number": 7}
    assert public["retrieved_contexts"][0]["raw_locator"] == {"bbox": [1, 2, 3, 4]}


def test_redact_absolute_local_paths_preserves_urls_and_redacts_windows_paths() -> None:
    redacted = actual_rag_eval._redact_absolute_local_paths(
        "LLM http://localhost:8081/v1 and path C:/Users/sfr99/secret.xlsx"
    )

    assert "http://localhost:8081/v1" in redacted
    assert "C:/Users/sfr99/secret.xlsx" not in redacted
    assert "redacted_path_sha256:" in redacted


def test_evidence_gate_diagnostic_computes_decision_without_mutating_answer() -> None:
    raw_outputs = [
        {
            "id": "q-date",
            "query": "When did Project Mercury launch?",
            "generated_answer": "Project Mercury launched on 2026-04-12.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-date",
                    "chunk_id": "chunk-date",
                    "source_atom_id": "src-date",
                    "evidence_bundle_id": "bundle-date",
                    "text": "Project Mercury launch window opens on 2026-04-12.",
                    "text_sha256": "hash-date",
                }
            ],
            "citations": [
                {
                    "doc_id": "doc-date",
                    "chunk_id": "chunk-date",
                    "source_atom_id": "src-date",
                    "evidence_bundle_id": "bundle-date",
                    "text": "Project Mercury launch window opens on 2026-04-12.",
                    "text_sha256": "hash-date",
                }
            ],
            "expected_answer": "forbidden expected answer",
            "expected_evidence": [{"text": "forbidden expected evidence"}],
            "answerability": "unanswerable",
            "row_id": "forbidden-row-id",
            "target_id": "forbidden-target-id",
        }
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="diagnostic")

    row = gated_outputs[0]
    assert row["generated_answer"] == "Project Mercury launched on 2026-04-12."
    assert row["evidence_gate_mode"] == "diagnostic"
    assert row["answer_gate_decision"] == "allow_answer"
    assert row["answer_modified_by_gate"] is False
    assert row["evidence_gate"]["gate_uses_expected_fields"] is False
    assert row["evidence_gate"]["gate_uses_gold_fields"] is False
    assert row["evidence_gate"]["gate_uses_legacy_fields"] is False
    assert row["evidence_gate"]["validator_uses_expected_fields"] is False
    assert row["evidence_gate"]["validator_uses_gold_fields"] is False
    assert row["evidence_gate"]["validator_uses_legacy_fields"] is False
    assert row["evidence_gate"]["retrieval_loop_triggered"] is False
    assert row["evidence_gate"]["selected_evidence_count"] == 1
    assert row["evidence_gate"]["citation_validations"][0]["citation_support_status"] == "supported"
    assert row["evidence_gate"]["citation_validations"][0]["citation_target_in_selected_evidence"] is True
    assert summary["evidence_gate_mode"] == "diagnostic"
    assert summary["allowed_answer_count"] == 1
    assert summary["abstained_count"] == 0
    assert summary["unsupported_answer_rate_before_gate"] == 0.0
    assert summary["unsupported_answer_rate_after_gate"] == 0.0


def test_evidence_gate_enforce_abstains_unsupported_numeric_and_entity_anchors() -> None:
    raw_outputs = [
        {
            "id": "q-wrong-date",
            "query": "When did Project Mercury launch?",
            "generated_answer": "Project Mercury launched on 2027-05-01.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-date",
                    "chunk_id": "chunk-date",
                    "source_atom_id": "src-date",
                    "evidence_bundle_id": "bundle-date",
                    "text": "Project Mercury launch window opens on 2026-04-12.",
                    "text_sha256": "hash-date",
                }
            ],
            "citations": [
                {
                    "doc_id": "doc-date",
                    "chunk_id": "chunk-date",
                    "source_atom_id": "src-date",
                    "evidence_bundle_id": "bundle-date",
                    "text": "Project Mercury launch window opens on 2026-04-12.",
                    "text_sha256": "hash-date",
                }
            ],
        },
        {
            "id": "q-wrong-entity",
            "query": "Where is Apollo HQ?",
            "generated_answer": "Apollo HQ is in Busan.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-hq",
                    "chunk_id": "chunk-hq",
                    "source_atom_id": "src-hq",
                    "evidence_bundle_id": "bundle-hq",
                    "text": "Apollo headquarters is in Seoul.",
                    "text_sha256": "hash-hq",
                }
            ],
            "citations": [
                {
                    "doc_id": "doc-hq",
                    "chunk_id": "chunk-hq",
                    "source_atom_id": "src-hq",
                    "evidence_bundle_id": "bundle-hq",
                    "text": "Apollo headquarters is in Seoul.",
                    "text_sha256": "hash-hq",
                }
            ],
        },
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="enforce")

    for row in gated_outputs:
        assert row["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
        assert row["answer_modified_by_gate"] is True
        assert row["unsupported_answer_blocked"] is True
        assert row["answer_gate_decision"] == "block_unsupported_answer"
        assert row["evidence_gate"]["retrieval_loop_triggered"] is False
    assert gated_outputs[0]["evidence_gate"]["abstention_reason"] == "missing_numeric_or_date_anchor"
    assert "2027" in gated_outputs[0]["evidence_gate"]["unsupported_answer_anchors"]
    assert gated_outputs[1]["evidence_gate"]["abstention_reason"] == "missing_entity_anchor"
    assert "busan" in gated_outputs[1]["evidence_gate"]["unsupported_answer_anchors"]
    assert summary["abstained_count"] == 2
    assert summary["unsupported_answer_blocked_count"] == 2
    assert summary["unsupported_answer_rate_before_gate"] == 1.0
    assert summary["unsupported_answer_rate_after_gate"] == 0.0


def test_evidence_gate_enforce_abstains_conflicting_numeric_date_evidence() -> None:
    raw_outputs = [
        {
            "id": "q-conflict",
            "query": "When did Project Mercury launch?",
            "generated_answer": "Project Mercury launched on 2026-04-12 at 09:00.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-conflict",
                    "chunk_id": "chunk-conflict",
                    "source_atom_id": "src-conflict",
                    "evidence_bundle_id": "bundle-conflict",
                    "text": "Project Mercury launched on 2026-04-12 at 10:00.",
                    "text_sha256": "hash-conflict",
                }
            ],
            "citations": [
                {
                    "doc_id": "doc-conflict",
                    "chunk_id": "chunk-conflict",
                    "source_atom_id": "src-conflict",
                    "evidence_bundle_id": "bundle-conflict",
                    "text": "Project Mercury launched on 2026-04-12 at 10:00.",
                    "text_sha256": "hash-conflict",
                }
            ],
        }
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="enforce")

    gate = gated_outputs[0]["evidence_gate"]
    assert gated_outputs[0]["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    assert gated_outputs[0]["answer_modified_by_gate"] is True
    assert gate["evidence_package_status"] == "conflicting"
    assert "conflicting_evidence" in gate["validation_reasons"]
    assert gate["abstention_reason"] == "conflicting_evidence"
    assert summary["conflicting_evidence_package_count"] == 1
    assert summary["unsupported_answer_rate_before_gate"] == 1.0
    assert summary["unsupported_answer_rate_after_gate"] == 0.0


def test_evidence_gate_enforce_blocks_off_topic_answer_missing_query_anchors_without_gold() -> None:
    raw_outputs = [
        {
            "id": "q-off-topic",
            "query": "Apollo headquarters location",
            "generated_answer": "Project Mercury launched on 2026-04-12.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-mercury",
                    "chunk_id": "chunk-mercury",
                    "source_atom_id": "src-mercury",
                    "evidence_bundle_id": "bundle-mercury",
                    "text": "Project Mercury launched on 2026-04-12.",
                    "text_sha256": "hash-mercury",
                }
            ],
            "citations": [
                {
                    "doc_id": "doc-mercury",
                    "chunk_id": "chunk-mercury",
                    "source_atom_id": "src-mercury",
                    "evidence_bundle_id": "bundle-mercury",
                    "text": "Project Mercury launched on 2026-04-12.",
                    "text_sha256": "hash-mercury",
                }
            ],
            "expected_answer": "Seoul",
            "expected_evidence": [{"text": "Apollo headquarters is in Seoul."}],
            "legacy_answer": "Seoul",
            "row_id": "forbidden-row",
            "target_id": "forbidden-target",
        }
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="enforce")

    row = gated_outputs[0]
    gate = row["evidence_gate"]
    assert row["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    assert row["answer_modified_by_gate"] is True
    assert row["answer_gate_decision"] == "block_unsupported_answer"
    assert row["unsupported_answer_blocked"] is True
    assert row["would_block_unsupported_answer"] is False
    assert gate["evidence_package_status"] == "insufficient"
    assert gate["selected_evidence_count"] == 1
    assert gate["citation_validations"][0]["citation_support_status"] == "supported"
    assert "missing_query_anchor" in gate["validation_reasons"]
    assert gate["abstention_reason"] == "insufficient_evidence"
    assert {"apollo", "headquarters"}.issubset(set(gate["unsupported_answer_anchors"]))
    assert gate["gate_uses_expected_fields"] is False
    assert gate["gate_uses_gold_fields"] is False
    assert gate["gate_uses_legacy_fields"] is False
    assert gate["unsupported_answer_blocked"] is True
    assert gate["would_block_unsupported_answer"] is False
    assert summary["insufficient_evidence_abstained_count"] == 1
    assert summary["unsupported_answer_rate_after_gate"] == 0.0


def test_citation_validator_requires_selected_evidence_not_retrieved_context_only() -> None:
    raw_outputs = [
        {
            "id": "q-selected",
            "query": "Where is Apollo HQ?",
            "generated_answer": "Apollo HQ is in Seoul.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-selected",
                    "chunk_id": "chunk-selected",
                    "source_atom_id": "src-selected",
                    "evidence_bundle_id": "bundle-selected",
                    "text": "Apollo HQ is in Seoul.",
                    "text_sha256": "hash-selected",
                },
                {
                    "doc_id": "doc-other",
                    "chunk_id": "chunk-other",
                    "source_atom_id": "src-other",
                    "evidence_bundle_id": "bundle-other",
                    "text": "Apollo HQ moved from Busan.",
                    "text_sha256": "hash-other",
                },
            ],
            "citations": [
                {
                    "doc_id": "doc-other",
                    "chunk_id": "chunk-other",
                    "source_atom_id": "src-other",
                    "evidence_bundle_id": "bundle-other",
                    "text": "Apollo HQ moved from Busan.",
                    "text_sha256": "hash-other",
                }
            ],
        }
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="diagnostic")

    row = gated_outputs[0]
    citation = row["evidence_gate"]["citation_validations"][0]
    assert row["evidence_gate"]["selected_evidence_count"] == 1
    assert citation["citation_target_exists"] is True
    assert citation["citation_target_in_retrieved_contexts"] is True
    assert citation["citation_target_in_selected_evidence"] is False
    assert citation["citation_support_status"] == "retrieved_context_only_diagnostic"
    assert row["answer_gate_decision"] == "block_unsupported_answer"
    assert row["answer_modified_by_gate"] is False
    assert row["generated_answer"] == "Apollo HQ is in Seoul."
    assert row["original_generated_answer_hash"] == row["gated_answer_hash"]
    assert row["unsupported_answer_blocked"] is False
    assert row["would_block_unsupported_answer"] is True
    assert row["evidence_gate"]["unsupported_answer_blocked"] is False
    assert row["evidence_gate"]["would_block_unsupported_answer"] is True
    assert summary["citation_supported_count"] == 0
    assert summary["citation_retrieved_context_only_diagnostic_count"] == 1
    assert summary["unsupported_answer_blocked_count"] == 0
    assert summary["would_block_unsupported_answer_count"] == 1


def test_selected_evidence_composer_uses_only_query_selected_sourceatom_evidence() -> None:
    raw_outputs = [
        {
            "id": "q-composer",
            "query": "Where is Apollo HQ?",
            "generated_answer": "extractive-v1 broad answer from all retrieved contexts",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-hq",
                    "chunk_id": "chunk-hq",
                    "source_atom_id": "src-hq",
                    "evidence_bundle_id": "bundle-hq",
                    "source_family": "TEXT",
                    "text": "Apollo HQ is in Seoul.",
                    "text_sha256": "hash-hq",
                },
                {
                    "doc_id": "doc-noise",
                    "chunk_id": "chunk-noise",
                    "source_atom_id": "src-noise",
                    "evidence_bundle_id": "bundle-noise",
                    "source_family": "TEXT",
                    "text": "The cafeteria menu changed in Busan.",
                    "text_sha256": "hash-noise",
                },
            ],
            "citations": [
                {
                    "doc_id": "doc-noise",
                    "chunk_id": "chunk-noise",
                    "source_atom_id": "src-noise",
                    "evidence_bundle_id": "bundle-noise",
                    "text": "The cafeteria menu changed in Busan.",
                    "text_sha256": "hash-noise",
                }
            ],
        }
    ]

    selected = select_composer_evidence(raw_outputs[0]["query"], raw_outputs[0]["retrieved_contexts"])
    composed = apply_selected_evidence_composer_to_outputs(raw_outputs)[0]
    gated_outputs, summary = apply_evidence_gate_to_outputs([composed], mode="diagnostic")

    assert [row["evidence_bundle_id"] for row in selected] == ["bundle-hq"]
    assert composed["answer_composer"]["provider"] == "selected-evidence-deterministic-v1"
    assert composed["answer_composer"]["input_policy"] == (
        "query_text_and_selected_sourceatom_evidence_only_no_gold_qrels_labels_ids_or_baseline"
    )
    assert composed["answer_composer"]["query_selected_evidence_count"] == 1
    assert composed["answer_composer"]["selected_evidence_count"] == 1
    assert composed["answer_composer"]["selected_evidence_ids"] == ["bundle-hq"]
    assert "Seoul" in composed["generated_answer"]
    assert "Busan" not in composed["generated_answer"]
    assert [citation["evidence_bundle_id"] for citation in composed["citations"]] == ["bundle-hq"]
    assert gated_outputs[0]["evidence_gate"]["citation_supported_count"] == 1
    assert gated_outputs[0]["evidence_gate"]["citation_retrieved_context_only_diagnostic_count"] == 0
    assert gated_outputs[0]["answer_gate_decision"] == "allow_answer"
    assert summary["citation_retrieved_context_only_diagnostic_count"] == 0


def test_selected_evidence_answer_shape_renders_xlsx_display_value_after_gate_without_gate_mutation() -> None:
    query = "2019년 2월 5호선의 승차총승객수는 몇 명입니까?"
    planner = {
        "source_family_hint": "xlsx",
        "planner_status": "planned_validated",
        "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
        "validated_axis_values": {
            "period": ["2019-02", "2019년 2월", "201902"],
            "row_entity": ["5호선"],
            "target_column": ["승차총승객수"],
            "display_value": [],
        },
    }
    raw_outputs = [
        {
            "id": "q-xlsx-answer-shape",
            "query": query,
            "query_evidence_planner": planner,
            "generated_answer": "legacy broad answer",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-xlsx",
                    "chunk_id": "chunk-xlsx-correct",
                    "source_atom_id": "src-xlsx-correct",
                    "evidence_bundle_id": "bundle-xlsx-correct",
                    "source_family": "XLSX",
                    "text": (
                        "sheet=철도 | range=A352:D401 | cell=D352 | row_label=대중교통구분=지하철 | "
                        "노선명=5호선 | 년월=201902 | target_column=승차총승객수 | display_value=15446522 | "
                        "source_date_alias=2019년 2월"
                    ),
                    "sheet": "철도",
                    "cell": "D352",
                    "cell_range": "A352:D401",
                    "row_index_1based": 352,
                    "row_label": "대중교통구분=지하철 | 노선명=5호선 | 년월=201902",
                    "column_label": "승차총승객수",
                    "target_column": "승차총승객수",
                    "display_value": "15446522",
                    "source_date_aliases": ["2019년 2월", "201902", "2019-02"],
                },
                {
                    "doc_id": "doc-xlsx",
                    "chunk_id": "chunk-xlsx-wrong-line",
                    "source_atom_id": "src-xlsx-wrong-line",
                    "evidence_bundle_id": "bundle-xlsx-wrong-line",
                    "source_family": "XLSX",
                    "text": (
                        "sheet=철도 | range=A302:D351 | cell=D302 | row_label=대중교통구분=지하철 | "
                        "노선명=수인선 | 년월=201902 | target_column=승차총승객수 | display_value=1124736 | "
                        "source_date_alias=2019년 2월"
                    ),
                    "sheet": "철도",
                    "cell": "D302",
                    "cell_range": "A302:D351",
                    "row_index_1based": 302,
                    "row_label": "대중교통구분=지하철 | 노선명=수인선 | 년월=201902",
                    "column_label": "승차총승객수",
                    "target_column": "승차총승객수",
                    "display_value": "1124736",
                    "source_date_aliases": ["2019년 2월", "201902", "2019-02"],
                },
            ],
            "citations": [],
        }
    ]

    composed = apply_selected_evidence_composer_to_outputs(raw_outputs, citation_format="markdown-portfolio")[0]
    gated_outputs, summary = apply_evidence_gate_to_outputs([composed], mode="enforce")
    rendered = gated_outputs[0]

    assert composed["generated_answer"].startswith("**Query:**")
    assert rendered["generated_answer"] == "15,446,522명입니다."
    assert rendered["answer_gate_decision"] == "allow_answer"
    assert rendered["evidence_gate"]["evidence_package_status"] == "sufficient"
    assert rendered["evidence_gate"]["gated_answer_hash"] == rendered["gated_answer_hash"]
    assert rendered["answer_shape_rendering"]["pre_render_answer_hash"] == rendered["gated_answer_hash"]
    assert rendered["answer_shape_rendering"]["rendered_answer_hash"] != rendered["gated_answer_hash"]
    assert rendered["answer_composer"]["rendering_mode"] == "source_owned_xlsx_display_value"
    assert rendered["answer_composer"]["rendered_answer_source_fields"] == ["target_column", "display_value"]
    assert rendered["answer_composer"]["uses_expected_answer"] is False
    assert rendered["answer_composer"]["uses_gold_fields"] is False
    assert rendered["answer_composer"]["uses_qrels"] is False
    assert rendered["answer_composer"]["uses_labels"] is False
    assert rendered["answer_composer"]["uses_query_or_row_or_target_ids"] is False
    assert summary["allowed_answer_count"] == 1


def test_selected_evidence_answer_shape_skips_conflicting_xlsx_display_values() -> None:
    query = "2019년 2월 5호선의 승차총승객수는 몇 명입니까?"
    planner = {
        "source_family_hint": "xlsx",
        "planner_status": "planned_validated",
        "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
        "validated_axis_values": {
            "period": ["2019-02", "2019년 2월", "201902"],
            "row_entity": ["5호선"],
            "target_column": ["승차총승객수"],
            "display_value": [],
        },
    }
    selected_evidence = [
        {
            "doc_id": "doc-xlsx",
            "chunk_id": "chunk-xlsx-first",
            "source_atom_id": "src-xlsx-first",
            "evidence_bundle_id": "bundle-xlsx-first",
            "source_family": "XLSX",
            "text": "노선명=5호선 | 년월=201902 | target_column=승차총승객수 | display_value=15446522",
            "sheet": "철도",
            "cell": "D352",
            "cell_range": "A352:D401",
            "row_label": "대중교통구분=지하철 | 노선명=5호선 | 년월=201902",
            "column_label": "승차총승객수",
            "target_column": "승차총승객수",
            "display_value": "15446522",
            "source_date_aliases": ["2019년 2월", "201902", "2019-02"],
        },
        {
            "doc_id": "doc-xlsx",
            "chunk_id": "chunk-xlsx-second",
            "source_atom_id": "src-xlsx-second",
            "evidence_bundle_id": "bundle-xlsx-second",
            "source_family": "XLSX",
            "text": "노선명=5호선 | 년월=201902 | target_column=승차총승객수 | display_value=999999",
            "sheet": "철도",
            "cell": "D353",
            "cell_range": "A352:D401",
            "row_label": "대중교통구분=지하철 | 노선명=5호선 | 년월=201902",
            "column_label": "승차총승객수",
            "target_column": "승차총승객수",
            "display_value": "999999",
            "source_date_aliases": ["2019년 2월", "201902", "2019-02"],
        },
    ]
    row = {
        "id": "q-xlsx-conflicting-answer-shape",
        "query": query,
        "query_evidence_planner": planner,
        "generated_answer": (
            "**Query:** 2019년 2월 5호선의 승차총승객수는 몇 명입니까?\n\n"
            "**Short answer:** 노선명=5호선 | 년월=201902 | target_column=승차총승객수 | "
            "display_value=15446522 | display_value=999999\n\n"
            "**Supporting passages:**"
        ),
        "retrieved_contexts": selected_evidence,
        "citations": [
            {
                "doc_id": evidence["doc_id"],
                "chunk_id": evidence["chunk_id"],
                "source_atom_id": evidence["source_atom_id"],
                "evidence_bundle_id": evidence["evidence_bundle_id"],
                "text": evidence["text"],
            }
            for evidence in selected_evidence
        ],
    }

    rendered = apply_evidence_gate_to_outputs([row], mode="enforce")[0][0]

    assert rendered["answer_gate_decision"] == "allow_answer"
    assert rendered["generated_answer"].startswith("**Query:**")
    assert rendered["answer_shape_rendering"] == {
        "applied": False,
        "skip_reason": "ambiguous_xlsx_display_value_candidates",
        "candidate_count": 2,
    }


def test_selected_evidence_composer_abstains_without_selected_sourceatom_evidence() -> None:
    raw_outputs = [
        {
            "id": "q-composer-empty",
            "query": "Where is Apollo HQ?",
            "generated_answer": "extractive-v1 broad answer from an unrelated retrieved context",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-noise",
                    "chunk_id": "chunk-noise",
                    "source_atom_id": "src-noise",
                    "evidence_bundle_id": "bundle-noise",
                    "source_family": "TEXT",
                    "text": "The cafeteria menu changed in Busan.",
                    "text_sha256": "hash-noise",
                }
            ],
            "citations": [
                {
                    "doc_id": "doc-noise",
                    "chunk_id": "chunk-noise",
                    "source_atom_id": "src-noise",
                    "evidence_bundle_id": "bundle-noise",
                    "text": "The cafeteria menu changed in Busan.",
                    "text_sha256": "hash-noise",
                }
            ],
        }
    ]

    composed = apply_selected_evidence_composer_to_outputs(raw_outputs)[0]
    gated_outputs, summary = apply_evidence_gate_to_outputs([composed], mode="enforce")

    assert composed["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    assert composed["citations"] == []
    assert composed["answer_composer"]["selected_evidence_count"] == 0
    assert composed["answer_composer"]["abstained"] is True
    assert composed["answer_composer"]["abstention_reason"] == "no_selected_sourceatom_evidence"
    assert gated_outputs[0]["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    assert summary["unsupported_answer_rate_after_gate"] == 0.0


def test_selected_evidence_composer_abstains_when_selected_evidence_is_insufficient() -> None:
    raw_outputs = [
        {
            "id": "q-composer-insufficient",
            "query": "When did Apollo HQ open?",
            "generated_answer": "extractive-v1 broad answer from a query-overlapping context",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-hq",
                    "chunk_id": "chunk-hq",
                    "source_atom_id": "src-hq",
                    "evidence_bundle_id": "bundle-hq",
                    "source_family": "TEXT",
                    "text": "Apollo HQ opening is described here, but the opening date is omitted.",
                    "text_sha256": "hash-hq-no-date",
                }
            ],
            "citations": [],
        }
    ]

    selected = select_composer_evidence(raw_outputs[0]["query"], raw_outputs[0]["retrieved_contexts"])
    composed = apply_selected_evidence_composer_to_outputs(raw_outputs)[0]
    gated_outputs, summary = apply_evidence_gate_to_outputs([composed], mode="enforce")

    assert [row["evidence_bundle_id"] for row in selected] == ["bundle-hq"]
    assert composed["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    assert composed["citations"] == []
    assert composed["answer_composer"]["query_selected_evidence_count"] == 1
    assert composed["answer_composer"]["selected_evidence_count"] == 0
    assert composed["answer_composer"]["abstained"] is True
    assert composed["answer_composer"]["abstention_reason"] == "insufficient_selected_evidence"
    assert gated_outputs[0]["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    assert summary["unsupported_answer_rate_after_gate"] == 0.0


def test_selected_evidence_composer_ignores_doc_chunk_only_contexts() -> None:
    raw_outputs = [
        {
            "id": "q-composer-doc-only",
            "query": "Where is Apollo HQ?",
            "generated_answer": "extractive-v1 broad answer",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-hq",
                    "chunk_id": "chunk-hq",
                    "source_family": "TEXT",
                    "text": "Apollo HQ is in Seoul.",
                    "text_sha256": "hash-doc-only",
                },
                {
                    "doc_id": "doc-hq-2",
                    "chunk_id": "chunk-hq-2",
                    "source_atom_id": "src-hq-2",
                    "evidence_bundle_id": "bundle-hq-2",
                    "source_family": "TEXT",
                    "text": "Apollo HQ is in Seoul.",
                    "text_sha256": "hash-sourceatom",
                },
            ],
            "citations": [],
        }
    ]

    selected = select_composer_evidence(raw_outputs[0]["query"], raw_outputs[0]["retrieved_contexts"])
    composed = apply_selected_evidence_composer_to_outputs(raw_outputs)[0]

    assert [row["evidence_bundle_id"] for row in selected] == ["bundle-hq-2"]
    assert [citation["evidence_bundle_id"] for citation in composed["citations"]] == ["bundle-hq-2"]
    assert all(citation.get("doc_id") != "doc-hq" for citation in composed["citations"])


def test_selected_evidence_composer_accepts_source_atom_without_bundle_id() -> None:
    raw_outputs = [
        {
            "id": "q-composer-sourceatom-only",
            "query": "When is Apollo HQ opening?",
            "generated_answer": "extractive-v1 broad answer",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-hq",
                    "chunk_id": "chunk-hq",
                    "source_atom_id": "src-hq",
                    "evidence_bundle_id": "",
                    "source_family": "TEXT",
                    "text": "Apollo HQ opening is scheduled for 2026년 4월.",
                    "text_sha256": "hash-hq",
                }
            ],
            "citations": [],
        }
    ]

    selected = select_composer_evidence(raw_outputs[0]["query"], raw_outputs[0]["retrieved_contexts"])
    composed = apply_selected_evidence_composer_to_outputs(raw_outputs)[0]
    gated_outputs, summary = apply_evidence_gate_to_outputs([composed], mode="diagnostic")

    assert [row["source_atom_id"] for row in selected] == ["src-hq"]
    assert composed["answer_composer"]["selected_evidence_ids"] == ["src-hq"]
    assert composed["answer_composer"]["abstained"] is False
    assert [citation["source_atom_id"] for citation in composed["citations"]] == ["src-hq"]
    assert gated_outputs[0]["evidence_gate"]["citation_supported_count"] == 1
    assert summary["citation_retrieved_context_only_diagnostic_count"] == 0


def test_selected_evidence_composer_cites_only_answer_supporting_selected_evidence() -> None:
    raw_outputs = [
        {
            "id": "q-composer-citation-subset",
            "query": "Where is Apollo HQ?",
            "generated_answer": "extractive-v1 broad answer",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-seoul",
                    "chunk_id": "chunk-seoul",
                    "source_atom_id": "src-seoul",
                    "source_family": "TEXT",
                    "text": "Apollo HQ is in Seoul.",
                    "text_sha256": "hash-seoul",
                },
                {
                    "doc_id": "doc-cafe",
                    "chunk_id": "chunk-cafe",
                    "source_atom_id": "src-cafe",
                    "source_family": "TEXT",
                    "text": "Apollo HQ cafeteria moved from Busan.",
                    "text_sha256": "hash-cafe",
                },
            ],
            "citations": [],
        }
    ]

    selected = select_composer_evidence(raw_outputs[0]["query"], raw_outputs[0]["retrieved_contexts"])
    composed = apply_selected_evidence_composer_to_outputs(raw_outputs)[0]
    gated_outputs, summary = apply_evidence_gate_to_outputs([composed], mode="diagnostic")

    assert [row["source_atom_id"] for row in selected] == ["src-seoul", "src-cafe"]
    assert [citation["source_atom_id"] for citation in composed["citations"]] == ["src-seoul"]
    assert gated_outputs[0]["evidence_gate"]["citation_supported_count"] == 1
    assert summary["citation_retrieved_context_only_diagnostic_count"] == 0


def test_selected_evidence_composer_prefers_context_when_query_anchors_span_lines() -> None:
    raw_outputs = [
        {
            "id": "q-composer-line-anchors",
            "query": "유우야키의 나이와 생일은 어떻게 적혀 있어",
            "generated_answer": "extractive-v1 broad answer",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-yuyaki",
                    "chunk_id": "chunk-yuyaki",
                    "source_atom_id": "src-yuyaki",
                    "evidence_bundle_id": "bundle-yuyaki",
                    "source_family": "TEXT",
                    "text": "夕焼(ユウヤキ)\n나이\n16세\n생일\n9월 29일\n유우야키 항목 참조.",
                    "text_sha256": "hash-yuyaki",
                    "score": 0.5,
                },
                {
                    "doc_id": "doc-shiro",
                    "chunk_id": "chunk-shiro",
                    "source_atom_id": "src-shiro",
                    "evidence_bundle_id": "bundle-shiro",
                    "source_family": "TEXT",
                    "text": "시로의 나이와 생일은 공식적으로 밝혀지지 않았고 외관은 대략 30대 중후반으로 추정된다.",
                    "text_sha256": "hash-shiro",
                    "score": 0.5,
                },
            ],
            "citations": [],
        }
    ]

    composed = apply_selected_evidence_composer_to_outputs(raw_outputs, citation_format="evidence-id")[0]
    gated_outputs, summary = apply_evidence_gate_to_outputs([composed], mode="diagnostic")

    assert composed["answer_composer"]["query_selected_evidence_ids"][0] == "bundle-yuyaki"
    assert composed["answer_composer"]["selected_evidence_ids"] == ["bundle-yuyaki"]
    assert "유우야키" in composed["generated_answer"]
    assert "16세" in composed["generated_answer"]
    assert "9월 29일" in composed["generated_answer"]
    assert "시로" not in composed["generated_answer"]
    assert gated_outputs[0]["answer_gate_decision"] == "allow_answer"
    assert gated_outputs[0]["evidence_gate"]["missing_query_anchors"] == []
    assert summary["unsupported_answer_rate_after_gate"] == 0.0


def test_evidence_gate_matches_compact_korean_query_anchor_to_spaced_title() -> None:
    validation = validate_evidence_package_for_gate(
        {
            "id": "q-spaced-title",
            "query": "소드아트 오디널 스케일은 어떤 극장판을 가리켜",
            "generated_answer": "소드 아트 온라인 -오디널 스케일-.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-sao",
                    "chunk_id": "chunk-os",
                    "source_atom_id": "src-sao-os",
                    "evidence_bundle_id": "bundle-sao-os",
                    "source_family": "TEXT",
                    "text": "극장판 소드 아트 온라인 -오디널 스케일- 과 같은 세계관이라는 것을 보여준다.",
                    "text_sha256": "hash-sao-os",
                }
            ],
            "citations": [
                {
                    "doc_id": "doc-sao",
                    "chunk_id": "chunk-os",
                    "source_atom_id": "src-sao-os",
                    "evidence_bundle_id": "bundle-sao-os",
                    "text": "극장판 소드 아트 온라인 -오디널 스케일- 과 같은 세계관이라는 것을 보여준다.",
                    "text_sha256": "hash-sao-os",
                }
            ],
        }
    )

    assert validation["evidence_package_status"] == "sufficient"
    assert "소드아트" not in validation["missing_query_anchors"]
    assert validation["query_anchor_coverage"] == 1.0
    assert validation["citation_supported_count"] == 1


def test_selected_evidence_composer_tolerates_invalid_scores_and_deduplicates() -> None:
    contexts = [
        {
            "rank": 1,
            "doc_id": "doc-low",
            "chunk_id": "chunk-low",
            "source_atom_id": "src-low",
            "evidence_bundle_id": "bundle-low",
            "text": "Apollo is mentioned, but HQ is not.",
            "score": "not-a-number",
        },
        {
            "rank": 2,
            "doc_id": "doc-hq",
            "chunk_id": "chunk-hq",
            "source_atom_id": "src-hq",
            "evidence_bundle_id": "bundle-hq",
            "text": "Apollo HQ is in Seoul.",
            "score": 0.1,
        },
        {
            "rank": 3,
            "doc_id": "doc-hq-duplicate",
            "chunk_id": "chunk-hq-duplicate",
            "source_atom_id": "src-hq",
            "evidence_bundle_id": "bundle-hq",
            "text": "Apollo HQ is in Seoul again.",
            "score": 0.9,
        },
    ]

    selected = select_composer_evidence("Where is Apollo HQ?", contexts, max_evidence=2)

    assert [row["evidence_bundle_id"] for row in selected] == ["bundle-hq", "bundle-low"]


def test_selected_evidence_composer_formats_selected_citations_by_variant() -> None:
    raw_outputs = [
        {
            "id": "q-composer-citation-format",
            "query": "Where is Apollo HQ?",
            "generated_answer": "extractive-v1 broad answer",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-hq",
                    "chunk_id": "chunk-hq",
                    "source_atom_id": "src-hq",
                    "evidence_bundle_id": "bundle-hq",
                    "source_family": "TEXT",
                    "granularity": "paragraph",
                    "page_number": "12",
                    "locator_fingerprint": "loc-hq",
                    "text": "Apollo HQ is in Seoul.",
                    "text_sha256": "hash-hq",
                }
            ],
            "citations": [],
        }
    ]

    compact = apply_selected_evidence_composer_to_outputs(raw_outputs, citation_format="compact")[0]
    evidence_id = apply_selected_evidence_composer_to_outputs(raw_outputs, citation_format="evidence-id")[0]
    source_locator = apply_selected_evidence_composer_to_outputs(raw_outputs, citation_format="source-locator")[0]

    assert compact["answer_composer"]["citation_format"] == "compact"
    assert compact["answer_composer"]["formatted_citations"] == ["[1] doc-hq#chunk-hq"]
    assert evidence_id["answer_composer"]["formatted_citations"] == [
        "[1] evidence_bundle_id=bundle-hq; source_atom_id=src-hq"
    ]
    assert source_locator["answer_composer"]["formatted_citations"] == [
        "[1] TEXT paragraph doc-hq#chunk-hq page=12 locator=loc-hq"
    ]
    assert [citation["evidence_bundle_id"] for citation in source_locator["citations"]] == ["bundle-hq"]


def test_selected_evidence_composer_markdown_portfolio_format_is_reader_facing() -> None:
    raw_outputs = [
        {
            "id": "q-composer-markdown-format",
            "query": "Where is Apollo HQ?",
            "generated_answer": "extractive-v1 broad answer",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-hq",
                    "chunk_id": "chunk-hq",
                    "source_atom_id": "src-hq",
                    "evidence_bundle_id": "bundle-hq",
                    "source_family": "TEXT",
                    "granularity": "paragraph",
                    "text": "Apollo HQ is in Seoul.",
                    "text_sha256": "hash-hq",
                }
            ],
            "citations": [],
        }
    ]

    composed = apply_selected_evidence_composer_to_outputs(raw_outputs, citation_format="markdown-portfolio")[0]
    gated_outputs, summary = apply_evidence_gate_to_outputs([composed], mode="diagnostic")

    assert composed["answer_composer"]["citation_format"] == "markdown-portfolio"
    assert composed["answer_composer"]["formatted_citations"] == [
        "- [1] **TEXT paragraph** doc-hq#chunk-hq (evidence_bundle_id=bundle-hq; source_atom_id=src-hq)"
    ]
    assert "## Selected Evidence Citations" in composed["generated_answer"]
    assert "- [1] **TEXT paragraph** doc-hq#chunk-hq" in composed["generated_answer"]
    assert "Apollo HQ is in Seoul." in composed["generated_answer"]
    assert gated_outputs[0]["evidence_gate"]["citation_supported_count"] == 1
    assert summary["citation_retrieved_context_only_diagnostic_count"] == 0


def test_selected_evidence_sentence_keeps_question_facet_out_of_broad_profile() -> None:
    selected = [
        {
            "doc_id": "doc-yuyaki",
            "chunk_id": "chunk-yuyaki",
            "source_atom_id": "src-yuyaki",
            "evidence_bundle_id": "bundle-yuyaki",
            "source_family": "TEXT",
            "text": (
                "夕焼(ユウヤキ) 나이 16세 생일 9월 29일 신장 164cm "
                "가슴사이즈 F컵 쓰리사이즈 B90-W57-H90 혈액형 O형 "
                "사용 손 양손 무기 및 전투 스타일 태도 두 자루/참격 좋아하는 음식 발효식품"
            ),
        }
    ]

    answer = actual_rag_eval._selected_evidence_sentence("유우야키의 나이와 생일은 어떻게 적혀 있어", selected)

    assert "나이 16세" in answer
    assert "생일 9월 29일" in answer
    assert "신장" not in answer
    assert "혈액형" not in answer
    assert "무기" not in answer


def test_selected_evidence_sentence_omits_interleaved_profile_facets() -> None:
    selected = [
        {
            "doc_id": "doc-mika",
            "chunk_id": "chunk-profile",
            "source_atom_id": "src-mika",
            "evidence_bundle_id": "bundle-mika",
            "source_family": "TEXT",
            "text": "Mika profile: age 17. Height 160cm. Birthday May 8. Blood type B. Weapon rifle.",
        }
    ]

    answer = actual_rag_eval._selected_evidence_sentence("What are Mika's age and birthday?", selected)

    assert "age 17" in answer
    assert "Birthday May 8" in answer
    assert "Height" not in answer
    assert "Blood type" not in answer
    assert "Weapon" not in answer


def test_selected_evidence_sentence_does_not_match_profile_facet_substrings() -> None:
    selected = [
        {
            "doc_id": "doc-keyword",
            "chunk_id": "chunk-keyword",
            "source_atom_id": "src-keyword",
            "evidence_bundle_id": "bundle-keyword",
            "source_family": "TEXT",
            "text": "문서 키워드는 나침반이다. 실제 답은 서울 본부이다.",
        }
    ]

    answer = actual_rag_eval._selected_evidence_sentence("본부는 어디야?", selected)

    assert "서울 본부" in answer
    assert answer != "키워드는 나침반이다."


def test_selected_evidence_sentence_prefers_profile_context_with_query_entity() -> None:
    selected = [
        {
            "doc_id": "doc-wrong",
            "chunk_id": "chunk-wrong",
            "source_atom_id": "src-wrong",
            "evidence_bundle_id": "bundle-wrong",
            "source_family": "TEXT",
            "text": "시로의 나이와 생일은 공식적으로 밝혀지지 않았다.",
        },
        {
            "doc_id": "doc-yuyaki",
            "chunk_id": "chunk-yuyaki",
            "source_atom_id": "src-yuyaki",
            "evidence_bundle_id": "bundle-yuyaki",
            "source_family": "TEXT",
            "text": "夕焼(ユウヤキ) 나이 16세 생일 9월 29일 신장 164cm 유우야키 항목 참조.",
        },
    ]

    answer = actual_rag_eval._selected_evidence_sentence("유우야키의 나이와 생일은 어떻게 적혀 있어", selected)

    assert "나이 16세" in answer
    assert "생일 9월 29일" in answer
    assert "신장" not in answer


def test_run_eval_selected_evidence_composer_is_explicit_and_report_only(tmp_path: Path) -> None:
    dataset = tmp_path / "selected_composer_gold.jsonl"
    context = tmp_path / "selected_composer_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_composer"
    write_jsonl(
        dataset,
        [{"id": "q-composer", "query": "Where is Apollo HQ?", "answerability": "answerable"}],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-composer",
                "generated_answer": "extractive-v1 broad answer from every context",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "text": "Apollo HQ is in Seoul.",
                        "text_sha256": "hash-hq",
                    },
                    {
                        "doc_id": "doc-noise",
                        "chunk_id": "chunk-noise",
                        "source_atom_id": "src-noise",
                        "evidence_bundle_id": "bundle-noise",
                        "source_family": "TEXT",
                        "text": "The cafeteria menu changed in Busan.",
                        "text_sha256": "hash-noise",
                    },
                ],
                "citations": [
                    {
                        "doc_id": "doc-noise",
                        "chunk_id": "chunk-noise",
                        "source_atom_id": "src-noise",
                        "evidence_bundle_id": "bundle-noise",
                        "text": "The cafeteria menu changed in Busan.",
                        "text_sha256": "hash-noise",
                    }
                ],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=2,
        run_id="selected_composer",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="evidence-id",
    )

    assert output_file_names(output_dir) == ["report.json"]
    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    assert report["generator_config"]["provider"] == "selected-evidence-deterministic-v1"
    assert report["generator_config"]["extractive_v1_baseline_preserved_for_comparison"] is True
    assert report["generator_config"]["selected_evidence_citation_formatter_invoked"] is True
    assert report["generator_config"]["selected_evidence_citation_format"] == "evidence-id"
    assert "markdown-portfolio" in report["generator_config"]["selected_evidence_citation_formatter_variants_available"]
    selected_evidence_summary_text = json.dumps(
        {
            "limitations": report["limitations"],
            "next_repair_targets": report["next_repair_targets"],
            "residual_risks": report["residual_risks"],
        },
        ensure_ascii=False,
    )
    assert "selected-evidence composer supplies answers" in selected_evidence_summary_text
    assert "selected-evidence composer is active" in selected_evidence_summary_text
    assert "extractive-v1 remains the generator" not in selected_evidence_summary_text
    assert "replace extractive-v1" not in selected_evidence_summary_text
    assert "answer composition is still extractive-v1" not in selected_evidence_summary_text
    assert report["generator_config"]["expected_answer_used_for_generation"] is False
    assert report["generator_config"]["expected_evidence_used_for_generation"] is False
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False
    assert report["artifact_contract"]["portfolio_experiment_sidecar_written"] is False
    assert "Seoul" in row["generated_answer"]
    assert "Busan" not in row["generated_answer"]
    assert [citation["evidence_bundle_id"] for citation in row["citations"]] == ["bundle-hq"]
    assert row["answer_composer"]["selected_evidence_ids"] == ["bundle-hq"]
    assert row["answer_composer"]["formatted_citations"] == [
        "[1] evidence_bundle_id=bundle-hq; source_atom_id=src-hq"
    ]
    assert row["answer_composer"]["uses_gold_fields"] is False
    assert row["answer_composer"]["uses_qrels"] is False
    assert row["answer_composer"]["uses_labels"] is False
    assert row["answer_composer"]["uses_answerability"] is False
    assert row["answer_composer"]["uses_expected_answer"] is False
    assert row["answer_composer"]["uses_expected_evidence"] is False
    assert row["answer_composer"]["uses_query_or_row_or_target_ids"] is False
    assert row["answer_composer"]["uses_baseline_topk_or_legacy_outputs"] is False
    assert "raw_prompt_payload_written" not in row["answer_composer"]
    assert "raw_response_payload_written" not in row["answer_composer"]
    assert row["evidence_gate"]["citation_retrieved_context_only_diagnostic_count"] == 0


def test_load_eval_dataset_normalizes_gold29_source_fields_in_memory(tmp_path: Path) -> None:
    dataset = tmp_path / "official_metric_input.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "query_id": "text_namu_v2_0005",
                "question_ko": "자동판매기 미궁 방랑 애니 3기 방영 시기는 문서에 어떻게 적혀 있어",
                "expected_answer_ko": "감독은 야마모토 타카시, 방영 시기는 2026년 4월.",
                "supporting_evidence_note": "감독은 야마모토 타카시, 방영 시기는 2026년 4월.",
                "citation_locator": {"cited_chunk_ids": ["a648c3a062d55aa3"]},
                "answerability_label": 3,
                "relevance_label": 3,
                "gold_status": "APPROVED",
                "track": "text_namu_v2_1",
            }
        ],
    )

    items = load_eval_dataset(dataset)

    assert len(items) == 1
    item = items[0]
    assert item.id == "text_namu_v2_0005"
    assert item.query == "자동판매기 미궁 방랑 애니 3기 방영 시기는 문서에 어떻게 적혀 있어"
    assert item.answerability == "answerable"
    assert item.has_answerability_label is True
    assert "missing_answerability_label" not in item.validation_warnings
    assert item.expected_answer == "감독은 야마모토 타카시, 방영 시기는 2026년 4월."
    assert item.expected_evidence[0].chunk_id == "a648c3a062d55aa3"
    assert item.expected_evidence[0].text == "감독은 야마모토 타카시, 방영 시기는 2026년 4월."
    assert item.source_row["question_ko"] == item.query


def test_run_eval_response_quality_summary_marks_silver_strict_metrics_not_applicable(tmp_path: Path) -> None:
    dataset = tmp_path / "xlsx_silver_retrieval_evidence_selected_v0.jsonl"
    context = tmp_path / "silver_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "silver_response_quality_summary"
    write_jsonl(
        dataset,
        [
            {
                "query_id": "xlsx_silver_v0_000001",
                "query": "자료 안에서 테크노페미니즘 항목의 엑셀 범위를 찾아줘.",
                "expected_answer_text": "Sheet1 > A5952:J6001",
                "citation_text": "Sheet1 > A5952:J6001",
                "quality_tier": "SILVER",
                "split": "silver_selected",
                "include_in_answer_generation_denominator": "false",
                "include_in_official_gold_denominator": "false",
                "track": "XLSX",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "xlsx_silver_v0_000001",
                "generated_answer": "Sheet1 > A5952:J6001",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-xlsx",
                        "chunk_id": "chunk-range",
                        "source_atom_id": "src-range",
                        "evidence_bundle_id": "bundle-range",
                        "source_family": "XLSX",
                        "granularity": "table_row",
                        "text": "Sheet1 > A5952:J6001",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-xlsx",
                        "chunk_id": "chunk-range",
                        "source_atom_id": "src-range",
                        "evidence_bundle_id": "bundle-range",
                        "text": "Sheet1 > A5952:J6001",
                    }
                ],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="silver_response_quality_summary",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    summary = report["response_quality_input_summary"]
    assert summary["schema_version"] == "actual_rag_eval.response_quality_input_summary.v1"
    assert summary["source_profile"] == "diagnostic_silver"
    assert summary["item_count"] == 1
    assert summary["answerability_distribution"] == {"answerable": 0, "unanswerable": 0, "unknown": 1}
    assert summary["strict_answer_citation_e2e_policy"]["strict_metrics_not_applicable"] is True
    assert summary["strict_answer_citation_e2e_policy"]["reason"] == "diagnostic_silver_answerability_unknown"
    assert summary["strict_answer_citation_e2e_policy"]["silver_strict_answer_citation_e2e"] == "N/A"
    assert summary["guardrails"]["official_metric"] is False
    assert summary["guardrails"]["gold_or_qrels_mutation"] is False
    assert summary["normalization"]["query_field_mappings"] == ["query"]
    assert summary["normalization"]["expected_answer_field_mappings"] == ["expected_answer_text"]
    assert summary["normalization"]["expected_evidence_field_mappings"] == ["citation_text"]
    assert report["strict_metrics"]["exact_or_alias_answer_correctness"]["denominator"] == 0
    assert report["strict_metrics"]["citation_precision"]["denominator"] == 0
    assert report["strict_metrics"]["e2e_rag_success_strict"]["denominator"] == 0
    assert output_file_names(output_dir) == ["report.json"]


def test_xlsx_pdf_residual_breakdown_classifies_source_derived_failures_without_gold_fields(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "gold29_xlsx_pdf_probe.jsonl"
    context = tmp_path / "xlsx_pdf_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_pdf_residual_breakdown"
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx-axis-missing",
                "query": "2019년 2월 5호선 승차총승객수는 얼마야?",
                "answerability": "answerable",
                "track": "xlsx_business_structured",
            },
            {
                "id": "pdf-axis-missing",
                "query": "2024년 영업이익 표의 값은 얼마야?",
                "answerability": "answerable",
                "track": "pdf_business_ocr_mm",
            },
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "xlsx-axis-missing",
                "generated_answer": "15,446,522명",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-xlsx",
                        "chunk_id": "chunk-xlsx",
                        "source_atom_id": "src-xlsx",
                        "evidence_bundle_id": "bundle-xlsx",
                        "source_family": "XLSX",
                        "granularity": "table_row",
                        "text": "2019년 2월 값은 15,446,522명입니다.",
                        "sheet": "2019년 2월",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-xlsx",
                        "chunk_id": "chunk-xlsx",
                        "source_atom_id": "src-xlsx",
                        "evidence_bundle_id": "bundle-xlsx",
                        "text": "2019년 2월 값은 15,446,522명입니다.",
                    }
                ],
            },
            {
                "id": "pdf-axis-missing",
                "generated_answer": "12.3억원",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-pdf",
                        "chunk_id": "chunk-pdf",
                        "source_atom_id": "src-pdf",
                        "evidence_bundle_id": "bundle-pdf",
                        "source_family": "PDF",
                        "granularity": "page_text",
                        "text": "2024년 값은 12.3억원입니다.",
                        "page_number": 7,
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-pdf",
                        "chunk_id": "chunk-pdf",
                        "source_atom_id": "src-pdf",
                        "evidence_bundle_id": "bundle-pdf",
                        "text": "2024년 값은 12.3억원입니다.",
                    }
                ],
            },
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="xlsx_pdf_residual_breakdown",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    breakdown = report["xlsx_pdf_residual_breakdown"]
    assert breakdown["schema_version"] == "actual_rag_eval.xlsx_pdf_residual_breakdown.v1"
    assert breakdown["enabled"] is True
    assert breakdown["report_only_diagnostic"] is True
    assert breakdown["official_metric"] is False
    assert breakdown["official_metric_input_rows"] == 0
    assert breakdown["uses_expected_fields"] is False
    assert breakdown["uses_gold_fields"] is False
    assert breakdown["uses_qrels"] is False
    assert breakdown["uses_labels"] is False
    assert breakdown["uses_ids"] is False
    assert breakdown["classification_counts"] == {"selected_evidence_has_value_missing_axis": 2}
    rows_by_id = {row["item_id"]: row for row in breakdown["rows"]}
    assert rows_by_id["xlsx-axis-missing"]["source_family"] == "XLSX"
    assert rows_by_id["xlsx-axis-missing"]["source_axis_fields_present"] == ["sheet"]
    assert rows_by_id["xlsx-axis-missing"]["source_axis_fields_missing"] == [
        "cell",
        "cell_range",
        "column_label",
        "header",
        "header_path",
        "row_index_1based",
        "row_label",
        "table_id",
        "target_column",
    ]
    assert rows_by_id["pdf-axis-missing"]["source_family"] == "PDF"
    assert rows_by_id["pdf-axis-missing"]["source_axis_fields_present"] == ["page_number"]
    assert rows_by_id["pdf-axis-missing"]["source_axis_fields_missing"] == [
        "bbox",
        "block_index",
        "column_label",
        "row_label",
        "section_title",
        "table_caption",
    ]
    assert output_file_names(output_dir) == ["report.json"]


def test_residual_anchor_matrix_reports_stage_anchor_presence_without_shortcuts(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "gold29_xlsx_axis_probe.jsonl"
    context = tmp_path / "xlsx_axis_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "residual_anchor_matrix"
    query = "2019년 2월 5호선 승차총승객수는 얼마야?"
    planner = actual_rag_eval._query_evidence_planner_summary(
        query=query,
        status="planned_validated",
        config={"backend": "test", "base_url": "http://localhost", "model": "test-model"},
        plan={
            "source_family_hint": "xlsx",
            "query_task": "date_filtered_lookup",
            "row_filters": {"line_name": "5호선", "period": "2019-02"},
            "target_axis": {"column": "승차총승객수", "value_type": "number"},
            "evidence_contract": ["period", "row_entity", "target_column", "display_value"],
            "intent_tokens": ["얼마야"],
            "validated_required_axes": ["period", "row_entity", "target_column", "display_value"],
            "validated_axis_values": {
                "period": ["2019-02", "2019년 2월"],
                "row_entity": ["5호선"],
                "target_column": ["승차총승객수"],
                "display_value": ["source-owned-display-axis-required"],
            },
        },
    )
    write_jsonl(
        dataset,
        [
            {
                "id": "xlsx-anchor-matrix",
                "query": query,
                "answerability": "answerable",
                "track": "xlsx_business_structured",
                "expected_answer": "SECRET_EXPECTED_VALUE_NEVER_RUNTIME",
                "expected_evidence": [{"text": "SECRET_EXPECTED_EVIDENCE_NEVER_RUNTIME"}],
                "qrels": [{"text": "SECRET_QRELS_NEVER_RUNTIME"}],
                "labels": ["SECRET_LABELS_NEVER_RUNTIME"],
                "gold_locator": "SECRET_GOLD_LOCATOR_NEVER_RUNTIME",
                "target_locator": "SECRET_TARGET_LOCATOR_NEVER_RUNTIME",
                "baseline_topk": [{"text": "SECRET_BASELINE_TOPK_NEVER_RUNTIME"}],
                "formula": "SECRET_FORMULA_NEVER_RUNTIME",
                "normalized_value": "SECRET_NORMALIZED_VALUE_NEVER_RUNTIME",
                "query_id": "SECRET_QUERY_ID_NEVER_RUNTIME",
                "row_id": "SECRET_ROW_ID_NEVER_RUNTIME",
                "target_id": "SECRET_TARGET_ID_NEVER_RUNTIME",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "xlsx-anchor-matrix",
                "generated_answer": "15,446,522명",
                "query_evidence_planner": planner,
                "query_anchor_classifier": actual_rag_eval._query_anchor_classifier_from_planner(query, planner),
                "raw_prompt_payload": {"secret": "SECRET_RAW_PROMPT_NEVER_RUNTIME"},
                "raw_response_payload": {"secret": "SECRET_RAW_RESPONSE_NEVER_RUNTIME"},
                "raw_tool_payload": {"secret": "SECRET_RAW_TOOL_NEVER_RUNTIME"},
                "tool_payload": {"secret": "SECRET_TOOL_PAYLOAD_NEVER_RUNTIME"},
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-xlsx",
                        "chunk_id": "chunk-xlsx",
                        "source_atom_id": "src-xlsx",
                        "evidence_bundle_id": "bundle-xlsx",
                        "source_family": "XLSX",
                        "granularity": "table_row",
                        "text": "2019년 2월 5호선 값은 15,446,522명입니다.",
                        "sheet": "2019년 2월",
                        "cell_range": "A1:C7",
                        "display_value": "15,446,522",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-xlsx",
                        "chunk_id": "chunk-xlsx",
                        "source_atom_id": "src-xlsx",
                        "evidence_bundle_id": "bundle-xlsx",
                        "source_family": "XLSX",
                        "text": "2019년 2월 5호선 값은 15,446,522명입니다.",
                    }
                ],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="residual_anchor_matrix",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False
    matrix = report["residual_anchor_matrix"]
    assert matrix["schema_version"] == "actual_rag_eval.residual_anchor_matrix.v1"
    assert matrix["report_only_diagnostic"] is True
    assert matrix["official_metric"] is False
    assert matrix["uses_gold_fields_as_runtime_inputs"] is False
    assert matrix["uses_expected_fields_as_runtime_inputs"] is False
    assert matrix["uses_qrels_or_labels_as_runtime_inputs"] is False
    assert matrix["row_count"] == 1
    row = matrix["rows"][0]
    assert row["item_id"] == "xlsx-anchor-matrix"
    assert row["source_family"] == "XLSX"
    assert row["query_shape"] == "table_lookup"
    assert row["retrieval_empty"] is False
    anchor_keys = {
        "query_anchor_present",
        "entity_anchor_present",
        "value_anchor_present",
        "date_or_number_anchor_present",
        "axis_anchor_present",
    }
    assert set(row["topk_anchor_presence"]) == anchor_keys
    assert set(row["selected_evidence_anchor_presence"]) == anchor_keys
    assert set(row["final_answer_anchor_presence"]) == anchor_keys
    assert row["topk_anchor_presence"]["query_anchor_present"] is True
    assert row["topk_anchor_presence"]["value_anchor_present"] is True
    assert row["topk_anchor_presence"]["axis_anchor_present"] is True
    assert row["selected_evidence_anchor_presence"]["value_anchor_present"] is True
    assert row["selected_evidence_anchor_presence"]["axis_anchor_present"] is True
    assert row["final_answer_anchor_presence"]["value_anchor_present"] is False
    assert row["final_answer_anchor_presence"]["axis_anchor_present"] is False
    assert "missing_validated_required_axes" in row["gate_validation_reasons"]
    assert row["residual_classification"] == "selected_evidence_has_value_missing_axis"
    encoded_matrix = json.dumps(matrix, ensure_ascii=False)
    assert "SECRET_EXPECTED_VALUE_NEVER_RUNTIME" not in encoded_matrix
    assert "SECRET_EXPECTED_EVIDENCE_NEVER_RUNTIME" not in encoded_matrix
    assert "SECRET_QRELS_NEVER_RUNTIME" not in encoded_matrix
    assert "SECRET_LABELS_NEVER_RUNTIME" not in encoded_matrix
    assert "SECRET_GOLD_LOCATOR_NEVER_RUNTIME" not in encoded_matrix
    assert "SECRET_TARGET_LOCATOR_NEVER_RUNTIME" not in encoded_matrix
    assert "SECRET_BASELINE_TOPK_NEVER_RUNTIME" not in encoded_matrix
    assert "SECRET_FORMULA_NEVER_RUNTIME" not in encoded_matrix
    assert "SECRET_NORMALIZED_VALUE_NEVER_RUNTIME" not in encoded_matrix
    assert "SECRET_QUERY_ID_NEVER_RUNTIME" not in encoded_matrix
    assert "SECRET_ROW_ID_NEVER_RUNTIME" not in encoded_matrix
    assert "SECRET_TARGET_ID_NEVER_RUNTIME" not in encoded_matrix
    encoded_report = json.dumps(report, ensure_ascii=False)
    assert "SECRET_RAW_PROMPT_NEVER_RUNTIME" not in encoded_report
    assert "SECRET_RAW_RESPONSE_NEVER_RUNTIME" not in encoded_report
    assert "SECRET_RAW_TOOL_NEVER_RUNTIME" not in encoded_report
    assert "SECRET_TOOL_PAYLOAD_NEVER_RUNTIME" not in encoded_report
    assert '"raw_prompt_payload":' not in encoded_report
    assert '"raw_response_payload":' not in encoded_report
    assert '"raw_tool_payload":' not in encoded_report
    assert '"tool_payload":' not in encoded_report


def test_source_native_axis_provenance_reports_axis_loss_stages(tmp_path: Path) -> None:
    dataset = tmp_path / "gold29_pdf_axis_probe.jsonl"
    context = tmp_path / "pdf_axis_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native_axis_provenance"
    write_jsonl(
        dataset,
        [
            {
                "id": "pdf-axis-provenance",
                "query": "2024년 영업이익 표의 값은 얼마야?",
                "answerability": "answerable",
                "track": "pdf_business_ocr_mm",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "pdf-axis-provenance",
                "generated_answer": "12.3억원",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-pdf",
                        "chunk_id": "chunk-pdf",
                        "source_atom_id": "src-pdf",
                        "evidence_bundle_id": "bundle-pdf",
                        "source_family": "PDF",
                        "granularity": "table_row",
                        "text": "2024년 영업이익 값은 12.3억원입니다.",
                        "page_number": 7,
                        "section_title": "재무 현황",
                        "table_caption": "영업이익 표",
                        "bbox": [10, 20, 200, 240],
                        "raw_locator": {
                            "page_number": 7,
                            "bbox": [10, 20, 200, 240],
                        },
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-pdf",
                        "chunk_id": "chunk-pdf",
                        "source_atom_id": "src-pdf",
                        "evidence_bundle_id": "bundle-pdf",
                        "source_family": "PDF",
                        "text": "2024년 영업이익 값은 12.3억원입니다.",
                        "page_number": 7,
                    }
                ],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="source_native_axis_provenance",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    provenance = report["source_native_axis_provenance"]
    assert provenance["schema_version"] == "actual_rag_eval.source_native_axis_provenance.v1"
    assert provenance["report_only_diagnostic"] is True
    assert provenance["official_metric"] is False
    assert provenance["stage_notes"]["source_registry_or_manifest"] == (
        "not_inspected_report_only_diagnostic_no_source_registry_or_manifest_runtime_input"
    )
    assert "page_number" in provenance["axis_fields"]
    assert "table_caption" in provenance["axis_fields"]
    row = provenance["rows"][0]
    assert row["item_id"] == "pdf-axis-provenance"
    assert row["source_family"] == "PDF"
    assert set(row["axis_presence_by_stage"]) == {
        "source_registry_or_manifest",
        "raw_locator_metadata",
        "weaviate_payload",
        "retrieved_context",
        "selected_evidence",
        "final_citation",
    }
    assert row["axis_presence_by_stage"]["source_registry_or_manifest"]["present"] == []
    assert row["axis_presence_by_stage"]["source_registry_or_manifest"]["stage_status"] == "not_inspected"
    assert row["axis_presence_by_stage"]["source_registry_or_manifest"]["not_inspected_reason"] == (
        "report_only_output_axis_loss_diagnostic_no_source_registry_or_manifest_runtime_input"
    )
    assert row["axis_presence_by_stage"]["raw_locator_metadata"]["present"] == []
    assert row["axis_presence_by_stage"]["retrieved_context"]["present"] == [
        "page_number",
        "section_title",
        "table_caption",
        "bbox",
    ]
    assert row["axis_presence_by_stage"]["selected_evidence"]["missing"] == [
        "row_label",
        "column_label",
    ]
    assert "page_number" in row["axis_presence_by_stage"]["final_citation"]["present"]
    assert row["axis_presence_by_stage"]["final_citation"]["missing"] == [
        "row_label",
        "column_label",
    ]


def test_xlsx_pdf_residual_breakdown_rejects_forbidden_shortcut_fields(tmp_path: Path) -> None:
    dataset = tmp_path / "forbidden_shortcuts.jsonl"
    context = tmp_path / "forbidden_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "xlsx_pdf_forbidden_shortcuts"
    forbidden_fields = {
        "expected_answer": "15,446,522명",
        "expected_evidence": [{"chunk_id": "gold-chunk", "text": "5호선 승차총승객수"}],
        "qrels": {"doc-xlsx": 1},
        "labels": ["answerable"],
        "query_id": "gold-query-id",
        "row_id": "gold-row-id",
        "target_id": "gold-target-id",
        "gold_locator": "Sheet1!B7",
        "target_locator": "Sheet1!B7",
        "normalized_value": "15446522",
        "formula": "=SUM(B1:B6)",
    }
    write_jsonl(
        dataset,
        [
            {
                "id": "forbidden-xlsx",
                "query": "2019년 2월 5호선 승차총승객수는 얼마야?",
                "answerability": "answerable",
                "track": "xlsx_business_structured",
                **forbidden_fields,
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "forbidden-xlsx",
                "generated_answer": "15,446,522명",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-xlsx",
                        "chunk_id": "chunk-xlsx",
                        "source_atom_id": "src-xlsx",
                        "evidence_bundle_id": "bundle-xlsx",
                        "source_family": "XLSX",
                        "text": "이 문장은 질의 축이나 값 근거를 제공하지 않습니다.",
                        **forbidden_fields,
                    }
                ],
                "citations": [],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="xlsx_pdf_forbidden_shortcuts",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    breakdown = report["xlsx_pdf_residual_breakdown"]
    row = breakdown["rows"][0]
    assert breakdown["uses_expected_fields"] is False
    assert breakdown["uses_gold_fields"] is False
    assert breakdown["uses_qrels"] is False
    assert breakdown["uses_labels"] is False
    assert breakdown["uses_ids"] is False
    assert breakdown["forbidden_shortcut_fields_used"] == []
    assert row["classification"] in {"candidate_present_anchor_missing", "selected_evidence_absent"}
    ignored_fields = set(row["forbidden_shortcut_fields_ignored"])
    assert set(forbidden_fields).issubset(ignored_fields)
    assert ignored_fields.issubset({*forbidden_fields, "answerability"})
    assert set(forbidden_fields).issubset(set(breakdown["forbidden_shortcut_fields_seen"]))
    assert row["forbidden_shortcut_fields_used"] == []
    row_payload = json.dumps(row, ensure_ascii=False)
    assert "15446522" not in row_payload
    assert "=SUM" not in row_payload
    assert "gold-query-id" not in row_payload
    assert output_file_names(output_dir) == ["report.json"]


def test_xlsx_pdf_residual_breakdown_excludes_supported_allowed_rows() -> None:
    row = {
        "id": "supported-xlsx",
        "generated_answer": "15,446,522명",
        "evidence_gate": {
            "evidence_package_status": "sufficient",
            "answer_gate_decision": "allow_answer",
            "validation_reasons": [],
            "retrieved_evidence_candidates": [
                {
                    "source_family": "XLSX",
                    "text": "2019년 2월 5호선 승차총승객수는 15,446,522명입니다.",
                    "sheet": "2019년 2월",
                    "cell_range": "A7:J7",
                    "cell": "F7",
                    "row_index_1based": "7",
                    "row_label": "5호선",
                    "column_label": "승차총승객수",
                    "target_column": "승차총승객수",
                    "header_path": "승하차 > 승차총승객수",
                    "table_id": "sheet-201902-main-table",
                }
            ],
            "selected_evidence": [
                {
                    "source_family": "XLSX",
                    "text": "2019년 2월 5호선 승차총승객수는 15,446,522명입니다.",
                    "sheet": "2019년 2월",
                    "cell_range": "A7:J7",
                    "cell": "F7",
                    "row_index_1based": "7",
                    "row_label": "5호선",
                    "column_label": "승차총승객수",
                    "target_column": "승차총승객수",
                    "header_path": "승하차 > 승차총승객수",
                    "table_id": "sheet-201902-main-table",
                }
            ],
        },
    }

    breakdown = actual_rag_eval.build_xlsx_pdf_residual_breakdown(items=[], rows=[row])

    assert breakdown["classification_counts"] == {}
    assert breakdown["rows"] == []
    assert breakdown["excluded_classification_counts"] == {"no_residual": 1}
    assert breakdown["uses_ids"] is False


def test_xlsx_pdf_residual_breakdown_does_not_use_item_id_track_fallback() -> None:
    item = actual_rag_eval.EvalItem(
        id="track-only-xlsx",
        query="2019년 2월 5호선 승차총승객수는 얼마야?",
        source_row={"track": "xlsx_business_structured"},
    )
    row = {
        "id": "track-only-xlsx",
        "generated_answer": "제공된 근거만으로는 답할 수 없습니다.",
        "evidence_gate": {
            "evidence_package_status": "insufficient",
            "answer_gate_decision": "block_answer",
            "validation_reasons": ["missing_query_anchor"],
            "retrieved_evidence_candidates": [],
            "selected_evidence": [],
        },
    }

    breakdown = actual_rag_eval.build_xlsx_pdf_residual_breakdown(items=[item], rows=[row])

    assert breakdown["uses_ids"] is False
    assert breakdown["classification_counts"] == {}
    assert breakdown["rows"] == []
    assert breakdown["excluded_classification_counts"] == {"not_xlsx_pdf": 1}


def test_xlsx_pdf_residual_breakdown_date_only_text_is_not_value_evidence() -> None:
    row = {
        "id": "xlsx-date-only",
        "generated_answer": "2019년 2월 5호선입니다.",
        "evidence_gate": {
            "evidence_package_status": "insufficient",
            "answer_gate_decision": "block_answer",
            "validation_reasons": ["missing_numeric_or_date_anchor"],
            "retrieved_evidence_candidates": [
                {
                    "source_family": "XLSX",
                    "text": "2019년 2월 5호선 행입니다.",
                    "sheet": "2019년 2월",
                    "row_label": "5호선",
                }
            ],
            "selected_evidence": [
                {
                    "source_family": "XLSX",
                    "text": "2019년 2월 5호선 행입니다.",
                    "sheet": "2019년 2월",
                    "row_label": "5호선",
                }
            ],
        },
    }

    breakdown = actual_rag_eval.build_xlsx_pdf_residual_breakdown(items=[], rows=[row])

    assert breakdown["classification_counts"] == {"selected_evidence_has_axis_missing_value": 1}
    assert breakdown["rows"][0]["classification"] == "selected_evidence_has_axis_missing_value"
    assert breakdown["rows"][0]["selected_evidence_value_anchor_present"] is False


def test_select_composer_evidence_uses_source_derived_xlsx_metadata_without_shortcuts() -> None:
    selected = select_composer_evidence(
        "2019년 2월 5호선 승차총승객수는 얼마야?",
        [
            {
                "doc_id": "doc-xlsx",
                "chunk_id": "chunk-row",
                "source_atom_id": "src-row",
                "evidence_bundle_id": "bundle-row",
                "source_family": "XLSX",
                "granularity": "table_row",
                "text": "15,446,522명",
                "sheet": "2019년 2월",
                "row_label": "5호선",
                "column_label": "승차총승객수",
                "source_workbook": "서울교통공사_월별_승하차.xlsx",
                "normalized_value": "15446522",
                "formula": "=SUM(A1:A3)",
            }
        ],
    )

    assert len(selected) == 1
    evidence = selected[0]
    assert evidence["source_atom_id"] == "src-row"
    metadata_text = evidence["composer_source_derived_metadata_text"]
    assert "2019년 2월" in metadata_text
    assert "5호선" in metadata_text
    assert "승차총승객수" in metadata_text
    assert "서울교통공사_월별_승하차.xlsx" not in metadata_text
    assert "15446522" not in metadata_text
    assert "=SUM" not in metadata_text
    assert evidence["composer_source_derived_metadata_fields"] == ["sheet", "row_label", "column_label"]
    assert evidence["composer_query_anchor_hits"] == ["2019년", "2월", "5호선", "승차총승객수"]


def test_selected_evidence_runtime_text_strips_embedded_workbook_filename_shortcuts() -> None:
    context = {
        "doc_id": "doc-xlsx",
        "chunk_id": "chunk-cell",
        "source_atom_id": "src-cell",
        "evidence_bundle_id": "bundle-cell",
        "source_family": "XLSX",
        "granularity": "cell",
        "text": (
            "sheet=일반현황 | range=A752:J801 | cell=G752 | "
            "row_label=장기요양기관이름=해뜨는요양원2 | "
            "column_label=시도 시군구 법정동명 | target_column=시도 시군구 법정동명 | "
            "value=국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 G752 | "
            "시도 시군구 법정동명=대구광역시 북구 복현동"
        ),
        "title": "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx",
        "workbook_id": "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx",
        "workbook_version_id": "docv-forbidden-workbook-version",
        "sheet": "일반현황",
        "cell_range": "A752:J801",
        "cell": "G752",
        "row_label": "장기요양기관이름=해뜨는요양원2",
        "target_column": "시도 시군구 법정동명",
        "display_value": "대구광역시 북구 복현동",
    }

    validation = validate_evidence_package_for_gate(
        {
            "query": "해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?",
            "generated_answer": "대구광역시 북구 복현동",
            "retrieved_contexts": [context],
            "citations": [],
        }
    )
    answer = actual_rag_eval._selected_evidence_answer(
        query="해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?",
        selected_evidence=validation["selected_evidence"],
        citation_format="markdown-portfolio",
    )
    serialized = json.dumps(
        {
            "selected_evidence": validation["selected_evidence"],
            "answer": answer,
        },
        ensure_ascii=False,
    )

    assert validation["selected_evidence"]
    assert "대구광역시 북구 복현동" in serialized
    assert "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx" not in serialized
    assert ".xlsx" not in serialized
    assert "workbook_id" not in serialized
    assert "workbook_version_id" not in serialized
    assert "title" not in serialized

    public_output = actual_rag_eval._item_output(
        actual_rag_eval.EvalItem(
            id="xlsx-runtime-safe-output",
            query="해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?",
        ),
        generated_answer="대구광역시 북구 복현동",
        contexts=[context],
        citations=[context],
    )
    public_serialized = json.dumps(public_output, ensure_ascii=False)

    assert "대구광역시 북구 복현동" in public_serialized
    assert "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx" not in public_serialized
    assert ".xlsx" not in public_serialized
    assert "workbook_id" not in public_serialized
    assert "workbook_version_id" not in public_serialized
    assert "title" not in public_serialized


def test_evidence_gate_uses_source_owned_xlsx_display_value_as_value_axis() -> None:
    validation = validate_evidence_package_for_gate(
        {
            "query": "2019년 2월 5호선 승차총승객수",
            "generated_answer": "15,446,522명",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-xlsx",
                    "chunk_id": "chunk-display-value",
                    "source_atom_id": "src-display-value",
                    "evidence_bundle_id": "bundle-display-value",
                    "source_family": "XLSX",
                    "granularity": "table_row",
                    "text": "2019년 2월 5호선 승차총승객수 행입니다.",
                    "sheet": "2019년 2월",
                    "cell_range": "A7:J7",
                    "row_label": "5호선",
                    "target_column": "승차총승객수",
                    "header_path": "승하차 > 승차총승객수",
                    "table_id": "sheet-201902-main-table",
                    "display_value": "15,446,522명",
                }
            ],
            "citations": [],
        }
    )

    assert validation["evidence_package_status"] == "sufficient"
    assert validation["missing_answer_anchors"] == []
    assert "missing_numeric_or_date_anchor" not in validation["validation_reasons"]
    selected = validation["selected_evidence"][0]
    assert selected["display_value"] == "15,446,522명"
    assert "display_value=15,446,522명" in actual_rag_eval.source_derived_evidence_metadata(selected)[0]


def test_selected_evidence_answer_discipline_allows_clean_supported_core() -> None:
    discipline = actual_rag_eval._selected_evidence_answer_discipline(
        query="Where is Apollo HQ?",
        answer="Apollo HQ is in Seoul.",
        selected_evidence=[
            {
                "doc_id": "doc-hq",
                "chunk_id": "chunk-hq",
                "source_atom_id": "src-hq",
                "evidence_bundle_id": "bundle-hq",
                "text": "Apollo HQ is in Seoul.",
            }
        ],
        cited_evidence_ids=["bundle-hq"],
    )

    assert discipline["status"] == "clean_supported"
    assert discipline["core_answer_supported"] is True
    assert discipline["unsupported_extra_detail"] is False
    assert discipline["query_irrelevant_supported_detail"] is False
    assert discipline["fallback_reason"] == ""
    assert discipline["unsupported_extra_preview"] == ""
    assert discipline["query_irrelevant_preview"] == ""
    assert discipline["input_policy"] == "query_text_selected_evidence_answer_only_no_gold_qrels_labels_ids_or_baseline"


def test_selected_evidence_answer_discipline_allows_korean_source_native_rephrasing() -> None:
    discipline = actual_rag_eval._selected_evidence_answer_discipline(
        query="2019년 2월 5호선 승차총승객수는 얼마야?",
        answer="2019년 2월 5호선의 승차총승객수는 15,446,522명입니다.",
        selected_evidence=[
            {
                "doc_id": "doc-xlsx",
                "chunk_id": "chunk-row",
                "source_atom_id": "src-xlsx",
                "evidence_bundle_id": "bundle-xlsx",
                "source_family": "XLSX",
                "text": "2019년 2월 5호선 승차총승객수 행입니다.",
                "sheet": "2019년 2월",
                "row_label": "5호선",
                "target_column": "승차총승객수",
                "display_value": "15,446,522명",
            }
        ],
        cited_evidence_ids=["bundle-xlsx"],
    )

    assert discipline["status"] == "clean_supported"
    assert discipline["core_answer_supported"] is True
    assert discipline["unsupported_extra_detail"] is False
    assert discipline["query_irrelevant_supported_detail"] is False
    assert discipline["fallback_reason"] == ""


def test_selected_evidence_answer_discipline_allows_source_native_display_value_focus() -> None:
    discipline = actual_rag_eval._selected_evidence_answer_discipline(
        query="2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 무엇입니까?",
        answer="대구광역시 수성구 파동로51길 96 (파동)",
        selected_evidence=[
            {
                "doc_id": "doc-xlsx-address",
                "chunk_id": "chunk-address",
                "source_atom_id": "src-address",
                "evidence_bundle_id": "bundle-address",
                "source_family": "XLSX",
                "text": (
                    "row_label=해오름요양원 | target_column=기관별 상세주소 | "
                    "display_value=대구광역시 수성구 파동로51길 96 (파동) | source_date_alias=2012년 3월"
                ),
                "row_label": "해오름요양원",
                "target_column": "기관별 상세주소",
                "header": "기관별 상세주소",
                "display_value": "대구광역시 수성구 파동로51길 96 (파동)",
            }
        ],
        cited_evidence_ids=["bundle-address"],
    )

    assert discipline["status"] == "clean_supported"
    assert discipline["core_answer_supported"] is True
    assert discipline["query_irrelevant_supported_detail"] is False


def test_selected_evidence_answer_discipline_rejects_off_focus_source_native_display_value() -> None:
    discipline = actual_rag_eval._selected_evidence_answer_discipline(
        query="What are Mika's age and birthday?",
        answer="160cm",
        selected_evidence=[
            {
                "doc_id": "doc-profile-xlsx",
                "chunk_id": "chunk-profile-xlsx",
                "source_atom_id": "src-profile-xlsx",
                "evidence_bundle_id": "bundle-profile-xlsx",
                "source_family": "XLSX",
                "text": "age=17 | birthday=May 8 | height=160cm",
                "row_label": "Mika",
                "target_column": "height",
                "header": "height",
                "display_value": "160cm",
            }
        ],
        cited_evidence_ids=["bundle-profile-xlsx"],
    )

    assert discipline["status"] == "true_insufficient_evidence"
    assert discipline["core_answer_supported"] is False
    assert discipline["query_irrelevant_supported_detail"] is False


def test_selected_evidence_answer_discipline_flags_unsupported_extra_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    direct = actual_rag_eval._selected_evidence_answer_discipline(
        query="Where is Apollo HQ?",
        answer="Apollo HQ is in Seoul. CEO is Dana.",
        selected_evidence=[
            {
                "doc_id": "doc-hq",
                "chunk_id": "chunk-hq",
                "source_atom_id": "src-hq",
                "evidence_bundle_id": "bundle-hq",
                "text": "Apollo HQ is in Seoul.",
            }
        ],
        cited_evidence_ids=["bundle-hq"],
    )
    assert direct["status"] == "supported_core_with_unsupported_extra"
    assert direct["core_answer_supported"] is True
    assert direct["unsupported_extra_detail"] is True
    assert "Dana" in direct["unsupported_extra_preview"]

    dataset = tmp_path / "selected_local_llm_unsupported_extra_gold.jsonl"
    context = tmp_path / "selected_local_llm_unsupported_extra_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_local_llm_unsupported_extra"
    write_jsonl(dataset, [{"id": "q-extra", "query": "Where is Apollo HQ?", "answerability": "answerable"}])
    write_jsonl(
        context,
        [
            {
                "id": "q-extra",
                "generated_answer": "legacy answer must not drive discipline",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [],
            }
        ],
    )
    calls: list[str] = []

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**kwargs: object) -> tuple[dict, dict]:
        calls.append(str(kwargs["prompt"]))
        if len(calls) == 1:
            return (
                {"answer": "Apollo HQ is in Seoul. CEO is Dana.", "citation_evidence_ids": ["bundle-hq"]},
                {
                    "raw_response_sha256": "sha256:unsupported-extra",
                    "raw_response": "SECRET_UNSUPPORTED_EXTRA_RAW_RESPONSE",
                    "raw_prompt_payload": {"secret": "SECRET_UNSUPPORTED_EXTRA_PROMPT"},
                },
            )
        return (
            {"answer": "Apollo HQ is in Seoul.", "citation_evidence_ids": ["bundle-hq"]},
            {
                "raw_response_sha256": "sha256:clean-retry",
                "raw_response": "SECRET_RETRY_RAW_RESPONSE",
                "raw_prompt_payload": {"secret": "SECRET_RETRY_PROMPT"},
            },
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_local_llm_unsupported_extra",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-local-llm-v1",
        selected_evidence_citation_format="evidence-id",
        selected_evidence_composer_retry_mode="bounded-once",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    retry = row["answer_composer"]["retry"]
    assert len(calls) == 2
    assert row["generated_answer"] == "Apollo HQ is in Seoul."
    assert row["answer_gate_decision"] == "allow_answer"
    assert row["answer_composer"]["answer_discipline"]["status"] == "clean_supported"
    assert retry["trigger"] == "answer_discipline_supported_core_with_unsupported_extra"
    assert retry["initial_answer_discipline_status"] == "supported_core_with_unsupported_extra"
    assert report["generator_config"]["unsupported_extra_detail_count"] == 1
    assert report["generator_config"]["local_llm_fallback_reason_counts"] == {
        "answer_discipline_supported_core_with_unsupported_extra": 1
    }
    encoded_report = json.dumps(report, ensure_ascii=False)
    assert "SECRET_UNSUPPORTED_EXTRA_RAW_RESPONSE" not in encoded_report
    assert "SECRET_UNSUPPORTED_EXTRA_PROMPT" not in encoded_report
    assert "SECRET_RETRY_RAW_RESPONSE" not in encoded_report
    assert "SECRET_RETRY_PROMPT" not in encoded_report
    assert '"raw_prompt_payload":' not in encoded_report
    assert '"raw_response":' not in encoded_report


def test_selected_evidence_answer_discipline_flags_query_irrelevant_supported_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence_text = (
        "Mika profile: age 17. Birthday May 8. Height 160cm. Blood type B. "
        "Weapon rifle. Favorite food curry."
    )
    direct = actual_rag_eval._selected_evidence_answer_discipline(
        query="What are Mika's age and birthday?",
        answer="Mika is 17, birthday May 8, height 160cm, blood type B, weapon rifle, and favorite food curry.",
        selected_evidence=[
            {
                "doc_id": "doc-mika",
                "chunk_id": "chunk-profile",
                "source_atom_id": "src-mika",
                "evidence_bundle_id": "bundle-mika",
                "text": evidence_text,
            }
        ],
        cited_evidence_ids=["bundle-mika"],
    )
    assert direct["status"] == "query_irrelevant_supported_detail"
    assert direct["core_answer_supported"] is True
    assert direct["query_irrelevant_supported_detail"] is True
    assert "height" in direct["query_irrelevant_preview"].lower()

    dataset = tmp_path / "selected_local_llm_query_irrelevant_gold.jsonl"
    context = tmp_path / "selected_local_llm_query_irrelevant_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_local_llm_query_irrelevant"
    write_jsonl(
        dataset,
        [{"id": "q-focus", "query": "What are Mika's age and birthday?", "answerability": "answerable"}],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-focus",
                "generated_answer": "legacy profile summary must not drive discipline",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-mika",
                        "chunk_id": "chunk-profile",
                        "source_atom_id": "src-mika",
                        "evidence_bundle_id": "bundle-mika",
                        "source_family": "TEXT",
                        "text": evidence_text,
                    }
                ],
                "citations": [],
            }
        ],
    )
    calls: list[str] = []

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**kwargs: object) -> tuple[dict, dict]:
        calls.append(str(kwargs["prompt"]))
        if len(calls) == 1:
            return (
                {
                    "answer": (
                        "Mika is 17, birthday May 8, height 160cm, blood type B, "
                        "weapon rifle, and favorite food curry."
                    ),
                    "citation_evidence_ids": ["bundle-mika"],
                },
                {"raw_response_sha256": "sha256:query-irrelevant"},
            )
        return (
            {"answer": "Mika is 17 and her birthday is May 8.", "citation_evidence_ids": ["bundle-mika"]},
            {"raw_response_sha256": "sha256:focused-retry"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_local_llm_query_irrelevant",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-local-llm-v1",
        selected_evidence_citation_format="evidence-id",
        selected_evidence_composer_retry_mode="bounded-once",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    retry = row["answer_composer"]["retry"]
    assert len(calls) == 2
    assert row["generated_answer"] == "Mika is 17 and her birthday is May 8."
    assert "height" not in row["generated_answer"].lower()
    assert "blood type" not in row["generated_answer"].lower()
    assert row["answer_composer"]["answer_discipline"]["status"] == "clean_supported"
    assert retry["trigger"] == "answer_discipline_query_irrelevant_supported_detail"
    assert retry["initial_answer_discipline_status"] == "query_irrelevant_supported_detail"
    assert report["generator_config"]["query_irrelevant_supported_detail_count"] == 1


def test_selected_evidence_local_llm_concise_answer_not_replaced_by_overexpanded_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "selected_local_llm_concise_gold.jsonl"
    context = tmp_path / "selected_local_llm_concise_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_local_llm_concise"
    write_jsonl(dataset, [{"id": "q-concise", "query": "Where is Apollo HQ?", "answerability": "answerable"}])
    write_jsonl(
        context,
        [
            {
                "id": "q-concise",
                "generated_answer": "legacy profile summary",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "text": "Apollo HQ is in Seoul. Apollo also has a regional office in Busan.",
                    }
                ],
                "citations": [],
            }
        ],
    )
    call_count = 0

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        nonlocal call_count
        call_count += 1
        return (
            {"answer": "Apollo HQ is in Seoul.", "citation_evidence_ids": ["bundle-hq"]},
            {"raw_response_sha256": "sha256:concise"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_local_llm_concise",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-local-llm-v1",
        selected_evidence_composer_retry_mode="bounded-once",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    assert call_count == 1
    assert row["generated_answer"] == "Apollo HQ is in Seoul."
    assert "Busan" not in row["generated_answer"]
    assert row["answer_composer"]["local_llm_fallback_used"] is False
    assert row["answer_composer"]["local_llm"]["status"] == "generated"
    assert row["answer_composer"]["retry"]["status"] == "not_triggered"
    assert row["answer_composer"]["retry"]["reason"] == "answer_discipline_clean_supported"
    assert report["generator_config"]["local_llm_acceptance_rate"] == 1.0
    assert report["generator_config"]["local_llm_rejected_then_deterministic_overexpanded_count"] == 0


def test_selected_evidence_local_llm_clean_gate_blocked_answer_uses_gate_aligned_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "selected_local_llm_gate_aligned_gold.jsonl"
    context = tmp_path / "selected_local_llm_gate_aligned_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_local_llm_gate_aligned"
    evidence_text = "타로를 실제로 만나기 위해 도쿄로 향한 미라는 역에 도착했다."
    write_jsonl(
        dataset,
        [
            {
                "id": "q-korean-gate-aligned",
                "query": "미라는 타로를 만나려고 어디로 향했어",
                "answerability": "answerable",
                "expected_answer": "SECRET_GATE_ALIGNED_EXPECTED_ANSWER_NEVER_GENERATE",
                "expected_evidence": [{"text": "SECRET_GATE_ALIGNED_EXPECTED_EVIDENCE_NEVER_GENERATE"}],
                "qrels": {"SECRET_GATE_ALIGNED_QREL_NEVER_GENERATE": 1},
                "labels": ["SECRET_GATE_ALIGNED_LABEL_NEVER_GENERATE"],
                "row_id": "SECRET_GATE_ALIGNED_ROW_ID_NEVER_RUNTIME",
                "target_id": "SECRET_GATE_ALIGNED_TARGET_ID_NEVER_RUNTIME",
                "baseline_topk": ["SECRET_GATE_ALIGNED_BASELINE_TOPK_NEVER_RUNTIME"],
                "silver_metadata": "SECRET_GATE_ALIGNED_SILVER_NEVER_RUNTIME",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-korean-gate-aligned",
                "generated_answer": "SECRET_GATE_ALIGNED_LEGACY_OUTPUT_NEVER_GENERATE",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-korean",
                        "chunk_id": "chunk-korean",
                        "source_atom_id": "src-korean",
                        "evidence_bundle_id": "bundle-korean",
                        "source_family": "TEXT",
                        "text": evidence_text,
                    }
                ],
                "citations": [],
            }
        ],
    )
    calls: list[str] = []

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**kwargs: object) -> tuple[dict, dict]:
        calls.append(str(kwargs.get("prompt", "")))
        return (
            {"answer": "미라는 타로를 만나려고 도쿄로 향했다.", "citation_evidence_ids": ["bundle-korean"]},
            {
                "raw_response_sha256": "sha256:gate-aligned",
                "raw_prompt_payload": {"secret": "SECRET_GATE_ALIGNED_RAW_PROMPT"},
                "rawPromptPayload": "SECRET_GATE_ALIGNED_RAW_PROMPT_CAMEL",
                "prompt": "SECRET_GATE_ALIGNED_PROMPT_FIELD",
                "raw_response": "SECRET_GATE_ALIGNED_RAW_RESPONSE",
                "raw_response_payload": "SECRET_GATE_ALIGNED_RAW_RESPONSE_PAYLOAD",
                "rawResponsePayload": "SECRET_GATE_ALIGNED_RAW_RESPONSE_PAYLOAD_CAMEL",
            },
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_local_llm_gate_aligned",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-local-llm-v1",
        selected_evidence_citation_format="evidence-id",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    composer = row["answer_composer"]
    config = report["generator_config"]
    assert len(calls) == 1
    assert row["generated_answer"] == evidence_text
    assert "도쿄로 향한" in row["generated_answer"]
    assert "도쿄로 향했다" not in row["generated_answer"]
    assert row["answer_gate_decision"] == "allow_answer"
    assert row["answer_modified_by_gate"] is False
    assert row["unsupported_answer_blocked"] is False
    assert row["evidence_gate"]["evidence_package_status"] == "sufficient"
    assert composer["local_llm"]["status"] == "gate_aligned_deterministic_fallback"
    assert composer["local_llm"]["fallback_reason"] == "local_llm_clean_answer_gate_insufficient"
    assert composer["local_llm_fallback_used"] is True
    assert composer["local_llm_gate_aligned_fallback_used"] is True
    assert composer["answer_rendering_policy"] == "source_native_selected_evidence_sentence_gate_aligned"
    assert composer["initial_evidence_package_status"] == "insufficient"
    assert composer["initial_answer_gate_decision"] == "block_unsupported_answer"
    assert "missing_entity_anchor" in composer["initial_validation_reasons"]
    assert "향했다" in composer["initial_missing_answer_anchors"]
    assert composer["gate_aligned_evidence_package_status"] == "sufficient"
    assert composer["initial_answer_discipline"]["status"] == "clean_supported"
    assert composer["answer_discipline"]["status"] == "clean_supported"
    assert output_file_names(output_dir) == ["report.json"]
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False
    assert "prompt" not in composer["local_llm"]
    assert "raw_response" not in composer["local_llm"]
    assert "raw_prompt_payload" not in composer["local_llm"]
    assert "raw_response_payload" not in composer["local_llm"]
    assert config["local_llm_gate_aligned_fallback_count"] == 1
    assert config["local_llm_status_counts"] == {"gate_aligned_deterministic_fallback": 1}
    assert config["local_llm_composer_fallback_used"] is True
    assert config["local_llm_accepted_clean_count"] == 0
    assert config["local_llm_acceptance_rate"] == 0.0
    assert config["local_llm_clean_answer_gate_blocked_count"] == 0
    assert report["evidence_gate"]["allowed_answer_count"] == 1
    assert report["evidence_gate"]["unsupported_answer_blocked_count"] == 0
    decomposition = report["selected_evidence_failure_decomposition"]
    assert decomposition["gate_blocked_clean_local_llm_count"] == 0
    assert decomposition["true_insufficient_evidence_count"] == 0
    assert config["expected_answer_used_for_generation"] is False
    assert config["expected_evidence_used_for_generation"] is False
    assert config["local_llm_prompt_payload_written"] is False
    assert config["local_llm_raw_response_payload_written"] is False
    assert composer["uses_expected_answer"] is False
    assert composer["uses_expected_evidence"] is False
    assert composer["uses_gold_fields"] is False
    assert composer["uses_qrels"] is False
    assert composer["uses_labels"] is False
    assert composer["uses_query_or_row_or_target_ids"] is False
    assert composer["uses_baseline_topk_or_legacy_outputs"] is False
    prompt_text = "\n".join(calls)
    encoded_report = json.dumps(report, ensure_ascii=False)
    generated_and_composer = json.dumps(
        {"generated_answer": row["generated_answer"], "answer_composer": composer},
        ensure_ascii=False,
    )
    protected_runtime_sentinels = [
        "SECRET_GATE_ALIGNED_EXPECTED_ANSWER_NEVER_GENERATE",
        "SECRET_GATE_ALIGNED_EXPECTED_EVIDENCE_NEVER_GENERATE",
        "SECRET_GATE_ALIGNED_QREL_NEVER_GENERATE",
        "SECRET_GATE_ALIGNED_LABEL_NEVER_GENERATE",
        "SECRET_GATE_ALIGNED_ROW_ID_NEVER_RUNTIME",
        "SECRET_GATE_ALIGNED_TARGET_ID_NEVER_RUNTIME",
        "SECRET_GATE_ALIGNED_BASELINE_TOPK_NEVER_RUNTIME",
        "SECRET_GATE_ALIGNED_SILVER_NEVER_RUNTIME",
        "SECRET_GATE_ALIGNED_LEGACY_OUTPUT_NEVER_GENERATE",
    ]
    for sentinel in protected_runtime_sentinels:
        assert sentinel not in prompt_text
        assert sentinel not in generated_and_composer
    for sentinel in (
        "SECRET_GATE_ALIGNED_RAW_PROMPT",
        "SECRET_GATE_ALIGNED_RAW_PROMPT_CAMEL",
        "SECRET_GATE_ALIGNED_PROMPT_FIELD",
        "SECRET_GATE_ALIGNED_RAW_RESPONSE",
        "SECRET_GATE_ALIGNED_RAW_RESPONSE_PAYLOAD",
        "SECRET_GATE_ALIGNED_RAW_RESPONSE_PAYLOAD_CAMEL",
    ):
        assert sentinel not in encoded_report
    assert '"raw_prompt_payload":' not in encoded_report
    assert '"rawPromptPayload":' not in encoded_report
    assert '"raw_response":' not in encoded_report
    assert '"raw_response_payload":' not in encoded_report
    assert '"rawResponsePayload":' not in encoded_report


def test_selected_evidence_local_llm_clean_rejected_output_uses_focused_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "selected_local_llm_clean_rejected_gold.jsonl"
    context = tmp_path / "selected_local_llm_clean_rejected_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_local_llm_clean_rejected"
    evidence_text = (
        "Mika profile: age 17. Birthday May 8. Height 160cm. Blood type B. "
        "Weapon rifle. Favorite food curry."
    )
    write_jsonl(
        dataset,
        [
            {
                "id": "q-clean-rejected",
                "query": "What are Mika's age and birthday?",
                "answerability": "answerable",
                "expected_answer": "SECRET_GOLD_ANSWER_NEVER_GENERATE",
                "expected_evidence": [{"text": "SECRET_GOLD_EVIDENCE_NEVER_GENERATE"}],
                "qrels": {"SECRET_QREL_DOC_NEVER_GENERATE": 1},
                "labels": ["SECRET_LABEL_NEVER_GENERATE"],
            }
        ],
    )
    prompts: list[str] = []
    write_jsonl(
        context,
        [
            {
                "id": "q-clean-rejected",
                "generated_answer": "legacy profile summary must not drive discipline",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-mika",
                        "chunk_id": "chunk-profile",
                        "source_atom_id": "src-mika",
                        "evidence_bundle_id": "bundle-mika",
                        "source_family": "TEXT",
                        "text": evidence_text,
                    }
                ],
                "citations": [],
            }
        ],
    )

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**kwargs: object) -> tuple[dict, dict]:
        prompts.append(str(kwargs.get("prompt")))
        return (
            {"answer": "Mika is 17 and her birthday is May 8.", "citation_evidence_ids": ["bundle-mika"]},
            {
                "raw_response_sha256": "sha256:clean-rejected",
                "raw_prompt_payload": {"secret": "SECRET_CLEAN_REJECTED_PROMPT"},
                "raw_response": "SECRET_CLEAN_REJECTED_RAW_RESPONSE",
            },
        )

    original_gate_select = actual_rag_eval._gate_select_evidence

    def reject_clean_local_answer(**kwargs: object) -> list[dict[str, object]]:
        if kwargs.get("answer") == "Mika is 17 and her birthday is May 8.":
            return []
        return original_gate_select(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)
    monkeypatch.setattr(actual_rag_eval, "_gate_select_evidence", reject_clean_local_answer)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_local_llm_clean_rejected",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-local-llm-v1",
        selected_evidence_citation_format="evidence-id",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    composer = row["answer_composer"]
    config = report["generator_config"]
    assert composer["local_llm"]["status"] == "unsupported_or_empty_deterministic_fallback"
    assert composer["initial_answer_discipline"]["status"] == "clean_supported"
    assert composer["answer_discipline"]["status"] == "clean_supported"
    assert "age 17" in row["generated_answer"]
    assert "Birthday May 8" in row["generated_answer"]
    assert "height" not in row["generated_answer"].lower()
    assert "blood type" not in row["generated_answer"].lower()
    assert config["local_llm_rejected_then_deterministic_overexpanded_count"] == 0
    assert config["query_irrelevant_supported_detail_count"] == 0
    assert config["answer_overexpansion_count_diagnostic"] == 0
    assert config["local_llm_clean_answer_output_rejected_count"] == 1
    assert config["local_llm_final_answer_discipline_status_counts"] == {"clean_supported": 1}
    assert config["expected_answer_used_for_generation"] is False
    assert config["expected_evidence_used_for_generation"] is False
    assert config["local_llm_prompt_payload_written"] is False
    assert config["local_llm_raw_response_payload_written"] is False
    assert composer["uses_expected_answer"] is False
    assert composer["uses_expected_evidence"] is False
    assert composer["uses_gold_fields"] is False
    assert composer["uses_qrels"] is False
    assert composer["uses_labels"] is False
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False
    prompt_text = "\n".join(prompts)
    assert "SECRET_GOLD_ANSWER_NEVER_GENERATE" not in prompt_text
    assert "SECRET_GOLD_EVIDENCE_NEVER_GENERATE" not in prompt_text
    assert "SECRET_QREL_DOC_NEVER_GENERATE" not in prompt_text
    assert "SECRET_LABEL_NEVER_GENERATE" not in prompt_text
    generated_and_composer = json.dumps(
        {"generated_answer": row["generated_answer"], "answer_composer": composer},
        ensure_ascii=False,
    )
    assert "SECRET_GOLD_ANSWER_NEVER_GENERATE" not in generated_and_composer
    assert "SECRET_GOLD_EVIDENCE_NEVER_GENERATE" not in generated_and_composer
    assert "SECRET_QREL_DOC_NEVER_GENERATE" not in generated_and_composer
    assert "SECRET_LABEL_NEVER_GENERATE" not in generated_and_composer
    encoded_report = json.dumps(report, ensure_ascii=False)
    assert "SECRET_CLEAN_REJECTED_PROMPT" not in encoded_report
    assert "SECRET_CLEAN_REJECTED_RAW_RESPONSE" not in encoded_report
    assert '"raw_prompt_payload":' not in encoded_report
    assert '"raw_response":' not in encoded_report


def test_run_eval_selected_evidence_local_llm_answer_discipline_metrics_are_reported_without_raw_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "selected_local_llm_discipline_metrics_gold.jsonl"
    context = tmp_path / "selected_local_llm_discipline_metrics_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_local_llm_discipline_metrics"
    write_jsonl(dataset, [{"id": "q-metrics", "query": "Where is Apollo HQ?", "answerability": "answerable"}])
    write_jsonl(
        context,
        [
            {
                "id": "q-metrics",
                "generated_answer": "legacy answer",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [],
            }
        ],
    )

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {"answer": "Apollo HQ is in Seoul.", "citation_evidence_ids": ["bundle-hq"]},
            {"raw_response_sha256": "sha256:metrics"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_local_llm_discipline_metrics",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        answer_composer="selected-evidence-local-llm-v1",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    config = report["generator_config"]
    discipline = report["items"][0]["answer_composer"]["answer_discipline"]
    assert discipline["status"] == "clean_supported"
    assert config["local_llm_acceptance_rate"] == 1.0
    assert config["local_llm_fallback_reason_counts"] == {}
    assert config["answer_overexpansion_count_diagnostic"] == 0
    assert config["unsupported_extra_detail_count"] == 0
    assert config["query_irrelevant_supported_detail_count"] == 0
    assert config["local_llm_rejected_then_deterministic_overexpanded_count"] == 0
    assert config["citation_id_mismatch_or_missing_count"] == 0
    assert config["anchor_morphology_false_negative_count"] == 0
    assert config["local_llm_prompt_payload_written"] is False
    assert config["local_llm_raw_response_payload_written"] is False
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False
    encoded_report = json.dumps(report, ensure_ascii=False)
    assert '"raw_prompt_payload":' not in encoded_report
    assert '"raw_response_payload":' not in encoded_report
    assert '"prompt":' not in encoded_report
    assert '"raw_response":' not in encoded_report


def test_selected_evidence_failure_decomposition_separates_retrieval_evidence_gate_and_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "selected_evidence_failure_decomposition_gold.jsonl"
    context = tmp_path / "selected_evidence_failure_decomposition_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_evidence_failure_decomposition"
    write_jsonl(
        dataset,
        [
            {"id": "q-retrieval-empty", "query": "Where is Apollo HQ?", "answerability": "answerable"},
            {"id": "q-selected-absent", "query": "Where is Borealis HQ?", "answerability": "answerable"},
            {"id": "q-anchor-missing", "query": "Where is Apollo HQ?", "answerability": "answerable"},
        ],
    )
    write_jsonl(
        context,
        [
            {"id": "q-retrieval-empty", "generated_answer": "", "retrieved_contexts": [], "citations": []},
            {
                "id": "q-selected-absent",
                "generated_answer": "legacy answer must not drive decomposition",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-related",
                        "chunk_id": "chunk-related",
                        "source_atom_id": "src-related",
                        "evidence_bundle_id": "bundle-related",
                        "source_family": "TEXT",
                        "text": "A weather bulletin says heavy rain is expected tomorrow.",
                    }
                ],
                "citations": [],
            },
            {
                "id": "q-anchor-missing",
                "generated_answer": "legacy answer must not drive decomposition",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "XLSX",
                        "granularity": "table_row",
                        "text": "target_column=headquarters | display_value=Seoul",
                        "target_column": "headquarters",
                        "display_value": "Seoul",
                    }
                ],
                "citations": [],
            },
        ],
    )

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**kwargs: object) -> tuple[dict, dict]:
        prompt = str(kwargs.get("prompt", ""))
        if "target_column=headquarters" in prompt:
            return ({"answer": "Apollo HQ is in Seoul.", "citation_evidence_ids": ["bundle-hq"]}, {})
        return ({"answer": "", "citation_evidence_ids": []}, {})

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_evidence_failure_decomposition",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-local-llm-v1",
        selected_evidence_citation_format="evidence-id",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    decomposition = report["selected_evidence_failure_decomposition"]
    assert decomposition["schema_version"] == "selected_evidence_failure_decomposition_v1"
    assert decomposition["report_only_diagnostic"] is True
    assert decomposition["official_metric"] is False
    assert decomposition["uses_expected_fields_as_runtime_inputs"] is False
    assert decomposition["post_run_expected_evidence_diagnostics_used"] is False
    assert decomposition["uses_gold_fields"] is False
    assert decomposition["uses_qrels"] is False
    assert decomposition["uses_labels"] is False
    assert decomposition["uses_ids_as_runtime_inputs"] is False
    assert decomposition["retrieval_empty_count"] == 1
    assert decomposition["selected_evidence_absent_count"] >= 1
    assert decomposition["selected_evidence_value_present_anchor_missing_count"] >= 1
    assert decomposition["true_insufficient_evidence_count"] >= 1
    row_classes = {row["id"]: set(row["classifications"]) for row in decomposition["rows"]}
    assert "retrieval_empty" in row_classes["q-retrieval-empty"]
    assert any("selected_evidence_absent" in classes for classes in row_classes.values())
    assert "selected_evidence_value_present_anchor_missing" in row_classes["q-anchor-missing"]


def test_selected_evidence_failure_decomposition_does_not_use_gold_expected_qrels_labels_or_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "selected_evidence_forbidden_sentinel_gold.jsonl"
    context = tmp_path / "selected_evidence_forbidden_sentinel_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_evidence_forbidden_sentinel"
    write_jsonl(
        dataset,
        [
            {
                "id": "SECRET_ROW_ID_NEVER_RUNTIME",
                "query": "Where is Apollo HQ?",
                "answerability": "answerable",
                "expected_answer": "SECRET_EXPECTED_ANSWER_NEVER_RUNTIME",
                "expected_evidence": [{"text": "SECRET_EXPECTED_EVIDENCE_NEVER_RUNTIME", "required": True}],
                "qrels": {"SECRET_QREL_NEVER_RUNTIME": 1},
                "labels": ["SECRET_LABEL_NEVER_RUNTIME"],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "SECRET_ROW_ID_NEVER_RUNTIME",
                "generated_answer": "legacy answer",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [],
            }
        ],
    )
    prompts: list[str] = []

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**kwargs: object) -> tuple[dict, dict]:
        prompts.append(str(kwargs.get("prompt", "")))
        return (
            {"answer": "Apollo HQ is in Seoul.", "citation_evidence_ids": ["bundle-hq"]},
            {"raw_response_sha256": "sha256:sentinel"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_evidence_forbidden_sentinel",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        answer_composer="selected-evidence-local-llm-v1",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    decomposition = report["selected_evidence_failure_decomposition"]
    audit = report["overfit_and_heuristic_audit"]
    assert decomposition["uses_expected_fields_as_runtime_inputs"] is False
    assert decomposition["post_run_expected_evidence_diagnostics_used"] is False
    assert decomposition["uses_gold_fields"] is False
    assert decomposition["uses_qrels"] is False
    assert decomposition["uses_labels"] is False
    assert decomposition["uses_ids_as_runtime_inputs"] is False
    assert audit["gold_or_expected_runtime_input_detected"] is False
    assert audit["row_specific_rule_detected"] is False
    assert audit["dataset_specific_rule_detected"] is False
    forbidden = [
        "SECRET_EXPECTED_ANSWER_NEVER_RUNTIME",
        "SECRET_EXPECTED_EVIDENCE_NEVER_RUNTIME",
        "SECRET_QREL_NEVER_RUNTIME",
        "SECRET_LABEL_NEVER_RUNTIME",
        "SECRET_ROW_ID_NEVER_RUNTIME",
    ]
    prompt_text = "\n".join(prompts)
    diagnostic_text = json.dumps(
        {
            "generated_answer": report["items"][0]["generated_answer"],
            "answer_composer": report["items"][0]["answer_composer"],
            "selected_evidence_failure_decomposition": decomposition,
            "overfit_and_heuristic_audit": audit,
        },
        ensure_ascii=False,
    )
    assert len(prompts) == 1
    for sentinel in forbidden:
        assert sentinel not in prompt_text
        assert sentinel not in diagnostic_text


def test_selected_evidence_failure_decomposition_reports_gate_blocked_clean_local_llm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "selected_evidence_gate_blocked_clean_gold.jsonl"
    context = tmp_path / "selected_evidence_gate_blocked_clean_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_evidence_gate_blocked_clean"
    write_jsonl(dataset, [{"id": "q-clean-gate-blocked", "query": "Where is Apollo HQ?", "answerability": "answerable"}])
    write_jsonl(
        context,
        [
            {
                "id": "q-clean-gate-blocked",
                "generated_answer": "legacy answer",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "text": "HQ is in Seoul.",
                    }
                ],
                "citations": [],
            }
        ],
    )

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {"answer": "Apollo HQ is in Seoul.", "citation_evidence_ids": ["bundle-hq"]},
            {"raw_response_sha256": "sha256:clean-gate-blocked"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_evidence_gate_blocked_clean",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-local-llm-v1",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert report["generator_config"]["local_llm_clean_answer_gate_blocked_count"] == 1
    assert report["generator_config"]["local_llm_gate_aligned_fallback_count"] == 0
    row = report["items"][0]
    assert row["answer_composer"]["local_llm"]["status"] == "generated"
    assert row["answer_composer"]["local_llm_fallback_used"] is False
    assert row["answer_composer"].get("local_llm_gate_aligned_fallback_used") is False
    assert "gate_aligned_evidence_package_status" not in row["answer_composer"]
    assert row["answer_composer"]["answer_discipline"]["status"] == "clean_supported"
    assert row["answer_gate_decision"] == "block_unsupported_answer"
    assert row["generated_answer"] == actual_rag_eval.BOUNDED_EVIDENCE_ABSTENTION_ANSWER
    assert row["answer_modified_by_gate"] is True
    assert row["unsupported_answer_blocked"] is True
    decomposition = report["selected_evidence_failure_decomposition"]
    assert decomposition["gate_blocked_clean_local_llm_count"] == 1
    assert decomposition["rows"][0]["local_llm_clean_answer_gate_blocked"] is True
    assert "gate_blocked_clean_local_llm" in decomposition["rows"][0]["classifications"]


def test_selected_evidence_failure_decomposition_splits_pre_fallback_and_final_insufficient() -> None:
    value_source = {
        "doc_id": "doc-hq",
        "chunk_id": "chunk-hq",
        "source_atom_id": "src-hq",
        "evidence_bundle_id": "bundle-hq",
        "source_family": "TEXT",
        "text": "target_column=headquarters | display_value=Seoul",
        "display_value": "Seoul",
    }
    report = actual_rag_eval.build_selected_evidence_failure_decomposition(
        items=[],
        rows=[
            {
                "id": "q-pre-fallback-allowed",
                "retrieved_contexts": [value_source],
                "answer_composer": {
                    "selected_evidence_count": 1,
                    "selected_evidence": [value_source],
                    "local_llm": {
                        "status": "answer_discipline_deterministic_fallback",
                        "fallback_reason": "answer_discipline_true_insufficient_evidence",
                    },
                    "initial_answer_discipline": {"status": "true_insufficient_evidence"},
                    "answer_discipline": {"status": "true_insufficient_evidence"},
                },
                "evidence_gate": {
                    "answer_gate_decision": "allow_answer",
                    "evidence_package_status": "sufficient",
                    "validation_reasons": [],
                },
            },
            {
                "id": "q-final-blocked",
                "retrieved_contexts": [value_source],
                "answer_composer": {
                    "selected_evidence_count": 1,
                    "selected_evidence": [value_source],
                    "answer_discipline": {"status": "clean_supported"},
                },
                "evidence_gate": {
                    "answer_gate_decision": "block_unsupported_answer",
                    "evidence_package_status": "insufficient",
                    "validation_reasons": ["missing_query_anchor"],
                },
            },
        ],
    )

    assert report["pre_fallback_true_insufficient_evidence_count"] == 1
    assert report["true_insufficient_evidence_count"] == 1
    rows = {row["id"]: row for row in report["rows"]}
    assert rows["q-pre-fallback-allowed"]["pre_fallback_true_insufficient_evidence"] is True
    assert rows["q-pre-fallback-allowed"]["true_insufficient_evidence"] is False
    assert "pre_fallback_true_insufficient_evidence" in rows["q-pre-fallback-allowed"]["classifications"]
    assert "true_insufficient_evidence" not in rows["q-pre-fallback-allowed"]["classifications"]
    assert rows["q-final-blocked"]["true_insufficient_evidence"] is True
    assert "true_insufficient_evidence" in rows["q-final-blocked"]["classifications"]


def test_selected_evidence_value_present_requires_source_native_value_or_numeric_signal() -> None:
    literal_only_source = {
        "doc_id": "doc-hq",
        "chunk_id": "chunk-hq",
        "source_atom_id": "src-hq",
        "evidence_bundle_id": "bundle-hq",
        "source_family": "TEXT",
        "text": "Apollo HQ is in Seoul.",
    }
    source_native_value = dict(literal_only_source, display_value="Seoul")

    report = actual_rag_eval.build_selected_evidence_failure_decomposition(
        items=[],
        rows=[
            {
                "id": "q-literal-only",
                "retrieved_contexts": [literal_only_source],
                "answer_composer": {"selected_evidence_count": 1, "selected_evidence": [literal_only_source]},
                "evidence_gate": {
                    "answer_gate_decision": "block_unsupported_answer",
                    "evidence_package_status": "insufficient",
                    "validation_reasons": ["missing_query_anchor"],
                },
            },
            {
                "id": "q-source-value",
                "retrieved_contexts": [source_native_value],
                "answer_composer": {"selected_evidence_count": 1, "selected_evidence": [source_native_value]},
                "evidence_gate": {
                    "answer_gate_decision": "block_unsupported_answer",
                    "evidence_package_status": "insufficient",
                    "validation_reasons": ["missing_query_anchor"],
                },
            },
        ],
    )

    rows = {row["id"]: row for row in report["rows"]}
    assert rows["q-literal-only"]["selected_evidence_value_present_anchor_missing"] is False
    assert "selected_evidence_value_present_anchor_missing" not in rows["q-literal-only"]["classifications"]
    assert rows["q-source-value"]["selected_evidence_value_present_anchor_missing"] is True
    assert "selected_evidence_value_present_anchor_missing" in rows["q-source-value"]["classifications"]


def test_selected_evidence_failure_decomposition_preserves_raw_payload_privacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "selected_evidence_payload_privacy_gold.jsonl"
    context = tmp_path / "selected_evidence_payload_privacy_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_evidence_payload_privacy"
    write_jsonl(dataset, [{"id": "q-payload", "query": "Where is Apollo HQ?", "answerability": "answerable"}])
    write_jsonl(
        context,
        [
            {
                "id": "q-payload",
                "generated_answer": "legacy answer",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [],
            }
        ],
    )

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        return (
            {"answer": "Apollo HQ is in Seoul.", "citation_evidence_ids": ["bundle-hq"]},
            {
                "raw_response_sha256": "sha256:payload-privacy",
                "raw_response": "SECRET_RAW_RESPONSE_NEVER_WRITE",
                "raw_prompt_payload": {"secret": "SECRET_RAW_PROMPT_NEVER_WRITE"},
            },
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_evidence_payload_privacy",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        answer_composer="selected-evidence-local-llm-v1",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False
    assert report["selected_evidence_failure_decomposition"]["raw_prompt_payload_written"] is False
    assert report["selected_evidence_failure_decomposition"]["raw_response_payload_written"] is False
    assert report["overfit_and_heuristic_audit"]["raw_prompt_payload_written"] is False
    assert report["overfit_and_heuristic_audit"]["raw_response_payload_written"] is False
    assert output_file_names(output_dir) == ["report.json"]
    encoded_report = json.dumps(report, ensure_ascii=False)
    assert "SECRET_RAW_RESPONSE_NEVER_WRITE" not in encoded_report
    assert "SECRET_RAW_PROMPT_NEVER_WRITE" not in encoded_report
    assert '"raw_prompt_payload":' not in encoded_report
    assert '"prompt":' not in encoded_report
    assert '"raw_response":' not in encoded_report


def test_selected_evidence_runtime_inputs_reject_gold_silver_qrels_label_sentinels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "selected_evidence_runtime_sentinel_gold.jsonl"
    context = tmp_path / "selected_evidence_runtime_sentinel_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_evidence_runtime_sentinel"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-runtime-sentinel",
                "query": "Where is Apollo HQ?",
                "answerability": "answerable",
                "expected_answer": "SECRET_RUNTIME_EXPECTED_ANSWER",
                "expected_evidence": [{"text": "SECRET_RUNTIME_EXPECTED_EVIDENCE"}],
                "qrels": {"SECRET_RUNTIME_QREL": 1},
                "labels": ["SECRET_RUNTIME_LABEL"],
                "row_id": "SECRET_RUNTIME_ROW_ID",
                "target_id": "SECRET_RUNTIME_TARGET_ID",
                "silver_metadata": "SECRET_RUNTIME_SILVER_FIELD",
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-runtime-sentinel",
                "generated_answer": "legacy answer",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [],
            }
        ],
    )
    prompts: list[str] = []

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**kwargs: object) -> tuple[dict, dict]:
        prompts.append(str(kwargs.get("prompt", "")))
        return (
            {"answer": "Apollo HQ is in Seoul.", "citation_evidence_ids": ["bundle-hq"]},
            {"raw_response_sha256": "sha256:runtime-sentinel"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_evidence_runtime_sentinel",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        answer_composer="selected-evidence-local-llm-v1",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    audit = report["overfit_and_heuristic_audit"]
    assert audit["schema_version"] == "overfit_and_heuristic_audit_v1"
    assert audit["report_only_diagnostic"] is True
    assert audit["gold_or_expected_runtime_input_detected"] is False
    assert audit["uses_expected_answers"] is False
    assert audit["uses_expected_evidence"] is False
    assert audit["uses_qrels"] is False
    assert audit["uses_labels"] is False
    assert audit["uses_ids_as_runtime_inputs"] is False
    forbidden = [
        "SECRET_RUNTIME_EXPECTED_ANSWER",
        "SECRET_RUNTIME_EXPECTED_EVIDENCE",
        "SECRET_RUNTIME_QREL",
        "SECRET_RUNTIME_LABEL",
        "SECRET_RUNTIME_ROW_ID",
        "SECRET_RUNTIME_TARGET_ID",
        "SECRET_RUNTIME_SILVER_FIELD",
    ]
    runtime_text = json.dumps(
        {
            "prompt_text": "\n".join(prompts),
            "generated_answer": report["items"][0]["generated_answer"],
            "answer_composer": report["items"][0]["answer_composer"],
            "audit": audit,
        },
        ensure_ascii=False,
    )
    assert len(prompts) == 1
    for sentinel in forbidden:
        assert sentinel not in runtime_text


def test_selected_evidence_runtime_inputs_reject_row_specific_or_dataset_specific_rules(tmp_path: Path) -> None:
    dataset = tmp_path / "selected_evidence_rule_audit_gold.jsonl"
    context = tmp_path / "selected_evidence_rule_audit_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_evidence_rule_audit"
    write_jsonl(dataset, [{"id": "q-rule-audit", "query": "Where is Apollo HQ?", "answerability": "answerable"}])
    write_jsonl(
        context,
        [
            {
                "id": "q-rule-audit",
                "generated_answer": "legacy answer",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_evidence_rule_audit",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        answer_composer="selected-evidence-deterministic-v1",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    audit = report["overfit_and_heuristic_audit"]
    assert audit["row_specific_rule_detected"] is False
    assert audit["dataset_specific_rule_detected"] is False
    assert audit["literal_case_term_rule_detected"] is False
    assert audit["literal_case_terms_detected"] == []


def test_overfit_and_heuristic_audit_detects_configured_rule_surfaces() -> None:
    audit = actual_rag_eval.build_overfit_and_heuristic_audit(
        rows=[],
        generator_config={
            "selected_evidence_composer_input_policy": "query_text_and_selected_evidence_only",
            "heuristic_rule_surfaces": {
                "literal_case_terms": ["Apollo HQ"],
                "row_specific_rules": ["text_namu_v2_0014"],
                "dataset_specific_rules": ["six-row gold diagnostic slice"],
            },
        },
    )

    assert audit["row_specific_rule_detected"] is True
    assert audit["dataset_specific_rule_detected"] is True
    assert audit["literal_case_term_rule_detected"] is True
    assert "Apollo HQ" in audit["literal_case_terms_detected"]
    assert audit["detected_rule_surfaces"]


def test_answer_focus_rules_are_generic_not_case_literal(tmp_path: Path) -> None:
    discipline = actual_rag_eval._selected_evidence_answer_discipline(
        query="What are Rina's age and birthday?",
        answer="Rina is 18 and her birthday is March 4.",
        selected_evidence=[
            {
                "doc_id": "doc-rina",
                "chunk_id": "chunk-profile",
                "source_atom_id": "src-rina",
                "evidence_bundle_id": "bundle-rina",
                "source_family": "TEXT",
                "text": "Rina profile: age 18. Birthday March 4. Height 161cm.",
            }
        ],
        cited_evidence_ids=["bundle-rina"],
    )
    assert discipline["status"] == "clean_supported"

    dataset = tmp_path / "selected_evidence_focus_rules_gold.jsonl"
    context = tmp_path / "selected_evidence_focus_rules_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_evidence_focus_rules"
    write_jsonl(dataset, [{"id": "q-focus-rules", "query": "What are Rina's age and birthday?", "answerability": "answerable"}])
    write_jsonl(
        context,
        [
            {
                "id": "q-focus-rules",
                "generated_answer": "legacy answer",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-rina",
                        "chunk_id": "chunk-profile",
                        "source_atom_id": "src-rina",
                        "evidence_bundle_id": "bundle-rina",
                        "source_family": "TEXT",
                        "text": "Rina profile: age 18. Birthday March 4. Height 161cm.",
                    }
                ],
                "citations": [],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_evidence_focus_rules",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        answer_composer="selected-evidence-deterministic-v1",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    audit = report["overfit_and_heuristic_audit"]
    assert audit["literal_case_term_rule_detected"] is False
    assert audit["remaining_rule_based_components"]
    assert "answer_focus_generic_terms" in audit["remaining_rule_based_components"]
    assert "Rina" not in json.dumps(audit["remaining_rule_based_components"], ensure_ascii=False)


def test_dataset_sufficiency_diagnostic_reports_source_family_and_query_shape_counts(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset_sufficiency_counts_gold.jsonl"
    context = tmp_path / "dataset_sufficiency_counts_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "dataset_sufficiency_counts"
    write_jsonl(
        dataset,
        [
            {"id": "q-text", "query": "Where is Apollo HQ?", "answerability": "answerable"},
            {"id": "q-xlsx", "query": "2019 February Line 5 passenger count", "answerability": "answerable"},
            {"id": "q-pdf", "query": "Which page section explains the survey method?", "answerability": "answerable"},
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-text",
                "generated_answer": "legacy answer",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-text",
                        "chunk_id": "chunk-text",
                        "source_atom_id": "src-text",
                        "evidence_bundle_id": "bundle-text",
                        "source_family": "TEXT",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [],
            },
            {
                "id": "q-xlsx",
                "generated_answer": "legacy answer",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-xlsx",
                        "chunk_id": "chunk-xlsx",
                        "source_atom_id": "src-xlsx",
                        "evidence_bundle_id": "bundle-xlsx",
                        "source_family": "XLSX",
                        "text": "2019 February Line 5 passenger count is 15,446,522.",
                    }
                ],
                "citations": [],
            },
            {
                "id": "q-pdf",
                "generated_answer": "legacy answer",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-pdf",
                        "chunk_id": "chunk-pdf",
                        "source_atom_id": "src-pdf",
                        "evidence_bundle_id": "bundle-pdf",
                        "source_family": "PDF",
                        "page_number": 7,
                        "section_title": "Survey method",
                        "text": "Page 7. Survey method section describes stratified sampling.",
                    }
                ],
                "citations": [],
            },
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="dataset_sufficiency_counts",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        answer_composer="selected-evidence-deterministic-v1",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    diagnostic = report["dataset_sufficiency_diagnostic"]
    assert diagnostic["schema_version"] == "dataset_sufficiency_diagnostic_v1"
    assert diagnostic["report_only_diagnostic"] is True
    assert diagnostic["official_metric"] is False
    assert diagnostic["uses_gold_fields"] is False
    assert diagnostic["uses_expected_fields_as_runtime_inputs"] is False
    assert diagnostic["uses_qrels"] is False
    assert diagnostic["uses_labels"] is False
    assert diagnostic["uses_ids_as_runtime_inputs"] is False
    assert diagnostic["raw_prompt_payload_written"] is False
    assert diagnostic["raw_response_payload_written"] is False
    assert diagnostic["source_families_observed"]["TEXT"] == 1
    assert diagnostic["source_families_observed"]["XLSX"] == 1
    assert diagnostic["source_families_observed"]["PDF"] == 1
    assert diagnostic["query_shape_counts"]["entity_fact"] >= 1
    assert diagnostic["query_shape_counts"]["numeric_date_fact"] >= 1
    assert diagnostic["query_shape_counts"]["page_section_lookup"] >= 1
    assert diagnostic["gold_rows_checked"] == 3
    assert diagnostic["coverage_gaps"] == []
    assert diagnostic["external_archive_recommended"] is False
    assert diagnostic["external_archive_used"] is False


def test_dataset_sufficiency_diagnostic_recommends_external_archive_only_for_coverage_gaps(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset_sufficiency_gap_gold.jsonl"
    context = tmp_path / "dataset_sufficiency_gap_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "dataset_sufficiency_gap"
    write_jsonl(
        dataset,
        [
            {"id": "q-covered", "query": "Where is Apollo HQ?", "answerability": "answerable"},
            {"id": "q-gap", "query": "Which table lists Korean public-data catalog status for May 2026?", "answerability": "answerable"},
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-covered",
                "generated_answer": "legacy answer",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-text",
                        "chunk_id": "chunk-text",
                        "source_atom_id": "src-text",
                        "evidence_bundle_id": "bundle-text",
                        "source_family": "TEXT",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [],
            },
            {"id": "q-gap", "generated_answer": "", "retrieved_contexts": [], "citations": []},
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="dataset_sufficiency_gap",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        answer_composer="selected-evidence-deterministic-v1",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    diagnostic = report["dataset_sufficiency_diagnostic"]
    assert diagnostic["external_archive_recommended"] is True
    assert diagnostic["external_archive_used"] is False
    assert diagnostic["external_archive_root"] == ""
    assert len(diagnostic["coverage_gaps"]) == 1
    gap = diagnostic["coverage_gaps"][0]
    assert gap["id"] == "q-gap"
    assert gap["reason"] == "retrieval_empty_or_corpus_coverage_suspected"
    assert diagnostic["rows_by_id"]["q-covered"]["external_archive_candidate_needed"] is False
    assert diagnostic["rows_by_id"]["q-gap"]["external_archive_candidate_needed"] is True


def test_run_eval_selected_evidence_local_llm_composer_unavailable_falls_back_without_raw_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "selected_local_llm_gold.jsonl"
    context = tmp_path / "selected_local_llm_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_local_llm_unavailable"
    write_jsonl(
        dataset,
        [{"id": "q-local-llm", "query": "Where is Apollo HQ?", "answerability": "answerable"}],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-local-llm",
                "generated_answer": "extractive-v1 broad answer from every context",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "text": "Apollo HQ is in Seoul.",
                        "text_sha256": "hash-hq",
                    }
                ],
                "citations": [],
            }
        ],
    )

    def fake_blockers(**_kwargs: object) -> list[str]:
        return ["LOCAL_LLM_UNAVAILABLE: connection refused"]

    def unexpected_call(**_kwargs: object) -> tuple[dict, dict]:
        raise AssertionError("local LLM should not be called when availability check fails")

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", unexpected_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_local_llm_unavailable",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-local-llm-v1",
    )

    assert output_file_names(output_dir) == ["report.json"]
    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    config = report["generator_config"]
    local_meta = row["answer_composer"]["local_llm"]
    assert config["provider"] == "selected-evidence-local-llm-v1"
    assert config["local_llm_generation_available"] is False
    assert config["local_llm_composer_fallback_used"] is True
    assert config["local_llm_not_used_reason"] == "local_llm_unavailable_deterministic_fallback"
    assert config["local_llm_blockers"] == ["LOCAL_LLM_UNAVAILABLE: connection refused"]
    assert config["actual_generation_model_used"] is False
    assert config["external_api_calls"] is False
    assert "Seoul" in row["generated_answer"]
    assert row["answer_composer"]["provider"] == "selected-evidence-local-llm-v1"
    assert local_meta["status"] == "unavailable_deterministic_fallback"
    assert local_meta["fallback_provider"] == "selected-evidence-deterministic-v1"
    assert local_meta["blockers"] == ["LOCAL_LLM_UNAVAILABLE: connection refused"]
    assert "prompt" not in local_meta
    assert "raw_response" not in local_meta
    assert "raw_prompt_payload_written" not in local_meta
    assert "raw_response_payload_written" not in local_meta
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False
    assert row["evidence_gate"]["unsupported_answer_blocked"] is False


def test_run_eval_selected_evidence_local_llm_composer_available_stores_hashes_and_preview_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "selected_local_llm_gold.jsonl"
    context = tmp_path / "selected_local_llm_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_local_llm_available"
    write_jsonl(
        dataset,
        [{"id": "q-local-llm", "query": "Where is Apollo HQ?", "answerability": "answerable"}],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-local-llm",
                "generated_answer": "extractive-v1 broad answer from every context",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "text": "Apollo HQ is in Seoul.",
                        "text_sha256": "hash-hq",
                    }
                ],
                "citations": [],
            }
        ],
    )
    captured: dict[str, str] = {}

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**kwargs: object) -> tuple[dict, dict]:
        prompt = str(kwargs["prompt"])
        captured["prompt"] = prompt
        assert "Apollo HQ is in Seoul." in prompt
        assert "extractive-v1 broad answer" not in prompt
        return (
            {
                "answer": "Apollo HQ is in Seoul.",
                "citation_evidence_ids": ["bundle-hq"],
            },
            {
                "raw_response_sha256": "sha256:raw-local-response",
                "strict_json": True,
            },
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_local_llm_available",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        answer_composer="selected-evidence-local-llm-v1",
        selected_evidence_citation_format="evidence-id",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    config = report["generator_config"]
    local_meta = row["answer_composer"]["local_llm"]
    assert config["provider"] == "selected-evidence-local-llm-v1"
    assert config["actual_generation_model_used"] is True
    assert config["local_llm_generation_available"] is True
    assert config["local_llm_composer_fallback_used"] is False
    assert config["local_llm_composer_generated_count"] == 1
    assert config["local_llm_prompt_payload_written"] is False
    assert config["local_llm_raw_response_payload_written"] is False
    assert row["generated_answer"] == "Apollo HQ is in Seoul."
    assert "**Short answer:**" not in row["generated_answer"]
    assert "**Supporting passages:**" not in row["generated_answer"]
    assert row["citations"][0]["evidence_bundle_id"] == "bundle-hq"
    assert row["answer_composer"]["formatted_citations"] == [
        "[1] evidence_bundle_id=bundle-hq; source_atom_id=src-hq"
    ]
    assert row["answer_composer"]["answer_rendering_policy"] == "local_llm_natural_query_context_sentence"
    assert row["answer_composer"]["answer_audit_scaffold_in_generated_answer"] is False
    assert local_meta["status"] == "generated"
    assert local_meta["prompt_sha256"].startswith("sha256:")
    assert local_meta["raw_response_sha256"] == "sha256:raw-local-response"
    assert local_meta["answer_preview"] == "Apollo HQ is in Seoul."
    assert "prompt" not in local_meta
    assert "raw_response" not in local_meta
    assert "raw_prompt_payload_written" not in local_meta
    assert "raw_response_payload_written" not in local_meta
    assert captured["prompt"]
    assert "natural, query-context sentence" in captured["prompt"]
    assert "Do not return only a terse fragment" in captured["prompt"]
    assert "Do not include audit headers" in captured["prompt"]
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False
    assert row["evidence_gate"]["citation_retrieved_context_only_diagnostic_count"] == 0


def test_run_eval_selected_evidence_local_llm_composer_retries_once_after_gate_insufficient(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "selected_local_llm_retry_gold.jsonl"
    context = tmp_path / "selected_local_llm_retry_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_local_llm_retry"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-local-retry",
                "query": "Where is Apollo HQ?",
                "answerability": "answerable",
                "expected_answer": "Forbidden gold answer",
                "expected_evidence": [{"text": "Forbidden expected evidence"}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-local-retry",
                "generated_answer": "legacy extractive answer must not become retry input",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "text": "Apollo HQ is in Seoul.",
                        "text_sha256": "hash-hq",
                    }
                ],
                "citations": [],
            }
        ],
    )
    captured_prompts: list[str] = []

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**kwargs: object) -> tuple[dict, dict]:
        prompt = str(kwargs["prompt"])
        captured_prompts.append(prompt)
        assert "q-local-retry" not in prompt
        assert "Forbidden gold answer" not in prompt
        assert "Forbidden expected evidence" not in prompt
        assert "legacy extractive answer" not in prompt
        if len(captured_prompts) == 1:
            return (
                {"answer": "Apollo HQ is in Seoul and Busan.", "citation_evidence_ids": ["bundle-hq"]},
                {"raw_response_sha256": "sha256:first"},
            )
        return (
            {"answer": "Apollo HQ is in Seoul.", "citation_evidence_ids": ["bundle-hq"]},
            {"raw_response_sha256": "sha256:retry"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_local_llm_retry",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-local-llm-v1",
        selected_evidence_citation_format="evidence-id",
        selected_evidence_composer_retry_mode="bounded-once",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    config = report["generator_config"]
    retry = row["answer_composer"]["retry"]
    assert len(captured_prompts) == 2
    assert "previous_answer_preview" not in captured_prompts[0]
    assert "Apollo HQ is in Seoul and Busan." in captured_prompts[1]
    assert config["selected_evidence_composer_retry_mode"] == "bounded-once"
    assert config["selected_evidence_composer_retry_attempt_count"] == 1
    assert config["selected_evidence_composer_retry_accepted_count"] == 1
    assert config["selected_evidence_composer_retry_rejected_count"] == 0
    assert config["selected_evidence_composer_retry_max_count_per_item"] == 1
    assert config["selected_evidence_composer_retry_raw_prompt_payload_written"] is False
    assert config["selected_evidence_composer_retry_raw_response_payload_written"] is False
    assert retry["enabled"] is True
    assert retry["attempted"] is True
    assert retry["attempt_count"] == 1
    assert retry["status"] == "accepted"
    assert retry["trigger"] == "evidence_gate_insufficient"
    assert retry["previous_answer_preview"] == "Apollo HQ is in Seoul and Busan."
    assert retry["retry_prompt_sha256"].startswith("sha256:")
    assert retry["retry_raw_response_sha256"] == "sha256:retry"
    assert "prompt" not in retry
    assert "raw_response" not in retry
    assert row["generated_answer"] == "Apollo HQ is in Seoul."
    assert "**Short answer:**" not in row["generated_answer"]
    assert row["answer_composer"]["answer_rendering_policy"] == "local_llm_natural_query_context_sentence"
    assert row["answer_composer"]["answer_audit_scaffold_in_generated_answer"] is False
    assert row["answer_gate_decision"] == "allow_answer"
    assert row["evidence_gate"]["unsupported_answer_blocked"] is False
    assert row["evidence_gate"]["citation_retrieved_context_only_diagnostic_count"] == 0
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False


def test_run_eval_selected_evidence_local_llm_composer_does_not_retry_when_gate_allows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "selected_local_llm_no_retry_gold.jsonl"
    context = tmp_path / "selected_local_llm_no_retry_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "selected_local_llm_no_retry"
    write_jsonl(
        dataset,
        [{"id": "q-local-no-retry", "query": "Where is Apollo HQ?", "answerability": "answerable"}],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-local-no-retry",
                "generated_answer": "legacy extractive answer",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "text": "Apollo HQ is in Seoul.",
                        "text_sha256": "hash-hq",
                    }
                ],
                "citations": [],
            }
        ],
    )
    call_count = 0

    def fake_blockers(**_kwargs: object) -> list[str]:
        return []

    def fake_call(**_kwargs: object) -> tuple[dict, dict]:
        nonlocal call_count
        call_count += 1
        return (
            {"answer": "Apollo HQ is in Seoul.", "citation_evidence_ids": ["bundle-hq"]},
            {"raw_response_sha256": "sha256:first"},
        )

    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "local_llm_entry_blockers", fake_blockers)
    monkeypatch.setattr(actual_rag_eval.LOCAL_LLM_HELPER, "call_local_llm_strict_json", fake_call)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="selected_local_llm_no_retry",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        answer_composer="selected-evidence-local-llm-v1",
        selected_evidence_composer_retry_mode="bounded-once",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    retry = row["answer_composer"]["retry"]
    assert call_count == 1
    assert report["generator_config"]["selected_evidence_composer_retry_attempt_count"] == 0
    assert retry["enabled"] is True
    assert retry["attempted"] is False
    assert retry["status"] == "not_triggered"
    assert retry["reason"] == "answer_discipline_clean_supported"
    assert row["answer_gate_decision"] == "allow_answer"


def test_run_eval_embeds_portfolio_comparison_report_only(tmp_path: Path) -> None:
    dataset = tmp_path / "portfolio_compare_gold.jsonl"
    context = tmp_path / "portfolio_compare_context.jsonl"
    baseline_dir = tmp_path / "reports" / "rag_eval" / "portfolio_compare_extractive"
    current_dir = tmp_path / "reports" / "rag_eval" / "portfolio_compare_selected"
    write_jsonl(
        dataset,
        [{"id": "q-portfolio", "query": "Where is Apollo HQ?", "answerability": "answerable"}],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-portfolio",
                "generated_answer": "Apollo HQ is somewhere in Korea.",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "granularity": "paragraph",
                        "text": "Apollo HQ is in Seoul.",
                        "text_sha256": "hash-hq",
                    }
                ],
                "citations": [],
            }
        ],
    )

    baseline = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=baseline_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="portfolio_compare_extractive",
        output_mode="single",
        evidence_gate_mode="diagnostic",
    )
    current = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=current_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="portfolio_compare_selected",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="markdown-portfolio",
        portfolio_comparison_reports=[f"extractive={baseline.report_path}"],
    )

    report = json.loads(current.report_path.read_text(encoding="utf-8"))
    comparison = report["portfolio_experiment_comparison"]
    assert output_file_names(current_dir) == ["report.json"]
    assert report["artifact_contract"]["portfolio_experiment_sidecar_written"] is False
    assert comparison["schema_version"] == "actual_rag_eval.portfolio_experiment_comparison.v1"
    assert comparison["enabled"] is True
    assert comparison["report_only_contract"] == "embedded_in_report_json_no_portfolio_sidecar"
    assert comparison["portfolio_experiment_sidecar_written"] is False
    assert comparison["comparison_input_policy"].startswith("post_run_report_json_only")
    assert comparison["raw_prompt_payload_written"] is False
    assert comparison["raw_response_payload_written"] is False
    assert comparison["lane_count"] == 2
    assert comparison["lanes"][0]["label"] == "extractive"
    assert comparison["lanes"][1]["label"] == "current"
    assert comparison["lanes"][0]["provider"] == "extractive-v1"
    assert comparison["lanes"][1]["provider"] == "selected-evidence-deterministic-v1"
    assert comparison["lanes"][1]["citation_precision_against_selected_evidence"] == 1.0
    diff = comparison["pairwise_diffs"][0]
    assert diff["gate_delta"]["after"]["unsupported_answer_rate_after_gate"] == 0.0
    item_diff = diff["answer_diffs"][0]
    assert item_diff["id"] == "q-portfolio"
    assert item_diff["answer_changed"] is True
    assert item_diff["citation_changed"] is True
    assert item_diff["baseline_answer"]["answer_sha256"].startswith("sha256:")
    assert item_diff["current_answer"]["answer_sha256"].startswith("sha256:")
    assert "Apollo HQ is somewhere" in item_diff["baseline_answer"]["answer_preview"]
    assert "Apollo HQ is in Seoul" in item_diff["current_answer"]["answer_preview"]
    serialized = json.dumps(comparison)
    assert '"prompt":' not in serialized
    assert '"raw_response":' not in serialized


def test_run_eval_writes_portfolio_summary_only_with_explicit_flag(tmp_path: Path) -> None:
    dataset = tmp_path / "portfolio_sidecar_gold.jsonl"
    context = tmp_path / "portfolio_sidecar_context.jsonl"
    baseline_dir = tmp_path / "reports" / "rag_eval" / "portfolio_sidecar_extractive"
    current_dir = tmp_path / "reports" / "rag_eval" / "portfolio_sidecar_selected"
    missing_comparison_dir = tmp_path / "reports" / "rag_eval" / "portfolio_sidecar_missing_comparison"
    write_jsonl(
        dataset,
        [{"id": "q-sidecar", "query": "Where is Apollo HQ?", "answerability": "answerable"}],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-sidecar",
                "generated_answer": "Apollo HQ is somewhere in Korea.",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "source_family": "TEXT",
                        "granularity": "paragraph",
                        "text": "Apollo HQ is in Seoul.",
                        "text_sha256": "hash-hq",
                    }
                ],
                "citations": [],
            }
        ],
    )

    baseline = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=baseline_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="portfolio_sidecar_extractive",
        output_mode="single",
        evidence_gate_mode="diagnostic",
    )
    current = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=current_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="portfolio_sidecar_selected",
        output_mode="single",
        evidence_gate_mode="enforce",
        answer_composer="selected-evidence-deterministic-v1",
        selected_evidence_citation_format="markdown-portfolio",
        portfolio_comparison_reports=[f"extractive={baseline.report_path}"],
        write_portfolio_experiment_summary=True,
    )

    assert output_file_names(current_dir) == ["portfolio_experiment_summary.md", "report.json"]
    report = json.loads(current.report_path.read_text(encoding="utf-8"))
    sidecar_path = current_dir / "portfolio_experiment_summary.md"
    text = sidecar_path.read_text(encoding="utf-8")
    assert report["artifact_contract"]["portfolio_experiment_sidecar_written"] is True
    assert report["artifact_paths"]["portfolio_experiment_summary_md"] == sidecar_path.as_posix()
    assert "# Non-Production Selected-Evidence Portfolio Experiment" in text
    assert "## Answer Diff" in text
    assert "## Citation Diff" in text
    assert "## Gate Before/After" in text
    assert "Unsupported answer blocked count" in text
    assert "Abstain count" in text
    assert "Citation precision against selected evidence" in text
    assert "Retrieved-context-only citation count" in text
    assert "## Residual Failure Taxonomy" in text
    assert "Apollo HQ is somewhere" in text
    assert "Apollo HQ is in Seoul" in text
    assert '"prompt":' not in text
    assert '"raw_response":' not in text

    with pytest.raises(DatasetSchemaError, match="requires at least one --portfolio-comparison-report"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=missing_comparison_dir,
            context_jsonl_path=context,
            top_k=1,
            run_id="portfolio_sidecar_missing_comparison",
            output_mode="single",
            evidence_gate_mode="enforce",
            write_portfolio_experiment_summary=True,
        )
