from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_text_namu_generated_answer_output.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_text_namu_generated_answer_output", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


generated_output = load_module()


def test_generated_answer_review_input_uses_source_bound_chunks_and_stays_diagnostic(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    output_jsonl = tmp_path / "generated_answers.jsonl"
    output_report = tmp_path / "generated_answers_report.json"
    output_md = tmp_path / "generated_answers_report.md"

    report = generated_output.run_generation(
        text_review_pack=paths["text_review_pack"],
        normalization_report=paths["normalization_report"],
        output_jsonl=output_jsonl,
        output_report=output_report,
        output_md=output_md,
    )

    assert report["status"] == "PASS"
    assert report["generated_answer_rows"] == 2
    assert report["missing_generated_answer_rows"] == 0
    assert report["rows_skipped_by_policy"] == 1
    assert report["rows_skipped_by_unresolved_source_binding"] == 1
    assert report["official_metric_input_rows"] == 0
    assert report["guardrails"]["official_metric_input_remains_false"] is True
    assert report["guardrails"]["production_index_mutation"] is False

    rows = read_jsonl(output_jsonl)
    assert len(rows) == 2
    first = rows[0]
    assert first["query_id"] == "text_001"
    assert first["safe_query_text"] == "작품 감독 알려줘"
    assert first["generated_answer"]
    assert first["cited_chunk_ids"] == ["chunk-1"]
    assert first["retrieved_chunk_ids"] == ["chunk-1"]
    assert first["citation_items"][0]["chunk_id"] == "chunk-1"
    assert first["citation_items"][0]["citation_text"] == "감독은 홍길동이다."
    assert first["generation_provenance"]["generator_name"] == "extractive-v1"
    assert first["generation_provenance"]["actual_generated_answer_output"] is True
    assert first["generation_provenance"]["official_metric_input"] is False
    assert first["retrieval_provenance"]["source_artifact_id"]
    assert first["prompt_model_config_provenance"]["prompt_template_sha256"]
    assert first["diagnostic_only"] is True
    assert first["official_metric_input"] is False


def test_generated_answer_contract_fails_closed_for_partial_boolean_missing_citation_and_provenance():
    valid = valid_generated_row()

    assert generated_output.generated_answer_contract_errors({"query_id": "text_001", "live_llm_run": True})
    assert generated_output.generated_answer_contract_errors({**valid, "generated_answer": ""})
    assert generated_output.generated_answer_contract_errors({**valid, "cited_chunk_ids": []})
    assert generated_output.generated_answer_contract_errors({**valid, "citation_items": []})
    assert generated_output.generated_answer_contract_errors({**valid, "generation_provenance": {}})
    assert generated_output.generated_answer_contract_errors({**valid, "official_metric_input": True})
    assert generated_output.generated_answer_contract_errors({**valid, "diagnostic_only": False})
    assert generated_output.generated_answer_contract_errors(valid) == []


def test_main_writes_compact_report_without_mutating_source_artifacts(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    before_review_pack = paths["text_review_pack"].read_text(encoding="utf-8")
    before_normalization = paths["normalization_report"].read_text(encoding="utf-8")
    output_jsonl = tmp_path / "review_input.jsonl"
    output_report = tmp_path / "report.json"
    output_md = tmp_path / "report.md"

    result = generated_output.main(
        [
            "--text-review-pack",
            str(paths["text_review_pack"]),
            "--normalization-report",
            str(paths["normalization_report"]),
            "--output-jsonl",
            str(output_jsonl),
            "--output-report",
            str(output_report),
            "--output-md",
            str(output_md),
        ]
    )

    assert result == 0
    assert output_jsonl.exists()
    assert output_report.exists()
    assert output_md.exists()
    assert paths["text_review_pack"].read_text(encoding="utf-8") == before_review_pack
    assert paths["normalization_report"].read_text(encoding="utf-8") == before_normalization
    report = json.loads(output_report.read_text(encoding="utf-8"))
    assert report["generated_answer_rows"] == 2
    assert report["guardrails"]["candidate_artifact_mutated"] is False


def valid_generated_row() -> dict:
    return {
        "query_id": "text_001",
        "safe_query_text": "질문",
        "generated_answer": "답변",
        "cited_chunk_ids": ["chunk-1"],
        "retrieved_chunk_ids": ["chunk-1"],
        "citation_items": [{"chunk_id": "chunk-1", "citation_text": "근거"}],
        "generation_provenance": {
            "generator_name": "extractive-v1",
            "answer_generation_execution": "source_bound_extractive_generator_no_llm",
            "actual_generated_answer_output": True,
            "official_metric_input": False,
        },
        "retrieval_provenance": {
            "source_artifact_id": "artifact",
            "production_index_used": False,
            "production_index_mutation": False,
        },
        "prompt_model_config_provenance": {
            "prompt_template_sha256": "abc",
            "model_name": "none_extractive_generator",
        },
        "diagnostic_only": True,
        "official_metric_input": False,
        "official_denominator_mutation": False,
    }


def write_fixture_bundle(tmp_path: Path) -> dict[str, Path]:
    text_review_pack = tmp_path / "text_review_pack.csv"
    normalization_report = tmp_path / "normalization.json"
    write_review_pack(text_review_pack)
    write_json(
        normalization_report,
        {
            "tracks": {
                "text_namu_v2": {
                    "proposed_official_candidate_query_ids": ["text_001", "text_002"],
                    "policy_excluded_query_ids": ["text_003"],
                    "source_verification_required_query_ids": ["text_004"],
                    "diagnostic_only_query_ids": [],
                    "expected_answer_or_evidence_revision_query_ids": [],
                    "review_marker_buckets": {
                        "needs_second_review": [],
                        "evidence_too_broad": [],
                        "ambiguous_query": [],
                    },
                }
            }
        },
    )
    return {"text_review_pack": text_review_pack, "normalization_report": normalization_report}


def write_review_pack(path: Path) -> None:
    fieldnames = [
        "query_id",
        "query",
        "expected_page_ids",
        "expected_section_ids",
        "expected_chunk_ids",
        "expected_page_title",
        "expected_section_path",
        "source_url",
        "chunk_text_sha256",
        "source_evidence_quote",
        "source_locator",
    ]
    rows = [
        {
            "query_id": "text_001",
            "query": "작품 감독 알려줘",
            "expected_page_ids": "page-1",
            "expected_section_ids": "section-1",
            "expected_chunk_ids": "chunk-1",
            "expected_page_title": "작품",
            "expected_section_path": "개요",
            "source_url": "https://example.test/work",
            "chunk_text_sha256": "sha-1",
            "source_evidence_quote": "감독은 홍길동이다.",
            "source_locator": "chunk_id=chunk-1; page_id=page-1; section_id=section-1",
        },
        {
            "query_id": "text_002",
            "query": "방영 시기 알려줘",
            "expected_page_ids": "page-2",
            "expected_section_ids": "section-2",
            "expected_chunk_ids": "chunk-2",
            "expected_page_title": "작품2",
            "expected_section_path": "개요",
            "source_url": "https://example.test/work2",
            "chunk_text_sha256": "sha-2",
            "source_evidence_quote": "2024년에 방영되었다.",
            "source_locator": "chunk_id=chunk-2; page_id=page-2; section_id=section-2",
        },
        {
            "query_id": "text_003",
            "query": "정책 제외",
            "expected_page_ids": "page-3",
            "expected_section_ids": "section-3",
            "expected_chunk_ids": "chunk-3",
            "expected_page_title": "작품3",
            "expected_section_path": "개요",
            "source_url": "https://example.test/work3",
            "chunk_text_sha256": "sha-3",
            "source_evidence_quote": "제외 근거.",
            "source_locator": "chunk_id=chunk-3",
        },
        {
            "query_id": "text_004",
            "query": "소스 검토",
            "expected_page_ids": "page-4",
            "expected_section_ids": "section-4",
            "expected_chunk_ids": "chunk-4",
            "expected_page_title": "작품4",
            "expected_section_path": "개요",
            "source_url": "https://example.test/work4",
            "chunk_text_sha256": "sha-4",
            "source_evidence_quote": "검토 근거.",
            "source_locator": "chunk_id=chunk-4",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows
