from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-worker" / "eval" / "harness" / "pdf_review_application.py"


def load_module():
    spec = importlib.util.spec_from_file_location("pdf_review_application_for_tests", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


app = load_module()


def test_review_pack_discovery_selects_latest_merged_file_lookup_pack(tmp_path: Path):
    review_dir = tmp_path / "review"
    old_pack = write_pack(review_dir / "pdf_supplemental_gold_review_pack_v3_manual_curated.csv", [row("v3-1")])
    selected_pack = write_pack(
        review_dir / "pdf_gold_review_pack_manual_v1_with_file_lookup.csv",
        [
            row("content-1"),
            file_row(
                "file-1",
                user_gold_decision="",
                user_answerability_label="",
                user_relevance_label="",
                user_expected_evidence_policy="",
                user_denominator_policy="",
                user_issue_tags="",
                user_notes="",
            ),
        ],
    )
    old_pack.touch()
    selected_pack.touch()

    selected = app.select_review_pack(review_dir)

    assert selected["path"] == selected_pack
    assert selected["complete_reviewed_row_count"] == 0
    assert selected["has_file_lookup_companion"] is True
    assert selected["file_lookup_row_count"] == 1


def test_required_review_labels_are_validated_and_incomplete_rows_excluded(tmp_path: Path):
    pack = write_pack(
        tmp_path / "review" / "pdf_gold_review_pack_manual_v1_with_file_lookup.csv",
        [
            row("suggested-only"),
            reviewed_content_row("reviewed-content"),
        ],
    )
    rows = app.read_csv_rows(pack)
    validation = app.validate_review_pack(pack, rows=rows, config=config(tmp_path), selected_metadata=app.review_pack_metadata(pack))
    normalized = app.normalize_review_rows(rows, source_path=pack)
    statuses = {row["query_id"]: row["application_status"] for row in normalized}

    assert validation["complete_reviewed_row_count"] == 1
    assert validation["incomplete_review_row_count"] == 1
    assert statuses["suggested-only"] == app.APPLICATION_STATUS_EXCLUDED_INCOMPLETE
    assert statuses["reviewed-content"] == app.APPLICATION_STATUS_OFFICIAL
    assert normalized[0]["exclusion_reason"] == "missing_required_user_review_labels"


def test_file_vs_content_reviewed_policy_is_applied_and_mismatches_are_categorized(tmp_path: Path):
    rows = [
        reviewed_content_row("content-ok"),
        reviewed_content_row(
            "content-expected-file",
            user_expected_evidence_policy="PDF_FILE_LOOKUP",
            user_denominator_policy="INCLUDE_FILE_LOOKUP_DENOMINATOR_CANDIDATE",
        ),
        file_row(
            "file-expected-content",
            user_gold_decision="KEEP_POSITIVE",
            user_answerability_label="ANSWERABLE",
            user_relevance_label="RELEVANT",
            user_expected_evidence_policy="PDF_CONTENT_LOOKUP",
            user_denominator_policy="INCLUDE_POSITIVE_DENOMINATOR_AFTER_USER_REVIEW",
            user_issue_tags="TABLE_ALLOW PAGE_ALLOW BBOX_ALLOW",
        ),
    ]
    pack = write_pack(tmp_path / "review" / "pdf_gold_review_pack_manual_v1_with_file_lookup.csv", rows)
    normalized = app.normalize_review_rows(app.read_csv_rows(pack), source_path=pack)
    mismatches = {row["query_id"]: row["route_mismatch_category"] for row in normalized}

    assert mismatches["content-ok"] == "MATCH"
    assert mismatches["content-expected-file"] == app.FAIL_FILE_EXPECTED_CONTENT_ACTUAL
    assert mismatches["file-expected-content"] == app.FAIL_CONTENT_EXPECTED_FILE_ACTUAL


def test_table_page_bbox_policy_is_applied_and_missing_policy_requires_review(tmp_path: Path):
    reviewed_table = reviewed_content_row(
        "table-ok",
        review_group="table_or_range_policy_review",
        review_lane="HIGH_CONFIDENCE_TABLE_CANDIDATE",
        expected_bbox="[1,2,3,4]",
        user_issue_tags="TABLE_ALLOW PAGE_ALLOW BBOX_ALLOW",
    )
    missing_policy = reviewed_content_row(
        "table-missing-policy",
        review_group="table_or_range_policy_review",
        review_lane="HIGH_CONFIDENCE_TABLE_CANDIDATE",
        expected_bbox="[1,2,3,4]",
        user_issue_tags="",
    )
    pack = write_pack(tmp_path / "review" / "pdf_gold_review_pack_manual_v1_with_file_lookup.csv", [reviewed_table, missing_policy])
    normalized = app.normalize_review_rows(app.read_csv_rows(pack), source_path=pack)
    by_id = {row["query_id"]: row for row in normalized}

    assert by_id["table-ok"]["application_status"] == app.APPLICATION_STATUS_OFFICIAL
    assert by_id["table-ok"]["table_policy_status"] == "ALLOW"
    assert by_id["table-missing-policy"]["application_status"] == app.APPLICATION_STATUS_REVIEW_REQUIRED
    assert app.FAIL_TABLE_POLICY_MISSING in by_id["table-missing-policy"]["failure_categories"]
    assert app.FAIL_BBOX_POLICY_MISSING in by_id["table-missing-policy"]["failure_categories"]


def test_non_positive_review_labels_cannot_become_official_candidates(tmp_path: Path):
    pack = write_pack(
        tmp_path / "review" / "pdf_gold_review_pack_manual_v1_with_file_lookup.csv",
        [
            reviewed_content_row("not-answerable", user_answerability_label="NOT_ANSWERABLE"),
            reviewed_content_row("irrelevant", user_relevance_label="IRRELEVANT"),
            reviewed_content_row("partial", user_relevance_label="PARTIAL"),
        ],
    )
    normalized = app.normalize_review_rows(app.read_csv_rows(pack), source_path=pack)
    by_id = {row["query_id"]: row for row in normalized}

    assert by_id["not-answerable"]["application_status"] == app.APPLICATION_STATUS_EXCLUDED_POLICY_REJECTED
    assert by_id["irrelevant"]["application_status"] == app.APPLICATION_STATUS_EXCLUDED_POLICY_REJECTED
    assert by_id["partial"]["application_status"] == app.APPLICATION_STATUS_REVIEW_REQUIRED
    assert app.FAIL_ANSWERABILITY_NOT_POSITIVE in by_id["not-answerable"]["failure_categories"]
    assert app.FAIL_RELEVANCE_NOT_RELEVANT in by_id["irrelevant"]["failure_categories"]
    assert app.FAIL_REVIEW_LABEL_MALFORMED in by_id["partial"]["failure_categories"]


def test_table_page_bbox_policy_requires_scoped_policy_tokens(tmp_path: Path):
    pack = write_pack(
        tmp_path / "review" / "pdf_gold_review_pack_manual_v1_with_file_lookup.csv",
        [
            reviewed_content_row(
                "generic-allow",
                review_group="table_or_range_policy_review",
                review_lane="HIGH_CONFIDENCE_TABLE_CANDIDATE",
                expected_bbox="[1,2,3,4]",
                user_issue_tags="ALLOW",
            ),
            reviewed_content_row(
                "scoped-allow",
                review_group="table_or_range_policy_review",
                review_lane="HIGH_CONFIDENCE_TABLE_CANDIDATE",
                expected_bbox="[1,2,3,4]",
                user_issue_tags="TABLE_ALLOW PAGE_ALLOW BBOX_ALLOW",
            ),
        ],
    )
    normalized = app.normalize_review_rows(app.read_csv_rows(pack), source_path=pack)
    by_id = {row["query_id"]: row for row in normalized}

    assert by_id["generic-allow"]["application_status"] == app.APPLICATION_STATUS_REVIEW_REQUIRED
    assert by_id["generic-allow"]["table_policy_status"] == "MISSING"
    assert by_id["generic-allow"]["bbox_policy_status"] == "MISSING"
    assert by_id["scoped-allow"]["application_status"] == app.APPLICATION_STATUS_OFFICIAL
    assert by_id["scoped-allow"]["table_policy_status"] == "ALLOW"
    assert by_id["scoped-allow"]["bbox_policy_status"] == "ALLOW"


def test_reviewed_route_trace_covers_pdf_table_lane_and_keeps_answer_denominators_zero(tmp_path: Path):
    pack = write_pack(
        tmp_path / "review" / "pdf_gold_review_pack_manual_v1_with_file_lookup.csv",
        [
            reviewed_content_row("content-1"),
            reviewed_content_row("table-1", review_group="table_or_range_policy_review", review_lane="HIGH_CONFIDENCE_TABLE_CANDIDATE"),
            file_row("file-1"),
        ],
    )
    reports = build_reports_for_pack(tmp_path, pack)
    summary = reports["route_trace"]["pdf_reviewed_route_summary"]

    assert summary["table_lane_count"] == 1
    assert summary["file_lookup_count"] == 1
    assert summary["content_lookup_count"] == 2
    assert reports["route_trace"]["pdf_answer_denominator"] == 0
    assert reports["route_trace"]["xlsx_answer_denominator"] == 0
    assert reports["route_trace"]["promotion_evidence"] is False


def test_agentic_loop_uses_diagnostic_fixtures_to_exercise_retry_without_allow_unscoped(tmp_path: Path):
    pack = write_pack(tmp_path / "review" / "pdf_gold_review_pack_manual_v1_with_file_lookup.csv", [row("blank")])
    reports = build_reports_for_pack(tmp_path, pack)
    summary = reports["agentic_loop"]["agentic_retry_summary"]

    assert summary["max_attempt_count"] == 3
    assert summary["retry_path_exercised"] is True
    assert summary["allow_unscoped_true_count"] == 0
    assert reports["agentic_loop"]["answer_generation_execution"] == "not_run_by_this_harness"


def test_denominator_registry_is_proposal_only_and_not_mutated(tmp_path: Path):
    pack = write_pack(tmp_path / "review" / "pdf_gold_review_pack_manual_v1_with_file_lookup.csv", [reviewed_content_row("content-1")])
    registry = write_registry(tmp_path)
    before = registry.read_bytes()

    reports = build_reports_for_pack(tmp_path, pack, registry=registry)
    after = registry.read_bytes()

    assert before == after
    assert reports["application"]["denominator_registry_update_performed"] is False
    assert reports["application"]["denominator_proposal_only"] is True
    assert reports["application"]["proposed_pdf_retrieval_evidence_denominator"] == 1
    assert reports["application"]["pdf_answer_denominator"] == 0


def test_manifest_tracks_ignored_reports_with_hashes(tmp_path: Path):
    pack = write_pack(tmp_path / "review" / "pdf_gold_review_pack_manual_v1_with_file_lookup.csv", [row("blank"), file_row("file")])
    config = app.ReviewApplicationConfig(
        date="20260507",
        review_dir=pack.parent,
        report_dir=tmp_path / "reports",
        official_registry=write_registry(tmp_path),
        manifest_path=tmp_path / "reports" / "pdf_xlsx_review_application_manifest_20260507.toml",
    )

    reports = app.write_review_application_reports(config)
    manifest_path = Path(reports["manifest_path"])
    manifest = (ROOT / manifest_path).resolve() if not manifest_path.is_absolute() else manifest_path
    text = manifest.read_text(encoding="utf-8")

    assert "promotion_evidence = false" in text
    assert "official_denominator_changed = false" in text
    assert "source_review_pack_sha256" in text
    assert "validation_json_path" in text
    assert reports["manifest"]["included_row_count"] == 1
    assert reports["manifest"]["excluded_row_count"] == 1


def test_xlsx_hidden_leakage_fail_closed_for_silver_generation(tmp_path: Path):
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    (report_dir / "xlsx_pre_silver_risk_closure_20260507.json").write_text(
        json.dumps({"artifact_resolution_summary": {"registry_hashes_match_current_files": True}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (report_dir / "rag_xlsx_human_review_official_positive_v0_hidden_negative_leakage_diagnostic.json").write_text(
        json.dumps(
            {
                "hidden_negative_row_count": 1,
                "validation": {"ok": True},
                "metrics": {
                    "hidden_content_leakage_count": 1,
                    "search_error_count": 0,
                    "hidden_negative_pass_count": 0,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = app.build_xlsx_strict_silver_report(config(tmp_path, report_dir=report_dir))

    assert payload["status"] == app.STATUS_FAIL
    assert payload["silver_generation_status"] == "FAIL_CLOSED_HIDDEN_LEAKAGE_OR_STRICT_PATH_NOT_INTACT"
    assert payload["xlsx_answer_denominator"] == 0


def build_reports_for_pack(tmp_path: Path, pack: Path, registry: Path | None = None):
    return app.build_review_application_reports(
        app.ReviewApplicationConfig(
            date="20260507",
            review_dir=pack.parent,
            report_dir=tmp_path / "reports",
            official_registry=registry or write_registry(tmp_path),
            selected_review_pack=pack,
        )
    )


def config(tmp_path: Path, report_dir: Path | None = None):
    return app.ReviewApplicationConfig(
        date="20260507",
        review_dir=tmp_path / "review",
        report_dir=report_dir or tmp_path / "reports",
        official_registry=write_registry(tmp_path),
    )


def write_registry(tmp_path: Path) -> Path:
    path = tmp_path / "eval_queries" / "official_denominator_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "official_denominator_registry_v1",
        "current_defaults": {
            "track_a_xlsx": {
                "denominator_key": "track_a_xlsx_human_review_normalized_v0",
            }
        },
        "official_diagnostic_denominators": {
            "track_c_pdf_c7_conservative": {
                "official_positive_denominator": 7,
                "official_pdf_answer_generation_denominator": 0,
                "promotion_evidence": False,
            },
            "track_a_xlsx_human_review_normalized_v0": {
                "official_xlsx_answer_generation_denominator": 0,
                "official_positive_denominator": 23,
            },
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_pack(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames())
        writer.writeheader()
        for record in rows:
            base = {key: "" for key in fieldnames()}
            base.update(record)
            writer.writerow(base)
    return path


def row(query_id: str, **overrides: str) -> dict[str, str]:
    record = {
        "track": "PDF_MANUAL_REVIEW",
        "query_id": query_id,
        "retrieval_lane": "PDF_CONTENT_RETRIEVAL_REVIEW",
        "review_group": "positive_retrieval_review",
        "source_file_name": "source.pdf",
        "expected_file_name": "source.pdf",
        "expected_document_version_id": "docv-pdf-1",
        "expected_page_no": "2",
        "expected_page_label": "2",
        "expected_bbox": "",
        "query": "본문에서 필요한 근거를 찾아줘",
        "expected_evidence_excerpt": "review evidence text",
        "review_lane": "READY_EXTRACTIVE_CONTEXT",
        "suggested_gold_decision": "KEEP_POSITIVE",
        "suggested_answerability_label": "ANSWERABLE",
        "suggested_relevance_label": "RELEVANT",
        "suggested_expected_evidence_policy": "KEEP_CURRENT_EVIDENCE",
        "suggested_denominator_policy": "INCLUDE_POSITIVE_DENOMINATOR_AFTER_USER_REVIEW",
        "risk_tags": "pdf_review_lane:READY_EXTRACTIVE_CONTEXT",
    }
    record.update(overrides)
    return record


def reviewed_content_row(query_id: str, **overrides: str) -> dict[str, str]:
    record = row(
        query_id,
        user_gold_decision="KEEP_POSITIVE",
        user_answerability_label="ANSWERABLE",
        user_relevance_label="RELEVANT",
        user_expected_evidence_policy="PDF_CONTENT_LOOKUP",
        user_denominator_policy="INCLUDE_POSITIVE_DENOMINATOR_AFTER_USER_REVIEW",
        user_issue_tags="PAGE_ALLOW",
        user_notes="reviewed",
    )
    record.update(overrides)
    return record


def file_row(query_id: str, **overrides: str) -> dict[str, str]:
    record = row(
        query_id,
        track="PDF_FILE_LOOKUP_REVIEW",
        retrieval_lane="PDF_FILE_LOOKUP_BY_METADATA",
        review_group="file_lookup_companion_review",
        review_lane="PDF_FILE_LOOKUP_BY_METADATA",
        expected_page_no="",
        expected_page_label="",
        expected_bbox="",
        expected_evidence_excerpt="expected_file_name=source.pdf; document_identity=docv-pdf-1",
        risk_tags="PDF_FILE_LOOKUP;NO_PAGE_OR_BBOX_REQUIRED;METADATA_LOOKUP",
        suggested_answerability_label="ANSWERABLE_AS_FILE_LOOKUP",
        suggested_expected_evidence_policy="EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY",
        suggested_denominator_policy="INCLUDE_FILE_LOOKUP_DENOMINATOR_CANDIDATE",
        user_gold_decision="KEEP_POSITIVE",
        user_answerability_label="ANSWERABLE_AS_FILE_LOOKUP",
        user_relevance_label="RELEVANT",
        user_expected_evidence_policy="PDF_FILE_LOOKUP",
        user_denominator_policy="INCLUDE_FILE_LOOKUP_DENOMINATOR_CANDIDATE",
        user_issue_tags="FILE_ALLOW",
        user_notes="reviewed file identity",
    )
    record.update(overrides)
    return record


def fieldnames() -> list[str]:
    return [
        "track",
        "query_id",
        "retrieval_lane",
        "review_group",
        "source_file_name",
        "expected_file_name",
        "expected_document_version_id",
        "expected_page_no",
        "expected_page_label",
        "expected_bbox",
        "query",
        "expected_evidence_excerpt",
        "evidence_object_summary",
        "deterministic_draft",
        "review_lane",
        "suggested_gold_decision",
        "suggested_answerability_label",
        "suggested_relevance_label",
        "suggested_expected_evidence_policy",
        "suggested_denominator_policy",
        "risk_tags",
        "diagnostic_reason",
        "user_gold_decision",
        "user_answerability_label",
        "user_relevance_label",
        "user_expected_evidence_policy",
        "user_denominator_policy",
        "user_issue_tags",
        "user_notes",
    ]
