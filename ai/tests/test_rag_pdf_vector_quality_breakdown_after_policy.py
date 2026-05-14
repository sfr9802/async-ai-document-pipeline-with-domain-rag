from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai" / "scripts" / "rag_pdf_vector_quality_breakdown_after_policy.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


c61_module = load_module("rag_pdf_vector_quality_breakdown_after_policy", MODULE_PATH)


def test_after_policy_reclassifies_table_pending_and_policy_successes():
    payload = c61_module.build_after_policy_breakdown(
        raw_breakdown=raw_breakdown(),
        policy_overlay=policy_overlay(),
        reviewed_manifest_rows=manifest_rows(),
        raw_breakdown_path=Path("c6.json"),
        policy_overlay_path=Path("overlay.json"),
        reviewed_manifest_path=Path("reviewed.csv"),
        expected_true_failure_count=1,
    )

    assert payload["status"] == "PASS"
    assert payload["policy_overlay_applied"] is True
    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert payload["raw_query_count"] == 10
    assert payload["table_deferred_count"] == 6
    assert payload["policy_resolved_count"] == 8
    assert payload["policy_unresolved_count"] == 0
    assert payload["true_retrieval_ranking_failure_count"] == 1
    assert payload["retrieval_tuning_candidate_ready_for_reviewed_non_table_set"] is True
    assert payload["retrieval_tuning_candidate_ready_for_all_pdf"] is False


def test_after_policy_fails_closed_when_overlay_unresolved():
    overlay = policy_overlay()
    overlay["unresolved_candidate_count"] = 1

    payload = c61_module.build_after_policy_breakdown(
        raw_breakdown=raw_breakdown(),
        policy_overlay=overlay,
        reviewed_manifest_rows=manifest_rows(),
        raw_breakdown_path=Path("c6.json"),
        policy_overlay_path=Path("overlay.json"),
        reviewed_manifest_path=Path("reviewed.csv"),
        expected_true_failure_count=1,
    )

    assert payload["status"] == "FAIL"
    assert "policy overlay unresolved_candidate_count must be 0" in payload["blockers"]


def test_after_policy_fails_closed_when_manifest_missing_raw_query():
    rows = manifest_rows()
    rows = [row for row in rows if row["query_id"] != "q-fail"]

    payload = c61_module.build_after_policy_breakdown(
        raw_breakdown=raw_breakdown(),
        policy_overlay=policy_overlay(),
        reviewed_manifest_rows=rows,
        raw_breakdown_path=Path("c6.json"),
        policy_overlay_path=Path("overlay.json"),
        reviewed_manifest_path=Path("reviewed.csv"),
        expected_true_failure_count=1,
    )

    assert payload["status"] == "FAIL"
    assert "reviewed manifest must include every raw C6 query_id: q-fail" in payload["blockers"]


def raw_breakdown() -> dict:
    rows = [classified("q-matched", "MATCHED", "pdf_page_lookup")]
    rows.append(classified("q-bbox", "PDF_BBOX_POLICY_MISMATCH", "pdf_page_lookup"))
    rows.append(classified("q-chunk", "PDF_CHUNK_GRANULARITY_ISSUE", "pdf_section_question"))
    rows.extend(classified(f"q-table-{idx}", "PDF_TABLE_GOLD_BINDING_MISMATCH", "pdf_table_lookup") for idx in range(6))
    rows.append(classified("q-fail", "PDF_EXPECTED_PAGE_ABSENT_IN_TOP10", "pdf_page_lookup"))
    return {
        "status": "PASS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "unknown_failure_count": 0,
        "classified_query_rows": rows,
    }


def policy_overlay() -> dict:
    rows = [
        overlay_row("q-bbox", "ACCEPT_PAGE_WITH_OPTIONAL_BBOX", True),
        overlay_row("q-chunk", "ACCEPT_CHUNK_TYPE_POLICY_RELABEL", True),
    ]
    rows.extend(overlay_row(f"q-table-{idx}", "DEFER_TO_TABLE_EXTRACTION", False) for idx in range(6))
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "unresolved_candidate_count": 0,
        "rows": rows,
    }


def manifest_rows() -> list[dict[str, str]]:
    rows = [manifest("q-matched", "positive_reviewed", "true")]
    rows.append(manifest("q-bbox", "positive_reviewed", "true"))
    rows.append(manifest("q-chunk", "positive_reviewed", "true"))
    rows.extend(manifest(f"q-table-{idx}", "table_deferred", "false") for idx in range(6))
    rows.append(manifest("q-fail", "positive_reviewed", "true"))
    return rows


def classified(query_id: str, failure_type: str, bucket: str) -> dict:
    return {
        "query_id": query_id,
        "bucket": bucket,
        "query": "query",
        "failure_type": failure_type,
        "c5_failure_reason": None if failure_type == "MATCHED" else "expected_page_not_found",
        "location_match": failure_type == "MATCHED",
        "expected": {"file_name": "sample.pdf", "page_no": 1},
    }


def overlay_row(query_id: str, decision: str, eligible: bool) -> dict:
    return {
        "query_id": query_id,
        "final_decision": decision,
        "positive_metric_eligible": eligible,
    }


def manifest(query_id: str, label: str, eligible: str) -> dict[str, str]:
    return {
        "query_id": query_id,
        "pdf_review_label": label,
        "review_decision": "KEEP_REVIEWED_POSITIVE",
        "pdf_match_policy": "EXACT_PAGE_AND_BBOX",
        "positive_metric_eligible": eligible,
    }
