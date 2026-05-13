from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "ai" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


builder = load_module("rag_pdf_supplemental_gold_review_candidate_builder")
pack = load_module("rag_pdf_supplemental_gold_review_pack")


def test_review_pack_reads_diagnostic_sources_and_keeps_user_columns_blank(tmp_path: Path):
    fixture = make_fixture(tmp_path)

    report = pack.build_review_pack(
        paths=fixture["paths"],
        output_dir=tmp_path / "pdf_supplemental_gold_review",
        summary_json_path=tmp_path / "rag_pdf_supplemental_gold_review_pack_summary.json",
        pack_size=5,
        expected_source_rows=5,
        high_confidence_table_max=1,
        restricted_table_max=1,
        control_min=1,
        control_max=2,
        ocr_max=0,
        gold_guard_paths=[fixture["gold_file"]],
        enforce_output_path_guard=False,
    )

    assert report["status"] == "PASS"
    assert report["source_candidate_row_count"] == 5
    assert report["review_row_count"] == 5
    assert report["user_columns_blank"] is True
    assert report["official_denominator_changed"] is False
    assert report["promotion_evidence"] is False
    assert report["existing_gold_csv_overwritten"] is False
    assert report["gold_files_modified"] is False

    rows = read_csv(Path(report["output_artifacts"]["review_csv"]["path"]))
    assert len(rows) == 5
    for row in rows:
        for column in pack.USER_COLUMNS:
            assert row[column] == ""


def test_ready_table_and_false_positive_lanes_do_not_change_denominator(tmp_path: Path):
    fixture = make_fixture(tmp_path)

    report = pack.build_review_pack(
        paths=fixture["paths"],
        output_dir=tmp_path / "pdf_supplemental_gold_review",
        summary_json_path=tmp_path / "rag_pdf_supplemental_gold_review_pack_summary.json",
        pack_size=5,
        expected_source_rows=5,
        high_confidence_table_max=1,
        restricted_table_max=1,
        control_min=1,
        control_max=2,
        ocr_max=0,
        gold_guard_paths=[fixture["gold_file"]],
        enforce_output_path_guard=False,
    )

    assert report["duplicate_query_id_count"] == 0
    assert report["lane_counts"]["READY_SECTION_SUMMARY"] == 1
    assert report["lane_counts"]["READY_RESTRICTED_TABLE_CONTEXT"] == 1
    assert report["lane_counts"]["HIGH_CONFIDENCE_TABLE_CANDIDATE"] == 1
    assert report["lane_counts"]["FALSE_POSITIVE_REFERENCE_CODE"] == 1
    assert report["official_denominator_changed"] is False
    assert report["official_denominator_evidence_created"] is False
    assert report["promotion_artifact_created"] is False

    jsonl_rows = read_jsonl(Path(report["output_artifacts"]["review_jsonl"]["path"]))
    assert all(row["official_denominator_changed"] is False for row in jsonl_rows)
    assert all(row["promotion_evidence"] is False for row in jsonl_rows)
    assert all(row["evidence_role"] == "diagnostic" for row in jsonl_rows)


def test_missing_guardrail_key_fails_closed(tmp_path: Path):
    fixture = make_fixture(tmp_path, missing_guardrail_key=True)

    with pytest.raises(builder.FailClosedInputError) as excinfo:
        pack.build_review_pack(
            paths=fixture["paths"],
            output_dir=tmp_path / "pdf_supplemental_gold_review",
            summary_json_path=tmp_path / "rag_pdf_supplemental_gold_review_pack_summary.json",
            pack_size=5,
            expected_source_rows=5,
            gold_guard_paths=[fixture["gold_file"]],
            enforce_output_path_guard=False,
        )

    assert any("missing guardrail key: promotion_evidence" in blocker for blocker in excinfo.value.blockers)


def test_high_confidence_table_candidate_is_not_table_semantics_success(tmp_path: Path):
    fixture = make_fixture(tmp_path)

    report = pack.build_review_pack(
        paths=fixture["paths"],
        output_dir=tmp_path / "pdf_supplemental_gold_review",
        summary_json_path=tmp_path / "rag_pdf_supplemental_gold_review_pack_summary.json",
        pack_size=5,
        expected_source_rows=5,
        high_confidence_table_max=1,
        restricted_table_max=1,
        control_min=1,
        control_max=2,
        ocr_max=0,
        gold_guard_paths=[fixture["gold_file"]],
        enforce_output_path_guard=False,
    )

    assert report["table_semantics_success_claimed"] is False
    assert report["row_column_value_semantics_claimed"] is False
    rows = read_jsonl(Path(report["output_artifacts"]["review_jsonl"]["path"]))
    high_rows = [row for row in rows if row["review_lane"] == "HIGH_CONFIDENCE_TABLE_CANDIDATE"]
    assert len(high_rows) == 1
    assert high_rows[0]["table_semantics_success_claimed"] is False
    assert high_rows[0]["row_column_value_semantics_claimed"] is False
    assert high_rows[0]["bbox_contract_success_not_claimed"] is True


def make_fixture(tmp_path: Path, *, missing_guardrail_key: bool = False) -> dict[str, object]:
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    paths = builder.CandidateInputPaths(
        synthetic_csv=source_dir / "gold_queries_pdf_supplemental_elec_lh_synthetic_diagnostic.csv",
        answer_quality_json=source_dir / "rag_pdf_supplemental_answer_evidence_quality_audit.json",
        answer_quality_csv=source_dir / "rag_pdf_supplemental_answer_evidence_quality_audit.csv",
        abstain_json=source_dir / "rag_pdf_supplemental_abstain_reason_breakdown.json",
        abstain_csv=source_dir / "rag_pdf_supplemental_abstain_reason_breakdown.csv",
        false_positive_json=source_dir / "rag_pdf_supplemental_table_like_false_positive_classification.json",
        false_positive_csv=source_dir / "rag_pdf_supplemental_table_like_false_positive_classification.csv",
        lh_reclassification_json=source_dir / "rag_pdf_supplemental_lh_not_ready_reclassification.json",
        lh_reclassification_csv=source_dir / "rag_pdf_supplemental_lh_not_ready_reclassification.csv",
        precision_json=source_dir / "rag_pdf_supplemental_table_evidence_candidate_precision_audit.json",
        precision_csv=source_dir / "rag_pdf_supplemental_table_evidence_candidate_precision_audit.csv",
        canary_json=source_dir / "rag_pdf_supplemental_llm_polishing_canary_readiness.json",
        canary_csv=source_dir / "rag_pdf_supplemental_llm_polishing_canary_readiness.csv",
        inventory_json=source_dir / "rag_pdf_supplemental_elec_lh_inventory.json",
        evidence_jsonl=source_dir / "answer_evidence_objects.jsonl",
        draft_jsonl=source_dir / "deterministic_answer_drafts.jsonl",
    )

    synthetic_rows = [
        synthetic_row("q_ready", "elec", "ready.pdf", 1, "paragraph_candidate", "section text"),
        synthetic_row("q_restricted", "elec", "table.pdf", 2, "table_like_block", "formula context"),
        synthetic_row("q_high", "elec", "grid.pdf", 3, "table_like_block", "numeric grid"),
        synthetic_row("q_fp", "lh", "ref.pdf", 4, "table_like_block", "LHCS 10 10 10"),
        synthetic_row("q_abstain", "lh", "weak.pdf", 5, "section_title_candidate", "keyword"),
    ]
    write_csv(paths.synthetic_csv, synthetic_rows, list(synthetic_rows[0]))

    quality_rows = [
        quality_row("q_ready", "elec", "ready.pdf", 1, True, False, "ready:paragraph_block_text_present"),
        quality_row("q_restricted", "elec", "table.pdf", 2, True, True, "ready:table_like_candidate_with_text"),
        quality_row("q_high", "elec", "grid.pdf", 3, True, True, "ready:table_like_candidate_with_text"),
        quality_row("q_fp", "lh", "ref.pdf", 4, False, True, "keyword_only_without_sufficient_context"),
        quality_row("q_abstain", "lh", "weak.pdf", 5, False, True, "keyword_only_without_sufficient_context"),
    ]
    write_csv(paths.answer_quality_csv, quality_rows, list(quality_rows[0]))

    abstain_rows = [
        abstain_row("q_abstain", "TABLE_LIKE_WITHOUT_ROW_COLUMN_VALUE"),
        abstain_row("q_fp", "ONLY_KEYWORD_OR_LABEL_PRESENT"),
    ]
    write_csv(paths.abstain_csv, abstain_rows, list(abstain_rows[0]))

    false_positive_rows = [
        false_positive_row("q_restricted", "BULLET_OR_FORMULA_CONTEXT"),
        false_positive_row("q_high", "REAL_NUMERIC_GRID_TABLE"),
        false_positive_row("q_fp", "REFERENCE_CODE_FRAGMENT"),
    ]
    write_csv(paths.false_positive_csv, false_positive_rows, list(false_positive_rows[0]))

    lh_rows = [
        {
            "query_id": "q_fp",
            "false_positive_classification": "REFERENCE_CODE_FRAGMENT",
            "revised_fix_lane": "REFERENCE_CODE_FRAGMENT_FILTER_REQUIRED",
            "section_context": "LHCS reference",
        }
    ]
    write_csv(paths.lh_reclassification_csv, lh_rows, list(lh_rows[0]))

    precision_rows = [
        precision_row("q_restricted", "BULLET_OR_FORMULA_CONTEXT", "EXTRACTIVE_CONTEXT_ONLY"),
        precision_row("q_high", "REAL_NUMERIC_GRID_TABLE", "HIGH_CONFIDENCE_TABLE_EVIDENCE_OBJECT_CANDIDATE"),
    ]
    write_csv(paths.precision_csv, precision_rows, list(precision_rows[0]))

    canary_rows = [
        canary_row("q_ready", "SAFE_SECTION_SUMMARY_CANARY_READY"),
        canary_row("q_restricted", "RESTRICTED_TABLE_CONTEXT_CANARY_READY"),
        canary_row("q_fp", "ABSTAIN_NO_CANARY"),
    ]
    write_csv(paths.canary_csv, canary_rows, list(canary_rows[0]))

    evidence_rows = [
        evidence_row("q_ready", "elec", "ready.pdf", 1, False),
        evidence_row("q_restricted", "elec", "table.pdf", 2, True),
        evidence_row("q_high", "elec", "grid.pdf", 3, True),
        evidence_row("q_fp", "lh", "ref.pdf", 4, True),
        evidence_row("q_abstain", "lh", "weak.pdf", 5, True),
    ]
    write_jsonl(paths.evidence_jsonl, evidence_rows)
    draft_rows = [
        draft_row("q_ready", "Section summary draft", ""),
        draft_row("q_restricted", "Restricted table-context draft", ""),
        draft_row("q_high", "High-confidence table candidate draft", ""),
        draft_row("q_fp", "", "keyword_only_without_sufficient_context"),
        draft_row("q_abstain", "", "TABLE_LIKE_WITHOUT_ROW_COLUMN_VALUE"),
    ]
    write_jsonl(paths.draft_jsonl, draft_rows)

    for path in [
        paths.answer_quality_json,
        paths.abstain_json,
        paths.false_positive_json,
        paths.lh_reclassification_json,
        paths.precision_json,
        paths.canary_json,
        paths.inventory_json,
    ]:
        payload = source_report_payload()
        if missing_guardrail_key and path == paths.inventory_json:
            payload.pop("promotion_evidence")
        write_json(path, payload)

    gold_file = tmp_path / "gold_queries_pdf_v0.csv"
    gold_file.write_text("query_id,query\nold,keep\n", encoding="utf-8")
    return {"paths": paths, "gold_file": gold_file}


def source_report_payload() -> dict[str, object]:
    return {
        "schema_version": "fixture",
        "status": "PASS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "official_denominator_changed": False,
        "codex_gold_policy_decision_applied": False,
        "pdf_c7_policy_decision_applied": False,
        "external_cloud_llm_run": False,
        "local_llm_run": False,
        "live_llm_answer_generation_run": False,
        "optional_judge_run": False,
        "retrieval_tuning_applied": False,
        "reranking_applied": False,
        "parser_expansion_applied": False,
        "db_mutation_applied": False,
        "searchunit_mutation_applied": False,
        "candidate_artifact_changed": False,
        "immutable_baseline_changed": False,
        "bbox_contract_success_not_claimed": True,
        "table_semantics_success_not_claimed": True,
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
    }


def synthetic_row(query_id: str, dataset: str, file_name: str, page_no: int, anchor_type: str, anchor_text: str) -> dict[str, object]:
    return {
        "query_id": query_id,
        "dataset_source": dataset,
        "file_name": file_name,
        "relative_path": f"ai/eval/datasets/{dataset}/{file_name}",
        "query": f"{file_name} review query",
        "anchor_text": anchor_text,
        "anchor_type": anchor_type,
        "expected_location_type": "pdf",
        "parser_derived_page_no": page_no,
        "parser_derived_section_title": "Section",
        "synthetic_diagnostic": True,
        "label_status": "diagnostic_only",
        "promotion_evidence": False,
    }


def quality_row(query_id: str, dataset: str, file_name: str, page_no: int, ready: bool, table_like: bool, reason: str) -> dict[str, object]:
    return {
        "query_id": query_id,
        "dataset_source": dataset,
        "file_name": file_name,
        "page_no": page_no,
        "anchor_type": "table_like_block" if table_like else "paragraph_candidate",
        "query": f"{file_name} review query",
        "answer_allowed": True,
        "evidence_ready": ready,
        "keyword_only_risk": not ready,
        "table_like_context_candidate": table_like,
        "ocr_needed_candidate": False,
        "evidence_text_chars": 120 if ready else 12,
        "evidence_context_chars": 240 if ready else 20,
        "reason": reason,
    }


def abstain_row(query_id: str, reason: str) -> dict[str, object]:
    return {
        "query_id": query_id,
        "dataset_source": "lh",
        "anchor_type": "table_like_block",
        "file_name": "weak.pdf",
        "page_no": 5,
        "primary_abstain_reason": reason,
        "draft_abstain_reason": reason,
        "quality_reason": "keyword_only_without_sufficient_context",
    }


def false_positive_row(query_id: str, classification: str) -> dict[str, object]:
    return {
        "query_id": query_id,
        "dataset_source": "elec",
        "file_name": "table.pdf",
        "page_no": 1,
        "classification": classification,
        "classification_reason": "fixture",
    }


def precision_row(query_id: str, classification: str, quality: str) -> dict[str, object]:
    return {
        "query_id": query_id,
        "false_positive_classification": classification,
        "candidate_quality": quality,
        "candidate_quality_reason": "fixture",
        "table_semantics_success_claimed": False,
    }


def canary_row(query_id: str, lane: str) -> dict[str, object]:
    return {
        "query_id": query_id,
        "answer_shape": "PDF_SECTION_WITH_SUMMARY",
        "canary_lane": lane,
        "canary_reason": "fixture",
    }


def evidence_row(query_id: str, dataset: str, file_name: str, page_no: int, table_like: bool) -> dict[str, object]:
    return {
        "query_id": query_id,
        "dataset_source": dataset,
        "file_name": file_name,
        "query": f"{file_name} review query",
        "evidence_role": "diagnostic",
        "promotion_evidence": False,
        "official_denominator_changed": False,
        "codex_gold_policy_decision_applied": False,
        "pdf_c7_policy_decision_applied": False,
        "evidence_text_excerpt": f"{query_id} evidence text",
        "nearby_context": f"{query_id} nearby context",
        "section_title": "Section",
        "table_like_context_candidate": table_like,
        "citation": {
            "page_no": page_no,
            "bbox": "[1, 2, 3, 4]",
            "relative_path": f"ai/eval/datasets/{dataset}/{file_name}",
        },
        "bbox_contract_success_not_claimed": True,
        "table_semantics_success_not_claimed": True,
    }


def draft_row(query_id: str, answer: str, reason: str) -> dict[str, object]:
    return {
        "query_id": query_id,
        "answer_draft": answer,
        "abstain_reason": reason,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "external_cloud_llm_run": False,
        "local_llm_run": False,
        "live_llm_answer_generation_run": False,
        "optional_judge_run": False,
    }


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
