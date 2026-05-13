from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai" / "scripts" / "rag_pdf_gold_policy_review.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_pdf_gold_policy_review", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


c7_module = load_module()


def test_c7_classifies_failed_queries_and_writes_decision_template_rows(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)
    c6 = c6_report([
        c6_row(
            "q_bbox",
            "pdf_page_lookup",
            "2025. 12.",
            "PDF_BBOX_POLICY_MISMATCH",
            primary="parser_chunk_contract",
            expected_chunk_type="paragraph",
            expected_bbox="[1,2,3,4]",
            evidence={"page_hit_missing_bbox_ranks": [2], "chunk_type_mismatch_ranks": [2]},
            hits=[hit(2, chunk_type="page", page_match=True, chunk_match=False)],
        ),
        c6_row(
            "q_table",
            "pdf_table_lookup",
            "518.4",
            "PDF_TABLE_GOLD_BINDING_MISMATCH",
            primary="parser_chunk_contract",
            expected_chunk_type="paragraph",
            expected_bbox="[1,2,3,4]",
            hits=[hit(1)],
        ),
        c6_row(
            "q_page",
            "pdf_section_question",
            "등으로 상승",
            "PDF_CHUNK_GRANULARITY_ISSUE",
            primary="parser_chunk_contract",
            expected_chunk_type="page",
            expected_bbox="",
            hits=[hit(1, chunk_type="paragraph", page_match=True, location_match=True, chunk_match=False)],
        ),
        c6_row(
            "q_generic",
            "pdf_page_lookup",
            "목 차",
            "PDF_EXPECTED_PAGE_ABSENT_IN_TOP10",
            primary="gold_policy",
            expected_chunk_type="paragraph",
            expected_bbox="[1,2,3,4]",
            hits=[hit(1, file_name="other.pdf", file_match=False, docv_match=False)],
        ),
        c6_row(
            "q_match",
            "pdf_page_lookup",
            "match",
            "MATCHED",
            primary="matched",
            expected_chunk_type="paragraph",
            expected_bbox="[1,2,3,4]",
            hits=[hit(1, page_match=True, bbox_overlap=True, location_match=True)],
            location_match=True,
        ),
    ])

    payload, template_rows = c7_module.build_review(
        c6_report=c6,
        c5_report=c5_report(),
        gold_rows=gold_rows(),
        c6_path=paths["c6"],
        c5_path=paths["c5"],
        gold_path=paths["gold"],
        decisions_template_path=paths["template"],
    )

    assert payload["status"] == "NEEDS_POLICY_DECISION"
    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert payload["namespace"] == c7_module.PDF_INDEX_VERSION
    assert payload["retrieval_execution"] == "not_run_by_this_script"
    assert payload["indexing_execution"] == "not_run_by_this_script"
    assert payload["promotion_execution"] == "not_run_by_this_script"
    assert payload["review_scope"]["failed_query_count"] == 4
    assert payload["review_scope"]["matched_control_count"] == 1
    assert payload["classification_counts"]["bbox_policy_review_required"] == 1
    assert payload["classification_counts"]["table_gold_policy_review_required"] == 1
    assert payload["classification_counts"]["page_only_evidence_policy_review_required"] == 1
    assert payload["classification_counts"]["query_surface_or_answerability_review_required"] == 1
    assert payload["all_classification_counts"]["diagnostic_only_exclude_candidate"] == 4
    assert payload["human_decision_required_count"] == 4
    assert payload["codex_diagnostic_only_candidate_count"] == 4
    assert payload["follow_up_c6_reclassification_plan"]["old_c6_mutated"] is False
    assert payload["gate_and_baseline_status"]["immutable_baseline_changed"] is False
    assert payload["gate_and_baseline_status"]["xlsx_candidate_artifact_changed"] is False
    assert len(template_rows) == 4
    assert template_rows[0]["allowed_user_decision_scope"] == (
        "gold_policy|expected_evidence_semantics|answerability_or_relevance_label"
    )
    assert template_rows[0]["user_gold_policy_decision"] == ""


def test_c7_fails_closed_on_promotion_evidence_true(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)
    c6 = c6_report([])
    c6["promotion_evidence"] = True

    payload, template_rows = c7_module.build_review(
        c6_report=c6,
        c5_report=c5_report(),
        gold_rows=gold_rows(),
        c6_path=paths["c6"],
        c5_path=paths["c5"],
        gold_path=paths["gold"],
        decisions_template_path=paths["template"],
    )

    assert payload["status"] == "FAIL"
    assert "C6 report must keep promotion_evidence=false" in payload["blockers"]
    assert template_rows == []


def test_c7_csv_template_writer(tmp_path: Path):
    path = tmp_path / "template.csv"
    rows = [
        {
            "query_id": "q1",
            "bucket": "pdf_page_lookup",
            "query": "목 차",
            "current_c7_classification": "query_surface_or_answerability_review_required",
        }
    ]

    c7_module.write_csv(path, rows)

    text = path.read_text(encoding="utf-8")
    assert "query_id,bucket,query,current_c7_classification" in text
    assert "q1,pdf_page_lookup,목 차,query_surface_or_answerability_review_required" in text


def fixture_paths(tmp_path: Path, monkeypatch) -> dict[str, Path]:
    root = tmp_path
    ai_worker = root / "ai"
    monkeypatch.setattr(c7_module, "ROOT", root)
    monkeypatch.setattr(c7_module, "AI_WORKER", ai_worker)
    paths = {
        "c6": ai_worker / "eval" / "reports" / "rag-ingestion" / "rag_pdf_vector_quality_breakdown.json",
        "c5": ai_worker / "eval" / "reports" / "rag-ingestion" / "rag_retrieval_eval_pdf_vector_diagnostic_report.json",
        "gold": ai_worker / "eval" / "eval_queries" / "gold_queries_pdf_v0.csv",
        "template": ai_worker / "eval" / "reports" / "rag-ingestion" / "rag_pdf_gold_policy_review_decisions_template.csv",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    return paths


def c6_report(rows: list[dict]) -> dict:
    failed_rows = [row for row in rows if row["failure_type"] != "MATCHED"]
    return {
        "status": "PASS_WITH_WARNINGS",
        "phase": "C6",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_backend": "vector",
        "namespace": c7_module.PDF_INDEX_VERSION,
        "index_version": c7_module.PDF_INDEX_VERSION,
        "artifact_dir": c7_module.PDF_ARTIFACT_DIR,
        "c7_ready": True,
        "failed_query_count": len(failed_rows),
        "unknown_failure_count": 0,
        "gold_policy_candidate_query_ids": [row["query_id"] for row in failed_rows],
        "parser_chunk_contract_candidate_query_ids": [
            row["query_id"] for row in failed_rows if row["primary_disposition"] == "parser_chunk_contract"
        ],
        "query_breakdown": rows,
        "classified_failed_query_rows": failed_rows,
    }


def c5_report() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "namespace": c7_module.PDF_INDEX_VERSION,
        "index_version": c7_module.PDF_INDEX_VERSION,
        "artifact_dir": c7_module.PDF_ARTIFACT_DIR,
        "allowUnscoped": False,
        "immutable_baseline_changed": False,
        "xlsx_candidate_artifact_changed": False,
        "query_results": [],
    }


def c6_row(
    query_id: str,
    bucket: str,
    query: str,
    failure_type: str,
    *,
    primary: str,
    expected_chunk_type: str,
    expected_bbox: str,
    evidence: dict | None = None,
    hits: list[dict],
    location_match: bool = False,
) -> dict:
    evidence_payload = {
        "top_k_count": len(hits),
        "file_hit_count": 1,
        "document_version_hit_count": 1,
        "expected_page_hit_count": 0,
        "bbox_overlap_hit_count": 0,
        "first_expected_file_rank": 1,
        "first_expected_docv_rank": 1,
        "first_expected_page_rank": None,
        "first_bbox_overlap_rank": None,
        "page_hit_missing_bbox_ranks": [],
        "chunk_type_mismatch_ranks": [],
        "location_match_without_identity_ranks": [],
        "correct_page_wrong_chunk_type_count": 0,
        "supporting_hit_ranks": [hit["rank"] for hit in hits[:3]],
    }
    evidence_payload.update(evidence or {})
    return {
        "query_id": query_id,
        "bucket": bucket,
        "query": query,
        "label_status": "bound",
        "failure_reason": None if failure_type == "MATCHED" else "expected_page_not_found",
        "failure_type": failure_type,
        "failure_types": [failure_type],
        "primary_disposition": primary,
        "secondary_dispositions": [],
        "hit_rank": 1 if hits else None,
        "location_rank": 1 if location_match else None,
        "expected": {
            "file_name": "sample.pdf",
            "document_version_id": "docv_pdf",
            "chunk_type": expected_chunk_type,
            "location_type": "pdf",
            "physical_page_index": "0",
            "page_no": "1",
            "page_label": "1",
            "bbox": expected_bbox,
        },
        "evidence": evidence_payload,
        "rationale": "fixture rationale",
        "next_action": "fixture next action",
        "top_hits": hits,
        "supporting_hits": hits[:3],
    }


def hit(
    rank: int,
    *,
    file_name: str = "sample.pdf",
    chunk_type: str = "paragraph",
    file_match: bool = True,
    docv_match: bool = True,
    chunk_match: bool = True,
    page_match: bool = False,
    bbox_overlap: bool = False,
    location_match: bool = False,
) -> dict:
    return {
        "rank": rank,
        "search_unit_id": f"su_{rank}",
        "score": 1.0 / rank,
        "source_file_name": file_name,
        "source_file_type": "PDF",
        "chunk_type": chunk_type,
        "page_no": 1 if page_match else 2,
        "physical_page_index": 0 if page_match else 1,
        "bbox_present": bbox_overlap,
        "citation_text": f"{file_name} > p.{1 if page_match else 2}",
        "match_breakdown": {
            "identity_match": file_match and docv_match and chunk_match,
            "location_match": location_match,
            "file_match": file_match,
            "document_version_match": docv_match,
            "chunk_type_match": chunk_match,
            "location_type_match": True,
            "pdf_page_match": page_match,
            "pdf_bbox_overlap": bbox_overlap,
            "pdf_exact_bbox": bbox_overlap,
            "indexing_contract_match": True,
            "required_index_version_match": True,
            "embedding_status_match": True,
        },
    }


def gold_rows() -> list[dict[str, str]]:
    return [
        gold_row("q_bbox", "pdf_page_lookup", "2025. 12.", "paragraph", "[1,2,3,4]"),
        gold_row("q_table", "pdf_table_lookup", "518.4", "paragraph", "[1,2,3,4]"),
        gold_row("q_page", "pdf_section_question", "등으로 상승", "page", ""),
        gold_row("q_generic", "pdf_page_lookup", "목 차", "paragraph", "[1,2,3,4]"),
        gold_row("q_match", "pdf_page_lookup", "match", "paragraph", "[1,2,3,4]"),
    ]


def gold_row(
    query_id: str,
    bucket: str,
    query: str,
    expected_chunk_type: str,
    expected_bbox: str,
) -> dict[str, str]:
    return {
        "query_id": query_id,
        "bucket": bucket,
        "query": query,
        "expected_file_name": "sample.pdf",
        "expected_document_version_id": "docv_pdf",
        "expected_chunk_type": expected_chunk_type,
        "expected_location_type": "pdf",
        "expected_physical_page_index": "0",
        "expected_page_no": "1",
        "expected_page_label": "1",
        "expected_bbox": expected_bbox,
        "expected_answer_text": query,
        "must_contain_terms": query,
        "expected_table_id": "",
        "label_status": "bound",
        "notes": "auto-bound seed from current normalized PDF search_unit" if query_id.startswith("q_generic") else "",
    }
