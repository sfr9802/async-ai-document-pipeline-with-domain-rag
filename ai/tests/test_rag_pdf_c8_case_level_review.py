from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai" / "scripts" / "rag_pdf_c8_case_level_review.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


review_module = load_module("rag_pdf_c8_case_level_review", MODULE_PATH)


def test_case_level_review_groups_decisions_without_tuning(tmp_path: Path):
    manifest_path = tmp_path / "reviewed.csv"
    manifest_path.write_text("query_id\n", encoding="utf-8")

    payload = review_module.build_case_level_review_report(
        rank_probe=rank_probe_report(),
        case_investigation=case_investigation_report(),
        case_pack=case_pack_report(),
        reviewed_diagnostic=reviewed_diagnostic_report(),
        reviewed_manifest_rows=manifest_rows(),
        rank_probe_path=Path("rank.json"),
        case_investigation_path=Path("investigation.json"),
        case_pack_path=Path("case_pack.json"),
        reviewed_diagnostic_path=Path("reviewed.json"),
        reviewed_manifest_path=manifest_path,
    )

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert payload["retrieval_tuning_executed"] is False
    assert payload["broad_tuning_recommended"] is False
    assert payload["case_count"] == 7
    assert payload["next_action_counts"] == {
        "FILE_DISAMBIGUATION_REVIEW": 1,
        "LEXICAL_EXACT_PHRASE_PROBE_REVIEW": 1,
        "QUERY_SURFACE_REVIEW": 5,
    }
    assert payload["decision_counts"] == {
        "REQUIRE_EMBEDDING_SURFACE_REVIEW": 1,
        "REQUIRE_FILE_DISAMBIGUATION_POLICY": 1,
        "REWRITE_QUERY_SURFACE": 5,
    }
    assert payload["proposed_query_rewrite_count"] == 5
    assert payload["query_surface_audit_counts"] == {
        "rewrite_count": 5,
        "changed_from_original_count": 5,
        "filename_leak_count": 0,
        "document_version_leak_count": 0,
        "pdf_extension_leak_count": 0,
        "latin_letter_count": 0,
        "korean_surface_count": 5,
    }
    assert payload["gold_binding_review_required_count"] == 0
    assert payload["expected_page_review_required_count"] == 1
    assert payload["file_disambiguation_policy_required_count"] == 1
    assert payload["embedding_surface_review_required_count"] == 1

    query_row = row_by_id(payload, "gq_auto_014")
    assert query_row["case_decision"] == "REWRITE_QUERY_SURFACE"
    assert query_row["proposed_query_surface"] == "달러 기준 1인당 국내총생산 표를 찾아줘"
    assert query_row["query_surface_audit"]["changed_from_original"] is True
    assert query_row["query_surface_audit"]["leaks_expected_file_name"] is False
    assert query_row["source_policy_fields"]["pdf_review_label"] is None
    assert query_row["review_requirements"]["query_surface_rewrite"] is True
    assert "query/label surface" in query_row["why_not_broad_tuning"]

    file_row = row_by_id(payload, "gq_pdf_section_question_002")
    assert file_row["case_decision"] == "REQUIRE_FILE_DISAMBIGUATION_POLICY"
    assert file_row["proposed_query_surface"] is None
    assert file_row["review_requirements"]["file_disambiguation_policy"] is True

    lexical_row = row_by_id(payload, "gq_pdf_section_question_003")
    assert lexical_row["case_decision"] == "REQUIRE_EMBEDDING_SURFACE_REVIEW"
    assert lexical_row["secondary_case_decisions"] == ["REQUIRE_EXPECTED_PAGE_REVIEW"]
    assert lexical_row["review_requirements"]["expected_page_review"] is True


def test_case_level_review_blocks_promoted_rank_probe(tmp_path: Path):
    manifest_path = tmp_path / "reviewed.csv"
    manifest_path.write_text("query_id\n", encoding="utf-8")
    promoted = rank_probe_report()
    promoted["promotion_evidence"] = True

    payload = review_module.build_case_level_review_report(
        rank_probe=promoted,
        case_investigation=case_investigation_report(),
        case_pack=case_pack_report(),
        reviewed_diagnostic=reviewed_diagnostic_report(),
        reviewed_manifest_rows=manifest_rows(),
        rank_probe_path=Path("rank.json"),
        case_investigation_path=Path("investigation.json"),
        case_pack_path=Path("case_pack.json"),
        reviewed_diagnostic_path=Path("reviewed.json"),
        reviewed_manifest_path=manifest_path,
    )

    assert payload["status"] == "BLOCKED_WITH_REASON"
    assert "C8.2 rank probe must keep promotion_evidence=false" in payload["blockers"]


def test_case_level_review_requires_exact_five_one_one_grouping(tmp_path: Path):
    manifest_path = tmp_path / "reviewed.csv"
    manifest_path.write_text("query_id\n", encoding="utf-8")
    rank_probe = rank_probe_report()
    rank_probe["rows"][0]["rank_probe_next_action"] = "RANK_DEPTH_REVIEW"

    payload = review_module.build_case_level_review_report(
        rank_probe=rank_probe,
        case_investigation=case_investigation_report(),
        case_pack=case_pack_report(),
        reviewed_diagnostic=reviewed_diagnostic_report(),
        reviewed_manifest_rows=manifest_rows(),
        rank_probe_path=Path("rank.json"),
        case_investigation_path=Path("investigation.json"),
        case_pack_path=Path("case_pack.json"),
        reviewed_diagnostic_path=Path("reviewed.json"),
        reviewed_manifest_path=manifest_path,
    )

    assert payload["status"] == "BLOCKED_WITH_REASON"
    assert any("source_next_action counts" in blocker for blocker in payload["blockers"])


def row_by_id(payload: dict, query_id: str) -> dict:
    return next(row for row in payload["rows"] if row["query_id"] == query_id)


def rank_probe_report() -> dict:
    rows = [
        row("gq_pdf_page_lookup_003", "목 차", "QUERY_SURFACE_REVIEW", "SHORT_OR_GENERIC_QUERY_SURFACE_TOO_WEAK", 5, 5, 63, 63, 45, 12, 5),
        row("gq_pdf_section_question_002", "수입(CIF)", "FILE_DISAMBIGUATION_REVIEW", "CROSS_DOCUMENT_REPEATED_TABLE_LABEL_FILE_RECALL", 13, 13, 13, 49, 13, 26, 12),
        row("gq_pdf_section_question_003", "2024 6,836.1", "LEXICAL_EXACT_PHRASE_PROBE_REVIEW", "EXPECTED_PAGE_PRESENT_BUT_DENSE_RANKING_MISS", 1, 1, None, None, None, 2, 0),
        row("gq_auto_009", "기간중", "QUERY_SURFACE_REVIEW", "SHORT_OR_GENERIC_QUERY_SURFACE_TOO_WEAK", 1, 1, 20, 20, 14, 24, 8),
        row("gq_auto_014", "달러", "QUERY_SURFACE_REVIEW", "SHORT_OR_GENERIC_QUERY_SURFACE_TOO_WEAK", 1, 1, 31, 31, 21, 221, 63),
        row("gq_auto_019", "기간중", "QUERY_SURFACE_REVIEW", "SHORT_OR_GENERIC_QUERY_SURFACE_TOO_WEAK", 1, 1, 17, 17, 11, 24, 8),
        row("gq_auto_025", "목 차", "QUERY_SURFACE_REVIEW", "SHORT_OR_GENERIC_QUERY_SURFACE_TOO_WEAK", 1, 1, 29, None, 23, 12, 5),
    ]
    return base_report(
        phase="C8.2",
        case_count=7,
        rows=rows,
        refined_next_action_counts={
            "FILE_DISAMBIGUATION_REVIEW": 1,
            "LEXICAL_EXACT_PHRASE_PROBE_REVIEW": 1,
            "QUERY_SURFACE_REVIEW": 5,
        },
        broad_tuning_recommended=False,
    )


def case_investigation_report() -> dict:
    rows = []
    for rank_row in rank_probe_report()["rows"]:
        rows.append(
            {
                "query_id": rank_row["query_id"],
                "query": rank_row["query"],
                "bucket": rank_row["bucket"],
                "root_cause": rank_row["source_root_cause"],
                "refined_next_action": rank_row["rank_probe_next_action"],
                "same_file_hit_ranks": [1],
                "same_page_hit_ranks": [],
                "evidence_summary": f"{rank_row['source_root_cause']}; expected_page_units=1.",
            }
        )
    return base_report(phase="C8.1", case_count=7, rows=rows, broad_tuning_recommended=False)


def case_pack_report() -> dict:
    cases = []
    for rank_row in rank_probe_report()["rows"]:
        cases.append(
            {
                "query_id": rank_row["query_id"],
                "query": rank_row["query"],
                "bucket": rank_row["bucket"],
                "next_action": "FILE_RECALL_INVESTIGATION"
                if rank_row["query_id"] == "gq_pdf_section_question_002"
                else "PAGE_RANKING_INVESTIGATION",
                "same_file_hit_ranks": [1],
                "same_page_hit_ranks": [],
            }
        )
    return base_report(phase="C8", case_count=7, cases=cases, broad_tuning_recommended=False)


def reviewed_diagnostic_report() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "table_specific_retrieval_proven": False,
        "immutable_baseline_changed": False,
        "xlsx_candidate_artifact_changed": False,
        "rows": [
            {
                "query_id": query_id,
                "expected_file_name": f"{query_id}.pdf",
            }
            for query_id in query_ids()
        ],
    }


def manifest_rows() -> list[dict[str, str]]:
    return [
        {
            "query_id": query_id,
            "query": query,
            "bucket": "pdf_page_lookup",
            "expected_file_name": f"{query_id}.pdf",
            "expected_document_version_id": "docv",
            "expected_page_no": "3",
            "expected_physical_page_index": "2",
            "expected_bbox": "[1,2,3,4]",
        }
        for query_id, query in [
            ("gq_pdf_page_lookup_003", "목 차"),
            ("gq_pdf_section_question_002", "수입(CIF)"),
            ("gq_pdf_section_question_003", "2024 6,836.1"),
            ("gq_auto_009", "기간중"),
            ("gq_auto_014", "달러"),
            ("gq_auto_019", "기간중"),
            ("gq_auto_025", "목 차"),
        ]
    ]


def row(
    query_id: str,
    query: str,
    action: str,
    root_cause: str,
    file_rank: int | None,
    docv_rank: int | None,
    page_rank: int | None,
    exact_rank: int | None,
    page_group_rank: int | None,
    exact_units: int,
    competing_pages: int,
) -> dict:
    return {
        "query_id": query_id,
        "query": query,
        "bucket": "pdf_page_lookup",
        "source_root_cause": root_cause,
        "rank_probe_next_action": action,
        "expected_document_version_id": "docv",
        "expected_file_name": f"{query_id}.pdf",
        "expected_page_no": "3",
        "expected_physical_page_index": "2",
        "expected_bbox": "[1,2,3,4]",
        "vector_probe": {
            "expected_file_first_rank": file_rank,
            "expected_docv_first_rank": docv_rank,
            "expected_page_first_rank": page_rank,
            "expected_exact_bbox_first_rank": exact_rank,
        },
        "page_aggregation_probe": {"expected_page_group_rank": page_group_rank},
        "lexical_probe": {
            "corpus_exact_phrase_unit_count": exact_units,
            "competing_exact_phrase_page_count": competing_pages,
            "expected_page_exact_phrase_present": True,
        },
        "broad_tuning_recommended": False,
    }


def base_report(**overrides) -> dict:
    report = {
        "status": "PASS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "pdf_candidate_namespace": "rag-ingestion-v2-pdf-candidate-v1",
        "pdf_artifact_dir": "rag-data-pdf-candidate-v1",
        "retrieval_tuning_executed": False,
        "table_specific_retrieval_proven": False,
        "immutable_baseline_changed": False,
        "xlsx_candidate_artifact_changed": False,
    }
    report.update(overrides)
    return report


def query_ids() -> list[str]:
    return [
        "gq_pdf_page_lookup_003",
        "gq_pdf_section_question_002",
        "gq_pdf_section_question_003",
        "gq_auto_009",
        "gq_auto_014",
        "gq_auto_019",
        "gq_auto_025",
    ]
